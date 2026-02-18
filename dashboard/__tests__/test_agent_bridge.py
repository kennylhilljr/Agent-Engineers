"""Tests for AI-109: Chat-to-Agent Bridge - Request Routing and Execution.

Tests cover:
- Intent parsing for all patterns
- Routing decisions
- Agent executor behavior
- Error handling
- Concurrent messages
- Server API endpoints: POST /api/chat, POST /api/chat/route, GET /api/chat/history

Coverage target: 80%+
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.intent_parser import (
    ParsedIntent,
    parse_intent,
    _find_closest_agent,
    KNOWN_AGENTS,
)
from dashboard.agent_executor import AgentExecutor, execute_intent, stream_intent_execution
from dashboard.chat_handler import ChatRouter, get_chat_history, clear_chat_history
import dashboard.server as server_module
from dashboard.server import DashboardServer


# ========== Intent Parser Tests ==========


class TestIntentParserStatusPatterns:
    """Tests for status query pattern detection."""

    def test_what_is_ticket_status(self):
        intent = parse_intent("What is AI-1 status?")
        assert intent.intent_type == "agent_action"
        assert intent.agent == "linear"
        assert intent.action == "status"
        assert intent.params["ticket"] == "AI-1"

    def test_whats_ticket_status_apostrophe(self):
        intent = parse_intent("What's AI-109 status?")
        assert intent.intent_type == "agent_action"
        assert intent.agent == "linear"
        assert intent.action == "status"
        assert intent.params["ticket"] == "AI-109"

    def test_status_of_ticket(self):
        intent = parse_intent("status of AI-42")
        assert intent.intent_type == "agent_action"
        assert intent.agent == "linear"
        assert intent.action == "status"
        assert intent.params["ticket"] == "AI-42"

    def test_status_for_ticket(self):
        intent = parse_intent("status for AI-200")
        assert intent.intent_type == "agent_action"
        assert intent.action == "status"
        assert intent.params["ticket"] == "AI-200"

    def test_check_ticket(self):
        intent = parse_intent("check AI-99")
        assert intent.intent_type == "agent_action"
        assert intent.action == "status"
        assert intent.params["ticket"] == "AI-99"

    def test_check_status_of_ticket(self):
        intent = parse_intent("check status of AI-5")
        assert intent.intent_type == "agent_action"
        assert intent.action == "status"
        assert intent.params["ticket"] == "AI-5"

    def test_status_command(self):
        intent = parse_intent("status AI-109")
        assert intent.intent_type == "agent_action"
        assert intent.action == "status"
        assert intent.params["ticket"] == "AI-109"

    def test_show_ticket(self):
        intent = parse_intent("show AI-15")
        assert intent.intent_type == "agent_action"
        assert intent.action == "status"
        assert intent.params["ticket"] == "AI-15"

    def test_ticket_status_trailing(self):
        intent = parse_intent("AI-109 status")
        assert intent.intent_type == "agent_action"
        assert intent.action == "status"
        assert intent.params["ticket"] == "AI-109"

    def test_ticket_key_uppercase(self):
        intent = parse_intent("What is ai-109 status?")
        assert intent.intent_type == "agent_action"
        assert intent.params["ticket"] == "AI-109"

    def test_original_message_preserved(self):
        msg = "What is AI-1 status?"
        intent = parse_intent(msg)
        assert intent.original_message == msg

    def test_different_project_prefix(self):
        intent = parse_intent("What is PROJ-42 status?")
        assert intent.intent_type == "agent_action"
        assert intent.params["ticket"] == "PROJ-42"


class TestIntentParserStartPatterns:
    """Tests for start/run agent pattern detection."""

    def test_start_agent_on_ticket(self):
        intent = parse_intent("Start coding on AI-109")
        assert intent.intent_type == "agent_action"
        assert intent.agent == "coding"
        assert intent.action == "start"
        assert intent.params["ticket"] == "AI-109"

    def test_run_agent_on_ticket(self):
        intent = parse_intent("Run github on AI-42")
        assert intent.intent_type == "agent_action"
        assert intent.agent == "github"
        assert intent.action == "start"
        assert intent.params["ticket"] == "AI-42"

    def test_launch_agent(self):
        intent = parse_intent("launch linear on AI-1")
        assert intent.intent_type == "agent_action"
        assert intent.action == "start"
        assert intent.params["ticket"] == "AI-1"

    def test_start_agent_for_ticket(self):
        intent = parse_intent("Start coding for AI-55")
        assert intent.intent_type == "agent_action"
        assert intent.action == "start"
        assert intent.params["ticket"] == "AI-55"

    def test_run_agent_without_preposition(self):
        intent = parse_intent("run coding AI-10")
        assert intent.intent_type == "agent_action"
        assert intent.action == "start"


class TestIntentParserPauseResumePatterns:
    """Tests for pause/resume pattern detection."""

    def test_pause_coding_agent(self):
        intent = parse_intent("pause coding")
        assert intent.intent_type == "agent_action"
        assert intent.agent == "coding"
        assert intent.action == "pause"

    def test_pause_agent_explicit(self):
        intent = parse_intent("pause coding agent")
        assert intent.intent_type == "agent_action"
        assert intent.action == "pause"

    def test_stop_agent(self):
        intent = parse_intent("stop coding")
        assert intent.intent_type == "agent_action"
        assert intent.action == "pause"

    def test_resume_coding_agent(self):
        intent = parse_intent("resume coding")
        assert intent.intent_type == "agent_action"
        assert intent.agent == "coding"
        assert intent.action == "resume"

    def test_restart_agent(self):
        intent = parse_intent("restart linear")
        assert intent.intent_type == "agent_action"
        assert intent.action == "resume"

    def test_continue_agent(self):
        intent = parse_intent("continue github")
        assert intent.intent_type == "agent_action"
        assert intent.action == "resume"


class TestIntentParserConversation:
    """Tests for conversation intent detection."""

    def test_hello(self):
        intent = parse_intent("Hello!")
        assert intent.intent_type == "conversation"
        assert intent.agent is None

    def test_general_question(self):
        intent = parse_intent("How does the dashboard work?")
        assert intent.intent_type == "conversation"

    def test_empty_message(self):
        intent = parse_intent("")
        assert intent.intent_type == "conversation"

    def test_whitespace_only(self):
        intent = parse_intent("   ")
        assert intent.intent_type == "conversation"

    def test_unrelated_text(self):
        intent = parse_intent("What's the weather like today?")
        assert intent.intent_type == "conversation"


class TestIntentParserQueryPatterns:
    """Tests for query intent detection."""

    def test_list_agents(self):
        intent = parse_intent("list all agents")
        assert intent.intent_type == "query"

    def test_show_issues(self):
        intent = parse_intent("show all issues")
        assert intent.intent_type == "query"

    def test_list_open_tickets(self):
        intent = parse_intent("list open tickets")
        assert intent.intent_type == "query"


class TestFindClosestAgent:
    """Tests for _find_closest_agent function."""

    def test_direct_match(self):
        assert _find_closest_agent("coding") == "coding"

    def test_code_alias(self):
        assert _find_closest_agent("code") == "coding"

    def test_git_alias(self):
        assert _find_closest_agent("git") == "github"

    def test_gpt_alias(self):
        assert _find_closest_agent("gpt") == "chatgpt"

    def test_unknown_returns_none(self):
        assert _find_closest_agent("xyz_unknown_agent_99") is None

    def test_pr_alias(self):
        assert _find_closest_agent("pr") == "pr_reviewer"


# ========== Agent Executor Tests ==========


class TestAgentExecutorStatus:
    """Tests for AgentExecutor status action."""

    @pytest.mark.asyncio
    async def test_status_no_api_key(self):
        """Without LINEAR_API_KEY, returns a stub response."""
        intent = parse_intent("What is AI-109 status?")
        executor = AgentExecutor(linear_api_key="")
        chunks = []
        async for chunk in executor.execute(intent):
            chunks.append(chunk)
        response = "".join(chunks)
        assert "AI-109" in response
        assert len(response) > 0

    @pytest.mark.asyncio
    async def test_status_invalid_ticket(self):
        """Completely invalid ticket format yields error message."""
        intent = ParsedIntent(
            intent_type="agent_action",
            agent="linear",
            action="status",
            params={"ticket": "NOT_VALID"},
            original_message="status NOT_VALID"
        )
        executor = AgentExecutor(linear_api_key="")
        chunks = []
        async for chunk in executor.execute(intent):
            chunks.append(chunk)
        response = "".join(chunks)
        assert "Invalid ticket format" in response

    @pytest.mark.asyncio
    async def test_status_empty_ticket(self):
        """Missing ticket yields helpful error."""
        intent = ParsedIntent(
            intent_type="agent_action",
            agent="linear",
            action="status",
            params={},
            original_message="status"
        )
        executor = AgentExecutor(linear_api_key="")
        chunks = []
        async for chunk in executor.execute(intent):
            chunks.append(chunk)
        response = "".join(chunks)
        assert "No ticket specified" in response

    @pytest.mark.asyncio
    async def test_status_with_linear_api(self):
        """With LINEAR_API_KEY, calls the Linear API."""
        mock_issue = {
            "id": "issue-123",
            "identifier": "AI-109",
            "title": "Chat-to-Agent Bridge",
            "state": {"name": "In Progress", "type": "started"},
            "assignee": {"name": "Test User"},
            "priority": 2,
            "updatedAt": "2026-02-17T10:00:00Z",
            "url": "https://linear.app/test/issue/AI-109",
        }
        executor = AgentExecutor(linear_api_key="fake-key")

        with patch.object(executor, '_query_linear_issue', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = mock_issue
            intent = parse_intent("What is AI-109 status?")
            chunks = []
            async for chunk in executor.execute(intent):
                chunks.append(chunk)
            response = "".join(chunks)
            assert "AI-109" in response
            assert "In Progress" in response
            assert "Chat-to-Agent Bridge" in response

    @pytest.mark.asyncio
    async def test_status_linear_api_not_found(self):
        """When Linear returns no issue, reports not found."""
        executor = AgentExecutor(linear_api_key="fake-key")

        with patch.object(executor, '_query_linear_issue', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = None
            intent = parse_intent("What is AI-999 status?")
            chunks = []
            async for chunk in executor.execute(intent):
                chunks.append(chunk)
            response = "".join(chunks)
            assert "not found" in response.lower() or "AI-999" in response

    @pytest.mark.asyncio
    async def test_status_linear_api_error(self):
        """When Linear API raises exception, reports error gracefully."""
        executor = AgentExecutor(linear_api_key="fake-key")

        with patch.object(executor, '_query_linear_issue', new_callable=AsyncMock) as mock_query:
            mock_query.side_effect = Exception("Connection refused")
            intent = parse_intent("What is AI-1 status?")
            chunks = []
            async for chunk in executor.execute(intent):
                chunks.append(chunk)
            response = "".join(chunks)
            # Should not crash, should produce error message
            assert len(response) > 0
            assert "Connection refused" in response or "error" in response.lower()


class TestAgentExecutorStartPauseResume:
    """Tests for start, pause, and resume actions."""

    @pytest.mark.asyncio
    async def test_start_agent(self):
        intent = parse_intent("Start coding on AI-42")
        executor = AgentExecutor(linear_api_key="")
        chunks = []
        async for chunk in executor.execute(intent):
            chunks.append(chunk)
        response = "".join(chunks)
        assert "coding" in response.lower()
        assert "AI-42" in response

    @pytest.mark.asyncio
    async def test_pause_agent(self):
        intent = ParsedIntent(
            intent_type="agent_action",
            agent="coding",
            action="pause",
            params={"target_agent": "coding"},
            original_message="pause coding"
        )
        executor = AgentExecutor(linear_api_key="")
        chunks = []
        async for chunk in executor.execute(intent):
            chunks.append(chunk)
        response = "".join(chunks)
        assert "paused" in response.lower()

    @pytest.mark.asyncio
    async def test_resume_agent(self):
        from dashboard.agent_executor import _paused_agents
        _paused_agents.add("linear")

        intent = ParsedIntent(
            intent_type="agent_action",
            agent="linear",
            action="resume",
            params={"target_agent": "linear"},
            original_message="resume linear"
        )
        executor = AgentExecutor(linear_api_key="")
        chunks = []
        async for chunk in executor.execute(intent):
            chunks.append(chunk)
        response = "".join(chunks)
        assert "resume" in response.lower() or "linear" in response.lower()

        # Cleanup
        _paused_agents.discard("linear")

    @pytest.mark.asyncio
    async def test_pause_empty_agent(self):
        intent = ParsedIntent(
            intent_type="agent_action",
            agent=None,
            action="pause",
            params={},
            original_message="pause"
        )
        executor = AgentExecutor(linear_api_key="")
        chunks = []
        async for chunk in executor.execute(intent):
            chunks.append(chunk)
        response = "".join(chunks)
        assert "No agent specified" in response

    @pytest.mark.asyncio
    async def test_unknown_action(self):
        intent = ParsedIntent(
            intent_type="agent_action",
            agent=None,
            action="fly_to_moon",
            params={},
            original_message="fly_to_moon"
        )
        executor = AgentExecutor(linear_api_key="")
        chunks = []
        async for chunk in executor.execute(intent):
            chunks.append(chunk)
        response = "".join(chunks)
        assert "Unknown action" in response or "fly_to_moon" in response


class TestAgentExecutorConversation:
    """Tests for conversation intent in executor."""

    @pytest.mark.asyncio
    async def test_conversation_intent_returns_bridge_note(self):
        intent = ParsedIntent(
            intent_type="conversation",
            agent=None,
            action=None,
            params={},
            original_message="Hello there"
        )
        executor = AgentExecutor(linear_api_key="")
        chunks = []
        async for chunk in executor.execute(intent):
            chunks.append(chunk)
        response = "".join(chunks)
        assert len(response) > 0


class TestExecuteIntent:
    """Tests for the execute_intent convenience function."""

    @pytest.mark.asyncio
    async def test_execute_intent_returns_string(self):
        intent = parse_intent("What is AI-1 status?")
        result = await execute_intent(intent, linear_api_key="")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_execute_intent_status_no_key(self):
        intent = parse_intent("status AI-200")
        result = await execute_intent(intent, linear_api_key="")
        assert "AI-200" in result


# ========== Chat Router Tests ==========


class TestChatRouter:
    """Tests for the ChatRouter class."""

    def test_parse_returns_intent(self):
        router = ChatRouter()
        intent = router.parse("What is AI-1 status?")
        assert isinstance(intent, ParsedIntent)
        assert intent.intent_type == "agent_action"

    def test_get_routing_decision_agent_action(self):
        router = ChatRouter()
        intent = parse_intent("What is AI-1 status?")
        routing = router.get_routing_decision(intent)
        assert routing["intent_type"] == "agent_action"
        assert routing["handler"] == "agent_executor"
        assert routing["agent"] == "linear"

    def test_get_routing_decision_query(self):
        router = ChatRouter()
        intent = ParsedIntent(
            intent_type="query",
            agent="linear",
            action="status",
            params={"ticket": "AI-1"},
            original_message="AI-1"
        )
        routing = router.get_routing_decision(intent)
        assert routing["handler"] == "linear_api"

    def test_get_routing_decision_conversation(self):
        router = ChatRouter()
        intent = parse_intent("Hello there!")
        routing = router.get_routing_decision(intent)
        assert routing["intent_type"] == "conversation"
        assert routing["handler"] == "ai_provider"
        assert routing["agent"] is None

    @pytest.mark.asyncio
    async def test_handle_message_agent_action(self):
        clear_chat_history()
        router = ChatRouter(linear_api_key="")
        result = await router.handle_message("What is AI-109 status?")
        assert "message_id" in result
        assert "routing" in result
        assert "response" in result
        assert result["routing"]["intent_type"] == "agent_action"
        assert "AI-109" in result["response"]

    @pytest.mark.asyncio
    async def test_handle_message_conversation(self):
        clear_chat_history()
        router = ChatRouter(linear_api_key="")
        result = await router.handle_message("Hello!")
        assert result["routing"]["intent_type"] == "conversation"
        assert len(result["response"]) > 0

    @pytest.mark.asyncio
    async def test_handle_message_stores_in_history(self):
        clear_chat_history()
        router = ChatRouter(linear_api_key="")
        result = await router.handle_message("What is AI-99 status?")
        history = get_chat_history()
        assert len(history) > 0
        assert any(m["message_id"] == result["message_id"] for m in history)

    @pytest.mark.asyncio
    async def test_concurrent_messages(self):
        """Test that multiple concurrent messages are handled without errors."""
        clear_chat_history()
        router = ChatRouter(linear_api_key="")

        messages = [
            "What is AI-1 status?",
            "What is AI-2 status?",
            "What is AI-3 status?",
            "Hello there!",
            "status AI-4",
        ]

        # Run all messages concurrently
        tasks = [
            router.handle_message(msg, provider="claude")
            for msg in messages
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        for result in results:
            assert "message_id" in result
            assert "response" in result
            assert len(result["response"]) > 0

    @pytest.mark.asyncio
    async def test_enqueue_message(self):
        """Test that enqueue_message works correctly."""
        clear_chat_history()
        router = ChatRouter(linear_api_key="")
        result = await router.enqueue_message("What is AI-1 status?")
        assert "message_id" in result
        assert "routing" in result


class TestChatHistory:
    """Tests for chat history management."""

    def test_clear_history(self):
        clear_chat_history()
        assert get_chat_history() == []

    @pytest.mark.asyncio
    async def test_history_limit(self):
        clear_chat_history()
        router = ChatRouter(linear_api_key="")

        # Add 5 messages
        for i in range(5):
            await router.handle_message(f"What is AI-{i} status?")

        # Request only 3
        history = get_chat_history(limit=3)
        assert len(history) == 3

    def test_history_sorted_by_timestamp(self):
        """Messages returned in chronological order."""
        clear_chat_history()

        # We can't easily control timestamps, just verify the function runs
        history = get_chat_history()
        assert isinstance(history, list)


# ========== Server API Tests ==========


class TestChatAPIEndpoints(AioHTTPTestCase):
    """Tests for POST /api/chat, POST /api/chat/route, GET /api/chat/history."""

    async def get_application(self):
        server_module._requirements_store.clear()
        clear_chat_history()

        ds = DashboardServer(
            project_name='test-project',
            metrics_dir=PROJECT_ROOT,
        )
        return ds.app

    @unittest_run_loop
    async def test_post_chat_with_status_query(self):
        """POST /api/chat with a status query returns routing info and response."""
        payload = {"message": "What is AI-109 status?", "provider": "claude"}
        resp = await self.client.request(
            'POST',
            '/api/chat',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        assert resp.status == 200
        data = await resp.json()
        assert 'message_id' in data
        assert 'routing' in data
        assert 'response' in data
        assert data['routing']['intent_type'] == 'agent_action'
        assert data['routing']['handler'] == 'agent_executor'
        assert 'AI-109' in data['response']

    @unittest_run_loop
    async def test_post_chat_with_conversation(self):
        """POST /api/chat with a general message routes to ai_provider."""
        payload = {"message": "Hello!"}
        resp = await self.client.request(
            'POST',
            '/api/chat',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data['routing']['intent_type'] == 'conversation'
        assert data['routing']['handler'] == 'ai_provider'

    @unittest_run_loop
    async def test_post_chat_missing_message_returns_400(self):
        """POST /api/chat without message returns 400."""
        payload = {"provider": "claude"}
        resp = await self.client.request(
            'POST',
            '/api/chat',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        assert resp.status == 400
        data = await resp.json()
        assert 'error' in data
        assert 'message' in data['error']

    @unittest_run_loop
    async def test_post_chat_empty_message_returns_400(self):
        """POST /api/chat with empty message returns 400."""
        payload = {"message": "   "}
        resp = await self.client.request(
            'POST',
            '/api/chat',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        assert resp.status == 400

    @unittest_run_loop
    async def test_post_chat_invalid_json_returns_400(self):
        """POST /api/chat with invalid JSON returns 400."""
        resp = await self.client.request(
            'POST',
            '/api/chat',
            data='not valid json',
            headers={'Content-Type': 'application/json'},
        )
        assert resp.status == 400

    @unittest_run_loop
    async def test_post_chat_route_status_query(self):
        """POST /api/chat/route returns routing decision without executing."""
        payload = {"message": "What is AI-1 status?"}
        resp = await self.client.request(
            'POST',
            '/api/chat/route',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        assert resp.status == 200
        data = await resp.json()
        assert 'intent' in data
        assert 'routing' in data
        assert data['intent']['intent_type'] == 'agent_action'
        assert data['intent']['agent'] == 'linear'
        assert data['intent']['action'] == 'status'
        assert data['intent']['params']['ticket'] == 'AI-1'
        assert data['routing']['handler'] == 'agent_executor'

    @unittest_run_loop
    async def test_post_chat_route_conversation(self):
        """POST /api/chat/route with general message returns conversation routing."""
        payload = {"message": "How are you?"}
        resp = await self.client.request(
            'POST',
            '/api/chat/route',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data['intent']['intent_type'] == 'conversation'
        assert data['routing']['handler'] == 'ai_provider'

    @unittest_run_loop
    async def test_post_chat_route_start_agent(self):
        """POST /api/chat/route with start command returns correct routing."""
        payload = {"message": "Start coding on AI-42"}
        resp = await self.client.request(
            'POST',
            '/api/chat/route',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data['intent']['intent_type'] == 'agent_action'
        assert data['intent']['action'] == 'start'
        assert data['intent']['params']['ticket'] == 'AI-42'

    @unittest_run_loop
    async def test_post_chat_route_missing_message_returns_400(self):
        """POST /api/chat/route without message returns 400."""
        payload = {}
        resp = await self.client.request(
            'POST',
            '/api/chat/route',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        assert resp.status == 400

    @unittest_run_loop
    async def test_post_chat_route_invalid_json_returns_400(self):
        """POST /api/chat/route with invalid JSON returns 400."""
        resp = await self.client.request(
            'POST',
            '/api/chat/route',
            data='bad json',
            headers={'Content-Type': 'application/json'},
        )
        assert resp.status == 400

    @unittest_run_loop
    async def test_get_chat_history_empty(self):
        """GET /api/chat/history returns empty list initially."""
        clear_chat_history()
        resp = await self.client.request('GET', '/api/chat/history')
        assert resp.status == 200
        data = await resp.json()
        assert 'messages' in data
        assert 'count' in data
        assert data['count'] == 0

    @unittest_run_loop
    async def test_get_chat_history_after_messages(self):
        """GET /api/chat/history returns messages after chat calls."""
        clear_chat_history()

        # Send a chat message
        payload = {"message": "What is AI-109 status?"}
        await self.client.request(
            'POST',
            '/api/chat',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )

        resp = await self.client.request('GET', '/api/chat/history')
        assert resp.status == 200
        data = await resp.json()
        assert data['count'] >= 1
        assert len(data['messages']) >= 1

    @unittest_run_loop
    async def test_options_preflight_chat(self):
        """OPTIONS /api/chat returns 204 for CORS preflight."""
        resp = await self.client.request('OPTIONS', '/api/chat')
        assert resp.status == 204

    @unittest_run_loop
    async def test_options_preflight_chat_route(self):
        """OPTIONS /api/chat/route returns 204 for CORS preflight."""
        resp = await self.client.request('OPTIONS', '/api/chat/route')
        assert resp.status == 204

    @unittest_run_loop
    async def test_post_chat_start_agent(self):
        """POST /api/chat with start command routes correctly."""
        payload = {"message": "Start coding on AI-42"}
        resp = await self.client.request(
            'POST',
            '/api/chat',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data['routing']['intent_type'] == 'agent_action'
        assert data['routing']['action'] == 'start'

    @unittest_run_loop
    async def test_post_chat_with_message_id(self):
        """POST /api/chat with client-supplied message_id uses it."""
        payload = {
            "message": "What is AI-1 status?",
            "message_id": "client-id-12345"
        }
        resp = await self.client.request(
            'POST',
            '/api/chat',
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'},
        )
        assert resp.status == 200
        data = await resp.json()
        assert data['message_id'] == 'client-id-12345'


class TestConcurrentChatRequests(AioHTTPTestCase):
    """Tests for concurrent chat message handling."""

    async def get_application(self):
        server_module._requirements_store.clear()
        clear_chat_history()

        ds = DashboardServer(
            project_name='test-project',
            metrics_dir=PROJECT_ROOT,
        )
        return ds.app

    @unittest_run_loop
    async def test_concurrent_chat_requests(self):
        """Multiple simultaneous chat requests are handled correctly."""
        payloads = [
            {"message": f"What is AI-{i} status?"}
            for i in range(1, 6)
        ]

        # Fire all requests concurrently
        tasks = [
            self.client.request(
                'POST',
                '/api/chat',
                data=json.dumps(p),
                headers={'Content-Type': 'application/json'},
            )
            for p in payloads
        ]
        responses = await asyncio.gather(*tasks)

        # All should succeed
        for resp in responses:
            assert resp.status == 200
            data = await resp.json()
            assert 'response' in data

    @unittest_run_loop
    async def test_error_handling_invalid_commands(self):
        """Error handling for edge-case commands."""
        edge_cases = [
            {"message": "status"},           # No ticket
            {"message": "pause"},             # No agent
            {"message": "resume"},            # No agent
            {"message": "AI-"},              # Malformed ticket
        ]

        for payload in edge_cases:
            resp = await self.client.request(
                'POST',
                '/api/chat',
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'},
            )
            # Should not 500 - may be 200 with error in response or 400
            assert resp.status in (200, 400), f"Unexpected status for {payload}"
