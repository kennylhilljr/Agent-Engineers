"""Tests for AI-92 + AI-93: Pause -> Edit -> Resume Cycle and Linear Sync Queue.

Covers:
    AI-92 - Pause -> Edit -> Resume cycle:
    - GET /api/agents/{name}/active-requirement returns 404 when no requirement set
    - GET /api/agents/{name}/active-requirement returns requirement with used_on_resume flag
    - POST /api/agents/{name}/acknowledge-requirement marks requirement as acknowledged
    - POST /api/agents/{name}/resume includes updated_requirement when pending edit
    - POST /api/agents/{name}/resume has no updated_requirement when acknowledged
    - Full pause -> edit -> resume cycle integration test

    AI-93 - Linear sync queue:
    - PUT /api/requirements/{key} with sync_to_linear=true adds to sync queue
    - PUT /api/requirements/{key} with sync_to_linear=false does NOT add to queue
    - GET /api/requirements/sync-queue returns all items
    - GET /api/requirements/sync-queue?pending_only=true filters processed items
    - POST /api/requirements/process-sync marks all pending items as processed
    - POST /api/requirements/process-sync with ticket_keys only marks specified items
    - process-sync sets linear_synced=True in requirements store
"""

import json
import sys
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

# Ensure the project root is importable
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.rest_api_server import (
    RESTAPIServer,
    _agent_states,
    _agent_status_details,
    _agent_active_requirements,
    _requirements_store,
    _requirements_cache,
    _linear_sync_queue,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_server(tmp_path: Path) -> RESTAPIServer:
    """Create a RESTAPIServer with a temp metrics dir."""
    return RESTAPIServer(
        project_name="test-req-flow",
        metrics_dir=tmp_path,
        port=18299,
        host="127.0.0.1",
    )


def _reset_state():
    """Clear all in-memory state before each test."""
    _agent_states.clear()
    _agent_status_details.clear()
    _agent_active_requirements.clear()
    _requirements_store.clear()
    _requirements_cache.clear()
    _linear_sync_queue.clear()


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


@pytest.fixture(autouse=True)
def clean_state():
    """Reset all module-level state before and after each test."""
    _reset_state()
    yield
    _reset_state()


# ---------------------------------------------------------------------------
# AI-92 Tests: active-requirement endpoint
# ---------------------------------------------------------------------------

class TestGetActiveRequirement:
    """GET /api/agents/{name}/active-requirement"""

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_agent(self, app):
        """Unknown agent name returns 404."""
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/agents/nonexistent_xyz/active-requirement")
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_returns_404_when_no_active_requirement(self, app):
        """Known agent with no active requirement returns 404."""
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/agents/coding/active-requirement")
            assert resp.status == 404
            data = await resp.json()
            assert "error" in data

    @pytest.mark.asyncio
    async def test_returns_requirement_with_used_on_resume_flag(self, app):
        """Returns requirement with used_on_resume=False when not yet acknowledged."""
        # Manually set active requirement
        _agent_active_requirements["coding"] = {
            "ticket_key": "AI-999",
            "acknowledged": False,
            "updated_at": "2026-01-01T00:00:00Z",
        }
        _requirements_store["AI-999"] = {
            "ticket_key": "AI-999",
            "title": "Test ticket",
            "description": "Original desc",
            "spec_text": "",
            "edited_description": "Edited desc",
            "last_edited": "2026-01-01T00:00:00Z",
            "sync_to_linear": False,
            "linear_synced": False,
        }

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/agents/coding/active-requirement")
            assert resp.status == 200
            data = await resp.json()
            assert data["agent_name"] == "coding"
            assert data["ticket_key"] == "AI-999"
            assert data["acknowledged"] is False
            assert data["used_on_resume"] is False
            assert "requirement" in data
            assert data["requirement"]["edited_description"] == "Edited desc"

    @pytest.mark.asyncio
    async def test_returns_used_on_resume_true_when_acknowledged(self, app):
        """Returns used_on_resume=True after acknowledgement."""
        _agent_active_requirements["coding"] = {
            "ticket_key": "AI-999",
            "acknowledged": True,
            "updated_at": "2026-01-01T00:00:00Z",
        }
        _requirements_store["AI-999"] = {
            "ticket_key": "AI-999",
            "edited_description": "Edited desc",
            "last_edited": "2026-01-01T00:00:00Z",
        }

        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/agents/coding/active-requirement")
            assert resp.status == 200
            data = await resp.json()
            assert data["acknowledged"] is True
            assert data["used_on_resume"] is True


# ---------------------------------------------------------------------------
# AI-92 Tests: acknowledge-requirement endpoint
# ---------------------------------------------------------------------------

class TestAcknowledgeRequirement:
    """POST /api/agents/{name}/acknowledge-requirement"""

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_agent(self, app):
        """Unknown agent name returns 404."""
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/agents/nonexistent_xyz/acknowledge-requirement",
                headers={"Content-Type": "application/json"},
                data=json.dumps({}),
            )
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_returns_404_when_no_active_requirement_and_no_ticket_key(self, app):
        """No active requirement and no ticket_key in body returns 404."""
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/agents/coding/acknowledge-requirement",
                headers={"Content-Type": "application/json"},
                data=json.dumps({}),
            )
            assert resp.status == 404

    @pytest.mark.asyncio
    async def test_acknowledges_existing_requirement(self, app):
        """Marks an existing unacknowledged requirement as acknowledged."""
        _agent_active_requirements["coding"] = {
            "ticket_key": "AI-100",
            "acknowledged": False,
            "updated_at": "2026-01-01T00:00:00Z",
        }

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/agents/coding/acknowledge-requirement",
                headers={"Content-Type": "application/json"},
                data=json.dumps({}),
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["acknowledged"] is True
            assert data["ticket_key"] == "AI-100"
            assert data["agent_name"] == "coding"

        # Verify in-memory state was updated
        assert _agent_active_requirements["coding"]["acknowledged"] is True

    @pytest.mark.asyncio
    async def test_creates_acknowledgement_via_body_ticket_key(self, app):
        """When no active requirement, allows creating one via ticket_key in body."""
        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/agents/coding/acknowledge-requirement",
                headers={"Content-Type": "application/json"},
                data=json.dumps({"ticket_key": "AI-200"}),
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["acknowledged"] is True
            assert data["ticket_key"] == "AI-200"


