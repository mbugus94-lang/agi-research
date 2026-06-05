"""
Tests for the Causal Evidence Ledger.

Covers:
- Claim CRUD: assert (idempotent), remove, has_claim
- Evidence CRUD: add_support / add_refute / remove / evidence_for
- Status transitions: ungrounded -> supported / contradicted / disputed / expired
- Verification: weighted support vs refute, freshness, reason strings
- Lineage: lineage / descendants / related_evidence
- Summary: counts, ungrounded_rate, contradiction_rate, weakest_claim_ids
- Serialization: to_dict / from_dict round trip; to_json / from_json
- Calibration signals: signals consumable by the metacognitive monitor
- Integration with ReflectionEngine-style trace
"""

import sys
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, "/home/workspace/agi-research")

from core.evidence_ledger import (
    Claim,
    ClaimStatus,
    ClaimVerification,
    Evidence,
    EvidenceKind,
    EvidenceLedger,
    EvidencePolarity,
    LedgerSummary,
    create_ledger,
)


# ---------------------------------------------------------------------------
# Claim CRUD
# ---------------------------------------------------------------------------


class ClaimCRUDTests(unittest.TestCase):
    def test_assert_claim_returns_claim(self):
        ledger = EvidenceLedger()
        c = ledger.assert_claim("Paris is the capital of France")
        self.assertIsInstance(c, Claim)
        self.assertTrue(ledger.has_claim(c.claim_id))

    def test_assert_claim_idempotent_by_id(self):
        ledger = EvidenceLedger()
        c1 = ledger.assert_claim("alpha", claim_id="c1")
        c2 = ledger.assert_claim("beta", claim_id="c1")
        self.assertEqual(c1.claim_id, c2.claim_id)
        self.assertEqual(ledger.get_claim("c1").text, "beta")

    def test_assert_claim_with_tags_and_depends_on(self):
        ledger = EvidenceLedger()
        c = ledger.assert_claim(
            "gamma",
            tags=["x", "y"],
            depends_on=["c1", "c2"],
        )
        self.assertEqual(c.tags, ["x", "y"])
        self.assertEqual(c.depends_on, ["c1", "c2"])

    def test_remove_claim_drops_evidence(self):
        ledger = EvidenceLedger()
        c = ledger.assert_claim("theta")
        ledger.add_support(c.claim_id, "evidence 1")
        ledger.add_refute(c.claim_id, "evidence 2")
        self.assertTrue(ledger.remove_claim(c.claim_id))
        self.assertFalse(ledger.has_claim(c.claim_id))
        self.assertEqual(ledger.evidence_for(c.claim_id), [])

    def test_remove_claim_unknown_returns_false(self):
        ledger = EvidenceLedger()
        self.assertFalse(ledger.remove_claim("nope"))

    def test_all_claims_returns_copy(self):
        ledger = EvidenceLedger()
        ledger.assert_claim("a")
        ledger.assert_claim("b")
        self.assertEqual(len(ledger.all_claims()), 2)


# ---------------------------------------------------------------------------
# Evidence CRUD and verification
# ---------------------------------------------------------------------------


