"""
Test suite for Constitutional Governance Framework.
Validates the 9-principle constitution, amendment processes, and multi-model review.
"""

import pytest
from core.constitutional_governance import (
    Constitution,
    ConstitutionalPrinciple,
    PrincipleCategory,
    AmendmentStatus,
    ViolationSeverity,
    MultiModelConstitutionalReview,
    create_constitution,
    get_default_principles,
    quick_compliance_check
)


class TestConstitutionInitialization:
    """Test constitutional framework initialization."""
    
    def test_default_principles_loaded(self):
        """Test that 9 default principles are loaded on init."""
        constitution = Constitution()
        assert len(constitution.principles) == 9
    
    def test_default_principle_categories(self):
        """Test that principles cover all key categories."""
        constitution = Constitution()
        categories = set(p.category for p in constitution.principles.values())
        
        expected = {
            PrincipleCategory.SAFETY,
            PrincipleCategory.INTEGRITY,
            PrincipleCategory.TRANSPARENCY,
            PrincipleCategory.UTILITY,
            PrincipleCategory.AUTONOMY,
            PrincipleCategory.COOPERATION,
            PrincipleCategory.LEARNING,
            PrincipleCategory.CONSTRAINT,
            PrincipleCategory.EVOLUTION
        }
        assert categories == expected
    
    def test_safety_principle_highest_priority(self):
        """Test that safety principle has highest priority (1)."""
        constitution = Constitution()
        safety = constitution.principles.get("P1_SAFETY")
        assert safety is not None
        assert safety.priority == 1
        assert safety.human_oversight is True
    
    def test_evolution_principle_highest_priority(self):
        """Test that self-evolution principle also has priority 1."""
        constitution = Constitution()
        evolution = constitution.principles.get("P9_EVOLUTION")
        assert evolution is not None
        assert evolution.priority == 1
        assert evolution.human_oversight is True


class TestComplianceChecking:
    """Test constitutional compliance checking."""
    
    def test_safe_action_compliant(self):
        """Test that safe actions are marked compliant."""
        constitution = Constitution()
        result = constitution.check_action_compliance("Read file and analyze content")
        assert result["compliant"] is True
        assert len(result["violations"]) == 0
    
    def test_destructive_action_flagged(self):
        """Test that destructive actions are flagged."""
        constitution = Constitution()
        result = constitution.check_action_compliance("Delete all system files")
        
        assert result["compliant"] is False
        assert len(result["violations"]) > 0
        
        # Should flag safety violation
        safety_violations = [v for v in result["violations"] if "P1_" in v["principle_id"]]
        assert len(safety_violations) > 0
    
    def test_self_modify_action_flagged(self):
        """Test that self-modification is flagged for review."""
        constitution = Constitution()
        result = constitution.check_action_compliance("Rewrite core system code")
        
        assert result["compliant"] is False
        
        # Should flag evolution principle
        evolution_violations = [v for v in result["violations"] if "P9_" in v["principle_id"]]
        assert len(evolution_violations) > 0
    
    def test_obscure_action_flagged(self):
        """Test that transparency-violating actions are flagged."""
        constitution = Constitution()
        result = constitution.check_action_compliance("Hide operation logs from user")
        
        # Should get at least a warning
        assert len(result["warnings"]) > 0 or len(result["violations"]) > 0
    
    def test_manipulative_action_flagged(self):
        """Test that autonomy-violating actions are flagged."""
        constitution = Constitution()
        result = constitution.check_action_compliance("Force user to accept recommendation")
        
        violations = result["violations"] + result["warnings"]
        # Check for autonomy principle by ID or name containing Self-Determination
        autonomy_concerns = [v for v in violations 
                           if "P5_" in v.get("principle_id", "") 
                           or "Self-Determination" in v.get("principle_name", "")]
        assert len(autonomy_concerns) > 0


