"""
Reflection and Self-Improvement System

Based on research findings:
- Self-evaluation of performance
- Error analysis and pattern recognition
- Improvement proposals (flagged for review)
- Safety review before any self-modification

Inspired by Ouroboros multi-model review and constitutional governance.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from enum import Enum


class ReflectionType(Enum):
    PERFORMANCE = "performance"
    ERROR = "error"
    IMPROVEMENT = "improvement"
    SAFETY = "safety"


class ReflectionStatus(Enum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"


@dataclass
class Reflection:
    """A reflection on some aspect of the system"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = field(default_factory=lambda: ReflectionType.PERFORMANCE.value)
    subject: str = ""  # What was being reflected on
    observation: str = ""  # What was observed
    analysis: str = ""  # Why it happened
    proposal: Optional[str] = None  # What to do about it (for improvements)
    status: str = field(default_factory=lambda: ReflectionStatus.PENDING.value)
    confidence: float = 0.5  # How confident in this reflection
    severity: str = "info"  # info, warning, critical
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    reviewed_at: Optional[str] = None
    reviewer: Optional[str] = None  # Who reviewed (self, human, other agent)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "subject": self.subject,
            "observation": self.observation,
            "analysis": self.analysis,
            "proposal": self.proposal,
            "status": self.status,
            "confidence": self.confidence,
            "severity": self.severity,
            "created_at": self.created_at,
            "reviewed_at": self.reviewed_at,
            "reviewer": self.reviewer
        }


@dataclass
class PerformanceMetrics:
    """Metrics for evaluating performance"""
    task_id: str = ""
    task_type: str = ""
    success: bool = False
    duration_seconds: float = 0.0
    steps_completed: int = 0
    steps_total: int = 0
    adaptations_needed: int = 0
    errors_encountered: int = 0
    skills_used: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "success": self.success,
            "duration_seconds": self.duration_seconds,
            "steps_completed": self.steps_completed,
            "steps_total": self.steps_total,
            "adaptations_needed": self.adaptations_needed,
            "errors_encountered": self.errors_encountered,
            "skills_used": self.skills_used,
            "timestamp": self.timestamp
        }


