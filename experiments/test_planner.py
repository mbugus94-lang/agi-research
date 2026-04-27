"""
Comprehensive test suite for the Planner Module.

Tests Tree of Thought planning, Test-Time Adaptation, MCP-aware planning,
and plan execution with refinement capabilities.

Run with: python -m pytest experiments/test_planner.py -v
"""

import sys
sys.path.insert(0, '/home/workspace/agi-research')

import pytest
import time
from unittest.mock import Mock
from core.planner import (
    PlanStatus, NodeStatus, PlanningContext, PlanNode, Plan, ExecutionTrace,
    TreeOfThoughtPlanner, TestTimeAdapter, MCPAwarePlanner, PlanExecutor,
    create_default_planner
)


class TestPlanningContext:
    """Test PlanningContext initialization and serialization."""
    
    def test_basic_initialization(self):
        """Test basic PlanningContext creation."""
        context = PlanningContext(
            task_description="Test task",
            constraints=["time < 1000ms"],
            available_tools=["web_search", "code_gen"]
        )
        
        assert context.task_description == "Test task"
        assert context.constraints == ["time < 1000ms"]
        assert context.available_tools == ["web_search", "code_gen"]
        assert context.max_depth == 5  # default
        assert context.max_parallel_branches == 3  # default
        assert context.refinement_threshold == 0.7  # default
    
    def test_default_values(self):
        """Test default values for optional parameters."""
        context = PlanningContext(task_description="Simple task")
        
        assert context.constraints == []
        assert context.available_tools == []
        assert context.memory_context == {}
        assert context.max_depth == 5
    
    def test_to_dict_serialization(self):
        """Test dict serialization of PlanningContext."""
        context = PlanningContext(
            task_description="Research AI trends",
            constraints=["use only free APIs"],
            available_tools=["web_search"],
            max_depth=3,
            max_parallel_branches=2
        )
        
        d = context.to_dict()
        assert d["task_description"] == "Research AI trends"
        assert d["constraints"] == ["use only free APIs"]
        assert d["available_tools"] == ["web_search"]
        assert d["max_depth"] == 3
        assert d["max_parallel_branches"] == 2
        assert d["refinement_threshold"] == 0.7


class TestPlanNode:
    """Test PlanNode creation and manipulation."""
    
    def test_node_creation(self):
        """Test basic PlanNode creation."""
        node = PlanNode(
            node_id="test_001",
            description="Search for data",
            action_type="tool_call"
        )
        
        assert node.node_id == "test_001"
        assert node.description == "Search for data"
        assert node.action_type == "tool_call"
        assert node.status == NodeStatus.PLANNED
        assert node.dependencies == []
        assert node.alternative_branches == []
    
    def test_auto_node_id_generation(self):
        """Test automatic node ID generation."""
        node = PlanNode(
            node_id="",
            description="Auto ID test",
            action_type="reasoning"
        )
        
        assert len(node.node_id) == 8  # UUID substring
        assert node.node_id != ""
    
    def test_node_with_dependencies(self):
        """Test node with dependencies."""
        node = PlanNode(
            node_id="step_2",
            description="Process results",
            action_type="reasoning",
            dependencies=["step_1"],
            expected_output="Processed data"
        )
        
        assert node.dependencies == ["step_1"]
        assert node.expected_output == "Processed data"
    
    def test_node_with_alternative_branches(self):
        """Test node with alternative branches (Tree of Thought)."""
        branch1 = PlanNode(
            node_id="branch_1",
            description="Approach A",
            action_type="reasoning"
        )
        branch2 = PlanNode(
            node_id="branch_2",
            description="Approach B",
            action_type="reasoning"
        )
        
        root = PlanNode(
            node_id="root",
            description="Choose approach",
            action_type="decision",
            alternative_branches=[branch1, branch2]
        )
        
        assert len(root.alternative_branches) == 2
        assert root.alternative_branches[0].node_id == "branch_1"
    
    def test_node_to_dict(self):
        """Test node serialization."""
        node = PlanNode(
            node_id="test_node",
            description="Test description",
            action_type="tool_call",
            parameters={"query": "AI news"},
            dependencies=["prev_node"],
            expected_output="Results",
            confidence=0.85
        )
        
        d = node.to_dict()
        assert d["node_id"] == "test_node"
        assert d["description"] == "Test description"
        assert d["action_type"] == "tool_call"
        assert d["parameters"] == {"query": "AI news"}
        assert d["dependencies"] == ["prev_node"]
        assert d["expected_output"] == "Results"
        assert d["status"] == "PLANNED"
        assert d["confidence"] == 0.85


