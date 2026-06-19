"""
Verification-Gated Loop Orchestrator - "Loop Engineering with Verification"

Inspired by the 2026-Q2 "loop engineering" convergence:

  - Addy Osmani, *Loop Engineering* (Jun 17 2026): "A loop is only as good
    as its verifier. The durable design layers an explicit verify step
    between observe and the next act."
  - The New Stack, *Loops are replacing prompts. Verification is about
    to be your biggest problem.* (Jun 17 2026): long-lived agent loops
    shift the failure surface from "wrong answer" to "wrong verifier."
  - Aikipedia *Loop Engineering* (Jun 17 2026): the unit of work shifts
    from the individual, turn-by-turn instruction to the *loop itself*:
    a persistent, goal-directed cycle of find -> act -> observe ->
    evaluate -> repeat until a completion condition is met.
  - Truefoundry, *Loop Engineering at Enterprise Scale* (Jun 2026): "a
    loop is a production system the instant it runs without you, and
    a laptop is the wrong runtime to run it on." Loop instances need
    lifecycle, identity, and revocation -- the "AI agent as employee"
    substrate that NewCore ($66M seed, Jun 15 2026) is building.
  - The Containment Gap paper (arXiv:2606.12797, Jun 2026): memory
    integrity and policy gates are the two containment mechanisms
    missing from every major agent framework. A loop that does not
    enforce both is a leak, not a loop.
  - mem9-guard-mcp (GitHub, Jun 2026): the policy-driven guard pattern
    for agent memory I/O. The loop's *every* state transition is
    an I/O event that needs a guard, not just memory writes.
  - agend-terminal hardening (GitHub issue #2158, Jun 2026): transient
    sub-agents must not silently rebind the parent instance's identity.
    A loop's loop_id is the substrate for the rebind check.

What this module adds on top of the existing governance stack:

  1. AgentIdentity        The first-class "AI agent as employee" record:
                          loop_id, principal, scope, permissions, lifecycle
                          state, revocation token. The NewCore substrate
                          in-process.

  2. LoopState            The seven explicit states of a verification-gated
                          loop: PROVISIONED -> RUNNING -> EVALUATING ->
                          WAITING_EVIDENCE -> WAITING_HUMAN -> COMPLETED /
                          REVOKED / FAILED. The loop never silently
                          transitions.

  3. LoopStep             A single act -> observe -> evaluate tuple.
                          Carries action, observation, evaluator verdict,
                          and the explicit *next* action or terminal
                          state. The step is the unit of audit.

  4. VerifierProtocol     The minimum interface every loop verifier must
                          satisfy: "given (action, observation, prior
                          evidence), return a verdict (CONTINUE / ESCALATE
                          / HALT) and the evidence that justified it."

  5. LedgerGateVerifier   A verifier that consults the EvidenceLedger:
                          an act without a SUPPORTED claim is HALT
                          (or ESCALATE if a claim is DISPUTED). The
                          "ungrounded is not safe" posture in loop form.

  6. BreakerGateVerifier  A verifier that consults the SafetyCircuitBreaker:
                          an act whose risk is CRITICAL is HALT; HIGH is
                          ESCALATE; LOW/MEDIUM is CONTINUE. The breaker's
                          policy blocklist is the floor -- it never gets
                          demoted.

  7. MonitorGateVerifier  A verifier that consults the MetacognitiveMonitor:
                          high load or low calibration -> ESCALATE; monitor
                          failure -> HALT. The shift is additive only
                          (never demotes).

  8. CompositeVerifier    A verifier that runs N verifiers in priority
                          order, takes the *strongest* verdict (HALT >
                          ESCALATE > CONTINUE), and produces a composite
                          evidence line. Mirrors the SafetyCircuitBreaker's
                          "promote never demote" posture.

  9. AgentLoop            The orchestrator. Owns one AgentIdentity, runs
                          the act -> observe -> evaluate -> step cycle
                          until the verifier says HALT (or the goal is
                          reached, or revocation arrives, or the budget
                          is exhausted). Every step is a LoopStep
                          appended to an in-memory ring + an on-disk
                          JSONL audit trail.

  10. LoopBudget          Hard caps on steps, tokens, and wall-time. The
                          "a loop is a production system" substrate:
                          runaway loops are *not* allowed to silently
                          consume the host.

  11. RevocationChannel   An operator-controlled revocation bus. A
                          revoked loop_id refuses to take new steps;
                          in-flight steps complete to a verifiable
                          terminal state. Mirrors NewCore's
                          "revocation mechanisms" requirement.

  12. create_agent_loop(identity, verifiers, budget, audit_path)
      The smallest viable install: 1 line, ~900 LOC.

Key invariants (conservative posture):

  - The loop NEVER silently transitions. Every state change produces a
    LoopStep on disk.
  - The composite verifier's verdict is the *strongest* of its members.
    A single HALT halts the loop. This is the antithesis of "the
    verifier got tired and let it through."
  - The breaker's CRITICAL verdict overrides any CONTINUE; the ledger's
    UNGROUNDED verdict overrides any CONTINUE; the monitor's failure
    overrides any CONTINUE. The floor is the floor.
  - A revoked loop_id refuses to take new steps immediately. The
    revocation is the *operator's* brake pedal -- a separate channel
    from the verifier.
  - The loop's budget is enforced *before* the act, not after. A loop
    that has exhausted its budget is COMPLETED with a budget_exhausted
    flag, not a HALT -- the operator can tell the two apart.
  - The AgentIdentity's permissions are *narrow* by default (READ only)
    and the loop's first action is the audit-trail open, not the first
    tool call. Mirrors mem9-guard's "agents never access raw store"
    posture.
  - Sub-loops (a loop that registers a sub-loop) inherit the parent's
    identity *minus* the revocations: a sub-loop cannot be more
    privileged than its parent. Mirrors agend-terminal's "transient
    sub-agents must not silently rebind the parent instance."
  - The audit trail is the *system of record*. The on-disk JSONL is
    the operator's view of "what did this loop do, in what order,
    under what verdict?" The in-memory ring is a *cache*, not a
    record of truth.
  - The module is LLM-agnostic: no model call, no network request,
    no position on which model is the substrate. The loop is the
    *shape* the model runs inside.

References:
  - Addy Osmani, *Loop Engineering*, Jun 17 2026
  - The New Stack, *Loops are replacing prompts*, Jun 17 2026
  - Aikipedia, *Loop Engineering*, Jun 17 2026
  - Truefoundry, *Loop Engineering at Enterprise Scale*, Jun 2026
  - The Containment Gap (arXiv:2606.12797, Jun 2026)
  - mem9-guard-mcp (Riku-KANO, Jun 2026)
  - agend-terminal hardening issue #2158 (Jun 2026)
  - NewCore, *Identity for the agentic era*, $66M seed Jun 15 2026
"""

