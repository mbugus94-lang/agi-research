"""
Tests for skills/skill_coevolution.py

Coverage:
  1.  Value objects: VerifierVerdict, VerifierSignal, CoEvolutionConfig
  2.  SurrogateVerifier: PASS / FAIL / NEEDS_MORE_EVIDENCE / disputed
  3.  ProposalLedger: append, history_for, recent ordering
  4.  SkillEvolutionGate: full pipeline + brake transitions + summary
  5.  Integration with the real core.evidence_ledger.EvidenceLedger
  6.  Conservative posture: marginal -> NEEDS_MORE_EVIDENCE, not PASS
  7.  Auditability: every verdict is persisted to the JSONL trail
"""

import json
import sys
import tempfile
from pathlib import Path

# Ensure repo root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from skills.skill_coevolution import (
    CoEvolutionConfig,
    LedgerEntry,
    ProposalLedger,
    SkillEvolutionGate,
    SurrogateVerifier,
    VerifierSignal,
    VerifierVerdict,
    create_skill_evolution_gate,
)


# ==================== TESTS: Value Objects ====================


class TestValueObjects:
    def test_verifier_verdict_values(self):
        assert VerifierVerdict.PASS.value == "pass"
        assert VerifierVerdict.FAIL.value == "fail"
        assert VerifierVerdict.NEEDS_MORE_EVIDENCE.value == "needs_more_evidence"
        assert VerifierVerdict.BLOCKED_BY_BRAKE.value == "blocked_by_brake"

    def test_signal_observed_success_rate_no_uses(self):
        s = VerifierSignal(skill_id="s1")
        assert s.observed_success_rate == 0.0

    def test_signal_observed_success_rate_with_data(self):
        s = VerifierSignal(
            skill_id="s1",
            observed_uses=10,
            observed_success_count=8,
            observed_failure_count=2,
        )
        assert abs(s.observed_success_rate - 0.8) < 1e-9

    def test_signal_candidate_signature_stable(self):
        s1 = VerifierSignal(
            skill_id="s1",
            action_template=["step1", "step2"],
            parameter_schema={"a": "str", "b": "int"},
        )
        s2 = VerifierSignal(
            skill_id="s2",  # different id, same content
            action_template=["step1", "step2"],
            parameter_schema={"a": "str", "b": "int"},
        )
        assert s1.candidate_signature == s2.candidate_signature
        assert len(s1.candidate_signature) == 16

    def test_signal_candidate_signature_differs_for_different_content(self):
        s1 = VerifierSignal(skill_id="s1", action_template=["a", "b"])
        s2 = VerifierSignal(skill_id="s1", action_template=["a", "b", "c"])
        assert s1.candidate_signature != s2.candidate_signature

    def test_config_defaults_are_conservative(self):
        cfg = CoEvolutionConfig()
        assert cfg.min_uses == 3
        assert cfg.min_success_rate == 0.6
        assert cfg.max_risk_band == "high"
        assert cfg.block_on_disputed_evidence is True
        assert cfg.persist_audit is True


# ==================== TESTS: SurrogateVerifier ====================


class TestSurrogateVerifier:
    def _signal(self, **kw) -> VerifierSignal:
        defaults = dict(
            skill_id="s1",
            skill_name="Test",
            observed_uses=10,
            observed_success_count=8,
            observed_failure_count=2,
        )
        defaults.update(kw)
        return VerifierSignal(**defaults)

    def test_pass_when_all_gates_clear(self):
        v = SurrogateVerifier()
        verdict, rationale = v.evaluate(self._signal())
        assert verdict == VerifierVerdict.PASS
        assert "All gates clear" in rationale

    def test_needs_more_evidence_when_underused(self):
        v = SurrogateVerifier()
        verdict, _ = v.evaluate(self._signal(observed_uses=1, observed_success_count=1, observed_failure_count=0))
        assert verdict == VerifierVerdict.NEEDS_MORE_EVIDENCE

    def test_fail_when_success_rate_low(self):
        cfg = CoEvolutionConfig(min_uses=2, min_success_rate=0.7)
        v = SurrogateVerifier(config=cfg)
        verdict, _ = v.evaluate(self._signal(observed_uses=10, observed_success_count=4, observed_failure_count=6))
        assert verdict == VerifierVerdict.FAIL

    def test_fail_when_risk_exceeds_config(self):
        cfg = CoEvolutionConfig(max_risk_band="low")
        v = SurrogateVerifier(config=cfg)
        # No target_file -> medium risk -> exceeds "low"
        verdict, _ = v.evaluate(self._signal())
        assert verdict == VerifierVerdict.FAIL

    def test_block_on_disputed_evidence(self):
        cfg = CoEvolutionConfig(block_on_disputed_evidence=True)
        v = SurrogateVerifier(config=cfg)
        # We can't easily fabricate a disputed ledger here without wiring
        # the real EvidenceLedger, so we pass through the disputed-evidence
        # branch by checking the gate-level integration test below.
        # But we CAN verify the config flag is read.
        assert cfg.block_on_disputed_evidence is True


