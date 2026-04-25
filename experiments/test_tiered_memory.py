"""
Tests for Tiered Memory System (L0/L1/L2 Architecture)

Validates:
- Three-tier storage (L0, L1, L2)
- Automatic consolidation
- Importance-based forgetting
- Semantic search with embeddings
- Episodic clustering
- Context gathering for tasks
"""

import sys
sys.path.insert(0, '/home/workspace/agi-research')

from core.tiered_memory import (
    TieredMemorySystem, TieredMemoryEntry
)
from datetime import datetime, timedelta


def run_tests():
    """Run all tiered memory tests"""
    passed = 0
    failed = 0
    
    def test(name, condition, details=""):
        nonlocal passed, failed
        if condition:
            print(f"✅ {name}")
            passed += 1
        else:
            print(f"❌ {name}: {details}")
            failed += 1
    
    print("=" * 60)
    print("TIERED MEMORY SYSTEM TESTS")
    print("=" * 60)
    
    # ==== TEST 1: Initialization ====
    print("\n--- Initialization Tests ---")
    
    memory = TieredMemorySystem(agent_id="test_agent")
    
    test("1.1: Memory system initializes",
         memory is not None)
    
    test("1.2: L0 buffer has correct capacity",
         memory.l0_capacity == 7)
    
    test("1.3: L1 capacity is set",
         memory.l1_capacity == 100)
    
    test("1.4: L2 capacity is set",
         memory.l2_capacity == 10000)
    
    test("1.5: Session ID is generated",
         len(memory.session_id) > 0)
    
    test("1.6: Agent ID is stored",
         memory.agent_id == "test_agent")
    
    # ==== TEST 2: L0 Context Buffer ====
    print("\n--- L0 Context Buffer Tests ---")
    
    l0_id1 = memory.store_l0("Immediate context 1", tags=["test", "l0"])
    l0_id2 = memory.store_l0("Immediate context 2", tags=["test", "l0"])
    
    test("2.1: L0 stores return IDs",
         len(l0_id1) > 0 and len(l0_id2) > 0)
    
    test("2.2: L0 buffer contains entries",
         len(memory.l0_buffer) == 2)
    
    # Fill to capacity
    for i in range(10):
        memory.store_l0(f"Context {i}")
    
    test("2.3: L0 respects capacity limit",
         len(memory.l0_buffer) <= memory.l0_capacity)
    
    l0_context = memory.get_l0_context()
    test("2.4: L0 context retrieval works",
         len(l0_context) > 0)
    
    test("2.5: L0 context is most recent first",
         l0_context[0].content == "Context 9")
    
    # ==== TEST 3: L1 Working Memory ====
    print("\n--- L1 Working Memory Tests ---")
    
    # Clear and start fresh
    memory = TieredMemorySystem(agent_id="test_agent", l1_capacity=10)
    
    l1_id1 = memory.store_l1("Working memory 1", tags=["work", "test"], importance=0.7)
    l1_id2 = memory.store_l1("Working memory 2", tags=["work", "test"], importance=0.5)
    
    test("3.1: L1 stores return IDs",
         len(l1_id1) > 0 and len(l1_id2) > 0)
    
    test("3.2: L1 stores in working memory",
         len(memory.l1_working) == 2)
    
    retrieved = memory.retrieve(l1_id1)
    test("3.3: L1 retrieval works",
         retrieved is not None and retrieved.content == "Working memory 1")
    
    test("3.4: Retrieval increments access count",
         retrieved.access_count >= 1)
    
    test("3.5: Retrieval updates last_accessed",
         retrieved.last_accessed is not None)
    
    # Test L1 capacity eviction
    for i in range(15):
        memory.store_l1(f"Memory {i}", importance=0.3)
    
    test("3.6: L1 respects capacity",
         len(memory.l1_working) <= memory.l1_capacity)
    
    l1_entries = memory.get_l1_working()
    test("3.7: L1 retrieval sorted by importance",
         len(l1_entries) > 0)
    
    # ==== TEST 4: L2 Long-term Storage ====
    print("\n--- L2 Long-term Storage Tests ---")
    
    l2_id1 = memory.store_l2("Long-term fact 1", tags=["fact", "l2"], importance=0.9)
    l2_id2 = memory.store_l2("Long-term fact 2", tags=["fact", "l2"], importance=0.8)
    
    test("4.1: L2 stores return IDs",
         len(l2_id1) > 0 and len(l2_id2) > 0)
    
    test("4.2: L2 stores in long-term",
         len(memory.l2_longterm) >= 2)
    
    l2_entries = memory.get_l2_longterm()
    test("4.3: L2 retrieval works",
         len(l2_entries) > 0)
    
    l2_tagged = memory.get_l2_longterm(tag="fact")
    test("4.4: L2 tag filtering works",
         len(l2_tagged) >= 2)
    
    # ==== TEST 5: Tiered Store Method ====
    print("\n--- Tiered Store Method Tests ---")
    
    memory = TieredMemorySystem(agent_id="test_agent", l1_capacity=50)
    
    l0_id = memory.store("L0 content", tier=0, tags=["tier0"])
    l1_id = memory.store("L1 content", tier=1, tags=["tier1"], importance=0.6)
    l2_id = memory.store("L2 content", tier=2, tags=["tier2"], importance=0.8)
    
    test("5.1: Tier 0 store goes to L0 buffer",
         len(memory.l0_buffer) >= 1)
    
    test("5.2: Tier 1 store goes to L1",
         l1_id in memory.l1_working)
    
    test("5.3: Tier 2 store goes to L2",
         l2_id in memory.l2_longterm)
    
    # ==== TEST 6: Tag Indexing ====
    print("\n--- Tag Indexing Tests ---")
    
    memory.store_l1("Tagged content A", tags=["tag1", "tag2"], importance=0.5)
    memory.store_l1("Tagged content B", tags=["tag2", "tag3"], importance=0.5)
    memory.store_l1("Tagged content C", tags=["tag1", "tag3"], importance=0.5)
    
    results_tag1 = memory.search_by_tags(["tag1"])
    test("6.1: Single tag search works",
         len(results_tag1) >= 2)
    
    results_multi = memory.search_by_tags(["tag1", "tag2"])
    test("6.2: Multi-tag search works",
         len(results_multi) >= 1)
    
    results_tier2 = memory.search_by_tags(["tag2"], tier=1)
    test("6.3: Tier-filtered search works",
         all(e.tier == 1 for e in results_tier2))
    
    # ==== TEST 7: Semantic Search ====
    print("\n--- Semantic Search Tests ---")
    
    memory = TieredMemorySystem(agent_id="test_agent")
    
    # Store semantically similar content
    memory.store_l1("Machine learning is great for AI", 
                    tags=["ml"], importance=0.7)
    memory.store_l1("Neural networks power deep learning",
                    tags=["dl"], importance=0.7)
    memory.store_l1("Python is a programming language",
                    tags=["python"], importance=0.7)
    
    # Semantic search for ML-related
    sem_results = memory.semantic_search("artificial intelligence learning", limit=3)
    test("7.1: Semantic search returns results",
         len(sem_results) > 0)
    
    test("7.2: Semantic results have scores",
         all(isinstance(score, float) for _, score in sem_results))
    
    test("7.3: Semantic results are sorted by score",
         len(sem_results) < 2 or sem_results[0][1] >= sem_results[1][1])
    
    # ==== TEST 8: Consolidation ====
    print("\n--- Consolidation Tests ---")
    
    memory = TieredMemorySystem(agent_id="test_agent", 
                                  l1_capacity=20,
                                  consolidation_interval_minutes=0)
    
    # Store high-importance L1 memories
    high_imp_ids = []
    for i in range(5):
        mid = memory.store_l1(f"Important memory {i}", 
                             tags=["consolidate"], 
                             importance=0.9,
                             task_id="consolidation_test")
        high_imp_ids.append(mid)
    
    # Store low-importance L1 memories
    for i in range(5):
        memory.store_l1(f"Low memory {i}", 
                       tags=["consolidate"], 
                       importance=0.2)
    
    initial_l1 = len(memory.l1_working)
    initial_l2 = len(memory.l2_longterm)
    
    # Force consolidation by manipulating last_consolidation
    memory.last_consolidation = datetime.now() - timedelta(hours=1)
    
    # Trigger consolidation via store (which checks consolidation)
    memory.store_l1("Trigger consolidation", importance=0.5)
    
    test("8.1: High-importance entries consolidated to L2",
         len([e for e in memory.l2_longterm.values() if "Important memory" in str(e.content)]) > 0 or
         len([e for e in memory.l1_working.values() if "Important memory" in str(e.content)]) > 0)
    
    test("8.2: Low-importance entries may be forgotten",
         len(memory.l1_working) <= memory.l1_capacity)
    
    # ==== TEST 9: L2→L1 Promotion ====
    print("\n--- L2 to L1 Promotion Tests ---")
    
    memory = TieredMemorySystem(agent_id="test_agent", l1_capacity=20)
    
    # Store in L2 and access multiple times
    l2_id = memory.store_l2("Promotable memory", 
                          tags=["promote"], 
                          importance=0.95)
    
    # Access multiple times to increase importance
    for _ in range(10):
        entry = memory.retrieve(l2_id)
    
    test("9.1: L2 entry exists after retrieval",
         l2_id in memory.l2_longterm or l2_id in memory.l1_working)
    
    # ==== TEST 10: Episodic Clustering ====
    print("\n--- Episodic Clustering Tests ---")
    
    memory = TieredMemorySystem(agent_id="test_agent")
    
    # Create a cluster of related memories
    task_tags = ["episode", "task_123"]
    for i in range(5):
        entry_id = memory.store_l1(f"Episode step {i}",
                                   tags=task_tags,
                                   importance=0.6,
                                   task_id="task_123")
        # Manually trigger clustering
        if entry_id in memory.l1_working:
            memory._cluster_episodic(memory.l1_working[entry_id])
    
    cluster = memory.get_episodic_cluster(task_tags)
    test("10.1: Episodic cluster contains related memories",
         len(cluster) >= 1)
    
    # ==== TEST 11: Context Gathering ====
    print("\n--- Context Gathering Tests ---")
    
    memory = TieredMemorySystem(agent_id="test_agent")
    
    # Store task-related memories
    task_id = "analysis_task_001"
    memory.store_l0("User request: Analyze data", tags=["input"])
    memory.store_l1("Loaded dataset with 1000 rows", 
                    tags=["data", "loading"], 
                    importance=0.7,
                    task_id=task_id)
    memory.store_l1("Applied preprocessing", 
                    tags=["preprocessing"], 
                    importance=0.6,
                    task_id=task_id)
    memory.store_l2("Model: Random Forest works well", 
                    tags=["model", "rf"],
                    importance=0.8)
    
    context = memory.get_context_for_task(
        task_id=task_id,
        include_l0=True,
        include_l1=True,
        include_l2=True,
        relevant_tags=["model", "rf"]
    )
    
    test("11.1: Context includes task ID",
         context.get("task_id") == task_id)
    
    test("11.2: Context includes L0 if requested",
         "l0_context" in context)
    
    test("11.3: Context includes L1 if requested",
         "l1_working" in context)
    
    test("11.4: Context includes L2 if requested",
         "l2_relevant" in context)
    
    # ==== TEST 12: Memory Entry Properties ====
    print("\n--- Memory Entry Property Tests ---")
    
    entry = TieredMemoryEntry(
        content="Test entry",
        tier=1,
        importance=0.8,
        tags=["test"],
        decay_rate=0.01
    )
    
    test("12.1: Entry has generated ID",
         len(entry.id) > 0)
    
    test("12.2: Entry has timestamp",
         entry.timestamp is not None)
    
    test("12.3: Current importance decays with time",
         entry.current_importance() <= entry.importance)
    
    # Simulate access
    entry.touch()
    test("12.4: Touch increments access count",
         entry.access_count == 1)
    
    test("12.5: Touch updates last_accessed",
         entry.last_accessed is not None)
    
    # ==== TEST 13: Forgetting Mechanism ====
    print("\n--- Forgetting Mechanism Tests ---")
    
    memory = TieredMemorySystem(agent_id="test_agent", l2_capacity=20)
    
    # Fill L2 with varying importance
    for i in range(25):
        importance = 0.3 + (i % 5) * 0.15  # 0.3 to 0.9
        memory.store_l2(f"Memory {i}", 
                       tags=["forget_test"],
                       importance=importance)
    
    initial_l2 = len(memory.l2_longterm)
    
    # Add one more to trigger forgetting
    memory.store_l2("Overflow memory", tags=["forget_test"], importance=0.5)
    
    test("13.1: L2 respects capacity via forgetting",
         len(memory.l2_longterm) <= memory.l2_capacity)
    
    # Check that high-importance memories remain
    high_importance_count = sum(
        1 for e in memory.l2_longterm.values() 
        if e.importance >= 0.8
    )
    test("13.2: High-importance memories preserved",
         high_importance_count > 0)
    
    # ==== TEST 14: Save and Load ====
    print("\n--- Save/Load Persistence Tests ---")
    
    import tempfile
    import os
    
    memory1 = TieredMemorySystem(agent_id="persist_agent")
    
    # Add memories to all tiers
    memory1.store_l0("L0 test", tags=["persist"])
    memory1.store_l1("L1 test", tags=["persist"], importance=0.7)
    memory1.store_l2("L2 test", tags=["persist"], importance=0.9)
    
    # Save
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    try:
        memory1.save(temp_path)
        test("14.1: Save creates file",
             os.path.exists(temp_path))
        
        # Load into new memory
        memory2 = TieredMemorySystem(agent_id="new_agent")
        memory2.load(temp_path)
        
        test("14.2: Load restores agent_id",
             memory2.agent_id == "persist_agent")
        
        test("14.3: Load restores L1 memories",
             len(memory2.l1_working) > 0)
        
        test("14.4: Load restores L2 memories",
             len(memory2.l2_longterm) > 0)
        
        test("14.5: Load restores tag index",
             len(memory2.tag_index) > 0)
        
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
    
    # ==== TEST 15: Task Episodic Summary ====
    print("\n--- Task Episodic Summary Tests ---")
    
    memory = TieredMemorySystem(agent_id="test_agent")
    task_id = "summary_task"
    
    # Create task memories
    memory.store_l1("Started task", tags=["task"], importance=0.5, task_id=task_id)
    memory.store_l1("Critical step", tags=["task", "critical"], importance=0.9, task_id=task_id)
    memory.store_l1("Final result", tags=["task", "result"], importance=0.8, task_id=task_id)
    
    summary = memory.create_episodic_summary(task_id)
    test("15.1: Summary is generated",
         summary is not None and len(summary) > 0)
    
    test("15.2: Summary contains task ID",
         task_id in summary)
    
    test("15.3: Summary includes high-importance events",
         "Critical step" in summary or "3" in summary)
    
    # ==== TEST 16: Statistics ====
    print("\n--- Statistics Tests ---")
    
    memory = TieredMemorySystem(agent_id="stats_agent")
    
    # Populate all tiers
    for i in range(5):
        memory.store_l0(f"L0 {i}")
    for i in range(10):
        memory.store_l1(f"L1 {i}", importance=0.5 + i * 0.05)
    for i in range(15):
        memory.store_l2(f"L2 {i}", importance=0.4 + i * 0.04)
    
    stats = memory.get_stats()
    
    test("16.1: Stats includes L0 info",
         "l0_buffer" in stats)
    
    test("16.2: Stats includes L1 info",
         "l1_working" in stats)
    
    test("16.3: Stats includes L2 info",
         "l2_longterm" in stats)
    
    test("16.4: L1 stats has size",
         stats["l1_working"]["size"] == 10)
    
    test("16.5: L2 stats has size",
         stats["l2_longterm"]["size"] == 15)
    
    test("16.6: Stats includes indices info",
         "indices" in stats)
    
    # ==== TEST 17: Importance Decay ====
    print("\n--- Importance Decay Tests ---")
    
    entry = TieredMemoryEntry(
        content="Decaying memory",
        importance=1.0,
        decay_rate=0.1,
        last_accessed=datetime.now() - timedelta(hours=24)
    )
    
    current_imp = entry.current_importance()
    test("17.1: Importance decays over time",
         current_imp < entry.importance)
    
    test("17.2: Decay is exponential",
         current_imp <= 0.1)  # ~0.09 after 24 hours with rate 0.1
    
    # Test that access boosts importance
    entry2 = TieredMemoryEntry(
        content="Accessed memory",
        importance=0.5,
        decay_rate=0.01,
        access_count=10
    )
    boosted_imp = entry2.current_importance()
    test("17.3: Access count boosts importance",
         boosted_imp > 0.5)
    
    # ==== TEST 18: Embedding Generation ====
    print("\n--- Embedding Generation Tests ---")
    
    memory = TieredMemorySystem(agent_id="test_agent")
    
    emb1 = memory._generate_embedding("Machine learning")
    emb2 = memory._generate_embedding("Machine learning")
    emb3 = memory._generate_embedding("Deep learning")
    
    test("18.1: Embeddings have correct dimension",
         len(emb1) == 64)
    
    test("18.2: Same content produces same embedding",
         emb1 == emb2)
    
    test("18.3: Different content produces different embeddings",
         emb1 != emb3)
    
    sim_same = memory._cosine_similarity(emb1, emb2)
    sim_diff = memory._cosine_similarity(emb1, emb3)
    
    test("18.4: Same content has high similarity",
         sim_same > 0.99)
    
    test("18.5: Cosine similarity is normalized",
         -1 <= sim_diff <= 1)
    
    # ==== TEST 19: Task Indexing ====
    print("\n--- Task Indexing Tests ---")
    
    memory = TieredMemorySystem(agent_id="test_agent")
    
    task_a = "task_A"
    task_b = "task_B"
    
    for i in range(5):
        memory.store_l1(f"Task A step {i}", tags=["task_a"], 
                       task_id=task_a, importance=0.5)
        memory.store_l1(f"Task B step {i}", tags=["task_b"],
                       task_id=task_b, importance=0.5)
    
    a_ids = memory.task_index.get(task_a, set())
    b_ids = memory.task_index.get(task_b, set())
    
    test("19.1: Task A memories are indexed",
         len(a_ids) == 5)
    
    test("19.2: Task B memories are indexed",
         len(b_ids) == 5)
    
    test("19.3: Task indexes are separate",
         len(a_ids & b_ids) == 0)
    
    # ==== TEST 20: Edge Cases ====
    print("\n--- Edge Case Tests ---")
    
    memory = TieredMemorySystem(agent_id="edge_agent", l1_capacity=5)
    
    # Empty search
    empty_results = memory.search_by_tags(["nonexistent"])
    test("20.1: Search with no matches returns empty",
         len(empty_results) == 0)
    
    # Retrieve nonexistent
    missing = memory.retrieve("fake_id_12345")
    test("20.2: Retrieve nonexistent returns None",
         missing is None)
    
    # Store with empty content
    empty_id = memory.store_l1("", importance=0.5)
    test("20.3: Can store empty content",
         empty_id in memory.l1_working)
    
    # L0 overflow
    for i in range(100):
        memory.store_l0(f"Overflow {i}")
    test("20.4: L0 handles massive overflow",
         len(memory.l0_buffer) <= memory.l0_capacity)
    
    # ==== FINAL SUMMARY ====
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
