"""REST API routes for spec management.

Provides CRUD endpoints for application specifications with shared memory
recommendation integration. All routes are tenant-scoped via middleware.
"""

import json
import logging
from typing import Optional

from aiohttp import web

from memory.shared_store import get_shared_memory_store
from specs.spec_manager import Spec, SpecError, SpecManager, SpecNotFoundError, SpecStatusError

logger = logging.getLogger(__name__)

# Cache of SpecManager instances per tenant
_spec_managers: dict[str, SpecManager] = {}


def _get_spec_manager(tenant_id: str, data_dir: str) -> SpecManager:
    """Get or create a SpecManager for a tenant."""
    if tenant_id not in _spec_managers:
        _spec_managers[tenant_id] = SpecManager(tenant_id, data_dir)
    return _spec_managers[tenant_id]


def _json_response(data, status: int = 200) -> web.Response:
    return web.json_response(data, status=status)


def _error_response(message: str, status: int = 400) -> web.Response:
    return web.json_response({"error": message}, status=status)


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


async def list_specs(request: web.Request) -> web.Response:
    """GET /api/specs — List specs for the current tenant."""
    tenant = request.get("tenant")
    if not tenant or not tenant.tenant_config:
        return _error_response("Tenant context required", 400)

    manager = _get_spec_manager(tenant.tenant_id, tenant.tenant_config.data_dir)
    status_filter = request.query.get("status")
    specs = manager.list_specs(status=status_filter)
    return _json_response({"specs": [s.to_dict() for s in specs]})


async def create_spec(request: web.Request) -> web.Response:
    """POST /api/specs — Create a new spec."""
    tenant = request.get("tenant")
    if not tenant or not tenant.tenant_config:
        return _error_response("Tenant context required", 400)

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return _error_response("Invalid JSON body")

    name = body.get("name", "").strip()
    content = body.get("content", "").strip()
    if not name or not content:
        return _error_response("'name' and 'content' are required")

    manager = _get_spec_manager(tenant.tenant_id, tenant.tenant_config.data_dir)
    spec = manager.create_spec(
        name=name,
        content=content,
        author_id=tenant.user_id,
        description=body.get("description", ""),
        context=body.get("context", ""),
    )
    return _json_response({"spec": spec.to_dict()}, status=201)


async def get_spec(request: web.Request) -> web.Response:
    """GET /api/specs/{spec_id} — Get a single spec."""
    tenant = request.get("tenant")
    if not tenant or not tenant.tenant_config:
        return _error_response("Tenant context required", 400)

    spec_id = request.match_info["spec_id"]
    manager = _get_spec_manager(tenant.tenant_id, tenant.tenant_config.data_dir)

    try:
        spec = manager.get_spec(spec_id)
    except SpecNotFoundError:
        return _error_response(f"Spec not found: {spec_id}", 404)

    return _json_response({"spec": spec.to_dict()})


async def update_spec(request: web.Request) -> web.Response:
    """PUT /api/specs/{spec_id} — Update a spec (creates new version)."""
    tenant = request.get("tenant")
    if not tenant or not tenant.tenant_config:
        return _error_response("Tenant context required", 400)

    spec_id = request.match_info["spec_id"]

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return _error_response("Invalid JSON body")

    content = body.get("content", "").strip()
    if not content:
        return _error_response("'content' is required")

    manager = _get_spec_manager(tenant.tenant_id, tenant.tenant_config.data_dir)

    try:
        spec = manager.update_spec(
            spec_id=spec_id,
            content=content,
            author_id=tenant.user_id,
            name=body.get("name"),
            description=body.get("description"),
            context=body.get("context"),
        )
    except SpecNotFoundError:
        return _error_response(f"Spec not found: {spec_id}", 404)
    except SpecStatusError as exc:
        return _error_response(str(exc), 409)

    return _json_response({"spec": spec.to_dict()})


