"""Verification-only fleet aggregation for CAGE-1 decision audit lines."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

from .signed_advisory_envelope import payload_digest

SCHEMA_VERSION = "1.0"
FLEET_CATEGORY = "cage1_decision_fleet_audit"


@dataclass(frozen=True)
class FleetAuditSource:
    source_id: str
    path: str
    line_count: int
    valid_line_count: int
    invalid_line_count: int
    statuses: dict[str, int]
    advisory_digests: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "path": self.path,
            "line_count": self.line_count,
            "valid_line_count": self.valid_line_count,
            "invalid_line_count": self.invalid_line_count,
            "statuses": dict(self.statuses),
            "advisory_digests": list(self.advisory_digests),
        }


@dataclass(frozen=True)
class FleetAuditLine:
    source_id: str
    source_path: str
    source_line_number: int
    status: str
    advisory_digest: Optional[str]
    envelope_digest: Optional[str]
    decision: Optional[str]
    operator_id: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": "cage1_decision_fleet_audit_line",
            "schema_version": SCHEMA_VERSION,
            "source_id": self.source_id,
            "source_path": self.source_path,
            "source_line_number": self.source_line_number,
            "status": self.status,
            "advisory_digest": self.advisory_digest,
            "envelope_digest": self.envelope_digest,
            "decision": self.decision,
            "operator_id": self.operator_id,
        }


@dataclass(frozen=True)
class DecisionFleetAuditSummary:
    category: str
    schema_version: str
    status: str
    source_count: int
    report_count: int
    line_count: int
    valid_line_count: int
    invalid_line_count: int
    status_counts: dict[str, int]
    decision_counts: dict[str, int]
    advisory_counts: dict[str, int]
    conflicting_advisories: list[str]
    sources: list[FleetAuditSource]
    lines: list[FleetAuditLine]
    report_status_counts: dict[str, int]
    decision_applied: bool
    automatic_action_taken: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "schema_version": self.schema_version,
            "status": self.status,
            "source_count": self.source_count,
            "report_count": self.report_count,
            "line_count": self.line_count,
            "valid_line_count": self.valid_line_count,
            "invalid_line_count": self.invalid_line_count,
            "status_counts": dict(self.status_counts),
            "decision_counts": dict(self.decision_counts),
            "advisory_counts": dict(self.advisory_counts),
            "conflicting_advisories": list(self.conflicting_advisories),
            "sources": [source.to_dict() for source in self.sources],
            "lines": [line.to_dict() for line in self.lines],
            "report_status_counts": dict(self.report_status_counts),
            "decision_applied": self.decision_applied,
            "automatic_action_taken": self.automatic_action_taken,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def _read_jsonl(path: str) -> list[Mapping[str, Any]]:
    records: list[Mapping[str, Any]] = []
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        value = json.loads(raw_line)
        if not isinstance(value, Mapping):
            raise ValueError(f"audit line in {path} must be a JSON object")
        records.append(value)
    return records


def load_decision_audit_jsonl(path: str, *, source_id: Optional[str] = None) -> tuple[FleetAuditSource, list[FleetAuditLine]]:
    source_path = str(path)
    identity = source_id or Path(path).name
    records = _read_jsonl(path)
    statuses = Counter(str(record.get("status", "missing_status")) for record in records)
    advisory_digests = sorted({str(record["advisory_digest"]) for record in records if record.get("advisory_digest")})
    lines = [
        FleetAuditLine(
            source_id=identity,
            source_path=source_path,
            source_line_number=int(record.get("line_number", index)),
            status=str(record.get("status", "missing_status")),
            advisory_digest=str(record["advisory_digest"]) if record.get("advisory_digest") else None,
            envelope_digest=str(record["envelope_digest"]) if record.get("envelope_digest") else None,
            decision=str(record["decision"]) if record.get("decision") else None,
            operator_id=str(record["operator_id"]) if record.get("operator_id") else None,
        )
        for index, record in enumerate(records, start=1)
    ]
    valid = statuses.get("valid", 0)
    return FleetAuditSource(identity, source_path, len(lines), valid, len(lines) - valid, dict(sorted(statuses.items())), advisory_digests), lines


def _summary(sources: list[FleetAuditSource], lines: list[FleetAuditLine], report_status_counts: Counter[str]) -> DecisionFleetAuditSummary:
    status_counts = Counter(line.status for line in lines)
    decision_counts = Counter(line.decision for line in lines if line.status == "valid" and line.decision)
    advisory_counts = Counter(line.advisory_digest for line in lines if line.advisory_digest)
    conflicts = sorted(advisory for advisory, count in advisory_counts.items() if count > 1 and len({line.decision for line in lines if line.advisory_digest == advisory and line.status == "valid" and line.decision}) > 1)
    if not lines:
        status = "unverified"
    elif conflicts:
        status = "conflicting"
    elif any(line.status != "valid" for line in lines):
        status = "invalid"
    else:
        status = "valid"
    return DecisionFleetAuditSummary(
        category=FLEET_CATEGORY,
        schema_version=SCHEMA_VERSION,
        status=status,
        source_count=len(sources),
        report_count=sum(report_status_counts.values()),
        line_count=len(lines),
        valid_line_count=status_counts.get("valid", 0),
        invalid_line_count=len(lines) - status_counts.get("valid", 0),
        status_counts=dict(sorted(status_counts.items())),
        decision_counts=dict(sorted(decision_counts.items())),
        advisory_counts=dict(sorted(advisory_counts.items())),
        conflicting_advisories=conflicts,
        sources=sources,
        lines=lines,
        report_status_counts=dict(sorted(report_status_counts.items())),
        decision_applied=False,
        automatic_action_taken=False,
    )


def aggregate_decision_audits(
    audits: Iterable[tuple[FleetAuditSource, Iterable[FleetAuditLine]]],
    *,
    report_statuses: Iterable[str] = (),
) -> DecisionFleetAuditSummary:
    sources: list[FleetAuditSource] = []
    lines: list[FleetAuditLine] = []
    for source, source_lines in audits:
        sources.append(source)
        lines.extend(source_lines)
    return _summary(sources, lines, Counter(report_statuses))


def aggregate_decision_audit_files(paths: Sequence[str], *, report_paths: Optional[Sequence[str]] = None) -> DecisionFleetAuditSummary:
    if not paths:
        raise ValueError("at least one audit path is required")
    if report_paths and len(report_paths) != len(paths):
        raise ValueError("--report must be supplied once per --audit")
    audits = [load_decision_audit_jsonl(path) for path in paths]
    report_statuses: list[str] = []
    for path in report_paths or []:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise ValueError(f"report in {path} must be a JSON object")
        report_statuses.append(str(value.get("status", "missing_status")))
    return aggregate_decision_audits(audits, report_statuses=report_statuses)


def write_fleet_audit_jsonl(summary: DecisionFleetAuditSummary, path: str) -> None:
    records: list[dict[str, Any]] = []
    records.extend(line.to_dict() for line in summary.lines)
    records.append({"category": FLEET_CATEGORY, "schema_version": SCHEMA_VERSION, "record_type": "summary", **summary.to_dict()})
    Path(path).write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records), encoding="utf-8")


__all__ = [
    "DecisionFleetAuditSummary",
    "FleetAuditLine",
    "FleetAuditSource",
    "aggregate_decision_audit_files",
    "aggregate_decision_audits",
    "load_decision_audit_jsonl",
    "write_fleet_audit_jsonl",
]
