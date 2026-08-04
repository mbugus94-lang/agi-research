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


def test_review_cli_conflicting_decisions_is_critical_and_review_only():
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_review", "--fixture", "conflicting-decisions"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["severity"] == "critical"
    assert payload["recommendation"] == "escalate"
    assert payload["operator_decision_required"] is True
    assert payload["automatic_action_taken"] is False
    assert "conflicting valid decisions for advisory=advisory-conflict" in payload["anomalies"]
    assert payload["evidence_status"] == {"total": 2, "valid": 2, "invalid_schema": 0, "other": 0}


def test_review_cli_conflicting_decisions_markdown_preserves_both_decisions():
    result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_review", "--fixture", "conflicting-decisions", "--format", "markdown"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Severity: **critical**" in result.stdout
    assert "conflicting valid decisions for advisory=advisory-conflict" in result.stdout
    assert "source=operator-one.jsonl, physical_line=3, decision=accept" in result.stdout
    assert "source=operator-two.jsonl, physical_line=4, decision=reject" in result.stdout
    assert "Automatic action taken: **no**" in result.stdout


def test_conflicting_decisions_fixture_is_critical_and_review_only():
    json_result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_review", "--fixture", "conflicting-decisions"],
        capture_output=True,
        text=True,
    )
    markdown_result = subprocess.run(
        [sys.executable, "-m", "cli.cage1_review", "--fixture", "conflicting-decisions", "--format", "markdown"],
        capture_output=True,
        text=True,
    )
    assert json_result.returncode == 0, json_result.stderr
    assert markdown_result.returncode == 0, markdown_result.stderr
    payload = json.loads(json_result.stdout)
    assert payload["severity"] == "critical"
    assert payload["recommendation"] == "escalate"
    assert payload["operator_decision_required"] is True
    assert payload["automatic_action_taken"] is False
    assert payload["raw_fleet"]["conflicting_advisories"] == ["advisory-conflict"]
    assert payload["evidence_status"] == {"total": 2, "valid": 2, "invalid_schema": 0, "other": 0}
    markdown = markdown_result.stdout
    assert "conflicting valid decisions for advisory=advisory-conflict" in markdown
    assert "decision=accept" in markdown
    assert "decision=reject" in markdown
    assert "Automatic action taken: **no**" in markdown


def test_evidence_projection_contract_matches_fleet_and_trend_sources():
    from core.cage1_advisory import project_evidence_lines, project_evidence_status

    fleet = {
        "category": "cage1_decision_fleet_audit",
        "lines": [
            {"source_id": "fleet-a.jsonl", "source_line_number": 2, "status": "valid", "decision": "defer"},
            {"source_id": "fleet-b.jsonl", "source_line_number": 9, "status": "invalid_schema"},
        ],
    }
    trend = {
        "category": "cage1_decision_fleet_audit_trend",
        "points": [{
            "snapshot_id": "snapshot-1",
            "line_provenance": [
                {"source_id": "trend-a.jsonl", "source_line_number": 4, "status": "valid", "decision": "accept"},
                {"source_id": "trend-b.jsonl", "source_line_number": 12, "status": "invalid_schema"},
            ],
        }],
    }
    assert project_evidence_lines(fleet) == fleet["lines"]
    assert project_evidence_lines(trend) == [
        {**trend["points"][0]["line_provenance"][0], "_snapshot_id": "snapshot-1"},
        {**trend["points"][0]["line_provenance"][1], "_snapshot_id": "snapshot-1"},
    ]
    assert project_evidence_status(fleet) == {"total": 2, "valid": 1, "invalid_schema": 1, "other": 0}
    assert project_evidence_status(trend) == {"total": 2, "valid": 1, "invalid_schema": 1, "other": 0}


