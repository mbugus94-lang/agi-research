"""
Validation tests for Tiered Memory System.

Tests cover:
- Tier boundaries and promotion/demotion
- Directory-based organization
- Context loading efficiency
- Retrieval trajectories
- Compression and archival
"""

import sys
sys.path.insert(0, '/home/workspace/agi-research')

from core.tiered_memory import (
    TieredMemorySystem, MemoryDirectory, MemoryEntry, MemoryTier
)


def test_basic_tier_creation():
    """Test: Can create memories in different tiers."""
    memory = TieredMemorySystem()
    
    l0 = memory.store("Current user message", tier=MemoryTier.L0_IMMEDIATE)
    l1 = memory.store("Recent conversation context", tier=MemoryTier.L1_WORKING)
    l2 = memory.store("Long-term knowledge fact", tier=MemoryTier.L2_ARCHIVAL)
    
    assert l0.tier == MemoryTier.L0_IMMEDIATE
    assert l1.tier == MemoryTier.L1_WORKING
    assert l2.tier == MemoryTier.L2_ARCHIVAL
    
    assert len(memory.l0_entries) == 1
    assert len(memory.l1_entries) == 1
    assert len(memory.l2_entries) == 1
    
    print("✅ Basic tier creation works")


def test_directory_organization():
    """Test: Filesystem-style directory structure."""
    memory = TieredMemorySystem()
    
    # Store in different directories
    memory.store("Tool: web_search result", directory="/tools/web", tier=MemoryTier.L1_WORKING)
    memory.store("Tool: file_read result", directory="/tools/files", tier=MemoryTier.L1_WORKING)
    memory.store("User preference", directory="/user/preferences", tier=MemoryTier.L2_ARCHIVAL)
    
    # Navigate directories
    tools_dir = memory.root.find("/tools")
    assert tools_dir is not None
    assert "web/" in tools_dir.ls()
    assert "files/" in tools_dir.ls()
    
    user_dir = memory.root.find("/user")
    assert user_dir is not None
    assert "preferences/" in user_dir.ls()
    
    print("✅ Directory organization works")


def test_l0_promotion_to_l1():
    """Test: L0 entries promoted to L1 when limit exceeded."""
    memory = TieredMemorySystem()
    
    # Fill L0 beyond capacity
    for i in range(15):
        memory.store(f"Message {i}", tier=MemoryTier.L0_IMMEDIATE)
    
    # L0 should be at capacity, overflow in L1
    assert len(memory.l0_entries) <= memory.L0_MAX_SIZE
    assert len(memory.l1_entries) > 0  # Overflow promoted
    
    # All entries should still be findable
    all_memories = memory.root.walk()
    assert len(all_memories) == 15
    
    print("✅ L0 promotion to L1 works")


def test_context_loading_order():
    """Test: Context loads in correct priority order (L0 -> L1 -> L2)."""
    memory = TieredMemorySystem()
    
    # Store in reverse priority order
    memory.store("Archival knowledge", tier=MemoryTier.L2_ARCHIVAL)
    memory.store("Working context", tier=MemoryTier.L1_WORKING)
    memory.store("Immediate message", tier=MemoryTier.L0_IMMEDIATE)
    
    context = memory.load_context()
    
    # L0 should be first
    assert len(context["l0_entries"]) == 1
    assert context["l0_entries"][0] == "Immediate message"
    
    # L1 should be included
    assert len(context["l1_entries"]) == 1
    assert context["l1_entries"][0] == "Working context"
    
    # Without query, L2 shouldn't auto-load
    assert len(context["l2_entries"]) == 0
    
    print("✅ Context loading priority works")


def test_semantic_retrieval():
    """Test: Can retrieve relevant memories by query."""
    memory = TieredMemorySystem()
    
    memory.store("Python is a programming language", tier=MemoryTier.L1_WORKING)
    memory.store("JavaScript runs in browsers", tier=MemoryTier.L1_WORKING)
    memory.store("Python has list comprehensions", tier=MemoryTier.L1_WORKING)
    memory.store("Machine learning uses neural networks", tier=MemoryTier.L1_WORKING)
    
    results = memory.retrieve_relevant("python programming", top_k=2)
    
    assert len(results) == 2
    # Python-related results should rank higher
    assert "python" in results[0][0].content.lower()
    
    print("✅ Semantic retrieval works")


def test_retrieval_trajectory():
    """Test: Loading produces observable retrieval trajectory."""
    memory = TieredMemorySystem()
    
    memory.store("Current task instruction", tier=MemoryTier.L0_IMMEDIATE, importance=0.9)
    memory.store("Previous tool output", tier=MemoryTier.L1_WORKING, importance=0.7)
    memory.store("Relevant background", tier=MemoryTier.L2_ARCHIVAL, importance=0.5)
    
    context = memory.load_context(query="task background", expand_tiers=True)
    
    trajectory = context["retrieval_trajectory"]
    assert len(trajectory) >= 2
    
    # First entries should be from L0
    assert trajectory[0].startswith("L0:")
    
    print("✅ Retrieval trajectory is observable")


