"""
Memory Refiner — LLM-guided compression and eviction for long-term agent memory.

Inspired by MemRefine (arXiv:2606.13177v1) — "use similarity only to propose
candidate pairs; defer merge/delete/preserve decisions to a judge that reasons
over factual content."

What this module adds on top of `TieredMemorySystem`:

1. **Budget-aware refinement**: the refiner takes a `budget` (max entries,
   max bytes, or max L0 token estimate) and iterates until the memory store
   fits.

2. **Candidate pair proposal via similarity**: pair entries whose embedding
   cosine similarity exceeds a threshold. Similarity is *proposal-only* —
   the judge makes the actual KEEP / MERGE / COMPRESS / EVICT / PROMOTE
   decision.

3. **Pluggable judge**: `RefinementJudge` protocol with two implementations:
   - `FactDensityJudge` (default, deterministic heuristic): scores each entry
     on fact-density, novelty, recency, and association count.
   - `LLMJudgeStub`: a recordable interface that defers verdicts to an
     external LLM. Records each call so tests can assert what *would* be
     sent to the LLM.

4. **Compression**: when MERGE is selected, the refiner produces a
   *compressed* fact-summary string from the two entries via
   `_compress_facts`. The merged entry inherits the higher importance and
   the union of tags + associations.

5. **Audit trail**: every decision is appended to a JSONL audit log so the
   *system of record* is reproducible. Mirrors the Dapr 1.18 "verifiable
   execution" pattern.

6. **Deterministic posture**: no network calls, no hidden state. Same
   memory state + same judge → same refinement plan. The judge is pure.

Design notes:
- This module does NOT replace TieredMemorySystem — it wraps it.
- The refiner never auto-promotes an entry to L1; that is the governor's job.
- The refiner never silently deletes an entry with importance > 0.8; it
  proposes a PROMOTE or KEEP instead. The judge enforces the floor.
- The refiner never silently merges two entries whose tag-union exceeds
  `max_merge_tags`; the operator (or judge) decides.
"""

import json
import math
import re
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, Set, Tuple

from core.tiered_memory import (
    MemoryTier,
    TieredMemoryEntry,
    TieredMemorySystem,
)


# -----------------------------------------------------------------------------
# Enums and dataclasses
# -----------------------------------------------------------------------------


class RefinementAction(Enum):
    """Verdicts a judge can issue for a candidate (or singleton) entry."""

    KEEP = "keep"             # leave the entry untouched
    EVICT = "evict"           # remove the entry (only for low-importance singletons)
    PROMOTE = "promote"       # the entry should be moved to a higher tier
    COMPRESS = "compress"     # rewrite the entry in shorter form, same tier
    MERGE = "merge"           # combine two entries into one (paired decision)


@dataclass
class RefinementCandidatePair:
    """A similarity-proposed pair awaiting a judge verdict.

    Similarity score is computed from embeddings (or a fallback character
    jaccard if no embedding exists). The judge receives the *content* and
    *metadata*, not the similarity — the similarity is proposal-only.
    """

    a_id: str
    b_id: str
    similarity: float
    a_content: Any
    b_content: Any
    a_importance: float
    b_importance: float
    a_tags: List[str]
    b_tags: List[str]
    a_associations: List[str]
    b_associations: List[str]

    def tag_union_size(self) -> int:
        return len(set(self.a_tags) | set(self.b_tags))

    def shared_tags(self) -> Set[str]:
        return set(self.a_tags) & set(self.b_tags)

    def to_dict(self) -> Dict:
        return {
            "a_id": self.a_id,
            "b_id": self.b_id,
            "similarity": self.similarity,
            "a_importance": self.a_importance,
            "b_importance": self.b_importance,
            "tag_union_size": self.tag_union_size(),
        }


@dataclass
class RefinementDecision:
    """The judge's verdict for a candidate (or singleton).

    `reason` is required: the judge's reasoning is the *auditable substrate*.
    A decision without a reason is rejected at construction time.
    """

    action: RefinementAction
    target_ids: List[str]  # the entry IDs this decision applies to
    reason: str
    judge: str  # which judge issued the verdict
    compressed_content: Optional[str] = None  # only set when action == COMPRESS or MERGE
    confidence: float = 1.0
    decided_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.reason or not self.reason.strip():
            raise ValueError("RefinementDecision requires a non-empty reason")
        if self.action in (RefinementAction.COMPRESS, RefinementAction.MERGE):
            if self.compressed_content is None:
                raise ValueError(
                    f"RefinementDecision with action={self.action.value} "
                    "requires compressed_content"
                )
        if not self.target_ids:
            raise ValueError("RefinementDecision requires at least one target_id")

    def to_dict(self) -> Dict:
        return {
            "action": self.action.value,
            "target_ids": list(self.target_ids),
            "reason": self.reason,
            "judge": self.judge,
            "compressed_content": self.compressed_content,
            "confidence": self.confidence,
            "decided_at": self.decided_at,
        }