def test_evidence_projection_contract_normalizes_fleet_and_trend_shapes():
    from core.cage1_advisory import project_evidence_lines, project_evidence_status

    fleet = {
        "lines": [
            {"source_id": "fleet-a", "status": "valid"},
            {"source_id": "fleet-b", "status": "invalid_schema"},
        ]
    }
    trend = {
        "points": [
            {
                "snapshot_id": "snapshot-one",
                "line_provenance": [
                    {"source_id": "trend-a", "status": "valid"},
                    {"source_id": "trend-b", "status": "other"},
                ],
            }
        ]
    }

    assert project_evidence_lines(fleet) == fleet["lines"]
    assert project_evidence_status(fleet) == {"total": 2, "valid": 1, "invalid_schema": 1, "other": 0}
    trend_lines = project_evidence_lines(trend)
    assert [line["source_id"] for line in trend_lines] == ["trend-a", "trend-b"]
    assert all(line["_snapshot_id"] == "snapshot-one" for line in trend_lines)
    assert project_evidence_status(trend) == {"total": 2, "valid": 1, "invalid_schema": 0, "other": 1}


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


def test_review_cli_mixed_trend_provenance_is_ordered_and_parity_preserving(tmp_path):
    source = {
        "category": "cage1_decision_fleet_audit_trend",
        "schema_version": "1.0",
        "status": "invalid",
        "points": [
            {
                "snapshot_id": "snapshot-one",
                "status": "invalid",
                "line_provenance": [
                    {
                        "source_id": "member-a.jsonl",
                        "source_line_number": 3,
                        "status": "valid",
                        "decision": "defer",
                    },
                    {
                        "source_id": "member-z.jsonl",
                        "source_line_number": 8,
                        "status": "invalid_schema",
                        "reason": "schema_version must be exactly '1.0'",
                    },
                ],
            },
            {
                "snapshot_id": "snapshot-two",
                "status": "invalid",
                "line_provenance": [
                    {
                        "source_id": "member-b.jsonl",
                        "source_line_number": 4,
                        "status": "valid",
                        "decision": "accept",
                    },
                    {
                        "source_id": "member-y.jsonl",
                        "source_line_number": 11,
                        "status": "invalid_schema",
                        "reason": "category must be exactly 'cage1_decision_audit_line'",
                    },
                ],
            },
        ],
        "flagged_changes": [],
        "decision_applied": False,
        "automatic_action_taken": False,
    }
    source_path = tmp_path / "mixed-trend.json"
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
    assert payload["evidence_status"] == {"total": 4, "valid": 2, "invalid_schema": 2, "other": 0}
    assert [point["snapshot_id"] for point in payload["raw_trend"]["points"]] == ["snapshot-one", "snapshot-two"]
    assert [line["source_id"] for point in payload["raw_trend"]["points"] for line in point["line_provenance"]] == [
        "member-a.jsonl",
        "member-z.jsonl",
        "member-b.jsonl",
        "member-y.jsonl",
    ]
    markdown = markdown_result.stdout
    markers = [
        "source=member-a.jsonl, physical_line=3, snapshot=snapshot-one, decision=defer",
        "source=member-z.jsonl, physical_line=8, snapshot=snapshot-one",
        "source=member-b.jsonl, physical_line=4, snapshot=snapshot-two, decision=accept",
        "source=member-y.jsonl, physical_line=11, snapshot=snapshot-two",
    ]
    assert all(marker in markdown for marker in markers)
    assert [markdown.index(marker) for marker in markers] == sorted(markdown.index(marker) for marker in markers)


def test_advisory_projection_matches_shared_evidence_contract_for_mixed_trend():
    from core.cage1_advisory import project_evidence_status, project_review_advisory

    source = {
        "category": "cage1_decision_fleet_audit_trend",
        "schema_version": "1.0",
        "status": "mixed",
        "points": [
            {
                "snapshot_id": "snapshot-one",
                "status": "mixed",
                "line_provenance": [
                    {"source_id": "member-a.jsonl", "source_line_number": 3, "status": "valid", "decision": "defer"},
                    {"source_id": "member-z.jsonl", "source_line_number": 8, "status": "invalid_schema"},
                ],
            },
            {
                "snapshot_id": "snapshot-two",
                "status": "mixed",
                "line_provenance": [
                    {"source_id": "member-b.jsonl", "source_line_number": 4, "status": "other"},
                    {"source_id": "member-y.jsonl", "source_line_number": 11, "status": "valid", "decision": "accept"},
                ],
            },
        ],
        "flagged_changes": [],
        "decision_applied": False,
        "automatic_action_taken": False,
    }

    advisory = project_review_advisory(source)
    expected = project_evidence_status(source)
    assert expected == {"total": 4, "valid": 2, "invalid_schema": 1, "other": 1}
    assert advisory.evidence_status == expected

    markdown = advisory.to_markdown()
    assert "- Total audit lines: **4**" in markdown
    assert "- Valid audit lines: **2**" in markdown
    assert "- Schema-invalid audit lines: **1**" in markdown
    assert "- Other-status audit lines: **1**" in markdown
    markers = [
        "source=member-a.jsonl, physical_line=3, snapshot=snapshot-one, decision=defer",
        "source=member-z.jsonl, physical_line=8, snapshot=snapshot-one",
        "source=member-y.jsonl, physical_line=11, snapshot=snapshot-two, decision=accept",
    ]
    assert all(marker in markdown for marker in markers)
    assert [markdown.index(marker) for marker in markers] == sorted(markdown.index(marker) for marker in markers)


