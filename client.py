"""
Claude SDK Client Configuration
===============================

Functions for creating and configuring the Claude Agent SDK client.
Uses Arcade MCP Gateway for Linear + GitHub + Slack integration.
"""

import json
from pathlib import Path
from typing import Literal, TypedDict, cast

from dotenv import load_dotenv

load_dotenv()

from arcade_config import (  # noqa: E402
    ALL_ARCADE_TOOLS,
    ARCADE_TOOLS_PERMISSION,
    get_arcade_mcp_config,
    validate_arcade_config,
)
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, McpServerConfig  # noqa: E402
from claude_agent_sdk.types import HookCallback, HookMatcher  # noqa: E402

from agents.definitions import AGENT_DEFINITIONS  # noqa: E402
from security import bash_security_hook  # noqa: E402

# Valid permission modes for the Claude SDK
PermissionMode = Literal["acceptEdits", "acceptAll", "reject", "ask"]


class SandboxConfig(TypedDict):
    """Sandbox configuration for bash command isolation."""

    enabled: bool
    autoAllowBashIfSandboxed: bool


class PermissionsConfig(TypedDict):
    """Permissions configuration for file and tool operations."""

    defaultMode: PermissionMode
    allow: list[str]


class SecuritySettings(TypedDict):
    """Complete security settings structure."""

    sandbox: SandboxConfig
    permissions: PermissionsConfig


# Playwright MCP tools for browser automation
PLAYWRIGHT_TOOLS: list[str] = [
    "mcp__playwright__browser_navigate",
    "mcp__playwright__browser_take_screenshot",
    "mcp__playwright__browser_click",
    "mcp__playwright__browser_type",
    "mcp__playwright__browser_select_option",
    "mcp__playwright__browser_hover",
    "mcp__playwright__browser_snapshot",
    "mcp__playwright__browser_wait_for",
]

# Built-in tools
BUILTIN_TOOLS: list[str] = [
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "Bash",
]

# Prompts directory
PROMPTS_DIR = Path(__file__).parent / "prompts"

# Maximum number of agent turns per session
MAX_AGENT_TURNS: int = 1000


def load_orchestrator_prompt() -> str:
    """Load the orchestrator system prompt."""
    return (PROMPTS_DIR / "orchestrator_prompt.md").read_text()


# ---------------------------------------------------------------------------
# Module-level caches to avoid redundant work across iterations
# ---------------------------------------------------------------------------

_cached_arcade_config: dict | None = None
_cached_orchestrator_prompt: str | None = None


def _get_cached_arcade_config() -> dict:
    """Return cached Arcade MCP config (created once per process)."""
    global _cached_arcade_config
    if _cached_arcade_config is None:
        _cached_arcade_config = get_arcade_mcp_config()
    return _cached_arcade_config


def _get_cached_orchestrator_prompt() -> str:
    """Return cached orchestrator prompt (loaded once per process)."""
    global _cached_orchestrator_prompt
    if _cached_orchestrator_prompt is None:
        _cached_orchestrator_prompt = load_orchestrator_prompt()
    return _cached_orchestrator_prompt


def create_security_settings() -> SecuritySettings:
    """
    Create the security settings structure.

    Returns:
        SecuritySettings with sandbox and permissions configured
    """
    return SecuritySettings(
        sandbox=SandboxConfig(enabled=True, autoAllowBashIfSandboxed=True),
        permissions=PermissionsConfig(
            defaultMode="acceptEdits",
            allow=[
                # Allow all file operations within the project directory
                "Read(./**)",
                "Write(./**)",
                "Edit(./**)",
                "Glob(./**)",
                "Grep(./**)",
                # Bash permission granted here, but actual commands are validated
                # by the bash_security_hook (see security.py for allowed commands)
                "Bash(*)",
                # Allow Playwright MCP tools for browser automation
                *PLAYWRIGHT_TOOLS,
                # Allow all Arcade MCP Gateway tools (Linear + GitHub + Slack)
                ARCADE_TOOLS_PERMISSION,
            ],
        ),
    )


