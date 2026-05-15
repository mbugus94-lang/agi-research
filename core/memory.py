"""
Memory Systems Implementation

Three-tier memory architecture:
- Working Memory: Short-term, active context
- Episodic Memory: Experiences and interactions
- Semantic Memory: Facts and learned knowledge

References:
- Personalized AGI via Neuroscience-Inspired Learning (arXiv:2504.20109v1)
- Tri-Memory Continual Learning system
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json
import hashlib
from collections import deque


@dataclass
class MemoryEntry:
    """Base memory entry"""
    id: str
    content: Any
    timestamp: float
    memory_type: str  # "working", "episodic", "semantic"
    metadata: Dict[str, Any] = field(default_factory=dict)
    importance: float = 0.5  # 0.0 to 1.0
    access_count: int = 0
    last_accessed: float = 0.0


class WorkingMemory:
    """
    Short-term memory for active context.
    
    Limited capacity, fast access.
    Inspired by cognitive working memory (4±1 chunks).
    """
    
    def __init__(self, capacity: int = 7):
        self.capacity = capacity
        self.entries: deque = deque(maxlen=capacity)
        self.context: Dict[str, Any] = {}
        
    def store(self, key: str, value: Any) -> None:
        """Store in working context."""
        self.context[key] = {
            "value": value,
            "timestamp": datetime.now().timestamp()
        }
    
    def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve from working context."""
        if key in self.context:
            entry = self.context[key]
            entry["timestamp"] = datetime.now().timestamp()  # Update access time
            return entry["value"]
        return None
    
    def add_entry(self, entry: MemoryEntry) -> None:
        """Add entry to working memory buffer.
        
        When capacity is exceeded, oldest entries (left side) are evicted.
        """
        entry.memory_type = "working"
        # Append to right side; oldest entries on left will be evicted if needed
        self.entries.append(entry)
    
    def get_recent(self, n: int = 5) -> List[MemoryEntry]:
        """Get n most recent entries.
        
        Most recent entries are on the right side of deque.
        """
        # Get last n items from the right side (most recent)
        return list(self.entries)[-n:] if len(self.entries) >= n else list(self.entries)
    
    def clear(self) -> None:
        """Clear working memory (e.g., between tasks)."""
        self.entries.clear()
        self.context.clear()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "capacity": self.capacity,
            "current_size": len(self.entries),
            "context_keys": list(self.context.keys())
        }


