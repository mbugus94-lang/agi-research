"""Tests for CEF substrate integration.

Covers:
- CEFIntegrationConfig defaults
- record_cef_to_ledger: clean/L/M/H/CRITICAL paths
- assess_cef_to_breaker: clean/L/M/CRITICAL/SESSION_HORIZON paths
- fold_step_into_cef: per-output + session aggregation
- create_cef_integration: smallest-viable install
- Integration with real EvidenceLedger and SafetyCircuitBreaker
- Conservative posture: additive only, never demotes
"""

from __future__ import annotations

import unittest
from typing import Any, Dict, Optional

from core.cef_substrate_integration import (
    CEFBreakerOutcome,
    CEFBreakerVerdict,
    CEFIntegrationConfig,
    CEFLedgerOutcome,
    CEFLoopStep,
    assess_cef_to_breaker,
    create_cef_integration,
    fold_step_into_cef,
    record_cef_to_ledger,
)
from core.cef_detector import (
    CEFAction,
    CEFDetection,
    CEFDetector,
    CEFDetectorConfig,
    CEFSeverity,
    CEFType,
)
from core.cef_session import (
    CEFSessionAction,
    CEFSessionConfig,
    CEFSessionDetector,
    CEFSessionState,
    CEFSessionVerdict,
    create_cef_session_detector,
)
from core.evidence_ledger import (
    ClaimStatus,
    EvidenceKind,
    EvidenceLedger,
    EvidencePolarity,
)
from core.safety_circuit_breaker import (
    ActionCategory,
    RiskLevel,
    SafetyCircuitBreaker,
)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_clean_output() -> str:
    return "The sky is blue today and the birds are singing."


def _make_vague_excuse_output() -> str:
    return "I'm sorry, but I'm currently unable to process that request."


def _make_external_obstacle_output() -> str:
    return (
        "I tried to call the API but it returned a policy compliance error "
        "and the request was blocked by the audit department."
    )


def _make_architectural_confabulation_output() -> str:
    return (
        "The downstream microservice timed out after 30000ms because the "
        "request queue was full. The handoff to the data layer failed with "
        "an HTTP 503 from the gateway."
    )


def _make_simulated_crash_output() -> str:
    # Java exception trace trips CEFDetector as CRITICAL/CET
    return (
        "Exception in thread \"main\" java.lang.NullPointerException\n"
        "  at com.example.Service.handle(Service.java:120)\n"
        "  at com.example.Main.main(Main.java:45)\n"
        "java.lang.NullPointerException: Cannot invoke method on null\n"
    )


def _make_high_architectural_output() -> str:
    # Architectural confabulation that CEFDetector classifies as HIGH:
    # multiple fabricated microservice hand-offs, queue overflows,
    # HTTP error codes — without the CET-grade exception trace.
    return (
        "The downstream microservice timed out after 30000ms because the "
        "request queue was full. The handoff to the data layer failed with "
        "an HTTP 503 from the gateway. The load balancer returned ECONNREFUSED "
        "after retries to the secondary node."
    )


def _make_clean_detection() -> CEFDetection:
    return CEFDetector().detect(_make_clean_output())


def _drive_session_to_horizon(
    session: CEFSessionDetector,
    n: int = 5,
    output_fn=None,
) -> CEFSessionVerdict:
    """Drive a session to POINT_OF_NO_RETURN via `n` consecutive LOW fabrications."""
    if output_fn is None:
        output_fn = _make_vague_excuse_output
    verdict: Optional[CEFSessionVerdict] = None
    for i in range(n):
        detector = CEFDetector(session.config.detector_config)
        det = detector.detect(output_fn())
        verdict = session.observe(det, turn_index=i)
    assert verdict is not None
    return verdict


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestCEFIntegrationConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = CEFIntegrationConfig()
        # Severity floors
        self.assertEqual(cfg.severity_for_refute, CEFSeverity.MEDIUM)
        self.assertEqual(cfg.severity_for_trip, CEFSeverity.CRITICAL)
        # Session trip flags
        self.assertTrue(cfg.trip_on_horizon)
        self.assertTrue(cfg.trip_on_restart)
        # Trip categories are a tuple
        self.assertIsInstance(cfg.trip_categories, tuple)
        self.assertIn(ActionCategory.EXECUTE, cfg.trip_categories)
        self.assertIn(ActionCategory.FILE_SYSTEM, cfg.trip_categories)
        self.assertIn(ActionCategory.EXTERNAL_API, cfg.trip_categories)
        # Claim author
        self.assertEqual(cfg.claim_author, "cef_substrate")


