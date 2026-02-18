"""WebSocket Latency Benchmark - REQ-PERF-001.

Provides a thread-safe LatencyTracker for measuring event emission-to-delivery
latency for WebSocket broadcasts. Exposes p50/p95/p99/max/mean statistics and
a check_target() helper to verify the 100ms SLA.

Also provides StreamingLatencyTracker (AI-182 / REQ-PERF-003) for tracking
the time from when ChatBridge.handle_message() is called to when the first
response chunk is yielded to the client, verifying the 500ms target.
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


# ---------------------------------------------------------------------------
# AI-182 / REQ-PERF-003: Chat response streaming latency tracker
# ---------------------------------------------------------------------------


class StreamingLatencyTracker:
    """Track latency from handle_message() call to first chunk yielded.

    Thread-safe. Records timestamps at two points:
    1. record_stream_start(stream_id)  — when handle_message() is called
    2. record_first_chunk(stream_id)   — when the first chunk is yielded

    The difference is the streaming start latency in milliseconds.
    Target: p99 <= 500 ms (REQ-PERF-003).
    """

    # Default streaming start target (REQ-PERF-003)
    DEFAULT_TARGET_MS: float = 500.0

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # Maps stream_id -> stream-start timestamp (monotonic, seconds)
        self._pending: Dict[str, float] = {}
        # Completed first-chunk latencies in milliseconds
        self._latencies: List[float] = []

    # ------------------------------------------------------------------
    # Recording API
    # ------------------------------------------------------------------

    def record_stream_start(self, stream_id: str) -> None:
        """Record when handle_message() is invoked for *stream_id*.

        Should be called at the very start of the streaming pipeline so the
        clock begins as close to the actual call as possible.

        Args:
            stream_id: Unique identifier for this streaming session.
        """
        ts = time.monotonic()
        with self._lock:
            self._pending[stream_id] = ts

    def record_first_chunk(self, stream_id: str) -> Optional[float]:
        """Record when the first response chunk is yielded for *stream_id*.

        Args:
            stream_id: Must match a previous record_stream_start() call.

        Returns:
            Latency in milliseconds from stream start to first chunk, or None
            if no matching start was found.
        """
        ts = time.monotonic()
        with self._lock:
            start_ts = self._pending.pop(stream_id, None)
            if start_ts is None:
                return None
            latency_ms = (ts - start_ts) * 1000.0
            self._latencies.append(latency_ms)
            return latency_ms

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    def get_streaming_stats(self) -> dict:
        """Return aggregated streaming-start latency statistics.

        Returns:
            dict with keys: p50, p95, p99, max, mean, count, within_500ms_pct.
            All latency values are in milliseconds.
            When there are no recorded latencies, numeric fields are 0.0 and
            within_500ms_pct is 100.0 (vacuously true).
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
                "within_500ms_pct": 100.0,
            }

        sorted_latencies = sorted(latencies)
        count = len(sorted_latencies)

        def percentile(data: List[float], pct: float) -> float:
            idx = (pct / 100.0) * (len(data) - 1)
            lower = int(idx)
            upper = min(lower + 1, len(data) - 1)
            frac = idx - lower
            return data[lower] + frac * (data[upper] - data[lower])

        within_500ms = sum(1 for v in latencies if v <= 500.0)
        within_500ms_pct = (within_500ms / count) * 100.0

        return {
            "p50": percentile(sorted_latencies, 50),
            "p95": percentile(sorted_latencies, 95),
            "p99": percentile(sorted_latencies, 99),
            "max": max(sorted_latencies),
            "mean": statistics.mean(latencies),
            "count": count,
            "within_500ms_pct": within_500ms_pct,
        }

    def check_streaming_target(self, target_ms: float = DEFAULT_TARGET_MS) -> bool:
        """Return True if p99 streaming latency is at or below *target_ms* ms.

        An empty tracker (no first-chunk records) is considered passing.

        Args:
            target_ms: Latency budget in milliseconds (default 500).

        Returns:
            True when p99 <= target_ms, False otherwise.
        """
        stats = self.get_streaming_stats()
        if stats["count"] == 0:
            return True
        return stats["p99"] <= target_ms

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all recorded latencies and pending start timestamps."""
        with self._lock:
            self._pending.clear()
            self._latencies.clear()

    def __repr__(self) -> str:  # pragma: no cover
        stats = self.get_streaming_stats()
        return (
            f"<StreamingLatencyTracker count={stats['count']} "
            f"p99={stats['p99']:.2f}ms "
            f"within_500ms={stats['within_500ms_pct']:.1f}%>"
        )
