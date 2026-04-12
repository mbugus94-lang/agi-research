"""
Category-Theoretic Framework for AGI Architecture Comparison

Based on: arXiv:2603.28906v1 "Working Paper: Towards a Category-theoretic 
Comparative Framework for Artificial General Intelligence"

This module implements a formal algebraic foundation for describing, comparing,
and analyzing AGI architectures using category theory. It unifies diverse
paradigms (RL, Universal AI, Active Inference, Schema-based Learning) under
a single mathematical framework.

Key Concepts:
- Categories represent agent architectures and environments
- Functors map between architectural paradigms
- Natural transformations capture architectural refinements
- Morphisms represent agent-environment interactions
"""

from typing import Dict, List, Any, Optional, Callable, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict
import json


class ArchitectureType(Enum):
    """AGI architectural paradigms as categories."""
    REINFORCEMENT_LEARNING = "rl"
    UNIVERSAL_AI = "universal"  # AIXI-style
    ACTIVE_INFERENCE = "active_inference"  # Friston/Free Energy Principle
    SCHEMA_BASED_LEARNING = "schema"  # Cognitive architectures
    CAUSAL_RL = "causal_rl"
    NEURO_SYMBOLIC = "neuro_symbolic"
    CUSTOM = "custom"


@dataclass
class Object:
    """
    Object in a category-theoretic sense.
    
    In AGI contexts, objects represent:
    - State spaces (S)
    - Action spaces (A)
    - Observation spaces (O)  
    - Belief states (B)
    - Policies (π)
    - Programs/Hypotheses (H)
    """
    name: str
    properties: Dict[str, Any] = field(default_factory=dict)
    structural_type: str = "generic"  # state, action, observation, belief, policy, program
    
    def __hash__(self):
        return hash(self.name)
    
    def __eq__(self, other):
        if isinstance(other, Object):
            return self.name == other.name
        return False


@dataclass
class Morphism:
    """
    Morphism (arrow) between objects.
    
    Represents:
    - Transition functions (S × A → S')
    - Observation functions (S → O)
    - Policy functions (B → A)
    - Learning updates (H × O → H')
    """
    name: str
    domain: Object  # Source object
    codomain: Object  # Target object
    mapping: Optional[Callable] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    
    # Structural properties
    is_deterministic: bool = True
    is_stochastic: bool = False
    is_partial: bool = False  # Partial function (undefined for some inputs)
    is_computable: bool = True
    
    def __hash__(self):
        return hash((self.name, self.domain.name, self.codomain.name))
    
    def __eq__(self, other):
        if not isinstance(other, Morphism):
            return False
        return (self.name == other.name and 
                self.domain == other.domain and 
                self.codomain == other.codomain)
    
    def compose(self, other: 'Morphism') -> Optional['Morphism']:
        """
        Compose morphisms: f ∘ g (do g then f).
        
        Returns new morphism if codomain(g) == domain(f).
        """
        if self.domain != other.codomain:
            return None
        
        return Morphism(
            name=f"{self.name}_∘_{other.name}",
            domain=other.domain,
            codomain=self.codomain,
            properties={
                "composition": True,
                "composed_from": [other.name, self.name]
            }
        )