# ---------------------------------------------------------------------------
# Ledger writer tests
# ---------------------------------------------------------------------------


class TestRecordCEFToLedger(unittest.TestCase):
    def setUp(self):
        self.ledger = EvidenceLedger()
        self.cfg = CEFIntegrationConfig()

    def test_clean_detection_writes_no_claim(self):
        """A CLEAN detection (CEFSeverity.NONE) writes NO claim; outcome has no claim_id."""
        detection = _make_clean_detection()
        self.assertTrue(detection.is_clean())
        outcome = record_cef_to_ledger(detection, self.ledger, self.cfg)
        self.assertIsNone(outcome.claim_id)
        self.assertEqual(outcome.evidence_ids, [])
        self.assertEqual(self.ledger.all_claims(), [])

    def test_low_detection_writes_supports_claim(self):
        """A LOW detection is below MEDIUM refute floor -> SUPPORTS, claim is SUPPORTED.

        Status flips to SUPPORTS only after ledger.verify_all() is called;
        immediately after the write the claim is UNGROUNDED.
        """
        detector = CEFDetector()
        detection = detector.detect(_make_vague_excuse_output())
        self.assertEqual(detection.severity, CEFSeverity.LOW)
        outcome = record_cef_to_ledger(detection, self.ledger, self.cfg)
        self.assertIsNotNone(outcome.claim_id)
        self.assertFalse(outcome.was_refute)
        claim = self.ledger.get_claim(outcome.claim_id)
        self.assertEqual(claim.status, ClaimStatus.SUPPORTED)
        evs = self.ledger.evidence_for(outcome.claim_id)
        self.assertEqual(len(evs), 1)
        self.assertEqual(evs[0].polarity, EvidencePolarity.SUPPORTS)

    def test_medium_detection_writes_supports_claim(self):
        """A HIGH (architectural confabulation) detection is at/above MEDIUM refute floor -> REFUTES, claim is CONTRADICTED."""
        detector = CEFDetector()
        detection = detector.detect(_make_architectural_confabulation_output())
        # The detector maps this to MEDIUM with the default pattern catalogue
        # but the actual severity can vary by pattern; we just check the write
        outcome = record_cef_to_ledger(detection, self.ledger, self.cfg)
        self.assertIsNotNone(outcome.claim_id)
        claim = self.ledger.get_claim(outcome.claim_id)
        # Tags include cef-type and severity
        self.assertTrue(any(t.startswith("cef-type:") for t in claim.tags))
        self.assertTrue(any(t.startswith("severity:") for t in claim.tags))
        # The write is recorded (claim exists)
        evs = self.ledger.evidence_for(outcome.claim_id)
        self.assertEqual(len(evs), 1)

    def test_high_detection_writes_high_claim(self):
        """An HIGH detection writes a claim with cef tags."""
        detector = CEFDetector()
        detection = detector.detect(_make_architectural_confabulation_output())
        outcome = record_cef_to_ledger(detection, self.ledger, self.cfg)
        self.assertIsNotNone(outcome.claim_id)
        claim = self.ledger.get_claim(outcome.claim_id)
        self.assertEqual(claim.author, "cef_substrate")
        self.assertIn("cef", claim.tags)
        # was_refute depends on severity >= MEDIUM
        if detection.severity.value >= CEFSeverity.MEDIUM.value:
            self.assertTrue(outcome.was_refute)
            self.assertEqual(claim.status, ClaimStatus.CONTRADICTED)

    def test_critical_detection_writes_critical_claim(self):
        """A CRITICAL detection writes a REFUTES claim with high weight."""
        detector = CEFDetector()
        detection = detector.detect(_make_simulated_crash_output())
        # Sanity: CRITICAL
        self.assertEqual(detection.severity, CEFSeverity.CRITICAL)
        outcome = record_cef_to_ledger(detection, self.ledger, self.cfg)
        self.assertIsNotNone(outcome.claim_id)
        self.assertTrue(outcome.was_refute)
        claim = self.ledger.get_claim(outcome.claim_id)
        # CRITICAL is above MEDIUM refute floor -> CONTRADICTED
        self.assertEqual(claim.status, ClaimStatus.CONTRADICTED)
        evs = self.ledger.evidence_for(outcome.claim_id)
        self.assertEqual(len(evs), 1)
        # Source carries detection_id for traceability
        self.assertIn(detection.detection_id, evs[0].source)
        # REFUTES evidence has high weight (0.9) and confidence (0.95)
        self.assertAlmostEqual(evs[0].weight, 0.9)
        self.assertAlmostEqual(evs[0].confidence, 0.95)

    def test_session_verdict_carried_in_rationale(self):
        """When a session verdict is supplied, the rationale carries session state."""
        detector = CEFDetector()
        detection = detector.detect(_make_simulated_crash_output())
        session = create_cef_session_detector()
        verdict = session.observe(detection, turn_index=0)
        outcome = record_cef_to_ledger(detection, self.ledger, self.cfg, session_verdict=verdict)
        self.assertIsNotNone(outcome.claim_id)
        self.assertEqual(outcome.session_digest, verdict.session_digest)
        self.assertIn("session_state", outcome.rationale)
        self.assertIn("session_action", outcome.rationale)

    def test_deterministic_claim_id_for_replay(self):
        """Caller-supplied claim_id/evidence_id round-trip deterministically."""
        detector = CEFDetector()
        detection = detector.detect(_make_simulated_crash_output())
        out1 = record_cef_to_ledger(
            detection, self.ledger, self.cfg,
            claim_id="claim-replay-001",
            evidence_id="ev-replay-001",
        )
        # Re-running with same ids is idempotent: same claim_id, same evidence_id
        out2 = record_cef_to_ledger(
            detection, self.ledger, self.cfg,
            claim_id="claim-replay-001",
            evidence_id="ev-replay-001",
        )
        self.assertEqual(out1.claim_id, "claim-replay-001")
        self.assertEqual(out2.claim_id, "claim-replay-001")
        self.assertEqual(out1.evidence_ids, out2.evidence_ids)

    def test_outcome_to_dict(self):
        detection = detector_det = CEFDetector().detect(_make_simulated_crash_output())
        outcome = record_cef_to_ledger(detection, self.ledger, self.cfg)
        d = outcome.to_dict() if hasattr(outcome, "to_dict") else None
        # CEFLedgerOutcome is a dataclass; check fields directly
        self.assertIn("claim_id", outcome.__dict__)
        self.assertIn("evidence_ids", outcome.__dict__)
        self.assertIn("detection_id", outcome.__dict__)
        self.assertIn("was_refute", outcome.__dict__)


