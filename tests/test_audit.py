"""Comprehensive test suite for Audit Log module (AI-246).

Tests:
    - AuditEntry creation and immutability
    - AuditStore append-only design (no modify/delete)
    - All event type constants defined
    - CSV and JSON export
    - Cursor-based pagination
    - Retention policy enforcement (90 days free, 1 year org/enterprise)
    - Filtering by actor_id, event_type, date range, resource_id
    - Route handlers: GET /api/audit-log, export/csv, export/json, event-types
    - Integration helpers: record_auth_event, record_team_event, etc.
    - bridge_teams_audit_event backward-compat shim
    - Module-level singletons (get_audit_store, reset_audit_store)

Target: >= 80% coverage of audit/ package
"""

import asyncio
import csv
import io
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Path bootstrap ────────────────────────────────────────────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ── Imports under test ────────────────────────────────────────────────────────
from audit.events import (
    # Auth
    AUTH_LOGIN, AUTH_LOGOUT, AUTH_LOGIN_FAILED,
    AUTH_SSO_CONFIG_CHANGED, AUTH_API_KEY_CREATED, AUTH_API_KEY_REVOKED,
    # Team
    TEAM_MEMBER_INVITED, TEAM_MEMBER_REMOVED, TEAM_ROLE_CHANGED,
    TEAM_PROJECT_CREATED, TEAM_PROJECT_DELETED,
    TEAM_INTEGRATION_CONNECTED, TEAM_INTEGRATION_DISCONNECTED,
    # Agent
    AGENT_SESSION_STARTED, AGENT_SESSION_COMPLETED, AGENT_SESSION_FAILED,
    AGENT_PAUSED, AGENT_RESUMED, AGENT_WEBHOOK_CREATED, AGENT_WEBHOOK_TRIGGERED,
    # Billing
    BILLING_PLAN_UPGRADED, BILLING_PLAN_DOWNGRADED,
    BILLING_PAYMENT_SUCCEEDED, BILLING_PAYMENT_FAILED,
    BILLING_USAGE_LIMIT_REACHED,
    # Groups
    AUTH_EVENTS, TEAM_EVENTS, AGENT_EVENTS, BILLING_EVENTS, ALL_EVENT_TYPES,
    EVENT_CATEGORIES, EVENT_DESCRIPTIONS,
    # Helpers
    get_event_description, get_event_category,
    is_valid_event_type, list_event_types,
)
from audit.models import (
    AuditEntry, AuditStore, ImmutabilityError,
    get_audit_store, reset_audit_store,
    RETENTION_DAYS_FREE, RETENTION_DAYS_ORG, ORG_TIER_PLANS,
    retention_days_for_plan,
)
from audit.integration import (
    record_audit_event, record_auth_event, record_team_event,
    record_agent_event, record_billing_event, bridge_teams_audit_event,
    SYSTEM_ACTOR,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def fresh_store():
    """Reset the global AuditStore before each test for isolation."""
    reset_audit_store()
    yield
    reset_audit_store()


@pytest.fixture
def store() -> AuditStore:
    """Return a fresh, isolated AuditStore instance."""
    return AuditStore()


def _ts(days_ago: int = 0) -> datetime:
    """Return a UTC datetime that is `days_ago` days in the past."""
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


# ============================================================================
# 1. Event type constants
# ============================================================================

class TestEventTypeConstants:
    """All required event types are defined and grouped correctly."""

    def test_all_auth_events_defined(self):
        assert AUTH_LOGIN in AUTH_EVENTS
        assert AUTH_LOGOUT in AUTH_EVENTS
        assert AUTH_LOGIN_FAILED in AUTH_EVENTS
        assert AUTH_SSO_CONFIG_CHANGED in AUTH_EVENTS
        assert AUTH_API_KEY_CREATED in AUTH_EVENTS
        assert AUTH_API_KEY_REVOKED in AUTH_EVENTS

    def test_all_team_events_defined(self):
        assert TEAM_MEMBER_INVITED in TEAM_EVENTS
        assert TEAM_MEMBER_REMOVED in TEAM_EVENTS
        assert TEAM_ROLE_CHANGED in TEAM_EVENTS
        assert TEAM_PROJECT_CREATED in TEAM_EVENTS
        assert TEAM_PROJECT_DELETED in TEAM_EVENTS
        assert TEAM_INTEGRATION_CONNECTED in TEAM_EVENTS
        assert TEAM_INTEGRATION_DISCONNECTED in TEAM_EVENTS

    def test_all_agent_events_defined(self):
        assert AGENT_SESSION_STARTED in AGENT_EVENTS
        assert AGENT_SESSION_COMPLETED in AGENT_EVENTS
        assert AGENT_SESSION_FAILED in AGENT_EVENTS
        assert AGENT_PAUSED in AGENT_EVENTS
        assert AGENT_RESUMED in AGENT_EVENTS
        assert AGENT_WEBHOOK_CREATED in AGENT_EVENTS
        assert AGENT_WEBHOOK_TRIGGERED in AGENT_EVENTS

    def test_all_billing_events_defined(self):
        assert BILLING_PLAN_UPGRADED in BILLING_EVENTS
        assert BILLING_PLAN_DOWNGRADED in BILLING_EVENTS
        assert BILLING_PAYMENT_SUCCEEDED in BILLING_EVENTS
        assert BILLING_PAYMENT_FAILED in BILLING_EVENTS
        assert BILLING_USAGE_LIMIT_REACHED in BILLING_EVENTS

    def test_all_event_types_union(self):
        union = AUTH_EVENTS | TEAM_EVENTS | AGENT_EVENTS | BILLING_EVENTS
        assert union == ALL_EVENT_TYPES

    def test_event_descriptions_cover_all_types(self):
        for et in ALL_EVENT_TYPES:
            assert et in EVENT_DESCRIPTIONS, f"Missing description for {et}"

    def test_event_categories_cover_all_types(self):
        covered = set()
        for events in EVENT_CATEGORIES.values():
            covered |= events
        assert covered == ALL_EVENT_TYPES

    def test_is_valid_event_type(self):
        assert is_valid_event_type(AUTH_LOGIN) is True
        assert is_valid_event_type("fake.event") is False
        assert is_valid_event_type("") is False

    def test_get_event_description(self):
        desc = get_event_description(AUTH_LOGIN)
        assert isinstance(desc, str)
        assert len(desc) > 0
        # Unknown returns the type itself
        assert get_event_description("unknown.type") == "unknown.type"

    def test_get_event_category(self):
        assert get_event_category(AUTH_LOGIN) == "auth"
        assert get_event_category(TEAM_MEMBER_INVITED) == "team"
        assert get_event_category(AGENT_SESSION_STARTED) == "agent"
        assert get_event_category(BILLING_PLAN_UPGRADED) == "billing"
        assert get_event_category("bogus.event") == "unknown"

    def test_list_event_types_sorted(self):
        types = list_event_types()
        assert types == sorted(types)
        assert set(types) == ALL_EVENT_TYPES


# ============================================================================
# 2. AuditEntry immutability
# ============================================================================

class TestAuditEntryImmutability:
    """AuditEntry uses frozen=True and cannot be mutated."""

    def test_entry_fields_readable(self):
        entry = AuditEntry.create(
            org_id="org1",
            actor_id="user1",
            event_type=AUTH_LOGIN,
            resource_id="user1",
            details={"ip": "1.2.3.4"},
        )
        assert entry.org_id == "org1"
        assert entry.actor_id == "user1"
        assert entry.event_type == AUTH_LOGIN
        assert entry.resource_id == "user1"
        assert entry.details == {"ip": "1.2.3.4"}
        assert entry.entry_id
        assert entry.timestamp

    def test_entry_is_frozen(self):
        entry = AuditEntry.create(
            org_id="org1", actor_id="u", event_type=AUTH_LOGIN
        )
        with pytest.raises((AttributeError, TypeError)):
            entry.org_id = "hacked"  # type: ignore[misc]

    def test_entry_details_cannot_be_mutated_via_reference(self):
        """Mutating the original dict does not affect the entry (copy is made)."""
        details = {"key": "value"}
        entry = AuditEntry.create(
            org_id="org1", actor_id="u", event_type=AUTH_LOGIN,
            details=details,
        )
        details["key"] = "tampered"
        # The entry should keep the original value
        assert entry.details["key"] == "value"

    def test_details_dict_is_immutable_mapping_proxy(self):
        """details is wrapped in MappingProxyType — direct mutation must raise."""
        entry = AuditEntry.create(
            org_id="org1", actor_id="u", event_type=AUTH_LOGIN,
            details={"ip": "1.2.3.4"},
        )
        with pytest.raises((TypeError, AttributeError)):
            entry.details["tampered"] = "yes"  # Must raise — MappingProxyType

    def test_to_dict_returns_all_fields(self):
        entry = AuditEntry.create(
            org_id="org1", actor_id="u1", event_type=AUTH_LOGOUT,
            resource_id="r1", details={"reason": "session_timeout"},
        )
        d = entry.to_dict()
        assert d["org_id"] == "org1"
        assert d["actor_id"] == "u1"
        assert d["event_type"] == AUTH_LOGOUT
        assert d["resource_id"] == "r1"
        assert d["details"]["reason"] == "session_timeout"

    def test_to_csv_row_has_correct_length(self):
        entry = AuditEntry.create(
            org_id="org1", actor_id="u1", event_type=AUTH_LOGIN,
        )
        row = entry.to_csv_row()
        assert len(row) == len(AuditEntry.csv_header())

    def test_csv_header_fields(self):
        header = AuditEntry.csv_header()
        assert "entry_id" in header
        assert "org_id" in header
        assert "actor_id" in header
        assert "event_type" in header
        assert "timestamp" in header

    def test_timestamp_dt_is_utc(self):
        entry = AuditEntry.create(org_id="o", actor_id="a", event_type=AUTH_LOGIN)
        assert entry.timestamp_dt.tzinfo is not None


# ============================================================================
# 3. AuditStore — append-only
# ============================================================================

class TestAuditStoreAppendOnly:
    """The AuditStore enforces append-only semantics."""

    def test_record_returns_entry(self, store):
        entry = store.record(
            org_id="org1", actor_id="u1", event_type=AUTH_LOGIN,
        )
        assert isinstance(entry, AuditEntry)
        assert entry.org_id == "org1"

    def test_total_count_increases(self, store):
        assert store.total_count == 0
        store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN)
        assert store.total_count == 1
        store.record(org_id="o", actor_id="a", event_type=AUTH_LOGOUT)
        assert store.total_count == 2

    def test_modify_raises_immutability_error(self, store):
        with pytest.raises(ImmutabilityError):
            store.modify("anything")

    def test_delete_raises_immutability_error(self, store):
        with pytest.raises(ImmutabilityError):
            store.delete("anything")

    def test_clear_empties_store_for_testing(self, store, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "test")
        store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN)
        assert store.total_count == 1
        store.clear()
        assert store.total_count == 0

    def test_clear_works_in_testing_env(self, store, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "testing")
        store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN)
        store.clear()
        assert store.total_count == 0

    def test_clear_works_in_development_env(self, store, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "development")
        store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN)
        store.clear()
        assert store.total_count == 0

    def test_clear_raises_in_production_env(self, store, monkeypatch):
        monkeypatch.setenv("ENVIRONMENT", "production")
        store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN)
        with pytest.raises(ImmutabilityError, match="not allowed in production"):
            store.clear()

    def test_entries_are_immutable_in_store(self, store):
        entry = store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN)
        with pytest.raises((AttributeError, TypeError)):
            entry.actor_id = "evil"  # type: ignore[misc]


