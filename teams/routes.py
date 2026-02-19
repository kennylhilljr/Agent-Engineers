"""Team management API routes.

AI-245: REST endpoints for team member management, role assignment, and invitations.

Endpoints:
    GET    /api/team/members                       - List team members
    POST   /api/team/invite                        - Send invitation (Owner/Admin)
    PUT    /api/team/members/{user_id}/role        - Update member role
    DELETE /api/team/members/{user_id}             - Remove member
    GET    /api/team/invite/{token}                - Get invite details
    POST   /api/team/invite/{token}/accept         - Accept invitation
    GET    /api/team/audit                         - Audit log (Owner/Admin)
    GET    /api/team/settings                      - Team settings page HTML
    PUT    /api/team/members/{user_id}/project-role - Set per-project role override

Authentication context:
    All routes derive user_id, role, and org_id from the server-side session
    via teams.auth_middleware.resolve_caller_context(). Client-supplied
    X-User-Role and X-Org-Id headers are NEVER used as authoritative sources.

    Demo/dev mode: set TEAM_DEMO_MODE=1 to accept X-User-Id header for the
    user_id (role and org_id are still derived server-side). Default: off.
"""

import logging
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from aiohttp import web

from teams.models import (
    Role,
    TeamError,
    TeamPermissionError,
    InvitationError,
    get_team_store,
    get_audit_log,
)
from teams.rbac import (
    ROLE_HIERARCHY,
    VALID_ROLES,
    Permission,
    check_permission,
    can_manage_role,
)
from teams.auth_middleware import resolve_caller_context

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: extract caller context from request (server-side only)
# ---------------------------------------------------------------------------


def _get_caller_context(request: web.Request) -> Dict[str, Optional[str]]:
    """Extract caller user_id, role, and org_id from the server-side session.

    Role and org_id are ALWAYS derived from TeamStore — never from headers.
    See teams.auth_middleware for the full security model.
    """
    return resolve_caller_context(request)


def _require_context(request: web.Request):
    """Return caller context, raising 401/400 if incomplete."""
    ctx = _get_caller_context(request)

    if not ctx["user_id"]:
        raise web.HTTPUnauthorized(
            reason="Authentication required. No valid session found."
        )
    if not ctx["role"]:
        raise web.HTTPUnauthorized(
            reason="User is not a member of any organization."
        )
    if not ctx["org_id"]:
        raise web.HTTPBadRequest(
            reason="Could not determine organization for authenticated user."
        )

    return ctx


def _json_error(message: str, status: int = 400, **extra) -> web.Response:
    """Return a JSON error response."""
    body: Dict[str, Any] = {"error": message, "status": status}
    body.update(extra)
    return web.json_response(body, status=status)


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


async def list_members(request: web.Request) -> web.Response:
    """GET /api/team/members - List all active members of the org.

    Required role: viewer or above.
    """
    try:
        ctx = _require_context(request)
    except web.HTTPException as exc:
        return _json_error(exc.reason, exc.status_code)

    role = ctx["role"]
    org_id = ctx["org_id"]

    if not check_permission(role, Permission.VIEW_MEMBERS):
        return _json_error("Insufficient permissions to view members", 403)

    store = get_team_store()
    members = store.list_members(org_id)

    return web.json_response({
        "org_id": org_id,
        "members": [m.to_dict() for m in members],
        "count": len(members),
    })


