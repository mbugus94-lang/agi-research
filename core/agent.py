"""
Base Agent implementing the ReAct (Reason + Act) pattern.
Based on: Yao et al. "ReAct: Synergizing Reasoning and Acting in Language Models"
"""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import time


class ActionType(Enum):
    THINK = "think"
    TOOL_CALL = "tool_call"
    ANSWER = "answer"


@dataclass
class Thought:
    content: str
    reasoning: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class Action:
    action_type: ActionType
    tool_name: Optional[str] = None
    tool_input: Optional[Dict] = None
    thought: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class Observation:
    content: str
    success: bool = True
    timestamp: float = field(default_factory=time.time)


@dataclass
class Step:
    thought: Thought
    action: Action
    observation: Observation


class Tool:
    """A tool that the agent can use."""
    
    def __init__(self, name: str, description: str, func: Callable, schema: Dict):
        self.name = name
        self.description = description
        self.func = func
        self.schema = schema
    
    def execute(self, **kwargs) -> Observation:
        try:
            result = self.func(**kwargs)
            return Observation(content=str(result), success=True)
        except Exception as e:
            return Observation(content=f"Error: {str(e)}", success=False)


class BaseAgent:
    """
    ReAct-based agent that reasons and acts in a loop.
    
    The ReAct pattern:
    1. REASON: Think about what to do
    2. ACT: Take an action (tool call or answer)
    3. OBSERVE: Get result from action
    4. REFLECT: Update understanding
    5. Repeat until complete
    """
    
    def __init__(
        self,
        name: str = "Agent",
        max_steps: int = 10,
        tools: Optional[List[Tool]] = None
    ):
        self.name = name
        self.max_steps = max_steps
        self.tools: Dict[str, Tool] = {t.name: t for t in (tools or [])}
        self.history: List[Step] = []
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        tool_descriptions = "\n".join([
            f"- {name}: {tool.description}"
            for name, tool in self.tools.items()
        ])
        
        return f"""You are {self.name}, an AI agent that solves problems using the ReAct pattern.

Available tools:
{tool_descriptions}

Follow this format for each step:
THOUGHT: Your reasoning about what to do next
ACTION: Either "tool_call" with tool name and input, or "answer" with final response

Be concise and strategic in your reasoning."""
    
    def think(self, context: str) -> Thought:
        """Generate a thought based on current context."""
        # For now, simple rule-based thinking
        # In production, this would call an LLM
        
        lines = context.split("\n")
        last_observation = lines[-1] if lines else ""
        
        # Simple heuristics for demo
        if "error" in last_observation.lower():
            reasoning = "The previous action failed. I need to try a different approach."
        elif len(self.history) >= self.max_steps - 1:
            reasoning = "I'm near the step limit. I should provide a final answer."
        elif not self.tools:
            reasoning = "No tools available. I'll answer directly based on context."
        else:
            reasoning = "I should analyze the task and use appropriate tools."
        
        return Thought(
            content=f"Analyzing: {context[:100]}...",
            reasoning=reasoning
        )
    
    def decide_action(self, thought: Thought) -> Action:
        """Decide what action to take based on thought."""
        # Simple rule-based decision
        if len(self.history) >= self.max_steps - 1:
            return Action(
                action_type=ActionType.ANSWER,
                thought=thought.reasoning
            )
        
        # For demo: if we have a tool, use the first one
        if self.tools:
            first_tool = list(self.tools.keys())[0]
            return Action(
                action_type=ActionType.TOOL_CALL,
                tool_name=first_tool,
                tool_input={"query": thought.content},
                thought=thought.reasoning
            )
        
        return Action(
            action_type=ActionType.ANSWER,
            thought=thought.reasoning
        )
    
    def execute_action(self, action: Action) -> Observation:
        """Execute the decided action."""
        if action.action_type == ActionType.ANSWER:
            return Observation(
                content=f"Final answer: {action.thought}",
                success=True
            )
        
        if action.action_type == ActionType.TOOL_CALL:
            if action.tool_name and action.tool_name in self.tools:
                tool = self.tools[action.tool_name]
                return tool.execute(**(action.tool_input or {}))
            return Observation(
                content=f"Tool '{action.tool_name}' not found",
                success=False
            )
        
        return Observation(
            content="No action taken",
            success=False
        )
    
    def run(self, task: str) -> Dict[str, Any]:
        """
        Run the ReAct loop to complete a task.
        
        Args:
            task: The task to complete
            
        Returns:
            Dict with final answer, steps taken, and success status
        """
        print(f"\n{'='*50}")
        print(f"🤖 {self.name} starting task: {task}")
        print(f"{'='*50}\n")
        
        context = f"Task: {task}\n"
        
        for step_num in range(self.max_steps):
            print(f"\n📍 Step {step_num + 1}/{self.max_steps}")
            
            # REASON
            thought = self.think(context)
            print(f"💭 Thought: {thought.reasoning}")
            
            # ACT
            action = self.decide_action(thought)
            print(f"🔧 Action: {action.action_type.value}")
            if action.tool_name:
                print(f"   Tool: {action.tool_name}")
            
            # OBSERVE
            observation = self.execute_action(action)
            print(f"👁️  Observation: {observation.content[:100]}...")
            
            # Record step
            step = Step(thought=thought, action=action, observation=observation)
            self.history.append(step)
            
            # Update context
            context += f"\nStep {step_num + 1}: {thought.reasoning}\n"
            context += f"Action: {action.action_type.value}\n"
            context += f"Result: {observation.content}\n"
            
            # Check if done
            if action.action_type == ActionType.ANSWER:
                print(f"\n✅ Task completed!")
                return {
                    "success": observation.success,
                    "answer": observation.content,
                    "steps_taken": step_num + 1,
                    "history": self.history
                }
        
        print(f"\n⚠️ Max steps reached")
        return {
            "success": False,
            "answer": "Max steps reached without completion",
            "steps_taken": len(self.history),
            "history": self.history
        }
    
    def reset(self):
        """Clear history for a new task."""
        self.history = []


def example_search_tool(query: str) -> str:
    """Example tool that simulates a search."""
    return f"Search results for '{query}': [simulated result]"


def example_calculator_tool(expression: str) -> str:
    """Example tool that calculates."""
    try:
        result = eval(expression)
        return str(result)
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    # Demo usage
    tools = [
        Tool("search", "Search for information", example_search_tool, {}),
        Tool("calculator", "Calculate expressions", example_calculator_tool, {})
    ]
    
    agent = BaseAgent(name="DemoAgent", tools=tools, max_steps=5)
    result = agent.run("What is 2 + 2?")
    
    print(f"\n📊 Result:")
    print(json.dumps({
        "success": result["success"],
        "answer": result["answer"],
        "steps_taken": result["steps_taken"]
    }, indent=2))