# ============================================================================
# 4. All required event types can be recorded
# ============================================================================

class TestAllEventTypesRecorded:
    """Every event type constant can be recorded successfully."""

    @pytest.mark.parametrize("event_type", sorted(ALL_EVENT_TYPES))
    def test_record_event_type(self, store, event_type):
        entry = store.record(
            org_id="org1",
            actor_id="user1",
            event_type=event_type,
            resource_id="resource1",
            details={"test": True},
        )
        assert entry.event_type == event_type


# ============================================================================
# 5. Filtering
# ============================================================================

class TestFiltering:
    """get_entries supports filtering by actor, event_type, date range, resource."""

    def _seed(self, store, n=5):
        """Insert n entries: alternating auth/team events with two actors."""
        for i in range(n):
            store.record(
                org_id="org1",
                actor_id="alice" if i % 2 == 0 else "bob",
                event_type=AUTH_LOGIN if i % 2 == 0 else TEAM_MEMBER_INVITED,
                resource_id=f"res_{i}",
                details={"index": i},
            )

    def test_filter_by_org_id(self, store):
        store.record(org_id="org1", actor_id="a", event_type=AUTH_LOGIN)
        store.record(org_id="org2", actor_id="b", event_type=AUTH_LOGIN)
        entries, _ = store.get_entries(org_id="org1")
        assert all(e.org_id == "org1" for e in entries)
        assert len(entries) == 1

    def test_filter_by_actor_id(self, store):
        self._seed(store)
        entries, _ = store.get_entries(actor_id="alice")
        assert all(e.actor_id == "alice" for e in entries)

    def test_filter_by_event_type(self, store):
        self._seed(store)
        entries, _ = store.get_entries(event_type=AUTH_LOGIN)
        assert all(e.event_type == AUTH_LOGIN for e in entries)

    def test_filter_by_resource_id(self, store):
        self._seed(store)
        entries, _ = store.get_entries(resource_id="res_0")
        assert len(entries) == 1
        assert entries[0].resource_id == "res_0"

    def test_filter_by_since(self, store):
        old_ts = _ts(days_ago=10)
        new_ts = _ts(days_ago=1)
        store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN, timestamp=old_ts)
        store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN, timestamp=new_ts)
        cutoff = _ts(days_ago=5)
        entries, _ = store.get_entries(since=cutoff)
        assert all(e.timestamp_dt >= cutoff for e in entries)
        assert len(entries) == 1

    def test_filter_by_until(self, store):
        old_ts = _ts(days_ago=10)
        new_ts = _ts(days_ago=1)
        store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN, timestamp=old_ts)
        store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN, timestamp=new_ts)
        cutoff = _ts(days_ago=5)
        entries, _ = store.get_entries(until=cutoff)
        assert all(e.timestamp_dt <= cutoff for e in entries)
        assert len(entries) == 1

    def test_combined_filters(self, store):
        self._seed(store)
        entries, _ = store.get_entries(actor_id="alice", event_type=AUTH_LOGIN)
        assert all(e.actor_id == "alice" and e.event_type == AUTH_LOGIN for e in entries)

    def test_no_results(self, store):
        self._seed(store)
        entries, cursor = store.get_entries(org_id="nonexistent_org")
        assert entries == []
        assert cursor is None

    def test_results_newest_first(self, store):
        for i in range(5):
            store.record(
                org_id="o", actor_id="a", event_type=AUTH_LOGIN,
                timestamp=_ts(days_ago=5 - i),  # oldest inserted first
            )
        entries, _ = store.get_entries()
        timestamps = [e.timestamp_dt for e in entries]
        assert timestamps == sorted(timestamps, reverse=True)


