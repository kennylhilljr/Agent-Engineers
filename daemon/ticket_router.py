"""
Ticket Router
=============

Routes tickets to the appropriate worker pool and selects the model
based on ticket complexity, labels, and configurable routing rules.

Used by daemon_v2 to determine which pool handles a ticket and which
Claude model to use for the session.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from daemon.worker_pool import (
    AVAILABLE_MODELS,
    PoolType,
    Ticket,
    TicketComplexity,
    WorkerPool,
)

logger = logging.getLogger("ticket_router")


# ---------------------------------------------------------------------------
# Routing Rule
# ---------------------------------------------------------------------------


@dataclass
class RoutingRule:
    """A single routing rule that maps ticket attributes to pool + model."""

    match: dict[str, Any]
    pool: PoolType
    model: str  # model name (haiku, sonnet, opus)

    def matches(self, ticket: Ticket) -> bool:
        """Check if this rule matches the given ticket."""
        for key, expected in self.match.items():
            if key == "labels":
                # Match if any expected label is in the ticket's labels
                expected_labels = expected if isinstance(expected, list) else [expected]
                if not any(lbl in ticket.labels for lbl in expected_labels):
                    return False
            elif key == "complexity":
                if ticket.complexity.value != expected:
                    return False
            elif key == "priority":
                if ticket.priority != expected:
                    return False
            elif key == "title_pattern":
                if not re.search(expected, ticket.title, re.IGNORECASE):
                    return False
            elif key == "status":
                if ticket.status != expected:
                    return False
            else:
                logger.debug("Unknown match key '%s' in routing rule", key)
                return False
        return True

    @staticmethod
    def from_dict(data: dict) -> RoutingRule:
        """Create a RoutingRule from a dictionary."""
        match = data.get("match", {})
        pool_name = data.get("pool", "coding")
        model = data.get("model", "sonnet")

        try:
            pool = PoolType(pool_name)
        except ValueError:
            logger.warning("Unknown pool '%s' in routing rule, defaulting to coding", pool_name)
            pool = PoolType.CODING

        return RoutingRule(match=match, pool=pool, model=model)


# ---------------------------------------------------------------------------
# Complexity estimation
# ---------------------------------------------------------------------------

# Keywords that suggest higher or lower complexity
_HIGH_COMPLEXITY_KEYWORDS = [
    "refactor",
    "redesign",
    "migrate",
    "architecture",
    "performance",
    "security",
    "database",
    "auth",
    "authentication",
    "integration",
    "real-time",
    "websocket",
    "infrastructure",
]

_LOW_COMPLEXITY_KEYWORDS = [
    "typo",
    "rename",
    "label",
    "color",
    "text",
    "copy",
    "readme",
    "comment",
    "lint",
    "format",
    "style",
    "docs",
    "documentation",
]


def estimate_complexity(ticket: Ticket) -> TicketComplexity:
    """Estimate ticket complexity from title and description keywords.

    This is a heuristic — the routing rules can override it.
    """
    if ticket.complexity != TicketComplexity.MEDIUM:
        # Already explicitly set
        return ticket.complexity

    text = f"{ticket.title} {ticket.description}".lower()

    for kw in _HIGH_COMPLEXITY_KEYWORDS:
        if kw in text:
            return TicketComplexity.HIGH

    for kw in _LOW_COMPLEXITY_KEYWORDS:
        if kw in text:
            return TicketComplexity.LOW

    return TicketComplexity.MEDIUM


# ---------------------------------------------------------------------------
# Model selection based on complexity
# ---------------------------------------------------------------------------

_COMPLEXITY_MODEL_MAP: dict[TicketComplexity, str] = {
    TicketComplexity.LOW: "haiku",
    TicketComplexity.MEDIUM: "sonnet",
    TicketComplexity.HIGH: "opus",
}


def select_model_for_complexity(complexity: TicketComplexity) -> str:
    """Return the model name appropriate for the given complexity."""
    return _COMPLEXITY_MODEL_MAP.get(complexity, "sonnet")


# ---------------------------------------------------------------------------
# Ticket Router
# ---------------------------------------------------------------------------


class TicketRouter:
    """Routes tickets to pools and selects models based on rules and heuristics."""

    def __init__(self, rules: list[RoutingRule] | None = None) -> None:
        self.rules: list[RoutingRule] = rules or []

    @classmethod
    def from_rule_dicts(cls, rule_dicts: list[dict]) -> TicketRouter:
        """Create a TicketRouter from a list of rule dictionaries."""
        rules = [RoutingRule.from_dict(d) for d in rule_dicts]
        return cls(rules=rules)

    def route(self, ticket: Ticket) -> PoolType:
        """Determine which pool should handle this ticket.

        Checks rules in order; first match wins. Falls back to CODING pool.
        """
        for rule in self.rules:
            if rule.matches(ticket):
                return rule.pool
        return PoolType.CODING

    def route_and_select(
        self,
        ticket: Ticket,
        pools: dict[PoolType, WorkerPool],
    ) -> tuple[PoolType, str]:
        """Route the ticket and select the model to use.

        Returns:
            A tuple of (pool_type, model_id) where model_id is the full
            Claude model identifier string.
        """
        # Check explicit rules first
        for rule in self.rules:
            if rule.matches(ticket):
                model_id = AVAILABLE_MODELS.get(rule.model, AVAILABLE_MODELS["sonnet"])
                return rule.pool, model_id

        # Fall back to complexity-based routing
        complexity = estimate_complexity(ticket)
        model_name = select_model_for_complexity(complexity)
        model_id = AVAILABLE_MODELS.get(model_name, AVAILABLE_MODELS["sonnet"])

        # Determine pool from complexity + labels
        pool_type = self._infer_pool(ticket)

        # Use pool's default model if available and no rule matched
        pool = pools.get(pool_type)
        if pool is not None and pool.config.default_model:
            pool_model = AVAILABLE_MODELS.get(pool.config.default_model)
            if pool_model:
                model_id = pool_model

        return pool_type, model_id

    def _infer_pool(self, ticket: Ticket) -> PoolType:
        """Infer pool type from ticket labels when no rule matches."""
        labels_lower = [lab.lower() for lab in ticket.labels]

        if any(lab in labels_lower for lab in ("review", "pr", "code-review")):
            return PoolType.REVIEW
        if any(lab in labels_lower for lab in ("linear", "triage", "planning")):
            return PoolType.LINEAR

        return PoolType.CODING
