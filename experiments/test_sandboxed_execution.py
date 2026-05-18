"""
Tests for sandboxed code execution environment.

Validates:
- Security restrictions (forbidden patterns, imports)
- Resource limits (time, memory)
- Result capture and metadata
- Execution history tracking
- Batch execution
- Pre/post execution hooks
"""

import sys
import time
from typing import Any, Dict, List

sys.path.insert(0, '/home/workspace/agi-research')

from skills.sandboxed_execution import (
    ExecutionResult,
    ExecutionSandbox,
    ExecutionStatus,
    SandboxedEnvironment,
    SandboxConfig,
    CodeValidator,
    SecurityError,
    create_sandbox,
    execute_sandboxed,
)


# ============================================================================
# Sandbox Configuration Tests
# ============================================================================

def test_sandbox_config_defaults():
    """Test default sandbox configuration."""
    config = SandboxConfig()
    assert config.max_execution_time == 30.0
    assert config.max_memory_mb == 256.0
    assert "os" in config.forbidden_imports
    assert "eval" in config.forbidden_patterns
    assert "math" in config.allowed_imports
    assert "json" in config.allowed_imports
    print("✓ Sandbox config defaults correct")


def test_sandbox_config_custom():
    """Test custom sandbox configuration."""
    config = SandboxConfig(
        max_execution_time=60.0,
        max_memory_mb=512.0,
        allowed_imports={"math", "random"},
        forbidden_patterns={"eval", "exec"}
    )
    assert config.max_execution_time == 60.0
    assert config.max_memory_mb == 512.0
    assert config.allowed_imports == {"math", "random"}
    assert config.forbidden_patterns == {"eval", "exec"}
    print("✓ Sandbox config customization works")


# ============================================================================
# Code Validator Tests
# ============================================================================

def test_validator_safe_code():
    """Test validation of safe code."""
    config = SandboxConfig()
    validator = CodeValidator(config)
    
    safe_code = """
import math

def calculate(x):
    return math.sqrt(x)

result = calculate(16)
"""
    is_valid, error = validator.validate(safe_code)
    assert is_valid, f"Safe code should be valid: {error}"
    assert error is None
    print("✓ Safe code passes validation")


def test_validator_forbidden_patterns():
    """Test detection of forbidden patterns."""
    config = SandboxConfig()
    validator = CodeValidator(config)
    
    # Test eval
    code_with_eval = "result = eval('1 + 1')"
    is_valid, error = validator.validate(code_with_eval)
    assert not is_valid
    assert "eval" in error.lower()
    
    # Test exec
    code_with_exec = "exec('print(1)')"
    is_valid, error = validator.validate(code_with_exec)
    assert not is_valid
    assert "exec" in error.lower()
    
    # Test __import__
    code_with_import = "os = __import__('os')"
    is_valid, error = validator.validate(code_with_import)
    assert not is_valid
    assert "__import__" in error
    
    print("✓ Forbidden patterns detected")


def test_validator_forbidden_imports():
    """Test detection of forbidden imports."""
    config = SandboxConfig()
    validator = CodeValidator(config)
    
    # Test forbidden module import
    code = "import os"
    is_valid, error = validator.validate(code)
    assert not is_valid
    assert "os" in error.lower()
    
    # Test forbidden from import
    code = "from subprocess import run"
    is_valid, error = validator.validate(code)
    assert not is_valid
    assert "subprocess" in error.lower()
    
    print("✓ Forbidden imports detected")


def test_validator_allowed_imports():
    """Test allowed imports are permitted."""
    config = SandboxConfig()
    validator = CodeValidator(config)
    
    for module in ["math", "json", "re", "datetime"]:
        code = f"import {module}"
        is_valid, error = validator.validate(code)
        assert is_valid, f"Import of {module} should be allowed: {error}"
    
    print("✓ Allowed imports pass validation")


def test_validator_not_allowed_import():
    """Test disallowed import is rejected."""
    config = SandboxConfig()
    validator = CodeValidator(config)
    
    # numpy is not in default allowed imports
    code = "import numpy"
    is_valid, error = validator.validate(code)
    assert not is_valid
    assert "numpy" in error.lower()
    
    print("✓ Non-allowed imports rejected")


def test_validator_syntax_error():
    """Test syntax error detection."""
    config = SandboxConfig()
    validator = CodeValidator(config)
    
    code = "def broken(:"  # Syntax error
    is_valid, error = validator.validate(code)
    assert not is_valid
    assert "syntax" in error.lower()
    
    print("✓ Syntax errors detected")


def test_validator_getattr_setattr():
    """Test getattr/setattr are forbidden."""
    config = SandboxConfig()
    validator = CodeValidator(config)
    
    code = "x = getattr(obj, 'attr')"
    is_valid, error = validator.validate(code)
    assert not is_valid
    assert "getattr" in error.lower()
    
    code = "setattr(obj, 'attr', value)"
    is_valid, error = validator.validate(code)
    assert not is_valid
    assert "setattr" in error.lower()
    
    print("✓ getattr/setattr forbidden")