def test_access_pattern_tracking():
    """Test: Memory access updates relevance scores."""
    memory = TieredMemorySystem()
    
    entry = memory.store("Important fact", tier=MemoryTier.L1_WORKING)
    
    initial_access = entry.access_count
    initial_relevance = entry.relevance_score
    
    # Simulate access
    entry.access()
    entry.access()
    entry.access()
    
    assert entry.access_count == initial_access + 3
    # Relevance should increase with access
    assert entry.relevance_score > initial_relevance
    
    print("✅ Access pattern tracking works")


def test_compression_and_archival():
    """Test: Old memories compressed and archived to L2."""
    import time
    
    memory = TieredMemorySystem()
    
    # Create old entries by manipulating timestamps
    old_entry = memory.store("Old conversation", tier=MemoryTier.L1_WORKING)
    old_entry.last_accessed = time.time() - 100000  # Make it old
    
    # Archive old entries
    compressed = memory.compress_and_archive()
    
    assert len(compressed) >= 1
    assert compressed[0].tier == MemoryTier.L2_ARCHIVAL
    assert compressed[0].compression_ratio < 1.0
    
    print("✅ Compression and archival works")


def test_session_statistics():
    """Test: Can generate comprehensive session statistics."""
    memory = TieredMemorySystem()
    
    # Populate with varied data
    for i in range(5):
        memory.store(f"L0 message {i}", tier=MemoryTier.L0_IMMEDIATE, importance=0.9)
    for i in range(10):
        memory.store(f"L1 context {i}", tier=MemoryTier.L1_WORKING, importance=0.6)
    for i in range(3):
        memory.store(f"L2 knowledge {i}", tier=MemoryTier.L2_ARCHIVAL, importance=0.4)
    
    stats = memory.session_summary()
    
    assert stats["l0_count"] == 5
    assert stats["l1_count"] == 10
    assert stats["l2_count"] == 3
    assert stats["total_memories"] == 18
    assert stats["avg_importance_l0"] > stats["avg_importance_l2"]
    
    print("✅ Session statistics generation works")


def test_directory_walk():
    """Test: Can recursively walk directory structure."""
    memory = TieredMemorySystem()
    
    # Create nested structure
    memory.store("Root memory", directory="/")
    memory.store("Tools memory", directory="/tools")
    memory.store("Web tool memory", directory="/tools/web")
    memory.store("Deep nested", directory="/a/b/c/d")
    
    # Walk from root
    all_memories = memory.root.walk()
    assert len(all_memories) == 4
    
    # Walk with depth limit
    limited = memory.root.walk(max_depth=1)
    assert len(limited) == 2  # Root + /tools
    
    print("✅ Directory walk works")


def test_memory_entry_serialization():
    """Test: Memories can be serialized and deserialized."""
    entry = MemoryEntry(
        content="Test content",
        tier=MemoryTier.L1_WORKING,
        importance_score=0.8,
        tags={"test", "important"},
        source="test_source"
    )
    
    # Serialize
    data = entry.to_dict()
    
    # Deserialize
    restored = MemoryEntry.from_dict(data)
    
    assert restored.content == entry.content
    assert restored.tier == entry.tier
    assert restored.importance_score == entry.importance_score
    assert restored.tags == entry.tags
    assert restored.source == entry.source
    
    print("✅ Memory entry serialization works")


def test_token_efficiency():
    """Test: Tiered loading is token-efficient."""
    memory = TieredMemorySystem()
    
    # Create many memories
    for i in range(50):
        memory.store(f"Large memory content with many words {i} " * 20, tier=MemoryTier.L1_WORKING)
    
    # Load with limited tokens
    context = memory.load_context(max_tokens=500, expand_tiers=False)
    
    # Should not exceed token limit significantly
    assert context["estimated_tokens"] <= 600  # Small buffer for estimation error
    
    # Should prioritize L0/L1
    assert len(context["l0_entries"]) + len(context["l1_entries"]) > 0
    
    print("✅ Token efficiency works")


if __name__ == "__main__":
    print("\n🧪 Running Tiered Memory System Tests\n")
    
    tests = [
        test_basic_tier_creation,
        test_directory_organization,
        test_l0_promotion_to_l1,
        test_context_loading_order,
        test_semantic_retrieval,
        test_retrieval_trajectory,
        test_access_pattern_tracking,
        test_compression_and_archival,
        test_session_statistics,
        test_directory_walk,
        test_memory_entry_serialization,
        test_token_efficiency
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} FAILED: {e}")
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"Results: {passed}/{len(tests)} tests passed")
    if failed == 0:
        print("🎉 All tests passed!")
    else:
        print(f"⚠️ {failed} test(s) failed")
    print(f"{'='*50}\n")
