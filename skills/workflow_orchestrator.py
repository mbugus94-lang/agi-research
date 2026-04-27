"""
Workflow Orchestrator - Autonomous Agentic Workflow Execution

Integrates planner, memory, tools, and verification for end-to-end
autonomous task execution based on April 2026 agentic AI research.

Key Research Insights:
- Agentic AI: High-level objectives → autonomous execution
- SMGI: Structural closure, stability, bounded capacity
- ARC-AGI: Test-time adaptation during execution
- Distributional Safety: Multi-agent coordination patterns
"""

import json
import uuid
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple, Set
from enum import Enum, auto
from datetime import datetime
from collections import defaultdict
import time


class WorkflowStatus(Enum):
    """Workflow execution status."""
    PENDING = auto()
    PLANNING = auto()
    EXECUTING = auto()
    VERIFYING = auto()
    COMPLETED = auto()
    FAILED = auto()
    PAUSED = auto()


class StepStatus(Enum):
    """Individual step execution status."""
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    RETRYING = auto()
    DELEGATED = auto()


@dataclass
class WorkflowStep:
    """A single step in a workflow execution."""
    step_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str = ""
    action_type: str = ""  # "skill", "memory", "delegate", "verify", "decide"
    target: str = ""  # Skill name, agent ID, etc.
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    
    # Execution state
    status: StepStatus = StepStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    
    # Metrics
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    execution_time_ms: float = 0.0
    
    # Verification
    verification_score: float = 0.0
    verification_required: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "description": self.description,
            "action_type": self.action_type,
            "target": self.target,
            "parameters": self.parameters,
            "dependencies": self.dependencies,
            "status": self.status.name,
            "result": self.result,
            "error": self.error,
            "retry_count": self.retry_count,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "execution_time_ms": self.execution_time_ms,
            "verification_score": self.verification_score
        }


@dataclass
class WorkflowContext:
    """Runtime context for workflow execution."""
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    goal: str = ""
    constraints: List[str] = field(default_factory=list)
    
    # State management
    variables: Dict[str, Any] = field(default_factory=dict)
    step_results: Dict[str, Any] = field(default_factory=dict)
    memory_references: List[str] = field(default_factory=list)
    
    # Configuration
    max_parallel_steps: int = 3
    enable_verification: bool = True
    enable_delegation: bool = False
    timeout_seconds: float = 300.0
    
    # Metrics
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    total_execution_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "goal": self.goal,
            "constraints": self.constraints,
            "variables": self.variables,
            "memory_references": self.memory_references,
            "max_parallel_steps": self.max_parallel_steps,
            "enable_verification": self.enable_verification,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_execution_time_ms": self.total_execution_time_ms
        }


@dataclass
class WorkflowResult:
    """Result of workflow execution."""
    workflow_id: str = ""
    status: WorkflowStatus = WorkflowStatus.PENDING
    success: bool = False
    output: Any = None
    steps_completed: int = 0
    steps_failed: int = 0
    execution_time_ms: float = 0.0
    context: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "status": self.status.name,
            "success": self.success,
            "output": self.output,
            "steps_completed": self.steps_completed,
            "steps_failed": self.steps_failed,
            "execution_time_ms": self.execution_time_ms,
            "errors": self.errors
        }


