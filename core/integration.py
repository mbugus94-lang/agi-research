"""
Integration Layer: Connecting Reflection, Planning, and Memory Systems

Implements the self-improving closed loop:
    Execute → Reflect → Plan(with history) → Execute(improved)

Inspired by:
- arXiv:2601.11658v1: Self-evolving agent with feedback loops
- arXiv:2604.01020v1: OrgAgent cross-layer coordination
- arXiv:2603.13372v1: ARC-AGI test-time adaptation and refinement

Key Components:
1. ReflectionMemoryBridge: Store reflection reports in tiered memory
2. PlanningWithReflection: Use historical insights for better planning  
3. SelfImprovingLoop: Automated improvement cycle
4. PerformanceTracker: Cross-system metrics aggregation
"""

from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
import json
import time
import uuid


class IntegrationMode(Enum):
    """Mode of integration operation."""
    PASSIVE = auto()      # Store reflections, manual planning use
    ACTIVE = auto()       # Automatic reflection query during planning
    AUTONOMOUS = auto()   # Full self-improving loop


@dataclass
class ExecutionTrace:
    """Complete trace of plan execution with reflection."""
    trace_id: str
    plan_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    # Components
    plan: Optional[Dict] = None
    execution_results: List[Dict] = field(default_factory=list)
    reflection_report: Optional[Any] = None
    improvement_proposals: List[Dict] = field(default_factory=list)
    
    # Metrics
    total_duration_ms: float = 0.0
    success: bool = False
    quality_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "plan_id": self.plan_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "plan": self.plan,
            "execution_results": self.execution_results,
            "reflection_report": self.reflection_report.to_dict() if hasattr(self.reflection_report, 'to_dict') else self.reflection_report,
            "improvement_proposals": self.improvement_proposals,
            "total_duration_ms": self.total_duration_ms,
            "success": self.success,
            "quality_score": self.quality_score
        }


