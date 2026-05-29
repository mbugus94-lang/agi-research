"""
Metacognitive Monitor - Self-Monitoring for AI Agents

Inspired by:
- "Artificial Intelligence Needs Meta Intelligence" (arXiv:2605.15567v1)
- Psychology-inspired metacognitive strategies
- Resource-rational AI principles

Provides:
1. Self-monitoring of internal states (confidence, progress, resources)
2. Adaptive resource allocation based on task demands
3. Real-time performance tracking and prediction
4. Metacognitive control signals for agent behavior

Key concepts from the paper:
- Metacognition: Self-monitoring of internal states and adaptive control
- Resource-rational: Allocate cognitive resources optimally
- Confidence calibration: Accurate assessment of own capabilities
- Monitoring: Track progress, detect errors, assess understanding
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple
from datetime import datetime
from enum import Enum
import json
import statistics


class MonitoringLevel(Enum):
    """Levels of metacognitive monitoring intensity."""
    MINIMAL = "minimal"       # Basic tracking only
    STANDARD = "standard"     # Full monitoring, periodic reports
    INTENSIVE = "intensive"   # Continuous monitoring, real-time feedback


class ConfidenceCalibration(Enum):
    """Confidence calibration states."""
    WELL_CALIBRATED = "well_calibrated"    # Confidence matches accuracy
    OVERCONFIDENT = "overconfident"        # Confidence > accuracy
    UNDERCONFIDENT = "underconfident"      # Confidence < accuracy
    UNCERTAIN = "uncertain"                # Low confidence, low accuracy


@dataclass
class ResourceUsage:
    """Tracks computational resource usage."""
    tokens_used: int = 0
    api_calls: int = 0
    tools_invoked: int = 0
    memory_operations: int = 0
    time_elapsed_ms: float = 0.0
    
    def total_cost_estimate(self) -> float:
        """Estimate relative cost of operations."""
        # Rough heuristic: tokens are cheapest, API calls most expensive
        return (
            self.tokens_used * 0.0001 +
            self.api_calls * 1.0 +
            self.tools_invoked * 0.5 +
            self.memory_operations * 0.1
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tokens_used": self.tokens_used,
            "api_calls": self.api_calls,
            "tools_invoked": self.tools_invoked,
            "memory_operations": self.memory_operations,
            "time_elapsed_ms": self.time_elapsed_ms,
            "cost_estimate": self.total_cost_estimate()
        }


@dataclass
class ProgressMetrics:
    """Tracks task progress and completion estimates."""
    steps_completed: int = 0
    steps_estimated_total: int = 0
    subtasks_completed: int = 0
    subtasks_total: int = 0
    errors_encountered: int = 0
    recoveries_successful: int = 0
    
    @property
    def completion_percentage(self) -> float:
        if self.steps_estimated_total == 0:
            return 0.0
        return min(100.0, (self.steps_completed / self.steps_estimated_total) * 100)
    
    @property
    def error_rate(self) -> float:
        if self.steps_completed == 0:
            return 0.0
        return self.errors_encountered / self.steps_completed
    
    @property
    def recovery_success_rate(self) -> float:
        if self.errors_encountered == 0:
            return 1.0
        return self.recoveries_successful / self.errors_encountered


@dataclass
class StateAssessment:
    """Assessment of current agent state."""
    timestamp: datetime = field(default_factory=datetime.now)
    task_complexity_score: float = 0.5  # 0-1 scale
    confidence_current_step: float = 0.8
    confidence_overall: float = 0.8
    attention_focus_score: float = 0.8  # How well focused on task
    cognitive_load_estimate: float = 0.5  # 0-1, higher = more loaded
    
    # Metacognitive calibration
    predicted_success_probability: float = 0.8
    estimated_remaining_steps: int = 0
    estimated_remaining_time_ms: float = 0.0
    
    # Control signals
    should_escalate: bool = False  # Escalate to human/sub-agent
    should_pause_for_reflection: bool = False
    should_adjust_strategy: bool = False
    recommended_action: Optional[str] = None


@dataclass
class MonitoredSession:
    """A complete monitored session with all metrics."""
    session_id: str
    task_description: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    # Metrics
    resources: ResourceUsage = field(default_factory=ResourceUsage)
    progress: ProgressMetrics = field(default_factory=ProgressMetrics)
    assessments: List[StateAssessment] = field(default_factory=list)
    
    # Outcome
    final_success: Optional[bool] = None
    final_confidence: float = 0.0
    
    # History
    events: List[Dict[str, Any]] = field(default_factory=list)
    
    def add_event(self, event_type: str, details: Dict[str, Any]):
        """Add a tracked event to session history."""
        self.events.append({
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "details": details
        })
    
    def get_calibration_assessment(self) -> ConfidenceCalibration:
        """Assess if confidence was well-calibrated."""
        if not self.assessments or self.final_success is None:
            return ConfidenceCalibration.UNCERTAIN
        
        avg_confidence = statistics.mean(
            a.confidence_overall for a in self.assessments
        )
        
        success = 1.0 if self.final_success else 0.0
        diff = avg_confidence - success
        
        if abs(diff) < 0.1:
            return ConfidenceCalibration.WELL_CALIBRATED
        elif diff > 0.2:
            return ConfidenceCalibration.OVERCONFIDENT
        elif diff < -0.2:
            return ConfidenceCalibration.UNDERCONFIDENT
        return ConfidenceCalibration.UNCERTAIN
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "task_description": self.task_description,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": (
                (self.end_time - self.start_time).total_seconds()
                if self.end_time else None
            ),
            "resources": self.resources.to_dict(),
            "progress": {
                "steps_completed": self.progress.steps_completed,
                "completion_percentage": self.progress.completion_percentage,
                "error_rate": self.progress.error_rate,
                "recovery_rate": self.progress.recovery_success_rate
            },
            "assessment_count": len(self.assessments),
            "final_success": self.final_success,
            "calibration": self.get_calibration_assessment().value,
            "event_count": len(self.events)
        }


class MetacognitiveMonitor:
    """
    Self-monitoring system for AI agents.
    
    Implements metacognitive strategies from arXiv:2605.15567v1:
    - Continuous self-monitoring of internal states
    - Adaptive resource allocation
    - Confidence calibration
    - Error detection and recovery monitoring
    """
    
    def __init__(self, level: MonitoringLevel = MonitoringLevel.STANDARD):
        self.level = level
        self.active_session: Optional[MonitoredSession] = None
        self.session_history: List[MonitoredSession] = []
        
        # Calibration tracking
        self.confidence_accuracy_pairs: List[Tuple[float, bool]] = []
        
        # Thresholds for control signals
        self.thresholds = {
            "low_confidence": 0.5,
            "very_low_confidence": 0.3,
            "high_error_rate": 0.3,
            "low_recovery_rate": 0.5,
            "high_cognitive_load": 0.8,
            "escalate_on_steps": 50  # Escalate if exceeding this many steps
        }
        
        # Strategy adjustment callbacks
        self.strategy_adjustment_handlers: List[Callable] = []
    
    def start_session(self, session_id: str, task_description: str) -> MonitoredSession:
        """Start a new monitored session."""
        # Close any existing session
        if self.active_session:
            self.end_session(success=False, reason="new_session_started")
        
        session = MonitoredSession(
            session_id=session_id,
            task_description=task_description
        )
        
        self.active_session = session
        session.add_event("session_start", {"description": task_description})
        
        return session
    
    def end_session(
        self,
        success: bool,
        final_confidence: float = 0.0,
        reason: str = "completed"
    ) -> Optional[MonitoredSession]:
        """End the current session and archive it."""
        if not self.active_session:
            return None
        
        session = self.active_session
        session.end_time = datetime.now()
        session.final_success = success
        session.final_confidence = final_confidence
        
        session.add_event("session_end", {
            "success": success,
            "reason": reason,
            "final_confidence": final_confidence
        })
        
        # Track calibration data
        if final_confidence > 0:
            self.confidence_accuracy_pairs.append((final_confidence, success))
        
        self.session_history.append(session)
        self.active_session = None
        
        return session
    
    def record_step(
        self,
        step_description: str,
        success: bool,
        resources_used: ResourceUsage,
        confidence: float
    ):
        """Record completion of a step."""
        if not self.active_session:
            return
        
        session = self.active_session
        session.progress.steps_completed += 1
        
        # Accumulate resources
        session.resources.tokens_used += resources_used.tokens_used
        session.resources.api_calls += resources_used.api_calls
        session.resources.tools_invoked += resources_used.tools_invoked
        session.resources.memory_operations += resources_used.memory_operations
        session.resources.time_elapsed_ms += resources_used.time_elapsed_ms
        
        # Track calibration
        self.confidence_accuracy_pairs.append((confidence, success))
        
        if not success:
            session.progress.errors_encountered += 1
        
        session.add_event("step_complete", {
            "description": step_description,
            "success": success,
            "confidence": confidence
        })
        
        # Intensive monitoring: assess after each step
        if self.level == MonitoringLevel.INTENSIVE:
            self.assess_current_state()
    
    def record_recovery(self, success: bool):
        """Record a recovery attempt from an error."""
        if not self.active_session:
            return
        
        if success:
            self.active_session.progress.recoveries_successful += 1
        
        self.active_session.add_event("recovery_attempt", {"success": success})
    
    def assess_current_state(
        self,
        task_complexity: float = 0.5,
        current_step_confidence: float = 0.8,
        attention_focus: float = 0.8,
        cognitive_load: float = 0.5
    ) -> StateAssessment:
        """
        Assess current agent state and generate control signals.
        
        This is the core metacognitive function that implements
        self-monitoring from arXiv:2605.15567v1.
        """
        if not self.active_session:
            raise ValueError("No active session")
        
        session = self.active_session
        progress = session.progress
        resources = session.resources
        
        # Calculate overall confidence
        recent_confidences = [
            c for c, _ in self.confidence_accuracy_pairs[-10:]
        ] if self.confidence_accuracy_pairs else [current_step_confidence]
        overall_confidence = statistics.mean(recent_confidences)
        
        # Predict success probability based on current trajectory
        error_rate = progress.error_rate
        recovery_rate = progress.recovery_success_rate
        
        # Higher errors and lower recovery = lower success probability
        predicted_success = max(0.0, min(1.0,
            overall_confidence * 0.4 +
            (1 - error_rate) * 0.3 +
            recovery_rate * 0.3
        ))
        
        # Estimate remaining steps
        if progress.completion_percentage > 0:
            remaining_ratio = (100 - progress.completion_percentage) / progress.completion_percentage
            estimated_remaining = int(progress.steps_completed * remaining_ratio)
        else:
            estimated_remaining = 10  # Default estimate
        
        # Generate control signals
        should_escalate = (
            overall_confidence < self.thresholds["very_low_confidence"] or
            error_rate > self.thresholds["high_error_rate"] or
            recovery_rate < self.thresholds["low_recovery_rate"] or
            progress.steps_completed > self.thresholds["escalate_on_steps"] or
            predicted_success < 0.3
        )
        
        should_pause = (
            overall_confidence < self.thresholds["low_confidence"] or
            cognitive_load > self.thresholds["high_cognitive_load"] or
            error_rate > self.thresholds["high_error_rate"] * 0.5
        )
        
        should_adjust = (
            error_rate > 0.1 or
            recovery_rate < 0.8 or
            cognitive_load > 0.6
        )
        
        # Determine recommended action
        recommended_action = None
        if should_escalate:
            recommended_action = "escalate_to_human_or_subagent"
        elif should_pause:
            recommended_action = "pause_and_reflect"
        elif should_adjust:
            recommended_action = "adjust_strategy"
        elif cognitive_load < 0.3 and predicted_success > 0.8:
            recommended_action = "increase_aggression"  # Can take more risks
        
        assessment = StateAssessment(
            task_complexity_score=task_complexity,
            confidence_current_step=current_step_confidence,
            confidence_overall=overall_confidence,
            attention_focus_score=attention_focus,
            cognitive_load_estimate=cognitive_load,
            predicted_success_probability=predicted_success,
            estimated_remaining_steps=estimated_remaining,
            estimated_remaining_time_ms=estimated_remaining * resources.time_elapsed_ms / max(1, progress.steps_completed),
            should_escalate=should_escalate,
            should_pause_for_reflection=should_pause,
            should_adjust_strategy=should_adjust,
            recommended_action=recommended_action
        )
        
        session.assessments.append(assessment)
        
        # Trigger strategy adjustment if needed
        if should_adjust and self.strategy_adjustment_handlers:
            for handler in self.strategy_adjustment_handlers:
                handler(assessment)
        
        return assessment
    
    def get_calibration_stats(self) -> Dict[str, float]:
        """Get confidence calibration statistics."""
        if len(self.confidence_accuracy_pairs) < 5:
            return {"calibration_status": "insufficient_data"}
        
        # Binned calibration analysis
        bins = {
            "0.0-0.2": {"confidences": [], "successes": []},
            "0.2-0.4": {"confidences": [], "successes": []},
            "0.4-0.6": {"confidences": [], "successes": []},
            "0.6-0.8": {"confidences": [], "successes": []},
            "0.8-1.0": {"confidences": [], "successes": []},
        }
        
        for conf, success in self.confidence_accuracy_pairs:
            if conf < 0.2:
                bins["0.0-0.2"]["confidences"].append(conf)
                bins["0.0-0.2"]["successes"].append(1.0 if success else 0.0)
            elif conf < 0.4:
                bins["0.2-0.4"]["confidences"].append(conf)
                bins["0.2-0.4"]["successes"].append(1.0 if success else 0.0)
            elif conf < 0.6:
                bins["0.4-0.6"]["confidences"].append(conf)
                bins["0.4-0.6"]["successes"].append(1.0 if success else 0.0)
            elif conf < 0.8:
                bins["0.6-0.8"]["confidences"].append(conf)
                bins["0.6-0.8"]["successes"].append(1.0 if success else 0.0)
            else:
                bins["0.8-1.0"]["confidences"].append(conf)
                bins["0.8-1.0"]["successes"].append(1.0 if success else 0.0)
        
        # Calculate calibration error (ECE - Expected Calibration Error)
        ece = 0.0
        total_samples = len(self.confidence_accuracy_pairs)
        
        for bin_name, bin_data in bins.items():
            if bin_data["confidences"]:
                avg_conf = statistics.mean(bin_data["confidences"])
                avg_success = statistics.mean(bin_data["successes"])
                bin_weight = len(bin_data["confidences"]) / total_samples
                ece += bin_weight * abs(avg_conf - avg_success)
        
        # Overall accuracy vs average confidence
        avg_confidence = statistics.mean(c for c, _ in self.confidence_accuracy_pairs)
        avg_accuracy = statistics.mean(1.0 if s else 0.0 for _, s in self.confidence_accuracy_pairs)
        
        return {
            "calibration_error_ece": round(ece, 3),
            "average_confidence": round(avg_confidence, 3),
            "average_accuracy": round(avg_accuracy, 3),
            "calibration_bias": round(avg_confidence - avg_accuracy, 3),
            "total_samples": total_samples,
            "calibration_status": (
                "well_calibrated" if abs(avg_confidence - avg_accuracy) < 0.1
                else "overconfident" if avg_confidence > avg_accuracy
                else "underconfident"
            ),
            "bin_details": {
                k: {
                    "count": len(v["confidences"]),
                    "avg_confidence": round(statistics.mean(v["confidences"]), 3) if v["confidences"] else 0,
                    "avg_accuracy": round(statistics.mean(v["successes"]), 3) if v["successes"] else 0
                }
                for k, v in bins.items()
            }
        }
    
    def get_session_summary(self, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get summary of a specific or the most recent session."""
        if session_id:
            session = next(
                (s for s in self.session_history if s.session_id == session_id),
                None
            )
        else:
            session = self.active_session or (self.session_history[-1] if self.session_history else None)
        
        return session.to_dict() if session else None
    
    def get_historical_patterns(self) -> Dict[str, Any]:
        """Analyze historical patterns across sessions."""
        if len(self.session_history) < 3:
            return {"status": "insufficient_data", "sessions": len(self.session_history)}
        
        recent = self.session_history[-10:]  # Last 10 sessions
        
        success_rate = statistics.mean(
            1.0 if s.final_success else 0.0
            for s in recent
            if s.final_success is not None
        )
        
        avg_completion = statistics.mean(
            s.progress.completion_percentage
            for s in recent
        )
        
        avg_error_rate = statistics.mean(
            s.progress.error_rate
            for s in recent
        )
        
        avg_resources = statistics.mean(
            s.resources.total_cost_estimate()
            for s in recent
        )
        
        return {
            "success_rate_10_sessions": round(success_rate, 3),
            "avg_completion_percentage": round(avg_completion, 1),
            "avg_error_rate": round(avg_error_rate, 3),
            "avg_resource_cost": round(avg_resources, 2),
            "trend": (
                "improving" if success_rate > 0.7 and avg_error_rate < 0.2
                else "stable" if success_rate > 0.5
                else "needs_attention"
            )
        }
    
    def register_strategy_adjustment_handler(self, handler: Callable):
        """Register a callback for strategy adjustment events."""
        self.strategy_adjustment_handlers.append(handler)
    
    def set_threshold(self, key: str, value: float):
        """Adjust a monitoring threshold."""
        if key in self.thresholds:
            self.thresholds[key] = value


# Convenience functions for quick monitoring
def create_monitor(level: str = "standard") -> MetacognitiveMonitor:
    """Create a metacognitive monitor with specified level."""
    level_enum = MonitoringLevel(level.lower())
    return MetacognitiveMonitor(level=level_enum)


def quick_session_summary(monitor: MetacognitiveMonitor) -> str:
    """Generate a human-readable session summary."""
    summary = monitor.get_session_summary()
    if not summary:
        return "No active or recent session"
    
    lines = [
        f"📊 Session: {summary['session_id']}",
        f"   Task: {summary['task_description'][:60]}...",
        f"   Duration: {summary.get('duration_seconds', 'in progress')}s",
        f"   Success: {summary['final_success']}",
        f"   Completion: {summary['progress']['completion_percentage']:.1f}%",
        f"   Error Rate: {summary['progress']['error_rate']:.3f}",
        f"   Calibration: {summary['calibration']}",
        f"   Resources: {summary['resources']['cost_estimate']:.2f} (est. cost)"
    ]
    
    return "\n".join(lines)
