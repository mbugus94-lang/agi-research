"""
Self-Reflection and Improvement System for AGI Agent
Based on: Ouroboros BIBLE.md pattern, Active Inference safety principles,
          and Distributional AGI Safety auditability requirements

This module implements structured self-reflection for safe agent evolution,
enabling performance analysis, capability assessment, and guided improvement
with constitutional safety guardrails.
"""

from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
import json
import hashlib
import time


class ReflectionScope(Enum):
    """Scope levels for reflection and self-modification."""
    INTERNAL_STATE = auto()      # Safe: memory, preferences, plans
    CONFIGURATION = auto()       # Caution: parameters, thresholds
    TOOL_BEHAVIOR = auto()       # Review: tool usage patterns
    CODE_STRUCTURE = auto()      # High scrutiny: module organization
    CORE_ARCHITECTURE = auto()   # Critical: fundamental algorithms
    SAFETY_CONSTRAINTS = auto()  # Forbidden: constitutional rules


class ChangeStatus(Enum):
    """Status of proposed self-modifications."""
    PROPOSED = auto()
    UNDER_REVIEW = auto()
    APPROVED = auto()
    REJECTED = auto()
    IMPLEMENTED = auto()
    ROLLED_BACK = auto()


class ReviewPerspective(Enum):
    """Simulated reviewer perspectives for multi-model review."""
    SAFETY_FIRST = "safety_first"      # Focus on risks, edge cases
    PERFORMANCE = "performance"       # Focus on efficiency, optimization
    CORRECTNESS = "correctness"       # Focus on logic, correctness
    MAINTAINABILITY = "maintainability"  # Focus on clarity, documentation
    ELEGANCE = "elegance"            # Focus on simplicity, beauty


@dataclass
class PerformanceRecord:
    """Record of a single task execution."""
    task_id: str
    task_type: str
    success: bool
    execution_time_ms: float
    quality_score: float  # 0.0 - 1.0
    error_type: Optional[str] = None
    retry_count: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CapabilityAssessment:
    """Self-assessment of a specific capability."""
    capability_name: str
    proficiency_score: float  # 0.0 - 1.0
    confidence: float  # 0.0 - 1.0
    sample_size: int
    last_evaluated: datetime
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)


@dataclass
class ImprovementGoal:
    """Structured goal for capability enhancement."""
    goal_id: str
    target_capability: str
    target_score: float
    current_score: float
    priority: int  # 1-10, higher = more important
    deadline: Optional[datetime] = None
    strategy: str = ""
    milestones: List[Tuple[str, float]] = field(default_factory=list)  # (description, target_score)
    created_at: datetime = field(default_factory=datetime.now)
    status: str = "active"  # active, completed, abandoned


@dataclass
class ProposedChange:
    """A proposed self-modification with full audit trail."""
    change_id: str
    scope: ReflectionScope
    description: str
    rationale: str
    expected_impact: Dict[str, float]  # metrics -> expected change
    implementation: str  # code or pseudo-code
    status: ChangeStatus = ChangeStatus.PROPOSED
    reviews: Dict[ReviewPerspective, Dict] = field(default_factory=dict)
    constitutional_violations: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    implemented_at: Optional[datetime] = None
    rolled_back_at: Optional[datetime] = None
    rollback_reason: Optional[str] = None


class ConstitutionalPrinciple:
    """A principle governing safe self-modification."""
    
    def __init__(self, name: str, description: str, check_fn: Callable[[ProposedChange], bool]):
        self.name = name
        self.description = description
        self.check_fn = check_fn
    
    def validate(self, change: ProposedChange) -> Tuple[bool, str]:
        """Returns (passed, violation_reason or 'OK')."""
        try:
            passed = self.check_fn(change)
            return (passed, "OK" if passed else f"Violates: {self.name}")
        except Exception as e:
            return (False, f"Validation error in {self.name}: {e}")


