"""
CONTRA-style benign-config finder (arXiv:2607.03423 §5 evaluation angle).

The compositional policy gate is a *classifier* — given a chain and a
policy registry, it returns ALLOW / BLOCK. CONTRA is the *adversarial
search problem* in the other direction: given a target chain
("JADEPUFFER-style exfiltration: read secret store, then post
externally"), find a *benign-looking* policy configuration that
admits the chain.

The intuition: an operator with a 1000-tool policy registry cannot
eyeball every (classification, cluster) assignment. A sub-1% misconfig
rate is 10 misconfigured tools. CONTRA finds those misconfigurations
by treating the policy registry as a *search space* and the gate's
verdict as the *fitness function*.

This is the same class of problem as the paper's red-team search:
benign-looking but functionally dangerous. The CONTRA name comes
from the "contrary" intuition — a config that looks safe on review
is *contrary* to its actual behavioral class.

Design (per the 2026-07-12 carryover in BUILD_LOG_2026-07-12.md):

  * `BenignConfigFinder` holds:
      - the *target chain* (JADEPUFFER pattern by default)
      - the *original gate* with its current policy registry
      - the *search space* (which knobs to mutate, with bounds)
      - the *fitness function* (verdict on target chain + benign-looking metric)
  * `search()` runs a bounded tree search. Default BFS-with-pruning,
    depth-bounded by the search-space dimensionality.
  * Returns a list of `BenignConfigHit` records:
      - the mutated policy snapshot
      - the chain verdict on the target chain (BLOCK_AND_ESCALATE / ALLOW / etc.)
      - the *benign-looking* score (lower = more innocuous on review)
      - the *hit_type* classification:
          * "adversarial_success" — chain admitted, but the *runtime taint* would have tripped
            (i.e. the chain is admitted by clearance but a runtime check would catch it)
          * "true_negative" — chain admitted AND the chain is actually safe under the
            original registry's runtime substrate
          * "missed_trip" — chain admitted AND the chain is *actually dangerous* under
            every substrate (the worst case: a real attack slipped through)
  * The benign-looking metric is a small heuristic over the
    diff between original and mutated policies:
      - many tools re-classified to *lower* sensitivity → looks innocuous
      - many tools put in the same "default" cluster → looks like a clean config
      - few tools changed in absolute terms → looks like a minor edit
  * Search is bounded: max_depth, max_iterations, time_budget_ms.

The module is *read-only* w.r.t. the live gate. The mutated policies
are constructed on a *shadow gate* (a copy of the live gate's policy
registry) — the original registry is never mutated. This matches
the substrate's "no auto-acts" principle (the original
compositional_policy.py docstring: "this module *classifies*; the
caller decides whether to allow, block, or escalate"). The finder's
hits are *review items* for a human operator, not auto-applied
configurations.

Safety: the substrate's SAFETY.md states that self-modifications
require REVIEW, never auto-apply. This module is no exception — it
emits *candidates* for review, never applies them. The CLI in
`cli/benign_config_search.py` is the only interface that emits the
review queue entries; the core module here only produces
candidates.

References:
  * arXiv:2607.03423 — DSCC: Dynamic Security Control Compositor
    (Phase 2 red-team evaluation, §5.2).
  * 2026-07-12 BUILD_LOG carryover: "CONTRA-style benign-config
    finder — a tree-search that searches the policy space for
    benign-looking configs that produce dangerous chains."
  * CONTRA name coinage: "contrary config" — looks innocuous on
    review, contrary to its behavioral class.
"""
from __future__ import annotations

import copy
import hashlib
import json
import time
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from core.compositional_policy import (
    ChainAction,
    ChainStep,
    ChainVerdict,
    ClassificationLevel,
    CompositionMode,
    CompositionalPolicyGate,
    DenyReason,
    TaintSource,
    VerbPolicy,
    classification_rank,
    taint_rank,
)


# ===========================================================================
# Search-space primitives
# ===========================================================================

