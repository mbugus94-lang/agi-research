"""
Self-Optimization Module

Inspired by SOLAR: A Self-Optimizing Open-Ended Autonomous Agent
(arXiv:2605.18401v1 - submitted May 18, 2026)

Implements lifelong learning and continual adaptation through:
1. Meta-learning at parameter level (treating model weights as exploration space)
2. Multi-level reinforcement learning for adaptation strategies
3. Episodic memory buffer for valid modification strategies
4. Test-time adaptation to unseen domains
5. Balance between plasticity (new tasks) and stability (meta-knowledge retention)

Key Concepts:
- Meta-strategy: Higher-level policy for how to adapt to new situations
- Modification strategies: Concrete parameter changes for specific adaptations
- Episodic buffer: Store of successful adaptations for future reference
- Test-time adaptation: Adjust to new domains during inference (not just training)

References:
- SOLAR paper: Self-optimizing agents for lifelong learning
- GenericAgent: Minimal self-evolving autonomous agent framework
- ASH: Agents that Self-Hone via Embodied Learning
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Tuple, Set, Union
from enum import Enum, auto
from datetime import datetime
import hashlib
import json
import time
import uuid
from collections import defaultdict
import math
import random


class AdaptationLevel(Enum):
    """Levels in the multi-level adaptation hierarchy."""
    PRIMITIVE = "primitive"      # Direct action adjustments
    STRATEGIC = "strategic"      # Strategy/approach changes
    META = "meta"                # How to generate strategies


class DomainType(Enum):
    """Types of domain shifts the agent can encounter."""
    TASK_SHIFT = "task_shift"           # New task type
    TOOL_CHANGE = "tool_change"         # Tool availability/behavior change
    ENVIRONMENT_CHANGE = "env_change"   # Environment dynamics change
    CONSTRAINT_CHANGE = "constraint_change"  # New constraints/goals
    DISTRIBUTION_SHIFT = "dist_shift"   # Input distribution change


@dataclass
class ModificationStrategy:
    """
    A concrete strategy for modifying agent behavior.
    
    In SOLAR, these are discovered adaptation strategies stored in
    the episodic buffer for future reuse.
    """
    id: str
    name: str
    level: AdaptationLevel
    description: str
    
    # When this strategy applies
    domain_types: List[DomainType] = field(default_factory=list)
    capability_requirements: List[str] = field(default_factory=list)
    
    # The strategy itself
    parameter_changes: Dict[str, Any] = field(default_factory=dict)
    prompt_modifications: List[str] = field(default_factory=list)
    tool_preferences: Dict[str, float] = field(default_factory=dict)
    
    # Performance tracking
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    average_utility: float = 0.0
    
    # Temporal metadata
    created_at: float = field(default_factory=time.time)
    last_used: Optional[float] = None
    last_domain: Optional[str] = None
    
    def success_rate(self) -> float:
        """Calculate success rate of this strategy."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5  # Neutral prior
        return self.success_count / total
    
    def update_utility(self, utility_delta: float):
        """Update running average utility with new observation."""
        self.usage_count += 1
        n = self.usage_count
        if n == 1:
            self.average_utility = utility_delta
        else:
            self.average_utility = (self.average_utility * (n - 1) + utility_delta) / n
    
    def matches_domain(self, domain_type: DomainType, capabilities: List[str]) -> float:
        """Calculate match score for this strategy to a domain."""
        domain_match = 1.0 if domain_type in self.domain_types else 0.0
        
        if self.capability_requirements:
            capability_overlap = len(
                set(capabilities) & set(self.capability_requirements)
            ) / len(self.capability_requirements)
        else:
            capability_overlap = 1.0
        
        return (domain_match * 0.6) + (capability_overlap * 0.4)


@dataclass
class AdaptationEpisode:
    """
    Record of an adaptation event stored in episodic memory.
    
    SOLAR maintains an episodic memory buffer of valid modification
    strategies to enable transfer learning and prevent forgetting.
    """
    id: str
    timestamp: float
    domain_type: DomainType
    domain_signature: str  # Hash of domain characteristics
    
    # What triggered adaptation
    trigger_context: Dict[str, Any] = field(default_factory=dict)
    performance_before: float = 0.0
    
    # The adaptation applied
    strategy_id: Optional[str] = None
    modifications_applied: Dict[str, Any] = field(default_factory=dict)
    
    # Outcome
    performance_after: float = 0.0
    adaptation_success: bool = False
    adaptation_time: float = 0.0  # Time to adapt
    
    def improvement(self) -> float:
        """Calculate performance improvement from adaptation."""
        if self.performance_before == 0:
            return 0.0
        return (self.performance_after - self.performance_before) / self.performance_before
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "domain_type": self.domain_type.value,
            "domain_signature": self.domain_signature,
            "trigger_context": self.trigger_context,
            "performance_before": self.performance_before,
            "strategy_id": self.strategy_id,
            "modifications_applied": self.modifications_applied,
            "performance_after": self.performance_after,
            "adaptation_success": self.adaptation_success,
            "adaptation_time": self.adaptation_time,
            "improvement": self.improvement()
        }


