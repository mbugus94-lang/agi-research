"""
Tests for Safety Circuit Breaker

Validates:
- Risk assessment accuracy
- Circuit state transitions
- Policy enforcement
- Self-modification guard
- Audit logging
"""

import unittest
import time
from datetime import datetime
from core.safety_circuit_breaker import (
    SafetyCircuitBreaker, SelfModificationGuard, create_safety_circuit_breaker,
    RiskLevel, CircuitState, ActionCategory, OperationRecord
)


class TestRiskAssessment(unittest.TestCase):
    """Test risk assessment logic."""
    
    def setUp(self):
        self.cb = SafetyCircuitBreaker()
    
    def test_self_modification_always_critical(self):
        """Self-modification is always critical risk."""
        risk = self.cb.assess_risk(
            ActionCategory.MODIFY_SELF,
            "/home/workspace/test.py",
            "Update configuration"
        )
        self.assertEqual(risk, RiskLevel.CRITICAL)
    
    def test_production_deletion_critical(self):
        """Deleting production data is critical."""
        risk = self.cb.assess_risk(
            ActionCategory.DELETE,
            "/data/production.db",
            "Drop old records"
        )
        self.assertEqual(risk, RiskLevel.CRITICAL)
    
    def test_database_drop_critical(self):
        """Database DROP operations are critical."""
        risk = self.cb.assess_risk(
            ActionCategory.DATABASE,
            "users_table",
            "DROP TABLE users"
        )
        self.assertEqual(risk, RiskLevel.CRITICAL)
    
    def test_external_api_write_high(self):
        """External API write operations are high risk."""
        risk = self.cb.assess_risk(
            ActionCategory.EXTERNAL_API,
            "https://api.example.com/data",
            "POST update user data"
        )
        self.assertEqual(risk, RiskLevel.HIGH)
    
    def test_external_api_read_medium(self):
        """External API read operations are medium risk."""
        risk = self.cb.assess_risk(
            ActionCategory.EXTERNAL_API,
            "https://api.example.com/data",
            "GET user profile"
        )
        self.assertEqual(risk, RiskLevel.MEDIUM)
    
    def test_read_operations_low(self):
        """Read operations are low risk."""
        risk = self.cb.assess_risk(
            ActionCategory.READ,
            "/home/workspace/data.txt",
            "Read file contents"
        )
        self.assertEqual(risk, RiskLevel.LOW)


class TestPolicyEnforcement(unittest.TestCase):
    """Test policy enforcement and blocking."""
    
    def setUp(self):
        self.cb = SafetyCircuitBreaker()
    
    def test_blocked_path_detected(self):
        """Blocked paths are detected and rejected."""
        record = OperationRecord(
            action_category=ActionCategory.FILE_SYSTEM,
            risk_level=RiskLevel.MEDIUM,
            description="Read password file",
            target="/etc/passwd"
        )
        
        result = self.cb.check_operation(record)
        self.assertFalse(result)
        self.assertEqual(record.result_status, "blocked")
    
    def test_blocked_command_detected(self):
        """Blocked commands are detected."""
        record = OperationRecord(
            action_category=ActionCategory.EXECUTE,
            risk_level=RiskLevel.MEDIUM,
            description="Format disk",
            target="rm -rf /"
        )
        
        result = self.cb.check_operation(record)
        self.assertFalse(result)
    
    def test_allowed_path_approved(self):
        """Operations in allowed paths are approved."""
        record = OperationRecord(
            action_category=ActionCategory.FILE_SYSTEM,
            risk_level=RiskLevel.LOW,
            description="Read workspace file",
            target="/home/workspace/data.txt"
        )
        
        result = self.cb.check_operation(record)
        self.assertTrue(result)
    
    def test_critical_requires_human_approval(self):
        """Critical operations require human approval."""
        record = OperationRecord(
            action_category=ActionCategory.MODIFY_SELF,
            risk_level=RiskLevel.CRITICAL,
            description="Update core logic",
            target="core/agent.py"
        )
        
        result = self.cb.check_operation(record)
        self.assertFalse(result)  # Not auto-approved
        self.assertEqual(record.result_status, "pending_approval")
        self.assertIn(record.operation_id, self.cb.pending_approvals)


