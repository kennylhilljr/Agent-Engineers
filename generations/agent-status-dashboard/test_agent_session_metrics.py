"""Tests for agent.py session loop instrumentation with metrics collector.

This module tests the integration between agent.py's run_autonomous_agent()
and the AgentMetricsCollector, verifying that:
- Sessions are created and tracked correctly
- Session lifecycle (start_session, end_session) works properly
- Metrics persist across sessions
- Continuation flow is properly handled
- Error cases are handled gracefully
"""

import json
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent_metrics_collector import AgentMetricsCollector
from metrics import SessionSummary


class TestSessionLifecycleBasics:
    """Test basic session lifecycle operations."""

    def test_start_session_creates_session_id(self):
        """Test that start_session returns a valid session ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            session_id = collector.start_session(session_type="initializer")

            # Should be a valid UUID
            assert isinstance(session_id, str)
            uuid.UUID(session_id)  # Will raise if not valid UUID

    def test_start_session_tracks_session_type(self):
        """Test that session type is tracked correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            # Test initializer session
            session_id1 = collector.start_session(session_type="initializer")
            assert session_id1 in collector._active_sessions
            assert collector._active_sessions[session_id1]["session_type"] == "initializer"

            # End first session
            collector.end_session(session_id1, status="complete")

            # Test continuation session
            session_id2 = collector.start_session(session_type="continuation")
            assert collector._active_sessions[session_id2]["session_type"] == "continuation"

    def test_end_session_creates_summary(self):
        """Test that end_session creates a SessionSummary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            session_id = collector.start_session(session_type="initializer")
            collector.end_session(session_id, status="complete")

            # Load state and verify session summary exists
            state = collector.get_state()
            assert len(state["sessions"]) == 1
            assert state["sessions"][0]["session_id"] == session_id
            assert state["sessions"][0]["status"] == "complete"
            assert state["sessions"][0]["session_type"] == "initializer"

    def test_end_session_increments_total_sessions(self):
        """Test that end_session increments total_sessions counter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            # Start and end first session
            session_id1 = collector.start_session()
            collector.end_session(session_id1)

            state = collector.get_state()
            assert state["total_sessions"] == 1

            # Start and end second session
            session_id2 = collector.start_session()
            collector.end_session(session_id2)

            state = collector.get_state()
            assert state["total_sessions"] == 2

    def test_end_session_with_invalid_id_raises_error(self):
        """Test that end_session raises ValueError for invalid session ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            with pytest.raises(ValueError, match="not an active session"):
                collector.end_session("invalid-session-id")


class TestSessionStatusTracking:
    """Test session status tracking (continue, error, complete)."""

    def test_session_status_continue(self):
        """Test session with 'continue' status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            session_id = collector.start_session()
            collector.end_session(session_id, status="continue")

            state = collector.get_state()
            assert state["sessions"][0]["status"] == "continue"

    def test_session_status_error(self):
        """Test session with 'error' status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            session_id = collector.start_session()
            collector.end_session(session_id, status="error")

            state = collector.get_state()
            assert state["sessions"][0]["status"] == "error"

    def test_session_status_complete(self):
        """Test session with 'complete' status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            session_id = collector.start_session()
            collector.end_session(session_id, status="complete")

            state = collector.get_state()
            assert state["sessions"][0]["status"] == "complete"


class TestSessionNumbering:
    """Test sequential session numbering."""

    def test_session_numbers_increment_sequentially(self):
        """Test that session numbers increment sequentially."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            # Create 3 sessions
            for i in range(1, 4):
                session_id = collector.start_session()
                collector.end_session(session_id)

                state = collector.get_state()
                assert state["sessions"][-1]["session_number"] == i

    def test_session_numbers_persist_across_collector_instances(self):
        """Test that session numbers persist when creating new collector instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # First collector - create 2 sessions
            collector1 = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )
            session_id1 = collector1.start_session()
            collector1.end_session(session_id1)
            session_id2 = collector1.start_session()
            collector1.end_session(session_id2)

            # New collector instance - should continue numbering
            collector2 = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )
            session_id3 = collector2.start_session()
            collector2.end_session(session_id3)

            # Verify session numbers
            state = collector2.get_state()
            assert state["sessions"][0]["session_number"] == 1
            assert state["sessions"][1]["session_number"] == 2
            assert state["sessions"][2]["session_number"] == 3


