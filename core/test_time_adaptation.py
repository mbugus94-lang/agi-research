"""
Test-Time Adaptation System

Implements dynamic refinement during task execution inspired by ARC-AGI success patterns.
Key capabilities:
- Progressive hypothesis exploration with budget management
- Cost-efficient inference-time optimization  
- MDL-based compression for efficient representation
- Adaptive hypothesis generation and verification

Research basis:
- ARC-AGI-3 shows test-time adaptation is critical (frontier AI <1% without it)
- CompressARC: MDL-based inference achieves ~20% on ARC-AGI-1 without pretraining
- Geometry of Benchmarks (arXiv:2512.04276): GVU operator for self-improvement
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Callable, Optional, Tuple
from enum import Enum
import time
import math


class AdaptationStrategy(Enum):
    """Strategies for test-time adaptation."""
    PROGRESSIVE_REFINEMENT = "progressive"  # Iterative improvement
    HYPOTHESIS_EXPLORATION = "exploration"    # Generate and test hypotheses
    MDL_COMPRESSION = "mdl"                   # Minimum description length
    ENSEMBLE_VOTING = "ensemble"              # Multiple models vote


@dataclass
class Hypothesis:
    """A candidate solution with metadata."""
    id: str
    content: Any
    confidence: float  # 0.0 to 1.0
    generation_cost: float  # Token or compute cost
    verification_score: Optional[float] = None
    parent_id: Optional[str] = None  # For tracking lineage
    generation_time: float = field(default_factory=time.time)
    
    def total_cost(self) -> float:
        """Total cost including verification if available."""
        base = self.generation_cost
        if self.verification_score is not None:
            base += 0.1  # Verification overhead
        return base


@dataclass  
class BudgetState:
    """Tracks resource consumption during adaptation."""
    total_budget: float
    used_budget: float = 0.0
    hypothesis_count: int = 0
    verification_count: int = 0
    start_time: float = field(default_factory=time.time)
    
    def remaining(self) -> float:
        return self.total_budget - self.used_budget
    
    def is_exhausted(self) -> bool:
        return self.used_budget >= self.total_budget
    
    def utilization_rate(self) -> float:
        """Budget consumption rate per second."""
        elapsed = time.time() - self.start_time
        if elapsed == 0:
            return 0.0
        return self.used_budget / elapsed


@dataclass
class AdaptationResult:
    """Result of test-time adaptation."""
    final_output: Any
    selected_hypothesis: Optional[Hypothesis]
    all_hypotheses: List[Hypothesis]
    iterations: int
    total_cost: float
    strategy: AdaptationStrategy
    improvement_trace: List[Dict[str, Any]]
    early_stopped: bool
    
    def efficiency_score(self) -> float:
        """Score based on quality per unit cost."""
        if self.total_cost == 0:
            return 0.0
        quality = self.selected_hypothesis.confidence if self.selected_hypothesis else 0.0
        return quality / math.log(1 + self.total_cost)  # Log-scaled cost


class HypothesisGenerator:
    """Generates candidate hypotheses for a problem."""
    
    def __init__(self, generator_fn: Callable[[Any, Dict], Any], cost_per_call: float = 1.0):
        self.generator_fn = generator_fn
        self.cost_per_call = cost_per_call
        self._call_count = 0
    
    def generate(self, problem: Any, context: Dict, budget: BudgetState) -> Optional[Hypothesis]:
        """Generate a new hypothesis if budget allows."""
        if budget.remaining() < self.cost_per_call:
            return None
        
        self._call_count += 1
        hypothesis_id = f"h_{self._call_count}_{int(time.time() * 1000) % 10000}"
        
        try:
            content = self.generator_fn(problem, context)
            confidence = self._estimate_confidence(content, problem)
            
            budget.used_budget += self.cost_per_call
            budget.hypothesis_count += 1
            
            return Hypothesis(
                id=hypothesis_id,
                content=content,
                confidence=confidence,
                generation_cost=self.cost_per_call
            )
        except Exception as e:
            return Hypothesis(
                id=hypothesis_id,
                content=None,
                confidence=0.0,
                generation_cost=self.cost_per_call
            )
    
    def generate_multiple(self, problem: Any, context: Dict, budget: BudgetState, 
                         n: int) -> List[Hypothesis]:
        """Generate up to n hypotheses within budget."""
        hypotheses = []
        for _ in range(n):
            if budget.is_exhausted():
                break
            h = self.generate(problem, context, budget)
            if h:
                hypotheses.append(h)
        return hypotheses
    
    def _estimate_confidence(self, content: Any, problem: Any) -> float:
        """Estimate confidence based on content properties."""
        # Simple heuristics - can be replaced with learned confidence model
        if content is None:
            return 0.0
        
        confidence = 0.5  # Base confidence
        
        # Prefer non-empty, structured outputs
        if isinstance(content, (list, dict)) and len(content) > 0:
            confidence += 0.2
        
        # Prefer specific formats (ARC-AGI: grids with consistent structure)
        if isinstance(content, list) and all(isinstance(row, list) for row in content):
            confidence += 0.15  # Grid structure detected
        
        return min(confidence, 1.0)


class HypothesisVerifier:
    """Verifies hypotheses against constraints or examples."""
    
    def __init__(self, verifier_fn: Callable[[Any, Any], Tuple[bool, float]], 
                 cost_per_verify: float = 0.1):
        self.verifier_fn = verifier_fn
        self.cost_per_verify = cost_per_verify
    
    def verify(self, hypothesis: Hypothesis, problem: Any, budget: BudgetState) -> float:
        """Verify a hypothesis and update its score. Returns verification score."""
        if budget.remaining() < self.cost_per_verify:
            return hypothesis.confidence  # Can't verify, use generation confidence
        
        budget.used_budget += self.cost_per_verify
        budget.verification_count += 1
        
        try:
            passed, score = self.verifier_fn(hypothesis.content, problem)
            hypothesis.verification_score = score if passed else score * 0.5
            return hypothesis.verification_score
        except Exception:
            hypothesis.verification_score = 0.0
            return 0.0


class MDLCompressor:
    """
    Minimum Description Length compression for efficient representation.
    Based on CompressARC approach (arXiv:2512.06104).
    """
    
    def description_length(self, data: Any) -> float:
        """Calculate description length of data."""
        if data is None:
            return float('inf')
        
        if isinstance(data, str):
            return len(data.encode('utf-8')) * 8  # Bits
        
        if isinstance(data, (list, tuple)):
            # Grid structures (ARC-AGI style)
            if data and isinstance(data[0], list):
                rows = len(data)
                cols = len(data[0]) if data[0] else 0
                # Count unique values for complexity
                flat = [cell for row in data for cell in row]
                unique = len(set(flat))
                return rows * cols * math.log2(max(unique, 2))
            else:
                return len(data) * 32  # Assume 32 bits per element
        
        if isinstance(data, dict):
            return sum(self.description_length(k) + self.description_length(v) 
                      for k, v in data.items())
        
        return 32  # Default: 32 bits
    
    def compression_ratio(self, original: Any, compressed: Any) -> float:
        """Calculate compression ratio."""
        orig_len = self.description_length(original)
        comp_len = self.description_length(compressed)
        if comp_len == 0:
            return float('inf')
        return orig_len / comp_len
    
    def is_compressible(self, data: Any, threshold: float = 2.0) -> bool:
        """Check if data shows compressible structure."""
        # Simple pattern: repeated elements indicate compressibility
        dl = self.description_length(data)
        
        # Estimate compressed size (run-length encoding approximation)
        if isinstance(data, list) and data:
            if isinstance(data[0], list):
                # Grid - check for row patterns
                row_patterns = set(tuple(row) for row in data)
                compressed_estimate = len(row_patterns) * self.description_length(data[0])
                return dl / compressed_estimate > threshold
        
        return False


class TestTimeAdapter:
    """
    Main test-time adaptation engine.
    Implements progressive refinement with budget management.
    """
    
    def __init__(self, 
                 generator: HypothesisGenerator,
                 verifier: Optional[HypothesisVerifier] = None,
                 strategy: AdaptationStrategy = AdaptationStrategy.PROGRESSIVE_REFINEMENT):
        self.generator = generator
        self.verifier = verifier
        self.strategy = strategy
        self.mdl_compressor = MDLCompressor()
        self._iteration_count = 0
    
    def adapt(self, problem: Any, 
              budget: float = 10.0,
              min_iterations: int = 3,
              max_iterations: int = 20,
              improvement_threshold: float = 0.01) -> AdaptationResult:
        """
        Run test-time adaptation on a problem.
        
        Args:
            problem: The problem to solve
            budget: Total compute budget (token or cost units)
            min_iterations: Minimum iterations before early stopping
            max_iterations: Hard maximum iterations
            improvement_threshold: Minimum improvement to continue
        
        Returns:
            AdaptationResult with final output and metadata
        """
        budget_state = BudgetState(total_budget=budget)
        hypotheses: List[Hypothesis] = []
        improvement_trace: List[Dict[str, Any]] = []
        
        best_score = 0.0
        stall_count = 0
        
        for iteration in range(max_iterations):
            self._iteration_count += 1
            
            if budget_state.is_exhausted():
                break
            
            # Generate new hypotheses based on strategy
            new_hyps = self._generate_batch(problem, hypotheses, budget_state)
            
            # Verify if verifier available
            if self.verifier:
                for h in new_hyps:
                    if budget_state.is_exhausted():
                        break
                    self.verifier.verify(h, problem, budget_state)
            
            hypotheses.extend(new_hyps)
            
            # Select best hypothesis
            best = self._select_best(hypotheses)
            current_score = best.verification_score if best and best.verification_score else 0.0
            
            # Track improvement
            improvement = current_score - best_score
            best_score = max(best_score, current_score)
            
            trace_entry = {
                'iteration': iteration,
                'hypotheses_count': len(hypotheses),
                'best_score': best_score,
                'budget_used': budget_state.used_budget,
                'improvement': improvement
            }
            improvement_trace.append(trace_entry)
            
            # Early stopping check
            if iteration >= min_iterations:
                if improvement < improvement_threshold:
                    stall_count += 1
                    if stall_count >= 3:  # Stall for 3 iterations
                        break
                else:
                    stall_count = 0
        
        # Final selection
        selected = self._select_best(hypotheses)
        
        return AdaptationResult(
            final_output=selected.content if selected else None,
            selected_hypothesis=selected,
            all_hypotheses=hypotheses,
            iterations=len(improvement_trace),
            total_cost=budget_state.used_budget,
            strategy=self.strategy,
            improvement_trace=improvement_trace,
            early_stopped=stall_count >= 3
        )
    
    def _generate_batch(self, problem: Any, 
                       existing: List[Hypothesis],
                       budget: BudgetState) -> List[Hypothesis]:
        """Generate a batch of hypotheses based on strategy."""
        
        if self.strategy == AdaptationStrategy.PROGRESSIVE_REFINEMENT:
            # Generate 1-2 hypotheses, building on best so far
            context = {'phase': 'refinement', 'existing_count': len(existing)}
            if existing:
                best = max(existing, key=lambda h: h.confidence)
                context['best_confidence'] = best.confidence
            return self.generator.generate_multiple(problem, context, budget, 2)
        
        elif self.strategy == AdaptationStrategy.HYPOTHESIS_EXPLORATION:
            # Generate diverse hypotheses
            context = {'phase': 'exploration', 'diversity_target': True}
            return self.generator.generate_multiple(problem, context, budget, 3)
        
        elif self.strategy == AdaptationStrategy.MDL_COMPRESSION:
            # Generate and check compressibility
            context = {'phase': 'mdl_optimization'}
            hyps = self.generator.generate_multiple(problem, context, budget, 2)
            # Filter for compressible solutions
            return [h for h in hyps if self.mdl_compressor.is_compressible(h.content)]
        
        elif self.strategy == AdaptationStrategy.ENSEMBLE_VOTING:
            # Generate multiple for ensemble
            context = {'phase': 'ensemble'}
            return self.generator.generate_multiple(problem, context, budget, 5)
        
        return []
    
    def _select_best(self, hypotheses: List[Hypothesis]) -> Optional[Hypothesis]:
        """Select best hypothesis from pool."""
        if not hypotheses:
            return None
        
        def score(h: Hypothesis) -> float:
            if h.verification_score is not None:
                return h.verification_score
            return h.confidence
        
        return max(hypotheses, key=score)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get adaptation statistics."""
        return {
            'total_iterations': self._iteration_count,
            'strategy': self.strategy.value,
            'has_verifier': self.verifier is not None
        }


