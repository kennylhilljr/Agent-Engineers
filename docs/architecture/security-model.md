# Security Model

Defense-in-depth security architecture with four layers.

## Security Layers

```mermaid
graph TB
    subgraph Layer1 ["Layer 1: Tenant Isolation"]
        TI_DATA["Separate data directories<br/><i>data/tenants/{id}/</i>"]
        TI_GEN["Separate project directories<br/><i>generations/{id}/</i>"]
        TI_WORKTREE["Separate worktree bases<br/><i>.worktrees/{id}/</i>"]
        TI_PORT["Separate port ranges"]
    end

    subgraph Layer2 ["Layer 2: OS Sandbox"]
        BWRAP["bwrap / container isolation"]
        FS_RESTRICT["Filesystem restrictions"]
    end

    subgraph Layer3 ["Layer 3: Permissions"]
        FILE_OPS["File operations restricted<br/>to tenant project directory"]
        RBAC["Role-based access control<br/><i>admin, member, viewer</i>"]
    end

    subgraph Layer4 ["Layer 4: Security Hooks"]
        ALLOWLIST["Bash command allowlist<br/><i>security.py</i>"]
        VALIDATION["Extra validation rules<br/><i>pkill, chmod, rm</i>"]
    end

    REQUEST["Incoming Request"] --> Layer1
    Layer1 --> Layer2
    Layer2 --> Layer3
    Layer3 --> Layer4
    Layer4 --> EXECUTE["Command Execution"]
```

## Authentication Flow

```mermaid
sequenceDiagram
    participant Browser as Browser
    participant API as REST API
    participant Auth as Auth Handler
    participant SSO as SSO Service

    alt Bearer Token Auth
        Browser->>API: Request + Authorization: Bearer <token>
        API->>Auth: validate_token(token)
        Auth->>Auth: hmac.compare_digest()
        Auth-->>API: Authenticated
    end

    alt OAuth / SSO
        Browser->>API: GET /auth/login
        API->>SSO: Redirect to IdP
        SSO-->>Browser: SAML/OIDC callback
        Browser->>API: POST /auth/callback
        API->>Auth: create_session(user)
        Auth-->>Browser: Set session cookie
    end
```

## Bash Command Security

```mermaid
flowchart LR
    CMD["Agent wants to run<br/>bash command"] --> HOOK["Security Hook<br/><i>pre-execution</i>"]
    HOOK --> CHECK{"Command in<br/>ALLOWED_COMMANDS?"}

    CHECK -->|No| BLOCK["BLOCKED<br/><i>Fail-safe deny</i>"]
    CHECK -->|Yes| EXTRA{"Needs extra<br/>validation?"}

    EXTRA -->|No| ALLOW["ALLOWED"]
    EXTRA -->|Yes| VALIDATE["Run validator<br/><i>validate_{cmd}_command()</i>"]

    VALIDATE -->|Pass| ALLOW
    VALIDATE -->|Fail| BLOCK
```

## Security Rules

| Command | Restriction |
|---------|-------------|
| `pkill` | Only dev processes: `node`, `npm`, `npx`, `vite`, `next` |
| `chmod` | Only `+x` mode |
| `rm` | Blocks system directories (`/`, `/usr`, `/etc`, etc.) |
| `curl`/`wget` | Allowed (sandboxed network) |
| Unlisted commands | Blocked entirely (fail-safe) |

## Authentication Methods

| Method | Layer | Use Case |
|--------|-------|----------|
| **Bearer Token** | API | Dashboard API access, `DASHBOARD_AUTH_TOKEN` env var |
| **SAML 2.0** | SSO | Enterprise IdP integration |
| **OpenID Connect** | SSO | OAuth-based SSO |
| **SCIM 2.0** | Provisioning | Automated user/group sync from IdP |
| **Session Cookie** | Web | Browser-based dashboard sessions |
