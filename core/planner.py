"""
Hierarchical Task Planner with Exploratory Planning and Resource Management.

Based on research insights from ARC-AGI-3 (arXiv:2603.24621v1):
- Agents fail at goal inference without explicit instructions
- Need for exploratory planning with hypothesis generation
- Resource-aware planning with budget management

Implements:
- Hierarchical task decomposition (SMGI structural theory inspired)
- Dynamic replanning with execution feedback loops
- Resource budgeting (compute, API calls, time)
- Exploratory hypothesis generation and testing
"""

from typing import Dict, List, Any, Optional, Callable, Tuple, Set, Union
from dataclasses import dataclass, field
from enum import Enum, auto
import json
import time
import uuid
from collections import defaultdict
import copy


class PlanStatus(Enum):
    """Status of a plan or sub-task."""
    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    BLOCKED = auto()  # Waiting for dependencies
    EXPLORING = auto()  # In hypothesis exploration phase


class TaskType(Enum):
    """Types of tasks for decomposition strategy."""
    ATOMIC = auto()  # Cannot be decomposed further
    SEQUENTIAL = auto()  # Sub-tasks must execute in order
    PARALLEL = auto()  # Sub-tasks can execute concurrently
    EXPLORATORY = auto()  # Requires hypothesis generation and testing
    CONDITIONAL = auto()  # Branch based on condition evaluation


@dataclass
class ResourceBudget:
    """Budget constraints for task execution."""
    max_api_calls: int = 100
    max_compute_time_seconds: float = 300.0
    max_tokens: int = 100000
    max_iterations: int = 50
    
    # Track actual usage
    api_calls_used: int = field(default=0)
    compute_time_used_seconds: float = field(default=0.0)
    tokens_used: int = field(default=0)
    iterations_used: int = field(default=0)
    
    def is_exhausted(self) -> bool:
        """Check if any budget limit is exceeded."""
        return (
            self.api_calls_used >= self.max_api_calls or
            self.compute_time_used_seconds >= self.max_compute_time_seconds or
            self.tokens_used >= self.max_tokens or
            self.iterations_used >= self.max_iterations
        )
    
    def remaining_ratio(self) -> float:
        """Calculate remaining budget ratio (0.0 to 1.0)."""
        ratios = [
            (self.max_api_calls - self.api_calls_used) / self.max_api_calls,
            (self.max_compute_time_seconds - self.compute_time_used_seconds) / self.max_compute_time_seconds,
            (self.max_tokens - self.tokens_used) / self.max_tokens,
            (self.max_iterations - self.iterations_used) / self.max_iterations
        ]
        return max(0.0, min(ratios))
    
    def consume(self, api_calls: int = 0, compute_time: float = 0.0, 
                tokens: int = 0, iterations: int = 0):
        """Record resource consumption."""
        self.api_calls_used += api_calls
        self.compute_time_used_seconds += compute_time
        self.tokens_used += tokens
        self.iterations_used += iterations


@dataclass
class Hypothesis:
    """Hypothesis for exploratory planning (ARC-AGI-3 style)."""
    hypothesis_id: str
    description: str
    confidence: float  # 0.0 to 1.0
    test_strategy: str
    expected_outcome: Any
    verification_criteria: List[str]
    
    # Execution tracking
    status: PlanStatus = field(default=PlanStatus.PENDING)
    test_results: List[Dict] = field(default_factory=list)
    actual_outcome: Any = field(default=None)
    validated: bool = field(default=False)