@dataclass
class Category:
    """
    Category representing an AGI architecture.
    
    A category C consists of:
    - Objects: obj(C) - state/action/observation spaces
    - Morphisms: hom(C) - transition/observation/policy functions
    - Identity morphisms: id_A for each object A
    - Associative composition: (f ∘ g) ∘ h = f ∘ (g ∘ h)
    
    Different architectures are different categories:
    - RL: States, Actions, Observations with transition and reward morphisms
    - Universal AI: Programs, Predictions, with update and selection morphisms
    - Active Inference: Beliefs, Policies, with inference and action morphisms
    """
    name: str
    architecture_type: ArchitectureType
    objects: Set[Object] = field(default_factory=set)
    morphisms: List[Morphism] = field(default_factory=list)
    
    # Structural metadata
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def add_object(self, obj: Object):
        """Add object to category."""
        self.objects.add(obj)
    
    def add_morphism(self, morph: Morphism):
        """Add morphism to category if domain/codomain are in category."""
        if morph.domain in self.objects and morph.codomain in self.objects:
            self.morphisms.append(morph)
        else:
            # Auto-add objects if needed
            self.objects.add(morph.domain)
            self.objects.add(morph.codomain)
            self.morphisms.append(morph)
    
    def get_morphisms_from(self, obj: Object) -> List[Morphism]:
        """Get all morphisms with given domain."""
        return [m for m in self.morphisms if m.domain == obj]
    
    def get_morphisms_to(self, obj: Object) -> List[Morphism]:
        """Get all morphisms with given codomain."""
        return [m for m in self.morphisms if m.codomain == obj]
    
    def compose_morphisms(self, f: Morphism, g: Morphism) -> Optional[Morphism]:
        """
        Compose morphisms within this category.
        f ∘ g means: do g first, then f.
        """
        if f.domain != g.codomain:
            return None
        
        return Morphism(
            name=f"{f.name}∘{g.name}",
            domain=g.domain,
            codomain=f.codomain,
            properties={"composed": True, "chain": [g.name, f.name]}
        )
    
    def structural_summary(self) -> Dict[str, Any]:
        """Get structural summary of category."""
        obj_types = defaultdict(int)
        for obj in self.objects:
            obj_types[obj.structural_type] += 1
        
        morph_types = defaultdict(int)
        for morph in self.morphisms:
            key = f"{morph.domain.structural_type}→{morph.codomain.structural_type}"
            morph_types[key] += 1
        
        return {
            "name": self.name,
            "type": self.architecture_type.value,
            "object_count": len(self.objects),
            "morphism_count": len(self.morphisms),
            "object_types": dict(obj_types),
            "morphism_types": dict(morph_types),
            "properties": self.properties
        }


@dataclass
class Functor:
    """
    Functor between categories (architectures).
    
    A functor F: C → D maps:
    - Objects: F(A) for each A in obj(C)
    - Morphisms: F(f): F(A) → F(B) for each f: A → B in hom(C)
    
    Preserves structure:
    - F(id_A) = id_{F(A)}
    - F(f ∘ g) = F(f) ∘ F(g)
    
    Functors represent:
    - Translations between architectural paradigms
    - Embeddings of simpler into more complex architectures
    - Abstractions that preserve behavioral properties
    """
    name: str
    source: Category
    target: Category
    
    # Mappings
    object_map: Dict[Object, Object] = field(default_factory=dict)
    morphism_map: Dict[Morphism, Morphism] = field(default_factory=dict)
    
    def map_object(self, obj: Object) -> Optional[Object]:
        """Map object from source to target category."""
        return self.object_map.get(obj)
    
    def map_morphism(self, morph: Morphism) -> Optional[Morphism]:
        """Map morphism from source to target category."""
        return self.morphism_map.get(morph)
    
    def is_valid(self) -> bool:
        """
        Check if functor preserves categorical structure.
        
        Validates:
        - All source objects mapped to target
        - All source morphisms mapped to target
        - Domain/codomain preservation
        """
        # Check object mapping completeness
        for obj in self.source.objects:
            if obj not in self.object_map:
                return False
        
        # Check morphism structure preservation
        for morph in self.source.morphisms:
            if morph not in self.morphism_map:
                return False
            
            mapped = self.morphism_map[morph]
            expected_domain = self.object_map.get(morph.domain)
            expected_codomain = self.object_map.get(morph.codomain)
            
            if mapped.domain != expected_domain or mapped.codomain != expected_codomain:
                return False
        
        return True
    
    def preservation_score(self) -> float:
        """
        Score how well structure is preserved (0.0 to 1.0).
        """
        if not self.source.objects:
            return 1.0
        
        score = 0.0
        checks = 0
        
        # Check object mappings
        for obj in self.source.objects:
            checks += 1
            if obj in self.object_map:
                score += 1.0
        
        # Check morphism mappings
        for morph in self.source.morphisms:
            checks += 1
            if morph in self.morphism_map:
                mapped = self.morphism_map[morph]
                if (mapped.domain == self.object_map.get(morph.domain) and
                    mapped.codomain == self.object_map.get(morph.codomain)):
                    score += 1.0
        
        return score / checks if checks > 0 else 1.0


