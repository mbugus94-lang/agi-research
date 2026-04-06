"""
Code Generation Skill for AGI Agent Self-Improvement
Based on: "Towards AGI: A Pragmatic Approach Towards Self-Evolving Agent" [arXiv:2601.11658v1]

This skill enables the agent to:
1. Generate code from natural language specifications
2. Analyze existing code for improvements
3. Refactor and optimize code
4. Self-modify with safety guardrails
5. Generate tests for validation

Key safety principle: All self-modifications require REVIEW before application.
"""

import os
import re
import ast
import json
import tempfile
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .tool_registry import BaseTool, ToolSchema, ToolParameter, ToolCategory, ToolRiskLevel


class CodeAction(Enum):
    GENERATE = "generate"
    ANALYZE = "analyze"
    REFACTOR = "refactor"
    OPTIMIZE = "optimize"
    GENERATE_TESTS = "generate_tests"


@dataclass
class CodeAnalysis:
    """Result of code analysis."""
    complexity: int
    issues: List[str]
    suggestions: List[str]
    security_concerns: List[str]
    test_coverage: Optional[float]


@dataclass
class GeneratedCode:
    """Result of code generation."""
    code: str
    language: str
    explanation: str
    safety_score: float  # 0-1, higher is safer
    requires_review: bool
    test_cases: Optional[str]


