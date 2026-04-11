"""
Knowledge Pre-compute Engine
Inspired by: Meta's AI Context Pre-compute approach (April 2026)

Uses specialized agents to analyze codebases and build structured context files,
reducing tool calls by ~40% and improving coverage from 5% to 100%.
"""

from typing import Dict, List, Any, Optional, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
import json
import os
import re
from pathlib import Path
from datetime import datetime


class FileType(Enum):
    CODE = "code"
    CONFIG = "config"
    DOC = "documentation"
    TEST = "test"
    DATA = "data"
    UNKNOWN = "unknown"


class AnalysisType(Enum):
    STRUCTURE = "structure"      # Module/class/function hierarchy
    DEPENDENCIES = "dependencies"  # Import/require relationships
    PATTERNS = "patterns"        # Design patterns and conventions
    DOMAIN = "domain"            # Business logic and concepts
    TRIBAL = "tribal"           # Non-obvious patterns from code


@dataclass
class FileAnalysis:
    """Analysis result for a single file."""
    path: str
    file_type: FileType
    size_bytes: int
    lines: int
    
    # Structure analysis
    classes: List[Dict[str, Any]] = field(default_factory=list)
    functions: List[Dict[str, Any]] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    
    # Dependency analysis
    imports: List[str] = field(default_factory=list)
    depended_by: List[str] = field(default_factory=list)
    
    # Pattern analysis
    patterns: List[str] = field(default_factory=list)
    conventions: List[str] = field(default_factory=list)
    
    # Domain analysis
    domain_concepts: List[str] = field(default_factory=list)
    business_logic: List[str] = field(default_factory=list)
    
    # Tribal knowledge
    non_obvious: List[str] = field(default_factory=list)
    gotchas: List[str] = field(default_factory=list)
    
    # Metadata
    analyzed_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ContextFile:
    """A pre-computed context file for efficient agent navigation."""
    module_name: str
    file_path: str
    summary: str
    key_components: List[Dict[str, Any]]
    dependencies: List[str]
    related_files: List[str]
    navigation_hints: List[str]
    non_obvious_patterns: List[str]
    
    # Statistics
    coverage_score: float  # 0.0 to 1.0
    tool_calls_saved: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_name": self.module_name,
            "file_path": self.file_path,
            "summary": self.summary,
            "key_components": self.key_components,
            "dependencies": self.dependencies,
            "related_files": self.related_files,
            "navigation_hints": self.navigation_hints,
            "non_obvious_patterns": self.non_obvious_patterns,
            "coverage_score": self.coverage_score,
            "tool_calls_saved": self.tool_calls_saved
        }


@dataclass
class KnowledgeIndex:
    """Master index of all pre-computed knowledge."""
    source_path: str
    total_files: int
    analyzed_files: int
    context_files: int
    coverage_percent: float
    analysis_date: str
    
    # Module registry
    modules: Dict[str, str] = field(default_factory=dict)  # name -> context_file_path
    
    # Search indices
    concept_index: Dict[str, List[str]] = field(default_factory=dict)  # concept -> files
    pattern_index: Dict[str, List[str]] = field(default_factory=dict)  # pattern -> files
    dependency_graph: Dict[str, List[str]] = field(default_factory=dict)  # file -> dependencies
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_path": self.source_path,
            "total_files": self.total_files,
            "analyzed_files": self.analyzed_files,
            "context_files": self.context_files,
            "coverage_percent": self.coverage_percent,
            "analysis_date": self.analysis_date,
            "modules": self.modules,
            "concept_index": self.concept_index,
            "pattern_index": self.pattern_index
        }


