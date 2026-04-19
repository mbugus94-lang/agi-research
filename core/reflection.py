"""
Self-Reflection System for AGI agents.

Implements introspective capabilities inspired by:
- arXiv:2601.11658v1: Teacher LLM for evaluation and feedback
- arXiv:2604.14990: AI becoming a subject through self-reflection
- arXiv:2601.10599: Institutional AI with runtime monitoring

The reflection system enables agents to:
1. Analyze their own performance and decisions
2. Identify patterns of success and failure
3. Generate improvement recommendations
4. Update planning strategies based on experience
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
import json
import statistics


class ReflectionScope(Enum):
    """Scope of reflection analysis."""
    TASK = auto()       # Single task reflection
    PLAN = auto()       # Plan-level reflection
    SESSION = auto()    # Multi-plan session reflection
    SYSTEM = auto()     # Long-term system-wide reflection


class ReflectionType(Enum):
    """Types of reflection."""
    PERFORMANCE = "performance"    # Success/failure analysis
    DECISION = "decision"          # Decision quality review
    LEARNING = "learning"          # Pattern extraction
    STRATEGY = "strategy"          # Approach effectiveness
    ERROR = "error"                # Failure root cause


@dataclass
class PerformanceMetrics:
    """Metrics for performance analysis."""
    tasks_total: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    
    # Timing
    total_time: float = 0.0  # seconds
    avg_task_time: float = 0.0
    min_task_time: Optional[float] = None
    max_task_time: Optional[float] = None
    
    # Quality
    quality_scores: List[float] = field(default_factory=list)  # 0-1 scale
    avg_quality: float = 0.0
    
    # Resources
    tokens_used: int = 0
    api_calls: int = 0
    tools_used: Dict[str, int] = field(default_factory=dict)
    
    def calculate_stats(self) -> None:
        """Calculate derived statistics."""
        if self.quality_scores:
            self.avg_quality = statistics.mean(self.quality_scores)
        
        completed = self.tasks_completed
        if completed > 0:
            self.avg_task_time = self.total_time / completed
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tasks_total": self.tasks_total,
            "tasks_completed": self.tasks_completed,
            "tasks_failed": self.tasks_failed,
            "success_rate": self.tasks_completed / self.tasks_total if self.tasks_total > 0 else 0,
            "total_time": self.total_time,
            "avg_task_time": self.avg_task_time,
            "avg_quality": self.avg_quality,
            "tokens_used": self.tokens_used,
            "api_calls": self.api_calls,
            "tools_used": self.tools_used
        }


@dataclass
class ReflectionReport:
    """A structured reflection report."""
    id: str
    timestamp: datetime
    scope: ReflectionScope
    reflection_type: ReflectionType
    
    # Analysis content
    summary: str
    successes: List[str] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)
    patterns_identified: List[str] = field(default_factory=list)
    root_causes: List[str] = field(default_factory=list)
    
    # Recommendations
    recommendations: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metrics
    metrics: Optional[PerformanceMetrics] = None
    
    # Action items
    action_items: List[str] = field(default_factory=list)
    priority_actions: List[str] = field(default_factory=list)
    
    # References
    related_plan_ids: List[str] = field(default_factory=list)
    related_task_ids: List[str] = field(default_factory=list)
    
    # Self-modification tracking (for safety)
    suggests_code_change: bool = False
    requires_human_review: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "scope": self.scope.name,
            "reflection_type": self.reflection_type.value,
            "summary": self.summary,
            "successes": self.successes,
            "failures": self.failures,
            "patterns_identified": self.patterns_identified,
            "root_causes": self.root_causes,
            "recommendations": self.recommendations,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "action_items": self.action_items,
            "priority_actions": self.priority_actions,
            "related_plan_ids": self.related_plan_ids,
            "related_task_ids": self.related_task_ids,
            "suggests_code_change": self.suggests_code_change,
            "requires_human_review": self.requires_human_review
        }


class ReflectionEngine:
    """
    Core engine for generating reflection reports.
    Implements the Teacher LLM pattern from self-evolving agent research.
    """
    
    def __init__(self, memory_system: Optional[Any] = None):
        self.memory = memory_system
        self.reflection_history: List[ReflectionReport] = []
        self.pattern_database: Dict[str, List[Dict]] = {}  # pattern_type -> examples
    
    def reflect_on_task(
        self,
        task_description: str,
        task_result: Any,
        execution_trace: List[Dict[str, Any]],
        success: bool,
        quality_score: Optional[float] = None
    ) -> ReflectionReport:
        """
        Generate reflection on a single task execution.
        
        Args:
            task_description: What the task was
            task_result: The output/result
            execution_trace: Step-by-step execution log
            success: Whether task succeeded
            quality_score: Optional quality rating (0-1)
        """
        report_id = f"task_ref_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        successes = []
        failures = []
        patterns = []
        root_causes = []
        
        if success:
            successes.append(f"Successfully completed: {task_description}")
            if execution_trace:
                # Identify what worked
                patterns.append("Execution followed expected path")
        else:
            failures.append(f"Failed to complete: {task_description}")
            # Analyze trace for failure point
            for step in execution_trace:
                if step.get("error") or step.get("status") == "failed":
                    root_causes.append(f"Failure at step: {step.get('step', 'unknown')}")
                    if "error" in step:
                        root_causes.append(f"Error: {step['error']}")
        
        # Extract patterns from trace
        tool_usage = {}
        for step in execution_trace:
            if "tool" in step:
                tool = step["tool"]
                tool_usage[tool] = tool_usage.get(tool, 0) + 1
        
        if tool_usage:
            most_used = max(tool_usage.items(), key=lambda x: x[1])
            patterns.append(f"Primary tool used: {most_used[0]} ({most_used[1]} times)")
        
        # Generate recommendations
        recommendations = []
        if not success:
            recommendations.append({
                "type": "retry_strategy",
                "description": "Consider alternative approach or tool selection",
                "priority": "high"
            })
        
        if quality_score and quality_score < 0.7:
            recommendations.append({
                "type": "quality_improvement",
                "description": "Review output quality standards and validation",
                "priority": "medium"
            })
        
        report = ReflectionReport(
            id=report_id,
            timestamp=datetime.now(),
            scope=ReflectionScope.TASK,
            reflection_type=ReflectionType.PERFORMANCE,
            summary=f"Task reflection: {'Success' if success else 'Failure'} on '{task_description[:50]}...'",
            successes=successes,
            failures=failures,
            patterns_identified=patterns,
            root_causes=root_causes,
            recommendations=recommendations,
            action_items=[r["description"] for r in recommendations]
        )
        
        self.reflection_history.append(report)
        return report
    
    def reflect_on_plan(
        self,
        plan_id: str,
        plan_goal: str,
        tasks_data: List[Dict[str, Any]],
        overall_success: bool
    ) -> ReflectionReport:
        """
        Generate reflection on a complete plan execution.
        
        Args:
            plan_id: Plan identifier
            plan_goal: The goal of the plan
            tasks_data: List of task execution data
            overall_success: Whether plan succeeded overall
        """
        report_id = f"plan_ref_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Calculate metrics
        metrics = PerformanceMetrics()
        metrics.tasks_total = len(tasks_data)
        
        for task in tasks_data:
            if task.get("status") == "completed":
                metrics.tasks_completed += 1
                if task.get("duration"):
                    metrics.total_time += task["duration"]
                if task.get("quality_score"):
                    metrics.quality_scores.append(task["quality_score"])
            elif task.get("status") == "failed":
                metrics.tasks_failed += 1
            
            # Count tool usage
            for tool in task.get("tools_used", []):
                metrics.tools_used[tool] = metrics.tools_used.get(tool, 0) + 1
        
        metrics.calculate_stats()
        
        # Analyze patterns
        successes = []
        failures = []
        patterns = []
        recommendations = []
        
        if overall_success:
            successes.append(f"Plan achieved goal: {plan_goal}")
            if metrics.avg_quality > 0.8:
                successes.append(f"High quality output (avg: {metrics.avg_quality:.2f})")
        else:
            failures.append(f"Plan failed to achieve goal: {plan_goal}")
            if metrics.tasks_failed > 0:
                failures.append(f"{metrics.tasks_failed} tasks failed")
        
        # Pattern: Dependency bottlenecks
        blocked_tasks = [t for t in tasks_data if t.get("blocked_by")]
        if blocked_tasks:
            patterns.append(f"{len(blocked_tasks)} tasks had dependency issues")
            recommendations.append({
                "type": "planning_improvement",
                "description": "Review task dependency structure for bottlenecks",
                "priority": "medium"
            })
        
        # Pattern: Tool usage
        if metrics.tools_used:
            patterns.append(f"Tools used: {', '.join(metrics.tools_used.keys())}")
        
        # Pattern: Time estimation accuracy
        estimated_times = [t.get("estimated_duration") for t in tasks_data if t.get("estimated_duration")]
        actual_times = [t.get("duration") for t in tasks_data if t.get("duration")]
        if estimated_times and actual_times:
            avg_estimate = statistics.mean(estimated_times)
            avg_actual = statistics.mean(actual_times)
            if abs(avg_estimate - avg_actual) / avg_actual > 0.3:
                patterns.append("Time estimation significantly off - review estimation model")
        
        report = ReflectionReport(
            id=report_id,
            timestamp=datetime.now(),
            scope=ReflectionScope.PLAN,
            reflection_type=ReflectionType.STRATEGY,
            summary=f"Plan reflection for '{plan_goal[:50]}...': {metrics.tasks_completed}/{metrics.tasks_total} tasks completed",
            successes=successes,
            failures=failures,
            patterns_identified=patterns,
            recommendations=recommendations,
            metrics=metrics,
            action_items=[r["description"] for r in recommendations],
            related_plan_ids=[plan_id]
        )
        
        self.reflection_history.append(report)
        return report
    
    def reflect_on_session(
        self,
        session_plans: List[Dict[str, Any]],
        session_goal: Optional[str] = None
    ) -> ReflectionReport:
        """
        Generate reflection across multiple plans in a session.
        
        Args:
            session_plans: Data about plans executed in session
            session_goal: Overall session objective
        """
        report_id = f"session_ref_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Aggregate metrics
        all_tasks = []
        for plan in session_plans:
            all_tasks.extend(plan.get("tasks", []))
        
        metrics = PerformanceMetrics()
        metrics.tasks_total = len(all_tasks)
        metrics.tasks_completed = sum(1 for t in all_tasks if t.get("status") == "completed")
        metrics.tasks_failed = sum(1 for t in all_tasks if t.get("status") == "failed")
        
        # Collect patterns
        patterns = []
        recommendations = []
        
        # Pattern: Success rate trend
        if metrics.tasks_total > 0:
            success_rate = metrics.tasks_completed / metrics.tasks_total
            if success_rate < 0.7:
                patterns.append(f"Low success rate: {success_rate:.1%}")
                recommendations.append({
                    "type": "system_improvement",
                    "description": "Investigate systemic causes of task failures",
                    "priority": "high"
                })
            elif success_rate > 0.9:
                patterns.append(f"High success rate: {success_rate:.1%}")
                patterns.append("Consider increasing task difficulty or complexity")
        
        # Pattern: Common failure modes
        failure_types = {}
        for task in all_tasks:
            if task.get("status") == "failed" and task.get("failure_type"):
                ft = task["failure_type"]
                failure_types[ft] = failure_types.get(ft, 0) + 1
        
        if failure_types:
            most_common = max(failure_types.items(), key=lambda x: x[1])
            patterns.append(f"Most common failure: {most_common[0]} ({most_common[1]} times)")
        
        report = ReflectionReport(
            id=report_id,
            timestamp=datetime.now(),
            scope=ReflectionScope.SESSION,
            reflection_type=ReflectionType.LEARNING,
            summary=f"Session reflection: {metrics.tasks_completed}/{metrics.tasks_total} tasks across {len(session_plans)} plans",
            patterns_identified=patterns,
            recommendations=recommendations,
            metrics=metrics,
            related_plan_ids=[p.get("id") for p in session_plans],
            action_items=[r["description"] for r in recommendations]
        )
        
        self.reflection_history.append(report)
        return report
    
    def generate_improvement_proposals(
        self,
        report: ReflectionReport
    ) -> List[Dict[str, Any]]:
        """
        Generate specific improvement proposals from a reflection.
        These can be fed to the self-analysis system for review.
        
        Returns list of proposals with structure compatible with self_analysis.py
        """
        proposals = []
        
        for rec in report.recommendations:
            proposal = {
                "id": f"prop_{report.id}_{len(proposals)}",
                "title": rec["description"],
                "improvement_type": rec["type"],
                "component": "planning" if rec["type"] in ["planning_improvement", "retry_strategy"] else "execution",
                "description": rec["description"],
                "rationale": f"Identified in reflection {report.id}",
                "expected_impact": f"Priority: {rec.get('priority', 'medium')}",
                "risk_level": "NORMAL",
                "requires_review": True,
                "source_reflection": report.id
            }
            proposals.append(proposal)
        
        return proposals
    
    def get_insights_for_planning(
        self,
        goal_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get insights to inform future planning.
        Returns aggregated patterns and recommendations.
        """
        # Filter relevant reflections
        relevant = [
            r for r in self.reflection_history
            if goal_type is None or r.reflection_type.value == goal_type
        ]
        
        if not relevant:
            return {
                "successful_approaches": [],
                "failed_approaches": [],
                "suggested_improvements": []
            }
        
        # Aggregate insights
        successful_approaches = []
        failed_approaches = []
        suggestions = []
        
        for report in relevant:
            successful_approaches.extend(report.successes)
            failed_approaches.extend(report.failures)
            suggestions.extend(report.action_items)
        
        # Get most common suggestions
        from collections import Counter
        suggestion_counts = Counter(suggestions)
        top_suggestions = [s for s, _ in suggestion_counts.most_common(5)]
        
        return {
            "successful_approaches": list(set(successful_approaches))[:5],
            "failed_approaches": list(set(failed_approaches))[:5],
            "suggested_improvements": top_suggestions,
            "total_reflections_analyzed": len(relevant)
        }


