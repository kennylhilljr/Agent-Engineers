# A2UI Components Integration Plan

**Version:** 1.0.0
**Issue:** AI-241 — Designer Agent: Figma Design System Integration
**Last Updated:** 2026-02-18
**Status:** Planning (Not yet implemented)

---

## Table of Contents

1. [Overview](#overview)
2. [A2UI Component Inventory](#a2ui-component-inventory)
3. [Compatibility Assessment](#compatibility-assessment)
4. [Dashboard Component Mapping](#dashboard-component-mapping)
5. [The Single-File Constraint](#the-single-file-constraint)
6. [Migration Strategy](#migration-strategy)
7. [Phase Plan](#phase-plan)
8. [Effort Estimates](#effort-estimates)
9. [Risk Assessment](#risk-assessment)
10. [Decision Recommendation](#decision-recommendation)

---

## Overview

This document evaluates the feasibility of integrating the `a2ui-components` library
(located at `/reusable/a2ui-components/`) into the Agent Dashboard's single-file
HTML application (`dashboard/dashboard.html`).

### Key Constraint

**The dashboard must remain a single HTML file.** This is a hard architectural
constraint. The file is served directly by the Python server and includes all HTML,
CSS, and JavaScript inline. No build step, no bundler, no external assets.

This constraint fundamentally shapes how (and whether) a2ui-components can be integrated.

---

## A2UI Component Inventory

The a2ui-components library (`/reusable/a2ui-components/`) contains:

### Component Catalog (9 components)

| Component | Type String | File | Description |
|-----------|-------------|------|-------------|
| TaskCard | `a2ui.TaskCard` | `components/task-card.tsx` | Task with status, category, progress bar |
| ProgressRing | `a2ui.ProgressRing` | `components/progress-ring.tsx` | Circular progress indicator |
| FileTree | `a2ui.FileTree` | `components/file-tree.tsx` | Hierarchical file browser |
| TestResults | `a2ui.TestResults` | `components/test-results.tsx` | Test suite results display |
| ActivityItem | `a2ui.ActivityItem` | `components/activity-item.tsx` | Activity feed entry |
| ApprovalCard | `a2ui.ApprovalCard` | `components/approval-card.tsx` | Human-in-the-loop approval UI |
| DecisionCard | `a2ui.DecisionCard` | `components/decision-card.tsx` | Multi-option decision prompt |
| MilestoneCard | `a2ui.MilestoneCard` | `components/milestone-card.tsx` | Sprint/milestone completion display |
| ErrorCard | `a2ui.ErrorCard` | `components/error-card.tsx` | Error display with stack trace |

### Library Infrastructure

| File | Purpose |
|------|---------|
| `lib/a2ui-types.ts` | TypeScript type definitions, data interfaces |
| `lib/a2ui-catalog.ts` | Component registry and lookup functions |
| `lib/a2ui-orchestrator.ts` | Agent-to-component orchestration |
| `lib/animations.ts` | Animation utilities |

### Technology Stack

- **Framework:** React 18 (TSX/JSX)
- **Styling:** Tailwind CSS utility classes (e.g., `bg-gray-900`, `text-blue-400`)
- **UI Primitives:** shadcn/ui (`Card`, `Badge`, `Progress`)
- **Icons:** Lucide React
- **Language:** TypeScript (.tsx files)
- **Build:** Requires Node.js bundler (Next.js/Vite assumed from import paths)

---

## Compatibility Assessment

### Fundamental Incompatibilities

| Issue | Severity | Detail |
|-------|----------|--------|
| React required | Blocking | a2ui components are React components. The dashboard uses vanilla JS. |
| Tailwind CSS required | Blocking | Components use Tailwind utility classes. No Tailwind in the dashboard. |
| TypeScript | Blocking | `.tsx` files cannot be used directly in a browser without transpilation. |
| shadcn/ui dependency | Blocking | Components import `@/components/ui/card`, `badge`, `progress` — requires a build step. |
| Lucide React icons | Blocking | Icon imports require React and bundler. |
| Module import paths | Blocking | `@/` alias paths require bundler configuration. |
| Build step required | Critical | Current dashboard has zero build step — it's served as a raw HTML file. |

### What Would Be Required to Integrate

To use a2ui-components in dashboard.html, ALL of the following would be needed:

1. **Add React** (via CDN or bundle) — ~130kb minified
2. **Add Tailwind CSS** (via CDN `<script>`) — renders Tailwind at runtime; functional but non-standard
3. **Transpile TypeScript** — impossible without a build step
4. **Bundle shadcn/ui + Lucide** — requires npm/bundler
5. **Break the single-file constraint** — OR use a build step that outputs a single HTML file

### Single-File Compatibility Verdict

**Not directly compatible.** The a2ui-components library requires a React+TypeScript+Tailwind build pipeline. This is fundamentally incompatible with the current single-file, no-build-step architecture.

---

## Dashboard Component Mapping

Even though direct integration is not feasible, the following table maps existing
dashboard components to their a2ui equivalents for reference during a future migration.

| Dashboard Pattern | A2UI Equivalent | Functional Match | Notes |
|-------------------|-----------------|------------------|-------|
| Agent status item (running) | `a2ui.TaskCard` | Partial | Task card shows title, status, progress — maps to running agent display |
| Progress indicators | `a2ui.ProgressRing` | Good | Dashboard has linear progress; a2ui has circular |
| Test result display | `a2ui.TestResults` | Excellent | Near 1:1 match for test output display |
| Activity feed | `a2ui.ActivityItem` | Good | Activity events with actor, action, timestamp |
| Human approval prompts | `a2ui.ApprovalCard` | Excellent | Human-in-the-loop approval flow |
| Decision prompts | `a2ui.DecisionCard` | Excellent | Multi-option decision UI |
| Sprint completion | `a2ui.MilestoneCard` | Good | Sprint/milestone celebration |
| Error display | `a2ui.ErrorCard` | Good | Error messages with stack trace |
| File diff view | `a2ui.FileTree` | Partial | File browser vs. diff viewer |

### Unmapped Dashboard Components (No A2UI Equivalent)

These existing dashboard patterns have no a2ui equivalent and would need to be
created or remain as-is:

- Left panel sidebar navigation
- Agent status dot with pulse animation
- Theme toggle (dark/light)
- Chat interface
- Pipeline visualization
- Metrics cards (token count, cost, duration)
- Achievement/XP display
- Project timeline

---

## The Single-File Constraint

### Why the Constraint Exists

The single-file architecture of `dashboard/dashboard.html` provides:

1. **Zero dependencies** — No npm install, no build step, no CDN required
2. **Easy distribution** — Drop the file anywhere and it works
3. **Server simplicity** — Python HTTP server serves one file
4. **Reliability** — No external dependencies that can fail
5. **Portability** — Works offline, in containers, behind firewalls

### Approaches That Preserve the Single-File Constraint

#### Option A: Inline Transpiled Output

Build a2ui-components using a bundler configured to produce a self-contained
JavaScript bundle, then inline the bundle into dashboard.html. This preserves
the single-file requirement but adds a build step.

- **Pros:** Clean components, type safety, all a2ui features
- **Cons:** Requires build pipeline, dramatically increases file size, React adds ~130kb

#### Option B: Vanilla JS Reimplementation

Rewrite the a2ui component patterns in vanilla JavaScript (no React, no TypeScript)
and inline them in dashboard.html. This is what the dashboard already effectively does.

- **Pros:** No build step, maintains single-file, no size penalty
- **Cons:** Duplicates effort, loses type safety, components diverge from canonical a2ui

#### Option C: Web Components Wrapper

Convert a2ui components to Web Components (Custom Elements) which can be used
without React. Build them with Lit or StencilJS and inline the output.

- **Pros:** Framework-agnostic, reusable, standard browser APIs
- **Cons:** Requires a2ui to be rewritten/wrapped, complex build pipeline

#### Option D: Separate Chat UI (Recommended Path)

The primary use of a2ui-components in this project is in the chat interface
(AI responses rendering structured UI). This already happens in a separate
context. Keep a2ui for the React-based chat components and maintain the
dashboard.html as vanilla JS.

- **Pros:** Right tool for each job, no architectural compromise
- **Cons:** Parallel maintenance of two UI systems

---

## Migration Strategy

Given the constraints, the recommended migration strategy is a **phased parallel
approach** that does not force a single-file architecture change.

### Strategy: "Bridge Pattern"

Maintain two distinct UI systems that coexist:

1. **dashboard.html** — Vanilla JS + CSS, no build step, single file
   - Handles: Agent monitoring, real-time status, sidebar navigation, theme toggle
   - Does NOT use a2ui-components directly

2. **React Chat UI** (separate, optional extension point)
   - Handles: Chat interface, structured AI responses, a2ui-components rendering
   - Uses the full a2ui catalog for generative UI components

The dashboard.html can reference a2ui **design patterns** (layout, spacing, colors)
without importing the React components.

---

## Phase Plan

### Phase 0: Design Token Alignment (Now — No Code Changes)

**Goal:** Align dashboard.html's CSS custom properties with a2ui's Tailwind colors.

- Extract all hardcoded colors from dashboard.html (done — see `design_tokens.json`)
- Map dashboard colors to Tailwind equivalents (e.g., `#22c55e` → `green-500`)
- Document alignment in `docs/DESIGN_SYSTEM.md`
- **Effort:** 1–2 days | **Risk:** None (documentation only)

### Phase 1: Token Enrichment (1–2 sprints)

**Goal:** Replace hardcoded colors in dashboard.html with CSS variables.

- Add status color CSS variables to `:root`:
  ```css
  --status-running: #22c55e;
  --status-paused: #eab308;
  --status-error: #ef4444;
  --status-idle: #475569;
  --status-running-bg: rgba(34, 197, 94, 0.1);
  --status-paused-bg: rgba(234, 179, 8, 0.1);
  --status-error-bg: rgba(239, 68, 68, 0.1);
  ```
- Add spacing, radius, shadow, and motion tokens
- Update `design_tokens.json` to reflect new state
- **Effort:** 4–8 hours | **Risk:** Low (CSS changes only)

### Phase 2: Vanilla JS Component Library (2–4 sprints)

**Goal:** Create a vanilla JS equivalent of the a2ui component patterns for dashboard.html.

- Create `dashboard/components.js` (or inline in dashboard.html):
  - `DashboardTaskCard` — mirrors `a2ui.TaskCard` data structure
  - `DashboardProgressRing` — SVG-based circular progress
  - `DashboardErrorCard` — error display matching a2ui pattern
  - `DashboardApprovalCard` — approval prompt matching a2ui pattern
- Use shared JSON schema from `lib/a2ui-types.ts` to ensure data compatibility
- **Effort:** 2–3 weeks | **Risk:** Medium (new code, needs testing)

### Phase 3: Build Pipeline (Future — Optional)

**Goal:** Add optional build step that outputs a single-file dashboard.

Only pursue this phase if React integration is strongly desired.

- Configure a bundler (Vite or Webpack) to:
  1. Compile TSX components
  2. Bundle React, shadcn/ui, Lucide
  3. Inline everything into a single HTML file output
- Output: `dist/dashboard.html` — still single file, but built
- **Effort:** 1–2 weeks | **Risk:** High (changes deployment process)

### Phase 4: Full Migration (Long-term)

**Goal:** Replace dashboard.html with a proper React app using a2ui-components.

- Break the single-file constraint intentionally
- Build with Next.js or Vite + React
- Use a2ui-components catalog throughout
- **Effort:** 4–8 weeks | **Risk:** High (architectural change, deployment change)

---

## Effort Estimates

| Phase | Description | Effort | Risk | Recommended |
|-------|-------------|--------|------|-------------|
| Phase 0 | Design token alignment (docs) | 1–2 days | None | Yes, now |
| Phase 1 | Token enrichment (CSS vars) | 4–8 hours | Low | Yes, next sprint |
| Phase 2 | Vanilla JS component library | 2–3 weeks | Medium | Yes, Q2 |
| Phase 3 | Build pipeline (single-file output) | 1–2 weeks | High | Optional |
| Phase 4 | Full React migration | 4–8 weeks | High | Future |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Build pipeline breaks single-file serving | High | Critical | Phase 3 is optional; maintain fallback |
| React bundle size too large for inline | Medium | High | Tree-shake; consider Preact (~3kb) |
| Component API divergence | Medium | Medium | Use `a2ui-types.ts` as shared schema spec |
| Design drift (dashboard vs. a2ui) | High | Low | Design token alignment in Phase 0/1 |
| Maintenance overhead (two UI systems) | High | Medium | Phase 2 vanilla JS components reduce drift |

---

## Decision Recommendation

**Short term (now):** Do NOT attempt to import a2ui-components into dashboard.html.
The technical incompatibility (React + TypeScript + Tailwind) makes this infeasible
without a build step.

**Do instead:**
1. Complete Phase 0 (token alignment documentation — done)
2. Complete Phase 1 (add CSS variable tokens to dashboard.html — quick win)
3. Evaluate Phase 3 (build pipeline) when/if the single-file constraint is reconsidered

**Design System Reference:** The `docs/DESIGN_SYSTEM.md` and `design_tokens.json`
serve as the source of truth for both the vanilla dashboard and any future React
migration, ensuring design consistency regardless of which path is chosen.
