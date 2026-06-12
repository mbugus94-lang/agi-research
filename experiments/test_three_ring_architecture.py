"""
Three-Ring Architecture Test Suite
===================================

Tests for core/three_ring_architecture.py.

Organized in seven classes:
  - TestRingLayer / TestRiskProfile / TestCostClass -- value-object tests
  - TestAgentDescriptor -- descriptor cross-checks, serialization
  - TestPermissionScope -- the conservative permission bound default
  - TestFederationLayer -- registry invariants, planner escalation
  - TestFrontierLayer -- registry invariants, tailwind accounting
  - TestThreeRingGovernor -- end-to-end routing, conservative posture,
    audit trail, tailwind recommendation engine
  - TestConvenienceConstructors -- make_ring2_agent / make_ring3_agent
    defaults and registry integration
  - TestConservativePosture -- the macro invariants of the
    Three-Ring Architecture paper
"""

import json
import os
import tempfile
from pathlib import Path

import pytest

from core.three_ring_architecture import (
    AgentDescriptor,
    CapabilityTailwind,
    CostClass,
    FederationLayer,
    FrontierLayer,
    PermissionScope,
    RingLayer,
    RiskProfile,
    R2_DEFAULT_PERMISSIONS,
    R3_DEFAULT_PERMISSIONS,
    RING_TO_RISK,
    RoutingDecision,
    StrategyPlan,
    ThreeRingGovernor,
    create_three_ring_governor,
    make_ring2_agent,
    make_ring3_agent,
)


# ---------------------------------------------------------------------------
# Value-object tests
# ---------------------------------------------------------------------------


class TestRingLayer:
    def test_three_rings(self):
        assert {r.value for r in RingLayer} == {
            "ring_1_production",
            "ring_2_federation",
            "ring_3_frontier",
        }

    def test_is_str(self):
        # str-mixins should compare equal to their string values.
        assert RingLayer.FEDERATION == "ring_2_federation"

    def test_ring_to_risk_crosswalk(self):
        assert RING_TO_RISK[RingLayer.PRODUCTION] == RiskProfile.INFORMATIONAL
        assert RING_TO_RISK[RingLayer.FEDERATION] == RiskProfile.DETERMINISTIC
        assert RING_TO_RISK[RingLayer.FRONTIER] == RiskProfile.NON_DETERMINISTIC


class TestRiskProfile:
    def test_three_risk_profiles(self):
        assert {r.value for r in RiskProfile} == {
            "deterministic",
            "non_deterministic",
            "informational",
        }


class TestCostClass:
    def test_four_cost_classes(self):
        assert {c.value for c in CostClass} == {
            "low",
            "medium",
            "high",
            "critical",
        }


class TestPermissionScope:
    def test_default_r2_permissions_are_bounded(self):
        # Ring 2 default: read + write + execute. No DELEGATE, no BROAD.
        assert PermissionScope.DELEGATE not in R2_DEFAULT_PERMISSIONS
        assert PermissionScope.BROAD not in R2_DEFAULT_PERMISSIONS
        assert PermissionScope.READ in R2_DEFAULT_PERMISSIONS
        assert PermissionScope.WRITE in R2_DEFAULT_PERMISSIONS
        assert PermissionScope.EXECUTE in R2_DEFAULT_PERMISSIONS

    def test_default_r3_permissions_are_broader(self):
        # Ring 3 default: includes DELEGATE + BROAD.
        assert PermissionScope.DELEGATE in R3_DEFAULT_PERMISSIONS
        assert PermissionScope.BROAD in R3_DEFAULT_PERMISSIONS
        # R3 superset of R2.
        for p in R2_DEFAULT_PERMISSIONS:
            assert p in R3_DEFAULT_PERMISSIONS

    def test_r2_permissions_strict_subset_of_r3(self):
        assert set(R2_DEFAULT_PERMISSIONS).issubset(set(R3_DEFAULT_PERMISSIONS))


# ---------------------------------------------------------------------------
# AgentDescriptor tests
# ---------------------------------------------------------------------------


