# Proposals for 10x Development Velocity

## Executive Summary

After a thorough analysis of the Agent-Engineers codebase, I've identified **10 proposals** organized by impact and feasibility. The current system has a fundamentally **sequential execution model** with significant overhead at every layer. The biggest gains come from parallelizing work, reducing ceremony per ticket, and eliminating artificial delays.

---

## Current Bottleneck Analysis

The system processes tickets through an 8-step sequential pipeline per ticket:

```
Linear status check → Verification test → Slack notify → Transition to In Progress
→ Code implementation → Git commit + PR → PR review → Transition to Done
```

Each step involves a separate agent delegation through the orchestrator, and each delegation is a full SDK round-trip. A single ticket touches **6+ agent delegations** (linear, slack, coding, github, linear again, slack again, pr_reviewer, linear again, slack again). Most of these are sequential and blocking.

**Key numbers from the code:**
- `AUTO_CONTINUE_DELAY_SECONDS = 3` — 3s sleep between every session iteration (`agent.py:32`)
- Additional `asyncio.sleep(1)` between sessions (`agent.py:291`)
- `WORKER_COOLDOWN = 5` seconds between tickets in daemon mode (`daemon.py:84`)
- `DEFAULT_POLL_INTERVAL = 30` seconds between ticket polls (`daemon.py:69`)
- Fresh SDK client created every iteration, including MCP server init, settings file write, and prompt reload (`agent.py:240`, `client.py:149-222`)
- Orchestrator prompt is 433 lines, continuation task is 204 lines — retransmitted every session

---

## TIER 1: Quick Wins (High Impact, Low Effort)

### Proposal 1: Eliminate Artificial Delays

**Problem:** The system has 4+ seconds of hard-coded sleep per iteration that serve no purpose.

**Current code:**
- `agent.py:32` — `AUTO_CONTINUE_DELAY_SECONDS = 3`
- `agent.py:286` — `await asyncio.sleep(AUTO_CONTINUE_DELAY_SECONDS)`
- `agent.py:291` — `await asyncio.sleep(1)` ("Small delay between sessions")
- `daemon.py:84` — `WORKER_COOLDOWN = 5`

**Proposal:** Reduce all delays to 0.5s or remove them entirely. The comment says "prevents context window exhaustion" but context exhaustion is already handled by creating a fresh client each iteration. The delays add no safety value.

**Impact:** If a project has 10 features and each takes 3 iterations on average, that's 30 iterations × 4s = **2 minutes of pure waiting eliminated**. In daemon mode with `WORKER_COOLDOWN`, multiply by worker count.

---

### Proposal 2: Batch Orchestrator Ceremony Steps

**Problem:** For every single ticket, the orchestrator makes 6-9 sequential agent delegations. Many of these are lightweight and independent.

**Current flow per ticket (from `continuation_task.md`):**
1. Linear agent: get status (Step 2)
2. Coding agent: verification test (Step 3)
3. Slack agent: notify started (Step 4a)
4. Linear agent: transition to In Progress (Step 4b)
5. Coding agent: implement feature (Step 4c)
6. GitHub agent: commit + PR (Step 5)
7. Linear agent: transition to Review (Step 6a)
8. Slack agent: notify PR ready (Step 6b)
9. PR reviewer agent: review PR (Step 7)
10. Linear agent: transition to Done (Step 8)
11. Slack agent: notify completed (Step 8)

**Proposal:** Combine independent steps into parallel delegations:
- Steps 4a + 4b can run in parallel (Slack notify + Linear transition are independent)
- Steps 6a + 6b can run in parallel (Linear transition + Slack notify)
- Step 8's Linear transition + Slack notify can run in parallel

This requires updating the orchestrator prompt to instruct parallel delegation where the Claude SDK supports it (the `Task` tool can be called concurrently).

**Impact:** 3-4 fewer sequential round-trips per ticket. At ~15-30s per delegation, that's **45-120 seconds saved per ticket**.

---

### Proposal 3: Make Verification Test Conditional

**Problem:** The orchestrator runs a full Playwright verification test before every single ticket (Step 3). This is the most expensive pre-check — it starts a browser, loads the app, clicks through features, and takes screenshots.

**Current rule** (`continuation_task.md:37`): "Run init.sh to start dev server, then verify 1-2 completed features still work."

**Proposal:** Make verification conditional:
- **Skip verification** if the last ticket was completed successfully (APPROVED) and no error occurred
- **Run verification** only after: errors, PR rejections (CHANGES_REQUESTED), session restarts, or every Nth ticket (e.g., every 3rd)
- Track a `last_verification_status` flag in `.linear_project.json`

**Impact:** Verification takes 30-90 seconds per run. Skipping it for 2 out of every 3 tickets saves **60-180 seconds per 3 tickets**.

---

## TIER 2: Architectural Improvements (High Impact, Medium Effort)

### Proposal 4: Parallel Ticket Processing with the Daemon

