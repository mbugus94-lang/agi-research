"""
Adversarial test pass for the compositional policy gate.

Closes the 2026-07-09 build's "next priority" item #1:
  "Adversarial test pass for the compositional gate
   (20 synthetic chains: maximal-fanout, secret-to-PUBLIC (not external),
    trusted-data reset attempts, in-chain policy mutation, etc.)"

The existing test_compositional_policy.py covers the *happy path* of each
deny reason and the documented JADEPUFFER pattern. This file covers the
*evasion attempts* and *boundary conditions* an attacker or a misbehaving
agent would actually try:

  1.  Secret to PUBLIC (not EXTERNAL) — leak via lower-trust sink
  2.  Trusted-data reset attempt — wash SECRET through a TRUSTED filter
  3.  Maximal-fanout (5+ distinct sinks) — TOO_MANY_DISTINCT_SINKS
  4.  In-chain policy mutation — registry change after verdict
  5.  Self-claim TRUSTED — step declares taint_in=TRUSTED while running
      is already SECRET (monotonic check must hold)
  6.  is_secret_emitting=True with empty sinks and internal taint
  7.  Two-step secret fanout — split exfil across multiple calls
  8.  Alternating trust levels — TR, UN, TR, UN, escalate
  9.  Long chain with delayed write — many reads then a single write
  10. Mixed-secret chain — SECRET in middle, sink at the end
  11. Cycle / repeated step — same verb twice
  12. requires_review bypass attempt — audit-only block
  13. Sensitive-to-PUBLIC with intermediate EXTERNAL step
  14. Audit log tampering — modify middle record, detect via prev_digest
  15. Boundary taint threshold — exact rank at threshold
  16. Sequential chains share audit log correctly
  17. All-sinks-on-one-verb — single verb with many sinks
  18. Secret emission without destination egress
  19. Write-after-untrusted with intervening trusted (saw_untrusted
      is NOT reset by trusted — verified)
  20. Comprehensive 7-step stress chain
  21. Digest determinism under reordering
  22. max_sinks boundary — exactly max_sinks+1 distinct sinks

All tests use only the public API of core.compositional_policy. No
mutation of internal state is required. Where a test does mutate
internal state (e.g. test_in_chain_policy_mutation), it does so
*after* a verdict has been produced and asserts the earlier verdict
is unchanged (immutability of verdicts under later mutation).
"""

import json
import os
import sys
import unittest
from typing import Any, Dict, List, Tuple

sys.path.insert(0, "/home/workspace/agi-research")

