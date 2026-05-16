"""
Tests for Reflection System

Validates:
- ExecutionTrace recording and analysis
- Pattern extraction from traces
- Insight generation
- Reflector integration
- Batch reflection capabilities
"""

import sys
sys.path.insert(0, '/home/workspace/agi-research')

from core.reflection import (
    ExecutionTrace, Pattern, Insight, InsightType, ReflectionScope,
    TraceAnalyzer, InsightGenerator, Reflector,
    create_reflector, quick_reflect
)
from datetime import datetime


def test_execution_trace_creation():
    """Test ExecutionTrace initialization"""
    trace = ExecutionTrace(
        trace_id="test_001",
        goal="Test goal",
        start_time=datetime.now().timestamp()
    )
    assert trace.trace_id == "test_001"
    assert trace.goal == "Test goal"
    assert trace.success_rate == 0.0
    assert trace.duration == 0.0
    print("✅ ExecutionTrace creation")


def test_execution_trace_add_step():
    """Test adding steps to trace"""
    trace = ExecutionTrace(
        trace_id="test_002",
        goal="Test goal",
        start_time=datetime.now().timestamp()
    )
    
    trace.add_step("action_1", {"result": "ok"}, True)
    trace.add_step("action_2", {"result": "fail"}, False)
    trace.add_step("action_3", {"result": "ok"}, True)
    
    assert len(trace.steps) == 3
    assert len(trace.outcomes) == 3
    assert trace.success_rate == 2/3
    print("✅ ExecutionTrace add_step")


def test_execution_trace_duration():
    """Test trace duration calculation"""
    import time
    
    trace = ExecutionTrace(
        trace_id="test_003",
        goal="Test goal",
        start_time=datetime.now().timestamp()
    )
    
    time.sleep(0.1)
    trace.end_time = datetime.now().timestamp()
    
    assert trace.duration >= 0.1
    print("✅ ExecutionTrace duration")


def test_execution_trace_to_dict():
    """Test trace serialization"""
    trace = ExecutionTrace(
        trace_id="test_004",
        goal="Test goal",
        start_time=datetime.now().timestamp()
    )
    
    trace.add_step("action", {"result": "ok"}, True)
    trace.end_time = datetime.now().timestamp()
    
    data = trace.to_dict()
    assert data["trace_id"] == "test_004"
    assert data["success_rate"] == 1.0
    assert data["step_count"] == 1
    print("✅ ExecutionTrace to_dict")


def test_pattern_creation():
    """Test Pattern dataclass"""
    pattern = Pattern(
        pattern_id="pat_001",
        pattern_type="success",
        description="Success pattern",
        elements=["step1", "step2", "step3"],
        frequency=3,
        confidence=0.8
    )
    
    assert pattern.pattern_id == "pat_001"
    assert pattern.pattern_type == "success"
    assert len(pattern.elements) == 3
    print("✅ Pattern creation")


def test_pattern_to_dict():
    """Test Pattern serialization"""
    pattern = Pattern(
        pattern_id="pat_002",
        pattern_type="sequence",
        description="Sequence pattern",
        elements=["a", "b", "c"],
        frequency=2,
        confidence=0.75,
        source_traces=["trace1", "trace2"]
    )
    
    data = pattern.to_dict()
    assert data["pattern_id"] == "pat_002"
    assert data["frequency"] == 2
    assert len(data["source_traces"]) == 2
    print("✅ Pattern to_dict")


def test_insight_creation():
    """Test Insight dataclass"""
    insight = Insight(
        insight_id="ins_001",
        insight_type=InsightType.STRATEGY_IMPROVEMENT,
        description="Strategy needs improvement",
        evidence=["trace_001"],
        confidence=0.8,
        suggested_action="Try alternative approach"
    )
    
    assert insight.insight_id == "ins_001"
    assert insight.insight_type == InsightType.STRATEGY_IMPROVEMENT
    assert insight.actionable is True
    print("✅ Insight creation")


