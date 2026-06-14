"""
Proof-Carrying Action (PCA) Bridge

Inspired by the June 2026 runtime-governance frontier:
- Proof-Carrying Agent Actions (arXiv:2606.04104) -- portable action
  envelopes, runtime/approval receipts, replay-ready proofs, five-checkpoint
  workflow, externality-aware certificates, enforceability classes.
- SARC (arXiv:2605.07728) -- Pre-Action Gate / Action-Time Monitor /
  Post-Action Auditor / Escalation Router; constraints as first-class
  objects.
- OpenKedge (arXiv:2604.08601) -- Intent-to-Execution Evidence Chain
  (IEEC) with cryptographically linked proposal -> approval -> outcome.
- Proposal-Certification-Execution (arXiv:2605.24462) -- execution
  conditioned on certified traces (L_exec = L_G \\cap L_cert(M_Pi)).
- SentinelAgent DCC/IPDP (arXiv:2604.02767) -- authority scope, intent
  vector, policy constraints; P6 scope-action conformance and P7 output
  schema conformance.

The bridge connects three existing repo substrates:

    SafetyCircuitBreaker     -- per-action policy + approval gate
    EvidenceLedger           -- claim/evidence substrate for the gate
    VerifiableActionLoop     -- propose -> verify -> execute -> recover
    ThreeRingGovernor        -- Ring 2 federation / Ring 3 frontier

into a single **portable action certificate** with:

    1. Pre-Action Admissibility Checkpoint
    2. Action Open Checkpoint (intention frozen)
    3. Assumption Capture Checkpoint (evidence digest + context)
    4. Approval Checkpoint (with enforceability class)
    5. Outcome Closure Checkpoint (replay-ready proof)

and an **Intent-to-Execution Evidence Chain (IEEC)** that hash-links
the certificate to the post-execution outcome.

Core invariants:

    - Execution is *gated* on a valid ActionCertificate; bare
      VerifiableAction execution is still possible for backwards
      compatibility, but the loop exposes a `certify_and_execute`
      path that always produces a certificate.
    - The certificate is *immutable* after Outcome Closure.  The
      post-hoc `record_outcome` writes a new IEEC step, it does not
      mutate the certificate.
    - Approval is expressed as an **EnforceabilityClass** (PCAA), not
      a single boolean: REQUIRE_HUMAN, REQUIRE_BRIDGE, POLICY_ONLY,
      AUTO.  REQUIRE_HUMAN is a hard gate; POLICY_ONLY is the
      default; AUTO requires the action to be both Ring 2 bounded
      and pre-verified.
    - Externality context is **first-class**: an ActionCertificate
      carries (a) destination visibility, (b) provenance, (c) cost
      class, (d) data classification, (e) reversal bounds.  Removing
      externality context from the certificate is detected at
      `verify_certificate` time.
    - The IEEC is **append-only** and hash-chained (OpenKedge IEEC).
      Each step stores the SHA-256 of the previous step + the
      current step's canonical JSON, so tampering with one step
      invalidates every later step.

The module is LLM-agnostic, deterministic, and roughly ~1000 LOC.  It
does not call any LLM, send any network request, or take a position
on which model is the substrate.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterable, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CheckpointKind(str, Enum):
    """The five PCAA checkpoints; the PCA bridge uses all five.

    PRE_ADMISSIBILITY    -- action is structurally valid + policy allows it
    ACTION_OPEN         -- the action's intent is frozen and named
    ASSUMPTION_CAPTURE  -- externality context + evidence digest attached
    APPROVAL            -- EnforceabilityClass determined; bridge or human
    OUTCOME_CLOSURE     -- post-execution outcome recorded; proof closed
    """

    PRE_ADMISSIBILITY = "pre_admissibility"
    ACTION_OPEN = "action_open"
    ASSUMPTION_CAPTURE = "assumption_capture"
    APPROVAL = "approval"
    OUTCOME_CLOSURE = "outcome_closure"


class EnforceabilityClass(str, Enum):
    """How the approval was obtained (PCAA enforceability classes).

    REQUIRE_HUMAN  -- hard gate; explicit human approval required
    REQUIRE_BRIDGE -- gate routed through ThreeRingGovernor; the
                      bridge decision is the approval
    POLICY_ONLY    -- pre-defined policy approved it (SafetyCircuitBreaker
                      or ConstitutionalGovernance); no human in the loop
    AUTO           -- action is Ring 2 bounded AND pre-verified; no
                      approval needed at all
    """

    REQUIRE_HUMAN = "require_human"
    REQUIRE_BRIDGE = "require_bridge"
    POLICY_ONLY = "policy_only"
    AUTO = "auto"


class CertificateState(str, Enum):
    """Lifecycle of an ActionCertificate.

    The state machine is:

        DRAFT  -- created by ``propose``; not yet admissible
        ADMISSIBLE -- pre_admissibility + action_open + assumption_capture
                      all passed
        PENDING_APPROVAL -- awaiting explicit human approval
        APPROVED  -- approval recorded; ready to execute
        EXECUTING -- execution started (call once)
        CLOSED    -- outcome closure recorded; certificate is immutable
        REJECTED  -- failed pre-admissibility; certificate is closed
        ABANDONED -- manually abandoned before execution; certificate is
                     closed
    """

    DRAFT = "draft"
    ADMISSIBLE = "admissible"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    CLOSED = "closed"
    REJECTED = "rejected"
    ABANDONED = "abandoned"


class ReversalBound(str, Enum):
    """How reversible the action is (PCAA reversal bound).

    IRREVERSIBLE   -- once done, cannot be undone (delete production row,
                       send money, kill a process)
    REVERSIBLE     -- can be undone with bounded effort (write to file,
                       create a resource)
    TRANSIENT      -- leaves no persistent trace (read, query, observe)
    """

    IRREVERSIBLE = "irreversible"
    REVERSIBLE = "reversible"
    TRANSIENT = "transient"


class DataClassification(str, Enum):
    """How sensitive the action's data is.

    PUBLIC        -- no restrictions
    INTERNAL      -- not for external sharing
    CONFIDENTIAL  -- need-to-know; logged separately
    RESTRICTED    -- access-controlled; ring-3 frontier only with bridge
    """

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ExternalityContext:
    """Externality context attached at the Assumption Capture checkpoint.

    PCAA calls these "boundary facts".  We make them first-class so
    that ``verify_certificate`` can refuse any certificate that is
    missing the fields the operator has marked as required.
    """

    destination_visibility: str = "local"   # local | network | external
    provenance: str = "user"                # user | system | derived
    cost_class: str = "low"                 # low | medium | high | critical
    data_classification: DataClassification = DataClassification.INTERNAL
    reversal_bound: ReversalBound = ReversalBound.REVERSIBLE
    requires_audit: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "destination_visibility": self.destination_visibility,
            "provenance": self.provenance,
            "cost_class": self.cost_class,
            "data_classification": self.data_classification.value,
            "reversal_bound": self.reversal_bound.value,
            "requires_audit": self.requires_audit,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExternalityContext":
        return cls(
            destination_visibility=data.get("destination_visibility", "local"),
            provenance=data.get("provenance", "user"),
            cost_class=data.get("cost_class", "low"),
            data_classification=DataClassification(
                data.get("data_classification", "internal")
            ),
            reversal_bound=ReversalBound(data.get("reversal_bound", "reversible")),
            requires_audit=data.get("requires_audit", True),
        )


@dataclass
class Checkpoint:
    """A single PCAA checkpoint.  Immutable once created."""

    kind: CheckpointKind
    passed: bool
    notes: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind.value,
            "passed": self.passed,
            "notes": self.notes,
            "timestamp": self.timestamp,
            "detail": self.detail,
        }


@dataclass
class ApprovalReceipt:
    """The approval recorded at the APPROVAL checkpoint.

    The receipt is what the certificate carries into execution.  A
    REQUIRE_HUMAN receipt is the operator's documented decision;
    REQUIRE_BRIDGE is the routing decision; POLICY_ONLY is the policy
    ID + the breaker that approved it; AUTO is the pre-verification
    transcript.
    """

    enforceability: EnforceabilityClass
    approver: str                          # "human:operator_1" / "bridge:gov" / ...
    approver_kind: str                     # human | bridge | policy | auto
    policy_ids: List[str] = field(default_factory=list)
    claim_ids: List[str] = field(default_factory=list)  # evidence-ledger claims
    routing_decision_ref: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enforceability": self.enforceability.value,
            "approver": self.approver,
            "approver_kind": self.approver_kind,
            "policy_ids": list(self.policy_ids),
            "claim_ids": list(self.claim_ids),
            "routing_decision_ref": self.routing_decision_ref,
            "timestamp": self.timestamp,
            "rationale": self.rationale,
        }


@dataclass
class ActionCertificate:
    """A portable action certificate (PCAA).

    A certificate is the **system of record** for a single action: it
    carries the action's intent, the externality context, the
    evidence digest, the approval, and (after closure) the outcome.
    It is *immutable* after Outcome Closure.
    """

    certificate_id: str
    action_id: str
    action_type: str
    parameters: Dict[str, Any]
    agent_id: str
    ring_layer: str                        # ring_1_production | ring_2_federation | ring_3_frontier
    state: CertificateState = CertificateState.DRAFT
    checkpoints: List[Checkpoint] = field(default_factory=list)
    externality: ExternalityContext = field(default_factory=ExternalityContext)
    approval: Optional[ApprovalReceipt] = None
    evidence_digest: str = ""              # sha256 of (intent + externality + checkpoints)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    closed_at: Optional[str] = None
    outcome: Optional[Dict[str, Any]] = None
    policy_evidence: List[str] = field(default_factory=list)

    def add_checkpoint(self, kind: CheckpointKind, passed: bool,
                       notes: str = "", detail: Optional[Dict[str, Any]] = None) -> Checkpoint:
        """Append a checkpoint; refuses to mutate after CLOSED."""
        if self.state in (CertificateState.CLOSED,
                          CertificateState.REJECTED,
                          CertificateState.ABANDONED):
            raise RuntimeError(
                f"cannot add checkpoint to closed certificate {self.certificate_id} "
                f"(state={self.state.value})"
            )
        cp = Checkpoint(kind=kind, passed=passed, notes=notes,
                        detail=detail or {})
        self.checkpoints.append(cp)
        return cp

    def has_checkpoint(self, kind: CheckpointKind, passed: Optional[bool] = None) -> bool:
        for cp in self.checkpoints:
            if cp.kind == kind and (passed is None or cp.passed == passed):
                return True
        return False

    def is_immutable(self) -> bool:
        return self.state in (CertificateState.CLOSED,
                              CertificateState.REJECTED,
                              CertificateState.ABANDONED)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "certificate_id": self.certificate_id,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "parameters": self.parameters,
            "agent_id": self.agent_id,
            "ring_layer": self.ring_layer,
            "state": self.state.value,
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "externality": self.externality.to_dict(),
            "approval": self.approval.to_dict() if self.approval else None,
            "evidence_digest": self.evidence_digest,
            "created_at": self.created_at,
            "closed_at": self.closed_at,
            "outcome": self.outcome,
            "policy_evidence": list(self.policy_evidence),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionCertificate":
        cert = cls(
            certificate_id=data["certificate_id"],
            action_id=data["action_id"],
            action_type=data["action_type"],
            parameters=dict(data.get("parameters", {})),
            agent_id=data["agent_id"],
            ring_layer=data["ring_layer"],
            state=CertificateState(data.get("state", "draft")),
            externality=ExternalityContext.from_dict(data.get("externality", {})),
            evidence_digest=data.get("evidence_digest", ""),
            created_at=data.get("created_at", ""),
            closed_at=data.get("closed_at"),
            outcome=data.get("outcome"),
            policy_evidence=list(data.get("policy_evidence", [])),
        )
        for cp_data in data.get("checkpoints", []):
            cert.checkpoints.append(Checkpoint(
                kind=CheckpointKind(cp_data["kind"]),
                passed=bool(cp_data.get("passed", False)),
                notes=cp_data.get("notes", ""),
                timestamp=cp_data.get("timestamp", ""),
                detail=cp_data.get("detail", {}),
            ))
        if data.get("approval"):
            a = data["approval"]
            cert.approval = ApprovalReceipt(
                enforceability=EnforceabilityClass(a["enforceability"]),
                approver=a.get("approver", ""),
                approver_kind=a.get("approver_kind", ""),
                policy_ids=list(a.get("policy_ids", [])),
                claim_ids=list(a.get("claim_ids", [])),
                routing_decision_ref=a.get("routing_decision_ref"),
                timestamp=a.get("timestamp", ""),
                rationale=a.get("rationale", ""),
            )
        return cert


@dataclass
class IEECStep:
    """A single step of the Intent-to-Execution Evidence Chain.

    Each step hash-links the previous step's digest to the current
    step's canonical content.  ``prev_digest == ''`` only for the
    first step.
    """

    step_id: str
    certificate_id: str
    sequence: int
    event: str                              # e.g. "propose", "approve", "execute", "close"
    payload: Dict[str, Any]
    prev_digest: str
    digest: str = ""

    def compute_digest(self) -> str:
        """SHA-256 of (prev_digest + canonical payload + sequence + event + ts)."""
        body = {
            "certificate_id": self.certificate_id,
            "sequence": self.sequence,
            "event": self.event,
            "prev_digest": self.prev_digest,
            "payload": self.payload,
        }
        canonical = json.dumps(body, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    def finalize(self) -> None:
        self.digest = self.compute_digest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "certificate_id": self.certificate_id,
            "sequence": self.sequence,
            "event": self.event,
            "payload": self.payload,
            "prev_digest": self.prev_digest,
            "digest": self.digest,
        }


# ---------------------------------------------------------------------------
# Hash helpers
# ---------------------------------------------------------------------------


def canonical_hash(obj: Any) -> str:
    """Deterministic SHA-256 of any JSON-serialisable object."""
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode()
    ).hexdigest()


def digest_certificate(cert: ActionCertificate) -> str:
    """The evidence digest of a certificate's intent + externality.

    Excludes ``checkpoints`` (those change as the certificate flows
    through the loop), ``approval``, ``state``, and ``outcome`` --
    the digest is over the *thing the certificate authorises*, not
    the *way it was authorised* (which is on the IEEC).
    """
    body = {
        "action_id": cert.action_id,
        "action_type": cert.action_type,
        "parameters": cert.parameters,
        "agent_id": cert.agent_id,
        "ring_layer": cert.ring_layer,
        "externality": cert.externality.to_dict(),
    }
    return canonical_hash(body)


# ---------------------------------------------------------------------------
# Required-externality policy
# ---------------------------------------------------------------------------


class ExternalityPolicy:
    """Which externality fields are required by class.

    PCAA: missing externality context harms routing quality.  This
    policy lets the operator mark which fields the loop will refuse
    to be silent about.
    """

    DEFAULT_REQUIRED = (
        "destination_visibility",
        "provenance",
        "cost_class",
        "data_classification",
        "reversal_bound",
    )

    def __init__(self, required: Optional[Iterable[str]] = None) -> None:
        self.required: Set[str] = set(required or self.DEFAULT_REQUIRED)

    def missing_fields(self, ext: ExternalityContext) -> List[str]:
        present = {
            "destination_visibility": ext.destination_visibility,
            "provenance": ext.provenance,
            "cost_class": ext.cost_class,
            "data_classification": ext.data_classification.value,
            "reversal_bound": ext.reversal_bound.value,
        }
        return [f for f in self.required if not present.get(f) or not str(present.get(f)).strip()]


# ---------------------------------------------------------------------------
# Pre-admissibility policy
# ---------------------------------------------------------------------------


class AdmissibilityDecision(str, Enum):
    ADMISSIBLE = "admissible"
    REQUIRES_BRIDGE = "requires_bridge"
    REQUIRES_HUMAN = "requires_human"
    REJECTED = "rejected"


# Default action type -> reversal bound (SARC Pre-Action Gate default).
DEFAULT_REVERSAL_BOUND: Dict[str, ReversalBound] = {
    "read": ReversalBound.TRANSIENT,
    "search": ReversalBound.TRANSIENT,
    "query": ReversalBound.TRANSIENT,
    "write": ReversalBound.REVERSIBLE,
    "create": ReversalBound.REVERSIBLE,
    "update": ReversalBound.REVERSIBLE,
    "delete": ReversalBound.IRREVERSIBLE,
    "drop": ReversalBound.IRREVERSIBLE,
    "truncate": ReversalBound.IRREVERSIBLE,
    "execute": ReversalBound.REVERSIBLE,
    "send_money": ReversalBound.IRREVERSIBLE,
    "publish": ReversalBound.REVERSIBLE,
}


# Action types that always require human approval.
HUMAN_GATED_ACTION_TYPES: Set[str] = {
    "delete",
    "drop",
    "truncate",
    "send_money",
    "self_modify",
    "purge",
    "kill",
    "force_push",
}


# Action types whose cost class is at least MEDIUM by default.
COST_HEAVY_ACTION_TYPES: Set[str] = {
    "execute",
    "compute",
    "send_money",
    "publish",
    "broadcast",
}


@dataclass
class AdmissibilityVerdict:
    decision: AdmissibilityDecision
    rationale: str
    suggested_enforceability: EnforceabilityClass
    detail: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# PCA Bridge
# ---------------------------------------------------------------------------


class ProofCarryingActionBridge:
    """The PCAA-style bridge between the agent loop and the action executors.

    The bridge is a small, deterministic, on-disk-auditable state
    machine.  Each certificate produces at least four IEEC steps
    (propose, approve, execute, close); ABANDON / REJECTED paths
    produce fewer.

    The bridge does not *execute* actions.  It certifies them and
    hands them to the registered executor; the executor is responsible
    for the actual effect, and is expected to call ``record_outcome``
    once it is done.
    """

    def __init__(
        self,
        externality_policy: Optional[ExternalityPolicy] = None,
        require_human_for_ring3: bool = True,
    ) -> None:
        self.externality_policy = externality_policy or ExternalityPolicy()
        self.require_human_for_ring3 = require_human_for_ring3

        # Active certificates
        self.certificates: Dict[str, ActionCertificate] = {}

        # IEEC, one chain per certificate
        self.ieec: Dict[str, List[IEECStep]] = {}

        # Executors registered by action type
        self.executors: Dict[str, Callable[[ActionCertificate], Dict[str, Any]]] = {}

        # Approval queue (for REQUIRE_HUMAN certificates)
        self.pending_approvals: Dict[str, ActionCertificate] = {}

        # Cross-certificate links: cert -> list of certificate_ids that
        # depend on this one (for replay-ready proof of multi-step plans)
        self.dependents: Dict[str, List[str]] = {}

        # Optional on-disk audit path; if set, every IEEC step is
        # appended to ``<audit_path>/ieec.jsonl`` for replay.
        self.audit_path: Optional[Path] = None

    # -- executors ---------------------------------------------------------

    def register_executor(
        self, action_type: str,
        executor: Callable[[ActionCertificate], Dict[str, Any]],
    ) -> None:
        self.executors[action_type] = executor

    # -- propose -----------------------------------------------------------

    def propose(
        self,
        action_id: str,
        action_type: str,
        parameters: Dict[str, Any],
        agent_id: str,
        ring_layer: str,
        externality: Optional[ExternalityContext] = None,
    ) -> Tuple[ActionCertificate, AdmissibilityVerdict]:
        """Create a certificate and run the pre-admissibility checkpoint."""
        cert = ActionCertificate(
            certificate_id=f"cert_{uuid.uuid4().hex[:12]}",
            action_id=action_id,
            action_type=action_type,
            parameters=dict(parameters),
            agent_id=agent_id,
            ring_layer=ring_layer,
            externality=externality or ExternalityContext(),
        )

        # PCAA: externality context is first-class; missing fields are
        # a hard fail at the gate.
        missing = self.externality_policy.missing_fields(cert.externality)
        if missing:
            cert.add_checkpoint(
                CheckpointKind.PRE_ADMISSIBILITY,
                passed=False,
                notes=f"missing required externality fields: {missing}",
                detail={"missing_fields": missing},
            )
            cert.state = CertificateState.REJECTED
            self.certificates[cert.certificate_id] = cert
            self._append_ieec(cert, "reject", {
                "reason": "missing_externality",
                "missing_fields": missing,
            })
            return cert, AdmissibilityVerdict(
                decision=AdmissibilityDecision.REJECTED,
                rationale=f"missing externality fields: {missing}",
                suggested_enforceability=EnforceabilityClass.REQUIRE_HUMAN,
                detail={"missing_fields": missing},
            )

        verdict = self._admissibility_verdict(cert)

        if verdict.decision == AdmissibilityDecision.REJECTED:
            cert.state = CertificateState.REJECTED
            cert.add_checkpoint(
                CheckpointKind.PRE_ADMISSIBILITY,
                passed=False,
                notes=verdict.rationale,
                detail=verdict.detail,
            )
            self.certificates[cert.certificate_id] = cert
            self._append_ieec(cert, "reject", {
                "reason": "policy_violation",
                "rationale": verdict.rationale,
            })
            return cert, verdict

        # The three pre-execution checkpoints are recorded in order.
        cert.add_checkpoint(
            CheckpointKind.PRE_ADMISSIBILITY,
            passed=True,
            notes=verdict.rationale,
            detail=verdict.detail,
        )
        cert.add_checkpoint(
            CheckpointKind.ACTION_OPEN,
            passed=True,
            notes="action intent frozen at propose time",
            detail={"action_id": cert.action_id, "action_type": cert.action_type},
        )
        cert.add_checkpoint(
            CheckpointKind.ASSUMPTION_CAPTURE,
            passed=True,
            notes="externality captured",
            detail={"externality": cert.externality.to_dict()},
        )

        # Compute evidence digest over intent + externality
        cert.evidence_digest = digest_certificate(cert)

        # State machine: ADMISSIBLE, or PENDING_APPROVAL if it needs
        # a human in the loop.
        if verdict.decision == AdmissibilityDecision.REQUIRES_HUMAN:
            cert.state = CertificateState.PENDING_APPROVAL
            self.pending_approvals[cert.certificate_id] = cert
        else:
            cert.state = CertificateState.ADMISSIBLE

        self.certificates[cert.certificate_id] = cert
        self.ieec[cert.certificate_id] = []
        self._append_ieec(cert, "propose", {
            "evidence_digest": cert.evidence_digest,
            "verdict": verdict.decision.value,
            "enforceability": verdict.suggested_enforceability.value,
        })
        return cert, verdict

    # -- admissibility ----------------------------------------------------

    def _admissibility_verdict(self, cert: ActionCertificate) -> AdmissibilityVerdict:
        """Decide ADMISSIBLE / REQUIRES_BRIDGE / REQUIRES_HUMAN / REJECTED."""
        ext = cert.externality

        # IRREVERSIBLE + RESTRICTED is a hard human gate (SARC: zero
        # hard-constraint violations required).
        if (ext.reversal_bound == ReversalBound.IRREVERSIBLE
                and ext.data_classification in (DataClassification.CONFIDENTIAL,
                                                 DataClassification.RESTRICTED)):
            return AdmissibilityVerdict(
                decision=AdmissibilityDecision.REQUIRES_HUMAN,
                rationale="irreversible action on confidential/restricted data",
                suggested_enforceability=EnforceabilityClass.REQUIRE_HUMAN,
                detail={"reversal_bound": ext.reversal_bound.value,
                        "data_classification": ext.data_classification.value},
            )

        # Always-human-gated action types
        if cert.action_type in HUMAN_GATED_ACTION_TYPES:
            return AdmissibilityVerdict(
                decision=AdmissibilityDecision.REQUIRES_HUMAN,
                rationale=f"action type '{cert.action_type}' is always human-gated",
                suggested_enforceability=EnforceabilityClass.REQUIRE_HUMAN,
                detail={"action_type": cert.action_type},
            )

        # Ring 3 frontier with non-network destination is bridge-routed
        if cert.ring_layer == "ring_3_frontier":
            if self.require_human_for_ring3:
                return AdmissibilityVerdict(
                    decision=AdmissibilityDecision.REQUIRES_HUMAN,
                    rationale="ring 3 frontier requires human gate by default",
                    suggested_enforceability=EnforceabilityClass.REQUIRE_HUMAN,
                    detail={"ring_layer": cert.ring_layer},
                )
            return AdmissibilityVerdict(
                decision=AdmissibilityDecision.REQUIRES_BRIDGE,
                rationale="ring 3 frontier action routed through bridge",
                suggested_enforceability=EnforceabilityClass.REQUIRE_BRIDGE,
                detail={"ring_layer": cert.ring_layer},
            )

        # External destination visibility: bridge routing preferred
        if ext.destination_visibility == "external":
            return AdmissibilityVerdict(
                decision=AdmissibilityDecision.REQUIRES_BRIDGE,
                rationale="external destination routed through bridge",
                suggested_enforceability=EnforceabilityClass.REQUIRE_BRIDGE,
                detail={"destination_visibility": ext.destination_visibility},
            )

        # Cost class: critical => human
        if ext.cost_class == "critical":
            return AdmissibilityVerdict(
                decision=AdmissibilityDecision.REQUIRES_HUMAN,
                rationale="critical cost class requires human gate",
                suggested_enforceability=EnforceabilityClass.REQUIRE_HUMAN,
                detail={"cost_class": ext.cost_class},
            )

        # Default: AUTO if Ring 2 + bounded, else POLICY_ONLY
        if cert.ring_layer == "ring_2_federation":
            return AdmissibilityVerdict(
                decision=AdmissibilityDecision.ADMISSIBLE,
                rationale="ring 2 federation auto-approved",
                suggested_enforceability=EnforceabilityClass.AUTO,
            )

        return AdmissibilityVerdict(
            decision=AdmissibilityDecision.ADMISSIBLE,
            rationale="ring 1 informational / default policy",
            suggested_enforceability=EnforceabilityClass.POLICY_ONLY,
        )

    # -- approve / reject / abandon -----------------------------------------

    def approve(
        self,
        certificate_id: str,
        approver: str,
        policy_ids: Optional[List[str]] = None,
        claim_ids: Optional[List[str]] = None,
        routing_decision_ref: Optional[str] = None,
        enforceability: Optional[EnforceabilityClass] = None,
        rationale: str = "",
    ) -> ActionCertificate:
        """Approve a pending-approval certificate.

        Also auto-approves ADMISSIBLE certificates (enforceability
        defaults from the verdict if not provided).
        """
        if certificate_id not in self.certificates:
            raise KeyError(f"unknown certificate: {certificate_id}")
        cert = self.certificates[certificate_id]
        if cert.is_immutable():
            raise RuntimeError(
                f"cannot approve immutable certificate {certificate_id} "
                f"(state={cert.state.value})"
            )
        if cert.state not in (CertificateState.PENDING_APPROVAL,
                              CertificateState.ADMISSIBLE,
                              CertificateState.DRAFT):
            raise RuntimeError(
                f"certificate {certificate_id} is in state {cert.state.value}, "
                f"not pending approval"
            )

        if not cert.has_checkpoint(CheckpointKind.PRE_ADMISSIBILITY, passed=True):
            raise RuntimeError(
                f"cannot approve certificate {certificate_id} without "
                f"a passing pre-admissibility checkpoint"
            )

        # If no enforceability supplied, infer from ring + last verdict
        if enforceability is None:
            enforceability = (
                EnforceabilityClass.REQUIRE_HUMAN
                if cert.state == CertificateState.PENDING_APPROVAL
                else EnforceabilityClass.AUTO
            )

        receipt = ApprovalReceipt(
            enforceability=enforceability,
            approver=approver,
            approver_kind=("human" if enforceability
                           == EnforceabilityClass.REQUIRE_HUMAN else "policy"),
            policy_ids=list(policy_ids or []),
            claim_ids=list(claim_ids or []),
            routing_decision_ref=routing_decision_ref,
            rationale=rationale,
        )
        cert.approval = receipt
        cert.add_checkpoint(
            CheckpointKind.APPROVAL,
            passed=True,
            notes=f"approved by {approver} ({enforceability.value})",
            detail={"approver": approver, "enforceability": enforceability.value},
        )
        cert.state = CertificateState.APPROVED
        self.pending_approvals.pop(certificate_id, None)

        self._append_ieec(cert, "approve", receipt.to_dict())
        return cert

    def reject(
        self,
        certificate_id: str,
        operator: str,
        reason: str = "",
    ) -> ActionCertificate:
        if certificate_id not in self.certificates:
            raise KeyError(f"unknown certificate: {certificate_id}")
        cert = self.certificates[certificate_id]
        if cert.is_immutable():
            raise RuntimeError(
                f"cannot reject immutable certificate {certificate_id}"
            )
        cert.state = CertificateState.REJECTED
        cert.closed_at = datetime.now(timezone.utc).isoformat()
        self.pending_approvals.pop(certificate_id, None)
        self._append_ieec(cert, "reject", {
            "operator": operator,
            "reason": reason,
        })
        return cert

    def abandon(self, certificate_id: str, operator: str,
                reason: str = "") -> ActionCertificate:
        if certificate_id not in self.certificates:
            raise KeyError(f"unknown certificate: {certificate_id}")
        cert = self.certificates[certificate_id]
        if cert.is_immutable():
            raise RuntimeError(
                f"cannot abandon immutable certificate {certificate_id}"
            )
        cert.state = CertificateState.ABANDONED
        cert.closed_at = datetime.now(timezone.utc).isoformat()
        self.pending_approvals.pop(certificate_id, None)
        self._append_ieec(cert, "abandon", {
            "operator": operator,
            "reason": reason,
        })
        return cert

    # -- execute + outcome ------------------------------------------------

    def execute(self, certificate_id: str) -> ActionCertificate:
        """Run the registered executor for an approved certificate."""
        if certificate_id not in self.certificates:
            raise KeyError(f"unknown certificate: {certificate_id}")
        cert = self.certificates[certificate_id]
        if cert.is_immutable():
            raise RuntimeError(
                f"cannot execute immutable certificate {certificate_id}"
            )
        if cert.state != CertificateState.APPROVED:
            raise RuntimeError(
                f"cannot execute certificate {certificate_id} in state "
                f"{cert.state.value} (must be APPROVED)"
            )
        if cert.action_type not in self.executors:
            raise RuntimeError(
                f"no executor registered for action type '{cert.action_type}'"
            )

        cert.state = CertificateState.EXECUTING
        self._append_ieec(cert, "execute_start", {
            "executor": cert.action_type,
        })
        executor = self.executors[cert.action_type]
        try:
            result = executor(cert) or {}
        except Exception as e:
            result = {"status": "error", "error": str(e)}
        cert.outcome = result
        cert.state = CertificateState.CLOSED
        cert.closed_at = datetime.now(timezone.utc).isoformat()
        self._append_ieec(cert, "close", {"outcome": result})
        return cert

    def record_outcome(
        self,
        certificate_id: str,
        outcome: Dict[str, Any],
    ) -> ActionCertificate:
        """Record the post-execution outcome for an in-flight certificate.

        The executor calls this after doing the work.  The certificate
        is closed and a new IEEC step is appended; the original
        certificate is *not* mutated in any other way.
        """
        if certificate_id not in self.certificates:
            raise KeyError(f"unknown certificate: {certificate_id}")
        cert = self.certificates[certificate_id]
        if cert.state != CertificateState.EXECUTING:
            raise RuntimeError(
                f"cannot record outcome for certificate {certificate_id} "
                f"in state {cert.state.value} (must be EXECUTING)"
            )
        cert.outcome = dict(outcome)
        cert.state = CertificateState.CLOSED
        cert.closed_at = datetime.now(timezone.utc).isoformat()
        self._append_ieec(cert, "close", {"outcome": cert.outcome})
        return cert

    # -- verify / replay ---------------------------------------------------

    def verify_certificate(self, cert: ActionCertificate) -> Tuple[bool, List[str]]:
        """Verify a certificate is internally consistent.

        Returns (ok, errors).  Re-checks:

            - the evidence digest matches the recomputed digest
            - all five checkpoints are present in the right order
            - if CLOSED, the OUTCOME_CLOSURE step was the last step
            - if APPROVAL was reached, the approval was for an
              appropriate enforceability class
            - externality context is complete per the policy
        """
        errors: List[str] = []

        # evidence digest
        if cert.evidence_digest and cert.evidence_digest != digest_certificate(cert):
            errors.append("evidence_digest_mismatch")

        # checkpoint ordering
        seen: List[CheckpointKind] = [cp.kind for cp in cert.checkpoints]
        expected_pre = [
            CheckpointKind.PRE_ADMISSIBILITY,
            CheckpointKind.ACTION_OPEN,
            CheckpointKind.ASSUMPTION_CAPTURE,
        ]
        for i, kind in enumerate(expected_pre):
            if i >= len(seen) or seen[i] != kind:
                errors.append(f"checkpoint_order_missing_{kind.value}")
                break
            if not cert.checkpoints[i].passed:
                errors.append(f"checkpoint_{kind.value}_failed")

        # if state is APPROVED/EXECUTING/CLOSED, must have APPROVAL
        if cert.state in (CertificateState.APPROVED,
                          CertificateState.EXECUTING,
                          CertificateState.CLOSED):
            if not cert.has_checkpoint(CheckpointKind.APPROVAL, passed=True):
                errors.append("approval_checkpoint_missing")

        # closed certificates need outcome closure
        if cert.is_immutable() and cert.state == CertificateState.CLOSED:
            # either the last IEEC step is "close" or the certificate
            # has an outcome recorded
            ieec_steps = self.ieec.get(cert.certificate_id, [])
            if not any(step.event == "close" for step in ieec_steps):
                if cert.outcome is None:
                    errors.append("closed_certificate_missing_outcome")

        # externality completeness
        missing = self.externality_policy.missing_fields(cert.externality)
        if missing and cert.state != CertificateState.REJECTED:
            errors.append(f"externality_incomplete:{','.join(missing)}")

        return (len(errors) == 0, errors)

    def verify_ieec(self, certificate_id: str) -> Tuple[bool, List[str]]:
        """Verify the hash chain of the IEEC is unbroken."""
        steps = self.ieec.get(certificate_id, [])
        errors: List[str] = []
        prev = ""
        for i, step in enumerate(steps):
            if step.prev_digest != prev:
                errors.append(
                    f"step_{i}_prev_digest_mismatch: expected {prev[:8]}..., "
                    f"got {step.prev_digest[:8]}..."
                )
            if step.sequence != i:
                errors.append(f"step_{i}_sequence_mismatch")
            recomputed = step.compute_digest()
            if step.digest and step.digest != recomputed:
                errors.append(f"step_{i}_digest_mismatch")
            prev = step.digest or recomputed
        return (len(errors) == 0, errors)

    def replay(self, certificate_id: str) -> List[Dict[str, Any]]:
        """Return the certificate's IEEC steps in order (for replay)."""
        return [step.to_dict() for step in self.ieec.get(certificate_id, [])]

    # -- persistence -------------------------------------------------------

    def enable_audit(self, audit_path: Path) -> None:
        self.audit_path = Path(audit_path)
        self.audit_path.mkdir(parents=True, exist_ok=True)

    def _append_ieec(self, cert: ActionCertificate, event: str,
                     payload: Dict[str, Any]) -> IEECStep:
        if cert.certificate_id not in self.ieec:
            self.ieec[cert.certificate_id] = []
        chain = self.ieec[cert.certificate_id]
        prev_digest = chain[-1].digest if chain else ""
        step = IEECStep(
            step_id=f"step_{uuid.uuid4().hex[:10]}",
            certificate_id=cert.certificate_id,
            sequence=len(chain),
            event=event,
            payload=dict(payload),
            prev_digest=prev_digest,
        )
        step.finalize()
        chain.append(step)

        if self.audit_path is not None:
            audit_file = self.audit_path / "ieec.jsonl"
            with audit_file.open("a") as f:
                f.write(json.dumps(step.to_dict(), default=str) + "\n")
        return step

    # -- summary / inspection ----------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """A descriptive view of the bridge state."""
        state_counts: Dict[str, int] = {}
        for c in self.certificates.values():
            state_counts[c.state.value] = state_counts.get(c.state.value, 0) + 1
        ring_counts: Dict[str, int] = {}
        for c in self.certificates.values():
            ring_counts[c.ring_layer] = ring_counts.get(c.ring_layer, 0) + 1
        enforceability_counts: Dict[str, int] = {}
        for c in self.certificates.values():
            if c.approval:
                k = c.approval.enforceability.value
                enforceability_counts[k] = enforceability_counts.get(k, 0) + 1
        return {
            "total_certificates": len(self.certificates),
            "pending_approvals": len(self.pending_approvals),
            "by_state": state_counts,
            "by_ring": ring_counts,
            "by_enforceability": enforceability_counts,
            "ieec_steps_total": sum(len(v) for v in self.ieec.values()),
            "audit_path": str(self.audit_path) if self.audit_path else None,
        }


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------


def create_pca_bridge(
    audit_path: Optional[Path] = None,
    externality_policy: Optional[ExternalityPolicy] = None,
    require_human_for_ring3: bool = True,
) -> ProofCarryingActionBridge:
    """Smallest viable install: 1 line."""
    bridge = ProofCarryingActionBridge(
        externality_policy=externality_policy,
        require_human_for_ring3=require_human_for_ring3,
    )
    if audit_path is not None:
        bridge.enable_audit(audit_path)
    return bridge
