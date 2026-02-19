"""Tests for AI-86: REQ-FEED-001 Live Activity Feed - Agent Events Timeline.

Covers:
- GET /api/feed returns list (empty initially)
- POST /api/feed adds event with all required fields
- Auto-generated id and timestamp
- Event validation (agent required, description required, status validation)
- Feed capped at 50 events (oldest dropped when 51st added)
- Unknown agent returns 400 on invalid status but warns (doesn't block) on unknown name
- WebSocket broadcast on new event (feed_update message)
- GET /api/feed returns events newest-first
"""

import json
import sys
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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
        "project_name": "test-feed",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T12:00:00Z",
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


def _reset_rest_module():
    """Reset module-level state in rest_api_server before each test."""
    rest_module._agent_states.clear()
    rest_module._requirements_cache.clear()
    rest_module._decisions_log.clear()
    rest_module._ws_clients.clear()
    rest_module._agent_status_details.clear()
    rest_module._rest_agent_recent_events.clear()
    rest_module._rest_agent_xp_store.clear()
    rest_module._rest_feed_events.clear()
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
        project_name="test-feed",
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
# GET /api/feed
# ---------------------------------------------------------------------------

async def test_get_feed_returns_200(client):
    """GET /api/feed returns HTTP 200."""
    resp = await client.get("/api/feed")
    assert resp.status == 200


async def test_get_feed_returns_list_initially_empty(client):
    """GET /api/feed returns an empty list when no events have been added."""
    resp = await client.get("/api/feed")
    data = await resp.json()
    assert isinstance(data, list)
    assert len(data) == 0


async def test_get_feed_content_type(client):
    """GET /api/feed returns JSON content type."""
    resp = await client.get("/api/feed")
    assert "application/json" in resp.headers.get("Content-Type", "")


# ---------------------------------------------------------------------------
# POST /api/feed
# ---------------------------------------------------------------------------

async def test_post_feed_returns_201(client):
    """POST /api/feed returns HTTP 201."""
    resp = await client.post("/api/feed", json={
        "agent": "coding",
        "description": "Implemented leaderboard feature",
        "status": "success",
        "ticket_key": "AI-84",
        "duration_s": 45.2,
    })
    assert resp.status == 201


async def test_post_feed_returns_event_with_auto_id(client):
    """POST /api/feed auto-generates an 'id' UUID for the event."""
    resp = await client.post("/api/feed", json={
        "agent": "coding",
        "description": "Test event",
    })
    assert resp.status == 201
    data = await resp.json()
    assert "event" in data
    event = data["event"]
    assert "id" in event
    assert len(event["id"]) == 36  # UUID format


async def test_post_feed_returns_event_with_timestamp(client):
    """POST /api/feed auto-generates a 'timestamp' ISO string."""
    resp = await client.post("/api/feed", json={
        "agent": "ops",
        "description": "Deployed service",
    })
    assert resp.status == 201
    data = await resp.json()
    event = data["event"]
    assert "timestamp" in event
    assert event["timestamp"].endswith("Z")


async def test_post_feed_all_required_fields_present(client):
    """POST /api/feed: returned event has all required fields."""
    resp = await client.post("/api/feed", json={
        "agent": "github",
        "description": "Created pull request",
        "status": "success",
        "ticket_key": "AI-86",
        "duration_s": 12.5,
    })
    assert resp.status == 201
    event = (await resp.json())["event"]
    required_fields = ["id", "timestamp", "agent", "status", "ticket_key", "duration_s", "description"]
    for field in required_fields:
        assert field in event, f"Missing field: {field}"


async def test_post_feed_event_stored_and_retrievable(client):
    """POST /api/feed then GET /api/feed returns the event."""
    await client.post("/api/feed", json={
        "agent": "linear",
        "description": "Closed Linear ticket",
        "status": "success",
        "ticket_key": "AI-77",
    })
    resp = await client.get("/api/feed")
    data = await resp.json()
    assert len(data) == 1
    assert data[0]["agent"] == "linear"
    assert data[0]["ticket_key"] == "AI-77"


async def test_post_feed_multiple_events_newest_first(client):
    """GET /api/feed returns events newest first."""
    agents = ["coding", "ops", "github"]
    for agent in agents:
        await client.post("/api/feed", json={
            "agent": agent,
            "description": f"Event from {agent}",
        })
    resp = await client.get("/api/feed")
    data = await resp.json()
    assert len(data) == 3
    # Newest first: last posted agent should be first in response
    assert data[0]["agent"] == "github"
    assert data[1]["agent"] == "ops"
    assert data[2]["agent"] == "coding"


# ---------------------------------------------------------------------------
# Field validation
# ---------------------------------------------------------------------------

async def test_post_feed_missing_agent_returns_400(client):
    """POST /api/feed without 'agent' returns 400."""
    resp = await client.post("/api/feed", json={"description": "No agent"})
    assert resp.status == 400
    data = await resp.json()
    assert "error" in data


async def test_post_feed_missing_description_returns_400(client):
    """POST /api/feed without 'description' returns 400."""
    resp = await client.post("/api/feed", json={"agent": "coding"})
    assert resp.status == 400
    data = await resp.json()
    assert "error" in data


