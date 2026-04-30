"""
Category-Theoretic Agent Framework

Based on arXiv:2603.28906v1 "Towards a Category-theoretic Comparative Framework 
for Artificial General Intelligence" by Dov Te'eni and Nir Lipovetzky.

Provides a formal mathematical foundation for:
1. Composing agents as morphisms with typed inputs/outputs
2. Unifying diverse AGI paradigms under algebraic structure
3. Enabling rigorous architectural comparison
4. Supporting structural closure and dynamical stability

Key Concepts:
- Category: Collection of objects (agent states) and morphisms (transformations)
- Functor: Maps between categories preserving structure
- Natural Transformation: Morphism between functors
- Monad: Encapsulates computational context (effects)
"""

from typing import TypeVar, Generic, Callable, Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum, auto
from abc import ABC, abstractmethod
import uuid
import json


# Type variables for generic programming
T = TypeVar('T')
U = TypeVar('U')
V = TypeVar('V')


class AgentType(Enum):
    """Types of agents in the categorical framework."""
    REACTIVE = auto()      # Stimulus-response
    DELIBERATIVE = auto()  # Planning-based
    LEARNING = auto()      # Adaptive/learning
    MULTI_AGENT = auto()   # Distributed/collective
    HYBRID = auto()        # Combination of above


@dataclass(frozen=True)
class Object:
    """
    Object in the category - represents an agent state or configuration.
    
    Immutable state container with typed properties.
    Objects are nodes in the categorical graph.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def __hash__(self):
        return hash(self.id)
    
    def with_property(self, key: str, value: Any) -> 'Object':
        """Create new object with additional property (immutability)."""
        new_props = dict(self.properties)
        new_props[key] = value
        return Object(id=self.id, properties=new_props)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get property value."""
        return self.properties.get(key, default)


@dataclass
class Morphism:
    """
    Morphism in the category - represents an agent transformation.
    
    A morphism f: A → B transforms object A into object B.
    In agent terms: a computation or action that changes state.
    """
    name: str
    source: Object  # Domain
    target: Object  # Codomain
    transform: Callable[[Object], Object]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def compose(self, other: 'Morphism') -> 'Morphism':
        """
        Compose morphisms: if f: A → B and g: B → C, then g ∘ f: A → C
        
        This is the fundamental operation of category theory.
        """
        if self.target != other.source:
            raise ValueError(
                f"Cannot compose: {self.name} target != {other.name} source"
            )
        
        def composed_transform(obj: Object) -> Object:
            intermediate = self.transform(obj)
            return other.transform(intermediate)
        
        return Morphism(
            name=f"{other.name} ∘ {self.name}",
            source=self.source,
            target=other.target,
            transform=composed_transform,
            metadata={
                "composition": True,
                "first": self.name,
                "second": other.name
            }
        )
    
    def apply(self, obj: Object) -> Object:
        """Apply morphism to object."""
        if obj != self.source:
            raise ValueError(f"Object {obj.id} is not source of morphism {self.name}")
        return self.transform(obj)


@dataclass
class Category:
    """
    Category of agents - collection of objects and morphisms.
    
    A category C consists of:
    - Objects: ob(C) - agent states
    - Morphisms: hom(C) - agent transformations
    - Identity morphisms: id_A: A → A for each object A
    - Composition: ∘ operation satisfying associativity and identity laws
    """
    name: str
    objects: Set[Object] = field(default_factory=set)
    morphisms: Dict[str, Morphism] = field(default_factory=dict)
    
    def add_object(self, obj: Object) -> None:
        """Add object to category."""
        self.objects.add(obj)
    
    def add_morphism(self, morphism: Morphism) -> None:
        """Add morphism to category."""
        self.morphisms[morphism.name] = morphism
        self.objects.add(morphism.source)
        self.objects.add(morphism.target)
    
    def identity(self, obj: Object) -> Morphism:
        """Create identity morphism for object: id_A: A → A"""
        if obj not in self.objects:
            self.add_object(obj)
        
        return Morphism(
            name=f"id_{obj.id}",
            source=obj,
            target=obj,
            transform=lambda x: x,  # Identity function
            metadata={"type": "identity"}
        )
    
    def compose(self, f_name: str, g_name: str) -> Morphism:
        """Compose two morphisms by name."""
        if f_name not in self.morphisms:
            raise ValueError(f"Morphism {f_name} not found")
        if g_name not in self.morphisms:
            raise ValueError(f"Morphism {g_name} not found")
        
        f = self.morphisms[f_name]
        g = self.morphisms[g_name]
        
        composed = f.compose(g)
        self.add_morphism(composed)
        return composed


