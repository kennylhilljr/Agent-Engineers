"""Comprehensive tests for strengths and weaknesses detection.

Tests cover:
- Rolling window calculations with various window sizes
- All strength/weakness conditions
- Edge cases: empty data, single agent, equal agents, outliers
- Percentile calculations across multiple agents
- Integration scenarios with realistic data
"""

import unittest
from datetime import datetime, timedelta
from metrics import AgentEvent, AgentProfile, DashboardState
from strengths_weaknesses import (
    calculate_rolling_window_stats,
    calculate_agent_percentiles,
    detect_strengths,
    detect_weaknesses,
    update_agent_strengths_weaknesses,
    get_strength_description,
    get_weakness_description,
)


def create_test_event(
    agent_name: str,
    status: str = "success",
    duration_seconds: float = 60.0,
    cost_usd: float = 0.01,
    tokens: int = 1000,
    artifacts: list = None,
) -> AgentEvent:
    """Helper to create test events."""
    now = datetime.utcnow()
    return {
        "event_id": f"test-event-{now.timestamp()}",
        "agent_name": agent_name,
        "session_id": "test-session",
        "ticket_key": "AI-48",
        "started_at": now.isoformat() + "Z",
        "ended_at": (now + timedelta(seconds=duration_seconds)).isoformat() + "Z",
        "duration_seconds": duration_seconds,
        "status": status,
        "input_tokens": tokens // 2,
        "output_tokens": tokens // 2,
        "total_tokens": tokens,
        "estimated_cost_usd": cost_usd,
        "artifacts": artifacts or [],
        "error_message": "" if status == "success" else "Test error",
        "model_used": "claude-sonnet-4-5",
    }


def create_test_profile(agent_name: str) -> AgentProfile:
    """Helper to create test agent profiles."""
    return {
        "agent_name": agent_name,
        "total_invocations": 0,
        "successful_invocations": 0,
        "failed_invocations": 0,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "total_duration_seconds": 0.0,
        "commits_made": 0,
        "prs_created": 0,
        "prs_merged": 0,
        "files_created": 0,
        "files_modified": 0,
        "lines_added": 0,
        "lines_removed": 0,
        "tests_written": 0,
        "issues_created": 0,
        "issues_completed": 0,
        "messages_sent": 0,
        "reviews_completed": 0,
        "success_rate": 0.0,
        "avg_duration_seconds": 0.0,
        "avg_tokens_per_call": 0.0,
        "cost_per_success_usd": 0.0,
        "xp": 0,
        "level": 1,
        "current_streak": 0,
        "best_streak": 0,
        "achievements": [],
        "strengths": [],
        "weaknesses": [],
        "recent_events": [],
        "last_error": "",
        "last_active": datetime.utcnow().isoformat() + "Z",
    }


def create_test_state(agents: list = None, events: list = None) -> DashboardState:
    """Helper to create test dashboard state."""
    now = datetime.utcnow().isoformat() + "Z"
    agent_dict = {}
    if agents:
        for agent_name in agents:
            agent_dict[agent_name] = create_test_profile(agent_name)

    return {
        "version": 1,
        "project_name": "test-project",
        "created_at": now,
        "updated_at": now,
        "total_sessions": 0,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "total_duration_seconds": 0.0,
        "agents": agent_dict,
        "events": events or [],
        "sessions": [],
    }


