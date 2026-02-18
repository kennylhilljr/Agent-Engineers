"""Tests for AI-87 + AI-88: Agent Pause / Resume control endpoints.

Covers:
    - POST /api/agents/{name}/pause -> status becomes "paused"
    - POST /api/agents/{name}/resume -> status becomes "idle"
    - pause adds a feed event (status=in_progress, description contains "paused by user")
    - resume adds a feed event (status=success, description contains "resumed by user")
    - pause on already-paused agent is idempotent
    - resume on idle agent is idempotent
    - unknown agent returns 404 for both pause and resume
    - response body has correct shape: {name, previous_status, new_status, message, timestamp}
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

# Ensure the project root is importable
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.rest_api_server import (
    RESTAPIServer,
    _agent_states,
    _rest_feed_events,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_server(tmp_path: Path) -> RESTAPIServer:
    """Create a RESTAPIServer with a temp metrics dir."""
    return RESTAPIServer(
        project_name="test-pause-resume",
        metrics_dir=tmp_path,
        port=18199,
        host="127.0.0.1",
    )


async def _reset_agent(name: str = "coding") -> None:
    """Reset a specific agent's state to idle and clear feed events."""
    _agent_states[name] = "idle"
    _rest_feed_events.clear()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


@pytest.fixture
def rest_server(tmp_dir):
    return _make_server(tmp_dir)


@pytest.fixture
def app(rest_server):
    return rest_server.app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPauseEndpoint:
    """POST /api/agents/{name}/pause"""

    @pytest.mark.asyncio
    async def test_pause_sets_status_to_paused(self, app):
        """Pausing an idle agent should set its status to 'paused'."""
        async with TestClient(TestServer(app)) as client:
            await _reset_agent("coding")
            resp = await client.post("/api/agents/coding/pause")
            assert resp.status == 200
            data = await resp.json()
            assert data["new_status"] == "paused"
            assert _agent_states["coding"] == "paused"

    @pytest.mark.asyncio
    async def test_pause_returns_correct_shape(self, app):
        """Pause response should include name, previous_status, new_status, message, timestamp."""
        async with TestClient(TestServer(app)) as client:
            await _reset_agent("linear")
            resp = await client.post("/api/agents/linear/pause")
            assert resp.status == 200
            data = await resp.json()
            assert data["name"] == "linear"
            assert "previous_status" in data
            assert data["new_status"] == "paused"
            assert "message" in data
            assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_pause_records_previous_status(self, app):
        """previous_status in response should match the state before pausing."""
        async with TestClient(TestServer(app)) as client:
            _agent_states["coding"] = "idle"
            _rest_feed_events.clear()
            resp = await client.post("/api/agents/coding/pause")
            assert resp.status == 200
            data = await resp.json()
            assert data["previous_status"] == "idle"

    @pytest.mark.asyncio
    async def test_pause_adds_feed_event(self, app):
        """Pausing an agent should append a feed event with status=in_progress."""
        async with TestClient(TestServer(app)) as client:
            await _reset_agent("coding")
            before_count = len(_rest_feed_events)
            resp = await client.post("/api/agents/coding/pause")
            assert resp.status == 200
            assert len(_rest_feed_events) == before_count + 1
            event = _rest_feed_events[-1]
            assert event["agent"] == "coding"
            assert event["status"] == "in_progress"
            assert "paused by user" in event["description"]

    @pytest.mark.asyncio
    async def test_pause_idempotent_already_paused(self, app):
        """Pausing an already-paused agent should succeed (idempotent)."""
        async with TestClient(TestServer(app)) as client:
            _agent_states["coding"] = "paused"
            _rest_feed_events.clear()
            resp = await client.post("/api/agents/coding/pause")
            assert resp.status == 200
            data = await resp.json()
            assert data["new_status"] == "paused"
            assert data["previous_status"] == "paused"

    @pytest.mark.asyncio
    async def test_pause_unknown_agent_returns_404(self, app):
        """Pausing an unknown agent should return 404."""
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/agents/nonexistent_xyz/pause")
            assert resp.status == 404
            data = await resp.json()
            assert "error" in data

    @pytest.mark.asyncio
    async def test_pause_running_agent(self, app):
        """Pausing a running agent should succeed without aborting the task."""
        async with TestClient(TestServer(app)) as client:
            _agent_states["coding"] = "running"
            _rest_feed_events.clear()
            resp = await client.post("/api/agents/coding/pause")
            assert resp.status == 200
            data = await resp.json()
            assert data["new_status"] == "paused"
            assert data["previous_status"] == "running"


