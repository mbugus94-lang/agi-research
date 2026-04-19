"""
Test suite for planner and reflection modules.
Validates the core planning and introspection capabilities.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.planner import (
    Task, TaskStatus, TaskPriority, Plan, PlanExecutor, HierarchicalPlanner,
    create_planner, create_simple_plan
)
from core.reflection import (
    ReflectionEngine, ReflectionScope, ReflectionType, PerformanceMetrics,
    ReflectivePlanner, create_reflection_engine, quick_reflect
)


class TestTaskManagement:
    """Test basic task operations."""
    
    def test_task_creation(self):
        """Test creating a task with all fields."""
        task = Task(
            id="test_1",
            description="Test task",
            status=TaskStatus.PENDING,
            priority=TaskPriority.HIGH,
            expected_output="result",
            tools_required=["tool1"],
            depends_on=["dep1"]
        )
        assert task.id == "test_1"
        assert task.description == "Test task"
        assert task.priority == TaskPriority.HIGH
        assert task.tools_required == ["tool1"]
        print("✅ Task creation")
        return True
    
    def test_task_serialization(self):
        """Test task to/from dict conversion."""
        task = Task(
            id="test_2",
            description="Serialization test",
            priority=TaskPriority.MEDIUM,
            expected_output="output",
            tools_required=["search", "analyze"]
        )
        data = task.to_dict()
        restored = Task.from_dict(data)
        assert restored.id == task.id
        assert restored.description == task.description
        assert restored.priority == task.priority
        print("✅ Task serialization")
        return True
    
    def test_task_status_transitions(self):
        """Test task status workflow."""
        task = Task(id="test_3", description="Status test")
        assert task.status == TaskStatus.PENDING
        
        # Ready → In Progress → Completed
        task.status = TaskStatus.READY
        task.started_at = __import__('datetime').datetime.now()
        task.status = TaskStatus.IN_PROGRESS
        task.status = TaskStatus.COMPLETED
        task.completed_at = __import__('datetime').datetime.now()
        
        assert task.status == TaskStatus.COMPLETED
        print("✅ Task status transitions")
        return True


class TestPlanExecution:
    """Test plan execution with dependencies."""
    
    def test_plan_creation(self):
        """Test creating a plan."""
        executor = PlanExecutor()
        plan = executor.create_plan("Test goal", "Test description", "sequential")
        assert plan.goal == "Test goal"
        assert plan.description == "Test description"
        assert plan.strategy == "sequential"
        assert plan.id is not None
        print("✅ Plan creation")
        return True
    
    def test_task_decomposition(self):
        """Test decomposing goal into tasks."""
        executor = PlanExecutor()
        plan = executor.create_plan("Research project")
        
        subtasks = [
            {"description": "Gather data", "priority": "HIGH", "expected_output": "raw_data"},
            {"description": "Analyze data", "priority": "HIGH", "depends_on": [0], "expected_output": "analysis"},
            {"description": "Write report", "priority": "MEDIUM", "depends_on": [1], "expected_output": "report"}
        ]
        
        tasks = executor.decompose_goal(plan, subtasks)
        assert len(tasks) == 3
        assert tasks[1].depends_on == [f"{plan.id}_0"]
        assert tasks[2].depends_on == [f"{plan.id}_1"]
        print("✅ Task decomposition")
        return True
    
    def test_dependency_tracking(self):
        """Test tracking task dependencies."""
        executor = PlanExecutor()
        plan = executor.create_plan("Build system")
        
        subtasks = [
            {"description": "Setup environment"},
            {"description": "Install dependencies", "depends_on": [0]},
            {"description": "Run tests", "depends_on": [1]}
        ]
        
        tasks = executor.decompose_goal(plan, subtasks)
        
        # Check blocks relationships
        assert plan.id + "_1" in plan.tasks[plan.id + "_0"].blocks
        assert plan.id + "_2" in plan.tasks[plan.id + "_1"].blocks
        print("✅ Dependency tracking")
        return True
    
    def test_ready_tasks_detection(self):
        """Test finding tasks ready to execute."""
        executor = PlanExecutor()
        plan = executor.create_plan("Multi-step task")
        
        subtasks = [
            {"description": "Step 1"},
            {"description": "Step 2", "depends_on": [0]},
            {"description": "Step 3", "depends_on": [1]}
        ]
        
        executor.decompose_goal(plan, subtasks)
        
        # Initially only step 1 should be ready
        ready = executor.get_ready_tasks(plan)
        assert len(ready) == 1
        assert ready[0].id == f"{plan.id}_0"
        
        # Complete step 1
        executor.complete_task(plan.tasks[f"{plan.id}_0"], "done")
        
        # Now step 2 should be ready
        ready = executor.get_ready_tasks(plan)
        assert len(ready) == 1
        assert ready[0].id == f"{plan.id}_1"
        print("✅ Ready tasks detection")
        return True
    
    def test_execution_order(self):
        """Test getting execution order with parallel stages."""
        executor = PlanExecutor()
        plan = executor.create_plan("Parallel execution test")
        
        subtasks = [
            {"description": "A1"},  # Stage 1
            {"description": "A2"},  # Stage 1 (parallel with A1)
            {"description": "B", "depends_on": [0, 1]},  # Stage 2 (depends on both)
            {"description": "C1", "depends_on": [2]},  # Stage 3
            {"description": "C2", "depends_on": [2]},  # Stage 3 (parallel with C1)
        ]
        
        executor.decompose_goal(plan, subtasks)
        order = executor.get_execution_order(plan)
        
        # Should have 3 stages (A1+A2 → B → C1+C2)
        assert len(order) == 3
        
        # Stage 1: A1, A2 (parallel, both have no dependencies)
        assert len(order[0]) == 2
        assert f"{plan.id}_0" in order[0]
        assert f"{plan.id}_1" in order[0]
        
        # Stage 2: B (depends on both A1 and A2)
        assert len(order[1]) == 1
        assert f"{plan.id}_2" in order[1]
        
        # Stage 3: C1, C2 (parallel, both depend on B)
        assert len(order[2]) == 2
        print("✅ Execution order with parallel stages")
        return True
    
    def test_replan_on_failure(self):
        """Test replanning for failed tasks."""
        executor = PlanExecutor()
        plan = executor.create_plan("Original plan")
        
        subtasks = [
            {"description": "Task 1"},
            {"description": "Task 2", "depends_on": [0]},
            {"description": "Task 3", "depends_on": [1]}
        ]
        
        executor.decompose_goal(plan, subtasks)
        
        # Fail task 1
        executor.fail_task(plan.tasks[f"{plan.id}_0"], "Connection error")
        
        # Create recovery plan
        recovery = executor.replan(plan, f"{plan.id}_0")
        assert recovery is not None
        assert "Recover from failure" in recovery.goal
        assert len(recovery.tasks) >= 2  # Analysis + retry
        print("✅ Replan on failure")
        return True


class TestHierarchicalPlanning:
    """Test three-level hierarchical planner."""
    
    def test_strategic_plan(self):
        """Test L0 strategic planning."""
        planner = create_planner()
        plan = planner.create_strategic_plan("Build AGI system")
        
        assert plan.goal == "Build AGI system"
        assert len(plan.tasks) == 4  # Default 4 phases
        
        task_ids = list(plan.tasks.keys())
        assert "Research" in plan.tasks[task_ids[0]].description or "information gathering" in plan.tasks[task_ids[0]].description
        print("✅ Strategic plan creation")
        return True
    
    def test_custom_strategic_phases(self):
        """Test strategic plan with custom phases."""
        planner = create_planner()
        custom_phases = [
            {"description": "Design", "priority": "HIGH"},
            {"description": "Implement", "priority": "HIGH", "depends_on": [0]},
            {"description": "Deploy", "priority": "MEDIUM", "depends_on": [1]}
        ]
        
        plan = planner.create_strategic_plan(
            "Custom project",
            context={"strategic_phases": custom_phases}
        )
        
        assert len(plan.tasks) == 3
        print("✅ Custom strategic phases")
        return True
    
    def test_planning_with_reflection(self):
        """Test planning informed by reflection data."""
        planner = create_planner()
        
        reflection_data = {
            "successful_approaches": ["Parallel execution for independent tasks"],
            "failed_approaches": ["Sequential planning for unrelated tasks"],
            "suggested_improvements": ["Add validation checkpoints"]
        }
        
        plan = planner.plan_with_reflection("Complex project", reflection_data)
        
        assert plan.id is not None
        assert len(plan.tasks) > 0
        
        # Should have validation step due to past failures
        has_validation = any(
            "validation" in t.description.lower() or "review" in t.description.lower()
            for t in plan.tasks.values()
        )
        assert has_validation
        print("✅ Planning with reflection")
        return True


class TestReflection:
    """Test reflection capabilities."""
    
    def test_task_reflection(self):
        """Test reflecting on single task."""
        engine = create_reflection_engine()
        
        trace = [
            {"step": "search", "tool": "web_search", "status": "success"},
            {"step": "analyze", "tool": "analyzer", "status": "success"}
        ]
        
        report = engine.reflect_on_task(
            task_description="Research AGI papers",
            task_result={"papers": 5},
            execution_trace=trace,
            success=True,
            quality_score=0.85
        )
        
        assert report.scope == ReflectionScope.TASK
        assert len(report.successes) > 0
        assert report.metrics is None  # Single task, no aggregate metrics
        print("✅ Task reflection")
        return True
    
    def test_task_failure_reflection(self):
        """Test reflection on failed task."""
        engine = create_reflection_engine()
        
        trace = [
            {"step": "search", "tool": "web_search", "error": "Connection timeout"}
        ]
        
        report = engine.reflect_on_task(
            task_description="Failed search",
            task_result=None,
            execution_trace=trace,
            success=False
        )
        
        assert len(report.failures) > 0
        assert len(report.root_causes) > 0
        assert len(report.recommendations) > 0
        print("✅ Task failure reflection")
        return True
    
    def test_plan_reflection(self):
        """Test reflecting on complete plan."""
        engine = create_reflection_engine()
        
        tasks_data = [
            {"status": "completed", "duration": 5.0, "quality_score": 0.9},
            {"status": "completed", "duration": 3.0, "quality_score": 0.8},
            {"status": "failed", "failure_type": "timeout"}
        ]
        
        report = engine.reflect_on_plan(
            plan_id="plan_123",
            plan_goal="Build feature",
            tasks_data=tasks_data,
            overall_success=False
        )
        
        assert report.scope == ReflectionScope.PLAN
        assert report.metrics is not None
        assert report.metrics.tasks_total == 3
        assert report.metrics.tasks_completed == 2
        assert report.metrics.tasks_failed == 1
        print("✅ Plan reflection with metrics")
        return True
    
    def test_session_reflection(self):
        """Test reflecting across multiple plans."""
        engine = create_reflection_engine()
        
        session_plans = [
            {
                "id": "plan_1",
                "tasks": [
                    {"status": "completed"},
                    {"status": "completed"}
                ]
            },
            {
                "id": "plan_2",
                "tasks": [
                    {"status": "completed"},
                    {"status": "failed", "failure_type": "api_error"}
                ]
            }
        ]
        
        report = engine.reflect_on_session(session_plans)
        
        assert report.scope == ReflectionScope.SESSION
        assert report.metrics.tasks_total == 4
        # Success rate should be identified as pattern
        assert len(report.patterns_identified) > 0
        print("✅ Session reflection")
        return True
    
    def test_improvement_proposals(self):
        """Test generating improvement proposals."""
        engine = create_reflection_engine()
        
        trace = [{"step": "action", "tool": "test_tool", "status": "failed"}]
        report = engine.reflect_on_task(
            task_description="Failing task",
            task_result=None,
            execution_trace=trace,
            success=False
        )
        
        proposals = engine.generate_improvement_proposals(report)
        
        assert len(proposals) > 0
        assert all("requires_review" in p for p in proposals)
        assert all("risk_level" in p for p in proposals)
        print("✅ Improvement proposals")
        return True
    
    def test_insights_for_planning(self):
        """Test extracting insights for future planning."""
        engine = create_reflection_engine()
        
        # Add some history
        for _ in range(3):
            trace = [{"step": "test", "status": "success"}]
            engine.reflect_on_task(
                task_description="Test task",
                task_result={},
                execution_trace=trace,
                success=True
            )
        
        insights = engine.get_insights_for_planning()
        
        assert "successful_approaches" in insights
        assert "failed_approaches" in insights
        assert "suggested_improvements" in insights
        print("✅ Insights for planning")
        return True
    
    def test_quick_reflect(self):
        """Test quick reflection convenience function."""
        report = quick_reflect(
            task_description="Simple task",
            success=True,
            notes=["Used efficient approach", "Completed quickly"]
        )
        
        assert report is not None
        assert report.scope == ReflectionScope.TASK
        assert len(report.patterns_identified) > 0  # Notes become patterns
        print("✅ Quick reflect")
        return True


class TestIntegration:
    """Test planner-reflection integration."""
    
    def test_reflective_planner_bridge(self):
        """Test ReflectivePlanner connects both systems."""
        from core.planner import HierarchicalPlanner
        
        planner = HierarchicalPlanner()
        reflection = ReflectionEngine()
        
        bridge = ReflectivePlanner(planner, reflection)
        
        # Mock execution function
        def mock_execute(plan):
            return {
                "success": True,
                "tasks": [
                    {"status": "completed", "duration": 1.0, "quality_score": 0.9}
                ]
            }
        
        result = bridge.plan_and_execute("Test goal", mock_execute, reflect=True)
        
        assert "plan" in result
        assert "result" in result
        assert "reflection" in result
        assert result["reflection"] is not None
        print("✅ ReflectivePlanner bridge")
        return True
    
    def test_end_to_end_workflow(self):
        """Test complete plan → execute → reflect flow."""
        executor = PlanExecutor()
        reflection = ReflectionEngine()
        
        # Create plan
        plan = executor.create_plan("Research project")
        subtasks = [
            {"description": "Search for papers"},
            {"description": "Summarize findings", "depends_on": [0]}
        ]
        tasks = executor.decompose_goal(plan, subtasks)
        
        # Execute
        for task in tasks:
            executor.start_task(task)
            executor.complete_task(task, {"result": "success"})
        
        executor.update_plan_status(plan)
        
        # Reflect
        tasks_data = [
            {"status": "completed", "duration": 2.0, "quality_score": 0.9},
            {"status": "completed", "duration": 1.5, "quality_score": 0.85}
        ]
        
        report = reflection.reflect_on_plan(
            plan_id=plan.id,
            plan_goal=plan.goal,
            tasks_data=tasks_data,
            overall_success=True
        )
        
        assert plan.status == "completed"
        assert report.metrics.avg_quality > 0.8
        print("✅ End-to-end workflow")
        return True


class TestSimplePlan:
    """Test convenience functions."""
    
    def test_create_simple_plan(self):
        """Test simple plan creation from step list."""
        steps = ["Research", "Design", "Implement", "Test"]
        plan = create_simple_plan("Build feature", steps)
        
        assert plan.goal == "Build feature"
        assert len(plan.tasks) == 4
        
        # Check sequential dependencies
        for i, task in enumerate(plan.tasks.values()):
            if i == 0:
                assert len(task.depends_on) == 0
            else:
                assert len(task.depends_on) == 1
        print("✅ Simple plan creation")
        return True


def run_all_tests():
    """Run complete test suite."""
    test_classes = [
        TestTaskManagement,
        TestPlanExecution,
        TestHierarchicalPlanning,
        TestReflection,
        TestIntegration,
        TestSimplePlan
    ]
    
    total_tests = 0
    passed_tests = 0
    
    for test_class in test_classes:
        print(f"\n{test_class.__name__}:")
        instance = test_class()
        
        for attr_name in dir(instance):
            if attr_name.startswith("test_"):
                total_tests += 1
                try:
                    getattr(instance, attr_name)()
                    passed_tests += 1
                except Exception as e:
                    print(f"❌ {attr_name}: {e}")
    
    print(f"\n{'='*50}")
    print(f"Results: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️ {total_tests - passed_tests} tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
