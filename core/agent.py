"""
Base Agent Implementation

A minimal but extensible agent architecture based on 2026 research:
- Cartesian agency: clear separation between core and interface
- Test-time adaptation: refinement during execution
- Constitutional governance: safety-first self-modification
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from enum import Enum


class AgentState(Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    WAITING = "waiting"


@dataclass
class AgentIdentity:
    """Persistent identity across sessions - inspired by Ouroboros"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "AGI-Agent"
    version: str = "0.1.0"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    core_values: List[str] = field(default_factory=lambda: [
        "safety_first",
        "incremental_progress",
        "test_everything",
        "document_findings"
    ])
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "created_at": self.created_at,
            "core_values": self.core_values
        }


@dataclass
class Task:
    """A task for the agent to execute"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    goal: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    parent_id: Optional[str] = None
    subtasks: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, in_progress, completed, failed
    result: Any = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "description": self.description,
            "goal": self.goal,
            "context": self.context,
            "parent_id": self.parent_id,
            "subtasks": self.subtasks,
            "status": self.status,
            "result": self.result,
            "created_at": self.created_at,
            "completed_at": self.completed_at
        }


class BaseAgent:
    """
    Base agent with:
    - Identity persistence
    - State management
    - Skill registry
    - Basic task execution loop
    """
    
    def __init__(self, identity: Optional[AgentIdentity] = None):
        self.identity = identity or AgentIdentity()
        self.state = AgentState.IDLE
        self.memory = {}  # Will integrate with core/memory.py
        self.skills: Dict[str, Callable] = {}
        self.current_task: Optional[Task] = None
        self.task_history: List[Task] = []
        self.reflection_enabled = True
        
    def register_skill(self, name: str, skill: Callable) -> None:
        """Register a skill function"""
        self.skills[name] = skill
        
    def get_identity(self) -> Dict:
        """Return agent identity as dict"""
        return self.identity.to_dict()
    
    def create_task(self, description: str, goal: str, 
                    context: Optional[Dict] = None,
                    parent_id: Optional[str] = None) -> Task:
        """Create a new task"""
        task = Task(
            description=description,
            goal=goal,
            context=context or {},
            parent_id=parent_id
        )
        return task
    
    def execute_skill(self, skill_name: str, **kwargs) -> Any:
        """Execute a registered skill"""
        if skill_name not in self.skills:
            raise ValueError(f"Skill '{skill_name}' not found. Available: {list(self.skills.keys())}")
        
        self.state = AgentState.EXECUTING
        try:
            result = self.skills[skill_name](**kwargs)
            return result
        except Exception as e:
            return {"error": str(e), "skill": skill_name}
        finally:
            self.state = AgentState.IDLE
    
    def execute_task(self, task: Task, max_iterations: int = 10) -> Task:
        """
        Execute a task with test-time refinement loop.
        
        Based on ARC-AGI research: test-time adaptation is critical.
        This implements a basic refinement loop.
        """
        self.current_task = task
        task.status = "in_progress"
        
        for iteration in range(max_iterations):
            # Planning phase
            self.state = AgentState.PLANNING
            plan = self._generate_plan(task, iteration)
            
            # Execution phase
            self.state = AgentState.EXECUTING
            step_result = self._execute_plan_step(plan, iteration)
            
            # Reflection/adaptation phase (test-time refinement)
            if self.reflection_enabled:
                self.state = AgentState.REFLECTING
                should_adapt = self._reflect_on_step(step_result, iteration)
                if should_adapt:
                    self._adapt_plan(task, step_result)
            
            # Check completion
            if self._is_task_complete(task, step_result):
                task.status = "completed"
                task.result = step_result
                task.completed_at = datetime.now().isoformat()
                break
        else:
            task.status = "failed"
            task.result = {"error": "Max iterations reached"}
        
        self.task_history.append(task)
        self.current_task = None
        self.state = AgentState.IDLE
        return task
    
    def _generate_plan(self, task: Task, iteration: int) -> Dict:
        """Generate a plan for the task - to be enhanced with core/planner.py"""
        return {
            "iteration": iteration,
            "action": "execute_skill",
            "target": task.description,
            "steps": ["analyze", "execute", "verify"]
        }
    
    def _execute_plan_step(self, plan: Dict, iteration: int) -> Dict:
        """Execute a single plan step"""
        return {
            "iteration": iteration,
            "status": "executed",
            "plan": plan
        }
    
    def _reflect_on_step(self, result: Dict, iteration: int) -> bool:
        """
        Reflect on execution and decide if adaptation is needed.
        
        This is the test-time refinement loop from ARC-AGI research.
        """
        # Basic implementation - will be enhanced with core/reflection.py
        if "error" in result:
            return True  # Adapt on error
        return False
    
    def _adapt_plan(self, task: Task, result: Dict) -> None:
        """Adapt the plan based on reflection"""
        # Placeholder for adaptive planning
        task.context["adaptation_count"] = task.context.get("adaptation_count", 0) + 1
    
    def _is_task_complete(self, task: Task, result: Dict) -> bool:
        """Check if task is complete"""
        return result.get("status") == "completed"
    
    def get_status(self) -> Dict:
        """Get current agent status"""
        return {
            "identity": self.identity.to_dict(),
            "state": self.state.value,
            "skills": list(self.skills.keys()),
            "current_task": self.current_task.to_dict() if self.current_task else None,
            "task_count": len(self.task_history)
        }
    
    def save_state(self, path: str) -> None:
        """Save agent state to file"""
        state = {
            "identity": self.identity.to_dict(),
            "memory": self.memory,
            "task_history": [t.to_dict() for t in self.task_history],
            "skills_registered": list(self.skills.keys())
        }
        with open(path, 'w') as f:
            json.dump(state, f, indent=2)
    
    def load_state(self, path: str) -> None:
        """Load agent state from file"""
        with open(path, 'r') as f:
            state = json.load(f)
        
        self.identity = AgentIdentity(**state["identity"])
        self.memory = state.get("memory", {})
        # Skills must be re-registered (functions can't be serialized)
        self.task_history = [Task(**t) for t in state.get("task_history", [])]


def example_skill(name: str = "world") -> str:
    """Example skill for testing"""
    return f"Hello, {name}!"


if __name__ == "__main__":
    # Basic test
    agent = BaseAgent()
    agent.register_skill("greet", example_skill)
    
    print("Agent Identity:", agent.get_identity())
    
    task = agent.create_task(
        description="Test greeting",
        goal="Execute a greeting skill"
    )
    
    result = agent.execute_task(task, max_iterations=1)
    print("Task Result:", result.to_dict())
    print("Agent Status:", agent.get_status())
