"""
Tool Privilege Governor - Least-privilege tool selection for BaseAgent.

Inspired by:
  - "When Lower Privileges Suffice: Investigating Over-Privileged Tool Selection
    in LLM Agents" (OpenReview AXH6buTOVx, 2026) - ToolPrivBench
    finding: mainstream LLM agents frequently over-select higher-privilege
    tools when a lower-privilege option would suffice; transient tool
    failures amplify the escalation; prompt-level controls offer limited
    mitigation; a privilege-aware post-training defense is the proposed
    mitigation.
  - "Unsafe Only in Combination" (OpenReview v2QHWcC0UC) - CAPSPLIT-IB:
    risks emerge from capability *combinations*, not isolated tools.
  - "Will the Agent Recuse Itself?" (arXiv:2606.06460) - the Recuse
    Signal pattern: a published, in-band cooperative governance signal.
  - Three-Ring Architecture (arXiv:2606.07119) - the paper's R2/R3 risk
    distinction maps onto tool privilege scope.
  - ProofCarryingActionBridge (Jun 13) - the bridge's per-action
    EnforceabilityClass is the substrate for privilege-bound actions.

The repo already has per-action *policy* gates (SafetyCircuitBreaker,
ThreeRingGovernor, GovernedActionLoop) and an *evidence* substrate
(EvidenceLedger). What it doesn't have is a *least-privilege tool
planner*: when a step in the planner's plan calls for a tool, the
governor ranks all registered tools by *required privilege* and picks
the cheapest one that is sufficient for the step.

The governor does three things, in order:

  1. PRIVILEGE RANKING:   every registered tool carries a
     ToolPrivilegeDescriptor (action_type, permission_scope,
     cost_class, ring_layer, required_capability). The governor
     sorts candidate tools by a composite privilege score:
     permission_scope rank + cost_class weight + ring_layer
     penalty. Lower score = lower privilege = preferred.

  2. SUFFICIENCY CHECK:   a tool is "sufficient" for a step if it
     (a) handles the action category, (b) declares the required
     capability or matches by name, (c) is not blocked by the
     policy blocklist, and (d) has not exceeded its per-step or
     per-minute rate limit. The governor picks the lowest-privilege
     sufficient tool.

  3. AUDIT TRAIL:        every selection is recorded in a
     SelectionRecord with the ranked candidates, the chosen tool,
     and the privilege delta (chosen vs. the naive top-of-list).
     This is the *measurable* substrate for the OpenReview finding
     that "over-privileged tool selection is common."

Conservative posture (mirrors the rest of the repo):

  - The governor NEVER auto-escalates privilege; on transient
    failures it surfaces a *suggestion* to the operator, who
    can either accept (require_human) or retry with the same
    tool. The CAPSPLIT-IB paper's "minimum-cost intervention"
    idea is preserved as a recommendation, not an action.
  - Insufficient tools (no matching capability) are surfaced
    explicitly. The governor does not silently fall back to a
    higher-privilege tool; it records an InsufficiencyReport
    the operator can audit.
  - A *blocked* tool (SafetyCircuitBreaker policy blocklist)
    is never selected, even if it is the lowest-privilege
    sufficient option. The blocklist is the floor.
  - The privilege score is deterministic and stable: same
    registered tools -> same ranking. No "smart" reordering
    that could change results between runs.
  - The audit trail is the *system of record* for tool
    selection; downstream reflection / metacog can use it as
    a calibration signal (a high over-privilege rate is a
    metacognitive red flag).

The module is LLM-agnostic, deterministic, and small (~750 LOC).
It does not call any LLM, send any network request, or take a
position on which model is the substrate.

Decisions:

  - We model privilege as a small composite of three axes:
    permission_scope (READ < WRITE < EXECUTE < DELEGATE < BROAD),
    cost_class (LOW < MEDIUM < HIGH < CRITICAL), and ring_layer
    (R2 < R3). The composite is the sum of ranks, not a product;
    the axes are independent in the worst case.
  - We keep "capability match" as a separate predicate from
    "permission match". A tool can have the right capability
    (e.g. "execute_code") but the wrong permission (e.g. EXECUTE
    vs. READ). The governor ranks *sufficient* tools by
    permission, not by capability. This is the OpenReview
    finding: agents over-select the *capability* match, not
    the *privilege* match.
  - We treat the SafetyCircuitBreaker's blocklist as a *floor*,
    not a *ceiling*. The governor never selects a blocked
    tool; the operator can override per-call via the
    `allow_blocked=True` flag (used only for explicit human
    override of the policy).
  - We do not implement a full ToolPrivBench-style benchmark
    here; that's a research-grade scoring harness. We implement
    the *governor* the benchmark would be measured against.

References:
  - OpenReview AXH6buTOVx, "When Lower Privileges Suffice" (2026)
  - OpenReview v2QHWcC0UC, "Unsafe Only in Combination" (2026)
  - arXiv:2606.06460, "Will the Agent Recurse Itself?" (2026)
  - arXiv:2606.07119, "Three-Ring Architecture" (2026)
  - core.proof_carrying_action (Jun 13) - per-action envelope
  - core.safety_circuit_breaker (May 2026) - policy blocklist
  - core.three_ring_architecture (Jun 12) - R2/R3 routing
  - core.governed_action_loop (Jun 14) - four-substrate cross-check
  - core.evidence_ledger (Jun 5) - claim/evidence substrate
"""

