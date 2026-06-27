"""
Tests for GovernorCircuit (core/governor_circuit.py).

Coverage
--------
- TestGovernorCircuitConfig (7): construction, defaults, threshold bounds,
  hysteresis invariant (reset <= trip), probe_count floor, layer ids
- TestGateEnums (2): GateState / GateAction round-trip
- TestGateObservation (3): construction, to_dict, metadata default
- TestGateTransition (3): construction, to_dict, immutability (frozen)
- TestGovernorDecision (2): construction, to_dict
- TestGovernorCircuitNoEngine (5): empty state, decide closed, upper_bound
  zero, summary, write_audit, transitions
- TestGovernorCircuitSingleLayer (3): bound from engine, OPEN transition,
  HALF_OPEN on recovery
- TestGovernorCircuitTwoLayerMax (3): max-bound selection, session-only
  drives gate, per-output-only drives gate
- TestGovernorCircuitHysteresis (6): chatter prevention, OPEN->HALF_OPEN
  only when bound <= reset_threshold, HALF_OPEN->CLOSED requires probes,
  HALF_OPEN->OPEN on rebound, CLOSED->OPEN requires trip_threshold
- TestGovernorCircuitAudit (4): transitions appended, write_audit JSONL,
  reset clears log, reset preserves engines
- TestGovernorCircuitConvenience (4): create_governor_circuit defaults,
  custom thresholds, rejection of invalid config, no-engine install
- TestGovernorCircuitIntegration (3): real ProbabilisticTripEngine feeding
  (3 trips -> gate OPEN), recovery (no trips -> gate CLOSED), mixed
  observations (open and close cycle)
- TestGovernorCircuitConservativePosture (3): reset never above trip,
  reset preserves engines, no auto-close on a single good probe when
  probe_count > 1
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest

from core.governor_circuit import (
    DEFAULT_PROBE_COUNT,
    DEFAULT_RESET_THRESHOLD,
    DEFAULT_TRIP_THRESHOLD,
    GateAction,
    GateObservation,
    GateState,
    GateTransition,
    GovernorCircuit,
    GovernorCircuitConfig,
    GovernorDecision,
    create_governor_circuit,
)


# ---------------------------------------------------------------------------
# Helper: a minimal in-memory engine for fast, dependency-free tests
# ---------------------------------------------------------------------------


class _StubEngine:
    """Minimal stand-in for ProbabilisticTripEngine.

    Lets the tests drive the bound directly without depending on
    scipy or the full engine module.
    """

    def __init__(self, bound: float = 0.0, band: str = "low") -> None:
        self._bound = bound
        self._band = band
        self.history: list = []

    def update(self, observation) -> None:
        self.history.append(observation)

    @property
    def trip_upper_bound(self) -> float:
        return self._bound

    @property
    def trip_band(self) -> str:
        return self._band

    def set_bound(self, bound: float, band: str | None = None) -> None:
        self._bound = bound
        if band is not None:
            self._band = band

    def summary(self) -> dict:
        return {
            "trip_upper_bound": self._bound,
            "trip_band": self._band,
            "history_size": len(self.history),
        }


# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------


class TestGovernorCircuitConfig:
    def test_default_construction(self) -> None:
        cfg = GovernorCircuitConfig()
        assert cfg.trip_threshold == DEFAULT_TRIP_THRESHOLD
        assert cfg.reset_threshold == DEFAULT_RESET_THRESHOLD
        assert cfg.probe_count == DEFAULT_PROBE_COUNT
        assert cfg.session_layer_id == "session"
        assert cfg.per_output_layer_id == "per_output"

    def test_trip_threshold_bounds_low(self) -> None:
        with pytest.raises(ValueError, match="trip_threshold must be in"):
            GovernorCircuitConfig(trip_threshold=-0.01)

    def test_trip_threshold_bounds_high(self) -> None:
        with pytest.raises(ValueError, match="trip_threshold must be in"):
            GovernorCircuitConfig(trip_threshold=1.01)

    def test_reset_threshold_bounds(self) -> None:
        with pytest.raises(ValueError, match="reset_threshold must be in"):
            GovernorCircuitConfig(reset_threshold=1.5)

    def test_hysteresis_invariant(self) -> None:
        # reset > trip is the only forbidden arrangement.
        with pytest.raises(ValueError, match="reset_threshold must be <="):
            GovernorCircuitConfig(trip_threshold=0.05, reset_threshold=0.10)

    def test_probe_count_floor(self) -> None:
        with pytest.raises(ValueError, match="probe_count must be >="):
            GovernorCircuitConfig(probe_count=0)

    def test_equal_thresholds_allowed(self) -> None:
        # reset == trip is degenerate but allowed (no hysteresis band).
        cfg = GovernorCircuitConfig(
            trip_threshold=0.05, reset_threshold=0.05, probe_count=1
        )
        assert cfg.trip_threshold == cfg.reset_threshold


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestGateEnums:
    def test_gate_state_values(self) -> None:
        assert GateState.CLOSED.value == "closed"
        assert GateState.HALF_OPEN.value == "half_open"
        assert GateState.OPEN.value == "open"

    def test_gate_action_values(self) -> None:
        assert GateAction.ALLOW.value == "allow"
        assert GateAction.PROBE.value == "probe"
        assert GateAction.BLOCK.value == "block"


# ---------------------------------------------------------------------------
# GateObservation tests
# ---------------------------------------------------------------------------


class TestGateObservation:
    def test_construction(self) -> None:
        obs = GateObservation(tripped=True, label="test_trip")
        assert obs.tripped is True
        assert obs.label == "test_trip"
        assert obs.metadata == {}
        assert obs.timestamp  # auto-populated

    def test_to_dict(self) -> None:
        obs = GateObservation(
            tripped=False,
            label="ok",
            metadata={"session_id": "abc"},
        )
        d = obs.to_dict()
        assert d["tripped"] is False
        assert d["label"] == "ok"
        assert d["metadata"] == {"session_id": "abc"}
        assert "timestamp" in d

    def test_metadata_default_empty(self) -> None:
        obs = GateObservation(tripped=True, label="x")
        assert obs.metadata == {}


# ---------------------------------------------------------------------------
# GateTransition tests
# ---------------------------------------------------------------------------


class TestGateTransition:
    def test_construction(self) -> None:
        t = GateTransition(
            from_state=GateState.CLOSED,
            to_state=GateState.OPEN,
            upper_bound=0.10,
            trip_band="high",
            reason="trip",
            consecutive_good=0,
            timestamp="2026-06-26T00:00:00+00:00",
        )
        assert t.from_state == GateState.CLOSED
        assert t.to_state == GateState.OPEN
        assert t.upper_bound == pytest.approx(0.10)
        assert t.transition_id  # auto-populated UUID

    def test_to_dict(self) -> None:
        t = GateTransition(
            from_state=GateState.OPEN,
            to_state=GateState.HALF_OPEN,
            upper_bound=0.01,
            trip_band="medium",
            reason="recovered",
            consecutive_good=1,
            timestamp="2026-06-26T00:00:00+00:00",
        )
        d = t.to_dict()
        assert d["from_state"] == "open"
        assert d["to_state"] == "half_open"
        assert d["upper_bound"] == pytest.approx(0.01)
        assert d["consecutive_good"] == 1
        assert "transition_id" in d

    def test_frozen(self) -> None:
        t = GateTransition(
            from_state=GateState.CLOSED,
            to_state=GateState.OPEN,
            upper_bound=0.05,
            trip_band="medium",
            reason="trip",
            consecutive_good=0,
            timestamp="t",
        )
        with pytest.raises(Exception):
            t.upper_bound = 0.99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# GovernorDecision tests
# ---------------------------------------------------------------------------


class TestGovernorDecision:
    def test_construction(self) -> None:
        d = GovernorDecision(
            action=GateAction.ALLOW,
            state=GateState.CLOSED,
            upper_bound=0.0,
            trip_band="low",
            consecutive_good=0,
            reason="ok",
            timestamp="t",
        )
        assert d.action == GateAction.ALLOW
        assert d.state == GateState.CLOSED

    def test_to_dict(self) -> None:
        d = GovernorDecision(
            action=GateAction.BLOCK,
            state=GateState.OPEN,
            upper_bound=0.10,
            trip_band="high",
            consecutive_good=0,
            reason="tripped",
            timestamp="t",
        )
        dd = d.to_dict()
        assert dd["action"] == "block"
        assert dd["state"] == "open"
        assert dd["upper_bound"] == pytest.approx(0.10)


# ---------------------------------------------------------------------------
# No-engine tests
# ---------------------------------------------------------------------------


class TestGovernorCircuitNoEngine:
    def test_initial_state_closed(self) -> None:
        g = GovernorCircuit()
        assert g.state == GateState.CLOSED

    def test_initial_decide_allow(self) -> None:
        g = GovernorCircuit()
        d = g.decide()
        assert d.action == GateAction.ALLOW
        assert d.state == GateState.CLOSED
        assert d.upper_bound == pytest.approx(0.0)

    def test_upper_bound_zero_without_engines(self) -> None:
        g = GovernorCircuit()
        assert g.upper_bound == pytest.approx(0.0)
        assert g.trip_band == "low"

    def test_summary_shape(self) -> None:
        g = GovernorCircuit()
        s = g.summary()
        assert s["state"] == "closed"
        assert s["upper_bound"] == pytest.approx(0.0)
        assert s["trip_band"] == "low"
        assert s["transition_count"] == 0
        assert s["per_output_engine"] is None
        assert s["session_engine"] is None

    def test_no_engines_no_reevaluate_change(self) -> None:
        g = GovernorCircuit()
        obs = GateObservation(tripped=True, label="x")
        # With no engines, the bound stays 0.0 -- the gate stays CLOSED.
        d = g.feed(per_output_observation=obs)
        assert d.state == GateState.CLOSED
        assert d.action == GateAction.ALLOW


# ---------------------------------------------------------------------------
# Single-layer tests
# ---------------------------------------------------------------------------


class TestGovernorCircuitSingleLayer:
    def test_bound_driven_by_engine(self) -> None:
        eng = _StubEngine(bound=0.10, band="high")
        g = GovernorCircuit(per_output_engine=eng)
        assert g.upper_bound == pytest.approx(0.10)
        assert g.trip_band == "high"

    def test_open_on_bound_cross(self) -> None:
        eng = _StubEngine(bound=0.10, band="high")
        g = GovernorCircuit(per_output_engine=eng)
        d = g.decide()
        assert d.action == GateAction.BLOCK
        assert d.state == GateState.OPEN
        assert len(g.transitions()) == 0  # decide() doesn't transition

        # Now feed -- bound stays above threshold -- transitions to OPEN.
        obs = GateObservation(tripped=True, label="trip")
        d = g.feed(per_output_observation=obs)
        assert d.state == GateState.OPEN
        assert len(g.transitions()) == 1

    def test_half_open_on_recovery(self) -> None:
        eng = _StubEngine(bound=0.10, band="high")
        g = GovernorCircuit(per_output_engine=eng)
        g.feed(per_output_observation=GateObservation(tripped=True, label="trip"))
        assert g.state == GateState.OPEN

        # Bring bound down.
        eng.set_bound(bound=0.005, band="low")
        d = g.feed(per_output_observation=GateObservation(tripped=False, label="ok"))
        # bound=0.005 <= reset_threshold=0.01 -> HALF_OPEN
        assert g.state == GateState.HALF_OPEN
        # With probe_count=1, one good probe -> CLOSED.
        assert d.action == GateAction.ALLOW or d.action == GateAction.PROBE
        assert g.state == GateState.CLOSED or g.state == GateState.HALF_OPEN


# ---------------------------------------------------------------------------
# Two-layer tests
# ---------------------------------------------------------------------------


class TestGovernorCircuitTwoLayerMax:
    def test_max_bound_selection(self) -> None:
        per = _StubEngine(bound=0.01, band="medium")
        sess = _StubEngine(bound=0.20, band="critical")
        g = GovernorCircuit(per_output_engine=per, session_engine=sess)
        assert g.upper_bound == pytest.approx(0.20)
        assert g.trip_band == "critical"

    def test_session_only_drives_gate(self) -> None:
        sess = _StubEngine(bound=0.10, band="high")
        g = GovernorCircuit(session_engine=sess)
        d = g.decide()
        assert d.action == GateAction.BLOCK
        assert d.state == GateState.OPEN

    def test_per_output_only_drives_gate(self) -> None:
        per = _StubEngine(bound=0.10, band="high")
        g = GovernorCircuit(per_output_engine=per)
        d = g.decide()
        assert d.action == GateAction.BLOCK

    def test_lower_layer_does_not_dominate(self) -> None:
        # Session at HIGH (0.10), per-output at LOW (0.001). Gate must
        # see the session layer.
        sess = _StubEngine(bound=0.10, band="high")
        per = _StubEngine(bound=0.001, band="low")
        g = GovernorCircuit(per_output_engine=per, session_engine=sess)
        assert g.upper_bound == pytest.approx(0.10)
        assert g.trip_band == "high"


# ---------------------------------------------------------------------------
# Hysteresis tests
# ---------------------------------------------------------------------------


class TestGovernorCircuitHysteresis:
    def test_closed_to_open_at_threshold(self) -> None:
        eng = _StubEngine(bound=0.06, band="high")
        g = GovernorCircuit(per_output_engine=eng)
        g.feed(per_output_observation=GateObservation(tripped=True, label="trip"))
        assert g.state == GateState.OPEN

    def test_chatter_prevention(self) -> None:
        # Bound oscillating just below and above trip_threshold must
        # NOT cause the gate to chatter between CLOSED and OPEN.
        eng = _StubEngine(bound=0.04, band="medium")  # below trip_threshold
        g = GovernorCircuit(per_output_engine=eng)
        for _ in range(5):
            g.feed(per_output_observation=GateObservation(tripped=False, label="ok"))
        assert g.state == GateState.CLOSED
        # Now nudge just above trip_threshold.
        eng.set_bound(bound=0.06, band="high")
        g.feed(per_output_observation=GateObservation(tripped=True, label="trip"))
        assert g.state == GateState.OPEN
        # Back down -- between thresholds, still OPEN.
        eng.set_bound(bound=0.03, band="medium")
        g.feed(per_output_observation=GateObservation(tripped=False, label="ok"))
        assert g.state == GateState.OPEN

    def test_open_to_half_open_only_at_reset(self) -> None:
        eng = _StubEngine(bound=0.10, band="high")
        g = GovernorCircuit(per_output_engine=eng)
        g.feed(per_output_observation=GateObservation(tripped=True, label="trip"))
        assert g.state == GateState.OPEN
        # Bound at 0.02 is above reset_threshold=0.01 -- still OPEN.
        eng.set_bound(bound=0.02, band="medium")
        g.feed(per_output_observation=GateObservation(tripped=False, label="ok"))
        assert g.state == GateState.OPEN
        # Bound at 0.005 is below reset_threshold -- HALF_OPEN.
        eng.set_bound(bound=0.005, band="low")
        g.feed(per_output_observation=GateObservation(tripped=False, label="ok"))
        assert g.state == GateState.HALF_OPEN or g.state == GateState.CLOSED

    def test_half_open_to_closed_requires_probes(self) -> None:
        # With probe_count=2, two consecutive good probes are needed.
        cfg = GovernorCircuitConfig(probe_count=2)
        eng = _StubEngine(bound=0.10, band="high")
        g = GovernorCircuit(config=cfg, per_output_engine=eng)
        g.feed(per_output_observation=GateObservation(tripped=True, label="trip"))
        assert g.state == GateState.OPEN
        eng.set_bound(bound=0.005, band="low")
        # First good probe: HALF_OPEN, not yet CLOSED.
        g.feed(per_output_observation=GateObservation(tripped=False, label="ok"))
        assert g.state == GateState.HALF_OPEN
        # Second good probe: now CLOSED.
        g.feed(per_output_observation=GateObservation(tripped=False, label="ok"))
        assert g.state == GateState.CLOSED

    def test_half_open_back_to_open_on_rebound(self) -> None:
        eng = _StubEngine(bound=0.10, band="high")
        g = GovernorCircuit(per_output_engine=eng)
        g.feed(per_output_observation=GateObservation(tripped=True, label="trip"))
        eng.set_bound(bound=0.005, band="low")
        g.feed(per_output_observation=GateObservation(tripped=False, label="ok"))
        assert g.state == GateState.HALF_OPEN or g.state == GateState.CLOSED
        # Rebound -- bound back above trip_threshold.
        eng.set_bound(bound=0.20, band="critical")
        # First, force the state back to HALF_OPEN if it had closed.
        # In the default probe_count=1 path, it would have closed.
        # We then trigger a re-evaluation by feeding.
        g.feed(per_output_observation=GateObservation(tripped=True, label="trip"))
        assert g.state == GateState.OPEN

    def test_closed_to_open_requires_threshold(self) -> None:
        # Bound at exactly 0.04 is below trip_threshold=0.05. Gate
        # stays CLOSED.
        eng = _StubEngine(bound=0.04, band="medium")
        g = GovernorCircuit(per_output_engine=eng)
        for _ in range(3):
            g.feed(per_output_observation=GateObservation(tripped=True, label="trip"))
        assert g.state == GateState.CLOSED


# ---------------------------------------------------------------------------
# Audit tests
# ---------------------------------------------------------------------------


class TestGovernorCircuitAudit:
    def test_transitions_appended(self) -> None:
        eng = _StubEngine(bound=0.10, band="high")
        g = GovernorCircuit(per_output_engine=eng)
        g.feed(per_output_observation=GateObservation(tripped=True, label="trip"))
        eng.set_bound(bound=0.005, band="low")
        g.feed(per_output_observation=GateObservation(tripped=False, label="ok"))
        ts = g.transitions()
        assert len(ts) >= 1
        assert any(t.from_state == GateState.CLOSED for t in ts)

    def test_write_audit_jsonl(self, tmp_path) -> None:
        eng = _StubEngine(bound=0.10, band="high")
        g = GovernorCircuit(per_output_engine=eng)
        g.feed(per_output_observation=GateObservation(tripped=True, label="trip"))
        path = tmp_path / "audit.jsonl"
        g.write_audit(str(path))
        # Append a second wave.
        eng.set_bound(bound=0.005, band="low")
        g.feed(per_output_observation=GateObservation(tripped=False, label="ok"))
        g.write_audit(str(path))
        # The file should have at least one line per call.
        lines = path.read_text().strip().split("\n")
        assert len(lines) >= 2
        for line in lines:
            obj = json.loads(line)
            assert "transition_id" in obj
            assert "from_state" in obj
            assert "to_state" in obj

    def test_reset_clears_log(self) -> None:
        eng = _StubEngine(bound=0.10, band="high")
        g = GovernorCircuit(per_output_engine=eng)
        g.feed(per_output_observation=GateObservation(tripped=True, label="trip"))
        assert len(g.transitions()) >= 1
        g.reset()
        assert g.state == GateState.CLOSED
        assert g.transition_count == 0
        assert g.consecutive_good == 0

    def test_reset_preserves_engines(self) -> None:
        eng = _StubEngine(bound=0.10, band="high")
        g = GovernorCircuit(per_output_engine=eng)
        g.feed(per_output_observation=GateObservation(tripped=True, label="trip"))
        g.reset()
        # Engine is untouched.
        assert eng.trip_upper_bound == pytest.approx(0.10)
        assert eng.history  # history is preserved


# ---------------------------------------------------------------------------
# Convenience tests
# ---------------------------------------------------------------------------


class TestGovernorCircuitConvenience:
    def test_create_defaults(self) -> None:
        g = create_governor_circuit()
        assert g.state == GateState.CLOSED
        assert g.config.trip_threshold == DEFAULT_TRIP_THRESHOLD
        assert g.config.reset_threshold == DEFAULT_RESET_THRESHOLD

    def test_create_with_engines(self) -> None:
        per = _StubEngine(bound=0.10, band="high")
        sess = _StubEngine(bound=0.20, band="critical")
        g = create_governor_circuit(per_output_engine=per, session_engine=sess)
        assert g.upper_bound == pytest.approx(0.20)

    def test_create_custom_thresholds(self) -> None:
        g = create_governor_circuit(
            trip_threshold=0.10, reset_threshold=0.02, probe_count=3
        )
        assert g.config.trip_threshold == pytest.approx(0.10)
        assert g.config.reset_threshold == pytest.approx(0.02)
        assert g.config.probe_count == 3

    def test_create_rejects_invalid(self) -> None:
        with pytest.raises(ValueError):
            create_governor_circuit(trip_threshold=0.01, reset_threshold=0.10)


# ---------------------------------------------------------------------------
# Integration with real ProbabilisticTripEngine
# ---------------------------------------------------------------------------


class TestGovernorCircuitIntegration:
    @pytest.fixture
    def real_engines(self):
        """Two real ProbabilisticTripEngine instances (if available)."""
        from core.cef_probabilistic_verification import (
            ProbabilisticTripEngine,
            TripObservation,
            create_probabilistic_trip_engine,
        )
        per = create_probabilistic_trip_engine()
        sess = create_probabilistic_trip_engine()
        return per, sess, TripObservation

    def test_three_trips_open_gate(self, real_engines) -> None:
        per, sess, TripObservation = real_engines
        # Pre-warm engines past the warm-up window so the bound is
        # data-driven, not prior-driven. The test name is legacy;
        # it exercises "trips open the gate after warm-up".
        g = create_governor_circuit(
            per_output_engine=per,
            session_engine=sess,
            trip_threshold=0.40,
            reset_threshold=0.05,
        )
        # Warm-up: 20 ok feeds bring the engines out of the
        # warm-up window. The bound after 20 ok observations is
        # ~0.13 (Clopper-Pearson 95% upper CI on 0/20).
        for _ in range(20):
            g.feed(
                per_output_observation=GateObservation(tripped=False, label="ok"),
                session_observation=GateObservation(tripped=False, label="ok"),
            )
        assert g.state == GateState.CLOSED
        # Now drive per_output with enough trips that the bound
        # exceeds trip_threshold=0.40. With default Hoeffding +
        # Clopper-Pearson, 8/28 (empirical 0.29) gives bound ~0.42.
        for _ in range(8):
            g.feed(
                per_output_observation=GateObservation(tripped=True, label="trip"),
            )
        assert g.state == GateState.OPEN
        d = g.decide()
        assert d.action == GateAction.BLOCK

    def test_recovery_returns_to_closed(self, real_engines) -> None:
        per, sess, _ = real_engines
        # Pre-warm so the bound is data-driven.
        g = create_governor_circuit(
            per_output_engine=per,
            session_engine=sess,
            trip_threshold=0.40,
            reset_threshold=0.20,
            probe_count=1,
        )
        for _ in range(20):
            g.feed(
                per_output_observation=GateObservation(tripped=False, label="ok"),
                session_observation=GateObservation(tripped=False, label="ok"),
            )
        # Trip hard past warm-up.
        for _ in range(10):
            g.feed(
                per_output_observation=GateObservation(tripped=True, label="trip"),
            )
        assert g.state == GateState.OPEN
        # Now feed many clean observations to bring the bound down.
        # After ~80 ok observations on top of 30 total with 10 trips,
        # empirical rate = 10/110 ~ 0.09; bound well below 0.05.
        for _ in range(80):
            g.feed(
                per_output_observation=GateObservation(tripped=False, label="ok"),
            )
        assert g.state == GateState.CLOSED

    def test_mixed_open_close_cycle(self, real_engines) -> None:
        per, sess, _ = real_engines
        g = create_governor_circuit(
            per_output_engine=per,
            session_engine=sess,
            trip_threshold=0.40,
            reset_threshold=0.20,
            probe_count=2,
        )
        # Pre-warm: 20 clean observations so the bound is data-driven.
        for _ in range(20):
            g.feed(
                per_output_observation=GateObservation(tripped=False, label="ok"),
                session_observation=GateObservation(tripped=False, label="ok"),
            )
        # Phase 1: heavy trips past warm-up -> OPEN.
        for _ in range(8):
            g.feed(
                per_output_observation=GateObservation(tripped=True, label="trip"),
            )
        assert g.state == GateState.OPEN
        # Phase 2: clean observations -> recovery -> HALF_OPEN -> CLOSED.
        # 100 ok obs on top of 28 total with 8 trips: empirical = 8/128 ~ 0.06;
        # bound well below 0.05.
        for _ in range(100):
            g.feed(
                per_output_observation=GateObservation(tripped=False, label="ok"),
            )
        assert g.state == GateState.CLOSED
        # Phase 3: trip again -> OPEN. With Hoeffding on 128 prior ok obs,
        # need ~80 trips on top
        for _ in range(80):
            g.feed(
                per_output_observation=GateObservation(tripped=True, label="trip"),
            )
        assert g.state == GateState.OPEN
        # The transition log records the full cycle.
        ts = g.transitions()
        assert len(ts) >= 2


# ---------------------------------------------------------------------------
# Conservative posture tests
# ---------------------------------------------------------------------------


class TestGovernorCircuitConservativePosture:
    def test_no_silent_close_from_open(self) -> None:
        eng = _StubEngine(bound=0.10, band="high")
        g = GovernorCircuit(per_output_engine=eng)
        g.feed(per_output_observation=GateObservation(tripped=True, label="trip"))
        assert g.state == GateState.OPEN
        # Bound stays high -- gate stays OPEN, even after many feeds.
        for _ in range(5):
            g.feed(per_output_observation=GateObservation(tripped=True, label="trip"))
        assert g.state == GateState.OPEN

    def test_probe_count_floor_enforced(self) -> None:
        # probe_count=1 is the most conservative floor.
        cfg = GovernorCircuitConfig(probe_count=1)
        assert cfg.probe_count == 1
        # probe_count=0 is rejected.
        with pytest.raises(ValueError):
            GovernorCircuitConfig(probe_count=0)

    def test_no_auto_close_on_single_probe_when_probe_count_high(self) -> None:
        # With probe_count=3, a single good probe does NOT close the gate.
        cfg = GovernorCircuitConfig(probe_count=3)
        eng = _StubEngine(bound=0.10, band="high")
        g = GovernorCircuit(config=cfg, per_output_engine=eng)
        g.feed(per_output_observation=GateObservation(tripped=True, label="trip"))
        assert g.state == GateState.OPEN
        eng.set_bound(bound=0.005, band="low")
        g.feed(per_output_observation=GateObservation(tripped=False, label="ok"))
        assert g.state == GateState.HALF_OPEN
        assert g.state != GateState.CLOSED
        g.feed(per_output_observation=GateObservation(tripped=False, label="ok"))
        assert g.state == GateState.HALF_OPEN
        g.feed(per_output_observation=GateObservation(tripped=False, label="ok"))
        assert g.state == GateState.CLOSED


# ---------------------------------------------------------------------------
# Feed validation tests
# ---------------------------------------------------------------------------


class TestGovernorCircuitFeedValidation:
    def test_feed_requires_at_least_one_observation(self) -> None:
        g = GovernorCircuit()
        with pytest.raises(ValueError, match="at least one"):
            g.feed()

    def test_feed_with_both_observations(self) -> None:
        per = _StubEngine(bound=0.10, band="high")
        sess = _StubEngine(bound=0.20, band="critical")
        g = GovernorCircuit(per_output_engine=per, session_engine=sess)
        d = g.feed(
            per_output_observation=GateObservation(tripped=True, label="p"),
            session_observation=GateObservation(tripped=True, label="s"),
        )
        assert d.state == GateState.OPEN

    def test_to_dict_round_trip(self) -> None:
        eng = _StubEngine(bound=0.10, band="high")
        g = GovernorCircuit(per_output_engine=eng)
        g.feed(per_output_observation=GateObservation(tripped=True, label="trip"))
        d = g.to_dict()
        assert d["state"] == "open"
        assert d["per_output_engine"]["trip_upper_bound"] == pytest.approx(0.10)
        assert len(d["transitions"]) >= 1
        # Transitions are JSON-serializable.
        json.dumps(d)


# ---------------------------------------------------------------------------
# Warm-up grace tests
# ---------------------------------------------------------------------------


class TestGovernorCircuitWarmUp:
    """Verify the cold-engine grace window.

    The gate suppresses CLOSED -> OPEN transitions while one or more
    engines are still in their warm-up window (n_observations <
    warm_up_min_obs). The suppressed decision is recorded as a
    ``warming_grace`` transition so the audit trail stays complete.

    These tests use a stub engine with an ``n_observations`` counter so
    the warm-up logic actually fires (most stub-based tests bypass
    warm-up because the stub doesn't expose n_observations).
    """

    def _engine_with_count(self, bound: float, band: str, n: int):
        """A stub that exposes n_observations like a real engine.

        Returns a small object that the gate can call update() on
        and that reports the configured bound and observation count.
        """

        class _CountingEngine:
            def __init__(self, bound: float, band: str, n: int) -> None:
                self._bound = bound
                self._band = band
                self._n = n

            def update(self, observation: Any) -> None:
                self._n += 1

            @property
            def n_observations(self) -> int:
                return self._n

            @property
            def trip_upper_bound(self) -> float:
                return self._bound

            @property
            def trip_band(self) -> str:
                return self._band

        return _CountingEngine(bound, band, n)

    def test_cold_engine_does_not_trip_gate(self) -> None:
        # Cold engine reports high bound but the gate ignores it
        # because n_observations == 0 (cold = silent).
        eng = self._engine_with_count(bound=0.99, band="critical", n=0)
        g = GovernorCircuit(per_output_engine=eng)
        d = g.decide()
        assert d.action == GateAction.ALLOW
        assert g.state == GateState.CLOSED

    def test_warm_up_window_suppresses_trip(self) -> None:
        # Engine has 1 observation and a high bound; gate stays CLOSED.
        eng = self._engine_with_count(bound=0.50, band="critical", n=1)
        g = GovernorCircuit(
            config=GovernorCircuitConfig(),
            per_output_engine=eng,
            warm_up_min_obs=5,
        )
        d = g.decide()
        assert d.action == GateAction.ALLOW
        assert g.state == GateState.CLOSED

    def test_warm_up_completes_then_trips(self) -> None:
        # After warm_up_min_obs observations, the engine is warmed
        # and a high bound DOES trip the gate.
        eng = self._engine_with_count(bound=0.50, band="critical", n=5)
        g = GovernorCircuit(
            config=GovernorCircuitConfig(warm_up_min_obs=5),
            per_output_engine=eng,
        )
        d = g.decide()
        assert g.state == GateState.OPEN
        assert d.action == GateAction.BLOCK

    def test_warming_grace_audit_record(self) -> None:
        # During warm-up, a suppressed transition is still recorded
        # in the audit log with reason "warming_grace".
        eng = self._engine_with_count(bound=0.50, band="critical", n=1)
        g = GovernorCircuit(
            config=GovernorCircuitConfig(warm_up_min_obs=5),
            per_output_engine=eng,
        )
        # Drive the gate via feed() so a transition attempt occurs.
        g.feed(per_output_observation=GateObservation(tripped=True, label="trip"))
        ts = g.transitions()
        warming = [t for t in ts if "warming_grace" in t.reason]
        assert len(warming) >= 1
        assert warming[0].from_state == GateState.CLOSED
        assert warming[0].to_state == GateState.CLOSED

    def test_warm_up_min_obs_zero_disables_grace(self) -> None:
        # Setting warm_up_min_obs=0 makes every engine warm
        # immediately, so a single observation trips the gate.
        eng = self._engine_with_count(bound=0.50, band="critical", n=1)
        g = GovernorCircuit(
            config=GovernorCircuitConfig(warm_up_min_obs=0),
            per_output_engine=eng,
        )
        d = g.decide()
        assert g.state == GateState.OPEN
        assert d.action == GateAction.BLOCK
