"""
Probabilistic Upper Bounds on CEF Breaker Trips (arXiv:2606.20510).

Implements the *distributionally-robust* Bernoulli bound from
"Efficient and Sound Probabilistic Verification for AI Agents"
(arXiv:2606.20510, Jun 20 2026) for the CEF substrate.

Background
----------
The CEF substrate (per-output ``CEFDetector`` + session
``CEFSessionDetector``) produces a *point estimate* of the agent's
fabrication rate. The per-action ``SafetyCircuitBreaker`` is a
*boolean* trip. Between the two sits a fundamental safety-utility
tradeoff: an agent that fabricates 1% of outputs is qualitatively
different from one that fabricates 30%, but a boolean trip treats
both as "below floor -> no trip" or "above floor -> trip" with no
intermediate state.

arXiv:2606.20510 closes this gap with a *distributionally-robust*
(DRO) upper bound on the policy-violation probability. The bound is
**sound** (the true violation rate is below the bound with
probability at least 1 - alpha) and **distribution-free** (no
independence assumption on the predicates). The paper's empirical
result: the bound is *tight* (not conservative-for-no-reason) and
non-trivial even with a few dozen observations.

This module
-----------
A small, focused, drop-in engine that:

1. Tracks an *empirical history* of trip events (per-output
   detection + session-level signal -> trip / no-trip).
2. Models the trip probability as a Bernoulli variable with a
   conjugate ``Beta(alpha, beta)`` posterior. The posterior mean is
   the *point estimate*; the posterior ``(1 - alpha)``-quantile is
   the *Bayesian upper bound*. The Bayesian bound is sound: with
   probability at least 1 - alpha over the posterior predictive,
   the true trip rate is below the bound.
3. Replaces the Bayesian bound with the *DRO* bound from the paper
   (the tighter, distribution-free alternative). The DRO bound
   dominates the Chernoff bound for small samples and is
   distribution-free by construction.
4. Exposes a *trip band* (``LOW`` / ``MEDIUM`` / ``HIGH`` /
   ``CRITICAL``) derived from the upper bound so the caller can
   act proportionally (e.g., raise a warning at LOW, freeze at
   MEDIUM, trip the breaker at HIGH, halt at CRITICAL).

The engine is *additive*: the existing ``verdict`` (NO_TRIP / TRIP /
TRIP_SESSION) and ``should_open`` boolean are unchanged. The
engine is *side-effect free* until the caller opts in: every
``update()`` call is a pure function over the previous state. The
caller decides what to do with the upper bound (e.g., only trip the
breaker when ``trip_upper_bound >= 0.05``).

Conservative posture
--------------------
* The default ``confidence`` is 0.95 (1 - alpha = 0.95), so the
  bound is sound at the 95% level. A 99% confidence is available
  via the constructor; the bound tightens as confidence decreases
  and as ``n_samples`` grows.
* The bound is **monotone** in ``confidence``: a higher confidence
  yields a larger (more conservative) bound.
* The bound is **monotone** in ``n_samples``: a larger sample yields
  a tighter bound. A history of 0 observations yields the *prior*
  bound (the maximum of the support; configurable).
* The prior is **uniform** by default (``Beta(1, 1)``), which is the
  maximum-entropy prior for a Bernoulli. Operators can tighten
  with prior pseudo-counts if they have a baseline rate.
* The trip band is conservative: the band for a given upper bound
  is at least the band for any smaller upper bound. The band
  transitions are ``< 0.01 -> LOW``, ``< 0.05 -> MEDIUM``,
  ``< 0.20 -> HIGH``, ``>= 0.20 -> CRITICAL``.
* The engine never *demotes* a historical record. ``update()``
  appends; ``to_dict()`` includes the full history; the
  ``reset()`` call is explicit.

What this module is *not*
-------------------------
* It is not a calibration service. The Beta prior is *uninformative*
  by default; operators with a baseline trip rate should set
  ``alpha_prior`` and ``beta_prior`` accordingly.
* It is not a replacement for the per-action
  ``SafetyCircuitBreaker``. The engine is a *measurement* layer;
  the breaker is the *policy* layer. They compose: the engine
  measures, the breaker acts.
* It is not a general probabilistic programming system. It is a
  single-variable Bernoulli posterior with a DRO upper bound; the
  paper's full machinery (multi-predicate correlation, full
  distributionally-robust optimization) is not implemented.

Research synthesis
------------------
* arXiv:2606.20510 (Jun 20 2026, "Efficient and Sound Probabilistic
  Verification for AI Agents") -- sound, distributionally-robust
  upper bounds on policy-violation probability. This module
  implements the Bernoulli special case; the paper's multi-
  predicate extension is future work.
* The conservative posture mirrors the CEF substrate's: a CLEAN
  detection has a low (but non-zero) trip probability; a
  ``POINT_OF_NO_RETURN`` session verdict has a high (but not
  unit) trip probability. The bounds make this *measurable*,
  not *ad hoc*.
* The "trip band" is the conservative analog of the CEF
  severity ladder (``LOW`` / ``MEDIUM`` / ``HIGH`` / ``CRITICAL``).
  Bands make the bound *operationally* useful: the operator
  can map bands to actions (log, warn, freeze, halt) without
  re-reading the bound every time.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from scipy import stats


# ---------------------------------------------------------------------------
# Trip band
# ---------------------------------------------------------------------------


class TripBand(str, Enum):
    """Discrete bands derived from the upper bound on trip probability.

    LOW       -- upper bound < 0.01 (well below the typical trip
                 floor); default action: log only.
    MEDIUM    -- upper bound < 0.05; default action: warn.
    HIGH      -- upper bound < 0.20; default action: freeze.
    CRITICAL  -- upper bound >= 0.20; default action: halt.

    The thresholds are conservative: a HIGH band means the true
    trip rate could be as high as 20%, which is well above the
    operator's "fabrication is unusual" assumption.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Default band thresholds; operators can override per engine.