def test_insight_to_dict():
    """Test Insight serialization"""
    insight = Insight(
        insight_id="ins_002",
        insight_type=InsightType.ERROR_PATTERN,
        description="Error detected",
        evidence=["trace_002"],
        confidence=0.7
    )
    
    data = insight.to_dict()
    assert data["insight_type"] == "error_pattern"
    assert data["confidence"] == 0.7
    assert data["applied"] is False
    print("✅ Insight to_dict")


def test_trace_analyzer_initialization():
    """Test TraceAnalyzer setup"""
    analyzer = TraceAnalyzer()
    assert len(analyzer.patterns) == 0
    assert len(analyzer.pattern_index) == 0
    print("✅ TraceAnalyzer initialization")


def test_trace_analyzer_success_pattern():
    """Test pattern extraction from successful trace"""
    analyzer = TraceAnalyzer()
    
    trace = ExecutionTrace(
        trace_id="test_success",
        goal="Successful task",
        start_time=datetime.now().timestamp()
    )
    
    # Add successful steps
    for i in range(5):
        trace.add_step(f"action_{i}", {"result": f"ok_{i}"}, True)
    
    trace.end_time = datetime.now().timestamp()
    
    patterns = analyzer.analyze_trace(trace)
    
    # Should extract success pattern and sequence pattern
    assert len(patterns) >= 1
    success_patterns = [p for p in patterns if p.pattern_type == "success"]
    assert len(success_patterns) >= 1
    print("✅ TraceAnalyzer success pattern")


def test_trace_analyzer_failure_pattern():
    """Test pattern extraction from failing trace"""
    analyzer = TraceAnalyzer()
    
    trace = ExecutionTrace(
        trace_id="test_failure",
        goal="Failing task",
        start_time=datetime.now().timestamp()
    )
    
    # Add mostly failing steps
    trace.add_step("action_1", {"result": "ok"}, True)
    trace.add_step("action_2", {"error": "fail"}, False)
    trace.add_step("action_3", {"error": "fail"}, False)
    trace.add_step("action_4", {"error": "fail"}, False)
    
    trace.end_time = datetime.now().timestamp()
    
    patterns = analyzer.analyze_trace(trace)
    
    # Should extract failure pattern
    failure_patterns = [p for p in patterns if p.pattern_type == "failure"]
    assert len(failure_patterns) >= 1
    print("✅ TraceAnalyzer failure pattern")


def test_trace_analyzer_multiple_traces():
    """Test pattern extraction from multiple traces"""
    analyzer = TraceAnalyzer()
    
    traces = []
    for i in range(3):
        trace = ExecutionTrace(
            trace_id=f"trace_{i}",
            goal="Similar task",
            start_time=datetime.now().timestamp()
        )
        
        # Similar action sequences
        trace.add_step("step_A", {"result": "ok"}, True)
        trace.add_step("step_B", {"result": "ok"}, True)
        trace.end_time = datetime.now().timestamp()
        
        traces.append(trace)
    
    patterns = analyzer.analyze_multiple_traces(traces, min_frequency=2)
    
    # Should find recurring patterns
    assert len(patterns) >= 1
    assert all(p.frequency >= 2 for p in patterns)
    print("✅ TraceAnalyzer multiple traces")


def test_trace_analyzer_find_similar():
    """Test finding similar patterns"""
    analyzer = TraceAnalyzer()
    
    # Create trace and extract patterns
    trace = ExecutionTrace(
        trace_id="test_similar",
        goal="Test task",
        start_time=datetime.now().timestamp()
    )
    
    trace.add_step("search_web", {"results": 10}, True)
    trace.add_step("analyze_results", {"insights": 3}, True)
    trace.add_step("synthesize", {"summary": "done"}, True)
    trace.end_time = datetime.now().timestamp()
    
    analyzer.analyze_trace(trace)
    
    # Find similar patterns
    similar = analyzer.find_similar_patterns(["search_web", "analyze"], limit=5)
    
    # Should find at least one pattern with "search_web"
    assert len(similar) >= 1
    print("✅ TraceAnalyzer find similar")


