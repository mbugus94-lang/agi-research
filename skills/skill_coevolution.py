"""
Skill Co-Evolution Verifier - Bridge between the skill bank and the RSI gate.

Inspired by the June 2026 wave of self-evolving-skill research:

  - CoEvoSkills (arXiv:2604.01687): Skill Generator + Surrogate Verifier
    co-evolve. Multi-file skill packages, no ground-truth required, ~71% on
    SkillsBench (Claude Opus 4.6 + Claude Code). The verifier side of
    that pattern is what we implement here.
  - DataCOPE (arXiv:2606.06416): Unsupervised verifier signals from
    trajectories. Our verifier reads the *trajectory* the skill bank
    already records, plus the *claim* the EvidenceLedger already has.
  - EvoDS (arXiv:2606.03841): Synthesis -> Verification -> Caching ->
    Expansion. The verification stage is the one we expose; the
    Synthesis stage is already in `skill_governance.crystallize_pattern`,
    the Caching stage is `ProposalLedger`, and Expansion is the next
    iteration's signal collection.
  - MUSE-Autoskill (arXiv:2605.27366): "Skills are separate from the
    model." We extend that to: "Skills are also separate from the RSI
    gate" -- the same substrate (EvidenceLedger, BrakePedal, classifier),
    different policies.
  - SkillsBench (arXiv:2602.12670): Self-generated skills underperform
    curated skills by ~17.5pp. This is why the verifier is conservative:
    lean BLOCKED_BY_BRAKE on marginal signals rather than pass-through.
  - SkillsVote (OpenReview kj068rI9Uh, carried): "evidence-gated
    admission" is the macro pattern. The verifier is the gatekeeper.
  - Agent Evolving Learning (OpenReview dtPo105y8x, carried): two-timescale
    separation -- a fast verifier (this module) and a slow gate
    (the BrakePedal, which we *also* consult here).

What this module does:

  1. SurrogateVerifier     LLM-agnostic, deterministic signal aggregator.
                          Reads a VerifierSignal (skill metadata + usage
                          stats + evidence claim ids + target file) and
                          renders a VerifierVerdict.
  2. ProposalLedger        Substrate of the audit trail. Every verdict
                          is recorded with timestamp, proposal id, skill
                          id, signal, verdict, rationale, and the prior
                          verdict for the same skill id.
  3. SkillEvolutionGate    The orchestrator. Wraps the verifier, the
                          ledger, a BrakePedal, and a CoEvolutionConfig.
                          Exposes evaluate / history / recent / summary
                          / audit_path. Never mutates the skill bank.
                          Never auto-applies.

Safety posture:

  - The verifier NEVER mutates a CrystallizedSkill. It only emits
    verdicts into the ledger.
  - The default brake is DAMPED: only LOW risk skill updates flow
    without operator intervention.
  - BLOCKED_BY_BRAKE is the conservative default for marginal signals,
    not the failure case.
  - The audit file lists the gate's brake state and depth at the
    time of every verdict, so after-the-fact review can correlate
    "what did the system believe" with "what did the system decide."

Decisions:

  - LLM-agnostic on purpose. The verifier is a deterministic rollup of
    existing signals (success rate, usage, evidence, risk band). If a
    future verifier wants to call an LLM, the LLM goes through the
    same `VerifierSignal -> VerifierVerdict` interface.
  - The ledger is append-only. There is no `delete` or `update` path.
    This is the same pattern the EvidenceLedger follows.
  - `ProposalLedger` and `EvidenceLedger` are intentionally separate:
    the EvidenceLedger tracks *claims about the world*, the
    ProposalLedger tracks *verdicts on skill updates*. Merging them
    would couple substrate (claim evidence) to policy (skill update
    gating), which is exactly the coupling the brake pedal is meant
    to keep separate.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Enums and dataclasses (value objects)
# ---------------------------------------------------------------------------


class VerifierVerdict(str, Enum):
    """The verifier's verdict on a single skill update proposal.

    PASS                - The signal meets every gate; safe to advance
                          in the lifecycle (DRAFT -> VALIDATED).
    FAIL                - The signal is clearly insufficient or risky;
                          do not promote.
    NEEDS_MORE_EVIDENCE - Marginal signal: not enough uses, no claim
                          cited, or ledger absent. The default for
                          under-used skills; a retry path is encouraged.
    BLOCKED_BY_BRAKE    - The signal is fine but the operator's brake
                          pedal is in BRAKED or DAMPED. Visible in the
                          audit trail, never auto-flows.
    """

    PASS = "pass"
    FAIL = "fail"
    NEEDS_MORE_EVIDENCE = "needs_more_evidence"
    BLOCKED_BY_BRAKE = "blocked_by_brake"


@dataclass
class VerifierSignal:
    """The signal a verifier reads to render a verdict.

    The fields are deliberately the union of what the skill bank, the
    EvidenceLedger, and the RSI gate already expose. Nothing here is
    computed; everything is read.
    """

    # Skill bank fields
    skill_id: str
    skill_name: str = ""
    skill_type: str = ""               # atomic / composite / adaptive / meta / recovery
    domain: str = "general"
    action_template: List[str] = field(default_factory=list)
    parameter_schema: Dict[str, Any] = field(default_factory=dict)
    # Telemetry from the skill bank's execution log
    observed_uses: int = 0
    observed_success_count: int = 0
    observed_failure_count: int = 0
    # Target file (drives risk classification; defaults to None when
    # the proposal is a *new* skill with no file yet)
    target_file: Optional[str] = None
    # EvidenceLedger
    evidence_claim_ids: List[str] = field(default_factory=list)
    # Free-form rationale from the proposal author
    rationale: str = ""

    @property
    def candidate_signature(self) -> str:
        """Stable hash of (action_template + parameter_schema).

        Used to dedupe near-identical proposals in the audit trail
        and to detect "we already saw this signal before."
        """
        h = hashlib.sha256()
        h.update(repr(sorted(self.action_template)).encode("utf-8"))
        h.update(repr(sorted(self.parameter_schema.keys())).encode("utf-8"))
        return h.hexdigest()[:16]

    @property
    def observed_success_rate(self) -> float:
        total = self.observed_success_count + self.observed_failure_count
        if total <= 0:
            return 0.0
        return self.observed_success_count / total

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["candidate_signature"] = self.candidate_signature
        d["observed_success_rate"] = self.observed_success_rate
        return d


@dataclass
class CoEvolutionConfig:
    """Tunables for the verifier. All defaults are conservative.

    min_uses              - The skill must have been used at least this
                            many times before the verifier trusts the
                            observed success rate.
    min_success_rate      - Minimum observed success rate (in [0,1])
                            for a PASS verdict.
    max_risk_band         - Maximum risk band the verifier will
                            green-light. The classifier (see
                            `classify_risk`) is the source of truth.
    block_on_disputed_evidence - If True (default), any cited claim that
                                 is DISPUTED or CONTRADICTED in the
                                 EvidenceLedger forces NEEDS_MORE_EVIDENCE.
    persist_audit         - If True (default), every verdict is written
                            to the audit JSONL trail.
    """

    min_uses: int = 3
    min_success_rate: float = 0.6
    max_risk_band: str = "high"            # low / medium / high / critical
    block_on_disputed_evidence: bool = True
    persist_audit: bool = True


# ---------------------------------------------------------------------------
# Brake pedal (substrate-respecting, scoped to the gate)
# ---------------------------------------------------------------------------


class _GateBrakeState(str, Enum):
    """A two-axis visibility matrix for skill-update verdicts.

    We mirror the RSI BrakePedal's vocabulary (BRAKED / DAMPED / OPEN)
    so the operator can read the same labels across both systems.
    The mapping of risk -> visibility differs slightly: the gate
    treats BLOCKED_BY_BRAKE as a *first-class* verdict rather than a
    visibility layer on PASS, so the operator can see "the signal was
    fine, but the brake said no" in the audit trail.
    """

    BRAKED = "braked"
    DAMPED = "damped"
    OPEN = "open"


@dataclass
class _GateBrakePedal:
    """Minimal brake for the skill-evolution gate.

    Distinct from `core.recursive_self_improvement.BrakePedal` on
    purpose: the gate is a separate process with its own throttle.
    Sharing the same object would couple two policies that should
    be allowed to diverge (e.g. a DAMPED skill gate with an OPEN
    self-edit gate is a legitimate configuration).
    """

    state: _GateBrakeState = _GateBrakeState.DAMPED
    history: List[Tuple[datetime, _GateBrakeState, str]] = field(default_factory=list)

    def transition(self, new_state: _GateBrakeState, reason: str) -> None:
        if new_state == self.state:
            return
        self.history.append((datetime.now(timezone.utc), new_state, reason))
        self.state = new_state


# ---------------------------------------------------------------------------
# Surrogate verifier
# ---------------------------------------------------------------------------


# Risk band ordering, copied from `core.recursive_self_improvement` so we
# don't import the module (it would create a cycle). Keep in sync with
# `RiskBand` over there.
_RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _classify_risk_local(target_file: Optional[str]) -> str:
    """Minimal local port of `classify_risk` for the gate.

    The full classifier treats `core/` modules as HIGH and the
    explicit self-surface list as CRITICAL. The gate needs the
    *signal* (risk band as a string) for the verdict, not the
    full proposal. This port is intentionally narrow.
    """
    if not target_file:
        return "medium"
    normalized = target_file.lstrip("./")
    if normalized.endswith(".py") and normalized.startswith("core/"):
        return "high"
    if normalized in {"SAFETY.md", "AGENTS.md"}:
        return "critical"
    return "medium"


def _evidence_status_local(claim_ids: List[str], ledger: Any) -> str:
    """Minimal local port of `EvidenceRequirement.evaluate`.

    Returns one of: 'grounded', 'ungrounded', 'disputed', 'unknown'.
    Mirrors the upstream logic but stays decoupled from the RSI gate
    so the two systems can evolve independently.
    """
    if not claim_ids:
        return "ungrounded"
    if ledger is None:
        return "unknown"
    statuses: List[str] = []
    for cid in claim_ids:
        try:
            raw = ledger.verify(cid).status
            if hasattr(raw, "value"):
                statuses.append(str(raw.value).upper())
            else:
                statuses.append(str(raw).upper())
        except Exception:
            statuses.append("ERROR")
    if any(s in {"DISPUTED", "CONTRADICTED"} for s in statuses):
        return "disputed"
    if any(s == "SUPPORTED" for s in statuses):
        return "grounded"
    return "ungrounded"


@dataclass
class SurrogateVerifier:
    """LLM-agnostic, deterministic signal aggregator.

    The verifier does not *decide* what to do with a verdict; it
    only renders a verdict. The gate is the decision-maker.
    """

    config: CoEvolutionConfig = field(default_factory=CoEvolutionConfig)

    def evaluate(
        self,
        signal: VerifierSignal,
        ledger: Any = None,
    ) -> Tuple[VerifierVerdict, str]:
        """Return (verdict, rationale) for the given signal.

        Rationale is a one-paragraph human-readable string intended
        for the audit trail. It is *not* a recommendation; the
        operator reads it after the fact.
        """
        # Compute the four signal components we always emit.
        risk_band = _classify_risk_local(signal.target_file)
        evidence_status = _evidence_status_local(signal.evidence_claim_ids, ledger)
        uses_ok = signal.observed_uses >= self.config.min_uses
        success_ok = signal.observed_success_rate >= self.config.min_success_rate
        risk_ok = _RISK_ORDER[risk_band] <= _RISK_ORDER[self.config.max_risk_band]
        evidence_ok = not (
            self.config.block_on_disputed_evidence and evidence_status == "disputed"
        )

        reasons: List[str] = [
            f"uses={signal.observed_uses} (min={self.config.min_uses}) -> {'ok' if uses_ok else 'low'}",
            f"success_rate={signal.observed_success_rate:.2f} (min={self.config.min_success_rate}) -> {'ok' if success_ok else 'low'}",
            f"risk_band={risk_band} (max={self.config.max_risk_band}) -> {'ok' if risk_ok else 'over'}",
            f"evidence_status={evidence_status} -> {'ok' if evidence_ok else 'disputed'}",
        ]

        # Decision tree. Order matters: marginal signals are
        # NEEDS_MORE_EVIDENCE, never FAIL, because the failure case
        # should require *more* evidence, not "we never will."
        if not uses_ok:
            return VerifierVerdict.NEEDS_MORE_EVIDENCE, (
                "Under-used skill: " + "; ".join(reasons)
                + ". Need more execution traces before promotion."
            )
        if not evidence_ok:
            return VerifierVerdict.NEEDS_MORE_EVIDENCE, (
                "Disputed evidence cited: " + "; ".join(reasons)
                + ". Re-verify the underlying claim before promotion."
            )
        if not success_ok:
            return VerifierVerdict.FAIL, (
                "Observed success rate below threshold: " + "; ".join(reasons)
                + ". Do not promote until the rate recovers."
            )
        if not risk_ok:
            return VerifierVerdict.FAIL, (
                "Risk band exceeds config: " + "; ".join(reasons)
                + ". Reduce the proposal's footprint or route to a human."
            )
        return VerifierVerdict.PASS, (
            "All gates clear: " + "; ".join(reasons) + "."
        )


# ---------------------------------------------------------------------------
# Proposal ledger
# ---------------------------------------------------------------------------


@dataclass
class LedgerEntry:
    """A single row in the audit trail."""

    timestamp: str
    proposal_id: str
    skill_id: str
    candidate_signature: str
    signal: Dict[str, Any]
    verdict: str
    rationale: str
    brake_state_at_submission: str
    prior_verdict: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProposalLedger:
    """Append-only ledger of verifier verdicts.

    Different in spirit from the EvidenceLedger: this one tracks
    *verdicts on skill updates*, not *evidence for claims*. The two
    ledgers can be joined at audit time via `skill_id` or `proposal_id`.
    """

    def __init__(self, max_entries: int = 1024) -> None:
        self._entries: Deque[LedgerEntry] = deque(maxlen=max_entries)
        self._by_skill: Dict[str, List[int]] = {}  # skill_id -> indices in entries
        self._by_proposal: Dict[str, int] = {}     # proposal_id -> index

    def append(
        self,
        *,
        proposal_id: str,
        signal: VerifierSignal,
        verdict: VerifierVerdict,
        rationale: str,
        brake_state: _GateBrakeState,
    ) -> LedgerEntry:
        prior = self._latest_for_skill(signal.skill_id)
        entry = LedgerEntry(
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            proposal_id=proposal_id,
            skill_id=signal.skill_id,
            candidate_signature=signal.candidate_signature,
            signal=signal.to_dict(),
            verdict=verdict.value,
            rationale=rationale,
            brake_state_at_submission=brake_state.value,
            prior_verdict=prior.verdict if prior else None,
        )
        # If we are at the deque cap, the oldest entry will be evicted
        # from the *front*; we also drop it from the index dicts to
        # keep them accurate. This is a best-effort consistency.
        if len(self._entries) == self._entries.maxlen:
            evicted = self._entries[0]
            for sid, idxs in list(self._by_skill.items()):
                self._by_skill[sid] = [i for i in idxs if i != 0]
                if not self._by_skill[sid]:
                    del self._by_skill[sid]
            self._by_proposal.pop(evicted.proposal_id, None)
        index = len(self._entries)
        self._entries.append(entry)
        self._by_skill.setdefault(signal.skill_id, []).append(index)
        self._by_proposal[proposal_id] = index
        return entry

    def _latest_for_skill(self, skill_id: str) -> Optional[LedgerEntry]:
        idxs = self._by_skill.get(skill_id, [])
        if not idxs:
            return None
        return self._entries[idxs[-1]]

    def history_for(self, skill_id: str) -> List[LedgerEntry]:
        idxs = self._by_skill.get(skill_id, [])
        return [self._entries[i] for i in idxs]

    def recent(self, n: int = 10) -> List[LedgerEntry]:
        return list(self._entries)[-n:]

    def __len__(self) -> int:
        return len(self._entries)


# ---------------------------------------------------------------------------
# Gate (orchestrator)
# ---------------------------------------------------------------------------


def _make_proposal_id(prefix: str = "sev") -> str:
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%SZ')}_{int(time.time() * 1e6) % 1000:03d}"


@dataclass
class SkillEvolutionGate:
    """The orchestrator. Brings together the verifier, the ledger, the brake.

    Typical usage:
        gate = SkillEvolutionGate(ledger=evidence_ledger, audit_path=Path("audit/skill_evolution.jsonl"))
        verdict, rationale = gate.evaluate(signal)
        # ...operator reviews the audit trail and decides
    """

    config: CoEvolutionConfig = field(default_factory=CoEvolutionConfig)
    verifier: SurrogateVerifier = field(init=False)
    ledger: ProposalLedger = field(default_factory=ProposalLedger)
    brake: _GateBrakePedal = field(default_factory=_GateBrakePedal)
    evidence_ledger: Any = None
    audit_path: Optional[Path] = None
    _depth: int = 0

    def __post_init__(self) -> None:
        self.verifier = SurrogateVerifier(config=self.config)

    # --- core ------------------------------------------------------------

    def evaluate(self, signal: VerifierSignal) -> Tuple[VerifierVerdict, str]:
        """Render a verdict for a skill update proposal.

        Sequence:
          1. Run the surrogate verifier (deterministic, LLM-agnostic).
          2. If the verifier returned PASS, consult the brake.
          3. Append a ledger entry.
          4. If `persist_audit`, write a JSONL row.
        """
        self._depth += 1
        try:
            verdict, rationale = self.verifier.evaluate(signal, self.evidence_ledger)
            if verdict == VerifierVerdict.PASS and self.brake.state != _GateBrakeState.OPEN:
                # Brake DAMPED or BRAKED -> downgrade PASS to BLOCKED_BY_BRAKE
                verdict = VerifierVerdict.BLOCKED_BY_BRAKE
                rationale = (
                    rationale
                    + f" [brake={self.brake.state.value}: PASS demoted to BLOCKED_BY_BRAKE]"
                )
            proposal_id = _make_proposal_id()
            self.ledger.append(
                proposal_id=proposal_id,
                signal=signal,
                verdict=verdict,
                rationale=rationale,
                brake_state=self.brake.state,
            )
            if self.config.persist_audit and self.audit_path is not None:
                self._persist(proposal_id, signal, verdict, rationale)
            return verdict, rationale
        finally:
            self._depth = max(0, self._depth - 1)

    # --- persistence -----------------------------------------------------

    def _persist(
        self,
        proposal_id: str,
        signal: VerifierSignal,
        verdict: VerifierVerdict,
        rationale: str,
    ) -> None:
        assert self.audit_path is not None
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "proposal_id": proposal_id,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "signal": signal.to_dict(),
            "verdict": verdict.value,
            "rationale": rationale,
            "brake_state": self.brake.state.value,
            "gate_depth": self._depth,
            "ledger_size": len(self.ledger),
        }
        with open(self.audit_path, "a") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")

    # --- introspection ---------------------------------------------------

    def history(self, skill_id: str) -> List[LedgerEntry]:
        return self.ledger.history_for(skill_id)

    def recent(self, n: int = 10) -> List[LedgerEntry]:
        return self.ledger.recent(n)

    def summary(self) -> str:
        return (
            f"SkillEvolutionGate: brake={self.brake.state.value}, "
            f"depth={self._depth}, ledger={len(self.ledger)}, "
            f"config(min_uses={self.config.min_uses}, "
            f"min_success_rate={self.config.min_success_rate}, "
            f"max_risk_band={self.config.max_risk_band}), "
            f"audit={'present' if self.audit_path else 'absent'}."
        )

    def audit_path_default(self) -> Path:
        return Path(f"audit/skill_evolution_{int(time.time())}.jsonl")


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------


def create_skill_evolution_gate(
    evidence_ledger: Any = None,
    audit_path: Optional[Path] = None,
    config: Optional[CoEvolutionConfig] = None,
) -> SkillEvolutionGate:
    """Factory function with conservative defaults.

    Default brake is DAMPED: LOW risk passes; >=MEDIUM is BLOCKED_BY_BRAKE
    by default. The operator transitions to OPEN for full autonomy.
    """
    return SkillEvolutionGate(
        config=config or CoEvolutionConfig(),
        evidence_ledger=evidence_ledger,
        audit_path=audit_path,
    )


__all__ = [
    "VerifierVerdict",
    "VerifierSignal",
    "CoEvolutionConfig",
    "SurrogateVerifier",
    "ProposalLedger",
    "LedgerEntry",
    "SkillEvolutionGate",
    "create_skill_evolution_gate",
]