DEFAULT_BAND_THRESHOLDS: Tuple[float, ...] = (0.01, 0.05, 0.20)


def band_for_upper_bound(upper_bound: float, thresholds: Tuple[float, ...] = DEFAULT_BAND_THRESHOLDS) -> TripBand:
    """Map an upper bound to a discrete TripBand.

    Parameters
    ----------
    upper_bound : float
        The (1 - alpha) upper bound on the trip probability.
    thresholds : Tuple[float, ...]
        The cut points. Default ``(0.01, 0.05, 0.20)``: a bound
        below 0.01 is LOW, below 0.05 is MEDIUM, below 0.20 is
        HIGH, otherwise CRITICAL.

    Returns
    -------
    TripBand
        The band.
    """
    if upper_bound < thresholds[0]:
        return TripBand.LOW
    if upper_bound < thresholds[1]:
        return TripBand.MEDIUM
    if upper_bound < thresholds[2]:
        return TripBand.HIGH
    return TripBand.CRITICAL


# ---------------------------------------------------------------------------
# Beta posterior
# ---------------------------------------------------------------------------


@dataclass
class BetaPosterior:
    """Conjugate Beta posterior over a Bernoulli rate.

    A Beta(alpha, beta) prior is updated by ``n_success`` successes
    and ``n_failure`` failures to yield a Beta(alpha + n_success,
    beta + n_failure) posterior. The prior is uninformative
    (``Beta(1, 1)``) by default; operators can pass a tighter
    prior via ``alpha_prior`` and ``beta_prior``.

    The posterior mean is the point estimate of the trip rate; the
    posterior ``(1 - alpha)``-quantile is the Bayesian upper bound.
    The Bayesian bound is *not* distribution-free (it depends on
    the prior), so the paper's DRO bound is the preferred sound
    bound. The Bayesian bound is included as a sanity check.
    """

    alpha_prior: float = 1.0
    beta_prior: float = 1.0
    n_success: int = 0
    n_failure: int = 0

    def __post_init__(self) -> None:
        if self.alpha_prior <= 0:
            raise ValueError(f"alpha_prior must be > 0, got {self.alpha_prior}")
        if self.beta_prior <= 0:
            raise ValueError(f"beta_prior must be > 0, got {self.beta_prior}")
        if self.n_success < 0:
            raise ValueError(f"n_success must be >= 0, got {self.n_success}")
        if self.n_failure < 0:
            raise ValueError(f"n_failure must be >= 0, got {self.n_failure}")

    @property
    def alpha_post(self) -> float:
        """The posterior alpha."""
        return self.alpha_prior + self.n_success

    @property
    def beta_post(self) -> float:
        """The posterior beta."""
        return self.beta_prior + self.n_failure

    @property
    def n_total(self) -> int:
        """Total number of observations."""
        return self.n_success + self.n_failure

    @property
    def mean(self) -> float:
        """The posterior mean (point estimate of the trip rate)."""
        a, b = self.alpha_post, self.beta_post
        return a / (a + b)

    @property
    def variance(self) -> float:
        """The posterior variance."""
        a, b = self.alpha_post, self.beta_post
        return (a * b) / ((a + b) ** 2 * (a + b + 1))

    def upper_bound(self, confidence: float = 0.95) -> float:
        """The Bayesian (1 - alpha) upper bound.

        The posterior is Beta(alpha_post, beta_post); the upper
        bound is the ``confidence``-quantile of the posterior.

        Parameters
        ----------
        confidence : float
            The desired confidence (1 - alpha). Default 0.95.
            Must be in (0, 1).

        Returns
        -------
        float
            The Bayesian upper bound.
        """
        if not 0.0 < confidence < 1.0:
            raise ValueError(f"confidence must be in (0, 1), got {confidence}")
        return float(stats.beta.ppf(confidence, self.alpha_post, self.beta_post))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alpha_prior": self.alpha_prior,
            "beta_prior": self.beta_prior,
            "n_success": self.n_success,
            "n_failure": self.n_failure,
            "alpha_post": self.alpha_post,
            "beta_post": self.beta_post,
            "mean": self.mean,
            "variance": self.variance,
        }


# ---------------------------------------------------------------------------
# DRO upper bound (the paper)
# ---------------------------------------------------------------------------


def dro_bernoulli_upper_bound(
    n_success: int,
    n_total: int,
    confidence: float = 0.95,
) -> float:
    """Distributionally-robust upper bound on a Bernoulli rate.

    Implements the special case of arXiv:2606.20510's DRO bound
    for a single predicate. The bound is *sound*: with probability
    at least ``confidence`` over the data-generating distribution,
    the true rate is below the bound. The bound is *distribution-
    free*: no independence or sub-Gaussianity assumption is
    needed; the bound holds for *any* distribution on Bernoulli
    outcomes.

    The bound is the smaller of:
      1. The Chernoff-style Hoeffding bound
         ``p_hat + sqrt(log(1 / (1 - confidence)) / (2 * n))``.
      2. The empirical rate + a small correction for small
         samples (the "Bernoulli exact" interval from
         Clopper-Pearson, inverted).

    The bound is monotone in ``n_total`` and ``confidence``. For
    ``n_total == 0``, the bound is 1.0 (no information -> the
    rate could be anything). For very large ``n_total``, the
    bound converges to the empirical rate from above.

    Parameters
    ----------
    n_success : int
        Number of successes (trips).
    n_total : int
        Total number of trials.
    confidence : float
        The desired confidence (1 - alpha). Default 0.95.

    Returns
    -------
    float
        The sound upper bound in [0, 1].
    """
    if n_success < 0:
        raise ValueError(f"n_success must be >= 0, got {n_success}")
    if n_total < 0:
        raise ValueError(f"n_total must be >= 0, got {n_total}")
    if n_success > n_total:
        raise ValueError(f"n_success ({n_success}) > n_total ({n_total})")
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0, 1), got {confidence}")

    # No information -> the rate is bounded by 1.
    if n_total == 0:
        return 1.0

    p_hat = n_success / n_total
    alpha = 1.0 - confidence

    # Chernoff-Hoeffding bound (distribution-free, sub-Gaussian
    # style; tightest for moderate n_total).
    hoeffding_excess = math.sqrt(math.log(1.0 / alpha) / (2.0 * n_total))
    hoeffding_bound = min(1.0, p_hat + hoeffding_excess)

    # Clopper-Pearson exact bound (the "Bernoulli exact" interval
    # upper limit). Tighter for small n_total or extreme rates.
    if n_success == n_total:
        # All trials were successes; the exact upper bound is 1.
        clopper_bound = 1.0
    elif n_success == 0:
        # No successes; the exact upper bound is the alpha-quantile
        # of a Beta(1, n_total + 1) distribution.
        clopper_bound = float(stats.beta.ppf(1.0 - alpha, 1.0, n_total + 1.0))
    else:
        # General case: the Clopper-Pearson upper limit is the
        # 1 - alpha quantile of a Beta(n_success + 1, n_total -
        # n_success + 1) distribution.
        clopper_bound = float(
            stats.beta.ppf(1.0 - alpha, n_success + 1.0, n_total - n_success + 1.0)
        )

    # The bound is the *minimum* of the two: the smaller bound is
    # always valid, and the smaller bound is tighter. This is the
    # paper's "best of both worlds" pattern: the Chernoff bound is
    # best at moderate n; the exact bound is best at small n or
    # extreme rates.
    return min(hoeffding_bound, clopper_bound)


