"""
CEF Substrate Integration -- bridge the CEF/CET detector family
(per-output ``CEFDetector`` + session ``CEFSessionDetector``) to the
three core safety substrates:

  * ``EvidenceLedger`` -- CEF detections and session verdicts become
    auditable claims, just like proof-carrying actions.
  * ``SafetyCircuitBreaker`` -- CRITICAL per-output detections and
    session-level ``POINT_OF_NO_RETURN`` verdicts trip the breaker
    for the agent's principal.
  * ``AgentLoop`` (Jun 17 build) -- the long-horizon loop's act ->
    observe -> evaluate cycle folds each ``observation`` through the
    CEF substrate; the session verdict is the loop's *output-boundary*
    safety signal.

Motivation
----------
The June 19 build created ``CEFDetector`` (per-output fabrication
detection); the June 20 build created ``CEFSessionDetector`` (the
"point of no return" aggregator) and wired it into
``GovernedActionLoop``. The natural next move -- flagged in the June
20 build log's "Next Priority" -- is to wire CEF into the rest of
the substrate: the long-horizon ``AgentLoop``, the causal
``EvidenceLedger``, and the per-action ``SafetyCircuitBreaker``.

This module is the **additive** version of that wiring. It is *not*
a modification to the substrate files themselves (those are in
``SELF_SURFACE_PREFIXES`` per ``core/recursive_self_improvement.py``,
and the safety policy in ``SAFETY.md`` requires human review for any
self-surface edit). Instead, this module provides call-site helpers
that downstream code uses to *connect* their existing CEF detectors
to the rest of the substrate. If/when the wiring is approved for
in-substrate integration, the helpers in this module become the
reference implementation.

Design constraints
------------------
* Pure-Python, no I/O, no LLM, no clock reads. Operators decide when
  to call these helpers.
* The ledger writer is **additive**: a CLEAN detection is recorded
  (low-weight) but never overwrites prior evidence. CRITICAL
  detections are recorded as REFUTES evidence with a high weight
  on a fresh claim, so a verification pass flips the claim to
  CONTRADICTED.
* The breaker assessor is **additive**: a CLEAN or LOW detection
  does *not* trip the breaker. CRITICAL -> trip (one strike);
  ``POINT_OF_NO_RETURN`` session -> trip (session-level strike).
* The loop bridge is **additive**: it never mutates the loop's
  verdict. It folds the loop's observations through the session
  detector and returns the session verdict; the caller decides
  whether to halt.
* The session_id for the CEFSessionDetector is the loop's
  ``loop_id`` (or ``principal``) -- the substrate-level identity
  that survives across runs. This mirrors the NewCore "digital
  employee" framing where one identity owns many sessions.

What this module is *not*
-------------------------
* It is not an auto-trier. ``assess_cef_to_breaker`` returns a
  ``CEFBreakerOutcome`` with a recommendation; the caller
  (``GovernedActionLoop`` / ``AgentLoop``) decides whether to trip.
  Operators can wrap the helper in a layer that *always* trips
  CRITICAL, or one that only logs CRITICAL on a configurable rate.
* It is not a replacement for the substrate's per-action and
  per-step checks. The CEF substrate is the **output-boundary**
  layer; the breaker is the **action-boundary** layer; the ledger
  is the **causal** layer. Each layer has its own job.

Research synthesis
------------------
* arXiv:2606.14831 (Jun 12 2026, CEF/CET paper) -- the per-output
  detector is the substrate; the session aggregator is the load-
  bearing claim; "T20+ ignores ground truth" is the recovery
  horizon.
* Google DeepMind's June 18 layered-security roadmap (Fortune) --
  treats AI agents as rogue insiders; layered control over tools,
  data, and behavior. Our CEF + breaker + ledger + Three-Ring
  substrate is the open-source implementation of that pattern.
* "Foundry: Host-Owned Trust and Memory for Long-Horizon Agent
  Swarms" (OpenReview MWLIRDa4DC, 2026) -- central evaluator +
  established-facts registry + cross-agent memory. Our
  ``EvidenceLedger`` is the in-process facts registry; the CEF
  integration is the bridge from per-output detection to the
  registry.
* arXiv:2606.20510 (Jun 20 2026, "Efficient and Sound Probabilistic
  Verification for AI Agents") -- distributionally-robust bounds on
  policy-violation probability. The CEF session verdict is a
  *point estimate*; the breaker is a *boolean*. Future work is to
  add probabilistic upper bounds.
* Salesforce/Fin $3.6B (Jun 15), NewCore $66M (Jun 15) -- the
  enterprise agent market is converging on identity + lifecycle +
  audit. Our AgentIdentity + RevocationChannel + EvidenceLedger is
  the in-process substrate.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .cef_detector import (
    CEFAction,
    CEFDetection,
    CEFDetector,
    CEFDetectorConfig,
    CEFSeverity,
    CEFType,
    create_cef_detector,
)
from .cef_session import (
    CEFSessionAction,
    CEFSessionConfig,
    CEFSessionDetector,
    CEFSessionState,
    CEFSessionVerdict,
    create_cef_session_detector,
)
from .evidence_ledger import (
    Claim,
    ClaimStatus,
    Evidence,
    EvidenceKind,
    EvidenceLedger,
    EvidencePolarity,
)
from .safety_circuit_breaker import (
    ActionCategory,
    CircuitState,
    OperationRecord,
    RiskLevel,
    SafetyCircuitBreaker,
)

# Optional: the arXiv:2606.20510 probabilistic verification
# substrate. Imported lazily so the CEF substrate still works
# without scipy; ``TripObservation`` is referenced as a global
# inside ``assess_cef_to_breaker`` and guarded by an
# ``is None`` check.
try:
    from .cef_probabilistic_verification import (
        ProbabilisticTripEngine,
        TripBand,
        TripObservation,
    )
except ImportError:  # pragma: no cover -- scipy not installed
    ProbabilisticTripEngine = None  # type: ignore[assignment]
    TripBand = None  # type: ignore[assignment]
    TripObservation = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CEFIntegrationConfig:
    """Operator-controlled configuration for the CEF substrate bridge.

    Attributes
    ----------
    severity_for_refute : CEFSeverity
        Minimum per-output severity that writes REFUTES evidence to
        the ledger. Below this, evidence is recorded as SUPPORTS with
        low weight ("detection observed, does not refute the
        agent's claim"). Default ``MEDIUM`` -- a single LOW
        (vague-excuse) detection is not strong enough to refute
        the agent's claim that it is acting in good faith.
    severity_for_trip : CEFSeverity
        Minimum per-output severity that trips the breaker. Default
        ``CRITICAL`` -- only CET-grade fabrications auto-trip; HIGH
        and below log but do not trip. Operators can lower to HIGH
        for a more aggressive posture.
    trip_on_horizon : bool
        Whether a session-level ``POINT_OF_NO_RETURN`` trips the
        breaker regardless of peak severity. Default True -- the
        session-level signal is the load-bearing claim, so we always
        act on it.
    trip_on_restart : bool
        Whether a session-level ``RESTART`` action also trips the
        breaker (in addition to the per-output CRITICAL strike).
        Default True -- a RESTART verdict means the principal
        should be re-instantiated, which is what an OPEN breaker
        forces.
    trip_categories : Tuple[ActionCategory, ...]
        The action categories a CEF trip blocks. Default is
        ``(ActionCategory.EXECUTE, ActionCategory.FILE_SYSTEM,
        ActionCategory.EXTERNAL_API)`` -- a fabricating agent
        should not be executing, writing files, or hitting external
        APIs. Read-only actions are still allowed (the agent can
        keep observing while the operator reviews).
    claim_author : str
        The author of the CEF-induced claims. Default "cef_substrate".
    probabilistic_engine : Optional["ProbabilisticTripEngine"]
        Optional engine for the (1 - alpha) upper bound on the
        trip rate. When supplied, every ``assess_cef_to_breaker``
        call feeds the engine (trip / no-trip) and the outcome
        carries ``trip_probability``, ``trip_upper_bound``,
        ``trip_band``, and ``trip_n_samples``. See
        ``core.cef_probabilistic_verification`` (arXiv:2606.20510).
        Default ``None`` -- the engine is opt-in; existing call
        sites are unaffected.
    """

    severity_for_refute: CEFSeverity = CEFSeverity.MEDIUM
    severity_for_trip: CEFSeverity = CEFSeverity.CRITICAL
    trip_on_horizon: bool = True
    trip_on_restart: bool = True
    trip_categories: Tuple[ActionCategory, ...] = (
        ActionCategory.EXECUTE,
        ActionCategory.FILE_SYSTEM,
        ActionCategory.EXTERNAL_API,
    )
    claim_author: str = "cef_substrate"
    probabilistic_engine: Optional[Any] = None  # forward ref to ProbabilisticTripEngine


# Late-bound forward import for the type hint. Done at module
# scope so the type is resolvable in IDEs; the actual wiring in
# ``assess_cef_to_breaker`` is duck-typed so the integration
# remains decoupled.
try:  # pragma: no cover -- import-time wiring
    from .cef_probabilistic_verification import (  # noqa: F401
        ProbabilisticTripEngine,
        TripBand,
        TripObservation,
        band_for_upper_bound,
    )
except ImportError:  # pragma: no cover -- pre-integration import order
    ProbabilisticTripEngine = None  # type: ignore[assignment]
    TripBand = None  # type: ignore[assignment]
    TripObservation = None  # type: ignore[assignment]
    band_for_upper_bound = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Ledger outcome
# ---------------------------------------------------------------------------


@dataclass
class CEFLedgerOutcome:
    """Result of a ``record_cef_to_ledger`` call.

    Attributes
    ----------
    claim_id : Optional[str]
        The new or existing claim id. None if ``detection`` was a
        CLEAN beat below the ledger floor.
    evidence_ids : List[str]
        The evidence ids written to the ledger. May be empty (CLEAN
        beat) or one (single detection) or more (multi-evidence
        from markers).
    claim_status : Optional[ClaimStatus]
        The claim's status after the write. None if no claim was
        touched.
    detection_id : str
        The detection_id of the input detection (echoed for audit).
    session_digest : Optional[str]
        The session_digest from the input verdict, if any. None
        for per-output calls.
    was_refute : bool
        True if the evidence was written as REFUTES (the detection
        met the refute floor). False if written as SUPPORTS.
    rationale : str
        Human-readable explanation of the write.
    """

    claim_id: Optional[str]
    evidence_ids: List[str]
    claim_status: Optional[ClaimStatus]
    detection_id: str
    session_digest: Optional[str]
    was_refute: bool
    rationale: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "evidence_ids": list(self.evidence_ids),
            "claim_status": self.claim_status.value if self.claim_status else None,
            "detection_id": self.detection_id,
            "session_digest": self.session_digest,
            "was_refute": bool(self.was_refute),
            "rationale": self.rationale,
        }


# ---------------------------------------------------------------------------
# Breaker outcome
# ---------------------------------------------------------------------------


class CEFBreakerVerdict(str, Enum):
    """The recommendation from ``assess_cef_to_breaker``.

    NO_TRIP      -- the detection is below the trip floor; nothing
                    to do
    TRIP         -- the breaker should open (or stay open)
    TRIP_SESSION -- the session-level signal forces a trip
    """

    NO_TRIP = "no_trip"
    TRIP = "trip"
    TRIP_SESSION = "trip_session"


@dataclass
class CEFBreakerOutcome:
    """Result of an ``assess_cef_to_breaker`` call.

    Attributes
    ----------
    verdict : CEFBreakerVerdict
        The recommendation.
    detection_id : str
        The detection_id of the input detection.
    session_digest : Optional[str]
        The session_digest from the input verdict, if any.
    session_state : Optional[CEFSessionState]
        The session state, if a session verdict was supplied.
    rationale : str
        Human-readable explanation.
    tripped_categories : List[ActionCategory]
        The categories a caller would block. Empty if NO_TRIP.
    should_open : bool
        Convenience: ``True`` iff the breaker should be opened.
    trip_probability : float
        The posterior-mean point estimate of the trip rate
        (from the configured ``ProbabilisticTripEngine``).
        ``0.0`` if no engine is configured. See
        ``core.cef_probabilistic_verification`` (arXiv:2606.20510).
    trip_upper_bound : float
        The (1 - alpha) DRO upper bound on the trip rate
        (sound, distribution-free). ``0.0`` if no engine is
        configured. The caller can gate breaker-open decisions
        on this bound (e.g., only open when bound >= 0.05).
    trip_band : str
        The discrete trip band (``"low"`` / ``"medium"`` /
        ``"high"`` / ``"critical"`` / ``"unknown"``). Derived
        from ``trip_upper_bound`` via
        ``core.cef_probabilistic_verification.band_for_upper_bound``.
        ``"unknown"`` if no engine is configured.
    trip_n_samples : int
        The number of observations that fed the engine. ``0``
        if no engine is configured.
    """

    verdict: CEFBreakerVerdict
    detection_id: str
    session_digest: Optional[str]
    session_state: Optional[CEFSessionState]
    rationale: str
    tripped_categories: List[ActionCategory] = field(default_factory=list)
    should_open: bool = False
    # Probabilistic-verification fields (arXiv:2606.20510). All
    # default to the "no engine" state so existing call sites
    # that ignore these fields are unaffected.
    trip_probability: float = 0.0
    trip_upper_bound: float = 0.0
    trip_band: str = "unknown"
    trip_n_samples: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "detection_id": self.detection_id,
            "session_digest": self.session_digest,
            "session_state": self.session_state.value if self.session_state else None,
            "rationale": self.rationale,
            "tripped_categories": [cat.value for cat in self.tripped_categories],
            "should_open": self.should_open,
            "trip_probability": self.trip_probability,
            "trip_upper_bound": self.trip_upper_bound,
            "trip_band": self.trip_band,
            "trip_n_samples": self.trip_n_samples,
        }


# Backward-compat re-export: callers that imported the trip-band
# enum from this module will resolve via the integration module.
# The canonical home is ``core.cef_probabilistic_verification``.
try:  # pragma: no cover -- import-time wiring
    from .cef_probabilistic_verification import (  # noqa: F401
        TripBand,
        band_for_upper_bound,
    )
except ImportError:  # pragma: no cover -- pre-integration import order
    TripBand = None  # type: ignore[assignment]
    band_for_upper_bound = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Agent-loop bridge
# ---------------------------------------------------------------------------


@dataclass
class CEFLoopStep:
    """A single folded step in the CEF <-> AgentLoop bridge.

    Attributes
    ----------
    step_index : int
        The AgentLoop's step sequence number (act-evaluate pair).
    agent_output : str
        The text the agent produced for this step.
    detection : CEFDetection
        The per-output CEF detection.
    session_verdict : CEFSessionVerdict
        The session verdict after folding the detection.
    observation : Optional[Dict[str, Any]]
        The AgentLoop's observation dict (echoed for audit).
    recommended_loop_action : str
        The bridge's recommendation: ``"continue"``, ``"warn"``,
        ``"freeze"``, ``"restart"``, or ``"halt"``.
    """

    step_index: int
    agent_output: str
    detection: CEFDetection
    session_verdict: CEFSessionVerdict
    observation: Optional[Dict[str, Any]]
    recommended_loop_action: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_index": self.step_index,
            "agent_output": self.agent_output,
            "detection": self.detection.to_dict(),
            "session_verdict": self.session_verdict.to_dict(),
            "observation": self.observation,
            "recommended_loop_action": self.recommended_loop_action,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_claim_text(
    detection: CEFDetection,
    session_verdict: Optional[CEFSessionVerdict],
) -> str:
    """Build the claim text for a CEF detection.

    The claim is the proposition that the agent's output is
    fabrication-grounded. We do *not* claim the agent is "lying" --
    we claim a specific CEF pattern matched with a specific severity
    and type. Operators verify the claim by re-running the detector
    on the same output.
    """
    parts = [
        f"CEF detection {detection.detection_id}: "
        f"type={detection.cef_type.value} "
        f"severity={detection.severity.value} "
        f"action={detection.recommended_action.value}",
    ]
    if session_verdict is not None:
        parts.append(
            f" session={session_verdict.session_id} "
            f"state={session_verdict.state.value} "
            f"action={session_verdict.action.value} "
            f"peak={session_verdict.peak_severity.value}"
        )
    # Snippet (truncated to 200 chars to keep the claim text small)
    if detection.markers:
        snippet = detection.markers[0].snippet
        if len(snippet) > 200:
            snippet = snippet[:197] + "..."
        parts.append(f" snippet={snippet!r}")
    return "".join(parts)


def _build_evidence_content(
    detection: CEFDetection,
    session_verdict: Optional[CEFSessionVerdict],
) -> str:
    """Build the evidence content string for a CEF detection."""
    parts = [
        f"detection_id={detection.detection_id}",
        f"type={detection.cef_type.value}",
        f"severity={detection.severity.value}",
        f"action={detection.recommended_action.value}",
        f"confidence={detection.confidence:.3f}",
    ]
    if session_verdict is not None:
        parts.extend(
            [
                f"session_state={session_verdict.state.value}",
                f"session_action={session_verdict.action.value}",
                f"session_digest={session_verdict.session_digest[:16]}...",
            ]
        )
    if detection.rationale:
        parts.append(f"rationale={detection.rationale}")
    return "; ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def record_cef_to_ledger(
    detection: CEFDetection,
    ledger: EvidenceLedger,
    config: Optional[CEFIntegrationConfig] = None,
    session_verdict: Optional[CEFSessionVerdict] = None,
    claim_id: Optional[str] = None,
    evidence_id: Optional[str] = None,
) -> CEFLedgerOutcome:
    """Record a CEF detection (and optional session verdict) to an
    ``EvidenceLedger``.

    The ledger is the substrate's causal record. Writing a CEF
    detection to the ledger makes it auditable: a future
    ``verify_all()`` pass flips the claim to CONTRADICTED on a
    CRITICAL detection, or DISPUTED on a MEDIUM/HIGH detection
    with mixed prior evidence.

    Parameters
    ----------
    detection : CEFDetection
        The per-output detection to record.
    ledger : EvidenceLedger
        The destination ledger.
    config : Optional[CEFIntegrationConfig]
        The integration config. None uses defaults.
    session_verdict : Optional[CEFSessionVerdict]
        The session verdict, if available. Carried in the evidence
        content (not the claim) so a future reviewer can see the
        session-level context.
    claim_id : Optional[str]
        Caller-supplied claim id (for deterministic replay).
    evidence_id : Optional[str]
        Caller-supplied evidence id (for deterministic replay).

    Returns
    -------
    CEFLedgerOutcome
        The outcome, including the claim/evidence ids and a
        rationale.

    Notes
    -----
    * A CLEAN detection (``CEFSeverity.NONE``) is recorded as
      SUPPORTS with low weight -- the agent's output was checked and
      was clean. This is the substrate's "I checked, and it's OK"
      signal.
    * A detection below ``config.severity_for_refute`` is recorded
      as SUPPORTS with moderate weight -- the detection is
      informative but does not refute the agent's claim.
    * A detection at or above ``config.severity_for_refute`` is
      recorded as REFUTES with high weight -- the agent's claim is
      contradicted.
    """
    cfg = config or CEFIntegrationConfig()

    # CLEAN beat: no claim, no evidence. The caller is asking "did
    # anything happen?" and the answer is no.
    if detection.is_clean():
        return CEFLedgerOutcome(
            claim_id=None,
            evidence_ids=[],
            claim_status=None,
            detection_id=detection.detection_id,
            session_digest=session_verdict.session_digest if session_verdict else None,
            was_refute=False,
            rationale="clean detection: no claim written",
        )

    is_refute = detection.severity.value >= cfg.severity_for_refute.value
    polarity = EvidencePolarity.REFUTES if is_refute else EvidencePolarity.SUPPORTS
    weight = 0.9 if is_refute else 0.4
    confidence = 0.95 if is_refute else 0.7

    cid = claim_id or f"cef-claim-{detection.detection_id}"
    claim_text = _build_claim_text(detection, session_verdict)
    claim = ledger.assert_claim(
        text=claim_text,
        author=cfg.claim_author,
        tags=["cef", f"cef-type:{detection.cef_type.value}", f"severity:{detection.severity.value}"],
        claim_id=cid,
    )

    evidence_content = _build_evidence_content(detection, session_verdict)
    ev = ledger.add_evidence(
        claim_id=claim.claim_id,
        polarity=polarity,
        content=evidence_content,
        kind=EvidenceKind.OBSERVATION,
        source=f"cef_detector:{detection.detection_id}",
        weight=weight,
        confidence=confidence,
        evidence_id=evidence_id,
    )
    evidence_ids = [ev.evidence_id] if ev is not None else []

    rationale_parts = [
        f"wrote {polarity.value} evidence (weight={weight:.2f}, "
        f"confidence={confidence:.2f}) for claim {claim.claim_id}",
        f"type={detection.cef_type.value}",
        f"severity={detection.severity.value}",
    ]
    if session_verdict is not None:
        rationale_parts.append(
            f"session_state={session_verdict.state.value} "
            f"session_action={session_verdict.action.value}"
        )

    ledger.verify(claim.claim_id)

    return CEFLedgerOutcome(
        claim_id=claim.claim_id,
        evidence_ids=evidence_ids,
        claim_status=claim.status,
        detection_id=detection.detection_id,
        session_digest=session_verdict.session_digest if session_verdict else None,
        was_refute=is_refute,
        rationale="; ".join(rationale_parts),
    )


def assess_cef_to_breaker(
    detection: CEFDetection,
    breaker: Optional[SafetyCircuitBreaker] = None,
    config: Optional[CEFIntegrationConfig] = None,
    session_verdict: Optional[CEFSessionVerdict] = None,
    principal: str = "cef_principal",
) -> CEFBreakerOutcome:
    """Assess a CEF detection (and optional session verdict) against
    a ``SafetyCircuitBreaker``.

    The breaker is the substrate's per-action gate. Opening the
    breaker blocks the principal from issuing further write/execute/
    external-API actions until the operator resets it. A fabricating
    agent should not be able to act on its fabrications.

    Parameters
    ----------
    detection : CEFDetection
        The per-output detection to assess.
    breaker : SafetyCircuitBreaker
        The destination breaker.
    config : Optional[CEFIntegrationConfig]
        The integration config. None uses defaults.
    session_verdict : Optional[CEFSessionVerdict]
        The session verdict, if available. Session-level signals
        can trip the breaker even when the per-output detection is
        below the floor.
    principal : str
        The principal the trip is for. Default ``"cef_principal"``.

    Returns
    -------
    CEFBreakerOutcome
        The outcome, including the verdict, the recommended
        categories to block, and a rationale.

    Notes
    -----
    * A CLEAN detection never trips the breaker.
    * A detection below ``config.severity_for_trip`` does not trip
      the breaker (it is recorded elsewhere, e.g., the ledger).
    * A detection at or above ``config.severity_for_trip`` trips
      the breaker for ``config.trip_categories``.
    * A session in ``POINT_OF_NO_RETURN`` trips the breaker if
      ``config.trip_on_horizon`` is True.
    * A session with ``RESTART`` action also trips the breaker if
      ``config.trip_on_restart`` is True.
    * The breaker is **not** mutated by this function -- the caller
      decides whether to call ``breaker.reset_circuit`` /
      ``breaker._record_failure`` / or use the ``should_open`` flag
      in their own gate. This keeps the function side-effect free.
    """
    cfg = config or CEFIntegrationConfig()

    categories: List[ActionCategory] = []
    verdict: CEFBreakerVerdict = CEFBreakerVerdict.NO_TRIP
    rationale_parts: List[str] = []

    # Per-output trip
    if not detection.is_clean() and detection.severity.value >= cfg.severity_for_trip.value:
        categories = list(cfg.trip_categories)
        verdict = CEFBreakerVerdict.TRIP
        rationale_parts.append(
            f"per-output {detection.severity.value} >= "
            f"severity_for_trip={cfg.severity_for_trip.value}: trip"
        )

    # Session-level trip
    if session_verdict is not None:
        session_state = session_verdict.state
        session_action = session_verdict.action
        if cfg.trip_on_horizon and session_state == CEFSessionState.POINT_OF_NO_RETURN:
            categories = list(cfg.trip_categories)
            verdict = CEFBreakerVerdict.TRIP_SESSION
            rationale_parts.append(
                f"session {session_verdict.session_id} crossed "
                f"POINT_OF_NO_RETURN: trip"
            )
        elif cfg.trip_on_restart and session_action == CEFSessionAction.RESTART:
            categories = list(cfg.trip_categories)
            verdict = CEFBreakerVerdict.TRIP_SESSION
            rationale_parts.append(
                f"session {session_verdict.session_id} action=RESTART: trip"
            )

    if verdict == CEFBreakerVerdict.NO_TRIP:
        rationale_parts.append(
            f"per-output {detection.severity.value} below "
            f"severity_for_trip={cfg.severity_for_trip.value}: no trip"
        )
        if session_verdict is not None:
            rationale_parts.append(
                f"session state={session_verdict.state.value} "
                f"action={session_verdict.action.value}: no trip"
            )

    # Optional: feed the probabilistic trip engine. The engine is
    # the arXiv:2606.20510 (1 - alpha) upper bound; feeding it here
    # gives the caller a *measurable* trip rate even when the
    # boolean verdict is NO_TRIP. We feed AFTER computing the
    # verdict so the engine's state always reflects the *current*
    # decision, not a prior one.
    trip_probability = 0.0
    trip_upper_bound_v = 0.0
    trip_band_v = "unknown"
    trip_n_samples_v = 0
    if cfg.probabilistic_engine is not None and TripObservation is not None:
        try:
            engine = cfg.probabilistic_engine
            obs = TripObservation(
                tripped=(verdict != CEFBreakerVerdict.NO_TRIP),
                source="per_output",
                detection_id=detection.detection_id,
                session_digest=(
                    session_verdict.session_digest if session_verdict else None
                ),
            )
            engine.update(obs)
            trip_probability = float(engine.trip_probability)
            trip_upper_bound_v = float(engine.trip_upper_bound)
            trip_band_v = (
                engine.trip_band.value
                if hasattr(engine.trip_band, "value")
                else str(engine.trip_band)
            )
            trip_n_samples_v = int(engine.n_total)
            rationale_parts.append(
                f"probabilistic: n={trip_n_samples_v} "
                f"p={trip_probability:.4f} "
                f"ub={trip_upper_bound_v:.4f} band={trip_band_v}"
            )
        except Exception:  # pragma: no cover -- defensive
            # Engine failure is never a load-bearing claim; we
            # silently fall back to the boolean verdict.
            pass

    return CEFBreakerOutcome(
        verdict=verdict,
        detection_id=detection.detection_id,
        session_digest=session_verdict.session_digest if session_verdict else None,
        session_state=session_verdict.state if session_verdict else None,
        rationale="; ".join(rationale_parts),
        tripped_categories=categories,
        should_open=verdict != CEFBreakerVerdict.NO_TRIP,
        trip_probability=trip_probability,
        trip_upper_bound=trip_upper_bound_v,
        trip_band=trip_band_v,
        trip_n_samples=trip_n_samples_v,
    )


def fold_step_into_cef(
    agent_output: str,
    step_index: int,
    session_detector: CEFSessionDetector,
    observation: Optional[Dict[str, Any]] = None,
    turn_index: Optional[int] = None,
) -> CEFLoopStep:
    """Fold one AgentLoop step into the CEF substrate.

    The AgentLoop's act -> observe cycle produces a textual agent
    output per step. This helper runs the CEFDetector on that
    output, folds the result into the session detector, and
    returns the step-level CEF data.

    Parameters
    ----------
    agent_output : str
        The text the agent produced for this step (the candidate
        for fabrication detection).
    step_index : int
        The AgentLoop's step sequence number.
    session_detector : CEFSessionDetector
        The session detector. Mutated in place (folded). The caller
        owns the session detector and reuses it across steps.
    observation : Optional[Dict[str, Any]]
        The AgentLoop's observation dict. Echoed for audit; not
        used for detection.
    turn_index : Optional[int]
        The turn number. If None, ``step_index`` is used.

    Returns
    -------
    CEFLoopStep
        The step's CEF data, including the per-output detection,
        the session verdict, and the recommended loop action.

    Notes
    -----
    * The recommended loop action is derived from the session
      verdict, not the per-output detection: a clean output on a
      horizon-crossed session is still ``"freeze"`` or ``"restart"``
      because the session-level signal is the load-bearing claim.
    * The session detector is mutated in place. If the caller
      wants a snapshot, they should ``reset()`` and re-fold.
    """
    if turn_index is None:
        turn_index = step_index

    # Run the per-output detector using the session detector's
    # underlying config. The session detector owns its own
    # CEFDetectorConfig; this keeps the patterns consistent.
    detector = CEFDetector(session_detector.config.detector_config)
    detection = detector.detect(agent_output)

    # Fold into the session detector.
    session_verdict = session_detector.observe(detection, turn_index=turn_index)

    # Derive the recommended loop action from the session verdict.
    # CEFSessionAction -> loop action:
    #   CONTINUE -> "continue"
    #   WARN     -> "warn"
    #   FREEZE   -> "freeze"  (stop issuing more actions)
    #   RESTART  -> "restart" (re-instantiate the principal)
    if session_verdict.action == CEFSessionAction.CONTINUE:
        recommended = "continue"
    elif session_verdict.action == CEFSessionAction.WARN:
        recommended = "warn"
    elif session_verdict.action == CEFSessionAction.FREEZE:
        recommended = "freeze"
    elif session_verdict.action == CEFSessionAction.RESTART:
        recommended = "restart"
    else:
        recommended = "halt"

    # Per-output CRITICAL (CET) escalates to "halt" regardless of
    # session verdict. The CET case is the agent faking its own
    # crash -- the loop should not be tricked into continuing.
    if detection.severity == CEFSeverity.CRITICAL:
        recommended = "halt"

    return CEFLoopStep(
        step_index=step_index,
        agent_output=agent_output,
        detection=detection,
        session_verdict=session_verdict,
        observation=observation,
        recommended_loop_action=recommended,
    )


# ---------------------------------------------------------------------------
# Convenience constructors
# ---------------------------------------------------------------------------


def create_cef_integration(
    session_config: Optional[CEFSessionConfig] = None,
    integration_config: Optional[CEFIntegrationConfig] = None,
) -> Tuple[CEFSessionDetector, CEFIntegrationConfig]:
    """Create a (session_detector, integration_config) pair.

    This is the smallest-viable install: one line, one detector,
    one config. The caller owns the session detector and threads
    it through the loop.

    Parameters
    ----------
    session_config : Optional[CEFSessionConfig]
        The session config. None uses defaults from CEFSessionConfig.
    integration_config : Optional[CEFIntegrationConfig]
        The integration config. None uses defaults.

    Returns
    -------
    Tuple[CEFSessionDetector, CEFIntegrationConfig]
        The session detector and the integration config. Both are
        caller-owned.
    """
    s_cfg = session_config or CEFSessionConfig()
    i_cfg = integration_config or CEFIntegrationConfig()
    detector = create_cef_session_detector(s_cfg)
    return detector, i_cfg
