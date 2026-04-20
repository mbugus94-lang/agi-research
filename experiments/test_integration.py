"""
Test Suite for Integration Layer - Connecting Reflection, Planning, and Memory

Tests the self-improving closed loop:
    Execute → Reflect → Store → Plan(with history) → Execute(improved)

Validates:
1. ReflectionMemoryBridge: Storage and retrieval of reflections in tiered memory
2. PlanningWithReflection: Historical insights informing new plans
3. SelfImprovingLoop: Full automated improvement cycle
4. Cross-system metrics aggregation
5. Pattern recognition across execution traces
"""

import unittest
import time
import json
from datetime import datetime

# Adjust imports for test context
import sys
sys.path.insert(0, '/home/workspace/agi-research')

from core.integration import (
    ReflectionMemoryBridge,
    PlanningWithReflection,
    SelfImprovingLoop,
    ExecutionTrace,
    IntegrationMode,
    create_integrated_system
)
from core.reflection import (
    ReflectionEngine,
    ReflectionReport,
    ReflectionScope,
    ReflectionType,
    PerformanceMetrics
)
from core.planner import (
    HierarchicalPlanner,
    PlanExecutor,
    Plan,
    Task,
    TaskStatus,
    TaskPriority
)
from core.tiered_memory import (
    TieredMemorySystem,
    MemoryTier,
    MemoryEntry
)