async def submit_spec(request: web.Request) -> web.Response:
    """POST /api/specs/{spec_id}/submit — Submit spec for agent processing."""
    tenant = request.get("tenant")
    if not tenant or not tenant.tenant_config:
        return _error_response("Tenant context required", 400)

    spec_id = request.match_info["spec_id"]
    manager = _get_spec_manager(tenant.tenant_id, tenant.tenant_config.data_dir)

    try:
        spec = manager.submit_spec(spec_id)
    except SpecNotFoundError:
        return _error_response(f"Spec not found: {spec_id}", 404)
    except SpecStatusError as exc:
        return _error_response(str(exc), 409)

    return _json_response({
        "spec": spec.to_dict(),
        "message": "Spec submitted for agent processing",
    })


async def delete_spec(request: web.Request) -> web.Response:
    """DELETE /api/specs/{spec_id} — Delete a draft spec."""
    tenant = request.get("tenant")
    if not tenant or not tenant.tenant_config:
        return _error_response("Tenant context required", 400)

    spec_id = request.match_info["spec_id"]
    manager = _get_spec_manager(tenant.tenant_id, tenant.tenant_config.data_dir)

    try:
        manager.delete_spec(spec_id)
    except SpecNotFoundError:
        return _error_response(f"Spec not found: {spec_id}", 404)
    except SpecStatusError as exc:
        return _error_response(str(exc), 409)

    return _json_response({"deleted": True})


async def get_recommendations(request: web.Request) -> web.Response:
    """GET /api/specs/{spec_id}/recommendations — Get AI recommendations.

    Queries the shared memory system for patterns relevant to this spec
    and returns them without revealing source tenant information.
    """
    tenant = request.get("tenant")
    if not tenant or not tenant.tenant_config:
        return _error_response("Tenant context required", 400)

    # Check if tenant has shared memory read access
    if not tenant.tenant_config.shared_memory_read:
        return _json_response({"recommendations": []})

    spec_id = request.match_info["spec_id"]
    manager = _get_spec_manager(tenant.tenant_id, tenant.tenant_config.data_dir)

    try:
        spec = manager.get_spec(spec_id)
    except SpecNotFoundError:
        return _error_response(f"Spec not found: {spec_id}", 404)

    # Get recommendations from shared memory (public_dict strips source_tenant_id)
    store = get_shared_memory_store()
    recommendations = store.get_recommendations_for_spec(spec.content)

    return _json_response({
        "recommendations": [r.public_dict() for r in recommendations],
        "spec_id": spec_id,
    })


async def apply_recommendation(request: web.Request) -> web.Response:
    """POST /api/specs/{spec_id}/recommendations/{entry_id}/apply

    Track that a recommendation was applied and increment its usage count.
    """
    tenant = request.get("tenant")
    if not tenant or not tenant.tenant_config:
        return _error_response("Tenant context required", 400)

    spec_id = request.match_info["spec_id"]
    entry_id = request.match_info["entry_id"]

    manager = _get_spec_manager(tenant.tenant_id, tenant.tenant_config.data_dir)

    try:
        manager.apply_recommendation(spec_id, entry_id)
    except SpecNotFoundError:
        return _error_response(f"Spec not found: {spec_id}", 404)

    # Increment usage in shared memory
    store = get_shared_memory_store()
    store.increment_usage(entry_id)

    return _json_response({"applied": True})


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


def register_spec_routes(app: web.Application) -> None:
    """Register spec management routes on the aiohttp app."""
    app.router.add_get("/api/specs", list_specs)
    app.router.add_post("/api/specs", create_spec)
    app.router.add_get("/api/specs/{spec_id}", get_spec)
    app.router.add_put("/api/specs/{spec_id}", update_spec)
    app.router.add_delete("/api/specs/{spec_id}", delete_spec)
    app.router.add_post("/api/specs/{spec_id}/submit", submit_spec)
    app.router.add_get("/api/specs/{spec_id}/recommendations", get_recommendations)
    app.router.add_post(
        "/api/specs/{spec_id}/recommendations/{entry_id}/apply",
        apply_recommendation,
    )
    logger.info("Registered spec management routes")
