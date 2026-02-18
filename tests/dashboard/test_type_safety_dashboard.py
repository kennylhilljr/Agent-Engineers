"""Type safety tests for dashboard module - AI-196.

Tests:
- ParsedIntent has proper type annotations
- AgentConfig has proper type annotations
- ProviderBridge has proper type annotations
- Runtime type checking for key functions
"""

import inspect
import sys
import typing
from dataclasses import fields as dc_fields
from pathlib import Path
from typing import get_type_hints

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dashboard.intent_parser import ParsedIntent, parse_intent
from dashboard.config import AgentConfig
from dashboard.provider_bridge import ProviderBridge


# ---------------------------------------------------------------------------
# ParsedIntent type annotation tests
# ---------------------------------------------------------------------------

class TestParsedIntentTypeAnnotations:
    """Tests for ParsedIntent type annotations."""

    def test_parsed_intent_has_intent_type_annotation(self):
        """intent_type field has str annotation."""
        hints = get_type_hints(ParsedIntent)
        assert "intent_type" in hints
        assert hints["intent_type"] == str

    def test_parsed_intent_agent_is_optional_str(self):
        """agent field is Optional[str]."""
        hints = get_type_hints(ParsedIntent)
        assert "agent" in hints
        # Optional[str] = Union[str, None]
        origin = getattr(hints["agent"], "__origin__", None)
        # In Python 3.11+, Optional[str] has __origin__ = typing.Union
        assert origin is typing.Union or hints["agent"] == typing.Optional[str]

    def test_parsed_intent_action_is_optional_str(self):
        """action field is Optional[str]."""
        hints = get_type_hints(ParsedIntent)
        assert "action" in hints
        origin = getattr(hints["action"], "__origin__", None)
        assert origin is typing.Union or hints["action"] == typing.Optional[str]

    def test_parsed_intent_params_is_dict(self):
        """params field is dict."""
        hints = get_type_hints(ParsedIntent)
        assert "params" in hints
        assert hints["params"] == dict

    def test_parsed_intent_original_message_is_str(self):
        """original_message field is str."""
        hints = get_type_hints(ParsedIntent)
        assert "original_message" in hints
        assert hints["original_message"] == str

    def test_all_expected_fields_present(self):
        """All expected fields are present in ParsedIntent."""
        field_names = {f.name for f in dc_fields(ParsedIntent)}
        assert "intent_type" in field_names
        assert "agent" in field_names
        assert "action" in field_names
        assert "params" in field_names
        assert "original_message" in field_names


# ---------------------------------------------------------------------------
# parse_intent() return type test
# ---------------------------------------------------------------------------

class TestParseIntentReturnType:
    """Tests for parse_intent() return type."""

    def test_parse_intent_returns_parsed_intent(self):
        """parse_intent() returns a ParsedIntent instance."""
        result = parse_intent("hello")
        assert isinstance(result, ParsedIntent)

    def test_parse_intent_intent_type_is_str(self):
        """parse_intent() returns ParsedIntent with str intent_type."""
        result = parse_intent("check AI-1")
        assert isinstance(result.intent_type, str)

    def test_parse_intent_agent_is_str_or_none(self):
        """parse_intent() agent is str or None."""
        result = parse_intent("hello")
        assert result.agent is None or isinstance(result.agent, str)

    def test_parse_intent_action_is_str_or_none(self):
        """parse_intent() action is str or None."""
        result = parse_intent("hello")
        assert result.action is None or isinstance(result.action, str)

    def test_parse_intent_params_is_dict(self):
        """parse_intent() params is always a dict."""
        result = parse_intent("check AI-5")
        assert isinstance(result.params, dict)

    def test_parse_intent_original_message_is_str(self):
        """parse_intent() original_message is always a str."""
        result = parse_intent("test message")
        assert isinstance(result.original_message, str)


# ---------------------------------------------------------------------------
# AgentConfig type annotation tests
# ---------------------------------------------------------------------------

class TestAgentConfigTypeAnnotations:
    """Tests for AgentConfig type annotations."""

    def test_agent_config_has_host_annotation(self):
        """host field is annotated."""
        hints = get_type_hints(AgentConfig)
        assert "host" in hints
        assert hints["host"] == str

    def test_agent_config_has_port_annotation(self):
        """port field is annotated as int."""
        hints = get_type_hints(AgentConfig)
        assert "port" in hints
        assert hints["port"] == int

    def test_agent_config_has_linear_api_key_annotation(self):
        """linear_api_key field is str."""
        hints = get_type_hints(AgentConfig)
        assert "linear_api_key" in hints
        assert hints["linear_api_key"] == str

    def test_agent_config_has_anthropic_api_key_annotation(self):
        """anthropic_api_key field is str."""
        hints = get_type_hints(AgentConfig)
        assert "anthropic_api_key" in hints
        assert hints["anthropic_api_key"] == str

    def test_agent_config_has_default_provider_annotation(self):
        """default_provider field is str."""
        hints = get_type_hints(AgentConfig)
        assert "default_provider" in hints
        assert hints["default_provider"] == str

    def test_agent_config_is_provider_configured_returns_bool(self):
        """is_provider_configured() returns bool at runtime."""
        config = AgentConfig()
        result = config.is_provider_configured("claude")
        assert isinstance(result, bool)

    def test_agent_config_from_env_returns_agent_config(self):
        """from_env() returns AgentConfig instance."""
        config = AgentConfig.from_env()
        assert isinstance(config, AgentConfig)


# ---------------------------------------------------------------------------
# ProviderBridge type annotation tests
# ---------------------------------------------------------------------------

class TestProviderBridgeTypeAnnotations:
    """Tests for ProviderBridge type annotations."""

    def test_provider_bridge_has_provider_name_attribute(self):
        """ProviderBridge has provider_name class attribute."""
        assert hasattr(ProviderBridge, "provider_name")
        assert isinstance(ProviderBridge.provider_name, str)

    def test_provider_bridge_send_message_has_annotations(self):
        """send_message() has return type annotation."""
        hints = get_type_hints(ProviderBridge.send_message)
        assert "return" in hints
        assert hints["return"] == str

    def test_provider_bridge_send_message_message_param_annotated(self):
        """send_message() message param is annotated as str."""
        hints = get_type_hints(ProviderBridge.send_message)
        assert "message" in hints
        assert hints["message"] == str

    def test_mock_response_is_static_method(self):
        """_mock_response is a static method."""
        assert isinstance(
            inspect.getattr_static(ProviderBridge, "_mock_response"),
            staticmethod
        )

    def test_mock_response_returns_str(self):
        """_mock_response returns a str."""
        result = ProviderBridge._mock_response("test", "hello")
        assert isinstance(result, str)
