"""
Multi-Provider Bridge with Automatic Fallback
==============================================

Wraps multiple AI provider bridges (OpenRouter, Groq, Gemini) with automatic
fallback on rate limits or errors. Tries providers in priority order.

Usage:
    bridge = MultiProviderBridge.from_env()
    response = bridge.send_message("Analyze this backlog...")
    print(f"Response from {response.provider}: {response.content}")
"""

import os
import time
from dataclasses import dataclass

RATE_LIMIT_KEYWORDS = ("rate limit", "429", "quota", "too many requests", "limit exceeded")


@dataclass
class MultiProviderResponse:
    """Response from multi-provider bridge."""

    content: str
    provider: str
    model: str
    usage: dict | None = None
    fallback_used: bool = False
    attempts: int = 1


class MultiProviderBridge:
    """Tries multiple providers in order, falling back on rate limits or errors."""

    def __init__(self, providers: list[dict]) -> None:
        """Initialize with ordered list of provider configs.

        Each provider dict has:
            name: str - Display name
            type: str - "openrouter", "groq", or "gemini"
            bridge: object - Initialized bridge instance
            session_kwargs: dict - kwargs for create_session()
        """
        self._providers = providers

    @classmethod
    def from_env(cls, system_prompt: str | None = None) -> "MultiProviderBridge":
        """Build provider chain from available environment variables.

        Priority order:
        1. OpenRouter (free tier, 50 req/day)
        2. Groq (free tier, fast inference)
        3. Gemini (free tier via API key, 60 req/min)
        """
        providers = []

        # 1. OpenRouter
        if os.environ.get("OPENROUTER_API_KEY"):
            try:
                from bridges.openrouter_bridge import OpenRouterBridge

                bridge = OpenRouterBridge.from_env()
                providers.append({
                    "name": "OpenRouter",
                    "type": "openrouter",
                    "bridge": bridge,
                    "session_kwargs": {
                        "system_prompt": system_prompt,
                        "temperature": 0.7,
                        "max_tokens": 4096,
                    },
                })
                print("[MultiProvider] OpenRouter: available")
            except (ValueError, ImportError) as e:
                print(f"[MultiProvider] OpenRouter: unavailable ({e})")

        # 2. Groq
        if os.environ.get("GROQ_API_KEY"):
            try:
                from bridges.groq_bridge import GroqBridge

                bridge = GroqBridge.from_env()
                providers.append({
                    "name": "Groq",
                    "type": "groq",
                    "bridge": bridge,
                    "session_kwargs": {
                        "system_prompt": system_prompt,
                        "temperature": 0.7,
                        "max_tokens": 4096,
                    },
                })
                print("[MultiProvider] Groq: available")
            except (ValueError, ImportError) as e:
                print(f"[MultiProvider] Groq: unavailable ({e})")

        # 3. Gemini (API key mode only for non-interactive use)
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if api_key:
            try:
                from bridges.gemini_bridge import GeminiBridge

                os.environ.setdefault("GEMINI_AUTH_TYPE", "api-key")
                bridge = GeminiBridge.from_env()
                providers.append({
                    "name": "Gemini",
                    "type": "gemini",
                    "bridge": bridge,
                    "session_kwargs": {
                        "system_prompt": system_prompt,
                    },
                })
                print("[MultiProvider] Gemini: available")
            except (ValueError, ImportError) as e:
                print(f"[MultiProvider] Gemini: unavailable ({e})")

        if not providers:
            raise ValueError(
                "No AI providers available. Set at least one of:\n"
                "  OPENROUTER_API_KEY, GROQ_API_KEY, or GOOGLE_API_KEY/GEMINI_API_KEY"
            )

        print(f"[MultiProvider] {len(providers)} provider(s) in fallback chain")
        return cls(providers=providers)

    def send_message(self, message: str) -> MultiProviderResponse:
        """Send a message, trying each provider in order until one succeeds."""
        errors = []

        for i, provider in enumerate(self._providers):
            name = provider["name"]
            bridge = provider["bridge"]
            kwargs = provider["session_kwargs"]

            try:
                session = bridge.create_session(**kwargs)
                response = bridge.send_message(session, message)

                return MultiProviderResponse(
                    content=response.content,
                    provider=name,
                    model=response.model,
                    usage=getattr(response, "usage", None),
                    fallback_used=i > 0,
                    attempts=i + 1,
                )

            except Exception as e:
                error_str = str(e).lower()
                is_rate_limit = any(kw in error_str for kw in RATE_LIMIT_KEYWORDS)
                error_type = "RATE LIMITED" if is_rate_limit else "ERROR"
                print(f"[MultiProvider] {name}: {error_type} - {e}")
                errors.append(f"{name}: {e}")

                if is_rate_limit and i < len(self._providers) - 1:
                    next_name = self._providers[i + 1]["name"]
                    print(f"[MultiProvider] Falling back to {next_name}...")
                    time.sleep(1)  # Brief pause before fallback
                    continue
                elif not is_rate_limit:
                    # Non-rate-limit error — still try next provider
                    if i < len(self._providers) - 1:
                        next_name = self._providers[i + 1]["name"]
                        print(f"[MultiProvider] Trying {next_name}...")
                        continue

        # All providers failed
        raise RuntimeError(
            f"All {len(self._providers)} providers failed:\n" + "\n".join(errors)
        )

    def get_provider_status(self) -> list[dict[str, str]]:
        """Return status info for all configured providers."""
        statuses = []
        for p in self._providers:
            bridge = p["bridge"]
            info = bridge.get_auth_info() if hasattr(bridge, "get_auth_info") else {}
            statuses.append({
                "name": p["name"],
                "type": p["type"],
                **info,
            })
        return statuses
