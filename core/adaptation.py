"""
Test-Time Adaptation (TTA) System for AGI agents.

Implements dynamic refinement during task execution based on insights from:
- arXiv:2603.13372v1: "Test-time adaptation and refinement loops are essential success factors"
- ARC-AGI benchmark showing 2-3x performance drops without adaptation

Key capabilities:
1. Progressive hypothesis exploration
2. Multi-strategy adaptation (exploration vs exploitation)
3. Cost-aware inference optimization
4. Dynamic budget allocation
5. Hypothesis scoring and selection
"""

from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import time
import random


class AdaptationStrategy(Enum):
    """Strategies for test-time adaptation."""
    EXPLORE = "explore"           # Try new approaches
    EXPLOIT = "exploit"          # Use proven approaches
    HYBRID = "hybrid"            # Balance explore/exploit
    GREEDY = "greedy"            # Always pick highest confidence
    ADAPTIVE = "adaptive"        # Strategy shifts based on progress


@dataclass
class Hypothesis:
    """A candidate solution or approach to a task."""
    id: str
    description: str
    approach: str  # The actual method/code/prompt to try
    
    # Scoring
    confidence: float = 0.0  # 0.0 to 1.0
    score: float = 0.0       # Performance metric
    
    # Metadata
    created_at: float = field(default_factory=time.time)
    attempts: int = 0
    successes: int = 0
    failures: int = 0
    
    # Cost tracking
    compute_cost: float = 0.0  # Estimated cost in tokens/time
    time_spent: float = 0.0    # Actual time spent
    
    def update_score(self, result: Any, success: bool, cost: float = 0.0):
        """Update hypothesis based on execution result."""
        self.attempts += 1
        self.time_spent = time.time() - self.created_at
        self.compute_cost += cost
        
        if success:
            self.successes += 1
            # Bayesian-like confidence update
            self.confidence = (self.confidence * (self.attempts - 1) + 1.0) / self.attempts
        else:
            self.failures += 1
            self.confidence = (self.confidence * (self.attempts - 1) + 0.0) / self.attempts
        
        # Score is a combination of confidence and efficiency
        if self.attempts > 0:
            success_rate = self.successes / self.attempts
            efficiency = 1.0 / (1.0 + self.compute_cost * 0.01)  # Penalize high cost
            self.score = success_rate * 0.7 + self.confidence * 0.2 + efficiency * 0.1


@dataclass
class AdaptationState:
    """Current state of the adaptation process."""
    task: str
    hypotheses: List[Hypothesis] = field(default_factory=list)
    current_hypothesis: Optional[Hypothesis] = None
    
    # Budget management
    max_iterations: int = 10
    max_cost: float = 100.0  # Abstract cost units
    current_cost: float = 0.0
    iteration: int = 0
    
    # Strategy
    strategy: AdaptationStrategy = AdaptationStrategy.ADAPTIVE
    
    # Progress tracking
    best_score: float = 0.0
    best_hypothesis: Optional[Hypothesis] = None
    converged: bool = False
    
    # History
    iteration_history: List[Dict] = field(default_factory=list)


