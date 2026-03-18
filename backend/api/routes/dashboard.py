"""Dashboard API routes for PatchFlow analytics.

Provides endpoints for:
- Overview statistics
- Vulnerability trends
- Repository health
- Fix/PR metrics
- Severity distributions
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from typing import Optional, List
from datetime import datetime, timedelta
from pydantic import BaseModel
import structlog

from core.database import get_db
from models import User, Vulnerability, Repository, ScanJob
from api.routes.auth import get_current_user as get_current_user_from_token

logger = structlog.get_logger()
router = APIRouter(tags=["Dashboard"])


class DashboardStats(BaseModel):
    """Dashboard overview statistics."""
    total_vulnerabilities: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    fixed_count: int
    open_count: int
    prs_created: int
    prs_merged: int
    total_repositories: int
    scanned_repositories: int
    total_scans: int
    scans_this_week: int


class TrendData(BaseModel):
    """Trend data point."""
    date: str
    count: int
    severity: Optional[str] = None


class RepositoryHealth(BaseModel):
    """Repository health metrics."""
    repository_id: str
    repository_name: str
    total_vulns: int
    critical_vulns: int
    high_vulns: int
    last_scan_at: Optional[str]
    health_score: float  # 0-100
    fix_rate: float  # percentage


class SeverityDistribution(BaseModel):
    """Severity distribution data."""
    severity: str
    count: int
    percentage: float


class FixMetrics(BaseModel):
    """Fix automation metrics."""
    total_fixes_generated: int
    fixes_by_cwe: List[dict]
    average_fix_confidence: float
    prs_created: int
    prs_merged: int
    merge_rate: float


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard overview statistics."""
    
    # Count vulnerabilities by severity
    severity_counts = await db.execute(
        select(
            Vulnerability.severity,
            func.count(Vulnerability.id).label("count")
        )
        .join(Repository, Vulnerability.repository_id == Repository.id)
        .where(Repository.owner_id == current_user.id)
        .group_by(Vulnerability.severity)
    )
    severity_data = {row.severity: row.count for row in severity_counts.all()}
    
    # Count by status
    status_counts = await db.execute(
        select(
            Vulnerability.status,
            func.count(Vulnerability.id).label("count")
        )
        .join(Repository, Vulnerability.repository_id == Repository.id)
        .where(Repository.owner_id == current_user.id)
        .group_by(Vulnerability.status)
    )
    status_data = {row.status: row.count for row in status_counts.all()}
    
    # PR counts
    pr_counts = await db.execute(
        select(
            func.count(Vulnerability.id).label("total_prs"),
            func.sum(func.case([(Vulnerability.status == "fixed"), 1], else_=0)).label("merged_prs")
        )
        .join(Repository, Vulnerability.repository_id == Repository.id)
        .where(
            Repository.owner_id == current_user.id,
            Vulnerability.pr_url.isnot(None)
        )
    )
    pr_row = pr_counts.one()
    
    # Repository counts
    repo_counts = await db.execute(
        select(
            func.count(Repository.id).label("total"),
            func.sum(func.case([(Repository.last_scan_at.isnot(None)), 1], else_=0)).label("scanned")
        )
        .where(Repository.owner_id == current_user.id)
    )
    repo_row = repo_counts.one()
    
    # Scans this week
    week_ago = datetime.utcnow() - timedelta(days=7)
    scans_week = await db.execute(
        select(func.count(ScanJob.id))
        .join(Repository, ScanJob.repository_id == Repository.id)
        .where(Repository.owner_id == current_user.id, ScanJob.created_at >= week_ago)
    )
    scans_this_week = scans_week.scalar() or 0
    
    return DashboardStats(
        total_vulnerabilities=sum(severity_data.values()),
        critical_count=severity_data.get("critical", 0),
        high_count=severity_data.get("high", 0),
        medium_count=severity_data.get("medium", 0),
        low_count=severity_data.get("low", 0),
        fixed_count=status_data.get("fixed", 0),
        open_count=status_data.get("open", severity_data.get("critical", 0) + severity_data.get("high", 0) + severity_data.get("medium", 0) + severity_data.get("low", 0)),
        prs_created=pr_row.total_prs or 0,
        prs_merged=pr_row.merged_prs or 0,
        total_repositories=repo_row.total or 0,
        scanned_repositories=repo_row.scanned or 0,
        total_scans=await db.scalar(
            select(func.count(ScanJob.id))
            .join(Repository, ScanJob.repository_id == Repository.id)
            .where(Repository.owner_id == current_user.id)
        ) or 0,
        scans_this_week=scans_this_week
    )


