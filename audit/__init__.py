"""Audit Log module for Agent Dashboard (AI-246).

Provides a comprehensive, immutable audit trail for SOC 2 Type I compliance.

Captures events across:
- Authentication: login/logout, failed attempts, SSO, API keys
- User & Team: member invitations, role changes, project creation
- Agent: session lifecycle, pause/resume, webhooks
- Billing: plan changes, payment events, usage limits

Usage::

    from audit import get_audit_store, record_event
    from audit.events import AUTH_LOGIN

    store = get_audit_store()
    store.record(
        org_id="org_123",
        actor_id="user_456",
        event_type=AUTH_LOGIN,
        resource_id="user_456",
        details={"method": "password"},
    )

API endpoints:
    GET  /api/audit-log                - Paginated, filterable log
    GET  /api/audit-log/export/csv     - CSV export
    GET  /api/audit-log/export/json    - JSON export
"""

from audit.models import AuditEntry, AuditStore, get_audit_store, reset_audit_store
from audit.events import (
    # Auth
    AUTH_LOGIN, AUTH_LOGOUT, AUTH_LOGIN_FAILED, AUTH_SSO_CONFIG_CHANGED,
    AUTH_API_KEY_CREATED, AUTH_API_KEY_REVOKED,
    # Team
    TEAM_MEMBER_INVITED, TEAM_MEMBER_REMOVED, TEAM_ROLE_CHANGED,
    TEAM_PROJECT_CREATED, TEAM_PROJECT_DELETED,
    TEAM_INTEGRATION_CONNECTED, TEAM_INTEGRATION_DISCONNECTED,
    # Agent
    AGENT_SESSION_STARTED, AGENT_SESSION_COMPLETED, AGENT_SESSION_FAILED,
    AGENT_PAUSED, AGENT_RESUMED,
    AGENT_WEBHOOK_CREATED, AGENT_WEBHOOK_TRIGGERED,
    # Billing
    BILLING_PLAN_UPGRADED, BILLING_PLAN_DOWNGRADED,
    BILLING_PAYMENT_SUCCEEDED, BILLING_PAYMENT_FAILED,
    BILLING_USAGE_LIMIT_REACHED,
)

__all__ = [
    # Store
    "AuditEntry",
    "AuditStore",
    "get_audit_store",
    "reset_audit_store",
    # Auth events
    "AUTH_LOGIN",
    "AUTH_LOGOUT",
    "AUTH_LOGIN_FAILED",
    "AUTH_SSO_CONFIG_CHANGED",
    "AUTH_API_KEY_CREATED",
    "AUTH_API_KEY_REVOKED",
    # Team events
    "TEAM_MEMBER_INVITED",
    "TEAM_MEMBER_REMOVED",
    "TEAM_ROLE_CHANGED",
    "TEAM_PROJECT_CREATED",
    "TEAM_PROJECT_DELETED",
    "TEAM_INTEGRATION_CONNECTED",
    "TEAM_INTEGRATION_DISCONNECTED",
    # Agent events
    "AGENT_SESSION_STARTED",
    "AGENT_SESSION_COMPLETED",
    "AGENT_SESSION_FAILED",
    "AGENT_PAUSED",
    "AGENT_RESUMED",
    "AGENT_WEBHOOK_CREATED",
    "AGENT_WEBHOOK_TRIGGERED",
    # Billing events
    "BILLING_PLAN_UPGRADED",
    "BILLING_PLAN_DOWNGRADED",
    "BILLING_PAYMENT_SUCCEEDED",
    "BILLING_PAYMENT_FAILED",
    "BILLING_USAGE_LIMIT_REACHED",
]
