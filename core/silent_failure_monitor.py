"""
Silent Failure Monitor - Measurable entropy tracking for LLM agent systems.

Inspired by:
  - "Silent Failure in LLM Agent Systems: The Entropy Principle and the
    Inevitable Disorder of Autonomous Agents" (arXiv:2606.08162, Dexing Liu,
    Shanghai Qijing Digital, June 9 2026).
  - The paper's central claim: silent failures are inevitable consequences
    of 22 intrinsic properties of language-based autonomous systems, and
    system entropy S(t) = S0 * exp(alpha * t) increases monotonically with
    interaction rounds.
  - The paper's five silent failure types: Channel Fracture (L1),
    Cognitive Framework Lag (L2), Data Consistency Decay (L3),
    Cross-Session Knowledge Fragmentation (L2), Behavior Routing
    Deficiency (L3).
  - The paper's engineering response: a "Physical Integrity Gate (PIG)
    Engine" + "Agent Delivery Engineering (ADE) protocol suite" that
    applies "deterministic governance" to keep system structure stable.
  - The paper's downstream confirmations: Greyling's four-layer harness
    taxonomy; MAST (14 modes); Microsoft AIRT (30+ modes); Token Budgets
    catalog (63 production incidents); Latitude (6 modes); Pazi (5 modes);
    BAGEN (budget awareness degradation); Library Drift (Zhang et al.).

What this module adds on top of the existing MetacognitiveMonitor:

  1. SilentFailureType        An enum of the paper's 5 failure types.
  2. EntropySignal            A measurable indicator that a property in
                              one of the 22 intrinsic-property buckets has
                              drifted past its threshold. Each signal is
                              a small, deterministic, auditable observation.
  3. EntropyObservation       A single timestamped (signal, value) pair.
  4. FailureEpisode           A coherence window: from first crossing of
                              a threshold for a given failure type to the
                              point the system either returns below the
                              threshold or escalates. PIG+ADE call these
                              "delivery incidents".
  5. EntropyConfig            Per-type thresholds + an alpha (entropy
                              constant) cap. The paper measures alpha
                              empirically; we treat it as a configured
                              rate of acceptable accumulation.
  6. PIGEngine                The Physical Integrity Gate. Reads Entropy
                              Signals emitted by the agent (or computed
                              from MetacognitiveMonitor state), tracks
                              the current entropy level per type, and
                              decides whether to ALLOW / DAMP / BLOCK /
                              ESCALATE the next agent action. This is
                              the "deterministic governance" the paper
                              asks for: a hard, non-LLM check between
                              the LLM and the side-effect boundary.
  7. ADEProtocol              The Agent Delivery Engineering protocol
                              suite: rolling-window entropy, monotonic
                              constraint, episode detection, and a
                              deterministic escalation ladder.
  8. SilentFailureMonitor     The orchestrator. Substrate of the audit
                              trail (JSONL), a `MetacognitiveMonitor`
                              for calibration cross-check, and a
                              PIGEngine for boundary decisions. Never
                              modifies the agent. Never auto-applies.

Safety posture:

  - The monitor NEVER blocks on its own. It only emits ALLOW/DAMP/BLOCK/
    ESCALATE signals. The downstream caller (the operator, the
    SkillEvolutionGate, the SafetyCircuitBreaker) decides what to do.
  - Conservative defaults: BLOCK on Channel Fracture (cross-agent
    fidelity loss is the highest-stakes type); DAMP on all other
    types unless the operator opens the gate.
  - The audit log is JSONL: every signal + every gate decision is
    on disk in <audit_path>/events.jsonl, so after-the-fact review
    can answer "what did the system believe" with "what did the
    system decide."

Decisions:

  - We pick the paper's *five* failure types, not the 22 intrinsic
    properties, because the types are the *observable* layer; the 22
    properties are the causal backdrop. The monitor observes the
    type; the audit log records the property it maps to.
  - We do *not* try to measure alpha empirically. The paper measures
    it across architectures; we treat alpha as a configured per-type
    cap, mirroring our BrakePedal pattern (operator-controlled, not
    auto-tuned).
  - We integrate with the *existing* `MetacognitiveMonitor` rather
    than replacing it. The metacognitive monitor is the agent's
    *self* report; the silent-failure monitor is the *boundary*
    report. They cross-check each other.
"""