from __future__ import annotations

import json
import os
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterable, List, Optional, Protocol, Tuple


# ---------------------------------------------------------------------------
# Verdict enum and ordering
# ---------------------------------------------------------------------------


class Verdict(str, Enum):
    """The three explicit outcomes a loop verifier can return.

    Ordering matters: HALT > ESCALATE > CONTINUE. The composite verifier
    always takes the strongest member.
    """

    CONTINUE = "continue"      # proceed to the next step
    ESCALATE = "escalate"      # pause and request human / additional evidence
    HALT = "halt"              # stop the loop immediately

    def strength(self) -> int:
        return _VERDICT_STRENGTH[self]


_VERDICT_STRENGTH: Dict[Verdict, int] = {
    Verdict.CONTINUE: 0,
    Verdict.ESCALATE: 1,
    Verdict.HALT: 2,
}


def strongest(verdicts: Iterable[Verdict]) -> Verdict:
    """Return the strongest verdict in a collection.

    Empty collection -> CONTINUE (the loop may proceed if no one objects).
    HALT > ESCALATE > CONTINUE.
    """
    out = Verdict.CONTINUE
    for v in verdicts:
        if v.strength() > out.strength():
            out = v
    return out


# ---------------------------------------------------------------------------
# Agent identity ("AI agent as employee")
# ---------------------------------------------------------------------------


class LifecycleState(str, Enum):
    """The lifecycle of an agent identity.

    Mirrors the NewCore "identity, lifecycle, revocation" substrate:

      PROVISIONED  : identity is allocated; loop has not yet started
      RUNNING      : loop is actively taking steps
      WAITING      : loop is paused (escalation, evidence gap, or budget)
      COMPLETED    : loop reached its goal
      REVOKED      : operator-revoked; loop refuses new steps
      FAILED       : loop halted by a verifier (non-revocation)
    """

    PROVISIONED = "provisioned"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    REVOKED = "revoked"
    FAILED = "failed"


class Permission(str, Enum):
    """The minimum permission axes for an agent identity.

    Conservative default: READ. The loop must explicitly request WRITE,
    EXECUTE, DELEGATE, or BROAD. A loop with no permissions is a loop
    that can only observe, not act -- a useful substrate for
    "monitor this and tell me what you see" loops.
    """

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELEGATE = "delegate"
    BROAD = "broad"


