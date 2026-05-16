"""
Reflection System Implementation

Self-evaluation and meta-cognitive improvement module.

Implements the reflection cycle:
1. Review execution trace
2. Identify failures/successes
3. Extract patterns
4. Generate insights
5. Update memory/strategies

References:
- ReAct: Synergizing Reasoning and Acting in Language Models (Yao et al.)
- Reflexion: Self-Reflective Agents (Shinn et al.)
- Agent-World: Self-evolving training arenas (arXiv:2604.18292)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Tuple
from enum import Enum
from datetime import datetime
import json
import hashlib


class InsightType(Enum):
    """Types of insights that can be generated from reflection"""
    STRATEGY_IMPROVEMENT = "strategy_improvement"
    ERROR_PATTERN = "error_pattern"
    SUCCESS_PATTERN = "success_pattern"
    KNOWLEDGE_GAP = "knowledge_gap"
    EFFICIENCY_GAIN = "efficiency_gain"
    TOOL_RECOMMENDATION = "tool_recommendation"


class ReflectionScope(Enum):
    """Scope of reflection analysis"""
    SINGLE_STEP = "single_step"      # Reflect on one action
    EPISODE = "episode"              # Reflect on full task execution
    SESSION = "session"              # Reflect on multi-task session
    LIFETIME = "lifetime"            # Reflect on accumulated experience


@dataclass
class ExecutionTrace:
    """Record of agent execution for reflection"""
    trace_id: str
    goal: str
    start_time: float
    end_time: Optional[float] = None
    steps: List[Dict[str, Any]] = field(default_factory=list)
    outcomes: List[bool] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate across steps"""
        if not self.outcomes:
            return 0.0
        return sum(self.outcomes) / len(self.outcomes)
    
    @property
    def duration(self) -> float:
        """Calculate execution duration"""
        if self.end_time is None:
            return 0.0
        return self.end_time - self.start_time
    
    def add_step(
        self,
        action: str,
        result: Any,
        success: bool,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add a step to the trace"""
        self.steps.append({
            "action": action,
            "result": result,
            "success": success,
            "context": context or {},
            "timestamp": datetime.now().timestamp()
        })
        self.outcomes.append(success)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "goal": self.goal,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "success_rate": self.success_rate,
            "step_count": len(self.steps),
            "success_count": sum(self.outcomes),
            "failure_count": len(self.outcomes) - sum(self.outcomes),
            "steps": self.steps
        }


@dataclass
class Pattern:
    """Extracted pattern from execution traces"""
    pattern_id: str
    pattern_type: str  # "success", "failure", "sequence", "alternative"
    description: str
    elements: List[str]  # Component actions/conditions
    frequency: int = 1
    confidence: float = 0.5
    source_traces: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "description": self.description,
            "elements": self.elements,
            "frequency": self.frequency,
            "confidence": self.confidence,
            "source_traces": self.source_traces
        }


@dataclass
class Insight:
    """Generated insight from reflection"""
    insight_id: str
    insight_type: InsightType
    description: str
    evidence: List[str]  # Supporting trace IDs or pattern IDs
    confidence: float
    actionable: bool = True
    suggested_action: Optional[str] = None
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    applied: bool = False
    application_result: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "insight_type": self.insight_type.value,
            "description": self.description,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "actionable": self.actionable,
            "suggested_action": self.suggested_action,
            "created_at": self.created_at,
            "applied": self.applied,
            "application_result": self.application_result
        }


class TraceAnalyzer:
    """Analyze execution traces to extract patterns"""
    
    def __init__(self):
        self.patterns: Dict[str, Pattern] = {}
        self.pattern_index: Dict[str, List[str]] = {}  # element -> pattern IDs
    
    def analyze_trace(self, trace: ExecutionTrace) -> List[Pattern]:
        """Analyze a single trace and extract patterns"""
        discovered = []
        
        # Success pattern analysis
        if trace.success_rate > 0.7:
            success_steps = [s["action"] for s in trace.steps if s["success"]]
            if len(success_steps) >= 2:
                pattern = self._extract_sequence_pattern(
                    trace.trace_id,
                    success_steps,
                    "success",
                    f"Successful sequence for: {trace.goal}"
                )
                discovered.append(pattern)
        
        # Failure pattern analysis
        if trace.success_rate < 0.5:
            failure_steps = []
            for i, step in enumerate(trace.steps):
                if not step["success"]:
                    # Include preceding context
                    context = trace.steps[max(0, i-1):i+1]
                    failure_steps.extend([s["action"] for s in context])
            
            if failure_steps:
                pattern = self._extract_sequence_pattern(
                    trace.trace_id,
                    failure_steps,
                    "failure",
                    f"Failure pattern in: {trace.goal}"
                )
                discovered.append(pattern)
        
        # Sequence pattern analysis (all traces)
        if len(trace.steps) >= 3:
            all_actions = [s["action"] for s in trace.steps]
            pattern = self._extract_sequence_pattern(
                trace.trace_id,
                all_actions,
                "sequence",
                f"Action sequence for: {trace.goal}"
            )
            discovered.append(pattern)
        
        return discovered
    
    def analyze_multiple_traces(
        self,
        traces: List[ExecutionTrace],
        min_frequency: int = 2
    ) -> List[Pattern]:
        """Analyze multiple traces to find recurring patterns"""
        all_patterns: Dict[str, List[str]] = {}  # pattern fingerprint -> trace IDs
        
        for trace in traces:
            patterns = self.analyze_trace(trace)
            for pattern in patterns:
                fingerprint = self._fingerprint_pattern(pattern)
                if fingerprint not in all_patterns:
                    all_patterns[fingerprint] = []
                all_patterns[fingerprint].append(trace.trace_id)
        
        # Consolidate frequent patterns
        consolidated = []
        for fingerprint, trace_ids in all_patterns.items():
            if len(trace_ids) >= min_frequency:
                # Find or create consolidated pattern
                pattern_id = hashlib.md5(fingerprint.encode()).hexdigest()[:12]
                if pattern_id not in self.patterns:
                    pattern = Pattern(
                        pattern_id=pattern_id,
                        pattern_type="recurring",
                        description=f"Recurring pattern across {len(trace_ids)} traces",
                        elements=fingerprint.split("::"),
                        frequency=len(trace_ids),
                        confidence=min(0.95, 0.5 + 0.1 * len(trace_ids)),
                        source_traces=trace_ids
                    )
                    self.patterns[pattern_id] = pattern
                    consolidated.append(pattern)
        
        return consolidated
    
    def _extract_sequence_pattern(
        self,
        trace_id: str,
        elements: List[str],
        pattern_type: str,
        description: str
    ) -> Pattern:
        """Extract a sequence pattern"""
        fingerprint = self._fingerprint_from_elements(elements)
        pattern_id = hashlib.md5(f"{trace_id}:{fingerprint}".encode()).hexdigest()[:12]
        
        pattern = Pattern(
            pattern_id=pattern_id,
            pattern_type=pattern_type,
            description=description,
            elements=elements[:10],  # Limit size
            frequency=1,
            confidence=0.6 if pattern_type == "sequence" else 0.8,
            source_traces=[trace_id]
        )
        
        # Index elements
        for elem in elements[:5]:  # Index first 5 elements
            if elem not in self.pattern_index:
                self.pattern_index[elem] = []
            self.pattern_index[elem].append(pattern_id)
        
        # Store pattern
        self.patterns[pattern_id] = pattern
        
        return pattern
    
    def _fingerprint_pattern(self, pattern: Pattern) -> str:
        """Create fingerprint for pattern deduplication"""
        return "::".join(pattern.elements[:5])
    
    def _fingerprint_from_elements(self, elements: List[str]) -> str:
        """Create fingerprint from element list"""
        return "::".join(elements[:5])
    
    def find_similar_patterns(self, query_elements: List[str], limit: int = 5) -> List[Pattern]:
        """Find patterns with similar elements"""
        matches: Dict[str, int] = {}
        for elem in query_elements:
            for pattern_id in self.pattern_index.get(elem, []):
                matches[pattern_id] = matches.get(pattern_id, 0) + 1
        
        # Sort by match count
        sorted_matches = sorted(matches.items(), key=lambda x: x[1], reverse=True)
        return [self.patterns[pid] for pid, _ in sorted_matches[:limit] if pid in self.patterns]
    
    def get_patterns_by_type(self, pattern_type: str) -> List[Pattern]:
        """Get all patterns of a specific type"""
        return [p for p in self.patterns.values() if p.pattern_type == pattern_type]


class InsightGenerator:
    """Generate actionable insights from patterns and traces"""
    
    def __init__(self):
        self.insights: Dict[str, Insight] = {}
        self.insight_history: List[str] = []  # Ordered insight IDs
    
    def generate_insights(
        self,
        trace: ExecutionTrace,
        patterns: List[Pattern],
        context: Optional[Dict[str, Any]] = None
    ) -> List[Insight]:
        """Generate insights from a trace and its patterns"""
        insights = []
        
        # Strategy improvement insights
        if trace.success_rate < 0.5:
            insight = self._create_strategy_insight(trace, patterns)
            if insight:
                insights.append(insight)
        
        # Error pattern insights
        failure_patterns = [p for p in patterns if p.pattern_type == "failure"]
        for pattern in failure_patterns:
            insight = self._create_error_insight(pattern)
            if insight:
                insights.append(insight)
        
        # Success pattern insights
        if trace.success_rate > 0.8:
            success_patterns = [p for p in patterns if p.pattern_type == "success"]
            for pattern in success_patterns:
                insight = self._create_success_insight(pattern, trace)
                if insight:
                    insights.append(insight)
        
        # Efficiency insights
        if trace.duration > 60 and trace.success_rate < 0.7:  # Slow and struggling
            insight = self._create_efficiency_insight(trace)
            if insight:
                insights.append(insight)
        
        # Knowledge gap insights
        knowledge_gaps = self._identify_knowledge_gaps(trace)
        for gap in knowledge_gaps:
            insight = Insight(
                insight_id=self._generate_insight_id(),
                insight_type=InsightType.KNOWLEDGE_GAP,
                description=f"Knowledge gap identified: {gap}",
                evidence=[trace.trace_id],
                confidence=0.6,
                suggested_action=f"Acquire knowledge about: {gap}"
            )
            insights.append(insight)
        
        # Store insights
        for insight in insights:
            self.insights[insight.insight_id] = insight
            self.insight_history.append(insight.insight_id)
        
        return insights
    
    def _create_strategy_insight(
        self,
        trace: ExecutionTrace,
        patterns: List[Pattern]
    ) -> Optional[Insight]:
        """Create insight for strategy improvement"""
        failure_steps = [i for i, s in enumerate(trace.steps) if not s["success"]]
        
        if failure_steps:
            first_failure = failure_steps[0]
            suggested_action = f"Consider alternative approach before step {first_failure}"
            
            return Insight(
                insight_id=self._generate_insight_id(),
                insight_type=InsightType.STRATEGY_IMPROVEMENT,
                description=f"Low success rate ({trace.success_rate:.1%}) suggests strategy needs adjustment",
                evidence=[trace.trace_id] + [p.pattern_id for p in patterns],
                confidence=0.7 + (1 - trace.success_rate) * 0.2,
                suggested_action=suggested_action
            )
        return None
    
    def _create_error_insight(self, pattern: Pattern) -> Optional[Insight]:
        """Create insight from error pattern"""
        return Insight(
            insight_id=self._generate_insight_id(),
            insight_type=InsightType.ERROR_PATTERN,
            description=f"Error pattern detected: {pattern.description}",
            evidence=[pattern.pattern_id],
            confidence=pattern.confidence,
            suggested_action=f"Add error handling for: {', '.join(pattern.elements[:2])}"
        )
    
    def _create_success_insight(
        self,
        pattern: Pattern,
        trace: ExecutionTrace
    ) -> Optional[Insight]:
        """Create insight from success pattern"""
        return Insight(
            insight_id=self._generate_insight_id(),
            insight_type=InsightType.SUCCESS_PATTERN,
            description=f"Success pattern confirmed: {pattern.description}",
            evidence=[pattern.pattern_id, trace.trace_id],
            confidence=min(0.95, pattern.confidence + 0.1),
            suggested_action=f"Apply this pattern to similar tasks: {trace.goal}"
        )
    
    def _create_efficiency_insight(self, trace: ExecutionTrace) -> Optional[Insight]:
        """Create insight for efficiency improvement"""
        return Insight(
            insight_id=self._generate_insight_id(),
            insight_type=InsightType.EFFICIENCY_GAIN,
            description=f"Task took {trace.duration:.1f}s with {trace.success_rate:.1%} success - efficiency opportunity",
            evidence=[trace.trace_id],
            confidence=0.65,
            suggested_action="Consider parallel execution or caching for repeated operations"
        )
    
    def _identify_knowledge_gaps(self, trace: ExecutionTrace) -> List[str]:
        """Identify potential knowledge gaps from execution trace"""
        gaps = []
        
        for step in trace.steps:
            if not step["success"]:
                action = step["action"]
                result = str(step.get("result", ""))
                
                # Common knowledge gap indicators
                if "not found" in result.lower() or "unknown" in result.lower():
                    gaps.append(f"Missing information about: {action}")
                elif "error" in result.lower() and "syntax" in result.lower():
                    gaps.append(f"Correct usage of: {action}")
                elif "timeout" in result.lower() or "slow" in result.lower():
                    gaps.append(f"Optimization techniques for: {action}")
        
        return gaps
    
    def _generate_insight_id(self) -> str:
        """Generate unique insight ID"""
        timestamp = datetime.now().timestamp()
        return hashlib.md5(f"insight:{timestamp}:{len(self.insights)}".encode()).hexdigest()[:12]
    
    def get_actionable_insights(self, min_confidence: float = 0.6) -> List[Insight]:
        """Get actionable insights above confidence threshold"""
        return [
            i for i in self.insights.values()
            if i.actionable and i.confidence >= min_confidence and not i.applied
        ]
    
    def get_insights_by_type(self, insight_type: InsightType) -> List[Insight]:
        """Get all insights of a specific type"""
        return [i for i in self.insights.values() if i.insight_type == insight_type]
    
    def mark_applied(
        self,
        insight_id: str,
        result: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Mark an insight as applied with optional result"""
        if insight_id in self.insights:
            self.insights[insight_id].applied = True
            self.insights[insight_id].application_result = result
            return True
        return False


class Reflector:
    """
    Main reflection component for agent self-evaluation.
    
    Implements the reflection cycle:
    1. Review execution trace
    2. Identify failures/successes
    3. Extract patterns
    4. Generate insights
    5. Update strategies/memory
    """
    
    def __init__(
        self,
        memory_system: Optional[Any] = None,
        scope: ReflectionScope = ReflectionScope.EPISODE
    ):
        self.memory = memory_system
        self.scope = scope
        self.analyzer = TraceAnalyzer()
        self.generator = InsightGenerator()
        self.traces: Dict[str, ExecutionTrace] = {}
        self.current_trace: Optional[ExecutionTrace] = None
    
    def start_trace(self, goal: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """Start recording a new execution trace"""
        trace_id = hashlib.md5(f"{goal}:{datetime.now().timestamp()}".encode()).hexdigest()[:12]
        trace = ExecutionTrace(
            trace_id=trace_id,
            goal=goal,
            start_time=datetime.now().timestamp(),
            metadata=metadata or {}
        )
        self.traces[trace_id] = trace
        self.current_trace = trace
        return trace_id
    
    def record_step(
        self,
        trace_id: str,
        action: str,
        result: Any,
        success: bool,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a step in an execution trace"""
        if trace_id in self.traces:
            self.traces[trace_id].add_step(action, result, success, context)
    
    def end_trace(self, trace_id: str) -> ExecutionTrace:
        """Complete and return an execution trace"""
        if trace_id in self.traces:
            trace = self.traces[trace_id]
            trace.end_time = datetime.now().timestamp()
            return trace
        raise ValueError(f"Trace {trace_id} not found")
    
    def reflect(
        self,
        trace: ExecutionTrace,
        scope: Optional[ReflectionScope] = None
    ) -> Dict[str, Any]:
        """
        Perform reflection on an execution trace.
        
        Returns reflection results with patterns and insights.
        """
        scope = scope or self.scope
        
        # Analyze the trace
        patterns = self.analyzer.analyze_trace(trace)
        
        # Generate insights
        insights = self.generator.generate_insights(trace, patterns)
        
        # Create reflection result
        reflection = {
            "trace_id": trace.trace_id,
            "goal": trace.goal,
            "scope": scope.value,
            "success_rate": trace.success_rate,
            "duration": trace.duration,
            "patterns_discovered": len(patterns),
            "insights_generated": len(insights),
            "patterns": [p.to_dict() for p in patterns],
            "insights": [i.to_dict() for i in insights],
            "actionable_insights": len([i for i in insights if i.actionable]),
            "recommendations": self._generate_recommendations(trace, insights)
        }
        
        # Store in memory if available
        if self.memory:
            self._store_reflection(trace, reflection)
        
        return reflection
    
    def evaluate(
        self,
        goal: str,
        thoughts: List[Any],
        observations: List[Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate progress and determine if task is complete.
        
        Called during agent execution to decide whether to continue.
        """
        # Calculate progress metrics
        total_steps = len(observations)
        successful_steps = sum(1 for o in observations if getattr(o, 'success', False))
        
        # Check completion indicators
        goal_achieved = self._check_goal_achievement(goal, observations)
        
        # Generate continuation insight
        if goal_achieved:
            return {
                "complete": True,
                "insight": "Goal appears to be achieved based on success indicators",
                "success_rate": successful_steps / max(total_steps, 1),
                "should_continue": False
            }
        
        # Check for stuck condition
        if self._is_stuck(thoughts, observations):
            return {
                "complete": False,
                "insight": "Execution appears stuck - consider alternative approach",
                "success_rate": successful_steps / max(total_steps, 1),
                "should_continue": True,
                "suggestion": "try_alternative"
            }
        
        return {
            "complete": False,
            "insight": "Continue current approach",
            "success_rate": successful_steps / max(total_steps, 1),
            "should_continue": True
        }
    
    def reflect_batch(
        self,
        traces: List[ExecutionTrace],
        min_frequency: int = 2
    ) -> Dict[str, Any]:
        """
        Perform reflection on multiple traces to find recurring patterns.
        """
        # Analyze all traces together
        patterns = self.analyzer.analyze_multiple_traces(traces, min_frequency)
        
        # Aggregate statistics
        total_success_rate = sum(t.success_rate for t in traces) / len(traces)
        total_duration = sum(t.duration for t in traces)
        
        # Cross-trace insights
        insights = []
        for trace in traces:
            trace_patterns = self.analyzer.analyze_trace(trace)
            trace_insights = self.generator.generate_insights(trace, trace_patterns)
            insights.extend(trace_insights)
        
        return {
            "trace_count": len(traces),
            "avg_success_rate": total_success_rate,
            "total_duration": total_duration,
            "recurring_patterns": len(patterns),
            "patterns": [p.to_dict() for p in patterns],
            "insights": [i.to_dict() for i in insights[:10]],  # Top 10
            "recommendations": self._generate_batch_recommendations(traces, patterns)
        }
    
    def _generate_recommendations(
        self,
        trace: ExecutionTrace,
        insights: List[Insight]
    ) -> List[str]:
        """Generate recommendations from reflection"""
        recommendations = []
        
        # Strategy recommendations
        if trace.success_rate < 0.5:
            recommendations.append("Consider decomposing task into smaller subtasks")
            recommendations.append("Review available tools and skills for better matches")
        
        # Error handling recommendations
        error_insights = [i for i in insights if i.insight_type == InsightType.ERROR_PATTERN]
        if error_insights:
            recommendations.append("Add explicit error handling for identified failure patterns")
        
        # Efficiency recommendations
        if trace.duration > 30 and trace.success_rate > 0.7:
            recommendations.append("Task succeeded but was slow - consider caching or optimization")
        
        return recommendations
    
    def _generate_batch_recommendations(
        self,
        traces: List[ExecutionTrace],
        patterns: List[Pattern]
    ) -> List[str]:
        """Generate recommendations from batch reflection"""
        recommendations = []
        
        avg_success = sum(t.success_rate for t in traces) / len(traces)
        
        if avg_success < 0.6:
            recommendations.append("Overall strategy needs revision - success rate below threshold")
        
        if patterns:
            recommendations.append(f"{len(patterns)} recurring patterns identified - consider formalizing as skills")
        
        return recommendations
    
    def _check_goal_achievement(self, goal: str, observations: List[Any]) -> bool:
        """Check if goal appears to be achieved"""
        if not observations:
            return False
        
        # Check last few observations for explicit completion indicators
        recent = observations[-3:]
        
        # Check for explicit completion indicators in results
        for obs in reversed(recent):
            result = str(getattr(obs, 'result', '')).lower()
            if any(ind in result for ind in ['complete', 'done', 'success', 'achieved', 'finished']):
                return True
        
        return False
    
    def _is_stuck(self, thoughts: List[Any], observations: List[Any]) -> bool:
        """Check if execution appears stuck in a loop"""
        if len(observations) < 4:
            return False
        
        # Check for repeated actions
        recent_actions = [getattr(o, 'action', '') for o in observations[-4:]]
        if len(set(recent_actions)) < 3:  # Lots of repetition
            return True
        
        # Check for no progress in thoughts
        if len(thoughts) >= 3:
            recent_thoughts = [str(t) for t in thoughts[-3:]]
            if len(set(recent_thoughts)) == 1:  # Same thought repeated
                return True
        
        return False
    
    def _store_reflection(self, trace: ExecutionTrace, reflection: Dict[str, Any]) -> None:
        """Store reflection results in memory"""
        if hasattr(self.memory, 'store_episode'):
            self.memory.store_episode(
                content={
                    "type": "reflection",
                    "trace_id": trace.trace_id,
                    "goal": trace.goal,
                    "success_rate": trace.success_rate,
                    "insights_count": reflection["insights_generated"]
                },
                tags=["reflection", f"success_rate_{int(trace.success_rate * 100)}"],
                importance=0.7 if trace.success_rate < 0.5 else 0.5
            )
    
    def get_insights(self) -> List[Insight]:
        """Get all generated insights"""
        return list(self.generator.insights.values())
    
    def get_patterns(self) -> List[Pattern]:
        """Get all discovered patterns"""
        return list(self.analyzer.patterns.values())
    
    def get_trace_stats(self) -> Dict[str, Any]:
        """Get statistics across all traces"""
        if not self.traces:
            return {"trace_count": 0}
        
        success_rates = [t.success_rate for t in self.traces.values()]
        durations = [t.duration for t in self.traces.values() if t.end_time]
        
        return {
            "trace_count": len(self.traces),
            "avg_success_rate": sum(success_rates) / len(success_rates),
            "total_duration": sum(durations) if durations else 0,
            "avg_duration": sum(durations) / len(durations) if durations else 0,
            "pattern_count": len(self.analyzer.patterns),
            "insight_count": len(self.generator.insights)
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "scope": self.scope.value,
            "trace_count": len(self.traces),
            "pattern_count": len(self.analyzer.patterns),
            "insight_count": len(self.generator.insights),
            "stats": self.get_trace_stats()
        }


def create_reflector(memory_system: Optional[Any] = None) -> Reflector:
    """Factory function to create a configured Reflector"""
    return Reflector(memory_system=memory_system)


def quick_reflect(
    goal: str,
    actions: List[Tuple[str, Any, bool]],  # (action, result, success)
    memory_system: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Quick reflection on a simple action sequence.
    
    Convenience function for rapid reflection without full setup.
    """
    reflector = create_reflector(memory_system)
    
    # Create trace
    trace_id = reflector.start_trace(goal)
    for action, result, success in actions:
        reflector.record_step(trace_id, action, result, success)
    
    trace = reflector.end_trace(trace_id)
    return reflector.reflect(trace)
