<div align="center">

# 🤖 Agent Engineers

### _Autonomous Multi-Model AI Engineering Teams_

**Deploy a team of specialized AI agents that plan, code, review, and ship software — across Claude, Gemini, and beyond.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Claude Agent SDK](https://img.shields.io/badge/Claude_Agent_SDK-0.1.25-D4A574?style=for-the-badge&logo=anthropic&logoColor=white)](https://github.com/anthropics/claude-code/tree/main/agent-sdk-python)
[![Arcade MCP](https://img.shields.io/badge/Arcade_MCP-Gateway-7C3AED?style=for-the-badge)](https://arcade.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-22C55E?style=for-the-badge)](LICENSE)

<br/>

<img src="https://img.shields.io/badge/Claude-Orchestrator-D4A574?style=flat-square" alt="Claude" />
<img src="https://img.shields.io/badge/Gemini-Research-4285F4?style=flat-square" alt="Gemini" />
<img src="https://img.shields.io/badge/Jira-Tracking-0052CC?style=flat-square" alt="Jira" />
<img src="https://img.shields.io/badge/GitHub-Version_Control-181717?style=flat-square" alt="GitHub" />
<img src="https://img.shields.io/badge/Slack-Notifications-4A154B?style=flat-square" alt="Slack" />
<img src="https://img.shields.io/badge/Playwright-Browser_Testing-2EAD33?style=flat-square" alt="Playwright" />

---

*Hand off a feature request. Get back a PR with tests, screenshots, and a Slack notification.*

</div>

<br/>

## 🧬 What Is This?

Agent Engineers is a **multi-agent harness** built on the [Claude Agent SDK](https://github.com/anthropics/claude-code/tree/main/agent-sdk-python) that orchestrates a team of specialized AI agents to autonomously build software — end to end.

It doesn't just write code. It **manages a project board**, **creates feature branches**, **writes tests**, **takes browser screenshots for verification**, **opens PRs**, **runs code reviews**, and **posts progress updates to Slack** — all without human intervention.

The multi-model architecture means the right AI handles the right job: Claude Sonnet writes code, Claude Haiku manages lightweight coordination, and Google Gemini handles research with Google Search grounding — no single model bottleneck.

<br/>

## ⚡ The Agent Team

```
                          ┌─────────────────────┐
                          │    ORCHESTRATOR      │
                          │    Claude Haiku      │
                          │  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄  │
                          │  Plans · Delegates   │
                          │  Passes Context      │
                          └──────────┬──────────┘
                                     │
            ┌────────────┬───────────┼───────────┬────────────┐
            │            │           │           │            │
    ┌───────▼──────┐ ┌───▼────┐ ┌───▼────┐ ┌───▼─────┐ ┌───▼──────┐
    │   TRACKER    │ │ CODER  │ │ GITHUB │ │  SLACK  │ │ GEMINI   │
    │  Jira/Linear │ │ Sonnet │ │ Haiku  │ │  Haiku  │ │  Haiku   │
    │    Haiku     │ │        │ │        │ │         │ │    ↓     │
    ├──────────────┤ ├────────┤ ├────────┤ ├─────────┤ │ gemini   │
    │ Create issues│ │ Write  │ │ Branch │ │ Notify  │ │  -cli    │
    │ Track status │ │ Test   │ │ Commit │ │ on start│ │    ↓     │
    │ Transition   │ │ Verify │ │ PR     │ │ on done │ │ Google   │
    │ Comment      │ │ Screen │ │ Push   │ │ on block│ │ Gemini   │
    └──────────────┘ └────────┘ └────────┘ └─────────┘ │ 2.5 Pro  │
                                                        └──────────┘
                          ┌─────────────────────┐
                          │   PR REVIEWER        │
                          │   Claude Sonnet      │
                          │  ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄  │
                          │  Review · Approve    │
                          │  Request Changes     │
                          │  Auto-Merge          │
                          └─────────────────────┘
```

| Agent | Model | Role |
|:------|:------|:-----|
| **Orchestrator** | Claude Haiku | Coordinates all agents, passes context between them, enforces quality gates |
| **Tracker** (Jira) | Claude Haiku | Creates/updates Jira issues, manages sprint status, session handoff via META issue |
| **Tracker** (Linear) | Claude Haiku | Alternative tracker — same capabilities for Linear workspaces |
| **Coder** | Claude Sonnet | Implements features, writes tests, browser-tests with Playwright, provides screenshot evidence |
| **GitHub** | Claude Haiku | Creates branches, commits code, pushes to remote, opens pull requests |
| **PR Reviewer** | Claude Sonnet | Reviews PRs for quality, approves or requests changes, auto-merges approved PRs |
| **Slack** | Claude Haiku | Sends real-time notifications — task started, PR ready, completed, blocked |
| **Gemini** | Claude Haiku → gemini-cli | Research with Google Search grounding, long-context analysis, second opinions. Uses OAuth — no API key, no per-token billing |

<br/>

## 🔄 How It Works

Every feature follows a rigorous lifecycle — automatically:

```
 ┌──────────────────────────────────────────────────────────────────────┐
 │                                                                      │
 │   📋 Jira: Create issue         🔔 Slack: "Starting KAN-42..."      │
 │          │                              │                            │
 │          ▼                              ▼                            │
 │   🔍 Verification Gate ◄── FAIL ── Fix regressions first            │
 │          │                                                           │
 │        PASS                                                          │
 │          │                                                           │
 │          ▼                                                           │
 │   💻 Code: Implement + Test + Screenshot                             │
 │          │                                                           │
 │          ▼                                                           │
 │   🌿 GitHub: Branch → Commit → Push → PR                            │
 │          │                                                           │
 │          ▼                                                           │
 │   🔔 Slack: "PR ready for review..."                                │
 │          │                                                           │
 │          ▼                                                           │
 │   👀 PR Review ──── CHANGES REQUESTED ──► Back to Todo + Slack      │
 │          │                                                           │
 │       APPROVED                                                       │
 │          │                                                           │
 │          ▼                                                           │
 │   ✅ Merge → Jira: Done → Slack: "Completed!"                       │
 │                                                                      │
 └──────────────────────────────────────────────────────────────────────┘
```

**Quality gates enforced automatically:**
- 🚫 No new work until verification tests pass on existing features
- 📸 No issue marked "Done" without screenshot evidence
- 🧪 Every feature requires test coverage — no exceptions
- 🔁 Rejected PRs cycle back with reviewer feedback attached

<br/>

## 🔀 Multi-Model Strategy

Agent Engineers isn't locked to one AI provider. The orchestrator dispatches to the best model for each job:

| Task | Model | Why |
|:-----|:------|:----|
| Coordination & lightweight ops | **Claude Haiku** | Fast, cheap, great at following structured workflows |
| Code implementation & review | **Claude Sonnet** | Strong reasoning, excellent code quality |
| Research & web grounding | **Google Gemini 2.5 Pro** | Native Google Search integration, massive context window |
| Complex orchestration (optional) | **Claude Opus** | Deepest reasoning for complex multi-step planning |

Gemini integration uses Google's official `gemini-cli` with **OAuth authentication** — if you have a Google AI Pro/Ultra subscription, you get higher rate limits and Gemini 2.5 Pro access with zero API costs.

<br/>

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+** and **Node.js 18+**
- **Claude Code CLI**: `npm install -g @anthropic-ai/claude-code`
- **Arcade API Key**: [Get one here](https://api.arcade.dev/dashboard/api-keys)

> ⚠️ Linux/macOS only — Claude Agent SDK subagents don't work on Windows. Use WSL.

### Setup

```bash
# Clone the repo
git clone https://github.com/kennylhilljr/Agent-Engineers.git
cd Agent-Engineers

# Create virtual environment
python3 -m venv venv && source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Arcade API key and gateway slug

# Authorize Arcade tools (one-time OAuth flow)
python authorize_arcade.py

# (Optional) Set up Gemini CLI for research agent
chmod +x setup_gemini.sh && ./setup_gemini.sh
```

### Run

```bash
# Start an autonomous engineering session
uv run python autonomous_agent_demo.py --project-dir my-app

# Use Sonnet for orchestration (more capable, higher cost)
uv run python autonomous_agent_demo.py --project-dir my-app --model sonnet

# Limit iterations for testing
uv run python autonomous_agent_demo.py --project-dir my-app --max-iterations 3
```

<br/>

## ⚙️ Configuration

### Environment Variables

#### Core (Required)

| Variable | Description |
|:---------|:------------|
| `ARCADE_API_KEY` | Arcade API key ([get one](https://api.arcade.dev/dashboard/api-keys)) |
| `ARCADE_GATEWAY_SLUG` | Your Arcade MCP gateway slug |
| `ARCADE_USER_ID` | Your email for user tracking |

#### Integrations (Optional)

| Variable | Description |
|:---------|:------------|
| `GITHUB_REPO` | GitHub repo in `owner/repo` format for auto-push |
| `SLACK_CHANNEL` | Slack channel name (without `#`) for notifications |
| `JIRA_SERVER` | Jira server URL (enables Jira tracker instead of Linear) |
| `GEMINI_AUTH_TYPE` | `oauth` (default) or `api-key` |
| `GEMINI_MODEL` | `gemini-2.5-flash` (default), `gemini-2.5-pro`, `gemini-2.0-flash` |
| `GEMINI_ENABLED` | `true` (default) or `false` |

#### Model Selection (Optional)

| Variable | Default | Options |
|:---------|:--------|:--------|
| `ORCHESTRATOR_MODEL` | `haiku` | `haiku`, `sonnet`, `opus` |
| `LINEAR_AGENT_MODEL` | `haiku` | `haiku`, `sonnet`, `opus`, `inherit` |
| `JIRA_AGENT_MODEL` | `haiku` | `haiku`, `sonnet`, `opus`, `inherit` |
| `CODING_AGENT_MODEL` | `sonnet` | `haiku`, `sonnet`, `opus`, `inherit` |
| `GITHUB_AGENT_MODEL` | `haiku` | `haiku`, `sonnet`, `opus`, `inherit` |
| `SLACK_AGENT_MODEL` | `haiku` | `haiku`, `sonnet`, `opus`, `inherit` |
| `PR_REVIEWER_AGENT_MODEL` | `sonnet` | `haiku`, `sonnet`, `opus`, `inherit` |
| `GEMINI_AGENT_MODEL` | `haiku` | `haiku`, `sonnet`, `opus`, `inherit` |

#### Output Configuration

| Variable | Description | Default |
|:---------|:------------|:--------|
| `GENERATIONS_BASE_PATH` | Base directory for generated projects | `./generations` |

<br/>

## 📁 Project Structure

```
Agent-Engineers/
├── autonomous_agent_demo.py    # Main entry point
├── agent.py                    # Agent session logic
├── client.py                   # Claude SDK + MCP client configuration
├── security.py                 # Bash command allowlist & validation
├── progress.py                 # Progress tracking utilities
├── prompts.py                  # Prompt loading utilities
├── arcade_config.py            # Arcade MCP gateway configuration
├── authorize_arcade.py         # Arcade authorization flow
├── gemini_bridge.py            # Gemini CLI Python wrapper
├── gemini_config.py            # Gemini configuration & tools
├── setup_gemini.sh             # Gemini CLI first-run setup
├── agents/
│   ├── definitions.py          # All agent definitions & model config
│   └── orchestrator.py         # Orchestrator session runner
├── prompts/
│   ├── app_spec.txt            # Application specification
│   ├── orchestrator_prompt.md  # Orchestrator system prompt
│   ├── initializer_task.md     # First-run task message
│   ├── continuation_task.md    # Continuation session message
│   ├── linear_agent_prompt.md  # Linear sub-agent prompt
│   ├── jira_agent_prompt.md    # Jira sub-agent prompt
│   ├── coding_agent_prompt.md  # Coding sub-agent prompt
│   ├── github_agent_prompt.md  # GitHub sub-agent prompt
│   ├── slack_agent_prompt.md   # Slack sub-agent prompt
│   ├── pr_reviewer_agent_prompt.md  # PR reviewer prompt
│   └── gemini_agent_prompt.md  # Gemini sub-agent prompt
├── scripts/
│   └── gemini                  # Gemini CLI wrapper script
└── requirements.txt            # Python dependencies
```

<br/>

## 🛡️ Security Model

Defense-in-depth — multiple layers protect against unintended operations:

| Layer | What It Does |
|:------|:-------------|
| **OS Sandbox** | Bash commands run in an isolated bwrap/Docker-style sandbox |
| **Filesystem Restrictions** | File operations restricted to the project directory only |
| **Bash Allowlist** | Only explicitly permitted commands can execute (see `security.py`) |
| **Command Validation** | Sensitive commands (`rm`, `pkill`, `chmod`) get extra validation |
| **MCP Permissions** | Tools explicitly allowlisted in security settings |

<br/>

## 🔌 MCP Servers

| Server | Transport | Purpose |
|:-------|:----------|:--------|
| **Arcade Gateway** | HTTP | Unified OAuth access to Linear, Jira, GitHub, Slack (93+ tools) |
| **Playwright** | stdio | Browser automation for UI testing & screenshot evidence |
| **gemini-cli** | subprocess | Google Gemini models for research & web search grounding |

<br/>

## 📖 Customization

**Change what gets built:** Edit `prompts/app_spec.txt` with your application specification.

**Adjust issue count:** Edit `prompts/initializer_task.md` to control how many issues are created during initialization.

**Add allowed commands:** Edit `security.py` to add commands to `ALLOWED_COMMANDS`.

**Switch trackers:** Set `JIRA_SERVER` in `.env` for Jira, or leave it unset for Linear. The orchestrator auto-detects based on `.jira_project.json` or `.linear_project.json`.

<br/>

## 🐛 Troubleshooting

| Error | Fix |
|:------|:----|
| `ARCADE_API_KEY not set` | Get your key from [Arcade Dashboard](https://api.arcade.dev/dashboard/api-keys) |
| `ARCADE_GATEWAY_SLUG not set` | Create a gateway at [Arcade MCP Gateways](https://api.arcade.dev/dashboard/mcp-gateways) |
| `Authorization required` | Run `python authorize_arcade.py` |
| `Command blocked by security hook` | Add command to `ALLOWED_COMMANDS` in `security.py` |
| `MCP server connection failed` | Verify Arcade API key and gateway configuration |
| `GitHub agent requires GITHUB_REPO` | Set `GITHUB_REPO=owner/repo` in `.env` |
| `Slack channel not found` | Create the channel manually first — agents can't create channels |
| `gemini-cli not found` | Run `./setup_gemini.sh` or `npm install -g @google/gemini-cli` |

<br/>

## 📊 Monitoring Progress

| Where | What You See |
|:------|:-------------|
| **Jira/Linear** | Real-time issue transitions, implementation comments, session summaries on META issue |
| **GitHub** | Feature branches, commits, pull requests with linked issues |
| **Slack** | Live notifications for every task lifecycle event (start → PR → review → done) |
| **Terminal** | Agent coordination logs, tool calls, iteration progress |

<br/>

---

**Built with the [Claude Agent SDK](https://github.com/anthropics/claude-code/tree/main/agent-sdk-python) · Powered by [Arcade MCP](https://arcade.dev)**

*From feature request to merged PR — autonomously.*