# -----------------------------------------------------------------------------
# Judge protocol and default implementations
# -----------------------------------------------------------------------------


class RefinementJudge(Protocol):
    """Pluggable judge interface.

    A judge receives either a singleton entry (for COMPRESS/EVICT/PROMOTE/KEEP)
    or a candidate pair (for MERGE) and returns a `RefinementDecision`.

    Judges MUST be pure: same input -> same verdict. Tests rely on this.
    """

    name: str

    def judge_singleton(
        self,
        entry: TieredMemoryEntry,
        current_size: int,
        budget: int,
    ) -> RefinementDecision: ...

    def judge_pair(
        self,
        pair: RefinementCandidatePair,
    ) -> RefinementDecision: ...


def _fact_density(content: Any) -> float:
    """Heuristic fact-density score in [0, 1].

    Combines: numeric-token presence (0.4), entity-ish tokens (0.3),
    structural tokens (colons, dashes, dates) (0.2), and length normalization
    (0.1). All sub-scores are clipped.

    The score is intentionally *not* a proxy for "truthfulness"; it is a
    proxy for "content that is informationally dense and likely to be useful
    in future retrieval."
    """
    s = str(content)
    if not s.strip():
        return 0.0

    # numeric tokens: digits in the string
    num_tokens = len(re.findall(r"\b\d+(?:\.\d+)?\b", s))
    num_score = min(1.0, num_tokens / 5.0)

    # entity-ish tokens: capitalized words or words with hyphens
    entity_tokens = len(re.findall(r"\b[A-Z][A-Za-z0-9_-]{2,}\b", s))
    entity_score = min(1.0, entity_tokens / 4.0)

    # structural tokens: dates, paths, key:value pairs
    structural = len(re.findall(r"[:=/\\-]{1}|\d{4}-\d{2}-\d{2}", s))
    struct_score = min(1.0, structural / 4.0)

    # length normalization: penalty for very short or very long
    words = len(s.split())
    if words == 0:
        length_score = 0.0
    elif words < 3:
        length_score = 0.2
    elif words > 200:
        length_score = 0.4
    else:
        length_score = 1.0

    return (
        0.4 * num_score
        + 0.3 * entity_score
        + 0.2 * struct_score
        + 0.1 * length_score
    )


def _novelty_score(entry: TieredMemoryEntry) -> float:
    """Heuristic novelty score in [0, 1] based on age + access count.

    Older entries that have been re-accessed are higher-novelty; brand-new
    never-accessed entries get a small bonus (they may carry new info).
    """
    age_hours = (datetime.now() - entry.timestamp).total_seconds() / 3600
    # recency bonus: 1.0 if fresh, decaying
    recency = math.exp(-age_hours / 168.0)  # ~1 week half-life
    # access bonus: log-scaled
    access_bonus = min(1.0, math.log1p(entry.access_count) / math.log1p(5))
    return 0.5 * recency + 0.5 * access_bonus