class TestTimeAdapter:
    """
    Implements test-time adaptation for dynamic task refinement.
    
    Core insight from ARC-AGI: Systems that adapt during task execution
    significantly outperform static approaches. This module provides:
    
    1. Hypothesis generation and management
    2. Adaptive strategy selection
    3. Cost-aware resource allocation
    4. Progressive refinement loops
    """
    
    def __init__(
        self,
        strategy: AdaptationStrategy = AdaptationStrategy.ADAPTIVE,
        max_iterations: int = 10,
        max_cost: float = 100.0,
        convergence_threshold: float = 0.95
    ):
        self.strategy = strategy
        self.max_iterations = max_iterations
        self.max_cost = max_cost
        self.convergence_threshold = convergence_threshold
        
        # Statistics for learning across tasks
        self.global_stats = {
            "total_tasks": 0,
            "successful_adaptations": 0,
            "avg_iterations": 0,
            "avg_cost": 0.0,
            "strategy_performance": {s.value: [] for s in AdaptationStrategy}
        }
    
    def generate_hypotheses(self, task: str, context: Dict[str, Any]) -> List[Hypothesis]:
        """
        Generate initial hypotheses for a task.
        
        In production, this would use an LLM to generate diverse approaches.
        For now, uses template-based generation.
        """
        hypotheses = []
        
        # Generate diverse approaches based on task type
        templates = [
            ("direct", "Solve directly with single-step reasoning"),
            ("decomposed", "Break into sub-problems and solve sequentially"),
            ("parallel", "Attempt multiple approaches in parallel"),
            ("iterative", "Start with draft solution and refine iteratively"),
            ("search", "Search for similar problems and adapt solution"),
        ]
        
        for i, (approach_type, description) in enumerate(templates):
            h = Hypothesis(
                id=f"h_{i}_{approach_type}",
                description=description,
                approach=approach_type,
                confidence=0.5  # Start with neutral confidence
            )
            hypotheses.append(h)
        
        return hypotheses
    
    def select_hypothesis(
        self,
        state: AdaptationState,
        temperature: float = 1.0
    ) -> Hypothesis:
        """
        Select next hypothesis to try based on strategy.
        
        Args:
            state: Current adaptation state
            temperature: Exploration temperature (higher = more random)
        """
        available = [h for h in state.hypotheses if h.attempts < 3]  # Max 3 attempts each
        
        if not available:
            # All hypotheses exhausted, generate new one
            new_h = Hypothesis(
                id=f"h_gen_{state.iteration}",
                description=f"Generated hypothesis at iteration {state.iteration}",
                approach="adaptive",
                confidence=0.3
            )
            state.hypotheses.append(new_h)
            return new_h
        
        strategy = state.strategy
        
        if strategy == AdaptationStrategy.GREEDY:
            # Pick highest confidence
            return max(available, key=lambda h: h.confidence)
        
        elif strategy == AdaptationStrategy.EXPLORE:
            # Weighted random by inverse attempts (prefer untried)
            weights = [1.0 / (1 + h.attempts) for h in available]
            total = sum(weights)
            probs = [w / total for w in weights]
            return random.choices(available, weights=probs, k=1)[0]
        
        elif strategy == AdaptationStrategy.EXPLOIT:
            # Weighted random by confidence
            weights = [h.confidence for h in available]
            total = sum(weights)
            probs = [w / total for w in weights] if total > 0 else [1.0 / len(available)] * len(available)
            return random.choices(available, weights=probs, k=1)[0]
        
        elif strategy == AdaptationStrategy.HYBRID:
            # Blend of explore and exploit
            if random.random() < 0.3:  # 30% exploration
                return self.select_hypothesis(AdaptationState(
                    task=state.task, hypotheses=state.hypotheses,
                    strategy=AdaptationStrategy.EXPLORE
                ), temperature)
            else:
                return self.select_hypothesis(AdaptationState(
                    task=state.task, hypotheses=state.hypotheses,
                    strategy=AdaptationStrategy.EXPLOIT
                ), temperature)
        
        else:  # ADAPTIVE
            # Adjust strategy based on progress
            if state.iteration < 3:
                # Early: explore more
                return self.select_hypothesis(AdaptationState(
                    task=state.task, hypotheses=state.hypotheses,
                    strategy=AdaptationStrategy.EXPLORE
                ), temperature)
            elif state.best_score > 0.8:
                # Late, high score: exploit best
                return state.best_hypothesis or max(available, key=lambda h: h.confidence)
            else:
                # Mid: balanced
                return self.select_hypothesis(AdaptationState(
                    task=state.task, hypotheses=state.hypotheses,
                    strategy=AdaptationStrategy.HYBRID
                ), temperature)
    
    def should_continue(self, state: AdaptationState) -> bool:
        """Determine if adaptation should continue."""
        # Check budget
        if state.current_cost >= self.max_cost:
            return False
        if state.iteration >= self.max_iterations:
            return False
        
        # Check convergence
        if state.converged:
            return False
        
        # Check if we have a very good solution
        if state.best_score >= self.convergence_threshold:
            state.converged = True
            return False
        
        return True
    
    def adapt(
        self,
        task: str,
        executor: Callable[[Hypothesis, Dict], Tuple[Any, bool, float]],
        context: Dict[str, Any] = None,
        initial_hypotheses: List[Hypothesis] = None
    ) -> Dict[str, Any]:
        """
        Run test-time adaptation loop.
        
        Args:
            task: The task to solve
            executor: Function that executes a hypothesis, returns (result, success, cost)
            context: Additional context for the task
            initial_hypotheses: Optional pre-generated hypotheses
            
        Returns:
            Dict with best result, all results, adaptation history, and statistics
        """
        context = context or {}
        
        # Initialize state
        state = AdaptationState(
            task=task,
            strategy=self.strategy,
            max_iterations=self.max_iterations,
            max_cost=self.max_cost
        )
        
        # Generate or use initial hypotheses
        state.hypotheses = initial_hypotheses or self.generate_hypotheses(task, context)
        
        print(f"🔬 Test-Time Adaptation: {task[:50]}...")
        print(f"   Strategy: {state.strategy.value}")
        print(f"   Budget: {state.max_cost} units, {state.max_iterations} iterations")
        print(f"   Initial hypotheses: {len(state.hypotheses)}")
        
        # Adaptation loop
        while self.should_continue(state):
            state.iteration += 1
            print(f"\n📍 Iteration {state.iteration}/{state.max_iterations}")
            
            # Select hypothesis
            hypothesis = self.select_hypothesis(state)
            state.current_hypothesis = hypothesis
            print(f"   Testing: {hypothesis.description[:60]}...")
            
            # Execute
            start_time = time.time()
            result, success, cost = executor(hypothesis, context)
            actual_cost = cost + (time.time() - start_time) * 10  # Time cost
            
            # Update hypothesis
            hypothesis.update_score(result, success, actual_cost)
            state.current_cost += actual_cost
            
            print(f"   Result: {'✅' if success else '❌'} Score: {hypothesis.score:.3f} Cost: {actual_cost:.1f}")
            
            # Update best
            if hypothesis.score > state.best_score:
                state.best_score = hypothesis.score
                state.best_hypothesis = hypothesis
                print(f"   🏆 New best! Score: {state.best_score:.3f}")
            
            # Record iteration
            state.iteration_history.append({
                "iteration": state.iteration,
                "hypothesis_id": hypothesis.id,
                "success": success,
                "score": hypothesis.score,
                "cost": actual_cost,
                "cumulative_cost": state.current_cost,
                "best_score": state.best_score
            })
            
            # Check for early convergence
            if hypothesis.confidence >= self.convergence_threshold and success:
                print(f"   ✨ High confidence solution found!")
                state.converged = True
                break
        
        # Finalize
        print(f"\n{'='*50}")
        print(f"✅ Adaptation complete after {state.iteration} iterations")
        print(f"   Best score: {state.best_score:.3f}")
        print(f"   Total cost: {state.current_cost:.1f}")
        print(f"   Best hypothesis: {state.best_hypothesis.description if state.best_hypothesis else 'None'}")
        
        # Update global stats
        self._update_global_stats(state)
        
        return {
            "success": state.best_score >= 0.5,
            "best_result": state.best_hypothesis,
            "best_score": state.best_score,
            "iterations": state.iteration,
            "total_cost": state.current_cost,
            "converged": state.converged,
            "all_hypotheses": [self._hypothesis_to_dict(h) for h in state.hypotheses],
            "history": state.iteration_history,
            "strategy_used": state.strategy.value
        }
    
    def _hypothesis_to_dict(self, h: Hypothesis) -> Dict:
        """Convert hypothesis to dictionary."""
        return {
            "id": h.id,
            "description": h.description,
            "approach": h.approach,
            "confidence": h.confidence,
            "score": h.score,
            "attempts": h.attempts,
            "successes": h.successes,
            "failures": h.failures,
            "compute_cost": h.compute_cost,
            "time_spent": h.time_spent
        }
    
    def _update_global_stats(self, state: AdaptationState):
        """Update global performance statistics."""
        self.global_stats["total_tasks"] += 1
        if state.best_score >= 0.5:
            self.global_stats["successful_adaptations"] += 1
        
        # Running averages
        n = self.global_stats["total_tasks"]
        self.global_stats["avg_iterations"] = (
            self.global_stats["avg_iterations"] * (n - 1) + state.iteration
        ) / n
        self.global_stats["avg_cost"] = (
            self.global_stats["avg_cost"] * (n - 1) + state.current_cost
        ) / n
        
        # Strategy performance
        self.global_stats["strategy_performance"][state.strategy.value].append(state.best_score)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get global adaptation statistics."""
        return {
            "total_tasks": self.global_stats["total_tasks"],
            "success_rate": (
                self.global_stats["successful_adaptations"] / 
                max(1, self.global_stats["total_tasks"])
            ),
            "avg_iterations": self.global_stats["avg_iterations"],
            "avg_cost": self.global_stats["avg_cost"],
            "strategy_performance": {
                k: sum(v) / max(1, len(v)) if v else 0
                for k, v in self.global_stats["strategy_performance"].items()
            }
        }


class AdaptiveAgent:
    """
    An agent that uses test-time adaptation for improved performance.
    Wraps the base agent with adaptation capabilities.
    """
    
    def __init__(self, base_agent, adapter: Optional[TestTimeAdapter] = None):
        self.base_agent = base_agent
        self.adapter = adapter or TestTimeAdapter()
    
    def run_with_adaptation(self, task: str, **kwargs) -> Dict[str, Any]:
        """Run task with test-time adaptation."""
        
        def executor(hypothesis: Hypothesis, context: Dict) -> Tuple[Any, bool, float]:
            """Execute task with given hypothesis approach."""
            # Modify agent behavior based on hypothesis approach
            approach = hypothesis.approach
            
            if approach == "direct":
                # Single attempt, straightforward
                result = self._try_solve(task, max_steps=3, **kwargs)
                return result, result.get("success", False), 10.0
            
            elif approach == "decomposed":
                # Break into steps
                subtasks = self._decompose_task(task)
                results = []
                for sub in subtasks:
                    r = self._try_solve(sub, max_steps=2, **kwargs)
                    results.append(r)
                success = all(r.get("success", False) for r in results)
                return results, success, 20.0
            
            elif approach == "parallel":
                # Try multiple simple approaches
                attempts = [
                    self._try_solve(task, max_steps=2, temperature=0.0, **kwargs),
                    self._try_solve(task, max_steps=2, temperature=1.0, **kwargs),
                ]
                best = max(attempts, key=lambda x: x.get("score", 0))
                return best, best.get("success", False), 25.0
            
            elif approach == "iterative":
                # Draft then refine
                draft = self._try_solve(task, max_steps=2, draft=True, **kwargs)
                refined = self._try_solve(
                    f"Refine: {draft.get('answer', '')}", 
                    max_steps=3, 
                    **kwargs
                )
                return refined, refined.get("success", False), 30.0
            
            else:
                # Default
                result = self._try_solve(task, **kwargs)
                return result, result.get("success", False), 15.0
        
        return self.adapter.adapt(task, executor, context=kwargs)
    
    def _try_solve(self, task: str, **kwargs) -> Dict:
        """Attempt to solve task with base agent."""
        # Simplified - would call actual agent
        return {
            "success": True,
            "answer": f"Solution for: {task[:30]}...",
            "score": 0.7
        }
    
    def _decompose_task(self, task: str) -> List[str]:
        """Decompose task into subtasks."""
        # Simplified - would use LLM for actual decomposition
        return [f"Step 1: Analyze {task[:20]}...", f"Step 2: Solve {task[:20]}..."]


def demo():
    """Demonstrate test-time adaptation."""
    print("=" * 60)
    print("🧪 Test-Time Adaptation Demo")
    print("=" * 60)
    
    # Create adapter
    adapter = TestTimeAdapter(
        strategy=AdaptationStrategy.ADAPTIVE,
        max_iterations=8,
        max_cost=100.0
    )
    
    # Mock executor simulates different approaches
    def mock_executor(h: Hypothesis, ctx: Dict) -> Tuple[Any, bool, float]:
        """Simulate task execution with varying success rates."""
        # Simulate: some approaches work better
        success_rates = {
            "direct": 0.4,
            "decomposed": 0.6,
            "parallel": 0.5,
            "iterative": 0.7,
            "adaptive": 0.55
        }
        
        rate = success_rates.get(h.approach, 0.5)
        # Add some randomness
        success = random.random() < rate
        
        # Costs vary by approach
        costs = {
            "direct": 5.0,
            "decomposed": 15.0,
            "parallel": 20.0,
            "iterative": 25.0,
            "adaptive": 10.0
        }
        cost = costs.get(h.approach, 10.0)
        
        result = {
            "approach": h.approach,
            "output": f"Result using {h.approach}",
            "quality": rate + random.uniform(-0.1, 0.1)
        }
        
        return result, success, cost
    
    # Run adaptation
    result = adapter.adapt(
        task="Solve complex reasoning problem with multiple constraints",
        executor=mock_executor
    )
    
    print("\n" + "=" * 60)
    print("📊 Final Results")
    print("=" * 60)
    print(f"Success: {result['success']}")
    print(f"Iterations: {result['iterations']}")
    print(f"Best Score: {result['best_score']:.3f}")
    print(f"Total Cost: {result['total_cost']:.1f}")
    print(f"Converged: {result['converged']}")
    
    print("\n📈 Hypothesis Rankings:")
    sorted_h = sorted(result['all_hypotheses'], key=lambda x: x['score'], reverse=True)
    for i, h in enumerate(sorted_h[:5], 1):
        print(f"   {i}. {h['approach']}: score={h['score']:.3f}, conf={h['confidence']:.3f}, attempts={h['attempts']}")
    
    print("\n📉 Adaptation History:")
    for entry in result['history'][-5:]:
        print(f"   Iter {entry['iteration']}: {entry['hypothesis_id']} - "
              f"score={entry['score']:.3f}, cost={entry['cost']:.1f}")
    
    # Show global stats
    stats = adapter.get_stats()
    print("\n🌍 Global Stats:")
    print(f"   Total tasks: {stats['total_tasks']}")
    print(f"   Success rate: {stats['success_rate']:.1%}")
    print(f"   Avg iterations: {stats['avg_iterations']:.1f}")
    print(f"   Avg cost: {stats['avg_cost']:.1f}")


if __name__ == "__main__":
    demo()