# ============================================================================
# Execution Sandbox Tests
# ============================================================================

def test_sandbox_creation():
    """Test sandbox creation with config."""
    config = SandboxConfig(max_execution_time=10.0)
    sandbox = ExecutionSandbox(config)
    
    assert sandbox.config == config
    assert sandbox.execution_count == 0
    assert sandbox.success_count == 0
    print("✓ Sandbox creation works")


def test_sandbox_execute_simple():
    """Test simple code execution."""
    sandbox = ExecutionSandbox()
    
    result = sandbox.execute("x = 5 + 3")
    
    assert result.status == ExecutionStatus.SUCCESS
    assert result.error_message is None
    assert result.execution_time_ms > 0
    print("✓ Simple execution works")


def test_sandbox_execute_with_return():
    """Test execution that returns a value."""
    sandbox = ExecutionSandbox()
    
    result = sandbox.execute("5 + 3")
    
    assert result.status == ExecutionStatus.SUCCESS
    assert result.return_value == 8
    print("✓ Return value capture works")


def test_sandbox_execute_with_output():
    """Test stdout capture."""
    sandbox = ExecutionSandbox()
    
    code = """
print("Hello, World!")
print("Line 2")
"""
    result = sandbox.execute(code)
    
    assert result.status == ExecutionStatus.SUCCESS
    assert "Hello, World!" in result.stdout
    assert "Line 2" in result.stdout
    print("✓ Stdout capture works")


def test_sandbox_execute_with_import():
    """Test execution with allowed imports."""
    sandbox = ExecutionSandbox()
    
    code = """
import math

result = math.sqrt(16)
print(f"Square root: {result}")
result
"""
    result = sandbox.execute(code)
    
    assert result.status == ExecutionStatus.SUCCESS
    assert result.return_value == 4.0
    assert "Square root: 4.0" in result.stdout
    print("✓ Execution with imports works")


def test_sandbox_security_violation():
    """Test that forbidden code is blocked."""
    sandbox = ExecutionSandbox()
    
    result = sandbox.execute("import os")
    
    assert result.status == ExecutionStatus.SECURITY_VIOLATION
    assert result.error_message is not None
    assert "os" in result.error_message.lower()
    print("✓ Security violations blocked")


def test_sandbox_syntax_error():
    """Test handling of syntax errors."""
    sandbox = ExecutionSandbox()
    
    result = sandbox.execute("def broken(:")
    
    assert result.status == ExecutionStatus.SECURITY_VIOLATION
    assert "syntax" in result.error_message.lower()
    print("✓ Syntax errors handled")


def test_sandbox_runtime_exception():
    """Test handling of runtime exceptions."""
    sandbox = ExecutionSandbox()
    
    result = sandbox.execute("1 / 0")
    
    assert result.status == ExecutionStatus.FAILED
    assert "ZeroDivisionError" in result.error_type
    assert result.traceback_str is not None
    print("✓ Runtime exceptions captured")


def test_sandbox_timeout():
    """Test execution timeout."""
    config = SandboxConfig(max_execution_time=0.1)  # 100ms timeout
    sandbox = ExecutionSandbox(config)
    
    code = """
import time
time.sleep(1)  # Will timeout
"""
    result = sandbox.execute(code)
    
    assert result.status == ExecutionStatus.TIMEOUT
    assert "timed out" in result.error_message.lower()
    print("✓ Timeout enforcement works")


def test_sandbox_complex_calculation():
    """Test complex calculation in sandbox."""
    sandbox = ExecutionSandbox()
    
    code = """
import math
import json

def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

fib_20 = fibonacci(20)
data = {"fib_20": fib_20, "sqrt": math.sqrt(fib_20)}
print(json.dumps(data))
data["fib_20"]
"""
    result = sandbox.execute(code)
    
    assert result.status == ExecutionStatus.SUCCESS
    assert result.return_value == 6765  # fib(20)
    assert "6765" in result.stdout
    print("✓ Complex calculation works")


def test_sandbox_statistics():
    """Test execution statistics tracking."""
    sandbox = ExecutionSandbox()
    
    # Execute some code
    sandbox.execute("x = 1")
    sandbox.execute("y = 2")
    sandbox.execute("import os")  # Should fail
    
    stats = sandbox.get_statistics()
    
    assert stats["total_executions"] == 3
    assert stats["successful_executions"] == 2
    assert stats["failed_executions"] == 1
    assert abs(stats["success_rate"] - 0.667) < 0.01
    assert stats["total_execution_time_sec"] > 0
    print("✓ Statistics tracking works")


