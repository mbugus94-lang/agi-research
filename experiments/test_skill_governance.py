"""
Test suite for Skill Governance Lifecycle Module.

Tests the complete SkillsVote-inspired pipeline:
- Collection: Pattern crystallization
- Recommendation: Context-aware skill suggestion  
- Evolution: Skill improvement proposals

Coverage:
- SkillRegistry: Storage and retrieval
- PatternCrystallizer: Pattern → Skill conversion
- SkillRecommendationEngine: Context matching
- SkillEvolutionPipeline: Improvement proposals
- SkillGovernanceLifecycle: Full pipeline integration
"""

import pytest
import time
from typing import List, Dict, Any

from skills.skill_governance import (
    SkillGovernanceLifecycle,
    SkillRegistry,
    PatternCrystallizer,
    SkillRecommendationEngine,
    SkillEvolutionPipeline,
    CrystallizedSkill,
    SkillRecommendation,
    EvolutionProposal,
    SkillLifecycleStage,
    SkillType,
    SkillVersion,
    SkillVerificationResult,
    PatternConfidence,
    create_skill_governance
)


# ==================== TESTS: SkillRegistry ====================

class TestSkillRegistry:
    """Tests for skill registry storage and retrieval."""
    
    def test_register_and_retrieve(self):
        """Test basic skill registration and retrieval."""
        registry = SkillRegistry()
        
        skill = CrystallizedSkill(
            skill_id="test_001",
            name="Test Skill",
            description="A test skill",
            skill_type=SkillType.ATOMIC,
            lifecycle_stage=SkillLifecycleStage.DRAFT,
            derived_from_patterns=["p1"],
            extracted_from_trajectories=["t1"],
            action_template=["step1", "step2"],
            parameter_schema={},
            preconditions={},
            postconditions={},
            required_tools=["tool1"],
            version=SkillVersion(0, 1, 0),
            tags={"test", "draft"},
            domain="test"
        )
        
        registry.register(skill)
        retrieved = registry.get("test_001")
        
        assert retrieved is not None
        assert retrieved.name == "Test Skill"
        assert retrieved.skill_type == SkillType.ATOMIC
    
    def test_find_by_stage(self):
        """Test finding skills by lifecycle stage."""
        registry = SkillRegistry()
        
        stages = [
            SkillLifecycleStage.DRAFT,
            SkillLifecycleStage.DRAFT,
            SkillLifecycleStage.ACTIVE
        ]
        
        for i, stage in enumerate(stages):
            skill = CrystallizedSkill(
                skill_id=f"skill_{i}",
                name=f"Skill {i}",
                description="Test",
                skill_type=SkillType.ATOMIC,
                lifecycle_stage=stage,
                derived_from_patterns=[],
                extracted_from_trajectories=[],
                action_template=[],
                parameter_schema={},
                preconditions={},
                postconditions={},
                required_tools=[],
                version=SkillVersion(1, 0, 0)
            )
            registry.register(skill)
        
        draft_skills = registry.find_by_stage(SkillLifecycleStage.DRAFT)
        assert len(draft_skills) == 2
        
        active_skills = registry.find_by_stage(SkillLifecycleStage.ACTIVE)
        assert len(active_skills) == 1
    
    def test_find_by_domain(self):
        """Test domain-based skill filtering."""
        registry = SkillRegistry()
        
        domains = ["research", "coding", "research"]
        for i, domain in enumerate(domains):
            skill = CrystallizedSkill(
                skill_id=f"skill_{i}",
                name=f"Skill {i}",
                description="Test",
                skill_type=SkillType.ATOMIC,
                lifecycle_stage=SkillLifecycleStage.ACTIVE,
                derived_from_patterns=[],
                extracted_from_trajectories=[],
                action_template=[],
                parameter_schema={},
                preconditions={},
                postconditions={},
                required_tools=[],
                version=SkillVersion(1, 0, 0),
                domain=domain
            )
            registry.register(skill)
        
        research_skills = registry.find_by_domain("research")
        assert len(research_skills) == 2
    
    def test_update_stage(self):
        """Test lifecycle stage transitions."""
        registry = SkillRegistry()
        
        skill = CrystallizedSkill(
            skill_id="test_skill",
            name="Test",
            description="Test",
            skill_type=SkillType.ATOMIC,
            lifecycle_stage=SkillLifecycleStage.DRAFT,
            derived_from_patterns=[],
            extracted_from_trajectories=[],
            action_template=[],
            parameter_schema={},
            preconditions={},
            postconditions={},
            required_tools=[],
            version=SkillVersion(0, 1, 0)
        )
        
        registry.register(skill)
        
        # Update stage
        success = registry.update_stage("test_skill", SkillLifecycleStage.VALIDATED)
        assert success is True
        
        # Verify update
        updated = registry.get("test_skill")
        assert updated.lifecycle_stage == SkillLifecycleStage.VALIDATED
        
        # Verify old stage is empty
        draft_skills = registry.find_by_stage(SkillLifecycleStage.DRAFT)
        assert len(draft_skills) == 0
    
    def test_statistics(self):
        """Test registry statistics generation."""
        registry = SkillRegistry()
        
        # Register skills of various types
        for i in range(5):
            skill = CrystallizedSkill(
                skill_id=f"s{i}",
                name=f"Skill {i}",
                description="Test",
                skill_type=SkillType.ATOMIC if i < 3 else SkillType.COMPOSITE,
                lifecycle_stage=SkillLifecycleStage.ACTIVE if i < 2 else SkillLifecycleStage.DRAFT,
                derived_from_patterns=[],
                extracted_from_trajectories=[],
                action_template=[],
                parameter_schema={},
                preconditions={},
                postconditions={},
                required_tools=[],
                version=SkillVersion(1, 0, 0),
                domain="test"
            )
            registry.register(skill)
        
        stats = registry.get_statistics()
        
        assert stats["total_skills"] == 5
        assert stats["by_stage"]["active"] == 2
        assert stats["by_stage"]["draft"] == 3
        assert stats["by_type"]["atomic"] == 3
        assert stats["by_type"]["composite"] == 2


