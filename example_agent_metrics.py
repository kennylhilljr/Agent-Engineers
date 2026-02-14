"""Example usage of Agent Metrics Collection System.

This script demonstrates how to use the AgentMetricsCollector to track
session lifecycle and agent delegations in the Agent Status Dashboard.

Examples:
1. Simple session lifecycle (start → track → end)
2. Multi-agent session
3. Session continuation flow
4. Viewing metrics and profiles
"""

import json
import tempfile
import time
from pathlib import Path

from agent_metrics import AgentMetricsCollector


def example_simple_session():
    """Example 1: Simple session lifecycle."""
    print("\n" + "=" * 70)
    print("Example 1: Simple Session Lifecycle")
    print("=" * 70)

    # Create temporary directory for this example
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        collector = AgentMetricsCollector(project_dir)

        # Start a session
        print("\n1. Starting session...")
        session_id = collector.start_session(session_num=1, is_initializer=True)
        print(f"   Session ID: {session_id[:8]}...")

        # Track an agent delegation
        print("\n2. Tracking agent delegation...")
        with collector.track_agent("coding", ticket_key="AI-50") as tracker:
            # Simulate some work
            print("   Agent is working...")
            time.sleep(0.1)

            # Record tokens and artifacts
            tracker.set_tokens(input_tokens=1000, output_tokens=500)
            tracker.add_artifact("file:agent_metrics.py")
            print(f"   Recorded: 1500 tokens, 1 artifact")

        # End the session
        print("\n3. Ending session...")
        summary = collector.end_session(status="continue")
        print(f"   Session {summary['session_number']} complete:")
        print(f"   - Type: {summary['session_type']}")
        print(f"   - Status: {summary['status']}")
        print(f"   - Tokens: {summary['total_tokens']}")
        print(f"   - Cost: ${summary['total_cost_usd']:.4f}")
        print(f"   - Agents: {', '.join(summary['agents_invoked'])}")

        # View agent profile
        print("\n4. Agent profile:")
        profile = collector.get_agent_profile("coding")
        print(f"   Agent: {profile['agent_name']}")
        print(f"   Invocations: {profile['total_invocations']}")
        print(f"   Success rate: {profile['success_rate']:.1%}")
        print(f"   XP: {profile['xp']}")
        print(f"   Level: {profile['level']}")
        print(f"   Streak: {profile['current_streak']}")
        print(f"   Achievements: {', '.join(profile['achievements']) or 'None yet'}")


def example_multi_agent_session():
    """Example 2: Multi-agent session."""
    print("\n" + "=" * 70)
    print("Example 2: Multi-Agent Session")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        collector = AgentMetricsCollector(project_dir)

        # Start session
        print("\n1. Starting session...")
        collector.start_session(session_num=1)

        # Multiple agents working on the same ticket
        print("\n2. Tracking multiple agent delegations...")

        print("   - Linear agent creates issue...")
        with collector.track_agent("linear", ticket_key="AI-50") as tracker:
            tracker.set_tokens(input_tokens=300, output_tokens=150)
            tracker.add_artifact("issue:AI-50")

        print("   - Coding agent implements feature...")
        with collector.track_agent("coding", ticket_key="AI-50") as tracker:
            tracker.set_tokens(input_tokens=2000, output_tokens=1500)
            tracker.add_artifact("file:feature.py")
            tracker.add_artifact("file:test_feature.py")

        print("   - GitHub agent commits and creates PR...")
        with collector.track_agent("github", ticket_key="AI-50") as tracker:
            tracker.set_tokens(input_tokens=500, output_tokens=300)
            tracker.add_artifact("commit:abc123")
            tracker.add_artifact("pr:#42")

        print("   - Slack agent notifies team...")
        with collector.track_agent("slack", ticket_key="AI-50") as tracker:
            tracker.set_tokens(input_tokens=200, output_tokens=100)
            tracker.add_artifact("message:channel-general")

        # End session
        print("\n3. Session summary:")
        summary = collector.end_session(status="continue")
        print(f"   Agents invoked: {', '.join(summary['agents_invoked'])}")
        print(f"   Total tokens: {summary['total_tokens']:,}")
        print(f"   Total cost: ${summary['total_cost_usd']:.4f}")
        print(f"   Tickets worked: {', '.join(summary['tickets_worked'])}")

        # Show all agent profiles
        print("\n4. Agent profiles:")
        for agent_name in summary['agents_invoked']:
            profile = collector.get_agent_profile(agent_name)
            print(f"   {agent_name}:")
            print(f"     - Invocations: {profile['total_invocations']}")
            print(f"     - Tokens: {profile['total_tokens']}")
            print(f"     - XP: {profile['xp']}")