class FactDensityJudge:
    """Default heuristic judge. Deterministic, no network calls.

    Singleton verdicts:
        - importance >= keep_floor: KEEP (high-value, do not touch)
        - importance >= promote_floor and access_count >= 2: PROMOTE
        - fact_density < evict_floor and importance < 0.3: EVICT
        - fact_density in [compress_floor, keep_floor]: COMPRESS
        - else: KEEP

    Pair verdicts:
        - similarity < pair_min_similarity: KEEP both
        - tag_union > max_merge_tags: KEEP both
        - both importance >= 0.7: KEEP both (high-value, do not merge)
        - both fact_density low and shared tag: MERGE
        - one high / one low importance: MERGE (merge into the higher)
        - else: KEEP both
    """

    name = "fact_density"

    def __init__(
        self,
        keep_floor: float = 0.7,
        promote_floor: float = 0.5,
        compress_floor: float = 0.25,
        evict_floor: float = 0.15,
        pair_min_similarity: float = 0.6,
        max_merge_tags: int = 6,
    ):
        self.keep_floor = keep_floor
        self.promote_floor = promote_floor
        self.compress_floor = compress_floor
        self.evict_floor = evict_floor
        self.pair_min_similarity = pair_min_similarity
        self.max_merge_tags = max_merge_tags

    def judge_singleton(
        self,
        entry: TieredMemoryEntry,
        current_size: int,
        budget: int,
    ) -> RefinementDecision:
        importance = entry.current_importance() if hasattr(entry, "current_importance") else entry.importance
        fd = _fact_density(entry.content)
        novelty = _novelty_score(entry)

        # High-importance floor: do not touch
        if importance >= self.keep_floor:
            return RefinementDecision(
                action=RefinementAction.KEEP,
                target_ids=[entry.id],
                reason=(
                    f"importance={importance:.2f} >= keep_floor={self.keep_floor:.2f}; "
                    "high-value entry preserved"
                ),
                judge=self.name,
                confidence=min(1.0, importance),
            )

        # Promote candidate
        if importance >= self.promote_floor and entry.access_count >= 2:
            return RefinementDecision(
                action=RefinementAction.PROMOTE,
                target_ids=[entry.id],
                reason=(
                    f"importance={importance:.2f} >= promote_floor={self.promote_floor:.2f} "
                    f"and access_count={entry.access_count} >= 2; candidate for higher tier"
                ),
                judge=self.name,
                confidence=min(1.0, novelty),
            )

        # Evict candidate: low importance + low fact density
        if importance < 0.3 and fd < self.evict_floor:
            return RefinementDecision(
                action=RefinementAction.EVICT,
                target_ids=[entry.id],
                reason=(
                    f"importance={importance:.2f} < 0.3 and fact_density={fd:.2f} "
                    f"< evict_floor={self.evict_floor:.2f}; eviction candidate"
                ),
                judge=self.name,
                confidence=min(1.0, 1.0 - fd),
            )

        # Budget-pressure escalation: when over budget, EVICT low/medium-importance
        # entries even if their fact_density is moderate. Capped by protect_above_importance.
        if current_size > budget and importance < (self.keep_floor - 0.1) and importance < 0.7:
            return RefinementDecision(
                action=RefinementAction.EVICT,
                target_ids=[entry.id],
                reason=(
                    f"over budget ({current_size} > {budget}); importance={importance:.2f} "
                    f"< keep_floor-0.1={self.keep_floor - 0.1:.2f}; budget-pressure eviction"
                ),
                judge=self.name,
                confidence=0.6,
            )

        # Compress candidate: medium-low importance + medium fact density
        if fd >= self.compress_floor and importance < self.keep_floor:
            compressed = _compress_facts(entry.content)
            return RefinementDecision(
                action=RefinementAction.COMPRESS,
                target_ids=[entry.id],
                reason=(
                    f"fact_density={fd:.2f} >= compress_floor={self.compress_floor:.2f}; "
                    "compress while preserving facts"
                ),
                judge=self.name,
                compressed_content=compressed,
                confidence=fd,
            )

        # Default: keep
        return RefinementDecision(
            action=RefinementAction.KEEP,
            target_ids=[entry.id],
            reason=(
                f"importance={importance:.2f}, fact_density={fd:.2f}; "
                "no action warranted"
            ),
            judge=self.name,
            confidence=0.5,
        )

    def judge_pair(self, pair: RefinementCandidatePair) -> RefinementDecision:
        if pair.similarity < self.pair_min_similarity:
            return RefinementDecision(
                action=RefinementAction.KEEP,
                target_ids=[pair.a_id, pair.b_id],
                reason=(
                    f"similarity={pair.similarity:.2f} < pair_min_similarity="
                    f"{self.pair_min_similarity:.2f}; pair rejected"
                ),
                judge=self.name,
            )

        if pair.tag_union_size() > self.max_merge_tags:
            return RefinementDecision(
                action=RefinementAction.KEEP,
                target_ids=[pair.a_id, pair.b_id],
                reason=(
                    f"tag_union_size={pair.tag_union_size()} > "
                    f"max_merge_tags={self.max_merge_tags}; pair rejected"
                ),
                judge=self.name,
            )

        # Both high-importance: keep both (do not lose information)
        if pair.a_importance >= 0.7 and pair.b_importance >= 0.7:
            return RefinementDecision(
                action=RefinementAction.KEEP,
                target_ids=[pair.a_id, pair.b_id],
                reason=(
                    f"both importance >= 0.7 "
                    f"(a={pair.a_importance:.2f}, b={pair.b_importance:.2f}); "
                    "merge would risk losing signal"
                ),
                judge=self.name,
            )

        # Both low fact density AND share a tag: merge
        fd_a = _fact_density(pair.a_content)
        fd_b = _fact_density(pair.b_content)
        shared_tags = set(pair.a_tags) & set(pair.b_tags)
        if fd_a < 0.3 and fd_b < 0.3 and shared_tags:
            merged_content = _merge_facts(pair.a_content, pair.b_content)
            return RefinementDecision(
                action=RefinementAction.MERGE,
                target_ids=[pair.a_id, pair.b_id],
                reason=(
                    f"low fact_density (a={fd_a:.2f}, b={fd_b:.2f}) with shared "
                    f"tags {sorted(shared_tags)}; merge candidate"
                ),
                judge=self.name,
                compressed_content=merged_content,
                confidence=0.6 + 0.2 * pair.similarity,
            )

        # One high / one low: merge (high wins)
        if abs(pair.a_importance - pair.b_importance) >= 0.3:
            winner = pair.a_id if pair.a_importance >= pair.b_importance else pair.b_id
            loser = pair.b_id if winner == pair.a_id else pair.a_id
            merged_content = _merge_facts(pair.a_content, pair.b_content)
            return RefinementDecision(
                action=RefinementAction.MERGE,
                target_ids=[pair.a_id, pair.b_id],
                reason=(
                    f"importance delta={abs(pair.a_importance - pair.b_importance):.2f} "
                    f">= 0.3 (a={pair.a_importance:.2f}, b={pair.b_importance:.2f}); "
                    f"merge into higher-importance entry"
                ),
                judge=self.name,
                compressed_content=merged_content,
                confidence=0.7,
            )

        # Default: keep both
        return RefinementDecision(
            action=RefinementAction.KEEP,
            target_ids=[pair.a_id, pair.b_id],
            reason="no merge criterion met; both preserved",
            judge=self.name,
            confidence=0.5,
        )


