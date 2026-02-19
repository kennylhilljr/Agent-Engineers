"""Tests for GA launch pricing tier activation and enforcement (AI-247).

Covers:
- billing.tiers: TierDefinition, TIERS registry, get_tier, is_upgrade, is_downgrade
- billing.feature_gates: model access, concurrent agent limits, feature flags, require_tier
- billing.pricing: Stripe price ID lookup, annual savings, config completeness
- billing.overage: overage calculation, trial status, proration
- billing.routes: route handler logic (no aiohttp server required - tested via mocks)
"""

import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# =============================================================================
# billing.tiers
# =============================================================================

class TestTierDefinition:
    def test_all_five_tiers_registered(self):
        from billing.tiers import TIERS, TIER_ORDER
        assert set(TIERS.keys()) == {"explorer", "builder", "team", "organization", "fleet"}
        assert len(TIER_ORDER) == 5

    def test_explorer_is_free(self):
        from billing.tiers import get_tier
        t = get_tier("explorer")
        assert t.monthly_price_usd == 0.0
        assert t.annual_price_usd is None

    def test_builder_pricing(self):
        from billing.tiers import get_tier
        t = get_tier("builder")
        assert t.monthly_price_usd == 49.0
        assert t.annual_price_usd == 39.0

    def test_team_pricing(self):
        from billing.tiers import get_tier
        t = get_tier("team")
        assert t.monthly_price_usd == 199.0
        assert t.annual_price_usd == 149.0

    def test_organization_pricing(self):
        from billing.tiers import get_tier
        t = get_tier("organization")
        assert t.monthly_price_usd == 799.0
        assert t.annual_price_usd == 599.0

    def test_fleet_is_custom(self):
        from billing.tiers import get_tier
        t = get_tier("fleet")
        assert t.is_custom_pricing is True
        assert t.min_monthly_price == 5000.0

    def test_explorer_agent_hours(self):
        from billing.tiers import get_tier
        assert get_tier("explorer").agent_hours_per_month == 10

    def test_builder_agent_hours(self):
        from billing.tiers import get_tier
        assert get_tier("builder").agent_hours_per_month == 100

    def test_team_agent_hours(self):
        from billing.tiers import get_tier
        assert get_tier("team").agent_hours_per_month == 500

    def test_organization_agent_hours(self):
        from billing.tiers import get_tier
        assert get_tier("organization").agent_hours_per_month == 2000

    def test_fleet_unlimited_hours(self):
        from billing.tiers import get_tier
        assert get_tier("fleet").agent_hours_per_month is None

    def test_explorer_concurrent_agents(self):
        from billing.tiers import get_tier
        assert get_tier("explorer").concurrent_agents == 1

    def test_builder_concurrent_agents(self):
        from billing.tiers import get_tier
        assert get_tier("builder").concurrent_agents == 3

    def test_team_concurrent_agents(self):
        from billing.tiers import get_tier
        assert get_tier("team").concurrent_agents == 10

    def test_organization_concurrent_agents(self):
        from billing.tiers import get_tier
        assert get_tier("organization").concurrent_agents == 25

    def test_fleet_unlimited_concurrent(self):
        from billing.tiers import get_tier
        assert get_tier("fleet").concurrent_agents is None

    def test_explorer_haiku_only(self):
        from billing.tiers import get_tier, HAIKU_MODELS
        t = get_tier("explorer")
        for model in t.allowed_models:
            assert model in HAIKU_MODELS

    def test_builder_includes_sonnet(self):
        from billing.tiers import get_tier, SONNET_MODELS
        t = get_tier("builder")
        for m in SONNET_MODELS:
            assert m in t.allowed_models

    def test_fleet_allows_byo(self):
        from billing.tiers import get_tier
        assert "byo_model" in get_tier("fleet").allowed_models

    def test_get_tier_case_insensitive(self):
        from billing.tiers import get_tier
        assert get_tier("EXPLORER").tier_id == "explorer"
        assert get_tier("Builder").tier_id == "builder"

    def test_get_tier_unknown_raises(self):
        from billing.tiers import get_tier
        with pytest.raises(ValueError, match="Unknown tier"):
            get_tier("platinum")

    def test_trial_days_for_builder(self):
        from billing.tiers import get_tier
        assert get_tier("builder").trial_days == 14

    def test_trial_days_for_team(self):
        from billing.tiers import get_tier
        assert get_tier("team").trial_days == 14

    def test_trial_days_for_organization(self):
        from billing.tiers import get_tier
        assert get_tier("organization").trial_days == 14

    def test_no_trial_for_explorer(self):
        from billing.tiers import get_tier
        assert get_tier("explorer").trial_days == 0

    def test_no_trial_for_fleet(self):
        from billing.tiers import get_tier
        assert get_tier("fleet").trial_days == 0

    def test_is_upgrade_builder_to_team(self):
        from billing.tiers import is_upgrade
        assert is_upgrade("builder", "team") is True

    def test_is_upgrade_team_to_builder_false(self):
        from billing.tiers import is_upgrade
        assert is_upgrade("team", "builder") is False

    def test_is_downgrade_team_to_explorer(self):
        from billing.tiers import is_downgrade
        assert is_downgrade("team", "explorer") is True

    def test_is_downgrade_explorer_to_fleet_false(self):
        from billing.tiers import is_downgrade
        assert is_downgrade("explorer", "fleet") is False

    def test_same_tier_not_upgrade(self):
        from billing.tiers import is_upgrade
        assert is_upgrade("team", "team") is False

    def test_same_tier_not_downgrade(self):
        from billing.tiers import is_downgrade
        assert is_downgrade("team", "team") is False


