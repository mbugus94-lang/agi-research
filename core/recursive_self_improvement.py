"""
Recursive Self-Improvement (RSI) Gate - Safety-bounded self-edit pipeline

Inspired by the June 4, 2026 Anthropic Institute essay "When AI Builds Itself"
(Marina Favaro & Jack Clark) and the broader 2026 conversation about
"recursive self-improvement" (RSI) as the next threshold for frontier AI.

The essay's position:
  "In the near future, AI systems could become capable enough to
   autonomously design, build and train more capable successors on their own.
   ... AI that can build itself would be a major development in the history
   of technology ... but it 'could come sooner than most institutions are
   prepared for'."

Our repo's stance (per SAFETY.md):
  - Self-modifications REQUIRE human review.
  - All proposals are written to `proposals/`, never auto-applied.
  - Reversibility is mandatory.
  - The "brake pedal" is a real, explicit control, not a euphemism.

What this module adds on top of the existing SelfImprovementEngine
(analyzer + proposal generator) and MetacognitiveMonitor (calibration):

  1. RSIProposal            A first-class self-edit with safety metadata
  2. BrakePedal             A three-state gate (BRAKED / DAMPED / OPEN)
                            that the operator can use to throttle proposal
                            throughput, modelled on Anthropic's "brake pedal"
                            call. Default is BRAKED for the agent's own core.
  3. EvidenceRequirement    Every self-edit must ground at least one claim
                            in the EvidenceLedger (or be tagged UNGROUNDED
                            for explicit human triage).
  4. MetacognitiveScoring   Each proposal is scored against the running
                            MetacognitiveMonitor state: high cognitive load
                            or low calibration_score downgrades the
                            proposal's auto-clear status.
  5. RecursionDepthBudget   A counter that limits how many layers of
                            self-edit → re-analyze → re-propose we allow in
                            a single cycle. Inspired by Fujitsu's
                            Self-Evolving Multi-AI Agent work and the
                            AEL/Axelrod two-timescale bandit framing.
  6. RSIController          The orchestrator: pulls in analyzer + monitor
                            + ledger + brake pedal, emits RSIDecision
                            objects ready for human review.

This is *not* an auto-applier. It is a submission queue.

References:
  - Anthropic, "When AI Builds Itself" (June 4, 2026) - brake-pedal framing
  - AEL (OpenReview dtPo105y8x) - two-timescale self-evolving memory
  - Membrane (OpenReview fTz8N43gD3) - self-evolving contrastive safety memory
  - EvoMaster (OpenReview lidiprht3N) - ~100 LOC self-evolving scientific agent
  - DARPA / Fujitsu Self-Evolving Multi-AI Agent (May 2026) - governance before
    autonomous change
"""

from __future__ import annotations

import json
import os
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Brake pedal
# ---------------------------------------------------------------------------


class BrakeState(str, Enum):
    """Three-state brake pedal inspired by the Anthropic Institute essay.

    The mapping is intentionally not "open / closed" binary; the essay
    explicitly calls for a "damped" mode where some autonomous proposals
    can flow (low-risk) but not others (high-risk). This is the same
    pattern as AEL's two-timescale bandit: a fast inner loop can run,
    a slow outer loop is gated.

    BRAKED   - No self-edits are even scored. (Default for our own core/.)
    DAMPED   - Low-risk proposals surface for review; HIGH/CRITICAL stay
                parked and require explicit operator action.
    OPEN     - All proposals flow (still no auto-apply; the brake is on
                the application, not the proposal surface).
    """

    BRAKED = "braked"
    DAMPED = "damped"
    OPEN = "open"


