"""Crash isolation utilities for dashboard-orchestrator boundary.

Ensures dashboard failures are isolated from orchestrator execution.

This module provides decorators and wrapper classes that prevent dashboard
errors from propagating to the orchestrator. All exceptions are caught, logged,
and replaced with a configurable fallback value so the orchestrator can
continue running even if the dashboard is completely unavailable.

Design principles:
- Zero exceptions escape to callers
- Errors are always logged (not silently swallowed)
- Fallback values are explicit and configurable
- Async functions are handled with a dedicated decorator
"""

import asyncio
import functools
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def isolated(fallback=None, log_level=logging.WARNING):
    """Decorator that catches all exceptions, logs them, and returns a fallback.

    Use this to wrap any dashboard function that must not propagate exceptions
    to the orchestrator. The wrapped function behaves normally when no
    exception occurs. On exception the fallback value is returned instead.

    Args:
        fallback: Value to return when the decorated function raises. Defaults
            to None.
        log_level: Logging level used when an exception is caught. Defaults to
            logging.WARNING.

    Returns:
        Decorator that wraps the target function with exception isolation.

    Example::

        @isolated(fallback=False)
        def risky_dashboard_call():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.log(
                    log_level,
                    "Dashboard call failed (isolated): %s: %s",
                    func.__name__,
                    e,
                )
                return fallback
        return wrapper
    return decorator


def isolated_async(fallback=None, log_level=logging.WARNING):
    """Async version of the :func:`isolated` decorator.

    Provides the same semantics as :func:`isolated` but for ``async def``
    functions. The returned coroutine never raises; exceptions are caught and
    the fallback value is returned instead.

    Args:
        fallback: Value to return when the decorated coroutine raises. Defaults
            to None.
        log_level: Logging level used when an exception is caught. Defaults to
            logging.WARNING.

    Returns:
        Decorator that wraps the target coroutine with exception isolation.

    Example::

        @isolated_async(fallback=[])
        async def broadcast_to_clients(msg):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.log(
                    log_level,
                    "Dashboard async call failed (isolated): %s: %s",
                    func.__name__,
                    e,
                )
                return fallback
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# IsolatedDashboardClient
# ---------------------------------------------------------------------------

class IsolatedDashboardClient:
    """Wrapper around an OrchestratorHook that isolates all failures.

    This class provides the same public interface as the OrchestratorHook's
    emit_* methods but wraps every call in exception isolation. This means:

    - If the hook is None (dashboard not running), calls are silently no-ops.
    - If the hook raises on any emit call, the exception is caught and logged
      but not re-raised.
    - The ``available`` property lets callers check if a hook is present.

    Typical usage::

        hook = try_start_dashboard()           # may return None
        client = IsolatedDashboardClient(hook)

        # Safe to call even if hook is None or broken:
        client.emit_delegation("coding", "Implement AI-183", "Best agent")
        client.emit_decision({"agent": "linear", "confidence": 0.9})
        client.emit_reasoning("Choosing best agent based on task type")

    Attributes:
        _hook: The underlying OrchestratorHook, or None.
        _available: Whether a hook is attached.
    """

    def __init__(self, hook: Optional[Any] = None) -> None:
        """Initialise the isolated client.

        Args:
            hook: An ``OrchestratorHook`` instance, or ``None`` when the
                dashboard is not running. Passing ``None`` puts the client in
                no-op mode where all emit calls are silently ignored.
        """
        self._hook = hook
        self._available: bool = hook is not None

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Return True if a dashboard hook is attached."""
        return self._available

    # ------------------------------------------------------------------
    # Emit methods (isolated)
    # ------------------------------------------------------------------

    def emit_delegation(self, *args, **kwargs) -> None:
        """Emit a delegation event; silently no-ops if dashboard unavailable.

        Forwards to the hook's ``emit_delegation`` method with full isolation.
        Any exception raised by the hook is caught and logged but not
        re-raised so the orchestrator is never interrupted.

        Args:
            *args: Positional arguments forwarded to ``hook.emit_delegation``.
            **kwargs: Keyword arguments forwarded to ``hook.emit_delegation``.
        """
        if self._hook is None:
            return
        try:
            self._hook.emit_delegation(*args, **kwargs)
        except Exception as e:
            logger.warning(
                "IsolatedDashboardClient.emit_delegation failed (isolated): %s", e
            )

    def emit_decision(self, *args, **kwargs) -> None:
        """Emit a decision event; silently no-ops if dashboard unavailable.

        Forwards to the hook's ``emit_decision`` method with full isolation.
        Any exception raised by the hook is caught and logged but not
        re-raised so the orchestrator is never interrupted.

        Args:
            *args: Positional arguments forwarded to ``hook.emit_decision``.
            **kwargs: Keyword arguments forwarded to ``hook.emit_decision``.
        """
        if self._hook is None:
            return
        try:
            self._hook.emit_decision(*args, **kwargs)
        except Exception as e:
            logger.warning(
                "IsolatedDashboardClient.emit_decision failed (isolated): %s", e
            )

    def emit_reasoning(self, *args, **kwargs) -> None:
        """Emit a reasoning trace event; silently no-ops if dashboard unavailable.

        Forwards to the hook's ``emit_reasoning`` method with full isolation.
        Any exception raised by the hook is caught and logged but not
        re-raised so the orchestrator is never interrupted.

        Args:
            *args: Positional arguments forwarded to ``hook.emit_reasoning``.
            **kwargs: Keyword arguments forwarded to ``hook.emit_reasoning``.
        """
        if self._hook is None:
            return
        try:
            self._hook.emit_reasoning(*args, **kwargs)
        except Exception as e:
            logger.warning(
                "IsolatedDashboardClient.emit_reasoning failed (isolated): %s", e
            )

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"IsolatedDashboardClient("
            f"available={self._available}, "
            f"hook={self._hook!r}"
            f")"
        )