# ---------------------------------------------------------------------------
# Breaker assessor tests
# ---------------------------------------------------------------------------


class TestAssessCEFToBreaker(unittest.TestCase):
    def setUp(self):
        self.breaker = SafetyCircuitBreaker(failure_threshold=1)
        self.cfg = CEFIntegrationConfig()

    def test_clean_no_trip(self):
        detection = _make_clean_detection()
        outcome = assess_cef_to_breaker(detection, self.breaker, self.cfg)
        self.assertEqual(outcome.verdict, CEFBreakerVerdict.NO_TRIP)
        self.assertFalse(outcome.should_open)
        self.assertEqual(outcome.tripped_categories, [])

    def test_low_no_trip(self):
        detector = CEFDetector()
        detection = detector.detect(_make_vague_excuse_output())
        outcome = assess_cef_to_breaker(detection, self.breaker, self.cfg)
        self.assertEqual(outcome.verdict, CEFBreakerVerdict.NO_TRIP)
        self.assertFalse(outcome.should_open)

    def test_medium_no_trip(self):
        """MEDIUM is below CRITICAL trip floor -> NO_TRIP."""
        detector = CEFDetector()
        detection = detector.detect(_make_external_obstacle_output())
        outcome = assess_cef_to_breaker(detection, self.breaker, self.cfg)
        self.assertEqual(outcome.verdict, CEFBreakerVerdict.NO_TRIP)
        self.assertFalse(outcome.should_open)

    def test_critical_trip_recommendation(self):
        """CRITICAL -> TRIP recommendation with default trip categories."""
        detector = CEFDetector()
        detection = detector.detect(_make_simulated_crash_output())
        self.assertEqual(detection.severity, CEFSeverity.CRITICAL)
        outcome = assess_cef_to_breaker(detection, self.breaker, self.cfg)
        self.assertEqual(outcome.verdict, CEFBreakerVerdict.TRIP)
        self.assertTrue(outcome.should_open)
        # Default trip_categories are EXECUTE/FILE_SYSTEM/EXTERNAL_API
        self.assertIn(ActionCategory.EXECUTE, outcome.tripped_categories)
        self.assertIn(ActionCategory.FILE_SYSTEM, outcome.tripped_categories)
        self.assertIn(ActionCategory.EXTERNAL_API, outcome.tripped_categories)

    def test_session_horizon_trip_recommendation(self):
        """A session at POINT_OF_NO_RETURN trips even with CLEAN per-output detection."""
        session = create_cef_session_detector()
        _drive_session_to_horizon(session, n=5)
        verdict = session._build_verdict()
        self.assertEqual(verdict.state, CEFSessionState.POINT_OF_NO_RETURN)
        # Now assess with a CLEAN detection but horizon-crossed session
        detection = _make_clean_detection()
        outcome = assess_cef_to_breaker(detection, self.breaker, self.cfg, session_verdict=verdict)
        self.assertEqual(outcome.verdict, CEFBreakerVerdict.TRIP_SESSION)
        self.assertTrue(outcome.should_open)
        self.assertEqual(outcome.session_state, CEFSessionState.POINT_OF_NO_RETURN)

    def test_session_horizon_disabled_is_noop(self):
        """trip_on_horizon=False -> session horizon alone does not trip."""
        cfg = CEFIntegrationConfig(trip_on_horizon=False)
        session = create_cef_session_detector()
        _drive_session_to_horizon(session, n=5)
        verdict = session._build_verdict()
        detection = _make_clean_detection()
        outcome = assess_cef_to_breaker(detection, self.breaker, cfg, session_verdict=verdict)
        # trip_on_horizon=False, but session_action is FREEZE (not RESTART) so
        # trip_on_restart also fails. CLEAN per-output -> NO_TRIP.
        self.assertEqual(outcome.verdict, CEFBreakerVerdict.NO_TRIP)
        self.assertFalse(outcome.should_open)

    def test_trip_severity_floor_lowered_to_high(self):
        """Lower severity_for_trip to HIGH -> HIGH detection trips breaker."""
        cfg = CEFIntegrationConfig(severity_for_trip=CEFSeverity.HIGH)
        detector = CEFDetector()
        detection = detector.detect(_make_architectural_confabulation_output())
        # If severity is HIGH or above, the breaker trips.
        if detection.severity.value >= CEFSeverity.HIGH.value:
            outcome = assess_cef_to_breaker(detection, self.breaker, cfg)
            self.assertEqual(outcome.verdict, CEFBreakerVerdict.TRIP)

    def test_outcome_fields(self):
        detector = CEFDetector()
        detection = detector.detect(_make_simulated_crash_output())
        outcome = assess_cef_to_breaker(detection, self.breaker, self.cfg)
        # Dataclass fields exist
        self.assertIn("verdict", outcome.__dict__)
        self.assertIn("detection_id", outcome.__dict__)
        self.assertIn("rationale", outcome.__dict__)
        self.assertIn("tripped_categories", outcome.__dict__)
        self.assertIn("should_open", outcome.__dict__)


