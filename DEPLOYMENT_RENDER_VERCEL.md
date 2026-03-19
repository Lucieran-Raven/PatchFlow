# PatchFlow Deployment Guide

## Overview
This guide walks through deploying PatchFlow using Render.com (backend + database + Redis) and Vercel (frontend).

**Estimated Cost:** $0-20/month (Free tier available)
**Setup Time:** ~30 minutes

---

## Step 1: Deploy Backend to Render.com

### 1.1 Create Render Account
1. Go to https://render.com
2. Sign up with GitHub
3. Connect your `Lucieran-Raven/PatchFlow` repository

### 1.2 Create Blueprint Instance
1. In Render Dashboard, click **"New"** → **"Blueprint"**
2. Select your GitHub repo: `PatchFlow`
3. Render will read `render.yaml` and create:
   - **patchflow-backend** (Web Service)
   - **patchflow-db** (PostgreSQL Database)
   - **patchflow-redis** (Redis Cache)
   - **patchflow-worker** (Background Worker)
4. Click **"Apply"**

### 1.3 Add Environment Variables (Required)
Go to each service → **Environment** tab:

**patchflow-backend:**
```
CLERK_PUBLISHABLE_KEY=pk_test_cHJvbXB0LXRhcnBvbi0zMC5jbGVyay5hY2NvdW50cy5kZXYk
CLERK_SECRET_KEY=sk_test_LGGUwEkDTd9q839VKEzg0pk1gOvKwJ8uSYMrAiJ8yq
CLERK_WEBHOOK_SECRET=whsec_WdrniNLxFaM9BB/Qzp1+RCu09ZR0gpnZ
STRIPE_SECRET_KEY=sk_test_your_stripe_secret_key
STRIPE_WEBHOOK_SECRET=whsec_wqG1PNs4nx8LzruEq8F0fRWOwM7ml2YO
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
```

### 1.4 Update Stripe Webhook URL
1. Go to Stripe Dashboard → Webhooks
2. Edit your endpoint: `https://patchflow-backend.onrender.com/webhooks/stripe`
3. (URL will be: `https://patchflow-backend.onrender.com/webhooks/stripe`)

---

## Step 2: Deploy Frontend to Vercel

### 2.1 Create Vercel Account
1. Go to https://vercel.com
2. Sign up with GitHub
3. Click **"Add New Project"**

### 2.2 Import Repository
1. Select `Lucieran-Raven/PatchFlow`
2. **Framework Preset:** Next.js
3. **Root Directory:** `frontend`
4. Click **"Deploy"**

### 2.3 Add Environment Variables
Go to Project Settings → **Environment Variables**:

```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_cHJvbXB0LXRhcnBvbi0zMC5jbGVyay5hY2NvdW50cy5kZXYk
NEXT_PUBLIC_API_URL=https://patchflow-backend.onrender.com
```

### 2.4 Redeploy
After adding env vars, Vercel will automatically redeploy.

---

## Step 3: Update CORS (Backend)

Once deployed, update Render backend environment variable:
```
CORS_ORIGINS=https://your-frontend.vercel.app
```
Replace with your actual Vercel URL (e.g., `https://patchflow-xyz.vercel.app`)

---

## Step 4: Update Clerk Webhook URL

1. Go to Clerk Dashboard → Webhooks
2. Edit endpoint URL to: `https://patchflow-backend.onrender.com/webhooks/clerk`

---

## Step 5: Update GitHub OAuth Callback

1. Go to GitHub → Settings → Developer Settings → OAuth Apps
2. Update **Authorization callback URL** to:
   `https://patchflow-backend.onrender.com/auth/github/callback`

---

## Verification

### Health Checks
- Backend Health: `https://patchflow-backend.onrender.com/health/live`
- API Docs: `https://patchflow-backend.onrender.com/docs`
- Frontend: `https://your-app.vercel.app`

### Test Flow
1. Sign up via Clerk on frontend
2. Connect GitHub repository
3. Trigger a scan
4. Verify Stripe payment flow

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Database connection failed | Check `DATABASE_URL` in Render env vars |
| CORS errors | Update `CORS_ORIGINS` with exact Vercel URL |
| Webhooks not working | Verify webhook URLs in Stripe/Clerk dashboards |
| Build fails | Check build logs in Render/Vercel dashboards |

---

## Free Tier Limits

| Service | Free Tier | Upgrade When |
|---------|-----------|--------------|
| Render Web Service | 512 MB RAM, sleeps after 15 min idle | Consistent traffic |
| Render PostgreSQL | 1 GB storage, 10 connections | Data grows > 500MB |
| Render Redis | 25 MB | Cache needs > 25MB |
| Vercel | 100 GB bandwidth, 6000 build minutes | High traffic |

**Estimated Monthly Cost at Scale:**
- 0-100 users: **$0/month**
- 100-1000 users: **$7-20/month**
- 1000+ users: Consider AWS migration
