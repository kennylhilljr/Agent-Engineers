# Agent Status Dashboard — Feature Spec

## Overview

A real-time monitoring dashboard that surfaces the operational health, performance metrics, contribution history, and strengths/weaknesses of every agent in the multi-agent orchestrator. The dashboard has two complementary interfaces: a **CLI live view** (primary, for terminal workflows) and a **web UI** (optional, for richer visualization). All data flows from a single `AgentMetricsCollector` that hooks into the existing session loop.

---

## Goals

1. **Visibility** — See what every agent is doing right now, at a glance
2. **Cost awareness** — Track token usage and estimated cost per agent, per session, and per ticket
3. **Contribution tracking** — Record what each agent has accomplished with quantitative metrics
4. **Strengths & weaknesses** — Surface per-agent performance profiles (success rates, error patterns, speed)
5. **Gamification** — Rank agents with XP, levels, streaks, and achievements to make monitoring engaging
6. **Actionable** — Surface stalls, errors, and regressions early so the operator can intervene

---

## Architecture

### Data Flow

```
Session Loop (agent.py)
  └─► AgentMetricsCollector (new: metrics.py)
        ├─► MetricsStore (JSON file: .agent_metrics.json per project)
        ├─► CLI Dashboard (new: scripts/agent_dashboard.py)
        └─► Web Dashboard (optional: scripts/dashboard_server.py)

Orchestrator delegates to agents
  └─► Each delegation emits: start_event, end_event, error_event
        └─► Collector records timing, tokens, outcome, artifacts
```

### New Files

| File | Purpose |
|---|---|
| `metrics.py` | `AgentMetricsCollector` class, `MetricsStore`, data types |
| `scripts/agent_dashboard.py` | CLI live dashboard (curses/rich) |
| `scripts/dashboard_server.py` | Optional web UI server (asyncio + HTTP) |
| `scripts/test_metrics.py` | Tests for the metrics module |

### Modified Files

| File | Change |
|---|---|
| `agent.py` | Instrument session loop to emit metrics events |
| `agents/orchestrator.py` | Instrument delegation calls to emit per-agent events |
| `progress.py` | Add `AgentProfile` to `ProjectState` |
| `client.py` | Pass collector into client options |
| `CLAUDE.md` | Document the new feature |

---

## Data Model

### `AgentEvent` — Single agent invocation record

```python
class AgentEvent(TypedDict):
    """One agent delegation or session invocation."""
    event_id: str              # UUID
    agent_name: str            # "coding", "github", "linear", "slack", etc.
    session_id: str            # Parent session identifier
    ticket_key: str            # Linear ticket key (if applicable)
    started_at: str            # ISO 8601
    ended_at: str              # ISO 8601
    duration_seconds: float
    status: Literal["success", "error", "timeout", "blocked"]

    # Token tracking
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float  # Based on model pricing

    # Contribution artifacts
    artifacts: list[str]       # ["commit:abc123", "pr:#42", "file:src/foo.py", "issue:AI-12"]
    error_message: str         # Empty string if success
    model_used: str            # "claude-haiku-4-5", "claude-sonnet-4-5", etc.
```

### `AgentProfile` — Cumulative per-agent stats