# ==================== TESTS: ProposalLedger ====================


class TestProposalLedger:
    def _signal(self, skill_id="s1") -> VerifierSignal:
        return VerifierSignal(skill_id=skill_id, observed_uses=10, observed_success_count=8, observed_failure_count=2)

    def test_empty_ledger(self):
        ledger = ProposalLedger()
        assert len(ledger) == 0
        assert ledger.recent() == []
        assert ledger.history_for("any") == []

    def test_append_and_history_for(self):
        from skills.skill_coevolution import _GateBrakeState

        ledger = ProposalLedger()
        ledger.append(
            proposal_id="p1",
            signal=self._signal("s1"),
            verdict=VerifierVerdict.PASS,
            rationale="ok",
            brake_state=_GateBrakeState.DAMPED,
        )
        ledger.append(
            proposal_id="p2",
            signal=self._signal("s1"),
            verdict=VerifierVerdict.FAIL,
            rationale="low",
            brake_state=_GateBrakeState.DAMPED,
        )
        assert len(ledger) == 2
        history = ledger.history_for("s1")
        assert [h.verdict for h in history] == ["pass", "fail"]

    def test_recent_returns_last_n(self):
        from skills.skill_coevolution import _GateBrakeState

        ledger = ProposalLedger()
        for i in range(15):
            ledger.append(
                proposal_id=f"p{i}",
                signal=self._signal(f"s{i}"),
                verdict=VerifierVerdict.PASS,
                rationale="ok",
                brake_state=_GateBrakeState.OPEN,
            )
        recent = ledger.recent(5)
        assert len(recent) == 5
        assert recent[0].proposal_id == "p10"
        assert recent[-1].proposal_id == "p14"

    def test_prior_verdict_is_recorded(self):
        from skills.skill_coevolution import _GateBrakeState

        ledger = ProposalLedger()
        ledger.append(
            proposal_id="p1",
            signal=self._signal("s1"),
            verdict=VerifierVerdict.PASS,
            rationale="first",
            brake_state=_GateBrakeState.OPEN,
        )
        e2 = ledger.append(
            proposal_id="p2",
            signal=self._signal("s1"),
            verdict=VerifierVerdict.FAIL,
            rationale="second",
            brake_state=_GateBrakeState.OPEN,
        )
        assert e2.prior_verdict == "pass"

    def test_first_entry_has_no_prior(self):
        from skills.skill_coevolution import _GateBrakeState

        ledger = ProposalLedger()
        e1 = ledger.append(
            proposal_id="p1",
            signal=self._signal("s1"),
            verdict=VerifierVerdict.PASS,
            rationale="first",
            brake_state=_GateBrakeState.OPEN,
        )
        assert e1.prior_verdict is None


# ==================== TESTS: SkillEvolutionGate ====================


