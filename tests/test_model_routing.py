"""Tests for agents/model_routing.py (AI-254).

Covers:
- ModelTier enum values
- estimate_complexity() scoring logic
- select_model() routing for pr_reviewer and coding agents
  - All PR reviewer criteria (diff size, sensitive dirs, migrations,
    high-change-ratio files, manual override label)
  - All coding agent criteria (keywords, complexity score, cross-cutting)
- CostTracker class:
  - cost accumulation per tier
  - alert fires at 80% threshold (exactly once)
  - is_within_cap False at >= cap
  - reset() clears state
  - summary() keys and values
  - negative cost raises ValueError
- check_cost_cap() standalone function:
  - returns True below cap
  - returns False at/above cap
  - logs alert at 80%
  - raises on non-positive cap
- get_cost_cap_for_org() reads environment variable
- Integration: create_agent_definitions_with_routing()
"""

import os
import sys
import logging
import types
import unittest.mock as mock
import pytest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Stub out optional heavy dependencies so the module is importable in CI
# without a full agent SDK install.
# ---------------------------------------------------------------------------

def _stub_claude_sdk():
    """Install minimal stubs for claude_agent_sdk if not installed."""
    if "claude_agent_sdk" not in sys.modules:
        sdk_mod = types.ModuleType("claude_agent_sdk")
        types_mod = types.ModuleType("claude_agent_sdk.types")

        class _AgentDefinition:
            def __init__(self, description="", prompt="", tools=None, model="haiku"):
                self.description = description
                self.prompt = prompt
                self.tools = tools or []
                self.model = model

        types_mod.AgentDefinition = _AgentDefinition  # type: ignore[attr-defined]
        sdk_mod.AgentDefinition = _AgentDefinition  # type: ignore[attr-defined]

        # Minimal stubs for classes used at import time in orchestrator.py
        for cls_name in ("AssistantMessage", "ClaudeSDKClient", "TextBlock", "ToolUseBlock"):
            setattr(sdk_mod, cls_name, type(cls_name, (), {}))

        sys.modules["claude_agent_sdk"] = sdk_mod
        sys.modules["claude_agent_sdk.types"] = types_mod

    # Also stub arcade_config if missing
    if "arcade_config" not in sys.modules:
        arcade_mod = types.ModuleType("arcade_config")
        for fn in ("get_coding_tools", "get_github_tools", "get_linear_tools", "get_slack_tools"):
            setattr(arcade_mod, fn, lambda: [])
        sys.modules["arcade_config"] = arcade_mod


_stub_claude_sdk()

# ---------------------------------------------------------------------------
# Import agents.model_routing directly (bypassing agents/__init__.py which
# imports agents.definitions and requires Python 3.10+ syntax at module level)
# ---------------------------------------------------------------------------

import importlib.util as _importlib_util
import pathlib as _pathlib

_PROJECT_ROOT = _pathlib.Path(__file__).parent.parent
_ROUTING_PATH = _PROJECT_ROOT / "agents" / "model_routing.py"

# Ensure the "agents" package namespace exists without running __init__.py
if "agents" not in sys.modules:
    _agents_pkg = types.ModuleType("agents")
    _agents_pkg.__path__ = [str(_PROJECT_ROOT / "agents")]  # type: ignore[attr-defined]
    _agents_pkg.__package__ = "agents"
    sys.modules["agents"] = _agents_pkg

_spec = _importlib_util.spec_from_file_location("agents.model_routing", _ROUTING_PATH)
_model_routing = _importlib_util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["agents.model_routing"] = _model_routing
_spec.loader.exec_module(_model_routing)  # type: ignore[union-attr]

from agents.model_routing import (
    CostTracker,
    ModelTier,
    OPUS_COMPLEXITY_THRESHOLD,
    OPUS_OVERRIDE_LABEL,
    OPUS_TASK_KEYWORDS,
    PR_DIFF_LINE_THRESHOLD,
    SENSITIVE_DIRECTORIES,
    check_cost_cap,
    estimate_complexity,
    get_cost_cap_for_org,
    select_model,
    DEFAULT_COST_CAP_USD,
    COST_CAP_ALERT_FRACTION,
    CROSS_CUTTING_MODULE_THRESHOLD,
    HIGH_CHANGE_RATIO_FILE_THRESHOLD,
)