class TestRollingWindowStats(unittest.TestCase):
    """Test suite for rolling window statistics calculation."""

    def test_empty_events_list(self):
        """Test with no events."""
        stats = calculate_rolling_window_stats([], "coding", window_size=20)
        self.assertEqual(stats["event_count"], 0)
        self.assertEqual(stats["success_rate"], 0.0)
        self.assertEqual(stats["avg_duration"], 0.0)
        self.assertEqual(stats["avg_cost"], 0.0)
        self.assertEqual(stats["artifact_count"], 0)

    def test_single_event(self):
        """Test with single event."""
        events = [create_test_event("coding", duration_seconds=30.0, cost_usd=0.02)]
        stats = calculate_rolling_window_stats(events, "coding", window_size=20)

        self.assertEqual(stats["event_count"], 1)
        self.assertEqual(stats["success_rate"], 1.0)
        self.assertEqual(stats["avg_duration"], 30.0)
        self.assertEqual(stats["avg_cost"], 0.02)
        self.assertEqual(stats["duration_variance"], 0.0)

    def test_multiple_events_within_window(self):
        """Test with multiple events all within window."""
        events = [
            create_test_event("coding", duration_seconds=30.0, cost_usd=0.01),
            create_test_event("coding", duration_seconds=60.0, cost_usd=0.02),
            create_test_event("coding", duration_seconds=45.0, cost_usd=0.015),
        ]
        stats = calculate_rolling_window_stats(events, "coding", window_size=20)

        self.assertEqual(stats["event_count"], 3)
        self.assertEqual(stats["success_rate"], 1.0)
        self.assertAlmostEqual(stats["avg_duration"], 45.0, places=2)
        self.assertAlmostEqual(stats["avg_cost"], 0.015, places=3)

    def test_window_size_limits_events(self):
        """Test that window size properly limits events."""
        # Create 30 events
        events = [create_test_event("coding", duration_seconds=i) for i in range(30)]
        stats = calculate_rolling_window_stats(events, "coding", window_size=10)

        # Should only analyze last 10 events
        self.assertEqual(stats["event_count"], 10)

    def test_filters_by_agent_name(self):
        """Test that only events for specified agent are included."""
        events = [
            create_test_event("coding", duration_seconds=30.0),
            create_test_event("github", duration_seconds=60.0),
            create_test_event("coding", duration_seconds=45.0),
        ]
        stats = calculate_rolling_window_stats(events, "coding", window_size=20)

        # Should only count 2 coding events
        self.assertEqual(stats["event_count"], 2)
        self.assertAlmostEqual(stats["avg_duration"], 37.5, places=2)

    def test_success_rate_calculation(self):
        """Test success rate with mixed success/failure."""
        events = [
            create_test_event("coding", status="success"),
            create_test_event("coding", status="error"),
            create_test_event("coding", status="success"),
            create_test_event("coding", status="success"),
        ]
        stats = calculate_rolling_window_stats(events, "coding", window_size=20)

        self.assertEqual(stats["success_rate"], 0.75)

    def test_variance_calculation(self):
        """Test duration variance calculation."""
        # Events with durations: 10, 20, 30, 40, 50 (mean = 30, variance = 200)
        events = [
            create_test_event("coding", duration_seconds=10.0),
            create_test_event("coding", duration_seconds=20.0),
            create_test_event("coding", duration_seconds=30.0),
            create_test_event("coding", duration_seconds=40.0),
            create_test_event("coding", duration_seconds=50.0),
        ]
        stats = calculate_rolling_window_stats(events, "coding", window_size=20)

        self.assertAlmostEqual(stats["avg_duration"], 30.0, places=2)
        self.assertAlmostEqual(stats["duration_variance"], 200.0, places=2)

    def test_artifact_counting(self):
        """Test artifact counting."""
        events = [
            create_test_event("coding", artifacts=["file:a.py", "file:b.py"]),
            create_test_event("coding", artifacts=["commit:abc123"]),
            create_test_event("coding", artifacts=[]),
        ]
        stats = calculate_rolling_window_stats(events, "coding", window_size=20)

        self.assertEqual(stats["artifact_count"], 3)

    def test_token_averaging(self):
        """Test token averaging."""
        events = [
            create_test_event("coding", tokens=1000),
            create_test_event("coding", tokens=2000),
            create_test_event("coding", tokens=3000),
        ]
        stats = calculate_rolling_window_stats(events, "coding", window_size=20)

        self.assertAlmostEqual(stats["avg_tokens"], 2000.0, places=2)


