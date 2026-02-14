"""Integration tests for Agent Metrics Collection System.

Tests the complete session lifecycle including start_session, track_agent,
and end_session, as well as realistic multi-session scenarios and edge cases.

Test Coverage:
- Complete session lifecycle (start → track → end)
- Multi-session scenarios
- Multiple agents in a session
- Session continuation flow
- Error handling and recovery
- Persistence across sessions
- Real-world usage patterns
"""

import tempfile
import time
from pathlib import Path

import pytest

from agent_metrics import AgentMetricsCollector


class TestSessionLifecycle:
    """Test complete session lifecycle scenarios."""

    def test_simple_session_lifecycle(self, tmp_path: Path):
        """Test a simple complete session lifecycle."""
        collector = AgentMetricsCollector(tmp_path)

        # Start session
        session_id = collector.start_session(session_num=1, is_initializer=True)
        assert session_id is not None
        assert collector.current_session_id == session_id

        # Track agent work
        with collector.track_agent("coding", ticket_key="AI-50") as tracker:
            tracker.set_tokens(input_tokens=1000, output_tokens=500)
            tracker.add_artifact("file:agent_metrics.py")

        # End session
        summary = collector.end_session(status="continue")

        # Verify summary
        assert summary["session_number"] == 1
        assert summary["session_type"] == "initializer"
        assert summary["status"] == "continue"
        assert summary["total_tokens"] == 1500
        assert "coding" in summary["agents_invoked"]
        assert "AI-50" in summary["tickets_worked"]

        # Verify state
        assert collector.state["total_sessions"] == 1
        assert len(collector.state["sessions"]) == 1
        assert len(collector.state["events"]) == 1
        assert "coding" in collector.state["agents"]

    def test_multiple_agents_in_session(self, tmp_path: Path):
        """Test a session with multiple agent invocations."""
        collector = AgentMetricsCollector(tmp_path)

        collector.start_session(session_num=1)

        # Multiple agents working on same ticket
        with collector.track_agent("coding", ticket_key="AI-50") as tracker:
            tracker.set_tokens(input_tokens=1000, output_tokens=500)
            tracker.add_artifact("file:agent_metrics.py")

        with collector.track_agent("github", ticket_key="AI-50") as tracker:
            tracker.set_tokens(input_tokens=500, output_tokens=250)
            tracker.add_artifact("commit:abc123")

        with collector.track_agent("linear", ticket_key="AI-50") as tracker:
            tracker.set_tokens(input_tokens=200, output_tokens=100)
            tracker.add_artifact("issue:AI-50")

        summary = collector.end_session()

        # Verify all agents are tracked
        assert len(summary["agents_invoked"]) == 3
        assert "coding" in summary["agents_invoked"]
        assert "github" in summary["agents_invoked"]
        assert "linear" in summary["agents_invoked"]

        # Verify tokens are accumulated
        assert summary["total_tokens"] == 2550  # 1500 + 750 + 300

        # Verify all agent profiles exist
        assert "coding" in collector.state["agents"]
        assert "github" in collector.state["agents"]
        assert "linear" in collector.state["agents"]

    def test_session_with_mixed_success_failure(self, tmp_path: Path):
        """Test a session with both successful and failed invocations."""
        collector = AgentMetricsCollector(tmp_path)

        collector.start_session(session_num=1)

        # Success
        with collector.track_agent("coding"):
            pass

        # Failure
        with collector.track_agent("coding") as tracker:
            tracker.set_error("Test error")

        # Success again
        with collector.track_agent("coding"):
            pass

        collector.end_session()

        # Verify profile
        profile = collector.get_agent_profile("coding")
        assert profile["total_invocations"] == 3
        assert profile["successful_invocations"] == 2
        assert profile["failed_invocations"] == 1
        assert profile["success_rate"] == 2.0 / 3.0
        assert profile["current_streak"] == 1  # Reset after failure, then 1 success
        assert profile["best_streak"] == 1

    def test_continuation_session_flow(self, tmp_path: Path):
        """Test the continuation session flow (multiple sequential sessions)."""
        collector = AgentMetricsCollector(tmp_path)

        # Session 1 (initializer)
        collector.start_session(session_num=1, is_initializer=True)
        with collector.track_agent("coding"):
            pass
        summary1 = collector.end_session(status="continue")

        # Session 2 (continuation)
        collector.start_session(session_num=2, is_initializer=False)
        with collector.track_agent("coding"):
            pass
        summary2 = collector.end_session(status="continue")

        # Session 3 (continuation)
        collector.start_session(session_num=3, is_initializer=False)
        with collector.track_agent("coding"):
            pass
        summary3 = collector.end_session(status="complete")

        # Verify summaries
        assert summary1["session_type"] == "initializer"
        assert summary2["session_type"] == "continuation"
        assert summary3["session_type"] == "continuation"
        assert summary3["status"] == "complete"

        # Verify state
        assert collector.state["total_sessions"] == 3
        assert len(collector.state["sessions"]) == 3

        # Verify profile accumulation
        profile = collector.get_agent_profile("coding")
        assert profile["total_invocations"] == 3

    def test_session_with_multiple_tickets(self, tmp_path: Path):
        """Test a session working on multiple tickets."""
        collector = AgentMetricsCollector(tmp_path)

        collector.start_session(session_num=1)

        # Work on different tickets
        with collector.track_agent("coding", ticket_key="AI-50"):
            pass

        with collector.track_agent("coding", ticket_key="AI-51"):
            pass

        with collector.track_agent("github", ticket_key="AI-50"):
            pass

        summary = collector.end_session()

        # Verify tickets
        assert len(summary["tickets_worked"]) == 2
        assert "AI-50" in summary["tickets_worked"]
        assert "AI-51" in summary["tickets_worked"]


