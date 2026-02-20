# Agent Routing Decision Tree

This document describes the criteria used by the orchestrator to select between
specialized agents and model tiers. It serves as the authoritative reference for
explainable, auditable agent assignment decisions.

---

## 1. CODING_FAST vs CODING

| Criterion | CODING_FAST (haiku) | CODING (sonnet) |
|-----------|---------------------|-----------------|
| **File count** | <= 3 files | > 3 files |
| **Task type** | Text/copy, CSS, config, docs, renames | New components, pages, API routes |
| **Complexity keywords** | None of the below | `implement`, `refactor`, `architecture`, `redesign`, `migration`, `integration`, `performance`, `database`, `schema`, `security`, `auth`, `billing` |
| **Estimated token budget** | < 4 000 tokens | >= 4 000 tokens |
| **Cross-cutting modules** | < 3 modules | >= 3 modules |
| **State / DB changes** | No | Yes |
| **Test coverage** | Adding tests for existing features | New test suites for new features |

### Decision Logic

```
if any(keyword in task_description for keyword in COMPLEX_KEYWORDS):
    agent = CODING
elif files_changed > 3:
    agent = CODING
elif estimated_tokens >= 4000:
    agent = CODING
elif modules_affected >= 3:
    agent = CODING
else:
    agent = CODING_FAST
```

---

## 2. PR_REVIEWER_FAST vs PR_REVIEWER

| Criterion | PR_REVIEWER_FAST (haiku) | PR_REVIEWER (sonnet) |
|-----------|--------------------------|----------------------|
| **Lines changed** | <= 200 lines | > 200 lines |
| **File count** | <= 3 files | > 3 files |
| **Module risk level** | Frontend, additive changes only | Backend, auth, billing, security, core |
| **Change type** | Purely additive (no deletions in risk dirs) | Any modification in sensitive directories |
| **Migration files** | None | Any file matching: `migration`, `schema`, `alembic`, `flyway` |
| **High-change-ratio files** | 0–3 files with >50% change ratio | > 3 files with >50% change ratio |
| **Manual override label** | — | `review:opus` (escalates to Opus tier) |

### Sensitive Directories (always trigger PR_REVIEWER)

- `architecture/`
- `core/`
- `auth/`
- `billing/`
- `security/`

### Decision Logic

```
if lines_changed > 200:
    agent = PR_REVIEWER
elif any(sensitive_dir in changed_file for file in files):
    agent = PR_REVIEWER
elif any(migration_pattern in file for file in files):
    agent = PR_REVIEWER
elif count(files with change_ratio > 50%) > 3:
    agent = PR_REVIEWER
elif file_count > 3:
    agent = PR_REVIEWER
else:
    agent = PR_REVIEWER_FAST
```

---

## 3. Provider Selection: ChatGPT vs Gemini vs Groq vs Kimi

### Task Type Affinity Matrix

| Task Type | ChatGPT | Gemini | Groq | Kimi |
|-----------|---------|--------|------|------|
| Code review / second opinion | Primary | Secondary | Fallback | — |
| Cross-validation of logic | Primary | — | Primary | — |
| Research / documentation analysis | Secondary | Primary | — | Secondary |
| Large-context analysis (>100K tokens) | — | Secondary | — | Primary |
| Ultra-long context (>500K tokens) | — | — | — | Primary |
| Bilingual Chinese/English | — | — | — | Primary |
| Ultra-fast validation (<2s response) | — | — | Primary | — |
| Google ecosystem tasks | — | Primary | — | — |
| Alternative implementation comparison | Primary | Secondary | Secondary | — |

### Context Length Guide

| Provider | Max Context | Best For |
|----------|-------------|----------|
| ChatGPT (GPT-4o) | 128K tokens | Code, logic, reasoning |
| ChatGPT (o1/o3-mini) | 128K tokens | Complex reasoning chains |
| Gemini 1.5 Pro | 1M tokens | Large codebase analysis |
| Groq (Llama 3.3 70B) | 8K–32K tokens | Speed-critical validation |
| Groq (Mixtral) | 32K tokens | Speed-critical, moderate context |
| Kimi (Moonshot AI) | 2M tokens | Entire-repo analysis, bilingual |

### Speed Requirements

| Priority | Provider | Typical Latency |
|----------|----------|-----------------|
| Fastest | Groq (LPU) | < 1 second |
| Fast | ChatGPT (o3-mini) | 2–5 seconds |
| Standard | Gemini 1.5 | 3–8 seconds |
| Standard | ChatGPT (GPT-4o) | 3–10 seconds |
| Variable | Kimi | 5–15 seconds |

### Selection Decision Logic

