"""
Comprehensive unit and integration tests for dashboard/websocket_server.py

Tests all 7 message types, connection management, broadcasting, error handling,
and performance requirements (sub-100ms latency, rapid message handling).

Test coverage:
- Connection/disconnection lifecycle
- All 7 message types (agent_status, agent_event, reasoning, code_stream, chat_message, metrics_update, control_ack)
- Broadcasting to multiple clients
- Rapid message handling and ordering
- Error handling and connection cleanup
- Message serialization/deserialization
- Client ping/pong keepalive
"""

import asyncio
import json
import time
from typing import Any, List

import pytest
from aiohttp import ClientSession, WSMsgType, web
from aiohttp.test_utils import AioHTTPTestCase

from dashboard.websocket_server import (
    AgentEventMessage,
    AgentStatus,
    AgentStatusMessage,
    BaseMessage,
    ChatMessageChunk,
    CodeStreamMessage,
    ControlAckMessage,
    ControlCommand,
    MessageType,
    MetricsUpdateMessage,
    ReasoningMessage,
    WebSocketServer,
)


# ============================================================================
# Test Fixtures and Helpers
# ============================================================================

@pytest.fixture
def sample_event_data() -> dict[str, Any]:
    """Sample agent event data for testing."""
    return {
        'event_id': 'evt-123',
        'agent_name': 'coding',
        'session_id': 'sess-456',
        'ticket_key': 'AI-104',
        'status': 'success',
        'duration_seconds': 45.2,
        'total_tokens': 5000,
        'estimated_cost_usd': 0.15,
        'artifacts': ['file:src/main.py', 'commit:abc123']
    }


@pytest.fixture
def sample_metrics_data() -> dict[str, Any]:
    """Sample metrics data for testing."""
    return {
        'total_sessions': 10,
        'total_tokens': 50000,
        'total_cost_usd': 1.50,
        'agents': {
            'coding': {
                'agent_name': 'coding',
                'total_invocations': 20,
                'success_rate': 0.95
            }
        }
    }


# ============================================================================
# Unit Tests - Message Type Definitions
# ============================================================================

class TestMessageTypes:
    """Test all message type classes and their serialization."""

    def test_base_message_structure(self):
        """Test BaseMessage contains required fields."""
        msg = BaseMessage(type="test", timestamp="2024-01-01T00:00:00Z")
        assert msg.type == "test"
        assert msg.timestamp == "2024-01-01T00:00:00Z"

        msg_dict = msg.to_dict()
        assert isinstance(msg_dict, dict)
        assert msg_dict['type'] == "test"
        assert msg_dict['timestamp'] == "2024-01-01T00:00:00Z"

    def test_agent_status_message(self):
        """Test AgentStatusMessage creation and serialization."""
        msg = AgentStatusMessage(
            agent_name="coding",
            status=AgentStatus.RUNNING.value,
            metadata={'ticket_key': 'AI-104'}
        )

        assert msg.type == MessageType.AGENT_STATUS.value
        assert msg.agent_name == "coding"
        assert msg.status == "running"
        assert msg.metadata['ticket_key'] == 'AI-104'
        assert 'timestamp' in msg.to_dict()

    def test_agent_status_message_without_metadata(self):
        """Test AgentStatusMessage with no metadata."""
        msg = AgentStatusMessage(agent_name="github", status=AgentStatus.IDLE.value)
        assert msg.metadata == {}

    def test_agent_event_message(self, sample_event_data):
        """Test AgentEventMessage creation from event data."""
        msg = AgentEventMessage(sample_event_data)

        assert msg.type == MessageType.AGENT_EVENT.value
        assert msg.event_id == 'evt-123'
        assert msg.agent_name == 'coding'
        assert msg.ticket_key == 'AI-104'
        assert msg.duration_seconds == 45.2
        assert msg.tokens == 5000
        assert msg.cost_usd == 0.15
        assert 'file:src/main.py' in msg.artifacts

    def test_reasoning_message(self):
        """Test ReasoningMessage creation and serialization."""
        msg = ReasoningMessage(
            content="Delegating to coding agent based on complexity analysis",
            source="orchestrator",
            context={'ticket': 'AI-104', 'complexity': 'COMPLEX'}
        )

        assert msg.type == MessageType.REASONING.value
        assert "Delegating" in msg.content
        assert msg.source == "orchestrator"
        assert msg.context['complexity'] == 'COMPLEX'

    def test_code_stream_message(self):
        """Test CodeStreamMessage creation and serialization."""
        msg = CodeStreamMessage(
            content="def hello_world():",
            file_path="src/main.py",
            line_number=42,
            operation="add",
            language="python"
        )

        assert msg.type == MessageType.CODE_STREAM.value
        assert msg.content == "def hello_world():"
        assert msg.file_path == "src/main.py"
        assert msg.line_number == 42
        assert msg.operation == "add"
        assert msg.language == "python"

    def test_code_stream_message_defaults(self):
        """Test CodeStreamMessage with default parameters."""
        msg = CodeStreamMessage(content="console.log('test');", file_path="src/app.js")
        assert msg.line_number == 0
        assert msg.operation == "add"
        assert msg.language == "python"  # Default language

    def test_chat_message_chunk(self):
        """Test ChatMessageChunk creation and serialization."""
        msg = ChatMessageChunk(
            content="This is a test response.",
            message_id="msg-789",
            provider="claude",
            is_final=False
        )

        assert msg.type == MessageType.CHAT_MESSAGE.value
        assert msg.content == "This is a test response."
        assert msg.message_id == "msg-789"
        assert msg.provider == "claude"
        assert msg.is_final is False

    def test_chat_message_final_chunk(self):
        """Test ChatMessageChunk with is_final=True."""
        msg = ChatMessageChunk(
            content="Final chunk.",
            message_id="msg-789",
            provider="chatgpt",
            is_final=True
        )
        assert msg.is_final is True

    def test_metrics_update_message(self, sample_metrics_data):
        """Test MetricsUpdateMessage creation and serialization."""
        msg = MetricsUpdateMessage(metrics=sample_metrics_data, update_type="full")

        assert msg.type == MessageType.METRICS_UPDATE.value
        assert msg.metrics == sample_metrics_data
        assert msg.update_type == "full"

    def test_control_ack_message(self):
        """Test ControlAckMessage creation and serialization."""
        msg = ControlAckMessage(
            command=ControlCommand.PAUSE.value,
            agent_name="coding",
            status="acknowledged",
            message="Agent coding paused successfully"
        )

        assert msg.type == MessageType.CONTROL_ACK.value
        assert msg.command == "pause"
        assert msg.agent_name == "coding"
        assert msg.status == "acknowledged"
        assert "successfully" in msg.message


