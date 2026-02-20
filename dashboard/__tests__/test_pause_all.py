"""Tests for AI-89: Pause All / Resume All global agent control.

Covers:
    - POST /api/agents/pause-all pauses all 13 panel agents
    - POST /api/agents/resume-all restores only paused agents to idle
    - GET /api/agents/system-status returns correct counts and flag
    - _system_paused flag is set/cleared correctly
    - Feed event is added on pause-all and resume-all
    - Resume-all does NOT affect running agents (only paused ones)
    - system-status reflects current counts after mixed-state operations
    - Idempotent: pause-all on already-paused system still returns 200
    - resume-all when no agents are paused returns resumed_count=0
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

import dashboard.rest_api_server as rest_module
from dashboard.rest_api_server import (
    RESTAPIServer,
    _agent_states,
    _rest_feed_events,
    PANEL_AGENT_NAMES,
)
from dashboard.metrics_store import ALL_AGENT_NAMES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_server(tmp_path: Path) -> RESTAPIServer:
    """Create a RESTAPIServer with a temp metrics dir."""
    return RESTAPIServer(
        project_name="test-pause-all",
        metrics_dir=tmp_path,
        port=18299,
        host="127.0.0.1",
    )


def _reset_all_state():
    """Reset all agent states, feed events, and system_paused flag."""
    for name in ALL_AGENT_NAMES:
        _agent_states[name] = "idle"
    _rest_feed_events.clear()
    rest_module._system_paused = False


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
# Tests: POST /api/agents/pause-all
# ---------------------------------------------------------------------------

class TestPauseAllEndpoint:
    """POST /api/agents/pause-all"""

    @pytest.mark.asyncio
    async def test_pause_all_returns_200(self, app):
        """pause-all should return HTTP 200."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()
            resp = await client.post("/api/agents/pause-all")
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_pause_all_pauses_13_agents(self, app):
        """pause-all should pause all 13 panel agents (ALL_AGENT_NAMES)."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()
            resp = await client.post("/api/agents/pause-all")
            assert resp.status == 200
            data = await resp.json()
            # All agents in ALL_AGENT_NAMES should now be paused
            for name in ALL_AGENT_NAMES:
                assert _agent_states.get(name) == "paused", (
                    f"Expected {name} to be paused, got {_agent_states.get(name)!r}"
                )

    @pytest.mark.asyncio
    async def test_pause_all_response_shape(self, app):
        """pause-all response should have paused_count, message, status, timestamp."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()
            resp = await client.post("/api/agents/pause-all")
            data = await resp.json()
            assert "paused_count" in data
            assert "message" in data
            assert "status" in data
            assert "timestamp" in data
            assert data["paused_count"] == len(ALL_AGENT_NAMES)

    @pytest.mark.asyncio
    async def test_pause_all_sets_system_paused_flag(self, app):
        """pause-all should set _system_paused = True."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()
            assert rest_module._system_paused is False
            await client.post("/api/agents/pause-all")
            assert rest_module._system_paused is True

    @pytest.mark.asyncio
    async def test_pause_all_adds_feed_event(self, app):
        """pause-all should add exactly one orchestrator feed event."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()
            before_count = len(_rest_feed_events)
            await client.post("/api/agents/pause-all")
            assert len(_rest_feed_events) == before_count + 1
            event = _rest_feed_events[-1]
            assert event["agent"] == "orchestrator"
            assert event["status"] == "in_progress"
            assert "paused" in event["description"].lower()

    @pytest.mark.asyncio
    async def test_pause_all_idempotent(self, app):
        """pause-all on an already-paused system should still return 200."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()
            resp1 = await client.post("/api/agents/pause-all")
            assert resp1.status == 200
            resp2 = await client.post("/api/agents/pause-all")
            assert resp2.status == 200
            data = await resp2.json()
            assert data["paused_count"] == len(ALL_AGENT_NAMES)
            # Flag still True
            assert rest_module._system_paused is True


# ---------------------------------------------------------------------------
# Tests: POST /api/agents/resume-all
# ---------------------------------------------------------------------------

class TestResumeAllEndpoint:
    """POST /api/agents/resume-all"""

    @pytest.mark.asyncio
    async def test_resume_all_returns_200(self, app):
        """resume-all should return HTTP 200."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()
            resp = await client.post("/api/agents/resume-all")
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_resume_all_restores_paused_to_idle(self, app):
        """resume-all should set paused agents back to idle."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()
            # Pause all first
            await client.post("/api/agents/pause-all")
            for name in ALL_AGENT_NAMES:
                assert _agent_states.get(name) == "paused"

            # Now resume all
            resp = await client.post("/api/agents/resume-all")
            assert resp.status == 200
            for name in ALL_AGENT_NAMES:
                assert _agent_states.get(name) == "idle", (
                    f"Expected {name} to be idle, got {_agent_states.get(name)!r}"
                )

    @pytest.mark.asyncio
    async def test_resume_all_response_shape(self, app):
        """resume-all response should have resumed_count, message, status, timestamp."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()
            await client.post("/api/agents/pause-all")
            resp = await client.post("/api/agents/resume-all")
            data = await resp.json()
            assert "resumed_count" in data
            assert "message" in data
            assert "status" in data
            assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_resume_all_clears_system_paused_flag(self, app):
        """resume-all should clear _system_paused to False."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()
            await client.post("/api/agents/pause-all")
            assert rest_module._system_paused is True
            await client.post("/api/agents/resume-all")
            assert rest_module._system_paused is False

    @pytest.mark.asyncio
    async def test_resume_all_adds_feed_event(self, app):
        """resume-all should add one orchestrator feed event with status=success."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()
            await client.post("/api/agents/pause-all")
            _rest_feed_events.clear()
            before_count = len(_rest_feed_events)
            await client.post("/api/agents/resume-all")
            assert len(_rest_feed_events) == before_count + 1
            event = _rest_feed_events[-1]
            assert event["agent"] == "orchestrator"
            assert event["status"] == "success"
            assert "resumed" in event["description"].lower()

    @pytest.mark.asyncio
    async def test_resume_all_only_affects_paused_agents(self, app):
        """resume-all should NOT change running agents to idle."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()
            # Set all to paused first
            for name in ALL_AGENT_NAMES:
                _agent_states[name] = "paused"
            rest_module._system_paused = True

            # Mark one agent as running (simulating an in-flight task)
            running_agent = ALL_AGENT_NAMES[2]  # "coding"
            _agent_states[running_agent] = "running"

            resp = await client.post("/api/agents/resume-all")
            assert resp.status == 200
            data = await resp.json()

            # running agent should still be running
            assert _agent_states.get(running_agent) == "running", (
                f"Running agent should not be touched by resume-all"
            )

            # All other paused agents should now be idle
            for name in ALL_AGENT_NAMES:
                if name != running_agent:
                    assert _agent_states.get(name) == "idle"

            # resumed_count should be total - 1 (running agent not resumed)
            assert data["resumed_count"] == len(ALL_AGENT_NAMES) - 1

    @pytest.mark.asyncio
    async def test_resume_all_when_no_paused_agents(self, app):
        """resume-all when no agents are paused should return resumed_count=0."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()
            # All agents idle (none paused)
            resp = await client.post("/api/agents/resume-all")
            assert resp.status == 200
            data = await resp.json()
            assert data["resumed_count"] == 0


