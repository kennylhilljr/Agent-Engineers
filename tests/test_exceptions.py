"""Unit tests for the custom exception hierarchy in exceptions.py

Tests cover:
- AgentError base class functionality
- BridgeError for provider-related errors
- SecurityError for authentication/authorization errors
- Error code assignment and retrieval
- JSON serialization via to_dict()
- String representation with error codes
"""

import pytest
from exceptions import AgentError, BridgeError, SecurityError


class TestAgentError:
    """Test suite for AgentError base exception class."""

    def test_agent_error_basic_creation(self):
        """Test basic AgentError creation with message only."""
        error = AgentError("Test error message")
        assert error.message == "Test error message"
        assert error.error_code == "AGENT_ERROR"
        assert str(error) == "[AGENT_ERROR] Test error message"

    def test_agent_error_with_error_code(self):
        """Test AgentError creation with custom error code."""
        error = AgentError("Custom error", error_code="CUSTOM_CODE")
        assert error.message == "Custom error"
        assert error.error_code == "CUSTOM_CODE"
        assert str(error) == "[CUSTOM_CODE] Custom error"

    def test_agent_error_to_dict(self):
        """Test AgentError JSON serialization."""
        error = AgentError("Test message", error_code="TEST_CODE")
        data = error.to_dict()
        assert data["error_code"] == "TEST_CODE"
        assert data["error_type"] == "AgentError"
        assert data["message"] == "Test message"

    def test_agent_error_inheritance(self):
        """Test that AgentError inherits from Exception."""
        error = AgentError("Test error")
        assert isinstance(error, Exception)

    def test_agent_error_string_without_error_code(self):
        """Test string representation when error_code is None."""
        # When error_code is None, it defaults to "AGENT_ERROR"
        error = AgentError("Simple message", error_code=None)
        assert str(error) == "[AGENT_ERROR] Simple message"

    def test_agent_error_exception_handling(self):
        """Test that AgentError can be caught as Exception."""
        with pytest.raises(AgentError):
            raise AgentError("Test exception")

        with pytest.raises(Exception):
            raise AgentError("Test exception")


class TestBridgeError:
    """Test suite for BridgeError for AI provider bridge errors."""

    def test_bridge_error_basic_creation(self):
        """Test basic BridgeError creation."""
        error = BridgeError("Connection failed")
        assert error.message == "Connection failed"
        assert error.error_code == "BRIDGE_ERROR"
        assert error.provider is None

    def test_bridge_error_with_provider(self):
        """Test BridgeError with provider information."""
        error = BridgeError(
            "API error",
            error_code="BRIDGE_MODEL_ERROR",
            provider="claude"
        )
        assert error.message == "API error"
        assert error.error_code == "BRIDGE_MODEL_ERROR"
        assert error.provider == "claude"
        assert str(error) == "[BRIDGE_MODEL_ERROR] API error"

    def test_bridge_error_to_dict(self):
        """Test BridgeError JSON serialization includes provider."""
        error = BridgeError(
            "Connection timeout",
            error_code="BRIDGE_TIMEOUT",
            provider="openai"
        )
        data = error.to_dict()
        assert data["error_code"] == "BRIDGE_TIMEOUT"
        assert data["error_type"] == "BridgeError"
        assert data["message"] == "Connection timeout"
        assert data["provider"] == "openai"

    def test_bridge_error_to_dict_without_provider(self):
        """Test BridgeError JSON serialization without provider."""
        error = BridgeError("Error occurred", error_code="BRIDGE_ERROR")
        data = error.to_dict()
        assert "provider" not in data

    def test_bridge_error_inheritance(self):
        """Test that BridgeError inherits from AgentError."""
        error = BridgeError("Test error", provider="claude")
        assert isinstance(error, AgentError)
        assert isinstance(error, Exception)

    def test_bridge_error_exception_handling(self):
        """Test catching BridgeError and AgentError separately."""
        with pytest.raises(BridgeError):
            raise BridgeError("Bridge failed", provider="gemini")

        # Should also be catchable as AgentError
        with pytest.raises(AgentError):
            raise BridgeError("Bridge failed", provider="gemini")

    def test_bridge_error_codes(self):
        """Test various BridgeError error codes."""
        error_codes = [
            ("BRIDGE_CONNECTION", "Connection to provider failed"),
            ("BRIDGE_AUTH", "Authentication with provider failed"),
            ("BRIDGE_MODEL_ERROR", "Provider returned model error"),
            ("BRIDGE_RATE_LIMIT", "Rate limit exceeded"),
            ("BRIDGE_TIMEOUT", "Request timeout"),
            ("BRIDGE_INVALID_CONFIG", "Invalid provider configuration"),
            ("BRIDGE_UNSUPPORTED_PROVIDER", "Provider not supported"),
        ]

        for code, message in error_codes:
            error = BridgeError(message, error_code=code)
            assert error.error_code == code
            assert code in str(error)