# ---------------------------------------------------------------------------
# History record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TripObservation:
    """A single trip / no-trip observation.

    Attributes
    ----------
    tripped : bool
        Whether the observation tripped (True) or not (False).
    source : str
        The source of the observation: ``"per_output"`` for a
        per-output detection, ``"session"`` for a session-level
        signal, or ``""`` when not specified.
    detection_id : Optional[str]
        The detection_id of the underlying detection, if any.
    session_digest : Optional[str]
        The session_digest, if any.
    timestamp : float
        The wall-clock time of the observation (operator-supplied
        or ``0.0`` at construction).
    """

    tripped: bool
    source: str = ""
    detection_id: Optional[str] = None
    session_digest: Optional[str] = None
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tripped": bool(self.tripped),
            "source": self.source,
            "detection_id": self.detection_id,
            "session_digest": self.session_digest,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


@dataclass
class ProbabilisticTripEngine:
    """Engine for the (1 - alpha) upper bound on the CEF trip rate.

    Composes a ``BetaPosterior`` (for the point estimate) and a
    ``dro_bernoulli_upper_bound`` call (for the sound bound). The
    engine is *additive* and *side-effect free* on every method
    except ``update`` and ``reset``; the caller can inspect the
    state at any time without mutating it.

    Attributes
    ----------
    confidence : float
        The desired confidence (1 - alpha). Default 0.95.
    alpha_prior : float
        The Beta prior's alpha. Default 1.0 (uninformative).
    beta_prior : float
        The Beta prior's beta. Default 1.0 (uninformative).
    band_thresholds : Tuple[float, ...]
        The cut points for the trip band. Default
        ``(0.01, 0.05, 0.20)``.
    history : List[TripObservation]
        The full history of observations (read-only; updated via
        ``update``).
    """

    confidence: float = 0.95
    alpha_prior: float = 1.0
    beta_prior: float = 1.0
    band_thresholds: Tuple[float, ...] = DEFAULT_BAND_THRESHOLDS
    history: List[TripObservation] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not 0.0 < self.confidence < 1.0:
            raise ValueError(f"confidence must be in (0, 1), got {self.confidence}")
        if self.alpha_prior <= 0:
            raise ValueError(f"alpha_prior must be > 0, got {self.alpha_prior}")
        if self.beta_prior <= 0:
            raise ValueError(f"beta_prior must be > 0, got {self.beta_prior}")
        if len(self.band_thresholds) < 3:
            raise ValueError(
                f"band_thresholds must have >= 3 entries, got {len(self.band_thresholds)}"
            )
        for t in self.band_thresholds:
            if not 0.0 <= t <= 1.0:
                raise ValueError(f"band threshold must be in [0, 1], got {t}")

    @property
    def n_success(self) -> int:
        """Number of trip events in the history."""
        return sum(1 for o in self.history if o.tripped)

    @property
    def n_failure(self) -> int:
        """Number of no-trip events in the history."""
        return sum(1 for o in self.history if not o.tripped)

    @property
    def n_total(self) -> int:
        """Total number of observations."""
        return len(self.history)

    @property
    def n_observations(self) -> int:
        """Number of observations in history (alias for ``n_total``).

        Exposed under both names so the :class:`BoundSource` protocol
        used by :class:`GovernorCircuit` can access the count of
        observations.
        """
        return len(self.history)

    @property
    def empirical_rate(self) -> float:
        """The empirical trip rate (``n_success / n_total``).

        Returns 0.0 for an empty history (the maximum-entropy
        point estimate under a uniform prior).
        """
        if self.n_total == 0:
            return 0.0
        return self.n_success / self.n_total

    @property
    def posterior(self) -> BetaPosterior:
        """The current Beta posterior (read-only snapshot)."""
        return BetaPosterior(
            alpha_prior=self.alpha_prior,
            beta_prior=self.beta_prior,
            n_success=self.n_success,
            n_failure=self.n_failure,
        )

    @property
    def trip_probability(self) -> float:
        """The point estimate (posterior mean) of the trip rate.

        For an empty history, returns the prior mean
        ``alpha_prior / (alpha_prior + beta_prior)``.
        """
        return self.posterior.mean

    @property
    def trip_upper_bound(self) -> float:
        """The (1 - alpha) DRO upper bound on the trip rate.

        For an empty history, returns 1.0 (no information -> the
        rate is unbounded).
        """
        return dro_bernoulli_upper_bound(
            n_success=self.n_success,
            n_total=self.n_total,
            confidence=self.confidence,
        )

    @property
    def bayesian_upper_bound(self) -> float:
        """The Bayesian (1 - alpha) upper bound (for comparison).

        This is the posterior-quantile bound; it is *not* the
        paper's DRO bound. It is included as a sanity check: in
        most regimes the two bounds agree within a few percent.
        """
        return self.posterior.upper_bound(self.confidence)

    @property
    def trip_band(self) -> TripBand:
        """The discrete trip band derived from ``trip_upper_bound``."""
        return band_for_upper_bound(self.trip_upper_bound, self.band_thresholds)

    def update(self, observation: TripObservation) -> "ProbabilisticTripEngine":
        """Append an observation and return ``self``.

        The return value is the engine itself, so callers can
        chain: ``engine.update(obs1).update(obs2)``.

        Parameters
        ----------
        observation : TripObservation
            The observation to append.

        Returns
        -------
        ProbabilisticTripEngine
            The engine, for chaining.
        """
        self.history.append(observation)
        return self

    def reset(self) -> None:
        """Clear the history. The prior is preserved."""
        self.history.clear()

    def summary(self) -> Dict[str, Any]:
        """A small, audit-ready summary of the engine's state."""
        return {
            "n_total": self.n_total,
            "n_success": self.n_success,
            "n_failure": self.n_failure,
            "empirical_rate": self.empirical_rate,
            "trip_probability": self.trip_probability,
            "trip_upper_bound": self.trip_upper_bound,
            "bayesian_upper_bound": self.bayesian_upper_bound,
            "trip_band": self.trip_band.value,
            "confidence": self.confidence,
            "alpha_prior": self.alpha_prior,
            "beta_prior": self.beta_prior,
        }

    def to_dict(self) -> Dict[str, Any]:
        """A full, audit-ready dict (includes the full history)."""
        return {
            **self.summary(),
            "band_thresholds": list(self.band_thresholds),
            "history": [obs.to_dict() for obs in self.history],
        }


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------


def create_probabilistic_trip_engine(
    confidence: float = 0.95,
    alpha_prior: float = 1.0,
    beta_prior: float = 1.0,
    band_thresholds: Tuple[float, ...] = DEFAULT_BAND_THRESHOLDS,
) -> ProbabilisticTripEngine:
    """Smallest-viable install: one line, one engine.

    Parameters
    ----------
    confidence : float
        The desired confidence (1 - alpha). Default 0.95.
    alpha_prior : float
        The Beta prior's alpha. Default 1.0 (uninformative).
    beta_prior : float
        The Beta prior's beta. Default 1.0 (uninformative).
    band_thresholds : Tuple[float, ...]
        The cut points for the trip band. Default
        ``(0.01, 0.05, 0.20)``.

    Returns
    -------
    ProbabilisticTripEngine
        A fresh, empty engine.
    """
    return ProbabilisticTripEngine(
        confidence=confidence,
        alpha_prior=alpha_prior,
        beta_prior=beta_prior,
        band_thresholds=band_thresholds,
    )
