"""Validation tests for signed, review-only CAGE-1 operator decisions."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from core.cage1_decision import (
    create_operator_decision,
    sign_operator_decision,
    verify_operator_decision,
)
from core.signed_advisory_envelope import EnvelopeConfig, KeyRegistry, envelope_from_json


@pytest.fixture
def advisory():
    return {
        "category": "cage1_fleet_review",
        "severity": "high",
        "recommendation": "review",
        "operator_decision_required": True,
        "automatic_action_taken": False,
        "raw_fleet": {"sessions": [{"label": "s1", "report_digest": "abc"}]},
    }


def test_decision_record_is_content_addressed_and_review_only(advisory):
    record = create_operator_decision(advisory, "defer", "operator-1", rationale="need another run", decided_at=10)
    assert record.advisory_digest
    assert record.automatic_action_taken is False
    assert record.to_dict()["decision"] == "defer"


def test_decision_rejects_tampered_advisory_digest(advisory):
    record = create_operator_decision(advisory, "accept", "operator-1")
    payload = record.to_dict()
    payload["advisory"]["severity"] = "critical"
    with pytest.raises(ValueError, match="advisory_digest"):
        type(record).from_dict(payload)


def test_decision_rejects_auto_action(advisory):
    record = create_operator_decision(advisory, "reject", "operator-1")
    payload = record.to_dict()
    payload["automatic_action_taken"] = True
    with pytest.raises(ValueError, match="automatic action"):
        type(record).from_dict(payload)


def test_signed_decision_verifies(advisory):
    record = create_operator_decision(advisory, "accept", "operator-1", decided_at=10)
    envelope = sign_operator_decision(record, "review-key", b"secret", config=EnvelopeConfig(issued_at=10), now=10)
    keys = KeyRegistry()
    keys.register("review-key", b"secret")
    result = verify_operator_decision(envelope, keys, now=10)
    assert result.valid is True
    assert result.decision == "accept"
    assert result.operator_id == "operator-1"
    assert result.advisory_digest == record.advisory_digest


def test_tampered_signed_decision_fails(advisory):
    record = create_operator_decision(advisory, "reject", "operator-1", decided_at=10)
    envelope = sign_operator_decision(record, "review-key", b"secret", config=EnvelopeConfig(issued_at=10), now=10)
    payload = envelope.to_dict()
    payload["payload"]["decision"] = "accept"
    keys = KeyRegistry()
    keys.register("review-key", b"secret")
    result = verify_operator_decision(payload, keys, now=10)
    assert result.valid is False
    assert result.status == "payload_mismatch"


def test_cli_create_sign_verify(tmp_path, advisory):
    advisory_path = tmp_path / "advisory.json"
    advisory_path.write_text(json.dumps(advisory), encoding="utf-8")
    decision_path = tmp_path / "decision.json"
    envelope_path = tmp_path / "decision-envelope.json"
    create = subprocess.run(
        [sys.executable, "-m", "cli.cage1_decision", "create", "--advisory", str(advisory_path), "--decision", "defer", "--operator-id", "op-1", "--out", str(decision_path)],
        capture_output=True,
        text=True,
    )
    assert create.returncode == 0, create.stderr
    sign = subprocess.run(
        [sys.executable, "-m", "cli.cage1_decision", "sign", "--decision", str(decision_path), "--key-id", "k1", "--hmac-secret", "secret", "--issued-at", "10", "--out", str(envelope_path)],
        capture_output=True,
        text=True,
    )
    assert sign.returncode == 0, sign.stderr
    verify = subprocess.run(
        [sys.executable, "-m", "cli.cage1_decision", "verify", "--envelope", str(envelope_path), "--key-id", "k1", "--hmac-secret", "secret", "--now", "10"],
        capture_output=True,
        text=True,
    )
    assert verify.returncode == 0, verify.stderr
    assert json.loads(verify.stdout)["decision"] == "defer"
