"""
Comprehensive tests for UIOrchestrator LLM-based component selection (KAN-84)

Tests the full orchestration pipeline: event handling, deterministic fallback,
LLM-based decision making, component generation, and edge cases.
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from a2ui_generator import A2UIGenerator
from ui_orchestrator import DEFAULT_EVENT_MAPPING, UIOrchestrator


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _make_event(event_type: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Build a minimal DashboardEvent dict."""
    return {"type": event_type, "payload": payload or {}}


def _component_types(message: Dict[str, Any]) -> List[str]:
    """Extract the list of component type strings from a surfaceUpdate."""
    return [c["type"] for c in message["components"]]


def _component_ids(message: Dict[str, Any]) -> List[str]:
    """Extract the list of component id strings from a surfaceUpdate."""
    return [c["id"] for c in message["components"]]


# ---------------------------------------------------------------------------
#  1-7  Deterministic fallback: correct components per event type
# ---------------------------------------------------------------------------

class TestFallbackComponentSelection:
    """Verify that the deterministic fallback produces the right component
    set for every supported event type."""

    @pytest.fixture
    def orchestrator(self) -> UIOrchestrator:
        """Orchestrator with LLM disabled (pure fallback)."""
        return UIOrchestrator(use_llm=False)

    # 1. task_started -> TaskCard + ActivityItem
    @pytest.mark.asyncio
    async def test_task_started_generates_task_card_and_activity(self, orchestrator):
        event = _make_event("task_started", {
            "task_id": "t-1",
            "title": "Setup database",
            "status": "in_progress",
        })
        msg = await orchestrator.handle_event(event)
        types = _component_types(msg)
        assert "a2ui.TaskCard" in types
        assert "a2ui.ActivityItem" in types
        assert len(types) == 2

    # 2. decision_needed -> DecisionCard + ActivityItem
    @pytest.mark.asyncio
    async def test_decision_needed_generates_decision_card_and_activity(self, orchestrator):
        event = _make_event("decision_needed", {
            "decision_id": "d-1",
            "question": "Which ORM?",
            "options": [{"label": "SQLAlchemy"}, {"label": "Tortoise"}],
        })
        msg = await orchestrator.handle_event(event)
        types = _component_types(msg)
        assert "a2ui.DecisionCard" in types
        assert "a2ui.ActivityItem" in types
        assert len(types) == 2

    # 3. approval_needed -> ApprovalCard + ActivityItem
    @pytest.mark.asyncio
    async def test_approval_needed_generates_approval_card_and_activity(self, orchestrator):
        event = _make_event("approval_needed", {
            "approval_id": "a-1",
            "action": "Delete staging DB",
            "risk_level": "high",
            "context": "Needed to reset schema",
        })
        msg = await orchestrator.handle_event(event)
        types = _component_types(msg)
        assert "a2ui.ApprovalCard" in types
        assert "a2ui.ActivityItem" in types
        assert len(types) == 2

    # 4. error -> ErrorCard + ActivityItem
    @pytest.mark.asyncio
    async def test_error_generates_error_card_and_activity(self, orchestrator):
        event = _make_event("error", {
            "error_id": "e-1",
            "message": "Connection refused",
            "details": "Port 5432 unreachable",
        })
        msg = await orchestrator.handle_event(event)
        types = _component_types(msg)
        assert "a2ui.ErrorCard" in types
        assert "a2ui.ActivityItem" in types
        assert len(types) == 2

    # 5. milestone -> MilestoneCard + ProgressRing + ActivityItem
    @pytest.mark.asyncio
    async def test_milestone_generates_milestone_progress_and_activity(self, orchestrator):
        event = _make_event("milestone", {
            "title": "Phase 1 complete",
            "summary": "All core features implemented",
            "tasks_completed": 10,
            "percentage": 50,
            "total_tasks": 20,
        })
        msg = await orchestrator.handle_event(event)
        types = _component_types(msg)
        assert "a2ui.MilestoneCard" in types
        assert "a2ui.ProgressRing" in types
        assert "a2ui.ActivityItem" in types
        assert len(types) == 3

    # 6. file_changed -> FileTree + ActivityItem
    @pytest.mark.asyncio
    async def test_file_changed_generates_file_tree_and_activity(self, orchestrator):
        event = _make_event("file_changed", {
            "files": [{"path": "src/main.py", "status": "modified"}],
            "active_file": "src/main.py",
            "modified_files": ["src/main.py"],
            "message": "Modified main.py",
        })
        msg = await orchestrator.handle_event(event)
        types = _component_types(msg)
        assert "a2ui.FileTree" in types
        assert "a2ui.ActivityItem" in types
        assert len(types) == 2

    # 7. test_results -> TestResults + ActivityItem
    @pytest.mark.asyncio
    async def test_test_results_generates_test_results_and_activity(self, orchestrator):
        event = _make_event("test_results", {
            "tests": [{"name": "test_login", "passed": True}],
            "test_status": "completed",
            "coverage": {"lines": 87.5},
            "message": "All tests pass",
        })
        msg = await orchestrator.handle_event(event)
        types = _component_types(msg)
        assert "a2ui.TestResults" in types
        assert "a2ui.ActivityItem" in types
        assert len(types) == 2