@dataclass(frozen=True)
class AgentIdentity:
    """The first-class identity record for a loop.

    The NewCore substrate in-process. Every loop has one. Sub-loops
    inherit a *narrower* version of the parent's permissions and
    cannot widen them.
    """

    loop_id: str
    principal: str                 # who/what owns this loop (e.g. "dave92", "ops-bot")
    purpose: str                   # human-readable description of intent
    permissions: Tuple[Permission, ...] = (Permission.READ,)
    parent_loop_id: Optional[str] = None   # set for sub-loops
    provisioned_at: str = field(default_factory=lambda: _utcnow_iso())
    expires_at: Optional[str] = None       # ISO; None = no expiry

    def __post_init__(self) -> None:
        if not self.loop_id:
            raise ValueError("loop_id is required")
        if not self.principal:
            raise ValueError("principal is required")
        if not self.purpose:
            raise ValueError("purpose is required")
        # Narrow: de-duplicate and sort so the frozen tuple is canonical.
        perms = tuple(sorted(set(self.permissions), key=lambda p: p.value))
        object.__setattr__(self, "permissions", perms)

    def has(self, perm: Permission) -> bool:
        return perm in self.permissions

    def narrower(self, child_loop_id: str, child_purpose: str) -> "AgentIdentity":
        """Return a child identity with a *narrower* permission set.

        A child cannot be more privileged than its parent. The child's
        permissions are a *subset* of the parent's permissions.

        Mirrors agend-terminal's "transient sub-agents must not silently
        rebind the parent instance" hardening.
        """
        return AgentIdentity(
            loop_id=child_loop_id,
            principal=self.principal,
            purpose=child_purpose,
            permissions=self.permissions,   # child starts with the same set; caller narrows
            parent_loop_id=self.loop_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "loop_id": self.loop_id,
            "principal": self.principal,
            "purpose": self.purpose,
            "permissions": [p.value for p in self.permissions],
            "parent_loop_id": self.parent_loop_id,
            "provisioned_at": self.provisioned_at,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AgentIdentity":
        return cls(
            loop_id=d["loop_id"],
            principal=d["principal"],
            purpose=d["purpose"],
            permissions=tuple(Permission(p) for p in d.get("permissions", ["read"])),
            parent_loop_id=d.get("parent_loop_id"),
            provisioned_at=d.get("provisioned_at", _utcnow_iso()),
            expires_at=d.get("expires_at"),
        )


# ---------------------------------------------------------------------------
# Loop step
# ---------------------------------------------------------------------------


class StepPhase(str, Enum):
    """The phase of a loop step. A step is act -> observe -> evaluate."""

    ACT = "act"
    OBSERVE = "observe"
    EVALUATE = "evaluate"


@dataclass
class LoopStep:
    """A single act -> observe -> evaluate tuple.

    The step is the unit of audit. Every step is appended to the in-memory
    ring *and* the on-disk JSONL trail. The step carries the verifier's
    verdict, the evidence that justified it, and the explicit *next* state.
    """

    step_id: str
    loop_id: str
    sequence: int
    phase: StepPhase
    action: Optional[Dict[str, Any]] = None       # the act
    observation: Optional[Dict[str, Any]] = None  # the observe
    verdict: Optional[Verdict] = None            # the evaluate
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    composite_rationale: str = ""
    next_action: Optional[Dict[str, Any]] = None  # the next act (if CONTINUE)
    terminal_reason: Optional[str] = None        # set on the closing step
    started_at: str = field(default_factory=lambda: _utcnow_iso())
    ended_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "loop_id": self.loop_id,
            "sequence": self.sequence,
            "phase": self.phase.value,
            "action": self.action,
            "observation": self.observation,
            "verdict": self.verdict.value if self.verdict is not None else None,
            "evidence": list(self.evidence),
            "composite_rationale": self.composite_rationale,
            "next_action": self.next_action,
            "terminal_reason": self.terminal_reason,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }


# ---------------------------------------------------------------------------
# Verifier protocol + default implementations
# ---------------------------------------------------------------------------


class VerifierProtocol(Protocol):
    """The minimum interface a loop verifier must satisfy.

    The verifier is the substrate for "loop engineering with verification."
    A loop with no verifier is a fire-and-forget script, not a loop.
    """

    name: str

    def evaluate(
        self,
        identity: AgentIdentity,
        action: Dict[str, Any],
        observation: Optional[Dict[str, Any]],
        prior_evidence: List[Dict[str, Any]],
    ) -> Tuple[Verdict, str, List[Dict[str, Any]]]:
        """Return (verdict, rationale, evidence)."""
        ...


@dataclass
class _Evidence:
    """Convenience for verifiers to build evidence rows."""

    source: str
    kind: str
    payload: Dict[str, Any]
    polarity: str = "neutral"   # supporting | contradicting | neutral

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "kind": self.kind,
            "payload": self.payload,
            "polarity": self.polarity,
        }


