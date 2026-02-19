environment          = "production"
aws_region           = "us-east-1"
app_name             = "agent-dashboard"

# Networking
vpc_cidr             = "10.0.0.0/16"
availability_zones   = ["us-east-1a", "us-east-1b", "us-east-1c"]
private_subnet_cidrs = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
public_subnet_cidrs  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

# ACM certificate (must be created manually or via separate TF)
acm_certificate_arn  = "arn:aws:acm:us-east-1:ACCOUNT_ID:certificate/CERT_ID_PRODUCTION"

# ECS Fargate - sized for production load
task_cpu             = 512
task_memory          = 1024
desired_count        = 2
min_capacity         = 2
max_capacity         = 10

# RDS - production-grade (Multi-AZ enabled via environment check in main.tf)
db_instance_class    = "db.t3.small"
db_allocated_storage = 100

# ElastiCache - production-grade (2 replicas enabled via environment check)
redis_node_type      = "cache.t3.small"

# Logging
log_retention_days   = 90
