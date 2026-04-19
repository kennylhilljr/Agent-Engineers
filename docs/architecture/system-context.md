# System Context Diagram (C4 Level 1)

High-level view of the Agent Engineers platform and its external interactions.

```mermaid
graph TB
    subgraph Actors
        CUSTOMER["Customer<br/><i>Enterprise tenant user</i>"]
        ADMIN["Platform Admin<br/><i>Manages tenants & agents</i>"]
    end

    PLATFORM["Agent Engineers Platform<br/><i>Multi-tenant agentic coding platform</i>"]

    subgraph External Systems
        CLAUDE["Claude API<br/><i>Anthropic LLM</i>"]
        LINEAR["Linear<br/><i>Issue tracking</i>"]
        GITHUB["GitHub<br/><i>Version control & PRs</i>"]
        SLACK["Slack<br/><i>Notifications</i>"]
        ARCADE["Arcade MCP Gateway<br/><i>Tool orchestration</i>"]
        PROVIDERS["AI Providers<br/><i>OpenAI, Gemini, Groq,<br/>Kimi, Windsurf, OpenRouter</i>"]
    end

    CUSTOMER -->|"Submit specs,<br/>view projects"| PLATFORM
    ADMIN -->|"Manage tenants,<br/>monitor agents"| PLATFORM

    PLATFORM -->|"Agent sessions"| CLAUDE
    PLATFORM -->|"Issue management"| LINEAR
    PLATFORM -->|"Git operations,<br/>PRs, code review"| GITHUB
    PLATFORM -->|"Progress updates"| SLACK
    PLATFORM -->|"Tool execution"| ARCADE
    PLATFORM -->|"Bridge requests"| PROVIDERS
```

## Actors

| Actor | Description |
|-------|-------------|
| **Customer** | Enterprise tenant user who submits application specs and monitors agent progress via the customer dashboard |
| **Platform Admin** | Operator who manages tenants, agent pools, shared memory, and platform configuration |

## External Systems

| System | Integration |
|--------|-------------|
| **Claude API** | Primary LLM for agent sessions via Claude Agent SDK |
| **Linear** | Issue and project management — agents create/update tickets autonomously |
| **GitHub** | Git operations, branch management, pull requests, and code review |
| **Slack** | Progress notifications and status updates |
| **Arcade MCP Gateway** | Tool orchestration layer providing controlled access to external tools |
| **AI Providers** | Alternative LLM providers accessed through the bridge architecture |
