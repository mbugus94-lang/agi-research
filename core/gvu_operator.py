"""
GVU (Generator-Verifier-Updater) Operator System
Based on: "The Geometry of Benchmarks: A New Path Toward AGI" (arXiv:2512.04276)

Unifies RL, self-play, debate, and verifier-based fine-tuning as special cases
of a single self-improvement flow.
"""

from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import time
import json
from datetime import datetime


class GVUPhase(Enum):
    """Three phases of the GVU cycle."""
    GENERATE = "generate"
    VERIFY = "verify"
    UPDATE = "update"


class ImprovementMethod(Enum):
    """Types of improvement methods unified by GVU."""
    REINFORCEMENT_LEARNING = "rl"
    SELF_PLAY = "self_play"
    DEBATE = "debate"
    VERIFIER_BASED = "verifier_based"
    EXPERT_ITERATION = "expert_iteration"
    STDP = "self_taught_reasoner"  # Self-Taught Reasoner pattern


@dataclass
class GeneratedOutput:
    """Output from the generator phase."""
    content: Any
    generation_params: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "content": self._serialize_content(),
            "generation_params": self.generation_params,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }
    
    def _serialize_content(self) -> Any:
        """Serialize content for storage."""
        if isinstance(self.content, (str, int, float, bool, type(None))):
            return self.content
        elif isinstance(self.content, (list, dict)):
            return self.content
        else:
            return str(self.content)


@dataclass
class VerificationResult:
    """Result from the verifier phase."""
    is_valid: bool
    score: float  # 0.0 to 1.0
    feedback: str
    issues: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    verifier_type: str = "default"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "is_valid": self.is_valid,
            "score": self.score,
            "feedback": self.feedback,
            "issues": self.issues,
            "strengths": self.strengths,
            "timestamp": self.timestamp,
            "verifier_type": self.verifier_type,
            "metadata": self.metadata
        }


@dataclass
class UpdateDelta:
    """Change proposed by the updater phase."""
    parameter_changes: Dict[str, Any] = field(default_factory=dict)
    strategy_changes: List[str] = field(default_factory=list)
    learning_signal: float = 0.0  # Positive or negative signal
    update_type: str = "parameter"
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "parameter_changes": self.parameter_changes,
            "strategy_changes": self.strategy_changes,
            "learning_signal": self.learning_signal,
            "update_type": self.update_type,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }


@dataclass
class GVUCycle:
    """One complete GVU cycle."""
    cycle_id: str
    phase: GVUPhase
    generated: Optional[GeneratedOutput] = None
    verification: Optional[VerificationResult] = None
    update: Optional[UpdateDelta] = None
    context: Dict[str, Any] = field(default_factory=dict)
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    
    def complete(self):
        """Mark cycle as complete."""
        self.end_time = time.time()
    
    @property
    def duration(self) -> float:
        """Duration of cycle in seconds."""
        end = self.end_time or time.time()
        return end - self.start_time
    
    def to_dict(self) -> Dict:
        return {
            "cycle_id": self.cycle_id,
            "phase": self.phase.value,
            "generated": self.generated.to_dict() if self.generated else None,
            "verification": self.verification.to_dict() if self.verification else None,
            "update": self.update.to_dict() if self.update else None,
            "context": self.context,
            "duration": self.duration,
            "start_time": self.start_time,
            "end_time": self.end_time
        }


