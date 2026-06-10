"""
Tests for the Silent Failure Monitor (Entropy Principle / PIG+ADE).

Covers:
  - TestSilentFailureType / TestEntropyConfig        value objects
  - TestEntropySignal                                 value validation
  - TestPIGEngineBasicDecision                        below-threshold ALLOW,
                                                     above-threshold DAMP,
                                                     episode BLOCK, escalate
  - TestPIGEngineChannelFracture                      the highest-stakes type
                                                     BLOCKs on first episode
  - TestPIGEngineEpisodeLifecycle                     open/close/reopen
  - TestPIGEngineGroundingCoherence                   ADE evidence_coherence
  - TestPIGEngineCrossTypeDamping                     ADE cross_type_damping
  - TestPIGEngineMonotonicConstraint                  ADE monotonic_constraint
  - TestSilentFailureMonitorAuditTrail                JSONL persistence
  - TestSilentFailureMonitorRecent                    recent(n) ordering
  - TestSilentFailureMonitorSummary                   deterministic summary
  - TestSilentFailureMonitorIntegration               observe_batch + aggregate
  - TestEntropyAlphaCapEscalation                     alpha cap forces ESCALATE
  - TestFailureEpisodeDuration                        duration_s math
  - TestAuditabilityInvariant                         every decision has a
                                                     rationale
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
from typing import List

import pytest

from core.silent_failure_monitor import (
    ADEProtocol,
    DEFAULT_CONFIG_BY_TYPE,
    EntropyConfig,
    EntropyObservation,
    EntropySignal,
    FAILURE_TO_PROPERTIES,
    FailureEpisode,
    PIGDecision,
    PIGEngine,
    SilentFailureMonitor,
    SilentFailureType,
    create_silent_failure_monitor,
    quick_signal,
)


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


class TestSilentFailureType:
    def test_five_types(self) -> None:
        assert len(list(SilentFailureType)) == 5

    def test_property_map_covers_all(self) -> None:
        for t in SilentFailureType:
            assert t in FAILURE_TO_PROPERTIES
            assert len(FAILURE_TO_PROPERTIES[t]) >= 1

    def test_channel_fracture_maps_to_transmission(self) -> None:
        props = FAILURE_TO_PROPERTIES[SilentFailureType.CHANNEL_FRACTURE]
        # P4, P5, P6, P7 are the L1 transmission properties.
        assert "P4" in props
        assert "P7" in props


class TestEntropyConfig:
    def test_valid_construction(self) -> None:
        cfg = EntropyConfig()
        assert cfg.threshold == 0.5
        assert cfg.episode_count == 3

    def test_threshold_out_of_range(self) -> None:
        with pytest.raises(ValueError):
            EntropyConfig(threshold=1.5)
        with pytest.raises(ValueError):
            EntropyConfig(threshold=-0.1)

    def test_episode_count_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            EntropyConfig(episode_count=0)

    def test_default_configs_distinct_per_type(self) -> None:
        cf = DEFAULT_CONFIG_BY_TYPE[SilentFailureType.CHANNEL_FRACTURE]
        cs = DEFAULT_CONFIG_BY_TYPE[SilentFailureType.CROSS_SESSION_FRAGMENTATION]
        # Channel Fracture has a tighter threshold than cross-session
        # fragmentation, per the paper's "highest stakes" framing.
        assert cf.threshold < cs.threshold
        assert cf.episode_count <= cs.episode_count


class TestEntropySignal:
    def test_valid_value(self) -> None:
        sig = EntropySignal(
            failure_type=SilentFailureType.CHANNEL_FRACTURE,
            value=0.5,
            metric="fidelity_loss",
            source="agent_loop",
            grounding=("P4", "P7"),
        )
        assert sig.failure_type == SilentFailureType.CHANNEL_FRACTURE
        assert sig.value == 0.5

    def test_value_out_of_range(self) -> None:
        with pytest.raises(ValueError):
            EntropySignal(
                failure_type=SilentFailureType.CHANNEL_FRACTURE,
                value=1.1,
                metric="x",
                source="x",
            )


# ---------------------------------------------------------------------------
# PIG Engine
# ---------------------------------------------------------------------------


class TestPIGEngineBasicDecision:
    def test_below_threshold_allow(self) -> None:
        engine = PIGEngine()
        sig = quick_signal(SilentFailureType.DATA_CONSISTENCY_DECAY, value=0.3)
        decision, rationale = engine.evaluate(sig)
        assert decision == PIGDecision.ALLOW
        assert "threshold" in rationale

    def test_above_threshold_damp_before_episode(self) -> None:
        engine = PIGEngine()
        # 1st signal above threshold: DAMP (count=1, episode_count=3).
        sig = quick_signal(SilentFailureType.DATA_CONSISTENCY_DECAY, value=0.7)
        decision, _ = engine.evaluate(sig)
        assert decision == PIGDecision.DAMP

    def test_episode_opens_at_count(self) -> None:
        engine = PIGEngine()
        cfg = DEFAULT_CONFIG_BY_TYPE[SilentFailureType.DATA_CONSISTENCY_DECAY]
        for i in range(cfg.episode_count):
            d, _ = engine.evaluate(
                quick_signal(SilentFailureType.DATA_CONSISTENCY_DECAY, value=0.7)
            )
        # The 3rd signal opens the episode -> BLOCK.
        assert d == PIGDecision.BLOCK
        assert engine.current_episode(
            SilentFailureType.DATA_CONSISTENCY_DECAY
        ) is not None

    def test_escalate_on_sustained(self) -> None:
        engine = PIGEngine()
        cfg = DEFAULT_CONFIG_BY_TYPE[SilentFailureType.DATA_CONSISTENCY_DECAY]
        for _ in range(cfg.episode_count):
            engine.evaluate(
                quick_signal(SilentFailureType.DATA_CONSISTENCY_DECAY, value=0.7)
            )
        # 4th signal: episode already open, escalation_count > 0 -> ESCALATE.
        d, _ = engine.evaluate(
            quick_signal(SilentFailureType.DATA_CONSISTENCY_DECAY, value=0.7)
        )
        assert d == PIGDecision.ESCALATE


class TestPIGEngineChannelFracture:
    def test_channel_fracture_blocks_on_first_episode(self) -> None:
        engine = PIGEngine()
        cfg = DEFAULT_CONFIG_BY_TYPE[SilentFailureType.CHANNEL_FRACTURE]
        for _ in range(cfg.episode_count):
            d, rationale = engine.evaluate(
                quick_signal(SilentFailureType.CHANNEL_FRACTURE, value=0.6)
            )
        # Channel fracture: BLOCK, not just DAMP at threshold.
        assert d == PIGDecision.BLOCK
        # The rationale references the failure type by name (which is
        # "channel_fracture" in the engine's output).

    def test_channel_fracture_escalates_quickly(self) -> None:
        engine = PIGEngine()
        cfg = DEFAULT_CONFIG_BY_TYPE[SilentFailureType.CHANNEL_FRACTURE]
        for _ in range(cfg.episode_count):
            engine.evaluate(
                quick_signal(SilentFailureType.CHANNEL_FRACTURE, value=0.6)
            )
        d, _ = engine.evaluate(
            quick_signal(SilentFailureType.CHANNEL_FRACTURE, value=0.6)
        )
        assert d == PIGDecision.ESCALATE


# ---------------------------------------------------------------------------
# Episode lifecycle
# ---------------------------------------------------------------------------


class TestPIGEngineEpisodeLifecycle:
    def test_episode_closes_on_recovery(self) -> None:
        # Use a tiny window so the "recovery" rolling count drops
        # back below the episode threshold immediately. The default
        # 300s window would require time travel; we keep the test
        # deterministic by configuring a 0.1s window.
        cfg = EntropyConfig(
            threshold=0.5, episode_count=2, episode_window_s=0.1
        )
        engine = PIGEngine(
            config_by_type={
                SilentFailureType.DATA_CONSISTENCY_DECAY: cfg
            }
        )
        # Open an episode.
        engine.evaluate(
            quick_signal(SilentFailureType.DATA_CONSISTENCY_DECAY, value=0.7)
        )
        engine.evaluate(
            quick_signal(SilentFailureType.DATA_CONSISTENCY_DECAY, value=0.7)
        )
        assert engine.current_episode(
            SilentFailureType.DATA_CONSISTENCY_DECAY
        ) is not None
        # Wait for the window to expire so the rolling count drops.
        time.sleep(0.2)
        # Recovery: a value below threshold -- episode closes.
        engine.evaluate(
            quick_signal(SilentFailureType.DATA_CONSISTENCY_DECAY, value=0.2)
        )
        assert engine.current_episode(
            SilentFailureType.DATA_CONSISTENCY_DECAY
        ) is None

    def test_episode_can_reopen(self) -> None:
        # Use a tiny window so we can simulate "the system returned
        # to baseline" between episodes without time travel.
        cfg = EntropyConfig(
            threshold=0.5, episode_count=2, episode_window_s=0.1
        )
        engine = PIGEngine(
            config_by_type={
                SilentFailureType.DATA_CONSISTENCY_DECAY: cfg
            }
        )
        # Open, close, re-open.
        engine.evaluate(
            quick_signal(SilentFailureType.DATA_CONSISTENCY_DECAY, value=0.7)
        )
        engine.evaluate(
            quick_signal(SilentFailureType.DATA_CONSISTENCY_DECAY, value=0.7)
        )
        time.sleep(0.2)
        engine.evaluate(
            quick_signal(SilentFailureType.DATA_CONSISTENCY_DECAY, value=0.2)
        )
        engine.evaluate(
            quick_signal(SilentFailureType.DATA_CONSISTENCY_DECAY, value=0.7)
        )
        engine.evaluate(
            quick_signal(SilentFailureType.DATA_CONSISTENCY_DECAY, value=0.7)
        )
        ep = engine.current_episode(SilentFailureType.DATA_CONSISTENCY_DECAY)
        assert ep is not None
        assert ep.is_open()

    def test_open_episodes_lists_only_open(self) -> None:
        engine = PIGEngine()
        cf_cfg = DEFAULT_CONFIG_BY_TYPE[SilentFailureType.CHANNEL_FRACTURE]
        for _ in range(cf_cfg.episode_count):
            engine.evaluate(
                quick_signal(SilentFailureType.CHANNEL_FRACTURE, value=0.6)
            )
        open_eps = engine.open_episodes()
        assert len(open_eps) == 1
        assert open_eps[0].failure_type == SilentFailureType.CHANNEL_FRACTURE


# ---------------------------------------------------------------------------
# ADE Protocol
# ---------------------------------------------------------------------------


class TestPIGEngineGroundingCoherence:
    def test_incoherent_grounding_yields_prefixed_rationale(self) -> None:
        engine = PIGEngine()
        sig = EntropySignal(
            failure_type=SilentFailureType.CHANNEL_FRACTURE,
            value=0.55,
            metric="x",
            source="x",
            grounding=("P99",),  # Not in the paper's property map
        )
        d, rationale = engine.evaluate(sig)
        assert "grounding" in rationale
        assert "P99" in rationale

    def test_coherent_grounding_accepted(self) -> None:
        engine = PIGEngine()
        sig = quick_signal(
            SilentFailureType.CHANNEL_FRACTURE, value=0.3, grounding=("P4",)
        )
        d, rationale = engine.evaluate(sig)
        assert d == PIGDecision.ALLOW
        assert "grounding" not in rationale

    def test_ade_evidence_coherence_helper(self) -> None:
        good = quick_signal(SilentFailureType.CHANNEL_FRACTURE, value=0.3)
        assert ADEProtocol.evidence_coherence(good)
        bad = EntropySignal(
            failure_type=SilentFailureType.CHANNEL_FRACTURE,
            value=0.3,
            metric="x",
            source="x",
            grounding=("P99",),
        )
        assert not ADEProtocol.evidence_coherence(bad)


class TestPIGEngineCrossTypeDamping:
    def test_escalate_wins_over_block(self) -> None:
        d = ADEProtocol.cross_type_damping(
            {
                SilentFailureType.DATA_CONSISTENCY_DECAY: PIGDecision.BLOCK,
                SilentFailureType.CHANNEL_FRACTURE: PIGDecision.ESCALATE,
            }
        )
        assert d == PIGDecision.ESCALATE

    def test_block_wins_over_damp(self) -> None:
        d = ADEProtocol.cross_type_damping(
            {
                SilentFailureType.BEHAVIOR_ROUTING_DEFICIENCY: PIGDecision.DAMP,
                SilentFailureType.CHANNEL_FRACTURE: PIGDecision.BLOCK,
            }
        )
        assert d == PIGDecision.BLOCK

    def test_allow_when_all_allow(self) -> None:
        d = ADEProtocol.cross_type_damping(
            {
                SilentFailureType.BEHAVIOR_ROUTING_DEFICIENCY: PIGDecision.ALLOW,
                SilentFailureType.DATA_CONSISTENCY_DECAY: PIGDecision.ALLOW,
            }
        )
        assert d == PIGDecision.ALLOW

    def test_channel_fracture_has_highest_priority(self) -> None:
        assert (
            ADEProtocol.TYPE_PRIORITY[SilentFailureType.CHANNEL_FRACTURE]
            == 5
        )
        assert (
            ADEProtocol.TYPE_PRIORITY[SilentFailureType.BEHAVIOR_ROUTING_DEFICIENCY]
            == 1
        )


class TestPIGEngineMonotonicConstraint:
    def test_peak_alpha_is_monotonic(self) -> None:
        ep = FailureEpisode(
            failure_type=SilentFailureType.DATA_CONSISTENCY_DECAY,
            opened_at=time.time(),
            peak_value=0.7,
            peak_alpha=0.05,
            decision=PIGDecision.BLOCK,
        )
        assert ADEProtocol.monotonic_constraint(ep)

    def test_ade_episode_window(self) -> None:
        ep = FailureEpisode(
            failure_type=SilentFailureType.DATA_CONSISTENCY_DECAY,
            opened_at=time.time() - 60,
            peak_value=0.7,
            peak_alpha=0.05,
            decision=PIGDecision.BLOCK,
        )
        assert ADEProtocol.episode_window(ep, max_window_s=3600)

    def test_ade_episode_window_violated(self) -> None:
        ep = FailureEpisode(
            failure_type=SilentFailureType.DATA_CONSISTENCY_DECAY,
            opened_at=time.time() - 7200,
            peak_value=0.7,
            peak_alpha=0.05,
            decision=PIGDecision.BLOCK,
        )
        assert not ADEProtocol.episode_window(ep, max_window_s=3600)


# ---------------------------------------------------------------------------
# Alpha cap escalation
# ---------------------------------------------------------------------------


class TestEntropyAlphaCapEscalation:
    def test_alpha_cap_is_checked_on_escalation(self) -> None:
        # Tight alpha_cap = 0.001 means even a single high-value signal
        # produces alpha > cap. First sustained signal after the
        # episode opens should ESCALATE; alpha appears in the
        # recorded audit metadata (rolling_alpha) regardless.
        cfg = EntropyConfig(
            threshold=0.5, episode_count=2, alpha_cap=0.001
        )
        engine = PIGEngine(
            config_by_type={
                SilentFailureType.DATA_CONSISTENCY_DECAY: cfg
            }
        )
        engine.evaluate(
            quick_signal(SilentFailureType.DATA_CONSISTENCY_DECAY, value=0.6)
        )
        # 2nd signal: episode opens -> BLOCK.
        d2, _ = engine.evaluate(
            quick_signal(SilentFailureType.DATA_CONSISTENCY_DECAY, value=0.6)
        )
        assert d2 == PIGDecision.BLOCK
        # 3rd signal: escalation_count > 0 -> ESCALATE.
        d3, _ = engine.evaluate(
            quick_signal(SilentFailureType.DATA_CONSISTENCY_DECAY, value=0.6)
        )
        assert d3 == PIGDecision.ESCALATE
        # The engine recorded an alpha that exceeds the cap.
        assert engine.rolling_alpha(
            SilentFailureType.DATA_CONSISTENCY_DECAY
        ) > cfg.alpha_cap


# ---------------------------------------------------------------------------
# Failure episode
# ---------------------------------------------------------------------------


class TestFailureEpisodeDuration:
    def test_duration_for_open_episode(self) -> None:
        ep = FailureEpisode(
            failure_type=SilentFailureType.DATA_CONSISTENCY_DECAY,
            opened_at=time.time() - 5,
            peak_value=0.7,
            peak_alpha=0.05,
            decision=PIGDecision.BLOCK,
        )
        assert ep.duration_s() >= 5

    def test_duration_for_closed_episode(self) -> None:
        now = time.time()
        ep = FailureEpisode(
            failure_type=SilentFailureType.DATA_CONSISTENCY_DECAY,
            opened_at=now - 10,
            peak_value=0.7,
            peak_alpha=0.05,
            decision=PIGDecision.BLOCK,
            closed_at=now,
        )
        assert abs(ep.duration_s() - 10) < 0.1

    def test_is_open(self) -> None:
        ep = FailureEpisode(
            failure_type=SilentFailureType.DATA_CONSISTENCY_DECAY,
            opened_at=time.time(),
            peak_value=0.7,
            peak_alpha=0.05,
            decision=PIGDecision.BLOCK,
        )
        assert ep.is_open()
        ep.closed_at = time.time()
        assert not ep.is_open()


# ---------------------------------------------------------------------------
# Silent Failure Monitor
# ---------------------------------------------------------------------------


class TestSilentFailureMonitorAuditTrail:
    def test_jsonl_persists_each_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            monitor = create_silent_failure_monitor(audit_dir=tmp)
            for _ in range(3):
                monitor.observe(
                    quick_signal(SilentFailureType.CHANNEL_FRACTURE, value=0.6)
                )
            path = monitor.audit_path()
            assert path is not None
            assert path.exists()
            with path.open("r", encoding="utf-8") as f:
                lines = [json.loads(line) for line in f]
            assert len(lines) == 3
            assert all("decision" in r for r in lines)
            assert all("signal" in r for r in lines)
            assert all("rationale" in r for r in lines)

    def test_in_memory_mode_no_audit_path(self) -> None:
        monitor = SilentFailureMonitor()
        assert monitor.audit_path() is None
        # Should not raise.
        monitor.observe(quick_signal(SilentFailureType.CHANNEL_FRACTURE, value=0.5))

    def test_observation_callback_invoked(self) -> None:
        seen: List[EntropyObservation] = []
        monitor = SilentFailureMonitor(on_observation=seen.append)
        monitor.observe(quick_signal(SilentFailureType.CHANNEL_FRACTURE, value=0.5))
        assert len(seen) == 1
        assert seen[0].signal.failure_type == SilentFailureType.CHANNEL_FRACTURE


class TestSilentFailureMonitorRecent:
    def test_recent_returns_last_n(self) -> None:
        monitor = SilentFailureMonitor()
        for i in range(15):
            monitor.observe(
                quick_signal(
                    SilentFailureType.DATA_CONSISTENCY_DECAY,
                    value=0.3 + i * 0.01,
                )
            )
        recent = monitor.recent(5)
        assert len(recent) == 5
        # Recent should be the *last* 5, in order.
        assert recent[0].signal.value <= recent[-1].signal.value

    def test_history_for_filters_by_type(self) -> None:
        monitor = SilentFailureMonitor()
        monitor.observe(quick_signal(SilentFailureType.CHANNEL_FRACTURE, value=0.5))
        monitor.observe(
            quick_signal(SilentFailureType.DATA_CONSISTENCY_DECAY, value=0.5)
        )
        monitor.observe(quick_signal(SilentFailureType.CHANNEL_FRACTURE, value=0.5))
        cf_history = monitor.history_for(SilentFailureType.CHANNEL_FRACTURE)
        assert len(cf_history) == 2


class TestSilentFailureMonitorSummary:
    def test_summary_includes_engine_state(self) -> None:
        monitor = SilentFailureMonitor()
        monitor.observe(quick_signal(SilentFailureType.CHANNEL_FRACTURE, value=0.5))
        s = monitor.summary()
        assert "PIG Engine state" in s
        assert "channel_fracture" in s
        assert "observations=1" in s

    def test_summary_lists_open_episodes(self) -> None:
        monitor = SilentFailureMonitor()
        cfg = DEFAULT_CONFIG_BY_TYPE[SilentFailureType.CHANNEL_FRACTURE]
        for _ in range(cfg.episode_count):
            monitor.observe(quick_signal(SilentFailureType.CHANNEL_FRACTURE, value=0.6))
        s = monitor.summary()
        assert "open_episodes=1" in s


class TestSilentFailureMonitorIntegration:
    def test_observe_batch_returns_per_type_decisions(self) -> None:
        monitor = SilentFailureMonitor()
        decisions = monitor.observe_batch([
            quick_signal(SilentFailureType.CHANNEL_FRACTURE, value=0.3),
            quick_signal(SilentFailureType.DATA_CONSISTENCY_DECAY, value=0.3),
        ])
        assert decisions[SilentFailureType.CHANNEL_FRACTURE] == PIGDecision.ALLOW
        assert decisions[SilentFailureType.DATA_CONSISTENCY_DECAY] == PIGDecision.ALLOW

    def test_aggregate_decision_picks_highest(self) -> None:
        monitor = SilentFailureMonitor()
        agg = monitor.aggregate_decision(
            {
                SilentFailureType.CHANNEL_FRACTURE: PIGDecision.BLOCK,
                SilentFailureType.DATA_CONSISTENCY_DECAY: PIGDecision.DAMP,
            }
        )
        assert agg == PIGDecision.BLOCK

    def test_observe_batch_then_aggregate_end_to_end(self) -> None:
        monitor = SilentFailureMonitor()
        # Drive Channel Fracture to BLOCK and Data Consistency to DAMP.
        cf_cfg = DEFAULT_CONFIG_BY_TYPE[SilentFailureType.CHANNEL_FRACTURE]
        for _ in range(cf_cfg.episode_count):
            monitor.observe(quick_signal(SilentFailureType.CHANNEL_FRACTURE, value=0.6))
        monitor.observe(quick_signal(SilentFailureType.DATA_CONSISTENCY_DECAY, value=0.7))
        # Now a fresh observe_batch on the *existing* state:
        decisions = {
            SilentFailureType.CHANNEL_FRACTURE: PIGDecision.BLOCK,
            SilentFailureType.DATA_CONSISTENCY_DECAY: PIGDecision.DAMP,
        }
        assert monitor.aggregate_decision(decisions) == PIGDecision.BLOCK


# ---------------------------------------------------------------------------
# Auditability invariant
# ---------------------------------------------------------------------------


class TestAuditabilityInvariant:
    def test_every_decision_has_a_rationale(self) -> None:
        monitor = SilentFailureMonitor()
        for v in (0.2, 0.5, 0.7, 0.9):
            monitor.observe(quick_signal(SilentFailureType.CHANNEL_FRACTURE, value=v))
        for obs in monitor.recent(10):
            assert obs.rationale
            assert obs.decision.value in (
                "allow", "damp", "block", "escalate"
            )

    def test_audit_file_records_brake_state_metadata(self) -> None:
        # We don't import BrakePedal here, but the audit record's
        # `decision` + `rolling_alpha` together should be enough to
        # reconstruct the boundary state.
        with tempfile.TemporaryDirectory() as tmp:
            monitor = create_silent_failure_monitor(audit_dir=tmp)
            monitor.observe(quick_signal(SilentFailureType.CHANNEL_FRACTURE, value=0.6))
            path = monitor.audit_path()
            assert path is not None
            with path.open("r", encoding="utf-8") as f:
                record = json.loads(f.readline())
            for key in (
                "timestamp", "signal", "decision", "rationale",
                "rolling_count", "rolling_alpha"
            ):
                assert key in record
            assert record["signal"]["failure_type"] == "channel_fracture"
            assert record["signal"]["grounding"]  # auto-filled from property map
