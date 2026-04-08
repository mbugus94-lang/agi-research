"""
Reflection and self-improvement module for AGI agents.
Implements self-evaluation and learning from experience.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class PerformanceMetrics:
    """Metrics from a single task execution."""
    task: str
    success: bool
    steps_taken: int
    time_elapsed: float
    errors: List[str] = field(default_factory=list)
    tool_calls: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    attempts: List[Dict] = field(default_factory=list)  # For tracking multiple attempts
    
    def __post_init__(self):
        if self.attempts is None:
            self.attempts = []
    
    def record_attempt(self, success: bool, duration: float, cost: float = 0.0):
        """Record a single attempt."""
        self.attempts.append({
            "success": success,
            "duration": duration,
            "cost": cost,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics from all attempts."""
        if not self.attempts:
            return {
                "total_attempts": 0,
                "successes": 0,
                "failures": 0,
                "success_rate": 0.0,
                "avg_cost": 0.0
            }
        
        total = len(self.attempts)
        successes = sum(1 for a in self.attempts if a["success"])
        failures = total - successes
        avg_cost = sum(a.get("cost", 0) for a in self.attempts) / total
        
        return {
            "total_attempts": total,
            "successes": successes,
            "failures": failures,
            "success_rate": successes / total if total > 0 else 0.0,
            "avg_cost": avg_cost
        }
    
    def to_dict(self) -> Dict:
        return {
            "task": self.task,
            "success": self.success,
            "steps_taken": self.steps_taken,
            "time_elapsed": self.time_elapsed,
            "errors": self.errors,
            "tool_calls": self.tool_calls,
            "timestamp": self.timestamp.isoformat(),
            "attempts": self.attempts
        }


@dataclass
class ReflectionResult:
    """Result of reflection on task performance."""
    insights: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    confidence: float = 0.5
    task: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "insights": self.insights,
            "recommendations": self.recommendations,
            "confidence": self.confidence,
            "task": self.task
        }


@dataclass
class Reflection:
    """A reflection on task performance."""
    task: str
    what_went_well: str
    what_could_improve: str
    lessons_learned: str
    suggested_changes: List[str] = field(default_factory=list)
    confidence: float = 0.5  # 0-1
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "task": self.task,
            "what_went_well": self.what_went_well,
            "what_could_improve": self.what_could_improve,
            "lessons_learned": self.lessons_learned,
            "suggested_changes": self.suggested_changes,
            "confidence": self.confidence,
            "timestamp": self.timestamp.isoformat()
        }