@dataclass
class MetaStrategy:
    """
    Higher-level policy for generating adaptation strategies.
    
    SOLAR uses multi-level RL where meta-strategies determine
    how to discover new modification strategies.
    """
    id: str
    name: str
    description: str
    
    # Exploration parameters
    exploration_rate: float = 0.3
    temperature: float = 1.0
    
    # Strategy generation approach
    generation_method: str = "compose"  # compose, mutate, combine, discover
    
    # Selection criteria for generated strategies
    min_success_rate_threshold: float = 0.6
    min_utility_threshold: float = 0.0
    
    # Performance tracking
    strategies_generated: int = 0
    strategies_adopted: int = 0
    average_strategy_quality: float = 0.0
    
    def generate_strategy_params(self, 
                                 context: Dict[str, Any],
                                 existing_strategies: List[ModificationStrategy]) -> Dict[str, Any]:
        """Generate parameters for a new strategy based on this meta-strategy."""
        params = {
            "exploration_rate": self.exploration_rate,
            "temperature": self.temperature,
            "generation_method": self.generation_method
        }
        
        if self.generation_method == "compose":
            # Compose from existing strategies
            if existing_strategies:
                template = random.choice(existing_strategies)
                params["template_id"] = template.id
                params["variation_degree"] = 0.3
                
        elif self.generation_method == "mutate":
            # Mutate existing strategy
            if existing_strategies:
                base = random.choice(existing_strategies)
                params["base_id"] = base.id
                params["mutation_rate"] = 0.2
                
        return params


