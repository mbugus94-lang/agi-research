"""Teachability Score - longitudinal safety as an epistemic property.

Background
----------
The ICML 2026 position paper "Agentic Safety is an Epistemic Property, Not
a Behavioral One" (OpenReview 30mapdhNKH) argues that safety should be
measured as the system's ability to *remain teachable* over time -- not
just whether its current policy behaves acceptably. The key claim:

    "Systems can remain ostensibly competent while eroding the conditions
     needed for future correction, making static evaluations insufficient."

For our CEF substrate, "teachability" reduces to measurable questions:

1. **Recovery responsiveness** - when the bound trips and the operator
   intervenes (e.g. by removing the bad action), how fast does the bound
   come back down to safe? A substrate that bounces back in 1-2 probes
   is *more teachable* than one that stays tripped for 100 observations.

2. **Intervention friction** - how much operator effort is required to
   cause a measurable shift in the bound? If removing one bad action
   moves the bound by 0.01 but you need 100 such actions to bring it
   under threshold, the operator's corrective leverage is small.

3. **Audit trail completeness** - does the substrate record *who*
   intervened, *when*, and *what changed*? Without this trail, future
   operators cannot learn from past interventions, which is the
   longitudinal component of teachability.

4. **Chatter resistance** - does the substrate avoid spurious recovery
   transitions that would erode operator trust? A gate that flutters
   between CLOSED and OPEN makes operators stop trusting the signal.

This module defines ``TeachabilityScore`` -- a small dataclass that
combines four sub-scores into one ``teachability`` number in [0, 1],
along with the per-component breakdown for audit.

Score interpretation
--------------------
- ``teachability >= 0.8``  : excellent -- substrate is easy to teach,
  audit trail is rich, recovery is fast.
- ``0.5 <= teachability < 0.8`` : acceptable -- operator can teach the
  substrate, but with friction.
- ``teachability < 0.5``  : poor -- the substrate has lost most of its
  corrective leverage; recommend a manual review and possibly a fresh
  engine.

Design choices
--------------
* Pure functions over gate state. No network, no model, no side effects.
* Score is computed from a ``GovernorCircuit`` and an optional audit log.
* All inputs are public API of ``GovernorCircuit`` (state, summary,
  transitions). No internal-state peeking that breaks the contract.
* Audit log entries may carry an optional ``intervention`` field with
  operator metadata; the score credits interventions if they appear.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Sub-scores.
# ---------------------------------------------------------------------------


def recovery_responsiveness(
    transition_count: int,
    recovery_count: int,
    *,
    expected_recoveries: Optional[int] = None,
) -> float:
    """Score recovery responsiveness in [0, 1].

    A recovery is any OPEN->HALF_OPEN or HALF_OPEN->CLOSED transition.
    A "fully-taught" substrate has at least one recovery per ~5
    transitions that touch an elevated state. If we see recovery_count
    recoveries among transition_count transitions, the score is

        min(1.0, recovery_count / expected_recoveries)

    where ``expected_recoveries`` defaults to ``max(1, transition_count // 5)``.

    Parameters
    ----------
    transition_count : int
        Total state transitions observed in the window.
    recovery_count : int
        Transitions that closed or half-opened the gate (recovery events).
    expected_recoveries : int, optional
        Operator's prior on how many recoveries they expect. Default
        ``max(1, transition_count // 5)``.

    Returns
    -------
    float
        Score in [0, 1]. 1.0 means the substrate recovered exactly as
        often as expected; 0.0 means no recoveries seen at all.
    """
    if transition_count <= 0:
        # No transitions yet: the substrate is "indeterminate" -- give it
        # a neutral mid-score so the overall score doesn't bias too hard.
        return 0.5
    if expected_recoveries is None:
        expected_recoveries = max(1, transition_count // 5)
    if expected_recoveries <= 0:
        return 1.0
    ratio = recovery_count / expected_recoveries
    return max(0.0, min(1.0, ratio))


def intervention_friction(
    audit_records: Sequence[Dict[str, Any]],
) -> float:
    """Score how much operator intervention has changed the bound.

    For each ``intervention`` record in the audit log, we look at the
    ``pre_bound`` and ``post_bound`` fields (optional) and credit the
    operator with the magnitude of the drop. Friction is high (score low)
    when interventions don't move the bound; friction is low (score high)
    when a single intervention shifts the bound substantially.

    Score = clip( mean( (pre - post) / max(pre, epsilon) ), 0, 1 )

    If no intervention records carry both ``pre_bound`` and ``post_bound``,
    return 0.5 (indeterminate).

    Parameters
    ----------
    audit_records : sequence of dict
        The audit log lines, each a dict.

    Returns
    -------
    float
        Score in [0, 1].
    """
    drops: List[float] = []
    for rec in audit_records:
        if not isinstance(rec, dict):
            continue
        if rec.get("intervention") is not True:
            continue
        pre = rec.get("pre_bound")
        post = rec.get("post_bound")
        if not isinstance(pre, (int, float)) or not isinstance(post, (int, float)):
            continue
        if pre <= 0:
            continue
        drops.append(max(0.0, (pre - post) / pre))
    if not drops:
        return 0.5
    mean_drop = sum(drops) / len(drops)
    return max(0.0, min(1.0, mean_drop))


def audit_trail_completeness(audit_records: Sequence[Dict[str, Any]]) -> float:
    """Score the audit trail's richness in [0, 1].

    We grade on three axes (each in [0, 1]):

    - ``has_timestamp``     : does every record carry a timestamp?
    - ``has_reason``        : does every record carry a reason?
    - ``has_layer_metadata``: does every record identify the layer?

    Final score is the unweighted mean.

    Parameters
    ----------
    audit_records : sequence of dict
        The audit log lines.

    Returns
    -------
    float
        Score in [0, 1]. 0.5 (indeterminate) when no records exist.
    """
    if not audit_records:
        return 0.5
    n = len(audit_records)
    has_ts = sum(1 for r in audit_records if isinstance(r, dict) and "timestamp" in r)
    has_reason = sum(
        1
        for r in audit_records
        if isinstance(r, dict) and r.get("reason") not in (None, "")
    )
    has_layer = sum(
        1 for r in audit_records if isinstance(r, dict) and "layer" in r
    )
    return ((has_ts + has_reason + has_layer) / (3 * n))


def chatter_resistance(
    transitions: Sequence[Any],
    *,
    horizon: int = 200,
) -> float:
    """Score chatter resistance in [0, 1].

    Chatter is repeated CLOSED <-> OPEN oscillation that erodes operator
    trust. We grade by counting state-direction reversals in the last
    ``horizon`` transitions. A perfectly teachable substrate has zero
    reversals.

    Score = max(0.0, 1.0 - reversals / horizon)

    Parameters
    ----------
    transitions : sequence
        The gate's transition log. Each element is expected to expose
        ``from_state`` and ``to_state`` attributes (matching the
        ``GateTransition`` dataclass) or be a dict with those keys.
    horizon : int
        How many recent transitions to inspect. Default 200.

    Returns
    -------
    float
        Score in [0, 1]. 0.5 when the transition log is empty.
    """
    if not transitions:
        return 0.5
    recent = transitions[-horizon:]
    reversals = 0
    prev_state: Optional[str] = None
    for t in recent:
        if hasattr(t, "from_state"):
            cur_from = t.from_state.value if hasattr(t.from_state, "value") else str(t.from_state)
        elif isinstance(t, dict):
            cur_from = t.get("from_state", "")
        else:
            continue
        cur_from = str(cur_from)
        if prev_state is not None and cur_from != prev_state:
            # A reversal is a transition whose ``from_state`` differs from
            # the previous transition's ``from_state`` -- i.e. we just
            # changed direction.
            reversals += 1
        prev_state = cur_from
    return max(0.0, 1.0 - (reversals / horizon))


# ---------------------------------------------------------------------------
# Combined score.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TeachabilityScore:
    """Combined longitudinal safety score for the CEF substrate.

    Attributes
    ----------
    recovery : float
        Sub-score for recovery responsiveness in [0, 1].
    friction : float
        Sub-score for intervention friction in [0, 1].
    audit : float
        Sub-score for audit-trail completeness in [0, 1].
    chatter : float
        Sub-score for chatter resistance in [0, 1].
    teachability : float
        Weighted geometric mean of the four sub-scores, in [0, 1].
    intervention_count : int
        How many operator interventions were observed.
    recovery_count : int
        How many recovery transitions were observed.
    transition_count : int
        Total transitions inspected.
    notes : list of str
        Human-readable observations about the score.
    """

    recovery: float
    friction: float
    audit: float
    chatter: float
    teachability: float
    intervention_count: int = 0
    recovery_count: int = 0
    transition_count: int = 0
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "teachability": self.teachability,
            "components": {
                "recovery": self.recovery,
                "friction": self.friction,
                "audit": self.audit,
                "chatter": self.chatter,
            },
            "intervention_count": self.intervention_count,
            "recovery_count": self.recovery_count,
            "transition_count": self.transition_count,
            "notes": list(self.notes),
        }

    def band(self) -> str:
        """A discrete band for dashboards."""
        if self.teachability >= 0.8:
            return "excellent"
        if self.teachability >= 0.5:
            return "acceptable"
        return "poor"


# Weights chosen so a missing-input score (0.5) on one axis pulls the
# overall score toward 0.71 rather than 1.0. The geometric mean is
# conservative against optimistic inputs (it punishes zeros).
_WEIGHTS = {
    "recovery": 0.30,
    "friction": 0.20,
    "audit": 0.20,
    "chatter": 0.30,
}


def _safe_log(score: float) -> float:
    if score <= 0:
        # log(0) is -inf, which collapses the geometric mean. Treat a true
        # zero as "epsilon" so we still get a finite (low) score.
        return math.log(1e-9)
    return math.log(score)


def compute_teachability(
    *,
    transitions: Sequence[Any],
    audit_records: Optional[Sequence[Dict[str, Any]]] = None,
    recovery_count: Optional[int] = None,
    transition_count: Optional[int] = None,
    chatter_horizon: int = 200,
) -> TeachabilityScore:
    """Compute the combined ``TeachabilityScore`` for a gate.

    Parameters
    ----------
    transitions : sequence
        The gate's transition log (GateTransition dataclasses or dicts).
    audit_records : sequence of dict, optional
        Audit log lines for intervention-friction and audit-completeness
        scoring. Defaults to empty.
    recovery_count : int, optional
        Override for recovery-event count. By default we count
        OPEN->HALF_OPEN or HALF_OPEN->CLOSED transitions ourselves.
    transition_count : int, optional
        Override for transition-count. By default we use
        ``len(transitions)``.
    chatter_horizon : int
        How many recent transitions to inspect for chatter. Default 200.

    Returns
    -------
    TeachabilityScore
    """
    audit_records = audit_records or []
    if transition_count is None:
        transition_count = len(transitions)
    if recovery_count is None:
        rec_count = 0
        for t in transitions:
            if hasattr(t, "to_state"):
                to_state = t.to_state.value if hasattr(t.to_state, "value") else str(t.to_state)
                from_state = t.from_state.value if hasattr(t.from_state, "value") else str(t.from_state)
            elif isinstance(t, dict):
                to_state = str(t.get("to_state", ""))
                from_state = str(t.get("from_state", ""))
            else:
                continue
            # Recovery = either OPEN -> HALF_OPEN or HALF_OPEN -> CLOSED.
            # Compare case-insensitively so we work on both real
            # GateTransition dataclasses (lower-case values) and
            # dict-imported JSONL (might be upper-case).
            fs = (from_state or "").lower()
            ts = (to_state or "").lower()
            if fs == "open" and ts == "half_open":
                rec_count += 1
            elif fs == "half_open" and ts == "closed":
                rec_count += 1
        recovery_count = rec_count

    rec = recovery_responsiveness(transition_count, recovery_count)
    fric = intervention_friction(audit_records)
    aud = audit_trail_completeness(audit_records)
    chat = chatter_resistance(transitions, horizon=chatter_horizon)

    intervention_count = sum(
        1 for r in audit_records if isinstance(r, dict) and r.get("intervention") is True
    )

    # Weighted geometric mean (penalises low outliers).
    log_sum = (
        _WEIGHTS["recovery"] * _safe_log(rec)
        + _WEIGHTS["friction"] * _safe_log(fric)
        + _WEIGHTS["audit"] * _safe_log(aud)
        + _WEIGHTS["chatter"] * _safe_log(chat)
    )
    teachability = math.exp(log_sum)

    notes: List[str] = []
    if rec < 0.4:
        notes.append("Recovery responsiveness is low -- check recovery churn.")
    if fric < 0.4:
        notes.append(
            "Intervention friction is high -- operator interventions "
            "are not moving the bound. Consider stricter priors or "
            "audit-trail intervention records."
        )
    if aud < 0.6:
        notes.append(
            "Audit trail is sparse -- add timestamps, reasons, and "
            "layer ids to every transition."
        )
    if chat < 0.6:
        notes.append(
            "Chatter is high -- the gate is flapping. Tighten the gap "
            "between trip_threshold and reset_threshold."
        )
    if not notes:
        notes.append("All sub-scores are healthy.")

    return TeachabilityScore(
        recovery=rec,
        friction=fric,
        audit=aud,
        chatter=chat,
        teachability=teachability,
        intervention_count=intervention_count,
        recovery_count=recovery_count,
        transition_count=transition_count,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Convenience: score from a GovernorCircuit directly.
# ---------------------------------------------------------------------------


def teachability_from_circuit(
    circuit: Any,
    *,
    audit_records: Optional[Sequence[Dict[str, Any]]] = None,
    chatter_horizon: int = 200,
) -> TeachabilityScore:
    """Compute the score directly from a ``GovernorCircuit`` instance.

    The circuit must expose ``to_dict()`` (the canonical public surface),
    which carries ``transitions`` and summary fields. Audit records are
    passed separately.
    """
    d = circuit.to_dict() if hasattr(circuit, "to_dict") else {}
    transitions = d.get("transitions", [])
    return compute_teachability(
        transitions=transitions,
        audit_records=audit_records,
        chatter_horizon=chatter_horizon,
    )


__all__ = [
    "TeachabilityScore",
    "audit_trail_completeness",
    "chatter_resistance",
    "compute_teachability",
    "intervention_friction",
    "recovery_responsiveness",
    "teachability_from_circuit",
]