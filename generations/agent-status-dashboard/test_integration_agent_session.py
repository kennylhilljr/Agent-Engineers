"""Integration tests for agent.py session metrics instrumentation.

These tests simulate realistic agent workflow scenarios including:
- Full session lifecycle (initializer + multiple continuations)
- Multi-agent delegation patterns
- Error recovery across sessions
- Persistence across process restarts
- Real-world token and cost accumulation
"""

import json
import tempfile
import time
from datetime import datetime
from pathlib import Path

import pytest

from agent_metrics_collector import AgentMetricsCollector


class TestFullSessionWorkflow:
    """Test complete session workflows from start to finish."""

    def test_initializer_session_workflow(self):
        """Test a complete initializer session with multiple agent delegations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            # Simulate initializer session
            session_id = collector.start_session(session_type="initializer")

            # Simulate orchestrator delegating to multiple agents
            # 1. Linear agent creates issues
            with collector.track_agent("linear", "AI-50", "claude-haiku-4-5", session_id) as tracker:
                tracker.add_tokens(500, 300)
                tracker.add_artifact("issue:created:AI-50")

            # 2. Coding agent implements features
            with collector.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id) as tracker:
                tracker.add_tokens(2000, 3000)
                tracker.add_artifact("file:created:agent_metrics.py")
                tracker.add_artifact("file:created:test_metrics.py")

            # 3. GitHub agent commits and creates PR
            with collector.track_agent("github", "AI-50", "claude-haiku-4-5", session_id) as tracker:
                tracker.add_tokens(300, 200)
                tracker.add_artifact("commit:abc123")
                tracker.add_artifact("pr:created:#50")

            # 4. Slack agent sends notification
            with collector.track_agent("slack", "AI-50", "claude-haiku-4-5", session_id) as tracker:
                tracker.add_tokens(200, 150)
                tracker.add_artifact("message:channel:engineering")

            # End session
            collector.end_session(session_id, status="continue")

            # Verify session summary
            state = collector.get_state()
            session = state["sessions"][0]

            assert session["session_type"] == "initializer"
            assert session["status"] == "continue"
            assert len(session["agents_invoked"]) == 4
            assert "linear" in session["agents_invoked"]
            assert "coding" in session["agents_invoked"]
            assert "github" in session["agents_invoked"]
            assert "slack" in session["agents_invoked"]

            # Verify token totals
            expected_tokens = (500+300) + (2000+3000) + (300+200) + (200+150)
            assert session["total_tokens"] == expected_tokens

            # Verify all 4 events were recorded
            assert len(state["events"]) == 4

    def test_continuation_session_workflow(self):
        """Test a continuation session building on previous state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            # Initial session
            session_id1 = collector.start_session(session_type="initializer")
            with collector.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id1) as tracker:
                tracker.add_tokens(1000, 2000)
            collector.end_session(session_id1, status="continue")

            # Continuation session
            session_id2 = collector.start_session(session_type="continuation")
            with collector.track_agent("coding", "AI-51", "claude-sonnet-4-5", session_id2) as tracker:
                tracker.add_tokens(800, 1200)
            collector.end_session(session_id2, status="continue")

            # Another continuation
            session_id3 = collector.start_session(session_type="continuation")
            with collector.track_agent("coding", "AI-52", "claude-sonnet-4-5", session_id3) as tracker:
                tracker.add_tokens(600, 900)
            collector.end_session(session_id3, status="complete")

            # Verify all sessions recorded
            state = collector.get_state()
            assert len(state["sessions"]) == 3
            assert state["sessions"][0]["session_type"] == "initializer"
            assert state["sessions"][1]["session_type"] == "continuation"
            assert state["sessions"][2]["session_type"] == "continuation"

            # Verify final session has "complete" status
            assert state["sessions"][2]["status"] == "complete"


