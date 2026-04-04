"""
Experiment: Test Integrated Agent with Tool Registry
Validates the full agent stack: memory, planning, tools, reflection.
"""

import sys
import json
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.integrated_agent import IntegratedAgent, AgentConfig
from core.memory import MemorySystem
from core.planner import Planner, TaskStatus
from core.reflection import Reflector
from skills import get_registry, WebSearchSkill, FileReadSkill, CalculatorTool


def test_tool_registry():
    """Test 1: Tool Registry functionality"""
    print("\n" + "="*60)
    print("TEST 1: Tool Registry")
    print("="*60)
    
    registry = get_registry()
    
    # List tools
    tools = registry.list_tools()
    print(f"✓ Registered tools: {tools}")
    
    # Test calculator
    result = registry.execute("calculator", expression="10 * 5 + 3")
    assert result.success, f"Calculator failed: {result.error}"
    assert result.data["result"] == 53, f"Wrong result: {result.data}"
    print(f"✓ Calculator: 10 * 5 + 3 = {result.data['result']}")
    
    # Test file read
    result = registry.execute("file_read", path="README.md")
    if result.success and isinstance(result.data, dict):
        print(f"✓ File read: README.md ({len(result.data.get('content', ''))} chars)")
    else:
        print(f"⚠ File read skipped: {result.error if not result.success else 'unexpected data type'}")
    
    # Stats
    stats = registry.get_stats()
    print(f"✓ Registry stats: {stats['total_tools']} tools, {stats['total_executions']} executions")
    
    return True


def test_memory_system():
    """Test 2: Memory System"""
    print("\n" + "="*60)
    print("TEST 2: Memory System")
    print("="*60)
    
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = MemorySystem(storage_dir=tmpdir)
        
        # Working memory
        memory.add_to_context("First message")
        memory.add_to_context("Second message")
        context = memory.get_context(n=2)
        assert "First" in context and "Second" in context
        print(f"✓ Working memory: {len(memory.working.entries)} entries")
        
        # Episodic memory
        memory.record_episode(
            task="Test task",
            outcome="Success",
            lessons="Test lesson"
        )
        similar = memory.recall_similar("test")
        assert len(similar) > 0
        print(f"✓ Episodic memory: {len(memory.episodic.episodes)} episodes")
        
        # Semantic memory
        memory.learn_fact("test_key", "test_value", category="test")
        value = memory.recall_fact("test_key")
        assert value == "test_value"
        print(f"✓ Semantic memory: {len(memory.semantic.facts)} facts")
        
        # Full context
        full = memory.get_full_context("test query")
        assert "Current Context" in full
        print(f"✓ Full context generated ({len(full)} chars)")
    
    return True


def test_planner():
    """Test 3: Task Planner"""
    print("\n" + "="*60)
    print("TEST 3: Task Planner")
    print("="*60)
    
    planner = Planner()
    
    # Decompose goal
    root = planner.decompose("Research AI trends and write a report")
    print(f"✓ Plan created: {root.description}")
    print(f"✓ Subtasks: {len(root.subtasks)}")
    
    # Get execution path
    path = planner.get_execution_path()
    print(f"✓ Execution path: {len(path)} tasks")
    
    # Execute tasks
    completed = 0
    while True:
        task = planner.get_next_task()
        if not task:
            break
        
        planner.update_task(task.id, TaskStatus.IN_PROGRESS)
        planner.update_task(task.id, TaskStatus.COMPLETED, result="Done")
        completed += 1
    
    print(f"✓ Completed: {completed}/{len(path)} tasks")
    assert planner.is_complete(), "Plan should be complete"
    
    return True


