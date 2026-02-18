# Onboarding Wizard — Design Spec

**Feature:** AI-241 Phase 2 Design Spec
**Status:** Design Spec (Not Implemented)
**Last Updated:** 2026-02-18
**Target Users:** New developers setting up the Agent Dashboard for the first time

---

## Overview

A multi-step onboarding wizard that guides new users through the initial configuration
of the Agent Dashboard: connecting API keys, configuring agents, and verifying connectivity.

The wizard should be a modal overlay displayed on first launch (no `config.json` detected)
or accessible via Settings > "Run Setup Wizard".

---

## Layout Description

### Modal Overlay

```
┌─────────────────────────────────────────────────────┐
│  [overlay: rgba(0,0,0,0.7) blur(4px)]              │
│  ┌─────────────────────────────────────────────┐   │
│  │           WIZARD MODAL (640px wide)          │   │
│  │  ┌───────────────────────────────────────┐  │   │
│  │  │  HEADER: Icon + Title + Close (×)     │  │   │
│  │  ├───────────────────────────────────────┤  │   │
│  │  │  STEP INDICATOR (5 dots or numbers)   │  │   │
│  │  ├───────────────────────────────────────┤  │   │
│  │  │                                       │  │   │
│  │  │         STEP CONTENT AREA             │  │   │
│  │  │         (varies per step)             │  │   │
│  │  │                                       │  │   │
│  │  ├───────────────────────────────────────┤  │   │
│  │  │  FOOTER: [Back] [Skip] [Next/Finish]  │  │   │
│  │  └───────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### Step Indicator

```
  Step 1 of 5
  [●]──[○]──[○]──[○]──[○]
  Welcome  APIs  Agents  Test  Done
