"""Benchmark runner for agent quality, speed, and cost metrics (AI-248).

BenchmarkRunner collects and analyzes performance data, checking for regressions
against historical baselines.
"""

from __future__ import annotations

import statistics
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class SpeedMetrics:
    """Speed performance metrics for an agent run.

    Attributes:
        avg_task_completion_time: Average time (seconds) to complete a task.
        p50_latency: 50th percentile latency in seconds.
        p95_latency: 95th percentile latency in seconds.
        p99_latency: 99th percentile latency in seconds.
        ticket_to_pr_time: Time in seconds from ticket assignment to PR merge.
    """

    avg_task_completion_time: float = 0.0
    p50_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0
    ticket_to_pr_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "avg_task_completion_time": self.avg_task_completion_time,
            "p50_latency": self.p50_latency,
            "p95_latency": self.p95_latency,
            "p99_latency": self.p99_latency,
            "ticket_to_pr_time": self.ticket_to_pr_time,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpeedMetrics":
        return cls(
            avg_task_completion_time=data.get("avg_task_completion_time", 0.0),
            p50_latency=data.get("p50_latency", 0.0),
            p95_latency=data.get("p95_latency", 0.0),
            p99_latency=data.get("p99_latency", 0.0),
            ticket_to_pr_time=data.get("ticket_to_pr_time", 0.0),
        )


@dataclass
class QualityMetrics:
    """Quality metrics for an agent run.

    Attributes:
        pr_approval_rate: Rate of PRs approved on first review (0.0 to 1.0).
        test_coverage_delta: Change in test coverage percentage (can be negative).
        defect_density: Code review defect density (defects per 100 lines of code).
    """

    pr_approval_rate: float = 0.0
    test_coverage_delta: float = 0.0
    defect_density: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pr_approval_rate": self.pr_approval_rate,
            "test_coverage_delta": self.test_coverage_delta,
            "defect_density": self.defect_density,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualityMetrics":
        return cls(
            pr_approval_rate=data.get("pr_approval_rate", 0.0),
            test_coverage_delta=data.get("test_coverage_delta", 0.0),
            defect_density=data.get("defect_density", 0.0),
        )


@dataclass
class CostMetrics:
    """Cost metrics for an agent run.

    Attributes:
        cost_per_agent_hour: Cost in USD per agent hour for this run.
        cost_per_ticket: Cost in USD per successfully completed ticket.
        haiku_utilization: Fraction of requests served by Haiku tier (0.0-1.0).
        sonnet_utilization: Fraction of requests served by Sonnet tier (0.0-1.0).
        opus_utilization: Fraction of requests served by Opus tier (0.0-1.0).
    """

    cost_per_agent_hour: float = 0.0
    cost_per_ticket: float = 0.0
    haiku_utilization: float = 0.0
    sonnet_utilization: float = 0.0
    opus_utilization: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cost_per_agent_hour": self.cost_per_agent_hour,
            "cost_per_ticket": self.cost_per_ticket,
            "haiku_utilization": self.haiku_utilization,
            "sonnet_utilization": self.sonnet_utilization,
            "opus_utilization": self.opus_utilization,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CostMetrics":
        return cls(
            cost_per_agent_hour=data.get("cost_per_agent_hour", 0.0),
            cost_per_ticket=data.get("cost_per_ticket", 0.0),
            haiku_utilization=data.get("haiku_utilization", 0.0),
            sonnet_utilization=data.get("sonnet_utilization", 0.0),
            opus_utilization=data.get("opus_utilization", 0.0),
        )


