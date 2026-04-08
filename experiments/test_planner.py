"""
Test suite for Planner system.
Validates task decomposition, plan generation, and execution tracking.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.planner import Planner, Task, Plan, PlanStatus


def test_task_creation():
    """Test task creation and properties."""
    print("\n🧪 Test 1: Task Creation")
    
    task = Task(
        id="task_001",
        description="Search for information",
        action="web_search",
        parameters={"query": "AI research"},
        estimated_duration=5.0
    )
    
    assert task.id == "task_001", "Task ID should match"
    assert task.action == "web_search", "Action should match"
    assert task.status == "pending", "Initial status should be pending"
    
    print("   ✅ Task creation works correctly")
    return True


def test_task_dependencies():
    """Test task dependency management."""
    print("\n🧪 Test 2: Task Dependencies")
    
    task_a = Task(id="a", description="Step A", action="step_a")
    task_b = Task(id="b", description="Step B", action="step_b", dependencies=["a"])
    task_c = Task(id="c", description="Step C", action="step_c", dependencies=["a", "b"])
    
    # Check dependencies
    assert "a" in task_b.dependencies, "B should depend on A"
    assert task_a.can_execute(), "A can execute (no dependencies)"
    assert not task_b.can_execute(), "B cannot execute yet (A not done)"
    
    # Mark A complete
    task_a.mark_complete()
    assert task_b.can_execute(), "B can execute now (A is done)"
    
    print("   ✅ Task dependencies work correctly")
    return True


def test_plan_creation():
    """Test plan generation."""
    print("\n🧪 Test 3: Plan Creation")
    
    planner = Planner()
    
    tasks = [
        Task(id="1", description="Research", action="web_search", parameters={"query": "AGI"}),
        Task(id="2", description="Analyze", action="analyze", dependencies=["1"]),
        Task(id="3", description="Report", action="write", dependencies=["2"]),
    ]
    
    plan = planner.create_plan(
        goal="Research and report on AGI",
        tasks=tasks
    )
    
    assert plan.goal == "Research and report on AGI", "Goal should match"
    assert len(plan.tasks) == 3, "Should have 3 tasks"
    assert plan.status == PlanStatus.PENDING, "Initial plan status should be pending"
    
    print("   ✅ Plan creation works correctly")
    return True


def test_plan_execution_order():
    """Test plan execution respects dependencies."""
    print("\n🧪 Test 4: Plan Execution Order")
    
    planner = Planner()
    
    execution_order = []
    
    class MockTask(Task):
        def execute(self):
            execution_order.append(self.id)
            self.mark_complete()
            return {"result": f"Executed {self.id}"}
    
    tasks = [
        MockTask(id="prep", description="Prepare", action="prep"),
        MockTask(id="exec", description="Execute", action="exec", dependencies=["prep"]),
        MockTask(id="cleanup", description="Cleanup", action="cleanup", dependencies=["exec"]),
    ]
    
    plan = planner.create_plan("Test workflow", tasks)
    
    # Simulate execution (respecting dependencies)
    ready = [t for t in plan.tasks if t.can_execute()]
    while ready:
        task = ready[0]
        task.execute()
        ready = [t for t in plan.tasks if t.can_execute() and t.status != "completed"]
    
    assert execution_order == ["prep", "exec", "cleanup"], "Should execute in dependency order"
    
    print("   ✅ Plan execution order works correctly")
    return True


def test_plan_decomposition():
    """Test automatic task decomposition."""
    print("\n🧪 Test 5: Plan Decomposition")
    
    planner = Planner()
    
    # Simulate decomposing a high-level goal
    goal = "Build a web scraper"
    
    # In real implementation, this would use LLM
    # For testing, use manual decomposition
    subtasks = [
        Task(id="1", description="Design data structure", action="design"),
        Task(id="2", description="Implement fetcher", action="code", dependencies=["1"]),
        Task(id="3", description="Add parsing logic", action="code", dependencies=["2"]),
        Task(id="4", description="Write tests", action="test", dependencies=["3"]),
    ]
    
    plan = planner.create_plan(goal, subtasks)
    
    assert len(plan.tasks) == 4, "Should decompose into 4 tasks"
    assert plan.tasks[3].dependencies == ["3"], "Last task should depend on task 3"
    
    print("   ✅ Plan decomposition works correctly")
    return True


def test_plan_adaptation():
    """Test plan adaptation when tasks fail."""
    print("\n🧪 Test 6: Plan Adaptation")
    
    planner = Planner()
    
    tasks = [
        Task(id="1", description="Step 1", action="step1"),
        Task(id="2", description="Step 2", action="step2", dependencies=["1"]),
        Task(id="alt", description="Alternative", action="alt_step"),
    ]
    
    plan = planner.create_plan("Adaptable plan", tasks)
    
    # Mark task 1 as failed
    plan.tasks[0].mark_failed("API error")
    
    # Plan should detect failure
    assert plan.status == PlanStatus.FAILED, "Plan should show failed status"
    
    # Replan with alternative
    plan.replan(fallback_task_id="alt")
    
    # Alternative task should now be executable
    alt_task = next(t for t in plan.tasks if t.id == "alt")
    assert alt_task.can_execute(), "Alternative task should be ready"
    
    print("   ✅ Plan adaptation works correctly")
    return True


def run_all_tests():
    """Run all planner tests."""
    print("=" * 60)
    print("🧪 Planner System Test Suite")
    print("=" * 60)
    
    tests = [
        test_task_creation,
        test_task_dependencies,
        test_plan_creation,
        test_plan_execution_order,
        test_plan_decomposition,
        test_plan_adaptation,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"   ❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Results: {passed}/{passed+failed} tests passed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    
    if success:
        print("\n✅ All planner tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)
