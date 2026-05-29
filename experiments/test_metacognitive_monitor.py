"""
Tests for Metacognitive Monitor

Validates:
1. Session lifecycle management
2. Resource tracking accuracy
3. Progress monitoring
4. State assessment and control signals
5. Calibration tracking
6. Historical pattern analysis
"""

import sys
sys.path.insert(0, '/home/workspace/agi-research')

from core.metacognitive_monitor import (
    MetacognitiveMonitor,
    MonitoredSession,
    ResourceUsage,
    MonitoringLevel,
    StateAssessment,
    create_monitor,
    quick_session_summary
)


def test_session_lifecycle():
    """Test starting and ending sessions."""
    monitor = MetacognitiveMonitor(level=MonitoringLevel.STANDARD)
    
    # Start session
    session = monitor.start_session("test-001", "Test task for metacognitive monitoring")
    assert monitor.active_session is not None
    assert session.session_id == "test-001"
    assert session.task_description == "Test task for metacognitive monitoring"
    
    # End session
    ended = monitor.end_session(success=True, final_confidence=0.9, reason="test_complete")
    assert ended is not None
    assert ended.final_success is True
    assert ended.final_confidence == 0.9
    assert monitor.active_session is None
    assert len(monitor.session_history) == 1
    
    return True


def test_resource_tracking():
    """Test resource usage tracking."""
    monitor = MetacognitiveMonitor()
    monitor.start_session("test-002", "Resource tracking test")
    
    resources = ResourceUsage(
        tokens_used=1500,
        api_calls=3,
        tools_invoked=2,
        memory_operations=5,
        time_elapsed_ms=1200.0
    )
    
    monitor.record_step(
        step_description="Step 1",
        success=True,
        resources_used=resources,
        confidence=0.85
    )
    
    session = monitor.active_session
    assert session.resources.tokens_used == 1500
    assert session.resources.api_calls == 3
    assert session.resources.tools_invoked == 2
    assert session.resources.memory_operations == 5
    assert session.progress.steps_completed == 1
    
    # Test cost estimation
    cost = session.resources.total_cost_estimate()
    expected = 1500 * 0.0001 + 3 * 1.0 + 2 * 0.5 + 5 * 0.1
    assert abs(cost - expected) < 0.01
    
    monitor.end_session(success=True)
    return True


def test_progress_monitoring():
    """Test progress tracking and completion percentage."""
    monitor = MetacognitiveMonitor()
    session = monitor.start_session("test-003", "Progress test")
    
    # Simulate steps
    for i in range(5):
        resources = ResourceUsage(tokens_used=100, api_calls=1)
        success = i != 2  # One failure
        monitor.record_step(
            step_description=f"Step {i}",
            success=success,
            resources_used=resources,
            confidence=0.8
        )
    
    session.progress.steps_estimated_total = 10
    
    # Check progress metrics
    assert session.progress.steps_completed == 5
    assert session.progress.completion_percentage == 50.0
    assert session.progress.errors_encountered == 1
    assert session.progress.error_rate == 0.2
    
    monitor.end_session(success=True)
    return True


def test_state_assessment():
    """Test metacognitive state assessment and control signals."""
    monitor = MetacognitiveMonitor(level=MonitoringLevel.INTENSIVE)
    monitor.start_session("test-004", "Assessment test")
    
    # Test normal state
    assessment = monitor.assess_current_state(
        task_complexity=0.5,
        current_step_confidence=0.9,
        attention_focus=0.9,
        cognitive_load=0.2  # Low enough to trigger increase_aggression
    )
    
    assert isinstance(assessment, StateAssessment)
    assert assessment.predicted_success_probability > 0.7
    assert assessment.should_escalate is False
    assert assessment.should_pause_for_reflection is False
    assert assessment.recommended_action == "increase_aggression"
    
    # Test low confidence state (should trigger pause)
    assessment2 = monitor.assess_current_state(
        task_complexity=0.8,
        current_step_confidence=0.4,
        attention_focus=0.6,
        cognitive_load=0.7
    )
    
    assert assessment2.should_pause_for_reflection is True
    assert assessment2.recommended_action == "pause_and_reflect"
    
    # Test very low confidence (should trigger escalation)
    for _ in range(3):
        monitor.record_step(
            step_description="Error step",
            success=False,
            resources_used=ResourceUsage(),
            confidence=0.2
        )
    
    assessment3 = monitor.assess_current_state(
        task_complexity=0.9,
        current_step_confidence=0.2,
        attention_focus=0.4,
        cognitive_load=0.9
    )
    
    assert assessment3.should_escalate is True
    assert assessment3.recommended_action == "escalate_to_human_or_subagent"
    
    monitor.end_session(success=False)
    return True


