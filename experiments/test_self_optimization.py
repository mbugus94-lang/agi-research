"""
Tests for Self-Optimization Module

Validates SOLAR-inspired lifelong learning capabilities:
1. Strategy discovery and storage
2. Episodic memory for transfer learning
3. Test-time adaptation to new domains
4. Plasticity-stability balance

Test Coverage Target: 25+ comprehensive tests
"""

import sys
sys.path.insert(0, '/home/workspace/agi-research')

import pytest
import time
from datetime import datetime
from core.self_optimization import (
    AdaptationLevel, DomainType, ModificationStrategy, AdaptationEpisode,
    MetaStrategy, EpisodicBuffer, SelfOptimizingEngine,
    create_self_optimizing_engine, quick_adapt
)


# =============================================================================
# ModificationStrategy Tests
# =============================================================================

def test_strategy_creation():
    """Test basic strategy creation."""
    strategy = ModificationStrategy(
        id="test_001",
        name="Test Strategy",
        level=AdaptationLevel.STRATEGIC,
        description="A test strategy",
        domain_types=[DomainType.TASK_SHIFT],
        capability_requirements=["web_search", "code_gen"]
    )
    
    assert strategy.id == "test_001"
    assert strategy.name == "Test Strategy"
    assert strategy.level == AdaptationLevel.STRATEGIC
    assert strategy.success_rate() == 0.5  # Neutral prior


def test_strategy_success_rate():
    """Test success rate calculation."""
    strategy = ModificationStrategy(
        id="test_002",
        name="Successful Strategy",
        level=AdaptationLevel.PRIMITIVE,
        description="High success strategy"
    )
    
    # Add successes
    strategy.success_count = 8
    strategy.failure_count = 2
    
    assert strategy.success_rate() == 0.8


def test_strategy_utility_update():
    """Test utility tracking."""
    strategy = ModificationStrategy(
        id="test_003",
        name="Utility Test",
        level=AdaptationLevel.PRIMITIVE,
        description="Testing utility updates"
    )
    
    # Simulate usage - first update sets the value
    strategy.update_utility(0.5)
    assert strategy.average_utility == 0.5
    
    # Second update averages
    strategy.update_utility(0.7)
    # Running average: (0.5 + 0.7) / 2 = 0.6
    assert strategy.average_utility == pytest.approx(0.6)


def test_strategy_domain_matching():
    """Test domain matching calculation."""
    strategy = ModificationStrategy(
        id="test_004",
        name="Domain Matcher",
        level=AdaptationLevel.STRATEGIC,
        description="Domain matching test",
        domain_types=[DomainType.TASK_SHIFT, DomainType.TOOL_CHANGE],
        capability_requirements=["search", "analysis"]
    )
    
    # Exact domain match
    score = strategy.matches_domain(DomainType.TASK_SHIFT, ["search", "analysis", "coding"])
    assert score > 0.8  # High match due to domain + capabilities
    
    # Partial domain match
    score = strategy.matches_domain(DomainType.ENVIRONMENT_CHANGE, ["search"])
    assert score < 0.5  # Lower match


# =============================================================================
# AdaptationEpisode Tests
# =============================================================================

def test_episode_creation():
    """Test episode creation and basic properties."""
    episode = AdaptationEpisode(
        id="ep_001",
        timestamp=time.time(),
        domain_type=DomainType.TASK_SHIFT,
        domain_signature="abc123",
        performance_before=0.5,
        performance_after=0.7,
        adaptation_success=True,
        adaptation_time=2.5
    )
    
    assert episode.improvement() == pytest.approx(0.4)  # (0.7 - 0.5) / 0.5
    assert episode.adaptation_success
    assert episode.to_dict()["improvement"] == pytest.approx(0.4)


