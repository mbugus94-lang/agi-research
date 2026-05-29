"""
Research Synthesis Skill

Automatically processes web research results into structured, actionable summaries.
Inspired by:
- "Explore Before You Solve" (AERA framework) - systematic exploration before planning
- "Generative Recursive Reasoning" (GRAM) - multi-trajectory reasoning synthesis
- "Learning to Build the Environment" (EvoEnv) - self-improving knowledge construction

This skill transforms raw search results into:
1. Structured findings with confidence scores
2. Research trends and patterns
3. Actionable insights for agent decision-making
4. Persistent knowledge for future reference
"""

import json
import hashlib
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import asyncio


class FindingCategory(Enum):
    """Categories for research findings."""
    BREAKTHROUGH = "breakthrough"      # Major new development
    TREND = "trend"                    # Emerging pattern
    TOOL = "tool"                      # New tool/framework
    PAPER = "paper"                    # Research paper
    OPINION = "opinion"                # Expert opinion/prediction
    WARNING = "warning"                # Risk/caution


class ConfidenceLevel(Enum):
    """Confidence levels for synthesized findings."""
    HIGH = 0.9      # Multiple corroborating sources
    MEDIUM = 0.7    # Some corroboration or authoritative source
    LOW = 0.5       # Single source or preliminary
    SPECULATIVE = 0.3  # Early/conjectural


@dataclass
class ResearchFinding:
    """A single synthesized research finding."""
    title: str
    summary: str
    category: FindingCategory
    confidence: ConfidenceLevel
    sources: List[Dict[str, str]]  # [{"title": "...", "url": "..."}]
    key_insights: List[str]
    timestamp: datetime = field(default_factory=datetime.now)
    relevance_score: float = 0.5
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "summary": self.summary,
            "category": self.category.value,
            "confidence": self.confidence.value,
            "sources": self.sources,
            "key_insights": self.key_insights,
            "timestamp": self.timestamp.isoformat(),
            "relevance_score": self.relevance_score,
            "tags": self.tags
        }


@dataclass
class ResearchTrend:
    """An identified trend across multiple findings."""
    name: str
    description: str
    evidence_count: int
    supporting_findings: List[str]  # Finding titles
    momentum: str  # "accelerating", "stable", "early"
    time_horizon: str  # "immediate", "near-term", "long-term"


@dataclass
class SynthesisResult:
    """Complete research synthesis output."""
    query: str
    timestamp: datetime
    total_sources: int
    findings: List[ResearchFinding]
    trends: List[ResearchTrend]
    key_takeaways: List[str]
    recommended_actions: List[str]
    knowledge_hash: str  # For deduplication
    
    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "timestamp": self.timestamp.isoformat(),
            "total_sources": self.total_sources,
            "findings": [f.to_dict() for f in self.findings],
            "trends": [
                {
                    "name": t.name,
                    "description": t.description,
                    "evidence_count": t.evidence_count,
                    "supporting_findings": t.supporting_findings,
                    "momentum": t.momentum,
                    "time_horizon": t.time_horizon
                }
                for t in self.trends
            ],
            "key_takeaways": self.key_takeaways,
            "recommended_actions": self.recommended_actions,
            "knowledge_hash": self.knowledge_hash
        }


