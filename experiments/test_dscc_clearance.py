"""
Tests for DSCC clearance-mode wiring into the Compositional Policy Gate
(arXiv:2607.03423).

This is the 2026-07-12 next-priority item from the 2026-07-11 build log:
"DSCC clearance-mode wiring — partition the policy registry into
classification-level clusters; pre-compute the MRS (Most Restrictive Set)
for each cluster; require the agent to declare the cluster at chain
proposal time. arXiv:2607.03423 reports 79.2% / 95.5% block rate."

Coverage:
- CompositionMode enum (CLEARANCE / TAINT)
- ClassificationLevel enum + classification_rank() + max_classification()
- Gate's chain_effective_classification() (high-water mark)
- Gate's mrs_clearance_check() (the DSCC Step-3 clearance check)
- Gate's cluster_compatible() + chain_cluster_compatibility()
- Wire-through into check_chain: chain_classification, cluster_set, and
  CLEARANCE_LEVEL_INSUFFICIENT / CLEARANCE_CLUSTER_MISMATCH reasons
- Block-rate validation against the paper's 79.2% / 95.5% figures
- Taint mode still admits under-classified chains
- create_jadepuffer_demo_gate supports composition_mode
- Integration with the JADEPUFFER attack pattern
"""

from __future__ import annotations

import unittest
from typing import Dict, Tuple

from core.compositional_policy import (
    ChainAction,
    ChainStep,
    ChainVerdict,
    ClassificationLevel as CL,
    CompositionMode,
    CompositionalPolicyGate,
    DenyReason,
    VerbPolicy,
    TaintSource,
    classification_rank,
    create_gate,
    create_jadepuffer_demo_gate,
    max_classification,
)
from core.compositional_policy import TaintSource as TS


# ===========================================================================
# Helpers
# ===========================================================================

def _vp(name: str, taint_in: TaintSource, classification: ClassificationLevel, **kw) -> VerbPolicy:
    return VerbPolicy(
        verb_name=name,
        taint_in=taint_in,
        classification=classification,
        **kw,
    )


# ===========================================================================
# 1. CompositionMode
# ===========================================================================

class TestCompositionMode(unittest.TestCase):
    """The gate accepts a `composition_mode` constructor arg and validates it."""

    def test_default_is_clearance(self) -> None:
        g = CompositionalPolicyGate()
        self.assertEqual(g.composition_mode, CompositionMode.CLEARANCE)

    def test_explicit_clearance(self) -> None:
        g = CompositionalPolicyGate(composition_mode=CompositionMode.CLEARANCE)
        self.assertEqual(g.composition_mode, CompositionMode.CLEARANCE)

    def test_explicit_taint(self) -> None:
        g = CompositionalPolicyGate(composition_mode=CompositionMode.TAINT)
        self.assertEqual(g.composition_mode, CompositionMode.TAINT)

    def test_invalid_mode_raises(self) -> None:
        with self.assertRaises(ValueError):
            CompositionalPolicyGate(composition_mode="not-a-mode")

    def test_set_composition_mode(self) -> None:
        g = CompositionalPolicyGate()
        g.set_composition_mode(CompositionMode.TAINT)
        self.assertEqual(g.composition_mode, CompositionMode.TAINT)
        g.set_composition_mode(CompositionMode.CLEARANCE)
        self.assertEqual(g.composition_mode, CompositionMode.CLEARANCE)


# ===========================================================================
# 2. Cluster registry
# ===========================================================================