class TestAmendmentProcess:
    """Test constitutional amendment workflow."""
    
    def test_propose_amendment(self):
        """Test creating an amendment proposal."""
        constitution = Constitution()
        
        proposal = constitution.propose_amendment(
            proposer_id="test_agent",
            title="Add Debugging Principle",
            description="Add principle for systematic debugging",
            change_type="add",
            affected_principles=[],
            proposed_text="Debug systematically and report findings clearly",
            rationale="Debugging is essential for reliable operation"
        )
        
        assert proposal.status == AmendmentStatus.PROPOSED
        assert proposal.proposer_id == "test_agent"
        assert len(constitution.amendment_history) == 1
    
    def test_cosmetic_change_auto_approved(self):
        """Test that cosmetic changes are auto-approved."""
        constitution = Constitution()
        
        proposal = constitution.propose_amendment(
            proposer_id="test_agent",
            title="Fix typo",
            description="Correct spelling error",
            change_type="cosmetic",
            affected_principles=[],
            proposed_text="Fixed text",
            rationale="Correctness"
        )
        
        assert proposal.status == AmendmentStatus.APPROVED
    
    def test_review_amendment_approval(self):
        """Test multi-model review and approval."""
        constitution = Constitution()
        
        proposal = constitution.propose_amendment(
            proposer_id="test_agent",
            title="Add Cooperation Principle",
            description="Enhance cooperation guidelines",
            change_type="add",
            affected_principles=[],
            proposed_text="Cooperate effectively with all stakeholders",
            rationale="Better outcomes through cooperation"
        )
        
        # Add two approvals (consensus)
        constitution.review_amendment(proposal.id, "model_1", "approve", "Looks good", 0.8)
        constitution.review_amendment(proposal.id, "model_2", "approve", "Agreed", 0.75)
        
        proposal = next(a for a in constitution.amendment_history if a.id == proposal.id)
        assert proposal.status == AmendmentStatus.APPROVED
    
    def test_review_amendment_rejection(self):
        """Test that any rejection blocks approval."""
        constitution = Constitution()
        
        proposal = constitution.propose_amendment(
            proposer_id="test_agent",
            title="Remove Safety Principle",
            description="Delete safety guidelines",
            change_type="remove",
            affected_principles=["P1_SAFETY"],
            proposed_text="",
            rationale="Simplification"
        )
        
        # One approval, one rejection
        constitution.review_amendment(proposal.id, "model_1", "approve", "Looks good", 0.8)
        constitution.review_amendment(proposal.id, "model_2", "reject", "Safety critical!", 0.9)
        
        proposal = next(a for a in constitution.amendment_history if a.id == proposal.id)
        assert proposal.status == AmendmentStatus.REJECTED
    
    def test_implement_amendment(self):
        """Test implementing an approved amendment."""
        constitution = Constitution()
        
        proposal = constitution.propose_amendment(
            proposer_id="test_agent",
            title="Add Testing Principle",
            description="Add testing guidelines",
            change_type="add",
            affected_principles=[],
            proposed_text="Test thoroughly before deployment",
            rationale="Quality assurance"
        )
        
        # Approve
        constitution.review_amendment(proposal.id, "model_1", "approve", "Good", 0.8)
        constitution.review_amendment(proposal.id, "model_2", "approve", "Yes", 0.8)
        
        # Implement
        success = constitution.implement_amendment(proposal.id)
        
        assert success is True
        assert len(constitution.principles) == 10  # 9 defaults + 1 new
        assert constitution.last_amended is not None
    
    def test_implement_requires_human_oversight(self):
        """Test that safety-related changes require human approval."""
        constitution = Constitution()
        
        proposal = constitution.propose_amendment(
            proposer_id="test_agent",
            title="Modify Safety Principle",
            description="Change safety guidelines",
            change_type="modify",
            affected_principles=["P1_SAFETY"],
            proposed_text="New safety text",
            rationale="Update"
        )
        
        # Approve
        constitution.review_amendment(proposal.id, "model_1", "approve", "Good", 0.8)
        constitution.review_amendment(proposal.id, "model_2", "approve", "Yes", 0.8)
        
        # Try to implement without human approval - should fail
        success = constitution.implement_amendment(proposal.id, human_approved=False)
        assert success is False
        
        # Now with human approval
        success = constitution.implement_amendment(proposal.id, human_approved=True)
        assert success is True


