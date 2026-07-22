"""Read-only trend analysis for ordered CAGE-1 evaluation snapshots."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence


@dataclass(frozen=True)
class TrendPoint:
    position: int
    label: str
    digest: str
    n_reports: int
    admitted: int
    refused: int
    escalated: int
    made_non_effective: int
    substrate_coverage: float
    memory_integrity_score: float | None
    retrieval_quality_score: float | None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DigestLink:
    position: int
    from_digest: str
    to_digest: str
    matches_previous: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RegressionFlag:
    position: int
    from_label: str
    to_label: str
    metric: str
    baseline: float
    current: float
    delta: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CAGE1FleetTrend:
    trend: "CAGE1Trend"
    fleet: Any

    def to_dict(self) -> Dict[str, Any]:
        return {"trend": self.trend.to_dict(), "fleet": self.fleet.to_dict()}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        return self.trend.to_markdown() + "\n" + self.fleet.to_markdown()


@dataclass(frozen=True)
class CAGE1Trend:
    points: List[TrendPoint]
    digest_links: List[DigestLink]
    regressions: List[RegressionFlag]
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "points": [point.to_dict() for point in self.points],
            "digest_links": [link.to_dict() for link in self.digest_links],
            "regressions": [flag.to_dict() for flag in self.regressions],
            "notes": self.notes,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        lines = [
            "# CAGE-1 Trend",
            "",
            f"- Snapshots: **{len(self.points)}**",
            f"- Digest mismatches: **{sum(not link.matches_previous for link in self.digest_links)}**",
            f"- Regression flags: **{len(self.regressions)}**",
            "",
            "## Snapshot trajectory",
            "",
            "| # | Label | Reports | Admitted | Refused | Coverage | Memory | Retrieval | Digest |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---|",
        ]
        for point in self.points:
            memory = f"{point.memory_integrity_score:.3f}" if point.memory_integrity_score is not None else "n/a"
            retrieval = f"{point.retrieval_quality_score:.3f}" if point.retrieval_quality_score is not None else "n/a"
            lines.append(
                f"| {point.position} | `{point.label}` | {point.n_reports} | {point.admitted} | "
                f"{point.refused} | {point.substrate_coverage:.3f} | {memory} | {retrieval} | `{point.digest[:12]}` |"
            )
        lines.extend(["", "## Digest lineage", "", "| # | From | To | Match |", "|---:|---|---|---|"])
        for link in self.digest_links:
            lines.append(f"| {link.position} | `{link.from_digest[:12]}` | `{link.to_digest[:12]}` | {'yes' if link.matches_previous else 'no'} |")
        lines.extend(["", "## Regression flags", "", "| # | Transition | Metric | Baseline | Current | Delta |", "|---:|---|---|---:|---:|---:|"])
        for flag in self.regressions:
            lines.append(
                f"| {flag.position} | `{flag.from_label}` → `{flag.to_label}` | `{flag.metric}` | "
                f"{flag.baseline:.3f} | {flag.current:.3f} | {flag.delta:+.3f} |"
            )
        if self.notes:
            lines.extend(["", "## Notes", "", self.notes])
        return "\n".join(lines) + "\n"


def _mapping(value: Any) -> Mapping[str, Any]:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if not isinstance(value, Mapping):
        raise TypeError(f"snapshot must be a mapping or expose to_dict(), got {type(value).__name__}")
    return value


def _count(snapshot: Mapping[str, Any], key: str) -> int:
    outcomes = snapshot.get("outcome_distribution", {})
    if not isinstance(outcomes, Mapping):
        return 0
    try:
        return int(outcomes.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _optional_score(snapshot: Mapping[str, Any], section: str) -> float | None:
    value = snapshot.get(section, {})
    if not isinstance(value, Mapping):
        return None
    score = value.get("score")
    return float(score) if isinstance(score, (int, float)) and not isinstance(score, bool) else None


def _point(snapshot: Any, position: int) -> TrendPoint:
    data = _mapping(snapshot)
    coverage = data.get("substrate_coverage", 0.0)
    try:
        coverage = float(coverage)
    except (TypeError, ValueError):
        coverage = 0.0
    reports = data.get("n_reports", 0)
    try:
        reports = int(reports)
    except (TypeError, ValueError):
        reports = 0
    return TrendPoint(
        position=position,
        label=str(data.get("label", f"snapshot-{position}")),
        digest=str(data.get("report_digest", "")),
        n_reports=reports,
        admitted=_count(data, "admitted"),
        refused=_count(data, "refused"),
        escalated=_count(data, "escalated"),
        made_non_effective=_count(data, "made_non_effective"),
        substrate_coverage=coverage,
        memory_integrity_score=_optional_score(data, "memory_integrity"),
        retrieval_quality_score=_optional_score(data, "retrieval_quality"),
    )


def _numeric_metrics(point: TrendPoint) -> Dict[str, float]:
    values: Dict[str, float] = {
        "admitted": float(point.admitted),
        "refused": float(point.refused),
        "escalated": float(point.escalated),
        "made_non_effective": float(point.made_non_effective),
        "substrate_coverage": point.substrate_coverage,
    }
    if point.memory_integrity_score is not None:
        values["memory_integrity_score"] = point.memory_integrity_score
    if point.retrieval_quality_score is not None:
        values["retrieval_quality_score"] = point.retrieval_quality_score
    return values


def trend_evaluations(snapshots: Sequence[Any], *, notes: str = "") -> CAGE1Trend:
    """Build an ordered, read-only trajectory and flag regressions.

    Counts are compared as recorded, while score regressions are only
    flagged when both adjacent snapshots explicitly measured the score.
    """
    points = [_point(snapshot, index) for index, snapshot in enumerate(snapshots)]
    links: List[DigestLink] = []
    regressions: List[RegressionFlag] = []
    for position in range(1, len(points)):
        previous = points[position - 1]
        current = points[position]
        links.append(DigestLink(position, previous.digest, current.digest, previous.digest == current.digest))
        old_metrics = _numeric_metrics(previous)
        new_metrics = _numeric_metrics(current)
        for metric in sorted(set(old_metrics) & set(new_metrics)):
            baseline = old_metrics[metric]
            value = new_metrics[metric]
            delta = value - baseline
            is_regression = (metric in {"admitted", "substrate_coverage", "memory_integrity_score", "retrieval_quality_score"} and delta < 0) or (
                metric in {"refused", "escalated", "made_non_effective"} and delta > 0
            )
            if is_regression:
                regressions.append(RegressionFlag(
                    position=position,
                    from_label=previous.label,
                    to_label=current.label,
                    metric=metric,
                    baseline=baseline,
                    current=value,
                    delta=delta,
                    reason="lower is worse" if metric in {"admitted", "substrate_coverage", "memory_integrity_score", "retrieval_quality_score"} else "higher is worse",
                ))
    return CAGE1Trend(points=points, digest_links=links, regressions=regressions, notes=notes)


def trend_fleet_snapshots(snapshots: Sequence[Any], *, notes: str = "") -> CAGE1FleetTrend:
    """Build a trend plus a provenance-preserving fleet envelope.

    The trend is a compact trajectory; the fleet retains ordered sessions,
    digest lineage, anomalies, and explicit unmeasured evidence. Neither
    layer mutates the supplied snapshots or applies policy.
    """
    from .cage1_fleet import aggregate_fleet

    return CAGE1FleetTrend(
        trend=trend_evaluations(snapshots, notes=notes),
        fleet=aggregate_fleet(snapshots, notes=notes),
    )


def load_evaluations(path: str) -> List[Dict[str, Any]]:
    """Load an ordered JSON array of CAGE-1 snapshots."""
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError("trend JSON must contain an array")
    return [dict(_mapping(item)) for item in value]


__all__ = [
    "CAGE1FleetTrend",
    "CAGE1Trend",
    "DigestLink",
    "RegressionFlag",
    "TrendPoint",
    "load_evaluations",
    "trend_evaluations",
    "trend_fleet_snapshots",
]