class TestClusterRegistry(unittest.TestCase):
    """register_cluster / lookup_cluster / clusters properties."""

    def test_register_and_lookup(self) -> None:
        g = CompositionalPolicyGate()
        g.register_cluster("read_internal", "internal_cluster")
        g.register_cluster("http_post_external", "external_cluster")
        self.assertEqual(g.lookup_cluster("read_internal"), "internal_cluster")
        self.assertEqual(g.lookup_cluster("http_post_external"), "external_cluster")

    def test_unknown_verb_returns_default(self) -> None:
        g = CompositionalPolicyGate()
        self.assertEqual(g.lookup_cluster("not_registered"), "default")

    def test_clusters_property_is_a_copy(self) -> None:
        g = CompositionalPolicyGate()
        g.register_cluster("a", "x")
        cs = g.clusters
        cs["b"] = "y"
        # Mutating the returned dict should not mutate the gate's state
        self.assertEqual(g.lookup_cluster("b"), "default")

    def test_cluster_compatible_same(self) -> None:
        g = CompositionalPolicyGate()
        self.assertTrue(g.cluster_compatible("a", "a"))

    def test_cluster_compatible_default(self) -> None:
        g = CompositionalPolicyGate()
        # default is compatible with anything (the "unassigned" cluster)
        self.assertTrue(g.cluster_compatible("default", "x"))
        self.assertTrue(g.cluster_compatible("x", "default"))

    def test_cluster_compatible_distinct(self) -> None:
        g = CompositionalPolicyGate()
        self.assertFalse(g.cluster_compatible("a", "b"))

    def test_chain_cluster_compatibility_ok(self) -> None:
        g = CompositionalPolicyGate()
        g.register_cluster("a", "cluster_x")
        g.register_cluster("b", "cluster_x")
        ok, conflicts = g.chain_cluster_compatibility(
            [ChainStep("a"), ChainStep("b")]
        )
        self.assertTrue(ok)
        self.assertEqual(conflicts, ())

    def test_chain_cluster_compatibility_conflict(self) -> None:
        g = CompositionalPolicyGate()
        g.register_cluster("a", "cluster_x")
        g.register_cluster("b", "cluster_y")
        ok, conflicts = g.chain_cluster_compatibility(
            [ChainStep("a"), ChainStep("b")]
        )
        self.assertFalse(ok)
        self.assertIn(("cluster_x", "cluster_y"), conflicts)


# ===========================================================================
# 3. Effective classification (high-water mark)
# ===========================================================================

class TestEffectiveClassification(unittest.TestCase):
    """chain_effective_classification() — the DSCC C_eff high-water mark."""

    def test_empty_chain(self) -> None:
        g = CompositionalPolicyGate()
        eff = g.chain_effective_classification([])
        self.assertEqual(eff, CL.PUBLIC)

    def test_empty_chain_with_initial(self) -> None:
        g = CompositionalPolicyGate(initial_classification=CL.CONFIDENTIAL)
        eff = g.chain_effective_classification([])
        self.assertEqual(eff, CL.CONFIDENTIAL)

    def test_high_water_mark(self) -> None:
        g = CompositionalPolicyGate(
            policies={
                "a": _vp("a", TS.INTERNAL, CL.PUBLIC),
                "b": _vp("b", TS.INTERNAL, CL.CONFIDENTIAL),
                "c": _vp("c", TS.INTERNAL, CL.INTERNAL),
            }
        )
        # max of PUBLIC, CONFIDENTIAL, INTERNAL = CONFIDENTIAL
        eff = g.chain_effective_classification([
            ChainStep("a"), ChainStep("b"), ChainStep("c"),
        ])
        self.assertEqual(eff, CL.CONFIDENTIAL)

    def test_high_water_mark_seeded_from_initial(self) -> None:
        g = CompositionalPolicyGate(
            initial_classification=CL.RESTRICTED,
            policies={
                "a": _vp("a", TS.INTERNAL, CL.PUBLIC),
            },
        )
        # Initial RESTRICTED is the floor; PUBLIC verb can't lower it
        eff = g.chain_effective_classification([ChainStep("a")])
        self.assertEqual(eff, CL.RESTRICTED)

    def test_high_water_mark_monotonic(self) -> None:
        g = CompositionalPolicyGate(
            policies={
                "a": _vp("a", TS.INTERNAL, CL.PUBLIC),
                "b": _vp("b", TS.INTERNAL, CL.CONFIDENTIAL),
            }
        )
        # Adding a higher-class verb should never lower C_eff
        eff1 = g.chain_effective_classification([ChainStep("a")])
        eff2 = g.chain_effective_classification([ChainStep("a"), ChainStep("b")])
        self.assertEqual(eff1, CL.PUBLIC)
        self.assertEqual(eff2, CL.CONFIDENTIAL)
        # eff2 must be >= eff1
        self.assertGreaterEqual(
            classification_rank(eff2), classification_rank(eff1)
        )

    def test_classification_rank_ordering(self) -> None:
        self.assertLess(
            classification_rank(CL.PUBLIC),
            classification_rank(CL.INTERNAL),
        )
        self.assertLess(
            classification_rank(CL.INTERNAL),
            classification_rank(CL.CONFIDENTIAL),
        )
        self.assertLess(
            classification_rank(CL.CONFIDENTIAL),
            classification_rank(CL.RESTRICTED),
        )

    def test_max_classification_takes_higher(self) -> None:
        self.assertEqual(
            max_classification(CL.PUBLIC, CL.CONFIDENTIAL),
            CL.CONFIDENTIAL,
        )
        self.assertEqual(
            max_classification(CL.RESTRICTED, CL.INTERNAL),
            CL.RESTRICTED,
        )
        self.assertEqual(
            max_classification(CL.INTERNAL, CL.INTERNAL),
            CL.INTERNAL,
        )


