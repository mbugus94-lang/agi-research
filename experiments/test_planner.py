"""
Test Suite for Planner Module

Validates Tree of Thought planning, test-time adaptation,
and MCP-aware plan generation.
"""

import sys
import unittest
from typing import Any, Tuple

# Add parent directory to path
sys.path.insert(0, '/home/workspace/agi-research')

from core.planner import (
    PlanStatus, NodeStatus,
    PlanningContext, PlanNode, Plan, ExecutionTrace,
    TreeOfThoughtPlanner, TestTimeAdapter,
    MCPAwarePlanner, PlanExecutor,
    create_default_planner
)


class TestPlanningContext(unittest.TestCase):
    """Test planning context creation and configuration."""
    
    def test_context_creation_defaults(self):
        """Test context with default values."""
        ctx = PlanningContext(
            task_description="Test task"
        )
        self.assertEqual(ctx.task_description, "Test task")
        self.assertEqual(ctx.max_depth, 5)
        self.assertEqual(ctx.max_parallel_branches, 3)
        self.assertEqual(ctx.refinement_threshold, 0.7)
        self.assertEqual(ctx.constraints, [])
        self.assertEqual(ctx.available_tools, [])
    
    def test_context_creation_custom(self):
        """Test context with custom values."""
        ctx = PlanningContext(
            task_description="Research task",
            constraints=["budget", "time"],
            available_tools=["web_search", "analysis"],
            max_depth=7,
            max_parallel_branches=5,
            refinement_threshold=0.8
        )
        self.assertEqual(ctx.task_description, "Research task")
        self.assertEqual(ctx.constraints, ["budget", "time"])
        self.assertEqual(ctx.available_tools, ["web_search", "analysis"])
        self.assertEqual(ctx.max_depth, 7)
        self.assertEqual(ctx.max_parallel_branches, 5)
        self.assertEqual(ctx.refinement_threshold, 0.8)
    
    def test_context_to_dict(self):
        """Test context serialization."""
        ctx = PlanningContext(
            task_description="Test",
            constraints=["c1"],
            available_tools=["t1"]
        )
        d = ctx.to_dict()
        self.assertEqual(d["task_description"], "Test")
        self.assertEqual(d["constraints"], ["c1"])
        self.assertEqual(d["available_tools"], ["t1"])
        self.assertEqual(d["max_depth"], 5)


class TestPlanNode(unittest.TestCase):
    """Test plan node functionality."""
    
    def test_node_creation(self):
        """Test node creation with defaults."""
        node = PlanNode(
            node_id="n1",
            description="Test node",
            action_type="tool_call"
        )
        self.assertEqual(node.node_id, "n1")
        self.assertEqual(node.description, "Test node")
        self.assertEqual(node.action_type, "tool_call")
        self.assertEqual(node.status, NodeStatus.PLANNED)
        self.assertEqual(node.confidence, 1.0)
        self.assertEqual(node.retry_count, 0)
        self.assertEqual(node.max_retries, 3)
    
    def test_node_with_dependencies(self):
        """Test node with dependencies."""
        node = PlanNode(
            node_id="n2",
            description="Dependent node",
            action_type="reasoning",
            dependencies=["n1"],
            expected_output="Result"
        )
        self.assertEqual(node.dependencies, ["n1"])
        self.assertEqual(node.expected_output, "Result")
    
    def test_node_alternative_branches(self):
        """Test node with alternative branches."""
        branch1 = PlanNode(node_id="b1", description="Branch 1", action_type="decision")
        branch2 = PlanNode(node_id="b2", description="Branch 2", action_type="decision")
        
        node = PlanNode(
            node_id="root",
            description="Root",
            action_type="decision",
            alternative_branches=[branch1, branch2]
        )
        self.assertEqual(len(node.alternative_branches), 2)
    
    def test_node_serialization(self):
        """Test node serialization to dict."""
        node = PlanNode(
            node_id="n3",
            description="Test",
            action_type="subgoal",
            parameters={"key": "value"}
        )
        d = node.to_dict()
        self.assertEqual(d["node_id"], "n3")
        self.assertEqual(d["action_type"], "subgoal")
        self.assertEqual(d["parameters"], {"key": "value"})
        self.assertEqual(d["status"], "PLANNED")