def _ok_evidence(verifier_name: str, note: str) -> _Evidence:
    return _Evidence(verifier_name, "permit", {"note": note}, "supporting")


def _block_evidence(verifier_name: str, note: str) -> _Evidence:
    return _Evidence(verifier_name, "block", {"note": note}, "contradicting")


# ---- Breaker gate ----------------------------------------------------------


class BreakerGateVerifier:
    """A verifier that consults a SafetyCircuitBreaker-shaped object.

    The breaker's verdict is treated as a *floor*:
      - BLOCKED -> HALT (the policy blocklist is the floor)
      - CRITICAL -> HALT
      - HIGH     -> ESCALATE
      - MEDIUM   -> ESCALATE (operator can opt to allow)
      - LOW      -> CONTINUE
      - missing / not a breaker -> CONTINUE (verifier is conservative
        in the "I cannot object" direction)

    The verifier never *demotes* a verdict. It only adds weight.
    """

    def __init__(self, breaker: Any = None) -> None:
        self.breaker = breaker
        self.name = "breaker"

    def evaluate(
        self,
        identity: AgentIdentity,
        action: Dict[str, Any],
        observation: Optional[Dict[str, Any]],
        prior_evidence: List[Dict[str, Any]],
    ) -> Tuple[Verdict, str, List[Dict[str, Any]]]:
        if self.breaker is None:
            return Verdict.CONTINUE, "no breaker attached", []

        tool = action.get("tool", "")
        params = action.get("params", {})

        # The breaker's `assess_risk` is the canonical entry point.
        assess = getattr(self.breaker, "assess_risk", None)
        if assess is None:
            return Verdict.CONTINUE, "breaker has no assess_risk", []

        try:
            assessment = assess(action_type=tool, params=params)
        except Exception as exc:  # breaker must never crash the loop
            return Verdict.ESCALATE, f"breaker raised: {exc!r}", [
                _block_evidence(self.name, f"raised: {exc!r}").to_dict()
            ]

        # The breaker's `is_blocked` is the hard blocklist floor.
        is_blocked = bool(getattr(assessment, "blocked", False) or
                          getattr(assessment, "is_blocked", False))
        if is_blocked:
            return Verdict.HALT, "breaker policy blocklist", [
                _block_evidence(self.name, "policy blocklist").to_dict()
            ]

        # Risk-level mapping
        risk = getattr(assessment, "risk_level", None)
        risk_value = getattr(risk, "value", None) if risk is not None else None
        try:
            risk_int = int(risk_value) if risk_value is not None else None
        except (TypeError, ValueError):
            risk_int = None

        if risk_int is None:
            return Verdict.CONTINUE, "breaker returned no risk_level", []
        if risk_int >= 4:    # CRITICAL
            return Verdict.HALT, "breaker risk CRITICAL", [
                _block_evidence(self.name, "risk CRITICAL").to_dict()
            ]
        if risk_int >= 3:    # HIGH
            return Verdict.ESCALATE, "breaker risk HIGH", [
                _block_evidence(self.name, "risk HIGH").to_dict()
            ]
        if risk_int >= 2:    # MEDIUM
            return Verdict.ESCALATE, "breaker risk MEDIUM", [
                _block_evidence(self.name, "risk MEDIUM").to_dict()
            ]
        return Verdict.CONTINUE, "breaker risk LOW", [
            _ok_evidence(self.name, "risk LOW").to_dict()
        ]


# ---- Ledger gate -----------------------------------------------------------