class ResearchSynthesisSkill:
    """
    Synthesizes web research into structured knowledge.
    
    Implements the "explore before you solve" pattern:
    1. EXPLORE: Gather diverse sources
    2. SYNTHESIZE: Extract patterns and insights  
    3. STRUCTURE: Organize into actionable findings
    4. PERSIST: Store for future use
    """
    
    def __init__(self):
        self.synthesis_history: List[SynthesisResult] = []
        self.category_patterns = {
            FindingCategory.BREAKTHROUGH: [
                "breakthrough", "revolutionary", "first time", "solves",
                "achieves", "new milestone", "significant advance"
            ],
            FindingCategory.TOOL: [
                "framework", "library", "sdk", "platform", "open source",
                "github", "released", "launched", "available"
            ],
            FindingCategory.PAPER: [
                "arxiv", "research", "paper", "study", "publication",
                "demonstrates", "proposes", "introduces"
            ],
            FindingCategory.WARNING: [
                "risk", "warning", "danger", "threat", "concern",
                "existential", "safety", "attack", "poisoning"
            ]
        }
    
    def _compute_hash(self, content: str) -> str:
        """Compute hash for deduplication."""
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def _categorize_finding(self, title: str, text: str) -> FindingCategory:
        """Auto-categorize based on content patterns."""
        content = (title + " " + text).lower()
        
        for category, patterns in self.category_patterns.items():
            if any(p in content for p in patterns):
                return category
        
        return FindingCategory.TREND
    
    def _extract_confidence(self, sources: List[Dict]) -> ConfidenceLevel:
        """Determine confidence based on source diversity and authority."""
        if len(sources) >= 3:
            return ConfidenceLevel.HIGH
        elif len(sources) >= 2:
            return ConfidenceLevel.MEDIUM
        elif any(s.get("url", "").endswith(('.edu', '.gov', 'arxiv.org')) 
                 for s in sources):
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW
    
    def _extract_insights(self, text: str) -> List[str]:
        """Extract key insights from text."""
        insights = []
        sentences = text.split('.')
        
        for sentence in sentences:
            sentence = sentence.strip()
            # Look for insight patterns
            if any(marker in sentence.lower() for marker in [
                "key", "main", "critical", "important", "essential",
                "enables", "allows", "provides", "demonstrates",
                "achieves", "outperforms", "improves", "reduces"
            ]):
                if len(sentence) > 20 and len(sentence) < 200:
                    insights.append(sentence)
        
        return insights[:5]  # Top 5 insights
    
    def synthesize(
        self,
        query: str,
        search_results: List[Dict[str, Any]],
        relevance_threshold: float = 0.3
    ) -> SynthesisResult:
        """
        Synthesize search results into structured findings.
        
        Args:
            query: Original research query
            search_results: Raw search results with title, url, text
            relevance_threshold: Minimum relevance to include
            
        Returns:
            SynthesisResult with structured findings
        """
        findings = []
        
        # Process each search result
        for result in search_results:
            title = result.get("title", "")
            text = result.get("text", "")
            url = result.get("url", "")
            
            # Skip low-quality results
            if len(text) < 50:
                continue
            
            # Auto-categorize
            category = self._categorize_finding(title, text)
            
            # Extract insights
            insights = self._extract_insights(text)
            
            # Build finding
            finding = ResearchFinding(
                title=title,
                summary=text[:500] + "..." if len(text) > 500 else text,
                category=category,
                confidence=self._extract_confidence([{"title": title, "url": url}]),
                sources=[{"title": title, "url": url}],
                key_insights=insights,
                relevance_score=0.5 + (0.3 if category == FindingCategory.BREAKTHROUGH else 0)
            )
            
            findings.append(finding)
        
        # Identify trends
        trends = self._identify_trends(findings)
        
        # Generate takeaways and recommendations
        takeaways = self._generate_takeaways(findings, trends)
        actions = self._generate_recommendations(findings, trends)
        
        # Create synthesis result
        synthesis = SynthesisResult(
            query=query,
            timestamp=datetime.now(),
            total_sources=len(search_results),
            findings=findings,
            trends=trends,
            key_takeaways=takeaways,
            recommended_actions=actions,
            knowledge_hash=self._compute_hash(query + json.dumps(
                [f.title for f in findings]
            ))
        )
        
        # Store in history
        self.synthesis_history.append(synthesis)
        
        return synthesis
    
    def _identify_trends(self, findings: List[ResearchFinding]) -> List[ResearchTrend]:
        """Identify trends across findings."""
        trends = []
        
        # Group by category and look for patterns
        category_counts = {}
        for f in findings:
            cat = f.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        # Create trend for significant categories
        for cat, count in category_counts.items():
            if count >= 2:
                supporting = [f.title for f in findings if f.category.value == cat][:5]
                trends.append(ResearchTrend(
                    name=f"{cat.replace('_', ' ').title()} Activity",
                    description=f"Multiple developments in {cat} observed",
                    evidence_count=count,
                    supporting_findings=supporting,
                    momentum="accelerating" if count >= 4 else "stable",
                    time_horizon="near-term"
                ))
        
        # Look for specific technology trends
        tech_terms = ["MCP", "A2A", "multi-agent", "autonomous", "reasoning"]
        for term in tech_terms:
            matching = [f for f in findings if term.lower() in f.summary.lower()]
            if len(matching) >= 2:
                trends.append(ResearchTrend(
                    name=f"{term} Focus",
                    description=f"Growing attention to {term} in research",
                    evidence_count=len(matching),
                    supporting_findings=[f.title for f in matching][:3],
                    momentum="accelerating",
                    time_horizon="immediate"
                ))
        
        return trends
    
    def _generate_takeaways(
        self,
        findings: List[ResearchFinding],
        trends: List[ResearchTrend]
    ) -> List[str]:
        """Generate key takeaways from synthesis."""
        takeaways = []
        
        # High confidence findings
        high_conf = [f for f in findings if f.confidence.value >= 0.7]
        if high_conf:
            takeaways.append(
                f"{len(high_conf)} high-confidence finding(s) identified, "
                f"including {len([f for f in high_conf if f.category == FindingCategory.BREAKTHROUGH])} "
                f"potential breakthrough(s)"
            )
        
        # Trend summary
        if trends:
            accelerating = [t for t in trends if t.momentum == "accelerating"]
            if accelerating:
                takeaways.append(
                    f"{len(accelerating)} accelerating trend(s) detected: "
                    f"{', '.join(t.name for t in accelerating[:3])}"
                )
        
        # Category distribution
        categories = {}
        for f in findings:
            cat = f.category.value
            categories[cat] = categories.get(cat, 0) + 1
        
        top_categories = sorted(categories.items(), key=lambda x: x[1], reverse=True)[:2]
        if top_categories:
            takeaways.append(
                f"Primary focus areas: {', '.join(f'{cat}({count})' for cat, count in top_categories)}"
            )
        
        return takeaways
    
    def _generate_recommendations(
        self,
        findings: List[ResearchFinding],
        trends: List[ResearchTrend]
    ) -> List[str]:
        """Generate recommended actions based on synthesis."""
        actions = []
        
        # Breakthrough follow-up
        breakthroughs = [f for f in findings if f.category == FindingCategory.BREAKTHROUGH]
        if breakthroughs:
            actions.append(
                f"Investigate {len(breakthroughs)} breakthrough(s) for potential "
                f"integration or architectural impact"
            )
        
        # Tool evaluation
        tools = [f for f in findings if f.category == FindingCategory.TOOL]
        if tools:
            actions.append(
                f"Evaluate {len(tools)} new tool(s) for potential adoption"
            )
        
        # Paper deep-dive
        papers = [f for f in findings if f.category == FindingCategory.PAPER]
        if papers:
            high_conf_papers = [p for p in papers if p.confidence.value >= 0.7]
            actions.append(
                f"Deep-read {len(high_conf_papers)} high-confidence paper(s)"
            )
        
        # Warning review
        warnings = [f for f in findings if f.category == FindingCategory.WARNING]
        if warnings:
            actions.append(
                f"Review {len(warnings)} warning/caution item(s) for risk assessment"
            )
        
        # Trend monitoring
        if trends:
            actions.append(
                f"Continue monitoring {len(trends)} identified trend(s)"
            )
        
        return actions
    
    def compare_syntheses(
        self,
        synthesis_a: SynthesisResult,
        synthesis_b: SynthesisResult
    ) -> Dict:
        """Compare two synthesis results for delta analysis."""
        findings_a = {f.title for f in synthesis_a.findings}
        findings_b = {f.title for f in synthesis_b.findings}
        
        new_findings = findings_b - findings_a
        stale_findings = findings_a - findings_b
        
        return {
            "new_findings_count": len(new_findings),
            "stale_findings_count": len(stale_findings),
            "new_findings": list(new_findings)[:10],
            "trend_changes": self._compare_trends(synthesis_a.trends, synthesis_b.trends),
            "time_delta_hours": (
                synthesis_b.timestamp - synthesis_a.timestamp
            ).total_seconds() / 3600
        }
    
    def _compare_trends(
        self,
        trends_a: List[ResearchTrend],
        trends_b: List[ResearchTrend]
    ) -> List[Dict]:
        """Compare trend lists."""
        names_a = {t.name for t in trends_a}
        names_b = {t.name for t in trends_b}
        
        changes = []
        
        # New trends
        for t in trends_b:
            if t.name not in names_a:
                changes.append({
                    "type": "emerged",
                    "trend": t.name,
                    "evidence": t.evidence_count
                })
        
        # Faded trends
        for t in trends_a:
            if t.name not in names_b:
                changes.append({
                    "type": "faded",
                    "trend": t.name
                })
        
        return changes
    
    def get_synthesis_history(self) -> List[SynthesisResult]:
        """Get all past syntheses."""
        return self.synthesis_history
    
    def find_similar_research(
        self,
        query: str,
        top_k: int = 3
    ) -> List[SynthesisResult]:
        """Find historically similar research queries."""
        query_terms = set(query.lower().split())
        
        scored = []
        for synth in self.synthesis_history:
            synth_terms = set(synth.query.lower().split())
            overlap = len(query_terms & synth_terms) / len(query_terms | synth_terms)
            scored.append((overlap, synth))
        
        scored.sort(reverse=True)
        return [s for _, s in scored[:top_k]]


