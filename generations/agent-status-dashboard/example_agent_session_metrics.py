"""Example demonstrating agent.py session metrics instrumentation.

This script shows how the AgentMetricsCollector integrates with the agent.py
session loop to track:
- Session lifecycle (start_session, end_session)
- Multiple agent delegations within a session
- Token usage and cost tracking
- Artifact creation
- Continuation flow across multiple sessions

Run this to see metrics collection in action:
    python example_agent_session_metrics.py
"""

import tempfile
from pathlib import Path

from agent_metrics_collector import AgentMetricsCollector


def print_separator(title: str = ""):
    """Print a visual separator."""
    if title:
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}\n")
    else:
        print(f"\n{'-'*70}\n")


def print_session_summary(collector: AgentMetricsCollector, session_id: str):
    """Print summary of a completed session."""
    state = collector.get_state()

    # Find the session
    session = None
    for s in state["sessions"]:
        if s["session_id"] == session_id:
            session = s
            break

    if not session:
        print(f"Session {session_id} not found")
        return

    print(f"Session {session['session_number']} complete:")
    print(f"- Type: {session['session_type']}")
    print(f"- Status: {session['status']}")
    print(f"- Tokens: {session['total_tokens']}")
    print(f"- Cost: ${session['total_cost_usd']:.4f}")
    print(f"- Agents: {', '.join(session['agents_invoked'])}")
    print(f"- Tickets: {', '.join(session['tickets_worked'])}")


def print_agent_profile(collector: AgentMetricsCollector, agent_name: str):
    """Print agent profile summary."""
    state = collector.get_state()

    if agent_name not in state["agents"]:
        print(f"Agent {agent_name} not found")
        return

    profile = state["agents"][agent_name]

    print(f"\nAgent profile:")
    print(f"  Agent: {profile['agent_name']}")
    print(f"  Invocations: {profile['total_invocations']}")
    print(f"  Success rate: {profile['success_rate']*100:.1f}%")
    print(f"  XP: {profile['xp']}")
    print(f"  Level: {profile['level']}")
    print(f"  Streak: {profile['current_streak']}")
    print(f"  Achievements: {', '.join(profile['achievements']) if profile['achievements'] else 'None'}")
    print(f"  Files created: {profile['files_created']}")
    print(f"  Commits: {profile['commits_made']}")
    print(f"  PRs created: {profile['prs_created']}")


def example_1_basic_session():
    """Example 1: Basic session with single agent."""
    print_separator("Example 1: Basic Session")

    with tempfile.TemporaryDirectory() as tmpdir:
        collector = AgentMetricsCollector(
            project_name="example-project",
            metrics_dir=Path(tmpdir)
        )

        print("Starting session...")
        session_id = collector.start_session(session_type="initializer")
        print(f"Session ID: {session_id}")

        print("\nTracking coding agent...")
        with collector.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id) as tracker:
            # Simulate work
            tracker.add_tokens(input_tokens=2000, output_tokens=3000)
            tracker.add_artifact("file:created:agent_metrics_collector.py")
            tracker.add_artifact("file:created:test_agent_metrics_collector.py")

        print("Ending session...")
        collector.end_session(session_id, status="continue")

        print_separator()
        print_session_summary(collector, session_id)
        print_agent_profile(collector, "coding")


def example_2_multi_agent_session():
    """Example 2: Session with multiple agents (orchestrator pattern)."""
    print_separator("Example 2: Multi-Agent Session")

    with tempfile.TemporaryDirectory() as tmpdir:
        collector = AgentMetricsCollector(
            project_name="example-project",
            metrics_dir=Path(tmpdir)
        )

        session_id = collector.start_session(session_type="initializer")
        print(f"Session ID: {session_id}\n")

        # 1. Linear agent creates issue
        print("1. Linear agent creates issue...")
        with collector.track_agent("linear", "AI-50", "claude-haiku-4-5", session_id) as tracker:
            tracker.add_tokens(500, 300)
            tracker.add_artifact("issue:created:AI-50")

        # 2. Coding agent implements
        print("2. Coding agent implements feature...")
        with collector.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id) as tracker:
            tracker.add_tokens(3000, 5000)
            tracker.add_artifact("file:created:feature.py")
            tracker.add_artifact("file:created:test_feature.py")

        # 3. GitHub agent commits and PRs
        print("3. GitHub agent commits and creates PR...")
        with collector.track_agent("github", "AI-50", "claude-haiku-4-5", session_id) as tracker:
            tracker.add_tokens(400, 250)
            tracker.add_artifact("commit:abc123")
            tracker.add_artifact("pr:created:#50")

        # 4. Slack agent notifies
        print("4. Slack agent sends notification...")
        with collector.track_agent("slack", "AI-50", "claude-haiku-4-5", session_id) as tracker:
            tracker.add_tokens(200, 150)
            tracker.add_artifact("message:channel:engineering")

        collector.end_session(session_id, status="continue")

        print_separator()
        print_session_summary(collector, session_id)

        print("\nAgent profiles:")
        for agent in ["linear", "coding", "github", "slack"]:
            print_agent_profile(collector, agent)


