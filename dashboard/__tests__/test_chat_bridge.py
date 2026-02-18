"""Comprehensive tests for dashboard/chat_bridge.py (AI-173 / REQ-TECH-008).

Tests cover:
- IntentParser: recognises ask_agent, run_task, get_status, general_chat
- AgentRouter: maps intents to the correct agent name
- ChatBridge.handle_message: returns an async generator
- Response chunks have the correct format
- Graceful fallback for unknown intents
- Error handling for edge cases
"""

import asyncio
from typing import Optional
import pytest

from dashboard.chat_bridge import (
    INTENT_ASK_AGENT,
    INTENT_GENERAL_CHAT,
    INTENT_GET_STATUS,
    INTENT_RUN_TASK,
    KNOWN_AGENTS,
    AgentRouter,
    ChatBridge,
    IntentParser,
)


# ===========================================================================
# Helpers
# ===========================================================================

async def collect_chunks(generator) -> list:
    """Collect all chunks from an async generator into a list."""
    chunks = []
    async for chunk in generator:
        chunks.append(chunk)
    return chunks


# ===========================================================================
# IntentParser tests
# ===========================================================================


class TestIntentParserAskAgent:
    """Tests for ask_agent intent detection."""

    def setup_method(self):
        self.parser = IntentParser()

    def test_ask_coding_agent_explicit(self):
        result = self.parser.parse_intent("ask coding agent to implement the login feature")
        assert result["intent_type"] == INTENT_ASK_AGENT
        assert result["agent"] == "coding"
        assert result["confidence"] >= 0.8

    def test_ask_linear_agent_explicit(self):
        result = self.parser.parse_intent("ask linear agent to update ticket AI-173")
        assert result["intent_type"] == INTENT_ASK_AGENT
        assert result["agent"] == "linear"

    def test_ask_github_agent_explicit(self):
        result = self.parser.parse_intent("ask github agent to create a pull request")
        assert result["intent_type"] == INTENT_ASK_AGENT
        assert result["agent"] == "github"

    def test_ask_slack_agent_explicit(self):
        result = self.parser.parse_intent("ask slack agent to notify the channel")
        assert result["intent_type"] == INTENT_ASK_AGENT
        assert result["agent"] == "slack"

    def test_delegate_to_pattern(self):
        result = self.parser.parse_intent("delegate to coding to fix the auth bug")
        assert result["intent_type"] == INTENT_ASK_AGENT

    def test_tell_agent_pattern(self):
        result = self.parser.parse_intent("tell the coding agent to add tests")
        assert result["intent_type"] == INTENT_ASK_AGENT
        assert result["agent"] == "coding"

    def test_use_agent_pattern(self):
        result = self.parser.parse_intent("use the github agent to merge the PR")
        assert result["intent_type"] == INTENT_ASK_AGENT
        assert result["agent"] == "github"

    def test_implicit_coding_keyword(self):
        result = self.parser.parse_intent("implement the new API endpoint")
        assert result["intent_type"] == INTENT_ASK_AGENT
        assert result["agent"] == "coding"

    def test_implicit_github_create_pr(self):
        result = self.parser.parse_intent("create pr for the feature branch")
        assert result["intent_type"] == INTENT_ASK_AGENT
        assert result["agent"] == "github"

    def test_implicit_slack_send(self):
        result = self.parser.parse_intent("send slack message to the team")
        assert result["intent_type"] == INTENT_ASK_AGENT
        assert result["agent"] == "slack"

    def test_unknown_agent_in_ask_pattern(self):
        # 'robot' is not in KNOWN_AGENTS — agent should be None
        result = self.parser.parse_intent("ask robot agent to do something")
        assert result["intent_type"] == INTENT_ASK_AGENT
        assert result["agent"] is None

    def test_write_code_keyword(self):
        result = self.parser.parse_intent("write code to parse JSON files")
        assert result["intent_type"] == INTENT_ASK_AGENT
        assert result["agent"] == "coding"