# ==================== TESTS: PatternCrystallizer ====================

class TestPatternCrystallizer:
    """Tests for pattern-to-skill crystallization."""
    
    def test_crystallize_high_confidence_pattern(self):
        """Test crystallization of high-confidence pattern."""
        registry = SkillRegistry()
        crystallizer = PatternCrystallizer(registry)
        
        pattern_data = {
            "pattern_id": "p_001",
            "pattern_type": "action_sequence",
            "action_template": ["search_arxiv", "analyze_papers", "summarize"],
            "frequency": 10,
            "success_rate": 0.85,
            "source_trajectories": ["t1", "t2"],
            "confidence": 0.9,
            "preconditions": {"has_query": True},
            "postconditions": {"has_summary": True},
            "parameter_slots": ["query"]
        }
        
        skill = crystallizer.crystallize(**pattern_data)
        
        assert skill is not None
        assert skill.skill_type == SkillType.COMPOSITE
        assert skill.lifecycle_stage == SkillLifecycleStage.DRAFT
        assert skill.domain == "research"  # Inferred from action template
        assert "auto-crystallized" in skill.tags
        assert len(skill.action_template) == 3
    
    def test_crystallize_low_confidence_rejected(self):
        """Test that low-confidence patterns are rejected."""
        registry = SkillRegistry()
        crystallizer = PatternCrystallizer(registry)
        
        pattern_data = {
            "pattern_id": "p_low",
            "pattern_type": "action_sequence",
            "action_template": ["step1"],
            "frequency": 2,
            "success_rate": 0.5,
            "source_trajectories": ["t1"],
            "confidence": 0.3,  # Below MEDIUM threshold
            "preconditions": {},
            "postconditions": {},
            "parameter_slots": []
        }
        
        skill = crystallizer.crystallize(**pattern_data)
        
        assert skill is None  # Rejected due to low confidence
    
    def test_crystallize_recovery_pattern(self):
        """Test crystallization of recovery strategy patterns."""
        registry = SkillRegistry()
        crystallizer = PatternCrystallizer(registry)
        
        pattern_data = {
            "pattern_id": "p_recovery",
            "pattern_type": "recovery_strategy",
            "action_template": ["retry_with_backoff", "fallback_to_cache"],
            "frequency": 5,
            "success_rate": 0.95,
            "source_trajectories": ["t1"],
            "confidence": 0.8,
            "preconditions": {"error_occurred": True},
            "postconditions": {"recovered": True},
            "parameter_slots": []
        }
        
        skill = crystallizer.crystallize(**pattern_data)
        
        assert skill is not None
        assert skill.skill_type == SkillType.RECOVERY
    
    def test_crystallize_domain_inference(self):
        """Test domain inference from action patterns."""
        registry = SkillRegistry()
        crystallizer = PatternCrystallizer(registry)
        
        test_cases = [
            ("search_arxiv read_paper", "research"),
            ("write_code run_tests", "coding"),
            ("process_csv load_data", "data"),
            ("generic_action another", "general")
        ]
        
        for i, (actions, expected_domain) in enumerate(test_cases):
            pattern_data = {
                "pattern_id": f"p_{i}",
                "pattern_type": "action_sequence",
                "action_template": actions.split(),
                "frequency": 5,
                "success_rate": 0.8,
                "source_trajectories": [f"t{i}"],
                "confidence": 0.8,
                "preconditions": {},
                "postconditions": {},
                "parameter_slots": []
            }
            
            skill = crystallizer.crystallize(**pattern_data)
            assert skill.domain == expected_domain, f"Expected {expected_domain} for {actions}"