class CapabilityFunctional:
    """
    Measures agent capability across task space.
    Maps from (task, performance) to scalar capability measure.
    """
    
    def __init__(self, name: str, task_family: str):
        self.name = name
        self.task_family = task_family
        self.measurements: List[Dict] = []
        self.baseline = 0.0
        self.target = 1.0
    
    def measure(self, task: str, performance: float, 
                resources_used: Dict[str, float]) -> float:
        """
        Compute capability measure for a task performance.
        
        Args:
            task: Task identifier
            performance: Performance score (0.0 to 1.0)
            resources_used: Dict of resources (tokens, time, compute)
        
        Returns:
            Capability measure (higher is better)
        """
        # Normalize performance
        normalized_perf = (performance - self.baseline) / (self.target - self.baseline)
        normalized_perf = max(0.0, min(1.0, normalized_perf))
        
        # Cost penalty (lower resource use = better)
        cost_factor = 1.0
        if "tokens" in resources_used:
            cost_factor = 1.0 / (1.0 + resources_used["tokens"] / 1000)
        if "time" in resources_used:
            cost_factor *= 1.0 / (1.0 + resources_used["time"] / 60)
        
        capability = normalized_perf * cost_factor
        
        self.measurements.append({
            "task": task,
            "performance": performance,
            "resources": resources_used,
            "capability": capability,
            "timestamp": time.time()
        })
        
        return capability
    
    def get_trend(self, window: int = 10) -> float:
        """Get trend over recent measurements."""
        if len(self.measurements) < 2:
            return 0.0
        
        recent = self.measurements[-window:]
        if len(recent) < 2:
            return 0.0
        
        # Simple linear trend
        first = recent[0]["capability"]
        last = recent[-1]["capability"]
        return (last - first) / len(recent)


class Generator:
    """
    Generates outputs, solutions, or candidates.
    Can use different strategies: single-shot, diverse sampling, tree search, etc.
    """
    
    def __init__(self, name: str, generation_fn: Optional[Callable] = None):
        self.name = name
        self.generation_fn = generation_fn or self._default_generate
        self.generation_history: List[Dict] = []
        self.temperature = 1.0
        self.diversity_boost = 0.0
    
    def _default_generate(self, context: Dict[str, Any], 
                          params: Dict[str, Any]) -> Any:
        """Default generation - can be overridden."""
        return f"Generated output for: {context.get('task', 'unknown')}"
    
    def generate(self, context: Dict[str, Any], 
                 strategy: str = "default",
                 num_candidates: int = 1) -> List[GeneratedOutput]:
        """
        Generate output(s) based on context.
        
        Args:
            context: Input context (task, constraints, etc.)
            strategy: Generation strategy (default, diverse, beam_search, etc.)
            num_candidates: Number of candidates to generate
        
        Returns:
            List of GeneratedOutput
        """
        outputs = []
        
        for i in range(num_candidates):
            # Adjust params based on strategy
            params = {
                "temperature": self.temperature,
                "diversity_boost": self.diversity_boost,
                "candidate_index": i,
                "total_candidates": num_candidates,
                "strategy": strategy
            }
            
            # Generate content
            content = self.generation_fn(context, params)
            
            output = GeneratedOutput(
                content=content,
                generation_params=params,
                metadata={
                    "strategy": strategy,
                    "candidate_number": i + 1
                }
            )
            outputs.append(output)
        
        self.generation_history.append({
            "context": context,
            "strategy": strategy,
            "num_candidates": num_candidates,
            "timestamp": time.time()
        })
        
        return outputs
    
    def self_play_generate(self, context: Dict[str, Any],
                          opponent_history: List[Dict]) -> GeneratedOutput:
        """Generate with self-play consideration (see opponent's history)."""
        # Adapt based on what opponent has done
        adapted_context = context.copy()
        adapted_context["opponent_history"] = opponent_history
        
        return self.generate(adapted_context, strategy="self_play", num_candidates=1)[0]


