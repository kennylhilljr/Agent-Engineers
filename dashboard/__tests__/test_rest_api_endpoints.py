"""Tests for AI-169: REQ-TECH-004 REST API Endpoints.

Covers:
- GET /api/agents returns agent list
- GET /api/agents/{name}/events returns events
- GET /api/agents/{unknown}/events returns 404
- GET /api/sessions returns sessions
- GET /api/providers returns providers with availability
- POST /api/chat returns response
- POST /api/agents/{name}/pause returns paused status
- POST /api/agents/{name}/resume returns resumed status
- Pause broadcasts agent_status WebSocket event
- Resume broadcasts agent_status WebSocket event
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

# Ensure the project root is importable.
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import dashboard.rest_api_server as rest_module
from dashboard.rest_api_server import RESTAPIServer, _agent_states, _ws_clients


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_test_metrics(tmp_path: Path) -> Path:
    """Write a minimal .agent_metrics.json file and return its path."""
    metrics = {
        "version": 1,
        "project_name": "test-project",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T12:00:00Z",
        "total_sessions": 2,
        "total_tokens": 3000,
        "total_cost_usd": 0.15,
        "total_duration_seconds": 30.0,
        "agents": {
            "coding": {
                "agent_name": "coding",
                "total_invocations": 5,
                "successful_invocations": 4,
                "failed_invocations": 1,
                "total_tokens": 2000,
                "total_cost_usd": 0.10,
                "total_duration_seconds": 20.0,
                "commits_made": 1,
                "prs_created": 0,
                "prs_merged": 0,
                "files_created": 1,
                "files_modified": 2,
                "lines_added": 50,
                "lines_removed": 10,
                "tests_written": 2,
                "issues_created": 0,
                "issues_completed": 1,
                "messages_sent": 0,
                "reviews_completed": 0,
                "success_rate": 0.8,
                "avg_duration_seconds": 4.0,
                "avg_tokens_per_call": 400.0,
                "cost_per_success_usd": 0.025,
                "xp": 100,
                "level": 2,
                "current_streak": 1,
                "best_streak": 3,
                "achievements": [],
                "strengths": [],
                "weaknesses": [],
                "recent_events": ["event-1"],
                "last_error": "",
                "last_active": "2024-01-01T12:00:00Z",
            }
        },
        "events": [
            {
                "event_id": "event-1",
                "agent_name": "coding",
                "session_id": "session-1",
                "ticket_key": "AI-100",
                "started_at": "2024-01-01T10:00:00Z",
                "ended_at": "2024-01-01T10:05:00Z",
                "duration_seconds": 300.0,
                "status": "success",
                "input_tokens": 1000,
                "output_tokens": 1000,
                "total_tokens": 2000,
                "estimated_cost_usd": 0.10,
                "artifacts": [],
                "error_message": "",
                "model_used": "claude-sonnet-4-5",
                "file_changes": [],
            }
        ],
        "sessions": [
            {
                "session_id": "session-1",
                "session_number": 1,
                "session_type": "initializer",
                "started_at": "2024-01-01T10:00:00Z",
                "ended_at": "2024-01-01T10:30:00Z",
                "status": "complete",
                "agents_invoked": ["coding"],
                "total_tokens": 2000,
                "total_cost_usd": 0.10,
                "tickets_worked": ["AI-100"],
            }
        ],
    }
    metrics_path = tmp_path / ".agent_metrics.json"
    metrics_path.write_text(json.dumps(metrics))
    return metrics_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_metrics_dir(tmp_path):
    """Temporary directory with a pre-populated metrics file."""
    _make_test_metrics(tmp_path)
    return tmp_path


@pytest.fixture()
def rest_server(tmp_metrics_dir):
    """RESTAPIServer instance backed by a temp metrics directory."""
    # Reset in-memory state between tests so each test starts fresh.
    rest_module._agent_states.clear()
    rest_module._requirements_cache.clear()
    rest_module._decisions_log.clear()
    rest_module._ws_clients.clear()

    server = RESTAPIServer(
        project_name="test-project",
        metrics_dir=tmp_metrics_dir,
        port=18500,
        host="127.0.0.1",
    )
    return server


@pytest.fixture()
async def client(rest_server):
    """aiohttp TestClient wrapping the REST server."""
    async with TestClient(TestServer(rest_server.app)) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /api/agents
# ---------------------------------------------------------------------------

async def test_get_agents_returns_list(client):
    """GET /api/agents returns a JSON object with an 'agents' list."""
    resp = await client.get("/api/agents")
    assert resp.status == 200
    data = await resp.json()
    assert "agents" in data
    assert isinstance(data["agents"], list)
    assert "total_agents" in data
    assert data["total_agents"] >= 1


async def test_get_agents_includes_all_known_agents(client):
    """GET /api/agents returns all 14 registered agent names."""
    from dashboard.metrics_store import ALL_AGENT_NAMES
    resp = await client.get("/api/agents")
    assert resp.status == 200
    data = await resp.json()
    assert data["total_agents"] == len(ALL_AGENT_NAMES)


# ---------------------------------------------------------------------------
# GET /api/agents/{name}/events
# ---------------------------------------------------------------------------

async def test_get_agent_events_returns_events(client):
    """GET /api/agents/coding/events returns events for 'coding'."""
    resp = await client.get("/api/agents/coding/events")
    assert resp.status == 200
    data = await resp.json()
    assert "events" in data
    assert isinstance(data["events"], list)
    assert data["agent_name"] == "coding"


async def test_get_agent_events_filters_by_agent(client):
    """Events returned all belong to the requested agent."""
    resp = await client.get("/api/agents/coding/events")
    assert resp.status == 200
    data = await resp.json()
    for event in data["events"]:
        assert event["agent_name"] == "coding"


async def test_get_agent_events_unknown_agent_returns_404(client):
    """GET /api/agents/nonexistent/events returns 404."""
    resp = await client.get("/api/agents/nonexistent_agent_xyz/events")
    assert resp.status == 404
    data = await resp.json()
    assert "error" in data


async def test_get_agent_events_limit_param(client):
    """GET /api/agents/coding/events?limit=1 returns at most 1 event."""
    resp = await client.get("/api/agents/coding/events?limit=1")
    assert resp.status == 200
    data = await resp.json()
    assert len(data["events"]) <= 1


# ---------------------------------------------------------------------------
# GET /api/sessions
# ---------------------------------------------------------------------------

async def test_get_sessions_returns_list(client):
    """GET /api/sessions returns a JSON object with a 'sessions' list."""
    resp = await client.get("/api/sessions")
    assert resp.status == 200
    data = await resp.json()
    assert "sessions" in data
    assert isinstance(data["sessions"], list)
    assert "total_sessions" in data


async def test_get_sessions_returns_seeded_data(client):
    """GET /api/sessions returns the session written to the metrics file."""
    resp = await client.get("/api/sessions")
    assert resp.status == 200
    data = await resp.json()
    assert len(data["sessions"]) >= 1
    assert data["sessions"][0]["session_id"] == "session-1"


# ---------------------------------------------------------------------------
# GET /api/providers
# ---------------------------------------------------------------------------

async def test_get_providers_returns_list(client):
    """GET /api/providers returns a JSON object with a 'providers' list."""
    resp = await client.get("/api/providers")
    assert resp.status == 200
    data = await resp.json()
    assert "providers" in data
    assert isinstance(data["providers"], list)
    assert len(data["providers"]) >= 1


async def test_get_providers_includes_availability_field(client):
    """Each provider entry has an 'available' boolean field."""
    resp = await client.get("/api/providers")
    assert resp.status == 200
    data = await resp.json()
    for provider in data["providers"]:
        assert "available" in provider
        assert isinstance(provider["available"], bool)


async def test_get_providers_claude_always_available(client):
    """Claude provider is always listed (default provider)."""
    resp = await client.get("/api/providers")
    assert resp.status == 200
    data = await resp.json()
    provider_ids = [p.get("provider_id") for p in data["providers"]]
    assert "claude" in provider_ids


async def test_get_providers_openai_unavailable_without_key(client):
    """OpenAI provider is unavailable when OPENAI_API_KEY is not set."""
    env_without_key = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    import unittest.mock as mock
    with mock.patch.dict(os.environ, env_without_key, clear=True):
        resp = await client.get("/api/providers")
    assert resp.status == 200
    data = await resp.json()
    openai_provider = next(
        (p for p in data["providers"] if p.get("provider_id") == "openai"), None
    )
    if openai_provider is not None:
        assert openai_provider["available"] is False


# ---------------------------------------------------------------------------
# POST /api/chat
# ---------------------------------------------------------------------------

async def test_post_chat_missing_message_returns_400(client):
    """POST /api/chat without 'message' field returns 400."""
    resp = await client.post("/api/chat", json={})
    assert resp.status == 400
    data = await resp.json()
    assert "error" in data


async def test_post_chat_invalid_json_returns_400(client):
    """POST /api/chat with invalid JSON returns 400."""
    resp = await client.post(
        "/api/chat",
        data="not json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status == 400


async def test_post_chat_returns_response(client, monkeypatch):
    """POST /api/chat with a valid message returns a 200 response.

    We monkeypatch the import so that the fallback path is taken (no actual AI
    call required), which returns a plain JSON response with status='success'.
    """
    import builtins
    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "dashboard.chat_handler":
            raise ImportError("mocked")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)

    payload = {"message": "Hello, world!", "provider": "claude"}
    resp = await client.post("/api/chat", json=payload)
    assert resp.status == 200
    data = await resp.json()
    assert "response" in data or "status" in data


# ---------------------------------------------------------------------------
# POST /api/agents/{name}/pause
# ---------------------------------------------------------------------------

async def test_pause_agent_returns_paused_status(client):
    """POST /api/agents/coding/pause returns state='paused'."""
    resp = await client.post("/api/agents/coding/pause")
    assert resp.status == 200
    data = await resp.json()
    assert data["state"] == "paused"
    assert data["agent_name"] == "coding"


async def test_pause_agent_updates_in_memory_state(client, rest_server):
    """POST /api/agents/coding/pause sets the in-memory state to 'paused'."""
    await client.post("/api/agents/coding/pause")
    assert rest_module._agent_states.get("coding") == "paused"


async def test_pause_unknown_agent_returns_404(client):
    """POST /api/agents/nonexistent/pause returns 404."""
    resp = await client.post("/api/agents/nonexistent_agent_xyz/pause")
    assert resp.status == 404


# ---------------------------------------------------------------------------
# POST /api/agents/{name}/resume
# ---------------------------------------------------------------------------

async def test_resume_agent_returns_resumed_status(client):
    """POST /api/agents/coding/resume returns state='idle'."""
    # First pause it
    await client.post("/api/agents/coding/pause")
    # Then resume
    resp = await client.post("/api/agents/coding/resume")
    assert resp.status == 200
    data = await resp.json()
    assert data["state"] == "idle"
    assert data["agent_name"] == "coding"


async def test_resume_agent_updates_in_memory_state(client, rest_server):
    """POST /api/agents/coding/resume sets the in-memory state to 'idle'."""
    rest_module._agent_states["coding"] = "paused"
    await client.post("/api/agents/coding/resume")
    assert rest_module._agent_states.get("coding") == "idle"


async def test_resume_unknown_agent_returns_404(client):
    """POST /api/agents/nonexistent/resume returns 404."""
    resp = await client.post("/api/agents/nonexistent_agent_xyz/resume")
    assert resp.status == 404


# ---------------------------------------------------------------------------
# WebSocket broadcast on pause/resume
# ---------------------------------------------------------------------------

async def test_pause_broadcasts_agent_status_via_websocket(client):
    """POST /api/agents/coding/pause broadcasts {type: agent_status, status: paused}."""
    from aiohttp import WSMsgType

    received: list = []

    async with client.session.ws_connect(
        client.make_url("/api/ws")
    ) as ws:
        # Pause the agent
        await client.post("/api/agents/coding/pause")

        # Read one WS message (with a short timeout)
        try:
            msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
        except asyncio.TimeoutError:
            pytest.fail("No WebSocket message received after pause")

        assert msg.type == WSMsgType.TEXT
        data = json.loads(msg.data)
        assert data["type"] == "agent_status"
        assert data["agent"] == "coding"
        assert data["status"] == "paused"


async def test_resume_broadcasts_agent_status_via_websocket(client):
    """POST /api/agents/coding/resume broadcasts {type: agent_status, status: idle}."""
    from aiohttp import WSMsgType

    # Pre-pause the agent
    rest_module._agent_states["coding"] = "paused"

    async with client.session.ws_connect(
        client.make_url("/api/ws")
    ) as ws:
        # Resume the agent
        await client.post("/api/agents/coding/resume")

        # Read one WS message
        try:
            msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
        except asyncio.TimeoutError:
            pytest.fail("No WebSocket message received after resume")

        assert msg.type == WSMsgType.TEXT
        data = json.loads(msg.data)
        assert data["type"] == "agent_status"
        assert data["agent"] == "coding"
        assert data["status"] == "idle"
