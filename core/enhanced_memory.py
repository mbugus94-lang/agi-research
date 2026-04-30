"""
Enhanced Memory System with Vector Search and Automatic Consolidation

Addresses the key AGI gap identified in research (arXiv 2510.18212):
- Current AI models show "jagged" cognitive profiles with major deficits in 
  long-term memory storage
- This system implements: vector-based semantic retrieval, memory consolidation,
  and context compression

Based on:
- DeepSeek V4's Hybrid Attention Architecture for long conversation memory
- OpenViking's tiered context database (L0/L1/L2) with 60-80% token reduction
- Ouroboros' persistent identity patterns
"""

import json
import uuid
import hashlib
import numpy as np
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Callable
from collections import deque, defaultdict
import heapq


@dataclass
class MemoryEntry:
    """Enhanced memory entry with embedding support and importance scoring."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: Any = None
    memory_type: str = "episodic"  # working, episodic, semantic, procedural
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: List[str] = field(default_factory=list)
    importance: float = 0.5  # 0-1 scale
    access_count: int = 0
    last_accessed: Optional[str] = None
    embedding: Optional[np.ndarray] = field(default=None, repr=False)
    embedding_hash: Optional[str] = None  # For cache validation
    source_ids: List[str] = field(default_factory=list)  # For consolidated memories
    consolidation_level: int = 0  # 0=raw, 1=consolidated, 2=abstracted
    
    def to_dict(self) -> Dict:
        """Serialize to dict, handling numpy arrays."""
        data = asdict(self)
        if self.embedding is not None:
            data['embedding'] = self.embedding.tolist()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> "MemoryEntry":
        """Deserialize from dict."""
        if 'embedding' in data and data['embedding'] is not None:
            data['embedding'] = np.array(data['embedding'])
        return cls(**data)
    
    def compute_importance(self, content_analyzer: Optional[Callable] = None) -> float:
        """Compute importance score based on content and metadata."""
        base_score = 0.3
        
        # Length factor (longer content often more important)
        content_str = str(self.content)
        if len(content_str) > 100:
            base_score += min(0.1, len(content_str) / 10000)
        
        # Access pattern (frequently accessed = more important)
        if self.access_count > 0:
            base_score += min(0.2, self.access_count / 50)
        
        # Recency boost
        try:
            age_days = (datetime.now() - datetime.fromisoformat(self.timestamp)).days
            if age_days < 7:
                base_score += 0.1
            elif age_days < 30:
                base_score += 0.05
        except:
            pass
        
        # Keyword-based importance
        important_keywords = [
            'error', 'failure', 'success', 'breakthrough', 'critical',
            'solution', 'lesson', 'insight', 'decision', 'goal'
        ]
        content_lower = content_str.lower()
        keyword_hits = sum(1 for kw in important_keywords if kw in content_lower)
        base_score += min(0.3, keyword_hits * 0.05)
        
        self.importance = min(1.0, base_score)
        return self.importance


class SimpleEmbeddingModel:
    """Simple embedding model using TF-IDF-like approach (no external deps)."""
    
    def __init__(self, embedding_dim: int = 128):
        self.embedding_dim = embedding_dim
        self.vocab = {}
        self.vocab_built = False
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization."""
        # Lowercase and split on non-alphanumeric
        import re
        return re.findall(r'\b[a-z]+\b', text.lower())
    
    def _build_vocab(self, texts: List[str]):
        """Build vocabulary from corpus."""
        word_freq = defaultdict(int)
        for text in texts:
            for token in self._tokenize(text):
                word_freq[token] += 1
        
        # Take top embedding_dim most frequent words
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        self.vocab = {word: i for i, (word, _) in enumerate(sorted_words[:self.embedding_dim])}
        self.vocab_built = True
    
    def embed(self, text: str) -> np.ndarray:
        """Create embedding vector for text."""
        tokens = self._tokenize(text)
        embedding = np.zeros(self.embedding_dim)
        
        for token in tokens:
            if token in self.vocab:
                embedding[self.vocab[token]] += 1
        
        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = embedding / norm
        
        return embedding