class TestIntentParserRunTask:
    """Tests for run_task intent detection."""

    def setup_method(self):
        self.parser = IntentParser()

    def test_run_tests(self):
        result = self.parser.parse_intent("run tests")
        assert result["intent_type"] == INTENT_RUN_TASK
        assert result["confidence"] >= 0.8

    def test_run_pytest(self):
        result = self.parser.parse_intent("run pytest for the dashboard module")
        assert result["intent_type"] == INTENT_RUN_TASK

    def test_execute_tests(self):
        result = self.parser.parse_intent("execute tests and report results")
        assert result["intent_type"] == INTENT_RUN_TASK

    def test_run_build(self):
        result = self.parser.parse_intent("run build and package the application")
        assert result["intent_type"] == INTENT_RUN_TASK

    def test_run_linter(self):
        result = self.parser.parse_intent("run linter on all Python files")
        assert result["intent_type"] == INTENT_RUN_TASK

    def test_run_task_routes_to_coding(self):
        result = self.parser.parse_intent("run tests")
        assert result["agent"] == "coding"


class TestIntentParserGetStatus:
    """Tests for get_status intent detection."""

    def setup_method(self):
        self.parser = IntentParser()

    def test_whats_the_status(self):
        result = self.parser.parse_intent("what's the status of the agents?")
        assert result["intent_type"] == INTENT_GET_STATUS

    def test_agent_status(self):
        result = self.parser.parse_intent("show agent status")
        assert result["intent_type"] == INTENT_GET_STATUS

    def test_how_are_agents(self):
        result = self.parser.parse_intent("how are the agents doing?")
        assert result["intent_type"] == INTENT_GET_STATUS

    def test_check_status(self):
        result = self.parser.parse_intent("check status of the system")
        assert result["intent_type"] == INTENT_GET_STATUS

    def test_health_check(self):
        result = self.parser.parse_intent("health check")
        assert result["intent_type"] == INTENT_GET_STATUS

    def test_status_has_no_required_agent(self):
        result = self.parser.parse_intent("what's the status")
        assert result["intent_type"] == INTENT_GET_STATUS
        # No specific agent required for status checks
        # (agent may be None)


class TestIntentParserGeneralChat:
    """Tests for general_chat fallback."""

    def setup_method(self):
        self.parser = IntentParser()

    def test_hello_is_general_chat(self):
        result = self.parser.parse_intent("Hello there!")
        assert result["intent_type"] == INTENT_GENERAL_CHAT

    def test_question_is_general_chat(self):
        result = self.parser.parse_intent("What is the meaning of life?")
        assert result["intent_type"] == INTENT_GENERAL_CHAT

    def test_empty_string_is_general_chat(self):
        result = self.parser.parse_intent("")
        assert result["intent_type"] == INTENT_GENERAL_CHAT

    def test_none_is_general_chat(self):
        result = self.parser.parse_intent(None)  # type: ignore[arg-type]
        assert result["intent_type"] == INTENT_GENERAL_CHAT

    def test_result_has_required_keys(self):
        result = self.parser.parse_intent("hello")
        assert "intent_type" in result
        assert "agent" in result
        assert "task" in result
        assert "confidence" in result

    def test_confidence_is_float_in_range(self):
        result = self.parser.parse_intent("hello")
        assert isinstance(result["confidence"], float)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_intent_type_is_valid(self):
        from dashboard.chat_bridge import VALID_INTENT_TYPES
        for msg in ["run tests", "ask coding agent to do x", "what's the status", "hello"]:
            result = self.parser.parse_intent(msg)
            assert result["intent_type"] in VALID_INTENT_TYPES


# ===========================================================================
# AgentRouter tests
# ===========================================================================