class TestCircuitState(unittest.TestCase):
    """Test circuit breaker state machine."""
    
    def setUp(self):
        self.cb = SafetyCircuitBreaker(failure_threshold=3)
    
    def test_initial_state_closed(self):
        """Circuit starts in closed state."""
        self.assertEqual(self.cb.state, CircuitState.CLOSED)
    
    def test_circuit_opens_after_failures(self):
        """Circuit opens after threshold failures."""
        # Generate failures
        for _ in range(3):
            record = OperationRecord(
                action_category=ActionCategory.FILE_SYSTEM,
                risk_level=RiskLevel.MEDIUM,
                description="Blocked operation",
                target="/etc/passwd"
            )
            self.cb.check_operation(record)
        
        self.assertEqual(self.cb.state, CircuitState.OPEN)
    
    def test_circuit_blocks_when_open(self):
        """Circuit blocks operations when open."""
        # Force circuit open
        self.cb.state = CircuitState.OPEN
        self.cb.last_failure_time = datetime.now().timestamp()
        
        record = OperationRecord(
            action_category=ActionCategory.READ,
            risk_level=RiskLevel.LOW,
            description="Safe read",
            target="/home/workspace/safe.txt"
        )
        
        result = self.cb.check_operation(record)
        self.assertFalse(result)
        self.assertEqual(record.result_details, "Circuit breaker is OPEN")
    
    def test_circuit_resets_after_timeout(self):
        """Circuit attempts reset after timeout."""
        self.cb = SafetyCircuitBreaker(
            failure_threshold=3,
            recovery_timeout_seconds=0  # Immediate
        )
        
        # Force circuit open with old failure time
        self.cb.state = CircuitState.OPEN
        self.cb.last_failure_time = datetime.now().timestamp() - 1
        
        # Should attempt reset
        record = OperationRecord(
            action_category=ActionCategory.READ,
            risk_level=RiskLevel.LOW,
            description="Safe read",
            target="/home/workspace/safe.txt"
        )
        
        self.cb.check_operation(record)
        self.assertEqual(self.cb.state, CircuitState.CLOSED)
    
    def test_manual_reset(self):
        """Manual reset works."""
        self.cb.state = CircuitState.OPEN
        self.cb.reset_circuit()
        self.assertEqual(self.cb.state, CircuitState.CLOSED)


class TestRateLimiting(unittest.TestCase):
    """Test rate limiting functionality."""
    
    def setUp(self):
        self.cb = SafetyCircuitBreaker()
    
    def test_rate_limit_enforced(self):
        """Rate limits are enforced."""
        # Set very low rate limit
        self.cb.policies[ActionCategory.READ].rate_limit_per_minute = 2
        
        # First two should pass
        for i in range(2):
            record = OperationRecord(
                action_category=ActionCategory.READ,
                risk_level=RiskLevel.LOW,
                description=f"Read {i}",
                target="/home/workspace/file.txt"
            )
            result = self.cb.check_operation(record)
            self.assertTrue(result)
        
        # Third should be blocked
        record = OperationRecord(
            action_category=ActionCategory.READ,
            risk_level=RiskLevel.LOW,
            description="Read 3",
            target="/home/workspace/file.txt"
        )
        result = self.cb.check_operation(record)
        self.assertFalse(result)
        self.assertEqual(record.result_details, "Rate limit exceeded")


class TestSelfModificationGuard(unittest.TestCase):
    """Test self-modification guard."""
    
    def setUp(self):
        self.cb = SafetyCircuitBreaker()
        self.guard = SelfModificationGuard(self.cb)
    
    def test_proposal_creates_pending(self):
        """Proposing creates pending modification."""
        op_id = self.guard.propose_modification(
            description="Add new feature",
            target_file="core/agent.py",
            change_summary="Add logging",
            rollback_plan="Revert commit",
            test_plan="Run unit tests"
        )
        
        self.assertIsNotNone(op_id)
        self.assertIn(op_id, self.cb.pending_approvals)
        
        pending = self.guard.get_pending_modifications()
        self.assertEqual(len(pending), 1)
    
    def test_approve_allows_execution(self):
        """Approving allows the modification."""
        op_id = self.guard.propose_modification(
            description="Add new feature",
            target_file="core/agent.py",
            change_summary="Add logging",
            rollback_plan="Revert commit",
            test_plan="Run unit tests"
        )
        
        result = self.guard.approve_modification(op_id, reviewer="test_user")
        self.assertTrue(result)
        
        # Should be removed from pending
        self.assertNotIn(op_id, self.cb.pending_approvals)
        
        pending = self.guard.get_pending_modifications()
        self.assertEqual(len(pending), 0)
    
    def test_reject_blocks_execution(self):
        """Rejecting blocks the modification."""
        op_id = self.guard.propose_modification(
            description="Add new feature",
            target_file="core/agent.py",
            change_summary="Add logging",
            rollback_plan="Revert commit",
            test_plan="Run unit tests"
        )
        
        result = self.guard.reject_modification(op_id, reason="Too risky")
        self.assertTrue(result)
        
        # Should be removed from pending
        self.assertNotIn(op_id, self.cb.pending_approvals)


