"""
Test Suite for Workflow DAG Execution Engine

Comprehensive tests for:
1. DAG construction and validation
2. Topological sorting
3. Parallel and sequential execution
4. Checkpointing and recovery
5. Self-healing with fallbacks
6. Error handling and retries
"""

import pytest
import time
import threading
from typing import Dict, Any

from core.workflow_dag import (
    WorkflowDAG, WorkflowNode, WorkflowEdge, NodeStatus, WorkflowStatus, EdgeType,
    WorkflowExecutor, WorkflowCheckpoint, create_parallel_workflow, create_sequential_workflow,
    create_map_reduce_workflow, NodeResult
)


class TestWorkflowNode:
    """Test WorkflowNode class."""
    
    def test_node_creation(self):
        """Test basic node creation."""
        action = lambda ctx: "result"
        node = WorkflowNode(
            node_id="test_1",
            name="Test Node",
            action=action,
            max_retries=5,
            timeout_seconds=60.0
        )
        
        assert node.node_id == "test_1"
        assert node.name == "Test Node"
        assert node.action == action
        assert node.max_retries == 5
        assert node.timeout_seconds == 60.0
        assert node.parallelizable is True
    
    def test_node_defaults(self):
        """Test node default values."""
        node = WorkflowNode(
            node_id="test_2",
            name="Test Node",
            action=lambda ctx: None
        )
        
        assert node.max_retries == 3
        assert node.timeout_seconds == 300.0
        assert node.parallelizable is True
        assert node.requires == []


class TestWorkflowDAG:
    """Test WorkflowDAG construction and validation."""
    
    @pytest.fixture
    def simple_dag(self):
        """Create a simple sequential DAG."""
        dag = WorkflowDAG(name="SimpleDAG")
        
        dag.add_node(WorkflowNode("a", "Node A", lambda ctx: "A"))
        dag.add_node(WorkflowNode("b", "Node B", lambda ctx: "B"))
        dag.add_node(WorkflowNode("c", "Node C", lambda ctx: "C"))
        
        dag.connect("a", "b")
        dag.connect("b", "c")
        
        return dag
    
    @pytest.fixture
    def branching_dag(self):
        """Create a DAG with branching."""
        dag = WorkflowDAG(name="BranchingDAG")
        
        dag.add_node(WorkflowNode("start", "Start", lambda ctx: "start"))
        dag.add_node(WorkflowNode("branch1", "Branch 1", lambda ctx: "b1"))
        dag.add_node(WorkflowNode("branch2", "Branch 2", lambda ctx: "b2"))
        dag.add_node(WorkflowNode("merge", "Merge", lambda ctx: "merged"))
        
        dag.connect("start", "branch1")
        dag.connect("start", "branch2")
        dag.connect("branch1", "merge")
        dag.connect("branch2", "merge")
        
        return dag
    
    def test_add_node(self):
        """Test adding nodes to DAG."""
        dag = WorkflowDAG()
        node = WorkflowNode("node1", "Node 1", lambda ctx: None)
        
        dag.add_node(node)
        
        assert "node1" in dag.nodes
        assert dag.nodes["node1"] == node
    
    def test_connect_nodes(self):
        """Test connecting nodes."""
        dag = WorkflowDAG()
        
        dag.add_node(WorkflowNode("a", "A", lambda ctx: None))
        dag.add_node(WorkflowNode("b", "B", lambda ctx: None))
        
        dag.connect("a", "b")
        
        assert len(dag.edges) == 1
        assert dag.edges[0].from_node == "a"
        assert dag.edges[0].to_node == "b"
    
    def test_validate_valid_dag(self, simple_dag):
        """Test validation of valid DAG."""
        is_valid, errors = simple_dag.validate()
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_detects_cycle(self):
        """Test cycle detection."""
        dag = WorkflowDAG()
        
        dag.add_node(WorkflowNode("a", "A", lambda ctx: None))
        dag.add_node(WorkflowNode("b", "B", lambda ctx: None))
        dag.add_node(WorkflowNode("c", "C", lambda ctx: None))
        
        # Create cycle: a -> b -> c -> a
        dag.connect("a", "b")
        dag.connect("b", "c")
        dag.connect("c", "a")
        
        is_valid, errors = dag.validate()
        
        assert is_valid is False
        assert len(errors) >= 1
        assert any("Cycle detected" in e for e in errors)
    
    def test_validate_unknown_edge_endpoints(self):
        """Test validation catches unknown nodes in edges."""
        dag = WorkflowDAG()
        dag.add_node(WorkflowNode("a", "A", lambda ctx: None))
        dag.connect("a", "nonexistent")
        
        is_valid, errors = dag.validate()
        
        assert is_valid is False
        assert any("unknown node" in e.lower() for e in errors)
    
    def test_get_entry_nodes(self, branching_dag):
        """Test entry node detection."""
        entries = branching_dag.get_entry_nodes()
        
        assert entries == {"start"}
    
    def test_get_exit_nodes(self, branching_dag):
        """Test exit node detection."""
        exits = branching_dag.get_exit_nodes()
        
        assert exits == {"merge"}
    
    def test_topological_sort(self, simple_dag):
        """Test topological sorting."""
        sorted_nodes = simple_dag.topological_sort()
        
        assert sorted_nodes == ["a", "b", "c"]
    
    def test_topological_sort_branching(self, branching_dag):
        """Test topological sort with branching."""
        sorted_nodes = branching_dag.topological_sort()
        
        # start must come first, merge must come last
        assert sorted_nodes[0] == "start"
        assert sorted_nodes[-1] == "merge"
        # branch1 and branch2 can be in either order
        assert "branch1" in sorted_nodes[1:3]
        assert "branch2" in sorted_nodes[1:3]
    
    def test_get_dependencies(self, simple_dag):
        """Test dependency resolution."""
        deps_c = simple_dag.get_dependencies("c")
        
        assert deps_c == {"b"}
    
    def test_get_dependents(self, branching_dag):
        """Test dependent resolution."""
        deps_start = branching_dag.get_dependents("start")
        
        assert deps_start == {"branch1", "branch2"}
    
    def test_get_execution_levels(self, branching_dag):
        """Test execution level grouping."""
        levels = branching_dag.get_execution_levels()
        
        assert levels[0] == {"start"}
        assert levels[1] == {"branch1", "branch2"}
        assert levels[2] == {"merge"}
    
    def test_to_dict(self, simple_dag):
        """Test serialization."""
        data = simple_dag.to_dict()
        
        assert data["name"] == "SimpleDAG"
        assert len(data["nodes"]) == 3
        assert len(data["edges"]) == 2
        assert data["entry_nodes"] == ["a"]
        assert data["exit_nodes"] == ["c"]