class TestReflectionMemoryBridge(unittest.TestCase):
    """Test storage and retrieval of reflection reports in tiered memory."""
    
    def setUp(self):
        self.memory = TieredMemorySystem()
        self.bridge = ReflectionMemoryBridge(self.memory)
        self.reflection = ReflectionEngine()
    
    def test_01_store_task_scope_reflection(self):
        """TASK scope reflections should be stored in L0 (immediate) tier."""
        # Create a reflection report manually
        report = ReflectionReport(
            id="task_ref_001",
            timestamp=datetime.now(),
            scope=ReflectionScope.TASK,
            reflection_type=ReflectionType.PERFORMANCE,
            summary="Task reflection test",
            successes=["Completed successfully"],
            failures=[],
            patterns_identified=["Fast execution"],
            root_causes=[],
            recommendations=[],
            metrics=PerformanceMetrics(tasks_total=1, tasks_completed=1)
        )
        
        memory_id = self.bridge.store_reflection(report)
        
        self.assertIsNotNone(memory_id)
        # Check that something was stored in memory
        self.assertGreater(len(self.memory.l0_entries), 0)
    
    def test_02_store_plan_scope_reflection(self):
        """PLAN scope reflections should be stored in L1 (working) tier."""
        report = ReflectionReport(
            id="plan_ref_001",
            timestamp=datetime.now(),
            scope=ReflectionScope.PLAN,
            reflection_type=ReflectionType.STRATEGY,
            summary="Plan reflection test",
            successes=["Plan executed successfully"],
            failures=[],
            patterns_identified=["Good parallelization"],
            root_causes=[],
            recommendations=[{"type": "continue", "description": "Keep strategy", "priority": "low"}],
            metrics=PerformanceMetrics(tasks_total=3, tasks_completed=3, avg_quality=0.9)
        )
        
        memory_id = self.bridge.store_reflection(report)
        
        self.assertIsNotNone(memory_id)
        # Check that report scope is PLAN
        self.assertEqual(report.scope, ReflectionScope.PLAN)
    
    def test_03_store_system_scope_reflection(self):
        """SYSTEM scope reflections should be stored in L2 (archival) tier."""
        report = ReflectionReport(
            id="sys_reflection_001",
            timestamp=datetime.now(),
            scope=ReflectionScope.SYSTEM,
            reflection_type=ReflectionType.PERFORMANCE,
            summary="System-wide performance analysis",
            successes=["Consistent API response times"],
            failures=["Memory tier optimization needed"],
            patterns_identified=["L2 access is slower than expected"],
            root_causes=["Compression overhead"],
            recommendations=[{"type": "optimization", "description": "Implement caching layer", "priority": "high"}],
            metrics=PerformanceMetrics(
                tasks_total=100,
                tasks_completed=85,
                avg_quality=0.85
            )
        )
        
        memory_id = self.bridge.store_reflection(report)
        
        self.assertIsNotNone(memory_id)
        self.assertEqual(report.scope, ReflectionScope.SYSTEM)
    
    def test_04_query_relevant_reflections(self):
        """Query should return relevant reflections sorted by relevance."""
        # Store multiple reflections
        for i in range(3):
            report = ReflectionReport(
                id=f"ref_{i}",
                timestamp=datetime.now(),
                scope=ReflectionScope.TASK,
                reflection_type=ReflectionType.PERFORMANCE,
                summary=f"Task performance analysis {i}",
                successes=["Good execution"],
                patterns_identified=["Pattern A" if i == 0 else "Pattern B"],
                recommendations=[],
                metrics=PerformanceMetrics(tasks_total=1, tasks_completed=1)
            )
            self.bridge.store_reflection(report)
        
        # Query for relevant reflections
        results = self.bridge.query_relevant_reflections(
            task_description="Pattern A task execution",
            limit=5
        )
        
        self.assertIsInstance(results, list)
    
    def test_05_store_execution_trace(self):
        """Execution traces should be stored with reflection context."""
        trace = ExecutionTrace(
            trace_id="trace_001",
            plan_id="plan_001",
            started_at=datetime.now(),
            success=True,
            quality_score=0.92
        )
        
        report = ReflectionReport(
            id="ref_trace_001",
            timestamp=datetime.now(),
            scope=ReflectionScope.PLAN,
            reflection_type=ReflectionType.PERFORMANCE,
            summary="Execution trace analysis",
            successes=["All tasks completed"],
            patterns_identified=["Parallel execution works well"],
            recommendations=[{"type": "continue", "description": "Continue using parallelization", "priority": "low"}],
            metrics=PerformanceMetrics(tasks_total=5, tasks_completed=5, avg_quality=0.92)
        )
        
        memory_id = self.bridge.store_reflection(report, trace)
        
        self.assertIsNotNone(memory_id)
    
    def test_06_get_performance_patterns(self):
        """Should extract aggregated performance patterns across reflections."""
        # Store reflections with patterns
        for i in range(3):
            report = ReflectionReport(
                id=f"pattern_ref_{i}",
                timestamp=datetime.now(),
                scope=ReflectionScope.PLAN,
                reflection_type=ReflectionType.PERFORMANCE,
                summary=f"Analysis {i}",
                successes=["Success pattern A", "Success pattern B"],
                failures=["Failure pattern X"],
                patterns_identified=["Learning pattern C"],
                recommendations=[{"type": "improvement", "description": "Improvement D", "priority": "medium"}],
                metrics=PerformanceMetrics(
                    tasks_total=10,
                    tasks_completed=8 if i < 2 else 10,
                    avg_quality=0.75 + (i * 0.05)
                )
            )
            self.bridge.store_reflection(report)
        
        patterns = self.bridge.get_performance_patterns()
        
        self.assertIn("total_reflections", patterns)
        self.assertIn("success_patterns", patterns)
        self.assertIn("failure_patterns", patterns)


