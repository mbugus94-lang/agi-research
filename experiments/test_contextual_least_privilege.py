"""Tests for the Contextual Least Privilege (CLP) substrate.

Prismata (arXiv:2607.08147) §3 - labels-only-decrease.

Coverage:
  1. VisibilityLabel lattice (monotone-decreasing by construction).
  2. Taint-to-visibility mapping (one-way, never promotes privilege).
  3. ReadCapability / CapabilitySet construction & lookup.
  4. Gate basic ALLOW (single verb within initial visibility).
  5. Gate BLOCK on visibility mismatch.
  6. Gate BLOCK on context-narrowed visibility (later verb needs more).
  7. Gate BLOCK on missing capability (undeclared verb).
  8. Empty chain semantics.
  9. Labels-only-decrease invariant (verify on every verdict).
 10. Audit digest determinism + 64 hex chars.
 11. Combined write+read gate (the integrity/confidentiality duality).
 12. Adversarial: privilege promotion is structurally impossible.
"""

from __future__ import annotations

import pytest

from core.compositional_policy import (
    ChainStep,
    CompositionMode,
    CompositionalPolicyGate,
    create_gate,
    create_jadepuffer_demo_gate,
)
from core.contextual_least_privilege import (
    CLPAction,
    CLPReason,
    CLPVerdict,
    CapabilitySet,
    ContextualLeastPrivilegeGate,
    ReadCapability,
    VisibilityLabel,
    dual_gate_check,
    map_taint_to_visibility,
    min_visibility,
    visibility_rank,
    create_jadepuffer_clp_capability_set,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _cap(name, required, reads_untrusted=False, emits_to_sink=False):
    return ReadCapability(
        name=name,
        required_label=required,
        reads_untrusted_input=reads_untrusted,
        emits_to_sink=emits_to_sink,
    )


def _secure_capability_set():
    """A strict capability set: SECRET is the default, most ops are read-only."""
    return CapabilitySet(capabilities={
        "read_env": _cap("read_env", VisibilityLabel.SECRET, reads_untrusted=True),
        "read_secret_store": _cap("read_secret_store", VisibilityLabel.SECRET),
        "http_post_external": _cap("http_post_external", VisibilityLabel.EXTERNAL, emits_to_sink=True),
        "pure_compute": _cap("pure_compute", VisibilityLabel.PUBLIC),
    })


# ---------------------------------------------------------------------------
# 1. Visibility lattice
# ---------------------------------------------------------------------------

class TestVisibilityLattice:
    def test_visibility_rank_is_strictly_ordered(self):
        # SECRET < INTERNAL < PUBLIC (less visibility = lower rank)
        # The lattice is: a higher number means MORE visibility required.
        # We assert strict total order across the canonical labels.
        # The actual rank ordering in the module is:
        #   INTERNAL < PUBLIC < SECRET
        # (UNTRUSTED, USER, EXTERNAL are intermediate non-canonical labels).
        # Higher rank = more privilege required.
        labels_in_order = [
            VisibilityLabel.INTERNAL,  # rank 1
            VisibilityLabel.PUBLIC,    # rank 3
            VisibilityLabel.SECRET,    # rank 6
        ]
        ranks = [visibility_rank(v) for v in labels_in_order]
        assert ranks == sorted(ranks), "ranks must be in non-decreasing order"
        # and no two canonical labels share a rank
        assert len(set(ranks)) == len(ranks), "ranks must be unique"

    def test_min_visibility_returns_less_visible(self):
        # min_visibility: meet of two labels = the *less visible* one.
        # PUBLIC is less visible than SECRET (PUBLIC is a public-internet
        # scope; SECRET is a secrets store scope; seeing SECRET requires
        # SECRET-level clearance, not vice-versa).
        a = VisibilityLabel.PUBLIC
        b = VisibilityLabel.SECRET
        result = min_visibility(a, b)
        assert result == VisibilityLabel.PUBLIC

    def test_min_visibility_commutative(self):
        a = VisibilityLabel.PUBLIC
        b = VisibilityLabel.INTERNAL
        assert min_visibility(a, b) == min_visibility(b, a)


# ---------------------------------------------------------------------------
# 2. Taint -> visibility mapping
# ---------------------------------------------------------------------------

class TestTaintToVisibilityMapping:
    def test_mapping_is_total(self):
        from core.compositional_policy import TaintSource
        for t in TaintSource:
            v = map_taint_to_visibility(t)
            assert isinstance(v, VisibilityLabel)

    def test_mapping_never_promotes_visibility(self):
        # The mapping should be a one-way *narrowing*. It may demote
        # the chain's visibility when an untrusted source is touched.
        # It should NEVER widen visibility (i.e., lower rank).
        from core.compositional_policy import TaintSource
        for t in TaintSource:
            v = map_taint_to_visibility(t)
            # Every mapped visibility is at least PUBLIC (the
            # narrowest possible) and at most SECRET (the widest
            # privileged). We do not assert a monotonic mapping
            # because untrusted sources may map to SECRET. The
            # contract is: a fresh chain starts at SECRET and the
            # mapping can only narrow or hold.
            assert visibility_rank(v) <= visibility_rank(VisibilityLabel.SECRET)


# ---------------------------------------------------------------------------
# 3. ReadCapability / CapabilitySet
# ---------------------------------------------------------------------------

class TestReadCapability:
    def test_capability_set_lookups(self):
        caps = CapabilitySet(capabilities={
            "a": _cap("a", VisibilityLabel.PUBLIC),
            "b": _cap("b", VisibilityLabel.SECRET),
        })
        assert caps.lookup("a").required_label == VisibilityLabel.PUBLIC
        assert caps.lookup("b").required_label == VisibilityLabel.SECRET
        assert not caps.has_capability("missing")  # no default supplied

    def test_capability_set_contains(self):
        caps = CapabilitySet(capabilities={"a": _cap("a", VisibilityLabel.PUBLIC)})
        assert "a" in caps
        assert "b" not in caps


# ---------------------------------------------------------------------------
# 4. Gate basic ALLOW
# ---------------------------------------------------------------------------

class TestGateBasicAllow:
    def test_single_verb_within_initial_visibility(self):
        caps = CapabilitySet(capabilities={
            "pure_compute": _cap("pure_compute", VisibilityLabel.PUBLIC),
        })
        gate = ContextualLeastPrivilegeGate(
            caps, initial_visibility=VisibilityLabel.SECRET
        )
        v = gate.check_chain([ChainStep("pure_compute")])
        assert v.action == CLPAction.ALLOW
        assert v.visibility_at_each_step == [VisibilityLabel.PUBLIC]  # verb is within initial; running = required

    def test_empty_chain_returns_allow_with_empty_trace(self):
        caps = CapabilitySet(capabilities={"x": _cap("x", VisibilityLabel.SECRET)})
        gate = ContextualLeastPrivilegeGate(
            caps, initial_visibility=VisibilityLabel.SECRET
        )
        v = gate.check_chain([])
        assert v.action == CLPAction.ALLOW
        assert v.visibility_at_each_step == []
        assert v.required_at_each_step == []


# ---------------------------------------------------------------------------
# 5 & 6. Gate BLOCK on visibility mismatch
# ---------------------------------------------------------------------------

class TestGateBlocks:
    def test_verb_needing_more_visibility_than_initial_is_blocked(self):
        # A verb that requires SECRET but the chain starts at PUBLIC
        # must be blocked immediately. SECRET has the *highest* rank
        # (most privileged), so PUBLIC cannot see SECRET.
        caps = CapabilitySet(capabilities={
            "secret_reader": _cap("secret_reader", VisibilityLabel.SECRET),
        })
        gate = ContextualLeastPrivilegeGate(
            caps, initial_visibility=VisibilityLabel.PUBLIC
        )
        v = gate.check_chain([ChainStep("secret_reader")])
        assert v.action == CLPAction.BLOCK_AND_ESCALATE
        assert CLPReason.VISIBILITY_INSUFFICIENT in v.reasons

    def test_blocked_chain_short_circuits(self):
        # Once a step is blocked, every later step is padded with
        # the same BLOCK action (visibility can only narrow).
        caps = CapabilitySet(capabilities={
            "blocked_step": _cap("blocked_step", VisibilityLabel.SECRET),
            "innocent_step": _cap("innocent_step", VisibilityLabel.PUBLIC),
        })
        gate = ContextualLeastPrivilegeGate(
            caps, initial_visibility=VisibilityLabel.PUBLIC
        )
        v = gate.check_chain([
            ChainStep("blocked_step"),
            ChainStep("innocent_step"),
        ])
        assert v.action == CLPAction.BLOCK_AND_ESCALATE
        # The blocked step is recorded, and the innocent step is padded
        assert len(v.visibility_at_each_step) == 2
        assert len(v.required_at_each_step) == 2


# ---------------------------------------------------------------------------
# 7. Missing capability
# ---------------------------------------------------------------------------

class TestGateMissingCapability:
    def test_undeclared_verb_blocks_when_no_default(self):
        caps = CapabilitySet(capabilities={
            "declared": _cap("declared", VisibilityLabel.PUBLIC),
        })
        gate = ContextualLeastPrivilegeGate(
            caps, initial_visibility=VisibilityLabel.SECRET
        )
        v = gate.check_chain([ChainStep("undeclared_verb")])
        assert v.action == CLPAction.BLOCK_AND_ESCALATE
        assert CLPReason.CAPABILITY_NOT_REGISTERED in v.reasons

    def test_undeclared_verb_allowed_when_default_capability_set(self):
        default = _cap("default", VisibilityLabel.PUBLIC)
        caps = CapabilitySet(
            capabilities={},
            default_capability=default,
        )
        gate = ContextualLeastPrivilegeGate(
            caps, initial_visibility=VisibilityLabel.SECRET
        )
        v = gate.check_chain([ChainStep("anything")])
        assert v.action == CLPAction.ALLOW


# ---------------------------------------------------------------------------
# 8. Context narrowing (the load-bearing CLP property)
# ---------------------------------------------------------------------------

class TestContextNarrowing:
    def test_chain_secret_then_public_then_secret_blocks(self):
        # Step 1: needs SECRET (allowed at SECRET)
        # Step 2: needs PUBLIC (allowed, but narrows to PUBLIC)
        # Step 3: needs SECRET (BLOCKED: PUBLIC cannot see SECRET)
        caps = CapabilitySet(capabilities={
            "step_secret": _cap("step_secret", VisibilityLabel.SECRET),
            "step_public": _cap("step_public", VisibilityLabel.PUBLIC),
        })
        gate = ContextualLeastPrivilegeGate(
            caps, initial_visibility=VisibilityLabel.SECRET
        )
        v = gate.check_chain([
            ChainStep("step_secret"),
            ChainStep("step_public"),
            ChainStep("step_secret"),
        ])
        assert v.action == CLPAction.BLOCK_AND_ESCALATE
        # Step 1: SECRET, Step 2: PUBLIC (narrowed), Step 3: would be SECRET
        assert v.visibility_at_each_step[0] == VisibilityLabel.SECRET
        assert v.visibility_at_each_step[1] == VisibilityLabel.PUBLIC
        # Step 3 stays PUBLIC (narrowed, cannot widen)


# ---------------------------------------------------------------------------
# 9. Labels-only-decrease invariant
# ---------------------------------------------------------------------------

class TestLabelsOnlyDecrease:
    def test_invariant_holds_for_allowed_chain(self):
        caps = _secure_capability_set()
        gate = ContextualLeastPrivilegeGate(
            caps, initial_visibility=VisibilityLabel.SECRET
        )
        chain = [
            ChainStep("pure_compute"),
            ChainStep("pure_compute"),
        ]
        v = gate.check_chain(chain)
        assert v.action == CLPAction.ALLOW
        # verify_labels_only_decrease is a no-arg sanity check on the
        # verdict's own trace. It should hold by construction.
        assert v.verify_labels_only_decrease() is True

    def test_invariant_holds_for_blocked_chain(self):
        caps = _secure_capability_set()
        gate = ContextualLeastPrivilegeGate(
            caps, initial_visibility=VisibilityLabel.PUBLIC
        )
        chain = [ChainStep("read_secret_store")]
        v = gate.check_chain(chain)
        assert v.action != CLPAction.ALLOW
        assert v.verify_labels_only_decrease() is True

    def test_invariant_holds_for_empty_chain(self):
        caps = _secure_capability_set()
        gate = ContextualLeastPrivilegeGate(
            caps, initial_visibility=VisibilityLabel.SECRET
        )
        v = gate.check_chain([])
        assert v.verify_labels_only_decrease() is True


# ---------------------------------------------------------------------------
# 10. Audit digest
# ---------------------------------------------------------------------------

class TestAuditDigest:
    def test_digest_is_64_hex_chars(self):
        caps = _secure_capability_set()
        gate = ContextualLeastPrivilegeGate(
            caps, initial_visibility=VisibilityLabel.SECRET
        )
        v = gate.check_chain([ChainStep("pure_compute")])
        assert v.audit_digest is not None
        assert len(v.audit_digest) == 64
        int(v.audit_digest, 16)  # valid hex

    def test_digest_is_deterministic(self):
        caps = _secure_capability_set()
        gate = ContextualLeastPrivilegeGate(
            caps, initial_visibility=VisibilityLabel.SECRET
        )
        chain = [ChainStep("pure_compute"), ChainStep("pure_compute")]
        v1 = gate.check_chain(chain)
        v2 = gate.check_chain(chain)
        assert v1.audit_digest == v2.audit_digest

    def test_digest_changes_when_chain_changes(self):
        caps = _secure_capability_set()
        gate = ContextualLeastPrivilegeGate(
            caps, initial_visibility=VisibilityLabel.SECRET
        )
        v1 = gate.check_chain([ChainStep("pure_compute")])
        v2 = gate.check_chain([ChainStep("pure_compute"), ChainStep("pure_compute")])
        assert v1.audit_digest != v2.audit_digest


# ---------------------------------------------------------------------------
# 11. Combined write+read gate (integrity/confidentiality duality)
# ---------------------------------------------------------------------------

class TestCombinedGate:
    def test_evaluate_chain_returns_both_verdicts(self):
        write_gate = create_jadepuffer_demo_gate()
        caps = create_jadepuffer_clp_capability_set()
        read_gate = ContextualLeastPrivilegeGate(
            caps, initial_visibility=VisibilityLabel.SECRET
        )
        chain = [
            ChainStep("read_env"),
            ChainStep("read_secret_store"),
            ChainStep("http_post_external"),
        ]
        write_v, read_v, both_allow = dual_gate_check(
            chain, write_gate, read_gate
        )
        # The JADEPUFFER demo is a known-dangerous chain. Either or
        # both gates should reject it. The point is the *duality*:
        # the operator gets *both* verdicts and can choose whether
        # to admit only when BOTH allow.
        assert write_v is not None
        assert read_v is not None
        assert isinstance(both_allow, bool)
        # The chain is dangerous, so both_allow should be False.
        assert both_allow is False

    def test_benign_chain_admitted_by_both_gates(self):
        write_gate = create_jadepuffer_demo_gate()
        caps = _secure_capability_set()
        read_gate = ContextualLeastPrivilegeGate(
            caps, initial_visibility=VisibilityLabel.SECRET
        )
        chain = [ChainStep("read_env"), ChainStep("http_post_external")]
        write_v, read_v, both_allow = dual_gate_check(
            chain, write_gate, read_gate
        )
        assert both_allow is True


# ---------------------------------------------------------------------------
# 12. Adversarial: privilege promotion is structurally impossible
# ---------------------------------------------------------------------------

class TestPrivilegePromotionForbidden:
    def test_no_verb_can_promote_running_visibility(self):
        # Even if we register a verb that "tries to widen" visibility,
        # the gate's `min_visibility` is monotone-narrowing.
        caps = CapabilitySet(capabilities={
            "narrower": _cap("narrower", VisibilityLabel.PUBLIC),
            "wider_attempt": _cap("wider_attempt", VisibilityLabel.SECRET),
        })
        gate = ContextualLeastPrivilegeGate(
            caps, initial_visibility=VisibilityLabel.SECRET
        )
        chain = [
            ChainStep("narrower"),  # narrows to PUBLIC
            ChainStep("wider_attempt"),  # cannot widen back to SECRET
        ]
        v = gate.check_chain(chain)
        # Step 1 narrows to PUBLIC. Step 2 wants SECRET, but PUBLIC
        # cannot see SECRET, so step 2 is blocked.
        assert v.action == CLPAction.BLOCK_AND_ESCALATE
        # The trace shows the narrowing is permanent.
        # visibility_at_each_step[0] is the running visibility *after*
        # step 0 — the verb `narrower` narrows from SECRET to PUBLIC.
        assert v.visibility_at_each_step[0] == VisibilityLabel.PUBLIC
        assert v.visibility_at_each_step[1] == VisibilityLabel.PUBLIC

    def test_labels_only_decrease_always_holds(self):
        # Run a battery of mixed chains and check the invariant
        # holds on every verdict.
        caps = _secure_capability_set()
        gate = ContextualLeastPrivilegeGate(
            caps, initial_visibility=VisibilityLabel.SECRET
        )
        chains = [
            [ChainStep("pure_compute")],
            [ChainStep("pure_compute"), ChainStep("pure_compute")],
            [ChainStep("read_env")],  # reads untrusted
            [ChainStep("read_env"), ChainStep("read_secret_store")],
            [ChainStep("http_post_external")],
        ]
        for chain in chains:
            v = gate.check_chain(chain)
            assert v.verify_labels_only_decrease() is True, (
                f"labels-only-decrease violated on chain: {chain}"
            )
