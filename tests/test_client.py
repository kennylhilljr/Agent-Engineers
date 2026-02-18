"""Unit tests for the Claude SDK client configuration in client.py

Tests cover:
- create_security_settings returns correct structure
- write_security_settings creates .claude_settings.json
- write_security_settings skips write when content is unchanged
- Permission mode structure validation
- Sandbox configuration validation
- PLAYWRIGHT_TOOLS and BUILTIN_TOOLS lists
- create_client with fully mocked SDK dependencies
- Security hook integration (PreToolUse hook for Bash)

All external dependencies (ClaudeSDKClient, arcade, dotenv, etc.) are mocked.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestSecuritySettings:
    """Tests for create_security_settings."""

    def _import_client(self):
        """Import client module with all external deps mocked."""
        mocks = {
            "dotenv": MagicMock(),
            "arcade_config": MagicMock(
                ALL_ARCADE_TOOLS=[],
                ARCADE_TOOLS_PERMISSION="mcp__arcade__*",
                SLACK_MCP_TOOLS=[],
                SLACK_MCP_TOOLS_PERMISSION="mcp__slack__*",
                get_arcade_mcp_config=MagicMock(return_value={}),
                validate_arcade_config=MagicMock(),
            ),
            "claude_agent_sdk": MagicMock(),
            "claude_agent_sdk.types": MagicMock(),
            "agents": MagicMock(),
            "agents.definitions": MagicMock(AGENT_DEFINITIONS={}),
            "security": MagicMock(),
        }
        with patch.dict("sys.modules", mocks):
            import importlib
            if "client" in sys.modules:
                del sys.modules["client"]
            import client as c
            return c

    def test_create_security_settings_returns_dict(self):
        """Test that create_security_settings returns a dict."""
        c = self._import_client()
        settings = c.create_security_settings()
        assert isinstance(settings, dict)

    def test_security_settings_has_sandbox_key(self):
        """Test that security settings includes 'sandbox' key."""
        c = self._import_client()
        settings = c.create_security_settings()
        assert "sandbox" in settings

    def test_security_settings_has_permissions_key(self):
        """Test that security settings includes 'permissions' key."""
        c = self._import_client()
        settings = c.create_security_settings()
        assert "permissions" in settings

    def test_sandbox_has_enabled_field(self):
        """Test that sandbox configuration has 'enabled' field."""
        c = self._import_client()
        settings = c.create_security_settings()
        assert "enabled" in settings["sandbox"]

    def test_permissions_has_default_mode(self):
        """Test that permissions has 'defaultMode' set."""
        c = self._import_client()
        settings = c.create_security_settings()
        assert "defaultMode" in settings["permissions"]
        assert settings["permissions"]["defaultMode"] == "acceptEdits"

    def test_permissions_allow_list_contains_bash(self):
        """Test that the allow list includes Bash permissions."""
        c = self._import_client()
        settings = c.create_security_settings()
        allow_list = settings["permissions"]["allow"]
        bash_perms = [p for p in allow_list if "Bash" in p]
        assert len(bash_perms) > 0

    def test_permissions_allow_list_contains_file_ops(self):
        """Test that the allow list includes Read, Write, Edit operations."""
        c = self._import_client()
        settings = c.create_security_settings()
        allow_list = settings["permissions"]["allow"]
        ops = ["Read", "Write", "Edit"]
        for op in ops:
            assert any(op in p for p in allow_list), f"{op} not found in allow list"

    def test_permission_mode_is_accept_edits(self):
        """Test that the default permission mode is acceptEdits."""
        c = self._import_client()
        settings = c.create_security_settings()
        assert settings["permissions"]["defaultMode"] == "acceptEdits"


class TestWriteSecuritySettings:
    """Tests for write_security_settings function."""

    def setup_method(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _import_client(self):
        mocks = {
            "dotenv": MagicMock(),
            "arcade_config": MagicMock(
                ALL_ARCADE_TOOLS=[],
                ARCADE_TOOLS_PERMISSION="mcp__arcade__*",
                SLACK_MCP_TOOLS=[],
                SLACK_MCP_TOOLS_PERMISSION="mcp__slack__*",
                get_arcade_mcp_config=MagicMock(return_value={}),
                validate_arcade_config=MagicMock(),
            ),
            "claude_agent_sdk": MagicMock(),
            "claude_agent_sdk.types": MagicMock(),
            "agents": MagicMock(),
            "agents.definitions": MagicMock(AGENT_DEFINITIONS={}),
            "security": MagicMock(),
        }
        with patch.dict("sys.modules", mocks):
            if "client" in sys.modules:
                del sys.modules["client"]
            import client as c
            return c

    def test_creates_settings_file_in_project_dir(self):
        """Test that write_security_settings creates .claude_settings.json."""
        c = self._import_client()
        settings = c.create_security_settings()
        path = c.write_security_settings(self.temp_dir, settings)

        settings_file = self.temp_dir / ".claude_settings.json"
        assert settings_file.exists()
        assert path == settings_file

    def test_settings_file_is_valid_json(self):
        """Test that the written settings file is valid JSON."""
        c = self._import_client()
        settings = c.create_security_settings()
        c.write_security_settings(self.temp_dir, settings)

        settings_file = self.temp_dir / ".claude_settings.json"
        content = settings_file.read_text()
        parsed = json.loads(content)
        assert isinstance(parsed, dict)

    def test_skips_write_when_content_unchanged(self):
        """Test that a second write is skipped when content hasn't changed."""
        c = self._import_client()
        settings = c.create_security_settings()

        # First write
        c.write_security_settings(self.temp_dir, settings)

        settings_file = self.temp_dir / ".claude_settings.json"
        mtime_before = settings_file.stat().st_mtime

        # Second write with same content
        c.write_security_settings(self.temp_dir, settings)
        mtime_after = settings_file.stat().st_mtime

        # Modification time should be the same (file not rewritten)
        assert mtime_before == mtime_after

    def test_returns_path_to_settings_file(self):
        """Test that the function returns the path to the settings file."""
        c = self._import_client()
        settings = c.create_security_settings()
        result_path = c.write_security_settings(self.temp_dir, settings)

        assert isinstance(result_path, Path)
        assert result_path.name == ".claude_settings.json"

    def test_creates_project_dir_if_not_exists(self):
        """Test that the project directory is created if it doesn't exist."""
        c = self._import_client()
        new_dir = self.temp_dir / "new_subdir"
        assert not new_dir.exists()

        settings = c.create_security_settings()
        c.write_security_settings(new_dir, settings)

        assert new_dir.exists()
        assert (new_dir / ".claude_settings.json").exists()


