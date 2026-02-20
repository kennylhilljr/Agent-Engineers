"""Expanded tests for dashboard/config.py - AI-194.

Covers:
- AgentConfig default values
- AgentConfig from_env()
- AgentConfig.is_provider_configured()
- AgentConfig host/port from env vars
- AgentConfig API key fields
- get_agent_config() singleton behavior
- reset_agent_config() for testing
- DashboardConfig validation (existing)
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dashboard.config import (
    AgentConfig,
    get_agent_config,
    reset_agent_config,
    DashboardConfig,
    get_config,
    reset_config,
)


@pytest.fixture(autouse=True)
def reset_configs():
    """Reset both config singletons before each test."""
    reset_config()
    reset_agent_config()
    yield
    reset_config()
    reset_agent_config()


# ---------------------------------------------------------------------------
# AgentConfig default values
# ---------------------------------------------------------------------------

class TestAgentConfigDefaults:
    """Tests for AgentConfig default values."""

    def test_default_host_is_localhost(self):
        """Default host is 'localhost'."""
        env = {k: v for k, v in os.environ.items()
               if k not in ("DASHBOARD_HOST",)}
        with patch.dict(os.environ, env, clear=True):
            config = AgentConfig()
            assert config.host == "localhost"

    def test_default_port_is_8420(self):
        """Default port is 8420."""
        env = {k: v for k, v in os.environ.items()
               if k not in ("DASHBOARD_PORT",)}
        with patch.dict(os.environ, env, clear=True):
            config = AgentConfig()
            assert config.port == 8420

    def test_default_provider_is_claude(self):
        """Default provider is 'claude'."""
        env = {k: v for k, v in os.environ.items()
               if k not in ("DEFAULT_PROVIDER",)}
        with patch.dict(os.environ, env, clear=True):
            config = AgentConfig()
            assert config.default_provider == "claude"

    def test_default_linear_api_key_is_empty(self):
        """Default linear_api_key is empty string."""
        env = {k: v for k, v in os.environ.items()
               if k not in ("LINEAR_API_KEY",)}
        with patch.dict(os.environ, env, clear=True):
            config = AgentConfig()
            assert config.linear_api_key == ""

    def test_default_anthropic_api_key_is_empty(self):
        """Default anthropic_api_key is empty string."""
        env = {k: v for k, v in os.environ.items()
               if k not in ("ANTHROPIC_API_KEY",)}
        with patch.dict(os.environ, env, clear=True):
            config = AgentConfig()
            assert config.anthropic_api_key == ""

    def test_default_openai_api_key_is_empty(self):
        """Default openai_api_key is empty string."""
        env = {k: v for k, v in os.environ.items()
               if k not in ("OPENAI_API_KEY",)}
        with patch.dict(os.environ, env, clear=True):
            config = AgentConfig()
            assert config.openai_api_key == ""


# ---------------------------------------------------------------------------
# AgentConfig from environment variables
# ---------------------------------------------------------------------------

class TestAgentConfigFromEnv:
    """Tests for AgentConfig reading from environment variables."""

    def test_host_from_env(self):
        """DASHBOARD_HOST env var sets host."""
        with patch.dict(os.environ, {"DASHBOARD_HOST": "0.0.0.0"}):
            config = AgentConfig()
            assert config.host == "0.0.0.0"

    def test_port_from_env(self):
        """DASHBOARD_PORT env var sets port."""
        with patch.dict(os.environ, {"DASHBOARD_PORT": "9000"}):
            config = AgentConfig()
            assert config.port == 9000

    def test_default_provider_from_env(self):
        """DEFAULT_PROVIDER env var sets default_provider."""
        with patch.dict(os.environ, {"DEFAULT_PROVIDER": "gemini"}):
            config = AgentConfig()
            assert config.default_provider == "gemini"

    def test_linear_api_key_from_env(self):
        """LINEAR_API_KEY env var sets linear_api_key."""
        with patch.dict(os.environ, {"LINEAR_API_KEY": "lin_test_key"}):
            config = AgentConfig()
            assert config.linear_api_key == "lin_test_key"

    def test_anthropic_api_key_from_env(self):
        """ANTHROPIC_API_KEY env var sets anthropic_api_key."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}):
            config = AgentConfig()
            assert config.anthropic_api_key == "sk-ant-test"

    def test_openai_api_key_from_env(self):
        """OPENAI_API_KEY env var sets openai_api_key."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-openai-test"}):
            config = AgentConfig()
            assert config.openai_api_key == "sk-openai-test"

    def test_from_env_classmethod_creates_agent_config(self):
        """from_env() classmethod creates an AgentConfig instance."""
        config = AgentConfig.from_env()
        assert isinstance(config, AgentConfig)


# ---------------------------------------------------------------------------
# AgentConfig.is_provider_configured() tests
# ---------------------------------------------------------------------------

class TestIsProviderConfigured:
    """Tests for AgentConfig.is_provider_configured()."""

    def test_claude_not_configured_by_default(self):
        """claude is not configured when anthropic_api_key is empty."""
        env = {k: v for k, v in os.environ.items()
               if k not in ("ANTHROPIC_API_KEY",)}
        with patch.dict(os.environ, env, clear=True):
            config = AgentConfig()
            assert config.is_provider_configured("claude") is False

    def test_claude_configured_with_key(self):
        """claude is configured when anthropic_api_key is set."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            config = AgentConfig()
            assert config.is_provider_configured("claude") is True

    def test_chatgpt_not_configured_without_key(self):
        """chatgpt is not configured when openai_api_key is empty."""
        env = {k: v for k, v in os.environ.items()
               if k not in ("OPENAI_API_KEY",)}
        with patch.dict(os.environ, env, clear=True):
            config = AgentConfig()
            assert config.is_provider_configured("chatgpt") is False

    def test_chatgpt_configured_with_key(self):
        """chatgpt is configured when openai_api_key is set."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            config = AgentConfig()
            assert config.is_provider_configured("chatgpt") is True

    def test_linear_configured_with_key(self):
        """linear is configured when linear_api_key is set."""
        with patch.dict(os.environ, {"LINEAR_API_KEY": "lin_key"}):
            config = AgentConfig()
            assert config.is_provider_configured("linear") is True

    def test_unknown_provider_returns_false(self):
        """Unknown provider returns False (no key map entry)."""
        config = AgentConfig()
        assert config.is_provider_configured("unknown_provider") is False


# ---------------------------------------------------------------------------
# get_agent_config() singleton tests
# ---------------------------------------------------------------------------

class TestGetAgentConfig:
    """Tests for get_agent_config() singleton."""

    def test_get_agent_config_returns_agent_config(self):
        """get_agent_config() returns an AgentConfig instance."""
        config = get_agent_config()
        assert isinstance(config, AgentConfig)

    def test_get_agent_config_returns_same_instance(self):
        """get_agent_config() returns the same singleton instance."""
        c1 = get_agent_config()
        c2 = get_agent_config()
        assert c1 is c2

    def test_reset_agent_config_clears_singleton(self):
        """reset_agent_config() forces re-creation on next call."""
        c1 = get_agent_config()
        reset_agent_config()
        c2 = get_agent_config()
        assert c1 is not c2