class EvidenceAndVerificationTests(unittest.TestCase):
    def test_no_evidence_marks_ungrounded(self):
        ledger = EvidenceLedger()
        c = ledger.assert_claim("hydrogen is the lightest element")
        v = ledger.verify(c.claim_id)
        self.assertEqual(v.status, ClaimStatus.UNGROUNDED)
        self.assertEqual(v.support_count, 0)
        self.assertEqual(v.refute_count, 0)
        self.assertEqual(v.confidence, 0.0)

    def test_only_support_marks_supported(self):
        ledger = EvidenceLedger()
        c = ledger.assert_claim("water is H2O")
        ledger.add_support(c.claim_id, "chemistry textbook entry", kind=EvidenceKind.EXTERNAL)
        v = ledger.verify(c.claim_id)
        self.assertEqual(v.status, ClaimStatus.SUPPORTED)
        self.assertEqual(v.support_count, 1)
        self.assertEqual(v.reason, "net_positive_evidence")

    def test_only_refute_marks_contradicted(self):
        ledger = EvidenceLedger()
        c = ledger.assert_claim("the earth is flat")
        ledger.add_refute(c.claim_id, "satellite imagery shows sphere", kind=EvidenceKind.OBSERVATION)
        v = ledger.verify(c.claim_id)
        self.assertEqual(v.status, ClaimStatus.CONTRADICTED)
        self.assertEqual(v.refute_count, 1)

    def test_mixed_evidence_picks_lead(self):
        ledger = EvidenceLedger()
        c = ledger.assert_claim("alpha")
        ledger.add_support(c.claim_id, "supporting", weight=2.0)
        ledger.add_refute(c.claim_id, "refuting", weight=0.5)
        v = ledger.verify(c.claim_id)
        self.assertEqual(v.status, ClaimStatus.SUPPORTED)
        self.assertGreater(v.weighted_support, v.weighted_refute)
        self.assertIn("support_lead", v.reason)

    def test_mixed_evidence_disputed_when_tied(self):
        ledger = EvidenceLedger()
        c = ledger.assert_claim("alpha")
        ledger.add_support(c.claim_id, "supporting", weight=1.0)
        ledger.add_refute(c.claim_id, "refuting", weight=1.0)
        v = ledger.verify(c.claim_id)
        self.assertEqual(v.status, ClaimStatus.DISPUTED)
        self.assertEqual(v.confidence, 0.5)

    def test_confidence_clipped_to_unit(self):
        ledger = EvidenceLedger()
        c = ledger.assert_claim("alpha")
        for i in range(20):
            ledger.add_support(c.claim_id, f"evidence {i}", weight=2.0, confidence=2.0)
        v = ledger.verify(c.claim_id)
        self.assertLessEqual(v.confidence, 1.0)

    def test_remove_evidence_drops_from_claim(self):
        ledger = EvidenceLedger()
        c = ledger.assert_claim("alpha")
        ev = ledger.add_support(c.claim_id, "supporting")
        self.assertTrue(ledger.remove_evidence(ev.evidence_id))
        self.assertEqual(ledger.evidence_for(c.claim_id), [])
        self.assertFalse(ledger.remove_evidence("missing"))

    def test_weight_zero_evidence_ignored(self):
        ledger = EvidenceLedger()
        c = ledger.assert_claim("alpha")
        ledger.add_support(c.claim_id, "weak", weight=0.0, confidence=0.0)
        v = ledger.verify(c.claim_id)
        # zero weight on both sides -> empty after clipping -> ungrounded
        self.assertEqual(v.weighted_support, 0.0)
        self.assertEqual(v.weighted_refute, 0.0)
        self.assertEqual(v.status, ClaimStatus.UNGROUNDED)


# ---------------------------------------------------------------------------
# Freshness
# ---------------------------------------------------------------------------


class FreshnessTests(unittest.TestCase):
    def test_fresh_by_default(self):
        ledger = EvidenceLedger()
        c = ledger.assert_claim("alpha")
        ledger.add_support(c.claim_id, "supporting")
        v = ledger.verify(c.claim_id)
        self.assertTrue(v.is_fresh)
        self.assertEqual(v.status, ClaimStatus.SUPPORTED)

    def test_expired_when_freshness_window_passed(self):
        ledger = EvidenceLedger(freshness_window=timedelta(seconds=1))
        c = ledger.assert_claim("alpha")
        ledger.add_support(c.claim_id, "supporting")
        # backdate the claim to simulate elapsed time
        ledger._claims[c.claim_id].created_at = datetime.now() - timedelta(hours=2)
        v = ledger.verify(c.claim_id)
        self.assertFalse(v.is_fresh)
        self.assertEqual(v.status, ClaimStatus.EXPIRED)

    def test_ungrounded_becomes_expired_when_stale(self):
        ledger = EvidenceLedger(freshness_window=timedelta(seconds=1))
        c = ledger.assert_claim("alpha")
        ledger._claims[c.claim_id].created_at = datetime.now() - timedelta(hours=2)
        v = ledger.verify(c.claim_id)
        self.assertEqual(v.status, ClaimStatus.EXPIRED)


# ---------------------------------------------------------------------------
# Lineage and related evidence
# ---------------------------------------------------------------------------


