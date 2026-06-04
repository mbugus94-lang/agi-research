"""
Context-Oriented Memory Cache (PEEK-Inspired)

Inspired by:
- "PEEK: Context Map as an Orientation Cache for Long-Context LLM Agents"
  (arXiv:2605.19932v1, Zhuohan Gu, Qizheng Zhang, Omar Khattab, Samuel Madden)
- Long-context LLM agent efficiency research
- Resource-rational memory principles

Problem it solves:
  Long-context LLM agents re-process or re-retrieve the same context across
  recurring tasks. This is expensive (token cost) and slow. PEEK proposes a
  reusable "context map" that captures (a) what the context contains,
  (b) how it's organized, and (c) which elements have historically been
  useful. The agent orients itself through the cache instead of re-reading
  raw context.

This module implements a PEEK-style orientation cache that is decoupled from
any particular LLM provider or vector DB. It is designed to plug into the
existing tiered_memory / enhanced_memory / metacognitive_monitor pipeline.

Key components:
1. ContextEntry        - a single reusable entry in the orientation cache
2. AccessRecord        - log entry for a cache hit/miss/save
3. DistillationResult  - what was extracted from an execution trace
4. Distiller           - extracts transferable patterns from successful runs
5. Cartographer        - translates distilled patterns into cache edits
6. EvictionPolicy      - strategy enum (LRU, LFU, COST_AWARE, HYBRID)
7. Evictor             - applies a policy within a token budget
8. ContextMap          - the orientation cache itself
9. ContextOrientedAgent- thin integration helper
10. Convenience functions: create_cache, create_agent

Design principles:
- No external deps (works in sandbox; no vector DB, no LLM)
- Token-budget aware: every entry declares its cost
- Cost savings are tracked and exposed (for metacognitive monitor to consume)
- Deterministic and testable; deterministic keys for cache lookups
- Replay-safe: distillation + cartography is a pure function of inputs
"""

from __future__ import annotations

import hashlib
import math
import time
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CacheEntryKind(Enum):
    """Types of entries that can live in the orientation cache."""
    FACT = "fact"                     # Atomic piece of information
    SCHEMA = "schema"                 # Structure / organization of data
    PATTERN = "pattern"               # Recurring usage pattern
    INSTRUCTION = "instruction"       # User / domain-specific instruction
    TOOL_TRACE = "tool_trace"         # Successful tool invocation summary
    SUMMARY = "summary"               # Distilled summary of a context region


class AccessOutcome(Enum):
    HIT = "hit"
    MISS = "miss"
    SAVE = "save"
    EVICT = "evict"
    UPDATE = "update"


class EditAction(Enum):
    ADD = "add"
    UPDATE = "update"
    REMOVE = "remove"
    NOOP = "noop"


class EvictionPolicy(Enum):
    LRU = "lru"               # Least recently used
    LFU = "lfu"               # Least frequently used
    COST_AWARE = "cost_aware" # Highest cost-per-hit first
    HYBRID = "hybrid"         # Weighted blend of recency, frequency, cost


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ContextEntry:
    """A single entry in the orientation cache."""
    entry_id: str
    key: str
    kind: CacheEntryKind
    content: str
    token_cost: int                          # Estimated token cost to use this entry
    priority: float = 0.5                    # 0.0 - 1.0; higher = keep longer
    hit_count: int = 0
    miss_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def record_hit(self) -> None:
        self.hit_count += 1
        self.last_accessed = time.time()

    def record_miss(self) -> None:
        self.miss_count += 1

    @property
    def access_count(self) -> int:
        return self.hit_count + self.miss_count

    @property
    def hit_rate(self) -> float:
        if self.access_count == 0:
            return 0.0
        return self.hit_count / self.access_count

    @property
    def value_density(self) -> float:
        """Hits per token - higher is better for keeping this entry."""
        if self.token_cost <= 0:
            return float(self.hit_count)
        return self.hit_count / self.token_cost

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "key": self.key,
            "kind": self.kind.value,
            "content": self.content,
            "token_cost": self.token_cost,
            "priority": self.priority,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "last_accessed": self.last_accessed,
            "created_at": self.created_at,
            "value_density": self.value_density,
            "metadata": dict(self.metadata),
        }


@dataclass
class AccessRecord:
    """Audit log entry for cache activity."""
    record_id: str
    outcome: AccessOutcome
    key: str
    timestamp: float = field(default_factory=time.time)
    saved_tokens: int = 0
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "outcome": self.outcome.value,
            "key": self.key,
            "timestamp": self.timestamp,
            "saved_tokens": self.saved_tokens,
            "detail": self.detail,
        }