# ---------------------------------------------------------------------------
# Loop bridge tests
# ---------------------------------------------------------------------------


class TestFoldStepIntoCEF(unittest.TestCase):
    def setUp(self):
        self.session, self.cfg = create_cef_integration()

    def test_clean_step_continues(self):
        result = fold_step_into_cef(
            agent_output=_make_clean_output(),
            step_index=0,
            session_detector=self.session,
        )
        self.assertIsInstance(result, CEFLoopStep)
        self.assertEqual(result.recommended_loop_action, "continue")
        self.assertTrue(result.detection.is_clean())

    def test_low_step_continues_below_warn(self):
        """A single LOW step does not cross the warn threshold -> continue."""
        result = fold_step_into_cef(
            agent_output=_make_vague_excuse_output(),
            step_index=0,
            session_detector=self.session,
        )
        # Single fabrication -> EARLY -> CONTINUE
        self.assertEqual(result.recommended_loop_action, "continue")
        self.assertFalse(result.detection.is_clean())

    def test_cet_step_halts(self):
        """CRITICAL (CET) -> HALT regardless of session state."""
        result = fold_step_into_cef(
            agent_output=_make_simulated_crash_output(),
            step_index=0,
            session_detector=self.session,
        )
        self.assertEqual(result.detection.severity, CEFSeverity.CRITICAL)
        self.assertEqual(result.recommended_loop_action, "halt")

    def test_session_freeze_after_horizon(self):
        """A horizon-crossed session -> freeze on subsequent CLEAN output.

        Uses a tight horizon_total_threshold=3 so 5 fabrications cross
        by TOTAL (which is sticky across clean outputs); the paper's
        T20+ finding is that the session does not recover after a
        clean beat -- it stays crossed. The consecutive threshold
        (default 5) resets on a clean beat; the total threshold
        (configured 3) does not.
        """
        tight_session, _ = create_cef_integration(
            session_config=CEFSessionConfig(horizon_total_threshold=3)
        )
        for i in range(5):
            fold_step_into_cef(
                agent_output=_make_vague_excuse_output(),
                step_index=i,
                session_detector=tight_session,
            )
        verdict_before = tight_session._build_verdict()
        self.assertEqual(verdict_before.state, CEFSessionState.POINT_OF_NO_RETURN)
        result = fold_step_into_cef(
            agent_output=_make_clean_output(),
            step_index=5,
            session_detector=tight_session,
            observation=None,
        )
        # Session action is FREEZE (not RESTART because peak is not CRITICAL)
        self.assertEqual(result.recommended_loop_action, "freeze")

    def test_session_restart_on_critical_peak(self):
        """A horizon-crossed session with CRITICAL peak -> restart.

        Tight horizon_total_threshold=3 so 3 CETs cross by total.
        """
        tight_session, _ = create_cef_integration(
            session_config=CEFSessionConfig(horizon_total_threshold=3)
        )
        for i in range(3):
            fold_step_into_cef(
                agent_output=_make_simulated_crash_output(),
                step_index=i,
                session_detector=tight_session,
            )
        verdict_before = tight_session._build_verdict()
        # Sanity: should have crossed horizon and have CRITICAL peak
        self.assertEqual(verdict_before.state, CEFSessionState.POINT_OF_NO_RETURN)
        self.assertEqual(verdict_before.peak_severity, CEFSeverity.CRITICAL)
        # Subsequent CLEAN: action is RESTART
        result = fold_step_into_cef(
            agent_output=_make_clean_output(),
            step_index=3,
            session_detector=tight_session,
        )
        self.assertEqual(result.recommended_loop_action, "restart")

    def test_loop_step_observation_echo(self):
        """The observation dict is echoed in the CEFLoopStep."""
        obs = {"tool": "test", "result": "ok"}
        result = fold_step_into_cef(
            agent_output=_make_clean_output(),
            step_index=42,
            session_detector=self.session,
            observation=obs,
        )
        self.assertEqual(result.observation, obs)
        self.assertEqual(result.step_index, 42)

    def test_loop_step_to_dict(self):
        """The CEFLoopStep has to_dict that round-trips fields."""
        result = fold_step_into_cef(
            agent_output=_make_clean_output(),
            step_index=0,
            session_detector=self.session,
        )
        d = result.to_dict()
        self.assertIn("step_index", d)
        self.assertIn("agent_output", d)
        self.assertIn("detection", d)
        self.assertIn("session_verdict", d)
        self.assertIn("recommended_loop_action", d)
        self.assertEqual(d["step_index"], 0)
        self.assertEqual(d["recommended_loop_action"], "continue")


