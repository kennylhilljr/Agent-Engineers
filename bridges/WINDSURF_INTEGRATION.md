# Windsurf (Codeium) Agent Integration

## Overview

Adds Codeium's Windsurf IDE as a sub-agent in the multi-AI orchestrator.
Windsurf runs in headless mode, providing its own agentic coding model (Cascade)
for parallel coding tasks, cross-IDE validation, and alternative implementations.

## Architecture

```
Orchestrator
    |
    +-- linear (Haiku)
    +-- coding (Sonnet)      <-- Primary coding agent (Claude)
    +-- github (Haiku)
    +-- slack (Haiku)
    +-- chatgpt (Haiku)  --> OpenAI Bridge   --> ChatGPT API
    +-- gemini (Haiku)   --> Gemini Bridge   --> Gemini API
    +-- groq (Haiku)     --> Groq Bridge     --> Groq Cloud
    +-- kimi (Haiku)     --> KIMI Bridge     --> Moonshot API
    +-- windsurf (Haiku) --> Windsurf Bridge --> Windsurf CLI / Docker
                               |
                               +-- CLI mode (local installation)
                               +-- Docker mode (isolated container)
```

## Files

| File | Purpose |
|------|---------|
| `windsurf_bridge.py` | Core bridge with CLI and Docker execution backends |
| `scripts/windsurf_cli.py` | Standalone CLI for submitting tasks |
| `prompts/windsurf_agent_prompt.md` | System prompt for the Windsurf bridge agent |
| `agents/definitions.py` | `windsurf` agent definition with `WINDSURF_AGENT` export |

## Setup

### Path 1: CLI Mode (Default)

Install Windsurf IDE from https://codeium.com/windsurf. The CLI must be
available in PATH as `windsurf`.

```bash
# .env:
WINDSURF_MODE=cli
```

### Path 2: Docker Mode

Build or pull a Windsurf-in-a-box Docker image:

```bash
# .env:
WINDSURF_MODE=docker
WINDSURF_DOCKER_IMAGE=windsurfinabox:latest
```

### Configuration

```bash
# Execution mode: cli (default) or docker
WINDSURF_MODE=cli

# Docker image (only for docker mode)
WINDSURF_DOCKER_IMAGE=windsurfinabox:latest

# Task timeout in seconds (default: 300)
WINDSURF_TIMEOUT=300

# Working directory for tasks (default: temp dir)
# WINDSURF_WORKSPACE=/path/to/workspace

# Orchestrator sub-agent model (default: haiku)
# WINDSURF_AGENT_MODEL=haiku
```

### Verify Setup

```bash
python scripts/windsurf_cli.py --status
```

## Usage

### CLI (Standalone)

```bash
# Submit a coding task
python scripts/windsurf_cli.py --task "Implement a login page with form validation"

# Specify workspace
python scripts/windsurf_cli.py --task "Add unit tests" --workspace ./my-project

# Docker mode
python scripts/windsurf_cli.py --mode docker --task "Refactor auth module"

# Custom timeout
python scripts/windsurf_cli.py --timeout 600 --task "Large refactor task"

# Interactive mode
python scripts/windsurf_cli.py

# Pipe input
echo "Fix the bug in auth.py" | python scripts/windsurf_cli.py

# Verbose (show changed files)
python scripts/windsurf_cli.py -v --task "Update CSS"
```

### Programmatic (Python)

```python
from windsurf_bridge import WindsurfBridge

bridge = WindsurfBridge.from_env()
session = bridge.create_session(workspace="./my-project")
response = bridge.send_task(session, "Add error handling to the API routes")
print(response.content)
print(f"Files changed: {response.files_changed}")
print(f"Exit code: {response.exit_code}")
```

## How It Works

Windsurf operates via file-based communication:

1. **Input:** Task written to `.windsurf-instructions.md` in the workspace
2. **Execution:** Windsurf CLI runs in headless mode (or Docker container)
3. **Output:** Results read from `.windsurf-output.txt`
4. **Files:** Any files created/modified by Windsurf in the workspace

The bridge handles all file I/O and process management.

## When the Orchestrator Uses Windsurf

- Parallel coding: Windsurf implements a feature independently for comparison
- Cross-IDE validation: have Windsurf verify an implementation approach
- Alternative implementations: get a second implementation to compare
- User explicitly requests Windsurf for a coding task

## Acceptance Criteria

- [x] Task submission via CLI and Docker modes
- [x] File-based communication with Windsurf
- [x] Orchestrator integration as sub-agent
- [x] Timeout handling for long-running tasks
- [x] Changed file detection via git diff
- [x] Documentation complete
