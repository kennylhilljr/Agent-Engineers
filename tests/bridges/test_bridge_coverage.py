"""Comprehensive bridge coverage tests - AI-192.

Covers:
- ProviderBridge ABC cannot be instantiated directly
- All 6 concrete bridges: provider_name, is_available(), _mock_response()
- BridgeRegistry: get(), aliases, KeyError for unknown
- BridgeRegistry: list_available(), list_all()
- All bridges: send_message returns string when unavailable (mock response)
- All bridges: send_message_async returns string
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dashboard.provider_bridge import (
    ProviderBridge,
    ClaudeBridge,
    OpenAIBridge,
    GeminiBridge,
    GroqBridge,
    KimiBridge,
    WindsurfBridge,
    BridgeRegistry,
    get_registry,
    get_bridge,
)


# ---------------------------------------------------------------------------
# ProviderBridge ABC tests
# ---------------------------------------------------------------------------

class TestProviderBridgeABC:
    """Tests for the ProviderBridge abstract base class."""

    def test_cannot_instantiate_directly(self):
        """ProviderBridge is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            ProviderBridge()  # type: ignore

    def test_abc_has_provider_name_attribute(self):
        """ProviderBridge class has provider_name attribute."""
        assert hasattr(ProviderBridge, "provider_name")
        assert ProviderBridge.provider_name == "unknown"

    def test_mock_response_includes_provider_name(self):
        """_mock_response returns string with provider name in UPPER case."""
        resp = ProviderBridge._mock_response("claude", "test message")
        assert "CLAUDE" in resp

    def test_mock_response_includes_echo_of_message(self):
        """_mock_response echoes the message."""
        resp = ProviderBridge._mock_response("gemini", "hello world")
        assert "hello world" in resp

    def test_mock_response_truncates_long_messages(self):
        """_mock_response truncates messages to at most 120 chars."""
        # Use a message where first and second halves are distinct
        long_msg = "A" * 120 + "B" * 80  # 200 chars total
        resp = ProviderBridge._mock_response("groq", long_msg)
        # First 120 chars (all A's) should be present
        assert "A" * 120 in resp
        # The B characters beyond 120 should NOT appear
        assert "B" not in resp

    def test_concrete_subclass_requires_is_available_and_send_message(self):
        """A concrete subclass must implement is_available and send_message."""
        class MinimalBridge(ProviderBridge):
            provider_name = "test"
            def is_available(self): return False
            def send_message(self, message, context=None): return "ok"

        bridge = MinimalBridge()
        assert bridge.is_available() is False
        assert bridge.send_message("hi") == "ok"


# ---------------------------------------------------------------------------
# ClaudeBridge tests
# ---------------------------------------------------------------------------