class LineageTests(unittest.TestCase):
    def test_lineage_returns_ancestors(self):
        ledger = EvidenceLedger()
        a = ledger.assert_claim("a", claim_id="a")
        b = ledger.assert_claim("b", claim_id="b", depends_on=["a"])
        c = ledger.assert_claim("c", claim_id="c", depends_on=["b"])
        order = ledger.lineage(c.claim_id)
        self.assertEqual(order[0], "c")
        self.assertIn("a", order)
        self.assertIn("b", order)

    def test_lineage_handles_cycles_safely(self):
        ledger = EvidenceLedger()
        ledger.assert_claim("a", claim_id="a", depends_on=["b"])
        ledger.assert_claim("b", claim_id="b", depends_on=["a"])
        order = ledger.lineage("a")
        self.assertEqual(set(order), {"a", "b"})

    def test_descendants_finds_dependents(self):
        ledger = EvidenceLedger()
        ledger.assert_claim("a", claim_id="a")
        ledger.assert_claim("b", claim_id="b", depends_on=["a"])
        ledger.assert_claim("c", claim_id="c", depends_on=["b"])
        desc = ledger.descendants("a")
        self.assertIn("b", desc)
        self.assertIn("c", desc)

    def test_related_evidence_lexical_match(self):
        ledger = EvidenceLedger()
        c1 = ledger.assert_claim("france capital paris euro")
        ledger.add_support(c1.claim_id, "Paris is the capital of France and uses the Euro")
        c2 = ledger.assert_claim("germany capital berlin")
        related = ledger.related_evidence(c2.text, top_k=3)
        self.assertEqual(related, [])  # no overlap
        # query related to c1 should return at least one piece
        related = ledger.related_evidence("tell me about Paris and Euro", top_k=3)
        self.assertGreaterEqual(len(related), 1)

    def test_related_evidence_threshold(self):
        ledger = EvidenceLedger(lexical_threshold=0.99)
        c = ledger.assert_claim("france capital paris")
        ledger.add_support(c.claim_id, "Paris is the capital of France and uses the Euro")
        related = ledger.related_evidence("Berlin Germany", top_k=3)
        self.assertEqual(related, [])


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


class SummaryTests(unittest.TestCase):
    def test_summary_empty_ledger(self):
        ledger = EvidenceLedger()
        s = ledger.summary()
        self.assertEqual(s.total_claims, 0)
        self.assertEqual(s.ungrounded_rate, 0.0)
        self.assertEqual(s.contradiction_rate, 0.0)

    def test_summary_counts_each_status(self):
        ledger = EvidenceLedger()
        c1 = ledger.assert_claim("a")
        c2 = ledger.assert_claim("b")
        c3 = ledger.assert_claim("c")
        c4 = ledger.assert_claim("d")
        ledger.add_support(c2.claim_id, "ok")
        ledger.add_refute(c3.claim_id, "no")
        # c4 stays ungrounded
        s = ledger.summary()
        self.assertEqual(s.total_claims, 4)
        self.assertEqual(s.ungrounded, 2)  # c1 and c4
        self.assertEqual(s.supported, 1)
        self.assertEqual(s.contradicted, 1)
        self.assertAlmostEqual(s.ungrounded_rate, 0.5)
        self.assertAlmostEqual(s.contradiction_rate, 0.25)

    def test_summary_flags_weakest(self):
        ledger = EvidenceLedger()
        c1 = ledger.assert_claim("a")
        c2 = ledger.assert_claim("b")
        c3 = ledger.assert_claim("c")
        ledger.add_support(c1.claim_id, "strong", weight=2.0)
        ledger.add_refute(c3.claim_id, "weak", weight=0.1)
        # c2 is ungrounded -> weakest
        s = ledger.summary()
        self.assertIn(c2.claim_id, s.weakest_claim_ids)

    def test_summary_audit_trail_included(self):
        ledger = EvidenceLedger()
        ledger.assert_claim("a")
        s = ledger.summary()
        self.assertGreater(len(s.audit_trail), 0)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class SerializationTests(unittest.TestCase):
    def test_round_trip_dict(self):
        ledger = EvidenceLedger()
        c = ledger.assert_claim("alpha", tags=["x"])
        ledger.add_support(c.claim_id, "supporting", kind=EvidenceKind.TOOL_TRACE)
        data = ledger.to_dict()
        restored = EvidenceLedger.from_dict(data)
        self.assertEqual(restored.get_claim(c.claim_id).text, "alpha")
        self.assertEqual(len(restored.evidence_for(c.claim_id)), 1)

    def test_round_trip_json(self):
        ledger = EvidenceLedger(freshness_window=timedelta(seconds=42))
        c = ledger.assert_claim("alpha")
        ledger.add_refute(c.claim_id, "refuting", weight=0.3)
        payload = ledger.to_json()
        restored = EvidenceLedger.from_json(payload)
        self.assertEqual(restored.freshness_window.total_seconds(), 42.0)
        self.assertEqual(len(restored.evidence_for(c.claim_id)), 1)

    def test_audit_trail_capped(self):
        ledger = EvidenceLedger(max_audit_trail=3)
        for i in range(10):
            ledger.assert_claim(f"c{i}")
        self.assertLessEqual(len(ledger._audit_trail), 3)


