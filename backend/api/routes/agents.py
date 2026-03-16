from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum

router = APIRouter()

class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    DISABLED = "disabled"

class AgentType(str, Enum):
    TRIAGE = "triage"
    INVESTIGATION = "investigation"
    THREAT_INTEL = "threat_intel"
    CODE_FIX = "code_fix"
    REMEDIATION = "remediation"
    ROLLBACK = "rollback"

class AgentInfo(BaseModel):
    id: str
    name: str
    type: AgentType
    status: AgentStatus
    description: str
    last_activity: Optional[str]
    metrics: Dict[str, Any]

class AgentActionRequest(BaseModel):
    agent_type: AgentType
    action: str
    payload: Optional[Dict[str, Any]] = None

# Mock agent data for MVP
AGENTS = [
    AgentInfo(
        id="triage-001",
        name="Triage Agent",
        type=AgentType.TRIAGE,
        status=AgentStatus.IDLE,
        description="First responder - classifies and prioritizes alerts",
        last_activity=None,
        metrics={"alerts_processed": 0, "avg_processing_time_ms": 0}
    ),
    AgentInfo(
        id="investigation-001",
        name="Investigation Agent",
        type=AgentType.INVESTIGATION,
        status=AgentStatus.IDLE,
        description="Deep forensic analysis across data sources",
        last_activity=None,
        metrics={"investigations_completed": 0, "root_cause_accuracy": 0}
    ),
    AgentInfo(
        id="code-fix-001",
        name="Code Fix Agent",
        type=AgentType.CODE_FIX,
        status=AgentStatus.IDLE,
        description="Generates working code patches with test cases",
        last_activity=None,
        metrics={"fixes_generated": 0, "success_rate": 0, "avg_generation_time_s": 0}
    ),
    AgentInfo(
        id="remediation-001",
        name="Remediation Agent",
        type=AgentType.REMEDIATION,
        status=AgentStatus.IDLE,
        description="Creates PRs and manages deployment pipeline",
        last_activity=None,
        metrics={"prs_created": 0, "auto_merges": 0}
    ),
    AgentInfo(
        id="rollback-001",
        name="Rollback Agent",
        type=AgentType.ROLLBACK,
        status=AgentStatus.IDLE,
        description="Monitors deployments and reverts if issues detected",
        last_activity=None,
        metrics={"deployments_monitored": 0, "rollbacks_triggered": 0}
    ),
]

@router.get("/", response_model=List[AgentInfo])
async def list_agents():
    """List all AI agents and their status."""
    return AGENTS

@router.get("/{agent_id}", response_model=AgentInfo)
async def get_agent(agent_id: str):
    """Get specific agent details."""
    for agent in AGENTS:
        if agent.id == agent_id:
            return agent
    raise HTTPException(status_code=404, detail="Agent not found")

@router.post("/{agent_id}/run")
async def run_agent(agent_id: str, request: AgentActionRequest):
    """Trigger an agent to run a specific action."""
    agent = None
    for a in AGENTS:
        if a.id == agent_id:
            agent = a
            break
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # TODO: Implement actual agent execution via message queue
    return {
        "message": f"Agent {agent.name} action queued",
        "agent_id": agent_id,
        "action": request.action,
        "status": "queued",
        "job_id": f"job-{agent_id}-{request.action}"
    }

@router.get("/orchestrator/status")
async def get_orchestrator_status():
    """Get overall orchestrator status."""
    return {
        "status": "healthy",
        "active_agents": sum(1 for a in AGENTS if a.status == AgentStatus.RUNNING),
        "total_agents": len(AGENTS),
        "queue_depth": 0,
        "messages_per_second": 0,
        "last_error": None
    }

@router.post("/orchestrator/pause")
async def pause_orchestrator():
    """Pause all agent processing."""
    return {"message": "Orchestrator paused", "status": "paused"}

@router.post("/orchestrator/resume")
async def resume_orchestrator():
    """Resume all agent processing."""
    return {"message": "Orchestrator resumed", "status": "active"}