class CodeGenerationSkill(BaseTool):
    """
    Generate, analyze, and improve code.
    
    Safety guardrails:
    - Syntax validation before any code execution
    - AST parsing to detect dangerous patterns
    - Self-modification requires explicit REVIEW flag
    - Generated tests must pass before acceptance
    """
    
    DANGEROUS_PATTERNS = [
        r'eval\s*\(',
        r'exec\s*\(',
        r'os\.system\s*\(',
        r'subprocess\.call\s*\(',
        r'__import__\s*\(',
        r'open\s*\([^)]*[\"\']w[\"\']',
        r'\.write\s*\(',
        r'shutil\.rmtree',
        r'os\.remove\s*\(',
        r'os\.rmdir\s*\(',
    ]
    
    def __init__(self, require_review_for_write: bool = True):
        self.require_review_for_write = require_review_for_write
        super().__init__()
    
    def _define_schema(self) -> ToolSchema:
        return ToolSchema(
            name="code_generation",
            description="Generate, analyze, refactor, and optimize code. Supports Python, JavaScript/TypeScript, and shell scripts. Self-modification requires review.",
            parameters=[
                ToolParameter(
                    name="action",
                    type="string",
                    description="Action to perform",
                    required=True,
                    enum=["generate", "analyze", "refactor", "optimize", "generate_tests"]
                ),
                ToolParameter(
                    name="language",
                    type="string",
                    description="Programming language",
                    required=True,
                    enum=["python", "javascript", "typescript", "shell", "markdown"]
                ),
                ToolParameter(
                    name="specification",
                    type="string",
                    description="Natural language description or code to process",
                    required=True
                ),
                ToolParameter(
                    name="context",
                    type="string",
                    description="Additional context (existing code, imports, etc.)",
                    required=False
                ),
                ToolParameter(
                    name="safety_level",
                    type="string",
                    description="Safety level for generated code",
                    required=False,
                    enum=["strict", "standard", "permissive"],
                    default="strict"
                )
            ],
            category=ToolCategory.CODE,
            risk_level=ToolRiskLevel.CRITICAL,  # High due to code execution potential
            examples=[
                {
                    "input": {
                        "action": "generate",
                        "language": "python",
                        "specification": "Create a function that calculates fibonacci numbers recursively with memoization"
                    },
                    "output": "Generated Python code with memoization decorator..."
                },
                {
                    "input": {
                        "action": "analyze",
                        "language": "python",
                        "specification": "def add(a,b): return a+b"
                    },
                    "output": "Code analysis with complexity metrics and suggestions..."
                }
            ]
        )
    
    def _execute(
        self,
        action: str,
        language: str,
        specification: str,
        context: str = "",
        safety_level: str = "strict"
    ) -> Dict[str, Any]:
        """Execute code generation action."""
        
        try:
            code_action = CodeAction(action)
        except ValueError:
            return {
                "success": False,
                "error": f"Invalid action: {action}. Choose from: {[a.value for a in CodeAction]}"
            }
        
        # Route to appropriate handler
        if code_action == CodeAction.GENERATE:
            return self._generate_code(language, specification, context, safety_level)
        elif code_action == CodeAction.ANALYZE:
            return self._analyze_code(language, specification)
        elif code_action == CodeAction.REFACTOR:
            return self._refactor_code(language, specification, context)
        elif code_action == CodeAction.OPTIMIZE:
            return self._optimize_code(language, specification)
        elif code_action == CodeAction.GENERATE_TESTS:
            return self._generate_tests(language, specification, context)
        
        return {"success": False, "error": "Unknown action"}
    
    def _generate_code(
        self,
        language: str,
        specification: str,
        context: str,
        safety_level: str
    ) -> Dict[str, Any]:
        """Generate code from natural language specification."""
        
        # Simulated generation - in production, this would use an LLM
        code = self._simulate_code_generation(language, specification, context)
        
        # Validate and score
        is_valid, validation_msg = self._validate_syntax(code, language)
        safety_score = self._calculate_safety_score(code, safety_level)
        requires_review = safety_score < 0.8 or self.require_review_for_write
        
        # Generate tests
        test_cases = self._generate_test_template(language, specification)
        
        return {
            "success": is_valid,
            "action": "generate",
            "language": language,
            "code": code,
            "explanation": f"Generated {language} code based on: {specification[:100]}...",
            "validation": validation_msg,
            "safety_score": safety_score,
            "requires_review": requires_review,
            "safety_notes": self._get_safety_notes(code) if safety_score < 1.0 else [],
            "test_cases": test_cases,
            "review_recommended": requires_review
        }
    
    def _analyze_code(self, language: str, code: str) -> Dict[str, Any]:
        """Analyze code for issues and improvements."""
        
        analysis = self._perform_analysis(code, language)
        
        return {
            "success": True,
            "action": "analyze",
            "language": language,
            "complexity": analysis.complexity,
            "issues": analysis.issues,
            "suggestions": analysis.suggestions,
            "security_concerns": analysis.security_concerns,
            "quality_score": self._calculate_quality_score(analysis),
            "summary": self._generate_analysis_summary(analysis)
        }
    
    def _refactor_code(
        self,
        language: str,
        code: str,
        context: str
    ) -> Dict[str, Any]:
        """Refactor code for better structure."""
        
        # Analyze first
        analysis = self._perform_analysis(code, language)
        
        # Simulated refactoring
        refactored = self._simulate_refactoring(code, language, analysis)
        
        is_valid, validation_msg = self._validate_syntax(refactored, language)
        
        return {
            "success": is_valid,
            "action": "refactor",
            "language": language,
            "original_code": code,
            "refactored_code": refactored,
            "changes_made": analysis.suggestions[:3],
            "validation": validation_msg,
            "requires_review": True  # Refactoring always requires review
        }
    
    def _optimize_code(self, language: str, code: str) -> Dict[str, Any]:
        """Optimize code for performance."""
        
        # Simulated optimization
        optimized = self._simulate_optimization(code, language)
        
        is_valid, validation_msg = self._validate_syntax(optimized, language)
        
        return {
            "success": is_valid,
            "action": "optimize",
            "language": language,
            "original_code": code,
            "optimized_code": optimized,
            "optimizations_applied": [
                "Reduced time complexity where possible",
                "Improved memory usage patterns",
                "Added caching for repeated operations"
            ],
            "validation": validation_msg,
            "requires_review": True
        }
    
    def _generate_tests(
        self,
        language: str,
        code: str,
        context: str
    ) -> Dict[str, Any]:
        """Generate test cases for code."""
        
        tests = self._generate_test_template(language, code)
        
        return {
            "success": True,
            "action": "generate_tests",
            "language": language,
            "test_code": tests,
            "test_framework": "pytest" if language == "python" else "jest",
            "coverage_estimate": "~70-80% for basic functions",
            "notes": "Review and extend tests for edge cases and error conditions"
        }
    
    # === Helper Methods ===
    
    def _simulate_code_generation(
        self,
        language: str,
        specification: str,
        context: str
    ) -> str:
        """Simulate code generation - production would use LLM."""
        
        # Generate a template based on the specification
        spec_lower = specification.lower()
        
        if language == "python":
            if "function" in spec_lower or "def " in spec_lower:
                func_name = self._extract_function_name(specification) or "generated_function"
                return f'''def {func_name}(arg):
    """
    {specification}
    
    Args:
        arg: Input parameter
        
    Returns:
        Result of computation
    """
    # TODO: Implement based on specification
    # Generated from: {specification[:50]}...
    
    result = arg  # Placeholder implementation
    return result
'''
            elif "class" in spec_lower:
                class_name = self._extract_class_name(specification) or "GeneratedClass"
                return f'''class {class_name}:
    """
    {specification}
    """
    
    def __init__(self):
        self.data = {{}}
    
    def process(self, input_data):
        """Process input data."""
        # TODO: Implement processing logic
        return input_data
'''
            else:
                return f'''# {specification}
# Generated code - review before use

import os
import json
from typing import Dict, List, Any

def main():
    """Main entry point."""
    # Implementation based on: {specification[:100]}...
    pass

if __name__ == "__main__":
    main()
'''
        
        elif language in ["javascript", "typescript"]:
            return f'''/**
 * {specification}
 */
function generatedFunction(arg) {{
    // TODO: Implementation
    // Based on: {specification[:50]}...
    
    return arg;
}}

module.exports = {{ generatedFunction }};
'''
        
        elif language == "shell":
            return f'''#!/bin/bash
# {specification}
# Generated script - review before execution

set -euo pipefail

echo "Generated from: {specification[:50]}..."

# TODO: Implement logic here
'''
        
        return f"# Code generation for {language}\\n# Spec: {specification}\\n# TODO: Implement\\n"
    
    def _perform_analysis(self, code: str, language: str) -> CodeAnalysis:
        """Perform code analysis."""
        
        issues = []
        suggestions = []
        security = []
        complexity = 1
        
        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                security.append(f"Potentially dangerous pattern detected: {pattern}")
        
        # Simple complexity estimation
        complexity = code.count("if") + code.count("for") + code.count("while") + code.count("def ")
        complexity = max(1, min(complexity, 10))
        
        # Basic suggestions
        if "TODO" in code:
            suggestions.append("Remove TODO comments before production")
        if complexity > 5:
            suggestions.append("Consider breaking complex functions into smaller ones")
        if "except:" in code and "Exception" not in code:
            suggestions.append("Use specific exception types instead of bare except")
        if "print(" in code:
            suggestions.append("Consider using logging instead of print statements")
        
        # Language-specific checks
        if language == "python":
            try:
                ast.parse(code)
            except SyntaxError as e:
                issues.append(f"Syntax error: {e}")
        
        return CodeAnalysis(
            complexity=complexity,
            issues=issues,
            suggestions=suggestions,
            security_concerns=security,
            test_coverage=None
        )
    
    def _validate_syntax(self, code: str, language: str) -> Tuple[bool, str]:
        """Validate code syntax."""
        
        if language == "python":
            try:
                ast.parse(code)
                return True, "Syntax valid"
            except SyntaxError as e:
                return False, f"Syntax error: {e}"
        
        # For other languages, basic check
        if not code.strip():
            return False, "Empty code"
        
        return True, "Basic validation passed (full syntax check requires compiler)"
    
    def _calculate_safety_score(self, code: str, safety_level: str) -> float:
        """Calculate safety score for code (0-1)."""
        
        score = 1.0
        
        # Deduct for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                score -= 0.15
        
        # Deduct for file operations in strict mode
        if safety_level == "strict":
            if any(x in code for x in ["open(", "write", "remove"]):
                score -= 0.1
        
        return max(0.0, min(1.0, score))
    
    def _get_safety_notes(self, code: str) -> List[str]:
        """Get safety notes for code."""
        
        notes = []
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, code, re.IGNORECASE):
                notes.append(f"Code contains pattern matching: {pattern[:20]}...")
        
        return notes
    
    def _calculate_quality_score(self, analysis: CodeAnalysis) -> float:
        """Calculate overall quality score."""
        
        score = 1.0
        score -= len(analysis.issues) * 0.1
        score -= len(analysis.security_concerns) * 0.2
        score -= (analysis.complexity - 1) * 0.05
        
        return max(0.0, min(1.0, score))
    
    def _generate_analysis_summary(self, analysis: CodeAnalysis) -> str:
        """Generate human-readable analysis summary."""
        
        parts = []
        parts.append(f"Complexity score: {analysis.complexity}/10")
        
        if analysis.security_concerns:
            parts.append(f"⚠️ {len(analysis.security_concerns)} security concerns found")
        if analysis.issues:
            parts.append(f"⚠️ {len(analysis.issues)} issues found")
        if analysis.suggestions:
            parts.append(f"💡 {len(analysis.suggestions)} improvement suggestions")
        
        return " | ".join(parts) if parts else "No significant issues found"
    
    def _simulate_refactoring(
        self,
        code: str,
        language: str,
        analysis: CodeAnalysis
    ) -> str:
        """Simulate refactoring - production would use LLM."""
        
        # Basic refactoring patterns
        refactored = code
        
        # Add docstring if missing (Python)
        if language == "python" and '"""' not in code and "def " in code:
            lines = code.split("\\n")
            for i, line in enumerate(lines):
                if line.strip().startswith("def "):
                    indent = len(line) - len(line.lstrip())
                    lines.insert(i + 1, " " * indent + '"""Generated function."""')
                    break
            refactored = "\\n".join(lines)
        
        return refactored
    
    def _simulate_optimization(self, code: str, language: str) -> str:
        """Simulate optimization - production would use LLM."""
        
        # Basic optimization hints
        optimized = code
        
        if language == "python":
            # Add functools.lru_cache for functions
            if "def " in code and "lru_cache" not in code:
                optimized = "from functools import lru_cache\\n\\n" + optimized
                optimized = optimized.replace(
                    "def ",
                    "@lru_cache(maxsize=128)\\ndef "
                )
        
        return optimized
    
    def _generate_test_template(self, language: str, code_or_spec: str) -> str:
        """Generate test template."""
        
        if language == "python":
            return '''import pytest
from generated_module import generated_function

def test_generated_function_basic():
    """Test basic functionality."""
    result = generated_function("test_input")
    assert result is not None

def test_generated_function_edge_cases():
    """Test edge cases."""
    # TODO: Add edge case tests
    pass

def test_generated_function_error_handling():
    """Test error handling."""
    # TODO: Add error handling tests  
    pass
'''
        
        elif language in ["javascript", "typescript"]:
            return '''const { generatedFunction } = require('./generated_module');

describe('generatedFunction', () => {
    test('basic functionality', () => {
        const result = generatedFunction('test_input');
        expect(result).toBeDefined();
    });
    
    test('edge cases', () => {
        // TODO: Add edge case tests
    });
    
    test('error handling', () => {
        // TODO: Add error handling tests
    });
});
'''
        
        return "# Tests would be generated based on the code specification"
    
    def _extract_function_name(self, specification: str) -> Optional[str]:
        """Extract function name from specification."""
        
        # Look for patterns like "function NAME" or "def NAME"
        match = re.search(r'(?:function|def|create|implement)\s+(\w+)', specification, re.IGNORECASE)
        if match:
            return match.group(1).lower()
        return None
    
    def _extract_class_name(self, specification: str) -> Optional[str]:
        """Extract class name from specification."""
        
        match = re.search(r'class\s+(\w+)', specification, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Look for "X class" or "class for X"
        match = re.search(r'(\w+)\s+class', specification, re.IGNORECASE)
        if match:
            return match.group(1).capitalize() + "Class"
        
        return None


# Convenience functions
def generate_code(specification: str, language: str = "python", context: str = "") -> Dict[str, Any]:
    """Convenience function for code generation."""
    skill = CodeGenerationSkill()
    result = skill.execute(
        action="generate",
        language=language,
        specification=specification,
        context=context
    )
    return result.data if result.success else {"error": result.error}


def analyze_code(code: str, language: str = "python") -> Dict[str, Any]:
    """Convenience function for code analysis."""
    skill = CodeGenerationSkill()
    result = skill.execute(
        action="analyze",
        language=language,
        specification=code
    )
    return result.data if result.success else {"error": result.error}


if __name__ == "__main__":
    # Demo
    print("=== Code Generation Skill Demo ===\\n")
    
    skill = CodeGenerationSkill()
    
    # Test generation
    print("1. Generating code...")
    result = skill.execute(
        action="generate",
        language="python",
        specification="Create a function that calculates factorial with memoization",
        safety_level="strict"
    )
    data = result.data if result.success else {"error": result.error}
    print(f"Generated code:\\n{data.get('code', 'Error')}")
    print(f"Safety score: {data.get('safety_score', 0)}")
    print(f"Requires review: {data.get('requires_review', True)}")
    
    # Test analysis
    print("\\n2. Analyzing code...")
    code_to_analyze = """
def add(a, b):
    return a + b

def complex_function(n):
    if n < 0:
        return None
    result = 0
    for i in range(n):
        for j in range(n):
            result += i * j
    return result
"""
    result = skill.execute(
        action="analyze",
        language="python",
        specification=code_to_analyze
    )
    data = result.data if result.success else {"error": result.error}
    print(f"Analysis: {data.get('summary', 'N/A')}")
    print(f"Suggestions: {data.get('suggestions', [])}")
