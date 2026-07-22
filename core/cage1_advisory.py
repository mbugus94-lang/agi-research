"""Review-only advisory projection for CAGE-1 fleet evidence.

This module preserves the raw fleet/trend envelopes and emits a bounded
operator-facing recommendation. It never changes policy, repairs evidence,
or applies an action automatically.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Optional


SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class CAGE1ReviewAdvisory:
    category: str
    schema_version: str
    severity: str
    recommendation: str
    operator_decision_required: bool
    automatic_action_taken: bool
    regression_count: int
    anomaly_count: int
    anomalies: list[str]
    notes: str
    raw_trend: Optional[dict[str, Any]]
    raw_fleet: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        lines = [
            "# CAGE-1 Review Advisory",
            "",
            f"- Severity: **{self.severity}**",
            f"- Recommendation: **{self.recommendation}**",
            f"- Operator decision required: **{'yes' if self.operator_decision_required else 'no'}**",
            f"- Automatic action taken: **{'yes' if self.automatic_action_taken else 'no'}**",
            f"- Trend regressions: **{self.regression_count}**",
            f"- Fleet anomalies: **{self.anomaly_count}**",
            "",
            "## Findings",
        ]
        if self.anomalies:
            lines.extend(f"- {item}" for item in self.anomalies)
        else:
            lines.append("- No fleet or trend anomalies were observed.")
        if self.notes:
            lines.extend(["", "## Notes", "", self.notes])
        lines.extend([
            "",
            "The raw fleet and trend envelopes are preserved for operator review. No automatic remediation was performed.",
            "",
        ])
        return "\n".join(lines)


def _mapping(value: Any) -> Mapping[str, Any]:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if not isinstance(value, Mapping):
        raise TypeError(f"CAGE-1 source must be a mapping or expose to_dict(), got {type(value).__name__}")
    return value


def _source_parts(source: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    payload = dict(_mapping(source))
    if "fleet" in payload:
        trend = payload.get("trend")
        fleet = payload.get("fleet")
        if not isinstance(fleet, Mapping):
            raise TypeError("CAGE-1 trend envelope must contain a fleet mapping")
        return (dict(trend) if isinstance(trend, Mapping) else {}, dict(fleet))
    return {}, payload


def project_review_advisory(source: Any, *, notes: str = "") -> CAGE1ReviewAdvisory:
    """Project CAGE-1 evidence into a review-only advisory.

    Severity is intentionally conservative and explainable:
    ``critical`` marks duplicate digest lineage or malformed/invalid evidence;
    ``high`` marks trend regressions; otherwise the result is ``none``.
    The raw envelopes are copied into the advisory for replay and review.
    """
    trend, fleet = _source_parts(source)
    regressions = trend.get("regressions", []) if isinstance(trend.get("regressions", []), list) else []
    anomalies = fleet.get("anomalies", []) if isinstance(fleet.get("anomalies", []), list) else []
    anomaly_text = [str(item) for item in anomalies]
    invalid_evidence = any("invalid " in item or "invalid_fields" in item for item in anomaly_text)
    duplicate_digest = any("duplicate digest" in item for item in anomaly_text)
    regression_count = len(regressions)
    if duplicate_digest or invalid_evidence:
        severity, recommendation = "critical", "escalate"
    elif regression_count or anomaly_text:
        severity, recommendation = "high", "review"
    else:
        severity, recommendation = "none", "defer"
    findings = [f"trend regression: {item.get('metric', 'unknown')} ({item.get('reason', 'regression')})" for item in regressions if isinstance(item, Mapping)]
    findings.extend(anomaly_text)
    return CAGE1ReviewAdvisory(
        category="cage1_fleet_review",
        schema_version=SCHEMA_VERSION,
        severity=severity,
        recommendation=recommendation,
        operator_decision_required=severity != "none",
        automatic_action_taken=False,
        regression_count=regression_count,
        anomaly_count=len(anomaly_text),
        anomalies=findings,
        notes=notes or str(fleet.get("notes", "") or trend.get("notes", "") or ""),
        raw_trend=trend or None,
        raw_fleet=fleet,
    )


def write_review_advisory(advisory: CAGE1ReviewAdvisory, path: str) -> None:
    Path(path).write_text(advisory.to_json() + "\n", encoding="utf-8")


__all__ = [
    "CAGE1ReviewAdvisory",
    "SCHEMA_VERSION",
    "project_review_advisory",
    "write_review_advisory",
]
