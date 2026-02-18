"""Tests for AI-80: REQ-MONITOR-002 Active Requirement Display - Running Agent Details.

Covers:
- GET /api/agents/{name}/requirement returns ticket key, title, description, token_count,
  estimated_cost, elapsed_time for a running agent
- POST /api/agents/{name}/status now accepts ticket_title, description, token_count, estimated_cost
- POST /api/agents/{name}/metrics updates token_count and estimated_cost for a running agent
- WebSocket broadcast on metrics update (agent_metrics_update)
- Elapsed time calculation for running agents
- Expand/collapse state via API (description field)
- GET /api/agents/status includes new fields (ticket_title, description, token_count, estimated_cost)
"""

import asyncio
import json
import sys
import time
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
        port=19501,
        host="127.0.0.1",
    )
    return server


@pytest.fixture()
async def client(rest_server):
    """aiohttp TestClient wrapping the REST server."""
    async with TestClient(TestServer(rest_server.app)) as c:
        yield c


# ---------------------------------------------------------------------------
# Helper: set an agent to running with ticket data
# ---------------------------------------------------------------------------

async def _set_agent_running(client, agent_name="coding", ticket="AI-80",
                              title="Active Requirement Display",
                              description="Full description of the requirement for testing expand/collapse",
                              token_count=500, estimated_cost=0.0025):
    """Helper: POST agent status to running with full ticket data."""
    resp = await client.post(
        f"/api/agents/{agent_name}/status",
        json={
            "status": "running",
            "current_ticket": ticket,
            "ticket_title": title,
            "description": description,
            "token_count": token_count,
            "estimated_cost": estimated_cost,
        }
    )
    assert resp.status == 200, f"Failed to set agent running: {await resp.text()}"
    return await resp.json()


# ---------------------------------------------------------------------------
# POST /api/agents/{name}/status - now accepts new fields (AI-80)
# ---------------------------------------------------------------------------