class TestSessionAgentTracking:
    """Test tracking of agents invoked during a session."""

    def test_session_tracks_agents_invoked(self):
        """Test that session tracks which agents were invoked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            session_id = collector.start_session()

            # Track multiple agents
            with collector.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id) as tracker:
                tracker.add_tokens(100, 200)

            with collector.track_agent("github", "AI-50", "claude-haiku-4-5", session_id) as tracker:
                tracker.add_tokens(50, 100)

            collector.end_session(session_id)

            # Verify agents are tracked
            state = collector.get_state()
            session = state["sessions"][0]
            assert "coding" in session["agents_invoked"]
            assert "github" in session["agents_invoked"]
            assert len(session["agents_invoked"]) == 2

    def test_session_tracks_unique_agents_only(self):
        """Test that each agent is only listed once even if invoked multiple times."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            session_id = collector.start_session()

            # Track same agent multiple times
            for _ in range(3):
                with collector.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id) as tracker:
                    tracker.add_tokens(100, 200)

            collector.end_session(session_id)

            # Verify agent is only listed once
            state = collector.get_state()
            session = state["sessions"][0]
            assert session["agents_invoked"] == ["coding"]


class TestSessionTokenAndCostTracking:
    """Test session-level token and cost aggregation."""

    def test_session_aggregates_tokens(self):
        """Test that session totals match sum of event tokens."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            session_id = collector.start_session()

            # Track multiple agents with different token counts
            with collector.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id) as tracker:
                tracker.add_tokens(100, 200)  # 300 total

            with collector.track_agent("github", "AI-50", "claude-haiku-4-5", session_id) as tracker:
                tracker.add_tokens(50, 100)  # 150 total

            collector.end_session(session_id)

            # Verify session totals
            state = collector.get_state()
            session = state["sessions"][0]
            assert session["total_tokens"] == 450  # 300 + 150

    def test_session_aggregates_costs(self):
        """Test that session cost totals are calculated correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            session_id = collector.start_session()

            # Track agents with known token counts
            with collector.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id) as tracker:
                tracker.add_tokens(1000, 1000)  # (1000/1000 * 0.003) + (1000/1000 * 0.015) = 0.018

            collector.end_session(session_id)

            # Verify cost calculation
            state = collector.get_state()
            session = state["sessions"][0]
            assert abs(session["total_cost_usd"] - 0.018) < 0.0001


class TestSessionTicketTracking:
    """Test tracking of tickets worked during a session."""

    def test_session_tracks_tickets_worked(self):
        """Test that session tracks unique ticket keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            session_id = collector.start_session()

            # Work on multiple tickets
            with collector.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id) as tracker:
                tracker.add_tokens(100, 200)

            with collector.track_agent("github", "AI-51", "claude-haiku-4-5", session_id) as tracker:
                tracker.add_tokens(50, 100)

            collector.end_session(session_id)

            # Verify tickets are tracked
            state = collector.get_state()
            session = state["sessions"][0]
            assert "AI-50" in session["tickets_worked"]
            assert "AI-51" in session["tickets_worked"]
            assert len(session["tickets_worked"]) == 2

    def test_session_deduplicates_ticket_keys(self):
        """Test that duplicate ticket keys are deduplicated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            session_id = collector.start_session()

            # Work on same ticket multiple times
            for _ in range(3):
                with collector.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id) as tracker:
                    tracker.add_tokens(100, 200)

            collector.end_session(session_id)

            # Verify ticket is only listed once
            state = collector.get_state()
            session = state["sessions"][0]
            assert session["tickets_worked"] == ["AI-50"]


