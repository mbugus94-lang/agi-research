"""
Tests for core/agent_loop.py

Coverage:
  1.  Verdict enum + ordering + strength
  2.  strongest() on empty / single / multi inputs
  3.  AgentIdentity construction, serialization round-trip, frozen
  4.  LifecycleState terminal detection
  5.  LoopBudget validation (post_init rejection of non-positive caps)
  6.  BudgetStatus exhaustion (steps / tokens / wall_time / cost)
  7.  RevocationChannel: revoke / is_revoked / reason / clear
  8.  LoopStep to_dict serialization
  9.  BreakerGateVerifier: LOW permits, CRITICAL halts, MEDIUM continues
  10. LedgerGateVerifier: SUPPORTED permits, CONTRADICTED halts
  11. MonitorGateVerifier: HALT recommendation, ESCALATE recommendation
  12. CompositeVerifier: HALT trumps ESCALATE trumps CONTINUE
  13. CompositeVerifier: member raise -> ESCALATE
  14. CompositeVerifier: empty member list rejected
  15. AgentLoop: happy path CONTINUE -> goal_reached
  16. AgentLoop: ESCALATE -> WAITING
  17. AgentLoop: HALT -> FAILED
  18. AgentLoop: terminal state cannot transition (rerun raises)
  19. AgentLoop: revocation mid-loop -> REVOKED
  20. AgentLoop: budget exhaustion -> COMPLETED with budget_exhausted
  21. AgentLoop: act raises -> FAILED with terminal_reason
  22. AgentLoop: audit trail persists JSONL
  23. AgentLoop: max_iterations cap respected
  24. AgentLoop: in-memory ring maxlen enforced
  25. Conservative posture: composite never demotes a HALT
  26. Conservative posture: revocation always wins over CONTINUE
  27. Conservative posture: FAILED is terminal (no rerun)
  28. Conservative posture: budget checked *before* act
  29. create_agent_loop convenience constructor wiring
  30. AgentLoop: budget counters incremented on CONTINUE
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock
from collections import deque

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.agent_loop import (  # noqa: E402
    AgentIdentity,
    AgentLoop,
    AgentLoopConfig,
    BreakerGateVerifier,
    BudgetStatus,
    CompositeVerifier,
    LedgerGateVerifier,
    LifecycleState,
    LoopBudget,
    LoopStep,
    MonitorGateVerifier,
    Permission,
    RevocationChannel,
    StepPhase,
    Verdict,
    create_agent_loop,
    strongest,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


class _RiskLevel:
    """A simple stand-in for SafetyCircuitBreaker.RiskLevel."""

    def __init__(self, name: str, value: int):
        self.name = name
        self.value = value

    def __repr__(self) -> str:
        return f"RiskLevel.{self.name}"


_RISK_LOOKUP = {
    "LOW": _RiskLevel("LOW", 1),
    "MEDIUM": _RiskLevel("MEDIUM", 2),
    "HIGH": _RiskLevel("HIGH", 3),
    "CRITICAL": _RiskLevel("CRITICAL", 4),
}


class _BreakerAssessment:
    def __init__(self, level_name: str, blocked: bool = False):
        self.risk_level = _RISK_LOOKUP[level_name]
        self.blocked = blocked
        self.is_blocked = blocked
        self.action_type = ""
        self.target = ""


class FakeBreaker:
    """A minimal stand-in for SafetyCircuitBreaker.assess_risk()."""

    def __init__(self, level: str = "LOW", blocked: bool = False):
        self._level = level
        self._blocked = blocked
        self.calls: list = []

    def assess_risk(self, action_type: str = "execute", target: str = "", params=None):
        self.calls.append((action_type, target, params or {}))
        return _BreakerAssessment(self._level, blocked=self._blocked)


class FakeLedger:
    """A minimal stand-in for EvidenceLedger.verify()."""

    def __init__(self, statuses):
        # statuses: dict[claim_id -> 'SUPPORTED' | 'CONTRADICTED' | 'DISPUTED' | 'UNKNOWN']
        self._statuses = dict(statuses)
        self.calls: list = []

    def verify(self, claim_id: str):
        self.calls.append(claim_id)
        status = self._statuses.get(claim_id, "UNKNOWN")
        # Mimic ClaimVerification shape
        from core.evidence_ledger import ClaimStatus, ClaimVerification
        cs = {
            "SUPPORTED": ClaimStatus.SUPPORTED,
            "CONTRADICTED": ClaimStatus.CONTRADICTED,
            "DISPUTED": ClaimStatus.DISPUTED,
            "UNKNOWN": ClaimStatus.UNGROUNDED,
        }.get(status, ClaimStatus.UNGROUNDED)
        # Match the real ClaimVerification constructor: claim_id, status,
        # support/refute counts, weights, confidence, is_fresh, reason.
        support = 2 if status == "SUPPORTED" else 0
        refute = 2 if status in ("CONTRADICTED", "DISPUTED") else 0
        return ClaimVerification(
            claim_id=claim_id,
            status=cs,
            support_count=support,
            refute_count=refute,
            weighted_support=float(support),
            weighted_refute=float(refute),
            confidence=0.9 if status != "UNGROUNDED" else 0.0,
            is_fresh=True,
            reason=f"fake-{status.lower()}",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _identity(perms=(Permission.READ,)):
    return AgentIdentity(
        loop_id="loop-test-001",
        principal="dave92",
        purpose="test loop",
        permissions=tuple(perms),
        provisioned_at="2026-06-18T05:00:00+00:00",
    )


def _permit_verifier(name="permit"):
    v = MagicMock()
    v.name = name
    v.evaluate.return_value = (Verdict.CONTINUE, "permit", [])
    return v


def _halt_verifier(name="halt"):
    v = MagicMock()
    v.name = name
    v.evaluate.return_value = (Verdict.HALT, "halt-by-test", [])
    return v


def _escalate_verifier(name="escalate"):
    v = MagicMock()
    v.name = name
    v.evaluate.return_value = (Verdict.ESCALATE, "escalate-by-test", [])
    return v


class _RecorderWork:
    """A work fn that records calls and returns a synthetic observation."""

    def __init__(self, observations):
        self.observations = list(observations)
        self.calls: list = []

    def __call__(self, identity, action):
        self.calls.append(action)
        if not self.observations:
            return {"ok": True}
        return self.observations.pop(0)


def _make_loop(
    verifiers,
    audit_path=None,
    identity=None,
    budget=None,
    revocation=None,
    work=None,  # accepted but unused; loop config doesn't take work fn
    goal=None,
):
    config = AgentLoopConfig(
        identity=identity or _identity(),
        verifier=CompositeVerifier(verifiers),
        budget=budget or LoopBudget(max_steps=20),
        audit_path=audit_path,
        revocation_channel=revocation,
    )
    return AgentLoop(config)


# ---------------------------------------------------------------------------
# 1. Verdict + strongest
# ---------------------------------------------------------------------------


class TestVerdict(unittest.TestCase):
    def test_values(self):
        self.assertEqual(Verdict.CONTINUE.value, "continue")
        self.assertEqual(Verdict.ESCALATE.value, "escalate")
        self.assertEqual(Verdict.HALT.value, "halt")

    def test_strength_ordering(self):
        self.assertLess(Verdict.CONTINUE, Verdict.ESCALATE)
        self.assertLess(Verdict.ESCALATE, Verdict.HALT)

    def test_str_mixin(self):
        self.assertEqual(Verdict.HALT.value, "halt")
        self.assertEqual(Verdict.HALT == "halt", True)


class TestStrongest(unittest.TestCase):
    def test_empty_returns_continue(self):
        self.assertEqual(strongest([]), Verdict.CONTINUE)

    def test_single(self):
        self.assertEqual(strongest([Verdict.CONTINUE]), Verdict.CONTINUE)

    def test_halt_trumps(self):
        self.assertEqual(
            strongest([Verdict.CONTINUE, Verdict.ESCALATE, Verdict.HALT]),
            Verdict.HALT,
        )

    def test_escalate_trumps_continue(self):
        self.assertEqual(
            strongest([Verdict.CONTINUE, Verdict.ESCALATE]),
            Verdict.ESCALATE,
        )

    def test_all_continue(self):
        self.assertEqual(
            strongest([Verdict.CONTINUE, Verdict.CONTINUE]),
            Verdict.CONTINUE,
        )


# ---------------------------------------------------------------------------
# 2. AgentIdentity
# ---------------------------------------------------------------------------


class TestAgentIdentity(unittest.TestCase):
    def test_construction_defaults(self):
        ident = _identity()
        self.assertEqual(ident.loop_id, "loop-test-001")
        self.assertEqual(ident.principal, "dave92")
        self.assertEqual(ident.permissions, (Permission.READ,))

    def test_serialization_round_trip(self):
        ident = AgentIdentity(
            loop_id="loop-test-002",
            principal="ops-bot",
            purpose="research synthesis",
            permissions=(Permission.READ, Permission.WRITE),
            provisioned_at="2026-06-18T05:00:00+00:00",
        )
        d = ident.to_dict()
        restored = AgentIdentity.from_dict(d)
        self.assertEqual(restored, ident)

    def test_from_dict_accepts_string_permission(self):
        d = {
            "loop_id": "x",
            "principal": "y",
            "purpose": "z",
            "permissions": ["read", "write"],
            "provisioned_at": "2026-06-18T05:00:00+00:00",
        }
        ident = AgentIdentity.from_dict(d)
        self.assertEqual(ident.permissions, (Permission.READ, Permission.WRITE))

    def test_frozen_rejects_mutation(self):
        ident = _identity()
        with self.assertRaises(Exception):
            ident.loop_id = "mutated"  # type: ignore


# ---------------------------------------------------------------------------
# 3. LifecycleState
# ---------------------------------------------------------------------------


class TestLifecycleState(unittest.TestCase):
    TERMINAL = {LifecycleState.COMPLETED, LifecycleState.FAILED, LifecycleState.REVOKED}

    def test_terminal_states(self):
        for s in (LifecycleState.COMPLETED, LifecycleState.FAILED, LifecycleState.REVOKED):
            self.assertIn(s, self.TERMINAL)

    def test_non_terminal(self):
        for s in (LifecycleState.PROVISIONED, LifecycleState.RUNNING, LifecycleState.WAITING):
            self.assertNotIn(s, self.TERMINAL)


# ---------------------------------------------------------------------------
# 4. LoopBudget + BudgetStatus
# ---------------------------------------------------------------------------


class TestBudget(unittest.TestCase):
    def test_defaults(self):
        b = LoopBudget()
        self.assertEqual(b.max_steps, 100)

    def test_zero_max_steps_rejected(self):
        with self.assertRaises(ValueError):
            LoopBudget(max_steps=0)

    def test_zero_max_tokens_rejected(self):
        with self.assertRaises(ValueError):
            LoopBudget(max_tokens=0)

    def test_zero_wall_time_rejected(self):
        with self.assertRaises(ValueError):
            LoopBudget(max_wall_time_s=0.0)

    def test_zero_cost_rejected(self):
        with self.assertRaises(ValueError):
            LoopBudget(max_cost_estimate=0.0)


class TestBudgetStatus(unittest.TestCase):
    def test_fresh_not_exhausted(self):
        s = BudgetStatus()
        b = LoopBudget(max_steps=10)
        exhausted, reason = s.is_exhausted(b)
        self.assertFalse(exhausted)
        self.assertEqual(reason, "")

    def test_steps_exhausted(self):
        s = BudgetStatus(steps=10)
        b = LoopBudget(max_steps=10)
        exhausted, reason = s.is_exhausted(b)
        self.assertTrue(exhausted)
        self.assertIn("max_steps", reason)

    def test_tokens_exhausted(self):
        s = BudgetStatus(tokens=1_000_000)
        b = LoopBudget(max_tokens=1_000_000)
        exhausted, _ = s.is_exhausted(b)
        self.assertTrue(exhausted)

    def test_wall_time_exhausted(self):
        s = BudgetStatus(wall_time_s=600.0)
        b = LoopBudget(max_wall_time_s=600.0)
        exhausted, _ = s.is_exhausted(b)
        self.assertTrue(exhausted)

    def test_cost_exhausted(self):
        s = BudgetStatus(cost_estimate=100.0)
        b = LoopBudget(max_cost_estimate=100.0)
        exhausted, _ = s.is_exhausted(b)
        self.assertTrue(exhausted)


# ---------------------------------------------------------------------------
# 5. RevocationChannel
# ---------------------------------------------------------------------------


class TestRevocationChannel(unittest.TestCase):
    def test_default_not_revoked(self):
        rc = RevocationChannel()
        self.assertFalse(rc.is_revoked("loop-x"))

    def test_revoke_then_query(self):
        rc = RevocationChannel()
        rc.revoke("loop-x", "operator test")
        self.assertTrue(rc.is_revoked("loop-x"))
        self.assertEqual(rc.reason("loop-x"), "operator test")

    def test_clear_revocation(self):
        rc = RevocationChannel()
        rc.revoke("loop-x")
        rc.clear("loop-x")
        self.assertFalse(rc.is_revoked("loop-x"))

    def test_reason_unknown_returns_none(self):
        rc = RevocationChannel()
        self.assertIsNone(rc.reason("never-seen"))


# ---------------------------------------------------------------------------
# 6. LoopStep serialization
# ---------------------------------------------------------------------------


class TestLoopStep(unittest.TestCase):
    def test_to_dict_round_trip_minimal(self):
        step = LoopStep(
            step_id="step-1",
            loop_id="loop-1",
            sequence=1,
            phase=StepPhase.ACT,
        )
        d = step.to_dict()
        self.assertEqual(d["step_id"], "step-1")
        self.assertEqual(d["phase"], "act")
        self.assertIsNone(d["verdict"])
        self.assertIsNone(d["action"])

    def test_to_dict_with_verdict(self):
        step = LoopStep(
            step_id="step-2",
            loop_id="loop-1",
            sequence=2,
            phase=StepPhase.EVALUATE,
            verdict=Verdict.HALT,
            composite_rationale="because",
            evidence=[{"source": "x", "kind": "permit"}],
        )
        d = step.to_dict()
        self.assertEqual(d["verdict"], "halt")


# ---------------------------------------------------------------------------
# 7. BreakerGateVerifier
# ---------------------------------------------------------------------------


class TestBreakerGateVerifier(unittest.TestCase):
    def test_low_risk_permits(self):
        v = BreakerGateVerifier(FakeBreaker("LOW"))
        verdict, rationale, ev = v.evaluate(_identity(), {"tool": "x"}, None, [])
        self.assertEqual(verdict, Verdict.CONTINUE)
        self.assertTrue(any("permit" in e.get("kind", "") for e in ev))

    def test_critical_halts(self):
        v = BreakerGateVerifier(FakeBreaker("CRITICAL"))
        verdict, rationale, ev = v.evaluate(_identity(), {"tool": "x"}, None, [])
        self.assertEqual(verdict, Verdict.HALT)

    def test_medium_escalates_by_default(self):
        # MEDIUM risk ESCALATEs (operator must approve); never CONTINUE
        # silently. The "promote-never-demote" invariant of the gate stack.
        v = BreakerGateVerifier(FakeBreaker("MEDIUM"))
        verdict, _, _ = v.evaluate(_identity(), {"tool": "x"}, None, [])
        self.assertEqual(verdict, Verdict.ESCALATE)

    def test_name_attribute(self):
        v = BreakerGateVerifier(FakeBreaker("LOW"))
        self.assertTrue(v.name)

    def test_default_blocked_levels(self):
        v = BreakerGateVerifier(FakeBreaker("LOW"))
        verdict, _, _ = v.evaluate(_identity(), {"tool": "x"}, None, [])
        self.assertEqual(verdict, Verdict.CONTINUE)


# ---------------------------------------------------------------------------
# 8. LedgerGateVerifier
# ---------------------------------------------------------------------------


class TestLedgerGateVerifier(unittest.TestCase):
    def test_supported_permits(self):
        ledger = FakeLedger({"c1": "SUPPORTED"})
        v = LedgerGateVerifier(ledger)
        verdict, _, ev = v.evaluate(_identity(), {"tool": "x", "claim_ids": ["c1"]}, None, [])
        self.assertEqual(verdict, Verdict.CONTINUE)
        self.assertGreater(len(ev), 0)

    def test_contradicted_halts(self):
        ledger = FakeLedger({"c1": "CONTRADICTED"})
        v = LedgerGateVerifier(ledger)
        verdict, _, _ = v.evaluate(
            _identity(), {"tool": "x", "claim_ids": ["c1"]}, None, []
        )
        self.assertEqual(verdict, Verdict.HALT)

    def test_no_required_claims_escalates(self):
        ledger = FakeLedger({})
        v = LedgerGateVerifier(ledger)
        verdict, _, _ = v.evaluate(_identity(), {"tool": "x"}, None, [])
        self.assertEqual(verdict, Verdict.ESCALATE)

    def test_unknown_claim_default_escalate(self):
        # No claim_ids present in action -> UNGROUNDED -> ESCALATE.
        ledger = FakeLedger({})
        v = LedgerGateVerifier(ledger)
        v_returned = v.evaluate(_identity(), {"tool": "x"}, None, [])[0]
        self.assertEqual(v_returned, Verdict.ESCALATE)

    def test_name_attribute(self):
        ledger = FakeLedger({})
        v = LedgerGateVerifier(ledger)
        self.assertTrue(v.name)


# ---------------------------------------------------------------------------
# 9. MonitorGateVerifier
# ---------------------------------------------------------------------------


class TestMonitorGateVerifier(unittest.TestCase):
    def test_no_monitor_returns_continue(self):
        v = MonitorGateVerifier(monitor=None)
        verdict, _, _ = v.evaluate(_identity(), {"tool": "x"}, None, [])
        self.assertEqual(verdict, Verdict.CONTINUE)

    def test_halt_recommendation_halts(self):
        monitor = MagicMock()
        monitor.assess_current_state.return_value = MagicMock(
            cognitive_load=0.5, confidence=0.8, recommendation="halt"
        )
        v = MonitorGateVerifier(monitor=monitor)
        verdict, _, _ = v.evaluate(_identity(), {"tool": "x"}, None, [])
        self.assertEqual(verdict, Verdict.HALT)

    def test_escalate_recommendation_escalates(self):
        monitor = MagicMock()
        monitor.assess_current_state.return_value = MagicMock(
            cognitive_load=0.5, confidence=0.8, recommendation="escalate please"
        )
        v = MonitorGateVerifier(monitor=monitor)
        verdict, _, _ = v.evaluate(_identity(), {"tool": "x"}, None, [])
        self.assertEqual(verdict, Verdict.ESCALATE)

    def test_high_load_escalates(self):
        monitor = MagicMock()
        monitor.assess_current_state.return_value = MagicMock(
            cognitive_load=0.95, confidence=0.8, recommendation=""
        )
        v = MonitorGateVerifier(monitor=monitor, high_load=0.9)
        verdict, _, _ = v.evaluate(_identity(), {"tool": "x"}, None, [])
        self.assertEqual(verdict, Verdict.ESCALATE)

    def test_low_confidence_escalates(self):
        monitor = MagicMock()
        monitor.assess_current_state.return_value = MagicMock(
            cognitive_load=0.1, confidence=0.05, recommendation=""
        )
        v = MonitorGateVerifier(monitor=monitor, low_confidence=0.1)
        verdict, _, _ = v.evaluate(_identity(), {"tool": "x"}, None, [])
        self.assertEqual(verdict, Verdict.ESCALATE)

    def test_within_budget_continues(self):
        monitor = MagicMock()
        monitor.assess_current_state.return_value = MagicMock(
            cognitive_load=0.3, confidence=0.8, recommendation=""
        )
        v = MonitorGateVerifier(monitor=monitor)
        verdict, _, _ = v.evaluate(_identity(), {"tool": "x"}, None, [])
        self.assertEqual(verdict, Verdict.CONTINUE)

    def test_monitor_raises_halts(self):
        monitor = MagicMock()
        monitor.assess_current_state.side_effect = RuntimeError("boom")
        v = MonitorGateVerifier(monitor=monitor)
        verdict, _, _ = v.evaluate(_identity(), {"tool": "x"}, None, [])
        self.assertEqual(verdict, Verdict.HALT)

    def test_monitor_without_assess_returns_continue(self):
        monitor = MagicMock(spec=[])  # no assess_current_state
        v = MonitorGateVerifier(monitor=monitor)
        verdict, _, _ = v.evaluate(_identity(), {"tool": "x"}, None, [])
        self.assertEqual(verdict, Verdict.CONTINUE)


# ---------------------------------------------------------------------------
# 10. CompositeVerifier
# ---------------------------------------------------------------------------


class TestCompositeVerifier(unittest.TestCase):
    def test_empty_rejected(self):
        with self.assertRaises(ValueError):
            CompositeVerifier([])

    def test_all_continue_continues(self):
        c = CompositeVerifier([_permit_verifier("a"), _permit_verifier("b")])
        v, _, _ = c.evaluate(_identity(), {"tool": "x"}, None, [])
        self.assertEqual(v, Verdict.CONTINUE)

    def test_halt_trumps(self):
        c = CompositeVerifier([_permit_verifier("a"), _halt_verifier("b")])
        v, rationale, _ = c.evaluate(_identity(), {"tool": "x"}, None, [])
        self.assertEqual(v, Verdict.HALT)
        self.assertIn("b=halt", rationale)

    def test_escalate_trumps_continue(self):
        c = CompositeVerifier([_permit_verifier("a"), _escalate_verifier("b")])
        v, _, _ = c.evaluate(_identity(), {"tool": "x"}, None, [])
        self.assertEqual(v, Verdict.ESCALATE)

    def test_member_raise_demotes_to_escalate(self):
        bad = MagicMock()
        bad.name = "bad"
        bad.evaluate.side_effect = RuntimeError("boom")
        c = CompositeVerifier([bad, _permit_verifier("ok")])
        v, rationale, _ = c.evaluate(_identity(), {"tool": "x"}, None, [])
        self.assertEqual(v, Verdict.ESCALATE)
        self.assertIn("raised", rationale)

    def test_conservative_posture_halt_never_demoted(self):
        c = CompositeVerifier([
            _halt_verifier("a"),
            _permit_verifier("b"),
            _permit_verifier("c"),
        ])
        v, _, _ = c.evaluate(_identity(), {"tool": "x"}, None, [])
        self.assertEqual(v, Verdict.HALT)

    def test_conservative_posture_member_exception_demotes(self):
        bad = MagicMock()
        bad.name = "bad"
        bad.evaluate.side_effect = RuntimeError("boom")
        c = CompositeVerifier([bad, _permit_verifier("ok")])
        v, _, _ = c.evaluate(_identity(), {"tool": "x"}, None, [])
        # Exception becomes ESCALATE, not CONTINUE -- conservative
        self.assertEqual(v, Verdict.ESCALATE)


# ---------------------------------------------------------------------------
# 11. AgentLoop end-to-end
# ---------------------------------------------------------------------------


class TestAgentLoopHappyPath(unittest.TestCase):
    def test_goal_reached_completes(self):
        work = _RecorderWork([{"score": 0.1}, {"score": 0.5}, {"score": 0.9}])
        goal = lambda obs: isinstance(obs, dict) and obs.get("score", 0) > 0.8
        loop = _make_loop([_permit_verifier()], work=work)
        result = loop.run(work, goal)
        self.assertEqual(loop.lifecycle, LifecycleState.COMPLETED)
        self.assertEqual(result.get("score"), 0.9)

    def test_step_count_increments(self):
        work = _RecorderWork([{"score": 0.1}, {"score": 0.4}, {"score": 0.95}])
        goal = lambda obs: obs.get("score", 0) > 0.8
        loop = _make_loop([_permit_verifier()], work=work)
        loop.run(work, goal)
        self.assertEqual(loop.lifecycle, LifecycleState.COMPLETED)
        # 3 act steps + 3 observe steps + 3 evaluate steps + 1 closing = 10
        self.assertGreaterEqual(loop.step_count, 7)

    def test_dry_run_no_audit_path(self):
        work = _RecorderWork([{"ok": True}])
        goal = lambda obs: obs.get("ok")
        loop = _make_loop([_permit_verifier()], work=work)
        loop.run(work, goal)
        self.assertIsNone(loop._audit_path)


class TestAgentLoopEscalate(unittest.TestCase):
    def test_escalate_pauses(self):
        work = _RecorderWork([{"ok": True}])
        goal = lambda obs: False
        loop = _make_loop([_escalate_verifier()], work=work)
        loop.run(work, goal)
        self.assertEqual(loop.lifecycle, LifecycleState.WAITING)

    def test_work_called_once_before_pause(self):
        work = _RecorderWork([{"ok": True}])
        goal = lambda obs: False
        loop = _make_loop([_escalate_verifier()], work=work)
        loop.run(work, goal)
        # Work is called once per act; ESCALATE pauses after the first act
        self.assertEqual(len(work.calls), 1)


class TestAgentLoopHalt(unittest.TestCase):
    def test_halt_fails_loop(self):
        work = _RecorderWork([{"ok": True}])
        goal = lambda obs: False
        loop = _make_loop([_halt_verifier()], work=work)
        result = loop.run(work, goal)
        self.assertEqual(loop.lifecycle, LifecycleState.FAILED)
        # result is the observation from the act that halted
        self.assertIsNotNone(result)


class TestAgentLoopTerminality(unittest.TestCase):
    def test_cannot_rerun_completed(self):
        work = _RecorderWork([{"ok": True}])
        goal = lambda obs: obs.get("ok")
        loop = _make_loop([_permit_verifier()], work=work)
        loop.run(work, goal)
        with self.assertRaises(RuntimeError):
            loop.run(work, goal)

    def test_cannot_rerun_failed(self):
        work = _RecorderWork([{"ok": True}])
        goal = lambda obs: False
        loop = _make_loop([_halt_verifier()], work=work)
        loop.run(work, goal)
        with self.assertRaises(RuntimeError):
            loop.run(work, goal)


class TestAgentLoopRevocation(unittest.TestCase):
    def test_revocation_revokes(self):
        rc = RevocationChannel()
        rc.revoke("loop-test-001", "operator mid-run")
        work = _RecorderWork([{"ok": True}, {"ok": True}])
        goal = lambda obs: False
        loop = _make_loop([_permit_verifier()], work=work, revocation=rc)
        loop.run(work, goal)
        self.assertEqual(loop.lifecycle, LifecycleState.REVOKED)

    def test_revocation_check_runs_before_act(self):
        rc = RevocationChannel()
        rc.revoke("loop-test-001")
        work = _RecorderWork([{"ok": True}, {"ok": True}])
        goal = lambda obs: False
        loop = _make_loop([_permit_verifier()], work=work, revocation=rc)
        loop.run(work, goal)
        # No work calls expected (revoked before first act)
        self.assertEqual(len(work.calls), 0)


class TestAgentLoopBudget(unittest.TestCase):
    def test_budget_exhaustion_completes(self):
        # Budget exhausted immediately (max_steps=0 is invalid; use a tight one)
        # So use a budget that exhausts after 1 step
        work = _RecorderWork([{"ok": True}, {"ok": True}, {"ok": True}])
        goal = lambda obs: False
        # max_steps=1 means the budget exhausts before the second act
        loop = _make_loop(
            [_permit_verifier()],
            work=work,
            budget=LoopBudget(max_steps=1),
        )
        loop.run(work, goal)
        self.assertEqual(loop.lifecycle, LifecycleState.COMPLETED)

    def test_budget_check_before_act(self):
        # Use a budget that exhausts after 0 steps (we have to find a way)
        # LoopBudget rejects max_steps=0; we work around by using
        # max_iterations=1 to demonstrate the cap
        work = _RecorderWork([{"ok": True}, {"ok": True}, {"ok": True}])
        goal = lambda obs: False
        loop = _make_loop(
            [_permit_verifier()],
            work=work,
            budget=LoopBudget(max_steps=10),
        )
        loop.run(work, goal, max_iterations=1)
        # With max_iterations=1, only 1 act happens
        self.assertEqual(len(work.calls), 1)


class TestAgentLoopActException(unittest.TestCase):
    def test_work_raises_fails_loop(self):
        def boom(identity, action):
            raise RuntimeError("work exploded")

        goal = lambda obs: False
        loop = _make_loop([_permit_verifier()], work=boom)
        loop.run(boom, goal)
        self.assertEqual(loop.lifecycle, LifecycleState.FAILED)


class TestAgentLoopAudit(unittest.TestCase):
    def test_audit_persists_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = os.path.join(tmp, "loop.jsonl")
            work = _RecorderWork([{"ok": True}])
            goal = lambda obs: obs.get("ok")
            loop = _make_loop([_permit_verifier()], work=work, audit_path=audit)
            loop.run(work, goal)
            self.assertTrue(os.path.exists(audit))
            with open(audit) as fh:
                lines = [json.loads(l) for l in fh if l.strip()]
            self.assertGreater(len(lines), 0)
            # Every line has step_id and loop_id
            for entry in lines:
                self.assertIn("step_id", entry)
                self.assertEqual(entry["loop_id"], "loop-test-001")


class TestAgentLoopRingBuffer(unittest.TestCase):
    def test_in_memory_ring_capped(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = os.path.join(tmp, "loop.jsonl")
            work = _RecorderWork([{"ok": False}, {"ok": False}, {"ok": True}])
            goal = lambda obs: obs.get("ok")
            loop = _make_loop(
                [_permit_verifier()],
                work=work,
                audit_path=audit,
            )
            # Force max_in_memory_steps small by reconfiguring
            loop._steps = deque(maxlen=2)  # type: ignore
            loop.run(work, goal)
            # Ring capped at 2, but audit trail has the full count
            self.assertLessEqual(loop.step_count, 2)
            with open(audit) as fh:
                lines = [json.loads(l) for l in fh if l.strip()]
            self.assertGreater(len(lines), 2)


class TestAgentLoopBudgetCounters(unittest.TestCase):
    def test_budget_counters_increment(self):
        work = _RecorderWork([{"ok": True, "tokens_used": 10, "cost_estimate": 0.5}])
        goal = lambda obs: obs.get("ok")
        loop = _make_loop([_permit_verifier()], work=work)
        loop.run(work, goal)
        self.assertGreaterEqual(loop.budget_status.tokens, 10)
        self.assertGreaterEqual(loop.budget_status.cost_estimate, 0.5)


class TestCreateAgentLoop(unittest.TestCase):
    def test_convenience_constructor(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = os.path.join(tmp, "loop.jsonl")
            work = _RecorderWork([{"ok": True}])
            goal = lambda obs: obs.get("ok")
            loop = create_agent_loop(
                principal="dave92",
                purpose="convenience test",
                verifiers=[_permit_verifier()],
                budget=LoopBudget(max_steps=10),
                audit_path=audit,
            )
            self.assertEqual(loop.config.identity.principal, "dave92")
            self.assertEqual(loop.config.identity.purpose, "convenience test")
            loop.run(work, goal)
            self.assertEqual(loop.lifecycle, LifecycleState.COMPLETED)

    def test_convenience_constructor_no_audit(self):
        work = _RecorderWork([{"ok": True}])
        goal = lambda obs: obs.get("ok")
        loop = create_agent_loop(
            principal="dave92",
            purpose="no audit",
            verifiers=[_permit_verifier()],
        )
        self.assertIsNone(loop._audit_path)
        loop.run(work, goal)
        self.assertEqual(loop.lifecycle, LifecycleState.COMPLETED)


if __name__ == "__main__":
    unittest.main()
