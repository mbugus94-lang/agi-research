"""
Code Generation Skill

Provides AGI agent with code generation and manipulation capabilities.
Critical for self-modification (with safety checks).
"""

import json
import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class CodeAction(Enum):
    GENERATE = "generate"
    MODIFY = "modify"
    REVIEW = "review"
    TEST = "test"


@dataclass
class CodeResult:
    code: str
    language: str
    explanation: str
    tests: Optional[str] = None
    file_path: Optional[str] = None
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "code": self.code,
            "language": self.language,
            "explanation": self.explanation,
            "tests": self.tests,
            "file_path": self.file_path,
            "timestamp": self.timestamp
        }


class CodeGenSkill:
    """
    Code generation and manipulation skill.
    
    SAFETY: All self-modification proposals require review.
    Critical files are protected from automatic modification.
    """
    
    CRITICAL_FILES = [
        "agent.py",      # Core agent identity
        "memory.py",     # Memory system
        "reflection.py", # Safety/oversight
        "constitution.py"  # Governance (if exists)
    ]
    
    def __init__(self, safe_mode: bool = True):
        self.safe_mode = safe_mode
        self.generation_history: List[Dict] = []
    
    def generate(self, 
                 description: str,
                 language: str = "python",
                 include_tests: bool = True,
                 context: Optional[Dict] = None) -> CodeResult:
        """
        Generate code from natural language description.
        
        Returns structured code with explanation.
        """
        # In production, calls LLM for code generation
        # For now, returns scaffold/template
        
        if language == "python":
            code = self._generate_python_scaffold(description, context)
            tests = self._generate_python_tests(description) if include_tests else None
        else:
            code = f"# TODO: Implement {description}\n# Language: {language}"
            tests = None
        
        result = CodeResult(
            code=code,
            language=language,
            explanation=f"Generated code for: {description}",
            tests=tests
        )
        
        self.generation_history.append({
            "action": "generate",
            "description": description,
            "language": language,
            "timestamp": datetime.now().isoformat()
        })
        
        return result
    
    def modify(self,
               file_path: str,
               modification: str,
               reason: str,
               context: Optional[Dict] = None) -> Dict:
        """
        Propose a code modification.
        
        SAFETY: Checks if file is critical before allowing.
        Returns proposal that requires review if critical.
        """
        # Check if critical
        is_critical = any(cf in file_path for cf in self.CRITICAL_FILES)
        
        if is_critical and self.safe_mode:
            return {
                "success": False,
                "requires_review": True,
                "reason": f"File '{file_path}' is CRITICAL. Self-modification requires review.",
                "proposal": {
                    "file_path": file_path,
                    "modification": modification,
                    "reason": reason
                },
                "safety_level": "critical"
            }
        
        # In production, would apply diff
        return {
            "success": True,
            "file_path": file_path,
            "modification": modification,
            "applied": False,  # Requires explicit apply
            "reason": reason
        }
    
    def review_code(self, 
                    code: str,
                    language: str = "python",
                    review_type: str = "general") -> Dict:
        """
        Review code for issues.
        
        Review types: general, security, performance, style
        """
        issues = []
        
        if review_type == "security":
            issues = self._security_review(code, language)
        elif review_type == "performance":
            issues = self._performance_review(code, language)
        elif review_type == "style":
            issues = self._style_review(code, language)
        else:
            issues = self._general_review(code, language)
        
        return {
            "code_length": len(code),
            "language": language,
            "review_type": review_type,
            "issues_found": len(issues),
            "issues": issues,
            "passed": len(issues) == 0
        }
    
    def _security_review(self, code: str, language: str) -> List[Dict]:
        """Security-focused code review"""
        issues = []
        
        if language == "python":
            # Check for dangerous patterns
            dangerous = ["eval(", "exec(", "__import__", "subprocess.call", "os.system"]
            for pattern in dangerous:
                if pattern in code:
                    issues.append({
                        "severity": "high",
                        "pattern": pattern,
                        "message": f"Potentially dangerous pattern found: {pattern}",
                        "line": self._find_line(code, pattern)
                    })
            
            # Check for hardcoded secrets
            secret_patterns = ["password", "api_key", "secret", "token"]
            for pattern in secret_patterns:
                if re.search(rf'{pattern}\s*=\s*["\'][^"\']+["\']', code, re.IGNORECASE):
                    issues.append({
                        "severity": "medium",
                        "pattern": pattern,
                        "message": f"Potential hardcoded secret: {pattern}",
                        "line": self._find_line(code, pattern)
                    })
        
        return issues
    
    def _performance_review(self, code: str, language: str) -> List[Dict]:
        """Performance-focused code review"""
        issues = []
        
        if language == "python":
            # Check for inefficient patterns
            if "for.*in.*range.*len" in code:
                issues.append({
                    "severity": "low",
                    "message": "Consider using enumerate() instead of range(len())",
                    "type": "optimization"
                })
        
        return issues
    
    def _style_review(self, code: str, language: str) -> List[Dict]:
        """Style-focused code review"""
        issues = []
        
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            if len(line) > 100:
                issues.append({
                    "severity": "low",
                    "line": i,
                    "message": "Line exceeds 100 characters",
                    "type": "style"
                })
        
        return issues
    
    def _general_review(self, code: str, language: str) -> List[Dict]:
        """General code review combining all aspects"""
        security = self._security_review(code, language)
        performance = self._performance_review(code, language)
        style = self._style_review(code, language)
        
        return security + performance + style
    
    def _find_line(self, code: str, pattern: str) -> Optional[int]:
        """Find line number containing pattern"""
        lines = code.split('\n')
        for i, line in enumerate(lines, 1):
            if pattern in line:
                return i
        return None
    
    def _generate_python_scaffold(self, description: str, context: Optional[Dict]) -> str:
        """Generate Python code scaffold"""
        return f'''"""
{description}

Generated by AGI agent code generation skill.
"""

def main():
    """Main function"""
    # TODO: Implement based on: {description}
    pass

if __name__ == "__main__":
    main()
'''
    
    def _generate_python_tests(self, description: str) -> str:
        """Generate Python test scaffold"""
        return f'''"""
Tests for: {description}
"""

import pytest

def test_main():
    """Basic test"""
    assert True  # TODO: Add real tests

if __name__ == "__main__":
    pytest.main([__file__])
'''
    
    def get_modification_proposals(self) -> List[Dict]:
        """Get all pending modification proposals"""
        return [h for h in self.generation_history 
                if h.get("action") == "propose_modify"]


