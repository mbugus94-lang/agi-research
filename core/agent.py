"""
Base Agent Implementation

Architecture based on System-1 (LLM) + System-2 (Coordination) pattern.
Implements EXPLORE → VERIFY → PLAN → EXECUTE → REFLECT cycle.
"""

import json
import asyncio
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class AgentState(Enum):
    IDLE = "idle"
    EXPLORING = "exploring"
    VERIFYING = "verifying"
    PLANNING = "planning"
    EXECUTING = "executing"
    REFLECTING = "reflecting"
    ERROR = "error"


@dataclass
class Thought:
    """A single thought/reasoning step."""
    content: str
    step_type: str  # explore, verify, plan, execute, reflect
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 0.5


@dataclass
class Action:
    """An action to be executed."""
    tool: str
    params: Dict[str, Any]
    expected_outcome: str
    requires_approval: bool = False


@dataclass
class ExecutionResult:
    """Result of executing an action."""
    success: bool
    output: Any
    error: Optional[str] = None
    execution_time_ms: int = 0


class BaseAgent:
    """
    Base agent with System-2 coordination layer.
    
    Key features:
    - EXPLORE/VERIFY/PLAN/EXECUTE/REFLECT cycle
    - MCP-style tool integration
    - Hierarchical memory integration
    - Self-correction capabilities
    """
    
    def __init__(
        self,
        name: str = "base_agent",
        llm_client = None,  # External LLM client
        memory_manager = None,
        planner = None,
        reflection_engine = None,
        max_iterations: int = 10
    ):
        self.name = name
        self.state = AgentState.IDLE
        self.llm_client = llm_client
        self.memory = memory_manager
        self.planner = planner
        self.reflection = reflection_engine
        self.max_iterations = max_iterations
        
        # Tools registry (MCP-style)
        self.tools: Dict[str, Callable] = {}
        
        # Reasoning trace
        self.thoughts: List[Thought] = []
        
        # Sub-agents for delegation
        self.sub_agents: Dict[str, 'BaseAgent'] = {}
    
    def register_tool(self, name: str, func: Callable, schema: Dict = None):
        """Register a tool following MCP protocol."""
        self.tools[name] = {
            "func": func,
            "schema": schema or {}
        }
    
    def register_sub_agent(self, name: str, agent: 'BaseAgent'):
        """Register a sub-agent for delegation."""
        self.sub_agents[name] = agent
    
    async def run(self, task: str, context: Dict = None) -> Dict:
        """
        Main agent loop: EXPLORE → VERIFY → PLAN → EXECUTE → REFLECT
        """
        self.state = AgentState.EXPLORING
        self.thoughts = []
        
        iteration = 0
        result = None
        
        while iteration < self.max_iterations:
            iteration += 1
            
            # EXPLORE: Gather information and understand the task
            exploration = await self._explore(task, context)
            self._add_thought(exploration, "explore")
            
            # VERIFY: Validate understanding and check assumptions
            verification = await self._verify(exploration)
            self._add_thought(verification, "verify")
            
            if not verification.get("valid", True):
                # Need more exploration
                context = self._update_context(context, verification)
                continue
            
            # PLAN: Create action sequence
            self.state = AgentState.PLANNING
            plan = await self._plan(task, exploration, verification)
            self._add_thought(str(plan), "plan")
            
            # EXECUTE: Run the plan
            self.state = AgentState.EXECUTING
            execution_results = await self._execute_plan(plan)
            
            # REFLECT: Evaluate and potentially iterate
            self.state = AgentState.REFLECTING
            reflection = await self._reflect(execution_results, task)
            self._add_thought(str(reflection), "reflect")
            
            if reflection.get("complete", False):
                result = {
                    "success": True,
                    "output": execution_results,
                    "reflection": reflection,
                    "thoughts": self.thoughts,
                    "iterations": iteration
                }
                break
            
            # Update context for next iteration
            context = self._update_context(context, reflection)
        
        if result is None:
            result = {
                "success": False,
                "error": "Max iterations reached",
                "thoughts": self.thoughts,
                "iterations": iteration
            }
        
        self.state = AgentState.IDLE
        return result
    
    async def _explore(self, task: str, context: Dict = None) -> Dict:
        """
        EXPLORE phase: Gather information about the task.
        Uses LLM to break down and understand requirements.
        """
        prompt = f"""Explore this task to understand what needs to be done.

Task: {task}
Context: {json.dumps(context or {}, indent=2)}

Available tools: {list(self.tools.keys())}

Provide a structured exploration including:
1. Task decomposition - what are the sub-tasks?
2. Information gaps - what do we need to know?
3. Initial hypotheses - what approaches might work?
4. Confidence level (0-1)

Respond as JSON with keys: decomposition, gaps, hypotheses, confidence"""
        
        # Mock LLM call - replace with actual implementation
        return {
            "decomposition": ["analyze task", "gather info", "execute"],
            "gaps": [],
            "hypotheses": ["standard approach should work"],
            "confidence": 0.7
        }
    
    async def _verify(self, exploration: Dict) -> Dict:
        """
        VERIFY phase: Check exploration validity.
        Implements RCA (Recursive Causal Audit) pattern.
        """
        # Check if we have enough information
        gaps = exploration.get("gaps", [])
        confidence = exploration.get("confidence", 0)
        
        valid = len(gaps) == 0 and confidence > 0.6
        
        return {
            "valid": valid,
            "gaps": gaps,
            "confidence": confidence,
            "reason": "sufficient information" if valid else "need more exploration"
        }
    
    async def _plan(self, task: str, exploration: Dict, verification: Dict) -> List[Action]:
        """
        PLAN phase: Create action sequence.
        Coordinates with planner module if available.
        """
        if self.planner:
            return await self.planner.create_plan(task, exploration, self.tools)
        
        # Default simple planning
        decomposition = exploration.get("decomposition", [])
        actions = []
        
        for step in decomposition:
            actions.append(Action(
                tool="llm_generate",
                params={"prompt": step},
                expected_outcome=f"Complete: {step}"
            ))
        
        return actions
    
    async def _execute_plan(self, plan) -> List[ExecutionResult]:
        """Execute a plan of actions."""
        results = []
        
        # Handle ExecutionPlan from Planner
        if hasattr(plan, 'parallel_groups'):
            # Execute by parallel groups
            for group in plan.parallel_groups:
                # Execute all nodes in group concurrently
                group_results = await asyncio.gather(*[
                    self._execute_action(plan.nodes[node_id])
                    for node_id in group
                    if node_id in plan.nodes
                ])
                results.extend(group_results)
                
                # Update node statuses
                for i, node_id in enumerate(group):
                    if node_id in plan.nodes:
                        plan.nodes[node_id].status = plan.nodes[node_id].status.COMPLETED if group_results[i].success else plan.nodes[node_id].status.FAILED
                        if self.memory:
                            await self.memory.store_action(plan.nodes[node_id], group_results[i])
        else:
            # Handle list of Action objects (legacy or simple plans)
            for action in plan:
                result = await self._execute_action(action)
                results.append(result)
                
                # Store in memory if available
                if self.memory:
                    await self.memory.store_action(action, result)
        
        return results
    
    async def _execute_action(self, node) -> ExecutionResult:
        """Execute a single action with error handling."""
        import time
        start = time.time()
        
        # Handle both Action objects and PlanNode objects
        if hasattr(node, 'tool'):
            tool_name = node.tool
            params = node.params if hasattr(node, 'params') else {}
        else:
            tool_name = node
            params = {}
        
        tool_info = self.tools.get(tool_name)
        if not tool_info:
            return ExecutionResult(
                success=False,
                output=None,
                error=f"Tool not found: {tool_name}",
                execution_time_ms=int((time.time() - start) * 1000)
            )
        
        try:
            func = tool_info["func"]
            if asyncio.iscoroutinefunction(func):
                output = await func(**params)
            else:
                output = func(**params)
            
            return ExecutionResult(
                success=True,
                output=output,
                execution_time_ms=int((time.time() - start) * 1000)
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output=None,
                error=str(e),
                execution_time_ms=int((time.time() - start) * 1000)
            )
    
    async def _reflect(self, results: List[ExecutionResult], original_task: str) -> Dict:
        """
        REFLECT phase: Evaluate execution and determine next steps.
        Implements reactive self-correction.
        """
        all_success = all(r.success for r in results)
        any_errors = any(r.error for r in results)
        
        if self.reflection:
            return await self.reflection.evaluate(results, original_task)
        
        # Default reflection
        if all_success:
            return {
                "complete": True,
                "success": True,
                "summary": "All actions completed successfully",
                "improvements": []
            }
        
        # Reactive self-correction
        errors = [r.error for r in results if r.error]
        return {
            "complete": False,
            "success": False,
            "errors": errors,
            "retry_suggested": True,
            "improvements": ["retry failed actions", "consider alternative approach"]
        }
    
    def _add_thought(self, content: Any, step_type: str):
        """Add a thought to the reasoning trace."""
        if isinstance(content, dict):
            content = json.dumps(content, indent=2)
        self.thoughts.append(Thought(
            content=str(content),
            step_type=step_type
        ))
    
    def _update_context(self, context: Dict, new_info: Dict) -> Dict:
        """Update context with new information."""
        if context is None:
            context = {}
        context.update(new_info)
        return context
    
    def get_trace(self) -> List[Dict]:
        """Get the full reasoning trace."""
        return [
            {
                "content": t.content,
                "type": t.step_type,
                "timestamp": t.timestamp.isoformat()
            }
            for t in self.thoughts
        ]
