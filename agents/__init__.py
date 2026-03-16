"""
AI Agents Package for PatchFlow

This package contains all AI agents for autonomous security remediation:
- Triage Agent: Alert classification and prioritization
- Investigation Agent: Deep forensic analysis
- Code Fix Agent: Generate working code patches
- Remediation Agent: Create PRs and deploy fixes
- Rollback Agent: Monitor and revert if issues
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum
import structlog

logger = structlog.get_logger()

class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"

class AgentResult:
    """Result from an agent execution."""
    def __init__(
        self,
        success: bool,
        data: Dict[str, Any],
        error: Optional[str] = None,
        confidence: Optional[float] = None
    ):
        self.success = success
        self.data = data
        self.error = error
        self.confidence = confidence

class BaseAgent(ABC):
    """Base class for all PatchFlow AI agents."""
    
    def __init__(self, name: str, agent_type: str):
        self.name = name
        self.agent_type = agent_type
        self.status = AgentStatus.IDLE
        self.logger = structlog.get_logger().bind(agent=name, type=agent_type)
    
    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> AgentResult:
        """Execute the agent's main logic."""
        pass
    
    async def run(self, context: Dict[str, Any]) -> AgentResult:
        """Run the agent with logging and error handling."""
        self.status = AgentStatus.RUNNING
        self.logger.info("Agent starting execution", context=context)
        
        try:
            result = await self.execute(context)
            self.status = AgentStatus.COMPLETED if result.success else AgentStatus.ERROR
            self.logger.info(
                "Agent execution completed",
                success=result.success,
                confidence=result.confidence
            )
            return result
        except Exception as e:
            self.status = AgentStatus.ERROR
            self.logger.error("Agent execution failed", error=str(e))
            return AgentResult(
                success=False,
                data={},
                error=str(e)
            )

__all__ = [
    "BaseAgent",
    "AgentStatus", 
    "AgentResult"
]
