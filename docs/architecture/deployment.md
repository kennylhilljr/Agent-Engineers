# Deployment Architecture

AWS infrastructure and CI/CD pipeline.

## AWS Infrastructure

```mermaid
graph TB
    subgraph Internet
        USER["Users / Browsers"]
    end

    subgraph AWS ["AWS Cloud"]
        subgraph Edge
            CF["CloudFront<br/><i>CDN + TLS termination</i>"]
        end

        subgraph VPC ["VPC"]
            subgraph Public ["Public Subnets"]
                ALB["Application Load Balancer<br/><i>HTTPS → target groups</i>"]
                NAT["NAT Gateway"]
            end

            subgraph Private ["Private Subnets"]
                subgraph ECS ["ECS Fargate"]
                    TASK_API["API Task<br/><i>dashboard.rest_api_server</i><br/>Port 8080"]
                    TASK_DAEMON["Daemon Task<br/><i>daemon control plane</i><br/>Port 9100"]
                end

                subgraph Data ["Data Tier"]
                    RDS["RDS PostgreSQL 15<br/><i>Multi-AZ (prod)</i>"]
                    REDIS_AWS["ElastiCache Redis 7<br/><i>Session & cache</i>"]
                end
            end
        end

        ECR["ECR<br/><i>Container registry</i>"]
        S3["S3<br/><i>Terraform state +<br/>static assets</i>"]
        CW["CloudWatch<br/><i>Logs & metrics</i>"]
    end

    USER --> CF
    CF --> ALB
    ALB --> TASK_API
    ALB --> TASK_DAEMON
    TASK_API --> RDS
    TASK_API --> REDIS_AWS
    TASK_DAEMON --> RDS
    ECS --> ECR
    ECS --> CW
    ECS --> NAT
    NAT --> Internet
```

## CI/CD Pipeline

```mermaid
flowchart LR
    subgraph Trigger
        PR["Pull Request"] --> CI
        PUSH["Push to main"] --> CI
        TAG["Release tag<br/><i>v*.*.*</i>"] --> PROD
    end

    subgraph CI ["CI Pipeline"]
        LINT["Lint & Format<br/><i>ruff check + format</i>"]
        TYPE["Type Check<br/><i>mypy</i>"]
        TEST["Unit Tests<br/><i>pytest</i>"]
        DOCKER_BUILD["Docker Build<br/><i>Size check < 500MB</i>"]
        SECURITY_SCAN["Security Scan<br/><i>pip-audit</i>"]
    end

    subgraph Staging ["Deploy: Staging"]
        BUILD_STG["Build & Push<br/><i>ECR staging</i>"]
        DEPLOY_STG["ECS Deploy<br/><i>staging service</i>"]
        SMOKE["Smoke Tests"]
    end

    subgraph PROD ["Deploy: Production"]
        VALIDATE["Validate tag<br/><i>semver check</i>"]
        BUILD_PRD["Build & Push<br/><i>ECR production</i>"]
        DEPLOY_PRD["ECS Deploy<br/><i>prod service</i>"]
        VERIFY["Health Verify"]
        ROLLBACK["Auto-Rollback<br/><i>on failure</i>"]
    end

    CI --> Staging
    DEPLOY_PRD -->|failure| ROLLBACK
```

## Docker Image

```mermaid
graph LR
    subgraph Build ["Stage 1: Builder"]
        BASE_B["python:3.11-slim"]
        DEPS["Install gcc, g++"]
        PIP["pip install requirements"]
    end

    subgraph Prod ["Stage 2: Production"]
        BASE_P["python:3.11-slim"]
        CURL["Install curl"]
        COPY_PKG["Copy packages from builder"]
        COPY_SRC["Copy application source"]
        CLEAN["Remove tests, .git, __pycache__"]
        USER_SET["Non-root user: appuser"]
        HEALTH["Healthcheck: /health"]
    end

    Build --> Prod
```

## Environment Matrix

| Environment | Instance | Database | Redis | Auto-Scale |
|------------|----------|----------|-------|------------|
| **Development** | Local | PostgreSQL 15 (Docker) | Redis 7 (Docker) | N/A |
| **Staging** | t3.micro | RDS Single-AZ | ElastiCache | 1-2 tasks |
| **Production** | t3.small+ | RDS Multi-AZ | ElastiCache | 2-10 tasks |
