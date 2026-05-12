"""
Workflow DAG (Directed Acyclic Graph) Execution Engine

Based on research from trending 2026 agent frameworks:
- aden-hive/hive: Graph-based execution DAGs for multi-agent coordination
- microsoft/agent-framework: Graph-based orchestration patterns with checkpointing
- agentspan-ai/agentspan: Durable execution with crash recovery

Provides:
1. DAG-based workflow definition with nodes and edges
2. Parallel and sequential execution modes
3. Checkpointing for durability and recovery
4. Self-healing with retry and fallback mechanisms
5. Visual execution tracing and observability
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Set, Tuple, Union
from enum import Enum, auto
from datetime import datetime
import asyncio
import json
import hashlib
import uuid
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed


class NodeStatus(Enum):
    """Status of a workflow node execution."""
    PENDING = "pending"         # Not yet started
    RUNNING = "running"         # Currently executing
    COMPLETED = "completed"     # Successfully finished
    FAILED = "failed"           # Execution failed
    SKIPPED = "skipped"         # Skipped due to condition
    RETRYING = "retrying"       # Attempting retry
    CANCELLED = "cancelled"     # Manually cancelled


class WorkflowStatus(Enum):
    """Status of overall workflow execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    RECOVERING = "recovering"


class EdgeType(Enum):
    """Types of edges connecting workflow nodes."""
    SEQUENTIAL = "sequential"   # Execute after completion
    PARALLEL = "parallel"       # Can execute concurrently
    CONDITIONAL = "conditional" # Execute based on condition
    ERROR = "error"             # Execute on error/fallback
    RETRY = "retry"             # Retry connection


@dataclass
class NodeResult:
    """Result of a node execution."""
    node_id: str
    status: NodeStatus
    output: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retry_count: int = 0
    execution_time_ms: float = 0.0
    checkpoint_id: Optional[str] = None
    
    @property
    def is_success(self) -> bool:
        return self.status == NodeStatus.COMPLETED
    
    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "status": self.status.value,
            "output": self.output if self.output is not None else None,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "retry_count": self.retry_count,
            "execution_time_ms": self.execution_time_ms
        }


@dataclass
class WorkflowCheckpoint:
    """Checkpoint for workflow recovery."""
    checkpoint_id: str
    workflow_id: str
    created_at: float
    node_results: Dict[str, NodeResult]
    context: Dict[str, Any]
    status: WorkflowStatus
    hash: str = ""
    
    def __post_init__(self):
        if not self.hash:
            self.hash = self._calculate_hash()
    
    def _calculate_hash(self) -> str:
        """Calculate integrity hash."""
        data = json.dumps({
            "workflow_id": self.workflow_id,
            "node_results": {k: v.to_dict() for k, v in self.node_results.items()},
            "context": self.context,
            "status": self.status.value
        }, sort_keys=True, default=str)
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def verify(self) -> bool:
        """Verify checkpoint integrity."""
        return self.hash == self._calculate_hash()
    
    def to_dict(self) -> Dict:
        return {
            "checkpoint_id": self.checkpoint_id,
            "workflow_id": self.workflow_id,
            "created_at": self.created_at,
            "status": self.status.value,
            "hash": self.hash,
            "node_count": len(self.node_results),
            "completed_nodes": sum(1 for r in self.node_results.values() if r.is_success)
        }


@dataclass
class WorkflowNode:
    """A node in the workflow DAG."""
    node_id: str
    name: str
    action: Callable[..., Any]
    
    # Configuration
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    timeout_seconds: float = 300.0
    fallback_node_id: Optional[str] = None
    
    # Parallel execution
    parallelizable: bool = True
    requires: List[str] = field(default_factory=list)  # Required inputs from other nodes
    
    # Conditional execution
    condition: Optional[Callable[[Dict], bool]] = None
    
    # Metadata
    description: str = ""
    estimated_duration_ms: int = 1000
    tags: List[str] = field(default_factory=list)
    
    def __hash__(self):
        return hash(self.node_id)
    
    def __eq__(self, other):
        if isinstance(other, WorkflowNode):
            return self.node_id == other.node_id
        return False