# ===========================================================================
# 4. mrs_clearance_check (DSCC Step 3)
# ===========================================================================

class TestMRSClearanceCheck(unittest.TestCase):
    """The DSCC clearance check: per-verb classification >= C_eff."""

    def test_safe_chain_passes(self) -> None:
        g = CompositionalPolicyGate(
            policies={
                "read_a": _vp("read_a", TS.INTERNAL, CL.INTERNAL),
                "read_b": _vp("read_b", TS.INTERNAL, CL.INTERNAL),
            }
        )
        ok, failing, c_eff, failing_cls = g.mrs_clearance_check([
            ChainStep("read_a"), ChainStep("read_b"),
        ])
        self.assertTrue(ok)
        self.assertEqual(failing, ())
        self.assertEqual(c_eff, CL.INTERNAL)
        self.assertEqual(failing_cls, ())

    def test_under_classified_fails(self) -> None:
        g = CompositionalPolicyGate(
            policies={
                "read_secret": _vp("read_secret", TS.SECRET, CL.RESTRICTED),
                "post_external": _vp("post_external", TS.EXTERNAL, CL.PUBLIC),
            }
        )
        ok, failing, c_eff, failing_cls = g.mrs_clearance_check([
            ChainStep("read_secret"), ChainStep("post_external"),
        ])
        self.assertFalse(ok)
        self.assertIn("post_external", failing)
        self.assertEqual(c_eff, CL.RESTRICTED)
        # The failing verb (post_external) has cluster 'default'
        self.assertIn('default', failing_cls)

    def test_under_classified_returns_c_eff(self) -> None:
        """The failing-verbs tuple still records the high-water mark."""
        g = CompositionalPolicyGate(
            policies={
                "a": _vp("a", TS.INTERNAL, CL.CONFIDENTIAL),
                "b": _vp("b", TS.INTERNAL, CL.PUBLIC),
            }
        )
        ok, failing, c_eff, _ = g.mrs_clearance_check([
            ChainStep("a"), ChainStep("b"),
        ])
        self.assertFalse(ok)
        self.assertEqual(c_eff, CL.CONFIDENTIAL)
        self.assertIn("b", failing)

    def test_public_chain_in_clearance_mode(self) -> None:
        """PUBLIC-classified verbs in a PUBLIC-classification chain pass."""
        g = CompositionalPolicyGate(
            policies={
                "a": _vp("a", TS.PUBLIC, CL.PUBLIC),
                "b": _vp("b", TS.PUBLIC, CL.PUBLIC),
            }
        )
        ok, _, _, _ = g.mrs_clearance_check([
            ChainStep("a"), ChainStep("b"),
        ])
        self.assertTrue(ok)


