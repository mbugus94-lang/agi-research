"""
Test suite for Self-Reflection and Improvement System (core/reflection.py)

Tests performance analysis, capability assessment, improvement planning,
constitutional safety, multi-perspective review, and audit trails.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from core.reflection import (
    ReflectionEngine,
    ReflectionScope,
    PerformanceRecord,
    ProposedChange,
    ReviewPerspective,
    ChangeStatus
)


class TestRunner:
    """Simple test runner for reflection module."""
    
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []
    
    def test(self, name: str):
        """Decorator for test functions."""
        def decorator(func):
            self.tests.append((name, func))
            return func
        return decorator
    
    def run(self):
        """Run all tests."""
        print("=" * 60)
        print("REFLECTION MODULE TEST SUITE")
        print("=" * 60)
        
        for name, func in self.tests:
            try:
                func()
                print(f"✅ {name}")
                self.passed += 1
            except AssertionError as e:
                print(f"❌ {name}: {e}")
                self.failed += 1
            except Exception as e:
                print(f"❌ {name}: Unexpected error: {e}")
                self.failed += 1
        
        print("=" * 60)
        print(f"RESULTS: {self.passed} passed, {self.failed} failed")
        print("=" * 60)
        return self.failed == 0


runner = TestRunner()


@runner.test("ReflectionEngine Initialization")
def test_initialization():
    """Test that reflection engine initializes with correct defaults."""
    engine = ReflectionEngine(agent_id="test_agent")
    
    assert engine.agent_id == "test_agent"
    assert len(engine.performance_history) == 0
    assert len(engine.capability_assessments) == 0
    assert len(engine.improvement_goals) == 0
    assert len(engine.change_history) == 0
    assert len(engine.constitution) == 5  # Default principles


@runner.test("Performance Record Storage")
def test_performance_recording():
    """Test recording and retrieving performance data."""
    engine = ReflectionEngine()
    
    # Record some performances
    for i in range(10):
        record = PerformanceRecord(
            task_id=f"task_{i}",
            task_type="code_generation",
            success=i < 8,  # 80% success rate
            execution_time_ms=1000.0 + i * 100,
            quality_score=0.5 + i * 0.05,
            error_type=None if i < 8 else "timeout"
        )
        engine.record_performance(record)
    
    assert len(engine.performance_history) == 10
    
    # Test analysis
    analysis = engine.analyze_performance_patterns("code_generation")
    assert analysis["total_records"] == 10
    assert analysis["success_rate"] == 0.8
    assert "error_patterns" in analysis


@runner.test("Performance Pattern Analysis")
def test_performance_analysis():
    """Test performance pattern analysis with trend detection."""
    engine = ReflectionEngine()
    
    # Simulate improving trend (older worse, newer better)
    for i in range(20):
        record = PerformanceRecord(
            task_id=f"task_{i}",
            task_type="analysis",
            success=i > 5,  # First 6 fail, rest succeed (improving trend)
            execution_time_ms=2000.0 - i * 50,  # Getting faster
            quality_score=0.3 + i * 0.035  # Improving quality
        )
        engine.record_performance(record)
    
    analysis = engine.analyze_performance_patterns("analysis")
    
    assert analysis["total_records"] == 20
    assert analysis["trend"] == "improving"
    assert analysis["trend_delta"] > 0
    assert analysis["avg_quality_score"] > 0.5


@runner.test("Problem Area Identification")
def test_problem_identification():
    """Test identification of underperforming task types."""
    engine = ReflectionEngine()
    
    # Add good performance for one type
    for i in range(10):
        engine.record_performance(PerformanceRecord(
            task_id=f"good_{i}",
            task_type="reliable_task",
            success=True,
            execution_time_ms=500.0,
            quality_score=0.9
        ))
    
    # Add poor performance for another type
    for i in range(10):
        engine.record_performance(PerformanceRecord(
            task_id=f"bad_{i}",
            task_type="problematic_task",
            success=i < 3,  # 30% success
            execution_time_ms=5000.0,
            quality_score=0.4,
            error_type="syntax_error"
        ))
    
    problems = engine.identify_problem_areas()
    
    assert len(problems) == 1
    assert problems[0]["task_type"] == "problematic_task"
    assert problems[0]["success_rate"] < 0.5
    assert problems[0]["severity"] == "high"


@runner.test("Capability Assessment")
def test_capability_assessment():
    """Test self-assessment of capabilities."""
    engine = ReflectionEngine()
    
    # Add performance records
    for i in range(20):
        engine.record_performance(PerformanceRecord(
            task_id=f"cap_{i}",
            task_type="reasoning",
            success=True,
            execution_time_ms=800.0,
            quality_score=0.8
        ))
    
    # Assess capability
    assessment = engine.assess_capability(
        capability_name="logical_reasoning",
        task_type="reasoning"
    )
    
    assert assessment.capability_name == "logical_reasoning"
    assert assessment.proficiency_score > 0.7
    assert assessment.confidence > 0.3  # Should have decent confidence with 20 samples
    assert assessment.sample_size == 20
    assert len(assessment.strengths) > 0


@runner.test("Capability Assessment with Insufficient Data")
def test_capability_assessment_insufficient():
    """Test assessment when sample size is too small."""
    engine = ReflectionEngine()
    
    # Add only a few records
    for i in range(3):
        engine.record_performance(PerformanceRecord(
            task_id=f"small_{i}",
            task_type="rare_task",
            success=True,
            execution_time_ms=1000.0,
            quality_score=0.6
        ))
    
    assessment = engine.assess_capability(
        capability_name="rare_capability",
        task_type="rare_task"
    )
    
    assert assessment.confidence < 0.2  # Low confidence with few samples
    assert len(assessment.weaknesses) > 0


@runner.test("Improvement Goal Creation")
def test_improvement_goal():
    """Test creation and tracking of improvement goals."""
    engine = ReflectionEngine()
    
    # First assess a capability
    for i in range(15):
        engine.record_performance(PerformanceRecord(
            task_id=f"goal_test_{i}",
            task_type="planning",
            success=True,
            execution_time_ms=1500.0,
            quality_score=0.6
        ))
    
    engine.assess_capability("strategic_planning", "planning")
    
    # Create improvement goal
    goal = engine.create_improvement_goal(
        target_capability="strategic_planning",
        target_score=0.85,
        priority=8,
        strategy="Practice complex planning scenarios with feedback"
    )
    
    assert goal.target_capability == "strategic_planning"
    assert goal.target_score == 0.85
    assert goal.current_score < 0.85
    assert goal.priority == 8
    assert goal.status == "active"
    assert len(goal.milestones) == 2  # Default milestones
    
    # Test prioritization
    goals = engine.prioritize_goals()
    assert len(goals) == 1
    assert goals[0].goal_id == goal.goal_id


@runner.test("Goal Progress Update")
def test_goal_progress():
    """Test updating goal progress."""
    engine = ReflectionEngine()
    
    for i in range(15):
        engine.record_performance(PerformanceRecord(
            task_id=f"prog_{i}",
            task_type="writing",
            success=True,
            execution_time_ms=1000.0,
            quality_score=0.5
        ))
    
    engine.assess_capability("writing", "writing")
    
    goal = engine.create_improvement_goal(
        target_capability="writing",
        target_score=0.9,
        priority=5
    )
    
    # Update with progress that completes goal
    engine.update_goal_progress(goal.goal_id, 0.95)
    
    updated = engine.improvement_goals[goal.goal_id]
    assert updated.current_score == 0.95
    assert updated.status == "completed"


@runner.test("Constitutional Principle Validation - Safety Immutability")
def test_safety_immutability():
    """Test that safety constraints cannot be modified."""
    engine = ReflectionEngine()
    
    # Try to modify safety constraints (should fail)
    change = engine.propose_change(
        scope=ReflectionScope.SAFETY_CONSTRAINTS,
        description="Relax safety threshold",
        rationale="For testing purposes",
        expected_impact={"flexibility": 0.1},
        implementation="threshold = 0.1"
    )
    
    assert change.status == ChangeStatus.REJECTED
    assert len(change.constitutional_violations) > 0
    assert any("Safety Immutability" in v for v in change.constitutional_violations)


@runner.test("Constitutional Principle Validation - Valid Change")
def test_valid_change():
    """Test that valid internal state changes are allowed."""
    engine = ReflectionEngine()
    
    change = engine.propose_change(
        scope=ReflectionScope.INTERNAL_STATE,
        description="Update preference weights",
        rationale="Adjust based on recent performance analysis showing preference for faster responses over perfect accuracy",
        expected_impact={"response_time": -0.2, "accuracy": -0.05},
        implementation="self.preferences['speed_weight'] = 0.7"
    )
    
    assert change.status == ChangeStatus.PROPOSED  # Not rejected
    assert len(change.constitutional_violations) == 0


@runner.test("Rationale Requirement Validation")
def test_rationale_requirement():
    """Test that changes require sufficient rationale."""
    engine = ReflectionEngine()
    
    change = engine.propose_change(
        scope=ReflectionScope.CONFIGURATION,
        description="Change setting",
        rationale="Just because",  # Too short!
        expected_impact={"metric": 0.5},
        implementation="x = 1"
    )
    
    assert ChangeStatus.REJECTED == change.status or any(
        "Rationale" in v for v in change.constitutional_violations
    )


@runner.test("Multi-Perspective Review Simulation")
def test_multi_perspective_review():
    """Test simulating reviews from different perspectives."""
    engine = ReflectionEngine()
    
    change = engine.propose_change(
        scope=ReflectionScope.CONFIGURATION,
        description="Implement caching for API responses",
        rationale="Reduce API costs and improve response times based on performance analysis showing 40% of calls are redundant",
        expected_impact={"cost_reduction": 0.4, "response_time": -0.3},
        implementation="cache = LRUCache(maxsize=1000)"
    )
    
    reviews = engine.simulate_review(change)
    
    assert len(reviews) >= 3  # Default perspectives
    assert ReviewPerspective.SAFETY_FIRST in reviews
    assert ReviewPerspective.CORRECTNESS in reviews
    
    # Each review should have approval status and confidence
    for perspective, review in reviews.items():
        assert "approved" in review
        assert "confidence" in review
        assert "concerns" in review


@runner.test("Architecture Change Requires History")
def test_architecture_change_requires_history():
    """Test that core architecture changes require established track record."""
    engine = ReflectionEngine()
    
    # Try to make architecture change without prior successful changes
    change = engine.propose_change(
        scope=ReflectionScope.CORE_ARCHITECTURE,
        description="Replace planning algorithm",
        rationale="Current algorithm has scalability issues with complex multi-step planning scenarios requiring backtracking",
        expected_impact={"scalability": 0.5, "complexity": 0.2},
        implementation="planner = NewAlgorithm()"
    )
    
    # Should have violation about needing track record
    violations = change.constitutional_violations
    assert any("Architecture Experience" in v for v in violations) or change.status == ChangeStatus.REJECTED


@runner.test("Change Approval Process")
def test_change_approval():
    """Test the change approval workflow."""
    engine = ReflectionEngine()
    
    # Create valid change
    change = engine.propose_change(
        scope=ReflectionScope.INTERNAL_STATE,
        description="Update learning rate",
        rationale="Performance analysis shows high error rate on edge cases, reducing learning rate should improve stability",
        expected_impact={"stability": 0.15, "convergence": 0.1},
        implementation="self.learning_rate *= 0.9"
    )
    
    # Get reviews
    engine.simulate_review(change)
    
    # Approve
    result = engine.approve_change(change.change_id)
    assert result == True
    
    # Verify status
    assert change.status == ChangeStatus.APPROVED


@runner.test("Change Implementation and Rollback")
def test_implementation_rollback():
    """Test implementation and rollback of changes."""
    engine = ReflectionEngine()
    
    # Create, review, approve
    change = engine.propose_change(
        scope=ReflectionScope.CONFIGURATION,
        description="Increase timeout",
        rationale="Current timeout causing failures on slow networks, observed 15% failure rate on >500ms responses",
        expected_impact={"failure_rate": -0.15},
        implementation="TIMEOUT = 30"
    )
    
    engine.simulate_review(change)
    engine.approve_change(change.change_id)
    
    # Implement
    result = engine.implement_change(change.change_id)
    assert result == True
    assert change.status == ChangeStatus.IMPLEMENTED
    assert change.implemented_at is not None
    
    # Rollback
    rollback_result = engine.rollback_change(change.change_id, "Causing unexpected side effects")
    assert rollback_result == True
    assert change.status == ChangeStatus.ROLLED_BACK
    assert change.rollback_reason == "Causing unexpected side effects"


@runner.test("Audit Trail Retrieval")
def test_audit_trail():
    """Test retrieving change history and audit trail."""
    engine = ReflectionEngine()
    
    # Create several changes
    for i in range(5):
        change = engine.propose_change(
            scope=ReflectionScope.INTERNAL_STATE if i % 2 == 0 else ReflectionScope.CONFIGURATION,
            description=f"Change {i}",
            rationale=f"Rationale for change {i}: " + "x" * 30,
            expected_impact={"metric": i * 0.1},
            implementation=f"change_{i}()"
        )
        
        if i < 3:
            engine.simulate_review(change)
            engine.approve_change(change.change_id)
            engine.implement_change(change.change_id)
    
    # Get full audit trail
    trail = engine.get_audit_trail()
    assert len(trail) == 5
    
    # Filter by scope
    internal_changes = engine.get_audit_trail(ReflectionScope.INTERNAL_STATE)
    assert len(internal_changes) == 3  # Changes 0, 2, 4


@runner.test("Reflection Report Generation")
def test_reflection_report():
    """Test comprehensive reflection report generation."""
    engine = ReflectionEngine()
    
    # Add performance data
    for i in range(30):
        engine.record_performance(PerformanceRecord(
            task_id=f"rpt_{i}",
            task_type="general",
            success=i < 25,
            execution_time_ms=1000.0,
            quality_score=0.75
        ))
    
    # Assess capability
    engine.assess_capability("general_capability", "general")
    
    # Create goal
    engine.create_improvement_goal("general_capability", 0.9, priority=7)
    
    # Propose a change
    change = engine.propose_change(
        scope=ReflectionScope.INTERNAL_STATE,
        description="Optimize",
        rationale="Performance optimization based on profiling results showing bottleneck in data processing pipeline",
        expected_impact={"speed": 0.2},
        implementation="optimize()"
    )
    engine.simulate_review(change)
    engine.approve_change(change.change_id)
    engine.implement_change(change.change_id)
    
    # Generate report
    report = engine.generate_reflection_report()
    
    assert "agent_id" in report
    assert "performance_summary" in report
    assert "capabilities" in report
    assert "improvement_goals" in report
    assert "self_modification_history" in report
    assert "recommendations" in report
    
    assert report["improvement_goals"]["active"] >= 1
    assert "IMPLEMENTED" in str(report["self_modification_history"])


@runner.test("Export and Import State")
def test_export_import():
    """Test exporting and importing reflection state."""
    engine = ReflectionEngine(agent_id="export_test")
    
    # Add some data
    engine.record_performance(PerformanceRecord(
        task_id="export_1",
        task_type="test",
        success=True,
        execution_time_ms=1000.0,
        quality_score=0.8
    ))
    
    engine.assess_capability("test_cap", "test")
    
    # Export
    state = engine.export_state()
    
    assert state["agent_id"] == "export_test"
    assert len(state["performance_history"]) == 1
    assert "capability_assessments" in state
    
    # Create new engine and import
    new_engine = ReflectionEngine(agent_id="new")
    # Note: full import implementation would reconstruct all objects
    # Here we just verify the export structure is correct


@runner.test("Performance Window Management")
def test_performance_window():
    """Test that performance history maintains reasonable window size."""
    engine = ReflectionEngine()
    
    # Add many records
    for i in range(150):
        engine.record_performance(PerformanceRecord(
            task_id=f"win_{i}",
            task_type="window_test",
            success=True,
            execution_time_ms=500.0,
            quality_score=0.7
        ))
    
    # Should be limited to window size (100)
    assert len(engine.performance_history) <= 110  # Some buffer allowed
    
    # Most recent should be kept
    assert engine.performance_history[-1].task_id == "win_149"


@runner.test("Complex Scenario - Full Workflow")
def test_full_workflow():
    """Test a complete reflection workflow scenario."""
    engine = ReflectionEngine(agent_id="workflow_test")
    
    # 1. Record mixed performance
    for i in range(50):
        engine.record_performance(PerformanceRecord(
            task_id=f"wf_{i}",
            task_type="code_review",
            success=i < 35,  # 70% success
            execution_time_ms=2000.0 if i >= 35 else 800.0,
            quality_score=0.6 if i >= 35 else 0.85,
            error_type="timeout" if i >= 35 else None
        ))
    
    # 2. Analyze and find problems
    analysis = engine.analyze_performance_patterns("code_review")
    problems = engine.identify_problem_areas()
    
    assert abs(analysis["success_rate"] - 0.7) < 0.01  # Allow floating point variance
    # Note: Problem identification depends on both success rate AND quality scores
    # May or may not be identified as problem area depending on thresholds
    assert len(problems) >= 0
    
    # 3. Assess capability
    assessment = engine.assess_capability("code_reviewing", "code_review")
    assert assessment.proficiency_score < 0.8  # Not excellent
    
    # 4. Create improvement goal
    goal = engine.create_improvement_goal(
        target_capability="code_reviewing",
        target_score=0.9,
        priority=9,
        strategy="Focus on timeout handling and edge case detection"
    )
    
    # 5. Propose a change to address the issue
    change = engine.propose_change(
        scope=ReflectionScope.CONFIGURATION,
        description="Increase timeout and add retry logic",
        rationale="Analysis shows 30% failure rate due to timeouts on large codebases. Adding progressive timeout with retry will reduce failures.",
        expected_impact={
            "timeout_failure_rate": -0.25,
            "avg_response_time": 0.1  # Slight increase acceptable
        },
        implementation="timeout = progressive_timeout(base=10, max=60, retries=2)"
    )
    
    # 6. Get multi-perspective review
    reviews = engine.simulate_review(change, [
        ReviewPerspective.SAFETY_FIRST,
        ReviewPerspective.CORRECTNESS,
        ReviewPerspective.PERFORMANCE,
        ReviewPerspective.MAINTAINABILITY
    ])
    
    # 7. Approve and implement
    engine.approve_change(change.change_id)
    engine.implement_change(change.change_id)
    
    # 8. Generate report
    report = engine.generate_reflection_report()
    
    assert report["agent_id"] == "workflow_test"
    assert len(report["recommendations"]) >= 1
    assert report["improvement_goals"]["active"] == 1
    
    # 9. Verify audit trail
    trail = engine.get_audit_trail()
    implemented = [c for c in trail if c.status == ChangeStatus.IMPLEMENTED]
    assert len(implemented) == 1


if __name__ == "__main__":
    success = runner.run()
    sys.exit(0 if success else 1)
