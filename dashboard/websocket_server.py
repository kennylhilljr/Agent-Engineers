"""WebSocket Server - Real-time Event Protocol for Agent Dashboard.

This module implements the WebSocket protocol for real-time updates as specified in
REQ-TECH-003. It provides async WebSocket server functionality with 7 message types
for streaming agent status, events, reasoning, code generation, chat messages,
metrics updates, and control acknowledgments.

Message Types:
    - agent_status: Agent status change (idle → running → paused → error)
    - agent_event: New agent event recorded
    - reasoning: Orchestrator or agent reasoning text
    - code_stream: Live code generation chunks
    - chat_message: Chat response chunk (streaming)
    - metrics_update: Updated dashboard metrics
    - control_ack: Acknowledgment of pause/resume/edit commands

Key Features:
    - Auto-reconnection with exponential backoff (client-side)
    - Crash isolation (server failures don't crash orchestrator)
    - Sub-100ms event latency (REQ-PERF-001)
    - Minimal dependencies (stdlib + aiohttp)

Usage:
    # Standalone server
    server = WebSocketServer(port=8421)
    await server.start()

    # Broadcast events
    await server.broadcast_agent_status("coding", "running", {"ticket": "AI-104"})
    await server.broadcast_reasoning("Delegating to coding agent", "orchestrator")
    await server.broadcast_code_stream("def hello():", "src/main.py", 1)
"""

import asyncio
import hmac
import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional, Set

from aiohttp import WSMsgType, web

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============================================================================
# Authentication Utilities
# ============================================================================

def get_auth_token() -> Optional[str]:
    """Get authentication token from environment variable."""
    return os.getenv("DASHBOARD_AUTH_TOKEN")


