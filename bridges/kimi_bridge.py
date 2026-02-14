"""
KIMI (Moonshot AI) Bridge Module
==================================

Wraps Moonshot AI's KIMI interaction to provide a unified interface for the
multi-AI orchestrator. KIMI is known for ultra-long context windows (up to 2M
tokens) and strong Chinese/English bilingual capabilities.

Uses the OpenAI-compatible API at https://api.moonshot.cn/v1, so the openai
Python SDK works directly with a different base_url.

Environment Variables:
    KIMI_API_KEY or MOONSHOT_API_KEY: API key from https://platform.moonshot.cn/console/api-keys
    KIMI_MODEL: Default model (default: moonshot-v1-auto)
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

KIMI_BASE_URL = "https://api.moonshot.cn/v1"


class KimiModel(StrEnum):
    MOONSHOT_V1_AUTO = "moonshot-v1-auto"
    MOONSHOT_V1_8K = "moonshot-v1-8k"
    MOONSHOT_V1_32K = "moonshot-v1-32k"
    MOONSHOT_V1_128K = "moonshot-v1-128k"
    KIMI_K2 = "kimi-k2"

    @classmethod
    def from_string(cls, value: str) -> "KimiModel":
        mapping = {m.value: m for m in cls}
        aliases = {
            "auto": cls.MOONSHOT_V1_AUTO,
            "8k": cls.MOONSHOT_V1_8K,
            "32k": cls.MOONSHOT_V1_32K,
            "128k": cls.MOONSHOT_V1_128K,
            "k2": cls.KIMI_K2,
        }
        key = value.lower().strip()
        return mapping.get(key, aliases.get(key, cls.MOONSHOT_V1_AUTO))


@dataclass
class KimiMessage:
    role: str
    content: str


@dataclass
class KimiSession:
    model: KimiModel
    messages: list[KimiMessage] = field(default_factory=list)

    def add_message(self, role: str, content: str) -> None:
        self.messages.append(KimiMessage(role=role, content=content))

    def to_openai_messages(self) -> list[dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in self.messages]


@dataclass
class KimiResponse:
    content: str
    model: str
    usage: dict | None = None
    finish_reason: str | None = None


class KimiClient:
    """KIMI API client using Moonshot's OpenAI-compatible endpoint."""

    def __init__(self, api_key: str | None = None) -> None:
        if OpenAI is None or AsyncOpenAI is None:
            raise ImportError("openai package not installed. Run: pip install openai")
        self.api_key = (
            api_key or os.environ.get("KIMI_API_KEY", "") or os.environ.get("MOONSHOT_API_KEY", "")
        )
        if not self.api_key:
            raise ValueError(
                "KIMI_API_KEY or MOONSHOT_API_KEY not set. "
                "Get a key from: https://platform.moonshot.cn/console/api-keys"
            )
        self._client = OpenAI(api_key=self.api_key, base_url=KIMI_BASE_URL)
        self._async_client = AsyncOpenAI(api_key=self.api_key, base_url=KIMI_BASE_URL)

    def send_message(self, session: KimiSession, message: str) -> KimiResponse:
        session.add_message("user", message)
        response = self._client.chat.completions.create(
            model=session.model.value,
            messages=session.to_openai_messages(),
            stream=False,
        )
        content = response.choices[0].message.content or ""
        session.add_message("assistant", content)
        return KimiResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            finish_reason=response.choices[0].finish_reason,
        )

    async def send_message_async(self, session: KimiSession, message: str) -> KimiResponse:
        session.add_message("user", message)
        response = await self._async_client.chat.completions.create(
            model=session.model.value,
            messages=session.to_openai_messages(),
            stream=False,
        )
        content = response.choices[0].message.content or ""
        session.add_message("assistant", content)
        return KimiResponse(
            content=content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            finish_reason=response.choices[0].finish_reason,
        )

    async def stream_response(self, session: KimiSession, message: str) -> AsyncIterator[str]:
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


class KimiBridge:
    """Unified bridge for KIMI / Moonshot AI access."""

    def __init__(self, client: KimiClient) -> None:
        self._client = client

    @classmethod
    def from_env(cls) -> "KimiBridge":
        return cls(client=KimiClient())

    def create_session(
        self, model: str | None = None, system_prompt: str | None = None
    ) -> KimiSession:
        model_str = model or os.environ.get("KIMI_MODEL", "moonshot-v1-auto")
        kimi_model = KimiModel.from_string(model_str)
        session = KimiSession(model=kimi_model)
        if system_prompt:
            session.add_message("system", system_prompt)
        return session

    def send_message(self, session: KimiSession, message: str) -> KimiResponse:
        return self._client.send_message(session, message)

    async def send_message_async(self, session: KimiSession, message: str) -> KimiResponse:
        return await self._client.send_message_async(session, message)

    async def stream_response(self, session: KimiSession, message: str) -> AsyncIterator[str]:
        async for token in self._client.stream_response(session, message):
            yield token

    def get_auth_info(self) -> dict[str, str]:
        key = os.environ.get("KIMI_API_KEY", "") or os.environ.get("MOONSHOT_API_KEY", "")
        return {
            "auth_type": "api-key",
            "model_default": os.environ.get("KIMI_MODEL", "moonshot-v1-auto"),
            "api_key_set": "yes" if key else "no",
            "api_key_prefix": key[:8] + "..." if len(key) > 8 else "(short)",
            "cost_note": "Pay-as-you-go. Up to 2M token context window.",
        }


def get_available_models() -> list[str]:
    return [m.value for m in KimiModel]


def print_auth_status() -> None:
    try:
        bridge = KimiBridge.from_env()
        info = bridge.get_auth_info()
        print("KIMI Authentication Status:")
        for key, value in info.items():
            print(f"  {key}: {value}")
    except (ValueError, ImportError) as e:
        print(f"KIMI authentication error: {e}")