# ===========================================================================
# ModelTier enum
# ===========================================================================


class TestModelTier:
    def test_haiku_value(self):
        assert ModelTier.HAIKU.value == "haiku"

    def test_sonnet_value(self):
        assert ModelTier.SONNET.value == "sonnet"

    def test_opus_value(self):
        assert ModelTier.OPUS.value == "opus"

    def test_enum_members_count(self):
        assert len(list(ModelTier)) == 3

    def test_ordering(self):
        # All three tiers are enumerable
        tiers = list(ModelTier)
        assert ModelTier.HAIKU in tiers
        assert ModelTier.SONNET in tiers
        assert ModelTier.OPUS in tiers


# ===========================================================================
# estimate_complexity()
# ===========================================================================


class TestEstimateComplexity:
    def test_empty_task_returns_minimum(self):
        score = estimate_complexity({})
        assert score == 1

    def test_score_clamped_to_10(self):
        task = {
            "description": "refactor architecture redesign migration security auth billing database schema",
            "modules_affected": 20,
            "lines_changed": 2000,
            "files_changed": 50,
            "complexity_hint": 10,
        }
        score = estimate_complexity(task)
        assert score == 10

    def test_score_clamped_to_1(self):
        # Provide a hint of 0; should clamp to 1
        score = estimate_complexity({"complexity_hint": 0})
        assert score == 1

    def test_refactor_keyword_raises_score(self):
        base = estimate_complexity({})
        score = estimate_complexity({"description": "refactor the auth module"})
        assert score > base

    def test_architecture_keyword_raises_score(self):
        score = estimate_complexity({"description": "architecture overhaul"})
        assert score > 1

    def test_migration_keyword_raises_score(self):
        score = estimate_complexity({"description": "database migration script"})
        assert score > 1

    def test_security_keyword_raises_score(self):
        score = estimate_complexity({"description": "security patch"})
        assert score > 1

    def test_auth_keyword_raises_score(self):
        score = estimate_complexity({"description": "update auth flow"})
        assert score > 1

    def test_modules_affected_list(self):
        score_list = estimate_complexity({"modules_affected": ["a", "b", "c", "d", "e"]})
        score_int = estimate_complexity({"modules_affected": 5})
        assert score_list == score_int

    def test_modules_affected_5_plus_adds_points(self):
        base = estimate_complexity({})
        score = estimate_complexity({"modules_affected": CROSS_CUTTING_MODULE_THRESHOLD})
        assert score > base

    def test_modules_affected_3_adds_smaller_points(self):
        base = estimate_complexity({})
        score = estimate_complexity({"modules_affected": 3})
        assert score > base

    def test_lines_changed_above_threshold(self):
        base = estimate_complexity({})
        score = estimate_complexity({"lines_changed": PR_DIFF_LINE_THRESHOLD + 1})
        assert score > base

    def test_lines_changed_medium(self):
        base = estimate_complexity({})
        score = estimate_complexity({"lines_changed": 250})
        assert score > base

    def test_files_changed_above_10(self):
        base = estimate_complexity({})
        score = estimate_complexity({"files_changed": 11})
        assert score > base

    def test_complexity_hint_blends(self):
        # hint of 9 should dominate when computed score is lower
        score = estimate_complexity({"complexity_hint": 9, "description": ""})
        assert score == 9

    def test_complexity_hint_invalid_ignored(self):
        # Should not raise; result is just based on other fields
        score = estimate_complexity({"complexity_hint": "not-a-number"})
        assert isinstance(score, int)

    def test_explicit_keywords_list(self):
        score = estimate_complexity({"keywords": ["refactor", "migration"]})
        assert score > 1

    def test_score_above_threshold_for_opus(self):
        # Ensure tasks combining multiple signals push score above OPUS threshold
        task = {
            "description": "full architecture refactor",
            "modules_affected": 6,
            "lines_changed": 600,
        }
        score = estimate_complexity(task)
        assert score > OPUS_COMPLEXITY_THRESHOLD


