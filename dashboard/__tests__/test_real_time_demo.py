"""Demonstration script for real-time metrics broadcasting.

This script starts the dashboard server, simulates agent tasks,
and captures the real-time event broadcasting in action.
"""

import asyncio
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dashboard.collector import AgentMetricsCollector
from dashboard.server import DashboardServer


async def simulate_agent_tasks(collector: AgentMetricsCollector, num_tasks: int = 3):
    """Simulate multiple agent tasks to demonstrate real-time broadcasting."""
    session_id = collector.start_session(session_type="initializer")

    print(f"\n{'='*60}")
    print("SIMULATING AGENT TASKS FOR REAL-TIME BROADCASTING DEMO")
    print(f"{'='*60}\n")

    for i in range(num_tasks):
        agent_name = f"agent-{i+1}"
        ticket = f"AI-{100+i}"

        print(f"[Task {i+1}] Starting {agent_name} on {ticket}...")

        try:
            with collector.track_agent(
                agent_name=agent_name,
                ticket_key=ticket,
                model_used="claude-sonnet-4-5",
                session_id=session_id
            ) as tracker:
                # Simulate work
                await asyncio.sleep(0.5)

                # Add token usage
                tokens_in = 1000 + (i * 500)
                tokens_out = 2000 + (i * 1000)
                tracker.add_tokens(tokens_in, tokens_out)

                # Add artifacts
                tracker.add_artifact(f"file:agent_{i+1}.py")
                tracker.add_artifact(f"commit:abc{i+1}23")

                print(f"[Task {i+1}] ✓ {agent_name} completed successfully")
                print(f"           Tokens: {tokens_in} in, {tokens_out} out")
                print(f"           Artifacts: 2 created\n")

        except Exception as e:
            print(f"[Task {i+1}] ✗ {agent_name} failed: {e}\n")

        # Brief pause between tasks
        if i < num_tasks - 1:
            await asyncio.sleep(0.3)

    collector.end_session(session_id, status="complete")

    print(f"{'='*60}")
    print("ALL TASKS COMPLETED")
    print(f"{'='*60}\n")


async def run_demo():
    """Run the real-time broadcasting demonstration."""
    import tempfile

    # Create temporary metrics directory
    temp_dir = Path(tempfile.mkdtemp())

    print(f"\n{'='*60}")
    print("REAL-TIME METRICS BROADCASTING DEMO - AI-107")
    print(f"{'='*60}")
    print(f"Metrics directory: {temp_dir}")
    print(f"{'='*60}\n")

    # Create server
    server = DashboardServer(
        project_name="ai-107-demo",
        metrics_dir=temp_dir,
        port=18082,
        host="127.0.0.1"
    )

    # Setup event logging
    event_count = {"started": 0, "completed": 0, "failed": 0}

    def log_event(event_type: str, event):
        event_count[event_type.replace("task_", "")] += 1
        print(f"[WebSocket] Broadcasting {event_type}: {event['agent_name']} ({event['ticket_key']})")

    server.collector.subscribe(log_event)

    # Start server
    from aiohttp import web
    runner = web.AppRunner(server.app)
    await runner.setup()
    site = web.TCPSite(runner, server.host, server.port)
    await site.start()

    print(f"Dashboard server started at http://{server.host}:{server.port}")
    print(f"WebSocket endpoint: ws://{server.host}:{server.port}/ws")
    print(f"\nWaiting for server to initialize...\n")

    await asyncio.sleep(1)

    # Simulate tasks
    await simulate_agent_tasks(server.collector, num_tasks=5)

    # Show summary
    print(f"\nBROADCAST SUMMARY:")
    print(f"  - task_started events:   {event_count['started']}")
    print(f"  - task_completed events: {event_count['completed']}")
    print(f"  - task_failed events:    {event_count['failed']}")
    print(f"  - Total events:          {sum(event_count.values())}\n")

    # Verify metrics stored
    state = server.collector.get_state()
    print(f"METRICS STATE:")
    print(f"  - Total events recorded: {len(state['events'])}")
    print(f"  - Agents tracked:        {len(state['agents'])}")
    print(f"  - Sessions:              {state['total_sessions']}")
    print(f"  - Total tokens:          {state['total_tokens']}")
    print(f"  - Total cost:            ${state['total_cost_usd']:.4f}\n")

    # Keep server running briefly
    print("Server will remain active for 3 seconds...")
    await asyncio.sleep(3)

    # Cleanup
    print("Shutting down server...")
    await runner.cleanup()

    print(f"\n{'='*60}")
    print("DEMO COMPLETE")
    print(f"{'='*60}\n")

    return event_count, state


if __name__ == "__main__":
    # Run the demo
    event_count, state = asyncio.run(run_demo())

    # Verify results
    assert event_count["started"] == 5, "Should have 5 task_started events"
    assert event_count["completed"] == 5, "Should have 5 task_completed events"
    assert event_count["failed"] == 0, "Should have 0 task_failed events"

    assert len(state["events"]) == 5, "Should have 5 events recorded"
    assert len(state["agents"]) == 5, "Should have 5 agents tracked"

    print("✓ All assertions passed!")
    print("✓ Real-time broadcasting working correctly!")