class TestAgentRouter:
    """Tests for AgentRouter.route()."""

    def setup_method(self):
        self.parser = IntentParser()
        self.router = AgentRouter()

    def _route(self, message: str) -> Optional[str]:
        intent = self.parser.parse_intent(message)
        return self.router.route(intent)

    def test_route_ask_coding_agent(self):
        assert self._route("ask coding agent to fix the bug") == "coding"

    def test_route_ask_linear_agent(self):
        assert self._route("ask linear agent to create a ticket") == "linear"

    def test_route_ask_github_agent(self):
        assert self._route("ask github agent to open a PR") == "github"

    def test_route_ask_slack_agent(self):
        assert self._route("ask slack agent to send a message") == "slack"

    def test_route_run_task_defaults_to_coding(self):
        assert self._route("run tests") == "coding"

    def test_route_status_returns_none(self):
        # Status is handled internally, no agent delegation needed
        assert self._route("what's the status") is None

    def test_route_general_chat_returns_none(self):
        assert self._route("hello there") is None

    def test_route_none_intent(self):
        assert self.router.route(None) is None  # type: ignore[arg-type]

    def test_route_empty_dict(self):
        assert self.router.route({}) is None

    def test_route_known_agent_in_intent(self):
        intent = {
            "intent_type": INTENT_ASK_AGENT,
            "agent": "pr_reviewer",
            "task": "review the PR",
            "confidence": 0.9,
        }
        assert self.router.route(intent) == "pr_reviewer"

    def test_route_unknown_agent_in_intent(self):
        intent = {
            "intent_type": INTENT_ASK_AGENT,
            "agent": "invalid_agent_xyz",
            "task": "do something",
            "confidence": 0.9,
        }
        # Falls back to default routing for ask_agent (None)
        result = self.router.route(intent)
        assert result is None

    def test_route_all_known_agents(self):
        """Every known agent can be routed to when set explicitly in intent."""
        for agent_name in KNOWN_AGENTS:
            intent = {
                "intent_type": INTENT_ASK_AGENT,
                "agent": agent_name,
                "task": "do something",
                "confidence": 0.9,
            }
            assert self.router.route(intent) == agent_name


# ===========================================================================
# ChatBridge tests
# ===========================================================================


