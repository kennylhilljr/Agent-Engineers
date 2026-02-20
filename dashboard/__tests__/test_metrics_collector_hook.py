"""Tests for Metrics Collector Hook (AI-171 / REQ-TECH-006).

Tests the integration between AgentMetricsCollector and DashboardServer:
  - Registering a callback works
  - _record_event calls registered callbacks
  - Callback receives correct event data
  - Multiple callbacks all called
  - Removing/deregistering a callback works
  - WebSocket clients receive agent_event when collector records
  - Backlog sent on WebSocket connect

Acceptance criteria (REQ-TECH-006):
  - Metrics collector hook integrated
  - Events broadcast to all clients
  - No event loss
  - Backlog available on reconnect (last N events)
  - Good performance
"""

import asyncio
import json
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from aiohttp import ClientSession, WSMsgType

from dashboard.collector import AgentMetricsCollector
from dashboard.server import DashboardServer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_collector(tmp_path: Path) -> AgentMetricsCollector:
    """Create a fresh AgentMetricsCollector backed by a temp directory."""
    return AgentMetricsCollector(project_name="test-hook", metrics_dir=tmp_path)


async def _ws_recv(ws, timeout: float = 3.0) -> dict:
    """Receive one TEXT WebSocket message and return as dict."""
    msg = await ws.receive(timeout=timeout)
    assert msg.type == WSMsgType.TEXT, f"Expected TEXT, got {msg.type}: {msg!r}"
    return json.loads(msg.data)


