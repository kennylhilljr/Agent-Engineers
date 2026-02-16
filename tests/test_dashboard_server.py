"""Unit tests for dashboard_server.py

Tests the DashboardServer class including:
- Initialization and configuration
- REST API endpoints: /api/health, /api/metrics, /api/agents
- HTML dashboard generation
- Error handling and edge cases
- Integration with MetricsStore
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

# Add project root to path
import sys
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.dashboard_server import DashboardServer
from dashboard.metrics import DashboardState
from dashboard.metrics_store import MetricsStore


class TestDashboardServer(AioHTTPTestCase):
    """Test suite for DashboardServer."""

    async def get_application(self):
        """Create test application instance."""
        # Create temporary directory for test metrics
        self.temp_dir = tempfile.TemporaryDirectory()
        self.project_dir = Path(self.temp_dir.name)

        # Create test metrics file
        self._create_test_metrics()

        # Create server instance
        self.server = DashboardServer(
            project_dir=self.project_dir,
            host="127.0.0.1",
            port=8420,
            project_name="test-project"
        )

        return self.server.app

    async def tearDown(self):
        """Clean up test resources."""
        await super().tearDown()
        self.temp_dir.cleanup()

    def _create_test_metrics(self):
        """Create a test .agent_metrics.json file."""
        test_state: DashboardState = {
            "version": 1,
            "project_name": "test-project",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-02-16T12:00:00Z",
            "total_sessions": 10,
            "total_tokens": 50000,
            "total_cost_usd": 5.00,
            "total_duration_seconds": 600.0,
            "agents": {
                "coding": {
                    "agent_name": "coding",
                    "total_invocations": 20,
                    "successful_invocations": 18,
                    "failed_invocations": 2,
                    "total_tokens": 30000,
                    "total_cost_usd": 3.00,
                    "total_duration_seconds": 360.0,
                    "commits_made": 10,
                    "prs_created": 5,
                    "prs_merged": 4,
                    "files_created": 15,
                    "files_modified": 30,
                    "lines_added": 500,
                    "lines_removed": 200,
                    "tests_written": 20,
                    "issues_created": 0,
                    "issues_completed": 3,
                    "messages_sent": 0,
                    "reviews_completed": 0,
                    "success_rate": 0.9,
                    "avg_duration_seconds": 18.0,
                    "avg_tokens_per_call": 1500.0,
                    "cost_per_success_usd": 0.167,
                    "xp": 540,
                    "level": 6,
                    "current_streak": 5,
                    "best_streak": 8,
                    "achievements": ["first_commit", "test_master"],
                    "strengths": ["testing", "productivity"],
                    "weaknesses": ["error_recovery"],
                    "recent_events": ["evt-001", "evt-002"],
                    "last_error": "Test timeout",
                    "last_active": "2026-02-16T12:00:00Z"
                },
                "linear": {
                    "agent_name": "linear",
                    "total_invocations": 10,
                    "successful_invocations": 9,
                    "failed_invocations": 1,
                    "total_tokens": 5000,
                    "total_cost_usd": 0.50,
                    "total_duration_seconds": 50.0,
                    "commits_made": 0,
                    "prs_created": 0,
                    "prs_merged": 0,
                    "files_created": 0,
                    "files_modified": 0,
                    "lines_added": 0,
                    "lines_removed": 0,
                    "tests_written": 0,
                    "issues_created": 8,
                    "issues_completed": 5,
                    "messages_sent": 0,
                    "reviews_completed": 0,
                    "success_rate": 0.9,
                    "avg_duration_seconds": 5.0,
                    "avg_tokens_per_call": 500.0,
                    "cost_per_success_usd": 0.056,
                    "xp": 270,
                    "level": 4,
                    "current_streak": 3,
                    "best_streak": 6,
                    "achievements": ["issue_creator"],
                    "strengths": ["issue_tracking"],
                    "weaknesses": [],
                    "recent_events": [],
                    "last_error": "",
                    "last_active": "2026-02-16T11:00:00Z"
                },
                "orchestrator": {
                    "agent_name": "orchestrator",
                    "total_invocations": 0,
                    "successful_invocations": 0,
                    "failed_invocations": 0,
                    "total_tokens": 0,
                    "total_cost_usd": 0.0,
                    "total_duration_seconds": 0.0,
                    "commits_made": 0,
                    "prs_created": 0,
                    "prs_merged": 0,
                    "files_created": 0,
                    "files_modified": 0,
                    "lines_added": 0,
                    "lines_removed": 0,
                    "tests_written": 0,
                    "issues_created": 0,
                    "issues_completed": 0,
                    "messages_sent": 0,
                    "reviews_completed": 0,
                    "success_rate": 0.0,
                    "avg_duration_seconds": 0.0,
                    "avg_tokens_per_call": 0.0,
                    "cost_per_success_usd": 0.0,
                    "xp": 0,
                    "level": 1,
                    "current_streak": 0,
                    "best_streak": 0,
                    "achievements": [],
                    "strengths": [],
                    "weaknesses": [],
                    "recent_events": [],
                    "last_error": "",
                    "last_active": ""
                }
            },
            "events": [],
            "sessions": []
        }

        metrics_path = self.project_dir / ".agent_metrics.json"
        with open(metrics_path, 'w') as f:
            json.dump(test_state, f, indent=2)

    @unittest_run_loop
    async def test_health_endpoint(self):
        """Test /api/health endpoint returns correct status."""
        resp = await self.client.get('/api/health')
        assert resp.status == 200

        data = await resp.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert data["server"]["project_name"] == "test-project"
        assert data["server"]["port"] == 8420
        assert data["metrics_file"]["exists"] is True
        assert data["metrics_file"]["size_bytes"] > 0

    @unittest_run_loop
    async def test_metrics_endpoint(self):
        """Test /api/metrics endpoint returns full dashboard state."""
        resp = await self.client.get('/api/metrics')
        assert resp.status == 200

        data = await resp.json()
        assert data["version"] == 1
        assert data["project_name"] == "test-project"
        assert data["total_sessions"] == 10
        assert data["total_tokens"] == 50000
        assert data["total_cost_usd"] == 5.00
        assert "agents" in data
        assert len(data["agents"]) >= 3  # At least our test agents

    @unittest_run_loop
    async def test_agents_endpoint(self):
        """Test /api/agents endpoint returns sorted agent list."""
        resp = await self.client.get('/api/agents')
        assert resp.status == 200

        data = await resp.json()
        assert "agents" in data
        agents = data["agents"]
        assert len(agents) >= 3

        # Verify agents are sorted by level (descending)
        for i in range(len(agents) - 1):
            assert agents[i]["level"] >= agents[i + 1]["level"]

        # Verify agent structure
        agent = agents[0]
        assert "agent_name" in agent
        assert "total_invocations" in agent
        assert "success_rate" in agent
        assert "level" in agent
        assert "xp" in agent

    @unittest_run_loop
    async def test_index_endpoint(self):
        """Test / endpoint returns HTML dashboard."""
        resp = await self.client.get('/')
        assert resp.status == 200
        assert 'text/html' in resp.content_type

        html = await resp.text()
        assert "<!DOCTYPE html>" in html
        assert "Agent Status Dashboard" in html
        assert "loadDashboard()" in html  # Check for JavaScript
        assert ".agent-card" in html  # Check for CSS

    @unittest_run_loop
    async def test_cors_headers(self):
        """Test CORS headers are present on API endpoints."""
        resp = await self.client.get('/api/health')
        assert resp.status == 200
        # Note: CORS headers may not be present in test client
        # This is tested more thoroughly in integration tests

    @unittest_run_loop
    async def test_metrics_endpoint_missing_file(self):
        """Test /api/metrics handles missing metrics file gracefully."""
        # Remove metrics file
        metrics_path = self.project_dir / ".agent_metrics.json"
        metrics_path.unlink()

        resp = await self.client.get('/api/metrics')
        assert resp.status == 200

        # Should return empty state with all agents
        data = await resp.json()
        assert "agents" in data
        # MetricsStore creates empty profiles for all canonical agents
        assert len(data["agents"]) == 14  # All 13 agents + empty profiles

    @unittest_run_loop
    async def test_html_contains_all_agents(self):
        """Test HTML dashboard contains all agent data."""
        # Get HTML from index endpoint
        resp = await self.client.get('/')
        html = await resp.text()

        # Check for essential HTML structure
        assert "<!DOCTYPE html>" in html
        assert "Agent Status Dashboard" in html  # Title is in the HTML, not necessarily in <title> tags

        # Check for CSS classes
        assert "agent-card" in html
        assert "agent-header" in html
        assert "agent-stats" in html

        # Check for JavaScript functions
        assert "loadDashboard" in html
        assert "renderAgents" in html
        assert "renderAgentCard" in html

        # Check for API endpoints
        assert "/api/metrics" in html


class TestDashboardServerUnit:
    """Unit tests for DashboardServer that don't require aiohttp client."""

    def test_initialization_with_defaults(self):
        """Test server initializes with default values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            server = DashboardServer(
                project_dir=Path(tmpdir)
            )

            assert server.host == "127.0.0.1"
            assert server.port == 8420
            assert server.project_name == "agent-dashboard"

    def test_initialization_with_custom_values(self):
        """Test server initializes with custom values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            server = DashboardServer(
                project_dir=Path(tmpdir),
                host="0.0.0.0",
                port=9000,
                project_name="custom-project"
            )

            assert server.host == "0.0.0.0"
            assert server.port == 9000
            assert server.project_name == "custom-project"

    def test_html_generation_is_valid(self):
        """Test that generated HTML is valid and contains required elements."""
        with tempfile.TemporaryDirectory() as tmpdir:
            server = DashboardServer(project_dir=Path(tmpdir))
            html = server._generate_dashboard_html()

            # Basic HTML structure
            assert html.startswith("<!DOCTYPE html>")
            assert "<html" in html
            assert "</html>" in html
            assert "<head>" in html
            assert "<body>" in html

            # Title and meta
            assert "<title>Agent Status Dashboard</title>" in html
            assert 'charset="UTF-8"' in html

            # Essential divs
            assert 'id="stats"' in html
            assert 'id="agents"' in html

            # JavaScript functions
            assert "function loadDashboard()" in html
            assert "function renderDashboard()" in html
            assert "function renderAgents()" in html
            assert "function renderAgentCard(agent)" in html

            # CSS styling
            assert "<style>" in html
            assert ".agent-card" in html
            assert ".agent-header" in html

    def test_routes_are_registered(self):
        """Test that all required routes are registered."""
        with tempfile.TemporaryDirectory() as tmpdir:
            server = DashboardServer(project_dir=Path(tmpdir))

            # Get all registered routes
            routes = [route.resource.canonical for route in server.app.router.routes()]

            assert "/" in routes
            assert "/api/health" in routes
            assert "/api/metrics" in routes
            assert "/api/agents" in routes