class MutatorKind(str, Enum):
    """The kinds of mutations the finder considers.

    The model: every mutation is *individually* a small,
    reviewable-looking change. The *combination* of mutations is
    what produces the dangerous chain. This is the CONTRA pattern
    (arXiv:2606.19390 §3.2, "benign-looking config" search).
    """
    DOWNGRADE_CLASSIFICATION = "downgrade_classification"
    """Lower a verb's classification by one rank."""
    RENAME_VERB = "rename_verb"
    """Rename a verb. The search registers a NEW verb whose policy
    matches an *existing* verb, creating a duplicate-effective
    policy under a different name. The clearance check matches on
    the verb *name*, not the policy, so a renamed policy bypasses
    any policy-name-specific denylist."""
    CONSOLIDATE_CLUSTER = "consolidate_cluster"
    """Move a verb to the "default" (most permissive) cluster."""
    CLEAR_MAX_INPUT_CLASSIFICATION = "clear_max_input_classification"
    """Remove a verb's max_input_classification cap, allowing
    lower-classification data to flow in."""
    WIDEN_TAINT_OUT = "widen_taint_out"
    """Reclassify a verb's taint_in to a higher (less-trusted)
    source — makes the verb look like a *reading* verb to a
    reviewer (it now outputs higher taint) but increases the
    chain's effective taint when composed with downstream
    verbs."""


@dataclass(frozen=True)
class PolicyMutation:
    """A single mutation to apply to a copy of the policy registry.

    `verb_name` identifies the target verb. `kind` identifies the
    mutation type. `new_value` carries the new value (level index
    for DOWNGRADE_CLASSIFICATION, cluster name for
    CONSOLIDATE_CLUSTER, etc.). The mutation is immutable so a
    search path is a hashable tuple of mutations.
    """
    verb_name: str
    kind: MutatorKind
    new_value: Any = None

    def describe(self) -> str:
        return f"{self.verb_name}:{self.kind.value}:{self.new_value}"

    def digest(self) -> str:
        return hashlib.sha256(self.describe().encode("utf-8")).hexdigest()[:16]


@dataclass
class SearchBudget:
    """Bounds the finder's search so a misconfigured policy registry cannot
    turn the search into an unbounded tree walk."""
    max_iterations: int = 256
    """Total number of (mutation, evaluation) pairs to attempt."""
    max_depth: int = 4
    """Maximum number of mutations in a single candidate path."""
    time_budget_ms: int = 5_000
    """Wall-clock cap. The search stops at the next iteration boundary."""
    max_results: int = 16
    """Stop emitting hits after this many are found."""

    def is_exhausted(
        self, *, iterations: int, started_at: float
    ) -> bool:
        if iterations >= self.max_iterations:
            return True
        if (time.time() - started_at) * 1000.0 >= self.time_budget_ms:
            return True
        return False


# ===========================================================================
# Search-space derivation
# ===========================================================================

def _classification_levels_in_rank_order() -> List[ClassificationLevel]:
    """Return the classification levels in *ascending* rank order
    (PUBLIC < INTERNAL < RESTRICTED < CRITICAL). The search uses
    this to *downgrade* classifications one step at a time."""
    pairs = [
        (c, classification_rank(c))
        for c in ClassificationLevel
    ]
    pairs.sort(key=lambda p: p[1])
    return [c for c, _ in pairs]


