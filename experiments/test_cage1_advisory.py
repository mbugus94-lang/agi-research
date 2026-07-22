"""Tests for the review-only CAGE-1 advisory projection."""

from __future__ import annotations

import json
import subprocess
import sys

from core.cage1_advisory import project_review_advisory
from core.cage1_trend import trend_fleet_snapshots


def _snapshot(label, digest, admitted=3, refused=0, coverage=0.5, measured=False, score=None):
    memory = {"measured": measured, "score": score}
    return {
        "label": label,
        "report_digest": digest,
        "n_reports": admitted + refused,
        "substrate_coverage": coverage,
        "outcome_distribution": {"admitted": admitted, "refused": refused, "escalated": 0, "made_non_effective": 0},
        "memory_integrity": memory,
        "retrieval_quality": {"measured": False, "score": None},
    }


def test_clean_projection_defers_without_action():
    advisory = project_review_advisory(trend_fleet_snapshots([_snapshot("session-1", "one")]))
    assert advisory.severity == "none"
    assert advisory.recommendation == "defer"
    assert advisory.operator_decision_required is False
    assert advisory.automatic_action_taken is False
    assert advisory.raw_fleet["sessions"][0]["label"] == "session-1"


def test_regression_projection_requires_review_and_preserves_raw_envelope():
    snapshots = [_snapshot("session-1", "one", admitted=5, coverage=1.0), _snapshot("session-2", "two", admitted=2, coverage=0.4)]
    source = trend_fleet_snapshots(snapshots, notes="operator review")
    advisory = project_review_advisory(source)
    assert advisory.severity == "high"
    assert advisory.recommendation == "review"
    assert advisory.operator_decision_required is True
    assert advisory.automatic_action_taken is False
    assert advisory.regression_count >= 1
    assert advisory.raw_trend == source.trend.to_dict()
    assert advisory.notes == "operator review"


def test_duplicate_digest_is_critical():
    source = trend_fleet_snapshots([_snapshot("session-1", "same"), _snapshot("session-2", "same")])
    advisory = project_review_advisory(source)
    assert advisory.severity == "critical"
    assert advisory.recommendation == "escalate"
    assert any("duplicate digest" in item for item in advisory.anomalies)


def test_cli_emits_review_only_advisory(tmp_path):
    path = tmp_path / "fleet.json"
    path.write_text(json.dumps([_snapshot("session-1", "one"), _snapshot("session-2", "two", admitted=1, refused=1)]), encoding="utf-8")
    out = tmp_path / "advisory.json"
    result = subprocess.run([sys.executable, "-m", "cli.cage1_review", "--fleet-input", str(path), "--out", str(out)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["category"] == "cage1_fleet_review"
    assert payload["automatic_action_taken"] is False
    assert json.loads(out.read_text())["raw_fleet"]["sessions"]