class TestPlan:
    """Test Plan structure and operations."""
    
    def test_plan_creation(self):
        """Test basic plan creation."""
        context = PlanningContext(task_description="Test task")
        plan = Plan(
            plan_id="plan_001",
            context=context
        )
        
        assert plan.plan_id == "plan_001"
        assert plan.context == context
        assert plan.status == PlanStatus.PENDING
        assert plan.root_nodes == []
        assert plan.version == 1
        assert plan.parent_plan_id is None
    
    def test_auto_plan_id_generation(self):
        """Test automatic plan ID generation."""
        context = PlanningContext(task_description="Auto ID")
        plan = Plan(plan_id="", context=context)
        
        assert len(plan.plan_id) == 12
        assert plan.plan_id != ""
    
    def test_node_indexing(self):
        """Test that nodes get indexed correctly."""
        context = PlanningContext(task_description="Test")
        plan = Plan(plan_id="p1", context=context)
        
        node1 = PlanNode(node_id="n1", description="Step 1", action_type="action")
        node2 = PlanNode(node_id="n2", description="Step 2", action_type="action")
        
        plan.root_nodes = [node1, node2]
        plan._index_nodes()
        
        assert "n1" in plan.all_nodes
        assert "n2" in plan.all_nodes
        assert plan.all_nodes["n1"] == node1
    
    def test_get_ready_nodes(self):
        """Test getting nodes ready for execution."""
        context = PlanningContext(task_description="Test")
        plan = Plan(plan_id="p1", context=context)
        
        node1 = PlanNode(node_id="n1", description="Step 1", action_type="action")
        node2 = PlanNode(node_id="n2", description="Step 2", action_type="action", dependencies=["n1"])
        node3 = PlanNode(node_id="n3", description="Step 3", action_type="action")
        
        plan.root_nodes = [node1, node2, node3]
        plan._index_nodes()
        
        ready = plan.get_ready_nodes()
        assert len(ready) == 2  # n1 and n3 (no deps)
        assert node1 in ready
        assert node3 in ready
        assert node2 not in ready  # depends on n1
    
    def test_get_ready_nodes_after_completion(self):
        """Test ready nodes after some complete."""
        context = PlanningContext(task_description="Test")
        plan = Plan(plan_id="p1", context=context)
        
        node1 = PlanNode(node_id="n1", description="Step 1", action_type="action")
        node2 = PlanNode(node_id="n2", description="Step 2", action_type="action", dependencies=["n1"])
        
        plan.root_nodes = [node1, node2]
        plan._index_nodes()
        
        # Mark n1 as completed
        plan.all_nodes["n1"].status = NodeStatus.COMPLETED
        
        ready = plan.get_ready_nodes()
        assert len(ready) == 1
        assert node2 in ready
    
    def test_get_parallel_groups(self):
        """Test getting parallel execution groups."""
        context = PlanningContext(task_description="Test")
        plan = Plan(plan_id="p1", context=context)
        
        # Create dependency chain: A, B -> A, C -> B, D (no deps)
        node_a = PlanNode(node_id="a", description="A", action_type="action")
        node_b = PlanNode(node_id="b", description="B", action_type="action", dependencies=["a"])
        node_c = PlanNode(node_id="c", description="C", action_type="action", dependencies=["b"])
        node_d = PlanNode(node_id="d", description="D", action_type="action")
        
        plan.root_nodes = [node_a, node_b, node_c, node_d]
        plan._index_nodes()
        
        groups = plan.get_parallel_groups()
        
        # Group 1: a, d (no dependencies)
        assert len(groups[0]) == 2
        assert node_a in groups[0]
        assert node_d in groups[0]
        
        # Group 2: b (depends on a)
        assert len(groups[1]) == 1
        assert node_b in groups[1]
        
        # Group 3: c (depends on b)
        assert len(groups[2]) == 1
        assert node_c in groups[2]
    
    def test_plan_to_dict(self):
        """Test plan serialization."""
        context = PlanningContext(task_description="Research task")
        plan = Plan(
            plan_id="plan_test",
            context=context,
            version=2,
            parent_plan_id="plan_original"
        )
        
        d = plan.to_dict()
        assert d["plan_id"] == "plan_test"
        assert d["status"] == "PENDING"
        assert d["version"] == 2
        assert d["parent_plan_id"] == "plan_original"
        assert d["trace_count"] == 0
        assert d["context"]["task_description"] == "Research task"


