"""
Deep Research Skill - Multi-Step Research with Synthesis

Inspired by DeerFlow 2.0's Deep Research capability:
- Iterative research with follow-up queries
- Structured synthesis of findings
- Source attribution and confidence scoring
- Research memory for cross-session continuity

Integration with:
- WebSearchSkill for information gathering
- TieredMemorySystem for research history retention
- Verification system for source credibility
"""

import json
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Set
from datetime import datetime
from enum import Enum
import re


class ResearchPhase(Enum):
    """Phases of the deep research process."""
    INITIAL_QUERY = "initial_query"
    SOURCE_GATHERING = "source_gathering"
    SYNTHESIS = "synthesis"
    FOLLOW_UP = "follow_up"
    VERIFICATION = "verification"
    REPORT_GENERATION = "report_generation"


class SourceCredibility(Enum):
    """Credibility tiers for research sources."""
    HIGH = 0.9      # Academic journals, official docs, established institutions
    MEDIUM = 0.6    # Reputable news, industry publications, verified blogs
    LOW = 0.3       # Forums, social media, unverified sources
    UNKNOWN = 0.5   # Default for unclassified sources


@dataclass
class ResearchSource:
    """A single research source with metadata."""
    title: str
    url: str
    content: str
    credibility: SourceCredibility = SourceCredibility.UNKNOWN
    credibility_score: float = 0.5
    access_date: str = field(default_factory=lambda: datetime.now().isoformat())
    query_context: str = ""
    key_findings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "url": self.url,
            "content_preview": self.content[:500] + "..." if len(self.content) > 500 else self.content,
            "credibility": self.credibility.name,
            "credibility_score": self.credibility_score,
            "access_date": self.access_date,
            "query_context": self.query_context,
            "key_findings": self.key_findings
        }


@dataclass
class ResearchFinding:
    """A synthesized finding from multiple sources."""
    claim: str
    supporting_sources: List[str]  # URLs
    confidence: float  # 0.0-1.0 based on source credibility and consensus
    counter_evidence: List[str] = field(default_factory=list)
    uncertainty_factors: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "claim": self.claim,
            "supporting_sources": self.supporting_sources,
            "confidence": round(self.confidence, 2),
            "counter_evidence": self.counter_evidence,
            "uncertainty_factors": self.uncertainty_factors
        }


@dataclass
class ResearchReport:
    """Complete research report with synthesis."""
    query: str
    research_id: str
    timestamp: str
    findings: List[ResearchFinding]
    sources: List[ResearchSource]
    gaps_identified: List[str]
    follow_up_questions: List[str]
    overall_confidence: float
    methodology: str = "multi_step_web_research"
    total_iterations: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "query": self.query,
            "research_id": self.research_id,
            "timestamp": self.timestamp,
            "overall_confidence": round(self.overall_confidence, 2),
            "methodology": self.methodology,
            "total_iterations": self.total_iterations,
            "findings": [f.to_dict() for f in self.findings],
            "sources": [s.to_dict() for s in self.sources],
            "gaps_identified": self.gaps_identified,
            "follow_up_questions": self.follow_up_questions
        }
    
    def to_markdown(self) -> str:
        """Generate markdown report for human consumption."""
        md = f"# Research Report: {self.query}\n\n"
        md += f"**Research ID:** `{self.research_id}`\n\n"
        md += f"**Date:** {self.timestamp[:10]}\n\n"
        md += f"**Overall Confidence:** {round(self.overall_confidence * 100)}%\n\n"
        md += f"**Methodology:** {self.methodology} ({self.total_iterations} iterations)\n\n"
        
        md += "## Key Findings\n\n"
        for i, finding in enumerate(self.findings, 1):
            confidence_emoji = "🟢" if finding.confidence > 0.8 else "🟡" if finding.confidence > 0.5 else "🔴"
            md += f"### {i}. {confidence_emoji} {finding.claim}\n\n"
            md += f"**Confidence:** {round(finding.confidence * 100)}%\n\n"
            md += f"**Supporting Sources:** {', '.join(finding.supporting_sources[:3])}\n\n"
            if finding.counter_evidence:
                md += f"**Counter Evidence:** {', '.join(finding.counter_evidence)}\n\n"
            if finding.uncertainty_factors:
                md += f"**Uncertainties:** {', '.join(finding.uncertainty_factors)}\n\n"
        
        md += "## Sources\n\n"
        for source in self.sources:
            cred_emoji = "✅" if source.credibility == SourceCredibility.HIGH else "⚠️" if source.credibility == SourceCredibility.LOW else "📄"
            md += f"{cred_emoji} [{source.title}]({source.url}) - {source.credibility.name} ({round(source.credibility_score * 100)}%)\n\n"
        
        if self.gaps_identified:
            md += "\n## Knowledge Gaps\n\n"
            for gap in self.gaps_identified:
                md += f"- {gap}\n"
        
        if self.follow_up_questions:
            md += "\n## Follow-Up Questions\n\n"
            for q in self.follow_up_questions:
                md += f"- {q}\n"
        
        return md


