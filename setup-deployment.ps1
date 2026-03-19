# PatchFlow Deployment Setup Script for Windows
# Run this script to set up Neon DB, Render, and Vercel deployments

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "PatchFlow Deployment Setup" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check and Install CLIs
Write-Host "Step 1: Checking CLI installations..." -ForegroundColor Yellow
Write-Host "----------------------------------------------"

# Check Neon CLI
if (!(Get-Command neonctl -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Neon CLI..." -ForegroundColor Green
    npm install -g neonctl
} else {
    Write-Host "Neon CLI already installed" -ForegroundColor Green
}

# Check Vercel CLI  
if (!(Get-Command vercel -ErrorAction SilentlyContinue)) {
    Write-Host "Installing Vercel CLI..." -ForegroundColor Green
    npm install -g vercel
} else {
    Write-Host "Vercel CLI already installed" -ForegroundColor Green
}

Write-Host ""
Write-Host "Step 2: Neon Database Setup" -ForegroundColor Yellow
Write-Host "----------------------------------------------"
Write-Host "Please authenticate with Neon (browser will open)..."
neonctl auth

Write-Host ""
Write-Host "Creating Neon project..." -ForegroundColor Green
$projectOutput = neonctl projects create --name patchflow --region aws-ap-southeast-1 --output json 2>&1
Write-Host $projectOutput

Write-Host ""
Write-Host "Step 3: Vercel Setup" -ForegroundColor Yellow
Write-Host "----------------------------------------------"
Write-Host "Please authenticate with Vercel (browser will open)..."
vercel login

Write-Host ""
Write-Host "Step 4: Configuration Files Created" -ForegroundColor Green
Write-Host "----------------------------------------------"
Write-Host "The following files have been created:"
Write-Host "  - render.yaml (Render.com configuration)"
Write-Host "  - vercel.json (Vercel configuration)"
Write-Host "  - DEPLOYMENT_RENDER_VERCEL.md (Full guide)"
Write-Host ""

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "Manual Steps Required:" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Go to https://dashboard.render.com/" -ForegroundColor White
Write-Host "   - Click 'New' -> 'Blueprint'" -ForegroundColor White
Write-Host "   - Select your PatchFlow repository" -ForegroundColor White
Write-Host "   - Render will use render.yaml to create services" -ForegroundColor White
Write-Host ""
Write-Host "2. Add these environment variables in Render dashboard:" -ForegroundColor Yellow
Write-Host "   CLERK_PUBLISHABLE_KEY=pk_test_cHJvbXB0LXRhcnBvbi0zMC5jbGVyay5hY2NvdW50cy5kZXYk"
Write-Host "   CLERK_SECRET_KEY=sk_test_LGGUwEkDTd9q839VKEzg0pk1gOvKwJ8uSYMrAiJ8yq"
Write-Host "   CLERK_WEBHOOK_SECRET=whsec_WdrniNLxFaM9BB/Qzp1+RCu09ZR0gpnZ"
Write-Host "   STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key"
Write-Host "   STRIPE_WEBHOOK_SECRET=whsec_wqG1PNs4nx8LzruEq8F0fRWOwM7ml2YO"
Write-Host "   GITHUB_CLIENT_ID=your_github_client_id"
Write-Host "   GITHUB_CLIENT_SECRET=your_github_client_secret"
Write-Host "   OPENAI_API_KEY=your_openai_key"
Write-Host "   ANTHROPIC_API_KEY=your_anthropic_key"
Write-Host ""
Write-Host "3. Go to https://vercel.com/" -ForegroundColor White
Write-Host "   - Import your PatchFlow repository" -ForegroundColor White
Write-Host "   - Set root directory to 'frontend'" -ForegroundColor White
Write-Host "   - Add environment variables:" -ForegroundColor Yellow
Write-Host "     NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_cHJvbXB0LXRhcnBvbi0zMC5jbGVyay5hY2NvdW50cy5kZXYk"
Write-Host "     NEXT_PUBLIC_API_URL=https://your-backend-url.onrender.com"
Write-Host ""
Write-Host "4. Update webhook URLs:" -ForegroundColor Yellow
Write-Host "   - Stripe: https://your-backend.onrender.com/webhooks/stripe"
Write-Host "   - Clerk: https://your-backend.onrender.com/webhooks/clerk"
Write-Host "   - GitHub OAuth: https://your-backend.onrender.com/auth/github/callback"
Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host "Setup files ready! Follow the manual steps above." -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
