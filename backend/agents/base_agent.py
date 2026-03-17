"""Base Agent Framework for PatchFlow AI Agents.

Provides the foundation for all AI-powered agents including:
- Triage Agent
- Code Fix Agent  
- PR Review Agent
"""
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
import structlog
from datetime import datetime
import json

logger = structlog.get_logger()


class AgentStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class AgentPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class AgentTask:
    """Represents a task for an agent to execute."""
    id: str
    agent_type: str
    payload: Dict[str, Any]
    priority: AgentPriority = AgentPriority.MEDIUM
    status: AgentStatus = AgentStatus.IDLE
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass  
class AgentContext:
    """Context passed to agents during execution."""
    task: AgentTask
    user_id: Optional[str] = None
    repository_id: Optional[str] = None
    vulnerability_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def log_context(self) -> Dict[str, Any]:
        """Return context as dict for logging."""
        return {
            "task_id": self.task.id,
            "agent_type": self.task.agent_type,
            "user_id": self.user_id,
            "repository_id": self.repository_id,
            "vulnerability_id": self.vulnerability_id,
        }


class BaseAgent(ABC):
    """Abstract base class for all PatchFlow AI agents.
    
    Agents follow a lifecycle:
    1. initialize() - Setup resources
    2. execute() - Run the main task
    3. validate_result() - Verify output quality
    4. cleanup() - Release resources
    """
    
    def __init__(self, agent_type: str, name: str):
        self.agent_type = agent_type
        self.name = name
        self.status = AgentStatus.IDLE
        self.logger = logger.bind(agent_type=agent_type, agent_name=name)
        self._task_handlers: Dict[str, Callable] = {}
        self._register_handlers()
    
    def _register_handlers(self):
        """Register task type handlers. Override in subclasses."""
        pass
    
    @abstractmethod
    async def initialize(self, context: AgentContext) -> bool:
        """Initialize the agent with necessary resources.
        
        Returns:
            True if initialization successful
        """
        pass
    
    @abstractmethod
    async def execute(self, context: AgentContext) -> Dict[str, Any]:
        """Execute the agent's main task.
        
        Args:
            context: Execution context with task details
            
        Returns:
            Dictionary containing execution results
        """
        pass
    
    async def validate_result(self, context: AgentContext, result: Dict[str, Any]) -> bool:
        """Validate the execution result.
        
        Override in subclasses for domain-specific validation.
        
        Returns:
            True if result is valid
        """
        return result is not None and isinstance(result, dict)
    
    async def cleanup(self, context: AgentContext):
        """Cleanup resources after execution."""
        self.status = AgentStatus.IDLE
    
    async def run(self, context: AgentContext) -> Dict[str, Any]:
        """Run the complete agent lifecycle.
        
        This is the main entry point for executing an agent task.
        """
        task_id = context.task.id
        self.logger.info("Starting agent execution", **context.log_context())
        
        try:
            # Update status
            self.status = AgentStatus.RUNNING
            context.task.status = AgentStatus.RUNNING
            context.task.started_at = datetime.utcnow()
            
            # Initialize
            if not await self.initialize(context):
                raise Exception("Agent initialization failed")
            
            # Execute
            result = await self.execute(context)
            
            # Validate
            if not await self.validate_result(context, result):
                raise Exception("Result validation failed")
            
            # Success
            context.task.status = AgentStatus.COMPLETED
            context.task.completed_at = datetime.utcnow()
            context.task.result = result
            
            self.logger.info(
                "Agent execution completed",
                task_id=task_id,
                duration=self._get_duration(context.task)
            )
            
            return result
            
        except Exception as e:
            self.logger.error(
                "Agent execution failed",
                task_id=task_id,
                error=str(e),
                retry_count=context.task.retry_count
            )
            
            context.task.status = AgentStatus.FAILED
            context.task.error_message = str(e)
            context.task.completed_at = datetime.utcnow()
            
            # Retry logic
            if context.task.retry_count < context.task.max_retries:
                context.task.retry_count += 1
                self.logger.info("Retrying task", task_id=task_id, attempt=context.task.retry_count)
                await asyncio.sleep(2 ** context.task.retry_count)  # Exponential backoff
                return await self.run(context)
            
            raise
            
        finally:
            await self.cleanup(context)
    
    def _get_duration(self, task: AgentTask) -> float:
        """Calculate task duration in seconds."""
        if task.started_at and task.completed_at:
            return (task.completed_at - task.started_at).total_seconds()
        return 0.0


