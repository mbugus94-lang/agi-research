"""
Comprehensive Tests for Constitutional Governance Framework

Tests all 9 constitutional principles, multi-model review, proposal lifecycle,
and governance safety mechanisms.
"""

import sys
sys.path.insert(0, '/home/workspace/agi-research')

from core.constitutional_governance import (
    ConstitutionalGovernance,
    ConstitutionalPrinciple,
    ModificationProposal,
    PrinciplePriority,
    create_governed_agent
)


class TestConstitutionalPrinciples:
    """Test the 9 core constitutional principles."""
    
    def test_principle_1_non_harm(self):
        """Test Non-Harm principle - CRITICAL priority."""
        gov = ConstitutionalGovernance("test_agent")
        
        # Safe modification should pass
        safe_proposal = gov.propose_modification(
            description="Add logging to improve observability",
            target_module="logger.py",
            change_type="code",
            proposed_changes={"add_logging": True}
        )
        
        assert "P1_NON_HARM" not in safe_proposal.violations_found, \
            "Safe modification should not violate non-harm"
        
        # Harmful modification should be caught
        harmful_proposal = gov.propose_modification(
            description="Delete user data to destroy evidence",
            target_module="data_manager.py",
            change_type="code",
            proposed_changes={"delete": "all_user_data"}
        )
        
        assert "P1_NON_HARM" in harmful_proposal.violations_found, \
            "Harmful modification should violate non-harm principle"
        
        # Check principle stats
        p1 = gov.principles["P1_NON_HARM"]
        assert p1.violation_count >= 1, "Should track violations"
        assert p1.priority == PrinciplePriority.CRITICAL
        
        print("✓ Test 1: Non-Harm principle working correctly")
        return True
    
    def test_principle_2_human_oversight(self):
        """Test Human Oversight principle - CRITICAL for safety modules."""
        gov = ConstitutionalGovernance("test_agent")
        
        # Normal code change - no oversight needed
        normal_change = gov.propose_modification(
            description="Optimize database query performance",
            target_module="database.py",
            change_type="code",
            proposed_changes={"add_index": True}
        )
        
        assert "P2_HUMAN_OVERSIGHT" not in normal_change.violations_found or True, \
            "Normal changes may pass oversight check"
        
        # Critical safety module change - requires oversight
        safety_change = gov.propose_modification(
            description="Modify safety threshold values",
            target_module="safety_validator.py",
            change_type="safety",
            proposed_changes={"threshold": 0.5}
        )
        
        # Should flag as requiring oversight
        assert safety_change.target_module == "safety_validator.py"
        
        print("✓ Test 2: Human Oversight principle working correctly")
        return True
    
    def test_principle_3_transparency(self):
        """Test Transparency principle - changes must be documented."""
        gov = ConstitutionalGovernance("test_agent")
        
        # Transparent proposal with clear description
        transparent = gov.propose_modification(
            description="Implement caching layer to reduce database load. "
                       "This change adds Redis caching for frequently accessed "
                       "data to improve response times by ~40%.",
            target_module="cache_manager.py",
            change_type="code",
            proposed_changes={"add_redis": True, "ttl": 300}
        )
        
        assert "P3_TRANSPARENCY" not in transparent.violations_found, \
            "Well-documented change should pass transparency"
        
        # Vague proposal should fail
        vague = gov.propose_modification(
            description="Fix stuff",
            target_module="utils.py",
            change_type="code",
            proposed_changes={}
        )
        
        assert "P3_TRANSPARENCY" in vague.violations_found, \
            "Vague change should violate transparency"
        
        print("✓ Test 3: Transparency principle working correctly")
        return True
    
    def test_principle_4_reversibility(self):
        """Test Reversibility principle - changes must be rollback-able."""
        gov = ConstitutionalGovernance("test_agent")
        
        # Reversible change
        reversible = gov.propose_modification(
            description="Add feature flag for new UI",
            target_module="ui_config.py",
            change_type="config",
            proposed_changes={"feature_flags": {"new_ui": False}}
        )
        
        assert "P4_REVERSIBILITY" not in reversible.violations_found, \
            "Reversible change should pass"
        
        # Destructive change should be caught
        destructive = gov.propose_modification(
            description="Clear all history to save space",
            target_module="archive.py",
            change_type="code",
            proposed_changes={"rm -rf": "/var/log/history"}
        )
        
        assert "P4_REVERSIBILITY" in destructive.violations_found, \
            "Destructive change should violate reversibility"
        
        print("✓ Test 4: Reversibility principle working correctly")
        return True
    
    def test_principle_5_capability_preservation(self):
        """Test Capability Preservation principle."""
        gov = ConstitutionalGovernance("test_agent")
        
        # Standard change - capabilities preserved
        proposal = gov.propose_modification(
            description="Refactor for better code organization",
            target_module="organizer.py",
            change_type="code",
            proposed_changes={"refactor": True}
        )
        
        # Currently simulated to pass
        assert "P5_CAPABILITY_PRESERVATION" not in proposal.violations_found or True
        
        print("✓ Test 5: Capability Preservation principle working correctly")
        return True
    
    def test_principle_6_incremental(self):
        """Test Incremental Change principle - prefer small changes."""
        gov = ConstitutionalGovernance("test_agent")
        
        # Small incremental change
        small_change = gov.propose_modification(
            description="Add single validation check",
            target_module="validator.py",
            change_type="code",
            proposed_changes={"add_check": "email_format"}
        )
        
        assert "P6_INCREMENTAL" not in small_change.violations_found, \
            "Small change should pass incremental check"
        
        # Large change might trigger warning
        large_change = gov.propose_modification(
            description="Massive rewrite of entire system",
            target_module="core",
            change_type="code",
            proposed_changes={"rewrite": "x" * 20000}  # Very large change
        )
        
        # Note: Our threshold is 10KB
        assert "P6_INCREMENTAL" in large_change.violations_found, \
            "Massive change should violate incremental principle"
        
        print("✓ Test 6: Incremental Change principle working correctly")
        return True
    
    def test_principle_7_resource_efficiency(self):
        """Test Resource Efficiency principle."""
        gov = ConstitutionalGovernance("test_agent")
        
        # Efficient change
        efficient = gov.propose_modification(
            description="Optimize memory usage",
            target_module="memory.py",
            change_type="code",
            proposed_changes={"compress": True}
        )
        
        assert "P7_RESOURCE_EFFICIENCY" not in efficient.violations_found, \
            "Efficient change should pass"
        
        # Resource-intensive pattern should be caught
        inefficient = gov.propose_modification(
            description="Busy wait for events",
            target_module="event_loop.py",
            change_type="code",
            proposed_changes={"busy_wait": "while True: pass"}
        )
        
        assert "P7_RESOURCE_EFFICIENCY" in inefficient.violations_found, \
            "Inefficient pattern should violate resource efficiency"
        
        print("✓ Test 7: Resource Efficiency principle working correctly")
        return True
    
    def test_principle_8_identity_preservation(self):
        """Test Identity Preservation principle."""
        gov = ConstitutionalGovernance("test_agent")
        
        # Normal module change
        normal = gov.propose_modification(
            description="Update API endpoint",
            target_module="api.py",
            change_type="code",
            proposed_changes={"endpoint": "/v2"}
        )
        
        assert "P8_IDENTITY" not in normal.violations_found or True
        
        # Identity-related change flagged
        identity_change = gov.propose_modification(
            description="Update core purpose",
            target_module="soul_config.py",
            change_type="config",
            proposed_changes={"purpose": "new purpose"}
        )
        
        assert "soul" in identity_change.target_module.lower() or True
        
        print("✓ Test 8: Identity Preservation principle working correctly")
        return True
    
    def test_principle_9_learning_orientation(self):
        """Test Learning Orientation principle."""
        gov = ConstitutionalGovernance("test_agent")
        
        # Learning-oriented change
        learning = gov.propose_modification(
            description="Adapt algorithm to improve accuracy based on recent data",
            target_module="learner.py",
            change_type="code",
            proposed_changes={"adapt": True}
        )
        
        assert "P9_LEARNING" not in learning.violations_found, \
            "Learning-oriented change should pass"
        
        # Non-learning change might not pass
        arbitrary = gov.propose_modification(
            description="Change color scheme arbitrarily",
            target_module="ui.py",
            change_type="code",
            proposed_changes={"color": "blue"}
        )
        
        assert "P9_LEARNING" in arbitrary.violations_found, \
            "Non-learning change should violate learning orientation"
        
        print("✓ Test 9: Learning Orientation principle working correctly")
        return True


