# Agent Creation Rules and Workflow

**Issue:** AI-271
**Last updated:** 2026-02-19
**Author:** PM Agent (claude-sonnet-4-5)

---

## Overview

Every time a new agent is added to the system, a specific set of files and registrations must be updated. Skipping any step will result in a broken agent that is invisible to the orchestrator, has no git identity, gets the wrong model, or does not appear in the dashboard.

This document is the single source of truth for creating a new agent.

---

## Checklist: New Agent Creation

Use this checklist in order. All items are mandatory unless marked optional.

### 1. Create the prompt file

**File:** `prompts/<agent_name>_agent_prompt.md`

Every agent must have a dedicated prompt file. Follow this template:

```markdown
## YOUR ROLE - <AGENT NAME IN CAPS>

One-sentence description of this agent's responsibility.

### Available Tools

List the tool groups this agent has access to.

### CRITICAL: Screenshot Evidence Required

**Every task MUST include screenshot evidence.**

### Workflow

Step-by-step instructions for the agent to follow.

### Git Identity (MANDATORY)

This section is auto-appended by `_build_git_identity_prompt()`. Do NOT add it manually.
```

Existing examples to reference:
- `prompts/coding_agent_prompt.md` — code-writing agent pattern
- `prompts/ops_agent_prompt.md` — multi-tool lightweight ops pattern
- `prompts/jira_agent_prompt.md` — third-party integration pattern
- `prompts/security_reviewer_agent_prompt.md` — specialized review pattern

---

### 2. Register the agent in `agents/definitions.py`

This file is the authoritative registry. Three sections must be updated:

#### 2a. Add a default model to `DEFAULT_MODELS`

```python
DEFAULT_MODELS: Final[dict[str, ModelOption]] = {
    # ... existing entries ...
    "<agent_name>": "haiku",  # or "sonnet" / "opus"
}
```

**Model selection guidance:**
- `haiku` — Lightweight integrations: issue tracking, notifications, simple file ops
- `sonnet` — Complex reasoning, code review, PM tasks, security analysis
- `opus` — Reserved for the highest-complexity tickets (auto-routed by daemon)

#### 2b. Add a Git identity to `AGENT_GIT_IDENTITIES`

```python
AGENT_GIT_IDENTITIES: Final[dict[str, GitIdentity]] = {
    # ... existing entries ...
    "<agent_name>": GitIdentity("<Human Name> Agent", "<agent-name>-agent@claude-agents.dev"),
}
```

The email must follow the pattern `<agent-name>-agent@claude-agents.dev`. This identity is embedded in every git commit made by the agent. Commits without the correct `--author` flag are blocked by the security system.

#### 2c. Add the agent to `create_agent_definitions()`

```python
def create_agent_definitions() -> dict[str, AgentDefinition]:
    def _prompt(name: str, prompt_file: str) -> str:
        return _load_prompt(prompt_file) + _build_git_identity_prompt(name)

    return {
        # ... existing entries ...
        "<agent_name>": AgentDefinition(
            description=(
                "One sentence describing what this agent does and when to use it."
            ),
            prompt=_prompt("<agent_name>", "<agent_name>_agent_prompt"),
            tools=_get_<agent_name>_tools(),   # or inline if simple
            model=_get_model("<agent_name>"),
        ),
    }
```

**Important:** The `description` is what the orchestrator reads to decide whether to delegate to this agent. Write it from the orchestrator's perspective: "Use this agent when..."

#### 2d. Add a convenience constant (optional but recommended)

```python
<AGENT_NAME>_AGENT = AGENT_DEFINITIONS["<agent_name>"]
```

---

### 3. Define the tool getter function in `agents/definitions.py`

Create a private `_get_<agent_name>_tools()` function that returns the correct tool list:

```python
def _get_<agent_name>_tools() -> list[str]:
    """Tools for <agent name> — describe what tools and why."""
    return <tool_group_function>() + FILE_TOOLS + ["Bash"]
```

**Available tool groups (from `arcade_config.py`):**

| Function | Tools included | Use case |
|---|---|---|
| `get_linear_tools()` | Linear MCP | Issue management |
| `get_github_tools()` | GitHub MCP | Git, PRs, code review |
| `get_slack_tools()` | Slack MCP | Notifications, messaging |
| `get_coding_tools()` | All coding tools + Playwright | Full-stack dev |
| `get_qa_tools()` | Coding tools + test runners | Test writing |
| `get_jira_tools()` | Jira MCP (optional import) | Jira integration |
| `FILE_TOOLS` | Read, Write, Edit, Glob | File operations |

For third-party integrations (like Jira), wrap the import in try/except to avoid import errors when the MCP is not configured:

```python
def _get_<agent_name>_tools() -> list[str]:
    try:
        from arcade_config import get_<service>_tools
        return get_<service>_tools() + FILE_TOOLS + ["Bash"]
    except (ImportError, AttributeError):
        return FILE_TOOLS + ["Bash"]
```

---

### 4. Register the agent in the dashboard metrics system

**File:** `dashboard/rest_api_server.py` — The REST API auto-discovers agents from `create_agent_definitions()`, so no changes are needed here for basic agent status display.

**File:** `dashboard/metrics.py` — If the agent has unique metric types (e.g., `reviews_completed`, `messages_sent`), verify that the `AgentMetrics` dataclass already covers the metric. If a new metric field is needed, add it to `AgentMetrics` and update the JSON serializer.

---

