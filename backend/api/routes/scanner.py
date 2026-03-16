"""Scan API routes for vulnerability scanning."""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from datetime import datetime
import structlog

from core.database import get_db
from models import User, Repository, ScanJob, Vulnerability
from api.routes.auth import get_current_user as get_current_user_from_token
from services.scanner_service import scan_orchestrator, Severity

logger = structlog.get_logger()
router = APIRouter(tags=["Vulnerability Scanning"])


@router.post("/repositories/{repo_id}/scan")
async def trigger_scan(
    repo_id: str,
    background_tasks: BackgroundTasks,
    branch: str = "main",
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """Manually trigger a vulnerability scan for a repository."""
    # Get repository
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id, Repository.owner_id == current_user.id)
    )
    repo = result.scalar_one_or_none()
    
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Create scan job
    scan_job = ScanJob(
        repository_id=repo_id,
        trigger_type="manual",
        branch=branch,
        scanners_used=["trivy"],
        status="queued"
    )
    db.add(scan_job)
    await db.commit()
    await db.refresh(scan_job)
    
    # Trigger scan in background
    background_tasks.add_task(
        run_scan_job,
        scan_job.id,
        repo.clone_url or repo.url,
        branch,
        current_user.github_token,
        db
    )
    
    logger.info("Scan triggered", job_id=scan_job.id, repo_id=repo_id, user_id=current_user.id)
    
    return {
        "status": "queued",
        "scan_job_id": scan_job.id,
        "repository": repo.full_name,
        "branch": branch
    }


@router.get("/repositories/{repo_id}/scans")
async def list_scans(
    repo_id: str,
    limit: int = 10,
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """List scan jobs for a repository."""
    # Verify ownership
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id, Repository.owner_id == current_user.id)
    )
    repo = result.scalar_one_or_none()
    
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Get scans
    result = await db.execute(
        select(ScanJob)
        .where(ScanJob.repository_id == repo_id)
        .order_by(desc(ScanJob.created_at))
        .limit(limit)
    )
    scans = result.scalars().all()
    
    return {
        "scans": [
            {
                "id": scan.id,
                "trigger_type": scan.trigger_type,
                "branch": scan.branch,
                "status": scan.status,
                "total_findings": scan.total_findings,
                "critical_count": scan.critical_count,
                "high_count": scan.high_count,
                "medium_count": scan.medium_count,
                "low_count": scan.low_count,
                "started_at": scan.started_at.isoformat() if scan.started_at else None,
                "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
                "created_at": scan.created_at.isoformat() if scan.created_at else None
            }
            for scan in scans
        ]
    }


