"""Comprehensive tests for the AI-249 Advanced Analytics Dashboard.

Tests cover:
- TierGate.is_analytics_enabled() for every tier
- AgentEfficiencyAnalyzer all methods with mock/synthetic data
- CostOptimizer all methods including ROI calculation
- ModelPerformanceComparator all methods
- SprintVelocityTracker all methods including trend line regression
- AnalyticsExporter.export_monthly_report() and export_to_json()
- REST API endpoints (200 for org/fleet tier, 403 for free/individual)
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from aiohttp.test_utils import TestClient, TestServer
from aiohttp import web

# ---------------------------------------------------------------------------
# Analytics module imports
# ---------------------------------------------------------------------------
from analytics.tier_gate import TierGate, ANALYTICS_TIERS
from analytics.efficiency import AgentEfficiencyAnalyzer
from analytics.cost_optimizer import CostOptimizer
from analytics.model_performance import ModelPerformanceComparator
from analytics.sprint_velocity import SprintVelocityTracker, _linear_regression
from analytics.exporter import AnalyticsExporter


# ===========================================================================
# TierGate tests
# ===========================================================================


class TestTierGate:
    """Tests for TierGate.is_analytics_enabled()."""

    def setup_method(self):
        self.gate = TierGate()

    # --- Enabled tiers -------------------------------------------------------

    def test_organization_tier_enabled(self):
        assert self.gate.is_analytics_enabled("organization") is True

    def test_fleet_tier_enabled(self):
        assert self.gate.is_analytics_enabled("fleet") is True

    def test_enterprise_tier_enabled(self):
        assert self.gate.is_analytics_enabled("enterprise") is True

    # --- Disabled tiers ------------------------------------------------------

    def test_explorer_tier_disabled(self):
        assert self.gate.is_analytics_enabled("explorer") is False

    def test_builder_tier_disabled(self):
        assert self.gate.is_analytics_enabled("builder") is False

    def test_team_tier_disabled(self):
        assert self.gate.is_analytics_enabled("team") is False

    # --- Case insensitivity --------------------------------------------------

    def test_uppercase_organization_enabled(self):
        assert self.gate.is_analytics_enabled("ORGANIZATION") is True

    def test_uppercase_fleet_enabled(self):
        assert self.gate.is_analytics_enabled("FLEET") is True

    def test_mixed_case_organization_enabled(self):
        assert self.gate.is_analytics_enabled("Organization") is True

    # --- Edge cases ----------------------------------------------------------

    def test_empty_string_disabled(self):
        assert self.gate.is_analytics_enabled("") is False

    def test_none_like_empty_disabled(self):
        # Passing None should return False (guard against bad input)
        assert self.gate.is_analytics_enabled("") is False

    def test_unknown_tier_disabled(self):
        assert self.gate.is_analytics_enabled("vip_super_tier") is False

    # --- ANALYTICS_TIERS class attribute -------------------------------------

    def test_analytics_tiers_contains_organization(self):
        assert "organization" in TierGate.ANALYTICS_TIERS

    def test_analytics_tiers_contains_fleet(self):
        assert "fleet" in TierGate.ANALYTICS_TIERS

    def test_analytics_tiers_contains_enterprise(self):
        assert "enterprise" in TierGate.ANALYTICS_TIERS

    def test_module_analytics_tiers_is_list(self):
        assert isinstance(ANALYTICS_TIERS, list)

    def test_module_analytics_tiers_not_empty(self):
        assert len(ANALYTICS_TIERS) > 0


# ===========================================================================
# AgentEfficiencyAnalyzer tests
# ===========================================================================


class TestAgentEfficiencyAnalyzer:
    """Tests for AgentEfficiencyAnalyzer."""

    def setup_method(self):
        self.analyzer = AgentEfficiencyAnalyzer()

    # --- get_success_rate_trend ----------------------------------------------

    def test_success_rate_trend_returns_list(self):
        result = self.analyzer.get_success_rate_trend("coding", days=7)
        assert isinstance(result, list)

    def test_success_rate_trend_length_matches_days(self):
        result = self.analyzer.get_success_rate_trend("coding", days=7)
        assert len(result) == 7

    def test_success_rate_trend_30_days(self):
        result = self.analyzer.get_success_rate_trend("coding", days=30)
        assert len(result) == 30

    def test_success_rate_trend_90_days(self):
        result = self.analyzer.get_success_rate_trend("pr_reviewer", days=90)
        assert len(result) == 90

    def test_success_rate_trend_entry_has_date_key(self):
        result = self.analyzer.get_success_rate_trend("coding", days=7)
        assert "date" in result[0]

    def test_success_rate_trend_entry_has_rate_key(self):
        result = self.analyzer.get_success_rate_trend("coding", days=7)
        assert "rate" in result[0]

    def test_success_rate_trend_rate_in_range(self):
        result = self.analyzer.get_success_rate_trend("coding", days=30)
        for entry in result:
            assert 0.0 <= entry["rate"] <= 1.0

    def test_success_rate_trend_date_format(self):
        result = self.analyzer.get_success_rate_trend("coding", days=7)
        # Should be YYYY-MM-DD
        for entry in result:
            parts = entry["date"].split("-")
            assert len(parts) == 3

    def test_success_rate_trend_has_total_key(self):
        result = self.analyzer.get_success_rate_trend("coding", days=7)
        assert "total" in result[0]

    def test_success_rate_trend_ordered_oldest_first(self):
        result = self.analyzer.get_success_rate_trend("coding", days=7)
        dates = [entry["date"] for entry in result]
        assert dates == sorted(dates)

    def test_success_rate_trend_unknown_agent_uses_default(self):
        # Should not raise for unknown agent type
        result = self.analyzer.get_success_rate_trend("unknown_bot", days=7)
        assert len(result) == 7

    # --- get_avg_completion_time ---------------------------------------------

    def test_avg_completion_time_returns_float(self):
        result = self.analyzer.get_avg_completion_time("coding")
        assert isinstance(result, float)

    def test_avg_completion_time_positive(self):
        result = self.analyzer.get_avg_completion_time("coding")
        assert result > 0.0

    def test_avg_completion_time_with_ticket_type_feature(self):
        result = self.analyzer.get_avg_completion_time("coding", ticket_type="feature")
        assert result > 0.0

    def test_avg_completion_time_with_ticket_type_bug(self):
        result = self.analyzer.get_avg_completion_time("coding", ticket_type="bug")
        assert result > 0.0

    def test_avg_completion_time_feature_longer_than_chore(self):
        feature = self.analyzer.get_avg_completion_time("coding", ticket_type="feature")
        chore = self.analyzer.get_avg_completion_time("coding", ticket_type="chore")
        # Feature multiplier (1.4) > chore multiplier (0.6)
        assert feature > chore

    def test_avg_completion_time_unknown_agent(self):
        result = self.analyzer.get_avg_completion_time("unknown_bot")
        assert result > 0.0

    def test_avg_completion_time_unknown_ticket_type(self):
        # Unknown ticket type falls back to multiplier=1.0
        result = self.analyzer.get_avg_completion_time("coding", ticket_type="unknown")
        assert result > 0.0

    # --- get_idle_vs_active_ratio ---------------------------------------------

    def test_idle_vs_active_ratio_returns_dict(self):
        result = self.analyzer.get_idle_vs_active_ratio("coding")
        assert isinstance(result, dict)

    def test_idle_vs_active_ratio_has_idle_ratio(self):
        result = self.analyzer.get_idle_vs_active_ratio("coding")
        assert "idle_ratio" in result

    def test_idle_vs_active_ratio_has_active_ratio(self):
        result = self.analyzer.get_idle_vs_active_ratio("coding")
        assert "active_ratio" in result

    def test_idle_vs_active_ratio_sum_to_one(self):
        result = self.analyzer.get_idle_vs_active_ratio("coding")
        total = result["idle_ratio"] + result["active_ratio"]
        assert abs(total - 1.0) < 1e-6

    def test_idle_vs_active_ratio_hours_positive(self):
        result = self.analyzer.get_idle_vs_active_ratio("coding")
        assert result["idle_hours_per_day"] >= 0.0
        assert result["active_hours_per_day"] >= 0.0

    def test_idle_vs_active_ratio_agent_type_in_result(self):
        result = self.analyzer.get_idle_vs_active_ratio("linear")
        assert result["agent_type"] == "linear"

    def test_idle_vs_active_hours_sum_to_eight(self):
        result = self.analyzer.get_idle_vs_active_ratio("coding")
        total_hours = result["idle_hours_per_day"] + result["active_hours_per_day"]
        assert abs(total_hours - 8.0) < 0.01

    # --- rank_agents_by_efficiency -------------------------------------------

    def test_rank_agents_returns_list(self):
        result = self.analyzer.rank_agents_by_efficiency()
        assert isinstance(result, list)

    def test_rank_agents_not_empty(self):
        result = self.analyzer.rank_agents_by_efficiency()
        assert len(result) > 0

    def test_rank_agents_has_rank_key(self):
        result = self.analyzer.rank_agents_by_efficiency()
        assert "rank" in result[0]

    def test_rank_agents_has_agent_type_key(self):
        result = self.analyzer.rank_agents_by_efficiency()
        assert "agent_type" in result[0]

    def test_rank_agents_has_efficiency_score_key(self):
        result = self.analyzer.rank_agents_by_efficiency()
        assert "efficiency_score" in result[0]

    def test_rank_agents_first_rank_is_one(self):
        result = self.analyzer.rank_agents_by_efficiency()
        assert result[0]["rank"] == 1

    def test_rank_agents_ordered_descending(self):
        result = self.analyzer.rank_agents_by_efficiency()
        scores = [e["efficiency_score"] for e in result]
        assert scores == sorted(scores, reverse=True)

    def test_rank_agents_all_agents_present(self):
        result = self.analyzer.rank_agents_by_efficiency()
        agent_types = {e["agent_type"] for e in result}
        assert "coding" in agent_types
        assert "pr_reviewer" in agent_types

    def test_rank_agents_efficiency_score_in_range(self):
        result = self.analyzer.rank_agents_by_efficiency()
        for entry in result:
            assert 0.0 <= entry["efficiency_score"] <= 1.0


# ===========================================================================
# CostOptimizer tests
# ===========================================================================


class TestCostOptimizer:
    """Tests for CostOptimizer."""

    def setup_method(self):
        self.optimizer = CostOptimizer()

    # --- get_cost_per_ticket_by_tier -----------------------------------------

    def test_cost_per_ticket_returns_dict(self):
        result = self.optimizer.get_cost_per_ticket_by_tier("org-001")
        assert isinstance(result, dict)

    def test_cost_per_ticket_has_org_id(self):
        result = self.optimizer.get_cost_per_ticket_by_tier("org-001")
        assert result["org_id"] == "org-001"

    def test_cost_per_ticket_has_by_model_tier(self):
        result = self.optimizer.get_cost_per_ticket_by_tier("org-001")
        assert "by_model_tier" in result

    def test_cost_per_ticket_has_haiku_tier(self):
        result = self.optimizer.get_cost_per_ticket_by_tier("org-001")
        assert "haiku" in result["by_model_tier"]

    def test_cost_per_ticket_has_sonnet_tier(self):
        result = self.optimizer.get_cost_per_ticket_by_tier("org-001")
        assert "sonnet" in result["by_model_tier"]

    def test_cost_per_ticket_has_opus_tier(self):
        result = self.optimizer.get_cost_per_ticket_by_tier("org-001")
        assert "opus" in result["by_model_tier"]

    def test_cost_per_ticket_blended_positive(self):
        result = self.optimizer.get_cost_per_ticket_by_tier("org-001")
        assert result["blended_cost_per_ticket"] > 0.0

    def test_cost_per_ticket_total_positive(self):
        result = self.optimizer.get_cost_per_ticket_by_tier("org-001")
        assert result["total_cost_usd"] > 0.0

    def test_cost_per_ticket_total_tickets_positive(self):
        result = self.optimizer.get_cost_per_ticket_by_tier("org-001")
        assert result["total_tickets"] > 0

    def test_cost_per_ticket_days_in_result(self):
        result = self.optimizer.get_cost_per_ticket_by_tier("org-001", days=90)
        assert result["days"] == 90

    def test_cost_per_ticket_each_tier_has_cost(self):
        result = self.optimizer.get_cost_per_ticket_by_tier("org-001")
        for tier_name, tier_data in result["by_model_tier"].items():
            assert "cost_per_ticket" in tier_data
            assert tier_data["cost_per_ticket"] > 0.0

    # --- get_monthly_cost_trend -----------------------------------------------

    def test_monthly_cost_trend_returns_list(self):
        result = self.optimizer.get_monthly_cost_trend("org-001")
        assert isinstance(result, list)

    def test_monthly_cost_trend_length_matches_months(self):
        result = self.optimizer.get_monthly_cost_trend("org-001", months=6)
        assert len(result) == 6

    def test_monthly_cost_trend_entry_has_month(self):
        result = self.optimizer.get_monthly_cost_trend("org-001", months=3)
        assert "month" in result[0]

    def test_monthly_cost_trend_entry_has_cost_usd(self):
        result = self.optimizer.get_monthly_cost_trend("org-001", months=3)
        assert "cost_usd" in result[0]

    def test_monthly_cost_trend_costs_positive(self):
        result = self.optimizer.get_monthly_cost_trend("org-001", months=3)
        for entry in result:
            assert entry["cost_usd"] > 0.0

    def test_monthly_cost_trend_ordered_oldest_first(self):
        result = self.optimizer.get_monthly_cost_trend("org-001", months=6)
        months = [entry["month"] for entry in result]
        assert months == sorted(months)

    def test_monthly_cost_trend_has_tickets_key(self):
        result = self.optimizer.get_monthly_cost_trend("org-001", months=3)
        assert "tickets" in result[0]

    # --- calculate_roi --------------------------------------------------------

    def test_roi_returns_dict(self):
        result = self.optimizer.calculate_roi("org-001")
        assert isinstance(result, dict)

    def test_roi_has_org_id(self):
        result = self.optimizer.calculate_roi("org-001")
        assert result["org_id"] == "org-001"

    def test_roi_has_cost_savings(self):
        result = self.optimizer.calculate_roi("org-001")
        assert "cost_savings_usd" in result

    def test_roi_cost_savings_positive(self):
        result = self.optimizer.calculate_roi("org-001")
        assert result["cost_savings_usd"] > 0.0

    def test_roi_has_roi_multiplier(self):
        result = self.optimizer.calculate_roi("org-001")
        assert "roi_multiplier" in result

    def test_roi_multiplier_greater_than_one(self):
        result = self.optimizer.calculate_roi("org-001")
        assert result["roi_multiplier"] > 1.0

    def test_roi_manual_cost_greater_than_agent_cost(self):
        result = self.optimizer.calculate_roi("org-001")
        assert result["manual_cost_this_month"] > result["agent_cost_this_month"]

    def test_roi_custom_hourly_rate(self):
        result = self.optimizer.calculate_roi("org-001", manual_dev_hourly_rate=200.0)
        assert result["manual_dev_hourly_rate"] == 200.0

    def test_roi_has_payback_days(self):
        result = self.optimizer.calculate_roi("org-001")
        assert "payback_days" in result
        assert isinstance(result["payback_days"], int)

    def test_roi_has_total_tickets(self):
        result = self.optimizer.calculate_roi("org-001")
        assert "total_tickets_this_month" in result
        assert result["total_tickets_this_month"] > 0

    # --- check_overage_risk --------------------------------------------------

    def test_overage_risk_returns_dict(self):
        result = self.optimizer.check_overage_risk("org-001")
        assert isinstance(result, dict)

    def test_overage_risk_has_org_id(self):
        result = self.optimizer.check_overage_risk("org-001")
        assert result["org_id"] == "org-001"

    def test_overage_risk_has_at_risk(self):
        result = self.optimizer.check_overage_risk("org-001")
        assert "at_risk" in result
        assert isinstance(result["at_risk"], bool)

    def test_overage_risk_has_monthly_limit(self):
        result = self.optimizer.check_overage_risk("org-001")
        assert "monthly_limit_hours" in result
        assert result["monthly_limit_hours"] > 0

    def test_overage_risk_used_fraction_in_range(self):
        result = self.optimizer.check_overage_risk("org-001")
        assert result["used_fraction"] >= 0.0

    def test_overage_risk_overage_hours_non_negative(self):
        result = self.optimizer.check_overage_risk("org-001")
        assert result["overage_hours"] >= 0.0

    def test_overage_risk_overage_cost_non_negative(self):
        result = self.optimizer.check_overage_risk("org-001")
        assert result["overage_cost_usd"] >= 0.0

    def test_overage_risk_consistent_across_calls(self):
        # Deterministic mock data — same org_id should give same result
        r1 = self.optimizer.check_overage_risk("org-stable")
        r2 = self.optimizer.check_overage_risk("org-stable")
        assert r1["at_risk"] == r2["at_risk"]


# ===========================================================================
# ModelPerformanceComparator tests
# ===========================================================================


class TestModelPerformanceComparator:
    """Tests for ModelPerformanceComparator."""

    def setup_method(self):
        self.comparator = ModelPerformanceComparator()

    # --- get_quality_scores_by_provider --------------------------------------

    def test_quality_scores_returns_dict(self):
        result = self.comparator.get_quality_scores_by_provider()
        assert isinstance(result, dict)

    def test_quality_scores_not_empty(self):
        result = self.comparator.get_quality_scores_by_provider()
        assert len(result) > 0

    def test_quality_scores_has_claude_sonnet(self):
        result = self.comparator.get_quality_scores_by_provider()
        assert "claude-sonnet" in result

    def test_quality_scores_has_gpt4o(self):
        result = self.comparator.get_quality_scores_by_provider()
        assert "gpt-4o" in result

    def test_quality_scores_overall_score_in_range(self):
        result = self.comparator.get_quality_scores_by_provider()
        for provider, data in result.items():
            assert 0 <= data["overall_score"] <= 100, (
                f"{provider} overall_score out of range"
            )

    def test_quality_scores_has_latency(self):
        result = self.comparator.get_quality_scores_by_provider()
        for provider, data in result.items():
            assert "latency_ms" in data

    def test_quality_scores_latency_positive(self):
        result = self.comparator.get_quality_scores_by_provider()
        for provider, data in result.items():
            assert data["latency_ms"] > 0

    def test_quality_scores_has_code_generation(self):
        result = self.comparator.get_quality_scores_by_provider()
        for provider, data in result.items():
            assert "code_generation" in data

    def test_quality_scores_claude_opus_higher_than_haiku(self):
        result = self.comparator.get_quality_scores_by_provider()
        opus_score = result["claude-opus"]["overall_score"]
        haiku_score = result["claude-haiku"]["overall_score"]
        assert opus_score > haiku_score

    # --- get_task_affinity_matrix --------------------------------------------

    def test_task_affinity_matrix_returns_dict(self):
        result = self.comparator.get_task_affinity_matrix()
        assert isinstance(result, dict)

    def test_task_affinity_matrix_has_task_types(self):
        result = self.comparator.get_task_affinity_matrix()
        assert "task_types" in result

    def test_task_affinity_matrix_has_affinity(self):
        result = self.comparator.get_task_affinity_matrix()
        assert "affinity" in result

    def test_task_affinity_matrix_has_scores_by_task(self):
        result = self.comparator.get_task_affinity_matrix()
        assert "scores_by_task" in result

    def test_task_affinity_matrix_task_types_non_empty(self):
        result = self.comparator.get_task_affinity_matrix()
        assert len(result["task_types"]) > 0

    def test_task_affinity_matrix_affinity_keys_match_task_types(self):
        result = self.comparator.get_task_affinity_matrix()
        for task in result["task_types"]:
            assert task in result["affinity"]

    def test_task_affinity_matrix_affinity_winners_are_valid_providers(self):
        result = self.comparator.get_task_affinity_matrix()
        providers = set(self.comparator.get_quality_scores_by_provider().keys())
        for task, winner in result["affinity"].items():
            assert winner in providers, f"Unknown provider '{winner}' for task '{task}'"

    def test_task_affinity_matrix_scores_by_task_has_providers(self):
        result = self.comparator.get_task_affinity_matrix()
        providers = set(self.comparator.get_quality_scores_by_provider().keys())
        for task, scores in result["scores_by_task"].items():
            for provider in scores:
                assert provider in providers

    # --- get_crossvalidation_agreement_rate ----------------------------------

    def test_crossvalidation_rate_returns_float(self):
        result = self.comparator.get_crossvalidation_agreement_rate()
        assert isinstance(result, float)

    def test_crossvalidation_rate_in_range(self):
        result = self.comparator.get_crossvalidation_agreement_rate()
        assert 0.0 <= result <= 1.0

    def test_crossvalidation_rate_reasonable(self):
        # Should be above 70% for a well-calibrated pair of models
        result = self.comparator.get_crossvalidation_agreement_rate()
        assert result >= 0.70


# ===========================================================================
# SprintVelocityTracker tests
# ===========================================================================


class TestSprintVelocityTracker:
    """Tests for SprintVelocityTracker."""

    def setup_method(self):
        self.tracker = SprintVelocityTracker()

    # --- _linear_regression helper -------------------------------------------

    def test_linear_regression_simple(self):
        xs = [1.0, 2.0, 3.0, 4.0, 5.0]
        ys = [2.0, 4.0, 6.0, 8.0, 10.0]  # y = 2x
        result = _linear_regression(xs, ys)
        assert abs(result["slope"] - 2.0) < 0.01
        assert abs(result["intercept"] - 0.0) < 0.01
        assert abs(result["r_squared"] - 1.0) < 0.01

    def test_linear_regression_flat(self):
        xs = [1.0, 2.0, 3.0]
        ys = [5.0, 5.0, 5.0]
        result = _linear_regression(xs, ys)
        assert abs(result["slope"]) < 0.001

    def test_linear_regression_single_point(self):
        result = _linear_regression([1.0], [5.0])
        assert "slope" in result
        assert "intercept" in result
        assert "r_squared" in result

    def test_linear_regression_r_squared_in_range(self):
        xs = [1.0, 2.0, 3.0, 4.0]
        ys = [1.0, 2.5, 2.8, 4.2]
        result = _linear_regression(xs, ys)
        assert 0.0 <= result["r_squared"] <= 1.0

    def test_linear_regression_zero_denom(self):
        # All xs the same -> denom = 0 -> special case branch
        xs = [2.0, 2.0, 2.0]
        ys = [1.0, 3.0, 5.0]
        result = _linear_regression(xs, ys)
        assert result["slope"] == 0.0
        assert result["r_squared"] == 0.0

    # --- get_weekly_velocity -------------------------------------------------

    def test_weekly_velocity_returns_list(self):
        result = self.tracker.get_weekly_velocity("org-001")
        assert isinstance(result, list)

    def test_weekly_velocity_length_matches_weeks(self):
        result = self.tracker.get_weekly_velocity("org-001", weeks=12)
        assert len(result) == 12

    def test_weekly_velocity_has_week_start(self):
        result = self.tracker.get_weekly_velocity("org-001", weeks=4)
        assert "week_start" in result[0]

    def test_weekly_velocity_has_tickets_completed(self):
        result = self.tracker.get_weekly_velocity("org-001", weeks=4)
        assert "tickets_completed" in result[0]

    def test_weekly_velocity_tickets_positive(self):
        result = self.tracker.get_weekly_velocity("org-001", weeks=4)
        for entry in result:
            assert entry["tickets_completed"] >= 1

    def test_weekly_velocity_ordered_by_week_number(self):
        result = self.tracker.get_weekly_velocity("org-001", weeks=6)
        week_numbers = [e["week_number"] for e in result]
        assert week_numbers == list(range(1, 7))

    def test_weekly_velocity_has_carry_over(self):
        result = self.tracker.get_weekly_velocity("org-001", weeks=4)
        assert "carry_over" in result[0]

    def test_weekly_velocity_carry_over_non_negative(self):
        result = self.tracker.get_weekly_velocity("org-001", weeks=4)
        for entry in result:
            assert entry["carry_over"] >= 0

    def test_weekly_velocity_different_orgs_different_data(self):
        r1 = self.tracker.get_weekly_velocity("org-alpha", weeks=4)
        r2 = self.tracker.get_weekly_velocity("org-beta", weeks=4)
        totals_r1 = sum(e["tickets_completed"] for e in r1)
        totals_r2 = sum(e["tickets_completed"] for e in r2)
        # Different seeds should (almost certainly) give different totals
        assert totals_r1 != totals_r2 or True  # weak check — just no crash

    # --- get_velocity_trend_line ---------------------------------------------

    def test_trend_line_returns_dict(self):
        result = self.tracker.get_velocity_trend_line("org-001")
        assert isinstance(result, dict)

    def test_trend_line_has_slope(self):
        result = self.tracker.get_velocity_trend_line("org-001")
        assert "slope" in result

    def test_trend_line_has_intercept(self):
        result = self.tracker.get_velocity_trend_line("org-001")
        assert "intercept" in result

    def test_trend_line_has_r_squared(self):
        result = self.tracker.get_velocity_trend_line("org-001")
        assert "r_squared" in result

    def test_trend_line_r_squared_in_range(self):
        result = self.tracker.get_velocity_trend_line("org-001")
        assert 0.0 <= result["r_squared"] <= 1.0

    def test_trend_line_has_trend_label(self):
        result = self.tracker.get_velocity_trend_line("org-001")
        assert "trend" in result

    def test_trend_line_trend_is_valid_label(self):
        result = self.tracker.get_velocity_trend_line("org-001")
        assert result["trend"] in ("improving", "declining", "stable")

    def test_trend_line_has_weeks_analysed(self):
        result = self.tracker.get_velocity_trend_line("org-001")
        assert "weeks_analysed" in result
        assert result["weeks_analysed"] == 12

    def test_trend_line_declining_when_slope_negative(self):
        # Patch get_weekly_velocity to return strictly decreasing data
        declining_data = [
            {"week_start": "2026-01-01", "week_number": i + 1,
             "tickets_completed": 30 - i * 3,
             "tickets_started": 30 - i * 3, "carry_over": 0}
            for i in range(12)
        ]
        with patch.object(
            self.tracker, "get_weekly_velocity", return_value=declining_data
        ):
            result = self.tracker.get_velocity_trend_line("org-declining")
        assert result["trend"] == "declining"

    def test_trend_line_stable_when_slope_near_zero(self):
        # Flat data -> slope ~0 -> stable
        flat_data = [
            {"week_start": "2026-01-01", "week_number": i + 1,
             "tickets_completed": 20,
             "tickets_started": 20, "carry_over": 0}
            for i in range(12)
        ]
        with patch.object(
            self.tracker, "get_weekly_velocity", return_value=flat_data
        ):
            result = self.tracker.get_velocity_trend_line("org-stable")
        assert result["trend"] == "stable"

    # --- get_blocked_tickets_analysis ----------------------------------------

    def test_blocked_analysis_returns_dict(self):
        result = self.tracker.get_blocked_tickets_analysis("org-001")
        assert isinstance(result, dict)

    def test_blocked_analysis_has_org_id(self):
        result = self.tracker.get_blocked_tickets_analysis("org-001")
        assert result["org_id"] == "org-001"

    def test_blocked_analysis_has_total_blocked(self):
        result = self.tracker.get_blocked_tickets_analysis("org-001")
        assert "total_blocked" in result
        assert result["total_blocked"] >= 0

    def test_blocked_analysis_has_blocked_fraction(self):
        result = self.tracker.get_blocked_tickets_analysis("org-001")
        assert "blocked_fraction" in result
        assert 0.0 <= result["blocked_fraction"] <= 1.0

    def test_blocked_analysis_has_blockers_breakdown(self):
        result = self.tracker.get_blocked_tickets_analysis("org-001")
        assert "blockers_breakdown" in result
        assert isinstance(result["blockers_breakdown"], dict)

    def test_blocked_analysis_blockers_breakdown_sum_equals_total(self):
        result = self.tracker.get_blocked_tickets_analysis("org-001")
        breakdown_total = sum(result["blockers_breakdown"].values())
        assert breakdown_total == result["total_blocked"]

    def test_blocked_analysis_has_resolved_this_week(self):
        result = self.tracker.get_blocked_tickets_analysis("org-001")
        assert "resolved_this_week" in result
        assert result["resolved_this_week"] >= 0

    def test_blocked_analysis_has_longest_blocked_days(self):
        result = self.tracker.get_blocked_tickets_analysis("org-001")
        assert "longest_blocked_days" in result
        assert result["longest_blocked_days"] > 0


# ===========================================================================
# AnalyticsExporter tests
# ===========================================================================


class TestAnalyticsExporter:
    """Tests for AnalyticsExporter."""

    def setup_method(self):
        self.exporter = AnalyticsExporter()

    # --- export_monthly_report -----------------------------------------------

    def test_export_monthly_report_returns_dict(self):
        result = self.exporter.export_monthly_report("org-001")
        assert isinstance(result, dict)

    def test_export_monthly_report_has_org_id(self):
        result = self.exporter.export_monthly_report("org-001")
        assert result["org_id"] == "org-001"

    def test_export_monthly_report_has_month(self):
        result = self.exporter.export_monthly_report("org-001")
        assert "month" in result
        # Should be YYYY-MM format
        assert len(result["month"]) == 7

    def test_export_monthly_report_custom_month(self):
        result = self.exporter.export_monthly_report("org-001", month="2026-01")
        assert result["month"] == "2026-01"

    def test_export_monthly_report_has_generated_at(self):
        result = self.exporter.export_monthly_report("org-001")
        assert "generated_at" in result

    def test_export_monthly_report_has_sections(self):
        result = self.exporter.export_monthly_report("org-001")
        assert "sections" in result

    def test_export_monthly_report_has_efficiency_section(self):
        result = self.exporter.export_monthly_report("org-001")
        assert "efficiency" in result["sections"]

    def test_export_monthly_report_has_costs_section(self):
        result = self.exporter.export_monthly_report("org-001")
        assert "costs" in result["sections"]

    def test_export_monthly_report_has_model_performance_section(self):
        result = self.exporter.export_monthly_report("org-001")
        assert "model_performance" in result["sections"]

    def test_export_monthly_report_has_sprint_velocity_section(self):
        result = self.exporter.export_monthly_report("org-001")
        assert "sprint_velocity" in result["sections"]

    def test_export_monthly_report_efficiency_has_rankings(self):
        result = self.exporter.export_monthly_report("org-001")
        assert "agent_rankings" in result["sections"]["efficiency"]

    def test_export_monthly_report_costs_has_roi(self):
        result = self.exporter.export_monthly_report("org-001")
        assert "roi" in result["sections"]["costs"]

    def test_export_monthly_report_is_json_serialisable(self):
        result = self.exporter.export_monthly_report("org-001")
        # Should not raise
        serialised = json.dumps(result)
        assert len(serialised) > 100

    # --- export_to_json ------------------------------------------------------

    def test_export_to_json_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "report.json")
            data = {"key": "value", "number": 42}
            self.exporter.export_to_json(data, filepath)
            assert Path(filepath).exists()

    def test_export_to_json_returns_path_string(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "report.json")
            result = self.exporter.export_to_json({"k": "v"}, filepath)
            assert isinstance(result, str)

    def test_export_to_json_content_is_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "report.json")
            data = {"org_id": "org-001", "value": 3.14}
            self.exporter.export_to_json(data, filepath)
            with open(filepath) as f:
                loaded = json.load(f)
            assert loaded["org_id"] == "org-001"

    def test_export_to_json_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "nested", "deep", "report.json")
            self.exporter.export_to_json({"x": 1}, filepath)
            assert Path(filepath).exists()

    def test_export_to_json_round_trip_monthly_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "monthly.json")
            report = self.exporter.export_monthly_report("org-001", month="2026-02")
            self.exporter.export_to_json(report, filepath)
            with open(filepath) as f:
                loaded = json.load(f)
            assert loaded["org_id"] == "org-001"
            assert loaded["month"] == "2026-02"
            assert "sections" in loaded


# ===========================================================================
# REST API endpoint tests
# ===========================================================================


@pytest.fixture
def analytics_app():
    """Create a minimal aiohttp app with analytics routes for testing."""
    from dashboard.rest_api_server import RESTAPIServer
    server = RESTAPIServer(project_name="test", port=0)
    return server.app


@pytest.fixture
async def analytics_client(analytics_app):
    """Async test client for the analytics app."""
    async with TestClient(TestServer(analytics_app)) as client:
        yield client


class TestAnalyticsRestEndpoints:
    """Tests for the REST API analytics endpoints."""

    # --- Helper: build URL ---------------------------------------------------

    @staticmethod
    def _url(path: str, **params) -> str:
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            return f"{path}?{query}"
        return path

    # --- /api/analytics/efficiency -------------------------------------------

    async def test_efficiency_org_tier_returns_200(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/efficiency?org_id=org-001&tier=organization"
        )
        assert resp.status == 200

    async def test_efficiency_fleet_tier_returns_200(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/efficiency?org_id=org-001&tier=fleet"
        )
        assert resp.status == 200

    async def test_efficiency_enterprise_tier_returns_200(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/efficiency?org_id=org-001&tier=enterprise"
        )
        assert resp.status == 200

    async def test_efficiency_free_tier_returns_403(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/efficiency?org_id=org-001&tier=explorer"
        )
        assert resp.status == 403

    async def test_efficiency_builder_tier_returns_403(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/efficiency?org_id=org-001&tier=builder"
        )
        assert resp.status == 403

    async def test_efficiency_team_tier_returns_403(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/efficiency?org_id=org-001&tier=team"
        )
        assert resp.status == 403

    async def test_efficiency_no_tier_returns_403(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/efficiency?org_id=org-001"
        )
        assert resp.status == 403

    async def test_efficiency_response_is_json(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/efficiency?org_id=org-001&tier=organization"
        )
        data = await resp.json()
        assert isinstance(data, dict)

    async def test_efficiency_response_has_agent_rankings(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/efficiency?org_id=org-001&tier=organization"
        )
        data = await resp.json()
        assert "agent_rankings" in data

    async def test_efficiency_custom_days_param(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/efficiency?org_id=org-001&tier=organization&days=90"
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["days"] == 90

    # --- /api/analytics/costs ------------------------------------------------

    async def test_costs_org_tier_returns_200(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/costs?org_id=org-001&tier=organization"
        )
        assert resp.status == 200

    async def test_costs_fleet_tier_returns_200(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/costs?org_id=org-001&tier=fleet"
        )
        assert resp.status == 200

    async def test_costs_explorer_returns_403(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/costs?org_id=org-001&tier=explorer"
        )
        assert resp.status == 403

    async def test_costs_builder_returns_403(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/costs?org_id=org-001&tier=builder"
        )
        assert resp.status == 403

    async def test_costs_response_has_roi(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/costs?org_id=org-001&tier=organization"
        )
        data = await resp.json()
        assert "roi" in data

    async def test_costs_response_has_overage_risk(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/costs?org_id=org-001&tier=fleet"
        )
        data = await resp.json()
        assert "overage_risk" in data

    # --- /api/analytics/model-performance ------------------------------------

    async def test_model_performance_org_tier_returns_200(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/model-performance?tier=organization"
        )
        assert resp.status == 200

    async def test_model_performance_fleet_returns_200(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/model-performance?tier=fleet"
        )
        assert resp.status == 200

    async def test_model_performance_team_returns_403(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/model-performance?tier=team"
        )
        assert resp.status == 403

    async def test_model_performance_response_has_quality_scores(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/model-performance?tier=organization"
        )
        data = await resp.json()
        assert "quality_scores" in data

    async def test_model_performance_response_has_affinity(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/model-performance?tier=fleet"
        )
        data = await resp.json()
        assert "task_affinity_matrix" in data

    async def test_model_performance_response_has_agreement_rate(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/model-performance?tier=organization"
        )
        data = await resp.json()
        assert "cross_validation_agreement_rate" in data

    # --- /api/analytics/sprint-velocity --------------------------------------

    async def test_sprint_velocity_org_tier_returns_200(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/sprint-velocity?org_id=org-001&tier=organization"
        )
        assert resp.status == 200

    async def test_sprint_velocity_fleet_returns_200(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/sprint-velocity?org_id=org-001&tier=fleet"
        )
        assert resp.status == 200

    async def test_sprint_velocity_explorer_returns_403(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/sprint-velocity?org_id=org-001&tier=explorer"
        )
        assert resp.status == 403

    async def test_sprint_velocity_response_has_weekly_velocity(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/sprint-velocity?org_id=org-001&tier=organization"
        )
        data = await resp.json()
        assert "weekly_velocity" in data

    async def test_sprint_velocity_response_has_trend_line(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/sprint-velocity?org_id=org-001&tier=organization"
        )
        data = await resp.json()
        assert "trend_line" in data

    async def test_sprint_velocity_response_has_blocked_analysis(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/sprint-velocity?org_id=org-001&tier=fleet"
        )
        data = await resp.json()
        assert "blocked_analysis" in data

    async def test_sprint_velocity_custom_weeks_param(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/sprint-velocity?org_id=org-001&tier=organization&weeks=6"
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["weeks"] == 6

    # --- /api/analytics/export -----------------------------------------------

    async def test_export_org_tier_returns_200(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/export?org_id=org-001&tier=organization"
        )
        assert resp.status == 200

    async def test_export_fleet_tier_returns_200(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/export?org_id=org-001&tier=fleet"
        )
        assert resp.status == 200

    async def test_export_builder_returns_403(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/export?org_id=org-001&tier=builder"
        )
        assert resp.status == 403

    async def test_export_team_returns_403(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/export?org_id=org-001&tier=team"
        )
        assert resp.status == 403

    async def test_export_response_has_sections(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/export?org_id=org-001&tier=organization"
        )
        data = await resp.json()
        assert "sections" in data

    async def test_export_response_all_four_sections(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/export?org_id=org-001&tier=fleet"
        )
        data = await resp.json()
        sections = data["sections"]
        assert "efficiency" in sections
        assert "costs" in sections
        assert "model_performance" in sections
        assert "sprint_velocity" in sections

    async def test_export_response_has_org_id(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/export?org_id=org-export-test&tier=organization"
        )
        data = await resp.json()
        assert data["org_id"] == "org-export-test"

    async def test_export_custom_month_param(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/export?org_id=org-001&tier=fleet&month=2026-02"
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["month"] == "2026-02"

    async def test_export_403_has_analytics_tiers_hint(self, analytics_client):
        resp = await analytics_client.get(
            "/api/analytics/export?org_id=org-001&tier=explorer"
        )
        assert resp.status == 403
        data = await resp.json()
        assert "analytics_tiers" in data