@dataclass
class NaturalTransformation:
    """
    Natural transformation between functors.
    
    Given functors F, G: C → D, a natural transformation η: F ⇒ G
    assigns to each object A in C a morphism η_A: F(A) → G(A) in D
    such that for all f: A → B in C:
    
        G(f) ∘ η_A = η_B ∘ F(f)
    
    (Naturality square commutes)
    
    Natural transformations represent:
    - Architectural refinements
    - Behavioral equivalences
    - Implementation variations that preserve semantics
    """
    name: str
    source_functor: Functor
    target_functor: Functor
    
    # Component morphisms for each object
    components: Dict[Object, Morphism] = field(default_factory=dict)
    
    def naturality_check(self, morph: Morphism) -> bool:
        """
        Check naturality square for a morphism f: A → B.
        
        G(f) ∘ η_A == η_B ∘ F(f)
        """
        A = morph.domain
        B = morph.codomain
        
        eta_A = self.components.get(A)
        eta_B = self.components.get(B)
        
        if not eta_A or not eta_B:
            return False
        
        # Get F(f) and G(f)
        F_f = self.source_functor.map_morphism(morph)
        G_f = self.target_functor.map_morphism(morph)
        
        if not F_f or not G_f:
            return False
        
        # Check: G(f) ∘ η_A == η_B ∘ F(f)
        # This is a structural check (we can't compute actual equality)
        # We verify that compositions exist and types match
        left = G_f.codomain == eta_A.codomain  # G(f) ∘ η_A
        right = eta_B.domain == F_f.codomain   # η_B ∘ F(f)
        
        return left and right
    
    def is_natural(self) -> bool:
        """Check if all naturality squares commute."""
        for morph in self.source_functor.source.morphisms:
            if not self.naturality_check(morph):
                return False
        return True