```python
class AgentProfile(TypedDict):
    """Cumulative performance profile for one agent."""
    agent_name: str

    # Lifetime counters
    total_invocations: int
    successful_invocations: int
    failed_invocations: int
    total_tokens: int
    total_cost_usd: float
    total_duration_seconds: float

    # Contribution counters
    commits_made: int          # GitHub agent
    prs_created: int           # GitHub agent
    prs_merged: int            # GitHub agent
    files_created: int         # Coding agent
    files_modified: int        # Coding agent
    lines_added: int           # Coding agent
    lines_removed: int         # Coding agent
    tests_written: int         # Coding agent
    issues_created: int        # Linear agent
    issues_completed: int      # Linear agent
    messages_sent: int         # Slack agent
    reviews_completed: int     # PR Reviewer agent

    # Derived metrics (recalculated on read)
    success_rate: float        # successful / total
    avg_duration_seconds: float
    avg_tokens_per_call: float
    cost_per_success_usd: float

    # Gamification
    xp: int
    level: int
    current_streak: int        # Consecutive successes
    best_streak: int
    achievements: list[str]    # ["first_blood", "century_club", "perfect_day", ...]

    # Strengths & weaknesses (auto-detected)
    strengths: list[str]       # ["fast_execution", "high_success_rate", "low_cost"]
    weaknesses: list[str]      # ["high_error_rate", "slow", "expensive"]

    # Recent history (rolling window)
    recent_events: list[str]   # Last 20 event_ids for drill-down
    last_error: str            # Most recent error message
    last_active: str           # ISO 8601 timestamp
```

### `DashboardState` — Top-level metrics file

```python
class DashboardState(TypedDict):
    """Root structure of .agent_metrics.json."""
    version: int                               # Schema version (1)
    project_name: str
    created_at: str                            # ISO 8601
    updated_at: str                            # ISO 8601

    # Global counters
    total_sessions: int
    total_tokens: int
    total_cost_usd: float
    total_duration_seconds: float

    # Per-agent profiles
    agents: dict[str, AgentProfile]            # keyed by agent_name

    # Event log (append-only, capped at 500 entries)
    events: list[AgentEvent]

    # Session history
    sessions: list[SessionSummary]             # Last 50 sessions
```

### `SessionSummary` — Per-session rollup

```python
class SessionSummary(TypedDict):
    session_id: str
    session_number: int
    session_type: Literal["initializer", "continuation"]
    started_at: str
    ended_at: str
    status: Literal["continue", "error", "complete"]
    agents_invoked: list[str]
    total_tokens: int
    total_cost_usd: float
    tickets_worked: list[str]
```

---

## AgentMetricsCollector

The central class that instruments the session loop. It is designed to be **non-blocking** and **failure-tolerant** — metrics collection never crashes the agent.

```python
class AgentMetricsCollector:
    """Collects and persists agent performance metrics.

    Usage:
        collector = AgentMetricsCollector(project_dir)

        # Start a session
        collector.start_session(session_num, is_initializer)

        # Track an agent delegation
        with collector.track_agent("coding", ticket_key="AI-42") as tracker:
            result = await run_coding_agent(...)
            tracker.set_tokens(result.input_tokens, result.output_tokens)
            tracker.add_artifact("commit:abc123")
        # Automatically records duration, success/failure, and persists

        # End session
        collector.end_session(status="continue")
    """
```

### Key Methods

| Method | Description |
|---|---|
| `start_session(num, is_init)` | Begin tracking a new session |
| `end_session(status)` | Finalize session, update rollups |
| `track_agent(name, ticket_key)` | Context manager for one agent delegation |
| `record_error(agent, error)` | Record an agent error |
| `get_dashboard_state()` | Return current `DashboardState` for rendering |
| `get_agent_profile(name)` | Return one agent's `AgentProfile` |
| `get_leaderboard()` | Return agents sorted by XP |

### Persistence

- State persisted to `<project_dir>/.agent_metrics.json`
- Written after every agent delegation completes (not mid-delegation)
- Events capped at 500 (oldest evicted via FIFO)
- Sessions capped at 50
- File writes are atomic (write to `.tmp` then rename)
- All I/O wrapped in try/except — metrics never crash the agent

---

## Gamification System

### XP Awards

| Action | XP | Notes |
|---|---|---|
| Successful delegation | +10 | Base award |
| Ticket completed | +25 | When Linear issue moves to Done |
| PR created | +15 | GitHub agent |
| PR merged | +30 | GitHub agent |
| Tests pass | +20 | Coding agent (after verification) |
| Fast completion (< 60s) | +5 | Speed bonus |
| Error recovery | +10 | Success after previous failure |
| Streak bonus | +streak | +1 XP per consecutive success |

