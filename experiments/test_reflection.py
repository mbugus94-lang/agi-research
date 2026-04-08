"""
Test suite for Reflection system.
Validates performance analysis, error detection, and improvement recommendations.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.reflection import Reflector, PerformanceMetrics, ReflectionResult


def test_metrics_calculation():
    """Test performance metrics calculation."""
    print("\n🧪 Test 1: Performance Metrics")
    
    metrics = PerformanceMetrics()
    
    # Record some outcomes
    metrics.record_attempt(success=True, duration=5.0, cost=1.0)
    metrics.record_attempt(success=True, duration=3.0, cost=0.5)
    metrics.record_attempt(success=False, duration=10.0, cost=2.0)
    
    # Calculate stats
    stats = metrics.get_stats()
    
    assert stats["total_attempts"] == 3, "Should have 3 attempts"
    assert stats["successes"] == 2, "Should have 2 successes"
    assert stats["failures"] == 1, "Should have 1 failure"
    assert abs(stats["success_rate"] - 0.667) < 0.01, "Success rate should be ~66.7%"
    
    print("   ✅ Performance metrics calculation works correctly")
    return True


def test_reflection_basic():
    """Test basic reflection functionality."""
    print("\n🧪 Test 2: Basic Reflection")
    
    reflector = Reflector()
    
    # Simulate execution history
    history = [
        {"step": 1, "action": "search", "success": True, "duration": 2.0},
        {"step": 2, "action": "analyze", "success": True, "duration": 3.0},
        {"step": 3, "action": "generate", "success": False, "duration": 5.0, "error": "Timeout"},
    ]
    
    result = reflector.reflect(history, task="Complete research task")
    
    assert isinstance(result, ReflectionResult), "Should return ReflectionResult"
    assert len(result.insights) > 0, "Should generate insights"
    
    print("   ✅ Basic reflection works correctly")
    return True


def test_error_pattern_detection():
    """Test detection of error patterns."""
    print("\n🧪 Test 3: Error Pattern Detection")
    
    reflector = Reflector()
    
    # History with repeated timeout errors
    history = [
        {"step": 1, "action": "api_call", "success": False, "error": "Timeout"},
        {"step": 2, "action": "api_call", "success": False, "error": "Timeout"},
        {"step": 3, "action": "api_call", "success": False, "error": "Timeout"},
    ]
    
    result = reflector.reflect(history, task="API integration")
    
    # Should detect timeout pattern
    timeout_insights = [i for i in result.insights if "timeout" in i.lower() or "api" in i.lower()]
    assert len(timeout_insights) > 0, "Should detect API/timeout issues"
    
    # Should recommend retries or alternative approach
    has_recommendation = any(
        "retry" in r.lower() or "alternative" in r.lower() 
        for r in result.recommendations
    )
    assert has_recommendation, "Should recommend handling timeouts"
    
    print("   ✅ Error pattern detection works correctly")
    return True


def test_success_pattern_learning():
    """Test learning from successful patterns."""
    print("\n🧪 Test 4: Success Pattern Learning")
    
    reflector = Reflector()
    
    # History with successful decomposition
    history = [
        {"step": 1, "action": "decompose", "success": True, "duration": 1.0},
        {"step": 2, "action": "execute_sub_1", "success": True, "duration": 2.0},
        {"step": 3, "action": "execute_sub_2", "success": True, "duration": 2.0},
        {"step": 4, "action": "combine", "success": True, "duration": 1.0},
    ]
    
    result = reflector.reflect(history, task="Complex problem solving")
    
    # Should recognize successful pattern
    pattern_recognized = any(
        "decompos" in i.lower() or "break down" in i.lower()
        for i in result.insights
    )
    assert pattern_recognized, "Should recognize decomposition pattern"
    
    # Should recommend similar approach for future
    has_positive_rec = any(
        "continue" in r.lower() or "similar" in r.lower()
        for r in result.recommendations
    )
    
    print("   ✅ Success pattern learning works correctly")
    return True


def test_improvement_tracking():
    """Test tracking of improvements over time."""
    print("\n🧪 Test 5: Improvement Tracking")
    
    reflector = Reflector()
    
    # First attempt - poor performance
    history1 = [
        {"step": 1, "action": "direct_attempt", "success": False, "duration": 10.0},
    ]
    
    result1 = reflector.reflect(history1, task="Solve problem")
    
    # Second attempt - improved with decomposition
    history2 = [
        {"step": 1, "action": "decompose", "success": True, "duration": 1.0},
        {"step": 2, "action": "solve_part_1", "success": True, "duration": 2.0},
        {"step": 3, "action": "solve_part_2", "success": True, "duration": 2.0},
    ]
    
    result2 = reflector.reflect(history2, task="Solve problem (retry)")
    
    # Compare and track improvement
    improvement = reflector.compare_with_baseline(result2, result1)
    
    assert improvement is not None, "Should be able to compare results"
    assert "better" in improvement.lower() or "improve" in improvement.lower(), "Should detect improvement"
    
    print("   ✅ Improvement tracking works correctly")
    return True


def test_reflection_integration():
    """Test reflection integration with adaptation."""
    print("\n🧪 Test 6: Reflection Integration")
    
    from core.adaptation import TestTimeAdapter, Hypothesis
    
    reflector = Reflector()
    adapter = TestTimeAdapter(max_iterations=5)
    
    # Simulate an adaptation run
    def executor_with_reflection(h: Hypothesis, ctx):
        # Simulate task execution with reflection
        success = h.approach != "failing_approach"
        
        # Generate execution history for reflection
        history = [
            {"step": 1, "action": h.approach, "success": success, "duration": 3.0}
        ]
        
        # Reflect on this attempt
        if not success:
            reflection = reflector.reflect(history, task="Test execution")
            # Could use reflection to adjust next hypothesis
        
        return {"approach": h.approach}, success, 5.0
    
    # Run adaptation with reflection-enhanced executor
    result = adapter.adapt(
        task="Test with reflection",
        executor=executor_with_reflection
    )
    
    assert result["iterations"] > 0, "Should complete iterations"
    
    print("   ✅ Reflection integration works correctly")
    return True


def run_all_tests():
    """Run all reflection tests."""
    print("=" * 60)
    print("🧪 Reflection System Test Suite")
    print("=" * 60)
    
    tests = [
        test_metrics_calculation,
        test_reflection_basic,
        test_error_pattern_detection,
        test_success_pattern_learning,
        test_improvement_tracking,
        test_reflection_integration,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"   ❌ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Results: {passed}/{passed+failed} tests passed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    
    if success:
        print("\n✅ All reflection tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)