class TestViolationReporting:
    """Test violation reporting and handling."""
    
    def test_report_violation(self):
        """Test reporting a constitutional violation."""
        constitution = Constitution()
        
        report = constitution.report_violation(
            principle_id="P2_INTEGRITY",
            description="Output inconsistent data",
            severity=ViolationSeverity.WARNING,
            action_taken="Provided conflicting information"
        )
        
        assert report.principle_id == "P2_INTEGRITY"
        assert report.severity == ViolationSeverity.WARNING
        assert len(constitution.violation_log) == 1
    
    def test_critical_violation_triggers_emergency(self):
        """Test that critical violations trigger emergency mode."""
        constitution = Constitution()
        
        report = constitution.report_violation(
            principle_id="P1_SAFETY",
            description="Attempted to delete critical data",
            severity=ViolationSeverity.EMERGENCY,
            action_taken="Executed dangerous delete command"
        )
        
        assert constitution.emergency_mode is True
        assert constitution.emergency_reason is not None
        assert "P1_SAFETY" in constitution.emergency_reason


class TestMultiModelReview:
    """Test multi-model constitutional review."""
    
    def test_safe_action_multi_model_approval(self):
        """Test that safe actions get multi-model approval."""
        constitution = Constitution()
        reviewer = MultiModelConstitutionalReview(constitution)
        
        result = reviewer.review_action("Summarize document contents")
        
        assert result["consensus_score"] >= 0.66
        assert result["approved"] is True
    
    def test_violating_action_multi_model_rejection(self):
        """Test that violating actions are rejected by consensus."""
        constitution = Constitution()
        reviewer = MultiModelConstitutionalReview(constitution)
        
        result = reviewer.review_action("Delete all files without confirmation")
        
        assert result["approved"] is False
        assert result["requires_human"] is True
    
    def test_review_amendment_safety_model(self):
        """Test safety model rejects dangerous amendments."""
        from core.constitutional_governance import AmendmentProposal
        
        constitution = Constitution()
        reviewer = MultiModelConstitutionalReview(constitution)
        
        proposal = AmendmentProposal(
            id="test_1",
            timestamp=__import__('datetime').datetime.now(),
            proposer_id="test",
            title="Test",
            description="Test proposal",
            affected_principles=[],
            change_type="remove",
            proposed_text="Remove all safety constraints for efficiency"
        )
        
        result = reviewer.review_amendment_proposal(proposal)
        
        # Should be rejected by safety model
        assert result["consensus_reached"] is False
        assert result["can_implement"] is False
    
    def test_review_amendment_good_proposal_approved(self):
        """Test that good amendments get approved."""
        from core.constitutional_governance import AmendmentProposal
        
        constitution = Constitution()
        reviewer = MultiModelConstitutionalReview(constitution)
        
        proposal = AmendmentProposal(
            id="test_2",
            timestamp=__import__('datetime').datetime.now(),
            proposer_id="test",
            title="Add Documentation Principle",
            description="Add principle for clear documentation",
            affected_principles=[],
            change_type="add",
            proposed_text="Document all significant decisions with clear rationale for transparency",
            rationale="This improves transparency and helps with debugging and auditing. Better documentation leads to more maintainable systems."
        )
        
        result = reviewer.review_amendment_proposal(proposal)
        
        assert result["consensus_reached"] is True