class TestAgentPercentiles(unittest.TestCase):
    """Test suite for agent percentile calculations."""

    def test_empty_state(self):
        """Test with no agents."""
        state = create_test_state()
        percentiles = calculate_agent_percentiles(state)
        self.assertEqual(percentiles, {})

    def test_single_agent(self):
        """Test with single agent."""
        events = [create_test_event("coding", duration_seconds=30.0)]
        state = create_test_state(agents=["coding"], events=events)
        percentiles = calculate_agent_percentiles(state)

        # Single agent should be at 0.5 percentile for all metrics
        self.assertEqual(percentiles["coding"]["duration_percentile"], 0.5)
        self.assertEqual(percentiles["coding"]["cost_percentile"], 0.5)
        self.assertEqual(percentiles["coding"]["success_percentile"], 0.5)
        self.assertEqual(percentiles["coding"]["consistency_percentile"], 0.5)

    def test_two_agents_different_speeds(self):
        """Test percentiles with two agents of different speeds."""
        events = [
            create_test_event("fast_agent", duration_seconds=10.0),
            create_test_event("slow_agent", duration_seconds=100.0),
        ]
        state = create_test_state(agents=["fast_agent", "slow_agent"], events=events)
        percentiles = calculate_agent_percentiles(state)

        # Fast agent should be at 100th percentile (1.0), slow at 0th (0.0)
        self.assertEqual(percentiles["fast_agent"]["duration_percentile"], 1.0)
        self.assertEqual(percentiles["slow_agent"]["duration_percentile"], 0.0)

    def test_three_agents_cost_ranking(self):
        """Test cost percentiles with three agents."""
        events = [
            create_test_event("cheap", cost_usd=0.001),
            create_test_event("medium", cost_usd=0.01),
            create_test_event("expensive", cost_usd=0.1),
        ]
        state = create_test_state(agents=["cheap", "medium", "expensive"], events=events)
        percentiles = calculate_agent_percentiles(state)

        # Cheap should be 100th percentile, expensive 0th, medium 50th
        self.assertEqual(percentiles["cheap"]["cost_percentile"], 1.0)
        self.assertEqual(percentiles["expensive"]["cost_percentile"], 0.0)
        self.assertEqual(percentiles["medium"]["cost_percentile"], 0.5)

    def test_success_rate_percentiles(self):
        """Test success rate percentiles."""
        events = [
            create_test_event("high_success", status="success"),
            create_test_event("high_success", status="success"),
            create_test_event("low_success", status="success"),
            create_test_event("low_success", status="error"),
        ]
        state = create_test_state(agents=["high_success", "low_success"], events=events)
        percentiles = calculate_agent_percentiles(state)

        # high_success (100%) should be better than low_success (50%)
        self.assertGreater(
            percentiles["high_success"]["success_percentile"],
            percentiles["low_success"]["success_percentile"]
        )

    def test_agents_with_no_events_excluded(self):
        """Test that agents with no events are excluded from percentiles."""
        events = [create_test_event("active_agent")]
        state = create_test_state(agents=["active_agent", "inactive_agent"], events=events)
        percentiles = calculate_agent_percentiles(state)

        self.assertIn("active_agent", percentiles)
        self.assertNotIn("inactive_agent", percentiles)

    def test_equal_agents(self):
        """Test percentiles when all agents are equal."""
        events = [
            create_test_event("agent1", duration_seconds=30.0, cost_usd=0.01),
            create_test_event("agent2", duration_seconds=30.0, cost_usd=0.01),
            create_test_event("agent3", duration_seconds=30.0, cost_usd=0.01),
        ]
        state = create_test_state(agents=["agent1", "agent2", "agent3"], events=events)
        percentiles = calculate_agent_percentiles(state)

        # All should have same percentiles when equal
        for agent_name in ["agent1", "agent2", "agent3"]:
            self.assertIn(agent_name, percentiles)