class TestResumeEndpoint:
    """POST /api/agents/{name}/resume"""

    @pytest.mark.asyncio
    async def test_resume_sets_status_to_idle(self, app):
        """Resuming a paused agent should set its status to 'idle'."""
        async with TestClient(TestServer(app)) as client:
            _agent_states["coding"] = "paused"
            _rest_feed_events.clear()
            resp = await client.post("/api/agents/coding/resume")
            assert resp.status == 200
            data = await resp.json()
            assert data["new_status"] == "idle"
            assert _agent_states["coding"] == "idle"

    @pytest.mark.asyncio
    async def test_resume_returns_correct_shape(self, app):
        """Resume response should include name, previous_status, new_status, message, timestamp."""
        async with TestClient(TestServer(app)) as client:
            _agent_states["linear"] = "paused"
            _rest_feed_events.clear()
            resp = await client.post("/api/agents/linear/resume")
            assert resp.status == 200
            data = await resp.json()
            assert data["name"] == "linear"
            assert "previous_status" in data
            assert data["new_status"] == "idle"
            assert "message" in data
            assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_resume_records_previous_status(self, app):
        """previous_status in response should match the state before resuming."""
        async with TestClient(TestServer(app)) as client:
            _agent_states["coding"] = "paused"
            _rest_feed_events.clear()
            resp = await client.post("/api/agents/coding/resume")
            assert resp.status == 200
            data = await resp.json()
            assert data["previous_status"] == "paused"

    @pytest.mark.asyncio
    async def test_resume_adds_feed_event(self, app):
        """Resuming an agent should append a feed event with status=success."""
        async with TestClient(TestServer(app)) as client:
            _agent_states["coding"] = "paused"
            _rest_feed_events.clear()
            before_count = len(_rest_feed_events)
            resp = await client.post("/api/agents/coding/resume")
            assert resp.status == 200
            assert len(_rest_feed_events) == before_count + 1
            event = _rest_feed_events[-1]
            assert event["agent"] == "coding"
            assert event["status"] == "success"
            assert "resumed by user" in event["description"]

    @pytest.mark.asyncio
    async def test_resume_idempotent_already_idle(self, app):
        """Resuming an already-idle agent should succeed (idempotent)."""
        async with TestClient(TestServer(app)) as client:
            _agent_states["coding"] = "idle"
            _rest_feed_events.clear()
            resp = await client.post("/api/agents/coding/resume")
            assert resp.status == 200
            data = await resp.json()
            assert data["new_status"] == "idle"
            assert data["previous_status"] == "idle"

    @pytest.mark.asyncio
    async def test_resume_unknown_agent_returns_404(self, app):
        """Resuming an unknown agent should return 404."""
        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/agents/nonexistent_xyz/resume")
            assert resp.status == 404
            data = await resp.json()
            assert "error" in data


class TestPauseResumeRoundTrip:
    """Integration: full pause -> resume cycle."""

    @pytest.mark.asyncio
    async def test_pause_then_resume_cycle(self, app):
        """Full pause-then-resume cycle transitions states correctly."""
        async with TestClient(TestServer(app)) as client:
            _agent_states["coding"] = "idle"
            _rest_feed_events.clear()

            # Pause
            resp1 = await client.post("/api/agents/coding/pause")
            assert resp1.status == 200
            d1 = await resp1.json()
            assert d1["new_status"] == "paused"
            assert _agent_states["coding"] == "paused"

            # Resume
            resp2 = await client.post("/api/agents/coding/resume")
            assert resp2.status == 200
            d2 = await resp2.json()
            assert d2["new_status"] == "idle"
            assert _agent_states["coding"] == "idle"

    @pytest.mark.asyncio
    async def test_pause_resume_generates_two_feed_events(self, app):
        """A pause+resume cycle should produce exactly 2 feed events."""
        async with TestClient(TestServer(app)) as client:
            _agent_states["coding"] = "idle"
            _rest_feed_events.clear()

            await client.post("/api/agents/coding/pause")
            await client.post("/api/agents/coding/resume")

            assert len(_rest_feed_events) == 2
            statuses = [e["status"] for e in _rest_feed_events]
            assert "in_progress" in statuses
            assert "success" in statuses

    @pytest.mark.asyncio
    async def test_multiple_agents_independent(self, app):
        """Pausing one agent should not affect another agent's status."""
        async with TestClient(TestServer(app)) as client:
            _agent_states["coding"] = "idle"
            _agent_states["linear"] = "idle"
            _rest_feed_events.clear()

            await client.post("/api/agents/coding/pause")
            assert _agent_states["coding"] == "paused"
            assert _agent_states["linear"] == "idle"
