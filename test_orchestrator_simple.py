#!/usr/bin/env python3
"""Simple test for orchestrator delegation tracking logic.

This script tests the core delegation tracking logic without requiring
full module imports.
"""

import asyncio
import re
import tempfile
from datetime import datetime
from pathlib import Path

from agent_metrics_collector import AgentMetricsCollector


def extract_ticket_key(task_description: str) -> str:
    """Extract ticket key from task description (same logic as orchestrator)."""
    ticket_match = re.search(r'\b(AI-\d+)\b', task_description)
    return ticket_match.group(1) if ticket_match else "unknown"


async def simulate_delegation_tracking():
    """Simulate the delegation tracking that happens in orchestrator."""
    print("\n" + "=" * 70)
    print("TESTING ORCHESTRATOR DELEGATION TRACKING LOGIC")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        metrics_dir = Path(tmpdir)

        # Create collector
        collector = AgentMetricsCollector(
            project_name="test-orchestrator",
            metrics_dir=metrics_dir
        )

        # Start session
        session_id = collector.start_session(session_type="continuation")
        print(f"\n✓ Started session: {session_id[:8]}...")

        # Simulate Task tool delegations
        print("\n" + "-" * 70)
        print("Simulating 3 Task tool delegations:")
        print("-" * 70)

        delegations = [
            ("coding", "Work on AI-51: Implement delegation tracking", False),
            ("github", "Create PR for AI-51", False),
            ("slack", "Notify team about AI-51 completion", False),
        ]

        for agent_name, task_desc, should_fail in delegations:
            # Extract ticket key (same logic as orchestrator)
            ticket_key = extract_ticket_key(task_desc)

            print(f"\n→ Delegation: {agent_name}")
            print(f"  Task: {task_desc}")
            print(f"  Extracted ticket: {ticket_key}")

            # Track delegation
            with collector.track_agent(
                agent_name=agent_name,
                ticket_key=ticket_key,
                model_used="claude-haiku-4-5",
                session_id=session_id
            ) as tracker:
                # Simulate work
                await asyncio.sleep(0.05)

                # Add token counts (same as orchestrator)
                tracker.add_tokens(input_tokens=500, output_tokens=1000)

                # Add artifacts
                tracker.add_artifact(f"delegation:{agent_name}")

                if should_fail:
                    tracker.set_error("Simulated error")

            print(f"  ✓ Tracked")

        # End session
        collector.end_session(session_id, status="complete")
        print(f"\n✓ Session ended")

        # Verification
        print("\n" + "=" * 70)
        print("VERIFICATION")
        print("=" * 70)

        state = collector.get_state()

        # Check events
        print(f"\n✓ Events recorded: {len(state['events'])}")
        assert len(state['events']) == 3, f"Expected 3 events, got {len(state['events'])}"

        for i, event in enumerate(state['events'], 1):
            print(f"\nEvent {i}:")
            print(f"  - Agent: {event['agent_name']}")
            print(f"  - Ticket: {event['ticket_key']}")
            print(f"  - Status: {event['status']}")
            print(f"  - Tokens: {event['input_tokens']} in, {event['output_tokens']} out")
            print(f"  - Duration: {event['duration_seconds']:.3f}s")
            print(f"  - Cost: ${event['estimated_cost_usd']:.6f}")

            assert event['ticket_key'] == "AI-51"
            assert event['status'] == "success"
            assert event['input_tokens'] == 500
            assert event['output_tokens'] == 1000
            assert event['duration_seconds'] > 0

        # Check session
        session = state['sessions'][0]
        print(f"\nSession summary:")
        print(f"  - Session ID: {session['session_id'][:8]}...")
        print(f"  - Agents invoked: {session['agents_invoked']}")
        print(f"  - Tickets worked: {session['tickets_worked']}")
        print(f"  - Total tokens: {session['total_tokens']}")
        print(f"  - Total cost: ${session['total_cost_usd']:.6f}")

        assert set(session['agents_invoked']) == {"coding", "github", "slack"}
        assert session['tickets_worked'] == ["AI-51"]
        assert session['total_tokens'] == 4500  # 3 × 1500

        # Check agent profiles
        print(f"\nAgent profiles created:")
        for agent_name in ["coding", "github", "slack"]:
            assert agent_name in state['agents']
            profile = state['agents'][agent_name]
            print(f"  - {agent_name}: {profile['total_invocations']} invocations, "
                  f"{profile['total_tokens']} tokens")

        print("\n" + "=" * 70)
        print("ALL TESTS PASSED ✓")
        print("=" * 70)

        # Show metrics file
        metrics_file = metrics_dir / ".agent_metrics.json"
        print(f"\nMetrics saved to: {metrics_file}")
        print(f"File size: {metrics_file.stat().st_size} bytes")

        return True


