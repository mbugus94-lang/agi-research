"""
Base Agent Implementation

Core agent loop implementing ReAct pattern:
Reason → Act → Observe → Reflect → Repeat

References:
- vasilyevdm/ai-agent-handbook: ReAct, Plan+Execute, Reflection patterns
- NVIDIA AI-Q Blueprint: Two-tier routing (shallow/fast vs deep/complex)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
import json
import time
from datetime import datetime


class AgentState(Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    OBSERVING = "observing"
    REFLECTING = "reflecting"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class Observation:
    """Result of an action"""
    timestamp: float
    action: str
    result: Any
    success: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Thought:
    """Reasoning step"""
    step: int
    content: str
    type: str  # "plan", "action", "reflection", "decision"
    timestamp: float


@dataclass
class AgentResult:
    """Final execution result"""
    goal: str
    success: bool
    output: Any
    thoughts: List[Thought]
    observations: List[Observation]
    execution_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAgent:
    """
    Base agent implementing the ReAct (Reason, Act, Observe, Reflect) loop.
    
    Architecture inspired by:
    - NVIDIA AI-Q: Two-tier routing (simple vs complex)
    - Microsoft multi-agent: Orchestration patterns
    - Conductor production patterns: Durable execution
    """
    
    def __init__(
        self,
        name: str = "agent",
        max_iterations: int = 10,
        skills: Optional[List[Any]] = None,
        planner: Optional[Any] = None,
        memory: Optional[Any] = None,
        reflector: Optional[Any] = None
    ):
        self.name = name
        self.max_iterations = max_iterations
        self.skills = skills or []
        self.planner = planner
        self.memory = memory
        self.reflector = reflector
        
        self.state = AgentState.IDLE
        self.thoughts: List[Thought] = []
        self.observations: List[Observation] = []
        self.current_iteration = 0
        
    def think(self, context: Dict[str, Any]) -> Thought:
        """
        Reasoning step: analyze situation and decide next action.
        
        Implements two-tier routing:
        - Simple tasks: Direct action selection
        - Complex tasks: Full planning with decomposition
        """
        self.state = AgentState.PLANNING
        
        # Determine if task needs full planning or direct action
        if self._is_simple_task(context):
            content = self._select_direct_action(context)
            thought_type = "action"
        else:
            if self.planner:
                plan = self.planner.create_plan(context)
                content = f"Plan: {plan}"
            else:
                content = self._basic_reasoning(context)
            thought_type = "plan"
        
        thought = Thought(
            step=self.current_iteration,
            content=content,
            type=thought_type,
            timestamp=time.time()
        )
        self.thoughts.append(thought)
        return thought
    
    def act(self, thought: Thought, context: Dict[str, Any]) -> Observation:
        """
        Execute the planned action using available skills.
        """
        self.state = AgentState.EXECUTING
        
        # Extract action from thought
        action = self._parse_action(thought.content)
        
        # Find appropriate skill
        skill = self._select_skill(action, context)
        
        if skill:
            try:
                result = skill.execute(action, context)
                success = True
            except Exception as e:
                result = {"error": str(e)}
                success = False
        else:
            result = {"error": f"No skill found for action: {action}"}
            success = False
        
        observation = Observation(
            timestamp=time.time(),
            action=action,
            result=result,
            success=success
        )
        self.observations.append(observation)
        return observation
    
    def observe(self, observation: Observation) -> Dict[str, Any]:
        """
        Process observation and update context.
        """
        self.state = AgentState.OBSERVING
        
        # Update context with observation
        context_update = {
            "last_observation": observation.result,
            "last_action_success": observation.success,
            "step": self.current_iteration
        }
        
        # Store in memory if available
        if self.memory:
            self.memory.store_episode({
                "action": observation.action,
                "result": observation.result,
                "success": observation.success,
                "timestamp": observation.timestamp
            })
        
        return context_update
    
    def reflect(self, context: Dict[str, Any]) -> Optional[Thought]:
        """
        Reflect on progress and decide whether to continue or terminate.
        
        Returns None if task is complete, otherwise returns reflection thought.
        """
        self.state = AgentState.REFLECTING
        
        if self.reflector:
            reflection = self.reflector.evaluate(
                goal=context.get("goal"),
                thoughts=self.thoughts,
                observations=self.observations,
                context=context
            )
            
            if reflection.get("complete", False):
                return None
            
            thought = Thought(
                step=self.current_iteration,
                content=reflection.get("insight", "Continue execution"),
                type="reflection",
                timestamp=time.time()
            )
            self.thoughts.append(thought)
            return thought
        
        # Basic reflection: check if goal achieved or max iterations
        if self._is_goal_achieved(context) or self.current_iteration >= self.max_iterations:
            return None
        
        thought = Thought(
            step=self.current_iteration,
            content="Continue to next step",
            type="reflection",
            timestamp=time.time()
        )
        self.thoughts.append(thought)
        return thought
    
    def run(self, goal: str, initial_context: Optional[Dict[str, Any]] = None) -> AgentResult:
        """
        Execute the full ReAct loop.
        
        Pattern: ReAct (Reason, Act, Observe, Reflect)
        Reference: Yao et al. "ReAct: Synergizing Reasoning and Acting in Language Models"
        """
        start_time = time.time()
        
        context = initial_context or {}
        context["goal"] = goal
        context["agent_name"] = self.name
        
        self.state = AgentState.EXECUTING
        
        while self.current_iteration < self.max_iterations:
            # 1. REASON: Think about next action
            thought = self.think(context)
            
            # 2. ACT: Execute the action
            observation = self.act(thought, context)
            
            # 3. OBSERVE: Process result
            context_update = self.observe(observation)
            context.update(context_update)
            
            # 4. REFLECT: Evaluate progress
            reflection = self.reflect(context)
            if reflection is None:
                break
            
            self.current_iteration += 1
        
        execution_time = time.time() - start_time
        
        # Determine success
        success = any(obs.success for obs in self.observations)
        
        # Compile output
        output = self._compile_output()
        
        self.state = AgentState.COMPLETE if success else AgentState.ERROR
        
        return AgentResult(
            goal=goal,
            success=success,
            output=output,
            thoughts=self.thoughts,
            observations=self.observations,
            execution_time=execution_time,
            metadata={
                "iterations": self.current_iteration,
                "agent_name": self.name,
                "final_state": self.state.value
            }
        )
    
    def _is_simple_task(self, context: Dict[str, Any]) -> bool:
        """
        Two-tier routing: determine if task can be handled without full planning.
        """
        goal = context.get("goal", "")
        # Simple heuristics for quick classification
        simple_indicators = ["quick", "simple", "lookup", "search", "check"]
        complex_indicators = ["complex", "multi-step", "analyze", "research", "build"]
        
        goal_lower = goal.lower()
        simple_score = sum(1 for s in simple_indicators if s in goal_lower)
        complex_score = sum(1 for c in complex_indicators if c in goal_lower)
        
        return simple_score > complex_score
    
    def _select_direct_action(self, context: Dict[str, Any]) -> str:
        """Select immediate action for simple tasks."""
        goal = context.get("goal", "")
        # Direct mapping for common simple tasks
        if "search" in goal.lower():
            return f"web_search: {goal}"
        elif "calculate" in goal.lower() or "compute" in goal.lower():
            return f"calculate: {goal}"
        else:
            return f"process: {goal}"
    
    def _basic_reasoning(self, context: Dict[str, Any]) -> str:
        """Basic reasoning when no planner is available."""
        return f"Analyze goal and determine approach: {context.get('goal')}"
    
    def _parse_action(self, thought_content: str) -> str:
        """Extract action from thought content."""
        # Simple parsing - in production use structured output
        if "Plan:" in thought_content:
            return thought_content.split("Plan:")[1].strip()
        elif ":" in thought_content:
            return thought_content.split(":", 1)[1].strip()
        return thought_content
    
    def _select_skill(self, action: str, context: Dict[str, Any]) -> Optional[Any]:
        """Select appropriate skill for action."""
        for skill in self.skills:
            if skill.can_handle(action, context):
                return skill
        return None
    
    def _is_goal_achieved(self, context: Dict[str, Any]) -> bool:
        """Check if goal has been achieved."""
        # Check last observation for success indicators
        if self.observations:
            last = self.observations[-1]
            if last.success and "complete" in str(last.result).lower():
                return True
        return False
    
    def _compile_output(self) -> Dict[str, Any]:
        """Compile final output from execution."""
        return {
            "thoughts": [
                {"step": t.step, "type": t.type, "content": t.content}
                for t in self.thoughts
            ],
            "observations": [
                {"action": o.action, "success": o.success, "result": o.result}
                for o in self.observations
            ],
            "final_observation": self.observations[-1].result if self.observations else None
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize agent state."""
        return {
            "name": self.name,
            "state": self.state.value,
            "iterations": self.current_iteration,
            "thought_count": len(self.thoughts),
            "observation_count": len(self.observations)
        }
