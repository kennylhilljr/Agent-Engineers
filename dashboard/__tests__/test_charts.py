"""Tests for AI-85: REQ-METRICS-003 Cost and Token Charts - Visual Analytics.

Covers:
- GET /api/charts/token-usage returns all 13 agents
- GET /api/charts/token-usage has required fields (agents, max)
- GET /api/charts/token-usage agents sorted descending by tokens
- GET /api/charts/cost-trend returns session data
- GET /api/charts/cost-trend returns required fields
- GET /api/charts/success-rate returns agents with rates
- GET /api/charts/success-rate has required fields per agent
- POST /api/charts/token-usage updates data (increment mode)
- POST /api/charts/token-usage updates data (set mode)
- POST /api/charts/token-usage with unknown agent returns 400
- POST /api/charts/token-usage with missing tokens returns 400
- POST /api/charts/token-usage with invalid JSON returns 400
- POST /api/charts/token-usage with non-numeric tokens returns 400
"""

import json
import sys
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

# Ensure the project root is importable
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import dashboard.rest_api_server as rest_module
from dashboard.rest_api_server import RESTAPIServer, PANEL_AGENT_NAMES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_metrics(tmp_path: Path) -> Path:
    """Write a minimal .agent_metrics.json for tests."""
    metrics = {
        "version": 1,
        "project_name": "test-charts",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T12:00:00Z",
        "total_sessions": 5,
        "total_tokens": 150_000,
        "total_cost_usd": 5.00,
        "total_duration_seconds": 3600.0,
        "agents": {
            "coding": {
                "xp": 1500,
                "level": 6,
                "success_rate": 0.95,
                "avg_duration_seconds": 120.0,
                "total_cost_usd": 3.00,
                "total_invocations": 20,
                "successful_invocations": 19,
                "failed_invocations": 1,
            },
            "ops": {
                "xp": 800,
                "level": 5,
                "success_rate": 0.80,
                "avg_duration_seconds": 45.0,
                "total_cost_usd": 1.50,
                "total_invocations": 15,
                "successful_invocations": 12,
                "failed_invocations": 3,
            },
        },
        "events": [],
        "sessions": [],
    }
    metrics_path = tmp_path / ".agent_metrics.json"
    metrics_path.write_text(json.dumps(metrics))
    return metrics_path


def _reset_rest_module():
    """Reset all module-level state in rest_api_server before each test."""
    rest_module._agent_states.clear()
    rest_module._requirements_cache.clear()
    rest_module._decisions_log.clear()
    rest_module._ws_clients.clear()
    rest_module._agent_status_details.clear()
    rest_module._rest_agent_recent_events.clear()
    rest_module._rest_agent_xp_store.clear()
    rest_module._rest_global_metrics.update({
        "total_sessions": 0,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "uptime_seconds": 0,
        "current_session": 0,
        "agents_active": 0,
        "tasks_completed_today": 0,
        "_server_start_time": None,
    })
    # Reset chart stores
    for name in PANEL_AGENT_NAMES:
        rest_module._rest_chart_token_usage[name] = 0
    rest_module._rest_chart_cost_trend.clear()


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
    _reset_rest_module()
    server = RESTAPIServer(
        project_name="test-charts",
        metrics_dir=tmp_metrics_dir,
        port=19900,
        host="127.0.0.1",
    )
    return server


@pytest.fixture()
async def client(rest_server):
    """aiohttp TestClient wrapping the REST server."""
    async with TestClient(TestServer(rest_server.app)) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /api/charts/token-usage
# ---------------------------------------------------------------------------

async def test_get_token_usage_returns_200(client):
    """GET /api/charts/token-usage returns HTTP 200."""
    resp = await client.get("/api/charts/token-usage")
    assert resp.status == 200


async def test_get_token_usage_returns_json_object(client):
    """GET /api/charts/token-usage returns a JSON object."""
    resp = await client.get("/api/charts/token-usage")
    data = await resp.json()
    assert isinstance(data, dict)


async def test_get_token_usage_has_required_fields(client):
    """GET /api/charts/token-usage response has 'agents' and 'max' fields."""
    resp = await client.get("/api/charts/token-usage")
    data = await resp.json()
    assert "agents" in data, "Missing 'agents' field"
    assert "max" in data, "Missing 'max' field"