# Skill function interfaces
def generate_code(description: str, **kwargs) -> Dict:
    """Agent-callable code generation"""
    skill = CodeGenSkill()
    result = skill.generate(description, **kwargs)
    return result.to_dict()


def propose_modification(file_path: str, modification: str, 
                        reason: str, **kwargs) -> Dict:
    """Agent-callable modification proposal"""
    skill = CodeGenSkill()
    return skill.modify(file_path, modification, reason, **kwargs)


def review_code(code: str, **kwargs) -> Dict:
    """Agent-callable code review"""
    skill = CodeGenSkill()
    return skill.review_code(code, **kwargs)


if __name__ == "__main__":
    # Test the skill
    skill = CodeGenSkill()
    
    # Generate code
    print("=== Generate Code ===")
    result = skill.generate("A function to calculate fibonacci numbers", 
                           include_tests=True)
    print(f"Language: {result.language}")
    print(f"Code:\n{result.code}")
    print(f"Tests:\n{result.tests}")
    
    # Review code
    print("\n=== Code Review ===")
    review = skill.review_code(result.code, review_type="security")
    print(f"Issues found: {review['issues_found']}")
    for issue in review['issues']:
        print(f"  [{issue['severity']}] {issue['message']}")
    
    # Try to modify critical file
    print("\n=== Critical File Modification (Should Fail) ===")
    mod = skill.modify("core/agent.py", "# Test", "Testing safety")
    print(f"Allowed: {mod['success']}")
    print(f"Requires review: {mod.get('requires_review', False)}")
    print(f"Reason: {mod.get('reason', 'N/A')}")