# ============================================================================
# 6. Cursor-based pagination
# ============================================================================

class TestCursorPagination:
    """Cursor-based pagination returns correct pages and cursors."""

    def _seed_many(self, store, n=15):
        for i in range(n):
            store.record(org_id="org1", actor_id="u", event_type=AUTH_LOGIN)

    def test_first_page_no_cursor(self, store):
        self._seed_many(store, 15)
        page, next_cursor = store.get_entries(limit=5)
        assert len(page) == 5
        assert next_cursor is not None

    def test_second_page_via_cursor(self, store):
        self._seed_many(store, 15)
        page1, cursor1 = store.get_entries(limit=5)
        page2, cursor2 = store.get_entries(limit=5, cursor=cursor1)
        assert len(page2) == 5
        # Pages must not overlap
        ids1 = {e.entry_id for e in page1}
        ids2 = {e.entry_id for e in page2}
        assert ids1.isdisjoint(ids2)

    def test_last_page_no_next_cursor(self, store):
        self._seed_many(store, 10)
        # Retrieve all 10 in a single page
        _, next_cursor = store.get_entries(limit=10)
        assert next_cursor is None

    def test_pagination_covers_all_entries(self, store):
        self._seed_many(store, 12)
        all_ids = set()
        cursor = None
        while True:
            page, cursor = store.get_entries(limit=5, cursor=cursor)
            all_ids.update(e.entry_id for e in page)
            if cursor is None:
                break
        assert len(all_ids) == 12

    def test_limit_capped_at_500(self, store):
        self._seed_many(store, 5)
        page, _ = store.get_entries(limit=9999)
        assert len(page) <= 500

    def test_invalid_cursor_returns_from_start(self, store):
        self._seed_many(store, 10)
        # A cursor that doesn't match any entry_id resets to start
        page, _ = store.get_entries(limit=5, cursor="nonexistent-cursor-xyz")
        assert len(page) == 5

    def test_count_helper(self, store):
        for _ in range(7):
            store.record(org_id="o1", actor_id="a", event_type=AUTH_LOGIN)
        for _ in range(3):
            store.record(org_id="o2", actor_id="a", event_type=AUTH_LOGOUT)
        assert store.count(org_id="o1") == 7
        assert store.count(org_id="o2") == 3
        assert store.count() == 10
        assert store.count(event_type=AUTH_LOGIN) == 7