class TestAgentDescriptor:
    def test_minimal_construction(self):
        a = AgentDescriptor(
            agent_id="a1",
            name="SearchBot",
            ring=RingLayer.FEDERATION,
            capabilities=("search",),
            permissions=R2_DEFAULT_PERMISSIONS,
            cost_class=CostClass.LOW,
        )
        assert a.agent_id == "a1"
        assert a.has_capability("search")
        assert not a.has_capability("code")
        assert a.has_permission(PermissionScope.READ)
        assert not a.has_permission(PermissionScope.DELEGATE)
        assert a.deterministic is True

    def test_empty_capabilities_rejected(self):
        with pytest.raises(ValueError, match="no capabilities"):
            AgentDescriptor(
                agent_id="a1",
                name="EmptyBot",
                ring=RingLayer.FEDERATION,
                capabilities=(),
                permissions=R2_DEFAULT_PERMISSIONS,
                cost_class=CostClass.LOW,
            )

    def test_to_dict_round_trip(self):
        a = make_ring2_agent("SearchBot", ("search", "web_search"))
        d = a.to_dict()
        assert d["ring"] == RingLayer.FEDERATION.value
        assert d["deterministic"] is True
        a2 = AgentDescriptor.from_dict(d)
        assert a2.agent_id == a.agent_id
        assert a2.ring == a.ring
        assert a2.capabilities == a.capabilities
        assert a2.permissions == a.permissions
        assert a2.cost_class == a.cost_class

    def test_registered_at_set(self):
        a = make_ring2_agent("X", ("cap",))
        assert a.registered_at > 0


# ---------------------------------------------------------------------------
# FederationLayer tests (Ring 2)
# ---------------------------------------------------------------------------


class TestFederationLayer:
    def test_empty_layer(self):
        fed = FederationLayer()
        assert fed.size() == 0
        assert fed.agents() == []

    def test_register_r2_agent(self):
        fed = FederationLayer()
        a = make_ring2_agent("SearchBot", ("search",))
        fed.register(a)
        assert fed.size() == 1
        assert fed.get(a.agent_id).name == "SearchBot"

    def test_reject_r3_agent(self):
        fed = FederationLayer()
        a = make_ring3_agent("LLMJudge", ("reasoning",))
        with pytest.raises(ValueError, match="FederationLayer only accepts Ring 2"):
            fed.register(a)

    def test_reject_non_deterministic_agent_in_r2(self):
        # Even with the right ring, a non-deterministic agent is rejected.
        # (We have to construct manually because make_ring2_agent forces
        # deterministic=True.)
        a = AgentDescriptor(
            agent_id="r2_xx",
            name="NaughtyR2",
            ring=RingLayer.FEDERATION,
            capabilities=("x",),
            permissions=R2_DEFAULT_PERMISSIONS,
            cost_class=CostClass.LOW,
            deterministic=False,
        )
        fed = FederationLayer()
        with pytest.raises(ValueError, match="non-deterministic"):
            fed.register(a)

    def test_deregister(self):
        fed = FederationLayer()
        a = make_ring2_agent("SearchBot", ("search",))
        fed.register(a)
        assert fed.deregister(a.agent_id) is True
        assert fed.deregister(a.agent_id) is False
        assert fed.size() == 0

    def test_find_by_capability(self):
        fed = FederationLayer()
        a1 = make_ring2_agent("SearchBot", ("search", "web_search"))
        a2 = make_ring2_agent("CodeBot", ("code_generation",))
        fed.register(a1)
        fed.register(a2)
        searchers = fed.find_by_capability("search")
        assert len(searchers) == 1
        assert searchers[0].name == "SearchBot"
        assert fed.find_by_capability("nonexistent") == []

    def test_plan_with_r2_match(self):
        fed = FederationLayer()
        a = make_ring2_agent("SearchBot", ("search",))
        fed.register(a)
        plan = fed.plan("req1", "I want to search the web", "search")
        assert plan.needs_frontier is False
        assert plan.steps[0][0] == a.agent_id
        assert plan.steps[0][1] == "search"

    def test_plan_with_explicit_capability_match(self):
        fed = FederationLayer()
        a = make_ring2_agent("SearchBot", ("search", "web_search"))
        fed.register(a)
        plan = fed.plan("req1", "free text", "web_search")
        assert plan.needs_frontier is False
        assert plan.steps[0][1] == "web_search"

    def test_plan_escalates_to_frontier_when_no_match(self):
        fed = FederationLayer()
        a = make_ring2_agent("SearchBot", ("search",))
        fed.register(a)
        plan = fed.plan("req1", "I want to do something exotic", "open_ended")
        assert plan.needs_frontier is True
        assert plan.frontier_capability == "open_ended"

    def test_plan_with_custom_planner(self):
        def custom_planner(request_id, agents, request, required_capability):
            return StrategyPlan(
                request_id=request_id,
                steps=(("custom_agent", "x"),),
                needs_frontier=False,
                rationale="custom planner",
            )

        fed = FederationLayer(planner_fn=custom_planner)
        plan = fed.plan("req1", "any", "any")
        assert plan.steps[0][0] == "custom_agent"

    def test_plan_for_returns_stored_plan(self):
        fed = FederationLayer()
        fed.register(make_ring2_agent("SearchBot", ("search",)))
        plan = fed.plan("req1", "search please", "search")
        assert fed.plan_for("req1") is plan
        assert fed.plan_for("nonexistent") is None

    def test_planner_must_return_strategyplan(self):
        def bad_planner(*args, **kwargs):
            return {"not": "a plan"}

        fed = FederationLayer(planner_fn=bad_planner)
        with pytest.raises(TypeError, match="expected StrategyPlan"):
            fed.plan("req1", "any", "any")