async def invite_member(request: web.Request) -> web.Response:
    """POST /api/team/invite - Create and send an invitation.

    Required role: admin or owner.

    Body (JSON):
        role  (str)  - Role to assign (required)
        email (str)  - Target email (optional; omit for shareable link)
    """
    try:
        ctx = _require_context(request)
    except web.HTTPException as exc:
        return _json_error(exc.reason, exc.status_code)

    role = ctx["role"]
    org_id = ctx["org_id"]
    user_id = ctx["user_id"]

    if not check_permission(role, Permission.INVITE_MEMBERS):
        return _json_error(
            "Only Admin or Owner can invite members", 403,
            your_role=role,
        )

    try:
        body = await request.json()
    except Exception:
        return _json_error("Invalid JSON body", 400)

    invite_role = body.get("role", Role.MEMBER.value)
    email = body.get("email")  # Optional

    if invite_role not in VALID_ROLES:
        return _json_error(
            f"Invalid role '{invite_role}'. Must be one of: {sorted(VALID_ROLES)}",
            400,
        )

    # Enforce: Admin cannot promote to Owner or Admin
    if not can_manage_role(role, invite_role):
        return _json_error(
            f"Role '{role}' cannot invite users with role '{invite_role}'",
            403,
            your_role=role,
            requested_role=invite_role,
        )

    store = get_team_store()
    audit = get_audit_log()

    # MODERATE 1: Rate limit — max 20 invites per org per day
    if not store.check_invite_rate_limit(org_id):
        return _json_error(
            "Invitation rate limit exceeded. Maximum 20 invitations per organization per day.",
            429,
        )

    # Check if email already a member
    if email:
        existing = store.get_member_by_email(org_id, email)
        if existing and existing.is_active:
            return _json_error(
                f"User with email '{email}' is already a member of this org",
                409,
            )

    invite = store.create_invitation(
        org_id=org_id,
        invited_by=user_id,
        role=invite_role,
        email=email,
    )

    # Record the invite timestamp for rate limiting
    store.record_invite_timestamp(org_id)

    # BLOCKER 2: Never store the full token in the audit log
    audit.record(
        org_id=org_id,
        actor_user_id=user_id,
        event_type="member_invited",
        details={
            "invite_id": invite.invite_id,
            "email": email,
            "role": invite_role,
            "token_prefix": invite.token[:8] + "...",
        },
    )

    logger.info(
        "Invitation created: org=%s inviter=%s role=%s email=%s token=%s",
        org_id, user_id, invite_role, email, invite.token[:8] + "...",
    )

    return web.json_response(
        {
            "invite": invite.to_dict(),
            "invite_url": f"/api/team/invite/{invite.token}",
            "message": "Invitation created",
        },
        status=201,
    )


async def get_invite(request: web.Request) -> web.Response:
    """GET /api/team/invite/{token} - Get invitation details (public, no auth required)."""
    token = request.match_info["token"]
    store = get_team_store()
    invite = store.get_invitation(token)

    if not invite:
        return _json_error("Invitation not found", 404)

    if invite.accepted:
        return _json_error("This invitation has already been accepted", 410)

    if invite.is_expired:
        return _json_error("This invitation has expired", 410)

    # Return limited info (no invited_by user_id for privacy)
    return web.json_response({
        "invite_id": invite.invite_id,
        "org_id": invite.org_id,
        "role": invite.role,
        "email": invite.email,
        "expires_at": invite.expires_at,
        "accepted": invite.accepted,
    })


async def accept_invite(request: web.Request) -> web.Response:
    """POST /api/team/invite/{token}/accept - Accept an invitation.

    BLOCKER 3 fix: user_id must come from the server session when available.
    For new users (shareable link flow), email is required in the body and a
    provisional user_id is generated server-side and linked at next login.

    Body (JSON):
        email        (str) - Accepting user's email (required)
        display_name (str) - Accepting user's display name (optional)
    """
    token = request.match_info["token"]

    try:
        body = await request.json()
    except Exception:
        return _json_error("Invalid JSON body", 400)

    email = body.get("email")
    display_name = body.get("display_name", email or "")

    if not email:
        return _json_error("Missing 'email' in body", 400)

    # Try to get user_id from server-side session
    ctx = _get_caller_context(request)
    user_id = ctx.get("user_id")

    if not user_id:
        # Shareable link flow for new/unauthenticated users:
        # Generate a provisional user_id server-side. This must be linked to
        # a real account at next login — client cannot inject their own user_id.
        user_id = f"provisional-{uuid.uuid4().hex}"
        logger.info(
            "Provisional user_id generated for invite acceptance: token=%s email=%s",
            token[:8] + "...", email,
        )

    store = get_team_store()
    audit = get_audit_log()

    try:
        member = store.accept_invitation(
            token=token,
            user_id=user_id,
            email=email,
            display_name=display_name,
        )
    except InvitationError as exc:
        return _json_error(str(exc), 400)

    invite = store.get_invitation(token)
    audit.record(
        org_id=member.org_id,
        actor_user_id=user_id,
        event_type="invite_accepted",
        details={
            "invite_id": invite.invite_id if invite else None,
            "role": member.role,
            "email": email,
        },
    )

    logger.info(
        "Invitation accepted: org=%s user=%s role=%s",
        member.org_id, user_id, member.role,
    )

    return web.json_response(
        {"member": member.to_dict(), "message": "Invitation accepted"},
        status=200,
    )


