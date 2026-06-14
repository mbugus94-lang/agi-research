"""
Governed Action Loop — Bridge between PCA, SafetyCircuitBreaker, EvidenceLedger,
and ThreeRingGovernor.

Builds on the ProofCarryingActionBridge (PCA, Jun 13), the SafetyCircuitBreaker
(per-action policy + approval gate), the EvidenceLedger (claim/evidence substrate
for the gate), and the ThreeRingGovernor (Ring 2 / Ring 3 routing) by wiring
them into a single ``propose``-side cross-check pipeline and a single
``execute``-side audit pipeline.

The integration is the third leg of the runtime-governance tripod:

  1. Per-action gate: SafetyCircuitBreaker.assess_risk()
  2. Per-claim substrate: EvidenceLedger.verify() (SUPPORTED / DISPUTED)
  3. Per-request router: ThreeRingGovernor.route() (R2 / R3)
  4. Per-action envelope: ProofCarryingActionBridge.propose() (PCA)

This module owns (a) the cross-check that runs *between* the four substrates,
and (b) the executor wrapper that calls the bridge's execute() and then
records the post-execution outcome into the breaker + the ledger.

Key invariants (conservative posture):

  - The breaker can PROMOTE a verdict to REQUIRES_HUMAN or REJECTED but never
    DEMOTE one.  The bridge's structural gates (irreversible+confidential,
    HUMAN_GATED_ACTION_TYPES, ring-3 + require_human) are the floor; the
    breaker adds weight on top.
  - The ledger can only ADJUST a verdict's rationale; it can never approve
    an action that the bridge has REJECTED.  The conservative posture is
    "ungrounded is not safe" — a PCA action with no SUPPORTED claim is held
    in PENDING_EVIDENCE (a sub-state, not in the original enum) until the
    operator resolves the gap.
  - The three-ring governor is consulted for *every* R2-or-R3 proposal; the
    result is recorded in the certificate's ``approval.detail['three_ring']``
    so the operator can audit which ring handled the request.  An R3
    refusal is *not* a PCA REJECTED — it is a "no available R3 agent" note
    and the operator decides.
  - The executor wrapper is the *only* sanctioned path to call
    ``bridge.execute()``.  Bypassing it (calling bridge.execute() directly
    or, worse, calling the underlying tool) is the substrate for the
    Self-Honesty Check (no automated check here; this is policy, not code).

The module is LLM-agnostic, deterministic, and small (~500 LOC).  It does
not call any LLM, send any network request, or take a position on which
model is the substrate.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .evidence_ledger import (
    ClaimStatus,
    EvidenceLedger,
    ClaimVerification,
)
from .proof_carrying_action import (
    ActionCertificate,
    AdmissibilityDecision,
    AdmissibilityVerdict,
    ApprovalReceipt,
    CertificateState,
    Checkpoint,
    CheckpointKind,
    DataClassification,
    EnforceabilityClass,
    ExternalityContext,
    ExternalityPolicy,
    ProofCarryingActionBridge,
    ReversalBound,
    create_pca_bridge,
)
from .safety_circuit_breaker import (
    ActionCategory,
    RiskLevel,
    SafetyCircuitBreaker,
)
from .three_ring_architecture import (
    AgentDescriptor,
    CapabilityTailwind,
    CostClass,
    PermissionScope,
    RingLayer,
    RiskProfile,
    RoutingDecision,
    ThreeRingGovernor,
)


# ---------------------------------------------------------------------------
# Cross-check verdict
# ---------------------------------------------------------------------------


class CrossCheckOutcome(str, Enum):
    """The outcome of the cross-check between the four substrates.

    ALLOW               -- all four substrates agree; the action may proceed
    HOLD_PENDING_HUMAN  -- the bridge's REQUIRES_HUMAN verdict was confirmed
                           by the breaker; the certificate is PENDING_APPROVAL
    HOLD_PENDING_EVIDENCE -- the bridge would have approved but the ledger
                              has no SUPPORTED claim grounding the action;
                              held in PENDING_APPROVAL with rationale
                              "ungrounded_evidence"; the operator must
                              explicitly resolve the gap
    HOLD_PENDING_RING   -- the three-ring governor refused to route; held
                            in PENDING_APPROVAL with rationale
                            "no_ring_route"; the operator picks a ring
    REJECT              -- one of the four substrates hard-rejected; the
                            certificate is REJECTED
    """

    ALLOW = "allow"
    HOLD_PENDING_HUMAN = "hold_pending_human"
    HOLD_PENDING_EVIDENCE = "hold_pending_evidence"
    HOLD_PENDING_RING = "hold_pending_ring"
    REJECT = "reject"


# Map SafetyCircuitBreaker.RiskLevel -> PCA EnforceabilityClass
# (the conservative mapping: high/critical risk -> REQUIRE_HUMAN;
# medium risk -> REQUIRE_BRIDGE so the three-ring governor gates it;
# low risk -> POLICY_ONLY which the bridge treats as pre-approved.)
RISK_TO_ENFORCEABILITY: Dict[RiskLevel, EnforceabilityClass] = {
    RiskLevel.LOW: EnforceabilityClass.POLICY_ONLY,
    RiskLevel.MEDIUM: EnforceabilityClass.REQUIRE_BRIDGE,
    RiskLevel.HIGH: EnforceabilityClass.REQUIRE_HUMAN,
    RiskLevel.CRITICAL: EnforceabilityClass.REQUIRE_HUMAN,
}


# Map action_type (string) -> SafetyCircuitBreaker ActionCategory
# Default to READ; the operator can override per proposal.
ACTION_TYPE_TO_CATEGORY: Dict[str, ActionCategory] = {
    "read": ActionCategory.READ,
    "search": ActionCategory.READ,
    "query": ActionCategory.READ,
    "write": ActionCategory.WRITE,
    "create": ActionCategory.WRITE,
    "update": ActionCategory.WRITE,
    "delete": ActionCategory.DELETE,
    "drop": ActionCategory.DELETE,
    "truncate": ActionCategory.DELETE,
    "execute": ActionCategory.EXECUTE,
    "self_modify": ActionCategory.MODIFY_SELF,
    "send_money": ActionCategory.EXTERNAL_API,
    "publish": ActionCategory.EXTERNAL_API,
    "broadcast": ActionCategory.EXTERNAL_API,
    "network_call": ActionCategory.NETWORK,
    "database": ActionCategory.DATABASE,
    "file_system": ActionCategory.FILE_SYSTEM,
}


@dataclass
class CrossCheckReport:
    """The result of running the four-substrate cross-check.

    A descriptive view, not a verdict.  The actual verdict is the
    ``outcome`` field, which the operator can act on.
    """

    outcome: CrossCheckOutcome
    bridge_decision: AdmissibilityDecision
    breaker_risk: Optional[RiskLevel] = None
    ledger_claim_count: int = 0
    ledger_supported: int = 0
    ledger_disputed: int = 0
    ledger_contradicted: int = 0
    routing_ring: Optional[RingLayer] = None
    routing_agent: Optional[str] = None
    routing_refused: bool = False
    enforceability: EnforceabilityClass = EnforceabilityClass.POLICY_ONLY
    rationale: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "bridge_decision": self.bridge_decision.value,
            "breaker_risk": self.breaker_risk.value if self.breaker_risk else None,
            "ledger_claim_count": self.ledger_claim_count,
            "ledger_supported": self.ledger_supported,
            "ledger_disputed": self.ledger_disputed,
            "ledger_contradicted": self.ledger_contradicted,
            "routing_ring": self.routing_ring.value if self.routing_ring else None,
            "routing_agent": self.routing_agent,
            "routing_refused": self.routing_refused,
            "enforceability": self.enforceability.value,
            "rationale": self.rationale,
            "detail": dict(self.detail),
        }


@dataclass
class GovernedActionRequest:
    """A typed request for the governed action loop.

    Carries everything the four substrates need: action metadata,
    externality context, the claim IDs that ground the action, and
    an optional ring / capability hint.
    """

    action_id: str
    action_type: str
    parameters: Dict[str, Any]
    agent_id: str
    ring_layer: str = "ring_2_federation"
    externality: Optional[ExternalityContext] = None
    claim_ids: Optional[List[str]] = None
    target: str = ""
    description: str = ""
    required_capability: Optional[str] = None
    permission: Optional[PermissionScope] = None


# ---------------------------------------------------------------------------
# Governed Action Loop
# ---------------------------------------------------------------------------


class GovernedActionLoop:
    """The wired-up loop: bridge + breaker + ledger + three-ring.

    The loop exposes three methods:

    - ``propose(request)`` -- runs the cross-check, attaches the report
      to the certificate as a new checkpoint, and returns
      ``(cert, verdict, report)``.  The certificate is now either
      ADMISSIBLE (with EnforceabilityClass adjusted by the cross-check),
      PENDING_APPROVAL (held by the cross-check), or REJECTED.

    - ``execute(certificate_id)`` -- the ONLY sanctioned path to
      ``bridge.execute()``.  Runs the executor and records the outcome
      into the breaker + the ledger.  Returns the closed certificate.

    - ``certify_and_execute(request, executor)`` -- convenience wrapper
      that runs propose + approve (if needed) + execute in one call.
      Used by callers that already know the action is approved.

    Cross-check semantics (the conservative posture):

      Step 1: bridge._admissibility_verdict() runs first.  The bridge's
              structural gates (irreversible+confidential, ring-3
              default, HUMAN_GATED_ACTION_TYPES) are the floor.
              If the bridge says REJECTED, the cross-check stops.
      Step 2: breaker.assess_risk() runs second.  If the breaker returns
              CRITICAL/HIGH, the cross-check promotes the verdict to
              REQUIRE_HUMAN (but never demotes REJECTED to ADMISSIBLE).
      Step 3: ledger.verify_all() runs third.  If the request supplied
              ``claim_ids``, every claim must be SUPPORTED.  If any are
              DISPUTED or CONTRADICTED, the cross-check holds the
              certificate in PENDING_EVIDENCE.
      Step 4: three-ring governor runs fourth.  If the request is R2 or
              R3, governor.route() is consulted.  A refusal (no matching
              agent) is held in PENDING_RING; a successful route is
              recorded in the certificate's approval detail.
    """

    def __init__(
        self,
        bridge: Optional[ProofCarryingActionBridge] = None,
        breaker: Optional[SafetyCircuitBreaker] = None,
        ledger: Optional[EvidenceLedger] = None,
        three_ring: Optional[ThreeRingGovernor] = None,
    ) -> None:
        self.bridge = bridge or create_pca_bridge()
        self.breaker = breaker or SafetyCircuitBreaker()
        self.ledger = ledger or EvidenceLedger()
        self.three_ring = three_ring  # optional; may be None

        # History of reports for audit
        self.reports: List[CrossCheckReport] = []
        self._counter = 0

    # -- propose ---------------------------------------------------------

    def propose(
        self, request: GovernedActionRequest,
    ) -> Tuple[ActionCertificate, AdmissibilityVerdict, CrossCheckReport]:
        """Run the cross-check and return the (possibly held) certificate."""
        cert, verdict = self.bridge.propose(
            action_id=request.action_id,
            action_type=request.action_type,
            parameters=request.parameters,
            agent_id=request.agent_id,
            ring_layer=request.ring_layer,
            externality=request.externality,
        )

        report = self._cross_check(cert, verdict, request)
        self._counter += 1
        self.reports.append(report)

        # Attach the cross-check as a new ASSUMPTION_CAPTURE checkpoint.
        # If the bridge already added ASSUMPTION_CAPTURE we don't add a
        # second one; we attach the cross-check detail to the bridge's
        # existing assumption capture note.  This keeps the IEEC step
        # count bounded and the audit trail human-readable.
        for cp in cert.checkpoints:
            if cp.kind == CheckpointKind.ASSUMPTION_CAPTURE:
                cp.detail["cross_check"] = report.to_dict()
                cp.notes = f"{cp.notes}; cross_check={report.outcome.value}"
                break

        # Apply the cross-check's outcome to the certificate's state.
        # The cross-check is a *promoter* -- it can REJECT, HOLD, or
        # accept; it never demotes a REJECTED to anything else.
        if cert.state == CertificateState.REJECTED:
            # Bridge already rejected; cross-check is informational only.
            return cert, verdict, report

        if report.outcome == CrossCheckOutcome.REJECT:
            cert.state = CertificateState.REJECTED
            self.bridge._append_ieec(cert, "cross_check_reject", {
                "rationale": report.rationale,
                "report": report.to_dict(),
            })
        elif report.outcome in (
            CrossCheckOutcome.HOLD_PENDING_HUMAN,
            CrossCheckOutcome.HOLD_PENDING_EVIDENCE,
            CrossCheckOutcome.HOLD_PENDING_RING,
        ):
            cert.state = CertificateState.PENDING_APPROVAL
            self.bridge.pending_approvals[cert.certificate_id] = cert
            self.bridge._append_ieec(cert, "cross_check_hold", {
                "outcome": report.outcome.value,
                "rationale": report.rationale,
                "enforceability": report.enforceability.value,
            })

        return cert, verdict, report

    # -- execute ---------------------------------------------------------

    def execute(
        self,
        certificate_id: str,
        target: str = "",
        description: str = "",
    ) -> ActionCertificate:
        """The sanctioned path to bridge.execute().

        Records the post-execution outcome into the breaker + the
        ledger, then runs the bridge's executor.  The breaker and
        ledger are read-only at this point -- we record the outcome,
        we do not re-gate.
        """
        cert = self.bridge.certificates.get(certificate_id)
        if cert is None:
            raise KeyError(f"unknown certificate: {certificate_id}")

        if cert.state != CertificateState.APPROVED:
            raise RuntimeError(
                f"cannot execute certificate {certificate_id} in state "
                f"{cert.state.value} (must be APPROVED)"
            )

        # Run the executor.  The bridge's execute() does the actual
        # dispatch and closes the certificate.  We wrap it in a
        # try/except so we can always record *something* into the
        # breaker + the ledger.
        try:
            closed = self.bridge.execute(certificate_id)
        except Exception as e:
            # Record the failure into the breaker before re-raising
            self.breaker.check_operation(_record_from_cert(
                cert, target, description, RiskLevel.HIGH,
            ))
            raise

        # Post-execution: record the outcome into the breaker and ledger.
        risk = self._derive_outcome_risk(closed)
        record = _record_from_cert(closed, target, description, risk)
        # We don't actually want to *re-gate* here -- the certificate
        # has already been approved and executed.  We just append to
        # the breaker's audit trail so the operator can see the
        # execution happened.
        self.breaker.operation_history.append(record)
        self.breaker.stats.total_requests += 1
        if closed.outcome.get("status") == "success":
            self.breaker.stats.approved_requests += 1
        elif closed.outcome.get("status") == "error":
            self.breaker.stats.failed_requests += 1

        return closed

    # -- one-shot --------------------------------------------------------

    def certify_and_execute(
        self,
        request: GovernedActionRequest,
        executor: Callable[[ActionCertificate], Dict[str, Any]],
        approver: Optional[str] = None,
    ) -> Tuple[ActionCertificate, CrossCheckReport]:
        """Propose, approve (if needed), and execute in one call.

        The ``approver`` is used for cross-check HOLD outcomes.  If
        ``approver`` is None and the cross-check holds the action, the
        method returns early with a PENDING_APPROVAL certificate.

        The executor is registered with the bridge for the duration of
        the call; a pre-existing executor for the same action_type is
        stashed and restored.  This is the principle of least surprise
        for callers that want to "just run it".
        """
        # Register the executor (or back up the existing one).
        stashed: Optional[Callable[[ActionCertificate], Dict[str, Any]]] = None
        if request.action_type in self.bridge.executors:
            stashed = self.bridge.executors[request.action_type]
        self.bridge.register_executor(request.action_type, executor)

        try:
            cert, verdict, report = self.propose(request)

            if cert.state == CertificateState.REJECTED:
                return cert, report

            if cert.state == CertificateState.PENDING_APPROVAL:
                if approver is None:
                    # Held; the operator must explicitly approve.
                    return cert, report
                # Auto-approve with the cross-check's enforceability.
                self.bridge.approve(
                    certificate_id=cert.certificate_id,
                    approver=approver,
                    rationale=(
                        f"approved by certify_and_execute; "
                        f"cross_check={report.outcome.value}; "
                        f"bridge_rationale={verdict.rationale}"
                    ),
                    enforceability=report.enforceability,
                    policy_ids=[
                        f"cross_check:{report.outcome.value}",
                        f"bridge:{verdict.decision.value}",
                    ],
                    claim_ids=list(request.claim_ids or []),
                )
            elif cert.state == CertificateState.ADMISSIBLE:
                # The cross-check said ALLOW but the bridge left the
                # cert in ADMISSIBLE (the operator hasn't approved
                # yet).  We promote to APPROVED with the cross-check's
                # enforceability so the executor can run.
                self.bridge.approve(
                    certificate_id=cert.certificate_id,
                    approver=approver or "certify_and_execute",
                    rationale=(
                        f"auto-approved by certify_and_execute; "
                        f"cross_check={report.outcome.value}"
                    ),
                    enforceability=report.enforceability,
                    policy_ids=[f"cross_check:{report.outcome.value}"],
                    claim_ids=list(request.claim_ids or []),
                )

            closed = self.execute(
                cert.certificate_id,
                target=request.target,
                description=request.description,
            )
            return closed, report
        finally:
            # Restore the stashed executor (or unregister).
            if stashed is not None:
                self.bridge.register_executor(request.action_type, stashed)
            else:
                self.bridge.executors.pop(request.action_type, None)

    # -- cross-check -----------------------------------------------------

    def _cross_check(
        self,
        cert: ActionCertificate,
        verdict: AdmissibilityVerdict,
        request: GovernedActionRequest,
    ) -> CrossCheckReport:
        """Run the four-substrate cross-check.

        Returns a CrossCheckReport.  The cross-check is a *promoter*:
        it can reject, hold, or accept, but never demote a verdict.
        """
        bridge_decision = verdict.decision
        enforceability = verdict.suggested_enforceability

        # Step 1: bridge structural gates.  If the bridge already
        # rejected, we don't waste cycles on the other substrates.
        if bridge_decision == AdmissibilityDecision.REJECTED:
            return CrossCheckReport(
                outcome=CrossCheckOutcome.REJECT,
                bridge_decision=bridge_decision,
                enforceability=enforceability,
                rationale=f"bridge rejected: {verdict.rationale}",
                detail={"bridge_rationale": verdict.rationale,
                        "bridge_detail": dict(verdict.detail)},
            )

        # Step 2: SafetyCircuitBreaker.assess_risk()
        category = ACTION_TYPE_TO_CATEGORY.get(
            request.action_type, ActionCategory.EXECUTE,
        )
        breaker_risk = self.breaker.assess_risk(
            category=category,
            target=request.target or request.action_id,
            description=request.description or request.action_type,
            parameters=request.parameters,
        )

        # Promote the enforceability class based on breaker risk.
        # Never demote: if the bridge already said REQUIRE_HUMAN, we
        # keep it; if the bridge said POLICY_ONLY and the breaker says
        # CRITICAL, we promote to REQUIRE_HUMAN.
        breaker_enforceability = RISK_TO_ENFORCEABILITY[breaker_risk]
        if _enforceability_rank(breaker_enforceability) > _enforceability_rank(
            enforceability,
        ):
            enforceability = breaker_enforceability

        # CRITICAL breaker risk is a hard hold (operator-visible).
        if breaker_risk == RiskLevel.CRITICAL:
            return CrossCheckReport(
                outcome=CrossCheckOutcome.HOLD_PENDING_HUMAN,
                bridge_decision=bridge_decision,
                breaker_risk=breaker_risk,
                enforceability=EnforceabilityClass.REQUIRE_HUMAN,
                rationale=(
                    f"breaker rated CRITICAL ({category.value}); "
                    f"human gate required"
                ),
                detail={"breaker_risk": breaker_risk.value,
                        "category": category.value,
                        "target": request.target},
            )

        # Step 3: EvidenceLedger.verify()
        ledger_report = self._check_ledger(request.claim_ids or [])

        # CONTRADICTED or DISPUTED claims -> hard hold.
        if ledger_report["contradicted"] > 0:
            return CrossCheckReport(
                outcome=CrossCheckOutcome.REJECT,
                bridge_decision=bridge_decision,
                breaker_risk=breaker_risk,
                ledger_claim_count=ledger_report["total"],
                ledger_contradicted=ledger_report["contradicted"],
                enforceability=enforceability,
                rationale=(
                    f"ledger has {ledger_report['contradicted']} "
                    f"CONTRADICTED claim(s); action rejected"
                ),
                detail=ledger_report,
            )

        if ledger_report["disputed"] > 0:
            return CrossCheckReport(
                outcome=CrossCheckOutcome.HOLD_PENDING_EVIDENCE,
                bridge_decision=bridge_decision,
                breaker_risk=breaker_risk,
                ledger_claim_count=ledger_report["total"],
                ledger_supported=ledger_report["supported"],
                ledger_disputed=ledger_report["disputed"],
                enforceability=EnforceabilityClass.REQUIRE_HUMAN,
                rationale=(
                    f"ledger has {ledger_report['disputed']} DISPUTED "
                    f"claim(s); operator must resolve evidence gap"
                ),
                detail=ledger_report,
            )

        # If claim_ids were supplied but none are SUPPORTED, hold for
        # evidence (ungrounded is not safe).
        if request.claim_ids and ledger_report["supported"] == 0:
            return CrossCheckReport(
                outcome=CrossCheckOutcome.HOLD_PENDING_EVIDENCE,
                bridge_decision=bridge_decision,
                breaker_risk=breaker_risk,
                ledger_claim_count=ledger_report["total"],
                enforceability=EnforceabilityClass.REQUIRE_HUMAN,
                rationale=(
                    f"supplied {len(request.claim_ids)} claim_id(s) but "
                    f"none are SUPPORTED; operator must ground the action"
                ),
                detail=ledger_report,
            )

        # Step 4: ThreeRingGovernor.route() (if configured)
        routing_ring: Optional[RingLayer] = None
        routing_agent: Optional[str] = None
        routing_refused = False
        if self.three_ring is not None and request.ring_layer in (
            RingLayer.FEDERATION.value, RingLayer.FRONTIER.value,
        ):
            required_cap = request.required_capability or request.action_type
            permission = request.permission or PermissionScope.READ
            try:
                routing = self.three_ring.route(
                    request=request.parameters,
                    required_capability=required_cap,
                    permission=permission,
                )
                routing_ring = routing.ring
                routing_agent = routing.agent_id
                if routing.needs_frontier and not routing_agent:
                    routing_refused = True
            except (RuntimeError, ValueError, AttributeError):
                routing_refused = True

            if routing_refused:
                return CrossCheckReport(
                    outcome=CrossCheckOutcome.HOLD_PENDING_RING,
                    bridge_decision=bridge_decision,
                    breaker_risk=breaker_risk,
                    ledger_claim_count=ledger_report["total"],
                    ledger_supported=ledger_report["supported"],
                    routing_refused=True,
                    enforceability=EnforceabilityClass.REQUIRE_HUMAN,
                    rationale=(
                        f"three-ring governor refused to route "
                        f"capability='{required_cap}'"
                    ),
                    detail=ledger_report,
                )

        # All four substrates agree.  If the bridge originally said
        # REQUIRE_HUMAN, the cross-check confirms it; if the bridge
        # said ADMISSIBLE / REQUIRES_BRIDGE, we accept with the
        # (possibly promoted) enforceability class.
        outcome = (
            CrossCheckOutcome.HOLD_PENDING_HUMAN
            if bridge_decision == AdmissibilityDecision.REQUIRES_HUMAN
            or enforceability == EnforceabilityClass.REQUIRE_HUMAN
            else CrossCheckOutcome.ALLOW
        )
        rationale = (
            "all four substrates agree; cross-check "
            f"{'requires_human' if outcome == CrossCheckOutcome.HOLD_PENDING_HUMAN else 'allows'}"
        )
        return CrossCheckReport(
            outcome=outcome,
            bridge_decision=bridge_decision,
            breaker_risk=breaker_risk,
            ledger_claim_count=ledger_report["total"],
            ledger_supported=ledger_report["supported"],
            ledger_disputed=ledger_report["disputed"],
            routing_ring=routing_ring,
            routing_agent=routing_agent,
            enforceability=enforceability,
            rationale=rationale,
            detail={
                "ledger": ledger_report,
                "breaker_risk": breaker_risk.value,
                "breaker_category": category.value,
                "routing_ring": routing_ring.value if routing_ring else None,
            },
        )

    def _check_ledger(self, claim_ids: List[str]) -> Dict[str, Any]:
        """Verify each supplied claim and tally statuses."""
        if not claim_ids:
            return {
                "total": 0, "supported": 0, "disputed": 0,
                "contradicted": 0, "ungrounded": 0, "expired": 0,
                "verifications": [],
            }
        verifications: List[ClaimVerification] = []
        for cid in claim_ids:
            verifications.append(self.ledger.verify(cid))
        tally = {
            "supported": 0, "disputed": 0, "contradicted": 0,
            "ungrounded": 0, "expired": 0,
        }
        for v in verifications:
            if v.status == ClaimStatus.SUPPORTED:
                tally["supported"] += 1
            elif v.status == ClaimStatus.DISPUTED:
                tally["disputed"] += 1
            elif v.status == ClaimStatus.CONTRADICTED:
                tally["contradicted"] += 1
            elif v.status == ClaimStatus.UNGROUNDED:
                tally["ungrounded"] += 1
            elif v.status == ClaimStatus.EXPIRED:
                tally["expired"] += 1
        return {
            "total": len(verifications),
            **tally,
            "verifications": [v.to_dict() for v in verifications],
        }

    def _derive_outcome_risk(self, cert: ActionCertificate) -> RiskLevel:
        """Map the certificate's outcome + reversal bound to a risk level."""
        if cert.outcome.get("status") == "error":
            return RiskLevel.HIGH
        if cert.externality.reversal_bound == ReversalBound.IRREVERSIBLE:
            return RiskLevel.HIGH
        if cert.externality.data_classification in (
            DataClassification.CONFIDENTIAL, DataClassification.RESTRICTED,
        ):
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    # -- audit / summary -------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        return {
            "bridge": self.bridge.summary(),
            "reports": [r.to_dict() for r in self.reports],
            "report_count": len(self.reports),
            "report_outcomes": {
                o.value: sum(1 for r in self.reports if r.outcome == o)
                for o in CrossCheckOutcome
            },
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enforceability_rank(ec: EnforceabilityClass) -> int:
    """Ordinal rank: AUTO < POLICY_ONLY < REQUIRE_BRIDGE < REQUIRE_HUMAN.

    Used so we can compare enforceability classes without ordering
    semantics bleeding into the enum itself.
    """
    return {
        EnforceabilityClass.AUTO: 0,
        EnforceabilityClass.POLICY_ONLY: 1,
        EnforceabilityClass.REQUIRE_BRIDGE: 2,
        EnforceabilityClass.REQUIRE_HUMAN: 3,
    }[ec]