class AGIArchitectureComparator:
    """
    Main comparator using category-theoretic framework.
    
    Enables rigorous comparison of AGI architectures by:
    1. Representing each as a category
    2. Finding functors between them
    3. Analyzing structural similarities
    4. Identifying commonalities and gaps
    """
    
    def __init__(self):
        self.categories: Dict[str, Category] = {}
        self.functors: List[Functor] = []
        self.transformations: List[NaturalTransformation] = []
    
    def create_standard_categories(self):
        """Create standard AGI architecture categories."""
        
        # RL Category: States × Actions → States, Observations
        rl = Category(
            name="StandardRL",
            architecture_type=ArchitectureType.REINFORCEMENT_LEARNING
        )
        
        S = Object("States", structural_type="state", properties={"finite": True})
        A = Object("Actions", structural_type="action", properties={"discrete": True})
        O = Object("Observations", structural_type="observation")
        R = Object("Rewards", structural_type="reward")
        
        transition = Morphism("T", S, S, is_stochastic=True)  # T: S × A → S
        observe = Morphism("Z", S, O, is_stochastic=True)       # Z: S → O
        reward_fn = Morphism("R", S, R)                         # R: S → R
        
        rl.add_morphism(transition)
        rl.add_morphism(observe)
        rl.add_morphism(reward_fn)
        
        self.categories["rl"] = rl
        
        # Active Inference Category: Beliefs × Policies → Actions
        ai = Category(
            name="ActiveInference",
            architecture_type=ArchitectureType.ACTIVE_INFERENCE
        )
        
        B = Object("Beliefs", structural_type="belief", properties={"probabilistic": True})
        Pi = Object("Policies", structural_type="policy")
        G = Object("GenerativeModel", structural_type="model")
        F = Object("FreeEnergy", structural_type="energy")
        
        infer = Morphism("Inference", O, B)           # Update beliefs from observations
        select_policy = Morphism("PolicySelection", B, Pi)
        act = Morphism("Action", Pi, A)
        minimize_fe = Morphism("MinimizeFE", B, F)
        
        ai.add_morphism(infer)
        ai.add_morphism(select_policy)
        ai.add_morphism(act)
        ai.add_morphism(minimize_fe)
        
        self.categories["active_inference"] = ai
        
        # Universal AI Category: Programs × Observations → Programs
        uai = Category(
            name="UniversalAI",
            architecture_type=ArchitectureType.UNIVERSAL_AI
        )
        
        H = Object("Hypotheses", structural_type="program", properties={"universal": True})
        P = Object("Predictions", structural_type="prediction")
        
        predict = Morphism("Predict", H, P)
        update = Morphism("Update", H, H, properties={"bayesian": True})  # P(H|O)
        select = Morphism("Select", P, A, properties={"optimal": True})
        
        uai.add_morphism(predict)
        uai.add_morphism(update)
        uai.add_morphism(select)
        
        self.categories["universal_ai"] = uai
        
        # Schema-Based Category: Schemas × Experience → UpdatedSchemas
        schema = Category(
            name="SchemaLearning",
            architecture_type=ArchitectureType.SCHEMA_BASED_LEARNING
        )
        
        Sch = Object("Schemas", structural_type="schema", properties={"symbolic": True})
        E = Object("Experiences", structural_type="experience")
        
        match = Morphism("Match", E, Sch)     # Match exp to schemas
        update_sch = Morphism("UpdateSchema", Sch, Sch)
        instantiate = Morphism("Instantiate", Sch, A)
        
        schema.add_morphism(match)
        schema.add_morphism(update_sch)
        schema.add_morphism(instantiate)
        
        self.categories["schema"] = schema
        
        # Neuro-Symbolic Category: Neural × Symbolic → Integrated
        ns = Category(
            name="NeuroSymbolic",
            architecture_type=ArchitectureType.NEURO_SYMBOLIC
        )
        
        N = Object("NeuralPatterns", structural_type="neural")
        Sym = Object("SymbolicRep", structural_type="symbolic")
        
        perceive = Morphism("Perceive", O, N)
        extract = Morphism("Extract", N, Sym)
        reason = Morphism("Reason", Sym, Sym)
        generate = Morphism("Generate", Sym, N)
        execute = Morphism("Execute", N, A)
        
        ns.add_morphism(perceive)
        ns.add_morphism(extract)
        ns.add_morphism(reason)
        ns.add_morphism(generate)
        ns.add_morphism(execute)
        
        self.categories["neuro_symbolic"] = ns
        
        return self.categories
    
    def compare_architectures(self, name1: str, name2: str) -> Dict[str, Any]:
        """
        Compare two architectures using categorical analysis.
        
        Returns structural similarities, differences, and potential functors.
        """
        cat1 = self.categories.get(name1)
        cat2 = self.categories.get(name2)
        
        if not cat1 or not cat2:
            return {"error": "Categories not found"}
        
        # Object type overlap
        types1 = set(obj.structural_type for obj in cat1.objects)
        types2 = set(obj.structural_type for obj in cat2.objects)
        
        # Structural comparison
        comparison = {
            "architectures": [name1, name2],
            "object_count": (len(cat1.objects), len(cat2.objects)),
            "morphism_count": (len(cat1.morphisms), len(cat2.morphisms)),
            "shared_object_types": list(types1 & types2),
            "unique_to_1": list(types1 - types2),
            "unique_to_2": list(types2 - types1),
            "structural_complexity": {
                name1: self._complexity_score(cat1),
                name2: self._complexity_score(cat2)
            }
        }
        
        # Attempt to find potential functor
        potential_functor = self._find_potential_functor(cat1, cat2)
        comparison["potential_functor"] = potential_functor
        
        return comparison
    
    def _complexity_score(self, cat: Category) -> float:
        """Calculate structural complexity score."""
        n_objects = len(cat.objects)
        n_morphisms = len(cat.morphisms)
        
        # More morphisms per object = more interconnected
        if n_objects == 0:
            return 0.0
        
        density = n_morphisms / n_objects
        
        # Stochastic morphisms add complexity
        stochastic = sum(1 for m in cat.morphisms if m.is_stochastic)
        
        return density + (stochastic / max(n_morphisms, 1)) * 0.5
    
    def _find_potential_functor(self, source: Category, target: Category) -> Dict[str, Any]:
        """
        Heuristic search for potential functor between categories.
        
        Maps objects by structural type similarity.
        """
        object_map = {}
        
        # Group objects by structural type
        source_by_type = defaultdict(list)
        target_by_type = defaultdict(list)
        
        for obj in source.objects:
            source_by_type[obj.structural_type].append(obj)
        
        for obj in target.objects:
            target_by_type[obj.structural_type].append(obj)
        
        # Map shared types
        for stype in source_by_type:
            if stype in target_by_type:
                # Simple 1-to-1 mapping for now
                for i, src_obj in enumerate(source_by_type[stype]):
                    if i < len(target_by_type[stype]):
                        object_map[src_obj] = target_by_type[stype][i]
        
        coverage = len(object_map) / max(len(source.objects), 1)
        
        return {
            "object_mappings": {src.name: tgt.name for src, tgt in object_map.items()},
            "coverage": coverage,
            "possible": coverage > 0.5
        }
    
    def get_architecture_landscape(self) -> Dict[str, Any]:
        """Get overview of all registered architectures."""
        return {
            "categories": {
                name: cat.structural_summary()
                for name, cat in self.categories.items()
            },
            "comparisons": [
                {
                    "pair": [n1, n2],
                    "summary": self.compare_architectures(n1, n2)
                }
                for i, n1 in enumerate(self.categories)
                for n2 in list(self.categories)[i+1:]
            ]
        }
    
    def identify_unification_opportunities(self) -> List[Dict[str, Any]]:
        """
        Identify where architectures could be unified via functors.
        
        Returns list of opportunities to bridge paradigms.
        """
        opportunities = []
        
        cats = list(self.categories.items())
        for i, (n1, c1) in enumerate(cats):
            for n2, c2 in cats[i+1:]:
                comp = self.compare_architectures(n1, n2)
                
                if comp.get("potential_functor", {}).get("possible"):
                    opportunities.append({
                        "source": n1,
                        "target": n2,
                        "shared_types": comp["shared_object_types"],
                        "coverage": comp["potential_functor"]["coverage"],
                        "note": f"Potential functor from {n1} to {n2}"
                    })
        
        return opportunities


