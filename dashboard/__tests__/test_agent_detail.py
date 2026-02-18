"""Tests for AI-81: REQ-MONITOR-003 Agent Detail View.

Covers:
- GET /api/agents/{name}/profile returns all required fields
- Profile for all 13 panel agents returns 200
- POST /api/agents/{name}/events adds event to history
- GET profile includes recent_events (last 20 max)
- Unknown agent returns 404
- Event validation (missing title returns 400)
- Events rolling window capped at 20
- Multiple events accumulate correctly
- Profile fields: lifetime_stats, gamification, contribution_counters, strengths, weaknesses
- DEFAULT_MODELS mapping present for all 13 agents
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from datetime import datetime

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

# Ensure the project root is importable.
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import dashboard.rest_api_server as rest_module
from dashboard.rest_api_server import RESTAPIServer, PANEL_AGENT_NAMES, _REST_DEFAULT_MODELS

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
                "total_invocations": 10,
                "successful_invocations": 8,
                "failed_invocations": 2,
                "total_tokens": 2000,
                "total_cost_usd": 0.10,
                "total_duration_seconds": 120.0,
                "commits_made": 5,
                "prs_created": 3,
                "prs_merged": 2,
                "files_created": 4,
                "files_modified": 8,
                "lines_added": 200,
                "lines_removed": 50,
                "tests_written": 3,
                "issues_created": 1,
                "issues_completed": 2,
                "messages_sent": 0,
                "reviews_completed": 0,
                "success_rate": 0.8,
                "avg_duration_seconds": 12.0,
                "avg_tokens_per_call": 200.0,
                "cost_per_success_usd": 0.0125,
                "xp": 150,
                "level": 3,
                "current_streak": 4,
                "best_streak": 7,
                "achievements": ["first_blood", "streak_10"],
                "strengths": ["high_success_rate", "fast_execution"],
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
    rest_module._rest_agent_recent_events.clear()
    rest_module._agent_status_details.clear()

    server = RESTAPIServer(
        project_name="test-project",
        metrics_dir=tmp_metrics_dir,
        port=18600,
        host="127.0.0.1",
    )
    return server


@pytest.fixture()
async def client(rest_server):
    """aiohttp TestClient wrapping the REST server."""
    async with TestClient(TestServer(rest_server.app)) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /api/agents/{name}/profile - Required fields
# ---------------------------------------------------------------------------

async def test_get_agent_profile_returns_200_for_known_agent(client):
    """GET /api/agents/coding/profile returns 200."""
    resp = await client.get("/api/agents/coding/profile")
    assert resp.status == 200


async def test_get_agent_profile_has_profile_key(client):
    """GET /api/agents/coding/profile returns JSON with 'profile' key."""
    resp = await client.get("/api/agents/coding/profile")
    assert resp.status == 200
    data = await resp.json()
    assert "profile" in data


async def test_get_agent_profile_has_all_required_top_level_fields(client):
    """Profile contains name, model, status, lifetime_stats, gamification,
    contribution_counters, strengths, weaknesses, recent_events."""
    resp = await client.get("/api/agents/coding/profile")
    data = await resp.json()
    profile = data["profile"]

    required_fields = [
        "name", "model", "status",
        "lifetime_stats", "gamification",
        "contribution_counters", "strengths", "weaknesses",
        "recent_events",
    ]
    for field in required_fields:
        assert field in profile, f"Missing field: {field}"


async def test_get_agent_profile_lifetime_stats_fields(client):
    """lifetime_stats contains tasks_completed, tasks_failed, success_rate, total_tokens, total_cost, avg_duration."""
    resp = await client.get("/api/agents/coding/profile")
    data = await resp.json()
    stats = data["profile"]["lifetime_stats"]

    required_stats = [
        "tasks_completed", "tasks_failed", "success_rate",
        "total_tokens", "total_cost", "avg_duration",
    ]
    for field in required_stats:
        assert field in stats, f"Missing lifetime_stats field: {field}"


async def test_get_agent_profile_gamification_fields(client):
    """gamification contains xp, level, streak, achievements."""
    resp = await client.get("/api/agents/coding/profile")
    data = await resp.json()
    gam = data["profile"]["gamification"]

    required_gam = ["xp", "level", "streak", "achievements"]
    for field in required_gam:
        assert field in gam, f"Missing gamification field: {field}"


async def test_get_agent_profile_contribution_fields(client):
    """contribution_counters contains commits, prs_created, prs_merged, linear_issues_closed."""
    resp = await client.get("/api/agents/coding/profile")
    data = await resp.json()
    contribs = data["profile"]["contribution_counters"]

    required_contribs = ["commits", "prs_created", "prs_merged", "linear_issues_closed"]
    for field in required_contribs:
        assert field in contribs, f"Missing contribution field: {field}"


async def test_get_agent_profile_coding_data_from_metrics(client):
    """Profile for 'coding' agent correctly loads data from metrics file."""
    resp = await client.get("/api/agents/coding/profile")
    data = await resp.json()
    profile = data["profile"]

    assert profile["name"] == "coding"
    assert profile["model"] == "sonnet"  # from _REST_DEFAULT_MODELS
    stats = profile["lifetime_stats"]
    assert stats["tasks_completed"] == 8   # successful_invocations
    assert stats["tasks_failed"] == 2      # failed_invocations
    assert stats["success_rate"] == 0.8
    assert stats["total_tokens"] == 2000

    gam = profile["gamification"]
    assert gam["xp"] == 150
    assert gam["level"] == 3
    assert gam["streak"] == 4
    assert "first_blood" in gam["achievements"]

    assert "high_success_rate" in profile["strengths"]

    contribs = profile["contribution_counters"]
    assert contribs["commits"] == 5
    assert contribs["prs_created"] == 3
    assert contribs["prs_merged"] == 2
    assert contribs["linear_issues_closed"] == 2


async def test_get_agent_profile_model_from_default_models(client):
    """Profile model field comes from _REST_DEFAULT_MODELS mapping."""
    for agent_name, expected_model in _REST_DEFAULT_MODELS.items():
        resp = await client.get(f"/api/agents/{agent_name}/profile")
        assert resp.status == 200, f"Expected 200 for agent {agent_name}"
        data = await resp.json()
        assert data["profile"]["model"] == expected_model, \
            f"Agent {agent_name}: expected model {expected_model}, got {data['profile']['model']}"


async def test_get_agent_profile_has_timestamp(client):
    """Profile response includes a timestamp field."""
    resp = await client.get("/api/agents/coding/profile")
    data = await resp.json()
    assert "timestamp" in data


# ---------------------------------------------------------------------------
# GET /api/agents/{name}/profile - All 13 panel agents return 200
# ---------------------------------------------------------------------------

async def test_profile_for_all_13_panel_agents(client):
    """GET /api/agents/{name}/profile returns 200 for all 13 canonical agents."""
    expected_agents = [
        "linear", "coding", "github", "slack", "pr_reviewer",
        "ops", "coding_fast", "pr_reviewer_fast", "chatgpt",
        "gemini", "groq", "kimi", "windsurf",
    ]
    assert len(expected_agents) == 13

    for agent_name in expected_agents:
        resp = await client.get(f"/api/agents/{agent_name}/profile")
        assert resp.status == 200, f"Expected 200 for agent '{agent_name}', got {resp.status}"
        data = await resp.json()
        assert "profile" in data
        assert data["profile"]["name"] == agent_name


# ---------------------------------------------------------------------------
# GET /api/agents/{name}/profile - Unknown agent returns 404
# ---------------------------------------------------------------------------

async def test_get_unknown_agent_profile_returns_404(client):
    """GET /api/agents/unknown_agent/profile returns 404."""
    resp = await client.get("/api/agents/unknown_agent/profile")
    assert resp.status == 404


async def test_get_unknown_agent_profile_returns_error_body(client):
    """GET /api/agents/not_real/profile 404 response includes 'error' field."""
    resp = await client.get("/api/agents/not_real/profile")
    assert resp.status == 404
    data = await resp.json()
    assert "error" in data
    assert "available_agents" in data


# ---------------------------------------------------------------------------
# POST /api/agents/{name}/events - Add event to history
# ---------------------------------------------------------------------------

async def test_post_agent_event_returns_201(client):
    """POST /api/agents/coding/events with valid body returns 201."""
    resp = await client.post("/api/agents/coding/events", json={
        "type": "task_completed",
        "title": "Implemented feature X",
        "status": "success",
        "ticket_key": "AI-123",
    })
    assert resp.status == 201


async def test_post_agent_event_returns_event_data(client):
    """POST event response contains event object with id, timestamp, type, title, status."""
    resp = await client.post("/api/agents/coding/events", json={
        "type": "task_started",
        "title": "Starting task",
        "status": "in_progress",
        "ticket_key": "AI-200",
    })
    data = await resp.json()
    assert "event" in data
    event = data["event"]
    assert "id" in event
    assert "timestamp" in event
    assert event["type"] == "task_started"
    assert event["title"] == "Starting task"
    assert event["status"] == "in_progress"
    assert event["ticket_key"] == "AI-200"


async def test_post_agent_event_unknown_agent_returns_404(client):
    """POST /api/agents/not_real/events returns 404."""
    resp = await client.post("/api/agents/not_real/events", json={
        "type": "task_completed",
        "title": "Test",
        "status": "success",
    })
    assert resp.status == 404


async def test_post_agent_event_missing_title_returns_400(client):
    """POST /api/agents/coding/events with missing title returns 400."""
    resp = await client.post("/api/agents/coding/events", json={
        "type": "task_completed",
        "status": "success",
    })
    assert resp.status == 400
    data = await resp.json()
    assert "error" in data


async def test_post_agent_event_invalid_json_returns_400(client):
    """POST /api/agents/coding/events with invalid JSON returns 400."""
    resp = await client.post(
        "/api/agents/coding/events",
        data="not json",
        headers={"Content-Type": "application/json"}
    )
    assert resp.status == 400


async def test_post_agent_event_with_duration(client):
    """POST event with duration field stores it correctly."""
    resp = await client.post("/api/agents/linear/events", json={
        "type": "task_completed",
        "title": "Closed issue AI-50",
        "status": "success",
        "ticket_key": "AI-50",
        "duration": 45.5,
    })
    assert resp.status == 201
    data = await resp.json()
    assert data["event"]["duration"] == 45.5


# ---------------------------------------------------------------------------
# GET profile includes recent_events (last 20 max)
# ---------------------------------------------------------------------------

async def test_profile_starts_with_empty_recent_events(client):
    """Profile recent_events starts empty for a fresh agent."""
    resp = await client.get("/api/agents/github/profile")
    data = await resp.json()
    assert data["profile"]["recent_events"] == []


async def test_profile_includes_posted_recent_events(client):
    """After posting an event, profile recent_events contains it."""
    # Post an event
    await client.post("/api/agents/coding/events", json={
        "type": "task_completed",
        "title": "Test event",
        "status": "success",
    })

    # Fetch profile
    resp = await client.get("/api/agents/coding/profile")
    data = await resp.json()
    events = data["profile"]["recent_events"]
    assert len(events) == 1
    assert events[0]["title"] == "Test event"


async def test_profile_recent_events_capped_at_20(client):
    """Posting 25 events results in only the last 20 in the profile."""
    for i in range(25):
        await client.post("/api/agents/slack/events", json={
            "type": "task_completed",
            "title": f"Event {i+1}",
            "status": "success",
        })

    resp = await client.get("/api/agents/slack/profile")
    data = await resp.json()
    events = data["profile"]["recent_events"]
    assert len(events) == 20

    # Last 20 events (indices 5-24 from original posting)
    # The most recent event should be "Event 25"
    titles = [e["title"] for e in events]
    assert "Event 25" in titles
    assert "Event 1" not in titles  # First 5 should be dropped


async def test_profile_recent_events_multiple_agents_independent(client):
    """Events for different agents don't cross-contaminate."""
    await client.post("/api/agents/coding/events", json={
        "type": "task_completed", "title": "Coding event", "status": "success"
    })
    await client.post("/api/agents/github/events", json={
        "type": "task_started", "title": "GitHub event", "status": "in_progress"
    })

    coding_resp = await client.get("/api/agents/coding/profile")
    github_resp = await client.get("/api/agents/github/profile")

    coding_events = (await coding_resp.json())["profile"]["recent_events"]
    github_events = (await github_resp.json())["profile"]["recent_events"]

    assert len(coding_events) == 1
    assert coding_events[0]["title"] == "Coding event"

    assert len(github_events) == 1
    assert github_events[0]["title"] == "GitHub event"