class Reflector:
    """
    Self-reflection and improvement system.
    Analyzes performance and suggests improvements.
    """
    
    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path
        self.metrics: List[PerformanceMetrics] = []
        self.reflections: List[Reflection] = []
        self.patterns: Dict[str, Any] = {}
        
        if storage_path:
            self._load()
    
    def record_performance(
        self,
        task: str,
        success: bool,
        steps_taken: int,
        time_elapsed: float,
        errors: List[str] = None,
        tool_calls: int = 0
    ) -> PerformanceMetrics:
        """Record performance metrics for a task."""
        metric = PerformanceMetrics(
            task=task,
            success=success,
            steps_taken=steps_taken,
            time_elapsed=time_elapsed,
            errors=errors or [],
            tool_calls=tool_calls
        )
        self.metrics.append(metric)
        self._analyze_patterns()
        self._save()
        return metric
    
    def reflect(self, history: List[Dict[str, Any]], task: str) -> ReflectionResult:
        """
        Generate reflection from execution history.
        
        Args:
            history: List of execution step dicts with keys like 'step', 'action', 'success', 'error', 'duration'
            task: The task that was executed
            
        Returns:
            ReflectionResult with insights and recommendations
        """
        insights = []
        recommendations = []
        
        # Analyze success patterns
        successes = [h for h in history if h.get("success", False)]
        failures = [h for h in history if not h.get("success", False)]
        
        if not failures:
            insights.append("All execution steps completed successfully")
            recommendations.append("Continue current approach for similar tasks")
        elif len(failures) > len(successes):
            insights.append(f"Majority of steps failed ({len(failures)}/{len(history)})")
            recommendations.append("Consider different strategy or approach")
        
        # Detect error patterns
        error_types = {}
        for step in failures:
            error = step.get("error", "")
            if "timeout" in error.lower():
                error_types["timeout"] = error_types.get("timeout", 0) + 1
            elif "api" in error.lower():
                error_types["api_error"] = error_types.get("api_error", 0) + 1
            elif "rate limit" in error.lower():
                error_types["rate_limit"] = error_types.get("rate_limit", 0) + 1
            else:
                error_types["other"] = error_types.get("other", 0) + 1
        
        if error_types.get("timeout", 0) >= 2:
            insights.append(f"Detected {error_types['timeout']} timeout errors")
            recommendations.append("Add retry logic with exponential backoff")
            recommendations.append("Consider increasing timeout thresholds")
        
        if error_types.get("rate_limit", 0) >= 1:
            insights.append("Rate limiting detected")
            recommendations.append("Implement rate limiting handling")
            recommendations.append("Add request throttling")
        
        # Analyze timing patterns
        durations = [h.get("duration", 0) for h in history]
        if durations:
            avg_duration = sum(durations) / len(durations)
            if avg_duration > 5.0:
                insights.append(f"Steps taking long time (avg {avg_duration:.1f}s)")
                recommendations.append("Optimize slow operations")
        
        # Analyze action patterns
        actions = [h.get("action", "") for h in history]
        if "decompose" in actions and len(failures) > 0:
            insights.append("Task decomposition was attempted but errors occurred")
            recommendations.append("Review decomposition strategy")
        
        confidence = len(successes) / len(history) if history else 0.0
        
        return ReflectionResult(
            insights=insights or ["No specific patterns detected"],
            recommendations=recommendations or ["Continue monitoring"],
            confidence=confidence,
            task=task
        )
    
    def compare_with_baseline(
        self,
        new_reflection: ReflectionResult,
        baseline_reflection: ReflectionResult
    ) -> str:
        """Compare new reflection against baseline and describe improvement."""
        if new_reflection.confidence > baseline_reflection.confidence:
            improvement = new_reflection.confidence - baseline_reflection.confidence
            return f"Improved by {improvement:.1%} confidence"
        elif new_reflection.confidence < baseline_reflection.confidence:
            decline = baseline_reflection.confidence - new_reflection.confidence
            return f"Declined by {decline:.1%} confidence - review needed"
        else:
            return "No change in performance - stable"
    
    def _generate_lessons(self, metrics: PerformanceMetrics) -> str:
        """Generate lessons learned from metrics."""
        lessons = []
        
        if not metrics.success:
            lessons.append("Task failure indicates need for better planning or more tools")
        
        if metrics.steps_taken > 10:
            lessons.append("Complex tasks need better decomposition")
        
        if metrics.tool_calls == 0 and not metrics.success:
            lessons.append("Consider using available tools more effectively")
        
        if metrics.errors:
            lessons.append(f"Learned {len(metrics.errors)} error patterns to avoid")
        
        return "; ".join(lessons) if lessons else "No specific lessons"
    
    def _analyze_patterns(self):
        """Analyze performance patterns over time."""
        if len(self.metrics) < 3:
            return
        
        recent = self.metrics[-10:]  # Last 10 tasks
        success_rate = sum(1 for m in recent if m.success) / len(recent)
        avg_steps = sum(m.steps_taken for m in recent) / len(recent)
        
        self.patterns = {
            "success_rate": success_rate,
            "average_steps": avg_steps,
            "total_tasks": len(self.metrics),
            "improving": success_rate > 0.7
        }
    
    def get_improvement_suggestions(self) -> List[str]:
        """Get general improvement suggestions based on patterns."""
        suggestions = []
        
        if not self.patterns:
            return suggestions
        
        if self.patterns.get("success_rate", 1) < 0.7:
            suggestions.append("Success rate below 70% - focus on planning and error handling")
        
        if self.patterns.get("average_steps", 0) > 8:
            suggestions.append("Tasks taking many steps - improve decomposition strategy")
        
        # Check for recurring errors
        error_counts = {}
        for m in self.metrics:
            for e in m.errors:
                error_counts[e] = error_counts.get(e, 0) + 1
        
        for error, count in error_counts.items():
            if count > 2:
                suggestions.append(f"Recurring error '{error[:30]}...' ({count}x) - add specific handling")
        
        return suggestions
    
    def get_reflection_summary(self, n: int = 5) -> str:
        """Get summary of recent reflections."""
        recent = self.reflections[-n:]
        if not recent:
            return "No reflections yet"
        
        lines = ["=== Recent Reflections ==="]
        for r in recent:
            lines.append(f"\nTask: {r.task}")
            lines.append(f"  Well: {r.what_went_well}")
            lines.append(f"  Improve: {r.what_could_improve}")
            lines.append(f"  Lessons: {r.lessons_learned}")
        
        lines.append(f"\n=== Performance Patterns ===")
        for key, value in self.patterns.items():
            lines.append(f"  {key}: {value}")
        
        suggestions = self.get_improvement_suggestions()
        if suggestions:
            lines.append(f"\n=== Improvement Suggestions ===")
            for s in suggestions:
                lines.append(f"  • {s}")
        
        return "\n".join(lines)
    
    def _load(self):
        """Load data from storage."""
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                
                for m in data.get("metrics", []):
                    metric = PerformanceMetrics(
                        task=m["task"],
                        success=m["success"],
                        steps_taken=m["steps_taken"],
                        time_elapsed=m["time_elapsed"],
                        errors=m.get("errors", []),
                        tool_calls=m.get("tool_calls", 0),
                        timestamp=datetime.fromisoformat(m["timestamp"])
                    )
                    self.metrics.append(metric)
                
                for r in data.get("reflections", []):
                    reflection = Reflection(
                        task=r["task"],
                        what_went_well=r["what_went_well"],
                        what_could_improve=r["what_could_improve"],
                        lessons_learned=r["lessons_learned"],
                        suggested_changes=r.get("suggested_changes", []),
                        confidence=r.get("confidence", 0.5),
                        timestamp=datetime.fromisoformat(r["timestamp"])
                    )
                    self.reflections.append(reflection)
                
                self.patterns = data.get("patterns", {})
        except FileNotFoundError:
            pass
    
    def _save(self):
        """Save data to storage."""
        if self.storage_path:
            with open(self.storage_path, 'w') as f:
                json.dump({
                    "metrics": [m.to_dict() for m in self.metrics],
                    "reflections": [r.to_dict() for r in self.reflections],
                    "patterns": self.patterns
                }, f, indent=2)