def derive_search_space(
    gate: CompositionalPolicyGate,
) -> List[PolicyMutation]:
    """Derive the *initial* search space from the live gate's policy
    registry.

    The space is bounded and reviewable:
      - One DOWNGRADE_CLASSIFICATION mutation per verb (the verb's
        classification - 1 rank). The benign-looking candidate
        *lowers* a tool's sensitivity.
      - One CONSOLIDATE_CLUSTER mutation per verb that is *not*
        already in the "default" cluster — moves the verb to
        "default" (the most permissive cluster).
      - One CLEAR_MAX_INPUT_CLASSIFICATION mutation per verb that
        *has* a `max_input_classification` cap.

    This is the *initial* space. The search is BFS-over-mutations
    so every candidate is a tuple of up to `max_depth` mutations
    from this set. The set is intentionally *small* (O(N) where N
    is the registry size, not O(N^2)) so the search is reviewable.
    """
    mutations: List[PolicyMutation] = []
    levels = _classification_levels_in_rank_order()
    seen_descs: set = set()

    for verb_name, policy in gate._policies.items():
        # 1. Downgrade classification (one step down).
        current_rank = classification_rank(policy.classification)
        if current_rank > 0:
            new_level = levels[current_rank - 1]
            m = PolicyMutation(
                verb_name=verb_name,
                kind=MutatorKind.DOWNGRADE_CLASSIFICATION,
                new_value=new_level,
            )
            if m.describe() not in seen_descs:
                mutations.append(m)
                seen_descs.add(m.describe())

        # 2. Consolidate cluster to "default" (if not already).
        if policy.cluster != "default":
            m = PolicyMutation(
                verb_name=verb_name,
                kind=MutatorKind.CONSOLIDATE_CLUSTER,
                new_value="default",
            )
            if m.describe() not in seen_descs:
                mutations.append(m)
                seen_descs.add(m.describe())

        # 3. Clear max_input_classification (if set).
        if policy.max_input_classification is not None:
            m = PolicyMutation(
                verb_name=verb_name,
                kind=MutatorKind.CLEAR_MAX_INPUT_CLASSIFICATION,
                new_value=None,
            )
            if m.describe() not in seen_descs:
                mutations.append(m)
                seen_descs.add(m.describe())

        # 4. Rename verb. Each policy is duplicated under a benign
        # name (the "_v2" suffix). The clearance check matches on
        # the verb *name*, so a renamed policy bypasses any
        # policy-name-specific denylist and the renamed verb is
        # *not* recognized as the same policy by a human reviewer
        # of the registry.
        m = PolicyMutation(
            verb_name=verb_name,
            kind=MutatorKind.RENAME_VERB,
            new_value=f"{verb_name}_v2",
        )
        if m.describe() not in seen_descs:
            mutations.append(m)
            seen_descs.add(m.describe())

        # 5. Widen taint_out to a higher-taint source. A widened
        # taint propagates to downstream steps in the chain; the
        # *chain* becomes dangerous, but the *policy* looks like
        # it just "reads more data" (a benign-looking upgrade).
        current_taint = policy.taint_in
        current_taint_rank = taint_rank(current_taint)
        # Walk to the *next* less-trusted taint source.
        less_trusted = None
        for candidate in (
            TaintSource.EXTERNAL,
            TaintSource.UNTRUSTED,
            TaintSource.SECRET,
        ):
            if taint_rank(candidate) > current_taint_rank:
                less_trusted = candidate
                break
        if less_trusted is not None:
            m = PolicyMutation(
                verb_name=verb_name,
                kind=MutatorKind.WIDEN_TAINT_OUT,
                new_value=less_trusted,
            )
            if m.describe() not in seen_descs:
                mutations.append(m)
                seen_descs.add(m.describe())

    return mutations


# ===========================================================================
# Shadow-gate construction
# ===========================================================================

def _copy_gate(gate: CompositionalPolicyGate) -> CompositionalPolicyGate:
    """Deep-copy a gate so mutations on the shadow don't leak.

    The shadow gets its own `_policies` dict (deep-copied VerbPolicy
    values) and its own `_clusters` dict. The shadow's audit log
    starts empty — the finder's evaluations should not appear in
    the live gate's audit log.
    """
    shadow = CompositionalPolicyGate.__new__(CompositionalPolicyGate)
    # Copy every attribute that participates in policy evaluation.
    # Unknown attribute set; fall back to __dict__ if needed.
    base = gate.__dict__
    shadow.__dict__.update(copy.deepcopy(base))
    shadow._policies = {
        name: copy.deepcopy(p)
        for name, p in gate._policies.items()
    }
    shadow._clusters = dict(gate._clusters)
    shadow._audit = []
    shadow._last_chain_digest = ""
    return shadow


