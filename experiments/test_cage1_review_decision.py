from __future__ import annotations

import json
import subprocess
import sys

from core.cage1_advisory import project_review_advisory
from core.cage1_decision import create_operator_decision, sign_operator_decision
from core.cage1_trend import trend_fleet_snapshots
from core.signed_advisory_envelope import EnvelopeConfig, envelope_to_json


def _snapshot(label: str, digest: str) -> dict:
    return {
        "label": label,
        "report_digest": digest,
        "n_reports": 2,
        "substrate_coverage": 1.0,
        "outcome_distribution": {"admitted": 2, "refused": 0, "escalated": 0, "made_non_effective": 0},
        "memory_integrity": {"measured": False, "score": None},
        "retrieval_quality": {"measured": False, "score": None},
    }


def _fixture(tmp_path):
    source = trend_fleet_snapshots([_snapshot("s1", "one")], notes="fixture")
    advisory = project_review_advisory(source)
    envelope = sign_operator_decision(
        create_operator_decision(advisory.to_dict(), "defer", "operator-1", decided_at=10),
        "k1",
        b"secret",
        config=EnvelopeConfig(issued_at=10),
        now=10,
    )
    source_path = tmp_path / "source.json"
    envelope_path = tmp_path / "decision.json"
    source_path.write_text(source.to_json(), encoding="utf-8")
    envelope_path.write_text(envelope_to_json(envelope), encoding="utf-8")
    return source_path, envelope_path


