# Platform Administration Guide

## Overview

This guide covers day-to-day platform administration: managing tenants, monitoring agent pools, tuning performance, and using the shared memory system.

## Tenant Management

### Creating a Tenant

Via API:

```bash
curl -X POST http://localhost:8080/api/platform/tenants \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corp",
    "slug": "acme-corp",
    "max_projects": 20,
    "max_concurrent_agents": 10,
    "allowed_models": ["haiku", "sonnet", "opus"],
    "sso_enabled": true,
    "pool_config": {
      "coding": {"pool_type": "coding", "min_reserved": 2, "max_burst": 5}
    }
  }'
```

Or via the Platform Admin Dashboard at `/platform/tenants`.

### Suspending a Tenant

Suspension blocks all operations but preserves data:

```bash
curl -X PATCH http://localhost:8080/api/platform/tenants/{tenant_id} \
  -H "Content-Type: application/json" \
  -d '{"status": "suspended"}'
```

### Reactivating a Tenant

```bash
curl -X PATCH http://localhost:8080/api/platform/tenants/{tenant_id} \
  -H "Content-Type: application/json" \
  -d '{"status": "active"}'
```

### Deleting a Tenant

This removes all tenant data including generated projects:

```bash
curl -X DELETE http://localhost:8080/api/platform/tenants/{tenant_id}
```

## Agent Pool Management

### Monitoring Pools

Check global pool status:

```bash
curl http://localhost:9100/platform/pools
```

Check per-tenant allocation:

```bash
curl http://localhost:9100/tenants/{tenant_id}/pools
```

### Pre-Warming Agents

Pre-warm the shared pool for faster tenant onboarding:

```bash
curl -X POST http://localhost:9100/platform/warm \
  -H "Content-Type: application/json" \
  -d '{"count": 5, "pool_type": "coding"}'
```

Set default warm pool size via environment:

```bash
export WARM_POOL_SIZE=3
```

### Resizing Pools

Adjust pool sizes dynamically:

```bash
curl -X PATCH http://localhost:9100/pools/coding \
  -H "Content-Type: application/json" \
  -d '{"max_workers": 10}'
```

## Shared Memory

### Browsing Entries

Access the memory browser at `/platform/memory` or via API:

```bash
# List all entries
curl http://localhost:8080/api/platform/memory?limit=50

# Search by keyword
curl http://localhost:8080/api/platform/memory?query=authentication

# Filter by category
curl http://localhost:8080/api/platform/memory?category=error_resolution
```

### Memory Categories

| Category | Description |
|---|---|
| `pattern` | Successful implementation patterns |
| `anti_pattern` | Approaches that failed |
| `architecture` | Architectural decisions and trade-offs |
| `tool_usage` | Effective tool/framework usage |
| `error_resolution` | Error diagnosis and fix patterns |
| `spec_template` | Reusable spec structures |
| `integration` | External service integration patterns |

### Managing Entries

Entries are automatically collected from agent sessions. Platform admins can:

- **Edit confidence**: Adjust how strongly an entry is recommended
- **Delete entries**: Remove incorrect or outdated patterns
- **Add tags**: Improve discoverability

## Environment Configuration

### Required Variables

| Variable | Description |
|---|---|
| `ARCADE_API_KEY` | Arcade MCP gateway API key |
| `ARCADE_GATEWAY_SLUG` | Gateway slug identifier |
| `PLATFORM_ADMIN_EMAILS` | Comma-separated admin emails |

### Tuning Variables

| Variable | Default | Description |
|---|---|---|
| `DEFAULT_TENANT_MAX_PROJECTS` | 10 | Default project limit for new tenants |
| `DEFAULT_TENANT_MAX_AGENTS` | 5 | Default concurrent agent limit |
| `WARM_POOL_SIZE` | 3 | Pre-warmed agents in shared pool |
| `ORCHESTRATOR_MODEL` | sonnet | Default orchestrator model |

## Monitoring

### Health Check

```bash
curl http://localhost:8080/health
curl http://localhost:9100/health
```

### Key Metrics

Monitor via the Platform Dashboard (`/platform/dashboard`):

- **Total tenants**: Active tenant count
- **Active agents**: Currently running agent sessions
- **Pool utilization**: Reserved vs. burst vs. idle workers
- **Memory entries**: Total patterns captured

### Troubleshooting

1. **Tenant can't start agents**: Check `max_concurrent_agents` limit and pool availability
2. **Slow agent startup**: Pre-warm the shared pool with more workers
3. **Memory recommendations irrelevant**: Review and adjust confidence scores, add tags
4. **Port conflicts**: Check tenant port range allocation in `TenantIsolationManager`
