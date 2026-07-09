"""
Tests for the Compositional Policy Gate (arXiv:2607.03423 DSCC-style).

Covers:
- TaintSource ordering and max_taint
- VerbPolicy construction
- ChainVerdict to_dict round-trip
- CompositionalPolicyGate construction, register, lookup
- check_chain: empty chain, safe chain, JADEPUFFER pattern,
  unknown verb, write-after-untrusted, sensitive-to-public,
  sink fanout, requires_review, deterministic
- Audit log: hash chain, replay safety
- Conservative posture: default-DENY, monotonic taint,
  fail-closed for unknown combinations
- create_gate: smallest viable install
"""

from __future__ import annotations

import hashlib
import json
import unittest
from typing import List

from core.compositional_policy import (
    ChainAction,
    ChainStep,
    ChainVerdict,
    CompositionalPolicyGate,
    DenyReason,
    TaintSource,
    VerbPolicy,
    create_gate,
    max_taint,
    taint_rank,
)


# ===========================================================================
# TaintSource
# ===========================================================================

class TestTaintSource(unittest.TestCase):
    def test_all_members_distinct(self):
        members = list(TaintSource)
        self.assertEqual(len(members), len(set(members)))

    def test_taint_rank_monotonic(self):
        # Rank ordering matches the module's hard-coded sequence.
        # TRUSTED < INTERNAL < USER < PUBLIC < EXTERNAL < UNTRUSTED < SECRET.
        order = [
            TaintSource.TRUSTED, TaintSource.INTERNAL, TaintSource.USER,
            TaintSource.PUBLIC, TaintSource.EXTERNAL,
            TaintSource.UNTRUSTED, TaintSource.SECRET,
        ]
        ranks = [taint_rank(t) for t in order]
        self.assertEqual(ranks, sorted(ranks))

    def test_max_taint_picks_higher_rank(self):
        self.assertEqual(
            max_taint(TaintSource.INTERNAL, TaintSource.EXTERNAL),
            TaintSource.EXTERNAL,
        )
        self.assertEqual(
            max_taint(TaintSource.SECRET, TaintSource.EXTERNAL),
            TaintSource.SECRET,
        )
        self.assertEqual(
            max_taint(TaintSource.TRUSTED, TaintSource.TRUSTED),
            TaintSource.TRUSTED,
        )


# ===========================================================================
# VerbPolicy
# ===========================================================================

class TestVerbPolicy(unittest.TestCase):
    def test_required_field(self):
        with self.assertRaises(TypeError):
            VerbPolicy()  # type: ignore[call-arg]

    def test_frozen(self):
        p = VerbPolicy(verb_name="read_file", taint_in=TaintSource.INTERNAL)
        with self.assertRaises(Exception):
            p.verb_name = "other"  # type: ignore[misc]

    def test_default_sinks_empty(self):
        p = VerbPolicy(verb_name="x", taint_in=TaintSource.INTERNAL)
        self.assertEqual(p.sinks, ())
        self.assertFalse(p.requires_review)
        self.assertFalse(p.is_secret_emitting)
        self.assertIsNone(p.max_taint_threshold)


# ===========================================================================
# ChainStep + ChainVerdict
# ===========================================================================

class TestChainStep(unittest.TestCase):
    def test_default_taint(self):
        s = ChainStep(verb_name="read_file")
        self.assertEqual(s.verb_name, "read_file")
        self.assertEqual(s.taint_in, TaintSource.INTERNAL)


class TestChainVerdict(unittest.TestCase):
    def test_to_dict_round_trip(self):
        v = ChainVerdict(
            action=ChainAction.BLOCK_AND_ESCALATE,
            reasons=[DenyReason.SECRET_TO_EXTERNAL],
            taint_at_each_step=[TaintSource.SECRET, TaintSource.EXTERNAL],
            sinks_seen=("read", "egress"),
            contains_secret=True,
            digest="abc123",
        )
        d = v.to_dict()
        self.assertEqual(d["action"], "block_and_escalate")
        self.assertEqual(d["reasons"], ["secret_to_external"])
        self.assertEqual(d["taint_at_each_step"], ["secret", "external"])
        self.assertEqual(d["sinks_seen"], ["read", "egress"])
        self.assertTrue(d["contains_secret"])
        self.assertEqual(d["digest"], "abc123")


# ===========================================================================
# Gate: construction
# ===========================================================================

