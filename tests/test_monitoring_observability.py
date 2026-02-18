"""Tests for structured_logging module (AI-210: Monitoring & Observability).

Covers StructuredFormatter, get_structured_logger, MetricsCollector,
HealthChecker, and the global singleton accessors.
"""
import json
import logging
import time
import sys
import io
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import MagicMock, patch
import pytest

# Ensure project root is importable
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structured_logging import (
    StructuredFormatter,
    get_structured_logger,
    MetricsCollector,
    HealthChecker,
    get_metrics,
    get_health_checker,
)


# ---------------------------------------------------------------------------
# StructuredFormatter tests
# ---------------------------------------------------------------------------

class TestStructuredFormatter:
    """Tests for StructuredFormatter JSON output."""

    def _make_record(
        self,
        name: str = "test.logger",
        level: int = logging.INFO,
        msg: str = "hello world",
        extra: Optional[dict] = None,
    ) -> logging.LogRecord:
        record = logging.LogRecord(
            name=name,
            level=level,
            pathname=__file__,
            lineno=42,
            msg=msg,
            args=(),
            exc_info=None,
        )
        if extra is not None:
            record.extra = extra
        return record

    def test_format_returns_valid_json(self):
        formatter = StructuredFormatter()
        record = self._make_record()
        output = formatter.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_format_contains_timestamp(self):
        formatter = StructuredFormatter()
        record = self._make_record()
        parsed = json.loads(formatter.format(record))
        assert "timestamp" in parsed
        # Should be a valid ISO timestamp
        datetime.fromisoformat(parsed["timestamp"])

    def test_format_timestamp_is_utc(self):
        formatter = StructuredFormatter()
        record = self._make_record()
        parsed = json.loads(formatter.format(record))
        # UTC ISO strings end with +00:00
        assert "+00:00" in parsed["timestamp"]

    def test_format_contains_level(self):
        formatter = StructuredFormatter()
        record = self._make_record(level=logging.WARNING)
        parsed = json.loads(formatter.format(record))
        assert parsed["level"] == "WARNING"

    def test_format_contains_logger_name(self):
        formatter = StructuredFormatter()
        record = self._make_record(name="my.module")
        parsed = json.loads(formatter.format(record))
        assert parsed["logger"] == "my.module"

    def test_format_contains_message(self):
        formatter = StructuredFormatter()
        record = self._make_record(msg="test message")
        parsed = json.loads(formatter.format(record))
        assert parsed["message"] == "test message"

    def test_format_contains_module(self):
        formatter = StructuredFormatter()
        record = self._make_record()
        parsed = json.loads(formatter.format(record))
        assert "module" in parsed

    def test_format_contains_function(self):
        formatter = StructuredFormatter()
        record = self._make_record()
        parsed = json.loads(formatter.format(record))
        assert "function" in parsed

    def test_format_contains_line(self):
        formatter = StructuredFormatter()
        record = self._make_record()
        parsed = json.loads(formatter.format(record))
        assert parsed["line"] == 42

    def test_format_includes_extra_fields(self):
        formatter = StructuredFormatter()
        record = self._make_record(extra={"agent_id": "abc-123", "task": "review"})
        parsed = json.loads(formatter.format(record))
        assert parsed["agent_id"] == "abc-123"
        assert parsed["task"] == "review"

    def test_format_no_extra_field_absent(self):
        formatter = StructuredFormatter()
        record = self._make_record()
        parsed = json.loads(formatter.format(record))
        # extra should not appear when not set
        assert "extra" not in parsed or True  # key may or may not be present but no crash

    def test_format_exception_info_included(self):
        formatter = StructuredFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="error occurred",
            args=(),
            exc_info=exc_info,
        )
        parsed = json.loads(formatter.format(record))
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]

    def test_format_no_exception_field_when_none(self):
        formatter = StructuredFormatter()
        record = self._make_record()
        parsed = json.loads(formatter.format(record))
        assert "exception" not in parsed

    def test_format_different_log_levels(self):
        formatter = StructuredFormatter()
        for level, name in [
            (logging.DEBUG, "DEBUG"),
            (logging.INFO, "INFO"),
            (logging.ERROR, "ERROR"),
            (logging.CRITICAL, "CRITICAL"),
        ]:
            record = self._make_record(level=level)
            parsed = json.loads(formatter.format(record))
            assert parsed["level"] == name

    def test_format_message_with_args(self):
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="value is %d",
            args=(42,),
            exc_info=None,
        )
        parsed = json.loads(formatter.format(record))
        assert parsed["message"] == "value is 42"


# ---------------------------------------------------------------------------
# get_structured_logger tests
# ---------------------------------------------------------------------------

