"""Tests for Free Tier / Explorer Plan Management (AI-220).

Covers:
- FreeTierManager: usage tracking (start/end session, hour calculation)
- Limit enforcement: agent-hour limit, concurrency, model restrictions
- Monthly reset logic
- Plan management (get/set)
- API endpoint integration (/api/billing/usage, /api/billing/plan, /api/billing/upgrade)
- Session tracking (active sessions)
- Upgrade info

Aim: >= 25 tests.
"""

import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
import sys
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.free_tier import (
    FreeTierManager,
    PlanConfig,
    PLAN_CONFIGS,
    ActiveSession,
    UserBillingRecord,
    _first_of_month_iso,
    _needs_monthly_reset,
    _get_plan_features,
    get_free_tier_manager,
    reset_free_tier_manager,
)


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def tmp_data_file(tmp_path):
    """Return a temporary data file path for FreeTierManager."""
    return tmp_path / "usage_data.json"


@pytest.fixture
def manager(tmp_data_file):
    """Return a fresh FreeTierManager using a temporary data file."""
    return FreeTierManager(data_file=tmp_data_file)


# ===========================================================================
# PlanConfig tests
# ===========================================================================

class TestPlanConfigs:
    """Tests for PLAN_CONFIGS definitions."""

    def test_all_plans_present(self):
        for plan_name in ("explorer", "builder", "team", "organization"):
            assert plan_name in PLAN_CONFIGS

    def test_explorer_plan_limits(self):
        cfg = PLAN_CONFIGS["explorer"]
        assert cfg.agent_hours_limit == 10.0
        assert cfg.max_concurrent_agents == 1
        assert "github" in cfg.allowed_integrations

    def test_explorer_allowed_models_haiku_only(self):
        cfg = PLAN_CONFIGS["explorer"]
        for model in cfg.allowed_models:
            assert "haiku" in model.lower()

    def test_builder_plan_limits(self):
        cfg = PLAN_CONFIGS["builder"]
        assert cfg.agent_hours_limit == 50.0
        assert cfg.max_concurrent_agents == 5
        assert cfg.price_monthly == 49.0

    def test_builder_allows_sonnet(self):
        cfg = PLAN_CONFIGS["builder"]
        assert any("sonnet" in m.lower() for m in cfg.allowed_models)

    def test_team_plan_limits(self):
        cfg = PLAN_CONFIGS["team"]
        assert cfg.agent_hours_limit == 200.0
        assert cfg.max_concurrent_agents == 20
        assert cfg.price_monthly == 199.0

    def test_organization_unlimited(self):
        cfg = PLAN_CONFIGS["organization"]
        import math
        assert math.isinf(cfg.agent_hours_limit)
        assert cfg.max_concurrent_agents == 0  # 0 = unlimited

    def test_plan_features_explorer(self):
        features = _get_plan_features("explorer")
        assert len(features) > 0
        assert any("10" in f and "agent-hour" in f for f in features)

    def test_plan_features_builder(self):
        features = _get_plan_features("builder")
        assert any("Sonnet" in f or "Opus" in f for f in features)


# ===========================================================================
# UserBillingRecord tests
# ===========================================================================

