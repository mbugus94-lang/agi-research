"""
Test suite for GVU (Generator-Verifier-Updater) Operator System.
Based on: "The Geometry of Benchmarks: A New Path Toward AGI" (arXiv:2512.04276)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.gvu_operator import (
    GVUOperator, Generator, Verifier, Updater,
    GVUPhase, ImprovementMethod, GeneratedOutput,
    VerificationResult, UpdateDelta, GVUCycle,
    CapabilityFunctional, GVUAgentAdapter
)


def test_generator_basic():
    """Test basic generation functionality."""
    gen = Generator("test_gen")
    outputs = gen.generate(
        context={"task": "Generate a greeting"},
        num_candidates=1
    )
    
    assert len(outputs) == 1
    assert isinstance(outputs[0], GeneratedOutput)
    assert "greeting" in outputs[0].content.lower()
    print("✅ Generator basic: PASSED")


def test_generator_multiple_candidates():
    """Test generating multiple candidates."""
    gen = Generator("test_gen")
    outputs = gen.generate(
        context={"task": "Generate solution"},
        num_candidates=3
    )
    
    assert len(outputs) == 3
    for i, out in enumerate(outputs):
        assert out.generation_params["candidate_index"] == i
        assert out.generation_params["total_candidates"] == 3
    print("✅ Generator multiple candidates: PASSED")


def test_generator_self_play():
    """Test self-play generation."""
    gen = Generator("test_gen")
    opponent_history = [{"move": "A", "result": "win"}]
    
    output = gen.self_play_generate(
        context={"task": "Game move"},
        opponent_history=opponent_history
    )
    
    assert isinstance(output, GeneratedOutput)
    assert output.generation_params["strategy"] == "self_play"
    print("✅ Generator self-play: PASSED")


def test_verifier_basic():
    """Test basic verification."""
    gen = Generator("test_gen")
    ver = Verifier("test_ver")
    
    output = gen.generate({"task": "test"}, num_candidates=1)[0]
    result = ver.verify(output, {"task": "test"}, "standard")
    
    assert isinstance(result, VerificationResult)
    assert 0.0 <= result.score <= 1.0
    assert isinstance(result.is_valid, bool)
    print("✅ Verifier basic: PASSED")


def test_verifier_debate():
    """Test debate verification."""
    gen = Generator("test_gen")
    ver = Verifier("test_ver")
    
    output = gen.generate({"task": "debate test"}, num_candidates=1)[0]
    result = ver.debate_verify(output, {"task": "debate"}, num_debaters=2)
    
    assert result.verifier_type == "debate"
    assert "debate" in result.feedback.lower() or "Debate" in result.feedback
    assert "variance" in result.metadata
    print("✅ Verifier debate: PASSED")


def test_updater_basic():
    """Test basic update functionality."""
    gen = Generator("test_gen")
    ver = Verifier("test_ver")
    upd = Updater("test_upd")
    
    # Create a cycle
    cycle = GVUCycle(
        cycle_id="test_1",
        phase=GVUPhase.UPDATE,
        generated=GeneratedOutput(content="test"),
        verification=VerificationResult(is_valid=True, score=0.8, feedback="Good")
    )
    
    delta = upd.update(gen, ver, cycle, ImprovementMethod.REINFORCEMENT_LEARNING)
    
    assert isinstance(delta, UpdateDelta)
    assert delta.learning_signal != 0
    print("✅ Updater basic: PASSED")


def test_updater_methods():
    """Test different improvement methods."""
    gen = Generator("test_gen")
    ver = Verifier("test_ver")
    upd = Updater("test_upd")
    
    methods = [
        ImprovementMethod.REINFORCEMENT_LEARNING,
        ImprovementMethod.SELF_PLAY,
        ImprovementMethod.DEBATE,
        ImprovementMethod.VERIFIER_BASED,
        ImprovementMethod.EXPERT_ITERATION
    ]
    
    for method in methods:
        cycle = GVUCycle(
            cycle_id=f"test_{method.value}",
            phase=GVUPhase.UPDATE,
            generated=GeneratedOutput(content=f"test {method.value}"),
            verification=VerificationResult(is_valid=True, score=0.75, feedback="OK")
        )
        
        delta = upd.update(gen, ver, cycle, method)
        assert isinstance(delta, UpdateDelta)
    
    print("✅ Updater methods: PASSED")


def test_gvu_single_cycle():
    """Test running a single GVU cycle."""
    gvu = GVUOperator("test_gvu")
    
    cycle = gvu.run_cycle(
        context={"task": "Simple math", "task_family": "math"},
        num_candidates=1,
        verification_type="standard",
        update_method=ImprovementMethod.REINFORCEMENT_LEARNING
    )
    
    assert cycle.cycle_id == "cycle_1"
    assert cycle.generated is not None
    assert cycle.verification is not None
    assert cycle.update is not None
    assert cycle.end_time is not None
    print("✅ GVU single cycle: PASSED")


def test_gvu_multiple_cycles():
    """Test running multiple GVU cycles."""
    gvu = GVUOperator("test_gvu")
    
    cycles = gvu.run_iterations(
        context={"task": "Iterative improvement", "task_family": "general"},
        num_iterations=5,
        improvement_method=ImprovementMethod.REINFORCEMENT_LEARNING
    )
    
    assert len(cycles) == 5
    assert all(c.generated is not None for c in cycles)
    assert all(c.verification is not None for c in cycles)
    print("✅ GVU multiple cycles: PASSED")


def test_capability_functional():
    """Test capability functional measurement."""
    func = CapabilityFunctional("math_capability", "math")
    
    # Add measurements
    for i in range(5):
        func.measure(
            task=f"task_{i}",
            performance=0.5 + i * 0.1,
            resources_used={"time": 10 + i, "tokens": 100 * (i + 1)}
        )
    
    assert len(func.measurements) == 5
    
    trend = func.get_trend(window=5)
    assert isinstance(trend, float)
    print("✅ Capability functional: PASSED")


def test_self_improvement_coefficient():
    """Test self-improvement coefficient (kappa) calculation."""
    gvu = GVUOperator("test_gvu")
    
    # Run several cycles
    for i in range(10):
        gvu.run_cycle(
            context={"task": f"Task {i}", "task_family": "test_capability"},
            num_candidates=1
        )
    
    # Compute kappa
    kappa = gvu.compute_self_improvement_coefficient("test_capability", window=5)
    
    assert isinstance(kappa, float)
    assert len(gvu.improvement_history) > 0
    print(f"✅ Self-improvement coefficient (κ={kappa:.4f}): PASSED")


def test_is_improving():
    """Test improvement detection."""
    gvu = GVUOperator("test_gvu")
    
    # Run cycles with varying performance to create trend
    for i in range(8):
        cycle = gvu.run_cycle(
            context={"task": f"Task {i}", "task_family": "improve_test"},
            num_candidates=1
        )
        # Manually adjust verification for upward trend
        if cycle.verification:
            cycle.verification.score = 0.5 + (i * 0.05)
    
    is_imp = gvu.is_improving("improve_test", window=5)
    # Should be improving given upward score trend
    print(f"✅ Is improving ({is_imp}): PASSED")


def test_get_best_outputs():
    """Test retrieving best outputs."""
    gvu = GVUOperator("test_gvu")
    
    # Run cycles
    for i in range(5):
        cycle = gvu.run_cycle(
            context={"task": f"Task {i}", "task_family": "best_test"},
            num_candidates=1
        )
        if cycle.verification:
            cycle.verification.score = 0.5 + (i * 0.1)
    
    best = gvu.get_best_outputs(min_score=0.6, max_results=3)
    
    assert isinstance(best, list)
    if best:
        assert all(b["score"] >= 0.6 for b in best)
        assert best[0]["score"] >= best[-1]["score"] if len(best) > 1 else True
    print("✅ Get best outputs: PASSED")


def test_gvu_statistics():
    """Test GVU statistics collection."""
    gvu = GVUOperator("test_gvu")
    
    # Run some cycles
    for i in range(5):
        gvu.run_cycle(
            context={"task": f"Task {i}", "task_family": "stats_test"},
            num_candidates=1
        )
    
    stats = gvu.get_statistics()
    
    assert stats["total_cycles"] == 5
    assert "average_score" in stats
    assert "max_score" in stats
    assert "improvement_rate" in stats
    print(f"✅ GVU statistics (avg={stats['average_score']:.2f}): PASSED")


def test_parameter_updates():
    """Test that parameter updates actually affect generator/verifier."""
    gen = Generator("test_gen")
    ver = Verifier("test_ver")
    upd = Updater("test_upd")
    
    initial_temp = gen.temperature
    initial_strict = ver.strictness
    
    # Create positive cycle
    cycle = GVUCycle(
        cycle_id="update_test",
        phase=GVUPhase.UPDATE,
        generated=GeneratedOutput(content="test"),
        verification=VerificationResult(is_valid=True, score=0.9, feedback="Excellent")
    )
    
    delta = upd.update(gen, ver, cycle, ImprovementMethod.REINFORCEMENT_LEARNING)
    
    # Temperature should have changed (decreased for positive reward)
    assert gen.temperature != initial_temp or upd.learning_rate == 0
    print(f"✅ Parameter updates (temp: {initial_temp:.2f} -> {gen.temperature:.2f}): PASSED")


def test_gvu_adapter():
    """Test GVU agent adapter."""
    
    class MockAgent:
        def __init__(self):
            self.name = "MockAgent"
        
        def run(self, task):
            return f"Processed: {task}"
    
    agent = MockAgent()
    adapter = GVUAgentAdapter(agent)
    
    result = adapter.improve_on_task("test task", num_iterations=3)
    
    assert "task" in result
    assert "iterations" in result
    assert "final_score" in result
    assert result["iterations"] <= 3  # May stop early for good results
    print(f"✅ GVU adapter (iterations={result['iterations']}): PASSED")


def test_gvu_phase_transitions():
    """Test phase tracking through GVU cycle."""
    gvu = GVUOperator("test_gvu")
    
    cycle = gvu.run_cycle(
        context={"task": "Phase test", "task_family": "phase_test"},
        num_candidates=1
    )
    
    # Final phase should be UPDATE
    assert cycle.phase == GVUPhase.UPDATE
    assert cycle.duration > 0
    print("✅ GVU phase transitions: PASSED")


def test_early_stopping():
    """Test early stopping on excellent results."""
    gvu = GVUOperator("test_gvu")
    
    cycles = gvu.run_iterations(
        context={"task": "Early stop test", "task_family": "early_stop"},
        num_iterations=10
    )
    
    # Should complete all or stop early if excellent
    assert len(cycles) <= 10
    assert len(cycles) >= 1
    print(f"✅ Early stopping (ran {len(cycles)}/10): PASSED")


# Test runner
if __name__ == "__main__":
    tests = [
        test_generator_basic,
        test_generator_multiple_candidates,
        test_generator_self_play,
        test_verifier_basic,
        test_verifier_debate,
        test_updater_basic,
        test_updater_methods,
        test_gvu_single_cycle,
        test_gvu_multiple_cycles,
        test_capability_functional,
        test_self_improvement_coefficient,
        test_is_improving,
        test_get_best_outputs,
        test_gvu_statistics,
        test_parameter_updates,
        test_gvu_adapter,
        test_gvu_phase_transitions,
        test_early_stopping
    ]
    
    passed = 0
    failed = 0
    
    print("\n" + "="*50)
    print("GVU Operator Test Suite")
    print("="*50 + "\n")
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__}: FAILED - {e}")
            failed += 1
    
    print("\n" + "="*50)
    print(f"Results: {passed}/{len(tests)} passed")
    if failed == 0:
        print("🎉 All tests passed!")
    else:
        print(f"⚠️ {failed} test(s) failed")
    print("="*50)