class ARCAdaptationSolver:
    """
    Specialized adapter for ARC-AGI style problems.
    Combines test-time adaptation with pattern-based reasoning.
    """
    
    def __init__(self, budget_per_problem: float = 50.0):
        # Generator for grid transformations
        def grid_generator(problem: Dict, context: Dict) -> Any:
            """Generate candidate grid transformations."""
            train_pairs = problem.get('train', [])
            test_input = problem.get('test', {}).get('input', [])
            
            if not train_pairs or not test_input:
                return None
            
            # Extract patterns from training
            patterns = self._extract_patterns(train_pairs)
            
            # Apply to test input
            return self._apply_patterns(test_input, patterns)
        
        # Verifier for grid predictions
        def grid_verifier(output: Any, problem: Dict) -> Tuple[bool, float]:
            """Verify grid output against constraints."""
            if not isinstance(output, list):
                return False, 0.0
            
            test_input = problem.get('test', {}).get('input', [])
            
            # Basic validity checks
            if not output or not isinstance(output[0], list):
                return False, 0.0
            
            score = 0.5  # Base score for valid structure
            
            # Size consistency with input (common ARC pattern)
            input_rows = len(test_input)
            input_cols = len(test_input[0]) if test_input else 0
            output_rows = len(output)
            output_cols = len(output[0]) if output else 0
            
            if input_rows == output_rows and input_cols == output_cols:
                score += 0.3  # Size preservation bonus
            
            # Value range check (ARC typically uses 0-9)
            flat = [cell for row in output for cell in row]
            if all(0 <= c <= 9 for c in flat):
                score += 0.2
            
            return True, min(score, 1.0)
        
        gen = HypothesisGenerator(grid_generator, cost_per_call=2.0)
        ver = HypothesisVerifier(grid_verifier, cost_per_verify=0.5)
        
        self.adapter = TestTimeAdapter(
            generator=gen,
            verifier=ver,
            strategy=AdaptationStrategy.HYPOTHESIS_EXPLORATION
        )
        self.budget = budget_per_problem
    
    def _extract_patterns(self, train_pairs: List[Dict]) -> List[Dict]:
        """Extract transformation patterns from training examples."""
        patterns = []
        
        for pair in train_pairs:
            inp = pair.get('input', [])
            out = pair.get('output', [])
            
            if not inp or not out:
                continue
            
            # Detect common patterns
            pattern = {'type': 'unknown'}
            
            # Check size changes
            in_rows, in_cols = len(inp), len(inp[0]) if inp else 0
            out_rows, out_cols = len(out), len(out[0]) if out else 0
            
            if in_rows == out_rows and in_cols == out_cols:
                pattern['size_change'] = 'none'
            else:
                pattern['size_change'] = f'{in_rows}x{in_cols}->{out_rows}x{out_cols}'
            
            # Check value preservation
            in_vals = set(cell for row in inp for cell in row)
            out_vals = set(cell for row in out for cell in row)
            pattern['value_change'] = 'preserved' if in_vals == out_vals else 'modified'
            
            patterns.append(pattern)
        
        return patterns
    
    def _apply_patterns(self, test_input: List, patterns: List[Dict]) -> List:
        """Apply extracted patterns to test input."""
        if not test_input:
            return []
        
        # Default: identity transformation
        output = [row[:] for row in test_input]  # Deep copy
        
        # Apply detected patterns
        for pattern in patterns:
            if pattern.get('size_change') == 'none':
                # Try value mapping
                if pattern.get('value_change') == 'preserved':
                    # Likely a geometric or structural transformation
                    pass  # Keep as-is for now
        
        return output
    
    def solve(self, arc_problem: Dict) -> AdaptationResult:
        """Solve an ARC-AGI style problem."""
        return self.adapter.adapt(
            problem=arc_problem,
            budget=self.budget,
            min_iterations=2,
            max_iterations=15,
            improvement_threshold=0.05
        )


