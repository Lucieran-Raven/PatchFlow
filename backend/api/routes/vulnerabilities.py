from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from uuid import UUID

from core.database import get_db
from models import Vulnerability, Repository

router = APIRouter()

class VulnerabilityResponse(BaseModel):
    id: str
    repository_id: str
    cve_id: Optional[str]
    cwe_id: Optional[str]
    title: str
    description: Optional[str]
    severity: str
    confidence_score: Optional[int]
    status: str
    file_path: Optional[str]
    package_name: Optional[str]
    current_version: Optional[str]
    fixed_version: Optional[str]
    detected_at: str
    fixed_at: Optional[str]

    class Config:
        from_attributes = True

class VulnerabilityStats(BaseModel):
    total: int
    open: int
    critical: int
    high: int
    medium: int
    low: int
    fixed_this_month: int
    avg_remediation_time_hours: float

@router.get("/", response_model=List[VulnerabilityResponse])
async def list_vulnerabilities(
    repository_id: Optional[UUID] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """List vulnerabilities with optional filters."""
    query = select(Vulnerability).order_by(desc(Vulnerability.detected_at))
    
    if repository_id:
        query = query.where(Vulnerability.repository_id == repository_id)
    if severity:
        query = query.where(Vulnerability.severity == severity)
    if status:
        query = query.where(Vulnerability.status == status)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    vulnerabilities = result.scalars().all()
    return vulnerabilities

@router.get("/stats", response_model=VulnerabilityStats)
async def get_vulnerability_stats(db: AsyncSession = Depends(get_db)):
    """Get vulnerability statistics."""
    # Total vulnerabilities
    total_result = await db.execute(select(func.count(Vulnerability.id)))
    total = total_result.scalar()
    
    # Open vulnerabilities
    open_result = await db.execute(
        select(func.count(Vulnerability.id)).where(Vulnerability.status == "open")
    )
    open_count = open_result.scalar()
    
    # By severity
    critical_result = await db.execute(
        select(func.count(Vulnerability.id)).where(Vulnerability.severity == "critical")
    )
    critical = critical_result.scalar()
    
    high_result = await db.execute(
        select(func.count(Vulnerability.id)).where(Vulnerability.severity == "high")
    )
    high = high_result.scalar()
    
    medium_result = await db.execute(
        select(func.count(Vulnerability.id)).where(Vulnerability.severity == "medium")
    )
    medium = medium_result.scalar()
    
    low_result = await db.execute(
        select(func.count(Vulnerability.id)).where(Vulnerability.severity == "low")
    )
    low = low_result.scalar()
    
    return VulnerabilityStats(
        total=total,
        open=open_count,
        critical=critical,
        high=high,
        medium=medium,
        low=low,
        fixed_this_month=0,  # TODO: Calculate
        avg_remediation_time_hours=0.0  # TODO: Calculate
    )

@router.get("/{vuln_id}", response_model=VulnerabilityResponse)
async def get_vulnerability(vuln_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get a specific vulnerability."""
    result = await db.execute(select(Vulnerability).where(Vulnerability.id == vuln_id))
    vuln = result.scalar_one_or_none()
    if not vuln:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    return vuln

@router.post("/{vuln_id}/fix")
async def trigger_fix(vuln_id: UUID, db: AsyncSession = Depends(get_db)):
    """Trigger AI fix generation for a vulnerability."""
    result = await db.execute(select(Vulnerability).where(Vulnerability.id == vuln_id))
    vuln = result.scalar_one_or_none()
    if not vuln:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    
    # TODO: Trigger fix via Code Fix Agent
    return {
        "message": "Fix generation triggered",
        "vulnerability_id": str(vuln_id),
        "status": "queued",
        "estimated_completion": "5-30 seconds"
    }

@router.post("/{vuln_id}/ignore")
async def ignore_vulnerability(
    vuln_id: UUID,
    reason: str,
    db: AsyncSession = Depends(get_db)
):
    """Mark a vulnerability as false positive or ignored."""
    result = await db.execute(select(Vulnerability).where(Vulnerability.id == vuln_id))
    vuln = result.scalar_one_or_none()
    if not vuln:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    
    vuln.status = "false_positive"
    await db.commit()
    
    return {
        "message": "Vulnerability marked as false positive",
        "vulnerability_id": str(vuln_id),
        "reason": reason
    }
