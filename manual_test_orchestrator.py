#!/usr/bin/env python3
"""Manual test script for orchestrator delegation tracking.

This script demonstrates that the orchestrator instrumentation works correctly
by simulating Task tool delegations and verifying that events are recorded.

Run this script to verify:
1. Task tool delegations are detected
2. Agent names and ticket keys are extracted
3. Events are recorded to .agent_metrics.json
4. Token counts are attributed correctly
5. Timing is captured
"""

import asyncio
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from agent_metrics_collector import AgentMetricsCollector
from claude_agent_sdk import (
    AssistantMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

# Import orchestrator function directly to avoid complex imports
# We'll patch the imports it needs
import agents.orchestrator as orchestrator_module


async def test_single_delegation():
    """Test a single Task tool delegation."""
    print("\n" + "=" * 70)
    print("TEST 1: Single Task Tool Delegation")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        metrics_dir = project_dir

        # Create collector
        collector = AgentMetricsCollector(
            project_name="test-orchestrator",
            metrics_dir=metrics_dir
        )

        # Start session
        session_id = collector.start_session(session_type="continuation")
        print(f"\n✓ Started session: {session_id[:8]}...")

        # Mock Claude SDK client
        mock_client = MagicMock()
        mock_client.query = AsyncMock()

        # Create mock Task tool usage
        async def mock_receive_response():
            # Orchestrator decides to delegate
            yield AssistantMessage(
                type="message",
                role="assistant",
                content=[
                    TextBlock(type="text", text="I'll delegate to the coding agent to work on AI-51."),
                    ToolUseBlock(
                        type="tool_use",
                        id="task_abc123",
                        name="Task",
                        input={"agent": "coding", "task": "Work on AI-51: Implement delegation tracking"}
                    )
                ]
            )

            # Simulate agent execution time
            await asyncio.sleep(0.1)

            # Tool result comes back
            yield UserMessage(
                type="message",
                role="user",
                content=[
                    ToolResultBlock(
                        type="tool_result",
                        tool_use_id="task_abc123",
                        content="Successfully implemented delegation tracking",
                        is_error=False
                    )
                ]
            )

        mock_client.receive_response = mock_receive_response

        # Run orchestrated session
        print("\n✓ Running orchestrated session with mocked client...")
        with mock_client:
            result = await orchestrator_module.run_orchestrated_session(
                client=mock_client,
                project_dir=project_dir,
                session_id=session_id,
                metrics_collector=collector
            )

        print(f"✓ Session result: {result.status}")

        # End session
        collector.end_session(session_id, status="complete")
        print(f"✓ Ended session")

        # Verify delegation was tracked
        state = collector.get_state()

        print("\n" + "-" * 70)
        print("VERIFICATION")
        print("-" * 70)

        # Check events
        print(f"\nTotal events recorded: {len(state['events'])}")
        assert len(state['events']) == 1, "Expected 1 event"
        print("✓ Correct number of events")

        event = state['events'][0]
        print(f"\nEvent details:")
        print(f"  - Agent: {event['agent_name']}")
        print(f"  - Ticket: {event['ticket_key']}")
        print(f"  - Status: {event['status']}")
        print(f"  - Input tokens: {event['input_tokens']}")
        print(f"  - Output tokens: {event['output_tokens']}")
        print(f"  - Duration: {event['duration_seconds']:.3f}s")

        assert event['agent_name'] == "coding", f"Expected 'coding', got '{event['agent_name']}'"
        assert event['ticket_key'] == "AI-51", f"Expected 'AI-51', got '{event['ticket_key']}'"
        assert event['status'] == "success", f"Expected 'success', got '{event['status']}'"
        assert event['input_tokens'] > 0, "Expected positive input tokens"
        assert event['output_tokens'] > 0, "Expected positive output tokens"

        print("\n✓ All assertions passed!")

        # Check agent profile
        print(f"\nAgent profiles: {list(state['agents'].keys())}")
        assert "coding" in state['agents'], "Expected 'coding' agent profile"

        coding_profile = state['agents']['coding']
        print(f"\nCoding agent profile:")
        print(f"  - Total invocations: {coding_profile['total_invocations']}")
        print(f"  - Successful: {coding_profile['successful_invocations']}")
        print(f"  - Failed: {coding_profile['failed_invocations']}")
        print(f"  - Total tokens: {coding_profile['total_tokens']}")

        assert coding_profile['total_invocations'] == 1
        assert coding_profile['successful_invocations'] == 1
        assert coding_profile['failed_invocations'] == 0

        print("\n✓ Agent profile updated correctly!")

        print("\n" + "=" * 70)
        print("TEST 1 PASSED ✓")
        print("=" * 70)


async def test_multiple_delegations():
    """Test multiple Task tool delegations in one session."""
    print("\n" + "=" * 70)
    print("TEST 2: Multiple Task Tool Delegations")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        collector = AgentMetricsCollector("test-multi", Path(tmpdir))
        session_id = collector.start_session()

        print(f"\n✓ Started session: {session_id[:8]}...")

        mock_client = MagicMock()
        mock_client.query = AsyncMock()

        # Multiple delegations
        async def mock_receive_response():
            # First: coding agent
            yield AssistantMessage(
                type="message",
                role="assistant",
                content=[
                    ToolUseBlock(
                        type="tool_use",
                        id="task_1",
                        name="Task",
                        input={"agent": "coding", "task": "Implement AI-51"}
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

            # Second: github agent
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
                        content="PR #123 created",
                        is_error=False
                    )
                ]
            )

            # Third: slack agent
            yield AssistantMessage(
                type="message",
                role="assistant",
                content=[
                    ToolUseBlock(
                        type="tool_use",
                        id="task_3",
                        name="Task",
                        input={"agent": "slack", "task": "Notify team about AI-51"}
                    )
                ]
            )
            yield UserMessage(
                type="message",
                role="user",
                content=[
                    ToolResultBlock(
                        type="tool_result",
                        tool_use_id="task_3",
                        content="Message sent",
                        is_error=False
                    )
                ]
            )

        mock_client.receive_response = mock_receive_response

        print("\n✓ Running orchestrated session with 3 delegations...")
        with mock_client:
            result = await orchestrator_module.run_orchestrated_session(
                client=mock_client,
                project_dir=project_dir,
                session_id=session_id,
                metrics_collector=collector
            )

        collector.end_session(session_id)

        # Verify
        state = collector.get_state()

        print("\n" + "-" * 70)
        print("VERIFICATION")
        print("-" * 70)

        print(f"\nTotal events: {len(state['events'])}")
        assert len(state['events']) == 3, f"Expected 3 events, got {len(state['events'])}"
        print("✓ Correct number of events")

        agents = [e['agent_name'] for e in state['events']]
        print(f"\nAgents invoked: {agents}")
        assert agents == ["coding", "github", "slack"]
        print("✓ Correct agent sequence")

        # Check session summary
        session = state['sessions'][0]
        print(f"\nSession summary:")
        print(f"  - Agents invoked: {session['agents_invoked']}")
        print(f"  - Tickets worked: {session['tickets_worked']}")
        print(f"  - Total tokens: {session['total_tokens']}")

        assert set(session['agents_invoked']) == {"coding", "github", "slack"}
        assert "AI-51" in session['tickets_worked']
        assert session['total_tokens'] == 4500  # 3 delegations × 1500 tokens

        print("\n✓ Session summary correct!")

        print("\n" + "=" * 70)
        print("TEST 2 PASSED ✓")
        print("=" * 70)


async def test_error_delegation():
    """Test failed Task tool delegation."""
    print("\n" + "=" * 70)
    print("TEST 3: Failed Task Tool Delegation")
    print("=" * 70)

    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)
        collector = AgentMetricsCollector("test-error", Path(tmpdir))
        session_id = collector.start_session()

        print(f"\n✓ Started session: {session_id[:8]}...")

        mock_client = MagicMock()
        mock_client.query = AsyncMock()

        async def mock_receive_response():
            yield AssistantMessage(
                type="message",
                role="assistant",
                content=[
                    ToolUseBlock(
                        type="tool_use",
                        id="task_fail",
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
                        tool_use_id="task_fail",
                        content="Error: Tests failed",
                        is_error=True
                    )
                ]
            )

        mock_client.receive_response = mock_receive_response

        print("\n✓ Running orchestrated session with failing delegation...")
        with mock_client:
            result = await orchestrator_module.run_orchestrated_session(
                client=mock_client,
                project_dir=project_dir,
                session_id=session_id,
                metrics_collector=collector
            )

        collector.end_session(session_id, status="error")

        # Verify
        state = collector.get_state()

        print("\n" + "-" * 70)
        print("VERIFICATION")
        print("-" * 70)

        event = state['events'][0]
        print(f"\nEvent status: {event['status']}")
        print(f"Error message: {event['error_message']}")

        assert event['status'] == "error"
        assert "Tests failed" in event['error_message']

        print("\n✓ Error recorded correctly!")

        # Check agent profile
        coding_profile = state['agents']['coding']
        print(f"\nCoding agent after error:")
        print(f"  - Total invocations: {coding_profile['total_invocations']}")
        print(f"  - Successful: {coding_profile['successful_invocations']}")
        print(f"  - Failed: {coding_profile['failed_invocations']}")

        assert coding_profile['total_invocations'] == 1
        assert coding_profile['successful_invocations'] == 0
        assert coding_profile['failed_invocations'] == 1

        print("\n✓ Agent profile reflects failure!")

        print("\n" + "=" * 70)
        print("TEST 3 PASSED ✓")
        print("=" * 70)


async def main():
    """Run all manual tests."""
    print("\n" + "╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "ORCHESTRATOR DELEGATION TRACKING TESTS" + " " * 15 + "║")
    print("╚" + "=" * 68 + "╝")

    try:
        await test_single_delegation()
        await test_multiple_delegations()
        await test_error_delegation()

        print("\n" + "╔" + "=" * 68 + "╗")
        print("║" + " " * 22 + "ALL TESTS PASSED ✓" + " " * 24 + "║")
        print("╚" + "=" * 68 + "╝\n")

        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
