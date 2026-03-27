# Product Roadmap

**Last Updated:** 2026-03-26
**Review Cadence:** Weekly (every Monday)
**Next Review:** 2026-03-30

---

## Q2 2026 (April - June): Foundation

### April 2026 — Multi-Tenant MVP

- [x] Remove billing/Stripe system
- [x] Implement tenant data model and store
- [x] Implement tenant isolation (directory, port, worktree)
- [x] Create tenant middleware for request scoping
- [x] Build customer dashboard (projects, agents, specs views)
- [x] Build platform admin dashboard (tenants, pools, memory, health)
- [x] Create spec-driven interface with CRUD and submission
- [x] Create shared memory system (store, collector, recommendations)
- [x] Update RBAC with enterprise permissions
- [x] Write tenant isolation, shared memory, and spec manager tests
- [x] Update all documentation (CLAUDE.md, architecture, admin guide)
- [ ] End-to-end integration testing
- [ ] Deploy to staging environment

### May 2026 — Agent Pool Maturity

- [ ] Implement pre-warming with configurable warm pool sizes
- [ ] Per-tenant agent hour tracking and soft limits
- [ ] Agent session replay and debugging tools
- [ ] Tenant onboarding wizard (guided setup flow)
- [ ] Spec templates library (common application patterns)
- [ ] WebSocket-based real-time updates scoped per tenant
- [ ] Load testing with 5+ concurrent tenants

### June 2026 — Memory Intelligence v1

- [ ] Vector-based similarity search for recommendations (extend knowledge_base/vector_store.py)
- [ ] Automated confidence scoring from outcome tracking
- [ ] Memory entry deduplication and merging
- [ ] Recommendation feedback loop (tenant marks recommendation helpful/not)
- [ ] Memory analytics dashboard for platform admins
- [ ] A/B testing framework for recommendation algorithms

---

## Q3 2026 (July - September): Scale

### July 2026 — Database Migration

- [ ] Migrate from JSON file persistence to PostgreSQL
- [ ] Implement connection pooling and query optimization
- [ ] Add database migrations with Alembic
- [ ] Migrate tenant store, memory store, spec store, user store
- [ ] Zero-downtime migration tooling

### August 2026 — Horizontal Scaling

- [ ] Stateless dashboard server (externalize session state to Redis)
- [ ] Multi-node daemon deployment (distributed worker pools)
- [ ] Shared nothing architecture for agent sessions
- [ ] Kubernetes deployment manifests (Helm charts)
- [ ] Auto-scaling based on tenant demand

### September 2026 — Advanced Security

- [ ] SOC 2 Type II compliance preparation
- [ ] Tenant data encryption at rest
- [ ] Network-level tenant isolation (namespace per tenant)
- [ ] API key management for programmatic access
- [ ] IP allowlisting per tenant
- [ ] Vulnerability scanning integration

---

## Q4 2026 (October - December): Enterprise Features

### October 2026 — Advanced Analytics

- [ ] Per-tenant cost attribution and reporting
- [ ] Agent performance benchmarking across tenants (anonymized)
- [ ] Sprint velocity and delivery metrics
- [ ] Custom report builder for tenant admins

### November 2026 — Custom Model Support

- [ ] Bring-your-own-model (BYO) for enterprise tenants
- [ ] Model performance comparison dashboard
- [ ] Automatic model selection based on task complexity and cost
- [ ] Fine-tuned model integration pipeline

### December 2026 — API and Integrations

- [ ] Public REST API with tenant-scoped API keys
- [ ] Webhook notifications for spec status changes
- [ ] Jira/Linear bidirectional sync per tenant
- [ ] Slack/Teams notifications per tenant
- [ ] GitHub/GitLab integration per tenant repository

---

## 2027: Growth

### Q1 2027 — On-Premise Option

- [ ] Self-hosted deployment package
- [ ] Air-gapped environment support
- [ ] Custom SSO/IdP integration
- [ ] Dedicated support tier

### Q2 2027 — Marketplace

- [ ] Spec template marketplace (community-contributed)
- [ ] Custom agent plugin system
- [ ] Integration marketplace (third-party tools)
- [ ] Tenant-to-tenant collaboration (opt-in)

### Q3-Q4 2027 — Platform Intelligence

- [ ] Predictive spec recommendations (proactive, not just reactive)
- [ ] Automated test generation from specs
- [ ] Cross-project dependency analysis
- [ ] AI-powered code quality scoring

---

## Weekly Review Process

Every Monday, the team reviews:

1. **Model landscape**: Evaluate new Claude, GPT, Gemini, and open-source model releases
   - Check Anthropic, OpenAI, Google model announcements
   - Benchmark new models against current defaults
   - Decision: integrate, replace, or add as option

2. **Roadmap progress**: Update completed items, adjust timelines

3. **Community intelligence**: Review GitHub issues, MCP ecosystem updates, competitor launches

4. **Memory system health**: Review recommendation accuracy, entry quality, collection volume

5. **Tenant feedback**: Aggregate and prioritize customer feature requests

---

## Model Evaluation Schedule

| Week | Focus Area |
|---|---|
| Week 1 of month | Claude model updates (Anthropic) |
| Week 2 of month | OpenAI / GPT model updates |
| Week 3 of month | Google Gemini / open-source models |
| Week 4 of month | MCP ecosystem and tool updates |

### Evaluation Criteria

- Task completion accuracy on benchmark suite
- Cost per agent-hour
- Context window utilization
- Latency (time to first token, total generation time)
- Tool use reliability
- Multi-turn conversation coherence