def test_insight_generator_initialization():
    """Test InsightGenerator setup"""
    generator = InsightGenerator()
    assert len(generator.insights) == 0
    assert len(generator.insight_history) == 0
    print("✅ InsightGenerator initialization")


def test_insight_generator_strategy_improvement():
    """Test strategy improvement insight generation"""
    generator = InsightGenerator()
    
    trace = ExecutionTrace(
        trace_id="test_strategy",
        goal="Task with failures",
        start_time=datetime.now().timestamp()
    )
    
    # Low success rate trace
    trace.add_step("action_1", {"result": "ok"}, True)
    trace.add_step("action_2", {"error": "fail"}, False)
    trace.add_step("action_3", {"error": "fail"}, False)
    trace.add_step("action_4", {"error": "fail"}, False)
    trace.end_time = datetime.now().timestamp()
    
    insights = generator.generate_insights(trace, [])
    
    # Should generate strategy improvement insight
    strategy_insights = [i for i in insights if i.insight_type == InsightType.STRATEGY_IMPROVEMENT]
    assert len(strategy_insights) >= 1
    print("✅ InsightGenerator strategy improvement")


def test_insight_generator_success_pattern():
    """Test success pattern insight generation"""
    generator = InsightGenerator()
    
    trace = ExecutionTrace(
        trace_id="test_success_insight",
        goal="Successful task",
        start_time=datetime.now().timestamp()
    )
    
    # High success rate
    for i in range(5):
        trace.add_step(f"action_{i}", {"result": "ok"}, True)
    trace.end_time = datetime.now().timestamp()
    
    # Create success pattern
    pattern = Pattern(
        pattern_id="pat_success",
        pattern_type="success",
        description="Success pattern",
        elements=["action_0", "action_1"],
        frequency=1,
        confidence=0.8,
        source_traces=[trace.trace_id]
    )
    
    insights = generator.generate_insights(trace, [pattern])
    
    # Should generate success insight
    success_insights = [i for i in insights if i.insight_type == InsightType.SUCCESS_PATTERN]
    assert len(success_insights) >= 1
    print("✅ InsightGenerator success pattern")


def test_insight_generator_knowledge_gap():
    """Test knowledge gap insight generation"""
    generator = InsightGenerator()
    
    trace = ExecutionTrace(
        trace_id="test_knowledge",
        goal="Task with unknowns",
        start_time=datetime.now().timestamp()
    )
    
    # Add step with "not found" error
    trace.add_step("lookup_info", {"error": "Information not found"}, False)
    trace.end_time = datetime.now().timestamp()
    
    insights = generator.generate_insights(trace, [])
    
    # Should generate knowledge gap insight
    gap_insights = [i for i in insights if i.insight_type == InsightType.KNOWLEDGE_GAP]
    assert len(gap_insights) >= 1
    print("✅ InsightGenerator knowledge gap")


def test_insight_generator_actionable_insights():
    """Test retrieving actionable insights"""
    generator = InsightGenerator()
    
    # Add some insights
    for i in range(3):
        insight = Insight(
            insight_id=f"ins_{i}",
            insight_type=InsightType.STRATEGY_IMPROVEMENT,
            description=f"Insight {i}",
            evidence=["trace"],
            confidence=0.7 + i * 0.1,
            actionable=True
        )
        generator.insights[insight.insight_id] = insight
    
    # Add one that's already applied
    applied_insight = Insight(
        insight_id="ins_applied",
        insight_type=InsightType.ERROR_PATTERN,
        description="Already applied",
        evidence=["trace"],
        confidence=0.9,
        actionable=True,
        applied=True
    )
    generator.insights[applied_insight.insight_id] = applied_insight
    
    # Get actionable insights
    actionable = generator.get_actionable_insights(min_confidence=0.7)
    
    # Should get 3 (not the applied one)
    assert len(actionable) == 3
    print("✅ InsightGenerator actionable insights")