class TestStrengthDetection(unittest.TestCase):
    """Test suite for strength detection."""

    def test_insufficient_events(self):
        """Test that no strengths detected with insufficient events."""
        stats = {"event_count": 3, "success_rate": 1.0}
        percentiles = {"coding": {"duration_percentile": 1.0}}

        strengths = detect_strengths("coding", stats, percentiles, min_events=5)
        self.assertEqual(strengths, [])

    def test_fast_execution_detected(self):
        """Test fast_execution strength detection."""
        stats = {
            "event_count": 10,
            "success_rate": 0.8,
            "avg_duration": 20.0,
            "artifact_count": 5,
        }
        percentiles = {"coding": {"duration_percentile": 0.80}}

        strengths = detect_strengths("coding", stats, percentiles, min_events=5)
        self.assertIn("fast_execution", strengths)

    def test_high_success_rate_detected(self):
        """Test high_success_rate strength detection."""
        stats = {
            "event_count": 10,
            "success_rate": 0.96,
            "avg_duration": 60.0,
            "artifact_count": 5,
        }
        percentiles = {"coding": {"duration_percentile": 0.5}}

        strengths = detect_strengths("coding", stats, percentiles, min_events=5)
        self.assertIn("high_success_rate", strengths)

    def test_high_success_rate_threshold(self):
        """Test high_success_rate threshold at 95%."""
        # Just below threshold
        stats_below = {
            "event_count": 10,
            "success_rate": 0.94,
            "avg_duration": 60.0,
            "artifact_count": 5,
        }
        percentiles = {"coding": {"duration_percentile": 0.5}}

        strengths = detect_strengths("coding", stats_below, percentiles, min_events=5)
        self.assertNotIn("high_success_rate", strengths)

        # At threshold
        stats_at = {
            "event_count": 10,
            "success_rate": 0.95,
            "avg_duration": 60.0,
            "artifact_count": 5,
        }

        strengths = detect_strengths("coding", stats_at, percentiles, min_events=5)
        self.assertIn("high_success_rate", strengths)

    def test_low_cost_detected(self):
        """Test low_cost strength detection."""
        stats = {
            "event_count": 10,
            "success_rate": 0.8,
            "avg_cost": 0.001,
            "artifact_count": 5,
        }
        percentiles = {"coding": {"cost_percentile": 0.85}}

        strengths = detect_strengths("coding", stats, percentiles, min_events=5)
        self.assertIn("low_cost", strengths)

    def test_consistent_detected(self):
        """Test consistent strength detection."""
        stats = {
            "event_count": 10,
            "success_rate": 0.8,
            "duration_variance": 5.0,
            "artifact_count": 5,
        }
        percentiles = {"coding": {"consistency_percentile": 0.90}}

        strengths = detect_strengths("coding", stats, percentiles, min_events=5)
        self.assertIn("consistent", strengths)

    def test_prolific_detected(self):
        """Test prolific strength detection."""
        stats = {
            "event_count": 10,
            "success_rate": 0.8,
            "artifact_count": 25,  # 2.5 artifacts per event
        }
        percentiles = {"coding": {"duration_percentile": 0.5}}

        strengths = detect_strengths("coding", stats, percentiles, min_events=5)
        self.assertIn("prolific", strengths)

    def test_prolific_threshold(self):
        """Test prolific threshold at 2.0 artifacts per event."""
        # Just below threshold
        stats_below = {
            "event_count": 10,
            "success_rate": 0.8,
            "artifact_count": 19,  # 1.9 per event
        }
        percentiles = {"coding": {"duration_percentile": 0.5}}

        strengths = detect_strengths("coding", stats_below, percentiles, min_events=5)
        self.assertNotIn("prolific", strengths)

        # At threshold
        stats_at = {
            "event_count": 10,
            "success_rate": 0.8,
            "artifact_count": 20,  # 2.0 per event
        }

        strengths = detect_strengths("coding", stats_at, percentiles, min_events=5)
        self.assertIn("prolific", strengths)

    def test_multiple_strengths(self):
        """Test detecting multiple strengths simultaneously."""
        stats = {
            "event_count": 10,
            "success_rate": 0.98,
            "avg_duration": 15.0,
            "avg_cost": 0.001,
            "duration_variance": 2.0,
            "artifact_count": 30,
        }
        percentiles = {
            "coding": {
                "duration_percentile": 0.95,
                "cost_percentile": 0.90,
                "consistency_percentile": 0.80,
            }
        }

        strengths = detect_strengths("coding", stats, percentiles, min_events=5)
        self.assertIn("fast_execution", strengths)
        self.assertIn("high_success_rate", strengths)
        self.assertIn("low_cost", strengths)
        self.assertIn("consistent", strengths)
        self.assertIn("prolific", strengths)


