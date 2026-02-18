"""Tests for WebSocket Protocol & Messages (AI-168 / REQ-TECH-003).

Tests all 7 required WebSocket message types:
  - agent_status   – POST /api/agent-status
  - agent_event    – POST /api/agent-event
  - reasoning      – POST /api/reasoning  (AI-158)
  - code_stream    – POST /api/code-stream (AI-163)
  - chat_message   – POST /api/chat-stream
  - metrics_update – sent on connect and periodically
  - control_ack    – POST /api/control-ack

Acceptance criteria (REQ-TECH-003):
  - All message types work
  - Correct JSON format with required fields
  - Message order preserved
  - No message loss
  - Latency < 100ms (local)
"""

import asyncio
import json
import tempfile
import time
from pathlib import Path

import pytest
import pytest_asyncio
from aiohttp import ClientSession, WSMsgType

from dashboard.server import DashboardServer

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_metrics_dir():
    """Create a temporary directory for metrics files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest_asyncio.fixture
async def server(temp_metrics_dir):
    """Start a DashboardServer on a free port for testing.

    Yields the running server instance and cleans up after each test.
    """
    from aiohttp import web

    srv = DashboardServer(
        project_name="test-ws-protocol",
        metrics_dir=temp_metrics_dir,
        port=18421,
        host="127.0.0.1",
    )

    runner = web.AppRunner(srv.app)
    await runner.setup()
    site = web.TCPSite(runner, srv.host, srv.port)
    await site.start()

    # Short settle time so the broadcast task is scheduled
    await asyncio.sleep(0.1)

    yield srv

    await runner.cleanup()


BASE = "http://127.0.0.1:18421"
WS_URL = "ws://127.0.0.1:18421/ws"


async def _ws_recv(ws, timeout: float = 2.0) -> dict:
    """Receive one TEXT WebSocket message and return as dict."""
    msg = await ws.receive(timeout=timeout)
    assert msg.type == WSMsgType.TEXT, f"Expected TEXT, got {msg.type}"
    return json.loads(msg.data)


# ---------------------------------------------------------------------------
# 1. WebSocket connection & initial metrics_update
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_websocket_connection_established(server):
    """WebSocket connection at /ws is accepted."""
    async with ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws:
            assert not ws.closed


@pytest.mark.asyncio
async def test_receives_metrics_update_on_connect(server):
    """Client receives a metrics_update message immediately on connect."""
    async with ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws:
            data = await _ws_recv(ws)
            assert data["type"] == "metrics_update"
            assert "data" in data
            assert "timestamp" in data


# ---------------------------------------------------------------------------
# 2. agent_status  (POST /api/agent-status)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_agent_status_broadcasts(server):
    """POST /api/agent-status broadcasts an agent_status WS message."""
    async with ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws:
            # Consume initial metrics_update
            await _ws_recv(ws)

            t0 = time.monotonic()
            resp = await session.post(
                f"{BASE}/api/agent-status",
                json={"agent": "coding", "status": "working", "ticket": "AI-168"},
            )
            assert resp.status == 200
            body = await resp.json()
            assert body["success"] is True

            data = await _ws_recv(ws)
            latency_ms = (time.monotonic() - t0) * 1000

            assert data["type"] == "agent_status"
            assert data["agent"] == "coding"
            assert data["status"] == "working"
            assert data["ticket"] == "AI-168"
            assert "timestamp" in data
            assert latency_ms < 100, f"Latency {latency_ms:.1f}ms exceeds 100ms"


@pytest.mark.asyncio
async def test_agent_status_all_valid_statuses(server):
    """All four valid status values are accepted."""
    async with ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws:
            await _ws_recv(ws)  # consume initial metrics

            for status in ("idle", "working", "paused", "error"):
                resp = await session.post(
                    f"{BASE}/api/agent-status",
                    json={"agent": "coding", "status": status},
                )
                assert resp.status == 200
                data = await _ws_recv(ws)
                assert data["type"] == "agent_status"
                assert data["status"] == status


@pytest.mark.asyncio
async def test_agent_status_invalid_status_rejected(server):
    """Invalid status values are rejected with HTTP 400."""
    async with ClientSession() as session:
        resp = await session.post(
            f"{BASE}/api/agent-status",
            json={"agent": "coding", "status": "invalid"},
        )
        assert resp.status == 400


@pytest.mark.asyncio
async def test_agent_status_missing_agent_rejected(server):
    """Missing 'agent' field is rejected with HTTP 400."""
    async with ClientSession() as session:
        resp = await session.post(
            f"{BASE}/api/agent-status",
            json={"status": "idle"},
        )
        assert resp.status == 400


# ---------------------------------------------------------------------------
# 3. agent_event  (POST /api/agent-event)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_agent_event_broadcasts(server):
    """POST /api/agent-event broadcasts an agent_event WS message."""
    async with ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws:
            await _ws_recv(ws)

            t0 = time.monotonic()
            resp = await session.post(
                f"{BASE}/api/agent-event",
                json={
                    "agent": "coding",
                    "event_type": "started",
                    "ticket": "AI-168",
                    "details": {"pr": "123"},
                },
            )
            assert resp.status == 200
            body = await resp.json()
            assert body["success"] is True

            data = await _ws_recv(ws)
            latency_ms = (time.monotonic() - t0) * 1000

            assert data["type"] == "agent_event"
            assert data["agent"] == "coding"
            assert data["event_type"] == "started"
            assert data["ticket"] == "AI-168"
            assert data["details"] == {"pr": "123"}
            assert "timestamp" in data
            assert latency_ms < 100, f"Latency {latency_ms:.1f}ms exceeds 100ms"


@pytest.mark.asyncio
async def test_agent_event_all_valid_event_types(server):
    """All three valid event_type values are accepted."""
    async with ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws:
            await _ws_recv(ws)

            for event_type in ("started", "completed", "failed"):
                resp = await session.post(
                    f"{BASE}/api/agent-event",
                    json={"agent": "coding", "event_type": event_type},
                )
                assert resp.status == 200
                data = await _ws_recv(ws)
                assert data["type"] == "agent_event"
                assert data["event_type"] == event_type


@pytest.mark.asyncio
async def test_agent_event_invalid_event_type_rejected(server):
    """Invalid event_type is rejected with HTTP 400."""
    async with ClientSession() as session:
        resp = await session.post(
            f"{BASE}/api/agent-event",
            json={"agent": "coding", "event_type": "unknown"},
        )
        assert resp.status == 400


# ---------------------------------------------------------------------------
# 4. chat_message  (POST /api/chat-stream)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_chat_stream_broadcasts(server):
    """POST /api/chat-stream broadcasts a chat_message WS message."""
    async with ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws:
            await _ws_recv(ws)

            t0 = time.monotonic()
            resp = await session.post(
                f"{BASE}/api/chat-stream",
                json={
                    "content": "Hello world",
                    "is_final": False,
                    "provider": "claude",
                },
            )
            assert resp.status == 200
            body = await resp.json()
            assert body["success"] is True
            assert "stream_id" in body

            data = await _ws_recv(ws)
            latency_ms = (time.monotonic() - t0) * 1000

            assert data["type"] == "chat_message"
            assert data["content"] == "Hello world"
            assert data["is_final"] is False
            assert data["provider"] == "claude"
            assert "stream_id" in data
            assert "timestamp" in data
            assert latency_ms < 100, f"Latency {latency_ms:.1f}ms exceeds 100ms"


@pytest.mark.asyncio
async def test_chat_stream_is_final(server):
    """chat_message with is_final=True is broadcast correctly."""
    async with ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws:
            await _ws_recv(ws)

            resp = await session.post(
                f"{BASE}/api/chat-stream",
                json={"content": "Final chunk", "is_final": True},
            )
            assert resp.status == 200

            data = await _ws_recv(ws)
            assert data["type"] == "chat_message"
            assert data["is_final"] is True


@pytest.mark.asyncio
async def test_chat_stream_stream_id_preserved(server):
    """Provided stream_id is preserved in WS broadcast."""
    stream_id = "test-stream-abc-123"
    async with ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws:
            await _ws_recv(ws)

            await session.post(
                f"{BASE}/api/chat-stream",
                json={"content": "chunk", "stream_id": stream_id},
            )
            data = await _ws_recv(ws)
            assert data["stream_id"] == stream_id


# ---------------------------------------------------------------------------
# 5. control_ack  (POST /api/control-ack)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_control_ack_broadcasts(server):
    """POST /api/control-ack broadcasts a control_ack WS message."""
    async with ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws:
            await _ws_recv(ws)

            t0 = time.monotonic()
            resp = await session.post(
                f"{BASE}/api/control-ack",
                json={
                    "agent": "coding",
                    "command": "pause",
                    "success": True,
                    "message": "Agent paused successfully",
                },
            )
            assert resp.status == 200
            body = await resp.json()
            assert body["success"] is True

            data = await _ws_recv(ws)
            latency_ms = (time.monotonic() - t0) * 1000

            assert data["type"] == "control_ack"
            assert data["agent"] == "coding"
            assert data["command"] == "pause"
            assert data["success"] is True
            assert data["message"] == "Agent paused successfully"
            assert "timestamp" in data
            assert latency_ms < 100, f"Latency {latency_ms:.1f}ms exceeds 100ms"


@pytest.mark.asyncio
async def test_control_ack_resume_command(server):
    """resume command is accepted in control_ack."""
    async with ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws:
            await _ws_recv(ws)

            resp = await session.post(
                f"{BASE}/api/control-ack",
                json={"agent": "coding", "command": "resume", "success": True},
            )
            assert resp.status == 200

            data = await _ws_recv(ws)
            assert data["type"] == "control_ack"
            assert data["command"] == "resume"


@pytest.mark.asyncio
async def test_control_ack_invalid_command_rejected(server):
    """Invalid command is rejected with HTTP 400."""
    async with ClientSession() as session:
        resp = await session.post(
            f"{BASE}/api/control-ack",
            json={"agent": "coding", "command": "stop"},
        )
        assert resp.status == 400


@pytest.mark.asyncio
async def test_control_ack_missing_agent_rejected(server):
    """Missing 'agent' field is rejected with HTTP 400."""
    async with ClientSession() as session:
        resp = await session.post(
            f"{BASE}/api/control-ack",
            json={"command": "pause"},
        )
        assert resp.status == 400


# ---------------------------------------------------------------------------
# 6. reasoning  (POST /api/reasoning – AI-158)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reasoning_type_works(server):
    """POST /api/reasoning broadcasts a reasoning WS message (AI-158 regression)."""
    async with ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws:
            await _ws_recv(ws)

            resp = await session.post(
                f"{BASE}/api/reasoning",
                json={"content": "Delegating to coding agent", "ticket": "AI-168"},
            )
            assert resp.status == 200

            data = await _ws_recv(ws)
            assert data["type"] == "reasoning"
            assert data["content"] == "Delegating to coding agent"
            assert "timestamp" in data


# ---------------------------------------------------------------------------
# 7. code_stream  (POST /api/code-stream – AI-163)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_code_stream_type_works(server):
    """POST /api/code-stream broadcasts a code_stream WS message (AI-163 regression)."""
    async with ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws:
            await _ws_recv(ws)

            resp = await session.post(
                f"{BASE}/api/code-stream",
                json={
                    "agent": "coding",
                    "file_path": "dashboard/server.py",
                    "chunk": "def hello():",
                    "chunk_type": "addition",
                    "is_final": False,
                },
            )
            assert resp.status == 200

            data = await _ws_recv(ws)
            assert data["type"] == "code_stream"
            assert data["chunk"] == "def hello():"
            assert "timestamp" in data


# ---------------------------------------------------------------------------
# 8. Message order preserved for rapid sequential broadcasts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_message_order_preserved_rapid_broadcast(server):
    """Messages arrive in the same order they are posted."""
    async with ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws:
            await _ws_recv(ws)  # consume initial metrics_update

            # Post 5 agent-status messages rapidly
            statuses = ["idle", "working", "paused", "working", "idle"]
            for status in statuses:
                await session.post(
                    f"{BASE}/api/agent-status",
                    json={"agent": "coding", "status": status},
                )

            received = []
            for _ in range(len(statuses)):
                data = await _ws_recv(ws)
                received.append(data["status"])

            assert received == statuses


@pytest.mark.asyncio
async def test_message_order_mixed_types(server):
    """Mixed message types arrive in posted order."""
    async with ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws:
            await _ws_recv(ws)

            # Post one of each new type
            await session.post(
                f"{BASE}/api/agent-status",
                json={"agent": "coding", "status": "working"},
            )
            await session.post(
                f"{BASE}/api/agent-event",
                json={"agent": "coding", "event_type": "started"},
            )
            await session.post(
                f"{BASE}/api/chat-stream",
                json={"content": "hi", "is_final": False},
            )
            await session.post(
                f"{BASE}/api/control-ack",
                json={"agent": "coding", "command": "pause", "success": True},
            )

            expected_types = ["agent_status", "agent_event", "chat_message", "control_ack"]
            for expected in expected_types:
                data = await _ws_recv(ws)
                assert data["type"] == expected


# ---------------------------------------------------------------------------
# 9. Multiple clients all receive broadcasts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multiple_clients_receive_broadcast(server):
    """All connected WebSocket clients receive each broadcast."""
    async with ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws1, \
                   session.ws_connect(WS_URL) as ws2, \
                   session.ws_connect(WS_URL) as ws3:

            # Drain initial metrics_update from all clients
            for ws in (ws1, ws2, ws3):
                await _ws_recv(ws)

            # Broadcast one agent_status
            await session.post(
                f"{BASE}/api/agent-status",
                json={"agent": "coding", "status": "working"},
            )

            for ws in (ws1, ws2, ws3):
                data = await _ws_recv(ws)
                assert data["type"] == "agent_status"
                assert data["agent"] == "coding"
                assert data["status"] == "working"


@pytest.mark.asyncio
async def test_multiple_clients_no_message_loss(server):
    """No messages are lost when broadcasting to multiple clients."""
    n_messages = 10
    async with ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws1, \
                   session.ws_connect(WS_URL) as ws2:

            await _ws_recv(ws1)
            await _ws_recv(ws2)

            # Send n_messages rapidly
            for i in range(n_messages):
                await session.post(
                    f"{BASE}/api/agent-status",
                    json={"agent": "coding", "status": "working", "ticket": f"AI-{i}"},
                )

            # Both clients should receive all n_messages
            for ws in (ws1, ws2):
                received_tickets = []
                for _ in range(n_messages):
                    data = await _ws_recv(ws)
                    received_tickets.append(data["ticket"])

                assert len(received_tickets) == n_messages


if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v", "--tb=short", "-s"])