class Verifier:
    """
    Validates generated outputs.
    Can use different verification strategies: rules, model-based, execution, etc.
    """
    
    def __init__(self, name: str, verify_fn: Optional[Callable] = None):
        self.name = name
        self.verify_fn = verify_fn or self._default_verify
        self.verification_history: List[Dict] = []
        self.strictness = 0.5  # 0.0 = lenient, 1.0 = strict
    
    def _default_verify(self, output: GeneratedOutput, 
                       context: Dict[str, Any]) -> VerificationResult:
        """Default verification - can be overridden."""
        return VerificationResult(
            is_valid=True,
            score=0.7,
            feedback="Default verification passed",
            verifier_type="default"
        )
    
    def verify(self, output: GeneratedOutput,
               context: Dict[str, Any],
               verification_type: str = "standard") -> VerificationResult:
        """
        Verify a generated output.
        
        Args:
            output: Output to verify
            context: Verification context
            verification_type: Type of verification (standard, execution, debate, etc.)
        
        Returns:
            VerificationResult
        """
        result = self.verify_fn(output, context)
        result.verifier_type = verification_type
        
        # Adjust score by strictness
        adjusted_score = result.score * (0.5 + 0.5 * self.strictness)
        result.score = min(1.0, adjusted_score)
        
        # Recompute validity
        result.is_valid = result.score >= 0.5
        
        self.verification_history.append({
            "output": output.to_dict(),
            "result": result.to_dict(),
            "verification_type": verification_type,
            "timestamp": time.time()
        })
        
        return result
    
    def debate_verify(self, output: GeneratedOutput,
                     context: Dict[str, Any],
                     num_debaters: int = 2) -> VerificationResult:
        """
        Verify via debate - multiple verifiers argue about correctness.
        Based on AI safety debate methodology.
        """
        # Simulate debate rounds
        debate_scores = []
        debate_feedback = []
        
        for i in range(num_debaters):
            # Each debater provides assessment
            score = self.verify(output, context).score
            debate_scores.append(score)
            debate_feedback.append(f"Debate_{i}: score={score:.2f}")
        
        # Consensus or conflict?
        avg_score = sum(debate_scores) / len(debate_scores)
        variance = sum((s - avg_score) ** 2 for s in debate_scores) / len(debate_scores)
        
        if variance > 0.1:
            # High disagreement - require more scrutiny
            final_score = avg_score * 0.8
            feedback = "High debate disagreement. Reduced confidence. " + " | ".join(debate_feedback)
        else:
            final_score = avg_score
            feedback = "Debate consensus. " + " | ".join(debate_feedback)
        
        return VerificationResult(
            is_valid=final_score >= 0.5,
            score=final_score,
            feedback=feedback,
            verifier_type="debate",
            metadata={"debate_scores": debate_scores, "variance": variance}
        )