# ---------------------------------------------------------------------------
# AI-92 Tests: resume with updated_requirement
# ---------------------------------------------------------------------------

class TestResumeWithUpdatedRequirement:
    """POST /api/agents/{name}/resume - includes updated_requirement when pending edit."""

    @pytest.mark.asyncio
    async def test_resume_without_active_requirement_has_no_updated_requirement(self, app):
        """Resume without any active requirement should not include updated_requirement."""
        _agent_states["coding"] = "paused"

        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/agents/coding/resume")
            assert resp.status == 200
            data = await resp.json()
            assert data["new_status"] == "idle"
            assert "updated_requirement" not in data

    @pytest.mark.asyncio
    async def test_resume_with_unacknowledged_edit_includes_updated_requirement(self, app):
        """Resume with unacknowledged edited requirement includes updated_requirement in response."""
        _agent_states["coding"] = "paused"
        _agent_active_requirements["coding"] = {
            "ticket_key": "AI-101",
            "acknowledged": False,
            "updated_at": "2026-01-01T00:00:00Z",
        }
        _requirements_store["AI-101"] = {
            "ticket_key": "AI-101",
            "title": "Test",
            "description": "Original",
            "spec_text": "",
            "edited_description": "Updated requirement text",
            "last_edited": "2026-01-01T00:00:00Z",
            "sync_to_linear": False,
            "linear_synced": False,
        }

        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/agents/coding/resume")
            assert resp.status == 200
            data = await resp.json()
            assert data["new_status"] == "idle"
            assert "updated_requirement" in data
            updated = data["updated_requirement"]
            assert updated["ticket_key"] == "AI-101"
            assert updated["edited_description"] == "Updated requirement text"

    @pytest.mark.asyncio
    async def test_resume_with_acknowledged_requirement_has_no_updated_requirement(self, app):
        """Resume when requirement is already acknowledged does NOT include updated_requirement."""
        _agent_states["coding"] = "paused"
        _agent_active_requirements["coding"] = {
            "ticket_key": "AI-102",
            "acknowledged": True,
            "updated_at": "2026-01-01T00:00:00Z",
        }
        _requirements_store["AI-102"] = {
            "ticket_key": "AI-102",
            "edited_description": "Already used requirement",
            "last_edited": "2026-01-01T00:00:00Z",
        }

        async with TestClient(TestServer(app)) as client:
            resp = await client.post("/api/agents/coding/resume")
            assert resp.status == 200
            data = await resp.json()
            assert "updated_requirement" not in data


