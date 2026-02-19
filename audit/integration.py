"""Audit integration helpers for emitting events from other modules (AI-246).

This module provides thin helper functions so that auth, billing, agent, and
team modules can emit audit events without importing the full audit machinery.

Usage in teams/routes.py::

    from audit.integration import record_team_event
    from audit.events import TEAM_MEMBER_INVITED

    record_team_event(
        org_id=org_id,
        actor_id=actor_user_id,
        event_type=TEAM_MEMBER_INVITED,
        resource_id=invite.invite_id,
        details={"email": email, "role": role},
    )

Usage in billing/webhook_handler.py::

    from audit.integration import record_billing_event
    from audit.events import BILLING_PAYMENT_SUCCEEDED

    record_billing_event(
        org_id=subscription.org_id,
        actor_id="stripe_webhook",
        event_type=BILLING_PAYMENT_SUCCEEDED,
        resource_id=payment_intent_id,
        details={"amount_usd": amount / 100, "currency": currency},
    )
"""

import logging
from typing import Any, Dict, Optional

from audit.models import AuditEntry, get_audit_store
from audit.events import (
    AUTH_EVENTS,
    TEAM_EVENTS,
    AGENT_EVENTS,
    BILLING_EVENTS,
    get_event_category,
)

logger = logging.getLogger(__name__)

# Sentinel actor_id used for system-generated events (no human actor)
SYSTEM_ACTOR = "system"


# ---------------------------------------------------------------------------
# Generic record helper
# ---------------------------------------------------------------------------


def record_audit_event(
    org_id: str,
    actor_id: str,
    event_type: str,
    resource_id: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> Optional[AuditEntry]:
    """Emit a single audit event to the global AuditStore.

    Failures are caught and logged rather than propagated so that audit
    instrumentation never breaks normal application flow.

    Args:
        org_id:      Organisation that owns this event.
        actor_id:    User (or system actor) that triggered the event.
        event_type:  One of the ``audit.events.*`` constants.
        resource_id: Optional ID of the affected resource.
        details:     Arbitrary JSON-serialisable metadata.

    Returns:
        The created AuditEntry, or None if recording failed.
    """
    try:
        store = get_audit_store()
        entry = store.record(
            org_id=org_id,
            actor_id=actor_id,
            event_type=event_type,
            resource_id=resource_id,
            details=details or {},
        )
        logger.debug(
            "Audit event recorded: org=%s actor=%s type=%s resource=%s",
            org_id, actor_id, event_type, resource_id,
        )
        return entry
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to record audit event: org=%s actor=%s type=%s",
            org_id, actor_id, event_type,
        )
        return None


# ---------------------------------------------------------------------------
# Category-specific helpers (thin wrappers that document intent)
# ---------------------------------------------------------------------------


def record_auth_event(
    org_id: str,
    actor_id: str,
    event_type: str,
    resource_id: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> Optional[AuditEntry]:
    """Emit an authentication audit event (AUTH_* constants)."""
    return record_audit_event(
        org_id=org_id,
        actor_id=actor_id,
        event_type=event_type,
        resource_id=resource_id,
        details=details,
    )


def record_team_event(
    org_id: str,
    actor_id: str,
    event_type: str,
    resource_id: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> Optional[AuditEntry]:
    """Emit a team/user management audit event (TEAM_* constants)."""
    return record_audit_event(
        org_id=org_id,
        actor_id=actor_id,
        event_type=event_type,
        resource_id=resource_id,
        details=details,
    )


def record_agent_event(
    org_id: str,
    actor_id: str,
    event_type: str,
    resource_id: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> Optional[AuditEntry]:
    """Emit an agent lifecycle audit event (AGENT_* constants)."""
    return record_audit_event(
        org_id=org_id,
        actor_id=actor_id,
        event_type=event_type,
        resource_id=resource_id,
        details=details,
    )


def record_billing_event(
    org_id: str,
    actor_id: str,
    event_type: str,
    resource_id: str = "",
    details: Optional[Dict[str, Any]] = None,
) -> Optional[AuditEntry]:
    """Emit a billing audit event (BILLING_* constants)."""
    return record_audit_event(
        org_id=org_id,
        actor_id=actor_id,
        event_type=event_type,
        resource_id=resource_id,
        details=details,
    )


# ---------------------------------------------------------------------------
# Bridge: teams.models.AuditLog → audit.AuditStore
# ---------------------------------------------------------------------------


def bridge_teams_audit_event(
    org_id: str,
    actor_user_id: str,
    event_type: str,
    details: Optional[Dict[str, Any]] = None,
    target_user_id: Optional[str] = None,
) -> Optional[AuditEntry]:
    """Bridge an event from the teams.models.AuditLog API to the new AuditStore.

    This function has the same signature as ``teams.models.AuditLog.record()``
    so that teams/routes.py can import this and call it in place of the old
    local audit log, while still populating the canonical AuditStore.

    The ``target_user_id`` is forwarded into ``details`` under the key
    ``"target_user_id"`` for backwards compatibility.
    """
    merged_details: Dict[str, Any] = dict(details or {})
    if target_user_id:
        merged_details.setdefault("target_user_id", target_user_id)

    # Map legacy team event_type strings to the canonical TEAM_* constants
    legacy_map = {
        "member_invited": "team.member_invited",
        "invite_accepted": "team.member_invited",  # no canonical "accepted" event
        "role_changed": "team.role_changed",
        "member_removed": "team.member_removed",
        "project_role_set": "team.role_changed",
    }
    canonical_type = legacy_map.get(event_type, event_type)

    resource_id = target_user_id or ""

    return record_audit_event(
        org_id=org_id,
        actor_id=actor_user_id,
        event_type=canonical_type,
        resource_id=resource_id,
        details=merged_details,
    )
