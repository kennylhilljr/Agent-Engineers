"""Tests for orchestrator.py delegation tracking instrumentation.

This module tests the integration between orchestrator.py's run_orchestrated_session()
and the AgentMetricsCollector, verifying that:
- Task tool delegations are detected and tracked
- Agent names and ticket keys are extracted correctly
- Delegation events are recorded with proper status
- Token attribution works correctly
- Timing is captured accurately
- Errors are handled gracefully
"""

import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_metrics_collector import AgentMetricsCollector
from agents.orchestrator import run_orchestrated_session
from claude_agent_sdk import (
    AssistantMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)


class TestDelegationDetection:
    """Test detection of Task tool usage in orchestrator."""

    @pytest.mark.asyncio
    async def test_task_tool_delegation_detected(self):
        """Test that Task tool usage is detected and tracked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            metrics_dir = project_dir

            # Create collector
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=metrics_dir
            )

            # Start session
            session_id = collector.start_session(session_type="continuation")

            # Mock Claude SDK client
            mock_client = MagicMock()
            mock_client.query = AsyncMock()

            # Create mock Task tool usage
            task_tool_use = ToolUseBlock(
                type="tool_use",
                id="task_123",
                name="Task",
                input={"agent": "coding", "task": "Work on AI-51: Implement feature"}
            )

            # Create mock response stream
            async def mock_receive_response():
                # First yield: Assistant uses Task tool
                yield AssistantMessage(
                    type="message",
                    role="assistant",
                    content=[
                        TextBlock(type="text", text="I'll delegate to the coding agent."),
                        task_tool_use
                    ]
                )

                # Second yield: Tool result
                yield UserMessage(
                    type="message",
                    role="user",
                    content=[
                        ToolResultBlock(
                            type="tool_result",
                            tool_use_id="task_123",
                            content="Delegation completed successfully",
                            is_error=False
                        )
                    ]
                )

            mock_client.receive_response = mock_receive_response

            # Run orchestrated session
            with mock_client:
                result = await run_orchestrated_session(
                    client=mock_client,
                    project_dir=project_dir,
                    session_id=session_id,
                    metrics_collector=collector
                )

            # End session
            collector.end_session(session_id, status="complete")

            # Verify delegation was tracked
            state = collector.get_state()
            assert len(state["events"]) == 1

            event = state["events"][0]
            assert event["agent_name"] == "coding"
            assert event["ticket_key"] == "AI-51"
            assert event["status"] == "success"
            assert event["session_id"] == session_id

    @pytest.mark.asyncio
    async def test_multiple_delegations_tracked(self):
        """Test that multiple Task tool delegations are tracked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            metrics_dir = project_dir

            # Create collector
            collector = AgentMetricsCollector(
                project_name="test-project",
                metrics_dir=metrics_dir
            )

            session_id = collector.start_session(session_type="continuation")

            # Mock client
            mock_client = MagicMock()
            mock_client.query = AsyncMock()

            # Create multiple Task tool uses
            async def mock_receive_response():
                # First delegation: coding agent
                yield AssistantMessage(
                    type="message",
                    role="assistant",
                    content=[
                        ToolUseBlock(
                            type="tool_use",
                            id="task_1",
                            name="Task",
                            input={"agent": "coding", "task": "Work on AI-51"}
                        )
                    ]
                )
                yield UserMessage(
                    type="message",
                    role="user",
                    content=[
                        ToolResultBlock(
                            type="tool_result",
                            tool_use_id="task_1",
                            content="Done",
                            is_error=False
                        )
                    ]
                )

                # Second delegation: github agent
                yield AssistantMessage(
                    type="message",
                    role="assistant",
                    content=[
                        ToolUseBlock(
                            type="tool_use",
                            id="task_2",
                            name="Task",
                            input={"agent": "github", "task": "Create PR for AI-51"}
                        )
                    ]
                )
                yield UserMessage(
                    type="message",
                    role="user",
                    content=[
                        ToolResultBlock(
                            type="tool_result",
                            tool_use_id="task_2",
                            content="PR created",
                            is_error=False
                        )
                    ]
                )

            mock_client.receive_response = mock_receive_response

            with mock_client:
                result = await run_orchestrated_session(
                    client=mock_client,
                    project_dir=project_dir,
                    session_id=session_id,
                    metrics_collector=collector
                )

            collector.end_session(session_id, status="complete")

            # Verify both delegations tracked
            state = collector.get_state()
            assert len(state["events"]) == 2

            # Check first delegation
            assert state["events"][0]["agent_name"] == "coding"
            assert state["events"][0]["ticket_key"] == "AI-51"

            # Check second delegation
            assert state["events"][1]["agent_name"] == "github"
            assert state["events"][1]["ticket_key"] == "AI-51"