async def _drain_until_type(ws, expected_type: str, timeout: float = 3.0) -> dict:
    """Read WebSocket messages until one with the expected type is received."""
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            raise TimeoutError(f"Did not receive '{expected_type}' within {timeout}s")
        data = await _ws_recv(ws, timeout=remaining)
        if data.get("type") == expected_type:
            return data


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_metrics_dir():
    """Temporary directory for metrics files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def collector(temp_metrics_dir):
    """A fresh AgentMetricsCollector."""
    return _make_collector(temp_metrics_dir)


@pytest_asyncio.fixture
async def server_with_collector(temp_metrics_dir):
    """DashboardServer started with a collector pre-wired (AI-171).

    Yields (server, collector) tuple and cleans up after each test.
    """
    from aiohttp import web

    coll = _make_collector(temp_metrics_dir)

    srv = DashboardServer(
        project_name="test-hook-ws",
        metrics_dir=temp_metrics_dir,
        port=18471,
        host="127.0.0.1",
        collector=coll,
    )

    runner = web.AppRunner(srv.app)
    await runner.setup()
    site = web.TCPSite(runner, srv.host, srv.port)
    await site.start()

    # Allow broadcast task to be scheduled
    await asyncio.sleep(0.1)

    yield srv, coll

    await runner.cleanup()


BASE = "http://127.0.0.1:18471"
WS_URL = "ws://127.0.0.1:18471/ws"


# ===========================================================================
# Part 1: AgentMetricsCollector callback mechanism (unit tests – no server)
# ===========================================================================

class TestRegisterEventCallback:
    """register_event_callback / unregister_event_callback unit tests."""

    def test_register_callback_works(self, collector):
        """Registering a callback adds it to the internal list."""
        received = []
        collector.register_event_callback(received.append)
        assert len(collector._record_event_callbacks) == 1

    def test_register_same_callback_twice_is_idempotent(self, collector):
        """Registering the same callback twice only adds it once."""
        cb = lambda e: None  # noqa: E731
        collector.register_event_callback(cb)
        collector.register_event_callback(cb)
        assert collector._record_event_callbacks.count(cb) == 1

    def test_unregister_existing_callback(self, collector):
        """unregister_event_callback removes a registered callback."""
        received = []
        collector.register_event_callback(received.append)
        assert len(collector._record_event_callbacks) == 1

        collector.unregister_event_callback(received.append)
        assert len(collector._record_event_callbacks) == 0

    def test_unregister_unregistered_callback_is_noop(self, collector):
        """Removing a callback that was never registered does not raise."""
        def never_registered(e):
            pass

        # Should not raise
        collector.unregister_event_callback(never_registered)
        assert len(collector._record_event_callbacks) == 0


class TestRecordEventCallsCallbacks:
    """_record_event must call all registered callbacks with the AgentEvent."""

    def _run_single_event(self, collector):
        """Helper: track a single agent delegation and return the recorded event."""
        session_id = collector.start_session()
        with collector.track_agent("coding", "AI-171", "claude-sonnet-4-5", session_id=session_id) as tracker:
            tracker.add_tokens(input_tokens=100, output_tokens=200)
        collector.end_session(session_id)

    def test_callback_called_once_per_event(self, collector):
        """Callback is invoked exactly once when one event is recorded."""
        received = []
        collector.register_event_callback(received.append)
        self._run_single_event(collector)
        assert len(received) == 1

    def test_callback_receives_agent_event_dict(self, collector):
        """Callback argument is a dict matching the recorded AgentEvent."""
        received = []
        collector.register_event_callback(received.append)
        self._run_single_event(collector)

        event = received[0]
        assert isinstance(event, dict)
        # Core AgentEvent fields
        assert "agent_name" in event
        assert "event_id" in event
        assert "started_at" in event
        assert "ended_at" in event
        assert "status" in event
        assert "total_tokens" in event

    def test_callback_receives_correct_agent_name(self, collector):
        """The event dict passed to the callback contains the correct agent name."""
        received = []
        collector.register_event_callback(received.append)
        self._run_single_event(collector)
        assert received[0]["agent_name"] == "coding"

    def test_callback_receives_correct_ticket_key(self, collector):
        """The event dict passed to the callback contains the correct ticket key."""
        received = []
        collector.register_event_callback(received.append)
        self._run_single_event(collector)
        assert received[0]["ticket_key"] == "AI-171"

    def test_callback_receives_correct_token_counts(self, collector):
        """Token counts in the callback event match what was added to the tracker."""
        received = []
        collector.register_event_callback(received.append)

        session_id = collector.start_session()
        with collector.track_agent("coding", "AI-171", "claude-sonnet-4-5", session_id=session_id) as tracker:
            tracker.add_tokens(input_tokens=500, output_tokens=1000)
        collector.end_session(session_id)

        event = received[0]
        assert event["input_tokens"] == 500
        assert event["output_tokens"] == 1000
        assert event["total_tokens"] == 1500

    def test_callback_receives_success_status(self, collector):
        """Status is 'success' for a normally completed delegation."""
        received = []
        collector.register_event_callback(received.append)
        self._run_single_event(collector)
        assert received[0]["status"] == "success"

    def test_multiple_callbacks_all_called(self, collector):
        """All registered callbacks are invoked for each event."""
        results_a = []
        results_b = []
        results_c = []

        collector.register_event_callback(results_a.append)
        collector.register_event_callback(results_b.append)
        collector.register_event_callback(results_c.append)

        self._run_single_event(collector)

        assert len(results_a) == 1
        assert len(results_b) == 1
        assert len(results_c) == 1

        # All must have received the same event
        assert results_a[0]["event_id"] == results_b[0]["event_id"] == results_c[0]["event_id"]

    def test_unregistered_callback_not_called(self, collector):
        """A callback that has been unregistered is not invoked."""
        results_registered = []
        results_removed = []

        collector.register_event_callback(results_registered.append)
        collector.register_event_callback(results_removed.append)
        collector.unregister_event_callback(results_removed.append)

        self._run_single_event(collector)

        assert len(results_registered) == 1
        assert len(results_removed) == 0  # was unregistered

    def test_error_in_callback_does_not_prevent_other_callbacks(self, collector):
        """A failing callback must not prevent other callbacks from running."""

        def bad_callback(e):
            raise RuntimeError("Intentional error in callback")

        good_results = []
        collector.register_event_callback(bad_callback)
        collector.register_event_callback(good_results.append)

        # Should not raise even though bad_callback raises
        self._run_single_event(collector)
        assert len(good_results) == 1

    def test_multiple_events_multiple_callback_calls(self, collector):
        """Each call to _record_event invokes registered callbacks."""
        received = []
        collector.register_event_callback(received.append)

        session_id = collector.start_session()
        for ticket in ("AI-100", "AI-101", "AI-102"):
            with collector.track_agent("coding", ticket, "claude-sonnet-4-5", session_id=session_id):
                pass
        collector.end_session(session_id)

        assert len(received) == 3
        tickets = [e["ticket_key"] for e in received]
        assert "AI-100" in tickets
        assert "AI-101" in tickets
        assert "AI-102" in tickets


# ===========================================================================
# Part 2: DashboardServer integration (WebSocket tests)
# ===========================================================================

class TestDashboardServerCollectorIntegration:
    """DashboardServer registers with collector and broadcasts agent_event messages."""

    @pytest.mark.asyncio
    async def test_server_registers_callback_on_collector(self, server_with_collector):
        """DashboardServer registers _on_new_event callback on the collector."""
        server, coll = server_with_collector
        # The server should have registered exactly one callback on the collector
        assert len(coll._record_event_callbacks) == 1

    @pytest.mark.asyncio
    async def test_websocket_client_receives_agent_event_on_record(self, server_with_collector):
        """When the collector records an event the WS client receives agent_event."""
        server, coll = server_with_collector

        async with ClientSession() as session:
            async with session.ws_connect(WS_URL) as ws:
                # Consume the initial metrics_update
                data = await _ws_recv(ws)
                assert data["type"] == "metrics_update"

                # Trigger a collector event (synchronous path outside async loop)
                # Because _on_new_event uses asyncio.ensure_future, we trigger from
                # inside the running loop to ensure it is scheduled correctly.
                async def _trigger():
                    sess_id = coll.start_session()
                    with coll.track_agent("coding", "AI-171", "claude-sonnet-4-5", session_id=sess_id):
                        pass
                    coll.end_session(sess_id)

                await _trigger()

                # The server should broadcast the agent_event
                data = await _drain_until_type(ws, "agent_event")

                assert data["type"] == "agent_event"
                assert data["agent"] == "coding"
                assert "timestamp" in data
                assert "details" in data

    @pytest.mark.asyncio
    async def test_agent_event_details_are_correct(self, server_with_collector):
        """agent_event details contain the expected fields from the collector event."""
        server, coll = server_with_collector

        async with ClientSession() as session:
            async with session.ws_connect(WS_URL) as ws:
                await _ws_recv(ws)  # consume metrics_update

                async def _trigger():
                    sess_id = coll.start_session()
                    with coll.track_agent("github", "AI-171", "claude-sonnet-4-5", session_id=sess_id) as tracker:
                        tracker.add_tokens(input_tokens=50, output_tokens=100)
                    coll.end_session(sess_id)

                await _trigger()

                data = await _drain_until_type(ws, "agent_event")

                assert data["agent"] == "github"
                details = data["details"]
                assert details["input_tokens"] == 50
                assert details["output_tokens"] == 100
                assert details["total_tokens"] == 150
                assert details["ticket_key"] == "AI-171"

    @pytest.mark.asyncio
    async def test_multiple_clients_receive_agent_event(self, server_with_collector):
        """All connected WebSocket clients receive the agent_event broadcast."""
        server, coll = server_with_collector

        async with ClientSession() as session:
            async with session.ws_connect(WS_URL) as ws1, \
                       session.ws_connect(WS_URL) as ws2:

                # Consume initial messages
                await _ws_recv(ws1)
                await _ws_recv(ws2)

                async def _trigger():
                    sess_id = coll.start_session()
                    with coll.track_agent("linear", "AI-171", "claude-sonnet-4-5", session_id=sess_id):
                        pass
                    coll.end_session(sess_id)

                await _trigger()

                data1 = await _drain_until_type(ws1, "agent_event")
                data2 = await _drain_until_type(ws2, "agent_event")

                assert data1["type"] == "agent_event"
                assert data2["type"] == "agent_event"
                # Both clients received the same event
                assert data1["details"]["event_id"] == data2["details"]["event_id"]

    @pytest.mark.asyncio
    async def test_no_event_loss_under_multiple_events(self, server_with_collector):
        """All collector events are broadcast; no event loss."""
        server, coll = server_with_collector
        n_events = 5

        async with ClientSession() as session:
            async with session.ws_connect(WS_URL) as ws:
                await _ws_recv(ws)  # consume metrics_update

                async def _trigger_n():
                    sess_id = coll.start_session()
                    for i in range(n_events):
                        with coll.track_agent("coding", f"AI-{i}", "claude-sonnet-4-5", session_id=sess_id):
                            pass
                    coll.end_session(sess_id)

                await _trigger_n()

                received_events = []
                try:
                    while len(received_events) < n_events:
                        data = await _ws_recv(ws, timeout=3.0)
                        if data.get("type") == "agent_event":
                            received_events.append(data)
                except asyncio.TimeoutError:
                    pass

                assert len(received_events) == n_events, (
                    f"Expected {n_events} agent_event messages, got {len(received_events)}"
                )

    @pytest.mark.asyncio
    async def test_backlog_sent_on_websocket_connect(self, server_with_collector):
        """When a client connects after events have been recorded, the backlog is sent."""
        server, coll = server_with_collector

        # Record events BEFORE a client connects
        async def _trigger():
            sess_id = coll.start_session()
            for i in range(3):
                with coll.track_agent("coding", f"AI-{i}", "claude-sonnet-4-5", session_id=sess_id):
                    pass
            coll.end_session(sess_id)

        await _trigger()

        # Give the server a moment to process callbacks
        await asyncio.sleep(0.1)

        # The backlog should have 3 entries by now
        assert len(server._agent_event_backlog) == 3

        async with ClientSession() as session:
            async with session.ws_connect(WS_URL) as ws:
                # First message is always metrics_update
                first = await _ws_recv(ws)
                assert first["type"] == "metrics_update"

                # Second message should be the backlog
                second = await _ws_recv(ws)
                assert second["type"] == "backlog"
                assert "events" in second
                assert "timestamp" in second
                assert len(second["events"]) == 3

    @pytest.mark.asyncio
    async def test_backlog_events_are_agent_event_messages(self, server_with_collector):
        """Backlog entries are fully-formatted agent_event messages."""
        server, coll = server_with_collector

        async def _trigger():
            sess_id = coll.start_session()
            with coll.track_agent("github", "AI-171", "claude-sonnet-4-5", session_id=sess_id):
                pass
            coll.end_session(sess_id)

        await _trigger()
        await asyncio.sleep(0.1)

        async with ClientSession() as session:
            async with session.ws_connect(WS_URL) as ws:
                await _ws_recv(ws)  # metrics_update

                backlog_msg = await _ws_recv(ws)
                assert backlog_msg["type"] == "backlog"

                for entry in backlog_msg["events"]:
                    assert entry["type"] == "agent_event"
                    assert "agent" in entry
                    assert "event_type" in entry
                    assert "details" in entry
                    assert "timestamp" in entry

    @pytest.mark.asyncio
    async def test_backlog_limited_to_last_20_events(self, server_with_collector):
        """Backlog contains at most the last 20 agent events."""
        server, coll = server_with_collector
        n = DashboardServer._AGENT_EVENT_BACKLOG_MAX + 5  # exceed the limit

        async def _trigger():
            sess_id = coll.start_session()
            for i in range(n):
                with coll.track_agent("coding", f"AI-{i}", "claude-sonnet-4-5", session_id=sess_id):
                    pass
            coll.end_session(sess_id)

        await _trigger()
        await asyncio.sleep(0.1)

        # The backlog should be capped at _AGENT_EVENT_BACKLOG_MAX
        assert len(server._agent_event_backlog) == DashboardServer._AGENT_EVENT_BACKLOG_MAX

    @pytest.mark.asyncio
    async def test_no_backlog_message_when_no_events(self, server_with_collector):
        """When no collector events have occurred, no backlog message is sent."""
        server, coll = server_with_collector

        async with ClientSession() as session:
            async with session.ws_connect(WS_URL) as ws:
                first = await _ws_recv(ws)
                assert first["type"] == "metrics_update"

                # Should NOT receive a backlog message (backlog is empty)
                # We verify by checking that the server's backlog is empty
                assert len(server._agent_event_backlog) == 0

                # Any further messages would be periodic metrics_update;
                # confirm no stray backlog arrives within a short window.
                try:
                    msg = await _ws_recv(ws, timeout=0.5)
                    # If we got a message, it must not be a backlog
                    assert msg["type"] != "backlog", "Unexpected backlog message when backlog is empty"
                except asyncio.TimeoutError:
                    pass  # Expected: no extra messages

    @pytest.mark.asyncio
    async def test_server_created_without_collector_works_normally(self, temp_metrics_dir):
        """DashboardServer without a collector works like before (no backlog, no hook)."""
        from aiohttp import web

        srv = DashboardServer(
            project_name="test-no-collector",
            metrics_dir=temp_metrics_dir,
            port=18472,
            host="127.0.0.1",
            # No collector= argument
        )

        runner = web.AppRunner(srv.app)
        await runner.setup()
        site = web.TCPSite(runner, srv.host, srv.port)
        await site.start()

        try:
            assert srv._agent_event_backlog == []

            async with ClientSession() as session:
                async with session.ws_connect("ws://127.0.0.1:18472/ws") as ws:
                    first = await _ws_recv(ws)
                    assert first["type"] == "metrics_update"

        finally:
            await runner.cleanup()


if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v", "--tb=short", "-s"])
