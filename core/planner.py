"""
Hierarchical Task Planning System for AGI agents.

Implements multi-level planning inspired by:
- arXiv:2601.11658v1: Hierarchical LLM architecture (Base LLM planning)
- arXiv:2604.01020v1: OrgAgent governance/execution/compliance layers
- arXiv:2602.01465: ReAct pattern for reasoning and acting

The planner decomposes goals into executable tasks with dependency management,
adaptive replanning, and integration with the memory and reflection systems.
"""

from typing import List, Dict, Any, Optional, Callable, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
import json
import uuid


class TaskStatus(Enum):
    """Status of a task in the plan."""
    PENDING = auto()
    READY = auto()  # Dependencies satisfied
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    BLOCKED = auto()  # Dependencies failed
    CANCELLED = auto()


class TaskPriority(Enum):
    """Priority levels for task scheduling."""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclass
class Task:
    """A single task in a plan."""
    id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    
    # Task details
    expected_output: Optional[str] = None
    tools_required: List[str] = field(default_factory=list)
    estimated_duration: Optional[float] = None  # minutes
    
    # Dependencies
    depends_on: List[str] = field(default_factory=list)  # Task IDs
    blocks: List[str] = field(default_factory=list)  # Tasks this blocks
    
    # Execution tracking
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.name,
            "priority": self.priority.name,
            "expected_output": self.expected_output,
            "tools_required": self.tools_required,
            "estimated_duration": self.estimated_duration,
            "depends_on": self.depends_on,
            "blocks": self.blocks,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        task = cls(
            id=data["id"],
            description=data["description"],
            status=TaskStatus[data["status"]],
            priority=TaskPriority[data["priority"]],
            expected_output=data.get("expected_output"),
            tools_required=data.get("tools_required", []),
            estimated_duration=data.get("estimated_duration"),
            depends_on=data.get("depends_on", []),
            blocks=data.get("blocks", []),
            retry_count=data.get("retry_count", 0),
            max_retries=data.get("max_retries", 3),
            metadata=data.get("metadata", {})
        )
        if data.get("started_at"):
            task.started_at = datetime.fromisoformat(data["started_at"])
        if data.get("completed_at"):
            task.completed_at = datetime.fromisoformat(data["completed_at"])
        task.result = data.get("result")
        task.error_message = data.get("error_message")
        return task


@dataclass
class Plan:
    """A complete plan consisting of multiple tasks."""
    id: str
    goal: str
    description: Optional[str] = None
    tasks: Dict[str, Task] = field(default_factory=dict)
    
    # Plan metadata
    status: str = "active"  # active, completed, failed, cancelled
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    # Strategy
    strategy: str = "sequential"  # sequential, parallel, adaptive
    max_parallel: int = 5
    
    # Statistics
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "description": self.description,
            "tasks": {tid: t.to_dict() for tid, t in self.tasks.items()},
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "strategy": self.strategy,
            "max_parallel": self.max_parallel,
            "total_tasks": len(self.tasks),
            "completed_tasks": sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED),
            "failed_tasks": sum(1 for t in self.tasks.values() if t.status == TaskStatus.FAILED)
        }