class TestErrorHandlingAndRecovery:
    """Test error handling and recovery scenarios."""

    def test_error_in_agent_delegation(self, tmp_path: Path):
        """Test handling errors within agent delegation."""
        collector = AgentMetricsCollector(tmp_path)

        collector.start_session(session_num=1)

        with collector.track_agent("coding") as tracker:
            tracker.set_error("Simulated error")

        collector.end_session()

        # Verify error is recorded
        event = collector.state["events"][0]
        assert event["status"] == "error"
        assert event["error_message"] == "Simulated error"

        profile = collector.get_agent_profile("coding")
        assert profile["failed_invocations"] == 1
        assert profile["last_error"] == "Simulated error"

    def test_session_error_status(self, tmp_path: Path):
        """Test ending a session with error status."""
        collector = AgentMetricsCollector(tmp_path)

        collector.start_session(session_num=1)

        with collector.track_agent("coding") as tracker:
            tracker.set_error("Session error")

        summary = collector.end_session(status="error")

        assert summary["status"] == "error"

    def test_recovery_after_failed_session(self, tmp_path: Path):
        """Test that system can recover after a failed session."""
        collector = AgentMetricsCollector(tmp_path)

        # Failed session
        collector.start_session(session_num=1)
        with collector.track_agent("coding") as tracker:
            tracker.set_error("Error")
        collector.end_session(status="error")

        # Recovery session
        collector.start_session(session_num=2)
        with collector.track_agent("coding"):
            pass
        summary = collector.end_session(status="continue")

        assert summary["status"] == "continue"
        assert collector.state["total_sessions"] == 2


class TestPersistence:
    """Test persistence and state recovery."""

    def test_persistence_across_collector_instances(self, tmp_path: Path):
        """Test that state persists across collector instances."""
        # First instance
        collector1 = AgentMetricsCollector(tmp_path)
        collector1.start_session(session_num=1)

        with collector1.track_agent("coding", ticket_key="AI-50") as tracker:
            tracker.set_tokens(input_tokens=1000, output_tokens=500)
            tracker.add_artifact("file:test.py")

        collector1.end_session()

        # Second instance (simulating restart)
        collector2 = AgentMetricsCollector(tmp_path)

        # Verify state loaded
        assert collector2.state["total_sessions"] == 1
        assert len(collector2.state["events"]) == 1
        assert "coding" in collector2.state["agents"]

        profile = collector2.get_agent_profile("coding")
        assert profile["total_invocations"] == 1
        assert profile["total_tokens"] == 1500

    def test_accumulation_across_restarts(self, tmp_path: Path):
        """Test that metrics accumulate correctly across restarts."""
        # First session
        collector1 = AgentMetricsCollector(tmp_path)
        collector1.start_session(session_num=1)
        with collector1.track_agent("coding"):
            pass
        collector1.end_session()

        # Restart and second session
        collector2 = AgentMetricsCollector(tmp_path)
        collector2.start_session(session_num=2)
        with collector2.track_agent("coding"):
            pass
        collector2.end_session()

        # Restart and verify
        collector3 = AgentMetricsCollector(tmp_path)
        assert collector3.state["total_sessions"] == 2

        profile = collector3.get_agent_profile("coding")
        assert profile["total_invocations"] == 2


