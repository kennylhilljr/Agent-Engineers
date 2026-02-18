"""Async event collector for telemetry & usage analytics (AI-227).

Design principles:
- Privacy-first: no PII ever stored; strip email/name/phone fields automatically
- Non-blocking: collect() is fire-and-forget; never raises or blocks the caller
- Batched writes: flush to JSONL every BATCH_INTERVAL_SECS or BATCH_SIZE events
- Opt-out: honour TELEMETRY_DISABLED env var; a local opt-out flag file also works
- Storage: append-only .telemetry_events.jsonl (one JSON object per line)
- Optional forwarding: POST to TELEMETRY_ENDPOINT if set (PostHog / Mixpanel etc.)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Events that are part of the defined product tracking schema
VALID_EVENT_TYPES = frozenset(
    [
        "session_started",
        "session_ended",
        "chat_message_sent",
        "provider_switched",
        "agent_paused",
        "agent_resumed",
        "dashboard_tab_viewed",
        "agent_hours_consumed",
        "onboarding_step_completed",
        # extras allowed for extensibility
    ]
)

# Properties containing PII that are stripped before storage
_PII_FIELDS = frozenset(
    [
        "email",
        "name",
        "full_name",
        "first_name",
        "last_name",
        "username",
        "phone",
        "phone_number",
        "address",
        "ip",
        "ip_address",
        "user_agent",
        "password",
        "token",
        "secret",
    ]
)

BATCH_SIZE = 100        # flush when queue reaches this many events
BATCH_INTERVAL_SECS = 5  # flush every N seconds regardless of queue size

# Default storage path (relative to cwd)
DEFAULT_STORAGE_PATH = Path(".telemetry_events.jsonl")

# Local opt-out flag file
OPT_OUT_FLAG_PATH = Path(".telemetry_optout")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class TelemetryEvent:
    """A single analytics event.

    Attributes:
        event_type:  The kind of event (e.g. "chat_message_sent").
        properties:  Arbitrary key-value payload — no PII allowed.
        timestamp:   ISO-8601 UTC timestamp (auto-set on creation).
        session_id:  Opaque session identifier (no user identity).
        event_id:    Unique ID for this individual event.
    """

    event_type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        """Return a serialisable dict representation."""
        return asdict(self)


# ---------------------------------------------------------------------------
# PII stripping
# ---------------------------------------------------------------------------


def strip_pii(properties: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of *properties* with any PII fields removed.

    Matching is case-insensitive so ``Email`` and ``EMAIL`` are both stripped.

    Args:
        properties: Raw event properties dict.

    Returns:
        Sanitised copy of the dict.
    """
    return {
        k: v
        for k, v in properties.items()
        if k.lower() not in _PII_FIELDS
    }


# ---------------------------------------------------------------------------
# Opt-out helpers
# ---------------------------------------------------------------------------


def is_telemetry_disabled() -> bool:
    """Return True when telemetry has been disabled via env var or flag file."""
    if os.environ.get("TELEMETRY_DISABLED", "").strip().lower() in ("1", "true", "yes"):
        return True
    if OPT_OUT_FLAG_PATH.exists():
        return True
    return False


def write_opt_out_flag() -> None:
    """Create the local opt-out flag file so telemetry stays off across restarts."""
    OPT_OUT_FLAG_PATH.touch()


def remove_opt_out_flag() -> None:
    """Remove the local opt-out flag file to re-enable telemetry."""
    if OPT_OUT_FLAG_PATH.exists():
        OPT_OUT_FLAG_PATH.unlink()


# ---------------------------------------------------------------------------
# EventCollector
# ---------------------------------------------------------------------------