# ---------------------------------------------------------------------------
# FrontierLayer tests (Ring 3)
# ---------------------------------------------------------------------------


class TestFrontierLayer:
    def test_empty_layer(self):
        front = FrontierLayer()
        assert front.size() == 0
        assert front.agents() == []

    def test_register_r3_agent(self):
        front = FrontierLayer()
        a = make_ring3_agent("LLMJudge", ("reasoning",))
        front.register(a)
        assert front.size() == 1

    def test_reject_r2_agent(self):
        front = FrontierLayer()
        a = make_ring2_agent("SearchBot", ("search",))
        with pytest.raises(ValueError, match="FrontierLayer only accepts Ring 3"):
            front.register(a)

    def test_reject_deterministic_agent_in_r3(self):
        a = AgentDescriptor(
            agent_id="r3_xx",
            name="NaughtyR3",
            ring=RingLayer.FRONTIER,
            capabilities=("x",),
            permissions=R3_DEFAULT_PERMISSIONS,
            cost_class=CostClass.LOW,
            deterministic=True,
        )
        front = FrontierLayer()
        with pytest.raises(ValueError, match="deterministic"):
            front.register(a)

    def test_deregister(self):
        front = FrontierLayer()
        a = make_ring3_agent("LLMJudge", ("reasoning",))
        front.register(a)
        assert front.deregister(a.agent_id) is True
        assert front.deregister(a.agent_id) is False
        assert front.size() == 0

    def test_find_by_capability(self):
        front = FrontierLayer()
        a = make_ring3_agent("LLMJudge", ("reasoning", "open_ended"))
        front.register(a)
        assert len(front.find_by_capability("reasoning")) == 1
        assert front.find_by_capability("nope") == []

    def test_tailwind_starts_at_zero(self):
        front = FrontierLayer()
        assert front.tailwind_pressure() == 0.0
        assert front.tailwind_pressure("anything") == 0.0

    def test_record_invocation_failure_increments_tailwind(self):
        front = FrontierLayer()
        a = make_ring3_agent("LLMJudge", ("x",), cost_class=CostClass.HIGH)
        front.register(a)
        front.record_invocation(a.agent_id, CostClass.HIGH, succeeded=False)
        # HIGH cost weight = 10.0
        assert front.tailwind_pressure(a.agent_id) == 10.0
        # Success does NOT increment.
        front.record_invocation(a.agent_id, CostClass.HIGH, succeeded=True)
        assert front.tailwind_pressure(a.agent_id) == 10.0
        # Another failure stacks.
        front.record_invocation(a.agent_id, CostClass.HIGH, succeeded=False)
        assert front.tailwind_pressure(a.agent_id) == 20.0

    def test_record_invocation_cost_weights(self):
        front = FrontierLayer()
        a = make_ring3_agent("LLMJudge", ("x",))
        front.register(a)
        # LOW=1, MEDIUM=3, HIGH=10, CRITICAL=30
        for cc, w in [
            (CostClass.LOW, 1.0),
            (CostClass.MEDIUM, 3.0),
            (CostClass.HIGH, 10.0),
            (CostClass.CRITICAL, 30.0),
        ]:
            front.record_invocation(a.agent_id, cc, succeeded=False)
        assert front.tailwind_pressure(a.agent_id) == 1 + 3 + 10 + 30

    def test_invocations_history(self):
        front = FrontierLayer()
        a = make_ring3_agent("LLMJudge", ("x",))
        front.register(a)
        for i in range(5):
            front.record_invocation(a.agent_id, CostClass.LOW, succeeded=True)
        invs = front.invocations(n=10)
        assert len(invs) == 5
        assert all(inv["agent_id"] == a.agent_id for inv in invs)

    def test_invocations_filter_by_agent(self):
        front = FrontierLayer()
        a1 = make_ring3_agent("LLM1", ("x",))
        a2 = make_ring3_agent("LLM2", ("y",))
        front.register(a1)
        front.register(a2)
        front.record_invocation(a1.agent_id, CostClass.LOW, succeeded=True)
        front.record_invocation(a2.agent_id, CostClass.LOW, succeeded=False)
        invs_a1 = front.invocations(agent_id=a1.agent_id, n=10)
        assert len(invs_a1) == 1
        assert invs_a1[0]["agent_id"] == a1.agent_id


