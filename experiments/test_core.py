"""
Core Component Tests

Validation tests for agent core components.
Run with: python -m pytest experiments/test_core.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core import (
    BaseAgent,
    MemorySystem,
    Planner,
    Reflector,
    Task,
    TaskStatus,
    Plan
)
from skills import WebSearchSkill, CodeGenSkill, AnalysisSkill


def test_working_memory():
    """Test working memory capacity and retrieval."""
    print("\n=== Testing Working Memory ===")
    
    memory = MemorySystem(working_capacity=3)
    
    # Store context items (stored in separate dict, not limited by capacity)
    memory.store_working("key1", "value1")
    memory.store_working("key2", "value2")
    memory.store_working("key3", "value3")
    memory.store_working("key4", "value4")  # Context items accumulate
    
    # Retrieve from context
    v1 = memory.retrieve_working("key1")
    v4 = memory.retrieve_working("key4")
    
    print(f"  key1 from context: {v1}")
    print(f"  key4 from context: {v4}")
    
    # Context stores all items (not capacity-limited)
    assert v1 == "value1", "Context items should persist"
    assert v4 == "value4", "Newest context item should exist"
    
    # Test entries deque (limited capacity)
    from core.memory import MemoryEntry
    import time
    
    # Add 4 entries to capacity-3 deque
    for i in range(4):
        entry = MemoryEntry(
            id=f"entry_{i}",
            content=f"data_{i}",
            timestamp=time.time(),
            memory_type="working"
        )
        memory.working.add_entry(entry)
        time.sleep(0.01)  # Small delay for distinct timestamps
    
    recent = memory.working.get_recent(5)  # Request more than capacity
    print(f"  Entries capacity: {memory.working.capacity}")
    print(f"  Recent entries returned: {len(recent)}")
    
    assert len(recent) == 3, "Should only have 3 entries (capacity limit)"
    assert recent[0].id == "entry_1", "First should be entry_1 (entry_0 evicted)"
    assert recent[-1].id == "entry_3", "Last should be entry_3 (most recent)"
    print("  ✓ Working memory test passed")


def test_episodic_memory():
    """Test episodic memory storage and retrieval."""
    print("\n=== Testing Episodic Memory ===")
    
    memory = MemorySystem()
    
    # Store episodes
    entry1 = memory.store_episode(
        content={"action": "search", "result": "found"},
        tags=["research", "success"],
        importance=0.8
    )
    entry2 = memory.store_episode(
        content={"action": "fail", "result": "error"},
        tags=["research", "failure"],
        importance=0.9
    )
    
    # Retrieve similar
    context = {"tags": ["research"], "task": "research task"}
    episodes = memory.retrieve_episodes(context, limit=2)
    
    print(f"  Stored {len([entry1, entry2])} episodes")
    print(f"  Retrieved {len(episodes)} episodes")
    
    assert len(episodes) > 0, "Should retrieve episodes"
    print("  ✓ Episodic memory test passed")


def test_planner():
    """Test planning and task decomposition."""
    print("\n=== Testing Planner ===")
    
    planner = Planner()
    
    # Simple sequential goal
    plan = planner.create_plan("Build a web application")
    
    print(f"  Goal: {plan.goal}")
    print(f"  Strategy: {plan.strategy}")
    print(f"  Tasks: {len(plan.get_all_tasks())}")
    
    assert plan.root_task is not None
    assert len(plan.get_all_tasks()) > 0
    print("  ✓ Planner test passed")


def test_reflector():
    """Test reflection and pattern extraction."""
    print("\n=== Testing Reflector ===")
    
    reflector = Reflector()
    
    # Simulate thoughts and observations
    class MockThought:
        def __init__(self, content, type_, step):
            self.content = content
            self.type = type_
            self.step = step
    
    class MockObs:
        def __init__(self, action, result, success):
            self.action = action
            self.result = result
            self.success = success
            self.timestamp = 1234567890
    
    thoughts = [
        MockThought("Plan: step 1", "plan", 0),
        MockThought("Action: execute", "action", 1)
    ]
    observations = [
        MockObs("step1", "done", True),
        MockObs("step2", "complete", True)
    ]
    
    result = reflector.evaluate(
        goal="test goal",
        thoughts=thoughts,
        observations=observations,
        context={}
    )
    
    print(f"  Reflection complete: {result.get('complete', False)}")
    print(f"  Insights: {len(result.get('insights', []))}")
    
    assert 'insights' in result
    print("  ✓ Reflector test passed")


def test_agent_basic():
    """Test basic agent execution."""
    print("\n=== Testing Base Agent ===")
    
    skills = [
        WebSearchSkill(),
        AnalysisSkill()
    ]
    
    agent = BaseAgent(
        name="test_agent",
        skills=skills,
        max_iterations=3
    )
    
    # Run simple task
    result = agent.run("search for information about AI")
    
    print(f"  Agent: {agent.name}")
    print(f"  Success: {result.success}")
    print(f"  Iterations: {result.metadata.get('iterations', 0)}")
    print(f"  Thoughts: {len(result.thoughts)}")
    
    assert result.goal == "search for information about AI"
    assert len(result.thoughts) > 0
    print("  ✓ Agent test passed")


def test_skill_selection():
    """Test skill matching and selection."""
    print("\n=== Testing Skill Selection ===")
    
    skills = [
        WebSearchSkill(),
        CodeGenSkill(),
        AnalysisSkill()
    ]
    
    # Use specific action strings that clearly match only one skill
    test_cases = [
        ("search web for data", WebSearchSkill),  # Clearly search
        ("generate python function", CodeGenSkill),  # Clearly code
        ("perform statistical evaluation", AnalysisSkill)  # Clearly analysis, avoiding "analyze" which might match code
    ]
    
    for action, expected_type in test_cases:
        matched_skill = None
        for skill in skills:
            if skill.can_handle(action, {}):
                matched_skill = skill
                break
        
        assert matched_skill is not None, f"No skill matched for: {action}"
        assert isinstance(matched_skill, expected_type), \
            f"Expected {expected_type.__name__} but got {type(matched_skill).__name__} for: {action}"
        print(f"  ✓ '{action}' -> {expected_type.__name__}")
    
    print("  ✓ Skill selection test passed")


def run_all_tests():
    """Run all validation tests."""
    print("="*50)
    print("AGI Core Component Tests")
    print("="*50)
    
    try:
        test_working_memory()
        test_episodic_memory()
        test_planner()
        test_reflector()
        test_agent_basic()
        test_skill_selection()
        
        print("\n" + "="*50)
        print("All tests passed! ✓")
        print("="*50)
        return True
    except Exception as e:
        print(f"\n  ✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