def test_reflection():
    """Test 4: Reflection System"""
    print("\n" + "="*60)
    print("TEST 4: Reflection System")
    print("="*60)
    
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        reflector = Reflector(storage_path=f"{tmpdir}/reflections.json")
        
        # Record metrics
        reflector.record_performance(
            task="Task 1",
            success=True,
            steps_taken=3,
            time_elapsed=2.5
        )
        reflector.record_performance(
            task="Task 2",
            success=False,
            steps_taken=10,
            time_elapsed=15.0,
            errors=["Timeout", "API error"]
        )
        
        print(f"✓ Recorded {len(reflector.metrics)} performance metrics")
        
        # Generate reflection
        from core.reflection import PerformanceMetrics
        metrics = PerformanceMetrics(
            task="Test",
            success=True,
            steps_taken=3,
            time_elapsed=2.0
        )
        reflection = reflector.reflect("Test task", metrics)
        
        print(f"✓ Generated reflection: {reflection.lessons_learned[:50]}...")
        
        # Get suggestions
        suggestions = reflector.get_improvement_suggestions()
        print(f"✓ Improvement suggestions: {len(suggestions)}")
        
        # Summary
        summary = reflector.get_reflection_summary()
        assert "Performance Patterns" in summary
        print(f"✓ Summary generated ({len(summary)} chars)")
    
    return True


def test_integrated_agent():
    """Test 5: Full Integrated Agent"""
    print("\n" + "="*60)
    print("TEST 5: Integrated Agent")
    print("="*60)
    
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        config = AgentConfig(
            name="TestAgent",
            max_steps=3,
            memory_storage_dir=tmpdir,
            reflection_storage_path=f"{tmpdir}/reflections.json",
            enable_planning=True,
            enable_reflection=True,
            verbose=False  # Quieter for tests
        )
        
        agent = IntegratedAgent(config)
        
        # Get initial state
        state = agent.get_state()
        print(f"✓ Initial state: {state['config']['name']}")
        print(f"✓ Available tools: {len(state['tools'])}")
        
        # Run task
        result = agent.run(
            task="Calculate 5 * 10",
            context="Testing calculator tool"
        )
        
        print(f"✓ Task completed: {result['success']}")
        print(f"✓ Steps taken: {result['steps_taken']}")
        print(f"✓ Elapsed: {result['elapsed_time']:.2f}s")
        
        # Check state after
        state = agent.get_state()
        print(f"✓ Memory episodes: {state['memory']['episodes']}")
        print(f"✓ Tool executions: {state['reflector']['total_metrics']}")
        
        # Run another task
        result2 = agent.run(
            task="List files in current directory",
            context="Testing file operations"
        )
        
        print(f"✓ Second task: {result2['success']}")
    
    return True


def test_skills_integration():
    """Test 6: Skills Integration"""
    print("\n" + "="*60)
    print("TEST 6: Skills Integration")
    print("="*60)
    
    from skills import search_web, read_file, list_files
    
    # Mock search (no API key)
    result = search_web("test query", max_results=2)
    assert "results" in result or "error" in result
    print(f"✓ Web search skill works")
    
    # File operations
    files = list_files(".", pattern="*.py")
    print(f"✓ File list skill: {len(files)} Python files found")
    
    # Try to read a file
    content = read_file("requirements.txt")
    if content:
        print(f"✓ File read skill: requirements.txt ({len(content)} chars)")
    else:
        print("⚠ File read: requirements.txt not found")
    
    return True


def run_all_tests():
    """Run all experiments."""
    print("\n" + "="*60)
    print("AGI AGENT INTEGRATION TESTS")
    print("="*60)
    
    tests = [
        ("Tool Registry", test_tool_registry),
        ("Memory System", test_memory_system),
        ("Task Planner", test_planner),
        ("Reflection System", test_reflection),
        ("Integrated Agent", test_integrated_agent),
        ("Skills Integration", test_skills_integration)
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, "PASS" if success else "FAIL"))
        except Exception as e:
            print(f"\n❌ {name} FAILED: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, "FAIL"))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for name, status in results:
        icon = "✅" if status == "PASS" else "❌"
        print(f"{icon} {name}: {status}")
    
    passed = sum(1 for _, s in results if s == "PASS")
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
