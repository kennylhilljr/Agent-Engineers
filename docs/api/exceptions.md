# exceptions – Custom Exception Hierarchy

**Source:** `exceptions.py`

---

## Overview

All Agent-Engineers errors inherit from `AgentError`, providing a unified
base for `except` clauses, structured logging, and JSON serialisation.

```
AgentError (base)
    ├── BridgeError          – AI provider communication errors
    ├── SecurityError        – Authentication / authorisation errors
    ├── ConfigurationError   – Misconfiguration / missing settings
    ├── TimeoutError         – Deadline / timeout exceeded
    ├── RateLimitError       – Rate limit exceeded
    └── AuthenticationError  – Dashboard-level credential errors
```

---

## `AgentError`

Base exception for all agent-related errors.

```python
class AgentError(Exception):
    def __init__(self, message: str, error_code: str = None): ...
    def __str__(self) -> str: ...
    def to_dict(self) -> dict: ...
    def to_json(self) -> str: ...
```

**Attributes:**

| Attribute | Type | Description |
|---|---|---|
| `message` | `str` | Human-readable error message |
| `error_code` | `str` | Machine-readable category code (default: `"AGENT_ERROR"`) |

**Example:**

```python
from exceptions import AgentError

try:
    raise AgentError("something went wrong", error_code="AGENT_ERROR")
except AgentError as e:
    print(e.error_code)   # AGENT_ERROR
    print(e.message)      # something went wrong
    print(str(e))         # [AGENT_ERROR] something went wrong
    data = e.to_dict()
    # {'error_code': 'AGENT_ERROR', 'error_type': 'AgentError',
    #  'message': 'something went wrong'}
```

---

## `BridgeError`

Raised when an AI provider bridge call fails.

```python
class BridgeError(AgentError):
    def __init__(self, message: str, error_code: str = "BRIDGE_ERROR",
                 provider: str = None): ...
```

**Additional attribute:** `provider` – name of the failing provider.

**Error codes:** `BRIDGE_CONNECTION`, `BRIDGE_AUTH`, `BRIDGE_MODEL_ERROR`,
`BRIDGE_RATE_LIMIT`, `BRIDGE_TIMEOUT`, `BRIDGE_INVALID_CONFIG`,
`BRIDGE_UNSUPPORTED_PROVIDER`

**Example:**

```python
from exceptions import BridgeError, is_retryable

try:
    response = await bridge.send_task("hello")
except BridgeError as e:
    print(e.provider)         # "openai"
    print(e.error_code)       # "BRIDGE_TIMEOUT"
    if is_retryable(e):
        pass  # retry logic here
```

---

## `SecurityError`

Raised for authentication and authorisation failures.

```python
class SecurityError(AgentError):
    def __init__(self, message: str, error_code: str = "SECURITY_ERROR",
                 auth_type: str = None, details: dict = None): ...
```

**Additional attributes:** `auth_type`, `details`

**Error codes:** `SECURITY_AUTH_FAILED`, `SECURITY_AUTH_MISSING`,
`SECURITY_TOKEN_INVALID`, `SECURITY_TOKEN_EXPIRED`,
`SECURITY_INSUFFICIENT_PERMISSIONS`, `SECURITY_INVALID_SIGNATURE`,
`SECURITY_INVALID_HEADER`

**Example:**

```python
from exceptions import SecurityError

raise SecurityError(
    "Bearer token has expired",
    error_code="SECURITY_TOKEN_EXPIRED",
    auth_type="bearer_token",
    details={"user_id": "u-123"},
)
```

---

## `ConfigurationError`

Raised when the application is misconfigured.

```python
class ConfigurationError(AgentError):
    def __init__(self, message: str, error_code: str = "CONFIG_ERROR",
                 config_key: str = None): ...
```

**Additional attribute:** `config_key` – the configuration key that caused
the error.

**Error codes:** `CONFIG_MISSING`, `CONFIG_INVALID`, `CONFIG_FILE_NOT_FOUND`,
`CONFIG_PARSE_ERROR`

**Example:**

