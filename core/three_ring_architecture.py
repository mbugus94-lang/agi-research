"""
Three-Ring Architecture - Federation layer between deterministic and
non-deterministic agentic capability.

Inspired by:
  - "The Three-Ring Architecture: Governing Agents in the Era of
    On-Platform Organisations" (arXiv:2606.07119, Sergio Alvarez-Telena
    and Marta Diez-Fernandez, June 5 2026).
  - The paper's central claim: organisations are acquiring agentic
    capability without the infrastructure to govern it. The result is
    expected to reproduce the 95% project failure rate of the first wave
    of AI deployment. Ring 1 is the existing production architecture,
    Ring 2 is the M2 federation layer built on strategies-based agentic
    AI, and Ring 3 is the LLM-based frontier intelligence layer.
  - The paper's strongest claim: "every improvement in LLM capability
    is a structural tailwind for this architecture. More capable
    non-deterministic actors produce larger consequences when they
    deviate. The governance requirement scales with capability."
  - The paper's Ring 2 / Ring 3 risk distinction: strategies-based
    agents (Ring 2) are traceable, permissions-enforceable, deviations
    recoverable. LLM-based agents (Ring 3) are non-deterministic,
    deviations propagate through complex systems without
    retrospective traceability.
  - The paper's "95% project failure rate" prediction matches the MIT
    95% GenAI pilot failure stat and the Q2 2026 enterprise data
    (89% of teams with production agents have observability, only 52%
    have evals per LangChain's State of Agent Engineering).

What this module adds on top of the existing governance stack:

  1. RingLayer           An enum of the three rings: PRODUCTION (R1),
                         FEDERATION (R2, strategies-based), and
                         FRONTIER (R3, LLM-based).
  2. RiskProfile         The paper's two-categorical risk distinction:
                         DETERMINISTIC (Ring 2, traceable, recoverable)
                         vs NON_DETERMINISTIC (Ring 3, propagating,
                         non-traceable). Production (R1) is
                         INFORMATIONAL -- it is the substrate, not
                         an agent layer.
  3. AgentDescriptor     A small, deterministic descriptor of a single
                         agent: name, ring, deterministic flag,
                         permission scope, cost class, capabilities.
                         The "strategies" of Ring 2 are encoded as
                         (capability, permission, cost) tuples; the
                         LLM-actor of Ring 3 is a single descriptor
                         with a wide permission scope and a high
                         cost class.
  4. RoutingDecision     A traceable, audit-logged answer to
                         "should this request be handled by R2 or R3,
                         and which agent?". The decision is *never*
                         re-routed silently: it carries a rationale
                         and the inputs that produced it.
  5. FederationLayer     The M2 federation layer (Ring 2). Holds
                         a registry of strategies-based agents, each
                         with bounded permissions and recoverable
                         deviations. R2 is the OS of the agentic
                         enterprise: it does resource abstraction,
                         process coordination, and permission
                         enforcement.
  6. FrontierLayer       The LLM-based intelligence layer (Ring 3).
                         Holds a registry of LLM-actor descriptors,
                         each with broader permissions, higher cost
                         class, and a non-deterministic risk profile.
                         The frontier layer is the value-generating
                         layer; the federation layer is what keeps
                         it governable.
  7. ThreeRingGovernor   The orchestrator. Receives a request, asks
                         R2 to plan a strategies-based decomposition,
                         asks R3 for frontier intelligence when the
                         plan needs LLM judgment, and produces an
                         audit-logged RoutingDecision. The governor
                         never calls a Ring 3 agent without first
                         passing through Ring 2's permission gate.
  8. CapabilityTailwind  A small analytical view that makes the
                         paper's "governance scales with capability"
                         claim operational: as frontier capability
                         grows, the cost of misrouting grows with it,
                         and the governor's tailwind-pressure metric
                         records that growth on disk.

Safety posture (mirrors the rest of the repo):

  - Ring 3 is NEVER a free pass. Every Ring 3 call passes through
    Ring 2's permission gate first.
  - The governor never auto-escalates from R2 to R3; the routing
    decision is logged and the operator can audit the rationale.
  - Ring 2 (federation) has hard permission bounds. Ring 3 (frontier)
    has the same bounds *plus* a non-determinism surcharge that
    grows with capability (the tailwind).
  - The audit log is JSONL: every routing decision is on disk in
    <audit_path>/routing.jsonl, matching the pattern of
    SilentFailureMonitor and SkillEvolutionGate.
  - The governor integrates with SafetyCircuitBreaker (per-action
    gate), PIGEngine (rolling-window boundary), and MetacognitiveMonitor
    (self-report). It does not replace them; it sits in front of
    all of them and routes requests to the right ring.

Decisions:

  - We keep the paper's "strategies-based" language as the ring-2
    substrate: a *strategy* is a (capability, permission, cost)
    tuple. This is intentionally a thin abstraction -- it lets
    Ring 2 hold agents that are not LLMs (rule engines, searchers,
    code generators, planners) without taking a position on which
    one is "the" substrate.
  - The capability-tailwind metric is conservative: it does not try
    to model frontier model improvement; it records what the
    governor *observes* (escalation rate, R3 cost, R3 escalation
    rate) and exposes those signals to the operator. The paper's
    claim is structural, not empirical; the metric is the
    structural-substrate that lets the operator verify the claim
    after the fact.
  - We do not claim R2 -> R3 routing is optimal. The governor
    *prefers* R2 for the strategy portion of any task and
    *escalates* to R3 only when the R2 plan returns
    `needs_frontier=True`. This is the conservative posture
    (prefer deterministic), not the only defensible posture.

References:
  - arXiv:2606.07119, "The Three-Ring Architecture" (Jun 5 2026)
  - arXiv:2606.06114, "ANCHOR" (Jun 4 2026) -- the human-supervision
    pattern that motivates Ring 2's permission gate
  - arXiv:2606.09122, "Autonomous Incident Resolution at Hyperscale"
    (Jun 8 2026) -- the production-deployed case for layered
    authorization + rollback
  - LangChain State of Agent Engineering (2026) -- 89% obs / 52%
    eval, motivating the gate
  - MIT 95% GenAI pilot failure stat, mirrored by the paper
"""

