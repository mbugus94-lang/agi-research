"""
Self-analysis and improvement system for AGI agents.
Implements DGM-H (Darwin Gödel Machine Hyperagent) inspired capability
with safety guardrails - analyzes own codebase and proposes specific improvements.

Based on: arXiv:2603.19461 - Hyperagents: Self-Improving AI Systems
Safety: All modifications require human review per arXiv:2601.04234
"""

from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
import os
import ast
import inspect
from pathlib import Path


class ImprovementType(Enum):
    """Types of self-improvements."""
    MISSING_COMPONENT = "missing_component"      # Add new module/file
    ENHANCEMENT = "enhancement"                   # Improve existing code
    REFACTORING = "refactoring"                   # Restructure for clarity
    OPTIMIZATION = "optimization"                 # Performance improvement
    BUG_FIX = "bug_fix"                          # Fix identified issue
    DOCUMENTATION = "documentation"               # Add/improve docs


@dataclass
class CodeIssue:
    """An identified issue or gap in the codebase."""
    file_path: str
    line_number: Optional[int]
    issue_type: str
    description: str
    severity: str  # low, medium, high, critical
    suggested_fix: Optional[str] = None


@dataclass
class ImprovementProposal:
    """A specific, actionable improvement proposal."""
    id: str
    title: str
    improvement_type: ImprovementType
    component: str
    description: str
    rationale: str
    expected_impact: str
    
    # Specific change details
    target_file: Optional[str] = None
    current_code: Optional[str] = None
    proposed_code: Optional[str] = None
    insertion_point: Optional[str] = None  # Function/class name to insert after
    
    # Safety and tracking
    risk_level: str = "NORMAL"  # SAFE, NORMAL, ELEVATED, CRITICAL
    requires_review: bool = True
    status: str = "proposed"  # proposed, under_review, approved, rejected, implemented
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    reviewed_at: Optional[datetime] = None
    reviewer_feedback: Optional[str] = None
    implemented_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "improvement_type": self.improvement_type.value,
            "component": self.component,
            "description": self.description,
            "rationale": self.rationale,
            "expected_impact": self.expected_impact,
            "target_file": self.target_file,
            "current_code": self.current_code,
            "proposed_code": self.proposed_code,
            "insertion_point": self.insertion_point,
            "risk_level": self.risk_level,
            "requires_review": self.requires_review,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "reviewer_feedback": self.reviewer_feedback,
            "implemented_at": self.implemented_at.isoformat() if self.implemented_at else None
        }


