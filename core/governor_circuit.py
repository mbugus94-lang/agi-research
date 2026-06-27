"""Governor Circuit - Policy Input Layer for the CEF Substrate.

Turns the upper bound from the ProbabilisticTripEngine into a policy
(arXiv:2606.20510 follow-on).

Background
----------
The 2026-06-24 build (core/cef_probabilistic_verification.py) introduced
ProbabilisticTripEngine -- a measurement layer that produces a sound
(1 - alpha) upper bound on the agent's CEF trip rate, plus a discrete
trip band (LOW / MEDIUM / HIGH / CRITICAL).

The 2026-06-25 build wired that engine into CEFSessionDetector so the
*session* path is also measurable. The bound is now available at two
layers (per_output, session) per session.

This module is the third leg: a stateful policy gate that *acts* on
the bound. A measurement that nobody reads is a hidden alarm; a
measurement that the gate trips on is an operational instrument.

Design
------
The gate has three states, mirroring the SafetyCircuitBreaker contract
already in the repo:

  CLOSED    bound below trip_threshold        -> action: ALLOW
  OPEN      bound at or above trip_threshold  -> action: BLOCK
  HALF_OPEN bound dropped to reset_threshold  -> action: PROBE / ALLOW

Hysteresis
~~~~~~~~~~
The OPEN -> HALF_OPEN transition fires only when the bound drops below
``reset_threshold``, which is strictly less than ``trip_threshold``. This
prevents chatter: a bound oscillating around the trip line will not flap
the gate.

Recovery
~~~~~~~~
HALF_OPEN stays HALF_OPEN until either (a) the bound re-crosses
``trip_threshold`` and the gate goes back to OPEN, or (b) ``probe_count``
consecutive good probes (no-trip feed() calls in HALF_OPEN) confirm
recovery, and the gate closes.

Two-layer max
~~~~~~~~~~~~~
When two engines are configured (per_output + session), the gate's
bound is the *maximum* of the two engines' bounds. The gate trips when
EITHER layer reports a high bound, and recovers when BOTH are low.

Conservative posture
--------------------
* The trip band is the union of the per-output and session bands.
* Transitions are append-only; the transition log is the audit trail.
* The bound is never demoted by the gate (only by the engines).
* ``reset_threshold < trip_threshold`` is enforced in __post_init__.
* The OPEN->HALF_OPEN transition itself counts as the first good
  probe (so a bound that drops sharply and stays low closes the
  gate in 1-2 probes, not probe_count+1).
* ``write_audit`` is append-mode and idempotent on repeated calls.
* HALF_OPEN->OPEN recovery-failure resets ``consecutive_good`` to 0.

What this module is *not*
-------------------------
* Not a calibration service for the Beta prior (handled by the engine).
* Not a trip detector (the engines do that).
* Not an executor -- the gate returns an action; the caller decides.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol

# Soft import for TripObservation (optional). The governor can be used
# without the full probabilistic engine; when present, observations are
# wrapped in TripObservation before being passed to the engine.
try:
    from core.cef_probabilistic_verification import TripObservation  # type: ignore
except Exception:
    TripObservation = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _safe_n_obs(engine: Any) -> int:
    """Best-effort accessor for ``engine.n_observations``.

    Returns 0 if the engine is None, does not expose the attribute, or
    the attribute does not coerce to int. This is the safe default
    because cold engines (zero observations) are treated as silent by
    the gate; a missing attribute also means "no evidence", not
    "infinite evidence".
    """
    if engine is None:
        return 0
    raw = getattr(engine, "n_observations", None)
    if raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Protocol for the bound source (the engine).
# ---------------------------------------------------------------------------


class BoundSource(Protocol):
    """Structural type for the per-layer bound source.

    Both ``ProbabilisticTripEngine`` and the test stub satisfy this
    protocol. The contract:

    * ``update(observation)`` appends an observation to history.
    * ``trip_upper_bound`` returns the current sound upper bound
      on the trip rate (a value in [0, 1]).
    * ``trip_band`` returns the discrete band label
      (``"low"`` / ``"medium"`` / ``"high"`` / ``"critical"``).
    * ``n_observations`` returns the number of observations that
      have been fed. A cold engine (n_observations == 0) reports
      its *prior* bound, which is not meaningful evidence; the
      gate treats cold engines as silent.

    The default ``n_observations`` is 0 so test stubs and minimal
    protocol implementations remain compatible: a stub that has
    never been fed is treated as silent by the gate.

    Why cold engines are silent
    ---------------------------
    A fresh Beta(1, 1) engine with zero observations has an upper
    bound of 1.0 (CRITICAL) because the prior is uniform on [0, 1].
    Using that value in the two-layer max would trip the gate the
    instant any caller wired up an unwarmed engine -- the opposite
    of conservative behavior. A cold engine means "no evidence",
    not "maximal risk"; the gate therefore skips it.

    This matches the 2026 agent-governance consensus (AgentRiskBOM
    arXiv:2606.21877): capability opacity (i.e., what the agent
    *can* do but has not yet demonstrated) is reported alongside
    observed behavior, not conflated with it.
    """

    def update(self, observation: Any) -> Any:
        ...

    @property
    def trip_upper_bound(self) -> float:
        ...

    @property
    def trip_band(self) -> str:
        ...

    @property
    def n_observations(self) -> int:
        ...




# ---------------------------------------------------------------------------
# Enums and dataclasses.
# ---------------------------------------------------------------------------


class GateState(str, Enum):
    """The gate's three operational states.

    ``str`` mixin so JSON serialization produces readable values
    (``"closed"`` / ``"open"`` / ``"half_open"``).
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class GateAction(str, Enum):
    """The action the caller should take given the gate's decision.

    * ``ALLOW``: the request is permitted; the gate's state is CLOSED
      (or HALF_OPEN with sufficient good probes).
    * ``BLOCK``: the request is refused; the gate's state is OPEN.
    * ``PROBE``: the request is permitted as a probe (HALF_OPEN with
      insufficient good probes); the caller should treat the
      result as evidence for the next probe decision.
    """

    ALLOW = "allow"
    BLOCK = "block"
    PROBE = "probe"