@dataclass
class SubTask:
    """Individual sub-task in a hierarchical plan."""
    task_id: str
    description: str
    task_type: TaskType
    status: PlanStatus = field(default=PlanStatus.PENDING)
    
    # Hierarchy
    parent_id: Optional[str] = field(default=None)
    children_ids: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    
    # Execution
    expected_output: Any = field(default=None)
    actual_output: Any = field(default=None)
    tool_requirements: List[str] = field(default_factory=list)
    
    # For exploratory tasks
    hypotheses: List[Hypothesis] = field(default_factory=list)
    active_hypothesis_id: Optional[str] = field(default=None)
    
    # Resource tracking
    estimated_cost: float = field(default=1.0)  # Relative cost estimate
    actual_cost: float = field(default=0.0)
    
    # Timing
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = field(default=None)
    completed_at: Optional[float] = field(default=None)
    
    # Iteration for replanning
    iteration: int = field(default=0)
    max_iterations: int = field(default=3)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'task_id': self.task_id,
            'description': self.description,
            'task_type': self.task_type.name,
            'status': self.status.name,
            'parent_id': self.parent_id,
            'children_ids': self.children_ids,
            'dependencies': self.dependencies,
            'expected_output': self.expected_output,
            'actual_output': self.actual_output,
            'tool_requirements': self.tool_requirements,
            'hypotheses': [self._hypothesis_to_dict(h) for h in self.hypotheses],
            'active_hypothesis_id': self.active_hypothesis_id,
            'estimated_cost': self.estimated_cost,
            'actual_cost': self.actual_cost,
            'created_at': self.created_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'iteration': self.iteration,
            'max_iterations': self.max_iterations
        }
    
    def _hypothesis_to_dict(self, h: Hypothesis) -> Dict:
        return {
            'hypothesis_id': h.hypothesis_id,
            'description': h.description,
            'confidence': h.confidence,
            'test_strategy': h.test_strategy,
            'expected_outcome': h.expected_outcome,
            'verification_criteria': h.verification_criteria,
            'status': h.status.name,
            'validated': h.validated
        }


@dataclass
class Plan:
    """Complete hierarchical plan with execution tracking."""
    plan_id: str
    goal_description: str
    root_task_id: str
    tasks: Dict[str, SubTask] = field(default_factory=dict)
    
    # Resource management
    budget: ResourceBudget = field(default_factory=ResourceBudget)
    
    # Execution state
    status: PlanStatus = field(default=PlanStatus.PENDING)
    current_task_id: Optional[str] = field(default=None)
    execution_history: List[Dict] = field(default_factory=list)
    
    # Replanning tracking
    replan_count: int = field(default=0)
    max_replans: int = field(default=5)
    
    # Timing
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = field(default=None)
    completed_at: Optional[float] = field(default=None)
    
    def get_task(self, task_id: str) -> Optional[SubTask]:
        """Get task by ID."""
        return self.tasks.get(task_id)
    
    def get_ready_tasks(self) -> List[SubTask]:
        """Get tasks that are ready to execute (dependencies met)."""
        ready = []
        for task in self.tasks.values():
            if task.status != PlanStatus.PENDING:
                continue
            
            # Check if all dependencies are completed
            deps_met = all(
                self.tasks.get(dep_id, SubTask(dep_id, "", TaskType.ATOMIC)).status == PlanStatus.COMPLETED
                for dep_id in task.dependencies
            )
            
            if deps_met:
                ready.append(task)
        
        return ready
    
    def get_completion_ratio(self) -> float:
        """Calculate plan completion ratio."""
        if not self.tasks:
            return 0.0
        
        completed = sum(1 for t in self.tasks.values() if t.status == PlanStatus.COMPLETED)
        return completed / len(self.tasks)


