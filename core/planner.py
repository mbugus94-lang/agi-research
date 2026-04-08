"""
Task planning module for AGI agents.
Implements hierarchical task decomposition and goal management.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import json


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class PlanStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    """A single task node in the plan."""
    id: str
    description: str
    action: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    estimated_duration: float = 0.0
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    subtasks: List['Task'] = field(default_factory=list)
    result: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_ready(self) -> bool:
        """Check if all dependencies are satisfied."""
        return all(
            dep.status == TaskStatus.COMPLETED 
            for dep in self.get_dependencies()
        )
    
    def can_execute(self) -> bool:
        """Check if task can be executed (dependencies satisfied)."""
        # For simple task with string dependency IDs
        # In practice, this checks against a task registry
        return True  # Simplified - assumes dependencies are checked elsewhere
    
    def mark_complete(self):
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED
    
    def mark_failed(self, error: str = ""):
        """Mark task as failed with error info."""
        self.status = TaskStatus.FAILED
        self.metadata["error"] = error
    
    def get_dependencies(self) -> List['Task']:
        """Get actual task objects for dependencies."""
        # This is a placeholder - in practice, tasks would reference a task registry
        return []
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "description": self.description,
            "action": self.action,
            "parameters": self.parameters,
            "estimated_duration": self.estimated_duration,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "subtasks": [t.to_dict() for t in self.subtasks],
            "result": self.result,
            "metadata": self.metadata
        }


@dataclass
class Plan:
    """A plan containing multiple tasks to achieve a goal."""
    goal: str
    tasks: List[Task] = field(default_factory=list)
    status: PlanStatus = PlanStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def replan(self, fallback_task_id: Optional[str] = None):
        """Adapt plan when tasks fail."""
        self.status = PlanStatus.PENDING
        
        if fallback_task_id:
            # Mark failed tasks and add alternative
            failed_count = sum(1 for t in self.tasks if t.status == TaskStatus.FAILED)
            
            # Create alternative task
            alt_task = Task(
                id=f"alt_{failed_count}",
                description=f"Alternative approach (replacing failed tasks)",
                action="alternative"
            )
            
            # Find first failed task's position and insert alternative
            for i, task in enumerate(self.tasks):
                if task.status == TaskStatus.FAILED:
                    # Update dependencies
                    alt_task.dependencies = [task.id]  # Depend on what failed
                    self.tasks.insert(i + 1, alt_task)
                    break
    
    def to_dict(self) -> Dict:
        return {
            "goal": self.goal,
            "status": self.status.value,
            "tasks": [t.to_dict() for t in self.tasks],
            "metadata": self.metadata
        }


class Planner:
    """
    Hierarchical task planner.
    Decomposes goals into actionable subtasks.
    """
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.current_plan: Optional[Task] = None
    
    def create_plan(self, goal: str, tasks: List[Task]) -> Plan:
        """Create a plan from a goal and task list."""
        plan = Plan(
            goal=goal,
            tasks=tasks,
            status=PlanStatus.PENDING
        )
        self.current_plan = plan
        return plan
    
    def decompose(self, goal: str, context: str = "") -> Task:
        """
        Decompose a goal into a task tree.
        
        Args:
            goal: High-level goal to achieve
            context: Additional context for decomposition
            
        Returns:
            Root task with subtasks
        """
        # Simple rule-based decomposition for now
        # In production, this would use an LLM
        
        subtasks = self._generate_subtasks(goal, context)
        
        root = Task(
            id="root",
            description=goal,
            subtasks=subtasks
        )
        
        self._register_tasks(root)
        self.current_plan = root
        
        return root
    
    def _generate_subtasks(self, goal: str, context: str) -> List[Task]:
        """Generate subtasks for a goal."""
        # Heuristic decomposition patterns
        goal_lower = goal.lower()
        
        subtasks = []
        
        # Pattern: Research + Analysis + Synthesis
        if any(word in goal_lower for word in ["analyze", "research", "find", "search"]):
            subtasks.extend([
                Task(id="1", description=f"Gather information about: {goal}", dependencies=[]),
                Task(id="2", description="Analyze gathered information", dependencies=["1"]),
                Task(id="3", description="Synthesize findings", dependencies=["2"])
            ])
        
        # Pattern: Plan + Execute + Verify
        elif any(word in goal_lower for word in ["create", "build", "implement", "make"]):
            subtasks.extend([
                Task(id="1", description=f"Plan approach for: {goal}", dependencies=[]),
                Task(id="2", description="Execute the plan", dependencies=["1"]),
                Task(id="3", description="Verify the result", dependencies=["2"])
            ])
        
        # Pattern: Single step
        else:
            subtasks.append(Task(
                id="1",
                description=goal,
                dependencies=[]
            ))
        
        return subtasks
    
    def _register_tasks(self, task: Task):
        """Register task in lookup dictionary."""
        self.tasks[task.id] = task
        for subtask in task.subtasks:
            self._register_tasks(subtask)
    
    def get_next_task(self) -> Optional[Task]:
        """Get the next ready task to execute."""
        if not self.current_plan:
            return None
        
        return self._find_ready_task(self.current_plan)
    
    def _find_ready_task(self, task: Task) -> Optional[Task]:
        """DFS to find first ready task."""
        if task.status == TaskStatus.PENDING:
            # Check if dependencies are satisfied
            deps_satisfied = all(
                self.tasks.get(dep_id, Task(dep_id, "")).status == TaskStatus.COMPLETED
                for dep_id in task.dependencies
            )
            if deps_satisfied:
                return task
        
        # Check subtasks
        for subtask in task.subtasks:
            ready = self._find_ready_task(subtask)
            if ready:
                return ready
        
        return None
    
    def update_task(self, task_id: str, status: TaskStatus, result: Any = None):
        """Update task status and result."""
        if task_id in self.tasks:
            self.tasks[task_id].status = status
            if result is not None:
                self.tasks[task_id].result = result
    
    def is_complete(self) -> bool:
        """Check if the current plan is complete."""
        if not self.current_plan:
            return True
        return self._check_complete(self.current_plan)
    
    def _check_complete(self, task: Task) -> bool:
        """Check if task and all subtasks are complete."""
        if task.status != TaskStatus.COMPLETED:
            return False
        return all(self._check_complete(t) for t in task.subtasks)
    
    def get_plan_summary(self) -> str:
        """Get human-readable plan summary."""
        if not self.current_plan:
            return "No active plan"
        
        lines = [f"Goal: {self.current_plan.description}", ""]
        self._print_task_tree(self.current_plan, lines, 0)
        return "\n".join(lines)
    
    def _print_task_tree(self, task: Task, lines: List[str], depth: int):
        """Add task tree to lines list."""
        indent = "  " * depth
        status_icon = {
            TaskStatus.PENDING: "⬜",
            TaskStatus.IN_PROGRESS: "🔄",
            TaskStatus.COMPLETED: "✅",
            TaskStatus.FAILED: "❌"
        }.get(task.status, "⬜")
        
        lines.append(f"{indent}{status_icon} {task.id}: {task.description}")
        
        for subtask in task.subtasks:
            self._print_task_tree(subtask, lines, depth + 1)
    
    def get_execution_path(self) -> List[Task]:
        """Get ordered list of tasks to execute."""
        if not self.current_plan:
            return []
        
        path = []
        self._collect_execution_order(self.current_plan, path)
        return path
    
    def _collect_execution_order(self, task: Task, path: List[Task]):
        """Collect tasks in execution order (topological)."""
        # Add dependencies first
        for dep_id in task.dependencies:
            if dep_id in self.tasks and self.tasks[dep_id] not in path:
                self._collect_execution_order(self.tasks[dep_id], path)
        
        if task not in path:
            path.append(task)
        
        # Then subtasks
        for subtask in task.subtasks:
            self._collect_execution_order(subtask, path)


class GoalManager:
    """
    Manages multiple goals and their priorities.
    """
    
    def __init__(self):
        self.goals: List[Dict[str, Any]] = []
        self.current_goal_index: int = 0
    
    def add_goal(self, goal: str, priority: int = 5, deadline: str = None):
        """Add a new goal with priority (1-10, higher = more important)."""
        self.goals.append({
            "goal": goal,
            "priority": priority,
            "deadline": deadline,
            "status": "pending"
        })
        # Re-sort by priority
        self.goals.sort(key=lambda g: g["priority"], reverse=True)
    
    def get_current_goal(self) -> Optional[str]:
        """Get the highest priority pending goal."""
        for goal in self.goals:
            if goal["status"] == "pending":
                return goal["goal"]
        return None
    
    def mark_goal_complete(self, goal: str):
        """Mark a goal as completed."""
        for g in self.goals:
            if g["goal"] == goal:
                g["status"] = "completed"
                break
    
    def get_all_goals(self) -> List[Dict[str, Any]]:
        """Get all goals with status."""
        return self.goals


if __name__ == "__main__":
    # Demo
    planner = Planner()
    
    # Decompose a goal
    root = planner.decompose(
        goal="Research and analyze the impact of AI on healthcare",
        context="Need comprehensive report for stakeholders"
    )
    
    print(planner.get_plan_summary())
    print("\n" + "="*50)
    
    # Simulate execution
    next_task = planner.get_next_task()
    while next_task:
        print(f"\nExecuting: {next_task.description}")
        planner.update_task(next_task.id, TaskStatus.IN_PROGRESS)
        # Simulate work...
        planner.update_task(next_task.id, TaskStatus.COMPLETED, result="Done")
        
        if planner.is_complete():
            break
        next_task = planner.get_next_task()
    
    print("\n" + planner.get_plan_summary())