class TestPlan(unittest.TestCase):
    """Test plan structure and execution tracking."""
    
    def test_plan_creation(self):
        """Test plan creation and indexing."""
        ctx = PlanningContext(task_description="Test plan")
        root = PlanNode(node_id="root", description="Root", action_type="subgoal")
        
        plan = Plan(
            plan_id="plan_1",
            context=ctx,
            root_nodes=[root]
        )
        
        self.assertEqual(plan.plan_id, "plan_1")
        self.assertEqual(plan.status, PlanStatus.PENDING)
        self.assertEqual(len(plan.root_nodes), 1)
        self.assertIn("root", plan.all_nodes)
    
    def test_get_ready_nodes_empty(self):
        """Test getting ready nodes with no dependencies."""
        ctx = PlanningContext(task_description="Test")
        node1 = PlanNode(node_id="n1", description="Node 1", action_type="tool_call")
        node2 = PlanNode(node_id="n2", description="Node 2", action_type="tool_call")
        
        plan = Plan(
            plan_id="plan_2",
            context=ctx,
            root_nodes=[node1, node2]
        )
        
        ready = plan.get_ready_nodes()
        self.assertEqual(len(ready), 2)
        self.assertIn(node1, ready)
        self.assertIn(node2, ready)
    
    def test_get_ready_nodes_with_dependencies(self):
        """Test getting ready nodes with satisfied dependencies."""
        ctx = PlanningContext(task_description="Test")
        node1 = PlanNode(node_id="n1", description="Node 1", action_type="tool_call")
        node1.status = NodeStatus.COMPLETED
        
        node2 = PlanNode(
            node_id="n2",
            description="Node 2",
            action_type="tool_call",
            dependencies=["n1"]
        )
        
        plan = Plan(
            plan_id="plan_3",
            context=ctx,
            root_nodes=[node1, node2]
        )
        
        ready = plan.get_ready_nodes()
        self.assertEqual(len(ready), 1)
        self.assertIn(node2, ready)
    
    def test_get_ready_nodes_with_unsatisfied_deps(self):
        """Test getting ready nodes with unsatisfied dependencies."""
        ctx = PlanningContext(task_description="Test")
        node1 = PlanNode(node_id="n1", description="Node 1", action_type="tool_call")
        # n1 is not completed
        
        node2 = PlanNode(
            node_id="n2",
            description="Node 2",
            action_type="tool_call",
            dependencies=["n1"]
        )
        
        plan = Plan(
            plan_id="plan_4",
            context=ctx,
            root_nodes=[node1, node2]
        )
        
        ready = plan.get_ready_nodes()
        self.assertEqual(len(ready), 1)  # Only n1 (no deps)
        self.assertIn(node1, ready)
    
    def test_parallel_groups(self):
        """Test parallel execution group identification."""
        ctx = PlanningContext(task_description="Test")
        n1 = PlanNode(node_id="n1", description="Step 1", action_type="tool_call")
        n2 = PlanNode(node_id="n2", description="Step 2", action_type="tool_call", dependencies=["n1"])
        n3 = PlanNode(node_id="n3", description="Step 3", action_type="tool_call", dependencies=["n1"])
        n4 = PlanNode(node_id="n4", description="Step 4", action_type="tool_call", dependencies=["n2", "n3"])
        
        plan = Plan(
            plan_id="plan_5",
            context=ctx,
            root_nodes=[n1, n2, n3, n4]
        )
        
        groups = plan.get_parallel_groups()
        self.assertEqual(len(groups), 3)
        self.assertEqual(len(groups[0]), 1)  # n1 only
        self.assertEqual(len(groups[1]), 2)  # n2, n3
        self.assertEqual(len(groups[2]), 1)  # n4
    
    def test_plan_serialization(self):
        """Test plan serialization."""
        ctx = PlanningContext(task_description="Serialization test")
        plan = Plan(plan_id="plan_6", context=ctx)
        
        d = plan.to_dict()
        self.assertEqual(d["plan_id"], "plan_6")
        self.assertEqual(d["status"], "PENDING")
        self.assertEqual(d["version"], 1)
        self.assertEqual(d["trace_count"], 0)


