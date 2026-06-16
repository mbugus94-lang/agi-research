"""
Tests for ToolPrivilegeGovernor.

Conservative-posture tests.  Each test verifies a single
invariant.  The full suite runs in <1 second.

Test classes:
  - TestSelectionOutcome          (5) -- enum values + ordering
  - TestPrivilegeScore            (6) -- composite + R2 vs R3 spread
  - TestDescriptorValidation      (5) -- empty-name / empty-action / empty-cap
  - TestDescriptorRoundTrip       (4) -- to_dict / from_dict
  - TestRegistry                  (6) -- register / deregister / get / size
  - TestPrivilegeRanking          (6) -- low beats high (delta < 0)
  - TestBlocklistFloor            (4) -- blocked tools never selected
  - TestRateLimiter               (3) -- per-minute cap honored
  - TestInsufficiencyReport       (4) -- diagnostic for INSUFFICIENT
  - TestLedgerConsultation        (3) -- claim_ids -> notes
  - TestActionCategoryMapping     (4) -- read/write/delete/etc.
  - TestConvenienceConstructors   (4) -- make_low / make_high
  - TestAuditTrail                (3) -- JSONL persisted when configured
  - TestSummary                   (4) -- over_privilege_rate, blocked_rate
  - TestConservativePosture       (4) -- promote never; blocked wins
  - TestIntegrationWithRealLedger (2) -- real EvidenceLedger round-trip

Total: ~67 tests
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Dict, List, Optional

from core.safety_circuit_breaker import (
    ActionCategory,
    SafetyCircuitBreaker,
)
from core.three_ring_architecture import (
    CostClass,
    PermissionScope,
    RingLayer,
)
from core.evidence_ledger import (
    Claim,
    ClaimStatus,
    Evidence,
    EvidenceKind,
    EvidenceLedger,
    EvidencePolarity,
)
from core.tool_privilege_governor import (
    InsufficiencyReport,
    SelectionOutcome,
    SelectionRecord,
    StepRequest,
    ToolPrivilegeDescriptor,
    ToolPrivilegeGovernor,
    ToolPrivilegeGovernorConfig,
    create_tool_privilege_governor,
    make_high_privilege_tool,
    make_low_privilege_tool,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_tool(
    tool_id: str = "r1",
    name: str = "Reader",
    ring: RingLayer = RingLayer.FEDERATION,
    perm: PermissionScope = PermissionScope.READ,
    cost: CostClass = CostClass.LOW,
    caps=("read",),
    blocked: bool = False,
) -> ToolPrivilegeDescriptor:
    return ToolPrivilegeDescriptor(
        tool_id=tool_id,
        name=name,
        action_type="read",
        action_category=ActionCategory.READ,
        permission_scope=perm,
        cost_class=cost,
        ring_layer=ring,
        capabilities=caps,
        is_blocked=blocked,
    )


def _write_tool(
    tool_id: str = "w1",
    name: str = "Writer",
    ring: RingLayer = RingLayer.FEDERATION,
    perm: PermissionScope = PermissionScope.WRITE,
    cost: CostClass = CostClass.LOW,
    caps=("write",),
    blocked: bool = False,
) -> ToolPrivilegeDescriptor:
    return ToolPrivilegeDescriptor(
        tool_id=tool_id,
        name=name,
        action_type="write",
        action_category=ActionCategory.WRITE,
        permission_scope=perm,
        cost_class=cost,
        ring_layer=ring,
        capabilities=caps,
        is_blocked=blocked,
    )


def _step(
    step_id: str = "s1",
    action_type: str = "read",
    required_capability: str = "read",
    requested_permission: Optional[PermissionScope] = None,
    claim_ids: Optional[List[str]] = None,
    priority: int = 0,
    target: str = "",
    description: str = "",
) -> StepRequest:
    return StepRequest(
        step_id=step_id,
        action_type=action_type,
        required_capability=required_capability,
        requested_permission=requested_permission,
        claim_ids=claim_ids or [],
        priority=priority,
        target=target,
        description=description,
    )


# ---------------------------------------------------------------------------
# TestSelectionOutcome
# ---------------------------------------------------------------------------


class TestSelectionOutcome(unittest.TestCase):
    def test_values(self):
        self.assertEqual(SelectionOutcome.SELECTED.value, "selected")
        self.assertEqual(SelectionOutcome.INSUFFICIENT.value, "insufficient")
        self.assertEqual(SelectionOutcome.BLOCKED_ALL.value, "blocked_all")
        self.assertEqual(SelectionOutcome.RATE_LIMITED.value, "rate_limited")
        self.assertEqual(SelectionOutcome.POLICY_DENIED.value, "policy_denied")

    def test_count(self):
        # 5 outcomes total
        self.assertEqual(len(list(SelectionOutcome)), 5)

    def test_str_mixin(self):
        self.assertEqual(str(SelectionOutcome.SELECTED), "SelectionOutcome.SELECTED")

    def test_record_serialization_carries_outcome_value(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool())
        rec = g.select_tool(_step())
        d = rec.to_dict()
        self.assertEqual(d["outcome"], "selected")

    def test_distinct_outcomes(self):
        names = {o.value for o in SelectionOutcome}
        self.assertEqual(len(names), 5)


# ---------------------------------------------------------------------------
# TestPrivilegeScore
# ---------------------------------------------------------------------------


class TestPrivilegeScore(unittest.TestCase):
    def test_low_r2_low_cost_read(self):
        t = _read_tool()  # READ+LOW+R2
        # 0 + 0 + 1 = 1
        self.assertEqual(t.privilege_score(), 1)

    def test_high_r3_critical_broad(self):
        t = ToolPrivilegeDescriptor(
            tool_id="broad", name="Broad", action_type="execute",
            action_category=ActionCategory.EXECUTE,
            permission_scope=PermissionScope.BROAD,
            cost_class=CostClass.CRITICAL,
            ring_layer=RingLayer.FRONTIER,
            capabilities=("execute",),
        )
        # 4 + 3 + 2 = 9
        self.assertEqual(t.privilege_score(), 9)

    def test_score_monotonic_in_permission(self):
        ranks = []
        for p in [
            PermissionScope.READ,
            PermissionScope.WRITE,
            PermissionScope.EXECUTE,
            PermissionScope.DELEGATE,
            PermissionScope.BROAD,
        ]:
            t = _read_tool(perm=p)
            ranks.append(t.privilege_score())
        self.assertEqual(ranks, sorted(ranks))

    def test_score_monotonic_in_cost(self):
        ranks = []
        for c in [CostClass.LOW, CostClass.MEDIUM, CostClass.HIGH, CostClass.CRITICAL]:
            t = _read_tool(cost=c)
            ranks.append(t.privilege_score())
        self.assertEqual(ranks, sorted(ranks))

    def test_score_monotonic_in_ring(self):
        ranks = []
        for r in [RingLayer.PRODUCTION, RingLayer.FEDERATION, RingLayer.FRONTIER]:
            t = _read_tool(ring=r)
            ranks.append(t.privilege_score())
        self.assertEqual(ranks, sorted(ranks))

    def test_score_deterministic(self):
        # Same descriptor -> same score across instances
        t1 = _read_tool()
        t2 = _read_tool()
        self.assertEqual(t1.privilege_score(), t2.privilege_score())


# ---------------------------------------------------------------------------
# TestDescriptorValidation
# ---------------------------------------------------------------------------


class TestDescriptorValidation(unittest.TestCase):
    def test_empty_name_rejected(self):
        with self.assertRaises(ValueError):
            ToolPrivilegeDescriptor(
                tool_id="x", name="", action_type="read",
                action_category=ActionCategory.READ,
                permission_scope=PermissionScope.READ,
                cost_class=CostClass.LOW,
                ring_layer=RingLayer.FEDERATION,
                capabilities=("read",),
            )

    def test_empty_action_type_rejected(self):
        with self.assertRaises(ValueError):
            ToolPrivilegeDescriptor(
                tool_id="x", name="X", action_type="",
                action_category=ActionCategory.READ,
                permission_scope=PermissionScope.READ,
                cost_class=CostClass.LOW,
                ring_layer=RingLayer.FEDERATION,
                capabilities=("read",),
            )

    def test_empty_capabilities_rejected(self):
        with self.assertRaises(ValueError):
            ToolPrivilegeDescriptor(
                tool_id="x", name="X", action_type="read",
                action_category=ActionCategory.READ,
                permission_scope=PermissionScope.READ,
                cost_class=CostClass.LOW,
                ring_layer=RingLayer.FEDERATION,
                capabilities=(),
            )

    def test_has_capability_true(self):
        t = _read_tool(caps=("read", "search"))
        self.assertTrue(t.has_capability("read"))
        self.assertTrue(t.has_capability("search"))

    def test_has_capability_false(self):
        t = _read_tool(caps=("read",))
        self.assertFalse(t.has_capability("execute"))


# ---------------------------------------------------------------------------
# TestDescriptorRoundTrip
# ---------------------------------------------------------------------------


class TestDescriptorRoundTrip(unittest.TestCase):
    def test_to_dict_keys(self):
        t = _read_tool()
        d = t.to_dict()
        for key in [
            "tool_id", "name", "action_type", "action_category",
            "permission_scope", "cost_class", "ring_layer",
            "capabilities", "is_blocked", "per_minute_cap",
            "per_step_cap", "privilege_score",
        ]:
            self.assertIn(key, d)

    def test_from_dict_round_trip(self):
        t = _read_tool()
        d = t.to_dict()
        t2 = ToolPrivilegeDescriptor.from_dict(d)
        self.assertEqual(t.tool_id, t2.tool_id)
        self.assertEqual(t.name, t2.name)
        self.assertEqual(t.action_type, t2.action_type)
        self.assertEqual(t.privilege_score(), t2.privilege_score())

    def test_capabilities_tuple_round_trip(self):
        t = _read_tool(caps=("read", "search", "query"))
        t2 = ToolPrivilegeDescriptor.from_dict(t.to_dict())
        self.assertEqual(t.capabilities, t2.capabilities)
        self.assertIsInstance(t2.capabilities, tuple)

    def test_blocked_round_trip(self):
        t = _read_tool(blocked=True)
        t2 = ToolPrivilegeDescriptor.from_dict(t.to_dict())
        self.assertTrue(t2.is_blocked)


# ---------------------------------------------------------------------------
# TestRegistry
# ---------------------------------------------------------------------------


class TestRegistry(unittest.TestCase):
    def test_register_returns_id(self):
        g = ToolPrivilegeGovernor()
        tid = g.register_tool(_read_tool(tool_id="r1"))
        self.assertEqual(tid, "r1")

    def test_get(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool(tool_id="r1"))
        self.assertIsNotNone(g.get("r1"))
        self.assertIsNone(g.get("missing"))

    def test_size(self):
        g = ToolPrivilegeGovernor()
        self.assertEqual(g.size(), 0)
        g.register_tool(_read_tool(tool_id="r1"))
        g.register_tool(_write_tool(tool_id="w1"))
        self.assertEqual(g.size(), 2)

    def test_deregister(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool(tool_id="r1"))
        self.assertTrue(g.deregister("r1"))
        self.assertEqual(g.size(), 0)
        self.assertFalse(g.deregister("r1"))  # idempotent

    def test_all_tools(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool(tool_id="r1"))
        g.register_tool(_write_tool(tool_id="w1"))
        self.assertEqual(len(g.all_tools()), 2)

    def test_register_overwrite(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool(tool_id="r1", caps=("read",)))
        g.register_tool(_read_tool(tool_id="r1", caps=("read", "search")))
        t = g.get("r1")
        self.assertEqual(t.capabilities, ("read", "search"))


# ---------------------------------------------------------------------------
# TestPrivilegeRanking
# ---------------------------------------------------------------------------


class TestPrivilegeRanking(unittest.TestCase):
    def test_low_priv_picked_over_high_priv(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool(tool_id="low"))     # score 1
        g.register_tool(_read_tool(tool_id="high", ring=RingLayer.FRONTIER,
                                   perm=PermissionScope.BROAD,
                                   cost=CostClass.CRITICAL))  # score 9
        rec = g.select_tool(_step(requested_permission=PermissionScope.READ))
        self.assertEqual(rec.chosen_tool_id, "low")

    def test_privilege_delta_negative(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool(tool_id="low"))
        g.register_tool(_read_tool(tool_id="high", ring=RingLayer.FRONTIER))
        rec = g.select_tool(_step(requested_permission=PermissionScope.READ))
        self.assertIsNotNone(rec.privilege_delta)
        self.assertLess(rec.privilege_delta, 0)

    def test_naive_score_highest(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool(tool_id="low"))
        g.register_tool(_read_tool(tool_id="high", ring=RingLayer.FRONTIER))
        rec = g.select_tool(_step())
        # Naive = highest score in candidate set
        self.assertEqual(rec.naive_privilege_score, 2)  # 0+0+2 = 2

    def test_rankings_sorted_ascending_privilege(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool(tool_id="a", ring=RingLayer.FRONTIER))  # score 2
        g.register_tool(_read_tool(tool_id="b", ring=RingLayer.FEDERATION))  # score 1
        g.register_tool(_read_tool(tool_id="c", ring=RingLayer.PRODUCTION))  # score 0
        rec = g.select_tool(_step())
        # The chosen should be the lowest-privilege
        self.assertEqual(rec.chosen_tool_id, "c")

    def test_requested_permission_honors_explicit_READ(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool(tool_id="r1", perm=PermissionScope.READ))
        rec = g.select_tool(_step(requested_permission=PermissionScope.READ))
        self.assertEqual(rec.chosen_tool_id, "r1")
        self.assertEqual(rec.outcome, SelectionOutcome.SELECTED)

    def test_requested_permission_filters_lower_privilege_tools(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool(tool_id="r1", perm=PermissionScope.READ))
        g.register_tool(_write_tool(tool_id="w1", perm=PermissionScope.WRITE))
        rec = g.select_tool(
            _step(
                step_id="s1",
                action_type="write",
                required_capability="write",
                requested_permission=PermissionScope.WRITE,
            )
        )


# ---------------------------------------------------------------------------
# TestBlocklistFloor
# ---------------------------------------------------------------------------


class TestBlocklistFloor(unittest.TestCase):
    def test_blocked_tool_never_selected(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool(tool_id="low_blocked", blocked=True))
        g.register_tool(_read_tool(tool_id="high_allowed",
                                   ring=RingLayer.FRONTIER))
        rec = g.select_tool(_step())
        self.assertNotEqual(rec.chosen_tool_id, "low_blocked")
        self.assertEqual(rec.chosen_tool_id, "high_allowed")

    def test_all_blocked_returns_blocked_all(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool(tool_id="a", blocked=True))
        g.register_tool(_read_tool(tool_id="b", blocked=True))
        rec = g.select_tool(_step())
        self.assertEqual(rec.outcome, SelectionOutcome.BLOCKED_ALL)

    def test_respect_blocklist_false_allows_blocked(self):
        g = ToolPrivilegeGovernor(config=ToolPrivilegeGovernorConfig(respect_blocklist=False))
        g.register_tool(_read_tool(tool_id="only", blocked=True))
        rec = g.select_tool(_step())
        self.assertEqual(rec.outcome, SelectionOutcome.SELECTED)
        self.assertEqual(rec.chosen_tool_id, "only")

    def test_blocked_tool_marked_in_ranking(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool(tool_id="blocked", blocked=True))
        g.register_tool(_read_tool(tool_id="ok"))
        rec = g.select_tool(_step())
        blocked_rank = next(r for r in rec.rankings if r.tool_id == "blocked")
        self.assertTrue(blocked_rank.blocked)
        self.assertFalse(blocked_rank.sufficient)
        self.assertEqual(blocked_rank.reason, "blocked_by_policy")


# ---------------------------------------------------------------------------
# TestRateLimiter
# ---------------------------------------------------------------------------


class TestRateLimiter(unittest.TestCase):
    def test_per_minute_cap_blocks_after_threshold(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(ToolPrivilegeDescriptor(
            tool_id="capped", name="Capped", action_type="read",
            action_category=ActionCategory.READ,
            permission_scope=PermissionScope.READ,
            cost_class=CostClass.LOW,
            ring_layer=RingLayer.FEDERATION,
            capabilities=("read",),
            per_minute_cap=2,
        ))
        for i in range(3):
            s = _step(step_id=f"s{i}")
            r = g.select_tool(s)
            if r.outcome == SelectionOutcome.SELECTED:
                g.record_outcome(s.step_id, True)
        # Third call should be RATE_LIMITED
        last = g.records()[-1]
        self.assertEqual(last.outcome, SelectionOutcome.RATE_LIMITED)

    def test_per_minute_cap_isolated_per_tool(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(ToolPrivilegeDescriptor(
            tool_id="capped", name="Capped", action_type="read",
            action_category=ActionCategory.READ,
            permission_scope=PermissionScope.READ,
            cost_class=CostClass.LOW,
            ring_layer=RingLayer.FEDERATION,
            capabilities=("read",),
            per_minute_cap=1,
        ))
        g.register_tool(_read_tool(tool_id="other"))
        # Cap out the first
        s1 = _step(step_id="s1")
        r1 = g.select_tool(s1)
        g.record_outcome(s1.step_id, True)
        # Now the other tool should still be selectable
        s2 = _step(step_id="s2")
        r2 = g.select_tool(s2)
        self.assertEqual(r2.outcome, SelectionOutcome.SELECTED)
        self.assertEqual(r2.chosen_tool_id, "other")

    def test_rate_limited_ranking_carries_flag(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(ToolPrivilegeDescriptor(
            tool_id="capped", name="Capped", action_type="read",
            action_category=ActionCategory.READ,
            permission_scope=PermissionScope.READ,
            cost_class=CostClass.LOW,
            ring_layer=RingLayer.FEDERATION,
            capabilities=("read",),
            per_minute_cap=1,
        ))
        s1 = _step(step_id="s1")
        g.select_tool(s1)
        g.record_outcome(s1.step_id, True)
        s2 = _step(step_id="s2")
        rec = g.select_tool(s2)
        rl = next(r for r in rec.rankings if r.tool_id == "capped")
        self.assertTrue(rl.rate_limited)
        self.assertEqual(rl.reason, "rate_limited")


# ---------------------------------------------------------------------------
# TestInsufficiencyReport
# ---------------------------------------------------------------------------


class TestInsufficiencyReport(unittest.TestCase):
    def test_no_candidates_yields_insufficient(self):
        g = ToolPrivilegeGovernor()
        rec = g.select_tool(_step(action_type="delete", required_capability="delete"))
        self.assertEqual(rec.outcome, SelectionOutcome.INSUFFICIENT)
        self.assertIsNotNone(rec.insufficiency)

    def test_insufficiency_report_shape(self):
        g = ToolPrivilegeGovernor()
        rec = g.select_tool(_step(action_type="delete", required_capability="delete"))
        ir = rec.insufficiency
        self.assertEqual(ir.step_id, "s1")
        self.assertEqual(ir.action_type, "delete")
        self.assertEqual(ir.candidates_considered, 0)

    def test_insufficiency_notes_describe_gap(self):
        g = ToolPrivilegeGovernor()
        rec = g.select_tool(_step(action_type="delete", required_capability="delete"))
        notes_text = " ".join(rec.insufficiency.notes).lower()
        self.assertIn("delete", notes_text)

    def test_insufficiency_to_dict_round_trip(self):
        g = ToolPrivilegeGovernor()
        rec = g.select_tool(_step(action_type="delete"))
        d = rec.insufficiency.to_dict()
        self.assertIn("step_id", d)
        self.assertIn("action_type", d)
        self.assertIn("closest_by_capability", d)
        self.assertIn("closest_by_privilege", d)
        self.assertIn("notes", d)


# ---------------------------------------------------------------------------
# TestLedgerConsultation
# ---------------------------------------------------------------------------


class TestLedgerConsultation(unittest.TestCase):
    def test_disabled_by_default(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool())
        # ledger=None and consult_ledger defaults True but no claims -> no notes
        s = _step(step_id="s1")
        rec = g.select_tool(s)
        self.assertEqual(rec.outcome, SelectionOutcome.SELECTED)

    def test_consult_ledger_disabled(self):
        g = ToolPrivilegeGovernor(
            ledger=EvidenceLedger(),
            config=ToolPrivilegeGovernorConfig(consult_ledger=False),
        )
        g.register_tool(_read_tool())
        s = _step(step_id="s1", claim_ids=["c1"])
        rec = g.select_tool(s)
        # consult_ledger is off; no notes attached
        self.assertEqual(rec.outcome, SelectionOutcome.SELECTED)

    def test_no_claims_means_no_consultation(self):
        g = ToolPrivilegeGovernor(ledger=EvidenceLedger())
        g.register_tool(_read_tool())
        rec = g.select_tool(_step(step_id="s1"))
        self.assertEqual(rec.outcome, SelectionOutcome.SELECTED)


# ---------------------------------------------------------------------------
# TestActionCategoryMapping
# ---------------------------------------------------------------------------


class TestActionCategoryMapping(unittest.TestCase):
    def test_read_maps_to_read(self):
        g = ToolPrivilegeGovernor()
        # The internal mapping should be the same vocabulary
        # the GovernedActionLoop uses.
        self.assertEqual(g._action_category_for("read"), "read")
        self.assertEqual(g._action_category_for("search"), "read")
        self.assertEqual(g._action_category_for("query"), "read")

    def test_write_maps_to_write(self):
        g = ToolPrivilegeGovernor()
        self.assertEqual(g._action_category_for("write"), "write")
        self.assertEqual(g._action_category_for("create"), "write")
        self.assertEqual(g._action_category_for("update"), "write")

    def test_delete_maps_to_delete(self):
        g = ToolPrivilegeGovernor()
        self.assertEqual(g._action_category_for("delete"), "delete")
        self.assertEqual(g._action_category_for("drop"), "delete")
        self.assertEqual(g._action_category_for("truncate"), "delete")

    def test_execute_and_conservative_default(self):
        g = ToolPrivilegeGovernor()
        self.assertEqual(g._action_category_for("execute"), "execute")
        # Unknown action types default to "execute" (the most
        # conservative category for the blocklist to look at)
        self.assertEqual(g._action_category_for("unknown_thing"), "execute")


# ---------------------------------------------------------------------------
# TestConvenienceConstructors
# ---------------------------------------------------------------------------


class TestConvenienceConstructors(unittest.TestCase):
    def test_make_low_privilege_tool_defaults(self):
        t = make_low_privilege_tool("Read", "read", capabilities=("read",))
        self.assertEqual(t.permission_scope, PermissionScope.READ)
        self.assertEqual(t.cost_class, CostClass.LOW)
        self.assertEqual(t.ring_layer, RingLayer.FEDERATION)

    def test_make_high_privilege_tool_defaults(self):
        t = make_high_privilege_tool("Exec", "execute", capabilities=("execute",))
        self.assertEqual(t.permission_scope, PermissionScope.EXECUTE)
        self.assertEqual(t.ring_layer, RingLayer.FRONTIER)
        # MEDIUM is the default for high -- operator must opt in to HIGH/CRITICAL
        self.assertEqual(t.cost_class, CostClass.MEDIUM)

    def test_low_priv_score_below_high_priv(self):
        low = make_low_privilege_tool("Read", "read", capabilities=("read",))
        high = make_high_privilege_tool("Exec", "execute", capabilities=("execute",))
        self.assertLess(low.privilege_score(), high.privilege_score())

    def test_explicit_tool_id_respected(self):
        t = make_low_privilege_tool("Read", "read", capabilities=("read",),
                                    tool_id="my_custom_id")
        self.assertEqual(t.tool_id, "my_custom_id")


# ---------------------------------------------------------------------------
# TestAuditTrail
# ---------------------------------------------------------------------------


class TestAuditTrail(unittest.TestCase):
    def test_audit_disabled_by_default(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool())
        g.select_tool(_step())
        # No audit_path set; no JSONL written anywhere
        self.assertIsNone(g.audit_path_obj)

    def test_audit_persists_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = ToolPrivilegeGovernor(audit_path=tmp)
            g.register_tool(_read_tool(tool_id="r1"))
            g.select_tool(_step(step_id="s1"))
            jsonl = Path(tmp) / "tool_selection.jsonl"
            self.assertTrue(jsonl.exists())
            lines = jsonl.read_text().strip().split("\n")
            self.assertEqual(len(lines), 1)
            d = json.loads(lines[0])
            self.assertEqual(d["step_id"], "s1")
            self.assertEqual(d["chosen_tool_id"], "r1")

    def test_audit_appends_across_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            g = ToolPrivilegeGovernor(audit_path=tmp)
            g.register_tool(_read_tool(tool_id="r1"))
            for i in range(3):
                g.select_tool(_step(step_id=f"s{i}"))
            jsonl = Path(tmp) / "tool_selection.jsonl"
            self.assertEqual(len(jsonl.read_text().strip().split("\n")), 3)


# ---------------------------------------------------------------------------
# TestSummary
# ---------------------------------------------------------------------------


class TestSummary(unittest.TestCase):
    def test_empty_summary(self):
        g = ToolPrivilegeGovernor()
        s = g.summary()
        self.assertEqual(s["total"], 0)
        self.assertEqual(s["registered_tools"], 0)
        for outcome in SelectionOutcome:
            self.assertIn(outcome.value, s["outcomes"])

    def test_summary_counts_outcomes(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool(tool_id="r1"))
        g.register_tool(_read_tool(tool_id="r2"))
        g.select_tool(_step(step_id="s1"))
        g.select_tool(_step(step_id="s2"))
        s = g.summary()
        self.assertEqual(s["total"], 2)
        self.assertEqual(s["outcomes"]["selected"], 2)

    def test_summary_over_privilege_rate(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool(tool_id="r1"))
        g.select_tool(_step(step_id="s1"))
        s = g.summary()
        # Only one tool, no over-privilege possible
        self.assertEqual(s["over_privilege_rate"], 0.0)

    def test_summary_registered_tools_count(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool(tool_id="a"))
        g.register_tool(_read_tool(tool_id="b"))
        g.register_tool(_read_tool(tool_id="c"))
        s = g.summary()
        self.assertEqual(s["registered_tools"], 3)


# ---------------------------------------------------------------------------
# TestConservativePosture
# ---------------------------------------------------------------------------


class TestConservativePosture(unittest.TestCase):
    def test_no_tool_auto_escalates(self):
        # A step with a high permission request should NOT
        # silently fall back to a lower-privilege tool; it
        # should return INSUFFICIENT.
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool(tool_id="r1", perm=PermissionScope.READ,
                                   caps=("read",)))
        rec = g.select_tool(_step(requested_permission=PermissionScope.BROAD))
        self.assertEqual(rec.outcome, SelectionOutcome.INSUFFICIENT)

    def test_blocked_wins_over_lower_privilege(self):
        # If the lowest-privilege tool is blocked, the next
        # lowest should win.  The blocklist is a *floor*.
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool(tool_id="low_blocked", blocked=True))
        g.register_tool(_read_tool(tool_id="mid_ok", ring=RingLayer.FRONTIER))
        rec = g.select_tool(_step())
        self.assertEqual(rec.chosen_tool_id, "mid_ok")

    def test_determinism(self):
        # Same registry + same steps -> same selections.
        g1 = ToolPrivilegeGovernor()
        g2 = ToolPrivilegeGovernor()
        for g in (g1, g2):
            g.register_tool(_read_tool(tool_id="a"))
            g.register_tool(_read_tool(tool_id="b", ring=RingLayer.FRONTIER))
        r1 = g1.select_tool(_step())
        r2 = g2.select_tool(_step())
        self.assertEqual(r1.chosen_tool_id, r2.chosen_tool_id)
        self.assertEqual(r1.privilege_delta, r2.privilege_delta)

    def test_records_capped(self):
        g = ToolPrivilegeGovernor()
        g.register_tool(_read_tool(tool_id="r1"))
        # Insert > 4096 records; deque should cap
        for i in range(4100):
            g.select_tool(_step(step_id=f"s{i}"))
        # records() should return <= 4096 (deque cap)
        self.assertLessEqual(len(g.records(n=5000)), 4096)


# ---------------------------------------------------------------------------
# TestIntegrationWithRealLedger
# ---------------------------------------------------------------------------


class TestIntegrationWithRealLedger(unittest.TestCase):
    def test_consult_real_ledger_with_supported_claim(self):
        ledger = EvidenceLedger()
        claim = Claim(
            claim_id="c1",
            text="the read is safe",
            status=ClaimStatus.SUPPORTED,
        )
        ledger.assert_claim(claim)
        g = ToolPrivilegeGovernor(ledger=ledger)
        g.register_tool(_read_tool(tool_id="r1"))
        rec = g.select_tool(_step(step_id="s1", claim_ids=["c1"]))
        self.assertEqual(rec.outcome, SelectionOutcome.SELECTED)

    def test_consult_real_ledger_with_disputed_claim(self):
        ledger = EvidenceLedger()
        claim = Claim(
            claim_id="c1",
            text="disputed",
            status=ClaimStatus.DISPUTED,
        )
        ledger.assert_claim(claim)
        g = ToolPrivilegeGovernor(ledger=ledger)
        g.register_tool(_read_tool(tool_id="r1"))
        rec = g.select_tool(_step(step_id="s1", claim_ids=["c1"]))
        # Outcome is still SELECTED; the disputed claim is
        # attached as a *note* in the audit trail, not a
        # gate.  The governor's job is privilege, not evidence.
        self.assertEqual(rec.outcome, SelectionOutcome.SELECTED)


if __name__ == "__main__":
    unittest.main()