def test_recovery_tracking():
    """Test error recovery monitoring."""
    monitor = MetacognitiveMonitor()
    monitor.start_session("test-005", "Recovery test")
    
    # Simulate error and recovery
    monitor.record_step(
        step_description="Step with error",
        success=False,
        resources_used=ResourceUsage(),
        confidence=0.6
    )
    
    monitor.record_recovery(success=True)
    
    session = monitor.active_session
    assert session.progress.errors_encountered == 1
    assert session.progress.recoveries_successful == 1
    assert session.progress.recovery_success_rate == 1.0
    
    # Test failed recovery
    monitor.record_step(
        step_description="Another error",
        success=False,
        resources_used=ResourceUsage(),
        confidence=0.5
    )
    monitor.record_recovery(success=False)
    
    assert session.progress.recoveries_successful == 1
    assert session.progress.errors_encountered == 2
    assert session.progress.recovery_success_rate == 0.5
    
    monitor.end_session(success=True)
    return True


def test_calibration_tracking():
    """Test confidence calibration tracking."""
    monitor = MetacognitiveMonitor()
    
    # Add multiple confidence-accuracy pairs
    for conf, success in [
        (0.9, True),   # Well calibrated
        (0.8, True),
        (0.7, False),  # Overconfident
        (0.9, False),  # Overconfident
        (0.3, False),  # Well calibrated (uncertain and failed)
        (0.4, False),
        (0.6, True),   # Underconfident
        (0.5, True),
    ]:
        monitor.confidence_accuracy_pairs.append((conf, success))
    
    stats = monitor.get_calibration_stats()
    
    assert "calibration_error_ece" in stats
    assert "average_confidence" in stats
    assert "average_accuracy" in stats
    assert stats["total_samples"] == 8
    assert "calibration_status" in stats
    assert "bin_details" in stats
    
    return True


def test_calibration_assessment():
    """Test calibration assessment for completed sessions."""
    monitor = MetacognitiveMonitor()
    
    # Well-calibrated session (confidence ~0.85, success=True)
    monitor.start_session("cal-001", "Calibrated task")
    monitor.confidence_accuracy_pairs.append((0.85, True))
    monitor.assess_current_state(current_step_confidence=0.85)
    monitor.end_session(success=True, final_confidence=0.85)
    
    # Overconfident session (confidence ~0.9, success=False)
    monitor.start_session("cal-002", "Overconfident task")
    monitor.confidence_accuracy_pairs.append((0.9, False))
    monitor.assess_current_state(current_step_confidence=0.9)
    monitor.end_session(success=False, final_confidence=0.9)
    
    # Underconfident session (confidence ~0.3, success=True)
    monitor.start_session("cal-003", "Underconfident task")
    monitor.confidence_accuracy_pairs.append((0.3, True))
    monitor.assess_current_state(current_step_confidence=0.3)
    monitor.end_session(success=True, final_confidence=0.3)
    
    sessions = monitor.session_history
    
    from core.metacognitive_monitor import ConfidenceCalibration
    
    # Check calibration - with single assessment matching final confidence
    cal1 = sessions[0].get_calibration_assessment()
    cal2 = sessions[1].get_calibration_assessment()
    cal3 = sessions[2].get_calibration_assessment()
    
    # Verify calibration states
    assert cal1 in [ConfidenceCalibration.WELL_CALIBRATED, ConfidenceCalibration.UNCERTAIN]
    assert cal2 == ConfidenceCalibration.OVERCONFIDENT
    assert cal3 in [ConfidenceCalibration.UNDERCONFIDENT, ConfidenceCalibration.UNCERTAIN]
    
    return True


def test_historical_patterns():
    """Test historical pattern analysis."""
    monitor = MetacognitiveMonitor()
    
    # Create several sessions with different outcomes
    for i in range(5):
        monitor.start_session(f"hist-{i}", f"Historical task {i}")
        for _ in range(3):
            resources = ResourceUsage(tokens_used=100)
            monitor.record_step(
                step_description="Step",
                success=True,
                resources_used=resources,
                confidence=0.85
            )
        monitor.end_session(success=True, final_confidence=0.9)
    
    patterns = monitor.get_historical_patterns()
    
    assert "success_rate_10_sessions" in patterns
    assert patterns["success_rate_10_sessions"] == 1.0
    assert patterns["trend"] == "improving"
    assert patterns["avg_error_rate"] == 0.0
    
    return True


def test_session_summary():
    """Test session summary generation."""
    monitor = MetacognitiveMonitor()
    monitor.start_session("summary-001", "Summary test session with longer description")
    
    for i in range(3):
        resources = ResourceUsage(tokens_used=200, api_calls=1)
        monitor.record_step(
            step_description=f"Action {i}",
            success=True,
            resources_used=resources,
            confidence=0.8
        )
    
    summary = monitor.get_session_summary()
    
    assert summary["session_id"] == "summary-001"
    assert "task_description" in summary
    assert "progress" in summary
    assert "resources" in summary
    assert summary["final_success"] is None  # Still active
    
    monitor.end_session(success=True)
    
    summary = monitor.get_session_summary()
    assert summary["final_success"] is True
    
    return True


