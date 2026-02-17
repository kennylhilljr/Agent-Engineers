# config – Centralized Configuration Management

**Source:** `config.py`

---

## Overview

All environment-variable access in Agent-Engineers is funnelled through this
module.  Instead of calling `os.environ` directly throughout the codebase,
every component imports `get_config()` and reads from the typed
`AgentConfig` dataclass.

This design makes testing straightforward: patch environment variables and
call `reset_config()` to obtain a fresh instance without restarting the
process.

---

## Quick-start

```python
from config import get_config

cfg = get_config()

# Check all required keys are present
errors = cfg.validate()
if errors:
    raise RuntimeError(f"Bad configuration: {errors}")

print(cfg.windsurf_mode)       # WindsurfMode.DISABLED
print(cfg.api_keys.anthropic)  # value of ANTHROPIC_API_KEY
print(cfg.dashboard_port)      # 8080 (default)
```

---

## Enumerations

### `WindsurfMode`

```python
class WindsurfMode(Enum):
    DISABLED    = "disabled"
    HEADLESS    = "headless"
    INTERACTIVE = "interactive"
```

Controls how the Windsurf IDE integration behaves.  Set via the
`WINDSURF_MODE` environment variable.

### `LogLevel`

```python
class LogLevel(Enum):
    DEBUG   = "debug"
    INFO    = "info"
    WARNING = "warning"
    ERROR   = "error"
```

Application-wide log verbosity.  Set via the `LOG_LEVEL` environment
variable (default: `"info"`).

---

## `APIKeys`

```python
@dataclass
class APIKeys:
    anthropic: Optional[str]   # ANTHROPIC_API_KEY
    openai:    Optional[str]   # OPENAI_API_KEY
    gemini:    Optional[str]   # GEMINI_API_KEY or GOOGLE_API_KEY
    groq:      Optional[str]   # GROQ_API_KEY
    linear:    Optional[str]   # LINEAR_API_KEY
    github:    Optional[str]   # GITHUB_TOKEN
    slack:     Optional[str]   # SLACK_BOT_TOKEN
    arcade:    Optional[str]   # ARCADE_API_KEY
```

All API keys are read lazily from the environment at instantiation time.

### `APIKeys.validate() -> list[str]`

Returns a list of missing **required** key names.  Currently only
`ANTHROPIC_API_KEY` is required; all others are optional.

```python
keys = APIKeys()
missing = keys.validate()
if missing:
    print(f"Please set: {', '.join(missing)}")
```

---

## `AgentConfig`

```python
@dataclass
class AgentConfig:
    windsurf_mode:       WindsurfMode  # WINDSURF_MODE (default: "disabled")
    timeout:             int           # AGENT_TIMEOUT  (default: 300 s)
    log_level:           LogLevel      # LOG_LEVEL      (default: "info")
    api_keys:            APIKeys
    prompts_dir:         Path          # PROMPTS_DIR    (default: "prompts")
    screenshots_dir:     Path          # SCREENSHOTS_DIR (default: "screenshots")
    github_repo:         Optional[str] # GITHUB_REPO
    linear_team_id:      Optional[str] # LINEAR_TEAM_ID
    dashboard_port:      int           # DASHBOARD_PORT  (default: 8080)
    websocket_port:      int           # WEBSOCKET_PORT  (default: 8765)
    control_plane_port:  int           # CONTROL_PLANE_PORT (default: 9100)
    max_workers:         int           # MAX_WORKERS     (default: 4)
```

### `AgentConfig.from_env() -> AgentConfig`  (classmethod)

Canonical factory method. All fields are populated from the current
environment at call time.

```python
import os
os.environ["AGENT_TIMEOUT"] = "600"
cfg = AgentConfig.from_env()
assert cfg.timeout == 600
```

### `AgentConfig.validate() -> list[str]`

Returns human-readable error messages for any misconfigured fields.

```python
cfg = AgentConfig.from_env()
errors = cfg.validate()
if errors:
    for err in errors:
        print(f"Config error: {err}")
```

### `AgentConfig.is_valid() -> bool`

Convenience wrapper; returns `True` when `validate()` returns `[]`.

```python
if not cfg.is_valid():
    raise RuntimeError("Invalid configuration – cannot start agent")
```

---

## Module-level helpers

### `get_config() -> AgentConfig`

Returns the process-wide singleton `AgentConfig` instance (lazy-created on
first call, then cached).

```python
from config import get_config

cfg = get_config()
print(cfg.dashboard_port)  # 8080
```

### `reset_config() -> None`

Clears the cached singleton so the next `get_config()` call creates a fresh
instance.  Primarily useful in tests.

```python
import os
from config import get_config, reset_config

os.environ["DASHBOARD_PORT"] = "9090"
reset_config()
cfg = get_config()
assert cfg.dashboard_port == 9090
reset_config()  # restore default state
```

---

## Environment variable reference

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | – | **Required.** Anthropic API key |
| `OPENAI_API_KEY` | – | OpenAI API key |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | – | Google Gemini API key |
| `GROQ_API_KEY` | – | Groq API key |
| `LINEAR_API_KEY` | – | Linear project management key |
| `GITHUB_TOKEN` | – | GitHub personal access token |
| `SLACK_BOT_TOKEN` | – | Slack bot token |
| `ARCADE_API_KEY` | – | Arcade API key |
| `WINDSURF_MODE` | `disabled` | `disabled` / `headless` / `interactive` |
| `AGENT_TIMEOUT` | `300` | Task timeout in seconds |
| `LOG_LEVEL` | `info` | `debug` / `info` / `warning` / `error` |
| `PROMPTS_DIR` | `prompts` | Path to prompts directory |
| `SCREENSHOTS_DIR` | `screenshots` | Path to screenshots directory |
| `GITHUB_REPO` | – | GitHub repo in `owner/repo` format |
| `LINEAR_TEAM_ID` | – | Linear team identifier |
| `DASHBOARD_PORT` | `8080` | HTTP dashboard port |
| `WEBSOCKET_PORT` | `8765` | WebSocket server port |
| `CONTROL_PLANE_PORT` | `9100` | Daemon control plane port |
| `MAX_WORKERS` | `4` | Maximum concurrent worker threads |