async def test_get_token_usage_returns_all_13_agents(client):
    """GET /api/charts/token-usage returns all 13 panel agents."""
    resp = await client.get("/api/charts/token-usage")
    data = await resp.json()
    agents = data["agents"]
    assert len(agents) == 13, f"Expected 13 agents, got {len(agents)}"


async def test_get_token_usage_contains_all_panel_agent_names(client):
    """GET /api/charts/token-usage includes all 13 canonical agent names."""
    resp = await client.get("/api/charts/token-usage")
    data = await resp.json()
    returned_names = {a["name"] for a in data["agents"]}
    for name in PANEL_AGENT_NAMES:
        assert name in returned_names, f"Missing agent: {name}"


async def test_get_token_usage_agent_has_required_fields(client):
    """GET /api/charts/token-usage each agent entry has 'name' and 'tokens'."""
    resp = await client.get("/api/charts/token-usage")
    data = await resp.json()
    for agent in data["agents"]:
        assert "name" in agent, f"Agent missing 'name': {agent}"
        assert "tokens" in agent, f"Agent missing 'tokens': {agent}"


async def test_get_token_usage_default_tokens_are_zero(client):
    """GET /api/charts/token-usage all agents start at 0 tokens."""
    resp = await client.get("/api/charts/token-usage")
    data = await resp.json()
    for agent in data["agents"]:
        assert agent["tokens"] == 0, f"Expected 0 tokens for {agent['name']}, got {agent['tokens']}"


async def test_get_token_usage_max_is_zero_by_default(client):
    """GET /api/charts/token-usage max is 0 when no tokens recorded."""
    resp = await client.get("/api/charts/token-usage")
    data = await resp.json()
    assert data["max"] == 0


async def test_get_token_usage_sorted_descending_by_tokens(client):
    """GET /api/charts/token-usage agents are sorted descending by tokens."""
    # First add some tokens
    await client.post("/api/charts/token-usage", json={"agent": "coding", "tokens": 5000, "set": True})
    await client.post("/api/charts/token-usage", json={"agent": "ops", "tokens": 2000, "set": True})

    resp = await client.get("/api/charts/token-usage")
    data = await resp.json()
    token_values = [a["tokens"] for a in data["agents"]]
    assert token_values == sorted(token_values, reverse=True), \
        f"Agents not sorted by tokens descending: {token_values}"


# ---------------------------------------------------------------------------
# GET /api/charts/cost-trend
# ---------------------------------------------------------------------------

async def test_get_cost_trend_returns_200(client):
    """GET /api/charts/cost-trend returns HTTP 200."""
    resp = await client.get("/api/charts/cost-trend")
    assert resp.status == 200


async def test_get_cost_trend_returns_json_object(client):
    """GET /api/charts/cost-trend returns a JSON object."""
    resp = await client.get("/api/charts/cost-trend")
    data = await resp.json()
    assert isinstance(data, dict)


async def test_get_cost_trend_has_sessions_field(client):
    """GET /api/charts/cost-trend response has 'sessions' field."""
    resp = await client.get("/api/charts/cost-trend")
    data = await resp.json()
    assert "sessions" in data, "Missing 'sessions' field"


async def test_get_cost_trend_sessions_is_list(client):
    """GET /api/charts/cost-trend sessions is a list."""
    resp = await client.get("/api/charts/cost-trend")
    data = await resp.json()
    assert isinstance(data["sessions"], list)


async def test_get_cost_trend_empty_by_default(client):
    """GET /api/charts/cost-trend returns empty sessions when no data."""
    resp = await client.get("/api/charts/cost-trend")
    data = await resp.json()
    assert data["sessions"] == []


async def test_get_cost_trend_returns_seeded_data(client):
    """GET /api/charts/cost-trend returns data that was directly seeded."""
    # Directly seed cost trend data
    rest_module._rest_chart_cost_trend.extend([
        {"session": 1, "cost": 1.50},
        {"session": 2, "cost": 2.25},
        {"session": 3, "cost": 0.80},
    ])
    resp = await client.get("/api/charts/cost-trend")
    data = await resp.json()
    assert len(data["sessions"]) == 3
    assert data["sessions"][0]["session"] == 1
    assert data["sessions"][0]["cost"] == 1.50


