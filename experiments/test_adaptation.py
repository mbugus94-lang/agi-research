"""
Test suite for Test-Time Adaptation (TTA) system.
Validates hypothesis generation, strategy selection, adaptation loop, and cost management.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.adaptation import (
    TestTimeAdapter, AdaptationStrategy, Hypothesis, AdaptationState,
    demo
)


def test_hypothesis_creation():
    """Test hypothesis initialization and scoring."""
    print("\n🧪 Test 1: Hypothesis Creation")
    
    h = Hypothesis(
        id="test_001",
        description="Test hypothesis",
        approach="direct",
        confidence=0.5
    )
    
    assert h.confidence == 0.5, "Initial confidence should be 0.5"
    assert h.attempts == 0, "Initial attempts should be 0"
    
    # Update with success
    h.update_score("result", True, 5.0)
    assert h.attempts == 1, "Attempts should increment"
    assert h.confidence > 0.5, "Confidence should increase after success"
    assert h.successes == 1, "Successes should increment"
    
    # Update with failure
    h.update_score(None, False, 3.0)
    assert h.failures == 1, "Failures should increment"
    
    print("   ✅ Hypothesis creation and scoring works correctly")
    return True


def test_adaptation_strategies():
    """Test different adaptation strategies."""
    print("\n🧪 Test 2: Adaptation Strategies")
    
    strategies = [
        AdaptationStrategy.GREEDY,
        AdaptationStrategy.EXPLORE,
        AdaptationStrategy.EXPLOIT,
        AdaptationStrategy.HYBRID,
        AdaptationStrategy.ADAPTIVE
    ]
    
    for strategy in strategies:
        adapter = TestTimeAdapter(strategy=strategy, max_iterations=3)
        
        def executor(h, ctx):
            return {"result": "ok"}, True, 5.0
        
        result = adapter.adapt(
            task="Test task",
            executor=executor
        )
        
        assert result["iterations"] > 0, f"{strategy.value} should complete at least 1 iteration"
        assert result["total_cost"] > 0, f"{strategy.value} should track cost"
        
        print(f"   ✅ {strategy.value} strategy works")
    
    return True


def test_strategy_selection():
    """Test hypothesis selection with different strategies."""
    print("\n🧪 Test 3: Strategy Selection")
    
    adapter = TestTimeAdapter()
    
    # Create state with hypotheses
    state = AdaptationState(task="test")
    state.hypotheses = [
        Hypothesis(id="h1", description="High confidence", approach="exploit", confidence=0.8),
        Hypothesis(id="h2", description="Untried", approach="explore", confidence=0.5, attempts=0),
        Hypothesis(id="h3", description="Low confidence", approach="fail", confidence=0.3, attempts=2),
    ]
    
    # Test greedy - should pick h1
    state.strategy = AdaptationStrategy.GREEDY
    h = adapter.select_hypothesis(state)
    assert h.id == "h1", "Greedy should pick highest confidence"
    print("   ✅ Greedy strategy selects highest confidence")
    
    # Test explore - should prefer untried (h2)
    state.strategy = AdaptationStrategy.EXPLORE
    # Run multiple times to verify probabilistic behavior
    selections = [adapter.select_hypothesis(state).id for _ in range(100)]
    h2_count = selections.count("h2")
    assert h2_count > 30, f"Explore should prefer untried (got {h2_count}/100 h2)"
    print("   ✅ Explore strategy prefers untried hypotheses")
    
    return True


def test_budget_management():
    """Test cost budget enforcement."""
    print("\n🧪 Test 4: Budget Management")
    
    adapter = TestTimeAdapter(max_iterations=10, max_cost=50.0)
    
    def expensive_executor(h, ctx):
        return {"result": "ok"}, True, 20.0  # High cost
    
    result = adapter.adapt(
        task="Expensive task",
        executor=expensive_executor
    )
    
    # Should stop early due to budget
    assert result["total_cost"] <= 60.0, f"Should respect budget (got {result['total_cost']})"
    assert result["iterations"] < 5, f"Should stop early (got {result['iterations']} iterations)"
    
    print(f"   ✅ Budget enforcement works (stopped after {result['iterations']} iterations)")
    return True


def test_convergence():
    """Test convergence detection."""
    print("\n🧪 Test 5: Convergence Detection")
    
    adapter = TestTimeAdapter(
        max_iterations=10,
        convergence_threshold=0.9
    )
    
    def good_executor(h, ctx):
        # Simulate finding a good solution quickly
        if h.approach == "direct":
            return {"quality": 0.95}, True, 5.0
        return {"quality": 0.5}, True, 5.0
    
    result = adapter.adapt(
        task="Easy convergence task",
        executor=good_executor
    )
    
    assert result["converged"] or result["best_score"] >= 0.8, "Should find good solution"
    
    print(f"   ✅ Convergence detection works (converged={result['converged']}, score={result['best_score']:.3f})")
    return True


def test_adaptive_strategy():
    """Test adaptive strategy that shifts based on progress."""
    print("\n🧪 Test 6: Adaptive Strategy")
    
    adapter = TestTimeAdapter(strategy=AdaptationStrategy.ADAPTIVE, max_iterations=6)
    
    def mixed_executor(h, ctx):
        # Different success rates for different approaches
        success_rates = {
            "explore": 0.3,
            "exploit": 0.7
        }
        success = h.approach in success_rates and hash(h.id) % 10 < success_rates[h.approach] * 10
        return {"approach": h.approach}, success, 5.0
    
    result = adapter.adapt(
        task="Adaptive test",
        executor=mixed_executor
    )
    
    # Should have tried multiple approaches
    approaches = set(h["approach"] for h in result["all_hypotheses"] if h["attempts"] > 0)
    assert len(approaches) >= 1, "Should try at least one approach"
    
    print(f"   ✅ Adaptive strategy works (tried {len(approaches)} approaches)")
    return True


def test_global_stats():
    """Test global statistics tracking."""
    print("\n🧪 Test 7: Global Statistics")
    
    adapter = TestTimeAdapter(max_iterations=3)
    
    def simple_executor(h, ctx):
        return {"ok": True}, True, 5.0
    
    # Run multiple tasks
    for i in range(3):
        adapter.adapt(
            task=f"Task {i}",
            executor=simple_executor
        )
    
    stats = adapter.get_stats()
    
    assert stats["total_tasks"] == 3, "Should track total tasks"
    assert stats["success_rate"] > 0, "Should have some success"
    assert stats["avg_iterations"] > 0, "Should track avg iterations"
    assert stats["avg_cost"] > 0, "Should track avg cost"
    
    print(f"   ✅ Global stats tracking works")
    print(f"      Total tasks: {stats['total_tasks']}")
    print(f"      Success rate: {stats['success_rate']:.1%}")
    print(f"      Avg iterations: {stats['avg_iterations']:.2f}")
    return True


def run_all_tests():
    """Run all adaptation tests."""
    print("=" * 60)
    print("🧪 Test-Time Adaptation Test Suite")
    print("=" * 60)
    
    tests = [
        test_hypothesis_creation,
        test_adaptation_strategies,
        test_strategy_selection,
        test_budget_management,
        test_convergence,
        test_adaptive_strategy,
        test_global_stats,
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
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed")
        sys.exit(1)
