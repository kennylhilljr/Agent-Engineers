# Billing & Subscription Page — Design Spec

**Feature:** AI-241 Phase 2 Design Spec
**Status:** Design Spec (Not Implemented)
**Last Updated:** 2026-02-18
**Target Users:** Developers and team leads managing API costs

---

## Overview

A billing and usage dashboard page within the Agent Dashboard that shows real-time
API cost tracking, per-agent spend breakdown, monthly usage summaries, and projected
costs. This page surfaces data already partially tracked by the metrics system.

---

## Layout Description

### Page Layout (within existing left-panel + main-content structure)

```
LEFT PANEL (sidebar — unchanged)
│
└── MAIN CONTENT
    ┌──────────────────────────────────────────────────────┐
    │  PAGE HEADER: Billing & Usage                        │
    │  "API cost tracking and subscription management"     │
    ├──────────────────────────────────────────────────────┤
    │                                                      │
    │  ROW 1: Summary Cards (4 cards, equal width)         │
    │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐        │
    │  │ Today  │ │  Week  │ │ Month  │ │ Budget │        │
    │  │ $0.42  │ │ $2.18  │ │ $14.67 │ │ 73%    │        │
    │  └────────┘ └────────┘ └────────┘ └────────┘        │
    │                                                      │
    │  ROW 2: Cost Chart + Per-Agent Breakdown             │
    │  ┌──────────────────────┐ ┌────────────────────┐    │
    │  │  Daily Cost Chart    │ │  Agent Breakdown    │    │
    │  │  (30-day bar/line)   │ │  Coding    45%      │    │
    │  │                      │ │  PR Review 22%      │    │
    │  │                      │ │  Linear    18%      │    │
    │  │                      │ │  Other     15%      │    │
    │  └──────────────────────┘ └────────────────────┘    │
    │                                                      │
    │  ROW 3: Token Usage Table                            │
    │  ┌──────────────────────────────────────────────┐   │
    │  │  Agent | Model | Tokens In | Tokens Out | $  │   │
    │  │  ─────────────────────────────────────────── │   │
    │  │  Coding  sonnet  1.2M      0.4M        $3.20 │   │
    │  │  PR Rev  sonnet  0.8M      0.2M        $2.10 │   │
    │  │  Linear  haiku   0.3M      0.1M        $0.22 │   │
    │  └──────────────────────────────────────────────┘   │
    │                                                      │
    │  ROW 4: Budget Settings + Alerts                     │
    │  ┌──────────────────────┐ ┌────────────────────┐    │
    │  │  Monthly Budget      │ │  Alert History      │    │
    │  │  $20.00 limit        │ │  Feb 15: 75% used   │    │
    │  │  [██████░░░░] 73%    │ │  Feb 10: 50% used   │    │
    │  │  [Edit Budget]       │ │                     │    │
    │  └──────────────────────┘ └────────────────────┘    │
    │                                                      │
    └──────────────────────────────────────────────────────┘
```

---

## Component List

### Summary Cards (Row 1)

| Card | Metric | Sub-label | Color accent |
|------|--------|-----------|-------------|
| Today's Cost | `$0.42` | "+$0.12 vs yesterday" | Neutral |
| This Week | `$2.18` | "7-day rolling total" | Neutral |
| This Month | `$14.67` | "of $20.00 budget" | Warning if >75% |
| Budget Used | `73%` | "5.3 days remaining" | Red if >90% |

**Card design:**
- Same `.card` class as existing cards
- Large metric number (1.5rem, `--text-primary`)
- Sub-label below in `--text-secondary`
- Color accent for warning states (amber >75%, red >90%)

### Daily Cost Chart (Row 2, left)

**Chart type:** Bar chart (prefer) or line chart

```
$2.00 │                        ▓
      │                    ▓   ▓
$1.00 │          ▓   ▓   ▓ ▓   ▓
      │   ▓   ▓  ▓   ▓   ▓ ▓   ▓
$0.00 └────────────────────────────
      1  5  10  15  20  25  28
      ← Last 30 days →
```

- X-axis: last 30 days (day numbers)
- Y-axis: dollar amount
- Hover tooltip: date, total cost, breakdown by model
- Bar color: `--accent` (blue) for normal, amber if budget warning
- Implemented as Canvas API or SVG (no external chart library to maintain single-file)

### Agent Breakdown (Row 2, right)