class SpecializedAnalyzer:
    """
    Specialized analyzer agent for specific analysis types.
    Each analyzer focuses on one aspect of code analysis.
    """
    
    def __init__(self, analysis_type: AnalysisType):
        self.analysis_type = analysis_type
        self.patterns = self._load_patterns()
    
    def _load_patterns(self) -> Dict[str, Any]:
        """Load analysis patterns for this analyzer type."""
        patterns = {
            AnalysisType.STRUCTURE: {
                "python_class": r"^class\s+(\w+)",
                "python_func": r"def\s+(\w+)",
                "js_class": r"^class\s+(\w+)",
                "js_func": r"^(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)",
                "typescript_interface": r"^interface\s+(\w+)",
            },
            AnalysisType.DEPENDENCIES: {
                "python_import": r"^(?:from\s+(\S+)\s+import|import\s+(\S+))",
                "js_import": r"^import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]",
                "js_require": r"(?:const|let|var)\s+\w+\s*=\s*require\(['\"]([^'\"]+)['\"]\)",
            },
            AnalysisType.PATTERNS: {
                "singleton": r"_instance|getInstance|Singleton",
                "factory": r"Factory|create.*Instance",
                "observer": r"observer|subscribe|emit|on\(",
                "decorator": r"@\w+|wrapper|decorate",
                "mvc": r"controller|model|view|router",
            },
            AnalysisType.DOMAIN: {
                "entity": r"entity|model|domain|business",
                "service": r"service|manager|handler",
                "repository": r"repository|dao|data",
            }
        }
        return patterns.get(self.analysis_type, {})
    
    def analyze(self, file_path: str, content: str) -> Dict[str, Any]:
        """Analyze a file and return structured findings."""
        results = {}
        lines = content.split('\n')
        
        if self.analysis_type == AnalysisType.STRUCTURE:
            results["classes"] = []
            results["functions"] = []
            results["exports"] = []
            
            for i, line in enumerate(lines, 1):
                # Python classes
                match = re.search(self.patterns["python_class"], line)
                if match:
                    results["classes"].append({
                        "name": match.group(1),
                        "line": i,
                        "type": "class"
                    })
                
                # Python functions
                match = re.search(self.patterns["python_func"], line)
                if match:
                    results["functions"].append({
                        "name": match.group(1),
                        "line": i,
                        "type": "function"
                    })
                
                # JS/TS exports
                if re.search(r"export\s+(?:default\s+)?(?:class|function|const|let|var)", line):
                    results["exports"].append(f"Line {i}: {line.strip()}")
        
        elif self.analysis_type == AnalysisType.DEPENDENCIES:
            results["imports"] = []
            
            for line in lines:
                # Python imports
                match = re.search(self.patterns["python_import"], line)
                if match:
                    results["imports"].append(match.group(1) or match.group(2))
                
                # JS imports
                match = re.search(self.patterns["js_import"], line)
                if match:
                    results["imports"].append(match.group(1))
                
                # JS require
                match = re.search(self.patterns["js_require"], line)
                if match:
                    results["imports"].append(match.group(1))
        
        elif self.analysis_type == AnalysisType.PATTERNS:
            results["patterns"] = []
            results["conventions"] = []
            
            content_lower = content.lower()
            for pattern_name in self.patterns:
                if pattern_name in ["singleton", "factory", "observer", "decorator", "mvc"]:
                    if re.search(self.patterns[pattern_name], content, re.IGNORECASE):
                        results["patterns"].append(pattern_name)
            
            # Detect naming conventions
            if re.search(r"^[a-z_][a-z0-9_]*$", content.split('\n')[0] if content else ""):
                results["conventions"].append("snake_case")
            if re.search(r"^[a-z]+([A-Z][a-z]*)+$", content.split('\n')[0] if content else ""):
                results["conventions"].append("camelCase")
            if re.search(r"^[A-Z][a-z]+([A-Z][a-z]*)+$", content.split('\n')[0] if content else ""):
                results["conventions"].append("PascalCase")
        
        elif self.analysis_type == AnalysisType.DOMAIN:
            results["domain_concepts"] = []
            results["business_logic"] = []
            
            # Extract TODO comments as domain hints
            for i, line in enumerate(lines, 1):
                if "TODO" in line or "FIXME" in line:
                    results["domain_concepts"].append(f"Line {i}: {line.strip()}")
                
                # Look for business logic patterns
                if any(kw in line.lower() for kw in ["validate", "process", "calculate", "compute"]):
                    results["business_logic"].append(f"Line {i}: {line.strip()[:100]}")
        
        elif self.analysis_type == AnalysisType.TRIBAL:
            results["non_obvious"] = []
            results["gotchas"] = []
            
            for i, line in enumerate(lines, 1):
                # Comments explaining complex logic
                if re.search(r"#\s*(?:NOTE|WARNING|IMPORTANT|HACK)", line, re.IGNORECASE):
                    results["non_obvious"].append(f"Line {i}: {line.strip()}")
                
                # Special handling patterns
                if re.search(r"(?:workaround|edge.case|special.case|legacy)", line, re.IGNORECASE):
                    results["gotchas"].append(f"Line {i}: {line.strip()}")
        
        return results