class TestChatBridgeHandleMessage:
    """Tests for ChatBridge.handle_message() and async generator output."""

    def setup_method(self):
        self.bridge = ChatBridge()

    @pytest.mark.asyncio
    async def test_returns_async_generator(self):
        generator = await self.bridge.handle_message("hello")
        # Should be an async iterable
        assert hasattr(generator, "__aiter__")

    @pytest.mark.asyncio
    async def test_basic_message_yields_chunks(self):
        gen = await self.bridge.handle_message("hello")
        chunks = await collect_chunks(gen)
        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_last_chunk_is_done(self):
        gen = await self.bridge.handle_message("hello")
        chunks = await collect_chunks(gen)
        assert chunks[-1]["type"] == "done"

    @pytest.mark.asyncio
    async def test_all_chunks_have_required_keys(self):
        gen = await self.bridge.handle_message("run tests")
        chunks = await collect_chunks(gen)
        for chunk in chunks:
            assert "type" in chunk
            assert "content" in chunk
            assert "metadata" in chunk
            assert "timestamp" in chunk

    @pytest.mark.asyncio
    async def test_timestamp_format(self):
        gen = await self.bridge.handle_message("hello")
        chunks = await collect_chunks(gen)
        for chunk in chunks:
            assert chunk["timestamp"].endswith("Z")

    @pytest.mark.asyncio
    async def test_intent_chunk_present(self):
        gen = await self.bridge.handle_message("ask coding agent to fix the bug")
        chunks = await collect_chunks(gen)
        intent_chunks = [c for c in chunks if c["type"] == "intent"]
        assert len(intent_chunks) == 1

    @pytest.mark.asyncio
    async def test_routing_chunk_present(self):
        gen = await self.bridge.handle_message("ask coding agent to fix the bug")
        chunks = await collect_chunks(gen)
        routing_chunks = [c for c in chunks if c["type"] == "routing"]
        assert len(routing_chunks) == 1

    @pytest.mark.asyncio
    async def test_agent_response_chunk_present(self):
        gen = await self.bridge.handle_message("ask coding agent to write a function")
        chunks = await collect_chunks(gen)
        response_chunks = [c for c in chunks if c["type"] == "agent_response"]
        assert len(response_chunks) >= 1

    @pytest.mark.asyncio
    async def test_run_task_routes_to_coding(self):
        gen = await self.bridge.handle_message("run tests please")
        chunks = await collect_chunks(gen)
        routing_chunks = [c for c in chunks if c["type"] == "routing"]
        assert len(routing_chunks) == 1
        assert "coding" in routing_chunks[0]["content"]

    @pytest.mark.asyncio
    async def test_status_query_returns_status_response(self):
        gen = await self.bridge.handle_message("what's the status of the agents?")
        chunks = await collect_chunks(gen)
        response_chunks = [c for c in chunks if c["type"] == "agent_response"]
        assert len(response_chunks) >= 1
        full_text = " ".join(c["content"] for c in response_chunks)
        assert "status" in full_text.lower() or "agent" in full_text.lower()

    @pytest.mark.asyncio
    async def test_general_chat_fallback(self):
        gen = await self.bridge.handle_message("How are you today?")
        chunks = await collect_chunks(gen)
        # Should have a fallback agent_response
        response_chunks = [c for c in chunks if c["type"] == "agent_response"]
        assert len(response_chunks) >= 1
        # Fallback metadata should indicate fallback=True
        fallback_chunks = [
            c for c in response_chunks
            if c.get("metadata", {}).get("fallback") is True
        ]
        assert len(fallback_chunks) >= 1

    @pytest.mark.asyncio
    async def test_empty_message_yields_error_chunk(self):
        gen = await self.bridge.handle_message("")
        chunks = await collect_chunks(gen)
        error_chunks = [c for c in chunks if c["type"] == "error"]
        assert len(error_chunks) >= 1

    @pytest.mark.asyncio
    async def test_none_message_yields_error_chunk(self):
        gen = await self.bridge.handle_message(None)  # type: ignore[arg-type]
        chunks = await collect_chunks(gen)
        error_chunks = [c for c in chunks if c["type"] == "error"]
        assert len(error_chunks) >= 1

    @pytest.mark.asyncio
    async def test_session_id_propagated_in_metadata(self):
        session_id = "test-session-abc123"
        gen = await self.bridge.handle_message("hello", session_id=session_id)
        chunks = await collect_chunks(gen)
        # The done chunk should include the session_id
        done_chunk = chunks[-1]
        assert done_chunk["metadata"].get("session_id") == session_id

    @pytest.mark.asyncio
    async def test_intent_metadata_in_intent_chunk(self):
        gen = await self.bridge.handle_message("ask coding agent to write tests")
        chunks = await collect_chunks(gen)
        intent_chunks = [c for c in chunks if c["type"] == "intent"]
        assert len(intent_chunks) == 1
        meta = intent_chunks[0]["metadata"]
        assert "intent_type" in meta
        assert "confidence" in meta

    @pytest.mark.asyncio
    async def test_multiple_messages_independent(self):
        """Multiple calls to handle_message are independent."""
        gen1 = await self.bridge.handle_message("run tests")
        gen2 = await self.bridge.handle_message("what's the status")
        chunks1 = await collect_chunks(gen1)
        chunks2 = await collect_chunks(gen2)
        # Both should end with 'done'
        assert chunks1[-1]["type"] == "done"
        assert chunks2[-1]["type"] == "done"
        # They should not share state
        assert chunks1 != chunks2

    @pytest.mark.asyncio
    async def test_custom_intent_parser_and_router(self):
        """ChatBridge accepts custom IntentParser and AgentRouter."""
        custom_parser = IntentParser()
        custom_router = AgentRouter()
        bridge = ChatBridge(intent_parser=custom_parser, agent_router=custom_router)
        gen = await bridge.handle_message("run tests")
        chunks = await collect_chunks(gen)
        assert chunks[-1]["type"] == "done"

    @pytest.mark.asyncio
    async def test_delegation_metadata_has_agent(self):
        """Agent delegation chunks include agent name in metadata."""
        gen = await self.bridge.handle_message("ask coding agent to refactor auth module")
        chunks = await collect_chunks(gen)
        response_chunks = [c for c in chunks if c["type"] == "agent_response"]
        assert len(response_chunks) >= 1
        # At least one response chunk should mention the agent
        agents_in_meta = [
            c["metadata"].get("agent") for c in response_chunks if "agent" in c.get("metadata", {})
        ]
        assert any(a == "coding" for a in agents_in_meta)

    @pytest.mark.asyncio
    async def test_delegation_status_in_metadata(self):
        """Delegation chunks include delegation_status in metadata."""
        gen = await self.bridge.handle_message("ask linear agent to close ticket AI-170")
        chunks = await collect_chunks(gen)
        response_chunks = [c for c in chunks if c["type"] == "agent_response"]
        statuses = [
            c["metadata"].get("delegation_status")
            for c in response_chunks
            if "delegation_status" in c.get("metadata", {})
        ]
        assert len(statuses) >= 1
        assert all(s in ("delegated", "executing") for s in statuses)

    @pytest.mark.asyncio
    async def test_chunk_type_values_are_valid(self):
        """All yielded chunk types are from a known set."""
        valid_types = {"intent", "routing", "agent_response", "error", "done", "text"}
        gen = await self.bridge.handle_message("ask coding agent to add logging")
        chunks = await collect_chunks(gen)
        for chunk in chunks:
            assert chunk["type"] in valid_types, (
                f"Unexpected chunk type: {chunk['type']}"
            )