**Problem:** The daemon (`daemon.py`) has a worker pool but uses a synthetic ticket pattern (`_poll_linear_tickets` returns a `LINEAR_CHECK` sentinel at line 129). Each worker runs a full orchestrator session that processes tickets sequentially. Workers don't actually work on different tickets in parallel — they all run the same continuation task and independently discover what to work on.

**Proposal:** Implement true parallel ticket dispatch:
1. **Add a pre-flight Linear API call** (via a lightweight SDK session or direct GraphQL) that fetches actual ticket IDs and statuses
2. **Assign specific tickets to specific workers** — each worker gets a concrete ticket key, not a generic "check Linear" instruction
3. **Add a ticket lock mechanism** in `.linear_project.json` (or a separate `.locks` directory) so workers don't pick the same ticket
4. **Modify the continuation task template** to accept a specific `--ticket-key` parameter so the orchestrator works on exactly one assigned ticket

**Impact:** With 3 workers processing 3 different tickets simultaneously instead of 1 at a time, this is an immediate **3x throughput multiplier**. With 5 workers, **5x**.

---

### Proposal 5: Reduce Orchestrator Overhead Per Session

**Problem:** Every session iteration creates a brand new SDK client (`agent.py:240`, `client.py:149-222`), which:
1. Validates Arcade config
2. Writes `.claude_settings.json` to disk
3. Creates 2 MCP server connections (Playwright npm, Arcade HTTP)
4. Loads and sends the 433-line orchestrator prompt
5. Loads and sends the 204-line continuation task

The orchestrator prompt and settings don't change between iterations.

**Proposal:**
- **Cache the security settings file** — only write it once on first session, skip on subsequent iterations (check if file exists and content matches)
- **Cache MCP server config** — reuse the same server config object across iterations instead of rebuilding
- **Condense the orchestrator prompt** — the 433-line prompt has significant redundancy (the same rules appear in both `orchestrator_prompt.md` and `continuation_task.md`). Consolidate to ~200 lines
- **Use prompt caching** — if the Claude SDK supports prompt caching (system prompt prefix caching), ensure the static system prompt is sent in a cacheable way so tokens aren't re-processed

**Impact:** Saves 2-5 seconds of client setup per iteration and reduces token consumption by ~40%. Over 20 iterations, that's **40-100 seconds and significant token cost savings**.

---

### Proposal 6: Collapse the Linear/Slack/GitHub Ceremony

**Problem:** The orchestrator uses separate haiku-powered agents for trivial operations. Sending a Slack message requires: orchestrator formats delegation → SDK creates haiku session → haiku reads Slack prompt → haiku calls one MCP tool → haiku returns. That's a full LLM round-trip for what is essentially a single API call.

Similarly, Linear status transitions are single MCP tool calls wrapped in a full agent delegation.

**Proposal:** Create a **composite "ops" agent** that handles all lightweight operations in a single delegation:
```
Instead of:
  1. Delegate to slack: "send started message"
  2. Delegate to linear: "transition to In Progress"
  3. Wait for both to return

Do:
  1. Delegate to ops agent: "For ticket AI-123:
     - Send Slack notification: Started
     - Transition Linear to In Progress
     - Return confirmations"
```

This combines 3-4 sequential delegations into 1. The ops agent gets all three tool sets (Linear + Slack + GitHub basic tools).

**Impact:** Reduces delegation count per ticket from 9-11 down to 4-5. At ~15-30s per delegation, saves **60-180 seconds per ticket**.

---

## TIER 3: Systemic Changes (Highest Impact, Highest Effort)

### Proposal 7: Intra-Session Multi-Ticket Pipeline

**Problem:** The orchestrator prompt instructs it to loop through tickets sequentially within a session (Step 8b in `continuation_task.md`). But each ticket goes through the full 8-step pipeline before the next one starts. There's no pipelining.

**Proposal:** Implement a pipelined execution model within a single orchestrator session:
```
Time →
Ticket 1: [Code] → [Commit+PR] → [Review]
Ticket 2:          [Code]       → [Commit+PR] → [Review]
Ticket 3:                        [Code]       → [Commit+PR] → [Review]
```

While Ticket 1 is in PR review, the coding agent starts on Ticket 2. While Ticket 2 is being coded, Ticket 1's review completes and gets marked Done.

This requires restructuring the orchestrator prompt to:
1. Maintain a pipeline state (which tickets are at which stage)
2. Issue parallel delegations (coding agent on Ticket 2 while PR reviewer reviews Ticket 1)
3. Handle out-of-order completions

**Impact:** With 3 tickets in the pipeline, the coding agent is always busy. The limiting factor becomes coding time, not ceremony. This could yield **2-3x throughput within a single session**.

---

### Proposal 8: Skip PR Review for Low-Risk Changes

**Problem:** Every ticket goes through a full PR review by a sonnet-powered PR reviewer agent. This adds a complete agent delegation cycle per ticket, even for trivial changes like copy updates or CSS fixes.

**Current rule** (`continuation_task.md:116-131`): PR review is mandatory for all tickets.

