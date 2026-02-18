"""Tests for AI-77: REQ-INTEGRATION-003 GitHub Access - PR and Issue Management.

Covers:
- POST /api/github/query returns a response
- GET /api/github/prs returns list
- GET /api/github/issues returns list
- GET /api/github/repo returns repo info
- Graceful degradation when GITHUB_REPO env var is not set
- Valid JSON responses with required fields
- Query parameter handling (state, limit)
- Missing/invalid request body handling
"""

import json
import os
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
        "project_name": "test-github",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T12:00:00Z",
        "total_sessions": 2,
        "total_tokens": 10000,
        "total_cost_usd": 1.00,
        "total_duration_seconds": 600.0,
        "agents": {},
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
        project_name="test-github",
        metrics_dir=tmp_metrics_dir,
        port=19910,
        host="127.0.0.1",
    )
    return server


@pytest.fixture()
async def client(rest_server):
    """aiohttp TestClient wrapping the REST server."""
    async with TestClient(TestServer(rest_server.app)) as c:
        yield c


@pytest.fixture()
async def client_with_repo(rest_server, monkeypatch):
    """TestClient with GITHUB_REPO env var set."""
    monkeypatch.setenv("GITHUB_REPO", "agent-engineers/agent-dashboard")
    async with TestClient(TestServer(rest_server.app)) as c:
        yield c


@pytest.fixture()
async def client_no_repo(rest_server, monkeypatch):
    """TestClient with GITHUB_REPO env var unset (graceful degradation)."""
    monkeypatch.delenv("GITHUB_REPO", raising=False)
    async with TestClient(TestServer(rest_server.app)) as c:
        yield c


# ---------------------------------------------------------------------------
# POST /api/github/query
# ---------------------------------------------------------------------------

async def test_github_query_returns_200(client_with_repo):
    """POST /api/github/query returns HTTP 200."""
    resp = await client_with_repo.post(
        "/api/github/query",
        json={"query": "What is the status of PR #1?"}
    )
    assert resp.status == 200


async def test_github_query_returns_json_object(client_with_repo):
    """POST /api/github/query returns a JSON object."""
    resp = await client_with_repo.post(
        "/api/github/query",
        json={"query": "List all open PRs"}
    )
    data = await resp.json()
    assert isinstance(data, dict)


async def test_github_query_has_response_field(client_with_repo):
    """POST /api/github/query response contains 'response' field."""
    resp = await client_with_repo.post(
        "/api/github/query",
        json={"query": "What are the open PRs?"}
    )
    data = await resp.json()
    assert "response" in data, "Missing 'response' field"


async def test_github_query_has_data_field(client_with_repo):
    """POST /api/github/query response contains 'data' field."""
    resp = await client_with_repo.post(
        "/api/github/query",
        json={"query": "List issues"}
    )
    data = await resp.json()
    assert "data" in data, "Missing 'data' field"


async def test_github_query_has_timestamp(client_with_repo):
    """POST /api/github/query response contains 'timestamp' field."""
    resp = await client_with_repo.post(
        "/api/github/query",
        json={"query": "Show PR diffs"}
    )
    data = await resp.json()
    assert "timestamp" in data, "Missing 'timestamp' field"


async def test_github_query_missing_query_returns_400(client_with_repo):
    """POST /api/github/query with empty body returns 400."""
    resp = await client_with_repo.post(
        "/api/github/query",
        json={}
    )
    assert resp.status == 400


async def test_github_query_empty_query_returns_400(client_with_repo):
    """POST /api/github/query with empty string query returns 400."""
    resp = await client_with_repo.post(
        "/api/github/query",
        json={"query": ""}
    )
    assert resp.status == 400


async def test_github_query_invalid_json_returns_400(client_with_repo):
    """POST /api/github/query with invalid JSON returns 400."""
    resp = await client_with_repo.post(
        "/api/github/query",
        data="not-json",
        headers={"Content-Type": "application/json"}
    )
    assert resp.status == 400


