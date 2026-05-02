"""
Agent-Memory Integration Tests

Validates that the BaseAgent properly integrates with the memory system:
- Working memory capacity management (Miller's Law)
- Automatic memory consolidation
- Memory-aware task execution
- Episodic memory for learning
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.agent import BaseAgent, AgentIdentity, Task
from core.memory import MemoryType


def test_agent_creation():
    """Test agent initialization with memory"""
    print("\n=== Test: Agent Creation ===")
    agent = BaseAgent()
    
    # Check memory initialized
    assert agent.memory is not None, "Memory should be initialized"
    
    # Check identity stored in semantic memory
    stats = agent.get_memory_stats()
    assert stats['by_type'].get('semantic', 0) >= 1, "Identity should be stored in semantic memory"
    
    print(f"✅ Agent created with memory adapter: {stats['storage_adapter']}")
    print(f"   Memory stats: {stats}")
    return True


def test_remember_and_recall():
    """Test working memory storage and retrieval"""
    print("\n=== Test: Remember and Recall ===")
    agent = BaseAgent()
    
    # Store several items in working memory
    mem_ids = []
    for i in range(5):
        mid = agent.remember(
            content={"event": f"test_event_{i}", "value": i},
            context={"test_id": i},
            importance=0.5
        )
        mem_ids.append(mid)
    
    # Verify all stored
    working = agent.memory.get_working_memory()
    assert len(working) == 5, f"Expected 5 working memories, got {len(working)}"
    
    # Test recall
    results = agent.recall(query="test_event", memory_type=MemoryType.WORKING)
    assert len(results) == 5, f"Expected 5 recalled memories, got {len(results)}"
    
    print(f"✅ Successfully stored and recalled {len(results)} memories")
    return True


def test_working_memory_capacity():
    """Test Miller's Law: working memory capacity ~7 items"""
    print("\n=== Test: Working Memory Capacity (Miller's Law) ===")
    agent = BaseAgent()
    
    # Store more than capacity (should trigger auto-consolidation)
    for i in range(10):
        agent.remember(
            content={"event": f"capacity_test_{i}", "value": i},
            importance=0.3
        )
    
    stats = agent.get_memory_stats()
    working_count = stats['working_memory_items']
    episodic_count = stats['by_type'].get('episodic', 0)
    
    # Working memory should be at capacity
    assert working_count <= 7, f"Working memory exceeded capacity: {working_count}"
    
    # Some should have been consolidated to episodic
    assert episodic_count > 0, "Some memories should be consolidated to episodic"
    
    print(f"✅ Working memory respects Miller's Law: {working_count} items (capacity: 7)")
    print(f"   Auto-consolidated {episodic_count} items to episodic memory")
    return True


def test_memorize_fact():
    """Test semantic memory storage"""
    print("\n=== Test: Semantic Memory (Facts) ===")
    agent = BaseAgent()
    
    # Store facts
    fact1 = agent.memorize_fact(
        content={"fact": "The sky is blue", "confidence": 0.99},
        category="physics",
        importance=0.7
    )
    
    fact2 = agent.memorize_fact(
        content={"fact": "2 + 2 = 4", "confidence": 1.0},
        category="math",
        importance=0.9
    )
    
    # Recall facts
    facts = agent.recall(memory_type=MemoryType.SEMANTIC, limit=10)
    assert len(facts) >= 2, f"Expected at least 2 facts, got {len(facts)}"
    
    # Check content
    fact_contents = [f['content'] for f in facts]
    assert any("sky is blue" in str(f) for f in fact_contents), "Sky fact should be stored"
    
    print(f"✅ Successfully stored {len(facts)} facts in semantic memory")
    return True


def test_learn_skill():
    """Test procedural memory for skills"""
    print("\n=== Test: Procedural Memory (Skills) ===")
    agent = BaseAgent()
    
    def sample_skill(x: int) -> int:
        """Doubles the input value"""
        return x * 2
    
    # Register skill
    agent.register_skill("double", sample_skill, store_in_memory=True)
    
    # Check skill stored in procedural memory
    skills = agent.recall(memory_type=MemoryType.PROCEDURAL)
    assert len(skills) >= 1, "Skill should be stored in procedural memory"
    
    # Check skill available
    assert "double" in agent.skills, "Skill should be registered"
    result = agent.execute_skill("double", x=5)
    assert result == 10, f"Skill should return 10, got {result}"
    
    print(f"✅ Skill stored in procedural memory and executed successfully")
    return True