# ---------------------------------------------------------------------------
# ThreeRingGovernor tests
# ---------------------------------------------------------------------------


class TestThreeRingGovernor:
    def test_construction(self):
        fed, front, gov, tw = create_three_ring_governor()
        assert gov.federation is fed
        assert gov.frontier is front
        assert gov.tailwind is tw
        assert gov.audit_path() is None
        assert gov.summary()["decisions_in_log"] == 0

    def test_route_r2_match(self):
        fed, front, gov, _ = create_three_ring_governor()
        fed.register(make_ring2_agent("SearchBot", ("search",)))
        d = gov.route("search the web", required_capability="search")
        assert d.ring == RingLayer.FEDERATION
        assert d.needs_frontier is False
        assert d.capability_required == "search"
        assert d.cost_class == CostClass.LOW

    def test_route_r3_when_no_r2_match(self):
        fed, front, gov, _ = create_three_ring_governor()
        fed.register(make_ring2_agent("SearchBot", ("search",)))
        front.register(make_ring3_agent("LLMJudge", ("open_ended", "reasoning")))
        d = gov.route("open question", required_capability="open_ended")
        assert d.ring == RingLayer.FRONTIER
        assert d.needs_frontier is True
        assert d.agent_id != ""

    def test_route_r3_picks_lowest_cost(self):
        fed, front, gov, _ = create_three_ring_governor()
        front.register(make_ring3_agent("Hi", ("x",), cost_class=CostClass.HIGH))
        front.register(make_ring3_agent("Lo", ("x",), cost_class=CostClass.LOW))
        front.register(make_ring3_agent("Med", ("x",), cost_class=CostClass.MEDIUM))
        d = gov.route("test", required_capability="x")
        assert d.cost_class == CostClass.LOW

    def test_route_r3_refuses_when_no_match(self):
        fed, front, gov, _ = create_three_ring_governor()
        # R2 can't handle, R3 has no matching capability.
        d = gov.route("test", required_capability="open_ended")
        assert d.ring == RingLayer.FRONTIER
        assert d.agent_id == ""  # refused
        assert "no R3 agent matches" in d.rationale

    def test_route_empty_federation_refuses(self):
        # R2 is empty and the planner returns an empty plan; governor
        # refuses to route.
        fed, front, gov, _ = create_three_ring_governor()
        # Use a planner that always returns an empty plan.
        fed._planner_fn = lambda *args, **kw: StrategyPlan(
            request_id=args[0], steps=(), needs_frontier=False, rationale="empty"
        )
        d = gov.route("test", required_capability="x")
        assert d.agent_id == ""
        assert "R2 plan is empty" in d.rationale

    def test_route_race_deregistered_agent(self):
        # R2 plans for an agent, but it's deregistered before route.
        fed, front, gov, _ = create_three_ring_governor()
        a = make_ring2_agent("SearchBot", ("search",))
        fed.register(a)
        # Replace the planner with one that returns a plan referencing
        # a known-but-deregistered agent.
        def bad_planner(rid, agents, request, required_capability):
            return StrategyPlan(
                request_id=rid,
                steps=(("ghost", "search"),),
                needs_frontier=False,
                rationale="ghost",
            )
        fed._planner_fn = bad_planner
        d = gov.route("search", required_capability="search")
        assert d.agent_id == ""
        assert "no longer registered" in d.rationale

    def test_route_records_decision_in_log(self):
        fed, front, gov, _ = create_three_ring_governor()
        fed.register(make_ring2_agent("SearchBot", ("search",)))
        d1 = gov.route("search", required_capability="search")
        d2 = gov.route("search", required_capability="search")
        assert gov.decisions()[-1].request_id == d2.request_id
        assert gov.summary()["decisions_in_log"] == 2
        assert gov.summary()["ring_2_routes"] == 2
        assert gov.summary()["ring_3_routes"] == 0

    def test_record_frontier_outcome(self):
        fed, front, gov, _ = create_three_ring_governor()
        front.register(make_ring3_agent("LLMJudge", ("x",), cost_class=CostClass.HIGH))
        d = gov.route("test", required_capability="x")
        gov.record_frontier_outcome(d, succeeded=False)
        assert front.tailwind_pressure(d.agent_id) == 10.0

    def test_record_frontier_outcome_ignores_r2(self):
        # R2 outcomes are not tracked by the frontier tailwind.
        fed, front, gov, _ = create_three_ring_governor()
        fed.register(make_ring2_agent("SearchBot", ("search",)))
        d = gov.route("test", required_capability="search")
        before = front.tailwind_pressure()
        gov.record_frontier_outcome(d, succeeded=False)
        assert front.tailwind_pressure() == before

    def test_audit_trail_persists_to_disk(self):
        with tempfile.TemporaryDirectory() as td:
            fed, front, gov, _ = create_three_ring_governor(audit_path=td)
            fed.register(make_ring2_agent("SearchBot", ("search",)))
            gov.route("search", required_capability="search")
            p = Path(td) / "routing.jsonl"
            assert p.exists()
            lines = p.read_text().strip().split("\n")
            assert len(lines) == 1
            entry = json.loads(lines[0])
            assert entry["ring"] == RingLayer.FEDERATION.value
            assert entry["capability_required"] == "search"

    def test_summary_includes_all_substrate(self):
        with tempfile.TemporaryDirectory() as td:
            fed, front, gov, tw = create_three_ring_governor(audit_path=td)
            fed.register(make_ring2_agent("SearchBot", ("search",)))
            front.register(make_ring3_agent("LLM", ("x",)))
            gov.route("search", required_capability="search")
            gov.route("test", required_capability="x")
            s = gov.summary()
            assert s["federation_size"] == 1
            assert s["frontier_size"] == 1
            assert s["ring_2_routes"] == 1
            assert s["ring_3_routes"] == 1
            assert s["audit_path"] == td


