environment          = "staging"
aws_region           = "us-east-1"
app_name             = "agent-dashboard"

# Networking
vpc_cidr             = "10.1.0.0/16"
availability_zones   = ["us-east-1a", "us-east-1b"]
private_subnet_cidrs = ["10.1.1.0/24", "10.1.2.0/24"]
public_subnet_cidrs  = ["10.1.101.0/24", "10.1.102.0/24"]

# ACM certificate (must be created manually or via separate TF)
acm_certificate_arn  = "arn:aws:acm:us-east-1:ACCOUNT_ID:certificate/CERT_ID_STAGING"

# ECS Fargate - smaller for staging
task_cpu             = 256
task_memory          = 512
desired_count        = 1
min_capacity         = 1
max_capacity         = 2

# RDS - smaller for staging
db_instance_class    = "db.t3.micro"
db_allocated_storage = 20

# ElastiCache - smallest for staging
redis_node_type      = "cache.t3.micro"

# Logging
log_retention_days   = 7
