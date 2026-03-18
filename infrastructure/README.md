# PatchFlow Infrastructure

Production-grade AWS infrastructure for the PatchFlow autonomous security platform.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    AWS CLOUD                              │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  VPC (10.0.0.0/16)                                  │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │ │
│  │  │  Public     │  │  Private    │  │  Database   │  │ │
│  │  │  Subnets    │  │  Subnets    │  │  Subnets    │  │ │
│  │  │  (ALB, NAT) │  │  (EKS, App) │  │  (RDS,     │  │ │
│  │  │             │  │             │  │  ElastiCache)│  │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  │ │
│  └─────────────────────────────────────────────────────┘ │
│                          │                                 │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  EKS Cluster (Kubernetes 1.29)                    │ │
│  │  • Managed Node Groups (t3.medium)                 │ │
│  │  • Auto-scaling (3-10 nodes)                      │ │
│  │  • GPU nodes for AI inference (g4dn.xlarge)      │ │
│  └─────────────────────────────────────────────────────┘ │
│                          │                                 │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  Data Layer                                        │ │
│  │  • RDS PostgreSQL 16 (Multi-AZ)                  │ │
│  │  • ElastiCache Redis (Cluster mode)              │ │
│  │  • MSK Kafka (3 brokers)                          │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

1. AWS CLI configured with credentials
2. Terraform >= 1.7.0
3. kubectl
4. AWS account with appropriate permissions

### Setup

```bash
# Initialize Terraform
cd infrastructure/terraform
terraform init

# Plan infrastructure
terraform plan -var="environment=production"

# Apply infrastructure
terraform apply -var="environment=production"

# Configure kubectl
aws eks update-kubeconfig --region us-east-1 --name patchflow-production
```

## Directory Structure

```
infrastructure/
├── terraform/
│   ├── modules/
│   │   ├── vpc/              # VPC, subnets, routing
│   │   ├── eks/              # EKS cluster, node groups
│   │   ├── rds/              # PostgreSQL database
│   │   ├── elasticache/      # Redis cluster
│   │   ├── msk/              # Kafka cluster
│   │   └── security/         # Security groups, IAM
│   ├── environments/
│   │   ├── production/       # Production config
│   │   └── staging/          # Staging config
│   ├── backend.tf            # Terraform state backend
│   ├── main.tf               # Main configuration
│   ├── variables.tf          # Input variables
│   └── outputs.tf            # Output values
└── kubernetes/
    ├── base/                 # Base K8s manifests
    └── overlays/
        ├── production/       # Production patches
        └── staging/         # Staging patches
```

## Environments

### Production
- Region: us-east-1
- VPC CIDR: 10.0.0.0/16
- EKS: 3-10 nodes (t3.medium)
- RDS: db.t3.medium Multi-AZ
- Redis: cache.t3.micro cluster

### Staging
- Region: us-east-1
- VPC CIDR: 10.1.0.0/16
- EKS: 2-5 nodes (t3.small)
- RDS: db.t3.micro Single-AZ
- Redis: cache.t3.micro single node

## Security

- All resources in private subnets
- VPC Flow Logs enabled
- Security groups with least privilege
- KMS encryption for data at rest
- IAM roles with OIDC (no long-term credentials)
- AWS WAF for ALB

## Cost Optimization

- Spot instances for non-critical workloads
- Reserved instances for baseline capacity
- Auto-scaling to match demand
- S3 lifecycle policies for logs
- Cost alerts at $500/month threshold

## Monitoring

- CloudWatch for infrastructure metrics
- Prometheus + Grafana for application metrics
- AWS CloudTrail for audit logs
- VPC Flow Logs for network analysis