# ---------------------------------------------------------------------------
#  8  Unknown event type falls back to ActivityItem
# ---------------------------------------------------------------------------

class TestUnknownEventFallback:

    @pytest.mark.asyncio
    async def test_unknown_event_type_falls_back_to_activity_item(self):
        orch = UIOrchestrator(use_llm=False)
        event = _make_event("totally_unknown_event", {"message": "hello"})
        msg = await orch.handle_event(event)
        types = _component_types(msg)
        assert types == ["a2ui.ActivityItem"]


# ---------------------------------------------------------------------------
#  9  surface_update message format
# ---------------------------------------------------------------------------

class TestSurfaceUpdateFormat:

    @pytest.mark.asyncio
    async def test_surface_update_has_required_top_level_fields(self):
        orch = UIOrchestrator(use_llm=False)
        event = _make_event("task_started", {"title": "Init"})
        msg = await orch.handle_event(event)

        assert msg["messageType"] == "surfaceUpdate"
        assert isinstance(msg["components"], list)
        assert "timestamp" in msg
        # Timestamp should be an ISO-format string
        assert isinstance(msg["timestamp"], str)
        assert "T" in msg["timestamp"]


# ---------------------------------------------------------------------------
#  10  Generated components have required fields (type, id, props)
# ---------------------------------------------------------------------------

class TestComponentRequiredFields:

    @pytest.mark.asyncio
    async def test_all_components_have_type_id_props(self):
        orch = UIOrchestrator(use_llm=False)
        for event_type in DEFAULT_EVENT_MAPPING:
            event = _make_event(event_type, {
                "title": "Test",
                "message": "Test message",
                "task_id": f"task-{event_type}",
                "decision_id": f"dec-{event_type}",
                "approval_id": f"appr-{event_type}",
                "error_id": f"err-{event_type}",
                "question": "Q?",
                "options": [],
                "action": "deploy",
                "risk_level": "low",
                "context": "ctx",
                "files": [],
                "tests": [],
                "test_status": "completed",
            })
            msg = await orch.handle_event(event)
            for comp in msg["components"]:
                assert "type" in comp, f"Missing 'type' in component for {event_type}"
                assert "id" in comp, f"Missing 'id' in component for {event_type}"
                assert "props" in comp, f"Missing 'props' in component for {event_type}"
                assert isinstance(comp["type"], str)
                assert isinstance(comp["id"], str)
                assert isinstance(comp["props"], dict)


# ---------------------------------------------------------------------------
#  11  Rapid sequential events
# ---------------------------------------------------------------------------