# ---------------------------------------------------------------------------
# RoutingDecision tests
# ---------------------------------------------------------------------------


class TestRoutingDecision:
    def test_to_dict_round_trip(self):
        d = RoutingDecision(
            request_id="req_1",
            ring=RingLayer.FRONTIER,
            agent_id="r3_x",
            needs_frontier=True,
            rationale="test",
            capability_required="reasoning",
            permission_used=PermissionScope.READ,
            cost_class=CostClass.HIGH,
        )
        d2 = RoutingDecision.from_dict(d.to_dict())
        assert d2.request_id == "req_1"
        assert d2.ring == RingLayer.FRONTIER
        assert d2.cost_class == CostClass.HIGH
        assert d2.permission_used == PermissionScope.READ


# ---------------------------------------------------------------------------
# StrategyPlan tests
# ---------------------------------------------------------------------------


class TestStrategyPlan:
    def test_basic_plan(self):
        p = StrategyPlan(
            request_id="req_1",
            steps=(("a1", "search"),),
            needs_frontier=False,
            rationale="match",
        )
        assert p.steps[0][0] == "a1"

    def test_needs_frontier_requires_capability(self):
        with pytest.raises(ValueError, match="frontier_capability is None"):
            StrategyPlan(
                request_id="req_1",
                needs_frontier=True,
                frontier_capability=None,
            )


