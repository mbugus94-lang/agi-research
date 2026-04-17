"""
Integration Module: Connecting Reflection, Planner, and Memory

Enables self-improving closed loop: execute → reflect → plan → improve
Based on research insights:
- Reflection data informs planning strategies
- Tiered memory stores reflection reports
- Performance patterns guide plan selection
- Continuous improvement through integrated feedback
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from datetime import datetime
import json
import asyncio


class FeedbackType(Enum):
    """Types of feedback that can flow between components."""
    PERFORMANCE_INSIGHT = "performance_insight"
    STRATEGY_SUGGESTION = "strategy_suggestion"
    MEMORY_UPDATE = "memory_update"
    PLAN_ADJUSTMENT = "plan_adjustment"
    CAPABILITY_GAP = "capability_gap"


class IntegrationPriority(Enum):
    """Priority levels for integration actions."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    BACKGROUND = 5


@dataclass
class ComponentFeedback:
    """Feedback flowing between components."""
    feedback_type: FeedbackType
    source_component: str
    target_component: str
    content: Dict[str, Any]
    priority: IntegrationPriority
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    processed: bool = False


@dataclass
class ReflectionToPlanningBridge:
    """Bridge connecting reflection insights to planning."""
    capability_name: str
    proficiency_score: float
    confidence: float
    trend: str  # "improving", "declining", "stable"
    suggested_strategies: List[str]
    priority: IntegrationPriority
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class PerformanceInformedPlan:
    """Plan enriched with performance data."""
    plan_id: str
    task_type: str
    base_strategy: str
    suggested_strategy: Optional[str] = None
    expected_success_rate: float = 0.0
    risk_assessment: Dict[str, Any] = field(default_factory=dict)
    adaptations: List[str] = field(default_factory=list)


class ComponentInterface:
    """Abstract interface for components in the integration system."""
    
    def __init__(self, name: str):
        self.name = name
        self.feedback_inbox: List[ComponentFeedback] = []
        self.feedback_outbox: List[ComponentFeedback] = []
    
    def receive_feedback(self, feedback: ComponentFeedback):
        """Receive feedback from other components."""
        self.feedback_inbox.append(feedback)
    
    def send_feedback(self, feedback: ComponentFeedback):
        """Send feedback to other components."""
        self.feedback_outbox.append(feedback)
    
    def process_feedback(self) -> List[ComponentFeedback]:
        """Process received feedback and return actionable items."""
        actionable = []
        for fb in self.feedback_inbox:
            if not fb.processed and fb.priority in [IntegrationPriority.CRITICAL, IntegrationPriority.HIGH]:
                actionable.append(fb)
                fb.processed = True
        return actionable