class TestRapidSequentialEvents:

    @pytest.mark.asyncio
    async def test_rapid_sequential_events_do_not_error(self):
        orch = UIOrchestrator(use_llm=False)
        events = [
            _make_event("task_started", {"title": f"Task {i}"})
            for i in range(50)
        ]
        messages = []
        for ev in events:
            msg = await orch.handle_event(ev)
            messages.append(msg)

        assert len(messages) == 50
        # Each message should be well-formed
        for msg in messages:
            assert msg["messageType"] == "surfaceUpdate"
            assert len(msg["components"]) > 0

    @pytest.mark.asyncio
    async def test_event_count_increments_correctly(self):
        orch = UIOrchestrator(use_llm=False)
        for i in range(5):
            await orch.handle_event(_make_event("activity", {"message": "ping"}))
        assert orch._event_count == 5


# ---------------------------------------------------------------------------
#  12  Fallback when LLM fails (mock httpx to raise error)
# ---------------------------------------------------------------------------

class TestLLMFailureFallback:

    @pytest.mark.asyncio
    async def test_llm_http_error_falls_back_to_deterministic(self):
        """When the LLM HTTP call raises, the orchestrator should silently
        fall back to the deterministic mapping."""
        orch = UIOrchestrator(use_llm=True)

        # Mock httpx.AsyncClient to raise an exception on post
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient", return_value=mock_client):
                event = _make_event("error", {
                    "error_id": "e-fallback",
                    "message": "boom",
                })
                msg = await orch.handle_event(event)

        types = _component_types(msg)
        assert "a2ui.ErrorCard" in types
        assert "a2ui.ActivityItem" in types

    @pytest.mark.asyncio
    async def test_llm_returns_unparseable_json_falls_back(self):
        """When the LLM returns gibberish instead of a JSON array, fallback
        should kick in."""
        orch = UIOrchestrator(use_llm=True)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "I have no idea what to do."}}]
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient", return_value=mock_client):
                event = _make_event("task_started", {"title": "Build server"})
                msg = await orch.handle_event(event)

        types = _component_types(msg)
        # Should fall back to deterministic mapping for task_started
        assert "a2ui.TaskCard" in types
        assert "a2ui.ActivityItem" in types

    @pytest.mark.asyncio
    async def test_llm_no_api_key_falls_back(self):
        """When OPENROUTER_API_KEY is missing, _llm_decide returns None and
        the fallback is used."""
        orch = UIOrchestrator(use_llm=True)

        with patch.dict("os.environ", {}, clear=True):
            event = _make_event("milestone", {
                "title": "Phase 2",
                "summary": "Tests done",
                "tasks_completed": 5,
            })
            msg = await orch.handle_event(event)

        types = _component_types(msg)
        assert "a2ui.MilestoneCard" in types
        assert "a2ui.ProgressRing" in types
        assert "a2ui.ActivityItem" in types

    @pytest.mark.asyncio
    async def test_llm_success_uses_llm_components(self):
        """When the LLM returns a valid JSON array, those components are used."""
        orch = UIOrchestrator(use_llm=True)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": '["ErrorCard", "ActivityItem"]'
                }
            }]
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            with patch("httpx.AsyncClient", return_value=mock_client):
                event = _make_event("error", {
                    "error_id": "e-llm",
                    "message": "LLM chose these",
                })
                msg = await orch.handle_event(event)

        types = _component_types(msg)
        assert "a2ui.ErrorCard" in types
        assert "a2ui.ActivityItem" in types


# ---------------------------------------------------------------------------
#  13  _map_event_type correctness
# ---------------------------------------------------------------------------

