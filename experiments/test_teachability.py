"""
Tests for core/teachability.py.

Coverage
--------
- TestSubscores (5): recovery, friction, audit completeness, chatter,
  empty-input defaults
- TestTeachabilityScore (3): dict export, band thresholds, frozen dataclass
- TestComputeTeachability (4): empty inputs, healthy inputs, audit penalty,
  low chatter score
- TestTeachabilityFromCircuit (2): direct circuit scoring, note generation
"""

from __future__ import annotations

import os
import sys
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from core.governor_circuit import GateObservation, GovernorCircuit, GovernorCircuitConfig  # noqa: E402
from core.teachability import (  # noqa: E402
    TeachabilityScore,
    audit_trail_completeness,
    chatter_resistance,
    compute_teachability,
    intervention_friction,
    recovery_responsiveness,
    teachability_from_circuit,
)
from core.cef_probabilistic_verification import ProbabilisticTripEngine  # noqa: E402


class TestSubscores(unittest.TestCase):
    def test_recovery_empty_defaults(self):
        self.assertEqual(recovery_responsiveness(0, 0), 0.5)

    def test_recovery_good(self):
        self.assertAlmostEqual(recovery_responsiveness(10, 2), 1.0)

    def test_friction_empty_defaults(self):
        self.assertEqual(intervention_friction([]), 0.5)

    def test_audit_empty_defaults(self):
        self.assertEqual(audit_trail_completeness([]), 0.5)

    def test_chatter_empty_defaults(self):
        self.assertEqual(chatter_resistance([]), 0.5)


class TestTeachabilityScore(unittest.TestCase):
    def test_to_dict(self):
        score = TeachabilityScore(0.9, 0.8, 0.7, 0.6, 0.75)
        payload = score.to_dict()
        self.assertEqual(payload["teachability"], 0.75)
        self.assertEqual(payload["components"]["audit"], 0.7)

    def test_band(self):
        self.assertEqual(TeachabilityScore(1, 1, 1, 1, 0.9).band(), "excellent")
        self.assertEqual(TeachabilityScore(1, 1, 1, 1, 0.6).band(), "acceptable")
        self.assertEqual(TeachabilityScore(1, 1, 1, 1, 0.2).band(), "poor")

    def test_frozen(self):
        score = TeachabilityScore(1, 1, 1, 1, 1)
        with self.assertRaises(Exception):
            score.teachability = 0.0  # type: ignore[attr-defined]


class TestComputeTeachability(unittest.TestCase):
    def test_empty_inputs(self):
        score = compute_teachability(transitions=[], audit_records=[])
        self.assertEqual(score.teachability, 0.5 ** 1.0)
        self.assertEqual(score.band(), "acceptable")

    def test_healthy_inputs(self):
        transitions = [
            {"from_state": "OPEN", "to_state": "HALF_OPEN"},
            {"from_state": "HALF_OPEN", "to_state": "CLOSED"},
        ]
        audit_records = [
            {
                "timestamp": "2026-06-30T00:00:00Z",
                "reason": "operator reset",
                "layer": "per_output",
                "intervention": True,
                "pre_bound": 0.9,
                "post_bound": 0.3,
            }
        ]
        score = compute_teachability(transitions=transitions, audit_records=audit_records)
        self.assertGreaterEqual(score.teachability, 0.5)
        self.assertGreaterEqual(score.recovery, 1.0 - 1e-9)
        self.assertIn("All sub-scores are healthy.", score.notes)

    def test_audit_penalty(self):
        score = compute_teachability(
            transitions=[{"from_state": "OPEN", "to_state": "HALF_OPEN"}],
            audit_records=[{"intervention": True}],
        )
        self.assertLess(score.audit, 0.7)
        self.assertTrue(any("Audit trail is sparse" in n for n in score.notes))

    def test_low_chatter(self):
        """A small set of stable states scores higher than a churny set."""
        stable = [
            {"from_state": "closed", "to_state": "open", "reason": "trip"},
            {"from_state": "open", "to_state": "closed", "reason": "recover"},
        ]
        churny = [
            {"from_state": "closed", "to_state": "open", "reason": "trip"},
            {"from_state": "open", "to_state": "closed", "reason": "recover"},
        ] * 20
        s_score = compute_teachability(transitions=stable)
        c_score = compute_teachability(transitions=churny)
        self.assertGreaterEqual(s_score.chatter, c_score.chatter)

    def test_recovery_counter_case_insensitive(self):
        """Recovery counter must work on both lower- and upper-case states.

        Regression: previously the counter was hard-coded to ``"OPEN"`` /
        ``"HALF_OPEN"``, but ``GateState`` enum values are lower-case
        ``"open"`` / ``"half_open"``. Case-insensitive comparison makes
        the helper robust to both real dataclass output and dict-imported
        JSONL.
        """
        lower = [
            {"from_state": "open", "to_state": "half_open", "reason": "recover1"},
            {"from_state": "half_open", "to_state": "closed", "reason": "recover2"},
        ]
        upper = [
            {"from_state": "OPEN", "to_state": "HALF_OPEN", "reason": "r1"},
            {"from_state": "HALF_OPEN", "to_state": "CLOSED", "reason": "r2"},
        ]
        s_lower = compute_teachability(transitions=lower)
        s_upper = compute_teachability(transitions=upper)
        self.assertEqual(s_lower.recovery_count, 2)
        self.assertEqual(s_upper.recovery_count, 2)
        # Recovery scores should match (the underlying scoring rule doesn't
        # depend on case).
        self.assertAlmostEqual(
            s_lower.recovery,
            s_upper.recovery,
            places=6,
        )


class TestTeachabilityFromCircuit(unittest.TestCase):
    def _circuit(self):
        eng = ProbabilisticTripEngine(alpha_prior=1.0, beta_prior=1.0)
        circuit = GovernorCircuit(
            config=GovernorCircuitConfig(trip_threshold=0.4, reset_threshold=0.2, probe_count=1),
            per_output_engine=eng,
        )
        circuit.feed(GateObservation(tripped=True, label="trip-1"))
        circuit.feed(GateObservation(tripped=False, label="ok-1"))
        return circuit

    def test_direct_scoring(self):
        circuit = self._circuit()
        score = teachability_from_circuit(circuit)
        self.assertGreaterEqual(score.transition_count, 1)
        self.assertGreaterEqual(score.teachability, 0.0)

    def test_notes_generated(self):
        circuit = self._circuit()
        score = teachability_from_circuit(circuit)
        self.assertTrue(score.notes)


if __name__ == "__main__":
    unittest.main()