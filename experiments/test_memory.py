"""
Memory System Validation Tests

Tests for the core memory module following the experimental framework
outlined in ARCHITECTURE.md.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.memory import Memory, MemoryType, create_memory, InMemoryAdapter, FileAdapter
import tempfile
import shutil


class TestResults:
    """Simple test result tracker."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []
    
    def add(self, name: str, passed: bool, message: str = ""):
        self.tests.append((name, passed, message))
        if passed:
            self.passed += 1
        else:
            self.failed += 1
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*50}")
        print(f"TEST SUMMARY: {self.passed}/{total} passed")
        print(f"{'='*50}")
        for name, passed, message in self.tests:
            status = "✅ PASS" if passed else "❌ FAIL"
            print(f"{status}: {name}")
            if message and not passed:
                print(f"      {message}")
        return self.failed == 0


def test_memory_basic_store_retrieve():
    """Test basic store and retrieve operations."""
    mem = create_memory("memory")
    
    # Store simple content
    mid = mem.store("Hello, World!", MemoryType.SEMANTIC)
    assert mid is not None, "Should return memory ID"
    
    # Retrieve
    content = mem.retrieve(mid)
    assert content == "Hello, World!", f"Expected 'Hello, World!', got {content}"
    
    return True


def test_memory_structured_content():
    """Test storing structured/dict content."""
    mem = create_memory("memory")
    
    content = {
        "task": "test_task",
        "result": "success",
        "metrics": {"accuracy": 0.95, "latency": 100}
    }
    
    mid = mem.store(content, MemoryType.EPISODIC)
    retrieved = mem.retrieve(mid)
    
    assert retrieved == content, f"Structured content mismatch: {retrieved}"
    return True


def test_memory_types():
    """Test different memory types."""
    mem = create_memory("memory")
    
    # Store different types
    working_id = mem.store("working item", MemoryType.WORKING)
    episodic_id = mem.store("episodic item", MemoryType.EPISODIC)
    semantic_id = mem.store("semantic item", MemoryType.SEMANTIC)
    procedural_id = mem.store("procedural item", MemoryType.PROCEDURAL)
    
    # Query by type
    working = mem.recall(memory_type=MemoryType.WORKING)
    episodic = mem.recall(memory_type=MemoryType.EPISODIC)
    semantic = mem.recall(memory_type=MemoryType.SEMANTIC)
    procedural = mem.recall(memory_type=MemoryType.PROCEDURAL)
    
    assert len(working) == 1, f"Expected 1 working, got {len(working)}"
    assert len(episodic) == 1, f"Expected 1 episodic, got {len(episodic)}"
    assert len(semantic) == 1, f"Expected 1 semantic, got {len(semantic)}"
    assert len(procedural) == 1, f"Expected 1 procedural, got {len(procedural)}"
    
    return True


def test_working_memory_capacity():
    """Test working memory capacity limit (Miller's law: 7±2)."""
    mem = create_memory("memory")
    
    # Store more than capacity
    ids = []
    for i in range(10):
        mid = mem.store(f"item {i}", MemoryType.WORKING)
        ids.append(mid)
    
    # Check working memory capacity enforced
    working = mem.recall(memory_type=MemoryType.WORKING)
    assert len(working) <= mem.WORKING_MEMORY_CAPACITY, \
        f"Working memory exceeded capacity: {len(working)} > {mem.WORKING_MEMORY_CAPACITY}"
    
    # Check auto-consolidation happened
    episodic = mem.recall(memory_type=MemoryType.EPISODIC)
    assert len(episodic) >= 3, f"Expected at least 3 consolidated, got {len(episodic)}"
    
    return True


def test_memory_consolidation():
    """Test manual consolidation of working memory."""
    mem = create_memory("memory")
    
    # Add to working memory
    mid1 = mem.store("item 1", MemoryType.WORKING)
    mid2 = mem.store("item 2", MemoryType.WORKING)
    
    # Consolidate specific item
    consolidated = mem.consolidate(mid1)
    assert mid1 in consolidated, "Should consolidate specified item"
    
    # Check it moved to episodic
    entry = mem._adapter.retrieve(mid1)
    assert entry.memory_type == MemoryType.EPISODIC, "Should be episodic after consolidation"
    
    # Consolidate all remaining working memory
    mem.consolidate()
    working = mem.recall(memory_type=MemoryType.WORKING)
    assert len(working) == 0, "Working memory should be empty after full consolidation"
    
    return True


def test_memory_importance():
    """Test importance-based retrieval."""
    mem = create_memory("memory")
    
    # Store with different importance
    low_id = mem.store("low importance", MemoryType.SEMANTIC, importance=0.3)
    mid_id = mem.store("medium importance", MemoryType.SEMANTIC, importance=0.6)
    high_id = mem.store("high importance", MemoryType.SEMANTIC, importance=0.9)
    
    # Query with minimum importance
    high_only = mem.recall(min_importance=0.8)
    assert len(high_only) == 1, f"Expected 1 high importance, got {len(high_only)}"
    assert high_only[0]["content"] == "high importance"
    
    medium_plus = mem.recall(min_importance=0.5)
    assert len(medium_plus) == 2, f"Expected 2 medium+, got {len(medium_plus)}"
    
    return True


