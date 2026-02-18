"""Tests for Chat Response Streaming Latency Benchmark - REQ-PERF-003.

Verifies that:
- StreamingLatencyTracker correctly records stream start and first chunk.
- get_streaming_stats() returns all required fields including within_500ms_pct.
- check_streaming_target() uses 500ms default.
- Integration: handle_message first chunk arrives within 500ms for general_chat.
- GET /api/streaming-latency returns valid JSON with all required fields.
- Thread-safety of StreamingLatencyTracker.
"""

import asyncio
import json
import tempfile
import threading
import time
from pathlib import Path

import pytest
import pytest_asyncio
from aiohttp import ClientSession
from aiohttp import web

from dashboard.latency_benchmark import StreamingLatencyTracker
from dashboard.chat_bridge import ChatBridge, IntentParser, AgentRouter
from dashboard.server import DashboardServer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tracker():
    """Return a fresh StreamingLatencyTracker."""
    return StreamingLatencyTracker()


@pytest.fixture
def temp_metrics_dir():
    """Temporary directory for metrics files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest_asyncio.fixture
async def server(temp_metrics_dir):
    """Start a DashboardServer on a free port and yield it."""
    srv = DashboardServer(
        project_name="test-streaming-latency",
        metrics_dir=temp_metrics_dir,
        port=18091,
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


@pytest.fixture
def bridge():
    """Return a fresh ChatBridge."""
    return ChatBridge(
        intent_parser=IntentParser(),
        agent_router=AgentRouter(),
    )


# ---------------------------------------------------------------------------
# Unit tests: StreamingLatencyTracker recording
# ---------------------------------------------------------------------------

class TestStreamingLatencyTrackerRecording:
    """Tests for stream start and first chunk recording."""

    def test_record_stream_start_stores_timestamp(self, tracker):
        """record_stream_start stores a pending entry for the stream_id."""
        tracker.record_stream_start("stream-001")
        with tracker._lock:
            assert "stream-001" in tracker._pending

    def test_record_first_chunk_returns_latency(self, tracker):
        """record_first_chunk returns a non-negative float in ms."""
        tracker.record_stream_start("stream-002")
        latency = tracker.record_first_chunk("stream-002")
        assert latency is not None
        assert latency >= 0.0

    def test_record_first_chunk_removes_pending(self, tracker):
        """After first chunk, the stream_id is no longer pending."""
        tracker.record_stream_start("stream-003")
        tracker.record_first_chunk("stream-003")
        with tracker._lock:
            assert "stream-003" not in tracker._pending

    def test_record_first_chunk_unknown_stream_returns_none(self, tracker):
        """First chunk without a matching stream start returns None."""
        result = tracker.record_first_chunk("nonexistent-stream")
        assert result is None

    def test_latency_appended_to_list(self, tracker):
        """Completed latencies accumulate in _latencies."""
        tracker.record_stream_start("s1")
        tracker.record_first_chunk("s1")
        tracker.record_stream_start("s2")
        tracker.record_first_chunk("s2")
        with tracker._lock:
            assert len(tracker._latencies) == 2

    def test_first_chunk_before_start_returns_none(self, tracker):
        """Calling record_first_chunk before record_stream_start returns None."""
        result = tracker.record_first_chunk("never-started")
        assert result is None

    def test_multiple_streams_independent(self, tracker):
        """Multiple concurrent streams are tracked independently."""
        tracker.record_stream_start("a")
        tracker.record_stream_start("b")
        tracker.record_stream_start("c")
        la = tracker.record_first_chunk("a")
        lb = tracker.record_first_chunk("b")
        lc = tracker.record_first_chunk("c")
        assert all(v is not None and v >= 0 for v in [la, lb, lc])


# ---------------------------------------------------------------------------
# Unit tests: get_streaming_stats()
# ---------------------------------------------------------------------------

class TestGetStreamingStats:
    """Tests for the streaming stats computation."""

    def test_empty_tracker_returns_zero_stats(self, tracker):
        """Empty tracker returns sensible defaults (all zeros, 100% within target)."""
        stats = tracker.get_streaming_stats()
        assert stats["count"] == 0
        assert stats["p50"] == 0.0
        assert stats["p95"] == 0.0
        assert stats["p99"] == 0.0
        assert stats["max"] == 0.0
        assert stats["mean"] == 0.0
        assert stats["within_500ms_pct"] == 100.0

    def test_get_streaming_stats_returns_all_required_fields(self, tracker):
        """get_streaming_stats() always returns all required fields."""
        stats = tracker.get_streaming_stats()
        required = {"p50", "p95", "p99", "max", "mean", "count", "within_500ms_pct"}
        assert required.issubset(stats.keys())

    def test_get_streaming_stats_count_matches_completed_streams(self, tracker):
        """count equals the number of completed start/first-chunk pairs."""
        for i in range(5):
            tracker.record_stream_start(f"s{i}")
            tracker.record_first_chunk(f"s{i}")
        assert tracker.get_streaming_stats()["count"] == 5

    def test_get_streaming_stats_mean_is_correct(self, tracker):
        """mean is computed correctly from injected latencies."""
        with tracker._lock:
            tracker._latencies = [100.0, 200.0, 300.0]
        stats = tracker.get_streaming_stats()
        assert abs(stats["mean"] - 200.0) < 1e-9

    def test_get_streaming_stats_max_is_correct(self, tracker):
        """max returns the largest recorded latency."""
        with tracker._lock:
            tracker._latencies = [50.0, 100.0, 200.0, 499.0]
        stats = tracker.get_streaming_stats()
        assert stats["max"] == 499.0

    def test_get_streaming_stats_p50_single_value(self, tracker):
        """p50 of a single value equals that value."""
        with tracker._lock:
            tracker._latencies = [250.0]
        stats = tracker.get_streaming_stats()
        assert abs(stats["p50"] - 250.0) < 1e-9

    def test_within_500ms_pct_all_fast(self, tracker):
        """All sub-500ms latencies yields 100% within target."""
        with tracker._lock:
            tracker._latencies = [50.0, 100.0, 200.0, 499.9]
        stats = tracker.get_streaming_stats()
        assert stats["within_500ms_pct"] == 100.0

    def test_within_500ms_pct_some_slow(self, tracker):
        """50% within target when half the latencies exceed 500ms."""
        with tracker._lock:
            tracker._latencies = [100.0, 100.0, 600.0, 800.0]
        stats = tracker.get_streaming_stats()
        assert abs(stats["within_500ms_pct"] - 50.0) < 1e-9


# ---------------------------------------------------------------------------
# Unit tests: check_streaming_target()
# ---------------------------------------------------------------------------

class TestCheckStreamingTarget:
    """Tests for the streaming target-verification helper."""

    def test_check_streaming_target_empty_returns_true(self, tracker):
        """Empty tracker passes: no data means no violation."""
        assert tracker.check_streaming_target() is True

    def test_check_streaming_target_passes_when_p99_within_limit(self, tracker):
        """Returns True when p99 <= 500ms."""
        with tracker._lock:
            tracker._latencies = [10.0] * 100  # p99 well below 500ms
        assert tracker.check_streaming_target(500) is True

    def test_check_streaming_target_fails_when_p99_exceeds_limit(self, tracker):
        """Returns False when p99 > 500ms."""
        with tracker._lock:
            # Use a small dataset where the high value clearly drives p99 > 500ms.
            tracker._latencies = [100.0] * 7 + [2000.0] * 3
        result = tracker.check_streaming_target(500)
        assert result is False

    def test_check_streaming_target_default_is_500ms(self, tracker):
        """Default target is 500ms."""
        with tracker._lock:
            tracker._latencies = [200.0] * 100
        assert tracker.check_streaming_target() is True

    def test_check_streaming_target_custom_threshold(self, tracker):
        """Custom target_ms is respected."""
        with tracker._lock:
            tracker._latencies = [100.0, 100.0, 100.0]
        assert tracker.check_streaming_target(200) is True
        assert tracker.check_streaming_target(50) is False


# ---------------------------------------------------------------------------
# Unit tests: reset()
# ---------------------------------------------------------------------------

class TestStreamingTrackerReset:
    """Tests for stats reset."""

    def test_reset_clears_latencies(self, tracker):
        """reset() removes all recorded latencies."""
        for i in range(3):
            tracker.record_stream_start(f"r{i}")
            tracker.record_first_chunk(f"r{i}")
        tracker.reset()
        assert tracker.get_streaming_stats()["count"] == 0

    def test_reset_clears_pending(self, tracker):
        """reset() also clears pending stream start timestamps."""
        tracker.record_stream_start("pending-stream")
        tracker.reset()
        with tracker._lock:
            assert len(tracker._pending) == 0

    def test_reset_allows_fresh_recording(self, tracker):
        """After reset, new recordings work normally."""
        tracker.record_stream_start("x")
        tracker.record_first_chunk("x")
        tracker.reset()
        tracker.record_stream_start("y")
        lat = tracker.record_first_chunk("y")
        assert lat is not None and lat >= 0
        assert tracker.get_streaming_stats()["count"] == 1


# ---------------------------------------------------------------------------
# Unit tests: Thread safety
# ---------------------------------------------------------------------------

class TestStreamingTrackerThreadSafety:
    """Concurrent access must not corrupt state."""

    def test_concurrent_record_does_not_corrupt(self, tracker):
        """Multiple threads calling record_stream_start/first_chunk are all recorded."""
        n = 50
        barrier = threading.Barrier(n)

        def start_and_chunk(i):
            barrier.wait()
            sid = f"thread-{i}"
            tracker.record_stream_start(sid)
            tracker.record_first_chunk(sid)

        threads = [threading.Thread(target=start_and_chunk, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert tracker.get_streaming_stats()["count"] == n

    def test_concurrent_get_streaming_stats_does_not_raise(self, tracker):
        """get_streaming_stats() can be called while records are being added."""
        stop = threading.Event()
        errors = []

        def writer():
            for i in range(100):
                tracker.record_stream_start(f"w{i}")
                tracker.record_first_chunk(f"w{i}")

        def reader():
            while not stop.is_set():
                try:
                    tracker.get_streaming_stats()
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
# Integration tests: ChatBridge instrumentation
# ---------------------------------------------------------------------------

class TestChatBridgeInstrumentation:
    """Tests for latency_tracker parameter in handle_message()."""

    @pytest.mark.asyncio
    async def test_handle_message_records_stream_start_and_first_chunk(self, bridge):
        """handle_message() with a tracker records start and first chunk."""
        tracker = StreamingLatencyTracker()
        stream_id = "test-session-001"

        generator = await bridge.handle_message(
            "Hello, how are you?",
            session_id=stream_id,
            latency_tracker=tracker,
        )
        # Consume the first chunk
        async for chunk in generator:
            break  # just need the first chunk

        stats = tracker.get_streaming_stats()
        assert stats["count"] == 1
        assert stats["p50"] >= 0.0

    @pytest.mark.asyncio
    async def test_general_chat_first_chunk_within_500ms(self, bridge):
        """For general_chat intent, first chunk arrives within 500ms."""
        tracker = StreamingLatencyTracker()
        stream_id = "perf-test-session"

        t0 = time.monotonic()
        generator = await bridge.handle_message(
            "Hello, just chatting",
            session_id=stream_id,
            latency_tracker=tracker,
        )
        # Get first chunk
        async for chunk in generator:
            elapsed_ms = (time.monotonic() - t0) * 1000
            break

        assert elapsed_ms < 500.0, (
            f"First chunk arrived after {elapsed_ms:.1f}ms (expected < 500ms)"
        )

    @pytest.mark.asyncio
    async def test_handle_message_without_tracker_still_works(self, bridge):
        """handle_message() without a tracker works normally (no crash)."""
        generator = await bridge.handle_message(
            "Hello",
            session_id="session-no-tracker",
        )
        chunks = []
        async for chunk in generator:
            chunks.append(chunk)
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_streaming_latency_within_target_after_multiple_calls(self, bridge):
        """After 5 general_chat calls, p99 is within the 500ms target."""
        tracker = StreamingLatencyTracker()

        for i in range(5):
            gen = await bridge.handle_message(
                f"Hello message {i}",
                session_id=f"session-{i}",
                latency_tracker=tracker,
            )
            async for chunk in gen:
                break  # just need first chunk

        assert tracker.check_streaming_target(500), (
            f"p99 streaming latency exceeded 500ms: {tracker.get_streaming_stats()}"
        )


# ---------------------------------------------------------------------------
# Integration tests: GET /api/streaming-latency endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_streaming_latency_endpoint_returns_200(server):
    """GET /api/streaming-latency responds with HTTP 200."""
    async with ClientSession() as session:
        async with session.get("http://127.0.0.1:18091/api/streaming-latency") as resp:
            assert resp.status == 200


@pytest.mark.asyncio
async def test_get_streaming_latency_endpoint_returns_valid_json(server):
    """GET /api/streaming-latency returns parseable JSON."""
    async with ClientSession() as session:
        async with session.get("http://127.0.0.1:18091/api/streaming-latency") as resp:
            body = await resp.json()
            assert isinstance(body, dict)


@pytest.mark.asyncio
async def test_get_streaming_latency_endpoint_contains_all_required_fields(server):
    """GET /api/streaming-latency response includes all required stat fields."""
    async with ClientSession() as session:
        async with session.get("http://127.0.0.1:18091/api/streaming-latency") as resp:
            body = await resp.json()

    required = {
        "p50", "p95", "p99", "max", "mean", "count", "within_500ms_pct",
        "target_ms", "target_met", "timestamp",
    }
    missing = required - set(body.keys())
    assert not missing, f"Missing fields in /api/streaming-latency response: {missing}"


@pytest.mark.asyncio
async def test_get_streaming_latency_endpoint_target_ms_is_500(server):
    """GET /api/streaming-latency response reports target_ms = 500."""
    async with ClientSession() as session:
        async with session.get("http://127.0.0.1:18091/api/streaming-latency") as resp:
            body = await resp.json()
    assert body["target_ms"] == 500


@pytest.mark.asyncio
async def test_get_streaming_latency_endpoint_empty_tracker_passes_target(server):
    """With no recorded streams, target_met is True (vacuously passing)."""
    server.streaming_latency_tracker.reset()
    async with ClientSession() as session:
        async with session.get("http://127.0.0.1:18091/api/streaming-latency") as resp:
            body = await resp.json()
    assert body["target_met"] is True
    assert body["count"] == 0