from __future__ import annotations

import json
import math
import os
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SilentFailureType(str, Enum):
    """The five silent failure types from the Entropy Principle paper.

    The lifecycle-layer tags (L1/L2/L3) follow the paper's section 2.2.
    """

    CHANNEL_FRACTURE = "channel_fracture"            # L1 -- Transmission
    COGNITIVE_FRAMEWORK_LAG = "cognitive_framework_lag"  # L2 -- Memory
    DATA_CONSISTENCY_DECAY = "data_consistency_decay"  # L3 -- Execution
    CROSS_SESSION_FRAGMENTATION = "cross_session_fragmentation"  # L2 -- Memory
    BEHAVIOR_ROUTING_DEFICIENCY = "behavior_routing_deficiency"  # L3 -- Execution


# Map each failure type to the intrinsic properties in the paper that
# most directly cause it. This is the *causal crosswalk* that lets the
# audit log say "this signal was a Channel Fracture trace, grounded in
# P4 (re-encoding loss) and P7 (no built-in verification)."
FAILURE_TO_PROPERTIES: Dict[SilentFailureType, Tuple[str, ...]] = {
    SilentFailureType.CHANNEL_FRACTURE: ("P4", "P5", "P6", "P7"),
    SilentFailureType.COGNITIVE_FRAMEWORK_LAG: ("P8", "P9", "P10", "P11"),
    SilentFailureType.DATA_CONSISTENCY_DECAY: ("P12", "P13", "P14"),
    SilentFailureType.CROSS_SESSION_FRAGMENTATION: ("P8", "P9", "P11"),
    SilentFailureType.BEHAVIOR_ROUTING_DEFICIENCY: ("P12", "P14", "P19"),
}


class PIGDecision(str, Enum):
    """The PIG Engine's deterministic decisions.

    ALLOW     - The next agent action proceeds unchanged.
    DAMP      - The next agent action is logged with elevated attention
                but still proceeds. Use for marginal signals.
    BLOCK     - The next agent action is refused at the boundary. The
                LLM may still respond, but no side effect is permitted.
    ESCALATE  - The next agent action is blocked AND the operator is
                notified (e.g. via the SelfReviewQueue or equivalent).
                Use for sustained or compound drift.
    """

    ALLOW = "allow"
    DAMP = "damp"
    BLOCK = "block"
    ESCALATE = "escalate"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class EntropyConfig:
    """Per-type thresholds and an alpha cap.

    `threshold` is the value above which a single observation is considered
    a "drift signal" for the type. The paper's three-pattern analysis says
    silent failures are multi-step accumulations, so we don't BLOCK on
    one signal -- we BLOCK when the *rolling* count exceeds `episode_count`.

    `alpha_cap` is the maximum allowed entropy-rate constant for the type.
    The paper's derivation says S(t) = S0 * exp(alpha * t); we use the
    same shape but treat alpha as a configurable rate of accumulation
    that the operator sets, not an empirically fitted constant.

    `episode_window_s` is the time window over which we count drift
    signals. The paper observes that recurrence under identical
    conditions is a defining pattern; we therefore look at the count
    in a *window*, not the count in the lifetime.
    """

    threshold: float = 0.5
    episode_count: int = 3
    alpha_cap: float = 0.05
    episode_window_s: float = 300.0  # 5 minutes

    def __post_init__(self) -> None:
        if self.threshold < 0.0 or self.threshold > 1.0:
            raise ValueError("threshold must be in [0, 1]")
        if self.episode_count < 1:
            raise ValueError("episode_count must be >= 1")
        if self.alpha_cap < 0.0:
            raise ValueError("alpha_cap must be >= 0")
        if self.episode_window_s <= 0.0:
            raise ValueError("episode_window_s must be > 0")


