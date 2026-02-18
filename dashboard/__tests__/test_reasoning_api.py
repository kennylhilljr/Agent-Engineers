"""Tests for AI-158: REQ-REASONING-001: Implement Live Reasoning Stream Display.

Tests cover:
- POST /api/reasoning broadcasts reasoning event to WebSocket clients
- POST /api/reasoning with missing content returns appropriate response
- WebSocket receives reasoning message after POST
- GET /health returns OK (sanity check)
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from aiohttp import web, ClientSession, WSMsgType
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

# Ensure the project root is importable
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.server import DashboardServer


# ---------------------------------------------------------------------------
# Fixtures for async integration tests (using real TCP server)
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_metrics_dir():
    """Create a temporary directory for metrics files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest_asyncio.fixture
async def reasoning_server(temp_metrics_dir):
    """Start a DashboardServer on an ephemeral port for reasoning tests."""
    srv = DashboardServer(
        project_name="test-reasoning",
        metrics_dir=temp_metrics_dir,
        port=18099,
        host="127.0.0.1",
    )
    runner = None
    try:
        runner = web.AppRunner(srv.app)
        await runner.setup()
        site = web.TCPSite(runner, srv.host, srv.port)
        await site.start()
        await asyncio.sleep(0.3)
        yield srv
    finally:
        if runner:
            await runner.cleanup()


# ---------------------------------------------------------------------------
# Unit tests using aiohttp test client (no real TCP required)
# ---------------------------------------------------------------------------

