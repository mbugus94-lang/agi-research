"""
Causal Evidence Ledger - Grounded claim tracking for AI agents.

Inspired by:
- WISE (OpenReview T8HuiP3yM9): Causal Event Graph connecting
  observations, task relevance, and causal structure.
- Lexical hints of accuracy in LLM reasoning chains (Sci Reports 2026):
  post-hoc calibration signals about which reasoning steps actually
  carried weight.
- CaveAgent (OpenReview p3dlOhpqKD): stateful runtime objects that
  persist across turns as a verifiable memory substrate.
- Metacognitive monitor (arXiv:2605.15567v1) and PEEK-style context cache
  (arXiv:2605.19932v1) - hooks for integrating evidence quality into
  resource-rational monitoring and orientation caching.

What this module does:
- Tracks every claim, observation, and inference the agent makes along
  with the evidence that supports or contradicts it.
- Provides deterministic, LLM-free verification routines: support count,
  contradiction count, freshness, lineage.
- Distinguishes UNGROUNDED claims (no evidence) from CONTRADICTED claims
  (evidence refutes them) and SUPPORTED claims (positive evidence).
- Surfaces the weakest links so reflection can target them.
- Stores and re-loads the ledger to/from JSON (stateful-runtime-friendly).

Decisions:
- Everything is LLM-agnostic and deterministic: scoring uses string
  overlap on token sets, recency windows, and explicit supports/refutes
  edges, not any neural judgment.
- Designed to plug into the existing BaseAgent / ReflectionEngine /
  MetacognitiveMonitor / ContextMap pipeline. The `claim_evaluator` in
  this file is deliberately self-contained so the surface area is small.
- Treats the ledger as a black-box substrate: an agent can call
  `EvidenceLedger.assert_claim`, `add_support`, `add_refute`, `verify`,
  `summary`, and `serialize` without knowing how scoring works.

Safety:
- No self-modification of the agent's code. The ledger is data, not
  behavior. Reflection and the metacognitive monitor consume ledger
  summaries to flag issues, but never auto-apply changes to other
  modules.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Enums and dataclasses
# ---------------------------------------------------------------------------


class ClaimStatus(Enum):
    """The verification status of a claim."""
    UNGROUNDED = "ungrounded"      # No evidence attached yet
    SUPPORTED = "supported"        # Net positive evidence
    CONTRADICTED = "contradicted"  # Net negative evidence
    DISPUTED = "disputed"          # Evidence on both sides
    EXPIRED = "expired"            # Past freshness window without renewal


class EvidencePolarity(Enum):
    """Whether a piece of evidence supports or refutes a claim."""
    SUPPORTS = "supports"
    REFUTES = "refutes"


class EvidenceKind(Enum):
    """The kind of evidence attached to a claim."""
    OBSERVATION = "observation"        # Direct tool/output observation
    TOOL_TRACE = "tool_trace"          # Result of a tool call
    MEMORY_ITEM = "memory_item"        # Retrieved from memory
    EXTERNAL = "external"              # From a web search / citation
    INFERENCE = "inference"            # Derived from another claim
    USER_STATEMENT = "user_statement"  # User-provided premise
    UNKNOWN = "unknown"


@dataclass
class Claim:
    """A proposition the agent has made that may need evidence."""
    claim_id: str
    text: str
    author: str = "agent"
    created_at: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    # claims this one depends on (causal / logical lineage)
    status: ClaimStatus = ClaimStatus.UNGROUNDED
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "author": self.author,
            "created_at": self.created_at.isoformat(),
            "tags": list(self.tags),
            "depends_on": list(self.depends_on),
            "status": self.status.value,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Claim":
        return cls(
            claim_id=data["claim_id"],
            text=data["text"],
            author=data.get("author", "agent"),
            created_at=datetime.fromisoformat(data["created_at"]),
            tags=list(data.get("tags", [])),
            depends_on=list(data.get("depends_on", [])),
            status=ClaimStatus(data.get("status", ClaimStatus.UNGROUNDED.value)),
            notes=data.get("notes", ""),
        )


@dataclass
class Evidence:
    """A piece of evidence attached to a claim."""
    evidence_id: str
    claim_id: str
    polarity: EvidencePolarity
    kind: EvidenceKind
    content: str
    source: str = ""
    weight: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)
    confidence: float = 0.8

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "claim_id": self.claim_id,
            "polarity": self.polarity.value,
            "kind": self.kind.value,
            "content": self.content,
            "source": self.source,
            "weight": self.weight,
            "created_at": self.created_at.isoformat(),
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Evidence":
        return cls(
            evidence_id=data["evidence_id"],
            claim_id=data["claim_id"],
            polarity=EvidencePolarity(data["polarity"]),
            kind=EvidenceKind(data.get("kind", EvidenceKind.UNKNOWN.value)),
            content=data["content"],
            source=data.get("source", ""),
            weight=float(data.get("weight", 1.0)),
            created_at=datetime.fromisoformat(data["created_at"]),
            confidence=float(data.get("confidence", 0.8)),
        )


@dataclass
class ClaimVerification:
    """Result of verifying a single claim."""
    claim_id: str
    status: ClaimStatus
    support_count: int
    refute_count: int
    weighted_support: float
    weighted_refute: float
    confidence: float
    is_fresh: bool
    reason: str
    linked_claim_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "status": self.status.value,
            "support_count": self.support_count,
            "refute_count": self.refute_count,
            "weighted_support": self.weighted_support,
            "weighted_refute": self.weighted_refute,
            "confidence": self.confidence,
            "is_fresh": self.is_fresh,
            "reason": self.reason,
            "linked_claim_ids": list(self.linked_claim_ids),
        }


@dataclass
class LedgerSummary:
    """Aggregate view of a ledger's evidence quality."""
    total_claims: int
    ungrounded: int
    supported: int
    contradicted: int
    disputed: int
    expired: int
    ungrounded_rate: float
    contradiction_rate: float
    weakest_claim_ids: List[str] = field(default_factory=list)
    audit_trail: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_claims": self.total_claims,
            "ungrounded": self.ungrounded,
            "supported": self.supported,
            "contradicted": self.contradicted,
            "disputed": self.disputed,
            "expired": self.expired,
            "ungrounded_rate": self.ungrounded_rate,
            "contradiction_rate": self.contradiction_rate,
            "weakest_claim_ids": list(self.weakest_claim_ids),
            "audit_trail": list(self.audit_trail),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_WORD_RE = re.compile(r"[A-Za-z0-9_]+")