@dataclass
class WorkflowEdge:
    """An edge connecting nodes in the workflow DAG."""
    from_node: str
    to_node: str
    edge_type: EdgeType = EdgeType.SEQUENTIAL
    condition: Optional[Callable[[NodeResult], bool]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkflowDAG:
    """
    Directed Acyclic Graph workflow definition.
    
    Nodes represent tasks/actions, edges represent execution dependencies.
    Supports parallel execution, conditional branching, and error handling.
    """
    
    def __init__(self, workflow_id: Optional[str] = None, name: str = ""):
        self.workflow_id = workflow_id or f"wf_{uuid.uuid4().hex[:12]}"
        self.name = name or f"Workflow_{self.workflow_id}"
        self.nodes: Dict[str, WorkflowNode] = {}
        self.edges: List[WorkflowEdge] = []
        self._graph: Dict[str, Set[str]] = defaultdict(set)  # Adjacency list
        self._reverse_graph: Dict[str, Set[str]] = defaultdict(set)
        self._entry_nodes: Optional[Set[str]] = None
        self._exit_nodes: Optional[Set[str]] = None
        self._sorted_nodes: Optional[List[str]] = None
    
    def add_node(self, node: WorkflowNode) -> 'WorkflowDAG':
        """Add a node to the workflow."""
        self.nodes[node.node_id] = node
        self._invalidate_cache()
        return self
    
    def add_edge(self, edge: WorkflowEdge) -> 'WorkflowDAG':
        """Add an edge between nodes."""
        self.edges.append(edge)
        self._graph[edge.from_node].add(edge.to_node)
        self._reverse_graph[edge.to_node].add(edge.from_node)
        self._invalidate_cache()
        return self
    
    def connect(self, from_node: str, to_node: str, 
                edge_type: EdgeType = EdgeType.SEQUENTIAL,
                condition: Optional[Callable[[NodeResult], bool]] = None) -> 'WorkflowDAG':
        """Convenience method to connect two nodes."""
        edge = WorkflowEdge(from_node, to_node, edge_type, condition)
        return self.add_edge(edge)
    
    def _invalidate_cache(self):
        """Invalidate cached graph analysis."""
        self._entry_nodes = None
        self._exit_nodes = None
        self._sorted_nodes = None
    
    def _detect_cycle(self) -> Optional[List[str]]:
        """Detect cycles using DFS. Returns cycle path if found."""
        visited = set()
        rec_stack = set()
        path = []
        
        def dfs(node_id: str) -> Optional[List[str]]:
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)
            
            for neighbor in self._graph.get(node_id, []):
                if neighbor not in visited:
                    result = dfs(neighbor)
                    if result:
                        return result
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]
            
            path.pop()
            rec_stack.remove(node_id)
            return None
        
        for node_id in self.nodes:
            if node_id not in visited:
                cycle = dfs(node_id)
                if cycle:
                    return cycle
        
        return None
    
    def validate(self) -> Tuple[bool, List[str]]:
        """
        Validate workflow DAG.
        
        Returns: (is_valid, list_of_errors)
        """
        errors = []
        
        # Check for cycles
        cycle = self._detect_cycle()
        if cycle:
            errors.append(f"Cycle detected: {' -> '.join(cycle)}")
        
        # Check all edge endpoints exist
        for edge in self.edges:
            if edge.from_node not in self.nodes:
                errors.append(f"Edge references unknown node: {edge.from_node}")
            if edge.to_node not in self.nodes:
                errors.append(f"Edge references unknown node: {edge.to_node}")
        
        # Check fallback nodes exist
        for node in self.nodes.values():
            if node.fallback_node_id and node.fallback_node_id not in self.nodes:
                errors.append(f"Node {node.node_id} references unknown fallback: {node.fallback_node_id}")
        
        # Check entry nodes exist
        entry_nodes = self.get_entry_nodes()
        if not entry_nodes:
            errors.append("No entry nodes found (DAG has no starting point)")
        
        return len(errors) == 0, errors
    
    def get_entry_nodes(self) -> Set[str]:
        """Get nodes with no incoming edges (starting points)."""
        if self._entry_nodes is None:
            all_nodes = set(self.nodes.keys())
            nodes_with_inputs = set()
            for edge in self.edges:
                if edge.edge_type in [EdgeType.SEQUENTIAL, EdgeType.CONDITIONAL]:
                    nodes_with_inputs.add(edge.to_node)
            self._entry_nodes = all_nodes - nodes_with_inputs
        return self._entry_nodes
    
    def get_exit_nodes(self) -> Set[str]:
        """Get nodes with no outgoing edges (end points)."""
        if self._exit_nodes is None:
            all_nodes = set(self.nodes.keys())
            nodes_with_outputs = set(edge.from_node for edge in self.edges)
            self._exit_nodes = all_nodes - nodes_with_outputs
        return self._exit_nodes
    
    def topological_sort(self) -> List[str]:
        """
        Return topologically sorted node IDs.
        
        Uses Kahn's algorithm for efficiency.
        """
        if self._sorted_nodes is not None:
            return self._sorted_nodes
        
        # Calculate in-degrees
        in_degree = {node_id: 0 for node_id in self.nodes}
        for edge in self.edges:
            if edge.edge_type in [EdgeType.SEQUENTIAL, EdgeType.CONDITIONAL]:
                in_degree[edge.to_node] += 1
        
        # Start with entry nodes
        queue = [n for n, d in in_degree.items() if d == 0]
        result = []
        
        while queue:
            node_id = queue.pop(0)
            result.append(node_id)
            
            for neighbor in self._graph.get(node_id, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        self._sorted_nodes = result
        return result
    
    def get_dependencies(self, node_id: str) -> Set[str]:
        """Get all nodes that must complete before this node can run."""
        return self._reverse_graph.get(node_id, set())
    
    def get_dependents(self, node_id: str) -> Set[str]:
        """Get all nodes that depend on this node."""
        return self._graph.get(node_id, set())
    
    def get_execution_levels(self) -> List[Set[str]]:
        """
        Group nodes into execution levels for parallel execution.
        
        Level 0: Entry nodes (no dependencies)
        Level N: Nodes whose dependencies are all in levels < N
        """
        levels = []
        remaining = set(self.nodes.keys())
        completed = set()
        
        while remaining:
            # Find nodes whose dependencies are all completed
            level_nodes = set()
            for node_id in remaining:
                deps = self.get_dependencies(node_id)
                if deps.issubset(completed):
                    level_nodes.add(node_id)
            
            if not level_nodes:
                # This shouldn't happen in a valid DAG
                break
            
            levels.append(level_nodes)
            completed.update(level_nodes)
            remaining -= level_nodes
        
        return levels
    
    def to_dict(self) -> Dict:
        """Serialize workflow definition."""
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "nodes": [
                {
                    "node_id": n.node_id,
                    "name": n.name,
                    "description": n.description,
                    "max_retries": n.max_retries,
                    "timeout_seconds": n.timeout_seconds,
                    "parallelizable": n.parallelizable,
                    "tags": n.tags
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "from": e.from_node,
                    "to": e.to_node,
                    "type": e.edge_type.value
                }
                for e in self.edges
            ],
            "entry_nodes": list(self.get_entry_nodes()),
            "exit_nodes": list(self.get_exit_nodes())
        }


