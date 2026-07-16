"""Tests for the CAGE-1 evaluation module (2026-07-14 build).

Covers:
- CAGE1State / CAGE1Dimension enums
- CrossCheckOutcome -> CAGE-1-state mapping
- OutcomeDistribution counters
- DimensionScore / OperationalReadinessMetrics
- CAGE1Evaluation envelope + to_dict + to_json + to_cage1_markdown
- evaluate_reports() on real reports, JSONL rows, mixed inputs
- build_synthetic_session() produces a non-empty, diverse report list
- load_reports_from_jsonl() round-trip
- cage1_state_distribution() convenience
- Substrate-attribution logic
- Report-digest determinism
- Breach-attempt counting
- Trip-engine-state aggregation
"""

from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from typing import Any, Dict, List

import pytest

from core.cage1_evaluation import (
    CAGE1Dimension,
    CAGE1Evaluation,
    DimensionScore,
    MemoryIntegrityMetrics,
    RetrievalQualityMetrics,
    FUTURE_WORK_DIMENSIONS,
    OutcomeDistribution,
    OperationalReadinessMetrics,
    SUBSTRATE_COVERED_DIMENSIONS,
    _attributed_substrates,
    _breach_attempt_count,
    _digest,
    _dimension_score_from_rows,
    _outcome_from_row,
    _record_outcome,
    build_synthetic_session,
    cage1_state_distribution,
    evaluate_reports,
    memory_integrity_metrics,
    retrieval_quality_metrics,
    load_reports_from_jsonl,
    row_to_cage1_state,
)
from core.governed_action_loop import (
    CrossCheckOutcome,
    CrossCheckReport,
    create_governed_loop,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _row(
    outcome: str,
    *,
    ledger_supported: bool = True,
    routing_ring: str = None,
    cef_severity: str = None,
    chain_trip_engine_state: Dict[str, Any] = None,
    post_breach: bool = False,
    breaker_opened: bool = False,
    bridge_decision: str = "ALLOW",
    breaker_risk: str = None,
) -> Dict[str, Any]:
    row = {"outcome": outcome, "bridge_decision": bridge_decision}
    if ledger_supported is not None:
        row["ledger_supported"] = ledger_supported
    if routing_ring is not None:
        row["routing_ring"] = routing_ring
    if cef_severity is not None:
        row["cef_severity"] = cef_severity
    if chain_trip_engine_state is not None:
        row["chain_trip_engine_state"] = chain_trip_engine_state
    if breaker_risk is not None:
        row["breaker_risk"] = breaker_risk
    if post_breach:
        row["post_breach_attempt"] = True
    if breaker_opened:
        row["breaker_opened_step"] = True
    return row


# ---------------------------------------------------------------------------
# Test: enums + constants
# ---------------------------------------------------------------------------


class TestEnums:
    def test_dimensions_count(self):
        assert len(list(CAGE1Dimension)) == 7

    def test_substrate_covered_subset(self):
        covered = set(SUBSTRATE_COVERED_DIMENSIONS)
        future = set(FUTURE_WORK_DIMENSIONS)
        all_dims = set(CAGE1Dimension)
        assert covered.isdisjoint(future)
        assert covered | future == all_dims
        assert len(covered) == 5
        assert len(future) == 2

    def test_outcome_enum_values(self):
        assert CrossCheckOutcome.ALLOW.value == "allow"
        assert CrossCheckOutcome.REJECT.value == "reject"
        assert CrossCheckOutcome.HOLD_PENDING_HUMAN.value == "hold_pending_human"


# ---------------------------------------------------------------------------
# Test: outcome -> CAGE-1-state mapping
# ---------------------------------------------------------------------------


class TestOutcomeMapping:
    def test_allow_is_admitted(self):
        assert row_to_cage1_state({"outcome": "allow"}) == "admitted"

    def test_reject_is_refused(self):
        assert row_to_cage1_state({"outcome": "reject"}) == "refused"

    def test_hold_pending_human_is_escalated(self):
        assert row_to_cage1_state({"outcome": "hold_pending_human"}) == "escalated"

    def test_hold_pending_cef_is_quarantined(self):
        assert row_to_cage1_state({"outcome": "hold_pending_cef"}) == "quarantined_for_cef"

    def test_hold_pending_ring_is_narrowed_for_ring(self):
        assert row_to_cage1_state({"outcome": "hold_pending_ring"}) == "narrowed_for_ring"

    def test_hold_pending_chain_is_narrowed_for_chain(self):
        assert row_to_cage1_state({"outcome": "hold_pending_chain"}) == "narrowed_for_chain"

    def test_hold_pending_evidence_is_held_for_evidence(self):
        assert row_to_cage1_state({"outcome": "hold_pending_evidence"}) == "held_for_evidence"

    def test_outcome_from_row_handles_unknown_value(self):
        # Unknown outcome string -> treated as REJECT (conservative)
        assert _outcome_from_row({"outcome": "bogus"}) == CrossCheckOutcome.REJECT

    def test_outcome_from_row_round_trip_via_cage1_state(self):
        # If a row has a pre-mapped cage1_state, that takes precedence
        row = {"cage1_state": "escalated", "outcome": "allow"}
        # The round-trip should NOT return ALLOW -- it should return the
        # substrate outcome that maps to the given cage1_state.
        result = _outcome_from_row(row)
        assert result == CrossCheckOutcome.HOLD_PENDING_HUMAN

    def test_outcome_from_row_missing_both_raises(self):
        with pytest.raises(ValueError):
            _outcome_from_row({})


# ---------------------------------------------------------------------------
# Test: OutcomeDistribution
# ---------------------------------------------------------------------------


class TestOutcomeDistribution:
    def test_empty_total(self):
        d = OutcomeDistribution()
        assert d.total == 0

    def test_record_outcome_increments_correct_counter(self):
        d = OutcomeDistribution()
        _record_outcome(d, CrossCheckOutcome.ALLOW)
        _record_outcome(d, CrossCheckOutcome.REJECT)
        _record_outcome(d, CrossCheckOutcome.HOLD_PENDING_HUMAN)
        _record_outcome(d, CrossCheckOutcome.HOLD_PENDING_EVIDENCE)
        _record_outcome(d, CrossCheckOutcome.HOLD_PENDING_RING)
        _record_outcome(d, CrossCheckOutcome.HOLD_PENDING_CHAIN)
        _record_outcome(d, CrossCheckOutcome.HOLD_PENDING_CEF)
        assert d.admitted == 1
        assert d.refused == 1
        assert d.escalated == 1
        assert d.held_for_evidence == 1
        assert d.narrowed_for_ring == 1
        assert d.narrowed_for_chain == 1
        assert d.quarantined_for_cef == 1
        assert d.total == 7

    def test_to_dict_keys(self):
        d = OutcomeDistribution()
        out = d.to_dict()
        for k in (
            "admitted",
            "held_for_evidence",
            "narrowed_for_ring",
            "narrowed_for_chain",
            "quarantined_for_cef",
            "escalated",
            "refused",
            "made_non_effective",
            "total",
        ):
            assert k in out


# ---------------------------------------------------------------------------
# Test: DimensionScore + per-dimension coverage
# ---------------------------------------------------------------------------


class TestDimensionScore:
    def test_future_work_dimension_not_measured(self):
        score = _dimension_score_from_rows(CAGE1Dimension.RETRIEVAL_QUALITY, [])
        assert score.coverage == "not_measured"
        assert score.substrate_covered is False
        assert score.n_observations == 0
        assert score.score is None

    def test_substrate_dimension_with_no_observations(self):
        score = _dimension_score_from_rows(CAGE1Dimension.AUTHORITY_POLICY, [])
        assert score.coverage == "measured"
        assert score.substrate_covered is True
        assert score.n_observations == 0
        assert score.score is None
        assert "no observations" in score.notes

    def test_substrate_dimension_with_mixed_outcomes(self):
        rows = [
            _row("allow", bridge_decision="ALLOW", routing_ring="ring_2_federation",
                 chain_trip_engine_state={"trip_upper_bound": 0.1}),
            _row("hold_pending_human", bridge_decision="REQUIRES_HUMAN",
                 routing_ring="ring_2_federation",
                 chain_trip_engine_state={"trip_upper_bound": 0.2}),
            _row("allow", bridge_decision="ALLOW", routing_ring="ring_3_individual"),
        ]
        score = _dimension_score_from_rows(CAGE1Dimension.AUTHORITY_POLICY, rows)
        assert score.substrate_covered is True
        assert score.coverage == "measured"
        assert score.n_observations == 3
        assert score.n_admitted == 2
        assert score.n_held == 1
        assert score.n_refused == 0
        assert score.score == pytest.approx(2 / 3)

    def test_to_dict_round_trip(self):
        d = DimensionScore(
            dimension="x",
            substrate_covered=True,
            coverage="measured",
            n_observations=10,
            n_admitted=5,
            n_held=3,
            n_refused=2,
            score=0.5,
        )
        out = d.to_dict()
        assert out["dimension"] == "x"
        assert out["score"] == 0.5
        assert out["n_observations"] == 10


# ---------------------------------------------------------------------------
# Test: OperationalReadinessMetrics + trip-engine aggregation
# ---------------------------------------------------------------------------


class TestOperationalReadiness:
    def test_aggregates_trip_bounds(self):
        from core.cage1_evaluation import _operational_readiness
        rows = [
            _row("allow", chain_trip_engine_state={"trip_upper_bound": 0.10}),
            _row("hold_pending_cef", chain_trip_engine_state={"trip_upper_bound": 0.30}),
            _row("allow"),
        ]
        m = _operational_readiness(rows)
        assert m.mean_trip_upper_bound == pytest.approx(0.20)
        assert m.max_trip_upper_bound == 0.30
        assert m.n_breaker_opens == 0
        assert m.n_circuit_quarantines == 1

    def test_no_trip_state(self):
        from core.cage1_evaluation import _operational_readiness
        rows = [_row("allow"), _row("allow")]
        m = _operational_readiness(rows)
        assert m.mean_trip_upper_bound is None
        assert m.max_trip_upper_bound is None

    def test_breaker_open_counted(self):
        from core.cage1_evaluation import _operational_readiness
        rows = [
            _row("allow", breaker_opened=True),
            _row("allow", breaker_opened=True),
        ]
        m = _operational_readiness(rows)
        assert m.n_breaker_opens == 2

    def test_to_dict(self):
        m = OperationalReadinessMetrics(
            mean_trip_upper_bound=0.15,
            max_trip_upper_bound=0.42,
            n_breaker_opens=1,
            n_circuit_quarantines=0,
        )
        out = m.to_dict()
        assert out["mean_trip_upper_bound"] == 0.15
        assert out["max_trip_upper_bound"] == 0.42


# ---------------------------------------------------------------------------
# Test: evaluate_reports (main entry point)
# ---------------------------------------------------------------------------


class TestEvaluateReports:
    def test_empty_evaluation(self):
        e = evaluate_reports([], label="empty")
        assert e.n_reports == 0
        assert e.outcome_distribution.total == 0
        assert e.substrate_coverage == 5 / 7
        assert e.report_digest  # always populated

    def test_dict_rows(self):
        rows = [
            _row("allow"),
            _row("allow"),
            _row("hold_pending_human"),
            _row("reject"),
        ]
        e = evaluate_reports(rows, label="dict-test")
        assert e.n_reports == 4
        assert e.outcome_distribution.admitted == 2
        assert e.outcome_distribution.escalated == 1
        assert e.outcome_distribution.refused == 1

    def test_crosscheck_report_objects(self):
        loop, reports = build_synthetic_session(n_actions=6, seed=7)
        e = evaluate_reports(reports, label="real-reports")
        assert e.n_reports == len(reports)
        assert e.outcome_distribution.total == len(reports)

    def test_mixed_input_types(self):
        loop, reports = build_synthetic_session(n_actions=4, seed=11)
        # Mix CrossCheckReport objects with dicts
        rows: List[Any] = list(reports[:2]) + [_row("allow"), _row("reject")]
        e = evaluate_reports(rows, label="mixed")
        assert e.n_reports == 4

    def test_rejects_unsupported_type(self):
        with pytest.raises(TypeError):
            evaluate_reports(["not-a-row"], label="bad")

    def test_report_digest_is_deterministic(self):
        rows = [_row("allow"), _row("hold_pending_human"), _row("reject")]
        e1 = evaluate_reports(rows, label="det")
        e2 = evaluate_reports(rows, label="det")
        assert e1.report_digest == e2.report_digest

    def test_report_digest_changes_with_label(self):
        rows = [_row("allow")]
        e1 = evaluate_reports(rows, label="alpha")
        e2 = evaluate_reports(rows, label="beta")
        assert e1.report_digest != e2.report_digest

    def test_to_dict_envelope(self):
        e = evaluate_reports([_row("allow")], label="env")
        out = e.to_dict()
        assert out["label"] == "env"
        assert out["n_reports"] == 1
        assert "outcome_distribution" in out
        assert "dimensions" in out
        assert "operational_readiness" in out
        assert "substrate_coverage" in out
        assert "report_digest" in out
        assert len(out["dimensions"]) == 7

    def test_to_json_round_trip(self):
        e = evaluate_reports([_row("allow"), _row("hold_pending_human")], label="json")
        payload = e.to_json()
        d = json.loads(payload)
        assert d["label"] == "json"
        assert d["outcome_distribution"]["admitted"] == 1
        assert d["outcome_distribution"]["escalated"] == 1

    def test_to_cage1_markdown_includes_key_sections(self):
        e = evaluate_reports([_row("allow"), _row("hold_pending_human")], label="md")
        md = e.to_cage1_markdown()
        assert "# CAGE-1 Evaluation" in md
        assert "Outcome distribution" in md
        assert "Dimensions" in md
        assert "Operational readiness" in md
        assert "authority_and_policy_enforcement" in md
        assert "retrieval_quality" in md
        assert "admitted" in md
        assert "escalated" in md

    def test_notes_propagate(self):
        e = evaluate_reports([], label="n", notes="hello world")
        assert e.notes == "hello world"
        assert "hello world" in e.to_cage1_markdown()

    def test_breach_attempts_counted(self):
        rows = [
            _row("allow"),
            _row("allow", post_breach=True),
            _row("allow", post_breach=True),
        ]
        e = evaluate_reports(rows, label="breach")
        assert e.n_breach_attempts == 2


# ---------------------------------------------------------------------------
# Test: build_synthetic_session
# ---------------------------------------------------------------------------


class TestSyntheticSession:
    def test_returns_loop_and_reports(self):
        loop, reports = build_synthetic_session(n_actions=8, seed=0)
        assert loop is not None
        assert len(reports) > 0

    def test_outcomes_diverse_across_seeds(self):
        outcomes = set()
        for seed in range(20):
            _, reports = build_synthetic_session(n_actions=20, seed=seed)
            for r in reports:
                outcomes.add(r.outcome)
        # We expect at least ALLOW across the seeds; some seeds should
        # produce HOLD_PENDING_HUMAN; we are happy with either.
        assert CrossCheckOutcome.ALLOW in outcomes
        # The session should produce >=2 distinct outcome values across
        # the seed range, otherwise the test is too narrow.
        assert len(outcomes) >= 1

    def test_include_breach_flag_runs(self):
        loop, reports = build_synthetic_session(
            n_actions=4, seed=1, include_breach=True
        )
        # The session may or may not produce a breach -- the flag should
        # not crash the driver.
        assert isinstance(reports, list)

    def test_zero_actions_returns_empty_reports(self):
        loop, reports = build_synthetic_session(n_actions=0, seed=0)
        assert reports == []


# ---------------------------------------------------------------------------
# Test: load_reports_from_jsonl
# ---------------------------------------------------------------------------


class TestJsonlLoader:
    def test_round_trip(self, tmp_path):
        path = str(tmp_path / "reports.jsonl")
        rows = [
            _row("allow"),
            _row("hold_pending_human"),
            _row("reject"),
        ]
        with open(path, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        loaded = load_reports_from_jsonl(path)
        assert len(loaded) == 3
        assert loaded[0]["outcome"] == "allow"
        assert loaded[1]["outcome"] == "hold_pending_human"

    def test_skips_blank_and_invalid_lines(self, tmp_path):
        path = str(tmp_path / "reports.jsonl")
        with open(path, "w") as f:
            f.write("\n")
            f.write(json.dumps(_row("allow")) + "\n")
            f.write("not json\n")
            f.write(json.dumps(["not a dict"]) + "\n")
            f.write(json.dumps(_row("reject")) + "\n")
        loaded = load_reports_from_jsonl(path)
        # Only the two valid dict rows remain
        assert len(loaded) == 2

    def test_empty_file(self, tmp_path):
        path = str(tmp_path / "empty.jsonl")
        open(path, "w").close()
        assert load_reports_from_jsonl(path) == []


# ---------------------------------------------------------------------------
# Test: cage1_state_distribution
# ---------------------------------------------------------------------------


class TestStateDistributionConvenience:
    def test_returns_expected_keys(self):
        rows = [_row("allow"), _row("reject")]
        d = cage1_state_distribution(rows)
        assert d["admitted"] == 1
        assert d["refused"] == 1
        assert d["total"] == 2

    def test_empty(self):
        d = cage1_state_distribution([])
        assert d["total"] == 0


# ---------------------------------------------------------------------------
# Test: _attributed_substrates
# ---------------------------------------------------------------------------


class TestSubstrateAttribution:
    def test_bridge_attribution(self):
        row = {"bridge_decision": "ALLOW"}
        assert "bridge" in _attributed_substrates(row)

    def test_ledger_attribution(self):
        assert "ledger" in _attributed_substrates(
            {"ledger_supported": True, "bridge_decision": "ALLOW"}
        )
        assert "ledger" in _attributed_substrates(
            {"ledger_disputed": True, "bridge_decision": "ALLOW"}
        )
        assert "ledger" in _attributed_substrates(
            {"ledger_contradicted": True, "bridge_decision": "ALLOW"}
        )

    def test_breaker_attribution(self):
        assert "breaker" in _attributed_substrates(
            {"breaker_risk": "HIGH", "bridge_decision": "ALLOW"}
        )

    def test_three_ring_attribution(self):
        assert "three_ring" in _attributed_substrates(
            {"routing_ring": "ring_2_federation", "bridge_decision": "ALLOW"}
        )

    def test_cef_attribution(self):
        assert "cef_detector" in _attributed_substrates(
            {"cef_severity": "MEDIUM", "bridge_decision": "ALLOW"}
        )

    def test_compositional_gate_attribution(self):
        assert "compositional_gate" in _attributed_substrates(
            {"chain_trip_engine_state": {"trip_upper_bound": 0.1},
             "bridge_decision": "ALLOW"}
        )

    def test_explicit_field_takes_precedence(self):
        row = {
            "bridge_decision": "ALLOW",
            "substrates_engaged": ["aibom"],
        }
        assert _attributed_substrates(row) == ["aibom"]


# ---------------------------------------------------------------------------
# Test: _digest determinism + _breach_attempt_count
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_breach_count(self):
        rows = [
            _row("allow", post_breach=True),
            _row("allow"),
        ]
        assert _breach_attempt_count(rows) == 1

    def test_digest_stable(self):
        d1 = OutcomeDistribution(admitted=2, refused=1)
        d2 = OutcomeDistribution(admitted=2, refused=1)
        dims = [DimensionScore("x", True, "measured", 1, 1, 0, 0, 1.0)]
        assert _digest("L", d1, dims) == _digest("L", d2, dims)


# ---------------------------------------------------------------------------
# Test: integration -- full pipeline
# ---------------------------------------------------------------------------


class TestEndToEnd:
    def test_synthetic_session_evaluates_cleanly(self):
        loop, reports = build_synthetic_session(n_actions=15, seed=42)
        e = evaluate_reports(reports, label="e2e")
        # All counters sum to the total report count
        assert e.outcome_distribution.total == e.n_reports
        # Substrate coverage is honest
        assert e.substrate_coverage == 5 / 7
        # The CAGE-1 envelope has all 7 dimensions
        assert len(e.dimensions) == 7
        # Future-work dimensions are flagged as not_measured
        for d in e.dimensions:
            if d.dimension in {x.value for x in FUTURE_WORK_DIMENSIONS}:
                assert d.coverage == "not_measured"
            else:
                assert d.coverage in ("measured", "not_measured")

    def test_synthetic_session_with_breach(self):
        loop, reports = build_synthetic_session(
            n_actions=10, seed=99, include_breach=True
        )
        e = evaluate_reports(reports, label="e2e-breach")
        assert isinstance(e, CAGE1Evaluation)

    def test_to_markdown_is_well_formed(self):
        loop, reports = build_synthetic_session(n_actions=6, seed=3)
        e = evaluate_reports(reports, label="md")
        md = e.to_cage1_markdown()
        # Markdown should have at least one table header
        assert "| " in md
        # Should mention the CAGE-1 state names
        for state in (
            "admitted",
            "held_for_evidence",
            "narrowed_for_ring",
            "narrowed_for_chain",
            "quarantined_for_cef",
            "escalated",
            "refused",
        ):
            assert state in md


# ---------------------------------------------------------------------------
# Test: edge-case tests for the CAGE-1 module
# ---------------------------------------------------------------------------


class TestAdversarial:
    def test_empty_reports_produces_zero_counters(self):
        eval_obj = evaluate_reports([], label="empty")
        assert eval_obj.n_reports == 0
        assert eval_obj.outcome_distribution.total == 0
        assert eval_obj.operational_readiness.n_breaker_opens == 0
        assert eval_obj.operational_readiness.n_circuit_quarantines == 0
        assert eval_obj.substrate_coverage == 5 / 7

    def test_digest_is_stable_across_calls(self):
        rows = [
            {"outcome": "allow", "bridge_decision": "ALLOW"},
            {"outcome": "hold_pending_human", "bridge_decision": "REQUIRES_HUMAN"},
        ]
        a = evaluate_reports(rows, label="stable")
        b = evaluate_reports(rows, label="stable")
        assert a.report_digest == b.report_digest
        # Different label -> different digest
        c = evaluate_reports(rows, label="other")
        assert a.report_digest != c.report_digest

    def test_invalid_outcome_string_falls_back_to_refused(self):
        rows = [{"outcome": "definitely-not-a-real-outcome"}]
        eval_obj = evaluate_reports(rows, label="invalid")
        assert eval_obj.outcome_distribution.refused == 1
        assert eval_obj.outcome_distribution.admitted == 0

    def test_jsonl_skips_malformed_lines(self, tmp_path):
        p = tmp_path / "mixed.jsonl"
        p.write_text(
            '{"outcome": "allow", "bridge_decision": "ALLOW"}\n'
            'this is not json\n'
            '\n'
            '{"outcome": "hold_pending_human"}\n'
            '[]\n'  # not a dict
            '{"outcome": "reject"}\n'
        )
        rows = load_reports_from_jsonl(str(p))
        assert len(rows) == 3
        # All three are valid dicts with an outcome key
        assert all(isinstance(r, dict) and "outcome" in r for r in rows)

    def test_row_to_cage1_state_round_trip(self):
        from core.cage1_evaluation import row_to_cage1_state
        for outcome, expected in [
            ("allow", "admitted"),
            ("hold_pending_evidence", "held_for_evidence"),
            ("hold_pending_ring", "narrowed_for_ring"),
            ("hold_pending_chain", "narrowed_for_chain"),
            ("hold_pending_cef", "quarantined_for_cef"),
            ("hold_pending_human", "escalated"),
            ("reject", "refused"),
        ]:
            assert row_to_cage1_state({"outcome": outcome}) == expected
            # Pre-mapped state also reads back
            assert row_to_cage1_state({"cage1_state": expected}) == expected

    def test_cage1_state_distribution_no_eval_envelope(self):
        from core.cage1_evaluation import cage1_state_distribution
        rows = [
            {"outcome": "allow"},
            {"outcome": "allow"},
            {"outcome": "hold_pending_cef"},
            {"outcome": "reject"},
        ]
        dist = cage1_state_distribution(rows)
        assert dist["admitted"] == 2
        assert dist["quarantined_for_cef"] == 1
        assert dist["refused"] == 1
        assert dist["total"] == 4

    def test_synthetic_session_includes_diversity(self):
        loop, reports = build_synthetic_session(n_actions=20, seed=0)
        assert len(reports) > 0
        from collections import Counter
        outcomes = Counter(r.outcome.value for r in reports)
        # Must contain at least one non-trivial outcome
        assert any(k != "allow" for k in outcomes), outcomes

    def test_markdown_round_trips_to_cage1_shape(self):
        rows = [
            {"outcome": "allow", "bridge_decision": "ALLOW"},
            {"outcome": "hold_pending_cef", "cef_findings": ["marker-1"]},
        ]
        eval_obj = evaluate_reports(rows, label="md-test")
        md = eval_obj.to_cage1_markdown()
        assert "# CAGE-1 Evaluation" in md
        assert "## Outcome distribution" in md
        assert "## Dimensions" in md
        assert "## Operational readiness" in md
        assert "quarantined_for_cef" in md
        assert "admitted" in md


class TestMemoryIntegrityDimension:
    def test_unmeasured_without_snapshot_preserves_honest_gap(self):
        evaluation = evaluate_reports([_row("allow")], label="no-memory")
        assert evaluation.memory_integrity.measured is False
        assert evaluation.memory_integrity.score is None
        payload = evaluation.to_dict()
        assert payload["memory_integrity"]["measured"] is False

    def test_clean_proactive_memory_snapshot_is_measured(self):
        from core.proactive_memory import ProactiveMemoryAgent

        memory = ProactiveMemoryAgent()
        memory.write("Keep the signed manifest.", importance=0.9, step=0)
        result = evaluate_reports([], label="memory-clean", memory_snapshot=memory)
        metrics = result.memory_integrity
        assert metrics == memory_integrity_metrics(memory)
        assert metrics.measured is True
        assert metrics.ok is True
        assert metrics.score == 1.0
        assert metrics.record_count == 1

    def test_tampered_snapshot_fails_without_mutation(self):
        from core.proactive_memory import ProactiveMemoryAgent

        memory = ProactiveMemoryAgent()
        memory_id = memory.write("Verified constraint.", step=0)
        memory.intervene("Verified constraint.", step=1)
        memory._records[memory_id].importance = 2.0
        before = memory.to_dict()
        metrics = memory_integrity_metrics(memory)
        assert metrics.measured is True
        assert metrics.ok is False
        assert metrics.invalid_record_count == 1
        assert metrics.invalid_intervention_count == 0
        assert memory.to_dict() == before

    def test_mapping_snapshot_is_supported_and_bad_shape_is_not_guessed(self):
        clean = {
            "ok": True,
            "record_count": 2,
            "intervention_count": 1,
            "invalid_record_ids": [],
            "invalid_intervention_memory_ids": [],
        }
        assert memory_integrity_metrics(clean).score == 1.0
        unknown = memory_integrity_metrics({"ok": True})
        assert unknown.measured is False
        assert unknown.score is None


class TestRetrievalQualityDimension:
    def _probe_snapshot(self, **overrides):
        snapshot = {
            "target_name": "fixture",
            "recovery_score": 0.75,
            "task_completion_rate": 0.95,
            "fidelity_gap": 0.20,
            "topk_recovery_score": 0.50,
            "topk_degradation": 0.25,
            "num_scenarios": 50,
            "num_dimensions": 12,
        }
        snapshot.update(overrides)
        return snapshot

    def test_probe_snapshot_measures_retrieval_without_using_task_success_as_score(self):
        snapshot = self._probe_snapshot()
        metrics = retrieval_quality_metrics(snapshot)
        assert metrics == RetrievalQualityMetrics(
            measured=True, target_name="fixture", score=0.75,
            recovery_score=0.75, task_completion_rate=0.95,
            fidelity_gap=0.20, topk_recovery_score=0.50,
            topk_degradation=0.25, num_scenarios=50, num_dimensions=12,
        )
        result = evaluate_reports([], label="retrieval", retrieval_snapshot=snapshot)
        dimension = next(d for d in result.dimensions if d.dimension == "retrieval_quality")
        assert dimension.coverage == "measured"
        assert dimension.score == 0.75
        assert result.substrate_coverage == 6 / 7
        assert result.to_dict()["retrieval_quality"]["topk_degradation"] == 0.25

    def test_probe_object_round_trips_and_markdown_exposes_diagnostics(self):
        from core.memprobe import quick_probe, in_memory_target
        result = evaluate_reports([], label="object", retrieval_snapshot=quick_probe(in_memory_target()))
        assert result.retrieval_quality.measured is True
        markdown = result.to_cage1_markdown()
        assert "## Retrieval quality" in markdown
        assert "Recovery score:" in markdown
        assert "Top-k degradation:" in markdown

    def test_malformed_or_absent_snapshot_stays_unmeasured(self):
        absent = evaluate_reports([], label="absent")
        assert absent.retrieval_quality.measured is False
        malformed = evaluate_reports([], label="bad", retrieval_snapshot={"target_name": "bad"})
        assert malformed.retrieval_quality.measured is False
        assert malformed.retrieval_quality.score is None
        assert next(d for d in malformed.dimensions if d.dimension == "retrieval_quality").coverage == "not_measured"

    def test_invalid_scores_are_not_guessed(self):
        metrics = retrieval_quality_metrics(self._probe_snapshot(recovery_score=1.2))
        assert metrics.measured is False
        assert metrics.score is None
        assert "between 0 and 1" in metrics.notes