@router.get("/trends")
async def get_vulnerability_trends(
    days: int = 30,
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """Get vulnerability discovery trends over time."""
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Daily vulnerability counts
    daily_counts = await db.execute(
        select(
            func.date(Vulnerability.created_at).label("date"),
            Vulnerability.severity,
            func.count(Vulnerability.id).label("count")
        )
        .join(Repository, Vulnerability.repository_id == Repository.id)
        .where(
            Repository.owner_id == current_user.id,
            Vulnerability.created_at >= start_date
        )
        .group_by(func.date(Vulnerability.created_at), Vulnerability.severity)
        .order_by(func.date(Vulnerability.created_at))
    )
    
    # Organize by date
    trends = {}
    for row in daily_counts.all():
        date_str = row.date.isoformat() if hasattr(row.date, 'isoformat') else str(row.date)
        if date_str not in trends:
            trends[date_str] = {"date": date_str, "total": 0, "by_severity": {}}
        trends[date_str]["by_severity"][row.severity] = row.count
        trends[date_str]["total"] += row.count
    
    return {
        "period_days": days,
        "trends": list(trends.values()),
        "summary": {
            "total_new": sum(t["total"] for t in trends.values()),
            "critical_new": sum(t["by_severity"].get("critical", 0) for t in trends.values()),
            "high_new": sum(t["by_severity"].get("high", 0) for t in trends.values())
        }
    }


@router.get("/severity-distribution")
async def get_severity_distribution(
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """Get vulnerability severity distribution."""
    
    result = await db.execute(
        select(
            Vulnerability.severity,
            func.count(Vulnerability.id).label("count")
        )
        .join(Repository, Vulnerability.repository_id == Repository.id)
        .where(Repository.owner_id == current_user.id)
        .group_by(Vulnerability.severity)
    )
    
    rows = result.all()
    total = sum(row.count for row in rows) or 1  # Avoid division by zero
    
    distribution = [
        SeverityDistribution(
            severity=row.severity,
            count=row.count,
            percentage=round((row.count / total) * 100, 2)
        )
        for row in rows
    ]
    
    # Sort by severity order
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    distribution.sort(key=lambda x: severity_order.get(x.severity, 5))
    
    return {
        "total": total,
        "distribution": distribution
    }


@router.get("/repository-health")
async def get_repository_health(
    limit: int = 10,
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """Get health metrics for repositories."""
    
    # Get repositories with vulnerability counts
    repo_data = await db.execute(
        select(
            Repository.id,
            Repository.full_name,
            Repository.last_scan_at,
            func.count(Vulnerability.id).label("total_vulns"),
            func.sum(func.case([(Vulnerability.severity == "critical"), 1], else_=0)).label("critical"),
            func.sum(func.case([(Vulnerability.severity == "high"), 1], else_=0)).label("high"),
            func.sum(func.case([(Vulnerability.status == "fixed"), 1], else_=0)).label("fixed"),
        )
        .outerjoin(Vulnerability, Vulnerability.repository_id == Repository.id)
        .where(Repository.owner_id == current_user.id)
        .group_by(Repository.id)
        .order_by(desc("total_vulns"))
        .limit(limit)
    )
    
    repositories = []
    for row in repo_data.all():
        total = row.total_vulns or 0
        critical = row.critical or 0
        high = row.high or 0
        fixed = row.fixed or 0
        
        # Calculate health score (0-100)
        # Start at 100, deduct for vulnerabilities
        health_score = 100
        health_score -= critical * 15  # -15 per critical
        health_score -= high * 8       # -8 per high
        health_score -= (total - critical - high) * 2  # -2 per other
        health_score = max(0, health_score)  # Floor at 0
        
        # Calculate fix rate
        fix_rate = (fixed / total * 100) if total > 0 else 0
        
        repositories.append(RepositoryHealth(
            repository_id=row.id,
            repository_name=row.full_name,
            total_vulns=total,
            critical_vulns=critical,
            high_vulns=high,
            last_scan_at=row.last_scan_at.isoformat() if row.last_scan_at else None,
            health_score=round(health_score, 2),
            fix_rate=round(fix_rate, 2)
        ))
    
    return {
        "repositories": repositories,
        "overall_health": round(
            sum(r.health_score for r in repositories) / len(repositories), 2
        ) if repositories else 0
    }


@router.get("/fix-metrics")
async def get_fix_metrics(
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """Get AI fix generation metrics."""
    
    # Fixes generated
    fix_stats = await db.execute(
        select(
            func.count(Vulnerability.id).label("total_fixes"),
            func.avg(Vulnerability.confidence_score).label("avg_confidence")
        )
        .join(Repository, Vulnerability.repository_id == Repository.id)
        .where(
            Repository.owner_id == current_user.id,
            Vulnerability.fix_generated == True
        )
    )
    fix_row = fix_stats.one()
    
    # Fixes by CWE
    cwe_stats = await db.execute(
        select(
            Vulnerability.cwe_id,
            func.count(Vulnerability.id).label("count")
        )
        .join(Repository, Vulnerability.repository_id == Repository.id)
        .where(
            Repository.owner_id == current_user.id,
            Vulnerability.fix_generated == True,
            Vulnerability.cwe_id.isnot(None)
        )
        .group_by(Vulnerability.cwe_id)
        .order_by(desc("count"))
        .limit(10)
    )
    
    # PR metrics
    pr_stats = await db.execute(
        select(
            func.count(Vulnerability.id).label("total_prs"),
            func.sum(func.case([(Vulnerability.status == "fixed"), 1], else_=0)).label("merged")
        )
        .join(Repository, Vulnerability.repository_id == Repository.id)
        .where(
            Repository.owner_id == current_user.id,
            Vulnerability.pr_url.isnot(None)
        )
    )
    pr_row = pr_stats.one()
    
    total_prs = pr_row.total_prs or 0
    merged_prs = pr_row.merged or 0
    
    return FixMetrics(
        total_fixes_generated=fix_row.total_fixes or 0,
        fixes_by_cwe=[{"cwe_id": row.cwe_id, "count": row.count} for row in cwe_stats.all()],
        average_fix_confidence=round(fix_row.avg_confidence or 0, 2),
        prs_created=total_prs,
        prs_merged=merged_prs,
        merge_rate=round((merged_prs / total_prs * 100), 2) if total_prs > 0 else 0
    )


@router.get("/recent-activity")
async def get_recent_activity(
    limit: int = 20,
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """Get recent activity feed."""
    
    # Recent vulnerabilities
    recent_vulns = await db.execute(
        select(
            Vulnerability.id,
            Vulnerability.title,
            Vulnerability.severity,
            Vulnerability.created_at,
            Vulnerability.status,
            Vulnerability.pr_url,
            Repository.full_name.label("repository")
        )
        .join(Repository, Vulnerability.repository_id == Repository.id)
        .where(Repository.owner_id == current_user.id)
        .order_by(desc(Vulnerability.created_at))
        .limit(limit)
    )
    
    activities = []
    for row in recent_vulns.all():
        activity_type = "vulnerability_found"
        if row.pr_url:
            activity_type = "pr_created"
        if row.status == "fixed":
            activity_type = "vulnerability_fixed"
        
        activities.append({
            "id": row.id,
            "type": activity_type,
            "title": row.title,
            "severity": row.severity,
            "repository": row.repository,
            "timestamp": row.created_at.isoformat() if row.created_at else None,
            "status": row.status,
            "pr_url": row.pr_url
        })
    
    return {
        "activities": activities,
        "total_count": len(activities)
    }
