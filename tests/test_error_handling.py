"""Comprehensive tests for the enhanced exception hierarchy (AI-207).

Covers:
- All exception types and their specific attributes
- Inheritance hierarchy correctness
- Error codes (defaults and custom)
- JSON serialization via to_dict() and to_json()
- is_retryable() helper function
- get_error_code() helper function
- __cause__ (exception chain) support in to_dict()
- error_handler context manager (reraise=True and reraise=False)
"""

import json

import pytest

from exceptions import (
    AgentError,
    AuthenticationError,
    BridgeError,
    ConfigurationError,
    RateLimitError,
    SecurityError,
    TimeoutError,
    error_handler,
    get_error_code,
    is_retryable,
)


# ---------------------------------------------------------------------------
# AgentError base class
# ---------------------------------------------------------------------------

class TestAgentError:
    def test_basic_creation(self):
        err = AgentError("Something went wrong")
        assert err.message == "Something went wrong"
        assert err.error_code == "AGENT_ERROR"

    def test_custom_error_code(self):
        err = AgentError("msg", error_code="MY_CODE")
        assert err.error_code == "MY_CODE"

    def test_str_includes_code_and_message(self):
        err = AgentError("msg", error_code="X")
        assert str(err) == "[X] msg"

    def test_none_error_code_defaults(self):
        err = AgentError("msg", error_code=None)
        assert err.error_code == "AGENT_ERROR"

    def test_is_exception(self):
        err = AgentError("msg")
        assert isinstance(err, Exception)

    def test_to_dict_keys(self):
        err = AgentError("hello", error_code="CODE")
        d = err.to_dict()
        assert d["error_code"] == "CODE"
        assert d["error_type"] == "AgentError"
        assert d["message"] == "hello"
        assert "cause" not in d

    def test_to_json_roundtrip(self):
        err = AgentError("hello", error_code="CODE")
        parsed = json.loads(err.to_json())
        assert parsed["error_code"] == "CODE"
        assert parsed["message"] == "hello"

    def test_cause_included_in_to_dict_when_chained(self):
        original = ValueError("original problem")
        try:
            raise original
        except ValueError as exc:
            wrapped = AgentError("wrapped")
            wrapped.__cause__ = exc
        d = wrapped.to_dict()
        assert "cause" in d
        assert d["cause"]["error_type"] == "ValueError"
        assert "original problem" in d["cause"]["message"]

    def test_agent_error_cause_chained(self):
        inner = BridgeError("inner", error_code="BRIDGE_CONNECTION", provider="claude")
        outer = AgentError("outer")
        outer.__cause__ = inner
        d = outer.to_dict()
        assert d["cause"]["error_code"] == "BRIDGE_CONNECTION"
        assert d["cause"]["error_type"] == "BridgeError"


# ---------------------------------------------------------------------------
# BridgeError
# ---------------------------------------------------------------------------

class TestBridgeError:
    def test_default_error_code(self):
        err = BridgeError("fail")
        assert err.error_code == "BRIDGE_ERROR"

    def test_provider_attribute(self):
        err = BridgeError("fail", provider="openai")
        assert err.provider == "openai"

    def test_no_provider_by_default(self):
        err = BridgeError("fail")
        assert err.provider is None

    def test_inherits_from_agent_error(self):
        err = BridgeError("fail")
        assert isinstance(err, AgentError)

    def test_to_dict_includes_provider(self):
        err = BridgeError("fail", error_code="BRIDGE_CONNECTION", provider="gemini")
        d = err.to_dict()
        assert d["provider"] == "gemini"
        assert d["error_type"] == "BridgeError"

    def test_to_dict_no_provider_key_when_absent(self):
        err = BridgeError("fail")
        assert "provider" not in err.to_dict()

    def test_catchable_as_agent_error(self):
        with pytest.raises(AgentError):
            raise BridgeError("fail", provider="anthropic")

    def test_bridge_specific_error_codes(self):
        codes = [
            "BRIDGE_CONNECTION", "BRIDGE_AUTH", "BRIDGE_MODEL_ERROR",
            "BRIDGE_RATE_LIMIT", "BRIDGE_TIMEOUT", "BRIDGE_INVALID_CONFIG",
            "BRIDGE_UNSUPPORTED_PROVIDER",
        ]
        for code in codes:
            err = BridgeError("msg", error_code=code)
            assert err.error_code == code
            assert code in str(err)


