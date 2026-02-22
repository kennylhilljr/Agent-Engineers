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


async def stream_chat_response(
    message: str,
    provider: str = "claude",
    model: Optional[str] = None,
    history: Optional[List[Dict]] = None,
    conversation_history: Optional[List[Dict]] = None,
) -> Any:
    """Stream a chat response, routing to the specified AI provider with mock fallback.

    Unlike the provider-specific streaming functions, this function always
    produces at least one text chunk — falling back to a mock response if the
    provider bridge is unavailable.  This supports hot-swap UX where the UI
    stays functional regardless of API key configuration.

    Yields dicts with 'type' key ('text', 'error', 'done', 'token').
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
                            f"{m.get('role', m.get('sender', 'user'))}: {m.get('content', m.get('text', ''))}"
                            for m in effective_history[-10:] if isinstance(m, dict)
                        )
                    response = await bridge.send_message_async(message, context=context)
                    if response:
                        # Stream response word by word for better UX
                        words = response.split()
                        chunk_size = 5  # words per chunk

                        for i in range(0, len(words), chunk_size):
                            chunk = " ".join(words[i:i + chunk_size]) + " "
                            # Yield token chunks for streaming
                            yield {
                                "type": "token",
                                "text": chunk,
                                "content": chunk,
                                "timestamp": datetime.utcnow().isoformat() + "Z",
                                "provider": provider,
                                "model": model or "default",
                            }
                            await asyncio.sleep(0.05)  # Simulate streaming delay

                        # Final text chunk with complete response
                        yield {
                            "type": "text",
                            "text": response,
                            "content": response,
                            "timestamp": datetime.utcnow().isoformat() + "Z",
                            "provider": provider,
                            "model": model or "default",
                        }
                        got_text = True
                except Exception as exc:
                    logger.error("[stream_chat] Bridge error for '%s': %s", provider, exc)
                    yield {
                        "type": "error",
                        "text": str(exc),
                        "content": str(exc),
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                    }
        except (KeyError, AttributeError):
            pass  # Unknown provider — fall through to mock

    if not got_text:
        # Mock fallback: always produce a text response so UI stays functional
        mock_text = (
            f"Configure an API key for {provider_display} in Settings to get real responses. "
            f"This is a demo response to keep the UI functional."
        )
        # Include both 'text' and 'content' keys for compatibility with different test expectations
        yield {
            "type": "text",
            "text": mock_text,
            "content": mock_text,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "provider": provider,
            "model": model or "default",
        }

    yield {
        "type": "done",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
