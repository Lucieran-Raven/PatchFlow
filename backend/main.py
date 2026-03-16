from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import structlog

from core.config import settings
from api.routes import auth, health, repositories, vulnerabilities, agents, github
from core.database import init_db

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
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(github.router, prefix="/auth/github", tags=["GitHub Integration"])
app.include_router(repositories.router, prefix="/repositories", tags=["Repositories"])
app.include_router(vulnerabilities.router, prefix="/vulnerabilities", tags=["Vulnerabilities"])
app.include_router(agents.router, prefix="/agents", tags=["Agents"])

@app.get("/")
async def root():
    return {
        "name": "PatchFlow API",
        "version": "0.1.0",
        "status": "operational",
        "docs": "/docs"
    }