class TestMultiAgentDelegation:
    """Test realistic multi-agent delegation patterns."""

    def test_orchestrator_delegation_pattern(self):
        """Test pattern where orchestrator delegates to multiple specialized agents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            session_id = collector.start_session()

            # Orchestrator pattern: linear -> coding -> github -> slack
            agents = [
                ("linear", "AI-50", 500, 300, ["issue:created:AI-50"]),
                ("coding", "AI-50", 2000, 3000, ["file:created:impl.py", "file:created:test.py"]),
                ("github", "AI-50", 300, 200, ["commit:xyz", "pr:created:#50"]),
                ("slack", "AI-50", 200, 150, ["message:channel:eng"]),
            ]

            for agent_name, ticket, input_tok, output_tok, artifacts in agents:
                with collector.track_agent(agent_name, ticket, "claude-sonnet-4-5", session_id) as tracker:
                    tracker.add_tokens(input_tok, output_tok)
                    for artifact in artifacts:
                        tracker.add_artifact(artifact)

            collector.end_session(session_id, status="complete")

            # Verify each agent has profile
            state = collector.get_state()
            assert len(state["agents"]) == 4

            # Verify linear agent created issue
            linear_profile = state["agents"]["linear"]
            assert linear_profile["issues_created"] == 1

            # Verify coding agent created files
            coding_profile = state["agents"]["coding"]
            assert coding_profile["files_created"] == 2

            # Verify github agent made commit and PR
            github_profile = state["agents"]["github"]
            assert github_profile["commits_made"] == 1
            assert github_profile["prs_created"] == 1

            # Verify slack agent sent message
            slack_profile = state["agents"]["slack"]
            assert slack_profile["messages_sent"] == 1

    def test_parallel_agent_invocations_in_session(self):
        """Test multiple agents working on different tickets in parallel."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            session_id = collector.start_session()

            # Simulate parallel work on different tickets
            tickets = [
                ("coding", "AI-50"),
                ("coding", "AI-51"),
                ("coding", "AI-52"),
                ("github", "AI-50"),
                ("github", "AI-51"),
            ]

            for agent_name, ticket in tickets:
                with collector.track_agent(agent_name, ticket, "claude-sonnet-4-5", session_id) as tracker:
                    tracker.add_tokens(500, 1000)

            collector.end_session(session_id)

            # Verify session tracked all unique tickets
            state = collector.get_state()
            session = state["sessions"][0]
            assert len(session["tickets_worked"]) == 3
            assert "AI-50" in session["tickets_worked"]
            assert "AI-51" in session["tickets_worked"]
            assert "AI-52" in session["tickets_worked"]


class TestErrorRecoveryScenarios:
    """Test error handling and recovery across sessions."""

    def test_session_with_partial_failures(self):
        """Test session where some agents succeed and some fail."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            session_id = collector.start_session()

            # Success
            with collector.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id) as tracker:
                tracker.add_tokens(1000, 2000)

            # Failure
            try:
                with collector.track_agent("linear", "AI-50", "claude-haiku-4-5", session_id) as tracker:
                    tracker.add_tokens(500, 300)
                    raise RuntimeError("API timeout")
            except RuntimeError:
                pass

            # Success
            with collector.track_agent("github", "AI-50", "claude-haiku-4-5", session_id) as tracker:
                tracker.add_tokens(300, 200)

            collector.end_session(session_id, status="error")

            # Verify all events recorded
            state = collector.get_state()
            assert len(state["events"]) == 3
            assert state["events"][0]["status"] == "success"
            assert state["events"][1]["status"] == "error"
            assert state["events"][2]["status"] == "success"

            # Verify agent profiles updated correctly
            assert state["agents"]["coding"]["successful_invocations"] == 1
            assert state["agents"]["linear"]["failed_invocations"] == 1
            assert state["agents"]["github"]["successful_invocations"] == 1

    def test_retry_after_error_session(self):
        """Test that agent can retry after error session."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            # First attempt - error
            session_id1 = collector.start_session()
            try:
                with collector.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id1) as tracker:
                    tracker.add_tokens(500, 1000)
                    raise RuntimeError("Build failed")
            except RuntimeError:
                pass
            collector.end_session(session_id1, status="error")

            # Retry - success
            session_id2 = collector.start_session(session_type="continuation")
            with collector.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id2) as tracker:
                tracker.add_tokens(500, 1000)
            collector.end_session(session_id2, status="continue")

            # Verify both sessions recorded
            state = collector.get_state()
            assert len(state["sessions"]) == 2
            assert state["sessions"][0]["status"] == "error"
            assert state["sessions"][1]["status"] == "continue"

            # Verify coding agent has both failure and success
            coding_profile = state["agents"]["coding"]
            assert coding_profile["failed_invocations"] == 1
            assert coding_profile["successful_invocations"] == 1
            assert coding_profile["total_invocations"] == 2