class IntegratedReflectionEngine(ComponentInterface):
    """Reflection engine integrated with planning and memory."""
    
    def __init__(self, agent_id: str = "integrated_agent"):
        super().__init__("reflection")
        self.agent_id = agent_id
        self.performance_history: Dict[str, List[Dict]] = {}
        self.insights_cache: Dict[str, Any] = {}
    
    def record_execution(self, task_id: str, task_type: str, success: bool, 
                         execution_time_ms: float, quality_score: float, 
                         error_type: Optional[str] = None):
        """Record task execution for reflection."""
        if task_type not in self.performance_history:
            self.performance_history[task_type] = []
        
        record = {
            "task_id": task_id,
            "success": success,
            "execution_time_ms": execution_time_ms,
            "quality_score": quality_score,
            "error_type": error_type,
            "timestamp": datetime.now().isoformat()
        }
        self.performance_history[task_type].append(record)
        
        # Maintain window of last 50 records per task type
        if len(self.performance_history[task_type]) > 50:
            self.performance_history[task_type] = self.performance_history[task_type][-50:]
    
    def analyze_and_send_insights(self, task_type: str) -> ReflectionToPlanningBridge:
        """Analyze performance and send insights to planning."""
        history = self.performance_history.get(task_type, [])
        if len(history) < 5:
            return None
        
        # Calculate trend
        recent = history[-10:]
        older = history[-20:-10] if len(history) >= 20 else history[:len(history)//2]
        
        recent_success = sum(1 for r in recent if r["success"]) / len(recent)
        older_success = sum(1 for r in older if r["success"]) / len(older)
        
        if recent_success > older_success + 0.1:
            trend = "improving"
        elif recent_success < older_success - 0.1:
            trend = "declining"
        else:
            trend = "stable"
        
        # Generate suggestions based on analysis
        suggestions = []
        if trend == "declining":
            suggestions.append(f"Consider alternative approach for {task_type}")
            suggestions.append("Review recent error patterns for systematic issues")
        elif trend == "improving":
            suggestions.append(f"Current strategy working well for {task_type}")
            suggestions.append("Consider increasing task complexity gradually")
        
        # Error analysis
        error_counts = {}
        for r in history:
            if r.get("error_type"):
                error_counts[r["error_type"]] = error_counts.get(r["error_type"], 0) + 1
        
        if error_counts:
            most_common = max(error_counts.items(), key=lambda x: x[1])
            suggestions.append(f"Address frequent error: {most_common[0]} ({most_common[1]} occurrences)")
        
        bridge = ReflectionToPlanningBridge(
            capability_name=task_type,
            proficiency_score=recent_success,
            confidence=min(len(history) / 50.0, 1.0),
            trend=trend,
            suggested_strategies=suggestions,
            priority=IntegrationPriority.HIGH if trend == "declining" else IntegrationPriority.MEDIUM
        )
        
        # Send feedback to planning
        feedback = ComponentFeedback(
            feedback_type=FeedbackType.PERFORMANCE_INSIGHT,
            source_component="reflection",
            target_component="planning",
            content={
                "bridge": bridge,
                "error_counts": error_counts,
                "success_rate": recent_success
            },
            priority=bridge.priority
        )
        self.send_feedback(feedback)
        
        return bridge


class IntegratedPlanner(ComponentInterface):
    """Planner that uses reflection insights and memory."""
    
    def __init__(self):
        super().__init__("planning")
        self.strategy_library: Dict[str, List[str]] = {
            "code_generation": ["direct_generation", "iterative_refinement", "test_driven"],
            "web_search": ["parallel_search", "sequential_deep_dive", "focused_query"],
            "analysis": ["comprehensive", "quick_scan", "targeted"],
            "default": ["standard", "conservative", "aggressive"]
        }
        self.active_plans: Dict[str, PerformanceInformedPlan] = {}
        self.performance_insights: Dict[str, ReflectionToPlanningBridge] = {}
    
    def update_from_reflection(self, bridge: ReflectionToPlanningBridge):
        """Update planning strategy based on reflection insights."""
        self.performance_insights[bridge.capability_name] = bridge
    
    def create_informed_plan(self, task_type: str, task_description: str) -> PerformanceInformedPlan:
        """Create a plan informed by performance data."""
        plan_id = f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{task_type}"
        
        # Get base strategies
        strategies = self.strategy_library.get(task_type, self.strategy_library["default"])
        base_strategy = strategies[0]
        
        # Modify based on reflection insights
        suggested_strategy = None
        adaptations = []
        expected_success = 0.7  # Default expectation
        
        insight = self.performance_insights.get(task_type)
        if insight:
            expected_success = insight.proficiency_score
            
            if insight.trend == "improving":
                # Use more advanced strategies
                if len(strategies) > 1:
                    suggested_strategy = strategies[-1]  # Most advanced
                adaptations.append("Leverage recent success pattern")
            elif insight.trend == "declining":
                # Use conservative approach
                suggested_strategy = strategies[0]  # Most conservative
                adaptations.append("Apply recovery strategy due to declining performance")
            
            if insight.suggested_strategies:
                adaptations.extend(insight.suggested_strategies[:2])
        
        plan = PerformanceInformedPlan(
            plan_id=plan_id,
            task_type=task_type,
            base_strategy=base_strategy,
            suggested_strategy=suggested_strategy or base_strategy,
            expected_success_rate=expected_success,
            risk_assessment={
                "confidence": insight.confidence if insight else 0.5,
                "trend": insight.trend if insight else "unknown",
                "risk_level": "high" if expected_success < 0.5 else "medium" if expected_success < 0.8 else "low"
            },
            adaptations=adaptations
        )
        
        self.active_plans[plan_id] = plan
        
        # Send feedback to reflection about plan creation
        feedback = ComponentFeedback(
            feedback_type=FeedbackType.PLAN_ADJUSTMENT,
            source_component="planning",
            target_component="reflection",
            content={
                "plan_id": plan_id,
                "task_type": task_type,
                "expected_success": expected_success,
                "adaptations": adaptations
            },
            priority=IntegrationPriority.MEDIUM
        )
        self.send_feedback(feedback)
        
        return plan


class IntegratedMemory(ComponentInterface):
    """Memory system that stores reflection reports and planning history."""
    
    def __init__(self, max_entries: int = 1000):
        super().__init__("memory")
        self.reflection_reports: List[Dict] = []
        self.planning_history: List[Dict] = []
        self.performance_trends: Dict[str, List[Dict]] = {}
        self.max_entries = max_entries
    
    def store_reflection_report(self, report: Dict, priority: IntegrationPriority = IntegrationPriority.MEDIUM):
        """Store a reflection report with tiered memory management."""
        entry = {
            "type": "reflection_report",
            "content": report,
            "priority": priority.name,
            "stored_at": datetime.now().isoformat(),
            "access_count": 0
        }
        self.reflection_reports.append(entry)
        
        # Maintain size limit with priority-based eviction
        if len(self.reflection_reports) > self.max_entries:
            # Remove lowest priority, oldest entries
            sorted_entries = sorted(
                self.reflection_reports,
                key=lambda x: (IntegrationPriority[x["priority"]].value, x["stored_at"])
            )
            self.reflection_reports = sorted_entries[len(sorted_entries) - self.max_entries:]
    
    def store_planning_history(self, plan: PerformanceInformedPlan, outcome: Optional[Dict] = None):
        """Store planning history with outcomes."""
        entry = {
            "plan_id": plan.plan_id,
            "task_type": plan.task_type,
            "strategy": plan.suggested_strategy,
            "expected_success": plan.expected_success_rate,
            "outcome": outcome,
            "created_at": datetime.now().isoformat()
        }
        self.planning_history.append(entry)
        
        if len(self.planning_history) > self.max_entries:
            self.planning_history = self.planning_history[-self.max_entries:]
    
    def retrieve_relevant_insights(self, task_type: str, limit: int = 5) -> List[Dict]:
        """Retrieve relevant insights for a task type."""
        # Filter by task type and sort by recency and access count
        relevant = [
            r for r in self.reflection_reports 
            if r["content"].get("task_type") == task_type or 
               r["content"].get("capability_name") == task_type
        ]
        
        # Update access counts
        for r in relevant[:limit]:
            r["access_count"] = r.get("access_count", 0) + 1
        
        return relevant[:limit]
    
    def get_performance_trend(self, task_type: str, window: int = 10) -> Optional[Dict]:
        """Get performance trend for a task type."""
        history = self.performance_trends.get(task_type, [])
        if not history:
            return None
        
        recent = history[-window:]
        return {
            "task_type": task_type,
            "data_points": len(recent),
            "average_score": sum(r.get("score", 0) for r in recent) / len(recent),
            "trend_direction": self._calculate_trend_direction(recent)
        }
    
    def _calculate_trend_direction(self, data: List[Dict]) -> str:
        """Calculate trend direction from data points."""
        if len(data) < 3:
            return "insufficient_data"
        
        first_half = data[:len(data)//2]
        second_half = data[len(data)//2:]
        
        first_avg = sum(d.get("score", 0) for d in first_half) / len(first_half)
        second_avg = sum(d.get("score", 0) for d in second_half) / len(second_half)
        
        diff = second_avg - first_avg
        if diff > 0.1:
            return "improving"
        elif diff < -0.1:
            return "declining"
        return "stable"


class SelfImprovingLoop:
    """Main integration orchestrator managing the self-improving loop."""
    
    def __init__(self, agent_id: str = "self_improving_agent"):
        self.agent_id = agent_id
        self.reflection = IntegratedReflectionEngine(agent_id)
        self.planner = IntegratedPlanner()
        self.memory = IntegratedMemory()
        self.execution_count = 0
        self.improvement_cycles = 0
    
    def execute_task(self, task_type: str, task_description: str, 
                     execute_fn: Callable[[PerformanceInformedPlan], Dict]) -> Dict:
        """
        Execute a task through the self-improving loop:
        1. Retrieve insights from memory
        2. Create informed plan
        3. Execute with monitoring
        4. Reflect on results
        5. Store in memory
        """
        # Step 1: Retrieve relevant insights
        insights = self.memory.retrieve_relevant_insights(task_type)
        for insight in insights:
            if "bridge" in insight.get("content", {}):
                self.planner.update_from_reflection(insight["content"]["bridge"])
        
        # Step 2: Create informed plan
        plan = self.planner.create_informed_plan(task_type, task_description)
        
        # Step 3: Execute
        start_time = datetime.now()
        try:
            result = execute_fn(plan)
            success = result.get("success", True)
            quality_score = result.get("quality", 0.8)
            error = result.get("error")
        except Exception as e:
            result = {"success": False, "error": str(e)}
            success = False
            quality_score = 0.0
            error = str(e)
        
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        
        # Step 4: Reflect
        task_id = f"task_{self.execution_count}"
        self.reflection.record_execution(
            task_id=task_id,
            task_type=task_type,
            success=success,
            execution_time_ms=execution_time,
            quality_score=quality_score,
            error_type=error
        )
        
        # Generate and send insights
        bridge = self.reflection.analyze_and_send_insights(task_type)
        
        # Step 5: Store in memory
        self.memory.store_planning_history(plan, {
            "success": success,
            "quality": quality_score,
            "execution_time_ms": execution_time
        })
        
        if bridge:
            self.memory.store_reflection_report({
                "task_type": task_type,
                "bridge": bridge,
                "timestamp": datetime.now().isoformat()
            })
        
        self.execution_count += 1
        
        # Process feedback between components
        self._process_component_feedback()
        
        return {
            "task_id": task_id,
            "success": success,
            "plan": plan,
            "execution_time_ms": execution_time,
            "quality_score": quality_score,
            "insights_applied": len(insights),
            "feedback_generated": bridge is not None
        }
    
    def _process_component_feedback(self):
        """Process feedback flowing between components."""
        # Reflection to Planning
        for fb in self.reflection.feedback_outbox:
            if fb.target_component == "planning":
                if fb.content.get("bridge"):
                    self.planner.update_from_reflection(fb.content["bridge"])
                fb.processed = True
        
        # Planning to Reflection
        for fb in self.planner.feedback_outbox:
            if fb.target_component == "reflection":
                # Reflection receives plan feedback
                fb.processed = True
        
        # Clear processed feedback
        self.reflection.feedback_outbox = [fb for fb in self.reflection.feedback_outbox if not fb.processed]
        self.planner.feedback_outbox = [fb for fb in self.planner.feedback_outbox if not fb.processed]
    
    def get_system_status(self) -> Dict:
        """Get comprehensive status of the integrated system."""
        return {
            "agent_id": self.agent_id,
            "execution_count": self.execution_count,
            "improvement_cycles": self.improvement_cycles,
            "reflection": {
                "task_types_tracked": len(self.reflection.performance_history),
                "total_records": sum(len(h) for h in self.reflection.performance_history.values()),
                "pending_feedback": len(self.reflection.feedback_outbox)
            },
            "planning": {
                "active_plans": len(self.planner.active_plans),
                "insights_loaded": len(self.planner.performance_insights),
                "pending_feedback": len(self.planner.feedback_outbox)
            },
            "memory": {
                "reflection_reports": len(self.memory.reflection_reports),
                "planning_history": len(self.memory.planning_history),
                "performance_trends": len(self.memory.performance_trends)
            },
            "feedback_flows": {
                "reflection_to_planning": sum(1 for fb in self.planner.feedback_inbox if fb.source_component == "reflection"),
                "planning_to_reflection": sum(1 for fb in self.reflection.feedback_inbox if fb.source_component == "planning")
            }
        }
    
    def export_state(self) -> Dict:
        """Export complete state for persistence."""
        return {
            "agent_id": self.agent_id,
            "execution_count": self.execution_count,
            "improvement_cycles": self.improvement_cycles,
            "reflection_history": self.reflection.performance_history,
            "memory_reports": self.memory.reflection_reports,
            "planning_history": self.memory.planning_history,
            "exported_at": datetime.now().isoformat()
        }
    
    def import_state(self, state: Dict):
        """Import state from persisted data."""
        self.agent_id = state.get("agent_id", self.agent_id)
        self.execution_count = state.get("execution_count", 0)
        self.improvement_cycles = state.get("improvement_cycles", 0)
        self.reflection.performance_history = state.get("reflection_history", {})
        self.memory.reflection_reports = state.get("memory_reports", [])
        self.memory.planning_history = state.get("planning_history", [])


# Convenience function for quick integration
def create_integrated_agent(agent_id: str = "integrated_agent") -> SelfImprovingLoop:
    """Create a fully integrated self-improving agent."""
    return SelfImprovingLoop(agent_id)
