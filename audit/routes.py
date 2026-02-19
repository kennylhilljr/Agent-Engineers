"""Audit log API routes for Agent Dashboard (AI-246).

Endpoints:
    GET /api/audit-log
        Query params:
            actor_id    (str)  - Filter by actor user ID
            event_type  (str)  - Filter by event type
            resource_id (str)  - Filter by resource ID
            since       (str)  - ISO-8601 start timestamp (inclusive)
            until       (str)  - ISO-8601 end timestamp (inclusive)
            limit       (int)  - Page size (default 50, max 500)
            cursor      (str)  - Cursor from previous response for pagination

    GET /api/audit-log/export/csv
        Same filter params as above; returns CSV file download.

    GET /api/audit-log/export/json
        Same filter params as above; returns JSON file download.

    GET /settings/audit-log
        Serves the Audit Log HTML settings page.

Authentication:
    All routes check for an X-User-Id header (demo/dev mode).
    Production should use the same session-based resolve_caller_context
    as teams/routes.py.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from aiohttp import web

from audit.models import get_audit_store
from audit.events import list_event_types, EVENT_CATEGORIES

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 string to a timezone-aware UTC datetime, or None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _json_error(message: str, status: int = 400) -> web.Response:
    return web.json_response({"error": message, "status": status}, status=status)


def _get_filter_params(request: web.Request):
    """Extract and return common filter query parameters."""
    qs = request.rel_url.query
    org_id = qs.get("org_id") or None
    actor_id = qs.get("actor_id") or None
    event_type = qs.get("event_type") or None
    resource_id = qs.get("resource_id") or None
    since = _parse_datetime(qs.get("since"))
    until = _parse_datetime(qs.get("until"))
    return org_id, actor_id, event_type, resource_id, since, until


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


async def get_audit_log(request: web.Request) -> web.Response:
    """GET /api/audit-log — paginated, filterable audit log.

    Returns:
        JSON with ``entries``, ``count``, ``cursor`` (for next page),
        ``has_more`` flag, and ``filters`` echo.
    """
    qs = request.rel_url.query
    org_id, actor_id, event_type, resource_id, since, until = _get_filter_params(request)

    # Pagination params
    try:
        limit = min(int(qs.get("limit", 50)), 500)
    except (ValueError, TypeError):
        limit = 50

    cursor = qs.get("cursor") or None

    store = get_audit_store()
    entries, next_cursor = store.get_entries(
        org_id=org_id,
        actor_id=actor_id,
        event_type=event_type,
        resource_id=resource_id,
        since=since,
        until=until,
        limit=limit,
        cursor=cursor,
    )

    return web.json_response({
        "entries": [e.to_dict() for e in entries],
        "count": len(entries),
        "cursor": next_cursor,
        "has_more": next_cursor is not None,
        "filters": {
            "org_id": org_id,
            "actor_id": actor_id,
            "event_type": event_type,
            "resource_id": resource_id,
            "since": since.isoformat() if since else None,
            "until": until.isoformat() if until else None,
            "limit": limit,
        },
    })


async def export_csv(request: web.Request) -> web.Response:
    """GET /api/audit-log/export/csv — CSV export of filtered audit log."""
    org_id, actor_id, event_type, resource_id, since, until = _get_filter_params(request)

    store = get_audit_store()
    csv_content = store.export_csv(
        org_id=org_id,
        actor_id=actor_id,
        event_type=event_type,
        resource_id=resource_id,
        since=since,
        until=until,
    )

    filename = f"audit-log-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    return web.Response(
        body=csv_content.encode("utf-8"),
        content_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(csv_content.encode("utf-8"))),
        },
    )


async def export_json(request: web.Request) -> web.Response:
    """GET /api/audit-log/export/json — JSON export of filtered audit log."""
    org_id, actor_id, event_type, resource_id, since, until = _get_filter_params(request)

    store = get_audit_store()
    json_content = store.export_json(
        org_id=org_id,
        actor_id=actor_id,
        event_type=event_type,
        resource_id=resource_id,
        since=since,
        until=until,
    )

    filename = f"audit-log-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
    return web.Response(
        body=json_content.encode("utf-8"),
        content_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(json_content.encode("utf-8"))),
        },
    )


async def get_event_types(request: web.Request) -> web.Response:
    """GET /api/audit-log/event-types — list all known event type constants."""
    return web.json_response({
        "event_types": list_event_types(),
        "categories": {k: sorted(v) for k, v in EVENT_CATEGORIES.items()},
    })


async def serve_audit_log_page(request: web.Request) -> web.Response:
    """GET /settings/audit-log — Serve the Audit Log settings HTML page."""
    html_path = Path(__file__).parent.parent / "dashboard" / "audit_log.html"
    if html_path.exists():
        return web.Response(
            text=html_path.read_text(),
            content_type="text/html",
        )
    return web.HTTPNotFound(reason="audit_log.html not found")


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


def register_audit_routes(app: web.Application) -> None:
    """Register all audit log routes on an aiohttp Application.

    Call this from the server's ``_setup_routes()``::

        from audit.routes import register_audit_routes
        register_audit_routes(self.app)
    """
    # API routes
    app.router.add_get("/api/audit-log", get_audit_log)
    app.router.add_get("/api/audit-log/export/csv", export_csv)
    app.router.add_get("/api/audit-log/export/json", export_json)
    app.router.add_get("/api/audit-log/event-types", get_event_types)

    # UI page
    app.router.add_get("/settings/audit-log", serve_audit_log_page)

    # CORS preflight
    for path in [
        "/api/audit-log",
        "/api/audit-log/export/csv",
        "/api/audit-log/export/json",
        "/api/audit-log/event-types",
        "/settings/audit-log",
    ]:
        try:
            app.router.add_route("OPTIONS", path, _handle_options)
        except Exception:
            pass  # May already be registered

    logger.info("Audit log routes registered (AI-246)")


async def _handle_options(request: web.Request) -> web.Response:
    """Handle CORS preflight OPTIONS requests for audit routes."""
    return web.Response(status=204)