class TestSkillEvolutionGate:
    def _signal(self, **kw) -> VerifierSignal:
        defaults = dict(
            skill_id="s1",
            observed_uses=10,
            observed_success_count=8,
            observed_failure_count=2,
        )
        defaults.update(kw)
        return VerifierSignal(**defaults)

    def test_default_brake_is_damped(self):
        gate = create_skill_evolution_gate()
        assert gate.brake.state.value == "damped"

    def test_pass_signal_blocked_by_damped_brake(self):
        gate = create_skill_evolution_gate()
        verdict, rationale = gate.evaluate(self._signal())
        # Verifier says PASS, brake (DAMPED) demotes to BLOCKED_BY_BRAKE
        assert verdict == VerifierVerdict.BLOCKED_BY_BRAKE
        assert "PASS demoted" in rationale

    def test_pass_signal_passes_under_open_brake(self):
        from skills.skill_coevolution import _GateBrakeState

        gate = create_skill_evolution_gate()
        gate.brake.transition(_GateBrakeState.OPEN, "test")
        verdict, _ = gate.evaluate(self._signal())
        assert verdict == VerifierVerdict.PASS

    def test_braked_blocks_everything(self):
        from skills.skill_coevolution import _GateBrakeState

        gate = create_skill_evolution_gate()
        gate.brake.transition(_GateBrakeState.BRAKED, "test")
        verdict, _ = gate.evaluate(self._signal())
        assert verdict == VerifierVerdict.BLOCKED_BY_BRAKE

    def test_summary_is_deterministic(self):
        gate = create_skill_evolution_gate()
        s = gate.summary()
        assert "brake=damped" in s
        assert "depth=0" in s
        assert "ledger=0" in s

    def test_audit_file_is_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "audit.jsonl"
            gate = create_skill_evolution_gate(audit_path=audit)
            gate.evaluate(self._signal())
            assert audit.exists()
            content = audit.read_text()
            assert "PASS" in content or "BLOCKED_BY_BRAKE" in content
            # JSONL format: one JSON object per line
            rows = [json.loads(line) for line in content.strip().split("\n") if line.strip()]
            assert len(rows) == 1
            assert "verdict" in rows[0]
            assert "brake_state" in rows[0]


# ==================== TESTS: Integration with Real EvidenceLedger ====================


class TestIntegrationWithRealLedger:
    def test_disputed_claim_forces_needs_more_evidence(self):
        from core.evidence_ledger import create_ledger

        ev_ledger = create_ledger()
        # A claim that will end up DISPUTED (both support and refute)
        c1 = ev_ledger.assert_claim("skill X is safe to promote")
        ev_ledger.add_support(c1.claim_id, "support1")
        ev_ledger.add_refute(c1.claim_id, "refute1")
        # Verify to populate status
        ev_ledger.verify(c1.claim_id)

        gate = create_skill_evolution_gate(evidence_ledger=ev_ledger)
        # OPEN brake so the only demoter is the verifier
        from skills.skill_coevolution import _GateBrakeState
        gate.brake.transition(_GateBrakeState.OPEN, "test")
        signal = VerifierSignal(
            skill_id="s1",
            observed_uses=10,
            observed_success_count=8,
            observed_failure_count=2,
            evidence_claim_ids=[c1.claim_id],
        )
        verdict, rationale = gate.evaluate(signal)
        assert verdict == VerifierVerdict.NEEDS_MORE_EVIDENCE
        assert "Disputed evidence" in rationale or "disputed" in rationale.lower()

    def test_grounded_claim_passes_under_open_brake(self):
        from core.evidence_ledger import create_ledger
        from skills.skill_coevolution import _GateBrakeState

        ev_ledger = create_ledger()
        c1 = ev_ledger.assert_claim("skill X is safe to promote")
        ev_ledger.add_support(c1.claim_id, "support1")
        ev_ledger.verify(c1.claim_id)

        gate = create_skill_evolution_gate(evidence_ledger=ev_ledger)
        gate.brake.transition(_GateBrakeState.OPEN, "test")
        signal = VerifierSignal(
            skill_id="s1",
            observed_uses=10,
            observed_success_count=8,
            observed_failure_count=2,
            evidence_claim_ids=[c1.claim_id],
        )
        verdict, _ = gate.evaluate(signal)
        assert verdict == VerifierVerdict.PASS

    def test_no_claim_cited_is_ungrounded(self):
        from skills.skill_coevolution import _GateBrakeState

        gate = create_skill_evolution_gate()
        gate.brake.transition(_GateBrakeState.OPEN, "test")
        signal = VerifierSignal(
            skill_id="s1",
            observed_uses=10,
            observed_success_count=8,
            observed_failure_count=2,
            evidence_claim_ids=[],
        )
        verdict, _ = gate.evaluate(signal)
        # Empty claim list -> ungrounded -> still passes (no dispute)
        # because the gate only demotes on DISPUTED, not UNGROUNDED.
        assert verdict == VerifierVerdict.PASS


