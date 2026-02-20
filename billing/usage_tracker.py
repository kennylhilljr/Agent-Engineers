"""Usage tracker for Agent Dashboard (AI-221).

Tracks agent-session hours per user and can flush usage to Stripe
as metered billing records.

Persistence: JSON file at data/usage_log.json
"""

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_USAGE_LOG_FILE = Path(__file__).parent.parent / "data" / "usage_log.json"


@dataclass
class UsageEntry:
    """A single usage record for a user session."""

    user_id: str
    session_id: str
    hours: float
    date: str  # ISO date string (YYYY-MM-DD)
    timestamp: float  # Unix timestamp when recorded
    reported_to_stripe: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


class UsageTracker:
    """Tracks agent-session usage per user and reports to Stripe.

    Args:
        log_file: Path to the JSON persistence file.
            Defaults to ``data/usage_log.json`` in project root.
    """

    def __init__(self, log_file: Optional[Path] = None) -> None:
        self._log_file = log_file or DEFAULT_USAGE_LOG_FILE
        self._entries: List[UsageEntry] = []
        self._log_file.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Load usage entries from JSON file."""
        try:
            if self._log_file.exists():
                raw = json.loads(self._log_file.read_text(encoding="utf-8"))
                for item in raw.get("entries", []):
                    self._entries.append(
                        UsageEntry(
                            user_id=item["user_id"],
                            session_id=item["session_id"],
                            hours=float(item.get("hours", 0.0)),
                            date=item.get("date", ""),
                            timestamp=float(item.get("timestamp", 0.0)),
                            reported_to_stripe=bool(
                                item.get("reported_to_stripe", False)
                            ),
                        )
                    )
                logger.debug(
                    f"UsageTracker: loaded {len(self._entries)} usage entries"
                )
        except Exception as exc:
            logger.warning(f"UsageTracker: could not load log file: {exc}")

    def _save(self) -> None:
        """Persist usage entries to JSON file. Keeps last 10,000 entries."""
        try:
            payload = {
                "entries": [e.to_dict() for e in self._entries[-10_000:]]
            }
            self._log_file.write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            logger.warning(f"UsageTracker: could not save log file: {exc}")

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_agent_session(
        self,
        user_id: str,
        session_id: str,
        hours: float,
        timestamp: Optional[float] = None,
    ) -> UsageEntry:
        """Record completed agent session usage.

        Args:
            user_id: Internal user identifier.
            session_id: Unique session identifier.
            hours: Duration of the session in hours.
            timestamp: Unix timestamp (defaults to now).

        Returns:
            The created UsageEntry.
        """
        if hours < 0:
            raise ValueError(f"hours must be non-negative, got {hours}")

        ts = timestamp or time.time()
        entry_date = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()

        entry = UsageEntry(
            user_id=user_id,
            session_id=session_id,
            hours=round(hours, 4),
            date=entry_date,
            timestamp=ts,
            reported_to_stripe=False,
        )
        self._entries.append(entry)
        self._save()
        logger.info(
            f"UsageTracker: recorded session user={user_id} "
            f"session={session_id} hours={hours:.4f}"
        )
        return entry

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def get_daily_usage(self, user_id: str, target_date: date) -> float:
        """Return total hours used by a user on a specific date.

        Args:
            user_id: Internal user identifier.
            target_date: Date to query (datetime.date object or YYYY-MM-DD string).

        Returns:
            Total hours as float.
        """
        if isinstance(target_date, str):
            date_str = target_date
        else:
            date_str = target_date.isoformat()

        total = sum(
            e.hours
            for e in self._entries
            if e.user_id == user_id and e.date == date_str
        )
        return round(total, 4)

    def get_monthly_usage(self, user_id: str, year: int, month: int) -> float:
        """Return total hours used by a user in a specific month.

        Args:
            user_id: Internal user identifier.
            year: Calendar year (e.g. 2024).
            month: Calendar month (1-12).

        Returns:
            Total hours as float.
        """
        prefix = f"{year:04d}-{month:02d}-"
        total = sum(
            e.hours
            for e in self._entries
            if e.user_id == user_id and e.date.startswith(prefix)
        )
        return round(total, 4)

    def get_user_entries(
        self,
        user_id: str,
        limit: int = 100,
    ) -> List[UsageEntry]:
        """Return recent usage entries for a user.

        Args:
            user_id: Internal user identifier.
            limit: Maximum entries to return (most recent first).

        Returns:
            List of UsageEntry objects.
        """
        entries = [e for e in self._entries if e.user_id == user_id]
        return sorted(entries, key=lambda e: e.timestamp, reverse=True)[:limit]

    def get_pending_stripe_entries(self, user_id: Optional[str] = None) -> List[UsageEntry]:
        """Return usage entries not yet reported to Stripe.

        Args:
            user_id: Filter by user (None returns all users).

        Returns:
            List of unreported UsageEntry objects.
        """
        entries = [e for e in self._entries if not e.reported_to_stripe]
        if user_id is not None:
            entries = [e for e in entries if e.user_id == user_id]
        return entries

    # ------------------------------------------------------------------
    # Stripe Reporting
    # ------------------------------------------------------------------

    async def flush_to_stripe(
        self,
        stripe_client: Any,
        subscription_store: Any,
    ) -> Dict[str, Any]:
        """Report all pending usage records to Stripe.

        This is a mock implementation for AI-221. In production, you would:
        1. Look up the subscription_item_id for each user from their subscription
        2. Call stripe_client.report_usage(subscription_item_id, quantity, timestamp)
        3. Mark entries as reported

        Args:
            stripe_client: StripeClient instance (or None to skip actual API calls)
            subscription_store: SubscriptionStore instance

        Returns:
            Summary dict with reported counts.
        """
        pending = self.get_pending_stripe_entries()
        if not pending:
            return {"reported": 0, "skipped": 0, "errors": 0}

        reported = 0
        skipped = 0
        errors = 0

        # Group by user_id for efficiency
        user_entries: Dict[str, List[UsageEntry]] = {}
        for entry in pending:
            user_entries.setdefault(entry.user_id, []).append(entry)

        for user_id, entries in user_entries.items():
            sub_record = subscription_store.get_subscription(user_id)
            if not sub_record or not sub_record.stripe_subscription_id:
                # Explorer users or users without Stripe subscription - skip silently
                skipped += len(entries)
                continue

            # In a real implementation, we'd get the subscription item ID from Stripe
            # For now, mark as reported (mock)
            total_hours = sum(e.hours for e in entries)
            logger.info(
                f"UsageTracker.flush_to_stripe: (mock) reporting {total_hours:.4f}h "
                f"for user={user_id}"
            )

            # Mock: mark entries as reported
            for entry in entries:
                entry.reported_to_stripe = True
                reported += 1

        self._save()
        return {"reported": reported, "skipped": skipped, "errors": errors}


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_global_usage_tracker: Optional[UsageTracker] = None


def get_usage_tracker() -> UsageTracker:
    """Return the global UsageTracker singleton (lazy init)."""
    global _global_usage_tracker
    if _global_usage_tracker is None:
        _global_usage_tracker = UsageTracker()
    return _global_usage_tracker


def reset_usage_tracker() -> None:
    """Reset the global UsageTracker singleton (useful for testing)."""
    global _global_usage_tracker
    _global_usage_tracker = None