@dataclass
class BenchmarkResult:
    """Complete benchmark result for one agent run.

    Attributes:
        run_id: Unique identifier for this benchmark run.
        agent_type: The type/name of the agent being benchmarked.
        timestamp: ISO-8601 UTC timestamp when benchmark was recorded.
        speed: Speed performance metrics.
        quality: Quality metrics.
        cost: Cost metrics.
        regression_detected: Whether a latency regression was detected.
        metadata: Arbitrary extra context (commit SHA, PR number, etc.).
    """

    agent_type: str
    speed: SpeedMetrics = field(default_factory=SpeedMetrics)
    quality: QualityMetrics = field(default_factory=QualityMetrics)
    cost: CostMetrics = field(default_factory=CostMetrics)
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    regression_detected: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "agent_type": self.agent_type,
            "timestamp": self.timestamp,
            "speed": self.speed.to_dict(),
            "quality": self.quality.to_dict(),
            "cost": self.cost.to_dict(),
            "regression_detected": self.regression_detected,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BenchmarkResult":
        result = cls(
            agent_type=data["agent_type"],
            speed=SpeedMetrics.from_dict(data.get("speed", {})),
            quality=QualityMetrics.from_dict(data.get("quality", {})),
            cost=CostMetrics.from_dict(data.get("cost", {})),
            run_id=data.get("run_id", str(uuid.uuid4())),
            timestamp=data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            regression_detected=data.get("regression_detected", False),
            metadata=data.get("metadata", {}),
        )
        return result


# ---------------------------------------------------------------------------
# Percentile helper
# ---------------------------------------------------------------------------


def _percentile(values: List[float], pct: float) -> float:
    """Calculate a percentile value from a sorted or unsorted list.

    Args:
        values: List of numeric values.
        pct: Percentile to compute (e.g., 95 for the 95th percentile).

    Returns:
        The percentile value, or 0.0 if the list is empty.
    """
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    idx = (pct / 100.0) * (len(sorted_vals) - 1)
    lower = int(idx)
    upper = min(lower + 1, len(sorted_vals) - 1)
    fraction = idx - lower
    return sorted_vals[lower] + fraction * (sorted_vals[upper] - sorted_vals[lower])


# ---------------------------------------------------------------------------
# BenchmarkRunner
# ---------------------------------------------------------------------------

# Regression threshold: alert if p95 latency degrades by more than this fraction
REGRESSION_THRESHOLD = 0.20  # 20%


