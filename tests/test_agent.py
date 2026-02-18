"""Unit tests for the agent session logic in agent.py

Tests cover:
- SessionResult NamedTuple creation and fields
- run_agent_session with mocked Claude SDK client
- run_agent_session error handling (ConnectionError, TimeoutError, generic Exception)
- COMPLETION_SIGNAL detection in response text
- broadcast_agent_status behavior (with and without WebSocket)
- run_autonomous_agent validation (max_iterations < 1)
- Session status constants
- extract_ticket_key: ticket key extraction from session response text (TD-001 / AI-231)

All external dependencies (ClaudeSDKClient, WebSocket) are fully mocked.
"""

import asyncio
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import constants and types that don't require external deps
from agent import (
    COMPLETION_SIGNAL,
    SESSION_COMPLETE,
    SESSION_CONTINUE,
    SESSION_ERROR,
    TICKET_KEY_PATTERN,
    SessionResult,
    broadcast_agent_status,
    extract_ticket_key,
    run_agent_session,
)


class TestSessionResult:
    """Tests for the SessionResult NamedTuple."""

    def test_session_result_creation(self):
        """Test that SessionResult can be created with status and response."""
        result = SessionResult(status=SESSION_CONTINUE, response="Hello from agent")
        assert result.status == SESSION_CONTINUE
        assert result.response == "Hello from agent"

    def test_session_result_error_status(self):
        """Test SessionResult with error status."""
        result = SessionResult(status=SESSION_ERROR, response="Something went wrong")
        assert result.status == SESSION_ERROR
        assert result.response == "Something went wrong"

    def test_session_result_complete_status(self):
        """Test SessionResult with complete status."""
        result = SessionResult(status=SESSION_COMPLETE, response=f"{COMPLETION_SIGNAL} Done!")
        assert result.status == SESSION_COMPLETE

    def test_session_result_is_immutable(self):
        """Test that SessionResult is a NamedTuple and immutable."""
        result = SessionResult(status=SESSION_CONTINUE, response="test")
        with pytest.raises(AttributeError):
            result.status = SESSION_ERROR  # type: ignore

    def test_session_result_fields(self):
        """Test that SessionResult has exactly status and response fields."""
        result = SessionResult(status=SESSION_CONTINUE, response="text")
        assert hasattr(result, "status")
        assert hasattr(result, "response")


class TestSessionStatusConstants:
    """Tests for the session status constants."""

    def test_session_continue_value(self):
        """Test that SESSION_CONTINUE is 'continue'."""
        assert SESSION_CONTINUE == "continue"

    def test_session_error_value(self):
        """Test that SESSION_ERROR is 'error'."""
        assert SESSION_ERROR == "error"

    def test_session_complete_value(self):
        """Test that SESSION_COMPLETE is 'complete'."""
        assert SESSION_COMPLETE == "complete"

    def test_completion_signal_is_string(self):
        """Test that COMPLETION_SIGNAL is a non-empty string."""
        assert isinstance(COMPLETION_SIGNAL, str)
        assert len(COMPLETION_SIGNAL) > 0


class TestBroadcastAgentStatus:
    """Tests for broadcast_agent_status function."""

    @pytest.mark.asyncio
    async def test_broadcast_does_nothing_when_websocket_unavailable(self):
        """Test that broadcast_agent_status is a no-op when WebSocket is not available."""
        with patch("agent.WEBSOCKET_AVAILABLE", False):
            # Should complete without error
            await broadcast_agent_status("test-agent", "running")

    @pytest.mark.asyncio
    async def test_broadcast_does_nothing_when_server_is_none(self):
        """Test that broadcast is a no-op when _websocket_server is None."""
        with patch("agent.WEBSOCKET_AVAILABLE", True), patch("agent._websocket_server", None):
            await broadcast_agent_status("test-agent", "idle")

    @pytest.mark.asyncio
    async def test_broadcast_calls_server_when_available(self):
        """Test that broadcast calls the WebSocket server when available."""
        mock_server = AsyncMock()
        mock_server.broadcast_agent_status = AsyncMock()

        with patch("agent.WEBSOCKET_AVAILABLE", True), patch("agent._websocket_server", mock_server):
            await broadcast_agent_status("coding", "running", {"ticket_key": "AI-1"})
            mock_server.broadcast_agent_status.assert_called_once_with(
                agent_name="coding",
                status="running",
                metadata={"ticket_key": "AI-1"}
            )

    @pytest.mark.asyncio
    async def test_broadcast_handles_server_exception_gracefully(self):
        """Test that broadcast_agent_status swallows exceptions from the server."""
        mock_server = AsyncMock()
        mock_server.broadcast_agent_status = AsyncMock(side_effect=RuntimeError("WS error"))

        with patch("agent.WEBSOCKET_AVAILABLE", True), patch("agent._websocket_server", mock_server):
            # Should not raise
            await broadcast_agent_status("agent", "error")

    @pytest.mark.asyncio
    async def test_broadcast_with_none_metadata_uses_empty_dict(self):
        """Test that None metadata is converted to empty dict."""
        mock_server = AsyncMock()
        mock_server.broadcast_agent_status = AsyncMock()

        with patch("agent.WEBSOCKET_AVAILABLE", True), patch("agent._websocket_server", mock_server):
            await broadcast_agent_status("agent", "idle", None)
            call_kwargs = mock_server.broadcast_agent_status.call_args[1]
            assert call_kwargs["metadata"] == {}


