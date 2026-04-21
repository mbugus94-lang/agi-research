"""
Agent Integration Test

Validates the core agent architecture:
- Identity persistence
- Task creation and execution
- Skill registration
- State management
"""

import sys
sys.path.insert(0, '/home/workspace/agi-research')

from core.agent import BaseAgent, AgentIdentity, Task, AgentState
from skills.web_search import web_search
from skills.code_gen import generate_code, review_code
from skills.analysis import analyze_patterns, synthesize
import json


def test_identity_persistence():
    """Test that agent identity is created and accessible"""
    print("\n=== Test: Identity Persistence ===")
    
    agent = BaseAgent()
    identity = agent.get_identity()
    
    assert "id" in identity, "Identity should have an ID"
    assert "version" in identity, "Identity should have version"
    assert "core_values" in identity, "Identity should have core values"
    
    print(f"✓ Identity created: {identity['name']} v{identity['version']}")
    print(f"✓ Core values: {', '.join(identity['core_values'])}")
    return True


def test_skill_registration():
    """Test skill registration and execution"""
    print("\n=== Test: Skill Registration ===")
    
    agent = BaseAgent()
    
    # Register skills
    agent.register_skill("web_search", web_search)
    agent.register_skill("generate_code", generate_code)
    agent.register_skill("analyze_patterns", analyze_patterns)
    
    status = agent.get_status()
    registered_skills = status["skills"]
    
    assert "web_search" in registered_skills, "web_search should be registered"
    assert "generate_code" in registered_skills, "generate_code should be registered"
    
    print(f"✓ Registered {len(registered_skills)} skills: {registered_skills}")
    return True


def test_task_creation():
    """Test task creation"""
    print("\n=== Test: Task Creation ===")
    
    agent = BaseAgent()
    task = agent.create_task(
        description="Test research task",
        goal="Research AGI architecture",
        context={"topic": "AGI"}
    )
    
    assert task.id is not None, "Task should have an ID"
    assert task.description == "Test research task", "Description should match"
    assert task.status == "pending", "New task should be pending"
    
    print(f"✓ Task created: {task.id[:8]}... - {task.description}")
    return True


def test_task_execution():
    """Test task execution with mock skills"""
    print("\n=== Test: Task Execution ===")
    
    agent = BaseAgent()
    
    # Mock skill that always succeeds
    def mock_skill(**kwargs):
        return {"status": "completed", "mock": True}
    
    agent.register_skill("mock_execute", mock_skill)
    
    task = agent.create_task(
        description="Execute mock task",
        goal="Test execution flow"
    )
    
    result = agent.execute_task(task, max_iterations=3)
    
    print(f"✓ Task executed: {result.status}")
    print(f"✓ Final state: {agent.state.value}")
    
    return True


def test_skill_execution_web_search():
    """Test web search skill execution"""
    print("\n=== Test: Web Search Skill ===")
    
    result = web_search("AGI research", num_results=3)
    
    assert result["success"], "Web search should succeed"
    assert "results" in result, "Should return results"
    assert len(result["results"]) > 0, "Should have at least one result"
    
    print(f"✓ Search returned {result['results_count']} results")
    print(f"✓ First result: {result['results'][0]['title'][:50]}...")
    
    return True


def test_skill_execution_code_gen():
    """Test code generation skill"""
    print("\n=== Test: Code Generation Skill ===")
    
    result = generate_code("A function to calculate factorial", language="python")
    
    assert "code" in result, "Should return code"
    assert "language" in result, "Should specify language"
    assert result["language"] == "python", "Language should be python"
    
    print(f"✓ Code generated ({len(result['code'])} chars)")
    print(f"✓ Explanation: {result['explanation'][:50]}...")
    
    return True


def test_code_review():
    """Test code review skill"""
    print("\n=== Test: Code Review Skill ===")
    
    # Code with security issue
    risky_code = '''
user_input = input("Enter code: ")
result = eval(user_input)
print(result)
'''
    
    result = review_code(risky_code, review_type="security")
    
    assert result["issues_found"] > 0, "Should find security issues"
    
    print(f"✓ Found {result['issues_found']} security issues")
    for issue in result["issues"]:
        print(f"  - [{issue['severity']}] {issue['message']}")
    
    return True


def test_analysis_skill():
    """Test analysis skill"""
    print("\n=== Test: Analysis Skill ===")
    
    data = ["a", "b", "a", "c", "a", "b", "a"]
    result = analyze_patterns(data, pattern_type="frequency")
    
    assert "findings" in result, "Should return findings"
    assert result["confidence"] > 0, "Should have confidence score"
    
    print(f"✓ Pattern analysis complete (confidence: {result['confidence']:.0%})")
    
    return True


def test_state_management():
    """Test agent state transitions"""
    print("\n=== Test: State Management ===")
    
    agent = BaseAgent()
    
    # Check initial state
    assert agent.state == AgentState.IDLE, "Initial state should be IDLE"
    
    # Register skill and execute to trigger state change
    def slow_skill(**kwargs):
        # State would change to EXECUTING here
        return {"done": True}
    
    agent.register_skill("slow", slow_skill)
    
    # After execution, should return to IDLE
    task = agent.create_task("Test", "Test state")
    agent.execute_task(task, max_iterations=1)
    
    assert agent.state == AgentState.IDLE, "Should return to IDLE"
    
    print(f"✓ State transitions working correctly")
    return True


def test_save_load():
    """Test agent state save/load"""
    print("\n=== Test: Save/Load State ===")
    
    import tempfile
    import os
    
    agent = BaseAgent()
    task = agent.create_task("Test task", "Test goal")
    
    # Save
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        temp_path = f.name
    
    agent.save_state(temp_path)
    
    # Load
    agent2 = BaseAgent()
    agent2.load_state(temp_path)
    
    assert agent2.identity.id == agent.identity.id, "ID should persist"
    assert len(agent2.task_history) == len(agent.task_history), "Task history should persist"
    
    os.unlink(temp_path)
    
    print(f"✓ State save/load working correctly")
    return True


def run_all_tests():
    """Run all validation tests"""
    print("=" * 60)
    print("AGI Agent Integration Tests")
    print("=" * 60)
    
    tests = [
        test_identity_persistence,
        test_skill_registration,
        test_task_creation,
        test_task_execution,
        test_skill_execution_web_search,
        test_skill_execution_code_gen,
        test_code_review,
        test_analysis_skill,
        test_state_management,
        test_save_load
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"✗ {test.__name__} FAILED")
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__} ERROR: {e}")
    
    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