class ReflectivePlanner:
    """
    Planner that integrates reflection for continuous improvement.
    Bridges the gap between planning and reflection systems.
    """
    
    def __init__(self, planner_engine: Any, reflection_engine: ReflectionEngine):
        self.planner = planner_engine
        self.reflection = reflection_engine
        self.planning_history: List[Dict] = []
    
    def plan_and_execute(
        self,
        goal: str,
        execute_fn: Callable[[Any], Any],
        reflect: bool = True
    ) -> Dict[str, Any]:
        """
        Plan, execute, and optionally reflect on results.
        
        Args:
            goal: The goal to achieve
            execute_fn: Function to execute the plan
            reflect: Whether to generate reflection after execution
        
        Returns:
            Dict with plan, result, and optional reflection report
        """
        # Get insights from past reflections
        insights = self.reflection.get_insights_for_planning()
        
        # Create plan informed by insights
        plan = self.planner.plan_with_reflection(goal, insights)
        
        # Execute
        result = execute_fn(plan)
        
        output = {
            "plan": plan,
            "result": result,
            "reflection": None
        }
        
        # Generate reflection if requested
        if reflect:
            reflection_report = self.reflection.reflect_on_plan(
                plan_id=plan.id,
                plan_goal=goal,
                tasks_data=result.get("tasks", []),
                overall_success=result.get("success", False)
            )
            output["reflection"] = reflection_report
            
            # Store for future planning
            self.planning_history.append({
                "plan_id": plan.id,
                "goal": goal,
                "success": result.get("success", False),
                "reflection_id": reflection_report.id
            })
        
        return output


# Convenience functions
def create_reflection_engine(memory_system: Optional[Any] = None) -> ReflectionEngine:
    """Create a new reflection engine."""
    return ReflectionEngine(memory_system=memory_system)


def quick_reflect(
    task_description: str,
    success: bool,
    notes: Optional[List[str]] = None
) -> ReflectionReport:
    """
    Quick reflection for simple use cases.
    
    Args:
        task_description: What was attempted
        success: Whether it succeeded
        notes: Optional list of observations
    """
    engine = ReflectionEngine()
    return engine.reflect_on_task(
        task_description=task_description,
        task_result={"success": success},
        execution_trace=[{"note": n} for n in (notes or [])],
        success=success
    )