class TestAuditLogging(unittest.TestCase):
    """Test audit logging functionality."""
    
    def setUp(self):
        self.cb = SafetyCircuitBreaker()
    
    def test_operations_logged(self):
        """All operations are logged."""
        record = OperationRecord(
            action_category=ActionCategory.READ,
            risk_level=RiskLevel.LOW,
            description="Test read",
            target="/home/workspace/file.txt"
        )
        
        self.cb.check_operation(record)
        
        log = self.cb.get_audit_log()
        self.assertEqual(len(log), 1)
        self.assertEqual(log[0].description, "Test read")
    
    def test_log_filtering_by_category(self):
        """Log can be filtered by category."""
        # Add operations of different categories
        for category in [ActionCategory.READ, ActionCategory.WRITE]:
            record = OperationRecord(
                action_category=category,
                risk_level=RiskLevel.LOW,
                description=f"Test {category.value}",
                target="/home/workspace/file.txt"
            )
            self.cb.check_operation(record)
        
        filtered = self.cb.get_audit_log(category=ActionCategory.READ)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].action_category, ActionCategory.READ)
    
    def test_log_filtering_by_risk(self):
        """Log can be filtered by risk level."""
        # Add operations of different risk levels
        for risk in [RiskLevel.LOW, RiskLevel.HIGH]:
            record = OperationRecord(
                action_category=ActionCategory.FILE_SYSTEM,
                risk_level=risk,
                description=f"Test {risk.value}",
                target="/home/workspace/file.txt"
            )
            self.cb.check_operation(record)
        
        filtered = self.cb.get_audit_log(risk_level=RiskLevel.HIGH)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].risk_level, RiskLevel.HIGH)


class TestStatistics(unittest.TestCase):
    """Test statistics tracking."""
    
    def setUp(self):
        self.cb = SafetyCircuitBreaker()
    
    def test_stats_tracked(self):
        """Statistics are tracked correctly."""
        # Approved operation
        record1 = OperationRecord(
            action_category=ActionCategory.READ,
            risk_level=RiskLevel.LOW,
            description="Approved",
            target="/home/workspace/file.txt"
        )
        self.cb.check_operation(record1)
        
        # Blocked operation (blocked path)
        record2 = OperationRecord(
            action_category=ActionCategory.FILE_SYSTEM,
            risk_level=RiskLevel.MEDIUM,
            description="Blocked",
            target="/etc/passwd"
        )
        self.cb.check_operation(record2)
        
        stats = self.cb.get_stats()
        self.assertEqual(stats["total_requests"], 2)
        self.assertEqual(stats["approved_requests"], 1)
        self.assertEqual(stats["policy_violations"], 1)  # Blocked paths are policy violations
        # The blocked operation doesn't count toward blocked_requests if it's a policy violation
        # It counts toward failed_requests because _record_failure is called


class TestFactory(unittest.TestCase):
    """Test factory function."""
    
    def test_create_production_defaults(self):
        """Factory creates with production-safe defaults."""
        cb = create_safety_circuit_breaker()
        
        self.assertEqual(cb.failure_threshold, 3)
        self.assertEqual(cb.recovery_timeout_seconds, 300)
        self.assertTrue(cb.enable_self_modification_review)


class TestIntegration(unittest.TestCase):
    """Integration tests."""
    
    def test_full_workflow(self):
        """Test complete safety workflow."""
        cb = create_safety_circuit_breaker()
        guard = SelfModificationGuard(cb)
        
        # 1. Normal operation - should pass
        record = OperationRecord(
            action_category=ActionCategory.READ,
            risk_level=RiskLevel.LOW,
            description="Read data",
            target="/home/workspace/data.txt"
        )
        self.assertTrue(cb.check_operation(record))
        
        # 2. Self-modification proposal - requires approval
        op_id = guard.propose_modification(
            description="Improve error handling",
            target_file="core/agent.py",
            change_summary="Add try-catch blocks",
            rollback_plan="git revert",
            test_plan="run tests"
        )
        self.assertIsNotNone(op_id)
        
        # 3. Check pending
        self.assertEqual(len(guard.get_pending_modifications()), 1)
        
        # 4. Approve
        self.assertTrue(guard.approve_modification(op_id, "admin"))
        
        # 5. Check stats
        stats = cb.get_stats()
        self.assertEqual(stats["total_requests"], 2)
        self.assertEqual(stats["high_risk_operations"], 1)


if __name__ == "__main__":
    unittest.main()
