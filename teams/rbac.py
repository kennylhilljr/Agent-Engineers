"""RBAC middleware and permission decorators for team management.

AI-245: Role-Based Access Control

Provides:
    - ROLE_HIERARCHY: numeric levels (viewer=10 < member=20 < admin=80 < owner=100)
    - ROLE_PERMISSIONS: per-role permission set
    - Permission enum: granular capability flags
    - require_role / require_permission: aiohttp request decorators
    - check_permission / can_manage_role: utility functions for route handlers
"""

import functools
import logging
from enum import Enum
from typing import Any, Callable, Optional, Set

from aiohttp import web

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Role hierarchy (numeric level for comparison)
# ---------------------------------------------------------------------------

ROLE_HIERARCHY: dict = {
    "viewer": 10,
    "member": 20,
    "admin": 80,
    "owner": 100,
}

VALID_ROLES: Set[str] = set(ROLE_HIERARCHY.keys())


# ---------------------------------------------------------------------------
# Permission enum
# ---------------------------------------------------------------------------


class Permission(str, Enum):
    """Granular capability flags."""

    # Read-only
    VIEW_DASHBOARD = "view_dashboard"
    VIEW_REPORTS = "view_reports"
    VIEW_MEMBERS = "view_members"

    # Agent operations
    RUN_AGENTS = "run_agents"
    VIEW_AGENTS = "view_agents"

    # Project operations
    CREATE_PROJECT = "create_project"
    EDIT_PROJECT = "edit_project"
    DELETE_PROJECT = "delete_project"

    # Member management
    INVITE_MEMBERS = "invite_members"
    REMOVE_MEMBERS = "remove_members"
    CHANGE_ROLES = "change_roles"

    # Integrations
    MANAGE_INTEGRATIONS = "manage_integrations"

    # Org-level
    MANAGE_BILLING = "manage_billing"
    DELETE_ORG = "delete_org"
    TRANSFER_OWNERSHIP = "transfer_ownership"


# ---------------------------------------------------------------------------
# Per-role permission sets
# ---------------------------------------------------------------------------

ROLE_PERMISSIONS: dict = {
    "viewer": {
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_REPORTS,
        Permission.VIEW_MEMBERS,
        Permission.VIEW_AGENTS,
    },
    "member": {
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_REPORTS,
        Permission.VIEW_MEMBERS,
        Permission.VIEW_AGENTS,
        Permission.RUN_AGENTS,
        Permission.CREATE_PROJECT,
        Permission.EDIT_PROJECT,
    },
    "admin": {
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_REPORTS,
        Permission.VIEW_MEMBERS,
        Permission.VIEW_AGENTS,
        Permission.RUN_AGENTS,
        Permission.CREATE_PROJECT,
        Permission.EDIT_PROJECT,
        Permission.DELETE_PROJECT,
        Permission.INVITE_MEMBERS,
        Permission.REMOVE_MEMBERS,
        Permission.CHANGE_ROLES,
        Permission.MANAGE_INTEGRATIONS,
    },
    "owner": {
        Permission.VIEW_DASHBOARD,
        Permission.VIEW_REPORTS,
        Permission.VIEW_MEMBERS,
        Permission.VIEW_AGENTS,
        Permission.RUN_AGENTS,
        Permission.CREATE_PROJECT,
        Permission.EDIT_PROJECT,
        Permission.DELETE_PROJECT,
        Permission.INVITE_MEMBERS,
        Permission.REMOVE_MEMBERS,
        Permission.CHANGE_ROLES,
        Permission.MANAGE_INTEGRATIONS,
        Permission.MANAGE_BILLING,
        Permission.DELETE_ORG,
        Permission.TRANSFER_OWNERSHIP,
    },
}


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def check_permission(role: str, permission: Permission) -> bool:
    """Return True if the given role has the specified permission.

    Args:
        role:       Role name string (viewer/member/admin/owner).
        permission: Permission flag to check.

    Returns:
        bool
    """
    perms = ROLE_PERMISSIONS.get(role, set())
    return permission in perms