async def test_post_event_total_events_in_response(client):
    """POST response includes total_events count."""
    # Post 3 events
    for i in range(3):
        await client.post("/api/agents/ops/events", json={
            "type": "task_completed",
            "title": f"Ops event {i+1}",
            "status": "success",
        })

    resp = await client.post("/api/agents/ops/events", json={
        "type": "task_completed",
        "title": "Final event",
        "status": "success",
    })
    data = await resp.json()
    assert data["total_events"] == 4
    assert data["agent_name"] == "ops"


# ---------------------------------------------------------------------------
# DEFAULT_MODELS validation
# ---------------------------------------------------------------------------

async def test_default_models_has_all_13_agents(client):
    """_REST_DEFAULT_MODELS covers all 13 panel agents."""
    expected_agents = [
        "linear", "coding", "github", "slack", "pr_reviewer",
        "ops", "coding_fast", "pr_reviewer_fast", "chatgpt",
        "gemini", "groq", "kimi", "windsurf",
    ]
    for agent in expected_agents:
        assert agent in _REST_DEFAULT_MODELS, f"Missing agent in DEFAULT_MODELS: {agent}"


async def test_coding_agent_uses_sonnet_model(client):
    """Coding and pr_reviewer agents use 'sonnet' model."""
    assert _REST_DEFAULT_MODELS["coding"] == "sonnet"
    assert _REST_DEFAULT_MODELS["pr_reviewer"] == "sonnet"


