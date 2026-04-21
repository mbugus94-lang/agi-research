"""
Planning System with Test-Time Refinement

Based on ARC-AGI research findings:
- Test-time adaptation and refinement loops are critical for success
- Compositional reasoning: build complex plans from simple primitives
- Task decomposition for complex goals
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from enum import Enum


class PlanStatus(Enum):
    DRAFT = "draft"
    EXECUTING = "executing"
    ADAPTING = "adapting"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PlanStep:
    """A single step in a plan"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    action: str = ""  # Skill name or sub-plan
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Any = None
    status: str = field(default_factory=lambda: StepStatus.PENDING.value)
    depends_on: List[str] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "description": self.description,
            "action": self.action,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "status": self.status,
            "depends_on": self.depends_on,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error
        }


@dataclass
class Plan:
    """A plan containing multiple steps"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    goal: str = ""
    description: str = ""
    steps: List[PlanStep] = field(default_factory=list)
    status: str = field(default_factory=lambda: PlanStatus.DRAFT.value)
    iteration: int = 0
    max_iterations: int = 10
    adaptation_history: List[Dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    parent_plan_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "goal": self.goal,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "adaptation_history": self.adaptation_history,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "parent_plan_id": self.parent_plan_id
        }
    
    def get_ready_steps(self) -> List[PlanStep]:
        """Get steps that are ready to execute (dependencies met)"""
        ready = []
        for step in self.steps:
            if step.status != StepStatus.PENDING.value:
                continue
            
            # Check dependencies
            deps_met = all(
                any(s.id == dep_id and s.status == StepStatus.COMPLETED.value 
                    for s in self.steps)
                for dep_id in step.depends_on
            )
            
            if deps_met:
                ready.append(step)
        
        return ready
    
    def get_failed_steps(self) -> List[PlanStep]:
        """Get all failed steps"""
        return [s for s in self.steps if s.status == StepStatus.FAILED.value]


class Planner:
    """
    Planning system with test-time refinement.
    
    Key features:
    1. Task decomposition into composable steps
    2. Dependency management between steps
    3. Test-time adaptation based on execution feedback
    4. Iterative refinement when steps fail
    """
    
    def __init__(self, skill_registry: Optional[Dict[str, Callable]] = None):
        self.skill_registry = skill_registry or {}
        self.plan_history: List[Plan] = []
        self.primitive_patterns: Dict[str, List[str]] = {
            "research": ["web_search", "summarize", "synthesize"],
            "implement": ["analyze", "design", "code", "test", "verify"],
            "debug": ["identify", "isolate", "fix", "verify"],
            "learn": ["observe", "hypothesize", "experiment", "conclude"]
        }
    
    def register_skill(self, name: str, skill: Callable) -> None:
        """Register a skill that can be used in plans"""
        self.skill_registry[name] = skill
    
    def decompose_goal(self, goal: str, context: Optional[Dict] = None) -> Plan:
        """
        Decompose a high-level goal into a plan with steps.
        
        Uses primitive patterns to build composable plans.
        """
        plan = Plan(goal=goal, description=f"Plan for: {goal}")
        
        # Simple keyword-based decomposition (to be enhanced with LLM)
        goal_lower = goal.lower()
        
        if "research" in goal_lower or "find" in goal_lower:
            pattern = self.primitive_patterns["research"]
        elif "implement" in goal_lower or "build" in goal_lower or "create" in goal_lower:
            pattern = self.primitive_patterns["implement"]
        elif "debug" in goal_lower or "fix" in goal_lower:
            pattern = self.primitive_patterns["debug"]
        elif "learn" in goal_lower or "understand" in goal_lower:
            pattern = self.primitive_patterns["learn"]
        else:
            pattern = ["analyze", "execute", "verify"]
        
        # Create steps from pattern
        for i, action in enumerate(pattern):
            step = PlanStep(
                description=f"Step {i+1}: {action}",
                action=action,
                inputs={"goal": goal, "context": context or {}}
            )
            
            # Add sequential dependency
            if i > 0:
                step.depends_on = [plan.steps[-1].id]
            
            plan.steps.append(step)
        
        return plan
    
    def execute_step(self, step: PlanStep, 
                     skill_executor: Callable) -> Dict[str, Any]:
        """
        Execute a single plan step.
        
        Returns result with success status and outputs.
        """
        step.status = StepStatus.IN_PROGRESS.value
        step.started_at = datetime.now().isoformat()
        
        try:
            if step.action in self.skill_registry:
                result = skill_executor(step.action, **step.inputs)
                step.outputs = result
                step.status = StepStatus.COMPLETED.value
            else:
                # Action not found - mark for adaptation
                step.error = f"Skill '{step.action}' not found"
                step.status = StepStatus.FAILED.value
                
        except Exception as e:
            step.error = str(e)
            step.status = StepStatus.FAILED.value
            
            # Check if can retry
            if step.retry_count < step.max_retries:
                step.retry_count += 1
                step.status = StepStatus.PENDING.value
        
        step.completed_at = datetime.now().isoformat()
        
        return {
            "step_id": step.id,
            "status": step.status,
            "outputs": step.outputs,
            "error": step.error,
            "retry_count": step.retry_count
        }
    
    def execute_plan(self, plan: Plan, 
                     skill_executor: Callable,
                     enable_adaptation: bool = True) -> Plan:
        """
        Execute a plan with test-time refinement.
        
        This is the core loop from ARC-AGI research:
        - Execute steps
        - Reflect on results
        - Adapt plan if needed
        - Iterate until complete or max iterations
        """
        plan.status = PlanStatus.EXECUTING.value
        plan.started_at = datetime.now().isoformat()
        
        while plan.iteration < plan.max_iterations:
            plan.iteration += 1
            
            # Get ready steps
            ready_steps = plan.get_ready_steps()
            
            if not ready_steps:
                # Check if complete or stuck
                pending = [s for s in plan.steps if s.status == StepStatus.PENDING.value]
                in_progress = [s for s in plan.steps if s.status == StepStatus.IN_PROGRESS.value]
                
                if not pending and not in_progress:
                    # All done
                    failed = plan.get_failed_steps()
                    plan.status = PlanStatus.FAILED.value if failed else PlanStatus.COMPLETED.value
                    break
                else:
                    # Stuck - need adaptation
                    if enable_adaptation:
                        self._adapt_plan_on_stuck(plan)
                        continue
                    else:
                        plan.status = PlanStatus.FAILED.value
                        break
            
            # Execute ready steps
            for step in ready_steps:
                result = self.execute_step(step, skill_executor)
                
                # Check if adaptation needed
                if enable_adaptation and result["status"] == StepStatus.FAILED.value:
                    if not self._should_adapt(plan, step):
                        continue
                    
                    self._adapt_plan_on_failure(plan, step, result)
                    break  # Restart iteration after adaptation
        
        plan.completed_at = datetime.now().isoformat()
        self.plan_history.append(plan)
        
        return plan
    
    def _should_adapt(self, plan: Plan, failed_step: PlanStep) -> bool:
        """Decide if plan should be adapted based on failure"""
        # Don't adapt if max retries not reached
        if failed_step.retry_count < failed_step.max_retries:
            return False
        
        # Don't adapt if already adapted too many times
        if len(plan.adaptation_history) >= 3:
            return False
        
        return True
    
    def _adapt_plan_on_failure(self, plan: Plan, 
                               failed_step: PlanStep,
                               result: Dict) -> None:
        """
        Adapt plan when a step fails.
        
        Strategies:
        1. Replace action with alternative
        2. Add sub-steps before failed step
        3. Skip if not critical
        """
        plan.status = PlanStatus.ADAPTING.value
        
        adaptation = {
            "timestamp": datetime.now().isoformat(),
            "trigger": "step_failure",
            "failed_step": failed_step.to_dict(),
            "strategy": None
        }
        
        # Try alternative action
        alternatives = self._get_alternatives(failed_step.action)
        
        if alternatives and failed_step.retry_count >= failed_step.max_retries:
            # Replace with alternative
            failed_step.action = alternatives[0]
            failed_step.retry_count = 0
            failed_step.status = StepStatus.PENDING.value
            failed_step.error = None
            adaptation["strategy"] = "alternative_action"
            adaptation["new_action"] = alternatives[0]
        else:
            # Add decomposition steps
            sub_steps = self._decompose_step(failed_step)
            
            if sub_steps:
                # Insert before failed step
                idx = plan.steps.index(failed_step)
                for i, sub in enumerate(sub_steps):
                    if i == 0:
                        sub.depends_on = failed_step.depends_on
                    else:
                        sub.depends_on = [sub_steps[i-1].id]
                    plan.steps.insert(idx + i, sub)
                
                # Update failed step dependencies
                failed_step.depends_on = [sub_steps[-1].id]
                failed_step.status = StepStatus.PENDING.value
                failed_step.retry_count = 0
                
                adaptation["strategy"] = "decomposition"
                adaptation["added_steps"] = len(sub_steps)
        
        plan.adaptation_history.append(adaptation)
    
    def _adapt_plan_on_stuck(self, plan: Plan) -> None:
        """Adapt plan when progress is stuck (dependency issues)"""
        # Find steps with unmet dependencies that could be parallelized
        pending = [s for s in plan.steps if s.status == StepStatus.PENDING.value]
        
        for step in pending:
            # Check if dependencies are actually required
            # Simplification: remove dependencies for now (risky!)
            if len(step.depends_on) > 0:
                step.depends_on = []  # Make independent
                
        plan.adaptation_history.append({
            "timestamp": datetime.now().isoformat(),
            "trigger": "stuck",
            "strategy": "parallelize",
            "affected_steps": len(pending)
        })
    
    def _get_alternatives(self, action: str) -> List[str]:
        """Get alternative actions for a failed skill"""
        alternatives_map = {
            "web_search": ["browser_navigate", "ask_user"],
            "code": ["pseudocode", "break_down"],
            "analyze": ["observe", "collect_data"],
            "test": ["manual_verify", "review_output"]
        }
        return alternatives_map.get(action, [])
    
    def _decompose_step(self, step: PlanStep) -> List[PlanStep]:
        """Decompose a complex step into sub-steps"""
        # Simple decomposition rules
        if step.action == "code":
            return [
                PlanStep(description="Design structure", action="design"),
                PlanStep(description="Write core logic", action="implement"),
                PlanStep(description="Add error handling", action="harden")
            ]
        elif step.action == "research":
            return [
                PlanStep(description="Initial search", action="web_search"),
                PlanStep(description="Deep dive", action="deep_search"),
                PlanStep(description="Synthesize findings", action="synthesize")
            ]
        return []
    
    def create_sub_plan(self, parent_plan: Plan, 
                        for_step: PlanStep,
                        sub_goal: str) -> Plan:
        """Create a sub-plan for a specific step"""
        sub_plan = self.decompose_goal(sub_goal)
        sub_plan.parent_plan_id = parent_plan.id
        return sub_plan


if __name__ == "__main__":
    # Basic test
    planner = Planner()
    
    # Mock skill executor
    def mock_executor(skill_name: str, **kwargs):
        print(f"  Executing: {skill_name}")
        if skill_name == "unknown":
            raise ValueError("Unknown skill")
        return {"status": "success", "skill": skill_name}
    
    planner.register_skill("web_search", mock_executor)
    planner.register_skill("summarize", mock_executor)
    planner.register_skill("synthesize", mock_executor)
    
    # Create plan
    plan = planner.decompose_goal("Research AGI latest developments")
    print("Plan created:", json.dumps(plan.to_dict(), indent=2))
    
    # Execute
    result = planner.execute_plan(plan, mock_executor, enable_adaptation=True)
    print("\nExecution complete:")
    print(f"  Status: {result.status}")
    print(f"  Iterations: {result.iteration}")
    print(f"  Adaptations: {len(result.adaptation_history)}")