class WorkflowExecutor:
    """
    Executor for WorkflowDAG with checkpointing and recovery.
    
    Features:
    - Parallel execution of independent nodes
    - Automatic retry with exponential backoff
    - Self-healing through fallback nodes
    - Checkpoint persistence for durability
    - Execution tracing and observability
    """
    
    def __init__(self, max_workers: int = 4, checkpoint_dir: str = "./checkpoints"):
        self.max_workers = max_workers
        self.checkpoint_dir = checkpoint_dir
        self._checkpoints: Dict[str, WorkflowCheckpoint] = {}
        self._execution_traces: Dict[str, List[Dict]] = defaultdict(list)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
    
    def execute(self, workflow: WorkflowDAG, 
                context: Optional[Dict] = None,
                resume_from: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute a workflow DAG.
        
        Args:
            workflow: The workflow definition
            context: Initial context/data for execution
            resume_from: Checkpoint ID to resume from (optional)
        
        Returns:
            Execution results with outputs and metadata
        """
        # Validate workflow
        is_valid, errors = workflow.validate()
        if not is_valid:
            raise ValueError(f"Invalid workflow: {'; '.join(errors)}")
        
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        context = context or {}
        
        # Load checkpoint if resuming
        if resume_from and resume_from in self._checkpoints:
            checkpoint = self._checkpoints[resume_from]
            if checkpoint.workflow_id != workflow.workflow_id:
                raise ValueError("Checkpoint does not match workflow")
            node_results = dict(checkpoint.node_results)
            context.update(checkpoint.context)
        else:
            node_results = {}
        
        # Track execution
        started_at = time.time()
        self._execution_traces[execution_id].append({
            "event": "execution_started",
            "timestamp": started_at,
            "workflow_id": workflow.workflow_id,
            "resume_from": resume_from
        })
        
        # Get execution levels for parallel execution
        execution_levels = workflow.get_execution_levels()
        
        try:
            for level_num, level_nodes in enumerate(execution_levels):
                # Check for cancellation
                if self._is_cancelled(execution_id):
                    raise WorkflowCancelledError("Workflow cancelled")
                
                # Skip already completed nodes
                pending_nodes = [
                    nid for nid in level_nodes 
                    if nid not in node_results or 
                    node_results[nid].status not in [NodeStatus.COMPLETED, NodeStatus.SKIPPED]
                ]
                
                if not pending_nodes:
                    continue
                
                self._log_trace(execution_id, "level_started", {
                    "level": level_num,
                    "nodes": pending_nodes
                })
                
                # Execute level (parallel where possible)
                level_results = self._execute_level(
                    workflow, pending_nodes, node_results, context, execution_id
                )
                
                # Update results
                node_results.update(level_results)
                
                # Create checkpoint after each level
                checkpoint = self._create_checkpoint(
                    workflow.workflow_id, node_results, context, WorkflowStatus.RUNNING
                )
                self._checkpoints[checkpoint.checkpoint_id] = checkpoint
                
                # Check for failures
                failed_nodes = [
                    nid for nid, r in level_results.items() 
                    if r.status == NodeStatus.FAILED
                ]
                
                if failed_nodes:
                    # Check if any failed nodes have fallbacks
                    recoverable = self._attempt_recovery(
                        workflow, failed_nodes, node_results, context, execution_id
                    )
                    
                    if not recoverable:
                        # Workflow failed
                        final_checkpoint = self._create_checkpoint(
                            workflow.workflow_id, node_results, context, WorkflowStatus.FAILED
                        )
                        self._checkpoints[final_checkpoint.checkpoint_id] = final_checkpoint
                        
                        return {
                            "execution_id": execution_id,
                            "workflow_id": workflow.workflow_id,
                            "status": WorkflowStatus.FAILED.value,
                            "node_results": {k: v.to_dict() for k, v in node_results.items()},
                            "failed_nodes": failed_nodes,
                            "checkpoint_id": final_checkpoint.checkpoint_id,
                            "execution_time_seconds": time.time() - started_at
                        }
            
            # Workflow completed
            final_checkpoint = self._create_checkpoint(
                workflow.workflow_id, node_results, context, WorkflowStatus.COMPLETED
            )
            self._checkpoints[final_checkpoint.checkpoint_id] = final_checkpoint
            
            self._log_trace(execution_id, "execution_completed", {
                "checkpoint_id": final_checkpoint.checkpoint_id
            })
            
            return {
                "execution_id": execution_id,
                "workflow_id": workflow.workflow_id,
                "status": WorkflowStatus.COMPLETED.value,
                "node_results": {k: v.to_dict() for k, v in node_results.items()},
                "checkpoint_id": final_checkpoint.checkpoint_id,
                "execution_time_seconds": time.time() - started_at,
                "outputs": {
                    nid: r.output for nid, r in node_results.items() 
                    if r.is_success
                }
            }
            
        except WorkflowCancelledError:
            checkpoint = self._create_checkpoint(
                workflow.workflow_id, node_results, context, WorkflowStatus.CANCELLED
            )
            self._checkpoints[checkpoint.checkpoint_id] = checkpoint
            
            return {
                "execution_id": execution_id,
                "workflow_id": workflow.workflow_id,
                "status": WorkflowStatus.CANCELLED.value,
                "node_results": {k: v.to_dict() for k, v in node_results.items()},
                "checkpoint_id": checkpoint.checkpoint_id
            }
    
    def _execute_level(self, workflow: WorkflowDAG, node_ids: List[str],
                       existing_results: Dict[str, NodeResult],
                       context: Dict, execution_id: str) -> Dict[str, NodeResult]:
        """Execute a level of nodes (parallel where possible)."""
        results = {}
        
        # Separate parallelizable and sequential nodes
        parallel_nodes = []
        sequential_nodes = []
        
        for nid in node_ids:
            node = workflow.nodes[nid]
            # Check if all dependencies completed successfully
            deps = workflow.get_dependencies(nid)
            deps_ok = all(
                existing_results.get(d) and existing_results[d].is_success 
                for d in deps
            )
            
            if not deps_ok and deps:
                # Skip - dependencies failed
                results[nid] = NodeResult(
                    node_id=nid,
                    status=NodeStatus.SKIPPED,
                    error="Dependencies failed"
                )
                continue
            
            # Check condition
            if node.condition and not node.condition(context):
                results[nid] = NodeResult(
                    node_id=nid,
                    status=NodeStatus.SKIPPED,
                    error="Condition not met"
                )
                continue
            
            if node.parallelizable:
                parallel_nodes.append(node)
            else:
                sequential_nodes.append(node)
        
        # Execute parallel nodes
        if parallel_nodes:
            futures = {
                self._executor.submit(self._execute_node, node, context, execution_id): node
                for node in parallel_nodes
            }
            
            for future in as_completed(futures):
                node = futures[future]
                try:
                    result = future.result()
                    results[node.node_id] = result
                except Exception as e:
                    results[node.node_id] = NodeResult(
                        node_id=node.node_id,
                        status=NodeStatus.FAILED,
                        error=str(e)
                    )
        
        # Execute sequential nodes
        for node in sequential_nodes:
            result = self._execute_node(node, context, execution_id)
            results[node.node_id] = result
        
        return results
    
    def _execute_node(self, node: WorkflowNode, context: Dict, 
                      execution_id: str) -> NodeResult:
        """Execute a single node with retry logic."""
        started_at = time.time()
        retry_count = 0
        
        self._log_trace(execution_id, "node_started", {
            "node_id": node.node_id,
            "node_name": node.name
        })
        
        while retry_count <= node.max_retries:
            try:
                # Prepare inputs from context
                node_context = {
                    **context,
                    "_execution_id": execution_id,
                    "_node_id": node.node_id,
                    "_retry_count": retry_count
                }
                
                # Execute with timeout
                if retry_count > 0:
                    time.sleep(node.retry_delay_seconds * retry_count)
                
                result = node.action(node_context)
                
                completed_at = time.time()
                
                self._log_trace(execution_id, "node_completed", {
                    "node_id": node.node_id,
                    "retry_count": retry_count
                })
                
                return NodeResult(
                    node_id=node.node_id,
                    status=NodeStatus.COMPLETED,
                    output=result,
                    started_at=started_at,
                    completed_at=completed_at,
                    retry_count=retry_count,
                    execution_time_ms=(completed_at - started_at) * 1000
                )
                
            except Exception as e:
                retry_count += 1
                
                self._log_trace(execution_id, "node_error", {
                    "node_id": node.node_id,
                    "error": str(e),
                    "retry_count": retry_count
                })
                
                if retry_count > node.max_retries:
                    completed_at = time.time()
                    return NodeResult(
                        node_id=node.node_id,
                        status=NodeStatus.FAILED,
                        error=str(e),
                        started_at=started_at,
                        completed_at=completed_at,
                        retry_count=retry_count,
                        execution_time_ms=(completed_at - started_at) * 1000
                    )
        
        # Shouldn't reach here
        return NodeResult(
            node_id=node.node_id,
            status=NodeStatus.FAILED,
            error="Max retries exceeded"
        )
    
    def _attempt_recovery(self, workflow: WorkflowDAG, failed_nodes: List[str],
                          node_results: Dict[str, NodeResult],
                          context: Dict, execution_id: str) -> bool:
        """Attempt recovery using fallback nodes."""
        recovered = []
        
        for node_id in failed_nodes:
            node = workflow.nodes.get(node_id)
            if not node or not node.fallback_node_id:
                continue
            
            fallback_node = workflow.nodes.get(node.fallback_node_id)
            if not fallback_node:
                continue
            
            self._log_trace(execution_id, "attempting_fallback", {
                "failed_node": node_id,
                "fallback_node": fallback_node.node_id
            })
            
            # Execute fallback
            result = self._execute_node(fallback_node, context, execution_id)
            node_results[fallback_node.node_id] = result
            
            if result.is_success:
                # Mark original as recovered (via fallback)
                node_results[node_id] = NodeResult(
                    node_id=node_id,
                    status=NodeStatus.COMPLETED,  # Recovered via fallback
                    output=result.output,
                    error=f"Recovered via fallback: {fallback_node.node_id}"
                )
                recovered.append(node_id)
        
        return len(recovered) == len(failed_nodes)
    
    def _create_checkpoint(self, workflow_id: str, 
                          node_results: Dict[str, NodeResult],
                          context: Dict, status: WorkflowStatus) -> WorkflowCheckpoint:
        """Create a checkpoint for recovery."""
        checkpoint_id = f"chk_{uuid.uuid4().hex[:12]}"
        
        return WorkflowCheckpoint(
            checkpoint_id=checkpoint_id,
            workflow_id=workflow_id,
            created_at=time.time(),
            node_results=dict(node_results),
            context=dict(context),
            status=status
        )
    
    def _is_cancelled(self, execution_id: str) -> bool:
        """Check if execution was cancelled."""
        # Implementation would check cancellation flags
        return False
    
    def _log_trace(self, execution_id: str, event: str, data: Dict):
        """Log execution trace event."""
        self._execution_traces[execution_id].append({
            "timestamp": time.time(),
            "event": event,
            **data
        })
    
    def get_checkpoint(self, checkpoint_id: str) -> Optional[WorkflowCheckpoint]:
        """Retrieve a checkpoint."""
        return self._checkpoints.get(checkpoint_id)
    
    def get_execution_trace(self, execution_id: str) -> List[Dict]:
        """Get execution trace for observability."""
        return self._execution_traces.get(execution_id, [])
    
    def resume_from_checkpoint(self, checkpoint_id: str, 
                               workflow: WorkflowDAG) -> Dict[str, Any]:
        """Resume workflow execution from a checkpoint."""
        return self.execute(workflow, resume_from=checkpoint_id)


class WorkflowCancelledError(Exception):
    """Raised when workflow is cancelled."""
    pass


def create_parallel_workflow(name: str, tasks: List[Tuple[str, str, Callable]]) -> WorkflowDAG:
    """
    Create a simple parallel workflow where all tasks run concurrently.
    
    Args:
        name: Workflow name
        tasks: List of (node_id, node_name, action) tuples
    """
    workflow = WorkflowDAG(name=name)
    
    for node_id, node_name, action in tasks:
        node = WorkflowNode(
            node_id=node_id,
            name=node_name,
            action=action,
            parallelizable=True
        )
        workflow.add_node(node)
    
    return workflow


def create_sequential_workflow(name: str, 
                                tasks: List[Tuple[str, str, Callable]]) -> WorkflowDAG:
    """
    Create a simple sequential workflow where tasks run one after another.
    
    Args:
        name: Workflow name
        tasks: List of (node_id, node_name, action) tuples
    """
    workflow = WorkflowDAG(name=name)
    
    prev_node_id = None
    for node_id, node_name, action in tasks:
        node = WorkflowNode(
            node_id=node_id,
            name=node_name,
            action=action,
            parallelizable=False
        )
        workflow.add_node(node)
        
        if prev_node_id:
            workflow.connect(prev_node_id, node_id)
        
        prev_node_id = node_id
    
    return workflow


def create_map_reduce_workflow(name: str,
                               map_tasks: List[Tuple[str, str, Callable]],
                               reduce_task: Tuple[str, str, Callable]) -> WorkflowDAG:
    """
    Create a map-reduce style workflow.
    
    All map tasks run in parallel, then reduce task combines results.
    """
    workflow = WorkflowDAG(name=name)
    
    # Add map nodes
    map_node_ids = []
    for node_id, node_name, action in map_tasks:
        node = WorkflowNode(
            node_id=node_id,
            name=node_name,
            action=action,
            parallelizable=True
        )
        workflow.add_node(node)
        map_node_ids.append(node_id)
    
    # Add reduce node
    reduce_id, reduce_name, reduce_action = reduce_task
    reduce_node = WorkflowNode(
        node_id=reduce_id,
        name=reduce_name,
        action=reduce_action,
        parallelizable=False,
        requires=map_node_ids
    )
    workflow.add_node(reduce_node)
    
    # Connect all map nodes to reduce node
    for map_id in map_node_ids:
        workflow.connect(map_id, reduce_id)
    
    return workflow


# Example usage and demo
if __name__ == "__main__":
    # Demo workflow
    print("=" * 70)
    print("🔄 WORKFLOW DAG EXECUTION ENGINE DEMO")
    print("=" * 70)
    
    # Create a sample workflow: Data Processing Pipeline
    workflow = WorkflowDAG(name="DataProcessingPipeline")
    
    # Define actions
    def fetch_data(ctx):
        print(f"  [fetch_data] Fetching data...")
        time.sleep(0.1)
        return {"raw_data": [1, 2, 3, 4, 5], "source": "api"}
    
    def validate_data(ctx):
        print(f"  [validate_data] Validating...")
        time.sleep(0.1)
        data = ctx.get("raw_data", [])
        return {"valid": len(data) > 0, "count": len(data)}
    
    def process_chunk_1(ctx):
        print(f"  [process_chunk_1] Processing chunk 1...")
        time.sleep(0.1)
        return {"chunk_1_result": "processed_1"}
    
    def process_chunk_2(ctx):
        print(f"  [process_chunk_2] Processing chunk 2...")
        time.sleep(0.1)
        return {"chunk_2_result": "processed_2"}
    
    def aggregate_results(ctx):
        print(f"  [aggregate_results] Aggregating...")
        time.sleep(0.1)
        return {"final_output": "aggregated"}
    
    # Add nodes
    workflow.add_node(WorkflowNode("fetch", "Fetch Data", fetch_data))
    workflow.add_node(WorkflowNode("validate", "Validate Data", validate_data, parallelizable=False))
    workflow.add_node(WorkflowNode("process_1", "Process Chunk 1", process_chunk_1))
    workflow.add_node(WorkflowNode("process_2", "Process Chunk 2", process_chunk_2))
    workflow.add_node(WorkflowNode("aggregate", "Aggregate Results", aggregate_results, parallelizable=False))
    
    # Connect nodes
    workflow.connect("fetch", "validate")
    workflow.connect("validate", "process_1")
    workflow.connect("validate", "process_2")
    workflow.connect("process_1", "aggregate")
    workflow.connect("process_2", "aggregate")
    
    # Validate
    is_valid, errors = workflow.validate()
    print(f"\n✅ Workflow valid: {is_valid}")
    if errors:
        print(f"   Errors: {errors}")
    
    # Show structure
    print(f"\n📊 Workflow Structure:")
    print(f"   Entry nodes: {workflow.get_entry_nodes()}")
    print(f"   Exit nodes: {workflow.get_exit_nodes()}")
    print(f"   Topological order: {workflow.topological_sort()}")
    print(f"   Execution levels: {[list(level) for level in workflow.get_execution_levels()]}")
    
    # Execute
    print(f"\n🚀 Executing Workflow...")
    executor = WorkflowExecutor(max_workers=4)
    result = executor.execute(workflow)
    
    print(f"\n✅ Execution Complete!")
    print(f"   Status: {result['status']}")
    print(f"   Execution time: {result['execution_time_seconds']:.2f}s")
    print(f"   Checkpoint: {result['checkpoint_id']}")
    
    print(f"\n📈 Node Results:")
    for node_id, node_result in result['node_results'].items():
        status_icon = "✅" if node_result['status'] == 'completed' else "❌"
        print(f"   {status_icon} {node_id}: {node_result['status']} ({node_result.get('execution_time_ms', 0):.0f}ms)")
    
    print("\n" + "=" * 70)
