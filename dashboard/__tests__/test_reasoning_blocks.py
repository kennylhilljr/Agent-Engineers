"""Tests for AI-160: REQ-REASONING-003: Implement Collapsible Reasoning Blocks.

Tests cover:
- GET /api/reasoning/blocks returns empty list initially
- After POST /api/reasoning, GET /api/reasoning/blocks returns 1 item
- After POST /api/agent-thinking, GET /api/reasoning/blocks returns 1 item
- History is bounded (max 100 items — circular buffer)
- Block summary fields are correct for reasoning events
- Block summary fields are correct for agent_thinking events
"""

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

from dashboard.server import DashboardServer, _REASONING_HISTORY_MAX


# ---------------------------------------------------------------------------
# Test helpers / fixtures
# ---------------------------------------------------------------------------

class TestReasoningBlocksBase(AioHTTPTestCase):
    """Base class: creates a fresh DashboardServer for each test method."""

    async def get_application(self):
        self._temp_dir = tempfile.mkdtemp()
        self._ds = DashboardServer(
            project_name="test-reasoning-blocks",
            metrics_dir=Path(self._temp_dir),
        )
        return self._ds.app


# ---------------------------------------------------------------------------
# Test: GET /api/reasoning/blocks returns empty list initially
# ---------------------------------------------------------------------------

class TestReasoningBlocksEmpty(TestReasoningBlocksBase):
    """GET /api/reasoning/blocks is empty on a fresh server."""

    @unittest_run_loop
    async def test_get_reasoning_blocks_initially_empty(self):
        """GET /api/reasoning/blocks returns empty blocks list on fresh server."""
        resp = await self.client.request("GET", "/api/reasoning/blocks")
        assert resp.status == 200
        data = await resp.json()
        assert "blocks" in data
        assert "total" in data
        assert data["blocks"] == []
        assert data["total"] == 0

    @unittest_run_loop
    async def test_get_reasoning_blocks_content_type_json(self):
        """GET /api/reasoning/blocks returns JSON content type."""
        resp = await self.client.request("GET", "/api/reasoning/blocks")
        assert "application/json" in resp.headers.get("Content-Type", "")


# ---------------------------------------------------------------------------
# Test: After POST /api/reasoning, GET /api/reasoning/blocks returns 1 item
# ---------------------------------------------------------------------------