class TestRealWorldScenarios:
    """Test realistic multi-agent session scenarios."""

    def test_typical_feature_implementation_session(self, tmp_path: Path):
        """Test a typical feature implementation session."""
        collector = AgentMetricsCollector(tmp_path)

        collector.start_session(session_num=1, is_initializer=False)

        # Linear agent creates issue
        with collector.track_agent("linear", ticket_key="AI-50") as tracker:
            tracker.set_tokens(input_tokens=300, output_tokens=150)
            tracker.add_artifact("issue:AI-50")

        # Coding agent implements feature
        with collector.track_agent("coding", ticket_key="AI-50") as tracker:
            tracker.set_tokens(input_tokens=2000, output_tokens=1500)
            tracker.add_artifact("file:feature.py")
            tracker.add_artifact("file:test_feature.py")

        # GitHub agent commits and creates PR
        with collector.track_agent("github", ticket_key="AI-50") as tracker:
            tracker.set_tokens(input_tokens=500, output_tokens=300)
            tracker.add_artifact("commit:abc123")
            tracker.add_artifact("pr:#42")

        # Slack agent notifies team
        with collector.track_agent("slack", ticket_key="AI-50") as tracker:
            tracker.set_tokens(input_tokens=200, output_tokens=100)
            tracker.add_artifact("message:channel-general")

        summary = collector.end_session(status="continue")

        # Verify session summary
        assert len(summary["agents_invoked"]) == 4
        assert summary["total_tokens"] == 5050  # Sum of all tokens
        assert "AI-50" in summary["tickets_worked"]

        # Verify all agents have profiles
        assert "linear" in collector.state["agents"]
        assert "coding" in collector.state["agents"]
        assert "github" in collector.state["agents"]
        assert "slack" in collector.state["agents"]

    def test_long_running_project_simulation(self, tmp_path: Path):
        """Test a long-running project with many sessions."""
        collector = AgentMetricsCollector(tmp_path)

        # Simulate 10 sessions
        for session_num in range(1, 11):
            is_initializer = session_num == 1

            collector.start_session(session_num=session_num, is_initializer=is_initializer)

            # 3-5 agent invocations per session
            num_invocations = (session_num % 3) + 3
            for _ in range(num_invocations):
                with collector.track_agent("coding", ticket_key=f"AI-{50 + session_num}"):
                    pass

            collector.end_session(status="continue" if session_num < 10 else "complete")

        # Verify accumulation
        assert collector.state["total_sessions"] == 10
        assert len(collector.state["sessions"]) == 10

        profile = collector.get_agent_profile("coding")
        assert profile["total_invocations"] > 30  # At least 30 invocations total

    def test_multi_agent_collaboration(self, tmp_path: Path):
        """Test multiple agents collaborating on the same ticket."""
        collector = AgentMetricsCollector(tmp_path)

        collector.start_session(session_num=1)

        ticket_key = "AI-50"

        # Linear creates issue
        with collector.track_agent("linear", ticket_key=ticket_key):
            pass

        # Coding implements
        with collector.track_agent("coding", ticket_key=ticket_key):
            pass

        # Coding writes tests
        with collector.track_agent("coding", ticket_key=ticket_key):
            pass

        # GitHub commits
        with collector.track_agent("github", ticket_key=ticket_key):
            pass

        # PR review
        with collector.track_agent("pr_reviewer", ticket_key=ticket_key):
            pass

        # GitHub merges
        with collector.track_agent("github", ticket_key=ticket_key):
            pass

        # Linear updates status
        with collector.track_agent("linear", ticket_key=ticket_key):
            pass

        # Slack notifies
        with collector.track_agent("slack", ticket_key=ticket_key):
            pass

        summary = collector.end_session()

        # All agents should be in summary
        assert len(summary["agents_invoked"]) == 5  # linear, coding, github, pr_reviewer, slack

        # Only one ticket
        assert len(summary["tickets_worked"]) == 1
        assert ticket_key in summary["tickets_worked"]

    def test_streaks_across_sessions(self, tmp_path: Path):
        """Test that streaks accumulate correctly across sessions."""
        collector = AgentMetricsCollector(tmp_path)

        # Session 1: 3 successes
        collector.start_session(session_num=1)
        for _ in range(3):
            with collector.track_agent("coding"):
                pass
        collector.end_session()

        profile = collector.get_agent_profile("coding")
        assert profile["current_streak"] == 3
        assert profile["best_streak"] == 3

        # Session 2: 2 more successes
        collector.start_session(session_num=2)
        for _ in range(2):
            with collector.track_agent("coding"):
                pass
        collector.end_session()

        profile = collector.get_agent_profile("coding")
        assert profile["current_streak"] == 5
        assert profile["best_streak"] == 5

        # Session 3: failure breaks streak
        collector.start_session(session_num=3)
        with collector.track_agent("coding") as tracker:
            tracker.set_error("Error")
        collector.end_session()

        profile = collector.get_agent_profile("coding")
        assert profile["current_streak"] == 0
        assert profile["best_streak"] == 5  # Best preserved


