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


def test_adversarial_inputs_are_reported_without_mutation():
    snapshots = [
        _snapshot("session-2", "same", 1, 0.5, 0.6, 0.7),
        _snapshot("session-1", "same", 1, 0.5, 0.6, 0.7),
    ]
    snapshots[0]["n_reports"] = -3
    snapshots[0]["substrate_coverage"] = "unknown"
    snapshots[0]["memory_integrity"]["score"] = float("nan")
    original = [dict(item) for item in snapshots]
    result = aggregate_fleet(snapshots)
    assert snapshots[0]["n_reports"] == original[0]["n_reports"]
    assert snapshots[0]["substrate_coverage"] == original[0]["substrate_coverage"]
    assert snapshots[0]["memory_integrity"]["score"] != snapshots[0]["memory_integrity"]["score"]
    assert "n_reports" in result.sessions[0].invalid_fields
    assert "substrate_coverage" in result.sessions[0].invalid_fields
    assert "memory_integrity.score" in result.sessions[0].invalid_fields
    assert any("label order decreases" in item for item in result.anomalies)
    assert any("duplicate digest" in item for item in result.anomalies)
    payload = result.to_dict()
    assert payload["anomalies"]
    assert "Anomalies" in result.to_markdown()


def test_malformed_optional_sections_stay_unmeasured():
    snapshot = _snapshot("a", "x", 1, 0.5, None, None)
    snapshot["retrieval_quality"] = ["not", "a", "mapping"]
    result = aggregate_fleet([snapshot])
    assert result.sessions[0].retrieval_quality == {}
    assert "retrieval_quality" in result.sessions[0].invalid_fields
    assert result.evidence_metrics == []


def test_jsonl_loader_accepts_blank_lines_and_preserves_order(tmp_path):
    from core.cage1_fleet import load_fleet_snapshots

    path = tmp_path / "snapshots.jsonl"
    rows = [_snapshot("session-1", "one", 1, 0.5, None, None), _snapshot("session-2", "two", 2, 0.75, 0.8, 0.9)]
    path.write_text("\n" + json.dumps(rows[0]) + "\n\n" + json.dumps(rows[1]) + "\n", encoding="utf-8")
    assert [row["label"] for row in load_fleet_snapshots(str(path))] == ["session-1", "session-2"]


def test_jsonl_input_is_loaded_in_order(tmp_path):
    path = tmp_path / "snapshots.jsonl"
    rows = [_snapshot("session-1", "one", 1, 0.5, None, None), _snapshot("session-2", "two", 2, 0.75, 0.8, 0.9)]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "cli.cage1_fleet", "--input", str(path), "--format", "json"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert [item["label"] for item in json.loads(result.stdout)["sessions"]] == ["session-1", "session-2"]


def test_jsonl_malformed_record_reports_line(tmp_path):
    path = tmp_path / "snapshots.jsonl"
    path.write_text(json.dumps(_snapshot("session-1", "one", 1, 0.5, None, None)) + "\nnot-json\n", encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "cli.cage1_fleet", "--input", str(path), "--format", "json"], capture_output=True, text=True)
    assert result.returncode == 2
    assert "line 2" in result.stderr


def test_cli_mixed_coverage_fixture_preserves_unmeasured_evidence():
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_fleet", "--fixture", "mixed-coverage", "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["notes"] == "fixture: mixed-coverage"
    assert payload["sessions"][0]["memory_integrity"]["measured"] is False
    assert any(item["metric"] == "score" and item["measured_sessions"] == 1 for item in payload["evidence_metrics"])


def test_cli_duplicate_digest_fixture_reports_anomaly():
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_fleet", "--fixture", "duplicate-digest", "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert any("duplicate digest" in item for item in payload["anomalies"])


def test_cli_requires_input_or_fixture():
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_fleet", "--format", "json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "required" in result.stderr
