"""Tests for the CEF probabilistic verification substrate (arXiv:2606.20510).

Covers:
- BetaPosterior: construction, validation, posterior moments, upper bound
- dro_bernoulli_upper_bound: validation, soundness vs n_total, Hoeffding
  vs Clopper-Pearson selection, edge cases (n=0, all-success, all-fail)
- TripBand: enum semantics, band_for_upper_bound thresholds, monotonicity
- TripObservation: construction, to_dict round-trip
- ProbabilisticTripEngine: construction, validation, update, history
  semantics, summary, to_dict, trip_probability / trip_upper_bound /
  trip_band properties, conservative posture (no demotion)
- CEFBreakerOutcome: probabilistic fields populated, no-engine defaults,
  engine-fed runs advance trip_probability / trip_upper_bound / trip_band
- create_probabilistic_trip_engine: convenience constructor
- Conservative posture: empty history -> critical (no info = assume worst);
  bands monotone in upper bound; engine never demotes historical records
"""

from __future__ import annotations

import unittest
from typing import List

from core.cef_probabilistic_verification import (
    DEFAULT_BAND_THRESHOLDS,
    BetaPosterior,
    ProbabilisticTripEngine,
    TripBand,
    TripObservation,
    band_for_upper_bound,
    create_probabilistic_trip_engine,
    dro_bernoulli_upper_bound,
)
from core.cef_substrate_integration import (
    CEFBreakerOutcome,
    CEFBreakerVerdict,
    CEFIntegrationConfig,
    assess_cef_to_breaker,
)
from core.cef_detector import (
    CEFAction,
    CEFDetection,
    CEFDetector,
    CEFDetectorConfig,
    CEFSeverity,
    CEFType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_clean_detection(detection_id: str = "d_clean") -> CEFDetection:
    """Build a CEFDetection with severity=CLEAN for use in tests."""
    return CEFDetection(
        detection_id=detection_id,
        cef_type=CEFType.NONE,
        severity=CEFSeverity.NONE,
        markers=[],
        recommended_action=CEFAction.NONE,
        confidence=0.0,
        rationale="clean",
        detected_at=0.0,
        output_length=0,
        output_hash="",
    )


def _make_critical_detection(detection_id: str = "d_critical") -> CEFDetection:
    """Build a CEFDetection with severity=CRITICAL for use in tests."""
    return CEFDetection(
        detection_id=detection_id,
        cef_type=CEFType.SIMULATED_CRASH,
        severity=CEFSeverity.CRITICAL,
        markers=[],
        recommended_action=CEFAction.ESCALATE,
        confidence=1.0,
        rationale="critical",
        detected_at=0.0,
        output_length=0,
        output_hash="",
    )


# ---------------------------------------------------------------------------
# BetaPosterior
# ---------------------------------------------------------------------------


class TestBetaPosterior(unittest.TestCase):
    """Tests for the conjugate Beta posterior."""

    def test_uniform_prior_mean_is_half(self) -> None:
        """Beta(1,1) has mean 0.5 and variance 1/12."""
        p = BetaPosterior()
        self.assertAlmostEqual(p.mean, 0.5)
        # Variance of Beta(1,1) = 1*1 / (4 * 3) = 1/12.
        self.assertAlmostEqual(p.variance, 1.0 / 12.0)

    def test_posterior_updates_with_observations(self) -> None:
        """After 3 success + 1 failure with uniform prior, posterior is
        Beta(4, 2), mean 2/3."""
        p = BetaPosterior(n_success=3, n_failure=1)
        self.assertAlmostEqual(p.alpha_post, 4.0)
        self.assertAlmostEqual(p.beta_post, 2.0)
        self.assertAlmostEqual(p.mean, 2.0 / 3.0)
        self.assertEqual(p.n_total, 4)

    def test_posterior_with_informative_prior(self) -> None:
        """A tight prior pulls the mean toward the prior's mean."""
        # Prior Beta(10, 10), mean 0.5; 0 observations -> mean 0.5.
        p = BetaPosterior(alpha_prior=10.0, beta_prior=10.0)
        self.assertAlmostEqual(p.mean, 0.5)
        # 100 successes -> mean (110 / 120) = 11/12.
        p2 = BetaPosterior(alpha_prior=10.0, beta_prior=10.0, n_success=100)
        self.assertAlmostEqual(p2.mean, 110.0 / 120.0)

    def test_upper_bound_quantile_monotone_in_confidence(self) -> None:
        """Higher confidence yields larger (more conservative) upper bound."""
        p = BetaPosterior(n_success=5, n_failure=5)
        ub_90 = p.upper_bound(confidence=0.90)
        ub_95 = p.upper_bound(confidence=0.95)
        ub_99 = p.upper_bound(confidence=0.99)
        self.assertLess(ub_90, ub_95)
        self.assertLess(ub_95, ub_99)
        # All bounds in (0.5, 1.0) for the symmetric case.
        self.assertGreater(ub_90, 0.5)
        self.assertLess(ub_99, 1.0)

    def test_upper_bound_validates_confidence(self) -> None:
        """Confidence outside (0, 1) raises ValueError."""
        p = BetaPosterior()
        with self.assertRaises(ValueError):
            p.upper_bound(confidence=0.0)
        with self.assertRaises(ValueError):
            p.upper_bound(confidence=1.0)
        with self.assertRaises(ValueError):
            p.upper_bound(confidence=-0.1)
        with self.assertRaises(ValueError):
            p.upper_bound(confidence=1.5)

    def test_validates_prior_parameters(self) -> None:
        """Negative or zero alpha/beta raises ValueError."""
        with self.assertRaises(ValueError):
            BetaPosterior(alpha_prior=0.0)
        with self.assertRaises(ValueError):
            BetaPosterior(beta_prior=-1.0)

    def test_validates_observation_counts(self) -> None:
        """Negative observation counts raise ValueError."""
        with self.assertRaises(ValueError):
            BetaPosterior(n_success=-1)
        with self.assertRaises(ValueError):
            BetaPosterior(n_failure=-1)

    def test_to_dict_round_trip(self) -> None:
        """to_dict exposes all post-state fields."""
        p = BetaPosterior(alpha_prior=2.0, beta_prior=3.0, n_success=5, n_failure=2)
        d = p.to_dict()
        self.assertEqual(d["alpha_prior"], 2.0)
        self.assertEqual(d["beta_prior"], 3.0)
        self.assertEqual(d["n_success"], 5)
        self.assertEqual(d["n_failure"], 2)
        self.assertEqual(d["alpha_post"], 7.0)
        self.assertEqual(d["beta_post"], 5.0)
        self.assertAlmostEqual(d["mean"], 7.0 / 12.0)
        self.assertIn("variance", d)


# ---------------------------------------------------------------------------
# dro_bernoulli_upper_bound
# ---------------------------------------------------------------------------


class TestDroUpperBound(unittest.TestCase):
    """Tests for the distributionally-robust Bernoulli upper bound."""

    def test_empty_history_is_one(self) -> None:
        """n_total == 0 yields bound = 1.0 (no information)."""
        self.assertEqual(dro_bernoulli_upper_bound(0, 0), 1.0)

    def test_all_failures_bound_is_small(self) -> None:
        """All-failures: bound is monotone in n_total (decreasing)."""
        b1 = dro_bernoulli_upper_bound(0, 1)
        b2 = dro_bernoulli_upper_bound(0, 10)
        b3 = dro_bernoulli_upper_bound(0, 100)
        self.assertGreater(b1, b2)
        self.assertGreater(b2, b3)
        self.assertLess(b3, 0.05)  # 0.05 = MEDIUM threshold

    def test_all_successes_bound_is_one(self) -> None:
        """All-successes: bound = 1.0 (we cannot rule out 100%)."""
        self.assertEqual(dro_bernoulli_upper_bound(5, 5), 1.0)

    def test_bound_is_sound(self) -> None:
        """For n_success/n_total = 0.1 with 100 trials, the bound is
        approximately 0.18 (well above the empirical rate, but
        well below 1.0)."""
        b = dro_bernoulli_upper_bound(10, 100)
        self.assertGreater(b, 0.10)
        self.assertLess(b, 0.25)

    def test_bound_is_tighter_with_more_data(self) -> None:
        """For the same empirical rate, more data yields a tighter
        (smaller) upper bound."""
        b_10 = dro_bernoulli_upper_bound(1, 10)
        b_100 = dro_bernoulli_upper_bound(10, 100)
        b_1000 = dro_bernoulli_upper_bound(100, 1000)
        # All have empirical rate 0.1, but b_1000 < b_100 < b_10.
        self.assertLess(b_1000, b_100)
        self.assertLess(b_100, b_10)

    def test_bound_monotone_in_confidence(self) -> None:
        """Higher confidence yields a larger (more conservative) bound."""
        n_success, n_total = 10, 100
        b_90 = dro_bernoulli_upper_bound(n_success, n_total, confidence=0.90)
        b_95 = dro_bernoulli_upper_bound(n_success, n_total, confidence=0.95)
        b_99 = dro_bernoulli_upper_bound(n_success, n_total, confidence=0.99)
        self.assertLess(b_90, b_95)
        self.assertLess(b_95, b_99)

    def test_validates_inputs(self) -> None:
        """Negative or invalid inputs raise ValueError."""
        with self.assertRaises(ValueError):
            dro_bernoulli_upper_bound(-1, 10)
        with self.assertRaises(ValueError):
            dro_bernoulli_upper_bound(5, -1)
        with self.assertRaises(ValueError):
            dro_bernoulli_upper_bound(11, 10)  # n_success > n_total
        with self.assertRaises(ValueError):
            dro_bernoulli_upper_bound(1, 1, confidence=0.0)
        with self.assertRaises(ValueError):
            dro_bernoulli_upper_bound(1, 1, confidence=1.0)

    def test_returns_min_of_two_bounds(self) -> None:
        """The bound is always <= min(Hoeffding, Clopper-Pearson)."""
        # Hoeffding for 10/100 at 95% = 0.1 + sqrt(log(20)/200) ~ 0.1 + 0.149
        # Clopper-Pearson for 10/100 at 95% = beta.ppf(0.95, 11, 91) ~ 0.176
        # Both should be > 0.1, and the min should be Clopper-Pearson here.
        b = dro_bernoulli_upper_bound(10, 100, confidence=0.95)
        self.assertGreater(b, 0.1)
        self.assertLess(b, 0.20)


# ---------------------------------------------------------------------------
# TripBand
# ---------------------------------------------------------------------------


class TestTripBand(unittest.TestCase):
    """Tests for the trip-band classification."""

    def test_low_band_below_one_percent(self) -> None:
        """Upper bound < 0.01 -> LOW."""
        self.assertEqual(
            band_for_upper_bound(0.0), TripBand.LOW
        )
        self.assertEqual(
            band_for_upper_bound(0.005), TripBand.LOW
        )

    def test_medium_band_below_five_percent(self) -> None:
        """Upper bound < 0.05 -> MEDIUM."""
        self.assertEqual(
            band_for_upper_bound(0.01), TripBand.MEDIUM
        )
        self.assertEqual(
            band_for_upper_bound(0.03), TripBand.MEDIUM
        )

    def test_high_band_below_twenty_percent(self) -> None:
        """Upper bound < 0.20 -> HIGH."""
        self.assertEqual(
            band_for_upper_bound(0.05), TripBand.HIGH
        )
        self.assertEqual(
            band_for_upper_bound(0.10), TripBand.HIGH
        )

    def test_critical_band_at_or_above_twenty_percent(self) -> None:
        """Upper bound >= 0.20 -> CRITICAL."""
        self.assertEqual(
            band_for_upper_bound(0.20), TripBand.CRITICAL
        )
        self.assertEqual(
            band_for_upper_bound(0.50), TripBand.CRITICAL
        )
        self.assertEqual(
            band_for_upper_bound(1.0), TripBand.CRITICAL
        )

    def test_band_monotone_in_upper_bound(self) -> None:
        """Bands are monotone: larger bound -> at least as critical."""
        values = [0.0, 0.001, 0.005, 0.01, 0.02, 0.05, 0.10, 0.20, 0.5, 1.0]
        bands = [band_for_upper_bound(v) for v in values]
        rank = {TripBand.LOW: 0, TripBand.MEDIUM: 1, TripBand.HIGH: 2, TripBand.CRITICAL: 3}
        ranks = [rank[b] for b in bands]
        self.assertEqual(ranks, sorted(ranks))

    def test_custom_thresholds(self) -> None:
        """Operator can override thresholds."""
        self.assertEqual(
            band_for_upper_bound(0.05, thresholds=(0.01, 0.10, 0.30)),
            TripBand.MEDIUM,
        )
        self.assertEqual(
            band_for_upper_bound(0.25, thresholds=(0.01, 0.10, 0.30)),
            TripBand.HIGH,
        )


# ---------------------------------------------------------------------------
# TripObservation
# ---------------------------------------------------------------------------


class TestTripObservation(unittest.TestCase):
    """Tests for the TripObservation dataclass."""

    def test_construction_with_defaults(self) -> None:
        """Default timestamp is 0.0; source and detection_id optional."""
        obs = TripObservation(tripped=True)
        self.assertTrue(obs.tripped)
        self.assertEqual(obs.source, "")
        self.assertIsNone(obs.detection_id)
        self.assertIsNone(obs.session_digest)
        self.assertEqual(obs.timestamp, 0.0)

    def test_to_dict_round_trip(self) -> None:
        """to_dict exposes all fields."""
        obs = TripObservation(
            tripped=True,
            source="per_output",
            detection_id="d_42",
            session_digest="sd_1",
            timestamp=123.0,
        )
        d = obs.to_dict()
        self.assertTrue(d["tripped"])
        self.assertEqual(d["source"], "per_output")
        self.assertEqual(d["detection_id"], "d_42")
        self.assertEqual(d["session_digest"], "sd_1")
        self.assertEqual(d["timestamp"], 123.0)


# ---------------------------------------------------------------------------
# ProbabilisticTripEngine
# ---------------------------------------------------------------------------


class TestProbabilisticTripEngine(unittest.TestCase):
    """Tests for the probabilistic trip engine."""

    def test_default_construction(self) -> None:
        """Defaults: confidence=0.95, uniform prior, default thresholds."""
        e = ProbabilisticTripEngine()
        self.assertEqual(e.confidence, 0.95)
        self.assertEqual(e.alpha_prior, 1.0)
        self.assertEqual(e.beta_prior, 1.0)
        self.assertEqual(e.band_thresholds, DEFAULT_BAND_THRESHOLDS)
        self.assertEqual(e.n_total, 0)
        self.assertEqual(e.n_success, 0)
        self.assertEqual(e.n_failure, 0)
        # Empty history: bound = 1.0, band = CRITICAL (no info = worst).
        self.assertEqual(e.trip_upper_bound, 1.0)
        self.assertEqual(e.trip_band, TripBand.CRITICAL)
        # Posterior mean under uniform prior with no data = 0.5.
        self.assertAlmostEqual(e.trip_probability, 0.5)

    def test_validates_inputs(self) -> None:
        """Bad construction params raise ValueError."""
        with self.assertRaises(ValueError):
            ProbabilisticTripEngine(confidence=0.0)
        with self.assertRaises(ValueError):
            ProbabilisticTripEngine(confidence=1.0)
        with self.assertRaises(ValueError):
            ProbabilisticTripEngine(alpha_prior=0.0)
        with self.assertRaises(ValueError):
            ProbabilisticTripEngine(beta_prior=-1.0)
        with self.assertRaises(ValueError):
            ProbabilisticTripEngine(band_thresholds=(0.1, 0.5))  # only 2 entries
        with self.assertRaises(ValueError):
            ProbabilisticTripEngine(band_thresholds=(2.0, 3.0, 4.0))  # > 1

    def test_update_appends_to_history(self) -> None:
        """Each update() appends one observation."""
        e = ProbabilisticTripEngine()
        e.update(TripObservation(tripped=True, source="per_output"))
        e.update(TripObservation(tripped=False))
        e.update(TripObservation(tripped=True, source="per_output"))
        self.assertEqual(e.n_total, 3)
        self.assertEqual(e.n_success, 2)
        self.assertEqual(e.n_failure, 1)
        self.assertEqual(len(e.history), 3)

    def test_update_returns_self_for_chaining(self) -> None:
        """update() returns self so callers can chain."""
        e = ProbabilisticTripEngine()
        result = e.update(TripObservation(tripped=True, source="per_output"))
        self.assertIs(result, e)

    def test_posterior_advances_with_observations(self) -> None:
        """trip_probability advances from prior mean toward empirical rate."""
        e = ProbabilisticTripEngine()
        # 10 successes, 90 failures -> posterior mean (11/102) ~ 0.108.
        for _ in range(10):
            e.update(TripObservation(tripped=True, source="per_output"))
        for _ in range(90):
            e.update(TripObservation(tripped=False, source="per_output"))
        self.assertAlmostEqual(e.trip_probability, 11.0 / 102.0, places=3)
        self.assertAlmostEqual(e.empirical_rate, 0.10)
        # Upper bound > empirical rate (conservative).
        self.assertGreater(e.trip_upper_bound, 0.10)
        # Upper bound tighter than 1.0 with 100 observations.
        self.assertLess(e.trip_upper_bound, 0.20)

    def test_trip_band_reflects_history(self) -> None:
        """trip_band is derived from trip_upper_bound."""
        e = create_probabilistic_trip_engine()
        # 100 clean observations -> bound ~ 0.04 -> MEDIUM band.
        for i in range(100):
            e.update(TripObservation(tripped=False, source="per_output"))
        self.assertEqual(e.trip_band, TripBand.MEDIUM)
        # 50 trips + 50 no-trips -> bound ~ 0.62 -> CRITICAL band.
        e.reset()
        for i in range(50):
            e.update(TripObservation(tripped=True, source="per_output"))
        for i in range(50):
            e.update(TripObservation(tripped=False, source="per_output"))
        self.assertEqual(e.trip_band, TripBand.CRITICAL)

    def test_reset_clears_history_preserves_prior(self) -> None:
        """reset() clears history but keeps prior."""
        e = create_probabilistic_trip_engine(alpha_prior=2.0, beta_prior=5.0)
        for _ in range(10):
            e.update(TripObservation(tripped=True, source="per_output"))
        self.assertEqual(e.n_total, 10)
        e.reset()
        self.assertEqual(e.n_total, 0)
        # Prior preserved.
        self.assertEqual(e.alpha_prior, 2.0)
        self.assertEqual(e.beta_prior, 5.0)
        # Empty posterior: posterior mean is prior mean.
        self.assertAlmostEqual(e.trip_probability, 2.0 / 7.0)

    def test_summary_dict_has_all_fields(self) -> None:
        """summary() exposes the operator-facing state."""
        e = create_probabilistic_trip_engine()
        e.update(TripObservation(tripped=True, source="per_output"))
        s = e.summary()
        self.assertEqual(s["n_total"], 1)
        self.assertEqual(s["n_success"], 1)
        self.assertEqual(s["n_failure"], 0)
        self.assertEqual(s["empirical_rate"], 1.0)
        self.assertIn("trip_probability", s)
        self.assertIn("trip_upper_bound", s)
        self.assertIn("bayesian_upper_bound", s)
        self.assertIn("trip_band", s)
        self.assertIn("confidence", s)
        self.assertIn("alpha_prior", s)
        self.assertIn("beta_prior", s)

    def test_to_dict_includes_full_history(self) -> None:
        """to_dict() includes the full observation history."""
        e = create_probabilistic_trip_engine()
        e.update(TripObservation(tripped=True, source="per_output", detection_id="d1"))
        e.update(TripObservation(tripped=False, source="per_output", detection_id="d2"))
        d = e.to_dict()
        self.assertEqual(len(d["history"]), 2)
        self.assertEqual(d["history"][0]["detection_id"], "d1")
        self.assertEqual(d["history"][1]["detection_id"], "d2")
        self.assertIn("band_thresholds", d)

    def test_bayesian_and_dro_bounds_agree_in_moderate_regime(self) -> None:
        """For moderate n, the Bayesian and DRO upper bounds agree."""
        e = create_probabilistic_trip_engine()
        for _ in range(10):
            e.update(TripObservation(tripped=True, source="per_output"))
        for _ in range(10):
            e.update(TripObservation(tripped=False))
        # Both bounds should be in (0.4, 0.8) for 10/20 at 95%.
        self.assertAlmostEqual(e.trip_upper_bound, e.bayesian_upper_bound, places=1)


# ---------------------------------------------------------------------------
# CEFBreakerOutcome probabilistic fields
# ---------------------------------------------------------------------------


class TestCEFBreakerOutcomeProbabilistic(unittest.TestCase):
    """Tests for the probabilistic fields on CEFBreakerOutcome."""

    def test_no_engine_defaults_are_unknown(self) -> None:
        """When no probabilistic_engine is supplied, the new fields
        are safe defaults: 0.0 / 0.0 / 'unknown' / 0."""
        outcome = assess_cef_to_breaker(
            detection=_make_clean_detection(),
        )
        self.assertEqual(outcome.trip_probability, 0.0)
        self.assertEqual(outcome.trip_upper_bound, 0.0)
        self.assertEqual(outcome.trip_band, "unknown")
        self.assertEqual(outcome.trip_n_samples, 0)
        # Conservative posture: verdict + should_open still correct.
        self.assertEqual(outcome.verdict, CEFBreakerVerdict.NO_TRIP)
        self.assertFalse(outcome.should_open)

    def test_engine_feeds_clean_detection(self) -> None:
        """A clean detection with an engine-fed history still records the
        observation and advances trip_probability."""
        engine = create_probabilistic_trip_engine()
        cfg = CEFIntegrationConfig(probabilistic_engine=engine)
        outcome = assess_cef_to_breaker(
            detection=_make_clean_detection(),
            config=cfg,
        )
        self.assertEqual(outcome.verdict, CEFBreakerVerdict.NO_TRIP)
        self.assertFalse(outcome.should_open)
        # Engine saw 1 observation (clean, no trip).
        self.assertEqual(outcome.trip_n_samples, 1)
        # Posterior mean: uniform prior + 1 failure = 1/(1+2) = 1/3.
        self.assertAlmostEqual(outcome.trip_probability, 1.0 / 3.0)
        # Bound is in (0, 1) and > posterior mean.
        self.assertGreater(outcome.trip_upper_bound, outcome.trip_probability)
        self.assertLess(outcome.trip_upper_bound, 1.0)
        self.assertIn(outcome.trip_band, {b.value for b in TripBand})

    def test_engine_feeds_critical_detection(self) -> None:
        """A CRITICAL detection trips the breaker AND advances the engine."""
        engine = create_probabilistic_trip_engine()
        cfg = CEFIntegrationConfig(probabilistic_engine=engine)
        outcome = assess_cef_to_breaker(
            detection=_make_critical_detection(),
            config=cfg,
        )
        # Verdict: trip (the boolean is unchanged).
        self.assertEqual(outcome.verdict, CEFBreakerVerdict.TRIP)
        self.assertTrue(outcome.should_open)
        # Engine saw 1 trip observation.
        self.assertEqual(outcome.trip_n_samples, 1)
        self.assertEqual(outcome.trip_probability, 2.0 / 3.0)  # Beta(2, 1) mean.
        # Bound is at the ceiling (small n, all-success -> Clopper-Pearson = 1).
        self.assertGreaterEqual(outcome.trip_upper_bound, 0.5)
        self.assertLessEqual(outcome.trip_upper_bound, 1.0)

    def test_engine_advances_across_calls(self) -> None:
        """Across multiple assess calls, the engine state advances."""
        engine = create_probabilistic_trip_engine()
        cfg = CEFIntegrationConfig(probabilistic_engine=engine)
        # 9 clean + 1 critical = 10 observations total.
        for i in range(9):
            o = assess_cef_to_breaker(
                detection=_make_clean_detection(), config=cfg,
            )
            self.assertEqual(o.trip_n_samples, i + 1)
        # After 9 clean: n_total=9, n_success=0.
        self.assertEqual(engine.n_total, 9)
        o = assess_cef_to_breaker(
            detection=_make_critical_detection(), config=cfg,
        )
        # After 1 critical: n_total=10, n_success=1.
        self.assertEqual(o.trip_n_samples, 10)
        self.assertEqual(engine.n_total, 10)
        self.assertEqual(engine.n_success, 1)
        # Posterior mean: uniform prior + 1 success + 9 failures = 2/12.
        self.assertAlmostEqual(o.trip_probability, 2.0 / 12.0)

    def test_to_dict_includes_probabilistic_fields(self) -> None:
        """to_dict() exposes the four new probabilistic fields."""
        engine = create_probabilistic_trip_engine()
        cfg = CEFIntegrationConfig(probabilistic_engine=engine)
        outcome = assess_cef_to_breaker(
            detection=_make_clean_detection(), config=cfg,
        )
        d = outcome.to_dict()
        self.assertIn("trip_probability", d)
        self.assertIn("trip_upper_bound", d)
        self.assertIn("trip_band", d)
        self.assertIn("trip_n_samples", d)
        self.assertEqual(d["trip_n_samples"], 1)


# ---------------------------------------------------------------------------
# Conservative posture
# ---------------------------------------------------------------------------


class TestConservativePosture(unittest.TestCase):
    """Conservative-posture invariants for the probabilistic substrate."""

    def test_empty_history_yields_critical_band(self) -> None:
        """No data -> worst-case: upper bound = 1.0, band = CRITICAL.
        This is the conservative analog of 'no info -> assume worst'."""
        e = create_probabilistic_trip_engine()
        self.assertEqual(e.trip_upper_bound, 1.0)
        self.assertEqual(e.trip_band, TripBand.CRITICAL)

    def test_engine_never_demotes(self) -> None:
        """Once an observation is recorded, the engine never forgets it.
        Only reset() (an explicit operator action) clears history."""
        e = create_probabilistic_trip_engine()
        e.update(TripObservation(tripped=True, source="per_output"))
        e.update(TripObservation(tripped=True, source="per_output"))
        e.update(TripObservation(tripped=True, source="per_output"))
        n_before = e.n_total
        s_before = e.n_success
        # "Demoting" attempt: update with no_trip.
        e.update(TripObservation(tripped=False, source="per_output"))
        # All four observations recorded.
        self.assertEqual(e.n_total, n_before + 1)
        # The original 3 trips are still in the history.
        self.assertEqual(e.n_success, s_before)
        self.assertEqual(len(e.history), 4)

    def test_band_thresholds_are_monotone_in_default(self) -> None:
        """Default thresholds are strictly increasing: 0.01 < 0.05 < 0.20."""
        self.assertEqual(DEFAULT_BAND_THRESHOLDS, (0.01, 0.05, 0.20))
        self.assertLess(DEFAULT_BAND_THRESHOLDS[0], DEFAULT_BAND_THRESHOLDS[1])
        self.assertLess(DEFAULT_BAND_THRESHOLDS[1], DEFAULT_BAND_THRESHOLDS[2])

    def test_band_function_monotone(self) -> None:
        """band_for_upper_bound is monotone non-decreasing in the bound."""
        prev = TripBand.LOW
        for v in [0.0, 0.001, 0.005, 0.01, 0.02, 0.05, 0.10, 0.20, 0.5, 1.0]:
            cur = band_for_upper_bound(v)
            rank = {TripBand.LOW: 0, TripBand.MEDIUM: 1, TripBand.HIGH: 2, TripBand.CRITICAL: 3}
            self.assertGreaterEqual(rank[cur], rank[prev])
            prev = cur


# ---------------------------------------------------------------------------
# Convenience constructor
# ---------------------------------------------------------------------------


class TestCreateEngine(unittest.TestCase):
    """Tests for the create_probabilistic_trip_engine helper."""

    def test_default_construction(self) -> None:
        """Default: confidence=0.95, uniform prior, default thresholds."""
        e = create_probabilistic_trip_engine()
        self.assertIsInstance(e, ProbabilisticTripEngine)
        self.assertEqual(e.confidence, 0.95)
        self.assertEqual(e.alpha_prior, 1.0)
        self.assertEqual(e.beta_prior, 1.0)

    def test_custom_prior(self) -> None:
        """Custom prior params are honored."""
        e = create_probabilistic_trip_engine(alpha_prior=2.0, beta_prior=5.0)
        self.assertEqual(e.alpha_prior, 2.0)
        self.assertEqual(e.beta_prior, 5.0)
        # Posterior mean under informative prior with no data = 2/7.
        self.assertAlmostEqual(e.trip_probability, 2.0 / 7.0)

    def test_custom_thresholds(self) -> None:
        """Custom band thresholds are honored."""
        e = create_probabilistic_trip_engine(band_thresholds=(0.005, 0.02, 0.10))
        self.assertEqual(e.band_thresholds, (0.005, 0.02, 0.10))
        self.assertEqual(e.trip_band, TripBand.CRITICAL)  # empty -> 1.0

    def test_custom_confidence(self) -> None:
        """Custom confidence is honored."""
        e_90 = create_probabilistic_trip_engine(confidence=0.90)
        e_99 = create_probabilistic_trip_engine(confidence=0.99)
        self.assertEqual(e_90.confidence, 0.90)
        self.assertEqual(e_99.confidence, 0.99)


if __name__ == "__main__":
    unittest.main()