class Updater:
    """
    Updates generator/verifier based on verification results.
    Implements different learning strategies.
    """
    
    def __init__(self, name: str, update_fn: Optional[Callable] = None):
        self.name = name
        self.update_fn = update_fn or self._default_update
        self.update_history: List[Dict] = []
        self.learning_rate = 0.1
    
    def _default_update(self, generator: Generator, verifier: Verifier,
                       cycle: GVUCycle) -> UpdateDelta:
        """Default update - can be overridden."""
        return UpdateDelta(
            learning_signal=cycle.verification.score - 0.5,
            strategy_changes=["default_update"],
            update_type="parameter"
        )
    
    def update(self, generator: Generator, verifier: Verifier,
               cycle: GVUCycle,
               method: ImprovementMethod = ImprovementMethod.REINFORCEMENT_LEARNING
              ) -> UpdateDelta:
        """
        Update based on GVU cycle result.
        
        Args:
            generator: Generator to potentially update
            verifier: Verifier to potentially update
            cycle: Completed GVU cycle
            method: Learning method to use
        
        Returns:
            UpdateDelta describing changes
        """
        delta = self._compute_update(generator, verifier, cycle, method)
        
        # Apply update based on type
        if delta.update_type == "parameter":
            self._apply_parameter_update(generator, verifier, delta)
        elif delta.update_type == "strategy":
            self._apply_strategy_update(generator, verifier, delta)
        
        self.update_history.append({
            "cycle_id": cycle.cycle_id,
            "method": method.value,
            "delta": delta.to_dict(),
            "timestamp": time.time()
        })
        
        return delta
    
    def _compute_update(self, generator: Generator, verifier: Verifier,
                       cycle: GVUCycle,
                       method: ImprovementMethod) -> UpdateDelta:
        """Compute update delta based on method."""
        
        if method == ImprovementMethod.REINFORCEMENT_LEARNING:
            # RL-style: positive reward for good verification, negative for bad
            reward = cycle.verification.score - 0.5  # Centered at 0
            return UpdateDelta(
                learning_signal=reward * self.learning_rate,
                parameter_changes={"temperature_adjustment": -reward * 0.1},
                update_type="parameter"
            )
        
        elif method == ImprovementMethod.SELF_PLAY:
            # Self-play: adjust based on win/loss against previous self
            signal = 1.0 if cycle.verification.is_valid else -1.0
            return UpdateDelta(
                learning_signal=signal * self.learning_rate,
                strategy_changes=["adapt_to_opponent"],
                update_type="strategy"
            )
        
        elif method == ImprovementMethod.DEBATE:
            # Debate: learn from argument quality
            metadata = cycle.verification.metadata or {}
            variance = metadata.get("variance", 0)
            # High variance means we need to improve verification
            return UpdateDelta(
                learning_signal=(0.1 - variance) * self.learning_rate,
                parameter_changes={"strictness_adjustment": variance * 0.2},
                update_type="parameter"
            )
        
        elif method == ImprovementMethod.VERIFIER_BASED:
            # Verifier-based: update generator to produce more verifiable outputs
            if cycle.verification.is_valid:
                signal = cycle.verification.score * self.learning_rate
            else:
                signal = -self.learning_rate
            return UpdateDelta(
                learning_signal=signal,
                strategy_changes=["prefer_verifiable_patterns"],
                update_type="strategy"
            )
        
        elif method == ImprovementMethod.EXPERT_ITERATION:
            # Expert iteration: replay good trajectories
            if cycle.verification.score > 0.8:
                return UpdateDelta(
                    learning_signal=self.learning_rate,
                    strategy_changes=["replay_expert_trajectory"],
                    update_type="strategy"
                )
            else:
                return UpdateDelta(
                    learning_signal=0.0,
                    strategy_changes=["explore_alternative"],
                    update_type="strategy"
                )
        
        else:
            return self.update_fn(generator, verifier, cycle)
    
    def _apply_parameter_update(self, generator: Generator, 
                               verifier: Verifier, delta: UpdateDelta):
        """Apply parameter-level updates."""
        for param, change in delta.parameter_changes.items():
            if param == "temperature_adjustment":
                generator.temperature = max(0.1, min(2.0, 
                    generator.temperature + change))
            elif param == "strictness_adjustment":
                verifier.strictness = max(0.0, min(1.0,
                    verifier.strictness + change))
    
    def _apply_strategy_update(self, generator: Generator,
                              verifier: Verifier, delta: UpdateDelta):
        """Apply strategy-level updates (recorded but not directly applied)."""
        # Strategy changes are logged for meta-learning
        pass