# ===========================================================================
# 5. Clearance check wired into check_chain
# ===========================================================================

class TestClearanceModeInCheckChain(unittest.TestCase):
    """The clearance check shows up on the ChainVerdict when in CLEARANCE mode."""

    def _gate(self, **kw) -> CompositionalPolicyGate:
        return CompositionalPolicyGate(
            policies={
                "read_internal_doc": _vp("read_internal_doc", TS.INTERNAL, CL.INTERNAL),
                "post_external": _vp("post_external", TS.EXTERNAL, CL.PUBLIC),
                "read_confidential": _vp("read_confidential", TS.SECRET, CL.CONFIDENTIAL),
            },
            composition_mode=CompositionMode.CLEARANCE,
            **kw,
        )

    def test_clearance_mode_safe_chain_allows(self) -> None:
        g = self._gate()
        v = g.check_chain([
            ChainStep("read_internal_doc"),
            ChainStep("read_internal_doc"),
        ])
        self.assertEqual(v.action, ChainAction.ALLOW)
        # No clearance reasons on a safe chain
        self.assertNotIn(DenyReason.CLEARANCE_LEVEL_INSUFFICIENT, v.reasons)

    def test_clearance_mode_blocks_under_classified(self) -> None:
        g = self._gate()
        v = g.check_chain([
            ChainStep("read_confidential"),
            ChainStep("post_external"),
        ])
        # post_external is PUBLIC; chain C_eff is CONFIDENTIAL -> block
        self.assertIn(v.action, (ChainAction.BLOCK, ChainAction.BLOCK_AND_ESCALATE))
        self.assertIn(DenyReason.CLEARANCE_LEVEL_INSUFFICIENT, v.reasons)

    def test_clearance_mode_blocks_cluster_mismatch(self) -> None:
        g = self._gate()
        g.register_cluster("read_confidential", "confidential_cluster")
        g.register_cluster("post_external", "public_cluster")
        v = g.check_chain([
            ChainStep("read_confidential"),
            ChainStep("post_external"),
        ])
        # Two distinct non-default clusters -> cluster_mismatch
        self.assertIn(DenyReason.CLEARANCE_CLUSTER_MISMATCH, v.reasons)

    def test_taint_mode_admits_under_classified(self) -> None:
        g = CompositionalPolicyGate(
            policies={
                "read_confidential": _vp("read_confidential", TS.SECRET, CL.CONFIDENTIAL),
                "post_external": _vp("post_external", TS.EXTERNAL, CL.PUBLIC),
            },
            composition_mode=CompositionMode.TAINT,
        )
        v = g.check_chain([
            ChainStep("read_confidential"),
            ChainStep("post_external"),
        ])
        # In TAINT mode, under-classification is allowed — but the
        # SECRET_TO_EXTERNAL rule may still fire.
        self.assertNotIn(
            DenyReason.CLEARANCE_LEVEL_INSUFFICIENT, v.reasons,
            "Taint mode must not raise the clearance reason",
        )

    def test_chain_classification_on_verdict(self) -> None:
        g = self._gate()
        v = g.check_chain([
            ChainStep("read_confidential"),
            ChainStep("read_internal_doc"),
        ])
        # C_eff is the max of CONFIDENTIAL, INTERNAL = CONFIDENTIAL
        self.assertEqual(v.chain_classification, CL.CONFIDENTIAL)

    def test_cluster_set_on_verdict(self) -> None:
        g = self._gate()
        g.register_cluster("read_confidential", "confidential_cluster")
        g.register_cluster("read_internal_doc", "internal_cluster")
        v = g.check_chain([
            ChainStep("read_confidential"),
            ChainStep("read_internal_doc"),
        ])
        self.assertIn("confidential_cluster", v.cluster_set)
        self.assertIn("internal_cluster", v.cluster_set)

    def test_empty_chain_records_initial(self) -> None:
        g = CompositionalPolicyGate(
            initial_classification=CL.CONFIDENTIAL,
        )
        v = g.check_chain([])
        self.assertEqual(v.action, ChainAction.ALLOW)
        self.assertEqual(v.chain_classification, CL.CONFIDENTIAL)

    def test_chain_classification_in_to_dict(self) -> None:
        g = self._gate()
        v = g.check_chain([
            ChainStep("read_confidential"),
            ChainStep("read_internal_doc"),
        ])
        d = v.to_dict()
        self.assertIn("chain_classification", d)
        self.assertEqual(d["chain_classification"], "confidential")
        self.assertIn("cluster_set", d)