@dataclass
class DistillationResult:
    """What the Distiller extracted from an execution trace."""
    facts: List[Tuple[str, str]] = field(default_factory=list)        # (key, content)
    patterns: List[Tuple[str, str]] = field(default_factory=list)     # (key, content)
    schemas: List[Tuple[str, str]] = field(default_factory=list)      # (key, content)
    summaries: List[Tuple[str, str]] = field(default_factory=list)    # (key, content)
    tool_traces: List[Tuple[str, str]] = field(default_factory=list)  # (key, content)

    def is_empty(self) -> bool:
        return not any([self.facts, self.patterns, self.schemas,
                        self.summaries, self.tool_traces])

    def total_items(self) -> int:
        return (len(self.facts) + len(self.patterns) + len(self.schemas)
                + len(self.summaries) + len(self.tool_traces))


@dataclass
class CartographyEdit:
    """A single edit produced by the Cartographer."""
    action: EditAction
    key: str
    kind: CacheEntryKind
    content: str = ""
    token_cost: int = 0
    priority: float = 0.5
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Distiller
# ---------------------------------------------------------------------------


def _normalize_key(text: str) -> str:
    return " ".join(text.lower().strip().split())


def _deterministic_key(prefix: str, payload: str) -> str:
    """Stable, collision-resistant key for cache lookups."""
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}:{_normalize_key(payload)[:80]}:{digest}"


class Distiller:
    """
    Extracts reusable orientation patterns from an execution trace.

    A trace is any iterable of (role, content) tuples or any object that
    exposes a `.messages` attribute. The Distiller is intentionally simple
    and deterministic so it can be tested without an LLM:

    - "facts"           : short imperative / declarative sentences
    - "patterns"        : tool invocations / repeated phrases
    - "schemas"         : structural markers (lists, tables, sections)
    - "summaries"       : longer narrative blocks (>120 chars)
    - "tool_traces"     : lines starting with "tool:" or "use "
    """

    FACT_HINTS = (" is ", " are ", " means ", " equals ", " == ",
                  " contains ", " has ", " was ", " were ")
    SCHEMA_HINTS = ("# ", "## ", "### ", "- ", "* ", "1.", "2.", "3.",
                    "{", "[", "|", ":")
    TOOL_HINTS = ("tool:", "use ", "call ", "invoke ", "exec ")

    def __init__(
        self,
        min_fact_len: int = 4,
        max_fact_len: int = 240,
        summary_min_len: int = 120,
    ):
        self.min_fact_len = min_fact_len
        self.max_fact_len = max_fact_len
        self.summary_min_len = summary_min_len

    def distill(
        self,
        trace: Iterable[Any],
        source_label: str = "trace",
    ) -> DistillationResult:
        result = DistillationResult()
        seen: set = set()

        messages = self._coerce_messages(trace)
        for idx, (role, content) in enumerate(messages):
            content = (content or "").strip()
            if not content:
                continue

            for raw_line in content.splitlines():
                line = raw_line.strip()
                if not line:
                    continue

                lower = line.lower()
                bucket, key, body = None, None, None

                if any(lower.startswith(h) for h in self.TOOL_HINTS):
                    bucket = result.tool_traces
                    key = _deterministic_key("tool", line)
                    body = line[: self.max_fact_len]
                elif any(line.startswith(h) for h in self.SCHEMA_HINTS):
                    bucket = result.schemas
                    key = _deterministic_key("schema", line)
                    body = line[: self.max_fact_len]
                elif (
                    self.min_fact_len <= len(line) <= self.max_fact_len
                    and any(h in lower for h in self.FACT_HINTS)
                ):
                    bucket = result.facts
                    key = _deterministic_key("fact", line)
                    body = line
                elif len(line) >= self.summary_min_len:
                    bucket = result.summaries
                    key = _deterministic_key("summary", f"{source_label}:{idx}")
                    body = line[: self.max_fact_len] + ("..." if len(line) > self.max_fact_len else "")
                elif role == "assistant" and len(line) <= self.max_fact_len:
                    bucket = result.patterns
                    key = _deterministic_key("pattern", line)
                    body = line
                else:
                    continue

                if key in seen:
                    continue
                seen.add(key)
                bucket.append((key, body))

        return result

    @staticmethod
    def _coerce_messages(trace: Iterable[Any]) -> List[Tuple[str, str]]:
        out: List[Tuple[str, str]] = []
        for item in trace:
            if isinstance(item, tuple) and len(item) >= 2:
                role, content = item[0], item[1]
            elif isinstance(item, dict):
                role = item.get("role", "user")
                content = item.get("content", "")
            elif hasattr(item, "role") and hasattr(item, "content"):
                role, content = item.role, item.content
            else:
                role, content = "user", str(item)
            out.append((str(role), str(content)))
        return out