class TestMetricsAccuracy:
    """Test accuracy of metrics calculations."""

    def test_token_counting_accuracy(self, tmp_path: Path):
        """Test that token counts are accurate."""
        collector = AgentMetricsCollector(tmp_path)

        collector.start_session(session_num=1)

        with collector.track_agent("coding") as tracker:
            tracker.set_tokens(input_tokens=1234, output_tokens=5678)

        collector.end_session()

        # Verify event
        event = collector.state["events"][0]
        assert event["input_tokens"] == 1234
        assert event["output_tokens"] == 5678
        assert event["total_tokens"] == 6912

        # Verify profile
        profile = collector.get_agent_profile("coding")
        assert profile["total_tokens"] == 6912

    def test_cost_calculation_accuracy(self, tmp_path: Path):
        """Test that cost calculations are accurate."""
        collector = AgentMetricsCollector(tmp_path)

        collector.start_session(session_num=1)

        with collector.track_agent("coding") as tracker:
            tracker.set_tokens(input_tokens=1000, output_tokens=500)

        collector.end_session()

        # Expected cost: (1000/1000 * 0.003) + (500/1000 * 0.015) = 0.0105
        event = collector.state["events"][0]
        assert abs(event["estimated_cost_usd"] - 0.0105) < 0.0001

    def test_duration_tracking_accuracy(self, tmp_path: Path):
        """Test that duration tracking is accurate."""
        collector = AgentMetricsCollector(tmp_path)

        collector.start_session(session_num=1)

        with collector.track_agent("coding"):
            time.sleep(0.2)  # Sleep for 200ms

        collector.end_session()

        event = collector.state["events"][0]
        # Duration should be at least 200ms
        assert event["duration_seconds"] >= 0.2
        # But not more than 300ms (accounting for overhead)
        assert event["duration_seconds"] < 0.3


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_session(self, tmp_path: Path):
        """Test a session with no agent invocations."""
        collector = AgentMetricsCollector(tmp_path)

        collector.start_session(session_num=1)
        summary = collector.end_session()

        assert summary["total_tokens"] == 0
        assert summary["total_cost_usd"] == 0.0
        assert len(summary["agents_invoked"]) == 0
        assert len(summary["tickets_worked"]) == 0

    def test_agent_with_no_tokens(self, tmp_path: Path):
        """Test agent invocation with zero tokens."""
        collector = AgentMetricsCollector(tmp_path)

        collector.start_session(session_num=1)

        with collector.track_agent("coding"):
            pass  # No tokens set

        collector.end_session()

        event = collector.state["events"][0]
        assert event["input_tokens"] == 0
        assert event["output_tokens"] == 0
        assert event["total_tokens"] == 0
        assert event["estimated_cost_usd"] == 0.0

    def test_agent_with_no_artifacts(self, tmp_path: Path):
        """Test agent invocation with no artifacts."""
        collector = AgentMetricsCollector(tmp_path)

        collector.start_session(session_num=1)

        with collector.track_agent("coding"):
            pass  # No artifacts added

        collector.end_session()

        event = collector.state["events"][0]
        assert event["artifacts"] == []

    def test_duplicate_agent_invocations_in_session(self, tmp_path: Path):
        """Test that duplicate agent names are handled correctly in session."""
        collector = AgentMetricsCollector(tmp_path)

        collector.start_session(session_num=1)

        # Same agent invoked multiple times
        with collector.track_agent("coding"):
            pass

        with collector.track_agent("coding"):
            pass

        with collector.track_agent("coding"):
            pass

        summary = collector.end_session()

        # Agent should appear only once in agents_invoked
        assert summary["agents_invoked"].count("coding") == 1

        # But profile should count all invocations
        profile = collector.get_agent_profile("coding")
        assert profile["total_invocations"] == 3

    def test_empty_ticket_key(self, tmp_path: Path):
        """Test agent invocation with empty ticket key."""
        collector = AgentMetricsCollector(tmp_path)

        collector.start_session(session_num=1)

        with collector.track_agent("coding", ticket_key=""):
            pass

        summary = collector.end_session()

        # Empty ticket key should not be in tickets_worked
        assert len(summary["tickets_worked"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