class TestSecurityError:
    """Test suite for SecurityError for authentication/authorization errors."""

    def test_security_error_basic_creation(self):
        """Test basic SecurityError creation."""
        error = SecurityError("Authentication failed")
        assert error.message == "Authentication failed"
        assert error.error_code == "SECURITY_ERROR"
        assert error.auth_type is None
        assert error.details == {}

    def test_security_error_with_auth_type(self):
        """Test SecurityError with authentication type."""
        error = SecurityError(
            "Invalid token",
            error_code="SECURITY_TOKEN_INVALID",
            auth_type="bearer_token"
        )
        assert error.message == "Invalid token"
        assert error.error_code == "SECURITY_TOKEN_INVALID"
        assert error.auth_type == "bearer_token"

    def test_security_error_with_details(self):
        """Test SecurityError with additional details."""
        details = {"ip_address": "192.168.1.1", "attempt": 3}
        error = SecurityError(
            "Too many attempts",
            error_code="SECURITY_AUTH_FAILED",
            auth_type="password",
            details=details
        )
        assert error.details == details

    def test_security_error_to_dict(self):
        """Test SecurityError JSON serialization."""
        details = {"provider": "openai"}
        error = SecurityError(
            "Missing API key",
            error_code="SECURITY_AUTH_MISSING",
            auth_type="api_key",
            details=details
        )
        data = error.to_dict()
        assert data["error_code"] == "SECURITY_AUTH_MISSING"
        assert data["error_type"] == "SecurityError"
        assert data["message"] == "Missing API key"
        assert data["auth_type"] == "api_key"
        assert data["details"] == details

    def test_security_error_to_dict_partial(self):
        """Test SecurityError JSON serialization with only some fields."""
        error = SecurityError(
            "Auth failed",
            error_code="SECURITY_AUTH_FAILED"
        )
        data = error.to_dict()
        assert "auth_type" not in data
        assert "details" not in data

    def test_security_error_inheritance(self):
        """Test that SecurityError inherits from AgentError."""
        error = SecurityError("Security issue", auth_type="api_key")
        assert isinstance(error, AgentError)
        assert isinstance(error, Exception)

    def test_security_error_exception_handling(self):
        """Test catching SecurityError and AgentError separately."""
        with pytest.raises(SecurityError):
            raise SecurityError("Unauthorized", auth_type="bearer_token")

        # Should also be catchable as AgentError
        with pytest.raises(AgentError):
            raise SecurityError("Unauthorized", auth_type="bearer_token")

    def test_security_error_codes(self):
        """Test various SecurityError error codes."""
        error_codes = [
            ("SECURITY_AUTH_FAILED", "Authentication failed"),
            ("SECURITY_AUTH_MISSING", "Missing authentication credentials"),
            ("SECURITY_TOKEN_INVALID", "Invalid or expired token"),
            ("SECURITY_TOKEN_EXPIRED", "Token has expired"),
            ("SECURITY_INSUFFICIENT_PERMISSIONS", "User lacks permissions"),
            ("SECURITY_INVALID_SIGNATURE", "Invalid request signature"),
            ("SECURITY_INVALID_HEADER", "Invalid security header format"),
        ]

        for code, message in error_codes:
            error = SecurityError(message, error_code=code)
            assert error.error_code == code
            assert code in str(error)


class TestExceptionHierarchy:
    """Test the exception inheritance hierarchy."""

    def test_exception_hierarchy_structure(self):
        """Test that exception hierarchy is correctly structured."""
        # BridgeError should inherit from AgentError
        assert issubclass(BridgeError, AgentError)
        # SecurityError should inherit from AgentError
        assert issubclass(SecurityError, AgentError)
        # AgentError should inherit from Exception
        assert issubclass(AgentError, Exception)

    def test_catch_all_with_agent_error(self):
        """Test that all custom exceptions can be caught with AgentError."""
        exceptions_to_test = [
            AgentError("Base error"),
            BridgeError("Bridge error", provider="claude"),
            SecurityError("Security error", auth_type="api_key"),
        ]

        for exc in exceptions_to_test:
            with pytest.raises(AgentError):
                raise exc

    def test_specific_exception_handling(self):
        """Test that exceptions can be handled specifically."""
        try:
            raise BridgeError("Bridge failed", provider="openai")
        except SecurityError:
            pytest.fail("SecurityError should not catch BridgeError")
        except BridgeError as e:
            assert e.provider == "openai"

        try:
            raise SecurityError("Auth failed", auth_type="bearer_token")
        except BridgeError:
            pytest.fail("BridgeError should not catch SecurityError")
        except SecurityError as e:
            assert e.auth_type == "bearer_token"

    def test_exception_message_preservation(self):
        """Test that exception messages are preserved through the hierarchy."""
        message = "Specific error message"

        agent_error = AgentError(message)
        bridge_error = BridgeError(message, provider="claude")
        security_error = SecurityError(message, auth_type="api_key")

        assert agent_error.message == message
        assert bridge_error.message == message
        assert security_error.message == message