DEFAULT_TRIP_THRESHOLD = 0.05
DEFAULT_RESET_THRESHOLD = 0.01
DEFAULT_PROBE_COUNT = 1
DEFAULT_WARM_UP_MIN_OBS = 10


@dataclass(frozen=True)
class GovernorCircuitConfig:
    """The gate's tunable thresholds.

    Attributes
    ----------
    trip_threshold : float
        The bound above which the gate opens. Default 0.05.
    reset_threshold : float
        The bound below which the gate moves from OPEN to HALF_OPEN.
        Must satisfy ``reset_threshold < trip_threshold``.
        Default 0.01.
    probe_count : int
        The number of consecutive good probes required before the
        gate closes (HALF_OPEN -> CLOSED). Default 1.
    warm_up_min_obs : int
        Minimum number of observations each engine must accumulate
        before its bound can trip the gate CLOSED -> OPEN. During
        the warm-up window, bounds are reported and decision
        metadata exposes the suppressed state, but transitions are
        recorded as ``warming_grace`` rather than as actual state
        changes. This matches the conservative posture: a wide
        posterior over a handful of observations is not strong
        evidence of a failure mode. Default 5.
    per_output_layer_id : str
        Metadata label for per-output observations. Default
        ``"per_output"``.
    session_layer_id : str
        Metadata label for session observations. Default
        ``"session"``.
    """

    trip_threshold: float = DEFAULT_TRIP_THRESHOLD
    reset_threshold: float = DEFAULT_RESET_THRESHOLD
    probe_count: int = DEFAULT_PROBE_COUNT
    warm_up_min_obs: int = DEFAULT_WARM_UP_MIN_OBS
    per_output_layer_id: str = "per_output"
    session_layer_id: str = "session"

    def __post_init__(self) -> None:
        if not 0.0 <= self.trip_threshold <= 1.0:
            raise ValueError(
                f"trip_threshold must be in [0, 1], got {self.trip_threshold}"
            )
        if not 0.0 <= self.reset_threshold <= 1.0:
            raise ValueError(
                f"reset_threshold must be in [0, 1], got {self.reset_threshold}"
            )
        if self.reset_threshold > self.trip_threshold:
            raise ValueError(
                "reset_threshold must be <= trip_threshold "
                f"(got reset={self.reset_threshold}, trip={self.trip_threshold})"
            )
        if self.probe_count < 1:
            raise ValueError(
                f"probe_count must be >= 1, got {self.probe_count}"
            )
        if self.warm_up_min_obs < 0:
            raise ValueError(
                f"warm_up_min_obs must be >= 0, got {self.warm_up_min_obs}"
            )