# ==================== TESTS: SkillRecommendationEngine ====================

class TestSkillRecommendationEngine:
    """Tests for context-aware skill recommendation."""
    
    def test_recommend_by_domain_match(self):
        """Test recommendation based on domain matching."""
        registry = SkillRegistry()
        engine = SkillRecommendationEngine(registry)
        
        # Register skills in different domains
        for domain in ["research", "coding", "data"]:
            skill = CrystallizedSkill(
                skill_id=f"skill_{domain}",
                name=f"{domain} skill",
                description="Test",
                skill_type=SkillType.ATOMIC,
                lifecycle_stage=SkillLifecycleStage.ACTIVE,
                derived_from_patterns=[],
                extracted_from_trajectories=[],
                action_template=[],
                parameter_schema={},
                preconditions={},
                postconditions={},
                required_tools=[],
                version=SkillVersion(1, 0, 0),
                domain=domain,
                usage_count=100,
                success_count=90
            )
            registry.register(skill)
        
        # Request recommendations for research context
        context = {"domain": "research"}
        recommendations = engine.recommend(context, top_k=3)
        
        assert len(recommendations) > 0
        assert recommendations[0].skill_id == "skill_research"
    
    def test_recommend_by_tag_match(self):
        """Test recommendation based on tag matching."""
        registry = SkillRegistry()
        engine = SkillRecommendationEngine(registry)
        
        skill = CrystallizedSkill(
            skill_id="tagged_skill",
            name="Tagged Skill",
            description="Test",
            skill_type=SkillType.ATOMIC,
            lifecycle_stage=SkillLifecycleStage.ACTIVE,
            derived_from_patterns=[],
            extracted_from_trajectories=[],
            action_template=[],
            parameter_schema={},
            preconditions={},
            postconditions={},
            required_tools=[],
            version=SkillVersion(1, 0, 0),
            tags={"search", "web"},
            usage_count=50,
            success_count=45
        )
        registry.register(skill)
        
        context = {"tags": ["search", "research"]}
        recommendations = engine.recommend(context, top_k=1)
        
        assert len(recommendations) == 1
        assert recommendations[0].skill_id == "tagged_skill"
    
    def test_recommend_by_tool_compatibility(self):
        """Test recommendation based on required tools."""
        registry = SkillRegistry()
        engine = SkillRecommendationEngine(registry)
        
        skill = CrystallizedSkill(
            skill_id="tool_skill",
            name="Tool Skill",
            description="Test",
            skill_type=SkillType.ATOMIC,
            lifecycle_stage=SkillLifecycleStage.ACTIVE,
            derived_from_patterns=[],
            extracted_from_trajectories=[],
            action_template=[],
            parameter_schema={},
            preconditions={},
            postconditions={},
            required_tools=["browser", "scraper"],
            version=SkillVersion(1, 0, 0),
            usage_count=30,
            success_count=28
        )
        registry.register(skill)
        
        context = {"required_tools": ["browser"]}
        recommendations = engine.recommend(context, top_k=1)
        
        assert len(recommendations) == 1
        assert recommendations[0].context_match.get("tool_compatible") is True
    
    def test_recommend_confidence_calculation(self):
        """Test that confidence considers maturity score."""
        registry = SkillRegistry()
        engine = SkillRecommendationEngine(registry)
        
        # Register two skills with different maturity
        for i, usage in enumerate([10, 200]):
            skill = CrystallizedSkill(
                skill_id=f"mature_{i}",
                name=f"Mature {i}",
                description="Test",
                skill_type=SkillType.ATOMIC,
                lifecycle_stage=SkillLifecycleStage.ACTIVE,
                derived_from_patterns=[],
                extracted_from_trajectories=[],
                action_template=[],
                parameter_schema={},
                preconditions={},
                postconditions={},
                required_tools=[],
                version=SkillVersion(1 if i == 1 else 0, 0, 0),
                domain="test",
                usage_count=usage,
                success_count=int(usage * 0.9)
            )
            registry.register(skill)
        
        context = {"domain": "test"}
        recommendations = engine.recommend(context, top_k=2)
        
        # Higher maturity skill should have higher confidence
        assert recommendations[0].skill_id == "mature_1"  # More mature