class TestGateConstruction(unittest.TestCase):
    def test_empty_gate(self):
        g = CompositionalPolicyGate()
        self.assertEqual(g.lookup("anything"), None)
        self.assertEqual(g.audit_log, [])

    def test_create_gate_returns_instance(self):
        g = create_gate()
        self.assertIsInstance(g, CompositionalPolicyGate)

    def test_register_and_lookup(self):
        g = CompositionalPolicyGate()
        p = VerbPolicy(verb_name="read_file", taint_in=TaintSource.INTERNAL)
        g.register(p)
        self.assertIs(g.lookup("read_file"), p)

    def test_register_validates_name(self):
        g = CompositionalPolicyGate()
        with self.assertRaises(ValueError):
            g.register(VerbPolicy(verb_name="", taint_in=TaintSource.INTERNAL))

    def test_max_sinks_clamped_to_1(self):
        g = CompositionalPolicyGate(max_sinks=0)
        self.assertEqual(g._max_sinks, 1)


# ===========================================================================
# check_chain: simple cases
# ===========================================================================

class TestCheckChainEmpty(unittest.TestCase):
    def test_empty_chain_allows(self):
        g = create_gate()
        v = g.check_chain([])
        self.assertEqual(v.action, ChainAction.ALLOW)
        self.assertEqual(v.reasons, [])
        self.assertEqual(v.taint_at_each_step, [])


class TestCheckChainSafe(unittest.TestCase):
    def test_internal_only_chain_allows(self):
        g = create_gate()
        g.register(VerbPolicy("read_file", TaintSource.INTERNAL, sinks=("read",)))
        g.register(VerbPolicy("summarize", TaintSource.INTERNAL, sinks=("compute",)))
        v = g.check_chain([
            ChainStep("read_file", TaintSource.INTERNAL),
            ChainStep("summarize", TaintSource.INTERNAL),
        ])
        self.assertEqual(v.action, ChainAction.ALLOW)
        self.assertEqual(v.reasons, [])

    def test_single_verb_allows(self):
        g = create_gate()
        g.register(VerbPolicy("read_file", TaintSource.INTERNAL))
        v = g.check_chain([ChainStep("read_file")])
        self.assertEqual(v.action, ChainAction.ALLOW)


# ===========================================================================
# check_chain: JADEPUFFER pattern (the headline attack)
# ===========================================================================

class TestJadePufferPattern(unittest.TestCase):
    """The 2026-07-01 JADEPUFFER attack chain:
    read_env -> http_post_external -> read_secret_store -> http_post_external.
    Each verb is permitted in isolation. The chain is an exfil pipeline."""

    def _jadepuffer_gate(self) -> CompositionalPolicyGate:
        g = create_gate()
        g.register(VerbPolicy("read_env", TaintSource.INTERNAL, sinks=("read",)))
        g.register(VerbPolicy("http_post_external", TaintSource.EXTERNAL, sinks=("egress",)))
        g.register(VerbPolicy(
            "read_secret_store", TaintSource.SECRET,
            sinks=("read",), is_secret_emitting=True,
        ))
        return g

    def test_jadepuffer_chain_is_blocked(self):
        g = self._jadepuffer_gate()
        v = g.check_chain([
            ChainStep("read_env", TaintSource.INTERNAL),
            ChainStep("http_post_external", TaintSource.EXTERNAL),
            ChainStep("read_secret_store", TaintSource.SECRET),
            ChainStep("http_post_external", TaintSource.EXTERNAL),
        ])
        self.assertEqual(v.action, ChainAction.BLOCK_AND_ESCALATE)
        self.assertIn(DenyReason.SECRET_TO_EXTERNAL, v.reasons)
        self.assertTrue(v.contains_secret)

    def test_jadepuffer_chain_marks_contains_secret(self):
        g = self._jadepuffer_gate()
        v = g.check_chain([
            ChainStep("read_env"),
            ChainStep("http_post_external"),
            ChainStep("read_secret_store", TaintSource.SECRET),
            ChainStep("http_post_external"),
        ])
        self.assertTrue(v.contains_secret)

    def test_safe_chain_no_secret_allowed(self):
        g = self._jadepuffer_gate()
        v = g.check_chain([
            ChainStep("read_env"),
            ChainStep("http_post_external"),
        ])
        self.assertEqual(v.action, ChainAction.ALLOW)
        self.assertFalse(v.contains_secret)