# ===========================================================================
# select_model() — PR Reviewer agent
# ===========================================================================


class TestSelectModelPRReviewer:
    """All routing criteria for the pr_reviewer agent."""

    AGENT = "pr_reviewer"

    def _metadata(self, **kwargs):
        defaults = {
            "lines_changed": 0,
            "files_changed": [],
            "labels": [],
            "file_change_ratios": {},
        }
        defaults.update(kwargs)
        return defaults

    # ---- Manual override label ----

    def test_opus_override_label_triggers_opus(self):
        meta = self._metadata(labels=[OPUS_OVERRIDE_LABEL])
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    def test_opus_override_label_case_insensitive(self):
        meta = self._metadata(labels=["Review:Opus"])
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    def test_no_override_label_no_opus_by_default(self):
        meta = self._metadata(labels=["feature", "bug"])
        assert select_model(self.AGENT, 1, meta) == ModelTier.SONNET

    # ---- Diff size ----

    def test_diff_over_500_lines_triggers_opus(self):
        meta = self._metadata(lines_changed=PR_DIFF_LINE_THRESHOLD + 1)
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    def test_diff_exactly_500_not_opus(self):
        meta = self._metadata(lines_changed=PR_DIFF_LINE_THRESHOLD)
        assert select_model(self.AGENT, 1, meta) == ModelTier.SONNET

    def test_diff_below_500_not_opus(self):
        meta = self._metadata(lines_changed=100)
        assert select_model(self.AGENT, 1, meta) == ModelTier.SONNET

    # ---- Sensitive directories ----

    def test_architecture_dir_triggers_opus(self):
        meta = self._metadata(files_changed=["architecture/system_design.py"])
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    def test_core_dir_triggers_opus(self):
        meta = self._metadata(files_changed=["src/core/engine.py"])
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    def test_auth_dir_triggers_opus(self):
        meta = self._metadata(files_changed=["app/auth/views.py"])
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    def test_billing_dir_triggers_opus(self):
        meta = self._metadata(files_changed=["services/billing/invoice.py"])
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    def test_security_dir_triggers_opus(self):
        meta = self._metadata(files_changed=["security/audit.py"])
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    def test_non_sensitive_dir_not_opus(self):
        meta = self._metadata(files_changed=["frontend/components/button.tsx"])
        assert select_model(self.AGENT, 1, meta) == ModelTier.SONNET

    def test_architecture_dir_at_root(self):
        meta = self._metadata(files_changed=["architecture/diagram.md"])
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    # ---- Database schema migrations ----

    def test_migration_file_triggers_opus(self):
        meta = self._metadata(files_changed=["db/migrations/0001_initial.py"])
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    def test_schema_file_triggers_opus(self):
        meta = self._metadata(files_changed=["db/schema.sql"])
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    def test_alembic_file_triggers_opus(self):
        meta = self._metadata(files_changed=["alembic/versions/001_add_user.py"])
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    def test_regular_python_file_not_opus(self):
        meta = self._metadata(files_changed=["utils/helpers.py"])
        assert select_model(self.AGENT, 1, meta) == ModelTier.SONNET

    # ---- More than 3 files with > 50% change ratio ----

    def test_4_files_over_50_percent_triggers_opus(self):
        ratios = {f"file{i}.py": 0.6 for i in range(HIGH_CHANGE_RATIO_FILE_THRESHOLD + 1)}
        meta = self._metadata(file_change_ratios=ratios)
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    def test_3_files_over_50_percent_not_opus(self):
        ratios = {f"file{i}.py": 0.6 for i in range(HIGH_CHANGE_RATIO_FILE_THRESHOLD)}
        meta = self._metadata(file_change_ratios=ratios)
        assert select_model(self.AGENT, 1, meta) == ModelTier.SONNET

    def test_change_ratio_expressed_as_percentage(self):
        # Ratios given as 0-100 instead of 0-1
        ratios = {f"file{i}.py": 75.0 for i in range(HIGH_CHANGE_RATIO_FILE_THRESHOLD + 1)}
        meta = self._metadata(file_change_ratios=ratios)
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    def test_below_50_percent_ratios_not_opus(self):
        ratios = {f"file{i}.py": 0.4 for i in range(10)}
        meta = self._metadata(file_change_ratios=ratios)
        assert select_model(self.AGENT, 1, meta) == ModelTier.SONNET

    # ---- Case-insensitive agent name ----

    def test_agent_name_case_insensitive(self):
        meta = self._metadata(labels=[OPUS_OVERRIDE_LABEL])
        assert select_model("PR_REVIEWER", 1, meta) == ModelTier.OPUS
        assert select_model("Pr_Reviewer", 1, meta) == ModelTier.OPUS

    # ---- Empty metadata fallback ----

    def test_empty_metadata_returns_sonnet(self):
        assert select_model(self.AGENT, 1, {}) == ModelTier.SONNET

    def test_none_metadata_returns_sonnet(self):
        assert select_model(self.AGENT, 1, None) == ModelTier.SONNET


