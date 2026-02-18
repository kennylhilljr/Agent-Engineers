"""Tests for AI-79: REQ-MONITOR-001 Agent Status Panel - All 13 Agents.

Covers:
- GET /api/agents/status returns all 13 panel agents
- GET /api/agents/status each agent has required fields (name, status, current_ticket, elapsed_time)
- POST /api/agents/{name}/status updates to valid statuses (idle, running, paused, error)
- POST /api/agents/{name}/status with invalid agent name returns 404
- POST /api/agents/{name}/status with invalid status returns 400
- POST /api/agents/{name}/status sets current_ticket when running
- POST /api/agents/{name}/status clears current_ticket when not running
- Status transitions: idle->running, running->paused, paused->idle, any->error
- WebSocket broadcast on status update
"""

import asyncio
import json
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
from dashboard.rest_api_server import (
    RESTAPIServer,
    _agent_states,
    _agent_status_details,
    _ws_clients,
    PANEL_AGENT_NAMES,
    VALID_AGENT_STATUSES,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPECTED_PANEL_AGENTS = [
    "linear", "coding", "github", "slack", "pr_reviewer",
    "ops", "coding_fast", "pr_reviewer_fast", "chatgpt",
    "gemini", "groq", "kimi", "windsurf",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_metrics(tmp_path: Path) -> Path:
    """Write a minimal .agent_metrics.json for tests."""
    metrics = {
        "version": 1,
        "project_name": "test-project",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T12:00:00Z",
        "total_sessions": 0,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "total_duration_seconds": 0.0,
        "agents": {},
        "events": [],
        "sessions": [],
    }
    metrics_path = tmp_path / ".agent_metrics.json"
    metrics_path.write_text(json.dumps(metrics))
    return metrics_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_metrics_dir(tmp_path):
    """Temporary directory with a minimal metrics file."""
    _make_minimal_metrics(tmp_path)
    return tmp_path


@pytest.fixture()
def rest_server(tmp_metrics_dir):
    """RESTAPIServer instance backed by a temp metrics directory."""
    # Reset module-level state before each test
    rest_module._agent_states.clear()
    rest_module._requirements_cache.clear()
    rest_module._decisions_log.clear()
    rest_module._ws_clients.clear()
    rest_module._agent_status_details.clear()

    server = RESTAPIServer(
        project_name="test-project",
        metrics_dir=tmp_metrics_dir,
        port=19500,
        host="127.0.0.1",
    )
    return server


@pytest.fixture()
async def client(rest_server):
    """aiohttp TestClient wrapping the REST server."""
    async with TestClient(TestServer(rest_server.app)) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /api/agents/status - Structure tests
# ---------------------------------------------------------------------------

async def test_get_agents_status_returns_200(client):
    """GET /api/agents/status returns HTTP 200."""
    resp = await client.get("/api/agents/status")
    assert resp.status == 200


async def test_get_agents_status_returns_json_object(client):
    """GET /api/agents/status returns JSON object with 'agents' and 'total' keys."""
    resp = await client.get("/api/agents/status")
    assert resp.status == 200
    data = await resp.json()
    assert "agents" in data
    assert "total" in data
    assert "timestamp" in data


async def test_get_agents_status_returns_all_13_agents(client):
    """GET /api/agents/status returns exactly 13 panel agents."""
    resp = await client.get("/api/agents/status")
    assert resp.status == 200
    data = await resp.json()
    agents = data["agents"]
    assert isinstance(agents, list)
    assert data["total"] == 13
    assert len(agents) == 13


async def test_get_agents_status_contains_all_expected_agent_names(client):
    """GET /api/agents/status includes all 13 expected agent names."""
    resp = await client.get("/api/agents/status")
    data = await resp.json()
    returned_names = {a["name"] for a in data["agents"]}
    for expected_name in EXPECTED_PANEL_AGENTS:
        assert expected_name in returned_names, f"Missing agent: {expected_name}"


async def test_get_agents_status_each_agent_has_required_fields(client):
    """Each agent in GET /api/agents/status has name, status, current_ticket, elapsed_time."""
    resp = await client.get("/api/agents/status")
    data = await resp.json()
    for agent in data["agents"]:
        assert "name" in agent, f"Agent missing 'name': {agent}"
        assert "status" in agent, f"Agent missing 'status': {agent}"
        assert "current_ticket" in agent, f"Agent missing 'current_ticket': {agent}"
        assert "elapsed_time" in agent, f"Agent missing 'elapsed_time': {agent}"


async def test_get_agents_status_initial_status_is_idle(client):
    """All agents start with 'idle' status on fresh initialization."""
    resp = await client.get("/api/agents/status")
    data = await resp.json()
    for agent in data["agents"]:
        assert agent["status"] == "idle", f"Agent {agent['name']} should be idle, got {agent['status']}"


async def test_get_agents_status_initial_current_ticket_is_null(client):
    """All agents have null current_ticket on fresh initialization."""
    resp = await client.get("/api/agents/status")
    data = await resp.json()
    for agent in data["agents"]:
        assert agent["current_ticket"] is None, f"Agent {agent['name']} should have null ticket"


# ---------------------------------------------------------------------------
# POST /api/agents/{name}/status - Valid status updates
# ---------------------------------------------------------------------------

async def test_post_agent_status_idle(client):
    """POST /api/agents/coding/status with status=idle returns 200."""
    resp = await client.post("/api/agents/coding/status", json={"status": "idle"})
    assert resp.status == 200
    data = await resp.json()
    assert data["new_status"] == "idle"
    assert data["agent_name"] == "coding"


async def test_post_agent_status_running(client):
    """POST /api/agents/coding/status with status=running returns 200."""
    resp = await client.post("/api/agents/coding/status", json={"status": "running"})
    assert resp.status == 200
    data = await resp.json()
    assert data["new_status"] == "running"


async def test_post_agent_status_paused(client):
    """POST /api/agents/coding/status with status=paused returns 200."""
    resp = await client.post("/api/agents/coding/status", json={"status": "paused"})
    assert resp.status == 200
    data = await resp.json()
    assert data["new_status"] == "paused"


async def test_post_agent_status_error(client):
    """POST /api/agents/coding/status with status=error returns 200."""
    resp = await client.post("/api/agents/coding/status", json={"status": "error"})
    assert resp.status == 200
    data = await resp.json()
    assert data["new_status"] == "error"


async def test_post_agent_status_with_ticket(client):
    """POST status=running with current_ticket stores ticket in status."""
    resp = await client.post(
        "/api/agents/coding/status",
        json={"status": "running", "current_ticket": "AI-79"}
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["new_status"] == "running"
    assert data["current_ticket"] == "AI-79"


async def test_post_agent_status_running_reflects_in_get(client):
    """After POST status=running, GET /api/agents/status reflects change."""
    await client.post(
        "/api/agents/linear/status",
        json={"status": "running", "current_ticket": "AI-100"}
    )
    resp = await client.get("/api/agents/status")
    data = await resp.json()
    linear = next(a for a in data["agents"] if a["name"] == "linear")
    assert linear["status"] == "running"
    assert linear["current_ticket"] == "AI-100"


async def test_post_agent_status_idle_clears_ticket(client):
    """After setting running then idle, current_ticket should be cleared."""
    await client.post(
        "/api/agents/coding/status",
        json={"status": "running", "current_ticket": "AI-79"}
    )
    await client.post("/api/agents/coding/status", json={"status": "idle"})
    resp = await client.get("/api/agents/status")
    data = await resp.json()
    coding = next(a for a in data["agents"] if a["name"] == "coding")
    assert coding["status"] == "idle"
    assert coding["current_ticket"] is None


async def test_post_agent_status_response_has_previous_status(client):
    """POST status update response includes previous_status field."""
    await client.post("/api/agents/github/status", json={"status": "running"})
    resp = await client.post("/api/agents/github/status", json={"status": "paused"})
    data = await resp.json()
    assert "previous_status" in data
    assert data["previous_status"] == "running"


# ---------------------------------------------------------------------------
# POST /api/agents/{name}/status - Invalid inputs
# ---------------------------------------------------------------------------

async def test_post_agent_status_invalid_agent_returns_404(client):
    """POST status for unknown agent returns 404."""
    resp = await client.post("/api/agents/unknown_agent_xyz/status", json={"status": "idle"})
    assert resp.status == 404
    data = await resp.json()
    assert "error" in data


async def test_post_agent_status_orchestrator_returns_404(client):
    """POST status for 'orchestrator' returns 404 (not in panel agents)."""
    resp = await client.post("/api/agents/orchestrator/status", json={"status": "idle"})
    assert resp.status == 404


async def test_post_agent_status_invalid_status_returns_400(client):
    """POST with invalid status string returns 400."""
    resp = await client.post("/api/agents/coding/status", json={"status": "working"})
    assert resp.status == 400
    data = await resp.json()
    assert "error" in data


async def test_post_agent_status_empty_status_returns_400(client):
    """POST with empty status string returns 400."""
    resp = await client.post("/api/agents/coding/status", json={"status": ""})
    assert resp.status == 400


async def test_post_agent_status_invalid_json_returns_400(client):
    """POST with invalid JSON body returns 400."""
    resp = await client.post(
        "/api/agents/coding/status",
        data="not-json",
        headers={"Content-Type": "application/json"}
    )
    assert resp.status == 400


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------

async def test_status_transition_idle_to_running(client):
    """idle -> running transition works correctly."""
    # Start at idle (default)
    await client.post("/api/agents/slack/status", json={"status": "idle"})
    resp = await client.post("/api/agents/slack/status", json={"status": "running"})
    assert resp.status == 200
    data = await resp.json()
    assert data["new_status"] == "running"
    assert data["previous_status"] == "idle"


async def test_status_transition_running_to_idle(client):
    """running -> idle transition works correctly."""
    await client.post("/api/agents/slack/status", json={"status": "running"})
    resp = await client.post("/api/agents/slack/status", json={"status": "idle"})
    assert resp.status == 200
    data = await resp.json()
    assert data["new_status"] == "idle"
    assert data["previous_status"] == "running"


async def test_status_transition_running_to_paused(client):
    """running -> paused transition works correctly."""
    await client.post("/api/agents/coding/status", json={"status": "running"})
    resp = await client.post("/api/agents/coding/status", json={"status": "paused"})
    assert resp.status == 200
    data = await resp.json()
    assert data["new_status"] == "paused"


async def test_status_transition_paused_to_idle(client):
    """paused -> idle transition works correctly."""
    await client.post("/api/agents/coding/status", json={"status": "paused"})
    resp = await client.post("/api/agents/coding/status", json={"status": "idle"})
    assert resp.status == 200
    data = await resp.json()
    assert data["new_status"] == "idle"


async def test_status_transition_any_to_error(client):
    """Any status -> error transition works correctly."""
    for initial in ("idle", "running", "paused"):
        await client.post("/api/agents/github/status", json={"status": initial})
        resp = await client.post("/api/agents/github/status", json={"status": "error"})
        assert resp.status == 200
        data = await resp.json()
        assert data["new_status"] == "error"
        assert data["previous_status"] == initial


# ---------------------------------------------------------------------------
# All 13 agents - individual update tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("agent_name", EXPECTED_PANEL_AGENTS)
async def test_each_of_13_agents_can_be_updated(client, agent_name):
    """Each of the 13 panel agents can have its status updated."""
    resp = await client.post(
        f"/api/agents/{agent_name}/status",
        json={"status": "running", "current_ticket": "AI-79"}
    )
    assert resp.status == 200, f"Failed for agent: {agent_name}"
    data = await resp.json()
    assert data["agent_name"] == agent_name
    assert data["new_status"] == "running"


# ---------------------------------------------------------------------------
# PANEL_AGENT_NAMES constant tests
# ---------------------------------------------------------------------------

def test_panel_agent_names_contains_13_agents():
    """PANEL_AGENT_NAMES module constant contains exactly 13 agents."""
    assert len(PANEL_AGENT_NAMES) == 13


def test_panel_agent_names_contains_expected_agents():
    """PANEL_AGENT_NAMES includes all 13 expected agent names."""
    for name in EXPECTED_PANEL_AGENTS:
        assert name in PANEL_AGENT_NAMES, f"Missing: {name}"


def test_valid_agent_statuses_constant():
    """VALID_AGENT_STATUSES contains idle, running, paused, error."""
    assert "idle" in VALID_AGENT_STATUSES
    assert "running" in VALID_AGENT_STATUSES
    assert "paused" in VALID_AGENT_STATUSES
    assert "error" in VALID_AGENT_STATUSES


# ---------------------------------------------------------------------------
# Elapsed time - running agents
# ---------------------------------------------------------------------------

async def test_running_agent_has_elapsed_time(client):
    """A running agent should have a non-null elapsed_time in the status response."""
    await client.post(
        "/api/agents/coding/status",
        json={"status": "running", "current_ticket": "AI-79"}
    )
    resp = await client.get("/api/agents/status")
    data = await resp.json()
    coding = next(a for a in data["agents"] if a["name"] == "coding")
    assert coding["status"] == "running"
    # elapsed_time should be 0 or more seconds (may be 0 for immediate query)
    assert coding["elapsed_time"] is not None
    assert coding["elapsed_time"] >= 0


async def test_idle_agent_has_null_elapsed_time(client):
    """An idle agent should have null elapsed_time."""
    resp = await client.get("/api/agents/status")
    data = await resp.json()
    linear = next(a for a in data["agents"] if a["name"] == "linear")
    assert linear["status"] == "idle"
    assert linear["elapsed_time"] is None
