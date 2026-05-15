"""
Reflection & Self-Improvement System

Implements metacognitive capabilities:
- Execution review and evaluation
- Pattern extraction from experience
- Strategy improvement
- Self-correction

References:
- AI agent handbook: Reflection patterns
- ARC-AGI: Test-time training (TTT) for adaptation
- Conductor production: Reflection/evaluation loops
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json


@dataclass
class Reflection:
    """A reflection on execution experience"""
    timestamp: float
    focus: str  # What was reflected on
    observations: List[str]  # Key observations
    insights: List[str]  # Derived insights
    recommendations: List[str]  # Actionable recommendations
    confidence: float  # Confidence in reflection (0-1)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionTrace:
    """Complete record of execution for analysis"""
    goal: str
    steps: List[Dict[str, Any]]
    outcomes: List[Dict[str, Any]]
    success: bool
    execution_time: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Pattern:
    """Extracted pattern from experience"""
    id: str
    type: str  # "success", "failure", "strategy", "tool"
    description: str
    conditions: List[str]  # When pattern applies
    consequences: List[str]  # What happens
    frequency: int = 1
    confidence: float = 0.5
    examples: List[str] = field(default_factory=list)


class Reflector:
    """
    Self-reflection system for agents.
    
    Implements metacognitive capabilities:
    - Review execution and identify issues
    - Extract patterns from success/failure
    - Generate insights for improvement
    - Recommend strategy adjustments
    
    Based on:
    - ReAct: Observation and reflection as part of loop
    - Test-Time Training (TTT): Adaptation during execution
    - ARC-AGI: Reflection for better generalization
    """
    
    def __init__(self):
        self.reflections: List[Reflection] = []
        self.patterns: List[Pattern] = []
        self.performance_history: List[Dict[str, Any]] = []
    
    def evaluate(
        self,
        goal: str,
        thoughts: List[Any],
        observations: List[Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evaluate execution and generate reflection.
        
        Returns assessment with recommendations.
        """
        # Build execution trace
        trace = self._build_trace(goal, thoughts, observations, context)
        
        # Analyze execution
        analysis = self._analyze_execution(trace)
        
        # Determine if complete
        complete = self._is_complete(trace, analysis)
        
        # Generate insights
        insights = self._generate_insights(trace, analysis)
        
        # Extract patterns
        new_patterns = self._extract_patterns(trace, analysis)
        for p in new_patterns:
            self._add_or_update_pattern(p)
        
        # Create reflection record
        reflection = Reflection(
            timestamp=datetime.now().timestamp(),
            focus=goal,
            observations=analysis.get("observations", []),
            insights=insights,
            recommendations=analysis.get("recommendations", []),
            confidence=analysis.get("confidence", 0.5)
        )
        self.reflections.append(reflection)
        
        # Store performance data
        self.performance_history.append({
            "goal": goal,
            "success": trace.success,
            "execution_time": trace.execution_time,
            "step_count": len(trace.steps),
            "timestamp": datetime.now().timestamp()
        })
        
        return {
            "complete": complete,
            "success": trace.success,
            "insights": insights,
            "recommendations": reflection.recommendations,
            "patterns_found": len(new_patterns),
            "improvement_needed": not complete or not trace.success
        }
    
    def reflect_on_strategy(
        self,
        strategy_name: str,
        usage_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Reflect on effectiveness of a planning strategy.
        
        Returns improvement recommendations.
        """
        if not usage_history:
            return {"improvements": [], "assessment": "insufficient_data"}
        
        # Calculate metrics
        total = len(usage_history)
        successes = sum(1 for h in usage_history if h.get("success", False))
        avg_time = sum(h.get("execution_time", 0) for h in usage_history) / total
        
        success_rate = successes / total if total > 0 else 0
        
        # Identify issues
        issues = []
        if success_rate < 0.7:
            issues.append("low_success_rate")
        if avg_time > 60:  # 60 seconds threshold
            issues.append("slow_execution")
        
        # Generate recommendations
        recommendations = []
        if "low_success_rate" in issues:
            recommendations.append("Consider decomposing tasks further")
            recommendations.append("Review failure patterns for common causes")
        if "slow_execution" in issues:
            recommendations.append("Look for parallelization opportunities")
            recommendations.append("Simplify task decomposition")
        
        return {
            "strategy": strategy_name,
            "success_rate": success_rate,
            "avg_execution_time": avg_time,
            "total_uses": total,
            "issues": issues,
            "recommendations": recommendations,
            "assessment": "needs_improvement" if issues else "effective"
        }
    
    def extract_learning(
        self,
        experiences: List[ExecutionTrace],
        min_confidence: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Extract learnings from multiple experiences.
        
        Finds patterns that hold across executions.
        """
        learnings = []
        
        # Analyze common success factors
        successes = [e for e in experiences if e.success]
        failures = [e for e in experiences if not e.success]
        
        if len(successes) >= 3:
            common_success_patterns = self._find_commonalities(successes)
            if common_success_patterns:
                learnings.append({
                    "type": "success_factor",
                    "patterns": common_success_patterns,
                    "confidence": len(successes) / len(experiences)
                })
        
        if len(failures) >= 3:
            common_failure_patterns = self._find_commonalities(failures)
            if common_failure_patterns:
                learnings.append({
                    "type": "failure_factor",
                    "patterns": common_failure_patterns,
                    "confidence": len(failures) / len(experiences),
                    "avoid": True
                })
        
        return learnings
    
    def _build_trace(
        self,
        goal: str,
        thoughts: List[Any],
        observations: List[Any],
        context: Dict[str, Any]
    ) -> ExecutionTrace:
        """Build execution trace from execution data."""
        steps = []
        for i, (thought, obs) in enumerate(zip(thoughts, observations)):
            step = {
                "step": i,
                "thought": str(thought.content) if hasattr(thought, 'content') else str(thought),
                "thought_type": thought.type if hasattr(thought, 'type') else "unknown",
                "action": obs.action if hasattr(obs, 'action') else str(obs),
                "result": obs.result if hasattr(obs, 'result') else None,
                "success": obs.success if hasattr(obs, 'success') else False
            }
            steps.append(step)
        
        # Determine overall success
        success = any(
            obs.success if hasattr(obs, 'success') else False
            for obs in observations
        ) if observations else False
        
        # Estimate execution time from timestamps if available
        execution_time = 0.0
        if observations and hasattr(observations[0], 'timestamp'):
            start = observations[0].timestamp
            end = observations[-1].timestamp
            execution_time = end - start
        
        return ExecutionTrace(
            goal=goal,
            steps=steps,
            outcomes=[{"success": obs.success, "result": obs.result} for obs in observations],
            success=success,
            execution_time=execution_time,
            metadata={"context_keys": list(context.keys())}
        )
    
    def _analyze_execution(self, trace: ExecutionTrace) -> Dict[str, Any]:
        """Analyze execution trace for issues and patterns."""
        observations = []
        recommendations = []
        
        # Check for failures
        failures = [s for s in trace.steps if not s.get("success", False)]
        if failures:
            observations.append(f"{len(failures)} steps failed")
            
            # Categorize failures
            error_types = set()
            for f in failures:
                result = str(f.get("result", ""))
                if "error" in result.lower():
                    error_types.add("execution_error")
                elif "not found" in result.lower():
                    error_types.add("resource_not_found")
                else:
                    error_types.add("unknown")
            
            if "execution_error" in error_types:
                recommendations.append("Review tool/skill error handling")
            if "resource_not_found" in error_types:
                recommendations.append("Verify resource availability before execution")
        
        # Check for repetition (stuck in loop)
        thought_contents = [s.get("thought", "") for s in trace.steps]
        if len(thought_contents) > 5:
            unique_thoughts = len(set(thought_contents))
            if unique_thoughts / len(thought_contents) < 0.5:
                observations.append("Possible repetition or stuck loop detected")
                recommendations.append("Add progress tracking to avoid loops")
        
        # Check completion indicators
        if trace.success:
            observations.append("Goal achieved successfully")
            recommendations.append("Consider recording successful approach as pattern")
        else:
            observations.append("Goal not fully achieved")
            recommendations.append("Analyze partial progress for next attempt")
        
        # Calculate confidence based on data quality
        confidence = min(1.0, len(trace.steps) / 10)  # More steps = more confidence
        
        return {
            "observations": observations,
            "recommendations": recommendations,
            "confidence": confidence,
            "failure_count": len(failures),
            "total_steps": len(trace.steps)
        }
    
    def _is_complete(self, trace: ExecutionTrace, analysis: Dict[str, Any]) -> bool:
        """Determine if task is complete based on trace and analysis."""
        # Success = complete
        if trace.success:
            return True
        
        # Too many failures = likely stuck
        if analysis.get("failure_count", 0) > 3:
            return True
        
        # Check for completion indicators in results
        for step in trace.steps:
            result = str(step.get("result", "")).lower()
            if "complete" in result or "done" in result or "finished" in result:
                return True
        
        return False
    
    def _generate_insights(
        self,
        trace: ExecutionTrace,
        analysis: Dict[str, Any]
    ) -> List[str]:
        """Generate insights from analysis."""
        insights = []
        
        # Success insights
        if trace.success:
            insights.append("Approach was effective for this goal")
            if trace.execution_time < 10:
                insights.append("Execution was efficient (under 10s)")
        
        # Failure insights
        failures = analysis.get("failure_count", 0)
        if failures > 0:
            insights.append(f"Encountered {failures} execution issues")
            if failures / max(len(trace.steps), 1) > 0.5:
                insights.append("High failure rate suggests approach needs revision")
        
        # Step-based insights
        if len(trace.steps) > 8:
            insights.append("Complex task with many steps - consider better decomposition")
        
        return insights
    
    def _extract_patterns(
        self,
        trace: ExecutionTrace,
        analysis: Dict[str, Any]
    ) -> List[Pattern]:
        """Extract patterns from execution."""
        patterns = []
        
        # Success pattern
        if trace.success:
            pattern = Pattern(
                id=f"success_{datetime.now().timestamp()}",
                type="success",
                description=f"Successful approach for: {trace.goal[:50]}",
                conditions=[f"goal contains: {trace.goal[:30]}"],
                consequences=["successful_completion"],
                confidence=0.7
            )
            patterns.append(pattern)
        
        # Failure pattern
        failures = analysis.get("failure_count", 0)
        if failures > 0:
            pattern = Pattern(
                id=f"failure_{datetime.now().timestamp()}",
                type="failure",
                description=f"Encountered {failures} failures",
                conditions=["multiple_step_failures"],
                consequences=["incomplete_execution"],
                confidence=0.6
            )
            patterns.append(pattern)
        
        return patterns
    
    def _add_or_update_pattern(self, new_pattern: Pattern) -> None:
        """Add new pattern or update existing similar one."""
        # Check for similar existing pattern
        for existing in self.patterns:
            if existing.type == new_pattern.type:
                if existing.description == new_pattern.description:
                    # Update existing
                    existing.frequency += 1
                    existing.confidence = min(1.0, existing.confidence + 0.1)
                    existing.examples.append(new_pattern.id)
                    return
        
        # Add new
        self.patterns.append(new_pattern)
    
    def _find_commonalities(self, traces: List[ExecutionTrace]) -> List[str]:
        """Find common elements across traces."""
        if not traces:
            return []
        
        # Simple implementation: find common step patterns
        common = []
        
        # Check for common first steps
        first_steps = [t.steps[0].get("thought", "") if t.steps else "" for t in traces]
        if len(set(first_steps)) == 1:
            common.append(f"always_starts_with: {first_steps[0][:50]}")
        
        # Check for common success indicators
        success_indicators = set()
        for trace in traces:
            for step in trace.steps:
                if step.get("success", False):
                    result = str(step.get("result", ""))
                    success_indicators.add(result[:50])
        
        if success_indicators:
            common.append(f"success_looks_like: {list(success_indicators)[0]}")
        
        return common
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get summary of performance over time."""
        if not self.performance_history:
            return {"status": "no_data"}
        
        total = len(self.performance_history)
        successes = sum(1 for p in self.performance_history if p.get("success", False))
        avg_time = sum(p.get("execution_time", 0) for p in self.performance_history) / total
        
        return {
            "total_executions": total,
            "success_rate": successes / total,
            "avg_execution_time": avg_time,
            "pattern_count": len(self.patterns),
            "reflection_count": len(self.reflections)
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "reflection_count": len(self.reflections),
            "pattern_count": len(self.patterns),
            "performance_entries": len(self.performance_history),
            "summary": self.get_performance_summary()
        }
