"""
Integrated Agent with full Tool Registry support.
Combines ReAct pattern with unified tool management.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
import json
import time

from core.agent import BaseAgent, Thought, Action, Observation, ActionType
from core.memory import MemorySystem
from core.planner import Planner, TaskStatus
from core.reflection import Reflector
from skills import ToolRegistry, get_registry, BaseTool


@dataclass
class AgentConfig:
    """Configuration for the integrated agent."""
    name: str = "IntegratedAgent"
    max_steps: int = 10
    memory_storage_dir: str = None
    reflection_storage_path: str = None
    enable_planning: bool = True
    enable_reflection: bool = True
    verbose: bool = True


class IntegratedAgent:
    """
    Fully integrated agent with memory, planning, reflection, and tools.
    
    Features:
    - ReAct reasoning loop
    - Unified tool registry
    - Multi-type memory (working, episodic, semantic)
    - Hierarchical task planning
    - Self-reflection and improvement tracking
    """
    
    def __init__(self, config: AgentConfig = None, tool_registry: ToolRegistry = None):
        self.config = config or AgentConfig()
        self.tools = tool_registry or get_registry()
        
        # Initialize subsystems
        self.memory = MemorySystem(storage_dir=self.config.memory_storage_dir)
        self.planner = Planner()
        self.reflector = Reflector(storage_path=self.config.reflection_storage_path)
        
        # State
        self.history: List[Dict[str, Any]] = []
        self.current_task: Optional[str] = None
        self._step_count = 0
    
    def _log(self, message: str):
        """Log message if verbose mode enabled."""
        if self.config.verbose:
            print(message)
    
    def _get_available_tools_prompt(self) -> str:
        """Generate tool descriptions for system prompt."""
        tools = []
        for name in self.tools.list_tools():
            tool = self.tools.get(name)
            tools.append(f"  • {name}: {tool.schema.description}")
        return "\n".join(tools)
    
    def think(self, context: str) -> Thought:
        """
        Generate a thought based on current context.
        Uses memory and task state to inform reasoning.
        """
        # Get relevant past experiences
        similar = self.memory.recall_similar(self.current_task or context)
        
        # Get known facts
        facts = []
        for key in ["task_strategy", "common_errors"]:
            fact = self.memory.recall_fact(key)
            if fact:
                facts.append(f"{key}: {fact}")
        
        # Build reasoning context
        reasoning_parts = []
        
        # Check for errors
        if "error" in context.lower() or "failed" in context.lower():
            reasoning_parts.append("The previous action encountered issues.")
            
            # Check if we've seen this error before
            for exp in similar:
                if "error" in exp.lower():
                    reasoning_parts.append("Similar errors occurred in past tasks. Trying alternative approach.")
                    break
        
        # Check step limit
        if self._step_count >= self.config.max_steps - 1:
            reasoning_parts.append("Approaching step limit. Should provide final answer.")
        
        # Check task progress
        if self.planner.current_plan:
            next_task = self.planner.get_next_task()
            if next_task:
                reasoning_parts.append(f"Next planned step: {next_task.description}")
        
        if not reasoning_parts:
            reasoning_parts.append("Analyzing task and selecting appropriate tools.")
        
        return Thought(
            content=context[:200],
            reasoning=" ".join(reasoning_parts)
        )
    
    def decide_action(self, thought: Thought) -> Action:
        """
        Decide what action to take.
        Uses planner and tool availability.
        """
        # Check if we're done
        if self._step_count >= self.config.max_steps - 1:
            return Action(
                action_type=ActionType.ANSWER,
                thought="Providing final answer due to step limit."
            )
        
        # Check planner for next task
        if self.config.enable_planning and self.planner.current_plan:
            next_task = self.planner.get_next_task()
            if next_task and next_task.status.value == "pending":
                # Map task to tool
                task_lower = next_task.description.lower()
                
                if any(word in task_lower for word in ["search", "find", "look up"]):
                    return Action(
                        action_type=ActionType.TOOL_CALL,
                        tool_name="web_search",
                        tool_input={"query": next_task.description},
                        thought=f"Executing planned step: {next_task.description}"
                    )
                
                elif any(word in task_lower for word in ["read", "get content", "load"]):
                    # Extract potential file path
                    return Action(
                        action_type=ActionType.TOOL_CALL,
                        tool_name="file_read",
                        tool_input={"path": "/home/workspace/agi-research/README.md"},
                        thought=f"Executing planned step: {next_task.description}"
                    )
                
                elif any(word in task_lower for word in ["calculate", "compute", "math"]):
                    return Action(
                        action_type=ActionType.TOOL_CALL,
                        tool_name="calculator",
                        tool_input={"expression": "2 + 2"},
                        thought=f"Executing planned step: {next_task.description}"
                    )
        
        # Default: use first available tool if any
        available_tools = self.tools.list_tools()
        if available_tools:
            tool_name = available_tools[0]
            tool = self.tools.get(tool_name)
            
            # Build simple input from tool schema
            tool_input = {}
            for param in tool.schema.parameters:
                if param.required:
                    if param.name in ["query", "expression", "content"]:
                        tool_input[param.name] = thought.content[:50]
                    elif param.name == "path":
                        tool_input[param.name] = "."
                    else:
                        tool_input[param.name] = ""
            
            return Action(
                action_type=ActionType.TOOL_CALL,
                tool_name=tool_name,
                tool_input=tool_input,
                thought=thought.reasoning
            )
        
        # No tools available - answer directly
        return Action(
            action_type=ActionType.ANSWER,
            thought=thought.reasoning
        )
    
    def execute_action(self, action: Action) -> Observation:
        """Execute the decided action using tool registry."""
        if action.action_type == ActionType.ANSWER:
            return Observation(
                content=f"Final answer: {action.thought}",
                success=True
            )
        
        if action.action_type == ActionType.TOOL_CALL:
            if action.tool_name:
                result = self.tools.execute(action.tool_name, **(action.tool_input or {}))
                
                # Record success/failure for reflection
                if not result.success:
                    self.memory.add_to_context(
                        f"Tool error: {action.tool_name} - {result.error}",
                        metadata={"type": "error", "tool": action.tool_name}
                    )
                
                return Observation(
                    content=json.dumps(result.data) if result.success else result.error,
                    success=result.success
                )
            
            return Observation(
                content="No tool specified",
                success=False
            )
        
        return Observation(
            content="Unknown action type",
            success=False
        )
    
    def run(self, task: str, context: str = "") -> Dict[str, Any]:
        """
        Execute the full agent loop on a task.
        
        Args:
            task: The task to complete
            context: Additional context information
            
        Returns:
            Dict with results, history, and metadata
        """
        start_time = time.time()
        self.current_task = task
        self._step_count = 0
        
        self._log(f"\n{'='*60}")
        self._log(f"🤖 {self.config.name} starting task: {task}")
        self._log(f"{'='*60}\n")
        
        # Initialize plan if planning enabled
        if self.config.enable_planning:
            self.planner.decompose(task, context)
            self._log(f"📋 Plan created:\n{self.planner.get_plan_summary()}\n")
        
        # Add to working memory
        self.memory.add_to_context(f"Task: {task}")
        if context:
            self.memory.add_to_context(f"Context: {context}")
        
        # ReAct loop
        for step_num in range(self.config.max_steps):
            self._step_count = step_num + 1
            
            self._log(f"\n📍 Step {step_num + 1}/{self.config.max_steps}")
            
            # Get current context from memory
            current_context = self.memory.get_context(n=5)
            full_context = f"Task: {task}\nContext: {current_context}"
            
            # REASON
            thought = self.think(full_context)
            self._log(f"💭 Thought: {thought.reasoning}")
            
            # ACT
            action = self.decide_action(thought)
            self._log(f"🔧 Action: {action.action_type.value}")
            if action.tool_name:
                self._log(f"   Tool: {action.tool_name}")
                self._log(f"   Input: {action.tool_input}")
            
            # OBSERVE
            observation = self.execute_action(action)
            status_icon = "✅" if observation.success else "❌"
            self._log(f"{status_icon} Observation: {str(observation.content)[:150]}...")
            
            # Record step
            step_record = {
                "step": step_num + 1,
                "thought": thought.reasoning,
                "action": {
                    "type": action.action_type.value,
                    "tool": action.tool_name,
                    "input": action.tool_input
                },
                "observation": {
                    "success": observation.success,
                    "content": observation.content[:500]
                }
            }
            self.history.append(step_record)
            
            # Add to memory
            self.memory.add_to_context(
                f"Step {step_num + 1}: {action.action_type.value} - {observation.success}",
                metadata={"step": step_num + 1, "success": observation.success}
            )
            
            # Update planner
            if self.config.enable_planning and action.tool_name:
                next_task = self.planner.get_next_task()
                if next_task:
                    self.planner.update_task(
                        next_task.id,
                        TaskStatus.COMPLETED if observation.success else TaskStatus.FAILED,
                        result=observation.content
                    )
            
            # Check if done
            if action.action_type == ActionType.ANSWER:
                break
        
        # Record episode
        elapsed = time.time() - start_time
        success = self.history and self.history[-1].get("observation", {}).get("success", False)
        
        self.memory.record_episode(
            task=task,
            outcome="success" if success else "incomplete",
            lessons=f"Completed in {self._step_count} steps, {elapsed:.1f}s"
        )
        
        # Reflect if enabled
        if self.config.enable_reflection:
            from core.reflection import PerformanceMetrics
            metrics = PerformanceMetrics(
                task=task,
                success=success,
                steps_taken=self._step_count,
                time_elapsed=elapsed,
                tool_calls=sum(1 for h in self.history if h.get("action", {}).get("tool"))
            )
            reflection = self.reflector.reflect(task, metrics)
            self._log(f"\n🤔 Reflection: {reflection.lessons_learned}")
        
        # Build result
        result = {
            "task": task,
            "success": success,
            "steps_taken": self._step_count,
            "elapsed_time": elapsed,
            "history": self.history,
            "tool_stats": self.tools.get_stats()
        }
        
        self._log(f"\n{'='*60}")
        self._log(f"✅ Task complete: {success}")
        self._log(f"{'='*60}")
        
        return result
    
    def get_state(self) -> Dict[str, Any]:
        """Get current agent state for inspection."""
        return {
            "config": {
                "name": self.config.name,
                "max_steps": self.config.max_steps
            },
            "tools": self.tools.list_tools(),
            "memory": {
                "working_context": self.memory.get_context(n=5),
                "episodes": len(self.memory.episodic.episodes),
                "facts": len(self.memory.semantic.facts)
            },
            "planner": {
                "has_plan": self.planner.current_plan is not None,
                "is_complete": self.planner.is_complete() if self.planner.current_plan else True
            },
            "reflector": {
                "total_metrics": len(self.reflector.metrics),
                "patterns": self.reflector.patterns
            }
        }
    
    def reset(self):
        """Reset agent state for new task."""
        self.history = []
        self.current_task = None
        self._step_count = 0
        self.memory.clear_working_memory()
        if self.planner.current_plan:
            self.planner.current_plan = None
            self.planner.tasks = {}


if __name__ == "__main__":
    # Demo
    config = AgentConfig(
        name="DemoAgent",
        max_steps=5,
        enable_planning=True,
        enable_reflection=True,
        verbose=True
    )
    
    agent = IntegratedAgent(config)
    
    print("=== Agent State ===")
    print(json.dumps(agent.get_state(), indent=2))
    
    print("\n=== Running Task ===")
    result = agent.run(
        task="List Python files in the current directory",
        context="Testing the integrated agent with file operations"
    )
    
    print("\n=== Final Result ===")
    print(json.dumps({
        "success": result["success"],
        "steps_taken": result["steps_taken"],
        "tool_stats": result["tool_stats"]
    }, indent=2))