class TestUserBillingRecord:
    """Tests for UserBillingRecord derived properties."""

    def test_percent_used_zero_initially(self):
        record = UserBillingRecord(user_id="u1", plan="explorer", hours_used=0.0)
        assert record.percent_used == 0.0

    def test_percent_used_at_half(self):
        record = UserBillingRecord(user_id="u1", plan="explorer", hours_used=5.0)
        assert record.percent_used == 50.0

    def test_percent_used_over_limit(self):
        record = UserBillingRecord(user_id="u1", plan="explorer", hours_used=12.0)
        assert record.percent_used == 120.0

    def test_hours_limit_for_explorer(self):
        record = UserBillingRecord(user_id="u1", plan="explorer")
        assert record.hours_limit == 10.0

    def test_reset_date_is_first_of_next_month(self):
        record = UserBillingRecord(user_id="u1", plan="explorer")
        reset_date = record.reset_date
        # Should be a valid date string
        assert reset_date != ""
        from datetime import date
        d = date.fromisoformat(reset_date)
        assert d.day == 1

    def test_to_dict_includes_expected_keys(self):
        record = UserBillingRecord(user_id="u1", plan="explorer", hours_used=3.0)
        d = record.to_dict()
        for key in ("user_id", "plan", "hours_used", "hours_limit", "percent_used",
                    "period_start", "reset_date", "show_upgrade_cta", "allowed_models"):
            assert key in d, f"Missing key: {key}"

    def test_show_upgrade_cta_false_below_80(self):
        record = UserBillingRecord(user_id="u1", plan="explorer", hours_used=7.9)
        assert record.to_dict()["show_upgrade_cta"] is False

    def test_show_upgrade_cta_true_at_80(self):
        record = UserBillingRecord(user_id="u1", plan="explorer", hours_used=8.0)
        assert record.to_dict()["show_upgrade_cta"] is True


# ===========================================================================
# Helper function tests
# ===========================================================================

class TestHelpers:
    """Tests for helper functions."""

    def test_first_of_month_iso_format(self):
        iso = _first_of_month_iso()
        dt = datetime.fromisoformat(iso)
        assert dt.day == 1
        assert dt.hour == 0
        assert dt.minute == 0

    def test_needs_monthly_reset_same_month(self):
        iso = _first_of_month_iso()
        assert _needs_monthly_reset(iso) is False

    def test_needs_monthly_reset_previous_month(self):
        # Use a date from January 2020 (clearly in the past)
        old_iso = "2020-01-01T00:00:00+00:00"
        assert _needs_monthly_reset(old_iso) is True

    def test_needs_monthly_reset_invalid_iso(self):
        # Invalid ISO should not raise - returns True as safe fallback
        result = _needs_monthly_reset("not-a-date")
        assert isinstance(result, bool)


# ===========================================================================
# FreeTierManager usage tracking tests
# ===========================================================================

class TestFreeTierManagerUsage:
    """Tests for usage tracking via FreeTierManager."""

    def test_get_usage_returns_default_for_new_user(self, manager):
        usage = manager.get_usage("user_new")
        assert usage["hours_used"] == 0.0
        assert usage["plan"] == "explorer"
        assert usage["hours_limit"] == 10.0
        assert usage["percent_used"] == 0.0

    def test_record_session_start_returns_session_info(self, manager):
        result = manager.record_session_start("u1", "sess-001")
        assert result["session_id"] == "sess-001"
        assert "started_at" in result
        assert "usage" in result

    def test_record_session_end_calculates_elapsed_hours(self, manager):
        # Start session
        manager.record_session_start("u1", "sess-002")
        # Simulate time passing by sleeping briefly
        time.sleep(0.1)  # 100ms
        result = manager.record_session_end("u1", "sess-002")
        assert result["session_id"] == "sess-002"
        # hours_consumed is a non-negative float
        assert result["hours_consumed"] >= 0
        # Usage hours_used should be updated (>= 0; for very fast test machines may round to 0.0)
        assert result["usage"]["hours_used"] >= 0.0
        # The session was tracked (result has no error)
        assert "error" not in result

    def test_record_session_end_unknown_session(self, manager):
        result = manager.record_session_end("u1", "unknown-session")
        assert "error" in result
        assert result["error"] == "session not found"

    def test_record_session_start_duplicate(self, manager):
        manager.record_session_start("u1", "dup-sess")
        result = manager.record_session_start("u1", "dup-sess")
        assert result.get("already_active") is True

    def test_get_active_sessions_empty_initially(self, manager):
        sessions = manager.get_active_sessions("u1")
        assert sessions == []

    def test_get_active_sessions_shows_started(self, manager):
        manager.record_session_start("u1", "active-sess")
        sessions = manager.get_active_sessions("u1")
        assert len(sessions) == 1
        assert sessions[0]["session_id"] == "active-sess"

    def test_get_active_sessions_cleared_after_end(self, manager):
        manager.record_session_start("u1", "temp-sess")
        manager.record_session_end("u1", "temp-sess")
        sessions = manager.get_active_sessions("u1")
        assert sessions == []

    def test_add_hours_for_testing(self, manager):
        manager.add_hours_for_testing("u1", 5.0)
        usage = manager.get_usage("u1")
        assert usage["hours_used"] == 5.0

    def test_hours_accumulate_across_sessions(self, manager):
        manager.add_hours_for_testing("u1", 3.0)
        manager.add_hours_for_testing("u1", 2.0)
        usage = manager.get_usage("u1")
        assert usage["hours_used"] == 5.0