def test_reflector_initialization():
    """Test Reflector setup"""
    reflector = Reflector()
    assert reflector.scope == ReflectionScope.EPISODE
    assert len(reflector.traces) == 0
    print("✅ Reflector initialization")


def test_reflector_start_trace():
    """Test starting a trace"""
    reflector = Reflector()
    
    trace_id = reflector.start_trace("Test goal", {"metadata": "test"})
    
    assert trace_id is not None
    assert trace_id in reflector.traces
    assert reflector.current_trace is not None
    assert reflector.current_trace.goal == "Test goal"
    print("✅ Reflector start_trace")


def test_reflector_record_step():
    """Test recording steps"""
    reflector = Reflector()
    
    trace_id = reflector.start_trace("Test goal")
    reflector.record_step(trace_id, "action_1", {"result": "ok"}, True)
    reflector.record_step(trace_id, "action_2", {"error": "fail"}, False)
    
    trace = reflector.traces[trace_id]
    assert len(trace.steps) == 2
    assert trace.success_rate == 0.5
    print("✅ Reflector record_step")


def test_reflector_end_trace():
    """Test ending a trace"""
    reflector = Reflector()
    
    trace_id = reflector.start_trace("Test goal")
    reflector.record_step(trace_id, "action", {"result": "ok"}, True)
    
    trace = reflector.end_trace(trace_id)
    
    assert trace.end_time is not None
    assert trace.duration > 0
    print("✅ Reflector end_trace")


def test_reflector_reflect():
    """Test reflection on a trace"""
    reflector = Reflector()
    
    trace_id = reflector.start_trace("Test goal")
    reflector.record_step(trace_id, "action_1", {"result": "ok"}, True)
    reflector.record_step(trace_id, "action_2", {"result": "ok"}, True)
    reflector.record_step(trace_id, "action_3", {"result": "ok"}, True)
    
    trace = reflector.end_trace(trace_id)
    reflection = reflector.reflect(trace)
    
    assert "trace_id" in reflection
    assert "patterns" in reflection
    assert "insights" in reflection
    assert reflection["success_rate"] == 1.0
    print("✅ Reflector reflect")


def test_reflector_evaluate_complete():
    """Test evaluation when goal appears complete"""
    reflector = Reflector()
    
    # Mock observations with success
    class MockObs:
        def __init__(self, success, result=""):
            self.success = success
            self.result = result
    
    observations = [
        MockObs(True, "Task complete"),
        MockObs(True, "Done")
    ]
    
    result = reflector.evaluate("Test goal", [], observations, {})
    
    assert result["complete"] is True
    assert result["should_continue"] is False
    print("✅ Reflector evaluate complete")


def test_reflector_evaluate_continue():
    """Test evaluation when should continue"""
    reflector = Reflector()
    
    class MockObs:
        def __init__(self, success, result=""):
            self.success = success
            self.result = result
    
    observations = [
        MockObs(True, "step 1"),
        MockObs(True, "step 2")
    ]
    
    result = reflector.evaluate("Test goal", [], observations, {})
    
    assert result["complete"] is False
    assert result["should_continue"] is True
    print("✅ Reflector evaluate continue")


def test_reflector_batch_reflect():
    """Test batch reflection on multiple traces"""
    reflector = Reflector()
    
    traces = []
    for i in range(3):
        trace_id = reflector.start_trace(f"Task {i}")
        reflector.record_step(trace_id, "action_A", {"result": "ok"}, True)
        reflector.record_step(trace_id, "action_B", {"result": "ok"}, True)
        trace = reflector.end_trace(trace_id)
        traces.append(trace)
    
    batch_result = reflector.reflect_batch(traces)
    
    assert batch_result["trace_count"] == 3
    assert batch_result["avg_success_rate"] == 1.0
    assert batch_result["recurring_patterns"] >= 1
    print("✅ Reflector batch reflect")