async def test_github_query_with_context(client_with_repo):
    """POST /api/github/query with context field returns 200."""
    resp = await client_with_repo.post(
        "/api/github/query",
        json={
            "query": "Show PR #42",
            "context": {"branch": "main", "user": "test-user"}
        }
    )
    assert resp.status == 200
    data = await resp.json()
    assert "response" in data


async def test_github_query_data_contains_query(client_with_repo):
    """POST /api/github/query response data echoes the query."""
    query_text = "What PRs are merged today?"
    resp = await client_with_repo.post(
        "/api/github/query",
        json={"query": query_text}
    )
    data = await resp.json()
    assert data.get("data", {}).get("query") == query_text


# ---------------------------------------------------------------------------
# GET /api/github/prs
# ---------------------------------------------------------------------------

async def test_github_prs_returns_200(client_with_repo):
    """GET /api/github/prs returns HTTP 200."""
    resp = await client_with_repo.get("/api/github/prs")
    assert resp.status == 200


async def test_github_prs_returns_json_object(client_with_repo):
    """GET /api/github/prs returns a JSON object."""
    resp = await client_with_repo.get("/api/github/prs")
    data = await resp.json()
    assert isinstance(data, dict)


async def test_github_prs_has_prs_field(client_with_repo):
    """GET /api/github/prs response has 'prs' list field."""
    resp = await client_with_repo.get("/api/github/prs")
    data = await resp.json()
    assert "prs" in data, "Missing 'prs' field"
    assert isinstance(data["prs"], list)


async def test_github_prs_has_repo_field(client_with_repo):
    """GET /api/github/prs response has 'repo' field."""
    resp = await client_with_repo.get("/api/github/prs")
    data = await resp.json()
    assert "repo" in data, "Missing 'repo' field"


async def test_github_prs_has_timestamp(client_with_repo):
    """GET /api/github/prs response has 'timestamp' field."""
    resp = await client_with_repo.get("/api/github/prs")
    data = await resp.json()
    assert "timestamp" in data, "Missing 'timestamp' field"


async def test_github_prs_state_query_param(client_with_repo):
    """GET /api/github/prs accepts state query parameter."""
    resp = await client_with_repo.get("/api/github/prs?state=closed")
    assert resp.status == 200
    data = await resp.json()
    assert data.get("state") == "closed"


async def test_github_prs_limit_query_param(client_with_repo):
    """GET /api/github/prs accepts limit query parameter."""
    resp = await client_with_repo.get("/api/github/prs?limit=5")
    assert resp.status == 200
    data = await resp.json()
    assert data.get("limit") == 5


async def test_github_prs_repo_is_configured(client_with_repo):
    """GET /api/github/prs shows configured=True when GITHUB_REPO is set."""
    resp = await client_with_repo.get("/api/github/prs")
    data = await resp.json()
    assert data.get("configured") is True


# ---------------------------------------------------------------------------
# GET /api/github/issues
# ---------------------------------------------------------------------------

async def test_github_issues_returns_200(client_with_repo):
    """GET /api/github/issues returns HTTP 200."""
    resp = await client_with_repo.get("/api/github/issues")
    assert resp.status == 200


async def test_github_issues_returns_json_object(client_with_repo):
    """GET /api/github/issues returns a JSON object."""
    resp = await client_with_repo.get("/api/github/issues")
    data = await resp.json()
    assert isinstance(data, dict)


async def test_github_issues_has_issues_field(client_with_repo):
    """GET /api/github/issues response has 'issues' list field."""
    resp = await client_with_repo.get("/api/github/issues")
    data = await resp.json()
    assert "issues" in data, "Missing 'issues' field"
    assert isinstance(data["issues"], list)


async def test_github_issues_has_repo_field(client_with_repo):
    """GET /api/github/issues response has 'repo' field."""
    resp = await client_with_repo.get("/api/github/issues")
    data = await resp.json()
    assert "repo" in data, "Missing 'repo' field"


async def test_github_issues_has_timestamp(client_with_repo):
    """GET /api/github/issues response has 'timestamp' field."""
    resp = await client_with_repo.get("/api/github/issues")
    data = await resp.json()
    assert "timestamp" in data, "Missing 'timestamp' field"


