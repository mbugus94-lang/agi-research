"""
Tiered Memory System with L0/L1/L2 Architecture

Based on research from DeerFlow 2.0 and Ouroboros:
- L0: Context Window / Immediate Attention (seconds to minutes)
- L1: Working Memory (active tasks, minutes to hours)  
- L2: Long-term Storage (consolidated, hours to years)

Features:
- Vector embedding for semantic search
- Automatic consolidation from L0→L1→L2
- Importance-based forgetting
- Knowledge graph integration hooks
- Episodic clustering for similar experiences
"""

import json
import uuid
import hashlib
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Set
from collections import deque, defaultdict
import math


@dataclass
class TieredMemoryEntry:
    """A memory entry in the tiered system"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: Any = None
    tier: int = 1  # 0=L0, 1=L1, 2=L2
    timestamp: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    importance: float = 0.5  # 0-1 scale
    tags: List[str] = field(default_factory=list)
    source_tier: Optional[int] = None  # Where did this memory originate?
    embedding: Optional[List[float]] = None  # Semantic vector (placeholder)
    associations: List[str] = field(default_factory=list)  # Related memory IDs
    decay_rate: float = 0.01  # How fast importance decays
    
    # Context metadata
    session_id: Optional[str] = None
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "content": self.content,
            "tier": self.tier,
            "timestamp": self.timestamp.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "importance": self.importance,
            "tags": self.tags,
            "source_tier": self.source_tier,
            "embedding": self.embedding,
            "associations": self.associations,
            "decay_rate": self.decay_rate,
            "session_id": self.session_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "TieredMemoryEntry":
        entry = cls()
        entry.id = data.get("id", str(uuid.uuid4()))
        entry.content = data.get("content")
        entry.tier = data.get("tier", 1)
        entry.timestamp = datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.now()
        entry.last_accessed = datetime.fromisoformat(data["last_accessed"]) if data.get("last_accessed") else datetime.now()
        entry.access_count = data.get("access_count", 0)
        entry.importance = data.get("importance", 0.5)
        entry.tags = data.get("tags", [])
        entry.source_tier = data.get("source_tier")
        entry.embedding = data.get("embedding")
        entry.associations = data.get("associations", [])
        entry.decay_rate = data.get("decay_rate", 0.01)
        entry.session_id = data.get("session_id")
        entry.task_id = data.get("task_id")
        entry.agent_id = data.get("agent_id")
        return entry
    
    def current_importance(self) -> float:
        """Calculate current importance with time decay"""
        age_hours = (datetime.now() - self.last_accessed).total_seconds() / 3600
        decay = math.exp(-self.decay_rate * age_hours)
        return self.importance * decay * (1 + 0.1 * self.access_count)
    
    def touch(self):
        """Mark as accessed"""
        self.access_count += 1
        self.last_accessed = datetime.now()


class TieredMemorySystem:
    """
    Three-tier memory architecture:
    
    L0 - Context Buffer (Immediate)
    - Capacity: 5-10 items
    - Duration: Seconds to minutes
    - Analogous to human attention/focus
    - No persistence (lost after session)
    
    L1 - Working Memory (Active)
    - Capacity: 100-500 items  
    - Duration: Minutes to hours
    - Current task context
    - Active goals and plans
    - Automatic consolidation to L2
    
    L2 - Long-term Storage (Persistent)
    - Capacity: 10,000+ items
    - Duration: Hours to years
    - Consolidated knowledge
    - Semantic indexing
    - Forgetting via importance decay
    """
    
    def __init__(self,
                 l0_capacity: int = 7,
                 l1_capacity: int = 100,
                 l2_capacity: int = 10000,
                 consolidation_interval_minutes: int = 10,
                 agent_id: str = "agent_001"):
        
        self.agent_id = agent_id
        self.session_id = str(uuid.uuid4())[:8]
        
        # Tier capacities
        self.l0_capacity = l0_capacity
        self.l1_capacity = l1_capacity
        self.l2_capacity = l2_capacity
        
        # Memory storage
        self.l0_buffer: deque = deque(maxlen=l0_capacity)  # Context buffer
        self.l1_working: Dict[str, TieredMemoryEntry] = {}  # Active working
        self.l2_longterm: Dict[str, TieredMemoryEntry] = {}  # Persistent storage
        
        # Index structures
        self.tag_index: Dict[str, Set[str]] = defaultdict(set)
        self.task_index: Dict[str, Set[str]] = defaultdict(set)
        self.session_index: Dict[str, Set[str]] = defaultdict(set)
        
        # Consolidation settings
        self.consolidation_interval = timedelta(minutes=consolidation_interval_minutes)
        self.last_consolidation = datetime.now()
        
        # Episodic clustering (for similar experiences)
        self.episodic_clusters: Dict[str, List[str]] = defaultdict(list)
        
        # Importance thresholds
        self.l1_importance_threshold = 0.3
        self.l2_importance_threshold = 0.6
        
    def _generate_embedding(self, content: Any) -> List[float]:
        """
        Generate a simple embedding vector (placeholder for real embeddings).
        In production, use sentence-transformers or OpenAI embeddings.
        """
        # Simple hash-based embedding for demo
        content_str = str(content)
        hash_val = int(hashlib.md5(content_str.encode()).hexdigest(), 16)
        random.seed(hash_val)
        return [random.uniform(-1, 1) for _ in range(64)]
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot / (norm1 * norm2)
    
    def store_l0(self, content: Any, tags: Optional[List[str]] = None,
                 task_id: Optional[str] = None) -> str:
        """Store in L0 context buffer (immediate attention)"""
        entry = TieredMemoryEntry(
            content=content,
            tier=0,
            tags=tags or [],
            task_id=task_id,
            agent_id=self.agent_id,
            session_id=self.session_id,
            importance=1.0,  # L0 items are always high importance
            decay_rate=0.5  # Fast decay
        )
        
        self.l0_buffer.append(entry)
        return entry.id
    
    def store_l1(self, content: Any, tags: Optional[List[str]] = None,
                 importance: float = 0.5, task_id: Optional[str] = None,
                 associations: Optional[List[str]] = None) -> str:
        """Store in L1 working memory (active context)"""
        
        # Check if we need to consolidate first
        self._check_consolidation()
        
        entry = TieredMemoryEntry(
            content=content,
            tier=1,
            tags=tags or [],
            importance=importance,
            task_id=task_id,
            agent_id=self.agent_id,
            session_id=self.session_id,
            embedding=self._generate_embedding(content),
            associations=associations or []
        )
        
        # If L1 full, move lowest importance to L2 or forget
        if len(self.l1_working) >= self.l1_capacity:
            self._evict_from_l1()
        
        self.l1_working[entry.id] = entry
        self._update_indices(entry)
        
        return entry.id
    
    def store_l2(self, content: Any, tags: Optional[List[str]] = None,
                 importance: float = 0.7, task_id: Optional[str] = None,
                 source_tier: int = 1) -> str:
        """Store directly in L2 long-term memory"""
        
        entry = TieredMemoryEntry(
            content=content,
            tier=2,
            tags=tags or [],
            importance=importance,
            task_id=task_id,
            agent_id=self.agent_id,
            session_id=self.session_id,
            source_tier=source_tier,
            embedding=self._generate_embedding(content)
        )
        
        # If L2 full, forget lowest importance items
        if len(self.l2_longterm) >= self.l2_capacity:
            self._forget_from_l2()
        
        self.l2_longterm[entry.id] = entry
        self._update_indices(entry)
        
        return entry.id
    
    def store(self, content: Any, tier: int = 1,
              tags: Optional[List[str]] = None,
              importance: float = 0.5,
              task_id: Optional[str] = None) -> str:
        """Store to specified tier"""
        if tier == 0:
            return self.store_l0(content, tags, task_id)
        elif tier == 1:
            return self.store_l1(content, tags, importance, task_id)
        else:
            return self.store_l2(content, tags, importance, task_id)
    
    def _update_indices(self, entry: TieredMemoryEntry):
        """Update all indices for a memory entry"""
        for tag in entry.tags:
            self.tag_index[tag].add(entry.id)
        if entry.task_id:
            self.task_index[entry.task_id].add(entry.id)
        if entry.session_id:
            self.session_index[entry.session_id].add(entry.id)
    
    def _remove_from_indices(self, entry: TieredMemoryEntry):
        """Remove entry from all indices"""
        for tag in entry.tags:
            self.tag_index[tag].discard(entry.id)
        if entry.task_id:
            self.task_index[entry.task_id].discard(entry.id)
        if entry.session_id:
            self.session_index[entry.session_id].discard(entry.id)
    
    def _evict_from_l1(self):
        """Move lowest importance item from L1 to L2 or forget"""
        if not self.l1_working:
            return
        
        # Find lowest importance entry
        lowest = min(self.l1_working.values(), key=lambda e: e.current_importance())
        
        # Remove from L1
        del self.l1_working[lowest.id]
        self._remove_from_indices(lowest)
        
        # Promote to L2 if important enough
        if lowest.current_importance() >= self.l1_importance_threshold:
            lowest.tier = 2
            lowest.source_tier = 1
            self.l2_longterm[lowest.id] = lowest
            self._update_indices(lowest)
    
    def _forget_from_l2(self):
        """Remove lowest importance items from L2 (true forgetting)"""
        if not self.l2_longterm:
            return
        
        # Sort by current importance and remove bottom 1%
        sorted_entries = sorted(
            self.l2_longterm.values(),
            key=lambda e: e.current_importance()
        )
        
        to_forget = int(len(sorted_entries) * 0.01) + 1
        for entry in sorted_entries[:to_forget]:
            if entry.current_importance() < self.l2_importance_threshold:
                del self.l2_longterm[entry.id]
                self._remove_from_indices(entry)
    
    def _check_consolidation(self):
        """Check if it's time to consolidate L1→L2"""
        now = datetime.now()
        if now - self.last_consolidation >= self.consolidation_interval:
            self.consolidate()
            self.last_consolidation = now
    
    def consolidate(self):
        """
        Consolidate L1 working memory to L2 long-term storage.
        Based on importance, recency, and access patterns.
        """
        consolidated = []
        
        for entry_id, entry in list(self.l1_working.items()):
            current_imp = entry.current_importance()
            age_hours = (datetime.now() - entry.timestamp).total_seconds() / 3600
            
            # Consolidation criteria
            should_consolidate = (
                current_imp >= self.l2_importance_threshold or
                (current_imp >= self.l1_importance_threshold and age_hours > 1) or
                entry.access_count >= 3  # Frequently accessed
            )
            
            if should_consolidate:
                # Move to L2
                entry.tier = 2
                entry.source_tier = 1
                self.l2_longterm[entry_id] = entry
                del self.l1_working[entry_id]
                consolidated.append(entry_id)
                
                # Cluster similar episodic memories
                self._cluster_episodic(entry)
        
        return consolidated
    
    def _cluster_episodic(self, entry: TieredMemoryEntry):
        """Cluster similar episodic memories together"""
        if not entry.tags:
            return
        
        # Create cluster key from primary tags
        cluster_key = tuple(sorted(entry.tags[:3]))
        self.episodic_clusters[str(cluster_key)].append(entry.id)
    
    def retrieve(self, memory_id: str) -> Optional[TieredMemoryEntry]:
        """Retrieve a memory by ID from any tier"""
        # Check L1
        if memory_id in self.l1_working:
            entry = self.l1_working[memory_id]
            entry.touch()
            return entry
        
        # Check L2
        if memory_id in self.l2_longterm:
            entry = self.l2_longterm[memory_id]
            entry.touch()
            # Promote to L1 if recently accessed
            if entry.current_importance() > 0.8:
                self._promote_to_l1(entry)
            return entry
        
        return None
    
    def _promote_to_l1(self, entry: TieredMemoryEntry):
        """Promote an L2 entry back to L1 (reactivation)"""
        if entry.id in self.l2_longterm:
            del self.l2_longterm[entry.id]
            entry.tier = 1
            
            # Make room if needed
            if len(self.l1_working) >= self.l1_capacity:
                self._evict_from_l1()
            
            self.l1_working[entry.id] = entry
    
    def search_by_tags(self, tags: List[str], tier: Optional[int] = None,
                       limit: int = 10) -> List[TieredMemoryEntry]:
        """Search memories by tags"""
        results = []
        seen = set()
        
        # Collect candidate IDs
        candidate_ids = set()
        for tag in tags:
            candidate_ids.update(self.tag_index.get(tag, set()))
        
        # Retrieve and score
        for memory_id in candidate_ids:
            if memory_id in seen:
                continue
            
            entry = None
            if tier is None or tier == 1:
                entry = self.l1_working.get(memory_id)
            if entry is None and (tier is None or tier == 2):
                entry = self.l2_longterm.get(memory_id)
            
            if entry:
                # Score by tag overlap and importance
                tag_overlap = len(set(entry.tags) & set(tags))
                score = tag_overlap * entry.current_importance()
                results.append((score, entry))
                seen.add(memory_id)
        
        # Sort by score
        results.sort(key=lambda x: x[0], reverse=True)
        
        # Touch accessed entries
        for _, entry in results[:limit]:
            entry.touch()
        
        return [entry for _, entry in results[:limit]]
    
    def semantic_search(self, query: Any, limit: int = 10) -> List[Tuple[TieredMemoryEntry, float]]:
        """Search by semantic similarity (using embeddings)"""
        query_embedding = self._generate_embedding(query)
        
        scored = []
        
        # Search L1
        for entry in self.l1_working.values():
            if entry.embedding:
                sim = self._cosine_similarity(query_embedding, entry.embedding)
                scored.append((entry, sim * entry.current_importance()))
        
        # Search L2
        for entry in self.l2_longterm.values():
            if entry.embedding:
                sim = self._cosine_similarity(query_embedding, entry.embedding)
                scored.append((entry, sim * entry.current_importance()))
        
        # Sort by score
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Touch accessed entries
        for entry, _ in scored[:limit]:
            entry.touch()
        
        return scored[:limit]
    
    def get_l0_context(self) -> List[TieredMemoryEntry]:
        """Get all L0 context buffer entries (most recent first)"""
        return list(reversed(self.l0_buffer))
    
    def get_l1_working(self, sort_by: str = "importance") -> List[TieredMemoryEntry]:
        """Get L1 working memory entries"""
        entries = list(self.l1_working.values())
        
        if sort_by == "importance":
            entries.sort(key=lambda e: e.current_importance(), reverse=True)
        elif sort_by == "recency":
            entries.sort(key=lambda e: e.last_accessed, reverse=True)
        elif sort_by == "access":
            entries.sort(key=lambda e: e.access_count, reverse=True)
        
        return entries
    
    def get_l2_longterm(self, tag: Optional[str] = None,
                        limit: int = 100) -> List[TieredMemoryEntry]:
        """Get L2 long-term memories, optionally filtered by tag"""
        if tag:
            ids = self.tag_index.get(tag, set())
            entries = [self.l2_longterm[i] for i in ids if i in self.l2_longterm]
        else:
            entries = list(self.l2_longterm.values())
        
        # Sort by importance
        entries.sort(key=lambda e: e.current_importance(), reverse=True)
        return entries[:limit]
    
    def get_episodic_cluster(self, tags: List[str]) -> List[TieredMemoryEntry]:
        """Get memories from the same episodic cluster"""
        cluster_key = tuple(sorted(tags[:3]))
        memory_ids = self.episodic_clusters.get(str(cluster_key), [])
        
        entries = []
        for mid in memory_ids:
            entry = self.retrieve(mid)
            if entry:
                entries.append(entry)
        
        return entries
    
    def get_context_for_task(self, task_id: str,
                            include_l0: bool = True,
                            include_l1: bool = True,
                            include_l2: bool = True,
                            relevant_tags: Optional[List[str]] = None) -> Dict:
        """Gather comprehensive context for a task"""
        context = {
            "task_id": task_id,
            "session_id": self.session_id,
            "agent_id": self.agent_id
        }
        
        # L0: Immediate context
        if include_l0:
            context["l0_context"] = [
                {"content": e.content, "tags": e.tags}
                for e in self.get_l0_context()
            ]
        
        # L1: Active working memory
        if include_l1:
            l1_entries = [e for e in self.l1_working.values() 
                         if e.task_id == task_id or not task_id]
            context["l1_working"] = [
                {"content": e.content, "tags": e.tags, 
                 "importance": e.current_importance()}
                for e in sorted(l1_entries, 
                              key=lambda x: x.current_importance(), 
                              reverse=True)[:20]
            ]
        
        # L2: Relevant long-term memories
        if include_l2 and relevant_tags:
            l2_entries = self.search_by_tags(relevant_tags, tier=2, limit=15)
            context["l2_relevant"] = [
                {"content": e.content, "tags": e.tags,
                 "importance": e.current_importance()}
                for e in l2_entries
            ]
        
        return context
    
    def create_episodic_summary(self, task_id: str) -> Optional[str]:
        """Create a summary of all memories associated with a task"""
        memory_ids = self.task_index.get(task_id, set())
        
        if not memory_ids:
            return None
        
        entries = []
        for mid in memory_ids:
            entry = self.l1_working.get(mid) or self.l2_longterm.get(mid)
            if entry:
                entries.append(entry)
        
        # Sort by timestamp
        entries.sort(key=lambda e: e.timestamp)
        
        # Build summary
        summary_lines = [
            f"Task {task_id} Summary:",
            f"Total memories: {len(entries)}",
            f"Duration: {entries[0].timestamp} to {entries[-1].timestamp}",
            "Key events:"
        ]
        
        # Include high-importance entries
        for entry in entries:
            if entry.current_importance() >= 0.7:
                summary_lines.append(f"  - [{entry.timestamp}] {str(entry.content)[:100]}")
        
        return "\n".join(summary_lines)
    
    def get_stats(self) -> Dict:
        """Get comprehensive memory statistics"""
        l1_importance = [e.current_importance() for e in self.l1_working.values()]
        l2_importance = [e.current_importance() for e in self.l2_longterm.values()]
        
        return {
            "l0_buffer": {
                "size": len(self.l0_buffer),
                "capacity": self.l0_capacity
            },
            "l1_working": {
                "size": len(self.l1_working),
                "capacity": self.l1_capacity,
                "avg_importance": sum(l1_importance) / len(l1_importance) if l1_importance else 0,
                "high_importance_count": sum(1 for i in l1_importance if i >= 0.7)
            },
            "l2_longterm": {
                "size": len(self.l2_longterm),
                "capacity": self.l2_capacity,
                "avg_importance": sum(l2_importance) / len(l2_importance) if l2_importance else 0,
                "high_importance_count": sum(1 for i in l2_importance if i >= 0.7)
            },
            "indices": {
                "tags": len(self.tag_index),
                "tasks": len(self.task_index),
                "sessions": len(self.session_index),
                "clusters": len(self.episodic_clusters)
            },
            "session_id": self.session_id,
            "last_consolidation": self.last_consolidation.isoformat()
        }
    
    def save(self, path: str) -> None:
        """Save memory system to file"""
        state = {
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "l1_working": {k: v.to_dict() for k, v in self.l1_working.items()},
            "l2_longterm": {k: v.to_dict() for k, v in self.l2_longterm.items()},
            "tag_index": {k: list(v) for k, v in self.tag_index.items()},
            "task_index": {k: list(v) for k, v in self.task_index.items()},
            "session_index": {k: list(v) for k, v in self.session_index.items()},
            "episodic_clusters": dict(self.episodic_clusters),
            "last_consolidation": self.last_consolidation.isoformat()
        }
        
        with open(path, 'w') as f:
            json.dump(state, f, indent=2)
    
    def load(self, path: str) -> None:
        """Load memory system from file"""
        with open(path, 'r') as f:
            state = json.load(f)
        
        self.agent_id = state.get("agent_id", self.agent_id)
        self.session_id = state.get("session_id", str(uuid.uuid4())[:8])
        
        self.l1_working = {
            k: TieredMemoryEntry.from_dict(v)
            for k, v in state.get("l1_working", {}).items()
        }
        
        self.l2_longterm = {
            k: TieredMemoryEntry.from_dict(v)
            for k, v in state.get("l2_longterm", {}).items()
        }
        
        self.tag_index = defaultdict(set, 
            {k: set(v) for k, v in state.get("tag_index", {}).items()})
        self.task_index = defaultdict(set,
            {k: set(v) for k, v in state.get("task_index", {}).items()})
        self.session_index = defaultdict(set,
            {k: set(v) for k, v in state.get("session_index", {}).items()})
        
        self.episodic_clusters = defaultdict(list,
            state.get("episodic_clusters", {}))
        
        self.last_consolidation = datetime.fromisoformat(
            state.get("last_consolidation", datetime.now().isoformat()))


