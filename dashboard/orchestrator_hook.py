"""Orchestrator Hook for Dashboard Event Emission (AI-172 / REQ-TECH-007).

This module provides a lightweight integration layer between the orchestrator
(agents/orchestrator.py) and the dashboard's AgentMetricsCollector.

The OrchestratorHook class emits reasoning and delegation decision events to the
dashboard server in a non-blocking way. Events are stored via the
AgentMetricsCollector's register_event_callback mechanism (introduced in AI-171).

Usage (basic)::

    from dashboard.orchestrator_hook import OrchestratorHook

    hook = OrchestratorHook()
    hook.attach_to_collector(my_collector)

    # Later, in the orchestrator:
    hook.emit_delegation(agent="coding", task="Implement AI-172", reasoning="Best fit")
    hook.emit_decision({"decision": "use coding agent", "confidence": 0.95})

Usage (HTTP-based, when running without a local collector)::

    hook = OrchestratorHook()
    hook.attach_to_server("http://localhost:8080")

    hook.emit_delegation("linear", "Check for new tickets", "Need to fetch issues")

The module is intentionally self-contained and imports no heavy dependencies so
that it can be used in environments where the full dashboard stack is not
installed.

Design principles:
- All public emit_* methods are non-blocking (fire-and-forget via threading)
- Graceful fallback when no collector or server is attached
- Minimal code changes required in the orchestrator
"""

import asyncio
import logging
import threading
import uuid
from datetime import datetime
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _utcnow_iso() -> str:
    """Return current UTC time as ISO 8601 string with trailing 'Z'."""
    return datetime.utcnow().isoformat() + "Z"


def _build_agent_event(
    agent_name: str,
    task: str,
    reasoning: str,
    event_type: str,
    session_id: str = "",
    extra: Optional[dict] = None,
) -> dict:
    """Build an AgentEvent-compatible dict for an orchestrator event.

    The returned dict is compatible with the AgentEvent TypedDict defined in
    ``dashboard.metrics`` so that it can be passed to any registered event
    callback without modification.

    Args:
        agent_name: Name of the target agent (e.g. "coding", "linear").
        task: Human-readable task description.
        reasoning: Orchestrator's reasoning for the decision.
        event_type: Semantic type: "delegation", "decision", "reasoning", etc.
        session_id: Optional orchestrator session identifier.
        extra: Additional key/value pairs to embed in the ``artifacts`` list.

    Returns:
        A dict matching the AgentEvent schema.
    """
    now = _utcnow_iso()
    artifacts = [
        f"event_type:{event_type}",
        f"reasoning:{reasoning[:200]}",
    ]
    if extra:
        for key, value in extra.items():
            artifacts.append(f"{key}:{str(value)[:100]}")

    return {
        "event_id": str(uuid.uuid4()),
        "agent_name": agent_name or "orchestrator",
        "session_id": session_id or str(uuid.uuid4()),
        "ticket_key": extra.get("ticket_key", "") if extra else "",
        "started_at": now,
        "ended_at": now,
        "duration_seconds": 0.0,
        "status": "success",
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "estimated_cost_usd": 0.0,
        "artifacts": artifacts,
        "error_message": "",
        "model_used": "orchestrator",
        "file_changes": [],
        # Orchestrator-specific extended fields (not in TypedDict but carried in dict)
        "_task": task,
        "_reasoning": reasoning,
        "_event_type": event_type,
    }


# ---------------------------------------------------------------------------
# OrchestratorHook
# ---------------------------------------------------------------------------

