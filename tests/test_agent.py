"""Unit tests for the agent session logic in agent.py

Tests cover:
- SessionResult NamedTuple creation and fields
- run_agent_session with mocked Claude SDK client
- run_agent_session error handling (ConnectionError, TimeoutError, generic Exception)
- COMPLETION_SIGNAL detection in response text
- broadcast_agent_status behavior (with and without WebSocket)
- run_autonomous_agent validation (max_iterations < 1)
- Session status constants

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
    SessionResult,
    broadcast_agent_status,
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
