"""Unit tests for bridges/base_bridge.py (BaseBridge ABC and BridgeResponse).

Tests cover:
- BridgeResponse dataclass fields, defaults, and equality
- BaseBridge cannot be instantiated directly (ABC enforcement)
- Concrete subclasses must implement all abstract methods
- provider_name abstract property is enforced
- send_task abstract method is enforced
- get_auth_info abstract method is enforced
- validate_response default implementation
- validate_response can be overridden
- __repr__ output format
- bridges package exports BaseBridge and BridgeResponse
"""

import asyncio
import sys
from dataclasses import fields
from pathlib import Path
from typing import Optional

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from bridges.base_bridge import BaseBridge, BridgeResponse


# ---------------------------------------------------------------------------
# Minimal concrete implementations for testing
# ---------------------------------------------------------------------------

class SimpleBridge(BaseBridge):
    """Minimal concrete bridge that echoes the task."""

    @property
    def provider_name(self) -> str:
        return "simple"

    async def send_task(self, task: str, **kwargs) -> BridgeResponse:
        return BridgeResponse(
            content=f"echo: {task}",
            model="simple-v1",
            provider=self.provider_name,
            tokens_used=len(task),
        )

    def get_auth_info(self) -> dict:
        return {"auth_type": "none", "api_key_set": "no"}


class FailingBridge(BaseBridge):
    """Bridge that always returns a failed response."""

    @property
    def provider_name(self) -> str:
        return "failing"

    async def send_task(self, task: str, **kwargs) -> BridgeResponse:
        return BridgeResponse(
            content="",
            model="failing-v1",
            provider=self.provider_name,
            success=False,
            error="simulated failure",
        )

    def get_auth_info(self) -> dict:
        return {"auth_type": "api_key", "api_key_set": "yes"}


class CustomValidatorBridge(BaseBridge):
    """Bridge that overrides validate_response to use custom logic."""

    @property
    def provider_name(self) -> str:
        return "custom"

    async def send_task(self, task: str, **kwargs) -> BridgeResponse:
        return BridgeResponse(content="", model="custom-v1", provider=self.provider_name)

    def get_auth_info(self) -> dict:
        return {}

    def validate_response(self, response: BridgeResponse) -> bool:
        # Accept any response where success=True, regardless of content
        return response.success


# ---------------------------------------------------------------------------
# BridgeResponse dataclass tests
# ---------------------------------------------------------------------------

class TestBridgeResponseFields:
    """Tests for BridgeResponse dataclass structure and defaults."""

    def test_required_fields_can_be_set(self):
        resp = BridgeResponse(content="hello", model="m1", provider="openai")
        assert resp.content == "hello"
        assert resp.model == "m1"
        assert resp.provider == "openai"

    def test_tokens_used_defaults_to_none(self):
        resp = BridgeResponse(content="x", model="m", provider="p")
        assert resp.tokens_used is None

    def test_error_defaults_to_none(self):
        resp = BridgeResponse(content="x", model="m", provider="p")
        assert resp.error is None

    def test_success_defaults_to_true(self):
        resp = BridgeResponse(content="x", model="m", provider="p")
        assert resp.success is True

    def test_all_fields_supplied(self):
        resp = BridgeResponse(
            content="result",
            model="gpt-4o",
            provider="openai",
            tokens_used=150,
            error=None,
            success=True,
        )
        assert resp.tokens_used == 150
        assert resp.success is True
        assert resp.error is None

    def test_failure_state(self):
        resp = BridgeResponse(
            content="",
            model="groq-llama",
            provider="groq",
            success=False,
            error="rate limit exceeded",
        )
        assert resp.success is False
        assert resp.error == "rate limit exceeded"
        assert resp.content == ""

    def test_is_dataclass_with_expected_field_names(self):
        field_names = {f.name for f in fields(BridgeResponse)}
        assert "content" in field_names
        assert "model" in field_names
        assert "provider" in field_names
        assert "tokens_used" in field_names
        assert "error" in field_names
        assert "success" in field_names

    def test_equality_same_values(self):
        r1 = BridgeResponse(content="a", model="m", provider="p")
        r2 = BridgeResponse(content="a", model="m", provider="p")
        assert r1 == r2

    def test_inequality_different_content(self):
        r1 = BridgeResponse(content="a", model="m", provider="p")
        r2 = BridgeResponse(content="b", model="m", provider="p")
        assert r1 != r2

    def test_tokens_used_accepts_integer(self):
        resp = BridgeResponse(content="x", model="m", provider="p", tokens_used=2048)
        assert resp.tokens_used == 2048

    def test_provider_field_stores_provider_name(self):
        for provider in ["openai", "gemini", "groq", "kimi", "windsurf"]:
            resp = BridgeResponse(content="x", model="m", provider=provider)
            assert resp.provider == provider