def test_episode_dict_serialization():
    """Test episode serialization to dictionary."""
    episode = AdaptationEpisode(
        id="ep_002",
        timestamp=1234567890.0,
        domain_type=DomainType.TOOL_CHANGE,
        domain_signature="xyz789",
        trigger_context={"task": "coding", "tools": ["python", "git"]},
        performance_before=0.3,
        strategy_id="strat_001",
        performance_after=0.6,
        adaptation_success=True,
        adaptation_time=1.5
    )
    
    data = episode.to_dict()
    assert data["id"] == "ep_002"
    assert data["domain_type"] == "tool_change"
    assert data["improvement"] == 1.0  # (0.6 - 0.3) / 0.3


# =============================================================================
# MetaStrategy Tests
# =============================================================================

def test_meta_strategy_creation():
    """Test meta-strategy creation."""
    meta = MetaStrategy(
        id="meta_001",
        name="Compose Strategy",
        description="Test meta strategy",
        generation_method="compose",
        exploration_rate=0.25
    )
    
    assert meta.generation_method == "compose"
    assert meta.exploration_rate == 0.25


def test_meta_strategy_params_generation():
    """Test parameter generation."""
    meta = MetaStrategy(
        id="meta_002",
        name="Mutation Meta",
        description="Test mutation",
        generation_method="mutate",
        exploration_rate=0.3
    )
    
    # Create a template strategy
    template = ModificationStrategy(
        id="template_001",
        name="Template",
        level=AdaptationLevel.PRIMITIVE,
        description="Template for mutation"
    )
    
    params = meta.generate_strategy_params({"task": "test"}, [template])
    assert "generation_method" in params
    assert params["generation_method"] == "mutate"


# =============================================================================
# EpisodicBuffer Tests
# =============================================================================

def test_buffer_creation():
    """Test buffer initialization."""
    buffer = EpisodicBuffer(max_size=100, retention_threshold=0.3)
    
    assert buffer.max_size == 100
    assert buffer.retention_threshold == 0.3
    assert buffer.total_episodes == 0


def test_buffer_add_successful_episode():
    """Test adding successful episode to buffer."""
    buffer = EpisodicBuffer(retention_threshold=0.2)
    
    episode = AdaptationEpisode(
        id="ep_success",
        timestamp=time.time(),
        domain_type=DomainType.TASK_SHIFT,
        domain_signature="sig_001",
        performance_before=0.5,
        performance_after=0.8,  # 60% improvement
        adaptation_success=True
    )
    
    added = buffer.add_episode(episode)
    assert added  # Success with >20% improvement
    assert buffer.total_episodes == 1
    assert buffer.successful_episodes == 1


def test_buffer_reject_failed_episode():
    """Test that failed episodes are rejected."""
    buffer = EpisodicBuffer()
    
    episode = AdaptationEpisode(
        id="ep_fail",
        timestamp=time.time(),
        domain_type=DomainType.TASK_SHIFT,
        domain_signature="sig_002",
        performance_before=0.5,
        performance_after=0.4,  # -20%
        adaptation_success=False
    )
    
    added = buffer.add_episode(episode)
    assert not added  # Failed episodes not retained


def test_buffer_add_and_find_strategy():
    """Test strategy storage and retrieval."""
    buffer = EpisodicBuffer()
    
    strategy = ModificationStrategy(
        id="strat_001",
        name="Search Strategy",
        level=AdaptationLevel.PRIMITIVE,
        description="Web search optimization",
        domain_types=[DomainType.TASK_SHIFT, DomainType.TOOL_CHANGE],
        capability_requirements=["web_search"]
    )
    
    buffer.add_strategy(strategy)
    assert len(buffer.strategies) == 1
    
    # Find strategies for matching domain
    found = buffer.find_strategies_for_domain(
        DomainType.TASK_SHIFT, ["web_search", "analysis"], top_k=5
    )
    assert len(found) == 1
    assert found[0][0].id == "strat_001"