def example_3_continuation_flow():
    """Example 3: Multiple sessions (continuation flow)."""
    print_separator("Example 3: Continuation Flow")

    with tempfile.TemporaryDirectory() as tmpdir:
        collector = AgentMetricsCollector(
            project_name="example-project",
            metrics_dir=Path(tmpdir)
        )

        # Session 1: Initializer
        print("Session 1: Initializer")
        session_id1 = collector.start_session(session_type="initializer")
        with collector.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id1) as tracker:
            tracker.add_tokens(2000, 3000)
            tracker.add_artifact("file:created:impl.py")
        collector.end_session(session_id1, status="continue")
        print_session_summary(collector, session_id1)

        # Session 2: Continuation
        print("\nSession 2: Continuation")
        session_id2 = collector.start_session(session_type="continuation")
        with collector.track_agent("coding", "AI-51", "claude-sonnet-4-5", session_id2) as tracker:
            tracker.add_tokens(1500, 2500)
            tracker.add_artifact("file:created:feature2.py")
        collector.end_session(session_id2, status="continue")
        print_session_summary(collector, session_id2)

        # Session 3: Final
        print("\nSession 3: Final")
        session_id3 = collector.start_session(session_type="continuation")
        with collector.track_agent("coding", "AI-52", "claude-sonnet-4-5", session_id3) as tracker:
            tracker.add_tokens(1000, 2000)
            tracker.add_artifact("file:created:feature3.py")
        collector.end_session(session_id3, status="complete")
        print_session_summary(collector, session_id3)

        print("\nFinal coding agent profile:")
        print_agent_profile(collector, "coding")

        state = collector.get_state()
        print(f"\nTotal sessions: {state['total_sessions']}")
        print(f"Total tokens: {state['total_tokens']}")
        print(f"Total cost: ${state['total_cost_usd']:.4f}")


def example_4_error_handling():
    """Example 4: Error handling in sessions."""
    print_separator("Example 4: Error Handling")

    with tempfile.TemporaryDirectory() as tmpdir:
        collector = AgentMetricsCollector(
            project_name="example-project",
            metrics_dir=Path(tmpdir)
        )

        session_id = collector.start_session()

        # Successful invocation
        print("1. Coding agent succeeds...")
        with collector.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id) as tracker:
            tracker.add_tokens(1000, 2000)
            tracker.add_artifact("file:created:impl.py")

        # Failed invocation
        print("2. Linear agent encounters error...")
        try:
            with collector.track_agent("linear", "AI-50", "claude-haiku-4-5", session_id) as tracker:
                tracker.add_tokens(500, 300)
                raise RuntimeError("API timeout - simulated error")
        except RuntimeError as e:
            print(f"   Caught error: {e}")

        # Another success
        print("3. GitHub agent succeeds...")
        with collector.track_agent("github", "AI-50", "claude-haiku-4-5", session_id) as tracker:
            tracker.add_tokens(300, 200)
            tracker.add_artifact("commit:xyz")

        collector.end_session(session_id, status="error")

        print_separator()
        print_session_summary(collector, session_id)

        state = collector.get_state()
        print("\nEvent statuses:")
        for i, event in enumerate(state["events"], 1):
            print(f"  Event {i} ({event['agent_name']}): {event['status']}")
            if event["error_message"]:
                print(f"    Error: {event['error_message']}")

        print("\nAgent success rates:")
        for agent_name in ["coding", "linear", "github"]:
            if agent_name in state["agents"]:
                profile = state["agents"][agent_name]
                print(f"  {agent_name}: {profile['success_rate']*100:.0f}% ({profile['successful_invocations']}/{profile['total_invocations']})")


def example_5_persistence():
    """Example 5: Persistence across collector instances."""
    print_separator("Example 5: Persistence")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # First collector instance
        print("Creating first collector instance...")
        collector1 = AgentMetricsCollector(
            project_name="example-project",
            metrics_dir=tmpdir_path
        )

        session_id1 = collector1.start_session()
        with collector1.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id1) as tracker:
            tracker.add_tokens(1000, 2000)
        collector1.end_session(session_id1)

        state1 = collector1.get_state()
        print(f"First instance - Total sessions: {state1['total_sessions']}")
        print(f"First instance - Coding invocations: {state1['agents']['coding']['total_invocations']}")

        # Second collector instance (simulates process restart)
        print("\nCreating second collector instance (simulates restart)...")
        collector2 = AgentMetricsCollector(
            project_name="example-project",
            metrics_dir=tmpdir_path
        )

        state2 = collector2.get_state()
        print(f"Second instance - Total sessions: {state2['total_sessions']}")
        print(f"Second instance - Coding invocations: {state2['agents']['coding']['total_invocations']}")
        print("State persisted correctly!")

        # Add another session
        print("\nAdding session from second instance...")
        session_id2 = collector2.start_session(session_type="continuation")
        with collector2.track_agent("coding", "AI-51", "claude-sonnet-4-5", session_id2) as tracker:
            tracker.add_tokens(800, 1500)
        collector2.end_session(session_id2)

        state3 = collector2.get_state()
        print(f"After new session - Total sessions: {state3['total_sessions']}")
        print(f"After new session - Coding invocations: {state3['agents']['coding']['total_invocations']}")

        # Verify metrics file exists
        metrics_file = tmpdir_path / ".agent_metrics.json"
        print(f"\nMetrics file exists: {metrics_file.exists()}")
        print(f"Metrics file size: {metrics_file.stat().st_size} bytes")


def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("  AGENT SESSION METRICS EXAMPLES")
    print("="*70)

    examples = [
        ("Basic Session", example_1_basic_session),
        ("Multi-Agent Session", example_2_multi_agent_session),
        ("Continuation Flow", example_3_continuation_flow),
        ("Error Handling", example_4_error_handling),
        ("Persistence", example_5_persistence),
    ]

    for i, (name, func) in enumerate(examples, 1):
        print(f"\n[{i}/{len(examples)}] Running: {name}")
        try:
            func()
            print(f"\n✓ {name} completed successfully")
        except Exception as e:
            print(f"\n✗ {name} failed: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*70)
    print("  ALL EXAMPLES COMPLETED")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
