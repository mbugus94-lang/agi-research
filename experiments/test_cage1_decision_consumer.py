from __future__ import annotations

import json
import subprocess
import sys

from core.cage1_advisory import project_review_advisory
from core.cage1_decision import create_operator_decision, sign_operator_decision
from core.cage1_decision_consumer import consume_operator_decision, consume_operator_decision_jsonl
from core.cage1_trend import trend_fleet_snapshots
from core.signed_advisory_envelope import EnvelopeConfig, KeyRegistry


def _snapshot(label, digest):
    return {
        "label": label,
        "report_digest": digest,
        "n_reports": 2,
        "substrate_coverage": 1.0,
        "outcome_distribution": {"admitted": 2, "refused": 0, "escalated": 0, "made_non_effective": 0},
        "memory_integrity": {"measured": False, "score": None},
        "retrieval_quality": {"measured": False, "score": None},
    }


def _fixture():
    source = trend_fleet_snapshots([_snapshot("s1", "one")], notes="fixture")
    advisory = project_review_advisory(source)
    record = create_operator_decision(advisory.to_dict(), "defer", "operator-1", decided_at=10)
    envelope = sign_operator_decision(record, "k1", b"secret", config=EnvelopeConfig(issued_at=10), now=10)
    keys = KeyRegistry()
    keys.register("k1", b"secret")
    return source, advisory, envelope, keys


def test_valid_join_is_verify_only():
    source, advisory, envelope, keys = _fixture()
    report = consume_operator_decision(advisory, [envelope], keys, raw_source=source, now=10)
    assert report.valid is True
    assert report.status == "valid"
    assert report.decision == "defer"
    assert report.decision_applied is False
    assert report.automatic_action_taken is False
    assert report.raw_evidence_status == "match"


def test_missing_raw_evidence_is_not_valid():
    _, advisory, envelope, keys = _fixture()
    report = consume_operator_decision(advisory, [envelope], keys, now=10)
    assert report.valid is False
    assert report.status == "missing"
    assert report.decision_applied is False


def test_tampered_raw_evidence_is_rejected():
    source, advisory, envelope, keys = _fixture()
    raw = source.to_dict()
    raw["fleet"]["sessions"][0]["label"] = "tampered"
    report = consume_operator_decision(advisory, [envelope], keys, raw_source=raw, now=10)
    assert report.valid is False
    assert report.status == "invalid"
    assert report.raw_evidence_status == "mismatch"


def test_conflicting_valid_decisions_are_ambiguous():
    source, advisory, first, keys = _fixture()
    reject = create_operator_decision(advisory.to_dict(), "reject", "operator-2", decided_at=10)
    second = sign_operator_decision(reject, "k1", b"secret", config=EnvelopeConfig(issued_at=10), now=10)
    report = consume_operator_decision(advisory, [first, second], keys, raw_source=source, now=10)
    assert report.valid is False
    assert report.status == "conflicting"
    assert report.decision is None
    assert report.valid_decision_count == 2


