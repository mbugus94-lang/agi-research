"""Verification-only joining of CAGE-1 advisories, decisions, and evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from .cage1_decision import verify_operator_decision
from .signed_advisory_envelope import KeyResolver, SignedEnvelope


CONSUMER_CATEGORY = "cage1_decision_consumer_report"
SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class DecisionConsumerReport:
    category: str
    schema_version: str
    valid: bool
    status: str
    reason: str
    advisory_digest: str
    raw_evidence_digest: Optional[str]
    raw_evidence_status: str
    decision: Optional[str]
    operator_ids: list[str]
    valid_decision_count: int
    invalid_decision_count: int
    invalid_statuses: list[str]
    decision_applied: bool
    automatic_action_taken: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "schema_version": self.schema_version,
            "valid": self.valid,
            "status": self.status,
            "reason": self.reason,
            "advisory_digest": self.advisory_digest,
            "raw_evidence_digest": self.raw_evidence_digest,
            "raw_evidence_status": self.raw_evidence_status,
            "decision": self.decision,
            "operator_ids": list(self.operator_ids),
            "valid_decision_count": self.valid_decision_count,
            "invalid_decision_count": self.invalid_decision_count,
            "invalid_statuses": list(self.invalid_statuses),
            "decision_applied": self.decision_applied,
            "automatic_action_taken": self.automatic_action_taken,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if not isinstance(value, Mapping):
        raise TypeError(f"value must be a mapping or expose to_dict(), got {type(value).__name__}")
    return value


def _canonical_digest(value: Mapping[str, Any]) -> str:
    from .signed_advisory_envelope import payload_digest

    return payload_digest(value)


def _evidence_payload(advisory: Mapping[str, Any]) -> Optional[dict[str, Any]]:
    trend = advisory.get("raw_trend")
    fleet = advisory.get("raw_fleet")
    if not isinstance(fleet, Mapping):
        return None
    return {
        "trend": dict(trend) if isinstance(trend, Mapping) else {},
        "fleet": dict(fleet),
    }


def consume_operator_decision(
    advisory: Mapping[str, Any] | Any,
    envelopes: Iterable[SignedEnvelope | Mapping[str, Any]],
    resolver: KeyResolver,
    *,
    raw_source: Mapping[str, Any] | Any | None = None,
    now: Optional[float] = None,
) -> DecisionConsumerReport:
    """Join evidence and verified decisions without executing a decision.

    The advisory and optional raw source are compared by content digest.
    A single unambiguous valid decision is reported, but never applied.
    """
    advisory_map = dict(_as_mapping(advisory))
    advisory_digest = _canonical_digest(advisory_map)
    expected_raw = _evidence_payload(advisory_map)
    raw_digest: Optional[str] = None
    if raw_source is None:
        evidence_status = "missing"
    else:
        raw_map = dict(_as_mapping(raw_source))
        raw_digest = _canonical_digest(raw_map)
        evidence_status = "match" if expected_raw is not None and raw_map == expected_raw else "mismatch"

    verified = [verify_operator_decision(item, resolver, now=now) for item in envelopes]
    valid_records = []
    invalid_statuses = []
    for result in verified:
        if not result.valid:
            invalid_statuses.append(result.status)
            continue
        if result.advisory_digest != advisory_digest:
            invalid_statuses.append("advisory_mismatch")
            continue
        valid_records.append(result)

    operator_ids = [str(item.operator_id) for item in valid_records if item.operator_id]
    decisions = {str(item.decision) for item in valid_records if item.decision}
    invalid_count = len(verified) - len(valid_records)
    if evidence_status == "missing":
        status, reason = "missing", "raw fleet/trend evidence was not supplied"
    elif evidence_status == "mismatch":
        status, reason = "invalid", "raw fleet/trend evidence does not match the advisory envelope"
    elif invalid_count and not valid_records:
        status, reason = "invalid", "no decision envelope passed signature and advisory checks"
    elif len(decisions) > 1:
        status, reason = "conflicting", "valid operator decisions conflict; no decision is selected"
    elif len(valid_records) == 1:
        status, reason = "valid", "advisory, raw evidence, and one signed operator decision verified"
    elif len(valid_records) > 1:
        status, reason = "ambiguous", "multiple valid operator decisions require operator review"
    else:
        status, reason = "missing", "no decision envelope was supplied"

    return DecisionConsumerReport(
        category=CONSUMER_CATEGORY,
        schema_version=SCHEMA_VERSION,
        valid=status == "valid" and evidence_status == "match",
        status=status,
        reason=reason,
        advisory_digest=advisory_digest,
        raw_evidence_digest=raw_digest,
        raw_evidence_status=evidence_status,
        decision=next(iter(decisions)) if len(decisions) == 1 and status == "valid" else None,
        operator_ids=operator_ids,
        valid_decision_count=len(valid_records),
        invalid_decision_count=invalid_count,
        invalid_statuses=invalid_statuses,
        decision_applied=False,
        automatic_action_taken=False,
    )


def write_consumer_report(report: DecisionConsumerReport, path: str) -> None:
    Path(path).write_text(report.to_json() + "\n", encoding="utf-8")


__all__ = ["CONSUMER_CATEGORY", "DecisionConsumerReport", "consume_operator_decision", "write_consumer_report"]