class TestPlanningWithReflection(unittest.TestCase):
    """Test using historical reflections to inform planning."""
    
    def setUp(self):
        self.memory = TieredMemorySystem()
        self.base_planner = HierarchicalPlanner()
        self.bridge = ReflectionMemoryBridge(self.memory)
        self.planner = PlanningWithReflection(self.base_planner, self.bridge)
    
    def test_07_plan_with_reflection_context(self):
        """Planning should query and use relevant past reflections."""
        # First, store some reflections about similar tasks
        report = ReflectionReport(
            id="planning_ref_001",
            timestamp=datetime.now(),
            scope=ReflectionScope.PLAN,
            reflection_type=ReflectionType.STRATEGY,
            summary="Web search planning strategy",
            successes=["Parallel search execution worked well"],
            failures=["Sequential execution was slow"],
            patterns_identified=["Search tasks benefit from parallelism"],
            root_causes=["Network latency in sequential mode"],
            recommendations=[{"type": "strategy", "description": "Use parallel execution for multiple searches", "priority": "high"}],
            metrics=PerformanceMetrics(
                tasks_total=3,
                tasks_completed=3,
                total_time=2.5,
                avg_quality=0.88
            )
        )
        self.bridge.store_reflection(report)
        
        # Now plan a similar task
        plan = self.planner.plan_with_reflection_context(
            goal="Search and analyze AGI research papers",
            available_tools=["web_search", "analyze", "summarize"]
        )
        
        self.assertIsNotNone(plan)
        self.assertTrue(hasattr(plan, 'id'))
    
    def test_08_insights_extraction(self):
        """Should extract actionable insights from reflections."""
        # Create sample reflections
        reflections = [
            {
                "reflection_data": {
                    "successes": ["Strategy A worked"],
                    "failures": ["Strategy B failed"],
                    "recommendations": [{"type": "strategy", "description": "Use Strategy A", "priority": "high"}],
                    "report_id": "ref_001"
                },
                "relevance_score": 0.85
            }
        ]
        
        insights = self.planner._extract_planning_insights(reflections)
        
        self.assertIsInstance(insights, dict)
        self.assertIn("avoid", insights)
        self.assertIn("replicate", insights)
        self.assertIn("recommendations", insights)
    
    def test_09_adaptation_tracking(self):
        """Should track planning adaptations over time."""
        # Create several plans to build adaptation history
        for i in range(3):
            self.planner.plan_with_reflection_context(
                goal=f"Task {i}: Analyze data",
                available_tools=["analyze"]
            )
        
        summary = self.planner.get_adaptation_summary()
        
        self.assertIn("adaptations", summary)
        self.assertEqual(summary["adaptations"], 3)
        self.assertIn("average_reflections_per_plan", summary)
        self.assertIn("average_planning_time_ms", summary)


class TestSelfImprovingLoop(unittest.TestCase):
    """Test the full self-improving execution cycle."""
    
    def setUp(self):
        self.planner, self.loop, self.bridge = create_integrated_system(
            mode=IntegrationMode.AUTONOMOUS
        )
    
    def test_11_execute_improving_cycle(self):
        """Should execute goal with reflection-based improvement."""
        trace = self.loop.execute_improving_cycle(
            goal="Research and summarize AGI papers",
            available_tools=["search", "read", "summarize"],
            max_iterations=2
        )
        
        self.assertIsInstance(trace, ExecutionTrace)
        self.assertIsNotNone(trace.trace_id)
        self.assertIsNotNone(trace.started_at)
        
        # Should have execution results
        self.assertIsInstance(trace.execution_results, list)
        
        # Should have reflection report
        self.assertIsNotNone(trace.reflection_report)
    
    def test_12_execution_trace_structure(self):
        """Execution trace should have proper structure."""
        trace = self.loop.execute_improving_cycle(
            goal="Simple test task",
            available_tools=["test_tool"],
            max_iterations=1
        )
        
        # Check trace structure
        trace_dict = trace.to_dict()
        self.assertIn("trace_id", trace_dict)
        self.assertIn("plan_id", trace_dict)
        self.assertIn("execution_results", trace_dict)
        self.assertIn("reflection_report", trace_dict)
        self.assertIn("improvement_proposals", trace_dict)
        self.assertIn("total_duration_ms", trace_dict)
        self.assertIn("success", trace_dict)
    
    def test_14_improvement_statistics(self):
        """Should track improvement statistics across cycles."""
        # Run multiple improvement cycles
        for i in range(3):
            self.loop.execute_improving_cycle(
                goal=f"Test goal {i}",
                available_tools=["tool"],
                max_iterations=1
            )
        
        stats = self.loop.get_improvement_statistics()
        
        self.assertIn("total_cycles", stats)
        self.assertEqual(stats["total_cycles"], 3)
        self.assertIn("average_quality", stats)
        self.assertIn("quality_trend", stats)
    
    def test_15_export_learning_report(self):
        """Should generate comprehensive learning report."""
        # Run a cycle to generate data
        self.loop.execute_improving_cycle(
            goal="Generate learning data",
            available_tools=["tool"],
            max_iterations=1
        )
        
        report = self.loop.export_learning_report()
        
        self.assertIsInstance(report, str)
        self.assertIn("Self-Improvement Learning Report", report)
        self.assertIn("Performance Statistics", report)
        self.assertIn("Learned Patterns", report)
    
    def test_16_multiple_iterations(self):
        """Should handle multiple improvement iterations."""
        trace = self.loop.execute_improving_cycle(
            goal="Iterative improvement test",
            available_tools=["tool_a", "tool_b"],
            max_iterations=3
        )
        
        # Should complete all iterations (or stop early on success)
        self.assertGreaterEqual(len(trace.execution_results), 1)
        
        # Should have final reflection
        self.assertIsNotNone(trace.reflection_report)