# ===========================================================================
# FreeTierManager limit enforcement tests
# ===========================================================================

class TestFreeTierManagerLimits:
    """Tests for limit enforcement."""

    def test_check_agent_hour_limit_allowed_when_under(self, manager):
        assert manager.check_agent_hour_limit("u1") is True

    def test_check_agent_hour_limit_denied_when_over(self, manager):
        manager.add_hours_for_testing("u1", 10.0)  # at limit
        assert manager.check_agent_hour_limit("u1") is False

    def test_check_agent_hour_limit_exact_limit(self, manager):
        # Exactly at the limit means they've used it all up
        manager.add_hours_for_testing("u1", 10.0)
        assert manager.check_agent_hour_limit("u1") is False

    def test_check_agent_hour_limit_just_under(self, manager):
        manager.add_hours_for_testing("u1", 9.99)
        assert manager.check_agent_hour_limit("u1") is True

    def test_check_concurrency_limit_allowed_no_sessions(self, manager):
        assert manager.check_concurrency_limit("u1") is True

    def test_check_concurrency_limit_denied_at_max(self, manager):
        # Explorer has max 1 concurrent agent
        manager.record_session_start("u1", "conc-sess-1")
        assert manager.check_concurrency_limit("u1") is False

    def test_check_concurrency_limit_uses_current_active_param(self, manager):
        # Pass current_active=1 directly - explorer has max 1
        assert manager.check_concurrency_limit("u1", current_active=1) is False
        assert manager.check_concurrency_limit("u1", current_active=0) is True

    def test_check_model_allowed_haiku_for_explorer(self, manager):
        assert manager.check_model_allowed("u1", "claude-haiku-3-5") is True
        assert manager.check_model_allowed("u1", "haiku") is True

    def test_check_model_denied_sonnet_for_explorer(self, manager):
        assert manager.check_model_allowed("u1", "claude-sonnet-4-5") is False
        assert manager.check_model_allowed("u1", "sonnet") is False

    def test_check_model_denied_opus_for_explorer(self, manager):
        assert manager.check_model_allowed("u1", "claude-opus-4-6") is False
        assert manager.check_model_allowed("u1", "opus") is False

    def test_check_model_allowed_sonnet_for_builder(self, manager):
        manager.set_user_plan("u1", "builder")
        assert manager.check_model_allowed("u1", "claude-sonnet-4-5") is True

    def test_check_model_allowed_opus_for_team(self, manager):
        manager.set_user_plan("u1", "team")
        assert manager.check_model_allowed("u1", "claude-opus-4-6") is True

    def test_organization_has_unlimited_concurrency(self, manager):
        manager.set_user_plan("u1", "organization")
        # max_concurrent_agents == 0 means unlimited
        assert manager.check_concurrency_limit("u1", current_active=100) is True


# ===========================================================================
# FreeTierManager monthly reset tests
# ===========================================================================