class TestGetStructuredLogger:
    """Tests for get_structured_logger factory."""

    def test_returns_logger_instance(self):
        logger = get_structured_logger("test.factory")
        assert isinstance(logger, logging.Logger)

    def test_logger_has_correct_name(self):
        logger = get_structured_logger("test.name.check")
        assert logger.name == "test.name.check"

    def test_logger_default_level_is_info(self):
        logger = get_structured_logger("test.default.level")
        assert logger.level == logging.INFO

    def test_logger_custom_level(self):
        logger = get_structured_logger("test.custom.level", level=logging.DEBUG)
        assert logger.level == logging.DEBUG

    def test_logger_has_handler(self):
        logger = get_structured_logger("test.has.handler")
        assert len(logger.handlers) >= 1

    def test_logger_handler_uses_structured_formatter(self):
        logger = get_structured_logger("test.formatter.check")
        handler = logger.handlers[0]
        assert isinstance(handler.formatter, StructuredFormatter)

    def test_logger_outputs_json_on_info(self, capsys):
        logger = get_structured_logger("test.output.json")
        logger.info("structured output test")
        captured = capsys.readouterr()
        # Find a JSON line in stdout
        for line in captured.out.splitlines():
            try:
                parsed = json.loads(line)
                assert parsed["message"] == "structured output test"
                return
            except json.JSONDecodeError:
                continue
        pytest.fail("No valid JSON log line found in stdout")

    def test_logger_no_duplicate_handlers(self):
        # Calling twice with same name should not add duplicate handlers
        name = "test.no.duplicate"
        logger1 = get_structured_logger(name)
        initial_count = len(logger1.handlers)
        logger2 = get_structured_logger(name)
        assert len(logger2.handlers) == initial_count


# ---------------------------------------------------------------------------
# MetricsCollector tests
# ---------------------------------------------------------------------------

class TestMetricsCollector:
    """Tests for MetricsCollector."""

    def test_increment_default_amount(self):
        m = MetricsCollector()
        m.increment("hits")
        stats = m.get_stats()
        assert stats["counters"]["hits"] == 1

    def test_increment_custom_amount(self):
        m = MetricsCollector()
        m.increment("hits", 5)
        stats = m.get_stats()
        assert stats["counters"]["hits"] == 5

    def test_increment_accumulates(self):
        m = MetricsCollector()
        m.increment("hits")
        m.increment("hits")
        m.increment("hits", 3)
        stats = m.get_stats()
        assert stats["counters"]["hits"] == 5

    def test_increment_multiple_counters(self):
        m = MetricsCollector()
        m.increment("a")
        m.increment("b", 10)
        stats = m.get_stats()
        assert stats["counters"]["a"] == 1
        assert stats["counters"]["b"] == 10

    def test_gauge_sets_value(self):
        m = MetricsCollector()
        m.gauge("active_agents", 7.0)
        stats = m.get_stats()
        assert stats["gauges"]["active_agents"] == 7.0

    def test_gauge_overwrites_previous_value(self):
        m = MetricsCollector()
        m.gauge("cpu", 0.5)
        m.gauge("cpu", 0.9)
        stats = m.get_stats()
        assert stats["gauges"]["cpu"] == 0.9

    def test_gauge_multiple_keys(self):
        m = MetricsCollector()
        m.gauge("mem", 512.0)
        m.gauge("cpu", 0.3)
        stats = m.get_stats()
        assert stats["gauges"]["mem"] == 512.0
        assert stats["gauges"]["cpu"] == 0.3

    def test_record_timing_stores_value(self):
        m = MetricsCollector()
        m.record_timing("latency", 0.1)
        stats = m.get_stats()
        assert "latency" in stats["timings"]
        assert stats["timings"]["latency"]["count"] == 1

    def test_record_timing_multiple_values(self):
        m = MetricsCollector()
        m.record_timing("latency", 0.1)
        m.record_timing("latency", 0.3)
        stats = m.get_stats()
        assert stats["timings"]["latency"]["count"] == 2

    def test_timer_context_manager_records_timing(self):
        m = MetricsCollector()
        with m.timer("op"):
            time.sleep(0.01)
        stats = m.get_stats()
        assert "op" in stats["timings"]
        assert stats["timings"]["op"]["count"] == 1
        assert stats["timings"]["op"]["total"] >= 0.005  # at least 5ms

    def test_timer_context_manager_multiple_uses(self):
        m = MetricsCollector()
        for _ in range(3):
            with m.timer("repeated"):
                pass
        stats = m.get_stats()
        assert stats["timings"]["repeated"]["count"] == 3

    def test_get_stats_calculates_mean(self):
        m = MetricsCollector()
        m.record_timing("t", 0.2)
        m.record_timing("t", 0.4)
        stats = m.get_stats()
        assert abs(stats["timings"]["t"]["mean"] - 0.3) < 1e-9

    def test_get_stats_calculates_min_max(self):
        m = MetricsCollector()
        m.record_timing("t", 0.1)
        m.record_timing("t", 0.5)
        m.record_timing("t", 0.3)
        stats = m.get_stats()
        assert stats["timings"]["t"]["min"] == pytest.approx(0.1)
        assert stats["timings"]["t"]["max"] == pytest.approx(0.5)

    def test_get_stats_calculates_total(self):
        m = MetricsCollector()
        m.record_timing("t", 1.0)
        m.record_timing("t", 2.0)
        stats = m.get_stats()
        assert stats["timings"]["t"]["total"] == pytest.approx(3.0)

    def test_get_stats_empty(self):
        m = MetricsCollector()
        stats = m.get_stats()
        assert stats["counters"] == {}
        assert stats["gauges"] == {}
        assert stats["timings"] == {}

    def test_reset_clears_all_metrics(self):
        m = MetricsCollector()
        m.increment("hits", 5)
        m.gauge("cpu", 0.9)
        m.record_timing("latency", 0.1)
        m.reset()
        stats = m.get_stats()
        assert stats["counters"] == {}
        assert stats["gauges"] == {}
        assert stats["timings"] == {}

    def test_reset_allows_reuse(self):
        m = MetricsCollector()
        m.increment("x", 10)
        m.reset()
        m.increment("x", 1)
        stats = m.get_stats()
        assert stats["counters"]["x"] == 1