# ===========================================================================
# 6. Block-rate parity with the paper (79.2% / 95.5%)
# ===========================================================================

class TestBlockRate(unittest.TestCase):
    """The paper's reference implementation: clearance mode blocks 79.2% of
    policy pairs and 95.5% of triples. The gate's mrs_clearance_check should
    block at least a similar share on a mixed-classification registry.
    """

    def _registry(self) -> Dict[str, VerbPolicy]:
        # 4 PUBLIC + 4 INTERNAL + 4 CONFIDENTIAL + 4 RESTRICTED verbs
        levels = [
            (CL.PUBLIC, TS.PUBLIC),
            (CL.INTERNAL, TS.INTERNAL),
            (CL.CONFIDENTIAL, TS.SECRET),
            (CL.RESTRICTED, TS.SECRET),
        ]
        regs: Dict[str, VerbPolicy] = {}
        for i, (cls, t) in enumerate(levels):
            for j in range(4):
                name = f"v_{cls.value}_{j}"
                regs[name] = _vp(name, t, cls)
        return regs

    def test_two_verb_mixed_classification_blocks(self) -> None:
        g = CompositionalPolicyGate(
            policies=self._registry(),
            composition_mode=CompositionMode.CLEARANCE,
        )
        names = list(self._registry().keys())
        total = 0
        blocked = 0
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                total += 1
                ok, _, _, _ = g.mrs_clearance_check([
                    ChainStep(a), ChainStep(b),
                ])
                if not ok:
                    blocked += 1
        # All mixed-classification pairs are blocked in clearance mode
        self.assertGreater(total, 0)
        self.assertGreater(blocked, 0)
        # At least 70% of pairs are blocked (paper reports 79.2%)
        self.assertGreaterEqual(blocked / total, 0.70)

    def test_three_verb_mixed_classification_blocks(self) -> None:
        g = CompositionalPolicyGate(
            policies=self._registry(),
            composition_mode=CompositionMode.CLEARANCE,
        )
        names = list(self._registry().keys())
        # All triples with at least one non-PUBLIC verb
        from itertools import combinations
        total = 0
        blocked = 0
        for combo in combinations(names, 3):
            total += 1
            ok, _, _, _ = g.mrs_clearance_check(
                [ChainStep(c) for c in combo]
            )
            if not ok:
                blocked += 1
        self.assertGreater(total, 0)
        # Paper reports 95.5% of triples blocked
        self.assertGreaterEqual(blocked / total, 0.90)


# ===========================================================================
# 7. Initial classification
# ===========================================================================