# ---------------------------------------------------------------------------
# SecurityError
# ---------------------------------------------------------------------------

class TestSecurityError:
    def test_default_error_code(self):
        err = SecurityError("denied")
        assert err.error_code == "SECURITY_ERROR"

    def test_auth_type_and_details(self):
        err = SecurityError("denied", auth_type="bearer_token", details={"ip": "1.2.3.4"})
        assert err.auth_type == "bearer_token"
        assert err.details["ip"] == "1.2.3.4"

    def test_details_defaults_to_empty_dict(self):
        err = SecurityError("denied")
        assert err.details == {}

    def test_inherits_from_agent_error(self):
        assert isinstance(SecurityError("x"), AgentError)

    def test_to_dict_full(self):
        err = SecurityError(
            "bad token",
            error_code="SECURITY_TOKEN_INVALID",
            auth_type="api_key",
            details={"attempt": 2}
        )
        d = err.to_dict()
        assert d["auth_type"] == "api_key"
        assert d["details"]["attempt"] == 2

    def test_to_dict_partial_fields_absent(self):
        err = SecurityError("denied", error_code="SECURITY_AUTH_FAILED")
        d = err.to_dict()
        assert "auth_type" not in d
        assert "details" not in d


# ---------------------------------------------------------------------------
# ConfigurationError
# ---------------------------------------------------------------------------

class TestConfigurationError:
    def test_default_error_code(self):
        err = ConfigurationError("bad config")
        assert err.error_code == "CONFIG_ERROR"

    def test_config_key_attribute(self):
        err = ConfigurationError("missing key", config_key="OPENAI_API_KEY")
        assert err.config_key == "OPENAI_API_KEY"

    def test_inherits_from_agent_error(self):
        assert isinstance(ConfigurationError("x"), AgentError)

    def test_to_dict_includes_config_key(self):
        err = ConfigurationError("missing", config_key="DATABASE_URL")
        d = err.to_dict()
        assert d["config_key"] == "DATABASE_URL"
        assert d["error_type"] == "ConfigurationError"

    def test_to_dict_no_config_key_when_absent(self):
        err = ConfigurationError("bad config")
        assert "config_key" not in err.to_dict()

    def test_catchable_as_agent_error(self):
        with pytest.raises(AgentError):
            raise ConfigurationError("missing key", config_key="X")


# ---------------------------------------------------------------------------
# TimeoutError
# ---------------------------------------------------------------------------

class TestTimeoutError:
    def test_default_error_code(self):
        err = TimeoutError("timed out")
        assert err.error_code == "TIMEOUT_ERROR"

    def test_timeout_seconds_attribute(self):
        err = TimeoutError("timed out", timeout_seconds=30.0)
        assert err.timeout_seconds == 30.0

    def test_inherits_from_agent_error(self):
        assert isinstance(TimeoutError("x"), AgentError)

    def test_to_dict_includes_timeout_seconds(self):
        err = TimeoutError("slow", timeout_seconds=5.5)
        d = err.to_dict()
        assert d["timeout_seconds"] == 5.5

    def test_to_dict_no_timeout_seconds_when_absent(self):
        err = TimeoutError("slow")
        assert "timeout_seconds" not in err.to_dict()

    def test_catchable_as_agent_error(self):
        with pytest.raises(AgentError):
            raise TimeoutError("timed out", timeout_seconds=10)


# ---------------------------------------------------------------------------
# RateLimitError
# ---------------------------------------------------------------------------

