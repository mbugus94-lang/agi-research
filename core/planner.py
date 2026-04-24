"""
Planner Module - Multi-Step Reasoning with Test-Time Adaptation

Implements Tree of Thought (ToT) planning, test-time refinement,
and MCP tool-aware plan generation based on April 2026 research findings.

Key Research Insights Integrated:
- ARC-AGI: Test-time adaptation critical for compositional generalization
- Agent-World: Environment-driven task synthesis for capability gaps
- SMGI: Structural meta-model for task planning (θ = r, H, Π, L, E, M)
- DeepSeek-R1: "Societies of thought" - internal deliberation via parallel reasoning paths
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any, Tuple, Set
from enum import Enum, auto
import uuid
import json
import time
from collections import defaultdict


class PlanStatus(Enum):
    """Plan execution status."""
    PENDING = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    REFINING = auto()


class NodeStatus(Enum):
    """Individual planning node status."""
    PLANNED = auto()
    EXECUTING = auto()
    COMPLETED = auto()
    FAILED = auto()
    REPLANNED = auto()


@dataclass
class PlanningContext:
    """Context for plan generation and execution."""
    task_description: str
    constraints: List[str] = field(default_factory=list)
    available_tools: List[str] = field(default_factory=list)
    memory_context: Dict[str, Any] = field(default_factory=dict)
    max_depth: int = 5
    max_parallel_branches: int = 3
    refinement_threshold: float = 0.7
    
    def to_dict(self) -> Dict:
        return {
            "task_description": self.task_description,
            "constraints": self.constraints,
            "available_tools": self.available_tools,
            "max_depth": self.max_depth,
            "max_parallel_branches": self.max_parallel_branches,
            "refinement_threshold": self.refinement_threshold
        }


@dataclass
class PlanNode:
    """A single step in a plan with Tree of Thought support."""
    node_id: str
    description: str
    action_type: str  # "tool_call", "reasoning", "subgoal", "decision"
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    expected_output: Optional[str] = None
    alternative_branches: List["PlanNode"] = field(default_factory=list)
    status: NodeStatus = NodeStatus.PLANNED
    execution_time_ms: float = 0.0
    actual_output: Optional[str] = None
    confidence: float = 1.0
    retry_count: int = 0
    max_retries: int = 3
    
    def __post_init__(self):
        if not self.node_id:
            self.node_id = str(uuid.uuid4())[:8]
    
    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "description": self.description,
            "action_type": self.action_type,
            "parameters": self.parameters,
            "dependencies": self.dependencies,
            "expected_output": self.expected_output,
            "alternative_branches": [b.to_dict() for b in self.alternative_branches],
            "status": self.status.name,
            "execution_time_ms": self.execution_time_ms,
            "actual_output": self.actual_output,
            "confidence": self.confidence,
            "retry_count": self.retry_count
        }


@dataclass
class ExecutionTrace:
    """Record of plan execution for learning and refinement."""
    trace_id: str
    plan_id: str
    node_executions: List[Dict] = field(default_factory=list)
    success_rate: float = 0.0
    total_time_ms: float = 0.0
    refinement_triggers: List[str] = field(default_factory=list)
    lessons_learned: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.trace_id:
            self.trace_id = str(uuid.uuid4())[:12]
    
    def record_node_execution(self, node_id: str, success: bool, 
                             output: Any, error: Optional[str] = None):
        """Record execution of a single node."""
        self.node_executions.append({
            "node_id": node_id,
            "success": success,
            "output": str(output)[:500] if output else None,
            "error": error,
            "timestamp": time.time()
        })
        
        # Update running success rate
        successful = sum(1 for e in self.node_executions if e["success"])
        self.success_rate = successful / len(self.node_executions)


@dataclass
class Plan:
    """A complete plan with Tree of Thought structure."""
    plan_id: str
    context: PlanningContext
    root_nodes: List[PlanNode] = field(default_factory=list)
    all_nodes: Dict[str, PlanNode] = field(default_factory=dict)
    status: PlanStatus = PlanStatus.PENDING
    created_at: float = field(default_factory=time.time)
    execution_traces: List[ExecutionTrace] = field(default_factory=list)
    current_trace: Optional[ExecutionTrace] = None
    version: int = 1
    parent_plan_id: Optional[str] = None
    
    def __post_init__(self):
        if not self.plan_id:
            self.plan_id = str(uuid.uuid4())[:12]
        if not self.all_nodes:
            self._index_nodes()
    
    def _index_nodes(self):
        """Index all nodes for fast lookup."""
        self.all_nodes = {}
        
        def add_node(node: PlanNode):
            self.all_nodes[node.node_id] = node
            for branch in node.alternative_branches:
                add_node(branch)
        
        for root in self.root_nodes:
            add_node(root)
    
    def get_ready_nodes(self) -> List[PlanNode]:
        """Get nodes ready for execution (dependencies satisfied)."""
        ready = []
        for node in self.all_nodes.values():
            if node.status != NodeStatus.PLANNED:
                continue
            deps_satisfied = all(
                self.all_nodes.get(dep, PlanNode("", "", "")).status == NodeStatus.COMPLETED
                for dep in node.dependencies
            )
            if deps_satisfied:
                ready.append(node)
        return ready
    
    def get_parallel_groups(self) -> List[List[PlanNode]]:
        """Group nodes into parallel-executable batches."""
        executed = set()
        groups = []
        remaining = set(self.all_nodes.keys())
        
        while remaining:
            group = []
            for node_id in list(remaining):
                node = self.all_nodes[node_id]
                deps = set(node.dependencies)
                if deps <= executed:  # All dependencies satisfied
                    group.append(node)
            
            if not group:
                break  # Deadlock or cycle
            
            groups.append(group)
            for node in group:
                executed.add(node.node_id)
                remaining.remove(node.node_id)
        
        return groups
    
    def to_dict(self) -> Dict:
        return {
            "plan_id": self.plan_id,
            "status": self.status.name,
            "version": self.version,
            "parent_plan_id": self.parent_plan_id,
            "context": self.context.to_dict(),
            "root_nodes": [n.to_dict() for n in self.root_nodes],
            "created_at": self.created_at,
            "trace_count": len(self.execution_traces)
        }


class TreeOfThoughtPlanner:
    """
    Tree of Thought planner with test-time adaptation.
    
    Implements parallel reasoning paths, branch evaluation,
    and dynamic replanning based on execution feedback.
    """
    
    def __init__(self, max_branches: int = 3, exploration_depth: int = 3):
        self.max_branches = max_branches
        self.exploration_depth = exploration_depth
        self.plan_history: List[Plan] = []
        self.execution_patterns: Dict[str, List[bool]] = defaultdict(list)
    
    def generate_plan(self, context: PlanningContext) -> Plan:
        """Generate initial plan with Tree of Thought branching."""
        plan = Plan(
            plan_id=f"plan_{int(time.time())}",
            context=context
        )
        
        # Decompose task into high-level goals
        goals = self._decompose_task(context.task_description)
        
        # For each goal, generate alternative approaches (Tree of Thought)
        for goal in goals:
            root_node = self._generate_goal_node(goal, context)
            plan.root_nodes.append(root_node)
        
        plan._index_nodes()
        self.plan_history.append(plan)
        return plan
    
    def _decompose_task(self, task: str) -> List[str]:
        """Decompose task into subgoals using pattern matching."""
        # Simple decomposition - in production this would use LLM
        task_lower = task.lower()
        
        if "research" in task_lower or "find" in task_lower:
            return [
                "Define search strategy",
                "Gather information from multiple sources",
                "Synthesize and analyze findings",
                "Generate structured output"
            ]
        elif "code" in task_lower or "implement" in task_lower:
            return [
                "Analyze requirements",
                "Design approach",
                "Implement solution",
                "Test and validate"
            ]
        elif "analyze" in task_lower or "evaluate" in task_lower:
            return [
                "Load and validate data",
                "Apply analytical methods",
                "Interpret results",
                "Generate insights"
            ]
        else:
            return [
                "Understand the task",
                "Plan approach",
                "Execute steps",
                "Review and finalize"
            ]
    
    def _generate_goal_node(self, goal: str, context: PlanningContext) -> PlanNode:
        """Generate a goal node with alternative branches."""
        root = PlanNode(
            node_id=f"goal_{uuid.uuid4().hex[:6]}",
            description=goal,
            action_type="subgoal",
            parameters={"goal": goal}
        )
        
        # Generate alternative approaches (Tree of Thought)
        approaches = self._generate_approaches(goal, context)
        
        for approach in approaches[:context.max_parallel_branches]:
            branch = self._generate_approach_branch(approach, context)
            root.alternative_branches.append(branch)
        
        return root
    
    def _generate_approaches(self, goal: str, context: PlanningContext) -> List[str]:
        """Generate alternative approaches for a goal."""
        # Simplified approach generation
        goal_lower = goal.lower()
        
        if "search" in goal_lower or "gather" in goal_lower:
            return [
                "Parallel web search with synthesis",
                "Targeted search with deep analysis",
                "Iterative search with refinement"
            ]
        elif "implement" in goal_lower or "code" in goal_lower:
            return [
                "Test-driven development",
                "Prototype and refine",
                "Reference existing patterns"
            ]
        elif "analyze" in goal_lower:
            return [
                "Statistical analysis",
                "Pattern recognition",
                "Comparative evaluation"
            ]
        else:
            return [
                "Direct approach",
                "Step-by-step decomposition",
                "Pattern-based solution"
            ]
    
    def _generate_approach_branch(self, approach: str, context: PlanningContext) -> PlanNode:
        """Generate a branch for a specific approach."""
        node = PlanNode(
            node_id=f"branch_{uuid.uuid4().hex[:6]}",
            description=approach,
            action_type="reasoning",
            parameters={"approach": approach}
        )
        
        # Add steps based on approach
        if "search" in approach.lower():
            node.dependencies = []
            # Would add web search tool calls here
        elif "code" in approach.lower() or "implement" in approach.lower():
            node.dependencies = []
            # Would add code generation steps
        
        return node
    
    def evaluate_branches(self, plan: Plan, evaluation_fn: Callable[[PlanNode], float]) -> Dict[str, float]:
        """Evaluate alternative branches using provided scoring function."""
        scores = {}
        
        for root in plan.root_nodes:
            for branch in root.alternative_branches:
                score = evaluation_fn(branch)
                scores[branch.node_id] = score
        
        return scores
    
    def select_best_branch(self, root_node: PlanNode, scores: Dict[str, float]) -> Optional[PlanNode]:
        """Select the highest-scoring branch for a goal."""
        if not root_node.alternative_branches:
            return None
        
        best_branch = max(
            root_node.alternative_branches,
            key=lambda b: scores.get(b.node_id, 0.0)
        )
        
        return best_branch if scores.get(best_branch.node_id, 0.0) > 0 else None


class TestTimeAdapter:
    """
    Test-time adaptation for plan refinement during execution.
    
    Based on ARC-AGI research: test-time adaptation critical for
    compositional generalization. Implements dynamic replanning
    when execution confidence falls below threshold.
    """
    
    def __init__(self, refinement_threshold: float = 0.7):
        self.refinement_threshold = refinement_threshold
        self.refinement_history: List[Dict] = []
    
    def should_refine(self, node: PlanNode, execution_result: Any) -> bool:
        """Determine if plan refinement is needed."""
        # Check confidence threshold
        if node.confidence < self.refinement_threshold:
            return True
        
        # Check if result indicates failure
        if isinstance(execution_result, dict):
            if execution_result.get("error") or execution_result.get("success") is False:
                return True
        
        # Check retry count
        if node.retry_count >= node.max_retries:
            return True
        
        return False
    
    def refine_node(self, node: PlanNode, failure_reason: str) -> PlanNode:
        """Create a refined version of a failed node."""
        # Mark original as replanned
        node.status = NodeStatus.REPLANNED
        
        # Create refined node
        refined = PlanNode(
            node_id=f"{node.node_id}_refined",
            description=f"{node.description} (refined: {failure_reason[:50]}...)",
            action_type=node.action_type,
            parameters={**node.parameters, "refinement_reason": failure_reason},
            dependencies=node.dependencies,
            max_retries=node.max_retries,
            expected_output=node.expected_output
        )
        
        # Add to refinement history
        self.refinement_history.append({
            "original_node": node.node_id,
            "refined_node": refined.node_id,
            "reason": failure_reason,
            "timestamp": time.time()
        })
        
        return refined
    
    def adapt_plan(self, plan: Plan, failed_node: PlanNode, 
                   failure_reason: str) -> Plan:
        """Create adapted plan with refined node."""
        # Create refined node
        refined_node = self.refine_node(failed_node, failure_reason)
        
        # Create new plan version
        new_plan = Plan(
            plan_id=f"{plan.plan_id}_v{plan.version + 1}",
            context=plan.context,
            parent_plan_id=plan.plan_id,
            version=plan.version + 1
        )
        
        # Copy and modify nodes
        for root in plan.root_nodes:
            new_root = self._copy_and_replace_node(root, failed_node.node_id, refined_node)
            new_plan.root_nodes.append(new_root)
        
        new_plan._index_nodes()
        return new_plan
    
    def _copy_and_replace_node(self, node: PlanNode, target_id: str, 
                               replacement: PlanNode) -> PlanNode:
        """Recursively copy node tree, replacing target node."""
        if node.node_id == target_id:
            # Update replacement dependencies to point to original's deps
            replacement.dependencies = node.dependencies
            return replacement
        
        # Copy this node
        new_node = PlanNode(
            node_id=node.node_id,
            description=node.description,
            action_type=node.action_type,
            parameters=node.parameters.copy(),
            dependencies=node.dependencies.copy(),
            expected_output=node.expected_output,
            status=node.status
        )
        
        # Recursively copy branches
        for branch in node.alternative_branches:
            new_branch = self._copy_and_replace_node(branch, target_id, replacement)
            new_node.alternative_branches.append(new_branch)
        
        return new_node


class MCPAwarePlanner:
    """
    Planner that incorporates MCP tool registry for plan generation.
    
    Integrates with Model Context Protocol to create plans that
    leverage available tools, resources, and prompts.
    """
    
    def __init__(self, tool_registry: Optional[Dict] = None):
        self.tool_registry = tool_registry or {}
        self.tool_usage_patterns: Dict[str, Dict] = defaultdict(lambda: {
            "success_count": 0, "failure_count": 0, "avg_execution_time": 0.0
        })
    
    def register_tool(self, tool_name: str, tool_schema: Dict):
        """Register an MCP-compliant tool."""
        self.tool_registry[tool_name] = tool_schema
    
    def generate_tool_aware_plan(self, context: PlanningContext,
                                 planner: TreeOfThoughtPlanner) -> Plan:
        """Generate plan considering available MCP tools."""
        # Filter tools by task relevance
        relevant_tools = self._select_relevant_tools(
            context.task_description,
            context.available_tools
        )
        
        # Update context with relevant tools
        context.available_tools = relevant_tools
        
        # Generate plan with tool awareness
        plan = planner.generate_plan(context)
        
        # Enhance plan nodes with tool calls
        self._enhance_with_tool_calls(plan, relevant_tools)
        
        return plan
    
    def _select_relevant_tools(self, task: str, available: List[str]) -> List[str]:
        """Select tools relevant to the task."""
        task_lower = task.lower()
        relevant = []
        
        tool_keywords = {
            "web_search": ["search", "find", "research", "lookup", "information"],
            "code_gen": ["code", "implement", "program", "function", "script"],
            "analysis": ["analyze", "evaluate", "assess", "compare"],
            "file_operations": ["file", "read", "write", "load", "save"],
            "communication": ["send", "notify", "message", "email"]
        }
        
        for tool in available:
            keywords = tool_keywords.get(tool, [])
            if any(kw in task_lower for kw in keywords):
                relevant.append(tool)
        
        return relevant if relevant else available[:3]
    
    def _enhance_with_tool_calls(self, plan: Plan, tools: List[str]):
        """Enhance plan nodes with appropriate tool calls."""
        for node in plan.all_nodes.values():
            # Add tool call parameters based on node type
            if node.action_type == "subgoal" and "search" in node.description.lower():
                if "web_search" in tools:
                    node.parameters["tool"] = "web_search"
                    node.parameters["tool_params"] = {"query": node.description}
            elif node.action_type == "subgoal" and "code" in node.description.lower():
                if "code_gen" in tools:
                    node.parameters["tool"] = "code_gen"


class PlanExecutor:
    """
    Execute plans with support for parallel execution and test-time adaptation.
    """
    
    def __init__(self, planner: TreeOfThoughtPlanner,
                 adapter: TestTimeAdapter,
                 max_parallel: int = 3):
        self.planner = planner
        self.adapter = adapter
        self.max_parallel = max_parallel
        self.active_plans: Dict[str, Plan] = {}
    
    def execute_plan(self, plan: Plan, 
                     node_executor: Callable[[PlanNode], Tuple[bool, Any]],
                     on_progress: Optional[Callable[[str, str], None]] = None) -> ExecutionTrace:
        """Execute plan with support for adaptation."""
        plan.status = PlanStatus.IN_PROGRESS
        self.active_plans[plan.plan_id] = plan
        
        trace = ExecutionTrace(
            trace_id=f"trace_{int(time.time())}",
            plan_id=plan.plan_id
        )
        plan.current_trace = trace
        
        start_time = time.time()
        
        # Execute in parallel groups
        for group in plan.get_parallel_groups():
            for node in group:
                if on_progress:
                    on_progress(plan.plan_id, f"Executing: {node.description}")
                
                # Execute node
                node.status = NodeStatus.EXECUTING
                node_start = time.time()
                
                try:
                    success, result = node_executor(node)
                    node.execution_time_ms = (time.time() - node_start) * 1000
                    
                    if success:
                        node.status = NodeStatus.COMPLETED
                        node.actual_output = str(result)[:500] if result else None
                        trace.record_node_execution(node.node_id, True, result)
                    else:
                        # Handle failure - check for refinement
                        node.retry_count += 1
                        
                        if self.adapter.should_refine(node, result):
                            trace.refinement_triggers.append(node.node_id)
                            trace.record_node_execution(node.node_id, False, result, str(result))
                            
                            # Adapt plan
                            new_plan = self.adapter.adapt_plan(plan, node, str(result))
                            plan.status = PlanStatus.REFINING
                            
                            if on_progress:
                                on_progress(plan.plan_id, f"Refining plan due to failure: {result}")
                            
                            # Continue with adapted plan
                            plan = new_plan
                            self.active_plans[new_plan.plan_id] = new_plan
                            plan.status = PlanStatus.IN_PROGRESS
                            
                            # Restart execution from beginning with new plan
                            return self.execute_plan(plan, node_executor, on_progress)
                        else:
                            node.status = NodeStatus.FAILED
                            trace.record_node_execution(node.node_id, False, result, str(result))
                
                except Exception as e:
                    node.status = NodeStatus.FAILED
                    node.execution_time_ms = (time.time() - node_start) * 1000
                    trace.record_node_execution(node.node_id, False, None, str(e))
        
        # Complete execution
        trace.total_time_ms = (time.time() - start_time) * 1000
        plan.execution_traces.append(trace)
        
        # Determine final status
        if trace.success_rate >= 1.0:
            plan.status = PlanStatus.COMPLETED
        elif trace.success_rate >= 0.5:
            plan.status = PlanStatus.COMPLETED  # Partial success
            trace.lessons_learned.append("Partial success - some nodes failed but core objectives met")
        else:
            plan.status = PlanStatus.FAILED
            trace.lessons_learned.append("Execution failed - consider plan redesign")
        
        del self.active_plans[plan.plan_id]
        return trace
    
    def get_plan_statistics(self, plan: Plan) -> Dict:
        """Get execution statistics for a plan."""
        total_nodes = len(plan.all_nodes)
        completed = sum(1 for n in plan.all_nodes.values() if n.status == NodeStatus.COMPLETED)
        failed = sum(1 for n in plan.all_nodes.values() if n.status == NodeStatus.FAILED)
        replanned = sum(1 for n in plan.all_nodes.values() if n.status == NodeStatus.REPLANNED)
        
        avg_execution_time = 0.0
        if plan.execution_traces:
            total_time = sum(t.total_time_ms for t in plan.execution_traces)
            avg_execution_time = total_time / len(plan.execution_traces)
        
        return {
            "total_nodes": total_nodes,
            "completed": completed,
            "failed": failed,
            "replanned": replanned,
            "success_rate": completed / total_nodes if total_nodes > 0 else 0,
            "version": plan.version,
            "execution_count": len(plan.execution_traces),
            "avg_execution_time_ms": avg_execution_time
        }


def create_default_planner(tool_registry: Optional[Dict] = None) -> Tuple[TreeOfThoughtPlanner, TestTimeAdapter, MCPAwarePlanner, PlanExecutor]:
    """Create a fully configured planning pipeline."""
    tot_planner = TreeOfThoughtPlanner(max_branches=3, exploration_depth=3)
    adapter = TestTimeAdapter(refinement_threshold=0.7)
    mcp_planner = MCPAwarePlanner(tool_registry)
    executor = PlanExecutor(tot_planner, adapter, max_parallel=3)
    
    return tot_planner, adapter, mcp_planner, executor


# Export main classes
__all__ = [
    "PlanStatus",
    "NodeStatus", 
    "PlanningContext",
    "PlanNode",
    "Plan",
    "ExecutionTrace",
    "TreeOfThoughtPlanner",
    "TestTimeAdapter",
    "MCPAwarePlanner",
    "PlanExecutor",
    "create_default_planner"
]