class TestPersistenceAcrossRestarts:
    """Test that metrics persist correctly across collector restarts."""

    def test_state_persists_between_collector_instances(self):
        """Test that creating new collector loads previous state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # First instance - create initial data
            collector1 = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            session_id = collector1.start_session()
            with collector1.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id) as tracker:
                tracker.add_tokens(1000, 2000)
            collector1.end_session(session_id)

            # Second instance - should load previous data
            collector2 = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            state = collector2.get_state()
            assert state["total_sessions"] == 1
            assert "coding" in state["agents"]
            assert state["agents"]["coding"]["total_tokens"] == 3000

    def test_continuation_session_sees_previous_sessions(self):
        """Test that continuation session can access data from previous sessions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # First collector - initializer session
            collector1 = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )
            session_id1 = collector1.start_session(session_type="initializer")
            with collector1.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id1) as tracker:
                tracker.add_tokens(1000, 2000)
                tracker.add_artifact("file:created:impl.py")
            collector1.end_session(session_id1, status="continue")

            # New collector - continuation session
            collector2 = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            # Can see previous session
            state_before = collector2.get_state()
            assert state_before["total_sessions"] == 1
            assert state_before["agents"]["coding"]["files_created"] == 1

            # Add continuation
            session_id2 = collector2.start_session(session_type="continuation")
            with collector2.track_agent("coding", "AI-51", "claude-sonnet-4-5", session_id2) as tracker:
                tracker.add_tokens(800, 1200)
                tracker.add_artifact("file:created:test.py")
            collector2.end_session(session_id2, status="complete")

            # Verify accumulation
            state_after = collector2.get_state()
            assert state_after["total_sessions"] == 2
            assert state_after["agents"]["coding"]["files_created"] == 2
            assert state_after["agents"]["coding"]["total_invocations"] == 2

    def test_metrics_file_structure(self):
        """Test that .agent_metrics.json has correct structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=tmpdir_path
            )

            session_id = collector.start_session()
            with collector.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id) as tracker:
                tracker.add_tokens(1000, 2000)
            collector.end_session(session_id)

            # Verify file exists
            metrics_file = tmpdir_path / ".agent_metrics.json"
            assert metrics_file.exists()

            # Verify JSON structure
            with open(metrics_file) as f:
                data = json.load(f)

            assert data["version"] == 1
            assert data["project_name"] == "test-project"
            assert "created_at" in data
            assert "updated_at" in data
            assert "agents" in data
            assert "events" in data
            assert "sessions" in data


class TestRealisticTokenCosts:
    """Test realistic token usage and cost calculations."""

    def test_session_calculates_realistic_costs(self):
        """Test that costs are calculated correctly for different models."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            session_id = collector.start_session()

            # Sonnet for heavy coding
            with collector.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id) as tracker:
                tracker.add_tokens(5000, 10000)
                # Cost: (5000/1000 * 0.003) + (10000/1000 * 0.015) = 0.015 + 0.15 = 0.165

            # Haiku for quick tasks
            with collector.track_agent("github", "AI-50", "claude-haiku-4-5", session_id) as tracker:
                tracker.add_tokens(1000, 500)
                # Cost: (1000/1000 * 0.0008) + (500/1000 * 0.004) = 0.0008 + 0.002 = 0.0028

            collector.end_session(session_id)

            # Verify costs
            state = collector.get_state()
            session = state["sessions"][0]

            # Total cost should be sum of both
            expected_cost = 0.165 + 0.0028
            assert abs(session["total_cost_usd"] - expected_cost) < 0.0001

    def test_high_token_usage_session(self):
        """Test session with realistic high token usage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            session_id = collector.start_session()

            # Simulate large codebase work
            with collector.track_agent("coding", "AI-50", "claude-sonnet-4-5", session_id) as tracker:
                tracker.add_tokens(50000, 30000)  # Large context + substantial output

            collector.end_session(session_id)

            state = collector.get_state()
            session = state["sessions"][0]

            assert session["total_tokens"] == 80000
            # Cost: (50000/1000 * 0.003) + (30000/1000 * 0.015) = 0.15 + 0.45 = 0.60
            assert abs(session["total_cost_usd"] - 0.60) < 0.01


class TestCompleteProjectLifecycle:
    """Test complete project lifecycle from initialization to completion."""

    def test_full_project_lifecycle(self):
        """Test complete project from start to PROJECT_COMPLETE."""
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=Path(tmpdir)
            )

            # Session 1: Initializer - create Linear issues
            session_id1 = collector.start_session(session_type="initializer")
            with collector.track_agent("linear", "SETUP", "claude-haiku-4-5", session_id1) as tracker:
                tracker.add_tokens(2000, 1000)
                for i in range(50, 56):
                    tracker.add_artifact(f"issue:created:AI-{i}")
            collector.end_session(session_id1, status="continue")

            # Session 2-6: Continuation - implement features
            for i in range(50, 56):
                session_id = collector.start_session(session_type="continuation")

                # Coding work
                with collector.track_agent("coding", f"AI-{i}", "claude-sonnet-4-5", session_id) as tracker:
                    tracker.add_tokens(3000, 5000)
                    tracker.add_artifact(f"file:created:feature_{i}.py")
                    tracker.add_artifact(f"file:created:test_{i}.py")

                # GitHub work
                with collector.track_agent("github", f"AI-{i}", "claude-haiku-4-5", session_id) as tracker:
                    tracker.add_tokens(500, 300)
                    tracker.add_artifact(f"commit:{i}")
                    tracker.add_artifact(f"pr:created:#{i}")

                # Linear update
                with collector.track_agent("linear", f"AI-{i}", "claude-haiku-4-5", session_id) as tracker:
                    tracker.add_tokens(200, 100)
                    tracker.add_artifact(f"issue:completed:AI-{i}")

                collector.end_session(session_id, status="continue")

            # Session 7: Final session - PROJECT_COMPLETE
            session_id7 = collector.start_session(session_type="continuation")
            with collector.track_agent("slack", "DONE", "claude-haiku-4-5", session_id7) as tracker:
                tracker.add_tokens(300, 200)
                tracker.add_artifact("message:channel:engineering:Project complete!")
            collector.end_session(session_id7, status="complete")

            # Verify final state
            state = collector.get_state()

            # Should have 8 sessions total (1 initializer + 6 feature + 1 final)
            assert state["total_sessions"] == 8

            # Verify all agents have activity
            assert "linear" in state["agents"]
            assert "coding" in state["agents"]
            assert "github" in state["agents"]
            assert "slack" in state["agents"]

            # Verify coding agent stats
            coding = state["agents"]["coding"]
            assert coding["total_invocations"] == 6  # One per feature
            assert coding["files_created"] == 12  # 2 files per feature

            # Verify github agent stats
            github = state["agents"]["github"]
            assert github["commits_made"] == 6
            assert github["prs_created"] == 6

            # Verify linear agent stats
            linear = state["agents"]["linear"]
            assert linear["issues_created"] == 6
            assert linear["issues_completed"] == 6

            # Verify final session is marked complete
            assert state["sessions"][-1]["status"] == "complete"