class TestMapEventType:

    def test_all_known_event_types_mapped(self):
        expected = {
            "task_started": "file",
            "task_completed": "milestone",
            "decision_needed": "decision",
            "approval_needed": "approval",
            "error": "error",
            "milestone": "milestone",
            "file_changed": "file",
            "test_results": "test",
            "activity": "command",
        }
        for event_type, expected_mapped in expected.items():
            assert UIOrchestrator._map_event_type(event_type) == expected_mapped, (
                f"_map_event_type({event_type!r}) should be {expected_mapped!r}"
            )

    def test_unknown_event_type_maps_to_command(self):
        assert UIOrchestrator._map_event_type("nonexistent") == "command"
        assert UIOrchestrator._map_event_type("") == "command"

    @pytest.mark.asyncio
    async def test_activity_item_event_type_matches_mapping(self):
        """Ensure the ActivityItem produced for each event type carries the
        correct eventType prop as defined by _map_event_type."""
        orch = UIOrchestrator(use_llm=False)
        for event_type in DEFAULT_EVENT_MAPPING:
            event = _make_event(event_type, {
                "title": "x", "message": "x",
                "task_id": "t", "decision_id": "d", "approval_id": "a",
                "error_id": "e", "question": "q", "options": [],
                "action": "act", "risk_level": "low", "context": "c",
                "files": [], "tests": [], "test_status": "ok",
            })
            msg = await orch.handle_event(event)
            activity = [c for c in msg["components"] if c["type"] == "a2ui.ActivityItem"]
            assert len(activity) == 1
            expected = UIOrchestrator._map_event_type(event_type)
            assert activity[0]["props"]["eventType"] == expected


# ---------------------------------------------------------------------------
#  14  Empty payload handling
# ---------------------------------------------------------------------------

class TestEmptyPayload:

    @pytest.mark.asyncio
    async def test_empty_payload_task_started(self):
        orch = UIOrchestrator(use_llm=False)
        event = _make_event("task_started", {})
        msg = await orch.handle_event(event)
        types = _component_types(msg)
        assert "a2ui.TaskCard" in types
        assert "a2ui.ActivityItem" in types

    @pytest.mark.asyncio
    async def test_missing_payload_key(self):
        orch = UIOrchestrator(use_llm=False)
        event = {"type": "error"}  # no 'payload' key at all
        msg = await orch.handle_event(event)
        types = _component_types(msg)
        assert "a2ui.ErrorCard" in types

    @pytest.mark.asyncio
    async def test_empty_payload_uses_defaults(self):
        """Components should populate sensible defaults when payload is empty."""
        orch = UIOrchestrator(use_llm=False)
        event = _make_event("decision_needed", {})
        msg = await orch.handle_event(event)
        decision = [c for c in msg["components"] if c["type"] == "a2ui.DecisionCard"]
        assert len(decision) == 1
        props = decision[0]["props"]
        # Should have the default question
        assert props["question"] == "Decision needed"
        assert isinstance(props["options"], list)

    @pytest.mark.asyncio
    async def test_missing_type_defaults_to_activity(self):
        """When the event dict has no 'type' key, it should default to 'activity'."""
        orch = UIOrchestrator(use_llm=False)
        event = {"payload": {"message": "just a log"}}
        msg = await orch.handle_event(event)
        types = _component_types(msg)
        assert types == ["a2ui.ActivityItem"]


# ---------------------------------------------------------------------------
#  15  Component IDs are unique across events
# ---------------------------------------------------------------------------

class TestComponentIdUniqueness:

    @pytest.mark.asyncio
    async def test_ids_unique_within_single_event(self):
        orch = UIOrchestrator(use_llm=False)
        event = _make_event("milestone", {
            "title": "Done",
            "summary": "All done",
            "tasks_completed": 5,
            "percentage": 100,
            "total_tasks": 5,
        })
        msg = await orch.handle_event(event)
        ids = _component_ids(msg)
        assert len(ids) == len(set(ids)), f"Duplicate IDs within event: {ids}"

    @pytest.mark.asyncio
    async def test_ids_unique_across_multiple_events(self):
        orch = UIOrchestrator(use_llm=False)
        all_ids: list[str] = []

        for i in range(10):
            event = _make_event("task_started", {
                "task_id": f"task-{i}",
                "title": f"Task {i}",
            })
            msg = await orch.handle_event(event)
            all_ids.extend(_component_ids(msg))

        assert len(all_ids) == len(set(all_ids)), (
            f"Duplicate component IDs across events: "
            f"{[x for x in all_ids if all_ids.count(x) > 1]}"
        )

    @pytest.mark.asyncio
    async def test_auto_generated_ids_are_unique(self):
        """When no explicit id is in the payload, auto-generated IDs based on
        _event_count should still be unique."""
        orch = UIOrchestrator(use_llm=False)
        all_ids: list[str] = []

        for _ in range(20):
            event = _make_event("error", {"message": "something broke"})
            msg = await orch.handle_event(event)
            all_ids.extend(_component_ids(msg))

        assert len(all_ids) == len(set(all_ids)), "Auto-generated IDs must be unique"