### 5. Register the agent in the worker pool (if daemon-managed)

**File:** `daemon/worker_pool.py` — Only needed if the new agent runs as an autonomous daemon worker (not orchestrator-delegated).

Update `POOL_TYPE_TO_AGENT_NAME` or add a new `PoolType` enum value if a new pool category is needed. For most new integrations this is NOT required — the daemon's coding pool handles delegation to the orchestrator, which then delegates to sub-agents.

---

### 6. Add the agent to the orchestrator routing rules (if needed)

**File:** `daemon/ticket_router.py` — Only update if the agent is a new top-level pool type (rare).

**File:** `agents/orchestrator.py` — The orchestrator automatically discovers all agents from `create_agent_definitions()`. No changes needed unless adding a custom routing heuristic.

---

### 7. Write tests

**Location:** `tests/` (Python) or `dashboard/__tests__/` (JS/Jest)

Every new agent must have:

1. A test that verifies the agent appears in `create_agent_definitions()` return value
2. A test that verifies the prompt file loads without error
3. A test that verifies the git identity is registered in `AGENT_GIT_IDENTITIES`
4. A test that verifies the default model is in `DEFAULT_MODELS`

Minimum test example:

```python
# tests/test_<agent_name>_agent.py
from agents.definitions import create_agent_definitions, AGENT_GIT_IDENTITIES, DEFAULT_MODELS

def test_<agent_name>_agent_registered():
    defs = create_agent_definitions()
    assert "<agent_name>" in defs
    agent = defs["<agent_name>"]
    assert agent.description
    assert agent.prompt
    assert len(agent.tools) > 0

def test_<agent_name>_git_identity():
    assert "<agent_name>" in AGENT_GIT_IDENTITIES
    identity = AGENT_GIT_IDENTITIES["<agent_name>"]
    assert identity.email.endswith("@claude-agents.dev")

def test_<agent_name>_default_model():
    assert "<agent_name>" in DEFAULT_MODELS
    assert DEFAULT_MODELS["<agent_name>"] in ("haiku", "sonnet", "opus", "inherit")
```

---

### 8. Update `.linear_project.json` (if a new session completes the agent)

After all PRs are merged and tests pass, update `total_issues` and `notes` fields:

```json
{
  "total_issues": <N+1>,
  "notes": "Added <agent_name> agent (AI-XXX)."
}
```

---

## Summary Table: Files to Update

| File | Required? | What to add |
|---|---|---|
| `prompts/<agent_name>_agent_prompt.md` | Yes | New prompt file |
| `agents/definitions.py` — `DEFAULT_MODELS` | Yes | `"<agent_name>": "haiku"` |
| `agents/definitions.py` — `AGENT_GIT_IDENTITIES` | Yes | `GitIdentity(...)` |
| `agents/definitions.py` — `create_agent_definitions()` | Yes | `AgentDefinition(...)` |
| `agents/definitions.py` — `_get_<name>_tools()` | Yes | Tool getter function |
| `agents/definitions.py` — convenience constant | Optional | `<NAME>_AGENT = ...` |
| `dashboard/metrics.py` — `AgentMetrics` | Only if new metric | New dataclass field |
| `daemon/worker_pool.py` — pool registration | Only if daemon-managed | `PoolType` or mapping |
| `daemon/ticket_router.py` — routing rules | Only if new pool | Routing rule |
| `tests/test_<agent_name>_agent.py` | Yes | 4 minimum test cases |
| `.linear_project.json` | Yes (post-merge) | Updated `total_issues`, `notes` |

---

## Environment Variable Convention

Each agent's model can be overridden at runtime without code changes:

```bash
export <AGENT_NAME_UPPER>_AGENT_MODEL=sonnet  # Override to sonnet
export <AGENT_NAME_UPPER>_AGENT_MODEL=opus    # Override to opus
```

Example: `CODING_AGENT_MODEL=opus` overrides the `coding` agent to use Opus.

This is handled automatically by `_get_model(agent_name)` in `agents/definitions.py`.

---

## Common Mistakes

1. **Forgetting `AGENT_GIT_IDENTITIES`** — The agent will make commits without a proper `--author` flag, and they will be blocked by the security system.

2. **Using a hardcoded model string** instead of `_get_model("<agent_name>")` — This bypasses environment variable overrides.

3. **Not adding a prompt file** — `_load_prompt()` will throw a `FileNotFoundError` at startup.

4. **Writing the description from the wrong perspective** — The `description` in `AgentDefinition` is read by the orchestrator. Write it as: "Use this agent when [situation]."

5. **Not adding tests** — PRs without tests will be rejected by the PR reviewer agent.

6. **Not wrapping optional MCP imports in try/except** — If the MCP gateway credential for an integration is not configured, the import will fail and all agents will fail to load.

---

## Reference: Existing Agent Patterns

### Lightweight integration agent (haiku, MCP tools)
See: `jira`, `gitlab`, `knowledge_base`, `slack`, `linear`

### Code-writing agent (sonnet, coding tools)
See: `coding`, `coding_fast`, `qa`

### Review agent (sonnet/haiku, GitHub tools)
See: `pr_reviewer`, `pr_reviewer_fast`, `security_reviewer`

### Bridge agent (haiku, file + bash tools)
See: `chatgpt`, `gemini`, `groq`, `kimi`, `windsurf`, `openrouter_dev`

### Composite operations agent (haiku, multi-MCP)
See: `ops`, `product_manager`
