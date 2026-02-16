"""Structured JSON Logging Configuration for Agent Dashboard.

This module provides a centralized logging configuration with:
- JSON-formatted logs for easy parsing and aggregation
- Structured fields (timestamp, level, module, message, extra context)
- Multiple handlers (console, file, rotating file)
- Performance metrics logging
- Request/response logging middleware
- Correlation IDs for tracing requests across services

Usage:
    from dashboard.logging_config import get_logger, setup_logging

    # Setup logging once at application startup
    setup_logging(log_level="INFO", log_file="app.log")

    # Get logger for a module
    logger = get_logger(__name__)

    # Log with structured context
    logger.info("User login", extra={
        "user_id": "123",
        "ip_address": "192.168.1.1",
        "user_agent": "Mozilla/5.0"
    })

    # Log performance metrics
    logger.info("API request completed", extra={
        "duration_ms": 150,
        "status_code": 200,
        "endpoint": "/api/metrics"
    })
"""

import json
import logging
import logging.handlers
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Default log directory
DEFAULT_LOG_DIR = Path("logs")

# Default log file names
DEFAULT_LOG_FILE = "dashboard.log"
DEFAULT_ERROR_LOG_FILE = "dashboard_error.log"
DEFAULT_ACCESS_LOG_FILE = "dashboard_access.log"

# Default log format
DEFAULT_LOG_LEVEL = "INFO"

# Max log file size (10 MB)
MAX_LOG_FILE_SIZE = 10 * 1024 * 1024

