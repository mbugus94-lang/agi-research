"""
Tests for Enhanced Memory System

Validates:
- Vector-based semantic search
- Memory consolidation (L0 → L1 → L2)
- Context compression
- Importance scoring
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import json
import tempfile
from datetime import datetime
import numpy as np

from core.enhanced_memory import (
    MemoryEntry,
    SimpleEmbeddingModel,
    EnhancedMemorySystem,
    create_enhanced_memory_system
)


class TestMemoryEntry(unittest.TestCase):
    """Test MemoryEntry dataclass."""
    
    def test_creation(self):
        """Test basic memory entry creation."""
        entry = MemoryEntry(content="Test content", tags=["test"])
        self.assertIsNotNone(entry.id)
        self.assertEqual(entry.content, "Test content")
        self.assertEqual(entry.tags, ["test"])
        self.assertEqual(entry.memory_type, "episodic")
        self.assertEqual(entry.access_count, 0)
    
    def test_importance_computation(self):
        """Test importance score computation."""
        entry = MemoryEntry(content="Critical error in production system")
        score = entry.compute_importance()
        
        # Should be higher than base due to keywords
        self.assertGreater(score, 0.3)
        
        # Test with access count
        entry.access_count = 10
        score2 = entry.compute_importance()
        self.assertGreater(score2, score)
    
    def test_serialization(self):
        """Test to_dict and from_dict."""
        entry = MemoryEntry(
            content="Test",
            tags=["a", "b"],
            importance=0.8
        )
        entry.embedding = np.array([0.1, 0.2, 0.3])
        
        data = entry.to_dict()
        restored = MemoryEntry.from_dict(data)
        
        self.assertEqual(restored.content, entry.content)
        self.assertEqual(restored.tags, entry.tags)
        self.assertEqual(restored.importance, entry.importance)
        self.assertTrue(np.allclose(restored.embedding, entry.embedding))


class TestSimpleEmbeddingModel(unittest.TestCase):
    """Test SimpleEmbeddingModel."""
    
    def test_embedding_creation(self):
        """Test basic embedding generation."""
        model = SimpleEmbeddingModel(embedding_dim=10)
        
        text = "hello world test"
        embedding = model.embed(text)
        
        self.assertEqual(len(embedding), 10)
        self.assertAlmostEqual(np.linalg.norm(embedding), 1.0, places=5)
    
    def test_embedding_consistency(self):
        """Test same text produces same embedding."""
        model = SimpleEmbeddingModel(embedding_dim=10)
        
        text = "the quick brown fox"
        emb1 = model.embed(text)
        emb2 = model.embed(text)
        
        self.assertTrue(np.allclose(emb1, emb2))
    
    def test_embedding_similarity(self):
        """Test similar texts have higher similarity."""
        model = SimpleEmbeddingModel(embedding_dim=20)
        
        text1 = "machine learning artificial intelligence"
        text2 = "machine learning ai"
        text3 = "completely unrelated topic about cooking"
        
        emb1 = model.embed(text1)
        emb2 = model.embed(text2)
        emb3 = model.embed(text3)
        
        sim_1_2 = np.dot(emb1, emb2)
        sim_1_3 = np.dot(emb1, emb3)
        
        self.assertGreater(sim_1_2, sim_1_3)


class TestEnhancedMemorySystem(unittest.TestCase):
    """Test EnhancedMemorySystem."""
    
    def setUp(self):
        """Set up test memory system."""
        self.memory = EnhancedMemorySystem(
            l0_capacity=5,
            l1_capacity=20,
            l2_capacity=10,
            consolidation_threshold=10
        )
    
    def test_store_and_retrieve(self):
        """Test basic store and retrieve operations."""
        mem_id = self.memory.store("Test content", memory_type="episodic")
        
        retrieved = self.memory.retrieve(mem_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.content, "Test content")
        self.assertEqual(retrieved.access_count, 1)  # Incremented on retrieve
    
    def test_working_memory_capacity(self):
        """Test L0 working memory has limited capacity."""
        # Fill working memory beyond capacity
        for i in range(10):
            self.memory.store(f"Content {i}", memory_type="working")
        
        # Should only have last 5
        self.assertEqual(len(self.memory.l0_working), 5)
    
    def test_episodic_memory_eviction(self):
        """Test L1 episodic memory eviction."""
        memory = EnhancedMemorySystem(
            l0_capacity=5,
            l1_capacity=5,  # Small for testing
            l2_capacity=5
        )
        
        # Store more than capacity
        ids = []
        for i in range(10):
            mid = memory.store(f"Episodic {i}", memory_type="episodic")
            ids.append(mid)
        
        # Should have 5 entries
        self.assertEqual(len(memory.l1_episodic), 5)
        
        # Some early IDs should be evicted
        early_retrieved = memory.retrieve(ids[0])
        # May or may not be evicted depending on importance
    
    def test_semantic_search(self):
        """Test vector-based semantic search."""
        # Store some memories
        self.memory.store("Machine learning is fascinating", 
                         memory_type="episodic", tags=["ai"])
        self.memory.store("Python is a great programming language",
                         memory_type="episodic", tags=["coding"])
        self.memory.store("Deep learning uses neural networks",
                         memory_type="episodic", tags=["ai"])
        
        # Search for AI-related content
        results = self.memory.semantic_search("artificial intelligence", top_k=3)
        
        # Should return results
        self.assertGreater(len(results), 0)
        
        # All results should have similarity scores
        for entry, similarity in results:
            self.assertIsInstance(similarity, float)
            self.assertGreaterEqual(similarity, -1.0)
            self.assertLessEqual(similarity, 1.0)
    
    def test_consolidation_working_to_episodic(self):
        """Test L0 to L1 consolidation."""
        memory = EnhancedMemorySystem(
            l0_capacity=5,
            l1_capacity=20,
            consolidation_threshold=5
        )
        
        # Store important working memories
        for i in range(5):
            memory.store(f"Important {i}", memory_type="working")
        
        # Access some to increase importance
        for entry in list(memory.l0_working)[:3]:
            entry.access_count = 3
            entry.importance = 0.7
        
        # Trigger consolidation
        memory._consolidate_working_to_episodic()
        
        # Important entries should be in episodic
        self.assertGreater(len(memory.l1_episodic), 0)
    
    def test_context_compression(self):
        """Test context compression for LLM prompts."""
        # Store various memories
        for i in range(10):
            self.memory.store(f"Memory {i}", memory_type="working")
        
        compressed = self.memory.compress_context(max_entries=3)
        
        self.assertLessEqual(len(compressed), 3)
        for item in compressed:
            self.assertIn("content", item)
            self.assertIn("importance", item)
    
    def test_relevant_context_retrieval(self):
        """Test getting relevant context for queries."""
        # Store memories
        self.memory.store("Error handling in Python", memory_type="episodic")
        self.memory.store("Neural network architectures", memory_type="episodic")
        self.memory.store("Python debugging tips", memory_type="episodic")
        
        # Get context for a query
        context = self.memory.get_relevant_context(
            "How to fix Python errors",
            max_tokens_estimate=1000
        )
        
        # Should return relevant context
        self.assertGreater(len(context), 0)
    
    def test_memory_stats(self):
        """Test memory statistics."""
        # Store some memories
        for i in range(5):
            self.memory.store(f"Content {i}", memory_type="episodic")
        
        stats = self.memory.get_memory_stats()
        
        self.assertIn("l0_working_size", stats)
        self.assertIn("l1_episodic_size", stats)
        self.assertIn("l2_semantic_size", stats)
        self.assertEqual(stats["l1_episodic_size"], 5)
    
    def test_export_import(self):
        """Test memory export and import."""
        # Store memories
        for i in range(5):
            self.memory.store(f"Content {i}", memory_type="episodic", tags=["test"])
        
        # Export to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            self.memory.export_memory(temp_path)
            
            # Create new memory system and import
            new_memory = EnhancedMemorySystem()
            new_memory.import_memory(temp_path)
            
            # Check imported data
            self.assertEqual(len(new_memory.l1_episodic), 5)
            
            # Check a specific entry
            entry = list(new_memory.l1_episodic.values())[0]
            self.assertEqual(entry.tags, ["test"])
        finally:
            os.unlink(temp_path)


class TestIntegrationWorkflows(unittest.TestCase):
    """Test integration workflows."""
    
    def test_full_memory_workflow(self):
        """Test complete memory workflow: store → search → retrieve → compress."""
        memory = create_enhanced_memory_system(
            working_capacity=5,
            episodic_capacity=50
        )
        
        # 1. Store working memories
        for i in range(3):
            memory.store(f"Working task {i}", memory_type="working")
        
        # 2. Store episodic experiences
        for i in range(10):
            memory.store(
                f"Experience with machine learning model {i}",
                memory_type="episodic",
                tags=["ml", "experiment"]
            )
        
        # 3. Search for relevant memories
        results = memory.semantic_search("machine learning", top_k=5)
        self.assertGreater(len(results), 0)
        
        # 4. Retrieve specific memory
        if results:
            mem_id = results[0][0].id
            retrieved = memory.retrieve(mem_id)
            self.assertIsNotNone(retrieved)
        
        # 5. Get compressed context
        context = memory.compress_context(max_entries=5)
        self.assertGreater(len(context), 0)
        
        # 6. Check stats
        stats = memory.get_memory_stats()
        self.assertGreater(stats["l1_episodic_size"], 0)
    
    def test_importance_based_retrieval(self):
        """Test that important memories are prioritized."""
        memory = create_enhanced_memory_system()
        
        # Store low importance memory
        low_id = memory.store("Random note", memory_type="episodic")
        
        # Store high importance memory
        high_id = memory.store(
            "Critical breakthrough: solved the alignment problem",
            memory_type="episodic"
        )
        
        # Recompute importance
        memory.l1_episodic[low_id].compute_importance()
        memory.l1_episodic[high_id].compute_importance()
        
        # High importance should be higher
        self.assertGreater(
            memory.l1_episodic[high_id].importance,
            memory.l1_episodic[low_id].importance
        )
    
    def test_tag_based_organization(self):
        """Test memories are properly organized by tags."""
        memory = create_enhanced_memory_system()
        
        # Store with different tags
        memory.store("AI research note", memory_type="episodic", tags=["ai", "research"])
        memory.store("Code snippet", memory_type="episodic", tags=["coding"])
        memory.store("ML experiment", memory_type="episodic", tags=["ai", "ml"])
        
        # Check tag index
        self.assertIn("ai", memory.tag_index)
        self.assertIn("coding", memory.tag_index)
        self.assertEqual(len(memory.tag_index["ai"]), 2)  # Two AI-tagged entries


def run_tests():
    """Run all tests and return results."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestMemoryEntry))
    suite.addTests(loader.loadTestsFromTestCase(TestSimpleEmbeddingModel))
    suite.addTests(loader.loadTestsFromTestCase(TestEnhancedMemorySystem))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationWorkflows))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