class OrchestratorHook:
    """Lightweight event emitter that bridges the orchestrator and dashboard.

    Collects orchestrator lifecycle events (delegation decisions, reasoning
    traces) and forwards them to either a local ``AgentMetricsCollector`` or a
    remote dashboard server via HTTP.

    All emit methods are non-blocking: work is done on a background thread so
    the orchestrator's hot path is never delayed.

    Attributes:
        _collector: The attached AgentMetricsCollector, or None.
        _server_url: Base URL of a remote dashboard server, or None.
        _events: In-memory list of all emitted events (for testing/introspection).
        _session_id: Orchestrator session identifier shared across events.
    """

    def __init__(self, session_id: Optional[str] = None) -> None:
        """Initialise the hook.

        Args:
            session_id: Optional session ID to associate with all events emitted
                by this hook instance. A new UUID is generated if not provided.
        """
        self._collector: Optional[Any] = None
        self._server_url: Optional[str] = None
        self._events: list[dict] = []
        self._session_id: str = session_id or str(uuid.uuid4())
        self._callbacks: list[Callable[[dict], None]] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Attachment methods
    # ------------------------------------------------------------------

    def attach_to_collector(self, collector) -> None:
        """Attach this hook to a local AgentMetricsCollector.

        The hook will use the collector's ``_record_event_callbacks`` channel
        (via direct callback invocation) to emit events. This is the preferred
        integration path when the dashboard server runs in the same process.

        Args:
            collector: An ``AgentMetricsCollector`` instance. Passing ``None``
                detaches the current collector (same as calling ``detach()``).
        """
        self._collector = collector
        if collector is not None:
            logger.debug("OrchestratorHook attached to collector %r", collector)
        else:
            logger.debug("OrchestratorHook detached from collector")

    def attach_to_server(self, server_url: str) -> None:
        """Attach this hook to a remote dashboard HTTP server.

        Events will be POSTed to ``<server_url>/api/agent-event`` in the
        background. This is the fallback path when no local collector is
        available.

        Args:
            server_url: Base URL of the dashboard server
                (e.g. ``"http://localhost:8080"``).
        """
        self._server_url = server_url.rstrip("/")
        logger.debug("OrchestratorHook will POST events to %s", self._server_url)

    def detach(self) -> None:
        """Detach from all outputs.  Events are still stored in ``_events``."""
        self._collector = None
        self._server_url = None
        logger.debug("OrchestratorHook detached from all outputs")

    def add_callback(self, callback: Callable[[dict], None]) -> None:
        """Register an additional in-process callback.

        The callback receives the raw event dict after each emit call. Useful
        for testing and for chaining multiple notification targets.

        Args:
            callback: Callable that accepts a single ``dict`` (event) argument.
        """
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[dict], None]) -> None:
        """Remove a previously registered callback.

        Args:
            callback: The callable to remove. No-op if not registered.
        """
        with self._lock:
            try:
                self._callbacks.remove(callback)
            except ValueError:
                pass

    # ------------------------------------------------------------------
    # Core emit methods
    # ------------------------------------------------------------------

    def emit_delegation(
        self,
        agent: str,
        task: str,
        reasoning: str,
        extra: Optional[dict] = None,
    ) -> None:
        """Emit a delegation decision event.

        Records that the orchestrator has decided to delegate a task to a
        specific agent.  The emission is non-blocking (background thread).

        Args:
            agent: Name of the target agent (e.g. ``"coding"``, ``"linear"``).
            task: Description of the task being delegated.
            reasoning: Orchestrator's rationale for choosing this agent.
            extra: Optional additional metadata (e.g. ``{"ticket_key": "AI-172"}``).
        """
        event = _build_agent_event(
            agent_name=agent,
            task=task,
            reasoning=reasoning,
            event_type="delegation",
            session_id=self._session_id,
            extra=extra,
        )
        self._emit_async(event)

    def emit_decision(
        self,
        decision: Any,
        reasoning: str = "",
        extra: Optional[dict] = None,
    ) -> None:
        """Emit a high-level decision event.

        Records an orchestrator decision that does not necessarily involve a
        direct agent delegation (e.g. choosing which ticket to work on).

        Args:
            decision: The decision data. If a ``dict``, it is used directly as
                the extra context. If a string or other scalar, it is stored
                under the ``"decision"`` key.
            reasoning: Optional reasoning text.
            extra: Optional additional metadata.
        """
        if isinstance(decision, dict):
            merged_extra = {**decision, **(extra or {})}
        else:
            merged_extra = {"decision": str(decision), **(extra or {})}

        agent_name = merged_extra.pop("agent", "orchestrator")
        task = merged_extra.pop("task", str(decision)[:200] if not isinstance(decision, dict) else "")

        event = _build_agent_event(
            agent_name=agent_name,
            task=task,
            reasoning=reasoning or merged_extra.pop("reasoning", ""),
            event_type="decision",
            session_id=self._session_id,
            extra=merged_extra if merged_extra else None,
        )
        self._emit_async(event)

    def emit_reasoning(
        self,
        content: str,
        context: Optional[dict] = None,
    ) -> None:
        """Emit a reasoning trace event.

        Records an orchestrator reasoning step without an associated agent
        delegation.

        Args:
            content: The reasoning text.
            context: Optional contextual metadata dict.
        """
        event = _build_agent_event(
            agent_name="orchestrator",
            task="",
            reasoning=content,
            event_type="reasoning",
            session_id=self._session_id,
            extra=context,
        )
        self._emit_async(event)

    # ------------------------------------------------------------------
    # Internal plumbing
    # ------------------------------------------------------------------

    def _emit_async(self, event: dict) -> None:
        """Store the event and schedule non-blocking delivery.

        The event is always appended to ``self._events`` (in-process store) then
        forwarded to the collector and/or HTTP server on a daemon thread so
        that the calling coroutine is never blocked.

        Any exception raised during forwarding is swallowed and logged so that
        orchestrator execution is never interrupted by dashboard unavailability.

        Args:
            event: The fully-formed event dict to emit.
        """
        # Always record in-memory first (this is synchronous and cheap)
        with self._lock:
            self._events.append(event)
            callbacks_snapshot = list(self._callbacks)

        # Fire-and-forget forwarding on a daemon thread
        t = threading.Thread(
            target=self._deliver,
            args=(event, callbacks_snapshot),
            daemon=True,
            name="orchestrator-hook-emit",
        )
        t.start()

    def _deliver(self, event: dict, callbacks: list) -> None:
        """Deliver a single event to all configured outputs.

        Runs on a background thread. All exceptions are caught so the thread
        never dies with an unhandled error.

        Args:
            event: The event dict to deliver.
            callbacks: Snapshot of extra callbacks to invoke.
        """
        # 1. Invoke extra in-process callbacks
        for cb in callbacks:
            try:
                cb(event)
            except Exception:
                logger.exception("Error in OrchestratorHook callback %r; skipping", cb)

        # 2. Forward to collector if attached
        if self._collector is not None:
            self._deliver_to_collector(event)

        # 3. POST to remote server if URL is configured
        if self._server_url is not None:
            self._deliver_to_server(event)

    def _deliver_to_collector(self, event: dict) -> None:
        """Forward an event via the collector's registered callbacks.

        Rather than going through the collector's full ``track_agent`` lifecycle
        (which would create a spurious session), we directly invoke the
        collector's ``_record_event_callbacks`` list if available, or fall back
        to ``register_event_callback``-registered callbacks.

        Args:
            event: The event dict to forward.
        """
        try:
            collector = self._collector
            if collector is None:
                return

            # Prefer the direct _record_event_callbacks channel (AI-171)
            record_callbacks = getattr(collector, "_record_event_callbacks", None)
            if record_callbacks:
                for cb in list(record_callbacks):
                    try:
                        cb(event)
                    except Exception:
                        logger.exception(
                            "Error in collector callback %r during orchestrator event delivery; skipping",
                            cb,
                        )
                return

            # Fallback: check if the collector exposes a public emit-style method
            emit = getattr(collector, "emit_event", None)
            if callable(emit):
                emit(event)

        except Exception:
            logger.exception("Failed to deliver orchestrator event to collector; continuing")

    def _deliver_to_server(self, event: dict) -> None:
        """POST an event to the remote dashboard server.

        Uses ``urllib`` (stdlib only) so there is no additional dependency.
        Times out after 2 seconds to stay non-blocking from the caller's
        perspective.

        Args:
            event: The event dict to POST.
        """
        import json
        import urllib.request
        import urllib.error

        url = f"{self._server_url}/api/agent-event"
        payload = json.dumps(event).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=2) as resp:
                logger.debug(
                    "OrchestratorHook: POST to %s returned %s", url, resp.status
                )
        except urllib.error.URLError as exc:
            logger.debug(
                "OrchestratorHook: could not reach dashboard server at %s (%s); continuing",
                url,
                exc,
            )
        except Exception:
            logger.exception(
                "OrchestratorHook: unexpected error posting to %s; continuing", url
            )

    # ------------------------------------------------------------------
    # Utility / introspection
    # ------------------------------------------------------------------

    @property
    def events(self) -> list[dict]:
        """Return a copy of all events emitted so far."""
        with self._lock:
            return list(self._events)

    def clear_events(self) -> None:
        """Clear the in-memory event store."""
        with self._lock:
            self._events.clear()

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"OrchestratorHook("
            f"session_id={self._session_id!r}, "
            f"collector={self._collector!r}, "
            f"server_url={self._server_url!r}, "
            f"events={len(self._events)}"
            f")"
        )


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def attach_to_collector(collector) -> "OrchestratorHook":
    """Create a new OrchestratorHook and attach it to the given collector.

    This is the recommended factory function for simple use-cases.

    Args:
        collector: An ``AgentMetricsCollector`` instance.

    Returns:
        A ready-to-use ``OrchestratorHook`` instance.
    """
    hook = OrchestratorHook()
    hook.attach_to_collector(collector)
    return hook


def attach_to_server(server_url: str) -> "OrchestratorHook":
    """Create a new OrchestratorHook configured for HTTP-based event emission.

    Args:
        server_url: Base URL of the dashboard HTTP server.

    Returns:
        A ready-to-use ``OrchestratorHook`` instance.
    """
    hook = OrchestratorHook()
    hook.attach_to_server(server_url)
    return hook