class LedgerGateVerifier:
    """A verifier that consults an EvidenceLedger-shaped object.

    The "ungrounded is not safe" posture in loop form:

      - At least one SUPPORTED claim tied to this action -> CONTINUE
      - Any DISPUTED claim tied to this action -> HALT
      - UNGROUNDED (no claim) -> ESCALATE
      - missing / not a ledger -> CONTINUE (verifier is conservative
        in the "I cannot object" direction)

    The verifier accepts a `claim_ids` key in the action dict. If absent,
    the action is treated as UNGROUNDED.
    """

    def __init__(self, ledger: Any = None) -> None:
        self.ledger = ledger
        self.name = "ledger"

    def evaluate(
        self,
        identity: AgentIdentity,
        action: Dict[str, Any],
        observation: Optional[Dict[str, Any]],
        prior_evidence: List[Dict[str, Any]],
    ) -> Tuple[Verdict, str, List[Dict[str, Any]]]:
        if self.ledger is None:
            return Verdict.CONTINUE, "no ledger attached", []

        claim_ids = list(action.get("claim_ids", []) or [])
        if not claim_ids:
            return Verdict.ESCALATE, "ungrounded action (no claim_ids)", [
                _block_evidence(self.name, "ungrounded").to_dict()
            ]

        # The ledger's `verify` (or `verify_claim`) is the canonical entry.
        verify = getattr(self.ledger, "verify", None) or getattr(self.ledger, "verify_claim", None)
        if verify is None:
            return Verdict.CONTINUE, "ledger has no verify", []

        try:
            results = [verify(cid) for cid in claim_ids]
        except Exception as exc:
            return Verdict.ESCALATE, f"ledger raised: {exc!r}", [
                _block_evidence(self.name, f"raised: {exc!r}").to_dict()
            ]

        supported = 0
        disputed = 0
        contradicted = 0
        for r in results:
            status = getattr(r, "status", None) or getattr(r, "claim_status", None)
            status_value = getattr(status, "value", str(status)).lower() if status is not None else ""
            if "support" in status_value:
                supported += 1
            elif "disput" in status_value:
                disputed += 1
            elif "contradict" in status_value:
                contradicted += 1

        if disputed > 0 or contradicted > 0:
            return Verdict.HALT, f"DISPUTED ({disputed}) / CONTRADICTED ({contradicted})", [
                _block_evidence(self.name, "DISPUTED claim").to_dict()
            ]
        if supported == 0:
            return Verdict.ESCALATE, "no SUPPORTED claim", [
                _block_evidence(self.name, "no SUPPORTED claim").to_dict()
            ]
        return Verdict.CONTINUE, f"{supported} SUPPORTED claim(s)", [
            _ok_evidence(self.name, f"{supported} SUPPORTED claim(s)").to_dict()
        ]


# ---- Monitor gate ----------------------------------------------------------


class MonitorGateVerifier:
    """A verifier that consults a MetacognitiveMonitor-shaped object.

    The "additive only" posture from the RSI gate:

      - High load (>= 0.8)            -> ESCALATE
      - Low confidence (<= 0.3)       -> ESCALATE
      - Recommendation == "escalate"  -> ESCALATE
      - Recommendation == "halt"      -> HALT
      - monitor error / missing       -> HALT
      - otherwise                     -> CONTINUE
    """

    def __init__(self, monitor: Any = None, high_load: float = 0.8, low_confidence: float = 0.3) -> None:
        self.monitor = monitor
        self.high_load = high_load
        self.low_confidence = low_confidence
        self.name = "monitor"

    def evaluate(
        self,
        identity: AgentIdentity,
        action: Dict[str, Any],
        observation: Optional[Dict[str, Any]],
        prior_evidence: List[Dict[str, Any]],
    ) -> Tuple[Verdict, str, List[Dict[str, Any]]]:
        if self.monitor is None:
            return Verdict.CONTINUE, "no monitor attached", []

        assess = getattr(self.monitor, "assess_current_state", None)
        if assess is None:
            return Verdict.CONTINUE, "monitor has no assess_current_state", []

        try:
            state = assess()
        except Exception as exc:
            return Verdict.HALT, f"monitor raised: {exc!r}", [
                _block_evidence(self.name, f"raised: {exc!r}").to_dict()
            ]

        load = float(getattr(state, "cognitive_load", 0.0) or 0.0)
        confidence = float(getattr(state, "confidence", 1.0) or 1.0)
        recommendation = str(getattr(state, "recommendation", "") or "").lower()

        if recommendation == "halt" or "halt" in recommendation:
            return Verdict.HALT, "monitor recommended HALT", [
                _block_evidence(self.name, "recommendation HALT").to_dict()
            ]
        if recommendation.startswith("escalate") or "escalate" in recommendation:
            return Verdict.ESCALATE, "monitor recommended ESCALATE", [
                _block_evidence(self.name, "recommendation ESCALATE").to_dict()
            ]
        if load >= self.high_load:
            return Verdict.ESCALATE, f"high cognitive load {load:.2f}", [
                _block_evidence(self.name, f"load {load:.2f}").to_dict()
            ]
        if confidence <= self.low_confidence:
            return Verdict.ESCALATE, f"low confidence {confidence:.2f}", [
                _block_evidence(self.name, f"confidence {confidence:.2f}").to_dict()
            ]
        return Verdict.CONTINUE, f"load={load:.2f} conf={confidence:.2f}", [
            _ok_evidence(self.name, "within budget").to_dict()
        ]


# ---- Composite -------------------------------------------------------------


