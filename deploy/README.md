# Agent Dashboard - Deployment Guide

This directory contains all deployment infrastructure for the Agent Dashboard SaaS platform.

## Architecture Overview

```
CloudFront CDN
     |
Application Load Balancer (HTTPS/TLS 1.3)
     |
ECS Fargate (auto-scaling 2-10 tasks)
     |          |
  RDS        ElastiCache
PostgreSQL      Redis
  15.4          7.0
```

## Directory Structure

```
deploy/
├── terraform/
│   ├── main.tf              # ECS Fargate, ALB, RDS, ElastiCache, CloudFront
│   ├── variables.tf         # Variable definitions
│   └── env/
│       ├── staging.tfvars   # Staging configuration
│       └── production.tfvars # Production configuration
├── postgres/
│   └── init.sql             # Database schema initialization
├── scripts/
│   ├── health_check.sh      # Verifies /health and /ready endpoints
│   └── smoke_test.sh        # Post-deployment smoke tests
├── nginx.conf               # Nginx reverse proxy config
└── README.md                # This file
```

## Local Development

### Prerequisites
- Docker >= 24.0
- Docker Compose >= 2.20

### Start local stack (dashboard + PostgreSQL + Redis)

```bash
docker-compose up -d
```

The dashboard will be available at http://localhost:8080.

### Health check

```bash
curl http://localhost:8080/health
curl http://localhost:8080/ready
```

## Docker

### Build

```bash
# Development build
docker build --target production -t agent-dashboard:local .

# Check image size (must be < 500MB)
docker image inspect agent-dashboard:local --format='{{.Size}}' | awk '{print $1/1024/1024 "MB"}'
```

### Run

```bash
docker run -d \
  -p 8080:8080 \
  -e ENVIRONMENT=production \
  -e DATABASE_URL=postgresql://... \
  -e REDIS_URL=redis://... \
  agent-dashboard:local
```

## CI/CD Pipelines

### CI (`ci.yml`) - runs on every PR
1. Unit tests with pytest
2. mypy type checking
3. Docker build + size check (< 500MB)
4. Security scan (pip-audit)

### Staging (`deploy-staging.yml`) - runs on push to `main`
1. Build and push image to ECR
2. Update ECS Fargate task definition
3. Rolling deploy (100% min healthy)
4. Smoke tests

### Production (`deploy-production.yml`) - runs on release tag (`v*.*.*`)
1. Validate semver tag
2. Build and push production image to ECR
3. Update ECS Fargate task definition
4. Rolling deploy with circuit breaker + auto-rollback
5. Smoke tests
6. CloudFront cache invalidation

## Terraform

### Setup

```bash
cd deploy/terraform

# Staging
terraform init
terraform plan -var-file=env/staging.tfvars
terraform apply -var-file=env/staging.tfvars

# Production
terraform plan -var-file=env/production.tfvars
terraform apply -var-file=env/production.tfvars
```

### Required AWS Secrets (GitHub Actions)
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `CLOUDFRONT_DISTRIBUTION_ID`

### Required Terraform Variables to set manually
- `acm_certificate_arn` - ACM certificate ARN for HTTPS

## Health Endpoints

| Endpoint | Purpose | Response |
|----------|---------|----------|
| `GET /health` | Docker/ECS HEALTHCHECK | `{"status": "ok", ...}` |
| `GET /api/health` | API health (same) | `{"status": "ok", ...}` |
| `GET /ready` | Readiness probe (DB + Redis connected) | `{"ready": true, ...}` |
| `GET /api/ready` | API readiness (same) | `{"ready": true, ...}` |

## Scripts

```bash
# Health check (local)
./deploy/scripts/health_check.sh http://localhost:8080

# Health check (staging)
./deploy/scripts/health_check.sh https://staging.agent-dashboard.example.com

# Smoke tests
./deploy/scripts/smoke_test.sh https://staging.agent-dashboard.example.com
```

## Security

- **Non-root user**: Container runs as `appuser` (UID from non-root group)
- **Secrets**: Stored in AWS SSM Parameter Store (SecureString), not in environment variables
- **TLS**: ALB enforces HTTPS, CloudFront enforces `redirect-to-https`
- **DB encryption**: RDS storage encrypted at rest, ElastiCache transit encryption enabled
- **Image scanning**: ECR scan-on-push enabled