# =============================================================================
# billing.feature_gates
# =============================================================================

class TestModelAccess:
    def test_haiku_allowed_on_explorer(self):
        from billing.feature_gates import is_model_allowed
        assert is_model_allowed("claude-haiku-3", "explorer") is True

    def test_sonnet_blocked_on_explorer(self):
        from billing.feature_gates import is_model_allowed
        assert is_model_allowed("claude-sonnet-3-5", "explorer") is False

    def test_sonnet_allowed_on_builder(self):
        from billing.feature_gates import is_model_allowed
        assert is_model_allowed("claude-sonnet-3-5", "builder") is True

    def test_gpt4o_blocked_on_builder(self):
        from billing.feature_gates import is_model_allowed
        assert is_model_allowed("gpt-4o", "builder") is False

    def test_gpt4o_allowed_on_team(self):
        from billing.feature_gates import is_model_allowed
        assert is_model_allowed("gpt-4o", "team") is True

    def test_all_models_on_fleet(self):
        from billing.feature_gates import is_model_allowed
        assert is_model_allowed("gpt-4o", "fleet") is True
        assert is_model_allowed("claude-opus-4", "fleet") is True

    def test_byo_model_on_fleet(self):
        from billing.feature_gates import is_model_allowed
        assert is_model_allowed("byo:my-custom-model", "fleet") is True

    def test_byo_model_blocked_on_team(self):
        from billing.feature_gates import is_model_allowed
        assert is_model_allowed("byo:custom", "team") is False

    def test_unknown_tier_returns_false(self):
        from billing.feature_gates import is_model_allowed
        assert is_model_allowed("claude-haiku-3", "unknown") is False

    def test_check_model_access_raises_on_denied(self):
        from billing.feature_gates import check_model_access, ModelAccessDeniedError
        with pytest.raises(ModelAccessDeniedError):
            check_model_access("gpt-4o", "explorer")

    def test_check_model_access_passes_on_allowed(self):
        from billing.feature_gates import check_model_access
        # Should not raise
        check_model_access("claude-haiku-3", "explorer")

    def test_model_access_denied_has_tier_info(self):
        from billing.feature_gates import check_model_access, ModelAccessDeniedError
        with pytest.raises(ModelAccessDeniedError) as exc_info:
            check_model_access("gpt-4o", "explorer")
        assert exc_info.value.current_tier == "explorer"


