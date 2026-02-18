"""Tests for AI-185: Graceful Degradation for Missing/Corrupted Metrics (REQ-REL-003).

Verifies that:
- Missing .agent_metrics.json → empty state, no crash
- Corrupted JSON → empty state, no crash, warning logged
- AgentMetricsCollector.is_healthy() returns True/False correctly
- AgentMetricsCollector.get_degradation_reason() returns None or descriptive string
- GET /api/health/metrics returns proper JSON
- Server continues serving after metrics file disappears
- Fresh file created by collector when missing
- MetricsStore.load() logs a warning when JSON is corrupted
"""

import json
import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop

# Import the modules under test
from dashboard.collector import AgentMetricsCollector
from dashboard.metrics_store import MetricsStore
from dashboard.server import DashboardServer


# ─────────────────────────────────────────────
# Helper fixtures
# ─────────────────────────────────────────────

def make_collector(tmp_path: Path) -> AgentMetricsCollector:
    """Create a collector using a temp directory."""
    return AgentMetricsCollector(project_name="test-project", metrics_dir=tmp_path)


def make_store(tmp_path: Path) -> MetricsStore:
    """Create a MetricsStore using a temp directory."""
    return MetricsStore(project_name="test-project", metrics_dir=tmp_path)


def write_valid_metrics(tmp_path: Path) -> Path:
    """Write a minimal valid .agent_metrics.json file and return its path."""
    store = make_store(tmp_path)
    state = store._create_empty_state()
    store.save(state)
    return store.metrics_path


def write_corrupt_metrics(tmp_path: Path) -> Path:
    """Write an intentionally broken JSON file and return its path."""
    metrics_path = tmp_path / ".agent_metrics.json"
    metrics_path.write_text("{ this is not valid json !!!", encoding="utf-8")
    return metrics_path


# ─────────────────────────────────────────────
# Test Group 1: Missing metrics file
# ─────────────────────────────────────────────

def test_missing_file_no_crash():
    """Collector does not crash when .agent_metrics.json is missing."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        collector = make_collector(tmp_path)
        # get_state() should not raise
        state = collector.get_state()
        assert state is not None


def test_missing_file_returns_empty_state():
    """get_state() returns a valid DashboardState with zero counters when file is missing."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        collector = make_collector(tmp_path)
        state = collector.get_state()
        assert state["total_sessions"] == 0
        assert state["total_tokens"] == 0
        assert isinstance(state["agents"], dict)
        assert isinstance(state["events"], list)
        assert state["events"] == []


def test_missing_file_is_healthy_returns_false():
    """is_healthy() returns False when .agent_metrics.json does not exist."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        collector = make_collector(tmp_path)
        assert collector.is_healthy() is False


def test_missing_file_degradation_reason_not_none():
    """get_degradation_reason() returns a non-None string when file is missing."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        collector = make_collector(tmp_path)
        reason = collector.get_degradation_reason()
        assert reason is not None
        assert isinstance(reason, str)
        assert len(reason) > 0


def test_missing_file_degradation_reason_mentions_missing():
    """get_degradation_reason() mentions 'missing' when file does not exist."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        collector = make_collector(tmp_path)
        reason = collector.get_degradation_reason()
        assert "missing" in reason.lower() or "exist" in reason.lower()


# ─────────────────────────────────────────────
# Test Group 2: Corrupted JSON
# ─────────────────────────────────────────────

def test_corrupted_json_no_crash():
    """Collector does not crash when .agent_metrics.json contains invalid JSON."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        write_corrupt_metrics(tmp_path)
        collector = make_collector(tmp_path)
        state = collector.get_state()
        assert state is not None


def test_corrupted_json_returns_empty_state():
    """get_state() returns a valid empty DashboardState when JSON is corrupted."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        write_corrupt_metrics(tmp_path)
        collector = make_collector(tmp_path)
        state = collector.get_state()
        assert isinstance(state["events"], list)
        assert isinstance(state["agents"], dict)


def test_corrupted_json_is_healthy_returns_false():
    """is_healthy() returns False when .agent_metrics.json contains invalid JSON."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        write_corrupt_metrics(tmp_path)
        collector = make_collector(tmp_path)
        assert collector.is_healthy() is False


def test_corrupted_json_degradation_reason_not_none():
    """get_degradation_reason() returns a string when JSON is corrupted."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        write_corrupt_metrics(tmp_path)
        collector = make_collector(tmp_path)
        reason = collector.get_degradation_reason()
        assert reason is not None
        assert isinstance(reason, str)


def test_corrupted_json_degradation_reason_mentions_corrupt():
    """get_degradation_reason() mentions 'corrupt' or 'invalid' when JSON is bad."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        write_corrupt_metrics(tmp_path)
        collector = make_collector(tmp_path)
        reason = collector.get_degradation_reason()
        assert any(word in reason.lower() for word in ("corrupt", "invalid", "json"))