# ===========================================================================
# check_chain: unknown verb (conservative default-DENY)
# ===========================================================================

class TestUnknownVerb(unittest.TestCase):
    def test_unknown_verb_blocks_and_escalates(self):
        g = create_gate()
        v = g.check_chain([ChainStep("do_unknown_thing")])
        self.assertEqual(v.action, ChainAction.BLOCK_AND_ESCALATE)
        self.assertIn(DenyReason.UNKNOWN_VERB, v.reasons)

    def test_unknown_verb_with_default_unknown(self):
        default = VerbPolicy(
            "fallback", TaintSource.INTERNAL, sinks=("compute",),
        )
        g = CompositionalPolicyGate(default_unknown_policy=default)
        v = g.check_chain([ChainStep("do_unknown_thing")])
        # Default policy was permissive; no deny reason; no review needed.
        self.assertEqual(v.action, ChainAction.ALLOW)
        self.assertEqual(v.reasons, [])

    def test_unknown_verb_first_in_chain_terminates(self):
        g = create_gate()
        g.register(VerbPolicy("read_file", TaintSource.INTERNAL))
        v = g.check_chain([
            ChainStep("do_unknown_thing"),
            ChainStep("read_file"),
        ])
        # Taint tracking halts on the first unknown verb.
        self.assertEqual(v.action, ChainAction.BLOCK_AND_ESCALATE)
        self.assertEqual(v.taint_at_each_step, [])


# ===========================================================================
# check_chain: write-after-untrusted (prompt injection pivot)
# ===========================================================================

class TestWriteAfterUntrusted(unittest.TestCase):
    def test_write_after_untrusted_blocks(self):
        g = create_gate()
        g.register(VerbPolicy("http_get", TaintSource.EXTERNAL, sinks=("read",)))
        g.register(VerbPolicy("write_file", TaintSource.INTERNAL, sinks=("write",)))
        v = g.check_chain([
            ChainStep("http_get", TaintSource.EXTERNAL),
            ChainStep("write_file"),
        ])
        self.assertEqual(v.action, ChainAction.BLOCK)
        self.assertIn(DenyReason.WRITE_AFTER_UNTRUSTED, v.reasons)

    def test_write_without_untrusted_does_not_block(self):
        g = create_gate()
        g.register(VerbPolicy("read_file", TaintSource.INTERNAL, sinks=("read",)))
        g.register(VerbPolicy("write_file", TaintSource.INTERNAL, sinks=("write",)))
        v = g.check_chain([
            ChainStep("read_file"),
            ChainStep("write_file"),
        ])
        self.assertNotIn(DenyReason.WRITE_AFTER_UNTRUSTED, v.reasons)


# ===========================================================================
# check_chain: sink fanout
# ===========================================================================

class TestSinkFanout(unittest.TestCase):
    def test_too_many_sinks_forces_review(self):
        g = create_gate(max_sinks=2)
        g.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        g.register(VerbPolicy("compute", TaintSource.INTERNAL, sinks=("compute",)))
        g.register(VerbPolicy("egress", TaintSource.EXTERNAL, sinks=("egress",)))
        g.register(VerbPolicy("write", TaintSource.INTERNAL, sinks=("write",)))
        v = g.check_chain([
            ChainStep("read"),
            ChainStep("compute"),
            ChainStep("egress"),
            ChainStep("write"),
        ])
        # 4 sinks > 2 -> ALLOW_ONLY_REVIEW with reason
        self.assertEqual(v.action, ChainAction.ALLOW_ONLY_REVIEW)
        self.assertIn(DenyReason.TOO_MANY_DISTINCT_SINKS, v.reasons)


# ===========================================================================
# check_chain: requires_review
# ===========================================================================

class TestRequiresReview(unittest.TestCase):
    def test_requires_review_forces_review(self):
        g = create_gate()
        g.register(VerbPolicy(
            "deploy_production", TaintSource.INTERNAL,
            sinks=("exec",), requires_review=True,
        ))
        v = g.check_chain([ChainStep("deploy_production")])
        self.assertEqual(v.action, ChainAction.ALLOW_ONLY_REVIEW)


# ===========================================================================
# check_chain: deterministic + audit
# ===========================================================================

