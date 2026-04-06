"""
Experiment: Code Generation Skill Validation

Hypothesis: The code generation skill can produce valid, safe code
with appropriate safety guardrails and review requirements.

This experiment validates:
1. Code generation produces syntactically valid code
2. Safety scoring correctly identifies dangerous patterns
3. Self-modification requires review as per safety policy
4. Generated code includes appropriate tests
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from skills.code_generation import CodeGenerationSkill, generate_code, analyze_code


def test_code_generation():
    """Test basic code generation."""
    print("\\n" + "="*60)
    print("TEST 1: Basic Code Generation")
    print("="*60)
    
    skill = CodeGenerationSkill()
    
    # Test Python function generation
    result = skill.execute(
        action="generate",
        language="python",
        specification="Create a function that calculates fibonacci numbers",
        safety_level="strict"
    )
    
    assert result.success, f"Generation failed: {result.error}"
    data = result.data
    
    print(f"✅ Code generated successfully")
    print(f"   Language: {data.get('language')}")
    print(f"   Safety score: {data.get('safety_score', 0):.2f}")
    print(f"   Requires review: {data.get('requires_review', True)}")
    print(f"   Validation: {data.get('validation', 'N/A')}")
    
    # Verify code is not empty
    code = data.get('code', '')
    assert code, "Generated code is empty"
    assert 'def ' in code, "Generated code should contain a function"
    
    print(f"\\n   Generated code preview (first 200 chars):")
    print(f"   {code[:200]}...")
    
    return True


def test_code_analysis():
    """Test code analysis capabilities."""
    print("\\n" + "="*60)
    print("TEST 2: Code Analysis")
    print("="*60)
    
    skill = CodeGenerationSkill()
    
    # Code with potential issues
    problematic_code = '''
def process_data(data):
    if data:
        result = eval(data)  # Dangerous!
        return result
    return None

def complex_function(n):
    for i in range(n):
        for j in range(n):
            for k in range(n):
                print(i, j, k)
'''
    
    result = skill.execute(
        action="analyze",
        language="python",
        specification=problematic_code
    )
    
    assert result.success, f"Analysis failed: {result.error}"
    data = result.data
    
    print(f"✅ Analysis completed")
    print(f"   Complexity: {data.get('complexity', 0)}")
    print(f"   Quality score: {data.get('quality_score', 0):.2f}")
    print(f"   Security concerns: {len(data.get('security_concerns', []))}")
    print(f"   Suggestions: {len(data.get('suggestions', []))}")
    
    # Verify security detection
    security = data.get('security_concerns', [])
    assert len(security) > 0, "Should detect eval() as security concern"
    
    print(f"\\n   Security concerns detected:")
    for concern in security[:3]:
        print(f"   - {concern}")
    
    return True


def test_safety_guardrails():
    """Test safety guardrails for dangerous code."""
    print("\\n" + "="*60)
    print("TEST 3: Safety Guardrails")
    print("="*60)
    
    skill = CodeGenerationSkill()
    
    # Generate code that might be unsafe
    result = skill.execute(
        action="generate",
        language="python",
        specification="Create a function that opens and writes to a file",
        safety_level="strict"
    )
    
    data = result.data
    safety_score = data.get('safety_score', 1.0)
    
    print(f"✅ Safety analysis completed")
    print(f"   Safety score: {safety_score:.2f}")
    print(f"   Requires review: {data.get('requires_review', True)}")
    
    # In strict mode, file operations should lower safety score
    assert safety_score < 1.0 or data.get('requires_review', True), \
        "File operations should trigger review requirement"
    
    safety_notes = data.get('safety_notes', [])
    print(f"\\n   Safety notes: {len(safety_notes)}")
    for note in safety_notes[:2]:
        print(f"   - {note}")
    
    return True


def test_test_generation():
    """Test automated test generation."""
    print("\\n" + "="*60)
    print("TEST 4: Test Generation")
    print("="*60)
    
    skill = CodeGenerationSkill()
    
    code_to_test = '''
def factorial(n):
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0 or n == 1:
        return 1
    return n * factorial(n - 1)
'''
    
    result = skill.execute(
        action="generate_tests",
        language="python",
        specification=code_to_test
    )
    
    assert result.success, f"Test generation failed: {result.error}"
    data = result.data
    
    print(f"✅ Tests generated")
    print(f"   Framework: {data.get('test_framework', 'N/A')}")
    print(f"   Coverage estimate: {data.get('coverage_estimate', 'N/A')}")
    
    tests = data.get('test_code', '')
    assert 'def test_' in tests, "Generated tests should contain test functions"
    
    print(f"\\n   Test code preview (first 300 chars):")
    print(f"   {tests[:300]}...")
    
    return True


def test_self_improvement_simulation():
    """Simulate self-improvement workflow."""
    print("\\n" + "="*60)
    print("TEST 5: Self-Improvement Simulation")
    print("="*60)
    
    skill = CodeGenerationSkill()
    
    # Step 1: Analyze existing code (simulated)
    existing_code = '''
def calculate_sum(numbers):
    result = 0
    for n in numbers:
        result = result + n
    return result
'''
    
    analysis_result = skill.execute(
        action="analyze",
        language="python",
        specification=existing_code
    )
    
    print(f"Step 1: Analysis complete")
    suggestions = analysis_result.data.get('suggestions', [])
    print(f"   Suggestions: {len(suggestions)}")
    
    # Step 2: Refactor based on analysis
    refactor_result = skill.execute(
        action="refactor",
        language="python",
        specification=existing_code,
        context="Add type hints and use built-in sum()"
    )
    
    print(f"\\nStep 2: Refactoring complete")
    print(f"   Success: {refactor_result.success}")
    print(f"   Requires review: {refactor_result.data.get('requires_review', True)}")
    
    # Step 3: Verify refactoring requires review (safety policy)
    assert refactor_result.data.get('requires_review', True), \
        "Self-modification must require review per safety policy"
    
    print(f"\\n✅ Self-improvement workflow validated")
    print(f"   Safety policy enforced: Changes require human review")
    
    return True


def run_all_tests():
    """Run all validation tests."""
    print("\\n" + "="*60)
    print("CODE GENERATION SKILL - VALIDATION EXPERIMENT")
    print("="*60)
    print("\\nHypothesis: Code generation skill produces valid, safe code")
    print("with appropriate safety guardrails and review requirements.")
    
    tests = [
        ("Code Generation", test_code_generation),
        ("Code Analysis", test_code_analysis),
        ("Safety Guardrails", test_safety_guardrails),
        ("Test Generation", test_test_generation),
        ("Self-Improvement", test_self_improvement_simulation),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success, None))
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"\\n❌ {name} failed: {e}")
    
    # Summary
    print("\\n" + "="*60)
    print("EXPERIMENT RESULTS")
    print("="*60)
    
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    for name, success, error in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"   {status}: {name}")
        if error:
            print(f"      Error: {error}")
    
    print(f"\\n{'='*60}")
    print(f"SUMMARY: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ HYPOTHESIS VALIDATED: Code generation skill works as expected")
        return 0
    else:
        print("⚠️ Some tests failed - review required")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
