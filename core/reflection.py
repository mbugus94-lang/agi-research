"""
Reflection & Self-Improvement Module

Implements:
- Reactive self-correction (security focus)
- Performance analysis
- Learning from failures
- UCCT (Unified Contextual Control Theory) alignment
"""

import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ReflectionResult:
    """Result of reflection process."""
    complete: bool
    success: bool
    summary: str
    errors: List[str]
    improvements: List[str]
    lessons_learned: List[str]
    confidence: float


class ReflectionEngine:
    """
    Self-reflection and improvement engine.
    
    Key capabilities:
    1. Reactive self-correction (post-execution)
    2. RCA (Recursive Causal Audit) - trace verification
    3. Performance pattern recognition
    4. Learning consolidation
    """
    
    def __init__(self):
        self.failure_patterns: List[Dict] = []
        self.success_patterns: List[Dict] = []
    
    async def evaluate(
        self,
        execution_results: List[Any],
        original_task: str,
        thought_trace: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Main reflection entry point.
        Evaluates execution and determines next steps.
        """
        # Analyze results
        all_success = all(r.success for r in execution_results)
        any_errors = any(r.error for r in execution_results if hasattr(r, 'error'))
        
        # Calculate aggregate metrics
        total_time = sum(
            getattr(r, 'execution_time_ms', 0) for r in execution_results
        )
        avg_time = total_time / len(execution_results) if execution_results else 0
        
        # Determine completion status
        if all_success:
            complete = True
            confidence = 0.9
        elif any_errors:
            # Check if errors are recoverable
            recoverable = self._assess_recoverability(execution_results)
            complete = not recoverable
            confidence = 0.4 if recoverable else 0.2
        else:
            complete = False
            confidence = 0.5
        
        # Generate improvements
        improvements = self._suggest_improvements(execution_results)
        
        # Extract lessons
        lessons = self._extract_lessons(execution_results, original_task)
        
        result = ReflectionResult(
            complete=complete,
            success=all_success,
            summary=self._generate_summary(execution_results),
            errors=[r.error for r in execution_results if hasattr(r, 'error') and r.error],
            improvements=improvements,
            lessons_learned=lessons,
            confidence=confidence
        )
        
        # Store patterns for future learning
        self._store_pattern(result, execution_results)
        
        return {
            "complete": result.complete,
            "success": result.success,
            "summary": result.summary,
            "errors": result.errors,
            "improvements": result.improvements,
            "lessons_learned": result.lessons_learned,
            "confidence": result.confidence,
            "retry_suggested": not result.complete and not result.success,
            "avg_execution_time_ms": avg_time
        }
    
    def verify_trace(
        self,
        thought_trace: List[Dict],
        final_output: Any,
        ledger: Optional["EvidenceLedger"] = None,
    ) -> Dict:
        """
        RCA (Recursive Causal Audit): Verify that output follows from reasoning trace.
        Implements trace-answer verification under pressure.

        When `ledger` is provided, the verifier also asks the
        EvidenceLedger for the evidence coverage of each step. The
        returned dict gains `grounded`, `coverage_rate`, and
        `recommended_action` keys so the caller can branch on the
        evidence-grounded view of the trace.
        """
        if not thought_trace:
            return {
                "valid": False,
                "reason": "No thought trace provided",
                "grounded": False,
                "coverage_rate": 0.0,
                "recommended_action": "none",
            }

        # Check for gaps in reasoning
        steps_by_type = {}
        for thought in thought_trace:
            step_type = thought.get("type", "unknown")
            steps_by_type[step_type] = steps_by_type.get(step_type, 0) + 1

        # Verify required steps exist
        required_steps = ["explore", "verify", "plan", "reflect"]
        missing = [s for s in required_steps if s not in steps_by_type]

        # Check if final output aligns with last reasoning
        last_thought = thought_trace[-1] if thought_trace else None
        alignment = self._check_alignment(last_thought, final_output)

        result: Dict[str, Any] = {
            "valid": len(missing) == 0 and alignment > 0.5,
            "steps_present": steps_by_type,
            "missing_steps": missing,
            "alignment_score": alignment,
            "reason": "Trace complete and aligned" if not missing else f"Missing steps: {missing}",
            "grounded": False,
            "coverage_rate": 0.0,
            "recommended_action": "none",
        }

        # Optional: consult the evidence ledger for per-step grounding
        if ledger is not None:
            try:
                from .trace_grounding import TraceGrounder
                grounder = TraceGrounder(ledger)
                report = grounder.ground_trace(
                    thought_trace,
                    trace_id=str(thought_trace[0].get("session_id", "verify_trace"))
                    if thought_trace else "verify_trace",
                )
                result["grounded"] = report.coverage_rate >= 0.5
                result["coverage_rate"] = report.coverage_rate
                result["recommended_action"] = report.recommended_action
                result["contradicted_step_ids"] = list(report.contradicted_step_ids)
                result["weakest_step_ids"] = list(report.weakest_step_ids)
                # combine ledger-based recommendation with structural
                # completeness. If structurally complete but evidence-poor,
                # caller is advised to fetch more evidence.
                if missing and report.coverage_rate >= 0.5:
                    result["valid"] = False
                    result["reason"] = (
                        f"Missing steps: {missing} (structural); "
                        f"evidence coverage {report.coverage_rate:.2f}"
                    )
            except Exception:
                # ledger consultation is best-effort; never break verify_trace
                pass

        return result
    
    def reactive_self_correct(
        self,
        error: str,
        context: Dict
    ) -> Dict:
        """
        Reactive self-correction mechanism.
        For security: detect and revert malicious actions post-execution.
        """
        # Check for known error patterns
        correction_strategy = self._identify_correction_strategy(error)
        
        return {
            "error_detected": True,
            "error_type": self._classify_error(error),
            "strategy": correction_strategy,
            "can_recover": correction_strategy != "abort",
            "suggested_action": self._get_recovery_action(correction_strategy, context),
            "requires_review": "security" in error.lower() or "malicious" in error.lower()
        }
    
    def get_failure_analysis(self, n_recent: int = 10) -> Dict:
        """Analyze recent failure patterns for improvement."""
        recent_failures = self.failure_patterns[-n_recent:] if self.failure_patterns else []
        
        if not recent_failures:
            return {"patterns": [], "common_causes": []}
        
        # Group by error type
        error_types = {}
        for failure in recent_failures:
            error_type = failure.get("error_type", "unknown")
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        # Find most common
        common_causes = sorted(error_types.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "patterns": recent_failures,
            "common_causes": common_causes,
            "total_analyzed": len(recent_failures),
            "improvement_recommendations": self._generate_recommendations(common_causes)
        }
    
    def _assess_recoverability(self, results: List[Any]) -> bool:
        """Determine if errors are recoverable."""
        for result in results:
            if hasattr(result, 'error') and result.error:
                # Simple heuristics
                if "timeout" in result.error.lower():
                    return True  # Can retry
                if "rate limit" in result.error.lower():
                    return True  # Can wait and retry
                if "not found" in result.error.lower():
                    return False  # Likely permanent
        return True
    
    def _suggest_improvements(self, results: List[Any]) -> List[str]:
        """Suggest improvements based on execution results."""
        improvements = []
        
        # Check execution times
        slow_ops = [r for r in results if getattr(r, 'execution_time_ms', 0) > 5000]
        if slow_ops:
            improvements.append(f"Optimize {len(slow_ops)} slow operations")
        
        # Check failures
        failures = [r for r in results if hasattr(r, 'success') and not r.success]
        if failures:
            improvements.append(f"Add retry logic for {len(failures)} failed operations")
        
        return improvements
    
    def _extract_lessons(self, results: List[Any], task: str) -> List[str]:
        """Extract lessons learned from execution."""
        lessons = []
        
        for result in results:
            if hasattr(result, 'error') and result.error:
                lesson = f"Failed: {result.error[:50]}..."
                lessons.append(lesson)
            elif hasattr(result, 'success') and result.success:
                lessons.append(f"Success pattern: {type(result).__name__}")
        
        return lessons
    
    def _generate_summary(self, results: List[Any]) -> str:
        """Generate execution summary."""
        total = len(results)
        successful = sum(1 for r in results if getattr(r, 'success', False))
        
        if successful == total:
            return f"All {total} operations completed successfully"
        elif successful == 0:
            return f"All {total} operations failed"
        else:
            return f"{successful}/{total} operations successful"
    
    def _check_alignment(self, last_thought: Optional[Dict], output: Any) -> float:
        """Check if output aligns with last reasoning step."""
        if not last_thought:
            return 0.0
        
        # Simple heuristic: if reflect step exists, assume alignment
        if last_thought.get("type") == "reflect":
            return 0.8
        
        return 0.5
    
    def _classify_error(self, error: str) -> str:
        """Classify error type."""
        error_lower = error.lower()
        
        if "security" in error_lower or "malicious" in error_lower:
            return "security"
        elif "timeout" in error_lower:
            return "timeout"
        elif "rate" in error_lower:
            return "rate_limit"
        elif "not found" in error_lower:
            return "not_found"
        else:
            return "unknown"
    
    def _identify_correction_strategy(self, error: str) -> str:
        """Identify strategy for correcting error."""
        error_type = self._classify_error(error)
        
        strategies = {
            "security": "abort",  # Don't recover from security issues automatically
            "timeout": "retry",
            "rate_limit": "backoff",
            "not_found": "alternative",
            "unknown": "retry"
        }
        
        return strategies.get(error_type, "retry")
    
    def _get_recovery_action(self, strategy: str, context: Dict) -> str:
        """Get specific recovery action."""
        actions = {
            "retry": "Retry operation with same parameters",
            "backoff": "Wait and retry with exponential backoff",
            "alternative": "Try alternative approach or tool",
            "abort": "Stop execution and request human review"
        }
        
        return actions.get(strategy, "Unknown")
    
    def _store_pattern(self, result: ReflectionResult, execution_results: List[Any]):
        """Store success/failure pattern for learning."""
        pattern = {
            "timestamp": datetime.now().isoformat(),
            "success": result.success,
            "error_type": result.errors[0] if result.errors else None,
            "confidence": result.confidence,
            "lessons": result.lessons_learned
        }
        
        if result.success:
            self.success_patterns.append(pattern)
        else:
            self.failure_patterns.append(pattern)
    
    def _generate_recommendations(self, common_causes: List[tuple]) -> List[str]:
        """Generate improvement recommendations."""
        recommendations = []
        
        for cause, count in common_causes[:3]:
            if cause == "timeout":
                recommendations.append("Consider increasing timeouts or using async operations")
            elif cause == "rate_limit":
                recommendations.append("Implement better rate limiting and backoff strategies")
            elif cause == "not_found":
                recommendations.append("Add pre-validation for resources before operations")
        
        return recommendations