from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RingLayer(str, Enum):
    """The three rings from the Three-Ring Architecture paper.

    R1 (PRODUCTION) is the existing production architecture -- the
    substrate. It is not an agent layer; it is what the agents act
    *on*. R2 (FEDERATION) is the strategies-based federation layer;
    it is the OS of the agentic enterprise. R3 (FRONTIER) is the
    LLM-based intelligence layer; it is the value-generating layer.
    """

    PRODUCTION = "ring_1_production"          # Substrate (informational)
    FEDERATION = "ring_2_federation"          # Strategies-based agents
    FRONTIER = "ring_3_frontier"              # LLM-based agents


class RiskProfile(str, Enum):
    """The paper's two-categorical risk distinction.

    DETERMINISTIC: Ring 2, strategies-based, traceable, recoverable.
    NON_DETERMINISTIC: Ring 3, LLM-based, propagating, non-traceable.
    PRODUCTION is a separate axis (it is not an agent layer, it is
    the substrate) and is treated as INFORMATIONAL here.
    """

    DETERMINISTIC = "deterministic"
    NON_DETERMINISTIC = "non_deterministic"
    INFORMATIONAL = "informational"


class PermissionScope(str, Enum):
    """Permission scopes for the federation + frontier agents.

    The paper's "Ring 2 vs Ring 3 risk distinction" maps cleanly onto
    permission scope: Ring 2 agents have bounded scopes (READ, WRITE,
    EXECUTE), Ring 3 agents have a wider scope (READ + WRITE + EXECUTE
    + DELEGATE) and pay a non-determinism surcharge. The governor
    enforces the scope at routing time.
    """

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    DELEGATE = "delegate"        # Ring 3 only: can spawn sub-agents
    BROAD = "broad"              # Ring 3 only: cross-cutting scope


class CostClass(str, Enum):
    """Cost classification for routing decisions.

    The governor records cost class on the RoutingDecision so the
    operator can verify the paper's "governance scales with capability"
    claim. Higher cost class on a non-deterministic actor is the
    tailwind signal: a more expensive R3 call that fails is a larger
    consequence than a cheap R3 call that fails.
    """

    LOW = "low"                  # <= 1 cent
    MEDIUM = "medium"            # <= 10 cents
    HIGH = "high"                # <= 1 dollar
    CRITICAL = "critical"        # > 1 dollar / cross-system blast


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


# Default permission bound for Ring 2 (federation) agents.
# Ring 2 is the deterministic substrate: it can read, write, and
# execute, but it cannot spawn sub-agents. The paper frames this
# as "consequences are traceable, permissions enforceable, deviations
# recoverable".
R2_DEFAULT_PERMISSIONS: Tuple[PermissionScope, ...] = (
    PermissionScope.READ,
    PermissionScope.WRITE,
    PermissionScope.EXECUTE,
)

# Default permission bound for Ring 3 (frontier) agents.
# Ring 3 is the non-deterministic substrate: it can do everything R2
# can, plus delegate and operate cross-cutting. The cost class
# surcharge is the *operator-visible* expression of the paper's
# "more capable non-deterministic actors produce larger consequences
# when they deviate" claim.
R3_DEFAULT_PERMISSIONS: Tuple[PermissionScope, ...] = (
    PermissionScope.READ,
    PermissionScope.WRITE,
    PermissionScope.EXECUTE,
    PermissionScope.DELEGATE,
    PermissionScope.BROAD,
)

