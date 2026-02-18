# bridges – AI Provider Bridge Module

**Source:** `bridges/base_bridge.py`
**Package:** `bridges/`

---

## Overview

The `bridges` package provides a uniform interface for communicating with
multiple AI providers. Every concrete bridge inherits from `BaseBridge` and
returns `BridgeResponse` objects so that callers never need to know which
provider is in use.

Available concrete bridges:

| Class | Provider | Source file |
|---|---|---|
| `OpenAIBridge` | OpenAI / ChatGPT | `bridges/openai_bridge.py` |
| `GeminiBridge` | Google Gemini | `bridges/gemini_bridge.py` |
| `GroqBridge` | Groq | `bridges/groq_bridge.py` |
| `KimiBridge` | Moonshot AI (Kimi) | `bridges/kimi_bridge.py` |
| `WindsurfBridge` | Windsurf IDE | `bridges/windsurf_bridge.py` |

---

## BridgeResponse

```python
@dataclass
class BridgeResponse:
    content: str
    model: str
    provider: str
    tokens_used: Optional[int] = None
    error: Optional[str] = None
    success: bool = True
```

Standard response returned by every `send_task` call.

| Field | Type | Description |
|---|---|---|
| `content` | `str` | Text returned by the AI provider |
| `model` | `str` | Model identifier, e.g. `"gpt-4o"` |
| `provider` | `str` | Provider name, e.g. `"openai"` |
| `tokens_used` | `int \| None` | Token count reported by the provider |
| `error` | `str \| None` | Error message on failure; `None` on success |
| `success` | `bool` | `True` when the call succeeded |

**Example:**

```python
response = BridgeResponse(
    content="The answer is 42.",
    model="claude-opus-4-6",
    provider="anthropic",
    tokens_used=150,
)
assert response.success is True
assert response.error is None
```

---

## BaseBridge

```python
class BaseBridge(ABC):
    ...
```

Abstract base class. Subclass it and implement the three abstract members.

### Abstract members

#### `provider_name` (property)

```python
@property
@abstractmethod
def provider_name(self) -> str: ...
```

Returns a lowercase string identifier for the provider (e.g. `"openai"`).

#### `send_task`

```python
@abstractmethod
async def send_task(self, task: str, **kwargs) -> BridgeResponse: ...
```

Send a prompt to the provider and return a `BridgeResponse`.

**Parameters:**

| Name | Type | Description |
|---|---|---|
| `task` | `str` | Prompt or task to send |
| `**kwargs` | | Provider-specific options (`model`, `temperature`, etc.) |

**Returns:** `BridgeResponse`

**Raises:** `~exceptions.BridgeError` on non-retryable provider errors.

**Example:**

```python
response = await bridge.send_task(
    "Summarise this PR description in one sentence.",
    model="gpt-4o",
    temperature=0.2,
)
print(response.content)
```

#### `get_auth_info`

```python
@abstractmethod
def get_auth_info(self) -> dict[str, str]: ...
```

Returns a dict of (possibly redacted) authentication fields for diagnostics.

**Example:**

```python
info = bridge.get_auth_info()
# {"api_key": "sk-...1234", "org_id": "org-abc"}
```

### Concrete methods

#### `validate_response`

```python
def validate_response(self, response: BridgeResponse) -> bool: ...
```

Returns `True` when `response.success` is `True` **and** `response.content`
is non-empty. Can be overridden by subclasses.

**Example:**

```python
response = await bridge.send_task("Hello")
if not bridge.validate_response(response):
    raise RuntimeError(f"Bad response: {response.error}")
```

---

## Implementing a custom bridge

```python
from bridges.base_bridge import BaseBridge, BridgeResponse
import asyncio

class MyBridge(BaseBridge):
    @property
    def provider_name(self) -> str:
        return "my_provider"

    async def send_task(self, task: str, **kwargs) -> BridgeResponse:
        # Call your provider API here
        return BridgeResponse(
            content="Hello from my provider",
            model="my-model-v1",
            provider=self.provider_name,
            tokens_used=42,
        )

    def get_auth_info(self) -> dict[str, str]:
        return {"api_key": "sk-..."}

bridge = MyBridge()
print(bridge)  # MyBridge(provider=my_provider)
response = asyncio.run(bridge.send_task("Write a haiku about Python"))
print(response.content)
```