def test_convenience_functions():
    """Test convenience functions."""
    # Test create_monitor
    monitor = create_monitor("intensive")
    assert monitor.level == MonitoringLevel.INTENSIVE
    
    monitor2 = create_monitor("minimal")
    assert monitor2.level == MonitoringLevel.MINIMAL
    
    # Test with standard level
    monitor3 = create_monitor("standard")
    assert monitor3.level == MonitoringLevel.STANDARD
    
    # Test quick_session_summary with active session
    monitor.start_session("conv-001", "Convenience test")
    summary = quick_session_summary(monitor)
    assert "conv-001" in summary
    assert "Duration:" in summary  # Shows duration field
    
    # Test with no session
    empty_summary = quick_session_summary(create_monitor())
    assert "No active" in empty_summary or "session" in empty_summary.lower()
    
    monitor.end_session(success=True)
    return True


def test_strategy_adjustment_handler():
    """Test strategy adjustment callbacks."""
    monitor = MetacognitiveMonitor()
    
    adjustments_triggered = []
    
    def mock_handler(assessment):
        adjustments_triggered.append(assessment)
    
    monitor.register_strategy_adjustment_handler(mock_handler)
    
    monitor.start_session("adj-001", "Adjustment test")
    
    # Trigger adjustment condition
    monitor.record_step(
        step_description="Problematic step",
        success=False,
        resources_used=ResourceUsage(),
        confidence=0.5
    )
    
    monitor.assess_current_state(
        task_complexity=0.8,
        current_step_confidence=0.4,
        cognitive_load=0.7
    )
    
    assert len(adjustments_triggered) > 0
    
    monitor.end_session(success=False)
    return True


def test_threshold_configuration():
    """Test threshold customization."""
    monitor = MetacognitiveMonitor()
    
    # Set custom threshold
    monitor.set_threshold("low_confidence", 0.7)
    assert monitor.thresholds["low_confidence"] == 0.7
    
    monitor.start_session("thresh-001", "Threshold test")
    
    # With higher threshold, 0.6 confidence should trigger pause
    assessment = monitor.assess_current_state(
        task_complexity=0.5,
        current_step_confidence=0.6,
        cognitive_load=0.5
    )
    
    assert assessment.should_pause_for_reflection is True  # 0.6 < 0.7
    
    monitor.end_session(success=True)
    return True


def test_event_tracking():
    """Test that events are properly tracked in session."""
    monitor = MetacognitiveMonitor()
    monitor.start_session("event-001", "Event tracking test")
    
    # Check initial events
    session = monitor.active_session
    assert len(session.events) == 1  # session_start event
    assert session.events[0]["type"] == "session_start"
    
    # Add custom event
    session.add_event("custom_event", {"detail": "test"})
    assert len(session.events) == 2
    
    # Record steps should add events
    resources = ResourceUsage()
    monitor.record_step("Step 1", True, resources, 0.8)
    assert len(session.events) == 3
    assert session.events[-1]["type"] == "step_complete"
    
    monitor.end_session(success=True, reason="test_end")
    assert len(session.events) == 4
    assert session.events[-1]["type"] == "session_end"
    
    return True


def test_intensive_vs_standard_monitoring():
    """Test different monitoring levels."""
    # Intensive should assess after each step
    intensive_monitor = MetacognitiveMonitor(level=MonitoringLevel.INTENSIVE)
    intensive_monitor.start_session("int-001", "Intensive monitoring")
    
    initial_count = len(intensive_monitor.active_session.assessments)
    
    intensive_monitor.record_step(
        step_description="Step",
        success=True,
        resources_used=ResourceUsage(),
        confidence=0.8
    )
    
    # Should have added assessment
    assert len(intensive_monitor.active_session.assessments) > initial_count
    
    intensive_monitor.end_session(success=True)
    
    # Standard should not assess after each step automatically
    standard_monitor = MetacognitiveMonitor(level=MonitoringLevel.STANDARD)
    standard_monitor.start_session("std-001", "Standard monitoring")
    
    standard_monitor.record_step(
        step_description="Step",
        success=True,
        resources_used=ResourceUsage(),
        confidence=0.8
    )
    
    # Should not have added assessment automatically
    assert len(standard_monitor.active_session.assessments) == 0
    
    standard_monitor.end_session(success=True)
    
    return True


# Run all tests
if __name__ == "__main__":
    tests = [
        test_session_lifecycle,
        test_resource_tracking,
        test_progress_monitoring,
        test_state_assessment,
        test_recovery_tracking,
        test_calibration_tracking,
        test_calibration_assessment,
        test_historical_patterns,
        test_session_summary,
        test_convenience_functions,
        test_strategy_adjustment_handler,
        test_threshold_configuration,
        test_event_tracking,
        test_intensive_vs_standard_monitoring,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            result = test()
            status = "✅ PASS" if result else "⚠️ SKIP"
            print(f"{status}: {test.__name__}")
            if result:
                passed += 1
        except Exception as e:
            print(f"❌ FAIL: {test.__name__} - {str(e)}")
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"Total: {len(tests)} | Passed: {passed} | Failed: {failed}")
    
    if failed == 0:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print(f"⚠️ {failed} test(s) failed")
        sys.exit(1)