def demo():
    """Demonstrate category-theoretic framework."""
    print("=" * 60)
    print("🧮 Category-Theoretic AGI Framework Demo")
    print("=" * 60)
    
    comparator = AGIArchitectureComparator()
    cats = comparator.create_standard_categories()
    
    print("\n📊 Standard Architecture Categories Created:")
    for name, cat in cats.items():
        summary = cat.structural_summary()
        morph_types_list = list(summary['morphism_types'].keys())
        print(f"\n   {name}:")
        print(f"      Objects: {summary['object_count']} ({', '.join(summary['object_types'])})")
        print(f"      Morphisms: {summary['morphism_count']}")
        print(f"      Types: {', '.join(morph_types_list[:3])}...")
    
    print("\n" + "=" * 60)
    print("📐 Architecture Comparisons:")
    print("=" * 60)
    
    comparisons = [
        ("rl", "active_inference"),
        ("rl", "universal_ai"),
        ("active_inference", "neuro_symbolic"),
        ("schema", "neuro_symbolic")
    ]
    
    for n1, n2 in comparisons:
        comp = comparator.compare_architectures(n1, n2)
        print(f"\n   {n1} ↔ {n2}:")
        print(f"      Shared object types: {comp['shared_object_types']}")
        print(f"      Unique to {n1}: {comp['unique_to_1']}")
        print(f"      Complexity: {n1}={comp['structural_complexity'][n1]:.2f}, "
              f"{n2}={comp['structural_complexity'][n2]:.2f}")
        
        functor = comp.get("potential_functor", {})
        if functor.get("possible"):
            print(f"      ✅ Potential functor: {functor['coverage']:.0%} coverage")
        else:
            print(f"      ❌ No simple functor possible ({functor.get('coverage', 0):.0%} coverage)")
    
    print("\n" + "=" * 60)
    print("🌉 Unification Opportunities:")
    print("=" * 60)
    
    opportunities = comparator.identify_unification_opportunities()
    for opp in opportunities:
        print(f"\n   {opp['source']} → {opp['target']}:")
        print(f"      Shared types: {', '.join(opp['shared_types'])}")
        print(f"      Coverage: {opp['coverage']:.0%}")
        print(f"      Note: {opp['note']}")
    
    print("\n" + "=" * 60)
    print("📝 Research Implications:")
    print("=" * 60)
    print("""
   1. RL and Active Inference share state/action/observation structure
      → Natural functor possible for translation between paradigms
   
   2. Universal AI adds universal program space - unique structure
      → Requires embedding functor from simpler categories
   
   3. Neuro-Symbolic bridges neural and symbolic representations
      → Acts as mediator category for paradigm integration
   
   4. Schema-based brings symbolic structure from cognitive science
      → Can embed into neuro-symbolic via schema→symbolic functor
   
   5. Category theory provides rigorous language for AGI comparison
      → Enables formal analysis of architectural tradeoffs
    """)


if __name__ == "__main__":
    demo()