class TestHealthCheck(AioHTTPTestCase):
    """Sanity check: GET /health returns OK."""

    async def get_application(self):
        ds = DashboardServer(
            project_name="test-health",
            metrics_dir=PROJECT_ROOT,
        )
        return ds.app

    @unittest_run_loop
    async def test_health_returns_ok(self):
        """GET /health responds with status ok."""
        resp = await self.client.request("GET", "/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"

    @unittest_run_loop
    async def test_health_content_type_is_json(self):
        """GET /health content type is application/json."""
        resp = await self.client.request("GET", "/health")
        assert "application/json" in resp.headers.get("Content-Type", "")


class TestReasoningEndpointUnit(AioHTTPTestCase):
    """Unit tests for POST /api/reasoning using aiohttp test client."""

    async def get_application(self):
        ds = DashboardServer(
            project_name="test-reasoning-unit",
            metrics_dir=PROJECT_ROOT,
        )
        return ds.app

    @unittest_run_loop
    async def test_post_reasoning_returns_success(self):
        """POST /api/reasoning with valid payload returns {"success": True}."""
        payload = {
            "content": "Ticket AI-42: Complexity COMPLEX. Delegating to coding agent.",
            "ticket": "AI-42",
        }
        resp = await self.client.request(
            "POST",
            "/api/reasoning",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["success"] is True

    @unittest_run_loop
    async def test_post_reasoning_with_empty_content_returns_success(self):
        """POST /api/reasoning with empty content still returns success.

        Missing or empty content is valid — the server uses an empty string
        as the default and broadcasts it normally.
        """
        payload = {"ticket": "AI-10"}
        resp = await self.client.request(
            "POST",
            "/api/reasoning",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["success"] is True

    @unittest_run_loop
    async def test_post_reasoning_with_invalid_json_returns_400(self):
        """POST /api/reasoning with non-JSON body returns 400."""
        resp = await self.client.request(
            "POST",
            "/api/reasoning",
            data="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400
        data = await resp.json()
        assert "error" in data

    @unittest_run_loop
    async def test_post_reasoning_broadcasts_to_connected_websockets(self):
        """POST /api/reasoning calls broadcast_to_websockets with reasoning message."""
        payload = {
            "content": "Reasoning text for broadcast test",
            "ticket": "AI-99",
        }

        # Patch at the class level: the replacement is called as an unbound method
        # so it receives (self, message). We accept both args.
        broadcast_calls = []

        async def fake_broadcast(server_self, message):
            broadcast_calls.append(message)

        with patch.object(DashboardServer, "broadcast_to_websockets", fake_broadcast):
            resp = await self.client.request(
                "POST",
                "/api/reasoning",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )

        assert resp.status == 200
        assert len(broadcast_calls) == 1
        msg = broadcast_calls[0]
        assert msg["type"] == "reasoning"
        assert msg["content"] == "Reasoning text for broadcast test"
        assert msg["ticket"] == "AI-99"
        assert "timestamp" in msg

    @unittest_run_loop
    async def test_post_reasoning_message_has_correct_fields(self):
        """POST /api/reasoning broadcast message contains required fields."""
        captured = []

        async def capture_broadcast(server_self, message):
            captured.append(message)

        with patch.object(DashboardServer, "broadcast_to_websockets", capture_broadcast):
            payload = {"content": "Decision: delegate to coding", "ticket": "AI-158"}
            await self.client.request(
                "POST",
                "/api/reasoning",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )

        assert len(captured) == 1
        msg = captured[0]
        assert msg["type"] == "reasoning"
        assert "content" in msg
        assert "ticket" in msg
        assert "timestamp" in msg


# ---------------------------------------------------------------------------
# Integration tests: WebSocket receives reasoning message after POST
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_websocket_receives_reasoning_after_post(reasoning_server):
    """WebSocket client receives reasoning message when POST /api/reasoning is called."""
    base = f"http://127.0.0.1:{reasoning_server.port}"
    ws_url = f"http://127.0.0.1:{reasoning_server.port}/ws"

    async with ClientSession() as session:
        async with session.ws_connect(ws_url) as ws:
            # Consume initial metrics_update message
            initial = await ws.receive(timeout=3)
            assert initial.type == WSMsgType.TEXT
            init_data = json.loads(initial.data)
            assert init_data["type"] == "metrics_update"

            # POST a reasoning event
            payload = {
                "content": "Ticket AI-42: COMPLEX. Delegating to coding (sonnet).",
                "ticket": "AI-42",
            }
            async with session.post(
                f"{base}/api/reasoning",
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as resp:
                assert resp.status == 200
                resp_data = await resp.json()
                assert resp_data["success"] is True

            # WebSocket should receive a reasoning message
            msg = await ws.receive(timeout=3)
            assert msg.type == WSMsgType.TEXT
            data = json.loads(msg.data)

            assert data["type"] == "reasoning"
            assert data["content"] == payload["content"]
            assert data["ticket"] == "AI-42"
            assert "timestamp" in data


@pytest.mark.asyncio
async def test_multiple_websocket_clients_receive_reasoning(reasoning_server):
    """All connected WebSocket clients receive the reasoning broadcast."""
    base = f"http://127.0.0.1:{reasoning_server.port}"
    ws_url = f"http://127.0.0.1:{reasoning_server.port}/ws"

    async with ClientSession() as session:
        async with session.ws_connect(ws_url) as ws1, \
                   session.ws_connect(ws_url) as ws2:

            # Consume initial metrics_update messages from both
            await ws1.receive(timeout=3)
            await ws2.receive(timeout=3)

            # POST a reasoning event
            payload = {"content": "Multi-client broadcast test", "ticket": "AI-158"}
            async with session.post(f"{base}/api/reasoning", json=payload) as resp:
                assert resp.status == 200

            # Both clients should receive the reasoning message
            msg1 = await ws1.receive(timeout=3)
            msg2 = await ws2.receive(timeout=3)

            data1 = json.loads(msg1.data)
            data2 = json.loads(msg2.data)

            assert data1["type"] == "reasoning"
            assert data2["type"] == "reasoning"
            assert data1["ticket"] == "AI-158"
            assert data2["ticket"] == "AI-158"


@pytest.mark.asyncio
async def test_reasoning_post_without_ticket_field(reasoning_server):
    """POST /api/reasoning without ticket field defaults ticket to empty string."""
    base = f"http://127.0.0.1:{reasoning_server.port}"
    ws_url = f"http://127.0.0.1:{reasoning_server.port}/ws"

    async with ClientSession() as session:
        async with session.ws_connect(ws_url) as ws:
            # Consume initial metrics_update
            await ws.receive(timeout=3)

            payload = {"content": "Reasoning without ticket"}
            async with session.post(f"{base}/api/reasoning", json=payload) as resp:
                assert resp.status == 200

            msg = await ws.receive(timeout=3)
            data = json.loads(msg.data)

            assert data["type"] == "reasoning"
            assert data["ticket"] == ""
            assert data["content"] == "Reasoning without ticket"
