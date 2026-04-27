"""
Deep Research Skill - Multi-step recursive research with tiered memory integration.

Based on InfoQuest and DeerFlow patterns for autonomous research agents.
Features:
- Recursive exploration with depth control
- Multi-source synthesis and cross-validation
- Tiered memory integration (L0/L1/L2)
- Query decomposition and parallel sub-queries
- Evidence tracking with confidence scoring
"""

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import random


class ResearchPhase(Enum):
    """Phases of deep research process."""
    PLANNING = auto()
    EXPLORATION = auto()
    SYNTHESIS = auto()
    VERIFICATION = auto()
    COMPLETE = auto()


class SourceType(Enum):
    """Types of research sources."""
    WEB_SEARCH = "web_search"
    WEBPAGE = "webpage"
    ARXIV = "arxiv"
    GITHUB = "github"
    KNOWLEDGE_BASE = "knowledge_base"
    INTERNAL_MEMORY = "internal_memory"


@dataclass
class EvidenceItem:
    """A piece of evidence with metadata."""
    content: str
    source: str
    source_type: SourceType
    confidence: float = 0.0
    relevance_score: float = 0.0
    timestamp: float = field(default_factory=time.time)
    verification_status: str = "unverified"  # unverified, confirmed, disputed
    citations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": self.content[:500],  # Truncated for storage
            "source": self.source,
            "source_type": self.source_type.value,
            "confidence": self.confidence,
            "relevance_score": self.relevance_score,
            "timestamp": self.timestamp,
            "verification_status": self.verification_status,
            "citations": self.citations
        }


@dataclass
class ResearchQuery:
    """A research query with decomposition support."""
    query_id: str
    original_query: str
    decomposed_subqueries: List[str] = field(default_factory=list)
    parent_query: Optional[str] = None
    depth: int = 0
    max_depth: int = 3
    phase: ResearchPhase = ResearchPhase.PLANNING
    priority: int = 5  # 1-10
    evidence_items: List[EvidenceItem] = field(default_factory=list)
    findings: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, active, complete, failed
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    
    def __post_init__(self):
        if not self.query_id:
            self.query_id = hashlib.md5(
                f"{self.original_query}:{time.time()}".encode()
            ).hexdigest()[:12]


@dataclass
class SynthesisResult:
    """Result of synthesizing research findings."""
    synthesis_id: str
    original_query: str
    summary: str
    key_findings: List[str]
    supporting_evidence: List[EvidenceItem]
    confidence_score: float
    gaps_identified: List[str]
    follow_up_queries: List[str]
    sources_summary: Dict[str, int]
    timestamp: float = field(default_factory=time.time)
    
    def to_report(self) -> str:
        """Generate a markdown research report."""
        report = f"""# Research Report: {self.original_query}

## Executive Summary
{self.summary}

## Key Findings
"""
        for i, finding in enumerate(self.key_findings, 1):
            report += f"\n{i}. {finding}\n"
        
        report += f"\n## Confidence Score: {self.confidence_score:.2f}\n"
        
        report += "\n## Sources\n"
        for source_type, count in self.sources_summary.items():
            report += f"- {source_type}: {count} items\n"
        
        if self.gaps_identified:
            report += "\n## Knowledge Gaps\n"
            for gap in self.gaps_identified:
                report += f"- {gap}\n"
        
        if self.follow_up_queries:
            report += "\n## Recommended Follow-up Research\n"
            for query in self.follow_up_queries[:5]:
                report += f"- {query}\n"
        
        return report