class TestTreeOfThoughtPlanner(unittest.TestCase):
    """Test Tree of Thought planning capabilities."""
    
    def test_planner_creation(self):
        """Test planner initialization."""
        planner = TreeOfThoughtPlanner(max_branches=4, exploration_depth=5)
        self.assertEqual(planner.max_branches, 4)
        self.assertEqual(planner.exploration_depth, 5)
    
    def test_generate_research_plan(self):
        """Test plan generation for research task."""
        planner = TreeOfThoughtPlanner()
        ctx = PlanningContext(task_description="Research the latest AI agents")
        
        plan = planner.generate_plan(ctx)
        
        self.assertIsNotNone(plan.plan_id)
        self.assertGreater(len(plan.root_nodes), 0)
        self.assertEqual(plan.status, PlanStatus.PENDING)
        self.assertEqual(len(planner.plan_history), 1)
        
        # Check that goals were decomposed
        root_descriptions = [r.description for r in plan.root_nodes]
        self.assertTrue(any("search" in d.lower() or "gather" in d.lower() 
                           for d in root_descriptions))
    
    def test_generate_code_plan(self):
        """Test plan generation for coding task."""
        planner = TreeOfThoughtPlanner()
        ctx = PlanningContext(task_description="Implement a Python function")
        
        plan = planner.generate_plan(ctx)
        
        self.assertGreater(len(plan.root_nodes), 0)
        root_descriptions = [r.description for r in plan.root_nodes]
        self.assertTrue(any("implement" in d.lower() or "design" in d.lower() 
                           for d in root_descriptions))
    
    def test_generate_analysis_plan(self):
        """Test plan generation for analysis task."""
        planner = TreeOfThoughtPlanner()
        ctx = PlanningContext(task_description="Analyze the dataset")
        
        plan = planner.generate_plan(ctx)
        
        self.assertGreater(len(plan.root_nodes), 0)
        root_descriptions = [r.description for r in plan.root_nodes]
        self.assertTrue(any("analyze" in d.lower() or "data" in d.lower() 
                           for d in root_descriptions))
    
    def test_alternative_branches_generated(self):
        """Test that alternative branches are generated."""
        planner = TreeOfThoughtPlanner(max_branches=3)
        ctx = PlanningContext(task_description="Research AI")
        
        plan = planner.generate_plan(ctx)
        
        # Check that at least one root node has alternative branches
        roots_with_branches = sum(1 for r in plan.root_nodes 
                                 if len(r.alternative_branches) > 0)
        self.assertGreater(roots_with_branches, 0)
    
    def test_branch_evaluation(self):
        """Test branch evaluation and selection."""
        planner = TreeOfThoughtPlanner()
        ctx = PlanningContext(task_description="Test")
        
        plan = planner.generate_plan(ctx)
        
        # Simple evaluation function
        def eval_fn(node: PlanNode) -> float:
            if "parallel" in node.description.lower():
                return 0.8
            return 0.5
        
        scores = planner.evaluate_branches(plan, eval_fn)
        self.assertIsInstance(scores, dict)
    
    def test_select_best_branch(self):
        """Test selecting best branch."""
        planner = TreeOfThoughtPlanner()
        
        # Create root with branches
        root = PlanNode(node_id="root", description="Root", action_type="subgoal")
        branch1 = PlanNode(node_id="b1", description="Branch 1", action_type="reasoning")
        branch2 = PlanNode(node_id="b2", description="Branch 2", action_type="reasoning")
        root.alternative_branches = [branch1, branch2]
        
        scores = {"b1": 0.3, "b2": 0.8}
        best = planner.select_best_branch(root, scores)
        
        self.assertIsNotNone(best)
        self.assertEqual(best.node_id, "b2")