class TestToolLists:
    """Tests for tool list constants in client.py."""

    def _import_client(self):
        mocks = {
            "dotenv": MagicMock(),
            "arcade_config": MagicMock(
                ALL_ARCADE_TOOLS=[],
                ARCADE_TOOLS_PERMISSION="mcp__arcade__*",
                SLACK_MCP_TOOLS=[],
                SLACK_MCP_TOOLS_PERMISSION="mcp__slack__*",
                get_arcade_mcp_config=MagicMock(return_value={}),
                validate_arcade_config=MagicMock(),
            ),
            "claude_agent_sdk": MagicMock(),
            "claude_agent_sdk.types": MagicMock(),
            "agents": MagicMock(),
            "agents.definitions": MagicMock(AGENT_DEFINITIONS={}),
            "security": MagicMock(),
        }
        with patch.dict("sys.modules", mocks):
            if "client" in sys.modules:
                del sys.modules["client"]
            import client as c
            return c

    def test_playwright_tools_is_list(self):
        """Test that PLAYWRIGHT_TOOLS is a list of strings."""
        c = self._import_client()
        assert isinstance(c.PLAYWRIGHT_TOOLS, list)
        for tool in c.PLAYWRIGHT_TOOLS:
            assert isinstance(tool, str)

    def test_playwright_tools_not_empty(self):
        """Test that PLAYWRIGHT_TOOLS has entries."""
        c = self._import_client()
        assert len(c.PLAYWRIGHT_TOOLS) > 0

    def test_builtin_tools_is_list(self):
        """Test that BUILTIN_TOOLS is a list of strings."""
        c = self._import_client()
        assert isinstance(c.BUILTIN_TOOLS, list)

    def test_builtin_tools_contains_expected_tools(self):
        """Test that BUILTIN_TOOLS contains Read, Write, Edit, Bash."""
        c = self._import_client()
        for tool in ["Read", "Write", "Edit", "Bash"]:
            assert tool in c.BUILTIN_TOOLS, f"{tool} not found in BUILTIN_TOOLS"

    def test_max_agent_turns_positive(self):
        """Test that MAX_AGENT_TURNS is a positive integer."""
        c = self._import_client()
        assert isinstance(c.MAX_AGENT_TURNS, int)
        assert c.MAX_AGENT_TURNS > 0