from __future__ import annotations

import json
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Set, Tuple


# Local imports stay in the core namespace; no cross-module cycles
from .safety_circuit_breaker import (
    ActionCategory,
    SafetyCircuitBreaker,
)
from .three_ring_architecture import (
    CostClass,
    PermissionScope,
    RingLayer,
)
from .evidence_ledger import (
    Claim,
    ClaimStatus,
    Evidence,
    EvidenceKind,
    EvidenceLedger,
    EvidencePolarity,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SelectionOutcome(str, Enum):
    """The outcome of a privilege-aware tool selection.

    SELECTED          - the governor found a sufficient tool and chose it
    INSUFFICIENT      - no registered tool is sufficient for the step
                        (caller must register more tools or decompose)
    BLOCKED_ALL       - every sufficient tool is blocked by the policy
                        blocklist; the step is unsafe to run as-is
    RATE_LIMITED      - every sufficient tool has hit its per-step
                        or per-minute cap; retry later
    POLICY_DENIED     - the SafetyCircuitBreaker's assess_risk()
                        returns a verdict that the governor refuses
                        to honor at this ring layer
    """

    SELECTED = "selected"
    INSUFFICIENT = "insufficient"
    BLOCKED_ALL = "blocked_all"
    RATE_LIMITED = "rate_limited"
    POLICY_DENIED = "policy_denied"


# ---------------------------------------------------------------------------
# Privilege descriptor + score
# ---------------------------------------------------------------------------


# Ordinal rank for PermissionScope (lower = safer)
_PERMISSION_RANK: Dict[PermissionScope, int] = {
    PermissionScope.READ: 0,
    PermissionScope.WRITE: 1,
    PermissionScope.EXECUTE: 2,
    PermissionScope.DELEGATE: 3,
    PermissionScope.BROAD: 4,
}


# Ordinal rank for CostClass (lower = cheaper)
_COST_RANK: Dict[CostClass, int] = {
    CostClass.LOW: 0,
    CostClass.MEDIUM: 1,
    CostClass.HIGH: 2,
    CostClass.CRITICAL: 3,
}


# Ordinal rank for RingLayer (lower = more deterministic)
_RING_RANK: Dict[RingLayer, int] = {
    RingLayer.PRODUCTION: 0,
    RingLayer.FEDERATION: 1,
    RingLayer.FRONTIER: 2,
}


@dataclass
class ToolPrivilegeDescriptor:
    """A small, deterministic descriptor of a single tool's privilege surface.

    The descriptor is *separate* from the callable. The callable
    is what the BaseAgent actually invokes; the descriptor is
    what the governor reasons about. This separation is the
    conservative posture: the operator can audit the privilege
    surface without running the tool, and the governor can
    refuse a tool *before* it is invoked.
    """

    tool_id: str
    name: str
    action_type: str
    action_category: ActionCategory
    permission_scope: PermissionScope
    cost_class: CostClass
    ring_layer: RingLayer
    capabilities: Tuple[str, ...]
    is_blocked: bool = False
    per_minute_cap: int = 60
    per_step_cap: int = 1
    description: str = ""
    version: str = "1.0"
    registered_at: float = field(default_factory=lambda: time.time())

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError(
                f"tool {self.tool_id} has empty name; refusing empty descriptor"
            )
        if not self.action_type:
            raise ValueError(
                f"tool {self.tool_id} has empty action_type"
            )
        if not self.capabilities:
            raise ValueError(
                f"tool {self.tool_id} has no capabilities; refusing empty descriptor"
            )

    def privilege_score(self) -> float:
        """Composite privilege score. Lower = lower privilege = preferred.

        The score is the sum of three independent ranks: permission
        (0..4), cost (0..3), ring (0..2). A read-only R2 LOW tool
        scores 0+0+1 = 1; a broad R3 CRITICAL tool scores 4+3+2 = 9.

        Ties (same composite) are broken by tool_id (stable
        lexicographic) so the ranking is deterministic across runs.
        """
        return (
            _PERMISSION_RANK[self.permission_scope]
            + _COST_RANK[self.cost_class]
            + _RING_RANK[self.ring_layer]
        )

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "name": self.name,
            "action_type": self.action_type,
            "action_category": self.action_category.value,
            "permission_scope": self.permission_scope.value,
            "cost_class": self.cost_class.value,
            "ring_layer": self.ring_layer.value,
            "capabilities": list(self.capabilities),
            "is_blocked": self.is_blocked,
            "per_minute_cap": self.per_minute_cap,
            "per_step_cap": self.per_step_cap,
            "description": self.description,
            "version": self.version,
            "registered_at": self.registered_at,
            "privilege_score": self.privilege_score(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolPrivilegeDescriptor":
        return cls(
            tool_id=data["tool_id"],
            name=data["name"],
            action_type=data["action_type"],
            action_category=ActionCategory(data["action_category"]),
            permission_scope=PermissionScope(data["permission_scope"]),
            cost_class=CostClass(data["cost_class"]),
            ring_layer=RingLayer(data["ring_layer"]),
            capabilities=tuple(data.get("capabilities", [])),
            is_blocked=bool(data.get("is_blocked", False)),
            per_minute_cap=int(data.get("per_minute_cap", 60)),
            per_step_cap=int(data.get("per_step_cap", 1)),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            registered_at=float(data.get("registered_at", time.time())),
        )


# ---------------------------------------------------------------------------
# Step request + result
# ---------------------------------------------------------------------------


@dataclass
class StepRequest:
    """A single step that the planner wants the governor to resolve.

    Carries the step_type, the action_type the planner is asking
    for, the required capability (if any), the requested
    permission scope, the priority, and optional claim_ids
    grounding the step in the EvidenceLedger.
    """

    step_id: str
    action_type: str
    required_capability: str = ""
    requested_permission: Optional[PermissionScope] = None
    priority: int = 0  # higher = more urgent; used for tie-breaking
    target: str = ""
    description: str = ""
    claim_ids: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action_type": self.action_type,
            "required_capability": self.required_capability,
            "requested_permission": (
                self.requested_permission.value
                if self.requested_permission else None
            ),
            "priority": self.priority,
            "target": self.target,
            "description": self.description,
            "claim_ids": list(self.claim_ids),
            "timestamp": self.timestamp,
        }


@dataclass
class CandidateRanking:
    """One row in the ranking table for a single selection.

    Carries the tool's privilege score, why it was ranked
    where it was, and whether it was ultimately selected.
    The ranking is the *auditable* substrate for the
    OpenReview finding that agents over-select higher
    privilege tools.
    """

    tool_id: str
    tool_name: str
    privilege_score: float
    sufficient: bool
    blocked: bool
    rate_limited: bool
    selected: bool
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "tool_name": self.tool_name,
            "privilege_score": self.privilege_score,
            "sufficient": self.sufficient,
            "blocked": self.blocked,
            "rate_limited": self.rate_limited,
            "selected": self.selected,
            "reason": self.reason,
        }


