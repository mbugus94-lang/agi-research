"""
Test suite for Constitutional Governance Framework.

Tests cover:
- Rule management (add, remove, immutable protection)
- Operation evaluation and violation detection
- Approval workflows
- Circuit breaker functionality
- Constitution persistence (export/import)
- GovernedAgent wrapper
"""

import unittest
import time
import os
import tempfile
from core.constitutional_governance import (
    ConstitutionalGovernance, ConstitutionalRule, GovernedAgent,
    RulePriority, RuleCategory, ApprovalStatus, CircuitBreakerState,
    create_default_governance, DEFAULT_CONSTITUTION
)


class TestConstitutionalRule(unittest.TestCase):
    """Test ConstitutionalRule dataclass."""
    
    def test_rule_creation(self):
        """Test basic rule creation."""
        rule = ConstitutionalRule(
            id="test-001",
            name="Test Rule",
            description="A test rule",
            category=RuleCategory.SAFETY,
            priority=RulePriority.HIGH,
            condition="test.condition",
            action="block"
        )
        
        self.assertEqual(rule.id, "test-001")
        self.assertEqual(rule.name, "Test Rule")
        self.assertEqual(rule.priority, RulePriority.HIGH)
        self.assertFalse(rule.immutable)
    
    def test_rule_to_dict(self):
        """Test rule serialization."""
        rule = ConstitutionalRule(
            id="test-002",
            name="Dict Test",
            description="Testing dict conversion",
            category=RuleCategory.ETHICS,
            priority=RulePriority.MEDIUM,
            condition="test.condition",
            action="warn",
            immutable=True
        )
        
        data = rule.to_dict()
        self.assertEqual(data["id"], "test-002")
        self.assertEqual(data["priority"], "MEDIUM")
        self.assertEqual(data["category"], "ethics")
        self.assertTrue(data["immutable"])
    
    def test_rule_from_dict(self):
        """Test rule deserialization."""
        data = {
            "id": "test-003",
            "name": "From Dict",
            "description": "Created from dict",
            "category": "security",
            "priority": "CRITICAL",
            "condition": "security.condition",
            "action": "block",
            "immutable": False,
            "created_at": time.time(),
            "violation_count": 5
        }
        
        rule = ConstitutionalRule.from_dict(data)
        self.assertEqual(rule.id, "test-003")
        self.assertEqual(rule.priority, RulePriority.CRITICAL)
        self.assertEqual(rule.violation_count, 5)