class CodebaseAnalyzer:
    """
    Analyzes the agent's own codebase for gaps and improvements.
    """
    
    # Expected architecture components
    EXPECTED_STRUCTURE = {
        "core": ["agent.py", "memory.py", "planner.py", "reflection.py", "self_analysis.py"],
        "skills": ["__init__.py", "web_search.py", "code_generation.py", 
                   "tool_integration.py", "file_operations.py", "tool_registry.py"],
        "experiments": ["test_agent.py", "test_code_generation.py", "test_tool_integration.py",
                        "test_self_analysis.py"]
    }
    
    # Architecture patterns we expect
    ARCHITECTURE_PATTERNS = {
        "SMGI_compliant": [
            "representational maps (tool schemas)",
            "hypothesis spaces (planning strategies)", 
            "evaluators (performance metrics)",
            "memory operators (storage/retrieval)"
        ],
        "safety_patterns": [
            "human_in_the_loop",
            "risk_classification",
            "approval_gates"
        ],
        "test_patterns": [
            "unit_tests",
            "integration_tests"
        ]
    }
    
    def __init__(self, codebase_path: str = "/home/workspace/agi-research"):
        self.codebase_path = Path(codebase_path)
        self.issues: List[CodeIssue] = []
        self.analysis_results: Dict[str, Any] = {}
    
    def analyze_structure(self) -> Dict[str, Any]:
        """Analyze codebase structure against expected architecture."""
        results = {
            "missing_files": [],
            "present_files": [],
            "coverage_percentage": 0.0,
            "issues": []
        }
        
        total_expected = 0
        total_present = 0
        
        for directory, expected_files in self.EXPECTED_STRUCTURE.items():
            dir_path = self.codebase_path / directory
            
            for filename in expected_files:
                total_expected += 1
                file_path = dir_path / filename
                
                if file_path.exists():
                    total_present += 1
                    results["present_files"].append(str(file_path.relative_to(self.codebase_path)))
                else:
                    results["missing_files"].append(str(file_path.relative_to(self.codebase_path)))
                    self.issues.append(CodeIssue(
                        file_path=str(file_path),
                        line_number=None,
                        issue_type="missing_component",
                        description=f"Expected file {filename} not found in {directory}",
                        severity="medium"
                    ))
        
        results["coverage_percentage"] = (total_present / total_expected * 100) if total_expected > 0 else 0
        results["issues"] = [self._issue_to_dict(i) for i in self.issues]
        
        self.analysis_results["structure"] = results
        return results
    
    def analyze_code_quality(self, file_path: str) -> Dict[str, Any]:
        """Analyze a specific file for code quality issues."""
        full_path = self.codebase_path / file_path
        
        if not full_path.exists():
            return {"error": "File not found"}
        
        try:
            with open(full_path, 'r') as f:
                content = f.read()
            
            # Try to parse as Python
            try:
                tree = ast.parse(content)
                
                # Count various elements
                functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
                classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
                imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
                
                # Check for docstrings
                missing_docstrings = []
                for func in functions:
                    if not ast.get_docstring(func):
                        missing_docstrings.append(func.name)
                
                for cls in classes:
                    if not ast.get_docstring(cls):
                        missing_docstrings.append(cls.name)
                
                return {
                    "file": file_path,
                    "lines": len(content.split('\n')),
                    "functions": len(functions),
                    "classes": len(classes),
                    "imports": len(imports),
                    "missing_docstrings": missing_docstrings,
                    "has_main_block": "if __name__ == \"__main__\"" in content,
                    "quality_score": self._calculate_quality_score(
                        len(functions), len(classes), missing_docstrings, content
                    )
                }
            
            except SyntaxError as e:
                return {
                    "file": file_path,
                    "error": f"Syntax error: {e}"
                }
        
        except Exception as e:
            return {"file": file_path, "error": str(e)}
    
    def _calculate_quality_score(self, functions: int, classes: int, 
                                  missing_docs: List[str], content: str) -> float:
        """Calculate a simple quality score (0-100)."""
        score = 50.0  # Base score
        
        # Bonus for having content
        if functions > 0 or classes > 0:
            score += 20
        
        # Penalty for missing docstrings
        total_items = functions + classes
        if total_items > 0:
            doc_coverage = (total_items - len(missing_docs)) / total_items
            score += 30 * doc_coverage
        
        # Bonus for having __main__ block (test/demo capability)
        if "if __name__ == \"__main__\"" in content:
            score += 10
        
        return min(100, max(0, score))
    
    def identify_improvement_opportunities(self) -> List[Dict[str, Any]]:
        """Identify specific improvement opportunities."""
        opportunities = []
        
        # Check for missing test coverage
        core_files = self.EXPECTED_STRUCTURE.get("core", [])
        test_files = self.EXPECTED_STRUCTURE.get("experiments", [])
        
        for core_file in core_files:
            base_name = core_file.replace(".py", "")
            expected_test = f"test_{base_name}.py"
            
            if expected_test not in test_files:
                opportunities.append({
                    "type": "missing_test",
                    "priority": "high",
                    "component": base_name,
                    "description": f"No test file found for {core_file}",
                    "target_file": f"experiments/test_{base_name}.py",
                    "suggested_action": f"Create test_{base_name}.py with unit tests"
                })
        
        # Check for vector/semantic memory (common gap)
        memory_file = self.codebase_path / "core" / "memory.py"
        if memory_file.exists():
            with open(memory_file, 'r') as f:
                content = f.read()
            
            if "embedding" not in content.lower() or "vector" not in content.lower():
                opportunities.append({
                    "type": "enhancement",
                    "priority": "high",
                    "component": "memory",
                    "description": "Memory system lacks vector/semantic search capability",
                    "target_file": "core/memory.py",
                    "suggested_action": "Add VectorMemory class with embedding-based search"
                })
        
        # Check for async/parallel execution support
        agent_file = self.codebase_path / "core" / "agent.py"
        if agent_file.exists():
            with open(agent_file, 'r') as f:
                content = f.read()
            
            if "async" not in content and "await" not in content:
                opportunities.append({
                    "type": "enhancement",
                    "priority": "medium",
                    "component": "agent",
                    "description": "Agent lacks async/parallel execution support",
                    "target_file": "core/agent.py",
                    "suggested_action": "Add async support for concurrent tool execution"
                })
        
        return opportunities
    
    def _issue_to_dict(self, issue: CodeIssue) -> Dict:
        """Convert CodeIssue to dict."""
        return {
            "file_path": issue.file_path,
            "line_number": issue.line_number,
            "issue_type": issue.issue_type,
            "description": issue.description,
            "severity": issue.severity,
            "suggested_fix": issue.suggested_fix
        }