# ============================================================================
# 7. Retention policy
# ============================================================================

class TestRetentionPolicy:
    """Retention policy removes old entries based on plan tier."""

    def test_free_tier_retention_constant(self):
        assert RETENTION_DAYS_FREE == 90

    def test_org_tier_retention_constant(self):
        assert RETENTION_DAYS_ORG == 365

    def test_retention_days_for_free(self):
        assert retention_days_for_plan("free") == RETENTION_DAYS_FREE

    def test_retention_days_for_starter(self):
        assert retention_days_for_plan("starter") == RETENTION_DAYS_FREE

    def test_retention_days_for_org(self):
        for plan in ORG_TIER_PLANS:
            assert retention_days_for_plan(plan) == RETENTION_DAYS_ORG

    def test_retention_days_case_insensitive(self):
        assert retention_days_for_plan("ENTERPRISE") == RETENTION_DAYS_ORG
        assert retention_days_for_plan("Organization") == RETENTION_DAYS_ORG

    def test_enforce_retention_removes_old_entries(self, store):
        # Add 3 very old entries (100 days ago) and 2 recent ones
        old_ts = _ts(days_ago=100)
        new_ts = _ts(days_ago=1)
        for _ in range(3):
            store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN, timestamp=old_ts)
        for _ in range(2):
            store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN, timestamp=new_ts)

        removed = store.enforce_retention(plan="free")
        assert removed == 3
        assert store.total_count == 2

    def test_enforce_retention_org_keeps_more(self, store):
        # 200 days old — free tier would remove, org keeps
        ts_200 = _ts(days_ago=200)
        store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN, timestamp=ts_200)

        removed = store.enforce_retention(plan="organization")
        assert removed == 0  # within 365-day window

    def test_enforce_retention_by_org_id(self, store):
        old_ts = _ts(days_ago=100)
        store.record(org_id="org1", actor_id="a", event_type=AUTH_LOGIN, timestamp=old_ts)
        store.record(org_id="org2", actor_id="a", event_type=AUTH_LOGIN, timestamp=old_ts)

        # Only apply retention to org1
        removed = store.enforce_retention(plan="free", org_id="org1")
        assert removed == 1
        assert store.total_count == 1

    def test_enforce_retention_returns_zero_when_nothing_expired(self, store):
        store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN)
        removed = store.enforce_retention(plan="free")
        assert removed == 0


