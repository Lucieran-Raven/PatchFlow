from fastapi import FastAPI, HTTPException, Depends
from contextlib import asynccontextmanager
import structlog

from core.config import settings
from api.routes import auth, health, repositories, vulnerabilities, agents, github, webhooks, scanner, pr_automation, dashboard
from api.routes.webhooks_clerk import router as clerk_webhook_router
from core.database import init_db
from core.security_middleware import add_security_middleware

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting up PatchFlow API...")
    await init_db()
    yield
    logger.info("Shutting down PatchFlow API...")

app = FastAPI(
    title="PatchFlow API",
    description="Autonomous AI Security Remediation Platform",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if not (settings.ENVIRONMENT == "production" and not settings.DOCKER_ENV) else None,
    redoc_url="/redoc" if not (settings.ENVIRONMENT == "production" and not settings.DOCKER_ENV) else None,
)

# Add comprehensive security middleware
add_security_middleware(app)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(clerk_webhook_router, prefix="/webhooks/clerk", tags=["Clerk Webhooks"])
app.include_router(github.router, prefix="/auth/github", tags=["GitHub Integration"])
app.include_router(webhooks.router, prefix="/webhooks/github", tags=["GitHub Webhooks"])
app.include_router(scanner.router, prefix="/scanner", tags=["Vulnerability Scanning"])
app.include_router(repositories.router, prefix="/repositories", tags=["Repositories"])
app.include_router(vulnerabilities.router, prefix="/vulnerabilities", tags=["Vulnerabilities"])
app.include_router(agents.router, prefix="/agents", tags=["Agents"])
app.include_router(pr_automation.router, prefix="/pr", tags=["PR Automation"])
app.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])

# Stripe routes (Phase 1 Week 3-4)
from api.routes import stripe as stripe_router
app.include_router(stripe_router.router, prefix="/stripe", tags=["Payments"])

@app.get("/")
async def root():
    return {
        "name": "PatchFlow API",
        "version": "0.1.0",
        "status": "operational",
        "docs": "/docs"
    }
