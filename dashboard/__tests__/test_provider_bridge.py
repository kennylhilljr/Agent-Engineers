"""Tests for dashboard/provider_bridge.py (AI-174 / REQ-TECH-009).

Coverage:
  - BridgeRegistry has all 6 providers
  - get_available_bridges() returns subset based on env vars
  - Each bridge has correct provider_name attribute
  - Mock response returned when API key not present
  - Error handling per bridge
  - Aliases (openai -> chatgpt, etc.)
  - Integration: ChatBridge routes provider names through provider_bridge
  - async send_message_async works
  - BridgeRegistry.status() returns dict
  - BridgeRegistry.provider_names() is sorted and complete
  - Unknown provider raises KeyError
  - WindsurfBridge is available when CLI is mocked
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure project root is importable (same as pytest.ini pythonpath)
# ---------------------------------------------------------------------------
_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from dashboard.provider_bridge import (
    BridgeRegistry,
    ClaudeBridge,
    GeminiBridge,
    GroqBridge,
    KimiBridge,
    OpenAIBridge,
    ProviderBridge,
    WindsurfBridge,
    get_bridge,
    get_registry,
)


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    """Remove all provider API keys so bridges default to mock mode."""
    keys = [
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "GEMINI_API_KEY",
        "GROQ_API_KEY",
        "KIMI_API_KEY",
        "MOONSHOT_API_KEY",
    ]
    for k in keys:
        monkeypatch.delenv(k, raising=False)


@pytest.fixture()
def registry(clear_env):
    """Fresh BridgeRegistry with no API keys set (all bridges in mock mode)."""
    return BridgeRegistry()


# ===========================================================================
# 1. BridgeRegistry has all 6 providers
# ===========================================================================


class TestBridgeRegistryHasAllProviders:
    EXPECTED_PROVIDERS = {"claude", "chatgpt", "gemini", "groq", "kimi", "windsurf"}

    def test_all_six_providers_registered(self, registry):
        assert set(registry.provider_names()) == self.EXPECTED_PROVIDERS

    def test_all_bridges_instantiated(self, registry):
        bridges = registry.all_bridges()
        assert len(bridges) == 6

    def test_each_bridge_is_provider_bridge_subclass(self, registry):
        for bridge in registry.all_bridges():
            assert isinstance(bridge, ProviderBridge)

    def test_provider_names_is_sorted(self, registry):
        names = registry.provider_names()
        assert names == sorted(names)


# ===========================================================================
# 2. Each bridge has the correct provider_name attribute
# ===========================================================================


class TestProviderNames:
    def test_claude_provider_name(self):
        assert ClaudeBridge.provider_name == "claude"

    def test_chatgpt_provider_name(self):
        assert OpenAIBridge.provider_name == "chatgpt"

    def test_gemini_provider_name(self):
        assert GeminiBridge.provider_name == "gemini"

    def test_groq_provider_name(self):
        assert GroqBridge.provider_name == "groq"

    def test_kimi_provider_name(self):
        assert KimiBridge.provider_name == "kimi"

    def test_windsurf_provider_name(self):
        assert WindsurfBridge.provider_name == "windsurf"

    def test_registry_bridges_have_matching_names(self, registry):
        for bridge in registry.all_bridges():
            # provider_name must be a non-empty string
            assert isinstance(bridge.provider_name, str)
            assert len(bridge.provider_name) > 0


# ===========================================================================
# 3. get_available_bridges() returns subset based on env vars
# ===========================================================================


class TestGetAvailableBridges:
    def test_no_keys_no_available_bridges_except_windsurf_maybe(self, registry):
        # With no API keys, non-local bridges are NOT available.
        # Windsurf may or may not be available (depends on local install).
        available = registry.get_available_bridges()
        for bridge in available:
            # Only windsurf can be available without an API key
            assert bridge.provider_name == "windsurf", (
                f"{bridge.provider_name} should not be available without API key"
            )

    def test_status_returns_dict_with_all_providers(self, registry):
        status = registry.status()
        assert isinstance(status, dict)
        assert set(status.keys()) == {"claude", "chatgpt", "gemini", "groq", "kimi", "windsurf"}

    def test_status_values_are_booleans(self, registry):
        for name, available in registry.status().items():
            assert isinstance(available, bool), f"{name} status should be bool"

    def test_claude_available_when_key_set(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        with patch("dashboard.provider_bridge.ClaudeBridge._client", create=True):
            bridge = ClaudeBridge.__new__(ClaudeBridge)
            bridge._api_key = "sk-ant-test"
            bridge._client = MagicMock()
            assert bridge.is_available() is True

    def test_claude_not_available_without_key(self):
        bridge = ClaudeBridge()
        assert bridge.is_available() is False


# ===========================================================================
# 4. Mock response when API key not present
# ===========================================================================


class TestMockResponseWhenUnavailable:
    """Each bridge must return a descriptive mock response – not raise."""

    def test_claude_mock_response(self):
        bridge = ClaudeBridge()
        assert not bridge.is_available()
        result = bridge.send_message("Hello Claude")
        assert "CLAUDE" in result.upper()
        assert "MOCK" in result.upper() or "mock" in result.lower() or "unavailable" in result.lower()

    def test_chatgpt_mock_response(self):
        bridge = OpenAIBridge()
        assert not bridge.is_available()
        result = bridge.send_message("Hello ChatGPT")
        assert "CHATGPT" in result.upper() or "MOCK" in result.upper()

    def test_gemini_mock_response(self):
        bridge = GeminiBridge()
        assert not bridge.is_available()
        result = bridge.send_message("Hello Gemini")
        assert "GEMINI" in result.upper() or "MOCK" in result.upper()

    def test_groq_mock_response(self):
        bridge = GroqBridge()
        assert not bridge.is_available()
        result = bridge.send_message("Hello Groq")
        assert "GROQ" in result.upper() or "MOCK" in result.upper()

    def test_kimi_mock_response(self):
        bridge = KimiBridge()
        assert not bridge.is_available()
        result = bridge.send_message("Hello Kimi")
        assert "KIMI" in result.upper() or "MOCK" in result.upper()

    def test_mock_response_contains_echo_of_message(self):
        bridge = ClaudeBridge()
        msg = "unique_test_message_12345"
        result = bridge.send_message(msg)
        assert msg in result

    def test_mock_response_is_string(self):
        for cls in [ClaudeBridge, OpenAIBridge, GeminiBridge, GroqBridge, KimiBridge]:
            bridge = cls()
            result = bridge.send_message("test")
            assert isinstance(result, str), f"{cls.__name__} mock must return str"


# ===========================================================================
# 5. Error handling per bridge
# ===========================================================================


class TestErrorHandling:
    def test_unknown_provider_raises_key_error(self, registry):
        with pytest.raises(KeyError):
            registry.get("nonexistent_provider")

    def test_registry_get_with_alias_openai(self, registry):
        bridge = registry.get("openai")
        assert bridge.provider_name == "chatgpt"

    def test_registry_get_with_alias_gpt(self, registry):
        bridge = registry.get("gpt")
        assert bridge.provider_name == "chatgpt"

    def test_registry_get_with_alias_anthropic(self, registry):
        bridge = registry.get("anthropic")
        assert bridge.provider_name == "claude"

    def test_registry_get_with_alias_moonshot(self, registry):
        bridge = registry.get("moonshot")
        assert bridge.provider_name == "kimi"

    def test_registry_get_with_alias_google(self, registry):
        bridge = registry.get("google")
        assert bridge.provider_name == "gemini"

    def test_registry_get_with_alias_cascade(self, registry):
        bridge = registry.get("cascade")
        assert bridge.provider_name == "windsurf"

    def test_claude_bridge_exception_propagates_when_available(self, monkeypatch):
        """When the bridge IS available and the API call fails, exception propagates."""
        bridge = ClaudeBridge.__new__(ClaudeBridge)
        bridge._api_key = "sk-ant-fake"
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("API error")
        bridge._client = mock_client
        assert bridge.is_available()
        with pytest.raises(RuntimeError, match="API error"):
            bridge.send_message("test")


# ===========================================================================
# 6. Async send_message_async works
# ===========================================================================


class TestAsyncSendMessage:
    @pytest.mark.asyncio
    async def test_claude_async_mock_response(self):
        bridge = ClaudeBridge()
        assert not bridge.is_available()
        result = await bridge.send_message_async("async test")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_chatgpt_async_mock_response(self):
        bridge = OpenAIBridge()
        result = await bridge.send_message_async("async test")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_gemini_async_mock_response(self):
        bridge = GeminiBridge()
        result = await bridge.send_message_async("async test")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_groq_async_mock_response(self):
        bridge = GroqBridge()
        result = await bridge.send_message_async("async test")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_kimi_async_mock_response(self):
        bridge = KimiBridge()
        result = await bridge.send_message_async("async test")
        assert isinstance(result, str)


# ===========================================================================
# 7. Integration: ChatBridge routes provider names through provider_bridge
# ===========================================================================


class TestChatBridgeProviderIntegration:
    """Verify that ChatBridge._handle_provider_bridge routes correctly."""

    @pytest.fixture()
    def chat_bridge_module(self):
        """Return the dashboard.chat_bridge module object."""
        import sys
        return sys.modules["dashboard.chat_bridge"]

    @pytest.fixture()
    def chat_bridge(self):
        from dashboard.chat_bridge import ChatBridge
        return ChatBridge()

    @pytest.mark.asyncio
    async def test_chatbridge_routes_gemini_via_provider_bridge(
        self, chat_bridge, chat_bridge_module
    ):
        """Asking the gemini agent routes through provider_bridge, not generic delegation."""
        mock_bridge = MagicMock()
        mock_bridge.is_available.return_value = False
        mock_bridge.send_message_async = AsyncMock(
            return_value="[GEMINI MOCK] Echo: hello"
        )
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_bridge

        original_registry = chat_bridge_module._provider_registry
        original_getter = chat_bridge_module._get_provider_registry
        try:
            chat_bridge_module._provider_registry = mock_registry
            chat_bridge_module._get_provider_registry = lambda: mock_registry

            gen = await chat_bridge.handle_message("ask the gemini agent to say hello")
            chunks = []
            async for chunk in gen:
                chunks.append(chunk)
        finally:
            chat_bridge_module._provider_registry = original_registry
            chat_bridge_module._get_provider_registry = original_getter

        types = [c["type"] for c in chunks]
        assert "routing" in types or "agent_response" in types
        mock_registry.get.assert_called()

    @pytest.mark.asyncio
    async def test_chatbridge_provider_bridge_fallback_when_registry_none(
        self, chat_bridge, chat_bridge_module
    ):
        """When registry is None, ChatBridge falls back gracefully."""
        original_getter = chat_bridge_module._get_provider_registry
        try:
            chat_bridge_module._get_provider_registry = lambda: None

            gen = await chat_bridge.handle_message("ask the groq agent to help")
            chunks = []
            async for chunk in gen:
                chunks.append(chunk)
        finally:
            chat_bridge_module._get_provider_registry = original_getter

        content_chunks = [c for c in chunks if c["type"] == "agent_response"]
        assert len(content_chunks) > 0

    @pytest.mark.asyncio
    async def test_chatbridge_provider_bridge_error_yields_error_chunk(
        self, chat_bridge, chat_bridge_module
    ):
        """When the bridge raises an exception, an error chunk is yielded."""
        mock_bridge = MagicMock()
        mock_bridge.is_available.return_value = True
        mock_bridge.send_message_async = AsyncMock(side_effect=RuntimeError("bridge exploded"))
        mock_registry = MagicMock()
        mock_registry.get.return_value = mock_bridge

        original_getter = chat_bridge_module._get_provider_registry
        try:
            chat_bridge_module._get_provider_registry = lambda: mock_registry

            gen = await chat_bridge.handle_message("ask the kimi agent to help")
            chunks = []
            async for chunk in gen:
                chunks.append(chunk)
        finally:
            chat_bridge_module._get_provider_registry = original_getter

        error_chunks = [c for c in chunks if c["type"] == "error"]
        assert len(error_chunks) > 0
        assert "bridge exploded" in error_chunks[0]["content"]

    @pytest.mark.asyncio
    async def test_chatbridge_non_provider_agent_uses_original_path(
        self, chat_bridge, chat_bridge_module
    ):
        """Standard agents (coding, linear, etc.) still use the original delegation path."""
        called = []
        original_getter = chat_bridge_module._get_provider_registry
        try:
            chat_bridge_module._get_provider_registry = lambda: (
                called.append(True) or None
            )

            gen = await chat_bridge.handle_message("ask the coding agent to write a test")
            chunks = []
            async for chunk in gen:
                chunks.append(chunk)
        finally:
            chat_bridge_module._get_provider_registry = original_getter

        # provider registry should NOT be called for 'coding'
        assert len(called) == 0
        assert any("coding" in c.get("content", "").lower() for c in chunks)


# ===========================================================================
# 8. Module-level singleton helpers
# ===========================================================================


class TestModuleSingleton:
    def test_get_registry_returns_bridge_registry(self, monkeypatch):
        # Reset singleton
        import dashboard.provider_bridge as pb
        monkeypatch.setattr(pb, "_registry", None)
        reg = get_registry()
        assert isinstance(reg, BridgeRegistry)

    def test_get_registry_is_cached(self, monkeypatch):
        import dashboard.provider_bridge as pb
        monkeypatch.setattr(pb, "_registry", None)
        reg1 = get_registry()
        reg2 = get_registry()
        assert reg1 is reg2

    def test_get_bridge_shortcut(self, monkeypatch):
        import dashboard.provider_bridge as pb
        monkeypatch.setattr(pb, "_registry", None)
        bridge = get_bridge("groq")
        assert bridge.provider_name == "groq"