### Levels

| Level | XP Required | Title |
|---|---|---|
| 1 | 0 | Intern |
| 2 | 50 | Junior |
| 3 | 150 | Mid-Level |
| 4 | 400 | Senior |
| 5 | 800 | Staff |
| 6 | 1500 | Principal |
| 7 | 3000 | Distinguished |
| 8 | 5000 | Fellow |

### Achievements

| ID | Name | Condition |
|---|---|---|
| `first_blood` | First Blood | First successful invocation |
| `century_club` | Century Club | 100 successful invocations |
| `perfect_day` | Perfect Day | 10+ invocations in one session, 0 errors |
| `speed_demon` | Speed Demon | 5 consecutive completions under 30s |
| `comeback_kid` | Comeback Kid | Success immediately after 3+ consecutive errors |
| `big_spender` | Big Spender | Single invocation over $1.00 |
| `penny_pincher` | Penny Pincher | 50+ successes at < $0.01 each |
| `marathon` | Marathon Runner | 100+ invocations in a single project |
| `polyglot` | Polyglot | Agent used across 5+ different ticket types |
| `night_owl` | Night Owl | Invocation between 00:00-05:00 local time |
| `streak_10` | On Fire | 10 consecutive successes |
| `streak_25` | Unstoppable | 25 consecutive successes |

---

## Strengths & Weaknesses Detection

Auto-detected from rolling window of last 50 invocations per agent:

### Strengths (positive signals)

| Strength | Condition |
|---|---|
| `fast_execution` | Avg duration in bottom 25th percentile across agents |
| `high_success_rate` | Success rate > 95% |
| `cost_efficient` | Cost per success in bottom 25th percentile |
| `consistent` | Std deviation of duration < 20% of mean |
| `streak_builder` | Current streak > 10 |
| `error_recovery` | Recovers from errors within 1 retry > 80% of the time |

### Weaknesses (negative signals)

| Weakness | Condition |
|---|---|
| `slow` | Avg duration in top 25th percentile across agents |
| `high_error_rate` | Error rate > 15% |
| `expensive` | Cost per success in top 25th percentile |
| `inconsistent` | Std deviation of duration > 50% of mean |
| `fragile` | Same error message repeated 3+ times |
| `timeout_prone` | Timeout rate > 5% |

---

## CLI Dashboard (`scripts/agent_dashboard.py`)

A terminal-based live view using the `rich` library (already available or easily installable).

### Layout