class TestExecutionTrace:
    """Test execution trace functionality."""
    
    def test_trace_creation(self):
        """Test execution trace creation."""
        trace = ExecutionTrace(trace_id="t1", plan_id="p1")
        
        assert trace.trace_id == "t1"
        assert trace.plan_id == "p1"
        assert trace.node_executions == []
        assert trace.success_rate == 0.0
        assert trace.total_time_ms == 0.0
    
    def test_auto_trace_id_generation(self):
        """Test automatic trace ID generation."""
        trace = ExecutionTrace(trace_id="", plan_id="p1")
        
        assert len(trace.trace_id) == 12
        assert trace.trace_id != ""
    
    def test_record_node_execution_success(self):
        """Test recording successful node execution."""
        trace = ExecutionTrace(trace_id="t1", plan_id="p1")
        
        trace.record_node_execution("n1", True, "output data")
        
        assert len(trace.node_executions) == 1
        assert trace.node_executions[0]["node_id"] == "n1"
        assert trace.node_executions[0]["success"] is True
        assert trace.node_executions[0]["output"] == "output data"
        assert trace.success_rate == 1.0
    
    def test_record_node_execution_failure(self):
        """Test recording failed node execution."""
        trace = ExecutionTrace(trace_id="t1", plan_id="p1")
        
        trace.record_node_execution("n1", False, None, "Error: timeout")
        
        assert len(trace.node_executions) == 1
        assert trace.node_executions[0]["success"] is False
        assert trace.node_executions[0]["error"] == "Error: timeout"
        assert trace.success_rate == 0.0
    
    def test_success_rate_calculation(self):
        """Test success rate calculation across multiple nodes."""
        trace = ExecutionTrace(trace_id="t1", plan_id="p1")
        
        trace.record_node_execution("n1", True, "ok")
        trace.record_node_execution("n2", True, "ok")
        trace.record_node_execution("n3", False, None, "error")
        
        assert trace.success_rate == 2 / 3