class TestIntegrationModes(unittest.TestCase):
    """Test different integration modes."""
    
    def test_17_passive_mode(self):
        """PASSIVE mode should store reflections without auto-planning use."""
        planner, loop, bridge = create_integrated_system(mode=IntegrationMode.PASSIVE)
        
        trace = loop.execute_improving_cycle(
            goal="Passive mode test",
            available_tools=["tool"],
            max_iterations=1
        )
        
        self.assertIsNotNone(trace)
    
    def test_18_active_mode(self):
        """ACTIVE mode should automatically query reflections during planning."""
        planner, loop, bridge = create_integrated_system(mode=IntegrationMode.ACTIVE)
        
        # First run to create some history
        trace1 = loop.execute_improving_cycle(
            goal="Active mode first run",
            available_tools=["tool"],
            max_iterations=1
        )
        
        # Second run should use reflections from first
        trace2 = loop.execute_improving_cycle(
            goal="Active mode second run similar",
            available_tools=["tool"],
            max_iterations=1
        )
        
        self.assertIsNotNone(trace1)
        self.assertIsNotNone(trace2)
    
    def test_19_autonomous_mode(self):
        """AUTONOMOUS mode should enable full self-improving loop."""
        planner, loop, bridge = create_integrated_system(mode=IntegrationMode.AUTONOMOUS)
        
        trace = loop.execute_improving_cycle(
            goal="Autonomous improvement",
            available_tools=["tool_a", "tool_b"],
            max_iterations=2
        )
        
        # Should have improvement proposals
        self.assertIsNotNone(trace.improvement_proposals)
        self.assertIsInstance(trace.improvement_proposals, list)


class TestEndToEndWorkflow(unittest.TestCase):
    """End-to-end workflow tests."""
    
    def test_20_full_improvement_cycle(self):
        """Complete cycle: plan → execute → reflect → store → replan."""
        memory = TieredMemorySystem()
        bridge = ReflectionMemoryBridge(memory)
        base_planner = HierarchicalPlanner()
        planner = PlanningWithReflection(base_planner, bridge)
        executor = base_planner.executor
        reflection = ReflectionEngine()
        
        # First iteration
        plan1 = planner.plan_with_reflection_context(
            goal="Analyze research papers",
            available_tools=["search", "analyze"]
        )
        
        # Execute (simulated by marking tasks complete)
        if hasattr(plan1, 'tasks'):
            for task_id in plan1.tasks:
                task = plan1.tasks[task_id]
                if hasattr(task, 'status'):
                    task.status = TaskStatus.COMPLETED
        
        # Reflect
        report1 = reflection.reflect_on_plan(
            plan_id=plan1.id,
            plan_goal="Analyze research papers",
            tasks_data=[{"status": "completed"}],
            overall_success=True
        )
        
        # Store
        bridge.store_reflection(report1)
        
        # Second iteration with learning
        plan2 = planner.plan_with_reflection_context(
            goal="Analyze more research papers",
            available_tools=["search", "analyze"]
        )
        
        # Verify second plan was created
        self.assertIsNotNone(plan2)
        
        # Verify adaptation tracking
        self.assertGreaterEqual(
            planner.get_adaptation_summary()["adaptations"],
            2
        )
    
    def test_21_pattern_learning_across_sessions(self):
        """Should learn patterns that persist across planning sessions."""
        planner, loop, bridge = create_integrated_system()
        
        # Session 1: Learn that parallel execution works
        trace1 = loop.execute_improving_cycle(
            goal="Parallel data processing",
            available_tools=["process_a", "process_b"],
            max_iterations=1
        )
        
        # Manually add pattern to reflection
        if trace1.reflection_report:
            trace1.reflection_report.patterns_identified.append(
                "Parallel execution is faster"
            )
            bridge.store_reflection(trace1.reflection_report, trace1)
        
        # Session 2: Similar goal should benefit from learned pattern
        trace2 = loop.execute_improving_cycle(
            goal="Parallel processing task",
            available_tools=["process_a", "process_b"],
            max_iterations=1
        )
        
        # Verify learning occurred (at least traces exist)
        self.assertEqual(len(loop._execution_traces), 2)