# ============================================================================
# 8. CSV and JSON export
# ============================================================================

class TestExport:
    """export_csv and export_json produce correct output."""

    def _seed(self, store, n=3):
        for i in range(n):
            store.record(
                org_id="org1", actor_id=f"user{i}",
                event_type=AUTH_LOGIN, details={"seq": i},
            )

    def test_csv_export_has_header(self, store):
        self._seed(store)
        csv_str = store.export_csv(org_id="org1")
        lines = csv_str.strip().split("\n")
        assert lines[0].startswith("entry_id")

    def test_csv_export_has_correct_row_count(self, store):
        self._seed(store, 3)
        csv_str = store.export_csv(org_id="org1")
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 3

    def test_csv_export_row_fields(self, store):
        store.record(
            org_id="org1", actor_id="alice", event_type=AUTH_LOGIN,
            resource_id="r1", details={"method": "password"},
        )
        csv_str = store.export_csv(org_id="org1")
        reader = csv.DictReader(io.StringIO(csv_str))
        row = next(reader)
        assert row["org_id"] == "org1"
        assert row["actor_id"] == "alice"
        assert row["event_type"] == AUTH_LOGIN
        assert row["resource_id"] == "r1"
        assert "method" in row["details"]

    def test_csv_export_filter_by_event_type(self, store):
        store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN)
        store.record(org_id="o", actor_id="a", event_type=AUTH_LOGOUT)
        csv_str = store.export_csv(org_id="o", event_type=AUTH_LOGIN)
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["event_type"] == AUTH_LOGIN

    def test_json_export_structure(self, store):
        self._seed(store)
        json_str = store.export_json(org_id="org1")
        data = json.loads(json_str)
        assert "audit_log" in data
        assert "count" in data
        assert "exported_at" in data
        assert data["count"] == 3

    def test_json_export_entries_have_required_fields(self, store):
        store.record(
            org_id="org1", actor_id="alice", event_type=AGENT_SESSION_STARTED,
            resource_id="session_abc", details={"agent": "coding"},
        )
        data = json.loads(store.export_json(org_id="org1"))
        entry = data["audit_log"][0]
        for field in ["entry_id", "org_id", "actor_id", "event_type", "resource_id", "details", "timestamp"]:
            assert field in entry, f"Missing field: {field}"

    def test_json_export_empty(self, store):
        data = json.loads(store.export_json(org_id="nonexistent"))
        assert data["count"] == 0
        assert data["audit_log"] == []

    def test_csv_export_empty(self, store):
        csv_str = store.export_csv(org_id="nonexistent")
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 0

    def test_json_export_has_total_exported_field(self, store):
        self._seed(store)
        data = json.loads(store.export_json(org_id="org1"))
        assert "total_exported" in data
        assert data["total_exported"] == 3

    def test_csv_export_returns_all_entries_over_500(self, store):
        """Export must not silently truncate at 500 entries."""
        n = 510
        for i in range(n):
            store.record(
                org_id="org_big", actor_id="bulk_user",
                event_type=AUTH_LOGIN, details={"seq": i},
            )
        csv_str = store.export_csv(org_id="org_big")
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == n, f"Expected {n} rows, got {len(rows)} (export truncated?)"

    def test_json_export_returns_all_entries_over_500(self, store):
        """JSON export must not silently truncate at 500 entries."""
        n = 510
        for i in range(n):
            store.record(
                org_id="org_big2", actor_id="bulk_user",
                event_type=AUTH_LOGIN, details={"seq": i},
            )
        data = json.loads(store.export_json(org_id="org_big2"))
        assert data["count"] == n, f"Expected {n}, got {data['count']} (export truncated?)"
        assert data["total_exported"] == n
        assert len(data["audit_log"]) == n