class TestWorkflowExecutor:
    """Test WorkflowExecutor execution capabilities."""
    
    @pytest.fixture
    def executor(self):
        """Create workflow executor."""
        return WorkflowExecutor(max_workers=2)
    
    @pytest.fixture
    def simple_success_dag(self):
        """Create DAG with all successful nodes."""
        dag = WorkflowDAG(name="SuccessDAG")
        
        dag.add_node(WorkflowNode("a", "Node A", lambda ctx: {"result": "A"}))
        dag.add_node(WorkflowNode("b", "Node B", lambda ctx: {"result": "B", "input": ctx.get("result")}))
        dag.connect("a", "b")
        
        return dag
    
    @pytest.fixture
    def dag_with_retry(self):
        """Create DAG with flaky node that eventually succeeds."""
        dag = WorkflowDAG(name="RetryDAG")
        
        call_count = {"count": 0}
        
        def flaky_action(ctx):
            call_count["count"] += 1
            if call_count["count"] < 3:
                raise ValueError("Temporary failure")
            return {"success": True, "attempts": call_count["count"]}
        
        node = WorkflowNode(
            node_id="flaky",
            name="Flaky Node",
            action=flaky_action,
            max_retries=5,
            retry_delay_seconds=0.01
        )
        dag.add_node(node)
        
        return dag, call_count
    
    @pytest.fixture
    def dag_with_fallback(self):
        """Create DAG with fallback node."""
        dag = WorkflowDAG(name="FallbackDAG")
        
        def failing_action(ctx):
            raise ValueError("Primary failure")
        
        def fallback_action(ctx):
            return {"result": "fallback_result"}
        
        dag.add_node(WorkflowNode(
            node_id="primary",
            name="Primary",
            action=failing_action,
            fallback_node_id="fallback"
        ))
        dag.add_node(WorkflowNode(
            node_id="fallback",
            name="Fallback",
            action=fallback_action
        ))
        
        return dag
    
    def test_execute_simple_workflow(self, executor, simple_success_dag):
        """Test basic workflow execution."""
        result = executor.execute(simple_success_dag)
        
        assert result["status"] == WorkflowStatus.COMPLETED.value
        assert result["workflow_id"] == simple_success_dag.workflow_id
        assert "execution_time_seconds" in result
    
    def test_execute_tracks_node_results(self, executor, simple_success_dag):
        """Test that node results are tracked."""
        result = executor.execute(simple_success_dag)
        
        assert "node_results" in result
        assert "a" in result["node_results"]
        assert "b" in result["node_results"]
        
        assert result["node_results"]["a"]["status"] == NodeStatus.COMPLETED.value
        assert result["node_results"]["b"]["status"] == NodeStatus.COMPLETED.value
    
    def test_execute_with_context(self, executor):
        """Test execution with initial context."""
        dag = WorkflowDAG()
        received_context = {}
        
        def capture_context(ctx):
            received_context.update(ctx)
            return {"captured": True}
        
        dag.add_node(WorkflowNode("capture", "Capture", capture_context))
        
        initial_context = {"key1": "value1", "key2": 42}
        result = executor.execute(dag, context=initial_context)
        
        assert result["status"] == WorkflowStatus.COMPLETED.value
        assert received_context["key1"] == "value1"
        assert received_context["key2"] == 42
    
    def test_retry_on_failure(self, executor, dag_with_retry):
        """Test that retries are attempted on failure."""
        dag, call_count = dag_with_retry
        
        result = executor.execute(dag)
        
        assert result["status"] == WorkflowStatus.COMPLETED.value
        assert call_count["count"] == 3  # 2 failures + 1 success
    
    def test_final_failure_after_retries(self, executor):
        """Test final failure when retries exhausted."""
        dag = WorkflowDAG()
        
        def always_fails(ctx):
            raise ValueError("Always fails")
        
        dag.add_node(WorkflowNode(
            node_id="failing",
            name="Failing",
            action=always_fails,
            max_retries=2,
            retry_delay_seconds=0.01
        ))
        
        result = executor.execute(dag)
        
        assert result["status"] == WorkflowStatus.FAILED.value
        assert "failing" in result["failed_nodes"]
    
    def test_fallback_recovery(self, executor, dag_with_fallback):
        """Test fallback node execution."""
        dag = dag_with_fallback
        
        result = executor.execute(dag)
        
        assert result["status"] == WorkflowStatus.COMPLETED.value
        # Primary should show as completed (recovered via fallback)
        assert result["node_results"]["primary"]["status"] == NodeStatus.COMPLETED.value
    
    def test_parallel_execution(self, executor):
        """Test that parallel nodes execute concurrently."""
        dag = WorkflowDAG(name="ParallelDAG")
        
        execution_times = {}
        
        def make_delayed_action(node_id: str, delay: float):
            def action(ctx):
                start = time.time()
                time.sleep(delay)
                execution_times[node_id] = time.time() - start
                return {"node": node_id}
            return action
        
        dag.add_node(WorkflowNode("slow1", "Slow 1", make_delayed_action("slow1", 0.1), parallelizable=True))
        dag.add_node(WorkflowNode("slow2", "Slow 2", make_delayed_action("slow2", 0.1), parallelizable=True))
        dag.add_node(WorkflowNode("slow3", "Slow 3", make_delayed_action("slow3", 0.1), parallelizable=True))
        
        start = time.time()
        result = executor.execute(dag)
        total_time = time.time() - start
        
        assert result["status"] == WorkflowStatus.COMPLETED.value
        # If truly parallel, should take ~0.1s not ~0.3s
        assert total_time < 0.25, f"Parallel execution took {total_time}s, expected < 0.25s"
    
    def test_conditional_skip(self, executor):
        """Test conditional node skipping."""
        dag = WorkflowDAG()
        
        executed = {"skipped": False, "not_skipped": False}
        
        dag.add_node(WorkflowNode("start", "Start", lambda ctx: {"value": 10}))
        dag.add_node(WorkflowNode(
            node_id="skip_me",
            name="Skip Me",
            action=lambda ctx: executed.update({"skipped": True}) or {"done": True},
            condition=lambda ctx: ctx.get("value", 0) > 100  # False, will skip
        ))
        dag.add_node(WorkflowNode(
            node_id="run_me",
            name="Run Me",
            action=lambda ctx: executed.update({"not_skipped": True}) or {"done": True},
            condition=lambda ctx: ctx.get("value", 0) < 100  # True, will run
        ))
        
        result = executor.execute(dag)
        
        assert result["status"] == WorkflowStatus.COMPLETED.value
        assert executed["not_skipped"] is True
        # Skipped nodes still complete but with skipped status
        assert result["node_results"]["skip_me"]["status"] == NodeStatus.SKIPPED.value
    
    def test_checkpoint_created(self, executor, simple_success_dag):
        """Test that checkpoints are created during execution."""
        result = executor.execute(simple_success_dag)
        
        checkpoint_id = result["checkpoint_id"]
        checkpoint = executor.get_checkpoint(checkpoint_id)
        
        assert checkpoint is not None
        assert checkpoint.workflow_id == simple_success_dag.workflow_id
        assert checkpoint.status == WorkflowStatus.COMPLETED
    
    def test_checkpoint_integrity(self, executor, simple_success_dag):
        """Test checkpoint integrity verification."""
        result = executor.execute(simple_success_dag)
        
        checkpoint = executor.get_checkpoint(result["checkpoint_id"])
        
        assert checkpoint.verify() is True
    
    def test_execution_trace(self, executor, simple_success_dag):
        """Test execution tracing."""
        result = executor.execute(simple_success_dag)
        
        trace = executor.get_execution_trace(result["execution_id"])
        
        assert len(trace) > 0
        assert any(e["event"] == "execution_started" for e in trace)
        assert any(e["event"] == "execution_completed" for e in trace)