# ---------------------------------------------------------------------------
#  Additional edge-case and integration tests
# ---------------------------------------------------------------------------

class TestOrchestratorIntegration:

    @pytest.mark.asyncio
    async def test_task_completed_generates_three_components(self):
        orch = UIOrchestrator(use_llm=False)
        event = _make_event("task_completed", {
            "task_id": "t-done",
            "title": "All tests pass",
            "status": "completed",
            "percentage": 100,
            "tasks_completed": 10,
            "total_tasks": 10,
        })
        msg = await orch.handle_event(event)
        types = _component_types(msg)
        assert "a2ui.TaskCard" in types
        assert "a2ui.ProgressRing" in types
        assert "a2ui.ActivityItem" in types
        assert len(types) == 3

    @pytest.mark.asyncio
    async def test_project_state_does_not_break_fallback(self):
        """Passing project_state to handle_event should not raise."""
        orch = UIOrchestrator(use_llm=False)
        event = _make_event("task_started", {"title": "Build"})
        state = {"totalTasks": 20, "completedTasks": 5}
        msg = await orch.handle_event(event, project_state=state)
        assert msg["messageType"] == "surfaceUpdate"

    def test_default_event_mapping_covers_all_key_types(self):
        """Ensure the DEFAULT_EVENT_MAPPING has entries for all the event
        types the dashboard uses."""
        required = {
            "task_started", "task_completed", "decision_needed",
            "approval_needed", "error", "milestone", "file_changed",
            "test_results", "activity",
        }
        assert required.issubset(set(DEFAULT_EVENT_MAPPING.keys()))

    @pytest.mark.asyncio
    async def test_generate_single_returns_none_for_unknown_component(self):
        orch = UIOrchestrator(use_llm=False)
        result = orch._generate_single("BogusWidget", "activity", {}, "evt-99")
        assert result is None

    def test_build_llm_prompt_includes_event_info(self):
        orch = UIOrchestrator(use_llm=True)
        prompt = orch._build_llm_prompt(
            "task_started",
            {"title": "Deploy app"},
            {"totalTasks": 10, "completedTasks": 3},
        )
        assert "task_started" in prompt
        assert "Deploy app" in prompt
        assert "3/10" in prompt
        assert "TaskCard" in prompt
        assert "ActivityItem" in prompt

    def test_build_llm_prompt_without_project_state(self):
        orch = UIOrchestrator(use_llm=True)
        prompt = orch._build_llm_prompt("error", {"message": "fail"}, None)
        assert "error" in prompt
        assert "Project state:" not in prompt

    @pytest.mark.asyncio
    async def test_parse_llm_response_valid_json_array(self):
        orch = UIOrchestrator(use_llm=True)
        # Simulate the full flow through _parse_llm_response
        content = 'Here is the answer: ["TaskCard", "ActivityItem"]'
        result = orch._parse_llm_response(content, "task_started", {"title": "x"})
        assert result is not None
        types = [c["type"] for c in result]
        assert "a2ui.TaskCard" in types
        assert "a2ui.ActivityItem" in types

    @pytest.mark.asyncio
    async def test_parse_llm_response_no_json_returns_none(self):
        orch = UIOrchestrator(use_llm=True)
        result = orch._parse_llm_response("no json here", "error", {"message": "x"})
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