class DecompositionStrategy:
    """Strategies for decomposing tasks into sub-tasks."""
    
    @staticmethod
    def analyze_task_type(task_description: str, context: Dict[str, Any]) -> TaskType:
        """Analyze task to determine decomposition strategy."""
        # Keywords indicating exploratory nature (ARC-AGI-3 style)
        exploratory_keywords = [
            'explore', 'discover', 'investigate',
            'unknown', 'ambiguous', 'unclear', 'hypothesis', 
            'experiment', 'figure out'
        ]
        
        # Keywords indicating parallel potential
        parallel_keywords = [
            'multiple', 'batch', 'parallel', 'concurrent', 'independent',
            'simultaneously', 'at the same time'
        ]
        
        # Keywords indicating conditional logic
        conditional_keywords = [
            'condition', 'branch', 'decide', 'choose', 'alternative',
            'depending', 'based on', 'evaluate'
        ]
        
        # Keywords indicating sequential logic
        sequential_keywords = [
            'first', 'second', 'third', 'then', 'next', 'after', 'finally',
            'step by step', 'followed by', 'sequence'
        ]
        
        desc_lower = task_description.lower()
        
        # Check for exploratory keywords first
        if any(kw in desc_lower for kw in exploratory_keywords):
            return TaskType.EXPLORATORY
        
        # Check for conditional
        if any(kw in desc_lower for kw in conditional_keywords):
            return TaskType.CONDITIONAL
        
        # Check for sequential markers (prioritized over parallel)
        if any(kw in desc_lower for kw in sequential_keywords):
            return TaskType.SEQUENTIAL
        
        # Check for parallel
        if any(kw in desc_lower for kw in parallel_keywords):
            return TaskType.PARALLEL
        
        # Simple tasks with few words are atomic
        words = task_description.split()
        if len(words) <= 6:
            return TaskType.ATOMIC
        
        # Default to sequential for moderate complexity
        return TaskType.SEQUENTIAL
    
    @staticmethod
    def decompose_exploratory(task: SubTask, context: Dict[str, Any]) -> List[SubTask]:
        """Decompose exploratory task with hypothesis generation."""
        subtasks = []
        
        # Generate hypotheses for exploration
        hypotheses = [
            Hypothesis(
                hypothesis_id=f"{task.task_id}_hyp_1",
                description=f"Direct approach: {task.description}",
                confidence=0.6,
                test_strategy="Attempt direct execution",
                expected_outcome="Task completed successfully",
                verification_criteria=["Output meets requirements", "No errors"]
            ),
            Hypothesis(
                hypothesis_id=f"{task.task_id}_hyp_2",
                description=f"Iterative refinement approach",
                confidence=0.4,
                test_strategy="Break into smaller steps and iterate",
                expected_outcome="Progressive improvement",
                verification_criteria=["Each iteration improves", "Converges to solution"]
            ),
            Hypothesis(
                hypothesis_id=f"{task.task_id}_hyp_3",
                description=f"Alternative path exploration",
                confidence=0.3,
                test_strategy="Try different methodology",
                expected_outcome="Alternative valid solution",
                verification_criteria=["Different approach works", "Within constraints"]
            )
        ]
        
        # Create hypothesis testing sub-tasks
        for i, hyp in enumerate(hypotheses):
            subtask = SubTask(
                task_id=f"{task.task_id}_test_{i}",
                description=f"Test hypothesis: {hyp.description}",
                task_type=TaskType.ATOMIC,
                parent_id=task.task_id,
                hypotheses=[hyp],
                active_hypothesis_id=hyp.hypothesis_id,
                estimated_cost=1.5  # Exploratory tasks cost more
            )
            subtasks.append(subtask)
        
        # Create synthesis task
        synthesis = SubTask(
            task_id=f"{task.task_id}_synthesize",
            description="Synthesize findings from hypothesis tests",
            task_type=TaskType.ATOMIC,
            parent_id=task.task_id,
            dependencies=[f"{task.task_id}_test_{i}" for i in range(len(hypotheses))],
            estimated_cost=0.5
        )
        subtasks.append(synthesis)
        
        return subtasks
    
    @staticmethod
    def decompose_sequential(task: SubTask, context: Dict[str, Any]) -> List[SubTask]:
        """Decompose into sequential sub-tasks."""
        # Identify natural breakpoints in task description
        parts = []
        
        # Simple heuristic: split on common sequence markers
        current_part = task.description
        for marker in ['. Then', ', then', '. Next', ', next', '. After', '. Finally', ' then ']:
            if marker in current_part:
                split = current_part.split(marker, 1)
                if len(split) == 2:
                    parts.append(split[0])
                    current_part = split[1]
        
        if parts and current_part:
            parts.append(current_part)
        
        if len(parts) < 2:
            # Fallback: estimate 3 sequential steps
            parts = [f"Step {i+1} of: {task.description}" for i in range(3)]
        
        subtasks = []
        prev_id = None
        
        for i, part in enumerate(parts):
            subtask = SubTask(
                task_id=f"{task.task_id}_step_{i}",
                description=part.strip(),
                task_type=TaskType.ATOMIC,
                parent_id=task.task_id,
                estimated_cost=1.0 / len(parts)
            )
            
            if prev_id:
                subtask.dependencies.append(prev_id)
            
            subtasks.append(subtask)
            prev_id = subtask.task_id
        
        return subtasks
    
    @staticmethod
    def decompose_parallel(task: SubTask, context: Dict[str, Any]) -> List[SubTask]:
        """Decompose into parallel sub-tasks."""
        # Identify parallelizable components
        # Simple heuristic: split on 'and', 'also', commas with independent actions
        
        components = task.description.split(' and ')
        if len(components) < 2:
            components = [f"Aspect {i+1}: {task.description}" for i in range(2)]
        
        subtasks = []
        for i, component in enumerate(components):
            subtask = SubTask(
                task_id=f"{task.task_id}_parallel_{i}",
                description=component.strip(),
                task_type=TaskType.ATOMIC,
                parent_id=task.task_id,
                estimated_cost=1.0 / len(components)
            )
            subtasks.append(subtask)
        
        # Add aggregation task
        aggregation = SubTask(
            task_id=f"{task.task_id}_aggregate",
            description=f"Combine parallel results for: {task.description}",
            task_type=TaskType.ATOMIC,
            parent_id=task.task_id,
            dependencies=[s.task_id for s in subtasks],
            estimated_cost=0.3
        )
        subtasks.append(aggregation)
        
        return subtasks