def example_session_continuation():
    """Example 3: Session continuation flow."""
    print("\n" + "=" * 70)
    print("Example 3: Session Continuation Flow")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        collector = AgentMetricsCollector(project_dir)

        # Session 1 (initializer)
        print("\n1. Session 1 (Initializer):")
        collector.start_session(session_num=1, is_initializer=True)
        with collector.track_agent("linear", ticket_key="AI-50"):
            pass
        with collector.track_agent("coding", ticket_key="AI-50"):
            pass
        summary1 = collector.end_session(status="continue")
        print(f"   Type: {summary1['session_type']}")
        print(f"   Agents: {', '.join(summary1['agents_invoked'])}")

        # Session 2 (continuation)
        print("\n2. Session 2 (Continuation):")
        collector.start_session(session_num=2, is_initializer=False)
        with collector.track_agent("coding", ticket_key="AI-51"):
            pass
        with collector.track_agent("github", ticket_key="AI-51"):
            pass
        summary2 = collector.end_session(status="continue")
        print(f"   Type: {summary2['session_type']}")
        print(f"   Agents: {', '.join(summary2['agents_invoked'])}")

        # Session 3 (continuation, complete)
        print("\n3. Session 3 (Continuation, Complete):")
        collector.start_session(session_num=3, is_initializer=False)
        with collector.track_agent("coding", ticket_key="AI-52"):
            pass
        summary3 = collector.end_session(status="complete")
        print(f"   Type: {summary3['session_type']}")
        print(f"   Status: {summary3['status']}")

        # Show overall metrics
        print("\n4. Overall project metrics:")
        state = collector.get_dashboard_state()
        print(f"   Total sessions: {state['total_sessions']}")
        print(f"   Total tokens: {state['total_tokens']:,}")
        print(f"   Total cost: ${state['total_cost_usd']:.4f}")
        print(f"   Agents tracked: {', '.join(state['agents'].keys())}")

        # Show coding agent progression
        print("\n5. Coding agent progression:")
        profile = collector.get_agent_profile("coding")
        print(f"   Total invocations: {profile['total_invocations']}")
        print(f"   Success rate: {profile['success_rate']:.1%}")
        print(f"   XP: {profile['xp']}")
        print(f"   Level: {profile['level']}")
        print(f"   Current streak: {profile['current_streak']}")
        print(f"   Best streak: {profile['best_streak']}")


