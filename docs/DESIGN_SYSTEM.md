# Agent Dashboard Design System

**Version:** 1.0.0
**Last Updated:** 2026-02-18
**Source:** Extracted from `dashboard/dashboard.html` (10,431 lines, 906 unique CSS classes)

---

## Table of Contents

1. [Overview](#overview)
2. [Design Tokens](#design-tokens)
3. [Color Palette](#color-palette)
4. [Typography](#typography)
5. [Spacing System](#spacing-system)
6. [Border & Radius](#border--radius)
7. [Shadow System](#shadow-system)
8. [Animation & Motion](#animation--motion)
9. [Component Inventory](#component-inventory)
10. [Layout System](#layout-system)
11. [Design Audit Findings](#design-audit-findings)

---

## Overview

The Agent Dashboard is a single-file HTML application (`dashboard/dashboard.html`) that provides real-time visibility into the agent orchestration system. The current design uses GitHub-inspired dark/light theming with a small set of CSS custom properties (CSS variables) for theming, augmented by a large number of hardcoded color values.

### Key Facts

- **CSS file size:** ~145,000 characters (single `<style>` block)
- **CSS classes:** 906 unique class names
- **CSS variables defined:** 11 in `:root`, 1 in `[data-theme="light"]`
- **Total CSS variable usages:** 175 references to 12 unique variables
- **Hardcoded color values:** 59 unique hex values not using CSS variables
- **Keyframe animations:** 7 (`pulse-green`, `pipeline-pulse`, `pulse`, `spin`, `fadeIn`, `bounce`, `reasoning-fade-in`)
- **Media queries:** 5 (breakpoints at 480px, 720px, 768px, 1100px)
- **Themes:** Dark (default) and Light (`[data-theme="light"]`)

---

## Design Tokens

All tokens are stored in `design_tokens.json` and extracted by `scripts/extract_design_tokens.py`.

### CSS Custom Properties (`:root`)

These are the **only** CSS variables currently defined. All other colors are hardcoded.

| Token | Dark Value | Light Value | Usage Count | Purpose |
|-------|-----------|-------------|-------------|---------|
| `--bg-primary` | `#0d1117` | `#ffffff` | 5 | Primary background (page-level) |
| `--bg-secondary` | `#161b22` | `#f6f8fa` | 6 | Secondary background (panels, sidebar) |
| `--text-primary` | `#e6edf3` | `#24292f` | 35 | Primary text content |
| `--text-secondary` | `#8b949e` | `#656d76` | 57 | Secondary/muted text, labels |
| `--border-color` | `#30363d` | `#d0d7de` | 41 | All borders and dividers |
| `--accent` | `#58a6ff` | `#0969da` | 19 | Interactive accent, links, active state |
| `--body-bg-start` | `#0f172a` | `#f0f4f8` | 2 | Gradient background start |
| `--body-bg-end` | `#1e293b` | `#dde8f0` | 2 | Gradient background end |
| `--card-bg` | `rgba(15,23,42,0.8)` | `rgba(255,255,255,0.9)` | 3 | Card component background |
| `--header-bg` | `rgba(15,23,42,0.5)` | `rgba(246,248,250,0.9)` | 1 | Sticky header background |
| `--transition-theme` | `background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease` | (same) | 1 | Theme transition shorthand |

> **Audit Finding:** `--panel-bg` is used 3 times in CSS via `var(--panel-bg, #161b22)` but is never defined in `:root` — it falls back to the hardcoded `#161b22` value.

---

## Color Palette

### Semantic Color System (Current State)

The dashboard uses GitHub's color palette as inspiration. Below are the semantically grouped hardcoded colors that should be migrated to CSS variables.

#### Background Colors

| Color | Hex | Usage Context |
|-------|-----|---------------|
| Page background (dark) | `#0d1117` | Body/page background (dark mode) |
| Surface background (dark) | `#161b22` | Cards, panels, sidebar |
| Subtle background (dark) | `#1e293b` | Gradient endpoint |
| Gradient start (dark) | `#0f172a` | Body gradient start |
| Page background (light) | `#ffffff` | Body/page background (light mode) |
| Surface background (light) | `#f6f8fa` | Cards, panels, sidebar |
| Subtle background (light) | `#f1f5f9` | Hover states, subtle areas |

#### Text Colors

| Color | Hex | Usage Context |
|-------|-----|---------------|
| Primary text (dark) | `#e6edf3` | Main content text |
| Secondary text (dark) | `#8b949e` | Labels, metadata, muted text |
| Muted text | `#94a3b8` | Dimmed/disabled content |
| Placeholder text | `#c9d1d9` | Input placeholders |
| Primary text (light) | `#24292f` | Main content text (light mode) |
| Secondary text (light) | `#656d76` | Labels/muted text (light mode) |
| Muted (light) | `#475569` | Additional muted text |

#### Border Colors

| Color | Hex | Usage Context |
|-------|-----|---------------|
| Border (dark) | `#30363d` | Card/panel borders |
| Border subtle | `#21262d` | Subtle separators |
| Border (light) | `#d0d7de` | Card/panel borders (light mode) |
| Border subtle (light) | `#e1e4e8` | Subtle separators (light mode) |
| Separator (light) | `#e2e8f0` | Dividers |

#### Accent / Interactive Colors

| Color | Hex | Usage Context |
|-------|-----|---------------|
| Accent blue (dark) | `#58a6ff` | Links, active nav, focus indicators |
| Accent blue (light) | `#0969da` | Links, active nav (light mode) |
| Blue hover | `#60a5fa` | Toggle buttons, link hovers |
| Blue light | `#93c5fd` | Hover state for desc toggles |
| Blue muted | `#3b82f6` | Less prominent interactive elements |
| Blue dark | `#2563eb` | Pressed states |
| Blue darkest | `#1d4ed8` | High-contrast interactive |
| Indigo | `#6366f1` | Tag/badge accents |
| Violet | `#818cf8` | Secondary accent elements |
| Purple | `#a855f7` | Badges, tags |
| Purple light | `#c084fc` | Light badge variants |
| Lavender | `#a78bfa` | Achievement/XP elements |

#### Status Colors

| Semantic | Color | Hex | Dark BG Tint | Usage |
|----------|-------|-----|-------------|-------|
| Success/Running | Green | `#22c55e` | `rgba(34,197,94,0.1)` | Running agents, success states |
| Success alt | Green | `#3fb950` | - | GitHub-style success |
| Success light | Mint | `#4ade80` | - | Success highlights |
| Success muted | Pale green | `#86efac` | - | Subtle success indicators |
| Success very light | | `#6ee7b7` | - | Background success tints |
| Merged/Deploy | Green | `#238636` | - | PR merged, deployment success |
| Warning/Paused | Amber | `#eab308` | `rgba(234,179,8,0.1)` | Paused agents, warnings |
| Warning alt | Yellow | `#fbbf24` | - | Cost indicators |
| Warning muted | | `#fcd34d` | - | Subtle warnings |
| Warning light | | `#f59e0b` | - | Alternative warning |
| Error/Stopped | Red | `#ef4444` | `rgba(239,68,68,0.1)` | Error states, stopped agents |
| Error alt | | `#f85149` | - | GitHub-style error |
| Error light | | `#fca5a5` | - | Error highlights |
| Error light | | `#f87171` | - | Subtle error |
| Info | Blue | `#60a5fa` | - | Informational elements |

#### Achievement/XP Colors (Gamification)

| Color | Hex | Usage |
|-------|-----|-------|
| Gold | `#ffd700` | Gold rank/achievements |
| Silver | `#c0c0c0` | Silver rank |
| Bronze | `#cd7f32` | Bronze rank |
| XP Purple | `#c4b5fd` | XP indicators |

#### Agent Status Dot Colors

| Status | Color | Hex |
|--------|-------|-----|
| Idle | Slate | `#475569` |
| Running | Green | `#22c55e` (animated pulse) |
| Paused | Amber | `#eab308` |
| Error | Red | `#ef4444` |

---

## Typography

The dashboard uses system fonts with a consistent hierarchy. No custom web fonts are loaded.

### Font Stack

```css
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
```

### Type Scale

| Role | Size | Weight | Usage |
|------|------|--------|-------|
| Body (base) | Browser default (~16px) | 400 | General content |
| Small/Label | `0.82rem` (~13px) | 400–500 | Nav items, metadata |
| XSmall | `0.75rem` (~12px) | 400 | Agent status items |
| XXSmall | `0.72rem` (~11.5px) | 500–700 | Running ticket labels |
| Tiny | `0.68rem` (~11px) | 400–700 | Section labels, metrics |
| Micro | `0.65rem` (~10px) | 400 | Toggle links |
| Logo | `0.85rem` (~13.5px) | 700 | Panel logo text |

### Letter Spacing

| Usage | Value |
|-------|-------|
| Section labels (uppercase) | `0.08em` |
| Paused badge | `0.06em` |
| Running ticket | `0.02em` |
| Pause/resume buttons | `0.03em` |

### Line Height

| Usage | Value |
|-------|-------|
| Agent description text | `1.4` |
| Button/badge labels | `1.4` |

---

## Spacing System

The dashboard uses ad-hoc spacing values without a defined scale. The following values appear frequently:

### Common Padding Values

| Value | Usage |
|-------|-------|
| `4px` | Tight padding (toggle button, nav icon) |
| `5px 10px` | Agent status items |
| `6px 10px` | Theme toggle button, running agent hover |
| `8px 10px` | Nav item padding |
| `12px 8px` | Panel content padding |
| `14px 12px` | Panel header |
| `16px 20px` | Agent detail header |
| `20px` | Main content area padding |

### Common Gap Values

| Value | Usage |
|-------|-------|
| `2px` | Agent status list gap |
| `3px` | Small metric gaps |
| `4px` | Panel content gap |
| `6px` | Header element gaps |
| `8px` | Agent status row gap |
| `10px` | Running metrics gap |
| `16px` | Collapse icon gap |

### Proposed Spacing Scale (Future)

```
--space-1: 4px
--space-2: 8px
--space-3: 12px
--space-4: 16px
--space-5: 20px
--space-6: 24px
--space-8: 32px
--space-10: 40px
```

---

## Border & Radius

### Border Radius Values

| Value | Usage |
|-------|-------|
| `3px` | Tiny badges, paused/label badges |
| `5px` | Agent status items |
| `6px` | Nav items, running agent container, general cards |
| `8px` | Theme toggle button |
| `50%` | Status indicator dots |

### Proposed Token System (Future)

```css
--radius-sm: 3px;
--radius-md: 6px;
--radius-lg: 8px;
--radius-full: 50%;
```

### Border Widths

All borders use `1px` (solid). No other widths are used.

---

## Shadow System

| Shadow | Value | Usage |
|--------|-------|-------|
| Detail panel | `-4px 0 24px rgba(0,0,0,0.4)` | Slide-in agent detail panel |
| Overlay | `rgba(0,0,0,0.55)` | Modal/overlay backdrop |

### Proposed Token System (Future)

```css
--shadow-panel: -4px 0 24px rgba(0,0,0,0.4);
--shadow-modal: 0 8px 32px rgba(0,0,0,0.4);
--shadow-card: 0 2px 8px rgba(0,0,0,0.2);
```

---

## Animation & Motion

### Keyframe Animations

| Name | Duration | Easing | Usage |
|------|----------|--------|-------|
| `pulse-green` | 1.5s | ease-in-out, infinite | Running agent status dot |
| `pipeline-pulse` | — | — | Pipeline step indicators |
| `pulse` | — | — | Generic pulse animation |
| `spin` | — | — | Loading spinner |
| `fadeIn` | — | — | Element entry animations |
| `bounce` | — | — | Achievement/notification bounce |
| `reasoning-fade-in` | — | — | AI reasoning reveal |

### Transition Values

| Property | Duration | Easing | Usage |
|----------|----------|--------|-------|
| `background` | `0.15s` | ease | Nav item hover |
| `background, color` | `0.2s` | ease | Theme toggle |
| `background-color, color, border-color` | `0.3s` | ease | Theme switch (full) |
| `width, min-width` | `0.3s` | ease | Panel collapse |
| `transform` | `0.3s` | `cubic-bezier(0.4,0,0.2,1)` | Slide-in panel |
| `max-height` | `0.3s` | ease-out/ease-in | Expandable sections |
| `opacity` | `0.25s` | ease | Overlay fade |

### Proposed Motion Tokens (Future)

```css
--duration-fast: 0.15s;
--duration-normal: 0.2s;
--duration-slow: 0.3s;
--easing-default: ease;
--easing-decelerate: cubic-bezier(0, 0, 0.2, 1);
--easing-accelerate: cubic-bezier(0.4, 0, 1, 1);
--easing-standard: cubic-bezier(0.4, 0, 0.2, 1);
```

---

## Component Inventory

The dashboard contains the following major component patterns:

### Layout Components

| Component | CSS Classes | Description |
|-----------|-------------|-------------|
| App Layout | `.app-layout` | Root flex layout (sidebar + main) |
| Left Panel | `.left-panel`, `.left-panel.collapsed` | Collapsible navigation sidebar (220px / 48px) |
| Main Content | `.main-content` | Primary content area |
| Container | `.container` | Max-width wrapper (1400px) |
| Header | `.header` | Sticky page header |

### Navigation

| Component | CSS Classes | Description |
|-----------|-------------|-------------|
| Panel Nav Item | `.panel-nav-item`, `.panel-nav-item.active` | Sidebar navigation buttons |
| Panel Section Label | `.panel-section-label` | Navigation group labels |
| Collapse Icon | `.collapse-icon`, `.collapse-icon-btn` | Icons shown in collapsed sidebar |

### Agent Status Components

| Component | CSS Classes | Description |
|-----------|-------------|-------------|
| Agent Status Panel | `.agent-status-panel` | Container for agent list |
| Agent Status Item | `.agent-status-item`, `.agent-status-item.status-running` | Individual agent row |
| Status Dot | `.agent-status-dot`, `.status-idle/.status-running/.status-paused/.status-error` | Animated status indicator |
| Status Label | `.agent-status-label`, `.label-*` | Text status badge |
| Pause/Resume Buttons | `.agent-pause-btn`, `.agent-resume-btn` | Action buttons |
| Paused Badge | `.agent-paused-badge` | "PAUSED" badge overlay |
| Running Header | `.agent-running-header`, `.agent-running-ticket`, `.agent-running-title` | Active task display |
| Running Metrics | `.agent-running-metrics`, `.agent-running-metric-*` | Token/cost/time metrics |
| Description Toggle | `.agent-desc-toggle`, `.agent-desc-container`, `.agent-desc-text` | Expandable agent description |

### Detail Panel (Slide-in)

| Component | CSS Classes | Description |
|-----------|-------------|-------------|
| Overlay | `.agent-detail-overlay` | Modal backdrop |
| Panel | `.agent-detail-panel` | Slide-in from right (420px) |
| Panel Header | `.agent-detail-header` | Sticky panel header |

### Cards

| Component | CSS Classes | Description |
|-----------|-------------|-------------|
| Card | `.card` | Standard data card |
| Card Title | `.card-title` | Card header text |

### Theme Toggle

| Component | CSS Classes | Description |
|-----------|-------------|-------------|
| Theme Button | `.theme-toggle-btn` | Dark/light mode switch |

### Chat Interface

| Component | CSS Classes | Description |
|-----------|-------------|-------------|
| Chat Message | `.chat-message`, `.chat-message.system` | Chat message bubbles |
| Chat Content | `.chat-message-content` | Message body with system styling |

---

## Layout System

### Responsive Breakpoints

| Breakpoint | Value | Behavior |
|------------|-------|----------|
| Mobile | `480px` | Compact layout adjustments |
| Tablet | `720px` | Mid-size adaptations |
| Small desktop | `768px` | Auto-collapse left panel |
| Medium desktop | `1100px` | Layout reflow |
| Container max | `1400px` | Maximum content width |

### Layout Dimensions

| Element | Dimension |
|---------|-----------|
| Left panel (expanded) | `220px` |
| Left panel (collapsed) | `48px` |
| Agent detail panel | `420px` (max `95vw`) |
| Container max-width | `1400px` |

---

## Design Audit Findings

### Issues Identified

1. **Massive hardcoded color usage:** 59 unique hardcoded hex colors appear in the CSS but are not referenced as CSS variables. Only 11 variables are in `:root`. This makes theming maintenance very difficult.

2. **Undefined variable:** `--panel-bg` is used 3 times via `var(--panel-bg, #161b22)` but is never defined in `:root`. It works due to the fallback value, but this is a bug.

3. **No spacing scale:** All padding/gap/margin values are ad-hoc. No consistent spacing system exists.

4. **No border-radius scale:** Multiple inconsistent radius values (3px, 5px, 6px, 8px, 50%) are hardcoded without tokens.

5. **No shadow tokens:** Box-shadow values are hardcoded without tokens.

6. **No motion tokens:** 7 transition durations and easings appear inconsistently throughout the file.

7. **Duplicate status colors:** Status colors (`#22c55e`, `#eab308`, `#ef4444`, `#475569`) are repeated throughout the CSS with both full hex and rgba variations, without CSS variable references.

8. **Typography not tokenized:** Font sizes use raw rem values without a defined scale or CSS variable system.

9. **Light theme coverage:** The `[data-theme="light"]` block overrides 10 of the 11 variables, but many hardcoded dark colors remain in use during light mode.

### Priority Fixes (Recommended)

| Priority | Fix | Effort |
|----------|-----|--------|
| High | Define `--panel-bg` in `:root` | 5 min |
| High | Add status color CSS variables (`--status-running`, `--status-paused`, `--status-error`, `--status-idle`) | 30 min |
| Medium | Add spacing tokens (`--space-1` through `--space-10`) | 1 hour |
| Medium | Add border-radius tokens | 30 min |
| Medium | Add typography scale tokens | 1 hour |
| Low | Replace all 59 hardcoded colors with CSS variable references | 4–8 hours |
| Low | Add shadow tokens | 30 min |
| Low | Add motion/animation tokens | 30 min |