# ============================================================================
# Integration Tests - WebSocket Server
# ============================================================================

class TestWebSocketServer(AioHTTPTestCase):
    """Integration tests for WebSocketServer with real connections."""

    async def get_application(self):
        """Create test application with WebSocket server."""
        self.ws_server = WebSocketServer(host='127.0.0.1', port=0)  # Random port
        self.ws_server.app = web.Application()
        self.ws_server.app.router.add_get('/ws', self.ws_server.websocket_handler)
        self.ws_server.app.router.add_get('/health', self.ws_server.health_handler)
        return self.ws_server.app

    async def tearDown(self):
        """Cleanup after tests."""
        await self.ws_server._close_all_connections()
        await super().tearDown()

    # ========================================================================
    # Connection Management Tests
    # ========================================================================

    async def test_health_endpoint(self):
        """Test health check endpoint returns correct data."""
        resp = await self.client.request("GET", "/health")
        assert resp.status == 200

        data = await resp.json()
        assert data['status'] == 'ok'
        assert 'connections' in data
        assert 'total_messages_sent' in data
        assert 'timestamp' in data

    async def test_websocket_connection(self):
        """Test basic WebSocket connection and disconnection."""
        async with self.client.ws_connect('/ws') as ws:
            # Should receive welcome message
            msg = await ws.receive()
            assert msg.type == WSMsgType.TEXT

            data = json.loads(msg.data)
            assert data['type'] == 'connection'
            assert data['status'] == 'connected'
            assert 'connection_id' in data

        # Check connection was removed
        assert len(self.ws_server.connections) == 0

    async def test_multiple_concurrent_connections(self):
        """Test server handles multiple concurrent connections."""
        connections = []

        # Connect 5 clients
        for i in range(5):
            ws = await self.client.ws_connect('/ws')
            connections.append(ws)

            # Read welcome message
            msg = await ws.receive()
            assert msg.type == WSMsgType.TEXT

        # Verify all connections tracked
        assert len(self.ws_server.connections) == 5

        # Close all connections
        for ws in connections:
            await ws.close()

        # Wait for cleanup
        await asyncio.sleep(0.1)

        # Verify all connections removed
        assert len(self.ws_server.connections) == 0

    async def test_ping_pong(self):
        """Test WebSocket ping/pong keepalive."""
        async with self.client.ws_connect('/ws') as ws:
            # Read welcome message
            await ws.receive()

            # Send ping
            await ws.send_str('ping')

            # Should receive pong
            msg = await ws.receive()
            assert msg.type == WSMsgType.TEXT
            assert msg.data == 'pong'

    # ========================================================================
    # Broadcasting Tests - All 7 Message Types
    # ========================================================================

    async def test_broadcast_agent_status(self):
        """Test broadcasting agent status change."""
        async with self.client.ws_connect('/ws') as ws:
            # Read welcome message
            await ws.receive()

            # Broadcast status change
            await self.ws_server.broadcast_agent_status(
                agent_name="coding",
                status=AgentStatus.RUNNING.value,
                metadata={'ticket_key': 'AI-104'}
            )

            # Receive broadcast
            msg = await ws.receive()
            assert msg.type == WSMsgType.TEXT

            data = json.loads(msg.data)
            assert data['type'] == MessageType.AGENT_STATUS.value
            assert data['agent_name'] == 'coding'
            assert data['status'] == 'running'
            assert data['metadata']['ticket_key'] == 'AI-104'

    async def test_broadcast_agent_event(self):
        """Test broadcasting agent event."""
        sample_event_data = {
            'event_id': 'evt-123',
            'agent_name': 'coding',
            'session_id': 'sess-456',
            'ticket_key': 'AI-104',
            'status': 'success',
            'duration_seconds': 45.2,
            'total_tokens': 5000,
            'estimated_cost_usd': 0.15,
            'artifacts': ['file:src/main.py', 'commit:abc123']
        }

        async with self.client.ws_connect('/ws') as ws:
            await ws.receive()  # Welcome message

            # Broadcast event
            await self.ws_server.broadcast_agent_event(sample_event_data)

            # Receive broadcast
            msg = await ws.receive()
            data = json.loads(msg.data)

            assert data['type'] == MessageType.AGENT_EVENT.value
            assert data['event_id'] == 'evt-123'
            assert data['agent_name'] == 'coding'
            assert data['tokens'] == 5000

    async def test_broadcast_reasoning(self):
        """Test broadcasting reasoning message."""
        async with self.client.ws_connect('/ws') as ws:
            await ws.receive()  # Welcome message

            # Broadcast reasoning
            await self.ws_server.broadcast_reasoning(
                content="Analyzing ticket complexity...",
                source="orchestrator",
                context={'ticket': 'AI-104'}
            )

            # Receive broadcast
            msg = await ws.receive()
            data = json.loads(msg.data)

            assert data['type'] == MessageType.REASONING.value
            assert "Analyzing" in data['content']
            assert data['source'] == 'orchestrator'

    async def test_broadcast_code_stream(self):
        """Test broadcasting code stream chunk."""
        async with self.client.ws_connect('/ws') as ws:
            await ws.receive()  # Welcome message

            # Broadcast code chunk
            await self.ws_server.broadcast_code_stream(
                content="def test_function():",
                file_path="src/test.py",
                line_number=10,
                operation="add",
                language="python"
            )

            # Receive broadcast
            msg = await ws.receive()
            data = json.loads(msg.data)

            assert data['type'] == MessageType.CODE_STREAM.value
            assert data['content'] == "def test_function():"
            assert data['file_path'] == "src/test.py"
            assert data['line_number'] == 10

    async def test_broadcast_chat_message(self):
        """Test broadcasting chat message chunk."""
        async with self.client.ws_connect('/ws') as ws:
            await ws.receive()  # Welcome message

            # Broadcast chat chunk
            await self.ws_server.broadcast_chat_message(
                content="This is a test response.",
                message_id="msg-123",
                provider="claude",
                is_final=False
            )

            # Receive broadcast
            msg = await ws.receive()
            data = json.loads(msg.data)

            assert data['type'] == MessageType.CHAT_MESSAGE.value
            assert data['content'] == "This is a test response."
            assert data['message_id'] == "msg-123"
            assert data['is_final'] is False

    async def test_broadcast_metrics_update(self):
        """Test broadcasting metrics update."""
        sample_metrics_data = {
            'total_sessions': 10,
            'total_tokens': 50000,
            'total_cost_usd': 1.50,
            'agents': {
                'coding': {
                    'agent_name': 'coding',
                    'total_invocations': 20,
                    'success_rate': 0.95
                }
            }
        }

        async with self.client.ws_connect('/ws') as ws:
            await ws.receive()  # Welcome message

            # Broadcast metrics
            await self.ws_server.broadcast_metrics_update(
                metrics=sample_metrics_data,
                update_type="full"
            )

            # Receive broadcast
            msg = await ws.receive()
            data = json.loads(msg.data)

            assert data['type'] == MessageType.METRICS_UPDATE.value
            assert data['metrics']['total_sessions'] == 10
            assert data['update_type'] == 'full'

    async def test_broadcast_control_ack(self):
        """Test broadcasting control acknowledgment."""
        async with self.client.ws_connect('/ws') as ws:
            await ws.receive()  # Welcome message

            # Broadcast control ack
            await self.ws_server.broadcast_control_ack(
                command=ControlCommand.PAUSE.value,
                agent_name="coding",
                status="completed",
                message_text="Agent paused successfully"
            )

            # Receive broadcast
            msg = await ws.receive()
            data = json.loads(msg.data)

            assert data['type'] == MessageType.CONTROL_ACK.value
            assert data['command'] == 'pause'
            assert data['agent_name'] == 'coding'
            assert data['status'] == 'completed'

    # ========================================================================
    # Multi-Client Broadcasting Tests
    # ========================================================================

    async def test_broadcast_to_multiple_clients(self):
        """Test broadcasting reaches all connected clients."""
        connections = []

        # Connect 3 clients
        for i in range(3):
            ws = await self.client.ws_connect('/ws')
            connections.append(ws)
            await ws.receive()  # Read welcome message

        # Broadcast to all
        clients_reached = await self.ws_server.broadcast_agent_status(
            agent_name="github",
            status=AgentStatus.IDLE.value
        )

        assert clients_reached == 3

        # All clients should receive the message
        for ws in connections:
            msg = await ws.receive()
            assert msg.type == WSMsgType.TEXT

            data = json.loads(msg.data)
            assert data['type'] == MessageType.AGENT_STATUS.value
            assert data['agent_name'] == 'github'

        # Cleanup
        for ws in connections:
            await ws.close()

    # ========================================================================
    # Performance Tests
    # ========================================================================

    async def test_rapid_message_handling(self):
        """Test rapid sequential message handling and ordering."""
        async with self.client.ws_connect('/ws') as ws:
            await ws.receive()  # Welcome message

            # Send 50 rapid messages
            message_count = 50
            for i in range(message_count):
                await self.ws_server.broadcast_agent_status(
                    agent_name="coding",
                    status=AgentStatus.RUNNING.value,
                    metadata={'iteration': i}
                )

            # Receive all messages and verify order
            received = []
            for i in range(message_count):
                msg = await asyncio.wait_for(ws.receive(), timeout=5.0)
                data = json.loads(msg.data)
                received.append(data['metadata']['iteration'])

            # Verify all messages received in order
            assert len(received) == message_count
            assert received == list(range(message_count))

    async def test_sub_100ms_latency(self):
        """Test event latency is under 100ms (REQ-PERF-001)."""
        async with self.client.ws_connect('/ws') as ws:
            await ws.receive()  # Welcome message

            # Measure latency for 10 broadcasts
            latencies = []
            for i in range(10):
                start_time = time.time()

                # Broadcast message
                await self.ws_server.broadcast_agent_status(
                    agent_name="coding",
                    status=AgentStatus.RUNNING.value
                )

                # Receive message
                await ws.receive()

                latency_ms = (time.time() - start_time) * 1000
                latencies.append(latency_ms)

            # Check average latency is under 100ms
            avg_latency = sum(latencies) / len(latencies)
            assert avg_latency < 100, f"Average latency {avg_latency}ms exceeds 100ms requirement"

    # ========================================================================
    # Error Handling Tests
    # ========================================================================

    async def test_invalid_json_from_client(self):
        """Test server handles invalid JSON gracefully."""
        async with self.client.ws_connect('/ws') as ws:
            await ws.receive()  # Welcome message

            # Send invalid JSON
            await ws.send_str("this is not json")

            # Server should not crash, connection should remain open
            await asyncio.sleep(0.1)

            # Send valid ping to verify connection still works
            await ws.send_str('ping')
            msg = await ws.receive()
            assert msg.data == 'pong'

    async def test_connection_cleanup_on_error(self):
        """Test connections are cleaned up after errors."""
        # Connect client
        ws = await self.client.ws_connect('/ws')
        await ws.receive()  # Welcome message

        assert len(self.ws_server.connections) == 1

        # Force close connection
        await ws.close()

        # Wait for cleanup
        await asyncio.sleep(0.2)

        # Verify connection was cleaned up
        assert len(self.ws_server.connections) == 0

    async def test_broadcast_with_no_connections(self):
        """Test broadcasting with no connected clients doesn't error."""
        # No connections
        assert len(self.ws_server.connections) == 0

        # Should not raise an error
        clients_reached = await self.ws_server.broadcast_agent_status(
            agent_name="coding",
            status=AgentStatus.IDLE.value
        )

        assert clients_reached == 0

    # ========================================================================
    # Statistics Tests
    # ========================================================================

    async def test_server_statistics(self):
        """Test server statistics tracking."""
        async with self.client.ws_connect('/ws') as ws:
            await ws.receive()  # Welcome message

            # Broadcast some messages
            await self.ws_server.broadcast_agent_status("coding", AgentStatus.RUNNING.value)
            await self.ws_server.broadcast_reasoning("Test reasoning", "orchestrator")

            # Get statistics
            stats = self.ws_server.get_stats()

            assert stats['active_connections'] == 1
            assert stats['total_broadcasts'] >= 2
            assert stats['total_messages_sent'] >= 3  # Welcome + 2 broadcasts


# Run tests with: python -m pytest tests/dashboard/test_websocket_server.py -v
