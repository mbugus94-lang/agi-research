"""
Tests for the EvidenceLedger-aware verify_trace in core/reflection.

The ledger-backed extension is opt-in: when a caller passes
`ledger=...`, the verifier consults the EvidenceLedger via
TraceGrounder and returns extra keys (`grounded`, `coverage_rate`,
`recommended_action`, `contradicted_step_ids`, `weakest_step_ids`).

These tests pin the surface area so future edits to either
core.reflection or core.trace_grounding don't silently break the
wiring.
"""

import sys
import unittest

sys.path.insert(0, "/home/workspace/agi-research")

from core.evidence_ledger import EvidenceLedger
from core.reflection import ReflectionEngine
from core.trace_grounding import RECOMMENDED_ACTIONS


def _happy_trace():
    return [
        {"type": "explore", "content": "find stuff"},
        {"type": "plan", "content": "do stuff"},
        {"type": "verify", "content": "check stuff"},
        {"type": "reflect", "content": "done"},
    ]


def _incomplete_trace():
    return [
        {"type": "explore", "content": "find"},
        {"type": "plan", "content": "do"},
    ]


class BackwardCompatTests(unittest.TestCase):
    def test_no_ledger_keeps_original_shape(self):
        eng = ReflectionEngine()
        out = eng.verify_trace(_happy_trace(), "final answer")
        # Original keys present
        self.assertIn("valid", out)
        self.assertIn("steps_present", out)
        self.assertIn("missing_steps", out)
        self.assertIn("alignment_score", out)
        self.assertIn("reason", out)
        self.assertTrue(out["valid"])

    def test_no_ledger_ungrounded_zero(self):
        eng = ReflectionEngine()
        out = eng.verify_trace(_happy_trace(), "answer")
        self.assertFalse(out["grounded"])
        self.assertEqual(out["coverage_rate"], 0.0)
        self.assertEqual(out["recommended_action"], "none")

    def test_empty_trace_no_ledger(self):
        eng = ReflectionEngine()
        out = eng.verify_trace([], "answer")
        self.assertFalse(out["valid"])


class WithLedgerTests(unittest.TestCase):
    def test_grounded_flag_set_for_supported_trace(self):
        eng = ReflectionEngine()
        ledger = EvidenceLedger()
        out = eng.verify_trace(_happy_trace(), "answer", ledger=ledger)
        self.assertTrue(out["grounded"])
        self.assertEqual(out["coverage_rate"], 1.0)
        self.assertEqual(out["recommended_action"], "none")
        self.assertTrue(out["valid"])

    def test_extra_keys_present(self):
        eng = ReflectionEngine()
        ledger = EvidenceLedger()
        out = eng.verify_trace(_happy_trace(), "answer", ledger=ledger)
        for k in (
            "grounded",
            "coverage_rate",
            "recommended_action",
            "contradicted_step_ids",
            "weakest_step_ids",
        ):
            self.assertIn(k, out)

    def test_recommended_action_in_vocabulary(self):
        eng = ReflectionEngine()
        out = eng.verify_trace(_happy_trace(), "answer", ledger=EvidenceLedger())
        self.assertIn(out["recommended_action"], RECOMMENDED_ACTIONS)

    def test_empty_trace_with_ledger(self):
        eng = ReflectionEngine()
        out = eng.verify_trace([], "answer", ledger=EvidenceLedger())
        self.assertFalse(out["valid"])
        self.assertEqual(out["coverage_rate"], 0.0)

    def test_incomplete_trace_with_ledger_still_invalid(self):
        eng = ReflectionEngine()
        out = eng.verify_trace(
            _incomplete_trace(), "answer", ledger=EvidenceLedger()
        )
        # missing 'verify' and 'reflect' -> invalid
        self.assertFalse(out["valid"])
        self.assertIn("verify", out["missing_steps"])
        self.assertIn("reflect", out["missing_steps"])

    def test_ledger_consultation_pure_no_extra_claims(self):
        # The grounder adds claims for each step. After verify_trace,
        # the ledger should have exactly len(trace) new claims.
        eng = ReflectionEngine()
        ledger = EvidenceLedger()
        baseline = len(ledger.all_claims())
        trace = _happy_trace()
        eng.verify_trace(trace, "answer", ledger=ledger)
        self.assertEqual(len(ledger.all_claims()) - baseline, len(trace))

    def test_re_verify_is_idempotent(self):
        eng = ReflectionEngine()
        ledger = EvidenceLedger()
        trace = _happy_trace()
        r1 = eng.verify_trace(trace, "answer", ledger=ledger)
        r2 = eng.verify_trace(trace, "answer", ledger=ledger)
        self.assertEqual(r1["coverage_rate"], r2["coverage_rate"])
        # Re-grounding reuses the same claim ids, claim count stable
        self.assertEqual(len(ledger.all_claims()), len(trace))

    def test_contradicted_step_surfaces(self):
        eng = ReflectionEngine()
        ledger = EvidenceLedger()
        trace = [
            {"type": "explore", "content": "ok"},
            {
                "type": "execute",
                "content": "tool ran",
                "output": {"status": "error"},
            },
            {"type": "plan", "content": "re-plan"},
            {"type": "verify", "content": "re-check"},
            {"type": "reflect", "content": "done"},
        ]
        out = eng.verify_trace(trace, "answer", ledger=ledger)
        self.assertGreater(len(out["contradicted_step_ids"]), 0)


if __name__ == "__main__":
    unittest.main()