async def test_github_issues_state_query_param(client_with_repo):
    """GET /api/github/issues accepts state query parameter."""
    resp = await client_with_repo.get("/api/github/issues?state=all")
    assert resp.status == 200
    data = await resp.json()
    assert data.get("state") == "all"


async def test_github_issues_limit_query_param(client_with_repo):
    """GET /api/github/issues accepts limit query parameter."""
    resp = await client_with_repo.get("/api/github/issues?limit=20")
    assert resp.status == 200
    data = await resp.json()
    assert data.get("limit") == 20


async def test_github_issues_repo_is_configured(client_with_repo):
    """GET /api/github/issues shows configured=True when GITHUB_REPO is set."""
    resp = await client_with_repo.get("/api/github/issues")
    data = await resp.json()
    assert data.get("configured") is True


# ---------------------------------------------------------------------------
# GET /api/github/repo
# ---------------------------------------------------------------------------

async def test_github_repo_returns_200(client_with_repo):
    """GET /api/github/repo returns HTTP 200."""
    resp = await client_with_repo.get("/api/github/repo")
    assert resp.status == 200


async def test_github_repo_returns_json_object(client_with_repo):
    """GET /api/github/repo returns a JSON object."""
    resp = await client_with_repo.get("/api/github/repo")
    data = await resp.json()
    assert isinstance(data, dict)


async def test_github_repo_has_name_field(client_with_repo):
    """GET /api/github/repo response has 'name' field."""
    resp = await client_with_repo.get("/api/github/repo")
    data = await resp.json()
    assert "name" in data, "Missing 'name' field"


async def test_github_repo_has_full_name_field(client_with_repo):
    """GET /api/github/repo response has 'full_name' field."""
    resp = await client_with_repo.get("/api/github/repo")
    data = await resp.json()
    assert "full_name" in data, "Missing 'full_name' field"


async def test_github_repo_has_open_prs_field(client_with_repo):
    """GET /api/github/repo response has 'open_prs' field."""
    resp = await client_with_repo.get("/api/github/repo")
    data = await resp.json()
    assert "open_prs" in data, "Missing 'open_prs' field"


async def test_github_repo_has_open_issues_field(client_with_repo):
    """GET /api/github/repo response has 'open_issues' field."""
    resp = await client_with_repo.get("/api/github/repo")
    data = await resp.json()
    assert "open_issues" in data, "Missing 'open_issues' field"


async def test_github_repo_has_stars_field(client_with_repo):
    """GET /api/github/repo response has 'stars' field."""
    resp = await client_with_repo.get("/api/github/repo")
    data = await resp.json()
    assert "stars" in data, "Missing 'stars' field"


async def test_github_repo_has_timestamp(client_with_repo):
    """GET /api/github/repo response has 'timestamp' field."""
    resp = await client_with_repo.get("/api/github/repo")
    data = await resp.json()
    assert "timestamp" in data, "Missing 'timestamp' field"


async def test_github_repo_full_name_matches_env(client_with_repo, monkeypatch):
    """GET /api/github/repo full_name matches GITHUB_REPO env var."""
    resp = await client_with_repo.get("/api/github/repo")
    data = await resp.json()
    assert data.get("full_name") == "agent-engineers/agent-dashboard"


async def test_github_repo_is_configured(client_with_repo):
    """GET /api/github/repo shows configured=True when GITHUB_REPO is set."""
    resp = await client_with_repo.get("/api/github/repo")
    data = await resp.json()
    assert data.get("configured") is True


# ---------------------------------------------------------------------------
# Graceful degradation: GITHUB_REPO not set
# ---------------------------------------------------------------------------

async def test_github_repo_not_configured_returns_200(client_no_repo):
    """GET /api/github/repo returns 200 even when GITHUB_REPO is not set."""
    resp = await client_no_repo.get("/api/github/repo")
    assert resp.status == 200


async def test_github_repo_not_configured_field(client_no_repo):
    """GET /api/github/repo shows configured=False when GITHUB_REPO is not set."""
    resp = await client_no_repo.get("/api/github/repo")
    data = await resp.json()
    assert data.get("configured") is False


