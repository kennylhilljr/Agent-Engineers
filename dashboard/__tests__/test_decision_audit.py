"""Tests for AI-162: REQ-DECISION-002: Implement Decision Audit Trail.

Tests cover:
- POST with full audit fields stores all fields
- POST with minimal fields uses defaults
- GET /api/decisions/{id} returns specific decision
- GET /api/decisions/summary returns correct counts
- input_factors stored correctly
- agent_selected and model_used stored correctly
- Filtering by type still works with extended schema
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

# Ensure the project root is importable
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.server import DashboardServer, DECISION_TYPES


# ---------------------------------------------------------------------------
# Test helpers / base class
# ---------------------------------------------------------------------------

class TestDecisionAuditBase(AioHTTPTestCase):
    """Base class: creates a fresh DashboardServer for each test method."""

    async def get_application(self):
        self._temp_dir = tempfile.mkdtemp()
        self._ds = DashboardServer(
            project_name="test-decision-audit",
            metrics_dir=Path(self._temp_dir),
        )
        return self._ds.app

    async def _post_decision(self, payload):
        """Helper: POST a decision and return the response."""
        return await self.client.request(
            "POST",
            "/api/decisions",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )


# ---------------------------------------------------------------------------
# 1. POST with full audit fields stores all new fields
# ---------------------------------------------------------------------------

class TestPostDecisionAuditFields(TestDecisionAuditBase):
    """POST /api/decisions with full audit trail fields stores them correctly."""

    @unittest_run_loop
    async def test_post_with_full_audit_fields_returns_201(self):
        """POST /api/decisions with all audit fields returns HTTP 201."""
        payload = {
            "type": "agent_selection",
            "ticket": "AI-162",
            "decision": "Select coding agent for AI-162",
            "reason": "Complexity analysis indicates this needs expert treatment",
            "outcome": "success",
            "input_factors": {
                "keywords": ["security", "auth"],
                "verification_status": "pass",
                "context": "Recent security review passed",
            },
            "agent_selected": "coding",
            "model_used": "claude-sonnet-4-5",
            "agent_event_id": "evt-abc-123",
            "duration_ms": 42,
            "session_id": "session-xyz",
        }
        resp = await self._post_decision(payload)
        assert resp.status == 201

    @unittest_run_loop
    async def test_post_stores_input_factors(self):
        """POST /api/decisions stores input_factors dict correctly."""
        input_factors = {
            "keywords": ["security", "auth"],
            "verification_status": "pass",
            "context": "Recent security review passed",
        }
        payload = {
            "type": "complexity",
            "decision": "Ticket is COMPLEX",
            "input_factors": input_factors,
        }
        resp = await self._post_decision(payload)
        data = await resp.json()
        assert "input_factors" in data
        assert data["input_factors"]["keywords"] == ["security", "auth"]
        assert data["input_factors"]["verification_status"] == "pass"
        assert data["input_factors"]["context"] == "Recent security review passed"

    @unittest_run_loop
    async def test_post_stores_agent_selected(self):
        """POST /api/decisions stores agent_selected field."""
        payload = {
            "type": "agent_selection",
            "decision": "Use coding_fast agent",
            "agent_selected": "coding_fast",
        }
        resp = await self._post_decision(payload)
        data = await resp.json()
        assert data["agent_selected"] == "coding_fast"

    @unittest_run_loop
    async def test_post_stores_model_used(self):
        """POST /api/decisions stores model_used field."""
        payload = {
            "type": "agent_selection",
            "decision": "Use haiku model",
            "model_used": "claude-haiku-4-5",
        }
        resp = await self._post_decision(payload)
        data = await resp.json()
        assert data["model_used"] == "claude-haiku-4-5"

    @unittest_run_loop
    async def test_post_stores_agent_event_id(self):
        """POST /api/decisions stores agent_event_id for cross-linking."""
        payload = {
            "type": "agent_selection",
            "decision": "Select agent",
            "agent_event_id": "evt-abc-123",
        }
        resp = await self._post_decision(payload)
        data = await resp.json()
        assert data["agent_event_id"] == "evt-abc-123"

    @unittest_run_loop
    async def test_post_stores_duration_ms(self):
        """POST /api/decisions stores duration_ms field."""
        payload = {
            "type": "complexity",
            "decision": "Analysis took 42ms",
            "duration_ms": 42,
        }
        resp = await self._post_decision(payload)
        data = await resp.json()
        assert data["duration_ms"] == 42

    @unittest_run_loop
    async def test_post_stores_session_id(self):
        """POST /api/decisions stores session_id for grouping."""
        payload = {
            "type": "verification",
            "decision": "Verification passed",
            "session_id": "session-xyz-999",
        }
        resp = await self._post_decision(payload)
        data = await resp.json()
        assert data["session_id"] == "session-xyz-999"

    @unittest_run_loop
    async def test_post_all_audit_fields_roundtrip(self):
        """POST /api/decisions with all audit fields stores and returns them all."""
        payload = {
            "type": "agent_selection",
            "ticket": "AI-162",
            "decision": "Full audit trail test",
            "reason": "Testing all fields",
            "outcome": "success",
            "input_factors": {"keywords": ["k1"], "verification_status": "pass"},
            "agent_selected": "coding",
            "model_used": "claude-sonnet-4-5",
            "agent_event_id": "evt-roundtrip-001",
            "duration_ms": 100,
            "session_id": "sess-full-001",
        }
        resp = await self._post_decision(payload)
        assert resp.status == 201
        data = await resp.json()

        assert data["type"] == "agent_selection"
        assert data["ticket"] == "AI-162"
        assert data["decision"] == "Full audit trail test"
        assert data["reason"] == "Testing all fields"
        assert data["outcome"] == "success"
        assert data["input_factors"]["keywords"] == ["k1"]
        assert data["input_factors"]["verification_status"] == "pass"
        assert data["agent_selected"] == "coding"
        assert data["model_used"] == "claude-sonnet-4-5"
        assert data["agent_event_id"] == "evt-roundtrip-001"
        assert data["duration_ms"] == 100
        assert data["session_id"] == "sess-full-001"
        assert "id" in data
        assert "timestamp" in data


# ---------------------------------------------------------------------------
# 2. POST with minimal fields uses defaults for new audit fields
# ---------------------------------------------------------------------------

class TestPostDecisionMinimalFields(TestDecisionAuditBase):
    """POST /api/decisions with minimal fields uses sensible defaults."""

    @unittest_run_loop
    async def test_minimal_post_defaults_input_factors_to_empty_dict(self):
        """POST without input_factors defaults to empty dict."""
        payload = {
            "type": "complexity",
            "decision": "Minimal decision",
        }
        resp = await self._post_decision(payload)
        data = await resp.json()
        assert data["input_factors"] == {}

    @unittest_run_loop
    async def test_minimal_post_defaults_agent_selected_to_empty_string(self):
        """POST without agent_selected defaults to empty string."""
        payload = {"type": "other", "decision": "Minimal"}
        resp = await self._post_decision(payload)
        data = await resp.json()
        assert data["agent_selected"] == ""

    @unittest_run_loop
    async def test_minimal_post_defaults_model_used_to_empty_string(self):
        """POST without model_used defaults to empty string."""
        payload = {"type": "other", "decision": "Minimal"}
        resp = await self._post_decision(payload)
        data = await resp.json()
        assert data["model_used"] == ""

    @unittest_run_loop
    async def test_minimal_post_defaults_agent_event_id_to_empty_string(self):
        """POST without agent_event_id defaults to empty string."""
        payload = {"type": "other", "decision": "Minimal"}
        resp = await self._post_decision(payload)
        data = await resp.json()
        assert data["agent_event_id"] == ""

    @unittest_run_loop
    async def test_minimal_post_defaults_duration_ms_to_none(self):
        """POST without duration_ms defaults to None."""
        payload = {"type": "other", "decision": "Minimal"}
        resp = await self._post_decision(payload)
        data = await resp.json()
        assert data["duration_ms"] is None

    @unittest_run_loop
    async def test_minimal_post_defaults_session_id_to_empty_string(self):
        """POST without session_id defaults to empty string."""
        payload = {"type": "other", "decision": "Minimal"}
        resp = await self._post_decision(payload)
        data = await resp.json()
        assert data["session_id"] == ""


# ---------------------------------------------------------------------------
# 3. GET /api/decisions/{id} returns specific decision
# ---------------------------------------------------------------------------

class TestGetDecisionById(TestDecisionAuditBase):
    """GET /api/decisions/{decision_id} returns a single decision record."""

    @unittest_run_loop
    async def test_get_by_id_returns_correct_decision(self):
        """GET /api/decisions/{id} returns the decision with that id."""
        payload = {
            "type": "verification",
            "ticket": "AI-200",
            "decision": "Verification check passed",
            "agent_event_id": "evt-verify-001",
        }
        post_resp = await self._post_decision(payload)
        posted = await post_resp.json()
        decision_id = posted["id"]

        get_resp = await self.client.request("GET", f"/api/decisions/{decision_id}")
        assert get_resp.status == 200
        data = await get_resp.json()
        assert data["id"] == decision_id
        assert data["type"] == "verification"
        assert data["ticket"] == "AI-200"
        assert data["decision"] == "Verification check passed"
        assert data["agent_event_id"] == "evt-verify-001"

    @unittest_run_loop
    async def test_get_by_id_includes_all_audit_fields(self):
        """GET /api/decisions/{id} returns all audit trail fields."""
        payload = {
            "type": "agent_selection",
            "decision": "Select model",
            "input_factors": {"keywords": ["auth"], "verification_status": "pass"},
            "agent_selected": "coding",
            "model_used": "claude-sonnet-4-5",
            "agent_event_id": "evt-001",
            "duration_ms": 55,
            "session_id": "sess-001",
        }
        post_resp = await self._post_decision(payload)
        posted = await post_resp.json()
        decision_id = posted["id"]

        get_resp = await self.client.request("GET", f"/api/decisions/{decision_id}")
        data = await get_resp.json()
        assert data["input_factors"]["keywords"] == ["auth"]
        assert data["agent_selected"] == "coding"
        assert data["model_used"] == "claude-sonnet-4-5"
        assert data["agent_event_id"] == "evt-001"
        assert data["duration_ms"] == 55
        assert data["session_id"] == "sess-001"

    @unittest_run_loop
    async def test_get_by_id_returns_404_for_unknown_id(self):
        """GET /api/decisions/{id} returns 404 when id not found."""
        get_resp = await self.client.request("GET", "/api/decisions/nonexistent-uuid-123")
        assert get_resp.status == 404

    @unittest_run_loop
    async def test_get_by_id_differentiates_multiple_decisions(self):
        """GET /api/decisions/{id} returns only the matching decision."""
        resp1 = await self._post_decision({"type": "complexity", "decision": "Decision A"})
        resp2 = await self._post_decision({"type": "verification", "decision": "Decision B"})
        d1 = await resp1.json()
        d2 = await resp2.json()

        get_resp = await self.client.request("GET", f"/api/decisions/{d1['id']}")
        data = await get_resp.json()
        assert data["decision"] == "Decision A"
        assert data["type"] == "complexity"


# ---------------------------------------------------------------------------
# 4. GET /api/decisions/summary returns correct counts
# ---------------------------------------------------------------------------

class TestGetDecisionsSummary(TestDecisionAuditBase):
    """GET /api/decisions/summary returns aggregate statistics."""

    @unittest_run_loop
    async def test_summary_initially_zero(self):
        """GET /api/decisions/summary returns zero counts on fresh server."""
        resp = await self.client.request("GET", "/api/decisions/summary")
        assert resp.status == 200
        data = await resp.json()
        assert data["total"] == 0
        assert data["by_type"] == {}
        assert data["by_outcome"] == {}
        assert data["recent_session_count"] == 0

    @unittest_run_loop
    async def test_summary_counts_by_type(self):
        """GET /api/decisions/summary counts decisions by type correctly."""
        await self._post_decision({"type": "agent_selection", "decision": "A1"})
        await self._post_decision({"type": "agent_selection", "decision": "A2"})
        await self._post_decision({"type": "complexity", "decision": "C1"})
        await self._post_decision({"type": "verification", "decision": "V1"})

        resp = await self.client.request("GET", "/api/decisions/summary")
        data = await resp.json()
        assert data["total"] == 4
        assert data["by_type"]["agent_selection"] == 2
        assert data["by_type"]["complexity"] == 1
        assert data["by_type"]["verification"] == 1

    @unittest_run_loop
    async def test_summary_counts_by_outcome(self):
        """GET /api/decisions/summary counts decisions by outcome correctly."""
        await self._post_decision({"type": "other", "decision": "D1", "outcome": "success"})
        await self._post_decision({"type": "other", "decision": "D2", "outcome": "success"})
        await self._post_decision({"type": "other", "decision": "D3", "outcome": "failure"})
        await self._post_decision({"type": "other", "decision": "D4", "outcome": "pending"})

        resp = await self.client.request("GET", "/api/decisions/summary")
        data = await resp.json()
        assert data["by_outcome"]["success"] == 2
        assert data["by_outcome"]["failure"] == 1
        assert data["by_outcome"]["pending"] == 1

    @unittest_run_loop
    async def test_summary_counts_sessions(self):
        """GET /api/decisions/summary counts unique session IDs."""
        await self._post_decision({"type": "other", "decision": "D1", "session_id": "sess-A"})
        await self._post_decision({"type": "other", "decision": "D2", "session_id": "sess-A"})
        await self._post_decision({"type": "other", "decision": "D3", "session_id": "sess-B"})
        await self._post_decision({"type": "other", "decision": "D4"})  # no session

        resp = await self.client.request("GET", "/api/decisions/summary")
        data = await resp.json()
        assert data["recent_session_count"] == 2

    @unittest_run_loop
    async def test_summary_total_matches_actual(self):
        """GET /api/decisions/summary total matches number of posted decisions."""
        for i in range(7):
            await self._post_decision({"type": "other", "decision": f"Decision {i}"})

        resp = await self.client.request("GET", "/api/decisions/summary")
        data = await resp.json()
        assert data["total"] == 7

    @unittest_run_loop
    async def test_summary_has_all_required_fields(self):
        """GET /api/decisions/summary response has all required fields."""
        resp = await self.client.request("GET", "/api/decisions/summary")
        data = await resp.json()
        assert "total" in data
        assert "by_type" in data
        assert "by_outcome" in data
        assert "recent_session_count" in data


# ---------------------------------------------------------------------------
# 5. Filtering by type still works with extended schema
# ---------------------------------------------------------------------------

class TestFilteringWithExtendedSchema(TestDecisionAuditBase):
    """Type filtering still works correctly after schema extension."""

    @unittest_run_loop
    async def test_filter_by_type_with_audit_fields(self):
        """?type=agent_selection still filters correctly with extended schema."""
        await self._post_decision({
            "type": "agent_selection",
            "decision": "Select coding agent",
            "agent_selected": "coding",
            "model_used": "claude-sonnet-4-5",
            "input_factors": {"keywords": ["security"]},
        })
        await self._post_decision({
            "type": "complexity",
            "decision": "Ticket is complex",
            "input_factors": {"keywords": ["large"]},
        })
        await self._post_decision({
            "type": "agent_selection",
            "decision": "Select fast agent",
            "agent_selected": "coding_fast",
        })

        resp = await self.client.request("GET", "/api/decisions?type=agent_selection")
        data = await resp.json()
        assert data["total"] == 2
        for d in data["decisions"]:
            assert d["type"] == "agent_selection"
            assert "input_factors" in d
            assert "agent_selected" in d
            assert "model_used" in d

    @unittest_run_loop
    async def test_filter_by_ticket_with_audit_fields(self):
        """?ticket=AI-42 still filters correctly with extended schema."""
        await self._post_decision({
            "type": "agent_selection",
            "ticket": "AI-42",
            "decision": "Decision for AI-42",
            "session_id": "sess-test",
        })
        await self._post_decision({
            "type": "complexity",
            "ticket": "AI-99",
            "decision": "Decision for AI-99",
        })

        resp = await self.client.request("GET", "/api/decisions?ticket=AI-42")
        data = await resp.json()
        assert data["total"] == 1
        assert data["decisions"][0]["ticket"] == "AI-42"
        assert data["decisions"][0]["session_id"] == "sess-test"

    @unittest_run_loop
    async def test_get_all_decisions_include_audit_fields(self):
        """GET /api/decisions returns decisions including all audit trail fields."""
        await self._post_decision({
            "type": "verification",
            "decision": "All audit fields present",
            "input_factors": {"keywords": ["test"]},
            "agent_selected": "review",
            "model_used": "claude-haiku-4-5",
            "agent_event_id": "evt-get-all",
            "duration_ms": 10,
            "session_id": "sess-get-all",
        })

        resp = await self.client.request("GET", "/api/decisions")
        data = await resp.json()
        assert data["total"] == 1
        d = data["decisions"][0]
        assert d["input_factors"]["keywords"] == ["test"]
        assert d["agent_selected"] == "review"
        assert d["model_used"] == "claude-haiku-4-5"
        assert d["agent_event_id"] == "evt-get-all"
        assert d["duration_ms"] == 10
        assert d["session_id"] == "sess-get-all"

    @unittest_run_loop
    async def test_all_decision_types_still_work_with_extended_schema(self):
        """All DECISION_TYPES still accepted after schema extension."""
        for dtype in DECISION_TYPES:
            payload = {
                "type": dtype,
                "decision": f"Test {dtype}",
                "agent_selected": "coding",
                "model_used": "claude-sonnet-4-5",
                "input_factors": {},
            }
            resp = await self._post_decision(payload)
            assert resp.status == 201
            data = await resp.json()
            assert data["type"] == dtype


# ---------------------------------------------------------------------------
# 6. WebSocket broadcast includes audit trail fields
# ---------------------------------------------------------------------------

class TestWebSocketAuditBroadcast(TestDecisionAuditBase):
    """POST /api/decisions broadcasts audit trail fields via WebSocket."""

    @unittest_run_loop
    async def test_ws_broadcast_includes_audit_fields(self):
        """decision_logged WebSocket event includes audit trail fields."""
        async with self.client.ws_connect('/ws') as ws:
            # Discard initial metrics_update
            msg = await ws.receive_json(timeout=2)
            assert msg['type'] == 'metrics_update'

            payload = {
                "type": "agent_selection",
                "ticket": "AI-162",
                "decision": "Select agent with audit",
                "agent_selected": "coding",
                "model_used": "claude-sonnet-4-5",
                "input_factors": {"keywords": ["security"]},
                "agent_event_id": "evt-ws-001",
                "session_id": "sess-ws",
            }
            post_resp = await self._post_decision(payload)
            assert post_resp.status == 201

            ws_msg = await ws.receive_json(timeout=2)
            assert ws_msg['type'] == 'decision_logged'
            decision = ws_msg['decision']
            assert decision['agent_selected'] == 'coding'
            assert decision['model_used'] == 'claude-sonnet-4-5'
            assert decision['input_factors']['keywords'] == ['security']
            assert decision['agent_event_id'] == 'evt-ws-001'
            assert decision['session_id'] == 'sess-ws'