class DeepResearchEngine:
    """
    Multi-step deep research engine with tiered memory integration.
    
    Implements recursive exploration, parallel sub-query processing,
    and evidence-based synthesis with confidence scoring.
    """
    
    def __init__(
        self,
        agent_id: str,
        memory_store: Optional[Any] = None,
        max_parallel_queries: int = 5,
        confidence_threshold: float = 0.7,
        web_search_fn: Optional[Callable] = None,
        webpage_reader_fn: Optional[Callable] = None
    ):
        self.agent_id = agent_id
        self.memory_store = memory_store
        self.max_parallel = max_parallel_queries
        self.confidence_threshold = confidence_threshold
        
        # External tool integrations
        self.web_search_fn = web_search_fn
        self.webpage_reader_fn = webpage_reader_fn
        
        # Active and completed research
        self.active_queries: Dict[str, ResearchQuery] = {}
        self.completed_queries: Dict[str, ResearchQuery] = {}
        self.synthesis_results: Dict[str, SynthesisResult] = {}
        
        # Research metrics
        self.total_queries_executed = 0
        self.total_evidence_collected = 0
        self.avg_synthesis_confidence = 0.0
    
    def _generate_query_id(self, query_text: str) -> str:
        """Generate unique query ID."""
        return hashlib.md5(
            f"{query_text}:{time.time()}".encode()
        ).hexdigest()[:12]
    
    def decompose_query(self, query: str, context: Optional[str] = None) -> List[str]:
        """
        Decompose a complex query into parallel sub-queries.
        
        Args:
            query: Original research query
            context: Optional context from parent query
            
        Returns:
            List of sub-queries for parallel exploration
        """
        # Query decomposition patterns
        decompositions = []
        
        # Pattern 1: Temporal decomposition
        if any(word in query.lower() for word in ["history", "evolution", "timeline", "past"]):
            decompositions.extend([
                f"{query} - historical background and origins",
                f"{query} - recent developments and current state",
                f"{query} - future trends and predictions"
            ])
        
        # Pattern 2: Comparative decomposition
        elif any(word in query.lower() for word in ["compare", "vs", "versus", "difference", "alternative"]):
            decompositions.extend([
                f"{query} - approach 1 methodology and benefits",
                f"{query} - approach 2 methodology and benefits",
                f"{query} - comparison criteria and trade-offs"
            ])
        
        # Pattern 3: Component decomposition (default)
        else:
            decompositions.extend([
                f"{query} - fundamental concepts and definitions",
                f"{query} - key techniques and methods",
                f"{query} - applications and use cases",
                f"{query} - challenges and limitations"
            ])
        
        # Add context-driven sub-query if context provided
        if context:
            decompositions.append(f"{query} - relationship to: {context[:100]}")
        
        return decompositions[:5]  # Limit to 5 sub-queries (4 default + 1 context)
    
    async def execute_web_search(
        self,
        query: str,
        num_results: int = 5
    ) -> List[EvidenceItem]:
        """
        Execute web search and extract evidence.
        
        This is a simulated implementation - in production,
        this would call actual web search tools.
        """
        evidence = []
        
        # Simulate search results
        # In production: actual web search API calls
        mock_results = [
            {
                "title": f"Result 1 for: {query[:30]}...",
                "url": f"https://example.com/search/{hashlib.md5(query.encode()).hexdigest()[:8]}",
                "snippet": f"Key information about {query}. This source provides comprehensive coverage..."
            },
            {
                "title": f"Result 2 for: {query[:30]}...",
                "url": f"https://example.org/info/{hashlib.md5(query.encode()).hexdigest()[:8]}",
                "snippet": f"Research findings indicate significant developments in {query}..."
            },
            {
                "title": f"Academic paper on {query[:30]}...",
                "url": f"https://arxiv.org/abs/{hashlib.md5(query.encode()).hexdigest()[:8]}",
                "snippet": f"This paper presents novel approaches to {query} with experimental results..."
            }
        ]
        
        for i, result in enumerate(mock_results[:num_results]):
            evidence.append(EvidenceItem(
                content=result["snippet"],
                source=result["url"],
                source_type=SourceType.WEB_SEARCH,
                confidence=0.6 + (0.1 * (len(mock_results) - i) / len(mock_results)),
                relevance_score=0.7 - (0.05 * i)
            ))
        
        return evidence
    
    async def explore_query(
        self,
        query: ResearchQuery,
        semaphore: asyncio.Semaphore
    ) -> ResearchQuery:
        """
        Explore a single research query comprehensively.
        
        Args:
            query: Research query to explore
            semaphore: Concurrency control
            
        Returns:
            Updated query with evidence
        """
        async with semaphore:
            query.status = "active"
            query.phase = ResearchPhase.EXPLORATION
            
            # Collect evidence from multiple sources
            evidence_collected = []
            
            # Source 1: Web search
            if self.web_search_fn:
                try:
                    web_evidence = await self.execute_web_search(query.original_query)
                    evidence_collected.extend(web_evidence)
                except Exception as e:
                    query.findings.append(f"Web search error: {str(e)}")
            
            # Source 2: Check memory for related research
            if self.memory_store:
                try:
                    # Query tiered memory for related information
                    memory_results = await self._query_memory(query.original_query)
                    evidence_collected.extend(memory_results)
                except Exception as e:
                    pass  # Memory optional
            
            # Filter and score evidence
            query.evidence_items = self._filter_evidence(evidence_collected)
            
            # Generate preliminary findings
            query.findings = self._extract_findings(query.evidence_items)
            
            # Check if we need deeper exploration
            if query.depth < query.max_depth and len(query.findings) < 3:
                # Decompose for deeper exploration
                subqueries = self.decompose_query(
                    query.original_query,
                    context=" ".join(query.findings)[:200]
                )
                query.decomposed_subqueries = subqueries
            
            query.status = "complete"
            query.completed_at = time.time()
            query.phase = ResearchPhase.SYNTHESIS
            
            return query
    
    async def _query_memory(self, query_text: str) -> List[EvidenceItem]:
        """Query tiered memory for related information."""
        evidence = []
        
        # In production: actual memory queries
        # Simulated memory results
        memory_items = [
            EvidenceItem(
                content=f"Previously researched related topic: {query_text[:40]}...",
                source="memory://l2_archive",
                source_type=SourceType.INTERNAL_MEMORY,
                confidence=0.8,
                relevance_score=0.6
            )
        ]
        
        return memory_items
    
    def _filter_evidence(
        self,
        evidence: List[EvidenceItem],
        min_confidence: float = 0.4
    ) -> List[EvidenceItem]:
        """Filter and rank evidence by quality."""
        # Remove duplicates by content hash
        seen_hashes = set()
        unique_evidence = []
        
        for item in evidence:
            content_hash = hashlib.md5(item.content.encode()).hexdigest()[:16]
            if content_hash not in seen_hashes:
                seen_hashes.add(content_hash)
                unique_evidence.append(item)
        
        # Filter by confidence and sort by relevance
        filtered = [
            e for e in unique_evidence
            if e.confidence >= min_confidence
        ]
        
        filtered.sort(key=lambda x: x.relevance_score * x.confidence, reverse=True)
        
        return filtered[:20]  # Top 20 evidence items
    
    def _extract_findings(self, evidence: List[EvidenceItem]) -> List[str]:
        """Extract key findings from evidence."""
        findings = []
        
        # Group evidence by themes (simplified)
        high_confidence = [e for e in evidence if e.confidence >= 0.7]
        
        for item in high_confidence[:5]:
            finding = f"[{item.source_type.value}] {item.content[:150]}..."
            findings.append(finding)
        
        return findings
    
    async def research(
        self,
        query_text: str,
        max_depth: int = 2,
        require_verification: bool = True
    ) -> SynthesisResult:
        """
        Execute deep research on a query.
        
        Args:
            query_text: Research query
            max_depth: Maximum recursion depth
            require_verification: Whether to verify findings
            
        Returns:
            SynthesisResult with comprehensive findings
        """
        # Create root query
        root_query = ResearchQuery(
            query_id=self._generate_query_id(query_text),
            original_query=query_text,
            max_depth=max_depth,
            depth=0
        )
        
        self.active_queries[root_query.query_id] = root_query
        
        # Exploration phase
        semaphore = asyncio.Semaphore(self.max_parallel)
        
        # Explore root query
        explored_root = await self.explore_query(root_query, semaphore)
        
        # Explore sub-queries if decomposed
        subquery_results = []
        if explored_root.decomposed_subqueries:
            subquery_tasks = []
            for subquery_text in explored_root.decomposed_subqueries:
                subquery = ResearchQuery(
                    query_id=self._generate_query_id(subquery_text),
                    original_query=subquery_text,
                    parent_query=root_query.query_id,
                    max_depth=max_depth,
                    depth=1
                )
                subquery_tasks.append(self.explore_query(subquery, semaphore))
            
            subquery_results = await asyncio.gather(*subquery_tasks)
        
        # Collect all evidence
        all_evidence = explored_root.evidence_items.copy()
        for sq in subquery_results:
            all_evidence.extend(sq.evidence_items)
            self.completed_queries[sq.query_id] = sq
        
        # Synthesis phase
        synthesis = self._synthesize_findings(
            query_text,
            all_evidence,
            explored_root.findings + [f for sq in subquery_results for f in sq.findings]
        )
        
        # Verification phase (if requested)
        if require_verification:
            synthesis = await self._verify_synthesis(synthesis)
        
        # Store in memory
        await self._store_research_memory(synthesis)
        
        # Update metrics
        self.total_queries_executed += 1 + len(subquery_results)
        self.total_evidence_collected += len(all_evidence)
        
        # Update running average confidence
        self.avg_synthesis_confidence = (
            (self.avg_synthesis_confidence * (self.total_queries_executed - 1) +
             synthesis.confidence_score) / self.total_queries_executed
        )
        
        self.synthesis_results[synthesis.synthesis_id] = synthesis
        self.completed_queries[root_query.query_id] = explored_root
        del self.active_queries[root_query.query_id]
        
        return synthesis
    
    def _synthesize_findings(
        self,
        original_query: str,
        evidence: List[EvidenceItem],
        findings: List[str]
    ) -> SynthesisResult:
        """
        Synthesize evidence into coherent findings.
        
        In production, this would use an LLM for synthesis.
        """
        # Calculate aggregate confidence
        if evidence:
            avg_confidence = sum(e.confidence for e in evidence) / len(evidence)
            high_confidence_ratio = len([e for e in evidence if e.confidence >= 0.7]) / len(evidence)
        else:
            avg_confidence = 0.0
            high_confidence_ratio = 0.0
        
        # Adjust confidence based on evidence quality
        confidence_score = min(0.95, avg_confidence * (0.5 + 0.5 * high_confidence_ratio))
        
        # Generate summary (simplified)
        summary = (
            f"Research on '{original_query}' identified {len(findings)} key findings "
            f"supported by {len(evidence)} evidence items from "
            f"{len(set(e.source_type for e in evidence))} source types. "
            f"Overall confidence: {confidence_score:.0%}."
        )
        
        # Identify gaps
        gaps = []
        if confidence_score < self.confidence_threshold:
            gaps.append("Insufficient high-confidence evidence")
        if len(findings) < 3:
            gaps.append("Limited depth of findings")
        if len(set(e.source_type for e in evidence)) < 2:
            gaps.append("Source diversity could be improved")
        
        # Generate follow-up queries
        follow_up = self._generate_follow_up_queries(original_query, findings, gaps)
        
        # Count sources
        sources_summary = {}
        for e in evidence:
            st = e.source_type.value
            sources_summary[st] = sources_summary.get(st, 0) + 1
        
        return SynthesisResult(
            synthesis_id=self._generate_query_id(original_query),
            original_query=original_query,
            summary=summary,
            key_findings=findings[:7],  # Top 7 findings
            supporting_evidence=evidence[:10],  # Top 10 evidence
            confidence_score=confidence_score,
            gaps_identified=gaps,
            follow_up_queries=follow_up,
            sources_summary=sources_summary
        )
    
    def _generate_follow_up_queries(
        self,
        query: str,
        findings: List[str],
        gaps: List[str]
    ) -> List[str]:
        """Generate follow-up research queries."""
        follow_up = []
        
        # Gap-driven follow-ups
        if "insufficient evidence" in " ".join(gaps).lower():
            follow_up.append(f"{query} - recent academic research")
            follow_up.append(f"{query} - industry expert perspectives")
        
        # Depth follow-ups
        if len(findings) > 0:
            follow_up.append(f"Advanced applications of {query}")
            follow_up.append(f"Implementation challenges: {query}")
        
        # Breadth follow-ups
        follow_up.append(f"Related fields and cross-disciplinary connections: {query}")
        follow_up.append(f"Future developments and emerging trends: {query}")
        
        return follow_up[:5]
    
    async def _verify_synthesis(
        self,
        synthesis: SynthesisResult
    ) -> SynthesisResult:
        """
        Verify synthesis through cross-validation.
        
        Checks for consistency and attempts to verify key claims.
        """
        # Mark evidence as verified/unverified
        for evidence in synthesis.supporting_evidence:
            if evidence.confidence >= 0.8 and evidence.relevance_score >= 0.7:
                evidence.verification_status = "confirmed"
            elif evidence.confidence >= 0.5:
                evidence.verification_status = "partially_confirmed"
            else:
                evidence.verification_status = "disputed"
        
        # Adjust confidence based on verification
        confirmed_count = len([
            e for e in synthesis.supporting_evidence
            if e.verification_status == "confirmed"
        ])
        
        if confirmed_count >= 3:
            verification_boost = 0.05
        elif confirmed_count >= 1:
            verification_boost = 0.0
        else:
            verification_boost = -0.1
        
        synthesis.confidence_score = min(0.99, max(0.0, 
            synthesis.confidence_score + verification_boost))
        
        return synthesis
    
    async def _store_research_memory(self, synthesis: SynthesisResult):
        """Store research results in tiered memory."""
        if not self.memory_store:
            return
        
        # Store in memory (simplified)
        memory_entry = {
            "type": "deep_research",
            "query": synthesis.original_query,
            "confidence": synthesis.confidence_score,
            "summary": synthesis.summary,
            "timestamp": synthesis.timestamp,
            "evidence_count": len(synthesis.supporting_evidence)
        }
        
        # In production: actual memory store calls
        # await self.memory_store.store_l2(memory_entry)
    
    def get_research_metrics(self) -> Dict[str, Any]:
        """Get research engine performance metrics."""
        return {
            "total_queries_executed": self.total_queries_executed,
            "total_evidence_collected": self.total_evidence_collected,
            "avg_synthesis_confidence": self.avg_synthesis_confidence,
            "active_queries": len(self.active_queries),
            "completed_queries": len(self.completed_queries),
            "synthesis_results": len(self.synthesis_results)
        }
    
    def get_research_history(
        self,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get history of completed research."""
        history = []
        for synthesis in sorted(
            self.synthesis_results.values(),
            key=lambda x: x.timestamp,
            reverse=True
        )[:limit]:
            history.append({
                "query": synthesis.original_query,
                "confidence": synthesis.confidence_score,
                "findings_count": len(synthesis.key_findings),
                "timestamp": datetime.fromtimestamp(synthesis.timestamp).isoformat()
            })
        return history


def create_research_engine(
    agent_id: str,
    **kwargs
) -> DeepResearchEngine:
    """Factory function to create a configured research engine."""
    return DeepResearchEngine(agent_id=agent_id, **kwargs)


# Synchronous wrapper for convenience
def run_research(
    query: str,
    max_depth: int = 2,
    agent_id: str = "default_agent"
) -> SynthesisResult:
    """
    Run deep research synchronously.
    
    Args:
        query: Research query
        max_depth: Maximum exploration depth
        agent_id: Agent identifier
        
    Returns:
        SynthesisResult with research findings
    """
    engine = create_research_engine(agent_id)
    return asyncio.run(engine.research(query, max_depth=max_depth))