from core.compositional_policy import (
    ChainAction,
    ChainStep,
    ChainVerdict,
    CompositionalPolicyGate,
    DenyReason,
    TaintSource,
    VerbPolicy,
    create_gate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_jade_puffer_baseline(g: CompositionalPolicyGate) -> None:
    """Register the classic JADEPUFFER verb set used in the 2026-07-09 build."""
    g.register(VerbPolicy("read_env", TaintSource.INTERNAL, sinks=("read",)))
    g.register(VerbPolicy("http_post_external", TaintSource.EXTERNAL, sinks=("egress",)))
    g.register(
        VerbPolicy(
            "read_secret_store",
            TaintSource.SECRET,
            sinks=("read",),
            is_secret_emitting=True,
        )
    )


# ---------------------------------------------------------------------------
# 1. Secret to PUBLIC (not EXTERNAL)
# ---------------------------------------------------------------------------


class TestSecretToPublicLeak(unittest.TestCase):
    """SENSITIVE_TO_PUBLIC: SECRET data -> verb whose policy taint is PUBLIC."""

    def test_secret_then_public_sink_blocks(self):
        g = create_gate()
        g.register(VerbPolicy("read_secret", TaintSource.SECRET, sinks=("read",)))
        g.register(VerbPolicy("log_public", TaintSource.PUBLIC, sinks=("egress",)))
        chain = [
            ChainStep("read_secret", TaintSource.SECRET),
            ChainStep("log_public", TaintSource.SECRET),
        ]
        v = g.check_chain(chain)
        self.assertIn(DenyReason.SENSITIVE_TO_PUBLIC, v.reasons)
        self.assertEqual(v.action, ChainAction.BLOCK)

    def test_secret_then_public_sink_with_intervening_internal(self):
        """SENSITIVE_TO_PUBLIC should fire on the *PUBLIC step* even if a
        safe INTERNAL step sits in between (the running taint is still SECRET)."""
        g = create_gate()
        g.register(VerbPolicy("read_secret", TaintSource.SECRET, sinks=("read",)))
        g.register(VerbPolicy("internal_buffer", TaintSource.INTERNAL, sinks=("compute",)))
        g.register(VerbPolicy("log_public", TaintSource.PUBLIC, sinks=("egress",)))
        chain = [
            ChainStep("read_secret", TaintSource.SECRET),
            ChainStep("internal_buffer", TaintSource.SECRET),
            ChainStep("log_public", TaintSource.SECRET),
        ]
        v = g.check_chain(chain)
        self.assertIn(DenyReason.SENSITIVE_TO_PUBLIC, v.reasons)
        self.assertEqual(v.action, ChainAction.BLOCK)


# ---------------------------------------------------------------------------
# 2. Trusted-data reset attempt (monotonicity)
# ---------------------------------------------------------------------------


class TestTaintMonotonicity(unittest.TestCase):
    """Once data is tainted, it cannot be 'washed' to a lower taint by
    declaring a step's taint_in as TRUSTED."""

    def test_secret_step_then_trusted_step_keeps_secret(self):
        g = create_gate()
        g.register(VerbPolicy("read_secret", TaintSource.SECRET, sinks=("read",)))
        g.register(VerbPolicy("normalize", TaintSource.TRUSTED, sinks=("compute",)))
        g.register(VerbPolicy("http_post_external", TaintSource.EXTERNAL, sinks=("egress",)))
        chain = [
            ChainStep("read_secret", TaintSource.SECRET),
            ChainStep("normalize", TaintSource.TRUSTED),  # attempt to wash
            ChainStep("http_post_external", TaintSource.TRUSTED),  # claim trusted
        ]
        v = g.check_chain(chain)
        # The gate computes running_data_taint = max(running, step.taint_in).
        # After step 0 it's SECRET; step 1's taint_in=TRUSTED is the lesser.
        # Step 2's taint_in=TRUSTED is also lesser. Running taint must remain
        # SECRET (monotonicity).
        self.assertEqual(v.taint_at_each_step[-1], TaintSource.SECRET)
        # The final step's verb has taint_in=EXTERNAL (the policy's taint_in
        # is the sink taint) and running data is SECRET -> SECRET_TO_EXTERNAL.
        self.assertIn(DenyReason.SECRET_TO_EXTERNAL, v.reasons)
        self.assertEqual(v.action, ChainAction.BLOCK_AND_ESCALATE)

    def test_taint_at_each_step_is_monotonic_non_decreasing(self):
        """For any chain, taint_at_each_step should never decrease."""
        g = create_gate()
        g.register(VerbPolicy("read_user", TaintSource.USER, sinks=("read",)))
        g.register(VerbPolicy("read_external", TaintSource.EXTERNAL, sinks=("read",)))
        g.register(VerbPolicy("normalize", TaintSource.INTERNAL, sinks=("compute",)))
        chain = [
            ChainStep("read_user", TaintSource.USER),
            ChainStep("normalize", TaintSource.INTERNAL),  # lower taint
            ChainStep("read_external", TaintSource.EXTERNAL),  # raises again
            ChainStep("normalize", TaintSource.INTERNAL),  # attempt to drop
        ]
        v = g.check_chain(chain)
        # ranks: USER=2, INTERNAL=1, EXTERNAL=4
        # Running: USER(2) -> max(2,1)=2 -> max(2,4)=4 -> max(4,1)=4
        # So taint_at_each_step is non-decreasing: 2,2,4,4
        ranks = [list(TaintSource).index(t) for t in v.taint_at_each_step]
        for a, b in zip(ranks, ranks[1:]):
            self.assertGreaterEqual(b, a, f"taint decreased: {ranks}")


# ---------------------------------------------------------------------------
# 3. Maximal-fanout (TOO_MANY_DISTINCT_SINKS)
# ---------------------------------------------------------------------------


class TestMaximalFanout(unittest.TestCase):
    def test_five_distinct_sinks_with_max_sinks_3_forces_review(self):
        g = create_gate(max_sinks=3)
        g.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        g.register(VerbPolicy("write", TaintSource.INTERNAL, sinks=("write",)))
        g.register(VerbPolicy("exec", TaintSource.INTERNAL, sinks=("exec",)))
        g.register(VerbPolicy("egress", TaintSource.EXTERNAL, sinks=("egress",)))
        g.register(VerbPolicy("compute", TaintSource.INTERNAL, sinks=("compute",)))
        chain = [
            ChainStep("read", TaintSource.INTERNAL),
            ChainStep("write", TaintSource.INTERNAL),
            ChainStep("exec", TaintSource.INTERNAL),
            ChainStep("egress", TaintSource.INTERNAL),
            ChainStep("compute", TaintSource.INTERNAL),
        ]
        v = g.check_chain(chain)
        # 5 distinct sinks (read, write, exec, egress, compute) > 3 -> review
        self.assertIn(DenyReason.TOO_MANY_DISTINCT_SINKS, v.reasons)
        self.assertEqual(v.action, ChainAction.ALLOW_ONLY_REVIEW)
        self.assertEqual(len(v.sinks_seen), 5)

    def test_repeated_sink_does_not_grow_fanout(self):
        """Using the same sink twice does not increase distinct count."""
        g = create_gate(max_sinks=2)
        g.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        g.register(VerbPolicy("read2", TaintSource.INTERNAL, sinks=("read",)))
        g.register(VerbPolicy("write", TaintSource.INTERNAL, sinks=("write",)))
        g.register(VerbPolicy("egress", TaintSource.EXTERNAL, sinks=("egress",)))
        chain = [
            ChainStep("read", TaintSource.INTERNAL),
            ChainStep("read2", TaintSource.INTERNAL),
            ChainStep("write", TaintSource.INTERNAL),
            ChainStep("egress", TaintSource.INTERNAL),
        ]
        v = g.check_chain(chain)
        # 3 distinct sinks (read, write, egress) > 2 -> review
        self.assertIn(DenyReason.TOO_MANY_DISTINCT_SINKS, v.reasons)
        self.assertEqual(len(v.sinks_seen), 3)


# ---------------------------------------------------------------------------
# 4. In-chain policy mutation
# ---------------------------------------------------------------------------


class TestInChainPolicyMutation(unittest.TestCase):
    def test_mutation_after_verdict_does_not_change_verdict(self):
        g = create_gate()
        g.register(VerbPolicy("a", TaintSource.INTERNAL, sinks=("read",)))
        chain = [ChainStep("a", TaintSource.INTERNAL)]
        v1 = g.check_chain(chain)
        # Mutate the registry after the verdict was produced
        g.register(VerbPolicy("a", TaintSource.EXTERNAL, sinks=("egress",)))
        # The earlier verdict must not retroactively change
        self.assertEqual(v1.action, ChainAction.ALLOW)
        # A new chain call reflects the new policy
        v2 = g.check_chain(chain)
        self.assertEqual(v2.action, ChainAction.ALLOW)  # EXTERNAL but no UNTRUSTED
        # Mutation produced a new audit entry
        self.assertEqual(len(g._audit), 2)


# ---------------------------------------------------------------------------
# 5. Self-claim TRUSTED with running SECRET
# ---------------------------------------------------------------------------


class TestSelfClaimTainted(unittest.TestCase):
    def test_step_claiming_trusted_does_not_erase_secret_running(self):
        g = create_gate()
        g.register(VerbPolicy("read_secret", TaintSource.SECRET, sinks=("read",)))
        g.register(VerbPolicy("noop", TaintSource.INTERNAL, sinks=("compute",)))
        g.register(VerbPolicy("post", TaintSource.EXTERNAL, sinks=("egress",)))
        chain = [
            ChainStep("read_secret", TaintSource.SECRET),
            ChainStep("noop", TaintSource.TRUSTED),  # attempt to wipe
            ChainStep("post", TaintSource.TRUSTED),  # attempt to wipe
        ]
        v = g.check_chain(chain)
        # The running taint at step 2 must still be SECRET.
        # max(SECRET, TRUSTED) = SECRET; max(SECRET, TRUSTED) = SECRET
        self.assertEqual(v.taint_at_each_step[1], TaintSource.SECRET)
        self.assertEqual(v.taint_at_each_step[2], TaintSource.SECRET)
        # The final step's verb has policy.taint_in=EXTERNAL. Running data is
        # SECRET -> SECRET_TO_EXTERNAL.
        self.assertIn(DenyReason.SECRET_TO_EXTERNAL, v.reasons)
        self.assertEqual(v.action, ChainAction.BLOCK_AND_ESCALATE)


# ---------------------------------------------------------------------------
# 6. is_secret_emitting=True with no destination egress
# ---------------------------------------------------------------------------


class TestSecretEmittingInternal(unittest.TestCase):
    def test_secret_emitting_with_internal_sink_does_not_block(self):
        """A verb that emits a secret but whose sink is INTERNAL is
        safe in isolation (the secret is not egressed)."""
        g = create_gate()
        g.register(
            VerbPolicy(
                "compute_with_secret",
                TaintSource.INTERNAL,
                sinks=("compute",),
                is_secret_emitting=True,
            )
        )
        chain = [ChainStep("compute_with_secret", TaintSource.INTERNAL)]
        v = g.check_chain(chain)
        self.assertNotIn(DenyReason.SECRET_TO_EXTERNAL, v.reasons)
        self.assertNotIn(DenyReason.SENSITIVE_TO_PUBLIC, v.reasons)
        # contains_secret is True because the verb emits one
        self.assertTrue(v.contains_secret)

    def test_secret_emitting_then_internal_then_egress_blocks(self):
        """The classic 'look benign, then leak' pattern."""
        g = create_gate()
        g.register(
            VerbPolicy(
                "compute_with_secret",
                TaintSource.INTERNAL,
                sinks=("compute",),
                is_secret_emitting=True,
            )
        )
        g.register(VerbPolicy("aggregate", TaintSource.INTERNAL, sinks=("compute",)))
        g.register(VerbPolicy("post", TaintSource.EXTERNAL, sinks=("egress",)))
        chain = [
            ChainStep("compute_with_secret", TaintSource.SECRET),
            ChainStep("aggregate", TaintSource.SECRET),
            ChainStep("post", TaintSource.SECRET),
        ]
        v = g.check_chain(chain)
        self.assertIn(DenyReason.SECRET_TO_EXTERNAL, v.reasons)
        self.assertEqual(v.action, ChainAction.BLOCK_AND_ESCALATE)


# ---------------------------------------------------------------------------
# 7. Two-step secret fanout (split exfil)
# ---------------------------------------------------------------------------


class TestSplitExfiltration(unittest.TestCase):
    def test_secret_to_internal_store_then_egress(self):
        g = create_gate()
        g.register(
            VerbPolicy(
                "read_secret_store",
                TaintSource.SECRET,
                sinks=("read",),
                is_secret_emitting=True,
            )
        )
        g.register(VerbPolicy("log_internal", TaintSource.INTERNAL, sinks=("compute",)))
        g.register(VerbPolicy("http_post_external", TaintSource.EXTERNAL, sinks=("egress",)))
        chain = [
            ChainStep("read_secret_store", TaintSource.SECRET),
            ChainStep("log_internal", TaintSource.SECRET),
            ChainStep("http_post_external", TaintSource.SECRET),
        ]
        v = g.check_chain(chain)
        # Same shape as JADEPUFFER but split with an internal step in between
        self.assertIn(DenyReason.SECRET_TO_EXTERNAL, v.reasons)
        self.assertEqual(v.action, ChainAction.BLOCK_AND_ESCALATE)
        self.assertTrue(v.contains_secret)


# ---------------------------------------------------------------------------
# 8. Alternating trust levels
# ---------------------------------------------------------------------------


class TestAlternatingTrust(unittest.TestCase):
    def test_trusted_untrusted_trusted_untrusted_writes_blocks(self):
        g = create_gate()
        g.register(VerbPolicy("trusted_read", TaintSource.TRUSTED, sinks=("read",)))
        g.register(VerbPolicy("untrusted_read", TaintSource.UNTRUSTED, sinks=("read",)))
        g.register(VerbPolicy("write", TaintSource.INTERNAL, sinks=("write",)))
        chain = [
            ChainStep("trusted_read", TaintSource.TRUSTED),
            ChainStep("untrusted_read", TaintSource.UNTRUSTED),
            ChainStep("trusted_read", TaintSource.TRUSTED),  # attempt to drop
            ChainStep("untrusted_read", TaintSource.UNTRUSTED),  # back up
            ChainStep("write", TaintSource.UNTRUSTED),
        ]
        v = g.check_chain(chain)
        # After the first UNTRUSTED, saw_untrusted is True. The final write
        # triggers WRITE_AFTER_UNTRUSTED.
        self.assertIn(DenyReason.WRITE_AFTER_UNTRUSTED, v.reasons)
        self.assertEqual(v.action, ChainAction.BLOCK)


# ---------------------------------------------------------------------------
# 9. Long chain with delayed write
# ---------------------------------------------------------------------------


class TestLongChainDelayedWrite(unittest.TestCase):
    def test_ten_reads_then_single_write_untrusted_blocks(self):
        g = create_gate()
        g.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        g.register(VerbPolicy("read_untrusted", TaintSource.UNTRUSTED, sinks=("read",)))
        g.register(VerbPolicy("write", TaintSource.INTERNAL, sinks=("write",)))
        chain = [
            ChainStep("read", TaintSource.INTERNAL)
            for _ in range(9)
        ] + [
            ChainStep("read_untrusted", TaintSource.UNTRUSTED),
            ChainStep("write", TaintSource.UNTRUSTED),
        ]
        v = g.check_chain(chain)
        # The final write is after an UNTRUSTED step -> WRITE_AFTER_UNTRUSTED
        self.assertIn(DenyReason.WRITE_AFTER_UNTRUSTED, v.reasons)
        self.assertEqual(v.action, ChainAction.BLOCK)
        # 2 distinct sinks (read, write) <= max_sinks=3 -> no fanout alarm
        self.assertNotIn(DenyReason.TOO_MANY_DISTINCT_SINKS, v.reasons)


# ---------------------------------------------------------------------------
# 10. Mixed-secret chain
# ---------------------------------------------------------------------------


class TestMixedSecretChain(unittest.TestCase):
    def test_secret_in_middle_blocks_via_running_taint(self):
        g = create_gate()
        g.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        g.register(VerbPolicy("read_secret", TaintSource.SECRET, sinks=("read",)))
        g.register(VerbPolicy("post", TaintSource.EXTERNAL, sinks=("egress",)))
        chain = [
            ChainStep("read", TaintSource.INTERNAL),
            ChainStep("read_secret", TaintSource.SECRET),
            ChainStep("read", TaintSource.SECRET),  # running stays SECRET
            ChainStep("post", TaintSource.SECRET),
        ]
        v = g.check_chain(chain)
        self.assertIn(DenyReason.SECRET_TO_EXTERNAL, v.reasons)
        self.assertEqual(v.action, ChainAction.BLOCK_AND_ESCALATE)
        # Running taint never drops back to INTERNAL after step 1
        for t in v.taint_at_each_step[1:]:
            self.assertEqual(t, TaintSource.SECRET)


# ---------------------------------------------------------------------------
# 11. Cycle / repeated step
# ---------------------------------------------------------------------------


class TestCycle(unittest.TestCase):
    def test_same_verb_repeated_in_chain(self):
        g = create_gate()
        g.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        chain = [ChainStep("read", TaintSource.INTERNAL) for _ in range(5)]
        v = g.check_chain(chain)
        self.assertEqual(v.action, ChainAction.ALLOW)
        # Same verb, same taint, same sinks -> safe
        self.assertEqual(len(v.sinks_seen), 1)

    def test_same_verb_with_escalating_taint(self):
        g = create_gate()
        g.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        chain = [
            ChainStep("read", TaintSource.INTERNAL),
            ChainStep("read", TaintSource.USER),
            ChainStep("read", TaintSource.EXTERNAL),
            ChainStep("read", TaintSource.UNTRUSTED),
        ]
        v = g.check_chain(chain)
        # No write after untrusted, no egress -> still ALLOW
        self.assertEqual(v.action, ChainAction.ALLOW)
        # Running taint escalates monotonically
        ranks = [list(TaintSource).index(t) for t in v.taint_at_each_step]
        self.assertEqual(ranks, sorted(ranks))


# ---------------------------------------------------------------------------
# 12. requires_review bypass attempt
# ---------------------------------------------------------------------------


class TestRequiresReviewBypass(unittest.TestCase):
    def test_requires_review_does_not_become_allow(self):
        """A chain where every step requires_review must not silently
        downgrade to ALLOW. The conservative posture is ALLOW_ONLY_REVIEW."""
        g = create_gate()
        g.register(
            VerbPolicy(
                "review_me",
                TaintSource.INTERNAL,
                sinks=("compute",),
                requires_review=True,
            )
        )
        chain = [ChainStep("review_me", TaintSource.INTERNAL)]
        v = g.check_chain(chain)
        self.assertEqual(v.action, ChainAction.ALLOW_ONLY_REVIEW)
        # The verb's requires_review flag must surface, not be hidden
        self.assertNotEqual(v.action, ChainAction.ALLOW)

    def test_requires_review_with_secret_emission_still_blocks(self):
        """If a review-required verb ALSO emits a secret to external, the
        chain should escalate (SECRET_TO_EXTERNAL has higher priority)."""
        g = create_gate()
        g.register(
            VerbPolicy(
                "review_then_post",
                TaintSource.EXTERNAL,
                sinks=("egress",),
                requires_review=True,
                is_secret_emitting=True,
            )
        )
        chain = [ChainStep("review_then_post", TaintSource.SECRET)]
        v = g.check_chain(chain)
        self.assertIn(DenyReason.SECRET_TO_EXTERNAL, v.reasons)
        self.assertEqual(v.action, ChainAction.BLOCK_AND_ESCALATE)


# ---------------------------------------------------------------------------
# 13. Sensitive-to-PUBLIC with intermediate EXTERNAL step
# ---------------------------------------------------------------------------


class TestSensitiveToPublicIntermediate(unittest.TestCase):
    def test_secret_to_external_then_public_sink_still_blocks(self):
        g = create_gate()
        g.register(VerbPolicy("read_secret", TaintSource.SECRET, sinks=("read",)))
        g.register(VerbPolicy("post_external", TaintSource.EXTERNAL, sinks=("egress",)))
        g.register(VerbPolicy("log_public", TaintSource.PUBLIC, sinks=("egress",)))
        chain = [
            ChainStep("read_secret", TaintSource.SECRET),
            ChainStep("post_external", TaintSource.SECRET),
            ChainStep("log_public", TaintSource.SECRET),
        ]
        v = g.check_chain(chain)
        # Both SECRET_TO_EXTERNAL (step 1) and SENSITIVE_TO_PUBLIC (step 2) fire
        self.assertIn(DenyReason.SECRET_TO_EXTERNAL, v.reasons)
        self.assertIn(DenyReason.SENSITIVE_TO_PUBLIC, v.reasons)
        # SECRET_TO_EXTERNAL has the highest priority -> BLOCK_AND_ESCALATE
        self.assertEqual(v.action, ChainAction.BLOCK_AND_ESCALATE)


# ---------------------------------------------------------------------------
# 14. Audit log tampering
# ---------------------------------------------------------------------------


class TestAuditLogTampering(unittest.TestCase):
    def test_modify_middle_record_detected_via_prev_digest(self):
        """Modifying a record in the middle of the audit log must be
        detectable because subsequent records chain via prev_digest.
        The next record's prev_digest will no longer match the actual
        digest of the tampered record.
        """
        g = create_gate()
        g.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        for _ in range(5):
            g.check_chain([ChainStep("read", TaintSource.INTERNAL)])
        # The digest of the tampered record itself is fixed at write-time
        # (it's hashed from the verdict content), so we cannot detect
        # tampering of record[2] by inspecting record[2] alone. Instead,
        # the *next* record's prev_digest was the original record[2]
        # digest; mutating record[2] but recomputing only its own digest
        # leaves the chain inconsistent.
        original_record_2_digest = g._audit[2]["digest"]
        # Tamper: change the action in the middle record WITHOUT
        # recomputing its digest. This simulates a partial tamper
        # (an attacker who modifies state but doesn't update the chain).
        g._audit[2]["verdict"]["action"] = ChainAction.BLOCK.value
        # The next record (record 3) carries the original prev_digest
        # (the digest that record 2 HAD, not the digest it has after
        # tamper). So record 3's prev_digest is now stale relative to
        # record 2's current contents -- detectable.
        self.assertEqual(
            g._audit[3]["prev_digest"], original_record_2_digest
        )
        # But the tampered record 2's contents no longer match its
        # stored digest: recomputing the hash from current contents
        # will differ from the stored digest. This is the tamper signal.
        recomputed = g._digest_verdict(
            ChainVerdict(
                action=ChainAction(
                    g._audit[2]["verdict"]["action"]
                ),
                reasons=[
                    DenyReason(r) for r in g._audit[2]["verdict"]["reasons"]
                ],
                taint_at_each_step=[
                    TaintSource(t)
                    for t in g._audit[2]["verdict"]["taint_at_each_step"]
                ],
                sink_taint_at_each_step=[
                    TaintSource(t)
                    for t in g._audit[2]["verdict"]["sink_taint_at_each_step"]
                ],
                sinks_seen=tuple(g._audit[2]["verdict"]["sinks_seen"]),
                contains_secret=g._audit[2]["verdict"]["contains_secret"],
            ),
            [ChainStep("read", TaintSource.INTERNAL)],
        )
        # NOTE: the stored digest was computed BEFORE the tamper, so
        # it reflects the original (untampered) verdict. The current
        # contents are different. We assert the recomputed digest
        # differs from the stored digest.
        self.assertNotEqual(recomputed, g._audit[2]["digest"])


# ---------------------------------------------------------------------------
# 15. Boundary taint threshold
# ---------------------------------------------------------------------------


class TestBoundaryTaintThreshold(unittest.TestCase):
    def test_taint_exactly_at_threshold_allows(self):
        """A step whose running taint rank == policy max_taint_threshold
        rank should NOT trigger TAINT_ESCALATION (strict greater-than)."""
        g = create_gate()
        # User data is rank 2; threshold at USER (also rank 2)
        g.register(
            VerbPolicy(
                "read_user",
                TaintSource.INTERNAL,
                sinks=("read",),
                max_taint_threshold=TaintSource.USER,
            )
        )
        chain = [ChainStep("read_user", TaintSource.USER)]
        v = g.check_chain(chain)
        self.assertNotIn(DenyReason.TAINT_ESCALATION, v.reasons)

    def test_taint_one_rank_above_threshold_blocks(self):
        g = create_gate()
        g.register(
            VerbPolicy(
                "read_user",
                TaintSource.INTERNAL,
                sinks=("read",),
                max_taint_threshold=TaintSource.USER,
            )
        )
        # EXTERNAL is rank 4 > USER rank 2
        chain = [ChainStep("read_user", TaintSource.EXTERNAL)]
        v = g.check_chain(chain)
        self.assertIn(DenyReason.TAINT_ESCALATION, v.reasons)
        self.assertEqual(v.action, ChainAction.BLOCK)

    def test_threshold_with_untrusted_input(self):
        g = create_gate()
        g.register(
            VerbPolicy(
                "read_user",
                TaintSource.INTERNAL,
                sinks=("read",),
                max_taint_threshold=TaintSource.EXTERNAL,
            )
        )
        # UNTRUSTED is rank 5 > EXTERNAL rank 4
        chain = [ChainStep("read_user", TaintSource.UNTRUSTED)]
        v = g.check_chain(chain)
        self.assertIn(DenyReason.TAINT_ESCALATION, v.reasons)


# ---------------------------------------------------------------------------
# 16. Sequential chains share audit log
# ---------------------------------------------------------------------------


class TestSequentialChains(unittest.TestCase):
    def test_two_chains_emit_two_audit_records(self):
        g = create_gate()
        g.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        g.check_chain([ChainStep("read", TaintSource.INTERNAL)])
        g.check_chain([ChainStep("read", TaintSource.INTERNAL)])
        self.assertEqual(len(g._audit), 2)
        # Second record chains off the first
        self.assertEqual(g._audit[1]["prev_digest"], g._audit[0]["digest"])
        # First record has no prev
        self.assertEqual(g._audit[0]["prev_digest"], "")

    def test_mixed_verdicts_in_audit_log(self):
        g = create_gate()
        g.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        g.register(VerbPolicy("write", TaintSource.INTERNAL, sinks=("write",)))
        g.register(VerbPolicy("read_untrusted", TaintSource.UNTRUSTED, sinks=("read",)))
        # 1. safe
        g.check_chain([ChainStep("read", TaintSource.INTERNAL)])
        # 2. write after untrusted -> BLOCK
        g.check_chain(
            [
                ChainStep("read_untrusted", TaintSource.UNTRUSTED),
                ChainStep("write", TaintSource.UNTRUSTED),
            ]
        )
        # 3. safe
        g.check_chain([ChainStep("read", TaintSource.INTERNAL)])
        self.assertEqual(len(g._audit), 3)
        self.assertEqual(g._audit[0]["verdict"]["action"], "allow")
        self.assertEqual(g._audit[1]["verdict"]["action"], "block")
        self.assertEqual(g._audit[2]["verdict"]["action"], "allow")


# ---------------------------------------------------------------------------
# 17. All-sinks-on-one-verb
# ---------------------------------------------------------------------------


class TestAllSinksOnOneVerb(unittest.TestCase):
    def test_one_verb_with_many_sinks(self):
        g = create_gate(max_sinks=3)
        # One verb with sinks=("read", "write", "exec", "egress")
        g.register(
            VerbPolicy(
                "do_everything",
                TaintSource.INTERNAL,
                sinks=("read", "write", "exec", "egress"),
            )
        )
        chain = [ChainStep("do_everything", TaintSource.INTERNAL)]
        v = g.check_chain(chain)
        # 4 sinks > 3 -> review
        self.assertIn(DenyReason.TOO_MANY_DISTINCT_SINKS, v.reasons)
        self.assertEqual(v.action, ChainAction.ALLOW_ONLY_REVIEW)


# ---------------------------------------------------------------------------
# 18. Secret emission without destination egress
# ---------------------------------------------------------------------------


class TestSecretEmittingNoEgress(unittest.TestCase):
    def test_secret_emitter_chained_with_internal_sinks_allows(self):
        g = create_gate()
        g.register(
            VerbPolicy(
                "emit_secret",
                TaintSource.INTERNAL,
                sinks=("compute",),
                is_secret_emitting=True,
            )
        )
        g.register(VerbPolicy("store", TaintSource.INTERNAL, sinks=("write",)))
        chain = [
            ChainStep("emit_secret", TaintSource.INTERNAL),
            ChainStep("store", TaintSource.INTERNAL),
        ]
        v = g.check_chain(chain)
        self.assertNotIn(DenyReason.SECRET_TO_EXTERNAL, v.reasons)
        self.assertTrue(v.contains_secret)
        # No egress sink -> not blocked
        self.assertEqual(v.action, ChainAction.ALLOW)


# ---------------------------------------------------------------------------
# 19. saw_untrusted is not reset by trusted
# ---------------------------------------------------------------------------


class TestSawUntrustedPersistence(unittest.TestCase):
    def test_trusted_after_untrusted_does_not_reset_flag(self):
        """The internal `saw_untrusted` flag is set when an UNTRUSTED or
        EXTERNAL step is seen. It must NOT be reset by a subsequent
        TRUSTED step (otherwise the agent could 'wash' the flag)."""
        g = create_gate()
        g.register(VerbPolicy("read_untrusted", TaintSource.UNTRUSTED, sinks=("read",)))
        g.register(VerbPolicy("read_trusted", TaintSource.TRUSTED, sinks=("read",)))
        g.register(VerbPolicy("write", TaintSource.INTERNAL, sinks=("write",)))
        chain = [
            ChainStep("read_untrusted", TaintSource.UNTRUSTED),
            ChainStep("read_trusted", TaintSource.TRUSTED),  # attempt to reset
            ChainStep("read_trusted", TaintSource.TRUSTED),  # attempt to reset
            ChainStep("write", TaintSource.TRUSTED),  # taint now TRUSTED, but flag persists
        ]
        v = g.check_chain(chain)
        # Even though the running taint is dropped back to TRUSTED, the
        # write-after-untrusted pattern is preserved by the saw_untrusted
        # flag.
        self.assertIn(DenyReason.WRITE_AFTER_UNTRUSTED, v.reasons)
        self.assertEqual(v.action, ChainAction.BLOCK)


# ---------------------------------------------------------------------------
# 20. Comprehensive 7-step stress chain
# ---------------------------------------------------------------------------


class TestComprehensiveStressChain(unittest.TestCase):
    def test_jade_puffer_with_ancillary_steps(self):
        """A 7-step chain that mirrors the 2026-07-01 JADEPUFFER incident
        with additional safe-looking steps interspersed."""
        g = create_gate()
        _register_jade_puffer_baseline(g)
        g.register(VerbPolicy("read_file", TaintSource.INTERNAL, sinks=("read",)))
        g.register(VerbPolicy("log", TaintSource.INTERNAL, sinks=("compute",)))
        chain = [
            ChainStep("read_file", TaintSource.INTERNAL),         # safe
            ChainStep("read_env", TaintSource.INTERNAL),          # safe
            ChainStep("http_post_external", TaintSource.INTERNAL),  # suspicious (exfil probe)
            ChainStep("read_secret_store", TaintSource.SECRET),  # secret acquired
            ChainStep("log", TaintSource.SECRET),                # attempt to mask
            ChainStep("read_env", TaintSource.SECRET),           # probe
            ChainStep("http_post_external", TaintSource.SECRET), # exfil
        ]
        v = g.check_chain(chain)
        self.assertIn(DenyReason.SECRET_TO_EXTERNAL, v.reasons)
        self.assertEqual(v.action, ChainAction.BLOCK_AND_ESCALATE)
        self.assertTrue(v.contains_secret)
        # Audit log captured exactly one record for this chain
        self.assertEqual(len(g._audit), 1)


# ---------------------------------------------------------------------------
# 21. Digest determinism under reordering
# ---------------------------------------------------------------------------


class TestDigestDeterminism(unittest.TestCase):
    def test_same_chain_same_digest(self):
        g = create_gate()
        g.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        chain = [ChainStep("read", TaintSource.INTERNAL)]
        v1 = g.check_chain(chain)
        v2 = g.check_chain(chain)
        self.assertEqual(v1.digest, v2.digest)

    def test_reordered_chain_different_digest(self):
        g = create_gate()
        g.register(VerbPolicy("a", TaintSource.INTERNAL, sinks=("read",)))
        g.register(VerbPolicy("b", TaintSource.INTERNAL, sinks=("compute",)))
        chain1 = [ChainStep("a", TaintSource.INTERNAL), ChainStep("b", TaintSource.INTERNAL)]
        chain2 = [ChainStep("b", TaintSource.INTERNAL), ChainStep("a", TaintSource.INTERNAL)]
        v1 = g.check_chain(chain1)
        v2 = g.check_chain(chain2)
        self.assertNotEqual(v1.digest, v2.digest)

    def test_extra_step_changes_digest(self):
        g = create_gate()
        g.register(VerbPolicy("a", TaintSource.INTERNAL, sinks=("read",)))
        g.register(VerbPolicy("b", TaintSource.INTERNAL, sinks=("read",)))
        chain1 = [ChainStep("a", TaintSource.INTERNAL)]
        chain2 = [ChainStep("a", TaintSource.INTERNAL), ChainStep("b", TaintSource.INTERNAL)]
        v1 = g.check_chain(chain1)
        v2 = g.check_chain(chain2)
        self.assertNotEqual(v1.digest, v2.digest)


# ---------------------------------------------------------------------------
# 22. max_sinks boundary
# ---------------------------------------------------------------------------


class TestMaxSinksBoundary(unittest.TestCase):
    def test_exactly_max_sinks_allows(self):
        g = create_gate(max_sinks=3)
        g.register(VerbPolicy("a", TaintSource.INTERNAL, sinks=("read",)))
        g.register(VerbPolicy("b", TaintSource.INTERNAL, sinks=("write",)))
        g.register(VerbPolicy("c", TaintSource.INTERNAL, sinks=("exec",)))
        chain = [ChainStep("a"), ChainStep("b"), ChainStep("c")]
        v = g.check_chain(chain)
        # 3 distinct sinks == max_sinks=3 -> no fanout alarm
        self.assertNotIn(DenyReason.TOO_MANY_DISTINCT_SINKS, v.reasons)
        self.assertEqual(v.action, ChainAction.ALLOW)

    def test_max_sinks_plus_one_forces_review(self):
        g = create_gate(max_sinks=3)
        g.register(VerbPolicy("a", TaintSource.INTERNAL, sinks=("read",)))
        g.register(VerbPolicy("b", TaintSource.INTERNAL, sinks=("write",)))
        g.register(VerbPolicy("c", TaintSource.INTERNAL, sinks=("exec",)))
        g.register(VerbPolicy("d", TaintSource.INTERNAL, sinks=("egress",)))
        chain = [ChainStep("a"), ChainStep("b"), ChainStep("c"), ChainStep("d")]
        v = g.check_chain(chain)
        # 4 distinct sinks > 3 -> review
        self.assertIn(DenyReason.TOO_MANY_DISTINCT_SINKS, v.reasons)
        self.assertEqual(v.action, ChainAction.ALLOW_ONLY_REVIEW)

    def test_max_sinks_1_clamps_to_1(self):
        """max_sinks=0 should be clamped to 1 (per TestGateConstruction)."""
        g = create_gate(max_sinks=0)
        self.assertEqual(g._max_sinks, 1)
        g.register(VerbPolicy("a", TaintSource.INTERNAL, sinks=("read",)))
        g.register(VerbPolicy("b", TaintSource.INTERNAL, sinks=("write",)))
        chain = [ChainStep("a"), ChainStep("b")]
        v = g.check_chain(chain)
        # 2 sinks > 1 -> review
        self.assertIn(DenyReason.TOO_MANY_DISTINCT_SINKS, v.reasons)


# ---------------------------------------------------------------------------
# Integration: verdict digest is SHA-256 (regression)
# ---------------------------------------------------------------------------


class TestDigestFormat(unittest.TestCase):
    def test_digest_is_64_hex_chars(self):
        g = create_gate()
        g.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        v = g.check_chain([ChainStep("read", TaintSource.INTERNAL)])
        self.assertEqual(len(v.digest), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in v.digest))

    def test_to_dict_round_trip_preserves_digest(self):
        g = create_gate()
        g.register(VerbPolicy("read", TaintSource.INTERNAL, sinks=("read",)))
        v = g.check_chain([ChainStep("read", TaintSource.INTERNAL)])
        d = v.to_dict()
        self.assertEqual(d["digest"], v.digest)
        # Should be JSON-serializable
        blob = json.dumps(d, sort_keys=True)
        self.assertIsInstance(blob, str)


if __name__ == "__main__":
    unittest.main()