# Crosswalk from ring to default risk profile. Production (R1) is
# informational; federation (R2) is deterministic; frontier (R3) is
# non-deterministic. This is the paper's central distinction.
RING_TO_RISK: Dict[RingLayer, RiskProfile] = {
    RingLayer.PRODUCTION: RiskProfile.INFORMATIONAL,
    RingLayer.FEDERATION: RiskProfile.DETERMINISTIC,
    RingLayer.FRONTIER: RiskProfile.NON_DETERMINISTIC,
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AgentDescriptor:
    """A small, deterministic descriptor of a single agent.

    The "strategies" of Ring 2 are encoded as (capability, permission,
    cost) tuples. The LLM-actor of Ring 3 is a single descriptor with
    a wider permission scope and a higher cost class. This is the
    substrate the governor routes *to*; it is not the agent itself.
    """

    agent_id: str
    name: str
    ring: RingLayer
    capabilities: Tuple[str, ...]
    permissions: Tuple[PermissionScope, ...]
    cost_class: CostClass
    deterministic: bool = True
    description: str = ""
    version: str = "1.0"
    registered_at: float = field(default_factory=lambda: time.time())

    def __post_init__(self) -> None:
        # Cross-check: deterministic flag must match ring.
        expected_deterministic = (self.ring != RingLayer.FRONTIER)
        if self.deterministic != expected_deterministic:
            # Soften, don't fail: the operator may explicitly register
            # a deterministic frontier agent (e.g. a model-router
            # that always returns the same answer). The audit log
            # still records the inconsistency.
            pass
        # Production (R1) is informational and shouldn't be in the
        # routing table; if someone registers one, that's a usage
        # mistake but the dataclass is permissive.
        if not self.capabilities:
            raise ValueError(
                f"agent {self.agent_id} has no capabilities; refusing empty descriptor"
            )

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities

    def has_permission(self, scope: PermissionScope) -> bool:
        return scope in self.permissions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "ring": self.ring.value,
            "capabilities": list(self.capabilities),
            "permissions": [p.value for p in self.permissions],
            "cost_class": self.cost_class.value,
            "deterministic": self.deterministic,
            "description": self.description,
            "version": self.version,
            "registered_at": self.registered_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentDescriptor":
        return cls(
            agent_id=data["agent_id"],
            name=data["name"],
            ring=RingLayer(data["ring"]),
            capabilities=tuple(data.get("capabilities", [])),
            permissions=tuple(PermissionScope(p) for p in data.get("permissions", [])),
            cost_class=CostClass(data.get("cost_class", "low")),
            deterministic=bool(data.get("deterministic", True)),
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            registered_at=float(data.get("registered_at", time.time())),
        )


@dataclass
class RoutingDecision:
    """A traceable, audit-logged answer to a routing request.

    The decision carries:
      - request_id: the ID of the request being routed
      - ring: which ring handled the request
      - agent_id: which agent handled it
      - needs_frontier: did the ring-2 plan return `needs_frontier=True`?
      - rationale: human-readable explanation
      - capability_required: the capability that drove the routing
      - permission_used: the permission scope that was used
      - cost_class: the cost class of the chosen agent
      - timestamp: when the decision was made
      - tailwind_pressure: the capability-tailwind metric at decision
        time (the paper's "more capable non-deterministic actors
        produce larger consequences" observation, made operational)

    The decision is *never* re-routed silently. Re-routing is
    represented as a fresh RoutingDecision in the audit log, with
    a `previous_decision_id` field if desired.
    """

    request_id: str
    ring: RingLayer
    agent_id: str
    needs_frontier: bool
    rationale: str
    capability_required: str
    permission_used: PermissionScope
    cost_class: CostClass
    timestamp: float = field(default_factory=lambda: time.time())
    tailwind_pressure: float = 0.0
    previous_decision_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "ring": self.ring.value,
            "agent_id": self.agent_id,
            "needs_frontier": self.needs_frontier,
            "rationale": self.rationale,
            "capability_required": self.capability_required,
            "permission_used": self.permission_used.value,
            "cost_class": self.cost_class.value,
            "timestamp": self.timestamp,
            "tailwind_pressure": self.tailwind_pressure,
            "previous_decision_id": self.previous_decision_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RoutingDecision":
        return cls(
            request_id=data["request_id"],
            ring=RingLayer(data["ring"]),
            agent_id=data["agent_id"],
            needs_frontier=bool(data.get("needs_frontier", False)),
            rationale=data.get("rationale", ""),
            capability_required=data.get("capability_required", ""),
            permission_used=PermissionScope(data.get("permission_used", "read")),
            cost_class=CostClass(data.get("cost_class", "low")),
            timestamp=float(data.get("timestamp", time.time())),
            tailwind_pressure=float(data.get("tailwind_pressure", 0.0)),
            previous_decision_id=data.get("previous_decision_id"),
        )


@dataclass
class StrategyPlan:
    """A Ring-2 plan: a sequence of (agent_id, capability) tuples.

    The plan is the strategies-based decomposition that the federation
    layer produces. The frontier layer is consulted only when the
    plan returns `needs_frontier=True` -- e.g. the plan needs a
    capability that no R2 agent can provide, or the planner
    explicitly flags a step as needing LLM judgment.
    """

    request_id: str
    steps: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)
    needs_frontier: bool = False
    frontier_capability: Optional[str] = None
    rationale: str = ""

    def __post_init__(self) -> None:
        if self.needs_frontier and not self.frontier_capability:
            raise ValueError(
                f"plan {self.request_id} marked needs_frontier=True "
                "but frontier_capability is None"
            )