```
  Agent Cost Breakdown — This Month
  ┌──────────────────────────────────┐
  │  Coding Agent       ████ 45% $6.60  │
  │  PR Reviewer        ██   22% $3.22  │
  │  Linear Agent       █    18% $2.64  │
  │  GitHub Agent       █    10% $1.47  │
  │  Others             ░     5% $0.74  │
  └──────────────────────────────────┘
  Total: $14.67
```

- Horizontal bar chart per agent
- Color-coded by agent type
- Percentage + absolute dollar value
- Clicking an agent row opens the agent's detail panel

### Token Usage Table (Row 3)

| Column | Description |
|--------|-------------|
| Agent | Agent name with status dot |
| Model | Model tier (haiku/sonnet/opus) + cost tier badge |
| Tokens In | Input token count (formatted: 1.2M) |
| Tokens Out | Output token count |
| Cache Hits | Prompt cache reads (reduces cost) |
| Cost | Dollar amount with micro-formatting ($0.042) |

**Table features:**
- Row sorting by any column (click header)
- Expandable rows showing per-session breakdown
- Color coding: green (within budget), amber (>50%), red (>90%)
- Time period selector: Today / Week / Month / Custom

### Budget Settings (Row 4, left)

```
  ┌────────────────────────────────┐
  │  Monthly Budget                │
  │                                │
  │  Current limit: $20.00         │
  │  Spent: $14.67 (73%)           │
  │                                │
  │  [████████████░░░░░░░] 73%     │
  │                                │
  │  Alert at: [75%▼] [90%▼]       │
  │                                │
  │  [ ] Pause agents at 100%      │
  │  [ ] Email alerts              │
  │                                │
  │  [Save Settings]               │
  └────────────────────────────────┘
```

**Budget controls:**
- Editable budget limit (click to edit, press Enter to save)
- Alert threshold dropdowns (multiples of 25%)
- "Pause all agents at budget limit" toggle
- "Send Slack notification at threshold" toggle

### Alert History (Row 4, right)

```
  ┌────────────────────────────────┐
  │  Budget Alerts                 │
  │                                │
  │  Feb 15, 14:22  ⚠ 75% reached │
  │  Feb 10, 09:41  ⚠ 50% reached │
  │  Feb 01, 00:00  ✓ Month reset  │
  │  Jan 28, 16:05  🔴 98% reached │
  │                                │
  │  [View All Alerts →]           │
  └────────────────────────────────┘
```

---

## User Flow

```
[Left Panel → "Billing" nav item]
         ↓
[Billing page loads with current month data]
         ↓
         ├── [Change time period] → data refreshes
         ├── [Click agent in chart] → agent detail panel opens
         ├── [Click table column header] → sort table
         ├── [Expand table row] → session-level breakdown
         ├── [Click "Edit Budget"] → inline edit of budget limit
         └── [Toggle alert settings] → save immediately
```

---

## Key Interactions

| Interaction | Behavior |
|-------------|----------|
| Time period switch | Re-fetch data for selected period, animate chart update |
| Bar chart hover | Show tooltip with date, cost, agent breakdown |
| Agent row click (chart) | Scroll to table and highlight agent rows |
| Table column sort | Sort ascending → descending → none (3-state) |
| Table row expand | Slide-open session list below the row |
| Edit budget | Inline text input appears, confirm on Enter or blur |
| Budget threshold dropdown | Save on selection change (no separate save button) |
| Pause agents toggle | Requires confirmation dialog before enabling |
| Export CSV button | Download current period data as CSV file |

---

## Design Tokens Used

- `--bg-secondary` — page background, card backgrounds
- `--text-primary` — metrics, headings
- `--text-secondary` — labels, sub-text
- `--border-color` — card borders, table row dividers
- `--accent` — chart bars, active filters, sort arrows
- Status tokens (to be added):
  - `--status-running: #22c55e` — under budget
  - `--status-paused: #eab308` — approaching limit
  - `--status-error: #ef4444` — over limit / budget exceeded

---

## Accessibility Requirements

- Table has proper `<thead>`, `<tbody>`, column scope attributes
- Sort buttons have `aria-sort` attribute (ascending/descending/none)
- Chart has `<title>` and `<desc>` elements for screen readers
- Alert thresholds announced via `aria-live` when changed
- Budget progress bar uses `role="progressbar"` with `aria-valuenow`
- Color is never the only indicator (icons + text labels supplement)
- All interactive elements reachable by keyboard