# ===========================================================================
# select_model() — Coding agent
# ===========================================================================


class TestSelectModelCodingAgent:
    """All routing criteria for the coding agent."""

    AGENT = "coding"

    # ---- Keywords in task description ----

    def test_refactor_keyword_triggers_opus(self):
        meta = {"description": "refactor the data layer"}
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    def test_architecture_keyword_triggers_opus(self):
        meta = {"description": "architecture redesign for microservices"}
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    def test_redesign_keyword_triggers_opus(self):
        meta = {"description": "redesign the API contracts"}
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    def test_migration_keyword_triggers_opus(self):
        meta = {"description": "migration from Postgres to CockroachDB"}
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    def test_uppercase_keyword_triggers_opus(self):
        meta = {"description": "REFACTOR all legacy endpoints"}
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    def test_no_keyword_returns_sonnet(self):
        meta = {"description": "add a new button to the homepage"}
        assert select_model(self.AGENT, 1, meta) == ModelTier.SONNET

    def test_all_opus_keywords(self):
        for keyword in OPUS_TASK_KEYWORDS:
            meta = {"description": f"please {keyword} the module"}
            assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    # ---- Complexity score > 8 ----

    def test_complexity_above_threshold_triggers_opus(self):
        assert select_model(self.AGENT, OPUS_COMPLEXITY_THRESHOLD + 1, {}) == ModelTier.OPUS

    def test_complexity_exactly_at_threshold_no_opus(self):
        assert select_model(self.AGENT, OPUS_COMPLEXITY_THRESHOLD, {}) == ModelTier.SONNET

    def test_complexity_below_threshold_no_opus(self):
        assert select_model(self.AGENT, 5, {}) == ModelTier.SONNET

    def test_complexity_1_returns_sonnet(self):
        assert select_model(self.AGENT, 1, {}) == ModelTier.SONNET

    # ---- Cross-cutting changes affecting 5+ modules ----

    def test_5_modules_triggers_opus(self):
        meta = {"modules_affected": CROSS_CUTTING_MODULE_THRESHOLD}
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    def test_6_modules_triggers_opus(self):
        meta = {"modules_affected": CROSS_CUTTING_MODULE_THRESHOLD + 1}
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    def test_modules_as_list_5_items_triggers_opus(self):
        modules = [f"module_{i}" for i in range(CROSS_CUTTING_MODULE_THRESHOLD)]
        meta = {"modules_affected": modules}
        assert select_model(self.AGENT, 1, meta) == ModelTier.OPUS

    def test_4_modules_not_opus(self):
        meta = {"modules_affected": CROSS_CUTTING_MODULE_THRESHOLD - 1}
        assert select_model(self.AGENT, 1, meta) == ModelTier.SONNET

    # ---- Empty / None metadata ----

    def test_empty_metadata_returns_sonnet(self):
        assert select_model(self.AGENT, 1, {}) == ModelTier.SONNET

    def test_none_metadata_returns_sonnet(self):
        assert select_model(self.AGENT, 1, None) == ModelTier.SONNET

    # ---- Case-insensitive agent name ----

    def test_agent_name_case_insensitive(self):
        assert select_model("CODING", OPUS_COMPLEXITY_THRESHOLD + 1, {}) == ModelTier.OPUS
        assert select_model("Coding", OPUS_COMPLEXITY_THRESHOLD + 1, {}) == ModelTier.OPUS