# ===========================================================================
# Integration: ChatBridge + server post_chat_stream (smoke test)
# ===========================================================================


class TestChatBridgeIntegration:
    """Light integration tests verifying ChatBridge integrates with server state."""

    @pytest.mark.asyncio
    async def test_bridge_pipeline_order(self):
        """Verify that intent chunk precedes routing chunk which precedes response."""
        bridge = ChatBridge()
        gen = await bridge.handle_message("ask github agent to merge the PR")
        chunks = await collect_chunks(gen)

        type_sequence = [c["type"] for c in chunks]
        # intent should come before routing
        if "intent" in type_sequence and "routing" in type_sequence:
            assert type_sequence.index("intent") < type_sequence.index("routing")
        # routing should come before agent_response
        if "routing" in type_sequence and "agent_response" in type_sequence:
            assert type_sequence.index("routing") < type_sequence.index("agent_response")
        # done should always be last
        assert type_sequence[-1] == "done"

    @pytest.mark.asyncio
    async def test_bridge_handles_pr_reviewer_agent(self):
        bridge = ChatBridge()
        gen = await bridge.handle_message("ask pr_reviewer agent to review the PR")
        chunks = await collect_chunks(gen)
        # Should detect pr_reviewer even with underscore
        intent_chunks = [c for c in chunks if c["type"] == "intent"]
        assert len(intent_chunks) >= 1
        assert chunks[-1]["type"] == "done"

    @pytest.mark.asyncio
    async def test_bridge_run_task_mentions_coding(self):
        bridge = ChatBridge()
        gen = await bridge.handle_message("run all tests now")
        chunks = await collect_chunks(gen)
        all_content = " ".join(c["content"] for c in chunks)
        assert "coding" in all_content.lower()

    @pytest.mark.asyncio
    async def test_error_chunk_has_error_code_in_metadata(self):
        bridge = ChatBridge()
        gen = await bridge.handle_message("")
        chunks = await collect_chunks(gen)
        error_chunks = [c for c in chunks if c["type"] == "error"]
        for ec in error_chunks:
            assert "error_code" in ec.get("metadata", {})


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