def test_cli_consume_valid(tmp_path):
    source, advisory, envelope, _ = _fixture()
    advisory_path = tmp_path / "advisory.json"
    raw_path = tmp_path / "raw.json"
    envelope_path = tmp_path / "envelope.json"
    advisory_path.write_text(advisory.to_json(), encoding="utf-8")
    raw_path.write_text(source.to_json(), encoding="utf-8")
    from core.signed_advisory_envelope import envelope_to_json
    envelope_path.write_text(envelope_to_json(envelope, indent=2), encoding="utf-8")
    result = subprocess.run([
        sys.executable, "-m", "cli.cage1_consume",
        "--advisory", str(advisory_path), "--raw-source", str(raw_path),
        "--envelope", str(envelope_path), "--key-id", "k1", "--hmac-secret", "secret", "--now", "10",
    ], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["valid"] is True
    assert payload["decision_applied"] is False


def test_expired_decision_is_reported_without_selection():
    source, advisory, _, keys = _fixture()
    record = create_operator_decision(advisory.to_dict(), "defer", "operator-expired", decided_at=10)
    expired = sign_operator_decision(
        record,
        "k1",
        b"secret",
        config=EnvelopeConfig(issued_at=10, expires_at=10),
        now=10,
    )
    report = consume_operator_decision(advisory, [expired], keys, raw_source=source, now=10)
    assert report.valid is False
    assert report.status == "invalid"
    assert report.decision is None
    assert report.invalid_statuses == ["expired"]


def test_cli_expired_envelope_is_machine_readable(tmp_path):
    source, advisory, _, _ = _fixture()
    record = create_operator_decision(advisory.to_dict(), "defer", "operator-expired", decided_at=10)
    expired = sign_operator_decision(
        record,
        "k1",
        b"secret",
        config=EnvelopeConfig(issued_at=10, expires_at=10),
        now=10,
    )
    from core.signed_advisory_envelope import envelope_to_json
    advisory_path = tmp_path / "advisory.json"
    raw_path = tmp_path / "raw.json"
    envelope_path = tmp_path / "expired.json"
    advisory_path.write_text(advisory.to_json(), encoding="utf-8")
    raw_path.write_text(source.to_json(), encoding="utf-8")
    envelope_path.write_text(envelope_to_json(expired, indent=2), encoding="utf-8")
    result = subprocess.run([
        sys.executable, "-m", "cli.cage1_consume",
        "--advisory", str(advisory_path), "--raw-source", str(raw_path),
        "--envelope", str(envelope_path), "--key-id", "k1",
        "--hmac-secret", "secret", "--now", "10",
    ], capture_output=True, text=True)
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "invalid"
    assert payload["invalid_statuses"] == ["expired"]
    assert payload["decision"] is None


def test_cli_malformed_envelope_returns_structured_error(tmp_path):
    source, advisory, _, _ = _fixture()
    advisory_path = tmp_path / "advisory.json"
    raw_path = tmp_path / "raw.json"
    envelope_path = tmp_path / "malformed.json"
    advisory_path.write_text(advisory.to_json(), encoding="utf-8")
    raw_path.write_text(source.to_json(), encoding="utf-8")
    envelope_path.write_text("{}", encoding="utf-8")
    result = subprocess.run([
        sys.executable, "-m", "cli.cage1_consume",
        "--advisory", str(advisory_path), "--raw-source", str(raw_path),
        "--envelope", str(envelope_path), "--key-id", "k1",
        "--hmac-secret", "secret", "--now", "10",
    ], capture_output=True, text=True)
    assert result.returncode == 2
    assert result.stdout == ""
    assert "ERROR:" in result.stderr
    assert "missing required fields" in result.stderr


def test_jsonl_audit_retains_valid_expired_and_malformed_lines():
    source, advisory, valid_envelope, keys = _fixture()
    record = create_operator_decision(advisory.to_dict(), "defer", "operator-expired", decided_at=10)
    expired = sign_operator_decision(record, "k1", b"secret", config=EnvelopeConfig(issued_at=10, expires_at=10), now=10)
    from core.signed_advisory_envelope import envelope_to_json
    jsonl = "\n".join([
        envelope_to_json(valid_envelope),
        envelope_to_json(expired),
        "not-json",
        "[]",
    ])
    audit = consume_operator_decision_jsonl(advisory, jsonl, keys, raw_source=source, now=10)
    assert audit.report.valid is False
    assert audit.report.status == "invalid"
    assert audit.report.invalid_decision_count == 3
    assert [line.status for line in audit.lines] == ["valid", "expired", "malformed_json", "malformed_record"]
    assert audit.lines[0].envelope_digest == valid_envelope.payload_digest
    assert audit.lines[1].decision is None


def test_jsonl_audit_empty_lines_are_not_records():
    source, advisory, envelope, keys = _fixture()
    from core.signed_advisory_envelope import envelope_to_json
    audit = consume_operator_decision_jsonl(advisory, "\n" + envelope_to_json(envelope) + "\n\n", keys, raw_source=source, now=10)
    assert len(audit.lines) == 1
    assert audit.report.valid is True


def test_cli_jsonl_audit_writes_machine_readable_lines(tmp_path):
    source, advisory, envelope, _ = _fixture()
    from core.signed_advisory_envelope import envelope_to_json
    advisory_path = tmp_path / "advisory.json"
    raw_path = tmp_path / "raw.json"
    decisions_path = tmp_path / "decisions.jsonl"
    audit_path = tmp_path / "audit.jsonl"
    advisory_path.write_text(advisory.to_json(), encoding="utf-8")
    raw_path.write_text(source.to_json(), encoding="utf-8")
    decisions_path.write_text(envelope_to_json(envelope) + "\nnot-json\n", encoding="utf-8")
    result = subprocess.run([
        sys.executable, "-m", "cli.cage1_consume",
        "--advisory", str(advisory_path), "--raw-source", str(raw_path),
        "--decisions-jsonl", str(decisions_path), "--audit-out", str(audit_path),
        "--key-id", "k1", "--hmac-secret", "secret", "--now", "10",
    ], capture_output=True, text=True)
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "invalid"
    audit_lines = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
    assert [line["status"] for line in audit_lines] == ["valid", "malformed_json"]
    assert audit_lines[1]["line_number"] == 2


def test_cli_requires_one_decision_input_mode(tmp_path):
    result = subprocess.run([
        sys.executable, "-m", "cli.cage1_consume",
        "--advisory", str(tmp_path / "missing.json"), "--raw-source", str(tmp_path / "missing-raw.json"),
        "--key-id", "k1", "--hmac-secret", "secret",
    ], capture_output=True, text=True)
    assert result.returncode == 2
    assert "provide --envelope or --decisions-jsonl" in result.stderr
