# CLAUDE.md

This file provides context for AI assistants working on this codebase.

## Project Overview

This is a **multi-agent autonomous software engineering harness** built on the Claude Agent SDK (`claude-agent-sdk`). It uses an orchestrator pattern to delegate work to specialized sub-agents (Linear, Coding, GitHub, Slack) that independently manage projects, write code, coordinate version control, and communicate progress.

**Language:** Python 3 (async)
**Framework:** Claude Agent SDK + Arcade MCP Gateway
**License:** MIT

## Repository Structure

```
├── agent.py                    # Core agent session loop logic
├── client.py                   # Claude SDK client configuration
├── security.py                 # Bash command security hooks (allowlist-based)
├── progress.py                 # Progress tracking via .linear_project.json
├── prompts.py                  # Prompt template loading utilities
├── agents/
│   ├── __init__.py             # Exports agent definitions and orchestrator
│   ├── definitions.py          # 13 agent definitions with per-agent model config
│   └── orchestrator.py         # Orchestrator session runner
├── bridges/                    # External AI provider bridges
│   ├── openai_bridge.py        # ChatGPT integration (Codex OAuth + Session Token)
│   ├── gemini_bridge.py        # Gemini integration (CLI OAuth + API key + Vertex AI)
│   ├── groq_bridge.py          # Groq integration (LPU inference)
│   ├── kimi_bridge.py          # KIMI/Moonshot integration (OpenAI-compatible)
│   ├── windsurf_bridge.py      # Windsurf integration (CLI/Docker)
│   └── *_INTEGRATION.md        # Per-provider setup docs
├── daemon/                     # Scalable ticket processing daemon
│   ├── control_plane.py        # HTTP control plane (port 9100)
│   ├── worker_pool.py          # Typed worker pool manager
│   ├── ticket_router.py        # Complexity-based ticket routing
│   └── worktree.py             # Git worktree isolation
├── scripts/
│   ├── autonomous_agent_demo.py # Main entry point / CLI
│   ├── daemon.py               # Simple ticket polling daemon
│   ├── daemon_v2.py            # Scalable daemon with worker pools
│   ├── arcade_config.py        # Arcade MCP gateway config and tool definitions
│   ├── authorize_arcade.py     # OAuth authorization flow for Arcade services
│   ├── chatgpt_cli.py          # Standalone ChatGPT CLI
│   ├── gemini_cli.py           # Standalone Gemini CLI
│   ├── groq_cli.py             # Standalone Groq CLI
│   ├── kimi_cli.py             # Standalone KIMI CLI
│   ├── windsurf_cli.py         # Standalone Windsurf CLI
│   ├── test_security.py        # Security hook test suite
│   └── ...                     # Other utilities
├── prompts/
│   ├── orchestrator_prompt.md  # Orchestrator system prompt
│   ├── *_agent_prompt.md       # Per-agent system prompts (13 total)
│   ├── initializer_task.md     # First-run initialization task template
│   └── continuation_task.md    # Continuation session task template
├── specs/                      # Application specifications
│   ├── app_spec.txt            # Default application specification
│   └── *.txt                   # Additional spec templates
├── pyproject.toml              # Ruff linter/formatter config
├── requirements.txt            # Pinned Python dependencies
├── .env.example                # Environment variable template
└── .gitignore                  # Git ignore rules
```

## Architecture

The system uses an **orchestrator pattern** with 13 specialized agents:

```
ORCHESTRATOR (haiku by default)
├── Workflow Agents
│   ├── LINEAR (haiku)          — Issue/project management in Linear
│   ├── CODING (sonnet)         — Code implementation + Playwright browser testing
│   ├── CODING_FAST (haiku)     — Simple changes (copy, CSS, config, tests)
│   ├── GITHUB (haiku)          — Git operations, branches, PRs
│   ├── PR_REVIEWER (sonnet)    — Automated code review and merge
│   ├── PR_REVIEWER_FAST (haiku) — Quick PR review for low-risk changes
│   ├── OPS (haiku)             — Batch operations (Linear + Slack + GitHub)
│   └── SLACK (haiku)           — Progress notifications
└── AI Provider Agents
    ├── CHATGPT (haiku)         — OpenAI GPT-4o, o1, o3-mini via bridge
    ├── GEMINI (haiku)          — Google Gemini 2.5 Flash/Pro via bridge
    ├── GROQ (haiku)            — Llama, Mixtral via Groq LPU bridge
    ├── KIMI (haiku)            — Moonshot AI ultra-long context via bridge
    └── WINDSURF (haiku)        — Codeium IDE headless/Docker via bridge
```

Key architectural decisions:
- **Each session creates a fresh SDK client** to prevent context window exhaustion in long-running loops
- **Agents don't share memory** — the orchestrator explicitly passes context between them
- **State is persisted via `.linear_project.json`** in the project directory
- **Session types:** "initializer" (first run, creates Linear issues) vs "continuation" (subsequent work)
- **Completion signal:** orchestrator outputs `PROJECT_COMPLETE:` when all features are done

## Running the Project

### Prerequisites
- Python 3.10+
- `uv` (recommended) or `pip` for package management
- Claude CLI authentication (`claude login`)
- Arcade API key and gateway (see `.env.example`)
- Node.js/npm (for Playwright MCP and generated projects)

### Quick Start