class TestRunAgentSession:
    """Tests for run_agent_session coroutine."""

    def setup_method(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_returns_continue_on_normal_response(self):
        """Test that SESSION_CONTINUE is returned for a normal response."""
        from claude_agent_sdk import AssistantMessage, TextBlock

        text_block = Mock(spec=TextBlock)
        text_block.text = "Normal agent response"

        assistant_msg = Mock(spec=AssistantMessage)
        assistant_msg.content = [text_block]

        async def _async_iter():
            yield assistant_msg

        mock_client = AsyncMock()
        mock_client.query = AsyncMock()
        mock_client.receive_response = MagicMock(return_value=_async_iter())

        with patch("agent.broadcast_agent_status", new=AsyncMock()):
            result = await run_agent_session(mock_client, "Do something", self.temp_dir)

        assert result.status == SESSION_CONTINUE
        assert "Normal agent response" in result.response

    @pytest.mark.asyncio
    async def test_returns_complete_when_completion_signal_present(self):
        """Test that SESSION_COMPLETE is returned when COMPLETION_SIGNAL is in response."""
        from claude_agent_sdk import AssistantMessage, TextBlock

        text_block = Mock(spec=TextBlock)
        text_block.text = f"{COMPLETION_SIGNAL} All features implemented."

        assistant_msg = Mock(spec=AssistantMessage)
        assistant_msg.content = [text_block]

        async def _async_iter():
            yield assistant_msg

        mock_client = AsyncMock()
        mock_client.query = AsyncMock()
        mock_client.receive_response = MagicMock(return_value=_async_iter())

        with patch("agent.broadcast_agent_status", new=AsyncMock()):
            result = await run_agent_session(mock_client, "Continue", self.temp_dir)

        assert result.status == SESSION_COMPLETE
        assert COMPLETION_SIGNAL in result.response

    @pytest.mark.asyncio
    async def test_returns_error_on_connection_error(self):
        """Test that SESSION_ERROR is returned on ConnectionError."""
        mock_client = AsyncMock()
        mock_client.query = AsyncMock(side_effect=ConnectionError("Network failed"))

        with patch("agent.broadcast_agent_status", new=AsyncMock()):
            result = await run_agent_session(mock_client, "Test task", self.temp_dir)

        assert result.status == SESSION_ERROR
        assert "Network failed" in result.response

    @pytest.mark.asyncio
    async def test_returns_error_on_timeout_error(self):
        """Test that SESSION_ERROR is returned on TimeoutError."""
        mock_client = AsyncMock()
        mock_client.query = AsyncMock(side_effect=TimeoutError("Request timed out"))

        with patch("agent.broadcast_agent_status", new=AsyncMock()):
            result = await run_agent_session(mock_client, "Test task", self.temp_dir)

        assert result.status == SESSION_ERROR

    @pytest.mark.asyncio
    async def test_returns_error_on_generic_exception(self):
        """Test that SESSION_ERROR is returned on any unexpected exception."""
        mock_client = AsyncMock()
        mock_client.query = AsyncMock(side_effect=RuntimeError("Unexpected failure"))

        with patch("agent.broadcast_agent_status", new=AsyncMock()):
            result = await run_agent_session(mock_client, "Test task", self.temp_dir)

        assert result.status == SESSION_ERROR
        assert "Unexpected failure" in result.response

    @pytest.mark.asyncio
    async def test_agent_name_passed_to_broadcast(self):
        """Test that the agent_name is passed to broadcast calls."""
        from claude_agent_sdk import AssistantMessage, TextBlock

        text_block = Mock(spec=TextBlock)
        text_block.text = "Done"

        assistant_msg = Mock(spec=AssistantMessage)
        assistant_msg.content = [text_block]

        async def _async_iter():
            yield assistant_msg

        mock_client = AsyncMock()
        mock_client.query = AsyncMock()
        mock_client.receive_response = MagicMock(return_value=_async_iter())

        broadcast_calls = []

        async def mock_broadcast(agent_name, status, metadata=None):
            broadcast_calls.append((agent_name, status, metadata))

        with patch("agent.broadcast_agent_status", new=mock_broadcast):
            await run_agent_session(
                mock_client, "task", self.temp_dir, agent_name="coding-agent"
            )

        # First call should be with "running"
        assert broadcast_calls[0][0] == "coding-agent"
        assert broadcast_calls[0][1] == "running"

    @pytest.mark.asyncio
    async def test_empty_response_returns_continue(self):
        """Test that an empty response still returns SESSION_CONTINUE."""
        async def _empty_iter():
            return
            yield  # Make it an async generator

        mock_client = AsyncMock()
        mock_client.query = AsyncMock()
        mock_client.receive_response = MagicMock(return_value=_empty_iter())

        with patch("agent.broadcast_agent_status", new=AsyncMock()):
            result = await run_agent_session(mock_client, "task", self.temp_dir)

        assert result.status == SESSION_CONTINUE
        assert result.response == ""


class TestRunAutonomousAgentValidation:
    """Tests for run_autonomous_agent input validation."""

    def setup_method(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_raises_value_error_for_zero_max_iterations(self):
        """Test that ValueError is raised when max_iterations is 0."""
        from agent import run_autonomous_agent

        with pytest.raises(ValueError, match="max_iterations must be positive"):
            await run_autonomous_agent(
                self.temp_dir, "claude-3-5-sonnet-latest", max_iterations=0
            )

    @pytest.mark.asyncio
    async def test_raises_value_error_for_negative_max_iterations(self):
        """Test that ValueError is raised when max_iterations is negative."""
        from agent import run_autonomous_agent

        with pytest.raises(ValueError, match="max_iterations must be positive"):
            await run_autonomous_agent(
                self.temp_dir, "claude-3-5-sonnet-latest", max_iterations=-5
            )


class TestExtractTicketKey:
    """Tests for the extract_ticket_key() helper (TD-001 / AI-231)."""

    # ------------------------------------------------------------------
    # Happy-path tests
    # ------------------------------------------------------------------

    def test_happy_path_extracts_key(self):
        """Happy path: 'PROJECT_TICKET: AI-123' yields 'AI-123'."""
        assert extract_ticket_key("PROJECT_TICKET: AI-123") == "AI-123"

    def test_happy_path_key_embedded_in_longer_text(self):
        """Key embedded mid-sentence is still extracted."""
        text = "Starting work on PROJECT_TICKET: AI-42 for the feature."
        assert extract_ticket_key(text) == "AI-42"

    def test_happy_path_key_at_end_of_text(self):
        """Key at the end of the response is extracted."""
        assert extract_ticket_key("All done. PROJECT_TICKET: ENG-999") == "ENG-999"

    def test_happy_path_key_at_start_of_text(self):
        """Key at the very start of the response is extracted."""
        assert extract_ticket_key("PROJECT_TICKET: XYZ-1 is being processed.") == "XYZ-1"

    def test_happy_path_multiline_text(self):
        """Key found in a multi-line response string."""
        text = "Checking Linear.\nPROJECT_TICKET: AI-231\nImplementing fix."
        assert extract_ticket_key(text) == "AI-231"

    def test_happy_path_extra_whitespace_after_colon(self):
        """Extra whitespace between colon and key is tolerated."""
        assert extract_ticket_key("PROJECT_TICKET:   AI-55") == "AI-55"

    def test_happy_path_no_space_after_colon(self):
        """No whitespace between colon and key is tolerated."""
        assert extract_ticket_key("PROJECT_TICKET:AI-7") == "AI-7"

    # ------------------------------------------------------------------
    # Multiple ticket mentions — documents that the FIRST match is used
    # ------------------------------------------------------------------

    def test_multiple_mentions_returns_first(self):
        """When multiple PROJECT_TICKET patterns appear, the first one is returned."""
        text = "PROJECT_TICKET: AI-10 ... later PROJECT_TICKET: AI-20"
        assert extract_ticket_key(text) == "AI-10"

    def test_multiple_mentions_documents_first_not_last(self):
        """Explicitly assert first-match semantics (not last)."""
        text = "PROJECT_TICKET: AI-1\nPROJECT_TICKET: AI-2\nPROJECT_TICKET: AI-3"
        result = extract_ticket_key(text)
        assert result == "AI-1"
        assert result != "AI-3"

    # ------------------------------------------------------------------
    # Missing pattern — graceful fallback to None
    # ------------------------------------------------------------------

    def test_missing_pattern_returns_none(self):
        """Response without pattern returns None."""
        assert extract_ticket_key("No ticket information here.") is None

    def test_empty_string_returns_none(self):
        """Empty string returns None without raising."""
        assert extract_ticket_key("") is None

    def test_whitespace_only_returns_none(self):
        """Whitespace-only string returns None."""
        assert extract_ticket_key("   \n\t  ") is None

    # ------------------------------------------------------------------
    # Malformed patterns — fall back gracefully
    # ------------------------------------------------------------------

    def test_malformed_no_key_after_colon(self):
        """'PROJECT_TICKET:' with nothing after it returns None."""
        assert extract_ticket_key("PROJECT_TICKET: ") is None

    def test_malformed_lowercase_prefix_not_matched(self):
        """Lowercase 'project_ticket:' does NOT match (pattern is case-sensitive)."""
        assert extract_ticket_key("project_ticket: ai-123") is None

    def test_malformed_missing_dash_in_key(self):
        """'PROJECT_TICKET: AI123' (no dash) does not match."""
        assert extract_ticket_key("PROJECT_TICKET: AI123") is None

    def test_malformed_numeric_prefix_not_matched(self):
        """'PROJECT_TICKET: 123-456' (numeric prefix) does not match."""
        assert extract_ticket_key("PROJECT_TICKET: 123-456") is None

    def test_malformed_partial_signal_not_matched(self):
        """Partial signal 'TICKET: AI-1' (no 'PROJECT_') does not match."""
        assert extract_ticket_key("TICKET: AI-1") is None

    def test_malformed_none_input(self):
        """Passing None (as wrong type) does not raise — handled by falsy check."""
        # extract_ticket_key checks 'if not text' — None is falsy
        assert extract_ticket_key(None) is None  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Daemon-path regression: ticket_key already known must not be clobbered
    # ------------------------------------------------------------------

    def test_daemon_path_ticket_key_not_clobbered(self):
        """
        In the daemon path ticket_key is pre-assigned before run_agent_session
        is called.  The 'effective_ticket_key = ticket_key or extracted_key'
        logic means a pre-assigned non-None key wins over the extracted one.
        This test verifies that precedence at the logic level.
        """
        pre_assigned = "AI-999"
        extracted = extract_ticket_key("PROJECT_TICKET: AI-001")
        effective = pre_assigned or extracted
        assert effective == "AI-999"  # pre-assigned wins

    # ------------------------------------------------------------------
    # Pattern constant sanity checks
    # ------------------------------------------------------------------

    def test_ticket_key_pattern_is_compiled_regex(self):
        """TICKET_KEY_PATTERN must be a compiled re.Pattern object."""
        import re
        assert isinstance(TICKET_KEY_PATTERN, re.Pattern)

    def test_ticket_key_pattern_matches_expected_format(self):
        """TICKET_KEY_PATTERN directly matches 'PROJECT_TICKET: AI-123'."""
        m = TICKET_KEY_PATTERN.search("PROJECT_TICKET: AI-123")
        assert m is not None
        assert m.group(1) == "AI-123"


class TestRunAgentSessionTicketKeyExtraction:
    """Integration tests: ticket key extraction inside run_agent_session (TD-001)."""

    def setup_method(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_session_broadcasts_extracted_ticket_key(self):
        """When response contains PROJECT_TICKET:, broadcast is called with that key."""
        from claude_agent_sdk import AssistantMessage, TextBlock

        text_block = Mock(spec=TextBlock)
        text_block.text = "Starting. PROJECT_TICKET: AI-231 is the target ticket."

        assistant_msg = Mock(spec=AssistantMessage)
        assistant_msg.content = [text_block]

        async def _async_iter():
            yield assistant_msg

        mock_client = AsyncMock()
        mock_client.query = AsyncMock()
        mock_client.receive_response = MagicMock(return_value=_async_iter())

        broadcast_calls = []

        async def mock_broadcast(agent_name, status, metadata=None):
            broadcast_calls.append({"agent_name": agent_name, "status": status, "metadata": metadata or {}})

        with patch("agent.broadcast_agent_status", new=mock_broadcast):
            result = await run_agent_session(
                mock_client, "do work", self.temp_dir,
                agent_name="coding", ticket_key=None
            )

        assert result.status == SESSION_CONTINUE
        # At least one broadcast call must carry the extracted ticket key
        ticket_broadcast = [c for c in broadcast_calls if c["metadata"].get("ticket_key") == "AI-231"]
        assert len(ticket_broadcast) >= 1, (
            "Expected at least one broadcast with ticket_key='AI-231', "
            f"got calls: {broadcast_calls}"
        )

    @pytest.mark.asyncio
    async def test_session_without_ticket_pattern_broadcasts_no_key(self):
        """When response has no PROJECT_TICKET pattern, no ticket key is broadcast."""
        from claude_agent_sdk import AssistantMessage, TextBlock

        text_block = Mock(spec=TextBlock)
        text_block.text = "Normal response with no ticket reference."

        assistant_msg = Mock(spec=AssistantMessage)
        assistant_msg.content = [text_block]

        async def _async_iter():
            yield assistant_msg

        mock_client = AsyncMock()
        mock_client.query = AsyncMock()
        mock_client.receive_response = MagicMock(return_value=_async_iter())

        broadcast_calls = []

        async def mock_broadcast(agent_name, status, metadata=None):
            broadcast_calls.append({"agent_name": agent_name, "status": status, "metadata": metadata or {}})

        with patch("agent.broadcast_agent_status", new=mock_broadcast):
            result = await run_agent_session(
                mock_client, "do work", self.temp_dir,
                agent_name="coding", ticket_key=None
            )

        assert result.status == SESSION_CONTINUE
        # No broadcast should carry a ticket_key at all
        ticket_broadcasts = [c for c in broadcast_calls if "ticket_key" in c["metadata"]]
        assert len(ticket_broadcasts) == 0, (
            f"Expected no ticket_key in broadcasts, got: {broadcast_calls}"
        )

    @pytest.mark.asyncio
    async def test_daemon_path_ticket_key_not_overridden_by_response(self):
        """Pre-assigned ticket_key from daemon path is not overridden by response text."""
        from claude_agent_sdk import AssistantMessage, TextBlock

        text_block = Mock(spec=TextBlock)
        # Response tries to emit a different ticket key
        text_block.text = "Working. PROJECT_TICKET: AI-001 mentioned in response."

        assistant_msg = Mock(spec=AssistantMessage)
        assistant_msg.content = [text_block]

        async def _async_iter():
            yield assistant_msg

        mock_client = AsyncMock()
        mock_client.query = AsyncMock()
        mock_client.receive_response = MagicMock(return_value=_async_iter())

        broadcast_calls = []

        async def mock_broadcast(agent_name, status, metadata=None):
            broadcast_calls.append({"agent_name": agent_name, "status": status, "metadata": metadata or {}})

        with patch("agent.broadcast_agent_status", new=mock_broadcast):
            result = await run_agent_session(
                mock_client, "do work", self.temp_dir,
                agent_name="coding",
                ticket_key="AI-999"  # Pre-assigned (daemon path)
            )

        assert result.status == SESSION_CONTINUE
        # The pre-assigned "AI-999" must appear, not "AI-001" from response
        # No extra "running" broadcast for the extracted key (ticket_key was already set)
        running_broadcasts_without_preassigned = [
            c for c in broadcast_calls
            if c["status"] == "running" and c["metadata"].get("ticket_key") == "AI-001"
        ]
        assert len(running_broadcasts_without_preassigned) == 0, (
            "Daemon path pre-assigned key should not be overridden by extracted key"
        )
        # The final idle broadcast should use the pre-assigned key
        idle_broadcasts = [c for c in broadcast_calls if c["status"] == "idle"]
        assert any(c["metadata"].get("ticket_key") == "AI-999" for c in idle_broadcasts), (
            f"Expected idle broadcast with pre-assigned key AI-999, got: {broadcast_calls}"
        )