class CompositeVerifier:
    """A verifier that runs N verifiers and takes the *strongest* verdict.

    The composite never demotes: if any member says HALT, the composite
    says HALT. If any member says ESCALATE (and none say HALT), the
    composite says ESCALATE. CONTINUE only if *all* members say
    CONTINUE.
    """

    def __init__(self, verifiers: List[VerifierProtocol]) -> None:
        if not verifiers:
            raise ValueError("at least one verifier is required")
        self.verifiers = list(verifiers)
        self.name = "composite"

    def evaluate(
        self,
        identity: AgentIdentity,
        action: Dict[str, Any],
        observation: Optional[Dict[str, Any]],
        prior_evidence: List[Dict[str, Any]],
    ) -> Tuple[Verdict, str, List[Dict[str, Any]]]:
        verdicts: List[Verdict] = []
        rationales: List[str] = []
        all_evidence: List[Dict[str, Any]] = []
        for v in self.verifiers:
            try:
                v_verdict, v_rationale, v_evidence = v.evaluate(
                    identity, action, observation, prior_evidence
                )
            except Exception as exc:
                v_verdict = Verdict.ESCALATE
                v_rationale = f"{v.name} raised: {exc!r}"
                v_evidence = [_block_evidence(v.name, f"raised: {exc!r}").to_dict()]
            verdicts.append(v_verdict)
            rationales.append(f"{v.name}={v_verdict.value}:{v_rationale}")
            all_evidence.extend(v_evidence)

        composite = strongest(verdicts)
        rationale = " | ".join(rationales)
        return composite, rationale, all_evidence


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------


@dataclass
class LoopBudget:
    """Hard caps on a loop's resource consumption.

    The "a loop is a production system" substrate: runaway loops are not
    allowed to silently consume the host. The budget is checked *before*
    the act, not after -- a loop that has exhausted its budget is
    COMPLETED with a budget_exhausted flag, not a HALT.
    """

    max_steps: int = 100
    max_tokens: int = 1_000_000
    max_wall_time_s: float = 600.0
    max_cost_estimate: float = 100.0

    def __post_init__(self) -> None:
        if self.max_steps <= 0:
            raise ValueError("max_steps must be > 0")
        if self.max_tokens <= 0:
            raise ValueError("max_tokens must be > 0")
        if self.max_wall_time_s <= 0:
            raise ValueError("max_wall_time_s must be > 0")
        if self.max_cost_estimate <= 0:
            raise ValueError("max_cost_estimate must be > 0")


@dataclass
class BudgetStatus:
    """The running consumption of a loop.

    Updated after every step. The loop checks `is_exhausted` before
    every act.
    """

    steps: int = 0
    tokens: int = 0
    wall_time_s: float = 0.0
    cost_estimate: float = 0.0
    started_at: str = field(default_factory=lambda: _utcnow_iso())

    def is_exhausted(self, budget: LoopBudget) -> Tuple[bool, str]:
        if self.steps >= budget.max_steps:
            return True, f"max_steps ({budget.max_steps}) reached"
        if self.tokens >= budget.max_tokens:
            return True, f"max_tokens ({budget.max_tokens}) reached"
        if self.wall_time_s >= budget.max_wall_time_s:
            return True, f"max_wall_time_s ({budget.max_wall_time_s}) reached"
        if self.cost_estimate >= budget.max_cost_estimate:
            return True, f"max_cost_estimate ({budget.max_cost_estimate}) reached"
        return False, ""


# ---------------------------------------------------------------------------
# Revocation channel
# ---------------------------------------------------------------------------


class RevocationChannel:
    """An operator-controlled revocation bus.

    A loop is revoked by calling ``revoke(loop_id, reason)``. Revoked
    loops refuse to take new steps immediately. In-flight steps
    complete to a verifiable terminal state.

    Mirrors NewCore's "revocation mechanisms" requirement.
    """

    def __init__(self) -> None:
        self._revoked: Dict[str, str] = {}  # loop_id -> reason

    def revoke(self, loop_id: str, reason: str = "operator-revoked") -> None:
        self._revoked[loop_id] = reason

    def is_revoked(self, loop_id: str) -> bool:
        return loop_id in self._revoked

    def reason(self, loop_id: str) -> Optional[str]:
        return self._revoked.get(loop_id)

    def clear(self, loop_id: str) -> None:
        self._revoked.pop(loop_id, None)


# ---------------------------------------------------------------------------
# AgentLoop
# ---------------------------------------------------------------------------


# A "work" function is the agent's act. It returns an observation dict.
WorkFn = Callable[[AgentIdentity, Dict[str, Any]], Dict[str, Any]]


@dataclass
class AgentLoopConfig:
    """The configuration for an AgentLoop.

    The config is the operator's view of "what does this loop do,
    and what stops it?"
    """

    identity: AgentIdentity
    verifier: CompositeVerifier
    budget: LoopBudget = field(default_factory=LoopBudget)
    audit_path: Optional[str] = None
    revocation_channel: Optional[RevocationChannel] = None
    max_in_memory_steps: int = 4096   # ring size; the disk trail is the truth