# Number of backup log files to keep
BACKUP_COUNT = 5


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging.

    Outputs logs in JSON format with standard fields:
    - timestamp: ISO 8601 timestamp
    - level: Log level (INFO, WARNING, ERROR, etc.)
    - logger: Logger name (usually module name)
    - message: Log message
    - extra: Additional context fields
    - exception: Exception details (if present)
    - stack_trace: Stack trace (if exception present)
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: LogRecord instance

        Returns:
            JSON-formatted log string
        """
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add process and thread info
        log_data["process_id"] = record.process
        log_data["thread_id"] = record.thread
        log_data["thread_name"] = record.threadName

        # Add extra fields from record (anything added via extra={})
        extra_fields = {}
        for key, value in record.__dict__.items():
            # Skip standard LogRecord attributes
            if key not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]:
                extra_fields[key] = value

        if extra_fields:
            log_data["extra"] = extra_fields

        # Add exception info if present
        if record.exc_info and isinstance(record.exc_info, tuple):
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "stack_trace": self.formatException(record.exc_info)
            }

        # Add stack info if present
        if record.stack_info:
            log_data["stack_info"] = record.stack_info

        return json.dumps(log_data, default=str)


class ColoredConsoleFormatter(logging.Formatter):
    """Colored console formatter for human-readable output.

    Uses ANSI color codes to highlight different log levels.
    Falls back to plain text if terminal doesn't support colors.
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
        "RESET": "\033[0m"        # Reset
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors.

        Args:
            record: LogRecord instance

        Returns:
            Colored log string
        """
        # Check if terminal supports colors
        if not sys.stdout.isatty():
            return super().format(record)

        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            colored_level = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
            record.levelname = colored_level

        # Format the record
        formatted = super().format(record)

        # Reset levelname to original (in case record is reused)
        record.levelname = levelname

        return formatted


class RequestContextFilter(logging.Filter):
    """Filter that adds request context to log records.

    Adds correlation_id, request_id, user_id, etc. to logs
    if they are present in the current context.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Add context fields to record.

        Args:
            record: LogRecord instance

        Returns:
            True (always allow record through)
        """
        # Try to get context from thread-local storage
        # This would be set by middleware in web requests
        try:
            import contextvars

            # Example: get correlation_id from context
            # correlation_id = correlation_id_var.get(None)
            # if correlation_id:
            #     record.correlation_id = correlation_id
            pass
        except (ImportError, Exception):
            pass

        return True


def setup_logging(
    log_level: str = DEFAULT_LOG_LEVEL,
    log_dir: Optional[Path] = None,
    log_file: str = DEFAULT_LOG_FILE,
    error_log_file: str = DEFAULT_ERROR_LOG_FILE,
    enable_console: bool = True,
    enable_json: bool = True,
    enable_color: bool = True
) -> None:
    """Setup structured logging for the application.

    Configures logging handlers for:
    - Console output (colored, human-readable)
    - Main log file (JSON format, rotating)
    - Error log file (JSON format, errors only, rotating)

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory for log files (default: ./logs)
        log_file: Main log file name
        error_log_file: Error log file name
        enable_console: Enable console output
        enable_json: Enable JSON formatting for file logs
        enable_color: Enable colored console output
    """
    # Create log directory if it doesn't exist
    if log_dir is None:
        log_dir = DEFAULT_LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler (human-readable)
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)

        if enable_color:
            console_formatter = ColoredConsoleFormatter(
                fmt="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
        else:
            console_formatter = logging.Formatter(
                fmt="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )

        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # Main log file handler (JSON format, rotating)
    main_log_path = log_dir / log_file
    main_file_handler = logging.handlers.RotatingFileHandler(
        filename=main_log_path,
        maxBytes=MAX_LOG_FILE_SIZE,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    main_file_handler.setLevel(log_level)

    if enable_json:
        main_file_handler.setFormatter(JSONFormatter())
    else:
        main_file_handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        ))

    root_logger.addHandler(main_file_handler)

    # Error log file handler (JSON format, errors only, rotating)
    error_log_path = log_dir / error_log_file
    error_file_handler = logging.handlers.RotatingFileHandler(
        filename=error_log_path,
        maxBytes=MAX_LOG_FILE_SIZE,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    error_file_handler.setLevel(logging.ERROR)

    if enable_json:
        error_file_handler.setFormatter(JSONFormatter())
    else:
        error_file_handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        ))

    root_logger.addHandler(error_file_handler)

    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging initialized",
        extra={
            "log_level": log_level,
            "log_dir": str(log_dir),
            "log_file": log_file,
            "error_log_file": error_log_file,
            "enable_console": enable_console,
            "enable_json": enable_json,
            "enable_color": enable_color
        }
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class LoggingMiddleware:
    """AIOHTTP middleware for request/response logging.

    Logs all HTTP requests and responses with:
    - Request method, path, headers, query params
    - Response status code, duration
    - Client IP, user agent
    - Correlation ID for tracing
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize logging middleware.

        Args:
            logger: Logger instance (default: create new logger)
        """
        self.logger = logger or get_logger("dashboard.access")

    async def __call__(self, app, handler):
        """Middleware handler function.

        Args:
            app: AIOHTTP application
            handler: Next handler in chain

        Returns:
            Response
        """
        async def middleware_handler(request):
            """Handle request with logging."""
            import time

            # Start timing
            start_time = time.time()

            # Generate correlation ID
            correlation_id = request.headers.get("X-Correlation-ID", str(id(request)))

            # Log request
            self.logger.info(
                "HTTP request started",
                extra={
                    "correlation_id": correlation_id,
                    "method": request.method,
                    "path": request.path,
                    "query_string": str(request.query_string),
                    "client_ip": request.remote,
                    "user_agent": request.headers.get("User-Agent", ""),
                    "content_length": request.content_length or 0
                }
            )

            try:
                # Call next handler
                response = await handler(request)

                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Log response
                self.logger.info(
                    "HTTP request completed",
                    extra={
                        "correlation_id": correlation_id,
                        "method": request.method,
                        "path": request.path,
                        "status_code": response.status,
                        "duration_ms": round(duration_ms, 2),
                        "response_size": response.content_length or 0
                    }
                )

                # Add correlation ID to response headers
                response.headers["X-Correlation-ID"] = correlation_id

                return response

            except Exception as e:
                # Calculate duration
                duration_ms = (time.time() - start_time) * 1000

                # Log error
                self.logger.error(
                    "HTTP request failed",
                    extra={
                        "correlation_id": correlation_id,
                        "method": request.method,
                        "path": request.path,
                        "duration_ms": round(duration_ms, 2),
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    },
                    exc_info=True
                )

                raise

        return middleware_handler


def log_performance_metric(
    logger: logging.Logger,
    metric_name: str,
    duration_ms: float,
    **extra_context
) -> None:
    """Log a performance metric.

    Args:
        logger: Logger instance
        metric_name: Name of the metric (e.g., "db_query", "api_call")
        duration_ms: Duration in milliseconds
        **extra_context: Additional context fields
    """
    logger.info(
        f"Performance metric: {metric_name}",
        extra={
            "metric_type": "performance",
            "metric_name": metric_name,
            "duration_ms": round(duration_ms, 2),
            **extra_context
        }
    )


def log_business_event(
    logger: logging.Logger,
    event_type: str,
    event_name: str,
    **extra_context
) -> None:
    """Log a business event.

    Args:
        logger: Logger instance
        event_type: Type of event (e.g., "user_action", "system_event")
        event_name: Name of the event
        **extra_context: Additional context fields
    """
    logger.info(
        f"Business event: {event_name}",
        extra={
            "event_type": event_type,
            "event_name": event_name,
            **extra_context
        }
    )


# Convenience function for structured logging
def log_with_context(
    logger: logging.Logger,
    level: str,
    message: str,
    **context
) -> None:
    """Log a message with structured context.

    Args:
        logger: Logger instance
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        message: Log message
        **context: Additional context fields
    """
    log_func = getattr(logger, level.lower())
    log_func(message, extra=context)
