"""Read-only comparison of two CAGE-1 evaluation snapshots."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence


_OUTCOME_KEYS = (
    "admitted",
    "held_for_evidence",
    "narrowed_for_ring",
    "narrowed_for_chain",
    "quarantined_for_cef",
    "escalated",
    "refused",
    "made_non_effective",
)


@dataclass(frozen=True)
class OutcomeDelta:
    state: str
    baseline: int
    current: int
    delta: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DimensionDelta:
    dimension: str
    baseline_coverage: str
    current_coverage: str
    baseline_score: Optional[float]
    current_score: Optional[float]
    score_delta: Optional[float]
    status: str
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CAGE1Comparison:
    baseline_label: str
    current_label: str
    baseline_digest: str
    current_digest: str
    digest_match: bool
    outcome_deltas: List[OutcomeDelta]
    dimension_deltas: List[DimensionDelta]
    changed_outcome_count: int
    changed_dimension_count: int
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "baseline_label": self.baseline_label,
            "current_label": self.current_label,
            "baseline_digest": self.baseline_digest,
            "current_digest": self.current_digest,
            "digest_match": self.digest_match,
            "outcome_deltas": [item.to_dict() for item in self.outcome_deltas],
            "dimension_deltas": [item.to_dict() for item in self.dimension_deltas],
            "changed_outcome_count": self.changed_outcome_count,
            "changed_dimension_count": self.changed_dimension_count,
            "notes": self.notes,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        lines = [
            f"# CAGE-1 Comparison — {self.baseline_label} → {self.current_label}",
            "",
            f"- Digest match: **{'yes' if self.digest_match else 'no'}**",
            f"- Changed outcomes: **{self.changed_outcome_count}**",
            f"- Changed dimensions: **{self.changed_dimension_count}**",
            "",
            "## Outcome deltas",
            "",
            "| State | Baseline | Current | Delta |",
            "|---|---:|---:|---:|",
        ]
        for item in self.outcome_deltas:
            lines.append(f"| `{item.state}` | {item.baseline} | {item.current} | {item.delta:+d} |")
        lines.extend([
            "",
            "## Dimension deltas",
            "",
            "| Dimension | Baseline | Current | Delta | Status |",
            "|---|---|---|---:|---|",
        ])
        for item in self.dimension_deltas:
            base = item.baseline_score if item.baseline_score is not None else "n/a"
            current = item.current_score if item.current_score is not None else "n/a"
            delta = f"{item.score_delta:+.3f}" if item.score_delta is not None else "n/a"
            lines.append(f"| `{item.dimension}` | {base} | {current} | {delta} | {item.status} |")
        if self.notes:
            lines.extend(["", "## Notes", "", self.notes])
        return "\n".join(lines) + "\n"


def _snapshot(value: Any) -> Mapping[str, Any]:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if not isinstance(value, Mapping):
        raise TypeError(f"evaluation must be a mapping or expose to_dict(), got {type(value).__name__}")
    return value


def _score(value: Any) -> Optional[float]:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _dimension_map(snapshot: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    dimensions = snapshot.get("dimensions", [])
    if not isinstance(dimensions, Sequence) or isinstance(dimensions, (str, bytes)):
        return {}
    result: Dict[str, Mapping[str, Any]] = {}
    for item in dimensions:
        if isinstance(item, Mapping) and item.get("dimension") is not None:
            result[str(item["dimension"])] = item
    return result


def _dimension_status(
    baseline_coverage: str,
    current_coverage: str,
    baseline_score: Optional[float],
    current_score: Optional[float],
    baseline_present: bool,
    current_present: bool,
) -> tuple[str, str]:
    if baseline_coverage != current_coverage or baseline_present != current_present:
        return "coverage_changed", f"coverage changed from {baseline_coverage} to {current_coverage}"
    if not baseline_present or not current_present:
        return "not_measured", "dimension absent from one or both snapshots"
    if baseline_score is None or current_score is None:
        return "not_measured", "score unavailable in one or both snapshots"
    delta = current_score - baseline_score
    if delta > 0:
        return "improved", ""
    if delta < 0:
        return "regressed", ""
    return "unchanged", ""


def compare_evaluations(baseline: Any, current: Any, *, notes: str = "") -> CAGE1Comparison:
    """Compare two snapshots without mutating either input or applying policy."""
    before = _snapshot(baseline)
    after = _snapshot(current)
    before_outcomes = before.get("outcome_distribution", {})
    after_outcomes = after.get("outcome_distribution", {})
    if not isinstance(before_outcomes, Mapping):
        before_outcomes = {}
    if not isinstance(after_outcomes, Mapping):
        after_outcomes = {}
    outcome_deltas = [
        OutcomeDelta(
            state=state,
            baseline=int(before_outcomes.get(state, 0) or 0),
            current=int(after_outcomes.get(state, 0) or 0),
            delta=int(after_outcomes.get(state, 0) or 0) - int(before_outcomes.get(state, 0) or 0),
        )
        for state in _OUTCOME_KEYS
    ]
    before_dims = _dimension_map(before)
    after_dims = _dimension_map(after)
    dimension_names = sorted(set(before_dims) | set(after_dims))
    dimension_deltas: List[DimensionDelta] = []
    for name in dimension_names:
        old = before_dims.get(name, {})
        new = after_dims.get(name, {})
        old_coverage = str(old.get("coverage", "not_measured"))
        new_coverage = str(new.get("coverage", "not_measured"))
        old_score = _score(old.get("score"))
        new_score = _score(new.get("score"))
        delta = new_score - old_score if old_score is not None and new_score is not None else None
        status, status_note = _dimension_status(
            old_coverage,
            new_coverage,
            old_score,
            new_score,
            name in before_dims,
            name in after_dims,
        )
        dimension_deltas.append(DimensionDelta(
            dimension=name,
            baseline_coverage=old_coverage,
            current_coverage=new_coverage,
            baseline_score=old_score,
            current_score=new_score,
            score_delta=delta,
            status=status,
            notes=status_note,
        ))
    changed_outcomes = sum(item.delta != 0 for item in outcome_deltas)
    changed_dimensions = sum(item.status not in {"unchanged", "not_measured"} for item in dimension_deltas)
    return CAGE1Comparison(
        baseline_label=str(before.get("label", "baseline")),
        current_label=str(after.get("label", "current")),
        baseline_digest=str(before.get("report_digest", "")),
        current_digest=str(after.get("report_digest", "")),
        digest_match=bool(before.get("report_digest")) and before.get("report_digest") == after.get("report_digest"),
        outcome_deltas=outcome_deltas,
        dimension_deltas=dimension_deltas,
        changed_outcome_count=changed_outcomes,
        changed_dimension_count=changed_dimensions,
        notes=notes,
    )


def load_evaluation(path: str) -> Dict[str, Any]:
    """Load one JSON evaluation snapshot from disk."""
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("evaluation JSON must contain an object")
    return value


__all__ = [
    "CAGE1Comparison",
    "DimensionDelta",
    "OutcomeDelta",
    "compare_evaluations",
    "load_evaluation",
]