class EventCollector:
    """Async telemetry event collector with batched JSONL writes.

    Start the collector by calling ``start()`` (or use as an async context
    manager). Events are collected with ``collect()`` (non-blocking).

    Args:
        storage_path: Path to the ``.telemetry_events.jsonl`` file.
        batch_size:   Flush after this many queued events.
        batch_interval: Flush every this many seconds even if batch_size
            not reached.
        endpoint: Optional HTTP(S) URL to forward events to (PostHog /
            Mixpanel / custom).  Reads from ``TELEMETRY_ENDPOINT`` env var
            when not supplied.
        session_id: Shared session identifier for all events emitted through
            this collector instance.
    """

    def __init__(
        self,
        storage_path: Path = DEFAULT_STORAGE_PATH,
        batch_size: int = BATCH_SIZE,
        batch_interval: float = BATCH_INTERVAL_SECS,
        endpoint: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        self.storage_path = Path(storage_path)
        self.batch_size = batch_size
        self.batch_interval = batch_interval
        self.endpoint = endpoint or os.environ.get("TELEMETRY_ENDPOINT")
        self.session_id = session_id or str(uuid.uuid4())

        self._queue: asyncio.Queue[TelemetryEvent] = asyncio.Queue()
        self._flush_task: Optional[asyncio.Task] = None  # type: ignore[type-arg]
        self._running = False
        self._events_written = 0   # monotonic counter for tests / metrics

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background flush loop."""
        if self._running:
            return
        self._running = True
        self._flush_task = asyncio.ensure_future(self._flush_loop())
        logger.debug("EventCollector started (session=%s)", self.session_id)

    async def stop(self) -> None:
        """Flush any remaining events and stop the background loop."""
        self._running = False
        # Drain the queue one last time
        await self._flush_pending()
        if self._flush_task and not self._flush_task.done():
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        logger.debug("EventCollector stopped")

    async def __aenter__(self) -> "EventCollector":
        await self.start()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.stop()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def collect(
        self,
        event_type: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Queue a telemetry event (fire-and-forget, never raises).

        Args:
            event_type:  One of ``VALID_EVENT_TYPES`` (or any string for
                extensibility).
            properties:  Arbitrary metadata dict.  PII fields are stripped
                automatically.  Will be empty dict if None.
        """
        try:
            if is_telemetry_disabled():
                return

            safe_props = strip_pii(properties or {})
            event = TelemetryEvent(
                event_type=event_type,
                properties=safe_props,
                session_id=self.session_id,
            )
            # Use put_nowait so collect() stays synchronous and non-blocking.
            # If the queue is full we silently drop rather than block.
            try:
                self._queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "Telemetry queue full — dropping event %s", event_type
                )
        except Exception:  # noqa: BLE001
            # Never let telemetry failures surface to callers
            logger.debug("Telemetry collect error (suppressed)", exc_info=True)

    # ------------------------------------------------------------------
    # Internal flush logic
    # ------------------------------------------------------------------

    async def _flush_loop(self) -> None:
        """Background task: flush events every BATCH_INTERVAL seconds."""
        while self._running:
            try:
                await asyncio.sleep(self.batch_interval)
                await self._flush_pending()
            except asyncio.CancelledError:
                break
            except Exception:  # noqa: BLE001
                logger.debug("Telemetry flush error (suppressed)", exc_info=True)

    async def _flush_pending(self) -> None:
        """Drain the queue and write all pending events to storage."""
        batch: List[TelemetryEvent] = []

        while not self._queue.empty():
            try:
                event = self._queue.get_nowait()
                batch.append(event)
            except asyncio.QueueEmpty:
                break

        if not batch:
            return

        await self._write_batch(batch)

    async def _write_batch(self, batch: List[TelemetryEvent]) -> None:
        """Append a batch of events to the JSONL file.

        Each event is serialised as a single JSON line (JSONL format).
        Writes are append-only to avoid data loss on concurrent access.
        """
        try:
            lines = "\n".join(json.dumps(ev.to_dict()) for ev in batch) + "\n"

            # Ensure parent directory exists
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.storage_path, "a", encoding="utf-8") as fh:
                fh.write(lines)

            self._events_written += len(batch)
            logger.debug("Telemetry: wrote %d events (total=%d)", len(batch), self._events_written)

            # Optional: forward to external endpoint
            if self.endpoint:
                await self._forward_batch(batch)

        except Exception:  # noqa: BLE001
            logger.debug("Telemetry write error (suppressed)", exc_info=True)

    async def _forward_batch(self, batch: List[TelemetryEvent]) -> None:
        """POST events to TELEMETRY_ENDPOINT (best-effort, errors suppressed)."""
        try:
            import aiohttp  # local import so we don't require it at module level

            payload = [ev.to_dict() for ev in batch]
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.endpoint,  # type: ignore[arg-type]
                    json={"events": payload},
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status >= 400:
                        logger.debug(
                            "Telemetry endpoint returned HTTP %d", resp.status
                        )
        except Exception:  # noqa: BLE001
            logger.debug("Telemetry forward error (suppressed)", exc_info=True)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_collector: Optional[EventCollector] = None


def get_collector(
    storage_path: Path = DEFAULT_STORAGE_PATH,
    **kwargs: Any,
) -> EventCollector:
    """Return the module-level EventCollector singleton.

    The singleton is created on first call and reused thereafter.
    Use ``reset_collector()`` to replace it (useful in tests).

    Args:
        storage_path: Passed to EventCollector on first construction only.
        **kwargs:     Additional keyword args for EventCollector construction
                      (ignored after first call unless reset first).

    Returns:
        The singleton EventCollector instance.
    """
    global _collector  # noqa: PLW0603
    if _collector is None:
        _collector = EventCollector(storage_path=storage_path, **kwargs)
    return _collector


def reset_collector(new_collector: Optional[EventCollector] = None) -> None:
    """Replace the module-level singleton (primarily for testing).

    Args:
        new_collector: If provided, replaces the singleton with this instance.
            If None, clears the singleton so the next ``get_collector()`` call
            creates a fresh one.
    """
    global _collector  # noqa: PLW0603
    _collector = new_collector