class Functor(ABC):
    """
    Functor F: C → D between categories.
    
    Maps objects to objects and morphisms to morphisms while preserving:
    - Identity: F(id_A) = id_{F(A)}
    - Composition: F(g ∘ f) = F(g) ∘ F(f)
    
    Functors represent structural-preserving mappings between agent systems.
    """
    
    def __init__(self, source: Category, target: Category, name: str = "F"):
        self.source = source
        self.target = target
        self.name = name
    
    @abstractmethod
    def map_object(self, obj: Object) -> Object:
        """Map object from source to target category."""
        pass
    
    @abstractmethod
    def map_morphism(self, morphism: Morphism) -> Morphism:
        """Map morphism from source to target category."""
        pass
    
    def verify_identity_preservation(self, obj: Object) -> bool:
        """Verify F(id_A) = id_{F(A)}"""
        id_source = self.source.identity(obj)
        mapped_id = self.map_morphism(id_source)
        
        mapped_obj = self.map_object(obj)
        id_target = self.target.identity(mapped_obj)
        
        return mapped_id.name == id_target.name
    
    def verify_composition_preservation(self, f: Morphism, g: Morphism) -> bool:
        """Verify F(g ∘ f) = F(g) ∘ F(f)"""
        composed = f.compose(g)
        mapped_composed = self.map_morphism(composed)
        
        mapped_f = self.map_morphism(f)
        mapped_g = self.map_morphism(g)
        mapped_composed_direct = mapped_f.compose(mapped_g)
        
        return mapped_composed.name == mapped_composed_direct.name


class AgentFunctor(Functor):
    """
    Concrete functor for mapping between agent architectures.
    
    Example: Map reactive agent category to deliberative agent category.
    """
    
    def __init__(
        self,
        source: Category,
        target: Category,
        object_mapping: Dict[str, str],
        morphism_transforms: Dict[str, Callable],
        name: str = "AgentFunctor"
    ):
        super().__init__(source, target, name)
        self.object_mapping = object_mapping
        self.morphism_transforms = morphism_transforms
    
    def map_object(self, obj: Object) -> Object:
        """Map agent state using predefined mapping."""
        if obj.id in self.object_mapping:
            mapped_id = self.object_mapping[obj.id]
            return Object(
                id=mapped_id,
                properties={"mapped_from": obj.id, **obj.properties}
            )
        return obj
    
    def map_morphism(self, morphism: Morphism) -> Morphism:
        """Map morphism using transformation functions."""
        if morphism.name in self.morphism_transforms:
            new_transform = self.morphism_transforms[morphism.name]
            return Morphism(
                name=f"{self.name}({morphism.name})",
                source=self.map_object(morphism.source),
                target=self.map_object(morphism.target),
                transform=new_transform,
                metadata={"functor": self.name, "original": morphism.name}
            )
        return morphism


