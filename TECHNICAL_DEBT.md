# Technical Debt Backlog

**Project:** Agent-Engineers
**Linear Issue:** AI-202
**Created:** 2026-02-17
**Last Updated:** 2026-02-17

This document tracks all TODO/FIXME comments identified in the codebase, their
resolution status, and the rationale for any deferred items. It is maintained
as part of AI-202 "Address Technical Debt - TODO/FIXME Comments".

---

## Audit Summary

Audit command used:
```
grep -rn "#.*TODO\|#.*FIXME\|#.*HACK\|#.*XXX" \
  /Users/bkh223/Documents/GitHub/agent-engineers \
  --include="*.py" \
  --exclude-dir=.venv \
  --exclude-dir=venv \
  --exclude-dir=__pycache__ \
  --exclude-dir=generations
```

**Total comment-style TODO/FIXME found:** 1
**Resolved:** 1 (comment clarified; functional deferral documented below)
**Deferred (pending future work):** 1 (same item — implementation still deferred)

> Note: The issue description mentioned 12 TODOs across 9 files. Those items
> were present in an earlier revision of the codebase and have already been
> resolved in prior commits. The `daemon/control_plane.py` and
> `scripts/daemon.py` files referenced in the issue context contain no
> remaining TODO/FIXME comment markers.

---

## Items Found

### TD-001 — ticket_key extraction in standalone agent loop

| Field       | Value |
|-------------|-------|
| **File**    | `agent.py` |
| **Line**    | 377 (original), now replaced with an explanatory block comment |
| **Original**| `ticket_key=None  # TODO: extract from Linear context` |
| **Priority**| Medium |
| **Status**  | Comment clarified in AI-202; implementation deferred |
| **Resolved**| Partially — TODO marker removed, rationale documented |

**Context:**

The `run_agent_session` function accepts a `ticket_key` parameter that is used
to broadcast the active ticket to the dashboard WebSocket server. In the
_standalone main loop_ (`main_loop` function in `agent.py`), the loop invokes
the agent using MCP tools to discover and pick up Linear tickets dynamically
each session — it does not receive a pre-assigned ticket key.

By contrast, the daemon path (`scripts/daemon.py` → `run_worker`) and the
scalable worker pool (`daemon/worker_pool.py`) already pass `ticket_key`
explicitly, because the ticket is known before the agent session starts.

**Why it is deferred:**

Extracting the active ticket key in the standalone loop would require:
1. A Linear API call (via MCP or REST) before each session to determine which
   ticket is currently assigned to the agent, **or**
2. Parsing the agent's response text to extract the ticket identifier it
   decided to work on.

Neither approach is trivial without refactoring the standalone loop to use
the same pre-assignment model as the daemon. This work is scoped to a future
Linear issue focused on standalone-loop improvements.

**What needs to happen:**

- Refactor `main_loop` to call the Linear MCP tool before each session to
  discover the next actionable ticket, then pass its key as `ticket_key`.
- Alternatively, parse the session response for a `PROJECT_TICKET: <key>`
  pattern (similar to how `SESSION_COMPLETE` is detected).
- Update `broadcast_agent_status` callers to always supply a ticket key so
  dashboard ticket tracking is complete.

---

## Items Previously Present (Now Fully Resolved in Earlier Commits)

The following items were identified in the issue description as existing in
prior revisions but have already been addressed:

| File                         | Count | Notes |
|------------------------------|-------|-------|
| `daemon/control_plane.py`    | 3     | No TODO/FIXME markers present in current revision |
| `scripts/daemon.py`          | 2     | No TODO/FIXME markers present in current revision |
| Other files (7)              | 7     | No TODO/FIXME markers present in current revision |

---

## Guidelines for Future TODOs

To keep technical debt controlled, all new TODO/FIXME comments must:

1. Reference a Linear issue (e.g., `# TODO(AI-NNN): <reason>`) **or** include
   an inline explanation of why deferral is justified.
2. Be captured in this file within the same PR that introduces them.
3. Not accumulate beyond 10 open items without a dedicated clean-up issue
   being created in Linear.

---

## Changelog

| Date       | Change |
|------------|--------|
| 2026-02-17 | Initial audit (AI-202). Found 1 active TODO. Replaced TODO marker with detailed explanatory comment. Added TD-001 entry. |