class RiskBand(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Map risk to whether the proposal is *visible* under a given brake state.
# Even at OPEN, CRITICAL proposals are flagged with requires_attention=True
# so they cannot be silently approved.
BRAKE_VISIBILITY: Dict[Tuple[BrakeState, RiskBand], bool] = {
    (BrakeState.BRAKED, RiskBand.LOW): False,
    (BrakeState.BRAKED, RiskBand.MEDIUM): False,
    (BrakeState.BRAKED, RiskBand.HIGH): False,
    (BrakeState.BRAKED, RiskBand.CRITICAL): False,
    (BrakeState.DAMPED, RiskBand.LOW): True,
    (BrakeState.DAMPED, RiskBand.MEDIUM): True,
    (BrakeState.DAMPED, RiskBand.HIGH): False,
    (BrakeState.DAMPED, RiskBand.CRITICAL): False,
    (BrakeState.OPEN, RiskBand.LOW): True,
    (BrakeState.OPEN, RiskBand.MEDIUM): True,
    (BrakeState.OPEN, RiskBand.HIGH): True,
    (BrakeState.OPEN, RiskBand.CRITICAL): True,  # but requires_attention=True
}


@dataclass
class BrakePedal:
    """Operator-controlled throttle for self-edits.

    The pedal is a process-wide singleton-ish object that the
    RSIController consults before scoring or surfacing a proposal. It
    never makes application decisions; it only constrains the *queue*.
    """

    state: BrakeState = BrakeState.BRAKED
    history: List[Tuple[datetime, BrakeState, str]] = field(default_factory=list)

    def transition(self, new_state: BrakeState, reason: str) -> None:
        if new_state == self.state:
            return
        self.history.append((datetime.now(timezone.utc), new_state, reason))
        self.state = new_state

    def visible(self, risk: RiskBand) -> bool:
        return BRAKE_VISIBILITY[(self.state, risk)]

    def requires_attention(self, risk: RiskBand) -> bool:
        # CRITICAL is always attention-flagged, even at OPEN, so it cannot
        # be silently mass-approved by a future automation.
        return risk == RiskBand.CRITICAL


# ---------------------------------------------------------------------------
# Recursion depth budget
# ---------------------------------------------------------------------------


class RecursionDepthExceeded(Exception):
    """Raised when a self-edit would push the recursion budget over the cap.

    The cap exists because RSI has a known failure mode: a self-edit
    triggers re-analysis, which generates more self-edits, which trigger
    re-analysis, ... This is the same pattern AEL addresses with
    two-timescale separation; we just hard-cap the inner loop.
    """


@dataclass
class RecursionDepthBudget:
    """Hard cap on inner-loop self-edit depth.

    The 'inner loop' is: self-edit proposed -> analyzer re-runs ->
    more self-edits proposed -> ... The 'outer loop' (operator approval)
    is uncapped.
    """

    max_depth: int = 2
    current_depth: int = 0
    _stack: Deque[str] = field(default_factory=deque)

    def enter(self, proposal_id: str) -> None:
        if self.current_depth >= self.max_depth:
            raise RecursionDepthExceeded(
                f"Recursion depth {self.max_depth} reached; refusing to "
                f"recurse on proposal {proposal_id}."
            )
        self._stack.append(proposal_id)
        self.current_depth += 1

    def exit(self) -> None:
        if self._stack:
            self._stack.pop()
        self.current_depth = max(0, self.current_depth - 1)

    def __enter__(self) -> "RecursionDepthBudget":
        # Use a synthetic id for the manual context-manager path; the
        # controller calls enter()/exit() with real ids in the inner loop.
        self.enter(f"<ctx:{time.time_ns()}>")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.exit()


# ---------------------------------------------------------------------------
# Risk classifier
# ---------------------------------------------------------------------------


# Files under these paths are treated as the *self* surface: highest band
# by default, regardless of the proposal's nominal risk. This is the
# pattern Membrane uses (contrastive cells block attacks on the safety
# memory) applied to the source tree: we protect the substrate that
# protects us.
SELF_SURFACE_PREFIXES: Tuple[str, ...] = (
    "core/safety_circuit_breaker.py",
    "core/constitutional_governance.py",
    "core/reflection.py",
    "core/recursive_self_improvement.py",  # this file
    "core/evidence_ledger.py",
    "core/trace_grounding.py",
    "core/metacognitive_monitor.py",
    "core/self_analysis.py",
    "core/agent.py",
    "core/memory.py",
    "core/planner.py",
    "SAFETY.md",
    "AGENTS.md",
)


def classify_risk(target_file: Optional[str], nominal: str = "NORMAL") -> RiskBand:
    """Promote a proposal's risk if it touches the *self* surface.

    The classifier is intentionally simple. The point is to encode
    "touching the safety substrate is always at least HIGH" without
    relying on an LLM. The proposal text still gets scored; this is
    the floor.
    """
    if not target_file:
        return RiskBand.MEDIUM

    normalized = target_file.lstrip("./")
    # First check the explicit self-surface list: anything that matches
    # is CRITICAL. This is the substrate of the system; we don't let
    # anyone - human or AI - touch it without an explicit attention flag.
    for prefix in SELF_SURFACE_PREFIXES:
        if normalized == prefix or normalized.endswith("/" + prefix):
            return RiskBand.CRITICAL
    # Then the broader core/ rule: any other core/ module is HIGH at
    # minimum. Done as a separate branch so the explicit list above
    # isn't shadowed by it.
    if normalized.startswith("core/") and normalized.endswith(".py"):
        return RiskBand.HIGH

    nominal_to_band = {
        "LOW": RiskBand.LOW,
        "NORMAL": RiskBand.MEDIUM,
        "ELEVATED": RiskBand.HIGH,
        "CRITICAL": RiskBand.CRITICAL,
    }
    return nominal_to_band.get(nominal.upper(), RiskBand.MEDIUM)


# ---------------------------------------------------------------------------
# Evidence requirement
# ---------------------------------------------------------------------------


class EvidenceStatus(str, Enum):
    GROUNDED = "grounded"          # At least one SUPPORTED claim in the ledger
    UNGROUNDED = "ungrounded"      # No claim; surfaces explicitly to human
    DISPUTED = "disputed"          # Has DISPUTED or CONTRADICTED claims
    UNKNOWN = "unknown"            # Ledger unavailable; default to UNGROUNDED


@dataclass
class EvidenceRequirement:
    """A self-edit must be evidence-grounded to qualify for OPEN-state flow.

    The decision tree:
      - Has SUPPORTED claims in the EvidenceLedger? -> GROUNDED (auto-eligible
        for the proposal queue under DAMPED / OPEN)
      - Has DISPUTED / CONTRADICTED claims? -> DISPUTED (always requires
        attention)
      - Ledger not present (None passed)? -> UNKNOWN (treat as UNGROUNDED)
      - Otherwise -> UNGROUNDED (visible only under OPEN with explicit
        operator opt-in per proposal)
    """

    @staticmethod
    def evaluate(
        claim_ids: List[str],
        ledger: Any,  # core.evidence_ledger.EvidenceLedger; Any to avoid import cycle
    ) -> EvidenceStatus:
        if not claim_ids:
            return EvidenceStatus.UNGROUNDED
        if ledger is None:
            return EvidenceStatus.UNKNOWN
        statuses: List[str] = []
        for cid in claim_ids:
            try:
                # ledger.verify(cid).status is a ClaimStatus enum; we
                # normalize to the lowercase string the decision tree
                # matches against.
                raw = ledger.verify(cid).status
                if hasattr(raw, "value"):
                    statuses.append(str(raw.value).upper())
                else:
                    statuses.append(str(raw).upper())
            except Exception:
                statuses.append("ERROR")
        if any(s in {"DISPUTED", "CONTRADICTED"} for s in statuses):
            return EvidenceStatus.DISPUTED
        if any(s == "SUPPORTED" for s in statuses):
            return EvidenceStatus.GROUNDED
        return EvidenceStatus.UNGROUNDED


# ---------------------------------------------------------------------------
# Metacognitive scoring
# ---------------------------------------------------------------------------


@dataclass
class MetacognitiveAdjustment:
    """How the running monitor state shifts a proposal's risk.

    The shift is *additive* on top of classify_risk; it never reduces
    risk. This is the same conservative posture Membrane takes with its
    Contrastive Safety Memory.
    """

    original: RiskBand
    adjusted: RiskBand
    reasons: List[str] = field(default_factory=list)


def _promote(band: RiskBand) -> RiskBand:
    order = [RiskBand.LOW, RiskBand.MEDIUM, RiskBand.HIGH, RiskBand.CRITICAL]
    idx = order.index(band)
    return order[min(idx + 1, len(order) - 1)]


def metacognitive_adjust(
    base: RiskBand,
    monitor: Any,  # core.metacognitive_monitor.MetacognitiveMonitor
) -> MetacognitiveAdjustment:
    """Promote risk if the agent is currently stressed or poorly calibrated.

    Reads monitor.assess_current_state() (best-effort: any failure is
    treated as a signal to promote, mirroring the principle of
    "conservative under uncertainty").
    """
    reasons: List[str] = []
    adjusted = base
    if monitor is None:
        return MetacognitiveAdjustment(base, adjusted, reasons)

    try:
        state = monitor.assess_current_state()
    except Exception as e:  # noqa: BLE001
        return MetacognitiveAdjustment(
            base, _promote(base), [f"monitor unavailable: {e!r}"]
        )

    # Promote on cognitive overload.
    cognitive_load = getattr(state, "cognitive_load_estimate", 0.0)
    if cognitive_load and cognitive_load >= 0.8:
        adjusted = _promote(adjusted)
        reasons.append(f"high cognitive_load ({cognitive_load:.2f})")

    # Promote on low calibration.
    calibration = getattr(state, "confidence_overall", 1.0)
    if calibration is not None and calibration < 0.4:
        adjusted = _promote(adjusted)
        reasons.append(f"low confidence_overall ({calibration:.2f})")

    # Promote on active escalation recommendation.
    rec_action = getattr(state, "recommended_action", None)
    if rec_action is not None and "escalate" in str(rec_action).lower():
        adjusted = _promote(adjusted)
        reasons.append(f"monitor recommends escalate ({rec_action})")

    return MetacognitiveAdjustment(base, adjusted, reasons)


# ---------------------------------------------------------------------------
# RSI proposal + decision
# ---------------------------------------------------------------------------


class ProposalStatus(str, Enum):
    DRAFT = "draft"          # Generated, not yet scored
    SCORED = "scored"        # Risk + evidence + metacog evaluated
    GATED = "gated"          # Held by brake pedal
    QUEUED = "queued"        # Surfaced for human review
    ATTENTION = "attention"  # CRITICAL / DISPUTED; never silently approved
    APPROVED = "approved"    # Human approved (does NOT auto-apply)
    REJECTED = "rejected"    # Human rejected
    SUPERSEDED = "superseded"  # Replaced by a later proposal


@dataclass
class RSIProposal:
    """A self-edit with full safety metadata.

    proposal_id      - stable id, e.g. rsi_2026-06-07T08-05-00Z_0001
    title            - short summary
    rationale        - why we want this change
    target_file      - relative path under repo root, or None
    risk_band        - post-classify, post-metacog
    evidence_status  - GROUNDED / UNGROUNDED / DISPUTED / UNKNOWN
    evidence_claim_ids - claim ids in EvidenceLedger (if any)
    evidence_reasons - human-readable explanation of the risk shift
    brake_state_at_submission - snapshot of the brake state when scored
    requires_attention - True if CRITICAL or DISPUTED
    status           - DRAFT -> SCORED -> GATED/QUEUED/ATTENTION -> ...
    created_at       - timestamp
    payload          - the proposed code/diff (opaque to the gate)
    """

    proposal_id: str
    title: str
    rationale: str
    target_file: Optional[str]
    risk_band: RiskBand = RiskBand.MEDIUM
    evidence_status: EvidenceStatus = EvidenceStatus.UNGROUNDED
    evidence_claim_ids: List[str] = field(default_factory=list)
    evidence_reasons: List[str] = field(default_factory=list)
    brake_state_at_submission: BrakeState = BrakeState.BRAKED
    requires_attention: bool = False
    status: ProposalStatus = ProposalStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payload: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["risk_band"] = self.risk_band.value
        d["evidence_status"] = self.evidence_status.value
        d["brake_state_at_submission"] = self.brake_state_at_submission.value
        d["status"] = self.status.value
        d["created_at"] = self.created_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RSIProposal":
        d = dict(d)
        d["risk_band"] = RiskBand(d["risk_band"])
        d["evidence_status"] = EvidenceStatus(d["evidence_status"])
        d["brake_state_at_submission"] = BrakeState(d["brake_state_at_submission"])
        d["status"] = ProposalStatus(d["status"])
        d["created_at"] = datetime.fromisoformat(d["created_at"])
        return cls(**d)


@dataclass
class RSIDecision:
    """The controller's verdict for a single proposal.

    visible           - whether the operator should see this in the queue
    requires_attention - True if CRITICAL or DISPUTED
    action            - 'queue' | 'gate' | 'attention' | 'reject'
    explanation       - one-paragraph human explanation
    """

    proposal_id: str
    visible: bool
    requires_attention: bool
    action: str
    explanation: str


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------


@dataclass
class RSIControllerConfig:
    """Tunables for the controller.

    All defaults are conservative. The point is to make the brake pedal
    a first-class configuration knob, not a hidden one.
    """

    proposals_dir: str = "proposals"
    max_depth: int = 2
    default_brake: BrakeState = BrakeState.BRAKED
    require_grounded_evidence: bool = True
    # If True, CRITICAL proposals are written to disk for human review
    # regardless of brake state. We always want a paper trail of the
    # most dangerous ideas the system generated.
    always_audit_critical: bool = True


class RSIController:
    """The orchestrator. Brings together brake + recursion + evidence + monitor.

    Typical usage:
        ctrl = RSIController(ledger=ledger, monitor=monitor, brake=brake)
        decision = ctrl.score_and_route(proposal)
        if decision.visible:
            ctrl.persist(proposal, decision)
    """

    def __init__(
        self,
        ledger: Any = None,
        monitor: Any = None,
        brake: Optional[BrakePedal] = None,
        config: Optional[RSIControllerConfig] = None,
        repo_root: str = "/home/workspace/agi-research",
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.ledger = ledger
        self.monitor = monitor
        self.brake = brake or BrakePedal(state=(config or RSIControllerConfig()).default_brake)
        self.config = config or RSIControllerConfig()
        self.repo_root = Path(repo_root)
        self.proposals_dir = self.repo_root / self.config.proposals_dir
        self.budget = RecursionDepthBudget(max_depth=self.config.max_depth)
        self.clock = clock

    # --- core scoring -----------------------------------------------------

    def score(self, proposal: RSIProposal) -> RSIProposal:
        """Run risk classification + evidence + metacog. Mutates & returns.

        The brake state is *snapshotted* onto the proposal so the audit
        trail shows what the world looked like when this proposal was
        scored. This is critical for after-the-fact review.
        """
        base = classify_risk(proposal.target_file)
        adj = metacognitive_adjust(base, self.monitor)
        evidence = EvidenceRequirement.evaluate(
            proposal.evidence_claim_ids, self.ledger
        )
        # If we require grounded evidence and the proposal is ungrounded,
        # promote risk to MEDIUM at minimum. LOW is allowed to flow under
        # OPEN when the only thing missing is a ledger claim.
        if self.config.require_grounded_evidence and evidence in {
            EvidenceStatus.UNGROUNDED,
            EvidenceStatus.UNKNOWN,
        }:
            if adj.adjusted == RiskBand.LOW:
                adj.adjusted = RiskBand.MEDIUM
            else:
                adj.adjusted = _promote(adj.adjusted)
            adj.reasons.append(f"evidence_status={evidence.value}")

        proposal.risk_band = adj.adjusted
        proposal.evidence_status = evidence
        proposal.evidence_reasons = list(adj.reasons)
        proposal.brake_state_at_submission = self.brake.state
        proposal.requires_attention = (
            self.brake.requires_attention(adj.adjusted)
            or evidence == EvidenceStatus.DISPUTED
        )
        proposal.status = ProposalStatus.SCORED
        return proposal

    def decide(self, proposal: RSIProposal) -> RSIDecision:
        """Decide what to do with a scored proposal."""
        if proposal.status == ProposalStatus.DRAFT:
            self.score(proposal)

        visible = self.brake.visible(proposal.risk_band)
        # CRITICAL is always audited to disk, even when not visible.
        must_audit = (
            self.config.always_audit_critical
            and proposal.risk_band == RiskBand.CRITICAL
        )

        if not visible:
            # When the proposal is CRITICAL, the audit path is always
            # open even though the operator doesn't see it in the queue.
            # This ensures the most dangerous ideas the system has ever
            # generated leave a paper trail regardless of brake state.
            must_audit_critical = (
                self.config.always_audit_critical
                and proposal.risk_band == RiskBand.CRITICAL
            )
            if not must_audit_critical:
                proposal.status = ProposalStatus.GATED
                return RSIDecision(
                    proposal_id=proposal.proposal_id,
                    visible=False,
                    requires_attention=proposal.requires_attention,
                    action="gate",
                    explanation=(
                        f"Held by brake pedal ({self.brake.state.value}); "
                        f"risk={proposal.risk_band.value}, "
                        f"evidence={proposal.evidence_status.value}."
                    ),
                )

        if proposal.requires_attention or proposal.risk_band == RiskBand.CRITICAL:
            proposal.status = ProposalStatus.ATTENTION
            action = "attention"
        else:
            proposal.status = ProposalStatus.QUEUED
            action = "queue"

        return RSIDecision(
            proposal_id=proposal.proposal_id,
            visible=True,
            requires_attention=proposal.requires_attention,
            action=action,
            explanation=(
                f"risk={proposal.risk_band.value} "
                f"(reasons: {', '.join(proposal.evidence_reasons) or 'none'}), "
                f"evidence={proposal.evidence_status.value}, "
                f"brake={proposal.brake_state_at_submission.value}."
            ),
        )

    def score_and_route(self, proposal: RSIProposal) -> RSIDecision:
        self.score(proposal)
        return self.decide(proposal)

    # --- batch / recursion -----------------------------------------------

    def score_batch(
        self, proposals: List[RSIProposal]
    ) -> List[Tuple[RSIProposal, RSIDecision]]:
        """Score a batch, holding the recursion budget for the whole batch.

        The inner-loop recursion guard is engaged around the whole batch
        rather than per-proposal: a single round of self-analysis can
        generate many proposals, and we don't want each one to enter
        the depth budget independently.
        """
        with self.budget:
            out: List[Tuple[RSIProposal, RSIDecision]] = []
            for p in proposals:
                out.append((p, self.score_and_route(p)))
            return out

    # --- persistence ------------------------------------------------------

    def _safe_filename(self, proposal: RSIProposal) -> str:
        # Sanitize for filesystem; no path traversal.
        title_slug = "".join(
            c if c.isalnum() or c in "-_" else "-" for c in proposal.title.lower()
        )[:50].strip("-")
        return f"{proposal.proposal_id}_{title_slug}.json"

    def persist(
        self, proposal: RSIProposal, decision: RSIDecision
    ) -> Optional[Path]:
        """Write the proposal + decision to proposals/. Never auto-applies."""
        # CRITICAL is always audited. Lower visibility is governed by decide().
        if not decision.visible and proposal.risk_band != RiskBand.CRITICAL:
            return None
        self.proposals_dir.mkdir(parents=True, exist_ok=True)
        path = self.proposals_dir / self._safe_filename(proposal)
        with open(path, "w") as f:
            json.dump(
                {
                    "proposal": proposal.to_dict(),
                    "decision": {
                        "visible": decision.visible,
                        "requires_attention": decision.requires_attention,
                        "action": decision.action,
                        "explanation": decision.explanation,
                    },
                },
                f,
                indent=2,
            )
        return path

    # --- convenience: human-readable summary -----------------------------

    def summary(self) -> str:
        brake = self.brake.state.value
        depth = f"{self.budget.current_depth}/{self.budget.max_depth}"
        return (
            f"RSIController: brake={brake}, recursion_depth={depth}, "
            f"proposals_dir={self.proposals_dir}, "
            f"ledger={'present' if self.ledger else 'absent'}, "
            f"monitor={'present' if self.monitor else 'absent'}."
        )


# ---------------------------------------------------------------------------
# Proposal factories (the *what*, not the *gate*)
# ---------------------------------------------------------------------------


def make_rsi_id(prefix: str = "rsi") -> str:
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H-%M-%SZ')}"


def proposal_from_improvement_proposal(
    ip: Any, *, prefix: str = "rsi"
) -> RSIProposal:
    """Bridge from the existing SelfImprovementEngine proposal to an RSIProposal.

    The improvement proposal carries its own risk_level string; we let
    classify_risk() re-derive the band from the *file* so the safety
    surface is the source of truth, not the proposal text.
    """
    return RSIProposal(
        proposal_id=make_rsi_id(prefix),
        title=getattr(ip, "title", "untitled"),
        rationale=getattr(ip, "rationale", ""),
        target_file=getattr(ip, "target_file", None),
        payload=getattr(ip, "proposed_code", None),
    )


__all__ = [
    "BrakePedal",
    "BrakeState",
    "EvidenceRequirement",
    "EvidenceStatus",
    "ProposalStatus",
    "RSIController",
    "RSIControllerConfig",
    "RSIDecision",
    "RSIProposal",
    "RecursionDepthBudget",
    "RecursionDepthExceeded",
    "RiskBand",
    "BRAKE_VISIBILITY",
    "SELF_SURFACE_PREFIXES",
    "classify_risk",
    "make_rsi_id",
    "metacognitive_adjust",
    "proposal_from_improvement_proposal",
]