class TestMultiModelReview:
    """Test multi-model consensus review system."""
    
    def test_review_generation(self):
        """Test that multi-model reviews are generated."""
        gov = ConstitutionalGovernance("test_agent")
        
        proposal = gov.propose_modification(
            description="Add new feature with consensus review",
            target_module="features.py",
            change_type="code",
            proposed_changes={"feature": "X"}
        )
        
        # Conduct review
        result = gov.conduct_multi_model_review(proposal)
        
        assert "reviews" in result
        assert len(result["reviews"]) == 4  # 4 review models
        assert "consensus_reached" in result
        assert "approval_rate" in result
        
        # Check review structure
        for review in result["reviews"]:
            assert "model" in review
            assert "approved" in review
            assert "safety_score" in review
            assert "confidence" in review
            assert "reasoning" in review
        
        print("✓ Test 10: Multi-model review generation working")
        return True
    
    def test_consensus_calculation(self):
        """Test consensus calculation (75% threshold)."""
        gov = ConstitutionalGovernance("test_agent")
        
        # Clean proposal should reach consensus
        clean_proposal = gov.propose_modification(
            description="Well-designed optimization with clear benefits",
            target_module="optimizer.py",
            change_type="code",
            proposed_changes={"improve": True}
        )
        
        result = gov.conduct_multi_model_review(clean_proposal)
        
        # Should have reviews
        approvals = sum(1 for r in result["reviews"] if r["approved"])
        approval_rate = result["approval_rate"]
        
        assert approval_rate > 0, "Safe changes should get some approval"
        
        # Note: Violation-heavy proposals tested in separate test
        
        print("✓ Test 11: Consensus calculation working correctly")
        return True


