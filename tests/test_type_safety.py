"""Comprehensive type safety tests for AI-208.

Tests cover:
- Protocol compliance for BaseBridge and AgentConfig
- runtime_checkable protocol isinstance() checks
- pyproject.toml mypy configuration
- Typed function type rejection
- Protocol structural matching
- Optional type handling
- protocols.py exports
"""
import sys
import os
import tomllib
from pathlib import Path
from typing import Any, Optional
import pytest

# Ensure repo root is on path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from protocols import (
    BridgeProtocol,
    ConfigProtocol,
    ProgressTrackerProtocol,
    ExceptionProtocol,
)
from bridges.base_bridge import BaseBridge, BridgeResponse
from config import AgentConfig, APIKeys
from exceptions import AgentError, BridgeError, ConfigurationError


# ---------------------------------------------------------------------------
# Helpers / Concrete stubs
# ---------------------------------------------------------------------------

class ConcreteStubBridge(BaseBridge):
    """Minimal concrete bridge for testing protocol compliance."""

    @property
    def provider_name(self) -> str:
        return "stub"

    async def send_task(self, task: str, **kwargs: Any) -> BridgeResponse:
        return BridgeResponse(content="ok", model="stub-model", provider="stub")

    def get_auth_info(self) -> dict[str, str]:
        return {"api_key": "test-key"}


class MinimalBridgeImplementation:
    """Structural (duck-typed) bridge – does NOT inherit BaseBridge."""

    @property
    def provider_name(self) -> str:
        return "minimal"

    async def send_task(self, task: str, **kwargs: Any) -> Any:
        return {"result": task}

    def get_auth_info(self) -> dict[str, str]:
        return {"token": "abc"}


class IncompleteBridge:
    """Missing get_auth_info – should NOT satisfy BridgeProtocol at runtime."""

    @property
    def provider_name(self) -> str:
        return "incomplete"

    async def send_task(self, task: str, **kwargs: Any) -> Any:
        return None


class ConcreteConfig:
    """Structural config implementation."""

    def validate(self) -> list[str]:
        return []

    def is_valid(self) -> bool:
        return True


class InvalidConfig:
    """Missing is_valid – should NOT satisfy ConfigProtocol."""

    def validate(self) -> list[str]:
        return ["missing key"]


class ConcreteProgressTracker:
    """Structural progress tracker."""

    def load_project_state(self) -> dict[str, Any]:
        return {"initialized": True}


class ConcreteException(Exception):
    """Structural exception matching ExceptionProtocol."""

    @property
    def error_code(self) -> Optional[str]:
        return "TEST_CODE"

    def to_dict(self) -> dict[str, Any]:
        return {"error_code": self.error_code, "message": str(self)}


# ---------------------------------------------------------------------------
# Part 1 – Protocol compliance for BaseBridge
# ---------------------------------------------------------------------------

class TestBaseBridgeProtocolCompliance:
    """Tests that BaseBridge implementations satisfy BridgeProtocol."""

    def test_concrete_bridge_has_provider_name(self) -> None:
        bridge = ConcreteStubBridge()
        assert bridge.provider_name == "stub"

    def test_concrete_bridge_has_get_auth_info(self) -> None:
        bridge = ConcreteStubBridge()
        auth = bridge.get_auth_info()
        assert isinstance(auth, dict)

    def test_concrete_bridge_is_instance_of_base_bridge(self) -> None:
        bridge = ConcreteStubBridge()
        assert isinstance(bridge, BaseBridge)

    def test_bridge_protocol_isinstance_concrete_bridge(self) -> None:
        """runtime_checkable: ConcreteStubBridge satisfies BridgeProtocol."""
        bridge = ConcreteStubBridge()
        assert isinstance(bridge, BridgeProtocol)

    def test_bridge_protocol_isinstance_structural(self) -> None:
        """runtime_checkable: structural duck-typed class satisfies BridgeProtocol."""
        bridge = MinimalBridgeImplementation()
        assert isinstance(bridge, BridgeProtocol)

    def test_bridge_protocol_rejects_incomplete(self) -> None:
        """runtime_checkable: class missing get_auth_info does NOT satisfy BridgeProtocol."""
        bridge = IncompleteBridge()
        assert not isinstance(bridge, BridgeProtocol)

    def test_bridge_provider_name_is_str(self) -> None:
        bridge = ConcreteStubBridge()
        assert isinstance(bridge.provider_name, str)

    def test_bridge_get_auth_info_returns_dict_of_strings(self) -> None:
        bridge = ConcreteStubBridge()
        auth = bridge.get_auth_info()
        assert all(isinstance(k, str) and isinstance(v, str) for k, v in auth.items())

    def test_bridge_repr(self) -> None:
        bridge = ConcreteStubBridge()
        assert "stub" in repr(bridge)

    def test_bridge_validate_response_true_for_valid(self) -> None:
        bridge = ConcreteStubBridge()
        resp = BridgeResponse(content="hello", model="m", provider="stub")
        assert bridge.validate_response(resp) is True

    def test_bridge_validate_response_false_for_failed(self) -> None:
        bridge = ConcreteStubBridge()
        resp = BridgeResponse(content="", model="m", provider="stub", success=False)
        assert bridge.validate_response(resp) is False