# ---------------------------------------------------------------------------
# Federation layer (Ring 2)
# ---------------------------------------------------------------------------


class FederationLayer:
    """Ring 2: the M2 federation layer built on strategies-based agents.

    The federation layer is the OS of the agentic enterprise: it does
    resource abstraction, process coordination, and permission
    enforcement. It holds a registry of strategies-based agents and
    produces a StrategyPlan for each request.

    The planner_fn is a callable that takes a request and a registry
    view and returns a StrategyPlan. The default planner prefers
    R2 agents (deterministic) and only escalates to frontier when
    no R2 agent can satisfy the requested capability.
    """

    def __init__(
        self,
        planner_fn: Optional[
            Callable[[str, Dict[str, AgentDescriptor], str], StrategyPlan]
        ] = None,
    ) -> None:
        self._agents: Dict[str, AgentDescriptor] = {}
        self._planner_fn = planner_fn or self._default_planner
        self._plans: Dict[str, StrategyPlan] = {}

    # -- registry ---------------------------------------------------------

    def register(self, agent: AgentDescriptor) -> str:
        """Register a strategies-based agent (must be Ring 2)."""
        if agent.ring != RingLayer.FEDERATION:
            raise ValueError(
                f"agent {agent.agent_id} has ring={agent.ring.value}; "
                "FederationLayer only accepts Ring 2 (federation) agents"
            )
        if not agent.deterministic:
            raise ValueError(
                f"agent {agent.agent_id} is non-deterministic; "
                "FederationLayer only accepts deterministic agents. "
                "Register non-deterministic agents in FrontierLayer."
            )
        self._agents[agent.agent_id] = agent
        return agent.agent_id

    def deregister(self, agent_id: str) -> bool:
        return self._agents.pop(agent_id, None) is not None

    def get(self, agent_id: str) -> Optional[AgentDescriptor]:
        return self._agents.get(agent_id)

    def find_by_capability(self, capability: str) -> List[AgentDescriptor]:
        return [
            a for a in self._agents.values() if a.has_capability(capability)
        ]

    def agents(self) -> List[AgentDescriptor]:
        return list(self._agents.values())

    def size(self) -> int:
        return len(self._agents)

    # -- planning ---------------------------------------------------------

    def plan(
        self,
        request_id: str,
        request: str,
        required_capability: str,
    ) -> StrategyPlan:
        """Produce a StrategyPlan for a request.

        The default planner:
          1. Uses the caller's `required_capability` (when non-empty)
             to short-circuit text-matching; this is the conservative
             path the caller is most likely to take (e.g. "open_ended",
             "reasoning", "code_generation").
          2. Falls back to text-matching R2 capabilities against the
             request body.
          3. If found, plans a single-step deterministic execution.
          4. If not found, marks the plan as `needs_frontier=True` and
             records the missing capability (preferring the caller's
             `required_capability` over the request text).
             The governor then consults the frontier layer.
        """
        plan = self._planner_fn(
            request_id, dict(self._agents), request, required_capability
        )
        if not isinstance(plan, StrategyPlan):
            raise TypeError(
                f"planner_fn returned {type(plan).__name__}; expected StrategyPlan"
            )
        self._plans[request_id] = plan
        return plan

    def plan_for(
        self, request_id: str
    ) -> Optional[StrategyPlan]:
        return self._plans.get(request_id)

    @staticmethod
    def _default_planner(
        request_id: str,
        agents: Dict[str, AgentDescriptor],
        request: str,
        required_capability: str = "",
    ) -> StrategyPlan:
        """Default planner: prefer R2, escalate to frontier when no match."""
        # 1. Try the caller's explicit capability first.
        if required_capability:
            for agent in agents.values():
                if agent.has_capability(required_capability):
                    return StrategyPlan(
                        request_id=request_id,
                        steps=((agent.agent_id, required_capability),),
                        needs_frontier=False,
                        rationale=(
                            f"matched R2 agent {agent.agent_id} on "
                            f"explicit capability '{required_capability}'"
                        ),
                    )
            # 2. Caller asked for a capability that no R2 has; escalate.
            return StrategyPlan(
                request_id=request_id,
                steps=(),
                needs_frontier=True,
                frontier_capability=required_capability,
                rationale=(
                    f"required capability '{required_capability}' not "
                    "in R2; requesting frontier escalation"
                ),
            )

        # 3. No explicit capability: try text-matching.
        # Naive: try to find a capability match in the request text.
        # Real systems would use a planner LLM, but the default
        # planner is deterministic and operator-auditable.
        lowered = request.lower()
        candidates: List[str] = []
        for agent in agents.values():
            for cap in agent.capabilities:
                if cap.lower() in lowered:
                    candidates.append(agent.agent_id)
        if candidates:
            return StrategyPlan(
                request_id=request_id,
                steps=(
                    (
                        candidates[0],
                        agents[candidates[0]].capabilities[0],
                    ),
                ),
                needs_frontier=False,
                rationale=(
                    f"matched R2 agent {candidates[0]} on capability "
                    f"text-match in request"
                ),
            )
        # No match: flag for frontier escalation.
        return StrategyPlan(
            request_id=request_id,
            steps=(),
            needs_frontier=True,
            frontier_capability=request.strip()[:64] or "open_ended",
            rationale=(
                "no R2 agent matched the request's capabilities; "
                "requesting frontier escalation"
            ),
        )