# ==================== TESTS: Conservative Posture ====================


class TestConservativePosture:
    def test_marginal_signal_becomes_needs_more_evidence_not_pass(self):
        v = SurrogateVerifier()
        # Just below min_uses
        signal = VerifierSignal(
            skill_id="s1",
            observed_uses=2,  # < min_uses=3
            observed_success_count=2,
            observed_failure_count=0,
        )
        verdict, _ = v.evaluate(signal)
        assert verdict == VerifierVerdict.NEEDS_MORE_EVIDENCE

    def test_low_success_rate_is_fail_not_pass(self):
        cfg = CoEvolutionConfig(min_uses=2, min_success_rate=0.6)
        v = SurrogateVerifier(config=cfg)
        signal = VerifierSignal(
            skill_id="s1",
            observed_uses=10,
            observed_success_count=3,
            observed_failure_count=7,
        )
        verdict, _ = v.evaluate(signal)
        assert verdict == VerifierVerdict.FAIL

    def test_under_min_uses_takes_precedence_over_success_rate(self):
        v = SurrogateVerifier()
        # High success rate but few uses -> still underused
        signal = VerifierSignal(
            skill_id="s1",
            observed_uses=1,
            observed_success_count=1,
            observed_failure_count=0,
        )
        verdict, _ = v.evaluate(signal)
        assert verdict == VerifierVerdict.NEEDS_MORE_EVIDENCE

    def test_brake_demotion_is_audited_in_rationale(self):
        gate = create_skill_evolution_gate()
        signal = VerifierSignal(
            skill_id="s1",
            observed_uses=10,
            observed_success_count=8,
            observed_failure_count=2,
        )
        verdict, rationale = gate.evaluate(signal)
        assert verdict == VerifierVerdict.BLOCKED_BY_BRAKE
        assert "damped" in rationale
        assert "PASS demoted" in rationale


# ==================== TESTS: Auditability ====================


class TestAuditability:
    def test_every_verdict_appears_in_audit(self):
        from skills.skill_coevolution import _GateBrakeState

        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "audit.jsonl"
            gate = create_skill_evolution_gate(audit_path=audit)
            gate.brake.transition(_GateBrakeState.OPEN, "test")

            signals = [
                VerifierSignal(
                    skill_id=f"s{i}",
                    observed_uses=10,
                    observed_success_count=8,
                    observed_failure_count=2,
                )
                for i in range(5)
            ]
            for s in signals:
                gate.evaluate(s)

            content = audit.read_text()
            rows = [json.loads(line) for line in content.strip().split("\n") if line.strip()]
            assert len(rows) == 5
            for row in rows:
                assert "verdict" in row
                assert "brake_state" in row
                assert row["brake_state"] == "open"

    def test_audit_records_brake_state_at_submission(self):
        from skills.skill_coevolution import _GateBrakeState

        with tempfile.TemporaryDirectory() as tmp:
            audit = Path(tmp) / "audit.jsonl"
            gate = create_skill_evolution_gate(audit_path=audit)

            # First: DAMPED (default)
            gate.evaluate(VerifierSignal(skill_id="s1", observed_uses=10, observed_success_count=8, observed_failure_count=2))
            # Then: OPEN
            gate.brake.transition(_GateBrakeState.OPEN, "test")
            gate.evaluate(VerifierSignal(skill_id="s2", observed_uses=10, observed_success_count=8, observed_failure_count=2))

            rows = [json.loads(line) for line in audit.read_text().strip().split("\n") if line.strip()]
            assert rows[0]["brake_state"] == "damped"
            assert rows[1]["brake_state"] == "open"

    def test_audit_path_default(self):
        gate = create_skill_evolution_gate()
        default = gate.audit_path_default()
        assert "skill_evolution_" in str(default)
        assert str(default).endswith(".jsonl")


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header"])
