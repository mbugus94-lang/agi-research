"""
Tests for Formal Workflow Verification System

Based on GraphFlow paper principles:
- Pre-condition checking
- Post-condition validation
- Invariant preservation
- Safety property enforcement
"""

import sys
sys.path.insert(0, '/home/workspace/agi-research')

from core.formal_workflow_verification import (
    WorkflowState,
    VerificationRule,
    VerificationType,
    VerificationSeverity,
    VerificationStatus,
    FormalWorkflowVerifier,
    VerifiedWorkflowNode,
    create_type_check,
    create_range_check,
    create_not_empty_check,
    create_dependency_check
)


class TestWorkflowState:
    """Test WorkflowState data structure"""
    
    def test_creation(self):
        """Test basic WorkflowState creation"""
        state = WorkflowState()
        assert state.variables == {}
        assert state.node_outputs == {}
        assert state.execution_path == []
        print("✓ WorkflowState creation")
    
    def test_get_set(self):
        """Test get and set operations"""
        state = WorkflowState()
        state.set("key1", "value1")
        assert state.get("key1") == "value1"
        assert state.get("nonexistent") is None
        assert state.get("nonexistent", "default") == "default"
        print("✓ Get/set operations")
    
    def test_node_output_recording(self):
        """Test recording node outputs"""
        state = WorkflowState()
        state.record_node_output("node1", {"result": "output1"})
        assert state.node_outputs["node1"] == {"result": "output1"}
        assert "node1" in state.execution_path
        print("✓ Node output recording")
    
    def test_state_copy(self):
        """Test state copying"""
        state = WorkflowState()
        state.set("var", "value")
        state.record_node_output("n1", "out")
        
        copy = state.copy()
        assert copy.get("var") == "value"
        assert copy.node_outputs["n1"] == "out"
        
        # Modifying copy shouldn't affect original
        copy.set("var", "new_value")
        assert state.get("var") == "value"
        print("✓ State copying")
    
    def test_to_dict(self):
        """Test serialization"""
        state = WorkflowState()
        state.set("x", 10)
        d = state.to_dict()
        assert d["variables"]["x"] == 10
        assert "timestamp" in d
        print("✓ State serialization")


class TestVerificationRule:
    """Test VerificationRule functionality"""
    
    def test_creation(self):
        """Test basic rule creation"""
        rule = VerificationRule(
            name="test_rule",
            rule_type=VerificationType.INVARIANT,
            severity=VerificationSeverity.ERROR
        )
        assert rule.name == "test_rule"
        assert rule.active is True
        print("✓ VerificationRule creation")
    
    def test_passing_condition(self):
        """Test rule with passing condition"""
        def always_pass(state):
            return True, None
        
        rule = VerificationRule(
            name="pass_rule",
            condition=always_pass,
            rule_type=VerificationType.PRE_CONDITION
        )
        
        state = WorkflowState()
        result = rule.evaluate(state)
        
        assert result.status == VerificationStatus.PASSING
        assert result.rule_name == "pass_rule"
        print("✓ Passing condition")
    
    def test_failing_condition(self):
        """Test rule with failing condition"""
        def always_fail(state):
            return False, "Custom failure message"
        
        rule = VerificationRule(
            name="fail_rule",
            condition=always_fail,
            rule_type=VerificationType.POST_CONDITION,
            failure_message="Explicit failure message"
        )
        
        state = WorkflowState()
        result = rule.evaluate(state)
        
        assert result.status == VerificationStatus.VIOLATED
        assert result.message == "Explicit failure message"
        print("✓ Failing condition")
    
    def test_inactive_rule(self):
        """Test inactive rule"""
        def condition(state):
            return True, None
        
        rule = VerificationRule(
            name="inactive",
            condition=condition,
            active=False
        )
        
        state = WorkflowState()
        result = rule.evaluate(state)
        
        assert result.status == VerificationStatus.UNCHECKED
        print("✓ Inactive rule")
    
    def test_node_specific_rule(self):
        """Test rule applying to specific nodes"""
        def condition(state):
            return True, None
        
        rule = VerificationRule(
            name="node_specific",
            condition=condition,
            applies_to_nodes=["node1", "node2"]
        )
        
        state = WorkflowState()
        
        # Should apply to node1
        result1 = rule.evaluate(state, "node1")
        assert result1.status == VerificationStatus.PASSING
        
        # Should not apply to node3
        result3 = rule.evaluate(state, "node3")
        assert result3.status == VerificationStatus.UNCHECKED
        print("✓ Node-specific rule")
    
    def test_condition_exception(self):
        """Test condition that raises exception"""
        def bad_condition(state):
            raise ValueError("Something went wrong")
        
        rule = VerificationRule(
            name="bad_rule",
            condition=bad_condition
        )
        
        state = WorkflowState()
        result = rule.evaluate(state)
        
        assert result.status == VerificationStatus.VIOLATED
        assert result.severity == VerificationSeverity.CRITICAL
        assert "error" in result.message.lower()
        print("✓ Condition exception handling")