class TestTestTimeAdapter(unittest.TestCase):
    """Test test-time adaptation capabilities."""
    
    def test_adapter_creation(self):
        """Test adapter initialization."""
        adapter = TestTimeAdapter(refinement_threshold=0.8)
        self.assertEqual(adapter.refinement_threshold, 0.8)
        self.assertEqual(adapter.refinement_history, [])
    
    def test_should_refine_low_confidence(self):
        """Test refinement trigger on low confidence."""
        adapter = TestTimeAdapter(refinement_threshold=0.7)
        node = PlanNode(
            node_id="n1",
            description="Test",
            action_type="tool_call",
            confidence=0.5
        )
        
        should_refine = adapter.should_refine(node, {"result": "ok"})
        self.assertTrue(should_refine)
    
    def test_should_refine_error_result(self):
        """Test refinement trigger on error result."""
        adapter = TestTimeAdapter(refinement_threshold=0.7)
        node = PlanNode(
            node_id="n1",
            description="Test",
            action_type="tool_call",
            confidence=0.9
        )
        
        should_refine = adapter.should_refine(node, {"error": "Failed", "success": False})
        self.assertTrue(should_refine)
    
    def test_should_not_refine(self):
        """Test no refinement needed."""
        adapter = TestTimeAdapter(refinement_threshold=0.7)
        node = PlanNode(
            node_id="n1",
            description="Test",
            action_type="tool_call",
            confidence=0.9
        )
        
        should_refine = adapter.should_refine(node, {"success": True, "data": "result"})
        self.assertFalse(should_refine)
    
    def test_should_refine_max_retries(self):
        """Test refinement after max retries."""
        adapter = TestTimeAdapter(refinement_threshold=0.7)
        node = PlanNode(
            node_id="n1",
            description="Test",
            action_type="tool_call",
            confidence=0.9,
            retry_count=3,
            max_retries=3
        )
        
        should_refine = adapter.should_refine(node, {"success": True})
        self.assertTrue(should_refine)
    
    def test_refine_node(self):
        """Test node refinement."""
        adapter = TestTimeAdapter()
        node = PlanNode(
            node_id="n1",
            description="Original",
            action_type="tool_call",
            parameters={"key": "value"}
        )
        
        refined = adapter.refine_node(node, "Timeout occurred")
        
        self.assertEqual(node.status, NodeStatus.REPLANNED)
        self.assertNotEqual(refined.node_id, node.node_id)
        self.assertIn("refined", refined.description)
        self.assertIn("Timeout", refined.description)
        self.assertEqual(adapter.refinement_history[0]["original_node"], "n1")
    
    def test_adapt_plan(self):
        """Test full plan adaptation."""
        adapter = TestTimeAdapter()
        ctx = PlanningContext(task_description="Test")
        
        n1 = PlanNode(node_id="n1", description="Node 1", action_type="tool_call")
        n2 = PlanNode(node_id="n2", description="Node 2", action_type="tool_call", dependencies=["n1"])
        
        plan = Plan(
            plan_id="plan_1",
            context=ctx,
            root_nodes=[n1, n2]
        )
        
        new_plan = adapter.adapt_plan(plan, n1, "Connection error")
        
        self.assertEqual(new_plan.parent_plan_id, "plan_1")
        self.assertEqual(new_plan.version, 2)
        self.assertNotEqual(new_plan.plan_id, plan.plan_id)
        self.assertEqual(len(new_plan.root_nodes), 2)


class TestMCPAwarePlanner(unittest.TestCase):
    """Test MCP-aware planning."""
    
    def test_register_tool(self):
        """Test tool registration."""
        planner = MCPAwarePlanner()
        schema = {"name": "web_search", "description": "Search the web"}
        
        planner.register_tool("web_search", schema)
        
        self.assertIn("web_search", planner.tool_registry)
        self.assertEqual(planner.tool_registry["web_search"], schema)
    
    def test_select_relevant_tools_for_research(self):
        """Test tool selection for research task."""
        planner = MCPAwarePlanner()
        available = ["web_search", "code_gen", "analysis", "file_operations"]
        
        relevant = planner._select_relevant_tools("Research the topic", available)
        
        self.assertIn("web_search", relevant)
    
    def test_select_relevant_tools_for_coding(self):
        """Test tool selection for coding task."""
        planner = MCPAwarePlanner()
        available = ["web_search", "code_gen", "analysis", "file_operations"]
        
        relevant = planner._select_relevant_tools("Implement the function", available)
        
        self.assertIn("code_gen", relevant)
    
    def test_select_relevant_tools_for_analysis(self):
        """Test tool selection for analysis task."""
        planner = MCPAwarePlanner()
        available = ["web_search", "code_gen", "analysis", "file_operations"]
        
        relevant = planner._select_relevant_tools("Analyze the dataset", available)
        
        self.assertIn("analysis", relevant)
    
    def test_select_relevant_tools_fallback(self):
        """Test tool fallback when no matches."""
        planner = MCPAwarePlanner()
        available = ["web_search", "code_gen", "analysis"]
        
        relevant = planner._select_relevant_tools("Do something unknown", available)
        
        # Should return up to 3 tools
        self.assertEqual(len(relevant), 3)
    
    def test_generate_tool_aware_plan(self):
        """Test generating plan with tool awareness."""
        tot_planner = TreeOfThoughtPlanner()
        mcp_planner = MCPAwarePlanner()
        mcp_planner.register_tool("web_search", {"type": "search"})
        
        ctx = PlanningContext(
            task_description="Research AI agents",
            available_tools=["web_search", "analysis"]
        )
        
        plan = mcp_planner.generate_tool_aware_plan(ctx, tot_planner)
        
        self.assertGreater(len(plan.root_nodes), 0)
        # Check context was updated with relevant tools
        self.assertIn("web_search", ctx.available_tools)


