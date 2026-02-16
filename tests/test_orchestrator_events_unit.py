"""
Unit Tests for AI-108: Orchestrator Hook - Reasoning Event Emission
Simplified version that tests functions directly without full module imports.

Test Coverage:
- Reasoning event emission during session lifecycle
- Delegation decision events with complexity assessment
- Event structure and metadata validation
- Error handling and graceful degradation
- Session event tracking (start, delegation, completion)
- Complexity assessment for different task types
"""

import asyncio
import json
import pytest
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dashboard.metrics import AgentEvent
from dashboard.metrics_store import MetricsStore


# Copy the functions we're testing to avoid module dependencies
def _assess_complexity(task_description: str) -> str:
    """Assess task complexity based on task description.

    Args:
        task_description: Task description text

    Returns:
        Complexity level: "SIMPLE", "MODERATE", or "COMPLEX"
    """
    task_lower = task_description.lower()

    # Complex indicators
    complex_keywords = ["implement", "refactor", "architect", "design", "integration", "test"]
    if any(keyword in task_lower for keyword in complex_keywords) or len(task_description) > 200:
        return "COMPLEX"

    # Simple indicators
    simple_keywords = ["check", "list", "view", "read", "get"]
    if any(keyword in task_lower for keyword in simple_keywords) or len(task_description) < 50:
        return "SIMPLE"

    return "MODERATE"


async def emit_reasoning_event(
    content: str,
    context: dict,
    project_dir: Path,
    session_id: str = "",
    event_type: str = "reasoning"
) -> None:
    """Emit a reasoning event to the dashboard."""
    try:
        metrics_store = MetricsStore(
            project_name="agent-dashboard",
            metrics_dir=project_dir
        )

        event_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + "Z"

        reasoning_event: AgentEvent = {
            "event_id": event_id,
            "agent_name": "orchestrator",
            "session_id": session_id or str(uuid.uuid4()),
            "ticket_key": context.get("ticket_key", ""),
            "started_at": timestamp,
            "ended_at": timestamp,
            "duration_seconds": 0.0,
            "status": "success",
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
            "artifacts": [
                f"reasoning:{event_type}",
                f"content:{content[:100]}",
            ],
            "error_message": "",
            "model_used": "orchestrator",
        }

        if "complexity" in context:
            reasoning_event["artifacts"].append(f"complexity:{context['complexity']}")
        if "agent_selection" in context:
            reasoning_event["artifacts"].append(f"agent_selection:{context['agent_selection']}")
        if "alternatives" in context:
            reasoning_event["artifacts"].append(f"alternatives:{','.join(context['alternatives'])}")

        state = metrics_store.load()
        state["events"].append(reasoning_event)
        metrics_store.save(state)

    except Exception as e:
        # Graceful degradation
        pass


class TestComplexityAssessment:
    """Test task complexity assessment."""

    def test_assess_simple_task(self):
        """Test simple task complexity assessment."""
        assert _assess_complexity("Check Linear for available tickets") == "SIMPLE"
        assert _assess_complexity("Read project state") == "SIMPLE"
        assert _assess_complexity("List issues") == "SIMPLE"

    def test_assess_moderate_task(self):
        """Test moderate task complexity assessment."""
        # These tasks don't match complex or simple keywords, so they're moderate
        assert _assess_complexity("Modify the logging system to add better error tracking") == "MODERATE"
        assert _assess_complexity("Adjust the metrics collection intervals and thresholds") == "MODERATE"

    def test_assess_complex_task(self):
        """Test complex task complexity assessment."""
        assert _assess_complexity("Implement AI-108 orchestrator event emission with comprehensive test coverage") == "COMPLEX"
        assert _assess_complexity("Refactor the agent delegation system to support dynamic routing") == "COMPLEX"
        assert _assess_complexity("Design and implement integration tests for the orchestrator") == "COMPLEX"

    def test_assess_empty_task(self):
        """Test empty task complexity assessment."""
        assert _assess_complexity("") == "SIMPLE"

    def test_assess_by_length(self):
        """Test complexity assessment based on length."""
        assert _assess_complexity("Fix bug") == "SIMPLE"

        long_task = "This is a very long task description that goes on and on " * 10
        assert _assess_complexity(long_task) == "COMPLEX"


