"""Chat Handler - Request Router for Chat-to-Agent Bridge.

This module routes incoming chat messages to the appropriate handler:
- agent_action intents -> AgentExecutor (Linear, coding, github agents)
- query intents -> Linear API or knowledge base
- conversation intents -> AI provider (Claude/ChatGPT/Gemini/etc.)

REQ-TECH-008: When the user sends a chat message requiring agent action,
the dashboard server must:
1. Parse user intent
2. Route to appropriate agent or let orchestrator decide
3. Execute delegation through existing session loop
4. Stream results back to chat

Concurrency:
    Uses asyncio.Queue to handle concurrent messages without dropping any.
    Each message gets its own task; the queue prevents overwhelming the system.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from dashboard.intent_parser import ParsedIntent, parse_intent
from dashboard.agent_executor import AgentExecutor, stream_intent_execution

logger = logging.getLogger(__name__)

# In-memory chat history (message_id -> message dict)
_chat_history: Dict[str, Dict] = {}

# Simple request queue for concurrency control
_request_queue: asyncio.Queue = asyncio.Queue(maxsize=50)

# Known AI provider names for conversation routing
AI_PROVIDERS = {"claude", "chatgpt", "gemini", "groq", "kimi", "windsurf"}

# ---------------------------------------------------------------------------
# Provider bridge integration (REQ-TECH-009 / AI-110)
# ---------------------------------------------------------------------------
# Lazily imported so ChatRouter degrades gracefully if provider_bridge has
# import issues (missing API keys, bridge module unavailable, etc.)

_provider_bridge_registry = None


def _get_provider_bridge_registry():
    """Lazily initialise and cache the BridgeRegistry singleton."""
    global _provider_bridge_registry
    if _provider_bridge_registry is None:
        try:
            from dashboard.provider_bridge import BridgeRegistry
            _provider_bridge_registry = BridgeRegistry()
        except Exception as exc:
            logger.warning("provider_bridge unavailable: %s", exc)
            _provider_bridge_registry = None
    return _provider_bridge_registry


class ChatRouter:
    """Routes chat messages to the appropriate handler.

    Responsibilities:
    1. Parse the message intent using IntentParser
    2. Route to AgentExecutor, Linear query, or conversation handler
    3. Return a routing decision for the caller
    4. Execute the routed action asynchronously

    Attributes:
        websockets: Optional set of WebSocket connections for streaming
        linear_api_key: Linear API key for issue queries
    """

    def __init__(
        self,
        websockets: Optional[Set[Any]] = None,
        linear_api_key: Optional[str] = None,
    ):
        """Initialize the router.

        Args:
            websockets: Active WebSocket connections for streaming results
            linear_api_key: Linear API key (defaults to LINEAR_API_KEY env var)
        """
        self.websockets = websockets or set()
        self.linear_api_key = linear_api_key
        self.executor = AgentExecutor(linear_api_key=linear_api_key)

    def parse(self, message: str) -> ParsedIntent:
        """Parse a user message into a structured intent.

        Args:
            message: Raw user message text

        Returns:
            ParsedIntent with intent_type, agent, action, and params
        """
        return parse_intent(message)

    def get_routing_decision(self, intent: ParsedIntent) -> Dict[str, Any]:
        """Determine how a message should be routed based on its intent.

        Args:
            intent: Parsed intent from parse()

        Returns:
            Dict with routing information:
                - intent_type: "agent_action" | "query" | "conversation"
                - handler: "agent_executor" | "linear_api" | "ai_provider"
                - agent: target agent name or None
                - action: action to perform or None
                - params: action parameters
                - description: human-readable routing description
        """
        if intent.intent_type == "agent_action":
            handler = "agent_executor"
            agent = intent.agent or "linear"
            description = (
                f"Routing to {agent} agent for action: {intent.action}"
            )

        elif intent.intent_type == "query":
            handler = "linear_api"
            agent = intent.agent
            description = (
                f"Querying {agent or 'knowledge base'} for: {intent.action}"
            )

        else:
            # conversation
            handler = "ai_provider"
            agent = None
            description = "Routing to AI provider for conversation"

        return {
            "intent_type": intent.intent_type,
            "handler": handler,
            "agent": agent,
            "action": intent.action,
            "params": intent.params,
            "description": description,
            "original_message": intent.original_message,
        }

    async def handle_message(
        self,
        message: str,
        provider: str = "claude",
        message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handle a chat message end-to-end.

        Parses intent, routes to appropriate handler, executes action,
        and returns the result.

        Args:
            message: Raw user message text
            provider: AI provider name (e.g., "claude", "chatgpt")
            message_id: Optional message ID for tracking

        Returns:
            Dict with:
                - message_id: str
                - routing: routing decision dict
                - response: str (the response text)
                - timestamp: ISO timestamp
                - provider: AI provider used
        """
        if message_id is None:
            message_id = str(uuid.uuid4())

        timestamp = datetime.utcnow().isoformat() + "Z"

        # Parse intent
        intent = self.parse(message)
        routing = self.get_routing_decision(intent)

        logger.info(
            f"[ChatRouter] Message '{message[:50]}...' -> "
            f"intent={intent.intent_type}, handler={routing['handler']}, "
            f"agent={routing['agent']}"
        )

        # Execute based on routing
        response = ""

        if routing["handler"] == "agent_executor":
            # Execute via AgentExecutor
            response = await stream_intent_execution(
                intent=intent,
                websockets=self.websockets if self.websockets else None,
                message_id=message_id,
                linear_api_key=self.linear_api_key,
            )

        elif routing["handler"] == "linear_api":
            # Direct Linear API query (same as agent_executor for now)
            response = await stream_intent_execution(
                intent=intent,
                websockets=self.websockets if self.websockets else None,
                message_id=message_id,
                linear_api_key=self.linear_api_key,
            )

        else:
            # conversation - route to ProviderBridgeRouter (REQ-TECH-009 / AI-110)
            response = await self._route_to_provider(message, provider)

        # Store in chat history
        result = {
            "message_id": message_id,
            "routing": routing,
            "response": response,
            "timestamp": timestamp,
            "provider": provider,
            "user_message": message,
        }
        _chat_history[message_id] = result

        return result

    async def _route_to_provider(
        self,
        message: str,
        provider: str = "claude",
        context: Optional[str] = None,
    ) -> str:
        """Route a conversation message to the specified AI provider bridge.

        Uses the ProviderBridgeRouter (BridgeRegistry) to forward the message
        to the appropriate AI provider bridge (REQ-TECH-009 / AI-110).

        Args:
            message: The user's message text
            provider: The AI provider name (claude, chatgpt, gemini, groq, kimi, windsurf)
            context: Optional system/context string to pass to the provider

        Returns:
            The provider's response text, or a fallback message if unavailable
        """
        registry = _get_provider_bridge_registry()
        provider_name = provider.capitalize()

        if registry is None:
            logger.warning(
                "ProviderBridgeRegistry unavailable; using placeholder for %s", provider
            )
            return (
                f"[{provider_name}] I understand your question. "
                f"This message will be processed by the {provider_name} AI provider."
            )

        try:
            bridge = registry.get(provider)
        except KeyError:
            logger.warning("Unknown provider '%s'; using placeholder response", provider)
            return (
                f"[{provider_name}] Unknown provider. "
                f"Available providers: claude, chatgpt, gemini, groq, kimi, windsurf."
            )

        logger.info(
            "[ChatRouter] Routing conversation to provider=%s, available=%s",
            provider,
            bridge.is_available(),
        )

        try:
            response = await bridge.send_message_async(message, context=context)
            return response
        except Exception as exc:
            logger.error(
                "[ChatRouter] Provider bridge error for %s: %s", provider, exc
            )
            return (
                f"[{provider_name}] Error communicating with provider: {exc}. "
                f"Please check your API configuration."
            )


    async def enqueue_message(
        self,
        message: str,
        provider: str = "claude",
        message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Enqueue a message for processing with concurrency control.

        If the queue is full, returns an error response immediately.

        Args:
            message: Raw user message text
            provider: AI provider name
            message_id: Optional message ID

        Returns:
            Same as handle_message()
        """
        if message_id is None:
            message_id = str(uuid.uuid4())

        try:
            # Try to put in queue (non-blocking check)
            _request_queue.put_nowait(message_id)
        except asyncio.QueueFull:
            logger.warning(f"Request queue full, rejecting message: {message[:30]}")
            return {
                "message_id": message_id,
                "routing": {
                    "intent_type": "error",
                    "handler": "none",
                    "description": "Server busy - request queue full",
                },
                "response": "The server is busy processing other requests. Please try again in a moment.",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "provider": provider,
                "user_message": message,
                "error": "queue_full",
            }

        try:
            result = await self.handle_message(message, provider, message_id)
        finally:
            # Drain our slot from the queue
            try:
                _request_queue.get_nowait()
                _request_queue.task_done()
            except asyncio.QueueEmpty:
                pass

        return result


# ---------------------------------------------------------------------------
# Model mapping helpers
# ---------------------------------------------------------------------------

_CLAUDE_MODEL_MAP = {
    "haiku-4.5": "claude-3-5-haiku-20241022",
    "sonnet-4.5": "claude-3-5-sonnet-20241022",
    "opus-4.6": "claude-3-opus-20240229",
    "haiku": "claude-3-5-haiku-20241022",
    "sonnet": "claude-3-5-sonnet-20241022",
    "opus": "claude-3-opus-20240229",
}

_OPENAI_MODEL_MAP = {
    "gpt-4o": "gpt-4o",
    "o1": "o1-preview",
    "o3-mini": "o3-mini",
    "o4-mini": "o4-mini",
}


def map_model_to_api(provider: str, model: str) -> str:
    """Map a dashboard model identifier to the provider API model name.

    Args:
        provider: Provider name ('claude', 'openai', etc.)
        model: Dashboard model identifier (e.g., 'sonnet-4.5', 'gpt-4o')

    Returns:
        The API model name, or the original model string if no mapping exists.
    """
    if provider == "claude":
        return _CLAUDE_MODEL_MAP.get(model, model)
    if provider == "openai":
        return _OPENAI_MODEL_MAP.get(model, model)
    return model


# ---------------------------------------------------------------------------
# Mock streaming with tool transparency
# ---------------------------------------------------------------------------

async def stream_mock_response(message: str, provider_name: str, model: str):
    """Yield mock streaming chunks with tool-transparency formatting.

    Produces realistic chunk sequences including tool_use, tool_result, and
    text chunks with timestamps. The response content depends on keywords in
    the message to mimic agent routing.

    Chunk types yielded:
      - {'type': 'tool_use', 'tool_name': ..., 'tool_input': ..., 'tool_id': ..., 'timestamp': ...}
      - {'type': 'tool_result', 'tool_id': ..., 'result': ..., 'timestamp': ...}
      - {'type': 'text', 'content': ..., 'timestamp': ...}
      - {'type': 'done', 'timestamp': ...}

    Args:
        message: User message (used for keyword routing)
        provider_name: Provider display name (e.g., 'Claude', 'OpenAI')
        model: Model identifier
    """
    import uuid
    from datetime import datetime, timezone

    def _ts() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    msg_lower = message.lower()

    # Determine routing based on message keywords
    if any(k in msg_lower for k in ("linear", "issue", "ticket", "sprint", "backlog")):
        tool_id = str(uuid.uuid4())[:8]
        yield {
            "type": "tool_use",
            "tool_name": "Linear_listIssues",
            "tool_input": {"query": message},
            "tool_id": tool_id,
            "timestamp": _ts(),
        }
        yield {
            "type": "tool_result",
            "tool_id": tool_id,
            "result": "Found 3 open issues: AI-100, AI-101, AI-102",
            "timestamp": _ts(),
        }
        yield {
            "type": "text",
            "content": (
                f"[{provider_name}/{model}] I found 3 open Linear issues for you. "
                f"Here's a summary: AI-100 (In Progress), AI-101 (Todo), AI-102 (Todo)."
            ),
            "timestamp": _ts(),
        }

    elif any(k in msg_lower for k in ("github", "pr", "pull request", "commit", "repo")):
        tool_id = str(uuid.uuid4())[:8]
        yield {
            "type": "tool_use",
            "tool_name": "Github_ListPullRequests",
            "tool_input": {"query": message},
            "tool_id": tool_id,
            "timestamp": _ts(),
        }
        yield {
            "type": "tool_result",
            "tool_id": tool_id,
            "result": "Found 2 open PRs: #45, #46",
            "timestamp": _ts(),
        }
        yield {
            "type": "text",
            "content": f"[{provider_name}/{model}] Found 2 open pull requests: #45 and #46.",
            "timestamp": _ts(),
        }

    elif any(k in msg_lower for k in ("slack", "channel", "message", "notification")):
        tool_id = str(uuid.uuid4())[:8]
        yield {
            "type": "tool_use",
            "tool_name": "slack_channels_list",
            "tool_input": {"query": message},
            "tool_id": tool_id,
            "timestamp": _ts(),
        }
        yield {
            "type": "tool_result",
            "tool_id": tool_id,
            "result": "Found Slack messages in #general and #engineering",
            "timestamp": _ts(),
        }
        yield {
            "type": "text",
            "content": f"[{provider_name}/{model}] Retrieved Slack messages from #general.",
            "timestamp": _ts(),
        }

    elif any(k in msg_lower for k in ("code", "implement", "function", "class", "script")):
        yield {
            "type": "text",
            "content": (
                f"[{provider_name}/{model}] Here's a Python example:\n\n"
                "```python\n"
                "def example():\n"
                "    \"\"\"Example function.\"\"\"\n"
                "    return 'Hello, World!'\n"
                "```\n"
            ),
            "timestamp": _ts(),
        }

    else:
        # Generic conversational response
        yield {
            "type": "text",
            "content": (
                f"[{provider_name}/{model}] I understand your question. "
                f"I'm a demo response from {provider_name} ({model}). "
                f"Configure real API keys for live responses."
            ),
            "timestamp": _ts(),
        }

    yield {"type": "done", "timestamp": _ts()}


# ---------------------------------------------------------------------------
# Provider-specific streaming (real API)
# ---------------------------------------------------------------------------

async def stream_claude_response(message: str, model: str = "sonnet-4.5",
                                  history: Optional[List[Dict]] = None):
    """Stream a response from the Claude (Anthropic) provider bridge.

    Yields dicts with 'type' key ('text', 'error', 'done').
    Falls back to mock streaming if bridge is unavailable.

    Args:
        message: User message text
        model: Claude model identifier (default: 'sonnet-4.5')
        history: Optional conversation history
    """
    async for chunk in _stream_provider_response(message, "claude", model, history):
        yield chunk


async def stream_openai_response(message: str, model: str = "gpt-4o",
                                  history: Optional[List[Dict]] = None):
    """Stream a response from the OpenAI provider bridge.

    Yields dicts with 'type' key ('text', 'error', 'done').
    Falls back to mock streaming if bridge is unavailable.

    Args:
        message: User message text
        model: OpenAI model identifier (default: 'gpt-4o')
        history: Optional conversation history
    """
    async for chunk in _stream_provider_response(message, "openai", model, history):
        yield chunk


def get_chat_history(limit: int = 100) -> List[Dict]:
    """Get recent chat history.

    Args:
        limit: Maximum number of messages to return

    Returns:
        List of chat message dicts, most recent last
    """
    messages = list(_chat_history.values())
    # Sort by timestamp, return most recent `limit` entries
    messages.sort(key=lambda m: m.get("timestamp", ""))
    return messages[-limit:]


def clear_chat_history() -> None:
    """Clear the in-memory chat history (for testing)."""
    _chat_history.clear()


# ---------------------------------------------------------------------------
# Streaming provider response functions (REQ-TECH-009 multi-provider)
# ---------------------------------------------------------------------------

async def _stream_provider_response(message: str, provider: str, model: Optional[str] = None,
                                     history: Optional[List[Dict]] = None):
    """Internal async generator that streams chunks from a provider bridge.

    Yields dicts with 'type' key:
      - {'type': 'text', 'text': '...'} for response text
      - {'type': 'error', 'text': '...'} for errors
      - {'type': 'done'} always last

    Args:
        message: The user message
        provider: Provider name (gemini, groq, kimi, etc.)
        model: Model identifier (optional)
        history: Conversation history (optional)
    """
    registry = _get_provider_bridge_registry()

    if registry is None:
        yield {"type": "error", "text": f"Provider bridge registry unavailable for '{provider}'"}
        yield {"type": "done"}
        return

    try:
        bridge = registry.get(provider)
    except (KeyError, AttributeError):
        # Unknown provider - yield error
        yield {"type": "error", "text": f"Unknown provider: '{provider}'"}
        yield {"type": "done"}
        return

    if not bridge.is_available():
        yield {"type": "error", "text": f"Provider '{provider}' bridge not available (check API key)"}
        yield {"type": "done"}
        return

    try:
        context = None
        if history:
            context = "\n".join(
                f"{m['role']}: {m['content']}" for m in history if isinstance(m, dict)
            )
        response = await bridge.send_message_async(message, context=context)
        if response:
            yield {"type": "text", "text": response}
        yield {"type": "done"}
    except Exception as exc:
        logger.error("[stream_provider] Error from '%s': %s", provider, exc)
        yield {"type": "error", "text": str(exc)}
        yield {"type": "done"}


async def stream_gemini_response(message: str, model: str = "2.5-flash",
                                  history: Optional[List[Dict]] = None):
    """Stream a response from the Gemini provider bridge.

    Yields dicts with 'type' key ('text', 'error', 'done').
    Produces error chunks if the bridge is unavailable.

    Args:
        message: User message text
        model: Gemini model identifier (default: '2.5-flash')
        history: Optional conversation history
    """
    async for chunk in _stream_provider_response(message, "gemini", model, history):
        yield chunk


async def stream_groq_response(message: str, model: str = "llama-3.3-70b",
                                history: Optional[List[Dict]] = None):
    """Stream a response from the Groq provider bridge.

    Yields dicts with 'type' key ('text', 'error', 'done').
    Produces error chunks if the bridge is unavailable.

    Args:
        message: User message text
        model: Groq model identifier (default: 'llama-3.3-70b')
        history: Optional conversation history
    """
    async for chunk in _stream_provider_response(message, "groq", model, history):
        yield chunk


async def stream_kimi_response(message: str, model: str = "moonshot-v1",
                                history: Optional[List[Dict]] = None):
    """Stream a response from the KIMI (Moonshot AI) provider bridge.

    Yields dicts with 'type' key ('text', 'error', 'done').
    Produces error chunks if the bridge is unavailable.

    Args:
        message: User message text
        model: KIMI model identifier (default: 'moonshot-v1')
        history: Optional conversation history
    """
    async for chunk in _stream_provider_response(message, "kimi", model, history):
        yield chunk


async def stream_chat_response(message: str, provider: str = "claude",
                                model: Optional[str] = None,
                                history: Optional[List[Dict]] = None,
                                conversation_history: Optional[List[Dict]] = None):
    """Stream a chat response, routing to the specified provider with mock fallback.

    Unlike the provider-specific streaming functions, this function always
    produces at least one text chunk — falling back to a mock response if the
    provider bridge is unavailable.  This supports hot-swap UX where the UI
    stays functional regardless of API key configuration.

    Yields dicts with 'type' key ('text', 'error', 'done').
    Text chunks include both 'text' and 'content' keys for compatibility.

    Args:
        message: User message text
        provider: AI provider name (claude, openai, gemini, groq, kimi, windsurf)
        model: Model identifier (optional)
        history: Optional conversation history list of {'role', 'content'} dicts
        conversation_history: Alias for history parameter
    """
    # Accept either parameter name
    effective_history = history or conversation_history

    registry = _get_provider_bridge_registry()
    provider_display = provider.capitalize()

    got_text = False

    if registry is not None:
        try:
            bridge = registry.get(provider)
            if bridge.is_available():
                try:
                    context = None
                    if effective_history:
                        context = "\n".join(
                            f"{m['role']}: {m['content']}"
                            for m in effective_history if isinstance(m, dict)
                        )
                    response = await bridge.send_message_async(message, context=context)
                    if response:
                        # Include both 'text' and 'content' keys for compatibility
                        yield {"type": "text", "text": response, "content": response}
                        got_text = True
                except Exception as exc:
                    logger.error("[stream_chat] Bridge error for '%s': %s", provider, exc)
                    yield {"type": "error", "text": str(exc)}
        except (KeyError, AttributeError):
            pass  # Unknown provider — fall through to mock

    if not got_text:
        # Mock fallback: always produce a text response so UI stays functional
        mock_text = (
            f"[{provider_display}] I understand your question. "
            f"This is a demo response — configure an API key for {provider_display} to "
            f"get real responses."
        )
        # Include both 'text' and 'content' keys for compatibility with different test expectations
        yield {
            "type": "text",
            "text": mock_text,
            "content": mock_text,
        }

    yield {"type": "done"}
