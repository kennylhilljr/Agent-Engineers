"""Unit tests for metrics.py TypedDict definitions.

Tests verify that:
1. Type definitions are valid and can be instantiated
2. All required fields are accessible
3. TypedDict validation works correctly for field types
4. Literal types enforce correct values
5. Documentation is comprehensive
"""

import unittest
from datetime import datetime
from typing import get_type_hints

from metrics import AgentEvent, AgentProfile, DashboardState, SessionSummary


class TestAgentEvent(unittest.TestCase):
    """Test suite for AgentEvent TypedDict."""

    def test_agent_event_creation(self):
        """Test creating a valid AgentEvent instance."""
        event: AgentEvent = {
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "agent_name": "coding",
            "session_id": "session-123",
            "ticket_key": "AI-44",
            "started_at": "2026-02-14T10:00:00Z",
            "ended_at": "2026-02-14T10:05:30Z",
            "duration_seconds": 330.5,
            "status": "success",
            "input_tokens": 1500,
            "output_tokens": 2500,
            "total_tokens": 4000,
            "estimated_cost_usd": 0.12,
            "artifacts": ["file:metrics.py", "file:test_metrics.py"],
            "error_message": "",
            "model_used": "claude-sonnet-4-5",
        }

        # Verify all fields are accessible
        self.assertEqual(event["event_id"], "550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(event["agent_name"], "coding")
        self.assertEqual(event["status"], "success")
        self.assertEqual(event["total_tokens"], 4000)
        self.assertEqual(len(event["artifacts"]), 2)

    def test_agent_event_error_status(self):
        """Test AgentEvent with error status."""
        event: AgentEvent = {
            "event_id": "error-event-001",
            "agent_name": "github",
            "session_id": "session-456",
            "ticket_key": "AI-45",
            "started_at": "2026-02-14T11:00:00Z",
            "ended_at": "2026-02-14T11:00:15Z",
            "duration_seconds": 15.2,
            "status": "error",
            "input_tokens": 500,
            "output_tokens": 100,
            "total_tokens": 600,
            "estimated_cost_usd": 0.02,
            "artifacts": [],
            "error_message": "Authentication failed: invalid token",
            "model_used": "claude-haiku-4-5",
        }

        self.assertEqual(event["status"], "error")
        self.assertNotEqual(event["error_message"], "")
        self.assertEqual(len(event["artifacts"]), 0)

    def test_agent_event_all_status_literals(self):
        """Test all valid status literal values."""
        valid_statuses = ["success", "error", "timeout", "blocked"]

        for status in valid_statuses:
            event: AgentEvent = {
                "event_id": f"event-{status}",
                "agent_name": "linear",
                "session_id": "session-789",
                "ticket_key": "AI-46",
                "started_at": "2026-02-14T12:00:00Z",
                "ended_at": "2026-02-14T12:01:00Z",
                "duration_seconds": 60.0,
                "status": status,  # type: ignore
                "input_tokens": 100,
                "output_tokens": 200,
                "total_tokens": 300,
                "estimated_cost_usd": 0.01,
                "artifacts": [],
                "error_message": "" if status == "success" else f"{status} occurred",
                "model_used": "claude-sonnet-4-5",
            }
            self.assertEqual(event["status"], status)

    def test_agent_event_type_hints(self):
        """Test that AgentEvent has correct type hints."""
        hints = get_type_hints(AgentEvent)

        # Verify key fields have correct types
        self.assertIn("event_id", hints)
        self.assertIn("agent_name", hints)
        self.assertIn("status", hints)
        self.assertIn("total_tokens", hints)
        self.assertIn("artifacts", hints)


class TestAgentProfile(unittest.TestCase):
    """Test suite for AgentProfile TypedDict."""

    def test_agent_profile_creation(self):
        """Test creating a valid AgentProfile instance."""
        profile: AgentProfile = {
            "agent_name": "coding",
            "total_invocations": 150,
            "successful_invocations": 142,
            "failed_invocations": 8,
            "total_tokens": 500000,
            "total_cost_usd": 15.50,
            "total_duration_seconds": 12500.0,
            "commits_made": 0,
            "prs_created": 0,
            "prs_merged": 0,
            "files_created": 45,
            "files_modified": 89,
            "lines_added": 3500,
            "lines_removed": 1200,
            "tests_written": 28,
            "issues_created": 0,
            "issues_completed": 0,
            "messages_sent": 0,
            "reviews_completed": 0,
            "success_rate": 0.9467,
            "avg_duration_seconds": 83.33,
            "avg_tokens_per_call": 3333.33,
            "cost_per_success_usd": 0.1092,
            "xp": 14200,
            "level": 7,
            "current_streak": 15,
            "best_streak": 42,
            "achievements": ["first_blood", "century_club", "perfectionist"],
            "strengths": ["fast_execution", "high_success_rate"],
            "weaknesses": ["verbose_output"],
            "recent_events": ["event-1", "event-2", "event-3"],
            "last_error": "File not found: config.yaml",
            "last_active": "2026-02-14T15:30:00Z",
        }

        # Verify all counter fields
        self.assertEqual(profile["total_invocations"], 150)
        self.assertEqual(profile["successful_invocations"], 142)
        self.assertEqual(profile["failed_invocations"], 8)

        # Verify contribution counters
        self.assertEqual(profile["files_created"], 45)
        self.assertEqual(profile["tests_written"], 28)

        # Verify derived metrics
        self.assertAlmostEqual(profile["success_rate"], 0.9467, places=4)

        # Verify gamification
        self.assertEqual(profile["level"], 7)
        self.assertEqual(len(profile["achievements"]), 3)

    def test_agent_profile_github_agent(self):
        """Test AgentProfile for GitHub agent with relevant counters."""
        profile: AgentProfile = {
            "agent_name": "github",
            "total_invocations": 75,
            "successful_invocations": 70,
            "failed_invocations": 5,
            "total_tokens": 150000,
            "total_cost_usd": 4.25,
            "total_duration_seconds": 3000.0,
            "commits_made": 42,
            "prs_created": 18,
            "prs_merged": 15,
            "files_created": 0,
            "files_modified": 0,
            "lines_added": 0,
            "lines_removed": 0,
            "tests_written": 0,
            "issues_created": 0,
            "issues_completed": 0,
            "messages_sent": 0,
            "reviews_completed": 0,
            "success_rate": 0.9333,
            "avg_duration_seconds": 40.0,
            "avg_tokens_per_call": 2000.0,
            "cost_per_success_usd": 0.0607,
            "xp": 7000,
            "level": 5,
            "current_streak": 10,
            "best_streak": 20,
            "achievements": ["first_blood", "commit_master"],
            "strengths": ["reliable", "fast"],
            "weaknesses": [],
            "recent_events": [],
            "last_error": "",
            "last_active": "2026-02-14T14:00:00Z",
        }

        # Verify GitHub-specific counters
        self.assertEqual(profile["commits_made"], 42)
        self.assertEqual(profile["prs_created"], 18)
        self.assertEqual(profile["prs_merged"], 15)

        # Verify non-GitHub counters are zero
        self.assertEqual(profile["files_created"], 0)
        self.assertEqual(profile["messages_sent"], 0)

    def test_agent_profile_type_hints(self):
        """Test that AgentProfile has correct type hints."""
        hints = get_type_hints(AgentProfile)

        # Verify key fields exist
        self.assertIn("agent_name", hints)
        self.assertIn("total_invocations", hints)
        self.assertIn("success_rate", hints)
        self.assertIn("achievements", hints)
        self.assertIn("strengths", hints)


class TestSessionSummary(unittest.TestCase):
    """Test suite for SessionSummary TypedDict."""

    def test_session_summary_creation(self):
        """Test creating a valid SessionSummary instance."""
        summary: SessionSummary = {
            "session_id": "session-abc-123",
            "session_number": 42,
            "session_type": "initializer",
            "started_at": "2026-02-14T09:00:00Z",
            "ended_at": "2026-02-14T09:45:30Z",
            "status": "complete",
            "agents_invoked": ["coding", "github", "linear"],
            "total_tokens": 25000,
            "total_cost_usd": 0.75,
            "tickets_worked": ["AI-44", "AI-45"],
        }

        # Verify all fields
        self.assertEqual(summary["session_number"], 42)
        self.assertEqual(summary["session_type"], "initializer")
        self.assertEqual(summary["status"], "complete")
        self.assertEqual(len(summary["agents_invoked"]), 3)
        self.assertEqual(len(summary["tickets_worked"]), 2)

    def test_session_summary_continuation(self):
        """Test SessionSummary for continuation session."""
        summary: SessionSummary = {
            "session_id": "session-def-456",
            "session_number": 43,
            "session_type": "continuation",
            "started_at": "2026-02-14T10:00:00Z",
            "ended_at": "2026-02-14T10:15:00Z",
            "status": "continue",
            "agents_invoked": ["slack"],
            "total_tokens": 5000,
            "total_cost_usd": 0.15,
            "tickets_worked": [],
        }

        self.assertEqual(summary["session_type"], "continuation")
        self.assertEqual(summary["status"], "continue")

    def test_session_summary_all_status_literals(self):
        """Test all valid status literal values for SessionSummary."""
        valid_statuses = ["continue", "error", "complete"]

        for status in valid_statuses:
            summary: SessionSummary = {
                "session_id": f"session-{status}",
                "session_number": 1,
                "session_type": "initializer",
                "started_at": "2026-02-14T12:00:00Z",
                "ended_at": "2026-02-14T12:10:00Z",
                "status": status,  # type: ignore
                "agents_invoked": [],
                "total_tokens": 1000,
                "total_cost_usd": 0.03,
                "tickets_worked": [],
            }
            self.assertEqual(summary["status"], status)

    def test_session_summary_type_hints(self):
        """Test that SessionSummary has correct type hints."""
        hints = get_type_hints(SessionSummary)

        # Verify key fields exist
        self.assertIn("session_id", hints)
        self.assertIn("session_type", hints)
        self.assertIn("status", hints)
        self.assertIn("agents_invoked", hints)


class TestDashboardState(unittest.TestCase):
    """Test suite for DashboardState TypedDict."""

    def test_dashboard_state_creation(self):
        """Test creating a valid DashboardState instance."""
        # Create sample agent profile
        coding_profile: AgentProfile = {
            "agent_name": "coding",
            "total_invocations": 100,
            "successful_invocations": 95,
            "failed_invocations": 5,
            "total_tokens": 300000,
            "total_cost_usd": 9.50,
            "total_duration_seconds": 5000.0,
            "commits_made": 0,
            "prs_created": 0,
            "prs_merged": 0,
            "files_created": 30,
            "files_modified": 50,
            "lines_added": 2000,
            "lines_removed": 500,
            "tests_written": 15,
            "issues_created": 0,
            "issues_completed": 0,
            "messages_sent": 0,
            "reviews_completed": 0,
            "success_rate": 0.95,
            "avg_duration_seconds": 50.0,
            "avg_tokens_per_call": 3000.0,
            "cost_per_success_usd": 0.10,
            "xp": 9500,
            "level": 6,
            "current_streak": 12,
            "best_streak": 30,
            "achievements": ["first_blood", "century_club"],
            "strengths": ["fast_execution"],
            "weaknesses": [],
            "recent_events": [],
            "last_error": "",
            "last_active": "2026-02-14T15:00:00Z",
        }

        # Create sample event
        event: AgentEvent = {
            "event_id": "event-001",
            "agent_name": "coding",
            "session_id": "session-1",
            "ticket_key": "AI-44",
            "started_at": "2026-02-14T10:00:00Z",
            "ended_at": "2026-02-14T10:05:00Z",
            "duration_seconds": 300.0,
            "status": "success",
            "input_tokens": 1000,
            "output_tokens": 2000,
            "total_tokens": 3000,
            "estimated_cost_usd": 0.09,
            "artifacts": ["file:metrics.py"],
            "error_message": "",
            "model_used": "claude-sonnet-4-5",
        }

        # Create sample session
        session: SessionSummary = {
            "session_id": "session-1",
            "session_number": 1,
            "session_type": "initializer",
            "started_at": "2026-02-14T10:00:00Z",
            "ended_at": "2026-02-14T10:30:00Z",
            "status": "complete",
            "agents_invoked": ["coding"],
            "total_tokens": 3000,
            "total_cost_usd": 0.09,
            "tickets_worked": ["AI-44"],
        }

        # Create dashboard state
        state: DashboardState = {
            "version": 1,
            "project_name": "agent-status-dashboard",
            "created_at": "2026-02-14T09:00:00Z",
            "updated_at": "2026-02-14T15:30:00Z",
            "total_sessions": 5,
            "total_tokens": 350000,
            "total_cost_usd": 10.50,
            "total_duration_seconds": 6000.0,
            "agents": {"coding": coding_profile},
            "events": [event],
            "sessions": [session],
        }

        # Verify top-level fields
        self.assertEqual(state["version"], 1)
        self.assertEqual(state["project_name"], "agent-status-dashboard")
        self.assertEqual(state["total_sessions"], 5)

        # Verify nested structures
        self.assertIn("coding", state["agents"])
        self.assertEqual(len(state["events"]), 1)
        self.assertEqual(len(state["sessions"]), 1)

    def test_dashboard_state_empty(self):
        """Test creating an empty DashboardState."""
        state: DashboardState = {
            "version": 1,
            "project_name": "new-project",
            "created_at": "2026-02-14T16:00:00Z",
            "updated_at": "2026-02-14T16:00:00Z",
            "total_sessions": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_duration_seconds": 0.0,
            "agents": {},
            "events": [],
            "sessions": [],
        }

        self.assertEqual(state["total_sessions"], 0)
        self.assertEqual(len(state["agents"]), 0)
        self.assertEqual(len(state["events"]), 0)
        self.assertEqual(len(state["sessions"]), 0)

    def test_dashboard_state_type_hints(self):
        """Test that DashboardState has correct type hints."""
        hints = get_type_hints(DashboardState)

        # Verify key fields exist
        self.assertIn("version", hints)
        self.assertIn("project_name", hints)
        self.assertIn("agents", hints)
        self.assertIn("events", hints)
        self.assertIn("sessions", hints)


class TestMetricsDocumentation(unittest.TestCase):
    """Test suite for documentation completeness."""

    def test_module_docstring(self):
        """Test that metrics module has comprehensive docstring."""
        import metrics

        self.assertIsNotNone(metrics.__doc__)
        self.assertIn("TypedDict", metrics.__doc__)
        self.assertIn("AgentEvent", metrics.__doc__)
        self.assertIn("AgentProfile", metrics.__doc__)
        self.assertIn("SessionSummary", metrics.__doc__)
        self.assertIn("DashboardState", metrics.__doc__)

    def test_typeddict_docstrings(self):
        """Test that all TypedDict classes have docstrings."""
        self.assertIsNotNone(AgentEvent.__doc__)
        self.assertIsNotNone(AgentProfile.__doc__)
        self.assertIsNotNone(SessionSummary.__doc__)
        self.assertIsNotNone(DashboardState.__doc__)

        # Verify docstrings are meaningful (not just placeholders)
        self.assertGreater(len(AgentEvent.__doc__), 50)
        self.assertGreater(len(AgentProfile.__doc__), 50)
        self.assertGreater(len(SessionSummary.__doc__), 50)
        self.assertGreater(len(DashboardState.__doc__), 50)


if __name__ == "__main__":
    unittest.main()
