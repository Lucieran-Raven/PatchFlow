"""AI Agent API routes for PatchFlow.

Endpoints for managing AI agent operations including:
- Vulnerability triage
- Agent task management
- Analysis results
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional, Dict, Any
from datetime import datetime
import structlog
import uuid

from core.database import get_db
from models import User, Vulnerability, Repository, ScanJob
from api.routes.auth import get_current_user as get_current_user_from_token
from agents.base_agent import AgentContext, AgentTask, AgentPriority, agent_orchestrator, AgentRegistry
from agents.triage_agent import TriageAgent

logger = structlog.get_logger()
router = APIRouter(tags=["AI Agents"])


@router.post("/vulnerabilities/{vuln_id}/triage")
async def triage_vulnerability(
    vuln_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """Trigger AI triage analysis for a vulnerability."""
    
    # Get vulnerability with repository info
    result = await db.execute(
        select(Vulnerability, Repository)
        .join(Repository, Vulnerability.repository_id == Repository.id)
        .where(Vulnerability.id == vuln_id, Repository.owner_id == current_user.id)
    )
    row = result.one_or_none()
    
    if not row:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    
    vuln, repo = row
    
    # Check if already triaged
    if vuln.triaged_at:
        return {
            "status": "already_triaged",
            "vulnerability_id": vuln_id,
            "triaged_at": vuln.triaged_at.isoformat(),
            "root_cause": vuln.root_cause,
            "risk_factors": vuln.risk_factors
        }
    
    # Prepare payload for triage agent
    payload = {
        "vulnerability": {
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
            "line_start": vuln.line_start,
            "line_end": vuln.line_end,
            "detected_at": vuln.detected_at.isoformat() if vuln.detected_at else None
        },
        "repository": {
            "id": repo.id,
            "name": repo.name,
            "full_name": repo.full_name,
            "is_private": repo.is_private,
            "language": repo.language,
            "default_branch": repo.default_branch
        }
    }
    
    # Submit task to agent orchestrator
    task_id = await agent_orchestrator.submit_task(
        agent_type="triage",
        payload=payload,
        priority=AgentPriority.HIGH if vuln.severity == "critical" else AgentPriority.MEDIUM
    )
    
    # Start processing in background
    background_tasks.add_task(run_triage_task, task_id, vuln_id, db)
    
    logger.info(
        "Triage task submitted",
        task_id=task_id,
        vuln_id=vuln_id,
        user_id=current_user.id
    )
    
    return {
        "status": "queued",
        "task_id": task_id,
        "vulnerability_id": vuln_id,
        "message": "AI triage analysis started"
    }


async def run_triage_task(task_id: str, vuln_id: str, db: AsyncSession):
    """Run triage task in background and save results."""
    from core.database import async_session_maker
    
    async with async_session_maker() as session:
        try:
            # Get the agent
            agent = AgentRegistry.get_agent("triage")
            if not agent:
                logger.error("Triage agent not found")
                return
            
            # Create task object (simplified for direct execution)
            task = AgentTask(
                id=task_id,
                agent_type="triage",
                payload={}  # Will be populated by orchestrator
            )
            
            # Get vulnerability data
            result = await session.execute(
                select(Vulnerability, Repository)
                .join(Repository, Vulnerability.repository_id == Repository.id)
                .where(Vulnerability.id == vuln_id)
            )
            row = result.one_or_none()
            
            if not row:
                logger.error("Vulnerability not found for triage", vuln_id=vuln_id)
                return
            
            vuln, repo = row
            
            # Create context
            context = AgentContext(
                task=task,
                user_id=repo.owner_id,
                repository_id=repo.id,
                vulnerability_id=vuln_id
            )
            context.task.payload = {
                "vulnerability": {
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
                    "detected_at": vuln.detected_at.isoformat() if vuln.detected_at else None
                },
                "repository": {
                    "id": repo.id,
                    "name": repo.name,
                    "full_name": repo.full_name,
                    "is_private": repo.is_private,
                    "language": repo.language,
                    "default_branch": repo.default_branch
                }
            }
            
            # Run agent
            result = await agent.run(context)
            
            # Update vulnerability with triage results
            vuln.triaged_at = datetime.utcnow()
            vuln.root_cause = result.get("attack_vector")  # Using attack vector as root cause for now
            vuln.exploitation_vector = result.get("exploit_difficulty")
            vuln.risk_factors = [
                f"risk_score:{result.get('risk_score')}",
                f"risk_level:{result.get('risk_level')}",
                f"priority:{result.get('recommended_action')}",
                f"exploitable:{result.get('is_exploitable')}",
                f"business_impact:{result.get('business_impact')}",
                f"fix_complexity:{result.get('fix_complexity')}"
            ]
            
            await session.commit()
            
            logger.info(
                "Triage completed",
                vuln_id=vuln_id,
                risk_score=result.get("risk_score"),
                risk_level=result.get("risk_level")
            )
            
        except Exception as e:
            logger.error("Triage task failed", vuln_id=vuln_id, error=str(e))


@router.get("/vulnerabilities/{vuln_id}/triage")
async def get_triage_result(
    vuln_id: str,
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """Get AI triage results for a vulnerability."""
    
    # Get vulnerability
    result = await db.execute(
        select(Vulnerability, Repository)
        .join(Repository, Vulnerability.repository_id == Repository.id)
        .where(Vulnerability.id == vuln_id, Repository.owner_id == current_user.id)
    )
    row = result.one_or_none()
    
    if not row:
        raise HTTPException(status_code=404, detail="Vulnerability not found")
    
    vuln, repo = row
    
    if not vuln.triaged_at:
        return {
            "vulnerability_id": vuln_id,
            "status": "not_triaged",
            "message": "Triage analysis not yet run"
        }
    
    # Parse risk factors
    risk_factors = vuln.risk_factors or []
    triage_data = {}
    
    for factor in risk_factors:
        if ":" in factor:
            key, value = factor.split(":", 1)
            triage_data[key] = value
    
    return {
        "vulnerability_id": vuln_id,
        "status": "triaged",
        "triaged_at": vuln.triaged_at.isoformat(),
        "risk_score": float(triage_data.get("risk_score", 0)),
        "risk_level": triage_data.get("risk_level", "unknown"),
        "is_exploitable": triage_data.get("exploitable") == "True",
        "business_impact": triage_data.get("business_impact", "unknown"),
        "recommended_action": triage_data.get("priority", "unknown"),
        "fix_complexity": triage_data.get("fix_complexity", "unknown"),
        "root_cause": vuln.root_cause,
        "exploitation_vector": vuln.exploitation_vector,
        "risk_factors": risk_factors
    }


@router.post("/scan-jobs/{scan_id}/triage-all")
async def triage_all_scan_vulnerabilities(
    scan_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """Trigger triage for all vulnerabilities in a scan."""
    
    # Verify scan ownership
    result = await db.execute(
        select(ScanJob, Repository)
        .join(Repository, ScanJob.repository_id == Repository.id)
        .where(ScanJob.id == scan_id, Repository.owner_id == current_user.id)
    )
    row = result.one_or_none()
    
    if not row:
        raise HTTPException(status_code=404, detail="Scan job not found")
    
    scan_job, repo = row
    
    # Get untriaged vulnerabilities
    result = await db.execute(
        select(Vulnerability)
        .where(
            Vulnerability.scan_job_id == scan_id,
            Vulnerability.triaged_at.is_(None)
        )
    )
    vulnerabilities = result.scalars().all()
    
    if not vulnerabilities:
        return {
            "scan_id": scan_id,
            "status": "no_vulnerabilities",
            "message": "No untriaged vulnerabilities found"
        }
    
    # Queue triage for each vulnerability
    task_ids = []
    for vuln in vulnerabilities:
        task_id = await agent_orchestrator.submit_task(
            agent_type="triage",
            payload={
                "vulnerability_id": vuln.id,
                "scan_id": scan_id
            },
            priority=AgentPriority.HIGH if vuln.severity == "critical" else AgentPriority.MEDIUM
        )
        task_ids.append(task_id)
        background_tasks.add_task(run_triage_task, task_id, vuln.id, db)
    
    logger.info(
        "Batch triage started",
        scan_id=scan_id,
        vuln_count=len(vulnerabilities),
        task_count=len(task_ids)
    )
    
    return {
        "scan_id": scan_id,
        "status": "queued",
        "vulnerabilities_count": len(vulnerabilities),
        "tasks_queued": len(task_ids),
        "message": f"Triage queued for {len(vulnerabilities)} vulnerabilities"
    }


@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    current_user: User = Depends(get_current_user_from_token)
):
    """Get status of an agent task."""
    
    # Note: In a full implementation, we'd check ownership
    # For now, return basic info
    
    task = await agent_orchestrator.get_task_status(task_id)
    
    if not task:
        return {
            "task_id": task_id,
            "status": "unknown",
            "message": "Task not found or still running"
        }
    
    return {
        "task_id": task_id,
        "agent_type": task.agent_type,
        "status": task.status.value,
        "priority": task.priority.value,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "retry_count": task.retry_count,
        "error_message": task.error_message,
        "result": task.result
    }


@router.get("/orchestrator/stats")
async def get_orchestrator_stats(
    current_user: User = Depends(get_current_user_from_token)
):
    """Get agent orchestrator statistics."""
    stats = agent_orchestrator.get_stats()
    
    return {
        "orchestrator_stats": stats,
        "registered_agents": AgentRegistry.list_agents(),
        "current_time": datetime.utcnow().isoformat()
    }
