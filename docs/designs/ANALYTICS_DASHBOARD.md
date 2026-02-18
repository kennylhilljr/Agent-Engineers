# Analytics Dashboard — Design Spec

**Feature:** AI-241 Phase 2 Design Spec
**Status:** Design Spec (Not Implemented)
**Last Updated:** 2026-02-18
**Target Users:** Engineering leads and developers tracking agent productivity

---

## Overview

A dedicated analytics page within the Agent Dashboard that provides historical
performance metrics, trend analysis, and insights about agent productivity,
cost efficiency, code quality outcomes, and system reliability.

---

## Layout Description

### Page Layout

```
LEFT PANEL (sidebar — unchanged)
│
└── MAIN CONTENT
    ┌──────────────────────────────────────────────────────┐
    │  PAGE HEADER: Analytics                              │
    │  "Agent performance metrics and trend analysis"      │
    │  [Time: Last 7 days ▼] [Agents: All ▼] [Export CSV] │
    ├──────────────────────────────────────────────────────┤
    │                                                      │
    │  ROW 1: Key Performance Indicators (5 KPI cards)     │
    │  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐      │
    │  │Tasks │ │PRs   │ │ Cost │ │Tokens│ │Uptime│      │
    │  │  42  │ │  18  │ │$14.67│ │ 8.2M │ │ 99.2%│      │
    │  │+12%  │ │+5%   │ │ -3%  │ │+18%  │ │ =    │      │
    │  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘      │
    │                                                      │
    │  ROW 2: Task Completion Chart + Agent Velocity       │
    │  ┌────────────────────────┐ ┌──────────────────┐    │
    │  │ Tasks Completed / Day  │ │ Agent Velocity   │    │
    │  │ (7-day bar chart)      │ │ Tasks / hour     │    │
    │  │                        │ │ Coding: ████ 4.2 │    │
    │  │  ▓ ▓ ▓ ▓ ▓ ▓ ▓        │ │ PR Rev: ██   2.1 │    │
    │  │  M T W T F S S        │ │ Others: █    1.3 │    │
    │  └────────────────────────┘ └──────────────────┘    │
    │                                                      │
    │  ROW 3: Cost Efficiency + Quality Metrics            │
    │  ┌────────────────────────┐ ┌──────────────────┐    │
    │  │ Cost per Task Trend    │ │ Code Quality     │    │
    │  │ (line chart: $/task)   │ │ PR approval rate │    │
    │  │                        │ │ Test pass rate   │    │
    │  │  ╲    /─────           │ │ Rework rate      │    │
    │  │   ╲__/                 │ │                  │    │
    │  └────────────────────────┘ └──────────────────┘    │
    │                                                      │
    │  ROW 4: Agent Performance Table                      │
    │  ┌──────────────────────────────────────────────┐   │
    │  │ Agent | Tasks | PRs | Cost | Tokens | Score  │   │
    │  │ ──────────────────────────────────────────── │   │
    │  │ Coding  28    14   $8.20  4.2M    A+         │   │
    │  │ PR Rev  18    18   $3.12  1.8M    A           │   │
    │  │ Linear  42    —    $0.84  0.5M    B+          │   │
    │  └──────────────────────────────────────────────┘   │
    │                                                      │
    │  ROW 5: Insights Panel                               │
    │  ┌──────────────────────────────────────────────┐   │
    │  │ 💡 AI-Generated Insights                      │   │
    │  │  • Coding Agent cost decreased 12% vs last week │ │
    │  │  • PR approval rate at all-time high (94%)    │   │
    │  │  • Tuesday peak: 8 tasks completed in 2 hours │   │
    │  └──────────────────────────────────────────────┘   │
    └──────────────────────────────────────────────────────┘
```

---

## Component List

### KPI Cards (Row 1)

| Card | Metric | Trend | Color Logic |
|------|--------|-------|-------------|
| Tasks Completed | `42` | `+12% vs prev period` | Green if positive |
| PRs Merged | `18` | `+5% vs prev period` | Green if positive |
| Total Cost | `$14.67` | `-3% vs prev period` | Green if cost down |
| Tokens Used | `8.2M` | `+18% vs prev period` | Neutral (informational) |
| System Uptime | `99.2%` | `= vs prev period` | Red if <95% |

**Card design:**
- Large metric (1.6rem, bold)
- Trend badge: arrow icon + percentage + color (green/red)
- Time period shown in card footer
- Hover: show absolute vs. relative toggle

### Task Completion Chart (Row 2, left)

```
  Tasks Completed per Day — Last 7 Days

  8 │        ▓
  6 │     ▓  ▓  ▓
  4 │  ▓  ▓  ▓  ▓  ▓  ▓
  2 │  ▓  ▓  ▓  ▓  ▓  ▓  ▓
  0 └─────────────────────
     Mon Tue Wed Thu Fri Sat Sun
```

- Bar chart (SVG or Canvas)
- Color: `--accent` (blue)
- Tooltip: date, count, agent breakdown
- Click bar: filter table to that day

### Agent Velocity Chart (Row 2, right)

Horizontal bar chart showing tasks-per-hour per agent:

```
  Agent Velocity (tasks/hour)

  Coding Agent  ████████████ 4.2
  PR Reviewer   ██████       2.1
  Linear Agent  ████         1.3
  GitHub Agent  ███          0.9
  Slack Agent   █            0.3
```