async def test_ticket_extraction():
    """Test ticket key extraction logic."""
    print("\n" + "=" * 70)
    print("TESTING TICKET KEY EXTRACTION")
    print("=" * 70)

    test_cases = [
        ("Work on AI-51: Implement feature", "AI-51"),
        ("AI-123 needs implementation", "AI-123"),
        ("Implement AI-999", "AI-999"),
        ("Fix bug in AI-1", "AI-1"),
        ("No ticket here", "unknown"),
        ("", "unknown"),
    ]

    print("\nTest cases:")
    for task_desc, expected in test_cases:
        result = extract_ticket_key(task_desc)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{task_desc}' → '{result}' (expected '{expected}')")
        assert result == expected, f"Failed for '{task_desc}'"

    print("\n✓ All extraction tests passed!")


async def test_error_tracking():
    """Test error tracking in delegations."""
    print("\n" + "=" * 70)
    print("TESTING ERROR TRACKING")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        collector = AgentMetricsCollector("test-error", Path(tmpdir))
        session_id = collector.start_session()

        print("\n→ Simulating failed delegation...")

        # Track failing delegation
        with collector.track_agent(
            agent_name="coding",
            ticket_key="AI-51",
            model_used="claude-sonnet-4-5",
            session_id=session_id
        ) as tracker:
            tracker.add_tokens(500, 1000)
            tracker.set_error("Tests failed: 3 tests did not pass")

        collector.end_session(session_id, status="error")

        # Verify
        state = collector.get_state()
        event = state['events'][0]

        print(f"\n✓ Event recorded with error status")
        print(f"  - Status: {event['status']}")
        print(f"  - Error: {event['error_message']}")

        assert event['status'] == "error"
        assert "Tests failed" in event['error_message']

        # Check agent profile
        profile = state['agents']['coding']
        print(f"\n✓ Agent profile updated:")
        print(f"  - Failed invocations: {profile['failed_invocations']}")
        print(f"  - Success rate: {profile['success_rate']:.1%}")

        assert profile['failed_invocations'] == 1
        assert profile['successful_invocations'] == 0
        assert profile['success_rate'] == 0.0

    print("\n✓ Error tracking test passed!")


async def main():
    """Run all tests."""
    print("\n" + "╔" + "=" * 68 + "╗")
    print("║" + " " * 12 + "ORCHESTRATOR DELEGATION TRACKING - SIMPLE TESTS" + " " * 9 + "║")
    print("╚" + "=" * 68 + "╝")

    try:
        await test_ticket_extraction()
        await test_error_tracking()
        await simulate_delegation_tracking()

        print("\n" + "╔" + "=" * 68 + "╗")
        print("║" + " " * 22 + "ALL TESTS PASSED ✓" + " " * 24 + "║")
        print("╚" + "=" * 68 + "╝\n")

        print("SUMMARY:")
        print("-" * 70)
        print("✓ Ticket key extraction working correctly")
        print("✓ Error tracking working correctly")
        print("✓ Delegation tracking logic working correctly")
        print("✓ Token attribution working correctly")
        print("✓ Session aggregation working correctly")
        print("✓ Agent profiles updated correctly")
        print("-" * 70)
        print("\nThe orchestrator instrumentation is ready for integration!")
        print()

        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