# ---------------------------------------------------------------------------
# CapabilityTailwind tests
# ---------------------------------------------------------------------------


class TestCapabilityTailwind:
    def test_empty_summary(self):
        tw = CapabilityTailwind()
        s = tw.summary()
        assert s["events_in_window"] == 0
        assert s["r3_escalation_rate"] == 0.0
        assert s["r3_failure_rate"] == 0.0
        assert s["recommendation"].startswith("OK")

    def test_recording_r3_increments(self):
        tw = CapabilityTailwind()
        tw.record(RingLayer.FRONTIER, CostClass.MEDIUM)
        tw.record(RingLayer.FRONTIER, CostClass.MEDIUM, succeeded=True)
        tw.record(RingLayer.FRONTIER, CostClass.MEDIUM, succeeded=False)
        s = tw.summary()
        assert s["events_in_window"] == 3
        assert s["r3_escalation_rate"] == 1.0
        assert s["r3_cost_distribution"][CostClass.MEDIUM.value] == 3
        assert s["r3_failure_rate"] == 0.5  # 1 fail / 2 with outcome

    def test_high_escalation_recommendation(self):
        tw = CapabilityTailwind()
        for _ in range(10):
            tw.record(RingLayer.FRONTIER, CostClass.LOW, succeeded=True)
        rec = tw.recommendation()
        assert "HIGH_ESCALATION" in rec

    def test_high_critical_cost_recommendation(self):
        tw = CapabilityTailwind()
        # Mix of R2 + R3 so escalation rate <= 50%, but a CRITICAL
        # R3 event was recorded.
        for _ in range(6):
            tw.record(RingLayer.FEDERATION, CostClass.LOW)
        tw.record(RingLayer.FRONTIER, CostClass.CRITICAL, succeeded=True)
        rec = tw.recommendation()
        assert "HIGH_CRITICAL_COST" in rec

    def test_high_failure_recommendation(self):
        tw = CapabilityTailwind()
        # Mix R2 + R3 so escalation rate <= 50%, but R3 failure > 30%.
        for _ in range(10):
            tw.record(RingLayer.FEDERATION, CostClass.LOW)
        for _ in range(4):
            tw.record(RingLayer.FRONTIER, CostClass.LOW, succeeded=False)
        for _ in range(6):
            tw.record(RingLayer.FRONTIER, CostClass.LOW, succeeded=True)
        rec = tw.recommendation()
        assert "HIGH_FAILURE_RATE" in rec

    def test_mixed_routes(self):
        tw = CapabilityTailwind()
        for _ in range(3):
            tw.record(RingLayer.FEDERATION, CostClass.LOW)
        for _ in range(2):
            tw.record(RingLayer.FRONTIER, CostClass.MEDIUM, succeeded=True)
        s = tw.summary()
        assert s["events_in_window"] == 5
        assert s["r3_escalation_rate"] == 0.4
        assert s["r3_failure_rate"] == 0.0


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------


class TestConvenienceConstructors:
    def test_make_ring2_agent_defaults(self):
        a = make_ring2_agent("Bot", ("search",))
        assert a.ring == RingLayer.FEDERATION
        assert a.deterministic is True
        assert a.cost_class == CostClass.LOW
        for p in a.permissions:
            assert p in R2_DEFAULT_PERMISSIONS
        assert PermissionScope.DELEGATE not in a.permissions
        assert PermissionScope.BROAD not in a.permissions

    def test_make_ring3_agent_defaults(self):
        a = make_ring3_agent("Bot", ("x",))
        assert a.ring == RingLayer.FRONTIER
        assert a.deterministic is False
        assert a.cost_class == CostClass.MEDIUM
        for p in R3_DEFAULT_PERMISSIONS:
            assert p in a.permissions
        assert PermissionScope.DELEGATE in a.permissions
        assert PermissionScope.BROAD in a.permissions

    def test_constructors_usable_with_governor(self):
        fed, front, gov, _ = create_three_ring_governor()
        a_r2 = make_ring2_agent("SearchBot", ("search",))
        a_r3 = make_ring3_agent("LLMJudge", ("reasoning",))
        fed.register(a_r2)
        front.register(a_r3)
        d_r2 = gov.route("search the web", required_capability="search")
        d_r3 = gov.route("open question", required_capability="reasoning")
        assert d_r2.ring == RingLayer.FEDERATION
        assert d_r3.ring == RingLayer.FRONTIER