class TestErrorCodeUsage:
    """Test error code assignment and usage patterns."""

    def test_error_code_default_values(self):
        """Test default error codes for each exception type."""
        agent_error = AgentError("msg")
        assert agent_error.error_code == "AGENT_ERROR"

        bridge_error = BridgeError("msg")
        assert bridge_error.error_code == "BRIDGE_ERROR"

        security_error = SecurityError("msg")
        assert security_error.error_code == "SECURITY_ERROR"

    def test_error_code_custom_values(self):
        """Test custom error code assignment."""
        custom_code = "CUSTOM_BRIDGE_ERROR"
        error = BridgeError("msg", error_code=custom_code)
        assert error.error_code == custom_code

    def test_error_code_in_string_representation(self):
        """Test that error codes are included in string representation."""
        error = SecurityError("Failed", error_code="SECURITY_TOKEN_INVALID")
        error_str = str(error)
        assert "SECURITY_TOKEN_INVALID" in error_str
        assert "Failed" in error_str


class TestJSONSerialization:
    """Test JSON serialization functionality."""

    def test_agent_error_json_serializable(self):
        """Test that AgentError can be JSON serialized."""
        import json
        error = AgentError("Test error", error_code="TEST")
        data = error.to_dict()
        json_str = json.dumps(data)
        assert "TEST" in json_str
        assert "Test error" in json_str

    def test_bridge_error_json_serializable(self):
        """Test that BridgeError can be JSON serialized."""
        import json
        error = BridgeError(
            "Provider error",
            error_code="BRIDGE_AUTH",
            provider="claude"
        )
        data = error.to_dict()
        json_str = json.dumps(data)
        assert "BRIDGE_AUTH" in json_str
        assert "claude" in json_str

    def test_security_error_json_serializable(self):
        """Test that SecurityError can be JSON serialized."""
        import json
        error = SecurityError(
            "Auth failed",
            error_code="SECURITY_AUTH_FAILED",
            auth_type="api_key",
            details={"attempts": 3}
        )
        data = error.to_dict()
        json_str = json.dumps(data)
        assert "SECURITY_AUTH_FAILED" in json_str
        assert "api_key" in json_str
        assert "attempts" in json_str


class TestIntegration:
    """Integration tests for exception usage patterns."""

    def test_provider_bridge_error_pattern(self):
        """Test typical provider bridge error pattern."""
        try:
            raise BridgeError(
                "Failed to connect to API endpoint",
                error_code="BRIDGE_CONNECTION",
                provider="gemini"
            )
        except BridgeError as e:
            assert e.error_code == "BRIDGE_CONNECTION"
            assert e.provider == "gemini"
            data = e.to_dict()
            assert data["error_type"] == "BridgeError"

    def test_authentication_error_pattern(self):
        """Test typical authentication error pattern."""
        try:
            raise SecurityError(
                "API key is invalid or expired",
                error_code="SECURITY_TOKEN_INVALID",
                auth_type="api_key",
                details={"provider": "openai", "key_age_days": 90}
            )
        except SecurityError as e:
            assert e.error_code == "SECURITY_TOKEN_INVALID"
            assert e.auth_type == "api_key"
            assert e.details["provider"] == "openai"
            data = e.to_dict()
            assert data["error_type"] == "SecurityError"

    def test_error_propagation_through_handlers(self):
        """Test error propagation through try/except blocks."""
        def inner_function():
            raise BridgeError(
                "Provider unavailable",
                error_code="BRIDGE_CONNECTION",
                provider="claude"
            )

        def outer_function():
            try:
                inner_function()
            except BridgeError as e:
                # Re-raise with additional context
                raise AgentError(
                    f"Failed to call provider {e.provider}: {e.message}",
                    error_code="AGENT_ERROR"
                )

        with pytest.raises(AgentError) as exc_info:
            outer_function()

        assert "claude" in str(exc_info.value)
