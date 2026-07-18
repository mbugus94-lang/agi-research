"""Tests for evidence-aware, read-only CAGE-1 comparison."""

from __future__ import annotations

from core.cage1_compare import compare_evaluations


def _snapshot(memory, retrieval):
    return {
        "label": "run",
        "report_digest": "digest",
        "outcome_distribution": {},
        "dimensions": [],
        "memory_integrity": memory,
        "retrieval_quality": retrieval,
    }


def test_memory_and_retrieval_metric_deltas_are_explicit():
    baseline = _snapshot(
        {
            "measured": True,
            "score": 1.0,
            "record_count": 10,
            "intervention_count": 2,
            "invalid_record_count": 0,
            "invalid_intervention_count": 0,
        },
        {
            "measured": True,
            "score": 0.8,
            "recovery_score": 0.8,
            "task_completion_rate": 0.9,
            "fidelity_gap": 0.1,
            "topk_recovery_score": 0.7,
            "topk_degradation": 0.2,
            "num_scenarios": 4,
            "num_dimensions": 10,
        },
    )
    current = _snapshot(
        {
            "measured": True,
            "score": 0.75,
            "record_count": 10,
            "intervention_count": 3,
            "invalid_record_count": 2,
            "invalid_intervention_count": 1,
        },
        {
            "measured": True,
            "score": 0.9,
            "recovery_score": 0.9,
            "task_completion_rate": 0.85,
            "fidelity_gap": 0.2,
            "topk_recovery_score": 0.75,
            "topk_degradation": 0.1,
            "num_scenarios": 5,
            "num_dimensions": 10,
        },
    )
    result = compare_evaluations(baseline, current)
    metrics = {(item.section, item.metric): item for item in result.evidence_deltas}
    assert metrics[("memory_integrity", "score")].status == "regressed"
    assert metrics[("memory_integrity", "invalid_record_count")].status == "regressed"
    assert metrics[("retrieval_quality", "recovery_score")].status == "improved"
    assert metrics[("retrieval_quality", "task_completion_rate")].status == "regressed"
    assert metrics[("retrieval_quality", "fidelity_gap")].status == "increased"


def test_unmeasured_evidence_stays_unmeasured():
    result = compare_evaluations(
        _snapshot({"measured": False, "score": None}, {"measured": False, "score": None}),
        _snapshot({"measured": True, "score": 0.5}, {"measured": False, "score": None}),
    )
    metrics = {(item.section, item.metric): item for item in result.evidence_deltas}
    assert metrics[("memory_integrity", "score")].status == "coverage_changed"
    assert metrics[("retrieval_quality", "score")].status == "not_measured"


def test_evidence_comparison_is_serialized_and_rendered():
    result = compare_evaluations(
        _snapshot({"measured": True, "score": 0.5}, {"measured": False}),
        _snapshot({"measured": True, "score": 0.75}, {"measured": False}),
    )
    payload = result.to_dict()
    assert payload["evidence_deltas"]
    assert "Evidence metric deltas" in result.to_markdown()