def write_security_settings(project_dir: Path, settings: SecuritySettings) -> Path:
    """
    Write security settings to project directory (cached — skips if unchanged).

    Only writes the file if it doesn't exist or its content has changed.
    This avoids redundant disk writes on every session iteration.

    Args:
        project_dir: Directory to write settings to
        settings: Security settings to write

    Returns:
        Path to the settings file

    Raises:
        IOError: If settings file cannot be written
    """
    project_dir.mkdir(parents=True, exist_ok=True)
    settings_file: Path = project_dir / ".claude_settings.json"
    new_content = json.dumps(settings, indent=2)

    # Skip write if file already has identical content
    if settings_file.exists():
        try:
            existing = settings_file.read_text()
            if existing == new_content:
                return settings_file
        except OSError:
            pass  # File unreadable — rewrite it

    try:
        settings_file.write_text(new_content)
    except OSError as e:
        raise OSError(
            f"Failed to write security settings to {settings_file}: {e}\n"
            f"Check disk space and file permissions.\n"
            f"Agent cannot start without security settings."
        ) from e

    return settings_file


def create_client(
    project_dir: Path,
    model: str,
    cwd: Path | None = None,
    agent_overrides: dict | None = None,
) -> ClaudeSDKClient:
    """
    Create a Claude Agent SDK client with multi-layered security.

    Args:
        project_dir: Directory for the project
        model: Claude model to use
        cwd: Working directory override (defaults to project_dir).
            Used by daemon_v2 for worktree isolation.
        agent_overrides: Optional agent definitions to use instead of the
            default AGENT_DEFINITIONS. Used by daemon_v2 for per-pool
            model routing.

    Returns:
        Configured ClaudeSDKClient

    Raises:
        ValueError: If required environment variables are not set

    Security layers (defense in depth):
    1. Sandbox - OS-level bash command isolation prevents filesystem escape
       (bwrap/docker-style isolation)
    2. Permissions - File operations restricted to project_dir only
       (enforced by SDK before tool execution)
    3. Security hooks - Bash commands validated against an allowlist
       (runs pre-execution via PreToolUse hook, see security.py for ALLOWED_COMMANDS)

    Execution: Permissions checked first, then hooks run, finally sandbox executes.
    """
    # Validate Arcade configuration (cached after first call)
    validate_arcade_config()

    # Get Arcade MCP configuration (cached at module level)
    arcade_config = _get_cached_arcade_config()

    # Create and write security settings (cached — skips if unchanged)
    security_settings: SecuritySettings = create_security_settings()
    settings_file: Path = write_security_settings(project_dir, security_settings)

    print(f"Security settings: {settings_file}")
    print(f"   Sandbox: on | Dir: {project_dir.resolve()} | MCP: arcade")

    # Load orchestrator prompt (cached at module level)
    orchestrator_prompt = _get_cached_orchestrator_prompt()

    # Use provided agent definitions or fall back to defaults
    agents = agent_overrides if agent_overrides is not None else AGENT_DEFINITIONS

    # Use provided cwd or fall back to project_dir
    effective_cwd = cwd if cwd is not None else project_dir

    return ClaudeSDKClient(
        options=ClaudeAgentOptions(
            model=model,
            system_prompt=orchestrator_prompt,
            allowed_tools=[
                *BUILTIN_TOOLS,
                *PLAYWRIGHT_TOOLS,
                *ALL_ARCADE_TOOLS,
            ],
            mcp_servers=cast(
                dict[str, McpServerConfig],
                {
                    "playwright": {"command": "npx", "args": ["-y", "@playwright/mcp@latest"]},
                    "arcade": arcade_config,
                },
            ),
            hooks={
                "PreToolUse": [
                    HookMatcher(
                        matcher="Bash",
                        hooks=[cast(HookCallback, bash_security_hook)],
                    ),
                ],
            },
            agents=agents,
            max_turns=MAX_AGENT_TURNS,
            cwd=str(effective_cwd.resolve()),
            settings=str(settings_file.resolve()),
        )
    )