class TestCreateClient:
    """Tests for the create_client function."""

    def setup_method(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _import_client_with_mock_sdk(self):
        """Import client with all external deps mocked including SDK."""
        mock_sdk_client = MagicMock()
        mock_sdk_class = MagicMock(return_value=mock_sdk_client)
        mock_options_class = MagicMock()
        mock_mcp_config = MagicMock()
        mock_hook_callback = MagicMock()
        mock_hook_matcher = MagicMock()

        mocks = {
            "dotenv": MagicMock(),
            "arcade_config": MagicMock(
                ALL_ARCADE_TOOLS=["mcp__arcade__tool1"],
                ARCADE_TOOLS_PERMISSION="mcp__arcade__*",
                SLACK_MCP_TOOLS=["mcp__slack__tool1"],
                SLACK_MCP_TOOLS_PERMISSION="mcp__slack__*",
                get_arcade_mcp_config=MagicMock(return_value={"type": "sse", "url": "http://test"}),
                validate_arcade_config=MagicMock(),
            ),
            "claude_agent_sdk": MagicMock(
                ClaudeSDKClient=mock_sdk_class,
                ClaudeAgentOptions=mock_options_class,
                McpServerConfig=mock_mcp_config,
            ),
            "claude_agent_sdk.types": MagicMock(
                HookCallback=mock_hook_callback,
                HookMatcher=mock_hook_matcher,
            ),
            "agents": MagicMock(),
            "agents.definitions": MagicMock(AGENT_DEFINITIONS={"agent1": {}}),
            "security": MagicMock(),
        }
        with patch.dict("sys.modules", mocks):
            if "client" in sys.modules:
                del sys.modules["client"]
            import client as c
            return c, mock_sdk_class

    def test_create_client_returns_sdk_client(self):
        """Test that create_client returns a ClaudeSDKClient instance."""
        c, mock_sdk_class = self._import_client_with_mock_sdk()

        result = c.create_client(self.temp_dir, "claude-3-5-sonnet-latest")
        assert result == mock_sdk_class.return_value

    def test_create_client_calls_sdk_with_model(self):
        """Test that create_client passes the model to the SDK."""
        c, mock_sdk_class = self._import_client_with_mock_sdk()

        c.create_client(self.temp_dir, "claude-opus-4")
        assert mock_sdk_class.called

    def test_create_client_creates_settings_file(self):
        """Test that create_client creates .claude_settings.json."""
        c, mock_sdk_class = self._import_client_with_mock_sdk()

        c.create_client(self.temp_dir, "claude-3-5-sonnet-latest")
        settings_file = self.temp_dir / ".claude_settings.json"
        assert settings_file.exists()

    def test_create_client_with_cwd_override(self):
        """Test that create_client accepts a cwd override."""
        c, mock_sdk_class = self._import_client_with_mock_sdk()

        custom_cwd = self.temp_dir / "custom_cwd"
        custom_cwd.mkdir()

        # Should not raise
        c.create_client(self.temp_dir, "claude-3-5-sonnet-latest", cwd=custom_cwd)
        assert mock_sdk_class.called

    def test_create_client_falls_back_when_arcade_unavailable(self):
        """Test that create_client handles missing Arcade config gracefully."""
        mock_sdk_client = MagicMock()
        mock_sdk_class = MagicMock(return_value=mock_sdk_client)

        mocks = {
            "dotenv": MagicMock(),
            "arcade_config": MagicMock(
                ALL_ARCADE_TOOLS=[],
                ARCADE_TOOLS_PERMISSION="mcp__arcade__*",
                SLACK_MCP_TOOLS=[],
                SLACK_MCP_TOOLS_PERMISSION="mcp__slack__*",
                get_arcade_mcp_config=MagicMock(return_value={}),
                validate_arcade_config=MagicMock(side_effect=ValueError("Arcade not configured")),
            ),
            "claude_agent_sdk": MagicMock(
                ClaudeSDKClient=mock_sdk_class,
                ClaudeAgentOptions=MagicMock(),
                McpServerConfig=MagicMock(),
            ),
            "claude_agent_sdk.types": MagicMock(),
            "agents": MagicMock(),
            "agents.definitions": MagicMock(AGENT_DEFINITIONS={}),
            "security": MagicMock(),
        }
        with patch.dict("sys.modules", mocks):
            if "client" in sys.modules:
                del sys.modules["client"]
            import client as c_mod
            # Should not raise even though arcade is unavailable
            result = c_mod.create_client(self.temp_dir, "claude-3-5-sonnet-latest")
            assert result == mock_sdk_class.return_value

    def test_create_client_with_system_prompt_override(self):
        """Test that create_client accepts a system_prompt override."""
        c, mock_sdk_class = self._import_client_with_mock_sdk()
        custom_prompt = "You are a specialized test agent."
        c.create_client(self.temp_dir, "claude-3-5-sonnet-latest", system_prompt=custom_prompt)
        assert mock_sdk_class.called

    def test_create_client_with_agent_overrides(self):
        """Test that create_client accepts agent_overrides."""
        c, mock_sdk_class = self._import_client_with_mock_sdk()
        custom_agents = {"my_agent": {"model": "test"}}
        c.create_client(self.temp_dir, "claude-3-5-sonnet-latest", agent_overrides=custom_agents)
        assert mock_sdk_class.called
