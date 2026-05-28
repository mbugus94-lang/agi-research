"""
Basic Agent Test Suite

Validates core agent functionality:
- Agent loop execution
- Tool registration and execution
- Memory integration
- Reflection cycle
"""

import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent import BaseAgent, AgentState
from core.memory import MemoryManager
from core.planner import Planner
from core.reflection import ReflectionEngine


async def test_basic_agent():
    """Test basic agent functionality."""
    print("=" * 60)
    print("TEST: Basic Agent Execution")
    print("=" * 60)
    
    # Create components
    memory = MemoryManager()
    planner = Planner()
    reflection = ReflectionEngine()
    
    # Create agent
    agent = BaseAgent(
        name="test_agent",
        memory_manager=memory,
        planner=planner,
        reflection_engine=reflection
    )
    
    # Register a simple tool
    async def echo_tool(message: str):
        return f"Echo: {message}"
    
    agent.register_tool("echo", echo_tool, {
        "name": "echo",
        "description": "Echo back a message"
    })
    
    # Test state transitions
    print(f"Initial state: {agent.state.value}")
    assert agent.state == AgentState.IDLE
    
    # Run agent with simple task
    result = await agent.run("Test task: echo hello")
    
    print(f"Final state: {agent.state.value}")
    print(f"Iterations: {result.get('iterations', 0)}")
    print(f"Thoughts recorded: {len(result.get('thoughts', []))}")
    
    assert agent.state == AgentState.IDLE
    assert "iterations" in result
    
    print("✓ Basic agent test passed")
    return True


async def test_memory_integration():
    """Test memory system integration."""
    print("\n" + "=" * 60)
    print("TEST: Memory Integration")
    print("=" * 60)
    
    memory = MemoryManager()
    
    # Store test memories
    id1 = memory.store(
        content="Test memory 1",
        memory_type="episodic",
        tags=["test"],
        importance=0.8
    )
    
    id2 = memory.store(
        content="Test memory 2",
        memory_type="semantic",
        tags=["test", "knowledge"],
        importance=0.6
    )
    
    print(f"Stored memory 1: {id1}")
    print(f"Stored memory 2: {id2}")
    
    # Retrieve
    results = memory.retrieve(tags=["test"], limit=10)
    print(f"Retrieved {len(results)} memories with 'test' tag")
    
    assert len(results) >= 2
    
    # Retrieve relevant
    relevant = memory.retrieve_relevant("test memory", limit=5)
    print(f"Found {len(relevant)} relevant memories")
    
    assert len(relevant) > 0
    
    print("✓ Memory integration test passed")
    return True


async def test_planner():
    """Test planner functionality."""
    print("\n" + "=" * 60)
    print("TEST: Planner")
    print("=" * 60)
    
    planner = Planner(max_parallel=2)
    
    exploration = {
        "decomposition": [
            "analyze requirements",
            "design solution",
            "implement code",
            "test results"
        ],
        "confidence": 0.8
    }
    
    tools = {
        "llm_generate": {},
        "code_generate": {},
        "file_read": {}
    }
    
    plan = await planner.create_plan(
        task="Build a web scraper",
        exploration=exploration,
        available_tools=tools
    )
    
    print(f"Plan created with {len(plan.nodes)} nodes")
    print(f"Entry points: {plan.entry_points}")
    print(f"Parallel groups: {len(plan.parallel_groups)}")
    
    assert len(plan.nodes) == 4
    assert len(plan.entry_points) == 1
    
    efficiency = planner.estimate_efficiency(plan)
    print(f"Estimated efficiency: {efficiency}")
    
    print("✓ Planner test passed")
    return True


async def test_reflection():
    """Test reflection engine."""
    print("\n" + "=" * 60)
    print("TEST: Reflection Engine")
    print("=" * 60)
    
    from core.agent import ExecutionResult
    
    reflection = ReflectionEngine()
    
    # Create mock results
    results = [
        ExecutionResult(success=True, output="Result 1", execution_time_ms=100),
        ExecutionResult(success=True, output="Result 2", execution_time_ms=200),
        ExecutionResult(success=False, output=None, error="Timeout", execution_time_ms=5000)
    ]
    
    eval_result = await reflection.evaluate(
        execution_results=results,
        original_task="Test task"
    )
    
    print(f"Complete: {eval_result['complete']}")
    print(f"Success: {eval_result['success']}")
    print(f"Summary: {eval_result['summary']}")
    print(f"Confidence: {eval_result['confidence']}")
    print(f"Improvements: {eval_result['improvements']}")
    
    assert not eval_result['complete']  # Not all successful
    assert not eval_result['success']
    assert len(eval_result['improvements']) > 0
    
    # Test trace verification
    thoughts = [
        {"type": "explore", "content": "Explored"},
        {"type": "verify", "content": "Verified"},
        {"type": "plan", "content": "Planned"},
        {"type": "reflect", "content": "Reflected"}
    ]
    
    verification = reflection.verify_trace(thoughts, "output")
    print(f"Trace verification: {verification}")
    
    assert verification['valid']
    
    print("✓ Reflection test passed")
    return True


async def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("AGI AGENT TEST SUITE")
    print("=" * 60)
    
    tests = [
        test_basic_agent,
        test_memory_integration,
        test_planner,
        test_reflection
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            await test()
            passed += 1
        except Exception as e:
            print(f"✗ Test failed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
