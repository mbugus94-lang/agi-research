"""
Planning Module

Implements planning with:
- EXPLORE / VERIFY / PLAN framework
- Task DAG construction
- Resource-harmonic average efficiency (RHAE) considerations
"""

import json
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum


class PlanStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class PlanNode:
    """A node in the plan DAG."""
    id: str
    action: str
    tool: str
    params: Dict[str, Any]
    dependencies: List[str] = field(default_factory=list)
    expected_outcome: str = ""
    status: PlanStatus = PlanStatus.PENDING
    result: Any = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class ExecutionPlan:
    """A complete execution plan."""
    task: str
    nodes: Dict[str, PlanNode]
    entry_points: List[str]  # Nodes with no dependencies
    parallel_groups: List[List[str]]  # Groups that can execute in parallel


class Planner:
    """
    Planning engine with EXPLORE-before-PLAN pattern.
    
    Based on AERA (Adaptive Epistemic Reasoning Agent) framework:
    - Speed-depth trade-off consideration
    - Resource-harmonic efficiency
    - Task DAG for parallel execution
    """
    
    def __init__(self, max_parallel: int = 4, min_confidence: float = 0.6):
        self.max_parallel = max_parallel
        self.min_confidence = min_confidence
    
    async def create_plan(
        self,
        task: str,
        exploration: Dict,
        available_tools: Dict[str, Any]
    ) -> ExecutionPlan:
        """
        Create an execution plan from exploration results.
        
        Implements EXPLORE-before-PLAN pattern:
        1. Analyze task decomposition
        2. Identify dependencies
        3. Group parallelizable tasks
        4. Validate plan completeness
        """
        decomposition = exploration.get("decomposition", [])
        
        # Create nodes from decomposition
        nodes = {}
        for i, step in enumerate(decomposition):
            node_id = f"step_{i}"
            
            # Select appropriate tool
            tool = self._select_tool(step, available_tools)
            
            # Identify dependencies (simplified - based on order)
            dependencies = []
            if i > 0:
                dependencies = [f"step_{i-1}"]
            
            nodes[node_id] = PlanNode(
                id=node_id,
                action=step,
                tool=tool,
                params={"task": step},
                dependencies=dependencies,
                expected_outcome=f"Completed: {step}"
            )
        
        # Build parallel execution groups
        entry_points = [n_id for n_id, n in nodes.items() if not n.dependencies]
        parallel_groups = self._build_parallel_groups(nodes)
        
        plan = ExecutionPlan(
            task=task,
            nodes=nodes,
            entry_points=entry_points,
            parallel_groups=parallel_groups
        )
        
        return plan
    
    def _select_tool(self, step: str, available_tools: Dict) -> str:
        """Select the most appropriate tool for a step."""
        step_lower = step.lower()
        
        # Simple heuristic matching
        if "search" in step_lower or "find" in step_lower:
            return "web_search" if "web_search" in available_tools else "llm_generate"
        elif "code" in step_lower or "write" in step_lower:
            return "code_generate" if "code_generate" in available_tools else "llm_generate"
        elif "read" in step_lower or "file" in step_lower:
            return "file_read" if "file_read" in available_tools else "llm_generate"
        
        # Default to LLM generation
        return "llm_generate" if "llm_generate" in available_tools else list(available_tools.keys())[0] if available_tools else "unknown"
    
    def _build_parallel_groups(self, nodes: Dict[str, PlanNode]) -> List[List[str]]:
        """
        Build groups of nodes that can execute in parallel.
        Uses topological sorting approach.
        """
        remaining = set(nodes.keys())
        completed = set()
        groups = []
        
        while remaining:
            # Find nodes with all dependencies satisfied
            executable = []
            for n_id in remaining:
                node = nodes[n_id]
                if all(dep in completed for dep in node.dependencies):
                    executable.append(n_id)
            
            if not executable:
                # Circular dependency or error
                break
            
            # Limit parallel group size
            group = executable[:self.max_parallel]
            groups.append(group)
            
            completed.update(group)
            remaining.difference_update(group)
        
        return groups
    
    async def optimize_plan(
        self,
        plan: ExecutionPlan,
        feedback: List[Dict]
    ) -> ExecutionPlan:
        """
        Optimize plan based on execution feedback.
        Implements RHAE (Resource-Harmonic Average Efficiency) principles.
        """
        # Analyze which nodes failed and why
        for node_id, node in plan.nodes.items():
            node_feedback = [f for f in feedback if f.get("node_id") == node_id]
            
            if node_feedback:
                avg_time = sum(f.get("execution_time_ms", 0) for f in node_feedback) / len(node_feedback)
                success_rate = sum(1 for f in node_feedback if f.get("success")) / len(node_feedback)
                
                # Adjust retry count based on success rate
                if success_rate < 0.5:
                    node.max_retries += 1
                elif success_rate > 0.9 and avg_time < 1000:
                    # Fast and reliable - can be parallelized more
                    pass
        
        return plan
    
    def estimate_efficiency(self, plan: ExecutionPlan) -> Dict:
        """
        Estimate plan efficiency using RHAE-like metrics.
        """
        total_nodes = len(plan.nodes)
        parallel_groups = len(plan.parallel_groups)
        
        # Simplified metrics
        action_efficiency = total_nodes / parallel_groups if parallel_groups > 0 else total_nodes
        
        # Information gain estimation (based on expected outcomes)
        expected_outcomes = sum(
            1 for n in plan.nodes.values() if n.expected_outcome
        )
        
        return {
            "total_nodes": total_nodes,
            "parallel_groups": parallel_groups,
            "action_efficiency": action_efficiency,
            "expected_outcomes": expected_outcomes,
            "estimated_completion_steps": parallel_groups
        }
    
    def get_ready_nodes(self, plan: ExecutionPlan) -> List[PlanNode]:
        """Get nodes ready for execution (dependencies satisfied)."""
        ready = []
        
        for node_id, node in plan.nodes.items():
            if node.status == PlanStatus.PENDING:
                # Check if all dependencies are completed
                deps_satisfied = all(
                    plan.nodes.get(dep, PlanNode(id=dep, action="", tool="")).status == PlanStatus.COMPLETED
                    for dep in node.dependencies
                )
                if deps_satisfied:
                    ready.append(node)
        
        return ready