class TestTreeOfThoughtPlanner:
    """Test Tree of Thought planning capabilities."""
    
    def test_planner_initialization(self):
        """Test planner initialization."""
        planner = TreeOfThoughtPlanner(max_branches=5, exploration_depth=4)
        
        assert planner.max_branches == 5
        assert planner.exploration_depth == 4
        assert planner.plan_history == []
    
    def test_generate_plan_basic(self):
        """Test basic plan generation."""
        planner = TreeOfThoughtPlanner()
        context = PlanningContext(
            task_description="Research AI trends",
            available_tools=["web_search"]
        )
        
        plan = planner.generate_plan(context)
        
        assert plan.context == context
        assert len(plan.root_nodes) > 0
        assert plan in planner.plan_history
    
    def test_decompose_research_task(self):
        """Test task decomposition for research tasks."""
        planner = TreeOfThoughtPlanner()
        
        goals = planner._decompose_task("Research the latest AI developments")
        
        assert len(goals) == 4
        assert "search" in goals[0].lower() or "strategy" in goals[0].lower()
        assert "gather" in goals[1].lower() or "information" in goals[1].lower()
        assert "synthesize" in goals[2].lower() or "analyze" in goals[2].lower()
    
    def test_decompose_code_task(self):
        """Test task decomposition for code tasks."""
        planner = TreeOfThoughtPlanner()
        
        goals = planner._decompose_task("Implement a sorting algorithm")
        
        assert len(goals) == 4
        assert "requirement" in goals[0].lower() or "analyze" in goals[0].lower()
        assert "design" in goals[1].lower() or "approach" in goals[1].lower()
        assert "implement" in goals[2].lower()
    
    def test_generate_approaches_search(self):
        """Test approach generation for search tasks."""
        planner = TreeOfThoughtPlanner()
        
        approaches = planner._generate_approaches(
            "Gather information from sources",
            PlanningContext(task_description="Test")
        )
        
        assert len(approaches) == 3
        assert any("parallel" in a.lower() for a in approaches)
        assert any("targeted" in a.lower() or "deep" in a.lower() for a in approaches)
    
    def test_generate_approaches_code(self):
        """Test approach generation for code tasks."""
        planner = TreeOfThoughtPlanner()
        
        approaches = planner._generate_approaches(
            "Implement solution",
            PlanningContext(task_description="Test")
        )
        
        assert len(approaches) == 3
        assert any("test-driven" in a.lower() or "prototype" in a.lower() for a in approaches)
    
    def test_goal_node_generation_with_branches(self):
        """Test goal node generation includes branches."""
        planner = TreeOfThoughtPlanner(max_branches=3)
        context = PlanningContext(
            task_description="Test",
            max_parallel_branches=2
        )
        
        node = planner._generate_goal_node("Search for data", context)
        
        assert node.description == "Search for data"
        assert node.action_type == "subgoal"
        assert len(node.alternative_branches) <= 2  # limited by max_parallel_branches
    
    def test_evaluate_branches(self):
        """Test branch evaluation."""
        planner = TreeOfThoughtPlanner()
        
        branch1 = PlanNode(node_id="b1", description="Approach 1", action_type="reasoning")
        branch2 = PlanNode(node_id="b2", description="Approach 2", action_type="reasoning")
        
        root = PlanNode(
            node_id="root",
            description="Root",
            action_type="decision",
            alternative_branches=[branch1, branch2]
        )
        
        context = PlanningContext(task_description="Test")
        plan = Plan(plan_id="p1", context=context, root_nodes=[root])
        plan._index_nodes()
        
        # Simple scoring function
        def score_fn(node):
            return 0.8 if node.node_id == "b1" else 0.6
        
        scores = planner.evaluate_branches(plan, score_fn)
        
        assert scores["b1"] == 0.8
        assert scores["b2"] == 0.6
    
    def test_select_best_branch(self):
        """Test selecting best branch."""
        planner = TreeOfThoughtPlanner()
        
        branch1 = PlanNode(node_id="b1", description="Approach 1", action_type="reasoning")
        branch2 = PlanNode(node_id="b2", description="Approach 2", action_type="reasoning")
        
        root = PlanNode(
            node_id="root",
            description="Root",
            action_type="decision",
            alternative_branches=[branch1, branch2]
        )
        
        scores = {"b1": 0.8, "b2": 0.6}
        best = planner.select_best_branch(root, scores)
        
        assert best == branch1  # Higher score
    
    def test_select_best_branch_with_low_scores(self):
        """Test selecting best branch when all scores are low."""
        planner = TreeOfThoughtPlanner()
        
        branch1 = PlanNode(node_id="b1", description="Approach 1", action_type="reasoning")
        
        root = PlanNode(
            node_id="root",
            description="Root",
            action_type="decision",
            alternative_branches=[branch1]
        )
        
        scores = {"b1": -0.5}  # Negative score
        best = planner.select_best_branch(root, scores)
        
        assert best is None  # Score too low