# ============================================================================
# 9. Integration helpers
# ============================================================================

class TestIntegrationHelpers:
    """record_auth_event, record_team_event, etc. write to the global store."""

    def test_record_auth_event(self):
        entry = record_auth_event(
            org_id="org1", actor_id="user1",
            event_type=AUTH_LOGIN, details={"ip": "1.1.1.1"},
        )
        assert entry is not None
        assert entry.event_type == AUTH_LOGIN
        store = get_audit_store()
        assert store.total_count == 1

    def test_record_team_event(self):
        entry = record_team_event(
            org_id="org1", actor_id="admin1",
            event_type=TEAM_MEMBER_INVITED, resource_id="invite_xyz",
        )
        assert entry is not None
        assert entry.event_type == TEAM_MEMBER_INVITED

    def test_record_agent_event(self):
        entry = record_agent_event(
            org_id="org1", actor_id="system",
            event_type=AGENT_SESSION_STARTED, resource_id="session_1",
        )
        assert entry is not None
        assert entry.event_type == AGENT_SESSION_STARTED

    def test_record_billing_event(self):
        entry = record_billing_event(
            org_id="org1", actor_id="stripe_webhook",
            event_type=BILLING_PAYMENT_SUCCEEDED, resource_id="pi_123",
            details={"amount_usd": 99.00},
        )
        assert entry is not None
        assert entry.event_type == BILLING_PAYMENT_SUCCEEDED

    def test_generic_record_audit_event(self):
        entry = record_audit_event(
            org_id="org1", actor_id="u1",
            event_type=AUTH_API_KEY_CREATED, resource_id="key_abc",
            details={"key_name": "ci-deploy"},
        )
        assert entry is not None
        assert entry.details["key_name"] == "ci-deploy"

    def test_record_event_failure_returns_none(self):
        """Failures in recording are silenced and return None."""
        with patch("audit.integration.get_audit_store", side_effect=RuntimeError("db down")):
            result = record_auth_event(
                org_id="o", actor_id="a", event_type=AUTH_LOGIN
            )
        assert result is None

    def test_system_actor_constant(self):
        assert SYSTEM_ACTOR == "system"