async def test_get_cost_trend_session_has_required_fields(client):
    """GET /api/charts/cost-trend session entries have 'session' and 'cost' fields."""
    rest_module._rest_chart_cost_trend.append({"session": 1, "cost": 2.50})
    resp = await client.get("/api/charts/cost-trend")
    data = await resp.json()
    assert len(data["sessions"]) > 0
    for s in data["sessions"]:
        assert "session" in s, f"Session entry missing 'session': {s}"
        assert "cost" in s, f"Session entry missing 'cost': {s}"


async def test_get_cost_trend_capped_at_10(client):
    """GET /api/charts/cost-trend returns at most 10 sessions."""
    for i in range(15):
        rest_module._rest_chart_cost_trend.append({"session": i + 1, "cost": float(i)})
    resp = await client.get("/api/charts/cost-trend")
    data = await resp.json()
    assert len(data["sessions"]) <= 10, f"Expected at most 10 sessions, got {len(data['sessions'])}"


# ---------------------------------------------------------------------------
# GET /api/charts/success-rate
# ---------------------------------------------------------------------------

async def test_get_success_rate_returns_200(client):
    """GET /api/charts/success-rate returns HTTP 200."""
    resp = await client.get("/api/charts/success-rate")
    assert resp.status == 200


async def test_get_success_rate_returns_json_object(client):
    """GET /api/charts/success-rate returns a JSON object."""
    resp = await client.get("/api/charts/success-rate")
    data = await resp.json()
    assert isinstance(data, dict)


async def test_get_success_rate_has_agents_field(client):
    """GET /api/charts/success-rate response has 'agents' field."""
    resp = await client.get("/api/charts/success-rate")
    data = await resp.json()
    assert "agents" in data, "Missing 'agents' field"


async def test_get_success_rate_returns_all_13_agents(client):
    """GET /api/charts/success-rate returns all 13 panel agents."""
    resp = await client.get("/api/charts/success-rate")
    data = await resp.json()
    assert len(data["agents"]) == 13, f"Expected 13 agents, got {len(data['agents'])}"


async def test_get_success_rate_contains_all_panel_agents(client):
    """GET /api/charts/success-rate includes all 13 canonical agent names."""
    resp = await client.get("/api/charts/success-rate")
    data = await resp.json()
    returned_names = {a["name"] for a in data["agents"]}
    for name in PANEL_AGENT_NAMES:
        assert name in returned_names, f"Missing agent: {name}"


async def test_get_success_rate_agent_has_required_fields(client):
    """GET /api/charts/success-rate each agent has 'name', 'rate', 'total' fields."""
    resp = await client.get("/api/charts/success-rate")
    data = await resp.json()
    for agent in data["agents"]:
        assert "name" in agent, f"Agent missing 'name': {agent}"
        assert "rate" in agent, f"Agent missing 'rate': {agent}"
        assert "total" in agent, f"Agent missing 'total': {agent}"


async def test_get_success_rate_rates_are_between_0_and_1(client):
    """GET /api/charts/success-rate all rates are in [0.0, 1.0]."""
    resp = await client.get("/api/charts/success-rate")
    data = await resp.json()
    for agent in data["agents"]:
        assert 0.0 <= agent["rate"] <= 1.0, \
            f"Rate out of range for {agent['name']}: {agent['rate']}"


async def test_get_success_rate_reflects_persisted_data(client):
    """GET /api/charts/success-rate reflects success_rate from .agent_metrics.json."""
    resp = await client.get("/api/charts/success-rate")
    data = await resp.json()
    agent_map = {a["name"]: a for a in data["agents"]}
    # coding has 0.95 in fixture
    assert agent_map["coding"]["rate"] == 0.95
    # ops has 0.80 in fixture
    assert agent_map["ops"]["rate"] == 0.80


async def test_get_success_rate_total_reflects_persisted_data(client):
    """GET /api/charts/success-rate total invocations come from stored metrics."""
    resp = await client.get("/api/charts/success-rate")
    data = await resp.json()
    agent_map = {a["name"]: a for a in data["agents"]}
    assert agent_map["coding"]["total"] == 20
    assert agent_map["ops"]["total"] == 15


# ---------------------------------------------------------------------------
# POST /api/charts/token-usage
# ---------------------------------------------------------------------------

async def test_post_token_usage_returns_200(client):
    """POST /api/charts/token-usage returns HTTP 200."""
    resp = await client.post("/api/charts/token-usage", json={"agent": "coding", "tokens": 1000})
    assert resp.status == 200