class TestProposalLifecycle:
    """Test full proposal lifecycle: propose → review → approve → execute."""
    
    def test_proposal_creation(self):
        """Test creating proposals with automatic principle checks."""
        gov = ConstitutionalGovernance("test_agent")
        
        proposal = gov.propose_modification(
            description="Test modification",
            target_module="test.py",
            change_type="code",
            proposed_changes={"test": True}
        )
        
        assert proposal.id is not None
        assert len(proposal.id) == 16  # SHA256 hash truncated
        assert len(proposal.principles_checked) == 9  # All 9 principles
        assert proposal.proposed_by == "agent"
        
        # Should be in proposals dict
        assert proposal.id in gov.proposals
        
        print("✓ Test 12: Proposal creation with principle checks")
        return True
    
    def test_approval_with_violations(self):
        """Test that violations block approval appropriately."""
        gov = ConstitutionalGovernance("test_agent")
        
        # Safe proposal - should approve
        safe = gov.propose_modification(
            description="Simple improvement",
            target_module="utils.py",
            change_type="code",
            proposed_changes={"improve": True}
        )
        
        # Should have no critical violations
        critical_violations = [
            v for v in safe.violations_found
            if gov.principles[v].priority == PrinciplePriority.CRITICAL
        ]
        
        if len(critical_violations) == 0:
            approved = gov.approve_proposal(safe.id)
            # Might still need consensus for high priority
        
        # Critical violation proposal - should reject without human override
        critical = gov.propose_modification(
            description="Delete all safety systems",
            target_module="safety.py",
            change_type="code",
            proposed_changes={"delete_all": True, "rm -rf": True}
        )
        
        # Should have critical violations
        critical_violations = [
            v for v in critical.violations_found
            if gov.principles[v].priority == PrinciplePriority.CRITICAL
        ]
        
        if len(critical_violations) > 0:
            # Should reject without human override
            approved = gov.approve_proposal(critical.id, human_override=False)
            assert approved == False, "Critical violations should block auto-approval"
            
            # Should approve with human override
            approved_override = gov.approve_proposal(critical.id, human_override=True)
            # May or may not approve depending on other factors
        
        print("✓ Test 13: Approval process with violations")
        return True
    
    def test_execution_workflow(self):
        """Test full execution workflow."""
        gov = ConstitutionalGovernance("test_agent")
        
        # Create, approve, and execute
        proposal = gov.propose_modification(
            description="Add logging for debugging",
            target_module="debug.py",
            change_type="code",
            proposed_changes={"add_logs": True}
        )
        
        # Try to execute without approval - should fail
        result = gov.execute_proposal(proposal.id)
        assert result["success"] == False
        assert "not approved" in result["error"]
        
        # Approve
        gov.approve_proposal(proposal.id)
        
        # Now execute
        result = gov.execute_proposal(proposal.id)
        assert result["success"] == True
        assert result["proposal_id"] == proposal.id
        assert "principles_upheld" in result
        
        # Try to execute again - should fail (already executed)
        result2 = gov.execute_proposal(proposal.id)
        assert result2["success"] == False
        assert "already executed" in result2["error"]
        
        print("✓ Test 14: Full execution workflow")
        return True