class TestWeaknessDetection(unittest.TestCase):
    """Test suite for weakness detection."""

    def test_insufficient_events(self):
        """Test that no weaknesses detected with insufficient events."""
        stats = {"event_count": 2, "success_rate": 0.5}
        percentiles = {"coding": {"duration_percentile": 0.1}}

        weaknesses = detect_weaknesses("coding", stats, percentiles, min_events=5)
        self.assertEqual(weaknesses, [])

    def test_high_error_rate_detected(self):
        """Test high_error_rate weakness detection."""
        stats = {
            "event_count": 10,
            "success_rate": 0.65,
        }
        percentiles = {"coding": {"duration_percentile": 0.5}}

        weaknesses = detect_weaknesses("coding", stats, percentiles, min_events=5)
        self.assertIn("high_error_rate", weaknesses)

    def test_high_error_rate_threshold(self):
        """Test high_error_rate threshold at 70%."""
        # At threshold (70%)
        stats_at = {
            "event_count": 10,
            "success_rate": 0.70,
        }
        percentiles = {"coding": {"duration_percentile": 0.5}}

        weaknesses = detect_weaknesses("coding", stats_at, percentiles, min_events=5)
        self.assertNotIn("high_error_rate", weaknesses)

        # Below threshold (69%)
        stats_below = {
            "event_count": 10,
            "success_rate": 0.69,
        }

        weaknesses = detect_weaknesses("coding", stats_below, percentiles, min_events=5)
        self.assertIn("high_error_rate", weaknesses)

    def test_slow_detected(self):
        """Test slow weakness detection."""
        stats = {
            "event_count": 10,
            "success_rate": 0.8,
        }
        percentiles = {"coding": {"duration_percentile": 0.15}}

        weaknesses = detect_weaknesses("coding", stats, percentiles, min_events=5)
        self.assertIn("slow", weaknesses)

    def test_expensive_detected(self):
        """Test expensive weakness detection."""
        stats = {
            "event_count": 10,
            "success_rate": 0.8,
        }
        percentiles = {"coding": {"cost_percentile": 0.20}}

        weaknesses = detect_weaknesses("coding", stats, percentiles, min_events=5)
        self.assertIn("expensive", weaknesses)

    def test_inconsistent_detected(self):
        """Test inconsistent weakness detection."""
        stats = {
            "event_count": 10,
            "success_rate": 0.8,
        }
        percentiles = {"coding": {"consistency_percentile": 0.10}}

        weaknesses = detect_weaknesses("coding", stats, percentiles, min_events=5)
        self.assertIn("inconsistent", weaknesses)

    def test_multiple_weaknesses(self):
        """Test detecting multiple weaknesses simultaneously."""
        stats = {
            "event_count": 10,
            "success_rate": 0.60,
        }
        percentiles = {
            "coding": {
                "duration_percentile": 0.10,
                "cost_percentile": 0.15,
                "consistency_percentile": 0.20,
            }
        }

        weaknesses = detect_weaknesses("coding", stats, percentiles, min_events=5)
        self.assertIn("high_error_rate", weaknesses)
        self.assertIn("slow", weaknesses)
        self.assertIn("expensive", weaknesses)
        self.assertIn("inconsistent", weaknesses)


class TestUpdateAgentStrengthsWeaknesses(unittest.TestCase):
    """Test suite for updating agent strengths/weaknesses in state."""

    def test_empty_state(self):
        """Test with empty state."""
        state = create_test_state()
        updated_state = update_agent_strengths_weaknesses(state)

        self.assertEqual(updated_state["agents"], {})

    def test_single_agent_update(self):
        """Test updating single agent."""
        events = [
            create_test_event("coding", status="success", duration_seconds=20.0)
            for _ in range(10)
        ]
        state = create_test_state(agents=["coding"], events=events)
        updated_state = update_agent_strengths_weaknesses(state)

        # Should have high_success_rate strength
        self.assertIn("high_success_rate", updated_state["agents"]["coding"]["strengths"])

    def test_multiple_agents_update(self):
        """Test updating multiple agents."""
        events = []
        # Fast agent
        for _ in range(10):
            events.append(create_test_event("fast", duration_seconds=10.0))
        # Slow agent
        for _ in range(10):
            events.append(create_test_event("slow", duration_seconds=100.0))

        state = create_test_state(agents=["fast", "slow"], events=events)
        updated_state = update_agent_strengths_weaknesses(state)

        # Fast should have fast_execution strength
        self.assertIn("fast_execution", updated_state["agents"]["fast"]["strengths"])
        # Slow should have slow weakness
        self.assertIn("slow", updated_state["agents"]["slow"]["weaknesses"])

    def test_custom_window_size(self):
        """Test with custom window size."""
        # Create 30 events, last 5 are failures
        events = []
        for i in range(25):
            events.append(create_test_event("coding", status="success"))
        for i in range(5):
            events.append(create_test_event("coding", status="error"))

        state = create_test_state(agents=["coding"], events=events)

        # With window_size=30, should see mixed success rate
        updated_state = update_agent_strengths_weaknesses(state, window_size=30)
        # 25 success out of 30 = 83.3% (no weakness)
        self.assertNotIn("high_error_rate", updated_state["agents"]["coding"]["weaknesses"])

        # With window_size=5, should see only failures
        updated_state = update_agent_strengths_weaknesses(state, window_size=5)
        # 0 success out of 5 = 0% (weakness)
        self.assertIn("high_error_rate", updated_state["agents"]["coding"]["weaknesses"])

    def test_custom_min_events(self):
        """Test with custom min_events threshold."""
        events = [
            create_test_event("coding", status="success", duration_seconds=10.0)
            for _ in range(3)
        ]
        state = create_test_state(agents=["coding"], events=events)

        # With min_events=5, should have no strengths/weaknesses
        updated_state = update_agent_strengths_weaknesses(state, min_events=5)
        self.assertEqual(updated_state["agents"]["coding"]["strengths"], [])
        self.assertEqual(updated_state["agents"]["coding"]["weaknesses"], [])

        # With min_events=2, should detect strengths
        updated_state = update_agent_strengths_weaknesses(state, min_events=2)
        self.assertGreater(len(updated_state["agents"]["coding"]["strengths"]), 0)


