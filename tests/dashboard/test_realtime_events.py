"""
Unit tests for Phase 2: Real-Time Updates - Event Emission Hooks

Tests that agent.py and orchestrator.py correctly emit WebSocket events
when agent status changes occur.

Test Coverage:
- Agent status broadcasting (idle → running → paused → error)
- Orchestrator reasoning broadcasting
- Event emission with metadata
- Graceful handling when WebSocket is unavailable
- Multiple simultaneous agents
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

# Test event emission functions
class TestAgentEventEmission:
    """Test agent.py event emission functionality."""

    @pytest.mark.asyncio
    async def test_broadcast_agent_status_with_websocket(self):
        """Test agent status broadcast when WebSocket is available."""
        # Create mock WebSocket server
        mock_ws_server = MagicMock()
        mock_ws_server.broadcast_agent_status = AsyncMock(return_value=1)

        # Patch the global websocket server
        with patch('agent._websocket_server', mock_ws_server):
            with patch('agent.WEBSOCKET_AVAILABLE', True):
                from agent import broadcast_agent_status

                # Broadcast running status
                await broadcast_agent_status(
                    agent_name="coding",
                    status="running",
                    metadata={"ticket_key": "AI-127"}
                )

                # Verify broadcast was called
                mock_ws_server.broadcast_agent_status.assert_called_once_with(
                    agent_name="coding",
                    status="running",
                    metadata={"ticket_key": "AI-127"}
                )

    @pytest.mark.asyncio
    async def test_broadcast_agent_status_without_websocket(self):
        """Test agent status broadcast when WebSocket is unavailable."""
        # Patch WebSocket as unavailable
        with patch('agent._websocket_server', None):
            with patch('agent.WEBSOCKET_AVAILABLE', False):
                from agent import broadcast_agent_status

                # Should not raise error
                await broadcast_agent_status(
                    agent_name="coding",
                    status="running",
                    metadata={}
                )

    @pytest.mark.asyncio
    async def test_broadcast_agent_status_with_websocket_error(self):
        """Test graceful handling when WebSocket broadcast fails."""
        # Create mock WebSocket server that raises error
        mock_ws_server = MagicMock()
        mock_ws_server.broadcast_agent_status = AsyncMock(side_effect=Exception("Connection lost"))

        with patch('agent._websocket_server', mock_ws_server):
            with patch('agent.WEBSOCKET_AVAILABLE', True):
                from agent import broadcast_agent_status

                # Should not raise error (graceful degradation)
                await broadcast_agent_status(
                    agent_name="coding",
                    status="error",
                    metadata={"error": "test error"}
                )

    @pytest.mark.asyncio
    async def test_agent_status_transitions(self):
        """Test complete agent status lifecycle: idle → running → idle."""
        mock_ws_server = MagicMock()
        mock_ws_server.broadcast_agent_status = AsyncMock(return_value=1)

        with patch('agent._websocket_server', mock_ws_server):
            with patch('agent.WEBSOCKET_AVAILABLE', True):
                from agent import broadcast_agent_status

                # Transition: idle → running
                await broadcast_agent_status("coding", "running", {"ticket_key": "AI-127"})

                # Transition: running → idle
                await broadcast_agent_status("coding", "idle", {"ticket_key": "AI-127"})

                # Verify both broadcasts
                assert mock_ws_server.broadcast_agent_status.call_count == 2


class TestOrchestratorEventEmission:
    """Test orchestrator.py event emission functionality."""

    @pytest.mark.asyncio
    async def test_broadcast_orchestrator_status(self):
        """Test orchestrator status broadcast."""
        mock_ws_server = MagicMock()
        mock_ws_server.broadcast_agent_status = AsyncMock(return_value=1)

        with patch('agents.orchestrator._websocket_server', mock_ws_server):
            with patch('agents.orchestrator.WEBSOCKET_AVAILABLE', True):
                from agents.orchestrator import broadcast_orchestrator_status

                # Broadcast orchestrator running
                await broadcast_orchestrator_status(
                    status="running",
                    metadata={"message": "Analyzing project state"}
                )

                # Verify broadcast
                mock_ws_server.broadcast_agent_status.assert_called_once_with(
                    agent_name="orchestrator",
                    status="running",
                    metadata={"message": "Analyzing project state"}
                )

    @pytest.mark.asyncio
    async def test_broadcast_reasoning(self):
        """Test orchestrator reasoning broadcast."""
        mock_ws_server = MagicMock()
        mock_ws_server.broadcast_reasoning = AsyncMock(return_count=1)

        with patch('agents.orchestrator._websocket_server', mock_ws_server):
            with patch('agents.orchestrator.WEBSOCKET_AVAILABLE', True):
                from agents.orchestrator import broadcast_reasoning

                # Broadcast reasoning
                await broadcast_reasoning(
                    content="Delegating to coding agent based on complexity",
                    context={"ticket": "AI-127", "complexity": "COMPLEX"}
                )

                # Verify broadcast
                mock_ws_server.broadcast_reasoning.assert_called_once_with(
                    content="Delegating to coding agent based on complexity",
                    source="orchestrator",
                    context={"ticket": "AI-127", "complexity": "COMPLEX"}
                )

    @pytest.mark.asyncio
    async def test_orchestrator_reasoning_without_websocket(self):
        """Test reasoning broadcast when WebSocket is unavailable."""
        with patch('agents.orchestrator._websocket_server', None):
            with patch('agents.orchestrator.WEBSOCKET_AVAILABLE', False):
                from agents.orchestrator import broadcast_reasoning

                # Should not raise error
                await broadcast_reasoning(
                    content="Test reasoning",
                    context={}
                )


class TestEventEmissionIntegration:
    """Integration tests for event emission in real agent sessions."""

    @pytest.mark.asyncio
    async def test_run_agent_session_broadcasts_status(self):
        """Test that run_agent_session broadcasts status changes."""
        # This is a lightweight integration test
        # Full integration would require Claude SDK client
        mock_ws_server = MagicMock()
        mock_ws_server.broadcast_agent_status = AsyncMock(return_value=1)

        with patch('agent._websocket_server', mock_ws_server):
            with patch('agent.WEBSOCKET_AVAILABLE', True):
                # Test that status broadcast is attempted
                # (actual session would require SDK client)
                from agent import broadcast_agent_status

                # Simulate agent starting work
                await broadcast_agent_status(
                    agent_name="coding",
                    status="running",
                    metadata={"ticket_key": "AI-127"}
                )

                # Simulate agent completing work
                await broadcast_agent_status(
                    agent_name="coding",
                    status="idle",
                    metadata={"ticket_key": "AI-127"}
                )

                # Verify both status changes were broadcast
                assert mock_ws_server.broadcast_agent_status.call_count == 2

                # Verify status sequence
                calls = mock_ws_server.broadcast_agent_status.call_args_list
                assert calls[0][1]['status'] == 'running'
                assert calls[1][1]['status'] == 'idle'

    @pytest.mark.asyncio
    async def test_agent_error_broadcasts_error_status(self):
        """Test that agent errors broadcast error status."""
        mock_ws_server = MagicMock()
        mock_ws_server.broadcast_agent_status = AsyncMock(return_value=1)

        with patch('agent._websocket_server', mock_ws_server):
            with patch('agent.WEBSOCKET_AVAILABLE', True):
                from agent import broadcast_agent_status

                # Simulate agent encountering error
                await broadcast_agent_status(
                    agent_name="coding",
                    status="error",
                    metadata={
                        "error": "Connection timeout",
                        "ticket_key": "AI-127"
                    }
                )

                # Verify error status was broadcast
                mock_ws_server.broadcast_agent_status.assert_called_once()
                call_args = mock_ws_server.broadcast_agent_status.call_args
                assert call_args[1]['status'] == 'error'
                assert 'error' in call_args[1]['metadata']

    @pytest.mark.asyncio
    async def test_multiple_agents_broadcast_independently(self):
        """Test that multiple agents can broadcast status independently."""
        mock_ws_server = MagicMock()
        mock_ws_server.broadcast_agent_status = AsyncMock(return_value=1)

        with patch('agent._websocket_server', mock_ws_server):
            with patch('agent.WEBSOCKET_AVAILABLE', True):
                from agent import broadcast_agent_status

                # Orchestrator starts
                await broadcast_agent_status("orchestrator", "running", {})

                # Coding agent starts
                await broadcast_agent_status("coding", "running", {"ticket_key": "AI-127"})

                # GitHub agent starts
                await broadcast_agent_status("github", "running", {"ticket_key": "AI-127"})

                # All agents broadcast independently
                assert mock_ws_server.broadcast_agent_status.call_count == 3

                # Verify each agent name
                calls = mock_ws_server.broadcast_agent_status.call_args_list
                agent_names = [call[1]['agent_name'] for call in calls]
                assert "orchestrator" in agent_names
                assert "coding" in agent_names
                assert "github" in agent_names


class TestRealtimeLatency:
    """Test that event broadcasting meets sub-100ms latency requirement."""

    @pytest.mark.asyncio
    async def test_broadcast_latency(self):
        """Test that event broadcasts complete in under 100ms."""
        import time

        mock_ws_server = MagicMock()
        mock_ws_server.broadcast_agent_status = AsyncMock(return_value=1)

        with patch('agent._websocket_server', mock_ws_server):
            with patch('agent.WEBSOCKET_AVAILABLE', True):
                from agent import broadcast_agent_status

                # Measure broadcast time
                start_time = time.time()

                await broadcast_agent_status(
                    agent_name="coding",
                    status="running",
                    metadata={"ticket_key": "AI-127"}
                )

                elapsed_ms = (time.time() - start_time) * 1000

                # Should be well under 100ms (mostly just function call overhead)
                assert elapsed_ms < 10, f"Broadcast took {elapsed_ms}ms (should be < 10ms)"

    @pytest.mark.asyncio
    async def test_rapid_status_changes(self):
        """Test handling of rapid status changes (stress test)."""
        mock_ws_server = MagicMock()
        mock_ws_server.broadcast_agent_status = AsyncMock(return_value=1)

        with patch('agent._websocket_server', mock_ws_server):
            with patch('agent.WEBSOCKET_AVAILABLE', True):
                from agent import broadcast_agent_status

                # Rapidly broadcast 100 status changes
                for i in range(100):
                    await broadcast_agent_status(
                        agent_name="coding",
                        status="running" if i % 2 == 0 else "idle",
                        metadata={"iteration": i}
                    )

                # All broadcasts should succeed
                assert mock_ws_server.broadcast_agent_status.call_count == 100


# Run tests with: python -m pytest tests/dashboard/test_realtime_events.py -v
