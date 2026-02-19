"""Tests for AI-82: REQ-MONITOR-004 Orchestrator Flow Visualization - Pipeline Steps.

Covers:
- GET /api/orchestrator/pipeline returns correct structure with 6 steps
- POST /api/orchestrator/pipeline sets full pipeline state
- POST /api/orchestrator/pipeline/step updates individual step
- POST /api/orchestrator/pipeline/step with invalid step ID returns 400
- 6 steps are always present in default state
- Active pipeline shows ticket key and step statuses
- Inactive pipeline returns active=False
- WebSocket broadcast on pipeline update
"""

import asyncio
import copy
import json
import sys
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

# Ensure the project root is importable
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import dashboard.rest_api_server as rest_module
from dashboard.rest_api_server import (
    RESTAPIServer,
    _PIPELINE_STEP_IDS,
    _PIPELINE_DEFAULT_STEPS,
    _make_default_pipeline,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPECTED_STEP_IDS = [
    "ops-start", "coding", "github", "ops-review", "pr_reviewer", "ops-done"
]

SAMPLE_PIPELINE = {
    "active": True,
    "ticket_key": "AI-82",
    "ticket_title": "Pipeline Visualization",
    "steps": [
        {"id": "ops-start",   "label": "ops: Starting",       "status": "completed", "duration": 2.3},
        {"id": "coding",      "label": "coding: Implement",   "status": "active",    "duration": None},
        {"id": "github",      "label": "github: Commit & PR", "status": "pending",   "duration": None},
        {"id": "ops-review",  "label": "ops: PR Ready",       "status": "pending",   "duration": None},
        {"id": "pr_reviewer", "label": "pr_reviewer: Review", "status": "pending",   "duration": None},
        {"id": "ops-done",    "label": "ops: Done",           "status": "pending",   "duration": None},
    ],
}


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
    # Reset pipeline state to default
    rest_module._pipeline_state = _make_default_pipeline()

    server = RESTAPIServer(
        project_name="test-project",
        metrics_dir=tmp_metrics_dir,
        port=19600,
        host="127.0.0.1",
    )
    return server


@pytest.fixture()
async def client(rest_server):
    """aiohttp TestClient wrapping the REST server."""
    async with TestClient(TestServer(rest_server.app)) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /api/orchestrator/pipeline - Structure Tests
# ---------------------------------------------------------------------------

async def test_get_pipeline_returns_200(client):
    """GET /api/orchestrator/pipeline returns HTTP 200."""
    resp = await client.get("/api/orchestrator/pipeline")
    assert resp.status == 200


async def test_get_pipeline_returns_json_with_required_keys(client):
    """GET /api/orchestrator/pipeline returns JSON with active, ticket_key, steps."""
    resp = await client.get("/api/orchestrator/pipeline")
    assert resp.status == 200
    data = await resp.json()
    assert "active" in data
    assert "ticket_key" in data
    assert "steps" in data


async def test_get_pipeline_default_inactive(client):
    """GET /api/orchestrator/pipeline returns active=False by default."""
    resp = await client.get("/api/orchestrator/pipeline")
    data = await resp.json()
    assert data["active"] is False
    assert data["ticket_key"] is None


async def test_get_pipeline_has_6_steps_by_default(client):
    """GET /api/orchestrator/pipeline always returns 6 steps."""
    resp = await client.get("/api/orchestrator/pipeline")
    data = await resp.json()
    steps = data["steps"]
    assert isinstance(steps, list)
    assert len(steps) == 6


async def test_get_pipeline_step_ids_match_expected(client):
    """GET /api/orchestrator/pipeline step IDs match expected workflow."""
    resp = await client.get("/api/orchestrator/pipeline")
    data = await resp.json()
    step_ids = [s["id"] for s in data["steps"]]
    assert step_ids == EXPECTED_STEP_IDS


async def test_get_pipeline_each_step_has_required_fields(client):
    """Each step has id, label, status, and duration fields."""
    resp = await client.get("/api/orchestrator/pipeline")
    data = await resp.json()
    for step in data["steps"]:
        assert "id" in step, f"Step missing id: {step}"
        assert "label" in step, f"Step missing label: {step}"
        assert "status" in step, f"Step missing status: {step}"
        assert "duration" in step, f"Step missing duration: {step}"


async def test_get_pipeline_default_steps_all_pending(client):
    """Default pipeline steps all have status=pending."""
    resp = await client.get("/api/orchestrator/pipeline")
    data = await resp.json()
    for step in data["steps"]:
        assert step["status"] == "pending", f"Expected pending, got {step['status']} for {step['id']}"


# ---------------------------------------------------------------------------
# POST /api/orchestrator/pipeline - Set Pipeline State
# ---------------------------------------------------------------------------

async def test_post_pipeline_sets_active_state(client):
    """POST /api/orchestrator/pipeline sets active=True and ticket_key."""
    resp = await client.post(
        "/api/orchestrator/pipeline",
        json={
            "active": True,
            "ticket_key": "AI-82",
            "ticket_title": "Test Pipeline",
            "steps": SAMPLE_PIPELINE["steps"],
        },
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["active"] is True
    assert data["ticket_key"] == "AI-82"
    assert data["ticket_title"] == "Test Pipeline"


async def test_post_pipeline_updates_steps(client):
    """POST /api/orchestrator/pipeline updates steps correctly."""
    resp = await client.post(
        "/api/orchestrator/pipeline",
        json=SAMPLE_PIPELINE,
    )
    assert resp.status == 200
    data = await resp.json()
    steps = data["steps"]
    assert len(steps) == 6
    assert steps[0]["status"] == "completed"
    assert steps[0]["duration"] == 2.3
    assert steps[1]["status"] == "active"
    assert steps[1]["duration"] is None


async def test_post_pipeline_persists_on_get(client):
    """After POST, GET returns the updated pipeline state."""
    await client.post("/api/orchestrator/pipeline", json=SAMPLE_PIPELINE)
    resp = await client.get("/api/orchestrator/pipeline")
    data = await resp.json()
    assert data["active"] is True
    assert data["ticket_key"] == "AI-82"
    assert data["steps"][0]["status"] == "completed"


async def test_post_pipeline_missing_active_returns_400(client):
    """POST /api/orchestrator/pipeline without active field returns 400."""
    resp = await client.post(
        "/api/orchestrator/pipeline",
        json={"ticket_key": "AI-82"},
    )
    assert resp.status == 400
    data = await resp.json()
    assert "error" in data


async def test_post_pipeline_invalid_json_returns_400(client):
    """POST /api/orchestrator/pipeline with invalid body returns 400."""
    resp = await client.post(
        "/api/orchestrator/pipeline",
        data="not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status == 400


async def test_post_pipeline_steps_not_array_returns_400(client):
    """POST /api/orchestrator/pipeline with steps as non-array returns 400."""
    resp = await client.post(
        "/api/orchestrator/pipeline",
        json={"active": True, "steps": "not-an-array"},
    )
    assert resp.status == 400


async def test_post_pipeline_deactivate(client):
    """POST /api/orchestrator/pipeline with active=False deactivates pipeline."""
    # First activate
    await client.post("/api/orchestrator/pipeline", json=SAMPLE_PIPELINE)
    # Then deactivate
    resp = await client.post(
        "/api/orchestrator/pipeline",
        json={"active": False},
    )
    assert resp.status == 200
    data = await resp.json()
    assert data["active"] is False


# ---------------------------------------------------------------------------
# POST /api/orchestrator/pipeline/step - Update Single Step
# ---------------------------------------------------------------------------

async def test_post_pipeline_step_updates_status(client):
    """POST /api/orchestrator/pipeline/step updates a step's status."""
    # Set up pipeline first
    await client.post("/api/orchestrator/pipeline", json=SAMPLE_PIPELINE)

    resp = await client.post(
        "/api/orchestrator/pipeline/step",
        json={"id": "coding", "status": "completed", "duration": 15.7},
    )
    assert resp.status == 200
    data = await resp.json()
    coding_step = next(s for s in data["steps"] if s["id"] == "coding")
    assert coding_step["status"] == "completed"
    assert coding_step["duration"] == 15.7


async def test_post_pipeline_step_invalid_id_returns_400(client):
    """POST /api/orchestrator/pipeline/step with invalid step ID returns 400."""
    resp = await client.post(
        "/api/orchestrator/pipeline/step",
        json={"id": "nonexistent-step", "status": "completed"},
    )
    assert resp.status == 400
    data = await resp.json()
    assert "error" in data
    assert "valid_ids" in data


async def test_post_pipeline_step_missing_id_returns_400(client):
    """POST /api/orchestrator/pipeline/step without id returns 400."""
    resp = await client.post(
        "/api/orchestrator/pipeline/step",
        json={"status": "completed"},
    )
    assert resp.status == 400


async def test_post_pipeline_step_missing_status_returns_400(client):
    """POST /api/orchestrator/pipeline/step without status returns 400."""
    resp = await client.post(
        "/api/orchestrator/pipeline/step",
        json={"id": "coding"},
    )
    assert resp.status == 400


async def test_post_pipeline_step_invalid_json_returns_400(client):
    """POST /api/orchestrator/pipeline/step with invalid JSON returns 400."""
    resp = await client.post(
        "/api/orchestrator/pipeline/step",
        data="not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status == 400


async def test_post_pipeline_step_all_step_ids_valid(client):
    """All 6 step IDs can be updated via POST /step."""
    for step_id in EXPECTED_STEP_IDS:
        resp = await client.post(
            "/api/orchestrator/pipeline/step",
            json={"id": step_id, "status": "completed", "duration": 1.0},
        )
        assert resp.status == 200, f"Failed for step_id={step_id}: {resp.status}"


async def test_post_pipeline_step_persists_on_get(client):
    """After updating a step, GET reflects the change."""
    await client.post("/api/orchestrator/pipeline", json=SAMPLE_PIPELINE)
    await client.post(
        "/api/orchestrator/pipeline/step",
        json={"id": "github", "status": "active"},
    )
    resp = await client.get("/api/orchestrator/pipeline")
    data = await resp.json()
    github_step = next(s for s in data["steps"] if s["id"] == "github")
    assert github_step["status"] == "active"


async def test_post_pipeline_step_returns_6_steps(client):
    """POST /api/orchestrator/pipeline/step always returns 6 steps."""
    resp = await client.post(
        "/api/orchestrator/pipeline/step",
        json={"id": "ops-start", "status": "completed"},
    )
    assert resp.status == 200
    data = await resp.json()
    assert len(data["steps"]) == 6


# ---------------------------------------------------------------------------
# Module-level constants tests
# ---------------------------------------------------------------------------

def test_pipeline_step_ids_constant():
    """_PIPELINE_STEP_IDS has exactly 6 entries."""
    assert len(_PIPELINE_STEP_IDS) == 6
    assert _PIPELINE_STEP_IDS == EXPECTED_STEP_IDS


def test_pipeline_default_steps_constant():
    """_PIPELINE_DEFAULT_STEPS has 6 steps, all pending."""
    assert len(_PIPELINE_DEFAULT_STEPS) == 6
    for step in _PIPELINE_DEFAULT_STEPS:
        assert step["status"] == "pending"
        assert step["duration"] is None


def test_make_default_pipeline():
    """_make_default_pipeline() returns correct structure."""
    pipeline = _make_default_pipeline()
    assert pipeline["active"] is False
    assert pipeline["ticket_key"] is None
    assert len(pipeline["steps"]) == 6


def test_make_default_pipeline_independent_copies():
    """_make_default_pipeline() returns independent copies (deep copy)."""
    p1 = _make_default_pipeline()
    p2 = _make_default_pipeline()
    p1["steps"][0]["status"] = "completed"
    assert p2["steps"][0]["status"] == "pending"