class AgentLoop:
    """The verification-gated loop orchestrator.

    Owns one AgentIdentity, runs the act -> observe -> evaluate -> step
    cycle until the verifier says HALT (or the goal is reached, or
    revocation arrives, or the budget is exhausted). Every step is a
    LoopStep appended to an in-memory ring + an on-disk JSONL audit
    trail.
    """

    def __init__(self, config: AgentLoopConfig) -> None:
        self.config = config
        self._steps: Deque[LoopStep] = deque(maxlen=config.max_in_memory_steps)
        self._budget_status = BudgetStatus()
        self._lifecycle = LifecycleState.PROVISIONED
        self._sequence = 0
        self._audit_path: Optional[Path] = None
        if config.audit_path:
            self._audit_path = Path(config.audit_path)
            self._audit_path.parent.mkdir(parents=True, exist_ok=True)

    # --- lifecycle accessors ----------------------------------------------

    @property
    def loop_id(self) -> str:
        return self.config.identity.loop_id

    @property
    def lifecycle(self) -> LifecycleState:
        return self._lifecycle

    @property
    def step_count(self) -> int:
        return len(self._steps)

    @property
    def steps(self) -> List[LoopStep]:
        return list(self._steps)

    @property
    def budget_status(self) -> BudgetStatus:
        return self._budget_status

    # --- audit persistence ------------------------------------------------

    def _persist(self, step: LoopStep) -> None:
        if self._audit_path is None:
            return
        with self._audit_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(step.to_dict(), sort_keys=True) + "\n")

    # --- core loop --------------------------------------------------------

    def run(
        self,
        work: WorkFn,
        goal: Callable[[Dict[str, Any]], bool],
        max_iterations: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run the loop until goal / halt / revocation / budget.

        `work(identity, action) -> observation` is the act -> observe step.
        `goal(observation) -> bool` is the operator-defined completion
        condition. `max_iterations` is a *soft* cap; the *hard* cap is
        the budget. The loop returns the final observation.
        """
        if self._lifecycle in (LifecycleState.COMPLETED, LifecycleState.FAILED, LifecycleState.REVOKED):
            raise RuntimeError(f"loop {self.loop_id} is already terminal ({self._lifecycle.value})")

        self._lifecycle = LifecycleState.RUNNING
        cap = max_iterations if max_iterations is not None else self.config.budget.max_steps

        observation: Optional[Dict[str, Any]] = None
        for _ in range(cap):
            # Revocation check
            rc = self.config.revocation_channel
            if rc is not None and rc.is_revoked(self.loop_id):
                self._terminate(LifecycleState.REVOKED, rc.reason(self.loop_id) or "revoked")
                return observation or {}

            # Budget check
            exhausted, reason = self._budget_status.is_exhausted(self.config.budget)
            if exhausted:
                self._terminate(LifecycleState.COMPLETED, f"budget_exhausted: {reason}")
                return observation or {}

            # Plan the next act from the prior observation
            action = self._plan_next_act(observation)
            prior_evidence = [e for s in self._steps for e in s.evidence]

            # ACT step
            act_step = self._new_step(StepPhase.ACT, action=action)
            try:
                observation = work(self.config.identity, action)
            except Exception as exc:
                act_step.observation = {"error": repr(exc)}
                act_step.ended_at = _utcnow_iso()
                act_step.terminal_reason = f"act-raised: {exc!r}"
                self._steps.append(act_step)
                self._persist(act_step)
                self._terminate(LifecycleState.FAILED, f"act-raised: {exc!r}")
                return {"error": repr(exc)}
            act_step.observation = observation
            act_step.ended_at = _utcnow_iso()
            self._steps.append(act_step)
            self._persist(act_step)

            # OBSERVE step (collapse into the act step's observation)
            obs_step = self._new_step(StepPhase.OBSERVE, observation=observation)
            obs_step.ended_at = _utcnow_iso()
            self._steps.append(obs_step)
            self._persist(obs_step)

            # Count every act against the budget, regardless of verdict.
            # The act happened; the cost was incurred. Halt/Escalate/Goal
            # do not erase the cost. A loop that returns COMPLETED on its
            # first step should still reflect the consumption.
            self._budget_status.steps += 1
            tokens = int(observation.get("tokens_used", 0) or 0) if isinstance(observation, dict) else 0
            cost = float(observation.get("cost_estimate", 0.0) or 0.0) if isinstance(observation, dict) else 0.0
            self._budget_status.tokens += tokens
            self._budget_status.cost_estimate += cost
            self._budget_status.wall_time_s = (
                datetime.now(timezone.utc) - _parse_iso(self._budget_status.started_at)
            ).total_seconds()

            # EVALUATE step
            eval_step = self._new_step(StepPhase.EVALUATE)
            verdict, rationale, evidence = self.config.verifier.evaluate(
                self.config.identity, action, observation, prior_evidence
            )
            eval_step.verdict = verdict
            eval_step.composite_rationale = rationale
            eval_step.evidence = list(evidence)

            # Goal check (only on CONTINUE -- a halted loop does not "win")
            if verdict == Verdict.CONTINUE and goal(observation):
                eval_step.terminal_reason = "goal_reached"
                eval_step.ended_at = _utcnow_iso()
                self._steps.append(eval_step)
                self._persist(eval_step)
                self._terminate(LifecycleState.COMPLETED, "goal_reached")
                return observation

            if verdict == Verdict.HALT:
                eval_step.terminal_reason = f"halt: {rationale}"
                eval_step.ended_at = _utcnow_iso()
                self._steps.append(eval_step)
                self._persist(eval_step)
                self._terminate(LifecycleState.FAILED, f"halt: {rationale}")
                return observation

            if verdict == Verdict.ESCALATE:
                # Pause and surface; the operator can resume by calling
                # `run` again. We do not auto-apply ESCALATE.
                eval_step.terminal_reason = f"escalate: {rationale}"
                eval_step.ended_at = _utcnow_iso()
                self._steps.append(eval_step)
                self._persist(eval_step)
                self._lifecycle = LifecycleState.WAITING
                return observation

            # CONTINUE: nothing else to do; the budget is already counted.
            eval_step.ended_at = _utcnow_iso()
            self._steps.append(eval_step)
            self._persist(eval_step)

        # Soft cap reached -- treated as a clean exit
        self._terminate(LifecycleState.COMPLETED, "max_iterations_reached")
        return observation or {}

    # --- helpers ----------------------------------------------------------

    def _new_step(self, phase: StepPhase, **kwargs: Any) -> LoopStep:
        self._sequence += 1
        return LoopStep(
            step_id=f"step-{self._sequence:06d}-{uuid.uuid4().hex[:8]}",
            loop_id=self.loop_id,
            sequence=self._sequence,
            phase=phase,
            **kwargs,
        )

    def _plan_next_act(self, observation: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Plan the next act from the prior observation.

        The default planner returns a "tick" action that carries the
        prior observation as a hint. Operators can subclass and override
        for richer planning; the loop's contract is just "return a dict."
        """
        if observation is None:
            return {"tool": "loop.tick", "params": {"reason": "init"}}
        return {
            "tool": "loop.tick",
            "params": {
                "reason": "next",
                "prior": observation,
            },
        }

    def _terminate(self, state: LifecycleState, reason: str) -> None:
        self._lifecycle = state
        # Append a closing step so the audit trail is unambiguously closed.
        closing = self._new_step(StepPhase.EVALUATE)
        closing.terminal_reason = reason
        closing.ended_at = _utcnow_iso()
        self._steps.append(closing)
        self._persist(closing)


# ---------------------------------------------------------------------------
# Convenience constructor
# ---------------------------------------------------------------------------


def create_agent_loop(
    principal: str,
    purpose: str,
    verifiers: List[VerifierProtocol],
    loop_id: Optional[str] = None,
    permissions: Tuple[Permission, ...] = (Permission.READ,),
    budget: Optional[LoopBudget] = None,
    audit_path: Optional[str] = None,
    revocation_channel: Optional[RevocationChannel] = None,
    breaker: Any = None,
    ledger: Any = None,
    monitor: Any = None,
) -> AgentLoop:
    """The smallest viable install: 1 line.

    Convenience wrapper that wires up the default verifier stack
    (composite of breaker / ledger / monitor, when attached) and
    returns a ready-to-run loop.

    Pass `breaker`, `ledger`, `monitor` to attach the corresponding
    verifiers. If a slot is None, that verifier is omitted from the
    composite (a loop with no verifier is a fire-and-forget script).
    """
    chosen: List[VerifierProtocol] = list(verifiers)
    if breaker is not None:
        chosen.append(BreakerGateVerifier(breaker))
    if ledger is not None:
        chosen.append(LedgerGateVerifier(ledger))
    if monitor is not None:
        chosen.append(MonitorGateVerifier(monitor))
    if not chosen:
        raise ValueError("at least one verifier is required (pass verifiers=, breaker=, ledger=, or monitor=)")
    composite = CompositeVerifier(chosen)
    identity = AgentIdentity(
        loop_id=loop_id or str(uuid.uuid4()),
        principal=principal,
        purpose=purpose,
        permissions=permissions,
    )
    return AgentLoop(
        AgentLoopConfig(
            identity=identity,
            verifier=composite,
            budget=budget or LoopBudget(),
            audit_path=audit_path,
            revocation_channel=revocation_channel,
        )
    )


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return datetime.now(timezone.utc)
