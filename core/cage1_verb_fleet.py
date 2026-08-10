"""Read-only fleet aggregation for ordered per-verb CAGE-1 comparisons."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence

SCHEMA_VERSION = "1.0"
FLEET_CATEGORY = "cage1_verb_comparison_fleet"


@dataclass(frozen=True)
class VerbComparisonSnapshot:
    snapshot_id: str
    path: str
    baseline_label: str
    current_label: str
    baseline_digest: str
    current_digest: str
    changed_profile_count: int
    profile_count: int
    profiles: tuple[Mapping[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "path": self.path,
            "baseline_label": self.baseline_label,
            "current_label": self.current_label,
            "baseline_digest": self.baseline_digest,
            "current_digest": self.current_digest,
            "changed_profile_count": self.changed_profile_count,
            "profile_count": self.profile_count,
            "profiles": [dict(profile) for profile in self.profiles],
        }


@dataclass(frozen=True)
class VerbComparisonFleetProfile:
    verb_name: str
    snapshot_count: int
    added_count: int
    removed_count: int
    changed_count: int
    coverage_changed_count: int
    unchanged_count: int
    observation_delta: Optional[int]
    latest_status: str
    latest_worst_state: str
    statuses: dict[str, int]

    @property
    def coverage_changed(self) -> bool:
        return self.coverage_changed_count > 0 or self.added_count > 0 or self.removed_count > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "verb_name": self.verb_name,
            "snapshot_count": self.snapshot_count,
            "added_count": self.added_count,
            "removed_count": self.removed_count,
            "changed_count": self.changed_count,
            "coverage_changed_count": self.coverage_changed_count,
            "unchanged_count": self.unchanged_count,
            "coverage_changed": self.coverage_changed,
            "observation_delta": self.observation_delta,
            "latest_status": self.latest_status,
            "latest_worst_state": self.latest_worst_state,
            "statuses": dict(self.statuses),
        }


@dataclass(frozen=True)
class VerbComparisonFleetSummary:
    category: str
    schema_version: str
    status: str
    snapshot_count: int
    snapshot_ids: tuple[str, ...]
    profiles: tuple[VerbComparisonFleetProfile, ...]
    total_changed_profile_count: int
    coverage_changed_verbs: tuple[str, ...]
    snapshot_digest_pairs: tuple[dict[str, str], ...]
    decision_applied: bool
    automatic_action_taken: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "schema_version": self.schema_version,
            "status": self.status,
            "snapshot_count": self.snapshot_count,
            "snapshot_ids": list(self.snapshot_ids),
            "profiles": [profile.to_dict() for profile in self.profiles],
            "total_changed_profile_count": self.total_changed_profile_count,
            "coverage_changed_verbs": list(self.coverage_changed_verbs),
            "snapshot_digest_pairs": [dict(item) for item in self.snapshot_digest_pairs],
            "decision_applied": self.decision_applied,
            "automatic_action_taken": self.automatic_action_taken,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        lines = [
            "# Per-verb CAGE-1 Fleet Comparison",
            "",
            f"- Status: **{self.status}**",
            f"- Snapshots: **{self.snapshot_count}**",
            f"- Changed profiles: **{self.total_changed_profile_count}**",
            f"- Decision applied: **{'yes' if self.decision_applied else 'no'}**",
            f"- Automatic action taken: **{'yes' if self.automatic_action_taken else 'no'}**",
            "",
            "| Verb | Snapshots | Added | Removed | Changed | Coverage changed | Obs Δ | Latest state |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
        for item in self.profiles:
            delta = "n/a" if item.observation_delta is None else f"{item.observation_delta:+d}"
            lines.append(f"| `{item.verb_name}` | {item.snapshot_count} | {item.added_count} | {item.removed_count} | {item.changed_count} | {'yes' if item.coverage_changed else 'no'} | {delta} | `{item.latest_worst_state or 'none'}` |")
        if self.snapshot_digest_pairs:
            lines.extend(["", "## Snapshot lineage", ""])
            for item in self.snapshot_digest_pairs:
                lines.append(f"- `{item['snapshot_id']}`: `{item['baseline_digest']}` → `{item['current_digest']}`")
        return "\n".join(lines) + "\n"


def _mapping(value: Any) -> Mapping[str, Any]:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if not isinstance(value, Mapping):
        raise TypeError(f"comparison must be a mapping or expose to_dict(), got {type(value).__name__}")
    return value


def _int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"comparison field {field!r} must be a non-negative integer")
    return value


def _snapshot(value: Any, snapshot_id: str, path: str) -> VerbComparisonSnapshot:
    data = _mapping(value)
    profiles = data.get("profiles")
    if not isinstance(profiles, list):
        raise ValueError("comparison JSON must contain a profiles list")
    normalized: list[Mapping[str, Any]] = []
    for profile in profiles:
        if not isinstance(profile, Mapping):
            raise ValueError("comparison profile entries must be objects")
        name = profile.get("verb_name")
        status = profile.get("status")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("comparison profiles require a non-empty verb_name")
        if not isinstance(status, str) or not status.strip():
            raise ValueError("comparison profiles require a non-empty status")
        normalized.append(dict(profile))
    return VerbComparisonSnapshot(
        snapshot_id=snapshot_id,
        path=path,
        baseline_label=str(data.get("baseline_label", "baseline")),
        current_label=str(data.get("current_label", "current")),
        baseline_digest=str(data.get("baseline_digest", "")),
        current_digest=str(data.get("current_digest", "")),
        changed_profile_count=_int(data.get("changed_profile_count", 0), "changed_profile_count"),
        profile_count=len(normalized),
        profiles=tuple(normalized),
    )


def load_comparison(path: str, *, snapshot_id: Optional[str] = None) -> VerbComparisonSnapshot:
    return _snapshot(json.loads(Path(path).read_text(encoding="utf-8")), snapshot_id or Path(path).stem, str(path))


def _optional_int(value: Any) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def aggregate_verb_comparisons(snapshots: Iterable[VerbComparisonSnapshot]) -> VerbComparisonFleetSummary:
    ordered = list(snapshots)
    if len({item.snapshot_id for item in ordered}) != len(ordered):
        raise ValueError("snapshot_id values must be unique")
    by_verb: dict[str, list[Mapping[str, Any]]] = {}
    for snapshot in ordered:
        for profile in snapshot.profiles:
            by_verb.setdefault(str(profile["verb_name"]), []).append(profile)
    results: list[VerbComparisonFleetProfile] = []
    for name in sorted(by_verb):
        entries = by_verb[name]
        statuses = Counter(str(entry["status"]) for entry in entries)
        observations = [_optional_int(entry.get("observation_delta")) for entry in entries]
        total_delta = sum(value for value in observations if value is not None) if all(value is not None for value in observations) else None
        latest = entries[-1]
        results.append(VerbComparisonFleetProfile(
            verb_name=name,
            snapshot_count=len(entries),
            added_count=statuses.get("added", 0),
            removed_count=statuses.get("removed", 0),
            changed_count=statuses.get("changed", 0),
            coverage_changed_count=statuses.get("coverage_changed", 0),
            unchanged_count=statuses.get("unchanged", 0),
            observation_delta=total_delta,
            latest_status=str(latest["status"]),
            latest_worst_state=str(latest.get("current_worst_state") or latest.get("baseline_worst_state") or ""),
            statuses=dict(sorted(statuses.items())),
        ))
    status = "unverified" if not ordered else "valid"
    return VerbComparisonFleetSummary(
        category=FLEET_CATEGORY,
        schema_version=SCHEMA_VERSION,
        status=status,
        snapshot_count=len(ordered),
        snapshot_ids=tuple(item.snapshot_id for item in ordered),
        profiles=tuple(results),
        total_changed_profile_count=sum(item.changed_count + item.added_count + item.removed_count + item.coverage_changed_count for item in results),
        coverage_changed_verbs=tuple(item.verb_name for item in results if item.coverage_changed),
        snapshot_digest_pairs=tuple({"snapshot_id": item.snapshot_id, "baseline_digest": item.baseline_digest, "current_digest": item.current_digest} for item in ordered),
        decision_applied=False,
        automatic_action_taken=False,
    )


def aggregate_verb_comparison_files(paths: Sequence[str], *, snapshot_ids: Optional[Sequence[str]] = None) -> VerbComparisonFleetSummary:
    if not paths:
        return aggregate_verb_comparisons([])
    if snapshot_ids is not None and len(snapshot_ids) != len(paths):
        raise ValueError("--snapshot-id must be supplied once per --comparison")
    ids = snapshot_ids or [Path(path).stem for path in paths]
    return aggregate_verb_comparisons([load_comparison(path, snapshot_id=identity) for path, identity in zip(paths, ids)])


__all__ = [
    "FLEET_CATEGORY",
    "SCHEMA_VERSION",
    "VerbComparisonFleetProfile",
    "VerbComparisonFleetSummary",
    "VerbComparisonSnapshot",
    "aggregate_verb_comparisons",
    "aggregate_verb_comparison_files",
    "load_comparison",
]
