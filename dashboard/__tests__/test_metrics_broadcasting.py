"""Unit tests for metrics event broadcasting system.

Tests the AgentMetricsCollector's event subscription and broadcasting functionality.
"""

import tempfile
import time
from pathlib import Path
from typing import List, Tuple

import pytest

from dashboard.collector import AgentMetricsCollector
from dashboard.metrics import AgentEvent


class EventRecorder:
    """Helper class to record events from the collector."""

    def __init__(self):
        self.events: List[Tuple[str, AgentEvent]] = []

    def callback(self, event_type: str, event: AgentEvent):
        """Record an event."""
        self.events.append((event_type, event))

    def clear(self):
        """Clear recorded events."""
        self.events = []

    def get_events_by_type(self, event_type: str) -> List[AgentEvent]:
        """Get all events of a specific type."""
        return [event for etype, event in self.events if etype == event_type]


@pytest.fixture
def temp_metrics_dir():
    """Create a temporary directory for metrics files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def collector(temp_metrics_dir):
    """Create a collector with a temporary metrics directory."""
    return AgentMetricsCollector(
        project_name="test-project",
        metrics_dir=temp_metrics_dir
    )


@pytest.fixture
def recorder():
    """Create an event recorder."""
    return EventRecorder()


def test_subscribe_and_unsubscribe(collector, recorder):
    """Test subscribing and unsubscribing from events."""
    # Subscribe
    collector.subscribe(recorder.callback)
    assert recorder.callback in collector._event_callbacks

    # Unsubscribe
    collector.unsubscribe(recorder.callback)
    assert recorder.callback not in collector._event_callbacks


def test_multiple_subscribers(collector):
    """Test that multiple subscribers can be registered."""
    recorder1 = EventRecorder()
    recorder2 = EventRecorder()
    recorder3 = EventRecorder()

    collector.subscribe(recorder1.callback)
    collector.subscribe(recorder2.callback)
    collector.subscribe(recorder3.callback)

    assert len(collector._event_callbacks) == 3
    assert recorder1.callback in collector._event_callbacks
    assert recorder2.callback in collector._event_callbacks
    assert recorder3.callback in collector._event_callbacks


def test_task_started_event(collector, recorder):
    """Test that task_started event is broadcast when tracking begins."""
    collector.subscribe(recorder.callback)

    session_id = collector.start_session()

    # Track an agent (this should trigger task_started)
    with collector.track_agent("test-agent", "AI-107", "claude-sonnet-4-5", session_id):
        pass

    collector.end_session(session_id)

    # Check for task_started event
    started_events = recorder.get_events_by_type("task_started")
    assert len(started_events) == 1

    event = started_events[0]
    assert event["agent_name"] == "test-agent"
    assert event["ticket_key"] == "AI-107"
    assert event["model_used"] == "claude-sonnet-4-5"
    assert event["status"] == "success"  # Optimistic status
    assert event["ended_at"] == ""  # Not ended yet


def test_task_completed_event(collector, recorder):
    """Test that task_completed event is broadcast on successful completion."""
    collector.subscribe(recorder.callback)

    session_id = collector.start_session()

    # Track an agent successfully
    with collector.track_agent("test-agent", "AI-107", "claude-sonnet-4-5", session_id) as tracker:
        tracker.add_tokens(1000, 2000)
        tracker.add_artifact("file:test.py")

    collector.end_session(session_id)

    # Check for task_completed event
    completed_events = recorder.get_events_by_type("task_completed")
    assert len(completed_events) == 1

    event = completed_events[0]
    assert event["agent_name"] == "test-agent"
    assert event["ticket_key"] == "AI-107"
    assert event["status"] == "success"
    assert event["input_tokens"] == 1000
    assert event["output_tokens"] == 2000
    assert event["total_tokens"] == 3000
    assert "file:test.py" in event["artifacts"]
    assert event["ended_at"] != ""  # Should have end time


def test_task_failed_event(collector, recorder):
    """Test that task_failed event is broadcast on error."""
    collector.subscribe(recorder.callback)

    session_id = collector.start_session()

    # Track an agent that fails
    try:
        with collector.track_agent("test-agent", "AI-107", "claude-sonnet-4-5", session_id) as tracker:
            tracker.add_tokens(500, 1000)
            raise ValueError("Test error")
    except ValueError:
        pass  # Expected

    collector.end_session(session_id)

    # Check for task_failed event
    failed_events = recorder.get_events_by_type("task_failed")
    assert len(failed_events) == 1

    event = failed_events[0]
    assert event["agent_name"] == "test-agent"
    assert event["status"] == "error"
    assert event["error_message"] == "Test error"
    assert event["input_tokens"] == 500
    assert event["output_tokens"] == 1000


def test_all_three_event_types(collector, recorder):
    """Test that all three event types are broadcast in sequence."""
    collector.subscribe(recorder.callback)

    session_id = collector.start_session()

    # Successful task
    with collector.track_agent("test-agent", "AI-107", "claude-sonnet-4-5", session_id) as tracker:
        tracker.add_tokens(1000, 2000)

    collector.end_session(session_id)

    # Should have task_started and task_completed
    assert len(recorder.get_events_by_type("task_started")) == 1
    assert len(recorder.get_events_by_type("task_completed")) == 1
    assert len(recorder.get_events_by_type("task_failed")) == 0

    # Verify order
    assert recorder.events[0][0] == "task_started"
    assert recorder.events[1][0] == "task_completed"


def test_multiple_tasks(collector, recorder):
    """Test broadcasting for multiple sequential tasks."""
    collector.subscribe(recorder.callback)

    session_id = collector.start_session()

    # Track multiple agents
    for i in range(3):
        with collector.track_agent(f"agent-{i}", f"AI-{100+i}", "claude-sonnet-4-5", session_id) as tracker:
            tracker.add_tokens(100 * (i+1), 200 * (i+1))

    collector.end_session(session_id)

    # Should have 3 started and 3 completed events
    assert len(recorder.get_events_by_type("task_started")) == 3
    assert len(recorder.get_events_by_type("task_completed")) == 3


def test_event_callback_error_handling(collector, recorder):
    """Test that errors in callbacks don't break the collector."""
    def bad_callback(event_type: str, event: AgentEvent):
        raise RuntimeError("Bad callback")

    collector.subscribe(bad_callback)
    collector.subscribe(recorder.callback)

    session_id = collector.start_session()

    # This should not raise despite bad_callback failing
    with collector.track_agent("test-agent", "AI-107", "claude-sonnet-4-5", session_id) as tracker:
        tracker.add_tokens(1000, 2000)

    collector.end_session(session_id)

    # Good callback should still work
    assert len(recorder.events) == 2  # task_started and task_completed