if __name__ == "__main__":
    # Demo/test
    memory = TieredMemorySystem(agent_id="test_agent")
    
    # Store some L0 context
    memory.store_l0("Current focus: Debugging memory system", 
                    tags=["debug", "memory"])
    memory.store_l0("User input: Test the tiered system",
                    tags=["input", "user"])
    
    # Store L1 working memories
    task_id = "task_001"
    for i in range(10):
        memory.store_l1(
            content=f"Working on subtask {i}",
            tags=["task", "subtask"],
            importance=0.5 + (i * 0.05),
            task_id=task_id
        )
    
    # Store high-importance L2 memories
    memory.store_l2(
        content="Critical architecture decision: Use tiered memory",
        tags=["architecture", "decision"],
        importance=0.95
    )
    memory.store_l2(
        content="Research insight: DeerFlow 2.0 uses InfoQuest",
        tags=["research", "deerflow"],
        importance=0.85
    )
    
    # Access some L2 to promote them
    for entry_id in list(memory.l2_longterm.keys())[:3]:
        for _ in range(5):  # Multiple accesses
            memory.retrieve(entry_id)
    
    # Trigger consolidation
    consolidated = memory.consolidate()
    print(f"Consolidated {len(consolidated)} memories to L2")
    
    # Search
    results = memory.search_by_tags(["task"])
    print(f"\nSearch for 'task': {len(results)} results")
    
    # Semantic search
    sem_results = memory.semantic_search("architecture decision")
    print(f"\nSemantic search: {len(sem_results)} results")
    
    # Stats
    print("\nMemory Stats:")
    print(json.dumps(memory.get_stats(), indent=2))
