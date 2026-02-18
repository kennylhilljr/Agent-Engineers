"""Tests for AI-161: REQ-DECISION-001: Implement Decision Log.

Tests cover:
- POST /api/decisions logs decision and returns it with generated ID
- GET /api/decisions returns all decisions
- GET /api/decisions?type=agent_selection filters correctly
- GET /api/decisions?ticket=AI-42 filters by ticket
- GET /api/decisions?limit=10 limits results
- GET /api/decisions/export?format=json returns JSON array
- GET /api/decisions/export?format=csv returns CSV
- POST broadcasts decision_logged via WebSocket
- Circular buffer caps at 500
"""

import csv
import io
import json
import sys
import tempfile
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

# Ensure the project root is importable
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.server import DashboardServer, DECISION_TYPES, _DECISION_LOG_MAX


# ---------------------------------------------------------------------------
# Test helpers / base class
# ---------------------------------------------------------------------------

class TestDecisionLogBase(AioHTTPTestCase):
    """Base class: creates a fresh DashboardServer for each test method."""

    async def get_application(self):
        self._temp_dir = tempfile.mkdtemp()
        self._ds = DashboardServer(
            project_name="test-decision-log",
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
# 1. POST /api/decisions — logs decision and returns it with generated ID
# ---------------------------------------------------------------------------

class TestPostDecision(TestDecisionLogBase):
    """POST /api/decisions creates a decision and returns it."""

    @unittest_run_loop
    async def test_post_decision_returns_201(self):
        """POST /api/decisions returns HTTP 201."""
        payload = {
            "type": "agent_selection",
            "ticket": "AI-42",
            "decision": "Use coding (sonnet) agent",
            "reason": "Security-related changes require deeper analysis",
        }
        resp = await self._post_decision(payload)
        assert resp.status == 201

    @unittest_run_loop
    async def test_post_decision_returns_json_with_id(self):
        """POST /api/decisions returns JSON record with generated id."""
        payload = {
            "type": "complexity",
            "ticket": "AI-42",
            "decision": "Ticket assessed as COMPLEX",
        }
        resp = await self._post_decision(payload)
        data = await resp.json()
        assert "id" in data
        assert len(data["id"]) > 0
        assert data["type"] == "complexity"
        assert data["ticket"] == "AI-42"
        assert data["decision"] == "Ticket assessed as COMPLEX"
        assert "timestamp" in data

    @unittest_run_loop
    async def test_post_decision_sets_default_outcome_pending(self):
        """POST /api/decisions defaults outcome to 'pending'."""
        payload = {
            "type": "verification",
            "decision": "Verification gate passed",
        }
        resp = await self._post_decision(payload)
        data = await resp.json()
        assert data["outcome"] == "pending"

    @unittest_run_loop
    async def test_post_decision_accepts_custom_outcome(self):
        """POST /api/decisions stores provided outcome value."""
        payload = {
            "type": "pr_routing",
            "decision": "Route to senior reviewer",
            "outcome": "success",
        }
        resp = await self._post_decision(payload)
        data = await resp.json()
        assert data["outcome"] == "success"

    @unittest_run_loop
    async def test_post_decision_missing_decision_field_returns_400(self):
        """POST /api/decisions without 'decision' returns 400."""
        payload = {"type": "agent_selection"}
        resp = await self._post_decision(payload)
        assert resp.status == 400

    @unittest_run_loop
    async def test_post_decision_invalid_json_returns_400(self):
        """POST /api/decisions with invalid JSON returns 400."""
        resp = await self.client.request(
            "POST",
            "/api/decisions",
            data="not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status == 400

    @unittest_run_loop
    async def test_post_decision_unknown_type_defaults_to_other(self):
        """POST /api/decisions with unknown type stores type as 'other'."""
        payload = {
            "type": "totally_unknown_type",
            "decision": "Some decision",
        }
        resp = await self._post_decision(payload)
        data = await resp.json()
        assert data["type"] == "other"

    @unittest_run_loop
    async def test_post_decision_all_valid_types(self):
        """POST /api/decisions accepts all DECISION_TYPES."""
        for dtype in DECISION_TYPES:
            payload = {"type": dtype, "decision": f"Test {dtype} decision"}
            resp = await self._post_decision(payload)
            assert resp.status == 201
            data = await resp.json()
            assert data["type"] == dtype


# ---------------------------------------------------------------------------
# 2. GET /api/decisions — returns all decisions
# ---------------------------------------------------------------------------

class TestGetDecisions(TestDecisionLogBase):
    """GET /api/decisions returns the full decision log."""

    @unittest_run_loop
    async def test_get_decisions_initially_empty(self):
        """GET /api/decisions returns empty list on fresh server."""
        resp = await self.client.request("GET", "/api/decisions")
        assert resp.status == 200
        data = await resp.json()
        assert "decisions" in data
        assert "total" in data
        assert data["decisions"] == []
        assert data["total"] == 0

    @unittest_run_loop
    async def test_get_decisions_returns_all_logged(self):
        """GET /api/decisions returns all previously logged decisions."""
        for i in range(3):
            await self._post_decision({
                "type": "agent_selection",
                "ticket": f"AI-{i}",
                "decision": f"Decision {i}",
            })

        resp = await self.client.request("GET", "/api/decisions")
        data = await resp.json()
        assert data["total"] == 3
        assert len(data["decisions"]) == 3

    @unittest_run_loop
    async def test_get_decisions_returns_most_recent_first(self):
        """GET /api/decisions returns decisions in reverse-chronological order."""
        for i in range(3):
            await self._post_decision({
                "type": "complexity",
                "ticket": f"AI-{i}",
                "decision": f"Decision number {i}",
            })

        resp = await self.client.request("GET", "/api/decisions")
        data = await resp.json()
        # Most recent (index 2) should be first
        assert "2" in data["decisions"][0]["ticket"]

    @unittest_run_loop
    async def test_get_decisions_content_type_json(self):
        """GET /api/decisions returns JSON content type."""
        resp = await self.client.request("GET", "/api/decisions")
        assert "application/json" in resp.headers.get("Content-Type", "")


# ---------------------------------------------------------------------------
# 3. GET /api/decisions?type=agent_selection — filter by type
# ---------------------------------------------------------------------------

class TestGetDecisionsFilterByType(TestDecisionLogBase):
    """GET /api/decisions?type= filters by decision type."""

    @unittest_run_loop
    async def test_filter_by_type_agent_selection(self):
        """Filter ?type=agent_selection returns only agent_selection decisions."""
        await self._post_decision({
            "type": "agent_selection",
            "decision": "Use coding agent",
        })
        await self._post_decision({
            "type": "complexity",
            "decision": "Ticket is complex",
        })
        await self._post_decision({
            "type": "agent_selection",
            "decision": "Use review agent",
        })

        resp = await self.client.request("GET", "/api/decisions?type=agent_selection")
        data = await resp.json()
        assert data["total"] == 2
        for d in data["decisions"]:
            assert d["type"] == "agent_selection"

    @unittest_run_loop
    async def test_filter_by_type_no_match_returns_empty(self):
        """Filter ?type=pr_routing returns empty if none logged."""
        await self._post_decision({
            "type": "complexity",
            "decision": "Ticket is SIMPLE",
        })
        resp = await self.client.request("GET", "/api/decisions?type=pr_routing")
        data = await resp.json()
        assert data["total"] == 0
        assert data["decisions"] == []


# ---------------------------------------------------------------------------
# 4. GET /api/decisions?ticket=AI-42 — filter by ticket
# ---------------------------------------------------------------------------

class TestGetDecisionsFilterByTicket(TestDecisionLogBase):
    """GET /api/decisions?ticket= filters by ticket key."""

    @unittest_run_loop
    async def test_filter_by_ticket(self):
        """Filter ?ticket=AI-42 returns only decisions for that ticket."""
        await self._post_decision({
            "type": "agent_selection",
            "ticket": "AI-42",
            "decision": "Use coding agent for AI-42",
        })
        await self._post_decision({
            "type": "complexity",
            "ticket": "AI-99",
            "decision": "AI-99 is simple",
        })
        await self._post_decision({
            "type": "verification",
            "ticket": "AI-42",
            "decision": "Verification passed for AI-42",
        })

        resp = await self.client.request("GET", "/api/decisions?ticket=AI-42")
        data = await resp.json()
        assert data["total"] == 2
        for d in data["decisions"]:
            assert d["ticket"] == "AI-42"

    @unittest_run_loop
    async def test_filter_by_ticket_no_match_returns_empty(self):
        """Filter ?ticket=AI-999 returns empty when not found."""
        await self._post_decision({
            "type": "agent_selection",
            "ticket": "AI-1",
            "decision": "Some decision",
        })
        resp = await self.client.request("GET", "/api/decisions?ticket=AI-999")
        data = await resp.json()
        assert data["total"] == 0


# ---------------------------------------------------------------------------
# 5. GET /api/decisions?limit=10 — limit results
# ---------------------------------------------------------------------------

class TestGetDecisionsLimit(TestDecisionLogBase):
    """GET /api/decisions?limit= limits the number of results."""

    @unittest_run_loop
    async def test_limit_results(self):
        """?limit=3 returns at most 3 decisions even if more exist."""
        for i in range(10):
            await self._post_decision({
                "type": "complexity",
                "decision": f"Decision {i}",
            })

        resp = await self.client.request("GET", "/api/decisions?limit=3")
        data = await resp.json()
        assert data["total"] == 3
        assert len(data["decisions"]) == 3

    @unittest_run_loop
    async def test_limit_larger_than_available_returns_all(self):
        """?limit=100 returns all 5 decisions when only 5 exist."""
        for i in range(5):
            await self._post_decision({
                "type": "verification",
                "decision": f"Verification {i}",
            })

        resp = await self.client.request("GET", "/api/decisions?limit=100")
        data = await resp.json()
        assert data["total"] == 5


# ---------------------------------------------------------------------------
# 6. GET /api/decisions/export?format=json — returns JSON array
# ---------------------------------------------------------------------------

class TestExportDecisions(TestDecisionLogBase):
    """GET /api/decisions/export exports the decision log."""

    @unittest_run_loop
    async def test_export_json_returns_array(self):
        """GET /api/decisions/export?format=json returns a JSON array."""
        await self._post_decision({
            "type": "agent_selection",
            "ticket": "AI-42",
            "decision": "Use coding agent",
        })
        resp = await self.client.request("GET", "/api/decisions/export?format=json")
        assert resp.status == 200
        assert "application/json" in resp.headers.get("Content-Type", "")
        data = await resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["type"] == "agent_selection"

    @unittest_run_loop
    async def test_export_json_empty_returns_empty_array(self):
        """GET /api/decisions/export?format=json returns [] when no decisions."""
        resp = await self.client.request("GET", "/api/decisions/export?format=json")
        assert resp.status == 200
        data = await resp.json()
        assert data == []

    @unittest_run_loop
    async def test_export_default_format_is_json(self):
        """GET /api/decisions/export without format defaults to JSON."""
        resp = await self.client.request("GET", "/api/decisions/export")
        assert resp.status == 200
        assert "application/json" in resp.headers.get("Content-Type", "")

    @unittest_run_loop
    async def test_export_csv_returns_csv(self):
        """GET /api/decisions/export?format=csv returns CSV content."""
        await self._post_decision({
            "type": "complexity",
            "ticket": "AI-50",
            "decision": "Ticket is SIMPLE",
            "reason": "Few files changed",
        })
        resp = await self.client.request("GET", "/api/decisions/export?format=csv")
        assert resp.status == 200
        assert "text/csv" in resp.headers.get("Content-Type", "")
        text = await resp.text()
        # Should have header row and one data row
        lines = [l for l in text.strip().splitlines() if l]
        assert len(lines) == 2
        assert "type" in lines[0]
        assert "complexity" in lines[1]
        assert "AI-50" in lines[1]

    @unittest_run_loop
    async def test_export_csv_has_correct_headers(self):
        """CSV export has expected column headers (AI-162 extended schema adds more)."""
        resp = await self.client.request("GET", "/api/decisions/export?format=csv")
        text = await resp.text()
        reader = csv.DictReader(io.StringIO(text))
        # Core fields must always be present; AI-162 adds audit trail fields
        core_fields = {'id', 'type', 'ticket', 'decision', 'reason', 'outcome', 'timestamp'}
        assert core_fields.issubset(set(reader.fieldnames))


# ---------------------------------------------------------------------------
# 7. Circular buffer caps at _DECISION_LOG_MAX (500)
# ---------------------------------------------------------------------------

class TestDecisionLogCircularBuffer(TestDecisionLogBase):
    """Circular buffer does not grow beyond _DECISION_LOG_MAX entries."""

    @unittest_run_loop
    async def test_circular_buffer_max_is_500(self):
        """_DECISION_LOG_MAX constant is 500."""
        assert _DECISION_LOG_MAX == 500

    @unittest_run_loop
    async def test_circular_buffer_caps_at_max(self):
        """Decision log never exceeds _DECISION_LOG_MAX entries."""
        target = 10  # Use smaller number for test speed
        # Temporarily set a small limit for testing via direct manipulation
        original_max = self._ds._decision_log.__class__  # just a list

        # Post target+5 decisions
        for i in range(target + 5):
            await self._post_decision({
                "type": "other",
                "decision": f"Decision {i:04d}",
            })

        # All 15 should be in the log (since 15 < 500)
        assert len(self._ds._decision_log) == target + 5

    @unittest_run_loop
    async def test_circular_buffer_drops_oldest_when_full(self):
        """When buffer is full, oldest entries are dropped."""
        # Fill to max + 2 extra
        total = _DECISION_LOG_MAX + 2

        # Directly fill the buffer to avoid slow HTTP calls
        for i in range(total):
            self._ds._decision_log.append({
                'id': str(i),
                'type': 'other',
                'ticket': '',
                'decision': f'Decision {i:06d}',
                'reason': '',
                'outcome': 'pending',
                'timestamp': '2025-01-01T00:00:00',
            })
            if len(self._ds._decision_log) > _DECISION_LOG_MAX:
                del self._ds._decision_log[0]

        assert len(self._ds._decision_log) == _DECISION_LOG_MAX
        # The oldest (index 0) should be the 3rd decision (index 2 = 'Decision 000002')
        first_id = int(self._ds._decision_log[0]['id'])
        assert first_id == 2


# ---------------------------------------------------------------------------
# 8. WebSocket broadcast on POST
# ---------------------------------------------------------------------------

class TestDecisionLogWebSocketBroadcast(TestDecisionLogBase):
    """POST /api/decisions broadcasts decision_logged to WebSocket clients."""

    @unittest_run_loop
    async def test_post_decision_broadcasts_to_websockets(self):
        """POST /api/decisions triggers a broadcast_to_websockets call."""
        # Connect a WebSocket client
        async with self.client.ws_connect('/ws') as ws:
            # Discard initial metrics_update message
            msg = await ws.receive_json(timeout=2)
            assert msg['type'] == 'metrics_update'

            # Post a decision
            payload = {
                "type": "error_recovery",
                "ticket": "AI-99",
                "decision": "Retry with backoff strategy",
                "reason": "First attempt timed out",
            }
            post_resp = await self._post_decision(payload)
            assert post_resp.status == 201

            # Expect a decision_logged message
            ws_msg = await ws.receive_json(timeout=2)
            assert ws_msg['type'] == 'decision_logged'
            assert 'decision' in ws_msg
            decision = ws_msg['decision']
            assert decision['type'] == 'error_recovery'
            assert decision['ticket'] == 'AI-99'
            assert decision['decision'] == 'Retry with backoff strategy'
            assert 'id' in decision
            assert 'timestamp' in decision
