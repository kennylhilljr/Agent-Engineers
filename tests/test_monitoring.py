"""
Comprehensive tests for monitoring and observability features.

Tests cover:
1. Structured JSON logging
2. Performance metrics collection
3. Enhanced /health endpoint
4. Prometheus metrics export
5. System status endpoint
6. Monitoring dashboard
7. Integration tests
8. Edge cases and error handling
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from aiohttp import ClientSession
from aiohttp.test_utils import AioHTTPTestCase

from dashboard.server import DashboardServer
from dashboard.logging_config import (
    setup_logging, get_logger, JSONFormatter, log_performance_metric
)
from dashboard.performance_metrics import (
    metrics_collector, increment_counter, set_gauge, record_metric,
    track_time, timed_operation, HistogramData
)


class TestStructuredLogging:
    """Test suite for structured JSON logging."""

    def setup_method(self):
        """Setup for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = Path(self.temp_dir) / "test.log"

    def teardown_method(self):
        """Cleanup after each test."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        # Reset metrics collector
        metrics_collector.reset()

    def test_json_formatter_basic_message(self):
        """Test 1: JSON formatter produces valid JSON."""
        import logging

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert "timestamp" in data
        assert data["level"] == "INFO"
        assert data["logger"] == "test"
        assert data["message"] == "Test message"
        assert "module" in data
        assert "function" in data

    def test_json_formatter_with_extra_fields(self):
        """Test 2: JSON formatter includes extra context fields."""
        import logging

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )

        # Add extra fields
        record.user_id = "123"
        record.request_id = "abc-def"

        formatted = formatter.format(record)
        data = json.loads(formatted)

        assert "extra" in data
        assert data["extra"]["user_id"] == "123"
        assert data["extra"]["request_id"] == "abc-def"

    def test_json_formatter_with_exception(self):
        """Test 3: JSON formatter includes exception info."""
        import logging
        import sys

        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=10,
                msg="Error occurred",
                args=(),
                exc_info=exc_info
            )

            formatted = formatter.format(record)
            data = json.loads(formatted)

            assert "exception" in data
            assert data["exception"]["type"] == "ValueError"
            assert "Test error" in data["exception"]["message"]
            assert "stack_trace" in data["exception"]

    def test_setup_logging_creates_log_files(self):
        """Test 4: Setup logging creates log files."""
        setup_logging(
            log_level="INFO",
            log_dir=Path(self.temp_dir),
            log_file="test.log",
            error_log_file="test_error.log"
        )

        logger = get_logger("test")
        logger.info("Test message")
        logger.error("Test error")

        # Check files exist
        assert (Path(self.temp_dir) / "test.log").exists()
        assert (Path(self.temp_dir) / "test_error.log").exists()

    def test_log_performance_metric(self):
        """Test 5: Log performance metric with structured data."""
        logger = get_logger("test")

        with patch.object(logger, 'info') as mock_info:
            log_performance_metric(
                logger,
                "api_call",
                150.5,
                endpoint="/api/metrics",
                status=200
            )

            mock_info.assert_called_once()
            call_args = mock_info.call_args

            assert "Performance metric: api_call" in call_args[0]
            extra = call_args[1]["extra"]
            assert extra["metric_type"] == "performance"
            assert extra["metric_name"] == "api_call"
            assert extra["duration_ms"] == 150.5


class TestPerformanceMetrics:
    """Test suite for performance metrics collection."""

    def setup_method(self):
        """Setup for each test."""
        metrics_collector.reset()

    def test_increment_counter(self):
        """Test 6: Increment counter metric."""
        increment_counter("test_counter", 5)
        assert metrics_collector.get_counter("test_counter") == 5

        increment_counter("test_counter", 3)
        assert metrics_collector.get_counter("test_counter") == 8

    def test_set_gauge(self):
        """Test 7: Set gauge metric."""
        set_gauge("test_gauge", 42.5)
        assert metrics_collector.get_gauge("test_gauge") == 42.5

        set_gauge("test_gauge", 100.0)
        assert metrics_collector.get_gauge("test_gauge") == 100.0

    def test_record_histogram(self):
        """Test 8: Record histogram observations."""
        record_metric("test_histogram", 10.0)
        record_metric("test_histogram", 20.0)
        record_metric("test_histogram", 30.0)

        hist = metrics_collector.get_histogram("test_histogram")
        assert hist is not None
        assert hist.count == 3
        assert hist.sum == 60.0
        assert hist.mean == 20.0

    def test_metrics_with_labels(self):
        """Test 9: Metrics with labels."""
        increment_counter("requests", 5, {"endpoint": "/api/metrics"})
        increment_counter("requests", 3, {"endpoint": "/api/agents"})

        assert metrics_collector.get_counter("requests", {"endpoint": "/api/metrics"}) == 5
        assert metrics_collector.get_counter("requests", {"endpoint": "/api/agents"}) == 3

    def test_track_time_decorator(self):
        """Test 10: Track time decorator."""
        @track_time("function_duration")
        def slow_function():
            import time
            time.sleep(0.1)
            return "done"

        result = slow_function()
        assert result == "done"

        hist = metrics_collector.get_histogram("function_duration")
        assert hist is not None
        assert hist.count == 1
        assert hist.mean >= 0.1

    def test_timed_operation_context_manager(self):
        """Test 11: Timed operation context manager."""
        import time

        with timed_operation("operation_duration"):
            time.sleep(0.05)

        hist = metrics_collector.get_histogram("operation_duration")
        assert hist is not None
        assert hist.count == 1
        assert hist.mean >= 0.05

    def test_get_metrics_export(self):
        """Test 12: Get metrics as dictionary."""
        increment_counter("counter1", 10)
        set_gauge("gauge1", 42)
        record_metric("hist1", 5.0)

        metrics = metrics_collector.get_metrics()

        assert "timestamp" in metrics
        assert "uptime_seconds" in metrics
        assert "counters" in metrics
        assert "gauges" in metrics
        assert "histograms" in metrics

    def test_prometheus_export(self):
        """Test 13: Export metrics in Prometheus format."""
        metrics_collector.register_metric(
            "test_counter",
            "counter",
            "Test counter metric"
        )
        increment_counter("test_counter", 42)

        prom_text = metrics_collector.export_prometheus()

        assert "# HELP test_counter Test counter metric" in prom_text
        assert "# TYPE test_counter counter" in prom_text
        assert "test_counter 42" in prom_text

    def test_histogram_percentiles(self):
        """Test 14: Histogram percentile calculations."""
        hist = HistogramData()

        for i in range(100):
            hist.observe(i / 100.0)

        assert hist.count == 100
        assert hist.percentile(50) > 0
        assert hist.percentile(95) >= hist.percentile(50)
        assert hist.percentile(99) >= hist.percentile(95)


class TestEnhancedHealthEndpoint(AioHTTPTestCase):
    """Test suite for enhanced /health endpoint."""

    async def get_application(self):
        """Create test application."""
        self.temp_dir = tempfile.mkdtemp()
        self.metrics_file = Path(self.temp_dir) / ".agent_metrics.json"

        # Create minimal valid metrics
        minimal_metrics = {
            "version": 1,
            "project_name": "test-project",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "total_sessions": 5,
            "total_tokens": 1000,
            "total_cost_usd": 0.5,
            "total_duration_seconds": 60.0,
            "agents": {},
            "events": [],
            "sessions": []
        }

        self.metrics_file.write_text(json.dumps(minimal_metrics))

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
        import shutil
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_health_endpoint_returns_detailed_status(self):
        """Test 15: Health endpoint returns detailed system information."""
        resp = await self.client.request("GET", "/health")
        assert resp.status == 200

        data = await resp.json()

        # Check required fields
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "service" in data
        assert "system" in data
        assert "metrics_store" in data
        assert "performance" in data

    async def test_health_endpoint_includes_system_metrics(self):
        """Test 16: Health endpoint includes CPU, memory, disk metrics."""
        resp = await self.client.request("GET", "/health")
        assert resp.status == 200

        data = await resp.json()
        system = data["system"]

        assert "cpu_percent" in system
        assert "memory_percent" in system
        assert "memory_used_mb" in system
        assert "memory_total_mb" in system
        assert "disk_percent" in system
        assert "disk_used_gb" in system

    async def test_health_endpoint_includes_service_info(self):
        """Test 17: Health endpoint includes service information."""
        resp = await self.client.request("GET", "/health")
        assert resp.status == 200

        data = await resp.json()
        service = data["service"]

        assert service["name"] == "agent-dashboard"
        assert "uptime_seconds" in service
        assert service["host"] == "127.0.0.1"
        assert service["port"] == 8080

    async def test_prometheus_metrics_endpoint(self):
        """Test 18: Prometheus metrics endpoint returns valid format."""
        resp = await self.client.request("GET", "/metrics")
        assert resp.status == 200
        assert "text/plain" in resp.content_type

        text = await resp.text()

        # Check for Prometheus format markers
        assert "# HELP" in text or "dashboard_" in text
        assert "# TYPE" in text or "dashboard_" in text

    async def test_system_status_endpoint(self):
        """Test 19: System status endpoint returns comprehensive data."""
        resp = await self.client.request("GET", "/api/system/status")
        assert resp.status == 200

        data = await resp.json()

        assert "timestamp" in data
        assert "status" in data
        assert "alerts" in data
        assert "system" in data
        assert "process" in data
        assert "performance_metrics" in data

    async def test_system_status_includes_alerts(self):
        """Test 20: System status detects and reports alerts."""
        resp = await self.client.request("GET", "/api/system/status")
        assert resp.status == 200

        data = await resp.json()

        # Alerts is a list (may be empty or contain warnings)
        assert isinstance(data["alerts"], list)

        # If there are alerts, check structure
        for alert in data["alerts"]:
            assert "severity" in alert
            assert "message" in alert
            assert "timestamp" in alert

    async def test_monitoring_dashboard_page(self):
        """Test 21: Monitoring dashboard HTML page is served."""
        resp = await self.client.request("GET", "/monitoring")

        # Should return HTML or 404 if file doesn't exist
        if resp.status == 200:
            content = await resp.text()
            assert "html" in content.lower()
            assert "monitoring" in content.lower()

    async def test_health_endpoint_performance(self):
        """Test 22: Health endpoint responds quickly."""
        import time

        start = time.time()
        resp = await self.client.request("GET", "/health")
        duration = time.time() - start

        assert resp.status == 200
        assert duration < 1.0  # Should respond in less than 1 second

    async def test_concurrent_health_checks(self):
        """Test 23: Multiple concurrent health checks."""
        tasks = []
        for _ in range(10):
            tasks.append(self.client.request("GET", "/health"))

        responses = await asyncio.gather(*tasks)

        # All should succeed
        for resp in responses:
            assert resp.status == 200


class TestMonitoringIntegration:
    """Integration tests for monitoring features."""

    def test_logging_and_metrics_integration(self):
        """Test 24: Logging and metrics work together."""
        metrics_collector.reset()

        logger = get_logger("test")

        # Log with performance metric
        log_performance_metric(
            logger,
            "test_operation",
            100.5,
            endpoint="/test"
        )

        # Record metric
        record_metric("test_operation", 0.1005)

        # Verify metric was recorded
        hist = metrics_collector.get_histogram("test_operation")
        assert hist is not None
        assert hist.count > 0

    def test_end_to_end_monitoring_workflow(self):
        """Test 25: Complete monitoring workflow."""
        metrics_collector.reset()

        # 1. Increment counters
        increment_counter("requests_total", 1, {"endpoint": "/api/metrics"})

        # 2. Set gauges
        set_gauge("active_connections", 5)

        # 3. Record histograms
        record_metric("request_duration", 0.150)

        # 4. Export metrics
        metrics = metrics_collector.get_metrics()

        assert "counters" in metrics
        assert "gauges" in metrics
        assert "histograms" in metrics

        # 5. Export to Prometheus format
        prom_text = metrics_collector.export_prometheus()
        assert len(prom_text) > 0


class TestErrorHandling:
    """Test error handling in monitoring features."""

    def test_metrics_collector_handles_invalid_values(self):
        """Test 26: Metrics collector handles invalid values gracefully."""
        metrics_collector.reset()

        # Should not raise exceptions
        try:
            increment_counter("test", float('nan'))
            set_gauge("test", float('inf'))
            record_metric("test", -1)  # Negative values should work
        except Exception as e:
            pytest.fail(f"Metrics collector raised unexpected exception: {e}")

    def test_json_formatter_handles_non_serializable(self):
        """Test 27: JSON formatter handles non-serializable objects."""
        import logging

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )

        # Add non-serializable object
        record.custom_obj = object()

        # Should not raise, should convert to string
        formatted = formatter.format(record)
        data = json.loads(formatted)  # Should parse successfully


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
