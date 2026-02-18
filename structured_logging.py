"""Structured logging for Agent-Engineers.

Provides JSON-formatted structured logging with consistent fields
across all components. Replaces scattered logging setup.
"""
from __future__ import annotations

import logging
import json
import time
import sys
from typing import Any, Optional
from datetime import datetime, timezone


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured log output."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        # Add extra fields
        if hasattr(record, "extra"):
            log_entry.update(record.extra)
        # Add exception info
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def get_structured_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Get a logger configured for structured JSON output.

    Args:
        name: Logger name (typically __name__)
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance

    Example:
        >>> logger = get_structured_logger(__name__)
        >>> logger.info("Agent started", extra={"extra": {"agent_id": "abc-123"}})
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


class MetricsCollector:
    """Simple in-memory metrics collection.

    Collects counters, gauges, and timing metrics for observability.

    Example:
        >>> metrics = MetricsCollector()
        >>> metrics.increment("requests_total")
        >>> metrics.gauge("active_agents", 3)
        >>> with metrics.timer("task_duration"):
        ...     time.sleep(0.1)
    """

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}
        self._gauges: dict[str, float] = {}
        self._timings: dict[str, list[float]] = {}

    def increment(self, name: str, amount: int = 1) -> None:
        """Increment a counter metric."""
        self._counters[name] = self._counters.get(name, 0) + amount

    def gauge(self, name: str, value: float) -> None:
        """Set a gauge metric value."""
        self._gauges[name] = value

    def record_timing(self, name: str, duration: float) -> None:
        """Record a timing measurement."""
        if name not in self._timings:
            self._timings[name] = []
        self._timings[name].append(duration)

    class _Timer:
        def __init__(self, collector: "MetricsCollector", name: str) -> None:
            self._collector = collector
            self._name = name
            self._start = 0.0

        def __enter__(self) -> "_Timer":
            self._start = time.monotonic()
            return self

        def __exit__(self, *args: Any) -> None:
            self._collector.record_timing(self._name, time.monotonic() - self._start)

    def timer(self, name: str) -> "_Timer":
        """Context manager for timing a block of code."""
        return self._Timer(self, name)

    def get_stats(self) -> dict[str, Any]:
        """Return all collected metrics as a dict."""
        stats: dict[str, Any] = {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "timings": {},
        }
        for name, values in self._timings.items():
            if values:
                stats["timings"][name] = {
                    "count": len(values),
                    "mean": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "total": sum(values),
                }
        return stats

    def reset(self) -> None:
        """Reset all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._timings.clear()


class HealthChecker:
    """Health check endpoint implementation.

    Example:
        >>> checker = HealthChecker()
        >>> checker.register("database", lambda: {"status": "ok"})
        >>> result = checker.check_all()
        >>> result["status"]
        'healthy'
    """

    def __init__(self) -> None:
        self._checks: dict[str, Any] = {}

    def register(self, name: str, check_fn: Any) -> None:
        """Register a health check function."""
        self._checks[name] = check_fn

    def check_all(self) -> dict[str, Any]:
        """Run all health checks and return aggregate status."""
        results: dict[str, Any] = {}
        overall_healthy = True

        for name, check_fn in self._checks.items():
            try:
                result = check_fn()
                results[name] = result or {"status": "ok"}
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}
                overall_healthy = False

        return {
            "status": "healthy" if overall_healthy else "degraded",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "checks": results,
        }


# Global instances
_metrics = MetricsCollector()
_health = HealthChecker()


def get_metrics() -> MetricsCollector:
    """Get the global MetricsCollector instance."""
    return _metrics


def get_health_checker() -> HealthChecker:
    """Get the global HealthChecker instance."""
    return _health
