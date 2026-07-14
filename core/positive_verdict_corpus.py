"""
Positive verdict corpus (NVIDIA ASPIRE-style skill distillation, 2026-07-14).

Research grounding
------------------
- arXiv:2607.07612 ("Towards Agentic AI Governance", 2026-07): a positive
  corpus of well-behaved agentic interactions is a foundation for
  governance: it lets operators (a) replay the chain during incident
  review, (b) train/calibrate gating thresholds against a known-good
  baseline, and (c) extract reusable "skills" (chain templates that
  succeeded) that can be re-applied to similar future tasks.
- NVIDIA ASPIRE (Skill Distillation, 2026): "successful trajectories
  become a positive corpus from which a smaller student agent is
  distilled". The substrate's analogue is *successful chain verdicts*
  becoming a positive corpus from which future trip-engine thresholds
  and CLP/DSCC capability sets are calibrated.
- arXiv:2607.03423 (DSCC §3.2): the operator's confidence in a gate
  improves with each replayed verdict that matches. The corpus gives
  the operator a stable record to replay against.

The substrate's two gates
-------------------------
- ``CompositionalPolicyGate`` produces ``ChainVerdict`` (write side,
  taint-only-increase).
- ``ContextualLeastPrivilegeGate`` produces ``CLPVerdict`` (read side,
  visibility-only-decrease).
- ``dual_gate_check`` produces a combined verdict.

This module records *successful* verdicts from any of these. An
"allow" verdict is the success criterion: the chain was permitted.
Failed chains (BLOCK / BLOCK_AND_ESCALATE) are useful for *negative*
corpus work but are not stored here.

Design notes
------------
- **Deterministic, content-addressed.** Every entry's ``corpus_digest``
  is SHA-256 of the canonicalized ``(chain_fingerprint, verdict_digest,
  gate_version, capability_set_id)`` tuple. Re-recording the same
  chain returns the same digest (idempotent).
- **Append-only.** Entries are never mutated or deleted. Operators
  freeze and rotate corpora; the substrate never silently drops an
  entry.
- **No I/O.** The corpus is an in-memory list. Persistence is the
  operator's job (use ``to_json()`` / ``from_json()`` to round-trip).
  This matches the substrate's "every gate is pure" invariant.
- **Replay-verifiable.** ``verify_entry(entry, gate, cap_set)`` re-runs
  the gate against the frozen chain and returns whether the recorded
  verdict matches the live verdict. A mismatch is a *corruption* signal,
  not a soft warning.
- **Trip-engine handoff.** ``attach_trip_engine(engine)`` makes every
  successful verdict observable to the operator's
  ``ProbabilisticTripEngine`` so the steady-state safety claim improves
  with each successful chain.
- **Skill-distillation hooks.** ``extract_skill(entry)`` projects an
  entry into a ``SkillTemplate`` (verb-sequence signature + initial
  visibility + capability-set ID) suitable for use as a
  pattern-matchable template in future chain planning.

This module is the substrate's *positive* counterpart to
``benign_config_finder`` (CONTRA, 2026-07-13, finding benign
configurations that avoid attack templates). The CONTRA module finds
benign configurations; this module *records* successful chains as
they happen, so a future operator can ask "what successful chains
have we seen in the last 30 days?" without needing to re-execute.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Chain fingerprinting
# ---------------------------------------------------------------------------


def _canonical_chain(chain: List[Dict[str, Any]]) -> str:
    """Canonical JSON serialization of a chain for digesting.

    Strips volatile fields (e.g. timestamps) and sorts keys so the
    digest is stable across re-recordings. Argument dicts are sorted
    by key; the chain itself is ordered.
    """
    norm: List[Dict[str, Any]] = []
    for step in chain:
        if not isinstance(step, dict):
            raise TypeError("chain steps must be dicts")
        clean: Dict[str, Any] = {}
        for k in sorted(step.keys()):
            v = step[k]
            if k in ("timestamp", "ts", "wall_time"):
                continue
            if isinstance(v, dict):
                v = {kk: vv for kk, vv in sorted(v.items())}
            clean[k] = v
        norm.append(clean)
    return json.dumps(norm, sort_keys=True, separators=(",", ":"))


def chain_fingerprint(chain: List[Dict[str, Any]]) -> str:
    """SHA-256 fingerprint of a chain (verb-sequence signature)."""
    return hashlib.sha256(_canonical_chain(chain).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Corpus entry
# ---------------------------------------------------------------------------


@dataclass
class CorpusEntry:
    """A single (chain, verdict) record.

    Attributes:
        chain: the chain steps (list of dicts, ordered).
        verdict_action: the verdict's recommended action string
            ("allow" / "block" / "block_and_escalate"). Only
            "allow" entries are stored; the assertion is enforced
            at construction.
        verdict_digest: the verdict's own digest (CLPVerdict.digest
            or ChainVerdict.digest). The audit anchor.
        gate_version: the gate's semantic version string. Lets the
            operator reason about corpus evolution across substrate upgrades.
        capability_set_id: the capability-set identifier this chain ran against.
        recorded_at: epoch milliseconds (int). Auto-filled by
            ``from_allow`` if not supplied.
        corpus_digest: SHA-256 of the canonicalized
            ``(chain_fingerprint, verdict_digest, gate_version,
            capability_set_id)`` tuple. Auto-computed by
            ``from_allow`` if not supplied.
        reason: optional human-readable reason the chain was permitted
            (e.g. "DSCC MRS in TAINT mode, no sensitive-to-public edges").
        provenance: optional metadata dict (e.g. ``{"session_id": "..."}``).

    The dataclass ``__init__`` accepts a *fully populated* record
    (used by ``from_json``). For normal construction use the
    ``from_allow`` classmethod, which auto-fills ``recorded_at`` and
    ``corpus_digest``.
    """

    chain: List[Dict[str, Any]]
    verdict_action: str
    verdict_digest: str
    gate_version: str
    capability_set_id: str
    recorded_at: int = 0
    corpus_digest: str = ""
    reason: str = ""
    provenance: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.verdict_action != "allow":
            raise AssertionError(
                "positive_verdict_corpus only stores 'allow' verdicts; "
                f"got {self.verdict_action!r}"
            )
        if not self.verdict_digest:
            raise ValueError("verdict_digest is required (audit anchor)")
        if not self.gate_version:
            raise ValueError("gate_version is required")
        if not self.capability_set_id:
            raise ValueError("capability_set_id is required")
        if not self.recorded_at:
            self.recorded_at = int(time.time() * 1000)
        if not self.corpus_digest:
            self.corpus_digest = _compute_corpus_digest(
                chain_fingerprint(self.chain),
                self.verdict_digest,
                self.gate_version,
                self.capability_set_id,
            )

    @classmethod
    def from_allow(
        cls,
        chain: List[Dict[str, Any]],
        verdict_digest: str,
        gate_version: str,
        capability_set_id: str,
        reason: str = "",
        provenance: Optional[Dict[str, Any]] = None,
        recorded_at: Optional[int] = None,
    ) -> "CorpusEntry":
        """Construct an 'allow' entry with auto-filled fields.

        Computes the chain fingerprint and the corpus digest from the
        four required fields. Used by ``PositiveVerdictCorpus.record``.
        """
        fp = chain_fingerprint(chain)
        digest = _compute_corpus_digest(
            chain_fingerprint=fp,
            verdict_digest=verdict_digest,
            gate_version=gate_version,
            capability_set_id=capability_set_id,
        )
        return cls(
            chain=chain,
            verdict_action="allow",
            verdict_digest=verdict_digest,
            gate_version=gate_version,
            capability_set_id=capability_set_id,
            recorded_at=recorded_at if recorded_at is not None else int(time.time() * 1000),
            corpus_digest=digest,
            reason=reason,
            provenance=provenance or {},
        )


# ---------------------------------------------------------------------------
# Skill distillation (ASPIRE-style projection)
# ---------------------------------------------------------------------------


@dataclass
class SkillTemplate:
    """A reusable chain template extracted from a corpus entry.

    A skill template is the *shape* of a successful chain: the verb
    sequence, the initial visibility/taint, and the capability-set
    that permitted it. An operator can use a SkillTemplate to
    pattern-match future chains: "is this new chain's shape close to
    a known-good skill?".

    Attributes:
        verbs: tuple of verb names in order (the shape).
        initial_visibility: the chain's starting visibility label
            (read side) or "taint" sentinel (write side).
        capability_set_id: the capability set that permitted the
            original chain.
        gate_version: the gate version the original was checked with.
        source_digest: the corpus entry's corpus_digest.
        use_count: how many times this template has been matched
            (operator-incremented; the substrate never auto-counts).
    """

    verbs: Tuple[str, ...]
    initial_visibility: str
    capability_set_id: str
    gate_version: str
    source_digest: str
    use_count: int = 0

    def shape_matches(self, verbs: Tuple[str, ...]) -> bool:
        """True iff this template's verb-sequence exactly matches."""
        return self.verbs == verbs