def test_reflector_get_stats():
    """Test getting trace statistics"""
    reflector = Reflector()
    
    # Create some traces
    for i in range(3):
        trace_id = reflector.start_trace(f"Task {i}")
        reflector.record_step(trace_id, "action", {"result": "ok"}, True)
        reflector.end_trace(trace_id)
    
    stats = reflector.get_trace_stats()
    
    assert stats["trace_count"] == 3
    assert stats["avg_success_rate"] == 1.0
    print("✅ Reflector get stats")


def test_create_reflector_factory():
    """Test factory function"""
    reflector = create_reflector()
    
    assert isinstance(reflector, Reflector)
    print("✅ create_reflector factory")


def test_quick_reflect():
    """Test quick reflection convenience function"""
    actions = [
        ("search", {"results": 10}, True),
        ("analyze", {"insights": 3}, True),
        ("synthesize", {"summary": "done"}, True)
    ]
    
    result = quick_reflect("Research task", actions)
    
    assert "trace_id" in result
    assert "patterns" in result
    assert "insights" in result
    assert result["success_rate"] == 1.0
    print("✅ quick_reflect")


def test_reflection_scope_enum():
    """Test reflection scope enum"""
    assert ReflectionScope.SINGLE_STEP.value == "single_step"
    assert ReflectionScope.EPISODE.value == "episode"
    assert ReflectionScope.SESSION.value == "session"
    assert ReflectionScope.LIFETIME.value == "lifetime"
    print("✅ ReflectionScope enum")


def test_insight_type_enum():
    """Test insight type enum"""
    assert InsightType.STRATEGY_IMPROVEMENT.value == "strategy_improvement"
    assert InsightType.ERROR_PATTERN.value == "error_pattern"
    assert InsightType.SUCCESS_PATTERN.value == "success_pattern"
    assert InsightType.KNOWLEDGE_GAP.value == "knowledge_gap"
    assert InsightType.EFFICIENCY_GAIN.value == "efficiency_gain"
    assert InsightType.TOOL_RECOMMENDATION.value == "tool_recommendation"
    print("✅ InsightType enum")


def test_reflector_to_dict():
    """Test Reflector serialization"""
    reflector = Reflector()
    
    # Create a trace
    trace_id = reflector.start_trace("Test")
    reflector.record_step(trace_id, "action", {}, True)
    reflector.end_trace(trace_id)
    
    data = reflector.to_dict()
    
    assert data["scope"] == "episode"
    assert data["trace_count"] == 1
    print("✅ Reflector to_dict")


# Run all tests
if __name__ == "__main__":
    tests = [
        test_execution_trace_creation,
        test_execution_trace_add_step,
        test_execution_trace_duration,
        test_execution_trace_to_dict,
        test_pattern_creation,
        test_pattern_to_dict,
        test_insight_creation,
        test_insight_to_dict,
        test_trace_analyzer_initialization,
        test_trace_analyzer_success_pattern,
        test_trace_analyzer_failure_pattern,
        test_trace_analyzer_multiple_traces,
        test_trace_analyzer_find_similar,
        test_insight_generator_initialization,
        test_insight_generator_strategy_improvement,
        test_insight_generator_success_pattern,
        test_insight_generator_knowledge_gap,
        test_insight_generator_actionable_insights,
        test_reflector_initialization,
        test_reflector_start_trace,
        test_reflector_record_step,
        test_reflector_end_trace,
        test_reflector_reflect,
        test_reflector_evaluate_complete,
        test_reflector_evaluate_continue,
        test_reflector_batch_reflect,
        test_reflector_get_stats,
        test_create_reflector_factory,
        test_quick_reflect,
        test_reflection_scope_enum,
        test_insight_type_enum,
        test_reflector_to_dict,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__}: {e}")
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"Results: {passed}/{len(tests)} tests passed")
    if failed == 0:
        print("✅ All tests passed!")
    else:
        print(f"❌ {failed} test(s) failed")
        sys.exit(1)