class GVUOperator:
    """
    Main GVU operator implementing the unified self-improvement flow.
    
    The GVU flow:
    1. GENERATE: Produce candidates/solutions/actions
    2. VERIFY: Validate quality, correctness, safety
    3. UPDATE: Improve generator/verifier based on feedback
    
    This subsumes:
    - RL: generate → environment reward → policy update
    - Self-play: generate move → game outcome → strategy update
    - Debate: generate arguments → judge verdict → belief update
    - Verifier-based: generate candidate → verifier check → preference update
    """
    
    def __init__(self, name: str = "GVU_Operator"):
        self.name = name
        self.generator = Generator(f"{name}_generator")
        self.verifier = Verifier(f"{name}_verifier")
        self.updater = Updater(f"{name}_updater")
        
        self.cycles: List[GVUCycle] = []
        self.capability_functionals: Dict[str, CapabilityFunctional] = {}
        self.cycle_counter = 0
        
        # Self-improvement tracking (Lie derivative approximation)
        self.improvement_history: List[Dict] = []
        self.kappa_threshold = 0.01  # Minimum improvement coefficient
    
    def run_cycle(self, context: Dict[str, Any],
                  num_candidates: int = 1,
                  verification_type: str = "standard",
                  update_method: ImprovementMethod = ImprovementMethod.REINFORCEMENT_LEARNING
                 ) -> GVUCycle:
        """
        Run one complete GVU cycle.
        
        Args:
            context: Task context
            num_candidates: Number of candidates to generate
            verification_type: Type of verification
            update_method: Learning method
        
        Returns:
            Completed GVUCycle
        """
        self.cycle_counter += 1
        cycle = GVUCycle(
            cycle_id=f"cycle_{self.cycle_counter}",
            phase=GVUPhase.GENERATE,
            context=context
        )
        
        # Phase 1: GENERATE
        outputs = self.generator.generate(context, num_candidates=num_candidates)
        cycle.generated = outputs[0] if outputs else None  # Take best or first
        
        # Phase 2: VERIFY
        cycle.phase = GVUPhase.VERIFY
        if cycle.generated:
            cycle.verification = self.verifier.verify(
                cycle.generated, context, verification_type
            )
        
        # Phase 3: UPDATE
        cycle.phase = GVUPhase.UPDATE
        if cycle.verification:
            cycle.update = self.updater.update(
                self.generator, self.verifier, cycle, update_method
            )
        
        cycle.complete()
        self.cycles.append(cycle)
        
        # Track capability
        self._update_capability(context, cycle)
        
        return cycle
    
    def run_iterations(self, context: Dict[str, Any],
                      num_iterations: int = 10,
                      improvement_method: ImprovementMethod = ImprovementMethod.REINFORCEMENT_LEARNING
                     ) -> List[GVUCycle]:
        """
        Run multiple GVU iterations for continuous improvement.
        
        Args:
            context: Task context
            num_iterations: Number of cycles
            improvement_method: Method for improvement
        
        Returns:
            List of completed cycles
        """
        cycles = []
        
        for i in range(num_iterations):
            cycle = self.run_cycle(
                context,
                num_candidates=1,
                verification_type="standard",
                update_method=improvement_method
            )
            cycles.append(cycle)
            
            # Early stopping if excellent result
            if cycle.verification and cycle.verification.score >= 0.95:
                break
        
        return cycles
    
    def compute_self_improvement_coefficient(self, 
                                             capability_name: str,
                                             window: int = 5) -> float:
        """
        Compute κ (kappa): the self-improvement coefficient.
        
        Based on the paper: κ is the Lie derivative of capability functional
        along GVU-induced flow. We approximate as the trend in recent capability.
        
        Args:
            capability_name: Name of capability to measure
            window: Number of recent cycles to consider
        
        Returns:
            κ value (positive = improvement, negative = regression)
        """
        if capability_name not in self.capability_functionals:
            return 0.0
        
        functional = self.capability_functionals[capability_name]
        kappa = functional.get_trend(window)
        
        self.improvement_history.append({
            "capability": capability_name,
            "kappa": kappa,
            "timestamp": time.time(),
            "window": window
        })
        
        return kappa
    
    def is_improving(self, capability_name: str, 
                   window: int = 5) -> bool:
        """Check if system is self-improving for given capability."""
        kappa = self.compute_self_improvement_coefficient(capability_name, window)
        return kappa > self.kappa_threshold
    
    def _update_capability(self, context: Dict[str, Any], cycle: GVUCycle):
        """Update capability functional with cycle result."""
        task_family = context.get("task_family", "default")
        
        if task_family not in self.capability_functionals:
            self.capability_functionals[task_family] = CapabilityFunctional(
                name=f"capability_{task_family}",
                task_family=task_family
            )
        
        functional = self.capability_functionals[task_family]
        
        if cycle.verification:
            resources = {
                "time": cycle.duration,
                "tokens": context.get("tokens_used", 0)
            }
            functional.measure(
                task=cycle.cycle_id,
                performance=cycle.verification.score,
                resources_used=resources
            )
    
    def get_best_outputs(self, min_score: float = 0.8,
                        max_results: int = 10) -> List[Dict]:
        """Get best outputs from history."""
        valid_cycles = [
            c for c in self.cycles
            if c.verification and c.verification.score >= min_score
        ]
        
        sorted_cycles = sorted(
            valid_cycles,
            key=lambda c: c.verification.score if c.verification else 0,
            reverse=True
        )
        
        return [
            {
                "cycle_id": c.cycle_id,
                "score": c.verification.score,
                "content": c.generated.content if c.generated else None,
                "feedback": c.verification.feedback
            }
            for c in sorted_cycles[:max_results]
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get GVU operator statistics."""
        if not self.cycles:
            return {"status": "no_cycles"}
        
        scores = [c.verification.score for c in self.cycles if c.verification]
        
        return {
            "total_cycles": len(self.cycles),
            "average_score": sum(scores) / len(scores) if scores else 0,
            "max_score": max(scores) if scores else 0,
            "min_score": min(scores) if scores else 0,
            "improvement_rate": self._compute_improvement_rate(),
            "capabilities": {
                name: {
                    "measurements": len(func.measurements),
                    "trend": func.get_trend()
                }
                for name, func in self.capability_functionals.items()
            },
            "recent_kappa": [
                h for h in self.improvement_history[-10:]
            ]
        }
    
    def _compute_improvement_rate(self) -> float:
        """Compute overall improvement rate across all cycles."""
        if len(self.cycles) < 10:
            return 0.0
        
        # Compare first half to second half
        mid = len(self.cycles) // 2
        first_half = self.cycles[:mid]
        second_half = self.cycles[mid:]
        
        first_scores = [c.verification.score for c in first_half if c.verification]
        second_scores = [c.verification.score for c in second_half if c.verification]
        
        if not first_scores or not second_scores:
            return 0.0
        
        first_avg = sum(first_scores) / len(first_scores)
        second_avg = sum(second_scores) / len(second_scores)
        
        return (second_avg - first_avg) / mid  # Per-cycle improvement


class GVUAgentAdapter:
    """
    Adapter to integrate GVU operator with existing agent systems.
    """
    
    def __init__(self, agent: Any):
        self.agent = agent
        self.gvu = GVUOperator(f"GVU_for_{getattr(agent, 'name', 'agent')}")
        
        # Set up generation to use agent's capabilities
        self.gvu.generator.generation_fn = self._agent_generate
        self.gvu.verifier.verify_fn = self._agent_verify
    
    def _agent_generate(self, context: Dict[str, Any], 
                       params: Dict[str, Any]) -> Any:
        """Use agent to generate output."""
        task = context.get("task", "")
        # Call agent's reasoning/acting if available
        if hasattr(self.agent, 'run') and callable(getattr(self.agent, 'run')):
            return self.agent.run(task)
        elif hasattr(self.agent, 'act') and callable(getattr(self.agent, 'act')):
            return self.agent.act(task)
        else:
            return f"Agent output for: {task}"
    
    def _agent_verify(self, output: GeneratedOutput, 
                     context: Dict[str, Any]) -> VerificationResult:
        """Use agent or external verifier to verify output."""
        # Check if agent has verification capability
        if hasattr(self.agent, 'verify') and callable(getattr(self.agent, 'verify')):
            result = self.agent.verify(output.content, context)
            if isinstance(result, dict):
                return VerificationResult(
                    is_valid=result.get("valid", True),
                    score=result.get("score", 0.5),
                    feedback=result.get("feedback", ""),
                    issues=result.get("issues", []),
                    strengths=result.get("strengths", [])
                )
        
        # Default verification
        return VerificationResult(
            is_valid=True,
            score=0.6,
            feedback="Default verification",
            verifier_type="agent_adapter"
        )
    
    def improve_on_task(self, task: str, num_iterations: int = 10) -> Dict:
        """
        Use GVU to iteratively improve on a task.
        
        Args:
            task: Task description
            num_iterations: Number of improvement cycles
        
        Returns:
            Results summary
        """
        context = {"task": task, "task_family": "general"}
        cycles = self.gvu.run_iterations(context, num_iterations)
        
        best = self.gvu.get_best_outputs(min_score=0.0, max_results=1)
        
        return {
            "task": task,
            "iterations": len(cycles),
            "final_score": cycles[-1].verification.score if cycles[-1].verification else 0,
            "best_score": best[0]["score"] if best else 0,
            "is_improving": self.gvu.is_improving("general"),
            "kappa": self.gvu.compute_self_improvement_coefficient("general"),
            "statistics": self.gvu.get_statistics()
        }