class TestReasoningBlocksAfterReasoning(TestReasoningBlocksBase):
    """History is updated after a POST /api/reasoning call."""

    @unittest_run_loop
    async def test_post_reasoning_then_get_blocks_returns_one_item(self):
        """After POST /api/reasoning, GET /api/reasoning/blocks contains 1 block."""
        payload = {
            "content": "Ticket AI-160: COMPLEX. Implementing collapsible blocks.",
            "ticket": "AI-160",
        }
        post_resp = await self.client.request(
            "POST", "/api/reasoning",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert post_resp.status == 200

        get_resp = await self.client.request("GET", "/api/reasoning/blocks")
        assert get_resp.status == 200
        data = await get_resp.json()
        assert data["total"] == 1
        assert len(data["blocks"]) == 1

    @unittest_run_loop
    async def test_reasoning_block_has_correct_fields(self):
        """Reasoning block in history contains type, content, ticket, timestamp."""
        payload = {
            "content": "Implementing expand/collapse UI for reasoning blocks.",
            "ticket": "AI-160",
        }
        await self.client.request(
            "POST", "/api/reasoning",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        get_resp = await self.client.request("GET", "/api/reasoning/blocks")
        data = await get_resp.json()
        block = data["blocks"][0]

        assert block["type"] == "reasoning"
        assert block["content"] == payload["content"]
        assert block["ticket"] == payload["ticket"]
        assert "timestamp" in block

    @unittest_run_loop
    async def test_multiple_reasoning_posts_accumulate(self):
        """Multiple POST /api/reasoning calls accumulate in history."""
        for i in range(3):
            payload = {"content": f"Reasoning step {i}", "ticket": "AI-160"}
            resp = await self.client.request(
                "POST", "/api/reasoning",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            assert resp.status == 200

        get_resp = await self.client.request("GET", "/api/reasoning/blocks")
        data = await get_resp.json()
        assert data["total"] == 3
        assert len(data["blocks"]) == 3


# ---------------------------------------------------------------------------
# Test: After POST /api/agent-thinking, GET /api/reasoning/blocks returns 1 item
# ---------------------------------------------------------------------------

class TestReasoningBlocksAfterAgentThinking(TestReasoningBlocksBase):
    """History is updated after a POST /api/agent-thinking call."""

    @unittest_run_loop
    async def test_post_agent_thinking_then_get_blocks_returns_one_item(self):
        """After POST /api/agent-thinking, GET /api/reasoning/blocks contains 1 block."""
        payload = {
            "agent": "coding",
            "category": "files",
            "content": "Reading server.py to understand current routes",
            "ticket": "AI-160",
        }
        post_resp = await self.client.request(
            "POST", "/api/agent-thinking",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert post_resp.status == 200

        get_resp = await self.client.request("GET", "/api/reasoning/blocks")
        assert get_resp.status == 200
        data = await get_resp.json()
        assert data["total"] == 1
        assert len(data["blocks"]) == 1

    @unittest_run_loop
    async def test_agent_thinking_block_has_correct_fields(self):
        """Agent thinking block in history has type, agent, category, content, ticket, timestamp."""
        payload = {
            "agent": "coding",
            "category": "changes",
            "content": "Adding GET /api/reasoning/blocks endpoint to server.py",
            "ticket": "AI-160",
        }
        await self.client.request(
            "POST", "/api/agent-thinking",
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )

        get_resp = await self.client.request("GET", "/api/reasoning/blocks")
        data = await get_resp.json()
        block = data["blocks"][0]

        assert block["type"] == "agent_thinking"
        assert block["agent"] == "coding"
        assert block["category"] == "changes"
        assert block["content"] == payload["content"]
        assert block["ticket"] == "AI-160"
        assert "timestamp" in block

    @unittest_run_loop
    async def test_mixed_events_both_appear_in_blocks(self):
        """Both reasoning and agent_thinking events appear in /api/reasoning/blocks."""
        await self.client.request(
            "POST", "/api/reasoning",
            data=json.dumps({"content": "Delegating to coding", "ticket": "AI-160"}),
            headers={"Content-Type": "application/json"},
        )
        await self.client.request(
            "POST", "/api/agent-thinking",
            data=json.dumps({"agent": "coding", "category": "commands",
                             "content": "Running tests", "ticket": "AI-160"}),
            headers={"Content-Type": "application/json"},
        )

        get_resp = await self.client.request("GET", "/api/reasoning/blocks")
        data = await get_resp.json()
        assert data["total"] == 2
        types = {b["type"] for b in data["blocks"]}
        assert "reasoning" in types
        assert "agent_thinking" in types


# ---------------------------------------------------------------------------
# Test: History is bounded at max 100 items (circular buffer)
# ---------------------------------------------------------------------------

class TestReasoningBlocksCircularBuffer(TestReasoningBlocksBase):
    """Circular buffer keeps at most _REASONING_HISTORY_MAX (100) items."""

    @unittest_run_loop
    async def test_history_bounded_at_max_100_items(self):
        """Posting more than 100 reasoning events keeps only the last 100."""
        over_limit = _REASONING_HISTORY_MAX + 10  # 110

        for i in range(over_limit):
            payload = {"content": f"Reasoning event #{i}", "ticket": "AI-160"}
            resp = await self.client.request(
                "POST", "/api/reasoning",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
            assert resp.status == 200

        get_resp = await self.client.request("GET", "/api/reasoning/blocks")
        data = await get_resp.json()

        # total reflects items stored (capped at max)
        assert data["total"] == _REASONING_HISTORY_MAX
        # blocks returns at most 50 (the last 50 of 100)
        assert len(data["blocks"]) <= 50

    @unittest_run_loop
    async def test_history_keeps_most_recent_events_when_full(self):
        """When buffer is full, the oldest events are dropped, newest are kept."""
        over_limit = _REASONING_HISTORY_MAX + 5  # 105

        for i in range(over_limit):
            payload = {"content": f"Event-{i:03d}", "ticket": "AI-160"}
            await self.client.request(
                "POST", "/api/reasoning",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )

        get_resp = await self.client.request("GET", "/api/reasoning/blocks")
        data = await get_resp.json()

        # The last 50 entries returned should be the most recent ones
        returned_contents = [b["content"] for b in data["blocks"]]
        # The last event posted should be in the returned blocks
        assert "Event-104" in returned_contents
        # The very first event should have been evicted
        assert "Event-000" not in returned_contents

    @unittest_run_loop
    async def test_max_100_constant_value(self):
        """_REASONING_HISTORY_MAX is set to 100."""
        assert _REASONING_HISTORY_MAX == 100

    @unittest_run_loop
    async def test_history_bounded_with_mixed_event_types(self):
        """Circular buffer respects max with mixed reasoning + agent_thinking events."""
        # Post 60 reasoning + 50 agent_thinking = 110 total, should cap at 100
        for i in range(60):
            payload = {"content": f"Reasoning {i}", "ticket": "AI-160"}
            await self.client.request(
                "POST", "/api/reasoning",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )
        for i in range(50):
            payload = {"agent": "coding", "category": "tests",
                       "content": f"Thinking {i}", "ticket": "AI-160"}
            await self.client.request(
                "POST", "/api/agent-thinking",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )

        get_resp = await self.client.request("GET", "/api/reasoning/blocks")
        data = await get_resp.json()
        assert data["total"] == _REASONING_HISTORY_MAX


# ---------------------------------------------------------------------------
# Test: GET /api/reasoning/blocks returns at most 50 even if 100 stored
# ---------------------------------------------------------------------------

class TestReasoningBlocksPagination(TestReasoningBlocksBase):
    """GET /api/reasoning/blocks returns last 50 items even when 100 are stored."""

    @unittest_run_loop
    async def test_blocks_response_capped_at_50_items(self):
        """blocks list in response is at most 50 items even when total is 100."""
        for i in range(_REASONING_HISTORY_MAX):
            payload = {"content": f"Event-{i}", "ticket": "AI-160"}
            await self.client.request(
                "POST", "/api/reasoning",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )

        get_resp = await self.client.request("GET", "/api/reasoning/blocks")
        data = await get_resp.json()

        assert data["total"] == _REASONING_HISTORY_MAX
        assert len(data["blocks"]) == 50  # returns last 50

    @unittest_run_loop
    async def test_blocks_response_all_items_when_under_50(self):
        """blocks list returns all items when fewer than 50 are stored."""
        for i in range(10):
            payload = {"content": f"Event-{i}", "ticket": "AI-160"}
            await self.client.request(
                "POST", "/api/reasoning",
                data=json.dumps(payload),
                headers={"Content-Type": "application/json"},
            )

        get_resp = await self.client.request("GET", "/api/reasoning/blocks")
        data = await get_resp.json()

        assert data["total"] == 10
        assert len(data["blocks"]) == 10