async def test_other_agents_use_haiku_model(client):
    """Non-coding/reviewer agents use 'haiku' model."""
    haiku_agents = [
        "linear", "github", "slack", "ops", "coding_fast",
        "pr_reviewer_fast", "chatgpt", "gemini", "groq", "kimi", "windsurf"
    ]
    for agent in haiku_agents:
        assert _REST_DEFAULT_MODELS[agent] == "haiku", \
            f"Expected haiku for {agent}, got {_REST_DEFAULT_MODELS[agent]}"


# ---------------------------------------------------------------------------
# Panel agent names validation
# ---------------------------------------------------------------------------

async def test_panel_agent_names_has_13_entries():
    """PANEL_AGENT_NAMES has exactly 13 agents."""
    assert len(PANEL_AGENT_NAMES) == 13


async def test_panel_agent_names_all_present():
    """All expected agent names are in PANEL_AGENT_NAMES."""
    expected = [
        "linear", "coding", "github", "slack", "pr_reviewer",
        "ops", "coding_fast", "pr_reviewer_fast", "chatgpt",
        "gemini", "groq", "kimi", "windsurf",
    ]
    for name in expected:
        assert name in PANEL_AGENT_NAMES


# ---------------------------------------------------------------------------
# Status integration
# ---------------------------------------------------------------------------