```
╔══════════════════════════════════════════════════════════════════════╗
║  AGENT STATUS DASHBOARD  │  Project: my-app  │  Session #7         ║
║  Uptime: 2h 14m          │  Total Cost: $3.42 │  Tokens: 1.2M     ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  AGENT LEADERBOARD                                                   ║
║  ┌────────────────────────────────────────────────────────────────┐  ║
║  │ #  Agent        Lvl  XP     Success  Avg Time  Cost    Status │  ║
║  │ 1  coding       ★5   823    94.2%    45.3s     $1.84   ● RUN  │  ║
║  │ 2  github       ★4   412    98.1%    12.1s     $0.31   ○ IDLE │  ║
║  │ 3  linear       ★3   287    96.7%    8.4s      $0.18   ○ IDLE │  ║
║  │ 4  pr_reviewer  ★3   195    91.3%    34.7s     $0.72   ○ IDLE │  ║
║  │ 5  slack        ★2   108    100.0%   3.2s      $0.05   ○ IDLE │  ║
║  │ 6  ops          ★2   89     97.8%    6.1s      $0.12   ○ IDLE │  ║
║  └────────────────────────────────────────────────────────────────┘  ║
║                                                                      ║
║  ACTIVE NOW                                                          ║
║  ┌────────────────────────────────────────────────────────────────┐  ║
║  │ coding ★5 [████████░░] 45s │ Ticket: AI-42 │ Tokens: 12.4k   │  ║
║  │ Strengths: fast_execution, high_success_rate                   │  ║
║  │ Achievements: 🏆 Century Club, ⚡ Speed Demon, 🔥 On Fire     │  ║
║  └────────────────────────────────────────────────────────────────┘  ║
║                                                                      ║
║  RECENT ACTIVITY                        │  AGENT PROFILES            ║
║  ┌─────────────────────────────────┐    │  ┌──────────────────────┐  ║
║  │ 14:23 coding  ✓ AI-42 (34s)    │    │  │ coding (Sonnet)      │  ║
║  │ 14:22 github  ✓ PR #18 (8s)    │    │  │ Strengths:           │  ║
║  │ 14:21 linear  ✓ AI-42→Done (5s)│    │  │  ✓ fast_execution    │  ║
║  │ 14:20 slack   ✓ notify (2s)    │    │  │  ✓ high_success_rate │  ║
║  │ 14:15 coding  ✗ AI-41 err (62s)│    │  │ Weaknesses:          │  ║
║  │ 14:14 coding  ✓ AI-41 retry    │    │  │  ⚠ expensive         │  ║
║  └─────────────────────────────────┘    │  └──────────────────────┘  ║
║                                                                      ║
║  TOKEN USAGE (by agent)                 │  COST TREND (last 10 sess) ║
║  coding    ████████████████░░░░ 812k    │  #1  $0.12               ║
║  pr_review ██████░░░░░░░░░░░░░░ 198k    │  #2  $0.34               ║
║  github    ███░░░░░░░░░░░░░░░░░  94k    │  #3  $0.28  ▼            ║
║  linear    ██░░░░░░░░░░░░░░░░░░  67k    │  ...                      ║
║  slack     ░░░░░░░░░░░░░░░░░░░░  12k    │  #7  $0.51  ▲            ║
╚══════════════════════════════════════════════════════════════════════╝
```

### CLI Modes

| Command | Description |
|---|---|
| `python scripts/agent_dashboard.py --project-dir my-app` | Live dashboard (auto-refreshes every 5s) |
| `python scripts/agent_dashboard.py --project-dir my-app --once` | Single snapshot, then exit |
| `python scripts/agent_dashboard.py --project-dir my-app --json` | JSON output for piping |
| `python scripts/agent_dashboard.py --project-dir my-app --agent coding` | Drill into one agent |
| `python scripts/agent_dashboard.py --project-dir my-app --leaderboard` | Leaderboard only |
| `python scripts/agent_dashboard.py --project-dir my-app --achievements` | All achievements |

---

## Integration Points

### 1. Session Loop (`agent.py`)

Instrument `run_autonomous_agent()` to create and pass the collector:

```python
# In run_autonomous_agent():
collector = AgentMetricsCollector(project_dir)

while True:
    collector.start_session(iteration, is_first_run)
    # ... existing session logic ...
    collector.end_session(result.status)
```

### 2. Orchestrator Delegation (`agents/orchestrator.py`)

The orchestrator's delegation to sub-agents should emit events. Since delegations happen via the SDK's `Task` tool, we hook into the response stream:

```python
# In run_orchestrated_session():
# When ToolUseBlock.name == "Task", extract agent_name from input
# When the corresponding ToolResultBlock arrives, record the outcome
```

### 3. Agent-Specific Artifact Detection

Each agent type produces different artifacts that should be auto-detected from tool results:

| Agent | Artifacts Detected From |
|---|---|
| `coding` | Write/Edit tool calls → files_modified; Bash `git diff --stat` → lines_added/removed |
| `github` | Bash `git commit` → commits_made; `gh pr create` → prs_created |
| `linear` | Arcade Linear tools → issues_created, issues_completed |
| `slack` | Arcade Slack tools → messages_sent |
| `pr_reviewer` | GitHub review tools → reviews_completed |

### 4. Token Counting

Token counts come from the Claude Agent SDK's response metadata. The collector reads `usage.input_tokens` and `usage.output_tokens` from each API response and attributes them to the active agent.