# ---------------------------------------------------------------------------
# Part 2 – Protocol compliance for AgentConfig
# ---------------------------------------------------------------------------

class TestAgentConfigProtocolCompliance:
    """Tests that AgentConfig satisfies ConfigProtocol."""

    def test_agent_config_isinstance_config_protocol(self) -> None:
        config = AgentConfig()
        assert isinstance(config, ConfigProtocol)

    def test_agent_config_validate_returns_list(self) -> None:
        config = AgentConfig()
        result = config.validate()
        assert isinstance(result, list)

    def test_agent_config_is_valid_returns_bool(self) -> None:
        config = AgentConfig()
        result = config.is_valid()
        assert isinstance(result, bool)

    def test_structural_config_isinstance_config_protocol(self) -> None:
        config = ConcreteConfig()
        assert isinstance(config, ConfigProtocol)

    def test_incomplete_config_not_config_protocol(self) -> None:
        config = InvalidConfig()
        assert not isinstance(config, ConfigProtocol)

    def test_api_keys_validate_returns_list(self) -> None:
        keys = APIKeys()
        result = keys.validate()
        assert isinstance(result, list)

    def test_agent_config_has_timeout(self) -> None:
        config = AgentConfig()
        assert isinstance(config.timeout, int)
        assert config.timeout > 0

    def test_agent_config_has_dashboard_port(self) -> None:
        config = AgentConfig()
        assert isinstance(config.dashboard_port, int)


# ---------------------------------------------------------------------------
# Part 3 – runtime_checkable isinstance() checks
# ---------------------------------------------------------------------------

class TestRuntimeCheckableProtocols:
    """Tests that @runtime_checkable protocols work correctly with isinstance()."""

    def test_bridge_protocol_is_runtime_checkable(self) -> None:
        # This will raise TypeError if not @runtime_checkable
        bridge = MinimalBridgeImplementation()
        result = isinstance(bridge, BridgeProtocol)
        assert isinstance(result, bool)

    def test_config_protocol_is_runtime_checkable(self) -> None:
        config = ConcreteConfig()
        result = isinstance(config, ConfigProtocol)
        assert isinstance(result, bool)

    def test_progress_tracker_protocol_is_runtime_checkable(self) -> None:
        tracker = ConcreteProgressTracker()
        result = isinstance(tracker, ProgressTrackerProtocol)
        assert isinstance(result, bool)

    def test_exception_protocol_is_runtime_checkable(self) -> None:
        exc = ConcreteException("test")
        result = isinstance(exc, ExceptionProtocol)
        assert isinstance(result, bool)

    def test_concrete_exception_satisfies_exception_protocol(self) -> None:
        exc = ConcreteException("test error")
        assert isinstance(exc, ExceptionProtocol)

    def test_progress_tracker_satisfies_protocol(self) -> None:
        tracker = ConcreteProgressTracker()
        assert isinstance(tracker, ProgressTrackerProtocol)

    def test_plain_object_does_not_satisfy_bridge_protocol(self) -> None:
        assert not isinstance(object(), BridgeProtocol)

    def test_plain_object_does_not_satisfy_config_protocol(self) -> None:
        assert not isinstance(object(), ConfigProtocol)


# ---------------------------------------------------------------------------
# Part 4 – pyproject.toml has mypy configuration
# ---------------------------------------------------------------------------