class EpisodicMemory:
    """
    Memory of experiences and interactions.
    
    Stores episodes (experiences) with temporal indexing.
    Implements importance-based retention and retrieval.
    """
    
    def __init__(self, max_entries: int = 1000):
        self.max_entries = max_entries
        self.episodes: List[MemoryEntry] = []
        self.index: Dict[str, List[str]] = {}  # Tag -> entry IDs
        
    def store_episode(
        self,
        content: Any,
        tags: Optional[List[str]] = None,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryEntry:
        """
        Store a new episode.
        
        Args:
            content: The experience content
            tags: Categorization tags
            importance: 0.0 to 1.0 retention priority
            metadata: Additional context
        """
        entry_id = hashlib.md5(
            f"{content}{datetime.now().timestamp()}".encode()
        ).hexdigest()[:12]
        
        entry = MemoryEntry(
            id=entry_id,
            content=content,
            timestamp=datetime.now().timestamp(),
            memory_type="episodic",
            metadata=metadata or {},
            importance=importance,
            last_accessed=datetime.now().timestamp()
        )
        
        # Add tags
        if tags:
            for tag in tags:
                if tag not in self.index:
                    self.index[tag] = []
                self.index[tag].append(entry_id)
        
        self.episodes.append(entry)
        
        # Prune if exceeding capacity
        if len(self.episodes) > self.max_entries:
            self._prune()
        
        return entry
    
    def retrieve_similar(
        self,
        context: Dict[str, Any],
        limit: int = 5
    ) -> List[MemoryEntry]:
        """
        Retrieve episodes similar to current context.
        
        Simple implementation: match tags and recency.
        Future: vector similarity search
        """
        # Score episodes by relevance
        scored = []
        for entry in self.episodes:
            score = self._calculate_relevance(entry, context)
            scored.append((score, entry))
        
        # Sort by score and return top results
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [entry for _, entry in scored[:limit]]
        
        # Update access metadata
        for entry in results:
            entry.access_count += 1
            entry.last_accessed = datetime.now().timestamp()
        
        return results
    
    def retrieve_by_tag(self, tag: str, limit: int = 10) -> List[MemoryEntry]:
        """Retrieve episodes by tag."""
        entry_ids = self.index.get(tag, [])
        entries = [e for e in self.episodes if e.id in entry_ids]
        return entries[-limit:]  # Most recent
    
    def _calculate_relevance(
        self,
        entry: MemoryEntry,
        context: Dict[str, Any]
    ) -> float:
        """Calculate relevance score for an episode."""
        score = 0.0
        
        # Importance factor
        score += entry.importance * 0.3
        
        # Recency factor (exponential decay)
        age_hours = (datetime.now().timestamp() - entry.timestamp) / 3600
        recency = max(0, 1 - (age_hours / 168))  # Decay over 1 week
        score += recency * 0.3
        
        # Tag matching
        context_tags = context.get("tags", [])
        entry_tags = set()
        for tag, ids in self.index.items():
            if entry.id in ids:
                entry_tags.add(tag)
        
        tag_overlap = len(set(context_tags) & entry_tags)
        score += (tag_overlap / max(len(context_tags), 1)) * 0.4
        
        return score
    
    def _prune(self) -> None:
        """Remove least important episodes when at capacity."""
        # Sort by importance × recency
        now = datetime.now().timestamp()
        
        def retention_priority(entry: MemoryEntry) -> float:
            age = now - entry.timestamp
            return entry.importance * max(0, 1 - age / (7 * 24 * 3600))
        
        self.episodes.sort(key=retention_priority)
        # Remove bottom 10%
        remove_count = max(1, len(self.episodes) // 10)
        removed = self.episodes[:remove_count]
        self.episodes = self.episodes[remove_count:]
        
        # Clean up index
        removed_ids = {e.id for e in removed}
        for tag in list(self.index.keys()):
            self.index[tag] = [id for id in self.index[tag] if id not in removed_ids]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_entries": self.max_entries,
            "current_entries": len(self.episodes),
            "tag_count": len(self.index),
            "avg_importance": sum(e.importance for e in self.episodes) / max(len(self.episodes), 1)
        }


class SemanticMemory:
    """
    Memory for facts, concepts, and learned knowledge.
    
    Structured knowledge storage with categorization.
    """
    
    def __init__(self):
        self.facts: Dict[str, Dict[str, Any]] = {}  # Key -> fact data
        self.concepts: Dict[str, Dict[str, Any]] = {}  # Concept definitions
        self.procedures: Dict[str, Dict[str, Any]] = {}  # How-to knowledge
        
    def store_fact(
        self,
        key: str,
        value: Any,
        category: str = "general",
        confidence: float = 1.0
    ) -> None:
        """Store a factual piece of knowledge."""
        self.facts[key] = {
            "value": value,
            "category": category,
            "confidence": confidence,
            "timestamp": datetime.now().timestamp(),
            "access_count": 0
        }
    
    def retrieve_fact(self, key: str) -> Optional[Any]:
        """Retrieve a fact by key."""
        if key in self.facts:
            self.facts[key]["access_count"] += 1
            return self.facts[key]["value"]
        return None
    
    def store_concept(
        self,
        name: str,
        definition: str,
        attributes: Optional[Dict[str, Any]] = None,
        relations: Optional[List[str]] = None
    ) -> None:
        """Store a concept definition."""
        self.concepts[name] = {
            "definition": definition,
            "attributes": attributes or {},
            "relations": relations or [],
            "timestamp": datetime.now().timestamp()
        }
    
    def retrieve_concept(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieve a concept by name."""
        return self.concepts.get(name)
    
    def store_procedure(
        self,
        name: str,
        steps: List[str],
        preconditions: Optional[List[str]] = None,
        postconditions: Optional[List[str]] = None
    ) -> None:
        """Store a procedural skill."""
        self.procedures[name] = {
            "steps": steps,
            "preconditions": preconditions or [],
            "postconditions": postconditions or [],
            "timestamp": datetime.now().timestamp()
        }
    
    def retrieve_procedure(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieve a procedure by name."""
        return self.procedures.get(name)
    
    def search_facts(self, query: str) -> List[Tuple[str, Any]]:
        """Search facts by partial key match."""
        results = []
        query_lower = query.lower()
        for key, data in self.facts.items():
            if query_lower in key.lower():
                results.append((key, data["value"]))
        return results
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "fact_count": len(self.facts),
            "concept_count": len(self.concepts),
            "procedure_count": len(self.procedures)
        }


class MemorySystem:
    """
    Unified memory system combining three tiers.
    
    Based on neuroscience-inspired Tri-Memory Continual Learning:
    - Fast learning (working memory)
    - Consolidation (episodic → semantic)
    - Long-term retention (semantic)
    """
    
    def __init__(
        self,
        working_capacity: int = 7,
        episodic_capacity: int = 1000
    ):
        self.working = WorkingMemory(capacity=working_capacity)
        self.episodic = EpisodicMemory(max_entries=episodic_capacity)
        self.semantic = SemanticMemory()
        
    def store_working(self, key: str, value: Any) -> None:
        """Store in working memory."""
        self.working.store(key, value)
    
    def retrieve_working(self, key: str) -> Optional[Any]:
        """Retrieve from working memory."""
        return self.working.retrieve(key)
    
    def store_episode(
        self,
        content: Any,
        tags: Optional[List[str]] = None,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> MemoryEntry:
        """Store an episodic memory."""
        return self.episodic.store_episode(content, tags, importance, metadata)
    
    def retrieve_episodes(
        self,
        context: Dict[str, Any],
        limit: int = 5
    ) -> List[MemoryEntry]:
        """Retrieve relevant episodic memories."""
        return self.episodic.retrieve_similar(context, limit)
    
    def store_fact(
        self,
        key: str,
        value: Any,
        category: str = "general",
        confidence: float = 1.0
    ) -> None:
        """Store a fact in semantic memory."""
        self.semantic.store_fact(key, value, category, confidence)
    
    def retrieve_fact(self, key: str) -> Optional[Any]:
        """Retrieve a fact."""
        return self.semantic.retrieve_fact(key)
    
    def consolidate(self) -> int:
        """
        Consolidate episodic memories into semantic knowledge.
        
        High-importance, frequently accessed episodes become facts.
        Returns number of consolidated entries.
        """
        consolidated = 0
        threshold_importance = 0.8
        threshold_access = 3
        
        for episode in self.episodic.episodes:
            if (episode.importance >= threshold_importance and 
                episode.access_count >= threshold_access):
                
                # Create fact key from content summary
                content_str = str(episode.content)
                key = f"learned_{episode.id}"
                
                self.semantic.store_fact(
                    key=key,
                    value=episode.content,
                    category="consolidated",
                    confidence=min(1.0, episode.importance)
                )
                consolidated += 1
        
        return consolidated
    
    def get_context_for_task(self, task: str, tags: Optional[List[str]] = None) -> Dict[str, Any]:
        """Gather relevant context for a task from all memory tiers."""
        context = {
            "working": {},
            "episodic": [],
            "semantic": {},
            "task": task
        }
        
        # Get working memory context
        context["working"] = dict(self.working.context)
        
        # Get relevant episodes
        episode_context = {"tags": tags or [], "task": task}
        context["episodic"] = [
            {"content": e.content, "tags": self._get_tags_for_entry(e)}
            for e in self.episodic.retrieve_similar(episode_context, limit=5)
        ]
        
        # Search for relevant facts
        task_keywords = task.lower().split()
        relevant_facts = {}
        for keyword in task_keywords:
            for key, value in self.semantic.search_facts(keyword):
                relevant_facts[key] = value
        context["semantic"] = relevant_facts
        
        return context
    
    def _get_tags_for_entry(self, entry: MemoryEntry) -> List[str]:
        """Get tags for an entry."""
        tags = []
        for tag, ids in self.episodic.index.items():
            if entry.id in ids:
                tags.append(tag)
        return tags
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "working": self.working.to_dict(),
            "episodic": self.episodic.to_dict(),
            "semantic": self.semantic.to_dict()
        }