# ---------------------------------------------------------------------------
# AI-92 Tests: Full pause -> edit -> resume integration
# ---------------------------------------------------------------------------

class TestPauseEditResumeCycle:
    """Integration test: full pause -> edit -> resume flow."""

    @pytest.mark.asyncio
    async def test_full_pause_edit_resume_cycle(self, app):
        """
        Full cycle:
        1. Pause an agent that's working on a ticket
        2. Edit the requirement
        3. Resume the agent - verify updated_requirement is in response
        4. Acknowledge the requirement
        5. Resume again - verify no updated_requirement
        """
        # Set up agent as running with a ticket
        _agent_states["coding"] = "running"
        _agent_status_details["coding"] = {
            "name": "coding",
            "status": "running",
            "current_ticket": "AI-555",
            "ticket_title": "Test Ticket",
            "started_at": "2026-01-01T00:00:00Z",
            "description": "Original requirement",
            "token_count": 0,
            "estimated_cost": 0.0,
        }

        async with TestClient(TestServer(app)) as client:
            # Step 1: Pause the agent
            resp = await client.post("/api/agents/coding/pause")
            assert resp.status == 200
            pause_data = await resp.json()
            assert pause_data["new_status"] == "paused"

            # Verify active requirement was set
            assert "coding" in _agent_active_requirements
            assert _agent_active_requirements["coding"]["ticket_key"] == "AI-555"
            assert _agent_active_requirements["coding"]["acknowledged"] is False

            # Step 2: Edit the requirement
            resp = await client.put(
                "/api/requirements/AI-555",
                headers={"Content-Type": "application/json"},
                data=json.dumps({
                    "edited_description": "Updated requirement after pause",
                    "sync_to_linear": False,
                }),
            )
            assert resp.status == 200
            edit_data = await resp.json()
            assert edit_data["status"] == "success"
            assert edit_data["queued_for_sync"] is False

            # Step 3: Resume the agent - should include updated_requirement
            resp = await client.post("/api/agents/coding/resume")
            assert resp.status == 200
            resume_data = await resp.json()
            assert resume_data["new_status"] == "idle"
            assert "updated_requirement" in resume_data
            assert resume_data["updated_requirement"]["ticket_key"] == "AI-555"
            assert resume_data["updated_requirement"]["edited_description"] == "Updated requirement after pause"

            # Step 4: Acknowledge the requirement
            resp = await client.post(
                "/api/agents/coding/acknowledge-requirement",
                headers={"Content-Type": "application/json"},
                data=json.dumps({}),
            )
            assert resp.status == 200
            ack_data = await resp.json()
            assert ack_data["acknowledged"] is True

            # Pause again to set back to paused
            _agent_states["coding"] = "paused"

            # Step 5: Resume again - should NOT include updated_requirement
            resp = await client.post("/api/agents/coding/resume")
            assert resp.status == 200
            resume_data2 = await resp.json()
            assert "updated_requirement" not in resume_data2


# ---------------------------------------------------------------------------
# AI-93 Tests: sync queue
# ---------------------------------------------------------------------------