class DeepResearchSkill:
    """
    Multi-step deep research capability for AGI agents.
    
    Performs iterative research with synthesis, source verification,
    and structured report generation.
    """
    
    # High-credibility domain patterns
    HIGH_CREDIBILITY_DOMAINS = [
        r'\.edu$', r'\.gov$', r'arxiv\.org', r'ieee\.org',
        r'nature\.com', r'science\.org', r'acm\.org',
        r'wikipedia\.org', r'wikidata\.org',
        r'docs\.python\.org', r'developer\.mozilla\.org',
        r'github\.com/.*\/.*\/blob',  # Code repositories
    ]
    
    # Low-credibility domain patterns
    LOW_CREDIBILITY_DOMAINS = [
        r'reddit\.com', r'twitter\.com', r'x\.com',
        r'facebook\.com', r'instagram\.com',
        r'tiktok\.com', r'youtube\.com/shorts',
        r'quora\.com', r'yahoo\.com/answers',
    ]
    
    def __init__(self, web_search_skill=None, memory_system=None):
        """
        Initialize deep research skill.
        
        Args:
            web_search_skill: WebSearchSkill instance for queries
            memory_system: TieredMemorySystem for research history
        """
        self.web_search = web_search_skill
        self.memory = memory_system
        self.research_history: List[ResearchReport] = []
        self.max_iterations = 3
        self.confidence_threshold = 0.7
        
    def _assess_source_credibility(self, url: str, title: str) -> tuple[SourceCredibility, float]:
        """Assess credibility of a source based on URL and title."""
        url_lower = url.lower()
        title_lower = title.lower()
        
        # Check high credibility patterns
        for pattern in self.HIGH_CREDIBILITY_DOMAINS:
            if re.search(pattern, url_lower):
                # Additional boost for academic/research content
                if any(kw in title_lower for kw in ['study', 'research', 'paper', 'analysis', 'survey']):
                    return SourceCredibility.HIGH, 0.95
                return SourceCredibility.HIGH, 0.85
        
        # Check low credibility patterns
        for pattern in self.LOW_CREDIBILITY_DOMAINS:
            if re.search(pattern, url_lower):
                return SourceCredibility.LOW, 0.3
        
        # Medium credibility for established publications
        medium_indicators = [
            'news', 'times', 'post', 'guardian', 'reuters',
            'bloomberg', 'forbes', 'techcrunch', 'verge',
            'medium.com', 'dev.to', 'substack'
        ]
        if any(ind in url_lower for ind in medium_indicators):
            return SourceCredibility.MEDIUM, 0.65
        
        return SourceCredibility.UNKNOWN, 0.5
    
    def _generate_follow_up_queries(self, current_sources: List[ResearchSource], 
                                    original_query: str) -> List[str]:
        """Generate follow-up queries based on gaps in current research."""
        follow_ups = []
        
        # Extract key entities from source titles
        entities = set()
        for source in current_sources:
            words = re.findall(r'\b[A-Z][a-z]+\b', source.title)
            entities.update(words)
        
        # Generate specific queries
        if len(current_sources) < 5:
            follow_ups.append(f"{original_query} official documentation")
            follow_ups.append(f"{original_query} research paper")
        
        # Check for temporal gaps
        current_years = set()
        for source in current_sources:
            years = re.findall(r'20[0-9]{2}', source.title + source.content)
            current_years.update(years)
        
        if '2026' not in current_years and '2025' not in current_years:
            follow_ups.append(f"{original_query} 2026")
        
        # Add entity-based queries
        for entity in list(entities)[:2]:
            follow_ups.append(f"{entity} {original_query}")
        
        return follow_ups[:3]  # Limit to 3 follow-ups
    
    def _synthesize_findings(self, sources: List[ResearchSource]) -> List[ResearchFinding]:
        """Synthesize findings from multiple sources."""
        findings = []
        
        # Group sources by common themes (simple keyword clustering)
        theme_keywords = {}
        for source in sources:
            content_lower = source.content.lower()
            # Extract key phrases (simplified)
            key_phrases = re.findall(r'\b[A-Z][a-z]+ (?:is|are|will|can|provides?)\b[^.]*\.', content_lower)
            for phrase in key_phrases[:3]:
                theme = phrase[:50]  # Truncate for theme key
                if theme not in theme_keywords:
                    theme_keywords[theme] = []
                theme_keywords[theme].append(source)
        
        # Create findings from clustered themes
        for theme, theme_sources in theme_keywords.items():
            if len(theme_sources) >= 2:  # Require multiple sources
                # Calculate confidence based on source credibility
                cred_scores = [s.credibility_score for s in theme_sources]
                avg_cred = sum(cred_scores) / len(cred_scores)
                
                # Boost confidence for consensus
                consensus_boost = min(0.1 * (len(theme_sources) - 1), 0.2)
                confidence = min(avg_cred + consensus_boost, 0.95)
                
                finding = ResearchFinding(
                    claim=theme.capitalize(),
                    supporting_sources=[s.url for s in theme_sources],
                    confidence=confidence
                )
                findings.append(finding)
        
        # Sort by confidence
        findings.sort(key=lambda f: f.confidence, reverse=True)
        return findings[:5]  # Top 5 findings
    
    def _identify_knowledge_gaps(self, query: str, sources: List[ResearchSource],
                                  findings: List[ResearchFinding]) -> List[str]:
        """Identify gaps in the research coverage."""
        gaps = []
        
        # Check query coverage
        query_terms = set(query.lower().split())
        covered_terms = set()
        for source in sources:
            covered_terms.update(source.content.lower().split())
        
        missing_terms = query_terms - covered_terms
        if missing_terms:
            gaps.append(f"Limited coverage of specific terms: {', '.join(list(missing_terms)[:3])}")
        
        # Check source diversity
        high_cred_count = sum(1 for s in sources if s.credibility == SourceCredibility.HIGH)
        if high_cred_count < 2:
            gaps.append("Limited high-credibility academic/official sources")
        
        # Check finding confidence
        low_conf_findings = [f for f in findings if f.confidence < 0.6]
        if low_conf_findings:
            gaps.append(f"{len(low_conf_findings)} findings have low confidence (< 60%)")
        
        # Check temporal coverage
        has_recent = any('2026' in s.title or '2025' in s.title for s in sources)
        if not has_recent:
            gaps.append("No recent (2025-2026) sources found")
        
        return gaps
    
    def research(self, query: str, 
                 iterations: int = 2,
                 store_in_memory: bool = True) -> ResearchReport:
        """
        Perform deep multi-step research on a query.
        
        Args:
            query: The research question or topic
            iterations: Number of research iterations (1-3)
            store_in_memory: Whether to store in tiered memory
            
        Returns:
            ResearchReport with synthesized findings
        """
        research_id = f"research_{int(time.time())}_{hash(query) % 10000}"
        all_sources: List[ResearchSource] = []
        
        # Phase 1: Initial query
        current_query = query
        queries_executed = [current_query]
        
        for iteration in range(min(iterations, self.max_iterations)):
            # Execute web search (mock or real)
            if self.web_search:
                try:
                    results = self.web_search.search(current_query, num_results=5)
                except Exception as e:
                    results = []
            else:
                # Mock results for testing
                results = self._mock_search(current_query)
            
            # Process results into sources
            for result in results:
                credibility, score = self._assess_source_credibility(
                    result.get('url', ''),
                    result.get('title', '')
                )
                
                source = ResearchSource(
                    title=result.get('title', 'Untitled'),
                    url=result.get('url', ''),
                    content=result.get('snippet', result.get('content', '')),
                    credibility=credibility,
                    credibility_score=score,
                    query_context=current_query,
                    key_findings=self._extract_key_findings(result.get('content', ''))
                )
                all_sources.append(source)
            
            # Generate follow-up for next iteration
            if iteration < iterations - 1:
                follow_ups = self._generate_follow_up_queries(all_sources, query)
                if follow_ups:
                    current_query = follow_ups[0]
                    queries_executed.append(current_query)
        
        # Phase 2: Synthesis
        findings = self._synthesize_findings(all_sources)
        
        # Phase 3: Gap analysis
        gaps = self._identify_knowledge_gaps(query, all_sources, findings)
        
        # Phase 4: Generate follow-up questions
        follow_up_questions = self._generate_follow_up_queries(all_sources, query)
        
        # Calculate overall confidence
        if findings:
            overall_confidence = sum(f.confidence for f in findings) / len(findings)
        else:
            overall_confidence = 0.0
        
        # Create report
        report = ResearchReport(
            query=query,
            research_id=research_id,
            timestamp=datetime.now().isoformat(),
            findings=findings,
            sources=all_sources,
            gaps_identified=gaps,
            follow_up_questions=follow_up_questions,
            overall_confidence=overall_confidence,
            total_iterations=len(queries_executed)
        )
        
        # Store in memory if requested
        if store_in_memory and self.memory:
            self._store_research_in_memory(report)
        
        # Add to local history
        self.research_history.append(report)
        
        return report
    
    def _extract_key_findings(self, content: str) -> List[str]:
        """Extract key findings from content."""
        findings = []
        sentences = re.split(r'[.!?]+', content)
        
        for sent in sentences:
            sent = sent.strip()
            # Look for declarative statements with metrics or key terms
            if len(sent) > 30 and len(sent) < 200:
                if any(kw in sent.lower() for kw in [
                    'is', 'are', 'provides', 'enables', 'allows',
                    'achieves', 'demonstrates', 'shows', 'found',
                    'percent', '%', '2026', '2025', 'study'
                ]):
                    findings.append(sent)
        
        return findings[:3]
    
    def _store_research_in_memory(self, report: ResearchReport):
        """Store research report in tiered memory system."""
        try:
            # Import here to avoid circular dependency
            from core.tiered_memory import MemoryTier
            
            # Store as L1 (working memory) - recent research
            self.memory.store(
                content=f"Research: {report.query} (confidence: {report.overall_confidence:.0%})",
                tier=MemoryTier.L1_WORKING,
                importance_score=report.overall_confidence,
                tags={"research", "deep_research", f"query_{report.research_id}"}
            )
            
            # If high confidence, also store key findings in L2
            if report.overall_confidence > 0.7:
                for finding in report.findings[:2]:
                    self.memory.store(
                        content=finding.claim,
                        tier=MemoryTier.L2_ARCHIVAL,
                        importance_score=finding.confidence,
                        tags={"research_finding", "knowledge", f"topic_{report.research_id}"}
                    )
        except Exception as e:
            # Silent fail - memory storage is optional
            pass
    
    def _mock_search(self, query: str) -> List[Dict]:
        """Generate mock search results for testing."""
        mock_results = {
            "agi": [
                {"title": "AGI Timeline Predictions 2026 - LifeArchitect.ai",
                 "url": "https://lifearchitect.ai/agi/",
                 "snippet": "Dario Amodei predicts powerful AI by 2026. AGI research shows rapid progress in reasoning capabilities."},
                {"title": "The State of AGI Research - arXiv 2026",
                 "url": "https://arxiv.org/abs/2603.07896",
                 "snippet": "SMGI: A Structural Theory of General Artificial Intelligence proposes four obligations for AGI systems."},
            ],
            "ai agents": [
                {"title": "AI Agent Frameworks Comparison 2026 - Intuz",
                 "url": "https://www.intuz.com/blog/top-5-ai-agent-frameworks-2025",
                 "snippet": "LangGraph, CrewAI, and AutoGen lead the agent framework landscape in 2026 with stateful workflows."},
                {"title": "DeerFlow 2.0 - GitHub Trending",
                 "url": "https://github.com/xiaonancs/deerflow",
                 "snippet": "Super agent harness coordinating sub-agents, memory, and sandboxes for long-horizon tasks."},
            ],
            "mcp": [
                {"title": "Model Context Protocol Specification",
                 "url": "https://modelcontextprotocol.io",
                 "snippet": "MCP enables seamless integration between AI systems and data sources through standardized protocol."},
            ]
        }
        
        # Find matching mock results
        query_lower = query.lower()
        for key, results in mock_results.items():
            if key in query_lower:
                return results
        
        # Default mock result
        return [
            {"title": f"Research on: {query}",
             "url": "https://example.com/research",
             "snippet": f"This is a mock result for query: {query}. In production, this would contain real search results."}
        ]
    
    def get_research_history(self, 
                            query_filter: Optional[str] = None,
                            min_confidence: float = 0.0) -> List[ResearchReport]:
        """Get filtered research history."""
        reports = self.research_history
        
        if query_filter:
            reports = [r for r in reports if query_filter.lower() in r.query.lower()]
        
        if min_confidence > 0:
            reports = [r for r in reports if r.overall_confidence >= min_confidence]
        
        return reports
    
    def compare_research(self, query1: str, query2: str) -> Dict:
        """Compare research results on two related queries."""
        report1 = self.research(query1, iterations=1, store_in_memory=False)
        report2 = self.research(query2, iterations=1, store_in_memory=False)
        
        # Find overlapping sources
        urls1 = {s.url for s in report1.sources}
        urls2 = {s.url for s in report2.sources}
        overlap = urls1 & urls2
        
        # Compare confidence
        confidence_diff = report1.overall_confidence - report2.overall_confidence
        
        return {
            "query1": query1,
            "query2": query2,
            "confidence1": report1.overall_confidence,
            "confidence2": report2.overall_confidence,
            "confidence_difference": confidence_diff,
            "shared_sources": len(overlap),
            "total_sources_1": len(report1.sources),
            "total_sources_2": len(report2.sources),
            "report1_findings": len(report1.findings),
            "report2_findings": len(report2.findings)
        }


# Factory function for easy instantiation
def create_deep_research_skill(web_search_skill=None, memory_system=None) -> DeepResearchSkill:
    """Create a configured DeepResearchSkill instance."""
    return DeepResearchSkill(
        web_search_skill=web_search_skill,
        memory_system=memory_system
    )
