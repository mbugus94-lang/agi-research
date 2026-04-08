"""
Memory system for AGI agents.
Implements working, episodic, and semantic memory.
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
import hashlib
import math
from collections import Counter
import re


@dataclass
class MemoryEntry:
    """A single memory entry."""
    content: str
    memory_type: str  # "working", "episodic", "semantic"
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    
    def to_dict(self) -> Dict:
        return {
            "content": self.content,
            "memory_type": self.memory_type,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "embedding": self.embedding
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MemoryEntry':
        """Create MemoryEntry from dictionary."""
        entry = cls(
            content=data["content"],
            memory_type=data["memory_type"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
            embedding=data.get("embedding")
        )
        return entry


class WorkingMemory:
    """
    Short-term memory holding current context.
    Limited capacity, FIFO eviction.
    """
    
    def __init__(self, capacity: int = 10):
        self.capacity = capacity
        self.entries: List[MemoryEntry] = []
    
    def add(self, content: str, metadata: Dict = None) -> MemoryEntry:
        """Add entry to working memory."""
        entry = MemoryEntry(
            content=content,
            memory_type="working",
            metadata=metadata or {}
        )
        self.entries.append(entry)
        
        # Evict oldest if over capacity
        if len(self.entries) > self.capacity:
            self.entries.pop(0)
        
        return entry
    
    def size(self) -> int:
        """Return current number of entries."""
        return len(self.entries)
    
    def get(self, key: str) -> Optional[Dict]:
        """Get entry by metadata key."""
        for entry in self.entries:
            if entry.metadata.get("id") == key:
                return entry.metadata
        return None
    
    def get_context(self, n: int = None) -> str:
        """Get recent context as formatted string."""
        entries = self.entries[-n:] if n else self.entries
        return "\n".join([e.content for e in entries])
    
    def clear(self):
        """Clear working memory."""
        self.entries = []


class EpisodicMemory:
    """
    Memory of past experiences/episodes.
    Stores agent interactions and their outcomes.
    """
    
    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path
        self.episodes: List[MemoryEntry] = []
        
        if storage_path:
            self._load()
    
    def add_episode(
        self,
        task: str,
        outcome: str,
        lessons: str,
        metadata: Dict = None
    ) -> MemoryEntry:
        """Record a completed episode."""
        content = f"Task: {task}\nOutcome: {outcome}\nLessons: {lessons}"
        entry = MemoryEntry(
            content=content,
            memory_type="episodic",
            metadata=metadata or {}
        )
        self.episodes.append(entry)
        self._save()
        return entry
    
    def store(self, data: Dict[str, Any]) -> MemoryEntry:
        """Store an episode from a dict."""
        return self.add_episode(
            task=data.get("task", "Unknown task"),
            outcome=data.get("output", data.get("outcome", "")),
            lessons=data.get("lessons", ""),
            metadata=data
        )
    
    def get_recent(self, limit: int = 10) -> List[Dict]:
        """Get recent episodes."""
        episodes = self.episodes[-limit:] if limit else self.episodes
        return [e.to_dict() for e in episodes]
    
    def search_by_task(self, task_type: str) -> List[Dict]:
        """Search episodes by task type."""
        results = []
        for episode in self.episodes:
            if task_type.lower() in episode.metadata.get("task", "").lower():
                results.append(episode.to_dict())
        return results
    
    def search(self, query: str, limit: int = 5) -> List[MemoryEntry]:
        """Simple keyword search through episodes."""
        # In production, use embeddings for semantic search
        results = []
        for episode in self.episodes:
            if query.lower() in episode.content.lower():
                results.append(episode)
                if len(results) >= limit:
                    break
        return results
    
    def get_similar_experiences(self, task: str) -> List[MemoryEntry]:
        """Find episodes similar to current task."""
        return self.search(task, limit=3)
    
    def _load(self):
        """Load episodes from storage."""
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                for item in data:
                    entry = MemoryEntry.from_dict(item)
                    self.episodes.append(entry)
        except FileNotFoundError:
            pass
    
    def _save(self):
        """Save episodes to storage."""
        if self.storage_path:
            with open(self.storage_path, 'w') as f:
                json.dump([e.to_dict() for e in self.episodes], f, indent=2)


class SemanticMemory:
    """
    Long-term factual knowledge.
    Key-value store for facts and concepts.
    """
    
    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path
        self.facts: Dict[str, Any] = {}
        
        if storage_path:
            self._load()
    
    def store(self, key: str, value: Any, category: str = "general"):
        """Store a fact."""
        self.facts[key] = {
            "value": value,
            "category": category,
            "timestamp": datetime.now().isoformat()
        }
        self._save()
    
    def store_fact(
        self,
        subject: str,
        predicate: str,
        object_: str,
        confidence: float = 1.0
    ):
        """Store a semantic fact as subject-predicate-object."""
        key = f"{subject}_{predicate}"
        self.facts[key] = {
            "subject": subject,
            "predicate": predicate,
            "object": object_,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        }
        self._save()
    
    def query(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None
    ) -> List[Dict]:
        """Query facts by subject and/or predicate."""
        results = []
        for key, fact in self.facts.items():
            match = True
            if subject and fact.get("subject") != subject:
                match = False
            if predicate and fact.get("predicate") != predicate:
                match = False
            if match:
                results.append(fact)
        return results
    
    def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve a fact."""
        fact = self.facts.get(key)
        return fact["value"] if fact else None
    
    def search_by_category(self, category: str) -> Dict[str, Any]:
        """Get all facts in a category."""
        return {
            k: v["value"] for k, v in self.facts.items()
            if v.get("category") == category
        }
    
    def _load(self):
        """Load facts from storage."""
        try:
            with open(self.storage_path, 'r') as f:
                self.facts = json.load(f)
        except FileNotFoundError:
            pass
    
    def _save(self):
        """Save facts to storage."""
        if self.storage_path:
            with open(self.storage_path, 'w') as f:
                json.dump(self.facts, f, indent=2)