async def update_member_role(request: web.Request) -> web.Response:
    """PUT /api/team/members/{user_id}/role - Update a member's role.

    Required role: admin (can set member/viewer) or owner (can set any role).

    Body (JSON):
        role (str) - New role to assign
    """
    try:
        ctx = _require_context(request)
    except web.HTTPException as exc:
        return _json_error(exc.reason, exc.status_code)

    actor_role = ctx["role"]
    actor_user_id = ctx["user_id"]
    org_id = ctx["org_id"]
    target_user_id = request.match_info["user_id"]

    if not check_permission(actor_role, Permission.CHANGE_ROLES):
        return _json_error(
            "Insufficient permissions to change roles", 403,
            your_role=actor_role,
        )

    try:
        body = await request.json()
    except Exception:
        return _json_error("Invalid JSON body", 400)

    new_role = body.get("role")
    if not new_role:
        return _json_error("Missing 'role' in body", 400)

    if new_role not in VALID_ROLES:
        return _json_error(
            f"Invalid role '{new_role}'. Must be one of: {sorted(VALID_ROLES)}",
            400,
        )

    # Enforce role hierarchy: Actor cannot promote above their own level
    if not can_manage_role(actor_role, new_role):
        return _json_error(
            f"Role '{actor_role}' cannot assign role '{new_role}'. "
            "Admin cannot promote to Owner.",
            403,
            your_role=actor_role,
            requested_role=new_role,
        )

    store = get_team_store()
    audit = get_audit_log()

    target_member = store.get_member(org_id, target_user_id)
    if not target_member or not target_member.is_active:
        return _json_error(f"Member {target_user_id} not found in org", 404)

    # Owner protection: cannot demote the last owner
    if target_member.role == Role.OWNER.value and new_role != Role.OWNER.value:
        if store.owner_count(org_id) <= 1:
            return _json_error(
                "Cannot demote the last Owner. Transfer ownership first.",
                400,
            )

    old_role = target_member.role

    try:
        member = store.update_role(org_id, target_user_id, new_role)
    except TeamError as exc:
        return _json_error(str(exc), 400)

    audit.record(
        org_id=org_id,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        event_type="role_changed",
        details={
            "old_role": old_role,
            "new_role": new_role,
        },
    )

    logger.info(
        "Role changed: org=%s actor=%s target=%s %s -> %s",
        org_id, actor_user_id, target_user_id, old_role, new_role,
    )

    return web.json_response({
        "member": member.to_dict(),
        "message": f"Role updated from {old_role} to {new_role}",
    })


async def remove_member(request: web.Request) -> web.Response:
    """DELETE /api/team/members/{user_id} - Remove a member from the org.

    Required role: admin (cannot remove owner) or owner.
    """
    try:
        ctx = _require_context(request)
    except web.HTTPException as exc:
        return _json_error(exc.reason, exc.status_code)

    actor_role = ctx["role"]
    actor_user_id = ctx["user_id"]
    org_id = ctx["org_id"]
    target_user_id = request.match_info["user_id"]

    if not check_permission(actor_role, Permission.REMOVE_MEMBERS):
        return _json_error(
            "Insufficient permissions to remove members", 403,
            your_role=actor_role,
        )

    store = get_team_store()
    audit = get_audit_log()

    target_member = store.get_member(org_id, target_user_id)
    if not target_member or not target_member.is_active:
        return _json_error(f"Member {target_user_id} not found in org", 404)

    # Admin cannot remove Owner
    if target_member.role == Role.OWNER.value and actor_role != Role.OWNER.value:
        return _json_error(
            "Only an Owner can remove another Owner from the organization.",
            403,
        )

    # Cannot remove the last owner
    if target_member.role == Role.OWNER.value:
        if store.owner_count(org_id) <= 1:
            return _json_error(
                "Cannot remove the last Owner. Transfer ownership first.",
                400,
            )

    success = store.remove_member(org_id, target_user_id)
    if not success:
        return _json_error("Failed to remove member", 500)

    audit.record(
        org_id=org_id,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        event_type="member_removed",
        details={"removed_role": target_member.role},
    )

    logger.info(
        "Member removed: org=%s actor=%s target=%s",
        org_id, actor_user_id, target_user_id,
    )

    return web.json_response({
        "message": f"Member {target_user_id} removed from org",
        "user_id": target_user_id,
    })


