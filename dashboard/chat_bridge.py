"""Chat-to-Agent Bridge Module (AI-173 / REQ-TECH-008).

This module bridges user chat messages to the agent system by:
1. Parsing user intent from natural language (rule-based / keyword matching)
2. Routing to the appropriate agent type
3. Executing delegation through the existing session loop (or simulating gracefully)
4. Streaming results back to the chat via an async generator

Classes:
    IntentParser  -- Extracts structured intent from raw chat text
    AgentRouter   -- Maps intents to agent names
    ChatBridge    -- Orchestrates intent parsing, routing, and streaming response

Intent Types:
    ask_agent     -- User wants an agent to do something specific
    run_task      -- User wants to run a task (tests, build, deploy, etc.)
    get_status    -- User is asking about agent / system status
    general_chat  -- No actionable agent intent detected (fallback)

AI-174 (REQ-TECH-009): Provider Bridge Integration
    Messages routed to non-Claude providers (chatgpt, gemini, groq, kimi,
    windsurf) are forwarded through dashboard.provider_bridge.  Claude
    messages go through ClaudeBridge.  Graceful fallback if unavailable.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Any, AsyncIterator, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sandbox policy integration (AI-177 / REQ-TECH-012)
# ---------------------------------------------------------------------------
# Lazily imported so ChatBridge degrades gracefully if dashboard.security has
# import issues (mirrors the pattern used for provider_bridge above).

_sandbox_policy = None


def _get_sandbox_policy():
    """Lazily initialise and cache the SandboxPolicy singleton."""
    global _sandbox_policy
    if _sandbox_policy is None:
        try:
            from dashboard.security import SandboxPolicy
            _sandbox_policy = SandboxPolicy()
        except Exception as exc:
            logger.warning("dashboard.security unavailable: %s", exc)
            _sandbox_policy = None
    return _sandbox_policy

# ---------------------------------------------------------------------------
# Provider bridge integration (AI-174 / REQ-TECH-009)
# ---------------------------------------------------------------------------
# Lazy import so ChatBridge still works even if provider_bridge has import
# issues (graceful degradation).

_provider_registry = None


def _get_provider_registry():
    """Lazily initialise and cache the BridgeRegistry singleton."""
    global _provider_registry
    if _provider_registry is None:
        try:
            from dashboard.provider_bridge import BridgeRegistry
            _provider_registry = BridgeRegistry()
        except Exception as exc:
            logger.warning("provider_bridge unavailable: %s", exc)
            _provider_registry = None
    return _provider_registry


# Providers handled by provider_bridge rather than the generic agent loop
_PROVIDER_BRIDGE_NAMES = frozenset({"claude", "chatgpt", "gemini", "groq", "kimi", "windsurf"})


# ---------------------------------------------------------------------------
# Intent Types
# ---------------------------------------------------------------------------

INTENT_ASK_AGENT = "ask_agent"
INTENT_RUN_TASK = "run_task"
INTENT_GET_STATUS = "get_status"
INTENT_GENERAL_CHAT = "general_chat"

VALID_INTENT_TYPES = (
    INTENT_ASK_AGENT,
    INTENT_RUN_TASK,
    INTENT_GET_STATUS,
    INTENT_GENERAL_CHAT,
)

# ---------------------------------------------------------------------------
# Known agent names (from agents/definitions.py)
# ---------------------------------------------------------------------------

KNOWN_AGENTS = {
    "coding",
    "coding_fast",
    "linear",
    "github",
    "slack",
    "pr_reviewer",
    "pr_reviewer_fast",
    "ops",
    "chatgpt",
    "gemini",
    "groq",
    "kimi",
    "windsurf",
}

# ---------------------------------------------------------------------------
# IntentParser
# ---------------------------------------------------------------------------

# Keyword sets for each intent (all lowercase)
_ASK_AGENT_PREFIXES = [
    r"ask\s+(?:the\s+)?(\w+)\s+agent",
    r"tell\s+(?:the\s+)?(\w+)\s+agent",
    r"have\s+(?:the\s+)?(\w+)\s+agent",
    r"use\s+(?:the\s+)?(\w+)\s+agent",
    r"delegate\s+to\s+(?:the\s+)?(\w+)",
    r"assign\s+to\s+(?:the\s+)?(\w+)",
    r"let\s+(?:the\s+)?(\w+)\s+(?:agent\s+)?handle",
    r"get\s+(?:the\s+)?(\w+)\s+agent\s+to",
]

_RUN_TASK_KEYWORDS = [
    "run tests",
    "run the tests",
    "run pytest",
    "execute tests",
    "run build",
    "build the project",
    "deploy",
    "run migration",
    "run linter",
    "run lint",
    "run checks",
    "run all tests",
    "run unit tests",
    "run integration tests",
    "start tests",
    "trigger tests",
    "run the build",
    "build and test",
    "test and build",
]

_STATUS_KEYWORDS = [
    "what's the status",
    "what is the status",
    "whats the status",
    "show status",
    "agent status",
    "system status",
    "how are the agents",
    "are agents running",
    "is the agent",
    "status of",
    "check status",
    "current status",
    "health check",
    "how is everything",
    "are you running",
    "what are you doing",
    "what is happening",
    "what's happening",
    "show me status",
    "give me a status",
    "dashboard status",
]

# Agent keyword aliases for routing without explicit "ask X agent"
_AGENT_KEYWORD_MAP: Dict[str, str] = {
    # coding agent
    "write code": "coding",
    "write a function": "coding",
    "write a class": "coding",
    "implement": "coding",
    "fix the bug": "coding",
    "fix bug": "coding",
    "refactor": "coding",
    "add a test": "coding",
    "add tests": "coding",
    "create a file": "coding",
    "write tests": "coding",
    "code": "coding",
    "implement feature": "coding",
    # linear agent
    "update linear": "linear",
    "create ticket": "linear",
    "create issue": "linear",
    "update ticket": "linear",
    "move ticket": "linear",
    "linear issue": "linear",
    "transition ticket": "linear",
    "close ticket": "linear",
    "close issue": "linear",
    # github agent
    "create pr": "github",
    "create pull request": "github",
    "merge pr": "github",
    "merge pull request": "github",
    "push to github": "github",
    "github": "github",
    "open pr": "github",
    "push code": "github",
    # slack agent
    "send slack": "slack",
    "post to slack": "slack",
    "notify slack": "slack",
    "slack message": "slack",
    "send message to slack": "slack",
    # pr reviewer
    "review pr": "pr_reviewer",
    "review the pr": "pr_reviewer",
    "review pull request": "pr_reviewer",
    "approve pr": "pr_reviewer",
    # ops agent
    "ops": "ops",
    "operations": "ops",
    "deploy ops": "ops",
}


class IntentParser:
    """Parse user intent from raw chat message text.

    Uses rule-based keyword matching (no ML dependency) to classify messages
    into one of four intent types and extract agent and task information.

    Returns:
        A dict with keys:
            intent_type (str): One of VALID_INTENT_TYPES
            agent (str | None): Detected agent name, or None
            task (str): Extracted task description
            confidence (float): 0.0 – 1.0 confidence estimate
    """

    def parse_intent(self, message: str) -> Dict[str, Any]:
        """Parse intent from a user message.

        Args:
            message: Raw user chat message string

        Returns:
            Dict with intent_type, agent, task, confidence
        """
        if not message or not isinstance(message, str):
            return self._make_intent(INTENT_GENERAL_CHAT, None, "", 0.5)

        lower = message.lower().strip()

        # 1. Check for explicit "ask X agent to …" patterns
        result = self._match_ask_agent(lower, message)
        if result is not None:
            return result

        # 2. Check for run_task intents
        result = self._match_run_task(lower, message)
        if result is not None:
            return result

        # 3. Check for status queries
        result = self._match_status(lower, message)
        if result is not None:
            return result

        # 4. Check agent keyword map (implicit agent routing)
        result = self._match_agent_keywords(lower, message)
        if result is not None:
            return result

        # 5. Fallback – general_chat
        return self._make_intent(INTENT_GENERAL_CHAT, None, message, 0.3)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _make_intent(
        self,
        intent_type: str,
        agent: Optional[str],
        task: str,
        confidence: float,
    ) -> Dict[str, Any]:
        return {
            "intent_type": intent_type,
            "agent": agent,
            "task": task,
            "confidence": round(min(1.0, max(0.0, confidence)), 2),
        }

    def _match_ask_agent(self, lower: str, original: str) -> Optional[Dict[str, Any]]:
        for pattern in _ASK_AGENT_PREFIXES:
            m = re.search(pattern, lower)
            if m:
                candidate = m.group(1).lower()
                agent = candidate if candidate in KNOWN_AGENTS else None
                # Extract the task portion after the matched pattern
                task = original[m.end():].strip().lstrip("to ").strip()
                if not task:
                    task = original
                return self._make_intent(INTENT_ASK_AGENT, agent, task, 0.9)
        return None

    def _match_run_task(self, lower: str, original: str) -> Optional[Dict[str, Any]]:
        for keyword in _RUN_TASK_KEYWORDS:
            if keyword in lower:
                return self._make_intent(INTENT_RUN_TASK, "coding", original, 0.85)
        return None

    def _match_status(self, lower: str, original: str) -> Optional[Dict[str, Any]]:
        for keyword in _STATUS_KEYWORDS:
            if keyword in lower:
                return self._make_intent(INTENT_GET_STATUS, None, original, 0.85)
        return None

    def _match_agent_keywords(self, lower: str, original: str) -> Optional[Dict[str, Any]]:
        # Sort by length descending to match longer phrases first
        for keyword in sorted(_AGENT_KEYWORD_MAP.keys(), key=len, reverse=True):
            if keyword in lower:
                agent = _AGENT_KEYWORD_MAP[keyword]
                return self._make_intent(INTENT_ASK_AGENT, agent, original, 0.75)
        return None


# ---------------------------------------------------------------------------
# AgentRouter
# ---------------------------------------------------------------------------

# Default routing table: intent → agent
_DEFAULT_ROUTING: Dict[str, Optional[str]] = {
    INTENT_ASK_AGENT: None,     # Use agent from intent if present, else None
    INTENT_RUN_TASK: "coding",  # run_task always goes to coding agent
    INTENT_GET_STATUS: None,    # Status handled internally, no agent needed
    INTENT_GENERAL_CHAT: None,  # General chat handled by chat_handler
}


class AgentRouter:
    """Map parsed intents to agent names.

    Routes intents to the correct agent based on the intent type and any
    agent detected by the IntentParser. Falls back gracefully when no
    specific agent is identified.
    """

    def route(self, intent: Dict[str, Any]) -> Optional[str]:
        """Determine the agent name to delegate to.

        Args:
            intent: Parsed intent dict from IntentParser.parse_intent()

        Returns:
            Agent name string (e.g. "coding"), or None if no routing needed.
        """
        if not intent or not isinstance(intent, dict):
            return None

        intent_type = intent.get("intent_type", INTENT_GENERAL_CHAT)
        agent = intent.get("agent")

        # If the intent already has a specific agent, use it
        if agent and agent in KNOWN_AGENTS:
            return agent

        # Apply default routing table
        return _DEFAULT_ROUTING.get(intent_type)


# ---------------------------------------------------------------------------
# ChatBridge
# ---------------------------------------------------------------------------

class ChatBridge:
    """Bridge user chat messages to agent execution and stream results.

    Composes IntentParser and AgentRouter to:
    1. Parse user intent
    2. Route to the appropriate agent
    3. Simulate or execute agent delegation
    4. Yield response chunks as an async generator

    All methods are non-blocking and degrade gracefully – if no agent
    is matched the bridge falls back to a helpful general response.

    Chunk format (dict):
        type (str):      'text' | 'intent' | 'routing' | 'agent_response' | 'error' | 'done'
        content (str):   Human-readable content for this chunk
        metadata (dict): Extra context (intent_type, agent, confidence, etc.)
        timestamp (str): ISO-8601 UTC timestamp with 'Z' suffix
    """

    def __init__(
        self,
        intent_parser: Optional[IntentParser] = None,
        agent_router: Optional[AgentRouter] = None,
    ):
        self.intent_parser = intent_parser or IntentParser()
        self.agent_router = agent_router or AgentRouter()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def handle_message(
        self,
        message: str,
        session_id: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Handle a user message and stream back response chunks.

        Args:
            message: Raw user chat message
            session_id: Optional session identifier for context

        Yields:
            Response chunk dicts with type, content, metadata, timestamp
        """
        return self._stream_response(message, session_id)

    # ------------------------------------------------------------------
    # Internal streaming generator
    # ------------------------------------------------------------------

    async def _stream_response(
        self,
        message: str,
        session_id: Optional[str],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Core async generator that drives the intent → route → execute → stream pipeline."""

        # --- Step 1: validate input ---
        if not message or not isinstance(message, str):
            yield self._chunk(
                "error",
                "Empty or invalid message received.",
                {"error_code": "BRIDGE_INVALID_INPUT"},
            )
            yield self._chunk("done", "", {})
            return

        try:
            # --- Step 2: parse intent ---
            intent = self.intent_parser.parse_intent(message)
            yield self._chunk(
                "intent",
                f"Detected intent: {intent['intent_type']} (confidence: {intent['confidence']})",
                {
                    "intent_type": intent["intent_type"],
                    "agent": intent["agent"],
                    "task": intent["task"],
                    "confidence": intent["confidence"],
                    "session_id": session_id,
                },
            )
            await asyncio.sleep(0)  # yield control

            # --- Step 3: route to agent ---
            target_agent = self.agent_router.route(intent)
            if target_agent:
                yield self._chunk(
                    "routing",
                    f"Routing to agent: {target_agent}",
                    {"agent": target_agent, "intent_type": intent["intent_type"]},
                )
            else:
                yield self._chunk(
                    "routing",
                    "No specific agent required; handling directly.",
                    {"agent": None, "intent_type": intent["intent_type"]},
                )
            await asyncio.sleep(0)

            # --- Step 4: execute (delegate or handle) ---
            async for chunk in self._execute(intent, target_agent, message, session_id):
                yield chunk

        except Exception as exc:
            logger.exception("ChatBridge error handling message: %r", message)
            yield self._chunk(
                "error",
                f"An error occurred while processing your message: {exc}",
                {"error_code": "BRIDGE_INTERNAL_ERROR", "exception": type(exc).__name__},
            )

        yield self._chunk("done", "", {"session_id": session_id})

    async def _execute(
        self,
        intent: Dict[str, Any],
        agent: Optional[str],
        original_message: str,
        session_id: Optional[str],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Dispatch to the appropriate execution handler based on intent type."""
        intent_type = intent.get("intent_type", INTENT_GENERAL_CHAT)

        if intent_type == INTENT_GET_STATUS:
            async for chunk in self._handle_status(intent, session_id):
                yield chunk

        elif intent_type == INTENT_RUN_TASK:
            async for chunk in self._handle_run_task(intent, agent, session_id):
                yield chunk

        elif intent_type == INTENT_ASK_AGENT and agent:
            async for chunk in self._handle_agent_delegation(intent, agent, session_id):
                yield chunk

        else:
            # General chat or unknown intent with no agent
            async for chunk in self._handle_general(original_message, session_id):
                yield chunk

    # ------------------------------------------------------------------
    # Intent-specific handlers
    # ------------------------------------------------------------------

    async def _handle_status(
        self, intent: Dict[str, Any], session_id: Optional[str]
    ) -> AsyncIterator[Dict[str, Any]]:
        """Handle get_status intents by returning current system status."""
        await asyncio.sleep(0)
        status_text = (
            "Agent system status: All agents are operational.\n"
            "- Coding agent: idle\n"
            "- Linear agent: idle\n"
            "- GitHub agent: idle\n"
            "- Slack agent: idle\n"
            "- Orchestrator: ready\n"
        )
        yield self._chunk(
            "agent_response",
            status_text,
            {"intent_type": INTENT_GET_STATUS, "session_id": session_id},
        )

    async def _handle_run_task(
        self,
        intent: Dict[str, Any],
        agent: Optional[str],
        session_id: Optional[str],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Handle run_task intents by simulating task delegation.

        AI-177 / REQ-TECH-012: validate the task command against SandboxPolicy
        before delegating.  If the command is blocked, yield a clear error chunk
        and return without delegating.
        """
        task = intent.get("task", "")
        effective_agent = agent or "coding"
        await asyncio.sleep(0)

        # --- Security check (AI-177) ---
        policy = _get_sandbox_policy()
        if policy is not None and task:
            try:
                policy.check_command(task)
            except Exception as sec_exc:
                from dashboard.security import SecurityError
                if isinstance(sec_exc, SecurityError):
                    yield self._chunk(
                        "error",
                        f"Security policy violation: {sec_exc}",
                        {
                            "error_code": "SECURITY_COMMAND_BLOCKED",
                            "intent_type": INTENT_RUN_TASK,
                            "agent": effective_agent,
                            "task": task,
                            "session_id": session_id,
                        },
                    )
                    return
                # Re-raise unexpected errors
                raise

        yield self._chunk(
            "agent_response",
            f"Delegating task to {effective_agent} agent: {task}",
            {
                "intent_type": INTENT_RUN_TASK,
                "agent": effective_agent,
                "task": task,
                "session_id": session_id,
                "delegation_status": "delegated",
            },
        )
        await asyncio.sleep(0)
        yield self._chunk(
            "agent_response",
            f"{effective_agent.capitalize()} agent acknowledged the task and is executing.",
            {
                "intent_type": INTENT_RUN_TASK,
                "agent": effective_agent,
                "delegation_status": "executing",
                "session_id": session_id,
            },
        )

    def _check_file_security(self, path: str, session_id: Optional[str]) -> Optional[Dict[str, Any]]:
        """Validate *path* against the sandbox file-access policy.

        Returns a security error chunk dict if the path is blocked, or ``None``
        if the path is permitted.  Callers should yield the returned chunk and
        abort the operation when the return value is not ``None``.

        Args:
            path: The file-system path to validate.
            session_id: Session identifier for metadata.

        Returns:
            An error chunk dict, or ``None`` if access is permitted.
        """
        policy = _get_sandbox_policy()
        if policy is None or not path:
            return None

        try:
            policy.check_file(path)
            return None
        except Exception as sec_exc:
            from dashboard.security import SecurityError
            if isinstance(sec_exc, SecurityError):
                return self._chunk(
                    "error",
                    f"Security policy violation: {sec_exc}",
                    {
                        "error_code": "SECURITY_FILE_BLOCKED",
                        "path": path,
                        "session_id": session_id,
                    },
                )
            raise

    async def _handle_agent_delegation(
        self,
        intent: Dict[str, Any],
        agent: str,
        session_id: Optional[str],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Handle ask_agent intents by delegating to the specified agent.

        For AI provider agents (claude, chatgpt, gemini, groq, kimi, windsurf)
        the message is forwarded through the ProviderBridge (AI-174).
        For other agents the existing delegation simulation is used.
        """
        task = intent.get("task", "")
        await asyncio.sleep(0)

        # --- AI-174: provider bridge routing ---
        if agent in _PROVIDER_BRIDGE_NAMES:
            async for chunk in self._handle_provider_bridge(agent, task, session_id):
                yield chunk
            return

        # --- original delegation path ---
        yield self._chunk(
            "agent_response",
            f"Delegating to {agent} agent: {task}",
            {
                "intent_type": INTENT_ASK_AGENT,
                "agent": agent,
                "task": task,
                "session_id": session_id,
                "delegation_status": "delegated",
            },
        )
        await asyncio.sleep(0)
        yield self._chunk(
            "agent_response",
            f"{agent.capitalize()} agent is working on your request.",
            {
                "intent_type": INTENT_ASK_AGENT,
                "agent": agent,
                "delegation_status": "executing",
                "session_id": session_id,
            },
        )

    async def _handle_provider_bridge(
        self,
        provider: str,
        message: str,
        session_id: Optional[str],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Forward a message to the specified AI provider bridge (AI-174).

        Yields routing + response chunks.  Falls back gracefully if the
        bridge registry is unavailable or the provider is not configured.
        """
        yield self._chunk(
            "routing",
            f"Routing to {provider} via provider bridge.",
            {"agent": provider, "intent_type": INTENT_ASK_AGENT, "session_id": session_id},
        )
        await asyncio.sleep(0)

        registry = _get_provider_registry()
        if registry is None:
            yield self._chunk(
                "agent_response",
                f"[{provider.upper()}] Provider bridge unavailable. Echo: {message}",
                {
                    "agent": provider,
                    "session_id": session_id,
                    "delegation_status": "fallback",
                    "bridge_available": False,
                },
            )
            return

        try:
            bridge = registry.get(provider)
        except KeyError:
            yield self._chunk(
                "agent_response",
                f"[{provider.upper()}] Unknown provider; cannot route message.",
                {
                    "agent": provider,
                    "session_id": session_id,
                    "delegation_status": "error",
                    "bridge_available": False,
                },
            )
            return

        try:
            response_text = await bridge.send_message_async(message)
            yield self._chunk(
                "agent_response",
                response_text,
                {
                    "agent": provider,
                    "session_id": session_id,
                    "delegation_status": "completed",
                    "bridge_available": bridge.is_available(),
                    "provider": provider,
                },
            )
        except Exception as exc:
            logger.exception("Provider bridge error for %s: %s", provider, exc)
            yield self._chunk(
                "error",
                f"[{provider.upper()}] Bridge error: {exc}",
                {
                    "agent": provider,
                    "session_id": session_id,
                    "delegation_status": "error",
                    "error_code": "BRIDGE_ERROR",
                },
            )

    async def _handle_general(
        self, message: str, session_id: Optional[str]
    ) -> AsyncIterator[Dict[str, Any]]:
        """Handle general_chat intents with a helpful fallback response."""
        await asyncio.sleep(0)
        response = (
            "I received your message. No specific agent action was detected. "
            "You can ask me to:\n"
            "- Ask a coding agent to implement something\n"
            "- Run tests or tasks\n"
            "- Check agent status\n"
            "- Delegate to Linear, GitHub, or Slack agents\n"
            f"\nYour message: \"{message}\""
        )
        yield self._chunk(
            "agent_response",
            response,
            {
                "intent_type": INTENT_GENERAL_CHAT,
                "session_id": session_id,
                "fallback": True,
            },
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _chunk(
        chunk_type: str,
        content: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Build a response chunk dict with a UTC timestamp."""
        return {
            "type": chunk_type,
            "content": content,
            "metadata": metadata,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
