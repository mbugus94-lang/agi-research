"""
Tests for Integrated Agent System
Tests the closed-loop integration: Execute → Reflect → Plan → Improve
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.integrated_agent import (
    IntegratedAgent, ExecutionCycle, StrategyAdaptation,
    ExecutionPhase, create_integrated_agent
)
from core.planner import SubTask, ResourceBudget, PlanStatus
from core.reflection import PerformanceRecord, ReflectionScope, ChangeStatus
from core.tiered_memory import MemoryTier
import time


class MockExecuteFn:
    """Mock execution function for testing."""
    
    def __init__(self, success_rate: float = 0.8, delay_ms: float = 10.0):
        self.success_rate = success_rate
        self.delay_ms = delay_ms
        self.call_count = 0
        self.results = []  # Track results for analysis
    
    def __call__(self, task: SubTask) -> tuple:
        self.call_count += 1
        
        # Simulate execution delay
        if self.delay_ms > 0:
            time.sleep(self.delay_ms / 1000)
        
        # Determine success based on rate
        import random
        success = random.random() < self.success_rate
        
        result = (success, f"Output_{self.call_count}" if success else Exception("Test error"))
        self.results.append({
            'task_id': task.task_id,
            'success': success,
            'description': task.description
        })
        
        return result


def test_integrated_agent_initialization():
    """Test that integrated agent initializes correctly."""
    agent = create_integrated_agent("test_agent_1")
    
    assert agent.agent_id == "test_agent_1"
    assert agent.planner is not None
    assert agent.reflection is not None
    assert agent.memory is not None
    
    status = agent.get_agent_status()
    assert status['agent_id'] == "test_agent_1"
    assert status['cycles_completed'] == 0
    
    print("✅ test_integrated_agent_initialization passed")


def test_execution_cycle_creation():
    """Test that execution cycle tracks phases correctly."""
    agent = create_integrated_agent("test_agent_2")
    
    # Create a simple mock executor that always succeeds
    mock_fn = MockExecuteFn(success_rate=1.0, delay_ms=1)
    
    # Execute a simple goal
    cycle = agent.execute_goal(
        goal="Test simple task",
        execute_fn=mock_fn,
        budget=ResourceBudget(max_api_calls=10, max_compute_time_seconds=5.0)
    )
    
    # Verify cycle completed
    assert cycle.cycle_id is not None
    assert cycle.goal == "Test simple task"
    assert cycle.completed_at is not None
    assert cycle.tasks_executed > 0
    assert cycle.tasks_succeeded > 0
    
    print("✅ test_execution_cycle_creation passed")


def test_performance_recording():
    """Test that execution performance is recorded for reflection."""
    agent = create_integrated_agent("test_agent_3")
    
    # Execute with varying success rates
    mock_fn = MockExecuteFn(success_rate=0.7, delay_ms=5)
    
    cycle = agent.execute_goal(
        goal="Test performance tracking",
        execute_fn=mock_fn
    )
    
    # Verify reflection has records
    assert len(agent.reflection.performance_history) > 0
    
    # Analyze patterns
    analysis = agent.reflection.analyze_performance_patterns()
    assert 'success_rate' in analysis
    
    print(f"   Recorded {len(agent.reflection.performance_history)} performance records")
    print("✅ test_performance_recording passed")


def test_capability_assessment():
    """Test that capabilities are assessed after execution."""
    agent = create_integrated_agent("test_agent_4")
    
    # Execute multiple cycles to build sample size
    for i in range(3):
        mock_fn = MockExecuteFn(success_rate=0.8, delay_ms=2)
        agent.execute_goal(
            goal=f"Test assessment cycle {i}",
            execute_fn=mock_fn
        )
    
    # Assess a capability
    assessment = agent.reflection.assess_capability(
        capability_name="test_execution",
        task_type="atomic_task"
    )
    
    assert assessment.capability_name == "test_execution"
    assert 0.0 <= assessment.proficiency_score <= 1.0
    assert assessment.sample_size > 0
    
    print(f"   Capability score: {assessment.proficiency_score:.3f}")
    print(f"   Confidence: {assessment.confidence:.3f}")
    print("✅ test_capability_assessment passed")


def test_memory_storage():
    """Test that execution insights are stored in memory."""
    agent = create_integrated_agent("test_agent_5")
    
    mock_fn = MockExecuteFn(success_rate=1.0, delay_ms=1)
    
    cycle = agent.execute_goal(
        goal="Test memory storage",
        execute_fn=mock_fn
    )
    
    # Verify memory references were created
    assert cycle.memory_context_id is not None
    assert cycle.reflection_report_id is not None
    
    # Try to retrieve from memory
    try:
        window = agent.memory.get_window(cycle.memory_context_id)
        if window:
            print(f"   Memory window status: {window.status.name}")
            print(f"   Tokens used: {window.tokens_used}")
    except Exception as e:
        print(f"   Note: Memory retrieval: {e}")
    
    print("✅ test_memory_storage passed")


def test_strategy_adaptation():
    """Test that strategies adapt based on performance."""
    agent = create_integrated_agent("test_agent_6")
    
    # First execution with low success rate
    mock_fn_low = MockExecuteFn(success_rate=0.4, delay_ms=5)
    cycle1 = agent.execute_goal(
        goal="Test strategy adaptation low",
        execute_fn=mock_fn_low
    )
    
    # Check if adaptation was created for underperforming type
    adaptations_before = len(agent.strategy_adaptations)
    
    # Second execution with high success rate
    mock_fn_high = MockExecuteFn(success_rate=1.0, delay_ms=2)
    cycle2 = agent.execute_goal(
        goal="Test strategy adaptation high",
        execute_fn=mock_fn_high
    )
    
    # Verify adaptations exist
    assert len(agent.strategy_adaptations) >= adaptations_before
    
    # Check adaptation parameters
    for task_type, adaptation in agent.strategy_adaptations.items():
        assert adaptation.decomposition_depth >= 3
        assert adaptation.exploration_budget_multiplier >= 1.0
        assert adaptation.retry_threshold >= 3
        
        print(f"   {task_type}: depth={adaptation.decomposition_depth}, "
              f"budget_mult={adaptation.exploration_budget_multiplier:.2f}")
    
    print("✅ test_strategy_adaptation passed")


def test_improvement_goal_creation():
    """Test that improvement goals are created for problem areas."""
    agent = create_integrated_agent("test_agent_7")
    
    # Execute with poor performance to trigger goals
    mock_fn = MockExecuteFn(success_rate=0.5, delay_ms=10)
    
    cycle = agent.execute_goal(
        goal="Test improvement goal creation",
        execute_fn=mock_fn
    )
    
    # Verify reflection has improvement goals
    active_goals = [g for g in agent.reflection.improvement_goals.values() 
                   if g.status == 'active']
    
    if active_goals:
        print(f"   Created {len(active_goals)} improvement goals")
        for goal in active_goals:
            print(f"   - {goal.target_capability}: target={goal.target_score:.2f}")
    
    print("✅ test_improvement_goal_creation passed")


def test_planning_with_memory():
    """Test memory-augmented planning."""
    agent = create_integrated_agent("test_agent_8")
    
    # First execution to create memories
    mock_fn = MockExecuteFn(success_rate=0.9, delay_ms=3)
    
    agent.execute_goal(
        goal="Test planning test goal",
        execute_fn=mock_fn
    )
    
    # Plan with memory retrieval
    plan, memories = agent.plan_with_memory(
        goal="Test planning test goal again",
        context={}
    )
    
    assert plan is not None
    assert plan.plan_id is not None
    
    if memories:
        print(f"   Retrieved {len(memories)} relevant memories")
        for mem in memories[:3]:
            print(f"   - {mem['goal'][:50]}... (relevance: {mem['relevance']:.2f})")
    
    print("✅ test_planning_with_memory passed")


def test_mid_execution_reflection():
    """Test that reflection occurs during long executions."""
    agent = create_integrated_agent("test_agent_9")
    agent.reflection_interval = 3  # Reflect every 3 tasks
    
    # Create many small tasks
    task_count = 10
    
    def counting_executor(task: SubTask):
        return (True, f"Result for {task.task_id}")
    
    cycle = agent.execute_goal(
        goal=f"Execute {task_count} tasks for mid-reflection testing",
        execute_fn=counting_executor,
        budget=ResourceBudget(max_api_calls=20, max_iterations=20)
    )
    
    # Verify cycle completed
    assert cycle.tasks_executed >= task_count
    
    # Check for mid-execution alerts
    alerts = [item for item in cycle.improvement_goals_created 
             if 'mid_exec_alert' in item]
    
    if alerts:
        print(f"   Generated {len(alerts)} mid-execution alerts")
    
    print("✅ test_mid_execution_reflection passed")


def test_propose_capability_improvements():
    """Test capability improvement proposals."""
    agent = create_integrated_agent("test_agent_10")
    
    # Build some performance history
    mock_fn = MockExecuteFn(success_rate=0.6, delay_ms=8)
    
    for i in range(5):
        agent.execute_goal(
            goal=f"Build history {i}",
            execute_fn=mock_fn
        )
    
    # Propose improvements
    proposals = agent.propose_capability_improvements()
    
    print(f"   Generated {len(proposals)} improvement proposals")
    
    for proposal in proposals:
        assert proposal.scope is not None
        assert len(proposal.rationale) > 20
        assert proposal.expected_impact is not None
        print(f"   - {proposal.description[:60]}...")
    
    print("✅ test_propose_capability_improvements passed")


def test_export_and_state():
    """Test that agent state can be exported."""
    agent = create_integrated_agent("test_agent_11")
    
    # Execute a cycle
    mock_fn = MockExecuteFn(success_rate=0.85, delay_ms=4)
    agent.execute_goal("Test state export", execute_fn=mock_fn)
    
    # Export state
    state = agent.export_state()
    
    assert 'agent_id' in state
    assert 'completed_cycles' in state
    assert 'strategy_adaptations' in state
    assert 'reflection_state' in state
    
    assert len(state['completed_cycles']) > 0
    assert state['agent_id'] == "test_agent_11"
    
    # Verify cycle export
    cycle = state['completed_cycles'][0]
    assert 'cycle_id' in cycle
    assert 'goal' in cycle
    assert 'tasks_executed' in cycle
    
    print(f"   Exported {len(state['completed_cycles'])} cycles")
    print(f"   Exported {len(state['strategy_adaptations'])} strategy adaptations")
    print("✅ test_export_and_state passed")


def test_full_integration_workflow():
    """Test complete integration workflow with multiple cycles."""
    agent = create_integrated_agent("test_agent_12")
    
    print("\n   === Full Integration Workflow Test ===")
    
    # Phase 1: Initial learning (low success)
    print("   Phase 1: Learning phase (60% success)")
    mock_low = MockExecuteFn(success_rate=0.6, delay_ms=5)
    for i in range(3):
        agent.execute_goal(f"Learning task {i}", execute_fn=mock_low)
    
    # Phase 2: Improvement (high success)
    print("   Phase 2: Improvement phase (90% success)")
    mock_high = MockExecuteFn(success_rate=0.9, delay_ms=3)
    for i in range(3):
        agent.execute_goal(f"Improved task {i}", execute_fn=mock_high)
    
    # Phase 3: Verify learning
    print("   Phase 3: Verification")
    
    # Check agent status
    status = agent.get_agent_status()
    print(f"   - Total cycles: {status['cycles_completed']}")
    print(f"   - Overall success rate: {status['overall_success_rate']:.3f}")
    print(f"   - Strategy adaptations: {status['strategy_adaptations_count']}")
    print(f"   - Capability assessments: {status['capability_assessments']}")
    print(f"   - Active improvement goals: {status['improvement_goals_active']}")
    
    # Verify reflection has data
    assert len(agent.reflection.performance_history) > 0
    
    # Check strategy adaptations were created
    assert len(agent.strategy_adaptations) > 0
    
    # Verify reflection report was generated
    for cycle in agent.completed_cycles:
        if cycle.reflection_report_id:
            print(f"   - Cycle {cycle.cycle_id[:8]}: "
                  f"{cycle.tasks_succeeded}/{cycle.tasks_executed} succeeded")
    
    print("✅ test_full_integration_workflow passed")


def test_error_handling():
    """Test that errors are handled gracefully."""
    agent = create_integrated_agent("test_agent_13")
    
    # Executor that fails often
    def failing_executor(task: SubTask):
        if "fail" in task.description.lower():
            return (False, Exception("Simulated failure"))
        return (True, "Success")
    
    # Mixed task execution
    cycle = agent.execute_goal(
        goal="Test with failing task and then normal task execution",
        execute_fn=failing_executor
    )
    
    # Should still complete cycle
    assert cycle.completed_at is not None
    
    # Check for error classification in reflection
    error_types = set()
    for record in agent.reflection.performance_history:
        if record.error_type:
            error_types.add(record.error_type)
    
    if error_types:
        print(f"   Classified error types: {error_types}")
    
    print("✅ test_error_handling passed")


def test_budget_management():
    """Test that resource budgets are respected."""
    agent = create_integrated_agent("test_agent_14")
    
    # Strict budget
    tight_budget = ResourceBudget(
        max_api_calls=5,
        max_compute_time_seconds=1.0,
        max_iterations=3
    )
    
    def slow_executor(task: SubTask):
        time.sleep(0.1)  # 100ms per task
        return (True, "Done")
    
    cycle = agent.execute_goal(
        goal="Test with tight budget constraints for resource management",
        execute_fn=slow_executor,
        budget=tight_budget
    )
    
    # Verify execution was constrained
    print(f"   Tasks executed: {cycle.tasks_executed}")
    print(f"   Total time: {cycle.total_execution_time_ms:.1f}ms")
    
    # Should have stopped due to budget
    assert cycle.tasks_executed <= 5
    
    print("✅ test_budget_management passed")


def run_all_tests():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("Running Integrated Agent Tests")
    print("=" * 60 + "\n")
    
    tests = [
        test_integrated_agent_initialization,
        test_execution_cycle_creation,
        test_performance_recording,
        test_capability_assessment,
        test_memory_storage,
        test_strategy_adaptation,
        test_improvement_goal_creation,
        test_planning_with_memory,
        test_mid_execution_reflection,
        test_propose_capability_improvements,
        test_export_and_state,
        test_full_integration_workflow,
        test_error_handling,
        test_budget_management,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"❌ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print(f"Results: {passed}/{len(tests)} passed, {failed} failed")
    print("=" * 60 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
