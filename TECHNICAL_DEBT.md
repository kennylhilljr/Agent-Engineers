# Technical Debt Backlog

**Project:** Agent-Engineers
**Linear Issue:** AI-202
**Created:** 2026-02-17
**Last Updated:** 2026-02-18

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
| **Priority**| Medium → High (escalated in AI-231) |
| **Status**  | **RESOLVED — 2026-02-18 (AI-231)** |
| **Resolved**| Fully — regex extraction implemented in `run_agent_session()` |

**Context:**

The `run_agent_session` function accepts a `ticket_key` parameter that is used
to broadcast the active ticket to the dashboard WebSocket server. In the
_standalone main loop_ (`run_autonomous_agent` function in `agent.py`), the
loop invokes the agent using MCP tools to discover and pick up Linear tickets
dynamically each session — it does not receive a pre-assigned ticket key.

By contrast, the daemon path (`scripts/daemon.py` → `run_worker`) and the
scalable worker pool (`daemon/worker_pool.py`) already pass `ticket_key`
explicitly, because the ticket is known before the agent session starts.

**Resolution (AI-231 — 2026-02-18):**

Implemented Option A (preferred): after collecting `response_text` inside
`run_agent_session()`, the code now calls `extract_ticket_key(response_text)`
which scans for the `PROJECT_TICKET: <KEY>` pattern using a pre-compiled
`re.compile` pattern (`TICKET_KEY_PATTERN`).

Changes made:

1. **`agent.py`** — Added:
   - `import re` at the top of the file.
   - `TICKET_KEY_PATTERN = re.compile(r"PROJECT_TICKET:\s*([A-Z]+-\d+)")` constant.
   - `extract_ticket_key(text: str) -> str | None` helper function.
   - Logic in `run_agent_session()` to call `extract_ticket_key()` after
     collecting `response_text`. When a key is found and no `ticket_key` was
     pre-assigned, an intermediate `broadcast_agent_status(status="running",
     metadata={"ticket_key": extracted_key})` call is made so the dashboard
     updates within seconds of the agent outputting the pattern.
   - `effective_ticket_key = ticket_key or extracted_key` ensures the
     pre-assigned daemon-path key always takes precedence (no regression).

2. **`tests/test_agent.py`** — Added `TestExtractTicketKey` (20 unit tests)
   and `TestRunAgentSessionTicketKeyExtraction` (3 integration tests) covering:
   - Happy path extraction from various text positions.
   - Extra/no whitespace after colon.
   - Multiple mentions → first match returned.
   - Missing pattern → `None` fallback.
   - Empty/whitespace/`None` input → `None` fallback.
   - Malformed patterns (lowercase, missing dash, numeric prefix, partial signal).
   - Daemon-path regression: pre-assigned key not clobbered by response text.

**Daemon path regression verified:** `effective_ticket_key = ticket_key or
extracted_key` means a truthy pre-assigned `ticket_key` always wins. The extra
"running" broadcast for the extracted key is guarded by `if extracted_key and
not ticket_key`, so daemon workers are unaffected.

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

---

## AI-191 Audit — dashboard/ Directory (2026-02-18)

**Audit Date:** 2026-02-18
**Linear Issue:** AI-191
**Scope:** `dashboard/*.py` files only

Audit command used:
```
grep -rn "TODO\|FIXME\|HACK" \
  /Users/bkh223/Documents/GitHub/agent-engineers/generations/agent-dashboard/dashboard/ \
  --include="*.py"
```

**Result: 0 TODO/FIXME/HACK comments found in dashboard/ directory.**

All `dashboard/*.py` files (intent_parser.py, agent_executor.py, chat_handler.py,
provider_bridge.py, config.py, rest_api_server.py, server.py, logging_config.py)
are clean with no deferred work markers.

### Summary Statistics

| Metric | Value |
|--------|-------|
| Files scanned | dashboard/*.py |
| TODOs found | 0 |
| FIXMEs found | 0 |
| HACKs found | 0 |
| Items resolved | 0 (none found) |
| Items deferred | 0 (none found) |

**Status: CLEAN — no technical debt markers in dashboard/ module.**

---

## Changelog

| Date       | Change |
|------------|--------|
| 2026-02-17 | Initial audit (AI-202). Found 1 active TODO. Replaced TODO marker with detailed explanatory comment. Added TD-001 entry. |
| 2026-02-18 | AI-191 audit of dashboard/ directory. Zero TODO/FIXME/HACK comments found. Dashboard module is clean. |
| 2026-02-18 | AI-231 resolves TD-001. Implemented `extract_ticket_key()` and `TICKET_KEY_PATTERN` in `agent.py`. Added 23 unit/integration tests in `tests/test_agent.py`. Dashboard now shows active ticket key for standalone sessions within 10 s of agent emitting `PROJECT_TICKET: <KEY>`. |