def can_manage_role(actor_role: str, target_role: str) -> bool:
    """Return True if actor_role can assign/change to target_role.

    Rules enforced here:
    - Owner can set any role (including owner).
    - Admin can set member and viewer, but NOT owner or admin.
    - Member and Viewer cannot manage roles at all.

    Args:
        actor_role:  The role of the person making the change.
        target_role: The role being assigned.

    Returns:
        bool
    """
    actor_level = ROLE_HIERARCHY.get(actor_role, 0)
    target_level = ROLE_HIERARCHY.get(target_role, 0)

    if actor_role == "owner":
        return True

    if actor_role == "admin":
        # Admin cannot promote to owner or admin
        return target_level < ROLE_HIERARCHY["admin"]

    return False


def get_request_role(request: web.Request) -> Optional[str]:
    """Extract the caller's role from the request context.

    Convention: route handlers store ``_team_role`` in ``request`` after
    verifying the session/token, or the RBAC middleware sets it.

    Falls back to checking request['user'] dict if present.

    Returns:
        Role string or None if not authenticated.
    """
    # Primary: set by RBAC decorators
    role = request.get("_team_role")
    if role:
        return role

    # Secondary: generic user dict (set by auth_middleware or session)
    user = request.get("user")
    if isinstance(user, dict):
        return user.get("role")

    return None


def get_request_user_id(request: web.Request) -> Optional[str]:
    """Extract the caller's user_id from the request context."""
    user_id = request.get("_team_user_id")
    if user_id:
        return user_id

    user = request.get("user")
    if isinstance(user, dict):
        return user.get("user_id") or user.get("id")

    return None


def get_request_org_id(request: web.Request) -> Optional[str]:
    """Extract org_id from request (header, query param, or context)."""
    org_id = request.get("_team_org_id")
    if org_id:
        return org_id

    # Check X-Org-Id header
    org_id = request.headers.get("X-Org-Id")
    if org_id:
        return org_id

    # Check query param
    return request.rel_url.query.get("org_id")


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------


def require_role(minimum_role: str):
    """Decorator: require that the caller has at least ``minimum_role``.

    The decorator looks up the caller's role via ``get_request_role(request)``.
    If the role is insufficient it returns a 403 JSON response.

    Usage::

        @require_role("admin")
        async def my_handler(self, request):
            ...

    Args:
        minimum_role: Minimum role string required ("viewer"/"member"/"admin"/"owner").
    """
    min_level = ROLE_HIERARCHY.get(minimum_role, 0)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Support both standalone functions and class methods
            request = None
            for arg in args:
                if isinstance(arg, web.Request):
                    request = arg
                    break

            if request is None:
                logger.warning("require_role: could not find Request in args")
                raise web.HTTPForbidden(
                    reason="Missing request context for RBAC check"
                )

            role = get_request_role(request)
            if not role:
                return web.json_response(
                    {"error": "Authentication required", "status": 401},
                    status=401,
                )

            role_level = ROLE_HIERARCHY.get(role, 0)
            if role_level < min_level:
                return web.json_response(
                    {
                        "error": "Insufficient permissions",
                        "required_role": minimum_role,
                        "your_role": role,
                        "status": 403,
                    },
                    status=403,
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_permission(permission: Permission):
    """Decorator: require the caller has the specified permission.

    Usage::

        @require_permission(Permission.INVITE_MEMBERS)
        async def my_handler(self, request):
            ...

    Args:
        permission: A ``Permission`` enum value.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            request = None
            for arg in args:
                if isinstance(arg, web.Request):
                    request = arg
                    break

            if request is None:
                raise web.HTTPForbidden(
                    reason="Missing request context for RBAC check"
                )

            role = get_request_role(request)
            if not role:
                return web.json_response(
                    {"error": "Authentication required", "status": 401},
                    status=401,
                )

            if not check_permission(role, permission):
                return web.json_response(
                    {
                        "error": "Insufficient permissions",
                        "required_permission": permission.value,
                        "your_role": role,
                        "status": 403,
                    },
                    status=403,
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator
