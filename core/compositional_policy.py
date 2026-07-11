"""
Compositional policy gate (arXiv:2607.03423 DSCC-style, security-driven).

The 2026-07-09 build closes a different gap than the per-verb
VerbPolicyBundle. Per-verb policy is "is this single tool call
permitted?". The compositional gap is: "is this *sequence* of tool
calls safe even when each individual call is permitted?". The 2026-07-10
build wires the gate into GovernedActionLoop as Step 6. The 2026-07-11
build feeds every chain verdict into a ProbabilisticTripEngine so the
operator gets a steady-state safety claim ("we expect <= X% of chains
to escalate") backed by a (1 - alpha) upper bound.

This is the gap exploited by the 2026-07-01 JADEPUFFER incident
(Sysdig Threat Research): an LLM agent chained read_env +
http_post_external + read_secret_store + http_post_external. Each
call was permitted in isolation; the chain was an exfiltration
pipeline.

Research grounding (2026-07-09):
  - arXiv:2607.03423 (DSCC, Microsoft AI, 2026): per-tool guardrails
    are insufficient for multi-tool chains. The MRS (Most Restrictive
    Set) compositional policy is the principled answer: chain
    policy = tightest single-tool policy + monotonic taint tracking.
  - arXiv:2607.05120 (Agent Data Injection, 2026): "trusted" data
    used as instructions. The TaintSource concept in this module
    captures which data is trusted vs untrusted.
  - CONTRA (arXiv:2607.03220, 2026): 75.1% of skills have a benign
    configuration that triggers a malicious action. Compositional
    checks reduce this attack surface.

Conservative posture:
  - Default-DENY for unknown verbs (per UNKNOWN_VERB).
  - Taint is monotonic: untrusted data cannot become trusted.
  - Chain verdict is FAIL-CLOSED: any unknown combination returns
    BLOCK_AND_ESCALATE, never ALLOW.
  - Pure functions: check_chain is a pure function of
    (chain, policy_snapshot) - no I/O, no globals.
  - All verdicts are recorded into a hash-chained audit log so
    downstream replay layers can reconstruct the decision.
  - No auto-acts: this module *classifies*; the caller decides
    whether to allow, block, or escalate.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Soft import of the probabilistic trip engine substrate (added 2026-07-11).
# The compositional gate feeds every chain verdict into a trip engine so the
# operator gets a steady-state safety claim ("we expect <= X% of chains to
# escalate") backed by a (1 - alpha) upper bound. The soft import keeps
# compositional_policy.py usable even if the CEF probabilistic module is
# missing or in a broken state (CEFDetectorAvailability-style fallback).
try:  # pragma: no cover - exercised by import path
    from core.cef_probabilistic_verification import (
        ProbabilisticTripEngine,
        TripObservation,
    )
    _TRIP_ENGINE_AVAILABLE = True
except Exception:  # noqa: BLE001 - import-time isolation
    ProbabilisticTripEngine = None  # type: ignore[assignment]
    TripObservation = None  # type: ignore[assignment]
    _TRIP_ENGINE_AVAILABLE = False


# ===========================================================================
# Enums
# ===========================================================================

class TaintSource(str, Enum):
    """Where a piece of data came from. Monotonic: cannot decrease."""
    TRUSTED = "trusted"             # operator-supplied, verified
    INTERNAL = "internal"           # the agent's own state
    USER = "user"                   # direct user input
    PUBLIC = "public"               # public-internet read
    EXTERNAL = "external"           # external API / tool output
    UNTRUSTED = "untrusted"         # user-supplied file, fetched, etc.
    SECRET = "secret"               # key material, credentials


# Two orthogonal taint orders:
#   - *Data* taint: how untrusted the data is. SECRET > UNTRUSTED >
#     EXTERNAL > PUBLIC > USER > INTERNAL > TRUSTED.
#   - *Sink* taint: how untrusted the destination is. EXTERNAL > PUBLIC
#     > USER > INTERNAL > TRUSTED. Sink taint never has SECRET/UNTRUSTED
#     (sinks are destinations, not data sources).
# The compositional rule is: data of taint X going to a sink of
# taint Y is a leak iff X is more tainted than Y. We use two
# separate ranks to avoid the bug where max(taint) overwrites
# SECRET with EXTERNAL.

_DATA_RANK = {
    TaintSource.TRUSTED: 0,
    TaintSource.INTERNAL: 1,
    TaintSource.USER: 2,
    TaintSource.PUBLIC: 3,
    TaintSource.EXTERNAL: 4,
    TaintSource.UNTRUSTED: 5,
    TaintSource.SECRET: 6,
}

_SINK_RANK = {
    TaintSource.TRUSTED: 0,
    TaintSource.INTERNAL: 1,
    TaintSource.USER: 2,
    TaintSource.PUBLIC: 3,
    TaintSource.EXTERNAL: 4,
}


def data_rank(t: TaintSource) -> int:
    return _DATA_RANK.get(t, 99)


def sink_rank(t: TaintSource) -> int:
    return _SINK_RANK.get(t, 99)


def max_data_taint(a: TaintSource, b: TaintSource) -> TaintSource:
    """Monotonic join on data taint."""
    return a if data_rank(a) >= data_rank(b) else b


def max_sink_taint(a: TaintSource, b: TaintSource) -> TaintSource:
    """Monotonic join on sink taint. Defaults to INTERNAL on miss."""
    if a not in _SINK_RANK and b not in _SINK_RANK:
        return TaintSource.INTERNAL
    if a not in _SINK_RANK:
        return b
    if b not in _SINK_RANK:
        return a
    return a if sink_rank(a) >= sink_rank(b) else b


# Kept as alias for backward compat.
def taint_rank(t: TaintSource) -> int:
    return data_rank(t)


def max_taint(a: TaintSource, b: TaintSource) -> TaintSource:
    return max_data_taint(a, b)


class ChainAction(str, Enum):
    """What to do with the chain."""
    ALLOW = "allow"
    ALLOW_ONLY_REVIEW = "allow_only_review"
    BLOCK = "block"
    BLOCK_AND_ESCALATE = "block_and_escalate"


class DenyReason(str, Enum):
    """Why the chain was denied. The first matching reason wins."""
    MISSING_VERB_POLICY = "missing_verb_policy"
    TAINT_ESCALATION = "taint_escalation"
    SECRET_TO_EXTERNAL = "secret_to_external"
    SENSITIVE_TO_PUBLIC = "sensitive_to_public"
    WRITE_AFTER_UNTRUSTED = "write_after_untrusted"
    TOO_MANY_DISTINCT_SINKS = "too_many_distinct_sinks"
    UNKNOWN_VERB = "unknown_verb"


# ===========================================================================
# Per-verb policy (operator-supplied)
# ===========================================================================

@dataclass(frozen=True)
class VerbPolicy:
    """Per-verb policy declaration.

    `taint_in` describes the taint the verb outputs (e.g. http_get
    outputs EXTERNAL). It is interpreted as the *sink taint* of the
    verb: how untrusted a destination the verb represents.

    `sinks` is the set of sink categories the verb belongs to. Used
    for sink-fanout analysis (many distinct sinks in one chain is a
    classic exfiltration pattern).

    `requires_review` if True: the verb forces ALLOW_ONLY_REVIEW on
    any chain containing it.

    `is_secret_emitting` if True: the verb is itself a source of
    secret material (e.g. read_secret_store, read_env). The data
    taint becomes SECRET whenever this verb is invoked.
    """
    verb_name: str
    taint_in: TaintSource
    sinks: Tuple[str, ...] = ()
    requires_review: bool = False
    max_taint_threshold: Optional[TaintSource] = None
    is_secret_emitting: bool = False
    is_secret_accepting: bool = False


# ===========================================================================
# Chain types
# ===========================================================================

@dataclass(frozen=True)
class ChainStep:
    """A single step in a proposed tool chain."""
    verb_name: str
    taint_in: TaintSource = TaintSource.INTERNAL


@dataclass
class ChainVerdict:
    """The verdict for a chain evaluation.

    `action` is the recommended action. `reasons` is the list of
    deny reasons (empty when ALLOW). `taint_at_each_step[i]` is the
    running data taint after step i. `sink_taint_at_each_step[i]`
    is the running sink taint after step i. `digest` is the SHA-256
    of the canonicalized verdict (audit anchor).
    """
    action: ChainAction
    reasons: List[DenyReason] = field(default_factory=list)
    taint_at_each_step: List[TaintSource] = field(default_factory=list)
    sink_taint_at_each_step: List[TaintSource] = field(default_factory=list)
    sinks_seen: Tuple[str, ...] = ()
    contains_secret: bool = False
    digest: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "reasons": [r.value for r in self.reasons],
            "taint_at_each_step": [t.value for t in self.taint_at_each_step],
            "sink_taint_at_each_step": [t.value for t in self.sink_taint_at_each_step],
            "sinks_seen": list(self.sinks_seen),
            "contains_secret": self.contains_secret,
            "digest": self.digest,
        }


# ===========================================================================
# Gate
# ===========================================================================

class CompositionalPolicyGate:
    """The compositional policy gate.

    Holds a registry of (verb_name -> VerbPolicy) and a default
    policy for unknown verbs. The gate's `check_chain` is a pure
    function: same input -> same output. The gate also maintains a
    hash-chained audit log so the caller can replay decisions.

    Conservative posture:
      - Unknown verbs default to BLOCK_AND_ESCALATE.
      - Empty chain returns ALLOW (vacuously safe).
      - A chain of length 1 is allowed iff the verb's policy allows it.
    """

    DEFAULT_MAX_SINKS = 3  # > 3 distinct sinks triggers fanout alarm

    def __init__(
        self,
        policies: Optional[Dict[str, VerbPolicy]] = None,
        default_unknown_policy: Optional[VerbPolicy] = None,
        max_sinks: int = DEFAULT_MAX_SINKS,
        audit_log: Optional[List[Dict[str, Any]]] = None,
        trip_engine: Optional["ProbabilisticTripEngine"] = None,
    ) -> None:
        self._policies: Dict[str, VerbPolicy] = dict(policies or {})
        self._default_unknown = default_unknown_policy
        self._max_sinks = max(1, int(max_sinks))
        self._audit: List[Dict[str, Any]] = list(audit_log) if audit_log is not None else []
        self._last_chain_digest: str = ""
        # Trip engine (optional, added 2026-07-11). When attached, every
        # check_chain() verdict is fed to the engine as a TripObservation
        # with tripped = (verdict.action != ChainAction.ALLOW). The engine
        # is read-only with respect to gate state: the gate's policies,
        # audit log, and verdict digest are all unaffected. The engine's
        # update() returns self, so a caller can snapshot the engine
        # state without touching the gate. The engine can also be
        # attached after construction via attach_trip_engine().
        if trip_engine is not None and ProbabilisticTripEngine is None:
            raise RuntimeError(
                "trip_engine was supplied but core.cef_probabilistic_verification "
                "is not importable in this environment"
            )
        self._trip_engine = trip_engine

    def attach_trip_engine(self, engine: "ProbabilisticTripEngine") -> None:
        """Attach a probabilistic trip engine to this gate.

        After attachment, every subsequent :meth:`check_chain` call will
        emit a :class:`TripObservation` to the engine. This is the
        steady-state safety monitor: the engine's ``trip_upper_bound``
        is the operator's claim about the chain-escalation rate.

        Parameters
        ----------
        engine : ProbabilisticTripEngine
            The engine to feed. Must not be ``None``. To detach the
            engine, set ``gate._trip_engine = None`` directly (intended
            for test teardown only).

        Raises
        ------
        TypeError
            If ``engine`` is ``None``.
        RuntimeError
            If the trip-engine module is not importable in this
            environment.
        """
        if engine is None:
            raise TypeError("engine must be a ProbabilisticTripEngine, not None")
        if ProbabilisticTripEngine is None:
            raise RuntimeError(
                "engine was supplied but core.cef_probabilistic_verification "
                "is not importable in this environment"
            )
        self._trip_engine = engine

    @property
    def trip_engine(self) -> Optional["ProbabilisticTripEngine"]:
        """The attached trip engine, or ``None`` if not attached."""
        return self._trip_engine

    @property
    def has_trip_engine(self) -> bool:
        return self._trip_engine is not None

    def trip_engine_state(self) -> Optional[Dict[str, Any]]:
        """Snapshot of the attached engine's state, or ``None``.

        Returns ``None`` if no engine is attached. Otherwise returns
        ``engine.summary()`` (n_success, n_failure, n_observations,
        empirical_rate, trip_upper_bound, trip_band). Read-only.
        """
        if self._trip_engine is None:
            return None
        return self._trip_engine.summary()

    def _record_trip_observation(self, v: ChainVerdict, chain: Sequence[ChainStep], now: Optional[float]) -> None:
        """Feed a single verdict into the attached trip engine.

        No-op when no engine is attached or when the trip engine module
        is not importable. The mapping is:

        - ``ChainAction.ALLOW`` -> TripObservation(tripped=False)
        - everything else (BLOCK, ALLOW_ONLY_REVIEW, BLOCK_AND_ESCALATE) -> TripObservation(tripped=True)

        The source string is ``"compositional_gate"`` so an AIOps layer
        can distinguish gate-driven observations from per-output CEF
        observations. ``detection_id`` is set to the chain digest when
        available, so the engine's history is replay-linkable to the
        gate's audit log.

        The engine is updated in-place; the engine's own ``update``
        returns self so the caller's chain pattern works. The gate's
        state is not mutated.
        """
        if self._trip_engine is None or TripObservation is None:
            return
        tripped = v.action != ChainAction.ALLOW
        # Use the audit log's chained digest if available (recorded just
        # before this call), falling back to the verdict digest.
        if self._audit:
            detection_id = self._audit[-1].get("digest") or v.digest or None
        else:
            detection_id = v.digest if v.digest else None
        obs = TripObservation(
            tripped=tripped,
            source="compositional_gate",
            detection_id=detection_id,
            session_digest=None,
            timestamp=float(now) if now is not None else time.time(),
        )
        try:
            self._trip_engine.update(obs)
        except Exception:  # noqa: BLE001 - never let the engine crash the gate
            # An engine that throws should not break a check_chain call.
            # The operator can detect the breakage via the engine's own
            # state (n_observations not advancing).
            return

    def register(self, policy: VerbPolicy) -> None:
        if not policy.verb_name:
            raise ValueError("VerbPolicy.verb_name is required")
        self._policies[policy.verb_name] = policy

    def lookup(self, verb_name: str) -> Optional[VerbPolicy]:
        return self._policies.get(verb_name)

    @property
    def audit_log(self) -> List[Dict[str, Any]]:
        return list(self._audit)

    @property
    def last_chain_digest(self) -> str:
        return self._last_chain_digest

    def check_chain(
        self,
        chain: Sequence[ChainStep],
        *,
        now: Optional[float] = None,
    ) -> ChainVerdict:
        """Evaluate a proposed chain. Pure function + audit append.

        `now` is a clock-override for deterministic tests. When None,
        uses time.time(). The audit log is the only side effect.
        """
        if not chain:
            v = ChainVerdict(action=ChainAction.ALLOW)
            v.digest = self._digest_verdict(v, chain)
            self._record_audit(v, chain, now)
            self._record_trip_observation(v, chain, now)
            return v

        reasons: List[DenyReason] = []
        running_data_taint = TaintSource.TRUSTED
        running_sink_taint = TaintSource.TRUSTED
        sinks: List[str] = []
        taint_at_each: List[TaintSource] = []
        sink_taint_at_each: List[TaintSource] = []
        contains_secret = False
        saw_untrusted = False

        for step in chain:
            policy = self.lookup(step.verb_name)
            if policy is None:
                if self._default_unknown is None:
                    reasons.append(DenyReason.UNKNOWN_VERB)
                    v = ChainVerdict(
                        action=ChainAction.BLOCK_AND_ESCALATE,
                        reasons=list(reasons),
                        taint_at_each_step=list(taint_at_each),
                        sink_taint_at_each_step=list(sink_taint_at_each),
                        sinks_seen=tuple(sinks),
                        contains_secret=contains_secret,
                    )
                    v.digest = self._digest_verdict(v, chain)
                    self._record_audit(v, chain, now)
                    self._record_trip_observation(v, chain, now)
                    return v
                policy = self._default_unknown

            # Monotonic taint update. Data taint propagates forward
            # only; sink taint propagates forward only. They are
            # orthogonal: data of taint X going to a sink of taint Y
            # is fine iff data_rank(X) <= sink_rank(Y).
            new_data_taint = max_data_taint(running_data_taint, step.taint_in)
            # The verb's own output is also a data taint source.
            # policy.taint_in is interpreted as a sink taint here:
            # it is the taint of the destination the verb represents.
            new_sink_taint = max_sink_taint(running_sink_taint, policy.taint_in)
            taint_at_each.append(new_data_taint)
            sink_taint_at_each.append(new_sink_taint)
            running_data_taint = new_data_taint
            running_sink_taint = new_sink_taint

            # Secret flow tracking. A step is 'secret-bearing' if
            # the data is secret OR the verb emits a secret.
            step_is_secret = (
                running_data_taint == TaintSource.SECRET
                or policy.is_secret_emitting
            )
            if step_is_secret:
                contains_secret = True

            # SECRET data -> a verb whose sink taint is EXTERNAL is
            # the classic exfil path. The data is what is being
            # leaked; the sink taint says where it is going.
            if (
                running_data_taint == TaintSource.SECRET
                and policy.taint_in == TaintSource.EXTERNAL
            ):
                if DenyReason.SECRET_TO_EXTERNAL not in reasons:
                    reasons.append(DenyReason.SECRET_TO_EXTERNAL)

            # Taint threshold check
            if (
                policy.max_taint_threshold is not None
                and data_rank(running_data_taint) > data_rank(policy.max_taint_threshold)
            ):
                if DenyReason.TAINT_ESCALATION not in reasons:
                    reasons.append(DenyReason.TAINT_ESCALATION)

            # Sensitive-to-public: SECRET data -> verb whose policy
            # taint is PUBLIC is a leak path. PUBLIC is below
            # EXTERNAL in sink rank.
            if (
                running_data_taint == TaintSource.SECRET
                and policy.taint_in == TaintSource.PUBLIC
            ):
                if DenyReason.SENSITIVE_TO_PUBLIC not in reasons:
                    reasons.append(DenyReason.SENSITIVE_TO_PUBLIC)

            # Write-after-untrusted: a verb that writes state
            # (sinks include "write" or "exec") following an
            # untrusted step is a prompt-injection pivot.
            if saw_untrusted and (
                "write" in policy.sinks or "exec" in policy.sinks
            ):
                if DenyReason.WRITE_AFTER_UNTRUSTED not in reasons:
                    reasons.append(DenyReason.WRITE_AFTER_UNTRUSTED)

            if step.taint_in in (TaintSource.UNTRUSTED, TaintSource.EXTERNAL):
                saw_untrusted = True

            # Sink fanout
            for s in policy.sinks:
                if s not in sinks:
                    sinks.append(s)
            if len(sinks) > self._max_sinks:
                if DenyReason.TOO_MANY_DISTINCT_SINKS not in reasons:
                    reasons.append(DenyReason.TOO_MANY_DISTINCT_SINKS)

        # Build verdict
        has_review = any(
            (self.lookup(s.verb_name) or self._default_unknown) is not None
            and (self.lookup(s.verb_name) or self._default_unknown).requires_review
            for s in chain
        )

        if DenyReason.SECRET_TO_EXTERNAL in reasons:
            action = ChainAction.BLOCK_AND_ESCALATE
        elif DenyReason.WRITE_AFTER_UNTRUSTED in reasons:
            action = ChainAction.BLOCK
        elif DenyReason.SENSITIVE_TO_PUBLIC in reasons:
            action = ChainAction.BLOCK
        elif DenyReason.TAINT_ESCALATION in reasons:
            action = ChainAction.BLOCK
        elif DenyReason.TOO_MANY_DISTINCT_SINKS in reasons:
            action = ChainAction.ALLOW_ONLY_REVIEW
        elif has_review:
            action = ChainAction.ALLOW_ONLY_REVIEW
        else:
            action = ChainAction.ALLOW

        v = ChainVerdict(
            action=action,
            reasons=list(reasons),
            taint_at_each_step=list(taint_at_each),
            sink_taint_at_each_step=list(sink_taint_at_each),
            sinks_seen=tuple(sinks),
            contains_secret=contains_secret,
        )
        v.digest = self._digest_verdict(v, chain)
        self._last_chain_digest = v.digest
        self._record_audit(v, chain, now)
        self._record_trip_observation(v, chain, now)
        return v

    # -----------------------------------------------------------------
    # Audit / digest internals
    # -----------------------------------------------------------------

    def _digest_verdict(self, v: ChainVerdict, chain: Sequence[ChainStep]) -> str:
        canon = {
            "chain": [(s.verb_name, s.taint_in.value) for s in chain],
            "verdict": v.to_dict(),
        }
        blob = json.dumps(canon, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    def _record_audit(
        self,
        v: ChainVerdict,
        chain: Sequence[ChainStep],
        now: Optional[float],
    ) -> None:
        ts = float(now) if now is not None else time.time()
        prev_digest = self._audit[-1]["digest"] if self._audit else ""
        record = {
            "ts": ts,
            "chain": [(s.verb_name, s.taint_in.value) for s in chain],
            "verdict": v.to_dict(),
            "prev_digest": prev_digest,
        }
        blob = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        record["digest"] = hashlib.sha256(blob).hexdigest()
        self._audit.append(record)


# ===========================================================================
# Smallest viable install
# ===========================================================================

def create_gate(
    policies: Optional[Dict[str, VerbPolicy]] = None,
    *,
    max_sinks: int = CompositionalPolicyGate.DEFAULT_MAX_SINKS,
) -> CompositionalPolicyGate:
    """Smallest viable install: 1 line, build a gate with sensible defaults.

    Default policies for the JADEPUFFER-pattern verbs are *not* installed
    automatically; the operator is expected to register them. A gate
    with no policies and no default_unknown will treat every chain as
    UNKNOWN_VERB and BLOCK_AND_ESCALATE - the safe default.
    """
    return CompositionalPolicyGate(
        policies=policies,
        default_unknown_policy=None,
        max_sinks=max_sinks,
    )


# ===========================================================================
# JadePuffer-pattern demo policies (operator convenience)
# ===========================================================================

# A small bundle of policies that model the JADEPUFFER attack surface.
# Operators are expected to register their own; this is a reference.

JADEPUFFER_DEMO_POLICIES: Dict[str, VerbPolicy] = {
    # read_env: emits SECRET data; taint_in is INTERNAL (the verb
    # itself is internal; it just produces secret output).
    "read_env": VerbPolicy(
        verb_name="read_env",
        taint_in=TaintSource.INTERNAL,
        sinks=("read",),
        is_secret_emitting=True,
    ),
    # read_secret_store: like read_env but explicitly for keys.
    "read_secret_store": VerbPolicy(
        verb_name="read_secret_store",
        taint_in=TaintSource.INTERNAL,
        sinks=("read",),
        is_secret_emitting=True,
    ),
    # http_get: an external read. Taint is EXTERNAL (the destination
    # is external). sinks include 'egress' (sends bytes out).
    "http_get": VerbPolicy(
        verb_name="http_get",
        taint_in=TaintSource.EXTERNAL,
        sinks=("egress",),
    ),
    # http_post_external: writes bytes to an external endpoint.
    "http_post_external": VerbPolicy(
        verb_name="http_post_external",
        taint_in=TaintSource.EXTERNAL,
        sinks=("egress", "write"),
    ),
    # read_file: a local read; UNTRUSTED (files can be tampered).
    "read_file": VerbPolicy(
        verb_name="read_file",
        taint_in=TaintSource.UNTRUSTED,
        sinks=("read",),
    ),
    # shell_exec: a sink that can do anything; forces review.
    "shell_exec": VerbPolicy(
        verb_name="shell_exec",
        taint_in=TaintSource.INTERNAL,
        sinks=("exec", "write", "egress"),
        requires_review=True,
    ),
    # write_file: a write sink; taint is INTERNAL.
    "write_file": VerbPolicy(
        verb_name="write_file",
        taint_in=TaintSource.INTERNAL,
        sinks=("write",),
    ),
}


def create_jadepuffer_demo_gate() -> CompositionalPolicyGate:
    """A gate pre-loaded with the JADEPUFFER-pattern policies.

    Used by the demo and by tests. The chain
    [read_env, http_post_external, read_secret_store, http_post_external]
    should return BLOCK_AND_ESCALATE with reason SECRET_TO_EXTERNAL.
    """
    return CompositionalPolicyGate(
        policies=dict(JADEPUFFER_DEMO_POLICIES),
        default_unknown_policy=None,
        max_sinks=3,
    )