async def test_profile_shows_agent_status(client):
    """Profile status field reflects the agent's current status."""
    # Update agent status to running
    await client.post("/api/agents/coding/status", json={
        "status": "running",
        "current_ticket": "AI-99",
    })

    resp = await client.get("/api/agents/coding/profile")
    data = await resp.json()
    assert data["profile"]["status"] == "running"


async def test_profile_shows_idle_by_default(client):
    """Profile status defaults to 'idle' for agents that haven't been updated."""
    resp = await client.get("/api/agents/gemini/profile")
    data = await resp.json()
    assert data["profile"]["status"] == "idle"


# ---------------------------------------------------------------------------
# Event type variations
# ---------------------------------------------------------------------------

async def test_post_event_various_types(client):
    """POST events with all supported event types."""
    event_types = [
        "task_started", "task_completed", "error_occurred",
        "file_modified", "test_run", "decision_made",
        "command_executed", "milestone_reached",
    ]
    for et in event_types:
        resp = await client.post("/api/agents/groq/events", json={
            "type": et,
            "title": f"Event of type {et}",
            "status": "success",
        })
        assert resp.status == 201, f"Failed for event type: {et}"


async def test_post_event_without_ticket_key(client):
    """POST event without ticket_key is accepted."""
    resp = await client.post("/api/agents/kimi/events", json={
        "type": "task_completed",
        "title": "Event without ticket",
        "status": "success",
    })
    assert resp.status == 201
    data = await resp.json()
    assert data["event"]["ticket_key"] == ""


async def test_post_event_without_optional_duration(client):
    """POST event without duration is accepted, duration is None."""
    resp = await client.post("/api/agents/windsurf/events", json={
        "type": "task_completed",
        "title": "No duration event",
        "status": "success",
    })
    assert resp.status == 201
    data = await resp.json()
    assert data["event"]["duration"] is None


# ---------------------------------------------------------------------------
# Profile for agents with no metrics data
# ---------------------------------------------------------------------------

async def test_profile_for_agent_without_metrics_has_zero_stats(client):
    """Profile for agent with no metrics data has zeros for stats."""
    resp = await client.get("/api/agents/linear/profile")
    assert resp.status == 200
    data = await resp.json()
    profile = data["profile"]

    # linear has no data in test metrics
    stats = profile["lifetime_stats"]
    assert stats["tasks_completed"] == 0
    assert stats["tasks_failed"] == 0
    assert stats["total_tokens"] == 0
    assert stats["success_rate"] == 0.0

    gam = profile["gamification"]
    assert gam["xp"] == 0
    assert gam["level"] == 1
    assert gam["streak"] == 0
    assert gam["achievements"] == []


async def test_profile_name_field_matches_agent(client):
    """Profile 'name' field matches the requested agent name."""
    for agent_name in ["linear", "coding", "github", "slack"]:
        resp = await client.get(f"/api/agents/{agent_name}/profile")
        data = await resp.json()
        assert data["profile"]["name"] == agent_name