class TestConcurrentAgentLimits:
    def test_explorer_limit_enforced(self):
        from billing.feature_gates import check_concurrent_agent_limit, ConcurrentAgentLimitError
        with pytest.raises(ConcurrentAgentLimitError):
            check_concurrent_agent_limit(1, "explorer")

    def test_explorer_within_limit(self):
        from billing.feature_gates import check_concurrent_agent_limit
        # 0 active agents should be fine
        check_concurrent_agent_limit(0, "explorer")

    def test_builder_at_limit(self):
        from billing.feature_gates import check_concurrent_agent_limit, ConcurrentAgentLimitError
        with pytest.raises(ConcurrentAgentLimitError):
            check_concurrent_agent_limit(3, "builder")

    def test_builder_within_limit(self):
        from billing.feature_gates import check_concurrent_agent_limit
        check_concurrent_agent_limit(2, "builder")

    def test_fleet_unlimited(self):
        from billing.feature_gates import check_concurrent_agent_limit
        # Should never raise for fleet
        check_concurrent_agent_limit(10000, "fleet")

    def test_get_concurrent_limit_explorer(self):
        from billing.feature_gates import get_concurrent_agent_limit
        assert get_concurrent_agent_limit("explorer") == 1

    def test_get_concurrent_limit_fleet(self):
        from billing.feature_gates import get_concurrent_agent_limit
        assert get_concurrent_agent_limit("fleet") is None

    def test_concurrent_limit_error_has_tier_info(self):
        from billing.feature_gates import check_concurrent_agent_limit, ConcurrentAgentLimitError
        with pytest.raises(ConcurrentAgentLimitError) as exc_info:
            check_concurrent_agent_limit(1, "explorer")
        assert exc_info.value.current_tier == "explorer"


class TestFeatureFlags:
    def test_explorer_has_basic_dashboard(self):
        from billing.feature_gates import has_feature
        assert has_feature("basic_dashboard", "explorer") is True

    def test_explorer_lacks_audit_log(self):
        from billing.feature_gates import has_feature
        assert has_feature("audit_log", "explorer") is False

    def test_team_has_audit_log(self):
        from billing.feature_gates import has_feature
        assert has_feature("audit_log", "team") is True

    def test_organization_has_sso_saml(self):
        from billing.feature_gates import has_feature
        assert has_feature("sso_saml", "organization") is True

    def test_builder_lacks_sso(self):
        from billing.feature_gates import has_feature
        assert has_feature("sso_saml", "builder") is False

    def test_fleet_has_byo_model(self):
        from billing.feature_gates import has_feature
        assert has_feature("byo_model", "fleet") is True

    def test_require_feature_raises_when_missing(self):
        from billing.feature_gates import require_feature, FeatureNotAvailableError
        with pytest.raises(FeatureNotAvailableError):
            require_feature("sso_saml", "builder")

    def test_require_feature_passes_when_available(self):
        from billing.feature_gates import require_feature
        require_feature("basic_dashboard", "explorer")

    def test_feature_not_available_has_tier_info(self):
        from billing.feature_gates import require_feature, FeatureNotAvailableError
        with pytest.raises(FeatureNotAvailableError) as exc_info:
            require_feature("sso_saml", "builder")
        assert exc_info.value.current_tier == "builder"

    def test_unknown_tier_returns_false_for_feature(self):
        from billing.feature_gates import has_feature
        assert has_feature("basic_dashboard", "nonexistent") is False


class TestRequireTierDecorator:
    def test_decorator_allows_correct_tier(self):
        from billing.feature_gates import require_tier

        @require_tier("team")
        def my_func(data, user_tier):
            return "ok"

        assert my_func("data", user_tier="team") == "ok"
        assert my_func("data", user_tier="organization") == "ok"
        assert my_func("data", user_tier="fleet") == "ok"

    def test_decorator_blocks_lower_tier(self):
        from billing.feature_gates import require_tier, TierGateError

        @require_tier("team")
        def my_func(data, user_tier):
            return "ok"

        with pytest.raises(TierGateError):
            my_func("data", user_tier="builder")

    def test_decorator_blocks_explorer_on_builder_gate(self):
        from billing.feature_gates import require_tier, TierGateError

        @require_tier("builder")
        def my_func(user_tier):
            return "ok"

        with pytest.raises(TierGateError):
            my_func(user_tier="explorer")

    def test_decorator_no_tier_raises(self):
        from billing.feature_gates import require_tier, TierGateError

        @require_tier("team")
        def my_func():
            return "ok"

        with pytest.raises(TierGateError):
            my_func()


# =============================================================================
# billing.pricing
# =============================================================================

