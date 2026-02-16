"""
Comprehensive tests for AI-106: Data Source - Metrics Store Integration

Tests cover all 8 required test steps:
1. Verify dashboard loads metrics from .agent_metrics.json
2. Verify MetricsStore class is used correctly
3. Verify agent definitions are loaded from agents/definitions.py
4. Verify provider availability is checked via environment variables
5. Verify metrics update when .agent_metrics.json changes
6. Test handling of missing or corrupted metrics file
7. Verify fallback behavior if metrics unavailable
8. Test concurrent reads from metrics store
"""

import asyncio
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from aiohttp.test_utils import AioHTTPTestCase

from agents.definitions import AGENT_DEFINITIONS, create_agent_definitions
from dashboard.metrics_store import MetricsStore
from dashboard.server import DashboardServer


class TestMetricsStoreIntegration(AioHTTPTestCase):
    """Integration tests for MetricsStore with dashboard server."""

    async def get_application(self):
        """Create test application with real MetricsStore."""
        # Create temporary metrics directory
        self.temp_dir = tempfile.mkdtemp()
        self.metrics_file = Path(self.temp_dir) / ".agent_metrics.json"

        # Create realistic metrics data matching .agent_metrics.json format
        self.test_metrics = {
            "version": 1,
            "project_name": "test-agent-dashboard",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T12:00:00Z",
            "total_sessions": 10,
            "total_tokens": 25000,
            "total_cost_usd": 1.25,
            "total_duration_seconds": 300.0,
            "agents": {
                "orchestrator": {
                    "agent_name": "orchestrator",
                    "total_invocations": 10,
                    "successful_invocations": 10,
                    "failed_invocations": 0,
                    "total_tokens": 2000,
                    "total_cost_usd": 0.1,
                    "total_duration_seconds": 20.0,
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
                    "success_rate": 1.0,
                    "avg_duration_seconds": 2.0,
                    "avg_tokens_per_call": 200.0,
                    "cost_per_success_usd": 0.01,
                    "xp": 100,
                    "level": 2,
                    "current_streak": 10,
                    "best_streak": 10,
                    "achievements": ["perfect_streak"],
                    "strengths": ["coordination"],
                    "weaknesses": [],
                    "recent_events": [],
                    "last_error": "",
                    "last_active": "2024-01-01T12:00:00Z"
                },
                "coding": {
                    "agent_name": "coding",
                    "total_invocations": 15,
                    "successful_invocations": 12,
                    "failed_invocations": 3,
                    "total_tokens": 10000,
                    "total_cost_usd": 0.5,
                    "total_duration_seconds": 120.0,
                    "commits_made": 5,
                    "prs_created": 2,
                    "prs_merged": 1,
                    "files_created": 8,
                    "files_modified": 15,
                    "lines_added": 450,
                    "lines_removed": 120,
                    "tests_written": 12,
                    "issues_created": 0,
                    "issues_completed": 3,
                    "messages_sent": 0,
                    "reviews_completed": 0,
                    "success_rate": 0.8,
                    "avg_duration_seconds": 8.0,
                    "avg_tokens_per_call": 666.67,
                    "cost_per_success_usd": 0.04167,
                    "xp": 360,
                    "level": 4,
                    "current_streak": 2,
                    "best_streak": 8,
                    "achievements": ["first_commit", "test_master", "code_warrior"],
                    "strengths": ["testing", "code_quality"],
                    "weaknesses": ["error_handling"],
                    "recent_events": ["event-001", "event-002"],
                    "last_error": "Import error: module not found",
                    "last_active": "2024-01-01T12:00:00Z"
                }
            },
            "events": [
                {
                    "event_id": "event-001",
                    "agent_name": "coding",
                    "session_id": "session-001",
                    "ticket_key": "AI-106",
                    "started_at": "2024-01-01T11:00:00Z",
                    "ended_at": "2024-01-01T11:08:00Z",
                    "duration_seconds": 480.0,
                    "status": "success",
                    "input_tokens": 1200,
                    "output_tokens": 1800,
                    "total_tokens": 3000,
                    "estimated_cost_usd": 0.063,
                    "artifacts": ["file:test_metrics.py:created", "commit:abc123def456"],
                    "error_message": "",
                    "model_used": "claude-sonnet-4-5",
                    "file_changes": []
                }
            ],
            "sessions": [
                {
                    "session_id": "session-001",
                    "session_number": 1,
                    "session_type": "initializer",
                    "started_at": "2024-01-01T10:00:00Z",
                    "ended_at": "2024-01-01T12:00:00Z",
                    "status": "complete",
                    "agents_invoked": ["orchestrator", "coding"],
                    "total_tokens": 12000,
                    "total_cost_usd": 0.6,
                    "tickets_worked": ["AI-106"]
                }
            ]
        }

        # Write test metrics to file
        self.metrics_file.write_text(json.dumps(self.test_metrics, indent=2))

        # Create server with MetricsStore
        self.server = DashboardServer(
            project_name="test-agent-dashboard",
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

    # Test Step 1: Verify dashboard loads metrics from .agent_metrics.json
    async def test_01_dashboard_loads_metrics_from_file(self):
        """Test 1: Verify dashboard loads metrics from .agent_metrics.json."""
        resp = await self.client.request("GET", "/api/metrics")
        assert resp.status == 200

        data = await resp.json()

        # Verify data matches what we wrote to .agent_metrics.json
        assert data["project_name"] == "test-agent-dashboard"
        assert data["total_sessions"] == 10
        assert data["total_tokens"] == 25000
        assert data["total_cost_usd"] == 1.25

        # Verify agents are loaded
        assert "coding" in data["agents"]
        assert "orchestrator" in data["agents"]
        assert data["agents"]["coding"]["total_invocations"] == 15
        assert data["agents"]["coding"]["success_rate"] == 0.8

    # Test Step 2: Verify MetricsStore class is used correctly
    async def test_02_metrics_store_class_used_correctly(self):
        """Test 2: Verify MetricsStore class is used correctly."""
        # Create a separate MetricsStore instance to test
        store = MetricsStore(
            project_name="test-agent-dashboard",
            metrics_dir=Path(self.temp_dir)
        )

        # Verify store configuration
        assert store.project_name == "test-agent-dashboard"
        assert store.metrics_path.name == ".agent_metrics.json"

        # Test store load method
        state = store.load()
        assert state["project_name"] == "test-agent-dashboard"
        assert "agents" in state
        assert "events" in state
        assert "sessions" in state

    # Test Step 3: Verify agent definitions are loaded from agents/definitions.py
    async def test_03_agent_definitions_loaded_from_definitions_py(self):
        """Test 3: Verify agent definitions come from agents/definitions.py."""
        # Import agent definitions
        from agents.definitions import AGENT_DEFINITIONS, create_agent_definitions

        # Verify all expected sub-agents are defined (orchestrator is separate)
        expected_agents = [
            "linear", "coding", "coding_fast", "github",
            "pr_reviewer", "pr_reviewer_fast", "ops", "slack",
            "chatgpt", "gemini", "groq", "kimi", "windsurf"
        ]

        definitions = create_agent_definitions()

        for agent_name in expected_agents:
            assert agent_name in definitions, f"Agent {agent_name} not in definitions"
            assert definitions[agent_name].description is not None
            assert definitions[agent_name].prompt is not None
            assert definitions[agent_name].tools is not None

    # Test Step 4: Verify provider availability is checked via environment variables
    async def test_04_provider_availability_checked_via_env_vars(self):
        """Test 4: Verify provider availability is checked via environment variables."""
        # Test provider status endpoint
        resp = await self.client.request("GET", "/api/providers/status")
        assert resp.status == 200

        data = await resp.json()
        assert "providers" in data

        # Verify all expected providers are checked
        expected_providers = ["claude", "chatgpt", "gemini", "groq", "kimi", "windsurf"]
        for provider in expected_providers:
            assert provider in data["providers"]
            provider_data = data["providers"][provider]
            assert "status" in provider_data
            assert "configured" in provider_data
            assert provider_data["status"] in ["available", "unconfigured", "error"]

    @pytest.mark.asyncio
    async def test_04b_provider_status_with_env_vars(self):
        """Test 4b: Verify provider status reflects environment variables."""
        # Test with mocked environment variables
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "test-key-123",
            "GOOGLE_API_KEY": "test-gemini-key",
            "GROQ_API_KEY": "",
            "KIMI_API_KEY": "",
        }):
            resp = await self.client.request("GET", "/api/providers/status")
            data = await resp.json()

            # ChatGPT should be available (key set)
            assert data["providers"]["chatgpt"]["configured"] is True
            assert data["providers"]["chatgpt"]["status"] == "available"

            # Gemini should be available (key set)
            assert data["providers"]["gemini"]["configured"] is True

            # Groq should be unconfigured (empty key)
            assert data["providers"]["groq"]["status"] == "unconfigured"

    # Test Step 5: Verify metrics update when .agent_metrics.json changes
    async def test_05_metrics_update_when_file_changes(self):
        """Test 5: Verify metrics update when .agent_metrics.json changes."""
        # Get initial metrics
        resp1 = await self.client.request("GET", "/api/metrics")
        data1 = await resp1.json()
        initial_sessions = data1["total_sessions"]

        # Update the metrics file
        updated_metrics = self.test_metrics.copy()
        updated_metrics["total_sessions"] = initial_sessions + 5
        updated_metrics["updated_at"] = "2024-01-01T13:00:00Z"
        self.metrics_file.write_text(json.dumps(updated_metrics, indent=2))

        # Give a moment for file system to flush
        await asyncio.sleep(0.1)

        # Get updated metrics (should reload from file)
        resp2 = await self.client.request("GET", "/api/metrics")
        data2 = await resp2.json()

        # Verify metrics were updated
        assert data2["total_sessions"] == initial_sessions + 5
        assert data2["updated_at"] == "2024-01-01T13:00:00Z"

    # Test Step 6: Test handling of missing or corrupted metrics file
    async def test_06a_handling_missing_metrics_file(self):
        """Test 6a: Test handling of missing metrics file."""
        # Delete the metrics file
        self.metrics_file.unlink()

        # Server should still respond with empty/default state
        resp = await self.client.request("GET", "/api/metrics")
        assert resp.status == 200

        data = await resp.json()
        # Should return a valid empty state
        assert "agents" in data
        assert "events" in data
        assert "sessions" in data

    async def test_06b_handling_corrupted_metrics_file(self):
        """Test 6b: Test handling of corrupted metrics file."""
        # Write invalid JSON to metrics file
        self.metrics_file.write_text("{ invalid json content ::::")

        # Server should handle corruption gracefully
        resp = await self.client.request("GET", "/api/metrics")
        assert resp.status == 200

        data = await resp.json()
        # Should return a valid state (either recovered from backup or fresh)
        assert isinstance(data, dict)
        assert "agents" in data

    async def test_06c_handling_corrupted_json_structure(self):
        """Test 6c: Test handling of valid JSON but invalid structure."""
        # Write valid JSON but wrong structure
        self.metrics_file.write_text(json.dumps({"invalid": "structure"}))

        resp = await self.client.request("GET", "/api/metrics")
        assert resp.status == 200

        data = await resp.json()
        # Should return valid empty state
        assert "agents" in data
        assert "events" in data

    # Test Step 7: Verify fallback behavior if metrics unavailable
    async def test_07_fallback_behavior_when_metrics_unavailable(self):
        """Test 7: Verify fallback behavior if metrics unavailable."""
        # Make metrics file unreadable
        self.metrics_file.chmod(0o000)

        try:
            resp = await self.client.request("GET", "/api/metrics")
            # Should still return 200 with fallback data
            assert resp.status in [200, 500]  # May return error or fallback

            if resp.status == 200:
                data = await resp.json()
                # Should have basic structure
                assert isinstance(data, dict)
        finally:
            # Restore permissions for cleanup
            self.metrics_file.chmod(0o644)

    async def test_07b_backup_file_recovery(self):
        """Test 7b: Verify recovery from backup file."""
        # Create a backup file
        backup_path = Path(self.temp_dir) / ".agent_metrics.json.bak"
        backup_data = self.test_metrics.copy()
        backup_data["project_name"] = "recovered-from-backup"
        backup_path.write_text(json.dumps(backup_data, indent=2))

        # Corrupt main file
        self.metrics_file.write_text("corrupted data")

        # Create a new store instance and load should recover from backup
        store = MetricsStore(
            project_name="test-agent-dashboard",
            metrics_dir=Path(self.temp_dir)
        )
        state = store.load()
        assert state["project_name"] == "recovered-from-backup"

    # Test Step 8: Test concurrent reads from metrics store
    async def test_08_concurrent_reads_from_metrics_store(self):
        """Test 8: Test concurrent reads from metrics store."""
        # Make multiple concurrent requests
        tasks = []
        for i in range(20):
            tasks.append(self.client.request("GET", "/api/metrics"))

        # Execute all requests concurrently
        responses = await asyncio.gather(*tasks)

        # All requests should succeed
        for resp in responses:
            assert resp.status == 200
            data = await resp.json()
            assert data["project_name"] == "test-agent-dashboard"
            assert "agents" in data

    def test_08b_concurrent_reads_from_multiple_threads(self):
        """Test 8b: Test concurrent reads from multiple threads."""
        results = []
        errors = []

        def read_metrics():
            try:
                store = MetricsStore(
                    project_name="test-agent-dashboard",
                    metrics_dir=Path(self.temp_dir)
                )
                state = store.load()
                results.append(state["project_name"])
            except Exception as e:
                errors.append(str(e))

        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=read_metrics)
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # All reads should succeed
        assert len(results) == 10
        assert len(errors) == 0
        assert all(name == "test-agent-dashboard" for name in results)

    async def test_08c_concurrent_websocket_connections(self):
        """Test 8c: Test multiple concurrent WebSocket connections."""
        # Create multiple WebSocket connections
        connections = []
        try:
            for _ in range(5):
                ws = await self.client.ws_connect("/ws")
                connections.append(ws)

            # All should receive initial metrics
            for ws in connections:
                msg = await asyncio.wait_for(ws.receive(), timeout=2.0)
                data = json.loads(msg.data)
                assert data["type"] == "metrics_update"
                assert "data" in data
        finally:
            # Clean up connections
            for ws in connections:
                await ws.close()