# Convenience functions for quick synthesis
def synthesize_research(
    query: str,
    search_results: List[Dict[str, Any]]
) -> SynthesisResult:
    """Quick synthesis function."""
    skill = ResearchSynthesisSkill()
    return skill.synthesize(query, search_results)


def format_synthesis_markdown(synthesis: SynthesisResult) -> str:
    """Format synthesis as markdown for documentation."""
    lines = [
        f"# Research Synthesis: {synthesis.query}",
        f"\n*Generated: {synthesis.timestamp.strftime('%Y-%m-%d %H:%M')}*",
        f"*Sources analyzed: {synthesis.total_sources}*",
        "\n## Key Takeaways",
    ]
    
    for takeaway in synthesis.key_takeaways:
        lines.append(f"- {takeaway}")
    
    lines.append("\n## Identified Trends")
    for trend in synthesis.trends:
        lines.append(f"\n### {trend.name}")
        lines.append(f"- **Status**: {trend.momentum}")
        lines.append(f"- **Evidence**: {trend.evidence_count} findings")
        lines.append(f"- **Horizon**: {trend.time_horizon}")
        lines.append(f"- {trend.description}")
    
    lines.append("\n## Findings by Category")
    
    by_category = {}
    for finding in synthesis.findings:
        cat = finding.category.value
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(finding)
    
    for cat, findings in sorted(by_category.items()):
        lines.append(f"\n### {cat.replace('_', ' ').title()} ({len(findings)})")
        for f in findings[:5]:  # Top 5 per category
            conf_emoji = "🔴" if f.confidence.value < 0.5 else "🟡" if f.confidence.value < 0.8 else "🟢"
            lines.append(f"\n**{f.title}** {conf_emoji}")
            lines.append(f"> {f.summary[:200]}...")
            if f.key_insights:
                lines.append(f"- Key insight: {f.key_insights[0]}")
    
    lines.append("\n## Recommended Actions")
    for i, action in enumerate(synthesis.recommended_actions, 1):
        lines.append(f"{i}. {action}")
    
    return "\n".join(lines)
