# Multi-Tenant Architecture

Tenant isolation, data partitioning, and resource allocation.

## Tenant Isolation Model

```mermaid
graph TB
    subgraph Platform
        MW["Tenant Middleware<br/><i>X-Tenant-Id resolution</i>"]
        TSTORE["TenantStore<br/><i>JSON persistence</i>"]
        ISO["IsolationManager<br/><i>Directory provisioning</i>"]
        POOL["TenantPool<br/><i>Agent allocation</i>"]
    end

    subgraph Tenant_A ["Tenant A (Acme Corp)"]
        DATA_A["data/tenants/tenant-a/"]
        GEN_A["generations/tenant-a/"]
        WT_A[".worktrees/tenant-a/"]
        POOL_A["Reserved: 3 agents<br/>Burst: +2 from warm pool"]
    end

    subgraph Tenant_B ["Tenant B (Beta Inc)"]
        DATA_B["data/tenants/tenant-b/"]
        GEN_B["generations/tenant-b/"]
        WT_B[".worktrees/tenant-b/"]
        POOL_B["Reserved: 2 agents<br/>Burst: +3 from warm pool"]
    end

    subgraph Shared
        WARM["Warm Pool<br/><i>Pre-warmed shared agents</i>"]
        MEMORY["Shared Memory<br/><i>Cross-tenant patterns<br/>(source anonymized)</i>"]
    end

    MW --> TSTORE
    MW --> ISO
    ISO --> DATA_A
    ISO --> GEN_A
    ISO --> DATA_B
    ISO --> GEN_B
    POOL --> POOL_A
    POOL --> POOL_B
    POOL --> WARM
    WARM -.->|burst| POOL_A
    WARM -.->|burst| POOL_B
```

## Data Partitioning

```mermaid
graph LR
    subgraph Filesystem
        direction TB
        ROOT["Project Root"]
        ROOT --> DATA["data/"]
        ROOT --> GEN["generations/"]
        ROOT --> WKTREE[".worktrees/"]

        DATA --> DT["tenants/"]
        DT --> DTA["tenant-a/<br/><i>config, specs, state</i>"]
        DT --> DTB["tenant-b/<br/><i>config, specs, state</i>"]

        GEN --> GA["tenant-a/<br/><i>generated projects</i>"]
        GEN --> GB["tenant-b/<br/><i>generated projects</i>"]

        WKTREE --> WA["tenant-a/<br/><i>git worktrees</i>"]
        WKTREE --> WB["tenant-b/<br/><i>git worktrees</i>"]
    end
```

## Request Flow with Tenant Context

```mermaid
sequenceDiagram
    participant Client as Customer Browser
    participant MW as Tenant Middleware
    participant Auth as Auth Handler
    participant API as REST API
    participant Store as TenantStore
    participant Spec as SpecManager

    Client->>MW: POST /api/specs<br/>X-Tenant-Id: tenant-a
    MW->>Store: resolve_tenant("tenant-a")
    Store-->>MW: TenantConfig

    MW->>Auth: validate_session(request)
    Auth-->>MW: User (role: member)

    MW->>API: request + TenantContext
    API->>Spec: create_spec(tenant_id="tenant-a", ...)
    Spec-->>API: Spec created
    API-->>Client: 201 Created
```

## Tenant Configuration

| Field | Description |
|-------|-------------|
| `tenant_id` | Unique identifier (UUID) |
| `name` | Display name (e.g., "Acme Corp") |
| `slug` | URL-safe identifier (e.g., "acme-corp") |
| `max_projects` | Maximum concurrent projects |
| `max_agents` | Maximum concurrent agent workers |
| `reserved_agents` | Guaranteed agent pool slots |
| `sso_config` | SAML/OIDC SSO configuration |
| `created_at` | Tenant creation timestamp |