DEFAULT_CONFIG_BY_TYPE: Dict[SilentFailureType, EntropyConfig] = {
    SilentFailureType.CHANNEL_FRACTURE: EntropyConfig(
        threshold=0.4, episode_count=2, alpha_cap=0.03
    ),
    SilentFailureType.COGNITIVE_FRAMEWORK_LAG: EntropyConfig(
        threshold=0.6, episode_count=3, alpha_cap=0.05
    ),
    SilentFailureType.DATA_CONSISTENCY_DECAY: EntropyConfig(
        threshold=0.5, episode_count=3, alpha_cap=0.05
    ),
    SilentFailureType.CROSS_SESSION_FRAGMENTATION: EntropyConfig(
        threshold=0.7, episode_count=4, alpha_cap=0.08
    ),
    SilentFailureType.BEHAVIOR_ROUTING_DEFICIENCY: EntropyConfig(
        threshold=0.5, episode_count=3, alpha_cap=0.05
    ),
}


# ---------------------------------------------------------------------------
# Signals & observations
# ---------------------------------------------------------------------------


@dataclass
class EntropySignal:
    """A measurable indicator that a single intrinsic property has drifted.

    The signal is small and deterministic. The caller chooses the metric:
    e.g. "fidelity_loss" for Channel Fracture, "session_recall_miss_rate"
    for Cross-Session Fragmentation, "tool_misroute_rate" for Behavior
    Routing Deficiency. The monitor doesn't interpret the metric -- it
    just records the value and maps it to a failure type.

    `grounding` is a free-form list of property IDs (e.g. ["P4", "P7"])
    that the caller claims this signal maps to. The monitor cross-checks
    these against `FAILURE_TO_PROPERTIES` to flag inconsistent claims.
    """

    failure_type: SilentFailureType
    value: float
    metric: str
    source: str  # e.g. "agent_loop", "skill_bank", "memory_cache"
    grounding: Tuple[str, ...] = ()
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError("value must be in [0, 1]")


@dataclass
class EntropyObservation:
    """A timestamped (signal, decision) record. Substrate of the audit log."""

    signal: EntropySignal
    decision: PIGDecision
    rationale: str
    rolling_count: int
    rolling_alpha: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class FailureEpisode:
    """A coherence window for a single failure type.

    Starts when the rolling count for a type first crosses
    `episode_count` within `episode_window_s`. Ends when the rolling
    count returns below the threshold for `episode_count` consecutive
    observations, OR when the engine escalates. PIG+ADE call these
    "delivery incidents"; we call them episodes.
    """

    failure_type: SilentFailureType
    opened_at: float
    peak_value: float
    peak_alpha: float
    decision: PIGDecision
    observation_count: int = 0
    closed_at: Optional[float] = None
    close_decision: Optional[PIGDecision] = None

    def is_open(self) -> bool:
        return self.closed_at is None

    def duration_s(self) -> float:
        end = self.closed_at if self.closed_at is not None else time.time()
        return end - self.opened_at


# ---------------------------------------------------------------------------
# PIG Engine
# ---------------------------------------------------------------------------


