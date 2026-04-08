"""
Test suite for Memory system.
Validates working memory, episodic memory, and semantic memory operations.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.memory import WorkingMemory, EpisodicMemory, SemanticMemory


def test_working_memory():
    """Test working memory operations."""
    print("\n🧪 Test 1: Working Memory")
    
    wm = WorkingMemory(capacity=5)
    
    # Add items
    wm.add("task_1", {"type": "task", "content": "Search web"})
    wm.add("task_2", {"type": "task", "content": "Read file"})
    
    assert wm.size() == 2, "Should have 2 items"
    
    # Retrieve
    item = wm.get("task_1")
    assert item is not None, "Should retrieve item"
    assert item["content"] == "Search web", "Should have correct content"
    
    # Capacity limit
    for i in range(5):
        wm.add(f"item_{i}", {"data": i})
    
    assert wm.size() <= 5, "Should respect capacity limit"
    
    # Clear
    wm.clear()
    assert wm.size() == 0, "Should be empty after clear"
    
    print("   ✅ Working memory operations work correctly")
    return True


def test_episodic_memory():
    """Test episodic memory (experience storage)."""
    print("\n🧪 Test 2: Episodic Memory")
    
    em = EpisodicMemory()
    
    # Store episodes
    em.store({
        "task": "web_search",
        "input": "AGI research",
        "output": "Results...",
        "success": True,
        "timestamp": 1000
    })
    
    em.store({
        "task": "code_gen",
        "input": "Python function",
        "output": "def foo(): ...",
        "success": True,
        "timestamp": 1001
    })
    
    # Retrieve recent
    recent = em.get_recent(limit=2)
    assert len(recent) == 2, "Should get 2 episodes"
    
    # Search by task type
    web_episodes = em.search_by_task("web_search")
    assert len(web_episodes) == 1, "Should find web search episode"
    
    print("   ✅ Episodic memory operations work correctly")
    return True


def test_semantic_memory():
    """Test semantic memory (knowledge storage)."""
    print("\n🧪 Test 3: Semantic Memory")
    
    sm = SemanticMemory()
    
    # Store facts
    sm.store_fact(
        subject="Python",
        predicate="is_a",
        object_="programming_language",
        confidence=1.0
    )
    
    sm.store_fact(
        subject="Python",
        predicate="has_feature",
        object_="list_comprehensions",
        confidence=0.95
    )
    
    # Query
    facts = sm.query(subject="Python")
    assert len(facts) == 2, "Should find 2 facts about Python"
    
    # Query by predicate
    is_a_facts = sm.query(predicate="is_a")
    assert len(is_a_facts) == 1, "Should find 1 is_a fact"
    
    print("   ✅ Semantic memory operations work correctly")
    return True


def test_memory_integration():
    """Test integration between memory systems."""
    print("\n🧪 Test 4: Memory Integration")
    
    # Simulate agent workflow
    wm = WorkingMemory()
    em = EpisodicMemory()
    sm = SemanticMemory()
    
    # Agent looks up knowledge
    sm.store_fact(
        subject="web_search",
        predicate="requires",
        object_="API_KEY",
        confidence=1.0
    )
    
    # Agent performs task
    wm.add("current_task", {"action": "web_search", "query": "test"})
    
    # Agent recalls similar experience
    em.store({
        "task": "web_search",
        "query": "previous search",
        "success": True
    })
    
    # Integration: Use semantic knowledge to guide working memory
    search_requirements = sm.query(subject="web_search")
    wm.add("requirements", search_requirements)
    
    assert wm.get("requirements") is not None, "Requirements should be in working memory"
    
    # Integration: Learn from episode
    similar = em.search_by_task("web_search")
    wm.add("similar_experiences", similar)
    
    assert wm.get("similar_experiences") is not None, "Should have similar experiences"
    
    print("   ✅ Memory integration works correctly")
    return True


def test_memory_persistence():
    """Test memory persistence across sessions."""
    print("\n🧪 Test 5: Memory Persistence (Simulated)")
    
    # In real implementation, this would test save/load to disk
    # For now, test that memory structures are serializable
    
    em = EpisodicMemory()
    em.store({"event": "test", "data": {"nested": "value"}})
    
    import json
    
    # Episodic memory should be JSON serializable
    recent = em.get_recent()
    try:
        json.dumps(recent)
    except TypeError:
        assert False, "Memory should be serializable"
    
    sm = SemanticMemory()
    sm.store_fact("A", "B", "C")
    facts = sm.query()
    try:
        json.dumps(facts)
    except TypeError:
        assert False, "Semantic memory should be serializable"
    
    print("   ✅ Memory structures are serializable")
    return True


def run_all_tests():
    """Run all memory tests."""
    print("=" * 60)
    print("🧪 Memory System Test Suite")
    print("=" * 60)
    
    tests = [
        test_working_memory,
        test_episodic_memory,
        test_semantic_memory,
        test_memory_integration,
        test_memory_persistence,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"   ❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Results: {passed}/{passed+failed} tests passed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    
    if success:
        print("\n✅ All memory tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)