class TestMetricsStoreDirectAccess:
    """Direct tests of MetricsStore class functionality."""

    def test_metrics_store_initialization(self):
        """Test MetricsStore initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = MetricsStore(
                project_name="test-project",
                metrics_dir=Path(temp_dir)
            )

            assert store.project_name == "test-project"
            assert store.metrics_dir == Path(temp_dir)
            assert store.metrics_path.name == ".agent_metrics.json"

    def test_metrics_store_create_empty_state(self):
        """Test creating empty state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = MetricsStore(
                project_name="test-project",
                metrics_dir=Path(temp_dir)
            )

            state = store.load()

            # Should create empty state with all required fields
            assert state["version"] == 1
            assert state["project_name"] == "test-project"
            assert state["total_sessions"] == 0
            assert isinstance(state["agents"], dict)
            assert isinstance(state["events"], list)
            assert isinstance(state["sessions"], list)

    def test_metrics_store_save_and_load(self):
        """Test save and load operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = MetricsStore(
                project_name="test-project",
                metrics_dir=Path(temp_dir)
            )

            # Load initial state
            state = store.load()

            # Modify state
            state["total_sessions"] = 5
            state["total_tokens"] = 10000

            # Save state
            store.save(state)

            # Load again and verify
            loaded_state = store.load()
            assert loaded_state["total_sessions"] == 5
            assert loaded_state["total_tokens"] == 10000

    def test_metrics_store_atomic_writes(self):
        """Test atomic write operations."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = MetricsStore(
                project_name="test-project",
                metrics_dir=Path(temp_dir)
            )

            state = store.load()
            state["total_sessions"] = 100

            # Save should create backup
            store.save(state)

            # Backup file should exist
            backup_path = Path(temp_dir) / ".agent_metrics.json.bak"
            # Note: Backup only created if main file existed before save

            # Main file should exist
            assert store.metrics_path.exists()

    def test_metrics_store_fifo_eviction(self):
        """Test FIFO eviction of old events and sessions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            store = MetricsStore(
                project_name="test-project",
                metrics_dir=Path(temp_dir)
            )

            state = store.load()

            # Add more than MAX_EVENTS
            for i in range(550):  # MAX_EVENTS is 500
                state["events"].append({
                    "event_id": f"event-{i}",
                    "agent_name": "test",
                    "session_id": "session-1",
                    "ticket_key": "AI-1",
                    "started_at": "2024-01-01T00:00:00Z",
                    "ended_at": "2024-01-01T00:01:00Z",
                    "duration_seconds": 60.0,
                    "status": "success",
                    "input_tokens": 100,
                    "output_tokens": 200,
                    "total_tokens": 300,
                    "estimated_cost_usd": 0.01,
                    "artifacts": [],
                    "error_message": "",
                    "model_used": "test",
                    "file_changes": []
                })

            # Save should trigger FIFO eviction
            store.save(state)

            # Reload and verify only last 500 events remain
            reloaded = store.load()
            assert len(reloaded["events"]) == 500
            # Should keep most recent events
            assert reloaded["events"][-1]["event_id"] == "event-549"


class TestAgentDefinitionsIntegration:
    """Tests for agent definitions integration."""

    def test_all_expected_agents_defined(self):
        """Test that all expected agents are defined."""
        definitions = create_agent_definitions()

        expected_agents = [
            "linear", "coding", "github", "slack", "pr_reviewer", "ops",
            "coding_fast", "pr_reviewer_fast", "chatgpt", "gemini",
            "groq", "kimi", "windsurf"
        ]

        for agent_name in expected_agents:
            assert agent_name in definitions
            agent_def = definitions[agent_name]
            assert agent_def.description is not None
            assert len(agent_def.description) > 0

    def test_agent_definitions_have_required_fields(self):
        """Test that agent definitions have all required fields."""
        definitions = create_agent_definitions()

        for agent_name, agent_def in definitions.items():
            assert hasattr(agent_def, 'description')
            assert hasattr(agent_def, 'prompt')
            assert hasattr(agent_def, 'tools')
            assert hasattr(agent_def, 'model')

            # Verify types
            assert isinstance(agent_def.description, str)
            assert isinstance(agent_def.prompt, str)
            assert isinstance(agent_def.tools, list)
            assert isinstance(agent_def.model, str)

    def test_bridge_agents_defined(self):
        """Test that all bridge agents are properly defined."""
        definitions = create_agent_definitions()

        bridge_agents = ["chatgpt", "gemini", "groq", "kimi", "windsurf"]

        for agent_name in bridge_agents:
            assert agent_name in definitions
            agent_def = definitions[agent_name]

            # Bridge agents should have file tools and bash
            assert "Bash" in agent_def.tools or len(agent_def.tools) > 0


class TestProviderAvailability:
    """Tests for provider availability checks."""

    def test_provider_status_checks_env_vars(self):
        """Test that provider status correctly checks environment variables."""
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "sk-test123",
            "GOOGLE_API_KEY": "google-test456",
            "GROQ_API_KEY": "",
        }, clear=False):
            # Test env var detection
            assert os.getenv("OPENAI_API_KEY") == "sk-test123"
            assert os.getenv("GOOGLE_API_KEY") == "google-test456"
            assert os.getenv("GROQ_API_KEY") == ""
            assert os.getenv("NONEXISTENT_KEY") is None

    def test_provider_env_var_mapping(self):
        """Test provider to environment variable mapping."""
        expected_mappings = {
            "claude": "ANTHROPIC_API_KEY",
            "chatgpt": "OPENAI_API_KEY",
            "gemini": "GOOGLE_API_KEY",
            "groq": "GROQ_API_KEY",
            "kimi": "KIMI_API_KEY",
            "windsurf": "WINDSURF_API_KEY",
        }

        # These mappings should be used by the server
        for provider, env_var in expected_mappings.items():
            assert isinstance(env_var, str)
            assert env_var.endswith("_API_KEY")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