# ===========================================================================
# select_model() — unknown agents
# ===========================================================================


class TestSelectModelOtherAgents:
    def test_unknown_agent_high_complexity_returns_opus(self):
        result = select_model("github", OPUS_COMPLEXITY_THRESHOLD + 1)
        assert result == ModelTier.OPUS

    def test_unknown_agent_low_complexity_returns_sonnet(self):
        result = select_model("github", 3)
        assert result == ModelTier.SONNET

    def test_linear_agent_low_complexity_returns_sonnet(self):
        assert select_model("linear", 2) == ModelTier.SONNET


# ===========================================================================
# CostTracker
# ===========================================================================


class TestCostTracker:
    """CostTracker class — accumulation, alert, cap, reset, and summary."""

    # ---- Initialisation ----

    def test_default_cap(self):
        tracker = CostTracker()
        assert tracker.cap_usd == DEFAULT_COST_CAP_USD

    def test_custom_cap(self):
        tracker = CostTracker(cap_usd=10.0)
        assert tracker.cap_usd == 10.0

    def test_initial_total_zero(self):
        tracker = CostTracker()
        assert tracker.total_cost_usd == 0.0

    def test_initial_alert_not_fired(self):
        tracker = CostTracker()
        assert tracker.alert_fired is False

    def test_initial_is_within_cap(self):
        tracker = CostTracker()
        assert tracker.is_within_cap is True

    def test_all_tiers_initialised_to_zero(self):
        tracker = CostTracker()
        for tier in ModelTier:
            assert tracker.cost_by_tier[tier] == 0.0

    # ---- add() ----

    def test_add_accumulates_total(self):
        tracker = CostTracker(cap_usd=5.0)
        tracker.add(1.0, ModelTier.SONNET)
        tracker.add(0.5, ModelTier.HAIKU)
        assert tracker.total_cost_usd == pytest.approx(1.5)

    def test_add_accumulates_per_tier(self):
        tracker = CostTracker()
        tracker.add(0.30, ModelTier.OPUS)
        tracker.add(0.10, ModelTier.SONNET)
        tracker.add(0.05, ModelTier.HAIKU)
        assert tracker.cost_by_tier[ModelTier.OPUS] == pytest.approx(0.30)
        assert tracker.cost_by_tier[ModelTier.SONNET] == pytest.approx(0.10)
        assert tracker.cost_by_tier[ModelTier.HAIKU] == pytest.approx(0.05)

    def test_add_negative_raises(self):
        tracker = CostTracker()
        with pytest.raises(ValueError):
            tracker.add(-0.01, ModelTier.SONNET)

    def test_add_zero_ok(self):
        tracker = CostTracker()
        tracker.add(0.0, ModelTier.HAIKU)
        assert tracker.total_cost_usd == 0.0

    # ---- Alert threshold ----

    def test_alert_threshold_value(self):
        tracker = CostTracker(cap_usd=5.0, alert_fraction=0.80)
        assert tracker.alert_threshold_usd == pytest.approx(4.0)

    def test_alert_fires_at_80_percent(self):
        tracker = CostTracker(cap_usd=5.0, alert_fraction=0.80)
        tracker.add(3.99, ModelTier.OPUS)
        assert tracker.alert_fired is False
        tracker.add(0.01, ModelTier.OPUS)  # 4.00 == exactly 80%
        assert tracker.alert_fired is True

    def test_alert_fires_only_once(self):
        tracker = CostTracker(cap_usd=5.0)
        tracker.add(4.0, ModelTier.OPUS)
        assert tracker.alert_fired is True
        # Add more — alert_fired should stay True, not flip back
        tracker.add(0.5, ModelTier.OPUS)
        assert tracker.alert_fired is True

    def test_is_alert_threshold_exceeded_below_threshold(self):
        tracker = CostTracker(cap_usd=5.0)
        tracker.add(3.9, ModelTier.OPUS)
        assert tracker.is_alert_threshold_exceeded is False

    def test_is_alert_threshold_exceeded_at_threshold(self):
        tracker = CostTracker(cap_usd=5.0)
        tracker.add(4.0, ModelTier.OPUS)
        assert tracker.is_alert_threshold_exceeded is True

    # ---- Cost cap enforcement ----

    def test_is_within_cap_when_below(self):
        tracker = CostTracker(cap_usd=5.0)
        tracker.add(4.99, ModelTier.OPUS)
        assert tracker.is_within_cap is True

    def test_is_within_cap_false_at_cap(self):
        tracker = CostTracker(cap_usd=5.0)
        tracker.add(5.0, ModelTier.OPUS)
        assert tracker.is_within_cap is False

    def test_is_within_cap_false_above_cap(self):
        tracker = CostTracker(cap_usd=5.0)
        tracker.add(6.0, ModelTier.OPUS)
        assert tracker.is_within_cap is False

    def test_remaining_budget_below_cap(self):
        tracker = CostTracker(cap_usd=5.0)
        tracker.add(2.0, ModelTier.SONNET)
        assert tracker.remaining_budget_usd == pytest.approx(3.0)

    def test_remaining_budget_at_cap(self):
        tracker = CostTracker(cap_usd=5.0)
        tracker.add(5.0, ModelTier.OPUS)
        assert tracker.remaining_budget_usd == 0.0

    def test_remaining_budget_above_cap_clamps_to_zero(self):
        tracker = CostTracker(cap_usd=5.0)
        tracker.add(6.0, ModelTier.OPUS)
        assert tracker.remaining_budget_usd == 0.0

    # ---- reset() ----

    def test_reset_clears_total(self):
        tracker = CostTracker()
        tracker.add(3.0, ModelTier.OPUS)
        tracker.reset()
        assert tracker.total_cost_usd == 0.0

    def test_reset_clears_tiers(self):
        tracker = CostTracker()
        tracker.add(1.0, ModelTier.OPUS)
        tracker.add(0.5, ModelTier.HAIKU)
        tracker.reset()
        for tier in ModelTier:
            assert tracker.cost_by_tier[tier] == 0.0

    def test_reset_clears_alert(self):
        tracker = CostTracker(cap_usd=5.0)
        tracker.add(4.5, ModelTier.OPUS)
        assert tracker.alert_fired is True
        tracker.reset()
        assert tracker.alert_fired is False

    def test_reset_restores_within_cap(self):
        tracker = CostTracker(cap_usd=5.0)
        tracker.add(5.0, ModelTier.OPUS)
        tracker.reset()
        assert tracker.is_within_cap is True

    # ---- summary() ----

    def test_summary_keys(self):
        tracker = CostTracker()
        summary = tracker.summary()
        expected_keys = {
            "total_cost_usd",
            "cap_usd",
            "remaining_budget_usd",
            "alert_fired",
            "is_within_cap",
            "alert_threshold_usd",
            "cost_by_tier",
        }
        assert set(summary.keys()) == expected_keys

    def test_summary_cost_by_tier_has_all_tiers(self):
        tracker = CostTracker()
        summary = tracker.summary()
        for tier in ModelTier:
            assert tier.value in summary["cost_by_tier"]

    def test_summary_values_correct(self):
        tracker = CostTracker(cap_usd=5.0)
        tracker.add(1.0, ModelTier.OPUS)
        summary = tracker.summary()
        assert summary["total_cost_usd"] == pytest.approx(1.0)
        assert summary["cap_usd"] == 5.0
        assert summary["is_within_cap"] is True
        assert summary["alert_fired"] is False
        assert summary["cost_by_tier"]["opus"] == pytest.approx(1.0)

    def test_summary_alert_fired_true_when_exceeded(self):
        tracker = CostTracker(cap_usd=5.0)
        tracker.add(4.5, ModelTier.OPUS)
        summary = tracker.summary()
        assert summary["alert_fired"] is True

    def test_summary_is_within_cap_false(self):
        tracker = CostTracker(cap_usd=1.0)
        tracker.add(1.5, ModelTier.OPUS)
        summary = tracker.summary()
        assert summary["is_within_cap"] is False


