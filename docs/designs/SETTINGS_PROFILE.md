# Settings & Profile Page — Design Spec

**Feature:** AI-241 Phase 2 Design Spec
**Status:** Design Spec (Not Implemented)
**Last Updated:** 2026-02-18
**Target Users:** Developers configuring their agent environment

---

## Overview

A settings and profile page providing access to user preferences, system configuration,
API key management, agent defaults, theme preferences, and notification settings.
Organized into tabbed sections for clarity.

---

## Layout Description

### Page Layout

```
LEFT PANEL (sidebar — unchanged)
│
└── MAIN CONTENT
    ┌──────────────────────────────────────────────────────┐
    │  PAGE HEADER: Settings                               │
    │  "Configure your agent environment and preferences"  │
    ├──────────────────────────────────────────────────────┤
    │                                                      │
    │  SETTINGS TABS                                       │
    │  [Profile] [API Keys] [Agents] [Appearance] [Notif]  │
    │  ─────────────────────────────────────────────────── │
    │                                                      │
    │  ACTIVE TAB CONTENT (full width below tabs)          │
    │  ┌──────────────────────────────────────────────┐   │
    │  │                                              │   │
    │  │  SETTINGS SECTION (grouped form fields)      │   │
    │  │                                              │   │
    │  └──────────────────────────────────────────────┘   │
    │                                                      │
    │  FOOTER: [Save Changes] [Reset to Defaults]          │
    └──────────────────────────────────────────────────────┘
```

### Tab Navigation

```
 ┌─────────┬──────────┬────────┬────────────┬────────────┐
 │ Profile │ API Keys │ Agents │ Appearance │ Notificatn │
 └─────────┴──────────┴────────┴────────────┴────────────┘
   (active tab has bottom border in --accent color)
```

---

## Tab Definitions

### Tab 1: Profile

**Purpose:** User identity and workspace configuration.

```
┌─────────────────────────────────────────────┐
│  Profile                                    │
│  ─────────────────────────────────────────  │
│                                             │
│  Display Name                               │
│  ┌──────────────────────────────────────┐  │
│  │ Developer Name                       │  │
│  └──────────────────────────────────────┘  │
│                                             │
│  Email (for alerts)                         │
│  ┌──────────────────────────────────────┐  │
│  │ dev@example.com                      │  │
│  └──────────────────────────────────────┘  │
│                                             │
│  Workspace / Project Name                   │
│  ┌──────────────────────────────────────┐  │
│  │ Agent Engineers                      │  │
│  └──────────────────────────────────────┘  │
│                                             │
│  Time Zone                                  │
│  ┌──────────────────────────────────────┐  │
│  │ UTC-5 (Eastern Time)             [▼] │  │
│  └──────────────────────────────────────┘  │
│                                             │
│  Avatar / Identifier Color                  │
│  ● ○ ○ ○ ○ ○ (color swatches)              │
│                                             │
└─────────────────────────────────────────────┘
```

### Tab 2: API Keys

**Purpose:** Manage API credentials for all integrated services.

```
┌─────────────────────────────────────────────┐
│  API Keys                                   │
│  ─────────────────────────────────────────  │
│                                             │
│  Anthropic (Required)                 [✓]   │
│  ┌─────────────────────────────────────┐   │
│  │ ●●●●●●●●●●●●●●●●●●sk-ant-         │[👁]│
│  └─────────────────────────────────────┘   │
│  Last validated: 2 hours ago  [Re-validate] │
│                                             │
│  Linear                               [✓]   │
│  ┌─────────────────────────────────────┐   │
│  │ ●●●●●●●●●●●●●●●●●●lin_api_        │[👁]│
│  └─────────────────────────────────────┘   │
│  Last validated: 1 day ago   [Re-validate]  │
│                                             │
│  GitHub                               [✗]   │
│  ┌─────────────────────────────────────┐   │
│  │ (not configured)                   │   │
│  └─────────────────────────────────────┘   │
│  [+ Add GitHub Token]                       │
│                                             │
│  Slack Webhook                        [—]   │
│  ┌─────────────────────────────────────┐   │
│  │ ●●●●●●●●●●●●●https://hooks...     │[👁]│
│  └─────────────────────────────────────┘   │
│                                             │
│  ⚠ Keys stored in .env (local only)        │
└─────────────────────────────────────────────┘
```