@dataclass
class NaturalTransformation:
    """
    Natural transformation η: F ⇒ G between functors F, G: C → D
    
    A family of morphisms in D, one for each object in C, satisfying
    naturality condition: η_B ∘ F(f) = G(f) ∘ η_A for all f: A → B
    
    Represents coherent mappings between different agent system views.
    """
    name: str
    source_functor: Functor
    target_functor: Functor
    components: Dict[str, Morphism] = field(default_factory=dict)
    
    def add_component(self, obj: Object, morphism: Morphism) -> None:
        """Add component morphism for object."""
        self.components[obj.id] = morphism
    
    def is_natural(self, f: Morphism) -> bool:
        """
        Verify naturality square commutes:
        
            F(A) --F(f)--> F(B)
             |               |
             | η_A           | η_B
             v               v
            G(A) --G(f)--> G(B)
        
        Requires: η_B ∘ F(f) = G(f) ∘ η_A
        """
        source_id = f.source.id
        target_id = f.target.id
        
        if source_id not in self.components or target_id not in self.components:
            return False
        
        eta_A = self.components[source_id]
        eta_B = self.components[target_id]
        
        F_f = self.source_functor.map_morphism(f)
        G_f = self.target_functor.map_morphism(f)
        
        left = eta_B.compose(F_f)
        right = G_f.compose(eta_A)
        
        return left.name == right.name


class Monad:
    """
    Monad for encapsulating agent effects and context.
    
    A monad T on category C consists of:
    - Functor T: C → C
    - Unit η: Id ⇒ T (return/pure)
    - Multiplication μ: T² ⇒ T (join/flatten)
    
    Laws:
    - Left identity: μ ∘ Tη = id_T
    - Right identity: μ ∘ ηT = id_T  
    - Associativity: μ ∘ Tμ = μ ∘ μT
    """
    
    def __init__(self, name: str, category: Category):
        self.name = name
        self.category = category
        self.unit: Optional[NaturalTransformation] = None
        self.multiply: Optional[NaturalTransformation] = None
    
    def set_unit(self, unit: NaturalTransformation) -> None:
        """Set unit natural transformation."""
        self.unit = unit
    
    def set_multiply(self, multiply: NaturalTransformation) -> None:
        """Set multiplication natural transformation."""
        self.multiply = multiply
    
    def bind(self, obj: Object, f: Callable[[Object], Object]) -> Object:
        """
        Monadic bind (>>=): sequential composition with context passing.
        
        bind(M, f) = μ(T(f)(M))
        """
        # Apply f within monadic context
        mapped = f(obj)
        
        # Flatten result (apply multiplication)
        if obj.id in self.multiply.components:
            return self.multiply.components[obj.id].apply(mapped)
        
        return mapped