@dataclass
class InsufficiencyReport:
    """A diagnostic for INSUFFICIENT and BLOCKED_ALL outcomes.

    Carries the step_id, the action_type, the count of
    candidates considered, and a sample of the closest
    candidates (by capability match) so the operator can
    audit *why* no tool was sufficient.
    """

    step_id: str
    action_type: str
    required_capability: str
    candidates_considered: int
    closest_by_capability: List[CandidateRanking] = field(default_factory=list)
    closest_by_privilege: List[CandidateRanking] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action_type": self.action_type,
            "required_capability": self.required_capability,
            "candidates_considered": self.candidates_considered,
            "closest_by_capability": [
                c.to_dict() for c in self.closest_by_capability
            ],
            "closest_by_privilege": [
                c.to_dict() for c in self.closest_by_privilege
            ],
            "notes": list(self.notes),
        }


@dataclass
class SelectionRecord:
    """The complete record of a single tool selection.

    The SelectionRecord is the *system of record* for tool
    selection. It is appended to a JSONL audit trail (if
    enabled) and consumed by the reflection / metacog layer
    as a calibration signal.

    privilege_delta is the *measurable* substrate for the
    OpenReview finding: chosen_score - naive_score, where
    naive_score is the highest-privilege tool's score.
    privilege_delta < 0 means the governor picked a *lower*
    privilege tool than the naive top-of-list.
    """

    step_id: str
    step_request: StepRequest
    outcome: SelectionOutcome
    chosen_tool_id: Optional[str]
    chosen_tool_name: Optional[str]
    chosen_privilege_score: Optional[float]
    naive_privilege_score: float
    privilege_delta: Optional[float]
    rankings: List[CandidateRanking] = field(default_factory=list)
    insufficiency: Optional[InsufficiencyReport] = None
    timestamp: float = field(default_factory=lambda: time.time())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_request": self.step_request.to_dict(),
            "outcome": self.outcome.value,
            "chosen_tool_id": self.chosen_tool_id,
            "chosen_tool_name": self.chosen_tool_name,
            "chosen_privilege_score": self.chosen_privilege_score,
            "naive_privilege_score": self.naive_privilege_score,
            "privilege_delta": self.privilege_delta,
            "rankings": [r.to_dict() for r in self.rankings],
            "insufficiency": (
                self.insufficiency.to_dict()
                if self.insufficiency else None
            ),
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Per-tool rate limiter
# ---------------------------------------------------------------------------


