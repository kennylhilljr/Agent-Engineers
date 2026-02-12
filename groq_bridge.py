"""
Groq Bridge Module
==================

Unified interface for Groq's LPU-powered inference API.
Supports both the native Groq SDK and OpenAI-compatible mode.

Authentication:
    - API Key (primary): Free tier with generous rate limits
    - OpenAI-compatible: Use existing OpenAI SDK with Groq base URL

Key Features:
    - Blazing fast inference via Groq's LPU (Language Processing Unit)
    - OpenAI-compatible API (easy migration)
    - Streaming support (sync and async)
    - Tool/function calling support
    - Vision/multimodal support (Llama 4 models)
    - Code execution via compound models
"""

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator, Generator, Optional


class GroqModel(str, Enum):
    """Available Groq models organized by category."""

    # Production models
    LLAMA_3_3_70B = "llama-3.3-70b-versatile"
    LLAMA_3_1_8B = "llama-3.1-8b-instant"
    GPT_OSS_120B = "openai/gpt-oss-120b"
    GPT_OSS_20B = "openai/gpt-oss-20b"

    # Preview models
    LLAMA_4_SCOUT = "meta-llama/llama-4-scout-17b-16e-instruct"
    LLAMA_4_MAVERICK = "meta-llama/llama-4-maverick-17b-128e-instruct"
    QWEN_3_32B = "qwen/qwen-3-32b"
    KIMI_K2 = "moonshotai/kimi-k2-instruct-0905"

    # Compound models (built-in tools: web search, code execution)
    COMPOUND = "groq/compound"
    COMPOUND_MINI = "groq/compound-mini"


# Model categories for easy reference
PRODUCTION_MODELS = [
    GroqModel.LLAMA_3_3_70B,
    GroqModel.LLAMA_3_1_8B,
    GroqModel.GPT_OSS_120B,
    GroqModel.GPT_OSS_20B,
]

PREVIEW_MODELS = [
    GroqModel.LLAMA_4_SCOUT,
    GroqModel.LLAMA_4_MAVERICK,
    GroqModel.QWEN_3_32B,
    GroqModel.KIMI_K2,
]

COMPOUND_MODELS = [
    GroqModel.COMPOUND,
    GroqModel.COMPOUND_MINI,
]

# Default model
DEFAULT_MODEL = GroqModel.LLAMA_3_3_70B


@dataclass
class GroqMessage:
    """A message in a Groq conversation."""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class GroqResponse:
    """Response from the Groq API."""
    content: str
    model: str
    finish_reason: str
    usage: dict = field(default_factory=dict)
    reasoning: Optional[str] = None
    executed_tools: Optional[list] = None


@dataclass
class GroqSession:
    """Manages a conversation session with Groq."""
    model: str = DEFAULT_MODEL.value
    messages: list = field(default_factory=list)
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    top_p: float = 1.0

    def __post_init__(self):
        if self.system_prompt:
            self.messages = [
                {"role": "system", "content": self.system_prompt}
            ] + self.messages


