variable "environment" {
  description = "Environment name (production, staging, development)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["production", "staging", "development"], var.environment)
    error_message = "Environment must be production, staging, or development."
  }
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "patchflow"
}

variable "cluster_version" {
  description = "Kubernetes version for EKS"
  type        = string
  default     = "1.29"
}

variable "node_instance_types" {
  description = "Instance types for EKS nodes"
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_min_size" {
  description = "Minimum number of nodes"
  type        = number
  default     = 3
}

variable "node_max_size" {
  description = "Maximum number of nodes"
  type        = number
  default     = 10
}

variable "node_desired_size" {
  description = "Desired number of nodes"
  type        = number
  default     = 3
}

variable "gpu_instance_types" {
  description = "GPU instance types for AI inference"
  type        = list(string)
  default     = ["g4dn.xlarge"]
}

variable "enable_gpu_nodes" {
  description = "Enable GPU nodes for AI agents"
  type        = bool
  default     = true
}

variable "database_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.medium"
}

variable "database_name" {
  description = "Name of the PostgreSQL database"
  type        = string
  default     = "patchflow"
}

variable "database_username" {
  description = "Master username for RDS"
  type        = string
  default     = "patchflow_admin"
  sensitive   = true
}

variable "database_password" {
  description = "Master password for RDS"
  type        = string
  sensitive   = true
}

variable "redis_node_type" {
  description = "ElastiCache Redis node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "enable_monitoring" {
  description = "Enable CloudWatch monitoring"
  type        = bool
  default     = true
}

variable "enable_vpc_flow_logs" {
  description = "Enable VPC Flow Logs"
  type        = bool
  default     = true
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = "patchflow.ai"
}

variable "grafana_admin_user" {
  description = "Grafana admin username"
  type        = string
  default     = "admin"
  sensitive   = true
}

variable "grafana_admin_password" {
  description = "Grafana admin password"
  type        = string
  sensitive   = true
}

variable "enable_waf" {
  description = "Enable AWS WAF"
  type        = bool
  default     = true
}

locals {
  common_tags = {
    Project     = "PatchFlow"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }

  name_prefix = "patchflow-${var.environment}"

  # Environment-specific configurations
  env_config = {
    production = {
      multi_az           = true
      deletion_protection = true
      skip_final_snapshot = false
      backup_retention    = 35
    }
    staging = {
      multi_az           = false
      deletion_protection = false
      skip_final_snapshot = true
      backup_retention    = 7
    }
    development = {
      multi_az           = false
      deletion_protection = false
      skip_final_snapshot = true
      backup_retention    = 1
    }
  }

  current_env = local.env_config[var.environment]
}