async def test_post_token_usage_increments_tokens(client):
    """POST /api/charts/token-usage increments agent's token count."""
    await client.post("/api/charts/token-usage", json={"agent": "coding", "tokens": 1000})
    await client.post("/api/charts/token-usage", json={"agent": "coding", "tokens": 500})
    resp = await client.get("/api/charts/token-usage")
    data = await resp.json()
    agent_map = {a["name"]: a for a in data["agents"]}
    assert agent_map["coding"]["tokens"] == 1500


async def test_post_token_usage_set_mode_overwrites(client):
    """POST /api/charts/token-usage with set=true overwrites token count."""
    await client.post("/api/charts/token-usage", json={"agent": "coding", "tokens": 9999})
    await client.post("/api/charts/token-usage", json={"agent": "coding", "tokens": 500, "set": True})
    resp = await client.get("/api/charts/token-usage")
    data = await resp.json()
    agent_map = {a["name"]: a for a in data["agents"]}
    assert agent_map["coding"]["tokens"] == 500


async def test_post_token_usage_updates_max(client):
    """POST /api/charts/token-usage updates the 'max' value."""
    await client.post("/api/charts/token-usage", json={"agent": "coding", "tokens": 50000, "set": True})
    resp = await client.get("/api/charts/token-usage")
    data = await resp.json()
    assert data["max"] == 50000


async def test_post_token_usage_response_includes_agents(client):
    """POST /api/charts/token-usage response includes updated agents list."""
    resp = await client.post("/api/charts/token-usage", json={"agent": "ops", "tokens": 2000})
    data = await resp.json()
    assert "agents" in data
    assert len(data["agents"]) == 13


async def test_post_token_usage_unknown_agent_returns_400(client):
    """POST /api/charts/token-usage with unknown agent returns 400."""
    resp = await client.post("/api/charts/token-usage", json={"agent": "nonexistent_agent", "tokens": 100})
    assert resp.status == 400
    data = await resp.json()
    assert "error" in data


async def test_post_token_usage_missing_agent_returns_400(client):
    """POST /api/charts/token-usage without 'agent' field returns 400."""
    resp = await client.post("/api/charts/token-usage", json={"tokens": 100})
    assert resp.status == 400
    data = await resp.json()
    assert "error" in data


async def test_post_token_usage_missing_tokens_returns_400(client):
    """POST /api/charts/token-usage without 'tokens' field returns 400."""
    resp = await client.post("/api/charts/token-usage", json={"agent": "coding"})
    assert resp.status == 400
    data = await resp.json()
    assert "error" in data


async def test_post_token_usage_invalid_json_returns_400(client):
    """POST /api/charts/token-usage with invalid JSON body returns 400."""
    resp = await client.post(
        "/api/charts/token-usage",
        data="not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status == 400


async def test_post_token_usage_non_numeric_tokens_returns_400(client):
    """POST /api/charts/token-usage with non-numeric 'tokens' field returns 400."""
    resp = await client.post("/api/charts/token-usage", json={"agent": "coding", "tokens": "many"})
    assert resp.status == 400


async def test_post_token_usage_all_agents_work(client):
    """POST /api/charts/token-usage works for every canonical agent."""
    for name in PANEL_AGENT_NAMES:
        resp = await client.post("/api/charts/token-usage", json={"agent": name, "tokens": 100})
        assert resp.status == 200, f"Expected 200 for agent {name}, got {resp.status}"


async def test_post_token_usage_cumulative_across_agents(client):
    """POST /api/charts/token-usage cumulative increments across multiple agents."""
    await client.post("/api/charts/token-usage", json={"agent": "linear", "tokens": 3000, "set": True})
    await client.post("/api/charts/token-usage", json={"agent": "coding", "tokens": 5000, "set": True})
    await client.post("/api/charts/token-usage", json={"agent": "ops", "tokens": 2000, "set": True})

    resp = await client.get("/api/charts/token-usage")
    data = await resp.json()
    agent_map = {a["name"]: a for a in data["agents"]}
    assert agent_map["linear"]["tokens"] == 3000
    assert agent_map["coding"]["tokens"] == 5000
    assert agent_map["ops"]["tokens"] == 2000
    assert data["max"] == 5000
