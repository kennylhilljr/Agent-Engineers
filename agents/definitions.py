"""
Agent Definitions - All orchestrator sub-agents including PR Reviewer,
ChatGPT, Gemini, Groq, KIMI, and Windsurf for multi-AI orchestration.
"""

import os
import sys
from pathlib import Path
from typing import Final, Literal, NamedTuple

# TypeGuard is only available in Python 3.10+
if sys.version_info >= (3, 10):
    from typing import TypeGuard
else:
    try:
        from typing_extensions import TypeGuard
    except ImportError:
        # Fallback for Python 3.9 without typing_extensions
        TypeGuard = type  # type: ignore

from arcade_config import (
    get_coding_tools,
    get_github_tools,
    get_linear_tools,
    get_slack_tools,
)
from claude_agent_sdk.types import AgentDefinition
from agents.model_routing import (
    CostTracker,
    ModelTier,
    check_cost_cap,
    estimate_complexity,
    get_cost_cap_for_org,
    select_model,
)

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
    "openrouter_dev": "haiku",
    "product_manager": "sonnet",
    "designer": "haiku",
    "jira": "haiku",
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
    "openrouter_dev": GitIdentity(
        "OpenRouter Dev Agent", "openrouter-dev-agent@claude-agents.dev"
    ),
    "product_manager": GitIdentity(
        "Product Manager Agent", "product-manager-agent@claude-agents.dev"
    ),
    "designer": GitIdentity("Designer Agent", "designer-agent@claude-agents.dev"),
    "jira": GitIdentity("Jira Agent", "jira-agent@claude-agents.dev"),
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


def _get_pm_agent_tools() -> list[str]:
    """Tools for product manager — Slack + Linear + GitHub + file ops + bash."""
    return (
        get_slack_tools() + get_linear_tools() + get_github_tools()
        + FILE_TOOLS + ["Bash", "Grep"]
    )


def _get_designer_agent_tools() -> list[str]:
    """Tools for designer agent — file ops + bash + Slack for collaboration."""
    return get_slack_tools() + FILE_TOOLS + ["Bash", "Grep"]