class TestDescriptions(unittest.TestCase):
    """Test suite for description functions."""

    def test_strength_descriptions(self):
        """Test all strength descriptions."""
        strengths = [
            "fast_execution",
            "high_success_rate",
            "low_cost",
            "consistent",
            "prolific"
        ]

        for strength in strengths:
            desc = get_strength_description(strength)
            self.assertIsInstance(desc, str)
            self.assertGreater(len(desc), 0)
            self.assertNotEqual(desc, "Unknown strength")

    def test_weakness_descriptions(self):
        """Test all weakness descriptions."""
        weaknesses = [
            "high_error_rate",
            "slow",
            "expensive",
            "inconsistent"
        ]

        for weakness in weaknesses:
            desc = get_weakness_description(weakness)
            self.assertIsInstance(desc, str)
            self.assertGreater(len(desc), 0)
            self.assertNotEqual(desc, "Unknown weakness")

    def test_unknown_strength(self):
        """Test unknown strength returns default."""
        desc = get_strength_description("unknown_strength")
        self.assertEqual(desc, "Unknown strength")

    def test_unknown_weakness(self):
        """Test unknown weakness returns default."""
        desc = get_weakness_description("unknown_weakness")
        self.assertEqual(desc, "Unknown weakness")


class TestEdgeCases(unittest.TestCase):
    """Test suite for edge cases and boundary conditions."""

    def test_zero_variance_single_event(self):
        """Test variance with single event is zero."""
        events = [create_test_event("coding", duration_seconds=30.0)]
        stats = calculate_rolling_window_stats(events, "coding")

        self.assertEqual(stats["duration_variance"], 0.0)

    def test_all_events_same_duration(self):
        """Test variance when all events have same duration."""
        events = [create_test_event("coding", duration_seconds=30.0) for _ in range(5)]
        stats = calculate_rolling_window_stats(events, "coding")

        self.assertEqual(stats["duration_variance"], 0.0)

    def test_agent_not_in_events(self):
        """Test stats for agent with no events."""
        events = [create_test_event("other_agent")]
        stats = calculate_rolling_window_stats(events, "coding")

        self.assertEqual(stats["event_count"], 0)
        self.assertEqual(stats["success_rate"], 0.0)

    def test_window_larger_than_events(self):
        """Test window size larger than available events."""
        events = [create_test_event("coding") for _ in range(5)]
        stats = calculate_rolling_window_stats(events, "coding", window_size=100)

        # Should use all 5 events
        self.assertEqual(stats["event_count"], 5)

    def test_all_failures(self):
        """Test with 100% failure rate."""
        events = [create_test_event("coding", status="error") for _ in range(10)]
        stats = calculate_rolling_window_stats(events, "coding")

        self.assertEqual(stats["success_rate"], 0.0)

    def test_percentile_boundary_conditions(self):
        """Test percentile calculations at boundaries."""
        events = [
            create_test_event("agent1", duration_seconds=10.0),
            create_test_event("agent2", duration_seconds=20.0),
        ]
        state = create_test_state(agents=["agent1", "agent2"], events=events)
        percentiles = calculate_agent_percentiles(state)

        # With 2 agents, percentiles should be 0.0 and 1.0
        self.assertIn(percentiles["agent1"]["duration_percentile"], [0.0, 1.0])
        self.assertIn(percentiles["agent2"]["duration_percentile"], [0.0, 1.0])


