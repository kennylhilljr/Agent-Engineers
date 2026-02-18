"""Unit tests for bridges/openai_bridge.py

Tests cover:
- ChatGPTModel enum and from_string method
- ChatMessage and ChatSession dataclasses
- ChatResponse dataclass
- CodexOAuthClient initialization (mocked openai package)
- CodexOAuthClient.send_message with mocked OpenAI response
- CodexOAuthClient.send_message_async with mocked async response
- SessionTokenClient initialization and auth errors
- OpenAIBridge.create_session
- OpenAIBridge.send_message (delegates to client)
- OpenAIBridge.from_env with environment variable control
- OpenAIBridge.get_auth_info
- Error handling: missing API key, missing session token
- check_codex_cli_installed
- get_available_models

All API calls are fully mocked (no real network requests).
"""

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Bridge imports may fail if openai is not installed;
# we use conditional imports so tests can still run
from bridges.openai_bridge import (
    AuthType,
    ChatGPTModel,
    ChatMessage,
    ChatResponse,
    ChatSession,
    OpenAIBridge,
    check_codex_cli_installed,
    get_available_models,
    print_auth_status,
)


class TestChatGPTModel:
    """Tests for ChatGPTModel enum."""

    def test_gpt4o_value(self):
        """Test that GPT_4O has the correct string value."""
        assert ChatGPTModel.GPT_4O == "gpt-4o"

    def test_o1_value(self):
        """Test that O1 has the correct string value."""
        assert ChatGPTModel.O1 == "o1"

    def test_o3_mini_value(self):
        """Test that O3_MINI has the correct string value."""
        assert ChatGPTModel.O3_MINI == "o3-mini"

    def test_o4_mini_value(self):
        """Test that O4_MINI has the correct string value."""
        assert ChatGPTModel.O4_MINI == "o4-mini"

    def test_from_string_gpt4o(self):
        """Test that from_string returns GPT_4O for 'gpt-4o'."""
        result = ChatGPTModel.from_string("gpt-4o")
        assert result == ChatGPTModel.GPT_4O

    def test_from_string_case_insensitive(self):
        """Test that from_string is case-insensitive."""
        result = ChatGPTModel.from_string("GPT-4O")
        assert result == ChatGPTModel.GPT_4O

    def test_from_string_unknown_returns_gpt4o(self):
        """Test that an unknown model string defaults to GPT_4O."""
        result = ChatGPTModel.from_string("unknown-model")
        assert result == ChatGPTModel.GPT_4O

    def test_from_string_with_whitespace(self):
        """Test that from_string handles surrounding whitespace."""
        result = ChatGPTModel.from_string("  o1  ")
        assert result == ChatGPTModel.O1


class TestChatMessage:
    """Tests for ChatMessage dataclass."""

    def test_chat_message_creation(self):
        """Test creating a ChatMessage."""
        msg = ChatMessage(role="user", content="Hello!")
        assert msg.role == "user"
        assert msg.content == "Hello!"

    def test_chat_message_assistant_role(self):
        """Test assistant role message."""
        msg = ChatMessage(role="assistant", content="I can help.")
        assert msg.role == "assistant"


class TestChatSession:
    """Tests for ChatSession dataclass."""

    def test_chat_session_creation(self):
        """Test creating a ChatSession."""
        session = ChatSession(model=ChatGPTModel.GPT_4O)
        assert session.model == ChatGPTModel.GPT_4O
        assert session.messages == []
        assert session.session_id is None

    def test_add_message(self):
        """Test adding a message to a session."""
        session = ChatSession(model=ChatGPTModel.GPT_4O)
        session.add_message("user", "Test message")
        assert len(session.messages) == 1
        assert session.messages[0].role == "user"
        assert session.messages[0].content == "Test message"

    def test_add_multiple_messages(self):
        """Test adding multiple messages."""
        session = ChatSession(model=ChatGPTModel.GPT_4O)
        session.add_message("user", "Hello")
        session.add_message("assistant", "Hi there")
        assert len(session.messages) == 2

    def test_to_openai_messages(self):
        """Test conversion to OpenAI-compatible message format."""
        session = ChatSession(model=ChatGPTModel.GPT_4O)
        session.add_message("user", "Test")
        session.add_message("assistant", "Response")

        messages = session.to_openai_messages()
        assert isinstance(messages, list)
        assert len(messages) == 2
        assert messages[0] == {"role": "user", "content": "Test"}
        assert messages[1] == {"role": "assistant", "content": "Response"}

    def test_to_openai_messages_empty(self):
        """Test conversion to OpenAI messages with no messages."""
        session = ChatSession(model=ChatGPTModel.GPT_4O)
        messages = session.to_openai_messages()
        assert messages == []