class EnhancedMemorySystem:
    """
    Enhanced memory system with:
    - Vector-based semantic search
    - Automatic memory consolidation
    - Tiered storage (L0=working, L1=episodic, L2=semantic)
    - Context compression
    """
    
    def __init__(self,
                 l0_capacity: int = 10,      # Working memory
                 l1_capacity: int = 1000,     # Episodic memory  
                 l2_capacity: int = 500,      # Semantic memory
                 embedding_dim: int = 128,
                 consolidation_threshold: int = 50):
        
        # Tiered memory stores
        self.l0_working: deque = deque(maxlen=l0_capacity)  # L0: Immediate context
        self.l1_episodic: Dict[str, MemoryEntry] = {}       # L1: Experiences
        self.l2_semantic: Dict[str, MemoryEntry] = {}       # L2: Abstracted knowledge
        self.procedural: Dict[str, MemoryEntry] = {}        # Skills/how-to
        
        # Configuration
        self.l0_capacity = l0_capacity
        self.l1_capacity = l1_capacity
        self.l2_capacity = l2_capacity
        self.consolidation_threshold = consolidation_threshold
        
        # Embedding model
        self.embedder = SimpleEmbeddingModel(embedding_dim)
        self.embedding_dim = embedding_dim
        
        # Indexes
        self.tag_index: Dict[str, List[str]] = defaultdict(list)
        self.time_index: List[Tuple[str, str]] = []  # (timestamp, entry_id)
        
        # Consolidation tracking
        self.consolidation_counter = 0
        
    def store(self, content: Any,
              memory_type: str = "episodic",
              tags: Optional[List[str]] = None,
              compute_embedding: bool = True) -> str:
        """Store a new memory entry with optional embedding."""
        
        entry = MemoryEntry(
            content=content,
            memory_type=memory_type,
            tags=tags or []
        )
        
        # Compute importance
        entry.compute_importance()
        
        # Compute embedding if requested
        if compute_embedding:
            content_str = str(content)
            entry.embedding = self.embedder.embed(content_str)
            entry.embedding_hash = hashlib.md5(content_str.encode()).hexdigest()[:16]
        
        # Store in appropriate tier
        if memory_type == "working":
            self.l0_working.append(entry)
        elif memory_type == "episodic":
            if len(self.l1_episodic) >= self.l1_capacity:
                self._evict_l1()
            self.l1_episodic[entry.id] = entry
        elif memory_type == "semantic":
            if len(self.l2_semantic) >= self.l2_capacity:
                self._evict_l2()
            self.l2_semantic[entry.id] = entry
        elif memory_type == "procedural":
            self.procedural[entry.id] = entry
        
        # Update indexes
        for tag in entry.tags:
            self.tag_index[tag].append(entry.id)
        self.time_index.append((entry.timestamp, entry.id))
        
        # Trigger consolidation check
        self.consolidation_counter += 1
        if self.consolidation_counter >= self.consolidation_threshold:
            self._run_consolidation()
            self.consolidation_counter = 0
        
        return entry.id
    
    def _evict_l1(self) -> None:
        """Evict least important entry from L1."""
        if not self.l1_episodic:
            return
        
        # Find least important, least recently accessed entry
        def eviction_score(entry):
            age_days = 0
            try:
                age_days = (datetime.now() - datetime.fromisoformat(entry.timestamp)).days
            except:
                pass
            return (entry.importance * 0.5 + 
                   (1.0 / (1 + entry.access_count)) * 0.3 + 
                   (1.0 / (1 + age_days)) * 0.2)
        
        victim = min(self.l1_episodic.values(), key=eviction_score)
        del self.l1_episodic[victim.id]
    
    def _evict_l2(self) -> None:
        """Evict least important entry from L2."""
        if not self.l2_semantic:
            return
        
        victim = min(self.l2_semantic.values(), key=lambda e: e.importance)
        del self.l2_semantic[victim.id]
    
    def semantic_search(self, query: str, 
                        memory_type: Optional[str] = None,
                        top_k: int = 5) -> List[Tuple[MemoryEntry, float]]:
        """Search memories by semantic similarity."""
        
        query_embedding = self.embedder.embed(query)
        results = []
        
        # Collect candidate memories
        candidates = []
        if memory_type is None or memory_type == "working":
            candidates.extend(self.l0_working)
        if memory_type is None or memory_type == "episodic":
            candidates.extend(self.l1_episodic.values())
        if memory_type is None or memory_type == "semantic":
            candidates.extend(self.l2_semantic.values())
        if memory_type is None or memory_type == "procedural":
            candidates.extend(self.procedural.values())
        
        # Compute similarities
        for entry in candidates:
            if entry.embedding is not None:
                similarity = np.dot(query_embedding, entry.embedding)
                results.append((entry, float(similarity)))
        
        # Sort by similarity and return top-k
        results.sort(key=lambda x: x[1], reverse=True)
        
        # Update access counts
        for entry, _ in results[:top_k]:
            entry.access_count += 1
            entry.last_accessed = datetime.now().isoformat()
        
        return results[:top_k]
    
    def retrieve(self, memory_id: str) -> Optional[MemoryEntry]:
        """Retrieve a memory by ID from any tier."""
        
        # Check L0
        for entry in self.l0_working:
            if entry.id == memory_id:
                entry.access_count += 1
                entry.last_accessed = datetime.now().isoformat()
                return entry
        
        # Check L1, L2, procedural
        entry = (self.l1_episodic.get(memory_id) or 
                self.l2_semantic.get(memory_id) or
                self.procedural.get(memory_id))
        
        if entry:
            entry.access_count += 1
            entry.last_accessed = datetime.now().isoformat()
        
        return entry
    
    def _run_consolidation(self) -> None:
        """
        Consolidate memories: compress working → episodic → semantic.
        Based on memory consolidation theory - important patterns get abstracted.
        """
        
        # Consolidate working memory to episodic
        if len(self.l0_working) >= self.l0_capacity // 2:
            self._consolidate_working_to_episodic()
        
        # Consolidate episodic to semantic (find patterns)
        if len(self.l1_episodic) >= self.l1_capacity // 2:
            self._consolidate_episodic_to_semantic()
    
    def _consolidate_working_to_episodic(self) -> None:
        """Move important working memories to episodic storage."""
        
        for entry in list(self.l0_working):
            if entry.importance >= 0.6 or entry.access_count >= 2:
                # Move to episodic
                entry.memory_type = "episodic"
                if len(self.l1_episodic) >= self.l1_capacity:
                    self._evict_l1()
                self.l1_episodic[entry.id] = entry
    
    def _consolidate_episodic_to_semantic(self) -> None:
        """Abstract patterns from episodic memories to semantic knowledge."""
        
        # Group episodic memories by tags
        tag_groups = defaultdict(list)
        for entry in self.l1_episodic.values():
            if entry.access_count >= 3:  # Frequently accessed = pattern
                for tag in entry.tags:
                    tag_groups[tag].append(entry)
        
        # Create semantic abstractions for groups with many entries
        for tag, entries in tag_groups.items():
            if len(entries) >= 5:
                # Create abstracted semantic memory
                abstraction = self._create_abstraction(entries, tag)
                if abstraction:
                    self.l2_semantic[abstraction.id] = abstraction
    
    def _create_abstraction(self, entries: List[MemoryEntry], 
                            tag: str) -> Optional[MemoryEntry]:
        """Create an abstracted semantic memory from episodic entries."""
        
        if not entries:
            return None
        
        # Extract common patterns (simplified)
        contents = [str(e.content) for e in entries]
        
        # Create summary content
        abstraction_content = {
            "type": "semantic_abstraction",
            "source_count": len(entries),
            "tag": tag,
            "pattern_summary": f"Pattern from {len(entries)} experiences tagged '{tag}'",
            "example_sources": [e.id for e in entries[:3]]
        }
        
        abstraction = MemoryEntry(
            content=abstraction_content,
            memory_type="semantic",
            tags=[tag, "auto_abstracted"],
            source_ids=[e.id for e in entries],
            consolidation_level=2,
            importance=0.8  # Abstracted knowledge is important
        )
        
        # Compute embedding for the abstraction
        content_str = json.dumps(abstraction_content)
        abstraction.embedding = self.embedder.embed(content_str)
        
        return abstraction
    
    def compress_context(self, max_entries: int = 5) -> List[Dict]:
        """
        Compress working memory context for LLM prompts.
        Returns most relevant recent entries.
        """
        
        # Get all working memory entries sorted by importance and recency
        entries = list(self.l0_working)
        entries.sort(key=lambda e: (e.importance, e.timestamp), reverse=True)
        
        # Take top entries
        compressed = []
        for entry in entries[:max_entries]:
            compressed.append({
                "id": entry.id,
                "content": entry.content,
                "type": entry.memory_type,
                "importance": entry.importance,
                "timestamp": entry.timestamp
            })
        
        return compressed
    
    def get_relevant_context(self, query: str, 
                             max_tokens_estimate: int = 2000) -> List[Dict]:
        """
        Get relevant context for a query, estimating token budget.
        Combines semantic search with working memory.
        """
        
        context = []
        total_chars = 0
        
        # Always include working memory first
        for entry in self.l0_working:
            entry_str = str(entry.content)
            if total_chars + len(entry_str) < max_tokens_estimate * 4:  # ~4 chars/token
                context.append({
                    "source": "working",
                    "content": entry.content,
                    "relevance": 1.0
                })
                total_chars += len(entry_str)
        
        # Add semantically similar memories
        semantic_results = self.semantic_search(query, top_k=5)
        for entry, similarity in semantic_results:
            if similarity < 0.5:  # Skip low relevance
                continue
            entry_str = str(entry.content)
            if total_chars + len(entry_str) < max_tokens_estimate * 4:
                context.append({
                    "source": entry.memory_type,
                    "content": entry.content,
                    "relevance": similarity
                })
                total_chars += len(entry_str)
        
        return context
    
    def get_memory_stats(self) -> Dict:
        """Get statistics about memory system state."""
        
        total_accesses = sum(
            e.access_count for e in list(self.l0_working) +
            list(self.l1_episodic.values()) +
            list(self.l2_semantic.values()) +
            list(self.procedural.values())
        )
        
        return {
            "l0_working_size": len(self.l0_working),
            "l0_capacity": self.l0_capacity,
            "l1_episodic_size": len(self.l1_episodic),
            "l1_capacity": self.l1_capacity,
            "l2_semantic_size": len(self.l2_semantic),
            "l2_capacity": self.l2_capacity,
            "procedural_size": len(self.procedural),
            "total_accesses": total_accesses,
            "tag_count": len(self.tag_index),
            "consolidation_counter": self.consolidation_counter
        }
    
    def export_memory(self, filepath: str) -> None:
        """Export all memories to JSON file."""
        
        data = {
            "l0_working": [e.to_dict() for e in self.l0_working],
            "l1_episodic": {k: v.to_dict() for k, v in self.l1_episodic.items()},
            "l2_semantic": {k: v.to_dict() for k, v in self.l2_semantic.items()},
            "procedural": {k: v.to_dict() for k, v in self.procedural.items()},
            "stats": self.get_memory_stats()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def import_memory(self, filepath: str) -> None:
        """Import memories from JSON file."""
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        self.l0_working = deque(
            [MemoryEntry.from_dict(e) for e in data.get("l0_working", [])],
            maxlen=self.l0_capacity
        )
        self.l1_episodic = {
            k: MemoryEntry.from_dict(v) for k, v in data.get("l1_episodic", {}).items()
        }
        self.l2_semantic = {
            k: MemoryEntry.from_dict(v) for k, v in data.get("l2_semantic", {}).items()
        }
        self.procedural = {
            k: MemoryEntry.from_dict(v) for k, v in data.get("procedural", {}).items()
        }


# Factory function for quick setup
def create_enhanced_memory_system(
    working_capacity: int = 10,
    episodic_capacity: int = 1000,
    semantic_capacity: int = 500
) -> EnhancedMemorySystem:
    """Create an enhanced memory system with reasonable defaults."""
    return EnhancedMemorySystem(
        l0_capacity=working_capacity,
        l1_capacity=episodic_capacity,
        l2_capacity=semantic_capacity
    )
