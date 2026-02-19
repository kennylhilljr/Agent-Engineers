"""Tests for bridge refactoring: BaseBridge ABC and BridgeResponse dataclass.

Covers:
- BaseBridge cannot be instantiated directly (ABC enforcement)
- BridgeResponse dataclass creation and default values
- Concrete bridge implementations can inherit from BaseBridge
- validate_response method behaviour
- __repr__ method output
- Conditional imports of real bridge files
- Shared interface contract across all bridges
"""

import pytest
from dataclasses import fields
from typing import Optional

from bridges.base_bridge import BaseBridge, BridgeResponse


# ---------------------------------------------------------------------------
# Concrete implementations used only within tests
# ---------------------------------------------------------------------------

class MinimalBridge(BaseBridge):
    """Minimal concrete bridge for testing the abstract interface."""

    @property
    def provider_name(self) -> str:
        return "minimal"

    async def send_task(self, task: str, **kwargs) -> BridgeResponse:
        return BridgeResponse(
            content=f"echo: {task}",
            model="minimal-v1",
            provider=self.provider_name,
            tokens_used=len(task),
        )

    def get_auth_info(self) -> dict[str, str]:
        return {"auth_type": "none"}


class AnotherBridge(BaseBridge):
    """Second concrete bridge used to verify multiple implementations."""

    @property
    def provider_name(self) -> str:
        return "another"

    async def send_task(self, task: str, **kwargs) -> BridgeResponse:
        return BridgeResponse(
            content="",
            model="another-v1",
            provider=self.provider_name,
            success=False,
            error="simulated failure",
        )

    def get_auth_info(self) -> dict[str, str]:
        return {"api_key": "secret-key", "auth_type": "api_key"}


class OverriddenValidateBridge(BaseBridge):
    """Bridge that overrides validate_response to accept empty content."""

    @property
    def provider_name(self) -> str:
        return "custom-validator"

    async def send_task(self, task: str, **kwargs) -> BridgeResponse:
        return BridgeResponse(content="", model="cv-1", provider=self.provider_name)

    def get_auth_info(self) -> dict[str, str]:
        return {}

    def validate_response(self, response: BridgeResponse) -> bool:
        # Accept any successful response regardless of content
        return response.success


# ---------------------------------------------------------------------------
# BridgeResponse dataclass tests
# ---------------------------------------------------------------------------

class TestBridgeResponseDataclass:
    """Tests for the BridgeResponse dataclass."""

    def test_bridge_response_required_fields(self):
        """BridgeResponse requires content, model, and provider."""
        resp = BridgeResponse(content="hello", model="gpt-4o", provider="openai")
        assert resp.content == "hello"
        assert resp.model == "gpt-4o"
        assert resp.provider == "openai"

    def test_bridge_response_default_tokens_used_is_none(self):
        """tokens_used defaults to None."""
        resp = BridgeResponse(content="hi", model="m", provider="p")
        assert resp.tokens_used is None

    def test_bridge_response_default_error_is_none(self):
        """error defaults to None."""
        resp = BridgeResponse(content="hi", model="m", provider="p")
        assert resp.error is None

    def test_bridge_response_default_success_is_true(self):
        """success defaults to True."""
        resp = BridgeResponse(content="hi", model="m", provider="p")
        assert resp.success is True

    def test_bridge_response_with_all_fields(self):
        """BridgeResponse can be created with all fields supplied."""
        resp = BridgeResponse(
            content="result",
            model="gemini-2.5-flash",
            provider="gemini",
            tokens_used=42,
            error=None,
            success=True,
        )
        assert resp.tokens_used == 42
        assert resp.success is True

    def test_bridge_response_failure_state(self):
        """BridgeResponse models a failure correctly."""
        resp = BridgeResponse(
            content="",
            model="llama-3.3-70b",
            provider="groq",
            success=False,
            error="rate limit exceeded",
        )
        assert resp.success is False
        assert resp.error == "rate limit exceeded"
        assert resp.content == ""

    def test_bridge_response_is_dataclass(self):
        """BridgeResponse is a proper dataclass with the expected fields."""
        field_names = {f.name for f in fields(BridgeResponse)}
        assert "content" in field_names
        assert "model" in field_names
        assert "provider" in field_names
        assert "tokens_used" in field_names
        assert "error" in field_names
        assert "success" in field_names

    def test_bridge_response_tokens_used_accepts_int(self):
        """tokens_used field accepts integer values."""
        resp = BridgeResponse(content="x", model="m", provider="p", tokens_used=1024)
        assert resp.tokens_used == 1024

    def test_bridge_response_equality(self):
        """Two BridgeResponse instances with identical fields are equal."""
        r1 = BridgeResponse(content="a", model="m", provider="p")
        r2 = BridgeResponse(content="a", model="m", provider="p")
        assert r1 == r2

    def test_bridge_response_inequality(self):
        """Two BridgeResponse instances with differing fields are not equal."""
        r1 = BridgeResponse(content="a", model="m", provider="p")
        r2 = BridgeResponse(content="b", model="m", provider="p")
        assert r1 != r2