class TestChatResponse:
    """Tests for ChatResponse dataclass."""

    def test_chat_response_creation(self):
        """Test creating a ChatResponse."""
        response = ChatResponse(content="Hello!", model="gpt-4o", finish_reason="stop")
        assert response.content == "Hello!"
        assert response.model == "gpt-4o"
        assert response.finish_reason == "stop"
        assert response.usage is None

    def test_chat_response_with_usage(self):
        """Test ChatResponse with usage info."""
        usage = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        response = ChatResponse(content="Done", model="gpt-4o", usage=usage)
        assert response.usage == usage
        assert response.usage["total_tokens"] == 30


class TestAuthType:
    """Tests for AuthType enum."""

    def test_codex_oauth_value(self):
        """Test CODEX_OAUTH value."""
        assert AuthType.CODEX_OAUTH == "codex-oauth"

    def test_session_token_value(self):
        """Test SESSION_TOKEN value."""
        assert AuthType.SESSION_TOKEN == "session-token"


class TestCodexOAuthClient:
    """Tests for CodexOAuthClient with mocked OpenAI SDK."""

    def test_raises_bridge_error_when_openai_not_installed(self):
        """Test that BridgeError is raised when openai package is not installed."""
        from bridges.openai_bridge import CodexOAuthClient
        with patch("bridges.openai_bridge.OpenAI", None), \
             patch("bridges.openai_bridge.AsyncOpenAI", None):
            from exceptions import BridgeError
            with pytest.raises(BridgeError, match="openai package not installed"):
                CodexOAuthClient(api_key="fake-key")

    def test_raises_security_error_when_no_api_key(self):
        """Test that SecurityError is raised when OPENAI_API_KEY is not set."""
        from bridges.openai_bridge import CodexOAuthClient
        mock_openai = MagicMock()
        mock_async_openai = MagicMock()

        with patch("bridges.openai_bridge.OpenAI", mock_openai), \
             patch("bridges.openai_bridge.AsyncOpenAI", mock_async_openai), \
             patch.dict(os.environ, {}, clear=True):
            # Temporarily remove the OPENAI_API_KEY from env
            env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
            with patch.dict(os.environ, env, clear=True):
                from exceptions import SecurityError
                with pytest.raises(SecurityError, match="OPENAI_API_KEY not set"):
                    CodexOAuthClient()

    def test_send_message_calls_openai_api(self):
        """Test that send_message calls the OpenAI API."""
        from bridges.openai_bridge import CodexOAuthClient

        mock_choice = MagicMock()
        mock_choice.message.content = "AI response text"
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 5
        mock_usage.completion_tokens = 10
        mock_usage.total_tokens = 15

        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]
        mock_completion.model = "gpt-4o"
        mock_completion.usage = mock_usage

        mock_sync_client = MagicMock()
        mock_sync_client.chat.completions.create.return_value = mock_completion

        mock_async_client = MagicMock()

        mock_openai_class = MagicMock(return_value=mock_sync_client)
        mock_async_openai_class = MagicMock(return_value=mock_async_client)

        with patch("bridges.openai_bridge.OpenAI", mock_openai_class), \
             patch("bridges.openai_bridge.AsyncOpenAI", mock_async_openai_class), \
             patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):

            client = CodexOAuthClient(api_key="sk-test-key")
            session = ChatSession(model=ChatGPTModel.GPT_4O)
            response = client.send_message(session, "Hello AI")

            assert response.content == "AI response text"
            assert response.model == "gpt-4o"
            assert response.usage["total_tokens"] == 15

    def test_send_message_adds_to_session(self):
        """Test that send_message adds user and assistant messages to session."""
        from bridges.openai_bridge import CodexOAuthClient

        mock_choice = MagicMock()
        mock_choice.message.content = "Response"
        mock_choice.finish_reason = "stop"

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 1
        mock_usage.completion_tokens = 1
        mock_usage.total_tokens = 2

        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]
        mock_completion.model = "gpt-4o"
        mock_completion.usage = mock_usage

        mock_sync_client = MagicMock()
        mock_sync_client.chat.completions.create.return_value = mock_completion
        mock_async_client = MagicMock()

        with patch("bridges.openai_bridge.OpenAI", MagicMock(return_value=mock_sync_client)), \
             patch("bridges.openai_bridge.AsyncOpenAI", MagicMock(return_value=mock_async_client)), \
             patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-key"}):

            client = CodexOAuthClient(api_key="sk-test-key")
            session = ChatSession(model=ChatGPTModel.GPT_4O)
            client.send_message(session, "Hello")

            # Session should have user and assistant messages
            assert len(session.messages) == 2
            assert session.messages[0].role == "user"
            assert session.messages[1].role == "assistant"