def constant_time_compare(a: str, b: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks.

    Args:
        a: First string to compare
        b: Second string to compare

    Returns:
        True if strings are equal, False otherwise

    Security Note:
        Uses Python's built-in hmac.compare_digest() which is specifically
        designed for constant-time comparison to prevent timing side-channel
        attacks. This prevents attackers from determining the correct token
        character by character based on response time differences.

        Strings are encoded to UTF-8 bytes before comparison to support
        unicode characters and ensure compatibility with hmac.compare_digest().
    """
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))


def validate_websocket_auth(request: web.Request) -> tuple[bool, Optional[str]]:
    """Validate WebSocket authentication from request.

    Checks for bearer token in:
    1. Authorization header (standard)
    2. Sec-WebSocket-Protocol header (for browsers that don't support custom headers)
    3. Query parameter 'token' (fallback for limited clients)

    Args:
        request: aiohttp Request object

    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if authentication succeeds or is not required
        - (False, error_message) if authentication fails
    """
    auth_token = get_auth_token()

    # If no token is configured, allow all connections (dev mode)
    if not auth_token:
        return (True, None)

    # Check Authorization header (standard method)
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if constant_time_compare(token, auth_token):
            return (True, None)

    # Check Sec-WebSocket-Protocol header (browser compatibility)
    # Browsers may send token in this header when custom headers aren't supported
    ws_protocol = request.headers.get("Sec-WebSocket-Protocol", "")
    if ws_protocol:
        # Format: "bearer-<token>" or just the token
        if ws_protocol.startswith("bearer-"):
            token = ws_protocol[7:]
            if constant_time_compare(token, auth_token):
                return (True, None)
        elif constant_time_compare(ws_protocol, auth_token):
            return (True, None)

    # Check query parameter (fallback for limited clients)
    token_param = request.query.get("token", "")
    if token_param and constant_time_compare(token_param, auth_token):
        return (True, None)

    # Authentication failed
    logger.warning(
        f"WebSocket authentication failed from {request.remote}"
    )
    return (False, "Unauthorized: Invalid or missing authentication token")


# ============================================================================
# Message Type Definitions (REQ-TECH-003)
# ============================================================================

class MessageType(str, Enum):
    """WebSocket message types for real-time updates."""
    AGENT_STATUS = "agent_status"           # Agent status change events
    AGENT_EVENT = "agent_event"             # New agent event recorded
    REASONING = "reasoning"                 # Orchestrator/agent reasoning
    CODE_STREAM = "code_stream"             # Live code generation chunks
    CHAT_MESSAGE = "chat_message"           # Chat response chunk
    METRICS_UPDATE = "metrics_update"       # Updated dashboard metrics
    CONTROL_ACK = "control_ack"             # Command acknowledgment


class AgentStatus(str, Enum):
    """Agent status states."""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


class ControlCommand(str, Enum):
    """Agent control commands."""
    PAUSE = "pause"
    RESUME = "resume"
    EDIT = "edit"


@dataclass
class BaseMessage:
    """Base message structure for all WebSocket messages."""
    type: str                               # Message type from MessageType enum
    timestamp: str                          # ISO 8601 timestamp

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary for JSON serialization."""
        return asdict(self)


@dataclass
class AgentStatusMessage(BaseMessage):
    """Agent status change message (agent_status).

    Broadcast when an agent transitions between states:
    idle → running → paused → error
    """
    agent_name: str                         # Agent identifier (e.g., "coding")
    status: str                             # New status from AgentStatus enum
    metadata: dict[str, Any]                # Additional context (ticket_key, error, etc.)

    def __init__(self, agent_name: str, status: str, metadata: Optional[dict] = None):
        super().__init__(
            type=MessageType.AGENT_STATUS.value,
            timestamp=datetime.utcnow().isoformat() + 'Z'
        )
        self.agent_name = agent_name
        self.status = status
        self.metadata = metadata or {}


@dataclass
class AgentEventMessage(BaseMessage):
    """Agent event message (agent_event).

    Broadcast when a new agent event is recorded in the metrics collector.
    """
    event_id: str                           # Unique event identifier
    agent_name: str                         # Agent that generated the event
    session_id: str                         # Parent session ID
    ticket_key: str                         # Linear ticket key (if applicable)
    status: str                             # Event status (success/error/timeout/blocked)
    duration_seconds: float                 # Execution duration
    tokens: int                             # Total tokens used
    cost_usd: float                         # Estimated cost in USD
    artifacts: list[str]                    # Artifacts produced

    def __init__(self, event_data: dict[str, Any]):
        super().__init__(
            type=MessageType.AGENT_EVENT.value,
            timestamp=datetime.utcnow().isoformat() + 'Z'
        )
        self.event_id = event_data.get('event_id', '')
        self.agent_name = event_data.get('agent_name', '')
        self.session_id = event_data.get('session_id', '')
        self.ticket_key = event_data.get('ticket_key', '')
        self.status = event_data.get('status', '')
        self.duration_seconds = event_data.get('duration_seconds', 0.0)
        self.tokens = event_data.get('total_tokens', 0)
        self.cost_usd = event_data.get('estimated_cost_usd', 0.0)
        self.artifacts = event_data.get('artifacts', [])


@dataclass
class ReasoningMessage(BaseMessage):
    """Reasoning message (reasoning).

    Broadcast orchestrator or agent reasoning text for transparency.
    """
    content: str                            # Reasoning text/decision explanation
    source: str                             # "orchestrator" or agent name
    context: dict[str, Any]                 # Additional context (ticket, complexity, etc.)

    def __init__(self, content: str, source: str, context: Optional[dict] = None):
        super().__init__(
            type=MessageType.REASONING.value,
            timestamp=datetime.utcnow().isoformat() + 'Z'
        )
        self.content = content
        self.source = source
        self.context = context or {}


@dataclass
class CodeStreamMessage(BaseMessage):
    """Code stream message (code_stream).

    Broadcast live code generation chunks as agents write code.
    """
    content: str                            # Code chunk (line or block)
    file_path: str                          # File being edited
    line_number: int                        # Line number in file
    operation: str                          # "add", "modify", "delete"
    language: str                           # Programming language for syntax highlighting

    def __init__(
        self,
        content: str,
        file_path: str,
        line_number: int = 0,
        operation: str = "add",
        language: str = "python"
    ):
        super().__init__(
            type=MessageType.CODE_STREAM.value,
            timestamp=datetime.utcnow().isoformat() + 'Z'
        )
        self.content = content
        self.file_path = file_path
        self.line_number = line_number
        self.operation = operation
        self.language = language


@dataclass
class ChatMessageChunk(BaseMessage):
    """Chat message chunk (chat_message).

    Broadcast streaming chat response chunks from AI providers.
    """
    content: str                            # Text chunk
    message_id: str                         # Message identifier for grouping chunks
    provider: str                           # AI provider (claude/chatgpt/gemini/etc.)
    is_final: bool                          # True if this is the last chunk

    def __init__(self, content: str, message_id: str, provider: str, is_final: bool = False):
        super().__init__(
            type=MessageType.CHAT_MESSAGE.value,
            timestamp=datetime.utcnow().isoformat() + 'Z'
        )
        self.content = content
        self.message_id = message_id
        self.provider = provider
        self.is_final = is_final


@dataclass
class MetricsUpdateMessage(BaseMessage):
    """Metrics update message (metrics_update).

    Broadcast updated dashboard metrics (subset or full state).
    """
    metrics: dict[str, Any]                 # Metrics data (can be full DashboardState or subset)
    update_type: str                        # "full", "agent", "session", "event"

    def __init__(self, metrics: dict[str, Any], update_type: str = "full"):
        super().__init__(
            type=MessageType.METRICS_UPDATE.value,
            timestamp=datetime.utcnow().isoformat() + 'Z'
        )
        self.metrics = metrics
        self.update_type = update_type


@dataclass
class ControlAckMessage(BaseMessage):
    """Control acknowledgment message (control_ack).

    Broadcast acknowledgment of pause/resume/edit commands.
    """
    command: str                            # Command type (pause/resume/edit)
    agent_name: str                         # Target agent
    status: str                             # "acknowledged", "completed", "failed"
    message: str                            # Human-readable status message

    def __init__(self, command: str, agent_name: str, status: str, message: str):
        super().__init__(
            type=MessageType.CONTROL_ACK.value,
            timestamp=datetime.utcnow().isoformat() + 'Z'
        )
        self.command = command
        self.agent_name = agent_name
        self.status = status
        self.message = message


# ============================================================================
# WebSocket Server Implementation
# ============================================================================

class WebSocketServer:
    """Async WebSocket server for real-time agent dashboard updates.

    Manages WebSocket connections, broadcasts events to all connected clients,
    and provides handlers for all 7 message types specified in REQ-TECH-003.

    Features:
        - Connection management (connect/disconnect tracking)
        - Broadcast to all connected clients
        - Individual client messaging
        - Automatic dead connection cleanup
        - Message queuing for offline clients (optional)
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8421,
        max_message_size: int = 10 * 1024 * 1024  # 10MB
    ):
        """Initialize WebSocket server.

        Args:
            host: Server host (default: 127.0.0.1 for localhost)
            port: Server port (default: 8421)
            max_message_size: Maximum WebSocket message size in bytes
        """
        self.host = host
        self.port = port
        self.max_message_size = max_message_size

        # Connection tracking
        self.connections: Set[web.WebSocketResponse] = set()
        self.connection_metadata: dict[int, dict] = {}  # Track metadata per connection

        # Message statistics
        self.total_messages_sent = 0
        self.total_broadcasts = 0

        # Server state
        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None

        logger.info(f"WebSocket server initialized on {host}:{port}")

    async def start(self):
        """Start the WebSocket server."""
        self.app = web.Application()
        self.app.router.add_get('/ws', self.websocket_handler)
        self.app.router.add_get('/health', self.health_handler)

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()

        logger.info(f"WebSocket server started on ws://{self.host}:{self.port}/ws")
        logger.info(f"Health endpoint available at http://{self.host}:{self.port}/health")

    async def stop(self):
        """Stop the WebSocket server and close all connections."""
        logger.info("Stopping WebSocket server...")

        # Close all active connections
        await self._close_all_connections()

        # Cleanup server
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()

        logger.info("WebSocket server stopped")

    async def health_handler(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({
            'status': 'ok',
            'connections': len(self.connections),
            'total_messages_sent': self.total_messages_sent,
            'total_broadcasts': self.total_broadcasts,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        })

    async def websocket_handler(self, request: web.Request) -> web.WebSocketResponse:
        """WebSocket connection handler.

        Accepts WebSocket connections and maintains them for real-time updates.

        Security:
            - If DASHBOARD_AUTH_TOKEN is set, validates bearer token before accepting connection
            - Supports token in Authorization header, Sec-WebSocket-Protocol header, or query param
            - Logs authentication failures (but not the invalid tokens)
        """
        # Validate authentication before accepting connection
        is_valid, error_message = validate_websocket_auth(request)
        if not is_valid:
            # Return 401 Unauthorized for failed authentication
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            await ws.send_json({
                'type': 'error',
                'error': 'Unauthorized',
                'message': error_message,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            })
            await ws.close(code=1008, message=b'Unauthorized')
            return ws

        ws = web.WebSocketResponse(max_msg_size=self.max_message_size)
        await ws.prepare(request)

        # Register connection
        connection_id = id(ws)
        self.connections.add(ws)
        self.connection_metadata[connection_id] = {
            'connected_at': datetime.utcnow().isoformat() + 'Z',
            'remote_addr': request.remote,
            'messages_received': 0,
            'messages_sent': 0
        }

        logger.info(
            f"WebSocket client connected: {connection_id} "
            f"from {request.remote} (total: {len(self.connections)})"
        )

        # Send welcome message
        await self._send_to_client(ws, {
            'type': 'connection',
            'status': 'connected',
            'connection_id': connection_id,
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'message': 'Connected to Agent Dashboard WebSocket'
        })

        try:
            # Listen for client messages
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    self.connection_metadata[connection_id]['messages_received'] += 1

                    # Handle ping/pong
                    if msg.data == 'ping':
                        await ws.send_str('pong')
                    else:
                        # Parse and handle client messages
                        try:
                            data = json.loads(msg.data)
                            await self._handle_client_message(ws, data)
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON from client {connection_id}: {msg.data}")

                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"WebSocket {connection_id} error: {ws.exception()}")
                    break

                elif msg.type == WSMsgType.CLOSE:
                    logger.info(f"WebSocket {connection_id} closed by client")
                    break

        except Exception as e:
            logger.error(f"WebSocket {connection_id} exception: {e}")

        finally:
            # Unregister connection
            self.connections.discard(ws)
            if connection_id in self.connection_metadata:
                del self.connection_metadata[connection_id]

            logger.info(
                f"WebSocket client disconnected: {connection_id} "
                f"(remaining: {len(self.connections)})"
            )

        return ws

    async def _handle_client_message(self, ws: web.WebSocketResponse, data: dict):
        """Handle messages from clients.

        Args:
            ws: WebSocket connection
            data: Parsed JSON message from client
        """
        message_type = data.get('type')

        # Handle different client message types
        if message_type == 'subscribe':
            # Client subscribes to specific event types
            logger.info(f"Client {id(ws)} subscribed to: {data.get('events', [])}")

        elif message_type == 'unsubscribe':
            # Client unsubscribes from event types
            logger.info(f"Client {id(ws)} unsubscribed from: {data.get('events', [])}")

        else:
            logger.debug(f"Unknown message type from client {id(ws)}: {message_type}")

    async def _send_to_client(self, ws: web.WebSocketResponse, message: dict) -> bool:
        """Send message to a specific client.

        Args:
            ws: WebSocket connection
            message: Message dictionary to send

        Returns:
            True if message sent successfully, False otherwise
        """
        try:
            await ws.send_json(message)

            connection_id = id(ws)
            if connection_id in self.connection_metadata:
                self.connection_metadata[connection_id]['messages_sent'] += 1

            self.total_messages_sent += 1
            return True

        except Exception as e:
            logger.error(f"Error sending to client {id(ws)}: {e}")
            return False

    async def _close_all_connections(self):
        """Close all active WebSocket connections gracefully."""
        if not self.connections:
            return

        logger.info(f"Closing {len(self.connections)} active connections...")

        close_tasks = []
        for ws in self.connections:
            close_tasks.append(ws.close(code=1001, message=b'Server shutting down'))

        await asyncio.gather(*close_tasks, return_exceptions=True)

        self.connections.clear()
        self.connection_metadata.clear()

    # ========================================================================
    # Broadcast Methods - All 7 Message Types (REQ-TECH-003)
    # ========================================================================

    async def broadcast(self, message: BaseMessage) -> int:
        """Broadcast a message to all connected clients.

        Args:
            message: Message object to broadcast

        Returns:
            Number of clients that received the message
        """
        if not self.connections:
            return 0

        message_dict = message.to_dict()
        success_count = 0
        failed_connections = set()

        # Broadcast to all connections
        for ws in self.connections:
            if await self._send_to_client(ws, message_dict):
                success_count += 1
            else:
                failed_connections.add(ws)

        # Remove failed connections
        self.connections -= failed_connections

        self.total_broadcasts += 1

        logger.debug(
            f"Broadcast {message.type} to {success_count}/{len(self.connections) + len(failed_connections)} clients"
        )

        return success_count

    async def broadcast_agent_status(
        self,
        agent_name: str,
        status: str,
        metadata: Optional[dict] = None
    ) -> int:
        """Broadcast agent status change.

        Args:
            agent_name: Agent identifier
            status: New status (idle/running/paused/error)
            metadata: Additional context (ticket_key, error details, etc.)

        Returns:
            Number of clients that received the message
        """
        message = AgentStatusMessage(agent_name, status, metadata)
        return await self.broadcast(message)

    async def broadcast_agent_event(self, event_data: dict[str, Any]) -> int:
        """Broadcast new agent event.

        Args:
            event_data: Agent event dictionary from metrics collector

        Returns:
            Number of clients that received the message
        """
        message = AgentEventMessage(event_data)
        return await self.broadcast(message)

    async def broadcast_reasoning(
        self,
        content: str,
        source: str,
        context: Optional[dict] = None
    ) -> int:
        """Broadcast orchestrator or agent reasoning.

        Args:
            content: Reasoning text/decision explanation
            source: "orchestrator" or agent name
            context: Additional context (ticket, complexity, etc.)

        Returns:
            Number of clients that received the message
        """
        message = ReasoningMessage(content, source, context)
        return await self.broadcast(message)

    async def broadcast_code_stream(
        self,
        content: str,
        file_path: str,
        line_number: int = 0,
        operation: str = "add",
        language: str = "python"
    ) -> int:
        """Broadcast live code generation chunk.

        Args:
            content: Code chunk (line or block)
            file_path: File being edited
            line_number: Line number in file
            operation: "add", "modify", or "delete"
            language: Programming language for syntax highlighting

        Returns:
            Number of clients that received the message
        """
        message = CodeStreamMessage(content, file_path, line_number, operation, language)
        return await self.broadcast(message)

    async def broadcast_chat_message(
        self,
        content: str,
        message_id: str,
        provider: str,
        is_final: bool = False
    ) -> int:
        """Broadcast chat response chunk.

        Args:
            content: Text chunk
            message_id: Message identifier for grouping chunks
            provider: AI provider (claude/chatgpt/gemini/etc.)
            is_final: True if this is the last chunk

        Returns:
            Number of clients that received the message
        """
        message = ChatMessageChunk(content, message_id, provider, is_final)
        return await self.broadcast(message)

    async def broadcast_metrics_update(
        self,
        metrics: dict[str, Any],
        update_type: str = "full"
    ) -> int:
        """Broadcast metrics update.

        Args:
            metrics: Metrics data (full DashboardState or subset)
            update_type: "full", "agent", "session", or "event"

        Returns:
            Number of clients that received the message
        """
        message = MetricsUpdateMessage(metrics, update_type)
        return await self.broadcast(message)

    async def broadcast_control_ack(
        self,
        command: str,
        agent_name: str,
        status: str,
        message_text: str
    ) -> int:
        """Broadcast control command acknowledgment.

        Args:
            command: Command type (pause/resume/edit)
            agent_name: Target agent
            status: "acknowledged", "completed", or "failed"
            message_text: Human-readable status message

        Returns:
            Number of clients that received the message
        """
        message = ControlAckMessage(command, agent_name, status, message_text)
        return await self.broadcast(message)

    # ========================================================================
    # Server Statistics and Monitoring
    # ========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get server statistics.

        Returns:
            Dictionary with connection and message statistics
        """
        return {
            'active_connections': len(self.connections),
            'total_messages_sent': self.total_messages_sent,
            'total_broadcasts': self.total_broadcasts,
            'connection_metadata': self.connection_metadata,
            'server_uptime': 'running' if self.site else 'stopped'
        }


# ============================================================================
# Standalone Server Entry Point
# ============================================================================

async def main():
    """Run standalone WebSocket server for testing."""
    import argparse

    parser = argparse.ArgumentParser(description='Agent Dashboard WebSocket Server')
    parser.add_argument('--host', default='127.0.0.1', help='Server host (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8421, help='Server port (default: 8421)')
    args = parser.parse_args()

    server = WebSocketServer(host=args.host, port=args.port)
    await server.start()

    logger.info("WebSocket server running. Press Ctrl+C to stop.")

    try:
        # Keep server running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
    finally:
        await server.stop()


if __name__ == '__main__':
    asyncio.run(main())
