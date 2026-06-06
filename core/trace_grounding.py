"""
Trace Grounding - Bridge between EvidenceLedger and ReflectionEngine.

Inspired by:
- WISE (OpenReview T8HuiP3yM9): Causal Event Graph that connects each
  reasoning step to the observations that justify it.
- CaveAgent (OpenReview p3dlOhpqKD): stateful runtime objects that
  persist verification state across turns.
- Failing Tools (OpenReview j7YsSnA64D): empirical finding that
  LLM agents fail because they *skip verification / recovery* steps,
  not because they pick the wrong tool. A grounded trace surfaces
  the missing verifications.
- ACTS (arXiv:2606.03965): plan / execute / check / conclude steering.
  The grounding bridge is the *check* step: every "plan" and
  "execute" step gets an evidence-backed claim.
- Theory of Space (OpenReview c2cxLvsdUp): belief inertia. A claim
  is not "grounded" just because it exists; the bridge asks the
  ledger to verify it.

What this module does:
- For a thought trace, assert a Claim per step in the EvidenceLedger
  and add a piece of evidence per step (TOOL_TRACE for tool output,
  OBSERVATION for direct observation, INFERENCE for derived claims,
  USER_STATEMENT for user-supplied steps).
- Return a TraceGroundingReport containing the per-step verification,
  a coverage rate, the weakest step ids, and a deterministic
  recommended action.
- The bridge is LLM-agnostic and read-only on the trace: it never
  rewrites the agent's reasoning, only annotates it.

Decisions:
- Step ids are stable: `trace:{session_id or 'default'}:{index}`.
  This means re-grounding the same trace reuses the same claim ids.
- Evidence polarity is chosen by step type and trace contents:
  explore -> SUPPORTS (we explored, we have data), plan -> SUPPORTS
  (we have a plan), verify -> SUPPORTS (we verified), reflect ->
  INFERENCE (a derived observation). Tool output is always
  SUPPORTS unless its `status` field is "error" or "failed" (then
  REFUTES), in which case it surfaces the contradiction.
- The report recommends actions but does not auto-apply them.
  `recommended_action` is a string the caller can branch on.
- Backward compatible: a trace with no ledger simply produces a
  zero-coverage report (caller is expected to upgrade or escalate).

Safety:
- No self-modification. The bridge annotates traces, never mutates
  the agent's source code. Recommended actions are advisory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .evidence_ledger import (
    Claim,
    ClaimStatus,
    ClaimVerification,
    EvidenceKind,
    EvidenceLedger,
    EvidencePolarity,
    LedgerSummary,
)


# ---------------------------------------------------------------------------
# Recommended action vocabulary
# ---------------------------------------------------------------------------


RECOMMENDED_ACTIONS = frozenset(
    {
        "none",
        "reverify_ungrounded",
        "reverify_contradicted",
        "request_more_evidence",
        "escalate_to_human",
        "fallback_strategy",
    }
)


# ---------------------------------------------------------------------------
# Step type -> evidence kind / polarity defaults
# ---------------------------------------------------------------------------


_STEP_DEFAULTS: Dict[str, Tuple[EvidenceKind, EvidencePolarity]] = {
    # exploration / data gathering
    "explore": (EvidenceKind.OBSERVATION, EvidencePolarity.SUPPORTS),
    "search": (EvidenceKind.EXTERNAL, EvidencePolarity.SUPPORTS),
    "observe": (EvidenceKind.OBSERVATION, EvidencePolarity.SUPPORTS),
    # planning
    "plan": (EvidenceKind.INFERENCE, EvidencePolarity.SUPPORTS),
    "decompose": (EvidenceKind.INFERENCE, EvidencePolarity.SUPPORTS),
    # execution
    "execute": (EvidenceKind.TOOL_TRACE, EvidencePolarity.SUPPORTS),
    "tool": (EvidenceKind.TOOL_TRACE, EvidencePolarity.SUPPORTS),
    "code": (EvidenceKind.TOOL_TRACE, EvidencePolarity.SUPPORTS),
    # verification
    "verify": (EvidenceKind.OBSERVATION, EvidencePolarity.SUPPORTS),
    "check": (EvidenceKind.OBSERVATION, EvidencePolarity.SUPPORTS),
    # reflection / memory
    "reflect": (EvidenceKind.INFERENCE, EvidencePolarity.SUPPORTS),
    "memory": (EvidenceKind.MEMORY_ITEM, EvidencePolarity.SUPPORTS),
    # user / external
    "user": (EvidenceKind.USER_STATEMENT, EvidencePolarity.SUPPORTS),
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class StepGrounding:
    """Per-step evidence coverage in the ledger."""

    step_index: int
    step_type: str
    step_id: str
    claim_id: Optional[str]
    verification: Optional[ClaimVerification]
    content_preview: str = ""

    def to_dict(self) -> Dict[str, Any]:
        v = self.verification
        return {
            "step_index": self.step_index,
            "step_type": self.step_type,
            "step_id": self.step_id,
            "claim_id": self.claim_id,
            "content_preview": self.content_preview,
            "status": v.status.value if v else None,
            "support_count": v.support_count if v else 0,
            "refute_count": v.refute_count if v else 0,
            "weighted_support": v.weighted_support if v else 0.0,
            "weighted_refute": v.weighted_refute if v else 0.0,
            "confidence": v.confidence if v else 0.0,
            "is_fresh": v.is_fresh if v else False,
            "reason": v.reason if v else "no_claim",
        }


@dataclass
class TraceGroundingReport:
    """Aggregate view of a trace's evidence coverage."""

    trace_id: str
    step_count: int
    covered_steps: int
    coverage_rate: float
    ungrounded_step_ids: List[str] = field(default_factory=list)
    contradicted_step_ids: List[str] = field(default_factory=list)
    disputed_step_ids: List[str] = field(default_factory=list)
    expired_step_ids: List[str] = field(default_factory=list)
    weakest_step_ids: List[str] = field(default_factory=list)
    recommended_action: str = "none"
    step_groundings: List[StepGrounding] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "step_count": self.step_count,
            "covered_steps": self.covered_steps,
            "coverage_rate": round(self.coverage_rate, 3),
            "ungrounded_step_ids": list(self.ungrounded_step_ids),
            "contradicted_step_ids": list(self.contradicted_step_ids),
            "disputed_step_ids": list(self.disputed_step_ids),
            "expired_step_ids": list(self.expired_step_ids),
            "weakest_step_ids": list(self.weakest_step_ids),
            "recommended_action": self.recommended_action,
            "notes": list(self.notes),
            "steps": [s.to_dict() for s in self.step_groundings],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _preview(text: str, limit: int = 80) -> str:
    if not text:
        return ""
    text = str(text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "\u2026"


def _evidence_for_step(step: Dict[str, Any]) -> Tuple[EvidenceKind, EvidencePolarity]:
    """Pick a default evidence kind/polarity based on the step's content first,
    then fall back to the step-type default.
    """
    # 1. Status markers in 'output' take priority over type-based defaults.
    #    A tool step with status='error' is a REFUTES even though 'execute'
    #    would otherwise be SUPPORTS.
    output = step.get("output")
    if isinstance(output, dict):
        status = str(output.get("status", "")).lower()
        if status in {"error", "failed", "failure", "exception"}:
            return (EvidenceKind.TOOL_TRACE, EvidencePolarity.REFUTES)
        if status in {"ok", "success", "completed", "succeeded"}:
            return (EvidenceKind.TOOL_TRACE, EvidencePolarity.SUPPORTS)

    # 2. Free-text "error" markers (only if not negated)
    content = step.get("content") or step.get("output") or ""
    content_str = str(content)
    if content and "error" in content_str.lower() and "no error" not in content_str.lower():
        return (EvidenceKind.TOOL_TRACE, EvidencePolarity.REFUTES)

    # 3. Step-type default
    step_type = (step.get("type") or "").lower()
    default = _STEP_DEFAULTS.get(step_type)
    if default is not None:
        return default

    # 4. Fallback
    return (EvidenceKind.OBSERVATION, EvidencePolarity.SUPPORTS)


def _content_text(step: Dict[str, Any]) -> str:
    """Return a text form of the step's content for claim text / preview."""
    content = step.get("content")
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return json_dumps(content) if False else str(content)
    return str(content)


# Cheap pure-stdlib JSON without importing json globally for hot path.
import json as _json


def _safe_dumps(obj: Any) -> str:
    try:
        return _json.dumps(obj, default=str, sort_keys=True)
    except Exception:
        return str(obj)


# ---------------------------------------------------------------------------
# Main bridge
# ---------------------------------------------------------------------------


class TraceGrounder:
    """Asserts claims for trace steps and reports evidence coverage.

    Usage:
        ledger = EvidenceLedger()
        grounder = TraceGrounder(ledger)
        report = grounder.ground_trace(thought_trace, trace_id="session-1")
        # report.weakest_step_ids, report.recommended_action, etc.
    """

    def __init__(
        self,
        ledger: EvidenceLedger,
        evidence_weight: float = 1.0,
        evidence_confidence: float = 0.8,
        ungrounded_threshold: float = 0.5,
        contradiction_threshold: float = 0.1,
        max_weakest: int = 5,
    ) -> None:
        self.ledger = ledger
        self.evidence_weight = float(evidence_weight)
        self.evidence_confidence = float(evidence_confidence)
        self.ungrounded_threshold = float(ungrounded_threshold)
        self.contradiction_threshold = float(contradiction_threshold)
        self.max_weakest = int(max_weakest)

    # -- public API -------------------------------------------------------

    def step_id(self, trace_id: str, index: int) -> str:
        return f"step:{trace_id}:{index}"

    def claim_id(self, trace_id: str, index: int) -> str:
        return f"trace:{trace_id}:{index}"

    def ground_trace(
        self,
        thought_trace: Sequence[Dict[str, Any]],
        trace_id: str = "default",
    ) -> TraceGroundingReport:
        """Assert one claim per step and return the coverage report."""
        if not thought_trace:
            return TraceGroundingReport(
                trace_id=trace_id,
                step_count=0,
                covered_steps=0,
                coverage_rate=0.0,
                recommended_action="none",
                notes=["empty_trace"],
            )

        step_groundings: List[StepGrounding] = []
        ungrounded: List[str] = []
        contradicted: List[str] = []
        disputed: List[str] = []
        expired: List[str] = []

        # accumulate a "depends_on" lineage so claim N is linked to claim N-1
        previous_claim_id: Optional[str] = None

        for index, step in enumerate(thought_trace):
            sid = self.step_id(trace_id, index)
            cid = self.claim_id(trace_id, index)
            step_type = str(step.get("type", "unknown"))
            text = _content_text(step)
            preview = _preview(text)

            # 1. assert the claim
            claim = self.ledger.assert_claim(
                text=text or f"<{step_type} step>",
                author=str(step.get("author", "agent")),
                tags=[step_type, "trace", trace_id],
                depends_on=[previous_claim_id] if previous_claim_id else None,
                claim_id=cid,
                notes=sid,
            )

            # 2. add evidence (auto-classify kind/polarity)
            kind, polarity = _evidence_for_step(step)
            self.ledger.add_evidence(
                claim_id=claim.claim_id,
                polarity=polarity,
                content=f"trace[{trace_id}] step[{index}] type={step_type} text={preview}",
                kind=kind,
                source=str(step.get("source", sid)),
                weight=self.evidence_weight,
                confidence=self.evidence_confidence,
            )

            # 3. verify and bucket
            v = self.ledger.verify(claim.claim_id)
            if v.status == ClaimStatus.UNGROUNDED:
                ungrounded.append(sid)
            elif v.status == ClaimStatus.CONTRADICTED:
                contradicted.append(sid)
            elif v.status == ClaimStatus.DISPUTED:
                disputed.append(sid)
            elif v.status == ClaimStatus.EXPIRED:
                expired.append(sid)

            step_groundings.append(
                StepGrounding(
                    step_index=index,
                    step_type=step_type,
                    step_id=sid,
                    claim_id=claim.claim_id,
                    verification=v,
                    content_preview=preview,
                )
            )
            previous_claim_id = claim.claim_id

        # coverage = fraction of steps that landed in a non-UNGROUNDED state
        # EXPIRED is treated as covered-but-stale (the step was grounded
        # once; the recommendation is to re-verify)
        covered = step_count = len(step_groundings)
        ungrounded_count = len(ungrounded)
        contradicted_count = len(contradicted)
        expired_count = len(expired)
        covered_non_ungrounded = (
            step_count - ungrounded_count
        )
        coverage_rate = covered_non_ungrounded / step_count if step_count else 0.0

        # weakest steps = sorted by support - refute ascending
        def _sort_key(g: StepGrounding) -> Tuple[float, float]:
            if g.verification is None:
                return (-1.0, 0.0)
            return (
                g.verification.weighted_support - g.verification.weighted_refute,
                -g.verification.weighted_refute,
            )

        ranked = sorted(step_groundings, key=_sort_key)
        # exclude SUPPORTED steps from the "weakest" set so callers see
        # only the steps that need attention.
        weakest = [
            g.step_id
            for g in ranked
            if g.verification is not None
            and g.verification.status != ClaimStatus.SUPPORTED
        ][: self.max_weakest]

        # recommended action
        action, notes = self._recommend(
            coverage_rate=coverage_rate,
            contradicted_count=contradicted_count,
            expired_count=expired_count,
            weakest=weakest,
        )

        return TraceGroundingReport(
            trace_id=trace_id,
            step_count=step_count,
            covered_steps=covered_non_ungrounded,
            coverage_rate=coverage_rate,
            ungrounded_step_ids=ungrounded,
            contradicted_step_ids=contradicted,
            disputed_step_ids=disputed,
            expired_step_ids=expired,
            weakest_step_ids=weakest,
            recommended_action=action,
            step_groundings=step_groundings,
            notes=notes,
        )

    # -- internals --------------------------------------------------------

    def _recommend(
        self,
        coverage_rate: float,
        contradicted_count: int,
        expired_count: int,
        weakest: List[str],
    ) -> Tuple[str, List[str]]:
        if contradicted_count > 0:
            return (
                "reverify_contradicted",
                [f"{contradicted_count} contradicted step(s) require re-verification"],
            )
        if coverage_rate < self.ungrounded_threshold:
            return (
                "request_more_evidence",
                [
                    f"coverage_rate={coverage_rate:.2f} below threshold "
                    f"{self.ungrounded_threshold:.2f}"
                ],
            )
        if expired_count > 0 and not weakest:
            return (
                "reverify_ungrounded",
                [f"{expired_count} expired step(s) need re-verification"],
            )
        if weakest:
            return (
                "reverify_ungrounded",
                [f"weakest steps: {', '.join(weakest)}"],
            )
        if expired_count > 0:
            return (
                "reverify_ungrounded",
                [f"{expired_count} expired step(s) need re-verification"],
            )
        return ("none", ["all steps supported"])

    # -- utility: produce a summary dict for the metacognitive monitor ----

    def to_calibration_blend(self, report: TraceGroundingReport) -> Dict[str, float]:
        """Return a small dict the monitor can fold into its calibration signals."""
        return {
            "trace_coverage_rate": report.coverage_rate,
            "trace_ungrounded_count": float(len(report.ungrounded_step_ids)),
            "trace_contradicted_count": float(len(report.contradicted_step_ids)),
            "trace_weakest_count": float(len(report.weakest_step_ids)),
        }


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------


def ground_trace(
    ledger: EvidenceLedger,
    thought_trace: Sequence[Dict[str, Any]],
    trace_id: str = "default",
    **kwargs: Any,
) -> TraceGroundingReport:
    """One-shot helper: build a grounder and run it on a trace."""
    grounder = TraceGrounder(ledger, **kwargs)
    return grounder.ground_trace(thought_trace, trace_id=trace_id)


__all__ = [
    "RECOMMENDED_ACTIONS",
    "StepGrounding",
    "TraceGroundingReport",
    "TraceGrounder",
    "ground_trace",
]