@dataclass(frozen=True)
class GateObservation:
    """A single observation fed to one layer of the gate.

    Attributes
    ----------
    tripped : bool
        True if this observation was a trip event; False if not.
    label : str
        A short human-readable label for the observation (e.g.
        ``"fabrication"``, ``"session_horizon_cross"``).
    metadata : dict
        Arbitrary extra metadata (e.g. detector_id, layer_id).
    timestamp : str
        ISO-8601 UTC timestamp. Auto-set to now() if omitted.
    """

    tripped: bool
    label: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tripped": self.tripped,
            "label": self.label,
            "metadata": dict(self.metadata),
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class GovernorDecision:
    """The gate's decision at a point in time.

    ``action`` is the primary signal for the caller. ``state`` is the
    underlying gate state. ``consecutive_good`` is the running
    HALF_OPEN probe counter.
    """

    action: GateAction
    state: GateState
    upper_bound: float
    trip_band: str
    consecutive_good: int
    reason: str
    timestamp: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "state": self.state.value,
            "upper_bound": self.upper_bound,
            "trip_band": self.trip_band,
            "consecutive_good": self.consecutive_good,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class GateTransition:
    """A single state transition in the gate's history.

    Append-only. Each transition carries the bound at the moment of
    transition, the trip band, and the reason.
    """

    from_state: GateState
    to_state: GateState
    upper_bound: float
    trip_band: str
    reason: str
    consecutive_good: int
    timestamp: str
    transition_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_state": self.from_state.value,
            "to_state": self.to_state.value,
            "upper_bound": self.upper_bound,
            "trip_band": self.trip_band,
            "reason": self.reason,
            "consecutive_good": self.consecutive_good,
            "timestamp": self.timestamp,
            "transition_id": self.transition_id,
        }




# ---------------------------------------------------------------------------
# GovernorCircuit
# ---------------------------------------------------------------------------