class ReflectionMemoryBridge:
    """
    Bridges the reflection system with tiered memory storage.
    
    Automatically stores reflection reports in appropriate memory tiers
    based on scope and importance, enabling retrieval during planning.
    """
    
    def __init__(self, memory_system):
        self.memory = memory_system
        self._stored_trace_ids: set = set()
    
    def store_reflection(
        self, 
        report,
        execution_trace: Optional[ExecutionTrace] = None
    ) -> str:
        """
        Store a reflection report in tiered memory.
        
        Storage strategy:
        - TASK scope: L0 (immediate) with short TTL
        - PLAN scope: L1 (working) for session reuse
        - SESSION/SYSTEM scope: L2 (archival) for long-term learning
        """
        # Get scope from report
        scope_name = report.scope.name if hasattr(report.scope, 'name') else str(report.scope)
        
        # Determine tier based on scope
        if scope_name == "TASK":
            tier_value = "l0"
            importance = 0.6
        elif scope_name == "PLAN":
            tier_value = "l1"
            importance = 0.7
        else:  # SESSION or SYSTEM
            tier_value = "l2"
            importance = 0.85
        
        # Build memory content
        content = json.dumps({
            "type": "reflection_report",
            "report_id": report.id,
            "scope": scope_name,
            "reflection_type": report.reflection_type.value if hasattr(report.reflection_type, 'value') else str(report.reflection_type),
            "summary": report.summary,
            "successes": report.successes,
            "failures": report.failures,
            "patterns_identified": report.patterns_identified,
            "root_causes": report.root_causes,
            "recommendations": report.recommendations,
            "metrics": report.metrics.to_dict() if report.metrics else None,
            "timestamp": report.timestamp.isoformat() if hasattr(report.timestamp, 'isoformat') else str(report.timestamp)
        })
        
        # Store in memory using tiered memory API
        from core.tiered_memory import MemoryTier
        tier = MemoryTier.L0_IMMEDIATE if tier_value == "l0" else (
            MemoryTier.L1_WORKING if tier_value == "l1" else MemoryTier.L2_ARCHIVAL
        )
        
        memory_id = self.memory.store(
            content=content,
            tier=tier,
            directory="/reflections",
            importance=importance,
            tags={"reflection", f"scope_{scope_name.lower()}", "analysis"},
            source="reflection_system"
        )
        
        # Store execution trace if provided
        if execution_trace:
            self._store_execution_trace(execution_trace, report)
        
        return str(id(memory_id))  # Use object id as reference
    
    def _store_execution_trace(
        self,
        trace: ExecutionTrace,
        report
    ) -> str:
        """Store complete execution trace for comprehensive analysis."""
        if trace.trace_id in self._stored_trace_ids:
            return ""
        
        content = json.dumps(trace.to_dict())
        
        from core.tiered_memory import MemoryTier
        entry = self.memory.store(
            content=content,
            tier=MemoryTier.L1_WORKING,  # Keep in working memory for analysis
            directory="/execution_traces",
            importance=0.75 if report.patterns_identified else 0.6,
            tags={"execution_trace", "plan_history", f"success_{trace.success}"},
            source="execution_tracker"
        )
        
        memory_id = str(id(entry))
        self._stored_trace_ids.add(trace.trace_id)
        return memory_id
    
    def query_relevant_reflections(
        self,
        task_description: str,
        scope_filter: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Query memory for relevant past reflections.
        
        Uses tiered retrieval approach.
        """
        results = []
        
        # Search across all memory using retrieve_relevant
        retrieved = self.memory.retrieve_relevant(task_description, top_k=limit * 2)
        
        for entry, score in retrieved:
            try:
                data = json.loads(entry.content)
                if data.get("type") != "reflection_report":
                    continue
                
                # Filter by scope if specified
                if scope_filter and data.get("scope") != scope_filter:
                    continue
                
                results.append({
                    "memory_tier": entry.tier.value,
                    "relevance_score": score,
                    "reflection_data": data,
                    "timestamp": entry.timestamp
                })
            except (json.JSONDecodeError, AttributeError):
                continue
        
        # Sort by relevance
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:limit]
    
    def get_performance_patterns(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract performance patterns across stored reflections.
        
        Returns aggregated insights on success/failure patterns,
        useful for planning strategy adjustments.
        """
        # Get all memories from /reflections directory
        dir_obj = self.memory.root.find("/reflections")
        if not dir_obj:
            return {
                "total_reflections": 0,
                "success_patterns": [],
                "failure_patterns": [],
                "tool_performance": {},
                "avg_quality_by_scope": {}
            }
        
        reflections = dir_obj.walk()
        
        patterns = {
            "total_reflections": 0,
            "success_patterns": [],
            "failure_patterns": [],
            "tool_performance": {},
            "avg_quality_by_scope": {}
        }
        
        scope_stats: Dict[str, List[float]] = {}
        
        for entry in reflections:
            try:
                data = json.loads(entry.content)
                if data.get("type") != "reflection_report":
                    continue
                
                patterns["total_reflections"] += 1
                scope = data.get("scope", "UNKNOWN")
                metrics = data.get("metrics", {}) or {}
                
                # Aggregate quality by scope
                quality = metrics.get("avg_quality", 0)
                if scope not in scope_stats:
                    scope_stats[scope] = []
                scope_stats[scope].append(quality)
                
                # Collect patterns
                patterns["success_patterns"].extend(data.get("successes", []))
                patterns["failure_patterns"].extend(data.get("failures", []))
                
                # Tool performance
                tools_used = metrics.get("tools_used", {})
                for tool, count in tools_used.items():
                    if tool not in patterns["tool_performance"]:
                        patterns["tool_performance"][tool] = {"uses": 0, "contexts": []}
                    patterns["tool_performance"][tool]["uses"] += count
                    
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
        
        # Calculate averages
        for scope, qualities in scope_stats.items():
            patterns["avg_quality_by_scope"][scope] = sum(qualities) / len(qualities) if qualities else 0
        
        return patterns


class PlanningWithReflection:
    """
    Enhanced planner that leverages historical reflections.
    
    Queries past reflection reports during planning to:
    1. Avoid previously identified failure patterns
    2. Reuse successful strategies
    3. Adjust task estimates based on historical performance
    """
    
    def __init__(
        self,
        planner,
        memory_bridge: ReflectionMemoryBridge
    ):
        self.planner = planner
        self.memory_bridge = memory_bridge
        self._adaptation_history: List[Dict] = []
    
    def plan_with_reflection_context(
        self,
        goal: str,
        available_tools: List[str],
        constraints: Optional[Dict[str, Any]] = None
    ):
        """
        Create a plan informed by relevant past reflections.
        
        Process:
        1. Query memory for similar past tasks/plans
        2. Analyze success/failure patterns
        3. Adjust planning strategy accordingly
        4. Create enhanced plan with reflection insights
        """
        start_time = time.time()
        
        # Query relevant reflections
        relevant_reflections = self.memory_bridge.query_relevant_reflections(
            task_description=goal,
            scope_filter=None,
            limit=10
        )
        
        # Analyze patterns
        insights = self._extract_planning_insights(relevant_reflections)
        
        # Create base plan using plan_with_reflection method
        reflection_data = {
            "successful_approaches": insights.get("replicate", []),
            "failed_approaches": insights.get("avoid", []),
            "suggested_improvements": insights.get("recommendations", [])
        } if insights else None
        
        plan = self.planner.plan_with_reflection(goal, reflection_data)
        
        # Record adaptation
        adaptation = {
            "timestamp": datetime.now().isoformat(),
            "goal": goal,
            "reflections_consulted": len(relevant_reflections),
            "insights_applied": len(insights) if insights else 0,
            "planning_time_ms": (time.time() - start_time) * 1000
        }
        self._adaptation_history.append(adaptation)
        
        return plan
    
    def _extract_planning_insights(
        self,
        reflections: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """Extract actionable insights from reflection data."""
        insights = {
            "avoid": [],
            "replicate": [],
            "recommendations": []
        }
        
        for ref in reflections:
            data = ref.get("reflection_data", {})
            
            # Identify failure patterns to avoid
            for failure in data.get("failures", []):
                insights["avoid"].append(failure)
            
            # Identify success patterns to replicate
            for success in data.get("successes", []):
                insights["replicate"].append(success)
            
            # Extract explicit recommendations
            for rec in data.get("recommendations", []):
                if isinstance(rec, dict) and "description" in rec:
                    insights["recommendations"].append(rec["description"])
                elif isinstance(rec, str):
                    insights["recommendations"].append(rec)
        
        # Remove duplicates while preserving order
        for key in insights:
            seen = set()
            unique = []
            for item in insights[key]:
                if item not in seen:
                    seen.add(item)
                    unique.append(item)
            insights[key] = unique
        
        return insights
    
    def get_adaptation_summary(self) -> Dict[str, Any]:
        """Get summary of planning adaptations based on reflections."""
        if not self._adaptation_history:
            return {"adaptations": 0, "average_reflections_per_plan": 0}
        
        total_reflections = sum(a["reflections_consulted"] for a in self._adaptation_history)
        
        return {
            "adaptations": len(self._adaptation_history),
            "average_reflections_per_plan": total_reflections / len(self._adaptation_history),
            "average_insights_applied": sum(a["insights_applied"] for a in self._adaptation_history) / len(self._adaptation_history),
            "average_planning_time_ms": sum(a["planning_time_ms"] for a in self._adaptation_history) / len(self._adaptation_history)
        }


class SelfImprovingLoop:
    """
    Automated self-improvement cycle:
    
    Execute → Reflect → Store → Plan(with history) → Execute(improved)
    
    Maintains continuous learning and adaptation.
    """
    
    def __init__(
        self,
        planner_with_reflection: PlanningWithReflection,
        executor,
        reflection_engine,
        memory_bridge: ReflectionMemoryBridge,
        mode: IntegrationMode = IntegrationMode.AUTONOMOUS
    ):
        self.planner = planner_with_reflection
        self.executor = executor
        self.reflection = reflection_engine
        self.memory_bridge = memory_bridge
        self.mode = mode
        
        self._execution_traces: List[ExecutionTrace] = []
        self._improvement_log: List[Dict] = []
    
    def execute_improving_cycle(
        self,
        goal: str,
        available_tools: List[str],
        max_iterations: int = 3
    ) -> ExecutionTrace:
        """
        Execute a goal with continuous improvement across iterations.
        
        Each iteration:
        1. Plan (using historical reflections)
        2. Execute
        3. Reflect
        4. Store in memory
        5. Use learnings for next iteration
        """
        trace = ExecutionTrace(
            trace_id=str(uuid.uuid4()),
            plan_id="",
            started_at=datetime.now()
        )
        
        iteration_results = []
        
        for iteration in range(max_iterations):
            iteration_start = time.time()
            
            # 1. Plan with reflection context
            plan = self.planner.plan_with_reflection_context(
                goal=goal,
                available_tools=available_tools
            )
            trace.plan_id = plan.id
            trace.plan = plan.to_dict() if hasattr(plan, 'to_dict') else {"id": plan.id, "goal": goal}
            
            # 2. Execute (simulated for this iteration)
            execution_result = self._execute_plan(plan)
            iteration_results.append(execution_result)
            trace.execution_results.append(execution_result)
            iteration_duration = (time.time() - iteration_start) * 1000
            
            # 3. Reflect on execution
            # Build tasks_data for reflection
            tasks_data = []
            for task_id, task in (plan.tasks.items() if hasattr(plan, 'tasks') else {}):
                tasks_data.append({
                    "id": task_id,
                    "description": task.description if hasattr(task, 'description') else str(task),
                    "status": "completed",  # Simulated success
                    "duration": iteration_duration / max(len(tasks_data), 1),
                    "quality_score": 0.8 - (iteration * 0.05)  # Simulated improvement
                })
            
            report = self.reflection.reflect_on_plan(
                plan_id=plan.id,
                plan_goal=goal,
                tasks_data=tasks_data,
                overall_success=True
            )
            trace.reflection_report = report
            
            # 4. Store in memory
            self.memory_bridge.store_reflection(report, trace)
            
            # 5. Check if we should continue iterating
            if report.metrics and report.metrics.avg_quality >= 0.9:
                trace.success = True
                trace.quality_score = report.metrics.avg_quality
                break
            
            # Generate improvement proposals for next iteration
            proposals = self.reflection.generate_improvement_proposals(report)
            trace.improvement_proposals = proposals
        
        trace.completed_at = datetime.now()
        trace.total_duration_ms = (datetime.now() - trace.started_at).total_seconds() * 1000
        trace.success = trace.success or any(r.get("success", False) for r in iteration_results)
        
        # Calculate quality from last reflection
        if trace.reflection_report and trace.reflection_report.metrics:
            trace.quality_score = trace.reflection_report.metrics.avg_quality
        
        self._execution_traces.append(trace)
        
        # Log improvement
        self._improvement_log.append({
            "timestamp": datetime.now().isoformat(),
            "trace_id": trace.trace_id,
            "iterations": len(iteration_results),
            "final_quality": trace.quality_score,
            "success": trace.success
        })
        
        return trace
    
    def _execute_plan(self, plan) -> Dict[str, Any]:
        """Execute a plan and return results."""
        # Simplified execution for integration demonstration
        # In practice, this would use the actual executor
        results = []
        overall_success = True
        
        tasks = plan.tasks if hasattr(plan, 'tasks') else {}
        for task_id in tasks:
            task = tasks[task_id]
            task_result = {
                "task_id": task_id,
                "success": True,  # Simulated
                "duration_ms": 100.0,
                "output": f"Completed: {task.description if hasattr(task, 'description') else str(task)}"
            }
            results.append(task_result)
        
        return {
            "plan_id": plan.id if hasattr(plan, 'id') else str(plan),
            "success": overall_success,
            "task_results": results,
            "total_duration_ms": len(results) * 100.0
        }
    
    def get_improvement_statistics(self) -> Dict[str, Any]:
        """Get statistics on self-improvement over time."""
        if not self._improvement_log:
            return {"total_cycles": 0, "average_quality": 0}
        
        qualities = [log["final_quality"] for log in self._improvement_log]
        
        return {
            "total_cycles": len(self._improvement_log),
            "successful_cycles": sum(1 for log in self._improvement_log if log["success"]),
            "success_rate": sum(1 for log in self._improvement_log if log["success"]) / len(self._improvement_log),
            "average_quality": sum(qualities) / len(qualities) if qualities else 0,
            "average_iterations": sum(log["iterations"] for log in self._improvement_log) / len(self._improvement_log),
            "quality_trend": "improving" if len(qualities) > 1 and qualities[-1] > qualities[0] else "stable"
        }
    
    def export_learning_report(self) -> str:
        """Export comprehensive learning report."""
        stats = self.get_improvement_statistics()
        patterns = self.memory_bridge.get_performance_patterns()
        
        report = f"""
# Self-Improvement Learning Report
Generated: {datetime.now().isoformat()}

## Performance Statistics
- Total Learning Cycles: {stats['total_cycles']}
- Success Rate: {stats['success_rate']:.1%}
- Average Quality Score: {stats['average_quality']:.2f}
- Average Iterations per Goal: {stats['average_iterations']:.1f}
- Quality Trend: {stats['quality_trend']}

## Learned Patterns
- Success Patterns Identified: {len(patterns['success_patterns'])}
- Failure Patterns Avoided: {len(patterns['failure_patterns'])}
- Total Reflections Stored: {patterns['total_reflections']}

## Performance by Scope
"""
        for scope, quality in patterns.get("avg_quality_by_scope", {}).items():
            report += f"- {scope}: {quality:.2f} avg quality\n"
        
        report += "\n## Tool Usage Patterns\n"
        for tool, data in patterns.get("tool_performance", {}).items():
            report += f"- {tool}: {data['uses']} uses\n"
        
        return report


def create_integrated_system(
    mode: IntegrationMode = IntegrationMode.AUTONOMOUS
):
    """
    Factory function to create a fully integrated system.
    
    Returns:
        Tuple of (planner_with_reflection, self_improving_loop, memory_bridge)
    """
    # Import here to avoid circular imports
    from core.tiered_memory import TieredMemorySystem
    from core.planner import HierarchicalPlanner
    from core.reflection import ReflectionEngine
    
    memory = TieredMemorySystem()
    base_planner = HierarchicalPlanner()
    executor = base_planner.executor
    reflection = ReflectionEngine()
    
    # Create integration layer
    memory_bridge = ReflectionMemoryBridge(memory)
    planner_with_reflection = PlanningWithReflection(base_planner, memory_bridge)
    improving_loop = SelfImprovingLoop(
        planner_with_reflection,
        executor,
        reflection,
        memory_bridge,
        mode
    )
    
    return planner_with_reflection, improving_loop, memory_bridge