def extract_skill(entry: CorpusEntry, initial_visibility: str = "secret") -> SkillTemplate:
    """Project a CorpusEntry into a reusable SkillTemplate.

    Args:
        entry: the corpus entry to project.
        initial_visibility: the chain's starting visibility
            (CLP) or "taint" sentinel (DSCC). The CLP default is
            "secret" (the strictest starting visibility).

    Returns:
        A SkillTemplate capturing the chain's verb sequence and
        the policy context that permitted it.
    """
    verbs = tuple(
        str(step.get("verb") or step.get("name") or step.get("op") or "<unnamed>")
        for step in entry.chain
    )
    return SkillTemplate(
        verbs=verbs,
        initial_visibility=initial_visibility,
        capability_set_id=entry.capability_set_id,
        gate_version=entry.gate_version,
        source_digest=entry.corpus_digest,
    )


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------


@dataclass
class CorpusStats:
    """Aggregate statistics over the corpus."""

    n_total: int
    n_allow: int
    n_by_gate: Dict[str, int]
    n_by_capability_set: Dict[str, int]
    digest: str  # SHA-256 of sorted (corpus_digest, ...) — corpus identity

    def action_distribution(self) -> Dict[str, int]:
        """Action distribution (always {"allow": n_total} for positive corpus)."""
        return {"allow": self.n_total, "block": 0, "block_and_escalate": 0}