class BenchmarkRunner:
    """Collects and analyzes benchmark metrics for agent runs.

    Usage:
        runner = BenchmarkRunner()
        result = runner.run_benchmark("engineer", run_data)
    """

    def collect_speed_metrics(
        self, agent_type: str, run_data: Dict[str, Any]
    ) -> SpeedMetrics:
        """Collect speed metrics from run data.

        Extracts latency samples and computes p50/p95/p99 percentiles.

        Args:
            agent_type: The type of agent (e.g. "engineer", "product_manager").
            run_data: Dict containing raw run telemetry. Expected keys:
                - ``latency_samples`` (list[float]): per-request latencies in seconds
                - ``task_durations`` (list[float]): per-task completion times in seconds
                - ``ticket_to_pr_seconds`` (float): end-to-end ticket-to-PR time

        Returns:
            SpeedMetrics populated from the run data.
        """
        latency_samples: List[float] = run_data.get("latency_samples", [])
        task_durations: List[float] = run_data.get("task_durations", [])
        ticket_to_pr: float = float(run_data.get("ticket_to_pr_seconds", 0.0))

        avg_task_time = (
            statistics.mean(task_durations) if task_durations else 0.0
        )

        return SpeedMetrics(
            avg_task_completion_time=avg_task_time,
            p50_latency=_percentile(latency_samples, 50),
            p95_latency=_percentile(latency_samples, 95),
            p99_latency=_percentile(latency_samples, 99),
            ticket_to_pr_time=ticket_to_pr,
        )

    def collect_quality_metrics(
        self, agent_type: str, run_data: Dict[str, Any]
    ) -> QualityMetrics:
        """Collect quality metrics from run data.

        Args:
            agent_type: The type of agent.
            run_data: Dict containing quality indicators. Expected keys:
                - ``prs_approved_first_review`` (int)
                - ``prs_total`` (int)
                - ``test_coverage_before`` (float): coverage % before the run
                - ``test_coverage_after`` (float): coverage % after the run
                - ``defects_found`` (int): number of review defects
                - ``lines_changed`` (int): lines of code changed

        Returns:
            QualityMetrics populated from the run data.
        """
        prs_approved = int(run_data.get("prs_approved_first_review", 0))
        prs_total = int(run_data.get("prs_total", 1))
        approval_rate = prs_approved / prs_total if prs_total > 0 else 0.0

        coverage_before = float(run_data.get("test_coverage_before", 0.0))
        coverage_after = float(run_data.get("test_coverage_after", 0.0))
        coverage_delta = coverage_after - coverage_before

        defects = int(run_data.get("defects_found", 0))
        lines_changed = int(run_data.get("lines_changed", 100))
        defect_density = (
            (defects / lines_changed) * 100 if lines_changed > 0 else 0.0
        )

        return QualityMetrics(
            pr_approval_rate=approval_rate,
            test_coverage_delta=coverage_delta,
            defect_density=defect_density,
        )

    def collect_cost_metrics(
        self, agent_type: str, run_data: Dict[str, Any]
    ) -> CostMetrics:
        """Collect cost metrics from run data.

        Args:
            agent_type: The type of agent.
            run_data: Dict containing cost data. Expected keys:
                - ``total_cost_usd`` (float): total spend in USD for the run
                - ``agent_hours`` (float): total agent compute hours consumed
                - ``tickets_completed`` (int): successfully closed tickets
                - ``haiku_requests`` (int)
                - ``sonnet_requests`` (int)
                - ``opus_requests`` (int)

        Returns:
            CostMetrics populated from the run data.
        """
        total_cost = float(run_data.get("total_cost_usd", 0.0))
        agent_hours = float(run_data.get("agent_hours", 1.0))
        tickets_completed = int(run_data.get("tickets_completed", 1))

        cost_per_hour = total_cost / agent_hours if agent_hours > 0 else 0.0
        cost_per_ticket = (
            total_cost / tickets_completed if tickets_completed > 0 else 0.0
        )

        haiku = int(run_data.get("haiku_requests", 0))
        sonnet = int(run_data.get("sonnet_requests", 0))
        opus = int(run_data.get("opus_requests", 0))
        total_requests = haiku + sonnet + opus

        if total_requests > 0:
            haiku_util = haiku / total_requests
            sonnet_util = sonnet / total_requests
            opus_util = opus / total_requests
        else:
            haiku_util = sonnet_util = opus_util = 0.0

        return CostMetrics(
            cost_per_agent_hour=cost_per_hour,
            cost_per_ticket=cost_per_ticket,
            haiku_utilization=haiku_util,
            sonnet_utilization=sonnet_util,
            opus_utilization=opus_util,
        )

    def check_regression(
        self,
        metric_name: str,
        current_value: float,
        historical_values: List[float],
    ) -> bool:
        """Check whether a metric has regressed beyond the allowed threshold.

        A regression is detected when the current value exceeds the historical
        p95 by more than REGRESSION_THRESHOLD (20%).

        Args:
            metric_name: Human-readable name for logging/debugging.
            current_value: The metric value from the most recent run.
            historical_values: List of historical metric values for the same
                metric over recent runs (used to compute the rolling p95).

        Returns:
            True if a regression is detected, False otherwise.
        """
        if not historical_values:
            return False

        historical_p95 = _percentile(historical_values, 95)

        if historical_p95 <= 0:
            return False

        regression = (current_value - historical_p95) / historical_p95
        return regression > REGRESSION_THRESHOLD

    def run_benchmark(
        self,
        agent_type: str,
        run_data: Dict[str, Any],
        historical_p95: Optional[float] = None,
    ) -> BenchmarkResult:
        """Run a complete benchmark analysis for an agent run.

        Collects all metric categories and checks for latency regressions.

        Args:
            agent_type: The type of agent being benchmarked.
            run_data: Raw telemetry data for the run.
            historical_p95: Optional pre-computed historical p95 latency for
                regression checking. If None, regression check is skipped.

        Returns:
            BenchmarkResult with all metrics populated.
        """
        speed = self.collect_speed_metrics(agent_type, run_data)
        quality = self.collect_quality_metrics(agent_type, run_data)
        cost = self.collect_cost_metrics(agent_type, run_data)

        regression_detected = False
        if historical_p95 is not None and historical_p95 > 0:
            ratio = (speed.p95_latency - historical_p95) / historical_p95
            regression_detected = ratio > REGRESSION_THRESHOLD

        return BenchmarkResult(
            agent_type=agent_type,
            speed=speed,
            quality=quality,
            cost=cost,
            regression_detected=regression_detected,
            metadata=run_data.get("metadata", {}),
        )