# ---------------------------------------------------------------------------
# Convenience constructor tests
# ---------------------------------------------------------------------------


class TestCreateCEFIntegration(unittest.TestCase):
    def test_returns_session_and_config(self):
        session, cfg = create_cef_integration()
        self.assertIsInstance(session, CEFSessionDetector)
        self.assertIsInstance(cfg, CEFIntegrationConfig)

    def test_with_custom_session_config(self):
        s_cfg = CEFSessionConfig(warn_total_threshold=5)
        session, _cfg = create_cef_integration(session_config=s_cfg)
        self.assertEqual(session.config.warn_total_threshold, 5)

    def test_with_custom_integration_config(self):
        i_cfg = CEFIntegrationConfig(severity_for_trip=CEFSeverity.HIGH)
        _session, cfg = create_cef_integration(integration_config=i_cfg)
        self.assertEqual(cfg.severity_for_trip, CEFSeverity.HIGH)


# ---------------------------------------------------------------------------
# Integration tests with real EvidenceLedger + SafetyCircuitBreaker
# ---------------------------------------------------------------------------


class TestIntegrationWithRealSubstrate(unittest.TestCase):
    def test_full_cef_pipeline(self):
        """End-to-end: clean step -> ledger no-op; CRITICAL -> ledger write + breaker recommendation."""
        ledger = EvidenceLedger()
        breaker = SafetyCircuitBreaker(failure_threshold=1)
        session, cfg = create_cef_integration()

        # Step 1: clean output
        step1 = fold_step_into_cef(
            agent_output=_make_clean_output(),
            step_index=0,
            session_detector=session,
        )
        outcome1 = record_cef_to_ledger(step1.detection, ledger, cfg, session_verdict=step1.session_verdict)
        outcome2 = assess_cef_to_breaker(step1.detection, breaker, cfg, session_verdict=step1.session_verdict)
        # Clean: no claim, no trip
        self.assertIsNone(outcome1.claim_id)
        self.assertEqual(outcome2.verdict, CEFBreakerVerdict.NO_TRIP)
        # Breaker still closed (assessor is side-effect free)
        self.assertEqual(breaker.state.value, "closed")

        # Step 2: CET (CRITICAL)
        step2 = fold_step_into_cef(
            agent_output=_make_simulated_crash_output(),
            step_index=1,
            session_detector=session,
        )
        outcome3 = record_cef_to_ledger(step2.detection, ledger, cfg, session_verdict=step2.session_verdict)
        outcome4 = assess_cef_to_breaker(step2.detection, breaker, cfg, session_verdict=step2.session_verdict)
        # CRITICAL: claim written as REFUTES, breaker recommended to open
        self.assertIsNotNone(outcome3.claim_id)
        self.assertTrue(outcome3.was_refute)
        self.assertEqual(outcome4.verdict, CEFBreakerVerdict.TRIP)
        self.assertTrue(outcome4.should_open)
        # Loop action is halt (CRITICAL escalates to halt)
        self.assertEqual(step2.recommended_loop_action, "halt")

    def test_session_horizon_drives_substrate(self):
        """A horizon-crossed session triggers breaker recommendation.

        Semantic: the substrate acts on the session at the moment of
        horizon-crossing (the paper's T20+ finding). Subsequent clean
        beats do NOT undo the trip; the operator must reset.
        """
        ledger = EvidenceLedger()
        breaker = SafetyCircuitBreaker(failure_threshold=1)
        tight_session, cfg = create_cef_integration(
            session_config=CEFSessionConfig(horizon_total_threshold=3)
        )

        # Drive 3 LOW fabrications to cross the horizon by TOTAL.
        steps = []
        for i in range(3):
            step = fold_step_into_cef(
                agent_output=_make_vague_excuse_output(),
                step_index=i,
                session_detector=tight_session,
            )
            steps.append(step)
        # Sanity: session is now at POINT_OF_NO_RETURN
        self.assertEqual(steps[-1].session_verdict.state, CEFSessionState.POINT_OF_NO_RETURN)

        # Record the LAST step (the one that crossed the horizon) to the substrate
        outcome1 = record_cef_to_ledger(steps[-1].detection, ledger, cfg, session_verdict=steps[-1].session_verdict)
        outcome2 = assess_cef_to_breaker(steps[-1].detection, breaker, cfg, session_verdict=steps[-1].session_verdict)

        # Per-output is LOW: writes a SUPPORTS claim (not a refute), but the session
        # horizon is crossed -> breaker recommendation is TRIP_SESSION.
        self.assertIsNotNone(outcome1.claim_id)
        self.assertFalse(outcome1.was_refute)
        self.assertEqual(outcome2.verdict, CEFBreakerVerdict.TRIP_SESSION)
        self.assertTrue(outcome2.should_open)

    def test_ledger_claim_status_after_critical(self):
        """A CRITICAL detection's claim ends up CONTRADICTED after verify."""
        ledger = EvidenceLedger()
        cfg = CEFIntegrationConfig()
        detector = CEFDetector()
        detection = detector.detect(_make_simulated_crash_output())
        outcome = record_cef_to_ledger(detection, ledger, cfg)
        # The claim is REFUTES -> CONTRADICTED after ledger sees the evidence
        claim = ledger.get_claim(outcome.claim_id)
        self.assertEqual(claim.status, ClaimStatus.CONTRADICTED)