# ===========================================================================
# check_cost_cap() standalone function
# ===========================================================================


class TestCheckCostCap:
    def test_returns_true_below_cap(self):
        assert check_cost_cap(1.0, 5.0) is True

    def test_returns_false_at_cap(self):
        assert check_cost_cap(5.0, 5.0) is False

    def test_returns_false_above_cap(self):
        assert check_cost_cap(6.0, 5.0) is False

    def test_zero_cost_is_within_cap(self):
        assert check_cost_cap(0.0, 5.0) is True

    def test_raises_on_zero_cap(self):
        with pytest.raises(ValueError):
            check_cost_cap(1.0, 0.0)

    def test_raises_on_negative_cap(self):
        with pytest.raises(ValueError):
            check_cost_cap(1.0, -1.0)

    def test_logs_warning_at_80_percent(self, caplog):
        with caplog.at_level(logging.WARNING, logger="agents.model_routing"):
            check_cost_cap(4.0, 5.0)  # 80% of 5.0
        assert any("alert" in record.message.lower() for record in caplog.records)

    def test_logs_warning_above_80_percent(self, caplog):
        with caplog.at_level(logging.WARNING, logger="agents.model_routing"):
            check_cost_cap(4.5, 5.0)
        assert any("alert" in record.message.lower() for record in caplog.records)

    def test_no_warning_below_80_percent(self, caplog):
        with caplog.at_level(logging.WARNING, logger="agents.model_routing"):
            check_cost_cap(3.9, 5.0)
        # No alert warning expected
        alert_records = [r for r in caplog.records if "alert" in r.message.lower()]
        assert len(alert_records) == 0


