"""Verification-only trend and delta reports for CAGE-1 fleet audits."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

SCHEMA_VERSION = "1.0"
TREND_CATEGORY = "cage1_decision_fleet_audit_trend"
FLEET_CATEGORY = "cage1_decision_fleet_audit"
_STATUS_RANK = {"valid": 0, "unverified": 1, "invalid": 2, "conflicting": 3}


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _validated_count(value: Any, label: str, *, default: int = 0) -> int:
    if value is None:
        value = default
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"invalid {label}: expected a non-negative integer")
    return value


def _count_map(value: Any, label: str) -> dict[str, int]:
    raw = _mapping(value or {}, label)
    result: dict[str, int] = {}
    for key, count in raw.items():
        result[str(key)] = _validated_count(count, f"{label}[{key!r}]")
    return dict(sorted(result.items()))


def _provenance_list(value: Any, label: str, *, required: bool = False) -> list[dict[str, Any]]:
    if value is None:
        if required:
            raise ValueError(f"missing {label}")
        return []
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a JSON array")
    return [dict(_mapping(item, f"{label} item")) for item in value]


def _delta(after: Mapping[str, int], before: Mapping[str, int]) -> dict[str, int]:
    keys = set(after) | set(before)
    return dict(sorted({key: after.get(key, 0) - before.get(key, 0) for key in keys if after.get(key, 0) != before.get(key, 0)}.items()))


def _missing_decisions(lines: Sequence[Mapping[str, Any]]) -> int:
    return sum(1 for line in lines if line.get("decision") is None)


def _validate_summary_schema(summary: Mapping[str, Any], path: str) -> None:
    if summary.get("category") != FLEET_CATEGORY:
        raise ValueError(f"unsupported category in {path}: {summary.get('category')!r}")
    if summary.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version in {path}: {summary.get('schema_version')!r}")


@dataclass(frozen=True)
class FleetAuditTrendPoint:
    snapshot_id: str
    summary_path: str
    status: str
    source_count: int
    report_count: int
    line_count: int
    valid_line_count: int
    invalid_line_count: int
    missing_decision_count: int
    status_counts: dict[str, int]
    decision_counts: dict[str, int]
    advisory_counts: dict[str, int]
    conflicting_advisories: list[str]
    report_status_counts: dict[str, int]
    source_provenance: list[dict[str, Any]]
    line_provenance: list[dict[str, Any]]

    @classmethod
    def from_summary(cls, summary: Mapping[str, Any], *, snapshot_id: str, summary_path: str) -> "FleetAuditTrendPoint":
        _validate_summary_schema(summary, summary_path)
        if "lines" not in summary:
            raise ValueError("missing lines")
        lines = _provenance_list(summary.get("lines"), "lines", required=True)
        sources = _provenance_list(summary.get("sources", []), "sources")
        status = str(summary.get("status", "unverified"))
        if status not in _STATUS_RANK:
            raise ValueError(f"unsupported fleet status: {status}")
        source_count = _validated_count(summary.get("source_count"), "source_count", default=len(sources))
        report_count = _validated_count(summary.get("report_count"), "report_count")
        line_count = _validated_count(summary.get("line_count"), "line_count", default=len(lines))
        valid_line_count = _validated_count(summary.get("valid_line_count"), "valid_line_count")
        invalid_line_count = _validated_count(summary.get("invalid_line_count"), "invalid_line_count")
        if line_count != len(lines):
            raise ValueError("line_count does not match lines provenance")
        if valid_line_count + invalid_line_count != line_count:
            raise ValueError("valid_line_count + invalid_line_count does not equal line_count")
        return cls(
            snapshot_id=snapshot_id,
            summary_path=summary_path,
            status=status,
            source_count=source_count,
            report_count=report_count,
            line_count=line_count,
            valid_line_count=valid_line_count,
            invalid_line_count=invalid_line_count,
            missing_decision_count=_missing_decisions(lines),
            status_counts=_count_map(summary.get("status_counts", {}), "status_counts"),
            decision_counts=_count_map(summary.get("decision_counts", {}), "decision_counts"),
            advisory_counts=_count_map(summary.get("advisory_counts", {}), "advisory_counts"),
            conflicting_advisories=sorted(str(item) for item in summary.get("conflicting_advisories", [])),
            report_status_counts=_count_map(summary.get("report_status_counts", {}), "report_status_counts"),
            source_provenance=sources,
            line_provenance=lines,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "summary_path": self.summary_path,
            "status": self.status,
            "source_count": self.source_count,
            "report_count": self.report_count,
            "line_count": self.line_count,
            "valid_line_count": self.valid_line_count,
            "invalid_line_count": self.invalid_line_count,
            "missing_decision_count": self.missing_decision_count,
            "status_counts": dict(self.status_counts),
            "decision_counts": dict(self.decision_counts),
            "advisory_counts": dict(self.advisory_counts),
            "conflicting_advisories": list(self.conflicting_advisories),
            "report_status_counts": dict(self.report_status_counts),
            "source_provenance": [dict(item) for item in self.source_provenance],
            "line_provenance": [dict(item) for item in self.line_provenance],
        }


@dataclass(frozen=True)
class FleetAuditTrendDelta:
    from_snapshot: str
    to_snapshot: str
    from_status: str
    to_status: str
    trend: str
    source_delta: int
    report_delta: int
    line_delta: int
    invalid_line_delta: int
    missing_decision_delta: int
    conflicting_advisory_delta: int
    status_counts_delta: dict[str, int]
    decision_counts_delta: dict[str, int]
    flags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "from_snapshot": self.from_snapshot,
            "to_snapshot": self.to_snapshot,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "trend": self.trend,
            "source_delta": self.source_delta,
            "report_delta": self.report_delta,
            "line_delta": self.line_delta,
            "invalid_line_delta": self.invalid_line_delta,
            "missing_decision_delta": self.missing_decision_delta,
            "conflicting_advisory_delta": self.conflicting_advisory_delta,
            "status_counts_delta": dict(self.status_counts_delta),
            "decision_counts_delta": dict(self.decision_counts_delta),
            "flags": list(self.flags),
        }


def _build_delta(before: FleetAuditTrendPoint, after: FleetAuditTrendPoint) -> FleetAuditTrendDelta:
    invalid_delta = after.invalid_line_count - before.invalid_line_count
    missing_delta = after.missing_decision_count - before.missing_decision_count
    conflict_delta = len(after.conflicting_advisories) - len(before.conflicting_advisories)
    status_rank_change = _STATUS_RANK[after.status] - _STATUS_RANK[before.status]
    trend = "degraded" if status_rank_change > 0 else "improved" if status_rank_change < 0 else "unchanged"
    flags: list[str] = []
    if invalid_delta > 0:
        flags.append("invalid_records_increased")
    elif invalid_delta < 0:
        flags.append("invalid_records_decreased")
    if conflict_delta > 0:
        flags.append("conflicting_advisories_increased")
    elif conflict_delta < 0:
        flags.append("conflicting_advisories_decreased")
    if missing_delta > 0:
        flags.append("missing_decisions_increased")
    elif missing_delta < 0:
        flags.append("missing_decisions_decreased")
    if status_rank_change > 0:
        flags.append("fleet_status_degraded")
    elif status_rank_change < 0:
        flags.append("fleet_status_improved")
    before_sources = {str(item.get("source_id")) for item in before.source_provenance if item.get("source_id") is not None}
    after_sources = {str(item.get("source_id")) for item in after.source_provenance if item.get("source_id") is not None}
    if before_sources != after_sources:
        flags.append("source_membership_changed")
    return FleetAuditTrendDelta(
        from_snapshot=before.snapshot_id,
        to_snapshot=after.snapshot_id,
        from_status=before.status,
        to_status=after.status,
        trend=trend,
        source_delta=after.source_count - before.source_count,
        report_delta=after.report_count - before.report_count,
        line_delta=after.line_count - before.line_count,
        invalid_line_delta=invalid_delta,
        missing_decision_delta=missing_delta,
        conflicting_advisory_delta=conflict_delta,
        status_counts_delta=_delta(after.status_counts, before.status_counts),
        decision_counts_delta=_delta(after.decision_counts, before.decision_counts),
        flags=flags,
    )


@dataclass(frozen=True)
class DecisionFleetAuditTrend:
    category: str
    schema_version: str
    status: str
    points: list[FleetAuditTrendPoint]
    deltas: list[FleetAuditTrendDelta]
    flagged_changes: list[str]
    decision_applied: bool
    automatic_action_taken: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "schema_version": self.schema_version,
            "status": self.status,
            "points": [point.to_dict() for point in self.points],
            "deltas": [delta.to_dict() for delta in self.deltas],
            "flagged_changes": list(self.flagged_changes),
            "decision_applied": self.decision_applied,
            "automatic_action_taken": self.automatic_action_taken,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def load_fleet_audit_summary(path: str, *, snapshot_id: Optional[str] = None) -> FleetAuditTrendPoint:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    summary = _mapping(value, f"summary in {path}")
    _validate_summary_schema(summary, path)
    identity = snapshot_id or Path(path).stem
    return FleetAuditTrendPoint.from_summary(summary, snapshot_id=identity, summary_path=str(path))


def trend_fleet_audits(points: Iterable[FleetAuditTrendPoint]) -> DecisionFleetAuditTrend:
    ordered = list(points)
    if not ordered:
        return DecisionFleetAuditTrend(TREND_CATEGORY, SCHEMA_VERSION, "unverified", [], [], [], False, False)
    deltas = [_build_delta(before, after) for before, after in zip(ordered, ordered[1:])]
    all_flags = [f"{delta.from_snapshot}->{delta.to_snapshot}:{flag}" for delta in deltas for flag in delta.flags]
    increases = [flag for delta in deltas for flag in delta.flags if flag.endswith("increased") or flag.endswith("degraded")]
    decreases = [flag for delta in deltas for flag in delta.flags if flag.endswith("decreased") or flag.endswith("improved")]
    status = "mixed" if increases and decreases else "degraded" if increases else "improving" if decreases else "stable"
    return DecisionFleetAuditTrend(TREND_CATEGORY, SCHEMA_VERSION, status, ordered, deltas, all_flags, False, False)


def trend_fleet_audit_files(paths: Sequence[str], *, snapshot_ids: Optional[Sequence[str]] = None) -> DecisionFleetAuditTrend:
    if not paths:
        raise ValueError("at least one summary path is required")
    if snapshot_ids and len(snapshot_ids) != len(paths):
        raise ValueError("--snapshot-id must be supplied once per --summary")
    points = [load_fleet_audit_summary(path, snapshot_id=(snapshot_ids[index] if snapshot_ids else None)) for index, path in enumerate(paths)]
    return trend_fleet_audits(points)


def write_fleet_audit_trend_jsonl(trend: DecisionFleetAuditTrend, path: str) -> None:
    records: list[dict[str, Any]] = []
    records.extend({"category": TREND_CATEGORY, "schema_version": SCHEMA_VERSION, "record_type": "point", **point.to_dict()} for point in trend.points)
    records.extend({"category": TREND_CATEGORY, "schema_version": SCHEMA_VERSION, "record_type": "delta", **delta.to_dict()} for delta in trend.deltas)
    records.append({"category": TREND_CATEGORY, "schema_version": SCHEMA_VERSION, "record_type": "summary", **trend.to_dict()})
    Path(path).write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records), encoding="utf-8")


__all__ = [
    "DecisionFleetAuditTrend",
    "FLEET_CATEGORY",
    "FleetAuditTrendDelta",
    "FleetAuditTrendPoint",
    "load_fleet_audit_summary",
    "trend_fleet_audit_files",
    "trend_fleet_audits",
    "write_fleet_audit_trend_jsonl",
]