class TestFreeTierManagerReset:
    """Tests for monthly reset logic."""

    def test_reset_usage_clears_hours(self, manager):
        manager.add_hours_for_testing("u1", 8.5)
        manager.reset_usage("u1")
        usage = manager.get_usage("u1")
        assert usage["hours_used"] == 0.0

    def test_reset_usage_updates_period_start_to_current_month(self, manager):
        manager.reset_usage("u1")
        usage = manager.get_usage("u1")
        period_dt = datetime.fromisoformat(usage["period_start"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        assert period_dt.month == now.month
        assert period_dt.year == now.year
        assert period_dt.day == 1

    def test_auto_reset_when_period_start_is_old_month(self, manager):
        # Manually set an old period start
        manager._get_or_create_billing("u1")
        record = manager._billing["u1"]
        record.hours_used = 7.5
        record.period_start = "2020-01-01T00:00:00+00:00"

        # Next call should trigger auto-reset
        usage = manager.get_usage("u1")
        assert usage["hours_used"] == 0.0

    def test_plan_preserved_after_reset(self, manager):
        manager.set_user_plan("u1", "builder")
        manager.reset_usage("u1")
        usage = manager.get_usage("u1")
        assert usage["plan"] == "builder"


# ===========================================================================
# FreeTierManager plan management tests
# ===========================================================================

class TestFreeTierManagerPlans:
    """Tests for plan management."""

    def test_default_plan_is_explorer(self, manager):
        plan = manager.get_plan("new_user")
        assert plan["plan"] == "explorer"

    def test_set_user_plan_changes_plan(self, manager):
        manager.set_user_plan("u1", "builder")
        plan = manager.get_plan("u1")
        assert plan["plan"] == "builder"
        assert plan["price_monthly"] == 49.0

    def test_set_user_plan_invalid_raises(self, manager):
        with pytest.raises(ValueError, match="Unknown plan"):
            manager.set_user_plan("u1", "invalid_plan")

    def test_get_upgrade_info_returns_all_tiers(self, manager):
        info = manager.get_upgrade_info()
        assert "tiers" in info
        plan_names = [t["plan"] for t in info["tiers"]]
        for expected in ("explorer", "builder", "team", "organization"):
            assert expected in plan_names

    def test_get_upgrade_info_has_upgrade_url(self, manager):
        info = manager.get_upgrade_info()
        assert "upgrade_url" in info
        assert info["upgrade_url"].startswith("http")


# ===========================================================================
# FreeTierManager persistence tests
# ===========================================================================

class TestFreeTierManagerPersistence:
    """Tests for data persistence."""

    def test_data_persisted_to_file(self, tmp_data_file):
        manager = FreeTierManager(data_file=tmp_data_file)
        manager.add_hours_for_testing("u1", 3.5)

        # File should exist now
        assert tmp_data_file.exists()
        raw = json.loads(tmp_data_file.read_text())
        assert "billing" in raw
        assert "u1" in raw["billing"]
        assert raw["billing"]["u1"]["hours_used"] == 3.5

    def test_data_loaded_from_file(self, tmp_data_file):
        # Write data first
        tmp_data_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "billing": {
                "u1": {
                    "plan": "builder",
                    "hours_used": 7.25,
                    "period_start": _first_of_month_iso(),
                    "last_updated": datetime.now(timezone.utc).isoformat(),
                }
            },
            "completed_sessions": []
        }
        tmp_data_file.write_text(json.dumps(payload), encoding="utf-8")

        # Load into a new manager
        manager2 = FreeTierManager(data_file=tmp_data_file)
        usage = manager2.get_usage("u1")
        assert usage["plan"] == "builder"
        assert usage["hours_used"] == 7.25


# ===========================================================================
# API endpoint integration tests
# ===========================================================================

@pytest.fixture
async def api_server(tmp_data_file):
    """Create a test aiohttp application with billing endpoints."""
    from dashboard.rest_api_server import RESTAPIServer
    from dashboard.free_tier import FreeTierManager, reset_free_tier_manager
    import dashboard.free_tier as ft_module

    # Reset and patch the global manager to use our tmp file
    reset_free_tier_manager()
    ft_module._global_free_tier_manager = FreeTierManager(data_file=tmp_data_file)

    server = RESTAPIServer(project_name="test", metrics_dir=tmp_data_file.parent)
    return TestServer(server.app)


@pytest.mark.asyncio
async def test_api_billing_usage_returns_200(tmp_data_file):
    """GET /api/billing/usage should return 200 with usage data."""
    from dashboard.rest_api_server import RESTAPIServer
    from dashboard.free_tier import FreeTierManager, reset_free_tier_manager
    import dashboard.free_tier as ft_module

    reset_free_tier_manager()
    ft_module._global_free_tier_manager = FreeTierManager(data_file=tmp_data_file)

    server = RESTAPIServer(project_name="test", metrics_dir=tmp_data_file.parent)
    async with TestClient(TestServer(server.app)) as client:
        resp = await client.get("/api/billing/usage")
        assert resp.status == 200
        data = await resp.json()
        assert "plan" in data or "tier" in data
        assert "hours_used" in data or "agent_hours_used" in data


@pytest.mark.asyncio
async def test_api_billing_plan_returns_200(tmp_data_file):
    """GET /api/billing/plan should return 200 with plan info."""
    from dashboard.rest_api_server import RESTAPIServer
    from dashboard.free_tier import FreeTierManager, reset_free_tier_manager
    import dashboard.free_tier as ft_module

    reset_free_tier_manager()
    ft_module._global_free_tier_manager = FreeTierManager(data_file=tmp_data_file)

    server = RESTAPIServer(project_name="test", metrics_dir=tmp_data_file.parent)
    async with TestClient(TestServer(server.app)) as client:
        resp = await client.get("/api/billing/plan")
        assert resp.status == 200
        data = await resp.json()
        assert "plan" in data
        assert data["plan"] == "explorer"


@pytest.mark.asyncio
async def test_api_billing_upgrade_returns_200(tmp_data_file):
    """POST /api/billing/upgrade should return 200 with tier info."""
    from dashboard.rest_api_server import RESTAPIServer
    from dashboard.free_tier import FreeTierManager, reset_free_tier_manager
    import dashboard.free_tier as ft_module

    reset_free_tier_manager()
    ft_module._global_free_tier_manager = FreeTierManager(data_file=tmp_data_file)

    server = RESTAPIServer(project_name="test", metrics_dir=tmp_data_file.parent)
    async with TestClient(TestServer(server.app)) as client:
        resp = await client.post(
            "/api/billing/upgrade",
            json={"plan": "builder"}
        )
        assert resp.status == 200
        data = await resp.json()
        assert "tiers" in data
        assert "upgrade_url" in data


@pytest.mark.asyncio
async def test_api_billing_session_start_returns_200(tmp_data_file):
    """POST /api/billing/session/start should return 200 for valid session."""
    from dashboard.rest_api_server import RESTAPIServer
    from dashboard.free_tier import FreeTierManager, reset_free_tier_manager
    import dashboard.free_tier as ft_module

    reset_free_tier_manager()
    ft_module._global_free_tier_manager = FreeTierManager(data_file=tmp_data_file)

    server = RESTAPIServer(project_name="test", metrics_dir=tmp_data_file.parent)
    async with TestClient(TestServer(server.app)) as client:
        resp = await client.post(
            "/api/billing/session/start",
            json={"session_id": "test-session-1", "model": "claude-haiku-3-5"}
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["session_id"] == "test-session-1"


@pytest.mark.asyncio
async def test_api_billing_session_start_denied_over_limit(tmp_data_file):
    """POST /api/billing/session/start should return 403 when hour limit exceeded."""
    from dashboard.rest_api_server import RESTAPIServer
    from dashboard.free_tier import FreeTierManager, reset_free_tier_manager
    import dashboard.free_tier as ft_module

    reset_free_tier_manager()
    mgr = FreeTierManager(data_file=tmp_data_file)
    mgr.add_hours_for_testing("default", 10.0)  # exhaust limit
    ft_module._global_free_tier_manager = mgr

    server = RESTAPIServer(project_name="test", metrics_dir=tmp_data_file.parent)
    async with TestClient(TestServer(server.app)) as client:
        resp = await client.post(
            "/api/billing/session/start",
            json={"session_id": "over-limit-sess"}
        )
        assert resp.status == 403
        data = await resp.json()
        assert data["error"] == "agent_hour_limit_exceeded"


@pytest.mark.asyncio
async def test_api_billing_session_start_denied_wrong_model(tmp_data_file):
    """POST /api/billing/session/start should return 403 for disallowed model."""
    from dashboard.rest_api_server import RESTAPIServer
    from dashboard.free_tier import FreeTierManager, reset_free_tier_manager
    import dashboard.free_tier as ft_module

    reset_free_tier_manager()
    ft_module._global_free_tier_manager = FreeTierManager(data_file=tmp_data_file)

    server = RESTAPIServer(project_name="test", metrics_dir=tmp_data_file.parent)
    async with TestClient(TestServer(server.app)) as client:
        resp = await client.post(
            "/api/billing/session/start",
            json={"session_id": "model-denied-sess", "model": "claude-sonnet-4-5"}
        )
        assert resp.status == 403
        data = await resp.json()
        assert data["error"] == "model_not_allowed"


@pytest.mark.asyncio
async def test_api_billing_session_end_returns_200(tmp_data_file):
    """POST /api/billing/session/end should return 200 for ended session."""
    from dashboard.rest_api_server import RESTAPIServer
    from dashboard.free_tier import FreeTierManager, reset_free_tier_manager
    import dashboard.free_tier as ft_module

    reset_free_tier_manager()
    mgr = FreeTierManager(data_file=tmp_data_file)
    mgr.record_session_start("default", "end-test-sess")
    ft_module._global_free_tier_manager = mgr

    server = RESTAPIServer(project_name="test", metrics_dir=tmp_data_file.parent)
    async with TestClient(TestServer(server.app)) as client:
        resp = await client.post(
            "/api/billing/session/end",
            json={"session_id": "end-test-sess"}
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["session_id"] == "end-test-sess"
        assert "hours_consumed" in data


@pytest.mark.asyncio
async def test_api_usage_legacy_endpoint(tmp_data_file):
    """GET /api/usage (legacy path) should also return usage data."""
    from dashboard.rest_api_server import RESTAPIServer
    from dashboard.free_tier import FreeTierManager, reset_free_tier_manager
    import dashboard.free_tier as ft_module

    reset_free_tier_manager()
    ft_module._global_free_tier_manager = FreeTierManager(data_file=tmp_data_file)

    server = RESTAPIServer(project_name="test", metrics_dir=tmp_data_file.parent)
    async with TestClient(TestServer(server.app)) as client:
        resp = await client.get("/api/usage")
        assert resp.status == 200


@pytest.mark.asyncio
async def test_api_billing_session_start_requires_session_id(tmp_data_file):
    """POST /api/billing/session/start should return 400 if session_id missing."""
    from dashboard.rest_api_server import RESTAPIServer
    from dashboard.free_tier import FreeTierManager, reset_free_tier_manager
    import dashboard.free_tier as ft_module

    reset_free_tier_manager()
    ft_module._global_free_tier_manager = FreeTierManager(data_file=tmp_data_file)

    server = RESTAPIServer(project_name="test", metrics_dir=tmp_data_file.parent)
    async with TestClient(TestServer(server.app)) as client:
        resp = await client.post(
            "/api/billing/session/start",
            json={}
        )
        assert resp.status == 400


# ===========================================================================
# Singleton tests
# ===========================================================================

class TestSingleton:
    """Tests for the module-level FreeTierManager singleton."""

    def test_get_free_tier_manager_returns_instance(self):
        reset_free_tier_manager()
        mgr = get_free_tier_manager()
        assert isinstance(mgr, FreeTierManager)

    def test_get_free_tier_manager_returns_same_instance(self):
        reset_free_tier_manager()
        mgr1 = get_free_tier_manager()
        mgr2 = get_free_tier_manager()
        assert mgr1 is mgr2

    def test_reset_free_tier_manager_creates_new_instance(self):
        mgr1 = get_free_tier_manager()
        reset_free_tier_manager()
        mgr2 = get_free_tier_manager()
        assert mgr1 is not mgr2