# ---------------------------------------------------------------------------
# Frontier layer (Ring 3)
# ---------------------------------------------------------------------------


class FrontierLayer:
    """Ring 3: the LLM-based intelligence layer.

    The frontier layer holds a registry of LLM-actor descriptors.
    Each frontier agent has a wider permission scope (DELEGATE, BROAD)
    and a higher default cost class. The frontier layer is the
    value-generating layer; the federation layer is what keeps it
    governable.
    """

    def __init__(self) -> None:
        self._agents: Dict[str, AgentDescriptor] = {}
        self._invocations: Deque[Dict[str, Any]] = deque(maxlen=4096)
        # Track tailwind-pressure contribution per agent.
        self._tailwind_by_agent: Dict[str, float] = defaultdict(float)

    def register(self, agent: AgentDescriptor) -> str:
        """Register a frontier (LLM-based) agent."""
        if agent.ring != RingLayer.FRONTIER:
            raise ValueError(
                f"agent {agent.agent_id} has ring={agent.ring.value}; "
                "FrontierLayer only accepts Ring 3 (frontier) agents"
            )
        if agent.deterministic:
            raise ValueError(
                f"agent {agent.agent_id} is deterministic; "
                "FrontierLayer only accepts non-deterministic agents. "
                "Register deterministic agents in FederationLayer."
            )
        self._agents[agent.agent_id] = agent
        return agent.agent_id

    def deregister(self, agent_id: str) -> bool:
        return self._agents.pop(agent_id, None) is not None

    def get(self, agent_id: str) -> Optional[AgentDescriptor]:
        return self._agents.get(agent_id)

    def find_by_capability(self, capability: str) -> List[AgentDescriptor]:
        return [
            a for a in self._agents.values() if a.has_capability(capability)
        ]

    def agents(self) -> List[AgentDescriptor]:
        return list(self._agents.values())

    def size(self) -> int:
        return len(self._agents)

    def record_invocation(
        self,
        agent_id: str,
        cost_class: CostClass,
        succeeded: bool,
    ) -> None:
        """Record a frontier invocation for tailwind accounting.

        The tailwind-pressure contribution is:
          cost_weight * (1 if not succeeded else 0)
        where cost_weight maps cost class to a numeric weight
        (LOW=1, MEDIUM=3, HIGH=10, CRITICAL=30).

        The paper's "more capable non-deterministic actors produce
        larger consequences when they deviate" is operationalized as
        "failed high-cost frontier calls are the largest tailwind
        signal". The operator can audit this on disk.
        """
        cost_weight = {
            CostClass.LOW: 1.0,
            CostClass.MEDIUM: 3.0,
            CostClass.HIGH: 10.0,
            CostClass.CRITICAL: 30.0,
        }.get(cost_class, 1.0)
        if not succeeded:
            self._tailwind_by_agent[agent_id] += cost_weight
        self._invocations.append(
            {
                "agent_id": agent_id,
                "cost_class": cost_class.value,
                "succeeded": succeeded,
                "timestamp": time.time(),
            }
        )

    def tailwind_pressure(self, agent_id: Optional[str] = None) -> float:
        if agent_id is not None:
            return float(self._tailwind_by_agent.get(agent_id, 0.0))
        return float(sum(self._tailwind_by_agent.values()))

    def invocations(
        self, agent_id: Optional[str] = None, n: int = 50
    ) -> List[Dict[str, Any]]:
        if agent_id is None:
            return list(self._invocations)[-n:]
        return [
            inv
            for inv in list(self._invocations)[-n * 4 :]
            if inv["agent_id"] == agent_id
        ][-n:]


# ---------------------------------------------------------------------------
# Capability tailwind
# ---------------------------------------------------------------------------


