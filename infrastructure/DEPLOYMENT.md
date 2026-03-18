# PatchFlow Infrastructure - Deployment Guide

## Phase 1 Week 1-2: Infrastructure Foundation (COMPLETE)

### What Was Built

#### 1. Terraform Infrastructure (`infrastructure/terraform/`)

**VPC & Networking:**
- VPC with 3 AZs (us-east-1a, 1b, 1c)
- Public subnets (ALB, NAT)
- Private subnets (EKS, applications)
- Database subnets (RDS, ElastiCache)
- NAT Gateways, Internet Gateway
- VPC Flow Logs enabled

**EKS Cluster:**
- Kubernetes 1.29
- 3 node groups:
  - `general`: 3-10 t3.medium nodes (ON_DEMAND)
  - `spot`: 1-5 spot instances (cost optimization)
  - `gpu`: 0-3 g4dn.xlarge nodes (AI inference)
- Auto-scaling enabled
- IRSA (IAM Roles for Service Accounts)
- CoreDNS, kube-proxy, VPC CNI, EBS CSI addons

**Data Layer:**
- RDS PostgreSQL 16 (Multi-AZ in production)
- Read replica for production
- ElastiCache Redis (cluster mode)
- Automated backups (7-35 days retention)
- Encryption at rest & in transit

**Storage:**
- S3 bucket for application data
- S3 bucket for Terraform state
- DynamoDB table for state locking
- Versioning & lifecycle policies

**Security:**
- Security groups with least privilege
- KMS encryption
- IAM roles for EKS
- WAF ready (ACL ARNs in manifests)

#### 2. Kubernetes Manifests (`infrastructure/k8s/base/`)

**Namespaces:**
- `patchflow`: Main application
- `patchflow-agents`: AI agent workloads
- `patchflow-monitoring`: Observability

**Applications:**
- Backend deployment (3 replicas, HPA 3-10)
- Frontend deployment (3 replicas, HPA 3-10)
- Service accounts with IRSA
- Health checks (liveness/readiness)
- Resource limits & requests
- Pod anti-affinity for HA

**Networking:**
- ALB Ingress (external-facing)
- Internal ALB for agents
- SSL/TLS termination
- WAF integration

**Configuration:**
- ConfigMaps for app settings
- Secrets template (for AWS Secrets Manager integration)

#### 3. CI/CD Pipeline (`.github/workflows/ci-cd.yml`)

**Stages:**
1. **Test Backend**: pytest with PostgreSQL & Redis services
2. **Test Frontend**: npm build & test
3. **Security Scan**: Trivy vulnerability scan
4. **Build & Push**: Docker images to ECR
5. **Deploy Production**: kubectl apply to EKS

**Features:**
- Path filtering (skip for docs)
- Service containers for testing
- Multi-environment deployment
- Manual approval for production

#### 4. Bootstrap Script (`infrastructure/scripts/bootstrap.sh`)

Automates:
- S3 bucket creation for Terraform state
- DynamoDB table for state locking
- Terraform initialization
- terraform.tfvars generation
- SSH key generation

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         AWS CLOUD                          │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  VPC (10.0.0.0/16)                                  │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │ │
│  │  │  Public     │  │  Private    │  │  Database   │ │ │
│  │  │  (ALB)      │  │  (EKS pods) │  │  (RDS/Redis)│ │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘ │ │
│  └─────────────────────────────────────────────────────┘ │
│                          │                                 │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  EKS Cluster (K8s 1.29)                             │ │
│  │  • 3-10 general nodes (t3.medium)                  │ │
│  │  • 0-3 GPU nodes (g4dn.xlarge) for AI agents       │ │
│  │  • Spot instances for cost optimization            │ │
│  └─────────────────────────────────────────────────────┘ │
│                          │                                 │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  Data Layer                                        │ │
│  │  • RDS PostgreSQL 16 (Multi-AZ)                  │ │
│  │  • ElastiCache Redis (cluster)                     │ │
│  │  • S3 (artifacts, logs)                           │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Estimated Costs

| Component | Monthly Cost |
|-----------|--------------|
| EKS Control Plane | $73 |
| EC2 (3× t3.medium) | $200 |
| RDS (db.t3.medium Multi-AZ) | $150 |
| ElastiCache (t3.micro) | $30 |
| ALB | $25 |
| Data Transfer | $50 |
| **Total** | **~$500-600/month** |

### Next Steps (Phase 1 Week 2-3)

1. **Deploy Infrastructure:**
   ```bash
   cd infrastructure/terraform
   ./scripts/bootstrap.sh production
   terraform apply
   ```

2. **Configure kubectl:**
   ```bash
   aws eks update-kubeconfig --region us-east-1 --name patchflow-production
   ```

3. **Install Addons:**
   - AWS Load Balancer Controller
   - External DNS
   - Cert Manager
   - Prometheus & Grafana

4. **Deploy Applications:**
   ```bash
   kubectl apply -k infrastructure/k8s/overlays/production/
   ```

### Prerequisites

- AWS CLI configured
- Terraform >= 1.7.0
- kubectl
- Helm 3
- Domain registered (patchflow.ai)

### Security Notes

- All secrets stored in AWS Secrets Manager (not in Git)
- Database passwords auto-generated
- IAM roles use OIDC (no long-term credentials)
- VPC Flow Logs enabled
- Encryption at rest & in transit

### Compliance

- Ready for SOC2 Type II
- Ready for ISO 27001
- Audit logging enabled
- 7-year retention configured

---

**Status:** ✅ Phase 1 Week 1-2 Complete
**Next:** Phase 1 Week 2-3 (Add-ons & Application Deployment)