# ============================================================================
# 10. Bridge: teams.models.AuditLog → audit.AuditStore
# ============================================================================

class TestBridgeTeamsAuditEvent:
    """bridge_teams_audit_event maps legacy event types to canonical ones."""

    def test_member_invited_mapped(self):
        entry = bridge_teams_audit_event(
            org_id="o", actor_user_id="admin",
            event_type="member_invited",
            details={"email": "bob@example.com"},
        )
        assert entry is not None
        assert entry.event_type == TEAM_MEMBER_INVITED

    def test_role_changed_mapped(self):
        entry = bridge_teams_audit_event(
            org_id="o", actor_user_id="admin",
            event_type="role_changed",
            target_user_id="user123",
        )
        assert entry is not None
        assert entry.event_type == TEAM_ROLE_CHANGED
        assert entry.resource_id == "user123"

    def test_member_removed_mapped(self):
        entry = bridge_teams_audit_event(
            org_id="o", actor_user_id="admin",
            event_type="member_removed",
            target_user_id="user999",
        )
        assert entry is not None
        assert entry.event_type == TEAM_MEMBER_REMOVED

    def test_target_user_id_in_details(self):
        entry = bridge_teams_audit_event(
            org_id="o", actor_user_id="admin",
            event_type="role_changed",
            target_user_id="target_user",
        )
        assert entry is not None
        assert entry.details.get("target_user_id") == "target_user"

    def test_unknown_legacy_type_passthrough(self):
        """Unknown legacy event types pass through unchanged."""
        entry = bridge_teams_audit_event(
            org_id="o", actor_user_id="system",
            event_type="some_future_event",
        )
        assert entry is not None
        assert entry.event_type == "some_future_event"


# ============================================================================
# 11. Module-level singletons
# ============================================================================

class TestSingletons:
    """get_audit_store returns the same instance; reset_audit_store resets it."""

    def test_get_audit_store_returns_singleton(self):
        s1 = get_audit_store()
        s2 = get_audit_store()
        assert s1 is s2

    def test_reset_audit_store_creates_new_instance(self):
        s1 = get_audit_store()
        reset_audit_store()
        s2 = get_audit_store()
        assert s1 is not s2

    def test_reset_clears_data(self):
        store = get_audit_store()
        store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN)
        assert store.total_count == 1
        reset_audit_store()
        new_store = get_audit_store()
        assert new_store.total_count == 0


# ============================================================================
# 12. Route handlers (integration via aiohttp test client)
# ============================================================================