# ---------------------------------------------------------------------------
# Cartographer
# ---------------------------------------------------------------------------


class Cartographer:
    """
    Translates a DistillationResult into a list of CartographyEdits
    that can be applied to a ContextMap.

    Policy:
    - Deduplicate: identical content produces NOOP
    - Promote: re-seeing a key -> UPDATE (raise priority, refresh content)
    - Demote low-quality: very short lines are removed
    - Token-cost aware: estimates cost as len(content)//4
    """

    MIN_CONTENT_LEN = 6
    MAX_CONTENT_LEN = 4000
    TOKEN_COST_DIVISOR = 4

    def __init__(
        self,
        default_priority: float = 0.5,
        update_priority_boost: float = 0.05,
        update_priority_cap: float = 0.95,
    ):
        self.default_priority = default_priority
        self.update_priority_boost = update_priority_boost
        self.update_priority_cap = update_priority_cap

    def plan(
        self,
        result: DistillationResult,
        existing: Dict[str, ContextEntry],
    ) -> List[CartographyEdit]:
        edits: List[CartographyEdit] = []

        for bucket, kind in (
            (result.facts, CacheEntryKind.FACT),
            (result.patterns, CacheEntryKind.PATTERN),
            (result.schemas, CacheEntryKind.SCHEMA),
            (result.summaries, CacheEntryKind.SUMMARY),
            (result.tool_traces, CacheEntryKind.TOOL_TRACE),
        ):
            for key, content in bucket:
                if len(content) < self.MIN_CONTENT_LEN:
                    edits.append(CartographyEdit(
                        action=EditAction.NOOP, key=key, kind=kind,
                        reason="content too short"))
                    continue
                if len(content) > self.MAX_CONTENT_LEN:
                    content = content[: self.MAX_CONTENT_LEN] + "..."

                token_cost = max(1, len(content) // self.TOKEN_COST_DIVISOR)

                if key in existing:
                    entry = existing[key]
                    new_priority = min(
                        self.update_priority_cap,
                        entry.priority + self.update_priority_boost,
                    )
                    edits.append(CartographyEdit(
                        action=EditAction.UPDATE, key=key, kind=kind,
                        content=content, token_cost=token_cost,
                        priority=new_priority,
                        reason="re-seen key; refresh priority",
                    ))
                else:
                    edits.append(CartographyEdit(
                        action=EditAction.ADD, key=key, kind=kind,
                        content=content, token_cost=token_cost,
                        priority=self.default_priority,
                        reason="new orientation entry",
                    ))

        # Deduplicate ADD/UPADTE for the same key, keep the later one
        dedup: Dict[str, CartographyEdit] = {}
        for edit in edits:
            if edit.action in (EditAction.ADD, EditAction.UPDATE):
                dedup[edit.key] = edit
        return list(dedup.values()) + [e for e in edits if e.action == EditAction.NOOP]


# ---------------------------------------------------------------------------
# Evictor
# ---------------------------------------------------------------------------


class Evictor:
    """Applies an eviction policy to bring cache token usage under budget."""

    def __init__(self, policy: EvictionPolicy = EvictionPolicy.HYBRID,
                 recency_weight: float = 0.4,
                 frequency_weight: float = 0.4,
                 cost_weight: float = 0.2):
        self.policy = policy
        self.recency_weight = recency_weight
        self.frequency_weight = frequency_weight
        self.cost_weight = cost_weight

    def _score(self, entry: ContextEntry, now: float, max_cost: int) -> float:
        """Higher score = keep longer."""
        age = max(0.001, now - entry.last_accessed)
        recency = 1.0 / (1.0 + math.log1p(age))
        frequency = math.log1p(entry.hit_count) / math.log1p(max(2, max_cost))
        cost_penalty = (entry.token_cost / max(1, max_cost))
        if self.policy == EvictionPolicy.LRU:
            return recency
        if self.policy == EvictionPolicy.LFU:
            return frequency
        if self.policy == EvictionPolicy.COST_AWARE:
            return -cost_penalty
        # HYBRID
        return (self.recency_weight * recency
                + self.frequency_weight * frequency
                - self.cost_weight * cost_penalty)

    def select_evictions(
        self,
        entries: List[ContextEntry],
        current_tokens: int,
        target_tokens: int,
    ) -> List[ContextEntry]:
        if current_tokens <= target_tokens or not entries:
            return []
        now = time.time()
        max_cost = max((e.token_cost for e in entries), default=1)
        scored = sorted(
            entries,
            key=lambda e: self._score(e, now, max_cost),
        )
        to_evict: List[ContextEntry] = []
        running = current_tokens
        for entry in scored:
            if running <= target_tokens:
                break
            to_evict.append(entry)
            running -= entry.token_cost
        return to_evict


# ---------------------------------------------------------------------------
# ContextMap (the orientation cache)
# ---------------------------------------------------------------------------


@dataclass
class CacheStats:
    """Aggregate statistics for the orientation cache."""
    size: int = 0
    total_tokens: int = 0
    hits: int = 0
    misses: int = 0
    saves: int = 0
    evictions: int = 0
    updates: int = 0
    saved_tokens_total: int = 0

    @property
    def total_lookups(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        if self.total_lookups == 0:
            return 0.0
        return self.hits / self.total_lookups

    def to_dict(self) -> Dict[str, Any]:
        return {
            "size": self.size,
            "total_tokens": self.total_tokens,
            "hits": self.hits,
            "misses": self.misses,
            "saves": self.saves,
            "evictions": self.evictions,
            "updates": self.updates,
            "saved_tokens_total": self.saved_tokens_total,
            "hit_rate": self.hit_rate,
        }


class ContextMap:
    """
    PEEK-inspired orientation cache with token-budget awareness.

    - lookups by deterministic key
    - admits new entries via Cartographer
    - evicts via Evictor to respect token budget
    - tracks per-entry hit/miss and saved tokens
    - exposes stats suitable for the metacognitive monitor
    """

    def __init__(
        self,
        token_budget: int = 4000,
        eviction_policy: EvictionPolicy = EvictionPolicy.HYBRID,
        distiller: Optional[Distiller] = None,
        cartographer: Optional[Cartographer] = None,
        evictor: Optional[Evictor] = None,
    ):
        self.token_budget = token_budget
        self.entries: Dict[str, ContextEntry] = {}
        self.history: List[AccessRecord] = []
        self.stats = CacheStats()
        self.distiller = distiller or Distiller()
        self.cartographer = cartographer or Cartographer()
        self.evictor = evictor or Evictor(policy=eviction_policy)

    # ---------------- core lookups ----------------

    def get(self, key: str) -> Optional[ContextEntry]:
        entry = self.entries.get(key)
        if entry is None:
            self.stats.misses += 1
            self.history.append(AccessRecord(
                record_id=str(uuid.uuid4()),
                outcome=AccessOutcome.MISS,
                key=key,
                detail="not in cache",
            ))
            return None
        entry.record_hit()
        self.stats.hits += 1
        self.stats.saved_tokens_total += entry.token_cost
        self.history.append(AccessRecord(
            record_id=str(uuid.uuid4()),
            outcome=AccessOutcome.HIT,
            key=key,
            saved_tokens=entry.token_cost,
        ))
        return entry

    def contains(self, key: str) -> bool:
        return key in self.entries

    # ---------------- writes ----------------

    def put(self, key: str, content: str, kind: CacheEntryKind,
            token_cost: Optional[int] = None,
            priority: float = 0.5,
            metadata: Optional[Dict[str, Any]] = None) -> ContextEntry:
        token_cost = token_cost if token_cost is not None else max(1, len(content) // 4)
        existing = self.entries.get(key)
        if existing is not None:
            existing.content = content
            existing.token_cost = token_cost
            existing.priority = min(0.95, existing.priority + 0.05)
            existing.metadata.update(metadata or {})
            self.stats.updates += 1
            self.history.append(AccessRecord(
                record_id=str(uuid.uuid4()),
                outcome=AccessOutcome.UPDATE,
                key=key,
                detail="updated in place",
            ))
            self._enforce_budget()
            return existing
        entry = ContextEntry(
            entry_id=str(uuid.uuid4()),
            key=key,
            kind=kind,
            content=content,
            token_cost=token_cost,
            priority=priority,
            metadata=dict(metadata or {}),
        )
        self.entries[key] = entry
        self.stats.saves += 1
        self.stats.size = len(self.entries)
        self.stats.total_tokens += token_cost
        self.history.append(AccessRecord(
            record_id=str(uuid.uuid4()),
            outcome=AccessOutcome.SAVE,
            key=key,
            saved_tokens=token_cost,
            detail=f"added {kind.value}",
        ))
        self._enforce_budget()
        return entry

    def remove(self, key: str) -> bool:
        entry = self.entries.pop(key, None)
        if entry is None:
            return False
        self.stats.size = len(self.entries)
        self.stats.total_tokens = max(0, self.stats.total_tokens - entry.token_cost)
        self.stats.evictions += 1
        self.history.append(AccessRecord(
            record_id=str(uuid.uuid4()),
            outcome=AccessOutcome.EVICT,
            key=key,
            saved_tokens=entry.token_cost,
            detail="manual remove",
        ))
        return True

    # ---------------- cartography-driven ingest ----------------

    def ingest_trace(
        self,
        trace: Iterable[Any],
        source_label: str = "trace",
    ) -> List[CartographyEdit]:
        """Run Distiller + Cartographer, apply edits, evict to budget."""
        result = self.distiller.distill(trace, source_label=source_label)
        edits = self.cartographer.plan(result, self.entries)
        applied: List[CartographyEdit] = []
        for edit in edits:
            if edit.action == EditAction.ADD:
                self.put(edit.key, edit.content, edit.kind,
                         token_cost=edit.token_cost, priority=edit.priority,
                         metadata={"reason": edit.reason})
                applied.append(edit)
            elif edit.action == EditAction.UPDATE:
                self.put(edit.key, edit.content, edit.kind,
                         token_cost=edit.token_cost, priority=edit.priority,
                         metadata={"reason": edit.reason})
                applied.append(edit)
        return applied

    # ---------------- budget enforcement ----------------

    def _enforce_budget(self) -> None:
        if self.stats.total_tokens <= self.token_budget:
            return
        evicted = self.evictor.select_evictions(
            list(self.entries.values()),
            self.stats.total_tokens,
            self.token_budget,
        )
        for entry in evicted:
            self.remove(entry.key)

    # ---------------- introspection ----------------

    def top_entries(self, n: int = 5) -> List[ContextEntry]:
        return sorted(self.entries.values(),
                      key=lambda e: e.value_density, reverse=True)[:n]

    def describe(self) -> Dict[str, Any]:
        return {
            "budget": self.token_budget,
            "stats": self.stats.to_dict(),
            "top_entries": [e.to_dict() for e in self.top_entries()],
            "policy": self.evictor.policy.value,
        }

    def clear(self) -> None:
        self.entries.clear()
        self.history.clear()
        self.stats = CacheStats()


# ---------------------------------------------------------------------------
# Agent-level integration helper
# ---------------------------------------------------------------------------


class ContextOrientedAgent:
    """
    Thin wrapper that shows how a BaseAgent would consume the orientation
    cache: look up by key before reading raw context, and ingest a trace
    after a successful run.
    """

    def __init__(
        self,
        name: str,
        cache: Optional[ContextMap] = None,
        token_budget: int = 4000,
    ):
        self.name = name
        self.cache = cache or ContextMap(token_budget=token_budget)
        self.runs: List[Dict[str, Any]] = []

    def consult(self, key: str) -> Optional[ContextEntry]:
        entry = self.cache.get(key)
        if entry is not None:
            entry.record_hit()  # double-count safe; idempotent
        return entry

    def remember(self, trace: Iterable[Any], source_label: str = "") -> List[CartographyEdit]:
        edits = self.cache.ingest_trace(trace, source_label=source_label or self.name)
        self.runs.append({
            "timestamp": time.time(),
            "source_label": source_label or self.name,
            "edits": len(edits),
            "cache_stats": self.cache.stats.to_dict(),
        })
        return edits

    def summary(self) -> Dict[str, Any]:
        return {
            "agent": self.name,
            "cache": self.cache.describe(),
            "runs": len(self.runs),
        }


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------


def create_cache(
    token_budget: int = 4000,
    policy: EvictionPolicy = EvictionPolicy.HYBRID,
) -> ContextMap:
    return ContextMap(token_budget=token_budget, eviction_policy=policy)


def create_agent(
    name: str = "context_oriented_agent",
    token_budget: int = 4000,
    policy: EvictionPolicy = EvictionPolicy.HYBRID,
) -> ContextOrientedAgent:
    return ContextOrientedAgent(
        name=name,
        cache=ContextMap(token_budget=token_budget, eviction_policy=policy),
    )