async def get_audit_events(request: web.Request) -> web.Response:
    """GET /api/team/audit - Retrieve audit log events.

    Required role: admin or owner.

    Query params:
        limit      (int, default 100, max 1000)
        event_type (str, optional) - filter by event type
    """
    try:
        ctx = _require_context(request)
    except web.HTTPException as exc:
        return _json_error(exc.reason, exc.status_code)

    role = ctx["role"]
    org_id = ctx["org_id"]

    if not check_permission(role, Permission.MANAGE_INTEGRATIONS):
        return _json_error(
            "Only Admin or Owner can view the audit log", 403,
            your_role=role,
        )

    # MODERATE 2: Cap the limit to prevent unbounded queries
    limit = min(int(request.rel_url.query.get("limit", 100)), 1000)
    event_type = request.rel_url.query.get("event_type")

    audit = get_audit_log()
    events = audit.get_events(org_id=org_id, event_type=event_type, limit=limit)

    return web.json_response({
        "org_id": org_id,
        "events": [e.to_dict() for e in events],
        "count": len(events),
    })


async def update_project_role(request: web.Request) -> web.Response:
    """PUT /api/team/members/{user_id}/project-role - Set per-project role override.

    Required role: admin or owner.

    Body (JSON):
        project_id (str) - Project ID to set override for
        role       (str) - Role to assign for this project
    """
    try:
        ctx = _require_context(request)
    except web.HTTPException as exc:
        return _json_error(exc.reason, exc.status_code)

    actor_role = ctx["role"]
    actor_user_id = ctx["user_id"]
    org_id = ctx["org_id"]
    target_user_id = request.match_info["user_id"]

    if not check_permission(actor_role, Permission.CHANGE_ROLES):
        return _json_error(
            "Insufficient permissions to set project role overrides", 403,
            your_role=actor_role,
        )

    try:
        body = await request.json()
    except Exception:
        return _json_error("Invalid JSON body", 400)

    project_id = body.get("project_id")
    role = body.get("role")

    if not project_id:
        return _json_error("Missing 'project_id' in body", 400)
    if not role:
        return _json_error("Missing 'role' in body", 400)
    if role not in VALID_ROLES:
        return _json_error(
            f"Invalid role '{role}'. Must be one of: {sorted(VALID_ROLES)}",
            400,
        )

    # BLOCKER 5: Enforce role hierarchy for project-role overrides.
    # Admin cannot self-promote to owner via project-role assignment.
    if not can_manage_role(actor_role, role):
        return _json_error(
            f"Role '{actor_role}' cannot assign project role '{role}'. "
            "Admin cannot set project roles above their own level.",
            403,
            your_role=actor_role,
            requested_role=role,
        )

    store = get_team_store()
    audit = get_audit_log()

    try:
        member = store.update_project_role(org_id, target_user_id, project_id, role)
    except TeamError as exc:
        return _json_error(str(exc), 404)

    audit.record(
        org_id=org_id,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        event_type="project_role_set",
        details={"project_id": project_id, "role": role},
    )

    return web.json_response({
        "member": member.to_dict(),
        "message": f"Project role set to '{role}' for project '{project_id}'",
    })


async def serve_team_page(request: web.Request) -> web.Response:
    """GET /settings/team - Serve team management HTML page."""
    html_path = Path(__file__).parent.parent / "dashboard" / "team.html"
    if html_path.exists():
        return web.Response(
            text=html_path.read_text(),
            content_type="text/html",
        )
    return web.HTTPNotFound(reason="team.html not found")


# ---------------------------------------------------------------------------
# Route registration helper
# ---------------------------------------------------------------------------


def register_team_routes(app: web.Application) -> None:
    """Register all team management routes on an aiohttp Application.

    Call this from your server's ``_setup_routes()`` method::

        from teams.routes import register_team_routes
        register_team_routes(self.app)
    """
    # Member management
    app.router.add_get("/api/team/members", list_members)
    app.router.add_post("/api/team/invite", invite_member)
    app.router.add_get("/api/team/invite/{token}", get_invite)
    app.router.add_post("/api/team/invite/{token}/accept", accept_invite)
    app.router.add_put("/api/team/members/{user_id}/role", update_member_role)
    app.router.add_delete("/api/team/members/{user_id}", remove_member)
    app.router.add_put(
        "/api/team/members/{user_id}/project-role", update_project_role
    )

    # Audit log
    app.router.add_get("/api/team/audit", get_audit_events)

    # Settings UI page
    app.router.add_get("/settings/team", serve_team_page)

    # CORS preflight
    for path in [
        "/api/team/members",
        "/api/team/invite",
        "/api/team/audit",
        "/settings/team",
    ]:
        try:
            app.router.add_route("OPTIONS", path, _handle_options)
        except Exception:
            pass  # May already be registered

    logger.info("Team management routes registered (AI-245)")


async def _handle_options(request: web.Request) -> web.Response:
    """Handle CORS preflight OPTIONS requests for team routes."""
    return web.Response(status=204)