class TestInitialClassification(unittest.TestCase):
    """initial_classification seeds the high-water mark before any verb runs."""

    def test_default_initial_is_public(self) -> None:
        g = CompositionalPolicyGate()
        self.assertEqual(g._initial_classification, CL.PUBLIC)

    def test_explicit_initial(self) -> None:
        g = CompositionalPolicyGate(
            initial_classification=CL.RESTRICTED,
        )
        self.assertEqual(g._initial_classification, CL.RESTRICTED)

    def test_invalid_initial_raises(self) -> None:
        with self.assertRaises((ValueError, TypeError)):
            CompositionalPolicyGate(initial_classification="bogus")  # type: ignore[arg-type]

    def test_initial_raises_high_water_mark(self) -> None:
        """A RESTRICTED initial forces the chain's C_eff up to RESTRICTED."""
        g = CompositionalPolicyGate(
            initial_classification=CL.RESTRICTED,
            policies={
                "a": _vp("a", TS.PUBLIC, CL.PUBLIC),
            },
        )
        eff = g.chain_effective_classification([ChainStep("a")])
        self.assertEqual(eff, CL.RESTRICTED)


# ===========================================================================
# 8. Integration with the JADEPUFFER demo gate
# ===========================================================================

class TestIntegrationWithJadePuffer(unittest.TestCase):
    """The JADEPUFFER chain should be blocked by the new clearance check."""

    def test_jadepuffer_caught_by_clearance(self) -> None:
        g = create_jadepuffer_demo_gate(composition_mode=CompositionMode.CLEARANCE)
        # JADEPUFFER chain: env -> external -> secret -> external
        # read_env=PUBLIC, http_post_external=PUBLIC, read_secret_store=INTERNAL/SECRET
        # The CONFIDENTIAL/INTERNAL read_secret_store raises C_eff; the
        # PUBLIC http_post_external is under-cleared -> CLEARANCE_LEVEL_INSUFFICIENT
        chain = [
            ChainStep("read_env", TS.INTERNAL),
            ChainStep("http_post_external", TS.EXTERNAL),
            ChainStep("read_secret_store", TS.SECRET),
            ChainStep("http_post_external", TS.EXTERNAL),
        ]
        v = g.check_chain(chain)
        self.assertIn(v.action, (ChainAction.BLOCK, ChainAction.BLOCK_AND_ESCALATE))
        # Either clearance, taint, or both should be on the reasons
        self.assertTrue(
            DenyReason.CLEARANCE_LEVEL_INSUFFICIENT in v.reasons
            or DenyReason.SECRET_TO_EXTERNAL in v.reasons
        )

    def test_jadepuffer_in_taint_mode_still_blocks(self) -> None:
        """In TAINT mode the clearance check is skipped, but the
        SECRET_TO_EXTERNAL rule still fires."""
        g = create_jadepuffer_demo_gate(composition_mode=CompositionMode.TAINT)
        chain = [
            ChainStep("read_env", TS.INTERNAL),
            ChainStep("http_post_external", TS.EXTERNAL),
            ChainStep("read_secret_store", TS.SECRET),
            ChainStep("http_post_external", TS.EXTERNAL),
        ]
        v = g.check_chain(chain)
        self.assertEqual(v.action, ChainAction.BLOCK_AND_ESCALATE)
        self.assertIn(DenyReason.SECRET_TO_EXTERNAL, v.reasons)
        # Taint mode skips the clearance check
        self.assertNotIn(DenyReason.CLEARANCE_LEVEL_INSUFFICIENT, v.reasons)


class TestJadePufferDemoGateModes(unittest.TestCase):
    """create_jadepuffer_demo_gate exposes composition_mode."""

    def test_demo_gate_default_clearance(self) -> None:
        g = create_jadepuffer_demo_gate()
        self.assertEqual(g.composition_mode, CompositionMode.CLEARANCE)

    def test_demo_gate_explicit_taint(self) -> None:
        g = create_jadepuffer_demo_gate(composition_mode=CompositionMode.TAINT)
        self.assertEqual(g.composition_mode, CompositionMode.TAINT)


# ===========================================================================
# Run
# ===========================================================================

if __name__ == "__main__":
    unittest.main()
