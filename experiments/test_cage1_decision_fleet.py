from __future__ import annotations

import json
import subprocess
import sys

from core.cage1_decision_fleet import (
    aggregate_decision_audits,
    aggregate_decision_audit_files,
    load_decision_audit_jsonl,
    write_fleet_audit_jsonl,
)


def _write(path, records):
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")


def _line(line_number, status="valid", advisory="a", decision="defer", operator="op"):
    return {
        "category": "cage1_decision_audit_line",
        "schema_version": "1.0",
        "line_number": line_number,
        "status": status,
        "reason": "fixture",
        "advisory_digest": advisory,
        "envelope_digest": f"env-{line_number}",
        "decision": decision if status == "valid" else None,
        "operator_id": operator if status == "valid" else None,
    }


def test_load_preserves_source_and_line_provenance(tmp_path):
    path = tmp_path / "member-a.jsonl"
    _write(path, [_line(4), _line(9, "expired")])
    source, lines = load_decision_audit_jsonl(str(path), source_id="member-a")
    assert source.source_id == "member-a"
    assert source.line_count == 2
    assert source.valid_line_count == 1
    assert source.invalid_line_count == 1
    assert [line.source_line_number for line in lines] == [4, 9]
    assert all(line.source_path == str(path) for line in lines)


def test_aggregate_marks_invalid_and_counts_each_member():
    first = (type("Source", (), {"source_id": "a"})(), [])
    second = (type("Source", (), {"source_id": "b"})(), [])
    summary = aggregate_decision_audits([])
    assert summary.status == "unverified"
    assert summary.decision_applied is False
    assert summary.automatic_action_taken is False


def test_aggregate_files_preserves_invalid_records_and_report_status(tmp_path):
    first = tmp_path / "a.jsonl"
    second = tmp_path / "b.jsonl"
    report_a = tmp_path / "a-report.json"
    report_b = tmp_path / "b-report.json"
    _write(first, [_line(1, advisory="a", decision="accept"), _line(2, "malformed_json", advisory=None)])
    _write(second, [_line(1, advisory="b", decision="reject")])
    report_a.write_text(json.dumps({"status": "invalid"}), encoding="utf-8")
    report_b.write_text(json.dumps({"status": "valid"}), encoding="utf-8")
    summary = aggregate_decision_audit_files([str(first), str(second)], report_paths=[str(report_a), str(report_b)])
    assert summary.status == "invalid"
    assert summary.source_count == 2
    assert summary.report_count == 2
    assert summary.line_count == 3
    assert summary.valid_line_count == 2
    assert summary.invalid_line_count == 1
    assert summary.status_counts == {"malformed_json": 1, "valid": 2}
    assert summary.report_status_counts == {"invalid": 1, "valid": 1}
    assert {line.source_id for line in summary.lines} == {"a.jsonl", "b.jsonl"}


def test_conflicting_valid_decisions_for_same_advisory_are_visible(tmp_path):
    path = tmp_path / "conflict.jsonl"
    _write(path, [_line(1, advisory="same", decision="accept", operator="one"), _line(2, advisory="same", decision="reject", operator="two")])
    summary = aggregate_decision_audit_files([str(path)])
    assert summary.status == "conflicting"
    assert summary.conflicting_advisories == ["same"]
    assert summary.decision_counts == {"accept": 1, "reject": 1}


def test_write_jsonl_has_lines_then_summary(tmp_path):
    path = tmp_path / "member.jsonl"
    out = tmp_path / "fleet.jsonl"
    _write(path, [_line(1)])
    summary = aggregate_decision_audit_files([str(path)])
    write_fleet_audit_jsonl(summary, str(out))
    records = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert records[0]["category"] == "cage1_decision_fleet_audit_line"
    assert records[-1]["record_type"] == "summary"
    assert records[-1]["status"] == "valid"


def test_cli_summary_and_output(tmp_path):
    path = tmp_path / "member.jsonl"
    out = tmp_path / "fleet.json"
    _write(path, [_line(1)])
    result = subprocess.run([
        sys.executable, "-m", "cli.cage1_fleet_audit",
        "--audit", str(path), "--out", str(out), "--summary",
    ], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "status=valid" in result.stdout
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["source_count"] == 1
    assert payload["decision_applied"] is False


def test_cli_rejects_mismatched_report_count(tmp_path):
    path = tmp_path / "member.jsonl"
    report = tmp_path / "report.json"
    _write(path, [_line(1)])
    report.write_text(json.dumps({"status": "valid"}), encoding="utf-8")
    result = subprocess.run([
        sys.executable, "-m", "cli.cage1_fleet_audit",
        "--audit", str(path), "--audit", str(path), "--report", str(report),
    ], capture_output=True, text=True)
    assert result.returncode == 2
    assert "once per --audit" in result.stderr


def test_loader_retains_malformed_json_and_non_object_lines(tmp_path):
    path = tmp_path / "malformed.jsonl"
    path.write_text('{"status":"valid","line_number":3,"advisory_digest":"a","decision":"defer"}\nnot-json\n[]\n', encoding="utf-8")
    source, lines = load_decision_audit_jsonl(str(path), source_id="member-malformed")
    assert source.line_count == 3
    assert source.valid_line_count == 1
    assert source.invalid_line_count == 2
    assert [line.status for line in lines] == ["valid", "malformed_json", "malformed_record"]
    assert [line.source_line_number for line in lines] == [3, 2, 3]
    assert lines[1].reason.startswith("invalid JSON:")
    assert lines[2].reason == "audit line must be a JSON object"


def test_cli_malformed_audit_is_nonzero_but_writes_complete_jsonl(tmp_path):
    path = tmp_path / "member.jsonl"
    out = tmp_path / "fleet.json"
    audit_out = tmp_path / "fleet.jsonl"
    path.write_text('{"status":"valid","line_number":1,"advisory_digest":"a","decision":"defer"}\nbroken\n', encoding="utf-8")
    result = subprocess.run([
        sys.executable, "-m", "cli.cage1_fleet_audit",
        "--audit", str(path), "--out", str(out), "--audit-out", str(audit_out), "--summary",
    ], capture_output=True, text=True)
    assert result.returncode == 1
    assert "status=invalid" in result.stdout
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["line_count"] == 2
    assert payload["status_counts"] == {"malformed_json": 1, "valid": 1}
    records = [json.loads(line) for line in audit_out.read_text(encoding="utf-8").splitlines()]
    assert [record["status"] for record in records[:-1]] == ["valid", "malformed_json"]
    assert records[-1]["record_type"] == "summary"
