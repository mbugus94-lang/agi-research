"""
Memory System Implementation

Hierarchical memory: Working → Episodic → Semantic
Implements persistent storage with retrieval mechanisms.
"""

import json
import sqlite3
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
import hashlib


@dataclass
class MemoryEntry:
    """A single memory entry."""
    id: str
    content: str
    memory_type: str  # working, episodic, semantic
    timestamp: datetime
    tags: List[str]
    importance: float  # 0-1
    embeddings: Optional[List[float]] = None
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class MemoryManager:
    """
    Hierarchical memory system for agents.
    
    Levels:
    - Working: Short-term, session-specific
    - Episodic: Past experiences and actions
    - Semantic: Facts, concepts, learned knowledge
    """
    
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()
        
        # In-memory working memory (fastest)
        self.working_memory: List[MemoryEntry] = []
        self.working_capacity = 10
    
    def _init_db(self):
        """Initialize SQLite database."""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                tags TEXT,
                importance REAL,
                embeddings TEXT,
                metadata TEXT
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_type ON memories(memory_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp)
        """)
        self.conn.commit()
    
    def store(
        self,
        content: str,
        memory_type: str = "episodic",
        tags: List[str] = None,
        importance: float = 0.5,
        metadata: Dict = None
    ) -> str:
        """Store a new memory entry."""
        entry_id = self._generate_id(content)
        entry = MemoryEntry(
            id=entry_id,
            content=content,
            memory_type=memory_type,
            timestamp=datetime.now(),
            tags=tags or [],
            importance=importance,
            metadata=metadata or {}
        )
        
        # Store in working memory if high importance or recent
        if memory_type == "working" or importance > 0.8:
            self._add_to_working_memory(entry)
        
        # Persist to database
        self._persist_entry(entry)
        
        return entry_id
    
    async def store_action(self, action, result):
        """Store an action-result pair (episodic memory)."""
        content = f"Action: {action.tool} | Result: {result.success}"
        metadata = {
            "tool": action.tool,
            "params": action.params,
            "success": result.success,
            "output": str(result.output) if result.output else None,
            "error": result.error
        }
        return self.store(
            content=content,
            memory_type="episodic",
            tags=["action", action.tool],
            importance=0.7 if result.success else 0.9,  # Failed actions more important
            metadata=metadata
        )
    
    def retrieve(
        self,
        query: str = None,
        memory_type: str = None,
        tags: List[str] = None,
        limit: int = 10,
        since: datetime = None
    ) -> List[MemoryEntry]:
        """Retrieve memories matching criteria."""
        # First check working memory (fast)
        if memory_type == "working" or memory_type is None:
            results = self._search_working_memory(query, tags)
            if results:
                return results[:limit]
        
        # Then query database
        return self._query_database(query, memory_type, tags, limit, since)
    
    def retrieve_relevant(
        self,
        context: str,
        limit: int = 5
    ) -> List[MemoryEntry]:
        """Retrieve memories relevant to current context."""
        # Simple keyword matching (replace with embedding similarity)
        keywords = context.lower().split()
        
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM memories ORDER BY importance DESC, timestamp DESC"
        )
        rows = cursor.fetchall()
        
        scored = []
        for row in rows:
            content = row[1].lower()
            score = sum(1 for kw in keywords if kw in content)
            scored.append((score, row))
        
        scored.sort(reverse=True)
        return [self._row_to_entry(row) for _, row in scored[:limit]]
    
    def consolidate(self):
        """
        Consolidate working memory to episodic.
        Called periodically to free working memory slots.
        """
        for entry in self.working_memory:
            if entry.memory_type == "working":
                # Convert to episodic
                entry.memory_type = "episodic"
                self._persist_entry(entry)
        
        # Clear working memory
        self.working_memory = []
    
    def get_episodic_summary(self, n_recent: int = 10) -> str:
        """Get summary of recent episodes."""
        entries = self.retrieve(memory_type="episodic", limit=n_recent)
        return "\n".join([
            f"[{e.timestamp.strftime('%H:%M')}] {e.content}"
            for e in entries
        ])
    
    def _add_to_working_memory(self, entry: MemoryEntry):
        """Add to working memory with capacity management."""
        self.working_memory.append(entry)
        
        # Evict least important if over capacity
        if len(self.working_memory) > self.working_capacity:
            self.working_memory.sort(key=lambda e: e.importance)
            evicted = self.working_memory.pop(0)
            # Ensure it's persisted
            self._persist_entry(evicted)
    
    def _search_working_memory(
        self,
        query: str = None,
        tags: List[str] = None
    ) -> List[MemoryEntry]:
        """Search working memory."""
        results = []
        for entry in self.working_memory:
            match = True
            if query and query.lower() not in entry.content.lower():
                match = False
            if tags and not any(t in entry.tags for t in tags):
                match = False
            if match:
                results.append(entry)
        
        return sorted(results, key=lambda e: e.importance, reverse=True)
    
    def _query_database(
        self,
        query: str = None,
        memory_type: str = None,
        tags: List[str] = None,
        limit: int = 10,
        since: datetime = None
    ) -> List[MemoryEntry]:
        """Query persistent storage."""
        cursor = self.conn.cursor()
        
        conditions = []
        params = []
        
        if memory_type:
            conditions.append("memory_type = ?")
            params.append(memory_type)
        
        if since:
            conditions.append("timestamp > ?")
            params.append(since.isoformat())
        
        if query:
            conditions.append("content LIKE ?")
            params.append(f"%{query}%")
        
        sql = "SELECT * FROM memories"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY importance DESC, timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        
        # Filter by tags in Python (SQLite doesn't support array operations easily)
        entries = [self._row_to_entry(row) for row in rows]
        
        if tags:
            entries = [e for e in entries if any(t in e.tags for t in tags)]
        
        return entries[:limit]
    
    def _persist_entry(self, entry: MemoryEntry):
        """Save entry to database."""
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT OR REPLACE INTO memories 
               (id, content, memory_type, timestamp, tags, importance, embeddings, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entry.id,
                entry.content,
                entry.memory_type,
                entry.timestamp.isoformat(),
                json.dumps(entry.tags),
                entry.importance,
                json.dumps(entry.embeddings) if entry.embeddings else None,
                json.dumps(entry.metadata)
            )
        )
        self.conn.commit()
    
    def _row_to_entry(self, row) -> MemoryEntry:
        """Convert database row to MemoryEntry."""
        return MemoryEntry(
            id=row[0],
            content=row[1],
            memory_type=row[2],
            timestamp=datetime.fromisoformat(row[3]),
            tags=json.loads(row[4]) if row[4] else [],
            importance=row[5],
            embeddings=json.loads(row[6]) if row[6] else None,
            metadata=json.loads(row[7]) if row[7] else {}
        )
    
    def _generate_id(self, content: str) -> str:
        """Generate unique ID for memory entry."""
        hash_input = f"{content}{datetime.now().isoformat()}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    
    def close(self):
        """Close database connection."""
        self.conn.close()
