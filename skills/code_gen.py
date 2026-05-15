"""
Code Generation Skill

Capability for generating, analyzing, and executing code.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass


@dataclass
class CodeResult:
    """Result of code generation/execution"""
    code: str
    language: str
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None


class CodeGenSkill:
    """
    Skill for code generation and execution.
    
    Supports multiple languages and execution contexts.
    """
    
    def __init__(self):
        self.name = "code_gen"
        self.description = "Generate, analyze, and execute code"
        self.capabilities = [
            "write code",
            "generate code",
            "execute code",
            "analyze code",
            "refactor code",
            "debug code"
        ]
        self.supported_languages = ["python", "javascript", "typescript", "bash", "json"]
    
    def can_handle(self, action: str, context: Dict[str, Any]) -> bool:
        """Check if this skill can handle the action."""
        action_lower = action.lower()
        
        code_keywords = [
            "code", "program", "script", "function", "class",
            "write", "generate", "create", "implement",
            "execute", "run", "test", "debug", "refactor"
        ]
        
        language_keywords = [
            "python", "javascript", "typescript", "js", "ts",
            "bash", "shell", "json", "yaml"
        ]
        
        # Check for code-related keywords
        has_code_keyword = any(kw in action_lower for kw in code_keywords)
        has_language = any(lang in action_lower for lang in language_keywords)
        
        return has_code_keyword or has_language
    
    def execute(self, action: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute code generation/execution action."""
        # Determine operation type
        operation = self._determine_operation(action)
        
        # Extract language
        language = self._detect_language(action, context)
        
        # Extract code or specification
        spec = self._extract_specification(action, context)
        
        if operation == "generate":
            return self._handle_generate(spec, language, context)
        elif operation == "execute":
            return self._handle_execute(spec, language, context)
        elif operation == "analyze":
            return self._handle_analyze(spec, context)
        elif operation == "debug":
            return self._handle_debug(spec, context)
        else:
            return {
                "success": False,
                "error": f"Unknown operation: {operation}",
                "supported_operations": ["generate", "execute", "analyze", "debug"]
            }
    
    def _determine_operation(self, action: str) -> str:
        """Determine the operation type from action."""
        action_lower = action.lower()
        
        if any(kw in action_lower for kw in ["write", "generate", "create", "implement"]):
            return "generate"
        elif any(kw in action_lower for kw in ["execute", "run", "test"]):
            return "execute"
        elif any(kw in action_lower for kw in ["analyze", "review", "check"]):
            return "analyze"
        elif any(kw in action_lower for kw in ["debug", "fix", "repair"]):
            return "debug"
        
        # Default to generate
        return "generate"
    
    def _detect_language(self, action: str, context: Dict[str, Any]) -> str:
        """Detect programming language from action."""
        action_lower = action.lower()
        
        # Check for explicit language mentions
        if "python" in action_lower or ".py" in action_lower:
            return "python"
        elif "typescript" in action_lower or ".ts" in action_lower:
            return "typescript"
        elif "javascript" in action_lower or ".js" in action_lower:
            return "javascript"
        elif "bash" in action_lower or "shell" in action_lower:
            return "bash"
        elif "json" in action_lower:
            return "json"
        
        # Default to Python
        return "python"
    
    def _extract_specification(self, action: str, context: Dict[str, Any]) -> str:
        """Extract code specification from action."""
        # Remove operation keywords
        spec = action
        for kw in ["write code", "generate", "create", "implement", "execute", "run", "debug", "fix"]:
            spec = spec.replace(kw, "").replace(kw.title(), "")
        
        # Remove language mentions
        for lang in ["python", "javascript", "typescript", "bash", "shell"]:
            spec = spec.replace(f"in {lang}", "").replace(lang, "")
        
        return spec.strip(": ")
    
    def _handle_generate(
        self,
        spec: str,
        language: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle code generation."""
        return {
            "success": True,
            "operation": "generate",
            "specification": spec,
            "language": language,
            "note": "Code generation request recorded",
            "code": None,  # Would be generated by LLM
            "metadata": {
                "line_count_estimate": spec.count("\n") + 10,
                "complexity": self._estimate_complexity(spec)
            }
        }
    
    def _handle_execute(
        self,
        spec: str,
        language: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle code execution."""
        return {
            "success": True,
            "operation": "execute",
            "language": language,
            "note": "Code execution framework ready",
            "output": None,  # Would contain actual output
            "execution_context": {
                "sandbox": True,
                "timeout": 30,
                "allowed_imports": ["os", "sys", "json", "re", "math", "random"]
            }
        }
    
    def _handle_analyze(self, spec: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle code analysis."""
        return {
            "success": True,
            "operation": "analyze",
            "note": "Code analysis framework ready",
            "analysis_types": ["syntax", "style", "complexity", "security"]
        }
    
    def _handle_debug(self, spec: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle debugging."""
        return {
            "success": True,
            "operation": "debug",
            "note": "Debugging framework ready",
            "approach": ["identify_error", "analyze_cause", "propose_fix", "verify_fix"]
        }
    
    def _estimate_complexity(self, spec: str) -> str:
        """Estimate complexity of code to generate."""
        word_count = len(spec.split())
        
        if word_count < 10:
            return "simple"
        elif word_count < 30:
            return "moderate"
        else:
            return "complex"
    
    def learn_from(self, experience: Dict[str, Any]) -> None:
        """Learn from code generation experience."""
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "supported_languages": self.supported_languages,
            "capabilities": self.capabilities
        }