async def test_github_repo_not_configured_name_is_none(client_no_repo):
    """GET /api/github/repo returns name=None when GITHUB_REPO is not set."""
    resp = await client_no_repo.get("/api/github/repo")
    data = await resp.json()
    assert data.get("name") is None


async def test_github_prs_not_configured_returns_200(client_no_repo):
    """GET /api/github/prs returns 200 even when GITHUB_REPO is not set."""
    resp = await client_no_repo.get("/api/github/prs")
    assert resp.status == 200


async def test_github_prs_not_configured_field(client_no_repo):
    """GET /api/github/prs shows configured=False when GITHUB_REPO is not set."""
    resp = await client_no_repo.get("/api/github/prs")
    data = await resp.json()
    assert data.get("configured") is False


async def test_github_prs_not_configured_empty_list(client_no_repo):
    """GET /api/github/prs returns empty prs list when GITHUB_REPO is not set."""
    resp = await client_no_repo.get("/api/github/prs")
    data = await resp.json()
    assert data.get("prs") == []


async def test_github_issues_not_configured_returns_200(client_no_repo):
    """GET /api/github/issues returns 200 even when GITHUB_REPO is not set."""
    resp = await client_no_repo.get("/api/github/issues")
    assert resp.status == 200


async def test_github_issues_not_configured_field(client_no_repo):
    """GET /api/github/issues shows configured=False when GITHUB_REPO is not set."""
    resp = await client_no_repo.get("/api/github/issues")
    data = await resp.json()
    assert data.get("configured") is False


async def test_github_issues_not_configured_empty_list(client_no_repo):
    """GET /api/github/issues returns empty issues list when GITHUB_REPO is not set."""
    resp = await client_no_repo.get("/api/github/issues")
    data = await resp.json()
    assert data.get("issues") == []


async def test_github_query_not_configured_returns_200(client_no_repo):
    """POST /api/github/query returns 200 even when GITHUB_REPO is not set."""
    resp = await client_no_repo.post(
        "/api/github/query",
        json={"query": "What are the open PRs?"}
    )
    assert resp.status == 200


async def test_github_query_not_configured_has_response(client_no_repo):
    """POST /api/github/query returns a response message even without GITHUB_REPO."""
    resp = await client_no_repo.post(
        "/api/github/query",
        json={"query": "Show me all issues"}
    )
    data = await resp.json()
    assert "response" in data
    assert len(data["response"]) > 0


async def test_github_query_not_configured_field(client_no_repo):
    """POST /api/github/query shows configured=False when GITHUB_REPO is not set."""
    resp = await client_no_repo.post(
        "/api/github/query",
        json={"query": "What are the open PRs?"}
    )
    data = await resp.json()
    assert data.get("configured") is False


async def test_github_query_not_configured_mentions_env_var(client_no_repo):
    """POST /api/github/query response mentions GITHUB_REPO when not configured."""
    resp = await client_no_repo.post(
        "/api/github/query",
        json={"query": "List PRs"}
    )
    data = await resp.json()
    assert "GITHUB_REPO" in data.get("response", "")


# ---------------------------------------------------------------------------
# OPTIONS (CORS preflight) - AI-77 endpoints
# ---------------------------------------------------------------------------

async def test_github_query_options_returns_204(client):
    """OPTIONS /api/github/query returns 204 for CORS preflight."""
    resp = await client.options("/api/github/query")
    assert resp.status == 204


async def test_github_prs_options_returns_204(client):
    """OPTIONS /api/github/prs returns 204 for CORS preflight."""
    resp = await client.options("/api/github/prs")
    assert resp.status == 204


async def test_github_issues_options_returns_204(client):
    """OPTIONS /api/github/issues returns 204 for CORS preflight."""
    resp = await client.options("/api/github/issues")
    assert resp.status == 204


async def test_github_repo_options_returns_204(client):
    """OPTIONS /api/github/repo returns 204 for CORS preflight."""
    resp = await client.options("/api/github/repo")
    assert resp.status == 204