def test_buffer_pruning():
    """Test buffer size management."""
    buffer = EpisodicBuffer(max_size=10, retention_threshold=0.0)
    
    # Add many episodes
    for i in range(15):
        episode = AdaptationEpisode(
            id=f"ep_{i}",
            timestamp=time.time() + i,  # Sequential timestamps
            domain_type=DomainType.TASK_SHIFT,
            domain_signature=f"sig_{i}",
            performance_before=0.5,
            performance_after=0.6 + (i * 0.01),
            adaptation_success=True
        )
        buffer.add_episode(episode)
    
    # Buffer should prune to stay under max_size
    assert len(buffer.episodes) <= buffer.max_size


def test_buffer_statistics():
    """Test buffer statistics calculation."""
    buffer = EpisodicBuffer()
    
    stats = buffer.get_statistics()
    assert "total_episodes" in stats
    assert "stored_episodes" in stats
    assert "success_rate" in stats


# =============================================================================
# SelfOptimizingEngine Tests
# =============================================================================

def test_engine_creation():
    """Test engine initialization."""
    engine = SelfOptimizingEngine(
        prior_strength=2.0,
        exploration_rate=0.25,
        adaptation_threshold=0.15
    )
    
    assert engine.prior_strength == 2.0
    assert engine.exploration_rate == 0.25
    assert engine.adaptation_threshold == 0.15
    assert len(engine.meta_strategies) == 3  # Default meta-strategies


def test_detect_domain_shift():
    """Test domain shift detection."""
    engine = SelfOptimizingEngine(adaptation_threshold=0.1)
    
    # No shift below threshold
    shift = engine.detect_domain_shift({"task_type": "coding"}, 0.05)
    assert shift is None
    
    # Detect task shift
    shift = engine.detect_domain_shift(
        {"task_type": "new_type"},
        0.3  # Above threshold
    )
    assert shift == DomainType.TASK_SHIFT


def test_detect_tool_change():
    """Test tool change detection."""
    engine = SelfOptimizingEngine()
    
    # First call sets last_tools
    shift = engine.detect_domain_shift(
        {"tool_set": ["python", "git"]},
        0.25
    )
    
    # Second call with different tools
    shift = engine.detect_domain_shift(
        {"tool_set": ["python", "docker"]},
        0.25
    )
    assert shift == DomainType.TOOL_CHANGE


def test_domain_signature_generation():
    """Test domain signature hashing."""
    engine = SelfOptimizingEngine()
    
    sig1 = engine.generate_domain_signature({"a": 1, "b": 2})
    sig2 = engine.generate_domain_signature({"b": 2, "a": 1})  # Same, different order
    sig3 = engine.generate_domain_signature({"a": 1, "b": 3})  # Different
    
    assert sig1 == sig2  # Same content = same signature
    assert sig1 != sig3  # Different content = different signature
    assert len(sig1) == 16  # Truncated SHA256


def test_adapt_to_new_domain():
    """Test adaptation to a new domain."""
    engine = SelfOptimizingEngine(exploration_rate=1.0)  # Always explore
    
    strategy = engine.adapt_to_domain(
        domain_type=DomainType.TASK_SHIFT,
        task_features={"type": "coding", "complexity": "high"},
        current_performance=0.4,
        available_capabilities=["code_gen", "analysis"]
    )
    
    assert strategy is not None
    assert strategy.id.startswith("strategy_task_shift_")
    assert strategy.level == AdaptationLevel.STRATEGIC


def test_adapt_with_existing_strategies():
    """Test exploitation of existing strategies."""
    engine = SelfOptimizingEngine(exploration_rate=0.0)  # Never explore
    
    # Pre-populate with a strategy
    strategy = ModificationStrategy(
        id="existing_001",
        name="Existing Strategy",
        level=AdaptationLevel.PRIMITIVE,
        description="Pre-existing",
        domain_types=[DomainType.TASK_SHIFT],
        capability_requirements=["code_gen"],
        success_count=10,
        failure_count=2
    )
    strategy.average_utility = 0.8
    engine.episodic_buffer.add_strategy(strategy)
    
    # Should select existing strategy
    selected = engine.adapt_to_domain(
        domain_type=DomainType.TASK_SHIFT,
        task_features={"type": "coding"},
        current_performance=0.5,
        available_capabilities=["code_gen"]
    )
    
    assert selected is not None
    assert selected.id == "existing_001"