class TestWorkflowHelperFunctions:
    """Test helper functions for creating common workflow patterns."""
    
    def test_create_parallel_workflow(self):
        """Test parallel workflow creation helper."""
        tasks = [
            ("task1", "Task 1", lambda ctx: "r1"),
            ("task2", "Task 2", lambda ctx: "r2"),
            ("task3", "Task 3", lambda ctx: "r3")
        ]
        
        workflow = create_parallel_workflow("ParallelWorkflow", tasks)
        
        assert workflow.name == "ParallelWorkflow"
        assert len(workflow.nodes) == 3
        assert len(workflow.edges) == 0  # No edges in pure parallel
        assert workflow.get_entry_nodes() == {"task1", "task2", "task3"}
        
        # All should be parallelizable
        for node in workflow.nodes.values():
            assert node.parallelizable is True
    
    def test_create_sequential_workflow(self):
        """Test sequential workflow creation helper."""
        tasks = [
            ("step1", "Step 1", lambda ctx: "r1"),
            ("step2", "Step 2", lambda ctx: "r2"),
            ("step3", "Step 3", lambda ctx: "r3")
        ]
        
        workflow = create_sequential_workflow("SequentialWorkflow", tasks)
        
        assert workflow.name == "SequentialWorkflow"
        assert len(workflow.nodes) == 3
        assert len(workflow.edges) == 2
        
        # Check edges connect in sequence
        assert workflow.edges[0].from_node == "step1"
        assert workflow.edges[0].to_node == "step2"
        assert workflow.edges[1].from_node == "step2"
        assert workflow.edges[1].to_node == "step3"
        
        # All should be sequential (not parallelizable)
        for node in workflow.nodes.values():
            assert node.parallelizable is False
    
    def test_create_map_reduce_workflow(self):
        """Test map-reduce workflow creation helper."""
        map_tasks = [
            ("map1", "Map 1", lambda ctx: "m1"),
            ("map2", "Map 2", lambda ctx: "m2")
        ]
        reduce_task = ("reduce", "Reduce", lambda ctx: "reduced")
        
        workflow = create_map_reduce_workflow("MapReduceWorkflow", map_tasks, reduce_task)
        
        assert workflow.name == "MapReduceWorkflow"
        assert len(workflow.nodes) == 3
        
        # Map nodes should have no dependencies (entry points)
        assert "map1" in workflow.get_entry_nodes()
        assert "map2" in workflow.get_entry_nodes()
        
        # Reduce node should depend on both map nodes
        assert workflow.get_dependencies("reduce") == {"map1", "map2"}
        
        # Reduce should be the exit node
        assert workflow.get_exit_nodes() == {"reduce"}