class SelfImprovementEngine:
    """
    Generates and manages specific, actionable improvement proposals.
    Inspired by DGM-H: meta-agent modifies task-agent with safety constraints.
    """
    
    def __init__(self, codebase_path: str = "/home/workspace/agi-research",
                 storage_path: Optional[str] = None):
        self.codebase_path = Path(codebase_path)
        self.storage_path = storage_path
        self.analyzer = CodebaseAnalyzer(codebase_path)
        self.proposals: List[ImprovementProposal] = []
        self._load()
    
    def run_full_analysis(self) -> Dict[str, Any]:
        """Run comprehensive self-analysis."""
        print("🔍 Running self-analysis...")
        
        # Analyze structure
        structure = self.analyzer.analyze_structure()
        
        # Analyze each core file
        core_quality = {}
        for filename in self.analyzer.EXPECTED_STRUCTURE.get("core", []):
            quality = self.analyzer.analyze_code_quality(f"core/{filename}")
            core_quality[filename] = quality
        
        # Identify opportunities
        opportunities = self.analyzer.identify_improvement_opportunities()
        
        # Generate proposals from opportunities
        for opp in opportunities:
            self._generate_proposal_from_opportunity(opp)
        
        results = {
            "structure_coverage": structure.get("coverage_percentage", 0),
            "core_quality": core_quality,
            "opportunities": opportunities,
            "proposals_generated": len(self.proposals),
            "pending_review": len([p for p in self.proposals if p.status == "proposed"])
        }
        
        print(f"✅ Analysis complete: {results['proposals_generated']} proposals generated")
        print(f"⚠️  {results['pending_review']} proposals awaiting review")
        
        return results
    
    def _generate_proposal_from_opportunity(self, opp: Dict[str, Any]):
        """Generate a detailed proposal from an opportunity."""
        proposal_id = f"{opp['component']}_{len(self.proposals):03d}"
        
        # Map opportunity type to improvement type
        type_mapping = {
            "missing_test": ImprovementType.MISSING_COMPONENT,
            "enhancement": ImprovementType.ENHANCEMENT,
            "refactoring": ImprovementType.REFACTORING,
            "missing_component": ImprovementType.MISSING_COMPONENT
        }
        
        improvement_type = type_mapping.get(opp["type"], ImprovementType.ENHANCEMENT)
        
        # Generate specific code based on type
        proposed_code = self._generate_proposed_code(opp)
        
        proposal = ImprovementProposal(
            id=proposal_id,
            title=opp["description"],
            improvement_type=improvement_type,
            component=opp["component"],
            description=opp["description"],
            rationale=f"Identified gap: {opp['description']}. Priority: {opp['priority']}",
            expected_impact=f"Will improve {opp['component']} capability and system robustness",
            target_file=opp.get("target_file"),
            proposed_code=proposed_code,
            risk_level="NORMAL" if opp["priority"] != "critical" else "ELEVATED",
            requires_review=True  # Safety: all self-modifications require review
        )
        
        self.proposals.append(proposal)
        self._save()
    
    def _generate_proposed_code(self, opp: Dict[str, Any]) -> Optional[str]:
        """Generate proposed code based on opportunity type."""
        component = opp["component"]
        
        if opp["type"] == "missing_test":
            return self._generate_test_template(component)
        
        if opp["type"] == "enhancement" and "vector" in opp["description"].lower():
            return self._generate_vector_memory_template()
        
        if opp["type"] == "enhancement" and "async" in opp["description"].lower():
            return self._generate_async_template()
        
        return None
    
    def _generate_test_template(self, component: str) -> str:
        """Generate a test file template."""
        return f'''"""
Tests for {component} module.
Generated by self-analysis system.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.{component} import *


def test_{component}_basic():
    """Basic functionality test."""
    # TODO: Implement test
    assert True


def test_{component}_integration():
    """Integration test with other components."""
    # TODO: Implement test
    assert True


if __name__ == "__main__":
    test_{component}_basic()
    test_{component}_integration()
    print("✅ All {component} tests passed")
'''
    
    def _generate_vector_memory_template(self) -> str:
        """Generate VectorMemory class template."""
        return '''
class VectorMemory:
    """
    Vector-based semantic memory using embeddings.
    Enables similarity search across memory entries.
    """
    
    def __init__(self, dimension: int = 768, storage_path: str = None):
        self.dimension = dimension
        self.storage_path = storage_path
        self.entries: List[MemoryEntry] = []
        # TODO: Add embedding model integration
    
    def add(self, content: str, metadata: Dict = None) -> MemoryEntry:
        """Add entry with embedding."""
        # TODO: Generate embedding
        entry = MemoryEntry(
            content=content,
            memory_type="semantic",
            metadata=metadata or {}
        )
        self.entries.append(entry)
        return entry
    
    def search(self, query: str, top_k: int = 5) -> List[MemoryEntry]:
        """Semantic search using embeddings."""
        # TODO: Implement similarity search
        return self.entries[:top_k]
'''
    
    def _generate_async_template(self) -> str:
        """Generate async support template."""
        return '''
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def execute_tools_async(self, tools: List[Tool], inputs: List[Dict]) -> List[Observation]:
    """Execute multiple tools concurrently."""
    with ThreadPoolExecutor(max_workers=4) as executor:
        loop = asyncio.get_event_loop()
        futures = [
            loop.run_in_executor(executor, tool.execute, **inp)
            for tool, inp in zip(tools, inputs)
        ]
        return await asyncio.gather(*futures)
'''
    
    def get_pending_proposals(self) -> List[ImprovementProposal]:
        """Get all proposals awaiting review."""
        return [p for p in self.proposals if p.status == "proposed"]
    
    def review_proposal(self, proposal_id: str, approved: bool, 
                        feedback: str = "") -> Optional[ImprovementProposal]:
        """
        Review a proposed change. 
        
        SAFETY: This requires human review. Never auto-approve.
        """
        for proposal in self.proposals:
            if proposal.id == proposal_id:
                proposal.status = "approved" if approved else "rejected"
                proposal.reviewer_feedback = feedback
                proposal.reviewed_at = datetime.now()
                self._save()
                return proposal
        return None
    
    def implement_proposal(self, proposal_id: str) -> Dict[str, Any]:
        """
        Implement an approved proposal.
        
        SAFETY: Only implements if status is "approved"
        """
        for proposal in self.proposals:
            if proposal.id == proposal_id:
                if proposal.status != "approved":
                    return {
                        "success": False,
                        "error": f"Proposal {proposal_id} not approved (status: {proposal.status})"
                    }
                
                if not proposal.target_file or not proposal.proposed_code:
                    return {
                        "success": False,
                        "error": "Proposal missing target_file or proposed_code"
                    }
                
                try:
                    target_path = self.codebase_path / proposal.target_file
                    
                    # If file doesn't exist, create it
                    if not target_path.exists():
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(target_path, 'w') as f:
                            f.write(proposal.proposed_code)
                    else:
                        # Append to existing file
                        with open(target_path, 'a') as f:
                            f.write("\n\n" + proposal.proposed_code)
                    
                    proposal.status = "implemented"
                    proposal.implemented_at = datetime.now()
                    self._save()
                    
                    return {
                        "success": True,
                        "file": str(target_path),
                        "message": f"Successfully implemented {proposal_id}"
                    }
                
                except Exception as e:
                    return {
                        "success": False,
                        "error": str(e)
                    }
        
        return {"success": False, "error": f"Proposal {proposal_id} not found"}
    
    def get_summary(self) -> str:
        """Get human-readable summary of all proposals."""
        lines = ["=== Self-Analysis Summary ===\n"]
        
        # Analysis results
        if hasattr(self.analyzer, 'analysis_results'):
            structure = self.analyzer.analysis_results.get("structure", {})
            lines.append(f"Structure Coverage: {structure.get('coverage_percentage', 0):.1f}%")
            lines.append(f"Issues Found: {len(structure.get('issues', []))}")
        
        lines.append(f"\nTotal Proposals: {len(self.proposals)}")
        
        # By status
        by_status = {}
        for p in self.proposals:
            by_status.setdefault(p.status, []).append(p)
        
        for status, props in by_status.items():
            lines.append(f"\n{status.upper()} ({len(props)}):")
            for p in props[:5]:  # Show first 5
                lines.append(f"  • [{p.id}] {p.component}: {p.title[:50]}...")
            if len(props) > 5:
                lines.append(f"  ... and {len(props) - 5} more")
        
        # Pending review warning
        pending = self.get_pending_proposals()
        if pending:
            lines.append(f"\n⚠️  {len(pending)} proposals awaiting human review")
            lines.append("   Safety: Review before implementing any changes")
        
        return "\n".join(lines)
    
    def _load(self):
        """Load proposals from storage."""
        if not self.storage_path:
            return
        
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                for p_data in data.get("proposals", []):
                    proposal = ImprovementProposal(
                        id=p_data["id"],
                        title=p_data["title"],
                        improvement_type=ImprovementType(p_data["improvement_type"]),
                        component=p_data["component"],
                        description=p_data["description"],
                        rationale=p_data["rationale"],
                        expected_impact=p_data["expected_impact"],
                        target_file=p_data.get("target_file"),
                        proposed_code=p_data.get("proposed_code"),
                        risk_level=p_data.get("risk_level", "NORMAL"),
                        status=p_data.get("status", "proposed"),
                        created_at=datetime.fromisoformat(p_data["created_at"])
                    )
                    self.proposals.append(proposal)
        except FileNotFoundError:
            pass
    
    def _save(self):
        """Save proposals to storage."""
        if not self.storage_path:
            return
        
        with open(self.storage_path, 'w') as f:
            json.dump({
                "proposals": [p.to_dict() for p in self.proposals]
            }, f, indent=2)


if __name__ == "__main__":
    # Demo self-analysis
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = SelfImprovementEngine(
            codebase_path="/home/workspace/agi-research",
            storage_path=f"{tmpdir}/proposals.json"
        )
        
        # Run analysis
        results = engine.run_full_analysis()
        
        print("\n" + engine.get_summary())
        
        # Show pending proposals
        pending = engine.get_pending_proposals()
        if pending:
            print("\n=== Pending Proposals ===")
            for p in pending[:3]:
                print(f"\n📝 {p.id} ({p.improvement_type.value})")
                print(f"   Component: {p.component}")
                print(f"   Description: {p.description}")
                print(f"   Target: {p.target_file}")
                if p.proposed_code:
                    print(f"   Code preview: {p.proposed_code[:100]}...")