class TestFormalWorkflowVerifier:
    """Test FormalWorkflowVerifier functionality"""
    
    def test_creation(self):
        """Test verifier creation"""
        verifier = FormalWorkflowVerifier()
        assert verifier.rules == {}
        assert verifier.results == []
        print("✓ Verifier creation")
    
    def test_add_pre_condition(self):
        """Test adding pre-condition"""
        verifier = FormalWorkflowVerifier()
        
        def check(state):
            return True, None
        
        rule_id = verifier.add_pre_condition(
            name="pre_check",
            condition=check,
            applies_to=["node1"]
        )
        
        assert rule_id in verifier.rules
        assert verifier.rules[rule_id].rule_type == VerificationType.PRE_CONDITION
        print("✓ Add pre-condition")
    
    def test_add_invariant(self):
        """Test adding invariant"""
        verifier = FormalWorkflowVerifier()
        
        def check(state):
            return True, None
        
        rule_id = verifier.add_invariant(
            name="inv_check",
            condition=check
        )
        
        assert rule_id in verifier.invariants
        assert verifier.rules[rule_id].rule_type == VerificationType.INVARIANT
        print("✓ Add invariant")
    
    def test_verify_pre_conditions(self):
        """Test pre-condition verification"""
        verifier = FormalWorkflowVerifier()
        
        verifier.add_pre_condition(
            name="check_value",
            condition=lambda s: (s.get("value") is not None, "Value is None")
        )
        
        # State without value - should fail
        state1 = WorkflowState()
        results1 = verifier.verify_pre_conditions(state1, "node1")
        assert any(r.status == VerificationStatus.VIOLATED for r in results1)
        
        # State with value - should pass
        state2 = WorkflowState()
        state2.set("value", 10)
        results2 = verifier.verify_pre_conditions(state2, "node1")
        assert all(r.status in [VerificationStatus.PASSING, VerificationStatus.UNCHECKED] 
                   for r in results2)
        print("✓ Pre-condition verification")
    
    def test_has_blocking_failures(self):
        """Test blocking failure detection"""
        from core.formal_workflow_verification import VerificationResult
        verifier = FormalWorkflowVerifier()
        
        # Non-blocking (warning)
        result1 = VerificationResult(
            rule_id="r1",
            rule_name="warn",
            status=VerificationStatus.VIOLATED,
            verification_type=VerificationType.PRE_CONDITION,
            severity=VerificationSeverity.WARNING,
            message="Warning"
        )
        
        # Blocking (error)
        result2 = VerificationResult(
            rule_id="r2",
            rule_name="error",
            status=VerificationStatus.VIOLATED,
            verification_type=VerificationType.PRE_CONDITION,
            severity=VerificationSeverity.ERROR,
            message="Error"
        )
        
        assert not verifier.has_blocking_failures([result1])
        assert verifier.has_blocking_failures([result2])
        assert verifier.has_blocking_failures([result1, result2])
        print("✓ Blocking failure detection")
    
    def test_get_verification_report(self):
        """Test report generation"""
        from core.formal_workflow_verification import VerificationResult
        verifier = FormalWorkflowVerifier()
        
        # Add some results
        verifier.results = [
            VerificationResult(
                rule_id="r1",
                rule_name="pass",
                status=VerificationStatus.PASSING,
                verification_type=VerificationType.PRE_CONDITION,
                severity=VerificationSeverity.ERROR,
                message="OK"
            ),
            VerificationResult(
                rule_id="r2",
                rule_name="fail",
                status=VerificationStatus.VIOLATED,
                verification_type=VerificationType.POST_CONDITION,
                severity=VerificationSeverity.CRITICAL,
                message="Failed"
            )
        ]
        
        report = verifier.get_verification_report()
        
        assert report["summary"]["total_checks"] == 2
        assert report["summary"]["passing"] == 1
        assert report["summary"]["violated"] == 1
        assert len(report["critical_failures"]) == 1
        print("✓ Verification report")
    
    def test_state_history(self):
        """Test state history recording"""
        verifier = FormalWorkflowVerifier()
        
        state1 = WorkflowState()
        state1.set("x", 1)
        
        state2 = WorkflowState()
        state2.set("x", 2)
        
        verifier.record_state(state1)
        verifier.record_state(state2)
        
        assert len(verifier.state_history) == 2
        assert verifier.state_history[0].get("x") == 1
        assert verifier.state_history[1].get("x") == 2
        print("✓ State history recording")