class TestClaudeBridge:
    """Tests for ClaudeBridge."""

    def test_provider_name_is_claude(self):
        """ClaudeBridge.provider_name == 'claude'."""
        bridge = ClaudeBridge()
        assert bridge.provider_name == "claude"

    def test_is_available_returns_bool(self):
        """is_available() returns a bool."""
        bridge = ClaudeBridge()
        result = bridge.is_available()
        assert isinstance(result, bool)

    def test_is_available_false_without_api_key(self):
        """Without ANTHROPIC_API_KEY, is_available() returns False."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove key if present
            env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
            with patch.dict(os.environ, env, clear=True):
                bridge = ClaudeBridge()
                assert bridge.is_available() is False

    def test_send_message_returns_mock_when_unavailable(self):
        """send_message() returns mock response when not available."""
        bridge = ClaudeBridge()
        # Force unavailable
        bridge._api_key = ""
        bridge._client = None
        result = bridge.send_message("hello")
        assert isinstance(result, str)
        assert "CLAUDE" in result.upper() or "MOCK" in result.upper()

    @pytest.mark.asyncio
    async def test_send_message_async_returns_string_when_unavailable(self):
        """send_message_async() returns string when unavailable."""
        bridge = ClaudeBridge()
        bridge._api_key = ""
        bridge._client = None
        result = await bridge.send_message_async("test")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# OpenAIBridge tests
# ---------------------------------------------------------------------------

class TestOpenAIBridge:
    """Tests for OpenAIBridge."""

    def test_provider_name_is_chatgpt(self):
        """OpenAIBridge.provider_name == 'chatgpt'."""
        bridge = OpenAIBridge()
        assert bridge.provider_name == "chatgpt"

    def test_is_available_returns_bool(self):
        """is_available() returns bool."""
        bridge = OpenAIBridge()
        assert isinstance(bridge.is_available(), bool)

    def test_is_available_false_without_api_key(self):
        """Without OPENAI_API_KEY, is_available() returns False."""
        env = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            bridge = OpenAIBridge()
            assert bridge.is_available() is False

    def test_send_message_returns_mock_when_unavailable(self):
        """send_message() returns mock string when unavailable."""
        bridge = OpenAIBridge()
        bridge._api_key = ""
        bridge._bridge = None
        result = bridge.send_message("hello")
        assert isinstance(result, str)
        assert "MOCK" in result or "chatgpt" in result.lower() or "CHATGPT" in result

    @pytest.mark.asyncio
    async def test_send_message_async_returns_string(self):
        """send_message_async() returns string when unavailable."""
        bridge = OpenAIBridge()
        bridge._api_key = ""
        bridge._bridge = None
        result = await bridge.send_message_async("test")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# GeminiBridge tests
# ---------------------------------------------------------------------------

class TestGeminiBridge:
    """Tests for GeminiBridge."""

    def test_provider_name_is_gemini(self):
        """GeminiBridge.provider_name == 'gemini'."""
        bridge = GeminiBridge()
        assert bridge.provider_name == "gemini"

    def test_is_available_returns_bool(self):
        bridge = GeminiBridge()
        assert isinstance(bridge.is_available(), bool)

    def test_send_message_returns_mock_when_unavailable(self):
        bridge = GeminiBridge()
        bridge._api_key = ""
        bridge._bridge = None
        result = bridge.send_message("hello")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_send_message_async_returns_string(self):
        bridge = GeminiBridge()
        bridge._api_key = ""
        bridge._bridge = None
        result = await bridge.send_message_async("test")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# GroqBridge tests
# ---------------------------------------------------------------------------

class TestGroqBridge:
    """Tests for GroqBridge."""

    def test_provider_name_is_groq(self):
        """GroqBridge.provider_name == 'groq'."""
        bridge = GroqBridge()
        assert bridge.provider_name == "groq"

    def test_is_available_returns_bool(self):
        bridge = GroqBridge()
        assert isinstance(bridge.is_available(), bool)

    def test_send_message_returns_mock_when_unavailable(self):
        bridge = GroqBridge()
        bridge._api_key = ""
        bridge._bridge = None
        result = bridge.send_message("hello")
        assert isinstance(result, str)
        assert "GROQ" in result or "groq" in result.lower()

    @pytest.mark.asyncio
    async def test_send_message_async_returns_string(self):
        bridge = GroqBridge()
        bridge._api_key = ""
        bridge._bridge = None
        result = await bridge.send_message_async("test")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# KimiBridge tests
# ---------------------------------------------------------------------------

class TestKimiBridge:
    """Tests for KimiBridge."""

    def test_provider_name_is_kimi(self):
        """KimiBridge.provider_name == 'kimi'."""
        bridge = KimiBridge()
        assert bridge.provider_name == "kimi"

    def test_is_available_returns_bool(self):
        bridge = KimiBridge()
        assert isinstance(bridge.is_available(), bool)

    def test_send_message_returns_mock_when_unavailable(self):
        bridge = KimiBridge()
        bridge._api_key = ""
        bridge._bridge = None
        result = bridge.send_message("hello")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_send_message_async_returns_string(self):
        bridge = KimiBridge()
        bridge._api_key = ""
        bridge._bridge = None
        result = await bridge.send_message_async("test")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# WindsurfBridge tests
# ---------------------------------------------------------------------------

class TestWindsurfBridge:
    """Tests for WindsurfBridge."""

    def test_provider_name_is_windsurf(self):
        """WindsurfBridge.provider_name == 'windsurf'."""
        bridge = WindsurfBridge()
        assert bridge.provider_name == "windsurf"

    def test_is_available_returns_bool(self):
        bridge = WindsurfBridge()
        assert isinstance(bridge.is_available(), bool)

    def test_send_message_returns_string_when_unavailable(self):
        """send_message returns mock string when bridge is None."""
        bridge = WindsurfBridge()
        bridge._bridge = None
        result = bridge.send_message("hello")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_send_message_async_returns_string(self):
        bridge = WindsurfBridge()
        bridge._bridge = None
        result = await bridge.send_message_async("test")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# BridgeRegistry tests
# ---------------------------------------------------------------------------

class TestBridgeRegistry:
    """Tests for BridgeRegistry."""

    @pytest.fixture
    def registry(self):
        """Fresh BridgeRegistry instance."""
        return BridgeRegistry()

    def test_get_claude_returns_claude_bridge(self, registry):
        """registry.get('claude') returns a ClaudeBridge."""
        bridge = registry.get("claude")
        assert isinstance(bridge, ClaudeBridge)

    def test_get_chatgpt_returns_openai_bridge(self, registry):
        """registry.get('chatgpt') returns an OpenAIBridge."""
        bridge = registry.get("chatgpt")
        assert isinstance(bridge, OpenAIBridge)

    def test_get_gemini_returns_gemini_bridge(self, registry):
        """registry.get('gemini') returns a GeminiBridge."""
        bridge = registry.get("gemini")
        assert isinstance(bridge, GeminiBridge)

    def test_get_groq_returns_groq_bridge(self, registry):
        """registry.get('groq') returns a GroqBridge."""
        bridge = registry.get("groq")
        assert isinstance(bridge, GroqBridge)

    def test_get_kimi_returns_kimi_bridge(self, registry):
        """registry.get('kimi') returns a KimiBridge."""
        bridge = registry.get("kimi")
        assert isinstance(bridge, KimiBridge)

    def test_get_windsurf_returns_windsurf_bridge(self, registry):
        """registry.get('windsurf') returns a WindsurfBridge."""
        bridge = registry.get("windsurf")
        assert isinstance(bridge, WindsurfBridge)

    def test_alias_openai_maps_to_chatgpt(self, registry):
        """'openai' alias resolves to ChatGPT/OpenAIBridge."""
        bridge = registry.get("openai")
        assert isinstance(bridge, OpenAIBridge)

    def test_alias_anthropic_maps_to_claude(self, registry):
        """'anthropic' alias resolves to ClaudeBridge."""
        bridge = registry.get("anthropic")
        assert isinstance(bridge, ClaudeBridge)

    def test_alias_google_maps_to_gemini(self, registry):
        """'google' alias resolves to GeminiBridge."""
        bridge = registry.get("google")
        assert isinstance(bridge, GeminiBridge)

    def test_alias_moonshot_maps_to_kimi(self, registry):
        """'moonshot' alias resolves to KimiBridge."""
        bridge = registry.get("moonshot")
        assert isinstance(bridge, KimiBridge)

    def test_alias_cascade_maps_to_windsurf(self, registry):
        """'cascade' alias resolves to WindsurfBridge."""
        bridge = registry.get("cascade")
        assert isinstance(bridge, WindsurfBridge)

    def test_get_unknown_raises_key_error(self, registry):
        """Unknown provider name raises KeyError."""
        with pytest.raises(KeyError):
            registry.get("unknown_provider_xyz")

    def test_get_empty_string_raises_key_error(self, registry):
        """Empty string raises KeyError."""
        with pytest.raises(KeyError):
            registry.get("")

    def test_list_available_returns_list(self, registry):
        """get_available_bridges() returns a list."""
        available = registry.get_available_bridges()
        assert isinstance(available, list)

    def test_list_all_returns_all_6_bridges(self, registry):
        """all_bridges() returns all 6 bridge instances."""
        all_bridges = registry.all_bridges()
        assert len(all_bridges) == 6

    def test_list_all_contains_all_types(self, registry):
        """all_bridges() contains all bridge types."""
        all_bridges = registry.all_bridges()
        bridge_types = {type(b) for b in all_bridges}
        assert ClaudeBridge in bridge_types
        assert OpenAIBridge in bridge_types
        assert GeminiBridge in bridge_types
        assert GroqBridge in bridge_types
        assert KimiBridge in bridge_types
        assert WindsurfBridge in bridge_types

    def test_provider_names_returns_sorted_list(self, registry):
        """provider_names() returns sorted list of canonical names."""
        names = registry.provider_names()
        assert isinstance(names, list)
        assert sorted(names) == names
        assert "claude" in names
        assert "chatgpt" in names
        assert "gemini" in names

    def test_status_returns_dict_of_bools(self, registry):
        """status() returns dict mapping name -> bool."""
        status = registry.status()
        assert isinstance(status, dict)
        for name, available in status.items():
            assert isinstance(name, str)
            assert isinstance(available, bool)

    def test_case_insensitive_lookup(self, registry):
        """Provider names are normalized to lowercase for lookup."""
        bridge = registry.get("CLAUDE")
        assert isinstance(bridge, ClaudeBridge)