def test_memory_update():
    """Test memory updates."""
    mem = create_memory("memory")
    
    mid = mem.store("original", MemoryType.SEMANTIC)
    
    # Update
    success = mem.update(mid, "updated", new_importance=0.8)
    assert success, "Update should succeed"
    
    # Verify
    retrieved = mem.retrieve(mid)
    assert retrieved == "updated", f"Expected 'updated', got {retrieved}"
    
    entry = mem._adapter.retrieve(mid)
    assert entry.importance == 0.8, f"Importance should be 0.8, got {entry.importance}"
    
    return True


def test_memory_forget():
    """Test memory deletion."""
    mem = create_memory("memory")
    
    mid = mem.store("to be forgotten", MemoryType.SEMANTIC)
    assert mem.retrieve(mid) is not None, "Should exist before deletion"
    
    success = mem.forget(mid)
    assert success, "Forget should succeed"
    
    assert mem.retrieve(mid) is None, "Should not exist after deletion"
    
    return True


def test_memory_search():
    """Test content-based search (recall with query)."""
    mem = create_memory("memory")
    
    mem.store("apple pie recipe", MemoryType.SEMANTIC)
    mem.store("banana bread recipe", MemoryType.SEMANTIC)
    mem.store("apple orchard location", MemoryType.SEMANTIC)
    mem.store("completely different", MemoryType.SEMANTIC)
    
    # Search for apple
    apple_results = mem.recall(query="apple")
    assert len(apple_results) == 2, f"Expected 2 apple results, got {len(apple_results)}"
    
    # Search for recipe
    recipe_results = mem.recall(query="recipe")
    assert len(recipe_results) == 2, f"Expected 2 recipe results, got {len(recipe_results)}"
    
    return True


def test_memory_metadata():
    """Test metadata storage and retrieval."""
    mem = create_memory("memory")
    
    mid = mem.store(
        "content",
        MemoryType.EPISODIC,
        metadata={
            "source": "test",
            "tags": ["important", "research"],
            "confidence": 0.95
        }
    )
    
    results = mem.recall(memory_type=MemoryType.EPISODIC)
    assert len(results) == 1
    
    metadata = results[0]["metadata"]
    assert metadata["source"] == "test"
    assert metadata["tags"] == ["important", "research"]
    assert metadata["confidence"] == 0.95
    
    return True


def test_file_adapter():
    """Test file-based persistence."""
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create and store
        mem1 = create_memory("file", storage_dir=temp_dir)
        mid = mem1.store("persistent content", MemoryType.SEMANTIC, importance=0.9)
        
        # Create new instance with same directory
        mem2 = create_memory("file", storage_dir=temp_dir)
        
        # Should retrieve from disk
        content = mem2.retrieve(mid)
        assert content == "persistent content", f"Expected 'persistent content', got {content}"
        
        # Check stats
        stats = mem2.stats()
        assert stats["total_entries"] == 1
        
    finally:
        shutil.rmtree(temp_dir)
    
    return True


def test_memory_stats():
    """Test memory statistics."""
    mem = create_memory("memory")
    
    # Empty stats
    stats = mem.stats()
    assert stats["total_entries"] == 0
    assert stats["working_memory_items"] == 0
    
    # Add memories
    mem.store("working", MemoryType.WORKING)
    mem.store("episodic", MemoryType.EPISODIC)
    mem.store("semantic1", MemoryType.SEMANTIC)
    mem.store("semantic2", MemoryType.SEMANTIC)
    
    stats = mem.stats()
    assert stats["total_entries"] == 4
    assert stats["by_type"]["working"] == 1
    assert stats["by_type"]["episodic"] == 1
    assert stats["by_type"]["semantic"] == 2
    
    return True


def run_all_tests():
    """Run all memory tests."""
    results = TestResults()
    
    tests = [
        ("Basic Store/Retrieve", test_memory_basic_store_retrieve),
        ("Structured Content", test_memory_structured_content),
        ("Memory Types", test_memory_types),
        ("Working Memory Capacity", test_working_memory_capacity),
        ("Memory Consolidation", test_memory_consolidation),
        ("Importance-based Retrieval", test_memory_importance),
        ("Memory Update", test_memory_update),
        ("Memory Forget", test_memory_forget),
        ("Content Search", test_memory_search),
        ("Metadata Storage", test_memory_metadata),
        ("File Adapter Persistence", test_file_adapter),
        ("Memory Statistics", test_memory_stats),
    ]
    
    for name, test_fn in tests:
        try:
            test_fn()
            results.add(name, True)
            print(f"✅ {name}")
        except AssertionError as e:
            results.add(name, False, str(e))
            print(f"❌ {name}: {e}")
        except Exception as e:
            results.add(name, False, f"Unexpected error: {e}")
            print(f"❌ {name}: Unexpected error: {e}")
    
    return results


if __name__ == "__main__":
    print("="*50)
    print("MEMORY SYSTEM VALIDATION TESTS")
    print("="*50)
    print()
    
    results = run_all_tests()
    success = results.summary()
    
    sys.exit(0 if success else 1)