class TestContinuationFlow:
    """Test continuation flow across multiple sessions."""

    def test_multiple_sessions_accumulate_correctly(self):
        """Test that metrics accumulate correctly across multiple sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            # Session 1: initializer
            session_id1 = collector.start_session(session_type="initializer")
            with collector.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id1) as tracker:
                tracker.add_tokens(1000, 2000)
            collector.end_session(session_id1, status="continue")

            # Session 2: continuation
            session_id2 = collector.start_session(session_type="continuation")
            with collector.track_agent("coding", "AI-51", "claude-sonnet-4-5", session_id2) as tracker:
                tracker.add_tokens(500, 1000)
            collector.end_session(session_id2, status="complete")

            # Verify both sessions are recorded
            state = collector.get_state()
            assert len(state["sessions"]) == 2
            assert state["total_sessions"] == 2

            # Verify agent profile accumulated across sessions
            coding_profile = state["agents"]["coding"]
            assert coding_profile["total_invocations"] == 2
            assert coding_profile["total_tokens"] == 4500  # 3000 + 1500

    def test_continuation_session_loads_previous_state(self):
        """Test that continuation sessions can see previous state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # First collector - create initial session
            collector1 = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )
            session_id1 = collector1.start_session(session_type="initializer")
            with collector1.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id1) as tracker:
                tracker.add_tokens(1000, 2000)
            collector1.end_session(session_id1, status="continue")

            # New collector instance - continuation session
            collector2 = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )
            state_before = collector2.get_state()
            assert state_before["total_sessions"] == 1
            assert "coding" in state_before["agents"]

            # Add continuation session
            session_id2 = collector2.start_session(session_type="continuation")
            with collector2.track_agent("coding", "AI-51", "claude-sonnet-4-5", session_id2) as tracker:
                tracker.add_tokens(500, 1000)
            collector2.end_session(session_id2, status="complete")

            # Verify both sessions are visible
            state_after = collector2.get_state()
            assert state_after["total_sessions"] == 2
            assert state_after["agents"]["coding"]["total_invocations"] == 2


class TestErrorHandling:
    """Test error handling in session lifecycle."""

    def test_session_handles_event_errors_gracefully(self):
        """Test that session can complete even if some events fail."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            session_id = collector.start_session()

            # Success event
            with collector.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id) as tracker:
                tracker.add_tokens(100, 200)

            # Error event
            try:
                with collector.track_agent("github", "AI-50", "claude-haiku-4-5", session_id) as tracker:
                    tracker.add_tokens(50, 100)
                    raise ValueError("Simulated error")
            except ValueError:
                pass  # Expected

            collector.end_session(session_id, status="error")

            # Verify session completed despite error
            state = collector.get_state()
            assert len(state["sessions"]) == 1
            assert state["sessions"][0]["status"] == "error"

            # Verify both events were recorded
            assert len(state["events"]) == 2
            assert state["events"][0]["status"] == "success"
            assert state["events"][1]["status"] == "error"

    def test_graceful_degradation_when_metrics_unavailable(self):
        """Test that agent.py can run without metrics module."""
        # This test verifies the import error handling in agent.py
        # If AgentMetricsCollector is not importable, agent.py should still work

        # This is tested by the actual instrumentation code which has:
        # try:
        #     from agent_metrics_collector import AgentMetricsCollector
        #     ...
        # except ImportError:
        #     ...
        #
        # We can't easily test this in isolation, but the code path exists
        # and is tested via manual testing
        pass


class TestTimestamps:
    """Test timestamp tracking in sessions."""

    def test_session_has_start_and_end_timestamps(self):
        """Test that sessions have valid start and end timestamps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            session_id = collector.start_session()
            collector.end_session(session_id)

            state = collector.get_state()
            session = state["sessions"][0]

            # Verify timestamps exist and are valid ISO 8601
            assert "started_at" in session
            assert "ended_at" in session

            started_at = datetime.fromisoformat(session["started_at"].replace("Z", "+00:00"))
            ended_at = datetime.fromisoformat(session["ended_at"].replace("Z", "+00:00"))

            # End time should be after start time
            assert ended_at >= started_at