class TestSyncQueue:
    """GET /api/requirements/sync-queue"""

    @pytest.mark.asyncio
    async def test_returns_empty_queue_initially(self, app):
        """Initially the sync queue is empty."""
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/api/requirements/sync-queue")
            assert resp.status == 200
            data = await resp.json()
            assert data["total"] == 0
            assert data["pending_count"] == 0
            assert data["queue"] == []

    @pytest.mark.asyncio
    async def test_put_with_sync_to_linear_true_adds_to_queue(self, app):
        """PUT requirement with sync_to_linear=True adds to sync queue."""
        async with TestClient(TestServer(app)) as client:
            resp = await client.put(
                "/api/requirements/AI-300",
                headers={"Content-Type": "application/json"},
                data=json.dumps({
                    "edited_description": "Synced requirement",
                    "sync_to_linear": True,
                }),
            )
            assert resp.status == 200
            put_data = await resp.json()
            assert put_data["queued_for_sync"] is True

            # Verify sync queue
            resp = await client.get("/api/requirements/sync-queue")
            assert resp.status == 200
            queue_data = await resp.json()
            assert queue_data["total"] == 1
            assert queue_data["pending_count"] == 1
            assert queue_data["queue"][0]["ticket_key"] == "AI-300"
            assert queue_data["queue"][0]["processed"] is False

    @pytest.mark.asyncio
    async def test_put_with_sync_to_linear_false_does_not_add_to_queue(self, app):
        """PUT requirement with sync_to_linear=False does NOT add to sync queue."""
        async with TestClient(TestServer(app)) as client:
            resp = await client.put(
                "/api/requirements/AI-301",
                headers={"Content-Type": "application/json"},
                data=json.dumps({
                    "edited_description": "Local-only requirement",
                    "sync_to_linear": False,
                }),
            )
            assert resp.status == 200
            put_data = await resp.json()
            assert put_data["queued_for_sync"] is False

            # Verify sync queue is empty
            resp = await client.get("/api/requirements/sync-queue")
            assert resp.status == 200
            queue_data = await resp.json()
            assert queue_data["total"] == 0
            assert queue_data["pending_count"] == 0

    @pytest.mark.asyncio
    async def test_pending_only_filter(self, app):
        """pending_only=true filters out processed items."""
        # Add two items: one pending, one will be processed
        _linear_sync_queue.append({
            "ticket_key": "AI-400",
            "edited_description": "pending item",
            "queued_at": "2026-01-01T00:00:00Z",
            "processed": False,
        })
        _linear_sync_queue.append({
            "ticket_key": "AI-401",
            "edited_description": "processed item",
            "queued_at": "2026-01-01T00:00:00Z",
            "processed": True,
        })

        async with TestClient(TestServer(app)) as client:
            # All items
            resp = await client.get("/api/requirements/sync-queue")
            assert resp.status == 200
            data = await resp.json()
            assert data["total"] == 2
            assert data["pending_count"] == 1

            # Pending only
            resp = await client.get("/api/requirements/sync-queue?pending_only=true")
            assert resp.status == 200
            data = await resp.json()
            assert len(data["queue"]) == 1
            assert data["queue"][0]["ticket_key"] == "AI-400"


# ---------------------------------------------------------------------------
# AI-93 Tests: process-sync endpoint
# ---------------------------------------------------------------------------