async def test_post_status_accepts_ticket_title(client):
    """POST /api/agents/coding/status accepts ticket_title field."""
    resp = await client.post(
        "/api/agents/coding/status",
        json={"status": "running", "current_ticket": "AI-80", "ticket_title": "My Ticket"}
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["ticket_title"] == "My Ticket"


async def test_post_status_accepts_description(client):
    """POST /api/agents/coding/status accepts description field."""
    resp = await client.post(
        "/api/agents/coding/status",
        json={"status": "running", "current_ticket": "AI-80",
              "description": "Full requirement description text"}
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["description"] == "Full requirement description text"


async def test_post_status_accepts_token_count(client):
    """POST /api/agents/coding/status accepts token_count field."""
    resp = await client.post(
        "/api/agents/coding/status",
        json={"status": "running", "current_ticket": "AI-80", "token_count": 1234}
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["token_count"] == 1234


async def test_post_status_accepts_estimated_cost(client):
    """POST /api/agents/coding/status accepts estimated_cost field."""
    resp = await client.post(
        "/api/agents/coding/status",
        json={"status": "running", "current_ticket": "AI-80", "estimated_cost": 0.0042}
    )
    assert resp.status == 200
    data = await resp.json()
    assert abs(data["estimated_cost"] - 0.0042) < 1e-9


async def test_post_status_running_stores_all_fields(client):
    """POST status=running stores ticket_title, description, token_count, estimated_cost."""
    data = await _set_agent_running(client, "coding", "AI-80",
                                     "Test Ticket Title",
                                     "Full description text",
                                     999, 0.0099)
    assert data["new_status"] == "running"
    assert data["current_ticket"] == "AI-80"
    assert data["ticket_title"] == "Test Ticket Title"
    assert data["description"] == "Full description text"
    assert data["token_count"] == 999
    assert abs(data["estimated_cost"] - 0.0099) < 1e-9


async def test_post_status_idle_clears_new_fields(client):
    """POST status=idle clears ticket_title, description, token_count, estimated_cost."""
    await _set_agent_running(client)
    resp = await client.post("/api/agents/coding/status", json={"status": "idle"})
    assert resp.status == 200
    data = await resp.json()
    assert data["ticket_title"] is None
    assert data["description"] is None
    assert data["token_count"] == 0
    assert data["estimated_cost"] == 0.0


async def test_post_status_error_clears_new_fields(client):
    """POST status=error clears ticket_title, description, token_count, estimated_cost."""
    await _set_agent_running(client)
    resp = await client.post("/api/agents/coding/status", json={"status": "error"})
    assert resp.status == 200
    data = await resp.json()
    assert data["ticket_title"] is None
    assert data["description"] is None
    assert data["token_count"] == 0
    assert data["estimated_cost"] == 0.0


# ---------------------------------------------------------------------------
# GET /api/agents/{name}/requirement - new endpoint (AI-80)
# ---------------------------------------------------------------------------

async def test_get_requirement_endpoint_exists(client):
    """GET /api/agents/coding/requirement returns 200."""
    resp = await client.get("/api/agents/coding/requirement")
    assert resp.status == 200


async def test_get_requirement_returns_json_with_required_fields(client):
    """GET /api/agents/coding/requirement returns all required fields."""
    resp = await client.get("/api/agents/coding/requirement")
    assert resp.status == 200
    data = await resp.json()
    assert "agent_name" in data
    assert "status" in data
    assert "current_ticket" in data
    assert "ticket_title" in data
    assert "description" in data
    assert "token_count" in data
    assert "estimated_cost" in data
    assert "elapsed_time" in data
    assert "started_at" in data
    assert "timestamp" in data


async def test_get_requirement_for_idle_agent(client):
    """GET /api/agents/coding/requirement for idle agent returns default values."""
    resp = await client.get("/api/agents/coding/requirement")
    assert resp.status == 200
    data = await resp.json()
    assert data["agent_name"] == "coding"
    assert data["status"] == "idle"
    assert data["current_ticket"] is None
    assert data["ticket_title"] is None
    assert data["description"] is None
    assert data["token_count"] == 0
    assert data["elapsed_time"] is None


async def test_get_requirement_for_running_agent(client):
    """GET /api/agents/coding/requirement for running agent returns stored data."""
    await _set_agent_running(
        client, "coding", "AI-80",
        "Active Requirement Display",
        "Full description for the active requirement feature",
        1500, 0.0075
    )
    resp = await client.get("/api/agents/coding/requirement")
    assert resp.status == 200
    data = await resp.json()
    assert data["agent_name"] == "coding"
    assert data["status"] == "running"
    assert data["current_ticket"] == "AI-80"
    assert data["ticket_title"] == "Active Requirement Display"
    assert data["description"] == "Full description for the active requirement feature"
    assert data["token_count"] == 1500
    assert abs(data["estimated_cost"] - 0.0075) < 1e-9


async def test_get_requirement_elapsed_time_is_non_negative_for_running(client):
    """GET /api/agents/coding/requirement for running agent has non-negative elapsed_time."""
    await _set_agent_running(client)
    resp = await client.get("/api/agents/coding/requirement")
    data = await resp.json()
    assert data["elapsed_time"] is not None
    assert data["elapsed_time"] >= 0


async def test_get_requirement_invalid_agent_returns_404(client):
    """GET /api/agents/unknown_xyz/requirement returns 404."""
    resp = await client.get("/api/agents/unknown_xyz/requirement")
    assert resp.status == 404
    data = await resp.json()
    assert "error" in data


async def test_get_requirement_all_13_agents(client):
    """GET /api/agents/{name}/requirement works for all 13 panel agents."""
    for agent_name in PANEL_AGENT_NAMES:
        resp = await client.get(f"/api/agents/{agent_name}/requirement")
        assert resp.status == 200, f"Failed for agent: {agent_name}"
        data = await resp.json()
        assert data["agent_name"] == agent_name


# ---------------------------------------------------------------------------
# POST /api/agents/{name}/metrics - new endpoint (AI-80)
# ---------------------------------------------------------------------------

async def test_post_metrics_endpoint_exists(client):
    """POST /api/agents/coding/metrics returns 200 with valid data."""
    resp = await client.post(
        "/api/agents/coding/metrics",
        json={"token_count": 100, "estimated_cost": 0.0003}
    )
    assert resp.status == 200


async def test_post_metrics_updates_token_count(client):
    """POST /api/agents/coding/metrics updates token_count."""
    await _set_agent_running(client, token_count=100)
    resp = await client.post(
        "/api/agents/coding/metrics",
        json={"token_count": 500}
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["token_count"] == 500


async def test_post_metrics_updates_estimated_cost(client):
    """POST /api/agents/coding/metrics updates estimated_cost."""
    await _set_agent_running(client, estimated_cost=0.001)
    resp = await client.post(
        "/api/agents/coding/metrics",
        json={"estimated_cost": 0.0042}
    )
    assert resp.status == 200
    data = await resp.json()
    assert abs(data["estimated_cost"] - 0.0042) < 1e-9


async def test_post_metrics_updates_both_fields(client):
    """POST /api/agents/coding/metrics updates both token_count and estimated_cost."""
    resp = await client.post(
        "/api/agents/coding/metrics",
        json={"token_count": 2000, "estimated_cost": 0.006}
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["token_count"] == 2000
    assert abs(data["estimated_cost"] - 0.006) < 1e-9


async def test_post_metrics_missing_both_fields_returns_400(client):
    """POST /api/agents/coding/metrics with no fields returns 400."""
    resp = await client.post(
        "/api/agents/coding/metrics",
        json={}
    )
    assert resp.status == 400
    data = await resp.json()
    assert "error" in data


async def test_post_metrics_invalid_agent_returns_404(client):
    """POST /api/agents/unknown_xyz/metrics returns 404."""
    resp = await client.post(
        "/api/agents/unknown_xyz/metrics",
        json={"token_count": 100}
    )
    assert resp.status == 404


async def test_post_metrics_invalid_json_returns_400(client):
    """POST /api/agents/coding/metrics with invalid JSON returns 400."""
    resp = await client.post(
        "/api/agents/coding/metrics",
        data="not-json",
        headers={"Content-Type": "application/json"}
    )
    assert resp.status == 400


async def test_post_metrics_reflects_in_requirement_endpoint(client):
    """After POST /api/agents/coding/metrics, GET /requirement shows updated values."""
    await _set_agent_running(client, token_count=100, estimated_cost=0.0003)
    # Update metrics
    await client.post(
        "/api/agents/coding/metrics",
        json={"token_count": 9999, "estimated_cost": 0.02997}
    )
    # Verify via requirement endpoint
    resp = await client.get("/api/agents/coding/requirement")
    data = await resp.json()
    assert data["token_count"] == 9999
    assert abs(data["estimated_cost"] - 0.02997) < 1e-6


async def test_post_metrics_token_only_preserves_cost(client):
    """POST /api/agents/coding/metrics with only token_count preserves existing cost."""
    await _set_agent_running(client, token_count=100, estimated_cost=0.0099)
    resp = await client.post(
        "/api/agents/coding/metrics",
        json={"token_count": 200}
    )
    assert resp.status == 200
    # Verify cost is preserved
    req_resp = await client.get("/api/agents/coding/requirement")
    data = await req_resp.json()
    assert data["token_count"] == 200
    assert abs(data["estimated_cost"] - 0.0099) < 1e-9


async def test_post_metrics_cost_only_preserves_tokens(client):
    """POST /api/agents/coding/metrics with only estimated_cost preserves existing tokens."""
    await _set_agent_running(client, token_count=500, estimated_cost=0.001)
    resp = await client.post(
        "/api/agents/coding/metrics",
        json={"estimated_cost": 0.005}
    )
    assert resp.status == 200
    req_resp = await client.get("/api/agents/coding/requirement")
    data = await req_resp.json()
    assert data["token_count"] == 500
    assert abs(data["estimated_cost"] - 0.005) < 1e-9


async def test_post_metrics_response_has_required_fields(client):
    """POST /api/agents/coding/metrics response includes status, agent_name, token_count, estimated_cost."""
    resp = await client.post(
        "/api/agents/coding/metrics",
        json={"token_count": 100, "estimated_cost": 0.0003}
    )
    assert resp.status == 200
    data = await resp.json()
    assert "status" in data
    assert "agent_name" in data
    assert "token_count" in data
    assert "estimated_cost" in data
    assert "timestamp" in data
    assert data["status"] == "success"
    assert data["agent_name"] == "coding"


# ---------------------------------------------------------------------------
# GET /api/agents/status - includes new fields (AI-80)
# ---------------------------------------------------------------------------

async def test_get_agents_status_includes_new_fields(client):
    """GET /api/agents/status each agent has ticket_title, description, token_count, estimated_cost."""
    resp = await client.get("/api/agents/status")
    assert resp.status == 200
    data = await resp.json()
    for agent in data["agents"]:
        assert "ticket_title" in agent, f"Agent {agent['name']} missing 'ticket_title'"
        assert "description" in agent, f"Agent {agent['name']} missing 'description'"
        assert "token_count" in agent, f"Agent {agent['name']} missing 'token_count'"
        assert "estimated_cost" in agent, f"Agent {agent['name']} missing 'estimated_cost'"


async def test_get_agents_status_running_agent_shows_requirement_data(client):
    """GET /api/agents/status for a running agent shows ticket_title and description."""
    await _set_agent_running(
        client, "linear", "AI-80",
        "Monitor Feature Title",
        "This is the monitoring feature description",
        300, 0.0009
    )
    resp = await client.get("/api/agents/status")
    assert resp.status == 200
    data = await resp.json()
    linear = next(a for a in data["agents"] if a["name"] == "linear")
    assert linear["status"] == "running"
    assert linear["current_ticket"] == "AI-80"
    assert linear["ticket_title"] == "Monitor Feature Title"
    assert linear["description"] == "This is the monitoring feature description"
    assert linear["token_count"] == 300
    assert abs(linear["estimated_cost"] - 0.0009) < 1e-9


async def test_get_agents_status_idle_agents_have_null_new_fields(client):
    """GET /api/agents/status idle agents have null ticket_title and description."""
    resp = await client.get("/api/agents/status")
    data = await resp.json()
    for agent in data["agents"]:
        if agent["status"] == "idle":
            assert agent["ticket_title"] is None, f"{agent['name']} should have null ticket_title"
            assert agent["description"] is None, f"{agent['name']} should have null description"
            assert agent["token_count"] == 0, f"{agent['name']} should have 0 token_count"


# ---------------------------------------------------------------------------
# Elapsed time calculation (AI-80)
# ---------------------------------------------------------------------------

async def test_elapsed_time_increases_over_time(client):
    """Elapsed time is calculated from started_at and increases as time passes."""
    await _set_agent_running(client, "coding")
    # Small sleep to ensure elapsed_time > 0
    await asyncio.sleep(1.1)
    resp = await client.get("/api/agents/coding/requirement")
    data = await resp.json()
    assert data["elapsed_time"] is not None
    assert data["elapsed_time"] >= 1


async def test_elapsed_time_is_none_for_idle_agent(client):
    """GET /api/agents/coding/requirement for idle agent has None elapsed_time."""
    resp = await client.get("/api/agents/coding/requirement")
    data = await resp.json()
    assert data["status"] == "idle"
    assert data["elapsed_time"] is None


async def test_elapsed_time_resets_when_agent_goes_idle(client):
    """After going idle, elapsed_time is cleared."""
    await _set_agent_running(client, "coding")
    await client.post("/api/agents/coding/status", json={"status": "idle"})
    resp = await client.get("/api/agents/coding/requirement")
    data = await resp.json()
    assert data["status"] == "idle"
    assert data["elapsed_time"] is None


# ---------------------------------------------------------------------------
# WebSocket broadcast on metrics update (AI-80)
# ---------------------------------------------------------------------------

async def test_metrics_update_response_has_success_status(client):
    """POST /api/agents/coding/metrics returns success status."""
    resp = await client.post(
        "/api/agents/coding/metrics",
        json={"token_count": 1000, "estimated_cost": 0.003}
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["status"] == "success"


async def test_metrics_update_broadcasts_to_ws_clients(client):
    """POST /api/agents/coding/metrics broadcasts agent_metrics_update to WebSocket clients."""
    messages = []

    # Connect WebSocket FIRST, then trigger metrics update
    async with client.ws_connect("/api/ws") as ws:
        # Allow WS connection to register
        await asyncio.sleep(0.05)

        # Update metrics (WS is already connected)
        await client.post(
            "/api/agents/coding/metrics",
            json={"token_count": 750, "estimated_cost": 0.00225}
        )

        # Read WebSocket messages (with timeout)
        try:
            msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
            if msg.type == aiohttp.WSMsgType.TEXT:
                messages.append(json.loads(msg.data))
        except (asyncio.TimeoutError, Exception):
            pass

    # Find agent_metrics_update message
    metrics_msgs = [m for m in messages if m.get("type") == "agent_metrics_update"]
    assert len(metrics_msgs) > 0, "Expected at least one agent_metrics_update message"
    msg = metrics_msgs[0]
    assert msg["agent"] == "coding"
    assert msg["token_count"] == 750
    assert abs(msg["estimated_cost"] - 0.00225) < 1e-9


# ---------------------------------------------------------------------------
# Description expand/collapse state (AI-80)
# ---------------------------------------------------------------------------

async def test_description_field_stored_and_retrieved(client):
    """Description field is stored when agent starts running and retrieved via /requirement."""
    long_desc = "This is a detailed description of the requirement that spans multiple lines.\n" \
                "It includes implementation notes, acceptance criteria, and test steps.\n" \
                "The full text should be visible when expanded."
    await _set_agent_running(client, "coding", description=long_desc)
    resp = await client.get("/api/agents/coding/requirement")
    data = await resp.json()
    assert data["description"] == long_desc


async def test_description_preview_truncation_is_frontend_only(client):
    """The backend always returns the full description - truncation is frontend only."""
    desc = "A" * 500  # 500 char description
    await _set_agent_running(client, "coding", description=desc)
    resp = await client.get("/api/agents/coding/requirement")
    data = await resp.json()
    assert data["description"] == desc
    assert len(data["description"]) == 500


async def test_description_none_when_idle(client):
    """Description is None when agent is idle."""
    await _set_agent_running(client, "coding", description="Some description")
    await client.post("/api/agents/coding/status", json={"status": "idle"})
    resp = await client.get("/api/agents/coding/requirement")
    data = await resp.json()
    assert data["description"] is None


async def test_description_none_when_agent_has_no_description(client):
    """Description can be None even when running (optional field)."""
    resp = await client.post(
        "/api/agents/coding/status",
        json={"status": "running", "current_ticket": "AI-80"}
    )
    assert resp.status == 200
    req_resp = await client.get("/api/agents/coding/requirement")
    data = await req_resp.json()
    assert data["description"] is None


# ---------------------------------------------------------------------------
# Cost calculation formula (AI-80)
# ---------------------------------------------------------------------------

async def test_cost_uses_haiku_pricing_formula(client):
    """Token cost at $0.000003/token (Haiku pricing) is stored correctly."""
    # 1000 tokens * $0.000003 = $0.003
    await _set_agent_running(client, token_count=1000, estimated_cost=0.003)
    resp = await client.get("/api/agents/coding/requirement")
    data = await resp.json()
    assert abs(data["estimated_cost"] - 0.003) < 1e-9


async def test_cost_uses_sonnet_pricing_formula(client):
    """Token cost at $0.000015/token (Sonnet pricing) is stored correctly."""
    # 1000 tokens * $0.000015 = $0.015
    await _set_agent_running(client, token_count=1000, estimated_cost=0.015)
    resp = await client.get("/api/agents/coding/requirement")
    data = await resp.json()
    assert abs(data["estimated_cost"] - 0.015) < 1e-9


async def test_zero_cost_for_zero_tokens(client):
    """Zero tokens results in zero estimated cost."""
    await _set_agent_running(client, token_count=0, estimated_cost=0.0)
    resp = await client.get("/api/agents/coding/requirement")
    data = await resp.json()
    assert data["token_count"] == 0
    assert data["estimated_cost"] == 0.0


# ---------------------------------------------------------------------------
# Multiple agents running simultaneously
# ---------------------------------------------------------------------------

async def test_multiple_agents_can_run_simultaneously(client):
    """Multiple agents can be in running state simultaneously with different ticket data."""
    agents_data = [
        ("coding", "AI-80", "Coding Ticket", "Coding description", 500, 0.0015),
        ("linear", "AI-81", "Linear Ticket", "Linear description", 200, 0.0006),
        ("github", "AI-82", "GitHub Ticket", "GitHub description", 800, 0.0024),
    ]

    for agent, ticket, title, desc, tokens, cost in agents_data:
        await _set_agent_running(client, agent, ticket, title, desc, tokens, cost)

    # Verify each agent's data is independent
    for agent, ticket, title, desc, tokens, cost in agents_data:
        resp = await client.get(f"/api/agents/{agent}/requirement")
        data = await resp.json()
        assert data["current_ticket"] == ticket, f"{agent}: wrong ticket"
        assert data["ticket_title"] == title, f"{agent}: wrong title"
        assert data["description"] == desc, f"{agent}: wrong description"
        assert data["token_count"] == tokens, f"{agent}: wrong token_count"
        assert abs(data["estimated_cost"] - cost) < 1e-9, f"{agent}: wrong cost"


async def test_status_endpoint_shows_all_running_agents(client):
    """GET /api/agents/status shows all running agents with their data."""
    await _set_agent_running(client, "coding", "AI-80", "T1", "D1", 100, 0.0003)
    await _set_agent_running(client, "linear", "AI-81", "T2", "D2", 200, 0.0006)

    resp = await client.get("/api/agents/status")
    data = await resp.json()
    agents = {a["name"]: a for a in data["agents"]}

    assert agents["coding"]["status"] == "running"
    assert agents["coding"]["ticket_title"] == "T1"
    assert agents["linear"]["status"] == "running"
    assert agents["linear"]["ticket_title"] == "T2"


# ---------------------------------------------------------------------------
# Import needed for WS test
# ---------------------------------------------------------------------------
import aiohttp