# ---------------------------------------------------------------------------
# Tests: GET /api/agents/system-status
# ---------------------------------------------------------------------------

class TestSystemStatusEndpoint:
    """GET /api/agents/system-status"""

    @pytest.mark.asyncio
    async def test_system_status_returns_200(self, app):
        """system-status should return HTTP 200."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()
            resp = await client.get("/api/agents/system-status")
            assert resp.status == 200

    @pytest.mark.asyncio
    async def test_system_status_response_shape(self, app):
        """system-status response should have system_paused, paused_agent_count, running_count, timestamp."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()
            resp = await client.get("/api/agents/system-status")
            data = await resp.json()
            assert "system_paused" in data
            assert "paused_agent_count" in data
            assert "running_count" in data
            assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_system_status_initially_not_paused(self, app):
        """system_paused should be False on fresh state."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()
            resp = await client.get("/api/agents/system-status")
            data = await resp.json()
            assert data["system_paused"] is False
            assert data["paused_agent_count"] == 0

    @pytest.mark.asyncio
    async def test_system_status_after_pause_all(self, app):
        """system_paused should be True and paused_agent_count correct after pause-all."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()
            await client.post("/api/agents/pause-all")
            resp = await client.get("/api/agents/system-status")
            data = await resp.json()
            assert data["system_paused"] is True
            assert data["paused_agent_count"] == len(ALL_AGENT_NAMES)

    @pytest.mark.asyncio
    async def test_system_status_after_resume_all(self, app):
        """system_paused should be False and paused_agent_count=0 after resume-all."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()
            await client.post("/api/agents/pause-all")
            await client.post("/api/agents/resume-all")
            resp = await client.get("/api/agents/system-status")
            data = await resp.json()
            assert data["system_paused"] is False
            assert data["paused_agent_count"] == 0

    @pytest.mark.asyncio
    async def test_system_status_running_count(self, app):
        """running_count should reflect agents with status='running'."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()
            # Mark 2 agents as running
            _agent_states[ALL_AGENT_NAMES[0]] = "running"
            _agent_states[ALL_AGENT_NAMES[1]] = "running"
            resp = await client.get("/api/agents/system-status")
            data = await resp.json()
            assert data["running_count"] == 2


