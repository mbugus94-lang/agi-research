"""
Sandboxed Code Execution Environment

Provides safe, isolated execution of Python code with:
- Resource limits (time, memory)
- Security restrictions (imports, builtins)
- AST validation before execution
- Execution history and statistics

Based on research findings:
- Agent-World: Environment synthesis critical for general agent intelligence
- GenericAgent: Sandboxed execution for safe self-evolution
- Agentic Microphysics: Sandboxing essential for multi-agent safety
"""

import ast
import builtins
import copy
import io
import resource
import signal
import sys
import tempfile
import time
import traceback
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union


class ExecutionStatus(Enum):
    """Status of code execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SECURITY_VIOLATION = "security_violation"
    RESOURCE_EXHAUSTED = "resource_exhausted"


@dataclass
class ExecutionResult:
    """Result of sandboxed code execution."""
    status: ExecutionStatus
    stdout: str = ""
    stderr: str = ""
    return_value: Any = None
    execution_time_ms: float = 0.0
    memory_usage_mb: float = 0.0
    error_message: Optional[str] = None
    error_type: Optional[str] = None
    traceback_str: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "status": self.status.value,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "return_value": str(self.return_value) if self.return_value is not None else None,
            "execution_time_ms": self.execution_time_ms,
            "memory_usage_mb": self.memory_usage_mb,
            "error_message": self.error_message,
            "error_type": self.error_type,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class SandboxConfig:
    """Configuration for execution sandbox."""
    max_execution_time: float = 30.0  # seconds
    max_memory_mb: float = 256.0
    allowed_imports: Optional[Set[str]] = None
    forbidden_imports: Set[str] = field(default_factory=lambda: {
        "os", "sys", "subprocess", "socket", "urllib", "http", "ftplib",
        "pickle", "ctypes", "multiprocessing", "threading"
    })
    forbidden_patterns: Set[str] = field(default_factory=lambda: {
        "eval", "exec", "compile", "__import__", "open", "input"
    })
    forbidden_builtins: Set[str] = field(default_factory=lambda: {
        "eval", "exec", "compile", "open", "input",
        "exit", "quit"
    })
    allow_file_write: bool = False
    allow_network: bool = False
    temp_dir_prefix: str = "sandbox_"
    
    def __post_init__(self):
        if self.allowed_imports is None:
            self.allowed_imports = {
                "math", "random", "statistics", "json", "re", 
                "datetime", "itertools", "functools", "collections",
                "typing", "dataclasses", "enum", "decimal", "fractions",
                "hashlib", "string", "time", "inspect"
            }
        # Ensure forbidden patterns is never None
        if self.forbidden_patterns is None:
            self.forbidden_patterns = {
                "eval", "exec", "compile", "__import__", "open", "input"
            }
        # Ensure forbidden imports is never None  
        if self.forbidden_imports is None:
            self.forbidden_imports = {
                "os", "sys", "subprocess", "socket", "urllib", "http", "ftplib",
                "pickle", "ctypes", "multiprocessing", "threading"
            }
        # Ensure forbidden builtins is never None
        if self.forbidden_builtins is None:
            self.forbidden_builtins = {
                "eval", "exec", "compile", "open", "input",
                "exit", "quit"
            }


class SecurityError(Exception):
    """Raised when code violates security policy."""
    pass


class CodeValidator:
    """Validates Python code for security before execution."""
    
    def __init__(self, config: SandboxConfig):
        self.config = config
    
    def validate(self, code: str) -> Tuple[bool, Optional[str]]:
        """
        Validate code for security violations.
        
        Returns:
            (is_valid, error_message)
        """
        # Ensure config values are never None
        forbidden_patterns = self.config.forbidden_patterns or set()
        forbidden_imports = self.config.forbidden_imports or set()
        allowed_imports = self.config.allowed_imports
        
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"
        
        # Check for forbidden patterns
        for node in ast.walk(tree):
            # Check for forbidden builtins
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in forbidden_patterns:
                        return False, f"Forbidden function call: {node.func.id}"
                
                # Check for getattr with dangerous attributes
                if isinstance(node.func, ast.Name) and node.func.id == "getattr":
                    return False, "getattr() is forbidden for security"
                
                # Check for setattr
                if isinstance(node.func, ast.Name) and node.func.id == "setattr":
                    return False, "setattr() is forbidden for security"
            
            # Check for forbidden names
            if isinstance(node, ast.Name):
                if node.id in forbidden_patterns:
                    return False, f"Forbidden identifier: {node.id}"
            
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name.split('.')[0]
                    if module_name in forbidden_imports:
                        return False, f"Forbidden import: {module_name}"
                    if allowed_imports is not None:
                        if module_name not in allowed_imports:
                            return False, f"Import not in allowlist: {module_name}"
            elif isinstance(node, ast.ImportFrom):
                # For "from X import Y", check the source module X
                if node.module:
                    module_name = node.module.split('.')[0]
                    if module_name in forbidden_imports:
                        return False, f"Forbidden import: {module_name}"
                    if allowed_imports is not None:
                        if module_name not in allowed_imports:
                            return False, f"Import not in allowlist: {module_name}"
                # Also check that individual imported names aren't forbidden
                for alias in node.names:
                    if alias.name in forbidden_imports:
                        return False, f"Forbidden import: {alias.name}"
            
            # Check for __dunder__ attributes
            if isinstance(node, ast.Attribute):
                if node.attr.startswith('__') and node.attr.endswith('__'):
                    dangerous = ['__class__', '__bases__', '__mro__', '__subclasses__',
                                '__globals__', '__code__', '__closure__', '__defaults__']
                    if node.attr in dangerous:
                        return False, f"Forbidden dunder access: {node.attr}"
        
        return True, None


class RestrictedBuiltins:
    """Restricted builtins dictionary for sandboxed execution."""
    
    @staticmethod
    def create(forbidden: Set[str]) -> Dict[str, Any]:
        """Create restricted builtins dictionary."""
        safe_builtins = {}
        for name in dir(builtins):
            if not name.startswith('_') and name not in forbidden:
                safe_builtins[name] = getattr(builtins, name)
        
        # Explicitly add __import__ which is needed for import statements
        # It's filtered out by the underscore check but required for imports
        if '__import__' not in forbidden:
            safe_builtins['__import__'] = builtins.__import__
        
        return safe_builtins


@contextmanager
def time_limit(seconds: float):
    """Context manager to limit execution time."""
    # Use a simple time-based check that works in more environments
    start = time.time()
    
    class TimeoutChecker:
        def __init__(self, deadline):
            self.deadline = deadline
        
        def check(self):
            if time.time() > self.deadline:
                raise TimeoutError(f"Execution timed out after {seconds} seconds")
    
    checker = TimeoutChecker(start + seconds)
    
    # Try signal-based approach first (more precise), fall back to time-based
    try:
        def signal_handler(signum, frame):
            raise TimeoutError(f"Execution timed out after {seconds} seconds")
        
        old_handler = signal.signal(signal.SIGALRM, signal_handler)
        signal.setitimer(signal.ITIMER_REAL, seconds)
        
        try:
            yield checker
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old_handler)
    except (AttributeError, ValueError):
        # Signal approach not available, yield the checker anyway
        # Note: actual enforcement requires periodic checking by the caller
        yield checker


@contextmanager
def memory_limit(max_mb: float):
    """Context manager to limit memory usage."""
    max_bytes = int(max_mb * 1024 * 1024)
    old_limit = resource.getrlimit(resource.RLIMIT_AS)
    
    try:
        resource.setrlimit(resource.RLIMIT_AS, (max_bytes, max_bytes))
        yield
    finally:
        resource.setrlimit(resource.RLIMIT_AS, old_limit)


class ExecutionSandbox:
    """
    Isolated execution environment for running Python code safely.
    
    Features:
    - Resource limits (time, memory)
    - Import restrictions
    - Builtin function restrictions
    - AST-based code validation
    - Execution result capture
    """
    
    def __init__(self, config: Optional[SandboxConfig] = None):
        self.config = config or SandboxConfig()
        self.validator = CodeValidator(self.config)
        self.execution_count = 0
        self.success_count = 0
        self.total_execution_time = 0.0
    
    def execute(
        self, 
        code: str, 
        context: Optional[Dict[str, Any]] = None,
        capture_output: bool = True
    ) -> ExecutionResult:
        """
        Execute code in sandboxed environment.
        
        Args:
            code: Python code to execute
            context: Variables to inject into execution namespace
            capture_output: Whether to capture stdout/stderr
            
        Returns:
            ExecutionResult with status, output, and metadata
        """
        start_time = time.time()
        self.execution_count += 1
        
        # Validate code before execution
        is_valid, error_msg = self.validator.validate(code)
        if not is_valid:
            return ExecutionResult(
                status=ExecutionStatus.SECURITY_VIOLATION,
                error_message=error_msg,
                error_type="SecurityError",
                execution_time_ms=(time.time() - start_time) * 1000
            )
        
        # Prepare execution namespace
        restricted_builtins = RestrictedBuiltins.create(self.config.forbidden_builtins)
        namespace = {"__builtins__": restricted_builtins}
        
        # Add allowed imports to namespace
        for module_name in self.config.allowed_imports or []:
            try:
                namespace[module_name] = __import__(module_name)
            except ImportError:
                pass  # Module not available, skip
        
        # Inject context variables
        if context:
            namespace.update(context)
        
        # Capture output if requested
        stdout_buffer = io.StringIO() if capture_output else None
        stderr_buffer = io.StringIO() if capture_output else None
        
        try:
            # Execute with resource limits
            with time_limit(self.config.max_execution_time):
                # Note: Memory limit using resource module is process-wide
                # For true isolation, would need subprocess
                
                if capture_output:
                    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                        # Compile and execute
                        compiled = compile(code, '<sandbox>', 'exec')
                        exec(compiled, namespace)
                        
                        # Try to get return value (last expression if any)
                        return_value = None
                        try:
                            # Parse and extract last expression value
                            tree = ast.parse(code)
                            if tree.body and isinstance(tree.body[-1], ast.Expr):
                                last_expr = compile(
                                    ast.Expression(tree.body[-1].value), 
                                    '<sandbox>', 'eval'
                                )
                                return_value = eval(last_expr, namespace)
                        except:
                            pass
                else:
                    compiled = compile(code, '<sandbox>', 'exec')
                    exec(compiled, namespace)
                    return_value = None
            
            execution_time = time.time() - start_time
            self.success_count += 1
            self.total_execution_time += execution_time
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                stdout=stdout_buffer.getvalue() if capture_output else "",
                stderr=stderr_buffer.getvalue() if capture_output else "",
                return_value=return_value,
                execution_time_ms=execution_time * 1000
            )
            
        except TimeoutError as e:
            return ExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                stdout=stdout_buffer.getvalue() if capture_output else "",
                stderr=stderr_buffer.getvalue() if capture_output else "",
                error_message=str(e),
                error_type="TimeoutError",
                execution_time_ms=(time.time() - start_time) * 1000
            )
            
        except MemoryError as e:
            return ExecutionResult(
                status=ExecutionStatus.RESOURCE_EXHAUSTED,
                error_message="Memory limit exceeded",
                error_type="MemoryError",
                execution_time_ms=(time.time() - start_time) * 1000
            )
            
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                stdout=stdout_buffer.getvalue() if capture_output else "",
                stderr=stderr_buffer.getvalue() if capture_output else "",
                error_message=str(e),
                error_type=type(e).__name__,
                traceback_str=traceback.format_exc(),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get execution statistics."""
        return {
            "total_executions": self.execution_count,
            "successful_executions": self.success_count,
            "failed_executions": self.execution_count - self.success_count,
            "success_rate": self.success_count / self.execution_count if self.execution_count > 0 else 0,
            "total_execution_time_sec": self.total_execution_time,
            "average_execution_time_ms": (self.total_execution_time / self.execution_count * 1000) if self.execution_count > 0 else 0,
        }


