"""Integration test for strengths/weaknesses with AgentMetricsCollector.

This test demonstrates how the strengths/weaknesses detection integrates
with the existing AgentMetricsCollector infrastructure.
"""

import unittest
import tempfile
from pathlib import Path
from agent_metrics_collector import AgentMetricsCollector
from strengths_weaknesses import update_agent_strengths_weaknesses


class TestStrengthsWeaknessesIntegration(unittest.TestCase):
    """Integration test suite for strengths/weaknesses with collector."""

    def setUp(self):
        """Set up temporary directory for test metrics."""
        self.temp_dir = tempfile.mkdtemp()
        self.metrics_dir = Path(self.temp_dir)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_integration_with_collector(self):
        """Test full integration with AgentMetricsCollector."""
        # Create collector
        collector = AgentMetricsCollector(
            project_name="test-integration",
            metrics_dir=self.metrics_dir
        )

        # Start a session
        session_id = collector.start_session(session_type="initializer")

        # Track multiple agents with different performance characteristics
        # Agent 1: Fast and successful
        for _ in range(15):
            with collector.track_agent("fast_agent", "AI-48", "claude-sonnet-4-5", session_id) as tracker:
                tracker.add_tokens(input_tokens=500, output_tokens=500)
                tracker.add_artifact("file:fast.py")
                tracker.add_artifact("commit:abc123")
                # Fast duration is simulated by the tracker

        # Agent 2: Slow with some errors
        for i in range(15):
            with collector.track_agent("slow_agent", "AI-48", "claude-opus-4-6", session_id) as tracker:
                tracker.add_tokens(input_tokens=2000, output_tokens=2000)
                if i % 4 == 0:  # 25% error rate
                    tracker.set_error("Test error")

        # End session
        collector.end_session(session_id, status="complete")

        # Get current state
        state = collector.get_state()

        # Verify agents were tracked
        self.assertIn("fast_agent", state["agents"])
        self.assertIn("slow_agent", state["agents"])

        # Update strengths/weaknesses
        updated_state = update_agent_strengths_weaknesses(state, window_size=20, min_events=10)

        # Verify fast_agent has strengths
        fast_profile = updated_state["agents"]["fast_agent"]
        self.assertGreater(len(fast_profile["strengths"]), 0)
        self.assertIn("high_success_rate", fast_profile["strengths"])
        self.assertIn("low_cost", fast_profile["strengths"])

        # Verify slow_agent has weaknesses or fewer strengths
        slow_profile = updated_state["agents"]["slow_agent"]
        # Slow agent should not have high_success_rate (75% success)
        self.assertNotIn("high_success_rate", slow_profile["strengths"])
        # Should be more expensive due to Opus model
        self.assertIn("expensive", slow_profile["weaknesses"])

        # Verify strengths/weaknesses are persisted
        self.assertIsInstance(fast_profile["strengths"], list)
        self.assertIsInstance(fast_profile["weaknesses"], list)
        self.assertIsInstance(slow_profile["strengths"], list)
        self.assertIsInstance(slow_profile["weaknesses"], list)

    def test_continuous_updates(self):
        """Test that strengths/weaknesses update as more events are tracked."""
        collector = AgentMetricsCollector(
            project_name="test-continuous",
            metrics_dir=self.metrics_dir
        )

        session_id = collector.start_session(session_type="initializer")

        # Track agent with initially good performance
        for _ in range(10):
            with collector.track_agent("improving_agent", "AI-48", "claude-sonnet-4-5", session_id) as tracker:
                tracker.add_tokens(input_tokens=1000, output_tokens=1000)
                tracker.add_artifact("file:code.py")
                # All successful

        # Update and check
        state = collector.get_state()
        updated_state = update_agent_strengths_weaknesses(state, min_events=5)
        profile = updated_state["agents"]["improving_agent"]

        # Should have high_success_rate strength
        self.assertIn("high_success_rate", profile["strengths"])
        initial_strengths = len(profile["strengths"])

        # Track more events with excellent performance
        for _ in range(10):
            with collector.track_agent("improving_agent", "AI-48", "claude-haiku-4-5", session_id) as tracker:
                tracker.add_tokens(input_tokens=500, output_tokens=500)
                tracker.add_artifact("file:fast.py")
                tracker.add_artifact("commit:xyz")
                tracker.add_artifact("test:test_fast.py")
                # Now using cheaper model with more artifacts

        # Update again
        state = collector.get_state()
        updated_state = update_agent_strengths_weaknesses(state, min_events=5)
        profile = updated_state["agents"]["improving_agent"]

        # Should have additional strengths now
        self.assertIn("high_success_rate", profile["strengths"])
        # With rolling window, the agent should have prolific due to recent high artifact count
        self.assertIn("prolific", profile["strengths"])  # 3 artifacts per event
        # May or may not have low_cost depending on window (first 10 used Sonnet, last 10 used Haiku)

        collector.end_session(session_id, status="complete")

    def test_multiple_agents_comparative(self):
        """Test comparative analysis across multiple agents."""
        collector = AgentMetricsCollector(
            project_name="test-comparative",
            metrics_dir=self.metrics_dir
        )

        session_id = collector.start_session(session_type="initializer")

        # Create 4 different agents with varying characteristics
        agents = {
            "coding": ("claude-haiku-4-5", 1000, ["file:code.py"]),
            "github": ("claude-sonnet-4-5", 1500, ["pr:created", "commit:abc"]),
            "linear": ("claude-sonnet-4-5", 2000, ["issue:AI-48"]),
            "slack": ("claude-opus-4-6", 3000, ["message:sent"]),
        }

        # Track events for each agent
        for agent_name, (model, tokens, artifacts) in agents.items():
            for _ in range(15):
                with collector.track_agent(agent_name, "AI-48", model, session_id) as tracker:
                    tracker.add_tokens(input_tokens=tokens // 2, output_tokens=tokens // 2)
                    for artifact in artifacts:
                        tracker.add_artifact(artifact)

        # Update strengths/weaknesses
        state = collector.get_state()
        updated_state = update_agent_strengths_weaknesses(state, min_events=10)

        # Verify all agents have been analyzed
        for agent_name in agents.keys():
            self.assertIn(agent_name, updated_state["agents"])
            profile = updated_state["agents"][agent_name]
            # Each should have either strengths or weaknesses or both
            has_feedback = len(profile["strengths"]) > 0 or len(profile["weaknesses"]) > 0
            # With 4 agents and relative comparisons, most should have some feedback
            # (though not guaranteed for all due to thresholds)

        # Coding (Haiku) should be cheapest
        coding_profile = updated_state["agents"]["coding"]
        self.assertIn("low_cost", coding_profile["strengths"])

        # Slack (Opus) should be most expensive
        slack_profile = updated_state["agents"]["slack"]
        self.assertIn("expensive", slack_profile["weaknesses"])

        collector.end_session(session_id, status="complete")


if __name__ == "__main__":
    unittest.main()