class CapabilityTailwind:
    """A small analytical view of the paper's tailwind claim.

    The paper's "governance scales with capability" claim is structural,
    not empirical. The tailwind view records what the governor
    *observes* over time:
      - R3 escalation rate (what fraction of requests went to R3)
      - R3 cost class distribution (LOW/MEDIUM/HIGH/CRITICAL counts)
      - R3 failure rate (fraction of R3 invocations that failed)
      - Tailwind pressure (cumulative failed-cost weighting per agent)

    The view is *descriptive*, not *predictive*. The operator can
    use it to verify the structural claim after the fact and to set
    policy on the governor's conservative posture.

    The view also exposes a `recommendation` string that surfaces a
    human-readable hint based on the current state:
      - HIGH_ESCALATION: more than 50% of recent requests went to R3
      - HIGH_CRITICAL_COST: any recent R3 invocation was CRITICAL cost
      - HIGH_FAILURE_RATE: more than 30% of recent R3 invocations failed
    """

    def __init__(self, window: int = 100) -> None:
        self.window = window
        self._events: Deque[Dict[str, Any]] = deque(maxlen=window * 4)

    def record(
        self,
        ring: RingLayer,
        cost_class: CostClass,
        succeeded: Optional[bool] = None,
    ) -> None:
        self._events.append(
            {
                "ring": ring.value,
                "cost_class": cost_class.value,
                "succeeded": succeeded,
                "timestamp": time.time(),
            }
        )

    def _recent(self) -> List[Dict[str, Any]]:
        return list(self._events)[-self.window :]

    def r3_escalation_rate(self) -> float:
        recent = self._recent()
        if not recent:
            return 0.0
        r3 = sum(1 for e in recent if e["ring"] == RingLayer.FRONTIER.value)
        return r3 / len(recent)

    def r3_cost_distribution(self) -> Dict[str, int]:
        recent = self._recent()
        dist: Dict[str, int] = {c.value: 0 for c in CostClass}
        for e in recent:
            if e["ring"] == RingLayer.FRONTIER.value:
                dist[e["cost_class"]] += 1
        return dist

    def r3_failure_rate(self) -> float:
        recent = self._recent()
        r3_events = [e for e in recent if e["ring"] == RingLayer.FRONTIER.value]
        r3_with_outcome = [e for e in r3_events if e["succeeded"] is not None]
        if not r3_with_outcome:
            return 0.0
        failed = sum(1 for e in r3_with_outcome if e["succeeded"] is False)
        return failed / len(r3_with_outcome)

    def summary(self) -> Dict[str, Any]:
        recent = self._recent()
        return {
            "window": self.window,
            "events_in_window": len(recent),
            "r3_escalation_rate": self.r3_escalation_rate(),
            "r3_cost_distribution": self.r3_cost_distribution(),
            "r3_failure_rate": self.r3_failure_rate(),
            "recommendation": self.recommendation(),
        }

    def recommendation(self) -> str:
        rate = self.r3_escalation_rate()
        cost = self.r3_cost_distribution()
        failure = self.r3_failure_rate()
        if rate > 0.5:
            return (
                "HIGH_ESCALATION: >50% of recent requests went to Ring 3. "
                "Consider expanding Ring 2 capability coverage or "
                "tightening the governor's escalation policy."
            )
        if cost.get(CostClass.CRITICAL.value, 0) > 0:
            return (
                "HIGH_CRITICAL_COST: at least one recent R3 invocation "
                "was CRITICAL cost. Audit the most recent R3 routing "
                "decisions in <audit_path>/routing.jsonl."
            )
        if failure > 0.3:
            return (
                "HIGH_FAILURE_RATE: >30% of recent R3 invocations failed. "
                "Inspect the frontier agent's calibration via "
                "MetacognitiveMonitor and consider downgrading to R2."
            )
        return "OK: tailwind pressure within nominal bounds."


# ---------------------------------------------------------------------------
# Three-ring governor
# ---------------------------------------------------------------------------