def test_review_cli_mixed_trend_json_markdown_preserve_evidence_contract(tmp_path):
    source = {
        "category": "cage1_decision_fleet_audit_trend",
        "schema_version": "1.0",
        "status": "mixed",
        "points": [
            {
                "snapshot_id": "snapshot-alpha",
                "status": "mixed",
                "line_provenance": [
                    {"source_id": "alpha-valid.jsonl", "source_line_number": 2, "status": "valid", "decision": "defer"},
                    {"source_id": "alpha-invalid.jsonl", "source_line_number": 7, "status": "invalid_schema"},
                ],
            },
            {
                "snapshot_id": "snapshot-beta",
                "status": "mixed",
                "line_provenance": [
                    {"source_id": "beta-other.jsonl", "source_line_number": 5, "status": "other"},
                    {"source_id": "beta-valid.jsonl", "source_line_number": 9, "status": "valid", "decision": "accept"},
                ],
            },
        ],
        "flagged_changes": [],
        "decision_applied": False,
        "automatic_action_taken": False,
    }
    source_path = tmp_path / "mixed-trend-contract.json"
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
    assert payload["evidence_status"] == {"total": 4, "valid": 2, "invalid_schema": 1, "other": 1}
    markdown = markdown_result.stdout
    assert "- Total audit lines: **4**" in markdown
    assert "- Valid audit lines: **2**" in markdown
    assert "- Schema-invalid audit lines: **1**" in markdown
    assert "- Other-status audit lines: **1**" in markdown
    markers = [
        "source=alpha-valid.jsonl, physical_line=2, snapshot=snapshot-alpha, decision=defer",
        "source=alpha-invalid.jsonl, physical_line=7, snapshot=snapshot-alpha",
        "source=beta-valid.jsonl, physical_line=9, snapshot=snapshot-beta, decision=accept",
    ]
    assert all(marker in markdown for marker in markers)
    assert [markdown.index(marker) for marker in markers] == sorted(markdown.index(marker) for marker in markers)


def test_advisory_markdown_projection_does_not_mutate_fleet_or_trend_evidence():
    from core.cage1_advisory import project_review_advisory

    sources = [
        {
            "category": "cage1_decision_fleet_audit",
            "schema_version": "1.0",
            "status": "invalid",
            "lines": [{
                "source_id": "fleet-member.jsonl",
                "source_line_number": 5,
                "status": "invalid_schema",
                "reason": "missing required field: category",
            }],
        },
        {
            "category": "cage1_decision_fleet_audit_trend",
            "schema_version": "1.0",
            "status": "stable",
            "points": [{
                "snapshot_id": "snapshot-one",
                "status": "invalid",
                "line_provenance": [{
                    "source_id": "trend-member.jsonl",
                    "source_line_number": 9,
                    "status": "invalid_schema",
                    "reason": "schema_version must be exactly '1.0'",
                }],
            }],
            "flagged_changes": [],
            "decision_applied": False,
            "automatic_action_taken": False,
        },
    ]

    for source in sources:
        before = json.loads(json.dumps(source))
        advisory = project_review_advisory(source)
        markdown = advisory.to_markdown()
        assert source == before
        if source["category"].endswith("trend"):
            assert advisory.raw_trend == source
        else:
            assert advisory.raw_fleet == source
        assert "schema-invalid audit line" in markdown
        assert advisory.automatic_action_taken is False
