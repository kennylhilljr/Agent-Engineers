"""Audit log data models for Agent Dashboard (AI-246).

Provides:
    - AuditEntry: immutable audit log entry (append-only design)
    - AuditStore: append-only in-memory store with cursor-based pagination,
      retention policy enforcement, and CSV/JSON export

PostgreSQL design notes (for future migration):
    CREATE TABLE audit_log (
        entry_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        org_id      TEXT NOT NULL,
        actor_id    TEXT NOT NULL,
        event_type  TEXT NOT NULL,
        resource_id TEXT,
        details     JSONB NOT NULL DEFAULT '{}',
        timestamp   TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    -- No UPDATE or DELETE triggers/permissions on this table.
    -- Retention enforced via pg_partman or a background job that ARCHIVEs
    -- rows older than the org's retention window to cold storage before deletion.
    CREATE INDEX ON audit_log (org_id, timestamp DESC);
    CREATE INDEX ON audit_log (org_id, actor_id);
    CREATE INDEX ON audit_log (org_id, event_type);
"""

import csv
import io
import json
import os
import types
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple

from audit.events import ALL_EVENT_TYPES

# ---------------------------------------------------------------------------
# Retention policy constants
# ---------------------------------------------------------------------------

#: Retention in days for free/starter tier
RETENTION_DAYS_FREE = 90

#: Retention in days for organization/enterprise tier
RETENTION_DAYS_ORG = 365

#: Plan tiers that receive the extended (1-year) retention window
ORG_TIER_PLANS = {"organization", "enterprise", "org", "business"}


def retention_days_for_plan(plan: str) -> int:
    """Return the number of retention days for the given subscription plan."""
    return RETENTION_DAYS_ORG if plan.lower() in ORG_TIER_PLANS else RETENTION_DAYS_FREE