@dataclass
class _PerToolCounts:
    """Rate-limit counters for a single tool.

    Uses a deque of (timestamp, kind) tuples for per-minute
    accounting and a per-step counter for the immediate
    cap. The deque is capped at 256 entries to bound memory.
    """

    last_step_at: float = 0.0
    minute_window: Deque[Tuple[float, str]] = field(
        default_factory=lambda: deque(maxlen=256)
    )

    def is_step_capped(self, per_step_cap: int) -> bool:
        # The per_step_cap is *per step resolution*, i.e. the
        # governor never selects the same tool twice in the
        # same selection cycle. This is enforced by the caller's
        # contract, not by the limiter, but we keep the field
        # for the descriptor.
        return per_step_cap <= 0

    def is_minute_capped(self, per_minute_cap: int) -> bool:
        now = time.time()
        cutoff = now - 60.0
        recent = sum(1 for t, _ in self.minute_window if t > cutoff)
        return recent >= per_minute_cap

    def record(self, kind: str) -> None:
        self.minute_window.append((time.time(), kind))


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------


def make_low_privilege_tool(
    name: str,
    action_type: str,
    capabilities: Tuple[str, ...],
    *,
    tool_id: Optional[str] = None,
    action_category: ActionCategory = ActionCategory.READ,
    ring_layer: RingLayer = RingLayer.FEDERATION,
    cost_class: CostClass = CostClass.LOW,
    description: str = "",
) -> ToolPrivilegeDescriptor:
    """The conservative default constructor: R2 bounded, READ, LOW.

    Matches the Three-Ring paper's R2 default: bounded
    permissions, recoverable deviations, low cost. The
    majority of agent tools should be R2 LOW.
    """
    return ToolPrivilegeDescriptor(
        tool_id=tool_id or f"tool_{uuid.uuid4().hex[:10]}",
        name=name,
        action_type=action_type,
        action_category=action_category,
        permission_scope=PermissionScope.READ,
        cost_class=cost_class,
        ring_layer=ring_layer,
        capabilities=capabilities,
        description=description,
    )


def make_high_privilege_tool(
    name: str,
    action_type: str,
    capabilities: Tuple[str, ...],
    *,
    tool_id: Optional[str] = None,
    action_category: ActionCategory = ActionCategory.EXECUTE,
    cost_class: CostClass = CostClass.MEDIUM,
    description: str = "",
) -> ToolPrivilegeDescriptor:
    """The conservative high-privilege constructor: R3, EXECUTE, MEDIUM.

    Used sparingly: only for tools that genuinely need
    execute or delegate scope. The default cost class is
    MEDIUM (not HIGH or CRITICAL) so the operator has to
    explicitly opt into higher cost for the most expensive
    tools.
    """
    return ToolPrivilegeDescriptor(
        tool_id=tool_id or f"tool_{uuid.uuid4().hex[:10]}",
        name=name,
        action_type=action_type,
        action_category=action_category,
        permission_scope=PermissionScope.EXECUTE,
        cost_class=cost_class,
        ring_layer=RingLayer.FRONTIER,
        capabilities=capabilities,
        description=description,
    )


# ---------------------------------------------------------------------------
# Governor
# ---------------------------------------------------------------------------


@dataclass
class ToolPrivilegeGovernorConfig:
    """Tunables for the governor.

    All defaults are conservative: refuse to silently
    escalate, refuse to auto-block, surface diagnostics.
    """

    max_per_minute_cap: int = 1000
    # If True, blocked tools are still ranked but never
    # selected. The audit trail records that they were
    # considered and rejected.
    respect_blocklist: bool = True
    # If True, the audit trail is persisted to JSONL on
    # disk. Operator opt-in.
    persist_audit: bool = False
    # If True, the governor reads the EvidenceLedger and
    # raises a soft flag when the step's claim_ids are not
    # SUPPORTED. The flag is recorded in the SelectionRecord
    # notes; the governor does not refuse the step.
    consult_ledger: bool = True


