"""In-memory benchmark storage with 90-day retention (AI-248).

BenchmarkStorage maintains an in-memory dict-based store of BenchmarkResult
objects, with automatic cleanup of results older than the configured retention
window.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from benchmarks.runner import BenchmarkResult, _percentile


class BenchmarkStorage:
    """Thread-safe in-memory storage for benchmark results.

    Results are stored keyed by ``run_id``. Cleanup removes results
    older than ``retention_days`` (default 90). Retrieval supports
    optional filtering by agent type and result count limiting.

    Args:
        retention_days: Number of days to retain results (default 90).
    """

    def __init__(self, retention_days: int = 90) -> None:
        self._retention_days = retention_days
        # Mapping run_id -> BenchmarkResult
        self._results: Dict[str, BenchmarkResult] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save_result(self, result: BenchmarkResult) -> None:
        """Persist a benchmark result in memory.

        Triggers automatic cleanup of expired results after saving.

        Args:
            result: The BenchmarkResult to store.
        """
        with self._lock:
            self._results[result.run_id] = result
        # Clean up old entries after each save so the store stays bounded
        self.cleanup_old_results(self._retention_days)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_results(
        self,
        agent_type: Optional[str] = None,
        limit: int = 30,
    ) -> List[BenchmarkResult]:
        """Retrieve stored benchmark results, newest first.

        Args:
            agent_type: If provided, only return results for this agent type.
            limit: Maximum number of results to return (default 30).

        Returns:
            List of BenchmarkResult objects sorted by timestamp descending.
        """
        with self._lock:
            results = list(self._results.values())

        if agent_type is not None:
            results = [r for r in results if r.agent_type == agent_type]

        # Sort newest first
        results.sort(key=lambda r: r.timestamp, reverse=True)
        return results[:limit]

    def get_historical_p95(
        self,
        metric_name: str,
        days: int = 7,
        agent_type: Optional[str] = None,
    ) -> float:
        """Compute the p95 of a named metric across results from the last N days.

        Supported metric names:
            - ``p95_latency``
            - ``p50_latency``
            - ``p99_latency``
            - ``avg_task_completion_time``
            - ``ticket_to_pr_time``
            - ``pr_approval_rate``
            - ``test_coverage_delta``
            - ``defect_density``
            - ``cost_per_agent_hour``
            - ``cost_per_ticket``

        Args:
            metric_name: The name of the metric to aggregate.
            days: How many days of history to include (default 7).
            agent_type: Optional filter by agent type.

        Returns:
            The p95 value, or 0.0 if there is insufficient data.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        with self._lock:
            results = list(self._results.values())

        values: List[float] = []
        for r in results:
            # Parse timestamp
            try:
                ts = datetime.fromisoformat(r.timestamp)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            if ts < cutoff:
                continue

            if agent_type is not None and r.agent_type != agent_type:
                continue

            value = self._extract_metric(r, metric_name)
            if value is not None:
                values.append(value)

        return _percentile(values, 95)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup_old_results(self, days: int = 90) -> int:
        """Remove results older than the given number of days.

        Args:
            days: Results older than this many days are deleted.

        Returns:
            Number of results removed.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        to_delete: List[str] = []

        with self._lock:
            for run_id, result in self._results.items():
                try:
                    ts = datetime.fromisoformat(result.timestamp)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    if ts < cutoff:
                        to_delete.append(run_id)
                except ValueError:
                    # Malformed timestamp — remove defensively
                    to_delete.append(run_id)

            for run_id in to_delete:
                del self._results[run_id]

        return len(to_delete)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_metric(result: BenchmarkResult, metric_name: str) -> Optional[float]:
        """Extract a named metric from a BenchmarkResult.

        Args:
            result: The benchmark result to inspect.
            metric_name: Name of the metric to extract.

        Returns:
            The float value if found, else None.
        """
        speed_fields = {
            "p95_latency": result.speed.p95_latency,
            "p50_latency": result.speed.p50_latency,
            "p99_latency": result.speed.p99_latency,
            "avg_task_completion_time": result.speed.avg_task_completion_time,
            "ticket_to_pr_time": result.speed.ticket_to_pr_time,
        }
        quality_fields = {
            "pr_approval_rate": result.quality.pr_approval_rate,
            "test_coverage_delta": result.quality.test_coverage_delta,
            "defect_density": result.quality.defect_density,
        }
        cost_fields = {
            "cost_per_agent_hour": result.cost.cost_per_agent_hour,
            "cost_per_ticket": result.cost.cost_per_ticket,
        }

        for mapping in (speed_fields, quality_fields, cost_fields):
            if metric_name in mapping:
                return float(mapping[metric_name])

        return None