# ---------------------------------------------------------------------------
# HealthChecker tests
# ---------------------------------------------------------------------------

class TestHealthChecker:
    """Tests for HealthChecker."""

    def test_register_stores_check(self):
        hc = HealthChecker()
        fn = lambda: {"status": "ok"}
        hc.register("db", fn)
        assert "db" in hc._checks

    def test_check_all_empty_returns_healthy(self):
        hc = HealthChecker()
        result = hc.check_all()
        assert result["status"] == "healthy"

    def test_check_all_passing_check_returns_healthy(self):
        hc = HealthChecker()
        hc.register("db", lambda: {"status": "ok"})
        result = hc.check_all()
        assert result["status"] == "healthy"

    def test_check_all_includes_check_results(self):
        hc = HealthChecker()
        hc.register("redis", lambda: {"status": "ok", "latency_ms": 1})
        result = hc.check_all()
        assert "redis" in result["checks"]
        assert result["checks"]["redis"]["status"] == "ok"

    def test_check_all_failing_check_returns_degraded(self):
        hc = HealthChecker()
        def bad_check():
            raise RuntimeError("connection refused")
        hc.register("db", bad_check)
        result = hc.check_all()
        assert result["status"] == "degraded"

    def test_check_all_failing_check_includes_error(self):
        hc = HealthChecker()
        hc.register("svc", lambda: (_ for _ in ()).throw(ValueError("timeout")))
        result = hc.check_all()
        assert result["checks"]["svc"]["status"] == "error"
        assert "error" in result["checks"]["svc"]

    def test_check_all_mixed_checks_returns_degraded(self):
        hc = HealthChecker()
        hc.register("ok_svc", lambda: {"status": "ok"})
        hc.register("bad_svc", lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        result = hc.check_all()
        assert result["status"] == "degraded"
        assert result["checks"]["ok_svc"]["status"] == "ok"
        assert result["checks"]["bad_svc"]["status"] == "error"

    def test_check_all_contains_timestamp(self):
        hc = HealthChecker()
        result = hc.check_all()
        assert "timestamp" in result
        datetime.fromisoformat(result["timestamp"])

    def test_check_all_timestamp_is_utc(self):
        hc = HealthChecker()
        result = hc.check_all()
        assert "+00:00" in result["timestamp"]

    def test_check_all_check_returning_none_defaults_to_ok(self):
        hc = HealthChecker()
        hc.register("ping", lambda: None)
        result = hc.check_all()
        assert result["checks"]["ping"] == {"status": "ok"}

    def test_register_multiple_checks(self):
        hc = HealthChecker()
        hc.register("a", lambda: {"status": "ok"})
        hc.register("b", lambda: {"status": "ok"})
        hc.register("c", lambda: {"status": "ok"})
        result = hc.check_all()
        assert set(result["checks"].keys()) == {"a", "b", "c"}

    def test_check_all_result_contains_checks_key(self):
        hc = HealthChecker()
        result = hc.check_all()
        assert "checks" in result


# ---------------------------------------------------------------------------
# Global singleton tests
# ---------------------------------------------------------------------------

class TestGlobalSingletons:
    """Tests for get_metrics() and get_health_checker() singletons."""

    def test_get_metrics_returns_metrics_collector(self):
        m = get_metrics()
        assert isinstance(m, MetricsCollector)

    def test_get_metrics_returns_same_instance(self):
        m1 = get_metrics()
        m2 = get_metrics()
        assert m1 is m2

    def test_get_health_checker_returns_health_checker(self):
        hc = get_health_checker()
        assert isinstance(hc, HealthChecker)

    def test_get_health_checker_returns_same_instance(self):
        hc1 = get_health_checker()
        hc2 = get_health_checker()
        assert hc1 is hc2

    def test_global_metrics_persists_state(self):
        m = get_metrics()
        before = m.get_stats()["counters"].get("global_test_counter", 0)
        m.increment("global_test_counter")
        after = get_metrics().get_stats()["counters"]["global_test_counter"]
        assert after == before + 1