class TestConstitutionalGovernance(unittest.TestCase):
    """Test ConstitutionalGovernance class."""
    
    def setUp(self):
        """Set up test governance."""
        self.gov = ConstitutionalGovernance("test-agent")
    
    def test_default_constitution_loaded(self):
        """Test that default constitution is loaded."""
        self.assertIn("core-001", self.gov.rules)
        self.assertIn("core-002", self.gov.rules)
        self.assertIn("core-003", self.gov.rules)
        self.assertIn("core-004", self.gov.rules)
        
        # Check immutability
        self.assertTrue(self.gov.rules["core-001"].immutable)
        self.assertTrue(self.gov.rules["core-002"].immutable)
    
    def test_add_mutable_rule(self):
        """Test adding a mutable rule."""
        rule = ConstitutionalRule(
            id="new-rule-001",
            name="New Rule",
            description="A new rule",
            category=RuleCategory.OPERATIONAL,
            priority=RulePriority.LOW,
            condition="test.condition",
            action="log",
            immutable=False
        )
        
        result = self.gov.add_rule(rule, "Adding for testing")
        self.assertTrue(result)
        self.assertIn("new-rule-001", self.gov.rules)
        self.assertIsNotNone(self.gov.rules["new-rule-001"].amended_at)
    
    def test_cannot_modify_immutable_rule(self):
        """Test that immutable rules cannot be modified."""
        new_rule = ConstitutionalRule(
            id="core-001",  # Existing immutable rule
            name="Modified",
            description="Attempted modification",
            category=RuleCategory.SAFETY,
            priority=RulePriority.LOW,
            condition="test",
            action="log",
            immutable=False
        )
        
        result = self.gov.add_rule(new_rule)
        self.assertFalse(result)
        
        # Original rule should remain
        self.assertEqual(self.gov.rules["core-001"].name, "No Harm to Humans")
    
    def test_remove_mutable_rule(self):
        """Test removing a mutable rule."""
        # First add a mutable rule
        rule = ConstitutionalRule(
            id="removable-001",
            name="Removable",
            description="Can be removed",
            category=RuleCategory.OPERATIONAL,
            priority=RulePriority.LOW,
            condition="test",
            action="log"
        )
        self.gov.add_rule(rule)
        
        # Remove it
        result = self.gov.remove_rule("removable-001")
        self.assertTrue(result)
        self.assertNotIn("removable-001", self.gov.rules)
    
    def test_cannot_remove_immutable_rule(self):
        """Test that immutable rules cannot be removed."""
        result = self.gov.remove_rule("core-001")
        self.assertFalse(result)
        self.assertIn("core-001", self.gov.rules)
    
    def test_evaluate_safe_operation(self):
        """Test evaluating an operation that doesn't violate rules."""
        result = self.gov.evaluate_operation(
            "read_file",
            {"path": "/tmp/test.txt"}
        )
        
        self.assertTrue(result["allowed"])
        self.assertEqual(len(result["violations"]), 0)
    
    def test_evaluate_system_modification(self):
        """Test evaluating system modification operation."""
        result = self.gov.evaluate_operation(
            "delete_file",
            {"path": "/etc/passwd", "has_approval": False}
        )
        
        # Should be blocked without approval
        self.assertFalse(result["allowed"])
        self.assertGreater(len(result["violations"]), 0)
        
        # Check violation details
        violation = result["violations"][0]
        self.assertEqual(violation["severity"], "CRITICAL")
    
    def test_evaluate_with_approval(self):
        """Test operation with explicit approval."""
        result = self.gov.evaluate_operation(
            "modify_config",
            {"path": "/etc/config", "has_approval": True}
        )
        
        # Should be allowed with approval
        self.assertTrue(result["allowed"])
    
    def test_approval_request_creation(self):
        """Test that approval requests are created when needed."""
        result = self.gov.evaluate_operation(
            "high_impact_operation",
            {"impact_score": 0.9, "has_explanation": False}
        )
        
        # Should require approval
        self.assertGreater(len(result["required_approvals"]), 0)
        self.assertIn("required_approvals", result)
    
    def test_approve_operation(self):
        """Test approving an operation."""
        # Create approval request
        result = self.gov.evaluate_operation(
            "expensive_operation",
            {"estimated_cost": 200}
        )
        
        approval_id = result["required_approvals"][0]
        
        # Approve it
        success = self.gov.approve_operation(approval_id, "human-operator")
        self.assertTrue(success)
        
        # Check status
        request = self.gov.approval_requests[approval_id]
        self.assertEqual(request.status, ApprovalStatus.APPROVED)
        self.assertEqual(request.approved_by, "human-operator")
    
    def test_deny_operation(self):
        """Test denying an operation."""
        # Create approval request
        result = self.gov.evaluate_operation(
            "biased_output",
            {"bias_score": 0.8}
        )
        
        approval_id = result["required_approvals"][0]
        
        # Deny it
        success = self.gov.deny_operation(approval_id, "Potential bias detected")
        self.assertTrue(success)
        
        request = self.gov.approval_requests[approval_id]
        self.assertEqual(request.status, ApprovalStatus.DENIED)
        self.assertEqual(request.denial_reason, "Potential bias detected")
    
    def test_circuit_breaker_registration(self):
        """Test circuit breaker registration."""
        self.gov.register_circuit_breaker("api_calls", 3, 30.0)
        
        self.assertIn("api_calls", self.gov.circuit_breakers)
        breaker = self.gov.circuit_breakers["api_calls"]
        self.assertEqual(breaker.name, "api_calls")
        self.assertEqual(breaker.failure_threshold, 3)
    
    def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in closed state."""
        self.gov.register_circuit_breaker("test_op", 3, 30.0)
        
        # Should allow execution initially
        self.assertTrue(self.gov.check_circuit_breaker("test_op"))
    
    def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures."""
        self.gov.register_circuit_breaker("fragile_op", 2, 30.0)
        
        # Record failures
        self.gov.record_circuit_result("fragile_op", False)
        self.assertTrue(self.gov.check_circuit_breaker("fragile_op"))  # Still closed
        
        self.gov.record_circuit_result("fragile_op", False)
        # Should be open now
        self.assertFalse(self.gov.check_circuit_breaker("fragile_op"))
    
    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovery after timeout."""
        self.gov.register_circuit_breaker("recover_op", 1, 0.1)  # 100ms timeout
        
        # Trip it
        self.gov.record_circuit_result("recover_op", False)
        self.assertFalse(self.gov.check_circuit_breaker("recover_op"))
        
        # Wait for timeout
        time.sleep(0.15)
        
        # Should be half-open now
        self.assertTrue(self.gov.check_circuit_breaker("recover_op"))
    
    def test_violation_tracking(self):
        """Test that violations are tracked."""
        initial_count = len(self.gov.violations)
        
        # Trigger violation
        self.gov.evaluate_operation(
            "delete_system_file",
            {"path": "/system/file"}
        )
        
        self.assertGreater(len(self.gov.violations), initial_count)
    
    def test_get_violations_filtering(self):
        """Test violation filtering."""
        # Trigger some violations
        self.gov.evaluate_operation("delete_file", {})
        
        # Get all violations
        all_violations = self.gov.get_violations()
        self.assertGreater(len(all_violations), 0)
        
        # Filter by severity
        critical = self.gov.get_violations(severity=RulePriority.CRITICAL)
        self.assertGreater(len(critical), 0)
    
    def test_constitution_export_import(self):
        """Test constitution export and import."""
        # Export
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name
        
        try:
            self.gov.export_constitution(filepath)
            self.assertTrue(os.path.exists(filepath))
            
            # Create new governance and import
            new_gov = ConstitutionalGovernance("import-test")
            result = new_gov.import_constitution(filepath)
            self.assertTrue(result)
            
            # Verify rules imported
            self.assertIn("core-001", new_gov.rules)
            self.assertTrue(new_gov.rules["core-001"].immutable)
        finally:
            os.unlink(filepath)
    
    def test_get_constitution(self):
        """Test getting constitution summary."""
        constitution = self.gov.get_constitution()
        
        self.assertEqual(constitution["agent_id"], "test-agent")
        self.assertGreater(constitution["total_rules"], 0)
        self.assertGreater(constitution["immutable_count"], 0)
        self.assertIn("rules", constitution)


class TestGovernedAgent(unittest.TestCase):
    """Test GovernedAgent wrapper."""
    
    def setUp(self):
        """Set up governed agent."""
        self.agent = GovernedAgent("governed-test")
    
    def test_safe_operation_execution(self):
        """Test executing a safe operation."""
        result = self.agent.execute(
            "read_data",
            {"source": "database", "query": "SELECT * FROM users"}
        )
        
        self.assertTrue(result["success"])
        self.assertFalse(result["approval_required"])
    
    def test_blocked_operation(self):
        """Test blocked operation."""
        result = self.agent.execute(
            "delete_system_file",
            {"path": "/etc/passwd"}
        )
        
        self.assertFalse(result["success"])
        self.assertIn("blocked", result["error"].lower())
        self.assertGreater(len(result["violations"]), 0)
    
    def test_approval_required(self):
        """Test operation requiring approval."""
        result = self.agent.execute(
            "high_cost_operation",
            {"estimated_cost": 500}
        )
        
        self.assertFalse(result["success"])
        self.assertTrue(result["approval_required"])
        self.assertIn("approval_ids", result)
    
    def test_circuit_breaker_blocks(self):
        """Test circuit breaker blocking operation."""
        # Register and trip circuit breaker
        self.agent.governance.register_circuit_breaker("unstable_op", 1, 60.0)
        self.agent.governance.record_circuit_result("unstable_op", False)
        
        # Try to execute
        result = self.agent.execute(
            "some_operation",
            {"circuit_breaker": "unstable_op"}
        )
        
        self.assertFalse(result["success"])
        self.assertIn("circuit breaker", result["error"].lower())


class TestFactoryFunctions(unittest.TestCase):
    """Test factory functions."""
    
    def test_create_default_governance(self):
        """Test factory function."""
        gov = create_default_governance("factory-test")
        
        self.assertEqual(len(gov.rules), 7)  # 4 core + 3 default
        self.assertIn("core-001", gov.rules)
        self.assertTrue(gov.rules["core-001"].immutable)
    
    def test_default_constitution_structure(self):
        """Test default constitution constant."""
        self.assertIn("core_principles", DEFAULT_CONSTITUTION)
        self.assertEqual(len(DEFAULT_CONSTITUTION["core_principles"]), 4)


class TestIntegrationScenarios(unittest.TestCase):
    """Integration test scenarios."""
    
    def test_full_workflow_safe_operation(self):
        """Test complete workflow for safe operation."""
        gov = ConstitutionalGovernance("integration-test")
        agent = GovernedAgent("integration-test", gov)
        
        # Execute safe operation
        result = agent.execute(
            "analyze_data",
            {"dataset": "sales_q1", "operation": "summary_stats"}
        )
        
        self.assertTrue(result["success"])
        self.assertEqual(len(result["violations"]), 0)
    
    def test_full_workflow_dangerous_operation(self):
        """Test complete workflow for dangerous operation."""
        gov = ConstitutionalGovernance("danger-test")
        agent = GovernedAgent("danger-test", gov)
        
        # Try dangerous operation
        result = agent.execute(
            "rm -rf /",
            {"targets_human": True}
        )
        
        self.assertFalse(result["success"])
        self.assertGreater(len(result["violations"]), 0)
        
        # Verify violation was logged
        violations = gov.get_violations()
        self.assertGreater(len(violations), 0)
    
    def test_full_workflow_approval_flow(self):
        """Test complete approval workflow."""
        gov = ConstitutionalGovernance("approval-test")
        agent = GovernedAgent("approval-test", gov)
        
        # Operation requiring approval
        result = agent.execute(
            "deploy_production",
            {"impact_score": 0.95, "has_explanation": False}
        )
        
        self.assertFalse(result["success"])
        self.assertTrue(result["approval_required"])
        
        # Get approval ID
        approval_id = result["approval_ids"][0]
        
        # Approve
        gov.approve_operation(approval_id, "senior-dev")
        
        # Check approval status
        request = gov.approval_requests[approval_id]
        self.assertEqual(request.status, ApprovalStatus.APPROVED)
    
    def test_multiple_rules_triggered(self):
        """Test operation triggering multiple rules."""
        gov = ConstitutionalGovernance("multi-rule-test")
        
        # Operation that triggers multiple rules
        result = gov.evaluate_operation(
            "unauthorized_pii_deletion",
            {
                "contains_pii": True,
                "has_consent": False,
                "targets_human": True
            }
        )
        
        self.assertFalse(result["allowed"])
        # Should trigger at least privacy and harm rules
        self.assertGreaterEqual(len(result["violations"]), 1)
    
    def test_amendment_tracking(self):
        """Test that amendments are tracked."""
        gov = ConstitutionalGovernance("amend-test")
        
        # Add a new rule
        new_rule = ConstitutionalRule(
            id="amended-rule",
            name="Original Name",
            description="Original description",
            category=RuleCategory.OPERATIONAL,
            priority=RulePriority.LOW,
            condition="test",
            action="log"
        )
        
        gov.add_rule(new_rule, "Initial addition")
        
        # Amend it
        amended = ConstitutionalRule(
            id="amended-rule",
            name="Amended Name",
            description="Amended description",
            category=RuleCategory.OPERATIONAL,
            priority=RulePriority.MEDIUM,
            condition="test.amended",
            action="warn"
        )
        
        gov.add_rule(amended, "Priority increased due to incidents")
        
        # Verify amendment was tracked
        rule = gov.rules["amended-rule"]
        self.assertEqual(rule.name, "Amended Name")
        self.assertEqual(rule.priority, RulePriority.MEDIUM)
        self.assertIsNotNone(rule.amended_at)
        self.assertEqual(rule.amendment_reason, "Priority increased due to incidents")


def run_tests():
    """Run all tests and return results."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestConstitutionalRule))
    suite.addTests(loader.loadTestsFromTestCase(TestConstitutionalGovernance))
    suite.addTests(loader.loadTestsFromTestCase(TestGovernedAgent))
    suite.addTests(loader.loadTestsFromTestCase(TestFactoryFunctions))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationScenarios))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful(), result.testsRun


if __name__ == "__main__":
    success, count = run_tests()
    print(f"\n{'='*60}")
    print(f"Tests: {count}")
    print(f"Status: {'✅ ALL PASSED' if success else '❌ SOME FAILED'}")
    print(f"{'='*60}")
    exit(0 if success else 1)
