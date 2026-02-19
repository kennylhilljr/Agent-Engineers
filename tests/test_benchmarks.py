"""Comprehensive tests for the AI-248 benchmark suite.

Covers:
- SpeedMetrics, QualityMetrics, CostMetrics data models
- BenchmarkRunner: collect_* methods and check_regression
- BenchmarkStorage: save / retrieve / cleanup
- BenchmarkAlerter: check_latency_regression / check_and_alert
- GitHubReporter: format_benchmark_comment
- REST endpoints: GET /api/benchmarks and GET /api/benchmarks/regression-alerts
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is importable
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from benchmarks.alerts import BenchmarkAlerter
from benchmarks.github_reporter import GitHubReporter
from benchmarks.runner import (
    BenchmarkResult,
    BenchmarkRunner,
    CostMetrics,
    QualityMetrics,
    SpeedMetrics,
    _percentile,
)
from benchmarks.storage import BenchmarkStorage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_data(**overrides) -> Dict[str, Any]:
    """Return a minimal run_data dict suitable for BenchmarkRunner."""
    base = {
        "latency_samples": [0.5, 1.0, 1.5, 2.0, 3.0, 0.8, 0.9, 1.2, 1.8, 4.0],
        "task_durations": [60.0, 120.0, 90.0],
        "ticket_to_pr_seconds": 7200.0,
        "prs_approved_first_review": 8,
        "prs_total": 10,
        "test_coverage_before": 75.0,
        "test_coverage_after": 80.0,
        "defects_found": 2,
        "lines_changed": 400,
        "total_cost_usd": 2.00,
        "agent_hours": 4.0,
        "tickets_completed": 2,
        "haiku_requests": 100,
        "sonnet_requests": 50,
        "opus_requests": 10,
    }
    base.update(overrides)
    return base


def _make_result(agent_type: str = "engineer", regression: bool = False, days_ago: float = 0.0) -> BenchmarkResult:
    """Create a BenchmarkResult with optional timestamp offset."""
    ts = datetime.now(timezone.utc) - timedelta(days=days_ago)
    result = BenchmarkResult(
        agent_type=agent_type,
        speed=SpeedMetrics(p95_latency=2.0, p50_latency=1.0, p99_latency=3.0, avg_task_completion_time=90.0, ticket_to_pr_time=7200.0),
        quality=QualityMetrics(pr_approval_rate=0.8, test_coverage_delta=5.0, defect_density=0.5),
        cost=CostMetrics(cost_per_agent_hour=0.5, cost_per_ticket=1.0, haiku_utilization=0.625, sonnet_utilization=0.3125, opus_utilization=0.0625),
        regression_detected=regression,
        timestamp=ts.isoformat(),
    )
    return result


# ===========================================================================
# _percentile helper
# ===========================================================================


class TestPercentileHelper:
    def test_empty_list_returns_zero(self):
        assert _percentile([], 95) == 0.0

    def test_single_element(self):
        assert _percentile([5.0], 95) == 5.0

    def test_p50_of_sorted_list(self):
        values = list(range(1, 101))  # 1..100
        result = _percentile(values, 50)
        assert abs(result - 50.0) < 1.5  # approximate due to interpolation

    def test_p95_above_p50(self):
        values = list(range(1, 101))
        assert _percentile(values, 95) > _percentile(values, 50)

    def test_p99_is_near_max(self):
        values = list(range(1, 101))
        assert _percentile(values, 99) >= 98.0


# ===========================================================================
# SpeedMetrics
# ===========================================================================


class TestSpeedMetrics:
    def test_defaults_are_zero(self):
        m = SpeedMetrics()
        assert m.avg_task_completion_time == 0.0
        assert m.p50_latency == 0.0
        assert m.p95_latency == 0.0
        assert m.p99_latency == 0.0
        assert m.ticket_to_pr_time == 0.0

    def test_to_dict_has_all_keys(self):
        m = SpeedMetrics(p95_latency=1.5)
        d = m.to_dict()
        assert set(d.keys()) == {
            "avg_task_completion_time",
            "p50_latency",
            "p95_latency",
            "p99_latency",
            "ticket_to_pr_time",
        }
        assert d["p95_latency"] == 1.5

    def test_from_dict_round_trips(self):
        original = SpeedMetrics(avg_task_completion_time=120.0, p95_latency=2.5)
        restored = SpeedMetrics.from_dict(original.to_dict())
        assert restored.avg_task_completion_time == 120.0
        assert restored.p95_latency == 2.5

    def test_from_dict_with_empty_dict_returns_defaults(self):
        m = SpeedMetrics.from_dict({})
        assert m.p95_latency == 0.0


# ===========================================================================
# QualityMetrics
# ===========================================================================


class TestQualityMetrics:
    def test_defaults_are_zero(self):
        m = QualityMetrics()
        assert m.pr_approval_rate == 0.0
        assert m.test_coverage_delta == 0.0
        assert m.defect_density == 0.0

    def test_to_dict_has_all_keys(self):
        m = QualityMetrics(pr_approval_rate=0.9)
        d = m.to_dict()
        assert "pr_approval_rate" in d
        assert "test_coverage_delta" in d
        assert "defect_density" in d

    def test_from_dict_round_trips(self):
        original = QualityMetrics(pr_approval_rate=0.85, test_coverage_delta=3.0, defect_density=0.25)
        restored = QualityMetrics.from_dict(original.to_dict())
        assert restored.pr_approval_rate == pytest.approx(0.85)
        assert restored.test_coverage_delta == pytest.approx(3.0)

    def test_from_dict_empty(self):
        m = QualityMetrics.from_dict({})
        assert m.pr_approval_rate == 0.0


# ===========================================================================
# CostMetrics
# ===========================================================================


class TestCostMetrics:
    def test_defaults_are_zero(self):
        m = CostMetrics()
        for attr in ("cost_per_agent_hour", "cost_per_ticket",
                     "haiku_utilization", "sonnet_utilization", "opus_utilization"):
            assert getattr(m, attr) == 0.0

    def test_to_dict_keys(self):
        m = CostMetrics(cost_per_agent_hour=1.23)
        d = m.to_dict()
        assert "cost_per_agent_hour" in d
        assert "haiku_utilization" in d

    def test_from_dict_round_trips(self):
        original = CostMetrics(
            cost_per_agent_hour=0.75,
            cost_per_ticket=2.50,
            haiku_utilization=0.6,
            sonnet_utilization=0.3,
            opus_utilization=0.1,
        )
        restored = CostMetrics.from_dict(original.to_dict())
        assert restored.cost_per_agent_hour == pytest.approx(0.75)
        assert restored.haiku_utilization == pytest.approx(0.6)


# ===========================================================================
# BenchmarkResult
# ===========================================================================


class TestBenchmarkResult:
    def test_auto_generated_run_id(self):
        r = BenchmarkResult(agent_type="engineer")
        assert r.run_id  # non-empty
        r2 = BenchmarkResult(agent_type="engineer")
        assert r.run_id != r2.run_id  # unique

    def test_to_dict_has_required_keys(self):
        r = BenchmarkResult(agent_type="designer")
        d = r.to_dict()
        for key in ("run_id", "agent_type", "timestamp", "speed", "quality", "cost",
                    "regression_detected", "metadata"):
            assert key in d, f"Missing key: {key}"

    def test_from_dict_round_trips(self):
        r = _make_result("engineer")
        restored = BenchmarkResult.from_dict(r.to_dict())
        assert restored.agent_type == "engineer"
        assert restored.run_id == r.run_id
        assert restored.speed.p95_latency == pytest.approx(r.speed.p95_latency)

    def test_metadata_preserved(self):
        r = BenchmarkResult(agent_type="test", metadata={"pr": 42, "sha": "abc"})
        d = r.to_dict()
        assert d["metadata"]["pr"] == 42


# ===========================================================================
# BenchmarkRunner — collect_speed_metrics
# ===========================================================================


class TestBenchmarkRunnerSpeedMetrics:
    def setup_method(self):
        self.runner = BenchmarkRunner()

    def test_basic_speed_metrics(self):
        run_data = _make_run_data()
        metrics = self.runner.collect_speed_metrics("engineer", run_data)
        assert isinstance(metrics, SpeedMetrics)
        assert metrics.avg_task_completion_time == pytest.approx(90.0)
        assert metrics.p95_latency > metrics.p50_latency
        assert metrics.ticket_to_pr_time == 7200.0

    def test_empty_latency_samples(self):
        run_data = _make_run_data(latency_samples=[], task_durations=[])
        metrics = self.runner.collect_speed_metrics("engineer", run_data)
        assert metrics.p95_latency == 0.0
        assert metrics.avg_task_completion_time == 0.0

    def test_single_latency_sample(self):
        run_data = _make_run_data(latency_samples=[1.5], task_durations=[100.0])
        metrics = self.runner.collect_speed_metrics("engineer", run_data)
        assert metrics.p50_latency == pytest.approx(1.5)
        assert metrics.p95_latency == pytest.approx(1.5)
        assert metrics.p99_latency == pytest.approx(1.5)
        assert metrics.avg_task_completion_time == pytest.approx(100.0)

    def test_p99_gte_p95_gte_p50(self):
        run_data = _make_run_data()
        m = self.runner.collect_speed_metrics("engineer", run_data)
        assert m.p99_latency >= m.p95_latency >= m.p50_latency


# ===========================================================================
# BenchmarkRunner — collect_quality_metrics
# ===========================================================================


class TestBenchmarkRunnerQualityMetrics:
    def setup_method(self):
        self.runner = BenchmarkRunner()

    def test_approval_rate_calculation(self):
        run_data = _make_run_data(prs_approved_first_review=8, prs_total=10)
        m = self.runner.collect_quality_metrics("engineer", run_data)
        assert m.pr_approval_rate == pytest.approx(0.8)

    def test_coverage_delta_positive(self):
        run_data = _make_run_data(test_coverage_before=75.0, test_coverage_after=80.0)
        m = self.runner.collect_quality_metrics("engineer", run_data)
        assert m.test_coverage_delta == pytest.approx(5.0)

    def test_coverage_delta_negative(self):
        run_data = _make_run_data(test_coverage_before=80.0, test_coverage_after=75.0)
        m = self.runner.collect_quality_metrics("engineer", run_data)
        assert m.test_coverage_delta == pytest.approx(-5.0)

    def test_defect_density_calculation(self):
        run_data = _make_run_data(defects_found=2, lines_changed=400)
        m = self.runner.collect_quality_metrics("engineer", run_data)
        assert m.defect_density == pytest.approx(0.5)  # 2/400 * 100

    def test_zero_prs_total_does_not_divide_by_zero(self):
        run_data = _make_run_data(prs_approved_first_review=0, prs_total=0)
        m = self.runner.collect_quality_metrics("engineer", run_data)
        assert m.pr_approval_rate == 0.0

    def test_zero_lines_changed_does_not_divide_by_zero(self):
        run_data = _make_run_data(defects_found=5, lines_changed=0)
        m = self.runner.collect_quality_metrics("engineer", run_data)
        assert m.defect_density == 0.0


# ===========================================================================
# BenchmarkRunner — collect_cost_metrics
# ===========================================================================


class TestBenchmarkRunnerCostMetrics:
    def setup_method(self):
        self.runner = BenchmarkRunner()

    def test_cost_per_hour_calculation(self):
        run_data = _make_run_data(total_cost_usd=2.0, agent_hours=4.0)
        m = self.runner.collect_cost_metrics("engineer", run_data)
        assert m.cost_per_agent_hour == pytest.approx(0.5)

    def test_cost_per_ticket_calculation(self):
        run_data = _make_run_data(total_cost_usd=4.0, tickets_completed=2)
        m = self.runner.collect_cost_metrics("engineer", run_data)
        assert m.cost_per_ticket == pytest.approx(2.0)

    def test_model_tier_utilization_sums_to_one(self):
        run_data = _make_run_data(haiku_requests=60, sonnet_requests=30, opus_requests=10)
        m = self.runner.collect_cost_metrics("engineer", run_data)
        total = m.haiku_utilization + m.sonnet_utilization + m.opus_utilization
        assert total == pytest.approx(1.0)

    def test_zero_requests_gives_zero_utilization(self):
        run_data = _make_run_data(haiku_requests=0, sonnet_requests=0, opus_requests=0)
        m = self.runner.collect_cost_metrics("engineer", run_data)
        assert m.haiku_utilization == 0.0

    def test_zero_agent_hours_does_not_divide_by_zero(self):
        run_data = _make_run_data(total_cost_usd=1.0, agent_hours=0.0)
        m = self.runner.collect_cost_metrics("engineer", run_data)
        assert m.cost_per_agent_hour == 0.0


# ===========================================================================
# BenchmarkRunner — check_regression
# ===========================================================================


class TestBenchmarkRunnerCheckRegression:
    def setup_method(self):
        self.runner = BenchmarkRunner()

    def test_no_regression_when_within_threshold(self):
        # current is 5% above historical p95 — should not trigger
        historical = [1.0] * 100  # p95 = 1.0
        assert not self.runner.check_regression("p95_latency", 1.05, historical)

    def test_regression_detected_at_21_percent(self):
        historical = [1.0] * 100  # p95 = 1.0
        assert self.runner.check_regression("p95_latency", 1.21, historical)

    def test_regression_exactly_at_threshold_not_triggered(self):
        # Exactly 20% — threshold is strictly greater than, so no alert
        historical = [1.0] * 100  # p95 = 1.0
        assert not self.runner.check_regression("p95_latency", 1.20, historical)

    def test_empty_historical_no_regression(self):
        assert not self.runner.check_regression("p95_latency", 99.0, [])

    def test_zero_historical_p95_no_regression(self):
        # All zeros => p95 = 0 => cannot compute regression
        assert not self.runner.check_regression("p95_latency", 1.0, [0.0] * 50)

    def test_improvement_not_regression(self):
        # Current value is below historical p95
        historical = [2.0] * 50
        assert not self.runner.check_regression("p95_latency", 1.5, historical)

    def test_large_regression_detected(self):
        historical = [1.0] * 50  # p95 = 1.0
        assert self.runner.check_regression("p95_latency", 5.0, historical)


# ===========================================================================
# BenchmarkRunner — run_benchmark
# ===========================================================================


class TestBenchmarkRunnerRunBenchmark:
    def setup_method(self):
        self.runner = BenchmarkRunner()

    def test_returns_benchmark_result(self):
        result = self.runner.run_benchmark("engineer", _make_run_data())
        assert isinstance(result, BenchmarkResult)
        assert result.agent_type == "engineer"

    def test_regression_not_detected_without_historical(self):
        result = self.runner.run_benchmark("engineer", _make_run_data(), historical_p95=None)
        assert not result.regression_detected

    def test_regression_detected_with_low_historical_p95(self):
        # Historical p95 = 0.001s, current will be >> 0.001 * 1.2
        result = self.runner.run_benchmark("engineer", _make_run_data(), historical_p95=0.001)
        assert result.regression_detected

    def test_no_regression_with_matching_historical(self):
        # Make latencies all 1.0s so p95 ~= 1.0; give high historical_p95 so no regression
        run_data = _make_run_data(latency_samples=[1.0] * 100)
        result = self.runner.run_benchmark("engineer", run_data, historical_p95=100.0)
        assert not result.regression_detected

    def test_metadata_propagated(self):
        run_data = _make_run_data()
        run_data["metadata"] = {"commit": "abc123"}
        result = self.runner.run_benchmark("engineer", run_data)
        assert result.metadata["commit"] == "abc123"


# ===========================================================================
# BenchmarkStorage — save / retrieve
# ===========================================================================


class TestBenchmarkStorageSaveRetrieve:
    def setup_method(self):
        self.storage = BenchmarkStorage(retention_days=90)

    def test_save_and_retrieve(self):
        result = _make_result("engineer")
        self.storage.save_result(result)
        results = self.storage.get_results()
        assert len(results) == 1
        assert results[0].run_id == result.run_id

    def test_retrieve_newest_first(self):
        old = _make_result("engineer", days_ago=1.0)
        new = _make_result("engineer", days_ago=0.0)
        self.storage.save_result(old)
        self.storage.save_result(new)
        results = self.storage.get_results()
        assert results[0].run_id == new.run_id

    def test_agent_type_filter(self):
        self.storage.save_result(_make_result("engineer"))
        self.storage.save_result(_make_result("designer"))
        eng_results = self.storage.get_results(agent_type="engineer")
        assert all(r.agent_type == "engineer" for r in eng_results)
        assert len(eng_results) == 1

    def test_limit_respected(self):
        for _ in range(10):
            self.storage.save_result(_make_result("engineer"))
        results = self.storage.get_results(limit=5)
        assert len(results) == 5

    def test_empty_storage_returns_empty_list(self):
        assert self.storage.get_results() == []

    def test_duplicate_save_overwrites(self):
        r = _make_result("engineer")
        self.storage.save_result(r)
        self.storage.save_result(r)  # same run_id
        assert len(self.storage.get_results()) == 1


# ===========================================================================
# BenchmarkStorage — get_historical_p95
# ===========================================================================


class TestBenchmarkStorageHistoricalP95:
    def setup_method(self):
        self.storage = BenchmarkStorage(retention_days=90)

    def test_empty_storage_returns_zero(self):
        assert self.storage.get_historical_p95("p95_latency") == 0.0

    def test_returns_p95_of_stored_results(self):
        # Save 10 results with known p95_latency values
        for i in range(10):
            r = _make_result("engineer")
            r.speed.p95_latency = float(i + 1)
            self.storage.save_result(r)
        p95 = self.storage.get_historical_p95("p95_latency", days=7)
        assert p95 > 0

    def test_excludes_old_results(self):
        old = _make_result("engineer", days_ago=10.0)
        old.speed.p95_latency = 999.0
        self.storage.save_result(old)
        # Only look at 7-day window — old result should be excluded
        p95 = self.storage.get_historical_p95("p95_latency", days=7)
        assert p95 == 0.0  # old result excluded, nothing in window

    def test_agent_type_filter(self):
        eng = _make_result("engineer")
        eng.speed.p95_latency = 1.0
        des = _make_result("designer")
        des.speed.p95_latency = 100.0
        self.storage.save_result(eng)
        self.storage.save_result(des)
        p95_eng = self.storage.get_historical_p95("p95_latency", agent_type="engineer")
        assert p95_eng < 50.0  # Should not include designer's 100.0

    def test_unknown_metric_returns_zero(self):
        self.storage.save_result(_make_result("engineer"))
        assert self.storage.get_historical_p95("nonexistent_metric") == 0.0


# ===========================================================================
# BenchmarkStorage — cleanup_old_results
# ===========================================================================


class TestBenchmarkStorageCleanup:
    def test_cleanup_removes_old_results(self):
        storage = BenchmarkStorage(retention_days=90)
        old = _make_result("engineer", days_ago=100.0)
        recent = _make_result("engineer", days_ago=5.0)
        # Bypass save_result to avoid triggering auto-cleanup
        storage._results[old.run_id] = old
        storage._results[recent.run_id] = recent
        removed = storage.cleanup_old_results(days=90)
        assert removed == 1
        results = storage.get_results()
        assert len(results) == 1
        assert results[0].run_id == recent.run_id

    def test_cleanup_keeps_recent_results(self):
        storage = BenchmarkStorage(retention_days=90)
        for _ in range(5):
            r = _make_result("engineer", days_ago=1.0)
            storage._results[r.run_id] = r
        removed = storage.cleanup_old_results(days=90)
        assert removed == 0
        assert len(storage.get_results()) == 5

    def test_cleanup_returns_count(self):
        storage = BenchmarkStorage(retention_days=90)
        for _ in range(3):
            r = _make_result("engineer", days_ago=200.0)
            storage._results[r.run_id] = r
        removed = storage.cleanup_old_results(days=90)
        assert removed == 3

    def test_save_triggers_cleanup(self):
        """Saving a result should automatically clean up results older than retention_days."""
        storage = BenchmarkStorage(retention_days=30)
        old = _make_result("engineer", days_ago=45.0)
        storage._results[old.run_id] = old  # bypass cleanup in save
        # Now save a fresh result which should trigger cleanup
        storage.save_result(_make_result("engineer"))
        results = storage.get_results()
        ids = [r.run_id for r in results]
        assert old.run_id not in ids


# ===========================================================================
# BenchmarkAlerter
# ===========================================================================


class TestBenchmarkAlerter:
    def setup_method(self):
        self.alerter = BenchmarkAlerter(threshold=0.20)

    def test_no_regression_within_threshold(self):
        assert not self.alerter.check_latency_regression(1.15, 1.0)

    def test_regression_above_threshold(self):
        assert self.alerter.check_latency_regression(1.25, 1.0)

    def test_zero_historical_no_regression(self):
        assert not self.alerter.check_latency_regression(99.0, 0.0)

    def test_negative_historical_no_regression(self):
        assert not self.alerter.check_latency_regression(1.0, -1.0)

    def test_improvement_not_regression(self):
        assert not self.alerter.check_latency_regression(0.5, 1.0)

    def test_custom_threshold(self):
        alerter = BenchmarkAlerter(threshold=0.10)
        assert alerter.check_latency_regression(1.11, 1.0)
        assert not alerter.check_latency_regression(1.09, 1.0)

    def test_send_alert_logs_warning(self):
        with patch("benchmarks.alerts.logger") as mock_logger:
            self.alerter.send_alert("test alert")
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "test alert" in str(call_args)

    def test_check_and_alert_fires_when_regression(self):
        with patch.object(self.alerter, "send_alert") as mock_send:
            result = self.alerter.check_and_alert(2.0, 1.0, agent_type="engineer")
            assert result is True
            mock_send.assert_called_once()

    def test_check_and_alert_no_fire_when_ok(self):
        with patch.object(self.alerter, "send_alert") as mock_send:
            result = self.alerter.check_and_alert(1.1, 1.0, agent_type="engineer")
            assert result is False
            mock_send.assert_not_called()


# ===========================================================================
# GitHubReporter — format_benchmark_comment
# ===========================================================================


class TestGitHubReporterFormat:
    def setup_method(self):
        self.reporter = GitHubReporter()

    def test_comment_contains_agent_type(self):
        result = _make_result("engineer")
        comment = self.reporter.format_benchmark_comment(result)
        assert "engineer" in comment

    def test_comment_contains_run_id(self):
        result = _make_result("engineer")
        comment = self.reporter.format_benchmark_comment(result)
        assert result.run_id in comment

    def test_comment_contains_speed_metrics(self):
        result = _make_result("engineer")
        comment = self.reporter.format_benchmark_comment(result)
        assert "p95 latency" in comment.lower() or "p95" in comment
        assert "p50" in comment

    def test_comment_contains_quality_metrics(self):
        result = _make_result("engineer")
        comment = self.reporter.format_benchmark_comment(result)
        assert "approval" in comment.lower()
        assert "coverage" in comment.lower()

    def test_comment_contains_cost_metrics(self):
        result = _make_result("engineer")
        comment = self.reporter.format_benchmark_comment(result)
        assert "cost" in comment.lower()
        assert "haiku" in comment.lower()

    def test_regression_badge_shown_when_regression(self):
        result = _make_result("engineer", regression=True)
        comment = self.reporter.format_benchmark_comment(result)
        assert "REGRESSION" in comment

    def test_ok_badge_shown_when_no_regression(self):
        result = _make_result("engineer", regression=False)
        comment = self.reporter.format_benchmark_comment(result)
        assert "No regression" in comment

    def test_metadata_included_when_present(self):
        result = BenchmarkResult(agent_type="test", metadata={"sha": "abc123"})
        comment = self.reporter.format_benchmark_comment(result)
        assert "abc123" in comment

    def test_returns_string(self):
        result = _make_result()
        assert isinstance(self.reporter.format_benchmark_comment(result), str)


# ===========================================================================
# GitHubReporter — post_pr_comment
# ===========================================================================


class TestGitHubReporterPostComment:
    def setup_method(self):
        self.reporter = GitHubReporter()

    def test_returns_true_on_success(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("benchmarks.github_reporter.subprocess.run", return_value=mock_result):
            assert self.reporter.post_pr_comment(42, "test") is True

    def test_returns_false_on_nonzero_returncode(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "error"
        with patch("benchmarks.github_reporter.subprocess.run", return_value=mock_result):
            assert self.reporter.post_pr_comment(42, "test") is False

    def test_returns_false_when_gh_not_found(self):
        with patch("benchmarks.github_reporter.subprocess.run", side_effect=FileNotFoundError):
            assert self.reporter.post_pr_comment(42, "test") is False

    def test_returns_false_on_timeout(self):
        import subprocess
        with patch("benchmarks.github_reporter.subprocess.run", side_effect=subprocess.TimeoutExpired("gh", 30)):
            assert self.reporter.post_pr_comment(42, "test") is False

    def test_includes_repo_in_command(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("benchmarks.github_reporter.subprocess.run", return_value=mock_result) as mock_run:
            reporter = GitHubReporter(repo="owner/repo")
            reporter.post_pr_comment(42, "body")
            cmd = mock_run.call_args[0][0]
            assert "--repo" in cmd
            assert "owner/repo" in cmd

    def test_pr_number_in_command(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("benchmarks.github_reporter.subprocess.run", return_value=mock_result) as mock_run:
            self.reporter.post_pr_comment(99, "body")
            cmd = mock_run.call_args[0][0]
            assert "99" in cmd


# ===========================================================================
# REST API endpoints
# ===========================================================================


def _get_rest_module():
    """Import dashboard.rest_api_server with SSO mocked out to avoid SyntaxError on Python 3.9."""
    import sys
    import types

    # Pre-stub the sso package so the import of rest_api_server succeeds on Python 3.9
    for sso_mod in ("sso", "sso.saml_handler", "sso.oidc_handler",
                    "sso.organization_store", "sso.jit_provisioner", "sso.scim_handler"):
        if sso_mod not in sys.modules:
            sys.modules[sso_mod] = types.ModuleType(sso_mod)

    # Provide required symbols that rest_api_server conditionally imports
    for attr in ("SAMLHandler", "SAMLConfig", "SAMLError", "SAMLValidationError"):
        setattr(sys.modules["sso.saml_handler"], attr, MagicMock)
    for attr in ("OIDCHandler", "OIDCConfig", "OIDCError", "OIDCValidationError"):
        setattr(sys.modules["sso.oidc_handler"], attr, MagicMock)
    for attr in ("OrganizationStore", "PlanGatingError"):
        setattr(sys.modules["sso.organization_store"], attr, MagicMock)
    for attr in ("JITProvisioner", "JITError", "JITDomainError"):
        setattr(sys.modules["sso.jit_provisioner"], attr, MagicMock)
    for attr in ("SCIMHandler", "SCIMError", "SCIMAuthError", "SCIMNotFoundError"):
        setattr(sys.modules["sso.scim_handler"], attr, MagicMock)

    if "dashboard.rest_api_server" in sys.modules:
        return sys.modules["dashboard.rest_api_server"]
    import importlib
    return importlib.import_module("dashboard.rest_api_server")


class TestBenchmarksRESTEndpoints:
    """Test the /api/benchmarks and /api/benchmarks/regression-alerts endpoints.

    These tests exercise the handler logic by patching the module-level
    _get_benchmark_storage and _BENCHMARKS_AVAILABLE symbols that the
    RESTAPIServer methods rely on.
    """

    @pytest.fixture
    def populated_storage(self):
        """Return a BenchmarkStorage with a few results."""
        storage = BenchmarkStorage(retention_days=90)
        storage.save_result(_make_result("engineer", regression=False))
        storage.save_result(_make_result("designer", regression=True))
        storage.save_result(_make_result("engineer", regression=False))
        return storage

    @pytest.mark.asyncio
    async def test_get_benchmarks_returns_results(self, populated_storage):
        """Handler returns results from storage."""
        rest_module = _get_rest_module()

        # Build a minimal server instance without starting it
        server = rest_module.RESTAPIServer.__new__(rest_module.RESTAPIServer)

        mock_request = MagicMock()
        mock_request.rel_url.query.get = lambda k, d=None: d

        with patch.object(rest_module, "_BENCHMARKS_AVAILABLE", True), \
             patch.object(rest_module, "_get_benchmark_storage", return_value=populated_storage):
            response = await server.get_benchmarks(mock_request)

        assert response.status == 200
        data = json.loads(response.body)
        assert "benchmarks" in data
        assert data["count"] == len(data["benchmarks"])

    @pytest.mark.asyncio
    async def test_get_benchmarks_unavailable_returns_503(self):
        rest_module = _get_rest_module()

        server = rest_module.RESTAPIServer.__new__(rest_module.RESTAPIServer)
        mock_request = MagicMock()

        with patch.object(rest_module, "_BENCHMARKS_AVAILABLE", False):
            response = await server.get_benchmarks(mock_request)

        assert response.status == 503

    @pytest.mark.asyncio
    async def test_get_regression_alerts_returns_alerts(self, populated_storage):
        rest_module = _get_rest_module()

        server = rest_module.RESTAPIServer.__new__(rest_module.RESTAPIServer)
        mock_request = MagicMock()

        with patch.object(rest_module, "_BENCHMARKS_AVAILABLE", True), \
             patch.object(rest_module, "_get_benchmark_storage", return_value=populated_storage):
            response = await server.get_benchmark_regression_alerts(mock_request)

        assert response.status == 200
        data = json.loads(response.body)
        assert "alerts" in data
        # designer has regression=True so should appear in alerts
        agent_types = [a["agent_type"] for a in data["alerts"]]
        assert "designer" in agent_types

    @pytest.mark.asyncio
    async def test_get_regression_alerts_unavailable_returns_503(self):
        rest_module = _get_rest_module()

        server = rest_module.RESTAPIServer.__new__(rest_module.RESTAPIServer)
        mock_request = MagicMock()

        with patch.object(rest_module, "_BENCHMARKS_AVAILABLE", False):
            response = await server.get_benchmark_regression_alerts(mock_request)

        assert response.status == 503

    @pytest.mark.asyncio
    async def test_get_benchmarks_agent_type_filter(self, populated_storage):
        rest_module = _get_rest_module()

        server = rest_module.RESTAPIServer.__new__(rest_module.RESTAPIServer)
        mock_request = MagicMock()
        # Simulate ?agent_type=engineer
        mock_request.rel_url.query.get = lambda k, d=None: "engineer" if k == "agent_type" else d

        with patch.object(rest_module, "_BENCHMARKS_AVAILABLE", True), \
             patch.object(rest_module, "_get_benchmark_storage", return_value=populated_storage):
            response = await server.get_benchmarks(mock_request)

        assert response.status == 200
        data = json.loads(response.body)
        for bench in data["benchmarks"]:
            assert bench["agent_type"] == "engineer"

    @pytest.mark.asyncio
    async def test_get_benchmarks_limit_param(self, populated_storage):
        rest_module = _get_rest_module()

        server = rest_module.RESTAPIServer.__new__(rest_module.RESTAPIServer)
        mock_request = MagicMock()
        mock_request.rel_url.query.get = lambda k, d=None: "1" if k == "limit" else d

        with patch.object(rest_module, "_BENCHMARKS_AVAILABLE", True), \
             patch.object(rest_module, "_get_benchmark_storage", return_value=populated_storage):
            response = await server.get_benchmarks(mock_request)

        assert response.status == 200
        data = json.loads(response.body)
        assert data["count"] <= 1


# ===========================================================================
# scripts/run_benchmarks — CLI integration
# ===========================================================================


class TestRunBenchmarksCLI:
    def test_run_benchmark_pipeline_returns_dict(self):
        from scripts.run_benchmarks import run_benchmark_pipeline

        result = run_benchmark_pipeline("engineer", "abc12345")
        assert isinstance(result, dict)
        assert "agent_type" in result
        assert result["agent_type"] == "engineer"

    def test_run_benchmark_pipeline_writes_json(self, tmp_path):
        from scripts.run_benchmarks import run_benchmark_pipeline

        out = tmp_path / "result.json"
        run_benchmark_pipeline("engineer", "deadbeef", output_json=out)
        assert out.exists()
        with open(out) as f:
            data = json.load(f)
        assert "run_id" in data

    def test_main_no_post_comment(self, tmp_path):
        from scripts.run_benchmarks import main

        out = tmp_path / "result.json"
        main(["--agent-type", "engineer", "--commit-sha", "cafebabe", "--output-json", str(out)])
        assert out.exists()

    def test_main_post_comment_missing_args_raises(self):
        from scripts.run_benchmarks import main

        with pytest.raises(SystemExit):
            main(["--post-comment"])  # missing --pr-number and --result-json