```python
from exceptions import ConfigurationError
import os

api_key = os.getenv("ANTHROPIC_API_KEY")
if not api_key:
    raise ConfigurationError(
        "ANTHROPIC_API_KEY is not set",
        error_code="CONFIG_MISSING",
        config_key="ANTHROPIC_API_KEY",
    )
```

---

## `TimeoutError`

Raised when an operation exceeds its time budget.

```python
class TimeoutError(AgentError):
    def __init__(self, message: str, error_code: str = "TIMEOUT_ERROR",
                 timeout_seconds: float = None): ...
```

**Additional attribute:** `timeout_seconds`

**Error codes:** `TIMEOUT_REQUEST`, `TIMEOUT_OPERATION`, `TIMEOUT_CONNECTION`

This exception is **always retryable** (see `is_retryable`).

**Example:**

```python
from exceptions import TimeoutError, is_retryable

raise TimeoutError(
    "Provider did not respond within 30 s",
    error_code="TIMEOUT_REQUEST",
    timeout_seconds=30.0,
)
# is_retryable(exc) returns True
```

---

## `RateLimitError`

Raised when a provider or internal component rejects a request due to rate
limiting.

```python
class RateLimitError(AgentError):
    def __init__(self, message: str, error_code: str = "RATE_LIMIT_ERROR",
                 retry_after: float = None, provider: str = None): ...
```

**Additional attributes:** `retry_after`, `provider`

**Error codes:** `RATE_LIMIT_EXCEEDED`, `RATE_LIMIT_PROVIDER`,
`RATE_LIMIT_INTERNAL`

This exception is **always retryable**.

**Example:**

```python
import time
from exceptions import RateLimitError

try:
    response = await bridge.send_task("hello")
except RateLimitError as e:
    if e.retry_after:
        time.sleep(e.retry_after)
```

---

## `AuthenticationError`

Raised when a credential presented to the Agent Dashboard itself is invalid.

```python
class AuthenticationError(AgentError):
    def __init__(self, message: str, error_code: str = "AUTH_ERROR",
                 username: str = None): ...
```

**Additional attribute:** `username`

**Error codes:** `AUTH_INVALID_CREDENTIALS`, `AUTH_MISSING_CREDENTIALS`,
`AUTH_TOKEN_EXPIRED`, `AUTH_INSUFFICIENT_SCOPE`

**Example:**

```python
from exceptions import AuthenticationError

raise AuthenticationError(
    "Invalid API key supplied",
    error_code="AUTH_INVALID_CREDENTIALS",
    username="alice@example.com",
)
```

---

## Helper functions

### `is_retryable(exc: BaseException) -> bool`

Returns `True` when the exception represents a transient condition that may
succeed on retry.  `RateLimitError` and `TimeoutError` are always retryable;
other `AgentError` subclasses are retryable when their `error_code` is in the
known retryable set.

```python
from exceptions import is_retryable, BridgeError

exc = BridgeError("timeout", error_code="BRIDGE_TIMEOUT", provider="openai")
print(is_retryable(exc))  # True
```

### `get_error_code(exc: BaseException) -> Optional[str]`

Returns the `error_code` from an `AgentError`, or `None` for standard Python
exceptions.

```python
from exceptions import get_error_code, BridgeError

exc = BridgeError("boom")
print(get_error_code(exc))       # "BRIDGE_ERROR"
print(get_error_code(ValueError("x")))  # None
```

---

## Context manager: `error_handler`

```python
@contextmanager
def error_handler(reraise: bool = True,
                  log_fn: Optional[Callable] = None):
    ...
```

Intercepts `AgentError` exceptions and optionally suppresses them.

**Parameters:**

| Name | Type | Default | Description |
|---|---|---|---|
| `reraise` | `bool` | `True` | Re-raise after calling `log_fn` |
| `log_fn` | `Callable` | `None` | Called with the caught exception |

**Yields:** `_ErrorHandlerContext` with an `exception` attribute.

**Example:**

```python
from exceptions import BridgeError, error_handler

with error_handler(reraise=False) as ctx:
    raise BridgeError("boom", provider="claude")

if ctx.exception:
    print(ctx.exception.error_code)  # BRIDGE_ERROR
```
