"""
Planner Implementation

Hierarchical task decomposition and planning.

Features:
- Goal decomposition into subgoals
- Strategy selection
- Plan revision on failure
- Multi-step reasoning

References:
- NVIDIA AI-Q Blueprint: Intent classification, shallow vs deep paths
- Microsoft multi-agent: Orchestration and delegation patterns
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
import json
from datetime import datetime


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class Task:
    """A unit of work in a plan"""
    id: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    subtasks: List["Task"] = field(default_factory=list)
    strategy: str = "default"
    estimated_effort: int = 1  # Relative effort units
    result: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_ready(self) -> bool:
        """Check if task is ready to execute (dependencies complete)."""
        return self.status == TaskStatus.PENDING and all(
            d.status == TaskStatus.COMPLETE for d in self.subtasks
            if d.id in self.dependencies
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "subtasks": [t.to_dict() for t in self.subtasks],
            "strategy": self.strategy,
            "estimated_effort": self.estimated_effort,
            "has_result": self.result is not None
        }


@dataclass
class Plan:
    """A complete plan for achieving a goal"""
    goal: str
    root_task: Task
    strategy: str
    created_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_all_tasks(self) -> List[Task]:
        """Flatten task tree into list."""
        tasks = []
        
        def collect(task: Task):
            tasks.append(task)
            for sub in task.subtasks:
                collect(sub)
        
        collect(self.root_task)
        return tasks
    
    def get_next_tasks(self) -> List[Task]:
        """Get tasks ready for execution."""
        return [t for t in self.get_all_tasks() if t.is_ready()]
    
    def get_completion_rate(self) -> float:
        """Calculate completion percentage."""
        tasks = self.get_all_tasks()
        if not tasks:
            return 0.0
        complete = sum(1 for t in tasks if t.status == TaskStatus.COMPLETE)
        return complete / len(tasks)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "strategy": self.strategy,
            "created_at": self.created_at,
            "completion_rate": self.get_completion_rate(),
            "task_count": len(self.get_all_tasks()),
            "root": self.root_task.to_dict()
        }


class Strategy:
    """Base class for planning strategies"""
    
    def __init__(self, name: str):
        self.name = name
    
    def can_handle(self, goal: str, context: Dict[str, Any]) -> bool:
        """Check if this strategy is appropriate for the goal."""
        return True
    
    def decompose(self, goal: str, context: Dict[str, Any]) -> Task:
        """Decompose goal into tasks. Must be implemented by subclasses."""
        raise NotImplementedError


class SequentialStrategy(Strategy):
    """
    Simple sequential decomposition.
    
    Break goal into ordered steps executed one after another.
    """
    
    def __init__(self):
        super().__init__("sequential")
    
    def can_handle(self, goal: str, context: Dict[str, Any]) -> bool:
        # Good for straightforward tasks
        indicators = ["steps", "process", "workflow", "procedure"]
        return any(ind in goal.lower() for ind in indicators)
    
    def decompose(self, goal: str, context: Dict[str, Any]) -> Task:
        """Create sequential task structure."""
        root = Task(
            id="root",
            description=goal,
            status=TaskStatus.PENDING
        )
        
        # Simple heuristic: split by common delimiters
        # In production, use LLM for intelligent decomposition
        parts = self._identify_steps(goal, context)
        
        prev_task_id = None
        for i, part in enumerate(parts):
            task = Task(
                id=f"step_{i}",
                description=part,
                dependencies=[prev_task_id] if prev_task_id else [],
                strategy="sequential"
            )
            root.subtasks.append(task)
            prev_task_id = task.id
        
        return root
    
    def _identify_steps(self, goal: str, context: Dict[str, Any]) -> List[str]:
        """Identify steps from goal."""
        # Default decomposition patterns
        goal_lower = goal.lower()
        
        if "research" in goal_lower:
            return [
                "Define research scope and objectives",
                "Gather relevant information and sources",
                "Analyze and synthesize findings",
                "Document conclusions and recommendations"
            ]
        elif "build" in goal_lower or "create" in goal_lower:
            return [
                "Define requirements and specifications",
                "Design structure and components",
                "Implement core functionality",
                "Test and validate results"
            ]
        elif "analyze" in goal_lower:
            return [
                "Collect relevant data and context",
                "Apply analytical methods",
                "Interpret results",
                "Form conclusions"
            ]
        else:
            # Generic decomposition
            return [
                f"Understand: {goal}",
                "Plan approach",
                "Execute plan",
                "Review results"
            ]


class ParallelStrategy(Strategy):
    """
    Parallel decomposition.
    
    Break goal into independent tasks that can execute concurrently.
    """
    
    def __init__(self):
        super().__init__("parallel")
    
    def can_handle(self, goal: str, context: Dict[str, Any]) -> bool:
        # Good for tasks with independent sub-components
        indicators = ["compare", "evaluate multiple", "gather", "collect", "research several"]
        return any(ind in goal.lower() for ind in indicators)
    
    def decompose(self, goal: str, context: Dict[str, Any]) -> Task:
        """Create parallel task structure."""
        root = Task(
            id="root",
            description=goal,
            status=TaskStatus.PENDING
        )
        
        # Identify parallelizable components
        components = self._identify_components(goal, context)
        
        for i, component in enumerate(components):
            task = Task(
                id=f"parallel_{i}",
                description=component,
                dependencies=[],  # No dependencies for parallel
                strategy="parallel"
            )
            root.subtasks.append(task)
        
        return root
    
    def _identify_components(self, goal: str, context: Dict[str, Any]) -> List[str]:
        """Identify parallel components."""
        # Default patterns
        goal_lower = goal.lower()
        
        if "compare" in goal_lower:
            return [
                "Analyze option A",
                "Analyze option B",
                "Compare and synthesize"
            ]
        elif "research" in goal_lower:
            return [
                "Search source A",
                "Search source B",
                "Search source C",
                "Synthesize findings"
            ]
        else:
            return [
                "Subtask 1",
                "Subtask 2",
                "Subtask 3"
            ]


class HierarchicalStrategy(Strategy):
    """
    Hierarchical decomposition.
    
    Multi-level breakdown with sub-goals and leaf tasks.
    """
    
    def __init__(self, max_depth: int = 3):
        super().__init__("hierarchical")
        self.max_depth = max_depth
    
    def can_handle(self, goal: str, context: Dict[str, Any]) -> bool:
        # Good for complex, multi-faceted goals
        indicators = ["complex", "comprehensive", "system", "architecture", "design"]
        return any(ind in goal.lower() for ind in indicators) or len(goal) > 100
    
    def decompose(self, goal: str, context: Dict[str, Any]) -> Task:
        """Create hierarchical task structure."""
        root = Task(
            id="root",
            description=goal,
            status=TaskStatus.PENDING
        )
        
        # Top-level breakdown
        subgoals = self._identify_subgoals(goal, context)
        
        for i, subgoal in enumerate(subgoals):
            subtask = self._create_subtree(subgoal, i, depth=1)
            root.subtasks.append(subtask)
        
        return root
    
    def _create_subtree(self, description: str, index: int, depth: int) -> Task:
        """Recursively create task subtree."""
        task = Task(
            id=f"h_{depth}_{index}",
            description=description,
            strategy="hierarchical"
        )
        
        if depth < self.max_depth:
            # Further decompose
            substeps = self._decompose_subgoal(description)
            for j, step in enumerate(substeps):
                child = Task(
                    id=f"h_{depth+1}_{index}_{j}",
                    description=step,
                    dependencies=[task.id],
                    strategy="hierarchical"
                )
                task.subtasks.append(child)
        
        return task
    
    def _identify_subgoals(self, goal: str, context: Dict[str, Any]) -> List[str]:
        """Identify major subgoals."""
        # Default multi-phase structure
        return [
            f"Phase 1: Discovery and requirements",
            f"Phase 2: Design and planning",
            f"Phase 3: Implementation",
            f"Phase 4: Validation and refinement"
        ]
    
    def _decompose_subgoal(self, subgoal: str) -> List[str]:
        """Decompose a subgoal into steps."""
        return [
            f"Understand: {subgoal}",
            f"Execute: {subgoal}",
            f"Verify: {subgoal}"
        ]


class Planner:
    """
    Hierarchical Task Planner
    
    Implements strategy selection and task decomposition.
    """
    
    def __init__(self):
        self.strategies: List[Strategy] = [
            SequentialStrategy(),
            ParallelStrategy(),
            HierarchicalStrategy()
        ]
    
    def create_plan(self, goal: str, context: Optional[Dict[str, Any]] = None) -> Plan:
        """
        Create a plan for achieving the goal.
        
        Two-tier routing:
        1. Select appropriate strategy based on goal characteristics
        2. Decompose using selected strategy
        """
        context = context or {}
        
        # Select strategy
        strategy = self._select_strategy(goal, context)
        
        # Decompose into task tree
        root_task = strategy.decompose(goal, context)
        
        return Plan(
            goal=goal,
            root_task=root_task,
            strategy=strategy.name,
            created_at=datetime.now().timestamp(),
            metadata={
                "context_keys": list(context.keys()),
                "strategy_selection_reason": f"Matched strategy: {strategy.name}"
            }
        )
    
    def revise_plan(
        self,
        plan: Plan,
        failed_task: Task,
        reason: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Plan:
        """
        Revise plan when a task fails.
        
        Strategies:
        - Decompose further if task was too big
        - Try alternative approach
        - Add dependency to resolve blocker
        """
        # Mark failed task
        failed_task.status = TaskStatus.FAILED
        
        # Create alternative approach
        alternative = Task(
            id=f"{failed_task.id}_alt",
            description=f"Alternative: {failed_task.description} (was: {reason})",
            dependencies=[d for d in failed_task.dependencies],  # Same deps
            strategy="alternative"
        )
        
        # Add alternative to parent
        parent = self._find_parent(plan.root_task, failed_task.id)
        if parent:
            parent.subtasks.append(alternative)
        
        return plan
    
    def _select_strategy(self, goal: str, context: Dict[str, Any]) -> Strategy:
        """Select best strategy for the goal."""
        # Score each strategy
        scores = []
        for strategy in self.strategies:
            score = 0
            if strategy.can_handle(goal, context):
                score += 1
            # Add more sophisticated scoring here
            scores.append((score, strategy))
        
        # Return highest scoring strategy
        scores.sort(key=lambda x: x[0], reverse=True)
        return scores[0][1]
    
    def _find_parent(self, root: Task, task_id: str) -> Optional[Task]:
        """Find parent of a task by ID."""
        for sub in root.subtasks:
            if sub.id == task_id:
                return root
            parent = self._find_parent(sub, task_id)
            if parent:
                return parent
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "available_strategies": [s.name for s in self.strategies],
            "strategy_count": len(self.strategies)
        }