async def test_post_feed_invalid_json_returns_400(client):
    """POST /api/feed with non-JSON body returns 400."""
    resp = await client.post(
        "/api/feed",
        data="not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status == 400


async def test_post_feed_invalid_status_returns_400(client):
    """POST /api/feed with unrecognised status returns 400."""
    resp = await client.post("/api/feed", json={
        "agent": "coding",
        "description": "Some event",
        "status": "INVALID_STATUS",
    })
    assert resp.status == 400
    data = await resp.json()
    assert "error" in data


async def test_post_feed_unknown_agent_warns_but_returns_201(client):
    """POST /api/feed with unknown agent name returns 201 (warn but don't block)."""
    resp = await client.post("/api/feed", json={
        "agent": "totally_unknown_agent",
        "description": "Some action",
        "status": "success",
    })
    # Should warn in logs but not block
    assert resp.status == 201


async def test_post_feed_status_defaults_to_success(client):
    """POST /api/feed without status defaults to 'success'."""
    resp = await client.post("/api/feed", json={
        "agent": "coding",
        "description": "Default status event",
    })
    assert resp.status == 201
    event = (await resp.json())["event"]
    assert event["status"] == "success"


async def test_post_feed_in_progress_status_accepted(client):
    """POST /api/feed with status='in_progress' returns 201."""
    resp = await client.post("/api/feed", json={
        "agent": "coding",
        "description": "Working on it",
        "status": "in_progress",
    })
    assert resp.status == 201


async def test_post_feed_error_status_accepted(client):
    """POST /api/feed with status='error' returns 201."""
    resp = await client.post("/api/feed", json={
        "agent": "ops",
        "description": "Deployment failed",
        "status": "error",
    })
    assert resp.status == 201


async def test_post_feed_optional_fields_can_be_omitted(client):
    """POST /api/feed without ticket_key and duration_s is valid."""
    resp = await client.post("/api/feed", json={
        "agent": "slack",
        "description": "Sent Slack notification",
    })
    assert resp.status == 201
    event = (await resp.json())["event"]
    assert event["ticket_key"] is None
    assert event["duration_s"] is None


# ---------------------------------------------------------------------------
# Feed cap at 50 events
# ---------------------------------------------------------------------------

async def test_post_feed_cap_at_50_events(client):
    """Feed is capped at 50 events; oldest are dropped when 51st is added."""
    # Post 51 events
    for i in range(51):
        await client.post("/api/feed", json={
            "agent": "coding",
            "description": f"Event number {i}",
        })
    resp = await client.get("/api/feed")
    data = await resp.json()
    assert len(data) == 50, f"Expected 50 events, got {len(data)}"


async def test_post_feed_cap_drops_oldest(client):
    """When 51st event is added, the first event (oldest) is dropped."""
    # Post event 0 as the oldest
    await client.post("/api/feed", json={
        "agent": "coding",
        "description": "OLDEST EVENT",
    })
    # Fill up to 50 more
    for i in range(50):
        await client.post("/api/feed", json={
            "agent": "ops",
            "description": f"Filler event {i}",
        })
    resp = await client.get("/api/feed")
    data = await resp.json()
    assert len(data) == 50
    descriptions = [e["description"] for e in data]
    assert "OLDEST EVENT" not in descriptions, "Oldest event should have been dropped"


async def test_post_feed_total_field_in_response(client):
    """POST /api/feed response includes 'total' count of current feed size."""
    for i in range(3):
        resp = await client.post("/api/feed", json={
            "agent": "coding",
            "description": f"Event {i}",
        })
    data = await resp.json()
    assert "total" in data
    assert data["total"] == 3


# ---------------------------------------------------------------------------
# WebSocket broadcast on new event
# ---------------------------------------------------------------------------

async def test_post_feed_triggers_websocket_broadcast(rest_server, tmp_metrics_dir):
    """POST /api/feed broadcasts a 'feed_update' message to all WS clients."""
    # Create a mock WS client
    mock_ws = MagicMock()
    mock_ws.send_str = AsyncMock()

    async with TestClient(TestServer(rest_server.app)) as c:
        # Inject a fake WS client
        rest_module._ws_clients.add(mock_ws)
        try:
            resp = await c.post("/api/feed", json={
                "agent": "coding",
                "description": "Triggered WS broadcast",
                "status": "success",
            })
            assert resp.status == 201

            # Verify send_str was called once
            assert mock_ws.send_str.called, "WebSocket broadcast was not called"
            call_args = mock_ws.send_str.call_args[0][0]
            message = json.loads(call_args)
            assert message["type"] == "feed_update"
            assert "event" in message
            assert message["event"]["agent"] == "coding"
        finally:
            rest_module._ws_clients.discard(mock_ws)


async def test_post_feed_websocket_broadcast_contains_event_fields(rest_server):
    """WebSocket feed_update broadcast contains all required event fields."""
    mock_ws = MagicMock()
    mock_ws.send_str = AsyncMock()

    async with TestClient(TestServer(rest_server.app)) as c:
        rest_module._ws_clients.add(mock_ws)
        try:
            await c.post("/api/feed", json={
                "agent": "github",
                "description": "Merged PR",
                "status": "success",
                "ticket_key": "AI-86",
                "duration_s": 33.1,
            })
            call_args = mock_ws.send_str.call_args[0][0]
            message = json.loads(call_args)
            event = message["event"]
            for field in ["id", "timestamp", "agent", "status", "ticket_key", "duration_s", "description"]:
                assert field in event, f"Missing field in WS event: {field}"
        finally:
            rest_module._ws_clients.discard(mock_ws)


# ---------------------------------------------------------------------------
# Description truncation
# ---------------------------------------------------------------------------

async def test_post_feed_description_truncated_to_120_chars(client):
    """POST /api/feed truncates description to 120 characters."""
    long_desc = "A" * 200
    resp = await client.post("/api/feed", json={
        "agent": "coding",
        "description": long_desc,
    })
    assert resp.status == 201
    event = (await resp.json())["event"]
    assert len(event["description"]) == 120
