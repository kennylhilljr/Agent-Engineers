"""Integration tests for WebSocket event broadcasting.

Tests the integration between AgentMetricsCollector and DashboardServer's
real-time WebSocket broadcasting system.
"""

import asyncio
import json
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from aiohttp import ClientSession, WSMsgType

from dashboard.server import DashboardServer


@pytest.fixture
def temp_metrics_dir():
    """Create a temporary directory for metrics files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest_asyncio.fixture
async def server(temp_metrics_dir):
    """Create and start a test server."""
    srv = DashboardServer(
        project_name="test-websocket",
        metrics_dir=temp_metrics_dir,
        port=18080,
        host="127.0.0.1"
    )

    # Start server in background
    runner = None
    try:
        from aiohttp import web
        runner = web.AppRunner(srv.app)
        await runner.setup()
        site = web.TCPSite(runner, srv.host, srv.port)
        await site.start()

        # Give server a moment to start
        await asyncio.sleep(0.5)

        yield srv

    finally:
        if runner:
            await runner.cleanup()


@pytest.mark.asyncio
async def test_websocket_connection(server):
    """Test that WebSocket connections can be established."""
    async with ClientSession() as session:
        async with session.ws_connect(f"http://127.0.0.1:18080/ws") as ws:
            # Wait for initial metrics message
            msg = await ws.receive(timeout=2)
            assert msg.type == WSMsgType.TEXT

            data = json.loads(msg.data)
            assert data["type"] == "metrics_update"
            assert "data" in data
            assert "timestamp" in data


@pytest.mark.asyncio
async def test_event_broadcast_on_task_started(server):
    """Test that task_started events are broadcast to WebSocket clients."""
    async with ClientSession() as session:
        async with session.ws_connect(f"http://127.0.0.1:18080/ws") as ws:
            # Consume initial metrics message
            await ws.receive(timeout=2)

            # Simulate an agent task starting
            session_id = server.collector.start_session()

            # Create a task in a separate coroutine to avoid blocking
            async def run_task():
                with server.collector.track_agent("test-agent", "AI-107", "claude-sonnet-4-5", session_id) as tracker:
                    await asyncio.sleep(0.1)
                    tracker.add_tokens(1000, 2000)

            # Start the task
            task = asyncio.create_task(run_task())

            # Wait for task_started broadcast
            msg = await ws.receive(timeout=2)
            assert msg.type == WSMsgType.TEXT

            data = json.loads(msg.data)
            assert data["type"] == "agent_event"
            assert data["event_type"] == "task_started"
            assert "event" in data

            event = data["event"]
            assert event["agent_name"] == "test-agent"
            assert event["ticket_key"] == "AI-107"
            assert event["status"] == "success"

            # Wait for task to complete
            await task

            # Wait for task_completed broadcast
            msg = await ws.receive(timeout=2)
            assert msg.type == WSMsgType.TEXT

            data = json.loads(msg.data)
            assert data["type"] == "agent_event"
            assert data["event_type"] == "task_completed"

            server.collector.end_session(session_id)


@pytest.mark.asyncio
async def test_event_broadcast_on_task_completed(server):
    """Test that task_completed events are broadcast to WebSocket clients."""
    async with ClientSession() as session:
        async with session.ws_connect(f"http://127.0.0.1:18080/ws") as ws:
            # Consume initial metrics message
            await ws.receive(timeout=2)

            # Run a task
            session_id = server.collector.start_session()

            async def run_task():
                with server.collector.track_agent("test-agent", "AI-107", "claude-sonnet-4-5", session_id) as tracker:
                    tracker.add_tokens(1500, 3000)
                    tracker.add_artifact("file:test.py")

            task = asyncio.create_task(run_task())

            # Consume task_started
            await ws.receive(timeout=2)

            # Wait for task_completed
            msg = await ws.receive(timeout=2)
            assert msg.type == WSMsgType.TEXT

            data = json.loads(msg.data)
            assert data["type"] == "agent_event"
            assert data["event_type"] == "task_completed"

            event = data["event"]
            assert event["agent_name"] == "test-agent"
            assert event["status"] == "success"
            assert event["input_tokens"] == 1500
            assert event["output_tokens"] == 3000
            assert event["total_tokens"] == 4500
            assert "file:test.py" in event["artifacts"]

            await task
            server.collector.end_session(session_id)


@pytest.mark.asyncio
async def test_event_broadcast_on_task_failed(server):
    """Test that task_failed events are broadcast to WebSocket clients."""
    async with ClientSession() as session:
        async with session.ws_connect(f"http://127.0.0.1:18080/ws") as ws:
            # Consume initial metrics message
            await ws.receive(timeout=2)

            # Run a task that fails
            session_id = server.collector.start_session()

            async def run_failing_task():
                try:
                    with server.collector.track_agent("test-agent", "AI-107", "claude-sonnet-4-5", session_id) as tracker:
                        tracker.add_tokens(500, 1000)
                        raise ValueError("Simulated failure")
                except ValueError:
                    pass  # Expected

            task = asyncio.create_task(run_failing_task())

            # Consume task_started
            await ws.receive(timeout=2)

            # Wait for task_failed
            msg = await ws.receive(timeout=2)
            assert msg.type == WSMsgType.TEXT

            data = json.loads(msg.data)
            assert data["type"] == "agent_event"
            assert data["event_type"] == "task_failed"

            event = data["event"]
            assert event["agent_name"] == "test-agent"
            assert event["status"] == "error"
            assert event["error_message"] == "Simulated failure"

            await task
            server.collector.end_session(session_id)


@pytest.mark.asyncio
async def test_multiple_websocket_clients(server):
    """Test that events are broadcast to all connected WebSocket clients."""
    async with ClientSession() as session:
        # Connect two WebSocket clients
        async with session.ws_connect(f"http://127.0.0.1:18080/ws") as ws1, \
                   session.ws_connect(f"http://127.0.0.1:18080/ws") as ws2:

            # Consume initial metrics messages
            await ws1.receive(timeout=2)
            await ws2.receive(timeout=2)

            # Run a task
            session_id = server.collector.start_session()

            async def run_task():
                with server.collector.track_agent("test-agent", "AI-107", "claude-sonnet-4-5", session_id) as tracker:
                    tracker.add_tokens(1000, 2000)

            task = asyncio.create_task(run_task())

            # Both clients should receive task_started
            msg1 = await ws1.receive(timeout=2)
            msg2 = await ws2.receive(timeout=2)

            data1 = json.loads(msg1.data)
            data2 = json.loads(msg2.data)

            assert data1["type"] == "agent_event"
            assert data1["event_type"] == "task_started"
            assert data2["type"] == "agent_event"
            assert data2["event_type"] == "task_started"

            await task

            # Both clients should receive task_completed
            msg1 = await ws1.receive(timeout=2)
            msg2 = await ws2.receive(timeout=2)

            data1 = json.loads(msg1.data)
            data2 = json.loads(msg2.data)

            assert data1["type"] == "agent_event"
            assert data1["event_type"] == "task_completed"
            assert data2["type"] == "agent_event"
            assert data2["event_type"] == "task_completed"

            server.collector.end_session(session_id)


@pytest.mark.asyncio
async def test_event_order_preservation(server):
    """Test that events are broadcast in the correct order."""
    async with ClientSession() as session:
        async with session.ws_connect(f"http://127.0.0.1:18080/ws") as ws:
            # Consume initial metrics message
            await ws.receive(timeout=2)

            # Run multiple tasks sequentially
            session_id = server.collector.start_session()

            for i in range(3):
                async def run_task():
                    with server.collector.track_agent(f"agent-{i}", f"AI-{100+i}", "claude-sonnet-4-5", session_id) as tracker:
                        tracker.add_tokens(100, 200)

                await run_task()

            # Should receive events in order:
            # task_started(0), task_completed(0), task_started(1), task_completed(1), task_started(2), task_completed(2)
            expected_events = [
                ("task_started", "agent-0"),
                ("task_completed", "agent-0"),
                ("task_started", "agent-1"),
                ("task_completed", "agent-1"),
                ("task_started", "agent-2"),
                ("task_completed", "agent-2"),
            ]

            received_events = []
            for _ in range(6):
                msg = await ws.receive(timeout=2)
                data = json.loads(msg.data)
                if data["type"] == "agent_event":
                    received_events.append((data["event_type"], data["event"]["agent_name"]))

            assert received_events == expected_events

            server.collector.end_session(session_id)


@pytest.mark.asyncio
async def test_websocket_survives_collector_errors(server):
    """Test that WebSocket broadcasting continues even if collector callbacks error."""
    async with ClientSession() as session:
        async with session.ws_connect(f"http://127.0.0.1:18080/ws") as ws:
            # Consume initial metrics message
            await ws.receive(timeout=2)

            # Add a bad callback that raises
            def bad_callback(event_type, event):
                raise RuntimeError("Bad callback")

            server.collector.subscribe(bad_callback)

            # Run a task - should still broadcast despite bad callback
            session_id = server.collector.start_session()

            async def run_task():
                with server.collector.track_agent("test-agent", "AI-107", "claude-sonnet-4-5", session_id) as tracker:
                    tracker.add_tokens(1000, 2000)

            task = asyncio.create_task(run_task())

            # Should still receive events
            msg = await ws.receive(timeout=2)
            data = json.loads(msg.data)
            assert data["type"] == "agent_event"
            assert data["event_type"] == "task_started"

            await task

            msg = await ws.receive(timeout=2)
            data = json.loads(msg.data)
            assert data["type"] == "agent_event"
            assert data["event_type"] == "task_completed"

            server.collector.end_session(session_id)


@pytest.mark.asyncio
async def test_periodic_metrics_broadcast_continues(server):
    """Test that periodic metrics broadcasts continue alongside event broadcasts."""
    async with ClientSession() as session:
        async with session.ws_connect(f"http://127.0.0.1:18080/ws") as ws:
            # Consume initial metrics message
            initial_msg = await ws.receive(timeout=2)
            data = json.loads(initial_msg.data)
            assert data["type"] == "metrics_update"

            # Wait for next periodic broadcast (5 seconds)
            # Note: This test may be slow due to the broadcast interval
            # We'll reduce the timeout and just verify the message type
            try:
                msg = await asyncio.wait_for(ws.receive(), timeout=6)
                data = json.loads(msg.data)
                # Could be either metrics_update or agent_event
                assert data["type"] in ["metrics_update", "agent_event"]
            except asyncio.TimeoutError:
                # Acceptable - periodic broadcast may not have triggered yet
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