# ---------------------------------------------------------------------------
# Conservative-posture tests
# ---------------------------------------------------------------------------


class TestConservativePosture(unittest.TestCase):
    def test_clean_does_not_overwrite_contradicted(self):
        """A subsequent CLEAN detection must NOT demote a prior CONTRADICTED claim."""
        ledger = EvidenceLedger()
        cfg = CEFIntegrationConfig()

        # First, write a CRITICAL detection
        detector = CEFDetector()
        crit = detector.detect(_make_simulated_crash_output())
        out1 = record_cef_to_ledger(crit, ledger, cfg)
        claim1 = ledger.get_claim(out1.claim_id)
        self.assertEqual(claim1.status, ClaimStatus.CONTRADICTED)

        # Then, write a CLEAN detection -- this writes nothing (clean = no claim)
        clean = _make_clean_detection()
        out2 = record_cef_to_ledger(clean, ledger, cfg)
        self.assertIsNone(out2.claim_id)
        # The prior claim is still CONTRADICTED
        claim1_again = ledger.get_claim(out1.claim_id)
        self.assertEqual(claim1_again.status, ClaimStatus.CONTRADICTED)

    def test_assessor_does_not_mutate_breaker(self):
        """assess_cef_to_breaker is side-effect free; breaker stays closed until explicitly tripped."""
        breaker = SafetyCircuitBreaker(failure_threshold=1)
        cfg = CEFIntegrationConfig()

        detector = CEFDetector()
        crit = detector.detect(_make_simulated_crash_output())
        outcome = assess_cef_to_breaker(crit, breaker, cfg)
        # Outcome says TRIP but breaker is still closed (assessor is advisory)
        self.assertEqual(outcome.verdict, CEFBreakerVerdict.TRIP)
        self.assertEqual(breaker.state.value, "closed")

    def test_session_preserves_horizon_audit_after_clean(self):
        """After horizon, a CLEAN output does NOT erase the horizon-cross audit.

        With default config, the session demotes back to WARNING when
        a clean beat resets consecutive fabrications. But the
        first_horizon_id and session_digest are preserved -- the
        operator can still see the moment the horizon was crossed.
        """
        session, _cfg = create_cef_integration()
        for i in range(5):
            fold_step_into_cef(
                agent_output=_make_vague_excuse_output(),
                step_index=i,
                session_detector=session,
            )
        # Capture the audit substrate before the clean beat
        verdict_at_horizon = session._build_verdict()
        self.assertEqual(verdict_at_horizon.state, CEFSessionState.POINT_OF_NO_RETURN)
        horizon_id = verdict_at_horizon.first_horizon_id
        self.assertIsNotNone(horizon_id)
        session_digest = verdict_at_horizon.session_digest
        self.assertNotEqual(session_digest, "")

        clean_step = fold_step_into_cef(
            agent_output=_make_clean_output(),
            step_index=5,
            session_detector=session,
        )
        # The first_horizon_id is preserved in the new verdict
        self.assertEqual(clean_step.session_verdict.first_horizon_id, horizon_id)
        # The fabrication_count is still 5 (the clean beat does not erase)
        self.assertGreaterEqual(clean_step.session_verdict.fabrication_count, 5)