class TestTicketKeyExtraction:
    """Test extraction of ticket keys from task descriptions."""

    @pytest.mark.asyncio
    async def test_ticket_key_extraction_from_task(self):
        """Test that ticket keys are correctly extracted from task descriptions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            collector = AgentMetricsCollector("test-project", Path(tmpdir))
            session_id = collector.start_session()

            mock_client = MagicMock()
            mock_client.query = AsyncMock()

            # Test various task description formats
            test_cases = [
                ("Work on AI-51: Implement feature", "AI-51"),
                ("AI-51 needs implementation", "AI-51"),
                ("Implement AI-123", "AI-123"),
                ("Fix bug in AI-999", "AI-999"),
            ]

            for task_desc, expected_ticket in test_cases:
                async def mock_receive_response():
                    yield AssistantMessage(
                        type="message",
                        role="assistant",
                        content=[
                            ToolUseBlock(
                                type="tool_use",
                                id=f"task_{expected_ticket}",
                                name="Task",
                                input={"agent": "coding", "task": task_desc}
                            )
                        ]
                    )
                    yield UserMessage(
                        type="message",
                        role="user",
                        content=[
                            ToolResultBlock(
                                type="tool_result",
                                tool_use_id=f"task_{expected_ticket}",
                                content="Done",
                                is_error=False
                            )
                        ]
                    )

                mock_client.receive_response = mock_receive_response

                with mock_client:
                    await run_orchestrated_session(
                        client=mock_client,
                        project_dir=project_dir,
                        session_id=session_id,
                        metrics_collector=collector
                    )

            collector.end_session(session_id)

            # Verify all ticket keys extracted correctly
            state = collector.get_state()
            extracted_tickets = [event["ticket_key"] for event in state["events"]]
            expected_tickets = [ticket for _, ticket in test_cases]

            assert extracted_tickets == expected_tickets


class TestTokenAttribution:
    """Test token attribution for delegations."""

    @pytest.mark.asyncio
    async def test_delegation_records_token_counts(self):
        """Test that delegations record token counts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            collector = AgentMetricsCollector("test-project", Path(tmpdir))
            session_id = collector.start_session()

            mock_client = MagicMock()
            mock_client.query = AsyncMock()

            async def mock_receive_response():
                yield AssistantMessage(
                    type="message",
                    role="assistant",
                    content=[
                        ToolUseBlock(
                            type="tool_use",
                            id="task_1",
                            name="Task",
                            input={"agent": "coding", "task": "Work on AI-51"}
                        )
                    ]
                )
                yield UserMessage(
                    type="message",
                    role="user",
                    content=[
                        ToolResultBlock(
                            type="tool_result",
                            tool_use_id="task_1",
                            content="Done",
                            is_error=False
                        )
                    ]
                )

            mock_client.receive_response = mock_receive_response

            with mock_client:
                await run_orchestrated_session(
                    client=mock_client,
                    project_dir=project_dir,
                    session_id=session_id,
                    metrics_collector=collector
                )

            collector.end_session(session_id)

            # Verify tokens are recorded
            state = collector.get_state()
            event = state["events"][0]

            # Current implementation uses estimated tokens (500 input, 1000 output)
            assert event["input_tokens"] == 500
            assert event["output_tokens"] == 1000
            assert event["total_tokens"] == 1500

    @pytest.mark.asyncio
    async def test_session_aggregates_delegation_tokens(self):
        """Test that session totals include delegation tokens."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            collector = AgentMetricsCollector("test-project", Path(tmpdir))
            session_id = collector.start_session()

            mock_client = MagicMock()
            mock_client.query = AsyncMock()

            # Multiple delegations
            async def mock_receive_response():
                for i in range(3):
                    yield AssistantMessage(
                        type="message",
                        role="assistant",
                        content=[
                            ToolUseBlock(
                                type="tool_use",
                                id=f"task_{i}",
                                name="Task",
                                input={"agent": "coding", "task": f"Work on AI-{50+i}"}
                            )
                        ]
                    )
                    yield UserMessage(
                        type="message",
                        role="user",
                        content=[
                            ToolResultBlock(
                                type="tool_result",
                                tool_use_id=f"task_{i}",
                                content="Done",
                                is_error=False
                            )
                        ]
                    )

            mock_client.receive_response = mock_receive_response

            with mock_client:
                await run_orchestrated_session(
                    client=mock_client,
                    project_dir=project_dir,
                    session_id=session_id,
                    metrics_collector=collector
                )

            collector.end_session(session_id)

            # Verify session aggregates all delegation tokens
            state = collector.get_state()
            session = state["sessions"][0]

            # 3 delegations × 1500 tokens each = 4500 total
            assert session["total_tokens"] == 4500


class TestTimingCapture:
    """Test timing capture for delegations."""

    @pytest.mark.asyncio
    async def test_delegation_captures_timing(self):
        """Test that delegation timing is captured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            collector = AgentMetricsCollector("test-project", Path(tmpdir))
            session_id = collector.start_session()

            mock_client = MagicMock()
            mock_client.query = AsyncMock()

            async def mock_receive_response():
                yield AssistantMessage(
                    type="message",
                    role="assistant",
                    content=[
                        ToolUseBlock(
                            type="tool_use",
                            id="task_1",
                            name="Task",
                            input={"agent": "coding", "task": "Work on AI-51"}
                        )
                    ]
                )
                # Simulate delay
                import asyncio
                await asyncio.sleep(0.1)
                yield UserMessage(
                    type="message",
                    role="user",
                    content=[
                        ToolResultBlock(
                            type="tool_result",
                            tool_use_id="task_1",
                            content="Done",
                            is_error=False
                        )
                    ]
                )

            mock_client.receive_response = mock_receive_response

            with mock_client:
                await run_orchestrated_session(
                    client=mock_client,
                    project_dir=project_dir,
                    session_id=session_id,
                    metrics_collector=collector
                )

            collector.end_session(session_id)

            # Verify timing captured
            state = collector.get_state()
            event = state["events"][0]

            assert "started_at" in event
            assert "ended_at" in event
            assert "duration_seconds" in event

            # Duration should be positive and reasonable
            assert event["duration_seconds"] > 0
            assert event["duration_seconds"] < 10  # Should be well under 10s for test