class TestRateLimitError:
    def test_default_error_code(self):
        err = RateLimitError("too many requests")
        assert err.error_code == "RATE_LIMIT_ERROR"

    def test_retry_after_attribute(self):
        err = RateLimitError("slow down", retry_after=60.0)
        assert err.retry_after == 60.0

    def test_provider_attribute(self):
        err = RateLimitError("limited", provider="openai")
        assert err.provider == "openai"

    def test_inherits_from_agent_error(self):
        assert isinstance(RateLimitError("x"), AgentError)

    def test_to_dict_includes_retry_after_and_provider(self):
        err = RateLimitError("limited", retry_after=30.0, provider="anthropic")
        d = err.to_dict()
        assert d["retry_after"] == 30.0
        assert d["provider"] == "anthropic"

    def test_to_dict_absent_optional_fields(self):
        err = RateLimitError("limited")
        d = err.to_dict()
        assert "retry_after" not in d
        assert "provider" not in d

    def test_catchable_as_agent_error(self):
        with pytest.raises(AgentError):
            raise RateLimitError("rate limited")


# ---------------------------------------------------------------------------
# AuthenticationError
# ---------------------------------------------------------------------------

class TestAuthenticationError:
    def test_default_error_code(self):
        err = AuthenticationError("invalid credentials")
        assert err.error_code == "AUTH_ERROR"

    def test_username_attribute(self):
        err = AuthenticationError("bad creds", username="alice")
        assert err.username == "alice"

    def test_inherits_from_agent_error(self):
        assert isinstance(AuthenticationError("x"), AgentError)

    def test_to_dict_includes_username(self):
        err = AuthenticationError("denied", error_code="AUTH_INVALID_CREDENTIALS", username="bob")
        d = err.to_dict()
        assert d["username"] == "bob"
        assert d["error_type"] == "AuthenticationError"

    def test_to_dict_no_username_when_absent(self):
        err = AuthenticationError("denied")
        assert "username" not in err.to_dict()

    def test_catchable_as_agent_error(self):
        with pytest.raises(AgentError):
            raise AuthenticationError("bad creds")


# ---------------------------------------------------------------------------
# Inheritance hierarchy
# ---------------------------------------------------------------------------

class TestInheritanceHierarchy:
    def test_all_subclass_agent_error(self):
        for cls in (BridgeError, SecurityError, ConfigurationError,
                    TimeoutError, RateLimitError, AuthenticationError):
            assert issubclass(cls, AgentError), f"{cls.__name__} must subclass AgentError"

    def test_agent_error_subclasses_exception(self):
        assert issubclass(AgentError, Exception)

    def test_siblings_do_not_catch_each_other(self):
        with pytest.raises(BridgeError):
            try:
                raise BridgeError("bridge fail")
            except SecurityError:
                pytest.fail("SecurityError should not catch BridgeError")

    def test_catch_all_via_agent_error(self):
        instances = [
            BridgeError("b"),
            SecurityError("s"),
            ConfigurationError("c"),
            TimeoutError("t"),
            RateLimitError("r"),
            AuthenticationError("a"),
        ]
        for exc in instances:
            with pytest.raises(AgentError):
                raise exc


# ---------------------------------------------------------------------------
# is_retryable() helper
# ---------------------------------------------------------------------------

class TestIsRetryable:
    def test_rate_limit_error_is_retryable(self):
        assert is_retryable(RateLimitError("limited")) is True

    def test_timeout_error_is_retryable(self):
        assert is_retryable(TimeoutError("timed out")) is True

    def test_bridge_connection_is_retryable(self):
        assert is_retryable(BridgeError("conn fail", error_code="BRIDGE_CONNECTION")) is True

    def test_bridge_rate_limit_is_retryable(self):
        assert is_retryable(BridgeError("rate", error_code="BRIDGE_RATE_LIMIT")) is True

    def test_bridge_timeout_is_retryable(self):
        assert is_retryable(BridgeError("timeout", error_code="BRIDGE_TIMEOUT")) is True

    def test_security_error_not_retryable(self):
        assert is_retryable(SecurityError("denied")) is False

    def test_agent_error_not_retryable_by_default(self):
        assert is_retryable(AgentError("generic")) is False

    def test_non_agent_error_not_retryable(self):
        assert is_retryable(ValueError("not agent")) is False

    def test_config_error_not_retryable(self):
        assert is_retryable(ConfigurationError("bad cfg")) is False

    def test_auth_error_not_retryable(self):
        assert is_retryable(AuthenticationError("bad creds")) is False


# ---------------------------------------------------------------------------
# get_error_code() helper
# ---------------------------------------------------------------------------