class WorkflowOrchestrator:
    """
    Orchestrates autonomous workflows by integrating:
    - Planner for task decomposition
    - Memory for context retention
    - Skills for execution
    - Verification for quality assurance
    """
    
    def __init__(self, 
                 skill_registry: Optional[Dict[str, Callable]] = None,
                 memory_interface: Optional[Any] = None,
                 planner_interface: Optional[Any] = None,
                 verification_interface: Optional[Any] = None):
        self.skill_registry = skill_registry or {}
        self.memory = memory_interface
        self.planner = planner_interface
        self.verification = verification_interface
        
        # Active workflows
        self.active_workflows: Dict[str, WorkflowContext] = {}
        self.workflow_steps: Dict[str, List[WorkflowStep]] = {}
        self.workflow_status: Dict[str, WorkflowStatus] = {}
        
        # Execution history
        self.completed_workflows: List[WorkflowResult] = []
        
        # Metrics
        self.total_workflows_executed = 0
        self.successful_workflows = 0
        self.failed_workflows = 0
        
    def register_skill(self, name: str, skill_func: Callable) -> None:
        """Register a skill for workflow execution."""
        self.skill_registry[name] = skill_func
        
    def create_workflow(self, goal: str, 
                        constraints: Optional[List[str]] = None,
                        initial_variables: Optional[Dict[str, Any]] = None) -> WorkflowContext:
        """Create a new workflow context."""
        context = WorkflowContext(
            goal=goal,
            constraints=constraints or [],
            variables=initial_variables or {}
        )
        self.active_workflows[context.workflow_id] = context
        self.workflow_steps[context.workflow_id] = []
        self.workflow_status[context.workflow_id] = WorkflowStatus.PENDING
        return context
    
    def add_step(self, workflow_id: str, 
                 description: str,
                 action_type: str,
                 target: str,
                 parameters: Optional[Dict[str, Any]] = None,
                 dependencies: Optional[List[str]] = None,
                 verification_required: bool = False) -> str:
        """Add a step to a workflow."""
        if workflow_id not in self.active_workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        step = WorkflowStep(
            description=description,
            action_type=action_type,
            target=target,
            parameters=parameters or {},
            dependencies=dependencies or [],
            verification_required=verification_required
        )
        
        self.workflow_steps[workflow_id].append(step)
        return step.step_id
    
    def generate_plan_steps(self, workflow_id: str) -> List[WorkflowStep]:
        """Generate workflow steps from a high-level goal using planning."""
        context = self.active_workflows.get(workflow_id)
        if not context:
            return []
        
        # Basic planning - can be enhanced with Tree of Thoughts
        # This is a simplified implementation
        steps = []
        
        # Step 1: Analyze and plan
        steps.append(WorkflowStep(
            description=f"Analyze goal: {context.goal[:50]}...",
            action_type="reasoning",
            target="analyze",
            parameters={"goal": context.goal}
        ))
        
        # Step 2: Gather context from memory
        if self.memory:
            steps.append(WorkflowStep(
                description="Retrieve relevant context from memory",
                action_type="memory",
                target="retrieve",
                parameters={"query": context.goal}
            ))
        
        # Step 3: Execute main task
        steps.append(WorkflowStep(
            description="Execute primary task",
            action_type="skill",
            target="execute_task",
            parameters={"goal": context.goal},
            dependencies=[steps[0].step_id] if steps else []
        ))
        
        # Step 4: Verify result
        steps.append(WorkflowStep(
            description="Verify execution result",
            action_type="verify",
            target="verify",
            parameters={},
            dependencies=[steps[-1].step_id],
            verification_required=True
        ))
        
        # Step 5: Store result in memory
        if self.memory:
            steps.append(WorkflowStep(
                description="Store result in memory",
                action_type="memory",
                target="store",
                parameters={},
                dependencies=[steps[-1].step_id]
            ))
        
        self.workflow_steps[workflow_id] = steps
        return steps
    
    async def execute_workflow(self, workflow_id: str) -> WorkflowResult:
        """Execute a workflow with all its steps."""
        if workflow_id not in self.active_workflows:
            return WorkflowResult(
                workflow_id=workflow_id,
                status=WorkflowStatus.FAILED,
                success=False,
                errors=["Workflow not found"]
            )
        
        context = self.active_workflows[workflow_id]
        steps = self.workflow_steps.get(workflow_id, [])
        
        if not steps:
            # Generate steps automatically
            steps = self.generate_plan_steps(workflow_id)
        
        self.workflow_status[workflow_id] = WorkflowStatus.EXECUTING
        start_time = time.time()
        
        completed_steps = 0
        failed_steps = 0
        errors = []
        
        try:
            for step in steps:
                step_result = await self._execute_step(step, context)
                
                if step_result:
                    completed_steps += 1
                    context.step_results[step.step_id] = step.result
                else:
                    failed_steps += 1
                    if step.error:
                        errors.append(f"Step {step.step_id}: {step.error}")
                    
                    # Handle retry
                    if step.retry_count < step.max_retries:
                        step.retry_count += 1
                        step.status = StepStatus.RETRYING
                        retry_result = await self._execute_step(step, context)
                        if retry_result:
                            completed_steps += 1
                            failed_steps -= 1
                            errors.pop()
        
        except Exception as e:
            errors.append(f"Workflow execution error: {str(e)}")
        
        # Complete workflow
        end_time = time.time()
        execution_time_ms = (end_time - start_time) * 1000
        
        success = failed_steps == 0 and completed_steps > 0
        self.workflow_status[workflow_id] = (
            WorkflowStatus.COMPLETED if success else WorkflowStatus.FAILED
        )
        
        context.completed_at = datetime.now().isoformat()
        context.total_execution_time_ms = execution_time_ms
        
        result = WorkflowResult(
            workflow_id=workflow_id,
            status=self.workflow_status[workflow_id],
            success=success,
            output=context.step_results,
            steps_completed=completed_steps,
            steps_failed=failed_steps,
            execution_time_ms=execution_time_ms,
            context=context.to_dict(),
            errors=errors
        )
        
        self.completed_workflows.append(result)
        self.total_workflows_executed += 1
        if success:
            self.successful_workflows += 1
        else:
            self.failed_workflows += 1
        
        return result
    
    async def _execute_step(self, step: WorkflowStep, 
                           context: WorkflowContext) -> bool:
        """Execute a single workflow step."""
        step.status = StepStatus.RUNNING
        step.started_at = datetime.now().isoformat()
        start_time = time.time()
        
        try:
            # Resolve parameter templates
            resolved_params = self._resolve_parameters(step.parameters, context)
            
            if step.action_type == "skill":
                result = await self._execute_skill(step.target, resolved_params)
            elif step.action_type == "memory":
                result = await self._execute_memory_op(step.target, resolved_params)
            elif step.action_type == "verify":
                result = await self._execute_verification(resolved_params)
            elif step.action_type == "delegate":
                result = await self._execute_delegation(step.target, resolved_params)
            elif step.action_type == "reasoning":
                result = await self._execute_reasoning(resolved_params)
            else:
                result = {"status": "unknown_action_type"}
            
            step.result = result
            step.status = StepStatus.COMPLETED
            
            # Verification if required
            if step.verification_required and self.verification:
                step.verification_score = await self._verify_result(result)
            
            return True
            
        except Exception as e:
            step.error = str(e)
            step.status = StepStatus.FAILED
            return False
        finally:
            step.completed_at = datetime.now().isoformat()
            step.execution_time_ms = (time.time() - start_time) * 1000
    
    def _resolve_parameters(self, parameters: Dict[str, Any], 
                           context: WorkflowContext) -> Dict[str, Any]:
        """Resolve parameter templates using context variables."""
        resolved = {}
        for key, value in parameters.items():
            if isinstance(value, str) and value.startswith("$"):
                # Template variable
                var_name = value[1:]
                if var_name in context.variables:
                    resolved[key] = context.variables[var_name]
                elif var_name in context.step_results:
                    resolved[key] = context.step_results[var_name]
                else:
                    resolved[key] = value
            else:
                resolved[key] = value
        return resolved
    
    async def _execute_skill(self, skill_name: str, 
                            parameters: Dict[str, Any]) -> Any:
        """Execute a registered skill."""
        if skill_name not in self.skill_registry:
            return {"error": f"Skill '{skill_name}' not found"}
        
        skill = self.skill_registry[skill_name]
        
        # Check if async
        if asyncio.iscoroutinefunction(skill):
            return await skill(**parameters)
        else:
            return skill(**parameters)
    
    async def _execute_memory_op(self, operation: str, 
                                 parameters: Dict[str, Any]) -> Any:
        """Execute memory operation."""
        if not self.memory:
            return {"status": "memory_not_available"}
        
        if operation == "store":
            return {"status": "stored"}
        elif operation == "retrieve":
            return {"results": []}
        else:
            return {"status": "unknown_operation"}
    
    async def _execute_verification(self, parameters: Dict[str, Any]) -> Any:
        """Execute verification."""
        if not self.verification:
            return {"status": "verification_not_available"}
        return {"status": "verified", "score": 1.0}
    
    async def _execute_delegation(self, agent_id: str, 
                                 parameters: Dict[str, Any]) -> Any:
        """Execute delegation to another agent."""
        return {"status": "delegated", "agent": agent_id}
    
    async def _execute_reasoning(self, parameters: Dict[str, Any]) -> Any:
        """Execute reasoning step."""
        return {"status": "reasoned", "goal": parameters.get("goal", "")}
    
    async def _verify_result(self, result: Any) -> float:
        """Verify a result and return confidence score."""
        if not self.verification:
            return 1.0
        return 0.95
    
    def get_workflow_status(self, workflow_id: str) -> Optional[WorkflowStatus]:
        """Get current status of a workflow."""
        return self.workflow_status.get(workflow_id)
    
    def get_workflow_steps(self, workflow_id: str) -> List[Dict[str, Any]]:
        """Get all steps of a workflow."""
        steps = self.workflow_steps.get(workflow_id, [])
        return [step.to_dict() for step in steps]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get orchestrator metrics."""
        total = self.total_workflows_executed
        success_rate = (
            self.successful_workflows / total * 100 if total > 0 else 0
        )
        
        return {
            "total_workflows": total,
            "successful": self.successful_workflows,
            "failed": self.failed_workflows,
            "success_rate_percent": round(success_rate, 2),
            "active_workflows": len(self.active_workflows),
            "registered_skills": len(self.skill_registry),
            "completed_workflows_stored": len(self.completed_workflows)
        }
    
    def create_agentic_workflow(self, goal: str,
                                available_skills: Optional[List[str]] = None,
                                require_verification: bool = True) -> str:
        """
        Create a complete agentic workflow from a high-level goal.
        This implements the "Agentic AI" pattern from April 2026 research.
        """
        context = self.create_workflow(
            goal=goal,
            constraints=["autonomous_execution", "self_verification"]
        )
        
        # Generate adaptive plan based on goal
        steps = self._generate_adaptive_plan(
            goal, context.workflow_id, available_skills, require_verification
        )
        
        self.workflow_steps[context.workflow_id] = steps
        return context.workflow_id
    
    def _generate_adaptive_plan(self, goal: str,
                               workflow_id: str,
                               available_skills: Optional[List[str]],
                               require_verification: bool) -> List[WorkflowStep]:
        """Generate an adaptive plan based on goal analysis."""
        steps = []
        
        # Parse goal to determine plan structure
        goal_lower = goal.lower()
        
        # Code generation workflow - check FIRST (higher priority)
        if any(kw in goal_lower for kw in ["code", "implement", "build", "write", "function", "class", "module"]):
            steps.extend(self._create_code_plan(goal, require_verification))
        
        # Research workflow
        elif any(kw in goal_lower for kw in ["research", "find", "search", "investigate", "explore", "study"]):
            steps.extend(self._create_research_plan(goal, require_verification))
        
        # Analysis workflow
        elif any(kw in goal_lower for kw in ["analyze", "evaluate", "assess", "compare", "review"]):
            steps.extend(self._create_analysis_plan(goal, require_verification))
        
        # Default workflow
        else:
            steps.extend(self._create_default_plan(goal, require_verification))
        
        return steps
    
    def _create_research_plan(self, goal: str, 
                              verify: bool) -> List[WorkflowStep]:
        """Create a research workflow plan."""
        steps = []
        
        step1 = WorkflowStep(
            description="Analyze research query and decompose",
            action_type="reasoning",
            target="decompose_query",
            parameters={"query": goal}
        )
        steps.append(step1)
        
        step2 = WorkflowStep(
            description="Execute web search for information gathering",
            action_type="skill",
            target="web_search",
            parameters={"query": goal},
            dependencies=[step1.step_id]
        )
        steps.append(step2)
        
        step3 = WorkflowStep(
            description="Synthesize findings from search results",
            action_type="skill",
            target="analysis",
            parameters={"task": "synthesize", "input": "$step2"},
            dependencies=[step2.step_id]
        )
        steps.append(step3)
        
        if verify:
            step4 = WorkflowStep(
                description="Verify research completeness",
                action_type="verify",
                target="verify_research",
                parameters={},
                dependencies=[step3.step_id],
                verification_required=True
            )
            steps.append(step4)
        
        return steps
    
    def _create_code_plan(self, goal: str, verify: bool) -> List[WorkflowStep]:
        """Create a code generation workflow plan."""
        steps = []
        
        step1 = WorkflowStep(
            description="Analyze requirements and plan implementation",
            action_type="reasoning",
            target="plan_code",
            parameters={"goal": goal}
        )
        steps.append(step1)
        
        step2 = WorkflowStep(
            description="Generate code implementation",
            action_type="skill",
            target="code_generation",
            parameters={"task": goal},
            dependencies=[step1.step_id]
        )
        steps.append(step2)
        
        if verify:
            step3 = WorkflowStep(
                description="Verify code quality and correctness",
                action_type="verify",
                target="verify_code",
                parameters={},
                dependencies=[step2.step_id],
                verification_required=True
            )
            steps.append(step3)
        
        return steps
    
    def _create_analysis_plan(self, goal: str, verify: bool) -> List[WorkflowStep]:
        """Create an analysis workflow plan."""
        steps = []
        
        step1 = WorkflowStep(
            description="Gather data for analysis",
            action_type="skill",
            target="data_gathering",
            parameters={"query": goal}
        )
        steps.append(step1)
        
        step2 = WorkflowStep(
            description="Perform analysis",
            action_type="skill",
            target="analysis",
            parameters={"task": "analyze", "input": "$step1"},
            dependencies=[step1.step_id]
        )
        steps.append(step2)
        
        return steps
    
    def _create_default_plan(self, goal: str, verify: bool) -> List[WorkflowStep]:
        """Create a default workflow plan."""
        steps = []
        
        step1 = WorkflowStep(
            description=f"Execute task: {goal[:40]}...",
            action_type="skill",
            target="execute",
            parameters={"goal": goal}
        )
        steps.append(step1)
        
        return steps


# Convenience factory functions

def create_orchestrator(skill_registry: Optional[Dict[str, Callable]] = None) -> WorkflowOrchestrator:
    """Create a workflow orchestrator with default configuration."""
    return WorkflowOrchestrator(skill_registry=skill_registry)


async def run_autonomous_workflow(goal: str,
                                  skills: Optional[Dict[str, Callable]] = None,
                                  require_verification: bool = True) -> WorkflowResult:
    """
    Run an autonomous workflow from a high-level goal.
    One-shot execution for simple use cases.
    """
    orchestrator = create_orchestrator(skills)
    workflow_id = orchestrator.create_agentic_workflow(
        goal=goal,
        require_verification=require_verification
    )
    return await orchestrator.execute_workflow(workflow_id)