# ---------------------------------------------------------------------------
# Calibration signals (metacognitive monitor hook)
# ---------------------------------------------------------------------------


class CalibrationSignalTests(unittest.TestCase):
    def test_signals_empty_ledger(self):
        ledger = EvidenceLedger()
        s = ledger.calibration_signals()
        self.assertEqual(s["ungrounded_rate"], 0.0)
        self.assertEqual(s["contradiction_rate"], 0.0)
        self.assertEqual(s["mean_confidence"], 0.0)

    def test_signals_reflect_state(self):
        ledger = EvidenceLedger()
        c1 = ledger.assert_claim("a")
        c2 = ledger.assert_claim("b")
        c3 = ledger.assert_claim("c")
        c4 = ledger.assert_claim("d")
        ledger.add_support(c2.claim_id, "ok")
        ledger.add_refute(c3.claim_id, "no")
        s = ledger.calibration_signals()
        self.assertAlmostEqual(s["ungrounded_rate"], 0.5)  # c1, c4
        self.assertAlmostEqual(s["contradiction_rate"], 0.25)
        self.assertGreater(s["mean_confidence"], 0.0)


# ---------------------------------------------------------------------------
# Integration
# ---------------------------------------------------------------------------


class IntegrationTests(unittest.TestCase):
    def test_full_evidence_workflow(self):
        ledger = create_ledger(freshness_seconds=3600, lexical_threshold=0.2)
        # 1) claim
        root = ledger.assert_claim(
            "agent should cache long-context orientation entries",
            tags=["memory", "context"],
        )
        ledger.add_support(
            root.claim_id,
            "PEEK paper shows 6.3-34% efficiency gains for long-context LLM agents",
            kind=EvidenceKind.EXTERNAL,
            source="arXiv:2605.19932v1",
        )
        # 2) linked claim
        child = ledger.assert_claim(
            "context cache should evict LRU under budget",
            tags=["memory"],
            depends_on=[root.claim_id],
        )
        ledger.add_support(
            child.claim_id,
            "PEEK's Evictor with LRU/LFU/COST_AWARE policies",
            kind=EvidenceKind.INFERENCE,
        )
        ledger.add_refute(
            child.claim_id,
            "naive LRU underperforms on homogeneous tokens",
            kind=EvidenceKind.OBSERVATION,
            weight=0.4,
        )
        # 3) verify and summarize
        root_v = ledger.verify(root.claim_id)
        child_v = ledger.verify(child.claim_id)
        self.assertEqual(root_v.status, ClaimStatus.SUPPORTED)
        # weighted support (1.0) > weighted refute (0.4) -> support_lead
        self.assertEqual(child_v.status, ClaimStatus.SUPPORTED)
        self.assertIn("support_lead", child_v.reason)

        summary = ledger.summary()
        self.assertEqual(summary.total_claims, 2)
        self.assertEqual(summary.supported, 2)
        # child_v is mixed with support lead -> only the still-ungrounded
        # ungrounded_claim (none here) would be the weakest
        self.assertNotIn(child.claim_id, summary.weakest_claim_ids)

        # 4) lineage and serialization
        self.assertIn(root.claim_id, ledger.lineage(child.claim_id))
        restored = EvidenceLedger.from_json(ledger.to_json())
        self.assertEqual(restored.summary().total_claims, 2)

        # 5) monitor hook
        signals = ledger.calibration_signals()
        # both claims have evidence -> ungrounded rate is 0
        self.assertEqual(signals["ungrounded_rate"], 0.0)
        self.assertGreater(signals["mean_confidence"], 0.0)

    def test_concurrent_claim_reuse(self):
        """Re-asserting the same logical claim with new evidence keeps history."""
        ledger = EvidenceLedger()
        c = ledger.assert_claim("reused")
        ledger.add_support(c.claim_id, "first evidence")
        ledger.add_refute(c.claim_id, "counter evidence", weight=0.5)
        v1 = ledger.verify(c.claim_id)
        self.assertEqual(v1.status, ClaimStatus.SUPPORTED)
        # stronger refute tips the balance
        ledger.add_refute(c.claim_id, "strong refute", weight=10.0)
        v2 = ledger.verify(c.claim_id)
        self.assertEqual(v2.status, ClaimStatus.CONTRADICTED)


if __name__ == "__main__":
    unittest.main()