# ==================== TESTS: SkillEvolutionPipeline ====================

class TestSkillEvolutionPipeline:
    """Tests for skill evolution proposals."""
    
    def test_propose_extension(self):
        """Test evolution proposal for skill extension."""
        registry = SkillRegistry()
        crystallizer = PatternCrystallizer(registry)
        pipeline = SkillEvolutionPipeline(registry, crystallizer)
        
        # Create base skill
        base_skill = CrystallizedSkill(
            skill_id="base_skill",
            name="Base Skill",
            description="Test",
            skill_type=SkillType.COMPOSITE,
            lifecycle_stage=SkillLifecycleStage.ACTIVE,
            derived_from_patterns=[],
            extracted_from_trajectories=[],
            action_template=["step1", "step2"],
            parameter_schema={},
            preconditions={},
            postconditions={},
            required_tools=[],
            version=SkillVersion(1, 0, 0),
            usage_count=100,
            success_count=85,
            failure_count=15  # Added to make success_rate = 0.85
        )
        registry.register(base_skill)
        
        # Pattern that extends the skill (more steps)
        new_patterns = [{
            "pattern_id": "extended",
            "pattern_type": "composite",  # Changed to match skill_type.value
            "action_template": ["step1", "step2", "step3", "step4"],
            "success_rate": 0.9,
            "frequency": 10  # Added to boost impact score
        }]
        
        proposal = pipeline.propose_evolution("base_skill", new_patterns)
        
        assert proposal is not None
        assert "Extended" in proposal.improvements[0]
    
    def test_propose_refinement(self):
        """Test evolution proposal for skill refinement."""
        registry = SkillRegistry()
        crystallizer = PatternCrystallizer(registry)
        pipeline = SkillEvolutionPipeline(registry, crystallizer)
        
        base_skill = CrystallizedSkill(
            skill_id="refine_skill",
            name="Refine Skill",
            description="Test",
            skill_type=SkillType.ATOMIC,
            lifecycle_stage=SkillLifecycleStage.ACTIVE,
            derived_from_patterns=[],
            extracted_from_trajectories=[],
            action_template=["action"],
            parameter_schema={},
            preconditions={},
            postconditions={},
            required_tools=[],
            version=SkillVersion(1, 0, 0),
            usage_count=100,
            success_count=70,
            failure_count=30  # Added to make success_rate = 0.7
        )
        registry.register(base_skill)
        
        # Pattern with higher success rate
        new_patterns = [{
            "pattern_id": "better",
            "pattern_type": "atomic",  # Changed to match skill_type.value
            "action_template": ["action"],
            "success_rate": 0.95  # Much better
        }]
        
        proposal = pipeline.propose_evolution("refine_skill", new_patterns)
        
        assert proposal is not None
        assert "Refined" in proposal.improvements[0] or "Replaced" in proposal.improvements[0]
    
    def test_no_evolution_low_impact(self):
        """Test that low-impact patterns don't trigger evolution."""
        registry = SkillRegistry()
        crystallizer = PatternCrystallizer(registry)
        pipeline = SkillEvolutionPipeline(registry, crystallizer)
        
        base_skill = CrystallizedSkill(
            skill_id="no_evo",
            name="No Evo Skill",
            description="Test",
            skill_type=SkillType.ATOMIC,
            lifecycle_stage=SkillLifecycleStage.ACTIVE,
            derived_from_patterns=[],
            extracted_from_trajectories=[],
            action_template=["action"],
            parameter_schema={},
            preconditions={},
            postconditions={},
            required_tools=[],
            version=SkillVersion(1, 0, 0),
            usage_count=1000,  # Very mature
            success_count=990  # 99% success
        )
        registry.register(base_skill)
        
        # Pattern barely better
        new_patterns = [{
            "pattern_id": "slightly_better",
            "pattern_type": "action_sequence",
            "action_template": ["action"],
            "success_rate": 0.995  # Only slightly better
        }]
        
        proposal = pipeline.propose_evolution("no_evo", new_patterns)
        
        assert proposal is None  # Not worth evolving


