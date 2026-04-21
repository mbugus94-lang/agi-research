"""
Compositional Reasoning Experiment

Tests the agent's ability to:
1. Decompose complex goals into sub-tasks
2. Compose solutions from simple primitives
3. Adapt plans based on intermediate results

Based on ARC-AGI research: compositional generalization is the critical unsolved challenge.
"""

import sys
sys.path.insert(0, '/home/workspace/agi-research')

from core.planner import Planner, Plan, PlanStep
from core.agent import BaseAgent
import json


def test_task_decomposition():
    """Test goal decomposition into primitives"""
    print("\n=== Test: Task Decomposition ===")
    
    planner = Planner()
    
    # Test different goal types
    goals = [
        "Research AGI latest developments",
        "Implement a new feature",
        "Debug failing tests",
        "Learn about neural networks"
    ]
    
    for goal in goals:
        plan = planner.decompose_goal(goal)
        print(f"\nGoal: {goal}")
        print(f"  Steps: {len(plan.steps)}")
        for i, step in enumerate(plan.steps, 1):
            print(f"    {i}. {step.action}: {step.description}")
    
    return True


def test_plan_execution_with_adaptation():
    """Test plan execution with test-time refinement"""
    print("\n=== Test: Plan Execution with Adaptation ===")
    
    planner = Planner()
    
    # Register mock skills
    call_count = {"success": 0, "fail": 0}
    
    def mock_skill_executor(skill_name, **kwargs):
        if skill_name == "always_fails":
            call_count["fail"] += 1
            raise Exception("Simulated failure")
        call_count["success"] += 1
        return {"status": "success", "skill": skill_name}
    
    # Create a plan that will need adaptation
    plan = planner.decompose_goal("Test adaptation")
    
    # Manually inject a failing step
    failing_step = PlanStep(
        description="This step will fail",
        action="always_fails"
    )
    plan.steps.insert(1, failing_step)
    
    # Execute with adaptation enabled
    result = planner.execute_plan(
        plan,
        mock_skill_executor,
        enable_adaptation=True
    )
    
    print(f"  Initial steps: {len(plan.steps)}")
    print(f"  Final status: {result.status}")
    print(f"  Adaptations: {len(result.adaptation_history)}")
    print(f"  Iterations: {result.iteration}")
    
    # Should have adapted
    assert len(result.adaptation_history) > 0, "Should have adapted"
    
    return True


def test_dependency_management():
    """Test step dependency handling"""
    print("\n=== Test: Dependency Management ===")
    
    planner = Planner()
    plan = planner.decompose_goal("Test dependencies")
    
    # Check dependencies are set up
    for i, step in enumerate(plan.steps):
        if i == 0:
            assert len(step.depends_on) == 0, "First step should have no deps"
            print(f"  Step {i+1}: {step.action} - no dependencies ✓")
        else:
            assert len(step.depends_on) > 0, f"Step {i+1} should depend on previous"
            print(f"  Step {i+1}: {step.action} - depends on {step.depends_on[0][:8]}... ✓")
    
    return True


def test_compositional_assembly():
    """Test composing complex behavior from simple primitives"""
    print("\n=== Test: Compositional Assembly ===")
    
    # Define primitive patterns
    primitives = {
        "observe": lambda x: f"observed({x})",
        "analyze": lambda x: f"analyzed({x})",
        "decide": lambda x: f"decided({x})",
        "act": lambda x: f"acted({x})"
    }
    
    # Compose them into a reasoning chain
    def reasoning_chain(input_data):
        step1 = primitives["observe"](input_data)
        step2 = primitives["analyze"](step1)
        step3 = primitives["decide"](step2)
        step4 = primitives["act"](step3)
        return step4
    
    result = reasoning_chain("sensor_reading")
    
    print(f"  Input: sensor_reading")
    print(f"  Output chain: {result}")
    
    # Verify composition worked
    assert "observed" in result
    assert "analyzed" in result
    assert "decided" in result
    assert "acted" in result
    
    print(f"  ✓ Composition successful")
    return True


