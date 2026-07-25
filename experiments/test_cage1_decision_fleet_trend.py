from __future__ import annotations

import json
import subprocess
import sys

from core.cage1_decision_fleet_trend import trend_fleet_audit_files, write_fleet_audit_trend_jsonl


def _summary(path, *, status="valid", sources=None, lines=None, status_counts=None, decision_counts=None, conflicts=None):
    sources = sources or [{"source_id": "member-a", "path": "a.jsonl"}]
    lines = lines or [{"source_id": "member-a", "source_line_number": 1, "status": "valid", "decision": "accept"}]
    value = {
        "category": "cage1_decision_fleet_audit",
        "schema_version": "1.0",
        "status": status,
        "source_count": len(sources),
        "report_count": len(sources),
        "line_count": len(lines),
        "valid_line_count": sum(item.get("status") == "valid" for item in lines),
        "invalid_line_count": sum(item.get("status") != "valid" for item in lines),
        "status_counts": status_counts or {"valid": len(lines)},
        "decision_counts": decision_counts or {"accept": len(lines)},
        "advisory_counts": {"advisory-a": len(lines)},
        "conflicting_advisories": conflicts or [],
        "report_status_counts": {status: len(sources)},
        "sources": sources,
        "lines": lines,
        "decision_applied": False,
        "automatic_action_taken": False,
    }
    path.write_text(json.dumps(value), encoding="utf-8")


def test_stable_single_point_is_non_actioning(tmp_path):
    path = tmp_path / "first.json"
    _summary(path)
    trend = trend_fleet_audit_files([str(path)])
    assert trend.status == "stable"
    assert trend.deltas == []
    assert trend.decision_applied is False
    assert trend.automatic_action_taken is False


def test_degradation_preserves_provenance_and_flags_counts(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    _summary(first)
    _summary(second, status="invalid", sources=[{"source_id": "member-b", "path": "b.jsonl"}], lines=[{"source_id": "member-b", "source_line_number": 2, "status": "expired", "decision": None}], status_counts={"expired": 1}, decision_counts={}, conflicts=[])
    trend = trend_fleet_audit_files([str(first), str(second)], snapshot_ids=["t1", "t2"])
    assert trend.status == "degraded"
    assert trend.deltas[0].trend == "degraded"
    assert trend.deltas[0].invalid_line_delta == 1
    assert trend.deltas[0].missing_decision_delta == 1
    assert "invalid_records_increased" in trend.deltas[0].flags
    assert "source_membership_changed" in trend.deltas[0].flags
    assert trend.points[1].line_provenance[0]["source_line_number"] == 2


def test_improvement_and_mixed_status_are_distinguished(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    third = tmp_path / "third.json"
    _summary(first, status="invalid", lines=[{"source_id": "member-a", "source_line_number": 1, "status": "expired", "decision": None}], status_counts={"expired": 1}, decision_counts={})
    _summary(second)
    _summary(third, status="conflicting", conflicts=["advisory-a"], lines=[{"source_id": "member-a", "source_line_number": 1, "status": "valid", "decision": "reject"}, {"source_id": "member-a", "source_line_number": 2, "status": "valid", "decision": "accept"}], status_counts={"valid": 2}, decision_counts={"accept": 1, "reject": 1})
    trend = trend_fleet_audit_files([str(first), str(second), str(third)])
    assert trend.status == "mixed"
    assert trend.deltas[0].trend == "improved"
    assert trend.deltas[1].trend == "degraded"
    assert any(flag.endswith("fleet_status_improved") for flag in trend.flagged_changes)
    assert any(flag.endswith("fleet_status_degraded") for flag in trend.flagged_changes)


def test_jsonl_writer_emits_points_deltas_and_summary(tmp_path):
    path = tmp_path / "first.json"
    out = tmp_path / "trend.jsonl"
    _summary(path)
    trend = trend_fleet_audit_files([str(path)])
    write_fleet_audit_trend_jsonl(trend, str(out))
    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert records[0]["record_type"] == "point"
    assert records[-1]["record_type"] == "summary"
    assert records[-1]["decision_applied"] is False


def test_cli_outputs_summary_and_rejects_bad_snapshot_count(tmp_path):
    path = tmp_path / "first.json"
    out = tmp_path / "trend.json"
    _summary(path)
    result = subprocess.run([sys.executable, "-m", "cli.cage1_fleet_trend", "--summary", str(path), "--out", str(out), "--summary-only"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "status=stable" in result.stdout
    assert json.loads(out.read_text(encoding="utf-8"))["status"] == "stable"
    bad = subprocess.run([sys.executable, "-m", "cli.cage1_fleet_trend", "--summary", str(path), "--summary", str(path), "--snapshot-id", "only-one"], capture_output=True, text=True)
    assert bad.returncode == 2
    assert "once per --summary" in bad.stderr
