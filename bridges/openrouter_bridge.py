"""
OpenRouter Bridge Module
========================

Unified interface for OpenRouter's multi-model API gateway.
Uses the OpenAI-compatible API at https://openrouter.ai/api/v1,
so the openai Python SDK works directly with a different base_url.

Supports both free-tier models (e.g., deepseek/deepseek-r1:free,
meta-llama/llama-3.3-70b-instruct:free) and paid models.

Environment Variables:
    OPENROUTER_API_KEY: API key from https://openrouter.ai/keys
    OPENROUTER_MODEL: Default model (default: openrouter/free)
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

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterModel(StrEnum):
    """Available OpenRouter free-tier models."""

    # Universal free router
    FREE_ROUTER = "openrouter/free"

    # Specific free models
    DEEPSEEK_R1_FREE = "deepseek/deepseek-r1:free"
    LLAMA_3_3_70B_FREE = "meta-llama/llama-3.3-70b-instruct:free"
    GEMMA_3_27B_FREE = "google/gemma-3-27b-it:free"
    MISTRAL_SMALL_FREE = "mistral/mistral-small-3.1-24b:free"

    @classmethod
    def from_string(cls, value: str) -> "OpenRouterModel":
        """Resolve a model string to an OpenRouterModel enum, supporting aliases."""
        mapping = {m.value: m for m in cls}
        aliases = {
            "free": cls.FREE_ROUTER,
            "deepseek": cls.DEEPSEEK_R1_FREE,
            "deepseek-r1": cls.DEEPSEEK_R1_FREE,
            "llama": cls.LLAMA_3_3_70B_FREE,
            "llama-70b": cls.LLAMA_3_3_70B_FREE,
            "gemma": cls.GEMMA_3_27B_FREE,
            "gemma-27b": cls.GEMMA_3_27B_FREE,
            "mistral": cls.MISTRAL_SMALL_FREE,
            "mistral-small": cls.MISTRAL_SMALL_FREE,
        }
        key = value.lower().strip()
        return mapping.get(key, aliases.get(key, cls.FREE_ROUTER))


# Default model
DEFAULT_MODEL = OpenRouterModel.FREE_ROUTER


@dataclass
class OpenRouterMessage:
    """A message in an OpenRouter conversation."""

    role: str
    content: str


@dataclass
class OpenRouterSession:
    """Manages a conversation session with OpenRouter."""

    model: OpenRouterModel
    messages: list[OpenRouterMessage] = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: int = 4096

    def add_message(self, role: str, content: str) -> None:
        self.messages.append(OpenRouterMessage(role=role, content=content))

    def to_openai_messages(self) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in self.messages]


@dataclass
class OpenRouterResponse:
    """Response from the OpenRouter API."""

    content: str
    model: str
    usage: dict | None = None
    finish_reason: str | None = None


class OpenRouterClient:
    """OpenRouter API client using the OpenAI-compatible endpoint."""

    def __init__(self, api_key: str | None = None) -> None:
        if OpenAI is None or AsyncOpenAI is None:
            raise ImportError("openai package not installed. Run: pip install openai")
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY not set. Get a key from: https://openrouter.ai/keys"
            )
        self._client = OpenAI(api_key=self.api_key, base_url=OPENROUTER_BASE_URL)
        self._async_client = AsyncOpenAI(api_key=self.api_key, base_url=OPENROUTER_BASE_URL)

    def send_message(self, session: OpenRouterSession, message: str) -> OpenRouterResponse:
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
        return OpenRouterResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            finish_reason=response.choices[0].finish_reason,
        )

    async def send_message_async(
        self, session: OpenRouterSession, message: str
    ) -> OpenRouterResponse:
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
        return OpenRouterResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            finish_reason=response.choices[0].finish_reason,
        )

    async def stream_response(
        self, session: OpenRouterSession, message: str
    ) -> AsyncIterator[str]:
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


class OpenRouterBridge:
    """Unified bridge for OpenRouter access."""

    def __init__(self, client: OpenRouterClient) -> None:
        self._client = client

    @classmethod
    def from_env(cls) -> "OpenRouterBridge":
        return cls(client=OpenRouterClient())

    def create_session(
        self,
        model: str | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> OpenRouterSession:
        model_str = model or os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL.value)
        or_model = OpenRouterModel.from_string(model_str)
        session = OpenRouterSession(
            model=or_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if system_prompt:
            session.add_message("system", system_prompt)
        return session

    def send_message(self, session: OpenRouterSession, message: str) -> OpenRouterResponse:
        return self._client.send_message(session, message)

    async def send_message_async(
        self, session: OpenRouterSession, message: str
    ) -> OpenRouterResponse:
        return await self._client.send_message_async(session, message)

    async def stream_response(
        self, session: OpenRouterSession, message: str
    ) -> AsyncIterator[str]:
        async for token in self._client.stream_response(session, message):
            yield token

    def get_auth_info(self) -> dict[str, str]:
        key = os.environ.get("OPENROUTER_API_KEY", "")
        return {
            "auth_type": "api-key",
            "model_default": os.environ.get("OPENROUTER_MODEL", DEFAULT_MODEL.value),
            "api_key_set": "yes" if key else "no",
            "api_key_prefix": key[:12] + "..." if len(key) > 12 else "(short)",
            "cost_note": "Free tier: 50 req/day (1000/day with $10 credit purchase).",
        }


def get_available_models() -> list[str]:
    return [m.value for m in OpenRouterModel]


def print_auth_status() -> None:
    try:
        bridge = OpenRouterBridge.from_env()
        info = bridge.get_auth_info()
        print("OpenRouter Authentication Status:")
        for key, value in info.items():
            print(f"  {key}: {value}")
    except (ValueError, ImportError) as e:
        print(f"OpenRouter authentication error: {e}")
