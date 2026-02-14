"""
Groq Bridge Module
==================

Unified interface for Groq's LPU-powered inference API.
Supports both the native Groq SDK and OpenAI-compatible mode.

Uses the OpenAI-compatible API at https://api.groq.com/openai/v1,
so the openai Python SDK works directly with a different base_url.

Environment Variables:
    GROQ_API_KEY: API key from https://console.groq.com/keys
    GROQ_MODEL: Default model (default: llama-3.3-70b-versatile)
"""

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum

try:
    from openai import AsyncOpenAI, OpenAI
except ImportError:
    AsyncOpenAI = None
    OpenAI = None

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class GroqModel(StrEnum):
    """Available Groq models organized by category."""

    # Production models
    LLAMA_3_3_70B = "llama-3.3-70b-versatile"
    LLAMA_3_1_8B = "llama-3.1-8b-instant"
    MIXTRAL_8X7B = "mixtral-8x7b-32768"
    GEMMA2_9B = "gemma2-9b-it"

    @classmethod
    def from_string(cls, value: str) -> "GroqModel":
        """Resolve a model string to a GroqModel enum, supporting aliases."""
        mapping = {m.value: m for m in cls}
        aliases = {
            "llama-70b": cls.LLAMA_3_3_70B,
            "llama-8b": cls.LLAMA_3_1_8B,
            "mixtral": cls.MIXTRAL_8X7B,
            "gemma": cls.GEMMA2_9B,
        }
        key = value.lower().strip()
        return mapping.get(key, aliases.get(key, cls.LLAMA_3_3_70B))


# Default model
DEFAULT_MODEL = GroqModel.LLAMA_3_3_70B


@dataclass
class GroqMessage:
    """A message in a Groq conversation."""

    role: str
    content: str


@dataclass
class GroqSession:
    """Manages a conversation session with Groq."""

    model: GroqModel
    messages: list[GroqMessage] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 4096

    def add_message(self, role: str, content: str) -> None:
        self.messages.append(GroqMessage(role=role, content=content))

    def to_openai_messages(self) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in self.messages]


@dataclass
class GroqResponse:
    """Response from the Groq API."""

    content: str
    model: str
    usage: dict | None = None
    finish_reason: str | None = None


class GroqClient:
    """Groq API client using the OpenAI-compatible endpoint."""

    def __init__(self, api_key: str | None = None) -> None:
        if OpenAI is None or AsyncOpenAI is None:
            raise ImportError("openai package not installed. Run: pip install openai")
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY not set. Get a free key from: https://console.groq.com/keys"
            )
        self._client = OpenAI(api_key=self.api_key, base_url=GROQ_BASE_URL)
        self._async_client = AsyncOpenAI(api_key=self.api_key, base_url=GROQ_BASE_URL)

    def send_message(self, session: GroqSession, message: str) -> GroqResponse:
        session.add_message("user", message)
        response = self._client.chat.completions.create(
            model=session.model.value,
            messages=session.to_openai_messages(),
            temperature=session.temperature,
            max_tokens=session.max_tokens,
            stream=False,
        )
        content = response.choices[0].message.content or ""
        session.add_message("assistant", content)
        return GroqResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            finish_reason=response.choices[0].finish_reason,
        )

    async def send_message_async(self, session: GroqSession, message: str) -> GroqResponse:
        session.add_message("user", message)
        response = await self._async_client.chat.completions.create(
            model=session.model.value,
            messages=session.to_openai_messages(),
            temperature=session.temperature,
            max_tokens=session.max_tokens,
            stream=False,
        )
        content = response.choices[0].message.content or ""
        session.add_message("assistant", content)
        return GroqResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            finish_reason=response.choices[0].finish_reason,
        )

    async def stream_response(self, session: GroqSession, message: str) -> AsyncIterator[str]:
        session.add_message("user", message)
        stream = await self._async_client.chat.completions.create(
            model=session.model.value,
            messages=session.to_openai_messages(),
            stream=True,
        )
        full_content = ""
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                token = chunk.choices[0].delta.content
                full_content += token
                yield token
        session.add_message("assistant", full_content)


class GroqBridge:
    """Unified bridge for Groq access."""

    def __init__(self, client: GroqClient) -> None:
        self._client = client

    @classmethod
    def from_env(cls) -> "GroqBridge":
        return cls(client=GroqClient())

    def create_session(
        self,
        model: str | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> GroqSession:
        model_str = model or os.environ.get("GROQ_MODEL", DEFAULT_MODEL.value)
        groq_model = GroqModel.from_string(model_str)
        session = GroqSession(
            model=groq_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if system_prompt:
            session.add_message("system", system_prompt)
        return session

    def send_message(self, session: GroqSession, message: str) -> GroqResponse:
        return self._client.send_message(session, message)

    async def send_message_async(self, session: GroqSession, message: str) -> GroqResponse:
        return await self._client.send_message_async(session, message)

    async def stream_response(self, session: GroqSession, message: str) -> AsyncIterator[str]:
        async for token in self._client.stream_response(session, message):
            yield token

    def get_auth_info(self) -> dict[str, str]:
        key = os.environ.get("GROQ_API_KEY", "")
        return {
            "auth_type": "api-key",
            "model_default": os.environ.get("GROQ_MODEL", DEFAULT_MODEL.value),
            "api_key_set": "yes" if key else "no",
            "api_key_prefix": key[:8] + "..." if len(key) > 8 else "(short)",
            "cost_note": "Free tier available. Ultra-fast LPU inference.",
        }


def get_available_models() -> list[str]:
    return [m.value for m in GroqModel]


def print_auth_status() -> None:
    try:
        bridge = GroqBridge.from_env()
        info = bridge.get_auth_info()
        print("Groq Authentication Status:")
        for key, value in info.items():
            print(f"  {key}: {value}")
    except (ValueError, ImportError) as e:
        print(f"Groq authentication error: {e}")
