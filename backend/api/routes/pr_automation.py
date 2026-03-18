"""PR Automation API routes for PatchFlow.

Endpoints for creating and managing pull requests with security fixes:
- Create PR with fix
- Get PR status
- List PRs for vulnerabilities
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from pydantic import BaseModel
import structlog

from core.database import get_db
from models import User, Vulnerability, Repository
from api.routes.auth import get_current_user as get_current_user_from_token
from services.pr_service import pr_service

logger = structlog.get_logger()
router = APIRouter(tags=["PR Automation"])


class CreatePRRequest(BaseModel):
    """Request body for creating a PR."""
    branch_name: Optional[str] = None
    pr_title: Optional[str] = None
    pr_body: Optional[str] = None


@router.post("/vulnerabilities/{vuln_id}/pr")
async def create_fix_pr(
    vuln_id: str,
    request: CreatePRRequest,
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """Create a GitHub pull request with the security fix."""
    
    # Verify vulnerability ownership
    result = await db.execute(
        select(Vulnerability, Repository)
        .join(Repository, Vulnerability.repository_id == Repository.id)
        .where(Vulnerability.id == vuln_id, Repository.owner_id == current_user.id)
    )
    row = result.one_or_none()
    
    if not row:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    
    vuln, repo = row
    
    # Check if fix exists
    if not vuln.fix_generated:
        raise HTTPException(
            status_code=400, 
            detail="No fix generated for this vulnerability. Call POST /agents/vulnerabilities/{id}/fix first."
        )
    
    # Check if PR already exists
    if vuln.pr_url:
        return {
            "status": "already_exists",
            "message": "PR already exists for this vulnerability",
            "pr_url": vuln.pr_url,
            "pr_number": vuln.pr_number
        }
    
    # Create PR
    result = await pr_service.create_fix_pr(
        vulnerability_id=vuln_id,
        user_id=current_user.id,
        custom_branch_name=request.branch_name,
        custom_pr_title=request.pr_title,
        custom_pr_body=request.pr_body
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to create PR"))
    
    return {
        "status": "created",
        "vulnerability_id": vuln_id,
        "pr_url": result["pr_url"],
        "pr_number": result["pr_number"],
        "branch_name": result["branch_name"],
        "commit_sha": result["commit_sha"],
        "title": result["title"]
    }


@router.get("/vulnerabilities/{vuln_id}/pr")
async def get_pr_status(
    vuln_id: str,
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """Get the status of a pull request for a vulnerability."""
    
    # Verify ownership
    result = await db.execute(
        select(Vulnerability, Repository)
        .join(Repository, Vulnerability.repository_id == Repository.id)
        .where(Vulnerability.id == vuln_id, Repository.owner_id == current_user.id)
    )
    row = result.one_or_none()
    
    if not row:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    
    vuln, repo = row
    
    if not vuln.pr_number:
        return {
            "vulnerability_id": vuln_id,
            "status": "no_pr",
            "message": "No PR has been created for this vulnerability"
        }
    
    # Get PR status from GitHub
    status = await pr_service.get_pr_status(vuln_id, current_user.id)
    
    return {
        "vulnerability_id": vuln_id,
        "pr_url": vuln.pr_url,
        "pr_number": vuln.pr_number,
        **status
    }


@router.post("/vulnerabilities/{vuln_id}/pr/refresh")
async def refresh_pr_status(
    vuln_id: str,
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """Refresh PR status from GitHub (useful after PR is merged/closed externally)."""
    
    # Verify ownership
    result = await db.execute(
        select(Vulnerability, Repository)
        .join(Repository, Vulnerability.repository_id == Repository.id)
        .where(Vulnerability.id == vuln_id, Repository.owner_id == current_user.id)
    )
    row = result.one_or_none()
    
    if not row:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    
    # Get fresh status
    status = await pr_service.get_pr_status(vuln_id, current_user.id)
    
    # If PR is merged, update vulnerability status
    if status.get("merged"):
        vuln, _ = row
        vuln.status = "fixed"
        await db.commit()
        logger.info("Vulnerability marked as fixed (PR merged)", vuln_id=vuln_id)
    
    return {
        "vulnerability_id": vuln_id,
        "status": "refreshed",
        "pr_status": status
    }


@router.get("/repositories/{repo_id}/prs")
async def list_repository_prs(
    repo_id: str,
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """List all pull requests created for a repository's vulnerabilities."""
    
    # Verify repository ownership
    result = await db.execute(
        select(Repository)
        .where(Repository.id == repo_id, Repository.owner_id == current_user.id)
    )
    repo = result.scalar_one_or_none()
    
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Get vulnerabilities with PRs
    result = await db.execute(
        select(Vulnerability)
        .where(
            Vulnerability.repository_id == repo_id,
            Vulnerability.pr_url.isnot(None)
        )
    )
    vulnerabilities = result.scalars().all()
    
    prs = []
    for vuln in vulnerabilities:
        prs.append({
            "vulnerability_id": vuln.id,
            "cve_id": vuln.cve_id,
            "cwe_id": vuln.cwe_id,
            "title": vuln.title,
            "severity": vuln.severity,
            "pr_url": vuln.pr_url,
            "pr_number": vuln.pr_number,
            "status": vuln.status,
            "file_path": vuln.file_path
        })
    
    return {
        "repository_id": repo_id,
        "repository_name": repo.full_name,
        "total_prs": len(prs),
        "pull_requests": prs
    }