def create_adaptive_solver(strategy: str = "progressive",
                          budget: float = 10.0,
                          custom_generator: Optional[Callable] = None,
                          custom_verifier: Optional[Callable] = None) -> TestTimeAdapter:
    """
    Factory function to create a test-time adaptation solver.
    
    Args:
        strategy: 'progressive', 'exploration', 'mdl', or 'ensemble'
        budget: Total compute budget
        custom_generator: Optional custom hypothesis generator function
        custom_verifier: Optional custom verifier function (returns (passed, score))
    
    Returns:
        Configured TestTimeAdapter instance
    """
    strategy_enum = AdaptationStrategy(strategy)
    
    # Default simple generator
    if custom_generator is None:
        def default_generator(problem: Any, context: Dict) -> Any:
            return {"solution": str(problem), "timestamp": time.time()}
        custom_generator = default_generator
    
    gen = HypothesisGenerator(custom_generator, cost_per_call=1.0)
    
    ver = None
    if custom_verifier:
        ver = HypothesisVerifier(custom_verifier, cost_per_verify=0.5)
    
    return TestTimeAdapter(gen, ver, strategy_enum)


# Example usage patterns
if __name__ == "__main__":
    # Demo 1: Simple progressive refinement
    print("=== Demo 1: Progressive Refinement ===")
    
    def demo_generator(problem: str, context: Dict) -> str:
        import random
        attempts = context.get('existing_count', 0)
        # Simulate improvement over iterations
        quality = min(0.9, 0.3 + attempts * 0.1 + random.uniform(-0.1, 0.1))
        return f"solution_v{attempts}_quality{quality:.2f}"
    
    def demo_verifier(output: str, problem: str) -> Tuple[bool, float]:
        # Extract quality from output string
        if "quality" in output:
            q = float(output.split("quality")[1].split("_")[0])
            return True, q
        return False, 0.0
    
    adapter = create_adaptive_solver(
        strategy="progressive",
        budget=5.0,
        custom_generator=demo_generator,
        custom_verifier=demo_verifier
    )
    
    result = adapter.adapt("test_problem", budget=5.0, max_iterations=10)
    print(f"Iterations: {result.iterations}")
    print(f"Total cost: {result.total_cost}")
    print(f"Early stopped: {result.early_stopped}")
    print(f"Final output: {result.final_output}")
    print(f"Efficiency score: {result.efficiency_score():.3f}")
    
    # Demo 2: ARC-style grid problem
    print("\n=== Demo 2: ARC-AGI Style Grid Problem ===")
    
    arc_solver = ARCAdaptationSolver(budget_per_problem=20.0)
    
    # Simple ARC-like problem
    arc_problem = {
        'train': [
            {
                'input': [[1, 1], [1, 1]],
                'output': [[2, 2], [2, 2]]  # Pattern: add 1 to each cell
            },
            {
                'input': [[3, 3], [3, 3]],
                'output': [[4, 4], [4, 4]]
            }
        ],
        'test': {
            'input': [[5, 5], [5, 5]]  # Expected: [[6, 6], [6, 6]]
        }
    }
    
    arc_result = arc_solver.solve(arc_problem)
    print(f"ARC iterations: {arc_result.iterations}")
    print(f"ARC total cost: {arc_result.total_cost}")
    print(f"ARC output grid: {arc_result.final_output}")
    
    # Demo 3: MDL compression check
    print("\n=== Demo 3: MDL Compression Analysis ===")
    compressor = MDLCompressor()
    
    # Simple pattern (compressible)
    grid1 = [[1, 1, 1], [1, 1, 1], [1, 1, 1]]
    dl1 = compressor.description_length(grid1)
    comp1 = compressor.is_compressible(grid1)
    print(f"Uniform grid: DL={dl1:.1f}, compressible={comp1}")
    
    # Complex pattern (less compressible)
    grid2 = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    dl2 = compressor.description_length(grid2)
    comp2 = compressor.is_compressible(grid2)
    print(f"Varied grid: DL={dl2:.1f}, compressible={comp2}")
    
    print("\n=== All demos complete ===")