class TestPricingConfig:
    def test_all_tiers_have_config(self):
        from billing.pricing import TIER_PRICE_CONFIGS
        for tier in ["explorer", "builder", "team", "organization", "fleet"]:
            assert tier in TIER_PRICE_CONFIGS

    def test_explorer_has_no_price_id(self):
        from billing.pricing import TIER_PRICE_CONFIGS
        assert TIER_PRICE_CONFIGS["explorer"].monthly_price_id == ""

    def test_builder_monthly_price_id_present(self):
        from billing.pricing import TIER_PRICE_CONFIGS
        assert TIER_PRICE_CONFIGS["builder"].monthly_price_id != ""

    def test_get_stripe_price_id_monthly(self):
        from billing.pricing import get_stripe_price_id
        pid = get_stripe_price_id("builder", "monthly")
        assert isinstance(pid, str) and len(pid) > 0

    def test_get_stripe_price_id_annual(self):
        from billing.pricing import get_stripe_price_id
        pid = get_stripe_price_id("team", "annual")
        assert isinstance(pid, str) and len(pid) > 0

    def test_get_stripe_price_id_unknown_tier_raises(self):
        from billing.pricing import get_stripe_price_id
        with pytest.raises(ValueError):
            get_stripe_price_id("platinum", "monthly")

    def test_get_stripe_price_id_invalid_period_raises(self):
        from billing.pricing import get_stripe_price_id
        with pytest.raises(ValueError):
            get_stripe_price_id("builder", "quarterly")

    def test_annual_savings_builder(self):
        from billing.pricing import get_annual_savings_pct
        pct = get_annual_savings_pct("builder")
        assert 15 < pct < 25  # ~20% savings

    def test_annual_savings_team(self):
        from billing.pricing import get_annual_savings_pct
        pct = get_annual_savings_pct("team")
        assert 20 < pct < 30  # ~25% savings

    def test_annual_savings_explorer_zero(self):
        from billing.pricing import get_annual_savings_pct
        assert get_annual_savings_pct("explorer") == 0.0

    def test_overage_rate_default(self):
        from billing.pricing import OVERAGE_RATE_PER_HOUR
        assert OVERAGE_RATE_PER_HOUR == 0.50

    def test_premium_surcharge_default(self):
        from billing.pricing import PREMIUM_MODEL_SURCHARGE_PER_HOUR
        assert PREMIUM_MODEL_SURCHARGE_PER_HOUR == 1.50

    def test_trial_days_default(self):
        from billing.pricing import TRIAL_DAYS
        assert TRIAL_DAYS == 14

    def test_trial_eligible_tiers(self):
        from billing.pricing import TRIAL_ELIGIBLE_TIERS
        assert "builder" in TRIAL_ELIGIBLE_TIERS
        assert "team" in TRIAL_ELIGIBLE_TIERS
        assert "organization" in TRIAL_ELIGIBLE_TIERS
        assert "explorer" not in TRIAL_ELIGIBLE_TIERS
        assert "fleet" not in TRIAL_ELIGIBLE_TIERS


# =============================================================================
# billing.overage
# =============================================================================

class TestOverageCalculation:
    def test_no_overage_within_limit(self):
        from billing.overage import calculate_overage
        result = calculate_overage("builder", used_hours=50.0)
        assert result.overage_hours == 0.0
        assert result.overage_charge_usd == 0.0

    def test_overage_beyond_limit(self):
        from billing.overage import calculate_overage
        result = calculate_overage("builder", used_hours=120.0)
        assert result.overage_hours == 20.0
        assert result.overage_charge_usd == pytest.approx(10.0)  # 20 * 0.50

    def test_explorer_hard_cap_no_charge(self):
        from billing.overage import calculate_overage
        result = calculate_overage("explorer", used_hours=15.0)
        assert result.is_hard_capped is True
        assert result.overage_charge_usd == 0.0
        assert result.overage_hours == 5.0

    def test_fleet_no_overage(self):
        from billing.overage import calculate_overage
        result = calculate_overage("fleet", used_hours=99999.0)
        assert result.overage_hours == 0.0
        assert result.included_hours is None

    def test_premium_surcharge_applied(self):
        from billing.overage import calculate_overage
        result = calculate_overage("team", used_hours=100.0, premium_hours=10.0)
        assert result.premium_surcharge_usd == pytest.approx(15.0)  # 10 * 1.50

    def test_total_charge_combines_overage_and_premium(self):
        from billing.overage import calculate_overage
        # 100 included, 110 used = 10 overage hrs @ 0.50 = $5
        # 5 premium hrs @ 1.50 = $7.50
        result = calculate_overage("builder", used_hours=110.0, premium_hours=5.0)
        assert result.overage_charge_usd == pytest.approx(5.0)
        assert result.premium_surcharge_usd == pytest.approx(7.50)
        assert result.total_charge_usd == pytest.approx(12.50)

    def test_no_overage_zero_usage(self):
        from billing.overage import calculate_overage
        result = calculate_overage("team", used_hours=0.0)
        assert result.overage_hours == 0.0
        assert result.total_charge_usd == 0.0

    def test_explorer_premium_no_charge(self):
        from billing.overage import calculate_overage
        result = calculate_overage("explorer", used_hours=8.0, premium_hours=2.0)
        # Explorer has no premium surcharge
        assert result.premium_surcharge_usd == 0.0