class TestDeterminismAndAudit(unittest.TestCase):
    def test_deterministic_same_input_same_digest(self):
        g1 = create_gate()
        g1.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        v1 = g1.check_chain([ChainStep("read")])

        g2 = create_gate()
        g2.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        v2 = g2.check_chain([ChainStep("read")])

        self.assertEqual(v1.digest, v2.digest)
        self.assertEqual(v1.action, v2.action)

    def test_audit_log_appended(self):
        g = create_gate()
        g.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        g.check_chain([ChainStep("read")])
        g.check_chain([ChainStep("read")])
        self.assertEqual(len(g.audit_log), 2)

    def test_audit_log_chained_via_prev_digest(self):
        g = create_gate()
        g.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        g.check_chain([ChainStep("read")], now=1.0)
        g.check_chain([ChainStep("read")], now=2.0)
        self.assertEqual(g.audit_log[0]["prev_digest"], "")
        self.assertEqual(g.audit_log[1]["prev_digest"], g.audit_log[0]["digest"])

    def test_audit_digest_is_sha256(self):
        g = create_gate()
        g.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        g.check_chain([ChainStep("read")])
        d = g.audit_log[0]["digest"]
        self.assertEqual(len(d), 64)
        # Verify it's a valid hex sha256
        int(d, 16)

    def test_audit_digest_matches_verdict_digest(self):
        g = create_gate()
        g.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        v = g.check_chain([ChainStep("read")])
        self.assertEqual(g.audit_log[-1]["verdict"]["digest"], v.digest)

    def test_now_override_propagates_to_audit(self):
        g = create_gate()
        g.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        g.check_chain([ChainStep("read")], now=12345.0)
        self.assertEqual(g.audit_log[-1]["ts"], 12345.0)


# ===========================================================================
# check_chain: taint threshold
# ===========================================================================

class TestTaintThreshold(unittest.TestCase):
    def test_above_threshold_blocks(self):
        g = create_gate()
        g.register(VerbPolicy(
            "http_get", TaintSource.EXTERNAL,
            sinks=("read",), max_taint_threshold=TaintSource.PUBLIC,
        ))
        v = g.check_chain([ChainStep("http_get", TaintSource.EXTERNAL)])
        self.assertEqual(v.action, ChainAction.BLOCK)
        self.assertIn(DenyReason.TAINT_ESCALATION, v.reasons)


# ===========================================================================
# Conservative posture
# ===========================================================================

class TestConservativePosture(unittest.TestCase):
    def test_unknown_verb_does_not_silently_allow(self):
        g = create_gate()
        v = g.check_chain([ChainStep("anything")])
        self.assertNotEqual(v.action, ChainAction.ALLOW)

    def test_taint_is_monotonic(self):
        g = create_gate()
        g.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        g.register(VerbPolicy("http_get", TaintSource.EXTERNAL, sinks=("read",)))
        v = g.check_chain([
            ChainStep("read"),
            ChainStep("http_get", TaintSource.EXTERNAL),
        ])
        # taint[0] = INTERNAL (from read), taint[1] = EXTERNAL
        self.assertEqual(v.taint_at_each_step[0], TaintSource.INTERNAL)
        self.assertEqual(v.taint_at_each_step[1], TaintSource.EXTERNAL)

    def test_pure_function_no_clock_when_now_passed(self):
        g = create_gate()
        g.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        v1 = g.check_chain([ChainStep("read")], now=1000.0)
        v2 = g.check_chain([ChainStep("read")], now=1000.0)
        self.assertEqual(v1.digest, v2.digest)
        # Audit ts is the same too
        self.assertEqual(g.audit_log[-2]["ts"], 1000.0)
        self.assertEqual(g.audit_log[-1]["ts"], 1000.0)


# ===========================================================================
# Create gate
# ===========================================================================

class TestCreateGate(unittest.TestCase):
    def test_create_gate_no_policies_blocks_everything(self):
        g = create_gate()
        v = g.check_chain([ChainStep("any_verb")])
        self.assertEqual(v.action, ChainAction.BLOCK_AND_ESCALATE)

    def test_create_gate_with_policies_allows_known(self):
        g = create_gate(
            policies={"read": VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",))},
        )
        v = g.check_chain([ChainStep("read")])
        self.assertEqual(v.action, ChainAction.ALLOW)


# ===========================================================================
# Run
# ===========================================================================

if __name__ == "__main__":
    unittest.main()