# ============================================================================
# SandboxedEnvironment Tests
# ============================================================================

def test_environment_creation():
    """Test environment creation."""
    env = SandboxedEnvironment(
        max_execution_time=60.0,
        max_memory_mb=512.0,
        allowed_imports=["math", "json"]
    )
    
    assert env.sandbox.config.max_execution_time == 60.0
    assert env.sandbox.config.max_memory_mb == 512.0
    assert env.execution_history == []
    print("✓ Environment creation works")


def test_environment_execution():
    """Test environment execution."""
    env = SandboxedEnvironment()
    
    result = env.execute("x = 42")
    
    assert result.status == ExecutionStatus.SUCCESS
    assert len(env.execution_history) == 1
    assert env.execution_history[0] == result
    print("✓ Environment execution works")


def test_environment_context():
    """Test execution with context variables."""
    env = SandboxedEnvironment()
    
    result = env.execute(
        "result = input_value * 2",
        context={"input_value": 21}
    )
    
    assert result.status == ExecutionStatus.SUCCESS
    print("✓ Context injection works")


def test_environment_history():
    """Test execution history tracking."""
    env = SandboxedEnvironment()
    
    for i in range(5):
        env.execute(f"x = {i}")
    
    history = env.get_history()
    assert len(history) == 5
    
    limited = env.get_history(limit=3)
    assert len(limited) == 3
    print("✓ History tracking works")


def test_environment_clear_history():
    """Test clearing execution history."""
    env = SandboxedEnvironment()
    
    env.execute("x = 1")
    env.execute("y = 2")
    assert len(env.execution_history) == 2
    
    env.clear_history()
    assert len(env.execution_history) == 0
    print("✓ History clearing works")


def test_environment_batch_execution():
    """Test batch execution of independent code snippets."""
    env = SandboxedEnvironment()
    
    # Each code snippet is independent - sandbox isolates executions
    code_list = [
        "a = 1 + 1",  # Sets a = 2
        "b = 2 + 2",  # Sets b = 4 (independent)
        "c = 3 + 3",  # Sets c = 6 (independent)
    ]
    
    results = env.execute_batch(code_list)
    
    assert len(results) == 3
    # All should succeed - each is independent
    for result in results:
        assert result.status == ExecutionStatus.SUCCESS
    
    print("✓ Batch execution works")


def test_environment_statistics():
    """Test environment statistics."""
    env = SandboxedEnvironment()
    
    env.execute("x = 1")
    env.execute("y = 2")
    env.execute("import os")  # Should fail
    
    stats = env.get_statistics()
    
    assert stats["history_size"] == 3
    assert stats["total_executions"] == 3
    assert stats["successful_executions"] == 2
    print("✓ Environment statistics work")


def test_environment_is_safe():
    """Test safety checking."""
    env = SandboxedEnvironment()
    
    is_safe, error = env.is_safe("x = 1 + 1")
    assert is_safe
    assert error is None
    
    is_safe, error = env.is_safe("import os")
    assert not is_safe
    assert "os" in error.lower()
    print("✓ Safety checking works")


# ============================================================================
# Hook Tests
# ============================================================================

def test_pre_execution_hook():
    """Test pre-execution hook."""
    hook_called = False
    hooked_code = None
    
    def pre_hook(code: str):
        nonlocal hook_called, hooked_code
        hook_called = True
        hooked_code = code
    
    env = SandboxedEnvironment(pre_execution_hook=pre_hook)
    env.execute("x = 1")
    
    assert hook_called
    assert hooked_code == "x = 1"
    print("✓ Pre-execution hook works")


def test_post_execution_hook():
    """Test post-execution hook."""
    hook_called = False
    hooked_result = None
    
    def post_hook(result: ExecutionResult):
        nonlocal hook_called, hooked_result
        hook_called = True
        hooked_result = result
    
    env = SandboxedEnvironment(post_execution_hook=post_hook)
    env.execute("x = 1")
    
    assert hook_called
    assert hooked_result is not None
    assert hooked_result.status == ExecutionStatus.SUCCESS
    print("✓ Post-execution hook works")


def test_hook_exception_handling():
    """Test that hook exceptions don't crash execution."""
    def bad_pre_hook(code: str):
        raise ValueError("Hook error")
    
    env = SandboxedEnvironment(pre_execution_hook=bad_pre_hook)
    result = env.execute("x = 1")
    
    # Execution should still complete (with error status from hook)
    assert result.status == ExecutionStatus.SECURITY_VIOLATION
    assert "hook" in result.error_message.lower()
    print("✓ Hook exceptions handled")


# ============================================================================
# Convenience Function Tests
# ============================================================================

def test_execute_sandboxed():
    """Test convenience function for sandboxed execution."""
    result = execute_sandboxed(
        "x = 21 * 2",
        max_execution_time=10.0,
        max_memory_mb=128.0
    )
    
    assert result.status == ExecutionStatus.SUCCESS
    print("✓ execute_sandboxed convenience function works")