_STOPWORDS: Set[str] = {
    "the", "a", "an", "of", "in", "on", "at", "to", "for", "and", "or",
    "is", "are", "was", "were", "be", "been", "being", "this", "that",
    "these", "those", "it", "its", "as", "by", "with", "from", "into",
    "we", "i", "you", "they", "he", "she", "them", "our", "your", "his",
    "her", "their", "my", "me", "us", "do", "does", "did", "done",
    "have", "has", "had", "having", "not", "no", "yes", "but", "if",
    "then", "than", "so", "such", "also", "too", "very", "can", "could",
    "should", "would", "may", "might", "will", "shall", "must",
}


def _tokenize(text: str) -> Set[str]:
    """Lowercase, alphanumeric tokens, drop stopwords."""
    if not text:
        return set()
    tokens = {m.group(0).lower() for m in _WORD_RE.finditer(text)}
    return {t for t in tokens if t not in _STOPWORDS and len(t) > 1}


def _lexical_overlap(a: str, b: str) -> float:
    """Jaccard-like overlap in [0,1] between two pieces of text."""
    ta = _tokenize(a)
    tb = _tokenize(b)
    if not ta or not tb:
        return 0.0
    inter = ta & tb
    union = ta | tb
    return len(inter) / len(union) if union else 0.0


def _now() -> datetime:
    return datetime.now()


# ---------------------------------------------------------------------------
# Core ledger
# ---------------------------------------------------------------------------