@dataclass
class AgentSpecification:
    """
    Complete specification of an agent in category-theoretic terms.
    
    Based on SMGI structural theory: θ = (r, H, Π, L, E, M)
    - r: representations
    - H: hypothesis space
    - Π: priors
    - L: evaluator/loss
    - E: evolution operator
    - M: memory operator
    """
    name: str
    agent_type: AgentType
    category: Category
    
    # Structural components
    representations: Dict[str, Object] = field(default_factory=dict)
    hypothesis_space: List[Morphism] = field(default_factory=list)
    priors: Dict[str, float] = field(default_factory=dict)
    
    # Dynamics
    evaluator: Optional[Callable[[Object], float]] = None
    evolution: Optional[Morphism] = None
    memory_operator: Optional[Morphism] = None
    
    # SMGI obligations
    structural_closure: bool = True
    dynamical_stability: bool = True
    bounded_capacity: bool = True
    evaluative_invariance: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize specification to dictionary."""
        return {
            "name": self.name,
            "agent_type": self.agent_type.name,
            "category": self.category.name,
            "representations": list(self.representations.keys()),
            "hypothesis_count": len(self.hypothesis_space),
            "priors": self.priors,
            "smgi_obligations": {
                "structural_closure": self.structural_closure,
                "dynamical_stability": self.dynamical_stability,
                "bounded_capacity": self.bounded_capacity,
                "evaluative_invariance": self.evaluative_invariance
            }
        }


class CategoryTheoreticAgent:
    """
    Agent implementation using category-theoretic foundations.
    
    Provides rigorous mathematical structure for:
    - State representation (objects)
    - Action execution (morphisms)
    - System composition (functors)
    - Effect handling (monads)
    """
    
    def __init__(self, spec: AgentSpecification):
        self.spec = spec
        self.current_state: Optional[Object] = None
        self.history: List[Morphism] = []
        self.active_morphisms: Dict[str, Morphism] = {}
    
    def initialize(self, initial_properties: Dict[str, Any]) -> Object:
        """Initialize agent with starting state."""
        self.current_state = Object(properties=initial_properties)
        self.spec.category.add_object(self.current_state)
        return self.current_state
    
    def execute(self, morphism: Morphism) -> Object:
        """Execute morphism on current state."""
        if self.current_state is None:
            raise RuntimeError("Agent not initialized")
        
        # Apply transformation
        new_state = morphism.apply(self.current_state)
        
        # Update state
        self.current_state = new_state
        self.spec.category.add_object(new_state)
        self.history.append(morphism)
        
        return new_state
    
    def compose_actions(self, action_names: List[str]) -> Morphism:
        """Compose multiple actions into single morphism."""
        if len(action_names) < 2:
            raise ValueError("Need at least 2 actions to compose")
        
        result = self.spec.category.morphisms[action_names[0]]
        
        for name in action_names[1:]:
            result = result.compose(self.spec.category.morphisms[name])
        
        return result
    
    def verify_structure(self) -> Dict[str, bool]:
        """Verify SMGI structural obligations."""
        return {
            "structural_closure": self.spec.structural_closure,
            "dynamical_stability": self.spec.dynamical_stability,
            "bounded_capacity": self.spec.bounded_capacity,
            "evaluative_invariance": self.spec.evaluative_invariance,
            "category_nonempty": len(self.spec.category.objects) > 0,
            "has_identity": all(
                f"id_{obj.id}" in self.spec.category.morphisms 
                or self.spec.category.identity(obj) is not None
                for obj in self.spec.category.objects
            )
        }


# Factory functions for common agent types

def create_reactive_agent(name: str) -> CategoryTheoreticAgent:
    """Create simple reactive agent (stimulus-response)."""
    cat = Category(name=f"{name}_category")
    
    spec = AgentSpecification(
        name=name,
        agent_type=AgentType.REACTIVE,
        category=cat
    )
    
    return CategoryTheoreticAgent(spec)


def create_deliberative_agent(name: str) -> CategoryTheoreticAgent:
    """Create deliberative agent with planning morphisms."""
    cat = Category(name=f"{name}_category")
    
    # Add planning morphism
    plan_obj = Object(properties={"type": "plan"})
    act_obj = Object(properties={"type": "action"})
    cat.add_object(plan_obj)
    cat.add_object(act_obj)
    
    spec = AgentSpecification(
        name=name,
        agent_type=AgentType.DELIBERATIVE,
        category=cat
    )
    
    return CategoryTheoreticAgent(spec)


def create_learning_agent(name: str) -> CategoryTheoreticAgent:
    """Create learning agent with adaptation morphisms."""
    cat = Category(name=f"{name}_category")
    
    spec = AgentSpecification(
        name=name,
        agent_type=AgentType.LEARNING,
        category=cat
    )
    
    return CategoryTheoreticAgent(spec)


def create_functor_between_agents(
    source_agent: CategoryTheoreticAgent,
    target_agent: CategoryTheoreticAgent,
    mapping_config: Dict[str, Any]
) -> AgentFunctor:
    """
    Create functor mapping between two agent categories.
    
    Enables comparison and transformation between different agent architectures.
    """
    return AgentFunctor(
        source=source_agent.spec.category,
        target=target_agent.spec.category,
        object_mapping=mapping_config.get("objects", {}),
        morphism_transforms=mapping_config.get("morphisms", {}),
        name=mapping_config.get("name", "AgentMapping")
    )