class TestTrialStatus:
    def test_explorer_not_trial_eligible(self):
        from billing.overage import get_trial_status
        status = get_trial_status("explorer", trial_start_ts=time.time())
        assert status.is_on_trial is False

    def test_fleet_not_trial_eligible(self):
        from billing.overage import get_trial_status
        status = get_trial_status("fleet", trial_start_ts=time.time())
        assert status.is_on_trial is False

    def test_no_trial_started(self):
        from billing.overage import get_trial_status
        status = get_trial_status("builder", trial_start_ts=None)
        assert status.is_on_trial is False
        assert status.days_remaining is None

    def test_active_trial(self):
        from billing.overage import get_trial_status
        start = time.time()
        status = get_trial_status("builder", trial_start_ts=start)
        assert status.is_on_trial is True
        assert status.days_remaining is not None
        assert status.days_remaining <= 14

    def test_expired_trial(self):
        from billing.overage import get_trial_status
        # Start 15 days ago
        start = time.time() - 15 * 86400
        status = get_trial_status("builder", trial_start_ts=start)
        assert status.is_expired is True
        assert status.is_on_trial is False

    def test_converted_trial(self):
        from billing.overage import get_trial_status
        start = time.time()
        status = get_trial_status("team", trial_start_ts=start, has_converted=True)
        assert status.has_converted is True
        assert status.is_on_trial is False

    def test_trial_end_calculated_correctly(self):
        from billing.overage import get_trial_status
        from billing.pricing import TRIAL_DAYS
        start = time.time()
        status = get_trial_status("team", trial_start_ts=start)
        expected_end = start + TRIAL_DAYS * 86400
        assert status.trial_end == pytest.approx(expected_end, abs=1)


class TestProration:
    def test_proration_upgrade_net_charge(self):
        from billing.overage import calculate_proration
        now = time.time()
        period_start = now - 15 * 86400   # 15 days ago
        period_end = now + 15 * 86400     # 15 days from now

        result = calculate_proration(
            from_tier_id="builder",
            to_tier_id="team",
            current_period_start_ts=period_start,
            current_period_end_ts=period_end,
        )
        # Net charge should be positive for upgrade
        assert result.net_charge_usd > 0
        assert result.days_remaining >= 14

    def test_proration_downgrade_credit(self):
        from billing.overage import calculate_proration
        now = time.time()
        period_start = now - 5 * 86400
        period_end = now + 25 * 86400

        result = calculate_proration(
            from_tier_id="team",
            to_tier_id="builder",
            current_period_start_ts=period_start,
            current_period_end_ts=period_end,
        )
        # Credit should exceed charge for downgrade
        assert result.net_charge_usd < 0

    def test_proration_zero_on_expired_period(self):
        from billing.overage import calculate_proration
        now = time.time()
        result = calculate_proration(
            from_tier_id="builder",
            to_tier_id="team",
            current_period_start_ts=now - 40 * 86400,
            current_period_end_ts=now - 10 * 86400,
        )
        assert result.days_remaining == 0

    def test_proration_annual_billing(self):
        from billing.overage import calculate_proration
        now = time.time()
        period_start = now - 30 * 86400
        period_end = now + 335 * 86400

        result = calculate_proration(
            from_tier_id="builder",
            to_tier_id="team",
            current_period_start_ts=period_start,
            current_period_end_ts=period_end,
            billing_period="annual",
        )
        # Annual prices are lower per month
        assert result.charge_usd > 0
        assert result.net_charge_usd > 0