# ---------------------------------------------------------------------------
# Conservative posture (the paper's macro invariants)
# ---------------------------------------------------------------------------


class TestConservativePosture:
    def test_r2_agents_cannot_be_in_frontier(self):
        # A Ring 2 agent must be deterministic; if you put it in the
        # frontier layer, the registration must fail.
        front = FrontierLayer()
        a = make_ring2_agent("SearchBot", ("search",))
        with pytest.raises(ValueError):
            front.register(a)

    def test_r3_agents_cannot_be_in_federation(self):
        # A Ring 3 agent must be non-deterministic; if you put it in
        # the federation layer, the registration must fail.
        fed = FederationLayer()
        a = make_ring3_agent("LLMJudge", ("reasoning",))
        with pytest.raises(ValueError):
            fed.register(a)

    def test_default_posture_prefers_r2(self):
        # When both rings have the capability, the governor routes to R2.
        fed, front, gov, _ = create_three_ring_governor()
        fed.register(make_ring2_agent("R2Bot", ("x",)))
        front.register(make_ring3_agent("R3Bot", ("x",)))
        d = gov.route("test", required_capability="x")
        assert d.ring == RingLayer.FEDERATION

    def test_frontier_escalation_only_when_r2_cant(self):
        # When only R3 has the capability, the governor routes to R3.
        fed, front, gov, _ = create_three_ring_governor()
        front.register(make_ring3_agent("R3Bot", ("x",)))
        d = gov.route("test", required_capability="x")
        assert d.ring == RingLayer.FRONTIER
        assert d.needs_frontier is True

    def test_failure_increases_tailwind_but_not_routes(self):
        # The tailwind_pressure is descriptive: a failed R3 call
        # increases the operator-visible metric but does NOT change
        # the routing policy. The paper's "more capable
        # non-deterministic actors produce larger consequences" is
        # recorded, not enforced.
        fed, front, gov, _ = create_three_ring_governor()
        front.register(make_ring3_agent("R3", ("x",), cost_class=CostClass.HIGH))
        d = gov.route("test", required_capability="x")
        gov.record_frontier_outcome(d, succeeded=False)
        # Second identical route goes the same way; tailwind is
        # descriptive, not enforced.
        d2 = gov.route("test", required_capability="x")
        assert d2.ring == RingLayer.FRONTIER
        assert front.tailwind_pressure() > 0

    def test_routing_decision_is_immutable_after_record(self):
        # A recorded RoutingDecision is not mutated by outcome
        # reporting.
        fed, front, gov, _ = create_three_ring_governor()
        front.register(make_ring3_agent("R3", ("x",), cost_class=CostClass.HIGH))
        d = gov.route("test", required_capability="x")
        decision_id = id(d)
        gov.record_frontier_outcome(d, succeeded=False)
        # Same object, same fields (in-memory).
        assert id(d) == decision_id
        assert d.ring == RingLayer.FRONTIER

    def test_governor_never_calls_r3_without_r2_planning(self):
        # If the federation layer is empty AND the request is for a
        # capability the planner_fn flags as needing frontier, the
        # governor must still go through the R2 planner first (the
        # conservative posture). We verify this by observing that
        # the federation's plan was recorded even when R3 was
        # ultimately selected.
        fed, front, gov, _ = create_three_ring_governor()
        front.register(make_ring3_agent("R3", ("x",)))
        d = gov.route("test", required_capability="x")
        # The R2 plan must have been recorded (even though the result
        # was to escalate).
        assert fed.plan_for(d.request_id) is not None
        assert fed.plan_for(d.request_id).needs_frontier is True
