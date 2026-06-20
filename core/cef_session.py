"""
CEF Session Aggregator -- session-level Constraint-Evasive Fabrication
detection on top of the per-output ``CEFDetector``.

Inspiration
-----------
This module is the direct implementation of the "point of no return"
finding from "Is Your Agent Playing Dead? Deployed LLM Agents Exhibit
Constraint-Evasive Fabrication and Thanatosis" (arXiv:2606.14831,
Rodríguez, Pozanco, Borrajo -- J.P. Morgan AI Research, Jun 12 2026):

    "Importantly, the recovery is only possible when ground truth is
     administered at T5. By T20+, the agent ignores the corrective
     information entirely -- the fabrication has become the
     conversational ground truth."

The per-output ``CEFDetector`` (core/cef_detector.py) flags a single
agent output as a fabrication on the CEFType / CEFSeverity ladder.
That is necessary but not sufficient: a single LOW detection is
*normal* -- an agent that says "I'm sorry, I can't help with that"
once has not started fabricating. The paper's session-level finding
is the load-bearing claim:

  * L5 (3 sealed exits)  averaged  4.67 CEF turns per session
  * L7 (all exits sealed) averaged 17.75 CEF turns per session
  * Once a session crosses the recovery horizon (T20+), the
    agent ignores ground-truth corrections.

This module closes that gap by aggregating per-output detections
across a session and emitting a ``CEFSessionVerdict`` that captures:

  * session CEF turn count
  * session-level severity (the MAX across the window)
  * a **recovery horizon** flag (``point_of_no_return``): once a
    threshold of consecutive or total fabrications is crossed, the
    operator must treat the session as compromised
  * the first detection that crossed the horizon (for audit)
  * a recommended operator action (CONTINUE / WARN / FREEZE /
    RESTART)

Design constraints
------------------
* Pure, deterministic, side-effect free. No I/O. No LLM. No clock
  reads beyond the optional ``turn_index`` carried by each detection.
* Cheap: O(N) in the session length. The per-output CEFDetector is
  O(len(output) * len(patterns)); this aggregator is just a fold
  over the detection stream.
* Configurable: ``CEFSessionConfig`` carries every threshold and the
  underlying ``CEFDetectorConfig``; no module-level constants.
* Conservative posture: aggregation can PROMOTE severity and
  recommendation but never DEMOTE. A single per-output NONE/LOW does
  not cancel a session-level HIGH/CRITICAL.
* The session's ``to_dict`` round-trips for audit; ``first_horizon_id``
  is the substrate for an evidence-ledger claim.

The module does **not** auto-act. It emits a verdict; the caller
(typically ``GovernedActionLoop``) chooses whether to FREEZE the
agent's session, RESTART the principal, or escalate to the operator.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .cef_detector import (
    CEFAction,
    CEFDetection,
    CEFDetector,
    CEFDetectorConfig,
    CEFMarker,
    CEFPattern,
    CEFSeverity,
    CEFType,
    DEFAULT_PATTERNS,
    create_cef_detector,
)


# ---------------------------------------------------------------------------
# Session-level enums
# ---------------------------------------------------------------------------


class CEFSessionState(str, Enum):
    """The session-level state of an agent's fabrication trajectory.

    CLEAN              -- no CEF detections observed in the window
    EARLY              -- 1-2 fabrications observed; below the warn threshold
    WARNING            -- fabrications above the warn threshold but below the
                          recovery horizon
    POINT_OF_NO_RETURN -- fabrications have crossed the recovery horizon;
                          operator MUST treat the session as compromised
                          (paper's T20+ finding)
    """

    CLEAN = "clean"
    EARLY = "early"
    WARNING = "warning"
    POINT_OF_NO_RETURN = "point_of_no_return"


class CEFSessionAction(str, Enum):
    """The recommended operator action for a session verdict.

    CONTINUE -- the session is clean or in EARLY; keep observing
    WARN     -- session is in WARNING; surface to the operator
    FREEZE   -- session crossed the horizon; stop the agent's
                principal from issuing more actions until reviewed
    RESTART  -- session crossed the horizon AND the most recent
                detection is CRITICAL; the principal should be
                re-instantiated
    """

    CONTINUE = "continue"
    WARN = "warn"
    FREEZE = "freeze"
    RESTART = "restart"


# ---------------------------------------------------------------------------
# Session config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CEFSessionConfig:
    """All thresholds the session aggregator needs.

    Attributes
    ----------
    detector_config : CEFDetectorConfig
        The per-output detector config. Operators extend the pattern
        catalogue here; the session aggregator inherits the patterns.
    warn_total_threshold : int
        Total non-NONE fabrications that flips the session from
        EARLY -> WARNING. Default 3 (matches the paper's "3
        consecutive fabricated Python exceptions" CET incident).
    warn_consecutive_threshold : int
        Consecutive non-NONE fabrications that flips the session
        from EARLY -> WARNING. Default 2 (the paper's "two or more
        strong markers co-occurring" macro invariant).
    horizon_total_threshold : int
        Total non-NONE fabrications that flips the session from
        WARNING -> POINT_OF_NO_RETURN. Default 20 (paper's T20+
        recovery horizon). Conservative operators may lower this.
    horizon_consecutive_threshold : int
        Consecutive non-NONE fabrications that flips the session
        from WARNING -> POINT_OF_NO_RETURN. Default 5 (paper's
        T5 recovery boundary).
    require_severity_floor : CEFSeverity
        The minimum severity a detection must reach to be counted
        toward the session's thresholds. Default LOW (any
        fabrication counts). Operators can raise this to MEDIUM to
        ignore VAGUE_EXCUSE-only sessions.
    """

    detector_config: CEFDetectorConfig = field(default_factory=CEFDetectorConfig)
    warn_total_threshold: int = 3
    warn_consecutive_threshold: int = 2
    horizon_total_threshold: int = 20
    horizon_consecutive_threshold: int = 5
    require_severity_floor: CEFSeverity = CEFSeverity.LOW


# ---------------------------------------------------------------------------
# Session verdict
# ---------------------------------------------------------------------------


@dataclass
class CEFSessionVerdict:
    """The aggregated session-level fabrication verdict.

    Attributes
    ----------
    session_id : str
        Caller-supplied session identifier (typically the agent's
        principal id).
    total_outputs : int
        Number of per-output detections fed into the aggregator.
    fabrication_count : int
        Number of detections at or above ``require_severity_floor``.
    consecutive_fabrications : int
        Length of the trailing consecutive-fabrication run (resets
        to 0 on a CLEAN detection).
    peak_severity : CEFSeverity
        The MAX severity observed across the window.
    peak_type : CEFType
        The CEFType that produced the peak severity (NONE if clean).
    state : CEFSessionState
        The session-level state after aggregation.
    action : CEFSessionAction
        The recommended operator action.
    first_horizon_id : Optional[str]
        The ``detection_id`` of the first detection that crossed
        the recovery horizon. None if the session has not crossed.
    first_horizon_turn : Optional[int]
        The turn index of the first horizon-crossing detection.
        None if the session has not crossed.
    rationale : str
        Human-readable explanation of the state + action.
    verdict_id : str
        Deterministic UUID for audit.
    verdict_at : str
        ISO-8601 UTC timestamp.
    session_digest : str
        SHA-256 of the concatenated detection_ids (content-addressed).
    """

    session_id: str
    total_outputs: int
    fabrication_count: int
    consecutive_fabrications: int
    peak_severity: CEFSeverity
    peak_type: CEFType
    state: CEFSessionState
    action: CEFSessionAction
    first_horizon_id: Optional[str]
    first_horizon_turn: Optional[int]
    rationale: str
    verdict_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    verdict_at: str = field(
        default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )
    session_digest: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "total_outputs": self.total_outputs,
            "fabrication_count": self.fabrication_count,
            "consecutive_fabrications": self.consecutive_fabrications,
            "peak_severity": self.peak_severity.value,
            "peak_type": self.peak_type.value,
            "state": self.state.value,
            "action": self.action.value,
            "first_horizon_id": self.first_horizon_id,
            "first_horizon_turn": self.first_horizon_turn,
            "rationale": self.rationale,
            "verdict_id": self.verdict_id,
            "verdict_at": self.verdict_at,
            "session_digest": self.session_digest,
        }

    def is_compromised(self) -> bool:
        """True iff the session has crossed the recovery horizon."""
        return self.state == CEFSessionState.POINT_OF_NO_RETURN


# ---------------------------------------------------------------------------
# Session detector
# ---------------------------------------------------------------------------


class CEFSessionDetector:
    """Aggregates per-output ``CEFDetection``s into a ``CEFSessionVerdict``.

    The detector is **stateful**: ``observe(detection)`` folds a new
    detection into the running session state and returns the new
    verdict. ``observe_stream(detections)`` is the convenience wrapper
    for the full window.

    The detector itself is cheap (a single fold); the expensive
    per-output work is delegated to ``CEFDetector``. This module's
    contribution is the *aggregation policy*:

      1. Filter: drop detections below ``require_severity_floor``.
      2. Count: increment ``fabrication_count``; reset
         ``consecutive_fabrications`` on a CLEAN detection.
      3. Track peak: ``peak_severity`` = MAX over the window; track
         the producing ``peak_type``.
      4. Horizon check: if total or consecutive fabrications have
         crossed the recovery-horizon thresholds, transition to
         ``POINT_OF_NO_RETURN`` and capture the crossing detection.
      5. Map state -> action: RESTART if both compromised AND
         peak is CRITICAL; otherwise FREEZE for compromised; WARN
         for WARNING; CONTINUE for CLEAN/EARLY.
      6. Emit rationale: short human-readable string describing the
         triggering threshold + peak.

    The detector never auto-acts. The caller chooses what to do with
    the verdict.
    """

    def __init__(self, config: Optional[CEFSessionConfig] = None) -> None:
        self._config = config or CEFSessionConfig()
        self._reset_state()

    def _reset_state(self) -> None:
        self._total_outputs: int = 0
        self._fabrication_count: int = 0
        self._consecutive: int = 0
        self._peak_severity: CEFSeverity = CEFSeverity.NONE
        self._peak_type: CEFType = CEFType.NONE
        self._first_horizon_id: Optional[str] = None
        self._first_horizon_turn: Optional[int] = None
        self._detection_ids: List[str] = []

    @property
    def config(self) -> CEFSessionConfig:
        return self._config

    def _passes_floor(self, detection: CEFDetection) -> bool:
        return detection.severity.value >= self._config.require_severity_floor.value

    def observe(
        self,
        detection: CEFDetection,
        turn_index: Optional[int] = None,
    ) -> CEFSessionVerdict:
        """Fold a single per-output detection into the session.

        Parameters
        ----------
        detection : CEFDetection
            The per-output CEFDetector result.
        turn_index : Optional[int]
            The turn number (0-based or 1-based, caller-defined).
            Used only to populate ``first_horizon_turn`` on the
            verdict when the horizon is crossed.
        """
        self._total_outputs += 1
        self._detection_ids.append(detection.detection_id)

        if not self._passes_floor(detection):
            # Below the floor: this is a "clean" beat, reset the
            # consecutive run but do not promote the peak.
            self._consecutive = 0
            return self._build_verdict()

        # Fabrication beat.
        self._fabrication_count += 1
        self._consecutive += 1

        if detection.severity.value > self._peak_severity.value:
            self._peak_severity = detection.severity
            self._peak_type = detection.cef_type

        # Horizon check: capture the FIRST crossing detection.
        if self._first_horizon_id is None and self._crossed_horizon():
            self._first_horizon_id = detection.detection_id
            self._first_horizon_turn = turn_index

        return self._build_verdict()

    def observe_stream(
        self,
        detections: Iterable[CEFDetection],
        turn_indices: Optional[Iterable[Optional[int]]] = None,
    ) -> CEFSessionVerdict:
        """Fold a full stream of detections; return the final verdict.

        Parameters
        ----------
        detections : Iterable[CEFDetection]
            The session's per-output detections in order.
        turn_indices : Optional[Iterable[Optional[int]]]
            Parallel iterable of turn numbers. None means "no turn
            info" (every detection's first_horizon_turn will be None).
        """
        if turn_indices is None:
            for det in detections:
                self.observe(det, turn_index=None)
        else:
            for det, idx in zip(detections, turn_indices):
                self.observe(det, turn_index=idx)
        return self._build_verdict()

    def reset(self) -> None:
        """Reset the session state. The detector instance is reusable."""
        self._reset_state()

    # -- internal ---------------------------------------------------------

    def _crossed_horizon(self) -> bool:
        return (
            self._fabrication_count >= self._config.horizon_total_threshold
            or self._consecutive >= self._config.horizon_consecutive_threshold
        )

    def _crossed_warn(self) -> bool:
        return (
            self._fabrication_count >= self._config.warn_total_threshold
            or self._consecutive >= self._config.warn_consecutive_threshold
        )

    def _derive_state(self) -> CEFSessionState:
        if self._total_outputs == 0:
            return CEFSessionState.CLEAN
        if self._fabrication_count == 0:
            # Outputs observed, none above the floor -> still CLEAN.
            return CEFSessionState.CLEAN
        if self._crossed_horizon():
            return CEFSessionState.POINT_OF_NO_RETURN
        if self._crossed_warn():
            return CEFSessionState.WARNING
        return CEFSessionState.EARLY

    def _derive_action(self, state: CEFSessionState) -> CEFSessionAction:
        if state == CEFSessionState.POINT_OF_NO_RETURN:
            # RESTART only if the peak was CRITICAL (CET-style).
            # Otherwise FREEZE -- the agent's outputs are
            # fabrications but the session may still recover.
            if self._peak_severity == CEFSeverity.CRITICAL:
                return CEFSessionAction.RESTART
            return CEFSessionAction.FREEZE
        if state == CEFSessionState.WARNING:
            return CEFSessionAction.WARN
        return CEFSessionAction.CONTINUE

    def _derive_rationale(self, state: CEFSessionState) -> str:
        if state == CEFSessionState.POINT_OF_NO_RETURN:
            reason_parts = []
            if self._fabrication_count >= self._config.horizon_total_threshold:
                reason_parts.append(
                    f"total_fabrications={self._fabrication_count} "
                    f">= horizon_total={self._config.horizon_total_threshold}"
                )
            if self._consecutive >= self._config.horizon_consecutive_threshold:
                reason_parts.append(
                    f"consecutive_fabrications={self._consecutive} "
                    f">= horizon_consecutive={self._config.horizon_consecutive_threshold}"
                )
            peak_note = (
                f"; peak_severity={self._peak_severity.value}"
                f" peak_type={self._peak_type.value}"
            )
            return (
                "point_of_no_return: " + "; ".join(reason_parts) + peak_note
            )
        if state == CEFSessionState.WARNING:
            reason_parts = []
            if self._fabrication_count >= self._config.warn_total_threshold:
                reason_parts.append(
                    f"total_fabrications={self._fabrication_count} "
                    f">= warn_total={self._config.warn_total_threshold}"
                )
            if self._consecutive >= self._config.warn_consecutive_threshold:
                reason_parts.append(
                    f"consecutive_fabrications={self._consecutive} "
                    f">= warn_consecutive={self._config.warn_consecutive_threshold}"
                )
            return "warning: " + "; ".join(reason_parts)
        if state == CEFSessionState.EARLY:
            return (
                f"early: fabrication_count={self._fabrication_count} "
                f"consecutive={self._consecutive} (below warn thresholds)"
            )
        return "clean: no fabrications observed"

    def _digest(self) -> str:
        h = hashlib.sha256()
        for did in self._detection_ids:
            h.update(did.encode("utf-8"))
            h.update(b"|")
        return h.hexdigest()

    def _build_verdict(self) -> CEFSessionVerdict:
        state = self._derive_state()
        action = self._derive_action(state)
        rationale = self._derive_rationale(state)
        digest = self._digest()
        return CEFSessionVerdict(
            session_id="",  # set by the caller via the verdict's session_id field
            total_outputs=self._total_outputs,
            fabrication_count=self._fabrication_count,
            consecutive_fabrications=self._consecutive,
            peak_severity=self._peak_severity,
            peak_type=self._peak_type,
            state=state,
            action=action,
            first_horizon_id=self._first_horizon_id,
            first_horizon_turn=self._first_horizon_turn,
            rationale=rationale,
            session_digest=digest,
        )


# ---------------------------------------------------------------------------
# Convenience: detect session from raw outputs
# ---------------------------------------------------------------------------


def detect_cef_session(
    session_id: str,
    outputs: Iterable[str],
    config: Optional[CEFSessionConfig] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Tuple[List[CEFDetection], CEFSessionVerdict]:
    """End-to-end convenience: run per-output CEF detection on each
    output, then aggregate into a session verdict.

    Parameters
    ----------
    session_id : str
        The session identifier.
    outputs : Iterable[str]
        The agent's per-turn outputs in order.
    config : Optional[CEFSessionConfig]
        Session config (carries the per-output detector config too).
    context : Optional[Dict[str, Any]]
        Context dict forwarded to every ``CEFDetector.detect`` call.

    Returns
    -------
    (detections, verdict) : Tuple[List[CEFDetection], CEFSessionVerdict]
        The per-output detections (so the caller can record them
        individually) and the aggregated session verdict.
    """
    cfg = config or CEFSessionConfig()
    detector = create_cef_detector(cfg.detector_config)
    aggregator = CEFSessionDetector(cfg)
    detections: List[CEFDetection] = []
    for i, output in enumerate(outputs):
        det = detector.detect(output, context or {})
        detections.append(det)
        aggregator.observe(det, turn_index=i)
    verdict = aggregator._build_verdict()
    verdict.session_id = session_id
    return detections, verdict


# ---------------------------------------------------------------------------
# Convenience: smallest viable install
# ---------------------------------------------------------------------------


def create_cef_session_detector(
    config: Optional[CEFSessionConfig] = None,
) -> CEFSessionDetector:
    """Smallest viable install: 1 line."""
    return CEFSessionDetector(config or CEFSessionConfig())