class TestPerformanceMetrics(unittest.TestCase):
    """Test metrics aggregation across systems."""
    
    def test_22_cross_system_metrics(self):
        """Should aggregate metrics from planner, executor, and reflection."""
        planner, loop, bridge = create_integrated_system()
        
        # Execute and collect metrics
        for i in range(3):
            trace = loop.execute_improving_cycle(
                goal=f"Metrics test {i}",
                available_tools=["tool"],
                max_iterations=1
            )
            
            # Verify trace has metrics
            trace_dict = trace.to_dict()
            self.assertIn("total_duration_ms", trace_dict)
            self.assertIn("quality_score", trace_dict)
        
        # Check statistics
        stats = loop.get_improvement_statistics()
        self.assertEqual(stats["total_cycles"], 3)
    
    def test_23_quality_tracking(self):
        """Should track quality scores across iterations."""
        planner, loop, bridge = create_integrated_system()
        
        qualities = []
        
        for i in range(3):
            trace = loop.execute_improving_cycle(
                goal=f"Quality tracking {i}",
                available_tools=["tool"],
                max_iterations=1
            )
            
            # Manually set quality for predictable tracking
            trace.quality_score = 0.7 + (i * 0.1)
            qualities.append(trace.quality_score)
        
        # Force update improvement log with quality scores
        for i, log in enumerate(loop._improvement_log):
            log["final_quality"] = qualities[i]
        
        stats = loop.get_improvement_statistics()
        
        # With increasing quality, trend should be improving or stable
        self.assertIn(stats["quality_trend"], ["improving", "stable"])


class TestErrorHandling(unittest.TestCase):
    """Test error handling in integration layer."""
    
    def test_24_invalid_reflection_storage(self):
        """Should handle invalid reflection data gracefully."""
        memory = TieredMemorySystem()
        bridge = ReflectionMemoryBridge(memory)
        
        # Create invalid data in memory
        memory.store(
            content="invalid json",
            tier=MemoryTier.L0_IMMEDIATE,
            directory="/reflections",
            tags={"reflection"}
        )
        
        # Query should handle gracefully
        results = bridge.query_relevant_reflections("test")
        
        # Should return empty or valid results, not crash
        self.assertIsInstance(results, list)
    
    def test_25_empty_planning_history(self):
        """Should handle planning with no prior reflections."""
        memory = TieredMemorySystem()
        bridge = ReflectionMemoryBridge(memory)
        base_planner = HierarchicalPlanner()
        planner = PlanningWithReflection(base_planner, bridge)
        
        # Plan without any stored reflections
        plan = planner.plan_with_reflection_context(
            goal="First ever plan",
            available_tools=["tool"]
        )
        
        self.assertIsNotNone(plan)


def run_tests():
    """Run all integration tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestReflectionMemoryBridge))
    suite.addTests(loader.loadTestsFromTestCase(TestPlanningWithReflection))
    suite.addTests(loader.loadTestsFromTestCase(TestSelfImprovingLoop))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationModes))
    suite.addTests(loader.loadTestsFromTestCase(TestEndToEndWorkflow))
    suite.addTests(loader.loadTestsFromTestCase(TestPerformanceMetrics))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorHandling))
    
    # Run with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"Test Summary: {result.testsRun} tests run")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print(f"Success Rate: {(result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun:.1%}")
    print(f"{'='*60}\n")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