class TestErrorHandling:
    """Test error handling in delegation tracking."""

    @pytest.mark.asyncio
    async def test_failed_delegation_recorded_as_error(self):
        """Test that failed delegations are recorded with error status."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            collector = AgentMetricsCollector("test-project", Path(tmpdir))
            session_id = collector.start_session()

            mock_client = MagicMock()
            mock_client.query = AsyncMock()

            async def mock_receive_response():
                yield AssistantMessage(
                    type="message",
                    role="assistant",
                    content=[
                        ToolUseBlock(
                            type="tool_use",
                            id="task_1",
                            name="Task",
                            input={"agent": "coding", "task": "Work on AI-51"}
                        )
                    ]
                )
                yield UserMessage(
                    type="message",
                    role="user",
                    content=[
                        ToolResultBlock(
                            type="tool_result",
                            tool_use_id="task_1",
                            content="Error: Failed to compile",
                            is_error=True
                        )
                    ]
                )

            mock_client.receive_response = mock_receive_response

            with mock_client:
                await run_orchestrated_session(
                    client=mock_client,
                    project_dir=project_dir,
                    session_id=session_id,
                    metrics_collector=collector
                )

            collector.end_session(session_id)

            # Verify error status recorded
            state = collector.get_state()
            event = state["events"][0]

            assert event["status"] == "error"
            assert "Failed to compile" in event["error_message"]

    @pytest.mark.asyncio
    async def test_tracking_without_metrics_collector_works(self):
        """Test that orchestrator works without metrics collector."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)

            mock_client = MagicMock()
            mock_client.query = AsyncMock()

            async def mock_receive_response():
                yield AssistantMessage(
                    type="message",
                    role="assistant",
                    content=[
                        TextBlock(type="text", text="Working on it...")
                    ]
                )

            mock_client.receive_response = mock_receive_response

            # Run without metrics_collector (should not crash)
            with mock_client:
                result = await run_orchestrated_session(
                    client=mock_client,
                    project_dir=project_dir,
                    session_id=None,
                    metrics_collector=None
                )

            assert result.status == "continue"

    @pytest.mark.asyncio
    async def test_malformed_task_input_handled_gracefully(self):
        """Test that malformed Task tool input doesn't crash orchestrator."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            collector = AgentMetricsCollector("test-project", Path(tmpdir))
            session_id = collector.start_session()

            mock_client = MagicMock()
            mock_client.query = AsyncMock()

            async def mock_receive_response():
                # Task with missing or malformed input
                yield AssistantMessage(
                    type="message",
                    role="assistant",
                    content=[
                        ToolUseBlock(
                            type="tool_use",
                            id="task_1",
                            name="Task",
                            input={}  # Missing agent and task fields
                        )
                    ]
                )
                yield UserMessage(
                    type="message",
                    role="user",
                    content=[
                        ToolResultBlock(
                            type="tool_result",
                            tool_use_id="task_1",
                            content="Done",
                            is_error=False
                        )
                    ]
                )

            mock_client.receive_response = mock_receive_response

            # Should not crash even with malformed input
            with mock_client:
                result = await run_orchestrated_session(
                    client=mock_client,
                    project_dir=project_dir,
                    session_id=session_id,
                    metrics_collector=collector
                )

            collector.end_session(session_id)

            # Verify delegation was still tracked (with "unknown" defaults)
            state = collector.get_state()
            assert len(state["events"]) == 1
            event = state["events"][0]
            assert event["agent_name"] == "unknown"
            assert event["ticket_key"] == "unknown"


class TestAgentProfileUpdates:
    """Test that agent profiles are updated from delegations."""

    @pytest.mark.asyncio
    async def test_delegation_updates_agent_profile(self):
        """Test that successful delegations update agent profiles."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            collector = AgentMetricsCollector("test-project", Path(tmpdir))
            session_id = collector.start_session()

            mock_client = MagicMock()
            mock_client.query = AsyncMock()

            async def mock_receive_response():
                yield AssistantMessage(
                    type="message",
                    role="assistant",
                    content=[
                        ToolUseBlock(
                            type="tool_use",
                            id="task_1",
                            name="Task",
                            input={"agent": "coding", "task": "Work on AI-51"}
                        )
                    ]
                )
                yield UserMessage(
                    type="message",
                    role="user",
                    content=[
                        ToolResultBlock(
                            type="tool_result",
                            tool_use_id="task_1",
                            content="Done",
                            is_error=False
                        )
                    ]
                )

            mock_client.receive_response = mock_receive_response

            with mock_client:
                await run_orchestrated_session(
                    client=mock_client,
                    project_dir=project_dir,
                    session_id=session_id,
                    metrics_collector=collector
                )

            collector.end_session(session_id)

            # Verify agent profile created and updated
            state = collector.get_state()
            assert "coding" in state["agents"]

            coding_profile = state["agents"]["coding"]
            assert coding_profile["total_invocations"] == 1
            assert coding_profile["successful_invocations"] == 1
            assert coding_profile["failed_invocations"] == 0
            assert coding_profile["total_tokens"] == 1500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
