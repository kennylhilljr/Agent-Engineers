"""Tests for AI-159: REQ-REASONING-002: Implement Agent Thinking Display.

Tests cover:
- POST /api/agent-thinking returns {"success": True}
- POST /api/agent-thinking broadcasts to WebSocket clients with correct fields
- POST /api/agent-thinking with invalid JSON returns 400
- WebSocket receives agent_thinking message after POST
- Different categories (files/changes/commands/tests) all work
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

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
async def thinking_server(temp_metrics_dir):
    """Start a DashboardServer on an ephemeral port for agent-thinking tests."""
    srv = DashboardServer(
        project_name="test-agent-thinking",
        metrics_dir=temp_metrics_dir,
        port=18199,
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

class TestAgentThinkingEndpointUnit(AioHTTPTestCase):
    """Unit tests for POST /api/agent-thinking using aiohttp test client."""

    async def get_application(self):
        ds = DashboardServer(
            project_name="test-agent-thinking-unit",
            metrics_dir=PROJECT_ROOT,
        )
        return ds.app

    @unittest_run_loop
    async def test_post_agent_thinking_returns_success(self):
        """POST /api/agent-thinking with valid payload returns {"success": True}."""
        payload = {
            "agent": "coding",
            "category": "files",
            "content": "Reading dashboard/server.py to understand routing",
            "ticket": "AI-159",
        }
        resp = await self.client.request(
            "POST",
            "/api/agent-thinking",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["success"] is True

    @unittest_run_loop
    async def test_post_agent_thinking_with_invalid_json_returns_400(self):
        """POST /api/agent-thinking with non-JSON body returns 400."""
        resp = await self.client.request(
            "POST",
            "/api/agent-thinking",
            data="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400
        data = await resp.json()
        assert "error" in data

    @unittest_run_loop
    async def test_post_agent_thinking_broadcasts_to_connected_websockets(self):
        """POST /api/agent-thinking calls broadcast_to_websockets with agent_thinking message."""
        payload = {
            "agent": "coding",
            "category": "commands",
            "content": "Running pytest dashboard/__tests__/",
            "ticket": "AI-159",
        }

        broadcast_calls = []

        async def fake_broadcast(server_self, message):
            broadcast_calls.append(message)

        with patch.object(DashboardServer, "broadcast_to_websockets", fake_broadcast):
            resp = await self.client.request(
                "POST",
                "/api/agent-thinking",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )

        assert resp.status == 200
        assert len(broadcast_calls) == 1
        msg = broadcast_calls[0]
        assert msg["type"] == "agent_thinking"
        assert msg["agent"] == "coding"
        assert msg["category"] == "commands"
        assert msg["content"] == "Running pytest dashboard/__tests__/"
        assert msg["ticket"] == "AI-159"
        assert "timestamp" in msg

    @unittest_run_loop
    async def test_post_agent_thinking_message_has_correct_fields(self):
        """POST /api/agent-thinking broadcast message contains all required fields."""
        captured = []

        async def capture_broadcast(server_self, message):
            captured.append(message)

        with patch.object(DashboardServer, "broadcast_to_websockets", capture_broadcast):
            payload = {
                "agent": "coding",
                "category": "changes",
                "content": "Will add renderAgentThinkingBlock to dashboard.html",
                "ticket": "AI-159",
            }
            await self.client.request(
                "POST",
                "/api/agent-thinking",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )

        assert len(captured) == 1
        msg = captured[0]
        assert msg["type"] == "agent_thinking"
        assert "agent" in msg
        assert "category" in msg
        assert "content" in msg
        assert "ticket" in msg
        assert "timestamp" in msg

    @unittest_run_loop
    async def test_post_agent_thinking_with_missing_fields_uses_defaults(self):
        """POST /api/agent-thinking with missing optional fields uses sensible defaults."""
        captured = []

        async def capture_broadcast(server_self, message):
            captured.append(message)

        with patch.object(DashboardServer, "broadcast_to_websockets", capture_broadcast):
            # Only send content, omit agent/category/ticket
            payload = {"content": "Minimal thinking event"}
            await self.client.request(
                "POST",
                "/api/agent-thinking",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )

        assert len(captured) == 1
        msg = captured[0]
        assert msg["type"] == "agent_thinking"
        assert msg["agent"] == ""
        assert msg["category"] == "files"  # default
        assert msg["content"] == "Minimal thinking event"
        assert msg["ticket"] == ""

    @unittest_run_loop
    async def test_category_files_is_broadcast_correctly(self):
        """POST /api/agent-thinking with category=files broadcasts correctly."""
        captured = []

        async def capture_broadcast(server_self, message):
            captured.append(message)

        with patch.object(DashboardServer, "broadcast_to_websockets", capture_broadcast):
            payload = {"agent": "coding", "category": "files", "content": "Reading server.py", "ticket": "AI-159"}
            await self.client.request(
                "POST", "/api/agent-thinking",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )

        assert captured[0]["category"] == "files"

    @unittest_run_loop
    async def test_category_changes_is_broadcast_correctly(self):
        """POST /api/agent-thinking with category=changes broadcasts correctly."""
        captured = []

        async def capture_broadcast(server_self, message):
            captured.append(message)

        with patch.object(DashboardServer, "broadcast_to_websockets", capture_broadcast):
            payload = {"agent": "coding", "category": "changes", "content": "Adding endpoint", "ticket": "AI-159"}
            await self.client.request(
                "POST", "/api/agent-thinking",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )

        assert captured[0]["category"] == "changes"

    @unittest_run_loop
    async def test_category_commands_is_broadcast_correctly(self):
        """POST /api/agent-thinking with category=commands broadcasts correctly."""
        captured = []

        async def capture_broadcast(server_self, message):
            captured.append(message)

        with patch.object(DashboardServer, "broadcast_to_websockets", capture_broadcast):
            payload = {"agent": "coding", "category": "commands", "content": "Running pytest", "ticket": "AI-159"}
            await self.client.request(
                "POST", "/api/agent-thinking",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )

        assert captured[0]["category"] == "commands"

    @unittest_run_loop
    async def test_category_tests_is_broadcast_correctly(self):
        """POST /api/agent-thinking with category=tests broadcasts correctly."""
        captured = []

        async def capture_broadcast(server_self, message):
            captured.append(message)

        with patch.object(DashboardServer, "broadcast_to_websockets", capture_broadcast):
            payload = {"agent": "coding", "category": "tests", "content": "Running test_agent_thinking_api.py", "ticket": "AI-159"}
            await self.client.request(
                "POST", "/api/agent-thinking",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )

        assert captured[0]["category"] == "tests"


# ---------------------------------------------------------------------------
# Integration tests: WebSocket receives agent_thinking message after POST
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_websocket_receives_agent_thinking_after_post(thinking_server):
    """WebSocket client receives agent_thinking message when POST /api/agent-thinking is called."""
    base = f"http://127.0.0.1:{thinking_server.port}"
    ws_url = f"http://127.0.0.1:{thinking_server.port}/ws"

    async with ClientSession() as session:
        async with session.ws_connect(ws_url) as ws:
            # Consume initial metrics_update message
            initial = await ws.receive(timeout=3)
            assert initial.type == WSMsgType.TEXT
            init_data = json.loads(initial.data)
            assert init_data["type"] == "metrics_update"

            # POST an agent thinking event
            payload = {
                "agent": "coding",
                "category": "files",
                "content": "Reading dashboard/server.py to understand the route setup",
                "ticket": "AI-159",
            }
            async with session.post(
                f"{base}/api/agent-thinking",
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as resp:
                assert resp.status == 200
                resp_data = await resp.json()
                assert resp_data["success"] is True

            # WebSocket should receive an agent_thinking message
            msg = await ws.receive(timeout=3)
            assert msg.type == WSMsgType.TEXT
            data = json.loads(msg.data)

            assert data["type"] == "agent_thinking"
            assert data["agent"] == "coding"
            assert data["category"] == "files"
            assert data["content"] == payload["content"]
            assert data["ticket"] == "AI-159"
            assert "timestamp" in data


@pytest.mark.asyncio
async def test_multiple_websocket_clients_receive_agent_thinking(thinking_server):
    """All connected WebSocket clients receive the agent_thinking broadcast."""
    base = f"http://127.0.0.1:{thinking_server.port}"
    ws_url = f"http://127.0.0.1:{thinking_server.port}/ws"

    async with ClientSession() as session:
        async with session.ws_connect(ws_url) as ws1, \
                   session.ws_connect(ws_url) as ws2:

            # Consume initial metrics_update messages from both
            await ws1.receive(timeout=3)
            await ws2.receive(timeout=3)

            # POST an agent thinking event
            payload = {
                "agent": "coding",
                "category": "tests",
                "content": "All 5 tests passing",
                "ticket": "AI-159",
            }
            async with session.post(f"{base}/api/agent-thinking", json=payload) as resp:
                assert resp.status == 200

            # Both clients should receive the agent_thinking message
            msg1 = await ws1.receive(timeout=3)
            msg2 = await ws2.receive(timeout=3)

            data1 = json.loads(msg1.data)
            data2 = json.loads(msg2.data)

            assert data1["type"] == "agent_thinking"
            assert data2["type"] == "agent_thinking"
            assert data1["ticket"] == "AI-159"
            assert data2["ticket"] == "AI-159"


@pytest.mark.asyncio
async def test_agent_thinking_all_four_categories_via_websocket(thinking_server):
    """All 4 categories (files, changes, commands, tests) are received via WebSocket."""
    base = f"http://127.0.0.1:{thinking_server.port}"
    ws_url = f"http://127.0.0.1:{thinking_server.port}/ws"
    categories = ["files", "changes", "commands", "tests"]

    async with ClientSession() as session:
        async with session.ws_connect(ws_url) as ws:
            # Consume initial metrics_update
            await ws.receive(timeout=3)

            for cat in categories:
                payload = {
                    "agent": "coding",
                    "category": cat,
                    "content": f"Thinking about {cat}",
                    "ticket": "AI-159",
                }
                async with session.post(f"{base}/api/agent-thinking", json=payload) as resp:
                    assert resp.status == 200

                msg = await ws.receive(timeout=3)
                data = json.loads(msg.data)

                assert data["type"] == "agent_thinking"
                assert data["category"] == cat
                assert data["content"] == f"Thinking about {cat}"
