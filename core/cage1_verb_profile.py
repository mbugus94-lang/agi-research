"""Per-verb CAGE-1 outcome profiles.

This module keeps aggregate governance results honest by preserving the
explicit action identity carried by an audit row. It does not infer a verb
from prose, and it never turns a missing identity into an invented label.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .cage1_evaluation import (
    OutcomeDistribution,
    _outcome_from_row,
    _record_outcome,
    load_reports_from_jsonl,
)
from .governed_action_loop import CrossCheckOutcome, CrossCheckReport

CAGE1_UNATTRIBUTED_VERB = "__unattributed__"


_STATE_RANK = {
    "admitted": 0,
    "held_for_evidence": 1,
    "narrowed_for_ring": 2,
    "narrowed_for_chain": 2,
    "quarantined_for_cef": 3,
    "escalated": 4,
    "refused": 5,
}


def verb_name_from_row(row: Dict[str, Any]) -> str:
    """Return the first explicit action identity, or the honest fallback bucket."""
    for key in ("verb_name", "action_type", "tool"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    detail = row.get("detail")
    if isinstance(detail, dict):
        for key in ("request_action_type", "verb_name", "action_type", "tool"):
            value = detail.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return CAGE1_UNATTRIBUTED_VERB


def _row_dict(value: CrossCheckReport | Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(value, CrossCheckReport):
        return value.to_dict()
    if hasattr(value, "to_dict"):
        result = value.to_dict()  # type: ignore[union-attr]
        if isinstance(result, dict):
            return dict(result)
    if isinstance(value, dict):
        return dict(value)
    raise TypeError(f"unsupported report type: {type(value).__name__}")


@dataclass
class VerbOutcomeProfile:
    """Outcome distribution and conservative rates for one explicit verb."""

    verb_name: str
    distribution: OutcomeDistribution
    worst_state: str = ""

    @property
    def n_observations(self) -> int:
        return self.distribution.total

    @property
    def admitted_rate(self) -> Optional[float]:
        return self.distribution.admitted / self.n_observations if self.n_observations else None

    @property
    def non_admitted_rate(self) -> Optional[float]:
        if not self.n_observations:
            return None
        return 1.0 - self.distribution.admitted / self.n_observations

    @property
    def refusal_rate(self) -> Optional[float]:
        return self.distribution.refused / self.n_observations if self.n_observations else None

    @property
    def escalation_rate(self) -> Optional[float]:
        return self.distribution.escalated / self.n_observations if self.n_observations else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verb_name": self.verb_name,
            "n_observations": self.n_observations,
            "distribution": self.distribution.to_dict(),
            "admitted_rate": self.admitted_rate,
            "non_admitted_rate": self.non_admitted_rate,
            "refusal_rate": self.refusal_rate,
            "escalation_rate": self.escalation_rate,
            "worst_state": self.worst_state,
        }


@dataclass
class VerbProfileReport:
    """A deterministic, replayable collection of per-verb profiles."""

    label: str
    profiles: List[VerbOutcomeProfile]
    n_rows: int
    n_unattributed: int
    report_digest: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "n_rows": self.n_rows,
            "n_unattributed": self.n_unattributed,
            "profiles": [profile.to_dict() for profile in self.profiles],
            "report_digest": self.report_digest,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        lines = [
            f"# Per-verb CAGE-1 Profile -- {self.label}",
            "",
            f"Rows evaluated: **{self.n_rows}**",
            f"Unattributed rows: **{self.n_unattributed}**",
            f"Report digest: `{self.report_digest[:16]}...`",
            "",
            "| Verb | N | Admitted | Non-admitted | Refused | Escalated | Worst state |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
        for profile in self.profiles:
            def rate(value: Optional[float]) -> str:
                return "n/a" if value is None else f"{value:.1%}"
            lines.append(
                f"| `{profile.verb_name}` | {profile.n_observations} | "
                f"{rate(profile.admitted_rate)} | {rate(profile.non_admitted_rate)} | "
                f"{rate(profile.refusal_rate)} | {rate(profile.escalation_rate)} | "
                f"`{profile.worst_state or 'none'}` |"
            )
        lines.append("")
        return "\n".join(lines)


def build_verb_profile(
    reports: Sequence[CrossCheckReport | Dict[str, Any]],
    *,
    label: str = "default",
) -> VerbProfileReport:
    """Group reports by explicit action identity and calculate per-verb rates."""
    grouped: Dict[str, VerbOutcomeProfile] = {}
    row_count = 0
    unattributed = 0
    for report in reports:
        row = _row_dict(report)
        verb = verb_name_from_row(row)
        if verb == CAGE1_UNATTRIBUTED_VERB:
            unattributed += 1
        profile = grouped.setdefault(verb, VerbOutcomeProfile(verb, OutcomeDistribution()))
        outcome = _outcome_from_row(row)
        _record_outcome(profile.distribution, outcome)
        state = {
            CrossCheckOutcome.ALLOW: "admitted",
            CrossCheckOutcome.HOLD_PENDING_EVIDENCE: "held_for_evidence",
            CrossCheckOutcome.HOLD_PENDING_RING: "narrowed_for_ring",
            CrossCheckOutcome.HOLD_PENDING_CHAIN: "narrowed_for_chain",
            CrossCheckOutcome.HOLD_PENDING_CEF: "quarantined_for_cef",
            CrossCheckOutcome.HOLD_PENDING_HUMAN: "escalated",
            CrossCheckOutcome.REJECT: "refused",
        }[outcome]
        if _STATE_RANK[state] >= _STATE_RANK.get(profile.worst_state, -1):
            profile.worst_state = state
        row_count += 1
    profiles = [grouped[name] for name in sorted(grouped)]
    payload = {
        "label": label,
        "n_rows": row_count,
        "n_unattributed": unattributed,
        "profiles": [profile.to_dict() for profile in profiles],
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return VerbProfileReport(label, profiles, row_count, unattributed, digest)


def load_and_profile(path: str, *, label: str = "default") -> VerbProfileReport:
    """Load report rows from JSONL and return a per-verb profile."""
    return build_verb_profile(load_reports_from_jsonl(path), label=label)


__all__ = [
    "VerbOutcomeProfile",
    "VerbProfileReport",
    "build_verb_profile",
    "load_and_profile",
    "verb_name_from_row",
]