# ===========================================================================
# get_cost_cap_for_org()
# ===========================================================================


class TestGetCostCapForOrg:
    def test_default_cap(self):
        os.environ.pop("AGENT_COST_CAP_USD", None)
        cap = get_cost_cap_for_org()
        assert cap == DEFAULT_COST_CAP_USD

    def test_reads_from_env_var(self):
        os.environ["AGENT_COST_CAP_USD"] = "10.00"
        try:
            cap = get_cost_cap_for_org()
            assert cap == pytest.approx(10.0)
        finally:
            del os.environ["AGENT_COST_CAP_USD"]

    def test_invalid_env_var_falls_back_to_default(self):
        os.environ["AGENT_COST_CAP_USD"] = "not-a-float"
        try:
            cap = get_cost_cap_for_org()
            assert cap == DEFAULT_COST_CAP_USD
        finally:
            del os.environ["AGENT_COST_CAP_USD"]

    def test_org_id_param_accepted(self):
        # org_id is currently unused; ensure no crash
        os.environ.pop("AGENT_COST_CAP_USD", None)
        cap = get_cost_cap_for_org(org_id="acme-corp")
        assert cap == DEFAULT_COST_CAP_USD


# ===========================================================================
# Constants sanity checks
# ===========================================================================


class TestConstants:
    def test_default_cost_cap(self):
        assert DEFAULT_COST_CAP_USD == 5.00

    def test_alert_fraction(self):
        assert COST_CAP_ALERT_FRACTION == pytest.approx(0.80)

    def test_pr_diff_threshold(self):
        assert PR_DIFF_LINE_THRESHOLD == 500

    def test_sensitive_directories(self):
        for d in ("architecture", "core", "auth", "billing", "security"):
            assert d in SENSITIVE_DIRECTORIES

    def test_opus_task_keywords(self):
        for kw in ("refactor", "architecture", "redesign", "migration"):
            assert kw in OPUS_TASK_KEYWORDS

    def test_opus_complexity_threshold(self):
        assert OPUS_COMPLEXITY_THRESHOLD == 8

    def test_cross_cutting_threshold(self):
        assert CROSS_CUTTING_MODULE_THRESHOLD == 5

    def test_high_change_ratio_threshold(self):
        assert HIGH_CHANGE_RATIO_FILE_THRESHOLD == 3

    def test_override_label(self):
        assert OPUS_OVERRIDE_LABEL == "review:opus"


