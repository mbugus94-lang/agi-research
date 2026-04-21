"""
Memory System for AGI Agent

Based on research findings:
- Working memory for current context
- Episodic memory for experiences
- Semantic memory for facts/patterns
- Procedural memory for skill traces

Inspired by Ouroboros' persistent identity and Clawith's memory architecture.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from collections import deque
import hashlib


@dataclass
class MemoryEntry:
    """A single memory entry"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: Any = None
    memory_type: str = "episodic"  # working, episodic, semantic, procedural
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: List[str] = field(default_factory=list)
    importance: float = 0.5  # 0-1 scale
    access_count: int = 0
    last_accessed: Optional[str] = None
    embeddings: Optional[List[float]] = None  # For semantic search
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "timestamp": self.timestamp,
            "tags": self.tags,
            "importance": self.importance,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "embeddings": self.embeddings
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "MemoryEntry":
        return cls(**data)


class MemorySystem:
    """
    Multi-tier memory system:
    
    1. Working Memory: Small, fast, recent context
    2. Episodic Memory: Experiences with outcomes
    3. Semantic Memory: Facts and learned patterns
    4. Procedural Memory: Skill execution traces
    """
    
    def __init__(self, 
                 working_capacity: int = 10,
                 episodic_capacity: int = 1000,
                 semantic_capacity: int = 500):
        
        # Working memory: limited size, fast access
        self.working_memory: deque = deque(maxlen=working_capacity)
        
        # Episodic memory: experiences with timestamps
        self.episodic_memory: Dict[str, MemoryEntry] = {}
        
        # Semantic memory: facts and patterns
        self.semantic_memory: Dict[str, MemoryEntry] = {}
        
        # Procedural memory: how to do things
        self.procedural_memory: Dict[str, MemoryEntry] = {}
        
        # Index for search
        self.tag_index: Dict[str, List[str]] = {}
        
    def store(self, content: Any, 
              memory_type: str = "episodic",
              tags: Optional[List[str]] = None,
              importance: float = 0.5) -> str:
        """Store a new memory entry"""
        
        entry = MemoryEntry(
            content=content,
            memory_type=memory_type,
            tags=tags or [],
            importance=importance
        )
        
        # Store in appropriate memory tier
        if memory_type == "working":
            self.working_memory.append(entry)
        elif memory_type == "episodic":
            self.episodic_memory[entry.id] = entry
        elif memory_type == "semantic":
            self.semantic_memory[entry.id] = entry
        elif memory_type == "procedural":
            self.procedural_memory[entry.id] = entry
        
        # Update tag index
        for tag in entry.tags:
            if tag not in self.tag_index:
                self.tag_index[tag] = []
            self.tag_index[tag].append(entry.id)
        
        return entry.id
    
    def retrieve(self, memory_id: str, 
                 memory_type: Optional[str] = None) -> Optional[MemoryEntry]:
        """Retrieve a specific memory by ID"""
        
        entry = None
        
        if memory_type == "working":
            for e in self.working_memory:
                if e.id == memory_id:
                    entry = e
                    break
        elif memory_type == "episodic":
            entry = self.episodic_memory.get(memory_id)
        elif memory_type == "semantic":
            entry = self.semantic_memory.get(memory_id)
        elif memory_type == "procedural":
            entry = self.procedural_memory.get(memory_id)
        else:
            # Search all tiers
            for e in self.working_memory:
                if e.id == memory_id:
                    entry = e
                    break
            entry = entry or self.episodic_memory.get(memory_id)
            entry = entry or self.semantic_memory.get(memory_id)
            entry = entry or self.procedural_memory.get(memory_id)
        
        if entry:
            entry.access_count += 1
            entry.last_accessed = datetime.now().isoformat()
        
        return entry
    
    def search_by_tags(self, tags: List[str], 
                       memory_type: Optional[str] = None) -> List[MemoryEntry]:
        """Search memories by tags"""
        results = []
        
        for tag in tags:
            if tag in self.tag_index:
                for memory_id in self.tag_index[tag]:
                    entry = self.retrieve(memory_id, memory_type)
                    if entry and entry not in results:
                        results.append(entry)
        
        # Sort by importance and recency
        results.sort(key=lambda e: (e.importance, e.timestamp), reverse=True)
        return results
    
    def get_working_memory(self) -> List[MemoryEntry]:
        """Get all entries in working memory"""
        return list(self.working_memory)
    
    def get_recent_episodes(self, n: int = 10) -> List[MemoryEntry]:
        """Get most recent episodic memories"""
        episodes = sorted(
            self.episodic_memory.values(),
            key=lambda e: e.timestamp,
            reverse=True
        )
        return episodes[:n]
    
    def get_important_memories(self, 
                               memory_type: Optional[str] = None,
                               threshold: float = 0.7,
                               n: int = 10) -> List[MemoryEntry]:
        """Get most important memories above threshold"""
        
        all_memories = []
        
        if memory_type is None or memory_type == "working":
            all_memories.extend(self.working_memory)
        if memory_type is None or memory_type == "episodic":
            all_memories.extend(self.episodic_memory.values())
        if memory_type is None or memory_type == "semantic":
            all_memories.extend(self.semantic_memory.values())
        if memory_type is None or memory_type == "procedural":
            all_memories.extend(self.procedural_memory.values())
        
        important = [m for m in all_memories if m.importance >= threshold]
        important.sort(key=lambda e: e.importance, reverse=True)
        
        return important[:n]
    
    def consolidate_working_to_episodic(self) -> None:
        """
        Move working memory entries to episodic memory.
        Called periodically to free up working memory.
        """
        while self.working_memory:
            entry = self.working_memory.popleft()
            entry.memory_type = "episodic"
            self.episodic_memory[entry.id] = entry
    
    def store_skill_trace(self, skill_name: str, 
                          inputs: Dict, 
                          outputs: Any,
                          success: bool,
                          duration_ms: float) -> str:
        """
        Store a procedural memory (skill execution trace).
        Used for learning from experience.
        """
        trace = {
            "skill": skill_name,
            "inputs": inputs,
            "outputs": outputs,
            "success": success,
            "duration_ms": duration_ms
        }
        
        importance = 0.8 if not success else 0.5  # Failed attempts more important
        
        return self.store(
            content=trace,
            memory_type="procedural",
            tags=["skill", skill_name, "success" if success else "failure"],
            importance=importance
        )
    
    def get_skill_traces(self, skill_name: str, 
                         success_only: bool = False) -> List[MemoryEntry]:
        """Get execution traces for a specific skill"""
        traces = self.search_by_tags(["skill", skill_name], "procedural")
        
        if success_only:
            traces = [t for t in traces if t.content.get("success", False)]
        
        return traces
    
    def get_context_for_task(self, task_description: str,
                            relevant_tags: Optional[List[str]] = None) -> Dict:
        """
        Gather relevant context for a new task.
        Combines working memory with relevant episodic/semantic memories.
        """
        context = {
            "working_memory": [e.to_dict() for e in self.get_working_memory()],
            "relevant_episodes": [],
            "relevant_semantic": [],
            "skill_traces": []
        }
        
        if relevant_tags:
            episodes = self.search_by_tags(relevant_tags, "episodic")
            context["relevant_episodes"] = [e.to_dict() for e in episodes[:5]]
            
            semantic = self.search_by_tags(relevant_tags, "semantic")
            context["relevant_semantic"] = [e.to_dict() for e in semantic[:5]]
        
        # Add recent important memories
        important = self.get_important_memories(threshold=0.8, n=5)
        context["important_memories"] = [e.to_dict() for e in important]
        
        return context
    
    def save(self, path: str) -> None:
        """Save memory system to file"""
        state = {
            "working_memory": [e.to_dict() for e in self.working_memory],
            "episodic_memory": {k: v.to_dict() for k, v in self.episodic_memory.items()},
            "semantic_memory": {k: v.to_dict() for k, v in self.semantic_memory.items()},
            "procedural_memory": {k: v.to_dict() for k, v in self.procedural_memory.items()},
            "tag_index": self.tag_index
        }
        
        with open(path, 'w') as f:
            json.dump(state, f, indent=2)
    
    def load(self, path: str) -> None:
        """Load memory system from file"""
        with open(path, 'r') as f:
            state = json.load(f)
        
        self.working_memory = deque(
            [MemoryEntry.from_dict(e) for e in state.get("working_memory", [])],
            maxlen=self.working_memory.maxlen
        )
        
        self.episodic_memory = {
            k: MemoryEntry.from_dict(v) 
            for k, v in state.get("episodic_memory", {}).items()
        }
        
        self.semantic_memory = {
            k: MemoryEntry.from_dict(v) 
            for k, v in state.get("semantic_memory", {}).items()
        }
        
        self.procedural_memory = {
            k: MemoryEntry.from_dict(v) 
            for k, v in state.get("procedural_memory", {}).items()
        }
        
        self.tag_index = state.get("tag_index", {})
    
    def get_stats(self) -> Dict:
        """Get memory system statistics"""
        return {
            "working_memory_size": len(self.working_memory),
            "episodic_memory_size": len(self.episodic_memory),
            "semantic_memory_size": len(self.semantic_memory),
            "procedural_memory_size": len(self.procedural_memory),
            "total_tags": len(self.tag_index),
            "working_capacity": self.working_memory.maxlen
        }


if __name__ == "__main__":
    # Basic test
    memory = MemorySystem(working_capacity=5)
    
    # Store some memories
    memory.store("Current goal: Build AGI", "working", ["goal", "agi"], 0.9)
    memory.store("Research: ARC-AGI shows test-time adaptation is key", 
                 "semantic", ["research", "arc-agi"], 0.8)
    memory.store("Experience: Failed to implement planner", 
                 "episodic", ["failure", "planner"], 0.9)
    
    # Store skill trace
    memory.store_skill_trace(
        skill_name="web_search",
        inputs={"query": "agi research"},
        outputs={"results": 10},
        success=True,
        duration_ms=1500
    )
    
    print("Memory Stats:", memory.get_stats())
    print("\nWorking Memory:")
    for m in memory.get_working_memory():
        print(f"  - {m.content}")
    
    print("\nSearch by tags ['research']:")
    results = memory.search_by_tags(["research"])
    for r in results:
        print(f"  - {r.content}")
    
    print("\nImportant memories:")
    for m in memory.get_important_memories(threshold=0.8):
        print(f"  - [{m.memory_type}] {m.content[:50]}...")