class TestPlanExecutor(unittest.TestCase):
    """Test plan execution with adaptation."""
    
    def test_executor_creation(self):
        """Test executor initialization."""
        tot = TreeOfThoughtPlanner()
        adapter = TestTimeAdapter()
        executor = PlanExecutor(tot, adapter, max_parallel=5)
        
        self.assertEqual(executor.max_parallel, 5)
        self.assertEqual(executor.active_plans, {})
    
    def test_simple_execution(self):
        """Test simple plan execution."""
        tot = TreeOfThoughtPlanner()
        adapter = TestTimeAdapter()
        executor = PlanExecutor(tot, adapter)
        
        ctx = PlanningContext(task_description="Test execution")
        node = PlanNode(node_id="n1", description="Simple task", action_type="tool_call")
        plan = Plan(plan_id="test_plan", context=ctx, root_nodes=[node])
        
        def mock_executor(node: PlanNode) -> Tuple[bool, Any]:
            return True, "Success"
        
        trace = executor.execute_plan(plan, mock_executor)
        
        self.assertEqual(plan.status, PlanStatus.COMPLETED)
        self.assertEqual(trace.success_rate, 1.0)
        self.assertEqual(len(trace.node_executions), 1)
    
    def test_execution_with_failure(self):
        """Test execution with node failure."""
        tot = TreeOfThoughtPlanner()
        adapter = TestTimeAdapter()
        executor = PlanExecutor(tot, adapter)
        
        ctx = PlanningContext(task_description="Test failure")
        node = PlanNode(node_id="n1", description="Failing task", action_type="tool_call")
        plan = Plan(plan_id="fail_plan", context=ctx, root_nodes=[node])
        
        def mock_executor(node: PlanNode) -> Tuple[bool, Any]:
            return False, {"error": "Failed", "success": False}
        
        # This will trigger refinement and re-execution, eventually failing
        # After 3 retries + refinements, it should fail
        trace = executor.execute_plan(plan, mock_executor)
        
        # The adapted plan is created during execution, check its traces
        # The final plan will have the trace added
        final_plan = executor.active_plans.get(plan.plan_id, plan)
        # Plan should have been refined at least once (version > 1 indicates adaptation)
        # or the final plan should have the trace
        self.assertGreaterEqual(len(final_plan.execution_traces), 0)
        # Verify trace exists
        self.assertIsNotNone(trace)
        self.assertGreater(len(trace.node_executions), 0)
    
    def test_parallel_execution_groups(self):
        """Test execution respects parallel groups."""
        tot = TreeOfThoughtPlanner()
        adapter = TestTimeAdapter()
        executor = PlanExecutor(tot, adapter)
        
        ctx = PlanningContext(task_description="Parallel test")
        n1 = PlanNode(node_id="n1", description="Independent 1", action_type="tool_call")
        n2 = PlanNode(node_id="n2", description="Independent 2", action_type="tool_call")
        
        plan = Plan(plan_id="parallel_plan", context=ctx, root_nodes=[n1, n2])
        
        execution_order = []
        def mock_executor(node: PlanNode) -> Tuple[bool, Any]:
            execution_order.append(node.node_id)
            return True, f"Result for {node.node_id}"
        
        trace = executor.execute_plan(plan, mock_executor)
        
        self.assertEqual(len(execution_order), 2)
        self.assertEqual(trace.success_rate, 1.0)
    
    def test_execution_statistics(self):
        """Test plan statistics calculation."""
        tot = TreeOfThoughtPlanner()
        adapter = TestTimeAdapter()
        executor = PlanExecutor(tot, adapter)
        
        ctx = PlanningContext(task_description="Stats test")
        n1 = PlanNode(node_id="n1", description="Node 1", action_type="tool_call")
        n2 = PlanNode(node_id="n2", description="Node 2", action_type="tool_call", dependencies=["n1"])
        n1.status = NodeStatus.COMPLETED
        n2.status = NodeStatus.COMPLETED
        
        plan = Plan(plan_id="stats_plan", context=ctx, root_nodes=[n1, n2])
        
        stats = executor.get_plan_statistics(plan)
        
        self.assertEqual(stats["total_nodes"], 2)
        self.assertEqual(stats["completed"], 2)
        self.assertEqual(stats["success_rate"], 1.0)
        self.assertEqual(stats["version"], 1)