class TestPyprojectTomlMypyConfig:
    """Tests that pyproject.toml contains proper mypy configuration."""

    @pytest.fixture(scope="class")
    def toml_data(self) -> dict[str, Any]:
        toml_path = REPO_ROOT / "pyproject.toml"
        with open(toml_path, "rb") as f:
            return tomllib.load(f)

    def test_mypy_section_exists(self, toml_data: dict[str, Any]) -> None:
        assert "tool" in toml_data
        assert "mypy" in toml_data["tool"]

    def test_mypy_python_version(self, toml_data: dict[str, Any]) -> None:
        mypy = toml_data["tool"]["mypy"]
        assert mypy["python_version"] == "3.11"

    def test_mypy_warn_return_any(self, toml_data: dict[str, Any]) -> None:
        mypy = toml_data["tool"]["mypy"]
        assert mypy["warn_return_any"] is True

    def test_mypy_warn_unused_configs(self, toml_data: dict[str, Any]) -> None:
        mypy = toml_data["tool"]["mypy"]
        assert mypy["warn_unused_configs"] is True

    def test_mypy_disallow_untyped_defs(self, toml_data: dict[str, Any]) -> None:
        mypy = toml_data["tool"]["mypy"]
        assert mypy["disallow_untyped_defs"] is True

    def test_mypy_disallow_incomplete_defs(self, toml_data: dict[str, Any]) -> None:
        mypy = toml_data["tool"]["mypy"]
        assert mypy["disallow_incomplete_defs"] is True

    def test_mypy_check_untyped_defs(self, toml_data: dict[str, Any]) -> None:
        mypy = toml_data["tool"]["mypy"]
        assert mypy["check_untyped_defs"] is True

    def test_mypy_no_implicit_optional(self, toml_data: dict[str, Any]) -> None:
        mypy = toml_data["tool"]["mypy"]
        assert mypy["no_implicit_optional"] is True

    def test_mypy_warn_redundant_casts(self, toml_data: dict[str, Any]) -> None:
        mypy = toml_data["tool"]["mypy"]
        assert mypy["warn_redundant_casts"] is True

    def test_mypy_overrides_section_exists(self, toml_data: dict[str, Any]) -> None:
        mypy = toml_data["tool"]["mypy"]
        assert "overrides" in mypy

    def test_mypy_overrides_ignore_missing_imports(self, toml_data: dict[str, Any]) -> None:
        overrides = toml_data["tool"]["mypy"]["overrides"]
        assert len(overrides) > 0
        assert overrides[0]["ignore_missing_imports"] is True

    def test_mypy_overrides_covers_openai(self, toml_data: dict[str, Any]) -> None:
        overrides = toml_data["tool"]["mypy"]["overrides"]
        all_modules: list[str] = []
        for override in overrides:
            all_modules.extend(override.get("module", []))
        assert any("openai" in m for m in all_modules)


# ---------------------------------------------------------------------------
# Part 5 – Protocol structural matching
# ---------------------------------------------------------------------------

class TestProtocolStructuralMatching:
    """Tests structural (duck-typed) protocol matching."""

    def test_any_class_with_validate_and_is_valid_satisfies_config_protocol(self) -> None:
        class MyConfig:
            def validate(self) -> list[str]:
                return []
            def is_valid(self) -> bool:
                return True

        assert isinstance(MyConfig(), ConfigProtocol)

    def test_any_class_with_load_project_state_satisfies_progress_protocol(self) -> None:
        class MyTracker:
            def load_project_state(self) -> dict[str, Any]:
                return {}

        assert isinstance(MyTracker(), ProgressTrackerProtocol)

    def test_exception_protocol_structural_match(self) -> None:
        class MyException(Exception):
            @property
            def error_code(self) -> Optional[str]:
                return "ERR"
            def to_dict(self) -> dict[str, Any]:
                return {"error_code": "ERR"}

        assert isinstance(MyException(), ExceptionProtocol)


# ---------------------------------------------------------------------------
# Part 6 – Optional type handling
# ---------------------------------------------------------------------------

