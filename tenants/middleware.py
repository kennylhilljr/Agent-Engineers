"""Tenant-aware aiohttp middleware.

Extracts tenant identity from incoming requests and injects a TenantContext
into ``request['tenant']`` for downstream handlers.

Tenant resolution order:
    1. ``X-Tenant-Id`` header (explicit API calls)
    2. Session-stored ``tenant_id`` (browser dashboard)
    3. User's default tenant from user store

Platform admin routes (``/platform/*``) bypass tenant requirement but still
populate context with ``is_platform_admin=True``.
"""

import logging
import os
from typing import Set

from aiohttp import web

from tenants.models import TenantContext, TenantNotFoundError, TenantSuspendedError
from tenants.store import get_tenant_store

logger = logging.getLogger(__name__)

# Routes that do not require tenant context
TENANT_EXEMPT_PATHS: Set[str] = {
    "/health",
    "/ready",
    "/auth/login",
    "/auth/register",
    "/auth/oauth/callback",
    "/api/auth/login",
    "/api/auth/register",
}

# Platform admin emails (comma-separated env var)
PLATFORM_ADMIN_EMAILS: Set[str] = set(
    e.strip()
    for e in os.environ.get("PLATFORM_ADMIN_EMAILS", "").split(",")
    if e.strip()
)


@web.middleware
async def tenant_middleware(request: web.Request, handler):
    """Resolve tenant context for each request.

    Injects ``request['tenant']`` as a :class:`TenantContext` instance.
    Returns 403 for suspended tenants and 400 for missing tenant on
    non-exempt paths.
    """
    path = request.path

    # Skip tenant resolution for health checks and auth endpoints
    if path in TENANT_EXEMPT_PATHS or path.startswith("/auth/"):
        return await handler(request)

    # Determine if this is a platform admin request
    is_platform_route = path.startswith("/platform/") or path.startswith("/api/platform/")

    # Extract user info from session/auth (set by auth middleware)
    user_id = request.get("user_id", "")
    user_email = request.get("user_email", "")
    user_role = request.get("user_role", "")
    is_platform_admin = user_email in PLATFORM_ADMIN_EMAILS

    # Platform admin routes: require admin status, tenant context optional
    if is_platform_route:
        if not is_platform_admin:
            return web.json_response(
                {"error": "Platform admin access required"},
                status=403,
            )
        # Platform admins get a context without a specific tenant
        request["tenant"] = TenantContext(
            tenant_id="",
            tenant_config=None,  # type: ignore[arg-type]
            user_id=user_id,
            org_id="",
            role="platform_admin",
            is_platform_admin=True,
        )
        return await handler(request)

    # Resolve tenant ID
    tenant_id = (
        request.headers.get("X-Tenant-Id", "")
        or request.get("session_tenant_id", "")
        or request.get("default_tenant_id", "")
    )

    if not tenant_id:
        # For WebSocket and non-critical paths, allow through without tenant
        if path.startswith("/ws") or path == "/api/providers":
            return await handler(request)
        return web.json_response(
            {"error": "Tenant context required. Provide X-Tenant-Id header."},
            status=400,
        )

    # Load tenant config
    try:
        store = get_tenant_store()
        config = store.get_tenant(tenant_id)
    except TenantNotFoundError:
        return web.json_response(
            {"error": f"Tenant not found: {tenant_id}"},
            status=404,
        )

    # Reject suspended tenants
    if not config.is_active():
        return web.json_response(
            {"error": f"Tenant is {config.status}. Contact platform administrator."},
            status=403,
        )

    # Inject tenant context
    request["tenant"] = TenantContext(
        tenant_id=tenant_id,
        tenant_config=config,
        user_id=user_id,
        org_id=request.get("org_id", ""),
        role=user_role,
        is_platform_admin=is_platform_admin,
    )

    return await handler(request)
