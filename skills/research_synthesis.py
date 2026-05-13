"""
Research Synthesis Skill - Aggregate findings from parallel research paths.

Inspired by AggAgent (arXiv:2604.11753v1) - treats multiple research rollouts
as an environment for inspection, synthesis, and knowledge distillation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Set, Tuple
from datetime import datetime
from collections import defaultdict
import json
import re


@dataclass
class ResearchFinding:
    """Single research finding from a source."""
    source: str
    source_type: str  # "arxiv", "github", "web", "paper", "experiment"
    title: str
    content: str
    date: datetime
    tags: List[str] = field(default_factory=list)
    confidence: float = 0.8  # 0-1 confidence in finding
    citations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "source_type": self.source_type,
            "title": self.title,
            "content": self.content,
            "date": self.date.isoformat(),
            "tags": self.tags,
            "confidence": self.confidence,
            "citations": self.citations,
        }


@dataclass
class SynthesisTheme:
    """Emergent theme from synthesizing multiple findings."""
    theme_id: str
    name: str
    description: str
    supporting_findings: List[str]  # finding source identifiers
    confidence: float
    contradictions: List[str] = field(default_factory=list)  # conflicting finding ids
    gaps: List[str] = field(default_factory=list)  # identified research gaps
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "theme_id": self.theme_id,
            "name": self.name,
            "description": self.description,
            "supporting_findings": self.supporting_findings,
            "confidence": self.confidence,
            "contradictions": self.contradictions,
            "gaps": self.gaps,
        }


@dataclass
class SynthesisReport:
    """Complete synthesis report from multiple research sources."""
    report_id: str
    generated_at: datetime
    num_sources: int
    num_findings: int
    themes: List[SynthesisTheme]
    key_insights: List[str]
    contradictions: List[Dict[str, Any]]
    research_gaps: List[str]
    next_steps: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "num_sources": self.num_sources,
            "num_findings": self.num_findings,
            "themes": [t.to_dict() for t in self.themes],
            "key_insights": self.key_insights,
            "contradictions": self.contradictions,
            "research_gaps": self.research_gaps,
            "next_steps": self.next_steps,
        }
    
    def to_markdown(self) -> str:
        """Generate markdown report for human reading."""
        lines = [
            f"# Research Synthesis Report\n",
            f"**Generated**: {self.generated_at.strftime('%Y-%m-%d %H:%M')}",
            f"**Sources**: {self.num_sources} | **Findings**: {self.num_findings}\n",
            "## Key Insights\n",
        ]
        for i, insight in enumerate(self.key_insights, 1):
            lines.append(f"{i}. {insight}")
        lines.append("\n## Emergent Themes\n")
        for theme in sorted(self.themes, key=lambda t: t.confidence, reverse=True):
            lines.append(f"\n### {theme.name} (confidence: {theme.confidence:.2f})")
            lines.append(f"{theme.description}")
            lines.append(f"\n**Supporting**: {', '.join(theme.supporting_findings[:3])}")
            if theme.contradictions:
                lines.append(f"**Contradictions**: {len(theme.contradictions)} conflicts identified")
            if theme.gaps:
                lines.append(f"**Gaps**: {', '.join(theme.gaps[:2])}")
        
        if self.contradictions:
            lines.append("\n## Identified Contradictions\n")
            for contradiction in self.contradictions:
                lines.append(f"- **{contradiction['theme']}**: {contradiction['description']}")
        
        if self.research_gaps:
            lines.append("\n## Research Gaps\n")
            for gap in self.research_gaps:
                lines.append(f"- {gap}")
        
        lines.append("\n## Recommended Next Steps\n")
        for i, step in enumerate(self.next_steps, 1):
            lines.append(f"{i}. {step}")
        
        return "\n".join(lines)


class ResearchSynthesizer:
    """
    Synthesize findings from multiple research sources.
    
    Implements aggregation patterns from AggAgent - treating parallel
    research paths as inspectable environment for synthesis.
    """
    
    def __init__(self):
        self.findings: List[ResearchFinding] = []
        self.theme_extractors: Dict[str, Callable[[ResearchFinding], bool]] = {}
        self._register_default_extractors()
    
    def _register_default_extractors(self):
        """Register default theme extraction patterns."""
        self.theme_extractors = {
            "self_evolution": lambda f: any(kw in f.content.lower() for kw in 
                ["self-evolving", "self modifying", "self-modifying", 
                 "selfmodifying", "self evolution", "self-evolution",
                 "autonomous improvement", "meta-learning",
                 "meta learning", "co-evolution", "coevolution",
                 "self-improving", "self improving"]),
            "multi_agent": lambda f: any(kw in f.content.lower() for kw in 
                ["multi-agent", "multi agent", "multiagent",
                 "agent orchestration", "agentic mesh", "swarm", 
                 "agent-to-agent", "a2a", "agent collaboration"]),
            "neuro_symbolic": lambda f: any(kw in f.content.lower() for kw in 
                ["neuro-symbolic", "neuro symbolic", "neurosymbolic",
                 "symbolic reasoning", "dsl", "compositional",
                 "hybrid neural", "neural symbolic"]),
            "safety_governance": lambda f: any(kw in f.content.lower() for kw in 
                ["safety", "governance", "constitutional", "constitution",
                 "alignment", "risk", "circuit breaker", "human-in-the-loop",
                 "human oversight", "approval workflow"]),
            "memory_systems": lambda f: any(kw in f.content.lower() for kw in 
                ["memory", "context", "retrieval", "tiered memory", 
                 "l0/l1/l2", "long-term memory", "working memory",
                 "episodic memory", "semantic memory"]),
            "benchmarks": lambda f: any(kw in f.content.lower() for kw in 
                ["arc-agi", "arc agi", "benchmark", "evaluation", 
                 "performance", "score", "accuracy", "metric"]),
            "mcp": lambda f: any(kw in f.content.lower() for kw in 
                ["mcp", "model context protocol", "tool integration",
                 "tool registry", "llm-tool"]),
            "parallelization": lambda f: any(kw in f.content.lower() for kw in 
                ["parallel", "aggregation", "coordination", "distributed",
                 "concurrent", "parallelizable", "aggagent"]),
        }
    
    def add_finding(self, finding: ResearchFinding) -> None:
        """Add a research finding to the synthesis pool."""
        self.findings.append(finding)
    
    def add_findings_batch(self, findings: List[ResearchFinding]) -> None:
        """Add multiple findings at once."""
        self.findings.extend(findings)
    
    def extract_themes(self) -> Dict[str, List[ResearchFinding]]:
        """Extract themes from all findings."""
        themes: Dict[str, List[ResearchFinding]] = defaultdict(list)
        
        for finding in self.findings:
            for theme_name, extractor in self.theme_extractors.items():
                try:
                    if extractor(finding):
                        themes[theme_name].append(finding)
                except Exception:
                    continue
        
        return dict(themes)
    
    def identify_contradictions(self, themes: Dict[str, List[ResearchFinding]]) -> List[Dict[str, Any]]:
        """Identify contradictions within themes."""
        contradictions = []
        
        for theme_name, findings in themes.items():
            if len(findings) < 2:
                continue
            
            # Check for confidence disagreements
            confidences = [f.confidence for f in findings]
            if max(confidences) - min(confidences) > 0.5:
                contradictions.append({
                    "theme": theme_name,
                    "type": "confidence_disagreement",
                    "description": f"Confidence ranges from {min(confidences):.2f} to {max(confidences):.2f}",
                    "sources": [f.source for f in findings],
                })
            
            # Check for temporal conflicts (recent finding contradicts older)
            sorted_by_date = sorted(findings, key=lambda f: f.date)
            if len(sorted_by_date) >= 2:
                recent = sorted_by_date[-1]
                older = sorted_by_date[-2]
                if "not" in recent.content.lower() and any(
                    word in older.content.lower() for word in ["is", "are", "will", "can"]
                ):
                    contradictions.append({
                        "theme": theme_name,
                        "type": "temporal_contradiction",
                        "description": f"Recent finding ({recent.date.date()}) may contradict earlier ({older.date.date()})",
                        "sources": [recent.source, older.source],
                    })
        
        return contradictions
    
    def identify_gaps(self, themes: Dict[str, List[ResearchFinding]]) -> List[str]:
        """Identify research gaps based on theme coverage."""
        gaps = []
        
        # Expected themes for comprehensive AGI research
        expected_themes = set(self.theme_extractors.keys())
        found_themes = set(themes.keys())
        missing_themes = expected_themes - found_themes
        
        for theme in missing_themes:
            gaps.append(f"No research coverage for: {theme.replace('_', ' ')}")
        
        # Identify under-represented themes
        for theme_name, findings in themes.items():
            if len(findings) < 2:
                gaps.append(f"Limited research on {theme_name.replace('_', ' ')}: only {len(findings)} source(s)")
        
        return gaps
    
    def generate_key_insights(self, themes: Dict[str, List[ResearchFinding]]) -> List[str]:
        """Generate high-level insights from themes."""
        insights = []
        
        # Count sources per theme for prioritization
        theme_counts = {name: len(findings) for name, findings in themes.items()}
        sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)
        
        for theme_name, count in sorted_themes[:5]:
            if count >= 3:
                theme_findings = themes[theme_name]
                avg_confidence = sum(f.confidence for f in theme_findings) / len(theme_findings)
                insights.append(
                    f"{theme_name.replace('_', ' ').title()}: Strong consensus across {count} sources "
                    f"(avg confidence: {avg_confidence:.2f})"
                )
            elif count >= 2:
                insights.append(
                    f"{theme_name.replace('_', ' ').title()}: Emerging pattern with {count} supporting sources"
                )
        
        # Cross-theme insights
        if "self_evolution" in themes and "multi_agent" in themes:
            insights.append(
                "Self-evolution and multi-agent coordination are converging trends - "
                "agents that evolve in multi-agent environments show stronger generalization"
            )
        
        if "neuro_symbolic" in themes and "benchmarks" in themes:
            insights.append(
                "Neuro-symbolic approaches showing measurable benchmark improvements "
                "(ARC-AGI-2: 16% → 30.8%)"
            )
        
        return insights
    
    def recommend_next_steps(self, themes: Dict[str, List[ResearchFinding]], 
                           gaps: List[str]) -> List[str]:
        """Generate recommended next research steps."""
        steps = []
        
        # Prioritize under-explored high-impact themes
        if "safety_governance" not in themes or len(themes.get("safety_governance", [])) < 3:
            steps.append("Deep research: Safety and governance frameworks for self-evolving multi-agent systems")
        
        if "parallelization" not in themes or len(themes.get("parallelization", [])) < 2:
            steps.append("Investigate parallel execution patterns (AggAgent-style) for research aggregation")
        
        # Build on strong themes
        if "self_evolution" in themes and len(themes["self_evolution"]) >= 3:
            steps.append("Prototype: Self-evolving skill acquisition module based on Agent-World and GenericAgent patterns")
        
        if "neuro_symbolic" in themes and len(themes["neuro_symbolic"]) >= 2:
            steps.append("Experiment: Implement compositional DSL for ARC-AGI-3 style reasoning")
        
        if "mcp" in themes:
            steps.append("Integration: Full MCP server implementation for AGI agent tool registry")
        
        # Address gaps
        for gap in gaps[:3]:
            if "Limited research" in gap:
                topic = gap.split("Limited research on ")[1].split(":")[0]
                steps.append(f"Expand research coverage: {topic}")
        
        return steps
    
    def synthesize(self, report_id: Optional[str] = None) -> SynthesisReport:
        """
        Synthesize all findings into a comprehensive report.
        
        This is the core AggAgent-inspired aggregation - treating multiple
        research trajectories as inspectable environment for knowledge distillation.
        """
        if not self.findings:
            raise ValueError("No findings to synthesize")
        
        # Extract themes
        themes_dict = self.extract_themes()
        
        # Create theme objects
        theme_objects = []
        for theme_name, findings in themes_dict.items():
            if len(findings) >= 2:  # Only themes with multiple findings
                avg_confidence = sum(f.confidence for f in findings) / len(findings)
                description = self._generate_theme_description(theme_name, findings)
                
                theme_obj = SynthesisTheme(
                    theme_id=f"theme_{theme_name}",
                    name=theme_name.replace('_', ' ').title(),
                    description=description,
                    supporting_findings=[f.source for f in findings],
                    confidence=avg_confidence,
                )
                theme_objects.append(theme_obj)
        
        # Identify contradictions and gaps
        contradictions = self.identify_contradictions(themes_dict)
        for theme_obj in theme_objects:
            theme_contradictions = [c for c in contradictions 
                                   if c['theme'].replace('-', '_') == theme_obj.theme_id.replace('theme_', '')]
            theme_obj.contradictions = [c['type'] for c in theme_contradictions]
        
        gaps = self.identify_gaps(themes_dict)
        for theme_obj in theme_objects:
            theme_gaps = [g for g in gaps if theme_obj.name.lower().replace(' ', '_') in g.lower()]
            theme_obj.gaps = theme_gaps
        
        # Generate insights and recommendations
        key_insights = self.generate_key_insights(themes_dict)
        next_steps = self.recommend_next_steps(themes_dict, gaps)
        
        # Get unique sources
        unique_sources = set(f.source for f in self.findings)
        
        return SynthesisReport(
            report_id=report_id or f"synthesis_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            generated_at=datetime.now(),
            num_sources=len(unique_sources),
            num_findings=len(self.findings),
            themes=theme_objects,
            key_insights=key_insights,
            contradictions=contradictions,
            research_gaps=gaps,
            next_steps=next_steps,
        )
    
    def _generate_theme_description(self, theme_name: str, findings: List[ResearchFinding]) -> str:
        """Generate a description for a theme based on its findings."""
        # Extract key terms from findings
        all_content = " ".join([f.content for f in findings])
        
        descriptions = {
            "self_evolution": (
                f"Self-evolving agent architectures showing {len(findings)} distinct approaches. "
                f"Key patterns: Agent-World training arenas, GenericAgent skill crystallization, "
                f"Ouroboros constitutional self-modification."
            ),
            "multi_agent": (
                f"Multi-agent orchestration with {len(findings)} implementations. "
                f"Graph-based DAGs emerging as standard pattern for coordination."
            ),
            "neuro_symbolic": (
                f"Neuro-symbolic hybrid approaches from {len(findings)} sources. "
                f"Compositional reasoning with DSLs showing measurable gains on ARC-AGI."
            ),
            "safety_governance": (
                f"Safety and governance frameworks across {len(findings)} sources. "
                f"Shift toward population-level multi-agent risk analysis."
            ),
            "memory_systems": (
                f"Memory architectures from {len(findings)} sources. "
                f"Tiered L0/L1/L2 hierarchy becoming standard pattern."
            ),
            "benchmarks": (
                f"Benchmark results from {len(findings)} sources. "
                f"ARC-AGI-3 showing massive human-AI performance gap (100% vs <1%)."
            ),
            "mcp": (
                f"Model Context Protocol adoption across {len(findings)} frameworks. "
                f"Emerging as standard for agent-tool integration."
            ),
            "parallelization": (
                f"Parallel execution patterns from {len(findings)} sources. "
                f"AggAgent-style aggregation enabling cost-efficient long-horizon tasks."
            ),
        }
        
        return descriptions.get(theme_name, 
            f"Theme '{theme_name}' identified across {len(findings)} research sources.")
    
    def clear(self) -> None:
        """Clear all findings."""
        self.findings.clear()
    
    def export_findings(self, filepath: str) -> None:
        """Export all findings to JSON."""
        data = {
            "exported_at": datetime.now().isoformat(),
            "num_findings": len(self.findings),
            "findings": [f.to_dict() for f in self.findings],
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def import_findings(self, filepath: str) -> None:
        """Import findings from JSON."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        for finding_dict in data.get("findings", []):
            finding = ResearchFinding(
                source=finding_dict["source"],
                source_type=finding_dict["source_type"],
                title=finding_dict["title"],
                content=finding_dict["content"],
                date=datetime.fromisoformat(finding_dict["date"]),
                tags=finding_dict.get("tags", []),
                confidence=finding_dict.get("confidence", 0.8),
                citations=finding_dict.get("citations", []),
            )
            self.findings.append(finding)


# Convenience functions for common use cases

def create_synthesizer() -> ResearchSynthesizer:
    """Create a new research synthesizer with default configuration."""
    return ResearchSynthesizer()


def quick_synthesize(findings_data: List[Dict[str, Any]]) -> SynthesisReport:
    """
    Quick synthesis from raw finding data.
    
    Example:
        findings = [
            {
                "source": "arXiv:2604.18292",
                "source_type": "arxiv",
                "title": "Agent-World",
                "content": "Self-evolving training arena...",
                "date": "2026-04-20",
                "tags": ["self-evolution", "benchmarks"],
            },
            ...
        ]
        report = quick_synthesize(findings)
    """
    synthesizer = ResearchSynthesizer()
    
    for data in findings_data:
        finding = ResearchFinding(
            source=data["source"],
            source_type=data["source_type"],
            title=data["title"],
            content=data["content"],
            date=datetime.fromisoformat(data["date"]) if isinstance(data["date"], str) else data["date"],
            tags=data.get("tags", []),
            confidence=data.get("confidence", 0.8),
            citations=data.get("citations", []),
        )
        synthesizer.add_finding(finding)
    
    return synthesizer.synthesize()