# =============================================================================
# billing.routes (unit tests without full aiohttp server)
# =============================================================================

class TestBillingRouteHelpers:
    def test_tier_to_dict_contains_required_keys(self):
        from billing.routes import _tier_to_dict
        d = _tier_to_dict("team")
        assert "tier_id" in d
        assert "name" in d
        assert "monthly_price_usd" in d
        assert "allowed_models" in d
        assert "features" in d
        assert "stripe_price_id" in d
        assert "annual_savings_pct" in d

    def test_tier_to_dict_annual(self):
        from billing.routes import _tier_to_dict
        d = _tier_to_dict("builder", billing_period="annual")
        assert d["tier_id"] == "builder"

    def test_register_billing_routes_registers_expected_paths(self):
        from billing.routes import register_billing_routes
        mock_app = MagicMock()
        mock_router = MagicMock()
        mock_app.router = mock_router

        register_billing_routes(mock_app)

        added_paths = [call.args[0] for call in mock_router.add_get.call_args_list]
        added_post_paths = [call.args[0] for call in mock_router.add_post.call_args_list]

        assert "/api/billing/tiers" in added_paths
        assert "/api/billing/current" in added_paths
        assert "/api/billing/upgrade" in added_post_paths
        assert "/api/billing/trial/start" in added_post_paths
        assert "/api/pricing" in added_paths


@pytest.mark.asyncio
class TestBillingRouteHandlers:
    async def test_list_tiers_returns_all_five(self):
        from billing.routes import list_tiers
        mock_request = MagicMock()
        mock_request.rel_url.query.get.return_value = "monthly"

        response = await list_tiers(mock_request)
        import json
        data = json.loads(response.text)
        assert len(data["tiers"]) == 5

    async def test_list_tiers_invalid_period(self):
        from billing.routes import list_tiers
        mock_request = MagicMock()
        mock_request.rel_url.query.get.return_value = "quarterly"

        response = await list_tiers(mock_request)
        assert response.status == 400

    async def test_get_current_billing_defaults_to_explorer(self):
        from billing.routes import get_current_billing
        mock_request = MagicMock(spec=[])

        response = await get_current_billing(mock_request)
        import json
        data = json.loads(response.text)
        assert data["tier"]["tier_id"] == "explorer"

    async def test_upgrade_tier_missing_to_tier(self):
        from billing.routes import upgrade_tier
        mock_request = AsyncMock()
        mock_request.json = AsyncMock(return_value={})
        mock_request.user_tier = "explorer"

        response = await upgrade_tier(mock_request)
        assert response.status == 400

    async def test_upgrade_tier_same_tier_conflict(self):
        from billing.routes import upgrade_tier
        mock_request = AsyncMock()
        mock_request.json = AsyncMock(return_value={"to_tier": "explorer"})
        mock_request.user_tier = "explorer"

        response = await upgrade_tier(mock_request)
        assert response.status == 409

    async def test_upgrade_tier_fleet_returns_contact_sales(self):
        from billing.routes import upgrade_tier
        import json
        mock_request = AsyncMock()
        mock_request.json = AsyncMock(return_value={"to_tier": "fleet"})
        mock_request.user_tier = "explorer"

        response = await upgrade_tier(mock_request)
        data = json.loads(response.text)
        assert "contact" in data.get("message", "").lower() or "sales" in str(data).lower()

    async def test_start_trial_invalid_tier(self):
        from billing.routes import start_trial
        mock_request = AsyncMock()
        mock_request.json = AsyncMock(return_value={"tier": "explorer"})

        response = await start_trial(mock_request)
        assert response.status == 400

    async def test_start_trial_valid_tier(self):
        from billing.routes import start_trial
        import json
        mock_request = AsyncMock()
        mock_request.json = AsyncMock(return_value={"tier": "team"})

        response = await start_trial(mock_request)
        data = json.loads(response.text)
        assert data["tier"] == "team"
        assert "trial_end" in data
        assert data["trial_days"] == 14

    async def test_start_trial_missing_tier(self):
        from billing.routes import start_trial
        mock_request = AsyncMock()
        mock_request.json = AsyncMock(return_value={})

        response = await start_trial(mock_request)
        assert response.status == 400