def test_corrupted_json_logs_warning(caplog):
    """MetricsStore.load() emits a WARNING log when JSON is corrupted."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        write_corrupt_metrics(tmp_path)
        store = make_store(tmp_path)
        with caplog.at_level(logging.WARNING, logger="dashboard.metrics_store"):
            store.load()
        assert any("corrupt" in r.message.lower() or "invalid" in r.message.lower()
                   for r in caplog.records), \
            "Expected a WARNING log about corrupted metrics but none found"


# ─────────────────────────────────────────────
# Test Group 3: is_healthy() with valid file
# ─────────────────────────────────────────────

def test_is_healthy_returns_true_with_valid_file():
    """is_healthy() returns True when a valid .agent_metrics.json file exists."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        write_valid_metrics(tmp_path)
        collector = make_collector(tmp_path)
        assert collector.is_healthy() is True


def test_get_degradation_reason_returns_none_when_healthy():
    """get_degradation_reason() returns None when metrics file is present and valid."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        write_valid_metrics(tmp_path)
        collector = make_collector(tmp_path)
        assert collector.get_degradation_reason() is None


# ─────────────────────────────────────────────
# Test Group 4: GET /api/health/metrics
# ─────────────────────────────────────────────

class TestMetricsHealthEndpoint(AioHTTPTestCase):
    """Integration tests for GET /api/health/metrics."""

    async def get_application(self):
        """Create a DashboardServer app with a temp directory."""
        self._tmp = tempfile.TemporaryDirectory()
        self._tmp_path = Path(self._tmp.name)
        self._server = DashboardServer(
            project_name="test-project",
            metrics_dir=self._tmp_path,
        )
        return self._server.app

    async def tearDownAsync(self):
        self._tmp.cleanup()

    @unittest_run_loop
    async def test_health_metrics_endpoint_returns_200(self):
        """GET /api/health/metrics returns HTTP 200."""
        resp = await self.client.get("/api/health/metrics")
        assert resp.status == 200

    @unittest_run_loop
    async def test_health_metrics_returns_json(self):
        """GET /api/health/metrics returns valid JSON."""
        resp = await self.client.get("/api/health/metrics")
        data = await resp.json()
        assert isinstance(data, dict)

    @unittest_run_loop
    async def test_health_metrics_has_healthy_field(self):
        """GET /api/health/metrics response includes 'healthy' boolean field."""
        resp = await self.client.get("/api/health/metrics")
        data = await resp.json()
        assert "healthy" in data
        assert isinstance(data["healthy"], bool)

    @unittest_run_loop
    async def test_health_metrics_has_degradation_reason_field(self):
        """GET /api/health/metrics response includes 'degradation_reason' field."""
        resp = await self.client.get("/api/health/metrics")
        data = await resp.json()
        assert "degradation_reason" in data

    @unittest_run_loop
    async def test_health_metrics_has_metrics_file_exists_field(self):
        """GET /api/health/metrics response includes 'metrics_file_exists' field."""
        resp = await self.client.get("/api/health/metrics")
        data = await resp.json()
        assert "metrics_file_exists" in data

    @unittest_run_loop
    async def test_health_metrics_has_timestamp_field(self):
        """GET /api/health/metrics response includes 'timestamp' field."""
        resp = await self.client.get("/api/health/metrics")
        data = await resp.json()
        assert "timestamp" in data

    @unittest_run_loop
    async def test_health_metrics_unhealthy_when_file_missing(self):
        """GET /api/health/metrics reports healthy=false when file is absent."""
        resp = await self.client.get("/api/health/metrics")
        data = await resp.json()
        # No file was written, so should be unhealthy
        assert data["healthy"] is False
        assert data["degradation_reason"] is not None

    @unittest_run_loop
    async def test_health_metrics_healthy_when_file_present(self):
        """GET /api/health/metrics reports healthy=true after a valid file is written."""
        # Write a valid metrics file
        store = make_store(self._tmp_path)
        state = store._create_empty_state()
        store.save(state)

        resp = await self.client.get("/api/health/metrics")
        data = await resp.json()
        assert data["healthy"] is True
        assert data["degradation_reason"] is None


# ─────────────────────────────────────────────
# Test Group 5: Server continuity after file disappears
# ─────────────────────────────────────────────

def test_server_continues_after_metrics_file_disappears():
    """MetricsStore.load() does not raise even after file is deleted mid-run."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        store = make_store(tmp_path)
        # Write a valid file
        state = store._create_empty_state()
        store.save(state)
        assert store.metrics_path.exists()

        # Delete the file
        store.metrics_path.unlink()

        # load() should still work, returning an empty state
        recovered = store.load()
        assert recovered is not None
        assert isinstance(recovered["events"], list)


def test_fresh_file_created_by_start_session():
    """Collector creates a fresh metrics file when start_session() is called."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        collector = make_collector(tmp_path)
        metrics_path = collector.store.metrics_path
        assert not metrics_path.exists(), "File should not exist before use"

        session_id = collector.start_session()
        collector.end_session(session_id, status="complete")

        assert metrics_path.exists(), "Metrics file should be created after end_session()"


def test_invalid_structure_treated_as_corrupt():
    """MetricsStore.load() returns fresh state when JSON is valid but structure is wrong."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        metrics_path = tmp_path / ".agent_metrics.json"
        # Write JSON that is syntactically valid but missing required fields
        metrics_path.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
        store = make_store(tmp_path)
        state = store.load()
        # Should fall back to fresh state without crashing
        assert isinstance(state["events"], list)
        assert state["total_sessions"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