class SelfImprover:
    """
    System for proposing and tracking self-improvements.
    """
    
    def __init__(self, storage_path: str = None):
        self.storage_path = storage_path
        self.proposals: List[Dict] = []
        self._load()
    
    def propose_change(
        self,
        component: str,
        change_description: str,
        rationale: str,
        expected_impact: str
    ) -> Dict:
        """
        Propose a change to the system.
        
        Args:
            component: Which component to change (e.g., "agent", "planner")
            change_description: What change to make
            rationale: Why this change is needed
            expected_impact: What improvement to expect
            
        Returns:
            Proposal dict with id and status
        """
        proposal = {
            "id": f"{component}_{len(self.proposals)}",
            "component": component,
            "change": change_description,
            "rationale": rationale,
            "expected_impact": expected_impact,
            "status": "proposed",  # proposed, approved, rejected, implemented
            "timestamp": datetime.now().isoformat()
        }
        
        self.proposals.append(proposal)
        self._save()
        return proposal
    
    def review_proposal(self, proposal_id: str, approved: bool, feedback: str = ""):
        """
        Review a proposed change.
        
        NOTE: This requires human review per safety guidelines.
        Changes are never auto-applied.
        """
        for p in self.proposals:
            if p["id"] == proposal_id:
                p["status"] = "approved" if approved else "rejected"
                p["review_feedback"] = feedback
                self._save()
                return p
        return None
    
    def get_pending_proposals(self) -> List[Dict]:
        """Get all proposals awaiting review."""
        return [p for p in self.proposals if p["status"] == "proposed"]
    
    def get_proposal_summary(self) -> str:
        """Get summary of all proposals."""
        lines = ["=== Self-Improvement Proposals ==="]
        
        by_status = {"proposed": [], "approved": [], "rejected": [], "implemented": []}
        for p in self.proposals:
            by_status[p["status"]].append(p)
        
        for status, proposals in by_status.items():
            if proposals:
                lines.append(f"\n{status.upper()} ({len(proposals)}):")
                for p in proposals:
                    lines.append(f"  • [{p['id']}] {p['component']}: {p['change'][:50]}...")
        
        return "\n".join(lines)
    
    def _load(self):
        """Load proposals from storage."""
        try:
            with open(self.storage_path, 'r') as f:
                self.proposals = json.load(f).get("proposals", [])
        except FileNotFoundError:
            pass
    
    def _save(self):
        """Save proposals to storage."""
        if self.storage_path:
            with open(self.storage_path, 'w') as f:
                json.dump({"proposals": self.proposals}, f, indent=2)


if __name__ == "__main__":
    # Demo
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        reflector = Reflector(storage_path=f"{tmpdir}/reflections.json")
        
        # Record some performance
        m1 = reflector.record_performance(
            task="Find capital of France",
            success=True,
            steps_taken=3,
            time_elapsed=2.5,
            tool_calls=1
        )
        
        m2 = reflector.record_performance(
            task="Analyze stock trends",
            success=False,
            steps_taken=10,
            time_elapsed=15.0,
            errors=["API timeout", "Invalid data format"],
            tool_calls=3
        )
        
        # Generate reflection
        r1 = reflector.reflect("Find capital of France", m1)
        r2 = reflector.reflect("Analyze stock trends", m2)
        
        print(reflector.get_reflection_summary())
        
        # Self-improvement proposals
        improver = SelfImprover(storage_path=f"{tmpdir}/proposals.json")
        
        improver.propose_change(
            component="agent",
            change_description="Add retry logic for API calls",
            rationale="Multiple API timeout errors observed",
            expected_impact="Reduce failure rate for external tool calls"
        )
        
        improver.propose_change(
            component="planner",
            change_description="Implement hierarchical decomposition for complex tasks",
            rationale="Tasks with >5 steps show higher failure rate",
            expected_impact="Improve success rate on complex tasks"
        )
        
        print("\n" + improver.get_proposal_summary())
        
        # Show pending proposals
        pending = improver.get_pending_proposals()
        print(f"\n⚠️  {len(pending)} proposals awaiting human review")
        print("   Safety: Changes must be reviewed before implementation")
