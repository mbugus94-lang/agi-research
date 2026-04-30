"""
Memory System for AGI Research

Implements a unified memory interface supporting multiple memory types
and storage backends. Based on research findings from SMGI [^7] and
LLM-in-Sandbox [^9] papers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
import json
import hashlib
import os
from pathlib import Path


class MemoryType(Enum):
    """Types of memory supported by the system."""
    WORKING = "working"       # Short-term, limited capacity (~7 items)
    EPISODIC = "episodic"     # Event sequences and experiences
    SEMANTIC = "semantic"     # Facts, concepts, knowledge
    PROCEDURAL = "procedural" # Skills and procedures


@dataclass
class MemoryEntry:
    """A single memory entry."""
    id: str
    content: Any
    memory_type: MemoryType
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    importance: float = 1.0  # 0.0 to 1.0
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    
    def __post_init__(self):
        if not self.id:
            self.id = self._generate_id()
    
    def _generate_id(self) -> str:
        """Generate unique ID based on content and timestamp."""
        content_str = json.dumps(self.content, sort_keys=True, default=str)
        hash_input = f"{content_str}{self.timestamp.isoformat()}"
        return hashlib.md5(hash_input.encode()).hexdigest()[:16]
    
    def touch(self):
        """Update access statistics."""
        self.access_count += 1
        self.last_accessed = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "importance": self.importance,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryEntry':
        """Create from dictionary."""
        return cls(
            id=data["id"],
            content=data["content"],
            memory_type=MemoryType(data["memory_type"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
            importance=data.get("importance", 1.0),
            access_count=data.get("access_count", 0),
            last_accessed=datetime.fromisoformat(data["last_accessed"]) if data.get("last_accessed") else None
        )


class MemoryAdapter(ABC):
    """Abstract base class for memory storage backends."""
    
    @abstractmethod
    def store(self, entry: MemoryEntry) -> str:
        """Store a memory entry, return its ID."""
        pass
    
    @abstractmethod
    def retrieve(self, memory_id: str) -> Optional[MemoryEntry]:
        """Retrieve a memory entry by ID."""
        pass
    
    @abstractmethod
    def query(self, memory_type: Optional[MemoryType] = None, 
              limit: int = 10,
              filter_fn: Optional[Callable[[MemoryEntry], bool]] = None) -> List[MemoryEntry]:
        """Query memory entries with optional filtering."""
        pass
    
    @abstractmethod
    def update(self, memory_id: str, entry: MemoryEntry) -> bool:
        """Update an existing memory entry."""
        pass
    
    @abstractmethod
    def delete(self, memory_id: str) -> bool:
        """Delete a memory entry."""
        pass
    
    @abstractmethod
    def clear(self, memory_type: Optional[MemoryType] = None):
        """Clear memory, optionally by type."""
        pass


class InMemoryAdapter(MemoryAdapter):
    """In-memory storage adapter (fast, non-persistent)."""
    
    def __init__(self):
        self._storage: Dict[str, MemoryEntry] = {}
    
    def store(self, entry: MemoryEntry) -> str:
        self._storage[entry.id] = entry
        return entry.id
    
    def retrieve(self, memory_id: str) -> Optional[MemoryEntry]:
        entry = self._storage.get(memory_id)
        if entry:
            entry.touch()
        return entry
    
    def query(self, memory_type: Optional[MemoryType] = None,
              limit: int = 10,
              filter_fn: Optional[Callable[[MemoryEntry], bool]] = None) -> List[MemoryEntry]:
        results = []
        for entry in self._storage.values():
            if memory_type and entry.memory_type != memory_type:
                continue
            if filter_fn and not filter_fn(entry):
                continue
            results.append(entry)
        
        # Sort by importance and recency
        results.sort(key=lambda e: (e.importance, e.timestamp), reverse=True)
        return results[:limit]
    
    def update(self, memory_id: str, entry: MemoryEntry) -> bool:
        if memory_id not in self._storage:
            return False
        self._storage[memory_id] = entry
        return True
    
    def delete(self, memory_id: str) -> bool:
        if memory_id not in self._storage:
            return False
        del self._storage[memory_id]
        return True
    
    def clear(self, memory_type: Optional[MemoryType] = None):
        if memory_type is None:
            self._storage.clear()
        else:
            self._storage = {
                k: v for k, v in self._storage.items() 
                if v.memory_type != memory_type
            }
    
    def __len__(self) -> int:
        return len(self._storage)


class FileAdapter(MemoryAdapter):
    """File-based persistent storage adapter."""
    
    def __init__(self, storage_dir: str = ".memory"):
        self._storage_dir = Path(storage_dir)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, MemoryEntry] = {}
        self._load_all()
    
    def _get_file_path(self, memory_id: str) -> Path:
        """Get file path for a memory entry."""
        return self._storage_dir / f"{memory_id}.json"
    
    def _load_all(self):
        """Load all memories from disk."""
        for file_path in self._storage_dir.glob("*.json"):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    entry = MemoryEntry.from_dict(data)
                    self._cache[entry.id] = entry
            except Exception as e:
                print(f"Warning: Failed to load {file_path}: {e}")
    
    def _save_entry(self, entry: MemoryEntry):
        """Save a single entry to disk."""
        file_path = self._get_file_path(entry.id)
        with open(file_path, 'w') as f:
            json.dump(entry.to_dict(), f, indent=2, default=str)
    
    def store(self, entry: MemoryEntry) -> str:
        self._cache[entry.id] = entry
        self._save_entry(entry)
        return entry.id
    
    def retrieve(self, memory_id: str) -> Optional[MemoryEntry]:
        entry = self._cache.get(memory_id)
        if entry:
            entry.touch()
            self._save_entry(entry)
        return entry
    
    def query(self, memory_type: Optional[MemoryType] = None,
              limit: int = 10,
              filter_fn: Optional[Callable[[MemoryEntry], bool]] = None) -> List[MemoryEntry]:
        results = []
        for entry in self._cache.values():
            if memory_type and entry.memory_type != memory_type:
                continue
            if filter_fn and not filter_fn(entry):
                continue
            results.append(entry)
        
        # Sort by importance and recency
        results.sort(key=lambda e: (e.importance, e.timestamp), reverse=True)
        return results[:limit]
    
    def update(self, memory_id: str, entry: MemoryEntry) -> bool:
        if memory_id not in self._cache:
            return False
        self._cache[memory_id] = entry
        self._save_entry(entry)
        return True
    
    def delete(self, memory_id: str) -> bool:
        if memory_id not in self._cache:
            return False
        del self._cache[memory_id]
        file_path = self._get_file_path(memory_id)
        if file_path.exists():
            file_path.unlink()
        return True
    
    def clear(self, memory_type: Optional[MemoryType] = None):
        if memory_type is None:
            for memory_id in list(self._cache.keys()):
                self.delete(memory_id)
        else:
            to_delete = [
                k for k, v in self._cache.items() 
                if v.memory_type == memory_type
            ]
            for memory_id in to_delete:
                self.delete(memory_id)


class Memory:
    """
    Main memory system interface.
    
    Provides unified access to multiple memory types with configurable
    storage backends. Supports working memory capacity management and
    consolidation to long-term memory.
    """
    
    WORKING_MEMORY_CAPACITY = 7  # Miller's law
    
    def __init__(self, adapter: Optional[MemoryAdapter] = None):
        self._adapter = adapter or InMemoryAdapter()
        self._working_memory: List[str] = []  # IDs in working memory
    
    def store(self, content: Any, 
              memory_type: MemoryType = MemoryType.WORKING,
              metadata: Optional[Dict[str, Any]] = None,
              importance: float = 1.0) -> str:
        """
        Store content in memory.
        
        Args:
            content: The content to store (any JSON-serializable data)
            memory_type: Type of memory to store in
            metadata: Optional metadata dictionary
            importance: Importance score (0.0 to 1.0)
        
        Returns:
            Memory entry ID
        """
        entry = MemoryEntry(
            id="",
            content=content,
            memory_type=memory_type,
            metadata=metadata or {},
            importance=importance
        )
        
        memory_id = self._adapter.store(entry)
        
        # Manage working memory capacity
        if memory_type == MemoryType.WORKING:
            self._working_memory.append(memory_id)
            self._enforce_working_memory_limit()
        
        return memory_id
    
    def retrieve(self, memory_id: str) -> Optional[Any]:
        """
        Retrieve content by memory ID.
        
        Args:
            memory_id: The memory entry ID
        
        Returns:
            The stored content, or None if not found
        """
        entry = self._adapter.retrieve(memory_id)
        return entry.content if entry else None
    
    def recall(self, query: Optional[str] = None,
               memory_type: Optional[MemoryType] = None,
               limit: int = 10,
               min_importance: float = 0.0) -> List[Dict[str, Any]]:
        """
        Recall memories matching criteria.
        
        Args:
            query: Optional search query (simple substring match for now)
            memory_type: Filter by memory type
            limit: Maximum number of results
            min_importance: Minimum importance threshold
        
        Returns:
            List of memory entries as dictionaries
        """
        def filter_fn(entry: MemoryEntry) -> bool:
            if entry.importance < min_importance:
                return False
            if query:
                content_str = json.dumps(entry.content, default=str).lower()
                return query.lower() in content_str
            return True
        
        entries = self._adapter.query(memory_type, limit, filter_fn)
        return [e.to_dict() for e in entries]
    
    def update(self, memory_id: str, new_content: Any,
               new_importance: Optional[float] = None) -> bool:
        """
        Update an existing memory entry.
        
        Args:
            memory_id: The memory entry ID
            new_content: New content
            new_importance: Optional new importance score
        
        Returns:
            True if updated, False if not found
        """
        entry = self._adapter.retrieve(memory_id)
        if not entry:
            return False
        
        entry.content = new_content
        if new_importance is not None:
            entry.importance = new_importance
        
        return self._adapter.update(memory_id, entry)
    
    def forget(self, memory_id: str) -> bool:
        """
        Delete a memory entry.
        
        Args:
            memory_id: The memory entry ID
        
        Returns:
            True if deleted, False if not found
        """
        if memory_id in self._working_memory:
            self._working_memory.remove(memory_id)
        return self._adapter.delete(memory_id)
    
    def consolidate(self, memory_id: Optional[str] = None) -> List[str]:
        """
        Consolidate working memory to long-term episodic memory.
        
        Based on research: Working memory has limited capacity and
        must be consolidated to long-term storage.
        
        Args:
            memory_id: Specific memory to consolidate, or None for all
        
        Returns:
            List of consolidated memory IDs
        """
        consolidated = []
        
        if memory_id:
            # Consolidate specific memory
            entry = self._adapter.retrieve(memory_id)
            if entry and entry.memory_type == MemoryType.WORKING:
                entry.memory_type = MemoryType.EPISODIC
                self._adapter.update(memory_id, entry)
                if memory_id in self._working_memory:
                    self._working_memory.remove(memory_id)
                consolidated.append(memory_id)
        else:
            # Consolidate all working memory
            for mid in list(self._working_memory):
                entry = self._adapter.retrieve(mid)
                if entry:
                    entry.memory_type = MemoryType.EPISODIC
                    self._adapter.update(mid, entry)
                    consolidated.append(mid)
            self._working_memory.clear()
        
        return consolidated
    
    def get_working_memory(self) -> List[Dict[str, Any]]:
        """Get all items currently in working memory."""
        results = []
        for memory_id in self._working_memory:
            entry = self._adapter.retrieve(memory_id)
            if entry:
                results.append(entry.to_dict())
        return results
    
    def clear(self, memory_type: Optional[MemoryType] = None):
        """Clear memory, optionally by type."""
        if memory_type == MemoryType.WORKING or memory_type is None:
            self._working_memory.clear()
        self._adapter.clear(memory_type)
    
    def _enforce_working_memory_limit(self):
        """Enforce working memory capacity limit."""
        while len(self._working_memory) > self.WORKING_MEMORY_CAPACITY:
            # Remove oldest (FIFO) or least important
            oldest_id = self._working_memory.pop(0)
            # Auto-consolidate to episodic
            entry = self._adapter.retrieve(oldest_id)
            if entry:
                entry.memory_type = MemoryType.EPISODIC
                self._adapter.update(oldest_id, entry)
    
    def stats(self) -> Dict[str, Any]:
        """Get memory system statistics."""
        all_entries = self._adapter.query(limit=10000)
        
        type_counts = {}
        for entry in all_entries:
            type_name = entry.memory_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        return {
            "total_entries": len(all_entries),
            "working_memory_items": len(self._working_memory),
            "working_memory_capacity": self.WORKING_MEMORY_CAPACITY,
            "by_type": type_counts,
            "storage_adapter": self._adapter.__class__.__name__
        }


def create_memory(adapter_type: str = "memory", **kwargs) -> Memory:
    """
    Factory function to create memory systems.
    
    Args:
        adapter_type: "memory" or "file"
        **kwargs: Additional arguments for the adapter
    
    Returns:
        Configured Memory instance
    """
    if adapter_type == "memory":
        adapter = InMemoryAdapter()
    elif adapter_type == "file":
        adapter = FileAdapter(**kwargs)
    else:
        raise ValueError(f"Unknown adapter type: {adapter_type}")
    
    return Memory(adapter)


# Module-level convenience function
memory = create_memory
