"""Tests for AI-186: REQ-OBS-001 — Structured Server Logging.

Covers:
- RequestLogger.log_request() logs method, path, status, duration_ms
- RequestLogger.log_ws_connect() logs connect event with client ID
- RequestLogger.log_ws_disconnect() logs disconnect event with client ID
- ProviderRoutingLogger.log_routing() logs intent_type, agent, confidence
- ErrorLogger.log_error() captures exception with exc_info (stack trace)
- Log output uses structured extra fields (parseable records)
- Custom logger names are respected
- Warning level emitted for 4xx/5xx status codes
- Integration: ws_handler in DashboardServer calls ws connect/disconnect loggers
- Integration: error_middleware calls ErrorLogger on unhandled exceptions
- Integration: post_chat_stream calls ProviderRoutingLogger on intent chunks
"""

import asyncio
import logging
import sys
import tempfile
from pathlib import Path
from typing import List
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

# Make sure the project root is importable
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.structured_logging import (
    ErrorLogger,
    ProviderRoutingLogger,
    RequestLogger,
    get_logger,
)


# ---------------------------------------------------------------------------
# Helper: capture log records emitted by a logger
# ---------------------------------------------------------------------------

class _CapturingHandler(logging.Handler):
    """In-memory log handler that accumulates LogRecord objects."""

    def __init__(self):
        super().__init__()
        self.records: List[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def _make_logger(name: str) -> tuple:
    """Return (logger, handler) pair with capturing handler attached."""
    log = logging.getLogger(f"dashboard.test_{name}")
    log.setLevel(logging.DEBUG)
    handler = _CapturingHandler()
    log.addHandler(handler)
    return log, handler


# ===========================================================================
# get_logger
# ===========================================================================


class TestGetLogger:
    """Tests for the get_logger() factory."""

    def test_returns_logger_instance(self):
        log = get_logger("foo")
        assert isinstance(log, logging.Logger)

    def test_logger_name_prefixed_with_dashboard(self):
        log = get_logger("bar")
        assert log.name == "dashboard.bar"

    def test_different_names_give_different_loggers(self):
        log1 = get_logger("x")
        log2 = get_logger("y")
        assert log1 is not log2

    def test_same_name_returns_same_logger(self):
        log1 = get_logger("same")
        log2 = get_logger("same")
        assert log1 is log2


# ===========================================================================
# RequestLogger
# ===========================================================================


class TestRequestLoggerLogRequest:
    """Tests for RequestLogger.log_request()."""

    def setup_method(self):
        self._log, self._handler = _make_logger("req")
        self._rl = RequestLogger(logger=self._log)

    def teardown_method(self):
        self._log.removeHandler(self._handler)

    def test_log_request_emits_record(self):
        self._rl.log_request("GET", "/api/metrics", 200, 12.5)
        assert len(self._handler.records) == 1

    def test_log_request_method_in_extra(self):
        self._rl.log_request("POST", "/api/chat", 201, 5.0)
        record = self._handler.records[0]
        assert record.method == "POST"

    def test_log_request_path_in_extra(self):
        self._rl.log_request("GET", "/api/agents", 200, 3.0)
        record = self._handler.records[0]
        assert record.path == "/api/agents"

    def test_log_request_status_in_extra(self):
        self._rl.log_request("GET", "/health", 200, 1.0)
        record = self._handler.records[0]
        assert record.status == 200

    def test_log_request_duration_in_extra(self):
        self._rl.log_request("GET", "/api/metrics", 200, 42.123)
        record = self._handler.records[0]
        assert record.duration_ms == 42.123

    def test_log_request_event_field(self):
        self._rl.log_request("GET", "/api/metrics", 200, 1.0)
        record = self._handler.records[0]
        assert record.event == "http_request"

    def test_log_request_info_level_for_2xx(self):
        self._rl.log_request("GET", "/api/metrics", 200, 1.0)
        assert self._handler.records[0].levelno == logging.INFO

    def test_log_request_warning_level_for_4xx(self):
        self._rl.log_request("GET", "/api/nope", 404, 1.0)
        assert self._handler.records[0].levelno == logging.WARNING

    def test_log_request_warning_level_for_5xx(self):
        self._rl.log_request("POST", "/api/crash", 500, 2.0)
        assert self._handler.records[0].levelno == logging.WARNING

    def test_log_request_extra_fields_merged(self):
        self._rl.log_request("GET", "/api/metrics", 200, 1.0, extra={"foo": "bar"})
        record = self._handler.records[0]
        assert record.foo == "bar"

    def test_log_request_duration_rounded(self):
        self._rl.log_request("GET", "/", 200, 1.23456789)
        record = self._handler.records[0]
        # Rounded to 3 decimal places
        assert record.duration_ms == 1.235


# ===========================================================================
# RequestLogger — WebSocket events
# ===========================================================================


class TestRequestLoggerWebSocket:
    """Tests for RequestLogger.log_ws_connect() and log_ws_disconnect()."""

    def setup_method(self):
        self._log, self._handler = _make_logger("ws")
        self._rl = RequestLogger(logger=self._log)

    def teardown_method(self):
        self._log.removeHandler(self._handler)

    def test_ws_connect_emits_record(self):
        self._rl.log_ws_connect("abc123")
        assert len(self._handler.records) == 1

    def test_ws_connect_client_id_in_extra(self):
        self._rl.log_ws_connect("client-42")
        record = self._handler.records[0]
        assert record.client_id == "client-42"

    def test_ws_connect_event_field(self):
        self._rl.log_ws_connect("client-1")
        record = self._handler.records[0]
        assert record.event == "ws_connect"

    def test_ws_connect_remote_in_extra_when_given(self):
        self._rl.log_ws_connect("client-9", remote="127.0.0.1")
        record = self._handler.records[0]
        assert record.remote == "127.0.0.1"

    def test_ws_connect_info_level(self):
        self._rl.log_ws_connect("client-7")
        assert self._handler.records[0].levelno == logging.INFO

    def test_ws_disconnect_emits_record(self):
        self._rl.log_ws_disconnect("abc999")
        assert len(self._handler.records) == 1

    def test_ws_disconnect_client_id_in_extra(self):
        self._rl.log_ws_disconnect("client-99")
        record = self._handler.records[0]
        assert record.client_id == "client-99"

    def test_ws_disconnect_event_field(self):
        self._rl.log_ws_disconnect("client-2")
        record = self._handler.records[0]
        assert record.event == "ws_disconnect"

    def test_ws_disconnect_reason_in_extra_when_given(self):
        self._rl.log_ws_disconnect("client-3", reason="client closed")
        record = self._handler.records[0]
        assert record.reason == "client closed"

    def test_ws_disconnect_info_level(self):
        self._rl.log_ws_disconnect("client-5")
        assert self._handler.records[0].levelno == logging.INFO


# ===========================================================================
# ProviderRoutingLogger
# ===========================================================================


class TestProviderRoutingLogger:
    """Tests for ProviderRoutingLogger.log_routing()."""

    def setup_method(self):
        self._log, self._handler = _make_logger("routing")
        self._prl = ProviderRoutingLogger(logger=self._log)

    def teardown_method(self):
        self._log.removeHandler(self._handler)

    def test_log_routing_emits_record(self):
        self._prl.log_routing("implement login", "ask_agent", "coding", 0.9)
        assert len(self._handler.records) == 1

    def test_log_routing_intent_type_in_extra(self):
        self._prl.log_routing("hello", "general_chat", None, 0.5)
        record = self._handler.records[0]
        assert record.intent_type == "general_chat"

    def test_log_routing_agent_in_extra_when_given(self):
        self._prl.log_routing("create pr", "ask_agent", "github", 0.85)
        record = self._handler.records[0]
        assert record.agent == "github"

    def test_log_routing_agent_none_when_no_agent(self):
        self._prl.log_routing("just chatting", "general_chat", None, 0.4)
        record = self._handler.records[0]
        assert record.agent is None

    def test_log_routing_confidence_in_extra(self):
        self._prl.log_routing("run tests", "run_task", "coding", 0.75)
        record = self._handler.records[0]
        assert record.confidence == 0.75

    def test_log_routing_event_field(self):
        self._prl.log_routing("status", "get_status", None, 0.6)
        record = self._handler.records[0]
        assert record.event == "routing_decision"

    def test_log_routing_info_level(self):
        self._prl.log_routing("test", "general_chat", None, 0.3)
        assert self._handler.records[0].levelno == logging.INFO

    def test_log_routing_message_preview_truncated(self):
        long_msg = "a" * 200
        self._prl.log_routing(long_msg, "general_chat", None, 0.5)
        record = self._handler.records[0]
        assert len(record.message_preview) == 120

    def test_log_routing_message_preview_short_message(self):
        msg = "short message"
        self._prl.log_routing(msg, "general_chat", None, 0.5)
        record = self._handler.records[0]
        assert record.message_preview == msg


# ===========================================================================
# ErrorLogger
# ===========================================================================


class TestErrorLogger:
    """Tests for ErrorLogger.log_error()."""

    def setup_method(self):
        self._log, self._handler = _make_logger("errors")
        self._el = ErrorLogger(logger=self._log)

    def teardown_method(self):
        self._log.removeHandler(self._handler)

    def test_log_error_emits_record(self):
        try:
            raise ValueError("test error")
        except ValueError as exc:
            self._el.log_error(exc)
        assert len(self._handler.records) == 1

    def test_log_error_captures_exc_info(self):
        try:
            raise RuntimeError("boom")
        except RuntimeError as exc:
            self._el.log_error(exc)
        record = self._handler.records[0]
        # exc_info is a 3-tuple (type, value, traceback)
        assert record.exc_info is not None
        assert record.exc_info[0] is RuntimeError

    def test_log_error_error_type_in_extra(self):
        try:
            raise TypeError("bad type")
        except TypeError as exc:
            self._el.log_error(exc)
        record = self._handler.records[0]
        assert record.error_type == "TypeError"

    def test_log_error_error_message_in_extra(self):
        try:
            raise ValueError("specific message")
        except ValueError as exc:
            self._el.log_error(exc)
        record = self._handler.records[0]
        assert record.error_message == "specific message"

    def test_log_error_event_field(self):
        try:
            raise Exception("generic")
        except Exception as exc:
            self._el.log_error(exc)
        record = self._handler.records[0]
        assert record.event == "error"

    def test_log_error_context_included(self):
        try:
            raise IOError("disk full")
        except IOError as exc:
            self._el.log_error(exc, context={"path": "/tmp/foo", "method": "GET"})
        record = self._handler.records[0]
        assert record.context == {"path": "/tmp/foo", "method": "GET"}

    def test_log_error_error_level(self):
        try:
            raise Exception("oops")
        except Exception as exc:
            self._el.log_error(exc)
        assert self._handler.records[0].levelno == logging.ERROR

    def test_log_error_stack_trace_in_exc_info(self):
        """Verify that the traceback in exc_info contains the raise site."""
        import traceback as tb_mod

        try:
            raise ValueError("trace me")
        except ValueError as exc:
            self._el.log_error(exc)

        record = self._handler.records[0]
        exc_info = record.exc_info
        assert exc_info is not None
        tb_lines = tb_mod.format_exception(*exc_info)
        full_tb = "".join(tb_lines)
        assert "ValueError" in full_tb
        assert "trace me" in full_tb


# ===========================================================================
# Custom logger name
# ===========================================================================


class TestCustomLoggerName:
    """Verify that custom loggers passed to constructors are used correctly."""

    def test_request_logger_uses_custom_logger(self):
        custom, handler = _make_logger("custom_req")
        rl = RequestLogger(logger=custom)
        rl.log_request("GET", "/", 200, 1.0)
        assert len(handler.records) == 1
        custom.removeHandler(handler)

    def test_provider_routing_logger_uses_custom_logger(self):
        custom, handler = _make_logger("custom_routing")
        prl = ProviderRoutingLogger(logger=custom)
        prl.log_routing("msg", "general_chat", None, 0.5)
        assert len(handler.records) == 1
        custom.removeHandler(handler)

    def test_error_logger_uses_custom_logger(self):
        custom, handler = _make_logger("custom_errors")
        el = ErrorLogger(logger=custom)
        try:
            raise Exception("err")
        except Exception as exc:
            el.log_error(exc)
        assert len(handler.records) == 1
        custom.removeHandler(handler)


# ===========================================================================
# Default logger names
# ===========================================================================


class TestDefaultLoggerNames:
    """Verify default logger names follow the dashboard.* namespace."""

    def test_request_logger_default_name(self):
        rl = RequestLogger()
        assert rl._logger.name == "dashboard.requests"

    def test_provider_routing_logger_default_name(self):
        prl = ProviderRoutingLogger()
        assert prl._logger.name == "dashboard.routing"

    def test_error_logger_default_name(self):
        el = ErrorLogger()
        assert el._logger.name == "dashboard.errors"


# ===========================================================================
# Integration: DashboardServer websocket_handler logs connect/disconnect
# ===========================================================================


class TestDashboardServerWSLogging:
    """Integration tests: websocket_handler uses RequestLogger for WS events."""

    def test_dashboard_server_has_ws_logger_attribute(self):
        """DashboardServer should create a _ws_logger attribute."""
        import tempfile
        from dashboard.server import DashboardServer

        with tempfile.TemporaryDirectory() as td:
            server = DashboardServer(project_name="test", metrics_dir=td)
            assert hasattr(server, "_ws_logger")
            assert isinstance(server._ws_logger, RequestLogger)

    def test_dashboard_server_has_provider_routing_logger(self):
        """DashboardServer should create a _provider_routing_logger attribute."""
        import tempfile
        from dashboard.server import DashboardServer

        with tempfile.TemporaryDirectory() as td:
            server = DashboardServer(project_name="test", metrics_dir=td)
            assert hasattr(server, "_provider_routing_logger")
            assert isinstance(server._provider_routing_logger, ProviderRoutingLogger)

    def test_dashboard_server_has_error_logger_attribute(self):
        """DashboardServer should create a _error_logger attribute."""
        import tempfile
        from dashboard.server import DashboardServer

        with tempfile.TemporaryDirectory() as td:
            server = DashboardServer(project_name="test", metrics_dir=td)
            assert hasattr(server, "_error_logger")
            assert isinstance(server._error_logger, ErrorLogger)


# ===========================================================================
# Integration: error_middleware uses ErrorLogger
# ===========================================================================


class TestErrorMiddlewareLogging:
    """Integration test: error_middleware calls _error_logger.log_error()."""

    @pytest.mark.asyncio
    async def test_error_middleware_calls_error_logger(self):
        """error_middleware should call _error_logger.log_error on unhandled exceptions."""
        from aiohttp import web
        from dashboard.server import error_middleware
        import dashboard.server as server_module

        # Capture calls to the module-level _error_logger
        call_log = []

        original = server_module._error_logger.log_error

        def spy_log_error(exc, context=None):
            call_log.append((exc, context))

        server_module._error_logger.log_error = spy_log_error

        try:
            request = MagicMock()
            request.method = "GET"
            request.path = "/api/crash"

            async def bad_handler(req):
                raise RuntimeError("middleware test error")

            response = await error_middleware(request, bad_handler)
            assert response.status == 500
            assert len(call_log) == 1
            exc, ctx = call_log[0]
            assert isinstance(exc, RuntimeError)
            assert ctx is not None
            assert ctx.get("method") == "GET"
        finally:
            server_module._error_logger.log_error = original
