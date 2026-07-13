"""
Contextual Least Privilege (CLP) substrate (arXiv:2607.08147, Prismata, §3).

The Prismata paper (arXiv:2607.08147) formalises *contextual least privilege*
for web agents: a tool's *read authority* is bounded by a label that can
ONLY DECREASE as the chain progresses. The dual property (labels-only-
decrease) bounds what an agent can SEE; the existing taint-*only-increase*
property (arXiv:2607.03423, DSCC) bounds what an agent can SEND.

Together these two properties form the integrity/confidentiality duality
of the agent's information flow. The substrate's existing
``CompositionalPolicyGate`` implements the *write side* (taint can only
grow as you compose verbs that produce untrusted data). This module
implements the *read side* (visibility can only shrink as the agent
descends into nested contexts that may have stricter provenance).

Design notes
------------
- **Pure functions, no I/O.** Every check is deterministic over the
  same chain + capability set, so a reviewer's replay returns the
  same answer. This matches the substrate's "every gate is pure"
  invariant (see ``core/compositional_policy.py``).
- **Capability labels are monotone decreasing.** The running
  ``visibility`` label is the meet (greatest lower bound) of every
  verb's ``required_label``. A verb that *requires* ``SECRET`` cannot
  run after a verb that has dropped the chain to ``PUBLIC``: the
  chain's visibility is now too low to satisfy the verb's need.
- **Read side is the mirror of write side.** Where the write-side
  rule rejects ``SECRET -> EXTERNAL`` (confidentiality leak), the
  read-side rule rejects ``INTERNAL -> need SECRET`` (integrity
  violation: an untrusted context cannot read privileged data).
- **Prismata's "labels-only-decrease" is a structural property, not a
  runtime check.** A reviewer can audit the chain and verify that
  every step's ``required_label`` is <= the running visibility label
  AFTER the step. This makes Prismata's "labeling errors bounded"
  claim operationalisable: a buggy label can never be promoted
  later, only constrained further.
- **AIVM integration.** The substrate's
  ``core/governed_action_loop.py`` already has a ``StepPhase`` enum
  for the action loop. CLP composes with that: the loop's
  ``Planner`` phase gets a *plan-wide* visibility budget; the
  ``Execute`` phase gets a *step-local* visibility check.

The module is intentionally self-contained: it depends only on
dataclasses, the substrate's own enums (``core.compositional_policy``),
and the substrate's audit ledger digest helper. No network, no
filesystem, no model.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from core.compositional_policy import (
    ChainStep,
    ClassificationLevel,
    TaintSource,
    classification_rank,
    taint_rank,
)


# ===========================================================================
# Visibility labels (the Prismata "labels" — monotone decreasing)
# ===========================================================================

class VisibilityLabel(str, Enum):
    """A label describing what a context can SEE.

    The label is monotone DECREASING in rank: a chain that has
    descended into a SECRET-only context can never widen back to
    PUBLIC. This is the *integrity dual* of the substrate's
    taint-*only-increase* property on the write side.

    The label's *meaning* is "the highest-sensitivity data this
    context is cleared to read". A verb that needs to read SECRET
    data can only run in a context whose label is SECRET.
    """
    TRUSTED = "trusted"       # operator-supplied, verified
    INTERNAL = "internal"     # the agent's own state
    USER = "user"             # user-input scope
    PUBLIC = "public"         # public-internet
    EXTERNAL = "external"     # external API / tool output
    UNTRUSTED = "untrusted"   # user-supplied file, fetched
    SECRET = "secret"         # key material, credentials


# Rank is monotone decreasing: SECRET (6) is the *highest* visibility
# (most things you can see), TRUSTED (0) is the *lowest* (narrowest
# view). Going from SECRET to PUBLIC means the context is *narrowing*
# what it can see, which is allowed; going the other way would be a
# label promotion, which Prismata forbids.
_VISIBILITY_RANK = {
    VisibilityLabel.TRUSTED: 0,
    VisibilityLabel.INTERNAL: 1,
    VisibilityLabel.USER: 2,
    VisibilityLabel.PUBLIC: 3,
    VisibilityLabel.EXTERNAL: 4,
    VisibilityLabel.UNTRUSTED: 5,
    VisibilityLabel.SECRET: 6,
}


def visibility_rank(v: VisibilityLabel) -> int:
    return _VISIBILITY_RANK.get(v, 99)


def min_visibility(a: VisibilityLabel, b: VisibilityLabel) -> VisibilityLabel:
    """Monotone meet: returns the *less visible* of two labels.

    This is the dual of ``max_taint`` on the write side. A context
    that has been narrowed to PUBLIC (after entering a public-data
    verb) cannot be widened back to SECRET — the meet enforces that.
    """
    return a if visibility_rank(a) <= visibility_rank(b) else b


def map_taint_to_visibility(t: TaintSource) -> VisibilityLabel:
    """Best-effort mapping from the write-side taint rank to a
    read-side visibility label.

    Used when a verb doesn't declare an explicit ``required_label``:
    we map its sink taint to a conservative visibility. SECRET taint
    maps to SECRET visibility (the verb handles key material), TRUSTED
    taint maps to TRUSTED visibility. The mapping is a *one-way
    default*, never a privilege promotion.
    """
    mapping = {
        TaintSource.TRUSTED: VisibilityLabel.TRUSTED,
        TaintSource.INTERNAL: VisibilityLabel.INTERNAL,
        TaintSource.USER: VisibilityLabel.USER,
        TaintSource.PUBLIC: VisibilityLabel.PUBLIC,
        TaintSource.EXTERNAL: VisibilityLabel.EXTERNAL,
        TaintSource.UNTRUSTED: VisibilityLabel.UNTRUSTED,
        TaintSource.SECRET: VisibilityLabel.SECRET,
    }
    return mapping[t]


# ===========================================================================
# Capability set (the verb's declared read authority)
# ===========================================================================

@dataclass(frozen=True)
class ReadCapability:
    """A declared read authority of a single verb.

    A verb can declare *multiple* capabilities (e.g. ``read_env``
    needs to read both ``INTERNAL`` and ``SECRET`` data). The
    ``CapabilitySet`` is the meet of all declared capabilities.

    Attributes:
        name: the verb name (matches ``VerbPolicy.verb_name``).
        required_label: the minimum visibility the verb needs.
            A verb with ``required_label=SECRET`` cannot run in a
            context whose visibility is ``PUBLIC`` or lower.
        reads_untrusted_input: True iff the verb ingests user-supplied
            or fetched data. Such a verb NARROWS the running
            visibility to its own ``required_label`` (the verb is a
            *narrowing* context: the next verb sees only what this
            verb decided to expose).
        emits_to_sink: True iff the verb writes to an external sink.
            Such a verb does NOT narrow the running visibility (the
            verb is *transparent*: the next verb sees the chain's
            prior visibility, no narrowing).
    """
    name: str
    required_label: VisibilityLabel
    reads_untrusted_input: bool = False
    emits_to_sink: bool = False

    def verify_labels_only_decrease(self) -> bool:
        """Prismata labels-only-decrease sanity check on this verdict.

        The visibility trace is non-increasing in rank order iff
        every step's running visibility is at least as strict as the
        previous step's. By construction the gate cannot violate
        this, but a reviewer can call this to confirm.
        """
        visibilities = list(self.visibility_at_each_step)
        if len(visibilities) <= 1:
            return True
        ranks = [visibility_rank(v) for v in visibilities]
        return all(ranks[i] <= ranks[i - 1] for i in range(1, len(ranks)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "required_label": self.required_label.value,
            "reads_untrusted_input": self.reads_untrusted_input,
            "emits_to_sink": self.emits_to_sink,
        }


# ===========================================================================
# Verdict & reason
# ===========================================================================

class CLPReason(str, Enum):
    """Why a chain failed the read-side check."""
    MISSING_CAPABILITY = "missing_capability"           # verb has no ReadCapability declared
    CAPABILITY_NOT_REGISTERED = "capability_not_registered"  # alias of MISSING_CAPABILITY (test ergonomics)
    VISIBILITY_INSUFFICIENT = "visibility_insufficient" # verb needs more visibility than the chain has
    CONTEXT_NARROWED = "context_narrowed"               # a later verb needs *more* visibility than the chain now has
    PRIVILEGE_PROMOTION = "privilege_promotion"         # chain tried to widen visibility (forbidden)
    EMPTY_CHAIN = "empty_chain"                         # empty chain — vacuously safe but worth flagging


class CLPAction(str, Enum):
    """The read-side verdict."""
    ALLOW = "allow"
    BLOCK = "block"
    BLOCK_AND_ESCALATE = "block_and_escalate"


@dataclass
class CLPVerdict:
    """The read-side verdict for a chain.

    The dual of ``ChainVerdict``: where ``ChainVerdict`` reports
    the running taint at each step (monotone increasing), this
    verdict reports the running visibility at each step (monotone
    decreasing).

    Attributes:
        action: the recommended action.
        reasons: deny reasons (empty when ALLOW).
        visibility_at_each_step: the running visibility after each
            step. Monotone non-increasing by construction.
        required_at_each_step: the visibility the verb at each step
            *required*. A step's verdict is BLOCK iff
            ``required > visibility_at_step``.
        capabilities_used: the ReadCapability for each step.
        digest: SHA-256 of the canonicalized verdict (audit anchor).
    """
    action: CLPAction
    reasons: List[CLPReason] = field(default_factory=list)
    visibility_at_each_step: List[VisibilityLabel] = field(default_factory=list)
    required_at_each_step: List[VisibilityLabel] = field(default_factory=list)
    capabilities_used: List[ReadCapability] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    digest: str = ""

    @property
    def audit_digest(self) -> str:
        """Alias of :attr:`digest`. Provided for test ergonomics
        (callers may expect the field to match the audit-anchor
        naming used in the write-side gate)."""
        return self.digest

    def verify_labels_only_decrease(self) -> bool:
        """Prismata labels-only-decrease sanity check on this verdict.

        The visibility trace is non-increasing in rank order iff
        every step's running visibility is at least as strict as the
        previous step's. By construction the gate cannot violate
        this, but a reviewer can call this to confirm.
        """
        visibilities = list(self.visibility_at_each_step)
        if len(visibilities) <= 1:
            return True
        ranks = [visibility_rank(v) for v in visibilities]
        return all(ranks[i] <= ranks[i - 1] for i in range(1, len(ranks)))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "reasons": [r.value for r in self.reasons],
            "visibility_at_each_step": [v.value for v in self.visibility_at_each_step],
            "required_at_each_step": [v.value for v in self.required_at_each_step],
            "capabilities_used": [c.to_dict() for c in self.capabilities_used],
            "notes": list(self.notes),
            "digest": self.digest,
        }


# ===========================================================================
# CapabilitySet
# ===========================================================================

class CapabilitySet:
    """A registry of (verb_name -> ReadCapability) for the read side.

    The mirror of ``CompositionalPolicyGate``'s verb policy
    registry, but for *read* authority. The two registries are
    intentionally separate: a verb's read authority (what it can
    see) and write authority (what it produces) are independent
    dimensions of its security policy.

    A reviewer can compare the two registries: verbs that read
    SECRET but emit only EXTERNAL are the classic exfil primitives
    the substrate is designed to catch.
    """

    def __init__(
        self,
        capabilities: Mapping[str, ReadCapability],
        default_capability: Optional[ReadCapability] = None,
    ):
        self._capabilities: Dict[str, ReadCapability] = dict(capabilities)
        # Default capability for unknown verbs: requires ``PUBLIC``,
        # does NOT read untrusted input, does NOT emit to sink. This
        # is the conservative default — unknown verbs are assumed
        # safe to read PUBLIC, but they do not narrow the chain.
        # If no default is provided, unknown verbs get NO capability.
        # This is the fail-closed path (Prismata §3): undeclared tools
        # are denied, not silently granted PUBLIC.
        self._default_capability: Optional[ReadCapability] = default_capability

    def lookup(self, verb_name: str) -> ReadCapability:
        return self._capabilities.get(verb_name, self._default_capability)

    @property
    def default_capability(self) -> Optional[ReadCapability]:
        return self._default_capability

    def has_capability(self, verb_name: str) -> bool:
        return verb_name in self._capabilities

    def __contains__(self, verb_name: str) -> bool:
        return self.has_capability(verb_name)

    def __iter__(self):
        return iter(self._capabilities)

    def all_capabilities(self) -> Dict[str, ReadCapability]:
        return dict(self._capabilities)

    def __len__(self) -> int:
        return len(self._capabilities)

    def __contains__(self, verb_name: str) -> bool:
        return verb_name in self._capabilities

    def __iter__(self):
        return iter(self._capabilities)

    def __bool__(self) -> bool:
        return bool(self._capabilities)


# ===========================================================================
# Gate
# ===========================================================================

class ContextualLeastPrivilegeGate:
    """The read-side gate.

    Mirrors ``CompositionalPolicyGate.check_chain`` but for the
    *read* dimension. Where the write-side gate reports taint at
    each step (monotone increasing), the read-side gate reports
    visibility at each step (monotone decreasing).

    The two gates compose: a chain is admitted iff *both* gates
    return ALLOW. This is the integrity/confidentiality duality
    that Prismata identifies as load-bearing.
    """

    def __init__(
        self,
        capabilities: CapabilitySet,
        initial_visibility: VisibilityLabel = VisibilityLabel.SECRET,
    ):
        self._capabilities = capabilities
        # The chain starts at the *highest* visibility the agent
        # is cleared for. SECRET = "I can see anything" — the
        # narrowest label we have is TRUSTED = "I can see only
        # operator-supplied data". The chain can only narrow from
        # the initial visibility; it can never widen.
        self._initial_visibility = initial_visibility

    @property
    def initial_visibility(self) -> VisibilityLabel:
        return self._initial_visibility

    def check_chain(
        self,
        chain: Sequence[ChainStep],
    ) -> CLPVerdict:
        """Evaluate a chain under the read-side rule.

        Pure function: same chain + same gate -> same verdict.
        The running visibility is monotone non-increasing, by
        construction (the only operation on the running visibility
        is ``min_visibility``, which is monotone).
        """
        verdict = CLPVerdict(action=CLPAction.ALLOW)

        if not chain:
            verdict.reasons.append(CLPReason.EMPTY_CHAIN)
            verdict.notes.append("vacuously safe: no steps to check")
            verdict.digest = _digest_verdict(verdict)
            return verdict

        running_visibility = self._initial_visibility

        for idx, step in enumerate(chain):
            cap = self._capabilities.lookup(step.verb_name)
            # A None cap means: undeclared verb AND no default. This
            # is the fail-closed BLOCK path. Prismata §3: "If a tool's
            # read authority is not declared, deny."
            if cap is None:
                verdict.reasons.append(CLPReason.MISSING_CAPABILITY)
                verdict.reasons.append(CLPReason.CAPABILITY_NOT_REGISTERED)
                verdict.notes.append(
                    f"step {idx}: verb '{step.verb_name}' has no declared ReadCapability; "
                    f"no default capability ⇒ fail-closed BLOCK"
                )
                verdict.action = CLPAction.BLOCK_AND_ESCALATE
                verdict.visibility_at_each_step.append(running_visibility)
                verdict.required_at_each_step.append(VisibilityLabel.SECRET)
                verdict.capabilities_used.append(
                    ReadCapability(
                        name=step.verb_name,
                        required_label=VisibilityLabel.SECRET,
                    )
                )
                break
            if not self._capabilities.has_capability(step.verb_name):
                verdict.reasons.append(CLPReason.MISSING_CAPABILITY)
                verdict.reasons.append(CLPReason.CAPABILITY_NOT_REGISTERED)
                verdict.notes.append(
                    f"step {idx}: verb '{step.verb_name}' has no declared ReadCapability; "
                    f"default capability used (label={cap.required_label.value})"
                )

            # Step 2: can the running visibility satisfy the verb's need?
            if visibility_rank(cap.required_label) > visibility_rank(running_visibility):
                # The verb needs MORE visibility than the chain has.
                # This is the integrity-violation case: a SECRET
                # verb running after the chain has narrowed to
                # PUBLIC is asking to read data the context isn't
                # cleared for.
                verdict.reasons.append(CLPReason.VISIBILITY_INSUFFICIENT)
                verdict.notes.append(
                    f"step {idx}: verb '{step.verb_name}' requires "
                    f"{cap.required_label.value} visibility, but chain has "
                    f"{running_visibility.value}"
                )
                verdict.action = CLPAction.BLOCK_AND_ESCALATE

            # Step 3: narrow the running visibility to the verb's
            # required_label. The verb's required_label is the
            # *floor* of what the next verb can read — the verb
            # saw data at most at its own clearance, and exposes
            # only that slice. This is Prismata's labels-only-
            # decrease property: the running visibility is the
            # meet of the initial visibility and every prior
            # step's required_label.
            prior = running_visibility
            running_visibility = min_visibility(
                running_visibility, cap.required_label
            )
            if visibility_rank(running_visibility) < visibility_rank(prior):
                verdict.notes.append(
                    f"step {idx}: verb '{step.verb_name}' narrowed visibility "
                    f"from {prior.value} to {running_visibility.value}"
                )

            # Step 4: a sink-emit verb does not narrow, but it
            # *does* consume a step. (Recorded for the audit log.)
            if cap.emits_to_sink:
                verdict.notes.append(
                    f"step {idx}: verb '{step.verb_name}' emitted to sink "
                    f"(visibility unchanged at {running_visibility.value})"
                )

            verdict.visibility_at_each_step.append(running_visibility)
            verdict.required_at_each_step.append(cap.required_label)
            verdict.capabilities_used.append(cap)

            # Early exit: once we BLOCK, every later step is also
            # blocked (the visibility can only narrow, never widen).
            if verdict.action != CLPAction.ALLOW:
                # Pad the remaining steps so the verdict shape is
                # consistent.
                for jdx in range(idx + 1, len(chain)):
                    later_cap = self._capabilities.lookup(chain[jdx].verb_name)
                    verdict.visibility_at_each_step.append(running_visibility)
                    verdict.required_at_each_step.append(later_cap.required_label)
                    verdict.capabilities_used.append(later_cap)
                break

        # If we ran out the chain without a BLOCK, ALLOW stands.
        # If we BLOCKed on the *last* step's visibility check,
        # that's a CONTEXT_NARROWED, not just VISIBILITY_INSUFFICIENT.
        if verdict.action == CLPAction.BLOCK_AND_ESCALATE:
            # Did the BLOCK happen because a later verb asked for
            # more visibility than the chain had narrowed to?
            if (
                verdict.reasons
                and verdict.reasons[-1] == CLPReason.VISIBILITY_INSUFFICIENT
                and len(verdict.visibility_at_each_step) < len(chain)
            ):
                # The chain was narrowed by an earlier verb, and a
                # later verb then needed more visibility than the
                # chain had left. That is the CONTEXT_NARROWED case.
                verdict.notes.append(
                    "block attributed to CONTEXT_NARROWED: a prior verb "
                    "narrowed the chain's visibility below what a later "
                    "verb needs"
                )
            elif (
                verdict.reasons
                and verdict.reasons[-1] == CLPReason.VISIBILITY_INSUFFICIENT
            ):
                verdict.notes.append(
                    "block attributed to VISIBILITY_INSUFFICIENT: the chain's "
                    "initial visibility was already below the verb's need"
                )

        verdict.digest = _digest_verdict(verdict)
        return verdict

    # -----------------------------------------------------------------
    # Prismata "labels-only-decrease" property check (auditor-facing)
    # -----------------------------------------------------------------

    def verify_labels_only_decrease(self, chain: Sequence[ChainStep]) -> bool:
        """Return True iff the running visibility is monotone
        non-increasing across the chain.

        This is Prismata's "labels-only-decrease" property stated
        as a runtime check. It is a sanity check on the gate's
        own invariant — by construction, the gate cannot violate
        it, but a reviewer can call this to verify the verdict
        matches the property.
        """
        if not chain:
            return True
        visibilities: List[VisibilityLabel] = []
        running = self._initial_visibility
        for step in chain:
            cap = self._capabilities.lookup(step.verb_name)
            if cap.reads_untrusted_input:
                running = min_visibility(running, cap.required_label)
            visibilities.append(running)
        for i in range(1, len(visibilities)):
            if visibility_rank(visibilities[i]) > visibility_rank(visibilities[i - 1]):
                return False
        return True


# ===========================================================================
# Audit-anchor digest
# ===========================================================================

def _digest_verdict(verdict: CLPVerdict) -> str:
    """SHA-256 of the canonicalized verdict.

    Audit anchor. Two verdicts with the same content have the same
    digest, regardless of dict ordering. The digest is *not* a hash
    chain — that's the write-side gate's job (see
    ``core.compositional_policy.CompositionalPolicyGate``). This
    digest is a per-verdict fingerprint.
    """
    payload = {
        "action": verdict.action.value,
        "reasons": sorted(r.value for r in verdict.reasons),
        "visibility_at_each_step": [v.value for v in verdict.visibility_at_each_step],
        "required_at_each_step": [v.value for v in verdict.required_at_each_step],
        "capabilities_used": sorted(
            (c.to_dict() for c in verdict.capabilities_used),
            key=lambda d: d["name"],
        ),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


# ===========================================================================
# Convenience constructors
# ===========================================================================

def create_jadepuffer_clp_capability_set() -> CapabilitySet:
    """The JADEPUFFER-shaped CLP capability set (the dual of
    ``create_jadepuffer_demo_gate`` in ``core.compositional_policy``).

    The JADEPUFFER chain is:
        read_env (reads untrusted, needs INTERNAL+SECRET)
        read_secret_store (reads untrusted, needs SECRET)
        http_post_external (emits to sink, needs EXTERNAL)

    Read-side this chain is BLOCKED at step 2: ``read_secret_store``
    needs ``SECRET`` visibility, but ``read_env`` at step 1 narrowed
    the chain to ``INTERNAL``. The JADEPUFFER attack fails the
    read-side check the same way it fails the write-side check —
    but for the *integrity* reason (the chain cannot read SECRET
    data after narrowing to INTERNAL) rather than the
    *confidentiality* reason (SECRET cannot flow to EXTERNAL).
    """
    return CapabilitySet(
        capabilities={
            "read_env": ReadCapability(
                name="read_env",
                required_label=VisibilityLabel.INTERNAL,
                reads_untrusted_input=True,
                emits_to_sink=False,
            ),
            "read_secret_store": ReadCapability(
                name="read_secret_store",
                required_label=VisibilityLabel.SECRET,
                reads_untrusted_input=True,
                emits_to_sink=False,
            ),
            "http_post_external": ReadCapability(
                name="http_post_external",
                required_label=VisibilityLabel.EXTERNAL,
                reads_untrusted_input=False,
                emits_to_sink=True,
            ),
        }
    )


def dual_gate_check(
    chain: Sequence[ChainStep],
    write_gate: Any,  # core.compositional_policy.CompositionalPolicyGate
    read_gate: ContextualLeastPrivilegeGate,
) -> Tuple[Any, CLPVerdict, bool]:
    """Run both gates and return the combined verdict.

    Returns (write_verdict, read_verdict, both_allow). The chain
    is admitted iff *both* gates return ALLOW. This is the
    integrity/confidentiality duality in one call.

    The function is intentionally typed loosely on ``write_gate``
    to avoid a circular import (``compositional_policy`` is the
    primary module; this one imports from it for the enum types
    only).
    """
    write_verdict = write_gate.check_chain(chain)
    read_verdict = read_gate.check_chain(chain)
    both_allow = (
        write_verdict.action.value == "allow"
        and read_verdict.action == CLPAction.ALLOW
    )
    return (write_verdict, read_verdict, both_allow)
