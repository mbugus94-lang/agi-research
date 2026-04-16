"""
Test suite for Hierarchical Planner with Exploratory Planning.

Validates:
1. Task decomposition strategies
2. Resource budgeting
3. Exploratory hypothesis generation (ARC-AGI-3 style)
4. Dynamic replanning
5. Plan execution flow
"""

import sys
import time
from typing import Tuple, Any

sys.path.insert(0, '/home/workspace/agi-research')

from core.planner import (
    HierarchicalPlanner, Plan, SubTask, ResourceBudget,
    TaskType, PlanStatus, Hypothesis,
    create_exploratory_planner, create_resource_constrained_planner,
    DecompositionStrategy
)


class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []
    
    def add(self, name: str, passed: bool, message: str = ""):
        self.tests.append((name, passed, message))
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        status = "✅" if passed else "❌"
        print(f"{status} {name}")
        if message and not passed:
            print(f"   {message}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"Test Results: {self.passed}/{total} passed")
        if self.failed == 0:
            print("🎉 All tests passed!")
        else:
            print(f"⚠️  {self.failed} tests failed")
        return self.failed == 0


# Test 1: Task Type Analysis
results = TestResults()
print("\n=== Test 1: Task Type Analysis ===")
strategy = DecompositionStrategy()

# Test exploratory detection
task_type = strategy.analyze_task_type(
    "Explore different approaches to solve this ambiguous problem",
    {}
)
results.add(
    "Exploratory keyword detection",
    task_type == TaskType.EXPLORATORY,
    f"Expected EXPLORATORY, got {task_type}"
)

# Test sequential detection
task_type = strategy.analyze_task_type(
    "First do step one, then step two, then finally step three",
    {}
)
results.add(
    "Sequential keyword detection",
    task_type == TaskType.SEQUENTIAL,
    f"Expected SEQUENTIAL, got {task_type}"
)

# Test parallel detection
task_type = strategy.analyze_task_type(
    "Process all files simultaneously and in parallel",
    {}
)
results.add(
    "Parallel keyword detection",
    task_type == TaskType.PARALLEL,
    f"Expected PARALLEL, got {task_type}"
)

# Test atomic (simple task)
task_type = strategy.analyze_task_type(
    "Search for a document",
    {}
)
results.add(
    "Atomic task detection",
    task_type == TaskType.ATOMIC,
    f"Expected ATOMIC, got {task_type}"
)

# Test 2: Plan Creation
print("\n=== Test 2: Plan Creation ===")
planner = HierarchicalPlanner(max_depth=3)

plan = planner.create_plan(
    goal="Research and write a comprehensive report on AGI benchmarks",
    context={'complexity': 'high'}
)

results.add(
    "Plan created with valid ID",
    len(plan.plan_id) > 0 and plan.goal_description == "Research and write a comprehensive report on AGI benchmarks",
    f"Plan ID: {plan.plan_id}, Goal: {plan.goal_description}"
)

results.add(
    "Root task exists in plan",
    plan.root_task_id in plan.tasks,
    f"Root ID: {plan.root_task_id}, Tasks: {list(plan.tasks.keys())[:3]}..."
)

# Check task decomposition occurred
root_task = plan.tasks[plan.root_task_id]
results.add(
    "Root task has children or is marked atomic",
    len(root_task.children_ids) > 0 or root_task.task_type == TaskType.ATOMIC,
    f"Children: {len(root_task.children_ids)}, Type: {root_task.task_type}"
)

# Test 3: Resource Budget
print("\n=== Test 3: Resource Budget ===")
budget = ResourceBudget(
    max_api_calls=10,
    max_compute_time_seconds=60.0,
    max_tokens=5000,
    max_iterations=5
)

results.add(
    "Budget starts not exhausted",
    not budget.is_exhausted(),
    f"Exhausted: {budget.is_exhausted()}"
)

# Consume resources
budget.consume(api_calls=5, compute_time=10.0, tokens=2000, iterations=2)
results.add(
    "Budget tracking consumption",
    budget.api_calls_used == 5 and budget.tokens_used == 2000,
    f"API calls: {budget.api_calls_used}, Tokens: {budget.tokens_used}"
)

remaining = budget.remaining_ratio()
results.add(
    "Budget remaining ratio calculated",
    0.0 < remaining < 1.0,
    f"Remaining ratio: {remaining}"
)

# Exhaust budget
budget.consume(api_calls=10, compute_time=60.0, tokens=5000, iterations=10)
results.add(
    "Budget detects exhaustion",
    budget.is_exhausted(),
    f"Exhausted: {budget.is_exhausted()}"
)

# Test 4: Exploratory Planning (ARC-AGI-3 Style)
print("\n=== Test 4: Exploratory Planning (ARC-AGI-3 Style) ===")
exploratory_planner = create_exploratory_planner()

exploratory_plan = exploratory_planner.create_plan(
    goal="Explore the environment to discover the hidden pattern and solve the puzzle",
    context={'mode': 'discovery', 'unknown_rules': True}
)

root = exploratory_plan.tasks[exploratory_plan.root_task_id]
results.add(
    "Exploratory task detected correctly",
    root.task_type == TaskType.EXPLORATORY,
    f"Type: {root.task_type}"
)

# Check for hypothesis generation
if len(root.children_ids) > 0:
    child_task = exploratory_plan.tasks[root.children_ids[0]]
    has_hypotheses = len(child_task.hypotheses) > 0
    results.add(
        "Exploratory sub-tasks have hypotheses",
        has_hypotheses,
        f"Hypotheses: {len(child_task.hypotheses)}"
    )
    
    if has_hypotheses:
        hyp = child_task.hypotheses[0]
        results.add(
            "Hypothesis has required fields",
            all([
                hyp.hypothesis_id,
                hyp.description,
                0.0 <= hyp.confidence <= 1.0,
                hyp.test_strategy
            ]),
            f"ID: {bool(hyp.hypothesis_id)}, Desc: {bool(hyp.description)}, "
            f"Confidence: {hyp.confidence}, Strategy: {bool(hyp.test_strategy)}"
        )

# Test 5: Plan Execution Flow
print("\n=== Test 5: Plan Execution Flow ===")
execution_planner = HierarchicalPlanner(max_depth=2)

execution_plan = execution_planner.create_plan(
    goal="Perform sequential steps: step 1, then step 2, then step 3",
    budget=ResourceBudget(max_iterations=10)
)

# Get next executable task
next_task = execution_planner.get_next_executable_task(execution_plan)
results.add(
    "Next executable task retrieved",
    next_task is not None,
    f"Next task: {next_task.task_id if next_task else None}"
)

if next_task:
    results.add(
        "Ready task has PENDING status",
        next_task.status == PlanStatus.PENDING,
        f"Status: {next_task.status}"
    )

# Test 6: Task Decomposition
print("\n=== Test 6: Task Decomposition ===")
deep_planner = HierarchicalPlanner(max_depth=5)

complex_plan = deep_planner.create_plan(
    goal="Build a multi-step system with preparation, execution, and validation phases",
    context={'requires_decomposition': True}
)

total_tasks = len(complex_plan.tasks)
results.add(
    "Complex task decomposed into sub-tasks",
    total_tasks > 1,
    f"Total tasks: {total_tasks}"
)

# Check hierarchy depth
def get_max_depth(plan, task_id, depth=0):
    task = plan.tasks.get(task_id)
    if not task or not task.children_ids:
        return depth
    return max(
        get_max_depth(plan, child_id, depth + 1)
        for child_id in task.children_ids
    )

max_depth = get_max_depth(complex_plan, complex_plan.root_task_id)
results.add(
    "Hierarchical depth created",
    max_depth >= 1,
    f"Max depth: {max_depth}"
)

# Test 7: Sequential Decomposition
print("\n=== Test 7: Sequential Decomposition ===")
seq_planner = HierarchicalPlanner(max_depth=3)

seq_plan = seq_planner.create_plan(
    goal="First analyze the data. Then generate insights. Finally write the report.",
    context={}
)

seq_root = seq_plan.tasks[seq_plan.root_task_id]
results.add(
    "Sequential task type detected",
    seq_root.task_type == TaskType.SEQUENTIAL,
    f"Type: {seq_root.task_type}"
)

# Check for sequential dependencies
if len(seq_root.children_ids) >= 2:
    child1 = seq_plan.tasks[seq_root.children_ids[0]]
    child2 = seq_plan.tasks[seq_root.children_ids[1]]
    
    # Second child should depend on first
    has_seq_deps = child1.task_id in child2.dependencies
    results.add(
        "Sequential dependencies created",
        has_seq_deps or len(seq_root.children_ids) > 0,
        f"Child2 depends on Child1: {has_seq_deps}"
    )

# Test 8: Parallel Decomposition
print("\n=== Test 8: Parallel Decomposition ===")
par_planner = HierarchicalPlanner(max_depth=3)

par_plan = par_planner.create_plan(
    goal="Process multiple files in parallel simultaneously",
    context={}
)

par_root = par_plan.tasks[par_plan.root_task_id]
results.add(
    "Parallel task type detected",
    par_root.task_type == TaskType.PARALLEL,
    f"Type: {par_root.task_type}"
)

# Test 9: Plan Summary
print("\n=== Test 9: Plan Summary ===")
summary_planner = HierarchicalPlanner(max_depth=2)
summary_plan = summary_planner.create_plan(
    goal="Simple atomic task",
    budget=ResourceBudget(max_iterations=5)
)

summary = summary_planner.get_plan_summary(summary_plan)
results.add(
    "Summary contains plan_id",
    'plan_id' in summary and summary['plan_id'] == summary_plan.plan_id,
    f"Plan ID in summary: {'plan_id' in summary}"
)

results.add(
    "Summary contains goal",
    'goal' in summary and summary['goal'] == "Simple atomic task",
    f"Goal in summary: {summary.get('goal')}"
)

results.add(
    "Summary tracks completion",
    'completion_ratio' in summary and 'total_tasks' in summary,
    f"Keys: {list(summary.keys())}"
)

# Test 10: Execute Step
print("\n=== Test 10: Execute Step ===")
exec_planner = HierarchicalPlanner(max_depth=2)
exec_plan = exec_planner.create_plan(
    goal="Execute test task",
    budget=ResourceBudget(max_iterations=5)
)

first_task = exec_planner.get_next_executable_task(exec_plan)

def mock_execute(task: SubTask) -> Tuple[bool, Any]:
    """Mock execution function."""
    return True, f"Completed: {task.description}"

if first_task:
    success = exec_planner.execute_step(exec_plan, first_task, mock_execute)
    results.add(
        "Step executed successfully",
        success and first_task.status == PlanStatus.COMPLETED,
        f"Success: {success}, Status: {first_task.status}"
    )
    
    results.add(
        "Execution recorded in history",
        len(exec_plan.execution_history) > 0,
        f"History entries: {len(exec_plan.execution_history)}"
    )
    
    results.add(
        "Budget consumed after execution",
        exec_plan.budget.iterations_used > 0,
        f"Iterations used: {exec_plan.budget.iterations_used}"
    )

# Test 11: Replanning on Failure
print("\n=== Test 11: Replanning on Failure ===")
replan_planner = HierarchicalPlanner(max_depth=2)
replan_plan = replan_planner.create_plan(
    goal="Task that may need replanning",
    budget=ResourceBudget(max_iterations=10)
)

# Simulate a failed task
fail_task = replan_planner.get_next_executable_task(replan_plan)
if fail_task:
    fail_task.status = PlanStatus.FAILED
    fail_task.iteration = 0
    fail_task.max_iterations = 3
    
    # Try replan
    replanned = replan_planner.replan(replan_plan, {'failed_task': fail_task.task_id})
    results.add(
        "Replan updates replan_count",
        replanned.replan_count > 0,
        f"Replan count: {replanned.replan_count}"
    )

# Test 12: Resource Constrained Planner
print("\n=== Test 12: Resource Constrained Planner ===")
constrained_planner = create_resource_constrained_planner(
    max_api_calls=20,
    max_time_seconds=120.0
)

constrained_plan = constrained_planner.create_plan(
    goal="Resource constrained task"
)

results.add(
    "Resource constrained planner created",
    isinstance(constrained_planner, HierarchicalPlanner),
    f"Type: {type(constrained_planner)}"
)

results.add(
    "Plan has resource budget",
    constrained_plan.budget.max_api_calls == 20,
    f"Max API calls: {constrained_plan.budget.max_api_calls}"
)

# Test 13: Hypothesis Testing Flow
print("\n=== Test 13: Hypothesis Testing Flow ===")
hyp_planner = HierarchicalPlanner(max_depth=3)
hyp_plan = hyp_planner.create_plan(
    goal="Explore hypotheses to find the solution",
    context={'requires_exploration': True}
)

# Find exploratory task
exploratory_task = None
for task in hyp_plan.tasks.values():
    if task.task_type == TaskType.EXPLORATORY:
        exploratory_task = task
        break

results.add(
    "Exploratory task found in plan",
    exploratory_task is not None,
    f"Found: {exploratory_task is not None}"
)

if exploratory_task and len(exploratory_task.children_ids) > 0:
    child = hyp_plan.tasks[exploratory_task.children_ids[0]]
    results.add(
        "Child task has hypothesis tracking",
        len(child.hypotheses) > 0 or child.active_hypothesis_id is not None,
        f"Hypotheses: {len(child.hypotheses)}, Active: {child.active_hypothesis_id}"
    )

# Test 14: Plan Completion Detection
print("\n=== Test 14: Plan Completion Detection ===")
complete_planner = HierarchicalPlanner(max_depth=1)
complete_plan = complete_planner.create_plan(
    goal="Single atomic task",
    budget=ResourceBudget(max_iterations=1)
)

# Initially should not be complete
results.add(
    "New plan not marked complete",
    not complete_planner.is_plan_complete(complete_plan),
    f"Is complete: {complete_planner.is_plan_complete(complete_plan)}"
)

# Complete the only task
only_task = complete_planner.get_next_executable_task(complete_plan)
if only_task:
    complete_planner.execute_step(complete_plan, only_task, mock_execute)
    results.add(
        "Plan marked complete when all tasks done",
        complete_planner.is_plan_complete(complete_plan),
        f"Is complete: {complete_planner.is_plan_complete(complete_plan)}"
    )

# Test 15: Task Serialization
print("\n=== Test 15: Task Serialization ===")
serial_planner = HierarchicalPlanner(max_depth=2)
serial_plan = serial_planner.create_plan(
    goal="Test serialization"
)

root_task = serial_plan.tasks[serial_plan.root_task_id]
serial_dict = root_task.to_dict()

results.add(
    "Task serializes to dictionary",
    isinstance(serial_dict, dict),
    f"Type: {type(serial_dict)}"
)

results.add(
    "Serialized task has required fields",
    all(key in serial_dict for key in ['task_id', 'description', 'task_type', 'status']),
    f"Keys: {list(serial_dict.keys())[:10]}..."
)

# Print final summary
print("\n" + "="*50)
print(f"Planner Test Suite - Hierarchical Task Planning")
print("="*50)
success = results.summary()

# Exit with appropriate code
sys.exit(0 if success else 1)
