"""WebSocket Client - Example client for Agent Dashboard WebSocket server.

This module provides a simple Python WebSocket client that connects to the
dashboard WebSocket server and receives real-time updates.

Features:
    - Auto-reconnection with exponential backoff
    - Message type filtering/subscription
    - Graceful shutdown
    - Event callbacks for different message types

Usage:
    # Basic usage
    client = WebSocketClient('ws://127.0.0.1:8421/ws')
    await client.connect()

    # Listen for specific event types
    client.on_agent_status(lambda data: print(f"Agent status: {data}"))
    client.on_code_stream(lambda data: print(f"Code: {data['content']}"))

    # Start receiving messages
    await client.run()
"""

import asyncio
import json
import logging
from typing import Any, Callable, Optional

from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType

logger = logging.getLogger(__name__)


class WebSocketClient:
    """WebSocket client with auto-reconnection for Agent Dashboard.

    Connects to the dashboard WebSocket server and handles real-time updates
    with automatic reconnection and exponential backoff.
    """

    def __init__(
        self,
        url: str,
        auto_reconnect: bool = True,
        max_reconnect_delay: float = 30.0
    ):
        """Initialize WebSocket client.

        Args:
            url: WebSocket server URL (e.g., ws://127.0.0.1:8421/ws)
            auto_reconnect: Enable automatic reconnection
            max_reconnect_delay: Maximum delay between reconnection attempts (seconds)
        """
        self.url = url
        self.auto_reconnect = auto_reconnect
        self.max_reconnect_delay = max_reconnect_delay

        # Connection state
        self.session: Optional[ClientSession] = None
        self.ws: Optional[ClientWebSocketResponse] = None
        self.connected = False
        self.reconnect_delay = 1.0  # Start with 1 second delay

        # Event callbacks
        self.callbacks: dict[str, list[Callable]] = {}

        # Message statistics
        self.messages_received = 0
        self.reconnect_count = 0

        logger.info(f"WebSocket client initialized for {url}")

    async def connect(self) -> bool:
        """Connect to WebSocket server.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            if not self.session:
                self.session = ClientSession()

            logger.info(f"Connecting to {self.url}...")
            self.ws = await self.session.ws_connect(self.url)
            self.connected = True
            self.reconnect_delay = 1.0  # Reset reconnect delay on success

            logger.info("Connected to WebSocket server")

            # Wait for welcome message
            msg = await self.ws.receive()
            if msg.type == WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data.get('type') == 'connection':
                    logger.info(f"Connection acknowledged: {data.get('message')}")

            return True

        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self.connected = False
            return False

    async def disconnect(self):
        """Disconnect from WebSocket server."""
        self.connected = False

        if self.ws:
            await self.ws.close()
            self.ws = None

        if self.session:
            await self.session.close()
            self.session = None

        logger.info("Disconnected from WebSocket server")

    async def reconnect(self):
        """Attempt to reconnect with exponential backoff."""
        if not self.auto_reconnect:
            return

        self.reconnect_count += 1

        logger.info(
            f"Reconnecting (attempt {self.reconnect_count}) in {self.reconnect_delay}s..."
        )

        await asyncio.sleep(self.reconnect_delay)

        if await self.connect():
            logger.info("Reconnection successful")
        else:
            # Exponential backoff: 1s, 2s, 4s, 8s, 16s, max 30s
            self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
            await self.reconnect()

    async def run(self):
        """Run the client message loop.

        Continuously receives and processes messages from the server.
        Automatically reconnects on connection loss if auto_reconnect is enabled.
        """
        while True:
            if not self.connected:
                if not await self.connect():
                    if self.auto_reconnect:
                        await self.reconnect()
                    else:
                        break
                continue

            try:
                async for msg in self.ws:
                    if msg.type == WSMsgType.TEXT:
                        await self._handle_message(msg.data)

                    elif msg.type == WSMsgType.ERROR:
                        logger.error(f"WebSocket error: {self.ws.exception()}")
                        break

                    elif msg.type == WSMsgType.CLOSED:
                        logger.info("WebSocket connection closed by server")
                        break

                # Connection closed
                self.connected = False

                if self.auto_reconnect:
                    await self.reconnect()
                else:
                    break

            except asyncio.CancelledError:
                logger.info("Client run loop cancelled")
                break

            except Exception as e:
                logger.error(f"Error in message loop: {e}")
                self.connected = False

                if self.auto_reconnect:
                    await self.reconnect()
                else:
                    break

    async def _handle_message(self, message_data: str):
        """Handle incoming message from server.

        Args:
            message_data: Raw message data (JSON string)
        """
        try:
            data = json.loads(message_data)
            message_type = data.get('type')

            self.messages_received += 1

            # Call registered callbacks for this message type
            if message_type in self.callbacks:
                for callback in self.callbacks[message_type]:
                    try:
                        callback(data)
                    except Exception as e:
                        logger.error(f"Error in callback for {message_type}: {e}")

            # Call wildcard callbacks (all message types)
            if '*' in self.callbacks:
                for callback in self.callbacks['*']:
                    try:
                        callback(data)
                    except Exception as e:
                        logger.error(f"Error in wildcard callback: {e}")

        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON received: {message_data}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    # ========================================================================
    # Event Registration Methods
    # ========================================================================

    def on(self, message_type: str, callback: Callable[[dict], Any]):
        """Register callback for a specific message type.

        Args:
            message_type: Message type to listen for (e.g., "agent_status")
                         Use "*" to receive all message types
            callback: Function to call when message is received
        """
        if message_type not in self.callbacks:
            self.callbacks[message_type] = []

        self.callbacks[message_type].append(callback)
        logger.debug(f"Registered callback for {message_type}")

    def on_agent_status(self, callback: Callable[[dict], Any]):
        """Register callback for agent_status messages."""
        self.on('agent_status', callback)

    def on_agent_event(self, callback: Callable[[dict], Any]):
        """Register callback for agent_event messages."""
        self.on('agent_event', callback)

    def on_reasoning(self, callback: Callable[[dict], Any]):
        """Register callback for reasoning messages."""
        self.on('reasoning', callback)

    def on_code_stream(self, callback: Callable[[dict], Any]):
        """Register callback for code_stream messages."""
        self.on('code_stream', callback)

    def on_chat_message(self, callback: Callable[[dict], Any]):
        """Register callback for chat_message messages."""
        self.on('chat_message', callback)

    def on_metrics_update(self, callback: Callable[[dict], Any]):
        """Register callback for metrics_update messages."""
        self.on('metrics_update', callback)

    def on_control_ack(self, callback: Callable[[dict], Any]):
        """Register callback for control_ack messages."""
        self.on('control_ack', callback)

    # ========================================================================
    # Utility Methods
    # ========================================================================

    async def ping(self) -> bool:
        """Send ping to server and wait for pong.

        Returns:
            True if pong received, False otherwise
        """
        if not self.connected or not self.ws:
            return False

        try:
            await self.ws.send_str('ping')

            # Wait for pong with timeout
            msg = await asyncio.wait_for(self.ws.receive(), timeout=5.0)

            if msg.type == WSMsgType.TEXT and msg.data == 'pong':
                return True

            return False

        except asyncio.TimeoutError:
            logger.warning("Ping timeout")
            return False
        except Exception as e:
            logger.error(f"Ping error: {e}")
            return False

    def get_stats(self) -> dict[str, Any]:
        """Get client statistics.

        Returns:
            Dictionary with connection and message statistics
        """
        return {
            'connected': self.connected,
            'messages_received': self.messages_received,
            'reconnect_count': self.reconnect_count,
            'current_reconnect_delay': self.reconnect_delay,
            'registered_callbacks': {
                msg_type: len(callbacks)
                for msg_type, callbacks in self.callbacks.items()
            }
        }


# ============================================================================
# Example Usage
# ============================================================================

async def example_usage():
    """Example usage of WebSocketClient."""
    # Create client
    client = WebSocketClient('ws://127.0.0.1:8421/ws')

    # Register callbacks for different message types
    client.on_agent_status(
        lambda data: print(f"[AGENT STATUS] {data['agent_name']}: {data['status']}")
    )

    client.on_reasoning(
        lambda data: print(f"[REASONING] {data['source']}: {data['content']}")
    )

    client.on_code_stream(
        lambda data: print(f"[CODE] {data['file_path']}:{data['line_number']} {data['content']}")
    )

    client.on_chat_message(
        lambda data: print(f"[CHAT] {data['provider']}: {data['content']}", end='')
    )

    client.on_metrics_update(
        lambda data: print(f"[METRICS] Updated: {data['update_type']}")
    )

    # Register wildcard callback (receives all messages)
    client.on('*', lambda data: logger.debug(f"Received {data['type']} message"))

    # Connect and run
    try:
        await client.run()
    except KeyboardInterrupt:
        print("\nShutting down...")
        await client.disconnect()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    asyncio.run(example_usage())
