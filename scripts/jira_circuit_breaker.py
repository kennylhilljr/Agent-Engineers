#!/usr/bin/env python3
"""
Jira Circuit Breaker + Operation Queue + Health Monitor
=========================================================

Provides resilience patterns for Jira API access:

- CircuitBreaker: Stops cascading failures (CLOSED → OPEN → HALF_OPEN)
- OperationQueue: Buffers write operations during outages for replay
- JiraHealthMonitor: Background daemon that probes Jira connectivity
"""

import logging
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from enum import Enum
from typing import Any, Callable, NamedTuple, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Circuit Breaker
# ---------------------------------------------------------------------------


class CircuitState(Enum):
    CLOSED = "closed"       # Normal — requests flow through
    OPEN = "open"           # Broken — requests rejected, writes queued
    HALF_OPEN = "half_open"  # Testing — one probe request allowed


class CircuitBreaker:
    """Circuit breaker for Jira API calls.

    After `failure_threshold` consecutive failures, the circuit opens
    and rejects all requests. After a backoff period it transitions to
    HALF_OPEN, allowing one probe. Success closes the circuit; failure
    reopens it with increased backoff.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        max_backoff: float = 600.0,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.max_backoff = max_backoff

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._consecutive_open_failures = 0  # how many times HALF_OPEN probes failed
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if backoff has elapsed → transition to HALF_OPEN
                backoff = self._get_backoff()
                if time.time() - self._last_failure_time >= backoff:
                    self._state = CircuitState.HALF_OPEN
                    logger.info(
                        f"Circuit breaker → HALF_OPEN (after {backoff:.0f}s backoff)"
                    )
            return self._state

    def can_execute(self) -> bool:
        """Check if a request should be attempted."""
        current = self.state  # triggers OPEN→HALF_OPEN check
        if current == CircuitState.CLOSED:
            return True
        if current == CircuitState.HALF_OPEN:
            return True  # allow one probe
        return False  # OPEN

    def record_success(self) -> None:
        """Record a successful request. Resets the circuit to CLOSED."""
        with self._lock:
            if self._state != CircuitState.CLOSED:
                logger.info("Circuit breaker → CLOSED (success)")
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._consecutive_open_failures = 0

    def record_failure(self, error: Optional[Exception] = None) -> None:
        """Record a failed request. Opens circuit after threshold."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Probe failed — go back to OPEN with increased backoff
                self._consecutive_open_failures += 1
                self._state = CircuitState.OPEN
                backoff = self._get_backoff()
                logger.warning(
                    f"Circuit breaker → OPEN (probe failed, "
                    f"next attempt in {backoff:.0f}s): {error}"
                )
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                backoff = self._get_backoff()
                logger.warning(
                    f"Circuit breaker → OPEN ({self._failure_count} failures, "
                    f"next attempt in {backoff:.0f}s): {error}"
                )

    def reset(self) -> None:
        """Force-reset the circuit to CLOSED."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._consecutive_open_failures = 0
            logger.info("Circuit breaker force-reset → CLOSED")

    def _get_backoff(self) -> float:
        """Exponential backoff: min(recovery_timeout * 2^n, max_backoff)."""
        exponent = self._consecutive_open_failures
        return min(self.recovery_timeout * (2 ** exponent), self.max_backoff)


# ---------------------------------------------------------------------------
# Operation Queue
# ---------------------------------------------------------------------------


class QueuedOperation(NamedTuple):
    method: str
    path: str
    body: Optional[dict]
    timestamp: float


class OperationQueue:
    """Buffers write operations during circuit-open periods for later replay.

    Only write operations (POST, PUT) are queued. Reads fail immediately
    when the circuit is open since stale data is worse than no data.
    """

    def __init__(self, max_size: int = 100, max_age: float = 3600.0):
        self._queue: deque[QueuedOperation] = deque(maxlen=max_size)
        self._max_age = max_age
        self._lock = threading.Lock()

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._queue)

    def enqueue(self, method: str, path: str, body: Optional[dict] = None) -> None:
        """Add a write operation to the queue."""
        with self._lock:
            op = QueuedOperation(
                method=method, path=path, body=body, timestamp=time.time()
            )
            self._queue.append(op)
            logger.info(f"Queued {method} {path} ({len(self._queue)} in queue)")

    def drain(self) -> list[QueuedOperation]:
        """Return and remove all queued operations, discarding stale ones."""
        with self._lock:
            now = time.time()
            ops = [
                op for op in self._queue
                if (now - op.timestamp) < self._max_age
            ]
            stale = len(self._queue) - len(ops)
            if stale > 0:
                logger.info(f"Discarded {stale} stale queued operations")
            self._queue.clear()
            return ops

    def clear(self) -> None:
        """Discard all queued operations."""
        with self._lock:
            count = len(self._queue)
            self._queue.clear()
            if count:
                logger.info(f"Cleared {count} queued operations")


# ---------------------------------------------------------------------------
# Health Monitor
# ---------------------------------------------------------------------------


class JiraHealthMonitor:
    """Background daemon that periodically probes Jira connectivity.

    Runs a GET /rest/api/3/myself probe at a configurable interval.
    Calls registered recovery callbacks when connectivity is restored.
    """

    def __init__(self, auth_manager: Any, check_interval: float = 60.0):
        self._auth_manager = auth_manager
        self._check_interval = check_interval
        self._healthy = True
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._recovery_callbacks: list[Callable[[], None]] = []
        self._lock = threading.Lock()

    @property
    def is_healthy(self) -> bool:
        with self._lock:
            return self._healthy

    def start(self) -> None:
        """Start the health monitor daemon thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._health_loop, daemon=True, name="jira-health-monitor"
        )
        self._thread.start()
        logger.info(
            f"Jira health monitor started (interval={self._check_interval}s)"
        )

    def stop(self) -> None:
        """Stop the health monitor."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self._check_interval + 5)
            self._thread = None
        logger.info("Jira health monitor stopped")

    def on_recovery(self, callback: Callable[[], None]) -> None:
        """Register a callback to run when Jira connectivity is restored."""
        self._recovery_callbacks.append(callback)

    def _health_loop(self) -> None:
        """Periodically check Jira connectivity."""
        while not self._stop_event.is_set():
            try:
                healthy = self._probe()
                was_healthy = self.is_healthy

                with self._lock:
                    self._healthy = healthy

                if healthy and not was_healthy:
                    logger.info("Jira connectivity RESTORED")
                    for cb in self._recovery_callbacks:
                        try:
                            cb()
                        except Exception as e:
                            logger.error(f"Recovery callback failed: {e}")
                elif not healthy and was_healthy:
                    logger.warning("Jira connectivity LOST")

            except Exception as e:
                logger.error(f"Health check error: {e}")
                with self._lock:
                    self._healthy = False

            self._stop_event.wait(self._check_interval)

    def _probe(self) -> bool:
        """Send a lightweight probe to Jira."""
        try:
            headers = self._auth_manager.get_auth_headers()
            base_url = self._auth_manager.get_base_url()
            url = f"{base_url}/rest/api/3/myself"

            req = urllib.request.Request(url, method="GET", headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except urllib.error.HTTPError as e:
            if e.code == 401:
                # Auth expired — try invalidating and refreshing
                self._auth_manager.invalidate_token()
                try:
                    headers = self._auth_manager.get_auth_headers()
                    base_url = self._auth_manager.get_base_url()
                    url = f"{base_url}/rest/api/3/myself"
                    req = urllib.request.Request(url, method="GET", headers=headers)
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        return resp.status == 200
                except Exception:
                    return False
            return False
        except Exception:
            return False
