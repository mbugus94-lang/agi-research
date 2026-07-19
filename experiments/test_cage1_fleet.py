"""Tests for read-only CAGE-1 fleet aggregation."""

from __future__ import annotations

import json
import subprocess
import sys

from core.cage1_fleet import aggregate_fleet


def _snapshot(label, digest, admitted, score, memory, retrieval):
    return {
        "label": label,
        "report_digest": digest,
        "n_reports": admitted,
        "substrate_coverage": score,
        "outcome_distribution": {"admitted": admitted, "refused": 0, "total": admitted},
        "dimensions": [{"dimension": "authority", "coverage": "measured", "score": score}],
        "memory_integrity": {"measured": memory is not None, "score": memory},
        "retrieval_quality": {"measured": retrieval is not None, "score": retrieval},
    }


def test_aggregation_preserves_sessions_totals_and_lineage():
    snapshots = [_snapshot("a", "one", 2, 0.5, 0.7, None), _snapshot("b", "two", 3, 0.75, 0.9, 0.8)]
    result = aggregate_fleet(snapshots)
    assert [item.label for item in result.sessions] == ["a", "b"]
    assert result.outcome_totals["admitted"] == 5
    assert result.digest_links[0].matches_previous is False
    assert result.dimension_summaries[0].delta == 0.25
    assert result.evidence_metrics[0].section == "memory_integrity"


def test_missing_evidence_is_explicit_and_serializable():
    result = aggregate_fleet([_snapshot("a", "same", 1, 0.5, None, None), _snapshot("b", "same", 1, 0.5, None, None)])
    assert result.evidence_metrics == []
    payload = result.to_dict()
    assert payload["sessions"][0]["memory_integrity"]["measured"] is False
    assert "CAGE-1 Fleet Aggregation" in result.to_markdown()


def test_cli_json_mode(tmp_path):
    path = tmp_path / "snapshots.json"
    path.write_text(json.dumps([_snapshot("a", "x", 1, 0.5, 0.6, 0.7)]), encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "cli.cage1_fleet", "--input", str(path), "--format", "json"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert len(json.loads(result.stdout)["sessions"]) == 1
