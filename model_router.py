"""
Model Router - Routes tasks to the appropriate AI provider (Claude, ChatGPT).
"""

import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from openai_bridge import (
    AuthType, ChatGPTModel, ChatResponse, ChatSession,
    OpenAIBridge, get_available_models as get_chatgpt_models,
)


class AIProvider(str, Enum):
    CLAUDE = "claude"
    CHATGPT = "chatgpt"


@dataclass
class RoutingDecision:
    provider: AIProvider
    model: str
    reason: str


class ModelRouter:
    def __init__(self) -> None:
        self._chatgpt_bridge: Optional[OpenAIBridge] = None
        self._chatgpt_available: Optional[bool] = None

    def route(self, task: str, provider: Optional[str] = None,
              model: Optional[str] = None) -> RoutingDecision:
        if provider:
            provider_lower = provider.lower().strip()
            if provider_lower in ("chatgpt", "openai", "gpt"):
                chatgpt_model = model or os.environ.get("CHATGPT_MODEL", "gpt-4o")
                return RoutingDecision(provider=AIProvider.CHATGPT,
                    model=chatgpt_model,
                    reason=f"Explicitly requested ChatGPT with {chatgpt_model}")
            if provider_lower == "claude":
                claude_model = model or "sonnet"
                return RoutingDecision(provider=AIProvider.CLAUDE,
                    model=claude_model,
                    reason=f"Explicitly requested Claude with {claude_model}")
        if model:
            model_lower = model.lower().strip()
            chatgpt_models = {m.value for m in ChatGPTModel}
            if model_lower in chatgpt_models:
                return RoutingDecision(provider=AIProvider.CHATGPT,
                    model=model_lower,
                    reason=f"Model {model_lower} is a ChatGPT model")
            if model_lower in ("haiku", "sonnet", "opus"):
                return RoutingDecision(provider=AIProvider.CLAUDE,
                    model=model_lower,
                    reason=f"Model {model_lower} is a Claude model")
        return RoutingDecision(provider=AIProvider.CLAUDE, model="sonnet",
            reason="Default routing to Claude Sonnet")

    def is_chatgpt_available(self) -> bool:
        if self._chatgpt_available is not None:
            return self._chatgpt_available
        try:
            self.get_chatgpt_bridge()
            self._chatgpt_available = True
        except (ValueError, ImportError):
            self._chatgpt_available = False
        return self._chatgpt_available

    def get_chatgpt_bridge(self) -> OpenAIBridge:
        if self._chatgpt_bridge is None:
            self._chatgpt_bridge = OpenAIBridge.from_env()
        return self._chatgpt_bridge

    def get_provider_status(self) -> dict[str, dict[str, object]]:
        status: dict[str, dict[str, object]] = {
            "claude": {"available": True, "models": ["haiku", "sonnet", "opus"]}}
        chatgpt_status: dict[str, object] = {"available": False, "models": [], "auth_type": None}
        try:
            bridge = self.get_chatgpt_bridge()
            info = bridge.get_auth_info()
            chatgpt_status["available"] = True
            chatgpt_status["models"] = get_chatgpt_models()
            chatgpt_status["auth_type"] = info.get("auth_type", "unknown")
            chatgpt_status["cost_note"] = info.get("cost_note", "")
        except (ValueError, ImportError) as e:
            chatgpt_status["error"] = str(e)
        status["chatgpt"] = chatgpt_status
        return status

    def print_status(self) -> None:
        status = self.get_provider_status()
        print("=" * 60)
        print("  Multi-AI Provider Status")
        print("=" * 60)
        for provider_name, info in status.items():
            available = "Y" if info.get("available") else "N"
            print(f"\n  [{available}] {provider_name.upper()}")
            if info.get("models"):
                print(f"      Models: {', '.join(info['models'])}")
            if info.get("auth_type"):
                print(f"      Auth: {info['auth_type']}")
            if info.get("cost_note"):
                print(f"      Cost: {info['cost_note']}")
            if info.get("error"):
                print(f"      Error: {info['error']}")
        print("\n" + "=" * 60)
