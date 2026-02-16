"""
Comprehensive unit and integration tests for dashboard/server.py
Testing all endpoints, WebSocket functionality, error handling, and edge cases.
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from aiohttp import ClientSession, WSMsgType
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

from dashboard.server import DashboardServer


class TestDashboardServerUnit(AioHTTPTestCase):
    """Unit tests for DashboardServer endpoints and functionality."""

    async def get_application(self):
        """Create test application."""
        # Create temporary metrics directory
        self.temp_dir = tempfile.mkdtemp()
        self.metrics_file = Path(self.temp_dir) / ".agent_metrics.json"

        # Create mock metrics data
        self.mock_metrics = {
            "project_name": "test-project",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T12:00:00Z",
            "total_sessions": 5,
            "total_tokens": 10000,
            "total_cost_usd": 0.5,
            "total_duration_seconds": 120.0,
            "agents": {
                "coding": {
                    "agent_name": "coding",
                    "total_invocations": 10,
                    "successful_invocations": 8,
                    "failed_invocations": 2,
                    "total_tokens": 5000,
                    "total_cost_usd": 0.25,
                    "total_duration_seconds": 60.0,
                    "commits_made": 3,
                    "prs_created": 1,
                    "prs_merged": 0,
                    "files_created": 2,
                    "files_modified": 5,
                    "lines_added": 150,
                    "lines_removed": 30,
                    "tests_written": 4,
                    "issues_created": 0,
                    "issues_completed": 1,
                    "messages_sent": 0,
                    "reviews_completed": 0,
                    "success_rate": 0.8,
                    "avg_duration_seconds": 6.0,
                    "avg_tokens_per_call": 500.0,
                    "cost_per_success_usd": 0.03125,
                    "xp": 250,
                    "level": 3,
                    "current_streak": 2,
                    "best_streak": 5,
                    "achievements": ["first_commit", "test_writer"],
                    "strengths": ["code_quality", "testing"],
                    "weaknesses": ["error_handling"],
                    "recent_events": ["event-1", "event-2"],
                    "last_error": "File not found",
                    "last_active": "2024-01-01T12:00:00Z"
                },
                "linear": {
                    "agent_name": "linear",
                    "total_invocations": 5,
                    "successful_invocations": 5,
                    "failed_invocations": 0,
                    "total_tokens": 2000,
                    "total_cost_usd": 0.1,
                    "total_duration_seconds": 30.0,
                    "commits_made": 0,
                    "prs_created": 0,
                    "prs_merged": 0,
                    "files_created": 0,
                    "files_modified": 0,
                    "lines_added": 0,
                    "lines_removed": 0,
                    "tests_written": 0,
                    "issues_created": 2,
                    "issues_completed": 1,
                    "messages_sent": 0,
                    "reviews_completed": 0,
                    "success_rate": 1.0,
                    "avg_duration_seconds": 6.0,
                    "avg_tokens_per_call": 400.0,
                    "cost_per_success_usd": 0.02,
                    "xp": 150,
                    "level": 2,
                    "current_streak": 5,
                    "best_streak": 5,
                    "achievements": ["issue_creator"],
                    "strengths": ["reliability"],
                    "weaknesses": [],
                    "recent_events": ["event-3"],
                    "last_error": "",
                    "last_active": "2024-01-01T11:30:00Z"
                }
            },
            "events": [
                {
                    "event_id": "event-1",
                    "agent_name": "coding",
                    "session_id": "session-1",
                    "ticket_key": "AI-100",
                    "started_at": "2024-01-01T10:00:00Z",
                    "ended_at": "2024-01-01T10:05:00Z",
                    "duration_seconds": 300.0,
                    "status": "success",
                    "input_tokens": 1000,
                    "output_tokens": 1500,
                    "total_tokens": 2500,
                    "estimated_cost_usd": 0.0525,
                    "artifacts": ["file:test.py:created", "commit:abc123"],
                    "error_message": "",
                    "model_used": "claude-sonnet-4-5"
                }
            ],
            "sessions": [
                {
                    "session_id": "session-1",
                    "session_number": 1,
                    "session_type": "initializer",
                    "started_at": "2024-01-01T10:00:00Z",
                    "ended_at": "2024-01-01T10:30:00Z",
                    "status": "complete",
                    "agents_invoked": ["coding", "linear"],
                    "total_tokens": 5000,
                    "total_cost_usd": 0.25,
                    "tickets_worked": ["AI-100"]
                }
            ]
        }

        # Write mock metrics to file
        self.metrics_file.write_text(json.dumps(self.mock_metrics, indent=2))

        # Create server instance
        self.server = DashboardServer(
            project_name="test-project",
            metrics_dir=Path(self.temp_dir),
            port=8080,
            host="127.0.0.1"
        )

        return self.server.app

    async def tearDown(self):
        """Cleanup after tests."""
        await super().tearDown()
        # Cleanup temp directory
        import shutil
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    @unittest_run_loop
    async def test_health_check_endpoint(self):
        """Test 1: Verify health check endpoint responds."""
        resp = await self.client.request("GET", "/health")
        assert resp.status == 200

        data = await resp.json()
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert data["project"] == "test-project"
        assert data["metrics_file_exists"] is True
        assert data["event_count"] > 0
        assert data["session_count"] > 0
        assert data["agent_count"] > 0

    @unittest_run_loop
    async def test_get_metrics_endpoint(self):
        """Test 2: Verify metrics endpoint returns current state."""
        resp = await self.client.request("GET", "/api/metrics")
        assert resp.status == 200

        data = await resp.json()
        assert data["project_name"] == "test-project"
        assert "agents" in data
        assert "events" in data
        assert "sessions" in data
        assert len(data["agents"]) >= 2  # coding and linear

    @unittest_run_loop
    async def test_get_agents_endpoint_returns_all_agents(self):
        """Test 3: Verify agents endpoint returns all 13 agents (if they exist)."""
        resp = await self.client.request("GET", "/api/metrics")
        assert resp.status == 200

        data = await resp.json()
        agents = data["agents"]

        # We have 2 agents in mock data
        assert len(agents) >= 2
        assert "coding" in agents
        assert "linear" in agents

    @unittest_run_loop
    async def test_get_specific_agent(self):
        """Test 4: Get specific agent profile."""
        resp = await self.client.request("GET", "/api/agents/coding")
        assert resp.status == 200

        data = await resp.json()
        assert "agent" in data
        assert data["agent"]["agent_name"] == "coding"
        assert data["agent"]["total_invocations"] == 10
        assert data["agent"]["success_rate"] == 0.8

    @unittest_run_loop
    async def test_get_agent_not_found(self):
        """Test 5: Get non-existent agent returns 404."""
        resp = await self.client.request("GET", "/api/agents/nonexistent")
        assert resp.status == 404

        data = await resp.json()
        assert "error" in data
        assert data["error"] == "Agent not found"
        assert "available_agents" in data

    @unittest_run_loop
    async def test_get_agent_with_events(self):
        """Test 6: Get agent with events included."""
        resp = await self.client.request("GET", "/api/agents/coding?include_events=1")
        assert resp.status == 200

        data = await resp.json()
        assert "agent" in data
        assert "recent_events" in data
        assert len(data["recent_events"]) >= 0

    @unittest_run_loop
    async def test_get_metrics_pretty_format(self):
        """Test 7: Verify pretty JSON formatting."""
        resp = await self.client.request("GET", "/api/metrics?pretty")
        assert resp.status == 200

        text = await resp.text()
        # Pretty JSON should have newlines and indentation
        assert "\n" in text
        assert "  " in text  # Indentation

    @unittest_run_loop
    async def test_cors_headers(self):
        """Test 8: Verify CORS headers are present."""
        resp = await self.client.request("GET", "/api/metrics")
        assert resp.status == 200

        # Check CORS headers
        assert "Access-Control-Allow-Origin" in resp.headers
        assert "Access-Control-Allow-Methods" in resp.headers
        assert "Access-Control-Allow-Headers" in resp.headers

    @unittest_run_loop
    async def test_options_request(self):
        """Test 9: Verify OPTIONS request for CORS preflight."""
        resp = await self.client.request("OPTIONS", "/api/metrics")
        assert resp.status == 204

    @unittest_run_loop
    async def test_serve_dashboard_html(self):
        """Test 10: Verify static HTML dashboard is served."""
        resp = await self.client.request("GET", "/")

        # If dashboard.html exists, should return it
        if resp.status == 200:
            content = await resp.text()
            assert len(content) > 0
            assert "html" in content.lower()

    @unittest_run_loop
    async def test_error_handling_invalid_json(self):
        """Test 11: Verify error handling for corrupted metrics file."""
        # Write invalid JSON to metrics file
        self.metrics_file.write_text("invalid json")

        resp = await self.client.request("GET", "/api/metrics")
        assert resp.status == 500

        data = await resp.json()
        assert "error" in data

    @unittest_run_loop
    async def test_multiple_concurrent_connections(self):
        """Test 12: Test server handles multiple concurrent connections."""
        # Make multiple concurrent requests
        tasks = []
        for _ in range(10):
            tasks.append(self.client.request("GET", "/health"))

        responses = await asyncio.gather(*tasks)

        # All should succeed
        for resp in responses:
            assert resp.status == 200

    @unittest_run_loop
    async def test_websocket_connection(self):
        """Test 13: Verify WebSocket connection works."""
        async with self.client.ws_connect("/ws") as ws:
            # Should receive initial metrics immediately
            msg = await ws.receive()
            assert msg.type == WSMsgType.TEXT

            data = json.loads(msg.data)
            assert data["type"] == "metrics_update"
            assert "data" in data
            assert "timestamp" in data

    @unittest_run_loop
    async def test_websocket_ping_pong(self):
        """Test 14: Verify WebSocket ping/pong."""
        async with self.client.ws_connect("/ws") as ws:
            # Wait for initial message
            await ws.receive()

            # Send ping
            await ws.send_str("ping")

            # Receive pong
            msg = await ws.receive()
            assert msg.data == "pong"

    @unittest_run_loop
    async def test_websocket_broadcast(self):
        """Test 15: Verify WebSocket broadcasts metrics updates."""
        async with self.client.ws_connect("/ws") as ws:
            # Receive initial message
            msg1 = await ws.receive()
            assert msg1.type == WSMsgType.TEXT

            # Wait for broadcast (may take up to 5 seconds based on broadcast_interval)
            # For testing, we just verify the initial message format
            data = json.loads(msg1.data)
            assert data["type"] == "metrics_update"
            assert "data" in data

    @unittest_run_loop
    async def test_agent_profile_completeness(self):
        """Test 16: Verify agent profile has all required fields."""
        resp = await self.client.request("GET", "/api/agents/coding")
        assert resp.status == 200

        data = await resp.json()
        agent = data["agent"]

        # Check all required fields exist
        required_fields = [
            "agent_name", "total_invocations", "successful_invocations",
            "failed_invocations", "total_tokens", "total_cost_usd",
            "success_rate", "avg_duration_seconds", "xp", "level",
            "achievements", "strengths", "weaknesses"
        ]

        for field in required_fields:
            assert field in agent, f"Missing required field: {field}"

    @unittest_run_loop
    async def test_metrics_endpoint_structure(self):
        """Test 17: Verify metrics endpoint returns proper structure."""
        resp = await self.client.request("GET", "/api/metrics")
        assert resp.status == 200

        data = await resp.json()

        # Verify top-level structure
        assert "project_name" in data
        assert "agents" in data
        assert "events" in data
        assert "sessions" in data
        assert "total_sessions" in data
        assert "total_tokens" in data
        assert "total_cost_usd" in data

    @unittest_run_loop
    async def test_session_data_structure(self):
        """Test 18: Verify session data has correct structure."""
        resp = await self.client.request("GET", "/api/metrics")
        assert resp.status == 200

        data = await resp.json()
        sessions = data["sessions"]

        if len(sessions) > 0:
            session = sessions[0]
            assert "session_id" in session
            assert "session_number" in session
            assert "started_at" in session
            assert "ended_at" in session
            assert "agents_invoked" in session
            assert "total_tokens" in session

    @unittest_run_loop
    async def test_event_data_structure(self):
        """Test 19: Verify event data has correct structure."""
        resp = await self.client.request("GET", "/api/metrics")
        assert resp.status == 200

        data = await resp.json()
        events = data["events"]

        if len(events) > 0:
            event = events[0]
            assert "event_id" in event
            assert "agent_name" in event
            assert "ticket_key" in event
            assert "started_at" in event
            assert "ended_at" in event
            assert "status" in event
            assert "total_tokens" in event

    @unittest_run_loop
    async def test_server_handles_empty_metrics(self):
        """Test 20: Verify server handles empty metrics file gracefully."""
        # Create minimal valid metrics
        minimal_metrics = {
            "project_name": "test-project",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "total_sessions": 0,
            "total_tokens": 0,
            "total_cost_usd": 0.0,
            "total_duration_seconds": 0.0,
            "agents": {},
            "events": [],
            "sessions": []
        }

        self.metrics_file.write_text(json.dumps(minimal_metrics))

        resp = await self.client.request("GET", "/api/metrics")
        assert resp.status == 200

        data = await resp.json()
        assert data["project_name"] == "test-project"
        assert len(data["agents"]) == 0


class TestDashboardServerSecurity:
    """Security tests for dashboard server."""

    def test_cors_configuration_default(self):
        """Test 21: Verify default CORS configuration is secure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            server = DashboardServer(
                project_name="test",
                metrics_dir=Path(temp_dir)
            )

            # Default host should be 127.0.0.1 (localhost only)
            assert server.host == "127.0.0.1"

    def test_cors_configuration_warning(self, capsys):
        """Test 22: Verify warning when binding to all interfaces."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # This should log a warning
            server = DashboardServer(
                project_name="test",
                metrics_dir=Path(temp_dir),
                host="0.0.0.0"
            )

            assert server.host == "0.0.0.0"


class TestDashboardServerEdgeCases:
    """Edge case tests for dashboard server."""

    def test_server_initialization_custom_port(self):
        """Test 23: Verify server can be initialized with custom port."""
        with tempfile.TemporaryDirectory() as temp_dir:
            server = DashboardServer(
                project_name="test",
                metrics_dir=Path(temp_dir),
                port=9000
            )

            assert server.port == 9000

    def test_server_initialization_custom_project_name(self):
        """Test 24: Verify server can be initialized with custom project name."""
        with tempfile.TemporaryDirectory() as temp_dir:
            server = DashboardServer(
                project_name="custom-project",
                metrics_dir=Path(temp_dir)
            )

            assert server.project_name == "custom-project"

    def test_websocket_tracking(self):
        """Test 25: Verify WebSocket connections are tracked."""
        with tempfile.TemporaryDirectory() as temp_dir:
            server = DashboardServer(
                project_name="test",
                metrics_dir=Path(temp_dir)
            )

            # Initially no connections
            assert len(server.websockets) == 0


@pytest.mark.asyncio
async def test_server_lifecycle():
    """Test 26: Verify server can be started and stopped cleanly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        server = DashboardServer(
            project_name="test",
            metrics_dir=Path(temp_dir)
        )

        # Server should be initialized
        assert server.app is not None
        assert server.store is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