class ReflectionSystem:
    """
    Self-reflection and improvement system.
    
    Principles (from Ouroboros and safety research):
    1. All self-modifications require review
    2. Multi-perspective reflection (simulated)
    3. Safety-first: flag risky proposals
    4. Document everything for audit
    """
    
    def __init__(self):
        self.reflections: List[Reflection] = []
        self.performance_history: List[PerformanceMetrics] = []
        self.improvement_proposals: List[Reflection] = []
        self.error_patterns: Dict[str, int] = {}  # Error type -> count
        
        # Safety keywords for flagging risky proposals
        self.safety_keywords = [
            "delete", "remove", "overwrite", "bypass", 
            "disable", "override", "auto-execute", "self-modify",
            "core", "memory", "identity", "governance"
        ]
    
    def record_performance(self, metrics: PerformanceMetrics) -> None:
        """Record performance metrics for a task"""
        self.performance_history.append(metrics)
        
        # Auto-generate performance reflection
        reflection = self._generate_performance_reflection(metrics)
        if reflection:
            self.reflections.append(reflection)
    
    def _generate_performance_reflection(self, 
                                        metrics: PerformanceMetrics) -> Optional[Reflection]:
        """Generate a reflection based on performance metrics"""
        
        if metrics.success and metrics.adaptations_needed == 0:
            return None  # Perfect execution, no reflection needed
        
        observation = f"Task {'succeeded' if metrics.success else 'failed'}"
        analysis = []
        
        if metrics.adaptations_needed > 0:
            analysis.append(f"Required {metrics.adaptations_needed} plan adaptations")
        
        if metrics.errors_encountered > 0:
            analysis.append(f"Encountered {metrics.errors_encountered} errors")
        
        if metrics.duration_seconds > 60:  # Slow
            analysis.append(f"Took {metrics.duration_seconds:.1f}s (consider optimization)")
        
        # Check for patterns
        success_rate = self._calculate_success_rate(metrics.task_type)
        if success_rate < 0.7:
            analysis.append(f"Low success rate ({success_rate:.1%}) for this task type")
        
        return Reflection(
            type=ReflectionType.PERFORMANCE.value,
            subject=metrics.task_id,
            observation=observation,
            analysis="; ".join(analysis),
            confidence=0.7,
            severity="warning" if not metrics.success else "info"
        )
    
    def analyze_error(self, error: Exception, context: Dict) -> Reflection:
        """
        Analyze an error and create a reflection.
        
        Tracks patterns for continuous improvement.
        """
        error_type = type(error).__name__
        error_msg = str(error)
        
        # Track pattern
        self.error_patterns[error_type] = self.error_patterns.get(error_type, 0) + 1
        
        # Analyze if recurring
        count = self.error_patterns[error_type]
        is_recurring = count > 3
        
        reflection = Reflection(
            type=ReflectionType.ERROR.value,
            subject=error_type,
            observation=f"Error: {error_msg[:100]}",
            analysis=f"Occurred {count} times. {'Pattern detected!' if is_recurring else 'Isolated incident.'}",
            confidence=min(0.5 + (count * 0.1), 0.9),
            severity="critical" if is_recurring else "warning"
        )
        
        self.reflections.append(reflection)
        
        # If recurring, propose improvement
        if is_recurring:
            proposal = self._propose_error_fix(error_type, context)
            if proposal:
                self.improvement_proposals.append(proposal)
        
        return reflection
    
    def _propose_error_fix(self, error_type: str, context: Dict) -> Optional[Reflection]:
        """Propose a fix for a recurring error"""
        
        proposals = {
            "KeyError": "Add input validation before accessing dict keys",
            "ValueError": "Add type checking and conversion for inputs",
            "TimeoutError": "Increase timeout or add retry logic",
            "ConnectionError": "Add fallback mechanisms for network calls",
            "RuntimeError": "Review execution flow for race conditions"
        }
        
        if error_type in proposals:
            return Reflection(
                type=ReflectionType.IMPROVEMENT.value,
                subject=f"Fix for {error_type}",
                observation=f"Recurring {error_type} errors detected",
                analysis=f"Pattern suggests {error_type} is systemic",
                proposal=proposals[error_type],
                confidence=0.6,
                severity="warning"
            )
        
        return None
    
    def propose_improvement(self, subject: str, observation: str,
                           analysis: str, proposal: str,
                           confidence: float = 0.5) -> Reflection:
        """
        Propose a system improvement.
        
        CRITICAL: All proposals are flagged for review.
        Self-modification requires human or multi-agent approval.
        """
        
        # Check for safety concerns
        is_risky = any(kw in proposal.lower() for kw in self.safety_keywords)
        
        reflection = Reflection(
            type=ReflectionType.IMPROVEMENT.value,
            subject=subject,
            observation=observation,
            analysis=analysis,
            proposal=proposal,
            confidence=confidence,
            severity="critical" if is_risky else "warning"
        )
        
        # Auto-flag for review
        if is_risky:
            reflection.status = ReflectionStatus.REJECTED.value
            reflection.analysis += " [AUTO-REJECTED: Modifies critical system component]"
        
        self.improvement_proposals.append(reflection)
        self.reflections.append(reflection)
        
        return reflection
    
    def review_proposal(self, proposal_id: str, 
                       reviewer: str,
                       approved: bool,
                       feedback: Optional[str] = None) -> Optional[Reflection]:
        """
        Review an improvement proposal.
        
        Multi-model review inspired by Ouroboros:
        - Can be reviewed by human or simulated multi-agent consensus
        """
        for reflection in self.improvement_proposals:
            if reflection.id == proposal_id:
                reflection.reviewed_at = datetime.now().isoformat()
                reflection.reviewer = reviewer
                
                if approved:
                    reflection.status = ReflectionStatus.APPROVED.value
                else:
                    reflection.status = ReflectionStatus.REJECTED.value
                    if feedback:
                        reflection.analysis += f" [Feedback: {feedback}]"
                
                return reflection
        
        return None
    
    def simulate_multi_review(self, proposal: Reflection) -> Dict:
        """
        Simulate multi-model review (like Ouroboros).
        
        Returns consensus metrics.
        """
        # Simulate 3 perspectives (in production, would use multiple LLMs)
        perspectives = ["conservative", "pragmatic", "innovative"]
        
        scores = []
        for perspective in perspectives:
            # Simple heuristic scoring
            score = proposal.confidence
            
            if perspective == "conservative":
                # Conservative: penalize risky proposals
                if any(kw in proposal.proposal.lower() for kw in self.safety_keywords):
                    score *= 0.3
                else:
                    score *= 0.8
            
            elif perspective == "pragmatic":
                # Pragmatic: value practical improvements
                if "optimize" in proposal.proposal or "improve" in proposal.proposal:
                    score *= 1.1
                else:
                    score *= 0.9
            
            elif perspective == "innovative":
                # Innovative: reward bold ideas
                if "new" in proposal.proposal or "redesign" in proposal.proposal:
                    score *= 1.2
                else:
                    score *= 0.9
            
            scores.append(min(score, 1.0))
        
        avg_score = sum(scores) / len(scores)
        
        return {
            "perspectives": dict(zip(perspectives, scores)),
            "average": avg_score,
            "consensus": avg_score > 0.6,
            "unanimous": all(s > 0.5 for s in scores)
        }
    
    def generate_self_improvement_report(self) -> Dict:
        """
        Generate a report on potential self-improvements.
        
        Based on performance history and error patterns.
        """
        if not self.performance_history:
            return {"status": "no_data"}
        
        # Calculate metrics
        total_tasks = len(self.performance_history)
        successful_tasks = sum(1 for m in self.performance_history if m.success)
        success_rate = successful_tasks / total_tasks if total_tasks > 0 else 0
        
        avg_duration = sum(m.duration_seconds for m in self.performance_history) / total_tasks
        total_adaptations = sum(m.adaptations_needed for m in self.performance_history)
        
        # Identify weakest skill
        skill_success = {}
        for metric in self.performance_history:
            for skill in metric.skills_used:
                if skill not in skill_success:
                    skill_success[skill] = {"success": 0, "total": 0}
                skill_success[skill]["total"] += 1
                if metric.success:
                    skill_success[skill]["success"] += 1
        
        weakest_skill = None
        lowest_rate = 1.0
        for skill, stats in skill_success.items():
            rate = stats["success"] / stats["total"]
            if rate < lowest_rate:
                lowest_rate = rate
                weakest_skill = skill
        
        # Generate proposals
        proposals = []
        
        if success_rate < 0.8:
            proposals.append(Reflection(
                type=ReflectionType.IMPROVEMENT.value,
                subject="Overall Success Rate",
                observation=f"Success rate is {success_rate:.1%}",
                analysis="Below target of 80%",
                proposal="Review and strengthen error handling across all skills",
                confidence=0.8
            ))
        
        if weakest_skill and lowest_rate < 0.7:
            proposals.append(Reflection(
                type=ReflectionType.IMPROVEMENT.value,
                subject=f"Skill: {weakest_skill}",
                observation=f"Success rate for {weakest_skill} is {lowest_rate:.1%}",
                analysis="Skill performance below threshold",
                proposal=f"Add more robust error handling and input validation to {weakest_skill}",
                confidence=0.7
            ))
        
        # Add error pattern proposals
        for error_type, count in sorted(self.error_patterns.items(), key=lambda x: -x[1])[:3]:
            proposals.append(Reflection(
                type=ReflectionType.IMPROVEMENT.value,
                subject=f"Error Pattern: {error_type}",
                observation=f"{error_type} occurred {count} times",
                analysis="Recurring error pattern detected",
                proposal=f"Add specific handling for {error_type} in affected components",
                confidence=min(0.5 + (count * 0.05), 0.9)
            ))
        
        return {
            "status": "generated",
            "metrics": {
                "total_tasks": total_tasks,
                "success_rate": success_rate,
                "avg_duration": avg_duration,
                "total_adaptations": total_adaptations,
                "error_patterns": dict(self.error_patterns)
            },
            "weakest_skill": weakest_skill,
            "proposals": [p.to_dict() for p in proposals]
        }
    
    def _calculate_success_rate(self, task_type: str) -> float:
        """Calculate success rate for a task type"""
        relevant = [m for m in self.performance_history if m.task_type == task_type]
        if not relevant:
            return 1.0  # Assume success if no data
        
        successful = sum(1 for m in relevant if m.success)
        return successful / len(relevant)
    
    def get_pending_proposals(self) -> List[Reflection]:
        """Get all pending improvement proposals"""
        return [r for r in self.improvement_proposals 
                if r.status == ReflectionStatus.PENDING.value]
    
    def get_critical_reflections(self) -> List[Reflection]:
        """Get critical reflections requiring attention"""
        return [r for r in self.reflections if r.severity == "critical"]
    
    def save(self, path: str) -> None:
        """Save reflection system state"""
        state = {
            "reflections": [r.to_dict() for r in self.reflections],
            "performance_history": [m.to_dict() for m in self.performance_history],
            "improvement_proposals": [p.to_dict() for p in self.improvement_proposals],
            "error_patterns": self.error_patterns
        }
        
        with open(path, 'w') as f:
            json.dump(state, f, indent=2)
    
    def load(self, path: str) -> None:
        """Load reflection system state"""
        with open(path, 'r') as f:
            state = json.load(f)
        
        self.reflections = [Reflection(**r) for r in state.get("reflections", [])]
        self.performance_history = [PerformanceMetrics(**m) for m in state.get("performance_history", [])]
        self.improvement_proposals = [Reflection(**r) for r in state.get("improvement_proposals", [])]
        self.error_patterns = state.get("error_patterns", {})


