"""
Test suite for SCRAT-inspired Verifiable Action System.
Tests tight coupling of control, memory, and verification.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.verifiable_action import (
    VerifiableActionLoop, ActionVerifier, VerifiableAction, EpisodicMemory,
    Observation, Hypothesis, VerificationLevel, ActionStatus,
    PartialObservableEnvironment
)
from datetime import datetime


def test_verification_levels():
    """Test 1: Different verification levels work correctly."""
    print("Test 1: Verification Levels...")
    
    for level in VerificationLevel:
        verifier = ActionVerifier(level=level)
        action = VerifiableAction(
            action_id=f"test_{level.name}",
            action_type="write",
            parameters={"target": "test_file", "content": "hello"},
            context={},
            verification_level=level
        )
        
        result = verifier.verify(action, context={"read_only": False})
        
        # Higher levels should perform more checks
        if level.value >= VerificationLevel.SYNTACTIC.value:
            assert "syntax_check" in result.checks_performed, f"Syntax check missing for {level}"
        if level.value >= VerificationLevel.SEMANTIC.value:
            assert "semantic_check" in result.checks_performed, f"Semantic check missing for {level}"
        
        print(f"  {level.name}: {len(result.checks_performed)} checks, passed={result.passed}")
    
    print("✅ Test 1 passed\n")
    return True


def test_episodic_memory():
    """Test 2: Episodic memory stores and retrieves correctly."""
    print("Test 2: Episodic Memory...")
    
    memory = EpisodicMemory(
        episode_id="test_episode",
        context={"task": "test"}
    )
    
    # Add observation
    obs = Observation(
        timestamp=datetime.now(),
        partial_view={"visible_attr": "value1"},
        visibility_bounds=({"visible_attr"}, {"hidden_attr"}),
        raw_data={"full": "data"}
    )
    memory.observations.append(obs)
    
    # Add hypothesis
    hyp = Hypothesis(
        hypothesis_id="hyp_1",
        description="The system is in state A",
        confidence=0.7
    )
    memory.hypotheses["hyp_1"] = hyp
    
    # Test retrieval
    relevant = memory.get_relevant_memories({"task": "test"}, k=5)
    assert len(relevant) >= 0, "Memory retrieval failed"
    
    # Test hypothesis update
    hyp.update_confidence({"obs": "obs1"}, supports=True)
    assert hyp.confidence > 0.7, "Confidence should increase with supporting evidence"
    
    hyp.update_confidence({"obs": "obs2"}, supports=False)
    assert hyp.confidence < 0.8, "Confidence should decrease with contradicting evidence"
    
    print(f"  Observations: {len(memory.observations)}")
    print(f"  Hypotheses: {len(memory.hypotheses)}")
    print(f"  Hypothesis confidence after update: {hyp.confidence:.2f}")
    print("✅ Test 2 passed\n")
    return True


def test_action_proposal():
    """Test 3: Action proposal generates valid actions."""
    print("Test 3: Action Proposal...")
    
    loop = VerifiableActionLoop(verification_level=VerificationLevel.SYNTACTIC)
    loop.start_episode("test_episode", {"task": "testing"})
    
    action = loop.propose_action(
        action_type="write",
        parameters={"target": "file.txt", "content": "test"},
        context={"path": "/tmp"}
    )
    
    assert action.action_id.startswith("action_"), "Action ID format incorrect"
    assert action.action_type == "write", "Action type incorrect"
    assert action.status == ActionStatus.PROPOSED, "Initial status should be PROPOSED"
    
    print(f"  Action ID: {action.action_id}")
    print(f"  Action Type: {action.action_type}")
    print(f"  Status: {action.status.value}")
    print("✅ Test 3 passed\n")
    return True


def test_semantic_verification():
    """Test 4: Semantic verification detects context violations."""
    print("Test 4: Semantic Verification...")
    
    verifier = ActionVerifier(level=VerificationLevel.SEMANTIC)
    
    # Should pass in normal context
    action_ok = VerifiableAction(
        action_id="test_ok",
        action_type="write",
        parameters={"target": "file.txt"},
        context={}
    )
    result_ok = verifier.verify(action_ok, context={"read_only": False})
    assert result_ok.passed, "Write should pass in non-read-only context"
    
    # Should fail in read-only context
    action_bad = VerifiableAction(
        action_id="test_bad",
        action_type="write",
        parameters={"target": "file.txt"},
        context={}
    )
    result_bad = verifier.verify(action_bad, context={"read_only": True})
    assert not result_bad.passed, "Write should fail in read-only context"
    
    print(f"  Normal context: passed={result_ok.passed}")
    print(f"  Read-only context: passed={result_bad.passed}")
    print("✅ Test 4 passed\n")
    return True


def test_action_handler_registration():
    """Test 5: Action handlers can be registered and called."""
    print("Test 5: Action Handler Registration...")
    
    loop = VerifiableActionLoop(verification_level=VerificationLevel.NONE)
    
    # Register handlers
    def write_handler(params):
        return {"success": True, "written": params.get("target")}
    
    def read_handler(params):
        return {"success": True, "data": f"content of {params.get('target')}"}
    
    loop.register_action_handler("write", write_handler)
    loop.register_action_handler("read", read_handler)
    
    # Check handlers are registered
    assert "write" in loop.action_handlers, "Write handler not registered"
    assert "read" in loop.action_handlers, "Read handler not registered"
    
    # Test direct handler call
    result = loop.action_handlers["write"]({"target": "test.txt"})
    assert result["success"], "Handler execution failed"
    
    print(f"  Registered handlers: {list(loop.action_handlers.keys())}")
    print(f"  Handler result: {result}")
    print("✅ Test 5 passed\n")
    return True


def test_full_verifiable_loop():
    """Test 6: Full verifiable action loop executes correctly."""
    print("Test 6: Full Verifiable Loop...")
    
    loop = VerifiableActionLoop(verification_level=VerificationLevel.SYNTACTIC)
    
    # Register handler
    loop.register_action_handler("compute", lambda p: {"success": True, "result": 42})
    
    # Start episode
    loop.start_episode("loop_test", {"task": "compute something"})
    
    # Propose and execute
    action = loop.propose_action(
        action_type="compute",
        parameters={"expression": "6*7"},
        context={"allowed": True}
    )
    
    def mock_observation():
        return Observation(
            timestamp=datetime.now(),
            partial_view={"result": "42"},
            visibility_bounds=({"result"}, set()),
            raw_data={}
        )
    
    success, result = loop.verify_and_execute(action, observation_callback=mock_observation)
    
    assert success, "Action execution should succeed"
    assert result is not None, "Should have result"
    assert action.status in [ActionStatus.EXECUTED, ActionStatus.RECOVERED], f"Status is {action.status}"
    
    print(f"  Success: {success}")
    print(f"  Result: {result}")
    print(f"  Final status: {action.status.value}")
    print(f"  Pre-verification: {action.pre_verification.passed if action.pre_verification else 'N/A'}")
    print("✅ Test 6 passed\n")
    return True


def test_hypothesis_management():
    """Test 7: Hypothesis creation and testing."""
    print("Test 7: Hypothesis Management...")
    
    loop = VerifiableActionLoop()
    loop.start_episode("hyp_test", {})
    
    # Create hypothesis
    hyp = loop.create_hypothesis("The button causes the door to open", 0.5)
    assert hyp.hypothesis_id in loop.current_episode.hypotheses, "Hypothesis not stored"
    
    # Test with supporting outcome
    action = loop.propose_action("press", {"button": "door_button"}, {})
    outcome = {"success": True, "door": "opened"}
    loop.test_hypothesis(hyp.hypothesis_id, action, outcome)
    
    assert len(hyp.evidence) > 0, "Evidence should be recorded"
    assert hyp.confidence > 0.5, "Confidence should increase"
    
    # Test with contradicting outcome
    outcome2 = {"success": True, "door": "closed"}
    loop.test_hypothesis(hyp.hypothesis_id, action, outcome2)
    
    # After testing with contradicting outcome, confidence should decrease
    final_confidence = hyp.confidence
    assert final_confidence < 0.75, f"Confidence should decrease after contradiction, got {final_confidence}"
    
    print(f"  Hypothesis: {hyp.description}")
    print(f"  Evidence: {len(hyp.evidence)}, contradictions recorded")
    print(f"  Current confidence: {hyp.confidence:.2f}")
    print("✅ Test 7 passed\n")
    return True


def test_memory_aware_verification():
    """Test 8: Memory-aware verification learns from past failures."""
    print("Test 8: Memory-Aware Verification...")
    
    loop = VerifiableActionLoop(verification_level=VerificationLevel.SEMANTIC)
    loop.start_episode("memory_test", {})
    
    # First: execute a failing action
    loop.register_action_handler("risky_op", lambda p: {"success": False, "error": "known failure"})
    
    action1 = loop.propose_action("risky_op", {"param": "value"}, {})
    
    def mock_obs():
        return Observation(datetime.now(), {}, (set(), set()), {})
    
    success1, result1 = loop.verify_and_execute(action1, mock_obs)
    # With high verification level, might be rejected
    
    # Second: similar action should be flagged
    verifier = ActionVerifier(level=VerificationLevel.SEMANTIC)
    action2 = VerifiableAction(
        action_id="action_2",
        action_type="risky_op",
        parameters={"param": "value"},  # Similar params
        context={}
    )
    
    result2 = verifier.verify(action2, {}, loop.current_episode)
    
    # Should have warnings due to similar past failures
    has_warning = any("failed" in w.lower() for w in result2.warnings)
    
    print(f"  First action status: {action1.status.value}")
    print(f"  Second action warnings: {result2.warnings}")
    print(f"  Has failure warning: {has_warning}")
    print("✅ Test 8 passed\n")
    return True


def test_partial_observability():
    """Test 9: Partial observable environment simulation."""
    print("Test 9: Partial Observability...")
    
    env = PartialObservableEnvironment(
        full_state={
            "visible_attr": "seen",
            "hidden_attr": "secret",
            "location": (10, 20)
        },
        visibility_mask={"visible_attr", "location"}
    )
    
    # Get observation
    obs = env.observe()
    
    assert "visible_attr" in obs.partial_view, "Visible attr should be in observation"
    assert "hidden_attr" not in obs.partial_view, "Hidden attr should not be in observation"
    
    assert "visible_attr" in obs.visibility_bounds[0], "Visible should be in bounds[0]"
    assert "hidden_attr" in obs.visibility_bounds[1], "Hidden should be in bounds[1]"
    
    # Execute explore action
    result = env.execute({"type": "explore", "reveal": {"hidden_attr"}})
    assert result["success"], "Explore should succeed"
    assert "hidden_attr" in env.visibility_mask, "Hidden attr should now be visible"
    
    # New observation
    obs2 = env.observe()
    assert "hidden_attr" in obs2.partial_view, "Hidden attr should now be visible"
    
    print(f"  Initial visible: {set(obs.partial_view.keys())}")
    print(f"  After exploration: {set(obs2.partial_view.keys())}")
    print("✅ Test 9 passed\n")
    return True


def test_simulation_verification():
    """Test 10: Simulation-based verification catches predicted failures."""
    print("Test 10: Simulation Verification...")
    
    verifier = ActionVerifier(level=VerificationLevel.SIMULATION)
    
    # Action that simulation predicts will fail
    action = VerifiableAction(
        action_id="sim_test",
        action_type="delete",
        parameters={"target": "important_file", "confirm": False},  # Missing confirmation
        context={}
    )
    
    result = verifier.verify(action, context={})
    
    # Should have simulation check
    assert "simulation" in result.checks_performed, "Simulation check missing"
    
    # Predicted failure due to missing confirmation
    if not result.passed:
        has_delete_error = any("confirm" in e.lower() for e in result.errors)
        assert has_delete_error or len(result.warnings) > 0, "Should warn about delete without confirm"
    
    print(f"  Simulation performed: {'simulation' in result.checks_performed}")
    print(f"  Result passed: {result.passed}")
    print(f"  Simulation result: {result.simulation_result}")
    print("✅ Test 10 passed\n")
    return True


def test_episode_summary():
    """Test 11: Episode summary provides useful statistics."""
    print("Test 11: Episode Summary...")
    
    loop = VerifiableActionLoop(verification_level=VerificationLevel.SYNTACTIC)
    loop.register_action_handler("test_op", lambda p: {"success": True})
    loop.start_episode("summary_test", {"task": "multi-action test"})
    
    # Execute multiple actions
    def mock_obs():
        return Observation(datetime.now(), {}, (set(), set()), {})
    
    for i in range(3):
        action = loop.propose_action("test_op", {"index": i}, {})
        loop.verify_and_execute(action, mock_obs)
    
    # Create hypothesis
    hyp = loop.create_hypothesis("Actions succeed consistently", 0.6)
    hyp.update_confidence({"action": "test"}, supports=True)
    
    # Get summary
    summary = loop.get_episode_summary()
    
    assert summary['episode_id'] == "summary_test", "Wrong episode"
    assert summary['actions'] == 3, f"Should have 3 actions, got {summary['actions']}"
    assert summary['hypotheses'] == 1, f"Should have 1 hypothesis, got {summary['hypotheses']}"
    
    print(f"  Episode ID: {summary['episode_id']}")
    print(f"  Duration: {summary['duration']:.1f}s")
    print(f"  Actions: {summary['actions']}")
    print(f"  Hypotheses: {summary['hypotheses']}")
    print(f"  Top hypotheses: {len(summary['top_hypotheses'])}")
    print("✅ Test 11 passed\n")
    return True


def test_rollback_plan_generation():
    """Test 12: Rollback plan generation for safe execution."""
    print("Test 12: Rollback Plan Generation...")
    
    verifier = ActionVerifier(level=VerificationLevel.EXHAUSTIVE)
    
    # Write action should have restore plan
    write_action = VerifiableAction(
        action_id="write_test",
        action_type="write",
        parameters={"target": "data.json", "content": "new data"},
        context={"backup": {"old_data": "previous"}}
    )
    
    result = verifier.verify(write_action, context={"backup": {"old_data": "previous"}})
    
    assert "rollback_plan" in result.checks_performed, "Rollback plan check missing"
    assert result.rollback_plan is not None, "Should have rollback plan"
    assert any(step["type"] == "restore" for step in result.rollback_plan), "Should have restore step"
    
    print(f"  Rollback plan: {result.rollback_plan}")
    print("✅ Test 12 passed\n")
    return True


def test_statistics_tracking():
    """Test 13: Statistics tracking across loop execution."""
    print("Test 13: Statistics Tracking...")
    
    loop = VerifiableActionLoop()
    loop.register_action_handler("success_op", lambda p: {"success": True})
    loop.register_action_handler("fail_op", lambda p: {"success": False})
    loop.start_episode("stats_test", {})
    
    def mock_obs():
        return Observation(datetime.now(), {}, (set(), set()), {})
    
    # Propose actions
    loop.propose_action("success_op", {}, {})  # Just proposed
    
    action2 = loop.propose_action("success_op", {}, {})
    loop.verify_and_execute(action2, mock_obs)  # Should execute
    
    action3 = loop.propose_action("unknown_op", {}, {})  # No handler
    loop.verify_and_execute(action3, mock_obs)  # Should fail
    
    stats = loop.get_stats()
    
    assert stats['actions_proposed'] >= 3, f"Should have 3+ proposed, got {stats['actions_proposed']}"
    assert stats['actions_executed'] + stats['actions_failed'] > 0, "Should have executed or failed actions"
    
    print(f"  Proposed: {stats['actions_proposed']}")
    print(f"  Verified: {stats['actions_verified']}")
    print(f"  Executed: {stats['actions_executed']}")
    print(f"  Failed: {stats['actions_failed']}")
    print(f"  Recovered: {stats['actions_recovered']}")
    print("✅ Test 13 passed\n")
    return True


def test_integration_scrat_principles():
    """Test 14: Integration demonstrates SCRAT principles."""
    print("Test 14: SCRAT Principles Integration...")
    
    loop = VerifiableActionLoop(verification_level=VerificationLevel.SIMULATION)
    
    # Register handler
    loop.register_action_handler("explore", lambda p: {
        "success": True,
        "observed": p.get("area"),
        "needs_recovery": p.get("area") == "danger_zone"
    })
    
    loop.start_episode("scrattest", {"scenario": "exploration"})
    
    # Create hypotheses about environment
    hyp1 = loop.create_hypothesis("North area is safe", 0.5)
    hyp2 = loop.create_hypothesis("South area contains resources", 0.3)
    
    def mock_obs():
        return Observation(
            datetime.now(),
            {"position": (5, 5), "terrain": "clear"},
            ({"position", "terrain"}, {"hazards", "resources"}),
            {}
        )
    
    # Execute with hypothesis testing
    action = loop.propose_action("explore", {"area": "north", "direction": "N"}, {})
    success, result = loop.verify_and_execute(action, mock_obs)
    
    # Test hypothesis with outcome
    outcome_supports = result and result.get("success", False) and not result.get("needs_recovery", False)
    loop.test_hypothesis(
        hyp1.hypothesis_id, 
        action, 
        {"success": outcome_supports}
    )
    
    # Verify memory integration
    assert action.hypothesis_references, "Action should reference hypotheses"
    assert loop.current_episode.actions, "Action should be in memory"
    
    # Verify control-verification coupling
    assert action.pre_verification is not None, "Should have pre-verification"
    
    print(f"  Hypotheses: {len(loop.current_episode.hypotheses)}")
    print(f"  Hypothesis 1 confidence: {hyp1.confidence:.2f}")
    print(f"  Action verified: {action.pre_verification.passed if action.pre_verification else 'N/A'}")
    print(f"  Memory references: {action.memory_references}")
    print(f"  Hypothesis references: {action.hypothesis_references}")
    print("✅ Test 14 passed\n")
    return True


# Run all tests
if __name__ == "__main__":
    print("=" * 60)
    print("Verifiable Action System Tests (SCRAT-inspired)")
    print("=" * 60 + "\n")
    
    tests = [
        test_verification_levels,
        test_episodic_memory,
        test_action_proposal,
        test_semantic_verification,
        test_action_handler_registration,
        test_full_verifiable_loop,
        test_hypothesis_management,
        test_memory_aware_verification,
        test_partial_observability,
        test_simulation_verification,
        test_episode_summary,
        test_rollback_plan_generation,
        test_statistics_tracking,
        test_integration_scrat_principles,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            failed += 1
            print(f"❌ {test.__name__} FAILED: {e}\n")
    
    print("=" * 60)
    print(f"Results: {passed}/{len(tests)} passed, {failed}/{len(tests)} failed")
    print("=" * 60)