def test_review_cli_verifies_signed_decision_without_applying_it(tmp_path):
    source_path, envelope_path = _fixture(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cli.cage1_review",
            "--trend-input",
            str(source_path),
            "--decision-envelope",
            str(envelope_path),
            "--decision-key-id",
            "k1",
            "--decision-hmac-secret",
            "secret",
            "--decision-now",
            "10",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["decision_verification"]["valid"] is True
    assert payload["decision_verification"]["decision"] == "defer"
    assert payload["decision_verification"]["decision_applied"] is False
    assert payload["decision_verification"]["automatic_action_taken"] is False


def test_review_cli_rejects_tampered_decision_and_writes_report(tmp_path):
    source_path, envelope_path = _fixture(tmp_path)
    payload = json.loads(envelope_path.read_text(encoding="utf-8"))
    payload["payload"]["decision"] = "accept"
    envelope_path.write_text(json.dumps(payload), encoding="utf-8")
    report_path = tmp_path / "decision-report.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cli.cage1_review",
            "--trend-input",
            str(source_path),
            "--decision-envelope",
            str(envelope_path),
            "--decision-key-id",
            "k1",
            "--decision-hmac-secret",
            "secret",
            "--decision-report-out",
            str(report_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    output = json.loads(result.stdout)
    assert output["decision_verification"]["valid"] is False
    assert output["decision_verification"]["decision_applied"] is False
    assert json.loads(report_path.read_text(encoding="utf-8"))["status"] == "invalid"


def test_review_cli_requires_verification_credentials(tmp_path):
    source_path, envelope_path = _fixture(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cli.cage1_review",
            "--trend-input",
            str(source_path),
            "--decision-envelope",
            str(envelope_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "decision-key-id" in result.stderr


def test_review_cli_schema_invalid_fixture_exposes_markdown_finding():
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_review", "--fixture", "schema-invalid", "--format", "markdown"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "schema-invalid audit line" in result.stdout
    assert "fixture-member.jsonl" in result.stdout
    assert "physical_line=7" in result.stdout
    assert "Automatic action taken: **no**" in result.stdout


def test_review_cli_schema_invalid_fixture_writes_json_without_mutating_source(tmp_path):
    out = tmp_path / "advisory.json"
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_review", "--fixture", "schema-invalid", "--out", str(out)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["severity"] == "critical"
    assert payload["recommendation"] == "escalate"
    assert payload["automatic_action_taken"] is False
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["raw_fleet"]["lines"][0]["status"] == "invalid_schema"


def test_review_cli_mixed_fleet_fixture_preserves_clean_and_schema_invalid_evidence(tmp_path):
    out = tmp_path / "mixed-advisory.json"
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_review", "--fixture", "mixed-fleet", "--out", str(out)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["severity"] == "critical"
    assert payload["recommendation"] == "escalate"
    assert payload["anomaly_count"] == 1
    assert "drifted-member.jsonl" in payload["anomalies"][0]
    assert "physical_line=8" in payload["anomalies"][0]
    raw_lines = json.loads(out.read_text(encoding="utf-8"))["raw_fleet"]["lines"]
    assert [line["status"] for line in raw_lines] == ["valid", "invalid_schema"]
    assert raw_lines[0]["decision"] == "defer"
    assert raw_lines[1]["decision"] is None


def test_review_cli_multi_schema_invalid_fixture_preserves_order_and_provenance(tmp_path):
    out = tmp_path / "multi-schema-advisory.json"
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_review", "--fixture", "multi-schema-invalid", "--out", str(out)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["severity"] == "critical"
    assert payload["recommendation"] == "escalate"
    assert payload["anomaly_count"] == 3
    assert [
        ("member-z.jsonl", "physical_line=12"),
        ("member-a.jsonl", "physical_line=4"),
        ("member-m.jsonl", "physical_line=19"),
    ] == [
        (next(source for source in ("member-z.jsonl", "member-a.jsonl", "member-m.jsonl") if source in item), next(marker for marker in ("physical_line=12", "physical_line=4", "physical_line=19") if marker in item))
        for item in payload["anomalies"]
    ]
    raw_lines = json.loads(out.read_text(encoding="utf-8"))["raw_fleet"]["lines"]
    assert [(line["source_id"], line["source_line_number"]) for line in raw_lines] == [
        ("member-z.jsonl", 12),
        ("member-a.jsonl", 4),
        ("member-m.jsonl", 19),
    ]
    assert all(line["status"] == "invalid_schema" for line in raw_lines)
    assert json.loads(out.read_text(encoding="utf-8"))["automatic_action_taken"] is False


def test_review_cli_multi_schema_invalid_fixture_markdown_preserves_complete_provenance():
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_review", "--fixture", "multi-schema-invalid", "--format", "markdown"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    markdown = result.stdout
    assert markdown.startswith("# CAGE-1 Review Advisory")
    assert "- Severity: **critical**" in markdown
    assert "- Recommendation: **escalate**" in markdown
    assert "- Operator decision required: **yes**" in markdown
    assert "- Automatic action taken: **no**" in markdown
    findings = [
        "source=member-z.jsonl, physical_line=12",
        "source=member-a.jsonl, physical_line=4",
        "source=member-m.jsonl, physical_line=19",
    ]
    positions = [markdown.index(finding) for finding in findings]
    assert positions == sorted(positions)
    assert "schema_version must be exactly '1.0'" in markdown
    assert "category must be exactly 'cage1_decision_audit_line'" in markdown
    assert "No automatic remediation was performed." in markdown


def test_review_cli_mixed_fleet_fixture_markdown_distinguishes_valid_and_invalid_evidence():
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_review", "--fixture", "mixed-fleet", "--format", "markdown"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    markdown = result.stdout
    assert "## Evidence status" in markdown
    assert "- Valid audit lines: **1**" in markdown
    assert "- Schema-invalid audit lines: **1**" in markdown
    valid_finding = "- `valid`: source=clean-member.jsonl, physical_line=3, decision=defer"
    invalid_finding = "- `invalid_schema`: source=drifted-member.jsonl, physical_line=8"
    assert valid_finding in markdown
    assert invalid_finding in markdown
    assert markdown.index(valid_finding) < markdown.index(invalid_finding)
    assert "Automatic action taken: **no**" in markdown
    assert "No automatic remediation was performed." in markdown


def test_review_cli_mixed_fleet_markdown_preserves_valid_and_invalid_evidence():
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_review", "--fixture", "mixed-fleet", "--format", "markdown"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    markdown = result.stdout
    assert "## Evidence status" in markdown
    assert "Valid audit lines: **1**" in markdown
    assert "Schema-invalid audit lines: **1**" in markdown
    valid = "`valid`: source=clean-member.jsonl, physical_line=3, decision=defer"
    invalid = "`invalid_schema`: source=drifted-member.jsonl, physical_line=8"
    assert valid in markdown
    assert invalid in markdown
    assert markdown.index(valid) < markdown.index(invalid)
    assert "No automatic remediation was performed." in markdown


def test_review_cli_mixed_fleet_markdown_preserves_valid_and_invalid_evidence():
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_review", "--fixture", "mixed-fleet", "--format", "markdown"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    markdown = result.stdout
    assert markdown.startswith("# CAGE-1 Review Advisory")
    assert "- Severity: **critical**" in markdown
    assert "- Recommendation: **escalate**" in markdown
    assert "- Operator decision required: **yes**" in markdown
    assert "- Automatic action taken: **no**" in markdown
    assert "## Evidence status" in markdown
    assert "- Valid audit lines: **1**" in markdown
    assert "- Schema-invalid audit lines: **1**" in markdown
    valid = "- `valid`: source=clean-member.jsonl, physical_line=3, decision=defer"
    invalid = "- `invalid_schema`: source=drifted-member.jsonl, physical_line=8"
    assert valid in markdown
    assert invalid in markdown
    assert markdown.index(valid) < markdown.index(invalid)
    assert "The raw fleet and trend envelopes are preserved for operator review." in markdown
    assert "No automatic remediation was performed." in markdown


def test_review_cli_mixed_fleet_json_and_markdown_share_evidence_counts():
    json_result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_review", "--fixture", "mixed-fleet"],
        capture_output=True,
        text=True,
    )
    markdown_result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_review", "--fixture", "mixed-fleet", "--format", "markdown"],
        capture_output=True,
        text=True,
    )
    assert json_result.returncode == 0, json_result.stderr
    assert markdown_result.returncode == 0, markdown_result.stderr
    evidence = json.loads(json_result.stdout)["evidence_status"]
    assert evidence == {"total": 2, "valid": 1, "invalid_schema": 1, "other": 0}
    markdown = markdown_result.stdout
    assert f"- Total audit lines: **{evidence['total']}**" in markdown
    assert f"- Valid audit lines: **{evidence['valid']}**" in markdown
    assert f"- Schema-invalid audit lines: **{evidence['invalid_schema']}**" in markdown
    assert f"- Other-status audit lines: **{evidence['other']}**" in markdown


def test_review_cli_trend_input_projects_line_provenance_into_evidence_status_and_markdown(tmp_path):
    source = {
        "category": "cage1_decision_fleet_audit_trend",
        "schema_version": "1.0",
        "status": "stable",
        "points": [{
            "snapshot_id": "t1",
            "status": "invalid",
            "line_provenance": [{
                "source_id": "trend-member.jsonl",
                "source_line_number": 17,
                "status": "invalid_schema",
                "reason": "missing required field: category",
            }],
        }],
        "flagged_changes": [],
        "decision_applied": False,
        "automatic_action_taken": False,
    }
    source_path = tmp_path / "trend.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")
    json_result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_review", "--trend-input", str(source_path)],
        capture_output=True,
        text=True,
    )
    markdown_result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_review", "--trend-input", str(source_path), "--format", "markdown"],
        capture_output=True,
        text=True,
    )
    assert json_result.returncode == 0, json_result.stderr
    assert markdown_result.returncode == 0, markdown_result.stderr
    payload = json.loads(json_result.stdout)
    assert payload["evidence_status"] == {"total": 1, "valid": 0, "invalid_schema": 1, "other": 0}
    markdown = markdown_result.stdout
    assert "- Total audit lines: **1**" in markdown
    assert "- Schema-invalid audit lines: **1**" in markdown
    assert "source=trend-member.jsonl, physical_line=17, snapshot=t1" in markdown
    assert "missing required field: category" not in markdown or "snapshot=t1" in markdown