class TestVerifiedWorkflowNode:
    """Test VerifiedWorkflowNode functionality"""
    
    def test_successful_execution(self):
        """Test node execution with verification"""
        verifier = FormalWorkflowVerifier()
        
        def executor(state):
            output = {"result": state.get("input", 0) * 2}
            new_state = state.copy()
            return output, new_state
        
        node = VerifiedWorkflowNode(
            node_id="double",
            executor=executor,
            verifier=verifier
        )
        
        state = WorkflowState()
        state.set("input", 5)
        
        output, results, should_continue = node.execute(state)
        
        assert output["result"] == 10
        assert should_continue is True
        assert node.execution_count == 1
        print("✓ Successful node execution")
    
    def test_execution_with_pre_condition(self):
        """Test node with pre-condition check"""
        verifier = FormalWorkflowVerifier()
        
        # Add pre-condition: input must exist
        verifier.add_pre_condition(
            name="input_exists",
            condition=lambda s: (s.get("input") is not None, "Input required")
        )
        
        def executor(state):
            return {"result": "success"}, state.copy()
        
        node = VerifiedWorkflowNode(
            node_id="process",
            executor=executor,
            verifier=verifier
        )
        
        # Without input - should fail pre-condition
        state1 = WorkflowState()
        output1, results1, should_continue1 = node.execute(state1)
        
        assert output1 is None
        assert should_continue1 is False
        assert any(r.rule_name == "input_exists" and r.status == VerificationStatus.VIOLATED 
                   for r in results1)
        
        # With input - should pass
        state2 = WorkflowState()
        state2.set("input", "data")
        output2, results2, should_continue2 = node.execute(state2)
        
        assert output2 is not None
        assert should_continue2 is True
        print("✓ Pre-condition enforcement")
    
    def test_execution_exception(self):
        """Test handling of execution exception"""
        verifier = FormalWorkflowVerifier()
        
        def bad_executor(state):
            raise ValueError("Execution failed")
        
        node = VerifiedWorkflowNode(
            node_id="bad",
            executor=bad_executor,
            verifier=verifier
        )
        
        state = WorkflowState()
        output, results, should_continue = node.execute(state)
        
        assert output is None
        assert should_continue is False
        assert any("Execution failed" in r.message for r in results)
        assert node.failure_count == 1
        print("✓ Execution exception handling")


class TestConvenienceFunctions:
    """Test convenience verification functions"""
    
    def test_type_check(self):
        """Test create_type_check"""
        check = create_type_check("x", int)
        
        state1 = WorkflowState()
        state1.set("x", 42)
        passed1, _ = check(state1)
        assert passed1 is True
        
        state2 = WorkflowState()
        state2.set("x", "not an int")
        passed2, msg = check(state2)
        assert passed2 is False
        assert "int" in msg
        
        state3 = WorkflowState()
        passed3, msg = check(state3)
        assert passed3 is False
        print("✓ Type check")
    
    def test_range_check(self):
        """Test create_range_check"""
        check = create_range_check("value", min_val=0, max_val=100)
        
        state1 = WorkflowState()
        state1.set("value", 50)
        assert check(state1)[0] is True
        
        state2 = WorkflowState()
        state2.set("value", -5)
        passed2, msg = check(state2)
        assert passed2 is False
        assert "below minimum" in msg
        
        state3 = WorkflowState()
        state3.set("value", 150)
        passed3, msg = check(state3)
        assert passed3 is False
        assert "above maximum" in msg
        print("✓ Range check")
    
    def test_not_empty_check(self):
        """Test create_not_empty_check"""
        check = create_not_empty_check("data")
        
        state1 = WorkflowState()
        state1.set("data", [1, 2, 3])
        assert check(state1)[0] is True
        
        state2 = WorkflowState()
        state2.set("data", [])
        passed2, msg = check(state2)
        assert passed2 is False
        assert "empty" in msg
        
        state3 = WorkflowState()
        passed3, msg = check(state3)
        assert passed3 is False
        print("✓ Not empty check")
    
    def test_dependency_check(self):
        """Test create_dependency_check"""
        check = create_dependency_check("input", "output")
        
        state1 = WorkflowState()
        state1.set("input", "data")
        state1.set("output", "processed")
        assert check(state1)[0] is True
        
        state2 = WorkflowState()
        state2.set("input", "data")
        state2.set("output", "")
        passed2, msg = check(state2)
        assert passed2 is False
        
        state3 = WorkflowState()
        passed3, msg = check(state3)
        assert passed3 is False
        print("✓ Dependency check")


def run_all_tests():
    """Run all test suites"""
    print("\n" + "="*60)
    print("Formal Workflow Verification Tests")
    print("="*60 + "\n")
    
    test_classes = [
        TestWorkflowState,
        TestVerificationRule,
        TestFormalWorkflowVerifier,
        TestVerifiedWorkflowNode,
        TestConvenienceFunctions
    ]
    
    total_tests = 0
    passed_tests = 0
    
    for test_class in test_classes:
        print(f"\n{test_class.__name__}")
        print("-" * 40)
        
        methods = [m for m in dir(test_class) if m.startswith("test_")]
        
        for method_name in methods:
            total_tests += 1
            try:
                instance = test_class()
                getattr(instance, method_name)()
                passed_tests += 1
            except AssertionError as e:
                print(f"✗ {method_name}: Assertion failed - {e}")
            except Exception as e:
                print(f"✗ {method_name}: Error - {e}")
    
    print("\n" + "="*60)
    print(f"Results: {passed_tests}/{total_tests} tests passed")
    print("="*60)
    
    return passed_tests == total_tests


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)