class TestProcessSync:
    """POST /api/requirements/process-sync"""

    @pytest.mark.asyncio
    async def test_marks_all_pending_items_as_processed(self, app):
        """Without ticket_keys, marks all pending items as processed."""
        _linear_sync_queue.append({
            "ticket_key": "AI-500",
            "edited_description": "req 500",
            "queued_at": "2026-01-01T00:00:00Z",
            "processed": False,
        })
        _linear_sync_queue.append({
            "ticket_key": "AI-501",
            "edited_description": "req 501",
            "queued_at": "2026-01-01T00:00:00Z",
            "processed": False,
        })

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/requirements/process-sync",
                headers={"Content-Type": "application/json"},
                data=json.dumps({}),
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["processed_count"] == 2
            assert set(data["items"]) == {"AI-500", "AI-501"}

        # Verify in-memory state
        assert all(item["processed"] for item in _linear_sync_queue)

    @pytest.mark.asyncio
    async def test_marks_only_specified_ticket_keys(self, app):
        """With ticket_keys, only marks specified items as processed."""
        _linear_sync_queue.append({
            "ticket_key": "AI-600",
            "edited_description": "req 600",
            "queued_at": "2026-01-01T00:00:00Z",
            "processed": False,
        })
        _linear_sync_queue.append({
            "ticket_key": "AI-601",
            "edited_description": "req 601",
            "queued_at": "2026-01-01T00:00:00Z",
            "processed": False,
        })

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/requirements/process-sync",
                headers={"Content-Type": "application/json"},
                data=json.dumps({"ticket_keys": ["AI-600"]}),
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["processed_count"] == 1
            assert data["items"] == ["AI-600"]

        # Verify only AI-600 is processed
        by_key = {item["ticket_key"]: item for item in _linear_sync_queue}
        assert by_key["AI-600"]["processed"] is True
        assert by_key["AI-601"]["processed"] is False

    @pytest.mark.asyncio
    async def test_process_sync_sets_linear_synced_in_requirements_store(self, app):
        """process-sync marks linear_synced=True in requirements store."""
        _linear_sync_queue.append({
            "ticket_key": "AI-700",
            "edited_description": "req 700",
            "queued_at": "2026-01-01T00:00:00Z",
            "processed": False,
        })
        _requirements_store["AI-700"] = {
            "ticket_key": "AI-700",
            "title": "Test",
            "description": "Original",
            "spec_text": "",
            "edited_description": "req 700",
            "last_edited": "2026-01-01T00:00:00Z",
            "sync_to_linear": True,
            "linear_synced": False,
        }

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/requirements/process-sync",
                headers={"Content-Type": "application/json"},
                data=json.dumps({}),
            )
            assert resp.status == 200

        # Verify linear_synced was updated
        assert _requirements_store["AI-700"]["linear_synced"] is True

    @pytest.mark.asyncio
    async def test_process_sync_skips_already_processed(self, app):
        """process-sync does not reprocess already processed items."""
        _linear_sync_queue.append({
            "ticket_key": "AI-800",
            "edited_description": "req 800",
            "queued_at": "2026-01-01T00:00:00Z",
            "processed": True,  # already processed
            "processed_at": "2026-01-01T00:00:00Z",
        })

        async with TestClient(TestServer(app)) as client:
            resp = await client.post(
                "/api/requirements/process-sync",
                headers={"Content-Type": "application/json"},
                data=json.dumps({}),
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["processed_count"] == 0


# ---------------------------------------------------------------------------
# AI-93 Tests: update_requirement queued_for_sync
# ---------------------------------------------------------------------------

class TestUpdateRequirementSyncFlag:
    """PUT /api/requirements/{ticket_key} - queued_for_sync response field."""

    @pytest.mark.asyncio
    async def test_queued_for_sync_true_when_sync_to_linear_true(self, app):
        """Response includes queued_for_sync=True when sync_to_linear=True."""
        async with TestClient(TestServer(app)) as client:
            resp = await client.put(
                "/api/requirements/AI-900",
                headers={"Content-Type": "application/json"},
                data=json.dumps({
                    "edited_description": "New requirement text",
                    "sync_to_linear": True,
                }),
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["queued_for_sync"] is True
            assert data["status"] == "success"

    @pytest.mark.asyncio
    async def test_queued_for_sync_false_when_sync_to_linear_false(self, app):
        """Response includes queued_for_sync=False when sync_to_linear=False."""
        async with TestClient(TestServer(app)) as client:
            resp = await client.put(
                "/api/requirements/AI-901",
                headers={"Content-Type": "application/json"},
                data=json.dumps({
                    "edited_description": "Local requirement text",
                    "sync_to_linear": False,
                }),
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["queued_for_sync"] is False

    @pytest.mark.asyncio
    async def test_missing_body_returns_400(self, app):
        """PUT with missing required field returns 400."""
        async with TestClient(TestServer(app)) as client:
            resp = await client.put(
                "/api/requirements/AI-902",
                headers={"Content-Type": "application/json"},
                data=json.dumps({"sync_to_linear": True}),  # no edited_description
            )
            assert resp.status == 400
            data = await resp.json()
            assert "error" in data
