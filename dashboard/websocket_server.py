"""
WebSocket server for real-time dashboard updates with broadcast support.
"""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class BroadcastMessage:
    """A message to be broadcast to WebSocket clients."""
    type: str
    data: Dict[str, Any]
    timestamp: str
    source: str = "system"
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(asdict(self))


class WebSocketBroadcaster:
    """Manages WebSocket connections and broadcasts messages."""
    
    def __init__(self):
        self.connections: Set[Any] = set()
        self.message_queue: asyncio.Queue = None
        self.broadcast_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def initialize(self) -> None:
        """Initialize the broadcaster."""
        self.message_queue = asyncio.Queue()
        self._running = True
        self.broadcast_task = asyncio.create_task(self._broadcast_worker())
        logger.info("WebSocketBroadcaster initialized")
    
    async def shutdown(self) -> None:
        """Shutdown the broadcaster."""
        logger.info("Shutting down WebSocketBroadcaster")
        self._running = False
        
        if self.broadcast_task:
            self.broadcast_task.cancel()
            try:
                await self.broadcast_task
            except asyncio.CancelledError:
                pass
        
        logger.info("WebSocketBroadcaster shutdown complete")
    
    async def connect(self, connection: Any) -> None:
        """Register a new WebSocket connection."""
        self.connections.add(connection)
        logger.debug(f"Client connected. Total connections: {len(self.connections)}")
    
    async def disconnect(self, connection: Any) -> None:
        """Unregister a WebSocket connection."""
        self.connections.discard(connection)
        logger.debug(f"Client disconnected. Total connections: {len(self.connections)}")
    
    async def broadcast(
        self,
        message_type: str,
        data: Dict[str, Any],
        source: str = "system"
    ) -> None:
        """
        Broadcast a message to all connected clients.
        
        Args:
            message_type: Type of message
            data: Message payload
            source: Source of the message
        """
        if not self._running:
            logger.warning("Broadcaster is not running, ignoring broadcast")
            return
        
        message = BroadcastMessage(
            type=message_type,
            data=data,
            timestamp=datetime.utcnow().isoformat() + 'Z',
            source=source
        )
        
        try:
            await self.message_queue.put(message)
            logger.debug(f"Broadcast message queued: {message_type}")
        except Exception as e:
            logger.error(f"Failed to queue broadcast message: {e}")
    
    async def _broadcast_worker(self) -> None:
        """Worker task for broadcasting messages to all clients."""
        logger.info("Broadcast worker started")
        
        try:
            while self._running:
                try:
                    # Get message with timeout
                    message = await asyncio.wait_for(
                        self.message_queue.get(),
                        timeout=1.0
                    )
                    
                    # Send to all connected clients
                    await self._send_to_all(message)
                    
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Broadcast worker error: {e}", exc_info=True)
        finally:
            logger.info("Broadcast worker stopped")
    
    async def _send_to_all(self, message: BroadcastMessage) -> None:
        """Send a message to all connected clients."""
        if not self.connections:
            logger.debug(f"No connections to broadcast to (message type: {message.type})")
            return
        
        disconnected = set()
        message_json = message.to_json()
        
        for connection in self.connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.warning(f"Failed to send message to client: {e}")
                disconnected.add(connection)
        
        # Clean up disconnected clients
        for connection in disconnected:
            await self.disconnect(connection)
        
        if disconnected:
            logger.debug(f"Removed {len(disconnected)} disconnected clients")
    
    def get_connection_count(self) -> int:
        """Get current number of connected clients."""
        return len(self.connections)
    
    async def broadcast_status_update(self, status_data: Dict[str, Any]) -> None:
        """Broadcast a status update."""
        await self.broadcast("status_update", status_data, source="orchestrator")
    
    async def broadcast_acceleration_event(self, event_data: Dict[str, Any]) -> None:
        """Broadcast an acceleration-related event."""
        await self.broadcast("acceleration_event", event_data, source="accelerator")
    
    async def broadcast_task_update(self, task_id: str, task_status: Dict[str, Any]) -> None:
        """Broadcast a task status update."""
        await self.broadcast("task_update", {
            "task_id": task_id,
            **task_status
        }, source="orchestrator")
    
    async def broadcast_metrics(self, metrics: Dict[str, Any]) -> None:
        """Broadcast metrics update."""
        await self.broadcast("metrics", metrics, source="metrics_collector")


# Global broadcaster instance
_broadcaster: Optional[WebSocketBroadcaster] = None


async def get_broadcaster() -> WebSocketBroadcaster:
    """Get or create the global broadcaster."""
    global _broadcaster
    
    if _broadcaster is None:
        _broadcaster = WebSocketBroadcaster()
        await _broadcaster.initialize()
    
    return _broadcaster


async def shutdown_broadcaster() -> None:
    """Shutdown the global broadcaster."""
    global _broadcaster
    
    if _broadcaster:
        await _broadcaster.shutdown()
        _broadcaster = None


# Example usage functions
async def broadcast_acceleration_enabled(factor: float) -> None:
    """Broadcast that acceleration has been enabled."""
    broadcaster = await get_broadcaster()
    await broadcaster.broadcast_acceleration_event({
        "action": "enabled",
        "acceleration_factor": factor
    })


async def broadcast_acceleration_disabled() -> None:
    """Broadcast that acceleration has been disabled."""
    broadcaster = await get_broadcaster()
    await broadcaster.broadcast_acceleration_event({
        "action": "disabled"
    })


async def broadcast_task_completed(task_id: str, duration_ms: float) -> None:
    """Broadcast that a task has been completed."""
    broadcaster = await get_broadcaster()
    await broadcaster.broadcast_task_update(task_id, {
        "status": "completed",
        "duration_ms": duration_ms
    })
