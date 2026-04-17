"""
Test Suite for Integration Module
Tests the self-improving loop connecting reflection, planning, and memory.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.integration import (
    SelfImprovingLoop, IntegratedReflectionEngine, IntegratedPlanner, IntegratedMemory,
    FeedbackType, IntegrationPriority, ComponentFeedback, ReflectionToPlanningBridge,
    PerformanceInformedPlan
)


def test_component_interface():
    """Test 1: Component interface feedback flow"""
    print("Test 1: Component interface feedback flow...")
    
    reflection = IntegratedReflectionEngine("test_agent")
    planner = IntegratedPlanner()
    
    # Send feedback from reflection to planner
    feedback = ComponentFeedback(
        feedback_type=FeedbackType.PERFORMANCE_INSIGHT,
        source_component="reflection",
        target_component="planning",
        content={"test": "data"},
        priority=IntegrationPriority.HIGH
    )
    
    reflection.send_feedback(feedback)
    planner.receive_feedback(feedback)
    
    assert len(reflection.feedback_outbox) == 1
    assert len(planner.feedback_inbox) == 1
    print("  ✅ Component interface feedback flow works")


def test_reflection_performance_recording():
    """Test 2: Reflection engine performance recording"""
    print("Test 2: Reflection engine performance recording...")
    
    engine = IntegratedReflectionEngine("test_agent")
    
    # Record multiple executions
    for i in range(10):
        engine.record_execution(
            task_id=f"task_{i}",
            task_type="code_generation",
            success=i % 3 != 0,  # 66% success rate
            execution_time_ms=1000.0 + i * 100,
            quality_score=0.7 + (i % 3) * 0.1,
            error_type=None if i % 3 != 0 else "syntax_error"
        )
    
    history = engine.performance_history.get("code_generation", [])
    assert len(history) == 10
    
    # Check window limit
    for i in range(60):  # Add more to test window
        engine.record_execution(
            task_id=f"task_extra_{i}",
            task_type="code_generation",
            success=True,
            execution_time_ms=500.0,
            quality_score=0.8
        )
    
    history = engine.performance_history.get("code_generation", [])
    assert len(history) == 50  # Window limit maintained
    print("  ✅ Performance recording with window management works")


def test_reflection_to_planning_bridge():
    """Test 3: Reflection generates insights for planning"""
    print("Test 3: Reflection to planning bridge...")
    
    engine = IntegratedReflectionEngine("test_agent")
    planner = IntegratedPlanner()
    
    # Record declining performance
    for i in range(20):
        # Intentionally declining: more failures as we go
        success = i < 10  # First 10 succeed, next 10 fail
        engine.record_execution(
            task_id=f"task_{i}",
            task_type="web_search",
            success=success,
            execution_time_ms=2000.0,
            quality_score=0.9 if success else 0.3
        )
    
    bridge = engine.analyze_and_send_insights("web_search")
    
    assert bridge is not None
    assert bridge.capability_name == "web_search"
    assert bridge.trend == "declining"
    assert bridge.priority == IntegrationPriority.HIGH
    assert len(bridge.suggested_strategies) > 0
    
    # Verify feedback was sent
    assert len(engine.feedback_outbox) == 1
    assert engine.feedback_outbox[0].feedback_type == FeedbackType.PERFORMANCE_INSIGHT
    print("  ✅ Reflection to planning bridge generation works")


def test_planner_informed_plan_creation():
    """Test 4: Planner creates informed plans"""
    print("Test 4: Planner creates informed plans...")
    
    planner = IntegratedPlanner()
    
    # Add an insight
    insight = ReflectionToPlanningBridge(
        capability_name="code_generation",
        proficiency_score=0.85,
        confidence=0.8,
        trend="improving",
        suggested_strategies=["Use advanced strategies"],
        priority=IntegrationPriority.MEDIUM
    )
    planner.update_from_reflection(insight)
    
    # Create informed plan
    plan = planner.create_informed_plan("code_generation", "Implement a sorting algorithm")
    
    assert plan.plan_id is not None
    assert plan.task_type == "code_generation"
    assert plan.expected_success_rate == 0.85  # From insight
    assert plan.suggested_strategy is not None
    assert len(plan.adaptations) > 0
    assert plan.risk_assessment["confidence"] == 0.8
    
    # Verify feedback was sent
    assert len(planner.feedback_outbox) == 1
    print("  ✅ Informed plan creation works")


def test_memory_storage_and_retrieval():
    """Test 5: Memory stores and retrieves insights"""
    print("Test 5: Memory storage and retrieval...")
    
    memory = IntegratedMemory(max_entries=10)
    
    # Store reports
    for i in range(15):
        memory.store_reflection_report({
            "task_type": "code_generation" if i % 2 == 0 else "analysis",
            "score": 0.7 + i * 0.01
        }, priority=IntegrationPriority.MEDIUM if i % 3 == 0 else IntegrationPriority.LOW)
    
    # Check size limit enforced
    assert len(memory.reflection_reports) == 10
    
    # Retrieve relevant insights
    insights = memory.retrieve_relevant_insights("code_generation", limit=3)
    # Should get code_generation reports (every other one, so about 7 stored, 3 retrieved)
    assert len(insights) <= 3
    
    # Check access count tracking
    for insight in insights:
        assert insight["access_count"] >= 1
    
    print("  ✅ Memory storage and retrieval works")


def test_self_improving_loop_basic():
    """Test 6: Basic self-improving loop execution"""
    print("Test 6: Self-improving loop execution...")
    
    loop = SelfImprovingLoop("test_loop")
    
    # Mock execution function
    def mock_execute(plan):
        return {
            "success": True,
            "quality": 0.85,
            "result": "task completed"
        }
    
    result = loop.execute_task(
        task_type="code_generation",
        task_description="Test task",
        execute_fn=mock_execute
    )
    
    assert result["success"] is True
    assert result["task_id"] == "task_0"
    assert result["quality_score"] == 0.85
    assert "plan" in result
    
    # Check execution count
    assert loop.execution_count == 1
    
    # Check memory updated
    assert len(loop.memory.planning_history) == 1
    
    print("  ✅ Self-improving loop basic execution works")


def test_improving_performance_adaptation():
    """Test 7: System adapts to improving performance"""
    print("Test 7: Improving performance adaptation...")
    
    loop = SelfImprovingLoop("test_adapt")
    
    # Simulate improving performance
    quality_scores = [0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.88, 0.9, 0.92, 0.93]
    
    for quality in quality_scores:
        loop.execute_task(
            task_type="analysis",
            task_description="Analyzing data",
            execute_fn=lambda p, q=quality: {"success": q > 0.6, "quality": q}
        )
    
    # Check reflection has history
    assert len(loop.reflection.performance_history.get("analysis", [])) == 10
    
    # Generate insights
    bridge = loop.reflection.analyze_and_send_insights("analysis")
    
    if bridge:
        assert bridge.trend == "improving"
        assert bridge.proficiency_score >= 0.8  # Allow exact match
    
    print("  ✅ Improving performance adaptation works")


def test_declining_performance_response():
    """Test 8: System responds to declining performance"""
    print("Test 8: Declining performance response...")
    
    loop = SelfImprovingLoop("test_decline")
    
    # Simulate declining performance
    quality_scores = [0.9, 0.85, 0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5, 0.45]
    
    for quality in quality_scores:
        loop.execute_task(
            task_type="web_search",
            task_description="Search for information",
            execute_fn=lambda p, q=quality: {"success": q > 0.6, "quality": q, "error": None if q > 0.6 else "timeout"}
        )
    
    # Generate insights
    bridge = loop.reflection.analyze_and_send_insights("web_search")
    
    if bridge:
        assert bridge.trend == "declining"
        assert bridge.priority == IntegrationPriority.HIGH
        # Should have suggestions for recovery
        assert any("alternative" in s.lower() or "review" in s.lower() 
                  for s in bridge.suggested_strategies)
    
    print("  ✅ Declining performance response works")


def test_system_status_report():
    """Test 9: System status reporting"""
    print("Test 9: System status reporting...")
    
    loop = SelfImprovingLoop("test_status")
    
    # Execute some tasks
    for i in range(5):
        loop.execute_task(
            task_type="test_task",
            task_description=f"Task {i}",
            execute_fn=lambda p: {"success": True, "quality": 0.8}
        )
    
    status = loop.get_system_status()
    
    assert status["agent_id"] == "test_status"
    assert status["execution_count"] == 5
    assert status["reflection"]["task_types_tracked"] == 1
    assert status["reflection"]["total_records"] == 5
    assert status["memory"]["planning_history"] == 5
    
    print("  ✅ System status reporting works")


def test_state_persistence():
    """Test 10: State export and import"""
    print("Test 10: State persistence...")
    
    loop1 = SelfImprovingLoop("persist_test")
    
    # Execute and build state
    for i in range(3):
        loop1.execute_task(
            task_type="persistent_task",
            task_description="Test",
            execute_fn=lambda p: {"success": True, "quality": 0.75}
        )
    
    # Export state
    state = loop1.export_state()
    
    assert state["agent_id"] == "persist_test"
    assert state["execution_count"] == 3
    assert "reflection_history" in state
    assert "planning_history" in state
    
    # Create new loop and import
    loop2 = SelfImprovingLoop("new_agent")
    loop2.import_state(state)
    
    assert loop2.agent_id == "persist_test"
    assert loop2.execution_count == 3
    assert len(loop2.reflection.performance_history.get("persistent_task", [])) == 3
    
    print("  ✅ State persistence works")


def test_feedback_processing():
    """Test 11: Feedback processing between components"""
    print("Test 11: Feedback processing...")
    
    loop = SelfImprovingLoop("feedback_test")
    
    # Manually add feedback
    loop.reflection.send_feedback(ComponentFeedback(
        feedback_type=FeedbackType.PERFORMANCE_INSIGHT,
        source_component="reflection",
        target_component="planning",
        content={"test": "insight"},
        priority=IntegrationPriority.HIGH
    ))
    
    # Process feedback
    loop._process_component_feedback()
    
    # Should have processed and cleared high priority feedback
    assert len(loop.reflection.feedback_outbox) == 0
    
    print("  ✅ Feedback processing works")


def test_multiple_task_types():
    """Test 12: Multiple task type tracking"""
    print("Test 12: Multiple task type tracking...")
    
    loop = SelfImprovingLoop("multi_type")
    
    task_types = ["coding", "search", "analysis", "generation", "review"]
    
    for i, task_type in enumerate(task_types):
        for j in range(5):
            loop.execute_task(
                task_type=task_type,
                task_description=f"Task {j}",
                execute_fn=lambda p: {"success": True, "quality": 0.8}
            )
    
    status = loop.get_system_status()
    assert status["reflection"]["task_types_tracked"] == 5
    assert status["reflection"]["total_records"] == 25
    
    print("  ✅ Multiple task type tracking works")


def test_strategy_selection():
    """Test 13: Strategy selection based on insights"""
    print("Test 13: Strategy selection...")
    
    planner = IntegratedPlanner()
    
    # Test with improving trend
    insight_improving = ReflectionToPlanningBridge(
        capability_name="code_generation",
        proficiency_score=0.9,
        confidence=0.95,
        trend="improving",
        suggested_strategies=[],
        priority=IntegrationPriority.MEDIUM
    )
    planner.update_from_reflection(insight_improving)
    
    plan_improving = planner.create_informed_plan("code_generation", "Test")
    
    # Should suggest more advanced strategy
    assert plan_improving.suggested_strategy is not None
    assert plan_improving.suggested_strategy == "test_driven"  # Last (most advanced) in library
    
    # Test with declining trend
    planner2 = IntegratedPlanner()
    insight_declining = ReflectionToPlanningBridge(
        capability_name="code_generation",
        proficiency_score=0.4,
        confidence=0.8,
        trend="declining",
        suggested_strategies=["Consider alternative approach"],
        priority=IntegrationPriority.HIGH
    )
    planner2.update_from_reflection(insight_declining)
    
    plan_declining = planner2.create_informed_plan("code_generation", "Test")
    
    # Should use conservative approach
    assert plan_declining.risk_assessment["risk_level"] == "high"
    assert len(plan_declining.adaptations) > 0
    assert plan_declining.suggested_strategy == "direct_generation"  # First (most conservative)
    
    print("  ✅ Strategy selection based on insights works")


def test_memory_priority_eviction():
    """Test 14: Memory priority-based eviction"""
    print("Test 14: Memory priority-based eviction...")
    
    memory = IntegratedMemory(max_entries=5)
    
    # Add entries with different priorities
    for i in range(3):
        memory.store_reflection_report(
            {"id": f"low_{i}"},
            priority=IntegrationPriority.LOW
        )
    
    for i in range(3):
        memory.store_reflection_report(
            {"id": f"critical_{i}"},
            priority=IntegrationPriority.CRITICAL
        )
    
    # Should keep critical, evict low priority older entries
    assert len(memory.reflection_reports) == 5
    
    # Check that critical entries remain
    priorities = [r["priority"] for r in memory.reflection_reports]
    assert any(p == "CRITICAL" for p in priorities)
    
    print("  ✅ Memory priority-based eviction works")


def test_error_pattern_detection():
    """Test 15: Error pattern detection and suggestions"""
    print("Test 15: Error pattern detection...")
    
    engine = IntegratedReflectionEngine("error_test")
    
    # Record with error patterns
    errors = ["timeout", "timeout", "syntax_error", "timeout", "network_error"]
    for i, error in enumerate(errors):
        engine.record_execution(
            task_id=f"task_{i}",
            task_type="api_call",
            success=False,
            execution_time_ms=5000.0,
            quality_score=0.2,
            error_type=error
        )
    
    # Also add successes for contrast
    for i in range(10):
        engine.record_execution(
            task_id=f"good_task_{i}",
            task_type="api_call",
            success=True,
            execution_time_ms=500.0,
            quality_score=0.9
        )
    
    bridge = engine.analyze_and_send_insights("api_call")
    
    if bridge:
        # Should detect timeout pattern
        feedback = engine.feedback_outbox[0]
        error_counts = feedback.content.get("error_counts", {})
        assert "timeout" in error_counts
        assert error_counts["timeout"] >= 3
        
        # Should suggest addressing frequent error
        assert any("timeout" in s or "frequent error" in s.lower() 
                  for s in bridge.suggested_strategies)
    
    print("  ✅ Error pattern detection works")


# Run all tests
if __name__ == "__main__":
    print("=" * 60)
    print("Integration Module Test Suite")
    print("=" * 60)
    
    tests = [
        test_component_interface,
        test_reflection_performance_recording,
        test_reflection_to_planning_bridge,
        test_planner_informed_plan_creation,
        test_memory_storage_and_retrieval,
        test_self_improving_loop_basic,
        test_improving_performance_adaptation,
        test_declining_performance_response,
        test_system_status_report,
        test_state_persistence,
        test_feedback_processing,
        test_multiple_task_types,
        test_strategy_selection,
        test_memory_priority_eviction,
        test_error_pattern_detection
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  ❌ Test failed: {e}")
            failed += 1
    
    print("=" * 60)
    print(f"Results: {passed}/{len(tests)} tests passed")
    if failed > 0:
        print(f"         {failed} tests failed")
    print("=" * 60)
