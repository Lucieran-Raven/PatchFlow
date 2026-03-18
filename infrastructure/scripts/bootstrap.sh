#!/bin/bash
# =============================================================================
# PatchFlow Infrastructure Bootstrap Script
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}  PatchFlow Infrastructure Bootstrap${NC}"
echo -e "${GREEN}==========================================${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v terraform &> /dev/null; then
    echo -e "${RED}Error: Terraform is not installed${NC}"
    exit 1
fi

if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl is not installed${NC}"
    exit 1
fi

if ! command -v helm &> /dev/null; then
    echo -e "${RED}Error: Helm is not installed${NC}"
    exit 1
fi

echo -e "${GREEN}✓ All prerequisites met${NC}"
echo ""

# Get environment
ENVIRONMENT=${1:-production}
if [[ ! "$ENVIRONMENT" =~ ^(production|staging|development)$ ]]; then
    echo -e "${RED}Error: Environment must be production, staging, or development${NC}"
    exit 1
fi

echo -e "${YELLOW}Bootstrapping environment: $ENVIRONMENT${NC}"
echo ""

# Create S3 bucket for Terraform state if it doesn't exist
echo -e "${YELLOW}Setting up Terraform state backend...${NC}"
aws s3api head-bucket --bucket patchflow-terraform-state 2>/dev/null || {
    echo "Creating S3 bucket for Terraform state..."
    aws s3 mb s3://patchflow-terraform-state --region us-east-1
    aws s3api put-bucket-versioning \
        --bucket patchflow-terraform-state \
        --versioning-configuration Status=Enabled
    aws s3api put-bucket-encryption \
        --bucket patchflow-terraform-state \
        --server-side-encryption-configuration '{
            "Rules": [{
                "ApplyServerSideEncryptionByDefault": {
                    "SSEAlgorithm": "AES256"
                }
            }]
        }'
}

# Create DynamoDB table for state locking
echo "Creating DynamoDB table for state locking..."
aws dynamodb describe-table --table-name patchflow-terraform-locks &>/dev/null || {
    aws dynamodb create-table \
        --table-name patchflow-terraform-locks \
        --attribute-definitions AttributeName=LockID,AttributeType=S \
        --key-schema AttributeName=LockID,KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --region us-east-1
}

echo -e "${GREEN}✓ Terraform backend configured${NC}"
echo ""

# Generate SSH key if needed
if [ ! -f ~/.ssh/patchflow_eks_key.pem ]; then
    echo -e "${YELLOW}Generating SSH key for EKS nodes...${NC}"
    ssh-keygen -t rsa -b 4096 -f ~/.ssh/patchflow_eks_key.pem -N ""
    chmod 400 ~/.ssh/patchflow_eks_key.pem
    echo -e "${GREEN}✓ SSH key generated${NC}"
fi

# Change to terraform directory
cd infrastructure/terraform

# Generate terraform.tfvars
echo -e "${YELLOW}Generating terraform.tfvars...${NC}"

cat > terraform.tfvars << EOF
environment = "$ENVIRONMENT"
aws_region = "us-east-1"

# Database password (generate a strong one)
database_password = "$(openssl rand -base64 32 | tr -d '=+/')"

# Domain
domain_name = "patchflow.ai"

# EKS configuration
cluster_version = "1.29"
node_min_size = 3
node_max_size = 10
node_desired_size = 3
enable_gpu_nodes = true

# Instance types
node_instance_types = ["t3.medium"]
gpu_instance_types = ["g4dn.xlarge"]

# Database
database_instance_class = "db.t3.medium"
redis_node_type = "cache.t3.micro"

# Security
enable_waf = true
enable_vpc_flow_logs = true
EOF

echo -e "${GREEN}✓ terraform.tfvars created${NC}"
echo ""

# Initialize Terraform
echo -e "${YELLOW}Initializing Terraform...${NC}"
terraform init

echo -e "${GREEN}✓ Terraform initialized${NC}"
echo ""

# Plan
echo -e "${YELLOW}Planning infrastructure changes...${NC}"
terraform plan -var-file=terraform.tfvars -out=tfplan

echo ""
echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}  Bootstrap Complete!${NC}"
echo -e "${GREEN}==========================================${NC}"
echo ""
echo -e "Next steps:"
echo -e "  1. Review the plan: ${YELLOW}terraform show tfplan${NC}"
echo -e "  2. Apply changes:  ${YELLOW}terraform apply tfplan${NC}"
echo -e "  3. Configure kubectl: ${YELLOW}aws eks update-kubeconfig --region us-east-1 --name patchflow-$ENVIRONMENT${NC}"
echo ""
echo -e "${YELLOW}WARNING: This will create AWS resources that may incur costs.${NC}"
echo -e "Estimated monthly cost: $200-500 (depending on usage)"
echo ""