# ==================== TESTS: SkillGovernanceLifecycle ====================

class TestSkillGovernanceLifecycle:
    """Integration tests for full governance lifecycle."""
    
    def test_full_lifecycle_draft_to_active(self):
        """Test complete skill lifecycle from draft to active."""
        governance = create_skill_governance()
        
        # Step 1: Crystallize pattern into draft skill
        pattern_data = {
            "pattern_id": "p_test",
            "pattern_type": "action_sequence",
            "action_template": ["search", "analyze", "summarize"],
            "frequency": 15,
            "success_rate": 0.88,
            "source_trajectories": ["t1", "t2"],
            "confidence": 0.85,
            "preconditions": {"has_topic": True},
            "postconditions": {"has_summary": True},
            "parameter_slots": ["topic"]
        }
        
        skill = governance.crystallize_pattern(pattern_data)
        assert skill is not None
        assert skill.lifecycle_stage == SkillLifecycleStage.DRAFT
        
        # Step 2: Validate the skill
        verification = SkillVerificationResult(
            passed=True,
            tests_run=10,
            tests_passed=10,
            coverage_percent=95.0,
            execution_time_ms=500
        )
        
        validated = governance.validate_skill(skill.skill_id, verification)
        assert validated is True
        
        validated_skill = governance.registry.get(skill.skill_id)
        assert validated_skill.lifecycle_stage == SkillLifecycleStage.VALIDATED
        
        # Step 3: Activate the skill
        activated = governance.activate_skill(skill.skill_id)
        assert activated is True
        
        active_skill = governance.registry.get(skill.skill_id)
        assert active_skill.lifecycle_stage == SkillLifecycleStage.ACTIVE
        assert active_skill.version.major == 1  # Bumped from 0.x to 1.0
    
    def test_recommendation_integration(self):
        """Test recommendation with crystallized and activated skills."""
        governance = create_skill_governance()
        
        # Crystallize and activate skills
        for domain in ["research", "coding"]:
            pattern_data = {
                "pattern_id": f"p_{domain}",
                "pattern_type": "action_sequence",
                "action_template": [f"{domain}_action"],
                "frequency": 10,
                "success_rate": 0.9,
                "source_trajectories": ["t1"],
                "confidence": 0.85,
                "preconditions": {},
                "postconditions": {},
                "parameter_slots": []
            }
            
            skill = governance.crystallize_pattern(pattern_data)
            
            # Validate and activate
            verification = SkillVerificationResult(
                passed=True,
                tests_run=5,
                tests_passed=5,
                coverage_percent=90.0,
                execution_time_ms=100
            )
            governance.validate_skill(skill.skill_id, verification)
            governance.activate_skill(skill.skill_id)
        
        # Test recommendation
        context = {"domain": "research"}
        recommendations = governance.recommend_skills(context, top_k=5)
        
        assert len(recommendations) > 0
        assert any(r.skill_id.startswith("skill_") for r in recommendations)
    
    def test_execution_tracking(self):
        """Test skill execution tracking and statistics."""
        governance = create_skill_governance()
        
        # Create and activate a skill
        pattern_data = {
            "pattern_id": "p_track",
            "pattern_type": "action_sequence",
            "action_template": ["trackable_action"],
            "frequency": 10,
            "success_rate": 0.9,
            "source_trajectories": ["t1"],
            "confidence": 0.85,
            "preconditions": {},
            "postconditions": {},
            "parameter_slots": []
        }
        
        skill = governance.crystallize_pattern(pattern_data)
        governance.validate_skill(skill.skill_id, SkillVerificationResult(
            passed=True, tests_run=5, tests_passed=5,
            coverage_percent=90.0, execution_time_ms=100
        ))
        governance.activate_skill(skill.skill_id)
        
        # Record executions
        for i in range(10):
            governance.record_execution(
                skill.skill_id,
                success=(i < 8),  # 8 successes, 2 failures
                context={"task": f"task_{i}"}
            )
        
        # Check updated statistics
        updated_skill = governance.registry.get(skill.skill_id)
        assert updated_skill.usage_count == 10
        assert updated_skill.success_count == 8
        assert updated_skill.failure_count == 2
        assert updated_skill.success_rate == 0.8
    
    def test_evolution_proposal_integration(self):
        """Test evolution proposal with governance system."""
        governance = create_skill_governance()
        
        # Create base skill
        pattern_data = {
            "pattern_id": "p_base",
            "pattern_type": "action_sequence",
            "action_template": ["step1"],
            "frequency": 10,
            "success_rate": 0.75,
            "source_trajectories": ["t1"],
            "confidence": 0.8,
            "preconditions": {},
            "postconditions": {},
            "parameter_slots": []
        }
        
        skill = governance.crystallize_pattern(pattern_data)
        governance.validate_skill(skill.skill_id, SkillVerificationResult(
            passed=True, tests_run=5, tests_passed=5,
            coverage_percent=90.0, execution_time_ms=100
        ))
        governance.activate_skill(skill.skill_id)
        
        # Simulate learning better pattern
        new_patterns = [{
            "pattern_id": "p_better",
            "pattern_type": "action_sequence",
            "action_template": ["step1", "step2"],  # Extended
            "success_rate": 0.95  # Better
        }]
        
        proposal = governance.propose_evolution(skill.skill_id, new_patterns)
        
        assert proposal is not None
        assert proposal.change_type in ["minor", "patch"]  # Extension could be minor or patch
    
    def test_get_stats(self):
        """Test statistics generation."""
        governance = create_skill_governance()
        
        # Create some skills
        for i in range(3):
            pattern_data = {
                "pattern_id": f"p_{i}",
                "pattern_type": "action_sequence",
                "action_template": [f"action_{i}"],
                "frequency": 10,
                "success_rate": 0.9,
                "source_trajectories": ["t1"],
                "confidence": 0.85,
                "preconditions": {},
                "postconditions": {},
                "parameter_slots": []
            }
            governance.crystallize_pattern(pattern_data)
        
        stats = governance.get_stats()
        
        assert stats["registry"]["total_skills"] == 3
        assert stats["registry"]["by_stage"]["draft"] == 3
        assert stats["crystallizations"] == 3
    
    def test_validation_failure(self):
        """Test skill validation failure path."""
        governance = create_skill_governance()
        
        pattern_data = {
            "pattern_id": "p_fail",
            "pattern_type": "action_sequence",
            "action_template": ["fail_action"],
            "frequency": 5,
            "success_rate": 0.6,
            "source_trajectories": ["t1"],
            "confidence": 0.7,
            "preconditions": {},
            "postconditions": {},
            "parameter_slots": []
        }
        
        skill = governance.crystallize_pattern(pattern_data)
        
        # Failed validation
        verification = SkillVerificationResult(
            passed=False,
            tests_run=10,
            tests_passed=2,
            coverage_percent=20.0,
            execution_time_ms=1000,
            errors=["Test failure 1", "Test failure 2"]
        )
        
        validated = governance.validate_skill(skill.skill_id, verification)
        assert validated is False
        
        skill = governance.registry.get(skill.skill_id)
        assert skill.lifecycle_stage == SkillLifecycleStage.BROKEN