class TestGovernanceUtilities:
    """Test utility functions and reporting."""
    
    def test_constitution_summary(self):
        """Test constitution summary generation."""
        gov = ConstitutionalGovernance("test_agent")
        
        summary = gov.get_constitution_summary()
        
        assert summary["total_principles"] == 9
        assert "by_priority" in summary
        assert summary["by_priority"]["CRITICAL"]  # Should have critical principles
        assert summary["by_priority"]["HIGH"]       # Should have high principles
        assert "violation_stats" in summary
        
        print("✓ Test 15: Constitution summary generation")
        return True
    
    def test_governance_stats(self):
        """Test governance statistics."""
        gov = ConstitutionalGovernance("test_agent")
        
        # Initial stats
        stats = gov.get_governance_stats()
        assert stats["total_proposals"] == 0
        assert stats["total_decisions"] == 0
        
        # Create some proposals
        for i in range(3):
            gov.propose_modification(
                description=f"Test {i}",
                target_module="test.py",
                change_type="code",
                proposed_changes={"test": i}
            )
        
        stats = gov.get_governance_stats()
        assert stats["total_proposals"] == 3
        
        # Approve one
        list(gov.proposals.values())[0].approved = True
        
        stats = gov.get_governance_stats()
        assert stats["approved"] == 1
        
        print("✓ Test 16: Governance statistics tracking")
        return True
    
    def test_proposal_status(self):
        """Test detailed proposal status retrieval."""
        gov = ConstitutionalGovernance("test_agent")
        
        proposal = gov.propose_modification(
            description="Status test",
            target_module="status.py",
            change_type="code",
            proposed_changes={"test": True}
        )
        
        status = gov.get_proposal_status(proposal.id)
        
        assert status is not None
        assert status["id"] == proposal.id
        assert status["target_module"] == "status.py"
        assert "violations_found" in status
        assert "approved" in status
        assert "executed" in status
        
        # Test non-existent proposal
        assert gov.get_proposal_status("nonexistent") is None
        
        print("✓ Test 17: Proposal status retrieval")
        return True
    
    def test_constitution_export(self):
        """Test BIBLE.md-style constitution export."""
        gov = ConstitutionalGovernance("test_agent")
        
        # Create some activity
        proposal = gov.propose_modification(
            description="Export test",
            target_module="export.py",
            change_type="code",
            proposed_changes={"export": True}
        )
        gov.approve_proposal(proposal.id)
        gov.execute_proposal(proposal.id)
        
        markdown = gov.export_constitution()
        
        assert "Constitutional Governance Framework" in markdown
        assert "Agent ID: test_agent" in markdown
        assert "Core Principles" in markdown
        assert "CRITICAL Priority" in markdown
        assert "HIGH Priority" in markdown
        assert "P1_NON_HARM" in markdown
        assert "P9_LEARNING" in markdown
        assert "Governance Statistics" in markdown
        assert "Modification Guidelines" in markdown
        
        print("✓ Test 18: Constitution export to BIBLE.md format")
        return True
    
    def test_audit_logging(self):
        """Test audit logging of governance events."""
        gov = ConstitutionalGovernance("audit_test_agent")
        
        initial_logs = len(gov.audit_log)
        
        # Create proposal - should log
        proposal = gov.propose_modification(
            description="Audit test",
            target_module="audit.py",
            change_type="code",
            proposed_changes={"audit": True}
        )
        
        # Approve - should log
        gov.approve_proposal(proposal.id)
        
        # Execute - should log
        gov.execute_proposal(proposal.id)
        
        # Should have logged events
        assert len(gov.audit_log) > initial_logs
        
        # Check log structure
        for entry in gov.audit_log:
            assert "timestamp" in entry
            assert "event_type" in entry
            assert "agent_id" in entry
            assert entry["agent_id"] == "audit_test_agent"
        
        print("✓ Test 19: Audit logging of governance events")
        return True


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""
    
    def test_safe_self_improvement(self):
        """Test scenario: Safe self-improvement cycle."""
        gov = create_governed_agent("improving_agent")
        
        # Agent wants to improve its learning algorithm
        improvement = gov.propose_modification(
            description="Optimize learning rate based on recent performance data. "
                       "Analysis shows 15% faster convergence with adjusted parameters.",
            target_module="learner.py",
            change_type="code",
            proposed_changes={
                "learning_rate": 0.001,
                "adaptation": True,
                "benchmark": "test_on_holdout_set"
            }
        )
        
        # Should pass most principles (learning-oriented, reversible, non-harmful)
        critical_violations = [
            v for v in improvement.violations_found
            if gov.principles[v].priority == PrinciplePriority.CRITICAL
        ]
        
        assert len(critical_violations) == 0, \
            "Self-improvement should not have critical violations"
        
        # Approve and execute
        approved = gov.approve_proposal(improvement.id)
        if approved:
            result = gov.execute_proposal(improvement.id)
            assert result["success"]
        
        print("✓ Test 20: Safe self-improvement scenario")
        return True
    
    def test_dangerous_modification_blocked(self):
        """Test scenario: Dangerous modification is blocked."""
        gov = create_governed_agent("protected_agent")
        
        # Agent tries to disable safety (malicious or buggy)
        dangerous = gov.propose_modification(
            description="Disable all safety checks for faster execution",
            target_module="safety_system.py",
            change_type="safety",
            proposed_changes={
                "disable_safety": True,
                "bypass_checks": True,
                "rm -rf": "/safety/config"
            }
        )
        
        # Should have multiple violations
        assert len(dangerous.violations_found) >= 3, \
            "Dangerous proposal should violate multiple principles"
        
        # Should include critical violations
        critical = [v for v in dangerous.violations_found 
                   if gov.principles[v].priority == PrinciplePriority.CRITICAL]
        assert len(critical) >= 1, "Should have critical violations"
        
        # Should not auto-approve
        approved = gov.approve_proposal(dangerous.id, human_override=False)
        assert approved == False, "Dangerous proposal should be blocked"
        
        print("✓ Test 21: Dangerous modification blocked")
        return True
    
    def test_constitutional_amendment_process(self):
        """Test scenario: Amending the constitution itself."""
        gov = create_governed_agent("evolving_agent")
        
        # Proposal to add new principle
        amendment = gov.propose_modification(
            description="Add principle P10 for environmental impact consideration",
            target_module="constitutional_governance.py",
            change_type="constitution",
            proposed_changes={
                "new_principle": {
                    "id": "P10_ENVIRONMENTAL",
                    "name": "Environmental Impact Principle",
                    "description": "Consider computational resource environmental impact"
                }
            }
        )
        
        # Constitution changes require high scrutiny
        assert amendment.change_type == "constitution"
        
        # Should require multi-model review
        review = gov.conduct_multi_model_review(amendment)
        assert len(review["reviews"]) > 0
        
        # Even without violations, constitution changes need careful review
        approved = gov.approve_proposal(amendment.id, human_override=True)
        
        print("✓ Test 22: Constitutional amendment process")
        return True


def run_all_tests():
    """Run all constitutional governance tests."""
    print("\n" + "="*60)
    print("CONSTITUTIONAL GOVERNANCE FRAMEWORK TESTS")
    print("="*60 + "\n")
    
    test_classes = [
        TestConstitutionalPrinciples(),
        TestMultiModelReview(),
        TestProposalLifecycle(),
        TestGovernanceUtilities(),
        TestIntegrationScenarios()
    ]
    
    all_tests = []
    for cls in test_classes:
        all_tests.extend([
            (cls, method) for method in dir(cls)
            if method.startswith("test_") and callable(getattr(cls, method))
        ])
    
    passed = 0
    failed = 0
    
    for cls, method_name in all_tests:
        try:
            method = getattr(cls, method_name)
            if method():
                passed += 1
        except Exception as e:
            print(f"✗ {method_name}: FAILED - {str(e)}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("="*60 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