def test_record_adaptation_outcome():
    """Test recording adaptation outcomes."""
    engine = SelfOptimizingEngine()
    
    strategy = ModificationStrategy(
        id="test_strat",
        name="Test",
        level=AdaptationLevel.PRIMITIVE,
        description="Test"
    )
    strategy.last_domain = "domain_123"
    engine.active_strategies["test_strat"] = strategy
    
    engine.record_adaptation_outcome(
        episode_id="ep_test",
        strategy=strategy,
        performance_before=0.5,
        performance_after=0.7,
        success=True,
        adaptation_time=2.0
    )
    
    assert strategy.usage_count >= 1  # Should be incremented
    assert strategy.success_count == 1
    assert len(engine.performance_history) == 1


def test_get_active_parameters():
    """Test parameter merging from active strategies."""
    engine = SelfOptimizingEngine()
    
    # Add active strategies with parameters
    strat1 = ModificationStrategy(
        id="s1",
        name="Strat1",
        level=AdaptationLevel.PRIMITIVE,
        description="Strategy 1",
        parameter_changes={"param_a": 0.5, "param_b": 1.0},
        success_count=5,
        failure_count=1
    )
    strat1.average_utility = 0.8
    
    engine.active_strategies["s1"] = strat1
    
    params = engine.get_active_parameters()
    assert "param_a" in params
    assert "param_b" in params


def test_engine_statistics():
    """Test engine statistics."""
    engine = SelfOptimizingEngine()
    
    stats = engine.get_statistics()
    assert "episodic_buffer" in stats
    assert "active_strategies" in stats
    assert "meta_strategies" in stats
    assert stats["meta_strategies"] == 3


def test_save_state():
    """Test state serialization."""
    engine = SelfOptimizingEngine()
    
    state = engine.save_state()
    assert "episodic_buffer" in state
    assert "performance_history" in state
    assert "statistics" in state


# =============================================================================
# Integration Tests
# =============================================================================

def test_full_adaptation_workflow():
    """Test complete adaptation workflow."""
    engine = SelfOptimizingEngine(exploration_rate=0.5)
    
    # Detect domain shift
    shift = engine.detect_domain_shift(
        {"task_type": "coding", "tool_set": ["python"]},
        0.35
    )
    assert shift is not None
    
    # Adapt to domain
    strategy = engine.adapt_to_domain(
        domain_type=shift,
        task_features={"complexity": "high", "deadline": "tight"},
        current_performance=0.45,
        available_capabilities=["code_gen", "web_search"]
    )
    assert strategy is not None
    
    # Record outcome
    engine.record_adaptation_outcome(
        episode_id=f"ep_{int(time.time())}",
        strategy=strategy,
        performance_before=0.45,
        performance_after=0.65,
        success=True,
        adaptation_time=1.5
    )
    
    # Verify strategy updated
    assert strategy.usage_count >= 1
    assert strategy.success_count >= 1


def test_multiple_domain_adaptations():
    """Test adaptation to multiple domain types."""
    engine = SelfOptimizingEngine()
    
    domains = [
        (DomainType.TASK_SHIFT, {"task_type": "research"}),
        (DomainType.TOOL_CHANGE, {"tool_set": ["browser", "api"]}),
        (DomainType.ENVIRONMENT_CHANGE, {"latency": "high"})
    ]
    
    for domain_type, features in domains:
        strategy = engine.adapt_to_domain(
            domain_type=domain_type,
            task_features=features,
            current_performance=0.5,
            available_capabilities=["search", "analysis"]
        )
        assert strategy is not None