class HierarchicalPlanner:
    """
    Hierarchical task planner with exploratory planning and resource management.
    
    Addresses ARC-AGI-3 findings:
    - Goal inference without explicit instructions
    - Hypothesis generation and testing
    - Resource-aware planning with budget management
    """
    
    def __init__(self, max_depth: int = 5):
        self.max_depth = max_depth
        self.plans: Dict[str, Plan] = {}
        self.decomposition_strategy = DecompositionStrategy()
        self.default_budget: Optional[ResourceBudget] = None
        
        # Statistics for learning
        self.decomposition_stats: Dict[TaskType, Dict] = defaultdict(
            lambda: {'attempts': 0, 'successes': 0, 'avg_cost': 0.0}
        )
    
    def create_plan(self, goal: str, budget: Optional[ResourceBudget] = None,
                    context: Optional[Dict] = None) -> Plan:
        """Create a hierarchical plan for the given goal."""
        plan_id = str(uuid.uuid4())[:8]
        
        # Use provided budget, default budget, or create new
        plan_budget = budget or self.default_budget or ResourceBudget()
        
        # Create root task
        root_task = SubTask(
            task_id=f"{plan_id}_root",
            description=goal,
            task_type=self.decomposition_strategy.analyze_task_type(goal, context or {})
        )
        
        plan = Plan(
            plan_id=plan_id,
            goal_description=goal,
            root_task_id=root_task.task_id,
            budget=copy.deepcopy(plan_budget)
        )
        
        plan.tasks[root_task.task_id] = root_task
        
        # Decompose recursively
        self._decompose_recursive(plan, root_task, 0, context or {})
        
        self.plans[plan_id] = plan
        
        return plan
    
    def _decompose_recursive(self, plan: Plan, task: SubTask, 
                            depth: int, context: Dict):
        """Recursively decompose task into sub-tasks."""
        if depth >= self.max_depth:
            task.task_type = TaskType.ATOMIC
            return
        
        # Skip decomposition for atomic tasks
        if task.task_type == TaskType.ATOMIC:
            return
        
        # Decompose based on task type
        if task.task_type == TaskType.EXPLORATORY:
            subtasks = self.decomposition_strategy.decompose_exploratory(task, context)
        elif task.task_type == TaskType.SEQUENTIAL:
            subtasks = self.decomposition_strategy.decompose_sequential(task, context)
        elif task.task_type == TaskType.PARALLEL:
            subtasks = self.decomposition_strategy.decompose_parallel(task, context)
        else:
            # Default: treat as atomic
            task.task_type = TaskType.ATOMIC
            return
        
        # Add sub-tasks to plan
        for subtask in subtasks:
            plan.tasks[subtask.task_id] = subtask
            task.children_ids.append(subtask.task_id)
        
        # Recursively decompose sub-tasks (with depth limit)
        for subtask in subtasks:
            if subtask.task_type != TaskType.ATOMIC:
                self._decompose_recursive(plan, subtask, depth + 1, context)
    
    def get_next_executable_task(self, plan: Plan) -> Optional[SubTask]:
        """Get the next task ready for execution."""
        ready_tasks = plan.get_ready_tasks()
        
        if not ready_tasks:
            return None
        
        # Prioritize by type and cost
        # 1. Non-exploratory tasks first (lower risk)
        # 2. Lower estimated cost first (fail fast)
        ready_tasks.sort(key=lambda t: (
            t.task_type == TaskType.EXPLORATORY,  # False < True
            t.estimated_cost
        ))
        
        return ready_tasks[0] if ready_tasks else None
    
    def execute_step(self, plan: Plan, task: SubTask, 
                    execute_fn: Callable[[SubTask], Tuple[bool, Any]]) -> bool:
        """Execute a single step and update plan state."""
        if plan.budget.is_exhausted():
            return False
        
        # Mark task as in progress
        task.status = PlanStatus.IN_PROGRESS
        task.started_at = time.time()
        plan.current_task_id = task.task_id
        
        if plan.started_at is None:
            plan.started_at = time.time()
        
        # Consume budget
        plan.budget.consume(
            api_calls=1,
            compute_time=0.1,
            tokens=1000,
            iterations=1
        )
        
        # Execute
        start_time = time.time()
        try:
            success, output = execute_fn(task)
            execution_time = time.time() - start_time
            
            task.actual_output = output
            task.actual_cost = execution_time
            task.completed_at = time.time()
            
            if success:
                task.status = PlanStatus.COMPLETED
            else:
                task.status = PlanStatus.FAILED
                
                # Check if we should retry with replanning
                if task.iteration < task.max_iterations:
                    return self._handle_failure_with_replan(plan, task, context={})
            
            # Record execution
            plan.execution_history.append({
                'task_id': task.task_id,
                'success': success,
                'execution_time': execution_time,
                'timestamp': time.time()
            })
            
            return success
            
        except Exception as e:
            task.status = PlanStatus.FAILED
            plan.execution_history.append({
                'task_id': task.task_id,
                'success': False,
                'error': str(e),
                'timestamp': time.time()
            })
            return False
    
    def _handle_failure_with_replan(self, plan: Plan, task: SubTask, 
                                   context: Dict) -> bool:
        """Handle task failure with dynamic replanning."""
        if plan.replan_count >= plan.max_replans:
            return False
        
        plan.replan_count += 1
        task.iteration += 1
        
        # Generate alternative approach
        # Simplified: mark as exploratory and add new hypothesis
        task.task_type = TaskType.EXPLORATORY
        
        new_hypothesis = Hypothesis(
            hypothesis_id=f"{task.task_id}_replan_{task.iteration}",
            description=f"Alternative approach (replan #{task.iteration})",
            confidence=0.5 - (task.iteration * 0.1),  # Decreasing confidence
            test_strategy=f"Revised execution strategy",
            expected_outcome="Successful completion",
            verification_criteria=["Output correct", "No exceptions"]
        )
        
        task.hypotheses.append(new_hypothesis)
        task.active_hypothesis_id = new_hypothesis.hypothesis_id
        task.status = PlanStatus.PENDING  # Reset to try again
        
        return True  # Will retry
    
    def replan(self, plan: Plan, feedback: Dict[str, Any]) -> Plan:
        """Create a revised plan based on execution feedback."""
        if plan.replan_count >= plan.max_replans:
            return plan
        
        plan.replan_count += 1
        
        # Analyze failed tasks
        failed_tasks = [
            t for t in plan.tasks.values() 
            if t.status == PlanStatus.FAILED
        ]
        
        # Create new sub-tasks for failed ones with different strategies
        for failed_task in failed_tasks:
            # Change task type for alternative approach
            if failed_task.task_type == TaskType.ATOMIC:
                failed_task.task_type = TaskType.EXPLORATORY
            
            # Reset for retry
            failed_task.status = PlanStatus.PENDING
            failed_task.iteration += 1
        
        return plan
    
    def is_plan_complete(self, plan: Plan) -> bool:
        """Check if all tasks in plan are completed or failed."""
        return all(
            t.status in [PlanStatus.COMPLETED, PlanStatus.FAILED]
            for t in plan.tasks.values()
        )
    
    def get_plan_summary(self, plan: Plan) -> Dict[str, Any]:
        """Get a summary of plan status."""
        total_tasks = len(plan.tasks)
        completed = sum(1 for t in plan.tasks.values() if t.status == PlanStatus.COMPLETED)
        failed = sum(1 for t in plan.tasks.values() if t.status == PlanStatus.FAILED)
        pending = sum(1 for t in plan.tasks.values() if t.status == PlanStatus.PENDING)
        in_progress = sum(1 for t in plan.tasks.values() if t.status == PlanStatus.IN_PROGRESS)
        
        return {
            'plan_id': plan.plan_id,
            'goal': plan.goal_description,
            'status': plan.status.name,
            'completion_ratio': plan.get_completion_ratio(),
            'total_tasks': total_tasks,
            'completed': completed,
            'failed': failed,
            'pending': pending,
            'in_progress': in_progress,
            'replan_count': plan.replan_count,
            'budget_remaining': plan.budget.remaining_ratio(),
            'execution_time': (
                time.time() - plan.started_at if plan.started_at else 0
            )
        }
    
    def get_learning_stats(self) -> Dict[str, Any]:
        """Get statistics for learning from past decompositions."""
        return {
            task_type.name: {
                'attempts': stats['attempts'],
                'successes': stats['successes'],
                'success_rate': (
                    stats['successes'] / stats['attempts'] 
                    if stats['attempts'] > 0 else 0
                ),
                'avg_cost': stats['avg_cost']
            }
            for task_type, stats in self.decomposition_stats.items()
        }


def create_exploratory_planner(budget: Optional[ResourceBudget] = None) -> HierarchicalPlanner:
    """Create a planner optimized for exploratory tasks (ARC-AGI-3 style)."""
    planner = HierarchicalPlanner(max_depth=4)
    if budget:
        planner.default_budget = budget
    return planner


def create_resource_constrained_planner(
    max_api_calls: int = 50,
    max_time_seconds: float = 180.0
) -> HierarchicalPlanner:
    """Create a planner with tight resource constraints."""
    planner = HierarchicalPlanner(max_depth=3)
    budget = ResourceBudget(
        max_api_calls=max_api_calls,
        max_compute_time_seconds=max_time_seconds,
        max_tokens=50000,
        max_iterations=25
    )
    planner.default_budget = budget
    return planner