**Key status indicators:**
- [✓] Green check — validated and working
- [✗] Red X — not configured or validation failed
- [—] Dash — configured but not validated

### Tab 3: Agents

**Purpose:** Configure default behaviors for each agent.

```
┌─────────────────────────────────────────────┐
│  Agent Configuration                        │
│  ─────────────────────────────────────────  │
│                                             │
│  Default Models                             │
│  ┌───────────────────────────────────────┐  │
│  │ Coding Agent         [sonnet      ▼]  │  │
│  │ PR Reviewer          [sonnet      ▼]  │  │
│  │ Linear Agent         [haiku       ▼]  │  │
│  │ GitHub Agent         [haiku       ▼]  │  │
│  │ Slack Agent          [haiku       ▼]  │  │
│  │ Designer Agent       [haiku       ▼]  │  │
│  │ Product Manager      [sonnet      ▼]  │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  Concurrency                                │
│  ┌───────────────────────────────────────┐  │
│  │ Max concurrent coding agents: [3  ±] │  │
│  │ Max concurrent PR reviewers:  [2  ±] │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  Safety                                     │
│  ┌───────────────────────────────────────┐  │
│  │ [✓] Require approval before pushing  │  │
│  │ [✓] Pause on budget exceeded         │  │
│  │ [ ] Auto-merge passing PRs           │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  Task Assignment                            │
│  ┌───────────────────────────────────────┐  │
│  │ Orchestrator model: [haiku        ▼]  │  │
│  │ Max ticket complexity: [High      ▼]  │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

### Tab 4: Appearance

**Purpose:** Visual customization (theme, density, layout).

```
┌─────────────────────────────────────────────┐
│  Appearance                                 │
│  ─────────────────────────────────────────  │
│                                             │
│  Theme                                      │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐    │
│  │  DARK   │  │  LIGHT  │  │  AUTO   │    │
│  │ (●) ■■■ │  │ ○   □□□ │  │ ○  ◑◑◑ │    │
│  └─────────┘  └─────────┘  └─────────┘    │
│  Current: Dark                              │
│                                             │
│  Sidebar                                    │
│  ┌───────────────────────────────────────┐  │
│  │ Default width:  [Expanded ▼]          │  │
│  │ Show agent icons: [✓]                 │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  Density                                    │
│  ┌───────────────────────────────────────┐  │
│  │ ○ Compact   (●) Normal   ○ Comfortable│  │
│  └───────────────────────────────────────┘  │
│                                             │
│  Accent Color                               │
│  ┌───────────────────────────────────────┐  │
│  │  ● Blue (default)                     │  │
│  │  ○ Purple                             │  │
│  │  ○ Green                              │  │
│  │  ○ Custom [#58a6ff]                   │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  Animations                                 │
│  [ ] Reduce motion (accessibility)          │
└─────────────────────────────────────────────┘
```

### Tab 5: Notifications

**Purpose:** Configure alerting and notification preferences.

```
┌─────────────────────────────────────────────┐
│  Notifications                              │
│  ─────────────────────────────────────────  │
│                                             │
│  In-App Notifications                       │
│  ┌───────────────────────────────────────┐  │
│  │ [✓] Agent task completed             │  │
│  │ [✓] Agent error occurred             │  │
│  │ [✓] PR ready for review              │  │
│  │ [ ] Agent status changed             │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  Slack Notifications                        │
│  ┌───────────────────────────────────────┐  │
│  │ Webhook: ●●●●●●●● [configured ✓]     │  │
│  │ Channel: #agent-notifications         │  │
│  │ [✓] Task completed                   │  │
│  │ [✓] Budget alerts                    │  │
│  │ [ ] Agent idle for >30 minutes       │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  Budget Alerts                              │
│  ┌───────────────────────────────────────┐  │
│  │ Alert at: [50%▼] [75%▼] [90%▼]       │  │
│  │ [✓] Pause agents at 100%             │  │
│  └───────────────────────────────────────┘  │
│                                             │
│  Sound                                      │
│  [ ] Play sound on task completion          │
│  [ ] Play sound on agent error              │
└─────────────────────────────────────────────┘
```

---

## Component List

| Component | Description | CSS Classes (proposed) |
|-----------|-------------|----------------------|
| SettingsPage | Page wrapper | `.settings-page` |
| SettingsTabs | Tab navigation | `.settings-tabs`, `.settings-tab`, `.settings-tab.active` |
| SettingsSection | Grouped form block | `.settings-section`, `.settings-section-title` |
| SettingsField | Label + input row | `.settings-field`, `.settings-field-label` |
| ApiKeyInput | Masked input with status | `.api-key-input`, `.api-key-status-icon` |
| ModelSelect | Dropdown for model tier | `.model-selector` |
| ToggleSwitch | Boolean on/off | `.settings-toggle` |
| ThemeSelector | Theme card picker | `.theme-card`, `.theme-card.active` |
| ColorPicker | Accent color swatches | `.color-swatch`, `.color-swatch.selected` |
| NumberStepper | +/- number control | `.number-stepper` |
| SettingsFooter | Save/Reset buttons | `.settings-footer` |

---

## User Flow

```
[Left Panel → "Settings" nav item]
         ↓
[Settings page loads — default tab: Profile]
         ↓
         ├── [Click tab] → show tab content
         ├── [Edit field] → field shows unsaved indicator (●)
         ├── [API key field] → show/hide eye toggle
         ├── [Re-validate] → spinner → success/failure
         ├── [Click "Save Changes"] → save all pending changes
         └── [Click "Reset to Defaults"] → confirmation dialog
```

---

## Key Interactions

| Interaction | Behavior |
|-------------|----------|
| Tab switch | Instant (no server round trip), preserve unsaved changes |
| Unsaved changes indicator | Yellow dot on tab label with unsaved edits |
| API key show/hide | Toggle masking with eye icon |
| API key re-validate | Inline spinner → check or error message |
| Model dropdown | Shows cost tier info: "haiku ($0.25/M)" |
| Theme selector | Applies immediately as live preview |
| Accent color | Applies immediately, updates `--accent` CSS variable |
| Save Changes | Shows "Saving..." → "Saved!" with green check |
| Reset to Defaults | Requires confirmation: "This will reset all settings" |
| Navigation away with unsaved | "You have unsaved changes. Leave?" confirmation |

---

## Design Tokens Used

- `--bg-secondary` — page and section backgrounds
- `--bg-primary` — input backgrounds
- `--text-primary` — field labels, values
- `--text-secondary` — helper text, placeholders
- `--border-color` — section borders, input borders
- `--accent` — active tab indicator, save button, focus ring
- `--card-bg` — settings section card backgrounds
- `--transition-theme` — live theme preview transitions

---

## Accessibility Requirements

- Tabs use `role="tablist"`, `role="tab"`, `aria-selected`, `aria-controls`
- Tab panels use `role="tabpanel"`, `aria-labelledby`
- API key inputs labeled properly with visible `<label>` elements
- Password inputs use `type="password"` with show/hide toggle updating `aria-label`
- Toggle switches use `role="switch"` with `aria-checked`
- Theme selector cards use `role="radio"` within `role="radiogroup"`
- Color picker swatches have accessible names (e.g., "Blue accent color")
- Form validation errors associated with inputs via `aria-describedby`
- Save confirmation uses `aria-live="polite"` for success/failure announcements