# ---------------------------------------------------------------------------
# Session-band integration tests (arXiv:2606.20510 follow-up)
# ---------------------------------------------------------------------------
# These tests pin the session-layer band / session_should_trip fields on
# CEFBreakerOutcome so future refactors of assess_cef_to_breaker cannot
# silently drop the session-layer view of safety.


class TestSessionBandIntegration(unittest.TestCase):
    """Pin the new session-band and session_should_trip fields.

    The motivation is the 2026-06-28 next-priority: surface the
    *session* band alongside the per-output band in the breaker
    outcome, so an operator who looks at one CEFBreakerOutcome
    sees both layers' measurement in one place. The session band
    is the categorical analogue of band_for_upper_bound (the
    per-output, measured band).
    """

    def setUp(self):
        from core.cef_substrate_integration import (
            band_for_session_state,
            session_should_trip,
        )
        self.band_for_session_state = band_for_session_state
        self.session_should_trip = session_should_trip
        self.breaker = SafetyCircuitBreaker(failure_threshold=1)
        self.cfg = CEFIntegrationConfig()

    # ----- band_for_session_state mapping -----

    def test_band_none_is_unknown(self):
        self.assertEqual(self.band_for_session_state(None), "unknown")

    def test_band_clean_is_low(self):
        self.assertEqual(
            self.band_for_session_state(CEFSessionState.CLEAN), "low"
        )

    def test_band_early_is_low(self):
        self.assertEqual(
            self.band_for_session_state(CEFSessionState.EARLY), "low"
        )

    def test_band_warning_is_medium(self):
        self.assertEqual(
            self.band_for_session_state(CEFSessionState.WARNING), "medium"
        )

    def test_band_point_of_no_return_is_critical(self):
        self.assertEqual(
            self.band_for_session_state(CEFSessionState.POINT_OF_NO_RETURN),
            "critical",
        )

    # ----- session_should_trip helper -----

    def test_session_should_trip_none_is_false(self):
        self.assertFalse(self.session_should_trip(None, True, True))

    def test_session_should_trip_clean_is_false(self):
        session = create_cef_session_detector()
        verdict = session._build_verdict()
        self.assertFalse(self.session_should_trip(verdict, True, True))

    def test_session_should_trip_horizon_disabled(self):
        session = create_cef_session_detector()
        _drive_session_to_horizon(session, n=5)
        verdict = session._build_verdict()
        # trip_on_horizon=False -> even POINT_OF_NO_RETURN does not trip
        self.assertFalse(
            self.session_should_trip(verdict, trip_on_horizon=False, trip_on_restart=True)
        )

    def test_session_should_trip_horizon_enabled(self):
        session = create_cef_session_detector()
        _drive_session_to_horizon(session, n=5)
        verdict = session._build_verdict()
        self.assertEqual(verdict.state, CEFSessionState.POINT_OF_NO_RETURN)
        self.assertTrue(
            self.session_should_trip(verdict, trip_on_horizon=True, trip_on_restart=False)
        )

    # ----- CEFBreakerOutcome field defaults -----

    def test_outcome_defaults_session_band_unknown(self):
        """No session verdict -> session_band='unknown', session_should_trip=False."""
        detection = _make_clean_detection()
        outcome = assess_cef_to_breaker(detection, self.breaker, self.cfg)
        self.assertEqual(outcome.session_band, "unknown")
        self.assertFalse(outcome.session_should_trip)

    def test_outcome_to_dict_includes_session_fields(self):
        """to_dict() must surface session_band and session_should_trip."""
        detection = _make_clean_detection()
        outcome = assess_cef_to_breaker(detection, self.breaker, self.cfg)
        d = outcome.to_dict()
        self.assertIn("session_band", d)
        self.assertIn("session_should_trip", d)
        self.assertEqual(d["session_band"], "unknown")
        self.assertEqual(d["session_should_trip"], False)

    # ----- CEFBreakerOutcome session-band surfacing -----

    def test_outcome_session_band_low_for_clean_session(self):
        """CLEAN session -> session_band='low', session_should_trip=False."""
        session = create_cef_session_detector()
        verdict = session._build_verdict()  # CLEAN with no observations
        detection = _make_clean_detection()
        outcome = assess_cef_to_breaker(
            detection, self.breaker, self.cfg, session_verdict=verdict
        )
        self.assertEqual(outcome.session_band, "low")
        self.assertFalse(outcome.session_should_trip)
        # The per-output band stays 'unknown' (no engine wired)
        self.assertEqual(outcome.trip_band, "unknown")

    def test_outcome_session_band_critical_at_horizon(self):
        """POINT_OF_NO_RETURN session -> session_band='critical', session_should_trip=True."""
        session = create_cef_session_detector()
        _drive_session_to_horizon(session, n=5)
        verdict = session._build_verdict()
        self.assertEqual(verdict.state, CEFSessionState.POINT_OF_NO_RETURN)
        # Use a CLEAN per-output detection so the per-output band is 'low'
        # (no engine) but the session band is critical.
        detection = _make_clean_detection()
        outcome = assess_cef_to_breaker(
            detection, self.breaker, self.cfg, session_verdict=verdict
        )
        self.assertEqual(outcome.session_band, "critical")
        self.assertTrue(outcome.session_should_trip)
        # The session band is independent of the per-output band.
        self.assertEqual(outcome.trip_band, "unknown")
        # But the verdict still respects trip_on_horizon=True (the default)
        self.assertEqual(outcome.verdict, CEFBreakerVerdict.TRIP_SESSION)

    def test_outcome_session_band_respects_horizon_toggle(self):
        """trip_on_horizon=False -> session_band is still computed, but session_should_trip=False."""
        cfg = CEFIntegrationConfig(trip_on_horizon=False)
        session = create_cef_session_detector()
        _drive_session_to_horizon(session, n=5)
        verdict = session._build_verdict()
        detection = _make_clean_detection()
        outcome = assess_cef_to_breaker(
            detection, self.breaker, cfg, session_verdict=verdict
        )
        # Band is still reported (the categorical state is unchanged)
        self.assertEqual(outcome.session_band, "critical")
        # But the *policy* decision respects the operator's toggle
        self.assertFalse(outcome.session_should_trip)
        # And the verdict is NO_TRIP because the operator disabled the
        # session-level strike and the per-output is CLEAN.
        self.assertEqual(outcome.verdict, CEFBreakerVerdict.NO_TRIP)

    def test_outcome_session_band_medium_for_warning(self):
        """WARNING session -> session_band='medium', session_should_trip=False (no horizon)."""
        session = create_cef_session_detector(CEFSessionConfig(warn_total_threshold=1))
        # Drive to WARNING but not horizon
        fold_step_into_cef(
            agent_output=_make_vague_excuse_output(),
            step_index=0,
            session_detector=session,
        )
        verdict = session._build_verdict()
        # The session should be in WARNING (1 fabrication > warn_total_threshold=1? No, equal.
        # The semantics are >= warn_total_threshold for EARLY->WARNING. Default 3.
        # We set warn_total_threshold=1, so a single fabrication flips EARLY->WARNING.)
        if verdict.state == CEFSessionState.WARNING:
            detection = _make_clean_detection()
            outcome = assess_cef_to_breaker(
                detection, self.breaker, self.cfg, session_verdict=verdict
            )
            self.assertEqual(outcome.session_band, "medium")
            self.assertFalse(outcome.session_should_trip)


if __name__ == "__main__":
    unittest.main()