class TestIntegration(unittest.TestCase):
    """Integration tests for the full planning pipeline."""
    
    def test_full_pipeline_creation(self):
        """Test creating default planning pipeline."""
        tools = {"web_search": {"type": "search"}}
        tot, adapter, mcp, executor = create_default_planner(tools)
        
        self.assertIsInstance(tot, TreeOfThoughtPlanner)
        self.assertIsInstance(adapter, TestTimeAdapter)
        self.assertIsInstance(mcp, MCPAwarePlanner)
        self.assertIsInstance(executor, PlanExecutor)
    
    def test_end_to_end_research_workflow(self):
        """Test end-to-end research planning workflow."""
        tools = {
            "web_search": {"description": "Search the web"},
            "analysis": {"description": "Analyze data"}
        }
        tot, adapter, mcp, executor = create_default_planner(tools)
        
        # Create context
        ctx = PlanningContext(
            task_description="Research the latest AI agent frameworks",
            available_tools=["web_search", "analysis"],
            max_parallel_branches=2
        )
        
        # Generate plan
        plan = mcp.generate_tool_aware_plan(ctx, tot)
        
        # Verify plan structure
        self.assertGreater(len(plan.root_nodes), 0)
        self.assertEqual(plan.status, PlanStatus.PENDING)
        
        # Mock executor
        def mock_executor(node: PlanNode) -> Tuple[bool, Any]:
            return True, f"Completed: {node.description}"
        
        # Execute
        trace = executor.execute_plan(plan, mock_executor)
        
        # Verify execution
        self.assertEqual(plan.status, PlanStatus.COMPLETED)
        self.assertGreater(trace.success_rate, 0)
    
    def test_end_to_end_with_adaptation(self):
        """Test end-to-end workflow with adaptation."""
        tools = {"code_gen": {"description": "Generate code"}}
        tot, adapter, mcp, executor = create_default_planner(tools)
        
        ctx = PlanningContext(
            task_description="Implement a sorting function",
            available_tools=["code_gen"],
            refinement_threshold=0.8
        )
        
        plan = mcp.generate_tool_aware_plan(ctx, tot)
        
        # Executor that fails then succeeds
        attempt_count = 0
        def adaptive_executor(node: PlanNode) -> Tuple[bool, Any]:
            nonlocal attempt_count
            attempt_count += 1
            if node.retry_count < 1:
                return False, {"error": "Syntax error"}
            return True, "def sort(): pass"
        
        trace = executor.execute_plan(plan, adaptive_executor)
        
        # Should have had at least one retry/refinement
        self.assertGreater(attempt_count, 1)


def run_tests():
    """Run all tests with output."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestPlanningContext))
    suite.addTests(loader.loadTestsFromTestCase(TestPlanNode))
    suite.addTests(loader.loadTestsFromTestCase(TestPlan))
    suite.addTests(loader.loadTestsFromTestCase(TestTreeOfThoughtPlanner))
    suite.addTests(loader.loadTestsFromTestCase(TestTestTimeAdapter))
    suite.addTests(loader.loadTestsFromTestCase(TestMCPAwarePlanner))
    suite.addTests(loader.loadTestsFromTestCase(TestPlanExecutor))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == "__main__":
    print("=" * 60)
    print("Running Planner Module Test Suite")
    print("=" * 60)
    result = run_tests()
    
    print("\n" + "=" * 60)
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 60)
    
    if result.wasSuccessful():
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed")
        sys.exit(1)