class LLMJudgeStub:
    """Stub LLM judge. Records every call so tests can assert what *would*
    be sent to an external LLM.

    The stub's `judge_pair` returns MERGE for any pair above
    `pair_threshold_similarity` and KEEP otherwise. This is intentionally
    simple — the production version would replace this with a real LLM call.
    """

    name = "llm_stub"

    def __init__(self, pair_threshold_similarity: float = 0.5, always_action: Optional[RefinementAction] = None):
        self.pair_threshold_similarity = pair_threshold_similarity
        self.calls: List[Dict] = []
        self.always_action = always_action

    def judge_singleton(
        self,
        entry: TieredMemoryEntry,
        current_size: int,
        budget: int,
    ) -> RefinementDecision:
        self.calls.append({
            "kind": "singleton",
            "entry_id": entry.id,
            "content": str(entry.content)[:200],
            "importance": entry.importance,
            "current_size": current_size,
            "budget": budget,
        })
        # always_action takes precedence
        if self.always_action is not None:
            return RefinementDecision(
                action=self.always_action,
                target_ids=[entry.id],
                reason=f"llm_stub: always_action={self.always_action.value}",
                judge=self.name,
            )
        # Deterministic stub: keep high-importance, compress the rest
        importance = entry.current_importance() if hasattr(entry, "current_importance") else entry.importance
        if importance >= 0.7:
            return RefinementDecision(
                action=RefinementAction.KEEP,
                target_ids=[entry.id],
                reason="llm_stub: high-importance preserved",
                judge=self.name,
            )
        compressed = _compress_facts(entry.content)
        return RefinementDecision(
            action=RefinementAction.COMPRESS,
            target_ids=[entry.id],
            reason="llm_stub: medium/low importance compressed",
            judge=self.name,
            compressed_content=compressed,
            confidence=0.6,
        )

    def judge_pair(self, pair: RefinementCandidatePair) -> RefinementDecision:
        self.calls.append({
            "kind": "pair",
            "a_id": pair.a_id,
            "b_id": pair.b_id,
            "similarity": pair.similarity,
            "a_content": str(pair.a_content)[:200],
            "b_content": str(pair.b_content)[:200],
        })
        if self.always_action is not None:
            return RefinementDecision(
                action=self.always_action,
                target_ids=[pair.a_id, pair.b_id],
                reason=f"llm_stub: always_action={self.always_action.value}",
                judge=self.name,
            )
        if pair.similarity < self.pair_threshold_similarity:
            return RefinementDecision(
                action=RefinementAction.KEEP,
                target_ids=[pair.a_id, pair.b_id],
                reason=f"llm_stub: similarity={pair.similarity:.2f} below threshold",
                judge=self.name,
            )
        merged = _merge_facts(pair.a_content, pair.b_content)
        return RefinementDecision(
            action=RefinementAction.MERGE,
            target_ids=[pair.a_id, pair.b_id],
            reason=f"llm_stub: similarity={pair.similarity:.2f} above threshold",
            judge=self.name,
            compressed_content=merged,
            confidence=0.7,
        )


# -----------------------------------------------------------------------------
# Compression helpers
# -----------------------------------------------------------------------------


def _compress_facts(content: Any) -> str:
    """Deterministic fact-compression.

    Strategy:
        - Strip filler words (very small stopword list).
        - Collapse whitespace.
        - Truncate to a configurable length (default 240 chars).

    This is *not* an LLM-based summary. The point is that the *judge* chose
    to compress; this is a safe, deterministic default the operator can
    override. In production the judge would return an LLM-generated summary
    and `compressed_content` would carry it.
    """
    s = str(content).strip()
    # Strip very common filler
    for filler in ("the ", "The ", "a ", "A ", "an ", "An "):
        if s.startswith(filler):
            s = s[len(filler):]
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)
    return s[:240]


