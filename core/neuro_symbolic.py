"""
Neuro-Symbolic Reasoning Module
Based on: ARC-AGI-3 insights (arXiv:2603.24621v1) + Category-Theoretic Framework (arXiv:2603.28906v1)

Core Insight from ARC-AGI-3: Current AI scores <1% on abstract reasoning tasks where humans score 100%.
The critical gap is compositional reasoning - the ability to:
1. Decompose problems into symbolic components
2. Apply neural pattern recognition to identify candidate transformations
3. Use symbolic constraints to filter and verify proposals
4. Compose verified sub-solutions into complete solutions

Architecture Pattern:
- PERCEPTION (Neural): Pattern recognition, candidate generation
- FILTERING (Symbolic): Constraint checking, rule-based validation  
- COMPOSITION (Hybrid): Symbolic structure + neural similarity

This implements the Neuro-Symbolic bridge pattern from category theory.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple, Set, Union
from enum import Enum, auto
from abc import ABC, abstractmethod
import json
import hashlib
from datetime import datetime


class ReasoningMode(Enum):
    """Neural vs Symbolic vs Hybrid reasoning modes."""
    NEURAL_ONLY = auto()      # Pure pattern recognition (fast, approximate)
    SYMBOLIC_ONLY = auto()   # Pure rule-based (slow, exact)
    NEURAL_FIRST = auto()    # Neural proposals, symbolic validation
    SYMBOLIC_FIRST = auto()  # Symbolic constraints guide neural search
    HYBRID_INTERLEAVED = auto()  # Alternating neural/symbolic steps


class PatternType(Enum):
    """Types of patterns the neural component can recognize."""
    VISUAL_GRID = "visual_grid"           # ARC-AGI style grid patterns
    SEQUENTIAL = "sequential"             # Step-by-step transformations
    COMPOSITIONAL = "compositional"     # Building complex from simple
    SYMMETRIC = "symmetric"               # Reflection, rotation invariance
    ABSTRACT_RELATION = "abstract_relation"  # Relational reasoning


@dataclass
class SymbolicConstraint:
    """Symbolic constraint for filtering neural proposals."""
    name: str
    check_function: Callable[[Any], bool]
    description: str
    strictness: float = 1.0  # 0.0-1.0, how strictly to enforce
    
    def check(self, candidate: Any) -> Tuple[bool, float]:
        """Check constraint, returns (passed, confidence)."""
        try:
            result = self.check_function(candidate)
            if isinstance(result, tuple):
                return result
            return result, self.strictness
        except Exception as e:
            return False, 0.0


@dataclass
class PatternTemplate:
    """Symbolic template for compositional reasoning."""
    name: str
    variables: List[str]
    structure: Dict[str, Any]
    composition_rules: List[Callable] = field(default_factory=list)
    
    def instantiate(self, bindings: Dict[str, Any]) -> Dict[str, Any]:
        """Create concrete instance from symbolic bindings."""
        instance = json.loads(json.dumps(self.structure))  # Deep copy
        
        def fill_vars(obj):
            if isinstance(obj, dict):
                return {k: fill_vars(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [fill_vars(item) for item in obj]
            elif isinstance(obj, str) and obj.startswith("$"):
                var_name = obj[1:]
                return bindings.get(var_name, obj)
            return obj
        
        return fill_vars(instance)
    
    def compose_with(self, other: 'PatternTemplate', 
                     composition_fn: Callable) -> 'PatternTemplate':
        """Compose two templates into a new template."""
        new_vars = list(set(self.variables + other.variables))
        new_structure = composition_fn(self.structure, other.structure)
        
        return PatternTemplate(
            name=f"{self.name}_composed_{other.name}",
            variables=new_vars,
            structure=new_structure,
            composition_rules=self.composition_rules + other.composition_rules
        )


@dataclass
class NeuralProposal:
    """Output from neural pattern recognition."""
    pattern_type: PatternType
    confidence: float
    candidate_solution: Any
    embedding: List[float]  # Neural embedding for similarity matching
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_hash(self) -> str:
        """Hash for deduplication."""
        content = f"{self.pattern_type.value}:{self.confidence}:{hash(str(self.candidate_solution))}"
        return hashlib.md5(content.encode()).hexdigest()


@dataclass
class VerifiedSolution:
    """Solution verified through symbolic constraints."""
    proposal: NeuralProposal
    passed_constraints: List[str]
    failed_constraints: List[str]
    verification_score: float
    compositional_steps: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def is_valid(self) -> bool:
        return len(self.failed_constraints) == 0 and self.verification_score > 0.8


class NeuralPerceptionModule:
    """
    Neural pattern recognition component.
    In real implementation, this would use actual neural networks.
    Here we simulate with pattern matching functions.
    """
    
    def __init__(self):
        self.pattern_recognizers: Dict[PatternType, Callable] = {}
        self.embeddings_cache: Dict[str, List[float]] = {}
        
    def register_recognizer(self, pattern_type: PatternType, 
                           recognizer_fn: Callable[[Any], List[NeuralProposal]]):
        """Register a neural recognizer for a pattern type."""
        self.pattern_recognizers[pattern_type] = recognizer_fn
    
    def generate_proposals(self, problem: Any, 
                          pattern_types: Optional[List[PatternType]] = None) -> List[NeuralProposal]:
        """Generate candidate solutions using neural pattern recognition."""
        if pattern_types is None:
            pattern_types = list(self.pattern_recognizers.keys())
        
        all_proposals = []
        
        for pt in pattern_types:
            if pt in self.pattern_recognizers:
                try:
                    proposals = self.pattern_recognizers[pt](problem)
                    all_proposals.extend(proposals)
                except Exception as e:
                    # Neural components can fail - that's expected
                    pass
        
        # Sort by confidence
        all_proposals.sort(key=lambda p: p.confidence, reverse=True)
        return all_proposals
    
    def compute_similarity(self, proposal1: NeuralProposal, 
                        proposal2: NeuralProposal) -> float:
        """Compute neural similarity between proposals."""
        # Cosine similarity between embeddings
        emb1 = proposal1.embedding
        emb2 = proposal2.embedding
        
        if len(emb1) != len(emb2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(emb1, emb2))
        norm1 = sum(a * a for a in emb1) ** 0.5
        norm2 = sum(b * b for b in emb2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)


class SymbolicConstraintModule:
    """
    Symbolic constraint checking and rule-based validation.
    """
    
    def __init__(self):
        self.constraints: Dict[str, SymbolicConstraint] = {}
        self.templates: Dict[str, PatternTemplate] = {}
        
    def register_constraint(self, constraint: SymbolicConstraint):
        """Register a symbolic constraint."""
        self.constraints[constraint.name] = constraint
    
    def register_template(self, template: PatternTemplate):
        """Register a pattern template for compositional reasoning."""
        self.templates[template.name] = template
    
    def verify_proposal(self, proposal: NeuralProposal, 
                       active_constraints: Optional[List[str]] = None,
                       mode: ReasoningMode = ReasoningMode.NEURAL_FIRST) -> VerifiedSolution:
        """Verify a neural proposal against symbolic constraints."""
        if active_constraints is None:
            active_constraints = list(self.constraints.keys())
        
        passed = []
        failed = []
        total_confidence = 0.0
        
        for constraint_name in active_constraints:
            if constraint_name in self.constraints:
                constraint = self.constraints[constraint_name]
                result, confidence = constraint.check(proposal.candidate_solution)
                
                if result:
                    passed.append(constraint_name)
                    total_confidence += confidence
                else:
                    failed.append(constraint_name)
                    if mode == ReasoningMode.SYMBOLIC_ONLY:
                        # In symbolic-only mode, any failure invalidates
                        break
        
        # Calculate verification score
        if len(active_constraints) > 0:
            verification_score = total_confidence / len(active_constraints)
        else:
            verification_score = 1.0
        
        return VerifiedSolution(
            proposal=proposal,
            passed_constraints=passed,
            failed_constraints=failed,
            verification_score=verification_score
        )
    
    def compose_templates(self, template_names: List[str], 
                         bindings: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Compose multiple templates into a structured solution."""
        if not template_names:
            return None
        
        # Start with first template
        first_template = self.templates.get(template_names[0])
        if not first_template:
            return None
        
        result = first_template.instantiate(bindings)
        
        # Compose remaining templates
        for template_name in template_names[1:]:
            template = self.templates.get(template_name)
            if template:
                # Apply composition rules
                for rule in template.composition_rules:
                    try:
                        result = rule(result, template.instantiate(bindings))
                    except:
                        pass
        
        return result