### Cost Calculation

```python
MODEL_COSTS: dict[str, tuple[float, float]] = {
    # (input_cost_per_1k, output_cost_per_1k)
    "claude-haiku-4-5-20251001": (0.001, 0.005),
    "claude-sonnet-4-5-20250929": (0.003, 0.015),
    "claude-opus-4-5-20251101": (0.015, 0.075),
}
```

---

## Optional Web Dashboard (`scripts/dashboard_server.py`)

A lightweight HTTP server that serves the same data as the CLI but with richer visualization.

- **Stack:** Python `asyncio` + `aiohttp` (or stdlib `http.server`) + vanilla HTML/JS
- **No frontend build step** — single HTML file with embedded CSS/JS
- **Endpoint:** `GET /api/metrics` → returns `DashboardState` as JSON
- **Endpoint:** `GET /api/agents/<name>` → returns one `AgentProfile`
- **Endpoint:** `GET /` → serves the dashboard HTML
- **Auto-refresh:** WebSocket or polling every 5s

This is a stretch goal. The CLI dashboard is the primary interface.

---

## Implementation Plan

### Phase 1: Data Layer (`metrics.py`)
1. Define all TypedDict types (`AgentEvent`, `AgentProfile`, `DashboardState`, `SessionSummary`)
2. Implement `MetricsStore` (JSON persistence with atomic writes, FIFO eviction)
3. Implement `AgentMetricsCollector` with `track_agent()` context manager
4. Implement XP/level calculation functions
5. Implement strengths/weaknesses detection
6. Implement achievement checking

### Phase 2: Instrumentation
1. Instrument `agent.py` session loop with collector lifecycle
2. Instrument `agents/orchestrator.py` to emit delegation events
3. Add token counting from SDK response metadata
4. Add artifact detection per agent type

### Phase 3: CLI Dashboard (`scripts/agent_dashboard.py`)
1. Build live terminal dashboard using `rich` library
2. Implement leaderboard view
3. Implement agent detail/drill-down view
4. Implement achievement display
5. Add `--once`, `--json`, `--agent`, `--leaderboard` modes

### Phase 4: Testing & Polish
1. Write tests in `scripts/test_metrics.py` (following existing test pattern)
2. Test XP calculations, level thresholds, achievement triggers
3. Test strengths/weaknesses detection edge cases
4. Test persistence (atomic writes, corruption recovery)
5. Update `CLAUDE.md` with new feature documentation

### Phase 5 (Stretch): Web Dashboard
1. Implement `dashboard_server.py` with aiohttp
2. Create single-file HTML dashboard with charts
3. Add WebSocket for live updates

---

## Dependencies

| Package | Purpose | Notes |
|---|---|---|
| `rich` | CLI dashboard rendering | Add to requirements.txt |

No other new dependencies required. All other functionality uses stdlib (`json`, `time`, `datetime`, `uuid`, `statistics`).

---

## Configuration

New environment variables (all optional):

| Variable | Default | Description |
|---|---|---|
| `DASHBOARD_REFRESH_INTERVAL` | `5` | CLI refresh interval in seconds |
| `DASHBOARD_WEB_PORT` | `8420` | Web dashboard port |
| `METRICS_EVENTS_CAP` | `500` | Max events in metrics file |
| `METRICS_SESSIONS_CAP` | `50` | Max sessions in metrics file |

---

## Compatibility

- **Non-breaking:** All new functionality. No existing behavior changes.
- **Graceful degradation:** If `.agent_metrics.json` is missing or corrupted, the collector creates a fresh one. The agent never crashes due to metrics.
- **Backward compatible:** Existing `progress.py` state file (`.linear_project.json`) is untouched. Dashboard metrics are a separate file.
- **Integration with watchdog:** The watchdog (`scripts/agent_watchdog.py`) can optionally read `.agent_metrics.json` for richer health reporting, but this is not required.
