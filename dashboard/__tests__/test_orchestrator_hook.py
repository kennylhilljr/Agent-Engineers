"""Tests for OrchestratorHook (AI-172 / REQ-TECH-007).

Verifies:
  - Hook initialisation
  - emit_delegation() stores event correctly
  - emit_decision() stores event correctly
  - emit_reasoning() stores event correctly
  - Events are non-blocking (no exceptions even if collector is None)
  - Graceful fallback when no collector attached
  - Event format is correct (all required fields present)
  - Multiple events accumulate
  - Hook can be attached and detached
  - Collector _record_event_callbacks are invoked
  - HTTP server delivery path (graceful degradation on connection error)
  - session_id is consistent across events from same hook instance
  - Factory helper functions work correctly
  - add_callback / remove_callback work correctly
  - Thread safety: concurrent emissions do not corrupt state

Acceptance criteria for AI-172 / REQ-TECH-007:
  - Orchestrator emits events at key points
  - Events have all required data (agent, task, reasoning, delegation info)
  - Non-blocking event emission
  - Graceful fallback if dashboard not available
  - Minimal code changes to orchestrator
"""

import threading
import time
import uuid
from unittest.mock import MagicMock, patch

import pytest

from dashboard.orchestrator_hook import (
    OrchestratorHook,
    attach_to_collector,
    attach_to_server,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wait_for_events(hook: OrchestratorHook, count: int, timeout: float = 2.0) -> None:
    """Block until ``hook.events`` contains at least ``count`` entries."""
    deadline = time.monotonic() + timeout
    while len(hook.events) < count:
        if time.monotonic() > deadline:
            raise TimeoutError(
                f"Expected at least {count} event(s) in hook after {timeout}s, "
                f"got {len(hook.events)}"
            )
        time.sleep(0.01)


def _make_mock_collector():
    """Return a MagicMock that mimics an AgentMetricsCollector."""
    collector = MagicMock()
    collector._record_event_callbacks = []
    return collector


# ---------------------------------------------------------------------------
# 1. Initialisation
# ---------------------------------------------------------------------------

class TestHookInitialisation:
    """Hook can be created and has sensible defaults."""

    def test_default_init_creates_hook(self):
        """OrchestratorHook can be instantiated without arguments."""
        hook = OrchestratorHook()
        assert hook is not None

    def test_default_session_id_is_uuid_string(self):
        """A session_id is auto-generated and looks like a UUID."""
        hook = OrchestratorHook()
        sid = hook._session_id
        assert isinstance(sid, str)
        # Should parse as a valid UUID
        parsed = uuid.UUID(sid)
        assert str(parsed) == sid

    def test_explicit_session_id_is_used(self):
        """A caller-supplied session_id is stored verbatim."""
        sid = "my-custom-session-id"
        hook = OrchestratorHook(session_id=sid)
        assert hook._session_id == sid

    def test_no_collector_by_default(self):
        """Collector is None before attach_to_collector() is called."""
        hook = OrchestratorHook()
        assert hook._collector is None

    def test_no_server_url_by_default(self):
        """server_url is None before attach_to_server() is called."""
        hook = OrchestratorHook()
        assert hook._server_url is None

    def test_events_list_is_empty_initially(self):
        """No events are recorded before any emit call."""
        hook = OrchestratorHook()
        assert hook.events == []


# ---------------------------------------------------------------------------
# 2. emit_delegation()
# ---------------------------------------------------------------------------

class TestEmitDelegation:
    """emit_delegation() stores the correct event."""

    def test_emit_delegation_stores_one_event(self):
        """A single emit_delegation call results in exactly one stored event."""
        hook = OrchestratorHook()
        hook.emit_delegation("coding", "Implement feature", "Best tool for the job")
        _wait_for_events(hook, 1)
        assert len(hook.events) == 1

    def test_emit_delegation_event_has_agent_name(self):
        """Event contains the correct agent_name."""
        hook = OrchestratorHook()
        hook.emit_delegation("linear", "List issues", "Need issue list")
        _wait_for_events(hook, 1)
        event = hook.events[0]
        assert event["agent_name"] == "linear"

    def test_emit_delegation_event_type_is_delegation(self):
        """The _event_type field is 'delegation'."""
        hook = OrchestratorHook()
        hook.emit_delegation("github", "Open PR", "Work is done")
        _wait_for_events(hook, 1)
        event = hook.events[0]
        assert event["_event_type"] == "delegation"

    def test_emit_delegation_task_stored(self):
        """The task text is stored in the event."""
        hook = OrchestratorHook()
        task = "Implement orchestrator hook for AI-172"
        hook.emit_delegation("coding", task, "Best coding agent")
        _wait_for_events(hook, 1)
        assert hook.events[0]["_task"] == task

    def test_emit_delegation_reasoning_stored(self):
        """The reasoning text is stored in the event."""
        hook = OrchestratorHook()
        reasoning = "Coding agent is the best choice for implementation tasks"
        hook.emit_delegation("coding", "Do something", reasoning)
        _wait_for_events(hook, 1)
        assert hook.events[0]["_reasoning"] == reasoning

    def test_emit_delegation_has_all_required_agent_event_fields(self):
        """The stored event contains all required AgentEvent-compatible fields."""
        required_fields = [
            "event_id", "agent_name", "session_id", "ticket_key",
            "started_at", "ended_at", "duration_seconds", "status",
            "input_tokens", "output_tokens", "total_tokens", "estimated_cost_usd",
            "artifacts", "error_message", "model_used",
        ]
        hook = OrchestratorHook()
        hook.emit_delegation("coding", "task", "reasoning")
        _wait_for_events(hook, 1)
        event = hook.events[0]
        for field in required_fields:
            assert field in event, f"Missing required field: {field}"

    def test_emit_delegation_session_id_matches_hook(self):
        """The event's session_id matches the hook's session_id."""
        sid = "test-session-xyz"
        hook = OrchestratorHook(session_id=sid)
        hook.emit_delegation("coding", "task", "reasoning")
        _wait_for_events(hook, 1)
        assert hook.events[0]["session_id"] == sid


# ---------------------------------------------------------------------------
# 3. emit_decision()
# ---------------------------------------------------------------------------

class TestEmitDecision:
    """emit_decision() stores the correct event."""

    def test_emit_decision_stores_one_event(self):
        """A single emit_decision call results in exactly one stored event."""
        hook = OrchestratorHook()
        hook.emit_decision({"decision": "work on AI-172"})
        _wait_for_events(hook, 1)
        assert len(hook.events) == 1

    def test_emit_decision_event_type_is_decision(self):
        """The _event_type field is 'decision'."""
        hook = OrchestratorHook()
        hook.emit_decision("Choose coding agent")
        _wait_for_events(hook, 1)
        assert hook.events[0]["_event_type"] == "decision"

    def test_emit_decision_with_dict_argument(self):
        """emit_decision works when passed a dict."""
        hook = OrchestratorHook()
        hook.emit_decision({"decision": "start working", "confidence": 0.9})
        _wait_for_events(hook, 1)
        assert len(hook.events) == 1

    def test_emit_decision_with_string_argument(self):
        """emit_decision works when passed a plain string."""
        hook = OrchestratorHook()
        hook.emit_decision("Start working on AI-172")
        _wait_for_events(hook, 1)
        assert len(hook.events) == 1

    def test_emit_decision_reasoning_stored(self):
        """The reasoning text is stored when provided."""
        hook = OrchestratorHook()
        reasoning = "This is the highest priority ticket"
        hook.emit_decision({"decision": "work on AI-172"}, reasoning=reasoning)
        _wait_for_events(hook, 1)
        assert hook.events[0]["_reasoning"] == reasoning


# ---------------------------------------------------------------------------
# 4. Non-blocking behaviour
# ---------------------------------------------------------------------------

class TestNonBlocking:
    """emit_* calls must not raise even if the collector/server is unavailable."""

    def test_emit_delegation_does_not_raise_without_collector(self):
        """No exception when no collector is attached."""
        hook = OrchestratorHook()
        # Should not raise
        hook.emit_delegation("coding", "task", "reasoning")

    def test_emit_decision_does_not_raise_without_collector(self):
        """No exception when no collector is attached."""
        hook = OrchestratorHook()
        hook.emit_decision("some decision")

    def test_emit_reasoning_does_not_raise_without_collector(self):
        """No exception when no collector is attached."""
        hook = OrchestratorHook()
        hook.emit_reasoning("Some reasoning text")

    def test_emit_delegation_does_not_raise_with_broken_collector(self):
        """No exception when the attached collector raises on callback invocation."""
        def bad_callback(event):
            raise RuntimeError("Broken collector!")

        mock_collector = MagicMock()
        mock_collector._record_event_callbacks = [bad_callback]

        hook = OrchestratorHook()
        hook.attach_to_collector(mock_collector)

        # Should not raise (exception is swallowed in background thread)
        hook.emit_delegation("coding", "task", "reasoning")
        _wait_for_events(hook, 1)  # event is still stored

    def test_emit_delegation_does_not_raise_with_unreachable_server(self):
        """No exception when the server URL is unreachable."""
        hook = OrchestratorHook()
        hook.attach_to_server("http://127.0.0.1:19999")  # nothing listening here
        # Should not raise
        hook.emit_delegation("coding", "task", "reasoning")
        _wait_for_events(hook, 1)


# ---------------------------------------------------------------------------
# 5. Graceful fallback
# ---------------------------------------------------------------------------

class TestGracefulFallback:
    """Events are always stored locally even when no external target is available."""

    def test_events_stored_with_no_output(self):
        """Events accumulate in-process even with no collector or server."""
        hook = OrchestratorHook()
        hook.emit_delegation("coding", "task1", "reason1")
        hook.emit_delegation("linear", "task2", "reason2")
        _wait_for_events(hook, 2)
        assert len(hook.events) == 2

    def test_clear_events_empties_store(self):
        """clear_events() removes all stored events."""
        hook = OrchestratorHook()
        hook.emit_delegation("coding", "task", "reason")
        _wait_for_events(hook, 1)
        hook.clear_events()
        assert hook.events == []

    def test_events_returns_copy(self):
        """hook.events returns a copy; mutating it does not affect the store."""
        hook = OrchestratorHook()
        hook.emit_delegation("coding", "task", "reason")
        _wait_for_events(hook, 1)
        copy = hook.events
        copy.clear()
        assert len(hook.events) == 1  # original is untouched


# ---------------------------------------------------------------------------
# 6. Multiple events accumulate
# ---------------------------------------------------------------------------

class TestMultipleEvents:
    """Multiple emit calls accumulate in the correct order."""

    def test_multiple_delegations_accumulate(self):
        """Three consecutive emit_delegation calls produce three events."""
        hook = OrchestratorHook()
        hook.emit_delegation("coding", "task1", "r1")
        hook.emit_delegation("linear", "task2", "r2")
        hook.emit_delegation("github", "task3", "r3")
        _wait_for_events(hook, 3)
        assert len(hook.events) == 3

    def test_mixed_emit_methods_accumulate(self):
        """Different emit methods all contribute to the same event store."""
        hook = OrchestratorHook()
        hook.emit_delegation("coding", "task", "reason")
        hook.emit_decision("some decision")
        hook.emit_reasoning("some reasoning")
        _wait_for_events(hook, 3)
        assert len(hook.events) == 3

    def test_agent_names_are_correct_for_multiple_events(self):
        """Each event carries the correct agent name."""
        hook = OrchestratorHook()
        hook.emit_delegation("coding", "code task", "reason")
        hook.emit_delegation("linear", "linear task", "reason")
        _wait_for_events(hook, 2)
        agents = [e["agent_name"] for e in hook.events]
        assert "coding" in agents
        assert "linear" in agents


# ---------------------------------------------------------------------------
# 7. Attach / detach
# ---------------------------------------------------------------------------

class TestAttachDetach:
    """Hook can be attached to and detached from a collector."""

    def test_attach_to_collector_sets_collector(self):
        """attach_to_collector sets the _collector attribute."""
        hook = OrchestratorHook()
        mock = _make_mock_collector()
        hook.attach_to_collector(mock)
        assert hook._collector is mock

    def test_detach_removes_collector(self):
        """detach() clears both _collector and _server_url."""
        hook = OrchestratorHook()
        mock = _make_mock_collector()
        hook.attach_to_collector(mock)
        hook.attach_to_server("http://localhost:8080")
        hook.detach()
        assert hook._collector is None
        assert hook._server_url is None

    def test_attach_none_detaches_collector(self):
        """Passing None to attach_to_collector detaches."""
        hook = OrchestratorHook()
        mock = _make_mock_collector()
        hook.attach_to_collector(mock)
        hook.attach_to_collector(None)
        assert hook._collector is None

    def test_attach_to_server_sets_url(self):
        """attach_to_server stores the URL (trailing slash stripped)."""
        hook = OrchestratorHook()
        hook.attach_to_server("http://example.com/")
        assert hook._server_url == "http://example.com"

    def test_events_still_stored_after_detach(self):
        """In-memory events are preserved after detaching."""
        hook = OrchestratorHook()
        mock = _make_mock_collector()
        hook.attach_to_collector(mock)
        hook.emit_delegation("coding", "task", "reason")
        _wait_for_events(hook, 1)
        hook.detach()
        assert len(hook.events) == 1  # still there


# ---------------------------------------------------------------------------
# 8. Collector integration
# ---------------------------------------------------------------------------

class TestCollectorIntegration:
    """Collector's _record_event_callbacks receive events from the hook."""

    def test_collector_callback_invoked_on_emit_delegation(self):
        """When a collector is attached, its registered callbacks receive the event."""
        received = []
        mock_collector = _make_mock_collector()
        mock_collector._record_event_callbacks = [received.append]

        hook = OrchestratorHook()
        hook.attach_to_collector(mock_collector)
        hook.emit_delegation("coding", "Implement feature", "Best choice")
        _wait_for_events(hook, 1)

        # Give the background thread a moment to deliver
        deadline = time.monotonic() + 2.0
        while len(received) == 0 and time.monotonic() < deadline:
            time.sleep(0.01)

        assert len(received) == 1
        event = received[0]
        assert event["agent_name"] == "coding"

    def test_collector_callback_receives_correct_session_id(self):
        """The event forwarded to the collector carries the hook's session_id."""
        received = []
        mock_collector = _make_mock_collector()
        mock_collector._record_event_callbacks = [received.append]

        sid = "session-for-test"
        hook = OrchestratorHook(session_id=sid)
        hook.attach_to_collector(mock_collector)
        hook.emit_delegation("coding", "task", "reason")

        deadline = time.monotonic() + 2.0
        while len(received) == 0 and time.monotonic() < deadline:
            time.sleep(0.01)

        assert received[0]["session_id"] == sid

    def test_real_collector_integration(self):
        """OrchestratorHook integrates with real AgentMetricsCollector."""
        import tempfile
        from pathlib import Path
        from dashboard.collector import AgentMetricsCollector

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = AgentMetricsCollector(
                project_name="test-orch-hook",
                metrics_dir=Path(tmpdir),
            )
            received = []
            collector.register_event_callback(received.append)

            hook = attach_to_collector(collector)
            hook.emit_delegation("coding", "Implement AI-172", "Best agent for coding tasks")

            deadline = time.monotonic() + 2.0
            while len(received) == 0 and time.monotonic() < deadline:
                time.sleep(0.01)

            assert len(received) == 1
            assert received[0]["agent_name"] == "coding"


# ---------------------------------------------------------------------------
# 9. Factory helpers
# ---------------------------------------------------------------------------

class TestFactoryHelpers:
    """Factory helper functions create correctly configured hook instances."""

    def test_attach_to_collector_factory(self):
        """attach_to_collector() returns a hook with collector set."""
        mock = _make_mock_collector()
        hook = attach_to_collector(mock)
        assert isinstance(hook, OrchestratorHook)
        assert hook._collector is mock

    def test_attach_to_server_factory(self):
        """attach_to_server() returns a hook with server_url set."""
        hook = attach_to_server("http://localhost:8080")
        assert isinstance(hook, OrchestratorHook)
        assert hook._server_url == "http://localhost:8080"


# ---------------------------------------------------------------------------
# 10. add_callback / remove_callback
# ---------------------------------------------------------------------------

class TestExtraCallbacks:
    """Extra in-process callbacks can be registered and removed."""

    def test_add_callback_receives_events(self):
        """add_callback registers a callable that receives each emitted event."""
        received = []
        hook = OrchestratorHook()
        hook.add_callback(received.append)
        hook.emit_delegation("coding", "task", "reason")

        deadline = time.monotonic() + 2.0
        while len(received) == 0 and time.monotonic() < deadline:
            time.sleep(0.01)

        assert len(received) == 1

    def test_remove_callback_stops_notifications(self):
        """remove_callback prevents further notifications to that callable."""
        received = []
        hook = OrchestratorHook()
        hook.add_callback(received.append)
        hook.emit_delegation("coding", "task1", "reason1")
        _wait_for_events(hook, 1)

        hook.remove_callback(received.append)
        hook.emit_delegation("coding", "task2", "reason2")
        _wait_for_events(hook, 2)

        # Give background threads a moment to settle
        time.sleep(0.1)
        # Should still be 1 (the second event was not delivered to the removed cb)
        assert len(received) == 1

    def test_add_same_callback_twice_is_idempotent(self):
        """Adding the same callback twice only adds it once."""
        cb = MagicMock()
        hook = OrchestratorHook()
        hook.add_callback(cb)
        hook.add_callback(cb)
        hook.emit_delegation("coding", "task", "reason")
        _wait_for_events(hook, 1)
        time.sleep(0.1)
        # Called exactly once (not twice due to dedup)
        assert cb.call_count == 1

    def test_remove_unregistered_callback_is_noop(self):
        """Removing a callback that was never added does not raise."""
        hook = OrchestratorHook()
        # Should not raise
        hook.remove_callback(lambda e: None)


# ---------------------------------------------------------------------------
# 11. Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    """Concurrent emit calls do not corrupt the event store."""

    def test_concurrent_emissions_all_stored(self):
        """Events emitted from multiple threads are all stored."""
        hook = OrchestratorHook()
        n = 20

        def _emit(i):
            hook.emit_delegation("coding", f"task-{i}", f"reason-{i}")

        threads = [threading.Thread(target=_emit, args=(i,)) for i in range(n)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        _wait_for_events(hook, n, timeout=5.0)
        assert len(hook.events) == n


# ---------------------------------------------------------------------------
# 12. emit_reasoning()
# ---------------------------------------------------------------------------

class TestEmitReasoning:
    """emit_reasoning() stores the correct event."""

    def test_emit_reasoning_stores_event(self):
        """emit_reasoning creates a stored event."""
        hook = OrchestratorHook()
        hook.emit_reasoning("Analysing project state")
        _wait_for_events(hook, 1)
        assert len(hook.events) == 1

    def test_emit_reasoning_event_type_is_reasoning(self):
        """The _event_type field is 'reasoning'."""
        hook = OrchestratorHook()
        hook.emit_reasoning("Thinking about next steps")
        _wait_for_events(hook, 1)
        assert hook.events[0]["_event_type"] == "reasoning"

    def test_emit_reasoning_agent_name_is_orchestrator(self):
        """Reasoning events are attributed to the 'orchestrator' agent."""
        hook = OrchestratorHook()
        hook.emit_reasoning("Some reasoning")
        _wait_for_events(hook, 1)
        assert hook.events[0]["agent_name"] == "orchestrator"

    def test_emit_reasoning_with_context(self):
        """Context dict is accepted and stored without raising."""
        hook = OrchestratorHook()
        hook.emit_reasoning("Choosing agent", context={"phase": "selection", "complexity": "HIGH"})
        _wait_for_events(hook, 1)
        assert len(hook.events) == 1


if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v", "--tb=short", "-s"])