class TestTestTimeAdapter:
    """Test test-time adaptation capabilities."""
    
    def test_adapter_initialization(self):
        """Test adapter initialization."""
        adapter = TestTimeAdapter(refinement_threshold=0.8)
        
        assert adapter.refinement_threshold == 0.8
        assert adapter.refinement_history == []
    
    def test_should_refine_low_confidence(self):
        """Test refinement trigger for low confidence."""
        adapter = TestTimeAdapter(refinement_threshold=0.7)
        
        node = PlanNode(
            node_id="n1",
            description="Test",
            action_type="action",
            confidence=0.5  # Below threshold
        )
        
        assert adapter.should_refine(node, "result") is True
    
    def test_should_refine_high_confidence(self):
        """Test no refinement when confidence is high."""
        adapter = TestTimeAdapter(refinement_threshold=0.7)
        
        node = PlanNode(
            node_id="n1",
            description="Test",
            action_type="action",
            confidence=0.9  # Above threshold
        )
        
        assert adapter.should_refine(node, "result") is False
    
    def test_should_refine_error_result(self):
        """Test refinement triggered by error result."""
        adapter = TestTimeAdapter(refinement_threshold=0.7)
        
        node = PlanNode(
            node_id="n1",
            description="Test",
            action_type="action",
            confidence=0.9
        )
        
        result = {"error": "Timeout", "success": False}
        assert adapter.should_refine(node, result) is True
    
    def test_should_refine_exhausted_retries(self):
        """Test refinement when retries exhausted."""
        adapter = TestTimeAdapter(refinement_threshold=0.7)
        
        node = PlanNode(
            node_id="n1",
            description="Test",
            action_type="action",
            confidence=0.9,
            retry_count=3,
            max_retries=3
        )
        
        assert adapter.should_refine(node, "result") is True
    
    def test_refine_node(self):
        """Test node refinement."""
        adapter = TestTimeAdapter()
        
        node = PlanNode(
            node_id="n1",
            description="Original step",
            action_type="tool_call",
            parameters={"query": "test"}
        )
        
        refined = adapter.refine_node(node, "Connection timeout after 30s")
        
        assert refined.node_id == "n1_refined"
        assert "refined" in refined.description.lower()
        assert "timeout" in refined.description.lower()
        assert refined.action_type == "tool_call"
        assert refined.parameters["refinement_reason"] == "Connection timeout after 30s"
        assert node.status == NodeStatus.REPLANNED
        assert len(adapter.refinement_history) == 1
    
    def test_adapt_plan(self):
        """Test full plan adaptation."""
        adapter = TestTimeAdapter()
        
        context = PlanningContext(task_description="Test")
        node1 = PlanNode(node_id="n1", description="Step 1", action_type="action")
        node2 = PlanNode(node_id="n2", description="Step 2", action_type="action")
        
        plan = Plan(plan_id="p1", context=context, root_nodes=[node1, node2])
        plan._index_nodes()
        
        new_plan = adapter.adapt_plan(plan, node1, "Failed to execute")
        
        assert new_plan.plan_id.startswith("p1_v")
        assert new_plan.parent_plan_id == "p1"
        assert new_plan.version == 2
        assert len(new_plan.root_nodes) == 2


class TestMCPAwarePlanner:
    """Test MCP-aware planning capabilities."""
    
    def test_planner_initialization(self):
        """Test MCP planner initialization."""
        registry = {"tool1": {}, "tool2": {}}
        planner = MCPAwarePlanner(tool_registry=registry)
        
        assert planner.tool_registry == registry
        assert planner.tool_usage_patterns["tool1"]["success_count"] == 0
    
    def test_register_tool(self):
        """Test tool registration."""
        planner = MCPAwarePlanner()
        
        planner.register_tool("web_search", {"description": "Search the web"})
        
        assert "web_search" in planner.tool_registry
        assert planner.tool_registry["web_search"]["description"] == "Search the web"
    
    def test_select_relevant_tools_research(self):
        """Test relevant tool selection for research."""
        planner = MCPAwarePlanner()
        
        available = ["web_search", "code_gen", "analysis", "file_operations"]
        relevant = planner._select_relevant_tools(
            "Research the latest AI news",
            available
        )
        
        assert "web_search" in relevant
    
    def test_select_relevant_tools_code(self):
        """Test relevant tool selection for code tasks."""
        planner = MCPAwarePlanner()
        
        available = ["web_search", "code_gen", "analysis", "file_operations"]
        relevant = planner._select_relevant_tools(
            "Implement a new feature",
            available
        )
        
        assert "code_gen" in relevant
    
    def test_select_relevant_tools_analysis(self):
        """Test relevant tool selection for analysis."""
        planner = MCPAwarePlanner()
        
        available = ["web_search", "code_gen", "analysis", "file_operations"]
        relevant = planner._select_relevant_tools(
            "Analyze the dataset",
            available
        )
        
        assert "analysis" in relevant
    
    def test_select_relevant_tools_no_match(self):
        """Test fallback when no tools match."""
        planner = MCPAwarePlanner()
        
        available = ["web_search", "code_gen", "analysis"]
        relevant = planner._select_relevant_tools(
            "Do something completely different",
            available
        )
        
        # Falls back to first 3 available
        assert len(relevant) == 3