# ---------------------------------------------------------------------------
# AuditEntry — immutable log entry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditEntry:
    """A single immutable audit log entry.

    ``frozen=True`` means instances cannot be mutated after creation,
    enforcing immutability at the Python level.
    """

    entry_id: str
    org_id: str
    actor_id: str        # user_id of the actor
    event_type: str      # one of audit.events.*
    resource_id: str     # ID of the affected resource (agent, project, user, …)
    details: Mapping[str, Any]
    timestamp: str       # ISO-8601 UTC string

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        org_id: str,
        actor_id: str,
        event_type: str,
        resource_id: str = "",
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> "AuditEntry":
        """Create a new immutable AuditEntry with a generated entry_id."""
        ts = timestamp or datetime.now(timezone.utc)
        # Wrap in MappingProxyType so the dict contents cannot be mutated
        # after creation, even though the dataclass is frozen=True.
        frozen_details = types.MappingProxyType(dict(details or {}))
        return cls(
            entry_id=str(uuid.uuid4()),
            org_id=org_id,
            actor_id=actor_id,
            event_type=event_type,
            resource_id=resource_id or "",
            details=frozen_details,
            timestamp=ts.isoformat(),
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serialisable dict representation."""
        return {
            "entry_id": self.entry_id,
            "org_id": self.org_id,
            "actor_id": self.actor_id,
            "event_type": self.event_type,
            "resource_id": self.resource_id,
            "details": dict(self.details),
            "timestamp": self.timestamp,
        }

    def to_csv_row(self) -> List[str]:
        """Return a flat list of strings suitable for a CSV row."""
        return [
            self.entry_id,
            self.org_id,
            self.actor_id,
            self.event_type,
            self.resource_id,
            json.dumps(dict(self.details)),
            self.timestamp,
        ]

    @staticmethod
    def csv_header() -> List[str]:
        """Return the CSV column header row."""
        return [
            "entry_id",
            "org_id",
            "actor_id",
            "event_type",
            "resource_id",
            "details",
            "timestamp",
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def timestamp_dt(self) -> datetime:
        """Parse the ISO-8601 timestamp string into a timezone-aware datetime."""
        return datetime.fromisoformat(self.timestamp)


# ---------------------------------------------------------------------------
# AuditStore — append-only, in-memory
# ---------------------------------------------------------------------------


class ImmutabilityError(Exception):
    """Raised when code attempts to modify or delete an audit entry."""


class AuditStore:
    """Append-only in-memory audit log store.

    Design constraints:
        - Entries are never modified or deleted (raises ImmutabilityError).
        - Retention policy removes entries older than the configured window
          only via :meth:`enforce_retention`, NOT via ad-hoc deletion.
        - Supports cursor-based pagination for the API layer.
        - Filterable by actor_id, event_type, date range, and resource_id.

    Thread safety note: The current implementation uses a plain list and is
    NOT thread-safe. Wrap with asyncio.Lock or use a thread-safe queue in
    production.
    """

    _MAX_ENTRIES = 100_000  # hard cap; oldest trimmed to 50k on overflow

    def __init__(self) -> None:
        # Ordered list of AuditEntry objects, oldest first
        self._entries: List[AuditEntry] = []
        # cursor → index mapping: cursor is the entry_id of the last seen item
        # (stored as a set for O(1) lookup of validity)
        self._entry_id_set: set = set()

    # ------------------------------------------------------------------
    # Append
    # ------------------------------------------------------------------

    def record(
        self,
        org_id: str,
        actor_id: str,
        event_type: str,
        resource_id: str = "",
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ) -> AuditEntry:
        """Append a new audit entry and return it.

        Args:
            org_id:      Organisation that owns this event.
            actor_id:    User (or system) that triggered the event.
            event_type:  One of the ``audit.events.*`` constants.
            resource_id: Optional ID of the affected resource.
            details:     Arbitrary JSON-serialisable key-value metadata.
            timestamp:   Override timestamp (UTC); defaults to now().

        Returns:
            The newly created, immutable AuditEntry.
        """
        entry = AuditEntry.create(
            org_id=org_id,
            actor_id=actor_id,
            event_type=event_type,
            resource_id=resource_id,
            details=details,
            timestamp=timestamp,
        )
        self._entries.append(entry)
        self._entry_id_set.add(entry.entry_id)

        # Hard cap: trim oldest half if overflow
        if len(self._entries) > self._MAX_ENTRIES:
            removed = self._entries[: self._MAX_ENTRIES // 2]
            self._entries = self._entries[self._MAX_ENTRIES // 2 :]
            for e in removed:
                self._entry_id_set.discard(e.entry_id)

        return entry

    # ------------------------------------------------------------------
    # Immutability guards (public interface to enforce the design contract)
    # ------------------------------------------------------------------

    def modify(self, *args: Any, **kwargs: Any) -> None:
        """Modification is prohibited on an audit log store."""
        raise ImmutabilityError(
            "Audit log entries are immutable. Modifications are not permitted."
        )

    def delete(self, *args: Any, **kwargs: Any) -> None:
        """Deletion is prohibited on an audit log store."""
        raise ImmutabilityError(
            "Audit log entries are immutable. Deletions are not permitted."
        )

    # ------------------------------------------------------------------
    # Querying / filtering
    # ------------------------------------------------------------------

    def _iter_filtered(
        self,
        org_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        event_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> Iterator[AuditEntry]:
        """Iterate over entries newest-first, applying all active filters."""
        for entry in reversed(self._entries):
            if org_id and entry.org_id != org_id:
                continue
            if actor_id and entry.actor_id != actor_id:
                continue
            if event_type and entry.event_type != event_type:
                continue
            if resource_id and entry.resource_id != resource_id:
                continue
            ts = entry.timestamp_dt
            if since and ts < since:
                continue
            if until and ts > until:
                continue
            yield entry

    def get_entries(
        self,
        org_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        event_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> Tuple[List[AuditEntry], Optional[str]]:
        """Return a page of entries with cursor-based pagination.

        Args:
            org_id:      Filter by organisation ID.
            actor_id:    Filter by actor user ID.
            event_type:  Filter by event type string.
            resource_id: Filter by resource ID.
            since:       Include only entries at or after this UTC datetime.
            until:       Include only entries at or before this UTC datetime.
            limit:       Maximum entries to return (default 50, max 500).
            cursor:      Opaque cursor from a previous response (entry_id of
                         the last item in the previous page).

        Returns:
            A 2-tuple ``(entries, next_cursor)`` where ``next_cursor`` is
            ``None`` when there are no further pages.
        """
        limit = min(max(1, limit), 500)

        filtered = list(
            self._iter_filtered(
                org_id=org_id,
                actor_id=actor_id,
                event_type=event_type,
                resource_id=resource_id,
                since=since,
                until=until,
            )
        )

        # Advance past cursor
        start = 0
        if cursor:
            for idx, entry in enumerate(filtered):
                if entry.entry_id == cursor:
                    start = idx + 1
                    break

        page = filtered[start : start + limit]
        next_cursor: Optional[str] = None
        if start + limit < len(filtered):
            next_cursor = page[-1].entry_id if page else None

        return page, next_cursor

    def count(
        self,
        org_id: Optional[str] = None,
        event_type: Optional[str] = None,
    ) -> int:
        """Return the number of entries matching the given filters."""
        return sum(1 for _ in self._iter_filtered(org_id=org_id, event_type=event_type))

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------

    def enforce_retention(self, plan: str = "free", org_id: Optional[str] = None) -> int:
        """Remove entries older than the retention window for the given plan.

        This is the ONLY legitimate way to remove entries from the store.
        It simulates what a background job would do in production
        (archive then delete aged rows).

        Args:
            plan:   Subscription plan name (determines retention window).
            org_id: If provided, only apply retention to this org's entries.

        Returns:
            Number of entries removed.
        """
        days = retention_days_for_plan(plan)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        kept: List[AuditEntry] = []
        removed_count = 0

        for entry in self._entries:
            should_remove = entry.timestamp_dt < cutoff
            if org_id:
                should_remove = should_remove and entry.org_id == org_id

            if should_remove:
                self._entry_id_set.discard(entry.entry_id)
                removed_count += 1
            else:
                kept.append(entry)

        self._entries = kept
        return removed_count

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_csv(
        self,
        org_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        event_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> str:
        """Export ALL matching entries as a CSV string (header + rows).

        Iterates all pages to avoid the 500-entry truncation bug.
        """
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(AuditEntry.csv_header())

        all_entries: List[AuditEntry] = []
        cursor: Optional[str] = None
        while True:
            page, next_cursor = self.get_entries(
                org_id=org_id,
                actor_id=actor_id,
                event_type=event_type,
                resource_id=resource_id,
                since=since,
                until=until,
                cursor=cursor,
                limit=1000,
            )
            all_entries.extend(page)
            if next_cursor is None:
                break
            cursor = next_cursor

        for entry in all_entries:
            writer.writerow(entry.to_csv_row())

        return output.getvalue()

    def export_json(
        self,
        org_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        event_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> str:
        """Export ALL matching entries as a JSON string.

        Iterates all pages to avoid the 500-entry truncation bug.
        Includes ``total_exported`` count in the metadata.
        """
        all_entries: List[AuditEntry] = []
        cursor: Optional[str] = None
        while True:
            page, next_cursor = self.get_entries(
                org_id=org_id,
                actor_id=actor_id,
                event_type=event_type,
                resource_id=resource_id,
                since=since,
                until=until,
                cursor=cursor,
                limit=1000,
            )
            all_entries.extend(page)
            if next_cursor is None:
                break
            cursor = next_cursor

        return json.dumps(
            {
                "audit_log": [e.to_dict() for e in all_entries],
                "count": len(all_entries),
                "total_exported": len(all_entries),
                "exported_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )

    # ------------------------------------------------------------------
    # Testing helpers
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Remove all entries. ONLY allowed in test/development environments."""
        env = os.environ.get("ENVIRONMENT", "production").lower()
        if env not in ("test", "testing", "development"):
            raise ImmutabilityError(
                "clear() is not allowed in production environment"
            )
        self._entries.clear()
        self._entry_id_set.clear()

    @property
    def total_count(self) -> int:
        """Total number of entries currently in the store."""
        return len(self._entries)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_store: Optional[AuditStore] = None


def get_audit_store() -> AuditStore:
    """Return the global AuditStore singleton."""
    global _store
    if _store is None:
        _store = AuditStore()
    return _store


def reset_audit_store() -> None:
    """Reset the global singleton (for testing isolation)."""
    global _store
    _store = AuditStore()