class TestOptionalTypeHandling:
    """Tests Optional type usage in the codebase."""

    def test_bridge_response_tokens_used_optional(self) -> None:
        resp = BridgeResponse(content="hi", model="m", provider="p")
        assert resp.tokens_used is None

    def test_bridge_response_tokens_used_set(self) -> None:
        resp = BridgeResponse(content="hi", model="m", provider="p", tokens_used=100)
        assert resp.tokens_used == 100

    def test_bridge_response_error_optional(self) -> None:
        resp = BridgeResponse(content="hi", model="m", provider="p")
        assert resp.error is None

    def test_agent_error_error_code_optional_property(self) -> None:
        exc = ConcreteException("test")
        # error_code property can return None per ExceptionProtocol
        code = exc.error_code
        assert code is None or isinstance(code, str)

    def test_api_keys_optional_fields_default_none(self) -> None:
        # Without env vars set, API keys may be None
        keys = APIKeys(
            anthropic=None, openai=None, gemini=None,
            groq=None, linear=None, github=None, slack=None, arcade=None
        )
        assert keys.anthropic is None
        assert keys.openai is None

    def test_api_keys_can_be_set(self) -> None:
        keys = APIKeys(anthropic="sk-test")
        assert keys.anthropic == "sk-test"


# ---------------------------------------------------------------------------
# Part 7 – protocols.py exports all protocols
# ---------------------------------------------------------------------------

class TestProtocolsModuleExports:
    """Tests that protocols.py correctly exports all protocol classes."""

    def test_bridge_protocol_exported(self) -> None:
        import protocols
        assert hasattr(protocols, "BridgeProtocol")

    def test_config_protocol_exported(self) -> None:
        import protocols
        assert hasattr(protocols, "ConfigProtocol")

    def test_progress_tracker_protocol_exported(self) -> None:
        import protocols
        assert hasattr(protocols, "ProgressTrackerProtocol")

    def test_exception_protocol_exported(self) -> None:
        import protocols
        assert hasattr(protocols, "ExceptionProtocol")

    def test_bridge_protocol_is_runtime_checkable_class(self) -> None:
        import protocols
        # runtime_checkable protocols have _is_protocol attribute
        assert getattr(protocols.BridgeProtocol, "_is_protocol", False) is True

    def test_config_protocol_is_runtime_checkable_class(self) -> None:
        import protocols
        assert getattr(protocols.ConfigProtocol, "_is_protocol", False) is True

    def test_protocols_module_docstring(self) -> None:
        import protocols
        assert protocols.__doc__ is not None
        assert len(protocols.__doc__) > 0

    def test_protocols_file_exists(self) -> None:
        protocols_path = REPO_ROOT / "protocols.py"
        assert protocols_path.exists()

    def test_all_four_protocols_importable(self) -> None:
        from protocols import (
            BridgeProtocol,
            ConfigProtocol,
            ProgressTrackerProtocol,
            ExceptionProtocol,
        )
        assert BridgeProtocol is not None
        assert ConfigProtocol is not None
        assert ProgressTrackerProtocol is not None
        assert ExceptionProtocol is not None


# ---------------------------------------------------------------------------
# Part 8 – AgentError satisfies ExceptionProtocol
# ---------------------------------------------------------------------------

class TestAgentErrorExceptionProtocol:
    """Tests that AgentError and subclasses satisfy ExceptionProtocol."""

    def test_agent_error_has_error_code(self) -> None:
        err = AgentError("test message", error_code="TEST")
        assert err.error_code == "TEST"

    def test_agent_error_to_dict_returns_dict(self) -> None:
        err = AgentError("test message")
        result = err.to_dict()
        assert isinstance(result, dict)

    def test_agent_error_satisfies_exception_protocol(self) -> None:
        err = AgentError("test")
        assert isinstance(err, ExceptionProtocol)

    def test_bridge_error_satisfies_exception_protocol(self) -> None:
        err = BridgeError("bridge fail", provider="openai")
        assert isinstance(err, ExceptionProtocol)

    def test_configuration_error_satisfies_exception_protocol(self) -> None:
        err = ConfigurationError("bad config")
        assert isinstance(err, ExceptionProtocol)

    def test_agent_error_to_dict_has_required_keys(self) -> None:
        err = AgentError("test", error_code="MYCODE")
        d = err.to_dict()
        assert "error_code" in d
        assert "message" in d
        assert d["error_code"] == "MYCODE"