class VectorMemory:
    """
    Semantic memory with vector-based search.
    Implements simplified TF-IDF style embeddings for semantic retrieval.
    
    Based on OpenViking pattern: context database with unified memory management.
    """
    
    def __init__(self, storage_path: str = None, embedding_dim: int = 100):
        self.storage_path = storage_path
        self.embedding_dim = embedding_dim
        self.entries: List[MemoryEntry] = []
        self.vocabulary: Dict[str, int] = {}  # word -> index mapping
        self.idf_scores: Dict[str, float] = {}  # word -> IDF score
        
        if storage_path:
            self._load()
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization."""
        # Lowercase, remove punctuation, split
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        tokens = [w for w in text.split() if len(w) > 2]
        return tokens
    
    def _compute_embedding(self, text: str) -> List[float]:
        """Compute TF-IDF style embedding vector."""
        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * self.embedding_dim
        
        # Update vocabulary
        for token in set(tokens):
            if token not in self.vocabulary:
                idx = len(self.vocabulary)
                if idx < self.embedding_dim:
                    self.vocabulary[token] = idx
        
        # Compute TF-IDF
        vector = [0.0] * self.embedding_dim
        token_counts = Counter(tokens)
        
        for token, count in token_counts.items():
            if token in self.vocabulary:
                idx = self.vocabulary[token]
                tf = count / len(tokens)
                idf = self.idf_scores.get(token, 1.0)
                vector[idx] = tf * idf
        
        # Normalize
        norm = math.sqrt(sum(x*x for x in vector))
        if norm > 0:
            vector = [x / norm for x in vector]
        
        return vector
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def add(self, content: str, metadata: Dict = None) -> MemoryEntry:
        """Add entry with auto-generated embedding."""
        embedding = self._compute_embedding(content)
        entry = MemoryEntry(
            content=content,
            memory_type="semantic",
            metadata=metadata or {},
            embedding=embedding
        )
        self.entries.append(entry)
        self._update_idf()
        
        if self.storage_path:
            self._save()
        
        return entry
    
    def _update_idf(self):
        """Update IDF scores based on current corpus."""
        if not self.entries:
            return
        
        # Count document frequency for each token
        doc_freq = Counter()
        for entry in self.entries:
            tokens = set(self._tokenize(entry.content))
            for token in tokens:
                doc_freq[token] += 1
        
        # Compute IDF
        N = len(self.entries)
        self.idf_scores = {
            token: math.log(N / (freq + 1)) + 1
            for token, freq in doc_freq.items()
        }
    
    def semantic_search(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.1
    ) -> List[Tuple[MemoryEntry, float]]:
        """
        Search entries by semantic similarity.
        
        Returns list of (entry, similarity_score) tuples ranked by similarity.
        """
        query_embedding = self._compute_embedding(query)
        
        results = []
        for entry in self.entries:
            if entry.embedding:
                similarity = self._cosine_similarity(query_embedding, entry.embedding)
                if similarity >= min_similarity:
                    results.append((entry, similarity))
        
        # Sort by similarity (descending)
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        keyword_weight: float = 0.3,
        semantic_weight: float = 0.7
    ) -> List[Tuple[MemoryEntry, float]]:
        """
        Combined keyword and semantic search.
        
        Balances exact matching with semantic understanding.
        """
        query_lower = query.lower()
        
        # Keyword scores
        keyword_scores = {}
        for i, entry in enumerate(self.entries):
            content_lower = entry.content.lower()
            # Simple keyword matching score
            matches = sum(1 for word in query_lower.split() if word in content_lower)
            keyword_scores[i] = matches / max(len(query_lower.split()), 1)
        
        # Semantic scores
        semantic_results = self.semantic_search(query, top_k=len(self.entries))
        semantic_scores = {self.entries.index(entry): score for entry, score in semantic_results}
        
        # Combine scores
        combined_scores = {}
        for i in range(len(self.entries)):
            kw_score = keyword_scores.get(i, 0)
            sem_score = semantic_scores.get(i, 0)
            combined = keyword_weight * kw_score + semantic_weight * sem_score
            if combined > 0:
                combined_scores[i] = combined
        
        # Get top results
        top_indices = sorted(combined_scores.keys(), key=lambda i: combined_scores[i], reverse=True)[:top_k]
        results = [(self.entries[i], combined_scores[i]) for i in top_indices]
        
        return results
    
    def get_by_metadata(self, key: str, value: Any) -> List[MemoryEntry]:
        """Find entries by metadata field."""
        return [e for e in self.entries if e.metadata.get(key) == value]
    
    def get_context_for_task(self, task: str, n: int = 3) -> str:
        """Get relevant context for a task."""
        results = self.hybrid_search(task, top_k=n)
        if not results:
            return ""
        
        parts = ["=== Relevant Context ==="]
        for entry, score in results:
            parts.append(f"[Similarity: {score:.2f}] {entry.content[:200]}...")
        
        return "\n".join(parts)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            "total_entries": len(self.entries),
            "vocabulary_size": len(self.vocabulary),
            "embedding_dimension": self.embedding_dim,
            "storage_path": self.storage_path
        }
    
    def _save(self):
        """Save to disk."""
        data = {
            "entries": [e.to_dict() for e in self.entries],
            "vocabulary": self.vocabulary,
            "idf_scores": self.idf_scores,
            "embedding_dim": self.embedding_dim
        }
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load(self):
        """Load from disk."""
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                self.entries = [MemoryEntry.from_dict(e) for e in data.get("entries", [])]
                self.vocabulary = data.get("vocabulary", {})
                self.idf_scores = data.get("idf_scores", {})
                self.embedding_dim = data.get("embedding_dim", self.embedding_dim)
        except FileNotFoundError:
            pass


class MemorySystem:
    """
    Unified memory system combining all memory types.
    """
    
    def __init__(self, storage_dir: str = None):
        self.working = WorkingMemory(capacity=10)
        self.episodic = EpisodicMemory(
            storage_path=f"{storage_dir}/episodes.json" if storage_dir else None
        )
        self.semantic = SemanticMemory(
            storage_path=f"{storage_dir}/facts.json" if storage_dir else None
        )
        self.vector = VectorMemory(
            storage_path=f"{storage_dir}/vector_memory.json" if storage_dir else None
        )
    
    def add_to_context(self, content: str, metadata: Dict = None):
        """Add to working memory."""
        return self.working.add(content, metadata)
    
    def get_context(self, n: int = 5) -> str:
        """Get current context."""
        return self.working.get_context(n)
    
    def record_episode(self, task: str, outcome: str, lessons: str = ""):
        """Record a completed task."""
        return self.episodic.add_episode(task, outcome, lessons)
    
    def recall_similar(self, task: str) -> List[str]:
        """Recall similar past experiences."""
        episodes = self.episodic.get_similar_experiences(task)
        return [e.content for e in episodes]
    
    def learn_fact(self, key: str, value: Any, category: str = "general"):
        """Learn a new fact."""
        self.semantic.store(key, value, category)
    
    def recall_fact(self, key: str) -> Optional[Any]:
        """Recall a learned fact."""
        return self.semantic.retrieve(key)
    
    def semantic_search(self, query: str, top_k: int = 5) -> List[Tuple[MemoryEntry, float]]:
        """Perform semantic search across vector memory."""
        return self.vector.hybrid_search(query, top_k=top_k)
    
    def get_full_context(self, task: str) -> str:
        """Build comprehensive context for a task."""
        parts = []
        
        # Working memory
        parts.append("=== Current Context ===")
        parts.append(self.working.get_context())
        
        # Similar experiences
        similar = self.episodic.get_similar_experiences(task)
        if similar:
            parts.append("\n=== Relevant Past Experiences ===")
            for ep in similar[:2]:
                parts.append(ep.content)
        
        # Semantic search results (new!)
        sem_results = self.vector.hybrid_search(task, top_k=3)
        if sem_results:
            parts.append("\n=== Semantically Relevant Knowledge ===")
            for entry, score in sem_results:
                parts.append(f"[{score:.2f}] {entry.content[:150]}...")
        
        # Relevant facts (heuristic: check if task keywords match)
        parts.append("\n=== Known Facts ===")
        for key, data in self.semantic.facts.items():
            if any(word in task.lower() for word in key.lower().split()):
                parts.append(f"{key}: {data['value']}")
        
        return "\n".join(parts)
    
    def clear_working_memory(self):
        """Clear short-term context."""
        self.working.clear()


if __name__ == "__main__":
    # Demo
    import tempfile
    import os
    
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = MemorySystem(storage_dir=tmpdir)
        
        # Add working memory
        memory.add_to_context("User asked: What is the capital of France?")
        memory.add_to_context("I should search for this information.")
        
        # Learn a fact
        memory.learn_fact("capital_france", "Paris", category="geography")
        memory.learn_fact("capital_germany", "Berlin", category="geography")
        
        # Record an episode
        memory.record_episode(
            task="Find capital of Spain",
            outcome="Successfully found Madrid",
            lessons="Always verify with multiple sources"
        )
        
        # Add to vector memory (semantic search)
        memory.vector.add("Paris is the capital and most populous city of France.", {"topic": "geography"})
        memory.vector.add("Berlin is the capital of Germany with a rich history.", {"topic": "geography"})
        memory.vector.add("Tokyo is Japan's capital and largest metropolis.", {"topic": "geography"})
        
        # Test semantic search
        print("=== Testing Semantic Search ===")
        results = memory.semantic_search("What is the capital city of France?", top_k=3)
        for entry, score in results:
            print(f"[Score: {score:.3f}] {entry.content}")
        
        print("\n" + "="*50)
        print(memory.get_full_context("What is the capital of France?"))