class PlanExecutor:
    """Executes plans with dependency tracking and adaptive replanning."""
    
    def __init__(self, tool_registry: Optional[Any] = None):
        self.tool_registry = tool_registry
        self.execution_history: List[Dict[str, Any]] = []
        self.active_plans: Dict[str, Plan] = {}
    
    def create_plan(
        self,
        goal: str,
        description: Optional[str] = None,
        strategy: str = "adaptive"
    ) -> Plan:
        """Create a new plan for a goal."""
        plan_id = str(uuid.uuid4())[:8]
        plan = Plan(
            id=plan_id,
            goal=goal,
            description=description,
            strategy=strategy
        )
        self.active_plans[plan_id] = plan
        return plan
    
    def decompose_goal(
        self,
        plan: Plan,
        subtasks: List[Dict[str, Any]]
    ) -> List[Task]:
        """
        Decompose a goal into subtasks.
        
        Args:
            plan: The plan to add tasks to
            subtasks: List of task definitions with keys:
                - description: str
                - priority: str (optional)
                - depends_on: List[str] (optional)
                - tools_required: List[str] (optional)
                - expected_output: str (optional)
        """
        tasks = []
        id_map = {}  # Map index to generated ID
        
        for i, task_def in enumerate(subtasks):
            task_id = f"{plan.id}_{i}"
            id_map[i] = task_id
            
            priority = TaskPriority.MEDIUM
            if "priority" in task_def:
                priority = TaskPriority[task_def["priority"].upper()]
            
            # Convert dependency indices to IDs
            depends_on = []
            if "depends_on" in task_def:
                for dep in task_def["depends_on"]:
                    if isinstance(dep, int):
                        depends_on.append(id_map.get(dep, f"{plan.id}_{dep}"))
                    else:
                        depends_on.append(dep)
            
            task = Task(
                id=task_id,
                description=task_def["description"],
                priority=priority,
                expected_output=task_def.get("expected_output"),
                tools_required=task_def.get("tools_required", []),
                estimated_duration=task_def.get("estimated_duration"),
                depends_on=depends_on,
                metadata=task_def.get("metadata", {})
            )
            tasks.append(task)
            plan.tasks[task_id] = task
        
        # Update blocks relationships
        for task in tasks:
            for dep_id in task.depends_on:
                if dep_id in plan.tasks:
                    plan.tasks[dep_id].blocks.append(task.id)
        
        plan.total_tasks = len(tasks)
        return tasks
    
    def get_ready_tasks(self, plan: Plan) -> List[Task]:
        """Get tasks that are ready to execute (dependencies satisfied)."""
        ready = []
        for task in plan.tasks.values():
            if task.status != TaskStatus.PENDING:
                continue
            
            # Check if all dependencies are completed
            deps_satisfied = all(
                plan.tasks.get(dep_id, Task(dep_id, "")).status == TaskStatus.COMPLETED
                for dep_id in task.depends_on
            )
            
            # Check if any dependency failed
            deps_failed = any(
                plan.tasks.get(dep_id, Task(dep_id, "")).status == TaskStatus.FAILED
                for dep_id in task.depends_on
            )
            
            if deps_failed:
                task.status = TaskStatus.BLOCKED
            elif deps_satisfied:
                task.status = TaskStatus.READY
                ready.append(task)
        
        # Sort by priority
        ready.sort(key=lambda t: t.priority.value)
        return ready
    
    def start_task(self, task: Task) -> None:
        """Mark a task as started."""
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now()
    
    def complete_task(self, task: Task, result: Any) -> None:
        """Mark a task as completed with result."""
        task.status = TaskStatus.COMPLETED
        task.result = result
        task.completed_at = datetime.now()
    
    def fail_task(self, task: Task, error: str) -> None:
        """Mark a task as failed with error message."""
        task.status = TaskStatus.FAILED
        task.error_message = error
        task.completed_at = datetime.now()
        
        # Check if we should retry
        if task.retry_count < task.max_retries:
            task.retry_count += 1
            task.status = TaskStatus.PENDING  # Will be re-evaluated
            task.error_message = None
    
    def update_plan_status(self, plan: Plan) -> None:
        """Update the overall plan status based on task states."""
        completed = sum(1 for t in plan.tasks.values() if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in plan.tasks.values() if t.status == TaskStatus.FAILED)
        pending = sum(1 for t in plan.tasks.values() if t.status in [TaskStatus.PENDING, TaskStatus.READY])
        
        plan.completed_tasks = completed
        plan.failed_tasks = failed
        
        if pending == 0:
            if failed == 0:
                plan.status = "completed"
            elif completed > 0:
                plan.status = "partial"
            else:
                plan.status = "failed"
            plan.completed_at = datetime.now()
    
    def get_execution_order(self, plan: Plan) -> List[List[str]]:
        """
        Get tasks in execution order, grouped by parallelizable stages.
        Returns list of lists, where each inner list contains task IDs that can run in parallel.
        """
        stages = []
        completed = set()
        remaining = set(plan.tasks.keys())
        
        while remaining:
            stage = []
            for task_id in remaining:
                task = plan.tasks[task_id]
                deps_satisfied = all(dep in completed for dep in task.depends_on)
                if deps_satisfied:
                    stage.append(task_id)
            
            if not stage:
                # Circular dependency or unresolvable
                break
            
            stages.append(stage)
            completed.update(stage)
            remaining -= set(stage)
        
        return stages
    
    def replan(
        self,
        plan: Plan,
        failed_task_id: str,
        new_subtasks: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Plan]:
        """
        Create a recovery plan for a failed task.
        
        Args:
            plan: Original plan
            failed_task_id: ID of the failed task
            new_subtasks: Optional replacement subtasks
        
        Returns:
            New recovery plan or None if cannot recover
        """
        failed_task = plan.tasks.get(failed_task_id)
        if not failed_task:
            return None
        
        # Create recovery subplan
        recovery_plan = self.create_plan(
            goal=f"Recover from failure: {failed_task.description}",
            description=f"Alternative approach after failure of {failed_task_id}",
            strategy="sequential"
        )
        
        if new_subtasks:
            self.decompose_goal(recovery_plan, new_subtasks)
        else:
            # Default recovery: retry with alternative approach
            self.decompose_goal(recovery_plan, [
                {
                    "description": f"Analyze failure of: {failed_task.description}",
                    "priority": "HIGH",
                    "expected_output": "failure_analysis"
                },
                {
                    "description": f"Retry with modified approach: {failed_task.description}",
                    "priority": "HIGH",
                    "depends_on": [0],
                    "expected_output": failed_task.expected_output
                }
            ])
        
        return recovery_plan