```
if context_tokens > 500_000:
    provider = KIMI
elif context_tokens > 100_000:
    provider = GEMINI  # or KIMI as fallback
elif is_bilingual_chinese_english:
    provider = KIMI
elif speed_required and context_tokens < 32_000:
    provider = GROQ
elif task_type in ["research", "google_ecosystem", "large_doc"]:
    provider = GEMINI
else:
    provider = CHATGPT  # default for code review / second opinions
```

---

## 4. Opus Escalation

Opus escalation is implemented in `agents/model_routing.py` (AI-254). The
following conditions trigger escalation from Sonnet to Opus:

### PR Reviewer — Opus Triggers

- Diff size > 500 lines changed
- Any changed file under: `architecture/`, `core/`, `auth/`, `billing/`, `security/`
- Any file path matching migration patterns: `migration`, `schema`, `alembic`, `flyway`
- More than 3 files with > 50% change ratio
- Manual override label: `review:opus`

### Coding Agent — Opus Triggers

- Task description contains: `refactor`, `architecture`, `redesign`, `migration`
- Complexity score > 8 (from `estimate_complexity()` in `agents/model_routing.py`)
- Cross-cutting changes affecting >= 5 modules

### Other Agents

All other agents default to Sonnet unless the complexity score from
`estimate_complexity()` exceeds the threshold of 8, in which case Opus is used.

See `agents/model_routing.py` for the full implementation.

---

## 5. Fallback Logic

When the preferred agent or model is unavailable, the following fallback chain
applies:

| Preferred Agent | Fallback 1 | Fallback 2 | Reason |
|-----------------|------------|------------|--------|
| `coding` | `coding_fast` | — | Degrade gracefully for timeout/overload |
| `pr_reviewer` | `pr_reviewer_fast` | — | Degrade gracefully for timeout/overload |
| `kimi` | `gemini` | `chatgpt` | Long-context fallback chain |
| `gemini` | `chatgpt` | `kimi` | Google API unavailable |
| `groq` | `chatgpt` | — | Groq LPU unavailable |
| `chatgpt` | `gemini` | `groq` | OpenAI API unavailable |

### Fallback Conditions

1. **Agent unavailable**: API key not set or provider returns 5xx error
2. **Rate limit exceeded**: Provider returns 429; retry with fallback after 2s
3. **Context too long**: Requested context exceeds provider limit; escalate to longer-context provider
4. **Cost cap reached**: Current session cost >= cap; downgrade to cheaper tier

### Fallback Decision Logic

```python
def select_agent_with_fallback(preferred_agent, task_metadata):
    if is_available(preferred_agent):
        return preferred_agent
    for fallback in FALLBACK_CHAIN[preferred_agent]:
        if is_available(fallback):
            log_routing_decision(
                agent_selected=fallback,
                routing_reason=f"Fallback from {preferred_agent}: unavailable",
                alternatives_considered=[preferred_agent]
            )
            return fallback
    raise AgentUnavailableError(f"No available agent for task")
```

---

## 6. Routing Metadata

Every agent assignment emits a `RoutingDecision` record (see
`agents/routing_metadata.py`):

```python
@dataclass
class RoutingDecision:
    session_id: str
    agent_selected: str          # e.g. "coding", "pr_reviewer_fast"
    routing_reason: str          # Human-readable explanation
    alternatives_considered: list[str]  # Other agents evaluated
    complexity_score: int        # 1–10 from estimate_complexity()
    model_tier: str              # "haiku" | "sonnet" | "opus"
    timestamp: str               # ISO 8601 UTC
```

Routing decisions are:

- Logged to structured session logs via `log_routing_decision()`
- Retrievable per session via `get_routing_history(session_id)`
- Exposed via REST API at `GET /api/sessions/{session_id}/routing`
- Visible in Agent Dashboard > Session Detail view

---

## 7. Complexity Score Reference

The `estimate_complexity()` function in `agents/model_routing.py` computes a
score from 1–10 using:

| Factor | Points |
|--------|--------|
| Keywords: `refactor`, `architecture`, `redesign`, `migration` | +3 each |
| Keywords: `security`, `auth`, `billing`, `database`, `schema` | +2 each |
| Keywords: `core`, `integration`, `performance` | +1 each |
| Modules affected >= 5 | +3 |
| Modules affected >= 3 | +1 |
| Lines changed > 500 | +2 |
| Lines changed > 200 | +1 |
| Files changed > 10 | +1 |
| PM Agent complexity hint (blended as max) | override |

**Thresholds:**
- Score <= 4: SIMPLE — use `coding_fast` / `pr_reviewer_fast`
- Score 5–8: MODERATE — use `coding` / `pr_reviewer`
- Score > 8: COMPLEX — use `coding` / `pr_reviewer` with Opus model tier