def _get_jira_agent_tools() -> list[str]:
    """Tools for Jira integration agent — Jira MCP + file ops + bash."""
    # Import here to avoid circular imports at module load time
    try:
        from arcade_config import get_jira_tools  # type: ignore[import]
        return get_jira_tools() + FILE_TOOLS + ["Bash"]
    except (ImportError, AttributeError):
        # Jira MCP tools not yet configured — fall back to file ops only
        return FILE_TOOLS + ["Bash"]


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
        "openrouter_dev": AgentDefinition(
            description=(
                "Provides access to 200+ models via OpenRouter (DeepSeek, Llama, Gemma, "
                "Mistral). Use for multi-provider fallback, free-tier parallel coding, "
                "or cost-optimized bulk tasks."
            ),
            prompt=_prompt("openrouter_dev", "openrouter_dev_agent_prompt"),
            tools=_get_bridge_agent_tools(),
            model=_get_model("openrouter_dev"),
        ),
        "product_manager": AgentDefinition(
            description=(
                "Manages product strategy, backlog grooming, sprint planning, and "
                "cross-agent coordination. Creates and assigns issues including "
                "[DESIGN]-prefixed tasks for the Designer agent."
            ),
            prompt=_prompt("product_manager", "product_manager_agent_prompt"),
            tools=_get_pm_agent_tools(),
            model=_get_model("product_manager"),
        ),
        "designer": AgentDefinition(
            description=(
                "UI/UX design specialist. Creates design systems, component specs, "
                "CSS implementations, and accessibility audits. Works on [DESIGN]-prefixed "
                "issues assigned by the Product Manager."
            ),
            prompt=_prompt("designer", "designer_agent_prompt"),
            tools=_get_designer_agent_tools(),
            model=_get_model("designer"),
        ),
        "jira": AgentDefinition(
            description=(
                "Jira integration agent for bidirectional issue sync. "
                "Handles inbound Jira webhooks, maps Jira issues to Agent-Engineers "
                "format, and posts completion updates (PR links, test summaries) "
                "back to Jira. Enables enterprise Jira customers to use "
                "Agent-Engineers without migrating to Linear."
            ),
            prompt=_prompt("linear", "linear_agent_prompt"),  # Reuse linear prompt as base
            tools=_get_jira_agent_tools(),
            model=_get_model("jira"),
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
OPENROUTER_DEV_AGENT = AGENT_DEFINITIONS["openrouter_dev"]
PRODUCT_MANAGER_AGENT = AGENT_DEFINITIONS["product_manager"]
DESIGNER_AGENT = AGENT_DEFINITIONS["designer"]
JIRA_AGENT = AGENT_DEFINITIONS["jira"]


def create_agent_definitions_with_routing(
    task: dict | None = None,
    pr_metadata: dict | None = None,
    org_id: str | None = None,
) -> dict[str, AgentDefinition]:
    """Create agent definitions with Opus model routing applied where appropriate.

    Uses :func:`agents.model_routing.estimate_complexity` and
    :func:`agents.model_routing.select_model` to determine whether the
    *coding* or *pr_reviewer* agents should be upgraded to Opus based on
    task complexity and PR metadata.

    Also enforces the per-org cost cap; if the cost cap has already been
    reached for the current run, Opus is downgraded to Sonnet.

    Args:
        task: Optional task dictionary passed to ``estimate_complexity()``.
        pr_metadata: Optional PR metadata dict passed to ``select_model()``.
        org_id: Optional organisation identifier for per-org cost cap lookup.

    Returns:
        Agent definitions dict with model tiers adjusted for the given task.
    """
    task = task or {}
    pr_metadata = pr_metadata or {}

    complexity = estimate_complexity(task)
    coding_tier = select_model("coding", complexity, task)
    pr_reviewer_tier = select_model("pr_reviewer", complexity, pr_metadata)

    # Enforce per-org cost cap: if the cap has already been hit, downgrade
    # Opus to Sonnet so we do not exceed the organisation's budget.
    cap_usd = get_cost_cap_for_org(org_id)

    # Build a CostTracker for this org so callers can extend it with real
    # spend data; here we use it to evaluate whether Opus is permissible.
    # A tracker seeded with zero cost is within cap for any positive cap.
    # The cap_hit flag becomes True only when the tracker's total meets or
    # exceeds the org cap (e.g., if a caller has already recorded spend).
    tracker = CostTracker(cap_usd=cap_usd)
    cap_hit = not tracker.is_within_cap

    # Also honour check_cost_cap for the zero-spend starting point; this
    # call is a no-op for fresh runs but surfaces a warning when cap <= 0.
    if cap_usd > 0:
        cap_within = check_cost_cap(tracker.total_cost_usd, cap_usd)
        if not cap_within:
            cap_hit = True

    if cap_hit:
        # Cost cap already exhausted — downgrade Opus to Sonnet to stay
        # within the organisation's budget.
        if coding_tier == ModelTier.OPUS:
            coding_tier = ModelTier.SONNET
        if pr_reviewer_tier == ModelTier.OPUS:
            pr_reviewer_tier = ModelTier.SONNET

    defs = create_agent_definitions()

    if coding_tier in (ModelTier.OPUS, ModelTier.SONNET):
        coding_model: ModelOption = coding_tier.value  # type: ignore[assignment]
        if coding_model in _VALID_MODELS:
            defs["coding"] = AgentDefinition(
                description=defs["coding"].description,
                prompt=defs["coding"].prompt,
                tools=defs["coding"].tools,
                model=coding_model,
            )

    if pr_reviewer_tier in (ModelTier.OPUS, ModelTier.SONNET):
        pr_model: ModelOption = pr_reviewer_tier.value  # type: ignore[assignment]
        if pr_model in _VALID_MODELS:
            defs["pr_reviewer"] = AgentDefinition(
                description=defs["pr_reviewer"].description,
                prompt=defs["pr_reviewer"].prompt,
                tools=defs["pr_reviewer"].tools,
                model=pr_model,
            )

    return defs


__all__ = [
    "AGENT_DEFINITIONS",
    "AGENT_GIT_IDENTITIES",
    "CODING_AGENT",
    "CODING_FAST_AGENT",
    "CHATGPT_AGENT",
    "DEFAULT_MODELS",
    "DESIGNER_AGENT",
    "GEMINI_AGENT",
    "GITHUB_AGENT",
    "GROQ_AGENT",
    "JIRA_AGENT",
    "KIMI_AGENT",
    "LINEAR_AGENT",
    "ModelOption",
    "OPENROUTER_DEV_AGENT",
    "OPS_AGENT",
    "PR_REVIEWER_AGENT",
    "PR_REVIEWER_FAST_AGENT",
    "PRODUCT_MANAGER_AGENT",
    "SLACK_AGENT",
    "WINDSURF_AGENT",
    # Model routing exports (re-exported for convenience)
    "CostTracker",
    "ModelTier",
    "check_cost_cap",
    "create_agent_definitions",
    "create_agent_definitions_for_pool",
    "create_agent_definitions_with_routing",
    "estimate_complexity",
    "get_cost_cap_for_org",
    "get_orchestrator_model",
    "select_model",
]