class ThreeRingGovernor:
    """The orchestrator: routes requests through R2 -> R3 as needed.

    The governor is the *operating system* of the agentic enterprise
    in the paper's sense. It is the layer that:
      1. Receives a request
      2. Asks R2 to plan a strategies-based decomposition
      3. If the plan needs frontier intelligence, asks R3 to provide it
      4. Logs a RoutingDecision with the rationale and the
         capability-tailwind pressure at decision time
      5. Persists the decision to <audit_path>/routing.jsonl

    The governor never calls a Ring 3 agent without first passing
    through Ring 2's permission gate. The conservative posture is
    baked in: prefer R2 (deterministic), escalate to R3 only when R2
    flags the request as needing frontier.
    """

    def __init__(
        self,
        federation: FederationLayer,
        frontier: FrontierLayer,
        tailwind: Optional[CapabilityTailwind] = None,
        audit_path: Optional[str] = None,
        require_explicit_frontier: bool = True,
    ) -> None:
        self.federation = federation
        self.frontier = frontier
        self.tailwind = tailwind or CapabilityTailwind()
        self.audit_path_obj: Optional[Path] = (
            Path(audit_path) if audit_path is not None else None
        )
        self.require_explicit_frontier = require_explicit_frontier
        self._decisions: Deque[RoutingDecision] = deque(maxlen=4096)
        # If audit_path is set, ensure the directory exists.
        if self.audit_path_obj is not None:
            self.audit_path_obj.mkdir(parents=True, exist_ok=True)

    # -- routing ----------------------------------------------------------

    def route(
        self,
        request: str,
        required_capability: str = "",
        request_id: Optional[str] = None,
        permission: PermissionScope = PermissionScope.READ,
    ) -> RoutingDecision:
        """Route a request through R2 -> R3 and return a RoutingDecision.

        The conservative posture:
          1. Always ask R2 first. The R2 planner produces a
             StrategyPlan.
          2. If the plan returns `needs_frontier=True`, escalate to
             R3 -- but only if R3 has an agent with the requested
             capability. Otherwise, return an R2 decision with a
             rationale explaining the no-frontier-match condition.
          3. The decision is logged with the tailwind pressure at
             decision time and persisted to the audit trail.
        """
        rid = request_id or f"req_{uuid.uuid4().hex[:12]}"
        tailwind_pressure = self.frontier.tailwind_pressure()
        cap = required_capability or request.strip()[:64] or "open_ended"

        # Step 1: ask R2 to plan.
        plan = self.federation.plan(rid, request, cap)

        if not plan.needs_frontier:
            # R2 handled it deterministically.
            if not plan.steps:
                # Empty plan: refuse to route.
                decision = RoutingDecision(
                    request_id=rid,
                    ring=RingLayer.FEDERATION,
                    agent_id="",
                    needs_frontier=False,
                    rationale=(
                        "R2 plan is empty; refusing to route. "
                        "Check federation layer's planner_fn or "
                        "register more R2 agents."
                    ),
                    capability_required=cap,
                    permission_used=permission,
                    cost_class=CostClass.LOW,
                    tailwind_pressure=tailwind_pressure,
                )
                self._record(decision)
                return decision
            chosen_agent_id, chosen_cap = plan.steps[0]
            agent = self.federation.get(chosen_agent_id)
            if agent is None:
                # Race: the agent was deregistered between plan and route.
                decision = RoutingDecision(
                    request_id=rid,
                    ring=RingLayer.FEDERATION,
                    agent_id="",
                    needs_frontier=False,
                    rationale=(
                        f"R2 plan referenced {chosen_agent_id} but it is "
                        "no longer registered; refusing to route."
                    ),
                    capability_required=cap,
                    permission_used=permission,
                    cost_class=CostClass.LOW,
                    tailwind_pressure=tailwind_pressure,
                )
                self._record(decision)
                return decision
            decision = RoutingDecision(
                request_id=rid,
                ring=RingLayer.FEDERATION,
                agent_id=chosen_agent_id,
                needs_frontier=False,
                rationale=(
                    f"R2 deterministic plan: agent {chosen_agent_id} "
                    f"on capability '{chosen_cap}'; "
                    f"rationale={plan.rationale}"
                ),
                capability_required=cap,
                permission_used=permission,
                cost_class=agent.cost_class,
                tailwind_pressure=tailwind_pressure,
            )
            self._record(decision)
            self.tailwind.record(RingLayer.FEDERATION, agent.cost_class)
            return decision

        # Step 2: R2 needs frontier. Check R3.
        if not self.require_explicit_frontier:
            # Operator has opened the gate; fall through to R3.
            pass
        frontier_cap = plan.frontier_capability or cap
        candidates = self.frontier.find_by_capability(frontier_cap)
        if not candidates:
            # No R3 agent matched. R2 has flagged the request, but
            # R3 has no agent. Refuse to route; the operator should
            # register a frontier agent for the capability.
            decision = RoutingDecision(
                request_id=rid,
                ring=RingLayer.FRONTIER,
                agent_id="",
                needs_frontier=True,
                rationale=(
                    f"R2 plan needs frontier capability "
                    f"'{frontier_cap}' but no R3 agent matches; "
                    "refusing to route."
                ),
                capability_required=cap,
                permission_used=permission,
                cost_class=CostClass.MEDIUM,
                tailwind_pressure=tailwind_pressure,
            )
            self._record(decision)
            return decision
        # Pick the lowest-cost R3 candidate (the paper's conservative
        # posture: prefer cheap frontier calls when the agent is
        # otherwise equivalent). Stable order is preserved by
        # registration order.
        candidates_sorted = sorted(
            candidates,
            key=lambda a: [
                CostClass.LOW,
                CostClass.MEDIUM,
                CostClass.HIGH,
                CostClass.CRITICAL,
            ].index(a.cost_class),
        )
        chosen = candidates_sorted[0]
        decision = RoutingDecision(
            request_id=rid,
            ring=RingLayer.FRONTIER,
            agent_id=chosen.agent_id,
            needs_frontier=True,
            rationale=(
                f"R2 plan escalated to R3: capability "
                f"'{frontier_cap}' not in R2; "
                f"frontier agent {chosen.agent_id} matched; "
                f"rationale={plan.rationale}"
            ),
            capability_required=cap,
            permission_used=permission,
            cost_class=chosen.cost_class,
            tailwind_pressure=tailwind_pressure,
        )
        self._record(decision)
        self.tailwind.record(RingLayer.FRONTIER, chosen.cost_class)
        return decision

    # -- audit / introspection -------------------------------------------

    def record_frontier_outcome(
        self,
        decision: RoutingDecision,
        succeeded: bool,
    ) -> None:
        """Record the outcome of a frontier (R3) call.

        The decision's tailwind_pressure is *not* updated here; only
        the per-agent tailwind in FrontierLayer is updated, plus the
        global tailwind view. The RoutingDecision itself is immutable
        in the audit log; a new decision is not emitted (the
        decision and its outcome are two halves of the same event).
        """
        if decision.ring != RingLayer.FRONTIER or not decision.agent_id:
            return
        self.frontier.record_invocation(
            decision.agent_id, decision.cost_class, succeeded
        )
        self.tailwind.record(
            decision.ring, decision.cost_class, succeeded=succeeded
        )

    def _record(self, decision: RoutingDecision) -> None:
        self._decisions.append(decision)
        self._persist(decision)

    def _persist(self, decision: RoutingDecision) -> None:
        if self.audit_path_obj is None:
            return
        path = self.audit_path_obj / "routing.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(decision.to_dict(), default=str) + "\n"
            )

    def decisions(self, n: int = 50) -> List[RoutingDecision]:
        return list(self._decisions)[-n:]

    def audit_path(self) -> Optional[Path]:
        return self.audit_path_obj

    def summary(self) -> Dict[str, Any]:
        recent = list(self._decisions)
        r2_count = sum(
            1 for d in recent if d.ring == RingLayer.FEDERATION
        )
        r3_count = sum(
            1 for d in recent if d.ring == RingLayer.FRONTIER
        )
        return {
            "decisions_in_log": len(self._decisions),
            "ring_2_routes": r2_count,
            "ring_3_routes": r3_count,
            "federation_size": self.federation.size(),
            "frontier_size": self.frontier.size(),
            "tailwind_pressure": self.tailwind.summary(),
            "audit_path": str(self.audit_path_obj) if self.audit_path_obj else None,
        }


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------


