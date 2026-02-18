"""WebSocket Latency Benchmark - REQ-PERF-001.

Provides a thread-safe LatencyTracker for measuring event emission-to-delivery
latency for WebSocket broadcasts. Exposes p50/p95/p99/max/mean statistics and
a check_target() helper to verify the 100ms SLA.
"""

import statistics
import threading
import time
from typing import Dict, List, Optional


class LatencyTracker:
    """Track WebSocket broadcast latency from event emission to delivery.

    Thread-safe. Records timestamps at two points:
    1. record_emit(event_id)     — called just before sending to WebSocket clients
    2. record_delivery(event_id) — called just after the send completes

    The difference (delivery - emit) is the per-event latency in milliseconds.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Maps event_id -> emit timestamp (monotonic, seconds)
        self._pending: Dict[str, float] = {}
        # Completed latencies in milliseconds
        self._latencies: List[float] = []

    # ------------------------------------------------------------------
    # Recording API
    # ------------------------------------------------------------------

    def record_emit(self, event_id: str) -> None:
        """Stamp the emission time for *event_id*.

        Should be called immediately before the message is sent to WebSocket
        clients so the clock starts as close to the actual send as possible.

        Args:
            event_id: Unique identifier for this broadcast event.
        """
        ts = time.monotonic()
        with self._lock:
            self._pending[event_id] = ts

    def record_delivery(self, event_id: str) -> Optional[float]:
        """Stamp delivery time for *event_id* and record the latency.

        Args:
            event_id: Must match a previous record_emit() call.

        Returns:
            Latency in milliseconds, or None if no matching emit was found.
        """
        ts = time.monotonic()
        with self._lock:
            emit_ts = self._pending.pop(event_id, None)
            if emit_ts is None:
                return None
            latency_ms = (ts - emit_ts) * 1000.0
            self._latencies.append(latency_ms)
            return latency_ms

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_stats(self) -> dict:
        """Return aggregated latency statistics.

        Returns:
            dict with keys: p50, p95, p99, max, mean, count, within_100ms_pct.
            All latency values are in milliseconds.
            When there are no recorded latencies, numeric fields are 0.0 and
            within_100ms_pct is 100.0 (vacuously true).
        """
        with self._lock:
            latencies = list(self._latencies)

        if not latencies:
            return {
                "p50": 0.0,
                "p95": 0.0,
                "p99": 0.0,
                "max": 0.0,
                "mean": 0.0,
                "count": 0,
                "within_100ms_pct": 100.0,
            }

        sorted_latencies = sorted(latencies)
        count = len(sorted_latencies)

        def percentile(data: List[float], pct: float) -> float:
            idx = (pct / 100.0) * (len(data) - 1)
            lower = int(idx)
            upper = min(lower + 1, len(data) - 1)
            frac = idx - lower
            return data[lower] + frac * (data[upper] - data[lower])

        within_100ms = sum(1 for v in latencies if v <= 100.0)
        within_100ms_pct = (within_100ms / count) * 100.0

        return {
            "p50": percentile(sorted_latencies, 50),
            "p95": percentile(sorted_latencies, 95),
            "p99": percentile(sorted_latencies, 99),
            "max": max(sorted_latencies),
            "mean": statistics.mean(latencies),
            "count": count,
            "within_100ms_pct": within_100ms_pct,
        }

    def check_target(self, target_ms: float = 100.0) -> bool:
        """Return True if p99 latency is at or below *target_ms* milliseconds.

        An empty tracker (no deliveries recorded) is considered passing.

        Args:
            target_ms: Latency budget in milliseconds (default 100).

        Returns:
            True when p99 <= target_ms, False otherwise.
        """
        stats = self.get_stats()
        if stats["count"] == 0:
            return True
        return stats["p99"] <= target_ms

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all recorded latencies and pending emit timestamps."""
        with self._lock:
            self._pending.clear()
            self._latencies.clear()

    def __repr__(self) -> str:  # pragma: no cover
        stats = self.get_stats()
        return (
            f"<LatencyTracker count={stats['count']} "
            f"p99={stats['p99']:.2f}ms "
            f"within_100ms={stats['within_100ms_pct']:.1f}%>"
        )
