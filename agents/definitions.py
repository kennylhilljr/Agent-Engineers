"""
Agent Definitions - All orchestrator sub-agents including PR Reviewer,
ChatGPT, Gemini, Groq, KIMI, and Windsurf for multi-AI orchestration.
"""

import os
from pathlib import Path
from typing import Final, Literal, NamedTuple, TypeGuard

from arcade_config import (
    get_coding_tools,
    get_github_tools,
    get_linear_tools,
    get_slack_tools,
)
from claude_agent_sdk.types import AgentDefinition

FILE_TOOLS: list[str] = ["Read", "Write", "Edit", "Glob"]
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
ModelOption = Literal["haiku", "sonnet", "opus", "inherit"]
_VALID_MODELS: Final[tuple[str, ...]] = ("haiku", "sonnet", "opus", "inherit")

DEFAULT_MODELS: Final[dict[str, ModelOption]] = {
    "linear": "haiku",
    "coding": "sonnet",
    "github": "haiku",
    "slack": "haiku",
    "pr_reviewer": "sonnet",
    "ops": "haiku",
    "coding_fast": "haiku",
    "pr_reviewer_fast": "haiku",
    "chatgpt": "haiku",
    "gemini": "haiku",
    "groq": "haiku",
    "kimi": "haiku",
    "windsurf": "haiku",
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


class GitIdentity(NamedTuple):
    """Git author identity for an agent."""

    name: str
    email: str


AGENT_GIT_IDENTITIES: Final[dict[str, GitIdentity]] = {
    "linear": GitIdentity("Linear Agent", "linear-agent@claude-agents.dev"),
    "github": GitIdentity("GitHub Agent", "github-agent@claude-agents.dev"),
    "slack": GitIdentity("Slack Agent", "slack-agent@claude-agents.dev"),
    "coding": GitIdentity("Coding Agent", "coding-agent@claude-agents.dev"),
    "pr_reviewer": GitIdentity("PR Reviewer Agent", "pr-reviewer-agent@claude-agents.dev"),
    "ops": GitIdentity("Ops Agent", "ops-agent@claude-agents.dev"),
    "coding_fast": GitIdentity("Coding Agent (Fast)", "coding-fast-agent@claude-agents.dev"),
    "pr_reviewer_fast": GitIdentity(
        "PR Reviewer Agent (Fast)", "pr-reviewer-fast-agent@claude-agents.dev"
    ),
    "chatgpt": GitIdentity("ChatGPT Bridge Agent", "chatgpt-agent@claude-agents.dev"),
    "gemini": GitIdentity("Gemini Bridge Agent", "gemini-agent@claude-agents.dev"),
    "groq": GitIdentity("Groq Bridge Agent", "groq-agent@claude-agents.dev"),
    "kimi": GitIdentity("KIMI Bridge Agent", "kimi-agent@claude-agents.dev"),
    "windsurf": GitIdentity("Windsurf Bridge Agent", "windsurf-agent@claude-agents.dev"),
}


def _build_git_identity_prompt(agent_name: str) -> str:
    """Build git identity instructions to append to an agent's prompt."""
    identity = AGENT_GIT_IDENTITIES.get(agent_name)
    if identity is None:
        return ""
    return f"""

### Git Identity (MANDATORY)

Your git identity is: **{identity.name} <{identity.email}>**

When making ANY git commit, you MUST include the `--author` flag:
```bash
git commit --author="{identity.name} <{identity.email}>" -m "your message"
```

Commits without `--author` will be BLOCKED by the security system.
"""


def _get_bridge_agent_tools() -> list[str]:
    """Tools for bridge agents (ChatGPT, Gemini, Groq, KIMI, Windsurf) — file ops + bash."""
    return FILE_TOOLS + ["Bash"]


def _get_pr_reviewer_tools() -> list[str]:
    """Tools for PR reviewer — GitHub MCP + file ops + bash."""
    return get_github_tools() + FILE_TOOLS + ["Bash"]


def _get_ops_agent_tools() -> list[str]:
    """Tools for ops agent — Linear + Slack + GitHub + file ops."""
    return get_linear_tools() + get_slack_tools() + get_github_tools() + FILE_TOOLS


def create_agent_definitions() -> dict[str, AgentDefinition]:
    def _prompt(name: str, prompt_file: str) -> str:
        return _load_prompt(prompt_file) + _build_git_identity_prompt(name)

    return {
        "linear": AgentDefinition(
            description="Manages Linear issues, project status, and session handoff.",
            prompt=_prompt("linear", "linear_agent_prompt"),
            tools=get_linear_tools() + FILE_TOOLS,
            model=_get_model("linear"),
        ),
        "github": AgentDefinition(
            description="Handles Git commits, branches, and GitHub PRs.",
            prompt=_prompt("github", "github_agent_prompt"),
            tools=get_github_tools() + FILE_TOOLS + ["Bash"],
            model=_get_model("github"),
        ),
        "slack": AgentDefinition(
            description="Sends Slack notifications to keep users informed.",
            prompt=_prompt("slack", "slack_agent_prompt"),
            tools=get_slack_tools() + FILE_TOOLS,
            model=_get_model("slack"),
        ),
        "coding": AgentDefinition(
            description="Writes and tests code.",
            prompt=_prompt("coding", "coding_agent_prompt"),
            tools=get_coding_tools(),
            model=_get_model("coding"),
        ),
        "pr_reviewer": AgentDefinition(
            description=(
                "Automated PR reviewer. Reviews PRs for quality, correctness, "
                "and test coverage. Approves and merges or requests changes."
            ),
            prompt=_prompt("pr_reviewer", "pr_reviewer_agent_prompt"),
            tools=_get_pr_reviewer_tools(),
            model=_get_model("pr_reviewer"),
        ),
        "ops": AgentDefinition(
            description=(
                "Composite operations agent. Handles all lightweight non-coding "
                "operations (Linear transitions, Slack notifications, GitHub labels) "
                "in a single delegation. Replaces sequential linear+slack+github calls."
            ),
            prompt=_prompt("ops", "ops_agent_prompt"),
            tools=_get_ops_agent_tools(),
            model=_get_model("ops"),
        ),
        "coding_fast": AgentDefinition(
            description=(
                "Fast coding agent using haiku. Use for simple changes: "
                "copy updates, CSS fixes, config changes, adding tests, "
                "renaming, documentation. Faster than the default coding agent."
            ),
            prompt=_prompt("coding_fast", "coding_agent_prompt"),
            tools=get_coding_tools(),
            model=_get_model("coding_fast"),
        ),
        "pr_reviewer_fast": AgentDefinition(
            description=(
                "Fast PR reviewer using haiku. Use for low-risk reviews: "
                "frontend-only changes, <= 3 files changed, no auth/db/API changes. "
                "Faster than the default PR reviewer."
            ),
            prompt=_prompt("pr_reviewer_fast", "pr_reviewer_agent_prompt"),
            tools=_get_pr_reviewer_tools(),
            model=_get_model("pr_reviewer_fast"),
        ),
        "chatgpt": AgentDefinition(
            description=(
                "Provides access to OpenAI ChatGPT models (GPT-4o, o1, o3-mini, o4-mini). "
                "Use for cross-validation, ChatGPT-specific tasks, second opinions on code, "
                "or when the user explicitly requests ChatGPT."
            ),
            prompt=_prompt("chatgpt", "chatgpt_agent_prompt"),
            tools=_get_bridge_agent_tools(),
            model=_get_model("chatgpt"),
        ),
        "gemini": AgentDefinition(
            description=(
                "Provides access to Google Gemini models (2.5 Flash, 2.5 Pro, 2.0 Flash). "
                "Use for cross-validation, research, Google ecosystem tasks, "
                "or large-context analysis (1M token window)."
            ),
            prompt=_prompt("gemini", "gemini_agent_prompt"),
            tools=_get_bridge_agent_tools(),
            model=_get_model("gemini"),
        ),
        "groq": AgentDefinition(
            description=(
                "Provides ultra-fast inference on open-source models (Llama 3.3 70B, "
                "Mixtral 8x7B, Gemma 2 9B) via Groq LPU hardware. Use for rapid "
                "cross-validation, bulk code review, or speed-critical tasks."
            ),
            prompt=_prompt("groq", "groq_agent_prompt"),
            tools=_get_bridge_agent_tools(),
            model=_get_model("groq"),
        ),
        "kimi": AgentDefinition(
            description=(
                "Provides access to Moonshot AI KIMI models with ultra-long context "
                "(up to 2M tokens). Use for analyzing entire codebases in one pass, "
                "bilingual Chinese/English tasks, or large-scale code analysis."
            ),
            prompt=_prompt("kimi", "kimi_agent_prompt"),
            tools=_get_bridge_agent_tools(),
            model=_get_model("kimi"),
        ),
        "windsurf": AgentDefinition(
            description=(
                "Runs Codeium Windsurf IDE in headless mode for parallel coding tasks. "
                "Use for cross-IDE validation, alternative implementations, or when "
                "Windsurf's Cascade model adds unique value to a coding task."
            ),
            prompt=_prompt("windsurf", "windsurf_agent_prompt"),
            tools=_get_bridge_agent_tools(),
            model=_get_model("windsurf"),
        ),
    }


def create_agent_definitions_for_pool(
    coding_model: str | None = None,
) -> dict[str, AgentDefinition]:
    """Create agent definitions with per-pool model overrides.

    Used by daemon_v2 to run coding workers with different models
    based on ticket complexity (e.g. haiku for trivial, opus for hard).

    Args:
        coding_model: Override model name for the coding agent.
            One of "haiku", "sonnet", "opus", or None to use the default.

    Returns:
        Agent definitions dict with the coding agent model overridden.
    """
    defs = create_agent_definitions()
    if coding_model is not None and coding_model in _VALID_MODELS:
        defs["coding"] = AgentDefinition(
            description=defs["coding"].description,
            prompt=defs["coding"].prompt,
            tools=defs["coding"].tools,
            model=coding_model,
        )
    return defs


AGENT_DEFINITIONS: dict[str, AgentDefinition] = create_agent_definitions()
LINEAR_AGENT = AGENT_DEFINITIONS["linear"]
GITHUB_AGENT = AGENT_DEFINITIONS["github"]
SLACK_AGENT = AGENT_DEFINITIONS["slack"]
CODING_AGENT = AGENT_DEFINITIONS["coding"]
PR_REVIEWER_AGENT = AGENT_DEFINITIONS["pr_reviewer"]
OPS_AGENT = AGENT_DEFINITIONS["ops"]
CODING_FAST_AGENT = AGENT_DEFINITIONS["coding_fast"]
PR_REVIEWER_FAST_AGENT = AGENT_DEFINITIONS["pr_reviewer_fast"]
CHATGPT_AGENT = AGENT_DEFINITIONS["chatgpt"]
GEMINI_AGENT = AGENT_DEFINITIONS["gemini"]
GROQ_AGENT = AGENT_DEFINITIONS["groq"]
KIMI_AGENT = AGENT_DEFINITIONS["kimi"]
WINDSURF_AGENT = AGENT_DEFINITIONS["windsurf"]
