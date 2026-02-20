"""Audit event type constants for Agent Dashboard (AI-246).

All event type strings are defined here as module-level constants to avoid
typos and to provide a single source of truth for event types.

Categories:
    AUTH_*    - Authentication events
    TEAM_*    - User and team management events
    AGENT_*   - Agent lifecycle events
    BILLING_* - Billing and subscription events
"""

from typing import Dict, List, Set

# ---------------------------------------------------------------------------
# Authentication Events
# ---------------------------------------------------------------------------

AUTH_LOGIN = "auth.login"
AUTH_LOGOUT = "auth.logout"
AUTH_LOGIN_FAILED = "auth.login_failed"
AUTH_SSO_CONFIG_CHANGED = "auth.sso_config_changed"
AUTH_API_KEY_CREATED = "auth.api_key_created"
AUTH_API_KEY_REVOKED = "auth.api_key_revoked"

# ---------------------------------------------------------------------------
# Team / User Events
# ---------------------------------------------------------------------------

TEAM_MEMBER_INVITED = "team.member_invited"
TEAM_MEMBER_REMOVED = "team.member_removed"
TEAM_ROLE_CHANGED = "team.role_changed"
TEAM_PROJECT_CREATED = "team.project_created"
TEAM_PROJECT_DELETED = "team.project_deleted"
TEAM_INTEGRATION_CONNECTED = "team.integration_connected"
TEAM_INTEGRATION_DISCONNECTED = "team.integration_disconnected"

# ---------------------------------------------------------------------------
# Agent Events
# ---------------------------------------------------------------------------

AGENT_SESSION_STARTED = "agent.session_started"
AGENT_SESSION_COMPLETED = "agent.session_completed"
AGENT_SESSION_FAILED = "agent.session_failed"
AGENT_PAUSED = "agent.paused"
AGENT_RESUMED = "agent.resumed"
AGENT_WEBHOOK_CREATED = "agent.webhook_created"
AGENT_WEBHOOK_TRIGGERED = "agent.webhook_triggered"

# ---------------------------------------------------------------------------
# Billing Events
# ---------------------------------------------------------------------------

BILLING_PLAN_UPGRADED = "billing.plan_upgraded"
BILLING_PLAN_DOWNGRADED = "billing.plan_downgraded"
BILLING_PAYMENT_SUCCEEDED = "billing.payment_succeeded"
BILLING_PAYMENT_FAILED = "billing.payment_failed"
BILLING_USAGE_LIMIT_REACHED = "billing.usage_limit_reached"

# ---------------------------------------------------------------------------
# Grouped sets for validation / filtering
# ---------------------------------------------------------------------------

AUTH_EVENTS: Set[str] = {
    AUTH_LOGIN,
    AUTH_LOGOUT,
    AUTH_LOGIN_FAILED,
    AUTH_SSO_CONFIG_CHANGED,
    AUTH_API_KEY_CREATED,
    AUTH_API_KEY_REVOKED,
}

TEAM_EVENTS: Set[str] = {
    TEAM_MEMBER_INVITED,
    TEAM_MEMBER_REMOVED,
    TEAM_ROLE_CHANGED,
    TEAM_PROJECT_CREATED,
    TEAM_PROJECT_DELETED,
    TEAM_INTEGRATION_CONNECTED,
    TEAM_INTEGRATION_DISCONNECTED,
}

AGENT_EVENTS: Set[str] = {
    AGENT_SESSION_STARTED,
    AGENT_SESSION_COMPLETED,
    AGENT_SESSION_FAILED,
    AGENT_PAUSED,
    AGENT_RESUMED,
    AGENT_WEBHOOK_CREATED,
    AGENT_WEBHOOK_TRIGGERED,
}

BILLING_EVENTS: Set[str] = {
    BILLING_PLAN_UPGRADED,
    BILLING_PLAN_DOWNGRADED,
    BILLING_PAYMENT_SUCCEEDED,
    BILLING_PAYMENT_FAILED,
    BILLING_USAGE_LIMIT_REACHED,
}

ALL_EVENT_TYPES: Set[str] = AUTH_EVENTS | TEAM_EVENTS | AGENT_EVENTS | BILLING_EVENTS

EVENT_CATEGORIES: Dict[str, Set[str]] = {
    "auth": AUTH_EVENTS,
    "team": TEAM_EVENTS,
    "agent": AGENT_EVENTS,
    "billing": BILLING_EVENTS,
}

# Human-readable descriptions
EVENT_DESCRIPTIONS: Dict[str, str] = {
    # Auth
    AUTH_LOGIN: "User logged in",
    AUTH_LOGOUT: "User logged out",
    AUTH_LOGIN_FAILED: "Failed login attempt",
    AUTH_SSO_CONFIG_CHANGED: "SSO configuration changed",
    AUTH_API_KEY_CREATED: "API key created",
    AUTH_API_KEY_REVOKED: "API key revoked",
    # Team
    TEAM_MEMBER_INVITED: "Team member invited",
    TEAM_MEMBER_REMOVED: "Team member removed",
    TEAM_ROLE_CHANGED: "Member role changed",
    TEAM_PROJECT_CREATED: "Project created",
    TEAM_PROJECT_DELETED: "Project deleted",
    TEAM_INTEGRATION_CONNECTED: "Integration connected",
    TEAM_INTEGRATION_DISCONNECTED: "Integration disconnected",
    # Agent
    AGENT_SESSION_STARTED: "Agent session started",
    AGENT_SESSION_COMPLETED: "Agent session completed",
    AGENT_SESSION_FAILED: "Agent session failed",
    AGENT_PAUSED: "Agent paused",
    AGENT_RESUMED: "Agent resumed",
    AGENT_WEBHOOK_CREATED: "Webhook created",
    AGENT_WEBHOOK_TRIGGERED: "Webhook triggered",
    # Billing
    BILLING_PLAN_UPGRADED: "Plan upgraded",
    BILLING_PLAN_DOWNGRADED: "Plan downgraded",
    BILLING_PAYMENT_SUCCEEDED: "Payment succeeded",
    BILLING_PAYMENT_FAILED: "Payment failed",
    BILLING_USAGE_LIMIT_REACHED: "Usage limit reached",
}


def get_event_description(event_type: str) -> str:
    """Return a human-readable description for an event type."""
    return EVENT_DESCRIPTIONS.get(event_type, event_type)


def get_event_category(event_type: str) -> str:
    """Return the category name for an event type (auth/team/agent/billing)."""
    for category, events in EVENT_CATEGORIES.items():
        if event_type in events:
            return category
    return "unknown"


def is_valid_event_type(event_type: str) -> bool:
    """Return True if event_type is one of the known event type constants."""
    return event_type in ALL_EVENT_TYPES


def list_event_types() -> List[str]:
    """Return all known event type strings sorted alphabetically."""
    return sorted(ALL_EVENT_TYPES)