def _apply_mutations(
    shadow: CompositionalPolicyGate,
    mutations: Sequence[PolicyMutation],
) -> None:
    """Apply a sequence of mutations to the shadow gate.

    VerbPolicy is a frozen dataclass, so we unregister + re-register
    to replace a policy. The audit log and clusters are mutated
    in-place.
    """
    for m in mutations:
        policy = shadow._policies.get(m.verb_name)
        if policy is None:
            continue
        if m.kind == MutatorKind.DOWNGRADE_CLASSIFICATION:
            new_policy = replace(policy, classification=m.new_value)
            shadow._policies[m.verb_name] = new_policy
        elif m.kind == MutatorKind.CONSOLIDATE_CLUSTER:
            new_policy = replace(policy, cluster=m.new_value)
            shadow._policies[m.verb_name] = new_policy
            shadow._clusters[m.verb_name] = m.new_value
        elif m.kind == MutatorKind.CLEAR_MAX_INPUT_CLASSIFICATION:
            new_policy = replace(policy, max_input_classification=None)
            shadow._policies[m.verb_name] = new_policy
        elif m.kind == MutatorKind.RENAME_VERB:
            # Unregister old name, register under new name. The new
            # policy is the old one with verb_name changed; we drop
            # the old name from clusters.
            new_policy = replace(policy, verb_name=m.new_value)
            shadow._policies.pop(m.verb_name, None)
            shadow._policies[m.new_value] = new_policy
            old_cluster = shadow._clusters.pop(m.verb_name, None)
            if old_cluster is not None:
                shadow._clusters[m.new_value] = old_cluster
        elif m.kind == MutatorKind.WIDEN_TAINT_OUT:
            new_policy = replace(policy, taint_in=m.new_value)
            shadow._policies[m.verb_name] = new_policy


# ===========================================================================
# Fitness function
# ===========================================================================

@dataclass
class BenignConfigHit:
    """A single search result: a benign-looking policy mutation set
    plus the chain verdict it produces on the target chain.
    """
    mutations: Tuple[PolicyMutation, ...]
    """The mutation tuple that produced this hit."""

    verdict_action: ChainAction
    """The action the mutated registry produced on the target chain."""

    verdict_digest: str
    """The verdict's SHA-256 digest (audit anchor)."""

    benign_looking_score: float
    """A small float in [0.0, 1.0]. Lower = more innocuous-looking.
    0.0 = "no mutation at all" (the original config).
    1.0 = "every verb is at PUBLIC level in the default cluster"
    (the maximally innocuous config)."""

    hit_type: str
    """One of:
        * "adversarial_success" — clearance admitted the chain, but the
          original runtime substrate would have tripped it. *Caught
          by defense-in-depth, not by clearance.*
        * "true_negative" — clearance admitted the chain, and the
          original runtime substrate *also* would have admitted it.
          The chain is genuinely safe.
        * "missed_trip" — clearance admitted the chain, and the
          original runtime substrate would *also* have admitted it,
          AND the chain is *actually dangerous* (matches the target
          pattern's danger signature). This is the worst case:
          a real attack slipped through every substrate.
    """

    chain_verdict_dict: Dict[str, Any]
    """The mutated gate's verdict on the target chain, as a dict.
    Useful for the CLI's review-queue entry."""

    mutation_digest: str
    """A short hash of the mutation tuple (for de-duplication)."""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mutations": [m.describe() for m in self.mutations],
            "verdict_action": self.verdict_action.value,
            "verdict_digest": self.verdict_digest,
            "benign_looking_score": self.benign_looking_score,
            "hit_type": self.hit_type,
            "chain_verdict": self.chain_verdict_dict,
            "mutation_digest": self.mutation_digest,
        }


def _benign_looking_score(
    original_policies: Dict[str, VerbPolicy],
    mutated_policies: Dict[str, VerbPolicy],
) -> float:
    """A small heuristic for "how innocuous does this config look on
    review?" Lower = more innocuous.

    Three components (all in [0, 1], summed with weights):
      * classification-drop: how many verbs were downgraded, normalized
        by the count of downgradable verbs. More drops = more
        innocuous (less alarming to a reviewer).
      * cluster-collapse: how many verbs moved to "default", normalized
        by the count of non-default verbs. More moves = more innocuous.
      * cap-removal: how many `max_input_classification` caps were
        removed, normalized by the count of verbs with caps.

    Final score is `0.6 * drops + 0.3 * cluster + 0.1 * cap_removal`,
    clamped to [0.0, 1.0]. A score of 0.0 means "no mutations" (the
    original config), 1.0 means "every knob dialed to its most
    innocuous setting".
    """
    drops = 0
    droppable = 0
    for name, orig in original_policies.items():
        mutated = mutated_policies.get(name)
        if mutated is None:
            continue
        if classification_rank(orig.classification) > 0:
            droppable += 1
            if (
                classification_rank(mutated.classification)
                < classification_rank(orig.classification)
            ):
                drops += 1
    drop_frac = (drops / droppable) if droppable else 0.0

    cluster_moves = 0
    clusterable = 0
    for name, orig in original_policies.items():
        if orig.cluster != "default":
            clusterable += 1
            mutated = mutated_policies.get(name)
            if mutated is not None and mutated.cluster == "default":
                cluster_moves += 1
    cluster_frac = (cluster_moves / clusterable) if clusterable else 0.0

    cap_removals = 0
    cap_count = 0
    for name, orig in original_policies.items():
        if orig.max_input_classification is not None:
            cap_count += 1
            mutated = mutated_policies.get(name)
            if (
                mutated is not None
                and mutated.max_input_classification is None
            ):
                cap_removals += 1
    cap_frac = (cap_removals / cap_count) if cap_count else 0.0

    score = 0.6 * drop_frac + 0.3 * cluster_frac + 0.1 * cap_frac
    return max(0.0, min(1.0, score))


