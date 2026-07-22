"""Tests for read-only CAGE-1 trend analysis."""

from __future__ import annotations

import json
import subprocess
import sys

from core.cage1_trend import load_evaluations, trend_evaluations, trend_fleet_snapshots


def _snapshot(label, digest, admitted=3, refused=0, coverage=0.5, memory=None, retrieval=None):
    return {
        "label": label,
        "report_digest": digest,
        "n_reports": admitted + refused,
        "substrate_coverage": coverage,
        "outcome_distribution": {"admitted": admitted, "refused": refused, "escalated": 0, "made_non_effective": 0},
        "memory_integrity": {"score": memory} if memory is not None else {"measured": False, "score": None},
        "retrieval_quality": {"score": retrieval} if retrieval is not None else {"measured": False, "score": None},
    }


def test_identical_trajectory_has_no_regressions_and_links_digests():
    result = trend_evaluations([_snapshot("a", "d"), _snapshot("b", "d")])
    assert len(result.points) == 2
    assert len(result.digest_links) == 1
    assert result.digest_links[0].matches_previous is True
    assert result.regressions == []


def test_counts_and_scores_flag_regressions():
    result = trend_evaluations([
        _snapshot("before", "a", admitted=5, refused=0, coverage=1.0, memory=1.0, retrieval=0.9),
        _snapshot("after", "b", admitted=3, refused=1, coverage=0.5, memory=0.8, retrieval=0.7),
    ])
    metrics = {item.metric for item in result.regressions}
    assert {"admitted", "refused", "substrate_coverage", "memory_integrity_score", "retrieval_quality_score"} <= metrics
    assert result.digest_links[0].matches_previous is False


def test_missing_optional_scores_are_not_guessed():
    result = trend_evaluations([_snapshot("a", "a", memory=None), _snapshot("b", "b", memory=0.2)])
    assert "memory_integrity_score" not in {item.metric for item in result.regressions}
    assert result.points[0].memory_integrity_score is None


def test_serialization_and_markdown():
    result = trend_evaluations([_snapshot("a", "a")], notes="review only")
    payload = json.loads(result.to_json())
    assert payload["notes"] == "review only"
    assert "CAGE-1 Trend" in result.to_markdown()


def test_loader_and_cli(tmp_path):
    path = tmp_path / "trend.json"
    path.write_text(json.dumps([_snapshot("before", "a"), _snapshot("after", "b", admitted=2, refused=1)]), encoding="utf-8")
    assert len(load_evaluations(str(path))) == 2
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_trend", "--input", str(path), "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert len(json.loads(result.stdout)["points"]) == 2


def test_cli_bad_input_returns_error(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_trend", "--input", str(tmp_path / "missing")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "ERROR:" in result.stderr


def test_fleet_trend_preserves_fleet_provenance_and_unmeasured_evidence():
    snapshots = [
        _snapshot("session-1", "one", memory=None),
        _snapshot("session-2", "two", memory=0.8),
    ]
    result = trend_fleet_snapshots(snapshots, notes="review only")
    payload = result.to_dict()
    assert len(payload["trend"]["points"]) == 2
    assert [item["label"] for item in payload["fleet"]["sessions"]] == ["session-1", "session-2"]
    assert payload["fleet"]["sessions"][0]["memory_integrity"]["measured"] is False
    assert payload["fleet"]["notes"] == "review only"
    assert result.to_markdown().count("CAGE-1") >= 2


def test_fleet_trend_does_not_mutate_input_on_anomaly():
    snapshots = [_snapshot("session-2", "same"), _snapshot("session-1", "same")]
    original = json.loads(json.dumps(snapshots))
    result = trend_fleet_snapshots(snapshots)
    assert snapshots == original
    assert any("label order decreases" in item for item in result.fleet.anomalies)
    assert any("duplicate digest" in item for item in result.fleet.anomalies)