class ReflectionEngine:
    """
    Core reflection engine for self-analysis and improvement.
    Implements safe self-modification with constitutional constraints.
    """
    
    def __init__(self, agent_id: str = "default"):
        self.agent_id = agent_id
        self.performance_history: List[PerformanceRecord] = []
        self.capability_assessments: Dict[str, CapabilityAssessment] = {}
        self.improvement_goals: Dict[str, ImprovementGoal] = {}
        self.change_history: List[ProposedChange] = []
        self.constitution: List[ConstitutionalPrinciple] = self._init_constitution()
        
        # Configuration
        self.min_samples_for_assessment = 5
        self.performance_window_size = 100
        self.confidence_threshold = 0.7
        
    def _init_constitution(self) -> List[ConstitutionalPrinciple]:
        """Initialize default constitutional safety principles."""
        
        def no_safety_modifications(change: ProposedChange) -> bool:
            """Never modify safety constraints."""
            return change.scope != ReflectionScope.SAFETY_CONSTRAINTS
        
        def code_requires_review(change: ProposedChange) -> bool:
            """Code changes must have multi-perspective review."""
            if change.scope in [ReflectionScope.CODE_STRUCTURE, ReflectionScope.CORE_ARCHITECTURE]:
                return len(change.reviews) >= 3  # At least 3 perspectives
            return True
        
        def requires_rationale(change: ProposedChange) -> bool:
            """All changes must have clear rationale."""
            return len(change.rationale) >= 20  # Minimum explanation length
        
        def measurable_impact(change: ProposedChange) -> bool:
            """Changes should have measurable expected impact."""
            return len(change.expected_impact) > 0
        
        def no_architecture_without_history(change: ProposedChange) -> bool:
            """Architecture changes require established track record."""
            if change.scope == ReflectionScope.CORE_ARCHITECTURE:
                # Must have at least 10 successful smaller changes first
                successful_changes = sum(
                    1 for c in self.change_history 
                    if c.status == ChangeStatus.IMPLEMENTED and c.scope != ReflectionScope.INTERNAL_STATE
                )
                return successful_changes >= 10
            return True
        
        return [
            ConstitutionalPrinciple(
                "Safety Immutability",
                "Safety constraints cannot be modified by the agent",
                no_safety_modifications
            ),
            ConstitutionalPrinciple(
                "Multi-Perspective Review",
                "Code changes require at least 3 reviewer perspectives",
                code_requires_review
            ),
            ConstitutionalPrinciple(
                "Rationale Requirement",
                "All changes must have clear rationale",
                requires_rationale
            ),
            ConstitutionalPrinciple(
                "Measurable Impact",
                "Changes must have measurable expected impact",
                measurable_impact
            ),
            ConstitutionalPrinciple(
                "Architecture Experience",
                "Core architecture changes require proven track record",
                no_architecture_without_history
            )
        ]
    
    # ============ Performance Analysis ============
    
    def record_performance(self, record: PerformanceRecord) -> None:
        """Record a task execution for pattern analysis."""
        self.performance_history.append(record)
        
        # Maintain window size
        if len(self.performance_history) > self.performance_window_size:
            self.performance_history = self.performance_history[-self.performance_window_size:]
    
    def analyze_performance_patterns(self, task_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze success/failure patterns across task executions.
        
        Returns:
            Dictionary with success_rate, avg_time, error_patterns, trends
        """
        records = self.performance_history
        if task_type:
            records = [r for r in records if r.task_type == task_type]
        
        if not records:
            return {"error": "No performance records available"}
        
        # Basic metrics
        total = len(records)
        successes = sum(1 for r in records if r.success)
        failures = total - successes
        
        success_rate = successes / total if total > 0 else 0
        avg_time = sum(r.execution_time_ms for r in records) / total
        avg_quality = sum(r.quality_score for r in records) / total
        
        # Error pattern analysis
        error_counts = {}
        for r in records:
            if r.error_type:
                error_counts[r.error_type] = error_counts.get(r.error_type, 0) + 1
        
        # Trend analysis (compare recent half to older half)
        mid = len(records) // 2
        if mid > 0:
            recent_success = sum(1 for r in records[mid:] if r.success) / len(records[mid:])
            older_success = sum(1 for r in records[:mid] if r.success) / len(records[:mid])
            trend = "improving" if recent_success > older_success else "declining" if recent_success < older_success else "stable"
            trend_delta = recent_success - older_success
        else:
            trend = "insufficient_data"
            trend_delta = 0
        
        return {
            "total_records": total,
            "success_rate": round(success_rate, 3),
            "failure_rate": round(failures / total, 3) if total > 0 else 0,
            "avg_execution_time_ms": round(avg_time, 2),
            "avg_quality_score": round(avg_quality, 3),
            "error_patterns": error_counts,
            "trend": trend,
            "trend_delta": round(trend_delta, 3),
            "retry_avg": sum(r.retry_count for r in records) / total
        }
    
    def identify_problem_areas(self) -> List[Dict[str, Any]]:
        """Identify task types with concerning performance."""
        # Group by task type
        by_type: Dict[str, List[PerformanceRecord]] = {}
        for r in self.performance_history:
            if r.task_type not in by_type:
                by_type[r.task_type] = []
            by_type[r.task_type].append(r)
        
        problems = []
        for task_type, records in by_type.items():
            if len(records) >= self.min_samples_for_assessment:
                success_rate = sum(1 for r in records if r.success) / len(records)
                avg_quality = sum(r.quality_score for r in records) / len(records)
                
                if success_rate < 0.7 or avg_quality < 0.6:
                    problems.append({
                        "task_type": task_type,
                        "success_rate": round(success_rate, 3),
                        "avg_quality": round(avg_quality, 3),
                        "sample_size": len(records),
                        "severity": "high" if success_rate < 0.5 else "medium"
                    })
        
        return sorted(problems, key=lambda x: x["success_rate"])
    
    # ============ Capability Assessment ============
    
    def assess_capability(self, capability_name: str, 
                        task_type: str,
                        evaluator_fn: Optional[Callable[[List[PerformanceRecord]], Tuple[float, List[str], List[str]]]] = None) -> CapabilityAssessment:
        """
        Self-assess a specific capability based on performance history.
        
        Args:
            capability_name: Name of the capability being assessed
            task_type: Task type associated with this capability
            evaluator_fn: Optional custom evaluator (returns score, strengths, weaknesses)
        
        Returns:
            CapabilityAssessment with scores and analysis
        """
        records = [r for r in self.performance_history if r.task_type == task_type]
        
        if len(records) < self.min_samples_for_assessment:
            return CapabilityAssessment(
                capability_name=capability_name,
                proficiency_score=0.5,
                confidence=0.1,
                sample_size=len(records),
                last_evaluated=datetime.now(),
                weaknesses=["Insufficient sample size for reliable assessment"]
            )
        
        if evaluator_fn:
            score, strengths, weaknesses = evaluator_fn(records)
        else:
            # Default evaluation
            score = sum(r.quality_score for r in records) / len(records)
            score = score * 0.7 + (sum(1 for r in records if r.success) / len(records)) * 0.3
            
            strengths = []
            weaknesses = []
            
            if sum(1 for r in records if r.success) / len(records) > 0.8:
                strengths.append("High success rate")
            if sum(r.execution_time_ms for r in records) / len(records) < 1000:
                strengths.append("Fast execution")
            if sum(1 for r in records if r.quality_score > 0.8) / len(records) > 0.5:
                strengths.append("Consistently high quality")
            
            if sum(1 for r in records if not r.success) / len(records) > 0.2:
                weaknesses.append("Unreliable - too many failures")
            if sum(r.retry_count for r in records) / len(records) > 1:
                weaknesses.append("Requires too many retries")
        
        # Calculate confidence based on sample size
        confidence = min(1.0, len(records) / 50)  # Max confidence at 50 samples
        
        assessment = CapabilityAssessment(
            capability_name=capability_name,
            proficiency_score=round(score, 3),
            confidence=round(confidence, 3),
            sample_size=len(records),
            last_evaluated=datetime.now(),
            strengths=strengths,
            weaknesses=weaknesses,
            improvement_suggestions=self._generate_suggestions(weaknesses)
        )
        
        self.capability_assessments[capability_name] = assessment
        return assessment
    
    def _generate_suggestions(self, weaknesses: List[str]) -> List[str]:
        """Generate improvement suggestions based on weaknesses."""
        suggestion_map = {
            "Unreliable - too many failures": "Implement better error handling and fallback strategies",
            "Requires too many retries": "Improve initial attempt quality through better planning",
            "Slow execution": "Optimize algorithm or implement caching",
            "Low quality outputs": "Add validation steps and quality gates",
            "Insufficient sample size for reliable assessment": "Execute more tasks to build assessment confidence"
        }
        
        suggestions = []
        for weakness in weaknesses:
            if weakness in suggestion_map:
                suggestions.append(suggestion_map[weakness])
            else:
                suggestions.append(f"Address: {weakness}")
        
        return suggestions
    
    def get_capability_profile(self) -> Dict[str, CapabilityAssessment]:
        """Get full capability assessment profile."""
        return self.capability_assessments
    
    # ============ Improvement Planning ============
    
    def create_improvement_goal(self, target_capability: str,
                               target_score: float,
                               priority: int = 5,
                               deadline: Optional[datetime] = None,
                               strategy: str = "") -> ImprovementGoal:
        """Create a structured improvement goal."""
        
        current = self.capability_assessments.get(target_capability)
        current_score = current.proficiency_score if current else 0.5
        
        goal = ImprovementGoal(
            goal_id=f"goal_{int(time.time())}_{hash(target_capability) % 10000}",
            target_capability=target_capability,
            target_score=target_score,
            current_score=current_score,
            priority=priority,
            deadline=deadline,
            strategy=strategy or "Practice and feedback loop",
            milestones=[
                (f"Reach {(current_score + (target_score - current_score) * 0.5):.2f}", 
                 current_score + (target_score - current_score) * 0.5),
                (f"Approach target at {(target_score * 0.9):.2f}", target_score * 0.9)
            ]
        )
        
        self.improvement_goals[goal.goal_id] = goal
        return goal
    
    def prioritize_goals(self) -> List[ImprovementGoal]:
        """Return goals sorted by priority and potential impact."""
        goals = list(self.improvement_goals.values())
        
        # Filter active goals
        active = [g for g in goals if g.status == "active"]
        
        # Sort by priority desc, then by gap (target - current) desc
        return sorted(active, key=lambda g: (g.priority, g.target_score - g.current_score), reverse=True)
    
    def update_goal_progress(self, goal_id: str, new_score: float) -> None:
        """Update a goal with new capability score."""
        if goal_id in self.improvement_goals:
            goal = self.improvement_goals[goal_id]
            goal.current_score = new_score
            
            # Check completion
            if new_score >= goal.target_score:
                goal.status = "completed"
            elif goal.deadline and datetime.now() > goal.deadline:
                goal.status = "abandoned"
    
    # ============ Self-Modification with Safety ============
    
    def propose_change(self, scope: ReflectionScope,
                      description: str,
                      rationale: str,
                      expected_impact: Dict[str, float],
                      implementation: str) -> ProposedChange:
        """
        Propose a self-modification with full constitutional validation.
        
        All changes must pass constitutional review before implementation.
        """
        
        # Generate unique ID
        content_hash = hashlib.sha256(
            f"{scope}{description}{time.time()}".encode()
        ).hexdigest()[:12]
        
        change = ProposedChange(
            change_id=f"change_{content_hash}",
            scope=scope,
            description=description,
            rationale=rationale,
            expected_impact=expected_impact,
            implementation=implementation,
            status=ChangeStatus.PROPOSED
        )
        
        # Constitutional validation
        violations = []
        for principle in self.constitution:
            passed, reason = principle.validate(change)
            if not passed:
                violations.append(reason)
        
        change.constitutional_violations = violations
        
        if violations:
            change.status = ChangeStatus.REJECTED
        
        self.change_history.append(change)
        return change
    
    def simulate_review(self, change: ProposedChange,
                       perspectives: List[ReviewPerspective] = None) -> Dict[ReviewPerspective, Dict]:
        """
        Simulate multi-perspective review of a proposed change.
        
        In production, this would call multiple LLM instances.
        For now, we simulate with rule-based analysis.
        """
        
        if perspectives is None:
            perspectives = [
                ReviewPerspective.SAFETY_FIRST,
                ReviewPerspective.CORRECTNESS,
                ReviewPerspective.MAINTAINABILITY
            ]
        
        reviews = {}
        
        for perspective in perspectives:
            review = self._generate_perspective_review(change, perspective)
            reviews[perspective] = review
        
        change.reviews = reviews
        change.status = ChangeStatus.UNDER_REVIEW
        return reviews
    
    def _generate_perspective_review(self, change: ProposedChange, 
                                    perspective: ReviewPerspective) -> Dict:
        """Generate a simulated review from a specific perspective."""
        
        # Base review structure
        review = {
            "perspective": perspective.value,
            "approved": False,
            "confidence": 0.5,
            "concerns": [],
            "suggestions": []
        }
        
        # Perspective-specific logic
        if perspective == ReviewPerspective.SAFETY_FIRST:
            if change.scope in [ReflectionScope.SAFETY_CONSTRAINTS, ReflectionScope.CORE_ARCHITECTURE]:
                review["concerns"].append("High-risk scope - requires extensive testing")
                review["confidence"] = 0.3
            elif change.scope == ReflectionScope.INTERNAL_STATE:
                review["approved"] = True
                review["confidence"] = 0.8
            else:
                review["approved"] = True
                review["confidence"] = 0.6
        
        elif perspective == ReviewPerspective.CORRECTNESS:
            if len(change.implementation) < 50:
                review["concerns"].append("Implementation seems incomplete")
                review["confidence"] = 0.4
            elif "TODO" in change.implementation or "FIXME" in change.implementation:
                review["concerns"].append("Contains unresolved TODOs/FIXMEs")
                review["suggestions"].append("Complete all TODOs before implementation")
                review["confidence"] = 0.5
            else:
                review["approved"] = True
                review["confidence"] = 0.75
        
        elif perspective == ReviewPerspective.MAINTAINABILITY:
            if len(change.rationale) < 50:
                review["concerns"].append("Rationale could be more detailed")
                review["suggestions"].append("Add more context about why this change is needed")
            if not change.expected_impact:
                review["concerns"].append("Expected impact not quantified")
            else:
                review["approved"] = True
                review["confidence"] = 0.7
        
        elif perspective == ReviewPerspective.PERFORMANCE:
            if change.expected_impact.get("execution_time_delta", 0) > 0:
                review["concerns"].append("Expected to increase execution time")
            elif change.expected_impact.get("memory_usage_delta", 0) > 0:
                review["concerns"].append("Expected to increase memory usage")
            else:
                review["approved"] = True
                review["confidence"] = 0.65
        
        elif perspective == ReviewPerspective.ELEGANCE:
            if "hack" in change.implementation.lower() or "workaround" in change.implementation.lower():
                review["concerns"].append("Contains hack/workaround - consider cleaner solution")
                review["confidence"] = 0.4
            else:
                review["approved"] = True
                review["confidence"] = 0.6
        
        return review
    
    def approve_change(self, change_id: str) -> bool:
        """Approve a change after review (in production: human or multi-model approval)."""
        for change in self.change_history:
            if change.change_id == change_id:
                if change.constitutional_violations:
                    return False  # Cannot approve constitutionally invalid changes
                
                # Check if we have sufficient reviews
                if len(change.reviews) >= 2:
                    approval_count = sum(1 for r in change.reviews.values() if r.get("approved"))
                    if approval_count >= len(change.reviews) * 0.6:  # Majority approval
                        change.status = ChangeStatus.APPROVED
                        return True
        
        return False
    
    def implement_change(self, change_id: str) -> bool:
        """
        Mark a change as implemented.
        
        NOTE: Actual implementation would execute the change.
        For safety, this framework only tracks proposals.
        """
        for change in self.change_history:
            if change.change_id == change_id:
                if change.status == ChangeStatus.APPROVED:
                    change.status = ChangeStatus.IMPLEMENTED
                    change.implemented_at = datetime.now()
                    return True
        
        return False
    
    def rollback_change(self, change_id: str, reason: str) -> bool:
        """Mark a change as rolled back."""
        for change in self.change_history:
            if change.change_id == change_id:
                if change.status == ChangeStatus.IMPLEMENTED:
                    change.status = ChangeStatus.ROLLED_BACK
                    change.rolled_back_at = datetime.now()
                    change.rollback_reason = reason
                    return True
        
        return False
    
    # ============ Audit and Reporting ============
    
    def get_audit_trail(self, scope_filter: Optional[ReflectionScope] = None) -> List[ProposedChange]:
        """Get full audit trail of changes, optionally filtered by scope."""
        changes = self.change_history
        if scope_filter:
            changes = [c for c in changes if c.scope == scope_filter]
        return changes
    
    def generate_reflection_report(self) -> Dict[str, Any]:
        """Generate comprehensive self-reflection report."""
        
        # Performance summary
        perf_summary = self.analyze_performance_patterns()
        
        # Problem areas
        problems = self.identify_problem_areas()
        
        # Capability summary
        capabilities = {
            name: {
                "score": cap.proficiency_score,
                "confidence": cap.confidence,
                "strengths": cap.strengths,
                "weaknesses": cap.weaknesses
            }
            for name, cap in self.capability_assessments.items()
        }
        
        # Goal summary
        active_goals = [g for g in self.improvement_goals.values() if g.status == "active"]
        completed_goals = [g for g in self.improvement_goals.values() if g.status == "completed"]
        
        # Change summary
        changes_by_status: Dict[str, int] = {}
        for c in self.change_history:
            status = c.status.name
            changes_by_status[status] = changes_by_status.get(status, 0) + 1
        
        return {
            "generated_at": datetime.now().isoformat(),
            "agent_id": self.agent_id,
            "performance_summary": perf_summary,
            "problem_areas": problems,
            "capabilities": capabilities,
            "improvement_goals": {
                "active": len(active_goals),
                "completed": len(completed_goals),
                "top_priority": active_goals[0].target_capability if active_goals else None
            },
            "self_modification_history": changes_by_status,
            "constitutional_principles": [p.name for p in self.constitution],
            "recommendations": self._generate_recommendations(problems, active_goals)
        }
    
    def _generate_recommendations(self, problems: List[Dict], 
                                 goals: List[ImprovementGoal]) -> List[str]:
        """Generate high-level recommendations based on analysis."""
        recommendations = []
        
        if problems:
            recommendations.append(
                f"Address {len(problems)} identified problem areas, starting with {problems[0]['task_type']}"
            )
        
        if goals:
            top_goal = max(goals, key=lambda g: g.priority)
            recommendations.append(
                f"Focus on improving {top_goal.target_capability} (priority {top_goal.priority})"
            )
        
        if not self.capability_assessments:
            recommendations.append("Conduct capability assessments for key task types")
        
        successful_changes = sum(
            1 for c in self.change_history if c.status == ChangeStatus.IMPLEMENTED
        )
        if successful_changes == 0 and self.change_history:
            recommendations.append("Review change approval process - many proposals but no implementations")
        
        return recommendations
    
    def export_state(self) -> Dict[str, Any]:
        """Export full reflection state for persistence."""
        return {
            "agent_id": self.agent_id,
            "performance_history": [
                {
                    "task_id": r.task_id,
                    "task_type": r.task_type,
                    "success": r.success,
                    "execution_time_ms": r.execution_time_ms,
                    "quality_score": r.quality_score,
                    "error_type": r.error_type,
                    "retry_count": r.retry_count,
                    "timestamp": r.timestamp.isoformat()
                }
                for r in self.performance_history
            ],
            "capability_assessments": {
                name: {
                    "capability_name": c.capability_name,
                    "proficiency_score": c.proficiency_score,
                    "confidence": c.confidence,
                    "sample_size": c.sample_size,
                    "last_evaluated": c.last_evaluated.isoformat(),
                    "strengths": c.strengths,
                    "weaknesses": c.weaknesses,
                    "improvement_suggestions": c.improvement_suggestions
                }
                for name, c in self.capability_assessments.items()
            },
            "improvement_goals": {
                gid: {
                    "goal_id": g.goal_id,
                    "target_capability": g.target_capability,
                    "target_score": g.target_score,
                    "current_score": g.current_score,
                    "priority": g.priority,
                    "deadline": g.deadline.isoformat() if g.deadline else None,
                    "strategy": g.strategy,
                    "status": g.status,
                    "created_at": g.created_at.isoformat()
                }
                for gid, g in self.improvement_goals.items()
            },
            "change_history": [
                {
                    "change_id": c.change_id,
                    "scope": c.scope.name,
                    "description": c.description,
                    "rationale": c.rationale,
                    "expected_impact": c.expected_impact,
                    "status": c.status.name,
                    "constitutional_violations": c.constitutional_violations,
                    "created_at": c.created_at.isoformat(),
                    "implemented_at": c.implemented_at.isoformat() if c.implemented_at else None,
                    "rolled_back_at": c.rolled_back_at.isoformat() if c.rolled_back_at else None,
                    "rollback_reason": c.rollback_reason
                }
                for c in self.change_history
            ]
        }
    
    def import_state(self, state: Dict[str, Any]) -> None:
        """Import reflection state from persisted data."""
        # This would reconstruct all dataclasses from the dict
        # Implementation omitted for brevity - would parse ISO dates,
        # reconstruct enums, etc.
        pass


def create_reflection_engine(agent_id: str = "default") -> ReflectionEngine:
    """Factory function to create a configured reflection engine."""
    return ReflectionEngine(agent_id)
