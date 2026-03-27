# Multi-Tenant Architecture

## Overview

The platform uses a multi-tenant architecture where each enterprise customer (tenant) operates in complete isolation while sharing the underlying infrastructure. Tenants cannot access each other's data, projects, or agent sessions.

## Tenant Model

### TenantConfig

Each tenant has a `TenantConfig` (defined in `tenants/models.py`) that controls:

- **Resource limits**: max projects, max concurrent agents, monthly agent-hour budget
- **Model access**: which Claude model tiers are allowed (haiku, sonnet, opus)
- **Feature flags**: SSO, SCIM, analytics, audit logging, custom integrations
- **Agent pool allocation**: per-pool-type reserved and burst worker counts
- **Isolation paths**: tenant-specific data and generation directories

### Tenant Lifecycle

```
create → active → suspended → reactivated
                 → deprovisioning → deleted
```

- **Active**: fully operational
- **Suspended**: all operations blocked, data preserved
- **Deprovisioning**: data cleanup in progress
- **Deleted**: all data removed

### Tenant-to-Organization Mapping

Each tenant maps 1:1 to an Organization in the SSO system. The `Organization.tenant_id` field links them. Creating an organization auto-provisions a tenant.

## Data Isolation

### Directory Structure

```
data/
├── tenants/
│   ├── {tenant-a-id}/
│   │   ├── specs/              # tenant A's spec files
│   │   ├── projects/           # tenant A's project state
│   │   └── specs_index.json    # tenant A's spec index
│   └── {tenant-b-id}/
│       ├── specs/
│       ├── projects/
│       └── specs_index.json
├── tenants.json                # global tenant registry
└── shared_memory.json          # cross-tenant patterns (platform team only)

generations/
├── {tenant-a-id}/
│   ├── project-1/              # tenant A's generated code
│   ├── project-2/
│   └── .worktrees/             # tenant A's git worktrees
└── {tenant-b-id}/
    ├── project-1/
    └── .worktrees/
```

### Port Isolation

Each tenant gets an isolated port range for dev servers to prevent collisions:

- Tenant 0: ports 3100-3119
- Tenant 1: ports 3120-3139
- Tenant N: ports 3100 + (N * 20) through 3100 + (N * 20) + 19

## Agent Pool Architecture

### Pool Types

- **Coding pool**: implementation agents (configurable min/max workers)
- **Review pool**: PR review agents
- **Linear pool**: project management agents
- **Warm pool**: pre-initialized workers for instant allocation (shared)

### Allocation Strategy

```
Per-Tenant Reserved Workers (guaranteed minimum)
    ↓ (if available)
Shared Warm Pool (pre-warmed, first-come-first-served)
    ↓ (if warm pool empty)
Dynamic Creation (on-demand, subject to global limits)
```

Each tenant's `pool_config` specifies:

- `min_reserved`: guaranteed minimum workers (always available)
- `max_burst`: maximum workers including burst from shared pool
- `default_model`: default Claude model tier for this pool

### Pre-Warming

Platform admins can pre-warm the shared pool via:

- API: `POST /api/platform/warm` with `{"count": N, "pool_type": "coding"}`
- Config: `WARM_POOL_SIZE` environment variable

## Request Flow

```
Client Request
    → Auth Middleware (validate session/token)
    → Tenant Middleware (resolve tenant, inject TenantContext)
    → Route Handler (tenant-scoped operations)
    → Response
```

The `TenantContext` (injected by middleware into `request['tenant']`) provides:

- `tenant_id`: active tenant
- `tenant_config`: full configuration
- `user_id`: authenticated user
- `role`: user's role in the tenant org
- `is_platform_admin`: platform-level access

## Shared Memory System

### Privacy Model

The shared memory system captures patterns across all tenant builds. Source tenant identity is stored for platform team auditing but **never exposed** to tenants.

- `MemoryEntry.source_tenant_id`: stored in persistence, visible only to platform admins
- `MemoryEntry.public_dict()`: strips `source_tenant_id` for tenant-facing APIs
- Recommendations on the spec page show pattern content without attribution

### Collection Pipeline

```
Agent Session Completes
    → MemoryCollector.on_session_complete()
    → Extract patterns (implementation, error resolution, tool usage)
    → Store in SharedMemoryStore
    → Available for future spec recommendations
```

### Recommendation Flow

```
Customer opens spec editor
    → GET /api/specs/{id}/recommendations
    → SharedMemoryStore.get_recommendations_for_spec(spec_content)
    → Keyword matching + confidence scoring
    → Return public_dict() entries (no source_tenant_id)
```

## Dashboard Access Control

### Customer Dashboard (`/customer/*`)

- Requires valid tenant context (X-Tenant-Id header or session)
- Scoped to tenant's own data only
- WebSocket broadcasts filtered to tenant's agents

### Platform Admin Dashboard (`/platform/*`)

- Requires `PLATFORM_ADMIN_EMAILS` membership
- Cross-tenant visibility
- Full shared memory access (including source_tenant_id)
- Tenant CRUD operations

### RBAC Permissions

| Permission | Viewer | Member | Admin | Owner | Platform Admin |
|---|---|---|---|---|---|
| MANAGE_TENANT_CONFIG | - | - | Yes | Yes | Yes |
| VIEW_PLATFORM_ADMIN | - | - | - | - | Yes |
| MANAGE_AGENT_POOLS | - | - | Yes | Yes | Yes |
| MANAGE_SHARED_MEMORY | - | - | - | - | Yes |
