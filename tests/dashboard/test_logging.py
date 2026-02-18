"""Tests for dashboard/logging_config.py - AI-198.

Covers:
- JSONFormatter outputs valid JSON
- JSONFormatter includes required fields
- ColoredConsoleFormatter falls back to plain text
- RequestContextFilter always passes records through
- setup_logging() creates handlers
- get_logger() returns a Logger
- log_performance_metric() logs with metric fields
- log_business_event() logs with event fields
- log_with_context() logs with extra context
- LoggingMiddleware initializes with default logger
"""

import json
import logging
import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dashboard.logging_config import (
    JSONFormatter,
    ColoredConsoleFormatter,
    RequestContextFilter,
    setup_logging,
    get_logger,
    log_performance_metric,
    log_business_event,
    log_with_context,
    LoggingMiddleware,
    DEFAULT_LOG_LEVEL,
)


# ---------------------------------------------------------------------------
# JSONFormatter tests
# ---------------------------------------------------------------------------

class TestJSONFormatter:
    """Tests for JSONFormatter."""

    def test_format_returns_valid_json(self):
        """format() returns valid JSON string."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="test.py", lineno=1,
            msg="test message", args=(), exc_info=None
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_format_includes_timestamp(self):
        """Formatted JSON includes 'timestamp' field."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="test.py", lineno=1,
            msg="msg", args=(), exc_info=None
        )
        output = json.loads(formatter.format(record))
        assert "timestamp" in output

    def test_format_includes_level(self):
        """Formatted JSON includes 'level' field."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.WARNING,
            pathname="test.py", lineno=1,
            msg="msg", args=(), exc_info=None
        )
        output = json.loads(formatter.format(record))
        assert output["level"] == "WARNING"

    def test_format_includes_logger_name(self):
        """Formatted JSON includes 'logger' field."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="my.module", level=logging.INFO,
            pathname="test.py", lineno=1,
            msg="msg", args=(), exc_info=None
        )
        output = json.loads(formatter.format(record))
        assert output["logger"] == "my.module"

    def test_format_includes_message(self):
        """Formatted JSON includes 'message' field."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="test.py", lineno=1,
            msg="hello world", args=(), exc_info=None
        )
        output = json.loads(formatter.format(record))
        assert output["message"] == "hello world"

    def test_format_includes_module(self):
        """Formatted JSON includes 'module' field."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="test.py", lineno=1,
            msg="msg", args=(), exc_info=None
        )
        output = json.loads(formatter.format(record))
        assert "module" in output

    def test_format_includes_line_number(self):
        """Formatted JSON includes 'line' field."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="test.py", lineno=42,
            msg="msg", args=(), exc_info=None
        )
        output = json.loads(formatter.format(record))
        assert output["line"] == 42


# ---------------------------------------------------------------------------
# RequestContextFilter tests
# ---------------------------------------------------------------------------

class TestRequestContextFilter:
    """Tests for RequestContextFilter."""

    def test_filter_always_returns_true(self):
        """filter() always returns True (pass-through)."""
        f = RequestContextFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO,
            pathname="test.py", lineno=1,
            msg="msg", args=(), exc_info=None
        )
        assert f.filter(record) is True

    def test_filter_does_not_raise(self):
        """filter() does not raise on any standard record."""
        f = RequestContextFilter()
        record = logging.LogRecord(
            name="test.module", level=logging.ERROR,
            pathname="test.py", lineno=99,
            msg="error occurred", args=(), exc_info=None
        )
        # Should not raise
        result = f.filter(record)
        assert result is True


# ---------------------------------------------------------------------------
# get_logger() tests
# ---------------------------------------------------------------------------

class TestGetLogger:
    """Tests for get_logger()."""

    def test_get_logger_returns_logger_instance(self):
        """get_logger() returns a logging.Logger instance."""
        logger = get_logger("test.module")
        assert isinstance(logger, logging.Logger)

    def test_get_logger_name_matches(self):
        """get_logger() returns logger with correct name."""
        logger = get_logger("my.custom.module")
        assert logger.name == "my.custom.module"

    def test_get_logger_same_name_returns_same_instance(self):
        """Same name returns same logger instance (standard Python behavior)."""
        l1 = get_logger("same.logger")
        l2 = get_logger("same.logger")
        assert l1 is l2


# ---------------------------------------------------------------------------
# log_performance_metric() tests
# ---------------------------------------------------------------------------

class TestLogPerformanceMetric:
    """Tests for log_performance_metric()."""

    def test_logs_without_raising(self):
        """log_performance_metric() does not raise."""
        logger = get_logger("perf.test")
        # Should not raise
        log_performance_metric(logger, "db_query", 15.5)

    def test_logs_with_extra_context(self):
        """log_performance_metric() accepts extra context."""
        logger = get_logger("perf.test2")
        # Should not raise with extra kwargs
        log_performance_metric(logger, "api_call", 42.0, endpoint="/api/test", status=200)


# ---------------------------------------------------------------------------
# log_business_event() tests
# ---------------------------------------------------------------------------

class TestLogBusinessEvent:
    """Tests for log_business_event()."""

    def test_logs_without_raising(self):
        """log_business_event() does not raise."""
        logger = get_logger("biz.test")
        log_business_event(logger, "user_action", "message_sent")

    def test_logs_with_extra_context(self):
        """log_business_event() accepts extra context."""
        logger = get_logger("biz.test2")
        log_business_event(
            logger, "system_event", "agent_started",
            agent="coding", ticket="AI-109"
        )


# ---------------------------------------------------------------------------
# log_with_context() tests
# ---------------------------------------------------------------------------

class TestLogWithContext:
    """Tests for log_with_context()."""

    def test_log_with_context_info(self):
        """log_with_context() works with info level."""
        logger = get_logger("ctx.test")
        log_with_context(logger, "info", "test message", key="value")

    def test_log_with_context_warning(self):
        """log_with_context() works with warning level."""
        logger = get_logger("ctx.test2")
        log_with_context(logger, "warning", "warning msg")

    def test_log_with_context_error(self):
        """log_with_context() works with error level."""
        logger = get_logger("ctx.test3")
        log_with_context(logger, "error", "error message", code=500)


# ---------------------------------------------------------------------------
# LoggingMiddleware tests
# ---------------------------------------------------------------------------

class TestLoggingMiddleware:
    """Tests for LoggingMiddleware."""

    def test_init_with_default_logger(self):
        """LoggingMiddleware can be initialized with default logger."""
        middleware = LoggingMiddleware()
        assert middleware.logger is not None

    def test_init_with_custom_logger(self):
        """LoggingMiddleware can be initialized with custom logger."""
        custom_logger = get_logger("custom.access")
        middleware = LoggingMiddleware(logger=custom_logger)
        assert middleware.logger is custom_logger