class HierarchicalPlanner:
    """
    Multi-level planner implementing hierarchical task decomposition.
    
    Strategy levels:
    - L0 (Strategic): High-level goal decomposition
    - L1 (Tactical): Mid-level planning and resource allocation
    - L2 (Operational): Concrete task execution plans
    """
    
    def __init__(self, memory_system: Optional[Any] = None):
        self.executor = PlanExecutor()
        self.memory = memory_system
        self.plan_history: List[Dict[str, Any]] = []
    
    def create_strategic_plan(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Plan:
        """
        L0: Create high-level strategic plan.
        Decomposes goal into major phases/milestones.
        """
        plan = self.executor.create_plan(
            goal=goal,
            description="Strategic plan with major milestones",
            strategy="adaptive"
        )
        
        # Default strategic phases (can be overridden by context)
        phases = [
            {
                "description": "Research and information gathering",
                "priority": "HIGH",
                "expected_output": "research_summary"
            },
            {
                "description": "Analysis and strategy formulation",
                "priority": "HIGH",
                "depends_on": [0],
                "expected_output": "strategy_document"
            },
            {
                "description": "Implementation execution",
                "priority": "HIGH",
                "depends_on": [1],
                "expected_output": "deliverables"
            },
            {
                "description": "Validation and review",
                "priority": "MEDIUM",
                "depends_on": [2],
                "expected_output": "validation_report"
            }
        ]
        
        # Override with context if provided
        if context and "strategic_phases" in context:
            phases = context["strategic_phases"]
        
        self.executor.decompose_goal(plan, phases)
        return plan
    
    def create_tactical_plan(
        self,
        strategic_task: Task,
        tactics: List[Dict[str, Any]]
    ) -> Plan:
        """
        L1: Create tactical plan for a strategic task.
        Decomposes into specific approaches and resource allocations.
        """
        plan = self.executor.create_plan(
            goal=strategic_task.description,
            description=f"Tactical plan for: {strategic_task.description[:50]}...",
            strategy="parallel"
        )
        
        self.executor.decompose_goal(plan, tactics)
        return plan
    
    def create_operational_plan(
        self,
        tactical_task: Task,
        operations: List[Dict[str, Any]]
    ) -> Plan:
        """
        L2: Create operational plan for a tactical task.
        Decomposes into concrete executable steps.
        """
        plan = self.executor.create_plan(
            goal=tactical_task.description,
            description=f"Operational plan: {tactical_task.description[:50]}...",
            strategy="sequential"
        )
        
        self.executor.decompose_goal(plan, operations)
        return plan
    
    def plan_with_reflection(
        self,
        goal: str,
        reflection_data: Optional[Dict[str, Any]] = None
    ) -> Plan:
        """
        Create plan informed by reflection data.
        Uses past performance to adjust planning strategy.
        
        Args:
            goal: The goal to plan for
            reflection_data: Past reflection data with keys:
                - successful_approaches: List[str]
                - failed_approaches: List[str]
                - suggested_improvements: List[str]
        """
        plan = self.executor.create_plan(goal=goal, strategy="adaptive")
        
        # Adjust planning based on reflection
        if reflection_data:
            # Add validation step if past failures suggest caution
            if reflection_data.get("failed_approaches"):
                phases = [
                    {"description": "Initial research", "priority": "MEDIUM"},
                    {"description": "Approach validation", "priority": "HIGH", "depends_on": [0]},
                    {"description": "Main execution", "priority": "HIGH", "depends_on": [1]},
                    {"description": "Verification", "priority": "HIGH", "depends_on": [2]}
                ]
            else:
                phases = [
                    {"description": "Research", "priority": "MEDIUM"},
                    {"description": "Execute with validated approach", "priority": "HIGH", "depends_on": [0]}
                ]
        else:
            # Default phases without reflection
            phases = [
                {"description": "Research and gather information", "priority": "MEDIUM"},
                {"description": "Plan and design approach", "priority": "HIGH", "depends_on": [0]},
                {"description": "Execute plan", "priority": "HIGH", "depends_on": [1]},
                {"description": "Validate results", "priority": "MEDIUM", "depends_on": [2]}
            ]
        
        self.executor.decompose_goal(plan, phases)
        
        # Store planning decision
        self.plan_history.append({
            "timestamp": datetime.now().isoformat(),
            "goal": goal,
            "plan_id": plan.id,
            "reflection_informed": reflection_data is not None,
            "strategy": plan.strategy
        })
        
        return plan
    
    def get_plan_statistics(self) -> Dict[str, Any]:
        """Get statistics across all plans."""
        total = len(self.executor.active_plans)
        completed = sum(1 for p in self.executor.active_plans.values() if p.status == "completed")
        failed = sum(1 for p in self.executor.active_plans.values() if p.status == "failed")
        active = sum(1 for p in self.executor.active_plans.values() if p.status == "active")
        
        return {
            "total_plans": total,
            "completed": completed,
            "failed": failed,
            "active": active,
            "success_rate": completed / total if total > 0 else 0
        }


# Convenience functions for creating planners
def create_planner(memory_system: Optional[Any] = None) -> HierarchicalPlanner:
    """Create a new hierarchical planner."""
    return HierarchicalPlanner(memory_system=memory_system)


def create_simple_plan(goal: str, steps: List[str]) -> Plan:
    """
    Create a simple sequential plan from a list of step descriptions.
    
    Args:
        goal: The overall goal
        steps: List of step descriptions
    
    Returns:
        A Plan with sequential dependencies
    """
    planner = HierarchicalPlanner()
    plan = planner.executor.create_plan(goal=goal, strategy="sequential")
    
    subtasks = [
        {
            "description": step,
            "priority": "MEDIUM",
            "depends_on": [i - 1] if i > 0 else []
        }
        for i, step in enumerate(steps)
    ]
    
    planner.executor.decompose_goal(plan, subtasks)
    return plan
