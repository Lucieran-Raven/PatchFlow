"""Health check endpoints for monitoring and Docker orchestration.

Provides:
- Liveness probe: Is the app running?
- Readiness probe: Is the app ready to accept traffic?
- Health details: Database, scanner, agent status
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from typing import Dict, Any, List
from datetime import datetime
import structlog

from core.database import get_db
from agents.base_agent import agent_orchestrator, AgentRegistry
from services.scanner_service import scan_orchestrator

logger = structlog.get_logger()
router = APIRouter(tags=["Health"])


class HealthStatus(BaseModel):
    """Health check response model."""
    status: str
    timestamp: str
    version: str = "0.1.0"
    checks: Dict[str, Any]


class ComponentStatus(BaseModel):
    """Individual component health status."""
    status: str  # healthy, degraded, unhealthy
    response_time_ms: float
    details: Dict[str, Any] = {}
    error: str | None = None


async def check_database_health(db: AsyncSession) -> ComponentStatus:
    """Check database connectivity."""
    import time
    start = time.time()
    
    try:
        result = await db.execute(text("SELECT 1"))
        await result.scalar_one()
        
        response_time = (time.time() - start) * 1000
        
        return ComponentStatus(
            status="healthy",
            response_time_ms=round(response_time, 2),
            details={"type": "sqlite", "connection": "established"}
        )
    except Exception as e:
        response_time = (time.time() - start) * 1000
        logger.error("Database health check failed", error=str(e))
        
        return ComponentStatus(
            status="unhealthy",
            response_time_ms=round(response_time, 2),
            error=str(e)
        )


async def check_agents_health() -> ComponentStatus:
    """Check AI agent orchestrator status."""
    import time
    start = time.time()
    
    try:
        stats = agent_orchestrator.get_stats()
        registered = AgentRegistry.list_agents()
        
        response_time = (time.time() - start) * 1000
        
        return ComponentStatus(
            status="healthy",
            response_time_ms=round(response_time, 2),
            details={
                "registered_agents": registered,
                "queue_size": stats.get("queue_size", 0),
                "running_tasks": stats.get("running_tasks", 0),
                "completed_tasks": stats.get("completed_tasks", 0)
            }
        )
    except Exception as e:
        response_time = (time.time() - start) * 1000
        logger.error("Agents health check failed", error=str(e))
        
        return ComponentStatus(
            status="degraded",
            response_time_ms=round(response_time, 2),
            error=str(e),
            details={"agents_available": False}
        )


async def check_scanner_health() -> ComponentStatus:
    """Check vulnerability scanner status."""
    import time
    start = time.time()
    
    try:
        scanner_count = len(scan_orchestrator.scanners)
        
        response_time = (time.time() - start) * 1000
        
        return ComponentStatus(
            status="healthy",
            response_time_ms=round(response_time, 2),
            details={
                "scanners_registered": scanner_count,
                "orchestrator_ready": True
            }
        )
    except Exception as e:
        response_time = (time.time() - start) * 1000
        logger.error("Scanner health check failed", error=str(e))
        
        return ComponentStatus(
            status="degraded",
            response_time_ms=round(response_time, 2),
            error=str(e)
        )


@router.get("/health/live")
async def liveness_probe():
    """Liveness probe - is the application running?
    
    Kubernetes/Docker uses this to know if container should be restarted.
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/health/ready")
async def readiness_probe(db: AsyncSession = Depends(get_db)):
    """Readiness probe - is the application ready to accept traffic?
    
    Kubernetes uses this to know if container should receive requests.
    """
    checks = {
        "database": await check_database_health(db),
        "agents": await check_agents_health(),
        "scanner": await check_scanner_health()
    }
    
    # Determine overall status
    unhealthy_count = sum(1 for c in checks.values() if c.status == "unhealthy")
    degraded_count = sum(1 for c in checks.values() if c.status == "degraded")
    
    if unhealthy_count > 0:
        status = "not_ready"
        http_status = 503
    elif degraded_count > 0:
        status = "ready_with_warnings"
        http_status = 200
    else:
        status = "ready"
        http_status = 200
    
    response = {
        "status": status,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            name: {
                "status": check.status,
                "response_time_ms": check.response_time_ms,
                "details": check.details,
                **({"error": check.error} if check.error else {})
            }
            for name, check in checks.items()
        }
    }
    
    if http_status == 503:
        raise HTTPException(status_code=503, detail=response)
    
    return response


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Comprehensive health check with all components.
    
    Returns detailed health information for monitoring and debugging.
    """
    checks = {
        "database": await check_database_health(db),
        "agents": await check_agents_health(),
        "scanner": await check_scanner_health()
    }
    
    # Calculate overall health score
    unhealthy_count = sum(1 for c in checks.values() if c.status == "unhealthy")
    degraded_count = sum(1 for c in checks.values() if c.status == "degraded")
    
    if unhealthy_count > 0:
        overall_status = "unhealthy"
    elif degraded_count > 0:
        overall_status = "degraded"
    else:
        overall_status = "healthy"
    
    # Calculate total response time
    total_response_time = sum(c.response_time_ms for c in checks.values())
    
    return HealthStatus(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat(),
        checks={
            name: {
                "status": check.status,
                "response_time_ms": check.response_time_ms,
                "details": check.details,
                **({"error": check.error} if check.error else {})
            }
            for name, check in checks.items()
        }
    )


@router.get("/health/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_db)):
    """Detailed health check with system information.
    
    Includes additional metrics useful for debugging and capacity planning.
    """
    import psutil
    import platform
    
    # Get system metrics
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Get health checks
    health = await health_check(db)
    
    return {
        **health.model_dump(),
        "system": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu": {
                "percent": cpu_percent,
                "count": psutil.cpu_count()
            },
            "memory": {
                "total_mb": round(memory.total / (1024 * 1024), 2),
                "available_mb": round(memory.available / (1024 * 1024), 2),
                "percent": memory.percent
            },
            "disk": {
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "percent": disk.percent
            }
        }
    }