class EvidenceLedger:
    """
    Tracks claims and the evidence that supports or refutes them.

    The ledger is the substrate that other modules consult when they
    need to know "do we actually have grounds to believe this?":

    - ReflectionEngine.verify_trace can ask the ledger for evidence
      coverage of each reasoning step.
    - MetacognitiveMonitor can use the ungrounded/contradiction rate as
      a calibration signal.
    - ContextMap ingestion can turn "claim" + "evidence" into a single
      INSTRUCTION / SCHEMA entry once verified.
    """

    def __init__(
        self,
        freshness_window: Optional[timedelta] = None,
        lexical_threshold: float = 0.15,
        max_audit_trail: int = 64,
    ) -> None:
        self.freshness_window = freshness_window or timedelta(hours=24)
        self.lexical_threshold = float(lexical_threshold)
        self.max_audit_trail = max_audit_trail
        self._claims: Dict[str, Claim] = {}
        self._evidence: Dict[str, Evidence] = {}
        self._evidence_by_claim: Dict[str, List[str]] = {}
        self._audit_trail: List[str] = []
        # monotonic counter for id generation, scoped per ledger
        self._counter: int = 0

    # -- id generation ----------------------------------------------------

    def _next_id(self, prefix: str) -> str:
        self._counter += 1
        return f"{prefix}_{self._counter:06d}"

    def _log(self, message: str) -> None:
        stamp = _now().isoformat(timespec="seconds")
        self._audit_trail.append(f"{stamp} {message}")
        if len(self._audit_trail) > self.max_audit_trail:
            # keep most recent events
            self._audit_trail = self._audit_trail[-self.max_audit_trail:]

    # -- claim CRUD -------------------------------------------------------

    def assert_claim(
        self,
        text: str,
        author: str = "agent",
        tags: Optional[Iterable[str]] = None,
        depends_on: Optional[Iterable[str]] = None,
        claim_id: Optional[str] = None,
        notes: str = "",
    ) -> Claim:
        """Add a claim. Returns the (new or existing) claim."""
        cid = claim_id or self._next_id("claim")
        if cid in self._claims:
            # idempotent: update mutable fields
            existing = self._claims[cid]
            if text and text != existing.text:
                existing.text = text
                self._log(f"updated claim text {cid}")
            if tags is not None:
                existing.tags = list(tags)
            if depends_on is not None:
                existing.depends_on = list(depends_on)
            if notes:
                existing.notes = notes
            return existing
        claim = Claim(
            claim_id=cid,
            text=text,
            author=author,
            tags=list(tags or []),
            depends_on=list(depends_on or []),
            notes=notes,
        )
        self._claims[cid] = claim
        self._evidence_by_claim.setdefault(cid, [])
        self._log(f"asserted claim {cid} ({author})")
        return claim

    def remove_claim(self, claim_id: str) -> bool:
        if claim_id not in self._claims:
            return False
        # drop claim and its evidence
        for ev_id in list(self._evidence_by_claim.get(claim_id, [])):
            self._evidence.pop(ev_id, None)
        self._evidence_by_claim.pop(claim_id, None)
        self._claims.pop(claim_id, None)
        self._log(f"removed claim {claim_id}")
        return True

    def has_claim(self, claim_id: str) -> bool:
        return claim_id in self._claims

    def get_claim(self, claim_id: str) -> Optional[Claim]:
        return self._claims.get(claim_id)

    def claims_with_status(self, status: ClaimStatus) -> List[Claim]:
        return [c for c in self._claims.values() if c.status == status]

    def all_claims(self) -> List[Claim]:
        return list(self._claims.values())

    # -- evidence CRUD ----------------------------------------------------

    def add_evidence(
        self,
        claim_id: str,
        polarity: EvidencePolarity,
        content: str,
        kind: EvidenceKind = EvidenceKind.OBSERVATION,
        source: str = "",
        weight: float = 1.0,
        confidence: float = 0.8,
        evidence_id: Optional[str] = None,
    ) -> Optional[Evidence]:
        if claim_id not in self._claims:
            return None
        eid = evidence_id or self._next_id("ev")
        if eid in self._evidence:
            existing = self._evidence[eid]
            existing.polarity = polarity
            existing.kind = kind
            existing.content = content
            existing.source = source
            existing.weight = float(weight)
            existing.confidence = float(confidence)
            self._log(f"updated evidence {eid} -> {claim_id} ({polarity.value})")
            return existing
        ev = Evidence(
            evidence_id=eid,
            claim_id=claim_id,
            polarity=polarity,
            kind=kind,
            content=content,
            source=source,
            weight=float(weight),
            confidence=float(confidence),
        )
        self._evidence[eid] = ev
        self._evidence_by_claim.setdefault(claim_id, []).append(eid)
        self._log(f"added {polarity.value} evidence {eid} -> {claim_id}")
        return ev

    def add_support(
        self,
        claim_id: str,
        content: str,
        kind: EvidenceKind = EvidenceKind.OBSERVATION,
        source: str = "",
        weight: float = 1.0,
        confidence: float = 0.8,
    ) -> Optional[Evidence]:
        return self.add_evidence(
            claim_id=claim_id,
            polarity=EvidencePolarity.SUPPORTS,
            content=content,
            kind=kind,
            source=source,
            weight=weight,
            confidence=confidence,
        )

    def add_refute(
        self,
        claim_id: str,
        content: str,
        kind: EvidenceKind = EvidenceKind.OBSERVATION,
        source: str = "",
        weight: float = 1.0,
        confidence: float = 0.8,
    ) -> Optional[Evidence]:
        return self.add_evidence(
            claim_id=claim_id,
            polarity=EvidencePolarity.REFUTES,
            content=content,
            kind=kind,
            source=source,
            weight=weight,
            confidence=confidence,
        )

    def evidence_for(self, claim_id: str) -> List[Evidence]:
        return [
            self._evidence[eid]
            for eid in self._evidence_by_claim.get(claim_id, [])
            if eid in self._evidence
        ]

    def remove_evidence(self, evidence_id: str) -> bool:
        ev = self._evidence.pop(evidence_id, None)
        if ev is None:
            return False
        bucket = self._evidence_by_claim.get(ev.claim_id, [])
        if evidence_id in bucket:
            bucket.remove(evidence_id)
        self._log(f"removed evidence {evidence_id}")
        return True

    # -- verification -----------------------------------------------------

    def verify(self, claim_id: str) -> ClaimVerification:
        """Recompute a single claim's status from its evidence."""
        claim = self._claims.get(claim_id)
        if claim is None:
            return ClaimVerification(
                claim_id=claim_id,
                status=ClaimStatus.UNGROUNDED,
                support_count=0,
                refute_count=0,
                weighted_support=0.0,
                weighted_refute=0.0,
                confidence=0.0,
                is_fresh=False,
                reason="claim_not_found",
            )

        evidences = self.evidence_for(claim_id)
        support_evs = [e for e in evidences if e.polarity == EvidencePolarity.SUPPORTS]
        refute_evs = [e for e in evidences if e.polarity == EvidencePolarity.REFUTES]

        # weight x confidence, clipped to [0,1] for each evidence item
        def _w(ev: Evidence) -> float:
            w = max(0.0, min(1.0, ev.weight)) * max(0.0, min(1.0, ev.confidence))
            return w

        weighted_support = sum(_w(e) for e in support_evs)
        weighted_refute = sum(_w(e) for e in refute_evs)

        is_fresh = (_now() - claim.created_at) <= self.freshness_window
        age = _now() - claim.created_at

        if not evidences or (weighted_support == 0 and weighted_refute == 0):
            # No evidence, OR all evidence has zero effective weight
            status = ClaimStatus.EXPIRED if not is_fresh else ClaimStatus.UNGROUNDED
            reason = "no_evidence" if is_fresh else "no_evidence_and_stale"
            confidence = 0.0
        elif weighted_support > 0 and weighted_refute == 0:
            status = ClaimStatus.SUPPORTED
            confidence = min(1.0, weighted_support / max(1.0, float(len(support_evs))))
            reason = "net_positive_evidence"
        elif weighted_refute > 0 and weighted_support == 0:
            status = ClaimStatus.CONTRADICTED
            confidence = min(1.0, weighted_refute / max(1.0, float(len(refute_evs))))
            reason = "net_negative_evidence"
        elif weighted_support > weighted_refute:
            status = ClaimStatus.SUPPORTED
            confidence = min(1.0, weighted_support / (weighted_support + weighted_refute))
            reason = "mixed_with_support_lead"
        elif weighted_refute > weighted_support:
            status = ClaimStatus.CONTRADICTED
            confidence = min(1.0, weighted_refute / (weighted_support + weighted_refute))
            reason = "mixed_with_refute_lead"
        else:
            status = ClaimStatus.DISPUTED
            confidence = 0.5
            reason = "tied_evidence"

        if not is_fresh and status in (ClaimStatus.SUPPORTED, ClaimStatus.DISPUTED):
            # mark stale positives as expired to encourage re-verification
            status = ClaimStatus.EXPIRED
            reason = f"{reason}_and_stale_{int(age.total_seconds())}s"

        # collect linked claim ids (depends_on + transitive one hop)
        linked: List[str] = []
        for dep in claim.depends_on:
            if dep in self._claims and dep not in linked:
                linked.append(dep)

        claim.status = status
        return ClaimVerification(
            claim_id=claim_id,
            status=status,
            support_count=len(support_evs),
            refute_count=len(refute_evs),
            weighted_support=weighted_support,
            weighted_refute=weighted_refute,
            confidence=confidence,
            is_fresh=is_fresh,
            reason=reason,
            linked_claim_ids=linked,
        )

    def verify_all(self) -> List[ClaimVerification]:
        return [self.verify(cid) for cid in self._claims]

    # -- lineage & causal graph ------------------------------------------

    def lineage(self, claim_id: str) -> List[str]:
        """Return this claim and the closure of its `depends_on` ancestors."""
        if claim_id not in self._claims:
            return []
        seen: Set[str] = set()
        order: List[str] = []
        stack = [claim_id]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            order.append(cur)
            claim = self._claims.get(cur)
            if claim is None:
                continue
            for dep in claim.depends_on:
                if dep in self._claims and dep not in seen:
                    stack.append(dep)
        return order

    def descendants(self, claim_id: str) -> List[str]:
        """Return claims that depend (transitively) on this one."""
        if claim_id not in self._claims:
            return []
        seen: Set[str] = set()
        order: List[str] = []
        # BFS
        frontier = [c.claim_id for c in self._claims.values() if claim_id in c.depends_on]
        while frontier:
            nxt: List[str] = []
            for cur in frontier:
                if cur in seen:
                    continue
                seen.add(cur)
                order.append(cur)
                nxt.extend(c.claim_id for c in self._claims.values() if cur in c.depends_on)
            frontier = nxt
        return order

    def related_evidence(self, text: str, top_k: int = 5) -> List[Tuple[Evidence, float]]:
        """
        Surface evidence items whose content has the highest lexical
        overlap with `text`. Useful for grounding a new claim in the
        ledger's existing evidence.
        """
        scored: List[Tuple[Evidence, float]] = []
        for ev in self._evidence.values():
            score = _lexical_overlap(text, ev.content)
            if score >= self.lexical_threshold:
                scored.append((ev, score))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]

    # -- summary ----------------------------------------------------------

    def summary(self) -> LedgerSummary:
        total = len(self._claims)
        if total == 0:
            return LedgerSummary(
                total_claims=0,
                ungrounded=0,
                supported=0,
                contradicted=0,
                disputed=0,
                expired=0,
                ungrounded_rate=0.0,
                contradiction_rate=0.0,
                weakest_claim_ids=[],
                audit_trail=list(self._audit_trail),
            )

        # re-verify lazily to make summary accurate
        results = self.verify_all()
        ungrounded = sum(1 for r in results if r.status == ClaimStatus.UNGROUNDED)
        supported = sum(1 for r in results if r.status == ClaimStatus.SUPPORTED)
        contradicted = sum(1 for r in results if r.status == ClaimStatus.CONTRADICTED)
        disputed = sum(1 for r in results if r.status == ClaimStatus.DISPUTED)
        expired = sum(1 for r in results if r.status == ClaimStatus.EXPIRED)

        # weakest = lowest support score, ties broken by refute count
        def _weak_key(r: ClaimVerification) -> Tuple[float, float]:
            return (r.weighted_support - r.weighted_refute, -r.weighted_refute)

        ranked = sorted(results, key=_weak_key)
        weakest = [r.claim_id for r in ranked if r.status != ClaimStatus.SUPPORTED][:5]

        return LedgerSummary(
            total_claims=total,
            ungrounded=ungrounded,
            supported=supported,
            contradicted=contradicted,
            disputed=disputed,
            expired=expired,
            ungrounded_rate=ungrounded / total,
            contradiction_rate=contradicted / total,
            weakest_claim_ids=weakest,
            audit_trail=list(self._audit_trail),
        )

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "freshness_window_seconds": int(self.freshness_window.total_seconds()),
            "lexical_threshold": self.lexical_threshold,
            "max_audit_trail": self.max_audit_trail,
            "counter": self._counter,
            "claims": [c.to_dict() for c in self._claims.values()],
            "evidence": [e.to_dict() for e in self._evidence.values()],
            "audit_trail": list(self._audit_trail),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceLedger":
        ledger = cls(
            freshness_window=timedelta(seconds=int(data.get("freshness_window_seconds", 86400))),
            lexical_threshold=float(data.get("lexical_threshold", 0.15)),
            max_audit_trail=int(data.get("max_audit_trail", 64)),
        )
        ledger._counter = int(data.get("counter", 0))
        for c in data.get("claims", []):
            claim = Claim.from_dict(c)
            ledger._claims[claim.claim_id] = claim
            ledger._evidence_by_claim.setdefault(claim.claim_id, [])
        for e in data.get("evidence", []):
            ev = Evidence.from_dict(e)
            ledger._evidence[ev.evidence_id] = ev
            ledger._evidence_by_claim.setdefault(ev.claim_id, []).append(ev.evidence_id)
        ledger._audit_trail = list(data.get("audit_trail", []))
        return ledger

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, payload: str) -> "EvidenceLedger":
        return cls.from_dict(json.loads(payload))

    # -- metacognition / monitor hooks -----------------------------------

    def calibration_signals(self) -> Dict[str, float]:
        """
        Return signals consumable by MetacognitiveMonitor / reflection.

        Keys:
        - ungrounded_rate: fraction of claims with no evidence
        - contradiction_rate: fraction of claims that are refuted
        - disputed_rate: fraction of claims with tied evidence
        - mean_confidence: average confidence across verifications
        - expired_rate: fraction of claims past freshness window
        """
        results = self.verify_all()
        if not results:
            return {
                "ungrounded_rate": 0.0,
                "contradiction_rate": 0.0,
                "disputed_rate": 0.0,
                "mean_confidence": 0.0,
                "expired_rate": 0.0,
            }
        n = len(results)
        ungrounded = sum(1 for r in results if r.status == ClaimStatus.UNGROUNDED)
        contradicted = sum(1 for r in results if r.status == ClaimStatus.CONTRADICTED)
        disputed = sum(1 for r in results if r.status == ClaimStatus.DISPUTED)
        expired = sum(1 for r in results if r.status == ClaimStatus.EXPIRED)
        mean_conf = sum(r.confidence for r in results) / n
        return {
            "ungrounded_rate": ungrounded / n,
            "contradiction_rate": contradicted / n,
            "disputed_rate": disputed / n,
            "mean_confidence": mean_conf,
            "expired_rate": expired / n,
        }


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------


def create_ledger(
    freshness_seconds: int = 86400,
    lexical_threshold: float = 0.15,
    max_audit_trail: int = 64,
) -> EvidenceLedger:
    return EvidenceLedger(
        freshness_window=timedelta(seconds=freshness_seconds),
        lexical_threshold=lexical_threshold,
        max_audit_trail=max_audit_trail,
    )


__all__ = [
    "ClaimStatus",
    "EvidencePolarity",
    "EvidenceKind",
    "Claim",
    "Evidence",
    "ClaimVerification",
    "LedgerSummary",
    "EvidenceLedger",
    "create_ledger",
]