# ---------------------------------------------------------------------------
# BaseBridge ABC enforcement
# ---------------------------------------------------------------------------

class TestBaseBridgeABCEnforcement:
    """Tests that BaseBridge enforces the abstract contract."""

    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseBridge()  # type: ignore[abstract]

    def test_subclass_missing_provider_name_cannot_instantiate(self):
        class MissingProviderName(BaseBridge):
            async def send_task(self, task: str, **kwargs) -> BridgeResponse:
                return BridgeResponse(content="", model="", provider="")
            def get_auth_info(self) -> dict:
                return {}
        with pytest.raises(TypeError):
            MissingProviderName()  # type: ignore[abstract]

    def test_subclass_missing_send_task_cannot_instantiate(self):
        class MissingSendTask(BaseBridge):
            @property
            def provider_name(self) -> str:
                return "test"
            def get_auth_info(self) -> dict:
                return {}
        with pytest.raises(TypeError):
            MissingSendTask()  # type: ignore[abstract]

    def test_subclass_missing_get_auth_info_cannot_instantiate(self):
        class MissingGetAuthInfo(BaseBridge):
            @property
            def provider_name(self) -> str:
                return "test"
            async def send_task(self, task: str, **kwargs) -> BridgeResponse:
                return BridgeResponse(content="", model="", provider="")
        with pytest.raises(TypeError):
            MissingGetAuthInfo()  # type: ignore[abstract]

    def test_fully_implemented_subclass_instantiates(self):
        bridge = SimpleBridge()
        assert bridge is not None

    def test_concrete_is_instance_of_base_bridge(self):
        bridge = SimpleBridge()
        assert isinstance(bridge, BaseBridge)

    def test_base_bridge_is_abc(self):
        from abc import ABC
        assert issubclass(BaseBridge, ABC)


# ---------------------------------------------------------------------------
# provider_name property
# ---------------------------------------------------------------------------

class TestProviderNameProperty:
    """Tests for the provider_name abstract property."""

    def test_simple_bridge_provider_name(self):
        bridge = SimpleBridge()
        assert bridge.provider_name == "simple"

    def test_failing_bridge_provider_name(self):
        bridge = FailingBridge()
        assert bridge.provider_name == "failing"

    def test_provider_name_returns_string(self):
        for bridge in [SimpleBridge(), FailingBridge(), CustomValidatorBridge()]:
            assert isinstance(bridge.provider_name, str)
            assert len(bridge.provider_name) > 0


# ---------------------------------------------------------------------------
# send_task method
# ---------------------------------------------------------------------------

class TestSendTask:
    """Tests for the send_task abstract async method."""

    def test_send_task_returns_bridge_response(self):
        bridge = SimpleBridge()
        result = asyncio.get_event_loop().run_until_complete(
            bridge.send_task("test task")
        )
        assert isinstance(result, BridgeResponse)

    def test_send_task_content_reflects_input(self):
        bridge = SimpleBridge()
        result = asyncio.get_event_loop().run_until_complete(
            bridge.send_task("hello world")
        )
        assert "hello world" in result.content

    def test_send_task_tokens_used_set(self):
        bridge = SimpleBridge()
        task = "hi"
        result = asyncio.get_event_loop().run_until_complete(
            bridge.send_task(task)
        )
        assert result.tokens_used == len(task)

    def test_send_task_failure_response(self):
        bridge = FailingBridge()
        result = asyncio.get_event_loop().run_until_complete(
            bridge.send_task("anything")
        )
        assert result.success is False
        assert result.error == "simulated failure"
        assert result.content == ""

    def test_send_task_provider_matches(self):
        bridge = SimpleBridge()
        result = asyncio.get_event_loop().run_until_complete(
            bridge.send_task("task")
        )
        assert result.provider == "simple"


# ---------------------------------------------------------------------------
# get_auth_info method
# ---------------------------------------------------------------------------

class TestGetAuthInfo:
    """Tests for the get_auth_info abstract method."""

    def test_returns_dict(self):
        bridge = SimpleBridge()
        info = bridge.get_auth_info()
        assert isinstance(info, dict)

    def test_simple_bridge_has_auth_type(self):
        bridge = SimpleBridge()
        info = bridge.get_auth_info()
        assert "auth_type" in info
        assert info["auth_type"] == "none"

    def test_failing_bridge_has_api_key_info(self):
        bridge = FailingBridge()
        info = bridge.get_auth_info()
        assert "api_key_set" in info

    def test_custom_bridge_returns_empty_dict(self):
        bridge = CustomValidatorBridge()
        info = bridge.get_auth_info()
        assert isinstance(info, dict)


# ---------------------------------------------------------------------------
# validate_response method
# ---------------------------------------------------------------------------