# ---------------------------------------------------------------------------
# BaseBridge ABC enforcement tests
# ---------------------------------------------------------------------------

class TestBaseBridgeABC:
    """Tests that BaseBridge enforces the abstract contract correctly."""

    def test_base_bridge_cannot_be_instantiated_directly(self):
        """Instantiating BaseBridge directly raises TypeError."""
        with pytest.raises(TypeError):
            BaseBridge()  # type: ignore[abstract]

    def test_missing_provider_name_raises_type_error(self):
        """A subclass missing provider_name cannot be instantiated."""
        class Incomplete(BaseBridge):
            async def send_task(self, task: str, **kwargs) -> BridgeResponse:
                return BridgeResponse(content="", model="", provider="")

            def get_auth_info(self) -> dict[str, str]:
                return {}

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_missing_send_task_raises_type_error(self):
        """A subclass missing send_task cannot be instantiated."""
        class Incomplete(BaseBridge):
            @property
            def provider_name(self) -> str:
                return "x"

            def get_auth_info(self) -> dict[str, str]:
                return {}

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_missing_get_auth_info_raises_type_error(self):
        """A subclass missing get_auth_info cannot be instantiated."""
        class Incomplete(BaseBridge):
            @property
            def provider_name(self) -> str:
                return "x"

            async def send_task(self, task: str, **kwargs) -> BridgeResponse:
                return BridgeResponse(content="", model="", provider="")

        with pytest.raises(TypeError):
            Incomplete()  # type: ignore[abstract]

    def test_complete_subclass_can_be_instantiated(self):
        """A fully implemented subclass can be instantiated without error."""
        bridge = MinimalBridge()
        assert bridge is not None

    def test_is_instance_of_base_bridge(self):
        """Concrete subclasses are instances of BaseBridge."""
        bridge = MinimalBridge()
        assert isinstance(bridge, BaseBridge)


# ---------------------------------------------------------------------------
# provider_name property tests
# ---------------------------------------------------------------------------

class TestProviderName:
    """Tests for the provider_name abstract property."""

    def test_provider_name_returns_string(self):
        """provider_name returns the correct string."""
        bridge = MinimalBridge()
        assert bridge.provider_name == "minimal"

    def test_provider_name_another_bridge(self):
        """provider_name returns the correct value for a second implementation."""
        bridge = AnotherBridge()
        assert bridge.provider_name == "another"


# ---------------------------------------------------------------------------
# send_task tests
# ---------------------------------------------------------------------------

class TestSendTask:
    """Tests for the send_task abstract method."""

    @pytest.mark.asyncio
    async def test_send_task_returns_bridge_response(self):
        """send_task returns a BridgeResponse instance."""
        bridge = MinimalBridge()
        response = await bridge.send_task("do something")
        assert isinstance(response, BridgeResponse)

    @pytest.mark.asyncio
    async def test_send_task_content_reflects_task(self):
        """MinimalBridge echoes the task in the response content."""
        bridge = MinimalBridge()
        response = await bridge.send_task("hello world")
        assert "hello world" in response.content

    @pytest.mark.asyncio
    async def test_send_task_failure_bridge(self):
        """AnotherBridge returns a failed BridgeResponse."""
        bridge = AnotherBridge()
        response = await bridge.send_task("anything")
        assert response.success is False
        assert response.error == "simulated failure"


# ---------------------------------------------------------------------------
# get_auth_info tests
# ---------------------------------------------------------------------------

class TestGetAuthInfo:
    """Tests for the get_auth_info abstract method."""

    def test_get_auth_info_returns_dict(self):
        """get_auth_info returns a dictionary."""
        bridge = MinimalBridge()
        info = bridge.get_auth_info()
        assert isinstance(info, dict)

    def test_get_auth_info_contains_auth_type(self):
        """MinimalBridge auth info contains auth_type key."""
        bridge = MinimalBridge()
        info = bridge.get_auth_info()
        assert "auth_type" in info

    def test_get_auth_info_api_key_bridge(self):
        """AnotherBridge auth info contains api_key and auth_type."""
        bridge = AnotherBridge()
        info = bridge.get_auth_info()
        assert "api_key" in info
        assert info["auth_type"] == "api_key"


# ---------------------------------------------------------------------------
# validate_response tests
# ---------------------------------------------------------------------------

