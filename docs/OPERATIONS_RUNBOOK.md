# Agent Dashboard — Production Operations Runbook

**Version:** 1.0
**Maintained by:** Platform Engineering
**Last updated:** 2026-02-19
**Ticket:** AI-260

---

## Table of Contents

1. [Monitoring and Observability](#1-monitoring-and-observability)
2. [Incident Response](#2-incident-response)
3. [Deployment Procedures](#3-deployment-procedures)
4. [Common Operational Tasks](#4-common-operational-tasks)
5. [SLA Definitions](#5-sla-definitions)

---

## 1. Monitoring and Observability

### 1.1 Key Metrics

The following metrics are the primary indicators of system health. All are exposed via the `/api/metrics` endpoint and collected into CloudWatch under the `/ecs/agent-dashboard` log group.

| Metric | Description | Source |
|--------|-------------|--------|
| `agent_error_rate` | Percentage of agent task executions ending in error | `/api/metrics`, CloudWatch |
| `task_latency_p50` | Median task completion time in milliseconds | `/api/metrics` |
| `task_latency_p95` | 95th percentile task completion time | `/api/metrics` |
| `task_latency_p99` | 99th percentile task completion time | `/api/metrics` |
| `websocket_connection_count` | Number of active WebSocket connections on `/ws` | CloudWatch, nginx access log |
| `queue_depth` | Number of pending tasks in the Redis work queue | CloudWatch, ElastiCache metrics |
| `memory_utilization` | ECS task memory utilization % (limit: 512 MB per task) | CloudWatch ECS Container Insights |
| `cpu_utilization` | ECS task CPU utilization % (limit: 1.0 vCPU per task) | CloudWatch ECS Container Insights |
| `db_connection_count` | Active PostgreSQL connections on RDS | RDS Performance Insights |
| `http_5xx_rate` | Rate of HTTP 5xx responses from the application | ALB access logs, CloudWatch |

### 1.2 Alerting Thresholds

All alerts are configured in CloudWatch Alarms and routed to the on-call rotation via PagerDuty.

#### Agent Error Rate

| Condition | Severity | Action |
|-----------|----------|--------|
| `agent_error_rate` > 5% for 5 minutes | P2 | Page on-call engineer |
| `agent_error_rate` > 20% for 2 minutes | P1 | Page on-call + escalate to engineering lead |

#### Task Latency

| Condition | Severity | Action |
|-----------|----------|--------|
| `task_latency_p95` > 10 seconds for 5 minutes | P2 | Investigate queue depth and ECS CPU |
| `task_latency_p99` > 30 seconds for 5 minutes | P1 | Page on-call engineer |

#### Infrastructure

| Condition | Severity | Action |
|-----------|----------|--------|
| `memory_utilization` > 80% for 5 minutes | P2 | Scale out ECS or investigate memory leak |
| `cpu_utilization` > 70% for 5 minutes | P2 | Auto-scaling policy triggers at 70% (see Terraform config) |
| `queue_depth` > 1000 for 10 minutes | P2 | Investigate worker pool; consider scaling |
| `websocket_connection_count` drops to 0 | P1 | WebSocket handler may have crashed |
| Health check failures on `/health` | P1 | ECS deployment circuit breaker will auto-rollback |
| `http_5xx_rate` > 1% for 5 minutes | P2 | Investigate application logs |
| `http_5xx_rate` > 5% for 2 minutes | P1 | Page on-call engineer |
| RDS connection failure | P0 | Full outage; immediate response required |

### 1.3 Dashboard Links

The Agent Dashboard UI provides real-time observability at the following paths. All paths are relative to the production base URL (`https://agent-dashboard.example.com`).

| View | Path | Description |
|------|------|-------------|
| Main Dashboard | `/` | Agent status panel, leaderboard, PM task launcher |
| Architecture View | `/architecture` (dashboard.html) | Provider rate limits, token usage, cost tracking |
| Audit Log UI | `/settings/audit-log` | SSO and admin action audit trail (AI-246) |
| Team Settings | `/settings/team` | RBAC member management UI (AI-245) |
| Pricing / Billing | `/pricing` | Subscription tiers and current billing status |
| Health Endpoint | `/health` | JSON health check (`{"status":"ok"}`) |
| Readiness Endpoint | `/ready` | JSON readiness check (`{"ready":"true"}`) |
| API Metrics | `/api/metrics` | Raw metrics JSON for agent operations |
| API Agent Status | `/api/agents` | List of all agents and their current status |
| System Status | `/api/agents/system-status` | Aggregate system status across all agents |

### 1.4 Log Locations

#### Production (AWS)

All production logs are shipped via the `awslogs` Docker log driver to CloudWatch. The configuration is defined in `docker-compose.prod.yml`:

```
CloudWatch Log Group:  /ecs/agent-dashboard
Log Stream Prefix:     dashboard
AWS Region:            us-east-1 (configurable via AWS_REGION)
```

To query logs using the AWS CLI:

```bash
# Tail recent application logs
aws logs tail /ecs/agent-dashboard --follow --region us-east-1

# Filter for errors in the last hour
aws logs filter-log-events \
  --log-group-name /ecs/agent-dashboard \
  --start-time $(date -d '1 hour ago' +%s000) \
  --filter-pattern "ERROR"

# Query structured logs with CloudWatch Insights
aws logs start-query \
  --log-group-name /ecs/agent-dashboard \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc | limit 50'
```

#### Nginx Access and Error Logs (within container / local Docker)

Defined in `deploy/nginx.conf`:

```
Access log:  /var/log/nginx/access.log  (format: combined + upstream timing)
Error log:   /var/log/nginx/error.log   (level: warn)
```

#### Local Development

When running via `init.sh` or `docker-compose.yml`, logs are emitted to stdout/stderr. Structured logging is provided by `structured_logging.py`. The `logs/` directory at the project root may receive file-backed logs depending on the runtime configuration.

---

## 2. Incident Response

### 2.1 On-Call Rotation

> **Template — replace with actual PagerDuty/OpsGenie schedule before production go-live.**

| Role | Responsibility | Rotation Cadence |
|------|---------------|------------------|
| Primary On-Call Engineer | First responder for all P0/P1/P2 alerts | Weekly rotation |
| Secondary On-Call Engineer | Escalation if primary is unreachable | Weekly rotation, offset by 3 days |
| Engineering Lead | Escalation path for P0/P1 incidents requiring architectural decisions | Available via direct message |
| VP Engineering | Stakeholder communication for P0 incidents with customer impact > 30 minutes | Available via direct message |

PagerDuty Service: `agent-dashboard-production`
On-call schedule URL: `https://[your-pagerduty-domain].pagerduty.com/schedules`

### 2.2 Severity Classification

#### P0 — Critical Outage

- **Definition:** Complete service unavailability. All users affected. Health check (`/health`) returning non-200 or timing out. ECS service has zero healthy tasks.
- **Response time:** Immediate (< 5 minutes to first acknowledgement)
- **Resolution target:** < 1 hour
- **Examples:** RDS connection failure, ECS cluster crash, CloudFront distribution error, expired TLS certificate.

#### P1 — Major Feature Broken

- **Definition:** Core functionality is unavailable for more than 20% of users. The service is up but a critical API subsystem is failing. `agent_error_rate` > 20%.
- **Response time:** < 15 minutes to first acknowledgement
- **Resolution target:** < 4 hours
- **Examples:** Agent task execution failing for majority of users, WebSocket connections dropping, authentication (`/api/auth/*`) returning 500s, Stripe webhook handler broken causing billing failures.

#### P2 — Partial Degradation

- **Definition:** Service is degraded for less than 20% of users, or a non-critical feature is broken. A workaround exists. `agent_error_rate` between 5–20%.
- **Response time:** < 1 hour to first acknowledgement
- **Resolution target:** < 8 hours
- **Examples:** Elevated latency on task execution, a specific AI provider bridge failing, SSO login broken for one IdP while email auth works, audit log export failing.

#### P3 — Minor Issue

- **Definition:** Minor degradation with a clear workaround. No measurable customer impact.
- **Response time:** Next business day
- **Resolution target:** Next sprint
- **Examples:** UI cosmetic bug, a non-critical API endpoint returning incorrect data, slow audit log queries, documentation links broken.

### 2.3 Escalation Paths

```
Alert fires in PagerDuty
        |
        v
Primary On-Call Engineer (5 min SLA to acknowledge)
        |
        | If not acknowledged in 5 minutes
        v
Secondary On-Call Engineer automatically paged
        |
        | If P0 or P1 not resolved within 30 minutes
        v
Engineering Lead notified directly
        |
        | If P0 not resolved within 45 minutes (customer-facing impact)
        v
VP Engineering notified; customer communication drafted
        |
        | If P0 involves data breach or security incident
        v
Security team + Legal notified immediately
```

For incidents that require Anthropic API escalation (e.g., Claude model availability issues), contact `support@anthropic.com` with your organization credentials and reference the affected Claude model and approximate request volume.

For Stripe billing escalations (e.g., webhook delivery failures, disputed charges), contact Stripe Dashboard → Support → Create Case. Reference the Stripe subscription ID from the `subscriptions` table.

### 2.4 Communication Templates

#### Initial Incident Notification (Slack — #incidents or #status channel)

```
:red_circle: *INCIDENT DECLARED — [P0/P1/P2]*

*Service:* Agent Dashboard (production)
*Time detected:* [UTC timestamp]
*Impact:* [Brief description — e.g., "Agent task execution failing for all users"]
*Symptoms:* [What users are seeing]
*Incident commander:* @[on-call engineer name]

Investigation is underway. Updates every 15 minutes or when status changes.
Status page: https://status.agent-dashboard.example.com
```

#### Update During Active Incident (every 15 minutes)

```
:information_source: *INCIDENT UPDATE — [P0/P1/P2] — [UTC timestamp]*

*Status:* Investigating / Identified / Mitigating / Monitoring
*Current impact:* [Updated description]
*What we know:* [Root cause hypothesis or confirmed cause]
*What we're doing:* [Active remediation steps]
*Next update:* [UTC timestamp or "when status changes"]
```

#### Incident Resolved

```
:white_check_mark: *INCIDENT RESOLVED — [P0/P1/P2]*

*Service:* Agent Dashboard (production)
*Duration:* [Start time] — [End time] ([total duration])
*Root cause:* [Brief description]
*Resolution:* [What fixed it]
*Users affected:* [Estimate]
*Follow-up:* Post-mortem to be published within 48 hours at [link]
```

#### User-Facing Status Page Message (for P0/P1)

```
We are currently investigating an issue affecting [feature/service].
Our team is actively working to resolve this.

Impact: [Brief, non-technical description]
Start time: [Time in user's timezone or UTC]

We will provide updates every 30 minutes. We apologize for the inconvenience.
```

---

## 3. Deployment Procedures

### 3.1 Standard Deployment Checklist

Production deployments are triggered automatically by publishing a GitHub Release with a semver tag (e.g., `v1.2.3`). The workflow is defined in `.github/workflows/deploy-production.yml`.

#### Pre-Deployment

- [ ] All tests pass on the release branch (CI workflow in `.github/workflows/ci.yml`)
- [ ] Staging deployment completed successfully (`.github/workflows/deploy-staging.yml`)
- [ ] Smoke tests pass on staging (`deploy/scripts/smoke_test.sh https://staging.agent-dashboard.example.com`)
- [ ] Database migrations reviewed and tested on staging (see section 3.4)
- [ ] No active P0 or P1 incidents in progress
- [ ] On-call engineer notified and available during deployment window
- [ ] Release notes drafted and reviewed
- [ ] Stripe webhook endpoints verified (if billing changes are included)
- [ ] SSM Parameter Store secrets up to date for the new release

#### Deployment Steps (automated via GitHub Actions)

1. GitHub Release published with tag matching `v*.*.*`
2. `validate-release` job: verifies semver tag format
3. `build-and-push` job: builds Docker image targeting the `production` stage, pushes to ECR with tag `v*.*.*` and `latest`
4. `deploy-production` job:
   - Downloads current ECS task definition
   - Renders updated task definition with new image tag
   - Deploys via rolling update (ECS `minimum_healthy_percent=100`, `maximum_percent=200`)
   - Waits for service stability
5. Smoke tests run against production (`deploy/scripts/smoke_test.sh`)
6. CloudFront cache invalidation (`/*`)
7. Release notes updated with deployment timestamp

#### Post-Deployment Verification

- [ ] Health check returns `{"status":"ok"}` at `https://agent-dashboard.example.com/health`
- [ ] Readiness check returns `{"ready":"true"}` at `https://agent-dashboard.example.com/ready`
- [ ] Manually verify agent status at `/api/agents`
- [ ] Verify metrics endpoint at `/api/metrics`
- [ ] Confirm WebSocket connections establish on `/ws`
- [ ] Check CloudWatch logs for any new error patterns in `/ecs/agent-dashboard`
- [ ] Confirm auto-scaling is functioning (ECS Service → Service Auto Scaling)

### 3.2 Rollback Procedure

#### Automatic Rollback

The ECS deployment circuit breaker is enabled (configured in `deploy/terraform/main.tf`):

```hcl
deployment_circuit_breaker {
  enable   = true
  rollback = true
}
```

If the new task definition fails its health check during a rolling deployment, ECS will automatically roll back to the previous stable task definition.

The Docker Swarm-equivalent rollback is also configured in `docker-compose.prod.yml`:

```yaml
update_config:
  failure_action: rollback
```

#### Manual Rollback via AWS CLI

If automatic rollback does not trigger or you need to roll back to a specific earlier version:

```bash
# Step 1: Identify the previous stable task definition revision
aws ecs describe-task-definition \
  --task-definition agent-dashboard-production \
  --query 'taskDefinition.revision'

# Step 2: List recent task definition revisions
aws ecs list-task-definitions \
  --family-prefix agent-dashboard-production \
  --sort DESC \
  --max-items 5

# Step 3: Update the ECS service to a specific prior revision
aws ecs update-service \
  --cluster agent-dashboard-production \
  --service agent-dashboard-production \
  --task-definition agent-dashboard-production:[PREVIOUS_REVISION] \
  --region us-east-1

# Step 4: Wait for rollback to stabilize
aws ecs wait services-stable \
  --cluster agent-dashboard-production \
  --services agent-dashboard-production

# Step 5: Run health check to confirm
bash deploy/scripts/health_check.sh https://agent-dashboard.example.com

# Step 6: Invalidate CloudFront cache if static assets changed
aws cloudfront create-invalidation \
  --distribution-id [CLOUDFRONT_DISTRIBUTION_ID] \
  --paths "/*"
```

#### ECR Image Rollback

If you need to redeploy a specific Docker image tag from ECR:

```bash
# List available image tags
aws ecr describe-images \
  --repository-name agent-dashboard \
  --query 'sort_by(imageDetails, &imagePushedAt)[-10:].imageTags'

# Force a new deployment with a specific ECR image tag
# (Update task definition image field, then update service)
aws ecs register-task-definition \
  --cli-input-json file://task-definition-rollback.json

aws ecs update-service \
  --cluster agent-dashboard-production \
  --service agent-dashboard-production \
  --task-definition agent-dashboard-production:[NEW_REVISION]
```

### 3.3 Blue/Green Deployment

The current Terraform infrastructure uses ECS rolling updates (`minimum_healthy_percent=100`, `maximum_percent=200`), which provides zero-downtime deployments. For a full blue/green pattern with instant traffic cutover:

#### Setup

```bash
# Step 1: Create a second ECS service (green) with the new task definition
aws ecs create-service \
  --cluster agent-dashboard-production \
  --service-name agent-dashboard-production-green \
  --task-definition agent-dashboard-production:[NEW_REVISION] \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}" \
  --load-balancers "targetGroupArn=[GREEN_TARGET_GROUP_ARN],containerName=dashboard,containerPort=8080"
```

#### Traffic Cutover

```bash
# Step 2: Health-check the green environment
bash deploy/scripts/health_check.sh https://green.agent-dashboard.example.com

# Step 3: Run full smoke test on green
bash deploy/scripts/smoke_test.sh https://green.agent-dashboard.example.com

# Step 4: Shift ALB listener to green target group
aws elbv2 modify-listener \
  --listener-arn [HTTPS_LISTENER_ARN] \
  --default-actions Type=forward,TargetGroupArn=[GREEN_TARGET_GROUP_ARN]

# Step 5: Monitor for 10 minutes
# Step 6: Decommission blue service if stable
aws ecs update-service \
  --cluster agent-dashboard-production \
  --service agent-dashboard-production-blue \
  --desired-count 0
```

#### Rollback (Blue/Green)

```bash
# Instantly revert to blue by restoring the listener
aws elbv2 modify-listener \
  --listener-arn [HTTPS_LISTENER_ARN] \
  --default-actions Type=forward,TargetGroupArn=[BLUE_TARGET_GROUP_ARN]
```

### 3.4 Database Migration Safety Checks

The production database is AWS RDS PostgreSQL 15.4 with Multi-AZ enabled, automated backups (retention: 7 days), and a backup window of 03:00–04:00 UTC. The schema is initialized via `deploy/postgres/init.sql`.

#### Before Running Any Migration

- [ ] Take a manual RDS snapshot before any schema change:
  ```bash
  aws rds create-db-snapshot \
    --db-instance-identifier agent-dashboard-production \
    --db-snapshot-identifier pre-migration-$(date +%Y%m%d%H%M)
  ```
- [ ] Test migration on staging RDS instance first
- [ ] Ensure migration is backwards-compatible (new columns must be `nullable` or have a `DEFAULT`; no column drops in the same release as the code change)
- [ ] Verify migration can be rolled back (have a down migration script ready)
- [ ] Schedule migration during low-traffic window (typically 02:00–04:00 UTC)
- [ ] Notify on-call engineer before starting

#### Migration Execution

```bash
# Connect to RDS via AWS Session Manager (bastion not required)
aws ssm start-session --target [ECS_TASK_ID]

# Or via psql with credentials from SSM Parameter Store
DATABASE_URL=$(aws ssm get-parameter \
  --name /agent-dashboard/production/DATABASE_URL \
  --with-decryption \
  --query Parameter.Value \
  --output text)

psql "$DATABASE_URL" -f migration-YYYYMMDD.sql

# Verify row counts and schema after migration
psql "$DATABASE_URL" -c "\d+ users"
psql "$DATABASE_URL" -c "SELECT count(*) FROM subscriptions;"
```

#### Dangerous Operations to Avoid in Production Migrations

- `DROP TABLE` or `DROP COLUMN` — always soft-delete first (add `is_deleted` column or rename)
- `ALTER TABLE ... ALTER COLUMN` that changes type — requires table rewrite and lock
- Adding a `NOT NULL` constraint to an existing column without a `DEFAULT` — locks table
- `TRUNCATE` on any table with data

---

## 4. Common Operational Tasks

### 4.1 Rotating API Keys

The application uses several external API keys managed via AWS SSM Parameter Store. All secrets are stored as `SecureString` parameters at the path prefix `/{app_name}/{environment}/`.

#### Secrets Stored in SSM Parameter Store

| Parameter Path | Description |
|---------------|-------------|
| `/agent-dashboard/production/DATABASE_URL` | RDS PostgreSQL connection string |
| `/agent-dashboard/production/REDIS_URL` | ElastiCache Redis connection string |
| `/agent-dashboard/production/SECRET_KEY` | Application session signing key (64-char random) |

#### Additional Secrets in ECS Task Environment / Docker Compose

Defined in `docker-compose.prod.yml`, these must be rotated in the ECS task definition and/or the deployment secrets store:

| Variable | Description |
|----------|-------------|
| `STRIPE_SECRET_KEY` | Stripe API secret key for billing (AI-221) |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook endpoint signing secret |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key for agent execution |

#### Rotation Procedure

```bash
# Step 1: Generate new secret value (example for SECRET_KEY)
NEW_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(64))")

# Step 2: Update the SSM parameter
aws ssm put-parameter \
  --name /agent-dashboard/production/SECRET_KEY \
  --value "$NEW_SECRET" \
  --type SecureString \
  --overwrite \
  --region us-east-1

# Step 3: For non-SSM secrets (e.g., STRIPE_SECRET_KEY), update the ECS task definition
# - Go to ECS Console -> Task Definitions -> agent-dashboard-production
# - Create new revision with updated environment variable
# - Deploy the new task definition revision

# Step 4: Force a new deployment to pick up the new secret
aws ecs update-service \
  --cluster agent-dashboard-production \
  --service agent-dashboard-production \
  --force-new-deployment \
  --region us-east-1

# Step 5: Verify the new tasks start successfully
aws ecs wait services-stable \
  --cluster agent-dashboard-production \
  --services agent-dashboard-production

# Step 6: Revoke the old key at the provider (Stripe Dashboard, Anthropic Console, etc.)
```

#### Stripe Key Rotation Specifics

1. Go to Stripe Dashboard -> Developers -> API Keys
2. Create a new **restricted** key with the same permissions as the existing key
3. Update `STRIPE_SECRET_KEY` in ECS environment via a new task definition revision
4. Deploy and confirm `/api/billing/tiers` and `/api/billing/current` return 200
5. Verify Stripe webhooks are still being received (check Stripe Dashboard -> Webhooks -> Recent deliveries)
6. Roll the old key in Stripe Dashboard

#### Anthropic API Key Rotation

1. Go to Anthropic Console -> API Keys
2. Create a new API key
3. Update `ANTHROPIC_API_KEY` in ECS environment
4. Deploy and confirm agent task execution is functional via `/api/agents`
5. Delete the old API key from Anthropic Console

### 4.2 Auditing SSO Configuration Changes

The audit log system (AI-246) records all SSO-related configuration changes. The audit log is accessible at:

- **API:** `GET /api/audit-log`
- **UI:** `/settings/audit-log`
- **Export (CSV):** `GET /api/audit-log/export/csv`
- **Export (JSON):** `GET /api/audit-log/export/json`
- **Event types list:** `GET /api/audit-log/event-types`

#### Querying SSO Configuration Changes via API

```bash
BASE_URL="https://agent-dashboard.example.com"

# Fetch all SSO-related audit events in the last 7 days
curl -s "${BASE_URL}/api/audit-log?event_type=sso_config_changed&since=$(date -d '7 days ago' --iso-8601=seconds)" \
  -H "X-User-Id: [your-user-id]" | jq .

# Filter by a specific actor (admin who made the change)
curl -s "${BASE_URL}/api/audit-log?actor_id=[admin-user-id]&since=$(date -d '30 days ago' --iso-8601=seconds)" \
  -H "X-User-Id: [your-user-id]" | jq '.entries[] | select(.event_type | startswith("sso"))'

# Export all audit events for a time range as CSV for compliance
curl -s "${BASE_URL}/api/audit-log/export/csv?since=2026-01-01T00:00:00Z&until=2026-02-01T00:00:00Z" \
  -H "X-User-Id: [your-user-id]" \
  -o audit-export-jan-2026.csv
```

#### SSO Audit Pagination

The audit log supports cursor-based pagination (default page size: 50, maximum: 500):

```bash
# First page
RESPONSE=$(curl -s "${BASE_URL}/api/audit-log?limit=100")
CURSOR=$(echo "$RESPONSE" | jq -r '.cursor')

# Subsequent pages
curl -s "${BASE_URL}/api/audit-log?limit=100&cursor=${CURSOR}"
```

#### SSO SAML/OIDC Configuration Files

The SSO handlers are located in the `sso/` directory:

- `sso/saml_handler.py` — SAML 2.0 IdP integration
- `sso/oidc_handler.py` — OpenID Connect integration
- `sso/scim_handler.py` — SCIM 2.0 provisioning (Fleet/Organization tiers)
- `sso/organization_store.py` — Organization SSO configuration storage

Any changes to SSO IdP metadata (entity IDs, certificates, ACS URLs) must be made by an Organization owner or Fleet admin and will be recorded in the audit log under the `sso_config_changed` event type. Coordinate with the customer's IT admin to ensure the IdP metadata is updated in sync.

### 4.3 Enterprise Customer Onboarding

Enterprise (Fleet tier) and Organization tier customers require manual onboarding steps in addition to self-service signup.

#### Step 1: Provision the Organization

The team management system (AI-245) uses RBAC with the following roles (highest to lowest): `owner`, `admin`, `member`, `viewer`.

```bash
BASE_URL="https://agent-dashboard.example.com"

# Create the initial owner account via the auth endpoint
# (or have the customer sign up via the UI — their first account becomes owner by default)

# Verify the org exists and the owner is set correctly
curl -s "${BASE_URL}/api/team/members" \
  -H "X-User-Id: [owner-user-id]" | jq '.members[] | select(.role == "owner")'
```

#### Step 2: Set the Tier

```bash
# Upgrade to the appropriate tier (requires authenticated owner session)
curl -s -X POST "${BASE_URL}/api/billing/upgrade" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: [owner-user-id]" \
  -d '{"to_tier": "fleet", "billing_period": "annual"}'

# Verify current billing state
curl -s "${BASE_URL}/api/billing/current" \
  -H "X-User-Id: [owner-user-id]" | jq '{tier: .tier.name, status: .trial}'
```

For Fleet (custom pricing), the API response redirects to sales (`contact_url`). The Stripe subscription must be created manually via the Stripe Dashboard after contract signing.

#### Step 3: Invite Team Members

The owner can invite additional admins and members. The invitation rate limit is 20 invitations per org per day.

```bash
# Invite an admin
curl -s -X POST "${BASE_URL}/api/team/invite" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: [owner-user-id]" \
  -d '{"role": "admin", "email": "admin@customer.com"}'

# Generate a shareable invite link (no email specified)
curl -s -X POST "${BASE_URL}/api/team/invite" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: [owner-user-id]" \
  -d '{"role": "member"}'
```

Accepted invitations are recorded in the audit log (`invite_accepted` event).

#### Step 4: Configure SSO (Organization and Fleet Tiers)

SSO (SAML/OIDC) is available on Organization and Fleet tiers. Coordinate with the customer's IT team to:

1. Provide the Service Provider (SP) entity ID and ACS URL from `sso/saml_handler.py` or `sso/oidc_handler.py`
2. Receive the IdP metadata XML (SAML) or OIDC well-known configuration URL
3. Update the organization's SSO configuration in `sso/organization_store.py`
4. Test SSO login with a pilot user account
5. Enable SCIM provisioning if required (Fleet tier only via `sso/scim_handler.py`)

All SSO configuration steps are recorded in `/api/audit-log`.

#### Step 5: Set Per-Project Role Overrides (if needed)

For customers requiring project-level RBAC:

```bash
# Grant a specific user a different role on a specific project
curl -s -X PUT "${BASE_URL}/api/team/members/[user-id]/project-role" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: [owner-or-admin-user-id]" \
  -d '{"project_id": "proj-abc123", "role": "admin"}'
```

#### Onboarding Checklist

- [ ] Organization account created; owner role assigned
- [ ] Tier set to Organization or Fleet; Stripe subscription active
- [ ] Initial admin users invited and access confirmed
- [ ] SSO configured and tested (if applicable)
- [ ] SCIM provisioning enabled and tested (Fleet only)
- [ ] Customer handed off runbook links and support contacts
- [ ] Audit log reviewed to confirm all setup actions recorded
- [ ] Dedicated support channel opened in Slack (Fleet tier)

### 4.4 Handling Billing Disputes

The billing system (AI-221) integrates with Stripe for subscription management. Billing disputes typically arise in two categories: usage overages and payment failures.

#### Investigating a Billing Dispute

```bash
BASE_URL="https://agent-dashboard.example.com"

# Get the customer's current billing state
curl -s "${BASE_URL}/api/billing/current" \
  -H "X-User-Id: [customer-user-id]" | jq '{
    tier: .tier.name,
    used_hours: .usage.used_hours,
    included_hours: .usage.included_hours,
    overage_hours: .usage.overage_hours,
    overage_charge_usd: .usage.overage_charge_usd,
    total_charge_usd: .usage.total_charge_usd
  }'

# Check trial status
curl -s "${BASE_URL}/api/billing/current" \
  -H "X-User-Id: [customer-user-id]" | jq '.trial'

# Get tier definitions to verify what was billed
curl -s "${BASE_URL}/api/billing/tiers?billing_period=monthly" | jq '.tiers[] | {name, monthly_price_usd, agent_hours_per_month}'
```

#### Stripe Dashboard Steps for Disputes

1. Log into Stripe Dashboard -> Customers
2. Search for the customer by email or Stripe customer ID (from `subscriptions` table: `stripe_customer_id`)
3. Review invoice history and the specific disputed charge
4. For legitimate overages, walk the customer through the usage data from `/api/billing/current`
5. For system errors (e.g., overage billed when usage was within limits), issue a Stripe credit or refund:
   - Stripe Dashboard -> Customers -> [Customer] -> Create Credit Note
6. Update the affected subscription if the dispute reveals a tier mismatch:
   ```bash
   curl -s -X POST "${BASE_URL}/api/billing/upgrade" \
     -H "Content-Type: application/json" \
     -H "X-User-Id: [customer-user-id]" \
     -d '{"to_tier": "[correct-tier]", "billing_period": "monthly"}'
   ```

#### Stripe Webhook Verification

If a customer reports their subscription not updating after payment:

```bash
# Check Stripe webhook delivery status
# In Stripe Dashboard: Developers -> Webhooks -> [Endpoint] -> Recent Deliveries

# Test that the webhook handler is reachable
curl -s -o /dev/null -w "%{http_code}" \
  https://agent-dashboard.example.com/api/billing/stripe/webhook
# Expected: 405 (GET not allowed) or 400 (no payload) — not 404 or 500
```

If webhooks are failing, check `billing/webhook_handler.py` and verify `STRIPE_WEBHOOK_SECRET` is current in the ECS task environment.

#### Fleet Tier Custom Billing

Fleet tier billing is handled via custom contracts, not the self-service Stripe flow. For Fleet tier billing questions:

1. Locate the customer's contract in the internal CRM
2. Cross-reference agent-hours usage from `/api/billing/current`
3. Escalate to the sales/customer success team for contract-level adjustments
4. Any credits or adjustments require approval from the VP of Revenue

---

## 5. SLA Definitions

### 5.1 Uptime Targets by Tier

| Tier (Product Name) | Tier ID | Uptime Target | Allowed Downtime / Month | Support Response SLA |
|--------------------|---------|---------------|--------------------------|---------------------|
| Explorer (Free) | `explorer` | 99.0% | ~7.2 hours | Best-effort (community support only) |
| Builder | `builder` | 99.5% | ~3.6 hours | 24-hour response (email support) |
| Team | `team` | 99.9% | ~43 minutes | 8-hour response (priority support) |
| Organization | `organization` | 99.9% | ~43 minutes | 8-hour response (dedicated support) |
| Fleet (Enterprise) | `fleet` | 99.99% | ~4.4 minutes | 1-hour response, dedicated CSM |

**Uptime measurement:** The service is considered "up" when `GET /health` returns HTTP 200 with `{"status":"ok"}` from at least one healthy ECS task, measured from the CloudFront origin. Measurements are taken every 60 seconds by the ALB health check configuration (threshold: 2 healthy, 3 unhealthy; interval: 30s; timeout: 10s).

**Scheduled maintenance:** Planned maintenance windows (typically 02:00–04:00 UTC on the first Tuesday of each month) are excluded from uptime calculations provided customers receive at least 72 hours advance notice via the status page and email.

### 5.2 Support Response Times

| Tier | P0 Response | P1 Response | P2 Response | P3 Response | Support Channel |
|------|-------------|-------------|-------------|-------------|-----------------|
| Explorer | Best-effort | Best-effort | Best-effort | Community | GitHub Issues / Community Forum |
| Builder | 24 hours | 24 hours | 24 hours | 5 business days | Email support |
| Team | 4 hours | 8 hours | 24 hours | 5 business days | Priority email + ticketing |
| Organization | 2 hours | 8 hours | 24 hours | 5 business days | Dedicated email + ticketing |
| Fleet | 1 hour | 1 hour | 4 hours | 2 business days | Dedicated CSM + Slack connect + ticketing |

### 5.3 Data Retention Policies

Per AI-246 (audit log and data retention), the following policies apply:

| Data Type | Explorer / Builder | Team / Organization | Fleet (Enterprise) |
|-----------|-------------------|--------------------|--------------------|
| **Audit log events** | 30 days | 90 days | 1 year |
| **Agent execution logs** | 30 days | 90 days | 1 year (or per contract) |
| **Usage records** (`usage_records` table) | 90 days | 90 days | 1 year |
| **Agent metrics snapshots** | 30 days | 90 days | 1 year |
| **Session records** | 30 days (or expiry) | 30 days (or expiry) | 90 days (or expiry) |
| **Subscription/billing records** | 7 years (legal requirement) | 7 years | 7 years |
| **RDS automated backups** | N/A (shared RDS) | 7-day retention | 7-day retention (configurable per contract) |

Data retention is enforced via scheduled cleanup jobs. Customers may request earlier deletion of their data by contacting support with a formal data deletion request; Fleet tier customers may have contractually defined extended retention.

### 5.4 SLA Exclusions

The following are excluded from uptime SLA calculations for all tiers:

- Force majeure events (natural disasters, widespread AWS region outages)
- Scheduled maintenance windows communicated at least 72 hours in advance
- Issues caused by customer-side network failures or misconfigured SSO IdP settings
- Actions taken by the customer that violate the Terms of Service
- Third-party service outages (Stripe, Anthropic API, Linear, GitHub) that are outside our control, provided the agent-dashboard service itself remains reachable

### 5.5 SLA Reporting

- Monthly uptime reports are generated from CloudWatch metrics and available to Organization and Fleet tier customers on request
- Fleet tier customers receive automated monthly SLA reports via their dedicated CSM
- SLA credit requests must be submitted within 30 days of the incident via `support@agent-dashboard.example.com` with the incident timestamp and evidence of impact

---

*This runbook should be reviewed and updated after each significant incident (post-mortem action), at each major release, and at minimum quarterly. Changes to this document should be submitted as pull requests and approved by the on-call engineering lead.*