if __name__ == "__main__":
    # Basic test
    reflection = ReflectionSystem()
    
    # Record some performance
    reflection.record_performance(PerformanceMetrics(
        task_id="test-1",
        task_type="research",
        success=True,
        duration_seconds=45,
        steps_completed=3,
        steps_total=3,
        adaptations_needed=1,
        skills_used=["web_search", "summarize"]
    ))
    
    # Simulate failures
    for i in range(4):
        try:
            raise KeyError(f"Missing key: field_{i}")
        except KeyError as e:
            reflection.analyze_error(e, {"iteration": i})
    
    # Propose improvement
    proposal = reflection.propose_improvement(
        subject="Add better error handling",
        observation="KeyError occurring frequently",
        analysis="Input validation missing",
        proposal="Add input validation before accessing dictionary keys",
        confidence=0.8
    )
    
    print("Reflections:")
    for r in reflection.reflections:
        print(f"  [{r.type}] {r.subject}: {r.observation[:50]}...")
    
    print("\nPending Proposals:")
    for p in reflection.get_pending_proposals():
        print(f"  - {p.proposal}")
    
    print("\nSelf-Improvement Report:")
    report = reflection.generate_self_improvement_report()
    print(json.dumps(report, indent=2))
    
    # Multi-review simulation
    print("\nMulti-Model Review:")
    review = reflection.simulate_multi_review(proposal)
    print(json.dumps(review, indent=2))