```

Active step: filled circle with accent color (`--accent`)
Completed step: filled circle with success green (`--status-running`)
Upcoming step: empty circle with border color

---

## Step Definitions

### Step 1: Welcome

**Purpose:** Introduce the system, set expectations.

```
┌─────────────────────────────────────┐
│  🤖  Welcome to Agent Dashboard     │
│                                     │
│  You're about to set up a powerful  │
│  AI agent orchestration system.     │
│  This wizard takes ~5 minutes.      │
│                                     │
│  What you'll need:                  │
│  ✓ Claude API key (Anthropic)       │
│  ✓ Linear API token (optional)      │
│  ✓ GitHub token (optional)          │
│  ✓ Slack webhook (optional)         │
│                                     │
│  Already configured?                │
│  [Skip Setup] or [Start →]          │
└─────────────────────────────────────┘
```

**Components:**
- Hero icon (robot/agent icon, 48px)
- Welcome headline (h2)
- Checklist of prerequisites
- Two CTAs: "Skip Setup" (text link) and "Start" (primary button)

### Step 2: API Keys

**Purpose:** Collect required and optional API credentials.

```
┌─────────────────────────────────────┐
│  🔑  Connect Your APIs              │
│                                     │
│  Required                           │
│  ┌─────────────────────────────┐    │
│  │ Anthropic API Key      [?]  │    │
│  │ [sk-ant-...          ] [✓]  │    │
│  └─────────────────────────────┘    │
│                                     │
│  Optional (enable more features)    │
│  ┌─────────────────────────────┐    │
│  │ Linear API Token       [?]  │    │
│  │ [lin_api_...         ] [ ]  │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │ GitHub Token           [?]  │    │
│  │ [ghp_...             ] [ ]  │    │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │ Slack Webhook URL      [?]  │    │
│  │ [https://hooks...    ] [ ]  │    │
│  └─────────────────────────────┘    │
│                                     │
│  🔒 Keys stored locally in .env     │
└─────────────────────────────────────┘
```

**Components:**
- Input fields with password masking (show/hide toggle)
- Inline validation (loading spinner → green check or red error)
- Help tooltip [?] linking to API documentation
- Security notice (lock icon + note about local storage)
- Required vs. optional visual separation

### Step 3: Agent Configuration

**Purpose:** Select which agents to enable and configure their models.

```
┌─────────────────────────────────────┐
│  🤖  Configure Agents               │
│                                     │
│  Core Agents (always enabled)       │
│  ┌───────────────────────────────┐  │
│  │ [●] Coding Agent   [sonnet ▼] │  │
│  │ [●] Linear Agent   [haiku  ▼] │  │
│  │ [●] GitHub Agent   [haiku  ▼] │  │
│  └───────────────────────────────┘  │
│                                     │
│  Optional Agents                    │
│  ┌───────────────────────────────┐  │
│  │ [●] Slack Agent    [haiku  ▼] │  │
│  │ [ ] PR Reviewer    [sonnet ▼] │  │
│  │ [ ] Designer Agent [haiku  ▼] │  │
│  │ [ ] Product Mgr    [sonnet ▼] │  │
│  └───────────────────────────────┘  │
│                                     │
│  AI Bridges (cross-AI validation)   │
│  ┌───────────────────────────────┐  │
│  │ [ ] ChatGPT  [ ] Gemini       │  │
│  │ [ ] Groq     [ ] KIMI         │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
```

**Components:**
- Toggle switch per agent
- Model selector dropdown (haiku / sonnet / opus)
- Agent group labels with section dividers
- Disabled state for agents whose API keys weren't provided in Step 2

### Step 4: Connectivity Test

**Purpose:** Verify all configured connections work before completing setup.

```
┌─────────────────────────────────────┐
│  🔬  Testing Connections            │
│                                     │
│  Running verification...            │
│                                     │
│  ┌───────────────────────────────┐  │
│  │ Anthropic API     [▓▓▓▓▓▓✓]  │  │
│  │ Linear API        [▓▓▓▓▓▓✓]  │  │
│  │ GitHub API        [▓▓▓░░░ ]  │  │
│  │ Slack Webhook     [       ]  │  │
│  └───────────────────────────────┘  │
│                                     │
│  GitHub: Waiting for response...    │
│                                     │
│  [Retry Failed]    [Continue →]     │
└─────────────────────────────────────┘
```

**States:**
- Pending: grey progress bar animating
- Success: green check mark + "Connected" label
- Failed: red X + error message + "Retry" action
- Skipped: grey dash (for optional APIs not configured)

**Components:**
- Progress bars with animated fill
- Status icons (spinner → check/X)
- Per-service error messages
- "Retry Failed" button for error recovery
- "Continue Anyway" (skip errors for optional services)

### Step 5: All Done

**Purpose:** Confirm setup, provide next steps.

```
┌─────────────────────────────────────┐
│                                     │
│           🎉 You're Set Up!          │
│                                     │
│  Agent Dashboard is ready to use.   │
│                                     │
│  What's next:                       │
│  → View the Dashboard               │
│  → Create your first Linear ticket  │
│  → Read the documentation           │
│                                     │
│  Summary:                           │
│  ✓ 3 APIs connected                 │
│  ✓ 4 agents enabled                 │
│  ✓ Dark mode active                 │
│                                     │
│           [Open Dashboard]          │
└─────────────────────────────────────┘
```

**Components:**
- Success celebration (confetti animation or large checkmark)
- Setup summary (count of connected APIs, enabled agents)
- Quick-start action list
- Primary CTA: "Open Dashboard" (dismisses modal)

---

## Component List

| Component | Description | CSS Classes (proposed) |
|-----------|-------------|----------------------|
| WizardModal | Full-screen overlay + centered modal | `.wizard-modal`, `.wizard-overlay` |
| StepIndicator | Progress dots with labels | `.wizard-step-indicator`, `.step-dot` |
| StepContent | Content area for each step | `.wizard-step`, `.wizard-step.active` |
| ApiKeyInput | Masked input with validation | `.api-key-input`, `.api-key-status` |
| AgentToggle | Toggle + model selector row | `.agent-toggle-row`, `.model-select` |
| ConnectionTest | Progress bar + status per service | `.connection-test-item`, `.test-progress` |
| WizardFooter | Back/Skip/Next buttons | `.wizard-footer`, `.wizard-btn-primary` |

---

## User Flow

```
[First Launch / "Run Setup Wizard"]
         ↓
[Step 1: Welcome] → "Start" →
         ↓
[Step 2: API Keys] → validate keys in real-time → "Next" →
         ↓
[Step 3: Agent Config] → toggle agents, select models → "Next" →
         ↓
[Step 4: Connectivity Test] → auto-run tests → all pass / "Continue" →
         ↓
[Step 5: All Done] → "Open Dashboard" → [dismiss modal]
```

**Alternative flows:**
- User closes modal at any step → show confirmation "Are you sure? Setup is not complete."
- User clicks "Skip" → skip optional step, go to next
- Connectivity test fails → show retry, allow "Continue Anyway" for optional services

---

## Key Interactions

| Interaction | Behavior |
|-------------|----------|
| Click step dot | Jump to that step (only if step is completed or current) |
| API key input | Live validation after 500ms debounce (show spinner → check/X) |
| Agent toggle ON | Enable agent row, activate model dropdown |
| Agent toggle OFF (required) | Show tooltip "This agent is required and cannot be disabled" |
| Model dropdown | Show haiku/sonnet/opus options with cost labels |
| Back button | Navigate to previous step (no data loss) |
| Next button | Validate current step, advance if valid |
| Finish button | Save config, dismiss wizard, load dashboard |
| Overlay click | Show confirmation dialog before closing |
| Keyboard Esc | Same as overlay click |

---

## Design Tokens Used

From `design_tokens.json`:

- `--bg-secondary` — modal background
- `--bg-primary` — overlay darkness
- `--text-primary` — headings and body text
- `--text-secondary` — helper text, labels
- `--border-color` — input borders, dividers
- `--accent` — active step dot, primary button
- `--card-bg` — modal content background
- `--transition-theme` — theme-aware transitions

Status colors (to be added as tokens):
- `--status-running: #22c55e` — connected/success states
- `--status-error: #ef4444` — connection failure states
- `--status-paused: #eab308` — pending/in-progress states

---

## Accessibility Requirements

- Full keyboard navigation (Tab, Shift+Tab, Enter, Esc)
- ARIA role `dialog` on modal, `aria-labelledby` pointing to title
- ARIA `aria-current="step"` on active step indicator
- Focus trap within modal when open
- Focus returns to trigger element on close
- Screen reader announcements on step transitions
- Input validation errors announced via `aria-live="polite"`
- Minimum 4.5:1 contrast ratio for all text
