"""
Agent Definitions - All specialized agents for the Agent-Engineers orchestrator.
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
    "linear": "haiku",
    "jira": "haiku",
    "coding": "sonnet",
    "github": "haiku",
    "slack": "haiku",
    "pr_reviewer": "sonnet",
    "chatgpt": "haiku",
    "gemini": "haiku",
    "groq": "haiku",
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


def _get_jira_tools() -> list[str]:
    """Jira tools from Arcade MCP gateway + file tools."""
    return FILE_TOOLS + ["Bash"]


def create_agent_definitions() -> dict[str, AgentDefinition]:
    return {
        "linear": AgentDefinition(
            description="Manages Linear issues, project status, and session handoff.",
            prompt=_load_prompt("linear_agent_prompt"),
            tools=get_linear_tools() + FILE_TOOLS,
            model=_get_model("linear")),
        "jira": AgentDefinition(
            description="Manages Jira issues, sprint status, and session handoff via META issue.",
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
            description="Reviews PRs for quality, approves or requests changes, auto-merges approved PRs.",
            prompt=_load_prompt("pr_reviewer_agent_prompt"),
            tools=get_github_tools() + FILE_TOOLS + ["Bash"],
            model=_get_model("pr_reviewer")),
        "chatgpt": AgentDefinition(
            description=(
                "Provides access to OpenAI ChatGPT models (GPT-4o, o1, o3-mini, o4-mini). "
                "Use for cross-validation, ChatGPT-specific tasks, second opinions on code, "
                "or when the user explicitly requests ChatGPT."),
            prompt=_load_prompt("chatgpt_agent_prompt"),
            tools=FILE_TOOLS + ["Bash"],
            model=_get_model("chatgpt")),
        "gemini": AgentDefinition(
            description=(
                "Research with Google Search grounding, long-context analysis, "
                "second opinions. Uses Gemini 2.5 Flash/Pro via gemini-cli."),
            prompt=_load_prompt("gemini_agent_prompt"),
            tools=FILE_TOOLS + ["Bash"],
            model=_get_model("gemini")),
        "groq": AgentDefinition(
            description=(
                "Ultra-fast inference via Groq LPU. Use for speed-critical tasks, "
                "open-source models (Llama 3.3 70B), cross-validation, and compound AI."),
            prompt=_load_prompt("groq_agent_prompt"),
            tools=FILE_TOOLS + ["Bash"],
            model=_get_model("groq")),
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
GROQ_AGENT = AGENT_DEFINITIONS["groq"]