# ---------------------------------------------------------------------------
# Tests: Full cycle integration
# ---------------------------------------------------------------------------

class TestPauseResumeAllCycle:
    """Integration: pause-all then resume-all cycle."""

    @pytest.mark.asyncio
    async def test_full_pause_resume_cycle(self, app):
        """Pause all -> resume all -> all agents idle, flag cleared."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()

            # Pause all
            r1 = await client.post("/api/agents/pause-all")
            assert r1.status == 200
            assert rest_module._system_paused is True

            # Resume all
            r2 = await client.post("/api/agents/resume-all")
            assert r2.status == 200
            assert rest_module._system_paused is False

            # All agents idle
            for name in ALL_AGENT_NAMES:
                assert _agent_states.get(name) == "idle"

    @pytest.mark.asyncio
    async def test_cycle_generates_two_feed_events(self, app):
        """pause-all + resume-all cycle should add 2 feed events total."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()
            await client.post("/api/agents/pause-all")
            await client.post("/api/agents/resume-all")
            assert len(_rest_feed_events) == 2
            statuses = [e["status"] for e in _rest_feed_events]
            assert "in_progress" in statuses
            assert "success" in statuses

    @pytest.mark.asyncio
    async def test_system_status_consistent_across_cycle(self, app):
        """system-status endpoint stays consistent through pause-all / resume-all."""
        async with TestClient(TestServer(app)) as client:
            _reset_all_state()

            # Before: not paused
            s0 = await (await client.get("/api/agents/system-status")).json()
            assert s0["system_paused"] is False

            # After pause-all
            await client.post("/api/agents/pause-all")
            s1 = await (await client.get("/api/agents/system-status")).json()
            assert s1["system_paused"] is True
            assert s1["paused_agent_count"] == len(ALL_AGENT_NAMES)

            # After resume-all
            await client.post("/api/agents/resume-all")
            s2 = await (await client.get("/api/agents/system-status")).json()
            assert s2["system_paused"] is False
            assert s2["paused_agent_count"] == 0