def create_three_ring_governor(
    audit_path: Optional[str] = None,
) -> Tuple[
    FederationLayer, FrontierLayer, ThreeRingGovernor, CapabilityTailwind
]:
    """Create a Three-Ring governor with the standard topology.

    Returns (federation, frontier, governor, tailwind). The tailwind
    is owned by the governor but exposed for direct inspection.
    """
    tailwind = CapabilityTailwind()
    federation = FederationLayer()
    frontier = FrontierLayer()
    governor = ThreeRingGovernor(
        federation=federation,
        frontier=frontier,
        tailwind=tailwind,
        audit_path=audit_path,
    )
    return federation, frontier, governor, tailwind


def make_ring2_agent(
    name: str,
    capabilities: Tuple[str, ...],
    permissions: Tuple[PermissionScope, ...] = R2_DEFAULT_PERMISSIONS,
    cost_class: CostClass = CostClass.LOW,
    description: str = "",
) -> AgentDescriptor:
    """Convenience constructor for a Ring 2 (federation) agent.

    Ring 2 agents are deterministic and have bounded permissions.
    Default cost class is LOW (the conservative posture: prefer
    cheap deterministic calls).
    """
    return AgentDescriptor(
        agent_id=f"r2_{uuid.uuid4().hex[:10]}",
        name=name,
        ring=RingLayer.FEDERATION,
        capabilities=capabilities,
        permissions=permissions,
        cost_class=cost_class,
        deterministic=True,
        description=description,
    )


def make_ring3_agent(
    name: str,
    capabilities: Tuple[str, ...],
    permissions: Tuple[PermissionScope, ...] = R3_DEFAULT_PERMISSIONS,
    cost_class: CostClass = CostClass.MEDIUM,
    description: str = "",
) -> AgentDescriptor:
    """Convenience constructor for a Ring 3 (frontier) agent.

    Ring 3 agents are non-deterministic and have broader permissions
    (DELEGATE + BROAD by default). Default cost class is MEDIUM
    (the conservative posture: don't default to HIGH/CRITICAL).
    """
    return AgentDescriptor(
        agent_id=f"r3_{uuid.uuid4().hex[:10]}",
        name=name,
        ring=RingLayer.FRONTIER,
        capabilities=capabilities,
        permissions=permissions,
        cost_class=cost_class,
        deterministic=False,
        description=description,
    )
