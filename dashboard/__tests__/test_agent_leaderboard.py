"""Tests for AI-84: REQ-METRICS-002 Agent Leaderboard - XP Ranking and Statistics.

Covers:
- GET /api/agents/leaderboard returns all 13 agents ranked by XP descending
- Rank numbers are correct (1-indexed, sequential)
- POST /api/agents/{name}/xp adds XP correctly (increment mode)
- POST /api/agents/{name}/xp with set=true overwrites XP
- POST /api/agents/{name}/xp triggers re-ranking
- POST /api/agents/{name}/xp with unknown agent returns 404
- POST /api/agents/{name}/xp with invalid JSON returns 400
- POST /api/agents/{name}/xp with missing xp field returns 400
- Leaderboard contains all required fields per agent
- XP addition is reflected in subsequent GET /api/agents/leaderboard
- Level is computed correctly from XP (using xp.py thresholds)
- Ties resolved stably (alphabetical by name)
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
        "project_name": "test-leaderboard",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T12:00:00Z",
        "total_sessions": 3,
        "total_tokens": 50_000,
        "total_cost_usd": 1.50,
        "total_duration_seconds": 1800.0,
        "agents": {
            "coding": {
                "xp": 1500,
                "level": 6,
                "success_rate": 0.95,
                "avg_duration_seconds": 120.0,
                "total_cost_usd": 4.50,
                "total_invocations": 20,
                "successful_invocations": 19,
                "failed_invocations": 1,
            },
            "ops": {
                "xp": 1200,
                "level": 5,
                "success_rate": 0.98,
                "avg_duration_seconds": 45.0,
                "total_cost_usd": 2.10,
                "total_invocations": 50,
                "successful_invocations": 49,
                "failed_invocations": 1,
            },
        },
        "events": [],
        "sessions": [],
    }
    metrics_path = tmp_path / ".agent_metrics.json"
    metrics_path.write_text(json.dumps(metrics))
    return metrics_path


def _reset_rest_module():
    """Reset module-level state in rest_api_server before each test."""
    rest_module._agent_states.clear()
    rest_module._requirements_cache.clear()
    rest_module._decisions_log.clear()
    rest_module._ws_clients.clear()
    rest_module._agent_status_details.clear()
    rest_module._rest_agent_recent_events.clear()
    # Reset leaderboard XP store
    rest_module._rest_agent_xp_store.clear()
    # Reset global metrics
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
        project_name="test-leaderboard",
        metrics_dir=tmp_metrics_dir,
        port=19800,
        host="127.0.0.1",
    )
    return server


@pytest.fixture()
async def client(rest_server):
    """aiohttp TestClient wrapping the REST server."""
    async with TestClient(TestServer(rest_server.app)) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /api/agents/leaderboard
# ---------------------------------------------------------------------------

async def test_get_leaderboard_returns_200(client):
    """GET /api/agents/leaderboard returns HTTP 200."""
    resp = await client.get("/api/agents/leaderboard")
    assert resp.status == 200


async def test_get_leaderboard_returns_list(client):
    """GET /api/agents/leaderboard returns a JSON list."""
    resp = await client.get("/api/agents/leaderboard")
    data = await resp.json()
    assert isinstance(data, list)


async def test_get_leaderboard_returns_all_13_agents(client):
    """GET /api/agents/leaderboard returns all 13 panel agents."""
    resp = await client.get("/api/agents/leaderboard")
    data = await resp.json()
    assert len(data) == 13, f"Expected 13 agents, got {len(data)}: {[a['name'] for a in data]}"


async def test_get_leaderboard_contains_all_panel_agent_names(client):
    """GET /api/agents/leaderboard includes all canonical agent names."""
    resp = await client.get("/api/agents/leaderboard")
    data = await resp.json()
    returned_names = {a['name'] for a in data}
    for name in PANEL_AGENT_NAMES:
        assert name in returned_names, f"Missing agent: {name}"


async def test_get_leaderboard_rank_numbers_are_sequential(client):
    """GET /api/agents/leaderboard rank numbers start at 1 and are sequential."""
    resp = await client.get("/api/agents/leaderboard")
    data = await resp.json()
    ranks = [a['rank'] for a in data]
    assert ranks == list(range(1, len(data) + 1)), f"Ranks are not sequential: {ranks}"


async def test_get_leaderboard_sorted_by_xp_descending(client):
    """GET /api/agents/leaderboard entries are sorted by XP descending."""
    resp = await client.get("/api/agents/leaderboard")
    data = await resp.json()
    xp_values = [a['xp'] for a in data]
    assert xp_values == sorted(xp_values, reverse=True), \
        f"Leaderboard not sorted by XP descending: {xp_values}"


async def test_get_leaderboard_persisted_xp_reflected(client):
    """GET /api/agents/leaderboard reflects XP from .agent_metrics.json for seeded agents."""
    resp = await client.get("/api/agents/leaderboard")
    data = await resp.json()
    agent_map = {a['name']: a for a in data}
    # coding has 1500 XP in the fixture
    assert agent_map['coding']['xp'] == 1500
    # ops has 1200 XP
    assert agent_map['ops']['xp'] == 1200


async def test_get_leaderboard_required_fields_per_agent(client):
    """GET /api/agents/leaderboard each agent has all required fields."""
    resp = await client.get("/api/agents/leaderboard")
    data = await resp.json()
    required_fields = ['rank', 'name', 'xp', 'level', 'success_rate', 'avg_duration_s', 'total_cost_usd', 'status']
    for agent in data:
        for field in required_fields:
            assert field in agent, f"Agent {agent.get('name', '?')} missing field: {field}"


async def test_get_leaderboard_rank_1_has_highest_xp(client):
    """GET /api/agents/leaderboard rank 1 agent has the highest XP."""
    resp = await client.get("/api/agents/leaderboard")
    data = await resp.json()
    max_xp = max(a['xp'] for a in data)
    rank1 = next(a for a in data if a['rank'] == 1)
    assert rank1['xp'] == max_xp


async def test_get_leaderboard_level_computed_from_xp(client):
    """GET /api/agents/leaderboard level is correctly computed from XP."""
    resp = await client.get("/api/agents/leaderboard")
    data = await resp.json()
    agent_map = {a['name']: a for a in data}
    # coding: 1500 XP -> level 6 (Principal: threshold at 1500)
    assert agent_map['coding']['level'] == 6
    # ops: 1200 XP -> level 5 (Staff: threshold 800-1500)
    assert agent_map['ops']['level'] == 5


async def test_get_leaderboard_status_defaults_to_idle(client):
    """GET /api/agents/leaderboard agents with no status default to 'idle'."""
    resp = await client.get("/api/agents/leaderboard")
    data = await resp.json()
    for agent in data:
        assert agent['status'] in ('idle', 'running', 'paused', 'error'), \
            f"Unexpected status: {agent['status']}"


# ---------------------------------------------------------------------------
# POST /api/agents/{name}/xp - add XP
# ---------------------------------------------------------------------------

async def test_post_xp_returns_200(client):
    """POST /api/agents/coding/xp returns HTTP 200."""
    resp = await client.post("/api/agents/coding/xp", json={"xp": 100})
    assert resp.status == 200


async def test_post_xp_adds_xp_to_agent(client):
    """POST /api/agents/coding/xp with increment adds XP correctly."""
    # First get baseline XP
    lb_resp = await client.get("/api/agents/leaderboard")
    lb = await lb_resp.json()
    agent_map = {a['name']: a for a in lb}
    baseline_xp = agent_map['coding']['xp']

    # Add 100 XP
    resp = await client.post("/api/agents/coding/xp", json={"xp": 100})
    data = await resp.json()
    assert data['xp'] == baseline_xp + 100
    assert data['agent'] == 'coding'


async def test_post_xp_set_mode_overwrites(client):
    """POST /api/agents/coding/xp with set=true overwrites XP."""
    resp = await client.post("/api/agents/coding/xp", json={"xp": 999, "set": True})
    data = await resp.json()
    assert data['xp'] == 999


async def test_post_xp_triggers_reranking(client):
    """POST /api/agents/ops/xp with high value re-ranks ops to position 1."""
    # Give ops a very high XP value
    resp = await client.post("/api/agents/ops/xp", json={"xp": 9999, "set": True})
    data = await resp.json()
    leaderboard = data['leaderboard']
    rank1 = next(a for a in leaderboard if a['rank'] == 1)
    assert rank1['name'] == 'ops', f"Expected ops at rank 1, got {rank1['name']}"


async def test_post_xp_response_includes_leaderboard(client):
    """POST /api/agents/coding/xp response includes updated leaderboard."""
    resp = await client.post("/api/agents/coding/xp", json={"xp": 50})
    data = await resp.json()
    assert 'leaderboard' in data
    assert isinstance(data['leaderboard'], list)
    assert len(data['leaderboard']) == 13


async def test_post_xp_response_includes_level(client):
    """POST /api/agents/coding/xp response includes computed level."""
    resp = await client.post("/api/agents/coding/xp", json={"xp": 0, "set": True})
    data = await resp.json()
    assert 'level' in data
    # 0 XP -> level 1 (Intern)
    assert data['level'] == 1


async def test_post_xp_sequential_increments_are_cumulative(client):
    """Multiple POST /api/agents/linear/xp calls accumulate XP correctly."""
    # Start at 0
    await client.post("/api/agents/linear/xp", json={"xp": 0, "set": True})
    # Add 100 three times
    for _ in range(3):
        await client.post("/api/agents/linear/xp", json={"xp": 100})
    lb_resp = await client.get("/api/agents/leaderboard")
    lb = await lb_resp.json()
    agent_map = {a['name']: a for a in lb}
    assert agent_map['linear']['xp'] == 300


# ---------------------------------------------------------------------------
# GET /api/agents/leaderboard - reflects XP after POST
# ---------------------------------------------------------------------------

async def test_leaderboard_reflects_xp_after_post(client):
    """GET /api/agents/leaderboard reflects XP added via POST."""
    await client.post("/api/agents/github/xp", json={"xp": 500, "set": True})
    lb_resp = await client.get("/api/agents/leaderboard")
    lb = await lb_resp.json()
    agent_map = {a['name']: a for a in lb}
    assert agent_map['github']['xp'] == 500


async def test_leaderboard_rank_order_after_multiple_xp_posts(client):
    """Leaderboard rank order is correct after multiple XP posts."""
    # Set explicit XP values
    await client.post("/api/agents/slack/xp", json={"xp": 3000, "set": True})
    await client.post("/api/agents/coding/xp", json={"xp": 2000, "set": True})
    await client.post("/api/agents/ops/xp", json={"xp": 1000, "set": True})

    lb_resp = await client.get("/api/agents/leaderboard")
    lb = await lb_resp.json()
    agent_map = {a['name']: a for a in lb}

    assert agent_map['slack']['rank'] < agent_map['coding']['rank']
    assert agent_map['coding']['rank'] < agent_map['ops']['rank']


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------

async def test_post_xp_unknown_agent_returns_404(client):
    """POST /api/agents/nonexistent/xp returns 404 for unknown agent."""
    resp = await client.post("/api/agents/nonexistent_agent/xp", json={"xp": 100})
    assert resp.status == 404
    data = await resp.json()
    assert 'error' in data


async def test_post_xp_invalid_json_returns_400(client):
    """POST /api/agents/coding/xp with invalid JSON body returns 400."""
    resp = await client.post(
        "/api/agents/coding/xp",
        data="not-json",
        headers={"Content-Type": "application/json"}
    )
    assert resp.status == 400


async def test_post_xp_missing_xp_field_returns_400(client):
    """POST /api/agents/coding/xp with missing 'xp' field returns 400."""
    resp = await client.post("/api/agents/coding/xp", json={"amount": 50})
    assert resp.status == 400
    data = await resp.json()
    assert 'error' in data


async def test_post_xp_non_numeric_xp_returns_400(client):
    """POST /api/agents/coding/xp with non-numeric 'xp' field returns 400."""
    resp = await client.post("/api/agents/coding/xp", json={"xp": "lots"})
    assert resp.status == 400


# ---------------------------------------------------------------------------
# Level thresholds
# ---------------------------------------------------------------------------

async def test_level_1_at_0_xp(client):
    """Agent with 0 XP is at level 1."""
    await client.post("/api/agents/linear/xp", json={"xp": 0, "set": True})
    lb_resp = await client.get("/api/agents/leaderboard")
    lb = await lb_resp.json()
    agent_map = {a['name']: a for a in lb}
    assert agent_map['linear']['level'] == 1


async def test_level_2_at_50_xp(client):
    """Agent with exactly 50 XP is at level 2."""
    await client.post("/api/agents/linear/xp", json={"xp": 50, "set": True})
    lb_resp = await client.get("/api/agents/leaderboard")
    lb = await lb_resp.json()
    agent_map = {a['name']: a for a in lb}
    assert agent_map['linear']['level'] == 2


async def test_level_8_at_5000_xp(client):
    """Agent with 5000 XP is at max level 8."""
    await client.post("/api/agents/linear/xp", json={"xp": 5000, "set": True})
    lb_resp = await client.get("/api/agents/leaderboard")
    lb = await lb_resp.json()
    agent_map = {a['name']: a for a in lb}
    assert agent_map['linear']['level'] == 8


# ---------------------------------------------------------------------------
# Stable tie-breaking
# ---------------------------------------------------------------------------

async def test_tie_breaking_alphabetical(client):
    """Agents with equal XP are ranked alphabetically by name."""
    # Set all agents to same XP = 0
    for name in PANEL_AGENT_NAMES:
        await client.post(f"/api/agents/{name}/xp", json={"xp": 0, "set": True})

    lb_resp = await client.get("/api/agents/leaderboard")
    lb = await lb_resp.json()

    names = [a['name'] for a in lb]
    assert names == sorted(names), f"Tie-breaking not alphabetical: {names}"
