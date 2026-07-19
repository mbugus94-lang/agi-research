"""Read-only fleet aggregation for ordered CAGE-1 session snapshots."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence


@dataclass(frozen=True)
class FleetSession:
    position: int
    label: str
    digest: str
    n_reports: int
    substrate_coverage: float
    outcome_distribution: Dict[str, int]
    memory_integrity: Dict[str, Any]
    retrieval_quality: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FleetDigestLink:
    position: int
    label: str
    digest: str
    matches_previous: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DimensionFleetSummary:
    dimension: str
    measured_sessions: int
    total_sessions: int
    mean_score: float | None
    first_score: float | None
    last_score: float | None
    delta: float | None
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceFleetMetric:
    section: str
    metric: str
    measured_sessions: int
    total_sessions: int
    mean: float | None
    minimum: float | None
    maximum: float | None
    first: float | None
    last: float | None
    delta: float | None
    status: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CAGE1Fleet:
    sessions: List[FleetSession]
    digest_links: List[FleetDigestLink]
    dimension_summaries: List[DimensionFleetSummary]
    evidence_metrics: List[EvidenceFleetMetric]
    outcome_totals: Dict[str, int]
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sessions": [item.to_dict() for item in self.sessions],
            "digest_links": [item.to_dict() for item in self.digest_links],
            "dimension_summaries": [item.to_dict() for item in self.dimension_summaries],
            "evidence_metrics": [item.to_dict() for item in self.evidence_metrics],
            "outcome_totals": self.outcome_totals,
            "notes": self.notes,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        lines = [
            "# CAGE-1 Fleet Aggregation",
            "",
            f"- Sessions: **{len(self.sessions)}**",
            f"- Digest mismatches: **{sum(not item.matches_previous for item in self.digest_links)}**",
            "",
            "## Outcome totals",
            "",
            "| State | Total |",
            "|---|---:|",
        ]
        for state, count in self.outcome_totals.items():
            lines.append(f"| `{state}` | {count} |")
        lines.extend([
            "",
            "## Session evidence",
            "",
            "| # | Label | Reports | Coverage | Memory | Retrieval | Digest |",
            "|---:|---|---:|---:|---:|---:|---|",
        ])
        for session in self.sessions:
            memory = _fmt(session.memory_integrity.get("score"))
            retrieval = _fmt(session.retrieval_quality.get("score"))
            lines.append(
                f"| {session.position} | `{session.label}` | {session.n_reports} | "
                f"{session.substrate_coverage:.3f} | {memory} | {retrieval} | `{session.digest[:12]}` |"
            )
        lines.extend([
            "",
            "## Dimension summaries",
            "",
            "| Dimension | Measured | Mean | First | Last | Delta | Status |",
            "|---|---:|---:|---:|---:|---:|---|",
        ])
        for item in self.dimension_summaries:
            lines.append(
                f"| `{item.dimension}` | {item.measured_sessions}/{item.total_sessions} | {_fmt(item.mean_score)} | "
                f"{_fmt(item.first_score)} | {_fmt(item.last_score)} | {_fmt_delta(item.delta)} | {item.status} |"
            )
        if self.evidence_metrics:
            lines.extend([
                "",
                "## Evidence metric summaries",
                "",
                "| Section | Metric | Measured | Mean | First | Last | Delta | Status |",
                "|---|---|---:|---:|---:|---:|---:|---|",
            ])
            for item in self.evidence_metrics:
                lines.append(
                    f"| `{item.section}` | `{item.metric}` | {item.measured_sessions}/{item.total_sessions} | "
                    f"{_fmt(item.mean)} | {_fmt(item.first)} | {_fmt(item.last)} | {_fmt_delta(item.delta)} | {item.status} |"
                )
        lines.extend(["", "## Digest lineage", "", "| # | Label | Digest | Match |", "|---:|---|---|---|"])
        for item in self.digest_links:
            lines.append(f"| {item.position} | `{item.label}` | `{item.digest[:12]}` | {'yes' if item.matches_previous else 'no'} |")
        if self.notes:
            lines.extend(["", "## Notes", "", self.notes])
        return "\n".join(lines) + "\n"


def _fmt(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):.3f}"


def _fmt_delta(value: Any) -> str:
    return "n/a" if value is None else f"{float(value):+.3f}"


def _mapping(value: Any) -> Mapping[str, Any]:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if not isinstance(value, Mapping):
        raise TypeError(f"snapshot must be a mapping or expose to_dict(), got {type(value).__name__}")
    return value


def _number(value: Any, default: float = 0.0) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else default


def _session(snapshot: Any, position: int) -> FleetSession:
    data = _mapping(snapshot)
    outcomes = data.get("outcome_distribution", {})
    outcomes = outcomes if isinstance(outcomes, Mapping) else {}
    return FleetSession(
        position=position,
        label=str(data.get("label", f"session-{position}")),
        digest=str(data.get("report_digest", "")),
        n_reports=int(data.get("n_reports", 0) or 0),
        substrate_coverage=_number(data.get("substrate_coverage")),
        outcome_distribution={str(k): int(v or 0) for k, v in outcomes.items() if isinstance(v, (int, float)) and not isinstance(v, bool)},
        memory_integrity=dict(data.get("memory_integrity", {})) if isinstance(data.get("memory_integrity"), Mapping) else {},
        retrieval_quality=dict(data.get("retrieval_quality", {})) if isinstance(data.get("retrieval_quality"), Mapping) else {},
    )


def _status(first: float | None, last: float | None, higher_is_better: bool = True) -> str:
    if first is None or last is None:
        return "not_measured"
    if last == first:
        return "unchanged"
    improved = last > first if higher_is_better else last < first
    return "improved" if improved else "regressed"


def _dimension_summaries(snapshots: Sequence[Mapping[str, Any]]) -> List[DimensionFleetSummary]:
    names = sorted({str(item.get("dimension")) for data in snapshots for item in (data.get("dimensions", []) if isinstance(data.get("dimensions", []), list) else []) if isinstance(item, Mapping) and item.get("dimension") is not None})
    summaries: List[DimensionFleetSummary] = []
    for name in names:
        values: List[float | None] = []
        for data in snapshots:
            dimensions = data.get("dimensions", [])
            row = next((item for item in dimensions if isinstance(item, Mapping) and str(item.get("dimension")) == name), None) if isinstance(dimensions, list) else None
            value = row.get("score") if isinstance(row, Mapping) else None
            values.append(float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None)
        measured = [value for value in values if value is not None]
        first = next((value for value in values if value is not None), None)
        last = next((value for value in reversed(values) if value is not None), None)
        summaries.append(DimensionFleetSummary(name, len(measured), len(values), sum(measured) / len(measured) if measured else None, first, last, last - first if first is not None and last is not None else None, _status(first, last)))
    return summaries


_EVIDENCE_METRICS = {
    "memory_integrity": ("score", "record_count", "intervention_count", "invalid_record_count", "invalid_intervention_count"),
    "retrieval_quality": ("score", "recovery_score", "task_completion_rate", "fidelity_gap", "topk_recovery_score", "topk_degradation", "num_scenarios", "num_dimensions"),
}


def _evidence_metrics(snapshots: Sequence[Mapping[str, Any]]) -> List[EvidenceFleetMetric]:
    metrics: List[EvidenceFleetMetric] = []
    for section, names in _EVIDENCE_METRICS.items():
        for name in names:
            values: List[float | None] = []
            for data in snapshots:
                section_data = data.get(section, {})
                value = section_data.get(name) if isinstance(section_data, Mapping) and section_data.get("measured", False) else None
                values.append(float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None)
            measured = [value for value in values if value is not None]
            if not measured:
                continue
            first = next((value for value in values if value is not None), None)
            last = next((value for value in reversed(values) if value is not None), None)
            higher = name not in {"invalid_record_count", "invalid_intervention_count", "topk_degradation", "fidelity_gap"}
            metrics.append(EvidenceFleetMetric(section, name, len(measured), len(values), sum(measured) / len(measured), min(measured), max(measured), first, last, last - first if first is not None and last is not None else None, _status(first, last, higher)))
    return metrics


def aggregate_fleet(snapshots: Sequence[Any], *, notes: str = "") -> CAGE1Fleet:
    """Aggregate ordered snapshots without mutating inputs or applying policy."""
    data = [_mapping(snapshot) for snapshot in snapshots]
    sessions = [_session(snapshot, index) for index, snapshot in enumerate(data)]
    links = [FleetDigestLink(index, sessions[index].label, sessions[index].digest, sessions[index].digest == sessions[index - 1].digest) for index in range(1, len(sessions))]
    totals: Dict[str, int] = {}
    for session in sessions:
        for state, count in session.outcome_distribution.items():
            if state == "total":
                continue
            totals[state] = totals.get(state, 0) + count
    return CAGE1Fleet(sessions, links, _dimension_summaries(data), _evidence_metrics(data), dict(sorted(totals.items())), notes)


def load_fleet_snapshots(path: str) -> List[Dict[str, Any]]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("fleet JSON must contain an array")
    return [dict(_mapping(item)) for item in value]


__all__ = [
    "CAGE1Fleet",
    "DimensionFleetSummary",
    "EvidenceFleetMetric",
    "FleetDigestLink",
    "FleetSession",
    "aggregate_fleet",
    "load_fleet_snapshots",
]