class PositiveVerdictCorpus:
    """Append-only, content-addressed corpus of successful chain verdicts.

    Thread-unsafe by design (the substrate is single-threaded for
    gate evaluation; if you need concurrent appends, wrap with a
    lock). The corpus never drops entries; operators freeze and
    rotate.
    """

    def __init__(self, label: str = "default") -> None:
        self.label = label
        self._entries: List[CorpusEntry] = []
        self._by_digest: Dict[str, CorpusEntry] = {}
        self._trip_engine: Any = None  # optional ProbabilisticTripEngine

    # ----- attach / detach trip engine ----------------------------------

    def attach_trip_engine(self, engine: Any) -> None:
        """Attach a ProbabilisticTripEngine.

        The engine is *observed* on every successful record. The
        substrate never mutates the engine's internal state; the
        engine's own ``observe()`` API is what the operator calls.
        This method just stores the reference so callers can fetch
        it via ``trip_engine()``.
        """
        self._trip_engine = engine

    def detach_trip_engine(self) -> None:
        self._trip_engine = None

    def trip_engine(self) -> Optional[Any]:
        return self._trip_engine

    # ----- record / query ------------------------------------------------

    def record(
        self,
        chain: List[Dict[str, Any]],
        verdict_action: str,
        verdict_digest: str,
        gate_version: str,
        capability_set_id: str,
        reason: str = "",
        provenance: Optional[Dict[str, Any]] = None,
    ) -> CorpusEntry:
        """Record a successful chain verdict.

        Idempotent: re-recording the same
        (chain, verdict_digest, gate_version, capability_set_id)
        tuple returns the existing entry without appending a
        duplicate.

        Raises:
            ValueError: if ``verdict_action`` is not "allow".
        """
        if verdict_action != "allow":
            raise AssertionError(
                "positive_verdict_corpus only stores 'allow' verdicts; "
                f"got {verdict_action!r}"
            )
        cf = chain_fingerprint(chain)
        digest = _compute_corpus_digest(
            cf, verdict_digest, gate_version, capability_set_id
        )
        existing = self._by_digest.get(digest)
        if existing is not None:
            return existing
        entry = CorpusEntry(
            chain=list(chain),
            verdict_action=verdict_action,
            verdict_digest=verdict_digest,
            gate_version=gate_version,
            capability_set_id=capability_set_id,
            recorded_at=int(time.time() * 1000),
            corpus_digest=digest,
            reason=reason,
            provenance=dict(provenance or {}),
        )
        self._entries.append(entry)
        self._by_digest[digest] = entry
        return entry

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self._entries)

    def get(self, corpus_digest: str) -> Optional[CorpusEntry]:
        return self._by_digest.get(corpus_digest)

    def by_capability_set(self, capability_set_id: str) -> List[CorpusEntry]:
        return [e for e in self._entries if e.capability_set_id == capability_set_id]


    def query(
        self,
        capability_set_id: Optional[str] = None,
        gate_version: Optional[str] = None,
        shape_match: Optional[Tuple[str, ...]] = None,
    ) -> List["CorpusEntry"]:
        """Return entries matching all supplied filters."""
        results = []
        for entry in self._entries:
            if capability_set_id is not None and entry.capability_set_id != capability_set_id:
                continue
            if gate_version is not None and entry.gate_version != gate_version:
                continue
            if shape_match is not None:
                verbs = tuple(
                    (step.get("verb") or step.get("name") or "")
                    for step in entry.chain
                )
                if verbs != shape_match:
                    continue
            results.append(entry)
        return results

    def by_gate(self, gate_version: str) -> List[CorpusEntry]:
        return [e for e in self._entries if e.gate_version == gate_version]

    def chain_seen(
        self,
        chain: List[Dict[str, Any]],
        gate_version: Optional[str] = None,
        capability_set_id: Optional[str] = None,
    ) -> bool:
        """True iff a verdict for this exact chain is in the corpus.

        Optionally restrict the match to entries recorded under
        ``gate_version`` and/or ``capability_set_id``; useful when
        the operator wants to ask "have we ever run this chain under
        gate v1.2?" rather than "any version".
        """
        cf = chain_fingerprint(chain)
        for e in self._entries:
            if gate_version is not None and e.gate_version != gate_version:
                continue
            if capability_set_id is not None and e.capability_set_id != capability_set_id:
                continue
            if chain_fingerprint(e.chain) == cf:
                return True
        return False

    def stats(self) -> CorpusStats:
        n_by_gate: Dict[str, int] = {}
        n_by_cap: Dict[str, int] = {}
        for e in self._entries:
            n_by_gate[e.gate_version] = n_by_gate.get(e.gate_version, 0) + 1
            n_by_cap[e.capability_set_id] = n_by_cap.get(e.capability_set_id, 0) + 1
        digest = _corpus_identity_digest(self._entries)
        return CorpusStats(
            n_total=len(self._entries),
            n_allow=len(self._entries),
            n_by_gate=n_by_gate,
            n_by_capability_set=n_by_cap,
            digest=digest,
        )

    # ----- replay / verify -----------------------------------------------

    def verify_entry(
        self,
        entry: CorpusEntry,
        gate: Any,
        capability_set: Any,
    ) -> bool:
        """Re-run the gate against the frozen chain.

        Returns True iff the live verdict matches the recorded
        verdict_digest. A mismatch indicates that either the gate
        semantics have changed (expected after a version bump) or
        the capability set has changed (operator decision). Either
        way, the recorded entry is *stale* for the current
        (gate, capability_set) pair.

        Note: this method does NOT mutate the corpus. To refresh a
        stale entry, the operator should record a new entry under
        the new (gate_version, capability_set_id).
        """
        live_verdict = gate.evaluate_chain(entry.chain, capability_set)
        live_digest = getattr(live_verdict, "digest", None) or getattr(
            live_verdict, "audit_digest", None
        )
        if live_digest is None:
            raise ValueError(
                "gate verdict has no .digest / .audit_digest; cannot verify"
            )
        return live_digest == entry.verdict_digest

    # ----- skill extraction ---------------------------------------------

    def extract_skills(self, initial_visibility: str = "secret") -> List[SkillTemplate]:
        """Group entries by (verbs, initial_visibility, capability_set_id,
        gate_version) and project each group into a single SkillTemplate.

        The ``use_count`` of each template is the number of entries that
        fell into its group (a measure of how often the shape has
        succeeded in practice).

        The result is sorted by descending ``use_count`` then by
        ``(verbs, capability_set_id, gate_version)`` for stable display.
        """
        groups: Dict[Tuple[Tuple[str, ...], str, str, str], int] = {}
        for entry in self._entries:
            verbs = tuple(
                (step.get("verb") or step.get("name") or "") for step in entry.chain
            )
            key = (verbs, initial_visibility, entry.capability_set_id, entry.gate_version)
            groups[key] = groups.get(key, 0) + 1
        templates = [
            SkillTemplate(
                verbs=key[0],
                initial_visibility=key[1],
                capability_set_id=key[2],
                gate_version=key[3],
                source_digest="",
                use_count=count,
            )
            for key, count in groups.items()
        ]
        templates.sort(
            key=lambda s: (-s.use_count, s.verbs, s.capability_set_id, s.gate_version)
        )
        return templates

    def find_skill(
        self, verbs: Tuple[str, ...], gate_version: Optional[str] = None
    ) -> Optional[SkillTemplate]:
        """Find a skill template matching the verb sequence.

        If ``gate_version`` is given, the match is restricted to
        entries recorded under that gate version. The first matching
        entry is projected into a *fresh* ``SkillTemplate`` with
        ``use_count=1`` (this match is counted). Returns ``None`` if
        no entry matches.
        """
        for entry in self._entries:
            entry_verbs = tuple(
                (step.get("verb") or step.get("name") or "")
                for step in entry.chain
            )
            if entry_verbs != verbs:
                continue
            if gate_version is not None and entry.gate_version != gate_version:
                continue
            return SkillTemplate(
                verbs=verbs,
                initial_visibility="secret",
                capability_set_id=entry.capability_set_id,
                gate_version=entry.gate_version,
                source_digest=entry.corpus_digest,
                use_count=1,
            )
        return None

    # ----- persistence ---------------------------------------------------

    def to_json(self) -> str:
        """Serialize the corpus to JSON (for persistence/rotation)."""
        return json.dumps(
            {
                "label": self.label,
                "entries": [
                    {
                        "chain": e.chain,
                        "verdict_action": e.verdict_action,
                        "verdict_digest": e.verdict_digest,
                        "gate_version": e.gate_version,
                        "capability_set_id": e.capability_set_id,
                        "recorded_at": e.recorded_at,
                        "corpus_digest": e.corpus_digest,
                        "reason": e.reason,
                        "provenance": e.provenance,
                    }
                    for e in self._entries
                ],
                "stats_digest": self.stats().digest,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, payload: str) -> "PositiveVerdictCorpus":
        """Deserialize a corpus from JSON (preserves insertion order)."""
        data = json.loads(payload)
        corpus = cls(label=data.get("label", "default"))
        for raw in data.get("entries", []):
            entry = CorpusEntry(
                chain=raw["chain"],
                verdict_action=raw["verdict_action"],
                verdict_digest=raw["verdict_digest"],
                gate_version=raw["gate_version"],
                capability_set_id=raw["capability_set_id"],
                recorded_at=raw["recorded_at"],
                corpus_digest=raw["corpus_digest"],
                reason=raw.get("reason", ""),
                provenance=raw.get("provenance", {}),
            )
            corpus._entries.append(entry)
            corpus._by_digest[entry.corpus_digest] = entry
        return corpus


# ---------------------------------------------------------------------------
# Digest helpers
# ---------------------------------------------------------------------------


def _compute_corpus_digest(
    chain_fingerprint: str,
    verdict_digest: str,
    gate_version: str,
    capability_set_id: str,
) -> str:
    payload = json.dumps(
        {
            "chain_fingerprint": chain_fingerprint,
            "verdict_digest": verdict_digest,
            "gate_version": gate_version,
            "capability_set_id": capability_set_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _corpus_identity_digest(entries: List[CorpusEntry]) -> str:
    """Digest of the corpus as a whole (independent of insertion order)."""
    sorted_digests = sorted(e.corpus_digest for e in entries)
    payload = json.dumps(sorted_digests, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