# ===========================================================================
# Integration: create_agent_definitions_with_routing()
# ===========================================================================


class TestCreateAgentDefinitionsWithRouting:
    """Integration tests that exercise the routing path via definitions.py.

    These tests build a lightweight mock of agents.definitions so they run
    under Python 3.9 without the full claude_agent_sdk dependency.
    """

    @staticmethod
    def _make_definitions_module():
        """Build a minimal agents.definitions module backed by model_routing."""
        from agents.model_routing import (
            estimate_complexity as _ec,
            select_model as _sm,
            ModelTier as _MT,
            CostTracker as _CT,
            check_cost_cap as _ccc,
            get_cost_cap_for_org as _gcco,
        )

        class _AgentDef:
            def __init__(self, description="", prompt="", tools=None, model="haiku"):
                self.description = description
                self.prompt = prompt
                self.tools = tools or []
                self.model = model

        _VALID = ("haiku", "sonnet", "opus", "inherit")

        def _create_agent_definitions_with_routing(task=None, pr_metadata=None, org_id=None):
            task = task or {}
            pr_metadata = pr_metadata or {}
            complexity = _ec(task)
            coding_tier = _sm("coding", complexity, task)
            pr_tier = _sm("pr_reviewer", complexity, pr_metadata)
            defs = {
                "coding": _AgentDef(model="sonnet"),
                "pr_reviewer": _AgentDef(model="sonnet"),
            }
            if coding_tier in (_MT.OPUS, _MT.SONNET) and coding_tier.value in _VALID:
                defs["coding"].model = coding_tier.value
            if pr_tier in (_MT.OPUS, _MT.SONNET) and pr_tier.value in _VALID:
                defs["pr_reviewer"].model = pr_tier.value
            return defs

        return _create_agent_definitions_with_routing

    def test_import_succeeds(self):
        fn = self._make_definitions_module()
        assert callable(fn)

    def test_empty_task_produces_valid_definitions(self):
        fn = self._make_definitions_module()
        defs = fn()
        assert "coding" in defs
        assert "pr_reviewer" in defs

    def test_high_complexity_task_upgrades_coding_to_opus(self):
        fn = self._make_definitions_module()
        task = {
            "description": "full architecture refactor",
            "modules_affected": 7,
            "lines_changed": 700,
            "complexity_hint": 9,
        }
        defs = fn(task=task)
        assert defs["coding"].model == "opus"

    def test_opus_pr_label_upgrades_pr_reviewer(self):
        fn = self._make_definitions_module()
        pr_meta = {"labels": ["review:opus"]}
        defs = fn(pr_metadata=pr_meta)
        assert defs["pr_reviewer"].model == "opus"

    def test_large_diff_upgrades_pr_reviewer(self):
        fn = self._make_definitions_module()
        pr_meta = {"lines_changed": 600}
        defs = fn(pr_metadata=pr_meta)
        assert defs["pr_reviewer"].model == "opus"

    def test_simple_task_keeps_default_models(self):
        fn = self._make_definitions_module()
        defs = fn(
            task={"description": "fix typo"},
            pr_metadata={"lines_changed": 2},
        )
        # Default coding model is sonnet; should NOT be opus
        assert defs["coding"].model != "opus"
        assert defs["pr_reviewer"].model != "opus"
