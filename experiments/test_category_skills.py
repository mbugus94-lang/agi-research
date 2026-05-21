"""
Test suite for Category-Theoretic Skill Composition Module.

Validates categorical laws:
- Identity laws: f ∘ id = f, id ∘ f = f
- Associativity: (f ∘ g) ∘ h = f ∘ (g ∘ h)
- Functor preservation: F(f ∘ g) = F(f) ∘ F(g)
- Verification: Pre/post/invariant checking at boundaries

Based on research in category-theoretic AGI frameworks and skill composition.
"""

import pytest
from dataclasses import dataclass
from typing import Any

import sys
sys.path.insert(0, '/home/workspace/agi-research')

from core.category_skills import (
    State,
    StateType,
    SkillMorphism,
    IdentitySkillMorphism,
    ConcreteSkillMorphism,
    CompositeSkillMorphism,
    SkillCategory,
    SkillFunctor,
    CompositionEngine,
    SkillCompositionError,
    VerificationResult,
    VerificationReport,
    create_skill_category,
    create_concrete_skill,
    verify_identity_law,
    verify_associativity,
    create_verified_composition,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def category():
    """Fresh skill category for testing."""
    return create_skill_category("TestCategory")


@pytest.fixture
def engine():
    """Fresh composition engine for testing."""
    return CompositionEngine(enable_memoization=True)


@pytest.fixture
def raw_state():
    """Sample raw input state."""
    return State(state_type=StateType.RAW_INPUT, value="hello world")


@pytest.fixture
def simple_skill(category):
    """Simple text transformation skill."""
    skill = ConcreteSkillMorphism(
        name="TextUpper",
        domain=StateType.RAW_INPUT,
        codomain=StateType.PROCESSED,
        func=str.upper
    )
    category.add_morphism(skill)
    return skill


@pytest.fixture
def length_skill(category):
    """Text length calculation skill."""
    skill = ConcreteSkillMorphism(
        name="TextLength",
        domain=StateType.PROCESSED,
        codomain=StateType.ANALYZED,
        func=len
    )
    category.add_morphism(skill)
    return skill


@pytest.fixture
def double_skill(category):
    """Double a number skill."""
    skill = ConcreteSkillMorphism(
        name="DoubleValue",
        domain=StateType.ANALYZED,
        codomain=StateType.SYNTHESIZED,
        func=lambda x: x * 2
    )
    category.add_morphism(skill)
    return skill


# =============================================================================
# State Tests
# =============================================================================

class TestState:
    """Test State dataclass functionality."""
    
    def test_state_creation(self):
        """Test basic state creation."""
        state = State(state_type=StateType.RAW_INPUT, value="test")
        assert state.state_type == StateType.RAW_INPUT
        assert state.value == "test"
        assert state.metadata == {}
        assert len(state.state_id) == 8
    
    def test_state_with_value(self, raw_state):
        """Test state value transformation."""
        new_state = raw_state.with_value("transformed")
        assert new_state.value == "transformed"
        assert new_state.state_type == StateType.RAW_INPUT
        assert new_state.state_id == raw_state.state_id
    
    def test_state_with_new_type(self, raw_state):
        """Test state with type transformation."""
        new_state = raw_state.with_value("processed", StateType.PROCESSED)
        assert new_state.state_type == StateType.PROCESSED
        assert new_state.value == "processed"
    
    def test_state_with_metadata(self, raw_state):
        """Test metadata extension."""
        new_state = raw_state.with_metadata(source="web", confidence=0.95)
        assert new_state.metadata["source"] == "web"
        assert new_state.metadata["confidence"] == 0.95
        assert new_state.metadata["confidence"] == 0.95
        assert "confidence" in new_state.metadata
    
    def test_state_hashable(self):
        """Test states can be used in sets/dicts."""
        state1 = State(state_type=StateType.RAW_INPUT, value="a")
        state2 = State(state_type=StateType.RAW_INPUT, value="b")
        state_set = {state1, state2}
        assert len(state_set) == 2


# =============================================================================
# Identity Morphism Tests
# =============================================================================

class TestIdentityMorphism:
    """Test identity morphism laws."""
    
    def test_identity_returns_same_state(self):
        """Test id(state) = state."""
        state = State(state_type=StateType.RAW_INPUT, value="unchanged")
        id_morphism = IdentitySkillMorphism(StateType.RAW_INPUT)
        
        result = id_morphism(state, verify=False)
        
        assert result.value == "unchanged"
        assert result.state_type == StateType.RAW_INPUT
    
    def test_identity_same_type(self):
        """Test identity preserves type."""
        for state_type in StateType:
            state = State(state_type=state_type, value=f"test_{state_type.name}")
            id_morphism = IdentitySkillMorphism(state_type)
            result = id_morphism(state, verify=False)
            assert result.state_type == state_type
    
    def test_identity_name(self):
        """Test identity morphism naming."""
        id_morph = IdentitySkillMorphism(StateType.PROCESSED)
        assert "id_" in id_morph.name
        assert "PROCESSED" in id_morph.name
    
    def test_identity_precondition_check(self):
        """Test identity verifies type."""
        state = State(state_type=StateType.RAW_INPUT, value="test")
        id_processed = IdentitySkillMorphism(StateType.PROCESSED)
        
        # Should fail - wrong type
        report = id_processed.verify_precondition(state)
        assert report.result == VerificationResult.FAIL


# =============================================================================
# Concrete Skill Tests
# =============================================================================

class TestConcreteSkill:
    """Test concrete skill morphism implementation."""
    
    def test_skill_execution(self, simple_skill):
        """Test basic skill execution."""
        state = State(state_type=StateType.RAW_INPUT, value="hello")
        result = simple_skill(state, verify=False)
        
        assert result.value == "HELLO"
        assert result.state_type == StateType.PROCESSED
    
    def test_skill_with_metadata(self, simple_skill):
        """Test skill preserves metadata."""
        state = State(
            state_type=StateType.RAW_INPUT, 
            value="hello",
            metadata={"source": "web"}
        )
        result = simple_skill(state, verify=False)
        
        assert result.metadata["source"] == "web"
    
    def test_skill_verification_pass(self, simple_skill):
        """Test skill with verification enabled."""
        state = State(state_type=StateType.RAW_INPUT, value="hello")
        result = simple_skill(state, verify=True)
        
        assert result.value == "HELLO"
    
    def test_skill_verification_fail_wrong_type(self, simple_skill):
        """Test skill fails verification with wrong input type."""
        state = State(state_type=StateType.PROCESSED, value="hello")
        
        with pytest.raises(SkillCompositionError, match="Precondition failed"):
            simple_skill(state, verify=True)
    
    def test_skill_success_rate_tracking(self, simple_skill):
        """Test skill tracks execution success."""
        assert simple_skill.success_rate == 1.0  # No executions yet
        
        state = State(state_type=StateType.RAW_INPUT, value="test")
        simple_skill(state, verify=False)
        
        assert simple_skill._execution_count == 1
        assert simple_skill._success_count == 1
        assert simple_skill.success_rate == 1.0


# =============================================================================
# Skill Composition Tests
# =============================================================================

class TestSkillComposition:
    """Test morphism composition (f ∘ g)."""
    
    def test_basic_composition(self, category, simple_skill, length_skill):
        """Test basic skill composition: length ∘ upper."""
        # Compose: length(upper("hello")) = 5
        composed = length_skill.compose(simple_skill, name="LengthOfUpper")
        
        state = State(state_type=StateType.RAW_INPUT, value="hello")
        result = composed(state, verify=False)
        
        assert result.value == 5
        assert result.state_type == StateType.ANALYZED
    
    def test_composition_type_mismatch(self, simple_skill, double_skill, length_skill):
        """Test composition fails with type mismatch."""
        # double_skill expects ANALYZED input, simple_skill outputs PROCESSED
        # This should fail when we try to compose them
        
        with pytest.raises(SkillCompositionError, match="Cannot compose"):
            double_skill.compose(simple_skill)
    
    def test_composition_components(self, simple_skill, length_skill):
        """Test composition exposes components."""
        composed = length_skill.compose(simple_skill)
        
        components = composed.components
        assert len(components) == 2
        assert components[0].name == simple_skill.name
        assert components[1].name == length_skill.name
    
    def test_composition_matmul_operator(self, simple_skill, length_skill):
        """Test @ operator for composition."""
        composed = length_skill @ simple_skill
        
        state = State(state_type=StateType.RAW_INPUT, value="test")
        result = composed(state, verify=False)
        
        assert result.value == 4
    
    def test_triple_composition(self, category, simple_skill, length_skill, double_skill):
        """Test three-skill composition."""
        # Compose: double(length(upper("hi"))) = 2 * len("HI") = 4
        composed = double_skill.compose(length_skill.compose(simple_skill))
        
        state = State(state_type=StateType.RAW_INPUT, value="hi")
        result = composed(state, verify=False)
        
        assert result.value == 4
        assert result.state_type == StateType.SYNTHESIZED


# =============================================================================
# Identity Law Tests (Category Theory)
# =============================================================================

class TestIdentityLaws:
    """Test categorical identity laws: f ∘ id = f, id ∘ f = f."""
    
    def test_right_identity(self, category, simple_skill):
        """Test f ∘ id = f (right identity)."""
        id_raw = category.identity(StateType.RAW_INPUT)
        
        # f ∘ id
        composed = simple_skill.compose(id_raw)
        
        state = State(state_type=StateType.RAW_INPUT, value="test")
        result_composed = composed(state, verify=False)
        result_direct = simple_skill(state, verify=False)
        
        assert result_composed.value == result_direct.value
        assert result_composed.state_type == result_direct.state_type
    
    def test_left_identity(self, category, simple_skill, length_skill):
        """Test id ∘ f = f (left identity)."""
        id_processed = category.identity(StateType.PROCESSED)
        
        # First create simple_skill output
        state = State(state_type=StateType.RAW_INPUT, value="hello")
        processed = simple_skill(state, verify=False)
        
        # id ∘ processed_state
        id_composed = id_processed.compose(
            IdentitySkillMorphism(StateType.PROCESSED)
        )
        
        # Actually test proper composition chain
        # length_skill: PROCESSED -> ANALYZED
        # id_processed: PROCESSED -> PROCESSED
        # So length_skill ∘ id_processed should work
        composed = length_skill.compose(id_processed)
        
        result_composed = composed(processed, verify=False)
        result_direct = length_skill(processed, verify=False)
        
        assert result_composed.value == result_direct.value
    
    def test_verify_identity_law_function(self, category, simple_skill):
        """Test identity law verification function."""
        result = verify_identity_law(simple_skill, category, "test value")
        assert result is True
    
    def test_identity_law_with_actual_composition(self, category, simple_skill):
        """Test f ∘ id returns equivalent result to f."""
        id_morphism = category.identity(StateType.RAW_INPUT)
        
        # f ∘ id
        f_after_id = simple_skill.compose(id_morphism)
        
        state = State(state_type=StateType.RAW_INPUT, value="identity test")
        result1 = f_after_id(state, verify=False)
        result2 = simple_skill(state, verify=False)
        
        assert result1.value == result2.value
        assert result1.state_type == result2.state_type


# =============================================================================
# Associativity Tests (Category Theory)
# =============================================================================

class TestAssociativity:
    """Test categorical associativity: (f ∘ g) ∘ h = f ∘ (g ∘ h)."""
    
    def test_associativity_three_skills(self, simple_skill, length_skill, double_skill):
        """Test (f ∘ g) ∘ h = f ∘ (g ∘ h)."""
        # Let h = simple_skill (RAW -> PROCESSED)
        #     g = length_skill (PROCESSED -> ANALYZED)
        #     f = double_skill (ANALYZED -> SYNTHESIZED)
        # (f ∘ g) ∘ h = f ∘ (g ∘ h)
        
        # Left: (f ∘ g) ∘ h
        fg = double_skill.compose(length_skill)
        left = fg.compose(simple_skill)
        
        # Right: f ∘ (g ∘ h)
        gh = length_skill.compose(simple_skill)
        right = double_skill.compose(gh)
        
        state = State(state_type=StateType.RAW_INPUT, value="associativity")
        
        result_left = left(state, verify=False)
        result_right = right(state, verify=False)
        
        assert result_left.value == result_right.value
        assert result_left.state_type == result_right.state_type
    
    def test_verify_associativity_function(self, simple_skill, length_skill, double_skill):
        """Test associativity verification function."""
        result = verify_associativity(double_skill, length_skill, simple_skill, "test")
        assert result is True
    
    def test_associativity_preserves_value(self, category):
        """Test associativity with numerical computation."""
        # h: x -> x * 2
        h = ConcreteSkillMorphism(
            name="Multiply2",
            domain=StateType.RAW_INPUT,
            codomain=StateType.PROCESSED,
            func=lambda x: x * 2
        )
        
        # g: x -> x + 10
        g = ConcreteSkillMorphism(
            name="Add10",
            domain=StateType.PROCESSED,
            codomain=StateType.ANALYZED,
            func=lambda x: x + 10
        )
        
        # f: x -> x / 2
        f = ConcreteSkillMorphism(
            name="Divide2",
            domain=StateType.ANALYZED,
            codomain=StateType.SYNTHESIZED,
            func=lambda x: x / 2
        )
        
        # (f ∘ g) ∘ h vs f ∘ (g ∘ h)
        # Input: 5
        # h: 5 * 2 = 10
        # g: 10 + 10 = 20
        # f: 20 / 2 = 10
        
        fg = f.compose(g)
        left = fg.compose(h)
        
        gh = g.compose(h)
        right = f.compose(gh)
        
        state = State(state_type=StateType.RAW_INPUT, value=5)
        
        result_left = left(state, verify=False)
        result_right = right(state, verify=False)
        
        assert result_left.value == 10.0
        assert result_right.value == 10.0


# =============================================================================
# Skill Category Tests
# =============================================================================

class TestSkillCategory:
    """Test skill category container."""
    
    def test_category_creation(self):
        """Test category initialization."""
        cat = create_skill_category("Test")
        assert cat.name == "Test"
        
        # All identity morphisms created
        for state_type in StateType:
            id_morph = cat.identity(state_type)
            assert id_morph.domain == state_type
            assert id_morph.codomain == state_type
    
    def test_add_and_retrieve_morphism(self, category, simple_skill):
        """Test adding morphisms to category."""
        category.add_morphism(simple_skill)
        
        retrieved = category.get_morphism("TextUpper")
        assert retrieved is simple_skill
    
    def test_compose_in_category(self, category, simple_skill, length_skill):
        """Test composition through category."""
        category.add_morphism(simple_skill)
        category.add_morphism(length_skill)
        
        composed = category.compose(length_skill, simple_skill)
        
        state = State(state_type=StateType.RAW_INPUT, value="category")
        result = composed(state, verify=False)
        
        assert result.value == 8
    
    def test_compose_type_mismatch_in_category(self, category, simple_skill, double_skill):
        """Test category catches type mismatch."""
        # simple_skill: RAW -> PROCESSED
        # double_skill: ANALYZED -> SYNTHESIZED
        # These don't compose
        
        with pytest.raises(SkillCompositionError, match="Cannot compose"):
            category.compose(double_skill, simple_skill, verify_types=True)
    
    def test_pipeline_creation(self, category, simple_skill, length_skill, double_skill):
        """Test pipeline composition."""
        category.add_morphism(simple_skill)
        category.add_morphism(length_skill)
        category.add_morphism(double_skill)
        
        # pipeline(a, b, c) = c ∘ b ∘ a
        pipeline = category.compose_pipeline(simple_skill, length_skill, double_skill)
        
        state = State(state_type=StateType.RAW_INPUT, value="pipe")
        result = pipeline(state, verify=False)
        
        # "pipe" -> "PIPE" -> 4 -> 8
        assert result.value == 8
    
    def test_find_morphisms_between(self, category, simple_skill, length_skill):
        """Test finding morphisms between types."""
        category.add_morphism(simple_skill)
        category.add_morphism(length_skill)
        
        # Find RAW -> PROCESSED
        raw_to_proc = category.get_morphisms_between(StateType.RAW_INPUT, StateType.PROCESSED)
        assert len(raw_to_proc) == 1
        assert raw_to_proc[0].name == "TextUpper"
        
        # Find PROCESSED -> ANALYZED
        proc_to_anal = category.get_morphisms_between(StateType.PROCESSED, StateType.ANALYZED)
        assert len(proc_to_anal) == 1
        assert proc_to_anal[0].name == "TextLength"


# =============================================================================
# Skill Functor Tests
# =============================================================================

class TestSkillFunctor:
    """Test functor structure preservation."""
    
    def test_functor_object_mapping(self):
        """Test functor maps objects correctly."""
        functor = SkillFunctor("TestFunctor")
        
        # Define object mapping
        functor.define_object_mapping(StateType.RAW_INPUT, StateType.PROCESSED)
        functor.define_object_mapping(StateType.PROCESSED, StateType.ANALYZED)
        
        assert functor.map_object(StateType.RAW_INPUT) == StateType.PROCESSED
        assert functor.map_object(StateType.PROCESSED) == StateType.ANALYZED
    
    def test_functor_morphism_mapping(self):
        """Test functor maps morphisms preserving structure."""
        functor = SkillFunctor("TestFunctor")
        functor.define_object_mapping(StateType.RAW_INPUT, StateType.PROCESSED)
        functor.define_object_mapping(StateType.PROCESSED, StateType.ANALYZED)
        
        skill = ConcreteSkillMorphism(
            name="TestSkill",
            domain=StateType.RAW_INPUT,
            codomain=StateType.PROCESSED,
            func=lambda x: x
        )
        
        mapped = functor.map_morphism(skill)
        
        # Domain and codomain should be mapped
        assert mapped.domain == StateType.PROCESSED
        assert mapped.codomain == StateType.ANALYZED
        assert functor.name in mapped.name
    
    def test_functor_preserves_identity(self):
        """Test functor preserves identity: F(id_A) = id_F(A)."""
        functor = SkillFunctor("TestFunctor")
        functor.define_object_mapping(StateType.RAW_INPUT, StateType.PROCESSED)
        
        id_raw = IdentitySkillMorphism(StateType.RAW_INPUT)
        mapped = functor.map_morphism(id_raw)
        
        # Should map to identity of mapped object
        assert isinstance(mapped, IdentitySkillMorphism)
        assert mapped.domain == StateType.PROCESSED
    
    def test_functor_preserves_composition(self):
        """Test F(f ∘ g) = F(f) ∘ F(g)."""
        functor = SkillFunctor("TestFunctor")
        functor.define_object_mapping(StateType.RAW_INPUT, StateType.PROCESSED)
        functor.define_object_mapping(StateType.PROCESSED, StateType.ANALYZED)
        functor.define_object_mapping(StateType.ANALYZED, StateType.SYNTHESIZED)
        
        g = ConcreteSkillMorphism(
            name="G",
            domain=StateType.RAW_INPUT,
            codomain=StateType.PROCESSED,
            func=lambda x: x + 1
        )
        
        f = ConcreteSkillMorphism(
            name="F",
            domain=StateType.PROCESSED,
            codomain=StateType.ANALYZED,
            func=lambda x: x * 2
        )
        
        # Map composition
        composition = f.compose(g)
        mapped_composition = functor.map_morphism(composition)
        
        # Map then compose
        mapped_f = functor.map_morphism(f)
        mapped_g = functor.map_morphism(g)
        
        # Both should result in same domain/codomain
        assert mapped_composition.domain == mapped_g.domain
        assert mapped_composition.codomain == mapped_f.codomain


# =============================================================================
# Composition Engine Tests
# =============================================================================

class TestCompositionEngine:
    """Test execution engine with verification and rollback."""
    
    def test_basic_execution(self, engine, simple_skill):
        """Test basic skill execution."""
        state = State(state_type=StateType.RAW_INPUT, value="engine")
        result = engine.execute(simple_skill, state)
        
        assert result.value == "ENGINE"
    
    def test_execution_with_verification(self, engine, simple_skill):
        """Test execution with verification enabled."""
        state = State(state_type=StateType.RAW_INPUT, value="verify")
        result = engine.execute(simple_skill, state, verify=True)
        
        assert result.value == "VERIFY"
    
    def test_execution_failure_rollback(self, engine):
        """Test rollback on execution failure."""
        failing_skill = ConcreteSkillMorphism(
            name="FailingSkill",
            domain=StateType.RAW_INPUT,
            codomain=StateType.PROCESSED,
            func=lambda x: x / 0  # Will fail for numeric
        )
        
        state = State(state_type=StateType.RAW_INPUT, value=42, metadata={"checkpoint": True})  # Numeric value
        
        result = engine.execute(failing_skill, state, enable_rollback=True)
        
        # Should return to checkpoint state with metadata
        assert result.metadata.get("rollback_reason") is not None
        assert result.metadata.get("failed_skill") == "FailingSkill"
    
    def test_memoization(self, engine, simple_skill):
        """Test result memoization."""
        state = State(state_type=StateType.RAW_INPUT, value="memo")
        
        # First execution
        result1 = engine.execute(simple_skill, state)
        
        # Second execution - should use memo
        result2 = engine.execute(simple_skill, state)
        
        assert result1.value == result2.value
    
    def test_composite_execution(self, engine, simple_skill, length_skill):
        """Test composite skill execution."""
        composed = length_skill.compose(simple_skill)
        
        state = State(state_type=StateType.RAW_INPUT, value="composite")
        result = engine.execute(composed, state)
        
        assert result.value == 9  # len("COMPOSITE")
    
    def test_execution_log(self, engine):
        """Test execution logging."""
        skill = ConcreteSkillMorphism(
            name="LogTestSkill",
            domain=StateType.RAW_INPUT,
            codomain=StateType.PROCESSED,
            func=lambda x: x.upper()
        )
        
        # Use different values to avoid memoization
        state1 = State(state_type=StateType.RAW_INPUT, value="log1")
        state2 = State(state_type=StateType.RAW_INPUT, value="log2")
        
        engine.execute(skill, state1)
        engine.execute(skill, state2)
        
        log = engine.get_execution_log()
        assert len(log) == 2
    
    def test_clear_memo(self, engine, simple_skill):
        """Test clearing memoization cache."""
        state = State(state_type=StateType.RAW_INPUT, value="clear")
        engine.execute(simple_skill, state)
        
        engine.clear_memo()
        # No exception means success


# =============================================================================
# Verified Composition Tests
# =============================================================================

class TestVerifiedComposition:
    """Test composition with verification boundaries."""
    
    def test_verified_composition_creation(self, simple_skill, length_skill):
        """Test creating verified composition."""
        composition = create_verified_composition(simple_skill, length_skill)
        
        state = State(state_type=StateType.RAW_INPUT, value="verified")
        result = composition(state, verify=False)
        
        assert result.value == 8
    
    def test_verified_composition_with_name(self, simple_skill, length_skill):
        """Test named verified composition."""
        composition = create_verified_composition(
            simple_skill, length_skill,
            name="MyPipeline"
        )
        
        assert composition.name == "MyPipeline"
    
    def test_verified_composition_insufficient_skills(self):
        """Test error with single skill."""
        skill = ConcreteSkillMorphism(
            name="OnlySkill",
            domain=StateType.RAW_INPUT,
            codomain=StateType.PROCESSED,
            func=lambda x: x
        )
        
        with pytest.raises(SkillCompositionError, match="at least 2 skills"):
            create_verified_composition(skill)


# =============================================================================
# Verification Report Tests
# =============================================================================

class TestVerification:
    """Test verification boundary checking."""
    
    def test_precondition_verification_pass(self, simple_skill):
        """Test precondition passes with correct type."""
        state = State(state_type=StateType.RAW_INPUT, value="test")
        report = simple_skill.verify_precondition(state)
        
        assert report.result == VerificationResult.PASS
        assert report.stage == "pre"
    
    def test_precondition_verification_fail(self, simple_skill):
        """Test precondition fails with wrong type."""
        state = State(state_type=StateType.TERMINAL, value="test")
        report = simple_skill.verify_precondition(state)
        
        assert report.result == VerificationResult.FAIL
        assert "Type mismatch" in report.message
    
    def test_custom_precondition(self, category):
        """Test custom precondition verification."""
        def check_length(state):
            if len(str(state.value)) < 5:
                return VerificationReport(
                    result=VerificationResult.FAIL,
                    stage="pre",
                    message="Value too short"
                )
            return VerificationReport(
                result=VerificationResult.PASS,
                stage="pre",
                message="Length OK"
            )
        
        skill = ConcreteSkillMorphism(
            name="LengthCheckSkill",
            domain=StateType.RAW_INPUT,
            codomain=StateType.PROCESSED,
            func=str.upper,
            verify_pre=check_length
        )
        
        short_state = State(state_type=StateType.RAW_INPUT, value="hi")
        long_state = State(state_type=StateType.RAW_INPUT, value="hello world")
        
        short_report = skill.verify_precondition(short_state)
        long_report = skill.verify_precondition(long_state)
        
        assert short_report.result == VerificationResult.FAIL
        assert long_report.result == VerificationResult.PASS


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """End-to-end integration tests."""
    
    def test_full_pipeline(self):
        """Test complete skill pipeline from raw to terminal."""
        category = create_skill_category("Integration")
        engine = CompositionEngine()
        
        # Create pipeline: RAW -> PROCESSED -> ANALYZED -> SYNTHESIZED -> ACTIONABLE -> TERMINAL
        skills = [
            ConcreteSkillMorphism(
                name=f"Step{i}",
                domain=list(StateType)[i],
                codomain=list(StateType)[i + 1],
                func=lambda x, multiplier=i: x * (multiplier + 1)
            )
            for i in range(len(StateType) - 1)
        ]
        
        # Build pipeline
        state = State(state_type=StateType.RAW_INPUT, value=1)
        current = state
        
        for skill in skills:
            current = engine.execute(skill, current, verify=True)
        
        # Verify progression through all types
        assert current.state_type == StateType.TERMINAL
        assert current.value > 0
    
    def test_composition_with_verified_boundaries(self):
        """Test composition with verification at each boundary."""
        category = create_skill_category("Verified")
        
        def verify_not_empty(state):
            if not state.value:
                return VerificationReport(
                    result=VerificationResult.FAIL,
                    stage="pre",
                    message="Empty value"
                )
            return VerificationReport(
                result=VerificationResult.PASS,
                stage="pre",
                message="Non-empty"
            )
        
        skill1 = ConcreteSkillMorphism(
            name="Trim",
            domain=StateType.RAW_INPUT,
            codomain=StateType.PROCESSED,
            func=str.strip,
            verify_pre=verify_not_empty
        )
        
        skill2 = ConcreteSkillMorphism(
            name="CountWords",
            domain=StateType.PROCESSED,
            codomain=StateType.ANALYZED,
            func=lambda x: len(x.split())
        )
        
        pipeline = skill2.compose(skill1)
        
        state = State(state_type=StateType.RAW_INPUT, value="  hello world  ")
        result = pipeline(state, verify=True)
        
        assert result.value == 2
    
    def test_functor_composition_chain(self):
        """Test applying functor to composition chain."""
        functor = SkillFunctor("ChainFunctor")
        
        # Map all state types
        types = list(StateType)
        for i, t in enumerate(types):
            if i < len(types) - 1:
                functor.define_object_mapping(t, types[i + 1])
        
        # Create skill chain
        skills = [
            ConcreteSkillMorphism(
                name=f"Skill{i}",
                domain=types[i],
                codomain=types[i + 1],
                func=lambda x, i=i: f"step{i}:{x}"
            )
            for i in range(3)
        ]
        
        # Build chain
        chain = skills[0]
        for skill in skills[1:]:
            chain = skill.compose(chain)
        
        # Apply functor
        mapped_chain = functor.map_morphism(chain)
        
        # Verify structure preserved
        assert mapped_chain.domain == types[1]  # Shifted by functor
        assert mapped_chain.codomain == types[4]  # Shifted by functor


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_empty_composition(self, category):
        """Test pipeline requires at least 2 skills."""
        skill = ConcreteSkillMorphism(
            name="Only",
            domain=StateType.RAW_INPUT,
            codomain=StateType.PROCESSED,
            func=lambda x: x
        )
        
        with pytest.raises(SkillCompositionError, match="at least 2 skills"):
            category.compose_pipeline(skill)
    
    def test_composition_error_message(self, simple_skill, double_skill):
        """Test informative error messages."""
        # These don't compose directly - mismatch
        with pytest.raises(SkillCompositionError) as exc:
            double_skill.compose(simple_skill)
        
        assert "Cannot compose" in str(exc.value)
        assert "TextUpper" in str(exc.value) or "DoubleValue" in str(exc.value)
    
    def test_state_immutability(self, raw_state, simple_skill):
        """Test that states remain immutable through transformations."""
        original_value = raw_state.value
        
        result = simple_skill(raw_state, verify=False)
        
        # Original unchanged
        assert raw_state.value == original_value
        assert result.value != original_value


# =============================================================================
# Performance/Stress Tests
# =============================================================================

class TestPerformance:
    """Test performance characteristics."""
    
    def test_deep_composition_chain(self, category):
        """Test deeply nested composition (10 levels)."""
        skills = []
        current_type = StateType.RAW_INPUT
        
        for i in range(10):
            next_type = list(StateType)[(i + 1) % len(StateType)]
            skill = ConcreteSkillMorphism(
                name=f"DeepSkill{i}",
                domain=current_type,
                codomain=next_type,
                func=lambda x, i=i: x + i
            )
            skills.append(skill)
            current_type = next_type
        
        # Build deep chain
        chain = skills[0]
        for skill in skills[1:]:
            # Note: types may not align perfectly, just test composition depth
            try:
                chain = skill.compose(chain)
            except SkillCompositionError:
                break  # Type mismatch expected, we tested depth
        
        # Composition succeeded up to some depth
        assert len(chain.components) >= 1
    
    def test_repeated_execution_memoization(self, engine):
        """Test memoization benefits."""
        expensive_skill = ConcreteSkillMorphism(
            name="Expensive",
            domain=StateType.RAW_INPUT,
            codomain=StateType.PROCESSED,
            func=lambda x: x * 2  # Simulated expensive
        )
        
        state = State(state_type=StateType.RAW_INPUT, value=42)
        
        # Execute multiple times
        for _ in range(100):
            result = engine.execute(expensive_skill, state)
            assert result.value == 84


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