@router.get("/scans/{scan_id}")
async def get_scan_details(
    scan_id: str,
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed scan results."""
    # Get scan with repository ownership check
    result = await db.execute(
        select(ScanJob, Repository)
        .join(Repository, ScanJob.repository_id == Repository.id)
        .where(ScanJob.id == scan_id, Repository.owner_id == current_user.id)
    )
    row = result.one_or_none()
    
    if not row:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    scan, repo = row
    
    # Get vulnerabilities
    result = await db.execute(
        select(Vulnerability)
        .where(Vulnerability.scan_job_id == scan_id)
        .order_by(Vulnerability.severity)
    )
    vulnerabilities = result.scalars().all()
    
    return {
        "scan": {
            "id": scan.id,
            "repository": repo.full_name,
            "trigger_type": scan.trigger_type,
            "branch": scan.branch,
            "status": scan.status,
            "scanners_used": scan.scanners_used,
            "total_findings": scan.total_findings,
            "critical_count": scan.critical_count,
            "high_count": scan.high_count,
            "medium_count": scan.medium_count,
            "low_count": scan.low_count,
            "error_message": scan.error_message,
            "started_at": scan.started_at.isoformat() if scan.started_at else None,
            "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        },
        "vulnerabilities": [
            {
                "id": vuln.id,
                "cve_id": vuln.cve_id,
                "cwe_id": vuln.cwe_id,
                "title": vuln.title,
                "description": vuln.description,
                "severity": vuln.severity,
                "package_name": vuln.package_name,
                "current_version": vuln.current_version,
                "fixed_version": vuln.fixed_version,
                "file_path": vuln.file_path,
                "status": vuln.status,
                "detected_at": vuln.detected_at.isoformat() if vuln.detected_at else None
            }
            for vuln in vulnerabilities
        ]
    }


@router.get("/repositories/{repo_id}/vulnerabilities")
async def list_vulnerabilities(
    repo_id: str,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """List vulnerabilities for a repository."""
    # Verify ownership
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id, Repository.owner_id == current_user.id)
    )
    repo = result.scalar_one_or_none()
    
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Build query
    query = select(Vulnerability).where(Vulnerability.repository_id == repo_id)
    
    if severity:
        query = query.where(Vulnerability.severity == severity.lower())
    if status:
        query = query.where(Vulnerability.status == status.lower())
    
    query = query.order_by(Vulnerability.severity).limit(limit)
    
    result = await db.execute(query)
    vulnerabilities = result.scalars().all()
    
    return {
        "repository": repo.full_name,
        "vulnerabilities": [
            {
                "id": vuln.id,
                "cve_id": vuln.cve_id,
                "title": vuln.title,
                "severity": vuln.severity,
                "package_name": vuln.package_name,
                "current_version": vuln.current_version,
                "fixed_version": vuln.fixed_version,
                "status": vuln.status,
                "detected_at": vuln.detected_at.isoformat() if vuln.detected_at else None
            }
            for vuln in vulnerabilities
        ],
        "total": len(vulnerabilities)
    }


async def run_scan_job(
    scan_job_id: str,
    repo_url: str,
    branch: str,
    github_token: Optional[str],
    db: AsyncSession
):
    """Execute a scan job in the background."""
    # Create new session for async operation
    from core.database import async_session_maker
    
    async with async_session_maker() as session:
        try:
            # Update job status
            result = await session.execute(
                select(ScanJob).where(ScanJob.id == scan_job_id)
            )
            scan_job = result.scalar_one()
            
            scan_job.status = "running"
            scan_job.started_at = datetime.utcnow()
            await session.commit()
            
            logger.info("Starting scan job", job_id=scan_job_id)
            
            # Run scanners
            if github_token:
                scan_orchestrator.enable_github_advisory(github_token)
            
            results = await scan_orchestrator.scan_repository(
                repo_url=repo_url,
                branch=branch,
                github_token=github_token
            )
            
            # Aggregate findings
            all_findings = scan_orchestrator.aggregate_findings(results)
            
            # Update scan job with results
            scan_job.status = "completed"
            scan_job.completed_at = datetime.utcnow()
            scan_job.total_findings = len(all_findings)
            scan_job.critical_count = sum(1 for f in all_findings if f.severity == Severity.CRITICAL)
            scan_job.high_count = sum(1 for f in all_findings if f.severity == Severity.HIGH)
            scan_job.medium_count = sum(1 for f in all_findings if f.severity == Severity.MEDIUM)
            scan_job.low_count = sum(1 for f in all_findings if f.severity == Severity.LOW)
            
            # Store findings as vulnerabilities
            for finding in all_findings:
                vuln = Vulnerability(
                    repository_id=scan_job.repository_id,
                    scan_job_id=scan_job_id,
                    cve_id=finding.cve_id,
                    title=finding.title,
                    description=finding.description,
                    severity=finding.severity.value,
                    package_name=finding.package_name,
                    current_version=finding.installed_version,
                    fixed_version=finding.fixed_version,
                    file_path=finding.file_path,
                    status="open"
                )
                session.add(vuln)
            
            await session.commit()
            
            logger.info(
                "Scan job completed",
                job_id=scan_job_id,
                findings=len(all_findings),
                critical=scan_job.critical_count,
                high=scan_job.high_count
            )
            
        except Exception as e:
            logger.error("Scan job failed", job_id=scan_job_id, error=str(e))
            
            result = await session.execute(
                select(ScanJob).where(ScanJob.id == scan_job_id)
            )
            scan_job = result.scalar_one()
            
            scan_job.status = "failed"
            scan_job.completed_at = datetime.utcnow()
            scan_job.error_message = str(e)
            await session.commit()
