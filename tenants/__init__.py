"""Multi-tenant infrastructure module.

Provides tenant isolation, configuration, and lifecycle management
for the enterprise multi-tenant platform.

Exports:
    - TenantConfig, PoolAllocation, TenantContext (data models)
    - TenantStore (CRUD persistence)
    - TenantIsolationManager (directory and resource isolation)
    - tenant_middleware (aiohttp middleware for request-scoped tenant context)
"""

from tenants.models import PoolAllocation, TenantConfig, TenantContext
from tenants.store import TenantStore, get_tenant_store, reset_tenant_store
from tenants.isolation import TenantIsolationManager
from tenants.middleware import tenant_middleware

__all__ = [
    "PoolAllocation",
    "TenantConfig",
    "TenantContext",
    "TenantIsolationManager",
    "TenantStore",
    "get_tenant_store",
    "reset_tenant_store",
    "tenant_middleware",
]
