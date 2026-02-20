"""Comprehensive tests for centralized configuration management (AI-205).

Tests cover:
- AgentConfig creation from environment variables
- APIKeys validation
- WindsurfMode enum values
- LogLevel enum values
- Default values
- get_config() singleton behavior
- reset_config() functionality
- validate() method
- Path configuration
- Port configuration
- Environment variable overrides
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    AgentConfig,
    APIKeys,
    LogLevel,
    WindsurfMode,
    get_config,
    reset_config,
)


# ---------------------------------------------------------------------------
# WindsurfMode enum tests
# ---------------------------------------------------------------------------

class TestWindsurfMode:
    def test_disabled_value(self):
        assert WindsurfMode.DISABLED.value == "disabled"

    def test_headless_value(self):
        assert WindsurfMode.HEADLESS.value == "headless"

    def test_interactive_value(self):
        assert WindsurfMode.INTERACTIVE.value == "interactive"

    def test_from_string_disabled(self):
        assert WindsurfMode("disabled") == WindsurfMode.DISABLED

    def test_from_string_headless(self):
        assert WindsurfMode("headless") == WindsurfMode.HEADLESS

    def test_from_string_interactive(self):
        assert WindsurfMode("interactive") == WindsurfMode.INTERACTIVE

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            WindsurfMode("unknown")


# ---------------------------------------------------------------------------
# LogLevel enum tests
# ---------------------------------------------------------------------------

class TestLogLevel:
    def test_debug_value(self):
        assert LogLevel.DEBUG.value == "debug"

    def test_info_value(self):
        assert LogLevel.INFO.value == "info"

    def test_warning_value(self):
        assert LogLevel.WARNING.value == "warning"

    def test_error_value(self):
        assert LogLevel.ERROR.value == "error"

    def test_from_string_info(self):
        assert LogLevel("info") == LogLevel.INFO

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            LogLevel("verbose")


# ---------------------------------------------------------------------------
# APIKeys tests
# ---------------------------------------------------------------------------

class TestAPIKeys:
    def test_default_all_none_when_no_env(self):
        with patch.dict(os.environ, {}, clear=True):
            keys = APIKeys()
        assert keys.anthropic is None
        assert keys.openai is None
        assert keys.gemini is None
        assert keys.groq is None
        assert keys.linear is None
        assert keys.github is None
        assert keys.slack is None
        assert keys.arcade is None

    def test_anthropic_key_from_env(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=True):
            keys = APIKeys()
        assert keys.anthropic == "sk-ant-test"

    def test_openai_key_from_env(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-openai-test"}, clear=True):
            keys = APIKeys()
        assert keys.openai == "sk-openai-test"

    def test_gemini_key_uses_gemini_api_key(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "gemini-test"}, clear=True):
            keys = APIKeys()
        assert keys.gemini == "gemini-test"

    def test_gemini_key_falls_back_to_google_api_key(self):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "google-test"}, clear=True):
            keys = APIKeys()
        assert keys.gemini == "google-test"

    def test_gemini_key_prefers_gemini_over_google(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "gemini-prio", "GOOGLE_API_KEY": "google-fallback"}, clear=True):
            keys = APIKeys()
        assert keys.gemini == "gemini-prio"

    def test_slack_key_from_env(self):
        with patch.dict(os.environ, {"SLACK_BOT_TOKEN": "xoxb-test"}, clear=True):
            keys = APIKeys()
        assert keys.slack == "xoxb-test"

    def test_arcade_key_from_env(self):
        with patch.dict(os.environ, {"ARCADE_API_KEY": "arcade-test"}, clear=True):
            keys = APIKeys()
        assert keys.arcade == "arcade-test"

    def test_validate_missing_anthropic(self):
        with patch.dict(os.environ, {}, clear=True):
            keys = APIKeys()
        errors = keys.validate()
        assert "ANTHROPIC_API_KEY" in errors

    def test_validate_passes_when_anthropic_present(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant"}, clear=True):
            keys = APIKeys()
        assert keys.validate() == []

    def test_github_key_from_env(self):
        with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp-test"}, clear=True):
            keys = APIKeys()
        assert keys.github == "ghp-test"

    def test_linear_key_from_env(self):
        with patch.dict(os.environ, {"LINEAR_API_KEY": "lin-test"}, clear=True):
            keys = APIKeys()
        assert keys.linear == "lin-test"

    def test_groq_key_from_env(self):
        with patch.dict(os.environ, {"GROQ_API_KEY": "groq-test"}, clear=True):
            keys = APIKeys()
        assert keys.groq == "groq-test"


# ---------------------------------------------------------------------------
# AgentConfig default values tests
# ---------------------------------------------------------------------------

class TestAgentConfigDefaults:
    def test_default_windsurf_mode_is_disabled(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = AgentConfig()
        assert cfg.windsurf_mode == WindsurfMode.DISABLED

    def test_default_timeout_is_300(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = AgentConfig()
        assert cfg.timeout == 300

    def test_default_log_level_is_info(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = AgentConfig()
        assert cfg.log_level == LogLevel.INFO

    def test_default_dashboard_port_is_8080(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = AgentConfig()
        assert cfg.dashboard_port == 8080

    def test_default_websocket_port_is_8765(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = AgentConfig()
        assert cfg.websocket_port == 8765

    def test_default_control_plane_port_is_9100(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = AgentConfig()
        assert cfg.control_plane_port == 9100

    def test_default_max_workers_is_4(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = AgentConfig()
        assert cfg.max_workers == 4

    def test_default_prompts_dir(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = AgentConfig()
        assert cfg.prompts_dir == Path("prompts")

    def test_default_screenshots_dir(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = AgentConfig()
        assert cfg.screenshots_dir == Path("screenshots")

    def test_default_github_repo_is_none(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = AgentConfig()
        assert cfg.github_repo is None

    def test_default_linear_team_id_is_none(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = AgentConfig()
        assert cfg.linear_team_id is None


# ---------------------------------------------------------------------------
# AgentConfig env var override tests
# ---------------------------------------------------------------------------

class TestAgentConfigEnvOverrides:
    def test_windsurf_mode_from_env(self):
        with patch.dict(os.environ, {"WINDSURF_MODE": "headless"}, clear=True):
            cfg = AgentConfig()
        assert cfg.windsurf_mode == WindsurfMode.HEADLESS

    def test_windsurf_mode_interactive_from_env(self):
        with patch.dict(os.environ, {"WINDSURF_MODE": "interactive"}, clear=True):
            cfg = AgentConfig()
        assert cfg.windsurf_mode == WindsurfMode.INTERACTIVE

    def test_timeout_from_env(self):
        with patch.dict(os.environ, {"AGENT_TIMEOUT": "600"}, clear=True):
            cfg = AgentConfig()
        assert cfg.timeout == 600

    def test_log_level_from_env(self):
        with patch.dict(os.environ, {"LOG_LEVEL": "debug"}, clear=True):
            cfg = AgentConfig()
        assert cfg.log_level == LogLevel.DEBUG

    def test_log_level_uppercase_from_env(self):
        with patch.dict(os.environ, {"LOG_LEVEL": "WARNING"}, clear=True):
            cfg = AgentConfig()
        assert cfg.log_level == LogLevel.WARNING

    def test_dashboard_port_from_env(self):
        with patch.dict(os.environ, {"DASHBOARD_PORT": "9090"}, clear=True):
            cfg = AgentConfig()
        assert cfg.dashboard_port == 9090

    def test_websocket_port_from_env(self):
        with patch.dict(os.environ, {"WEBSOCKET_PORT": "9000"}, clear=True):
            cfg = AgentConfig()
        assert cfg.websocket_port == 9000

    def test_control_plane_port_from_env(self):
        with patch.dict(os.environ, {"CONTROL_PLANE_PORT": "9200"}, clear=True):
            cfg = AgentConfig()
        assert cfg.control_plane_port == 9200

    def test_max_workers_from_env(self):
        with patch.dict(os.environ, {"MAX_WORKERS": "8"}, clear=True):
            cfg = AgentConfig()
        assert cfg.max_workers == 8

    def test_prompts_dir_from_env(self):
        with patch.dict(os.environ, {"PROMPTS_DIR": "/custom/prompts"}, clear=True):
            cfg = AgentConfig()
        assert cfg.prompts_dir == Path("/custom/prompts")

    def test_screenshots_dir_from_env(self):
        with patch.dict(os.environ, {"SCREENSHOTS_DIR": "/custom/screenshots"}, clear=True):
            cfg = AgentConfig()
        assert cfg.screenshots_dir == Path("/custom/screenshots")

    def test_github_repo_from_env(self):
        with patch.dict(os.environ, {"GITHUB_REPO": "org/repo"}, clear=True):
            cfg = AgentConfig()
        assert cfg.github_repo == "org/repo"

    def test_linear_team_id_from_env(self):
        with patch.dict(os.environ, {"LINEAR_TEAM_ID": "team-abc"}, clear=True):
            cfg = AgentConfig()
        assert cfg.linear_team_id == "team-abc"


# ---------------------------------------------------------------------------
# AgentConfig.from_env() tests
# ---------------------------------------------------------------------------

class TestAgentConfigFromEnv:
    def test_from_env_returns_agent_config(self):
        cfg = AgentConfig.from_env()
        assert isinstance(cfg, AgentConfig)

    def test_from_env_reads_timeout(self):
        with patch.dict(os.environ, {"AGENT_TIMEOUT": "120"}, clear=True):
            cfg = AgentConfig.from_env()
        assert cfg.timeout == 120

    def test_from_env_reads_api_keys(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-env"}, clear=True):
            cfg = AgentConfig.from_env()
        assert cfg.api_keys.anthropic == "sk-env"


# ---------------------------------------------------------------------------
# AgentConfig.validate() tests
# ---------------------------------------------------------------------------

class TestAgentConfigValidate:
    def test_validate_missing_anthropic_key(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = AgentConfig()
        errors = cfg.validate()
        assert "ANTHROPIC_API_KEY" in errors

    def test_validate_negative_timeout(self):
        with patch.dict(os.environ, {"AGENT_TIMEOUT": "-1", "ANTHROPIC_API_KEY": "sk"}, clear=True):
            cfg = AgentConfig()
        errors = cfg.validate()
        assert "AGENT_TIMEOUT must be positive" in errors

    def test_validate_zero_timeout(self):
        with patch.dict(os.environ, {"AGENT_TIMEOUT": "0", "ANTHROPIC_API_KEY": "sk"}, clear=True):
            cfg = AgentConfig()
        errors = cfg.validate()
        assert "AGENT_TIMEOUT must be positive" in errors

    def test_validate_low_dashboard_port(self):
        with patch.dict(os.environ, {"DASHBOARD_PORT": "80", "ANTHROPIC_API_KEY": "sk"}, clear=True):
            cfg = AgentConfig()
        errors = cfg.validate()
        assert "DASHBOARD_PORT must be >= 1024" in errors

    def test_validate_passes_with_all_required(self):
        env = {
            "ANTHROPIC_API_KEY": "sk-test",
            "AGENT_TIMEOUT": "300",
            "DASHBOARD_PORT": "8080",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = AgentConfig()
        assert cfg.validate() == []

    def test_is_valid_false_when_errors(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = AgentConfig()
        assert cfg.is_valid() is False

    def test_is_valid_true_when_no_errors(self):
        env = {
            "ANTHROPIC_API_KEY": "sk-test",
            "AGENT_TIMEOUT": "300",
            "DASHBOARD_PORT": "8080",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = AgentConfig()
        assert cfg.is_valid() is True


# ---------------------------------------------------------------------------
# get_config() singleton tests
# ---------------------------------------------------------------------------

class TestGetConfig:
    def setup_method(self):
        reset_config()

    def teardown_method(self):
        reset_config()

    def test_get_config_returns_agent_config(self):
        cfg = get_config()
        assert isinstance(cfg, AgentConfig)

    def test_get_config_singleton_same_instance(self):
        cfg1 = get_config()
        cfg2 = get_config()
        assert cfg1 is cfg2

    def test_get_config_after_reset_is_new_instance(self):
        cfg1 = get_config()
        reset_config()
        cfg2 = get_config()
        assert cfg1 is not cfg2

    def test_get_config_reads_env_vars(self):
        with patch.dict(os.environ, {"AGENT_TIMEOUT": "999"}, clear=True):
            cfg = get_config()
        assert cfg.timeout == 999


# ---------------------------------------------------------------------------
# reset_config() tests
# ---------------------------------------------------------------------------

class TestResetConfig:
    def setup_method(self):
        reset_config()

    def teardown_method(self):
        reset_config()

    def test_reset_clears_cached_config(self):
        cfg1 = get_config()
        reset_config()
        cfg2 = get_config()
        assert cfg1 is not cfg2

    def test_reset_allows_fresh_env_read(self):
        with patch.dict(os.environ, {"DASHBOARD_PORT": "8888"}, clear=True):
            cfg1 = get_config()
        assert cfg1.dashboard_port == 8888

        reset_config()

        with patch.dict(os.environ, {"DASHBOARD_PORT": "9999"}, clear=True):
            cfg2 = get_config()
        assert cfg2.dashboard_port == 9999

    def test_reset_can_be_called_multiple_times(self):
        reset_config()
        reset_config()
        reset_config()
        # Should not raise
        cfg = get_config()
        assert isinstance(cfg, AgentConfig)


# ---------------------------------------------------------------------------
# Path configuration tests
# ---------------------------------------------------------------------------

class TestPathConfiguration:
    def test_prompts_dir_is_path_type(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = AgentConfig()
        assert isinstance(cfg.prompts_dir, Path)

    def test_screenshots_dir_is_path_type(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = AgentConfig()
        assert isinstance(cfg.screenshots_dir, Path)

    def test_prompts_dir_custom_relative(self):
        with patch.dict(os.environ, {"PROMPTS_DIR": "custom/prompts"}, clear=True):
            cfg = AgentConfig()
        assert cfg.prompts_dir == Path("custom/prompts")

    def test_screenshots_dir_absolute_path(self):
        with patch.dict(os.environ, {"SCREENSHOTS_DIR": "/abs/screenshots"}, clear=True):
            cfg = AgentConfig()
        assert cfg.screenshots_dir == Path("/abs/screenshots")
        assert cfg.screenshots_dir.is_absolute()


# ---------------------------------------------------------------------------
# Port configuration tests
# ---------------------------------------------------------------------------

class TestPortConfiguration:
    def test_ports_are_integers(self):
        with patch.dict(os.environ, {}, clear=True):
            cfg = AgentConfig()
        assert isinstance(cfg.dashboard_port, int)
        assert isinstance(cfg.websocket_port, int)
        assert isinstance(cfg.control_plane_port, int)

    def test_dashboard_port_boundary_1024(self):
        with patch.dict(os.environ, {"DASHBOARD_PORT": "1024", "ANTHROPIC_API_KEY": "sk"}, clear=True):
            cfg = AgentConfig()
        errors = cfg.validate()
        assert "DASHBOARD_PORT must be >= 1024" not in errors

    def test_dashboard_port_boundary_1023_invalid(self):
        with patch.dict(os.environ, {"DASHBOARD_PORT": "1023", "ANTHROPIC_API_KEY": "sk"}, clear=True):
            cfg = AgentConfig()
        errors = cfg.validate()
        assert "DASHBOARD_PORT must be >= 1024" in errors

    def test_all_default_ports_are_valid(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk"}, clear=True):
            cfg = AgentConfig()
        assert cfg.dashboard_port >= 1024
        assert cfg.websocket_port >= 1024
        assert cfg.control_plane_port >= 1024


# ---------------------------------------------------------------------------
# APIKeys dataclass contains correct fields
# ---------------------------------------------------------------------------

class TestAPIKeysStructure:
    def test_api_keys_has_all_fields(self):
        keys = APIKeys()
        assert hasattr(keys, "anthropic")
        assert hasattr(keys, "openai")
        assert hasattr(keys, "gemini")
        assert hasattr(keys, "groq")
        assert hasattr(keys, "linear")
        assert hasattr(keys, "github")
        assert hasattr(keys, "slack")
        assert hasattr(keys, "arcade")

    def test_api_keys_validate_returns_list(self):
        with patch.dict(os.environ, {}, clear=True):
            keys = APIKeys()
        result = keys.validate()
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# AgentConfig integration test
# ---------------------------------------------------------------------------

class TestAgentConfigIntegration:
    def test_full_config_from_env(self):
        env = {
            "ANTHROPIC_API_KEY": "sk-ant-full",
            "OPENAI_API_KEY": "sk-openai-full",
            "WINDSURF_MODE": "headless",
            "AGENT_TIMEOUT": "120",
            "LOG_LEVEL": "debug",
            "DASHBOARD_PORT": "9000",
            "WEBSOCKET_PORT": "9001",
            "CONTROL_PLANE_PORT": "9002",
            "MAX_WORKERS": "2",
            "PROMPTS_DIR": "/prompts",
            "SCREENSHOTS_DIR": "/shots",
            "GITHUB_REPO": "org/repo",
            "LINEAR_TEAM_ID": "team-xyz",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = AgentConfig.from_env()

        assert cfg.api_keys.anthropic == "sk-ant-full"
        assert cfg.api_keys.openai == "sk-openai-full"
        assert cfg.windsurf_mode == WindsurfMode.HEADLESS
        assert cfg.timeout == 120
        assert cfg.log_level == LogLevel.DEBUG
        assert cfg.dashboard_port == 9000
        assert cfg.websocket_port == 9001
        assert cfg.control_plane_port == 9002
        assert cfg.max_workers == 2
        assert cfg.prompts_dir == Path("/prompts")
        assert cfg.screenshots_dir == Path("/shots")
        assert cfg.github_repo == "org/repo"
        assert cfg.linear_team_id == "team-xyz"
        assert cfg.is_valid() is True
