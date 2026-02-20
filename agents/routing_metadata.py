"""Routing Metadata for Agent Dashboard (AI-255).

Records and retrieves agent routing decisions so the orchestrator's agent
assignments are explainable and auditable.

Every time the orchestrator selects an agent it should call
``log_routing_decision()`` to persist a ``RoutingDecision`` record.
Historical records can be retrieved per-session via
``get_routing_history()``.

The in-memory store is intentionally simple (a module-level dict keyed on
session_id).  It is sufficient for single-process deployments and unit tests.
For multi-process or persistent deployments the same interface can be backed
by a database or file store without changing callers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory routing log: {session_id: [RoutingDecision, ...]}
# ---------------------------------------------------------------------------
_routing_log: Dict[str, List[Dict]] = {}


# ---------------------------------------------------------------------------
# RoutingDecision dataclass
# ---------------------------------------------------------------------------


@dataclass
class RoutingDecision:
    """Captures a single agent-selection decision made by the orchestrator.

    Attributes:
        session_id: Unique identifier for the orchestrator session.
        agent_selected: The agent that was chosen (e.g. ``"coding"``,
            ``"pr_reviewer_fast"``).
        routing_reason: Human-readable explanation of why this agent was
            selected (e.g. ``"file count <= 3, no complexity keywords"``).
        alternatives_considered: Other agents that were evaluated but not
            selected.
        complexity_score: Integer 1–10 from ``estimate_complexity()``.  Use
            ``0`` when not applicable.
        model_tier: The model tier selected (``"haiku"``, ``"sonnet"``, or
            ``"opus"``).
        timestamp: ISO 8601 UTC timestamp of the decision.  Defaults to the
            current time when the instance is created.
        task_description: Optional short description of the task being routed.
    """

    session_id: str
    agent_selected: str
    routing_reason: str
    alternatives_considered: List[str] = field(default_factory=list)
    complexity_score: int = 0
    model_tier: str = "sonnet"
    timestamp: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())
    task_description: str = ""

    def to_dict(self) -> Dict:
        """Return a JSON-serialisable dict representation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "RoutingDecision":
        """Reconstruct a RoutingDecision from a plain dict.

        Unknown keys are silently ignored so that older serialised records
        remain loadable after fields are added to the dataclass.
        """
        known = {
            "session_id",
            "agent_selected",
            "routing_reason",
            "alternatives_considered",
            "complexity_score",
            "model_tier",
            "timestamp",
            "task_description",
        }
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def log_routing_decision(
    session_id: str,
    decision: RoutingDecision,
) -> None:
    """Persist a routing decision to the in-memory log.

    Args:
        session_id: Session identifier.  Must match ``decision.session_id``
            (the argument is accepted for convenience / explicitness; they
            are reconciled internally).
        decision: The routing decision to record.

    Side-effects:
        - Appends a dict representation to ``_routing_log[session_id]``.
        - Logs an INFO message for observability.
    """
    # Reconcile session_id between argument and dataclass field
    if decision.session_id != session_id:
        logger.warning(
            "session_id mismatch: argument=%s, decision.session_id=%s — "
            "using argument value",
            session_id,
            decision.session_id,
        )
        decision = RoutingDecision(
            session_id=session_id,
            agent_selected=decision.agent_selected,
            routing_reason=decision.routing_reason,
            alternatives_considered=decision.alternatives_considered,
            complexity_score=decision.complexity_score,
            model_tier=decision.model_tier,
            timestamp=decision.timestamp,
            task_description=decision.task_description,
        )

    if session_id not in _routing_log:
        _routing_log[session_id] = []

    record = decision.to_dict()
    _routing_log[session_id].append(record)

    logger.info(
        "Routing decision logged",
        extra={
            "session_id": session_id,
            "agent_selected": decision.agent_selected,
            "model_tier": decision.model_tier,
            "complexity_score": decision.complexity_score,
            "routing_reason": decision.routing_reason,
        },
    )


def get_routing_history(session_id: str) -> List[RoutingDecision]:
    """Retrieve all routing decisions for a session.

    Args:
        session_id: The session to look up.

    Returns:
        A list of :class:`RoutingDecision` instances in the order they were
        logged.  Returns an empty list if the session has no recorded
        decisions.
    """
    records = _routing_log.get(session_id, [])
    decisions = []
    for record in records:
        try:
            decisions.append(RoutingDecision.from_dict(record))
        except (TypeError, ValueError) as exc:
            logger.warning("Skipping malformed routing record: %s — %s", record, exc)
    return decisions


def get_routing_history_raw(session_id: str) -> List[Dict]:
    """Return raw dict records for a session (suitable for JSON responses).

    Args:
        session_id: The session to look up.

    Returns:
        List of plain dicts; empty if the session has no recorded decisions.
    """
    return list(_routing_log.get(session_id, []))


def clear_routing_log(session_id: Optional[str] = None) -> None:
    """Clear routing log entries.

    Args:
        session_id: If given, clears only entries for that session.
            If ``None``, clears the entire log (useful in tests).
    """
    global _routing_log
    if session_id is None:
        _routing_log.clear()
    else:
        _routing_log.pop(session_id, None)
