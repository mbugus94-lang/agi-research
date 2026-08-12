"""Read-only join of per-verb fleet profiles and decision evidence."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

JOIN_CATEGORY = "cage1_verb_evidence_join"
SCHEMA_VERSION = "1.0"
UNATTRIBUTED = "__unattributed__"


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if not isinstance(value, Mapping):
        raise TypeError(f"{label} must be a mapping or expose to_dict()")
    return value


def load_json(path: str) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _identity(row: Mapping[str, Any]) -> str:
    for key in ("verb_name", "action_type", "tool"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    detail = row.get("detail")
    if isinstance(detail, Mapping):
        for key in ("verb_name", "action_type", "tool"):
            value = detail.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return UNATTRIBUTED


def _evidence_rows(value: Optional[Any]) -> tuple[list[dict[str, Any]], str]:
    if value is None:
        return [], "missing"
    source = _mapping(value, "evidence")
    if isinstance(source.get("fleet"), Mapping):
        source = _mapping(source["fleet"], "evidence.fleet")
    rows = source.get("lines")
    if rows is None and isinstance(source.get("line_provenance"), list):
        rows = source["line_provenance"]
    if rows is None and isinstance(source.get("points"), list):
        flattened: list[Any] = []
        for point in source["points"]:
            if isinstance(point, Mapping) and isinstance(point.get("line_provenance"), list):
                flattened.extend(point["line_provenance"])
        rows = flattened
    if not isinstance(rows, list):
        raise ValueError("evidence must contain a lines or line_provenance array")
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("evidence rows must be JSON objects")
        normalized.append(dict(row))
    return normalized, "present"


def _fleet_profiles(value: Any) -> tuple[Mapping[str, Any], tuple[str, ...], str]:
    source = _mapping(value, "fleet")
    raw_profiles = source.get("profiles")
    if not isinstance(raw_profiles, list):
        raise ValueError("fleet must contain a profiles array")
    profiles: list[Mapping[str, Any]] = []
    names: set[str] = set()
    for profile in raw_profiles:
        if not isinstance(profile, Mapping):
            raise ValueError("fleet profile entries must be JSON objects")
        name = profile.get("verb_name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("fleet profiles require a non-empty verb_name")
        if name in names:
            raise ValueError(f"duplicate fleet verb profile: {name}")
        names.add(name)
        profiles.append(profile)
    return tuple(profiles), tuple(str(item) for item in source.get("snapshot_ids", []) if isinstance(item, str)), str(source.get("status", "unverified"))


@dataclass(frozen=True)
class EvidenceRow:
    source_id: str
    source_line_number: Optional[int]
    status: str
    verb_name: str
    decision: Optional[str]
    operator_id: Optional[str]
    advisory_digest: Optional[str]
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_line_number": self.source_line_number,
            "status": self.status,
            "verb_name": self.verb_name,
            "decision": self.decision,
            "operator_id": self.operator_id,
            "advisory_digest": self.advisory_digest,
            "raw": dict(self.raw),
        }


@dataclass(frozen=True)
class VerbEvidenceJoin:
    verb_name: str
    fleet_status: str
    latest_worst_state: str
    coverage_changed: bool
    observation_delta: Optional[int]
    join_status: str
    evidence_status_counts: dict[str, int]
    valid_evidence_count: int
    decision_counts: dict[str, int]
    decision_review_status: str
    operator_ids: tuple[str, ...]
    evidence_rows: tuple[EvidenceRow, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "verb_name": self.verb_name,
            "fleet_status": self.fleet_status,
            "latest_worst_state": self.latest_worst_state,
            "coverage_changed": self.coverage_changed,
            "observation_delta": self.observation_delta,
            "join_status": self.join_status,
            "evidence_status_counts": dict(self.evidence_status_counts),
            "valid_evidence_count": self.valid_evidence_count,
            "decision_counts": dict(self.decision_counts),
            "decision_review_status": self.decision_review_status,
            "operator_ids": list(self.operator_ids),
            "evidence_rows": [row.to_dict() for row in self.evidence_rows],
        }


@dataclass(frozen=True)
class VerbEvidenceJoinSummary:
    category: str
    schema_version: str
    status: str
    fleet_status: str
    evidence_status: str
    snapshot_ids: tuple[str, ...]
    profiles: tuple[VerbEvidenceJoin, ...]
    evidence_rows: tuple[EvidenceRow, ...]
    evidence_status_counts: dict[str, int]
    decision_counts: dict[str, int]
    ambiguous_decision_count: int
    source_ids: tuple[str, ...]
    unmatched_identity_count: int
    unattributed_evidence_count: int
    decision_applied: bool
    automatic_action_taken: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "schema_version": self.schema_version,
            "status": self.status,
            "fleet_status": self.fleet_status,
            "evidence_status": self.evidence_status,
            "snapshot_ids": list(self.snapshot_ids),
            "profiles": [profile.to_dict() for profile in self.profiles],
            "evidence_rows": [row.to_dict() for row in self.evidence_rows],
            "evidence_status_counts": dict(self.evidence_status_counts),
            "decision_counts": dict(self.decision_counts),
            "ambiguous_decision_count": self.ambiguous_decision_count,
            "source_ids": list(self.source_ids),
            "unmatched_identity_count": self.unmatched_identity_count,
            "unattributed_evidence_count": self.unattributed_evidence_count,
            "decision_applied": self.decision_applied,
            "automatic_action_taken": self.automatic_action_taken,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        lines = [
            "# Per-verb CAGE-1 Evidence Join",
            "",
            f"- Status: **{self.status}**",
            f"- Evidence: **{self.evidence_status}**",
            f"- Snapshots: **{len(self.snapshot_ids)}**",
            f"- Unmatched evidence identities: **{self.unmatched_identity_count}**",
            f"- Unattributed evidence rows: **{self.unattributed_evidence_count}**",
            f"- Ambiguous decision profiles: **{self.ambiguous_decision_count}**",
            f"- Decision applied: **{'yes' if self.decision_applied else 'no'}**",
            f"- Automatic action taken: **{'yes' if self.automatic_action_taken else 'no'}**",
            "",
            "| Verb | Join | Decision review | Fleet state | Valid evidence | Decisions | Coverage changed |",
            "|---|---|---|---|---:|---|---|",
        ]
        for item in self.profiles:
            decisions = ", ".join(f"{key}:{value}" for key, value in item.decision_counts.items()) or "none"
            lines.append(f"| `{item.verb_name}` | `{item.join_status}` | `{item.decision_review_status}` | `{item.latest_worst_state or 'none'}` | {item.valid_evidence_count} | {decisions} | {'yes' if item.coverage_changed else 'no'} |")
        if self.evidence_rows:
            lines.extend(["", "## Evidence provenance", ""])
            for row in self.evidence_rows:
                lines.append(f"- `{row.status}`: verb=`{row.verb_name}`, source=`{row.source_id or 'unknown'}`, line={row.source_line_number or 'unknown'}, decision={row.decision or 'none'}")
        return "\n".join(lines) + "\n"


def join_verb_fleet_evidence(fleet: Any, evidence: Optional[Any] = None) -> VerbEvidenceJoinSummary:
    fleet_profiles, snapshot_ids, fleet_status = _fleet_profiles(fleet)
    raw_rows, evidence_status = _evidence_rows(evidence)
    rows: list[EvidenceRow] = []
    for raw in raw_rows:
        line = raw.get("source_line_number", raw.get("line_number"))
        line_number = line if isinstance(line, int) and not isinstance(line, bool) else None
        rows.append(EvidenceRow(
            source_id=str(raw.get("source_id", "")),
            source_line_number=line_number,
            status=str(raw.get("status", "unknown")),
            verb_name=_identity(raw),
            decision=str(raw["decision"]) if isinstance(raw.get("decision"), str) and raw.get("decision") else None,
            operator_id=str(raw["operator_id"]) if isinstance(raw.get("operator_id"), str) and raw.get("operator_id") else None,
            advisory_digest=str(raw["advisory_digest"]) if isinstance(raw.get("advisory_digest"), str) and raw.get("advisory_digest") else None,
            raw=raw,
        ))
    by_identity: dict[str, list[EvidenceRow]] = defaultdict(list)
    for row in rows:
        by_identity[row.verb_name].append(row)
    fleet_by_name = {str(profile["verb_name"]): profile for profile in fleet_profiles}
    names = sorted(set(fleet_by_name) | set(by_identity))
    joined: list[VerbEvidenceJoin] = []
    for name in names:
        profile = fleet_by_name.get(name)
        matched = by_identity.get(name, [])
        statuses = Counter(row.status for row in matched)
        valid_rows = [row for row in matched if row.status == "valid"]
        decisions = Counter(row.decision for row in valid_rows if row.decision)
        decision_review_status = "missing" if not valid_rows else "single" if len(valid_rows) == 1 else "ambiguous"
        operators = tuple(sorted({row.operator_id for row in valid_rows if row.operator_id}))
        if profile is None:
            join_status = "unmatched_evidence"
            state, coverage, delta, profile_status = "", False, None, "unmatched"
        elif not matched:
            join_status = "no_evidence"
            state = str(profile.get("latest_worst_state", ""))
            coverage = bool(profile.get("coverage_changed", False))
            delta = profile.get("observation_delta") if isinstance(profile.get("observation_delta"), int) else None
            profile_status = str(profile.get("latest_status", ""))
        else:
            join_status = "matched"
            state = str(profile.get("latest_worst_state", ""))
            coverage = bool(profile.get("coverage_changed", False))
            delta = profile.get("observation_delta") if isinstance(profile.get("observation_delta"), int) else None
            profile_status = str(profile.get("latest_status", ""))
        joined.append(VerbEvidenceJoin(name, profile_status, state, coverage, delta, join_status, dict(sorted(statuses.items())), len(valid_rows), dict(sorted(decisions.items())), decision_review_status, operators, tuple(matched)))
    unmatched_count = sum(1 for name in by_identity if name not in fleet_by_name and name != UNATTRIBUTED)
    unattributed_count = len(by_identity.get(UNATTRIBUTED, []))
    status = "unverified" if evidence_status == "missing" else "matched" if not unmatched_count and all(item.join_status in {"matched", "no_evidence"} for item in joined) else "partial"
    return VerbEvidenceJoinSummary(
        JOIN_CATEGORY,
        SCHEMA_VERSION,
        status,
        fleet_status,
        evidence_status,
        snapshot_ids,
        tuple(joined),
        tuple(rows),
        dict(sorted(Counter(row.status for row in rows).items())),
        dict(sorted(Counter(row.decision for row in rows if row.status == "valid" and row.decision).items())),
        sum(1 for item in joined if item.decision_review_status == "ambiguous"),
        tuple(sorted({row.source_id for row in rows if row.source_id})),
        unmatched_count,
        unattributed_count,
        False,
        False,
    )


__all__ = [
    "EvidenceRow",
    "JOIN_CATEGORY",
    "SCHEMA_VERSION",
    "VerbEvidenceJoin",
    "VerbEvidenceJoinSummary",
    "join_verb_fleet_evidence",
    "load_json",
]