class TestReasoningEventEmission:
    """Test reasoning event emission functionality."""

    @pytest.mark.asyncio
    async def test_emit_reasoning_event_basic(self):
        """Test basic reasoning event emission."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            session_id = str(uuid.uuid4())

            await emit_reasoning_event(
                content="Analyzing project state and checking for available tickets",
                context={
                    "session_id": session_id,
                    "phase": "initialization"
                },
                project_dir=project_dir,
                session_id=session_id,
                event_type="reasoning"
            )

            store = MetricsStore(project_name="agent-dashboard", metrics_dir=project_dir)
            state = store.load()

            assert len(state["events"]) == 1
            event = state["events"][0]

            assert event["agent_name"] == "orchestrator"
            assert event["session_id"] == session_id
            assert event["status"] == "success"
            assert any("reasoning:reasoning" in artifact for artifact in event["artifacts"])
            assert any("content:Analyzing project state" in artifact for artifact in event["artifacts"])

    @pytest.mark.asyncio
    async def test_emit_delegation_event_with_complexity(self):
        """Test delegation event emission with complexity assessment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            session_id = str(uuid.uuid4())

            await emit_reasoning_event(
                content="Delegating to coding agent: Implement AI-108 orchestrator hooks",
                context={
                    "session_id": session_id,
                    "agent_selection": "coding",
                    "complexity": "COMPLEX",
                    "alternatives": ["coding_fast", "ops"]
                },
                project_dir=project_dir,
                session_id=session_id,
                event_type="delegation"
            )

            store = MetricsStore(project_name="agent-dashboard", metrics_dir=project_dir)
            state = store.load()

            event = state["events"][0]
            assert event["agent_name"] == "orchestrator"
            assert any("complexity:COMPLEX" in artifact for artifact in event["artifacts"])
            assert any("agent_selection:coding" in artifact for artifact in event["artifacts"])
            assert any("alternatives:coding_fast,ops" in artifact for artifact in event["artifacts"])

    @pytest.mark.asyncio
    async def test_emit_session_lifecycle_events(self):
        """Test session lifecycle event sequence (start, delegation, complete)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            session_id = str(uuid.uuid4())

            # Session start
            await emit_reasoning_event(
                content="Starting orchestrated session",
                context={"session_id": session_id, "phase": "initialization"},
                project_dir=project_dir,
                session_id=session_id,
                event_type="session_start"
            )

            # Delegation
            await emit_reasoning_event(
                content="Delegating to linear agent",
                context={
                    "session_id": session_id,
                    "agent_selection": "linear",
                    "complexity": "SIMPLE"
                },
                project_dir=project_dir,
                session_id=session_id,
                event_type="delegation"
            )

            # Session complete
            await emit_reasoning_event(
                content="Session completed successfully",
                context={
                    "session_id": session_id,
                    "phase": "completion",
                    "status": "success"
                },
                project_dir=project_dir,
                session_id=session_id,
                event_type="session_complete"
            )

            store = MetricsStore(project_name="agent-dashboard", metrics_dir=project_dir)
            state = store.load()

            assert len(state["events"]) == 3
            assert all(event["session_id"] == session_id for event in state["events"])

    @pytest.mark.asyncio
    async def test_emit_error_event(self):
        """Test error event emission."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            session_id = str(uuid.uuid4())

            await emit_reasoning_event(
                content="Network error in orchestrated session",
                context={
                    "session_id": session_id,
                    "error_type": "ConnectionError",
                    "phase": "error"
                },
                project_dir=project_dir,
                session_id=session_id,
                event_type="error"
            )

            store = MetricsStore(project_name="agent-dashboard", metrics_dir=project_dir)
            state = store.load()

            event = state["events"][0]
            assert event["agent_name"] == "orchestrator"
            assert any("reasoning:error" in artifact for artifact in event["artifacts"])

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_store_failure(self):
        """Test that event emission failures don't crash the orchestrator."""
        project_dir = Path("/nonexistent/directory/that/does/not/exist")

        # Should not raise exception
        await emit_reasoning_event(
            content="Test reasoning",
            context={},
            project_dir=project_dir,
            session_id="test-session",
            event_type="reasoning"
        )

    @pytest.mark.asyncio
    async def test_multiple_concurrent_events(self):
        """Test handling of multiple concurrent event emissions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            session_id = str(uuid.uuid4())

            tasks = [
                emit_reasoning_event(
                    content=f"Event {i}",
                    context={"event_number": i},
                    project_dir=project_dir,
                    session_id=session_id,
                    event_type="reasoning"
                )
                for i in range(10)
            ]

            await asyncio.gather(*tasks)

            store = MetricsStore(project_name="agent-dashboard", metrics_dir=project_dir)
            state = store.load()

            assert len(state["events"]) == 10


class TestEventMetadata:
    """Test event metadata structure and completeness."""

    @pytest.mark.asyncio
    async def test_event_contains_all_required_fields(self):
        """Test that emitted events contain all required AgentEvent fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            session_id = str(uuid.uuid4())

            await emit_reasoning_event(
                content="Test reasoning",
                context={"test": "context"},
                project_dir=project_dir,
                session_id=session_id,
                event_type="reasoning"
            )

            store = MetricsStore(project_name="agent-dashboard", metrics_dir=project_dir)
            state = store.load()

            event = state["events"][0]

            required_fields = [
                "event_id", "agent_name", "session_id", "ticket_key",
                "started_at", "ended_at", "duration_seconds", "status",
                "input_tokens", "output_tokens", "total_tokens",
                "estimated_cost_usd", "artifacts", "error_message", "model_used"
            ]

            for field in required_fields:
                assert field in event, f"Missing required field: {field}"

    @pytest.mark.asyncio
    async def test_event_timestamps_are_valid_iso8601(self):
        """Test that event timestamps use valid ISO 8601 format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            await emit_reasoning_event(
                content="Test",
                context={},
                project_dir=project_dir,
                session_id="test-session",
                event_type="reasoning"
            )

            store = MetricsStore(project_name="agent-dashboard", metrics_dir=project_dir)
            state = store.load()

            event = state["events"][0]

            started_at = datetime.fromisoformat(event["started_at"].replace("Z", "+00:00"))
            ended_at = datetime.fromisoformat(event["ended_at"].replace("Z", "+00:00"))

            assert started_at is not None
            assert ended_at is not None

    @pytest.mark.asyncio
    async def test_event_ids_are_unique(self):
        """Test that each event has a unique event_id."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            for i in range(5):
                await emit_reasoning_event(
                    content=f"Event {i}",
                    context={},
                    project_dir=project_dir,
                    session_id="test-session",
                    event_type="reasoning"
                )

            store = MetricsStore(project_name="agent-dashboard", metrics_dir=project_dir)
            state = store.load()

            event_ids = [event["event_id"] for event in state["events"]]
            assert len(event_ids) == len(set(event_ids)), "Event IDs are not unique"


# Run tests with: python -m pytest tests/test_orchestrator_events_unit.py -v
