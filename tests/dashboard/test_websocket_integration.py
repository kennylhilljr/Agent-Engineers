"""
Integration test demonstrating WebSocket protocol with all 7 message types.

This test starts a WebSocket server, connects a client, and demonstrates
all message types being broadcast and received correctly.

Run with: python -m pytest tests/dashboard/test_websocket_integration.py -v -s
"""

import asyncio
import json

import pytest
from aiohttp import ClientSession

from dashboard.websocket_server import AgentStatus, WebSocketServer


@pytest.mark.asyncio
async def test_full_websocket_protocol():
    """Test complete WebSocket protocol with all 7 message types."""
    # Start server
    server = WebSocketServer(host='127.0.0.1', port=8422)
    await server.start()

    print(f"\n✓ WebSocket server started on ws://127.0.0.1:8422/ws")

    try:
        # Connect client
        async with ClientSession() as session:
            async with session.ws_connect('ws://127.0.0.1:8422/ws') as ws:
                print("✓ Client connected")

                # Read welcome message
                msg = await ws.receive()
                data = json.loads(msg.data)
                assert data['type'] == 'connection'
                print(f"✓ Received welcome: {data['message']}")

                # Test 1: agent_status
                print("\n1. Testing agent_status message type...")
                await server.broadcast_agent_status(
                    agent_name="coding",
                    status=AgentStatus.RUNNING.value,
                    metadata={'ticket_key': 'AI-104', 'model': 'claude-sonnet-4-5'}
                )

                msg = await ws.receive()
                data = json.loads(msg.data)
                assert data['type'] == 'agent_status'
                assert data['agent_name'] == 'coding'
                assert data['status'] == 'running'
                assert data['metadata']['ticket_key'] == 'AI-104'
                print(f"   ✓ Received agent_status: {data['agent_name']} -> {data['status']}")

                # Test 2: agent_event
                print("\n2. Testing agent_event message type...")
                await server.broadcast_agent_event({
                    'event_id': 'evt-ai104-001',
                    'agent_name': 'coding',
                    'session_id': 'sess-20240216-001',
                    'ticket_key': 'AI-104',
                    'status': 'success',
                    'duration_seconds': 45.2,
                    'total_tokens': 5000,
                    'estimated_cost_usd': 0.15,
                    'artifacts': ['file:dashboard/websocket_server.py:created', 'commit:abc123']
                })

                msg = await ws.receive()
                data = json.loads(msg.data)
                assert data['type'] == 'agent_event'
                assert data['event_id'] == 'evt-ai104-001'
                assert data['agent_name'] == 'coding'
                assert data['tokens'] == 5000
                print(f"   ✓ Received agent_event: {data['event_id']} - {data['status']} ({data['tokens']} tokens)")

                # Test 3: reasoning
                print("\n3. Testing reasoning message type...")
                await server.broadcast_reasoning(
                    content="Analyzing ticket AI-104: WebSocket Protocol implementation. "
                           "Complexity: COMPLEX (real-time networking, async patterns). "
                           "Decision: Delegate to coding agent with Sonnet 4.5 for robust implementation.",
                    source="orchestrator",
                    context={
                        'ticket': 'AI-104',
                        'complexity': 'COMPLEX',
                        'selected_agent': 'coding',
                        'selected_model': 'claude-sonnet-4-5',
                        'reasoning_tokens': 250
                    }
                )

                msg = await ws.receive()
                data = json.loads(msg.data)
                assert data['type'] == 'reasoning'
                assert data['source'] == 'orchestrator'
                assert 'WebSocket Protocol' in data['content']
                assert data['context']['complexity'] == 'COMPLEX'
                print(f"   ✓ Received reasoning from {data['source']}")
                print(f"      Content: {data['content'][:80]}...")

                # Test 4: code_stream
                print("\n4. Testing code_stream message type...")
                code_chunks = [
                    ("class WebSocketServer:", 1),
                    ("    def __init__(self, host, port):", 2),
                    ("        self.host = host", 3),
                    ("        self.port = port", 4),
                ]

                for content, line_num in code_chunks:
                    await server.broadcast_code_stream(
                        content=content,
                        file_path="dashboard/websocket_server.py",
                        line_number=line_num,
                        operation="add",
                        language="python"
                    )

                    msg = await ws.receive()
                    data = json.loads(msg.data)
                    assert data['type'] == 'code_stream'
                    assert data['file_path'] == 'dashboard/websocket_server.py'
                    assert data['line_number'] == line_num
                    print(f"   ✓ Line {line_num}: {data['content']}")

                # Test 5: chat_message (streaming)
                print("\n5. Testing chat_message message type (streaming)...")
                message_chunks = [
                    "I've implemented ",
                    "the WebSocket protocol ",
                    "with all 7 message types. ",
                    "Tests are passing!"
                ]

                message_id = "msg-ai104-response"
                for i, chunk in enumerate(message_chunks):
                    is_final = (i == len(message_chunks) - 1)
                    await server.broadcast_chat_message(
                        content=chunk,
                        message_id=message_id,
                        provider="claude",
                        is_final=is_final
                    )

                    msg = await ws.receive()
                    data = json.loads(msg.data)
                    assert data['type'] == 'chat_message'
                    assert data['message_id'] == message_id
                    assert data['provider'] == 'claude'
                    print(f"   ✓ Chunk {i+1}: '{data['content']}' (final: {data['is_final']})")

                # Test 6: metrics_update
                print("\n6. Testing metrics_update message type...")
                await server.broadcast_metrics_update(
                    metrics={
                        'total_sessions': 15,
                        'total_tokens': 125000,
                        'total_cost_usd': 3.75,
                        'agents': {
                            'coding': {
                                'agent_name': 'coding',
                                'total_invocations': 45,
                                'successful_invocations': 43,
                                'success_rate': 0.956,
                                'total_tokens': 80000,
                                'xp': 1250,
                                'level': 8
                            }
                        }
                    },
                    update_type="full"
                )

                msg = await ws.receive()
                data = json.loads(msg.data)
                assert data['type'] == 'metrics_update'
                assert data['update_type'] == 'full'
                assert data['metrics']['total_sessions'] == 15
                print(f"   ✓ Received metrics_update: {data['update_type']}")
                print(f"      Total sessions: {data['metrics']['total_sessions']}")
                print(f"      Total tokens: {data['metrics']['total_tokens']}")
                print(f"      Total cost: ${data['metrics']['total_cost_usd']}")

                # Test 7: control_ack
                print("\n7. Testing control_ack message type...")
                await server.broadcast_control_ack(
                    command="pause",
                    agent_name="coding",
                    status="acknowledged",
                    message_text="Agent 'coding' paused successfully. Current task will complete before pausing."
                )

                msg = await ws.receive()
                data = json.loads(msg.data)
                assert data['type'] == 'control_ack'
                assert data['command'] == 'pause'
                assert data['agent_name'] == 'coding'
                assert data['status'] == 'acknowledged'
                print(f"   ✓ Received control_ack: {data['command']} on {data['agent_name']}")
                print(f"      Status: {data['status']}")
                print(f"      Message: {data['message']}")

                # Verify server statistics
                print("\n8. Checking server statistics...")
                stats = server.get_stats()
                print(f"   ✓ Active connections: {stats['active_connections']}")
                print(f"   ✓ Total messages sent: {stats['total_messages_sent']}")
                print(f"   ✓ Total broadcasts: {stats['total_broadcasts']}")

                assert stats['active_connections'] == 1
                assert stats['total_broadcasts'] >= 7  # At least one broadcast per message type

                print("\n✓ All 7 message types tested successfully!")

    finally:
        # Stop server
        await server.stop()
        print("✓ WebSocket server stopped")


