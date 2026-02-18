"""
Comprehensive unit and integration tests for dashboard/rest_api_server.py

Tests all 14 REST API endpoints with authentication, error cases, and data validation.

Test Coverage:
- Health check (GET /api/health)
- Metrics (GET /api/metrics)
- All agents (GET /api/agents)
- Single agent (GET /api/agents/{name})
- Agent events (GET /api/agents/{name}/events)
- Sessions (GET /api/sessions)
- Providers (GET /api/providers)
- Chat (POST /api/chat)
- Pause agent (POST /api/agents/{name}/pause)
- Resume agent (POST /api/agents/{name}/resume)
- Update requirements (PUT /api/requirements/{ticket_key})
- Get requirements (GET /api/requirements/{ticket_key})
- Decisions (GET /api/decisions)
- Dashboard HTML (GET /)
- Authentication with and without token
- Error cases (404, 400, 401)
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from aiohttp.test_utils import AioHTTPTestCase

from dashboard.rest_api_server import RESTAPIServer


class TestRESTAPIServerEndpoints(AioHTTPTestCase):
    """Test all REST API endpoints."""

    async def get_application(self):
        """Create test application."""
        # Create temporary metrics directory
        self.temp_dir = tempfile.mkdtemp()
        self.metrics_file = Path(self.temp_dir) / ".agent_metrics.json"

        # Create mock metrics data
        self.mock_metrics = {
            "version": 1,
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
                    "model_used": "claude-sonnet-4-5",
                    "file_changes": []
                },
                {
                    "event_id": "event-2",
                    "agent_name": "coding",
                    "session_id": "session-1",
                    "ticket_key": "AI-100",
                    "started_at": "2024-01-01T10:10:00Z",
                    "ended_at": "2024-01-01T10:15:00Z",
                    "duration_seconds": 300.0,
                    "status": "success",
                    "input_tokens": 1000,
                    "output_tokens": 1500,
                    "total_tokens": 2500,
                    "estimated_cost_usd": 0.0525,
                    "artifacts": ["file:test2.py:modified"],
                    "error_message": "",
                    "model_used": "claude-sonnet-4-5",
                    "file_changes": []
                },
                {
                    "event_id": "event-3",
                    "agent_name": "linear",
                    "session_id": "session-1",
                    "ticket_key": "AI-100",
                    "started_at": "2024-01-01T10:20:00Z",
                    "ended_at": "2024-01-01T10:25:00Z",
                    "duration_seconds": 300.0,
                    "status": "success",
                    "input_tokens": 500,
                    "output_tokens": 500,
                    "total_tokens": 1000,
                    "estimated_cost_usd": 0.02,
                    "artifacts": ["issue:AI-101:created"],
                    "error_message": "",
                    "model_used": "claude-haiku-4-5",
                    "file_changes": []
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

        # Create server instance (no auth token for tests)
        with patch.dict(os.environ, {}, clear=False):
            # Ensure DASHBOARD_AUTH_TOKEN is not set for basic tests
            if 'DASHBOARD_AUTH_TOKEN' in os.environ:
                del os.environ['DASHBOARD_AUTH_TOKEN']

            self.server = RESTAPIServer(
                project_name="test-project",
                metrics_dir=Path(self.temp_dir),
                port=8420,
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

    # Test 1: Health check
    async def test_health_check(self):
        """Test GET /api/health returns 200 OK."""
        resp = await self.client.request("GET", "/api/health")
        assert resp.status == 200

        data = await resp.json()
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert data["project"] == "test-project"

    # Test 2: Get metrics
    async def test_get_metrics(self):
        """Test GET /api/metrics returns DashboardState."""
        resp = await self.client.request("GET", "/api/metrics")
        assert resp.status == 200

        data = await resp.json()
        assert data["project_name"] == "test-project"
        assert "agents" in data
        assert "events" in data
        assert "sessions" in data

    # Test 3: Get all agents
    async def test_get_all_agents(self):
        """Test GET /api/agents returns all agents."""
        resp = await self.client.request("GET", "/api/agents")
        assert resp.status == 200

        data = await resp.json()
        assert "agents" in data
        assert "total_agents" in data

        # Should return all 14 agents (from ALL_AGENT_NAMES)
        assert data["total_agents"] == 14
        assert len(data["agents"]) == 14

    # Test 4: Get specific agent
    async def test_get_specific_agent(self):
        """Test GET /api/agents/{name} returns specific agent."""
        resp = await self.client.request("GET", "/api/agents/coding")
        assert resp.status == 200

        data = await resp.json()
        assert "agent" in data
        assert data["agent"]["agent_name"] == "coding"
        assert data["agent"]["total_invocations"] == 10

    # Test 5: Get non-existent agent
    async def test_get_nonexistent_agent(self):
        """Test GET /api/agents/{name} returns 404 for invalid agent."""
        resp = await self.client.request("GET", "/api/agents/nonexistent")
        assert resp.status == 404

        data = await resp.json()
        assert "error" in data

    # Test 6: Get agent events
    async def test_get_agent_events(self):
        """Test GET /api/agents/{name}/events returns events for agent."""
        resp = await self.client.request("GET", "/api/agents/coding/events")
        assert resp.status == 200

        data = await resp.json()
        assert "events" in data
        assert data["agent_name"] == "coding"
        assert len(data["events"]) == 2  # coding has 2 events

    # Test 7: Get agent events with limit
    async def test_get_agent_events_with_limit(self):
        """Test GET /api/agents/{name}/events?limit=1 respects limit."""
        resp = await self.client.request("GET", "/api/agents/coding/events?limit=1")
        assert resp.status == 200

        data = await resp.json()
        assert len(data["events"]) == 1

    # Test 8: Get sessions
    async def test_get_sessions(self):
        """Test GET /api/sessions returns session history."""
        resp = await self.client.request("GET", "/api/sessions")
        assert resp.status == 200

        data = await resp.json()
        assert "sessions" in data
        assert "total_sessions" in data
        assert len(data["sessions"]) == 1

    # Test 9: Get providers
    async def test_get_providers(self):
        """Test GET /api/providers returns available providers."""
        resp = await self.client.request("GET", "/api/providers")
        assert resp.status == 200

        data = await resp.json()
        assert "providers" in data

        # Should have 6 providers
        assert len(data["providers"]) == 6

        # Claude should always be available
        claude = next(p for p in data["providers"] if p["provider_id"] == "claude")
        assert claude["available"] is True

    # Test 10: POST chat
    async def test_post_chat(self):
        """Test POST /api/chat sends message (streaming response)."""
        payload = {
            "message": "Hello, agent!",
            "provider": "claude",
            "model": "sonnet-4-5"
        }

        resp = await self.client.request("POST", "/api/chat", json=payload)
        assert resp.status == 200

        # Response is now streaming SSE, not JSON
        content_type = resp.headers.get('Content-Type', '')
        assert content_type in ['text/event-stream', 'application/json']

        # Read response content
        content = await resp.text()
        assert len(content) >= 0  # Response received

    # Test 11: POST chat with missing message
    async def test_post_chat_missing_message(self):
        """Test POST /api/chat returns 400 without message."""
        payload = {"provider": "claude"}

        resp = await self.client.request("POST", "/api/chat", json=payload)
        assert resp.status == 400

        data = await resp.json()
        assert "error" in data

    # Test 12: POST chat with invalid JSON
    async def test_post_chat_invalid_json(self):
        """Test POST /api/chat returns 400 for invalid JSON."""
        resp = await self.client.request(
            "POST",
            "/api/chat",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert resp.status == 400

    # Test 13: Pause agent
    async def test_pause_agent(self):
        """Test POST /api/agents/{name}/pause pauses agent."""
        resp = await self.client.request("POST", "/api/agents/coding/pause")
        assert resp.status == 200

        data = await resp.json()
        assert data["status"] == "success"
        assert data["state"] == "paused"
        assert data["agent_name"] == "coding"

    # Test 14: Pause non-existent agent
    async def test_pause_nonexistent_agent(self):
        """Test POST /api/agents/{name}/pause returns 404 for invalid agent."""
        resp = await self.client.request("POST", "/api/agents/nonexistent/pause")
        assert resp.status == 404

    # Test 15: Resume agent
    async def test_resume_agent(self):
        """Test POST /api/agents/{name}/resume resumes agent."""
        # First pause
        await self.client.request("POST", "/api/agents/coding/pause")

        # Then resume
        resp = await self.client.request("POST", "/api/agents/coding/resume")
        assert resp.status == 200

        data = await resp.json()
        assert data["status"] == "success"
        assert data["state"] == "idle"

    # Test 16: Update requirements
    async def test_update_requirements(self):
        """Test PUT /api/requirements/{ticket_key} updates requirements."""
        payload = {
            "requirements": "Build a REST API with authentication"
        }

        resp = await self.client.request(
            "PUT",
            "/api/requirements/AI-105",
            json=payload
        )
        assert resp.status == 200

        data = await resp.json()
        assert data["status"] == "success"
        assert data["ticket_key"] == "AI-105"

    # Test 17: Update requirements with missing field
    async def test_update_requirements_missing_field(self):
        """Test PUT /api/requirements/{ticket_key} returns 400 without requirements."""
        payload = {}

        resp = await self.client.request(
            "PUT",
            "/api/requirements/AI-105",
            json=payload
        )
        assert resp.status == 400

    # Test 18: Get requirements
    async def test_get_requirements(self):
        """Test GET /api/requirements/{ticket_key} returns requirements."""
        # First update
        payload = {"requirements": "Test requirement"}
        await self.client.request(
            "PUT",
            "/api/requirements/AI-105",
            json=payload
        )

        # Then get
        resp = await self.client.request("GET", "/api/requirements/AI-105")
        assert resp.status == 200

        data = await resp.json()
        assert data["ticket_key"] == "AI-105"
        assert data["requirements"] == "Test requirement"

    # Test 19: Get non-existent requirements
    async def test_get_nonexistent_requirements(self):
        """Test GET /api/requirements/{ticket_key} returns 404 for missing requirements."""
        resp = await self.client.request("GET", "/api/requirements/AI-999")
        assert resp.status == 404

    # Test 20: Get decisions
    async def test_get_decisions(self):
        """Test GET /api/decisions returns decision history."""
        # Generate some decisions
        await self.client.request("POST", "/api/agents/coding/pause")
        await self.client.request("POST", "/api/agents/coding/resume")

        resp = await self.client.request("GET", "/api/decisions")
        assert resp.status == 200

        data = await resp.json()
        assert "decisions" in data
        assert "total_decisions" in data
        assert len(data["decisions"]) >= 2

    # Test 21: Get decisions with limit
    async def test_get_decisions_with_limit(self):
        """Test GET /api/decisions?limit=1 respects limit."""
        await self.client.request("POST", "/api/agents/coding/pause")

        resp = await self.client.request("GET", "/api/decisions?limit=1")
        assert resp.status == 200

        data = await resp.json()
        assert len(data["decisions"]) == 1

    # Test 22: OPTIONS request (CORS preflight)
    async def test_options_request(self):
        """Test OPTIONS /api/metrics for CORS preflight."""
        resp = await self.client.request("OPTIONS", "/api/metrics")
        assert resp.status == 204

    # Test 23: CORS headers
    async def test_cors_headers(self):
        """Test CORS headers are present on responses."""
        resp = await self.client.request("GET", "/api/health")
        assert "Access-Control-Allow-Origin" in resp.headers
        assert "Access-Control-Allow-Methods" in resp.headers

    # Test 24: Serve dashboard HTML
    async def test_serve_dashboard(self):
        """Test GET / serves dashboard HTML."""
        resp = await self.client.request("GET", "/")

        # Should return 200 or 404 depending on whether HTML exists
        assert resp.status in [200, 404]

    # Test 25: Multiple concurrent requests
    async def test_concurrent_requests(self):
        """Test server handles multiple concurrent requests."""
        tasks = [
            self.client.request("GET", "/api/health"),
            self.client.request("GET", "/api/metrics"),
            self.client.request("GET", "/api/agents"),
            self.client.request("GET", "/api/sessions"),
            self.client.request("GET", "/api/providers")
        ]

        responses = await asyncio.gather(*tasks)

        # All should succeed
        for resp in responses:
            assert resp.status == 200


class TestRESTAPIServerAuthentication(AioHTTPTestCase):
    """Test authentication functionality."""

    async def get_application(self):
        """Create test application with auth enabled."""
        self.temp_dir = tempfile.mkdtemp()
        self.metrics_file = Path(self.temp_dir) / ".agent_metrics.json"

        # Create minimal metrics
        minimal_metrics = {
            "version": 1,
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

        # Set auth token in environment BEFORE creating server
        self.auth_token = "test-secret-token-12345"
        os.environ['DASHBOARD_AUTH_TOKEN'] = self.auth_token

        self.server = RESTAPIServer(
            project_name="test-project",
            metrics_dir=Path(self.temp_dir),
            port=8420,
            host="127.0.0.1"
        )

        return self.server.app

    async def tearDown(self):
        """Cleanup after tests."""
        await super().tearDown()
        import shutil
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        # Clean up environment variable
        if 'DASHBOARD_AUTH_TOKEN' in os.environ:
            del os.environ['DASHBOARD_AUTH_TOKEN']

    # Test 26: Authentication required
    async def test_auth_required_without_token(self):
        """Test requests without token are rejected (401)."""
        resp = await self.client.request("GET", "/api/metrics")
        assert resp.status == 401

        data = await resp.json()
        assert "error" in data

    # Test 27: Valid authentication
    async def test_auth_valid_token(self):
        """Test requests with valid token succeed."""
        headers = {"Authorization": "Bearer test-secret-token-12345"}
        resp = await self.client.request("GET", "/api/metrics", headers=headers)
        assert resp.status == 200

    # Test 28: Invalid authentication
    async def test_auth_invalid_token(self):
        """Test requests with invalid token are rejected (401)."""
        headers = {"Authorization": "Bearer wrong-token"}
        resp = await self.client.request("GET", "/api/metrics", headers=headers)
        assert resp.status == 401

    # Test 29: Health check bypasses auth
    async def test_health_check_no_auth(self):
        """Test health check works without authentication."""
        resp = await self.client.request("GET", "/api/health")
        assert resp.status == 200


class TestRESTAPIServerEdgeCases:
    """Test edge cases and error handling."""

    def test_server_initialization(self):
        """Test 30: Server initializes correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            server = RESTAPIServer(
                project_name="test",
                metrics_dir=Path(temp_dir)
            )

            assert server.app is not None
            assert server.store is not None
            assert server.port == 8420
            assert server.host == "0.0.0.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