class TestGetErrorCode:
    def test_returns_code_for_agent_error(self):
        err = AgentError("msg", error_code="MY_CODE")
        assert get_error_code(err) == "MY_CODE"

    def test_returns_code_for_subclass(self):
        err = BridgeError("fail", error_code="BRIDGE_AUTH")
        assert get_error_code(err) == "BRIDGE_AUTH"

    def test_returns_none_for_plain_exception(self):
        assert get_error_code(ValueError("oops")) is None

    def test_returns_none_for_none_input(self):
        # Passing something that is not an exception should return None
        assert get_error_code(RuntimeError("x")) is None


# ---------------------------------------------------------------------------
# error_handler context manager
# ---------------------------------------------------------------------------

class TestErrorHandlerContextManager:
    def test_suppresses_when_reraise_false(self):
        with error_handler(reraise=False) as ctx:
            raise BridgeError("boom", provider="claude")
        assert isinstance(ctx.exception, BridgeError)
        assert ctx.exception.provider == "claude"

    def test_reraises_by_default(self):
        with pytest.raises(BridgeError):
            with error_handler() as ctx:
                raise BridgeError("boom")

    def test_reraises_when_reraise_true(self):
        with pytest.raises(AgentError):
            with error_handler(reraise=True) as ctx:
                raise ConfigurationError("bad config")

    def test_log_fn_called_on_exception(self):
        captured = []
        with error_handler(reraise=False, log_fn=captured.append) as ctx:
            raise RateLimitError("too fast", retry_after=5.0)
        assert len(captured) == 1
        assert isinstance(captured[0], RateLimitError)

    def test_no_exception_leaves_ctx_exception_as_none(self):
        with error_handler(reraise=False) as ctx:
            pass  # no error
        assert ctx.exception is None

    def test_non_agent_errors_propagate_unaffected(self):
        with pytest.raises(ValueError):
            with error_handler(reraise=False) as ctx:
                raise ValueError("not an agent error")
        # ctx.exception should be None since we only intercept AgentError
        assert ctx.exception is None

    def test_log_fn_not_called_when_no_exception(self):
        called = []
        with error_handler(reraise=False, log_fn=lambda e: called.append(e)):
            x = 1 + 1  # no error
        assert called == []


# ---------------------------------------------------------------------------
# Exception chaining (__cause__) in to_dict
# ---------------------------------------------------------------------------

class TestExceptionChaining:
    def test_cause_chain_appears_in_to_dict(self):
        root = ValueError("database down")
        bridge = BridgeError("provider unavailable", provider="anthropic")
        bridge.__cause__ = root
        d = bridge.to_dict()
        assert d["cause"]["error_type"] == "ValueError"

    def test_nested_agent_error_chain(self):
        inner = ConfigurationError("missing key", config_key="API_KEY")
        outer = BridgeError("cannot start bridge")
        outer.__cause__ = inner
        d = outer.to_dict()
        assert d["cause"]["error_code"] == "CONFIG_ERROR"
        assert d["cause"]["config_key"] == "API_KEY"

    def test_no_cause_key_when_no_chain(self):
        err = TimeoutError("timed out")
        d = err.to_dict()
        assert "cause" not in d


# ---------------------------------------------------------------------------
# JSON serialization round-trips
# ---------------------------------------------------------------------------

class TestJSONSerialization:
    def test_all_types_json_serializable(self):
        errors = [
            AgentError("a", error_code="A"),
            BridgeError("b", provider="p"),
            SecurityError("c", auth_type="api_key", details={"k": "v"}),
            ConfigurationError("d", config_key="KEY"),
            TimeoutError("e", timeout_seconds=10.0),
            RateLimitError("f", retry_after=30.0, provider="openai"),
            AuthenticationError("g", username="user1"),
        ]
        for err in errors:
            data = err.to_dict()
            # Must be round-trippable through json
            serialized = json.dumps(data)
            parsed = json.loads(serialized)
            assert parsed["error_type"] == type(err).__name__

    def test_to_json_method(self):
        err = RateLimitError("limited", retry_after=45.0, provider="anthropic")
        parsed = json.loads(err.to_json())
        assert parsed["retry_after"] == 45.0
        assert parsed["provider"] == "anthropic"