class GroqBridge:
    """
    Unified Groq client matching the Claude SDK client interface pattern.

    Provides create_session / send_message / stream_response interface
    consistent with the other agent bridges (ChatGPT, Gemini).

    Usage:
        bridge = GroqBridge()
        session = bridge.create_session(model="llama-3.3-70b-versatile")
        response = bridge.send_message(session, "Hello!")
        print(response.content)

        # Streaming
        for chunk in bridge.stream_response(session, "Tell me a story"):
            print(chunk, end="", flush=True)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.groq.com/openai/v1",
        use_openai_compat: bool = False,
    ):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY", "")
        self.base_url = base_url
        self.use_openai_compat = use_openai_compat
        self._client = None
        self._async_client = None

    def _get_client(self):
        if self._client is None:
            if self.use_openai_compat:
                try:
                    from openai import OpenAI
                    self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                except ImportError:
                    raise ImportError("openai package required. Install with: pip install openai")
            else:
                try:
                    from groq import Groq
                    self._client = Groq(api_key=self.api_key)
                except ImportError:
                    raise ImportError("groq package required. Install with: pip install groq")
        return self._client

    def _get_async_client(self):
        if self._async_client is None:
            if self.use_openai_compat:
                try:
                    from openai import AsyncOpenAI
                    self._async_client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
                except ImportError:
                    raise ImportError("openai package required for OpenAI-compatible mode.")
            else:
                try:
                    from groq import AsyncGroq
                    self._async_client = AsyncGroq(api_key=self.api_key)
                except ImportError:
                    raise ImportError("groq package required. Install with: pip install groq")
        return self._async_client

    def create_session(self, model=None, system_prompt=None, temperature=0.7, max_tokens=4096):
        model_id = model or os.environ.get("GROQ_MODEL", DEFAULT_MODEL.value)
        return GroqSession(model=model_id, system_prompt=system_prompt, temperature=temperature, max_tokens=max_tokens)

    def send_message(self, session, message, json_mode=False):
        client = self._get_client()
        session.messages.append({"role": "user", "content": message})
        kwargs = {"model": session.model, "messages": session.messages, "temperature": session.temperature, "max_completion_tokens": session.max_tokens, "top_p": session.top_p, "stream": False}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        completion = client.chat.completions.create(**kwargs)
        choice = completion.choices[0]
        assistant_msg = choice.message.content or ""
        session.messages.append({"role": "assistant", "content": assistant_msg})
        usage = {}
        if hasattr(completion, "usage") and completion.usage:
            usage = {"prompt_tokens": completion.usage.prompt_tokens, "completion_tokens": completion.usage.completion_tokens, "total_tokens": completion.usage.total_tokens}
            if hasattr(completion.usage, "prompt_time"):
                usage["prompt_time"] = completion.usage.prompt_time
            if hasattr(completion.usage, "completion_time"):
                usage["completion_time"] = completion.usage.completion_time
            if hasattr(completion.usage, "total_time"):
                usage["total_time"] = completion.usage.total_time
        reasoning = getattr(choice.message, "reasoning", None)
        executed_tools = getattr(choice.message, "executed_tools", None)
        return GroqResponse(content=assistant_msg, model=completion.model, finish_reason=choice.finish_reason or "stop", usage=usage, reasoning=reasoning, executed_tools=executed_tools)

    def stream_response(self, session, message):
        client = self._get_client()
        session.messages.append({"role": "user", "content": message})
        stream = client.chat.completions.create(model=session.model, messages=session.messages, temperature=session.temperature, max_completion_tokens=session.max_tokens, top_p=session.top_p, stream=True)
        full_response = []
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                full_response.append(text)
                yield text
        session.messages.append({"role": "assistant", "content": "".join(full_response)})

    async def async_send_message(self, session, message, json_mode=False):
        client = self._get_async_client()
        session.messages.append({"role": "user", "content": message})
        kwargs = {"model": session.model, "messages": session.messages, "temperature": session.temperature, "max_completion_tokens": session.max_tokens, "top_p": session.top_p, "stream": False}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        completion = await client.chat.completions.create(**kwargs)
        choice = completion.choices[0]
        assistant_msg = choice.message.content or ""
        session.messages.append({"role": "assistant", "content": assistant_msg})
        usage = {}
        if hasattr(completion, "usage") and completion.usage:
            usage = {"prompt_tokens": completion.usage.prompt_tokens, "completion_tokens": completion.usage.completion_tokens, "total_tokens": completion.usage.total_tokens}
        return GroqResponse(content=assistant_msg, model=completion.model, finish_reason=choice.finish_reason or "stop", usage=usage)

    async def async_stream_response(self, session, message):
        client = self._get_async_client()
        session.messages.append({"role": "user", "content": message})
        stream = await client.chat.completions.create(model=session.model, messages=session.messages, temperature=session.temperature, max_completion_tokens=session.max_tokens, top_p=session.top_p, stream=True)
        full_response = []
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                text = chunk.choices[0].delta.content
                full_response.append(text)
                yield text
        session.messages.append({"role": "assistant", "content": "".join(full_response)})

    def list_models(self):
        client = self._get_client()
        models = client.models.list()
        return [{"id": m.id, "owned_by": m.owned_by, "created": m.created} for m in models.data]

    def check_status(self):
        try:
            models = self.list_models()
            return {"status": "connected", "auth": "api_key" if self.api_key else "none", "models_available": len(models), "api_key_set": bool(self.api_key), "base_url": self.base_url}
        except Exception as e:
            return {"status": "error", "error": str(e), "api_key_set": bool(self.api_key), "base_url": self.base_url}
