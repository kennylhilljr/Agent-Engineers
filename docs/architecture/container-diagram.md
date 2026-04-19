# Container Diagram (C4 Level 2)

Deployable units and data stores within the Agent Engineers platform.

```mermaid
graph TB
    subgraph Platform ["Agent Engineers Platform"]
        subgraph Web ["Web Layer"]
            CUST_DASH["Customer Dashboard<br/><i>HTML + JS</i><br/>Port 8080"]
            PLAT_DASH["Platform Admin Dashboard<br/><i>HTML + JS</i><br/>Port 8080"]
            REST["REST API Server<br/><i>Starlette/aiohttp</i><br/>Port 8080"]
            WS["WebSocket Server<br/><i>Real-time updates</i>"]
        end

        subgraph Core ["Core Engine"]
            ORCH["Orchestrator<br/><i>Agent session loop</i>"]
            SDK["Claude Agent SDK Client<br/><i>LLM interaction</i>"]
            AGENTS["Agent Definitions<br/><i>20+ specialized agents</i>"]
            ROUTER["Model Router<br/><i>Complexity-based selection</i>"]
        end

        subgraph Workers ["Worker Infrastructure"]
            DAEMON["Daemon Control Plane<br/><i>Port 9100</i>"]
            POOL["Worker Pool Manager<br/><i>Tenant-aware</i>"]
            WARM["Warm Pool<br/><i>Pre-warmed agents</i>"]
            TICKET["Ticket Router<br/><i>Complexity scoring</i>"]
            WORKTREE["Worktree Manager<br/><i>Git isolation</i>"]
        end

        subgraph Tenant ["Tenant Services"]
            TSTORE["Tenant Store<br/><i>JSON persistence</i>"]
            ISOLATION["Isolation Manager<br/><i>Directory scoping</i>"]
            SPEC["Spec Manager<br/><i>Lifecycle engine</i>"]
            TEAMS["Teams & RBAC"]
            SSO_SVC["SSO Service<br/><i>SAML, OIDC, SCIM</i>"]
        end

        subgraph Cross ["Cross-Cutting"]
            MEMORY["Shared Memory Store<br/><i>Cross-tenant patterns</i>"]
            SECURITY["Security Hooks<br/><i>Command allowlist</i>"]
            AUDIT_SVC["Audit Logger"]
            ANALYTICS["Analytics Engine"]
            BRIDGES["Provider Bridges<br/><i>OpenAI, Gemini, Groq,<br/>Kimi, Windsurf, OpenRouter</i>"]
        end
    end

    subgraph Data ["Data Stores"]
        JSON_FS["JSON Files<br/><i>data/tenants/*/</i>"]
        GEN_FS["Generated Projects<br/><i>generations/*/</i>"]
        PG["PostgreSQL<br/><i>Analytics & audit</i>"]
        REDIS["Redis<br/><i>Cache & sessions</i>"]
    end

    REST --> ORCH
    REST --> SPEC
    REST --> TSTORE
    CUST_DASH --> REST
    PLAT_DASH --> REST
    ORCH --> SDK
    ORCH --> AGENTS
    AGENTS --> ROUTER
    DAEMON --> POOL
    POOL --> WARM
    POOL --> TICKET
    POOL --> WORKTREE
    TSTORE --> JSON_FS
    ISOLATION --> GEN_FS
    ORCH --> WS
    ANALYTICS --> PG
    AUDIT_SVC --> PG
    MEMORY --> JSON_FS
    REST --> REDIS
```

## Container Descriptions

| Container | Technology | Purpose |
|-----------|-----------|---------|
| **Customer Dashboard** | HTML/JS | Tenant-scoped views for specs, projects, and agent status |
| **Platform Admin Dashboard** | HTML/JS | Cross-tenant monitoring, pool management, shared memory |
| **REST API Server** | Starlette + aiohttp | Unified HTTP API for dashboards, specs, and agent control |
| **WebSocket Server** | Python websockets | Real-time agent status push to dashboards |
| **Orchestrator** | Python async | Core session loop — delegates to specialized sub-agents |
| **Claude Agent SDK Client** | claude-agent-sdk | Manages LLM sessions with fresh context per iteration |
| **Daemon Control Plane** | Python HTTP (port 9100) | Scalable multi-tenant ticket processing |
| **Worker Pool Manager** | Python async | Manages reserved + burst agent workers per tenant |
| **Tenant Store** | JSON persistence | CRUD for tenant configuration and state |
| **Spec Manager** | Python | Spec lifecycle: draft → submitted → processing → completed |
| **Security Hooks** | Python | Pre-execution bash command validation via allowlist |
| **Provider Bridges** | Python async | Adapters for external AI providers (OpenAI, Gemini, etc.) |
