"""Provider Bridge Integration Module (AI-174 / REQ-TECH-009).

Wraps the existing bridge modules (bridges/*.py) in a unified, testable
interface for the dashboard.  Every provider exposes:

  - provider_name  (str attribute)
  - is_available() -> bool
  - send_message(message, context=None) -> str  (synchronous, for simple use)
  - send_message_async(message, context=None) -> Awaitable[str]  (async)

A ``BridgeRegistry`` collects all six providers and lets callers discover
which ones are ready (API key present / local tool installed).

Graceful degradation:
  If the underlying bridge module cannot be imported, or the required
  credentials are absent, the bridge still instantiates but ``is_available()``
  returns False and every send_* call returns a clearly labelled mock response
  instead of raising.

Providers
---------
  claude    – Anthropic Claude  (ANTHROPIC_API_KEY)
  chatgpt   – OpenAI ChatGPT    (OPENAI_API_KEY)
  gemini    – Google Gemini     (GOOGLE_API_KEY or GEMINI_API_KEY)
  groq      – Groq              (GROQ_API_KEY)
  kimi      – KIMI / Moonshot   (KIMI_API_KEY or MOONSHOT_API_KEY)
  windsurf  – Windsurf Cascade  (local CLI or Docker – no API key required)
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so bridge modules can be imported
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Import BaseBridge for type hints (bridges/base_bridge.py)
# ---------------------------------------------------------------------------
try:
    from bridges.base_bridge import BaseBridge as _BaseBridge, BridgeResponse as _BridgeResponse
except ImportError:
    _BaseBridge = None  # type: ignore[assignment,misc]
    _BridgeResponse = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class ProviderBridge(ABC):
    """Abstract base class for all AI provider bridges."""

    #: Stable, lowercase identifier used as the routing key.
    provider_name: str = "unknown"

    @abstractmethod
    def is_available(self) -> bool:
        """Return True when the bridge can handle real requests."""

    @abstractmethod
    def send_message(self, message: str, context: Optional[str] = None) -> str:
        """Send *message* synchronously and return the response text."""

    async def send_message_async(
        self, message: str, context: Optional[str] = None
    ) -> str:
        """Async variant – default implementation runs send_message in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.send_message, message, context)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _mock_response(provider: str, message: str) -> str:
        """Return a clearly labelled stub response (used when unavailable)."""
        return (
            f"[{provider.upper()} MOCK] API key not configured or bridge unavailable. "
            f"Echo: {message[:120]}"
        )


# ---------------------------------------------------------------------------
# Claude bridge
# ---------------------------------------------------------------------------

class ClaudeBridge(ProviderBridge):
    """Bridge for Anthropic Claude via the anthropic SDK."""

    provider_name = "claude"

    def __init__(self) -> None:
        self._api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
        self._client: Any = None
        if self._api_key:
            try:
                import anthropic  # type: ignore
                self._client = anthropic.Anthropic(api_key=self._api_key)
            except ImportError:
                logger.warning("anthropic package not installed; Claude will use mock mode.")

    def is_available(self) -> bool:
        return bool(self._api_key and self._client is not None)

    def send_message(self, message: str, context: Optional[str] = None) -> str:
        if not self.is_available():
            return self._mock_response(self.provider_name, message)
        try:
            system = context or "You are a helpful assistant."
            resp = self._client.messages.create(
                model="claude-opus-4-6",
                max_tokens=1024,
                system=system,
                messages=[{"role": "user", "content": message}],
            )
            return resp.content[0].text
        except Exception as exc:
            logger.error("ClaudeBridge error: %s", exc)
            raise


# ---------------------------------------------------------------------------
# OpenAI / ChatGPT bridge
# ---------------------------------------------------------------------------

class OpenAIBridge(ProviderBridge):
    """Bridge for OpenAI ChatGPT – delegates to bridges/openai_bridge.py."""

    provider_name = "chatgpt"

    def __init__(self) -> None:
        self._api_key: str = os.environ.get("OPENAI_API_KEY", "")
        self._bridge: Optional[_BaseBridge] = None
        self._session: Any = None
        if self._api_key:
            try:
                from bridges.openai_bridge import (  # type: ignore
                    CodexOAuthClient,
                    ChatSession,
                    ChatGPTModel,
                    OpenAIBridge as _OAIBridge,
                )
                client = CodexOAuthClient(api_key=self._api_key)
                self._bridge = _OAIBridge(auth_type="codex-oauth", client=client)
                self._session_cls = ChatSession
                self._model_cls = ChatGPTModel
            except Exception as exc:
                logger.warning("OpenAIBridge init failed: %s", exc)

    def is_available(self) -> bool:
        return bool(self._api_key and self._bridge is not None)

    def _make_session(self) -> Any:
        return self._session_cls(model=self._model_cls.GPT_4O)

    def send_message(self, message: str, context: Optional[str] = None) -> str:
        if not self.is_available():
            return self._mock_response(self.provider_name, message)
        try:
            session = self._make_session()
            if context:
                session.add_message("system", context)
            resp = self._bridge.send_message(session, message)
            return resp.content
        except Exception as exc:
            logger.error("OpenAIBridge error: %s", exc)
            raise


