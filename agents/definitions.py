"""
Agent Definitions - All orchestrator sub-agents including Jira, PR Reviewer,
ChatGPT, and Gemini for multi-AI orchestration.
"""

import os
from pathlib import Path
from typing import Final, Literal, TypeGuard

from claude_agent_sdk.types import AgentDefinition

from arcade_config import (
    get_linear_tools, get_github_tools, get_slack_tools, get_coding_tools,
)

FILE_TOOLS: list[str] = ["Read", "Write", "Edit", "Glob"]
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
ModelOption = Literal["haiku", "sonnet", "opus", "inherit"]
_VALID_MODELS: Final[tuple[str, ...]] = ("haiku", "sonnet", "opus", "inherit")

DEFAULT_MODELS: Final[dict[str, ModelOption]] = {
    "linear": "haiku", "jira": "haiku", "coding": "sonnet",
    "github": "haiku", "slack": "haiku", "pr_reviewer": "sonnet",
    "chatgpt": "haiku", "gemini": "haiku",
}


def _is_valid_model(value: str) -> TypeGuard[ModelOption]:
    return value in _VALID_MODELS


def _get_model(agent_name: str) -> ModelOption:
    env_var = f"{agent_name.upper()}_AGENT_MODEL"
    value = os.environ.get(env_var, "").lower().strip()
    if _is_valid_model(value):
        return value
    default = DEFAULT_MODELS.get(agent_name)
    if default is not None:
        return default
    return "haiku"


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text()


OrchestratorModelOption = Literal["haiku", "sonnet", "opus"]
_VALID_ORCHESTRATOR_MODELS: Final[tuple[str, ...]] = ("haiku", "sonnet", "opus")


def _is_valid_orchestrator_model(value: str) -> TypeGuard[OrchestratorModelOption]:
    return value in _VALID_ORCHESTRATOR_MODELS


def get_orchestrator_model() -> OrchestratorModelOption:
    value = os.environ.get("ORCHESTRATOR_MODEL", "").lower().strip()
    if _is_valid_orchestrator_model(value):
        return value
    return "haiku"


def _get_bridge_agent_tools() -> list[str]:
    """Tools for bridge agents (ChatGPT, Gemini) — file ops + bash."""
    return FILE_TOOLS + ["Bash"]


def _get_jira_tools() -> list[str]:
    """Tools for Jira agent — bash (curl) + file ops."""
    return FILE_TOOLS + ["Bash"]


def _get_pr_reviewer_tools() -> list[str]:
    """Tools for PR reviewer — GitHub MCP + file ops + bash."""
    return get_github_tools() + FILE_TOOLS + ["Bash"]


def create_agent_definitions() -> dict[str, AgentDefinition]:
    return {
        "linear": AgentDefinition(
            description="Manages Linear issues, project status, and session handoff.",
            prompt=_load_prompt("linear_agent_prompt"),
            tools=get_linear_tools() + FILE_TOOLS,
            model=_get_model("linear")),
        "jira": AgentDefinition(
            description=(
                "Manages Jira issues and project tracking via REST API. "
                "Alternative to Linear agent. Uses curl for Jira API calls."),
            prompt=_load_prompt("jira_agent_prompt"),
            tools=_get_jira_tools(),
            model=_get_model("jira")),
        "github": AgentDefinition(
            description="Handles Git commits, branches, and GitHub PRs.",
            prompt=_load_prompt("github_agent_prompt"),
            tools=get_github_tools() + FILE_TOOLS + ["Bash"],
            model=_get_model("github")),
        "slack": AgentDefinition(
            description="Sends Slack notifications to keep users informed.",
            prompt=_load_prompt("slack_agent_prompt"),
            tools=get_slack_tools() + FILE_TOOLS,
            model=_get_model("slack")),
        "coding": AgentDefinition(
            description="Writes and tests code.",
            prompt=_load_prompt("coding_agent_prompt"),
            tools=get_coding_tools(),
            model=_get_model("coding")),
        "pr_reviewer": AgentDefinition(
            description=(
                "Automated PR reviewer. Reviews PRs for quality, correctness, "
                "and test coverage. Approves and merges or requests changes."),
            prompt=_load_prompt("pr_reviewer_agent_prompt"),
            tools=_get_pr_reviewer_tools(),
            model=_get_model("pr_reviewer")),
        "chatgpt": AgentDefinition(
            description=(
                "Provides access to OpenAI ChatGPT models (GPT-4o, o1, o3-mini, o4-mini). "
                "Use for cross-validation, ChatGPT-specific tasks, second opinions on code, "
                "or when the user explicitly requests ChatGPT."),
            prompt=_load_prompt("chatgpt_agent_prompt"),
            tools=_get_bridge_agent_tools(),
            model=_get_model("chatgpt")),
        "gemini": AgentDefinition(
            description=(
                "Provides access to Google Gemini models (2.5 Flash, 2.5 Pro, 2.0 Flash). "
                "Use for cross-validation, research, Google ecosystem tasks, "
                "or large-context analysis (1M token window)."),
            prompt=_load_prompt("gemini_agent_prompt"),
            tools=_get_bridge_agent_tools(),
            model=_get_model("gemini")),
    }


AGENT_DEFINITIONS: dict[str, AgentDefinition] = create_agent_definitions()
LINEAR_AGENT = AGENT_DEFINITIONS["linear"]
JIRA_AGENT = AGENT_DEFINITIONS["jira"]
GITHUB_AGENT = AGENT_DEFINITIONS["github"]
SLACK_AGENT = AGENT_DEFINITIONS["slack"]
CODING_AGENT = AGENT_DEFINITIONS["coding"]
PR_REVIEWER_AGENT = AGENT_DEFINITIONS["pr_reviewer"]
CHATGPT_AGENT = AGENT_DEFINITIONS["chatgpt"]
GEMINI_AGENT = AGENT_DEFINITIONS["gemini"]
