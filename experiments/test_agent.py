"""
Tests for the base agent with ReAct pattern.
"""

import sys
sys.path.insert(0, '/home/workspace/agi-research')

from core.agent import BaseAgent, Tool, ActionType, Action
from skills.web_search import WebSearchSkill
import tempfile
import json


def test_basic_agent_creation():
    """Test that agent can be created."""
    agent = BaseAgent(name="TestAgent")
    assert agent.name == "TestAgent"
    assert len(agent.history) == 0
    print("✅ Agent creation test passed")


def test_thought_generation():
    """Test thought generation."""
    agent = BaseAgent(name="TestAgent")
    thought = agent.think("Test context")
    assert thought.content is not None
    assert thought.reasoning is not None
    print("✅ Thought generation test passed")


def test_action_decision():
    """Test action decision making."""
    agent = BaseAgent(name="TestAgent")
    thought = agent.think("Test context")
    action = agent.decide_action(thought)
    assert action.action_type in [ActionType.TOOL_CALL, ActionType.ANSWER]
    print("✅ Action decision test passed")


def test_tool_execution():
    """Test tool execution."""
    def mock_tool(query: str) -> str:
        return f"Result for: {query}"
    
    tool = Tool(
        name="mock_search",
        description="Mock search tool",
        func=mock_tool,
        schema={}
    )
    
    agent = BaseAgent(name="TestAgent", tools=[tool])
    
    thought = agent.think("Search for something")
    action = Action(
        action_type=ActionType.TOOL_CALL,
        tool_name="mock_search",
        tool_input={"query": "test"}
    )
    
    obs = agent.execute_action(action)
    assert obs.success
    assert "Result for:" in obs.content
    print("✅ Tool execution test passed")


def test_react_loop():
    """Test full ReAct loop execution."""
    def multiply(x: int, y: int) -> int:
        return x * y
    
    tool = Tool(
        name="calculator",
        description="Calculate product",
        func=lambda x, y: str(multiply(x, y)),
        schema={}
    )
    
    agent = BaseAgent(name="MathAgent", tools=[tool], max_steps=5)
    result = agent.run("Calculate 6 times 7")
    
    assert result["success"] is not None
    assert result["steps_taken"] > 0
    assert result["answer"] is not None
    print(f"✅ ReAct loop test passed (steps: {result['steps_taken']})")


def test_agent_reset():
    """Test agent history reset."""
    agent = BaseAgent(name="TestAgent")
    agent.run("Simple task")
    assert len(agent.history) > 0
    
    agent.reset()
    assert len(agent.history) == 0
    print("✅ Agent reset test passed")


def test_error_handling():
    """Test error handling in tool execution."""
    def failing_tool(x: int) -> str:
        raise ValueError("Intentional error")
    
    tool = Tool(
        name="failing_tool",
        description="Always fails",
        func=failing_tool,
        schema={}
    )
    
    agent = BaseAgent(name="ErrorAgent", tools=[tool])
    
    action = Action(
        action_type=ActionType.TOOL_CALL,
        tool_name="failing_tool",
        tool_input={"x": 1}
    )
    
    obs = agent.execute_action(action)
    assert not obs.success
    assert "Error" in obs.content
    print("✅ Error handling test passed")


def run_all_tests():
    """Run all agent tests."""
    print("\n" + "="*60)
    print("🧪 Testing Base Agent (ReAct Pattern)")
    print("="*60 + "\n")
    
    tests = [
        test_basic_agent_creation,
        test_thought_generation,
        test_action_decision,
        test_tool_execution,
        test_react_loop,
        test_agent_reset,
        test_error_handling,
    ]
    
    failed = []
    for test in tests:
        try:
            test()
        except AssertionError as e:
            failed.append((test.__name__, str(e)))
            print(f"❌ {test.__name__} failed: {e}")
        except Exception as e:
            failed.append((test.__name__, str(e)))
            print(f"❌ {test.__name__} error: {e}")
    
    print("\n" + "="*60)
    if failed:
        print(f"⚠️  {len(failed)}/{len(tests)} tests failed")
        return 1
    else:
        print(f"✅ All {len(tests)} tests passed")
        return 0


if __name__ == "__main__":
    sys.exit(run_all_tests())
