# Agent Dashboard — Requirements Document

## Document Purpose

This document specifies the requirements for the Agent Status Dashboard web application. It extends the existing `specs/agent_status_dashboard.md` feature spec with interactive capabilities: an AI Chat interface with multi-provider support, real-time agent visibility, agent pause/resume controls, requirement editing, and transparent reasoning/decision/coding display.

All code implementing these requirements must follow the [Andrej Karpathy Skills](https://github.com/forrestchang/andrej-karpathy-skills/tree/main) principles:

1. **Think Before Coding** — State assumptions explicitly. Present options when ambiguity exists. Push back on unnecessary complexity. Stop and ask when unclear.
2. **Simplicity First** — Write the minimum code that solves the stated problem. No speculative features, no "just in case" abstractions.
3. **Surgical Changes** — Touch only what is necessary. Match existing code style. Only remove dead code created by your own changes.
4. **Goal-Driven Execution** — Transform tasks into verifiable goals with concrete success criteria. Each step has a verification check.

---

## 1. System Overview

### 1.1 What This Is

A web-based dashboard that provides:

- **Real-time agent monitoring** — See which agents are active, what requirements they are working on, and their current status
- **AI Chat interface** — A conversational interface where users interact with the multi-agent system, choose AI providers and models, and issue commands
- **Agent control** — Pause agents, edit requirement instructions mid-flight, and resume agents
- **Transparent reasoning** — Live display of agent reasoning, decision-making, and code generation as it happens
- **External service integration** — The chat interface has direct access to Linear, Slack, and GitHub through the existing Arcade MCP gateway

### 1.2 What This Is Not

- Not a replacement for the CLI-based workflow — the CLI remains the primary entry point
- Not a standalone product — it is a view layer on top of the existing orchestrator in `agents/orchestrator.py`
- Not a new agent framework — it reuses all existing agent definitions from `agents/definitions.py`

### 1.3 Relationship to Existing System

```
┌─────────────────────────────────────────────────────────┐
│                  Agent Dashboard (NEW)                   │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  AI Chat UI  │  │ Agent Status │  │  Controls    │  │
│  │  (Provider   │  │ (Real-time   │  │  (Pause/     │  │
│  │   Selector)  │  │  Monitoring) │  │   Resume/    │  │
│  │              │  │              │  │   Edit)      │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                 │                 │           │
│         └────────┬────────┴────────┬────────┘           │
│                  │                 │                     │
│           ┌──────▼───────┐  ┌─────▼──────────┐         │
│           │  WebSocket   │  │  REST API       │         │
│           │  Server      │  │  Server         │         │
│           └──────┬───────┘  └─────┬──────────┘         │
└──────────────────┼────────────────┼─────────────────────┘
                   │                │
┌──────────────────▼────────────────▼─────────────────────┐
│              Existing System (UNCHANGED)                 │
│                                                         │
│  ┌────────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │  Orchestrator  │  │  Agent       │  │  Metrics   │  │
│  │  (orchestrator │  │  Definitions │  │  Collector  │  │
│  │   .py)         │  │  (defini-    │  │  (metrics  │  │
│  │                │  │   tions.py)  │  │   .py)     │  │
│  └────────────────┘  └──────────────┘  └────────────┘  │
│                                                         │
│  ┌────────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │  Session Loop  │  │  Progress    │  │  Security  │  │
│  │  (agent.py)    │  │  (progress   │  │  (security │  │
│  │                │  │   .py)       │  │   .py)     │  │
│  └────────────────┘  └──────────────┘  └────────────┘  │
│                                                         │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Arcade MCP Gateway (Linear, GitHub, Slack)        │ │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Bridge Modules (OpenAI, Gemini, Groq, KIMI,      │ │
│  │  Windsurf)                                         │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## 2. AI Chat Interface

### 2.1 Core Chat Functionality

**REQ-CHAT-001: Conversational Interface**
The dashboard must provide a chat interface where users type natural language messages and receive responses from the AI system. Messages display in a scrollable conversation thread with clear visual distinction between user messages and AI responses.

**REQ-CHAT-002: Message History**
The chat must persist message history for the current session. Messages include:
- User input (text)
- AI response (text, code blocks, structured data)
- System messages (agent status changes, errors, notifications)
- Timestamps for all messages

**REQ-CHAT-003: Code Block Rendering**
AI responses containing code must render with:
- Syntax highlighting appropriate to the language
- Copy-to-clipboard button
- File path annotation when the code references a specific file
- Diff view for code changes (additions in green, deletions in red)

### 2.2 AI Provider Selection

**REQ-PROVIDER-001: Provider Switcher**
The chat interface must include a provider selector that allows the user to switch between available AI providers. Supported providers (from existing bridge modules in `bridges/`):

| Provider | Models Available | Source |
|----------|-----------------|--------|
| Claude (default) | Haiku 4.5, Sonnet 4.5, Opus 4.6 | Direct (Claude Agent SDK) |
| ChatGPT | GPT-4o, o1, o3-mini, o4-mini | `bridges/openai_bridge.py` |
| Gemini | 2.5 Flash, 2.5 Pro, 2.0 Flash | `bridges/gemini_bridge.py` |
| Groq | Llama 3.3 70B, Mixtral 8x7B | `bridges/groq_bridge.py` |
| KIMI | Moonshot (2M context) | `bridges/kimi_bridge.py` |
| Windsurf | Cascade | `bridges/windsurf_bridge.py` |

**REQ-PROVIDER-002: Model Selector**
Within each provider, the user must be able to select a specific model. The selector must:
- Show only models available for the selected provider
- Display the currently active model
- Persist the selection for the duration of the session
- Default to the provider's recommended model

**REQ-PROVIDER-003: Provider Status Indicators**
Each provider in the selector must show its availability status:
- **Available** — API key configured, provider reachable
- **Unconfigured** — API key missing (show setup instructions on hover)
- **Error** — API key present but provider unreachable

**REQ-PROVIDER-004: Hot-Swap Without Context Loss**
Switching providers mid-conversation must:
- Preserve the full conversation history in the UI
- Insert a system message noting the provider change
- Send conversation context to the new provider for continuity
- Not interrupt any running agent operations

### 2.3 External Service Integration (Linear, Slack, GitHub)

**REQ-INTEGRATION-001: Linear Access**
The chat interface must have access to all 39 Linear MCP tools defined in `scripts/arcade_config.py`. Users can:
- Query issue status ("What's the status of AI-42?")
- Create issues ("Create a bug for the login page crash")
- Transition issues ("Move AI-42 to In Progress")
- View project boards and backlogs

**REQ-INTEGRATION-002: Slack Access**
The chat interface must have access to all 8 Slack MCP tools. Users can:
- Send messages to configured channels
- Read recent messages
- React to messages
- Pin important updates

**REQ-INTEGRATION-003: GitHub Access**
The chat interface must have access to all 46 GitHub MCP tools. Users can:
- View PR status and diffs
- Create and merge PRs
- View repository information
- Manage issues and labels

**REQ-INTEGRATION-004: Tool Transparency**
When the AI invokes an external tool (Linear, Slack, GitHub), the chat must:
- Show which tool is being called and with what parameters (collapsible detail)
- Show the tool's response (collapsible detail)
- Indicate success or failure with a visual status icon

---

## 3. Agent Monitoring

### 3.1 Real-Time Agent Status

**REQ-MONITOR-001: Agent Status Panel**
The dashboard must display a panel showing all 13 agents defined in `agents/definitions.py` with their current status:

| Status | Visual | Meaning |
|--------|--------|---------|
| Running | Green pulsing dot | Agent is actively processing a delegation |
| Idle | Gray dot | Agent is available, not currently delegated to |
| Paused | Yellow dot | Agent paused by user (see Section 4) |
| Error | Red dot | Agent's last invocation failed |

**REQ-MONITOR-002: Active Requirement Display**
When an agent is in "Running" status, the panel must show:
- The Linear ticket key and title the agent is working on (e.g., "AI-42: Add user authentication")
- The full requirement description (expandable)
- Time elapsed since the agent started this delegation
- Token count accumulating in real-time
- Estimated cost accumulating in real-time

**REQ-MONITOR-003: Agent Detail View**
Clicking on an agent in the status panel opens a detail view showing:
- The agent's `AgentProfile` data (from `metrics.py` types):
  - Lifetime statistics (invocations, success rate, tokens, cost)
  - Contribution counters (commits, PRs, files, issues, messages, reviews)
  - Gamification data (XP, level, streak, achievements)
  - Strengths and weaknesses (auto-detected)
- Recent event history (last 20 events from `recent_events`)
- The agent's current model assignment (from `DEFAULT_MODELS` in `definitions.py`)

**REQ-MONITOR-004: Orchestrator Flow Visualization**
The dashboard must show the orchestrator's current delegation flow:
```
Orchestrator
  ├─► ops (Starting AI-42) ✓ 3s
  ├─► coding (Implementing AI-42) ● 45s [ACTIVE]
  ├─► github (Commit + PR) ○ [PENDING]
  └─► ops (Mark Done + Notify) ○ [PENDING]
```
This visualizes the pipeline defined in the orchestrator prompt (Section "Session Flow" in `prompts/orchestrator_prompt.md`):
1. ops: Start + notify
2. coding/coding_fast: Implement + test
3. github: Commit + PR
4. ops: Review transition
5. pr_reviewer: Review
6. ops: Done + notify

### 3.2 Metrics Dashboard

**REQ-METRICS-001: Global Metrics Bar**
The top of the dashboard must show global metrics (from `DashboardState` in `metrics.py`):
- Total sessions completed
- Total tokens consumed
- Total estimated cost (USD)
- Total uptime/duration
- Current session number

**REQ-METRICS-002: Agent Leaderboard**
Display agents ranked by XP (from `AgentProfile.xp`), showing:
- Rank
- Agent name
- Level and XP
- Success rate
- Average execution time
- Total cost
- Current status (Running/Idle/Paused/Error)

This matches the leaderboard layout defined in the existing spec (`specs/agent_status_dashboard.md`, lines 310-326).

**REQ-METRICS-003: Cost and Token Charts**
Provide visual charts for:
- Token usage by agent (horizontal bar chart)
- Cost trend over recent sessions (line chart)
- Success rate by agent (bar chart)

### 3.3 Event Feed

**REQ-FEED-001: Live Activity Feed**
A scrolling feed showing agent events as they happen:
- Timestamp
- Agent name
- Status icon (success/error)
- Ticket key
- Duration
- Brief description

Format matches the "RECENT ACTIVITY" panel in the existing spec.

---

## 4. Agent Control — Pause, Edit, Resume

### 4.1 Pause/Resume

**REQ-CONTROL-001: Pause Agent**
The user must be able to pause a running agent. Pausing:
- Signals the orchestrator to stop delegating new work to this agent
- Does NOT terminate an in-progress delegation (the current task completes)
- Sets the agent's status to "Paused" in the status panel
- Inserts a system message in the chat: "Agent [name] paused by user"
- Prevents the orchestrator from selecting this agent for new tasks

**REQ-CONTROL-002: Resume Agent**
The user must be able to resume a paused agent. Resuming:
- Restores the agent to "Idle" status
- Makes the agent available for new delegations
- Inserts a system message in the chat: "Agent [name] resumed by user"

**REQ-CONTROL-003: Pause All / Resume All**
Global controls to pause or resume all agents simultaneously. When all agents are paused:
- The orchestrator enters a holding state
- A prominent banner shows "All agents paused — system is idle"
- No new delegations are dispatched

### 4.2 Requirement Editing

**REQ-CONTROL-004: View Current Requirements**
The dashboard must show the current requirement instructions for each active ticket. Requirements come from:
- Linear issue title and description (via Linear MCP tools)
- The `app_spec.txt` specification (from `specs/`)
- Any additional context passed by the orchestrator

**REQ-CONTROL-005: Edit Requirements Mid-Flight**
While an agent is paused, the user must be able to:
- Edit the requirement text for the ticket the agent was working on
- The edit interface is a text editor with markdown support
- Changes are saved and will be passed to the agent when it resumes

**REQ-CONTROL-006: Requirement Edit Flow**
The complete flow for editing requirements:
1. User pauses the agent (the current delegation completes)
2. User opens the requirement editor for the agent's current ticket
3. User modifies the requirement instructions
4. User saves the changes
5. User resumes the agent
6. The orchestrator passes the updated requirements to the agent on next delegation

**REQ-CONTROL-007: Requirement Sync to Linear**
When the user edits requirements through the dashboard, changes must optionally sync back to the Linear issue description (configurable via a toggle). This uses the existing Linear MCP tools.

---

## 5. Reasoning and Decision Transparency

### 5.1 Reasoning Display

**REQ-REASONING-001: Live Reasoning Stream**
The chat interface must show the AI's reasoning and decision-making process in real-time, similar to how Claude Code displays its thinking. This includes:
- The orchestrator's decision about which agent to delegate to and why
- The orchestrator's complexity assessment (Simple vs Complex)
- Context being passed between agents

Display format:
```
┌─ Orchestrator Reasoning ─────────────────────────────────────┐
│ Ticket AI-42: "Add user authentication"                       │
│ Complexity: COMPLEX (auth, security-related code)             │
│ Decision: Delegate to `coding` (sonnet) — not `coding_fast`  │
│ Reason: Security-related changes require deeper analysis      │
│ Context passed: Full issue description + existing auth files  │
└──────────────────────────────────────────────────────────────┘
```

**REQ-REASONING-002: Agent Thinking Display**
When an agent is working, display its reasoning steps:
- What files it is reading and why
- What changes it is planning
- What commands it is executing
- What tests it is running

This is the "inner monologue" of the agent, streamed in real-time.

**REQ-REASONING-003: Collapsible Reasoning Blocks**
Reasoning blocks must be collapsible:
- Default: collapsed, showing only a one-line summary
- Expanded: full reasoning text, tool calls, and responses
- The user can toggle individual blocks or expand/collapse all

### 5.2 Decision History

**REQ-DECISION-001: Decision Log**
Maintain a log of all orchestrator decisions:
- Agent selection decisions (which agent was chosen and alternatives considered)
- Complexity assessments
- Verification gate decisions (skip vs. run verification)
- PR review routing (pr_reviewer vs pr_reviewer_fast)
- Error recovery decisions

**REQ-DECISION-002: Decision Audit Trail**
Each decision in the log includes:
- Timestamp
- Decision type
- Input factors (ticket key, complexity keywords found, recent verification status)
- Outcome (agent selected, model used)
- Link to the resulting agent event

### 5.3 Code Generation Display

**REQ-CODE-001: Live Code Streaming**
When a coding agent (coding or coding_fast) is generating code, the dashboard must:
- Stream the code as it is being written (character-by-character or chunk-by-chunk)
- Show syntax highlighting
- Show which file is being edited
- Show the diff (additions/deletions) in real-time

**REQ-CODE-002: File Change Summary**
After a coding delegation completes, show a summary:
- List of files created/modified/deleted
- Line counts (added/removed)
- Diff view for each file (collapsible)

**REQ-CODE-003: Test Results Display**
When the coding agent runs tests, display:
- Test command executed
- Pass/fail status for each test
- Error output for failed tests
- Screenshot evidence (if Playwright tests)

---

## 6. Technical Requirements

### 6.1 Architecture

**REQ-TECH-001: Backend Server**
Python async server using `aiohttp` or `FastAPI`. The server:
- Serves the web dashboard (single-page application)
- Exposes REST API endpoints for dashboard data
- Maintains WebSocket connections for real-time updates
- Interfaces with the existing orchestrator and metrics collector

**REQ-TECH-002: Frontend**
Single HTML file with embedded CSS and JavaScript (no build step required). This matches the approach specified in the existing dashboard spec (`specs/agent_status_dashboard.md`, line 428):
> **No frontend build step** — single HTML file with embedded CSS/JS

**REQ-TECH-003: WebSocket Protocol**
Real-time updates via WebSocket. Message types:
- `agent_status` — Agent status change (idle → running → paused → error)
- `agent_event` — New agent event recorded
- `reasoning` — Orchestrator or agent reasoning text
- `code_stream` — Live code generation chunks
- `chat_message` — Chat response chunk (streaming)
- `metrics_update` — Updated dashboard metrics
- `control_ack` — Acknowledgment of pause/resume/edit commands

**REQ-TECH-004: REST API Endpoints**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/metrics` | Current `DashboardState` |
| GET | `/api/agents` | All agent profiles |
| GET | `/api/agents/{name}` | Single agent profile |
| GET | `/api/agents/{name}/events` | Recent events for an agent |
| GET | `/api/sessions` | Session history |
| GET | `/api/providers` | Available AI providers and models |
| POST | `/api/chat` | Send a chat message (returns streaming response) |
| POST | `/api/agents/{name}/pause` | Pause an agent |
| POST | `/api/agents/{name}/resume` | Resume an agent |
| PUT | `/api/requirements/{ticket_key}` | Update requirement instructions |
| GET | `/api/requirements/{ticket_key}` | Get current requirement instructions |
| GET | `/api/decisions` | Decision history log |
| GET | `/` | Serve the dashboard HTML |

**REQ-TECH-005: Data Source**
All metrics data reads from `.agent_metrics.json` via the existing `MetricsStore` class. Agent definitions come from `agents/definitions.py`. Provider availability comes from environment variable checks (API keys for each bridge module).

### 6.2 Integration Points

**REQ-TECH-006: Metrics Collector Hook**
The dashboard server subscribes to `AgentMetricsCollector` events. When the collector records a new event (in `_record_event()` in `agent_metrics_collector.py`), it must also emit the event to connected WebSocket clients.

**REQ-TECH-007: Orchestrator Hook**
The orchestrator (`agents/orchestrator.py`) must emit reasoning and delegation decisions to the dashboard server. This requires adding event emission points in `run_orchestrated_session()`.

**REQ-TECH-008: Chat-to-Agent Bridge**
When the user sends a chat message that requires agent action, the dashboard server must:
1. Parse the user intent
2. Route to the appropriate agent (or let the orchestrator decide)
3. Execute the delegation through the existing session loop
4. Stream results back to the chat

**REQ-TECH-009: Provider Bridge Integration**
Chat messages routed to non-Claude providers use the existing bridge modules:
- `bridges/openai_bridge.py` for ChatGPT
- `bridges/gemini_bridge.py` for Gemini
- `bridges/groq_bridge.py` for Groq
- `bridges/kimi_bridge.py` for KIMI
- `bridges/windsurf_bridge.py` for Windsurf

### 6.3 Configuration

**REQ-TECH-010: Environment Variables**
New environment variables (all optional, with sensible defaults):

| Variable | Default | Description |
|----------|---------|-------------|
| `DASHBOARD_WEB_PORT` | `8420` | Port for the web dashboard server |
| `DASHBOARD_WS_PORT` | `8421` | Port for WebSocket connections (or same port via upgrade) |
| `DASHBOARD_HOST` | `0.0.0.0` | Host to bind the dashboard server |
| `DASHBOARD_AUTH_TOKEN` | (none) | Bearer token for dashboard API authentication |
| `DASHBOARD_CORS_ORIGINS` | `*` | Allowed CORS origins |

### 6.4 Security

**REQ-TECH-011: Authentication**
If `DASHBOARD_AUTH_TOKEN` is set, all API endpoints and WebSocket connections require a valid bearer token. If not set, the dashboard is open (suitable for local development).

**REQ-TECH-012: Sandbox Compliance**
The dashboard server must operate within the existing security model:
- Bash commands executed through the chat are subject to the allowlist in `security.py`
- File operations are restricted to the project directory
- MCP tool calls go through the Arcade gateway with existing authorization

---

## 7. User Interface Layout

### 7.1 Main Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  HEADER: Project name │ Session # │ Total cost │ Tokens │ Provider │
├───────────────────────────┬─────────────────────────────────────────┤
│                           │                                         │
│   LEFT PANEL (30%)        │   MAIN PANEL (70%)                      │
│                           │                                         │
│   ┌───────────────────┐   │   ┌─────────────────────────────────┐   │
│   │ Agent Status       │   │   │                                 │   │
│   │ Panel              │   │   │  AI Chat Interface               │   │
│   │                    │   │   │                                 │   │
│   │ • coding  ● RUN   │   │   │  [Reasoning blocks]             │   │
│   │ • github  ○ IDLE  │   │   │  [Code streaming]               │   │
│   │ • linear  ○ IDLE  │   │   │  [Tool call results]            │   │
│   │ • slack   ○ IDLE  │   │   │  [Chat messages]                │   │
│   │ • ops     ○ IDLE  │   │   │                                 │   │
│   │ • pr_rev  ○ IDLE  │   │   │                                 │   │
│   │ ...               │   │   │                                 │   │
│   └───────────────────┘   │   │                                 │   │
│                           │   │                                 │   │
│   ┌───────────────────┐   │   │                                 │   │
│   │ Active Requirement │   │   │                                 │   │
│   │                    │   │   │                                 │   │
│   │ AI-42: Add user   │   │   │                                 │   │
│   │ authentication    │   │   │                                 │   │
│   │                    │   │   ├─────────────────────────────────┤   │
│   │ [Edit] [Pause]    │   │   │ Provider: Claude │ Model: Opus  │   │
│   └───────────────────┘   │   │ ┌─────────────────────────────┐ │   │
│                           │   │ │ Type a message...       [→] │ │   │
│   ┌───────────────────┐   │   │ └─────────────────────────────┘ │   │
│   │ Activity Feed      │   │   └─────────────────────────────────┘   │
│   │                    │   │                                         │
│   │ 14:23 coding ✓    │   │                                         │
│   │ 14:22 github ✓    │   │                                         │
│   │ 14:21 linear ✓    │   │                                         │
│   └───────────────────┘   │                                         │
├───────────────────────────┴─────────────────────────────────────────┤
│  FOOTER: Agent Leaderboard Summary │ Pause All │ Resume All        │
└─────────────────────────────────────────────────────────────────────┘
```

### 7.2 Responsive Behavior

**REQ-UI-001: Panel Collapsibility**
The left panel collapses to an icon bar on narrow viewports. The main chat panel takes full width.

**REQ-UI-002: Dark Mode**
The dashboard defaults to dark mode (consistent with terminal/IDE workflows). A toggle switches to light mode.

---

## 8. Data Flow Specifications

### 8.1 Chat Message Flow

```
User types message in chat input
  │
  ▼
Frontend sends POST /api/chat { message, provider, model }
  │
  ▼
Backend determines routing:
  ├─ Direct AI query → Route to selected provider via bridge module
  ├─ Agent command → Route to orchestrator for delegation
  └─ Tool request → Execute via Arcade MCP gateway
  │
  ▼
Backend streams response via WebSocket:
  ├─ reasoning: Orchestrator's delegation decision
  ├─ code_stream: Live code from coding agent
  ├─ chat_message: Text response chunks
  └─ agent_event: Status updates
  │
  ▼
Frontend renders response in chat thread
```

### 8.2 Pause/Resume Flow

```
User clicks Pause on agent "coding"
  │
  ▼
Frontend sends POST /api/agents/coding/pause
  │
  ▼
Backend sets agent state to "paused" in orchestrator config
  │
  ▼
Current delegation completes normally (not interrupted)
  │
  ▼
Orchestrator skips "coding" for new delegations
  │
  ▼
WebSocket broadcasts: { type: "agent_status", agent: "coding", status: "paused" }
  │
  ▼
Frontend updates status panel + inserts system message
```

### 8.3 Requirement Edit Flow

```
User pauses agent → clicks Edit on active ticket AI-42
  │
  ▼
Frontend fetches GET /api/requirements/AI-42
  │
  ▼
User modifies requirement text in editor
  │
  ▼
User saves → Frontend sends PUT /api/requirements/AI-42 { text }
  │
  ▼
Backend stores updated requirements
  │
  ▼
If "sync to Linear" enabled: Backend updates Linear issue via MCP
  │
  ▼
User resumes agent → POST /api/agents/coding/resume
  │
  ▼
Orchestrator passes updated requirements on next delegation
```

### 8.4 Reasoning Stream Flow

```
Orchestrator starts processing ticket
  │
  ▼
Orchestrator evaluates complexity keywords in title/description
  │
  ▼
Orchestrator emits reasoning event:
  { type: "reasoning", content: "Complexity: COMPLEX — auth keyword found" }
  │
  ▼
Orchestrator selects agent and model
  │
  ▼
Orchestrator emits decision event:
  { type: "reasoning", content: "Routing to coding (sonnet) — security-related" }
  │
  ▼
WebSocket broadcasts to all connected clients
  │
  ▼
Frontend renders reasoning block (collapsed by default)
```

---

## 9. Non-Functional Requirements

### 9.1 Performance

**REQ-PERF-001: WebSocket Latency**
Events must reach connected clients within 100ms of being emitted by the collector or orchestrator.

**REQ-PERF-002: Dashboard Load Time**
The dashboard HTML page must load in under 2 seconds on localhost (no external CDN dependencies).

**REQ-PERF-003: Chat Response Streaming**
Chat responses must begin streaming to the client within 500ms of the AI provider starting its response.

### 9.2 Reliability

**REQ-REL-001: Crash Isolation**
Dashboard server failures must never crash the orchestrator or agent session loop. The dashboard is an optional view layer. If the WebSocket disconnects, agents continue operating normally.

**REQ-REL-002: Reconnection**
If the WebSocket connection drops, the frontend must automatically reconnect with exponential backoff (1s, 2s, 4s, 8s, max 30s). On reconnect, the client fetches current state via REST API to resynchronize.

**REQ-REL-003: Graceful Degradation**
If the metrics file (`.agent_metrics.json`) is missing or corrupted:
- The dashboard shows empty state with a clear message
- The collector creates a fresh metrics file
- No data loss in other parts of the system

### 9.3 Observability

**REQ-OBS-001: Server Logging**
The dashboard server logs:
- WebSocket connections/disconnections
- API requests (method, path, status code)
- Provider routing decisions
- Errors with stack traces

---

## 10. Implementation Constraints

### 10.1 Karpathy Principles Compliance

All implementation must follow these constraints:

**Simplicity First:**
- Single HTML file for the frontend (no React, no build step, no npm)
- Vanilla JavaScript with no framework dependencies
- CSS embedded in the HTML file
- Minimal Python dependencies (prefer stdlib, reuse existing requirements)

**Surgical Changes:**
- Do not refactor existing code in `agent.py`, `orchestrator.py`, or `definitions.py` beyond adding event emission hooks
- New functionality goes in new files
- Existing interfaces remain unchanged

**Goal-Driven Execution:**
- Every feature has a testable success criterion
- Tests verify behavior, not implementation details
- Each phase is independently deployable

### 10.2 Compatibility

**REQ-COMPAT-001: Python Version**
Python 3.10+ (matching existing `pyproject.toml` target)

**REQ-COMPAT-002: No New System Dependencies**
The dashboard must work with the existing `requirements.txt` plus at most `aiohttp` (or use stdlib `asyncio` with `http.server`).

**REQ-COMPAT-003: Existing Security Model**
All operations through the dashboard are subject to the same security constraints as CLI operations:
- Bash allowlist (`security.py`)
- File permissions (project directory only)
- Arcade MCP authorization

---

## 11. Implementation Phases

### Phase 1: Foundation
**Goal:** Dashboard server starts and serves a static page with agent status.
**Success criteria:** `python scripts/dashboard_server.py --project-dir my-app` opens a browser showing all 13 agents with their current status from `.agent_metrics.json`.

- [ ] Create `scripts/dashboard_server.py` with async HTTP server
- [ ] Create single-file HTML dashboard with agent status panel
- [ ] REST API: `/api/health`, `/api/metrics`, `/api/agents`
- [ ] Load data from existing `MetricsStore`

### Phase 2: Real-Time Updates
**Goal:** Agent status updates appear in the dashboard without page refresh.
**Success criteria:** When the orchestrator delegates to a coding agent, the dashboard shows the agent transition from Idle to Running within 1 second.

- [ ] Add WebSocket server
- [ ] Add event emission hooks in `agent.py` and `agents/orchestrator.py`
- [ ] Frontend WebSocket client with auto-reconnection
- [ ] Live activity feed

### Phase 3: AI Chat Interface
**Goal:** User can chat with Claude through the dashboard and see responses.
**Success criteria:** User types "What is the status of all Linear issues?" and receives a formatted response with data from Linear.

- [ ] Chat UI component (message thread, input box)
- [ ] POST `/api/chat` endpoint with streaming response
- [ ] Provider/model selector UI
- [ ] Tool call transparency (show Linear/Slack/GitHub tool invocations)

### Phase 4: Multi-Provider Support
**Goal:** User can switch AI providers and models in the chat.
**Success criteria:** User switches from Claude to Gemini, sends a message, and receives a response from Gemini 2.5 Flash.

- [ ] Provider availability detection (check API keys)
- [ ] Bridge module integration for chat routing
- [ ] Provider status indicators in UI
- [ ] Hot-swap without context loss

### Phase 5: Agent Controls
**Goal:** User can pause, edit requirements, and resume agents.
**Success criteria:** User pauses the coding agent, edits the requirement for AI-42, resumes, and the agent picks up the updated requirements.

- [ ] Pause/Resume API endpoints and UI controls
- [ ] Requirement editor UI
- [ ] Requirement sync to Linear (optional)
- [ ] Pause All / Resume All global controls

### Phase 6: Reasoning and Decision Transparency
**Goal:** User can see why the orchestrator made each decision.
**Success criteria:** When the orchestrator delegates to `coding` instead of `coding_fast`, the dashboard shows the reasoning: "Complexity: COMPLEX — auth keyword found. Routing to coding (sonnet)."

- [ ] Reasoning event emission from orchestrator
- [ ] Collapsible reasoning blocks in chat UI
- [ ] Decision history log
- [ ] Live code streaming from coding agents

---

## 12. Testing Strategy

### 12.1 Unit Tests
Following the existing test pattern in `scripts/test_security.py` (custom `test_hook()` harness):

- **API endpoint tests:** Verify each REST endpoint returns correct data
- **WebSocket tests:** Verify event broadcasting and message types
- **Provider routing tests:** Verify chat messages route to correct provider
- **Pause/Resume state tests:** Verify agent state transitions
- **Requirement edit tests:** Verify requirement persistence and sync

### 12.2 Integration Tests
- **End-to-end chat flow:** Send message → receive response → verify in history
- **Agent lifecycle:** Start agent → pause → edit → resume → verify updated context
- **Provider switching:** Chat with Claude → switch to Gemini → verify response from Gemini
- **Metrics accuracy:** Run agent delegation → verify dashboard metrics update

### 12.3 Manual Verification
- Dashboard loads and displays all 13 agents
- Chat input accepts messages and displays responses
- Provider selector shows availability status
- Pause/Resume controls work correctly
- Reasoning blocks render and collapse
- Code streaming displays syntax highlighting

---

## 13. Glossary

| Term | Definition |
|------|------------|
| Agent | A specialized sub-agent defined in `agents/definitions.py` (e.g., coding, github, linear) |
| Bridge | An adapter module in `bridges/` that connects to an external AI provider |
| Delegation | The act of the orchestrator assigning a task to a specialized agent |
| MCP | Model Context Protocol — the interface used for Linear, GitHub, Slack tool access via Arcade |
| Orchestrator | The coordinating agent (`agents/orchestrator.py`) that delegates work to specialized agents |
| Provider | An AI model provider (Claude, ChatGPT, Gemini, Groq, KIMI, Windsurf) |
| Ticket | A Linear issue representing a unit of work |

---

## 14. References

- Existing dashboard spec: `specs/agent_status_dashboard.md`
- Agent definitions: `agents/definitions.py`
- Orchestrator: `agents/orchestrator.py`
- Session loop: `agent.py`
- Metrics types: `generations/agent-status-dashboard/metrics.py`
- Metrics collector: `generations/agent-status-dashboard/agent_metrics_collector.py`
- Bridge modules: `bridges/openai_bridge.py`, `bridges/gemini_bridge.py`, `bridges/groq_bridge.py`, `bridges/kimi_bridge.py`, `bridges/windsurf_bridge.py`
- Arcade MCP config: `scripts/arcade_config.py`
- Security model: `security.py`
- Karpathy coding principles: [forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills/tree/main)
