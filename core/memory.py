"""
Memory system for AGI agents.
Implements working, episodic, and semantic memory.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import hashlib


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
            "metadata": self.metadata
        }


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
                    entry = MemoryEntry(
                        content=item["content"],
                        memory_type=item["memory_type"],
                        timestamp=datetime.fromisoformat(item["timestamp"]),
                        metadata=item.get("metadata", {})
                    )
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
        
        # Get full context
        print(memory.get_full_context("What is the capital of France?"))