class TestValidateResponse:
    """Tests for the validate_response concrete method and override."""

    def test_default_returns_true_for_success_with_content(self):
        bridge = SimpleBridge()
        resp = BridgeResponse(content="some content", model="m", provider="p")
        assert bridge.validate_response(resp) is True

    def test_default_returns_false_when_success_is_false(self):
        bridge = SimpleBridge()
        resp = BridgeResponse(content="content", model="m", provider="p", success=False)
        assert bridge.validate_response(resp) is False

    def test_default_returns_false_when_content_is_empty(self):
        bridge = SimpleBridge()
        resp = BridgeResponse(content="", model="m", provider="p")
        assert bridge.validate_response(resp) is False

    def test_default_returns_false_for_both_conditions_failing(self):
        bridge = SimpleBridge()
        resp = BridgeResponse(content="", model="m", provider="p", success=False)
        assert bridge.validate_response(resp) is False

    def test_custom_validate_accepts_empty_content_when_success_true(self):
        bridge = CustomValidatorBridge()
        resp = BridgeResponse(content="", model="custom-v1", provider="custom")
        # Custom logic: accept if success=True
        assert bridge.validate_response(resp) is True

    def test_custom_validate_rejects_success_false(self):
        bridge = CustomValidatorBridge()
        resp = BridgeResponse(
            content="some content", model="custom-v1", provider="custom", success=False
        )
        assert bridge.validate_response(resp) is False

    def test_validate_response_returns_bool(self):
        bridge = SimpleBridge()
        resp = BridgeResponse(content="x", model="m", provider="p")
        result = bridge.validate_response(resp)
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# __repr__ method
# ---------------------------------------------------------------------------

class TestRepr:
    """Tests for the BaseBridge __repr__ implementation."""

    def test_repr_contains_class_name(self):
        bridge = SimpleBridge()
        assert "SimpleBridge" in repr(bridge)

    def test_repr_contains_provider_name(self):
        bridge = SimpleBridge()
        assert "simple" in repr(bridge)

    def test_repr_exact_format(self):
        bridge = SimpleBridge()
        assert repr(bridge) == "SimpleBridge(provider=simple)"

    def test_repr_failing_bridge(self):
        bridge = FailingBridge()
        assert repr(bridge) == "FailingBridge(provider=failing)"

    def test_repr_custom_validator_bridge(self):
        bridge = CustomValidatorBridge()
        assert repr(bridge) == "CustomValidatorBridge(provider=custom)"


# ---------------------------------------------------------------------------
# Package-level import tests
# ---------------------------------------------------------------------------

class TestPackageImports:
    """Tests that BaseBridge and BridgeResponse are importable from bridges package."""

    def test_bridges_package_exports_base_bridge(self):
        import bridges
        assert hasattr(bridges, "BaseBridge")

    def test_bridges_package_exports_bridge_response(self):
        import bridges
        assert hasattr(bridges, "BridgeResponse")

    def test_base_bridge_module_importable(self):
        import bridges.base_bridge as bb
        assert hasattr(bb, "BaseBridge")
        assert hasattr(bb, "BridgeResponse")

    def test_base_bridge_from_package_is_same_class(self):
        import bridges
        from bridges.base_bridge import BaseBridge as DirectImport
        assert bridges.BaseBridge is DirectImport

    def test_bridge_response_from_package_is_same_class(self):
        import bridges
        from bridges.base_bridge import BridgeResponse as DirectImport
        assert bridges.BridgeResponse is DirectImport


# ---------------------------------------------------------------------------
# Shared interface contract across multiple implementations
# ---------------------------------------------------------------------------

class TestSharedInterface:
    """Tests that all concrete bridges share the expected interface."""

    @pytest.fixture
    def all_bridges(self):
        return [SimpleBridge(), FailingBridge(), CustomValidatorBridge()]

    def test_all_have_provider_name(self, all_bridges):
        for bridge in all_bridges:
            name = bridge.provider_name
            assert isinstance(name, str) and len(name) > 0

    def test_all_have_get_auth_info_returning_dict(self, all_bridges):
        for bridge in all_bridges:
            info = bridge.get_auth_info()
            assert isinstance(info, dict)

    def test_all_have_validate_response(self, all_bridges):
        resp = BridgeResponse(content="test", model="m", provider="p")
        for bridge in all_bridges:
            result = bridge.validate_response(resp)
            assert isinstance(result, bool)

    def test_all_are_instances_of_base_bridge(self, all_bridges):
        for bridge in all_bridges:
            assert isinstance(bridge, BaseBridge)

    def test_all_have_repr(self, all_bridges):
        for bridge in all_bridges:
            r = repr(bridge)
            assert bridge.__class__.__name__ in r
            assert bridge.provider_name in r