def test_event_contains_session_id(collector, recorder):
    """Test that events contain the correct session_id."""
    collector.subscribe(recorder.callback)

    session_id = collector.start_session()

    with collector.track_agent("test-agent", "AI-107", "claude-sonnet-4-5", session_id) as tracker:
        tracker.add_tokens(1000, 2000)

    collector.end_session(session_id)

    # All events should have the correct session_id
    for event_type, event in recorder.events:
        assert event["session_id"] == session_id


def test_unsubscribe_stops_events(collector, recorder):
    """Test that unsubscribing stops receiving events."""
    collector.subscribe(recorder.callback)

    session_id = collector.start_session()

    # First task with subscription
    with collector.track_agent("test-agent", "AI-107", "claude-sonnet-4-5", session_id) as tracker:
        tracker.add_tokens(1000, 2000)

    assert len(recorder.events) == 2  # task_started and task_completed

    # Unsubscribe
    collector.unsubscribe(recorder.callback)
    recorder.clear()

    # Second task without subscription
    with collector.track_agent("test-agent-2", "AI-108", "claude-sonnet-4-5", session_id) as tracker:
        tracker.add_tokens(1000, 2000)

    collector.end_session(session_id)

    # Should not have received any new events
    assert len(recorder.events) == 0


def test_event_data_completeness(collector, recorder):
    """Test that events contain all required fields."""
    collector.subscribe(recorder.callback)

    session_id = collector.start_session()

    with collector.track_agent("test-agent", "AI-107", "claude-sonnet-4-5", session_id) as tracker:
        tracker.add_tokens(1000, 2000)
        tracker.add_artifact("file:test.py")
        tracker.add_artifact("commit:abc123")

    collector.end_session(session_id)

    # Check completed event
    completed_events = recorder.get_events_by_type("task_completed")
    assert len(completed_events) == 1

    event = completed_events[0]

    # Verify all required fields
    required_fields = [
        "event_id", "agent_name", "session_id", "ticket_key",
        "started_at", "ended_at", "duration_seconds", "status",
        "input_tokens", "output_tokens", "total_tokens",
        "estimated_cost_usd", "artifacts", "error_message", "model_used"
    ]

    for field in required_fields:
        assert field in event, f"Missing field: {field}"

    # Verify field values
    assert event["event_id"] != ""
    assert event["agent_name"] == "test-agent"
    assert event["ticket_key"] == "AI-107"
    assert event["model_used"] == "claude-sonnet-4-5"
    assert event["status"] == "success"
    assert event["input_tokens"] == 1000
    assert event["output_tokens"] == 2000
    assert event["total_tokens"] == 3000
    assert event["estimated_cost_usd"] > 0
    assert len(event["artifacts"]) == 2
    assert event["error_message"] == ""
    assert event["duration_seconds"] >= 0


def test_no_subscribers_no_error(collector):
    """Test that tracking works without any subscribers."""
    session_id = collector.start_session()

    # Should not raise even with no subscribers
    with collector.track_agent("test-agent", "AI-107", "claude-sonnet-4-5", session_id) as tracker:
        tracker.add_tokens(1000, 2000)

    collector.end_session(session_id)

    # Verify event was still recorded
    state = collector.get_state()
    assert len(state["events"]) == 1


def test_duplicate_subscription_prevention(collector, recorder):
    """Test that the same callback cannot be subscribed twice."""
    collector.subscribe(recorder.callback)
    collector.subscribe(recorder.callback)  # Try to subscribe again

    # Should only be in the list once
    assert len([cb for cb in collector._event_callbacks if cb == recorder.callback]) == 1


def test_event_timing(collector, recorder):
    """Test that event timing is accurate."""
    collector.subscribe(recorder.callback)

    session_id = collector.start_session()

    with collector.track_agent("test-agent", "AI-107", "claude-sonnet-4-5", session_id) as tracker:
        time.sleep(0.1)  # Sleep for 100ms
        tracker.add_tokens(1000, 2000)

    collector.end_session(session_id)

    # Check completed event timing
    completed_events = recorder.get_events_by_type("task_completed")
    assert len(completed_events) == 1

    event = completed_events[0]
    # Should be at least 100ms (0.1 seconds)
    assert event["duration_seconds"] >= 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