class TestValidateResponse:
    """Tests for the validate_response default and overridden behaviour."""

    def test_validate_response_success_with_content(self):
        """Default validate_response returns True for successful non-empty response."""
        bridge = MinimalBridge()
        resp = BridgeResponse(content="some text", model="m", provider="p")
        assert bridge.validate_response(resp) is True

    def test_validate_response_false_when_success_false(self):
        """Default validate_response returns False when success is False."""
        bridge = MinimalBridge()
        resp = BridgeResponse(content="text", model="m", provider="p", success=False)
        assert bridge.validate_response(resp) is False

    def test_validate_response_false_when_content_empty(self):
        """Default validate_response returns False when content is empty string."""
        bridge = MinimalBridge()
        resp = BridgeResponse(content="", model="m", provider="p")
        assert bridge.validate_response(resp) is False

    def test_validate_response_can_be_overridden(self):
        """A subclass can override validate_response with custom logic."""
        bridge = OverriddenValidateBridge()
        resp = BridgeResponse(content="", model="cv-1", provider="custom-validator")
        # Empty content but success=True; custom logic accepts this
        assert bridge.validate_response(resp) is True

    def test_validate_response_override_rejects_failure(self):
        """Overridden validate_response still rejects success=False."""
        bridge = OverriddenValidateBridge()
        resp = BridgeResponse(
            content="", model="cv-1", provider="custom-validator", success=False
        )
        assert bridge.validate_response(resp) is False


# ---------------------------------------------------------------------------
# __repr__ tests
# ---------------------------------------------------------------------------

class TestRepr:
    """Tests for the BaseBridge __repr__ method."""

    def test_repr_contains_class_name(self):
        """__repr__ includes the concrete class name."""
        bridge = MinimalBridge()
        r = repr(bridge)
        assert "MinimalBridge" in r

    def test_repr_contains_provider_name(self):
        """__repr__ includes the provider name."""
        bridge = MinimalBridge()
        r = repr(bridge)
        assert "minimal" in r

    def test_repr_format(self):
        """__repr__ follows the expected format."""
        bridge = MinimalBridge()
        assert repr(bridge) == "MinimalBridge(provider=minimal)"

    def test_repr_another_bridge(self):
        """__repr__ works correctly for a second implementation."""
        bridge = AnotherBridge()
        assert repr(bridge) == "AnotherBridge(provider=another)"


# ---------------------------------------------------------------------------
# Import tests for real bridge files (conditional)
# ---------------------------------------------------------------------------

class TestBridgeImports:
    """Tests that bridge module files can be imported without crashing."""

    def test_base_bridge_importable(self):
        """bridges.base_bridge can be imported successfully."""
        import bridges.base_bridge as bb
        assert hasattr(bb, "BaseBridge")
        assert hasattr(bb, "BridgeResponse")

    def test_bridges_package_exports_base_bridge(self):
        """The bridges package exports BaseBridge via __init__.py."""
        import bridges
        assert hasattr(bridges, "BaseBridge")

    def test_bridges_package_exports_bridge_response(self):
        """The bridges package exports BridgeResponse via __init__.py."""
        import bridges
        assert hasattr(bridges, "BridgeResponse")

    def test_openai_bridge_importable(self):
        """openai_bridge module can be imported (dependencies optional)."""
        try:
            import openai_bridge  # noqa: F401
            assert True
        except ImportError as exc:
            pytest.skip(f"openai_bridge optional dependency missing: {exc}")

    def test_gemini_bridge_importable(self):
        """gemini_bridge module can be imported (dependencies optional)."""
        try:
            import gemini_bridge  # noqa: F401
            assert True
        except ImportError as exc:
            pytest.skip(f"gemini_bridge optional dependency missing: {exc}")

    def test_groq_bridge_importable(self):
        """groq_bridge module can be imported (dependencies optional)."""
        try:
            import groq_bridge  # noqa: F401
            assert True
        except ImportError as exc:
            pytest.skip(f"groq_bridge optional dependency missing: {exc}")


# ---------------------------------------------------------------------------
# Shared interface contract tests
# ---------------------------------------------------------------------------

class TestSharedInterface:
    """Tests that all concrete bridges share the expected interface."""

    def test_all_test_bridges_have_provider_name(self):
        """All concrete test bridges expose provider_name."""
        bridges_list = [MinimalBridge(), AnotherBridge(), OverriddenValidateBridge()]
        for bridge in bridges_list:
            assert isinstance(bridge.provider_name, str)
            assert len(bridge.provider_name) > 0

    def test_all_test_bridges_have_get_auth_info(self):
        """All concrete test bridges implement get_auth_info returning a dict."""
        bridges_list = [MinimalBridge(), AnotherBridge(), OverriddenValidateBridge()]
        for bridge in bridges_list:
            info = bridge.get_auth_info()
            assert isinstance(info, dict)

    def test_all_test_bridges_have_validate_response(self):
        """All concrete test bridges have validate_response callable."""
        bridges_list = [MinimalBridge(), AnotherBridge(), OverriddenValidateBridge()]
        resp = BridgeResponse(content="test", model="m", provider="p")
        for bridge in bridges_list:
            result = bridge.validate_response(resp)
            assert isinstance(result, bool)

    def test_base_bridge_is_abstract(self):
        """BaseBridge itself is recognised as an ABC."""
        from abc import ABC
        assert issubclass(BaseBridge, ABC)
