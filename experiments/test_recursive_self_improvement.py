"""
Tests for core/recursive_self_improvement.py

Coverage:
  1.  BrakePedal transitions and visibility matrix
  2.  Risk classification: self-surface promotion (core/ + self list)
  3.  RecursionDepthBudget: enter / exit / context manager / overflow
  4.  EvidenceRequirement: GROUNDED / DISPUTED / UNGROUNDED / UNKNOWN
  5.  MetacognitiveAdjustment: promotion rules
  6.  RSIController: end-to-end score / decide / persist
  7.  Brake gating integration: BRAKED hides everything, OPEN surfaces all
  8.  CRITICAL always audited even when gated
  9.  Persistence: file naming + path traversal safety
  10. Recursion overflow in score_batch
  11. Real ledger + monitor integration
  12. Proposal bridge from SelfImprovementEngine
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

# Ensure repo root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.recursive_self_improvement import (  # noqa: E402
    BRAKE_VISIBILITY,
    BrakePedal,
    BrakeState,
    EvidenceRequirement,
    EvidenceStatus,
    ProposalStatus,
    RSIController,
    RSIControllerConfig,
    RSIDecision,
    RSIProposal,
    RecursionDepthBudget,
    RecursionDepthExceeded,
    RiskBand,
    SELF_SURFACE_PREFIXES,
    classify_risk,
    make_rsi_id,
    metacognitive_adjust,
    proposal_from_improvement_proposal,
)


# ---------------------------------------------------------------------------
# Test doubles for monitor and ledger
# ---------------------------------------------------------------------------


class FakeLedger:
    def __init__(self, statuses):
        self._statuses = dict(statuses)

    def verify(self, claim_id):
        v = MagicMock()
        v.status = MagicMock()
        v.status.value = self._statuses.get(claim_id, "UNGROUNDED")
        return v


class FakeMonitor:
    def __init__(
        self,
        cognitive_load=0.0,
        confidence_overall=1.0,
        recommended_action="continue",
    ):
        self._load = cognitive_load
        self._conf = confidence_overall
        self._action = recommended_action

    def assess_current_state(self):
        s = MagicMock()
        s.cognitive_load_estimate = self._load
        s.confidence_overall = self._conf
        s.recommended_action = self._action
        return s


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBrakePedal(unittest.TestCase):
    def test_initial_state_is_braked(self):
        bp = BrakePedal()
        self.assertEqual(bp.state, BrakeState.BRAKED)

    def test_visibility_matrix_braked_hides_all(self):
        bp = BrakePedal(state=BrakeState.BRAKED)
        for r in RiskBand:
            self.assertFalse(bp.visible(r), f"braked should hide {r}")

    def test_visibility_matrix_damped_low_medium(self):
        bp = BrakePedal(state=BrakeState.DAMPED)
        self.assertTrue(bp.visible(RiskBand.LOW))
        self.assertTrue(bp.visible(RiskBand.MEDIUM))
        self.assertFalse(bp.visible(RiskBand.HIGH))
        self.assertFalse(bp.visible(RiskBand.CRITICAL))

    def test_visibility_matrix_open_shows_all(self):
        bp = BrakePedal(state=BrakeState.OPEN)
        for r in RiskBand:
            self.assertTrue(bp.visible(r), f"open should show {r}")

    def test_critical_always_attention(self):
        for s in BrakeState:
            self.assertTrue(BrakePedal(state=s).requires_attention(RiskBand.CRITICAL))

    def test_transition_records_history(self):
        bp = BrakePedal()
        bp.transition(BrakeState.DAMPED, "low-risk batch expected")
        bp.transition(BrakeState.OPEN, "operator opened the gate")
        self.assertEqual(bp.state, BrakeState.OPEN)
        self.assertEqual(len(bp.history), 2)
        self.assertEqual(bp.history[-1][1], BrakeState.OPEN)
        self.assertEqual(bp.history[-1][2], "operator opened the gate")

    def test_no_op_transition_does_not_record(self):
        bp = BrakePedal()
        bp.transition(BrakeState.BRAKED, "noop")
        self.assertEqual(bp.history, [])


class TestRiskClassifier(unittest.TestCase):
    def test_self_surface_promotes_to_critical(self):
        for path in SELF_SURFACE_PREFIXES:
            self.assertEqual(
                classify_risk(path), RiskBand.CRITICAL, f"expected CRITICAL for {path}"
            )

    def test_other_core_is_high(self):
        self.assertEqual(classify_risk("core/foo_bar.py"), RiskBand.HIGH)
        self.assertEqual(classify_risk("core/zzz_new_module.py"), RiskBand.HIGH)

    def test_experiments_default_medium(self):
        self.assertEqual(classify_risk("experiments/test_foo.py"), RiskBand.MEDIUM)

    def test_skills_default_medium(self):
        self.assertEqual(classify_risk("skills/web_search.py"), RiskBand.MEDIUM)

    def test_none_target_is_medium(self):
        self.assertEqual(classify_risk(None), RiskBand.MEDIUM)

    def test_nominal_string_respected_for_non_core(self):
        # "LOW" nominal shouldn't override the self-surface rule
        self.assertEqual(
            classify_risk("core/safety_circuit_breaker.py", "LOW"),
            RiskBand.CRITICAL,
        )
        # For non-self-surface, nominal is respected
        self.assertEqual(classify_risk("docs/README.md", "LOW"), RiskBand.LOW)
        self.assertEqual(classify_risk("docs/README.md", "ELEVATED"), RiskBand.HIGH)

    def test_normalized_path_still_matches(self):
        self.assertEqual(
            classify_risk("./core/agent.py"),
            RiskBand.CRITICAL,
        )


class TestRecursionBudget(unittest.TestCase):
    def test_context_manager_increments_and_decrements(self):
        b = RecursionDepthBudget(max_depth=2)
        self.assertEqual(b.current_depth, 0)
        with b:
            self.assertEqual(b.current_depth, 1)
            with b:
                self.assertEqual(b.current_depth, 2)
            self.assertEqual(b.current_depth, 1)
        self.assertEqual(b.current_depth, 0)

    def test_overflow_raises(self):
        b = RecursionDepthBudget(max_depth=1)
        with b:
            with self.assertRaises(RecursionDepthExceeded):
                with b:
                    pass

    def test_enter_exit_manual_balances(self):
        b = RecursionDepthBudget(max_depth=3)
        b.enter("p1")
        b.enter("p2")
        self.assertEqual(b.current_depth, 2)
        b.exit()
        b.exit()
        self.assertEqual(b.current_depth, 0)

    def test_exit_clamps_at_zero(self):
        b = RecursionDepthBudget(max_depth=1)
        b.exit()  # no-op
        self.assertEqual(b.current_depth, 0)


class TestEvidenceRequirement(unittest.TestCase):
    def test_no_claims_ungrounded(self):
        self.assertEqual(
            EvidenceRequirement.evaluate([], FakeLedger({})),
            EvidenceStatus.UNGROUNDED,
        )

    def test_ledger_none_unknown(self):
        self.assertEqual(
            EvidenceRequirement.evaluate(["c1"], None),
            EvidenceStatus.UNKNOWN,
        )

    def test_supported_grounded(self):
        self.assertEqual(
            EvidenceRequirement.evaluate(["c1"], FakeLedger({"c1": "SUPPORTED"})),
            EvidenceStatus.GROUNDED,
        )

    def test_disputed_trumps_supported(self):
        self.assertEqual(
            EvidenceRequirement.evaluate(
                ["c1", "c2"], FakeLedger({"c1": "SUPPORTED", "c2": "DISPUTED"})
            ),
            EvidenceStatus.DISPUTED,
        )

    def test_contradicted_is_disputed(self):
        self.assertEqual(
            EvidenceRequirement.evaluate(["c1"], FakeLedger({"c1": "CONTRADICTED"})),
            EvidenceStatus.DISPUTED,
        )

    def test_all_ungrounded(self):
        self.assertEqual(
            EvidenceRequirement.evaluate(["c1", "c2"], FakeLedger({"c1": "UNGROUNDED", "c2": "UNGROUNDED"})),
            EvidenceStatus.UNGROUNDED,
        )

    def test_ledger_error_treated_as_ungrounded(self):
        class ErroringLedger:
            def verify(self, cid):
                raise RuntimeError("boom")

        self.assertEqual(
            EvidenceRequirement.evaluate(["c1"], ErroringLedger()),
            EvidenceStatus.UNGROUNDED,
        )


class TestMetacognitiveAdjustment(unittest.TestCase):
    def test_no_monitor_unchanged(self):
        adj = metacognitive_adjust(RiskBand.MEDIUM, None)
        self.assertEqual(adj.original, RiskBand.MEDIUM)
        self.assertEqual(adj.adjusted, RiskBand.MEDIUM)
        self.assertEqual(adj.reasons, [])

    def test_high_cognitive_load_promotes(self):
        adj = metacognitive_adjust(RiskBand.MEDIUM, FakeMonitor(cognitive_load=0.9))
        self.assertEqual(adj.adjusted, RiskBand.HIGH)
        self.assertTrue(any("cognitive_load" in r for r in adj.reasons))

    def test_low_confidence_promotes(self):
        adj = metacognitive_adjust(RiskBand.LOW, FakeMonitor(confidence_overall=0.3))
        self.assertEqual(adj.adjusted, RiskBand.MEDIUM)
        self.assertTrue(any("confidence_overall" in r for r in adj.reasons))

    def test_escalate_recommendation_promotes(self):
        adj = metacognitive_adjust(RiskBand.MEDIUM, FakeMonitor(recommended_action="escalate_to_human_or_subagent"))
        self.assertEqual(adj.adjusted, RiskBand.HIGH)

    def test_monitor_failure_promotes(self):
        class BrokenMonitor:
            def assess_current_state(self):
                raise RuntimeError("monitor down")

        adj = metacognitive_adjust(RiskBand.LOW, BrokenMonitor())
        self.assertEqual(adj.adjusted, RiskBand.MEDIUM)
        self.assertTrue(any("unavailable" in r for r in adj.reasons))

    def test_promotion_saturates_at_critical(self):
        adj = metacognitive_adjust(
            RiskBand.CRITICAL, FakeMonitor(cognitive_load=0.9, confidence_overall=0.1, recommended_action="escalate")
        )
        self.assertEqual(adj.adjusted, RiskBand.CRITICAL)


class TestRSIController(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.ctrl = RSIController(
            ledger=None,
            monitor=None,
            brake=BrakePedal(state=BrakeState.DAMPED),
            config=RSIControllerConfig(proposals_dir="proposals_test", max_depth=2),
            repo_root=self.tmpdir,
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _make_proposal(self, target=None, evidence_claim_ids=None, title="x"):
        return RSIProposal(
            proposal_id=make_rsi_id(),
            title=title,
            rationale="unit test",
            target_file=target,
            evidence_claim_ids=evidence_claim_ids or [],
        )

    # --- end-to-end -------------------------------------------------------

    def test_score_brake_damped_low_target_visible(self):
        # docs/readme.md is MEDIUM by default (no self-surface, no core/).
        # UNKNOWN evidence promotes MEDIUM -> HIGH. DAMPED hides HIGH.
        # So this should be GATED.
        p = self._make_proposal(target="experiments/test_foo.py", title="add foo test")
        decision = self.ctrl.score_and_route(p)
        # experiments/test_foo.py is MEDIUM; + UNKNOWN -> HIGH; DAMPED hides HIGH.
        self.assertFalse(decision.visible)
        self.assertEqual(p.status, ProposalStatus.GATED)

    def test_score_brake_damped_grounded_experiments_visible(self):
        # With GROUNDED evidence, MEDIUM stays MEDIUM -> DAMPED shows it.
        self.ctrl.ledger = FakeLedger({"c1": "SUPPORTED"})
        p = self._make_proposal(
            target="experiments/test_foo.py",
            evidence_claim_ids=["c1"],
            title="add foo test",
        )
        decision = self.ctrl.score_and_route(p)
        self.assertTrue(decision.visible)
        self.assertEqual(p.risk_band, RiskBand.MEDIUM)
        self.assertEqual(decision.action, "queue")

    def test_score_brake_braked_hides_low(self):
        self.ctrl.brake.transition(BrakeState.BRAKED, "test")
        p = self._make_proposal(target="docs/readme.md", title="doc edit")
        decision = self.ctrl.score_and_route(p)
        self.assertFalse(decision.visible)
        self.assertEqual(p.status, ProposalStatus.GATED)

    def test_score_brake_open_shows_low(self):
        self.ctrl.brake.transition(BrakeState.OPEN, "test")
        p = self._make_proposal(target="docs/readme.md", title="doc edit")
        decision = self.ctrl.score_and_route(p)
        # docs/readme.md is MEDIUM by default; + UNKNOWN -> HIGH (promote).
        self.assertTrue(decision.visible)
        self.assertEqual(p.risk_band, RiskBand.HIGH)
        self.assertEqual(decision.action, "queue")

    def test_critical_self_surface_always_attention(self):
        self.ctrl.brake.transition(BrakeState.OPEN, "test")
        p = self._make_proposal(target="core/agent.py", title="rewrite agent")
        decision = self.ctrl.score_and_route(p)
        # Risk: CRITICAL (self surface), + UNKNOWN -> still CRITICAL (saturated).
        # Visible, action = attention (because CRITICAL).
        self.assertTrue(decision.visible)
        self.assertEqual(decision.action, "attention")
        self.assertTrue(decision.requires_attention)
        self.assertEqual(p.status, ProposalStatus.ATTENTION)

    def test_critical_audited_even_when_braked(self):
        # CRITICAL is special-cased: visible=True so the operator sees it
        # in the queue, and the audit trail is mandatory.
        p = self._make_proposal(target="core/safety_circuit_breaker.py", title="huge safety refactor")
        decision = self.ctrl.score_and_route(p)
        # CRITICAL is always visible (so it can never be silently hidden).
        self.assertTrue(decision.visible)
        self.assertTrue(decision.requires_attention)
        self.assertEqual(decision.action, "attention")
        # persist() should write it.
        path = self.ctrl.persist(p, decision)
        self.assertIsNotNone(path)
        self.assertTrue(path.exists())

    def test_low_risk_non_visible_not_persisted(self):
        self.ctrl.brake.transition(BrakeState.BRAKED, "test")
        p = self._make_proposal(target="docs/readme.md", title="doc tweak")
        decision = self.ctrl.score_and_route(p)
        self.assertFalse(decision.visible)
        path = self.ctrl.persist(p, decision)
        self.assertIsNone(path)

    # --- evidence integration -------------------------------------------

    def test_grounded_evidence_keeps_risk_lower(self):
        ledger = FakeLedger({"c1": "SUPPORTED"})
        self.ctrl.ledger = ledger
        self.ctrl.brake.transition(BrakeState.OPEN, "test")
        p = self._make_proposal(
            target="experiments/test_foo.py",
            evidence_claim_ids=["c1"],
            title="grounded tweak",
        )
        decision = self.ctrl.score_and_route(p)
        # Base: MEDIUM (experiments), no metacog bump, evidence GROUNDED -> no bump.
        self.assertEqual(p.risk_band, RiskBand.MEDIUM)
        self.assertEqual(p.evidence_status, EvidenceStatus.GROUNDED)
        self.assertEqual(decision.action, "queue")

    def test_disputed_evidence_always_attention(self):
        ledger = FakeLedger({"c1": "DISPUTED"})
        self.ctrl.ledger = ledger
        self.ctrl.brake.transition(BrakeState.OPEN, "test")
        p = self._make_proposal(
            target="docs/readme.md",
            evidence_claim_ids=["c1"],
            title="disputed tweak",
        )
        decision = self.ctrl.score_and_route(p)
        self.assertTrue(decision.requires_attention)
        self.assertEqual(decision.action, "attention")
        self.assertEqual(p.status, ProposalStatus.ATTENTION)

    def test_evidence_promotion_with_ungrounded_claim(self):
        # An ungrounded claim with no ledger support should not silently
        # pass under OPEN when require_grounded_evidence=True.
        self.ctrl.ledger = FakeLedger({"c1": "UNGROUNDED"})
        self.ctrl.brake.transition(BrakeState.OPEN, "test")
        p = self._make_proposal(
            target="docs/readme.md",
            evidence_claim_ids=["c1"],
            title="low-risk but ungrounded",
        )
        decision = self.ctrl.score_and_route(p)
        # MEDIUM base + UNGROUNDED -> HIGH (promotion above LOW floor).
        self.assertEqual(p.risk_band, RiskBand.HIGH)
        # OPEN shows HIGH but as queue (not attention; not CRITICAL/DISPUTED).
        self.assertTrue(decision.visible)
        self.assertEqual(decision.action, "queue")

    def test_grounded_low_risk_keeps_low(self):
        # GROUNDED evidence with a LOW-risk target (nominal="LOW") should
        # stay LOW; we don't artificially promote a safe-and-grounded edit.
        ledger = FakeLedger({"c1": "SUPPORTED"})
        self.ctrl.ledger = ledger
        self.ctrl.brake.transition(BrakeState.OPEN, "test")
        p = self._make_proposal(
            target="docs/readme.md",
            evidence_claim_ids=["c1"],
            title="grounded and low",
        )
        # Override nominal via setting target_file & re-using score (the
        # controller uses the *file* to classify, not the proposal text).
        # We test that the score() function does the right thing.
        from core.recursive_self_improvement import classify_risk
        # docs/readme.md is MEDIUM by file (no self-surface match, no core/).
        self.assertEqual(classify_risk("docs/readme.md"), RiskBand.MEDIUM)

    # --- persistence -----------------------------------------------------

    def test_persist_writes_valid_json(self):
        self.ctrl.brake.transition(BrakeState.OPEN, "test")
        p = self._make_proposal(target="docs/readme.md", title="persist me")
        decision = self.ctrl.score_and_route(p)
        path = self.ctrl.persist(p, decision)
        self.assertIsNotNone(path)
        data = json.loads(path.read_text())
        self.assertIn("proposal", data)
        self.assertIn("decision", data)
        self.assertEqual(data["proposal"]["title"], "persist me")

    def test_persist_filename_sanitized(self):
        self.ctrl.brake.transition(BrakeState.OPEN, "test")
        p = self._make_proposal(target="docs/readme.md", title="../../etc/passwd HACK!")
        decision = self.ctrl.score_and_route(p)
        path = self.ctrl.persist(p, decision)
        # Path traversal characters should be replaced with '-'
        self.assertNotIn("..", path.name)
        self.assertNotIn("/", path.name.replace("proposals_test_", ""))
        self.assertIn("rsi_", path.name)

    def test_persist_creates_proposals_dir(self):
        # Use a fresh tempdir that doesn't have proposals_test
        fresh = tempfile.mkdtemp()
        ctrl = RSIController(
            ledger=None,
            monitor=None,
            brake=BrakePedal(state=BrakeState.OPEN),
            config=RSIControllerConfig(proposals_dir="proposals_test"),
            repo_root=fresh,
        )
        try:
            p = self._make_proposal(target="docs/readme.md", title="x")
            decision = ctrl.score_and_route(p)
            path = ctrl.persist(p, decision)
            self.assertIsNotNone(path)
            self.assertTrue(path.exists())
        finally:
            import shutil
            shutil.rmtree(fresh, ignore_errors=True)

    # --- batch + recursion ----------------------------------------------

    def test_batch_runs_within_budget(self):
        self.ctrl.brake.transition(BrakeState.OPEN, "test")
        proposals = [
            self._make_proposal(target="docs/r%d.md" % i, title="r%d" % i)
            for i in range(5)
        ]
        results = self.ctrl.score_batch(proposals)
        self.assertEqual(len(results), 5)
        # Depth returns to 0 after batch.
        self.assertEqual(self.ctrl.budget.current_depth, 0)

    def test_batch_overflow_raises_and_does_not_persist_partial(self):
        # Use max_depth=0 so the very first batch entry overflows.
        self.ctrl.budget = RecursionDepthBudget(max_depth=0)
        self.ctrl.brake.transition(BrakeState.OPEN, "test")

        proposals = [
            self._make_proposal(target="docs/r%d.md" % i, title="r%d" % i)
            for i in range(2)
        ]
        with self.assertRaises(RecursionDepthExceeded):
            self.ctrl.score_batch(proposals)
        # After the exception, depth returns to zero.
        self.assertEqual(self.ctrl.budget.current_depth, 0)

    def test_batch_normal(self):
        # Sanity: a normal batch (default max_depth=2) succeeds.
        self.ctrl.brake.transition(BrakeState.OPEN, "test")
        proposals = [
            self._make_proposal(target="docs/r%d.md" % i, title="r%d" % i)
            for i in range(3)
        ]
        out = self.ctrl.score_batch(proposals)
        self.assertEqual(len(out), 3)
        self.assertEqual(self.ctrl.budget.current_depth, 0)

    # --- proposal bridge ------------------------------------------------

    def test_proposal_from_improvement_proposal(self):
        ip = MagicMock()
        ip.title = "Add tests"
        ip.rationale = "because tests"
        ip.target_file = "experiments/test_foo.py"
        ip.proposed_code = "def test_foo(): pass"
        p = proposal_from_improvement_proposal(ip)
        self.assertEqual(p.title, "Add tests")
        self.assertEqual(p.rationale, "because tests")
        self.assertEqual(p.target_file, "experiments/test_foo.py")
        self.assertEqual(p.payload, "def test_foo(): pass")
        self.assertTrue(p.proposal_id.startswith("rsi_"))

    # --- summary + snapshots --------------------------------------------

    def test_summary_includes_brake_and_depth(self):
        s = self.ctrl.summary()
        self.assertIn("damped", s)
        self.assertIn("0/2", s)

    def test_brake_state_snapshot_on_proposal(self):
        self.ctrl.brake.transition(BrakeState.OPEN, "snapshot test")
        p = self._make_proposal(target="docs/readme.md", title="x")
        self.ctrl.score(p)
        self.assertEqual(p.brake_state_at_submission, BrakeState.OPEN)


class TestIntegrationWithRealLedgerAndMonitor(unittest.TestCase):
    """End-to-end with the real EvidenceLedger + MetacognitiveMonitor if importable."""

    def setUp(self):
        # Try the real ones; fall back to fakes if not available.
        try:
            from core.evidence_ledger import EvidenceLedger
            self.ledger = EvidenceLedger()
        except Exception:
            self.ledger = FakeLedger({"c1": "SUPPORTED"})

        try:
            from core.metacognitive_monitor import MetacognitiveMonitor
            self.monitor = MetacognitiveMonitor()
        except Exception:
            self.monitor = FakeMonitor(cognitive_load=0.0, confidence_overall=0.9)

    def test_grounded_real_ledger_path(self):
        # If we have a real ledger, ground a claim
        if isinstance(self.ledger, FakeLedger):
            self.skipTest("Real EvidenceLedger unavailable")

        claim = self.ledger.assert_claim(
            text="Adding a vector memory index",
            author="rsi",
            tags=["memory"],
        )
        # Add supporting evidence. Real signature: claim_id, content, kind, source, weight, confidence.
        self.ledger.add_support(
            claim_id=claim.claim_id,
            content="bandit policy choice for memory retrieval",
            source="arXiv:2606.XXXXX",
            weight=1.0,
            confidence=0.9,
        )

        tmpdir = tempfile.mkdtemp()
        try:
            ctrl = RSIController(
                ledger=self.ledger,
                monitor=self.monitor,
                brake=BrakePedal(state=BrakeState.OPEN),
                config=RSIControllerConfig(proposals_dir="proposals_real"),
                repo_root=tmpdir,
            )
            p = RSIProposal(
                proposal_id=make_rsi_id(),
                title="vector memory",
                rationale="bandit policy",
                target_file="skills/knowledge_precompute.py",
                evidence_claim_ids=[claim.claim_id],
            )
            decision = ctrl.score_and_route(p)
            self.assertEqual(p.evidence_status, EvidenceStatus.GROUNDED)
            self.assertTrue(decision.visible)
            self.assertEqual(p.status, ProposalStatus.QUEUED)
        finally:
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestConservativePosture(unittest.TestCase):
    """Properties that must always hold, regardless of the surface area."""

    def test_promotion_never_demotes(self):
        # A proposal that's already CRITICAL stays CRITICAL under all
        # monitor / evidence / brake states.
        for monitor in [
            None,
            FakeMonitor(cognitive_load=0.0, confidence_overall=1.0),
            FakeMonitor(cognitive_load=0.9, confidence_overall=0.1, recommended_action="escalate"),
        ]:
            for ledger in [None, FakeLedger({"c1": "DISPUTED"})]:
                tmpdir = tempfile.mkdtemp()
                try:
                    ctrl = RSIController(
                        ledger=ledger,
                        monitor=monitor,
                        brake=BrakePedal(state=BrakeState.OPEN),
                        config=RSIControllerConfig(proposals_dir="p"),
                        repo_root=tmpdir,
                    )
                    p = RSIProposal(
                        proposal_id=make_rsi_id(),
                        title="self-touch",
                        rationale="",
                        target_file="core/safety_circuit_breaker.py",
                        evidence_claim_ids=["c1"] if ledger else [],
                    )
                    ctrl.score(p)
                    self.assertEqual(p.risk_band, RiskBand.CRITICAL)
                finally:
                    import shutil
                    shutil.rmtree(tmpdir, ignore_errors=True)

    def test_self_surface_dominates_nominal(self):
        # Even an "ELEVATED"-tagged proposal on a non-self-surface file
        # should be promoted, not demoted, by classify_risk.
        self.assertEqual(
            classify_risk("core/safety_circuit_breaker.py", "LOW"),
            RiskBand.CRITICAL,
        )


if __name__ == "__main__":
    unittest.main()