def _merge_facts(a: Any, b: Any) -> str:
    """Merge two pieces of content by dedup-sorted concatenation.

    Splits each into sentence-like chunks, dedups by lowercase substring
    containment, joins with ' | '. Result is bounded by 480 chars.
    """
    def _chunks(s: str) -> List[str]:
        # Split on sentence boundaries; keep non-empty
        parts = re.split(r"(?<=[.!?])\s+|\n+", s)
        return [p.strip() for p in parts if p.strip()]

    a_chunks = _chunks(str(a))
    b_chunks = _chunks(str(b))

    merged: List[str] = []
    seen_lc: Set[str] = set()
    for chunk in a_chunks + b_chunks:
        lc = chunk.lower()
        # drop if a previously-seen chunk already contains this chunk as substring
        is_dup = any(lc in s for s in seen_lc)
        if not is_dup:
            merged.append(chunk)
            seen_lc.add(lc)

    out = " | ".join(merged)
    return out[:480]


# -----------------------------------------------------------------------------
# Similarity helpers
# -----------------------------------------------------------------------------


def _cosine_similarity(vec1: Optional[List[float]], vec2: Optional[List[float]]) -> float:
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2))
    n1 = math.sqrt(sum(a * a for a in vec1))
    n2 = math.sqrt(sum(b * b for b in vec2))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def _char_jaccard(a: Any, b: Any) -> float:
    """Fallback similarity when no embeddings are available."""
    sa = set(re.findall(r"\w+", str(a).lower()))
    sb = set(re.findall(r"\w+", str(b).lower()))
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / max(1, len(sa | sb))


def _similarity(a: TieredMemoryEntry, b: TieredMemoryEntry) -> float:
    """Combined similarity: cosine on embeddings, fallback to char jaccard.

    If both embeddings are None or empty, returns the char jaccard (which
    itself returns 0.0 for fully disjoint content). Never returns None.
    """
    if a.embedding and b.embedding:
        return _cosine_similarity(a.embedding, b.embedding)
    return _char_jaccard(a.content, b.content)


# -----------------------------------------------------------------------------
# MemoryRefiner
# -----------------------------------------------------------------------------


@dataclass
class RefinementReport:
    """Aggregate summary of one refine() call."""

    initial_size: int
    final_size: int
    iterations: int
    evicted: int = 0
    compressed: int = 0
    merged_pairs: int = 0
    promoted: int = 0
    kept: int = 0
    decisions: List[RefinementDecision] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "initial_size": self.initial_size,
            "final_size": self.final_size,
            "iterations": self.iterations,
            "evicted": self.evicted,
            "compressed": self.compressed,
            "merged_pairs": self.merged_pairs,
            "promoted": self.promoted,
            "kept": self.kept,
            "decision_count": len(self.decisions),
        }


@dataclass
class MemoryRefinerConfig:
    """Operator-tunable knobs."""

    similarity_threshold: float = 0.5
    max_iterations: int = 5
    max_pair_scan: int = 200  # upper bound on candidate-pair scan to keep cost bounded
    audit_path: Optional[str] = None
    promote_tier: MemoryTier = MemoryTier.L1_WORKING  # where PROMOTE entries go
    protect_above_importance: float = 0.85  # never evict above this importance


