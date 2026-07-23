"""Signed, review-only operator decisions for CAGE-1 advisories."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from .signed_advisory_envelope import (
    EnvelopeConfig,
    EnvelopeVerification,
    KeyResolver,
    SignedEnvelope,
    payload_digest,
    sign_envelope,
    verify_envelope,
)


SCHEMA_VERSION = "1.0"
DECISION_CATEGORY = "cage1_operator_decision"
VALID_DECISIONS = frozenset({"accept", "reject", "defer"})


@dataclass(frozen=True)
class OperatorDecision:
    category: str
    schema_version: str
    decision: str
    operator_id: str
    decided_at: float
    advisory_digest: str
    advisory: dict[str, Any]
    rationale: str
    automatic_action_taken: bool = False

    def __post_init__(self) -> None:
        if self.category != DECISION_CATEGORY:
            raise ValueError(f"unexpected decision category: {self.category!r}")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported decision schema: {self.schema_version!r}")
        if self.decision not in VALID_DECISIONS:
            raise ValueError(f"decision must be one of {sorted(VALID_DECISIONS)}")
        if not self.operator_id.strip():
            raise ValueError("operator_id must not be empty")
        if not self.advisory_digest:
            raise ValueError("advisory_digest must not be empty")
        if payload_digest(self.advisory) != self.advisory_digest:
            raise ValueError("advisory_digest does not match embedded advisory")
        if self.automatic_action_taken:
            raise ValueError("operator decisions are review-only; automatic action is forbidden")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OperatorDecision":
        if not isinstance(value, Mapping):
            raise TypeError(f"decision record must be a mapping, got {type(value).__name__}")
        advisory = value.get("advisory")
        if not isinstance(advisory, Mapping):
            raise ValueError("decision record must contain an advisory mapping")
        return cls(
            category=str(value.get("category", "")),
            schema_version=str(value.get("schema_version", "")),
            decision=str(value.get("decision", "")),
            operator_id=str(value.get("operator_id", "")),
            decided_at=float(value.get("decided_at", 0.0)),
            advisory_digest=str(value.get("advisory_digest", "")),
            advisory=dict(advisory),
            rationale=str(value.get("rationale", "")),
            automatic_action_taken=bool(value.get("automatic_action_taken", False)),
        )


@dataclass(frozen=True)
class DecisionVerification:
    valid: bool
    status: str
    reason: str
    decision: Optional[str]
    operator_id: Optional[str]
    advisory_digest: Optional[str]
    envelope: EnvelopeVerification

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "status": self.status,
            "reason": self.reason,
            "decision": self.decision,
            "operator_id": self.operator_id,
            "advisory_digest": self.advisory_digest,
            "envelope": self.envelope.to_dict(),
        }


def create_operator_decision(
    advisory: Mapping[str, Any],
    decision: str,
    operator_id: str,
    *,
    rationale: str = "",
    decided_at: Optional[float] = None,
) -> OperatorDecision:
    """Create an immutable decision record without taking any action."""
    advisory_copy = dict(advisory)
    return OperatorDecision(
        category=DECISION_CATEGORY,
        schema_version=SCHEMA_VERSION,
        decision=decision,
        operator_id=operator_id,
        decided_at=float(time.time() if decided_at is None else decided_at),
        advisory_digest=payload_digest(advisory_copy),
        advisory=advisory_copy,
        rationale=rationale,
        automatic_action_taken=False,
    )


def sign_operator_decision(
    record: OperatorDecision,
    key_id: str,
    key: Any,
    *,
    config: Optional[EnvelopeConfig] = None,
    now: Optional[float] = None,
) -> SignedEnvelope:
    """Sign a decision record; signing does not execute or apply it."""
    return sign_envelope(record.to_dict(), key_id, key, config=config, now=now)


def verify_operator_decision(
    envelope: SignedEnvelope | Mapping[str, Any],
    resolver: KeyResolver,
    *,
    now: Optional[float] = None,
) -> DecisionVerification:
    """Verify signature, payload integrity, and decision-record invariants."""
    envelope_result = verify_envelope(envelope, resolver, now=now)
    if not envelope_result.is_valid():
        return DecisionVerification(
            valid=False,
            status=envelope_result.status,
            reason=envelope_result.reason,
            decision=None,
            operator_id=None,
            advisory_digest=None,
            envelope=envelope_result,
        )
    try:
        record = OperatorDecision.from_dict(envelope_result.payload or {})
    except (TypeError, ValueError, KeyError) as exc:
        return DecisionVerification(
            valid=False,
            status="invalid_decision_record",
            reason=str(exc),
            decision=None,
            operator_id=None,
            advisory_digest=None,
            envelope=envelope_result,
        )
    return DecisionVerification(
        valid=True,
        status="valid",
        reason="signature, advisory digest, and review-only invariants verified",
        decision=record.decision,
        operator_id=record.operator_id,
        advisory_digest=record.advisory_digest,
        envelope=envelope_result,
    )


def write_operator_decision(record: OperatorDecision, path: str) -> None:
    Path(path).write_text(record.to_json() + "\n", encoding="utf-8")


def write_signed_decision(envelope: SignedEnvelope, path: str) -> None:
    from .signed_advisory_envelope import envelope_to_json

    Path(path).write_text(envelope_to_json(envelope, indent=2) + "\n", encoding="utf-8")


__all__ = [
    "DECISION_CATEGORY",
    "DecisionVerification",
    "OperatorDecision",
    "SCHEMA_VERSION",
    "VALID_DECISIONS",
    "create_operator_decision",
    "sign_operator_decision",
    "verify_operator_decision",
    "write_operator_decision",
    "write_signed_decision",
]