# ---------------------------------------------------------------------------
# Gemini bridge
# ---------------------------------------------------------------------------

class GeminiBridge(ProviderBridge):
    """Bridge for Google Gemini – delegates to bridges/gemini_bridge.py."""

    provider_name = "gemini"

    def __init__(self) -> None:
        self._api_key: str = (
            os.environ.get("GOOGLE_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
        )
        self._bridge: Optional[_BaseBridge] = None
        if self._api_key:
            try:
                from bridges.gemini_bridge import (  # type: ignore
                    GenAISDKClient,
                    GeminiBridge as _GBridge,
                    GeminiAuthType,
                    GeminiModel,
                    GeminiSession,
                )
                # Temporarily set env var so GenAISDKClient picks it up
                os.environ.setdefault("GOOGLE_API_KEY", self._api_key)
                client = GenAISDKClient(GeminiAuthType.API_KEY)
                self._bridge = _GBridge(auth_type=GeminiAuthType.API_KEY, client=client)
                self._session_cls = GeminiSession
                self._model_cls = GeminiModel
            except Exception as exc:
                logger.warning("GeminiBridge init failed: %s", exc)

    def is_available(self) -> bool:
        return bool(self._api_key and self._bridge is not None)

    def send_message(self, message: str, context: Optional[str] = None) -> str:
        if not self.is_available():
            return self._mock_response(self.provider_name, message)
        try:
            session = self._session_cls(model=self._model_cls.GEMINI_25_FLASH)
            if context:
                session.add_message("user", f"System: {context}")
                session.add_message("model", "Understood.")
            resp = self._bridge.send_message(session, message)
            return resp.content
        except Exception as exc:
            logger.error("GeminiBridge error: %s", exc)
            raise


# ---------------------------------------------------------------------------
# Groq bridge
# ---------------------------------------------------------------------------

class GroqBridge(ProviderBridge):
    """Bridge for Groq – delegates to bridges/groq_bridge.py."""

    provider_name = "groq"

    def __init__(self) -> None:
        self._api_key: str = os.environ.get("GROQ_API_KEY", "")
        self._bridge: Optional[_BaseBridge] = None
        if self._api_key:
            try:
                from bridges.groq_bridge import (  # type: ignore
                    GroqClient,
                    GroqBridge as _GBridge,
                    GroqModel,
                    GroqSession,
                )
                client = GroqClient(api_key=self._api_key)
                self._bridge = _GBridge(client=client)
                self._session_cls = GroqSession
                self._model_cls = GroqModel
            except Exception as exc:
                logger.warning("GroqBridge init failed: %s", exc)

    def is_available(self) -> bool:
        return bool(self._api_key and self._bridge is not None)

    def send_message(self, message: str, context: Optional[str] = None) -> str:
        if not self.is_available():
            return self._mock_response(self.provider_name, message)
        try:
            session = self._session_cls(model=self._model_cls.LLAMA_3_3_70B)
            if context:
                session.add_message("system", context)
            resp = self._bridge.send_message(session, message)
            return resp.content
        except Exception as exc:
            logger.error("GroqBridge error: %s", exc)
            raise


# ---------------------------------------------------------------------------
# KIMI bridge
# ---------------------------------------------------------------------------

class KimiBridge(ProviderBridge):
    """Bridge for KIMI / Moonshot AI – delegates to bridges/kimi_bridge.py."""

    provider_name = "kimi"

    def __init__(self) -> None:
        self._api_key: str = (
            os.environ.get("KIMI_API_KEY", "") or os.environ.get("MOONSHOT_API_KEY", "")
        )
        self._bridge: Optional[_BaseBridge] = None
        if self._api_key:
            try:
                from bridges.kimi_bridge import (  # type: ignore
                    KimiClient,
                    KimiBridge as _KBridge,
                    KimiModel,
                    KimiSession,
                )
                client = KimiClient(api_key=self._api_key)
                self._bridge = _KBridge(client=client)
                self._session_cls = KimiSession
                self._model_cls = KimiModel
            except Exception as exc:
                logger.warning("KimiBridge init failed: %s", exc)

    def is_available(self) -> bool:
        return bool(self._api_key and self._bridge is not None)

    def send_message(self, message: str, context: Optional[str] = None) -> str:
        if not self.is_available():
            return self._mock_response(self.provider_name, message)
        try:
            session = self._session_cls(model=self._model_cls.MOONSHOT_V1_AUTO)
            if context:
                session.add_message("system", context)
            resp = self._bridge.send_message(session, message)
            return resp.content
        except Exception as exc:
            logger.error("KimiBridge error: %s", exc)
            raise


# ---------------------------------------------------------------------------
# Windsurf bridge
# ---------------------------------------------------------------------------

class WindsurfBridge(ProviderBridge):
    """Bridge for Windsurf (Cascade) – delegates to bridges/windsurf_bridge.py.

    Windsurf does not require an API key; availability depends on whether the
    CLI or Docker is present.  Falls back to mock when neither is available.
    """

    provider_name = "windsurf"

    def __init__(self) -> None:
        self._bridge: Optional[_BaseBridge] = None
        try:
            from bridges.windsurf_bridge import (  # type: ignore
                WindsurfBridge as _WBridge,
                WindsurfMode,
                WindsurfSession,
            )
            # Try CLI first, then Docker
            mode_str = os.environ.get("WINDSURF_MODE", "cli")
            try:
                from bridges.windsurf_bridge import WindsurfCLIClient  # type: ignore
                cli_client = WindsurfCLIClient()
                self._bridge = _WBridge(mode=WindsurfMode.CLI, client=cli_client)
            except (ImportError, Exception):
                try:
                    from bridges.windsurf_bridge import WindsurfDockerClient  # type: ignore
                    docker_client = WindsurfDockerClient()
                    self._bridge = _WBridge(mode=WindsurfMode.DOCKER, client=docker_client)
                except (ImportError, Exception):
                    pass  # Both unavailable – mock mode
            self._session_cls = WindsurfSession
            self._ws_mode_cls = WindsurfMode
        except Exception as exc:
            logger.warning("WindsurfBridge init failed: %s", exc)

    def is_available(self) -> bool:
        return self._bridge is not None

    def send_message(self, message: str, context: Optional[str] = None) -> str:
        if not self.is_available():
            return self._mock_response(self.provider_name, message)
        try:
            import tempfile
            workspace = os.environ.get("WINDSURF_WORKSPACE") or tempfile.mkdtemp(
                prefix="windsurf-"
            )
            session = self._session_cls(
                mode=self._ws_mode_cls.CLI, workspace=workspace
            )
            if context:
                session.add_message("system", context)
            resp = self._bridge.send_task(session, message)
            return resp.content
        except Exception as exc:
            logger.error("WindsurfBridge error: %s", exc)
            raise


# ---------------------------------------------------------------------------
# BridgeRegistry
# ---------------------------------------------------------------------------

#: Canonical mapping from provider name to bridge class
_BRIDGE_CLASSES: Dict[str, type] = {
    "claude": ClaudeBridge,
    "chatgpt": OpenAIBridge,
    "gemini": GeminiBridge,
    "groq": GroqBridge,
    "kimi": KimiBridge,
    "windsurf": WindsurfBridge,
}

# Alias map so callers can use "openai" or "gpt" to reach ChatGPT
_PROVIDER_ALIASES: Dict[str, str] = {
    "openai": "chatgpt",
    "gpt": "chatgpt",
    "chatgpt": "chatgpt",
    "claude": "claude",
    "anthropic": "claude",
    "gemini": "gemini",
    "google": "gemini",
    "groq": "groq",
    "kimi": "kimi",
    "moonshot": "kimi",
    "windsurf": "windsurf",
    "cascade": "windsurf",
}


class BridgeRegistry:
    """Registry that holds one instance of each provider bridge.

    Usage::

        registry = BridgeRegistry()
        bridge = registry.get("gemini")
        response = bridge.send_message("Hello!")

        available = registry.get_available_bridges()
        # -> list of ProviderBridge instances whose .is_available() == True
    """

    def __init__(self) -> None:
        self._bridges: Dict[str, ProviderBridge] = {}
        for name, cls in _BRIDGE_CLASSES.items():
            try:
                self._bridges[name] = cls()
            except Exception as exc:
                logger.warning("Failed to instantiate %s: %s", name, exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, provider: str) -> ProviderBridge:
        """Return the bridge for *provider*.

        Accepts canonical names and aliases (e.g. "openai" -> ChatGPT bridge).

        Raises:
            KeyError: If the provider name is not recognised.
        """
        canonical = _PROVIDER_ALIASES.get(provider.lower().strip())
        if canonical is None:
            raise KeyError(
                f"Unknown provider '{provider}'. "
                f"Valid names: {sorted(_PROVIDER_ALIASES.keys())}"
            )
        bridge = self._bridges.get(canonical)
        if bridge is None:
            raise KeyError(f"Bridge for provider '{canonical}' failed to initialise.")
        return bridge

    def get_available_bridges(self) -> List[ProviderBridge]:
        """Return a list of bridges whose ``is_available()`` returns True."""
        return [b for b in self._bridges.values() if b.is_available()]

    def all_bridges(self) -> List[ProviderBridge]:
        """Return all registered bridge instances (available or not)."""
        return list(self._bridges.values())

    def provider_names(self) -> List[str]:
        """Return the sorted list of canonical provider names."""
        return sorted(self._bridges.keys())

    def status(self) -> Dict[str, bool]:
        """Return a dict mapping provider name -> is_available()."""
        return {name: bridge.is_available() for name, bridge in self._bridges.items()}


# ---------------------------------------------------------------------------
# Module-level singleton (convenience)
# ---------------------------------------------------------------------------

_registry: Optional[BridgeRegistry] = None


def get_registry() -> BridgeRegistry:
    """Return the module-level singleton BridgeRegistry (lazy init)."""
    global _registry
    if _registry is None:
        _registry = BridgeRegistry()
    return _registry


def get_bridge(provider: str) -> ProviderBridge:
    """Shortcut: get a bridge from the singleton registry."""
    return get_registry().get(provider)
