"""Benchmark tests for WebSocket latency - REQ-PERF-001.

Verifies that:
- LatencyTracker correctly records emit/delivery timestamps and computes stats.
- broadcast_to_websockets() completes within 100 ms for local connections.
- GET /api/latency exposes stats with all required fields.
"""

import asyncio
import json
import tempfile
import threading
import time
from pathlib import Path

import pytest
import pytest_asyncio
from aiohttp import ClientSession, WSMsgType
from aiohttp import web

from dashboard.latency_benchmark import LatencyTracker
from dashboard.server import DashboardServer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tracker():
    """Return a fresh LatencyTracker."""
    return LatencyTracker()


@pytest.fixture
def temp_metrics_dir():
    """Temporary directory for metrics files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest_asyncio.fixture
async def server(temp_metrics_dir):
    """Start a DashboardServer on a free port and yield it."""
    srv = DashboardServer(
        project_name="test-latency",
        metrics_dir=temp_metrics_dir,
        port=18090,
        host="127.0.0.1",
    )
    runner = web.AppRunner(srv.app)
    await runner.setup()
    site = web.TCPSite(runner, srv.host, srv.port)
    await site.start()
    await asyncio.sleep(0.2)
    try:
        yield srv
    finally:
        await runner.cleanup()


# ---------------------------------------------------------------------------
# Unit tests: LatencyTracker
# ---------------------------------------------------------------------------

class TestLatencyTrackerBasic:
    """Basic recording and stats tests."""

    def test_record_emit_stores_timestamp(self, tracker):
        """record_emit stores a pending entry for the event_id."""
        tracker.record_emit("evt-001")
        with tracker._lock:
            assert "evt-001" in tracker._pending

    def test_record_delivery_returns_latency(self, tracker):
        """record_delivery returns a non-negative float in ms."""
        tracker.record_emit("evt-002")
        latency = tracker.record_delivery("evt-002")
        assert latency is not None
        assert latency >= 0.0

    def test_record_delivery_removes_pending(self, tracker):
        """After delivery, the event_id is no longer pending."""
        tracker.record_emit("evt-003")
        tracker.record_delivery("evt-003")
        with tracker._lock:
            assert "evt-003" not in tracker._pending

    def test_record_delivery_unknown_event_returns_none(self, tracker):
        """Delivery without a matching emit returns None."""
        result = tracker.record_delivery("nonexistent")
        assert result is None

    def test_latency_appended_to_list(self, tracker):
        """Completed latencies accumulate in _latencies."""
        tracker.record_emit("e1")
        tracker.record_delivery("e1")
        tracker.record_emit("e2")
        tracker.record_delivery("e2")
        with tracker._lock:
            assert len(tracker._latencies) == 2

    def test_delivery_before_emit_returns_none(self, tracker):
        """Calling record_delivery before record_emit returns None."""
        result = tracker.record_delivery("never-emitted")
        assert result is None

    def test_multiple_events_independent(self, tracker):
        """Multiple concurrent events are tracked independently."""
        tracker.record_emit("a")
        tracker.record_emit("b")
        tracker.record_emit("c")
        la = tracker.record_delivery("a")
        lb = tracker.record_delivery("b")
        lc = tracker.record_delivery("c")
        assert all(v is not None and v >= 0 for v in [la, lb, lc])


# ---------------------------------------------------------------------------
# Unit tests: get_stats()
# ---------------------------------------------------------------------------

class TestGetStats:
    """Tests for the stats computation."""

    def test_empty_tracker_returns_zero_stats(self, tracker):
        """Empty tracker returns sensible defaults (all zeros, 100% within target)."""
        stats = tracker.get_stats()
        assert stats["count"] == 0
        assert stats["p50"] == 0.0
        assert stats["p95"] == 0.0
        assert stats["p99"] == 0.0
        assert stats["max"] == 0.0
        assert stats["mean"] == 0.0
        assert stats["within_100ms_pct"] == 100.0

    def test_get_stats_returns_all_required_fields(self, tracker):
        """get_stats() always returns all required fields."""
        stats = tracker.get_stats()
        required = {"p50", "p95", "p99", "max", "mean", "count", "within_100ms_pct"}
        assert required.issubset(stats.keys())

    def test_get_stats_count_matches_deliveries(self, tracker):
        """count equals the number of completed emit/delivery pairs."""
        for i in range(5):
            tracker.record_emit(f"e{i}")
            tracker.record_delivery(f"e{i}")
        assert tracker.get_stats()["count"] == 5

    def test_get_stats_mean_is_correct(self, tracker):
        """mean is computed correctly from injected latencies."""
        # Inject known latencies directly to avoid timing noise.
        with tracker._lock:
            tracker._latencies = [10.0, 20.0, 30.0]
        stats = tracker.get_stats()
        assert abs(stats["mean"] - 20.0) < 1e-9

    def test_get_stats_max_is_correct(self, tracker):
        """max returns the largest recorded latency."""
        with tracker._lock:
            tracker._latencies = [5.0, 50.0, 80.0, 99.0]
        stats = tracker.get_stats()
        assert stats["max"] == 99.0

    def test_get_stats_p50_single_value(self, tracker):
        """p50 of a single value equals that value."""
        with tracker._lock:
            tracker._latencies = [42.0]
        stats = tracker.get_stats()
        assert abs(stats["p50"] - 42.0) < 1e-9

    def test_within_100ms_pct_all_fast(self, tracker):
        """All sub-100ms latencies yields 100% within target."""
        with tracker._lock:
            tracker._latencies = [10.0, 20.0, 30.0, 99.9]
        stats = tracker.get_stats()
        assert stats["within_100ms_pct"] == 100.0

    def test_within_100ms_pct_some_slow(self, tracker):
        """50% within target when half the latencies exceed 100ms."""
        with tracker._lock:
            tracker._latencies = [50.0, 50.0, 150.0, 200.0]
        stats = tracker.get_stats()
        assert abs(stats["within_100ms_pct"] - 50.0) < 1e-9


# ---------------------------------------------------------------------------
# Unit tests: check_target()
# ---------------------------------------------------------------------------

class TestCheckTarget:
    """Tests for the target-verification helper."""

    def test_check_target_empty_returns_true(self, tracker):
        """Empty tracker passes: no data means no violation."""
        assert tracker.check_target() is True

    def test_check_target_passes_when_p99_within_limit(self, tracker):
        """Returns True when p99 <= 100ms."""
        with tracker._lock:
            tracker._latencies = [1.0] * 100  # p99 well below 100ms
        assert tracker.check_target(100) is True

    def test_check_target_fails_when_p99_exceeds_limit(self, tracker):
        """Returns False when p99 > 100ms."""
        with tracker._lock:
            # Use a small dataset where the high value clearly drives p99 > 100ms.
            # With [50]*7 + [500]*3 (10 values), p99 is near the max (500ms).
            tracker._latencies = [50.0] * 7 + [500.0] * 3
        result = tracker.check_target(100)
        assert result is False

    def test_check_target_custom_threshold(self, tracker):
        """Custom target_ms is respected."""
        with tracker._lock:
            tracker._latencies = [30.0, 30.0, 30.0]
        assert tracker.check_target(50) is True
        assert tracker.check_target(20) is False


# ---------------------------------------------------------------------------
# Unit tests: reset()
# ---------------------------------------------------------------------------

class TestReset:
    """Tests for stats reset."""

    def test_reset_clears_latencies(self, tracker):
        """reset() removes all recorded latencies."""
        for i in range(3):
            tracker.record_emit(f"r{i}")
            tracker.record_delivery(f"r{i}")
        tracker.reset()
        assert tracker.get_stats()["count"] == 0

    def test_reset_clears_pending(self, tracker):
        """reset() also clears pending emit timestamps."""
        tracker.record_emit("pending-evt")
        tracker.reset()
        with tracker._lock:
            assert len(tracker._pending) == 0

    def test_reset_allows_fresh_recording(self, tracker):
        """After reset, new recordings work normally."""
        tracker.record_emit("x")
        tracker.record_delivery("x")
        tracker.reset()
        tracker.record_emit("y")
        lat = tracker.record_delivery("y")
        assert lat is not None and lat >= 0
        assert tracker.get_stats()["count"] == 1


# ---------------------------------------------------------------------------
# Unit tests: Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    """Concurrent access must not corrupt state."""

    def test_concurrent_record_emit_does_not_corrupt(self, tracker):
        """Multiple threads calling record_emit simultaneously are all recorded."""
        n = 50
        barrier = threading.Barrier(n)

        def emit_and_deliver(i):
            barrier.wait()
            eid = f"thread-{i}"
            tracker.record_emit(eid)
            tracker.record_delivery(eid)

        threads = [threading.Thread(target=emit_and_deliver, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert tracker.get_stats()["count"] == n

    def test_concurrent_get_stats_does_not_raise(self, tracker):
        """get_stats() can be called while records are being added."""
        stop = threading.Event()
        errors = []

        def writer():
            for i in range(100):
                tracker.record_emit(f"w{i}")
                tracker.record_delivery(f"w{i}")

        def reader():
            while not stop.is_set():
                try:
                    tracker.get_stats()
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

        w = threading.Thread(target=writer)
        r = threading.Thread(target=reader)
        r.start()
        w.start()
        w.join()
        stop.set()
        r.join()

        assert errors == []


# ---------------------------------------------------------------------------
# Integration tests: actual WebSocket broadcast latency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_single_broadcast_latency_under_100ms(server):
    """A single broadcast to a connected client completes in < 100ms."""
    async with ClientSession() as session:
        async with session.ws_connect("http://127.0.0.1:18090/ws") as ws:
            # Consume initial metrics_update
            await ws.receive(timeout=3)

            start = time.monotonic()
            await server.broadcast_to_websockets({"type": "latency_test", "n": 1})
            elapsed_ms = (time.monotonic() - start) * 1000

            msg = await ws.receive(timeout=2)
            data = json.loads(msg.data)
            assert data["type"] == "latency_test"
            assert elapsed_ms < 100, f"Broadcast took {elapsed_ms:.1f}ms (expected < 100ms)"


@pytest.mark.asyncio
async def test_ten_rapid_broadcasts_all_under_100ms(server):
    """10 rapid broadcasts all complete within 100ms each."""
    async with ClientSession() as session:
        async with session.ws_connect("http://127.0.0.1:18090/ws") as ws:
            await ws.receive(timeout=3)

            latencies = []
            for i in range(10):
                t0 = time.monotonic()
                await server.broadcast_to_websockets({"type": "latency_test", "n": i})
                latency_ms = (time.monotonic() - t0) * 1000
                latencies.append(latency_ms)
                # Consume the message
                await ws.receive(timeout=2)

            for i, lat in enumerate(latencies):
                assert lat < 100, f"Broadcast #{i} took {lat:.1f}ms (expected < 100ms)"


@pytest.mark.asyncio
async def test_tracker_records_latency_during_broadcast(server):
    """broadcast_to_websockets() increments tracker count for each call."""
    server.latency_tracker.reset()
    async with ClientSession() as session:
        async with session.ws_connect("http://127.0.0.1:18090/ws") as ws:
            await ws.receive(timeout=3)
            for i in range(5):
                await server.broadcast_to_websockets({"type": "t", "n": i})
                await ws.receive(timeout=2)

    stats = server.latency_tracker.get_stats()
    assert stats["count"] >= 5


@pytest.mark.asyncio
async def test_tracker_p99_within_target_after_broadcasts(server):
    """After 10 local broadcasts, tracker reports p99 <= 100ms."""
    server.latency_tracker.reset()
    async with ClientSession() as session:
        async with session.ws_connect("http://127.0.0.1:18090/ws") as ws:
            await ws.receive(timeout=3)
            for i in range(10):
                await server.broadcast_to_websockets({"type": "bench", "n": i})
                await ws.receive(timeout=2)

    assert server.latency_tracker.check_target(100), (
        f"p99 latency exceeded 100ms: {server.latency_tracker.get_stats()}"
    )


# ---------------------------------------------------------------------------
# Integration tests: GET /api/latency endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_latency_endpoint_returns_200(server):
    """GET /api/latency responds with HTTP 200."""
    async with ClientSession() as session:
        async with session.get("http://127.0.0.1:18090/api/latency") as resp:
            assert resp.status == 200


@pytest.mark.asyncio
async def test_get_latency_endpoint_returns_valid_json(server):
    """GET /api/latency returns parseable JSON."""
    async with ClientSession() as session:
        async with session.get("http://127.0.0.1:18090/api/latency") as resp:
            body = await resp.json()
            assert isinstance(body, dict)


@pytest.mark.asyncio
async def test_get_latency_endpoint_contains_all_required_fields(server):
    """GET /api/latency response includes all required stat fields."""
    async with ClientSession() as session:
        async with session.get("http://127.0.0.1:18090/api/latency") as resp:
            body = await resp.json()

    required = {"p50", "p95", "p99", "max", "mean", "count", "within_100ms_pct",
                "target_ms", "target_met", "timestamp"}
    missing = required - set(body.keys())
    assert not missing, f"Missing fields in /api/latency response: {missing}"


@pytest.mark.asyncio
async def test_get_latency_endpoint_target_ms_is_100(server):
    """GET /api/latency response reports target_ms = 100."""
    async with ClientSession() as session:
        async with session.get("http://127.0.0.1:18090/api/latency") as resp:
            body = await resp.json()
    assert body["target_ms"] == 100


@pytest.mark.asyncio
async def test_get_latency_endpoint_reflects_broadcast_activity(server):
    """After a broadcast, /api/latency count increases."""
    server.latency_tracker.reset()
    before_count = (await (await ClientSession().get(
        "http://127.0.0.1:18090/api/latency")).json())["count"]

    async with ClientSession() as session:
        async with session.ws_connect("http://127.0.0.1:18090/ws") as ws:
            await ws.receive(timeout=3)
            await server.broadcast_to_websockets({"type": "x"})
            await ws.receive(timeout=2)

    async with ClientSession() as session:
        async with session.get("http://127.0.0.1:18090/api/latency") as resp:
            body = await resp.json()

    assert body["count"] > before_count