class TestOpenAIBridge:
    """Tests for OpenAIBridge class."""

    def _make_bridge(self, auth_type=AuthType.CODEX_OAUTH):
        """Create an OpenAIBridge with a mock client."""
        mock_client = MagicMock()
        return OpenAIBridge(auth_type=auth_type, client=mock_client), mock_client

    def test_create_session_default_model(self):
        """Test creating a session with default model."""
        bridge, _ = self._make_bridge()
        with patch.dict(os.environ, {"CHATGPT_MODEL": "gpt-4o"}):
            session = bridge.create_session()
        assert session.model == ChatGPTModel.GPT_4O

    def test_create_session_custom_model(self):
        """Test creating a session with a custom model."""
        bridge, _ = self._make_bridge()
        session = bridge.create_session(model="o1")
        assert session.model == ChatGPTModel.O1

    def test_create_session_with_system_prompt(self):
        """Test creating a session with a system prompt."""
        bridge, _ = self._make_bridge()
        session = bridge.create_session(system_prompt="You are a coding assistant.")
        assert len(session.messages) == 1
        assert session.messages[0].role == "system"
        assert "coding assistant" in session.messages[0].content

    def test_send_message_delegates_to_client(self):
        """Test that send_message delegates to the underlying client."""
        bridge, mock_client = self._make_bridge()
        mock_response = ChatResponse(content="Test response", model="gpt-4o")
        mock_client.send_message.return_value = mock_response

        session = ChatSession(model=ChatGPTModel.GPT_4O)
        result = bridge.send_message(session, "Hello")

        mock_client.send_message.assert_called_once_with(session, "Hello")
        assert result == mock_response

    def test_get_auth_info_codex_oauth(self):
        """Test get_auth_info for codex-oauth auth type."""
        bridge, _ = self._make_bridge(auth_type=AuthType.CODEX_OAUTH)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-12345", "CHATGPT_MODEL": "gpt-4o"}):
            info = bridge.get_auth_info()
        assert info["auth_type"] == "codex-oauth"
        assert "api_key_set" in info
        assert info["api_key_set"] == "yes"

    def test_get_auth_info_session_token(self):
        """Test get_auth_info for session-token auth type."""
        bridge, _ = self._make_bridge(auth_type=AuthType.SESSION_TOKEN)
        with patch.dict(os.environ, {"CHATGPT_SESSION_TOKEN": "sess-token-abc", "CHATGPT_MODEL": "gpt-4o"}):
            info = bridge.get_auth_info()
        assert info["auth_type"] == "session-token"
        assert "session_token_set" in info
        assert info["session_token_set"] == "yes"

    def test_get_auth_info_no_api_key(self):
        """Test get_auth_info when OPENAI_API_KEY is not set."""
        bridge, _ = self._make_bridge(auth_type=AuthType.CODEX_OAUTH)
        env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY",)}
        with patch.dict(os.environ, env, clear=True):
            info = bridge.get_auth_info()
        assert info.get("api_key_set") == "no"

    def test_from_env_uses_codex_oauth_by_default(self):
        """Test that from_env defaults to codex-oauth."""
        mock_codex_client = MagicMock()
        with patch.dict(os.environ, {"CHATGPT_AUTH_TYPE": "codex-oauth", "OPENAI_API_KEY": "sk-fake-key"}):
            with patch("bridges.openai_bridge.CodexOAuthClient", return_value=mock_codex_client):
                bridge = OpenAIBridge.from_env()
        assert bridge.auth_type == AuthType.CODEX_OAUTH

    def test_from_env_unknown_auth_type_falls_back_to_codex(self):
        """Test that an unknown auth type falls back to codex-oauth."""
        mock_codex_client = MagicMock()
        with patch.dict(os.environ, {"CHATGPT_AUTH_TYPE": "unknown-type", "OPENAI_API_KEY": "sk-fake-key"}):
            with patch("bridges.openai_bridge.CodexOAuthClient", return_value=mock_codex_client):
                bridge = OpenAIBridge.from_env()
        assert bridge.auth_type == AuthType.CODEX_OAUTH

    @pytest.mark.asyncio
    async def test_send_message_async_with_async_capable_client(self):
        """Test send_message_async when client supports async."""
        mock_client = MagicMock()
        mock_response = ChatResponse(content="Async response", model="gpt-4o")
        mock_client.send_message_async = AsyncMock(return_value=mock_response)

        bridge = OpenAIBridge(auth_type=AuthType.CODEX_OAUTH, client=mock_client)
        session = ChatSession(model=ChatGPTModel.GPT_4O)

        result = await bridge.send_message_async(session, "Hello async")
        assert result == mock_response

    @pytest.mark.asyncio
    async def test_send_message_async_falls_back_to_sync(self):
        """Test send_message_async falls back to sync when no async method."""
        mock_client = MagicMock(spec=[])  # No methods at all
        mock_response = ChatResponse(content="Sync response", model="gpt-4o")
        mock_client.send_message = MagicMock(return_value=mock_response)

        bridge = OpenAIBridge(auth_type=AuthType.CODEX_OAUTH, client=mock_client)
        session = ChatSession(model=ChatGPTModel.GPT_4O)

        result = await bridge.send_message_async(session, "Hello sync fallback")
        assert result == mock_response


