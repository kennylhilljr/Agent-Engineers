# AI Provider Bridge Interface Documentation

This document specifies the standard interface for AI provider bridges and provides implementation examples.

## Table of Contents

1. [Overview](#overview)
2. [Bridge Interface Specification](#bridge-interface-specification)
3. [Implementation Guide](#implementation-guide)
4. [Existing Bridges](#existing-bridges)
5. [Creating a New Bridge](#creating-a-new-bridge)
6. [Testing Bridges](#testing-bridges)

## Overview

AI provider bridges enable the Agent Dashboard to integrate with multiple AI providers (OpenAI, Google Gemini, Groq, etc.) through a unified interface. Each bridge translates between the provider's API and the common bridge interface.

### Architecture

```
Orchestrator
    ↓
Bridge Interface (Common API)
    ↓
    ├── OpenAI Bridge → OpenAI API
    ├── Gemini Bridge → Google Gemini API
    ├── Groq Bridge → Groq API
    ├── KIMI Bridge → Moonshot API
    └── Windsurf Bridge → Windsurf CLI/Docker
```

### Design Principles

1. **Consistent Interface**: All bridges expose the same core methods
2. **Provider Flexibility**: Each bridge handles provider-specific quirks
3. **Async Support**: Bridges support both sync and async operations
4. **Error Handling**: Consistent error types across providers
5. **Configuration**: Environment-based configuration

## Bridge Interface Specification

### Required Classes

#### 1. Session Class

Manages conversation state with the AI provider.

```python
from dataclasses import dataclass, field

@dataclass
class ChatMessage:
    """A single message in a conversation.

    Attributes:
        role: Message role (system, user, assistant)
        content: Message text content
    """
    role: str
    content: str

@dataclass
class ChatSession:
    """A conversation session with an AI provider.

    Attributes:
        model: Model identifier (e.g., "gpt-4o", "gemini-2.5-flash")
        messages: Conversation history
        session_id: Optional provider-specific session ID

    Example:
        >>> session = ChatSession(model="gpt-4o")
        >>> session.add_message("user", "Hello!")
        >>> session.add_message("assistant", "Hi there!")
    """
    model: str
    messages: list[ChatMessage] = field(default_factory=list)
    session_id: str | None = None

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation.

        Args:
            role: Message role (system, user, assistant)
            content: Message text
        """
        self.messages.append(ChatMessage(role=role, content=content))

    def to_provider_format(self) -> list[dict]:
        """Convert messages to provider-specific format.

        Returns:
            List of message dictionaries for the provider API
        """
        return [{"role": m.role, "content": m.content} for m in self.messages]
```

#### 2. Response Class

Represents a response from the AI provider.

```python
from dataclasses import dataclass

@dataclass
class ChatResponse:
    """Response from an AI provider.

    Attributes:
        content: Response text content
        model: Model that generated the response
        usage: Token usage statistics (provider-specific)
        finish_reason: Reason the model stopped (stop, length, etc.)

    Example:
        >>> response = ChatResponse(
        ...     content="Hello! How can I help?",
        ...     model="gpt-4o",
        ...     usage={"prompt_tokens": 10, "completion_tokens": 5},
        ...     finish_reason="stop"
        ... )
    """
    content: str
    model: str
    usage: dict | None = None
    finish_reason: str | None = None
```

#### 3. Bridge Class

Main bridge interface.

```python
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

class AIBridge(ABC):
    """Abstract base class for AI provider bridges.

    Subclasses must implement:
    - create_session()
    - send_message()
    - send_message_async()
    - stream_response() (optional but recommended)
    """

    @classmethod
    @abstractmethod
    def from_env(cls) -> "AIBridge":
        """Create bridge from environment variables.

        Returns:
            Configured bridge instance

        Raises:
            ValueError: If required environment variables are missing
            ImportError: If required packages are not installed

        Example:
            >>> bridge = MyBridge.from_env()
        """
        pass

    @abstractmethod
    def create_session(
        self,
        model: str | None = None,
        system_prompt: str | None = None
    ) -> ChatSession:
        """Create a new chat session.

        Args:
            model: Model identifier (uses default if None)
            system_prompt: Optional system message to start conversation

        Returns:
            New ChatSession instance

        Example:
            >>> session = bridge.create_session(
            ...     model="gpt-4o",
            ...     system_prompt="You are a helpful assistant"
            ... )
        """
        pass

    @abstractmethod
    def send_message(
        self,
        session: ChatSession,
        message: str
    ) -> ChatResponse:
        """Send a message synchronously.

        Args:
            session: Active chat session
            message: User message to send

        Returns:
            ChatResponse with model's reply

        Raises:
            ConnectionError: If provider API is unreachable
            ValueError: If request is invalid

        Example:
            >>> response = bridge.send_message(session, "Hello!")
            >>> print(response.content)
        """
        pass

    @abstractmethod
    async def send_message_async(
        self,
        session: ChatSession,
        message: str
    ) -> ChatResponse:
        """Send a message asynchronously.

        Args:
            session: Active chat session
            message: User message to send

        Returns:
            ChatResponse with model's reply

        Raises:
            ConnectionError: If provider API is unreachable
            ValueError: If request is invalid

        Example:
            >>> response = await bridge.send_message_async(session, "Hello!")
        """
        pass

    async def stream_response(
        self,
        session: ChatSession,
        message: str
    ) -> AsyncIterator[str]:
        """Stream response tokens as they're generated.

        Optional but recommended for better UX.

        Args:
            session: Active chat session
            message: User message to send

        Yields:
            Response text tokens as they arrive

        Example:
            >>> async for token in bridge.stream_response(session, "Count to 10"):
            ...     print(token, end="", flush=True)
        """
        # Default implementation: yield full response at once
        response = await self.send_message_async(session, message)
        yield response.content

    def get_auth_info(self) -> dict[str, str]:
        """Get authentication configuration info.

        Returns:
            Dictionary with auth status and configuration

        Example:
            >>> info = bridge.get_auth_info()
            >>> print(info["auth_type"])
            >>> print(info["api_key_set"])
        """
        return {
            "auth_type": "unknown",
            "status": "not_configured"
        }
```

## Implementation Guide

### Step 1: Create Bridge Module

Create a new file in `bridges/`:

```python
# bridges/my_provider_bridge.py
"""
My Provider Bridge Module
=========================
Connects to MyProvider AI service.

Environment Variables:
    MY_PROVIDER_API_KEY: API key for MyProvider
    MY_PROVIDER_MODEL: Default model (default: my-model-1)
"""

import os
from dataclasses import dataclass, field
from collections.abc import AsyncIterator

# Import provider SDK
try:
    from my_provider import Client, AsyncClient
except ImportError:
    Client = None
    AsyncClient = None
```

### Step 2: Implement Session and Response

```python
@dataclass
class ChatMessage:
    role: str
    content: str

@dataclass
class ChatSession:
    model: str
    messages: list[ChatMessage] = field(default_factory=list)
    session_id: str | None = None

    def add_message(self, role: str, content: str) -> None:
        self.messages.append(ChatMessage(role=role, content=content))

    def to_provider_messages(self) -> list[dict]:
        """Convert to provider-specific format."""
        return [
            {
                "role": m.role,
                "content": m.content
            }
            for m in self.messages
        ]

@dataclass
class ChatResponse:
    content: str
    model: str
    usage: dict | None = None
    finish_reason: str | None = None
```

### Step 3: Implement Bridge Class

```python
class MyProviderBridge:
    """Bridge for MyProvider AI service."""

    def __init__(self, api_key: str):
        """Initialize bridge.

        Args:
            api_key: MyProvider API key

        Raises:
            ImportError: If my_provider package not installed
        """
        if Client is None or AsyncClient is None:
            raise ImportError(
                "my_provider package not installed. "
                "Run: pip install my-provider-sdk"
            )

        self.api_key = api_key
        self._client = Client(api_key=api_key)
        self._async_client = AsyncClient(api_key=api_key)

    @classmethod
    def from_env(cls) -> "MyProviderBridge":
        """Create bridge from environment variables.

        Returns:
            Configured MyProviderBridge

        Raises:
            ValueError: If MY_PROVIDER_API_KEY not set

        Example:
            >>> bridge = MyProviderBridge.from_env()
        """
        api_key = os.environ.get("MY_PROVIDER_API_KEY", "")
        if not api_key:
            raise ValueError(
                "MY_PROVIDER_API_KEY not set. "
                "Get your key from https://myprovider.com/keys"
            )
        return cls(api_key=api_key)

    def create_session(
        self,
        model: str | None = None,
        system_prompt: str | None = None
    ) -> ChatSession:
        """Create a new chat session.

        Args:
            model: Model name (uses MY_PROVIDER_MODEL if None)
            system_prompt: Optional system message

        Returns:
            New ChatSession

        Example:
            >>> session = bridge.create_session(
            ...     model="my-model-1",
            ...     system_prompt="You are helpful"
            ... )
        """
        model_name = model or os.environ.get(
            "MY_PROVIDER_MODEL",
            "my-model-1"
        )
        session = ChatSession(model=model_name)

        if system_prompt:
            session.add_message("system", system_prompt)

        return session

    def send_message(
        self,
        session: ChatSession,
        message: str
    ) -> ChatResponse:
        """Send a message synchronously.

        Args:
            session: Active chat session
            message: User message

        Returns:
            ChatResponse with model reply

        Example:
            >>> response = bridge.send_message(session, "Hello!")
            >>> print(response.content)
        """
        session.add_message("user", message)

        # Call provider API
        response = self._client.chat.create(
            model=session.model,
            messages=session.to_provider_messages()
        )

        # Extract response
        content = response.choices[0].message.content
        session.add_message("assistant", content)

        return ChatResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            finish_reason=response.choices[0].finish_reason
        )

    async def send_message_async(
        self,
        session: ChatSession,
        message: str
    ) -> ChatResponse:
        """Send a message asynchronously.

        Args:
            session: Active chat session
            message: User message

        Returns:
            ChatResponse with model reply

        Example:
            >>> response = await bridge.send_message_async(session, "Hi!")
        """
        session.add_message("user", message)

        # Call provider API asynchronously
        response = await self._async_client.chat.create(
            model=session.model,
            messages=session.to_provider_messages()
        )

        content = response.choices[0].message.content
        session.add_message("assistant", content)

        return ChatResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            finish_reason=response.choices[0].finish_reason
        )

    async def stream_response(
        self,
        session: ChatSession,
        message: str
    ) -> AsyncIterator[str]:
        """Stream response tokens.

        Args:
            session: Active chat session
            message: User message

        Yields:
            Response tokens as they arrive

        Example:
            >>> async for token in bridge.stream_response(session, "Hi!"):
            ...     print(token, end="", flush=True)
        """
        session.add_message("user", message)

        stream = await self._async_client.chat.create(
            model=session.model,
            messages=session.to_provider_messages(),
            stream=True
        )

        full_content = ""
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                full_content += token
                yield token

        session.add_message("assistant", full_content)

    def get_auth_info(self) -> dict[str, str]:
        """Get authentication info.

        Returns:
            Auth configuration details

        Example:
            >>> info = bridge.get_auth_info()
            >>> print(info)
        """
        return {
            "auth_type": "api_key",
            "api_key_set": "yes" if self.api_key else "no",
            "api_key_prefix": self.api_key[:8] + "..." if len(self.api_key) > 8 else "",
            "default_model": os.environ.get("MY_PROVIDER_MODEL", "my-model-1")
        }
```

### Step 4: Create CLI Tool

```python
# scripts/my_provider_cli.py
"""
MyProvider CLI Tool
===================
Standalone CLI for interacting with MyProvider.
"""

import asyncio
import argparse
from bridges.my_provider_bridge import MyProviderBridge

async def main():
    parser = argparse.ArgumentParser(description="MyProvider CLI")
    parser.add_argument("--query", help="Single query mode")
    parser.add_argument("--model", help="Model to use")
    parser.add_argument("--stream", action="store_true", help="Stream response")
    parser.add_argument("--status", action="store_true", help="Show auth status")
    args = parser.parse_args()

    try:
        bridge = MyProviderBridge.from_env()

        if args.status:
            info = bridge.get_auth_info()
            print("MyProvider Status:")
            for key, value in info.items():
                print(f"  {key}: {value}")
            return

        session = bridge.create_session(model=args.model)

        if args.query:
            # Single query
            if args.stream:
                async for token in bridge.stream_response(session, args.query):
                    print(token, end="", flush=True)
                print()
            else:
                response = await bridge.send_message_async(session, args.query)
                print(response.content)
        else:
            # Interactive REPL
            print("MyProvider CLI (type 'exit' to quit)")
            while True:
                query = input("\n> ")
                if query.lower() in ("exit", "quit"):
                    break

                if args.stream:
                    async for token in bridge.stream_response(session, query):
                        print(token, end="", flush=True)
                    print()
                else:
                    response = await bridge.send_message_async(session, query)
                    print(response.content)

    except Exception as e:
        print(f"Error: {e}")
        return 1

if __name__ == "__main__":
    asyncio.run(main())
```

## Existing Bridges

### OpenAI Bridge

Located in `bridges/openai_bridge.py`

**Features:**
- Two auth modes: Codex OAuth and Session Token
- Models: GPT-4o, o1, o3-mini, o4-mini
- Full streaming support
- Token usage tracking

**Example:**
```python
from bridges.openai_bridge import OpenAIBridge

bridge = OpenAIBridge.from_env()
session = bridge.create_session(model="gpt-4o")
response = bridge.send_message(session, "Hello!")
```

### Gemini Bridge

Located in `bridges/gemini_bridge.py`

**Features:**
- Three auth modes: CLI OAuth, API Key, Vertex AI
- Models: Gemini 2.5 Flash/Pro, 2.0 Flash
- Large context windows (1M tokens)
- Search grounding support

**Example:**
```python
from bridges.gemini_bridge import GeminiBridge

bridge = GeminiBridge.from_env()
session = bridge.create_session(model="gemini-2.5-flash")
response = bridge.send_message(session, "Analyze this...")
```

### Groq Bridge

Located in `bridges/groq_bridge.py`

**Features:**
- Ultra-fast LPU inference
- Open-source models (Llama, Mixtral, Gemma)
- OpenAI-compatible API
- Generous free tier

**Example:**
```python
from bridges.groq_bridge import GroqBridge

bridge = GroqBridge.from_env()
session = bridge.create_session(model="llama-3.3-70b-versatile")
response = bridge.send_message(session, "Quick task")
```

## Creating a New Bridge

### Checklist

- [ ] Create bridge module in `bridges/`
- [ ] Implement required classes (Session, Response, Bridge)
- [ ] Add environment variable configuration
- [ ] Create CLI tool in `scripts/`
- [ ] Write unit tests in `tests/`
- [ ] Add integration tests
- [ ] Document in this file
- [ ] Add to main README.md
- [ ] Update requirements.txt

### Template

Use the implementation guide above as a template. Key points:

1. **Consistent naming**: Use `{Provider}Bridge` class name
2. **Error handling**: Provide helpful error messages
3. **Environment config**: Document all env vars
4. **Type hints**: Use comprehensive type annotations
5. **Docstrings**: Include examples in all docstrings
6. **Async support**: Implement both sync and async methods

## Testing Bridges

### Unit Tests

```python
# tests/test_my_provider_bridge.py
import pytest
from bridges.my_provider_bridge import MyProviderBridge

def test_create_session():
    """Test session creation."""
    bridge = MyProviderBridge(api_key="test-key")
    session = bridge.create_session(model="my-model-1")

    assert session.model == "my-model-1"
    assert len(session.messages) == 0

def test_create_session_with_system_prompt():
    """Test session with system prompt."""
    bridge = MyProviderBridge(api_key="test-key")
    session = bridge.create_session(
        system_prompt="You are helpful"
    )

    assert len(session.messages) == 1
    assert session.messages[0].role == "system"

@pytest.mark.asyncio
async def test_send_message_async():
    """Test async message sending."""
    bridge = MyProviderBridge.from_env()
    session = bridge.create_session()

    response = await bridge.send_message_async(session, "Test")

    assert response.content
    assert response.model
    assert len(session.messages) == 2  # user + assistant
```

### Integration Tests

```python
# tests/test_my_provider_integration.py
import pytest
from bridges.my_provider_bridge import MyProviderBridge

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_conversation():
    """Test a full conversation flow."""
    bridge = MyProviderBridge.from_env()
    session = bridge.create_session(
        system_prompt="You are a math tutor"
    )

    # First message
    response1 = await bridge.send_message_async(
        session,
        "What is 2+2?"
    )
    assert "4" in response1.content

    # Follow-up
    response2 = await bridge.send_message_async(
        session,
        "And what is that plus 3?"
    )
    assert "7" in response2.content

@pytest.mark.integration
@pytest.mark.asyncio
async def test_streaming():
    """Test streaming response."""
    bridge = MyProviderBridge.from_env()
    session = bridge.create_session()

    tokens = []
    async for token in bridge.stream_response(session, "Count to 5"):
        tokens.append(token)

    full_response = "".join(tokens)
    assert full_response
    assert len(tokens) > 1  # Should stream multiple tokens
```

## Best Practices

1. **Error Messages**: Provide actionable error messages
2. **Rate Limiting**: Handle provider rate limits gracefully
3. **Retries**: Implement exponential backoff for transient errors
4. **Logging**: Log API calls for debugging
5. **Caching**: Cache authentication tokens when possible
6. **Testing**: Test both happy path and error cases
7. **Documentation**: Keep docstrings updated with examples

## Troubleshooting

### Common Issues

**ImportError: Package not installed**
```bash
pip install <provider-sdk>
```

**ValueError: API key not set**
```bash
export MY_PROVIDER_API_KEY=your-key-here
```

**ConnectionError: API unreachable**
- Check internet connection
- Verify API endpoint URL
- Check provider status page

**Rate limit errors**
- Add exponential backoff
- Use provider's rate limit headers
- Implement request queuing

## Additional Resources

- [Developer Guide](DEVELOPER_GUIDE.md)
- [API Documentation](api/index.html)
- [Provider Integration Examples](../examples/)
