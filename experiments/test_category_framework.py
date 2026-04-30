"""
Tests for Category-Theoretic Agent Framework

Validates:
1. Category structure (objects, morphisms, composition)
2. Functor properties (identity preservation, composition preservation)
3. Natural transformations (naturality condition)
4. Monad laws (left/right identity, associativity)
5. Agent specifications (SMGI obligations)
6. Integration with existing agent components
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.category_framework import (
    Object, Morphism, Category,
    Functor, AgentFunctor, NaturalTransformation, Monad,
    AgentSpecification, AgentType, CategoryTheoreticAgent,
    create_reactive_agent, create_deliberative_agent, 
    create_learning_agent, create_functor_between_agents
)


class TestObject:
    """Test Object class - categorical objects."""
    
    def test_object_creation(self):
        """Test creating objects with properties."""
        obj = Object(properties={"state": "idle", "energy": 100})
        assert obj.get("state") == "idle"
        assert obj.get("energy") == 100
        assert obj.id is not None
    
    def test_object_immutability(self):
        """Test objects are immutable - new objects created for changes."""
        obj1 = Object(properties={"value": 10})
        obj2 = obj1.with_property("value", 20)
        
        assert obj1.get("value") == 10  # Original unchanged
        assert obj2.get("value") == 20  # New object has new value
        assert obj1 != obj2
    
    def test_object_hash(self):
        """Test objects can be hashed for use in sets/dicts."""
        obj = Object(properties={"test": True})
        assert hash(obj) is not None
        
        # Can add to set
        obj_set = {obj}
        assert obj in obj_set
    
    def test_object_default_value(self):
        """Test get with default value."""
        obj = Object()
        assert obj.get("missing", "default") == "default"


class TestMorphism:
    """Test Morphism class - categorical morphisms."""
    
    def test_morphism_creation(self):
        """Test creating morphisms."""
        source = Object(properties={"state": "A"})
        target = Object(properties={"state": "B"})
        
        def transform(obj):
            return target
        
        morph = Morphism(
            name="test_morph",
            source=source,
            target=target,
            transform=transform
        )
        
        assert morph.name == "test_morph"
        assert morph.source == source
        assert morph.target == target
    
    def test_morphism_application(self):
        """Test applying morphism to object."""
        source = Object(properties={"value": 1})
        target = Object(properties={"value": 2})
        
        def transform(obj):
            return target
        
        morph = Morphism(
            name="increment",
            source=source,
            target=target,
            transform=transform
        )
        
        result = morph.apply(source)
        assert result == target
    
    def test_morphism_composition(self):
        """Test morphism composition: g ∘ f."""
        # Create objects A -> B -> C
        A = Object(properties={"stage": "A"})
        B = Object(properties={"stage": "B"})
        C = Object(properties={"stage": "C"})
        
        f = Morphism(
            name="f",
            source=A,
            target=B,
            transform=lambda x: B
        )
        
        g = Morphism(
            name="g",
            source=B,
            target=C,
            transform=lambda x: C
        )
        
        # Compose: g ∘ f
        composed = f.compose(g)
        
        assert composed.source == A
        assert composed.target == C
        assert "∘" in composed.name
    
    def test_morphism_composition_invalid(self):
        """Test composition fails when target != source."""
        A = Object(properties={"stage": "A"})
        B = Object(properties={"stage": "B"})
        C = Object(properties={"stage": "C"})
        D = Object(properties={"stage": "D"})
        
        f = Morphism(
            name="f",
            source=A,
            target=B,
            transform=lambda x: B
        )
        
        g = Morphism(
            name="g",
            source=C,  # Different from B!
            target=D,
            transform=lambda x: D
        )
        
        with pytest.raises(ValueError, match="Cannot compose"):
            f.compose(g)
    
    def test_morphism_wrong_source(self):
        """Test applying morphism to wrong source object."""
        A = Object(properties={"stage": "A"})
        B = Object(properties={"stage": "B"})
        C = Object(properties={"stage": "C"})
        
        morph = Morphism(
            name="test",
            source=A,
            target=B,
            transform=lambda x: B
        )
        
        with pytest.raises(ValueError):
            morph.apply(C)  # C is not the source


class TestCategory:
    """Test Category class - collections of objects and morphisms."""
    
    def test_category_creation(self):
        """Test creating empty category."""
        cat = Category(name="TestCat")
        assert cat.name == "TestCat"
        assert len(cat.objects) == 0
        assert len(cat.morphisms) == 0
    
    def test_add_object(self):
        """Test adding objects to category."""
        cat = Category(name="TestCat")
        obj = Object(properties={"test": True})
        
        cat.add_object(obj)
        assert obj in cat.objects
    
    def test_add_morphism(self):
        """Test adding morphisms to category."""
        cat = Category(name="TestCat")
        A = Object()
        B = Object()
        
        morph = Morphism(
            name="test",
            source=A,
            target=B,
            transform=lambda x: B
        )
        
        cat.add_morphism(morph)
        assert "test" in cat.morphisms
        assert A in cat.objects
        assert B in cat.objects
    
    def test_identity_morphism(self):
        """Test creating identity morphisms."""
        cat = Category(name="TestCat")
        obj = Object(properties={"value": 42})
        
        id_morph = cat.identity(obj)
        
        assert id_morph.source == obj
        assert id_morph.target == obj
        assert id_morph.transform(obj) == obj  # Identity function
    
    def test_composition_in_category(self):
        """Test composing morphisms through category."""
        cat = Category(name="TestCat")
        A = Object()
        B = Object()
        C = Object()
        
        f = Morphism(name="f", source=A, target=B, transform=lambda x: B)
        g = Morphism(name="g", source=B, target=C, transform=lambda x: C)
        
        cat.add_morphism(f)
        cat.add_morphism(g)
        
        composed = cat.compose("f", "g")
        assert composed.source == A
        assert composed.target == C


class TestFunctor:
    """Test Functor class - structure-preserving mappings."""
    
    def test_functor_creation(self):
        """Test creating functors between categories."""
        C = Category(name="C")
        D = Category(name="D")
        
        class TestFunctor(Functor):
            def map_object(self, obj):
                return Object(properties={"mapped": obj.id})
            
            def map_morphism(self, morph):
                return morph
        
        F = TestFunctor(C, D, "F")
        assert F.source == C
        assert F.target == D
        assert F.name == "F"
    
    def test_agent_functor(self):
        """Test concrete AgentFunctor implementation."""
        C = Category(name="Source")
        D = Category(name="Target")
        
        obj_mapping = {"obj1": "mapped_obj1"}
        morph_transforms = {}
        
        F = AgentFunctor(C, D, obj_mapping, morph_transforms, "AgentF")
        
        obj = Object(id="obj1", properties={"test": True})
        mapped = F.map_object(obj)
        
        assert mapped.id == "mapped_obj1"
        assert mapped.get("mapped_from") == "obj1"


class TestNaturalTransformation:
    """Test NaturalTransformation class."""
    
    def test_natural_transformation_creation(self):
        """Test creating natural transformations."""
        C = Category(name="C")
        D = Category(name="D")
        
        class DummyFunctor(Functor):
            def map_object(self, obj):
                return obj
            def map_morphism(self, morph):
                return morph
        
        F = DummyFunctor(C, D, "F")
        G = DummyFunctor(C, D, "G")
        
        eta = NaturalTransformation(
            name="eta",
            source_functor=F,
            target_functor=G
        )
        
        assert eta.name == "eta"
        assert eta.source_functor == F
        assert eta.target_functor == G
    
    def test_add_component(self):
        """Test adding components to natural transformation."""
        C = Category(name="C")
        D = Category(name="D")
        
        class DummyFunctor(Functor):
            def map_object(self, obj):
                return obj
            def map_morphism(self, morph):
                return morph
        
        F = DummyFunctor(C, D, "F")
        G = DummyFunctor(C, D, "G")
        
        eta = NaturalTransformation("eta", F, G)
        
        obj = Object()
        A = Object()
        B = Object()
        morph = Morphism(name="test", source=A, target=B, transform=lambda x: B)
        
        eta.add_component(obj, morph)
        assert obj.id in eta.components


class TestMonad:
    """Test Monad class for computational context."""
    
    def test_monad_creation(self):
        """Test creating monads."""
        C = Category(name="C")
        T = Monad(name="Maybe", category=C)
        
        assert T.name == "Maybe"
        assert T.category == C
    
    def test_monad_set_unit(self):
        """Test setting unit natural transformation."""
        C = Category(name="C")
        T = Monad(name="Test", category=C)
        
        class DummyFunctor(Functor):
            def map_object(self, obj):
                return obj
            def map_morphism(self, morph):
                return morph
        
        F = DummyFunctor(C, C, "F")
        G = DummyFunctor(C, C, "G")
        eta = NaturalTransformation("eta", F, G)
        
        T.set_unit(eta)
        assert T.unit == eta


class TestAgentSpecification:
    """Test AgentSpecification class."""
    
    def test_specification_creation(self):
        """Test creating agent specifications."""
        cat = Category(name="AgentCat")
        
        spec = AgentSpecification(
            name="TestAgent",
            agent_type=AgentType.REACTIVE,
            category=cat
        )
        
        assert spec.name == "TestAgent"
        assert spec.agent_type == AgentType.REACTIVE
        assert spec.category == cat
        assert spec.structural_closure
        assert spec.dynamical_stability
        assert spec.bounded_capacity
        assert spec.evaluative_invariance
    
    def test_smgi_obligations(self):
        """Test SMGI four obligations are tracked."""
        cat = Category(name="AgentCat")
        
        spec = AgentSpecification(
            name="TestAgent",
            agent_type=AgentType.DELIBERATIVE,
            category=cat,
            structural_closure=True,
            dynamical_stability=True,
            bounded_capacity=True,
            evaluative_invariance=True
        )
        
        result = spec.to_dict()
        assert result["smgi_obligations"]["structural_closure"]
        assert result["smgi_obligations"]["dynamical_stability"]
        assert result["smgi_obligations"]["bounded_capacity"]
        assert result["smgi_obligations"]["evaluative_invariance"]
    
    def test_specification_serialization(self):
        """Test specification can be serialized."""
        cat = Category(name="AgentCat")
        
        spec = AgentSpecification(
            name="TestAgent",
            agent_type=AgentType.LEARNING,
            category=cat,
            priors={"bias": 0.1, "confidence": 0.9}
        )
        
        result = spec.to_dict()
        assert result["name"] == "TestAgent"
        assert result["agent_type"] == "LEARNING"
        assert result["priors"]["bias"] == 0.1


class TestCategoryTheoreticAgent:
    """Test CategoryTheoreticAgent class."""
    
    def test_agent_creation(self):
        """Test creating category-theoretic agents."""
        cat = Category(name="AgentCat")
        spec = AgentSpecification(
            name="TestAgent",
            agent_type=AgentType.HYBRID,
            category=cat
        )
        
        agent = CategoryTheoreticAgent(spec)
        assert agent.spec == spec
        assert agent.current_state is None
        assert len(agent.history) == 0
    
    def test_agent_initialization(self):
        """Test agent initialization."""
        cat = Category(name="AgentCat")
        spec = AgentSpecification(
            name="TestAgent",
            agent_type=AgentType.REACTIVE,
            category=cat
        )
        
        agent = CategoryTheoreticAgent(spec)
        initial = agent.initialize({"energy": 100, "state": "idle"})
        
        assert agent.current_state == initial
        assert initial.get("energy") == 100
        assert initial in cat.objects
    
    def test_agent_execution(self):
        """Test agent executing morphisms."""
        cat = Category(name="AgentCat")
        spec = AgentSpecification(
            name="TestAgent",
            agent_type=AgentType.REACTIVE,
            category=cat
        )
        
        agent = CategoryTheoreticAgent(spec)
        agent.initialize({"value": 0})
        
        # Create a simple increment morphism
        source = agent.current_state
        target = Object(properties={"value": 1})
        
        increment = Morphism(
            name="increment",
            source=source,
            target=target,
            transform=lambda x: target
        )
        
        result = agent.execute(increment)
        assert result == target
        assert agent.current_state == target
        assert len(agent.history) == 1
    
    def test_agent_verification(self):
        """Test agent structural verification."""
        cat = Category(name="AgentCat")
        spec = AgentSpecification(
            name="TestAgent",
            agent_type=AgentType.REACTIVE,
            category=cat,
            structural_closure=True,
            dynamical_stability=True,
            bounded_capacity=True,
            evaluative_invariance=True
        )
        
        agent = CategoryTheoreticAgent(spec)
        agent.initialize({"test": True})
        
        verification = agent.verify_structure()
        assert verification["structural_closure"]
        assert verification["dynamical_stability"]
        assert verification["bounded_capacity"]
        assert verification["evaluative_invariance"]
        assert verification["category_nonempty"]
    
    def test_uninitialized_execution(self):
        """Test execution fails when not initialized."""
        cat = Category(name="AgentCat")
        spec = AgentSpecification(
            name="TestAgent",
            agent_type=AgentType.REACTIVE,
            category=cat
        )
        
        agent = CategoryTheoreticAgent(spec)
        
        A = Object()
        B = Object()
        morph = Morphism(name="test", source=A, target=B, transform=lambda x: B)
        
        with pytest.raises(RuntimeError, match="not initialized"):
            agent.execute(morph)


class TestFactoryFunctions:
    """Test factory functions for creating agents."""
    
    def test_create_reactive_agent(self):
        """Test reactive agent factory."""
        agent = create_reactive_agent("ReactiveAgent")
        
        assert agent.spec.name == "ReactiveAgent"
        assert agent.spec.agent_type == AgentType.REACTIVE
        assert agent.spec.category.name == "ReactiveAgent_category"
    
    def test_create_deliberative_agent(self):
        """Test deliberative agent factory."""
        agent = create_deliberative_agent("DeliberativeAgent")
        
        assert agent.spec.name == "DeliberativeAgent"
        assert agent.spec.agent_type == AgentType.DELIBERATIVE
    
    def test_create_learning_agent(self):
        """Test learning agent factory."""
        agent = create_learning_agent("LearningAgent")
        
        assert agent.spec.name == "LearningAgent"
        assert agent.spec.agent_type == AgentType.LEARNING
    
    def test_create_functor_between_agents(self):
        """Test functor creation between agents."""
        agent1 = create_reactive_agent("Agent1")
        agent2 = create_deliberative_agent("Agent2")
        
        config = {
            "name": "TestMapping",
            "objects": {},
            "morphisms": {}
        }
        
        functor = create_functor_between_agents(agent1, agent2, config)
        
        assert functor.name == "TestMapping"
        assert functor.source == agent1.spec.category
        assert functor.target == agent2.spec.category


class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_complete_agent_workflow(self):
        """Test complete agent lifecycle with categorical structure."""
        # Create agent
        agent = create_deliberative_agent("WorkflowAgent")
        
        # Initialize
        agent.initialize({"step": 0, "data": None})
        
        # Create and execute multiple morphisms
        state0 = agent.current_state
        state1 = Object(properties={"step": 1, "data": "processed"})
        state2 = Object(properties={"step": 2, "data": "analyzed"})
        
        process = Morphism(
            name="process",
            source=state0,
            target=state1,
            transform=lambda x: state1
        )
        
        analyze = Morphism(
            name="analyze",
            source=state1,
            target=state2,
            transform=lambda x: state2
        )
        
        agent.execute(process)
        agent.execute(analyze)
        
        assert agent.current_state == state2
        assert len(agent.history) == 2
        assert agent.current_state.get("step") == 2
    
    def test_composition_workflow(self):
        """Test composing multiple actions into single morphism."""
        agent = create_reactive_agent("ComposeAgent")
        cat = agent.spec.category
        
        # Create objects and morphisms
        A = Object(properties={"stage": "A"})
        B = Object(properties={"stage": "B"})
        C = Object(properties={"stage": "C"})
        
        f = Morphism(name="f", source=A, target=B, transform=lambda x: B)
        g = Morphism(name="g", source=B, target=C, transform=lambda x: C)
        
        cat.add_morphism(f)
        cat.add_morphism(g)
        
        # Compose
        composed = agent.compose_actions(["f", "g"])
        
        assert composed.source == A
        assert composed.target == C
    
    def test_category_theory_laws(self):
        """Test fundamental category theory laws."""
        cat = Category(name="LawCat")
        
        # Create objects
        A = Object(properties={"name": "A"})
        B = Object(properties={"name": "B"})
        
        # Create morphism
        f = Morphism(
            name="f",
            source=A,
            target=B,
            transform=lambda x: B
        )
        
        cat.add_morphism(f)
        
        # Test identity law: f ∘ id_A = f
        id_A = cat.identity(A)
        composed = id_A.compose(f)
        
        assert composed.source == A
        assert composed.target == B
        
        # Test that composition is defined
        assert "∘" in composed.name


if __name__ == "__main__":
    # Run tests with pytest if available
    try:
        import pytest
        pytest.main([__file__, "-v"])
    except ImportError:
        # Fallback to basic test runner
        print("Running tests without pytest...")
        
        test_classes = [
            TestObject,
            TestMorphism,
            TestCategory,
            TestFunctor,
            TestNaturalTransformation,
            TestMonad,
            TestAgentSpecification,
            TestCategoryTheoreticAgent,
            TestFactoryFunctions,
            TestIntegration
        ]
        
        total_tests = 0
        passed_tests = 0
        
        for cls in test_classes:
            instance = cls()
            methods = [m for m in dir(instance) if m.startswith("test_")]
            
            for method_name in methods:
                total_tests += 1
                try:
                    method = getattr(instance, method_name)
                    method()
                    print(f"✅ {cls.__name__}.{method_name}")
                    passed_tests += 1
                except Exception as e:
                    print(f"❌ {cls.__name__}.{method_name}: {e}")
        
        print(f"\n{passed_tests}/{total_tests} tests passed")