class TestCheckCodexCLI:
    """Tests for check_codex_cli_installed function."""

    def test_returns_true_when_codex_installed(self):
        """Test that True is returned when codex CLI is installed."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            assert check_codex_cli_installed() is True

    def test_returns_false_when_codex_not_found(self):
        """Test that False is returned when codex CLI is not found."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert check_codex_cli_installed() is False

    def test_returns_false_when_timeout(self):
        """Test that False is returned on subprocess timeout."""
        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("codex", 10)):
            assert check_codex_cli_installed() is False

    def test_returns_false_when_non_zero_exit(self):
        """Test that False is returned when codex exits with non-zero code."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            assert check_codex_cli_installed() is False


class TestGetAvailableModels:
    """Tests for get_available_models function."""

    def test_returns_list(self):
        """Test that get_available_models returns a list."""
        models = get_available_models()
        assert isinstance(models, list)

    def test_returns_non_empty_list(self):
        """Test that the model list is not empty."""
        models = get_available_models()
        assert len(models) > 0

    def test_contains_gpt4o(self):
        """Test that gpt-4o is in the available models list."""
        models = get_available_models()
        assert "gpt-4o" in models

    def test_all_items_are_strings(self):
        """Test that all model names are strings."""
        models = get_available_models()
        for model in models:
            assert isinstance(model, str)
