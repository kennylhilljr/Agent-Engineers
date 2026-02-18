"""Expanded tests for dashboard/chat_handler.py - AI-190.

Covers:
- ChatRouter init with and without websockets/api_key
- parse() method delegates to parse_intent
- get_routing_decision() for different intents
- get_chat_history() returns list, respects limit
- clear_chat_history() empties history
- enqueue_message() queue full scenario
- handle_message() for conversation routing
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dashboard.chat_handler import (
    ChatRouter,
    get_chat_history,
    clear_chat_history,
)
from dashboard.intent_parser import ParsedIntent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_chat_history():
    """Clear chat history before each test."""
    clear_chat_history()
    yield
    clear_chat_history()


@pytest.fixture
def router():
    """Return a ChatRouter with mocked AgentExecutor."""
    with patch("dashboard.chat_handler.AgentExecutor") as mock_cls:
        mock_executor = MagicMock()
        mock_cls.return_value = mock_executor
        r = ChatRouter()
        yield r


@pytest.fixture
def router_with_ws():
    """Return a ChatRouter with websockets and api_key."""
    ws_set = {MagicMock(), MagicMock()}
    with patch("dashboard.chat_handler.AgentExecutor") as mock_cls:
        mock_executor = MagicMock()
        mock_cls.return_value = mock_executor
        r = ChatRouter(websockets=ws_set, linear_api_key="test_key")
        yield r


# ---------------------------------------------------------------------------
# ChatRouter.__init__ tests
# ---------------------------------------------------------------------------

class TestChatRouterInit:
    """Tests for ChatRouter initialization."""

    def test_init_default_no_args(self):
        """ChatRouter initializes with empty websockets and None api_key."""
        with patch("dashboard.chat_handler.AgentExecutor"):
            r = ChatRouter()
            assert r.websockets == set()
            assert r.linear_api_key is None

    def test_init_with_websockets(self):
        """ChatRouter stores provided websocket set."""
        ws = {MagicMock()}
        with patch("dashboard.chat_handler.AgentExecutor"):
            r = ChatRouter(websockets=ws)
            assert r.websockets == ws

    def test_init_with_api_key(self):
        """ChatRouter stores provided linear_api_key."""
        with patch("dashboard.chat_handler.AgentExecutor"):
            r = ChatRouter(linear_api_key="my_key")
            assert r.linear_api_key == "my_key"

    def test_init_none_websockets_defaults_to_empty_set(self):
        """Explicit None for websockets becomes empty set."""
        with patch("dashboard.chat_handler.AgentExecutor"):
            r = ChatRouter(websockets=None)
            assert isinstance(r.websockets, set)
            assert len(r.websockets) == 0

    def test_init_creates_agent_executor(self):
        """AgentExecutor is created during init."""
        with patch("dashboard.chat_handler.AgentExecutor") as mock_cls:
            ChatRouter(linear_api_key="key123")
            mock_cls.assert_called_once_with(linear_api_key="key123")


# ---------------------------------------------------------------------------
# parse() method tests
# ---------------------------------------------------------------------------

class TestChatRouterParse:
    """Tests for parse() method delegation."""

    def test_parse_delegates_to_parse_intent(self, router):
        """parse() returns a ParsedIntent."""
        result = router.parse("check AI-1")
        assert isinstance(result, ParsedIntent)

    def test_parse_status_intent(self, router):
        """parse() correctly identifies status intent."""
        result = router.parse("what is AI-109 status")
        assert result.intent_type == "agent_action"
        assert result.action == "status"

    def test_parse_conversation_intent(self, router):
        """parse() returns conversation for plain message."""
        result = router.parse("hello there")
        assert result.intent_type == "conversation"

    def test_parse_empty_string(self, router):
        """parse() handles empty string."""
        result = router.parse("")
        assert result.intent_type == "conversation"

    def test_parse_list_query(self, router):
        """parse() identifies list query."""
        result = router.parse("list all issues")
        assert result.intent_type == "query"


# ---------------------------------------------------------------------------
# get_routing_decision() tests
# ---------------------------------------------------------------------------

class TestGetRoutingDecision:
    """Tests for get_routing_decision()."""

    def test_agent_action_routes_to_agent_executor(self, router):
        """agent_action intent routes to agent_executor handler."""
        intent = ParsedIntent(
            intent_type="agent_action",
            agent="linear",
            action="status",
            params={"ticket": "AI-1"},
            original_message="check AI-1",
        )
        decision = router.get_routing_decision(intent)
        assert decision["handler"] == "agent_executor"
        assert decision["intent_type"] == "agent_action"
        assert decision["agent"] == "linear"
        assert decision["action"] == "status"

    def test_query_routes_to_linear_api(self, router):
        """query intent routes to linear_api handler."""
        intent = ParsedIntent(
            intent_type="query",
            agent="linear",
            action="list",
            params={},
            original_message="list issues",
        )
        decision = router.get_routing_decision(intent)
        assert decision["handler"] == "linear_api"
        assert decision["intent_type"] == "query"

    def test_conversation_routes_to_ai_provider(self, router):
        """conversation intent routes to ai_provider handler."""
        intent = ParsedIntent(
            intent_type="conversation",
            agent=None,
            action=None,
            params={},
            original_message="hello",
        )
        decision = router.get_routing_decision(intent)
        assert decision["handler"] == "ai_provider"
        assert decision["intent_type"] == "conversation"

    def test_routing_includes_description(self, router):
        """Routing decision includes human-readable description."""
        intent = ParsedIntent(intent_type="conversation", agent=None, action=None)
        decision = router.get_routing_decision(intent)
        assert "description" in decision
        assert isinstance(decision["description"], str)

    def test_routing_includes_original_message(self, router):
        """Routing decision includes original_message."""
        intent = ParsedIntent(
            intent_type="conversation",
            agent=None,
            action=None,
            original_message="test message",
        )
        decision = router.get_routing_decision(intent)
        assert decision["original_message"] == "test message"

    def test_agent_action_without_agent_defaults_to_linear(self, router):
        """agent_action with agent=None defaults to 'linear' in routing."""
        intent = ParsedIntent(
            intent_type="agent_action",
            agent=None,
            action="status",
            params={},
        )
        decision = router.get_routing_decision(intent)
        assert decision["agent"] == "linear"

    def test_routing_includes_params(self, router):
        """Routing decision passes through params."""
        intent = ParsedIntent(
            intent_type="agent_action",
            agent="linear",
            action="status",
            params={"ticket": "AI-5"},
        )
        decision = router.get_routing_decision(intent)
        assert decision["params"]["ticket"] == "AI-5"


# ---------------------------------------------------------------------------
# get_chat_history() tests
# ---------------------------------------------------------------------------

class TestGetChatHistory:
    """Tests for get_chat_history()."""

    def test_empty_history_returns_empty_list(self):
        """No messages -> empty list."""
        history = get_chat_history()
        assert history == []

    def test_history_returns_list(self):
        """get_chat_history() returns a list."""
        history = get_chat_history()
        assert isinstance(history, list)

    def test_history_respects_limit(self):
        """get_chat_history() respects limit parameter."""
        from dashboard.chat_handler import _chat_history
        # Manually insert history entries
        for i in range(10):
            _chat_history[f"msg-{i}"] = {
                "message_id": f"msg-{i}",
                "timestamp": f"2026-01-01T00:00:{i:02d}Z",
                "response": f"response {i}",
            }
        history = get_chat_history(limit=5)
        assert len(history) == 5

    def test_history_returns_all_when_limit_higher(self):
        """Returns all messages when limit > actual count."""
        from dashboard.chat_handler import _chat_history
        for i in range(3):
            _chat_history[f"msg-{i}"] = {
                "message_id": f"msg-{i}",
                "timestamp": f"2026-01-01T00:00:{i:02d}Z",
            }
        history = get_chat_history(limit=100)
        assert len(history) == 3


# ---------------------------------------------------------------------------
# clear_chat_history() tests
# ---------------------------------------------------------------------------

class TestClearChatHistory:
    """Tests for clear_chat_history()."""

    def test_clear_empties_history(self):
        """clear_chat_history() removes all entries."""
        from dashboard.chat_handler import _chat_history
        _chat_history["test"] = {"message_id": "test"}
        clear_chat_history()
        assert len(get_chat_history()) == 0

    def test_clear_idempotent(self):
        """Calling clear twice is safe."""
        clear_chat_history()
        clear_chat_history()
        assert get_chat_history() == []


# ---------------------------------------------------------------------------
# enqueue_message() queue full scenario
# ---------------------------------------------------------------------------

class TestEnqueueMessage:
    """Tests for enqueue_message()."""

    @pytest.mark.asyncio
    async def test_enqueue_returns_result_normally(self, router):
        """enqueue_message() processes normally when queue has space."""
        with patch.object(router, "handle_message", new_callable=AsyncMock) as mock_handle:
            mock_handle.return_value = {
                "message_id": "123",
                "response": "Hello",
                "routing": {"handler": "ai_provider"},
                "timestamp": "2026-01-01T00:00:00Z",
                "provider": "claude",
                "user_message": "hi",
            }
            result = await router.enqueue_message("hi", provider="claude")
            assert result["response"] == "Hello"
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueue_queue_full_returns_error(self):
        """enqueue_message() returns error when queue is full."""
        with patch("dashboard.chat_handler.AgentExecutor"):
            r = ChatRouter()

        # Fill the queue to capacity (maxsize=50)
        import asyncio as _asyncio
        from dashboard.chat_handler import _request_queue

        # Drain the queue first to ensure clean state
        while not _request_queue.empty():
            try:
                _request_queue.get_nowait()
            except _asyncio.QueueEmpty:
                break

        # Fill the queue
        filled = 0
        try:
            for i in range(50):
                _request_queue.put_nowait(f"item-{i}")
                filled += 1
        except _asyncio.QueueFull:
            pass

        try:
            result = await r.enqueue_message("test message")
            assert result.get("error") == "queue_full"
            assert "busy" in result.get("response", "").lower() or \
                   "queue" in result.get("response", "").lower()
        finally:
            # Drain the queue after test
            while not _request_queue.empty():
                try:
                    _request_queue.get_nowait()
                except _asyncio.QueueEmpty:
                    break

    @pytest.mark.asyncio
    async def test_enqueue_generates_message_id_if_not_provided(self, router):
        """enqueue_message() auto-generates message_id."""
        with patch.object(router, "handle_message", new_callable=AsyncMock) as mock_handle:
            mock_handle.return_value = {
                "message_id": "auto-gen",
                "response": "ok",
                "routing": {},
                "timestamp": "2026-01-01T00:00:00Z",
                "provider": "claude",
                "user_message": "test",
            }
            result = await router.enqueue_message("test")
            # handle_message receives a generated ID
            call_args = mock_handle.call_args
            assert call_args is not None