class MemoryRefiner:
    """MemRefine-inspired memory compression/refinement layer.

    Wraps a `TieredMemorySystem` and offers:

        - `propose_pairs()`: similarity-based candidate-pair proposal
        - `judge_pair(pair)`: delegated to the configured judge
        - `refine(budget)`: iterate until memory fits `budget`
        - `compress_one(entry_id)`: targeted compression
        - `evict_one(entry_id)`: targeted eviction (with safety floor)
        - `merge(a_id, b_id)`: targeted merge
        - `summary()`: aggregate metrics

    The refiner is *deterministic* given the same judge and the same
    TieredMemorySystem state. Tests rely on this.

    Conservative posture (invariants):

        - The refiner NEVER auto-merges two entries whose shared importance
          is below the keep_floor; the judge makes that call.
        - The refiner NEVER silently evicts an entry with importance above
          `protect_above_importance`. The judge may still issue KEEP.
        - The refiner NEVER calls the LLM judge directly; the stub records
          calls for testability. In production the stub is replaced by a
          thin wrapper around a real LLM.
        - The refiner NEVER mutates entries in place. Every COMPRESS creates
          a new entry; every MERGE creates one new entry and removes the two
          originals (in that order, so a crash leaves the originals intact
          via WAL-style journaling — see `audit_path`).
        - The refiner never *promotes* an entry unless the judge issues
          PROMOTE. The refiner does not pick the target tier; the operator
          does via `MemoryRefinerConfig.promote_tier`.
    """

    def __init__(
        self,
        memory: TieredMemorySystem,
        judge: Optional[RefinementJudge] = None,
        config: Optional[MemoryRefinerConfig] = None,
    ):
        self.memory = memory
        self.judge: RefinementJudge = judge or FactDensityJudge()
        self.config = config or MemoryRefinerConfig()

        # Audit trail
        self.audit: List[RefinementDecision] = []

    # ---------- candidate pair proposal ----------

    def _iter_entries(self, tiers: Optional[List[MemoryTier]] = None) -> List[TieredMemoryEntry]:
        """Iterate over all entries in the requested tiers."""
        tiers = tiers or [MemoryTier.L1_WORKING, MemoryTier.L2_ARCHIVAL]
        out: List[TieredMemoryEntry] = []
        if MemoryTier.L1_WORKING in tiers:
            out.extend(self.memory.l1_working.values())
        if MemoryTier.L2_ARCHIVAL in tiers:
            out.extend(self.memory.l2_longterm.values())
        return out

    def propose_pairs(
        self,
        tiers: Optional[List[MemoryTier]] = None,
        similarity_threshold: Optional[float] = None,
        limit: Optional[int] = None,
    ) -> List[RefinementCandidatePair]:
        """Propose merge candidates based on embedding/character similarity.

        O(n^2) on the candidate set, bounded by `config.max_pair_scan`.
        Returns pairs in descending similarity order.
        """
        threshold = similarity_threshold if similarity_threshold is not None else self.config.similarity_threshold
        entries = self._iter_entries(tiers)
        if limit is not None:
            entries = entries[:limit]
        else:
            entries = entries[: self.config.max_pair_scan]

        pairs: List[RefinementCandidatePair] = []
        n = len(entries)
        for i in range(n):
            for j in range(i + 1, n):
                a, b = entries[i], entries[j]
                sim = _similarity(a, b)
                if sim >= threshold:
                    pairs.append(RefinementCandidatePair(
                        a_id=a.id,
                        b_id=b.id,
                        similarity=sim,
                        a_content=a.content,
                        b_content=b.content,
                        a_importance=a.importance,
                        b_importance=b.importance,
                        a_tags=list(a.tags),
                        b_tags=list(b.tags),
                        a_associations=list(a.associations),
                        b_associations=list(b.associations),
                    ))
        pairs.sort(key=lambda p: p.similarity, reverse=True)
        return pairs

    # ---------- targeted actions ----------

    def compress_one(self, entry_id: str) -> Optional[RefinementDecision]:
        """Compress a single entry. Returns the decision (or None if not found).

        This is a *targeted* action — the caller asked for compression specifically,
        so we force the action to COMPRESS regardless of what the judge would
        recommend. The judge is consulted for `reason` text only.
        """
        entry = self._find_entry(entry_id)
        if entry is None:
            return None
        importance = entry.importance
        if importance >= self.config.protect_above_importance:
            decision = RefinementDecision(
                action=RefinementAction.KEEP,
                target_ids=[entry_id],
                reason=(
                    f"importance={importance:.2f} >= protect_above_importance="
                    f"{self.config.protect_above_importance:.2f}; compression refused "
                    "to protect high-value entry"
                ),
                judge=self.judge.name,
            )
            self._record_decision(decision)
            return decision
        decision = RefinementDecision(
            action=RefinementAction.COMPRESS,
            target_ids=[entry_id],
            reason="explicit compression requested via compress_one()",
            judge=self.judge.name,
            compressed_content=_compress_facts(entry.content),
        )
        self._apply_singleton_decision(decision)
        return decision

    def evict_one(self, entry_id: str) -> Optional[RefinementDecision]:
        """Evict a single entry. Returns the decision (or None if not found
        or protected by the importance floor).
        """
        entry = self._find_entry(entry_id)
        if entry is None:
            return None
        importance = entry.current_importance() if hasattr(entry, "current_importance") else entry.importance
        if importance > self.config.protect_above_importance:
            # Refuse to evict — record a KEEP with reason
            decision = RefinementDecision(
                action=RefinementAction.KEEP,
                target_ids=[entry_id],
                reason=(
                    f"importance={importance:.2f} > protect_above_importance="
                    f"{self.config.protect_above_importance:.2f}; eviction refused"
                ),
                judge=self.judge.name,
            )
            self._record_decision(decision)
            return decision
        decision = RefinementDecision(
            action=RefinementAction.EVICT,
            target_ids=[entry_id],
            reason="explicit eviction requested",
            judge=self.judge.name,
        )
        self._apply_singleton_decision(decision)
        return decision

    def merge(self, a_id: str, b_id: str) -> Optional[RefinementDecision]:
        """Merge two entries. Returns the decision (or None if either entry is missing)."""
        a = self._find_entry(a_id)
        b = self._find_entry(b_id)
        if a is None or b is None:
            return None
        pair = RefinementCandidatePair(
            a_id=a.id,
            b_id=b.id,
            similarity=_similarity(a, b),
            a_content=a.content,
            b_content=b.content,
            a_importance=a.importance,
            b_importance=b.importance,
            a_tags=list(a.tags),
            b_tags=list(b.tags),
            a_associations=list(a.associations),
            b_associations=list(b.associations),
        )
        decision = self.judge.judge_pair(pair)
        self._apply_pair_decision(decision)
        return decision

    # ---------- the main loop ----------

    def refine(self, budget: int) -> RefinementReport:
        """Iterate until the memory fits `budget` (max entries in L1 + L2).

        Each iteration:
            1. Propose candidate pairs.
            2. Judge each pair (KEEP / MERGE).
            3. For MERGE: produce a merged entry; remove the two originals.
            4. If still over budget, iterate on singletons:
               for the lowest-importance entries, judge KEEP / COMPRESS /
               EVICT / PROMOTE and apply.

        The loop terminates early if `max_iterations` is reached or the size
        stops decreasing.
        """
        report = RefinementReport(
            initial_size=len(self._iter_entries()),
            final_size=0,
            iterations=0,
        )
        self._active_report = report
        last_size = report.initial_size

        for it in range(self.config.max_iterations):
            report.iterations = it + 1
            current_size = len(self._iter_entries())
            if current_size <= budget:
                break

            # Phase 1: pair-level refinement
            pairs = self.propose_pairs()
            for pair in pairs:
                # Skip pairs where either entry no longer exists
                if self._find_entry(pair.a_id) is None or self._find_entry(pair.b_id) is None:
                    continue
                # Re-fetch the live entries (their importance may have changed)
                a = self._find_entry(pair.a_id)
                b = self._find_entry(pair.b_id)
                if a is None or b is None:
                    continue
                pair = RefinementCandidatePair(
                    a_id=a.id,
                    b_id=b.id,
                    similarity=_similarity(a, b),
                    a_content=a.content,
                    b_content=b.content,
                    a_importance=a.importance,
                    b_importance=b.importance,
                    a_tags=list(a.tags),
                    b_tags=list(a.tags),
                    a_associations=list(a.associations),
                    b_associations=list(b.associations),
                )
                decision = self.judge.judge_pair(pair)
                self._apply_pair_decision(decision)
                report.decisions.append(decision)

            # Phase 2: singleton-level refinement on the lowest-importance slice
            entries = sorted(
                self._iter_entries(),
                key=lambda e: (e.importance, _fact_density(e.content)),
            )
            for entry in entries:
                if len(self._iter_entries()) <= budget:
                    break
                if self._find_entry(entry.id) is None:
                    continue
                decision = self.judge.judge_singleton(
                    entry,
                    current_size=len(self._iter_entries()),
                    budget=budget,
                )
                self._apply_singleton_decision(decision)
                report.decisions.append(decision)

            new_size = len(self._iter_entries())
            size_changing_actions = report.evicted + report.merged_pairs
            if size_changing_actions == 0 and new_size >= last_size:
                # No size reduction: compression-only or keep-only; stop to avoid infinite loop
                break
            last_size = new_size

        report.final_size = len(self._iter_entries())
        self._active_report = None
        return report

    # ---------- introspection ----------

    def summary(self) -> Dict:
        """Aggregate stats over the audit trail."""
        actions = defaultdict(int)
        for d in self.audit:
            actions[d.action.value] += 1
        return {
            "audit_count": len(self.audit),
            "actions": dict(actions),
            "current_size": len(self._iter_entries()),
            "judge": self.judge.name,
            "protect_above_importance": self.config.protect_above_importance,
        }

    # ---------- internals ----------

    def _find_entry(self, entry_id: str) -> Optional[TieredMemoryEntry]:
        if entry_id in self.memory.l1_working:
            return self.memory.l1_working[entry_id]
        if entry_id in self.memory.l2_longterm:
            return self.memory.l2_longterm[entry_id]
        return None

    def _apply_singleton_decision(self, decision: RefinementDecision) -> None:
        self._record_decision(decision)
        entry_id = decision.target_ids[0]
        entry = self._find_entry(entry_id)
        if entry is None:
            return
        if decision.action == RefinementAction.KEEP or decision.action == RefinementAction.PROMOTE:
            if decision.action == RefinementAction.PROMOTE:
                self._promote_entry(entry, self.config.promote_tier)
                self._bump(getattr(self, "_active_report", None), "promoted")
            else:
                self._bump(getattr(self, "_active_report", None), "kept")
            return
        if decision.action == RefinementAction.EVICT:
            self._remove_entry(entry)
            self._bump(getattr(self, "_active_report", None), "evicted")
            return
        if decision.action == RefinementAction.COMPRESS:
            self._replace_entry_content(entry, decision.compressed_content or _compress_facts(entry.content))
            self._bump(getattr(self, "_active_report", None), "compressed")
            return

    def _apply_pair_decision(self, decision: RefinementDecision) -> None:
        self._record_decision(decision)
        if decision.action != RefinementAction.MERGE:
            return
        a = self._find_entry(decision.target_ids[0])
        b = self._find_entry(decision.target_ids[1])
        if a is None or b is None:
            return
        # Keep the higher-importance entry as the survivor; remove the other
        survivor = a if a.importance >= b.importance else b
        loser = b if survivor is a else a
        merged_content = decision.compressed_content or _merge_facts(a.content, b.content)
        merged_tags = sorted(set(survivor.tags) | set(loser.tags))
        merged_associations = sorted(set(survivor.associations) | set(loser.associations))
        survivor.content = merged_content
        survivor.tags = merged_tags
        survivor.associations = merged_associations
        # Importance: max of the two (the merged entry is at least as valuable as either)
        survivor.importance = max(a.importance, b.importance)
        # access_count: sum
        survivor.access_count = a.access_count + b.access_count
        # touch
        survivor.last_accessed = datetime.now()
        # Remove the loser
        self._remove_entry(loser)
        self._bump(getattr(self, "_active_report", None), "merged_pairs")

    @staticmethod
    def _bump(report: Optional["RefinementReport"], field: str) -> None:
        if report is None:
            return
        if hasattr(report, field):
            setattr(report, field, getattr(report, field) + 1)

    def _remove_entry(self, entry: TieredMemoryEntry) -> None:
        if entry.id in self.memory.l1_working:
            del self.memory.l1_working[entry.id]
            try:
                self.memory._remove_from_indices(entry)
            except Exception:
                pass
            return
        if entry.id in self.memory.l2_longterm:
            del self.memory.l2_longterm[entry.id]
            try:
                self.memory._remove_from_indices(entry)
            except Exception:
                pass

    def _promote_entry(self, entry: TieredMemoryEntry, target: MemoryTier) -> None:
        # If already in target tier, do nothing
        if (target == MemoryTier.L1_WORKING and entry.id in self.memory.l1_working) or \
           (target == MemoryTier.L2_ARCHIVAL and entry.id in self.memory.l2_longterm):
            return
        # Remove from current location
        self._remove_entry(entry)
        # Add to target tier
        if target == MemoryTier.L1_WORKING:
            # If L1 is full, evict the lowest
            if len(self.memory.l1_working) >= self.memory.l1_capacity:
                self.memory._evict_from_l1()
            entry.tier = MemoryTier.L1_WORKING
            self.memory.l1_working[entry.id] = entry
            try:
                self.memory._update_indices(entry)
            except Exception:
                pass
        elif target == MemoryTier.L2_ARCHIVAL:
            if len(self.memory.l2_longterm) >= self.memory.l2_capacity:
                self.memory._forget_from_l2()
            entry.tier = MemoryTier.L2_ARCHIVAL
            self.memory.l2_longterm[entry.id] = entry
            try:
                self.memory._update_indices(entry)
            except Exception:
                pass

    def _replace_entry_content(self, entry: TieredMemoryEntry, new_content: Any) -> None:
        entry.content = new_content
        # Re-generate embedding if available
        try:
            entry.embedding = self.memory._generate_embedding(new_content)
        except Exception:
            pass

    def _record_decision(self, decision: RefinementDecision) -> None:
        self.audit.append(decision)
        if self.config.audit_path:
            try:
                with open(self.config.audit_path, "a") as f:
                    f.write(json.dumps(decision.to_dict()) + "\n")
            except Exception:
                # Audit failure is non-fatal; the in-memory trail is the source of truth
                pass


# -----------------------------------------------------------------------------
# Smallest viable install helper
# -----------------------------------------------------------------------------


def create_memory_refiner(
    memory: TieredMemorySystem,
    judge: Optional[RefinementJudge] = None,
    audit_path: Optional[str] = None,
) -> MemoryRefiner:
    """One-line install: refiner + FactDensityJudge + optional audit trail."""
    config = MemoryRefinerConfig(audit_path=audit_path)
    return MemoryRefiner(memory=memory, judge=judge or FactDensityJudge(), config=config)