def example_viewing_metrics():
    """Example 4: Viewing metrics and profiles."""
    print("\n" + "=" * 70)
    print("Example 4: Viewing Metrics and Profiles")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        collector = AgentMetricsCollector(project_dir)

        # Create some activity
        print("\n1. Creating sample activity...")
        collector.start_session(session_num=1)

        # Multiple successful invocations
        for i in range(5):
            with collector.track_agent("coding", ticket_key=f"AI-{50 + i}") as tracker:
                tracker.set_tokens(
                    input_tokens=1000 + i * 100,
                    output_tokens=500 + i * 50
                )

        collector.end_session()

        # View dashboard state
        print("\n2. Dashboard State:")
        state = collector.get_dashboard_state()
        print(f"   Project: {state['project_name']}")
        print(f"   Version: {state['version']}")
        print(f"   Created: {state['created_at']}")
        print(f"   Total sessions: {state['total_sessions']}")
        print(f"   Total events: {len(state['events'])}")

        # View agent profile details
        print("\n3. Coding Agent Profile:")
        profile = collector.get_agent_profile("coding")
        print(f"   Invocations: {profile['total_invocations']}")
        print(f"   Success rate: {profile['success_rate']:.1%}")
        print(f"   Total tokens: {profile['total_tokens']:,}")
        print(f"   Avg tokens/call: {profile['avg_tokens_per_call']:.0f}")
        print(f"   Total cost: ${profile['total_cost_usd']:.4f}")
        print(f"   Cost/success: ${profile['cost_per_success_usd']:.4f}")
        print(f"   XP: {profile['xp']}")
        print(f"   Level: {profile['level']}")
        print(f"   Streak: {profile['current_streak']}/{profile['best_streak']}")
        print(f"   Achievements: {', '.join(profile['achievements']) or 'None'}")
        print(f"   Strengths: {', '.join(profile['strengths']) or 'None detected yet'}")
        print(f"   Weaknesses: {', '.join(profile['weaknesses']) or 'None detected yet'}")

        # View recent events
        print("\n4. Recent Events:")
        for i, event_id in enumerate(profile['recent_events'][-3:], 1):
            event = next(e for e in state['events'] if e['event_id'] == event_id)
            print(f"   Event {i}:")
            print(f"     - Ticket: {event['ticket_key']}")
            print(f"     - Tokens: {event['total_tokens']}")
            print(f"     - Duration: {event['duration_seconds']:.2f}s")
            print(f"     - Status: {event['status']}")

        # View metrics file location
        print(f"\n5. Metrics file: {collector.store.metrics_file}")
        print(f"   File exists: {collector.store.metrics_file.exists()}")
        if collector.store.metrics_file.exists():
            size = collector.store.metrics_file.stat().st_size
            print(f"   File size: {size:,} bytes")


def example_persistence():
    """Example 5: Persistence across collector instances."""
    print("\n" + "=" * 70)
    print("Example 5: Persistence Across Instances")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # First instance
        print("\n1. First collector instance:")
        collector1 = AgentMetricsCollector(project_dir)
        collector1.start_session(session_num=1)
        with collector1.track_agent("coding", ticket_key="AI-50"):
            pass
        collector1.end_session()
        print(f"   Total sessions: {collector1.state['total_sessions']}")
        print(f"   Total events: {len(collector1.state['events'])}")

        # Second instance (simulating restart)
        print("\n2. Second collector instance (after restart):")
        collector2 = AgentMetricsCollector(project_dir)
        print(f"   Total sessions: {collector2.state['total_sessions']}")
        print(f"   Total events: {len(collector2.state['events'])}")
        print(f"   ✓ State persisted and loaded successfully!")

        # Continue with more work
        print("\n3. Adding more work in second instance:")
        collector2.start_session(session_num=2)
        with collector2.track_agent("coding", ticket_key="AI-51"):
            pass
        collector2.end_session()
        print(f"   Total sessions: {collector2.state['total_sessions']}")
        print(f"   Total events: {len(collector2.state['events'])}")

        # Third instance
        print("\n4. Third collector instance (another restart):")
        collector3 = AgentMetricsCollector(project_dir)
        print(f"   Total sessions: {collector3.state['total_sessions']}")
        print(f"   Total events: {len(collector3.state['events'])}")
        profile = collector3.get_agent_profile("coding")
        print(f"   Coding agent invocations: {profile['total_invocations']}")
        print(f"   ✓ All metrics accumulated correctly!")


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("  AGENT METRICS COLLECTION SYSTEM - EXAMPLES")
    print("=" * 70)

    example_simple_session()
    example_multi_agent_session()
    example_session_continuation()
    example_viewing_metrics()
    example_persistence()

    print("\n" + "=" * 70)
    print("  EXAMPLES COMPLETE")
    print("=" * 70)
    print("\nKey takeaways:")
    print("1. Use start_session() to begin tracking")
    print("2. Use track_agent() context manager for each delegation")
    print("3. Use end_session() to finalize and persist")
    print("4. Metrics automatically integrate with XP, achievements, and strengths/weaknesses")
    print("5. State persists across collector instances")
    print("\n")


if __name__ == "__main__":
    main()