class TestPlanExecutor:
    """Test plan execution capabilities."""
    
    def test_executor_initialization(self):
        """Test executor initialization."""
        tot = TreeOfThoughtPlanner()
        adapter = TestTimeAdapter()
        executor = PlanExecutor(tot, adapter, max_parallel=5)
        
        assert executor.planner == tot
        assert executor.adapter == adapter
        assert executor.max_parallel == 5
        assert executor.active_plans == {}
    
    def test_execute_simple_plan(self):
        """Test executing a simple plan."""
        tot = TreeOfThoughtPlanner()
        adapter = TestTimeAdapter()
        executor = PlanExecutor(tot, adapter)
        
        context = PlanningContext(task_description="Test task")
        node = PlanNode(node_id="n1", description="Simple step", action_type="action")
        plan = Plan(plan_id="p1", context=context, root_nodes=[node])
        plan._index_nodes()
        
        # Mock executor that always succeeds
        def mock_executor(node):
            return True, "success"
        
        trace = executor.execute_plan(plan, mock_executor)
        
        assert trace.plan_id == "p1"
        assert trace.success_rate == 1.0
        assert plan.status == PlanStatus.COMPLETED
        assert len(trace.node_executions) == 1
        assert trace.node_executions[0]["success"] is True
    
    def test_execute_plan_with_failure(self):
        """Test plan execution with node failure."""
        tot = TreeOfThoughtPlanner()
        adapter = TestTimeAdapter()
        executor = PlanExecutor(tot, adapter)
        
        context = PlanningContext(task_description="Test task")
        node1 = PlanNode(node_id="n1", description="Step 1", action_type="action")
        node2 = PlanNode(node_id="n2", description="Step 2", action_type="action", dependencies=["n1"])
        
        plan = Plan(plan_id="p1", context=context, root_nodes=[node1, node2])
        plan._index_nodes()
        
        # Mock executor that fails on node 1
        def mock_executor(node):
            if node.node_id == "n1":
                return False, "Error: failed"
            return True, "success"
        
        trace = executor.execute_plan(plan, mock_executor)
        
        assert trace.node_executions[0]["success"] is False
        assert trace.node_executions[0]["error"] == "Error: failed"
    
    def test_execute_plan_with_multiple_nodes(self):
        """Test executing plan with multiple independent nodes."""
        tot = TreeOfThoughtPlanner()
        adapter = TestTimeAdapter()
        executor = PlanExecutor(tot, adapter)
        
        context = PlanningContext(task_description="Test task")
        node1 = PlanNode(node_id="n1", description="Step 1", action_type="action")
        node2 = PlanNode(node_id="n2", description="Step 2", action_type="action")
        
        plan = Plan(plan_id="p1", context=context, root_nodes=[node1, node2])
        plan._index_nodes()
        
        def mock_executor(node):
            return True, f"Output from {node.node_id}"
        
        trace = executor.execute_plan(plan, mock_executor)
        
        assert len(trace.node_executions) == 2
        assert trace.success_rate == 1.0
    
    def test_get_plan_statistics(self):
        """Test getting plan execution statistics."""
        tot = TreeOfThoughtPlanner()
        adapter = TestTimeAdapter()
        executor = PlanExecutor(tot, adapter)
        
        context = PlanningContext(task_description="Test task")
        node1 = PlanNode(node_id="n1", description="Step 1", action_type="action")
        node2 = PlanNode(node_id="n2", description="Step 2", action_type="action")
        node3 = PlanNode(node_id="n3", description="Step 3", action_type="action")
        
        plan = Plan(plan_id="p1", context=context, root_nodes=[node1, node2, node3])
        plan._index_nodes()
        
        # Simulate execution
        node1.status = NodeStatus.COMPLETED
        node2.status = NodeStatus.COMPLETED
        node3.status = NodeStatus.FAILED
        
        stats = executor.get_plan_statistics(plan)
        
        assert stats["total_nodes"] == 3
        assert stats["completed"] == 2
        assert stats["failed"] == 1
        assert stats["success_rate"] == 2 / 3
        assert stats["version"] == 1


