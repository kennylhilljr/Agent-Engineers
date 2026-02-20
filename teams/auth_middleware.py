"""Authentication middleware for Team Management routes (AI-245).

Provides server-side authentication context extraction, replacing the insecure
pattern of trusting client-supplied X-User-Role and X-Org-Id headers.

Security model:
    - In production (TEAM_DEMO_MODE not set): user_id is derived from the
      session cookie (signed HMAC token from dashboard/auth/session_manager.py).
      The role and org_id are then looked up server-side from TeamStore.
    - In demo/dev mode (TEAM_DEMO_MODE=1): X-User-Id header is accepted for
      convenience. X-User-Role and X-Org-Id are STILL derived server-side from
      TeamStore — they are never trusted from the client.

TEAM_DEMO_MODE must be explicitly set to enable demo header-based auth.
Default: off (secure).
"""

import logging
import os
from typing import Dict, Optional

from aiohttp import web

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Demo mode flag (must be explicitly enabled)
# ---------------------------------------------------------------------------

_DEMO_MODE: Optional[bool] = None


def is_demo_mode() -> bool:
    """Return True only if TEAM_DEMO_MODE env var is explicitly set to '1'."""
    global _DEMO_MODE
    if _DEMO_MODE is None:
        _DEMO_MODE = os.environ.get("TEAM_DEMO_MODE", "").strip() == "1"
        if _DEMO_MODE:
            logger.warning(
                "TEAM_DEMO_MODE=1 is active. "
                "Header-based user_id is accepted. "
                "DO NOT use in production."
            )
    return _DEMO_MODE


# ---------------------------------------------------------------------------
# Session cookie helper
# ---------------------------------------------------------------------------

_SESSION_COOKIE_NAME = "session"


def _get_session_token(request: web.Request) -> Optional[str]:
    """Extract the session token from the request cookie."""
    return request.cookies.get(_SESSION_COOKIE_NAME)


def _resolve_user_id_from_session(request: web.Request) -> Optional[str]:
    """Resolve user_id from the session cookie using SessionManager.

    Returns None if no valid session exists.
    """
    token = _get_session_token(request)
    if not token:
        return None

    try:
        # Import here to avoid circular imports / optional dependency
        from dashboard.auth.session_manager import SessionManager
        sm = SessionManager()
        return sm.validate_session(token)
    except Exception as exc:
        logger.debug("Session validation failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Core: resolve caller context securely
# ---------------------------------------------------------------------------


def resolve_caller_context(request: web.Request) -> Dict[str, Optional[str]]:
    """Resolve caller context (user_id, role, org_id) securely.

    Priority for user_id:
      1. request['_team_user_id'] — set by upstream middleware
      2. request['user']['user_id'] — set by auth middleware
      3. Session cookie (server-side validation via SessionManager)
      4. If TEAM_DEMO_MODE=1 only: X-User-Id header (dev/testing convenience)

    Role and org_id are ALWAYS derived server-side from TeamStore using the
    resolved user_id. The X-User-Role and X-Org-Id headers are NEVER used
    as authoritative sources.

    If the user supplies X-Org-Id, it is compared against the org they actually
    belong to for additional validation (cross-org access guard).

    Returns:
        Dict with keys: user_id, role, org_id (any may be None if unresolved)
    """
    # --- Step 1: Resolve user_id from a trusted source ---
    user_id: Optional[str] = None

    # Check middleware-set context first (highest trust)
    user_id = request.get("_team_user_id")
    if not user_id:
        user = request.get("user")
        if isinstance(user, dict):
            user_id = user.get("user_id") or user.get("id")

    # Try session cookie
    if not user_id:
        user_id = _resolve_user_id_from_session(request)

    # Demo mode: accept X-User-Id header ONLY when explicitly enabled
    if not user_id and is_demo_mode():
        user_id = request.headers.get("X-User-Id")
        if user_id:
            logger.debug("DEMO MODE: accepted user_id from X-User-Id header: %s", user_id)

    if not user_id:
        return {"user_id": None, "role": None, "org_id": None}

    # --- Step 2: Look up role and org_id from TeamStore (server-side) ---
    role: Optional[str] = None
    org_id: Optional[str] = None

    try:
        from teams.models import get_team_store
        store = get_team_store()

        # Find the member's org membership — iterate all orgs for this user
        # In a production system, user->org mapping would be indexed.
        member = _find_member_by_user_id(store, user_id)
        if member:
            role = member.role
            org_id = member.org_id

            # Cross-org validation: if client supplied X-Org-Id, verify it matches
            client_org_id = request.headers.get("X-Org-Id")
            if client_org_id and client_org_id != org_id:
                logger.warning(
                    "Cross-org access attempt: user=%s claims org=%s but belongs to org=%s",
                    user_id, client_org_id, org_id,
                )
                # Reject: the user doesn't belong to the claimed org
                return {"user_id": user_id, "role": None, "org_id": None}

    except Exception as exc:
        logger.error("Failed to look up member context for user_id=%s: %s", user_id, exc)

    return {"user_id": user_id, "role": role, "org_id": org_id}


def _find_member_by_user_id(store, user_id: str):
    """Search all orgs in the store for a member with the given user_id.

    Returns the first active TeamMember found, or None.

    Note: In production this should be backed by an indexed DB query.
    """
    # TeamStore._members is a dict: org_id -> {user_id -> TeamMember}
    for org_members in store._members.values():
        member = org_members.get(user_id)
        if member and member.is_active:
            return member
    return None
