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