class TestComplexWorkflows:
    """Test complex workflow scenarios."""
    
    def test_multi_level_parallel_execution(self):
        """Test workflow with multiple levels of parallel execution."""
        dag = WorkflowDAG(name="MultiLevelParallel")
        
        # Level 0: 1 node
        dag.add_node(WorkflowNode("input", "Input", lambda ctx: {"data": [1, 2, 3, 4]}))
        
        # Level 1: 4 parallel nodes
        for i in range(4):
            dag.add_node(WorkflowNode(
                f"process_{i}",
                f"Process {i}",
                lambda ctx, idx=i: {"processed": idx},
                parallelizable=True
            ))
            dag.connect("input", f"process_{i}")
        
        # Level 2: 2 parallel aggregation nodes
        dag.add_node(WorkflowNode("agg_1", "Agg 1", lambda ctx: {"agg": 1}, parallelizable=True, requires=["process_0", "process_1"]))
        dag.add_node(WorkflowNode("agg_2", "Agg 2", lambda ctx: {"agg": 2}, parallelizable=True, requires=["process_2", "process_3"]))
        dag.connect("process_0", "agg_1")
        dag.connect("process_1", "agg_1")
        dag.connect("process_2", "agg_2")
        dag.connect("process_3", "agg_2")
        
        # Level 3: 1 final node
        dag.add_node(WorkflowNode("output", "Output", lambda ctx: {"final": True}))
        dag.connect("agg_1", "output")
        dag.connect("agg_2", "output")
        
        executor = WorkflowExecutor(max_workers=4)
        result = executor.execute(dag)
        
        assert result["status"] == WorkflowStatus.COMPLETED.value
        
        # Verify execution levels
        levels = dag.get_execution_levels()
        assert len(levels) == 4
        assert levels[0] == {"input"}
        assert len(levels[1]) == 4
        assert len(levels[2]) == 2
        assert levels[3] == {"output"}
    
    def test_error_propagation(self):
        """Test that errors in dependencies block dependent nodes."""
        dag = WorkflowDAG()
        
        def success_action(ctx):
            return {"status": "success"}
        
        def fail_action(ctx):
            raise ValueError("Intentional failure")
        
        dag.add_node(WorkflowNode("start", "Start", success_action))
        dag.add_node(WorkflowNode("fail", "Fail", fail_action))
        dag.add_node(WorkflowNode("after_fail", "After Fail", success_action))
        
        dag.connect("start", "fail")
        dag.connect("fail", "after_fail")  # This should be skipped
        
        executor = WorkflowExecutor()
        result = executor.execute(dag)
        
        assert result["status"] == WorkflowStatus.FAILED.value
        assert result["node_results"]["start"]["status"] == NodeStatus.COMPLETED.value
        assert result["node_results"]["fail"]["status"] == NodeStatus.FAILED.value
        # after_fail will be PENDING since workflow fails before it runs
        # or it may not be in results at all
        if "after_fail" in result["node_results"]:
            assert result["node_results"]["after_fail"]["status"] in [
                NodeStatus.PENDING.value, 
                NodeStatus.SKIPPED.value
            ]
    
    def test_node_result_to_dict(self):
        """Test NodeResult serialization."""
        result = NodeResult(
            node_id="test_node",
            status=NodeStatus.COMPLETED,
            output={"key": "value"},
            started_at=1234567890.0,
            completed_at=1234567900.0,
            retry_count=2,
            execution_time_ms=10000.0
        )
        
        data = result.to_dict()
        
        assert data["node_id"] == "test_node"
        assert data["status"] == "completed"
        assert data["output"] == {"key": "value"}
        assert data["retry_count"] == 2
        assert data["execution_time_ms"] == 10000.0
    
    def test_checkpoint_to_dict(self):
        """Test Checkpoint serialization."""
        checkpoint = WorkflowCheckpoint(
            checkpoint_id="chk_123",
            workflow_id="wf_456",
            created_at=1234567890.0,
            node_results={},
            context={},
            status=WorkflowStatus.RUNNING
        )
        
        data = checkpoint.to_dict()
        
        assert data["checkpoint_id"] == "chk_123"
        assert data["workflow_id"] == "wf_456"
        assert data["status"] == "running"
        assert "hash" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