class AgentRegistry:
    """Registry for managing all available agents."""
    
    _agents: Dict[str, type] = {}
    _instances: Dict[str, BaseAgent] = {}
    
    @classmethod
    def register(cls, agent_type: str, agent_class: type):
        """Register an agent class."""
        cls._agents[agent_type] = agent_class
        logger.info("Agent registered", agent_type=agent_type, agent_class=agent_class.__name__)
    
    @classmethod
    def get_agent(cls, agent_type: str) -> Optional[BaseAgent]:
        """Get or create an agent instance."""
        if agent_type not in cls._instances:
            agent_class = cls._agents.get(agent_type)
            if agent_class:
                cls._instances[agent_type] = agent_class()
        return cls._instances.get(agent_type)
    
    @classmethod
    def list_agents(cls) -> List[str]:
        """List all registered agent types."""
        return list(cls._agents.keys())


class AgentOrchestrator:
    """Orchestrates execution of multiple agents.
    
    Manages:
    - Task queueing
    - Priority scheduling
    - Concurrent execution limits
    - Result aggregation
    """
    
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.completed_tasks: Dict[str, AgentTask] = {}
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.logger = logger.bind(component="AgentOrchestrator")
    
    async def submit_task(
        self,
        agent_type: str,
        payload: Dict[str, Any],
        priority: AgentPriority = AgentPriority.MEDIUM,
        context: Optional[AgentContext] = None
    ) -> str:
        """Submit a task for execution.
        
        Returns:
            Task ID
        """
        import uuid
        task_id = str(uuid.uuid4())
        
        task = AgentTask(
            id=task_id,
            agent_type=agent_type,
            payload=payload,
            priority=priority
        )
        
        # Priority queue uses lower numbers first, so invert priority
        await self.task_queue.put((priority.value, task))
        
        self.logger.info(
            "Task submitted",
            task_id=task_id,
            agent_type=agent_type,
            priority=priority.value
        )
        
        # Start processing if not already running
        if len(self.running_tasks) < self.max_concurrent:
            asyncio.create_task(self._process_queue())
        
        return task_id
    
    async def _process_queue(self):
        """Process tasks from the queue."""
        while not self.task_queue.empty():
            async with self.semaphore:
                _, task = await self.task_queue.get()
                
                if task.id in self.completed_tasks:
                    continue
                
                # Create and run agent
                agent = AgentRegistry.get_agent(task.agent_type)
                if not agent:
                    self.logger.error("Unknown agent type", agent_type=task.agent_type)
                    task.status = AgentStatus.FAILED
                    task.error_message = f"Unknown agent type: {task.agent_type}"
                    self.completed_tasks[task.id] = task
                    continue
                
                # Create context if not provided
                context = AgentContext(task=task)
                
                # Run agent
                try:
                    result = await agent.run(context)
                    self.completed_tasks[task.id] = task
                except Exception as e:
                    self.logger.error(
                        "Task execution failed",
                        task_id=task.id,
                        error=str(e)
                    )
                    self.completed_tasks[task.id] = task
    
    async def get_task_status(self, task_id: str) -> Optional[AgentTask]:
        """Get the status of a task."""
        if task_id in self.completed_tasks:
            return self.completed_tasks[task_id]
        
        # Check running tasks
        for task in self.running_tasks.values():
            if task.get_name() == task_id:
                # Task is still running, get from agent
                return None
        
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        return {
            "queue_size": self.task_queue.qsize(),
            "running_tasks": len(self.running_tasks),
            "completed_tasks": len(self.completed_tasks),
            "max_concurrent": self.max_concurrent,
        }


# Global orchestrator instance
agent_orchestrator = AgentOrchestrator(max_concurrent=3)