```bash
# Install dependencies
uv pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your ARCADE_API_KEY and ARCADE_GATEWAY_SLUG

# Authorize Arcade OAuth (one-time)
uv run python scripts/authorize_arcade.py

# Run the autonomous agent
uv run python scripts/autonomous_agent_demo.py --project-dir my-app

# With options
uv run python scripts/autonomous_agent_demo.py --project-dir my-app --model opus --max-iterations 5
```

### Running Tests

```bash
uv run python scripts/test_security.py
```

Tests are in `scripts/test_security.py` and cover:
- Command extraction logic (`extract_commands`)
- chmod validation (only `+x` variants allowed)
- init.sh validation (only `./init.sh` allowed)
- Dangerous command blocking (system directories, disallowed commands)
- Safe command allowlisting

There is no test framework — tests use a custom `test_hook()` harness that runs assertions and prints PASS/FAIL.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ARCADE_API_KEY` | Yes | Arcade API key (starts with `arc_`) |
| `ARCADE_GATEWAY_SLUG` | Yes | Custom MCP gateway slug |
| `ARCADE_USER_ID` | No | Email for Arcade tracking (default: `agent@local`) |
| `GENERATIONS_BASE_PATH` | No | Where to create projects (default: `./generations`) |
| `GITHUB_REPO` | No | `owner/repo` for GitHub integration |
| `SLACK_CHANNEL` | No | Slack channel for notifications |
| `ORCHESTRATOR_MODEL` | No | haiku/sonnet/opus (default: haiku) |
| `LINEAR_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |
| `CODING_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |
| `GITHUB_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |
| `SLACK_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |
| `PR_REVIEWER_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |
| `OPS_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |
| `CHATGPT_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |
| `GEMINI_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |
| `GROQ_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |
| `KIMI_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |
| `WINDSURF_AGENT_MODEL` | No | haiku/sonnet/opus/inherit |

## Security Model

The system uses defense-in-depth with three layers:

1. **Sandbox** — OS-level bash isolation via `bwrap`/container (configured in `.claude_settings.json`)
2. **Permissions** — File operations restricted to the project directory only
3. **Security hooks** — Pre-execution bash command validation via allowlist in `security.py`

### Bash Command Allowlist

Only commands in `ALLOWED_COMMANDS` (in `security.py:29-73`) are permitted. Key restrictions:
- **`pkill`** — Only dev processes: `node`, `npm`, `npx`, `vite`, `next`
- **`chmod`** — Only `+x` mode (making files executable)
- **`rm`** — Blocks system directories (`/`, `/etc`, `/usr`, `/home`, etc.)
- **`init.sh`** — Only `./init.sh` execution allowed
- Commands not in the allowlist are blocked entirely (fail-safe)

## Code Conventions

- **Type hints throughout** — all functions use Python type annotations including `NamedTuple`, `TypedDict`, `Literal`, `TypeGuard`
- **Async/await** — core agent logic is fully async using `asyncio`
- **Docstrings** — all public functions have docstrings with Args/Returns/Raises sections
- **Constants** — module-level typed constants with `Final` where appropriate
- **Error handling** — specific exception types caught with actionable error messages
- **Ruff** — linter and formatter configured via `pyproject.toml` (line-length=100, target py311)
- **No CI/CD** — no `.github/workflows` directory

## Key Patterns

### Session Loop (agent.py)
```python
# Each iteration creates a fresh client to avoid context exhaustion
while True:
    client = create_client(project_dir, model)
    async with client:
        result = await run_agent_session(client, prompt, project_dir)
    # Handle result.status: "continue" | "error" | "complete"
```

### Agent Definitions (agents/definitions.py)
Agent models are configurable via `{AGENT_NAME}_AGENT_MODEL` env vars. Definitions are created at import time. Each agent gets a subset of tools matching its domain.

### MCP Integration (client.py, arcade_config.py)
Two MCP servers are configured:
- **Playwright** (`@playwright/mcp@latest`) — browser automation for UI testing
- **Arcade** (HTTP gateway) — unified auth for Linear (39 tools), GitHub (46 tools), Slack (8 tools)

### Bridge Modules (bridges/)
External AI providers are integrated via bridge modules in `bridges/`. Each bridge wraps a provider's API (using their SDK or OpenAI-compatible endpoints) and is invoked by the corresponding agent via Bash. CLIs are in `scripts/*_cli.py`.

### Generated Project Structure
Each run creates an isolated project in `generations/<project-name>/` with:
- Its own `.git` repository
- `.linear_project.json` state marker
- `.claude_settings.json` security settings
- `app_spec.txt` application specification
- `init.sh` dev server startup script

## Common Tasks for Contributors

### Adding a new allowed bash command
Add to `ALLOWED_COMMANDS` in `security.py`. If the command needs extra validation, add it to `COMMANDS_NEEDING_EXTRA_VALIDATION` and implement a `validate_<cmd>_command()` function following the existing pattern. Add test cases to `scripts/test_security.py`.

### Adding a new specialized agent
1. Create a prompt file in `prompts/<name>_agent_prompt.md`
2. Add an `AgentDefinition` in `agents/definitions.py`
3. Define the tool subset for the agent in `scripts/arcade_config.py` (if using Arcade tools)
4. Add a `{NAME}_AGENT_MODEL` env var in the `_get_model()` function

### Modifying the app specification
Edit `specs/app_spec.txt` or create a new spec in `specs/`. The default spec is copied into the project directory on first run.
