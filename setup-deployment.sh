#!/bin/bash
# PatchFlow Automated Deployment Setup Script
# This script sets up Neon DB, Render, and Vercel deployments

echo "========================================="
echo "PatchFlow Deployment Setup"
echo "========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Step 1: Neon Database Setup${NC}"
echo "------------------------------"

# Check if neonctl is installed
if ! command -v neonctl &> /dev/null; then
    echo "Installing Neon CLI..."
    npm install -g neonctl
fi

# Authenticate with Neon
echo "Authenticating with Neon..."
neonctl auth

echo ""
echo -e "${YELLOW}Creating Neon Project...${NC}"
neonctl projects create --name patchflow --region aws-ap-southeast-1

echo ""
echo -e "${YELLOW}Creating Database...${NC}"
neonctl databases create --project-id $(neonctl projects list --output json | jq -r '.[0].id') --name patchflow

echo ""
echo -e "${GREEN}Neon database created!${NC}"
echo "Getting connection string..."
neonctl connection-string --project-id $(neonctl projects list --output json | jq -r '.[0].id') --database-name patchflow --role-name neon --output json

echo ""
echo "========================================="
echo -e "${YELLOW}Step 2: Render.com Setup${NC}"
echo "========================================="
echo ""
echo "Render.com uses Blueprint deployment."
echo "1. Go to: https://dashboard.render.com/"
echo "2. Click 'New' -> 'Blueprint'"
echo "3. Connect your GitHub repo"
echo "4. The render.yaml file in your repo will auto-configure everything"
echo ""
echo "Environment variables to add in Render dashboard:"
echo "- CLERK_PUBLISHABLE_KEY"
echo "- CLERK_SECRET_KEY"
echo "- CLERK_WEBHOOK_SECRET"
echo "- STRIPE_SECRET_KEY"
echo "- STRIPE_WEBHOOK_SECRET"
echo "- GITHUB_CLIENT_ID"
echo "- GITHUB_CLIENT_SECRET"
echo "- OPENAI_API_KEY"
echo "- ANTHROPIC_API_KEY"
echo ""

echo "========================================="
echo -e "${YELLOW}Step 3: Vercel Frontend Setup${NC}"
echo "========================================="
echo ""

# Check if vercel is installed
if ! command -v vercel &> /dev/null; then
    echo "Installing Vercel CLI..."
    npm install -g vercel
fi

# Authenticate with Vercel
echo "Authenticating with Vercel..."
vercel login

echo ""
echo "Deploying frontend..."
cd frontend
vercel --prod

echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}Setup Complete!${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Add environment variables in Render dashboard"
echo "2. Update Stripe webhook URL to: https://your-backend.onrender.com/webhooks/stripe"
echo "3. Update Clerk webhook URL to: https://your-backend.onrender.com/webhooks/clerk"
echo "4. Update GitHub OAuth callback to: https://your-backend.onrender.com/auth/github/callback"
echo ""
echo "Your app should be live soon!"
