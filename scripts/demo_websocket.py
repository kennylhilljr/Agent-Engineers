#!/usr/bin/env python3
"""
Demo script for WebSocket Protocol - All 7 Message Types

This script demonstrates the WebSocket server with all 7 message types
by simulating a complete agent workflow.

Run with: python scripts/demo_websocket.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.websocket_server import AgentStatus, WebSocketServer


async def simulate_agent_workflow(server: WebSocketServer):
    """Simulate a complete agent workflow with all message types."""
    print("\n" + "="*70)
    print("  AGENT DASHBOARD - WEBSOCKET PROTOCOL DEMO")
    print("  Simulating AI-104: WebSocket Protocol Implementation")
    print("="*70 + "\n")

    await asyncio.sleep(1)

    # 1. Orchestrator reasoning
    print("📊 [ORCHESTRATOR] Analyzing ticket...")
    await server.broadcast_reasoning(
        content="Analyzing ticket AI-104: WebSocket Protocol - Real-time Event Types. "
               "This requires implementing 7 message types with async server, "
               "connection management, and sub-100ms latency. "
               "Complexity assessment: COMPLEX (networking, async patterns, real-time requirements).",
        source="orchestrator",
        context={
            'ticket': 'AI-104',
            'complexity': 'COMPLEX',
            'keywords': ['websocket', 'real-time', 'async', 'protocol']
        }
    )
    await asyncio.sleep(1.5)

    # 2. Agent selection decision
    print("🤔 [ORCHESTRATOR] Selecting agent...")
    await server.broadcast_reasoning(
        content="Decision: Delegate to 'coding' agent with claude-sonnet-4-5. "
               "Rationale: Complex networking implementation requires careful design "
               "and robust error handling. Sonnet provides best balance of capability and cost.",
        source="orchestrator",
        context={
            'selected_agent': 'coding',
            'selected_model': 'claude-sonnet-4-5',
            'alternatives_considered': ['coding_fast'],
            'decision_factors': ['complexity', 'reliability_requirements']
        }
    )
    await asyncio.sleep(1.5)

    # 3. Agent status change - start
    print("🚀 [AGENT] Coding agent starting...")
    await server.broadcast_agent_status(
        agent_name="coding",
        status=AgentStatus.RUNNING.value,
        metadata={
            'ticket_key': 'AI-104',
            'model': 'claude-sonnet-4-5',
            'session_id': 'sess-demo-001'
        }
    )
    await asyncio.sleep(1)

    # 4. Code streaming - file 1
    print("💻 [CODE] Writing dashboard/websocket_server.py...")
    code_lines = [
        ('"""WebSocket Server - Real-time Event Protocol for Agent Dashboard."""', 1),
        ('', 2),
        ('import asyncio', 3),
        ('import json', 4),
        ('from dataclasses import dataclass', 5),
        ('from typing import Any, Set', 6),
        ('', 7),
        ('class WebSocketServer:', 10),
        ('    """Async WebSocket server for real-time updates."""', 11),
        ('', 12),
        ('    def __init__(self, host: str, port: int):', 13),
        ('        self.host = host', 14),
        ('        self.port = port', 15),
    ]

    for content, line_num in code_lines:
        await server.broadcast_code_stream(
            content=content,
            file_path="dashboard/websocket_server.py",
            line_number=line_num,
            operation="add",
            language="python"
        )
        await asyncio.sleep(0.1)

    await asyncio.sleep(1)

    # 5. Code streaming - file 2
    print("💻 [CODE] Writing tests/dashboard/test_websocket_server.py...")
    test_lines = [
        ('"""Tests for WebSocket server."""', 1),
        ('', 2),
        ('import pytest', 3),
        ('from dashboard.websocket_server import WebSocketServer', 4),
    ]

    for content, line_num in test_lines:
        await server.broadcast_code_stream(
            content=content,
            file_path="tests/dashboard/test_websocket_server.py",
            line_number=line_num,
            operation="add",
            language="python"
        )
        await asyncio.sleep(0.1)

    await asyncio.sleep(1)

    # 6. Chat message streaming (agent explaining what it did)
    print("💬 [CHAT] Agent response...")
    message_chunks = [
        "I've successfully implemented ",
        "the WebSocket protocol with all 7 message types: ",
        "agent_status, agent_event, reasoning, code_stream, ",
        "chat_message, metrics_update, and control_ack. ",
        "\n\nThe implementation includes: ",
        "async server with aiohttp, ",
        "connection management, ",
        "broadcasting to multiple clients, ",
        "and auto-reconnection support. ",
        "\n\nAll tests pass with 85% coverage, ",
        "and latency requirements are met (0.10ms average, ",
        "well under the 100ms requirement)."
    ]

    message_id = "msg-ai104-completion"
    for i, chunk in enumerate(message_chunks):
        is_final = (i == len(message_chunks) - 1)
        await server.broadcast_chat_message(
            content=chunk,
            message_id=message_id,
            provider="claude",
            is_final=is_final
        )
        await asyncio.sleep(0.15)

    await asyncio.sleep(1)

    # 7. Agent event - completion
    print("✅ [EVENT] Task completed")
    await server.broadcast_agent_event({
        'event_id': 'evt-ai104-001',
        'agent_name': 'coding',
        'session_id': 'sess-demo-001',
        'ticket_key': 'AI-104',
        'status': 'success',
        'duration_seconds': 180.5,
        'total_tokens': 12500,
        'estimated_cost_usd': 0.375,
        'artifacts': [
            'file:dashboard/websocket_server.py:created',
            'file:dashboard/websocket_client.py:created',
            'file:tests/dashboard/test_websocket_server.py:created',
            'file:tests/dashboard/test_websocket_integration.py:created',
            'commit:abc123def456'
        ]
    })
    await asyncio.sleep(1)

    # 8. Metrics update
    print("📈 [METRICS] Dashboard updated")
    await server.broadcast_metrics_update(
        metrics={
            'total_sessions': 42,
            'total_tokens': 250000,
            'total_cost_usd': 7.50,
            'agents': {
                'coding': {
                    'agent_name': 'coding',
                    'total_invocations': 85,
                    'successful_invocations': 82,
                    'success_rate': 0.965,
                    'total_tokens': 150000,
                    'total_cost_usd': 4.50,
                    'xp': 2100,
                    'level': 12
                }
            }
        },
        update_type="full"
    )
    await asyncio.sleep(1)

    # 9. Agent status change - idle
    print("⏸️  [AGENT] Coding agent idle")
    await server.broadcast_agent_status(
        agent_name="coding",
        status=AgentStatus.IDLE.value,
        metadata={
            'ticket_key': 'AI-104',
            'last_status': 'success'
        }
    )
    await asyncio.sleep(1)

    # 10. Control acknowledgment (simulating pause command)
    print("🎛️  [CONTROL] Pause command acknowledged")
    await server.broadcast_control_ack(
        command="pause",
        agent_name="coding",
        status="acknowledged",
        message_text="Agent 'coding' paused. Current task completed successfully. "
                    "Agent will not accept new delegations until resumed."
    )
    await asyncio.sleep(1)

    print("\n" + "="*70)
    print("  ✅ DEMO COMPLETE - All 7 message types demonstrated")
    print("="*70 + "\n")


async def main():
    """Run the demo."""
    # Start server
    server = WebSocketServer(host='127.0.0.1', port=8421)
    await server.start()

    print("\n🌐 WebSocket Server Started")
    print(f"   URL: ws://127.0.0.1:8421/ws")
    print(f"   Connect with: python dashboard/websocket_client.py")
    print("\n   Waiting 3 seconds for clients to connect...")
    print("   (Press Ctrl+C to stop)\n")

    await asyncio.sleep(3)

    try:
        # Run simulation
        await simulate_agent_workflow(server)

        # Keep server running for a bit
        print("Server will keep running for 10 seconds...")
        print("Connect additional clients to see the full history.\n")
        await asyncio.sleep(10)

    except KeyboardInterrupt:
        print("\n\nShutting down...")
    finally:
        await server.stop()
        print("✅ Server stopped\n")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Demo interrupted. Goodbye!\n")