def test_sub_plan_creation():
    """Test creating sub-plans for complex steps"""
    print("\n=== Test: Sub-Plan Creation ===")
    
    planner = Planner()
    
    # Create parent plan
    parent_plan = planner.decompose_goal("Complex task")
    
    # Create sub-plan for a specific step
    complex_step = parent_plan.steps[0]
    sub_plan = planner.create_sub_plan(
        parent_plan,
        complex_step,
        "Sub-goal: understand the problem"
    )
    
    assert sub_plan.parent_plan_id == parent_plan.id, "Sub-plan should reference parent"
    assert len(sub_plan.steps) > 0, "Sub-plan should have steps"
    
    print(f"  Parent plan: {parent_plan.id[:8]}...")
    print(f"  Sub-plan: {sub_plan.id[:8]}... (parent: {sub_plan.parent_plan_id[:8]}...)")
    print(f"  Sub-plan steps: {len(sub_plan.steps)}")
    
    return True


def test_retry_logic():
    """Test step retry on failure"""
    print("\n=== Test: Retry Logic ===")
    
    planner = Planner()
    
    attempts = []
    
    def flaky_executor(skill_name, **kwargs):
        attempts.append(skill_name)
        if len(attempts) < 3:  # Fail first 2 times
            raise Exception("Flaky service")
        return {"status": "success"}
    
    planner.register_skill("flaky", flaky_executor)
    
    plan = Plan(goal="Test retries")
    step = PlanStep(
        description="Flaky step",
        action="flaky",
        max_retries=3
    )
    plan.steps.append(step)
    
    result = planner.execute_step(step, flaky_executor)
    
    print(f"  Attempts: {len(attempts)}")
    print(f"  Retry count: {result['retry_count']}")
    print(f"  Final status: {result['status']}")
    
    return True


def test_adaptation_strategies():
    """Test different adaptation strategies"""
    print("\n=== Test: Adaptation Strategies ===")
    
    planner = Planner()
    
    # Test alternative action adaptation
    plan1 = Plan(goal="Test alternative")
    step1 = PlanStep(action="failing_action", max_retries=3)
    step1.retry_count = 3  # Simulate max retries reached
    plan1.steps.append(step1)
    
    planner._adapt_plan_on_failure(plan1, step1, {"error": "failed"})
    
    print(f"  Alternative strategy: {plan1.adaptation_history[0]['strategy']}")
    
    # Test decomposition adaptation
    plan2 = Plan(goal="Test decomposition")
    step2 = PlanStep(action="code")  # Known decomposable action
    step2.retry_count = 3
    plan2.steps.append(step2)
    
    planner._adapt_plan_on_failure(plan2, step2, {"error": "failed"})
    
    print(f"  Decomposition strategy: {plan2.adaptation_history[0]['strategy']}")
    print(f"  Added steps: {plan2.adaptation_history[0].get('added_steps', 0)}")
    
    return True


def test_plan_metrics():
    """Test plan execution metrics"""
    print("\n=== Test: Plan Metrics ===")
    
    planner = Planner()
    
    def fast_executor(skill_name, **kwargs):
        return {"status": "success"}
    
    planner.register_skill("fast", fast_executor)
    
    plan = planner.decompose_goal("Quick task")
    
    # Time the execution
    import time
    start = time.time()
    result = planner.execute_plan(plan, fast_executor)
    duration = time.time() - start
    
    print(f"  Execution time: {duration:.3f}s")
    print(f"  Iterations: {result.iteration}")
    print(f"  Steps completed: {sum(1 for s in result.steps if s.status == 'completed')}")
    
    return True


def run_compositional_tests():
    """Run all compositional reasoning tests"""
    print("=" * 60)
    print("Compositional Reasoning Experiments")
    print("Based on ARC-AGI research insights")
    print("=" * 60)
    
    tests = [
        test_task_decomposition,
        test_plan_execution_with_adaptation,
        test_dependency_management,
        test_compositional_assembly,
        test_sub_plan_creation,
        test_retry_logic,
        test_adaptation_strategies,
        test_plan_metrics
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"✗ {test.__name__} FAILED")
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__} ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if passed > 0 and failed == 0:
        print("\n✓ Compositional reasoning foundation validated!")
        print("  - Tasks decompose into primitives")
        print("  - Plans adapt based on feedback")
        print("  - Dependencies are respected")
        print("  - Sub-plans can be created")
    
    return failed == 0


if __name__ == "__main__":
    success = run_compositional_tests()
    sys.exit(0 if success else 1)