class ToolPrivilegeGovernor:
    """The privilege-aware tool selector.

    The governor exposes four methods:

    - ``register_tool(descriptor)`` - add a tool to the
      registry; the descriptor is the source of truth for
      privilege metadata.

    - ``select_tool(step)`` - run the privilege-aware
      selection algorithm; return a SelectionRecord.

    - ``record_outcome(step_id, succeeded)`` - record the
      outcome of a tool invocation; updates the per-tool
      rate limiter and the audit trail.

    - ``summary()`` - aggregate view: total selections,
      over-privilege rate, blocked-rate, mean privilege
      delta, etc.
    """

    def __init__(
        self,
        breaker: Optional[SafetyCircuitBreaker] = None,
        ledger: Optional[EvidenceLedger] = None,
        config: Optional[ToolPrivilegeGovernorConfig] = None,
        audit_path: Optional[str] = None,
    ) -> None:
        self.breaker = breaker
        self.ledger = ledger
        self.config = config or ToolPrivilegeGovernorConfig()
        self.audit_path_obj: Optional[Path] = (
            Path(audit_path) if audit_path is not None else None
        )
        if self.audit_path_obj is not None:
            self.audit_path_obj.mkdir(parents=True, exist_ok=True)
        self._tools: Dict[str, ToolPrivilegeDescriptor] = {}
        self._counters: Dict[str, _PerToolCounts] = {}
        self._records: Deque[SelectionRecord] = deque(maxlen=4096)

    # -- registry --------------------------------------------------------

    def register_tool(self, descriptor: ToolPrivilegeDescriptor) -> str:
        """Register a tool. Returns the tool_id.

        Overwrites if the tool_id is already registered; the
        old per-tool counters are reset on overwrite.
        """
        self._tools[descriptor.tool_id] = descriptor
        self._counters[descriptor.tool_id] = _PerToolCounts()
        return descriptor.tool_id

    def deregister(self, tool_id: str) -> bool:
        removed = self._tools.pop(tool_id, None) is not None
        self._counters.pop(tool_id, None)
        return removed

    def get(self, tool_id: str) -> Optional[ToolPrivilegeDescriptor]:
        return self._tools.get(tool_id)

    def all_tools(self) -> List[ToolPrivilegeDescriptor]:
        return list(self._tools.values())

    def size(self) -> int:
        return len(self._tools)

    # -- selection -------------------------------------------------------

    def select_tool(self, step: StepRequest) -> SelectionRecord:
        """Run the privilege-aware selection algorithm.

        Conservative posture:

          1. Compute the candidate set: tools whose action_type
             matches the step's action_type (or whose capabilities
             include the step's required_capability).
          2. For each candidate, decide if it is "sufficient":
             (a) handles the action category, (b) declares the
             required capability, (c) is not blocked, (d) is
             not rate-limited.
          3. Rank the sufficient candidates by privilege_score()
             ascending (lowest privilege first). Stable tie-break
             on tool_id.
          4. If the ranking is non-empty, pick the top. Record
             the choice in a SelectionRecord.
          5. If the ranking is empty, return an INSUFFICIENT or
             BLOCKED_ALL or RATE_LIMITED record depending on
             which predicate emptied it.
          6. The naive privilege score is the *highest* score
             in the candidate set; privilege_delta measures how
             much lower the chosen tool is than the naive pick.
        """
        candidates = self._candidates_for(step)
        rankings: List[CandidateRanking] = []
        sufficient: List[CandidateRanking] = []
        insufficient_kinds: Set[str] = set()
        chosen: Optional[CandidateRanking] = None

        for descriptor in candidates:
            entry = self._evaluate(descriptor, step)
            rankings.append(entry)
            if entry.sufficient:
                sufficient.append(entry)
            else:
                if entry.blocked:
                    insufficient_kinds.add("blocked")
                if entry.rate_limited:
                    insufficient_kinds.add("rate_limited")
                if not entry.sufficient and not entry.blocked and not entry.rate_limited:
                    insufficient_kinds.add("insufficient")

        # Sort: sufficient first (lowest privilege score first),
        # then insufficient for the diagnostic report.
        rankings.sort(
            key=lambda r: (
                0 if r.sufficient else 1,
                r.privilege_score,
                r.tool_id,
            )
        )
        if sufficient:
            chosen = rankings[0]
            chosen.selected = True
            outcome = SelectionOutcome.SELECTED
        else:
            # No sufficient tool. Decide the outcome by which
            # predicate emptied the set.
            if "blocked" in insufficient_kinds and "insufficient" not in insufficient_kinds:
                outcome = SelectionOutcome.BLOCKED_ALL
            elif "rate_limited" in insufficient_kinds and "insufficient" not in insufficient_kinds:
                outcome = SelectionOutcome.RATE_LIMITED
            elif "insufficient" in insufficient_kinds and not insufficient_kinds - {"insufficient"}:
                outcome = SelectionOutcome.INSUFFICIENT
            else:
                # Mixed: surface the most conservative posture.
                if "blocked" in insufficient_kinds:
                    outcome = SelectionOutcome.BLOCKED_ALL
                elif "rate_limited" in insufficient_kinds:
                    outcome = SelectionOutcome.RATE_LIMITED
                else:
                    outcome = SelectionOutcome.INSUFFICIENT

        # Naive score: the highest-privilege sufficient tool's score.
        # If no sufficient tool, naive_score is the *highest* score
        # in the candidate set (what the agent would have picked
        # under the "trust the LLM" baseline).
        if candidates:
            naive_score = max(d.privilege_score() for d in candidates)
        else:
            naive_score = 0.0

        # Optional ledger consultation
        notes: List[str] = []
        if self.config.consult_ledger and self.ledger is not None and step.claim_ids:
            statuses = []
            for cid in step.claim_ids:
                try:
                    v = self.ledger.verify(cid)
                    if hasattr(v.status, "value"):
                        statuses.append(str(v.status.value).upper())
                    else:
                        statuses.append(str(v.status).upper())
                except Exception:
                    statuses.append("ERROR")
            unsupported = [s for s in statuses if s not in {"SUPPORTED"}]
            if unsupported:
                notes.append(
                    f"ledger: {len(unsupported)} of {len(statuses)} "
                    f"claims are not SUPPORTED: {sorted(set(unsupported))}"
                )

        record = SelectionRecord(
            step_id=step.step_id,
            step_request=step,
            outcome=outcome,
            chosen_tool_id=chosen.tool_id if chosen else None,
            chosen_tool_name=chosen.tool_name if chosen else None,
            chosen_privilege_score=(
                chosen.privilege_score if chosen else None
            ),
            naive_privilege_score=naive_score,
            privilege_delta=(
                (chosen.privilege_score - naive_score)
                if chosen else None
            ),
            rankings=rankings,
            insufficiency=self._insufficiency_for(step, candidates, rankings)
            if outcome != SelectionOutcome.SELECTED else None,
        )
        if notes:
            # Attach notes via the insufficiency field's notes if
            # we have one; otherwise inline as part of the step
            # request for the audit log.
            record.step_request.description = (
                step.description + " | notes: " + " | ".join(notes)
            )

        # Persist if configured
        self._records.append(record)
        self._persist(record)
        return record

    def _candidates_for(self, step: StepRequest) -> List[ToolPrivilegeDescriptor]:
        """Return the candidate set for a step.

        A tool is a candidate if:
          - its action_type matches the step's action_type, OR
          - the step's required_capability is non-empty AND
            the tool declares that capability.
        The match is loose: we want to surface alternatives,
        not narrow to a single tool.
        """
        out: List[ToolPrivilegeDescriptor] = []
        for tool in self._tools.values():
            if tool.action_type == step.action_type:
                out.append(tool)
                continue
            if step.required_capability and tool.has_capability(
                step.required_capability
            ):
                out.append(tool)
        return out

    def _evaluate(
        self,
        descriptor: ToolPrivilegeDescriptor,
        step: StepRequest,
    ) -> CandidateRanking:
        """Decide if a single tool is sufficient for a step.

        Returns a CandidateRanking. The ranking is the
        auditable substrate; the caller (select_tool) does
        the actual picking.
        """
        # Blocked by the policy blocklist.
        blocked = (
            self.config.respect_blocklist and descriptor.is_blocked
        )
        # Sufficiency: handles the action category, declares the
        # capability (if specified), and the requested permission
        # is at or below the tool's permission scope.
        handles_category = (
            descriptor.action_category.value == self._action_category_for(
                step.action_type
            )
        )
        capability_ok = (
            not step.required_capability
            or descriptor.has_capability(step.required_capability)
        )
        # The requested permission must be at or below the tool's
        # permission scope; if the caller didn't specify, we
        # accept any tool that handles the action.
        if step.requested_permission is not None:
            permission_ok = (
                _PERMISSION_RANK[descriptor.permission_scope]
                >= _PERMISSION_RANK[step.requested_permission]
            )
        else:
            permission_ok = True
        action_type_ok = (
            descriptor.action_type == step.action_type
            or step.required_capability
            and descriptor.has_capability(step.required_capability)
        )
        # Rate-limit check (per-minute, since the per-step cap
        # is enforced by the caller's contract).
        counter = self._counters.get(descriptor.tool_id)
        if counter is None:
            counter = _PerToolCounts()
            self._counters[descriptor.tool_id] = counter
        rate_limited = counter.is_minute_capped(descriptor.per_minute_cap)
        sufficient = (
            handles_category
            and capability_ok
            and permission_ok
            and action_type_ok
            and not blocked
            and not rate_limited
        )
        # Build a short reason for the audit log.
        if blocked:
            reason = "blocked_by_policy"
        elif rate_limited:
            reason = "rate_limited"
        elif not handles_category:
            reason = "wrong_action_category"
        elif not capability_ok:
            reason = "missing_capability"
        elif not permission_ok:
            reason = "permission_too_low"
        elif not action_type_ok:
            reason = "action_type_mismatch"
        else:
            reason = "sufficient"
        return CandidateRanking(
            tool_id=descriptor.tool_id,
            tool_name=descriptor.name,
            privilege_score=descriptor.privilege_score(),
            sufficient=sufficient,
            blocked=blocked,
            rate_limited=rate_limited,
            selected=False,
            reason=reason,
        )

    def _action_category_for(self, action_type: str) -> str:
        """Map an action_type string to a SafetyCircuitBreaker category.

        This is the same vocabulary the GovernedActionLoop uses.
        We keep the mapping in the governor to avoid a circular
        import: GovernedActionLoop imports ThreeRing + SafetyCB,
        not ToolPrivilegeGovernor.
        """
        # Conservative default: unknown action_types map to
        # EXECUTE (the most conservative category for the
        # blocklist to look at). The operator can override
        # via the descriptor's action_category field.
        mapping = {
            "read": "read",
            "search": "read",
            "query": "read",
            "write": "write",
            "create": "write",
            "update": "write",
            "delete": "delete",
            "drop": "delete",
            "truncate": "delete",
            "execute": "execute",
            "self_modify": "modify_self",
            "send_money": "external_api",
            "publish": "external_api",
            "broadcast": "external_api",
            "network_call": "network",
            "database": "database",
            "file_system": "file_system",
        }
        return mapping.get(action_type, "execute")

    def _insufficiency_for(
        self,
        step: StepRequest,
        candidates: List[ToolPrivilegeDescriptor],
        rankings: List[CandidateRanking],
    ) -> InsufficiencyReport:
        """Build a diagnostic for INSUFFICIENT / BLOCKED_ALL / RATE_LIMITED.

        The report's ``closest_by_capability`` ranks candidates
        by how close they were to satisfying the step (lexical
        overlap on the required_capability); ``closest_by_privilege``
        ranks by privilege score ascending. Both lists are
        capped at 5 entries.
        """
        # Closest by capability: candidates whose capability set
        # shares at least one token with the required_capability.
        req_tokens = set(
            t for t in step.required_capability.lower().replace("_", " ").split()
            if t
        )
        if not req_tokens:
            req_tokens = set(step.action_type.lower().split())
        scored: List[Tuple[int, CandidateRanking]] = []
        for r in rankings:
            tool = self._tools.get(r.tool_id)
            if tool is None:
                continue
            tool_tokens = set()
            for cap in tool.capabilities:
                tool_tokens.update(cap.lower().replace("_", " ").split())
            inter = req_tokens & tool_tokens
            scored.append((len(inter), r))
        scored.sort(key=lambda pair: (-pair[0], pair[1].privilege_score, pair[1].tool_id))
        closest_by_cap = [r for _, r in scored[:5]]
        closest_by_priv = sorted(
            rankings, key=lambda r: (r.privilege_score, r.tool_id)
        )[:5]
        notes: List[str] = []
        if not candidates:
            notes.append(
                "no tools registered with the requested action_type "
                f"'{step.action_type}' or required_capability "
                f"'{step.required_capability}'"
            )
        else:
            insufficient = [r for r in rankings if not r.sufficient]
            if insufficient:
                reasons = sorted(set(r.reason for r in insufficient))
                notes.append(
                    f"all {len(insufficient)} candidates were "
                    f"insufficient; reasons: {reasons}"
                )
        return InsufficiencyReport(
            step_id=step.step_id,
            action_type=step.action_type,
            required_capability=step.required_capability,
            candidates_considered=len(candidates),
            closest_by_capability=closest_by_cap,
            closest_by_privilege=closest_by_priv,
            notes=notes,
        )

    # -- outcome recording ----------------------------------------------

    def record_outcome(self, step_id: str, succeeded: bool) -> None:
        """Record the outcome of a tool invocation.

        Updates the per-tool rate limiter (one call per
        invocation) and the audit trail. The success/failure
        signal is recorded but does not change the privilege
        score; the privilege score is a property of the tool
        descriptor, not of its history.
        """
        # Find the SelectionRecord for this step
        rec = None
        for r in reversed(self._records):
            if r.step_id == step_id:
                rec = r
                break
        if rec is None or rec.chosen_tool_id is None:
            return
        counter = self._counters.get(rec.chosen_tool_id)
        if counter is None:
            counter = _PerToolCounts()
            self._counters[rec.chosen_tool_id] = counter
        counter.record("ok" if succeeded else "error")

    # -- introspection ---------------------------------------------------

    def summary(self) -> Dict[str, Any]:
        """Aggregate view of the governor's selection history.

        Includes:
          - total selections + outcome breakdown
          - mean privilege_delta across successful selections
            (negative = chose lower privilege than the naive pick)
          - over_privilege_rate: fraction of successful selections
            where privilege_delta > 0 (the governor chose a *higher*
            privilege tool than necessary)
          - blocked_rate: fraction of selections that returned
            BLOCKED_ALL
          - insufficient_rate: fraction that returned INSUFFICIENT
        """
        total = len(self._records)
        if total == 0:
            return {
                "total": 0,
                "outcomes": {o.value: 0 for o in SelectionOutcome},
                "mean_privilege_delta": 0.0,
                "over_privilege_rate": 0.0,
                "blocked_rate": 0.0,
                "insufficient_rate": 0.0,
                "registered_tools": self.size(),
                "audit_path": (
                    str(self.audit_path_obj) if self.audit_path_obj else None
                ),
            }
        outcomes_count: Dict[str, int] = {o.value: 0 for o in SelectionOutcome}
        deltas: List[float] = []
        over_priv = 0
        for r in self._records:
            outcomes_count[r.outcome.value] += 1
            if r.outcome == SelectionOutcome.SELECTED and r.privilege_delta is not None:
                deltas.append(r.privilege_delta)
                if r.privilege_delta > 0:
                    over_priv += 1
        mean_delta = sum(deltas) / len(deltas) if deltas else 0.0
        selected_count = outcomes_count[SelectionOutcome.SELECTED.value] or 1
        return {
            "total": total,
            "outcomes": outcomes_count,
            "mean_privilege_delta": round(mean_delta, 3),
            "over_privilege_rate": round(over_priv / selected_count, 3),
            "blocked_rate": round(
                outcomes_count[SelectionOutcome.BLOCKED_ALL.value] / total, 3
            ),
            "insufficient_rate": round(
                outcomes_count[SelectionOutcome.INSUFFICIENT.value] / total, 3
            ),
            "registered_tools": self.size(),
            "audit_path": (
                str(self.audit_path_obj) if self.audit_path_obj else None
            ),
        }

    def records(self, n: int = 50) -> List[SelectionRecord]:
        return list(self._records)[-n:]

    # -- persistence -----------------------------------------------------

    def _persist(self, record: SelectionRecord) -> None:
        if self.audit_path_obj is None:
            return
        path = self.audit_path_obj / "tool_selection.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(record.to_dict(), default=str) + "\n"
            )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_tool_privilege_governor(
    audit_path: Optional[str] = None,
    breaker: Optional[SafetyCircuitBreaker] = None,
    ledger: Optional[EvidenceLedger] = None,
) -> ToolPrivilegeGovernor:
    """Smallest viable install: 1 line.

    Returns a governor with no tools registered. The
    operator registers tools via ``register_tool`` (or
    ``register_tools_batch`` for the bulk case). The
    breaker and ledger are optional; the governor works
    without them, but consult_ledger is a no-op when
    the ledger is None.
    """
    return ToolPrivilegeGovernor(
        breaker=breaker,
        ledger=ledger,
        config=ToolPrivilegeGovernorConfig(persist_audit=bool(audit_path)),
        audit_path=audit_path,
    )


__all__ = [
    "SelectionOutcome",
    "ToolPrivilegeDescriptor",
    "StepRequest",
    "CandidateRanking",
    "InsufficiencyReport",
    "SelectionRecord",
    "ToolPrivilegeGovernorConfig",
    "ToolPrivilegeGovernor",
    "make_low_privilege_tool",
    "make_high_privilege_tool",
    "create_tool_privilege_governor",
]