class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests for realistic scenarios."""

    def test_scenario_high_performing_agent(self):
        """Test detection for high-performing agent."""
        events = []
        for _ in range(20):
            events.append(create_test_event(
                "elite_agent",
                status="success",
                duration_seconds=15.0,
                cost_usd=0.001,
                artifacts=["file:a.py", "file:b.py", "commit:abc"]
            ))

        state = create_test_state(agents=["elite_agent"], events=events)
        updated_state = update_agent_strengths_weaknesses(state)

        strengths = updated_state["agents"]["elite_agent"]["strengths"]
        weaknesses = updated_state["agents"]["elite_agent"]["weaknesses"]

        # Should have multiple strengths
        self.assertIn("high_success_rate", strengths)
        self.assertIn("prolific", strengths)
        # Should have no weaknesses
        self.assertEqual(len(weaknesses), 0)

    def test_scenario_struggling_agent(self):
        """Test detection for struggling agent."""
        events = []
        for i in range(20):
            status = "success" if i % 3 == 0 else "error"
            events.append(create_test_event(
                "struggling_agent",
                status=status,
                duration_seconds=120.0,
                cost_usd=0.5
            ))

        state = create_test_state(agents=["struggling_agent"], events=events)
        updated_state = update_agent_strengths_weaknesses(state)

        weaknesses = updated_state["agents"]["struggling_agent"]["weaknesses"]

        # Should have high_error_rate weakness (33% success rate)
        self.assertIn("high_error_rate", weaknesses)

    def test_scenario_comparative_agents(self):
        """Test comparative detection across multiple agents."""
        events = []

        # Fast, cheap, successful agent
        for _ in range(20):
            events.append(create_test_event(
                "agent_fast",
                status="success",
                duration_seconds=20.0,
                cost_usd=0.005
            ))

        # Slow, expensive agent
        for _ in range(20):
            events.append(create_test_event(
                "agent_slow",
                status="success",
                duration_seconds=100.0,
                cost_usd=0.05
            ))

        # Medium agent
        for _ in range(20):
            events.append(create_test_event(
                "agent_medium",
                status="success",
                duration_seconds=60.0,
                cost_usd=0.025
            ))

        state = create_test_state(
            agents=["agent_fast", "agent_slow", "agent_medium"],
            events=events
        )
        updated_state = update_agent_strengths_weaknesses(state)

        # Fast should have strengths
        self.assertIn("fast_execution", updated_state["agents"]["agent_fast"]["strengths"])
        self.assertIn("low_cost", updated_state["agents"]["agent_fast"]["strengths"])

        # Slow should have weaknesses
        self.assertIn("slow", updated_state["agents"]["agent_slow"]["weaknesses"])
        self.assertIn("expensive", updated_state["agents"]["agent_slow"]["weaknesses"])

        # Medium should have neither strong strengths nor weaknesses
        # (depends on exact percentile thresholds)

    def test_scenario_inconsistent_agent(self):
        """Test detection of inconsistent performance."""
        events = []
        # Highly variable durations
        durations = [10, 100, 15, 90, 20, 95, 12, 85, 25, 100]
        for duration in durations:
            events.append(create_test_event(
                "inconsistent_agent",
                duration_seconds=float(duration)
            ))

        # Consistent agent
        for _ in range(10):
            events.append(create_test_event(
                "consistent_agent",
                duration_seconds=50.0
            ))

        state = create_test_state(
            agents=["inconsistent_agent", "consistent_agent"],
            events=events
        )
        updated_state = update_agent_strengths_weaknesses(state)

        # Inconsistent should have inconsistent weakness
        self.assertIn(
            "inconsistent",
            updated_state["agents"]["inconsistent_agent"]["weaknesses"]
        )

        # Consistent should have consistent strength
        self.assertIn(
            "consistent",
            updated_state["agents"]["consistent_agent"]["strengths"]
        )


if __name__ == "__main__":
    unittest.main()