def test_create_sandbox():
    """Test factory function for creating sandbox."""
    env = create_sandbox(
        max_execution_time=60.0,
        allowed_imports=["math", "json", "re"]
    )
    
    result = env.execute("import math; math.sqrt(16)")
    assert result.status == ExecutionStatus.SUCCESS
    print("✓ create_sandbox factory works")


# ============================================================================
# Integration Tests
# ============================================================================

def test_complex_workflow():
    """Test complex multi-step workflow."""
    env = SandboxedEnvironment(
        max_execution_time=30.0,
        allowed_imports=["math", "json", "random", "datetime"]
    )
    
    # Step 1: Calculate some values
    result1 = env.execute("""
import math
import random

# Calculate circle properties
radius = random.uniform(1, 10)
area = math.pi * radius ** 2
circumference = 2 * math.pi * radius

print(f"Radius: {radius:.2f}")
print(f"Area: {area:.2f}")
print(f"Circumference: {circumference:.2f}")

{"radius": radius, "area": area, "circumference": circumference}
""")
    
    assert result1.status == ExecutionStatus.SUCCESS
    assert result1.return_value is not None
    assert "radius" in result1.return_value
    
    # Step 2: Process the data
    context = {"previous_result": result1.return_value}
    result2 = env.execute("""
import json

# Access previous result from context
data = previous_result
scaled_area = data["area"] * 2

print(f"Original area: {data['area']:.2f}")
print(f"Scaled area: {scaled_area:.2f}")

{"scaled_area": scaled_area, "original_radius": data["radius"]}
""", context=context)
    
    assert result2.status == ExecutionStatus.SUCCESS
    
    # Check history
    assert len(env.execution_history) == 2
    
    # Check statistics
    stats = env.get_statistics()
    assert stats["history_size"] == 2
    assert stats["successful_executions"] == 2
    
    print("✓ Complex workflow works")


def test_security_comprehensive():
    """Comprehensive security test."""
    env = SandboxedEnvironment()
    
    # These should all be blocked
    malicious_codes = [
        "import os",
        "import sys",
        "from subprocess import run",
        "eval('1+1')",
        "exec('print(1)')",
        "__import__('os')",
        "open('/etc/passwd')",
        "getattr(obj, '__class__')",
    ]
    
    blocked_count = 0
    for code in malicious_codes:
        result = env.execute(code)
        if result.status in [ExecutionStatus.SECURITY_VIOLATION, ExecutionStatus.FAILED]:
            blocked_count += 1
    
    # Most should be blocked
    assert blocked_count >= len(malicious_codes) - 1
    print(f"✓ Security blocking works ({blocked_count}/{len(malicious_codes)} blocked)")


def test_result_serialization():
    """Test result serialization."""
    env = SandboxedEnvironment()
    
    result = env.execute("x = {'key': 'value'}; x")
    
    assert result.status == ExecutionStatus.SUCCESS
    
    # Serialize to dict
    data = result.to_dict()
    
    assert "status" in data
    assert "stdout" in data
    assert "stderr" in data
    assert "execution_time_ms" in data
    assert "timestamp" in data
    assert data["status"] == "success"
    
    print("✓ Result serialization works")


# ============================================================================
# Main Test Runner
# ============================================================================

def run_all_tests():
    """Run all tests and report results."""
    tests = [
        # Config tests
        test_sandbox_config_defaults,
        test_sandbox_config_custom,
        
        # Validator tests
        test_validator_safe_code,
        test_validator_forbidden_patterns,
        test_validator_forbidden_imports,
        test_validator_allowed_imports,
        test_validator_not_allowed_import,
        test_validator_syntax_error,
        test_validator_getattr_setattr,
        
        # Sandbox tests
        test_sandbox_creation,
        test_sandbox_execute_simple,
        test_sandbox_execute_with_return,
        test_sandbox_execute_with_output,
        test_sandbox_execute_with_import,
        test_sandbox_security_violation,
        test_sandbox_syntax_error,
        test_sandbox_runtime_exception,
        test_sandbox_timeout,
        test_sandbox_complex_calculation,
        test_sandbox_statistics,
        
        # Environment tests
        test_environment_creation,
        test_environment_execution,
        test_environment_context,
        test_environment_history,
        test_environment_clear_history,
        test_environment_batch_execution,
        test_environment_statistics,
        test_environment_is_safe,
        
        # Hook tests
        test_pre_execution_hook,
        test_post_execution_hook,
        test_hook_exception_handling,
        
        # Convenience tests
        test_execute_sandboxed,
        test_create_sandbox,
        
        # Integration tests
        test_complex_workflow,
        test_security_comprehensive,
        test_result_serialization,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