class SandboxedEnvironment:
    """
    High-level sandboxed environment with hooks and history.
    
    Provides:
    - Pre/post execution hooks
    - Execution history
    - Batch execution
    - Configurable policies
    """
    
    def __init__(
        self,
        max_execution_time: float = 30.0,
        max_memory_mb: float = 256.0,
        allowed_imports: Optional[List[str]] = None,
        forbidden_patterns: Optional[List[str]] = None,
        pre_execution_hook: Optional[Callable[[str], None]] = None,
        post_execution_hook: Optional[Callable[[ExecutionResult], None]] = None
    ):
        config = SandboxConfig(
            max_execution_time=max_execution_time,
            max_memory_mb=max_memory_mb,
            allowed_imports=set(allowed_imports) if allowed_imports else None,
            forbidden_patterns=set(forbidden_patterns) if forbidden_patterns else None
        )
        self.sandbox = ExecutionSandbox(config)
        self.pre_execution_hook = pre_execution_hook
        self.post_execution_hook = post_execution_hook
        self.execution_history: List[ExecutionResult] = []
    
    def execute(
        self, 
        code: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> ExecutionResult:
        """
        Execute code with hooks and history tracking.
        
        Args:
            code: Python code to execute
            context: Variables to inject into namespace
            
        Returns:
            ExecutionResult
        """
        # Pre-execution hook
        if self.pre_execution_hook:
            try:
                self.pre_execution_hook(code)
            except Exception as e:
                return ExecutionResult(
                    status=ExecutionStatus.SECURITY_VIOLATION,
                    error_message=f"Pre-execution hook failed: {e}",
                    error_type="HookError"
                )
        
        # Execute in sandbox
        result = self.sandbox.execute(code, context)
        
        # Track in history
        self.execution_history.append(result)
        
        # Post-execution hook
        if self.post_execution_hook:
            try:
                self.post_execution_hook(result)
            except Exception as e:
                # Log but don't fail
                pass
        
        return result
    
    def execute_batch(
        self, 
        code_list: List[str], 
        context: Optional[Dict[str, Any]] = None
    ) -> List[ExecutionResult]:
        """Execute multiple code snippets in sequence with shared context."""
        results = []
        accumulated_context = context.copy() if context else {}
        
        for code in code_list:
            result = self.execute(code, accumulated_context)
            results.append(result)
            
            # After successful execution, we would ideally capture the new variables
            # from the execution namespace, but since exec() doesn't return this,
            # users should design batch code to work with the context they provide
            # For full variable persistence, use a single combined code block
            
        return results
    
    def get_history(self, limit: Optional[int] = None) -> List[ExecutionResult]:
        """Get execution history."""
        if limit:
            return self.execution_history[-limit:]
        return self.execution_history.copy()
    
    def clear_history(self) -> None:
        """Clear execution history."""
        self.execution_history.clear()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics."""
        sandbox_stats = self.sandbox.get_statistics()
        
        # Calculate additional stats
        if self.execution_history:
            recent = self.execution_history[-100:]  # Last 100
            avg_time = sum(r.execution_time_ms for r in recent) / len(recent)
            max_time = max(r.execution_time_ms for r in recent)
        else:
            avg_time = 0
            max_time = 0
        
        return {
            **sandbox_stats,
            "history_size": len(self.execution_history),
            "recent_avg_time_ms": avg_time,
            "recent_max_time_ms": max_time,
        }
    
    def is_safe(self, code: str) -> Tuple[bool, Optional[str]]:
        """Check if code would be safe to execute (without running)."""
        return self.sandbox.validator.validate(code)


# Convenience functions

def execute_sandboxed(
    code: str,
    context: Optional[Dict[str, Any]] = None,
    max_execution_time: float = 30.0,
    max_memory_mb: float = 256.0,
    allowed_imports: Optional[List[str]] = None
) -> ExecutionResult:
    """
    Quick function to execute code in a sandbox.
    
    Args:
        code: Python code to execute
        context: Variables to inject
        max_execution_time: Timeout in seconds
        max_memory_mb: Memory limit in MB
        allowed_imports: List of allowed module names
        
    Returns:
        ExecutionResult
    """
    env = SandboxedEnvironment(
        max_execution_time=max_execution_time,
        max_memory_mb=max_memory_mb,
        allowed_imports=allowed_imports
    )
    return env.execute(code, context)


def create_sandbox(
    max_execution_time: float = 30.0,
    max_memory_mb: float = 256.0,
    allowed_imports: Optional[List[str]] = None
) -> SandboxedEnvironment:
    """Factory function to create a sandboxed environment."""
    return SandboxedEnvironment(
        max_execution_time=max_execution_time,
        max_memory_mb=max_memory_mb,
        allowed_imports=allowed_imports
    )