# ==================== TESTS: Edge Cases ====================

class TestEdgeCases:
    """Edge case and error handling tests."""
    
    def test_empty_registry_recommendation(self):
        """Test recommendation with empty registry."""
        governance = create_skill_governance()
        
        recommendations = governance.recommend_skills({"domain": "test"})
        assert len(recommendations) == 0
    
    def test_invalid_skill_retrieval(self):
        """Test retrieving non-existent skill."""
        registry = SkillRegistry()
        
        skill = registry.get("nonexistent")
        assert skill is None
    
    def test_invalid_stage_update(self):
        """Test updating stage of non-existent skill."""
        registry = SkillRegistry()
        
        result = registry.update_stage("nonexistent", SkillLifecycleStage.ACTIVE)
        assert result is False
    
    def test_skill_maturity_calculation(self):
        """Test maturity score calculation."""
        skill = CrystallizedSkill(
            skill_id="mature_test",
            name="Mature Test",
            description="Test",
            skill_type=SkillType.ATOMIC,
            lifecycle_stage=SkillLifecycleStage.ACTIVE,
            derived_from_patterns=[],
            extracted_from_trajectories=[],
            action_template=[],
            parameter_schema={},
            preconditions={},
            postconditions={},
            required_tools=[],
            version=SkillVersion(2, 0, 0),  # Major version 2
            usage_count=150,  # High usage
            success_count=135  # 90% success
        )
        
        maturity = skill.maturity_score
        
        # Should be fairly mature
        assert maturity > 0.5
        assert maturity <= 1.0
    
    def test_skill_version_bumping(self):
        """Test version bumping logic."""
        v = SkillVersion(1, 2, 3)
        
        patch = v.bump_patch()
        assert str(patch) == "1.2.4"
        
        minor = v.bump_minor()
        assert str(minor) == "1.3.0"
        
        major = v.bump_major()
        assert str(major) == "2.0.0"


# Run all tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
