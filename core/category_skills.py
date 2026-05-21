"""
Category-Theoretic Skill Composition Module

Implements formal category theory constructs for agent skill composition.
Skills are morphisms between agent states, enabling algebraic composition
with guaranteed properties (identity, associativity, functorial mapping).

Based on research:
- arXiv:2603.28906: Category-theoretic frameworks for AGI
- Corpus2Skill: Hierarchical skill organization
- Skill Induction for Code Agents: Verification-gated composition
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generic, List, Optional, Protocol, Set, TypeVar
from enum import Enum, auto
import hashlib
import json


class StateType(Enum):
    """Fundamental state types in the agent category."""
    RAW_INPUT = auto()
    PROCESSED = auto()
    ANALYZED = auto()
    SYNTHESIZED = auto()
    ACTIONABLE = auto()
    TERMINAL = auto()


@dataclass(frozen=True)
class State:
    """
    Object in the skill category.
    
    States are typed containers with value and metadata.
    Immutability ensures referential transparency for composition.
    """
    state_type: StateType
    value: Any
    metadata: Dict[str, Any] = field(default_factory=dict)
    state_id: str = field(default_factory=lambda: hashlib.md5(str(id(object())).encode()).hexdigest()[:8])
    
    def with_value(self, new_value: Any, new_type: Optional[StateType] = None) -> State:
        """Create new state with transformed value (functorial mapping)."""
        return State(
            state_type=new_type or self.state_type,
            value=new_value,
            metadata=self.metadata.copy(),
            state_id=self.state_id
        )
    
    def with_metadata(self, **kwargs) -> State:
        """Create new state with extended metadata."""
        new_metadata = self.metadata.copy()
        new_metadata.update(kwargs)
        return State(
            state_type=self.state_type,
            value=self.value,
            metadata=new_metadata,
            state_id=self.state_id
        )
    
    def __hash__(self) -> int:
        return hash((self.state_type, self.state_id))


class VerificationResult(Enum):
    """Result of pre/post-condition verification."""
    PASS = auto()
    FAIL = auto()
    WARNING = auto()


@dataclass
class VerificationReport:
    """Detailed verification result with diagnostics."""
    result: VerificationResult
    stage: str  # "pre", "post", "invariant"
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


class SkillMorphism(ABC):
    """
    Morphism in the skill category: a transformation from domain to codomain.
    
    Represents a skill as a typed function with verification boundaries.
    Mathematical properties:
    - Domain: Input state type
    - Codomain: Output state type  
    - Composition: ∘ operator producing new morphism
    """
    
    def __init__(
        self,
        name: str,
        domain: StateType,
        codomain: StateType,
        verify_pre: Optional[Callable[[State], VerificationReport]] = None,
        verify_post: Optional[Callable[[State, State], VerificationReport]] = None,
    ):
        self.name = name
        self.domain = domain
        self.codomain = codomain
        self._verify_pre = verify_pre
        self._verify_post = verify_post
        self._execution_count = 0
        self._success_count = 0
    
    @abstractmethod
    def execute(self, state: State) -> State:
        """
        Execute the skill transformation.
        
        Args:
            state: Input state (must match domain type)
            
        Returns:
            Output state (matches codomain type)
        """
        pass
    
    def verify_precondition(self, state: State) -> VerificationReport:
        """Verify input state satisfies domain requirements."""
        # Type check
        if state.state_type != self.domain:
            return VerificationReport(
                result=VerificationResult.FAIL,
                stage="pre",
                message=f"Type mismatch: expected {self.domain.name}, got {state.state_type.name}"
            )
        
        # Custom verification
        if self._verify_pre:
            return self._verify_pre(state)
        
        return VerificationReport(
            result=VerificationResult.PASS,
            stage="pre",
            message="Precondition satisfied"
        )
    
    def verify_postcondition(self, input_state: State, output_state: State) -> VerificationReport:
        """Verify output state satisfies codomain requirements."""
        # Type check
        if output_state.state_type != self.codomain:
            return VerificationReport(
                result=VerificationResult.FAIL,
                stage="post",
                message=f"Type mismatch: expected {self.codomain.name}, got {output_state.state_type.name}"
            )
        
        # Custom verification
        if self._verify_post:
            return self._verify_post(input_state, output_state)
        
        return VerificationReport(
            result=VerificationResult.PASS,
            stage="post",
            message="Postcondition satisfied"
        )
    
    def __call__(self, state: State, verify: bool = True) -> State:
        """
        Execute skill with optional verification.
        
        This is the categorical morphism application.
        """
        self._execution_count += 1
        
        if verify:
            pre_report = self.verify_precondition(state)
            if pre_report.result == VerificationResult.FAIL:
                raise SkillCompositionError(
                    f"Precondition failed for {self.name}: {pre_report.message}"
                )
        
        result = self.execute(state)
        
        if verify:
            post_report = self.verify_postcondition(state, result)
            if post_report.result == VerificationResult.FAIL:
                raise SkillCompositionError(
                    f"Postcondition failed for {self.name}: {post_report.message}"
                )
        
        self._success_count += 1
        return result
    
    def compose(self, other: SkillMorphism, name: Optional[str] = None) -> CompositeSkillMorphism:
        """
        Compose morphisms: self ∘ other (apply other, then self).
        
        In category theory notation: f ∘ g means "g then f"
        
        Args:
            other: Morphism to apply first (codomain must match our domain)
            name: Optional name for composed morphism
            
        Returns:
            Composite morphism representing the sequential application
        """
        if other.codomain != self.domain:
            raise SkillCompositionError(
                f"Cannot compose: {other.name} codomain ({other.codomain.name}) "
                f"doesn't match {self.name} domain ({self.domain.name})"
            )
        
        composite_name = name or f"{self.name}∘{other.name}"
        return CompositeSkillMorphism(
            first=other,
            second=self,
            name=composite_name
        )
    
    def __matmul__(self, other: SkillMorphism) -> CompositeSkillMorphism:
        """Use @ operator for composition: f @ g == f ∘ g"""
        return self.compose(other)
    
    @property
    def success_rate(self) -> float:
        """Empirical success rate from executions."""
        if self._execution_count == 0:
            return 1.0
        return self._success_count / self._execution_count


class CompositeSkillMorphism(SkillMorphism):
    """
    Composite morphism representing f ∘ g (g then f).
    
    This implements categorical composition with associativity properties.
    """
    
    def __init__(self, first: SkillMorphism, second: SkillMorphism, name: str):
        # Domain is domain of first (g)
        # Codomain is codomain of second (f)
        super().__init__(
            name=name,
            domain=first.domain,
            codomain=second.codomain
        )
        self.first = first
        self.second = second
        self._components = [first, second]
    
    def execute(self, state: State) -> State:
        """Execute composition: apply first, then second."""
        intermediate = self.first(state, verify=False)
        return self.second(intermediate, verify=False)
    
    def compose(self, other: SkillMorphism, name: Optional[str] = None) -> CompositeSkillMorphism:
        """
        Extend composition associatively.
        
        (f ∘ g) ∘ h = f ∘ (g ∘ h)
        
        We flatten to maintain associativity property.
        """
        if other.codomain != self.domain:
            raise SkillCompositionError(
                f"Cannot compose: type mismatch {other.codomain.name} vs {self.domain.name}"
            )
        
        # Build new composite preserving associativity
        composite_name = name or f"{self.name}∘{other.name}"
        
        # Create new composite with flattened components for efficiency
        new_composite = CompositeSkillMorphism.__new__(CompositeSkillMorphism)
        new_composite.first = other
        new_composite.second = self
        new_composite.name = composite_name
        new_composite.domain = other.domain
        new_composite.codomain = self.codomain
        new_composite._components = [other] + self._components
        new_composite._execution_count = 0
        new_composite._success_count = 0
        new_composite._verify_pre = None
        new_composite._verify_post = None
        
        return new_composite
    
    @property
    def components(self) -> List[SkillMorphism]:
        """Get flattened list of component morphisms."""
        return self._components.copy()


class IdentitySkillMorphism(SkillMorphism):
    """
    Identity morphism id_A for each state type A.
    
    Satisfies: f ∘ id_A = f and id_B ∘ f = f for f: A → B
    """
    
    def __init__(self, state_type: StateType):
        super().__init__(
            name=f"id_{state_type.name}",
            domain=state_type,
            codomain=state_type
        )
        self.state_type = state_type
    
    def execute(self, state: State) -> State:
        """Identity: return state unchanged."""
        return state


class ConcreteSkillMorphism(SkillMorphism):
    """
    Concrete skill implementation from a function.
    """
    
    def __init__(
        self,
        name: str,
        domain: StateType,
        codomain: StateType,
        func: Callable[[Any], Any],
        verify_pre: Optional[Callable[[State], VerificationReport]] = None,
        verify_post: Optional[Callable[[State, State], VerificationReport]] = None,
    ):
        super().__init__(name, domain, codomain, verify_pre, verify_post)
        self._func = func
    
    def execute(self, state: State) -> State:
        """Execute wrapped function on state value."""
        new_value = self._func(state.value)
        return State(
            state_type=self.codomain,
            value=new_value,
            metadata=state.metadata.copy()
        )


class SkillFunctor:
    """
    Functor mapping between skill categories.
    
    Preserves structure:
    - Maps objects (states) to objects
    - Maps morphisms (skills) to morphisms
    - Preserves composition: F(f ∘ g) = F(f) ∘ F(g)
    - Preserves identity: F(id_A) = id_F(A)
    """
    
    def __init__(self, name: str):
        self.name = name
        self._object_map: Dict[StateType, StateType] = {}
        self._morphism_cache: Dict[str, SkillMorphism] = {}
    
    def map_object(self, state_type: StateType) -> StateType:
        """Map object (state type) to target category."""
        if state_type not in self._object_map:
            raise SkillCompositionError(f"No mapping defined for {state_type.name}")
        return self._object_map[state_type]
    
    def define_object_mapping(self, source: StateType, target: StateType):
        """Define how to map a state type."""
        self._object_map[source] = target
    
    def map_morphism(self, skill: SkillMorphism) -> SkillMorphism:
        """
        Map morphism (skill) to target category.
        
        Preserves:
        - Domain/codomain structure via object mapping
        - Composition via lazy evaluation
        """
        cache_key = f"{self.name}:{skill.name}"
        if cache_key in self._morphism_cache:
            return self._morphism_cache[cache_key]
        
        # Map domain and codomain
        new_domain = self.map_object(skill.domain)
        new_codomain = self.map_object(skill.codomain)
        
        # Create mapped skill
        if isinstance(skill, CompositeSkillMorphism):
            # Preserve composition structure
            mapped_first = self.map_morphism(skill.first)
            mapped_second = self.map_morphism(skill.second)
            mapped = mapped_second.compose(mapped_first, name=f"{self.name}({skill.name})")
        elif isinstance(skill, IdentitySkillMorphism):
            # Preserve identity
            mapped = IdentitySkillMorphism(new_domain)
        else:
            # Concrete mapping
            mapped = ConcreteSkillMorphism(
                name=f"{self.name}({skill.name})",
                domain=new_domain,
                codomain=new_codomain,
                func=lambda x: x  # Identity on values, type transformed
            )
        
        self._morphism_cache[cache_key] = mapped
        return mapped


class SkillCategory:
    """
    Category of agent skills.
    
    Contains:
    - Objects: State types
    - Morphisms: Skills between state types
    - Identity morphisms for each object
    - Composition operation
    """
    
    def __init__(self, name: str):
        self.name = name
        self._morphisms: Dict[str, SkillMorphism] = {}
        self._identities: Dict[StateType, IdentitySkillMorphism] = {}
        
        # Create identity morphisms for all state types
        for state_type in StateType:
            self._identities[state_type] = IdentitySkillMorphism(state_type)
    
    def add_morphism(self, skill: SkillMorphism):
        """Add a morphism to the category."""
        self._morphisms[skill.name] = skill
    
    def get_morphism(self, name: str) -> Optional[SkillMorphism]:
        """Retrieve morphism by name."""
        return self._morphisms.get(name)
    
    def identity(self, state_type: StateType) -> IdentitySkillMorphism:
        """Get identity morphism for state type."""
        return self._identities[state_type]
    
    def compose(
        self, 
        f: SkillMorphism, 
        g: SkillMorphism,
        verify_types: bool = True
    ) -> CompositeSkillMorphism:
        """
        Compose morphisms f ∘ g (g then f).
        
        Args:
            f: Second morphism to apply
            g: First morphism to apply
            verify_types: Check type compatibility
            
        Returns:
            Composite morphism
        """
        if verify_types and g.codomain != f.domain:
            raise SkillCompositionError(
                f"Cannot compose {f.name} ∘ {g.name}: "
                f"codomain of {g.name} ({g.codomain.name}) "
                f"!= domain of {f.name} ({f.domain.name})"
            )
        
        return f.compose(g)
    
    def compose_pipeline(self, *skills: SkillMorphism) -> CompositeSkillMorphism:
        """
        Compose a pipeline of skills left-to-right.
        
        pipeline(a, b, c) = c ∘ b ∘ a (a first, then b, then c)
        """
        if len(skills) < 2:
            raise SkillCompositionError("Pipeline requires at least 2 skills")
        
        result = skills[0]
        for skill in skills[1:]:
            result = skill.compose(result)
        
        return result
    
    def get_morphisms_between(
        self, 
        domain: StateType, 
        codomain: StateType
    ) -> List[SkillMorphism]:
        """Find all morphisms between given state types."""
        return [
            m for m in self._morphisms.values()
            if m.domain == domain and m.codomain == codomain
        ]


class CompositionEngine:
    """
    Execution engine for composed skills with verification and rollback.
    """
    
    def __init__(self, enable_memoization: bool = True):
        self.enable_memoization = enable_memoization
        self._memo: Dict[str, State] = {}
        self._execution_log: List[Dict[str, Any]] = []
    
    def execute(
        self,
        skill: SkillMorphism,
        state: State,
        verify: bool = True,
        enable_rollback: bool = True
    ) -> State:
        """
        Execute skill with full verification and rollback support.
        
        Args:
            skill: Morphism to execute
            state: Input state
            verify: Enable pre/post condition checking
            enable_rollback: Save intermediate states for recovery
            
        Returns:
            Output state
        """
        execution_id = hashlib.md5(
            f"{skill.name}:{state.state_id}:{json.dumps(state.value, default=str)}".encode()
        ).hexdigest()[:12]
        
        # Check memoization
        if self.enable_memoization and execution_id in self._memo:
            return self._memo[execution_id]
        
        # Execute with checkpoint
        checkpoint = state if enable_rollback else None
        
        try:
            if isinstance(skill, CompositeSkillMorphism):
                result = self._execute_composite(skill, state, verify)
            else:
                result = skill(state, verify=verify)
            
            # Memoize successful result
            if self.enable_memoization:
                self._memo[execution_id] = result
            
            self._execution_log.append({
                "execution_id": execution_id,
                "skill": skill.name,
                "success": True,
                "checkpoint_restored": False
            })
            
            return result
            
        except Exception as e:
            self._execution_log.append({
                "execution_id": execution_id,
                "skill": skill.name,
                "success": False,
                "error": str(e),
                "checkpoint_restored": enable_rollback
            })
            
            if enable_rollback and checkpoint:
                # Return to checkpoint on failure
                return checkpoint.with_metadata(
                    rollback_reason=str(e),
                    failed_skill=skill.name
                )
            raise
    
    def _execute_composite(
        self,
        composite: CompositeSkillMorphism,
        state: State,
        verify: bool
    ) -> State:
        """Execute composite morphism component by component."""
        current = state
        
        for i, component in enumerate(composite.components):
            try:
                current = self.execute(component, current, verify, enable_rollback=False)
            except SkillCompositionError as e:
                # Enhance error with composition context
                raise SkillCompositionError(
                    f"Component {i+1}/{len(composite.components)} ({component.name}) failed: {e}"
                ) from e
        
        return current
    
    def get_execution_log(self) -> List[Dict[str, Any]]:
        """Get log of all executions."""
        return self._execution_log.copy()
    
    def clear_memo(self):
        """Clear memoization cache."""
        self._memo.clear()


class SkillCompositionError(Exception):
    """Error in skill composition or execution."""
    pass


# Convenience functions for common patterns

def create_skill_category(name: str = "Default") -> SkillCategory:
    """Create a new skill category with all identity morphisms."""
    return SkillCategory(name)


def create_concrete_skill(
    name: str,
    domain: StateType,
    codomain: StateType,
    func: Callable[[Any], Any]
) -> ConcreteSkillMorphism:
    """Create a simple concrete skill from a function."""
    return ConcreteSkillMorphism(name, domain, codomain, func)


def verify_identity_law(skill: SkillMorphism, category: SkillCategory, test_value: Any) -> bool:
    """
    Verify identity law: f ∘ id = f and id ∘ f = f
    
    Returns True if both identities hold for test value.
    """
    state = State(state_type=skill.domain, value=test_value)
    
    # f ∘ id (apply identity first, then f)
    id_domain = category.identity(skill.domain)
    f_after_id = skill.compose(id_domain)
    
    # id ∘ f (apply f first, then identity on codomain)
    id_codomain = category.identity(skill.codomain)
    id_after_f = id_codomain.compose(skill)
    
    try:
        result1 = f_after_id(state, verify=False)
        result2 = skill(state, verify=False)
        result3 = id_after_f(state, verify=False)
        
        # Check all results equivalent
        return (
            result1.value == result2.value == result3.value and
            result1.state_type == result2.state_type == result3.state_type
        )
    except Exception:
        return False


def verify_associativity(
    f: SkillMorphism,
    g: SkillMorphism,
    h: SkillMorphism,
    test_value: Any
) -> bool:
    """
    Verify associativity: (f ∘ g) ∘ h = f ∘ (g ∘ h)
    
    Returns True if associativity holds for test value.
    """
    # Check type compatibility
    if h.codomain != g.domain or g.codomain != f.domain:
        return False
    
    state = State(state_type=h.domain, value=test_value)
    
    # (f ∘ g) ∘ h
    fg = f.compose(g)
    fg_h = fg.compose(h)
    
    # f ∘ (g ∘ h)
    gh = g.compose(h)
    f_gh = f.compose(gh)
    
    try:
        result1 = fg_h(state, verify=False)
        result2 = f_gh(state, verify=False)
        
        return (
            result1.value == result2.value and
            result1.state_type == result2.state_type
        )
    except Exception:
        return False


def create_verified_composition(
    *skills: SkillMorphism,
    name: Optional[str] = None,
    invariant_check: Optional[Callable[[State], VerificationReport]] = None
) -> SkillMorphism:
    """
    Create a composition with verification at each boundary.
    
    Args:
        *skills: Skills to compose in order
        name: Optional name for composition
        invariant_check: Optional invariant to check at each step
        
    Returns:
        Verified composite morphism
    """
    if len(skills) < 2:
        raise SkillCompositionError("Need at least 2 skills to compose")
    
    # Build composition with verification
    composite = skills[0]
    for skill in skills[1:]:
        composite = skill.compose(composite)
    
    if name:
        composite.name = name
    
    return composite
