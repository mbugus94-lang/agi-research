"""Read-only comparison of per-verb CAGE-1 outcome profiles."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


_METRICS = ("admitted_rate", "non_admitted_rate", "refusal_rate", "escalation_rate")
_WORST_RANK = {
    "": 0,
    "admitted": 1,
    "held_for_evidence": 2,
    "narrowed_for_ring": 3,
    "narrowed_for_chain": 3,
    "quarantined_for_cef": 4,
    "escalated": 5,
    "refused": 6,
}


@dataclass(frozen=True)
class VerbOutcomeDelta:
    verb_name: str
    status: str
    baseline_observations: Optional[int]
    current_observations: Optional[int]
    observation_delta: Optional[int]
    baseline_admitted_rate: Optional[float]
    current_admitted_rate: Optional[float]
    admitted_rate_delta: Optional[float]
    baseline_non_admitted_rate: Optional[float]
    current_non_admitted_rate: Optional[float]
    non_admitted_rate_delta: Optional[float]
    baseline_refusal_rate: Optional[float]
    current_refusal_rate: Optional[float]
    refusal_rate_delta: Optional[float]
    baseline_escalation_rate: Optional[float]
    current_escalation_rate: Optional[float]
    escalation_rate_delta: Optional[float]
    baseline_worst_state: str
    current_worst_state: str
    worst_state_changed: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VerbProfileComparison:
    baseline_label: str
    current_label: str
    baseline_digest: str
    current_digest: str
    digest_match: bool
    profiles: List[VerbOutcomeDelta]
    changed_profile_count: int
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "baseline_label": self.baseline_label,
            "current_label": self.current_label,
            "baseline_digest": self.baseline_digest,
            "current_digest": self.current_digest,
            "digest_match": self.digest_match,
            "profiles": [item.to_dict() for item in self.profiles],
            "changed_profile_count": self.changed_profile_count,
            "notes": self.notes,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        lines = [
            f"# Per-verb CAGE-1 Comparison — {self.baseline_label} → {self.current_label}",
            "",
            f"- Digest match: **{'yes' if self.digest_match else 'no'}**",
            f"- Changed profiles: **{self.changed_profile_count}**",
            "",
            "| Verb | Status | N Δ | Admitted Δ | Non-admitted Δ | Refusal Δ | Escalation Δ | Worst state |",
            "|---|---|---:|---:|---:|---:|---:|---|",
        ]
        for item in self.profiles:
            def fmt(value: Optional[float]) -> str:
                return "n/a" if value is None else f"{value:+.1%}"
            observation_delta = "n/a" if item.observation_delta is None else f"{item.observation_delta:+d}"
            worst = item.current_worst_state or item.baseline_worst_state or "none"
            lines.append(
                f"| `{item.verb_name}` | {item.status} | {observation_delta} | {fmt(item.admitted_rate_delta)} | "
                f"{fmt(item.non_admitted_rate_delta)} | {fmt(item.refusal_rate_delta)} | "
                f"{fmt(item.escalation_rate_delta)} | `{worst}` |"
            )
        if self.notes:
            lines.extend(["", "## Notes", "", self.notes])
        return "\n".join(lines) + "\n"


def _mapping(value: Any) -> Mapping[str, Any]:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if not isinstance(value, Mapping):
        raise TypeError(f"profile must be a mapping or expose to_dict(), got {type(value).__name__}")
    return value


def _profile_map(value: Any) -> Dict[str, Mapping[str, Any]]:
    data = _mapping(value)
    profiles = data.get("profiles")
    if not isinstance(profiles, list):
        raise ValueError("profile JSON must contain a profiles list")
    result: Dict[str, Mapping[str, Any]] = {}
    for item in profiles:
        if not isinstance(item, Mapping):
            raise ValueError("profile entries must be objects")
        name = item.get("verb_name")
        if not isinstance(name, str) or not name:
            raise ValueError("profile entries require a non-empty verb_name")
        if name in result:
            raise ValueError(f"duplicate verb profile: {name}")
        result[name] = item
    return result


def _optional_int(value: Any) -> Optional[int]:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _optional_float(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _delta(old: Optional[float], new: Optional[float]) -> Optional[float]:
    return new - old if old is not None and new is not None else None


def _state(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _one(name: str, old: Optional[Mapping[str, Any]], new: Optional[Mapping[str, Any]]) -> VerbOutcomeDelta:
    if old is None:
        status = "added"
    elif new is None:
        status = "removed"
    else:
        status = "unchanged"
    old_n = _optional_int(old.get("n_observations")) if old else None
    new_n = _optional_int(new.get("n_observations")) if new else None
    old_state = _state(old.get("worst_state")) if old else ""
    new_state = _state(new.get("worst_state")) if new else ""
    values: Dict[str, Optional[float]] = {}
    for metric in _METRICS:
        values[f"old_{metric}"] = _optional_float(old.get(metric)) if old else None
        values[f"new_{metric}"] = _optional_float(new.get(metric)) if new else None
    if old is not None and new is not None:
        changed = old_n != new_n or old_state != new_state or any(_delta(values[f"old_{m}"], values[f"new_{m}"]) not in (None, 0.0) for m in _METRICS)
        if any(values[f"old_{m}"] is None or values[f"new_{m}"] is None for m in _METRICS):
            status = "coverage_changed"
        elif old_state != new_state or changed:
            status = "changed"
        else:
            status = "unchanged"
    return VerbOutcomeDelta(
        verb_name=name,
        status=status,
        baseline_observations=old_n,
        current_observations=new_n,
        observation_delta=new_n - old_n if old_n is not None and new_n is not None else None,
        baseline_admitted_rate=values["old_admitted_rate"], current_admitted_rate=values["new_admitted_rate"], admitted_rate_delta=_delta(values["old_admitted_rate"], values["new_admitted_rate"]),
        baseline_non_admitted_rate=values["old_non_admitted_rate"], current_non_admitted_rate=values["new_non_admitted_rate"], non_admitted_rate_delta=_delta(values["old_non_admitted_rate"], values["new_non_admitted_rate"]),
        baseline_refusal_rate=values["old_refusal_rate"], current_refusal_rate=values["new_refusal_rate"], refusal_rate_delta=_delta(values["old_refusal_rate"], values["new_refusal_rate"]),
        baseline_escalation_rate=values["old_escalation_rate"], current_escalation_rate=values["new_escalation_rate"], escalation_rate_delta=_delta(values["old_escalation_rate"], values["new_escalation_rate"]),
        baseline_worst_state=old_state,
        current_worst_state=new_state,
        worst_state_changed=old_state != new_state,
    )


def compare_verb_profiles(baseline: Any, current: Any, *, notes: str = "") -> VerbProfileComparison:
    before = _mapping(baseline)
    after = _mapping(current)
    old_profiles = _profile_map(before)
    new_profiles = _profile_map(after)
    profiles = [_one(name, old_profiles.get(name), new_profiles.get(name)) for name in sorted(set(old_profiles) | set(new_profiles))]
    changed = sum(item.status != "unchanged" for item in profiles)
    return VerbProfileComparison(
        baseline_label=str(before.get("label", "baseline")),
        current_label=str(after.get("label", "current")),
        baseline_digest=str(before.get("report_digest", "")),
        current_digest=str(after.get("report_digest", "")),
        digest_match=bool(before.get("report_digest")) and before.get("report_digest") == after.get("report_digest"),
        profiles=profiles,
        changed_profile_count=changed,
        notes=notes,
    )


def load_profile(path: str) -> Dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("profile JSON must contain an object")
    return value


__all__ = ["VerbOutcomeDelta", "VerbProfileComparison", "compare_verb_profiles", "load_profile"]