class TestCreateDefaultPlanner:
    """Test default planner factory function."""
    
    def test_create_all_components(self):
        """Test that all components are created."""
        tot, adapter, mcp, executor = create_default_planner()
        
        assert isinstance(tot, TreeOfThoughtPlanner)
        assert isinstance(adapter, TestTimeAdapter)
        assert isinstance(mcp, MCPAwarePlanner)
        assert isinstance(executor, PlanExecutor)
    
    def test_create_with_registry(self):
        """Test creation with tool registry."""
        registry = {"web_search": {}, "code_gen": {}}
        tot, adapter, mcp, executor = create_default_planner(registry)
        
        assert mcp.tool_registry == registry


class TestIntegrationScenarios:
    """Integration tests for complete planning workflows."""
    
    def test_full_research_planning_workflow(self):
        """Test complete research planning and execution."""
        # Setup
        tot = TreeOfThoughtPlanner()
        adapter = TestTimeAdapter()
        mcp = MCPAwarePlanner({"web_search": {}, "analysis": {}})
        executor = PlanExecutor(tot, adapter)
        
        # Create research context
        context = PlanningContext(
            task_description="Research latest AI developments",
            available_tools=["web_search", "analysis"],
            max_parallel_branches=2
        )
        
        # Generate plan
        plan = tot.generate_plan(context)
        
        # Verify plan structure
        assert len(plan.root_nodes) > 0
        
        # Check that goals were decomposed correctly
        goal_descriptions = [node.description for node in plan.root_nodes]
        assert any("search" in d.lower() or "strategy" in d.lower() for d in goal_descriptions)
    
    def test_code_generation_planning_workflow(self):
        """Test complete code generation planning."""
        tot = TreeOfThoughtPlanner()
        
        context = PlanningContext(
            task_description="Implement a new feature",
            available_tools=["code_gen"],
            max_parallel_branches=2
        )
        
        plan = tot.generate_plan(context)
        
        # Verify code-related goals
        goal_descriptions = [node.description for node in plan.root_nodes]
        assert any("implement" in d.lower() or "code" in d.lower() or "design" in d.lower() 
                   for d in goal_descriptions)
    
    def test_plan_with_alternatives_selection(self):
        """Test planning with alternative branch selection."""
        tot = TreeOfThoughtPlanner()
        
        context = PlanningContext(
            task_description="Research task",
            max_parallel_branches=3
        )
        
        plan = tot.generate_plan(context)
        
        # Evaluate branches with different scoring strategies
        def quality_score(node):
            # Prefer approaches with "parallel" or "direct"
            desc = node.description.lower()
            if "parallel" in desc:
                return 0.9
            elif "direct" in desc or "targeted" in desc:
                return 0.7
            return 0.5
        
        # Test for each root node separately
        for root in plan.root_nodes:
            if root.alternative_branches:
                # Get scores for this root's branches only
                branch_scores = {b.node_id: quality_score(b) for b in root.alternative_branches}
                
                # Manually find best branch
                best_branch_id = max(branch_scores.keys(), key=lambda k: branch_scores[k])
                expected_best = branch_scores[best_branch_id]
                
                # Use the planner's method
                scores = tot.evaluate_branches(plan, quality_score)
                best = tot.select_best_branch(root, scores)
                
                if best:
                    # Best should have highest score among THIS root's branches
                    assert scores[best.node_id] == expected_best, \
                        f"Expected best score {expected_best}, got {scores[best.node_id]}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