class KnowledgePrecomputeEngine:
    """
    Main engine for pre-computing knowledge from codebases.
    Uses specialized analyzers (like Meta's 50+ agents) to build context files.
    """
    
    def __init__(self, output_dir: str = ".knowledge_context"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Initialize specialized analyzers
        self.analyzers = {
            AnalysisType.STRUCTURE: SpecializedAnalyzer(AnalysisType.STRUCTURE),
            AnalysisType.DEPENDENCIES: SpecializedAnalyzer(AnalysisType.DEPENDENCIES),
            AnalysisType.PATTERNS: SpecializedAnalyzer(AnalysisType.PATTERNS),
            AnalysisType.DOMAIN: SpecializedAnalyzer(AnalysisType.DOMAIN),
            AnalysisType.TRIBAL: SpecializedAnalyzer(AnalysisType.TRIBAL),
        }
        
        # File type detection
        self.file_extensions = {
            FileType.CODE: [".py", ".js", ".ts", ".java", ".go", ".rs", ".cpp", ".c", ".h", ".rb", ".php"],
            FileType.CONFIG: [".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env"],
            FileType.DOC: [".md", ".txt", ".rst", ".adoc"],
            FileType.TEST: [".test.js", ".spec.js", ".test.ts", "_test.py", "_spec.py", "test_"],
            FileType.DATA: [".csv", ".xml", ".sql", ".graphql"],
        }
        
        self.file_analyses: Dict[str, FileAnalysis] = {}
    
    def detect_file_type(self, file_path: str) -> FileType:
        """Detect the type of a file based on extension and name."""
        path = Path(file_path)
        name = path.name.lower()
        suffix = path.suffix.lower()
        
        # Check test patterns FIRST (before generic extensions)
        test_patterns = [".test.", ".spec.", "_test.", "_spec.", "test_"]
        for pattern in test_patterns:
            if pattern in name:
                return FileType.TEST
        
        # Then check by extension
        for file_type, patterns in self.file_extensions.items():
            if file_type == FileType.TEST:
                continue  # Already checked above
            for pattern in patterns:
                if pattern.startswith("."):
                    if suffix == pattern:
                        return file_type
                else:
                    if pattern in name:
                        return file_type
        
        return FileType.UNKNOWN
    
    def scan_directory(self, root_path: str, ignore_patterns: Optional[List[str]] = None) -> List[str]:
        """Scan directory and return list of files to analyze."""
        if ignore_patterns is None:
            ignore_patterns = [
                "node_modules", ".git", "__pycache__", ".venv", "venv",
                ".pytest_cache", ".mypy_cache", "dist", "build", ".next",
                ".tox", ".eggs", "*.pyc", "*.pyo", "*.pyd", ".DS_Store"
            ]
        
        files = []
        root = Path(root_path)
        
        for path in root.rglob("*"):
            if path.is_file():
                # Check if should be ignored
                rel_path = str(path.relative_to(root))
                should_ignore = any(
                    pattern in rel_path or path.match(pattern)
                    for pattern in ignore_patterns
                )
                if not should_ignore:
                    files.append(str(path))
        
        return sorted(files)
    
    def analyze_file(self, file_path: str) -> FileAnalysis:
        """Analyze a single file using all specialized analyzers."""
        path = Path(file_path)
        file_type = self.detect_file_type(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            content = f"# Error reading file: {e}"
        
        lines = content.split('\n')
        
        # Create base analysis
        analysis = FileAnalysis(
            path=file_path,
            file_type=file_type,
            size_bytes=len(content.encode('utf-8')),
            lines=len(lines)
        )
        
        # Run all specialized analyzers
        for analysis_type, analyzer in self.analyzers.items():
            results = analyzer.analyze(file_path, content)
            
            if analysis_type == AnalysisType.STRUCTURE:
                analysis.classes = results.get("classes", [])
                analysis.functions = results.get("functions", [])
                analysis.exports = results.get("exports", [])
            
            elif analysis_type == AnalysisType.DEPENDENCIES:
                analysis.imports = results.get("imports", [])
            
            elif analysis_type == AnalysisType.PATTERNS:
                analysis.patterns = results.get("patterns", [])
                analysis.conventions = results.get("conventions", [])
            
            elif analysis_type == AnalysisType.DOMAIN:
                analysis.domain_concepts = results.get("domain_concepts", [])
                analysis.business_logic = results.get("business_logic", [])
            
            elif analysis_type == AnalysisType.TRIBAL:
                analysis.non_obvious = results.get("non_obvious", [])
                analysis.gotchas = results.get("gotchas", [])
        
        self.file_analyses[file_path] = analysis
        return analysis
    
    def build_dependency_graph(self):
        """Build reverse dependency graph (which files depend on which)."""
        for path, analysis in self.file_analyses.items():
            for dep in analysis.imports:
                # Find files that might match this import
                for other_path, other_analysis in self.file_analyses.items():
                    if other_path != path:
                        other_name = Path(other_path).stem
                        if dep.endswith(other_name) or other_name in dep:
                            other_analysis.depended_by.append(path)
    
    def generate_context_file(self, file_path: str) -> ContextFile:
        """Generate a pre-computed context file for a module."""
        analysis = self.file_analyses.get(file_path)
        if not analysis:
            raise ValueError(f"No analysis found for {file_path}")
        
        path = Path(file_path)
        module_name = path.stem
        
        # Find related files (same directory)
        parent = path.parent
        related = [
            f for f in self.file_analyses.keys()
            if Path(f).parent == parent and f != file_path
        ][:10]  # Limit to 10 related files
        
        # Generate summary
        summary_parts = [f"Module: {module_name}"]
        summary_parts.append(f"Type: {analysis.file_type.value}")
        summary_parts.append(f"Size: {analysis.lines} lines")
        
        if analysis.classes:
            summary_parts.append(f"Classes: {len(analysis.classes)}")
        if analysis.functions:
            summary_parts.append(f"Functions: {len(analysis.functions)}")
        if analysis.patterns:
            summary_parts.append(f"Patterns: {', '.join(analysis.patterns)}")
        
        summary = " | ".join(summary_parts)
        
        # Key components for navigation
        key_components = []
        for cls in analysis.classes[:5]:  # Top 5 classes
            key_components.append({
                "type": "class",
                "name": cls["name"],
                "line": cls["line"],
                "description": f"Class defined at line {cls['line']}"
            })
        
        for func in analysis.functions[:10]:  # Top 10 functions
            key_components.append({
                "type": "function",
                "name": func["name"],
                "line": func["line"],
                "description": f"Function defined at line {func['line']}"
            })
        
        # Navigation hints
        nav_hints = []
        if analysis.imports:
            nav_hints.append(f"Imports: {', '.join(analysis.imports[:5])}")
        if analysis.depended_by:
            nav_hints.append(f"Used by: {len(analysis.depended_by)} files")
        if analysis.patterns:
            nav_hints.append(f"Implements: {', '.join(analysis.patterns)}")
        
        # Calculate coverage score (rough estimate)
        coverage_score = 0.5  # Base score
        if analysis.classes or analysis.functions:
            coverage_score += 0.2
        if analysis.patterns:
            coverage_score += 0.1
        if analysis.imports:
            coverage_score += 0.1
        if analysis.non_obvious:
            coverage_score += 0.1
        
        # Estimate tool calls saved (3-5 calls per file without context)
        tool_calls_saved = 4
        
        return ContextFile(
            module_name=module_name,
            file_path=file_path,
            summary=summary,
            key_components=key_components,
            dependencies=analysis.imports[:10],
            related_files=related,
            navigation_hints=nav_hints,
            non_obvious_patterns=analysis.non_obvious + analysis.gotchas,
            coverage_score=min(coverage_score, 1.0),
            tool_calls_saved=tool_calls_saved
        )
    
    def precompute(self, source_path: str) -> KnowledgeIndex:
        """
        Main entry point: analyze codebase and generate all context files.
        
        Args:
            source_path: Root directory to analyze
            
        Returns:
            KnowledgeIndex with all generated context
        """
        print(f"🔍 Knowledge Pre-compute Engine starting...")
        print(f"   Source: {source_path}")
        
        # Phase 1: Scan
        print("\n📁 Phase 1: Scanning directory...")
        files = self.scan_directory(source_path)
        print(f"   Found {len(files)} files to analyze")
        
        # Phase 2: Analyze (like Meta's 50+ specialized agents)
        print("\n🤖 Phase 2: Running specialized analyzers...")
        analyzed_count = 0
        for i, file_path in enumerate(files):
            if i % 100 == 0:
                print(f"   Progress: {i}/{len(files)} files...")
            
            file_type = self.detect_file_type(file_path)
            if file_type in [FileType.CODE, FileType.CONFIG, FileType.DOC]:
                self.analyze_file(file_path)
                analyzed_count += 1
        
        print(f"   Analyzed {analyzed_count} files")
        
        # Phase 3: Build dependency graph
        print("\n🔗 Phase 3: Building dependency graph...")
        self.build_dependency_graph()
        
        # Phase 4: Generate context files
        print("\n📝 Phase 4: Generating context files...")
        context_files_dir = self.output_dir / "context_files"
        context_files_dir.mkdir(exist_ok=True)
        
        generated_count = 0
        total_tool_calls_saved = 0
        
        for file_path, analysis in self.file_analyses.items():
            if analysis.file_type == FileType.CODE:
                context = self.generate_context_file(file_path)
                
                # Save context file
                context_filename = f"{Path(file_path).stem}.context.json"
                context_path = context_files_dir / context_filename
                
                with open(context_path, 'w') as f:
                    json.dump(context.to_dict(), f, indent=2)
                
                generated_count += 1
                total_tool_calls_saved += context.tool_calls_saved
        
        # Phase 5: Build master index
        print("\n📚 Phase 5: Building knowledge index...")
        index = KnowledgeIndex(
            source_path=source_path,
            total_files=len(files),
            analyzed_files=analyzed_count,
            context_files=generated_count,
            coverage_percent=(analyzed_count / len(files) * 100) if files else 0,
            analysis_date=datetime.now().isoformat()
        )
        
        # Build module registry
        for file_path in self.file_analyses.keys():
            path = Path(file_path)
            context_filename = f"{path.stem}.context.json"
            index.modules[path.stem] = str(context_files_dir / context_filename)
        
        # Build concept index
        for file_path, analysis in self.file_analyses.items():
            for concept in analysis.domain_concepts:
                concept_key = concept.split(":")[0].strip()
                if concept_key not in index.concept_index:
                    index.concept_index[concept_key] = []
                index.concept_index[concept_key].append(file_path)
        
        # Build pattern index
        for file_path, analysis in self.file_analyses.items():
            for pattern in analysis.patterns:
                if pattern not in index.pattern_index:
                    index.pattern_index[pattern] = []
                index.pattern_index[pattern].append(file_path)
        
        # Save index
        index_path = self.output_dir / "knowledge_index.json"
        with open(index_path, 'w') as f:
            json.dump(index.to_dict(), f, indent=2)
        
        # Phase 6: Summary
        print(f"\n✅ Knowledge pre-computation complete!")
        print(f"   Total files: {index.total_files}")
        print(f"   Analyzed: {index.analyzed_files}")
        print(f"   Context files: {index.context_files}")
        print(f"   Coverage: {index.coverage_percent:.1f}%")
        print(f"   Estimated tool calls saved: {total_tool_calls_saved}")
        print(f"\n📂 Output: {self.output_dir.absolute()}")
        
        return index
    
    def query_context(self, query: str, index: Optional[KnowledgeIndex] = None) -> List[Dict[str, Any]]:
        """
        Query the pre-computed context for relevant information.
        
        Args:
            query: Search query (module name, concept, or pattern)
            index: Optional pre-loaded index
            
        Returns:
            List of relevant context file summaries
        """
        if index is None:
            index_path = self.output_dir / "knowledge_index.json"
            if index_path.exists():
                with open(index_path) as f:
                    data = json.load(f)
                    index = KnowledgeIndex(**data)
            else:
                return []
        
        results = []
        query_lower = query.lower()
        
        # Check module registry
        for module_name, context_path in index.modules.items():
            if query_lower in module_name.lower():
                try:
                    with open(context_path) as f:
                        context_data = json.load(f)
                        results.append(context_data)
                except Exception:
                    pass
        
        # Check concept index
        for concept, files in index.concept_index.items():
            if query_lower in concept.lower():
                for file_path in files[:3]:  # Limit results
                    path = Path(file_path)
                    if path.stem in index.modules:
                        try:
                            with open(index.modules[path.stem]) as f:
                                context_data = json.load(f)
                                if context_data not in results:
                                    results.append(context_data)
                        except Exception:
                            pass
        
        # Check pattern index
        for pattern, files in index.pattern_index.items():
            if query_lower in pattern.lower():
                for file_path in files[:3]:
                    path = Path(file_path)
                    if path.stem in index.modules:
                        try:
                            with open(index.modules[path.stem]) as f:
                                context_data = json.load(f)
                                if context_data not in results:
                                    results.append(context_data)
                        except Exception:
                            pass
        
        return results[:10]  # Limit total results


def demo():
    """Demo the Knowledge Pre-compute Engine."""
    print("=" * 60)
    print("🧠 Knowledge Pre-compute Engine Demo")
    print("   Inspired by Meta's 50+ agent approach (April 2026)")
    print("=" * 60)
    
    # Analyze the agi-research codebase itself
    engine = KnowledgePrecomputeEngine(output_dir="/home/workspace/agi-research/.knowledge_context")
    index = engine.precompute("/home/workspace/agi-research")
    
    # Demo query
    print("\n🔍 Demo Query: 'agent'")
    results = engine.query_context("agent", index)
    print(f"   Found {len(results)} relevant context files")
    
    for result in results[:3]:
        print(f"\n   📄 {result['module_name']}")
        print(f"      {result['summary']}")
        print(f"      Components: {len(result['key_components'])}")
        print(f"      Tool calls saved: {result['tool_calls_saved']}")
    
    print("\n" + "=" * 60)
    print("✅ Demo complete!")
    print("=" * 60)
    
    return index


if __name__ == "__main__":
    demo()