class EpisodicBuffer:
    """
    Memory buffer storing successful adaptation episodes and strategies.
    
    SOLAR's episodic buffer maintains valid modification strategies
    to balance plasticity (adapting to new tasks) and stability
    (retaining meta-knowledge).
    """
    
    def __init__(self, max_size: int = 1000, retention_threshold: float = 0.5):
        self.max_size = max_size
        self.retention_threshold = retention_threshold
        
        # Core storage
        self.episodes: Dict[str, AdaptationEpisode] = {}
        self.strategies: Dict[str, ModificationStrategy] = {}
        
        # Indexing for efficient retrieval
        self.domain_index: Dict[DomainType, List[str]] = defaultdict(list)
        self.strategy_domain_index: Dict[DomainType, List[str]] = defaultdict(list)
        
        # Statistics
        self.total_episodes = 0
        self.successful_episodes = 0
        
    def add_episode(self, episode: AdaptationEpisode) -> bool:
        """Add an adaptation episode to the buffer."""
        # Only retain successful episodes above threshold
        if episode.adaptation_success and episode.improvement() >= self.retention_threshold:
            self.episodes[episode.id] = episode
            self.domain_index[episode.domain_type].append(episode.id)
            self.total_episodes += 1
            if episode.adaptation_success:
                self.successful_episodes += 1
            
            # Manage buffer size
            self._prune_if_needed()
            return True
        return False
    
    def add_strategy(self, strategy: ModificationStrategy):
        """Add a modification strategy to the buffer."""
        self.strategies[strategy.id] = strategy
        for domain_type in strategy.domain_types:
            self.strategy_domain_index[domain_type].append(strategy.id)
    
    def find_strategies_for_domain(self, 
                                   domain_type: DomainType,
                                   capabilities: List[str],
                                   top_k: int = 5) -> List[Tuple[ModificationStrategy, float]]:
        """Find most relevant strategies for a domain."""
        candidates = []
        
        for strategy_id in self.strategy_domain_index[domain_type]:
            strategy = self.strategies.get(strategy_id)
            if strategy:
                match_score = strategy.matches_domain(domain_type, capabilities)
                quality_score = strategy.success_rate() * strategy.average_utility
                combined_score = match_score * 0.4 + quality_score * 0.6
                candidates.append((strategy, combined_score))
        
        # Sort by combined score and return top_k
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_k]
    
    def find_similar_episodes(self, 
                              domain_signature: str,
                              context_features: Dict[str, Any]) -> List[AdaptationEpisode]:
        """Find episodes similar to current context."""
        similar = []
        
        for episode in self.episodes.values():
            # Check domain signature similarity
            sig_similarity = self._signature_similarity(
                episode.domain_signature, domain_signature
            )
            
            # Check context feature overlap
            context_similarity = self._context_similarity(
                episode.trigger_context, context_features
            )
            
            combined = (sig_similarity * 0.6) + (context_similarity * 0.4)
            if combined > 0.7:  # Similarity threshold
                similar.append(episode)
        
        return sorted(similar, key=lambda e: e.improvement(), reverse=True)
    
    def _signature_similarity(self, sig1: str, sig2: str) -> float:
        """Calculate similarity between domain signatures."""
        # Simple hash-based similarity (can be replaced with more sophisticated methods)
        if sig1 == sig2:
            return 1.0
        
        # Count common prefix/suffix characters
        common = sum(c1 == c2 for c1, c2 in zip(sig1, sig2))
        return common / max(len(sig1), len(sig2))
    
    def _context_similarity(self, ctx1: Dict, ctx2: Dict) -> float:
        """Calculate similarity between context dictionaries."""
        if not ctx1 or not ctx2:
            return 0.0
        
        keys1, keys2 = set(ctx1.keys()), set(ctx2.keys())
        if not keys1 or not keys2:
            return 0.0
        
        overlap = len(keys1 & keys2) / len(keys1 | keys2)
        return overlap
    
    def _prune_if_needed(self):
        """Remove oldest/lowest-quality episodes if buffer exceeds max size."""
        if len(self.episodes) > self.max_size:
            # Sort by timestamp (oldest first) and improvement
            sorted_episodes = sorted(
                self.episodes.items(),
                key=lambda x: (x[1].timestamp, x[1].improvement())
            )
            
            # Remove oldest until we're at max_size
            to_remove = len(self.episodes) - self.max_size
            for i in range(to_remove):
                episode_id, episode = sorted_episodes[i]
                del self.episodes[episode_id]
                if episode_id in self.domain_index[episode.domain_type]:
                    self.domain_index[episode.domain_type].remove(episode_id)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get buffer statistics."""
        return {
            "total_episodes": self.total_episodes,
            "stored_episodes": len(self.episodes),
            "successful_episodes": self.successful_episodes,
            "success_rate": self.successful_episodes / max(1, self.total_episodes),
            "stored_strategies": len(self.strategies),
            "domain_coverage": len(self.domain_index),
            "strategy_coverage": len(self.strategy_domain_index)
        }


class SelfOptimizingEngine:
    """
    Core engine implementing SOLAR-style self-optimization.
    
    Enables lifelong learning through:
    1. Strategy discovery via meta-learning
    2. Episodic memory for transfer
    3. Test-time adaptation
    4. Plasticity-stability balance
    """
    
    def __init__(self, 
                 prior_strength: float = 1.0,
                 exploration_rate: float = 0.3,
                 adaptation_threshold: float = 0.2):
        self.prior_strength = prior_strength
        self.exploration_rate = exploration_rate
        self.adaptation_threshold = adaptation_threshold
        
        # Core components
        self.episodic_buffer = EpisodicBuffer()
        self.meta_strategies: Dict[str, MetaStrategy] = {}
        self.active_strategies: Dict[str, ModificationStrategy] = {}
        
        # Performance tracking
        self.current_performance: Dict[str, float] = {}
        self.performance_history: List[Dict[str, Any]] = []
        
        # State
        self.current_domain: Optional[str] = None
        self.adaptation_in_progress: bool = False
        
        # Initialize default meta-strategies
        self._initialize_meta_strategies()
    
    def _initialize_meta_strategies(self):
        """Initialize default meta-strategies for strategy generation."""
        self.meta_strategies["compose"] = MetaStrategy(
            id="meta_compose",
            name="Strategy Composition",
            description="Compose new strategies from existing ones",
            generation_method="compose",
            exploration_rate=0.25
        )
        
        self.meta_strategies["mutate"] = MetaStrategy(
            id="meta_mutate",
            name="Strategy Mutation",
            description="Mutate existing strategies with controlled variation",
            generation_method="mutate",
            exploration_rate=0.35
        )
        
        self.meta_strategies["explore"] = MetaStrategy(
            id="meta_explore",
            name="Novel Strategy Discovery",
            description="Explore completely new strategies",
            generation_method="discover",
            exploration_rate=0.5
        )
    
    def detect_domain_shift(self, 
                          task_features: Dict[str, Any],
                          performance_delta: float) -> Optional[DomainType]:
        """
        Detect if current task represents a domain shift requiring adaptation.
        
        Returns the type of domain shift detected, or None if no shift.
        """
        if abs(performance_delta) < self.adaptation_threshold:
            return None
        
        # Analyze task features to determine shift type
        if "task_type" in task_features and task_features["task_type"] not in self.current_performance:
            return DomainType.TASK_SHIFT
        
        if "tool_set" in task_features:
            current_tools = set(task_features["tool_set"])
            # Check for tool changes
            if hasattr(self, '_last_tools') and current_tools != self._last_tools:
                return DomainType.TOOL_CHANGE
            self._last_tools = current_tools
        
        if "constraints" in task_features:
            return DomainType.CONSTRAINT_CHANGE
        
        if performance_delta < -0.3:  # Significant drop
            return DomainType.DISTRIBUTION_SHIFT
        
        return DomainType.ENVIRONMENT_CHANGE
    
    def generate_domain_signature(self, task_features: Dict[str, Any]) -> str:
        """Generate a hash signature for the current domain."""
        # Create canonical representation
        canonical = json.dumps(task_features, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]
    
    def adapt_to_domain(self, 
                       domain_type: DomainType,
                       task_features: Dict[str, Any],
                       current_performance: float,
                       available_capabilities: List[str]) -> Optional[ModificationStrategy]:
        """
        Adapt to a new domain using strategies from episodic memory.
        
        This implements SOLAR's test-time adaptation - adjusting behavior
        during inference based on encountered domain characteristics.
        """
        domain_signature = self.generate_domain_signature(task_features)
        
        # Find similar past episodes
        similar_episodes = self.episodic_buffer.find_similar_episodes(
            domain_signature, task_features
        )
        
        # Find relevant strategies
        relevant_strategies = self.episodic_buffer.find_strategies_for_domain(
            domain_type, available_capabilities, top_k=5
        )
        
        # Decide whether to use existing or discover new strategy
        if relevant_strategies and random.random() > self.exploration_rate:
            # Exploit: Use best existing strategy
            selected_strategy, score = relevant_strategies[0]
            selected_strategy.usage_count += 1
            selected_strategy.last_used = time.time()
            selected_strategy.last_domain = domain_signature
            return selected_strategy
        else:
            # Explore: Generate new strategy
            new_strategy = self._discover_new_strategy(
                domain_type, task_features, available_capabilities,
                similar_episodes, relevant_strategies
            )
            if new_strategy:
                self.episodic_buffer.add_strategy(new_strategy)
                self.active_strategies[new_strategy.id] = new_strategy
            return new_strategy
    
    def _discover_new_strategy(self,
                               domain_type: DomainType,
                               task_features: Dict[str, Any],
                               capabilities: List[str],
                               similar_episodes: List[AdaptationEpisode],
                               relevant_strategies: List[Tuple[ModificationStrategy, float]]) -> Optional[ModificationStrategy]:
        """Discover a new modification strategy."""
        # Select meta-strategy
        meta = random.choice(list(self.meta_strategies.values()))
        meta.strategies_generated += 1
        
        # Generate strategy ID
        strategy_id = f"strategy_{domain_type.value}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Build strategy based on meta-strategy parameters
        strategy = ModificationStrategy(
            id=strategy_id,
            name=f"Auto-discovered {domain_type.value} strategy",
            level=AdaptationLevel.STRATEGIC,
            description=f"Discovered via {meta.name} for {domain_type.value}",
            domain_types=[domain_type],
            capability_requirements=capabilities[:3] if capabilities else [],
            tool_preferences={}
        )
        
        # Apply composition if relevant strategies exist
        if relevant_strategies and meta.generation_method == "compose":
            template = relevant_strategies[0][0]
            strategy.parameter_changes = dict(template.parameter_changes)
            strategy.tool_preferences = dict(template.tool_preferences)
            # Add variation
            strategy.parameter_changes["adaptation_strength"] = 0.5 + random.random() * 0.5
        
        # Apply mutation if appropriate
        elif relevant_strategies and meta.generation_method == "mutate":
            base = relevant_strategies[0][0]
            strategy.parameter_changes = {
                k: v * (1 + random.uniform(-meta.exploration_rate, meta.exploration_rate))
                for k, v in base.parameter_changes.items()
            }
        
        # Novel discovery for exploration
        else:
            strategy.parameter_changes = {
                "exploration_boost": meta.exploration_rate,
                "novelty_preference": 0.7,
                "risk_tolerance": 0.4
            }
        
        return strategy
    
    def record_adaptation_outcome(self,
                                  episode_id: str,
                                  strategy: ModificationStrategy,
                                  performance_before: float,
                                  performance_after: float,
                                  success: bool,
                                  adaptation_time: float):
        """Record the outcome of an adaptation episode."""
        # Update strategy statistics
        strategy.usage_count += 1
        if success:
            strategy.success_count += 1
            strategy.update_utility(performance_after - performance_before)
        else:
            strategy.failure_count += 1
            strategy.update_utility(-0.1)  # Penalty for failure
        
        # Create and store episode
        episode = AdaptationEpisode(
            id=episode_id,
            timestamp=time.time(),
            domain_type=strategy.domain_types[0] if strategy.domain_types else DomainType.TASK_SHIFT,
            domain_signature=strategy.last_domain or "unknown",
            strategy_id=strategy.id,
            performance_before=performance_before,
            performance_after=performance_after,
            adaptation_success=success,
            adaptation_time=adaptation_time
        )
        
        self.episodic_buffer.add_episode(episode)
        
        # Track performance history
        self.performance_history.append({
            "timestamp": time.time(),
            "episode_id": episode_id,
            "improvement": episode.improvement(),
            "success": success,
            "strategy_id": strategy.id
        })
    
    def get_active_parameters(self) -> Dict[str, Any]:
        """Get current active parameters from all active strategies."""
        merged = {}
        
        # Merge parameters from active strategies
        for strategy in self.active_strategies.values():
            weight = strategy.success_rate() * strategy.average_utility
            for key, value in strategy.parameter_changes.items():
                if key in merged:
                    # Weighted average based on strategy success
                    merged[key] = (merged[key] + value * weight) / (1 + weight)
                else:
                    merged[key] = value
        
        return merged
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive engine statistics."""
        return {
            "episodic_buffer": self.episodic_buffer.get_statistics(),
            "active_strategies": len(self.active_strategies),
            "meta_strategies": len(self.meta_strategies),
            "exploration_rate": self.exploration_rate,
            "adaptation_threshold": self.adaptation_threshold,
            "performance_history_entries": len(self.performance_history),
            "recent_performance": self.performance_history[-10:] if self.performance_history else []
        }
    
    def save_state(self) -> Dict[str, Any]:
        """Serialize engine state."""
        return {
            "episodic_buffer": {
                "episodes": {k: v.to_dict() for k, v in self.episodic_buffer.episodes.items()},
                "strategies": {
                    k: {
                        "id": v.id,
                        "name": v.name,
                        "level": v.level.value,
                        "domain_types": [dt.value for dt in v.domain_types],
                        "success_count": v.success_count,
                        "failure_count": v.failure_count,
                        "average_utility": v.average_utility,
                        "usage_count": v.usage_count
                    }
                    for k, v in self.episodic_buffer.strategies.items()
                }
            },
            "performance_history": self.performance_history[-100:],  # Last 100
            "statistics": self.get_statistics()
        }


# Convenience functions for quick usage
def create_self_optimizing_engine(prior_strength: float = 1.0) -> SelfOptimizingEngine:
    """Create a self-optimizing engine with default configuration."""
    return SelfOptimizingEngine(
        prior_strength=prior_strength,
        exploration_rate=0.3,
        adaptation_threshold=0.2
    )


def quick_adapt(engine: SelfOptimizingEngine,
                domain_type: str,
                task_description: str,
                current_performance: float,
                available_tools: List[str]) -> Optional[ModificationStrategy]:
    """Quick adaptation helper for common use cases."""
    domain = DomainType(domain_type) if domain_type in [dt.value for dt in DomainType] else DomainType.TASK_SHIFT
    
    task_features = {
        "description": task_description,
        "tool_set": available_tools,
        "task_type": domain_type
    }
    
    return engine.adapt_to_domain(
        domain_type=domain,
        task_features=task_features,
        current_performance=current_performance,
        available_capabilities=available_tools
    )
