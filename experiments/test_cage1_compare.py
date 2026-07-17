"""Tests for the read-only CAGE-1 snapshot comparison."""

from __future__ import annotations

import json
import subprocess
import sys

from core.cage1_compare import compare_evaluations, load_evaluation


def _evaluation(label="run", digest="digest", admitted=2, refused=1, score=0.5):
    return {
        "label": label,
        "report_digest": digest,
        "outcome_distribution": {
            "admitted": admitted,
            "held_for_evidence": 0,
            "narrowed_for_ring": 0,
            "narrowed_for_chain": 0,
            "quarantined_for_cef": 0,
            "escalated": 0,
            "refused": refused,
            "made_non_effective": 0,
        },
        "dimensions": [
            {"dimension": "retrieval_quality", "coverage": "not_measured", "score": None},
            {"dimension": "authority_and_policy_enforcement", "coverage": "measured", "score": score},
        ],
    }


def test_identical_snapshots_are_unchanged_and_digest_matches():
    result = compare_evaluations(_evaluation(), _evaluation())
    assert result.digest_match is True
    assert result.changed_outcome_count == 0
    assert result.changed_dimension_count == 0
    assert all(item.status in {"unchanged", "not_measured"} for item in result.dimension_deltas)


def test_changed_counts_and_scores_are_reported():
    result = compare_evaluations(
        _evaluation(label="before", digest="a", admitted=2, refused=1, score=0.5),
        _evaluation(label="after", digest="b", admitted=3, refused=0, score=0.8),
    )
    assert result.digest_match is False
    admitted = next(item for item in result.outcome_deltas if item.state == "admitted")
    assert (admitted.baseline, admitted.current, admitted.delta) == (2, 3, 1)
    score = next(item for item in result.dimension_deltas if item.dimension == "authority_and_policy_enforcement")
    assert score.score_delta == 0.30000000000000004
    assert score.status == "improved"
    assert result.changed_outcome_count == 2
    assert result.changed_dimension_count == 1


def test_coverage_change_and_missing_dimensions_are_explicit():
    before = _evaluation()
    after = _evaluation()
    after["dimensions"] = [{"dimension": "new_dimension", "coverage": "measured", "score": 1.0}]
    result = compare_evaluations(before, after)
    retrieval = next(item for item in result.dimension_deltas if item.dimension == "retrieval_quality")
    assert retrieval.status == "coverage_changed"
    new = next(item for item in result.dimension_deltas if item.dimension == "new_dimension")
    assert new.baseline_coverage == "not_measured"
    assert new.current_score == 1.0


def test_serialization_and_loader(tmp_path):
    path = tmp_path / "evaluation.json"
    path.write_text(json.dumps(_evaluation()), encoding="utf-8")
    loaded = load_evaluation(str(path))
    assert loaded["label"] == "run"
    comparison = compare_evaluations(loaded, loaded)
    assert "outcome_deltas" in json.loads(comparison.to_json())
    assert "CAGE-1 Comparison" in comparison.to_markdown()


def test_cli_json_mode(tmp_path):
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    baseline.write_text(json.dumps(_evaluation(label="before")), encoding="utf-8")
    current.write_text(json.dumps(_evaluation(label="after", score=0.9)), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_compare", "--baseline", str(baseline), "--current", str(current), "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["current_label"] == "after"


def test_cli_bad_input_returns_error(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_compare", "--baseline", str(tmp_path / "missing"), "--current", str(tmp_path / "missing2")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "ERROR:" in result.stderr