- Color per agent (consistent with status dots)
- Hover shows raw data: X tasks over Y hours

### Cost per Task Trend (Row 3, left)

```
  Average Cost per Task — Last 30 Days

  $0.60 │ ●
        │  ●─●
  $0.40 │     ●─●─●
        │         ●─●─●
  $0.20 │             ●─────●
        └─────────────────────
        1  5  10  15  20  25 30
```

- Line chart showing $/task over time
- Decreasing slope = good (agent getting more efficient)
- Reference line for team average or target

### Code Quality Metrics (Row 3, right)

Donut or gauge charts for:

```
  PR Approval Rate      Test Pass Rate     Rework Rate
       ┌──────┐              ┌──────┐          ┌──────┐
      ╱  94%  ╲            ╱  87%  ╲         ╱  8%   ╲
     │   A+    │          │   B+    │        │   Good  │
      ╲        ╱           ╲        ╱          ╲       ╱
       └──────┘              └──────┘           └──────┘
  (94% of PRs approved)  (87% tests pass)  (8% need rework)
```

Grading scale:
- A+: >90% | A: 80–90% | B: 70–80% | C: 60–70% | F: <60%

### Agent Performance Table (Row 4)

| Column | Description |
|--------|-------------|
| Agent | Name + status dot (current state) |
| Tasks | Completed task count in period |
| PRs | PRs opened + merged |
| Cost | Total API cost for period |
| Tokens In/Out | Token consumption |
| Efficiency | Cost per task (derived metric) |
| Score | Composite performance grade (A–F) |

**Table features:**
- Sortable by all columns
- Row click: expand to show daily breakdown
- Highlight row for agent currently running
- Color-coded Score column (green/yellow/red)

### Insights Panel (Row 5)

AI-generated text insights based on the metrics data:

```
  💡 Performance Insights — Last 7 Days

  Positive Trends:
  ● Coding Agent efficiency improved 12% (lower cost per task)
  ● PR approval rate reached all-time high at 94%
  ● Zero agent errors recorded this week

  Watch Points:
  ⚠ Token usage up 18% — review prompt complexity
  ⚠ Linear Agent has 3 unprocessed tickets >24h old

  Peak Performance:
  ★ Tuesday 14:00–16:00: 8 tasks completed (highest 2-hour burst)
  ★ Coding Agent: best week yet (28 tasks, $8.20 total)
```

- Insights generated by summarizing the metrics data client-side
- Grouped into Positive, Watch, and Peak sections
- Each insight is a single actionable sentence
- Refresh automatically when time period changes

---

## Filter Bar

```
┌──────────────────────────────────────────────────────┐
│  [Last 7 days ▼] [All Agents ▼] [All Models ▼]       │
│                                            [Export ▼] │
└──────────────────────────────────────────────────────┘
```

**Time period options:**
- Today / Yesterday
- Last 7 days (default)
- Last 30 days
- Last 90 days
- Custom date range (date picker)

**Agent filter:** All / specific agent (multi-select)

**Model filter:** All / haiku / sonnet / opus

**Export options:** CSV, JSON

---

## User Flow

```
[Left Panel → "Analytics" nav item]
         ↓
[Analytics page loads with 7-day default view]
         ↓
         ├── [Change time period] → all charts update with animation
         ├── [Filter by agent] → charts filter to selected agents
         ├── [Click bar in Task chart] → filter table to that day
         ├── [Click table column] → sort by that column
         ├── [Expand table row] → show daily breakdown for agent
         ├── [Hover chart] → tooltip with detail data
         └── [Export CSV] → download filtered data
```

---

## Key Interactions

| Interaction | Behavior |
|-------------|----------|
| Time period change | All charts and KPIs update simultaneously with 300ms transition |
| Agent filter | Charts and table filter immediately (no page reload) |
| Chart bar click | Highlights corresponding rows in performance table |
| Table row expand | Slide-open daily breakdown with sparkline mini-charts |
| KPI card click | Jump to related detailed chart |
| Trend percentage hover | Show absolute values: "42 vs 38 last period" |
| Export button | Dropdown: CSV / JSON, respects current filters |
| Insight item click | Scroll to the related chart |

---

## Mobile Layout (max-width: 768px)

On mobile, the multi-column layout collapses to single column:

```
[KPI Cards — horizontal scroll]
[Task Completion Chart — full width]
[Agent Velocity — full width]
[Performance Table — simplified 4 columns]
[Insights — full width]
```

Charts become touch-interactive (tap for tooltip instead of hover).

---

## Design Tokens Used

- `--bg-secondary` — page and card backgrounds
- `--text-primary` — metric values, headings
- `--text-secondary` — axis labels, helper text
- `--border-color` — card borders, table dividers
- `--accent` — chart primary color, active filters
- Status tokens:
  - `--status-running: #22c55e` — positive trends, high scores
  - `--status-paused: #eab308` — watch points, medium scores
  - `--status-error: #ef4444` — negative trends, low scores

---

## Accessibility Requirements

- Charts have `<title>` and `<desc>` elements for screen readers
- Table data cells have headers linked via `headers` attribute
- KPI trend indicators use text ("up 12%") not just icons
- Time period selector keyboard accessible
- All interactive chart elements focusable with keyboard
- Animations respect `prefers-reduced-motion` media query
- High contrast mode tested (sufficient contrast ratios)
- Export button has descriptive `aria-label` including format