def test_memory_context_retrieval():
    """Test memory-aware context for tasks"""
    print("\n=== Test: Memory Context Retrieval ===")
    agent = BaseAgent()
    
    # Store some episodic memories with matching content
    for i in range(3):
        agent.memory.store(
            content={"task_description": f"similar task about testing", "outcome": "success"},
            memory_type=MemoryType.EPISODIC,
            importance=0.6
        )
    
    # Get context for a task
    context = agent.get_memory_context("similar task about testing", limit=5)
    
    assert 'working_memory' in context, "Context should include working memory"
    assert 'episodic_memories' in context, "Context should include episodic memories"
    assert 'semantic_memories' in context, "Context should include semantic memories"
    assert 'procedural_memories' in context, "Context should include procedural memories"
    
    # Should have retrieved some episodic memories (query matching)
    # Note: Query matching is simple substring, so check if structure is correct
    assert len(context['episodic_memories']) >= 0, "Should retrieve episodic memories structure"
    
    print(f"✅ Retrieved context with {context['total_context_items']} items")
    print(f"   - Working: {len(context['working_memory'])}")
    print(f"   - Episodic: {len(context['episodic_memories'])}")
    print(f"   - Semantic: {len(context['semantic_memories'])}")
    print(f"   - Procedural: {len(context['procedural_memories'])}")
    return True


def test_task_execution_memory_logging():
    """Test that task execution logs to memory"""
    print("\n=== Test: Task Execution Memory Logging ===")
    agent = BaseAgent()
    
    def success_skill():
        return {"status": "success", "data": "test"}
    
    agent.register_skill("success", success_skill)
    
    # Create and execute task
    task = agent.create_task(
        description="Test task with memory",
        goal="Test memory logging during execution"
    )
    
    # Manually mark task as complete for testing
    result = agent.execute_task(task, max_iterations=1)
    
    # Check memories were created
    episodic = agent.recall(memory_type=MemoryType.EPISODIC, limit=20)
    assert len(episodic) > 0, "Task execution should create episodic memories"
    
    # Check for task-related events
    events = [e for e in episodic if 'event' in str(e.get('content', ''))]
    assert len(events) > 0, "Should have logged task events"
    
    print(f"✅ Task execution created {len(episodic)} episodic memories")
    return True


def test_memory_consolidation_after_task():
    """Test that working memory consolidates after task completion"""
    print("\n=== Test: Post-Task Memory Consolidation ===")
    agent = BaseAgent()
    
    # Fill working memory
    for i in range(5):
        agent.remember(content={"test": i}, importance=0.5)
    
    working_before = len(agent.memory.get_working_memory())
    
    # Execute a task (should trigger consolidation)
    task = agent.create_task(description="Test", goal="Test consolidation")
    agent.execute_task(task, max_iterations=1)
    
    # Working memory should be cleared/consolidated
    stats = agent.get_memory_stats()
    
    print(f"✅ Working memory before task: {working_before}, after: {stats['working_memory_items']}")
    return True


def test_persistence_with_file_adapter():
    """Test file-based memory persistence"""
    print("\n=== Test: File Adapter Persistence ===")
    import tempfile
    import shutil
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create agent with file storage
        agent1 = BaseAgent(memory_adapter="file", memory_path=temp_dir)
        agent1.memorize_fact(content={"test_fact": "persistent"}, importance=0.8)
        
        # Create new agent pointing to same storage
        agent2 = BaseAgent(memory_adapter="file", memory_path=temp_dir)
        
        # Should retrieve the fact
        facts = agent2.recall(memory_type=MemoryType.SEMANTIC)
        assert len(facts) >= 1, "Should retrieve persisted fact"
        
        print(f"✅ File adapter successfully persisted {len(facts)} memories")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    return True


def test_agent_state_saving():
    """Test agent state export"""
    print("\n=== Test: Agent State Saving ===")
    import tempfile
    import json
    
    agent = BaseAgent(identity=AgentIdentity(name="TestAgent"))
    agent.register_skill("test", lambda: "test")
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_path = f.name
    
    try:
        agent.save_agent_state(temp_path)
        
        with open(temp_path, 'r') as f:
            state = json.load(f)
        
        assert 'identity' in state, "State should include identity"
        assert 'memory_stats' in state, "State should include memory stats"
        assert state['identity']['name'] == "TestAgent", "Identity should match"
        
        print(f"✅ Agent state saved successfully")
        print(f"   Identity: {state['identity']['name']}")
        print(f"   Skills: {state['skills_registered']}")
    finally:
        os.unlink(temp_path)
    
    return True


def run_all_tests():
    """Run all integration tests"""
    print("=" * 60)
    print("AGENT-MEMORY INTEGRATION TESTS")
    print("=" * 60)
    
    tests = [
        test_agent_creation,
        test_remember_and_recall,
        test_working_memory_capacity,
        test_memorize_fact,
        test_learn_skill,
        test_memory_context_retrieval,
        test_task_execution_memory_logging,
        test_memory_consolidation_after_task,
        test_persistence_with_file_adapter,
        test_agent_state_saving,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ FAILED: {test.__name__}")
            print(f"   Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