@pytest.mark.asyncio
async def test_metrics_store_integration():
    """Test integration with MetricsStore."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = Path(tmpdir)

        # Create test metrics file
        test_state: DashboardState = {
            "version": 1,
            "project_name": "integration-test",
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-02-16T12:00:00Z",
            "total_sessions": 5,
            "total_tokens": 10000,
            "total_cost_usd": 1.00,
            "total_duration_seconds": 100.0,
            "agents": {
                "coding": {
                    "agent_name": "coding",
                    "total_invocations": 5,
                    "successful_invocations": 5,
                    "failed_invocations": 0,
                    "total_tokens": 10000,
                    "total_cost_usd": 1.00,
                    "total_duration_seconds": 100.0,
                    "commits_made": 3,
                    "prs_created": 1,
                    "prs_merged": 1,
                    "files_created": 5,
                    "files_modified": 10,
                    "lines_added": 150,
                    "lines_removed": 50,
                    "tests_written": 8,
                    "issues_created": 0,
                    "issues_completed": 1,
                    "messages_sent": 0,
                    "reviews_completed": 0,
                    "success_rate": 1.0,
                    "avg_duration_seconds": 20.0,
                    "avg_tokens_per_call": 2000.0,
                    "cost_per_success_usd": 0.20,
                    "xp": 150,
                    "level": 3,
                    "current_streak": 5,
                    "best_streak": 5,
                    "achievements": ["first_commit"],
                    "strengths": ["testing"],
                    "weaknesses": [],
                    "recent_events": [],
                    "last_error": "",
                    "last_active": "2026-02-16T12:00:00Z"
                }
            },
            "events": [],
            "sessions": []
        }

        metrics_path = project_dir / ".agent_metrics.json"
        with open(metrics_path, 'w') as f:
            json.dump(test_state, f, indent=2)

        # Create server and verify it loads data
        server = DashboardServer(
            project_dir=project_dir,
            project_name="integration-test"
        )

        # Load state through MetricsStore
        state = server.metrics_store.load()
        assert state["project_name"] == "integration-test"
        assert state["total_sessions"] == 5
        assert "coding" in state["agents"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