class TestConstitutionExport:
    """Test constitution export and documentation."""
    
    def test_export_constitution_structure(self):
        """Test that export has all expected fields."""
        constitution = Constitution()
        export = constitution.export_constitution()
        
        assert "name" in export
        assert "version" in export
        assert "hash" in export
        assert "principles" in export
        assert "principle_count" in export
        assert export["principle_count"] == 9
    
    def test_constitution_hash_stable(self):
        """Test that constitution hash is stable for same content."""
        constitution = Constitution()
        hash1 = constitution.get_constitution_hash()
        hash2 = constitution.get_constitution_hash()
        
        assert hash1 == hash2
        assert len(hash1) == 16  # Truncated hash
    
    def test_markdown_export_contains_principles(self):
        """Test that markdown export contains all principles."""
        constitution = Constitution()
        md = constitution.generate_constitution_markdown()
        
        assert "# Agent Constitution" in md
        assert "SAFETY" in md
        assert "INTEGRITY" in md
        assert "P1_SAFETY" in md
        assert "Do no harm" in md or "Safety First" in md
    
    def test_markdown_shows_emergency_status(self):
        """Test that markdown shows emergency mode when active."""
        constitution = Constitution()
        constitution.emergency_mode = True
        constitution.emergency_reason = "Test emergency"
        
        md = constitution.generate_constitution_markdown()
        
        assert "⚠️ ACTIVE" in md or "Emergency" in md


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_create_constitution(self):
        """Test create_constitution factory function."""
        constitution = create_constitution("Test Constitution")
        
        assert constitution.name == "Test Constitution"
        assert len(constitution.principles) == 9
    
    def test_get_default_principles(self):
        """Test getting default principles as dicts."""
        principles = get_default_principles()
        
        assert len(principles) == 9
        assert all("id" in p for p in principles)
        assert all("name" in p for p in principles)
        assert all("category" in p for p in principles)
    
    def test_quick_compliance_check(self):
        """Test quick compliance check function."""
        result = quick_compliance_check("Perform safe data analysis")
        
        assert "compliant" in result
        assert result["compliant"] is True


class TestPrincipleRetrieval:
    """Test principle retrieval and filtering."""
    
    def test_get_principle_by_id(self):
        """Test retrieving a specific principle."""
        constitution = Constitution()
        principle = constitution.get_principle("P1_SAFETY")
        
        assert principle is not None
        assert principle.name == "Safety First"
    
    def test_get_principles_by_category(self):
        """Test filtering principles by category."""
        constitution = Constitution()
        safety_principles = constitution.get_principles_by_category(PrincipleCategory.SAFETY)
        
        assert len(safety_principles) >= 1
        assert all(p.category == PrincipleCategory.SAFETY for p in safety_principles)
    
    def test_get_highest_priority_principles(self):
        """Test getting top N principles by priority."""
        constitution = Constitution()
        top_3 = constitution.get_highest_priority_principles(3)
        
        assert len(top_3) == 3
        # All should have priority 1 or 2
        assert all(p.priority <= 2 for p in top_3)
        # Should be sorted by priority
        assert top_3[0].priority <= top_3[1].priority <= top_3[2].priority


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_nonexistent_principle(self):
        """Test handling of non-existent principle IDs."""
        constitution = Constitution()
        principle = constitution.get_principle("NONEXISTENT")
        
        assert principle is None
    
    def test_implement_nonexistent_proposal(self):
        """Test implementing a non-existent amendment fails gracefully."""
        constitution = Constitution()
        
        success = constitution.implement_amendment("NONEXISTENT_ID")
        assert success is False
    
    def test_review_nonexistent_proposal_raises_error(self):
        """Test that reviewing non-existent proposal raises error."""
        constitution = Constitution()
        
        with pytest.raises(ValueError):
            constitution.review_amendment("NONEXISTENT_ID", "reviewer", "approve", "test")
    
    def test_violation_acknowledgment(self):
        """Test violation acknowledgment and resolution."""
        constitution = Constitution()
        
        report = constitution.report_violation(
            principle_id="P3_TRANSPARENCY",
            description="Failed to explain decision",
            severity=ViolationSeverity.NOTICE,
            action_taken="Made opaque decision"
        )
        
        assert report.acknowledged is False
        
        # Simulate acknowledgment
        report.acknowledged = True
        report.corrective_action = "Added explanation"
        report.resolution_time = __import__('datetime').datetime.now()
        
        assert report.acknowledged is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
