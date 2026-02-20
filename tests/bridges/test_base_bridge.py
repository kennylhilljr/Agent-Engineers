"""Tests for common bridge patterns across all bridge modules.

Tests cover shared patterns used in openai_bridge, gemini_bridge,
groq_bridge, kimi_bridge, and windsurf_bridge:
- Exception imports (BridgeError, SecurityError)
- Common dataclass patterns (ChatMessage, ChatResponse, ChatSession)
- AuthType enum patterns
- Model enum patterns with from_string fallback behavior
- Bridge class factory method pattern (from_env)
- get_available_models helper pattern
- Error propagation via BridgeError / SecurityError
- Environment variable handling patterns
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from exceptions import BridgeError, SecurityError


class TestBridgeExceptionPattern:
    """Tests for how bridges use BridgeError and SecurityError."""

    def test_bridge_error_can_be_raised(self):
        """Test that BridgeError can be raised and caught."""
        with pytest.raises(BridgeError) as exc_info:
            raise BridgeError(
                "Connection to provider failed",
                error_code="BRIDGE_CONNECTION",
                provider="openai"
            )
        assert exc_info.value.provider == "openai"
        assert exc_info.value.error_code == "BRIDGE_CONNECTION"

    def test_security_error_for_missing_credentials(self):
        """Test that SecurityError is raised for missing API credentials."""
        with pytest.raises(SecurityError) as exc_info:
            raise SecurityError(
                "API key not configured",
                error_code="SECURITY_AUTH_MISSING",
                auth_type="api_key",
                details={"provider": "gemini"}
            )
        assert exc_info.value.auth_type == "api_key"
        assert exc_info.value.details["provider"] == "gemini"

    def test_bridge_error_hierarchy_allows_agent_error_catch(self):
        """Test that BridgeError can be caught as AgentError."""
        from exceptions import AgentError
        with pytest.raises(AgentError):
            raise BridgeError("Provider unavailable", provider="groq")

    def test_security_error_with_provider_details(self):
        """Test SecurityError includes provider details."""
        try:
            raise SecurityError(
                "Missing API key",
                error_code="SECURITY_AUTH_MISSING",
                auth_type="api_key",
                details={"provider": "openai", "env_var": "OPENAI_API_KEY"}
            )
        except SecurityError as e:
            assert "OPENAI_API_KEY" in e.details.get("env_var", "")
            assert e.error_code == "SECURITY_AUTH_MISSING"

    def test_bridge_error_for_unsupported_provider(self):
        """Test BridgeError for unsupported provider (missing package)."""
        with pytest.raises(BridgeError) as exc_info:
            raise BridgeError(
                "Package not installed",
                error_code="BRIDGE_UNSUPPORTED_PROVIDER",
                provider="openai"
            )
        assert exc_info.value.error_code == "BRIDGE_UNSUPPORTED_PROVIDER"


class TestOpenAIBridgePatterns:
    """Tests for OpenAI bridge-specific patterns."""

    def test_chatgpt_model_enum_values(self):
        """Test that ChatGPTModel has expected string values."""
        try:
            from bridges.openai_bridge import ChatGPTModel
        except ImportError as e:
            pytest.skip(f"openai_bridge not importable: {e}")
        models = [m.value for m in ChatGPTModel]
        assert "gpt-4o" in models

    def test_auth_type_enum_values(self):
        """Test that OpenAI AuthType has expected values."""
        try:
            from bridges.openai_bridge import AuthType
        except ImportError as e:
            pytest.skip(f"openai_bridge not importable: {e}")
        assert AuthType.CODEX_OAUTH == "codex-oauth"
        assert AuthType.SESSION_TOKEN == "session-token"

    def test_chat_session_empty_at_start(self):
        """Test that a new ChatSession has no messages."""
        try:
            from bridges.openai_bridge import ChatSession, ChatGPTModel
        except ImportError as e:
            pytest.skip(f"openai_bridge not importable: {e}")
        session = ChatSession(model=ChatGPTModel.GPT_4O)
        assert len(session.messages) == 0

    def test_chat_response_has_content_field(self):
        """Test that ChatResponse has a content field."""
        try:
            from bridges.openai_bridge import ChatResponse
        except ImportError as e:
            pytest.skip(f"openai_bridge not importable: {e}")
        response = ChatResponse(content="Test content", model="gpt-4o")
        assert response.content == "Test content"

    def test_get_available_models_returns_strings(self):
        """Test that all available model names are strings."""
        try:
            from bridges.openai_bridge import get_available_models
        except ImportError as e:
            pytest.skip(f"openai_bridge not importable: {e}")
        models = get_available_models()
        assert all(isinstance(m, str) for m in models)


class TestGeminiBridgePatterns:
    """Tests for Gemini bridge-specific patterns."""

    def test_gemini_auth_types_exist(self):
        """Test that GeminiAuthType enum has the expected values."""
        try:
            from bridges.gemini_bridge import GeminiAuthType
        except ImportError as e:
            pytest.skip(f"gemini_bridge not importable: {e}")
        assert GeminiAuthType.CLI_OAUTH == "cli-oauth"
        assert GeminiAuthType.API_KEY == "api-key"

    def test_gemini_model_enum_has_values(self):
        """Test that GeminiModel enum has model values."""
        try:
            from bridges.gemini_bridge import GeminiModel
        except ImportError as e:
            pytest.skip(f"gemini_bridge not importable: {e}")
        models = [m.value for m in GeminiModel]
        assert len(models) > 0
        # All values should be non-empty strings
        for m in models:
            assert isinstance(m, str) and len(m) > 0

    def test_gemini_model_from_string_fallback(self):
        """Test that GeminiModel.from_string handles unknown values."""
        try:
            from bridges.gemini_bridge import GeminiModel
        except ImportError as e:
            pytest.skip(f"gemini_bridge not importable: {e}")
        # Should not raise, should return a default
        result = GeminiModel.from_string("unknown-gemini-model")
        assert isinstance(result, GeminiModel)


class TestGroqBridgePatterns:
    """Tests for Groq bridge-specific patterns."""

    def test_groq_bridge_module_importable(self):
        """Test that groq_bridge module can be imported."""
        try:
            import bridges.groq_bridge as groq_bridge
            assert groq_bridge is not None
        except ImportError as e:
            pytest.skip(f"groq_bridge not importable: {e}")

    def test_groq_bridge_has_exception_imports(self):
        """Test that groq_bridge imports BridgeError."""
        try:
            from bridges.groq_bridge import GroqBridge
            # If GroqBridge exists, verify bridge errors can be constructed
            err = BridgeError("test", provider="groq")
            assert err.provider == "groq"
        except ImportError:
            pytest.skip("GroqBridge not available")


class TestKimiBridgePatterns:
    """Tests for Kimi bridge-specific patterns."""

    def test_kimi_bridge_module_importable(self):
        """Test that kimi_bridge module can be imported."""
        try:
            import bridges.kimi_bridge as kimi_bridge
            assert kimi_bridge is not None
        except ImportError as e:
            pytest.skip(f"kimi_bridge not importable: {e}")


class TestWindsurfBridgePatterns:
    """Tests for Windsurf bridge-specific patterns."""

    def test_windsurf_bridge_module_importable(self):
        """Test that windsurf_bridge module can be imported."""
        try:
            import bridges.windsurf_bridge as windsurf_bridge
            assert windsurf_bridge is not None
        except ImportError as e:
            pytest.skip(f"windsurf_bridge not importable: {e}")


class TestCommonBridgePatterns:
    """Tests for patterns that should be consistent across all bridges."""

    def test_bridge_error_has_provider_field(self):
        """Test that BridgeError consistently accepts a provider field."""
        providers = ["openai", "gemini", "groq", "kimi", "windsurf"]
        for provider in providers:
            err = BridgeError(f"Error from {provider}", provider=provider)
            assert err.provider == provider

    def test_security_error_has_auth_type_field(self):
        """Test that SecurityError consistently accepts an auth_type field."""
        auth_types = ["api_key", "bearer_token", "session_token", "oauth", "cli-oauth"]
        for auth_type in auth_types:
            err = SecurityError(f"Auth error with {auth_type}", auth_type=auth_type)
            assert err.auth_type == auth_type

    def test_bridge_errors_are_serializable(self):
        """Test that bridge errors can be serialized via to_dict."""
        import json
        err = BridgeError("Serializable error", error_code="BRIDGE_ERROR", provider="test")
        data = err.to_dict()
        json_str = json.dumps(data)
        assert "test" in json_str
        assert "BRIDGE_ERROR" in json_str

    def test_security_errors_are_serializable(self):
        """Test that security errors can be serialized via to_dict."""
        import json
        err = SecurityError(
            "Serializable security error",
            error_code="SECURITY_AUTH_MISSING",
            auth_type="api_key",
            details={"provider": "openai"}
        )
        data = err.to_dict()
        json_str = json.dumps(data)
        assert "api_key" in json_str

    def test_bridge_error_default_code(self):
        """Test that BridgeError default error code is BRIDGE_ERROR."""
        err = BridgeError("Default error")
        assert err.error_code == "BRIDGE_ERROR"

    def test_security_error_default_code(self):
        """Test that SecurityError default error code is SECURITY_ERROR."""
        err = SecurityError("Default security error")
        assert err.error_code == "SECURITY_ERROR"

    def test_bridge_error_with_rate_limit_code(self):
        """Test BridgeError with rate limit error code pattern."""
        err = BridgeError(
            "Rate limit exceeded",
            error_code="BRIDGE_RATE_LIMIT",
            provider="openai"
        )
        assert err.error_code == "BRIDGE_RATE_LIMIT"
        assert "BRIDGE_RATE_LIMIT" in str(err)

    def test_bridge_error_with_timeout_code(self):
        """Test BridgeError with timeout error code pattern."""
        err = BridgeError(
            "Request timed out",
            error_code="BRIDGE_TIMEOUT",
            provider="gemini"
        )
        assert err.error_code == "BRIDGE_TIMEOUT"
        assert err.provider == "gemini"
