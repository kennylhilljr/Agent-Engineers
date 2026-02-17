# protocols – typing.Protocol Interface Definitions

**Source:** `protocols.py`

---

## Overview

This module defines structural subtyping contracts using Python's
`typing.Protocol`.  Components depend on these protocols rather than concrete
classes, reducing coupling and enabling easier testing with mocks.

All protocols are decorated with `@runtime_checkable`, so `isinstance` checks
work at runtime:

```python
from protocols import BridgeProtocol
from bridges.openai_bridge import OpenAIBridge

bridge = OpenAIBridge()
assert isinstance(bridge, BridgeProtocol)  # True
```

---

## `BridgeProtocol`

```python
@runtime_checkable
class BridgeProtocol(Protocol):
    @property
    def provider_name(self) -> str: ...
    async def send_task(self, task: str, **kwargs: Any) -> Any: ...
    def get_auth_info(self) -> dict[str, str]: ...
```

Any object that exposes these three members satisfies `BridgeProtocol` –
no explicit inheritance from `BaseBridge` is required.

**Members:**

| Member | Kind | Description |
|---|---|---|
| `provider_name` | property | Lowercase provider identifier |
| `send_task` | async method | Send a task prompt; return a response |
| `get_auth_info` | method | Return auth metadata dict |

**Example – type-annotated function accepting any bridge:**

```python
from protocols import BridgeProtocol

async def run_task(bridge: BridgeProtocol, task: str) -> str:
    response = await bridge.send_task(task)
    return response.content
```

---

## `ConfigProtocol`

```python
@runtime_checkable
class ConfigProtocol(Protocol):
    def validate(self) -> list[str]: ...
    def is_valid(self) -> bool: ...
```

Any configuration object that provides `validate()` and `is_valid()` satisfies
this protocol.

**Members:**

| Member | Kind | Description |
|---|---|---|
| `validate` | method | Returns list of error strings |
| `is_valid` | method | Returns `True` when valid |

**Example:**

```python
from protocols import ConfigProtocol
from config import AgentConfig

def check_config(cfg: ConfigProtocol) -> None:
    if not cfg.is_valid():
        raise ValueError(cfg.validate())

check_config(AgentConfig.from_env())
```

---

## `ProgressTrackerProtocol`

```python
@runtime_checkable
class ProgressTrackerProtocol(Protocol):
    def load_project_state(self) -> dict[str, Any]: ...
```

Any object that can load and return a project-state dictionary.

**Example:**

```python
from protocols import ProgressTrackerProtocol

def display_progress(tracker: ProgressTrackerProtocol) -> None:
    state = tracker.load_project_state()
    print(f"Issues open: {state.get('open_issues', 0)}")
```

---

## `ExceptionProtocol`

```python
@runtime_checkable
class ExceptionProtocol(Protocol):
    @property
    def error_code(self) -> Optional[str]: ...
    def to_dict(self) -> dict[str, Any]: ...
```

Structural contract for structured exceptions.  All `AgentError` subclasses
satisfy this protocol.

**Members:**

| Member | Kind | Description |
|---|---|---|
| `error_code` | property | Machine-readable error code string |
| `to_dict` | method | Returns JSON-compatible dict |

**Example:**

```python
from protocols import ExceptionProtocol
from exceptions import BridgeError

def log_error(exc: ExceptionProtocol) -> None:
    data = exc.to_dict()
    print(f"[{exc.error_code}] {data}")

log_error(BridgeError("connection refused", provider="openai"))
```

---

## Using protocols for dependency injection

Protocols make it trivial to swap implementations in tests:

```python
import asyncio
from typing import Any
from protocols import BridgeProtocol

class StubBridge:
    """Test double that satisfies BridgeProtocol."""

    @property
    def provider_name(self) -> str:
        return "stub"

    async def send_task(self, task: str, **kwargs: Any) -> Any:
        from bridges.base_bridge import BridgeResponse
        return BridgeResponse(content="stub reply", model="stub", provider="stub")

    def get_auth_info(self) -> dict[str, str]:
        return {}

assert isinstance(StubBridge(), BridgeProtocol)  # True – no inheritance needed
```
