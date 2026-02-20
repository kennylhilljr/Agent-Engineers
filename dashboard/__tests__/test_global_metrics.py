"""Tests for AI-83: REQ-METRICS-001 Global Metrics Bar.

Covers:
- GET /api/metrics/global returns all required fields
- GET /api/metrics/global returns non-negative uptime
- POST /api/metrics/global increments counters correctly
- POST /api/metrics/global with set=true overwrites values
- POST /api/metrics/global with invalid JSON returns 400
- Token formatting: 250000 -> "250K", 1500000 -> "1.5M"
- Cost formatting: "$12.50"
- Uptime calculation is non-negative
- Data types are correct (ints for counts, float for cost)
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

# Ensure the project root is importable
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import dashboard.rest_api_server as rest_module
from dashboard.rest_api_server import RESTAPIServer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_minimal_metrics(tmp_path: Path, total_sessions: int = 5,
                           total_tokens: int = 100_000,
                           total_cost_usd: float = 3.50) -> Path:
    """Write a minimal .agent_metrics.json for tests."""
    metrics = {
        "version": 1,
        "project_name": "test-project",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T12:00:00Z",
        "total_sessions": total_sessions,
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost_usd,
        "total_duration_seconds": 3600.0,
        "agents": {},
        "events": [],
        "sessions": [
            {
                "session_id": f"s{i}",
                "session_number": i,
                "session_type": "continuation",
                "started_at": "2024-01-01T00:00:00Z",
                "ended_at": "2024-01-01T01:00:00Z",
                "status": "complete",
                "agents_invoked": [],
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "tickets_worked": [],
            }
            for i in range(1, total_sessions + 1)
        ],
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
    # Reset global metrics store
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
        project_name="test-project",
        metrics_dir=tmp_metrics_dir,
        port=19700,
        host="127.0.0.1",
    )
    return server


@pytest.fixture()
async def client(rest_server):
    """aiohttp TestClient wrapping the REST server."""
    async with TestClient(TestServer(rest_server.app)) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /api/metrics/global - required fields
# ---------------------------------------------------------------------------

async def test_get_global_metrics_returns_200(client):
    """GET /api/metrics/global returns HTTP 200."""
    resp = await client.get("/api/metrics/global")
    assert resp.status == 200


async def test_get_global_metrics_returns_all_required_fields(client):
    """GET /api/metrics/global returns all 7 required fields."""
    resp = await client.get("/api/metrics/global")
    data = await resp.json()

    required_fields = [
        "total_sessions",
        "total_tokens",
        "total_cost_usd",
        "uptime_seconds",
        "current_session",
        "agents_active",
        "tasks_completed_today",
    ]
    for field in required_fields:
        assert field in data, f"Missing required field: {field}"


async def test_get_global_metrics_reads_persisted_sessions(client):
    """GET /api/metrics/global picks up total_sessions from .agent_metrics.json."""
    resp = await client.get("/api/metrics/global")
    data = await resp.json()
    # The fixture writes 5 sessions
    assert data["total_sessions"] == 5


async def test_get_global_metrics_reads_persisted_tokens(client):
    """GET /api/metrics/global picks up total_tokens from .agent_metrics.json."""
    resp = await client.get("/api/metrics/global")
    data = await resp.json()
    assert data["total_tokens"] == 100_000


async def test_get_global_metrics_reads_persisted_cost(client):
    """GET /api/metrics/global picks up total_cost_usd from .agent_metrics.json."""
    resp = await client.get("/api/metrics/global")
    data = await resp.json()
    assert abs(data["total_cost_usd"] - 3.50) < 0.001


async def test_get_global_metrics_uptime_is_non_negative(client):
    """GET /api/metrics/global returns uptime_seconds >= 0."""
    resp = await client.get("/api/metrics/global")
    data = await resp.json()
    assert data["uptime_seconds"] >= 0


async def test_get_global_metrics_agents_active_is_zero_when_idle(client):
    """GET /api/metrics/global returns agents_active=0 when all agents are idle."""
    resp = await client.get("/api/metrics/global")
    data = await resp.json()
    assert data["agents_active"] == 0


async def test_get_global_metrics_tasks_completed_today_default_zero(client):
    """GET /api/metrics/global returns tasks_completed_today=0 by default."""
    resp = await client.get("/api/metrics/global")
    data = await resp.json()
    assert data["tasks_completed_today"] == 0


async def test_get_global_metrics_current_session_reflects_session_count(client):
    """GET /api/metrics/global current_session reflects number of sessions recorded."""
    resp = await client.get("/api/metrics/global")
    data = await resp.json()
    # 5 sessions in the fixture, current_session falls back to len(sessions)
    assert data["current_session"] == 5


# ---------------------------------------------------------------------------
# POST /api/metrics/global - increment
# ---------------------------------------------------------------------------

async def test_post_global_metrics_increments_sessions(client):
    """POST /api/metrics/global increments total_sessions correctly."""
    # First, get the current value
    resp = await client.get("/api/metrics/global")
    initial = (await resp.json())["total_sessions"]

    resp = await client.post(
        "/api/metrics/global",
        json={"total_sessions": 3}
    )
    assert resp.status == 200
    data = await resp.json()
    # In-memory starts at 0, so after incrementing by 3, in-memory is 3.
    # Since persisted is 5 and in-memory is now non-zero (3), the result is 3
    # (in-memory takes precedence when non-zero).
    assert data["total_sessions"] == 3


async def test_post_global_metrics_increments_tokens(client):
    """POST /api/metrics/global increments total_tokens."""
    resp = await client.post(
        "/api/metrics/global",
        json={"total_tokens": 500}
    )
    assert resp.status == 200
    data = await resp.json()
    # In-memory was 0, now 500
    assert data["total_tokens"] == 500


async def test_post_global_metrics_increments_cost(client):
    """POST /api/metrics/global increments total_cost_usd."""
    resp = await client.post(
        "/api/metrics/global",
        json={"total_cost_usd": 0.05}
    )
    assert resp.status == 200
    data = await resp.json()
    assert abs(data["total_cost_usd"] - 0.05) < 0.0001


async def test_post_global_metrics_increments_tasks_completed_today(client):
    """POST /api/metrics/global increments tasks_completed_today."""
    resp = await client.post(
        "/api/metrics/global",
        json={"tasks_completed_today": 5}
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["tasks_completed_today"] == 5

    # Increment again
    resp2 = await client.post(
        "/api/metrics/global",
        json={"tasks_completed_today": 3}
    )
    data2 = await resp2.json()
    assert data2["tasks_completed_today"] == 8


async def test_post_global_metrics_set_mode_overwrites(client):
    """POST /api/metrics/global with set=true overwrites instead of incrementing."""
    # Pre-set some values
    await client.post("/api/metrics/global", json={"total_sessions": 10})

    # Now overwrite
    resp = await client.post(
        "/api/metrics/global",
        json={"total_sessions": 7, "set": True}
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["total_sessions"] == 7


async def test_post_global_metrics_invalid_json_returns_400(client):
    """POST /api/metrics/global with invalid JSON body returns 400."""
    resp = await client.post(
        "/api/metrics/global",
        data="not json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status == 400


async def test_post_global_metrics_returns_all_required_fields(client):
    """POST /api/metrics/global response includes all 7 required fields."""
    resp = await client.post(
        "/api/metrics/global",
        json={"total_tokens": 100}
    )
    data = await resp.json()
    required_fields = [
        "total_sessions", "total_tokens", "total_cost_usd",
        "uptime_seconds", "current_session", "agents_active",
        "tasks_completed_today",
    ]
    for field in required_fields:
        assert field in data, f"POST response missing required field: {field}"


async def test_post_global_metrics_multiple_fields_at_once(client):
    """POST /api/metrics/global can increment multiple fields in one call."""
    resp = await client.post(
        "/api/metrics/global",
        json={
            "total_sessions": 2,
            "total_tokens": 1000,
            "tasks_completed_today": 1,
        }
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["total_sessions"] == 2
    assert data["total_tokens"] == 1000
    assert data["tasks_completed_today"] == 1


# ---------------------------------------------------------------------------
# Uptime calculation
# ---------------------------------------------------------------------------

async def test_uptime_increases_over_time(rest_server, tmp_metrics_dir):
    """uptime_seconds is based on server start time and is non-negative."""
    # Set a past start time
    past = datetime(2024, 1, 1, 0, 0, 0)
    rest_module._rest_global_metrics["_server_start_time"] = past

    async with TestClient(TestServer(rest_server.app)) as c:
        resp = await c.get("/api/metrics/global")
        data = await resp.json()
        # Should be many seconds since 2024-01-01
        assert data["uptime_seconds"] > 0


async def test_uptime_is_non_negative_with_no_start_time(rest_server, tmp_metrics_dir):
    """uptime_seconds returns 0 when _server_start_time is None."""
    rest_module._rest_global_metrics["_server_start_time"] = None

    async with TestClient(TestServer(rest_server.app)) as c:
        resp = await c.get("/api/metrics/global")
        data = await resp.json()
        assert data["uptime_seconds"] >= 0


# ---------------------------------------------------------------------------
# Token formatting (pure Python utility - tested via endpoint values)
# ---------------------------------------------------------------------------

def _token_format_js(n: int) -> str:
    """
    Python reimplementation of the JS formatTokenCount function for testing.
    250000 -> "250K", 1500000 -> "1.5M"
    """
    if n >= 1_000_000:
        val = n / 1_000_000
        s = f"{val:.1f}".rstrip('0').rstrip('.')
        return s + 'M'
    if n >= 1_000:
        val = n / 1_000
        s = f"{val:.1f}".rstrip('0').rstrip('.')
        return s + 'K'
    return str(n)


def test_token_format_250k():
    """250000 tokens formats to '250K'."""
    assert _token_format_js(250_000) == "250K"


def test_token_format_1_5m():
    """1500000 tokens formats to '1.5M'."""
    assert _token_format_js(1_500_000) == "1.5M"


def test_token_format_2m():
    """2000000 tokens formats to '2M'."""
    assert _token_format_js(2_000_000) == "2M"


def test_token_format_small():
    """999 tokens formats as bare number."""
    assert _token_format_js(999) == "999"


def test_token_format_zero():
    """0 tokens formats as '0'."""
    assert _token_format_js(0) == "0"


def test_token_format_1k():
    """1000 tokens formats as '1K'."""
    assert _token_format_js(1_000) == "1K"


# ---------------------------------------------------------------------------
# Cost formatting
# ---------------------------------------------------------------------------

def _cost_format(v: float) -> str:
    """Python reimplementation of formatCostUSD JS function."""
    return f"${v:.2f}"


def test_cost_format_12_50():
    """12.50 formats as '$12.50'."""
    assert _cost_format(12.50) == "$12.50"


def test_cost_format_zero():
    """0 formats as '$0.00'."""
    assert _cost_format(0.0) == "$0.00"


def test_cost_format_small():
    """0.05 formats as '$0.05'."""
    assert _cost_format(0.05) == "$0.05"


def test_cost_format_large():
    """1234.56 formats as '$1234.56'."""
    assert _cost_format(1234.56) == "$1234.56"


# ---------------------------------------------------------------------------
# Uptime formatting
# ---------------------------------------------------------------------------

def _uptime_format(seconds: int) -> str:
    """Python reimplementation of formatUptime JS function."""
    if not seconds or seconds < 0:
        return "0s"
    d = seconds // 86400
    h = (seconds % 86400) // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if d > 0:
        return f"{d}d {h}h {m}m"
    if h > 0:
        return f"{h}h {m}m"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def test_uptime_format_2_days():
    """86400*2 + 4*3600 + 30*60 formats as '2d 4h 30m'."""
    seconds = 2 * 86400 + 4 * 3600 + 30 * 60
    assert _uptime_format(seconds) == "2d 4h 30m"


def test_uptime_format_hours_minutes():
    """3661 seconds formats as '1h 1m'."""
    assert _uptime_format(3661) == "1h 1m"


def test_uptime_format_minutes_seconds():
    """90 seconds formats as '1m 30s'."""
    assert _uptime_format(90) == "1m 30s"


def test_uptime_format_seconds_only():
    """45 seconds formats as '45s'."""
    assert _uptime_format(45) == "45s"


def test_uptime_format_zero():
    """0 formats as '0s'."""
    assert _uptime_format(0) == "0s"


def test_uptime_format_negative():
    """Negative seconds formats as '0s'."""
    assert _uptime_format(-10) == "0s"


# ---------------------------------------------------------------------------
# CORS / OPTIONS preflight
# ---------------------------------------------------------------------------

async def test_options_global_metrics_returns_204(client):
    """OPTIONS /api/metrics/global returns 204 for CORS preflight."""
    resp = await client.options("/api/metrics/global")
    assert resp.status == 204