def _classify_hit(
    *,
    mutated_action: ChainAction,
    original_action_on_same_chain: ChainAction,
    target_chain: Sequence[ChainStep],
) -> str:
    """Classify a hit into one of the three categories.

    "missed_trip" requires *both* the mutated gate to admit the chain
    *and* the original gate to also admit it (i.e. the original
    substrate does not catch the chain). For our purposes the target
    is a JADEPUFFER-style chain that the original substrate *should*
    trip, so a "missed_trip" means the search found a mutation that
    *removes* the original trip.
    """
    if mutated_action == ChainAction.ALLOW:
        if original_action_on_same_chain == ChainAction.ALLOW:
            return "missed_trip"
        return "adversarial_success"
    # mutated BLOCKED
    if original_action_on_same_chain != ChainAction.ALLOW:
        return "redundant"
    return "true_negative"


# ===========================================================================
# The finder
# ===========================================================================

@dataclass
class BenignConfigFinder:
    """The CONTRA-style benign-config finder.

    Usage:
        finder = BenignConfigFinder(
            target_chain=jadepuffer_chain(),
            gate=create_jadepuffer_demo_gate(),
        )
        hits = finder.search()
        for hit in hits:
            submit_to_review_queue(hit)  # human review

    The finder is *read-only* on the live gate. Mutations are applied
    to a shadow gate (a deep copy) and discarded. The search is
    bounded by `SearchBudget`. The finder emits `BenignConfigHit`
    records — review queue entries, not auto-applied configurations.
    """
    target_chain: Sequence[ChainStep]
    """The chain the search is trying to admit. Default JADEPUFFER
    pattern: read_env -> read_secret_store -> http_post_external."""

    gate: CompositionalPolicyGate
    """The live gate whose policy registry is the search space. The
    gate is *not* mutated."""

    budget: SearchBudget = field(default_factory=SearchBudget)
    """Search budget. Defaults are conservative (256 iterations, 5s)."""

    composition_mode: CompositionMode = CompositionMode.CLEARANCE
    """The mode the shadow gate runs in. CLEARANCE matches the
    default of the live substrate."""

    max_results: int = 16
    """Stop after this many hits. The CLI is the operator-facing
    surface; the finder's caller is expected to feed hits to a
    review queue, not accumulate them all in memory."""

    def _evaluate_on_original(self) -> ChainVerdict:
        """The original gate's verdict on the target chain. Used to
        classify hits (adversarial_success vs missed_trip)."""
        shadow = _copy_gate(self.gate)
        return shadow.check_chain(list(self.target_chain))

    def _evaluate_on_shadow(
        self, shadow: CompositionalPolicyGate
    ) -> ChainVerdict:
        return shadow.check_chain(list(self.target_chain))

    def _make_hit(
        self,
        *,
        mutations: Sequence[PolicyMutation],
        shadow: CompositionalPolicyGate,
        original_action: ChainAction,
    ) -> Optional[BenignConfigHit]:
        verdict = self._evaluate_on_shadow(shadow)
        if verdict.action != ChainAction.ALLOW:
            return None  # the search is only interested in admissions
        score = _benign_looking_score(
            self.gate._policies, shadow._policies
        )
        hit_type = _classify_hit(
            mutated_action=verdict.action,
            original_action_on_same_chain=original_action,
            target_chain=self.target_chain,
        )
        mutation_digest = hashlib.sha256(
            "|".join(m.digest() for m in mutations).encode("utf-8")
        ).hexdigest()[:16]
        return BenignConfigHit(
            mutations=tuple(mutations),
            verdict_action=verdict.action,
            verdict_digest=verdict.digest,
            benign_looking_score=score,
            hit_type=hit_type,
            chain_verdict_dict=verdict.to_dict(),
            mutation_digest=mutation_digest,
        )

    def search(self) -> List[BenignConfigHit]:
        """Run the bounded search. Returns a list of hits (possibly
        empty). The list is sorted by `(hit_type severity, benign_looking_score
        ascending)` so the most severe + most innocuous-looking hits
        come first.
        """
        original_verdict = self._evaluate_on_original()
        original_action = original_verdict.action

        # If the original gate already admits the target chain, the
        # search has nothing to find — the original config is itself
        # a "missed_trip" (or, more likely, the target is not a
        # dangerous chain under the current policy). We still emit
        # the *original* config as a hit so the operator sees the
        # baseline verdict, but the search will not iterate.
        if original_action == ChainAction.ALLOW:
            shadow = _copy_gate(self.gate)
            shadow.set_composition_mode(self.composition_mode)
            baseline_hit = self._make_hit(
                mutations=[],
                shadow=shadow,
                original_action=original_action,
            )
            return [baseline_hit] if baseline_hit else []

        space = derive_search_space(self.gate)
        if not space:
            return []

        started_at = time.time()
        iterations = 0
        hits: List[BenignConfigHit] = []
        seen_digests: set = set()
        # BFS-by-mutation-depth. The path is the prefix; we expand
        # the path by appending one mutation from `space` and
        # evaluating.
        # The starting node is the empty mutation tuple.
        current_paths: List[Tuple[PolicyMutation, ...]] = [()]
        # Track the original gate's verdict on the same chain for
        # the hit-type classifier.
        while current_paths and not self.budget.is_exhausted(
            iterations=iterations, started_at=started_at
        ):
            next_paths: List[Tuple[PolicyMutation, ...]] = []
            for path in current_paths:
                if self.budget.is_exhausted(
                    iterations=iterations, started_at=started_at
                ):
                    break
                if len(path) >= self.budget.max_depth:
                    continue
                for mut in space:
                    if self.budget.is_exhausted(
                        iterations=iterations, started_at=started_at
                    ):
                        break
                    if mut in path:
                        continue  # de-dupe
                    new_path = path + (mut,)
                    shadow = _copy_gate(self.gate)
                    shadow.set_composition_mode(self.composition_mode)
                    _apply_mutations(shadow, new_path)
                    iterations += 1
                    hit = self._make_hit(
                        mutations=new_path,
                        shadow=shadow,
                        original_action=original_action,
                    )
                    if hit is None:
                        continue
                    if hit.mutation_digest in seen_digests:
                        continue
                    seen_digests.add(hit.mutation_digest)
                    hits.append(hit)
                    if len(hits) >= self.max_results:
                        break
                    if len(new_path) < self.budget.max_depth:
                        next_paths.append(new_path)
                if len(hits) >= self.max_results:
                    break
            current_paths = next_paths
            if len(hits) >= self.max_results:
                break

        # Severity-ordered: missed_trip first (worst), then
        # adversarial_success, then true_negative. Within a tier, lower
        # benign_looking_score = more innocuous = more dangerous
        # (because the operator is more likely to approve it).
        severity_order = {
            "missed_trip": 0,
            "adversarial_success": 1,
            "true_negative": 2,
        }
        hits.sort(
            key=lambda h: (
                severity_order.get(h.hit_type, 99),
                h.benign_looking_score,
            )
        )
        return hits[: self.max_results]


# ===========================================================================
# Target-chain factory
# ===========================================================================

def jadepuffer_target_chain() -> List[ChainStep]:
    """The JADEPUFFER-style target chain: read env, read secret
    store, post externally. This is the canonical
    *benign-looking-but-dangerous* pattern from arXiv:2607.03423
    §5.2 red-team evaluation.
    """
    return [
        ChainStep(verb_name="read_env", taint_in=TaintSource_if_set()),
        ChainStep(
            verb_name="read_secret_store", taint_in=TaintSource_if_set()
        ),
        ChainStep(
            verb_name="http_post_external", taint_in=TaintSource_if_set()
        ),
    ]


# Late import to avoid circular import for the taint-source default.
def TaintSource_if_set():
    from core.compositional_policy import TaintSource
    return TaintSource.INTERNAL