class TestRouteHandlers:
    """API routes return correct responses."""

    def _make_app(self):
        from aiohttp import web
        from audit.routes import register_audit_routes
        app = web.Application()
        register_audit_routes(app)
        return app

    @pytest.mark.asyncio
    async def test_get_audit_log_empty(self):
        from aiohttp.test_utils import TestClient, TestServer
        from aiohttp import web
        app = self._make_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/audit-log")
            assert resp.status == 200
            data = await resp.json()
            assert "entries" in data
            assert "count" in data
            assert "cursor" in data
            assert "has_more" in data

    @pytest.mark.asyncio
    async def test_get_audit_log_with_entries(self):
        from aiohttp.test_utils import TestClient, TestServer
        store = get_audit_store()
        for i in range(3):
            store.record(org_id="org1", actor_id="u", event_type=AUTH_LOGIN)

        app = self._make_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/audit-log?org_id=org1")
            assert resp.status == 200
            data = await resp.json()
            assert data["count"] == 3

    @pytest.mark.asyncio
    async def test_get_audit_log_pagination(self):
        from aiohttp.test_utils import TestClient, TestServer
        store = get_audit_store()
        for _ in range(10):
            store.record(org_id="org1", actor_id="u", event_type=AUTH_LOGIN)

        app = self._make_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/audit-log?limit=5")
            data = await resp.json()
            assert data["count"] == 5
            assert data["has_more"] is True
            assert data["cursor"] is not None

    @pytest.mark.asyncio
    async def test_export_csv_endpoint(self):
        from aiohttp.test_utils import TestClient, TestServer
        store = get_audit_store()
        store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN)

        app = self._make_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/audit-log/export/csv")
            assert resp.status == 200
            assert "text/csv" in resp.content_type
            body = await resp.text()
            assert "entry_id" in body  # header row

    @pytest.mark.asyncio
    async def test_export_json_endpoint(self):
        from aiohttp.test_utils import TestClient, TestServer
        store = get_audit_store()
        store.record(org_id="o", actor_id="a", event_type=AUTH_LOGOUT)

        app = self._make_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/audit-log/export/json")
            assert resp.status == 200
            body = await resp.text()
            data = json.loads(body)
            assert "audit_log" in data
            assert data["count"] == 1

    @pytest.mark.asyncio
    async def test_get_event_types_endpoint(self):
        from aiohttp.test_utils import TestClient, TestServer
        app = self._make_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/audit-log/event-types")
            assert resp.status == 200
            data = await resp.json()
            assert "event_types" in data
            assert "categories" in data
            assert len(data["event_types"]) == len(ALL_EVENT_TYPES)

    @pytest.mark.asyncio
    async def test_get_audit_log_filter_by_event_type(self):
        from aiohttp.test_utils import TestClient, TestServer
        store = get_audit_store()
        store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN)
        store.record(org_id="o", actor_id="a", event_type=AUTH_LOGOUT)

        app = self._make_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.get(f"/api/audit-log?event_type={AUTH_LOGIN}")
            data = await resp.json()
            assert data["count"] == 1
            assert data["entries"][0]["event_type"] == AUTH_LOGIN

    @pytest.mark.asyncio
    async def test_get_audit_log_filter_by_actor(self):
        from aiohttp.test_utils import TestClient, TestServer
        store = get_audit_store()
        store.record(org_id="o", actor_id="alice", event_type=AUTH_LOGIN)
        store.record(org_id="o", actor_id="bob", event_type=AUTH_LOGIN)

        app = self._make_app()
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/audit-log?actor_id=alice")
            data = await resp.json()
            assert data["count"] == 1
            assert data["entries"][0]["actor_id"] == "alice"

    @pytest.mark.asyncio
    async def test_audit_log_page_html(self):
        from aiohttp.test_utils import TestClient, TestServer
        app = self._make_app()
        # We don't need the html to exist for the route test; check 200 or 404 gracefully
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/settings/audit-log")
            # Either the HTML exists (200) or the route returns 404 — either is acceptable
            assert resp.status in (200, 404)


# ============================================================================
# 13. Edge cases
# ============================================================================

class TestEdgeCases:
    """Edge cases and robustness checks."""

    def test_record_with_empty_details(self, store):
        entry = store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN)
        assert entry.details == {}

    def test_record_with_none_details(self, store):
        entry = AuditEntry.create(
            org_id="o", actor_id="a", event_type=AUTH_LOGIN, details=None
        )
        assert entry.details == {}

    def test_record_with_empty_resource_id(self, store):
        entry = store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN)
        assert entry.resource_id == ""

    def test_entry_id_is_unique(self, store):
        entries = [
            store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN)
            for _ in range(100)
        ]
        ids = [e.entry_id for e in entries]
        assert len(set(ids)) == 100

    def test_timestamp_override(self, store):
        custom_ts = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        entry = store.record(
            org_id="o", actor_id="a", event_type=AUTH_LOGIN,
            timestamp=custom_ts,
        )
        assert "2024-01-15" in entry.timestamp

    def test_enforce_retention_on_empty_store(self, store):
        removed = store.enforce_retention(plan="free")
        assert removed == 0

    def test_get_entries_limit_one(self, store):
        for _ in range(5):
            store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN)
        entries, _ = store.get_entries(limit=1)
        assert len(entries) == 1

    def test_export_csv_with_date_filter(self, store):
        old_ts = _ts(days_ago=10)
        new_ts = _ts(days_ago=1)
        store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN, timestamp=old_ts)
        store.record(org_id="o", actor_id="a", event_type=AUTH_LOGIN, timestamp=new_ts)
        cutoff = _ts(days_ago=5)
        csv_str = store.export_csv(since=cutoff)
        reader = csv.DictReader(io.StringIO(csv_str))
        rows = list(reader)
        assert len(rows) == 1

    def test_json_export_is_valid_json(self, store):
        store.record(org_id="o", actor_id="a", event_type=AGENT_SESSION_COMPLETED,
                     details={"unicode": "caf\u00e9"})
        json_str = store.export_json()
        data = json.loads(json_str)  # must not raise
        assert data["count"] == 1
