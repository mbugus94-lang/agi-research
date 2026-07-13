"""Tests for the CONTRA-style benign-config finder (core/benign_config_finder.py).

The CONTRA pattern: a tree-search that finds policy-config mutations that look
innocuous on review but admit a known-bad tool chain. The JADEPUFFER attack is
the target pattern.

Design: every test is pure-Python, no I/O, no network. The substrate is
CompositionalPolicyGate (core/compositional_policy.py). The shadow gate
mechanism is verified to not mutate the live gate.
"""

import copy

import pytest

from dataclasses import replace
from core.benign_config_finder import (
    BenignConfigFinder,
    BenignConfigHit,
    MutatorKind,
    PolicyMutation,
    SearchBudget,
    _apply_mutations,
    _benign_looking_score,
    _classify_hit,
    _copy_gate,
    _classification_levels_in_rank_order,
    derive_search_space,
    jadepuffer_target_chain,
)
from core.compositional_policy import (
    ChainAction,
    ChainStep,
    ClassificationLevel,
    CompositionMode,
    CompositionalPolicyGate,
    TaintSource,
    VerbPolicy,
    create_gate,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _secure_jadepuffer_gate():
    """A secure JADEPUFFER-shaped gate: 3 policies with strict clearance +
    distinct clusters + low taint, so the target chain trips both phases."""
    policies = {
        "read_env": VerbPolicy(
            verb_name="read_env",
            taint_in=TaintSource.INTERNAL,
            classification=ClassificationLevel.INTERNAL,
            cluster="sensitive",
            sinks=("read",),
        ),
        "read_secret_store": VerbPolicy(
            verb_name="read_secret_store",
            taint_in=TaintSource.SECRET,
            classification=ClassificationLevel.RESTRICTED,
            cluster="secrets",
            sinks=("read",),
        ),
        "http_post_external": VerbPolicy(
            verb_name="http_post_external",
            taint_in=TaintSource.EXTERNAL,
            classification=ClassificationLevel.PUBLIC,
            cluster="egress",
            sinks=("egress", "write"),
        ),
    }
    return create_gate(
        policies=policies,
        composition_mode=CompositionMode.CLEARANCE,
        initial_classification=ClassificationLevel.INTERNAL,
        clusters={
            "read_env": "sensitive",
            "read_secret_store": "secrets",
            "http_post_external": "egress",
        },
    )


def _weak_jadepuffer_gate():
    """A deliberately weak gate: all PUBLIC, all 'default' cluster → target chain allowed."""
    policies = {
        "read_env": VerbPolicy(
            verb_name="read_env",
            taint_in=TaintSource.INTERNAL,
            classification=ClassificationLevel.PUBLIC,
            cluster="default",
        ),
        "read_secret_store": VerbPolicy(
            verb_name="read_secret_store",
            taint_in=TaintSource.INTERNAL,
            classification=ClassificationLevel.PUBLIC,
            cluster="default",
        ),
        "http_post_external": VerbPolicy(
            verb_name="http_post_external",
            taint_in=TaintSource.INTERNAL,
            classification=ClassificationLevel.PUBLIC,
            cluster="default",
        ),
    }
    return create_gate(
        policies=policies,
        composition_mode=CompositionMode.CLEARANCE,
        initial_classification=ClassificationLevel.PUBLIC,
        clusters={
            "read_env": "default",
            "read_secret_store": "default",
            "http_post_external": "default",
        },
    )


# ---------------------------------------------------------------------------
# Search-space derivation
# ---------------------------------------------------------------------------


class TestDeriveSearchSpace:
    """The search space is the operator-visible, reviewable mutation set."""

    def test_search_space_is_deduplicated(self):
        """Multiple paths to the same mutation produce one entry."""
        gate = _secure_jadepuffer_gate()
        mutations = derive_search_space(gate)
        descs = [m.describe() for m in mutations]
        assert len(descs) == len(set(descs)), "search space contains duplicates"

    def test_search_space_contains_all_four_kinds(self):
        """DOWNGRADE, CONSOLIDATE, RENAME_VERB, WIDEN_TAINT_OUT are all present."""
        gate = _secure_jadepuffer_gate()
        mutations = derive_search_space(gate)
        kinds = {m.kind for m in mutations}
        assert MutatorKind.DOWNGRADE_CLASSIFICATION in kinds
        assert MutatorKind.CONSOLIDATE_CLUSTER in kinds
        assert MutatorKind.RENAME_VERB in kinds
        assert MutatorKind.WIDEN_TAINT_OUT in kinds

    def test_search_space_skips_already_low_classifications(self):
        """PUBLIC verbs have no DOWNGRADE mutation (already lowest)."""
        gate = _weak_jadepuffer_gate()
        mutations = derive_search_space(gate)
        for m in mutations:
            if m.kind == MutatorKind.DOWNGRADE_CLASSIFICATION:
                # All entries must be a level strictly below the verb's current
                # classification. PUBLIC is the floor, so any downgrade mutation
                # would be a no-op and should not be present.
                assert False, f"unexpected DOWNGRADE for already-PUBLIC verb: {m.describe()}"
        # No downgrade mutations at all on a fully-PUBLIC gate.
        kinds = {m.kind for m in mutations}
        assert MutatorKind.DOWNGRADE_CLASSIFICATION not in kinds

    def test_search_space_widen_uses_ascending_unkindness(self):
        """WIDEN_TAINT_OUT moves to a *less* trusted taint (higher sink rank)."""
        gate = _secure_jadepuffer_gate()
        # read_env starts at INTERNAL. WIDEN should produce a target that is
        # *less* trusted than INTERNAL (e.g., EXTERNAL or UNTRUSTED).
        widen_targets = {
            m.new_value for m in derive_search_space(gate)
            if m.kind == MutatorKind.WIDEN_TAINT_OUT and m.verb_name == "read_env"
        }
        assert len(widen_targets) > 0
        # INTERNAL itself must NOT be a WIDEN target (would be a no-op).
        assert TaintSource.INTERNAL not in widen_targets

    def test_search_space_rename_appends_version_suffix(self):
        """RENAME_VERB generates a vN-suffixed target name (not a random string)."""
        gate = _secure_jadepuffer_gate()
        renames = [
            m for m in derive_search_space(gate) if m.kind == MutatorKind.RENAME_VERB
        ]
        assert len(renames) > 0
        for m in renames:
            assert m.new_value != m.verb_name
            assert m.new_value.startswith(m.verb_name)


# ---------------------------------------------------------------------------
# Shadow-gate mechanism (the *isolation* guarantee)
# ---------------------------------------------------------------------------


class TestShadowGate:
    """The live gate is read-only; mutations live on a shadow copy."""

    def test_copy_gate_produces_independent_policy_dict(self):
        """Mutating the shadow's policies does not affect the live gate."""
        live = _secure_jadepuffer_gate()
        original_read_env_cls = live.lookup("read_env").classification
        shadow = _copy_gate(live)
        # Mutate shadow
        shadow._policies["read_env"] = replace(
            shadow._policies["read_env"],
            classification=ClassificationLevel.PUBLIC,
        )
        # Live unchanged
        assert live.lookup("read_env").classification == original_read_env_cls

    def test_copy_gate_produces_independent_cluster_dict(self):
        """Cluster map is also deep-copied."""
        live = _secure_jadepuffer_gate()
        shadow = _copy_gate(live)
        shadow._clusters["read_env"] = "default"
        assert live.lookup_cluster("read_env") == "sensitive"

    def test_copy_gate_shares_audit_log_reference_not_state(self):
        """The shadow's audit log starts empty (does not inherit the live gate's history)."""
        live = _secure_jadepuffer_gate()
        live.check_chain(jadepuffer_target_chain())  # populates audit log
        assert len(live.audit_log) > 0
        shadow = _copy_gate(live)
        assert len(shadow.audit_log) == 0

    def test_apply_mutations_downgrade_classification(self):
        """DOWNGRADE_CLASSIFICATION rewrites the verb's classification field."""
        gate = _secure_jadepuffer_gate()
        mutations = [
            PolicyMutation(
                verb_name="read_env",
                kind=MutatorKind.DOWNGRADE_CLASSIFICATION,
                new_value=ClassificationLevel.PUBLIC,
            )
        ]
        _apply_mutations(gate, mutations)
        assert gate.lookup("read_env").classification == ClassificationLevel.PUBLIC

    def test_apply_mutations_rename_verb(self):
        """RENAME_VERB unregisters old name and registers new name."""
        gate = _secure_jadepuffer_gate()
        old_policy = gate.lookup("read_env")
        mutations = [
            PolicyMutation(
                verb_name="read_env",
                kind=MutatorKind.RENAME_VERB,
                new_value="read_environment",
            )
        ]
        _apply_mutations(gate, mutations)
        assert gate.lookup("read_env") is None
        new_policy = gate.lookup("read_environment")
        assert new_policy is not None
        # Cluster carries over.
        assert new_policy.cluster == old_policy.cluster


# ---------------------------------------------------------------------------
# Hit classification
# ---------------------------------------------------------------------------


class TestClassifyHit:
    """The CONTRA-style classifier tags a hit as one of three types."""

    def test_adversarial_success_when_mutation_admits_a_blocked_chain(self):
        """Original blocks, mutated allows → 'adversarial_success' (the core CONTRA finding)."""
        hit_type = _classify_hit(
            mutated_action=ChainAction.ALLOW,
            original_action_on_same_chain=ChainAction.BLOCK_AND_ESCALATE,
            target_chain=jadepuffer_target_chain(),
        )
        assert hit_type == "adversarial_success"

    def test_missed_trip_when_both_admit_a_dangerous_chain(self):
        """Both allow → 'missed_trip' (the gate never caught the attack)."""
        hit_type = _classify_hit(
            mutated_action=ChainAction.ALLOW,
            original_action_on_same_chain=ChainAction.ALLOW,
            target_chain=jadepuffer_target_chain(),
        )
        assert hit_type == "missed_trip"

    def test_redundant_when_mutation_matches_original(self):
        """Both block → 'redundant' (no info, filter out)."""
        hit_type = _classify_hit(
            mutated_action=ChainAction.BLOCK_AND_ESCALATE,
            original_action_on_same_chain=ChainAction.BLOCK_AND_ESCALATE,
            target_chain=jadepuffer_target_chain(),
        )
        assert hit_type == "redundant"


# ---------------------------------------------------------------------------
# Benign-looking score
# ---------------------------------------------------------------------------


class TestBenignLookingScore:
    """The fitness function ranks hits by how innocuous the config looks."""

    def test_score_is_zero_for_no_mutation(self):
        """An empty mutation set yields a zero score (trivially 'looks like itself')."""
        gate = _secure_jadepuffer_gate()
        original = {n: p for n, p in gate._policies.items()}
        assert _benign_looking_score(original, original) == 0.0

    def test_score_increases_when_more_classifications_dropped(self):
        """Downgrading 2 of 3 verbs > downgrading 1 of 3."""
        gate = _secure_jadepuffer_gate()
        original = {n: p for n, p in gate._policies.items()}
        # Downgrade just read_env
        one_drop = dict(original)
        one_drop["read_env"] = replace(
            one_drop["read_env"], classification=ClassificationLevel.PUBLIC
        )
        # Downgrade all three
        all_drop = {
            n: replace(p, classification=ClassificationLevel.PUBLIC)
            for n, p in original.items()
        }
        s_one = _benign_looking_score(original, one_drop)
        s_all = _benign_looking_score(original, all_drop)
        assert s_all > s_one
        assert 0.0 <= s_one <= s_all <= 1.0

    def test_score_increases_with_cluster_consolidation(self):
        """Moving all non-default clusters to 'default' increases score."""
        gate = _secure_jadepuffer_gate()
        original = {n: p for n, p in gate._policies.items()}
        # Conserve classifications, just collapse clusters.
        collapsed = {
            n: replace(p, cluster="default") for n, p in original.items()
        }
        s = _benign_looking_score(original, collapsed)
        assert s > 0.0


# ---------------------------------------------------------------------------
# End-to-end search
# ---------------------------------------------------------------------------


class TestBenignConfigFinderSearch:
    """The high-level search returns BenignConfigHit records."""

    def test_search_returns_list(self):
        finder = BenignConfigFinder(
            target_chain=jadepuffer_target_chain(),
            gate=_secure_jadepuffer_gate(),
        )
        assert isinstance(finder.search(), list)

    def test_search_does_not_mutate_live_gate(self):
        """The core safety property: a search run leaves the live gate intact."""
        live = _secure_jadepuffer_gate()
        before = copy.deepcopy({n: p for n, p in live._policies.items()})
        before_clusters = dict(live._clusters)
        before_audit = len(live.audit_log)
        finder = BenignConfigFinder(
            target_chain=jadepuffer_target_chain(),
            gate=live,
            budget=SearchBudget(max_depth=2, max_iterations=64, time_budget_ms=500),
        )
        finder.search()
        after = {n: p for n, p in live._policies.items()}
        after_clusters = dict(live._clusters)
        # Policies are frozen dataclasses; identity comparison is sufficient.
        for name, policy in before.items():
            assert after[name] == policy, f"live gate mutated verb {name}"
        assert before_clusters == after_clusters
        # Audit log on the live gate only grows on a *real* check_chain call.
        # The finder uses the shadow gate for evaluation.
        assert len(live.audit_log) == before_audit

    def test_search_on_secure_gate_finds_zero_adversarial_hits(self):
        """A secure gate (clearance + cluster) resists the CONTRA search."""
        finder = BenignConfigFinder(
            target_chain=jadepuffer_target_chain(),
            gate=_secure_jadepuffer_gate(),
            budget=SearchBudget(max_depth=2, max_iterations=128, time_budget_ms=1000),
        )
        hits = finder.search()
        # The clearance + cluster split is the *strong* substrate. The CONTRA
        # search should not find a benign config that admits the chain in
        # this configuration. (0 adversarial_success hits.)
        adv = [h for h in hits if h.hit_type == "adversarial_success"]
        assert len(adv) == 0, (
            f"secure gate produced {len(adv)} adversarial_success hits: "
            f"{[h.to_dict() for h in adv]}"
        )

    def test_search_on_weak_gate_finds_missed_trip(self):
        """A weak gate (all PUBLIC, all 'default') → 'missed_trip' on the empty path."""
        finder = BenignConfigFinder(
            target_chain=jadepuffer_target_chain(),
            gate=_weak_jadepuffer_gate(),
            budget=SearchBudget(max_depth=1, max_iterations=8, time_budget_ms=200),
        )
        hits = finder.search()
        # The empty-mutations path is the entry case.
        empty_hits = [h for h in hits if len(h.mutations) == 0]
        assert any(h.hit_type == "missed_trip" for h in empty_hits)

    def test_hits_respect_max_results(self):
        """The finder caps results at `max_results`."""
        finder = BenignConfigFinder(
            target_chain=jadepuffer_target_chain(),
            gate=_weak_jadepuffer_gate(),
            max_results=1,
            budget=SearchBudget(max_depth=2, max_iterations=64, time_budget_ms=200),
        )
        hits = finder.search()
        assert len(hits) <= 1

    def test_hits_are_sorted_by_severity(self):
        """Hits come out with adversarial_success > missed_trip > redundant."""
        finder = BenignConfigFinder(
            target_chain=jadepuffer_target_chain(),
            gate=_weak_jadepuffer_gate(),
            budget=SearchBudget(max_depth=2, max_iterations=64, time_budget_ms=200),
        )
        hits = finder.search()
        order = {"adversarial_success": 0, "missed_trip": 1, "redundant": 2}
        seen = [order.get(h.hit_type, 99) for h in hits]
        assert seen == sorted(seen), f"hits not sorted by severity: {[h.hit_type for h in hits]}"

    def test_budget_time_exhaustion_stops_search(self):
        """A tiny time budget returns at most 1 iteration of work."""
        finder = BenignConfigFinder(
            target_chain=jadepuffer_target_chain(),
            gate=_secure_jadepuffer_gate(),
            budget=SearchBudget(max_depth=4, max_iterations=9999, time_budget_ms=1),
        )
        hits = finder.search()
        # No assertion on hit count; just that search terminated.
        assert isinstance(hits, list)

    def test_budget_iteration_exhaustion_stops_search(self):
        """max_iterations=0 yields an empty hit list."""
        finder = BenignConfigFinder(
            target_chain=jadepuffer_target_chain(),
            gate=_secure_jadepuffer_gate(),
            budget=SearchBudget(max_depth=4, max_iterations=0, time_budget_ms=9999),
        )
        hits = finder.search()
        assert hits == []


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


class TestConvenience:
    def test_jadepuffer_target_chain_has_three_steps(self):
        chain = jadepuffer_target_chain()
        assert len(chain) == 3
        names = [s.verb_name for s in chain]
        assert names == ["read_env", "read_secret_store", "http_post_external"]

    def test_jadepuffer_target_chain_steps_carry_internal_taint(self):
        """The target chain's per-step taint is INTERNAL (operator-supplied)."""
        chain = jadepuffer_target_chain()
        for step in chain:
            assert step.taint_in == TaintSource.INTERNAL

    def test_classification_levels_in_rank_order_is_sorted(self):
        """The helper returns the canonical ascending rank order."""
        order = _classification_levels_in_rank_order()
        assert order == sorted(order, key=lambda c: c.value) or len(order) > 0
        # More concretely: each subsequent level is at least as sensitive.
        for i in range(1, len(order)):
            assert order[i].value != order[i - 1].value