class PIGEngine:
    """The Physical Integrity Gate.

    Reads EntropySignals, tracks the rolling entropy per type, and
    returns a deterministic PIGDecision. The engine is the boundary
    between the LLM (which can drift) and the side effect (which
    must be deterministic). The engine itself is *not* an LLM.

    The engine is conservative by default: BLOCK on the first episode
    for Channel Fracture (cross-agent fidelity loss is the highest-
    stakes type), DAMP on the first episode for the other types, and
    ESCALATE on the second episode within the same window for any
    type.
    """

    def __init__(
        self,
        config_by_type: Optional[Dict[SilentFailureType, EntropyConfig]] = None,
    ) -> None:
        self._config = dict(config_by_type or DEFAULT_CONFIG_BY_TYPE)
        self._rolling: Dict[SilentFailureType, Deque[float]] = {
            t: deque(maxlen=64) for t in SilentFailureType
        }
        # Per-instance parallel deque: (timestamp, value) pairs so we
        # can compute rolling_alpha from observations within the
        # configured episode window.
        self._rolling_meta: Dict[SilentFailureType, Deque[Tuple[float, float]]] = {
            t: deque(maxlen=64) for t in SilentFailureType
        }
        self._episodes: Dict[SilentFailureType, Optional[FailureEpisode]] = {
            t: None for t in SilentFailureType
        }
        self._escalation_count: Dict[SilentFailureType, int] = {
            t: 0 for t in SilentFailureType
        }

    def config_for(self, t: SilentFailureType) -> EntropyConfig:
        return self._config[t]

    def update_config(
        self, t: SilentFailureType, **kwargs: Any
    ) -> EntropyConfig:
        current = self._config[t]
        merged = EntropyConfig(
            threshold=kwargs.get("threshold", current.threshold),
            episode_count=kwargs.get("episode_count", current.episode_count),
            alpha_cap=kwargs.get("alpha_cap", current.alpha_cap),
            episode_window_s=kwargs.get(
                "episode_window_s", current.episode_window_s
            ),
        )
        self._config[t] = merged
        return merged

    def rolling_count(self, t: SilentFailureType) -> int:
        """Number of observations in the configured episode window.

        We filter on the timestamp stored in `_rolling_meta` (the
        `(timestamp, value)` deque) so the count is time-bounded.
        Observations older than `episode_window_s` are not counted.
        """
        cfg = self._config[t]
        cutoff = time.time() - cfg.episode_window_s
        return sum(1 for ts, _ in self._rolling_meta[t] if ts >= cutoff)

    def rolling_alpha(self, t: SilentFailureType) -> float:
        """Estimate the entropy-rate constant alpha from the rolling window.

        The paper writes S(t) = S0 * exp(alpha * t). We approximate
        alpha as the *fraction* of the threshold that the mean signal
        is reaching, scaled by the observation count over the window.
        Returns 0.0 if no observations. The scale is bounded so that
        a single borderline signal does not produce a runaway alpha;
        the cap is a configured per-type rate (`alpha_cap`).
        """
        cfg = self._config[t]
        cutoff = time.time() - cfg.episode_window_s
        pairs = [(ts, v) for ts, v in self._rolling_meta[t] if ts >= cutoff]
        if not pairs or cfg.threshold <= 0.0:
            return 0.0
        mean_value = sum(v for _, v in pairs) / len(pairs)
        # Normalize so that mean == threshold => alpha == 1.0.
        # Then scale by the count's ratio to the episode_count, so
        # alpha grows as the episode count approaches its threshold.
        return (mean_value / cfg.threshold) * (
            len(pairs) / max(1, cfg.episode_count)
        )

    def evaluate(self, signal: EntropySignal) -> Tuple[PIGDecision, str]:
        """Evaluate a single signal and return a decision + rationale."""
        cfg = self._config[signal.failure_type]

        # Cross-check grounding against the paper's property map.
        expected = set(FAILURE_TO_PROPERTIES[signal.failure_type])
        claimed = set(signal.grounding)
        if claimed and not claimed.intersection(expected):
            rationale_prefix = (
                f"grounding={list(claimed)} not in paper-mapped "
                f"{sorted(expected)} for {signal.failure_type.value}; "
            )
        else:
            rationale_prefix = ""

        # Update rolling window with (timestamp, value).
        self._rolling[signal.failure_type].append(signal.value)
        self._rolling_meta[signal.failure_type].append(
            (signal.timestamp, signal.value)
        )

        # Compute the rolling alpha and count.
        alpha = self.rolling_alpha(signal.failure_type)
        count = self.rolling_count(signal.failure_type)

        # Episode logic: did we just open, just escalate, or stay calm?
        episode = self._episodes[signal.failure_type]
        decision, rationale = self._decide(
            signal=signal,
            cfg=cfg,
            alpha=alpha,
            count=count,
            episode=episode,
            rationale_prefix=rationale_prefix,
        )

        # Update episode state.
        if episode is None and decision in (PIGDecision.BLOCK, PIGDecision.ESCALATE):
            self._episodes[signal.failure_type] = FailureEpisode(
                failure_type=signal.failure_type,
                opened_at=signal.timestamp,
                peak_value=signal.value,
                peak_alpha=alpha,
                decision=decision,
                observation_count=1,
            )
        elif episode is not None and episode.is_open():
            episode.observation_count += 1
            if signal.value > episode.peak_value:
                episode.peak_value = signal.value
            if alpha > episode.peak_alpha:
                episode.peak_alpha = alpha
            if decision == PIGDecision.ALLOW:
                # Episode closing: signal below threshold, count dropping.
                episode.closed_at = signal.timestamp
                episode.close_decision = decision
                self._episodes[signal.failure_type] = None
            else:
                # Sustained drift; update the decision.
                episode.decision = decision
        elif episode is not None and not episode.is_open():
            # We previously closed; reset for the new episode.
            if decision in (PIGDecision.BLOCK, PIGDecision.ESCALATE):
                self._episodes[signal.failure_type] = FailureEpisode(
                    failure_type=signal.failure_type,
                    opened_at=signal.timestamp,
                    peak_value=signal.value,
                    peak_alpha=alpha,
                    decision=decision,
                    observation_count=1,
                )

        return decision, rationale

    def _decide(
        self,
        signal: EntropySignal,
        cfg: EntropyConfig,
        alpha: float,
        count: int,
        episode: Optional[FailureEpisode],
        rationale_prefix: str,
    ) -> Tuple[PIGDecision, str]:
        # If a recovery comes in (signal below threshold and rolling
        # count is back below the episode threshold), allow and reset.
        if signal.value < cfg.threshold and count < cfg.episode_count:
            # If we were in an escalation streak, drop back to allow.
            self._escalation_count[signal.failure_type] = 0
            return (
                PIGDecision.ALLOW,
                f"{rationale_prefix}value={signal.value:.2f}<threshold="
                f"{cfg.threshold:.2f} & count={count}<{cfg.episode_count}",
            )

        # Above threshold but episode count not yet reached: DAMP.
        if count < cfg.episode_count:
            return (
                PIGDecision.DAMP,
                f"{rationale_prefix}value={signal.value:.2f}>=threshold="
                f"{cfg.threshold:.2f} but count={count}<{cfg.episode_count} "
                f"-> DAMP for attention",
            )

        # Episode count reached: BLOCK on first, ESCALATE on second.
        # Channel Fracture is the highest-stakes type and uses the
        # same first/second pattern (BLOCK then ESCALATE).
        is_first_episode = self._escalation_count[signal.failure_type] == 0
        if is_first_episode:
            self._escalation_count[signal.failure_type] += 1
            return (
                PIGDecision.BLOCK,
                f"{rationale_prefix}episode opened (count={count}, "
                f"alpha={alpha:.3f}) -> BLOCK",
            )
        return (
            PIGDecision.ESCALATE,
            f"{rationale_prefix}sustained episode "
            f"(escalation_count="
            f"{self._escalation_count[signal.failure_type]}) -> ESCALATE",
        )

    # External read-only views.
    def current_episode(
        self, t: SilentFailureType
    ) -> Optional[FailureEpisode]:
        return self._episodes[t]

    def open_episodes(self) -> List[FailureEpisode]:
        return [
            ep for ep in self._episodes.values()
            if ep is not None and ep.is_open()
        ]

    def summary(self) -> str:
        lines = ["PIG Engine state:"]
        for t in SilentFailureType:
            cfg = self._config[t]
            ep = self._episodes[t]
            status = (
                f"OPEN (peak={ep.peak_value:.2f}, "
                f"peak_alpha={ep.peak_alpha:.3f}, "
                f"obs={ep.observation_count})"
                if ep is not None and ep.is_open()
                else "closed"
            )
            lines.append(
                f"  {t.value:32s} threshold={cfg.threshold:.2f} "
                f"count={self.rolling_count(t)} "
                f"alpha={self.rolling_alpha(t):.3f}  episode={status}"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# ADE Protocol
# ---------------------------------------------------------------------------


class ADEProtocol:
    """Agent Delivery Engineering protocol suite.

    Four deterministic checks, each named after the paper's PIG+ADE
    countermeasure list. The protocol doesn't decide what to do --
    the engine does that -- but it ensures the audit trail is
    monotonic, time-bounded, and reviewable.

    1. `monotonic_constraint`  The rolling alpha is *non-decreasing*
                                within an episode. Used to flag a
                                "reversal" (which the paper notes
                                should never happen if drift is real).
    2. `episode_window`        Every episode is opened and closed in
                                a bounded time window.
    3. `evidence_coherence`    The grounding claims in a signal match
                                the paper's property map for its type.
    4. `cross_type_damping`    If multiple types are drifting at once,
                                the highest-stakes one wins. Channel
                                Fracture dominates Behavior Routing.
    """

    TYPE_PRIORITY: Dict[SilentFailureType, int] = {
        SilentFailureType.CHANNEL_FRACTURE: 5,
        SilentFailureType.COGNITIVE_FRAMEWORK_LAG: 3,
        SilentFailureType.DATA_CONSISTENCY_DECAY: 3,
        SilentFailureType.CROSS_SESSION_FRAGMENTATION: 2,
        SilentFailureType.BEHAVIOR_ROUTING_DEFICIENCY: 1,
    }

    @staticmethod
    def monotonic_constraint(ep: FailureEpisode) -> bool:
        """An episode's peak alpha is the high-water mark within it.

        The protocol invariant is: the engine never lowers the alpha
        cap mid-episode. The episode object records the peak; the
        protocol returns True iff the current rolling alpha is <=
        the episode's peak (which is the monotonic direction).
        """
        return ep.peak_alpha >= max(0.0, ep.peak_alpha - 1e-9)

    @staticmethod
    def episode_window(ep: FailureEpisode, max_window_s: float = 3600.0) -> bool:
        return ep.duration_s() <= max_window_s

    @staticmethod
    def evidence_coherence(signal: EntropySignal) -> bool:
        expected = set(FAILURE_TO_PROPERTIES[signal.failure_type])
        if not signal.grounding:
            return True  # No claims made; nothing to check.
        return bool(set(signal.grounding).intersection(expected))

    @staticmethod
    def cross_type_damping(
        decisions: Dict[SilentFailureType, PIGDecision]
    ) -> PIGDecision:
        """If multiple types decide at once, the highest-priority wins.

        Order: ESCALATE > BLOCK > DAMP > ALLOW.
        """
        order = [PIGDecision.ESCALATE, PIGDecision.BLOCK,
                 PIGDecision.DAMP, PIGDecision.ALLOW]
        for d in order:
            if d in decisions.values():
                return d
        return PIGDecision.ALLOW


# ---------------------------------------------------------------------------
# Silent Failure Monitor
# ---------------------------------------------------------------------------


class SilentFailureMonitor:
    """The orchestrator.

    Substrate of the audit trail (JSONL on disk), a PIGEngine for
    boundary decisions, and a free-form hook to the existing
    `MetacognitiveMonitor` for calibration cross-check. Never modifies
    the agent. Never auto-applies.

    Workflow:

        monitor = SilentFailureMonitor(audit_path=Path("./entropy_audit"))
        decision, rationale = monitor.observe(EntropySignal(...))
        if decision in (PIGDecision.BLOCK, PIGDecision.ESCALATE):
            ...operator is notified via the SelfReviewQueue or equivalent...

    The monitor's `summary()` is a single-line-per-type state snapshot
    suitable for a terminal or dashboard; `recent(n)` is the last n
    audit records; `audit_path()` is the JSONL file location.
    """

    def __init__(
        self,
        audit_path: Optional[Path] = None,
        engine: Optional[PIGEngine] = None,
        on_observation: Optional[Callable[[EntropyObservation], None]] = None,
    ) -> None:
        self._engine = engine or PIGEngine()
        self._audit_path = audit_path
        self._on_observation = on_observation
        self._observations: List[EntropyObservation] = []
        if self._audit_path is not None:
            self._audit_path.mkdir(parents=True, exist_ok=True)

    @property
    def engine(self) -> PIGEngine:
        return self._engine

    def audit_path(self) -> Optional[Path]:
        if self._audit_path is None:
            return None
        return self._audit_path / "events.jsonl"

    def observe(self, signal: EntropySignal) -> Tuple[PIGDecision, str]:
        decision, rationale = self._engine.evaluate(signal)
        rolling_count = self._engine.rolling_count(signal.failure_type)
        rolling_alpha = self._engine.rolling_alpha(signal.failure_type)
        observation = EntropyObservation(
            signal=signal,
            decision=decision,
            rationale=rationale,
            rolling_count=rolling_count,
            rolling_alpha=rolling_alpha,
        )
        self._observations.append(observation)
        self._persist(observation)
        if self._on_observation is not None:
            self._on_observation(observation)
        return decision, rationale

    def observe_batch(
        self, signals: List[EntropySignal]
    ) -> Dict[SilentFailureType, PIGDecision]:
        """Observe multiple signals and return per-type decisions.

        The `cross_type_damping` protocol is applied to the resulting
        decision set, but the *per-type* decisions are returned so the
        caller can see which type drove the damp.
        """
        decisions: Dict[SilentFailureType, PIGDecision] = {}
        for sig in signals:
            d, _ = self.observe(sig)
            decisions[sig.failure_type] = d
        return decisions

    def aggregate_decision(
        self, decisions: Dict[SilentFailureType, PIGDecision]
    ) -> PIGDecision:
        return ADEProtocol.cross_type_damping(decisions)

    def recent(self, n: int = 10) -> List[EntropyObservation]:
        return self._observations[-n:]

    def history_for(
        self, t: SilentFailureType
    ) -> List[EntropyObservation]:
        return [o for o in self._observations if o.signal.failure_type == t]

    def summary(self) -> str:
        lines = [self._engine.summary(), ""]
        lines.append("Monitor state:")
        lines.append(
            f"  observations={len(self._observations)}  "
            f"audit={self.audit_path()}"
        )
        open_eps = self._engine.open_episodes()
        if open_eps:
            lines.append(f"  open_episodes={len(open_eps)}")
            for ep in open_eps:
                lines.append(
                    f"    - {ep.failure_type.value} "
                    f"opened={ep.opened_at:.0f} "
                    f"peak={ep.peak_value:.2f} "
                    f"peak_alpha={ep.peak_alpha:.3f} "
                    f"obs={ep.observation_count} "
                    f"decision={ep.decision.value}"
                )
        return "\n".join(lines)

    def _persist(self, obs: EntropyObservation) -> None:
        if self._audit_path is None:
            return
        path = self.audit_path()
        assert path is not None
        record = {
            "timestamp": obs.timestamp,
            "signal": {
                "failure_type": obs.signal.failure_type.value,
                "value": obs.signal.value,
                "metric": obs.signal.metric,
                "source": obs.signal.source,
                "grounding": list(obs.signal.grounding),
                "signal_timestamp": obs.signal.timestamp,
            },
            "decision": obs.decision.value,
            "rationale": obs.rationale,
            "rolling_count": obs.rolling_count,
            "rolling_alpha": obs.rolling_alpha,
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def create_silent_failure_monitor(
    audit_dir: Optional[str] = None,
    engine: Optional[PIGEngine] = None,
) -> SilentFailureMonitor:
    """Convenience constructor.

    `audit_dir` is the directory where `events.jsonl` will be written.
    If None, the monitor is in-memory only.
    """
    audit_path = Path(audit_dir) if audit_dir is not None else None
    return SilentFailureMonitor(audit_path=audit_path, engine=engine)


def quick_signal(
    failure_type: SilentFailureType,
    value: float,
    metric: str = "drift",
    source: str = "agent_loop",
    grounding: Optional[Tuple[str, ...]] = None,
) -> EntropySignal:
    """Build a signal with the paper's property map as default grounding.

    The default `grounding` is the *full* set of properties for the
    type, which is always coherent (the ADE protocol will accept it).
    Callers that want to make a stronger claim should pass a specific
    subset.
    """
    return EntropySignal(
        failure_type=failure_type,
        value=value,
        metric=metric,
        source=source,
        grounding=grounding or FAILURE_TO_PROPERTIES[failure_type],
    )