@pytest.mark.asyncio
async def test_rapid_message_ordering():
    """Test rapid message handling maintains correct ordering."""
    server = WebSocketServer(host='127.0.0.1', port=8423)
    await server.start()

    print(f"\n✓ Server started for rapid message test")

    try:
        async with ClientSession() as session:
            async with session.ws_connect('ws://127.0.0.1:8423/ws') as ws:
                await ws.receive()  # Welcome message

                # Send 100 rapid sequential messages
                print("   Sending 100 rapid messages...")
                message_count = 100
                for i in range(message_count):
                    await server.broadcast_agent_status(
                        agent_name="coding",
                        status=AgentStatus.RUNNING.value,
                        metadata={'sequence': i}
                    )

                # Receive and verify ordering
                print("   Receiving and verifying order...")
                received_sequences = []
                for i in range(message_count):
                    msg = await asyncio.wait_for(ws.receive(), timeout=5.0)
                    data = json.loads(msg.data)
                    received_sequences.append(data['metadata']['sequence'])

                # Verify perfect ordering
                assert received_sequences == list(range(message_count))
                print(f"   ✓ All {message_count} messages received in correct order")

    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_sub_100ms_latency_requirement():
    """Test that events reach clients within 100ms (REQ-PERF-001)."""
    import time

    server = WebSocketServer(host='127.0.0.1', port=8424)
    await server.start()

    print(f"\n✓ Server started for latency test")

    try:
        async with ClientSession() as session:
            async with session.ws_connect('ws://127.0.0.1:8424/ws') as ws:
                await ws.receive()  # Welcome message

                # Measure latency over 20 broadcasts
                latencies = []
                print("   Measuring latency for 20 broadcasts...")

                for i in range(20):
                    start_time = time.time()

                    # Broadcast message
                    await server.broadcast_agent_status(
                        agent_name="coding",
                        status=AgentStatus.RUNNING.value
                    )

                    # Receive message
                    await ws.receive()

                    latency_ms = (time.time() - start_time) * 1000
                    latencies.append(latency_ms)

                # Calculate statistics
                avg_latency = sum(latencies) / len(latencies)
                max_latency = max(latencies)
                min_latency = min(latencies)

                print(f"   ✓ Latency stats:")
                print(f"      Average: {avg_latency:.2f}ms")
                print(f"      Min: {min_latency:.2f}ms")
                print(f"      Max: {max_latency:.2f}ms")

                # Verify requirement
                assert avg_latency < 100, f"Average latency {avg_latency:.2f}ms exceeds 100ms requirement"
                print(f"   ✓ Meets REQ-PERF-001: Average latency {avg_latency:.2f}ms < 100ms")

    finally:
        await server.stop()


if __name__ == '__main__':
    # Run with: python tests/dashboard/test_websocket_integration.py
    asyncio.run(test_full_websocket_protocol())
    asyncio.run(test_rapid_message_ordering())
    asyncio.run(test_sub_100ms_latency_requirement())
