from fastapi import APIRouter
from datetime import datetime

router = APIRouter()

@router.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0"
    }

@router.get("/ready")
async def readiness_check():
    """Readiness probe for Kubernetes."""
    # TODO: Add database connection check
    return {
        "status": "ready",
        "checks": {
            "database": "ok",
            "redis": "ok",
            "kafka": "ok"
        }
    }