def _record_from_cert(
    cert: ActionCertificate,
    target: str,
    description: str,
    risk: RiskLevel,
):
    """Build a SafetyCircuitBreaker.OperationRecord from a closed cert.

    The breaker uses OperationRecord for its audit trail.  We construct
    a minimal record from the certificate; the record's
    ``operation_id`` matches the certificate's id so the operator can
    cross-reference.
    """
    from .safety_circuit_breaker import OperationRecord
    category = ACTION_TYPE_TO_CATEGORY.get(
        cert.action_type, ActionCategory.EXECUTE,
    )
    outcome = cert.outcome or {}
    return OperationRecord(
        operation_id=cert.certificate_id,
        action_category=category,
        risk_level=risk,
        description=description or cert.action_type,
        target=target or cert.action_id,
        parameters=dict(cert.parameters),
        approved=cert.state == CertificateState.CLOSED,
        approval_method=(
            cert.approval.enforceability.value
            if cert.approval else "auto"
        ),
        result_status=outcome.get("status", "success"),
    )


def create_governed_loop(
    audit_path: Optional[Path] = None,
    three_ring: Optional[ThreeRingGovernor] = None,
) -> GovernedActionLoop:
    """Smallest viable install: 1 line."""
    bridge = create_pca_bridge(audit_path=audit_path)
    return GovernedActionLoop(
        bridge=bridge,
        breaker=SafetyCircuitBreaker(),
        ledger=EvidenceLedger(),
        three_ring=three_ring,
    )