@dataclass
class ReasoningStep:
    """A single step in the reasoning process."""
    step_number: int
    mode: ReasoningMode
    input_data: Any
    neural_proposals: List[NeuralProposal] = field(default_factory=list)
    verified_solutions: List[VerifiedSolution] = field(default_factory=list)
    symbolic_bindings: Dict[str, Any] = field(default_factory=dict)
    templates_used: List[str] = field(default_factory=list)
    sub_problems: List[Any] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize step for logging/debugging."""
        return {
            "step": self.step_number,
            "mode": self.mode.name,
            "proposals_generated": len(self.neural_proposals),
            "solutions_verified": len(self.verified_solutions),
            "valid_solutions": sum(1 for s in self.verified_solutions if s.is_valid),
            "templates": self.templates_used,
            "sub_problems_decomposed": len(self.sub_problems)
        }


class CompositionalReasoningEngine:
    """
    Hybrid neuro-symbolic reasoning engine for compositional problems.
    Implements the pattern: Decompose → Propose (neural) → Filter (symbolic) → Compose → Verify
    """
    
    def __init__(self, 
                 neural_module: Optional[NeuralPerceptionModule] = None,
                 symbolic_module: Optional[SymbolicConstraintModule] = None):
        self.neural = neural_module or NeuralPerceptionModule()
        self.symbolic = symbolic_module or SymbolicConstraintModule()
        self.reasoning_history: List[ReasoningStep] = []
        self.max_steps = 10
        self.min_confidence = 0.7
        
    def solve(self, problem: Any, 
             mode: ReasoningMode = ReasoningMode.NEURAL_FIRST,
             max_proposals: int = 5) -> Tuple[Optional[VerifiedSolution], List[ReasoningStep]]:
        """
        Solve a problem using neuro-symbolic reasoning.
        
        Returns:
            (best_solution, reasoning_trace)
        """
        self.reasoning_history = []
        
        # Step 1: Decompose problem
        sub_problems = self._decompose(problem)
        
        if len(sub_problems) == 1:
            # Single-step problem
            solution = self._solve_single(problem, mode, max_proposals)
            return solution, self.reasoning_history
        
        # Multi-step compositional problem
        sub_solutions = []
        for i, sub_problem in enumerate(sub_problems):
            solution = self._solve_single(sub_problem, mode, max_proposals)
            if solution and solution.is_valid:
                sub_solutions.append(solution)
            else:
                # Failed to solve sub-problem
                return None, self.reasoning_history
        
        # Compose sub-solutions
        final_solution = self._compose_solutions(sub_solutions, problem)
        
        return final_solution, self.reasoning_history
    
    def _decompose(self, problem: Any) -> List[Any]:
        """Decompose problem into sub-problems."""
        # Use symbolic patterns to guide decomposition
        decomposition_patterns = [
            lambda p: [p],  # Atomic - no decomposition
            lambda p: self._try_grid_decomposition(p),
            lambda p: self._try_sequential_decomposition(p),
        ]
        
        for pattern in decomposition_patterns:
            result = pattern(problem)
            if result and len(result) > 0:
                return result
        
        return [problem]  # Default: treat as atomic
    
    def _try_grid_decomposition(self, problem: Any) -> Optional[List[Any]]:
        """Decompose grid-based problems (ARC-AGI style)."""
        if not isinstance(problem, dict):
            return None
        
        if "grid" in problem or "input" in problem:
            # Could decompose by regions, colors, or objects
            # For now, return as single problem
            pass
        
        return None
    
    def _try_sequential_decomposition(self, problem: Any) -> Optional[List[Any]]:
        """Decompose sequential problems."""
        if isinstance(problem, list) and len(problem) > 1:
            return problem
        return None
    
    def _solve_single(self, problem: Any, mode: ReasoningMode, 
                    max_proposals: int) -> Optional[VerifiedSolution]:
        """Solve a single (non-decomposed) problem."""
        step = ReasoningStep(
            step_number=len(self.reasoning_history) + 1,
            mode=mode,
            input_data=problem
        )
        
        # Generate neural proposals
        proposals = self.neural.generate_proposals(problem)
        step.neural_proposals = proposals[:max_proposals]
        
        if not proposals:
            self.reasoning_history.append(step)
            return None
        
        # Verify proposals with symbolic constraints
        verified = []
        for proposal in proposals[:max_proposals]:
            solution = self.symbolic.verify_proposal(proposal, mode=mode)
            verified.append(solution)
            
            if solution.is_valid and mode == ReasoningMode.NEURAL_FIRST:
                # In neural-first mode, return first valid solution
                step.verified_solutions = verified
                self.reasoning_history.append(step)
                return solution
        
        step.verified_solutions = verified
        
        # Return best solution
        valid_solutions = [s for s in verified if s.is_valid]
        if valid_solutions:
            best = max(valid_solutions, key=lambda s: s.verification_score)
        else:
            # No valid solutions - return best effort
            best = max(verified, key=lambda s: s.verification_score) if verified else None
        
        self.reasoning_history.append(step)
        return best
    
    def _compose_solutions(self, sub_solutions: List[VerifiedSolution], 
                          original_problem: Any) -> VerifiedSolution:
        """Compose multiple sub-solutions into final solution."""
        # Create a composite proposal
        composed_candidate = {
            "type": "composed",
            "parts": [s.proposal.candidate_solution for s in sub_solutions],
            "verification_scores": [s.verification_score for s in sub_solutions]
        }
        
        composed_proposal = NeuralProposal(
            pattern_type=PatternType.COMPOSITIONAL,
            confidence=min(s.proposal.confidence for s in sub_solutions),
            candidate_solution=composed_candidate,
            embedding=[],  # Would compute from parts
            metadata={"composed_from": len(sub_solutions)}
        )
        
        # Verify the composition
        verified = self.symbolic.verify_proposal(
            composed_proposal, 
            mode=ReasoningMode.HYBRID_INTERLEAVED
        )
        
        verified.compositional_steps = [
            {"sub_solution": i, "verification": s.verification_score}
            for i, s in enumerate(sub_solutions)
        ]
        
        return verified
    
    def explain_reasoning(self) -> Dict[str, Any]:
        """Generate explanation of the reasoning process."""
        return {
            "total_steps": len(self.reasoning_history),
            "steps": [step.to_dict() for step in self.reasoning_history],
            "neural_proposals_total": sum(len(s.neural_proposals) for s in self.reasoning_history),
            "solutions_verified_total": sum(len(s.verified_solutions) for s in self.reasoning_history),
            "valid_solutions_total": sum(
                sum(1 for sol in s.verified_solutions if sol.is_valid)
                for s in self.reasoning_history
            )
        }


# Default recognizers for common ARC-AGI style patterns

def create_default_neural_recognizers() -> Dict[PatternType, Callable]:
    """Create default pattern recognizers for ARC-AGI style problems."""
    
    def recognize_grid_patterns(problem: Any) -> List[NeuralProposal]:
        """Recognize patterns in grid-based problems."""
        proposals = []
        
        # Check if it's a grid problem
        if isinstance(problem, dict) and "input" in problem:
            grid = problem["input"]
            
            if isinstance(grid, list) and len(grid) > 0:
                # Pattern: Identity transformation
                proposals.append(NeuralProposal(
                    pattern_type=PatternType.VISUAL_GRID,
                    confidence=0.6,
                    candidate_solution=grid,
                    embedding=[1.0, 0.0, 0.0],  # Identity embedding
                    metadata={"pattern": "identity"}
                ))
                
                # Pattern: Horizontal flip
                flipped = [row[::-1] for row in grid]
                proposals.append(NeuralProposal(
                    pattern_type=PatternType.VISUAL_GRID,
                    confidence=0.5,
                    candidate_solution=flipped,
                    embedding=[0.0, 1.0, 0.0],  # Flip embedding
                    metadata={"pattern": "horizontal_flip"}
                ))
                
                # Pattern: Rotation
                if len(grid) == len(grid[0]) if grid else False:
                    rotated = [[grid[len(grid)-1-j][i] for j in range(len(grid))] 
                              for i in range(len(grid[0]))]
                    proposals.append(NeuralProposal(
                        pattern_type=PatternType.VISUAL_GRID,
                        confidence=0.4,
                        candidate_solution=rotated,
                        embedding=[0.0, 0.0, 1.0],  # Rotation embedding
                        metadata={"pattern": "rotate_90"}
                    ))
        
        return proposals
    
    def recognize_sequential_patterns(problem: Any) -> List[NeuralProposal]:
        """Recognize sequential transformation patterns."""
        proposals = []
        
        if isinstance(problem, list) and len(problem) >= 2:
            # Pattern: Identity sequence
            proposals.append(NeuralProposal(
                pattern_type=PatternType.SEQUENTIAL,
                confidence=0.7,
                candidate_solution=problem,
                embedding=[1.0, 0.0],
                metadata={"pattern": "identity_sequence"}
            ))
            
            # Pattern: Reverse sequence
            proposals.append(NeuralProposal(
                pattern_type=PatternType.SEQUENTIAL,
                confidence=0.5,
                candidate_solution=problem[::-1],
                embedding=[0.0, 1.0],
                metadata={"pattern": "reverse_sequence"}
            ))
        
        return proposals
    
    def recognize_abstract_relations(problem: Any) -> List[NeuralProposal]:
        """Recognize abstract relational patterns."""
        proposals = []
        
        # Generic pattern: Empty/no-op
        proposals.append(NeuralProposal(
            pattern_type=PatternType.ABSTRACT_RELATION,
            confidence=0.3,
            candidate_solution=None,
            embedding=[0.5, 0.5, 0.5],
            metadata={"pattern": "no_op"}
        ))
        
        return proposals
    
    return {
        PatternType.VISUAL_GRID: recognize_grid_patterns,
        PatternType.SEQUENTIAL: recognize_sequential_patterns,
        PatternType.ABSTRACT_RELATION: recognize_abstract_relations,
    }


def create_default_constraints() -> List[SymbolicConstraint]:
    """Create default symbolic constraints for verification."""
    
    def is_valid_grid(solution: Any) -> Tuple[bool, float]:
        """Check if solution is a valid grid."""
        if not isinstance(solution, list):
            return False, 0.0
        if len(solution) == 0:
            return False, 0.0
        row_lengths = [len(row) for row in solution if isinstance(row, list)]
        if not row_lengths:
            return False, 0.0
        if len(set(row_lengths)) != 1:
            return False, 0.3  # Partial credit for almost valid
        return True, 1.0
    
    def is_non_empty(solution: Any) -> Tuple[bool, float]:
        """Check if solution has content."""
        if solution is None:
            return False, 0.0
        if isinstance(solution, list) and len(solution) == 0:
            return False, 0.0
        if isinstance(solution, dict) and len(solution) == 0:
            return False, 0.0
        return True, 1.0
    
    def size_consistent(solution: Any) -> Tuple[bool, float]:
        """Check size consistency for grid solutions."""
        if not isinstance(solution, list):
            return True, 1.0  # Non-grid passes this constraint
        if len(solution) == 0:
            return False, 0.0
        # Reasonable grid size
        if len(solution) > 50:
            return False, 0.5
        return True, 1.0
    
    return [
        SymbolicConstraint("valid_grid", is_valid_grid, "Solution must be a valid grid structure"),
        SymbolicConstraint("non_empty", is_non_empty, "Solution must not be empty"),
        SymbolicConstraint("size_consistent", size_consistent, "Grid size must be reasonable"),
    ]


def create_default_templates() -> List[PatternTemplate]:
    """Create default pattern templates for compositional reasoning."""
    
    return [
        PatternTemplate(
            name="grid_transform",
            variables=["input_grid", "transformation"],
            structure={
                "operation": "$transformation",
                "input": "$input_grid",
                "output": None  # To be filled
            },
            composition_rules=[
                lambda a, b: {**a, "chained_with": b} if isinstance(a, dict) else a
            ]
        ),
        PatternTemplate(
            name="sequence_step",
            variables=["step_index", "operation"],
            structure={
                "step": "$step_index",
                "action": "$operation",
                "result": None
            }
        ),
    ]


# Factory function to create a fully configured engine

def create_neuro_symbolic_engine(
    custom_recognizers: Optional[Dict[PatternType, Callable]] = None,
    custom_constraints: Optional[List[SymbolicConstraint]] = None,
    custom_templates: Optional[List[PatternTemplate]] = None
) -> CompositionalReasoningEngine:
    """
    Create a neuro-symbolic reasoning engine with default or custom components.
    
    This implements the bridge pattern from category theory:
    - NeuralPerceptionModule → Pattern recognition (neural side)
    - SymbolicConstraintModule → Rule validation (symbolic side)  
    - CompositionalReasoningEngine → Hybrid reasoning (bridge)
    """
    
    # Create modules
    neural = NeuralPerceptionModule()
    symbolic = SymbolicConstraintModule()
    
    # Register default recognizers (or custom ones)
    recognizers = custom_recognizers or create_default_neural_recognizers()
    for pattern_type, recognizer in recognizers.items():
        neural.register_recognizer(pattern_type, recognizer)
    
    # Register default constraints (or custom ones)
    constraints = custom_constraints or create_default_constraints()
    for constraint in constraints:
        symbolic.register_constraint(constraint)
    
    # Register default templates (or custom ones)
    templates = custom_templates or create_default_templates()
    for template in templates:
        symbolic.register_template(template)
    
    # Create and return engine
    engine = CompositionalReasoningEngine(neural, symbolic)
    return engine
