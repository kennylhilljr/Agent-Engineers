"""Structured logging for dashboard server observability (AI-186 / REQ-OBS-001).

This module provides structured loggers for:
- API requests (method, path, status, duration)
- WebSocket connect/disconnect events
- Provider routing decisions (intent type, agent, confidence)
- Errors with full stack traces

All loggers use the ``dashboard.*`` namespace so they can be configured
independently from the root logger without polluting other namespaces.
"""

import logging
import time
import json
import traceback
from typing import Optional, Any


def get_logger(name: str) -> logging.Logger:
    """Return a logger in the ``dashboard.*`` namespace.

    Args:
        name: Sub-name appended to ``dashboard.`` (e.g. ``"requests"``
              → ``"dashboard.requests"``).

    Returns:
        A :class:`logging.Logger` instance.
    """
    return logging.getLogger(f"dashboard.{name}")


class RequestLogger:
    """Logs API requests with method, path, status code, and duration.

    Also emits structured WebSocket connect/disconnect events with the
    client identifier so operations can correlate WS lifecycle events.

    Usage::

        rl = RequestLogger()
        rl.log_request("GET", "/api/metrics", 200, 12.3)
        rl.log_ws_connect("abc123", remote="127.0.0.1")
        rl.log_ws_disconnect("abc123", reason="client closed")
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self._logger = logger or get_logger("requests")

    def log_request(
        self,
        method: str,
        path: str,
        status: int,
        duration_ms: float,
        extra: Optional[dict] = None,
    ) -> None:
        """Log a single HTTP API request.

        Args:
            method:      HTTP method (``"GET"``, ``"POST"``, …).
            path:        Request path (``"/api/metrics"``).
            status:      HTTP response status code (200, 404, 500, …).
            duration_ms: Request processing time in milliseconds.
            extra:       Optional dict of additional key/value pairs to include
                         in the structured log record.
        """
        record: dict = {
            "event": "http_request",
            "method": method,
            "path": path,
            "status": status,
            "duration_ms": round(duration_ms, 3),
        }
        if extra:
            record.update(extra)

        level = logging.WARNING if status >= 400 else logging.INFO
        self._logger.log(
            level,
            "%(method)s %(path)s %(status)s %(duration_ms)sms",
            record,
            extra=record,
        )

    def log_ws_connect(
        self,
        client_id: str,
        remote: Optional[str] = None,
    ) -> None:
        """Log a WebSocket client connection.

        Args:
            client_id: Unique identifier for the WebSocket client.
            remote:    Optional remote address (host/IP) of the connecting client.
        """
        record: dict = {
            "event": "ws_connect",
            "client_id": client_id,
        }
        if remote is not None:
            record["remote"] = remote

        self._logger.info(
            "WebSocket connected: client_id=%(client_id)s",
            record,
            extra=record,
        )

    def log_ws_disconnect(
        self,
        client_id: str,
        reason: Optional[str] = None,
    ) -> None:
        """Log a WebSocket client disconnection.

        Args:
            client_id: Unique identifier for the WebSocket client.
            reason:    Optional human-readable reason for the disconnect.
        """
        record: dict = {
            "event": "ws_disconnect",
            "client_id": client_id,
        }
        if reason is not None:
            record["reason"] = reason

        self._logger.info(
            "WebSocket disconnected: client_id=%(client_id)s",
            record,
            extra=record,
        )


class ProviderRoutingLogger:
    """Logs chat routing decisions made by ChatBridge / AgentRouter.

    Each routing decision captures the raw message intent, the resolved
    agent (if any), and the parser's confidence score.

    Usage::

        prl = ProviderRoutingLogger()
        prl.log_routing("implement login", "ask_agent", "coding", 0.9)
        prl.log_routing("hello there", "general_chat", None, 0.5)
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self._logger = logger or get_logger("routing")

    def log_routing(
        self,
        message: str,
        intent_type: str,
        agent: Optional[str],
        confidence: float,
    ) -> None:
        """Log a provider/agent routing decision.

        Args:
            message:     The original user message that was routed.
            intent_type: Detected intent classification (e.g. ``"ask_agent"``).
            agent:       Resolved agent name, or ``None`` if no specific agent.
            confidence:  Parser confidence score in the range ``[0.0, 1.0]``.
        """
        record: dict = {
            "event": "routing_decision",
            "message_preview": message[:120] if message else "",
            "intent_type": intent_type,
            "agent": agent,
            "confidence": round(confidence, 4),
        }
        self._logger.info(
            "Routing: intent=%(intent_type)s agent=%(agent)s confidence=%(confidence)s",
            record,
            extra=record,
        )


class ErrorLogger:
    """Logs errors with full stack traces for post-mortem debugging.

    Uses ``exc_info=True`` so the standard Python logging machinery
    captures the current exception's traceback automatically.

    Usage::

        el = ErrorLogger()
        try:
            risky_operation()
        except Exception as exc:
            el.log_error(exc, context={"request_path": "/api/foo"})
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        self._logger = logger or get_logger("errors")

    def log_error(
        self,
        error: Exception,
        context: Optional[dict] = None,
    ) -> None:
        """Log an exception with its full stack trace.

        The ``exc_info=True`` keyword ensures the traceback is captured
        and included by any log handler that supports it (e.g. the default
        StreamHandler with a suitable Formatter).

        Args:
            error:   The exception instance to log.
            context: Optional dict of additional key/value pairs describing
                     the execution context at the time of the error.
        """
        record: dict = {
            "event": "error",
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
        if context:
            record["context"] = context

        self._logger.error(
            "Error %(error_type)s: %(error_message)s",
            record,
            exc_info=True,
            extra=record,
        )