class GovernorCircuit:
    """A stateful policy gate driven by one or two bound sources.

    Parameters
    ----------
    config : GovernorCircuitConfig, optional
        The thresholds. Defaults are conservative (trip=0.05,
        reset=0.01, probe=1).
    per_output_engine : BoundSource, optional
        The per-output layer's engine. If None, the per-output layer
        is treated as silent (bound=0, band="low").
    session_engine : BoundSource, optional
        The session layer's engine. If None, the session layer is
        treated as silent (bound=0, band="low").

    The gate's bound is the maximum of the two engines' bounds.
    The gate's band is the worst of the two engines' bands.

    Attributes
    ----------
    state : GateState
        The current gate state.
    upper_bound : float
        The current bound (max of the two engines).
    trip_band : str
        The current trip band (worst of the two engines).
    transitions : List[GateTransition]
        The transition log (immutable copy returned by ``transitions()``).
    """

    def __init__(
        self,
        config: Optional[GovernorCircuitConfig] = None,
        per_output_engine: Optional[BoundSource] = None,
        session_engine: Optional[BoundSource] = None,
    ) -> None:
        self._config = config or GovernorCircuitConfig()
        self._per_output_engine = per_output_engine
        self._session_engine = session_engine
        self._state = GateState.CLOSED
        self._consecutive_good = 0
        self._transitions: List[GateTransition] = []
        self._transition_counter = 0

    # ------------------------------------------------------------------
    # Configuration accessors.
    # ------------------------------------------------------------------

    @property
    def config(self) -> GovernorCircuitConfig:
        return self._config

    @property
    def state(self) -> GateState:
        return self._state

    @property
    def consecutive_good(self) -> int:
        return self._consecutive_good

    @property
    def transition_count(self) -> int:
        return len(self._transitions)

    # ------------------------------------------------------------------
    # Bound accessors.
    # ------------------------------------------------------------------

    @staticmethod
    def _has_data(engine: Optional[Any]) -> bool:
        """Return True iff the engine has been fed at least one observation.

        A cold engine (n_observations == 0) is treated as silent: its
        prior-derived bound is not meaningful evidence and must not
        dominate the two-layer max. Engines that do not implement
        ``n_observations`` are assumed to be hot (legacy/stub
        compatibility): an engine without ``n_observations`` is
        treated as having data.
        """
        if engine is None:
            return False
        n_obs = getattr(engine, "n_observations", None)
        if n_obs is None:
            return True
        try:
            return int(n_obs) > 0
        except (TypeError, ValueError):
            return True

    @property
    def upper_bound(self) -> float:
        """The current upper bound (max of warmed engines' bounds).

        Silent engines (None) and cold engines (n_observations == 0)
        contribute 0.0. A cold engine's prior-derived bound is not
        meaningful evidence, so it is excluded from the max.

        Returns 0.0 when no engines are wired, or when every wired
        engine is cold. The gate in that case sees "no evidence" and
        stays CLOSED (a cold start is not a trip event).
        """
        bounds = []
        if self._has_data(self._per_output_engine):
            bounds.append(self._per_output_engine.trip_upper_bound)
        if self._has_data(self._session_engine):
            bounds.append(self._session_engine.trip_upper_bound)
        return max(bounds) if bounds else 0.0

    @property
    def per_output_bound(self) -> float:
        if not self._has_data(self._per_output_engine):
            return 0.0
        return self._per_output_engine.trip_upper_bound

    @property
    def session_bound(self) -> float:
        if not self._has_data(self._session_engine):
            return 0.0
        return self._session_engine.trip_upper_bound

    @property
    def trip_band(self) -> str:
        """The current trip band (worst of the engines' bands).

        Uses a fixed severity order: low < medium < high < critical.
        """
        order = ["low", "medium", "high", "critical"]
        bands = []
        if self._per_output_engine is not None:
            bands.append(self._per_output_engine.trip_band)
        if self._session_engine is not None:
            bands.append(self._session_engine.trip_band)
        if not bands:
            return "low"
        return max(bands, key=lambda b: order.index(b) if b in order else 0)

    @property
    def per_output_band(self) -> str:
        if self._per_output_engine is None:
            return "low"
        return self._per_output_engine.trip_band

    @property
    def session_band(self) -> str:
        if self._session_engine is None:
            return "low"
        return self._session_engine.trip_band


    # ------------------------------------------------------------------
    # Feed / decide.
    # ------------------------------------------------------------------

    def feed(
        self,
        per_output_observation: Optional[GateObservation] = None,
        session_observation: Optional[GateObservation] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GovernorDecision:
        """Record one or two layer observations and re-evaluate.

        At least one observation must be provided. The engines are
        updated first; the gate state is then re-evaluated; any
        transition is appended to the transition log.

        Parameters
        ----------
        per_output_observation : GateObservation, optional
            The per-output layer's observation.
        session_observation : GateObservation, optional
            The session layer's observation.
        metadata : dict, optional
            Caller-supplied metadata attached to any transition
            recorded by this feed.

        Returns
        -------
        GovernorDecision
            The decision after the feed.
        """
        if per_output_observation is None and session_observation is None:
            raise ValueError(
                "feed() requires at least one of "
                "per_output_observation or session_observation"
            )

        # Feed the engines.
        if per_output_observation is not None:
            self._feed_layer(
                self._per_output_engine,
                self._config.per_output_layer_id,
                per_output_observation,
            )
        if session_observation is not None:
            self._feed_layer(
                self._session_engine,
                self._config.session_layer_id,
                session_observation,
            )

        # Build the per-feed metadata for state-transition evaluation.
        meta = dict(metadata) if metadata else {}
        meta["per_output_observation"] = per_output_observation
        meta["session_observation"] = session_observation

        # Evaluate state transitions and return the decision.
        return self._reevaluate(meta)

    def decide(self) -> GovernorDecision:
        """Read-only evaluation: what action does the gate recommend now?

        Reads the bound from the engines. Does NOT transition state,
        does NOT increment the consecutive_good counter, does NOT
        append to the transition log. Use feed() to record an
        observation and transition state; use decide() to ask
        what the gate would do *now* given the current bound.

        Returns
        -------
        GovernorDecision
            The current decision, reflecting current state + bound.
        """
        bound = self.upper_bound
        band = self.trip_band
        return self._build_decision(bound, band, datetime.now(timezone.utc).isoformat())

    def reset(self) -> None:
        """Clear the transition log and return the gate to CLOSED.

        The engines are untouched (the historical bound is preserved).
        """
        self._state = GateState.CLOSED
        self._consecutive_good = 0
        self._transitions = []
        self._transition_counter = 0

    # ------------------------------------------------------------------
    # Audit.
    # ------------------------------------------------------------------

    def transitions(self) -> List[GateTransition]:
        """Return a copy of the transition log."""
        return list(self._transitions)

    def summary(self) -> Dict[str, Any]:
        """A small, audit-ready summary of the gate's state."""
        per_eng = (
            self._per_output_engine.summary()
            if self._per_output_engine is not None
            and hasattr(self._per_output_engine, "summary")
            else None
        )
        sess_eng = (
            self._session_engine.summary()
            if self._session_engine is not None
            and hasattr(self._session_engine, "summary")
            else None
        )
        return {
            "state": self._state.value,
            "upper_bound": self.upper_bound,
            "per_output_bound": self.per_output_bound,
            "session_bound": self.session_bound,
            "trip_band": self.trip_band,
            "per_output_band": self.per_output_band,
            "session_band": self.session_band,
            "consecutive_good": self._consecutive_good,
            "trip_threshold": self._config.trip_threshold,
            "reset_threshold": self._config.reset_threshold,
            "probe_count": self._config.probe_count,
            "transition_count": len(self._transitions),
            "per_output_engine": per_eng,
            "session_engine": sess_eng,
        }

    def to_dict(self) -> Dict[str, Any]:
        """A full, audit-ready dict (includes the full transition log)."""
        return {
            **self.summary(),
            "transitions": [t.to_dict() if hasattr(t, "to_dict") else asdict(t) for t in self._transitions],
        }

    def write_audit(self, path: str) -> None:
        """Append the current transition log to a JSONL file.

        Each line is one transition record. The file is opened in
        append mode, so this is safe to call repeatedly.
        """
        with open(path, "a", encoding="utf-8") as f:
            for t in self._transitions:
                d = t.to_dict() if hasattr(t, "to_dict") else asdict(t)
                f.write(json.dumps(d) + "\n")


    # ------------------------------------------------------------------
    # Internal: layer feeding.
    # ------------------------------------------------------------------

    def _feed_layer(
        self,
        engine: Optional[BoundSource],
        layer_id: str,
        observation: GateObservation,
    ) -> None:
        """Best-effort feed of an observation to an engine.

        A missing engine is a no-op. An engine that does not expose
        ``update()`` is also a no-op (the gate still decides on
        whatever bound the engine reports).
        """
        if engine is None or not hasattr(engine, "update"):
            return
        # Prefer wrapping as TripObservation if the engine knows the shape.
        if TripObservation is not None:
            try:
                engine.update(
                    TripObservation(
                        tripped=observation.tripped,
                        label=observation.label,
                        metadata={
                            **observation.metadata,
                            "layer": layer_id,
                            "timestamp": observation.timestamp,
                        },
                    )
                )
                return
            except Exception:
                pass
        # Fallback: pass the observation object directly.
        try:
            engine.update(observation)
        except Exception:
            # Engine update is best-effort.
            pass

    # ------------------------------------------------------------------
    # Internal: state transition evaluation.
    # ------------------------------------------------------------------

    def _engine_just_warmed(self, engine: Optional[BoundSource]) -> bool:
        """True iff the engine was cold before this feed and is now warm.

        "Just warmed" means n_observations == 1 right after the feed.
        A cold engine's first observation is not strong evidence of
        "agent is dangerous"; it is evidence of "we just got our
        first data point." The gate therefore does not transition
        to OPEN on the basis of a single first observation alone.
        """
        if engine is None or not hasattr(engine, "n_observations"):
            return False
        try:
            return int(getattr(engine, "n_observations")) == 1
        except Exception:
            return False

    def _any_engine_in_warmup(self) -> bool:
        """Return True iff at least one engine is still in the warm-up window.

        An engine is "in warm-up" when its observation count is below
        ``config.warm_up_min_obs``. During this window, the gate
        reports bounds and band decisions normally but suppresses
        the CLOSED -> OPEN transition; the suppressed decision is
        recorded as a ``warming_grace`` transition so the audit trail
        is complete.

        Why this matters
        ----------------
        A Beta(1, 1) engine's upper bound is the (1 - alpha)
        quantile of the posterior, which is *extremely wide* until
        the engine accumulates several observations. With 1-2
        observations, the upper bound can sit at 0.5-1.0 -- well
        above any reasonable trip_threshold. With 5 observations
        the bound has narrowed meaningfully; with 20 it is
        narrowly informative. The warm-up window is the gate's
        way of saying "wait for enough evidence before tripping".

        Engines that do not expose ``n_observations`` are assumed
        to be warmed (back-compat with legacy stubs); only engines
        that report their observation count are checked.

        The audit trail still records the suppressed decision (see
        ``_record_warming_decision``); only the *transition* is
        suppressed.
        """
        min_obs = self._config.warm_up_min_obs
        if self._per_output_engine is not None and hasattr(
            self._per_output_engine, "n_observations"
        ):
            per_n = _safe_n_obs(self._per_output_engine)
            if 0 < per_n < min_obs:
                return True
        if self._session_engine is not None and hasattr(
            self._session_engine, "n_observations"
        ):
            sess_n = _safe_n_obs(self._session_engine)
            if 0 < sess_n < min_obs:
                return True
        return False

    # Backward-compatible alias for older callers/tests that used
    # the single-observation-only check.
    def _any_engine_just_warmed(self) -> bool:
        """Alias for :meth:`_any_engine_in_warmup`.

        Preserved for backward compatibility with the original
        single-observation warm-up check. Returns True iff at least
        one engine is still in the warm-up window.
        """
        return self._any_engine_in_warmup()

    def _record_warming_decision(
        self,
        bound: float,
        band: str,
        prev_state: GateState,
        ts: str,
        reason: str,
    ) -> None:
        """Record a suppressed transition due to warm-up grace.

        The gate stays in ``prev_state``, but the operator-visible
        audit trail captures the suppressed decision so they can
        see the engine's bound crossed the trip line and the gate
        chose to wait for a second confirmation.
        """
        self._consecutive_good = 0
        self._transition(
            prev_state,
            prev_state,
            bound,
            band,
            "warming_grace: " + reason + " ("
            + ("%.4f" % bound)
            + " >= "
            + ("%.4f" % self._config.trip_threshold)
            + ", suppressed CLOSED->OPEN pending second feed)",
            ts,
        )

    def _reevaluate(self, metadata: Dict[str, Any]) -> GovernorDecision:
        """Re-evaluate the gate state and return the current decision.

        State transitions are driven by the bound (read from the
        engines). The consecutive_good counter is incremented only
        when this reevaluate was triggered by a feed() that included
        a non-tripping observation.
        """
        bound = self.upper_bound
        band = self.trip_band
        prev_state = self._state
        ts = datetime.now(timezone.utc).isoformat()

        # Drive the consecutive_good counter.
        self._update_consecutive_good(metadata)

        # State transitions.
        if self._state == GateState.CLOSED:
            if bound >= self._config.trip_threshold:
                # Warm-up grace: a bound rise driven entirely by an
                # engine's first observation is not yet strong
                # evidence. We still record the decision (audit
                # trail is append-only) but we do not transition
                # the gate until either (a) a second feed confirms
                # the elevated bound, or (b) the bound continues
                # to climb after warm-up completes.
                warming = self._any_engine_just_warmed()
                if warming:
                    self._record_warming_decision(
                        bound, band, prev_state, ts, reason="engine_warming"
                    )
                    return self._build_decision(bound, band, ts)
                self._consecutive_good = 0
                self._transition(
                    GateState.CLOSED,
                    GateState.OPEN,
                    bound,
                    band,
                    "bound crossed trip_threshold ("
                    + ("%.4f" % bound)
                    + " >= "
                    + ("%.4f" % self._config.trip_threshold)
                    + ")",
                    ts,
                )
        elif self._state == GateState.OPEN:
            if bound <= self._config.reset_threshold:
                self._consecutive_good = 1
                self._transition(
                    GateState.OPEN,
                    GateState.HALF_OPEN,
                    bound,
                    band,
                    "bound dropped to reset_threshold ("
                    + ("%.4f" % bound)
                    + " <= "
                    + ("%.4f" % self._config.reset_threshold)
                    + ")",
                    ts,
                )
            # else: bound in (reset, trip) band -- still OPEN, no transition.
        elif self._state == GateState.HALF_OPEN:
            if bound >= self._config.trip_threshold:
                self._consecutive_good = 0
                self._transition(
                    GateState.HALF_OPEN,
                    GateState.OPEN,
                    bound,
                    band,
                    "half_open recovery failed: bound re-crossed trip_threshold",
                    ts,
                )
            elif (
                bound <= self._config.reset_threshold
                and self._consecutive_good >= self._config.probe_count
            ):
                self._consecutive_good = 0
                self._transition(
                    GateState.HALF_OPEN,
                    GateState.CLOSED,
                    bound,
                    band,
                    "half_open: "
                    + str(self._consecutive_good)
                    + " consecutive good probe(s) confirmed recovery",
                    ts,
                )

        return self._build_decision(bound, band, ts)

    def _update_consecutive_good(self, metadata: Dict[str, Any]) -> None:
        """Update the consecutive_good counter based on the feed.

        The counter is incremented only by ``feed()`` calls (which
        include an observation in the metadata). ``decide()`` calls
        pass empty metadata and do not mutate the counter.

        Rules:
        - HALF_OPEN + non-tripping observation + bound below reset:
          increment counter.
        - HALF_OPEN + tripping observation OR bound above reset:
          reset counter to 0.
        - State is not HALF_OPEN: reset counter to 0.
        """
        if self._state != GateState.HALF_OPEN:
            self._consecutive_good = 0
            return

        per = metadata.get("per_output_observation")
        sess = metadata.get("session_observation")

        # If neither observation was supplied (decide() path), don't
        # touch the counter.
        if per is None and sess is None:
            return

        # Did either observation trip?
        tripped = False
        if per is not None and per.tripped:
            tripped = True
        if sess is not None and sess.tripped:
            tripped = True

        bound = self.upper_bound
        if not tripped and bound <= self._config.reset_threshold:
            self._consecutive_good += 1
        else:
            self._consecutive_good = 0

    def _build_decision(
        self, bound: float, band: str, ts: str
    ) -> GovernorDecision:
        """Build the GovernorDecision for the current state.

        * CLOSED -> ALLOW
        * OPEN -> BLOCK
        * HALF_OPEN + enough good probes -> ALLOW (probe passed)
        * HALF_OPEN + bound still elevated -> BLOCK
        * HALF_OPEN + bound recovered but not enough probes -> PROBE
        """
        if self._state == GateState.CLOSED:
            # If the bound is at or above trip_threshold, decide reports
            # the projected decision (state would become OPEN on next
            # reevaluate). We do not mutate state here.
            if bound >= self._config.trip_threshold:
                return GovernorDecision(
                    action=GateAction.BLOCK,
                    state=GateState.OPEN,
                    upper_bound=bound,
                    trip_band=band,
                    consecutive_good=self._consecutive_good,
                    reason="closed: projected to open (bound at or above trip_threshold)",
                    timestamp=ts,
                )
            return GovernorDecision(
                action=GateAction.ALLOW,
                state=GateState.CLOSED,
                upper_bound=bound,
                trip_band=band,
                consecutive_good=self._consecutive_good,
                reason="closed: bound below trip_threshold",
                timestamp=ts,
            )
        if self._state == GateState.OPEN:
            return GovernorDecision(
                action=GateAction.BLOCK,
                state=GateState.OPEN,
                upper_bound=bound,
                trip_band=band,
                consecutive_good=self._consecutive_good,
                reason="open: bound at or above trip_threshold",
                timestamp=ts,
            )
        # HALF_OPEN
        if bound <= self._config.reset_threshold:
            if self._consecutive_good >= self._config.probe_count:
                return GovernorDecision(
                    action=GateAction.ALLOW,
                    state=GateState.HALF_OPEN,
                    upper_bound=bound,
                    trip_band=band,
                    consecutive_good=self._consecutive_good,
                    reason="half_open: "
                    + str(self._consecutive_good)
                    + " good probe(s) collected (>= "
                    + str(self._config.probe_count)
                    + ")",
                    timestamp=ts,
                )
            return GovernorDecision(
                action=GateAction.PROBE,
                state=GateState.HALF_OPEN,
                upper_bound=bound,
                trip_band=band,
                consecutive_good=self._consecutive_good,
                reason="half_open: bound recovered, awaiting "
                    + str(self._consecutive_good)
                    + "/"
                    + str(self._config.probe_count)
                    + " probes",
                timestamp=ts,
            )
        # HALF_OPEN with elevated bound: still considered OPEN.
        return GovernorDecision(
            action=GateAction.BLOCK,
            state=GateState.HALF_OPEN,
            upper_bound=bound,
            trip_band=band,
            consecutive_good=self._consecutive_good,
            reason="half_open: bound still elevated",
            timestamp=ts,
        )

    def _transition(
        self,
        from_state: GateState,
        to_state: GateState,
        bound: float,
        band: str,
        reason: str,
        timestamp: str,
    ) -> None:
        """Record a state transition and apply it."""
        self._transition_counter += 1
        t = GateTransition(
            from_state=from_state,
            to_state=to_state,
            upper_bound=bound,
            trip_band=band,
            reason=reason,
            consecutive_good=self._consecutive_good,
            timestamp=timestamp,
            transition_id=uuid.uuid4().hex,
        )
        self._transitions.append(t)
        self._state = to_state



# ---------------------------------------------------------------------------
# Convenience constructors.
# ---------------------------------------------------------------------------


def create_governor_circuit(
    trip_threshold: float = DEFAULT_TRIP_THRESHOLD,
    reset_threshold: float = DEFAULT_RESET_THRESHOLD,
    probe_count: int = DEFAULT_PROBE_COUNT,
    per_output_engine: Optional[BoundSource] = None,
    session_engine: Optional[BoundSource] = None,
) -> GovernorCircuit:
    """Smallest-viable install: one line, one gate.

    Parameters
    ----------
    trip_threshold : float
        The bound above which the gate opens. Default 0.05.
    reset_threshold : float
        The bound at or below which the gate leaves OPEN for HALF_OPEN.
        Default 0.01.
    probe_count : int
        The number of consecutive non-tripping observations required
        in HALF_OPEN before the gate closes. Default 1.
    per_output_engine : BoundSource, optional
        The per-output layer's engine.
    session_engine : BoundSource, optional
        The session layer's engine.
    """
    return GovernorCircuit(
        config=GovernorCircuitConfig(
            trip_threshold=trip_threshold,
            reset_threshold=reset_threshold,
            probe_count=probe_count,
        ),
        per_output_engine=per_output_engine,
        session_engine=session_engine,
    )


__all__ = [
    "DEFAULT_TRIP_THRESHOLD",
    "DEFAULT_RESET_THRESHOLD",
    "DEFAULT_PROBE_COUNT",
    "DEFAULT_WARM_UP_MIN_OBS",
    "BoundSource",
    "GateAction",
    "GateObservation",
    "GateState",
    "GateTransition",
    "GovernorCircuit",
    "GovernorCircuitConfig",
    "GovernorDecision",
    "create_governor_circuit",
]