**Proposal:** Add a risk-based review policy:
- **Auto-approve** tickets where:
  - Files changed ≤ 3
  - No changes to auth, database, or API routes
  - All tests pass
  - Only frontend/UI changes
- **Full review** for:
  - Backend/API changes
  - Security-sensitive files
  - Changes touching > 5 files
  - Test failures

The orchestrator evaluates the coding agent's output and decides whether to skip to "merge + Done" or route through PR review.

**Impact:** For a typical 10-feature project where 60% of tickets are low-risk, this skips 6 PR review cycles. At ~30-60s each, saves **3-6 minutes total**.

---

### Proposal 9: Webhook-Driven Architecture (Replace Polling)

**Problem:** The daemon uses 30-second polling (`daemon.py:69`). After a ticket is completed, there's up to 30 seconds of idle time before the next poll discovers new work. Combined with `WORKER_COOLDOWN` (5s), workers sit idle for up to 35 seconds between tickets.

**Proposal:** Replace polling with an event-driven model:
1. **Linear webhooks** — Linear supports webhooks that fire on issue state changes. Set up a webhook endpoint that pushes events to the daemon
2. **Internal event queue** — Use `asyncio.Queue` as an internal work queue. Workers pull from the queue instead of waiting for polls
3. **Immediate dispatch** — When a ticket is completed, the worker immediately checks the queue for the next ticket (no cooldown, no polling delay)

**Implementation:**
- Add a lightweight HTTP server (e.g., `aiohttp` or `fastapi`) to the daemon that receives Linear webhook events
- Parse the webhook payload to identify actionable tickets
- Push to the work queue
- Workers `await queue.get()` instead of sleeping

**Impact:** Eliminates 30s poll latency + 5s cooldown = **35 seconds saved per ticket transition**. For 10 tickets across 3 workers, that's ~6 minutes of idle time eliminated.

---

### Proposal 10: Use Faster Models Strategically

**Problem:** The coding agent uses `sonnet` by default (`definitions.py:24`), and the PR reviewer also uses `sonnet`. These are the two most expensive and slowest operations. The orchestrator uses `haiku` which is fast but still processes 600+ lines of prompts.

**Proposal:** Implement a tiered model strategy:
- **Coding agent:** Use `sonnet` only for complex features (new components, state management, API routes). Use `haiku` for simple changes (copy, CSS, config, adding a test)
- **PR reviewer:** Use `haiku` for low-risk reviews (see Proposal 8). Use `sonnet` only for high-risk changes
- **Orchestrator:** Consider using a lighter prompt with `haiku` — the orchestrator doesn't do creative work, it follows a decision tree. A shorter, more structured prompt would let haiku perform better

The orchestrator can assess ticket complexity from the issue description and dynamically set the model for each delegation.

**Impact:** Haiku is ~10x faster than sonnet for simple tasks. Using haiku for 50% of coding tasks and 60% of reviews reduces total inference time by **30-40%**.

---

## Combined Impact Estimate

| Proposal | Category | Throughput Multiplier |
|----------|----------|----------------------|
| 1. Eliminate delays | Quick win | 1.1x |
| 2. Batch ceremony steps | Quick win | 1.2x |
| 3. Conditional verification | Quick win | 1.15x |
| 4. Parallel ticket processing | Architecture | 3-5x |
| 5. Reduce session overhead | Architecture | 1.2x |
| 6. Composite ops agent | Architecture | 1.3x |
| 7. Intra-session pipeline | Systemic | 2-3x |
| 8. Risk-based PR review | Systemic | 1.2x |
| 9. Webhook-driven dispatch | Systemic | 1.15x |
| 10. Strategic model selection | Systemic | 1.3x |

**Proposals 1-3 combined:** ~1.5x (easy wins, implement immediately)
**Proposals 4-6 combined:** ~4-6x (parallel workers + reduced overhead)
**Proposals 7-10 combined:** ~3-4x on top of parallelization (pipeline + reduced ceremony)

**All proposals combined (multiplicative):** Realistic estimate of **8-12x** throughput improvement.

---

## Recommended Implementation Order

### Phase 1 — Immediate (Proposals 1, 2, 3)
- Remove/reduce sleep delays in `agent.py` and `daemon.py`
- Update orchestrator prompt to batch independent delegations
- Add conditional verification logic

### Phase 2 — Parallel Workers (Proposal 4)
- Implement true ticket assignment in daemon
- Add ticket locking mechanism
- Scale to 5+ concurrent workers

### Phase 3 — Reduce Overhead (Proposals 5, 6)
- Cache settings and configs across iterations
- Consolidate prompts
- Create composite ops agent

### Phase 4 — Advanced Pipeline (Proposals 7, 8, 10)
- Implement intra-session pipelining
- Add risk-based review bypass
- Dynamic model selection per ticket

### Phase 5 — Event-Driven (Proposal 9)
- Set up Linear webhooks
- Replace polling with event queue
- Eliminate all inter-ticket idle time