def test_strategy_improvement_over_time():
    """Test that strategies improve with successful usage."""
    engine = SelfOptimizingEngine()
    
    strategy = ModificationStrategy(
        id="improving_strat",
        name="Improving",
        level=AdaptationLevel.STRATEGIC,
        description="Should improve",
        success_count=0,
        failure_count=0
    )
    
    # Simulate multiple successful uses
    for i in range(5):
        engine.record_adaptation_outcome(
            episode_id=f"ep_{i}",
            strategy=strategy,
            performance_before=0.5 + (i * 0.02),
            performance_after=0.6 + (i * 0.02),
            success=True,
            adaptation_time=1.0
        )
    
    assert strategy.success_rate() > 0.8
    assert strategy.average_utility > 0


def test_episodic_transfer_learning():
    """Test transfer via episodic memory."""
    engine = SelfOptimizingEngine(exploration_rate=0.0)  # Exploit only
    
    # Store successful episode
    episode = AdaptationEpisode(
        id="transfer_ep",
        timestamp=time.time(),
        domain_type=DomainType.TASK_SHIFT,
        domain_signature="similar_sig",
        performance_before=0.4,
        performance_after=0.7,
        adaptation_success=True,
        strategy_id="transfer_strat"
    )
    
    strategy = ModificationStrategy(
        id="transfer_strat",
        name="Transfer Strategy",
        level=AdaptationLevel.PRIMITIVE,
        description="From similar domain",
        domain_types=[DomainType.TASK_SHIFT],
        capability_requirements=["analysis"],
        success_count=5,
        failure_count=1,
        average_utility=0.6
    )
    
    engine.episodic_buffer.add_episode(episode)
    engine.episodic_buffer.add_strategy(strategy)
    
    # New similar domain should find existing strategy
    similar_strategies = engine.episodic_buffer.find_strategies_for_domain(
        DomainType.TASK_SHIFT, ["analysis"], top_k=5
    )
    
    assert len(similar_strategies) > 0
    assert similar_strategies[0][0].id == "transfer_strat"


# =============================================================================
# Convenience Function Tests
# =============================================================================

def test_create_self_optimizing_engine():
    """Test convenience factory function."""
    engine = create_self_optimizing_engine(prior_strength=1.5)
    
    assert engine.prior_strength == 1.5
    assert engine.exploration_rate == 0.3
    assert engine.adaptation_threshold == 0.2


def test_quick_adapt():
    """Test quick adaptation helper."""
    engine = create_self_optimizing_engine()
    
    strategy = quick_adapt(
        engine=engine,
        domain_type="task_shift",
        task_description="Research AGI papers",
        current_performance=0.4,
        available_tools=["web_search", "analysis"]
    )
    
    assert strategy is not None
    assert strategy.level == AdaptationLevel.STRATEGIC


# =============================================================================
# Edge Case Tests
# =============================================================================

def test_empty_capabilities():
    """Test adaptation with no capabilities."""
    engine = SelfOptimizingEngine()
    
    strategy = engine.adapt_to_domain(
        domain_type=DomainType.TASK_SHIFT,
        task_features={"test": "data"},
        current_performance=0.5,
        available_capabilities=[]
    )
    
    assert strategy is not None  # Should still generate a strategy


def test_zero_performance():
    """Test handling zero performance values."""
    episode = AdaptationEpisode(
        id="zero_perf",
        timestamp=time.time(),
        domain_type=DomainType.TASK_SHIFT,
        domain_signature="sig",
        performance_before=0.0,  # Edge case
        performance_after=0.1,
        adaptation_success=True
    )
    
    assert episode.improvement() == 0.0  # Avoid division issues


def test_buffer_overflow():
    """Test buffer under extreme load."""
    buffer = EpisodicBuffer(max_size=5, retention_threshold=0.0)
    
    for i in range(20):  # Add more than max_size
        episode = AdaptationEpisode(
            id=f"ep_{i}",
            timestamp=time.time() + i,  # Sequential timestamps
            domain_type=DomainType.TASK_SHIFT,
            domain_signature=f"sig_{i}",
            performance_before=0.5,
            performance_after=0.6,
            adaptation_success=True
        )
        buffer.add_episode(episode)
    
    # Buffer should prune to stay at or under max_size
    assert len(buffer.episodes) <= buffer.max_size


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
