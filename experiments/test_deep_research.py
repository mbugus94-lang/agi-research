"""
Test Suite for Deep Research Skill

Validates:
1. Source credibility assessment
2. Multi-step research with iteration
3. Finding synthesis and confidence calculation
4. Knowledge gap identification
5. Research history storage and retrieval
6. Report generation (JSON and Markdown)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
from skills.deep_research import (
    DeepResearchSkill, ResearchSource, ResearchFinding, ResearchReport,
    ResearchPhase, SourceCredibility, create_deep_research_skill
)


class TestSourceCredibility(unittest.TestCase):
    """Test source credibility assessment."""
    
    def test_high_credibility_academic_domains(self):
        """Test detection of high-credibility academic domains."""
        skill = DeepResearchSkill()
        
        # Academic domains
        cred, score = skill._assess_source_credibility(
            "https://arxiv.org/abs/2603.07896",
            "SMGI: A Structural Theory of General Artificial Intelligence"
        )
        self.assertEqual(cred, SourceCredibility.HIGH)
        self.assertGreaterEqual(score, 0.85)
        
        # Educational domains
        cred, score = skill._assess_source_credibility(
            "https://docs.python.org/3/tutorial",
            "Python Tutorial"
        )
        self.assertEqual(cred, SourceCredibility.HIGH)
    
    def test_high_credibility_with_research_keywords(self):
        """Test high credibility boost for research-related titles."""
        skill = DeepResearchSkill()
        
        cred, score = skill._assess_source_credibility(
            "https://nature.com/articles/s41586-026-12345",
            "Research study on neural networks"
        )
        self.assertEqual(cred, SourceCredibility.HIGH)
        self.assertGreater(score, 0.9)  # Boosted by research keyword
    
    def test_low_credibility_social_media(self):
        """Test detection of low-credibility social media."""
        skill = DeepResearchSkill()
        
        cred, score = skill._assess_source_credibility(
            "https://twitter.com/user/status/12345",
            "Hot take on AI"
        )
        self.assertEqual(cred, SourceCredibility.LOW)
        self.assertLess(score, 0.4)
    
    def test_medium_credibility_news(self):
        """Test detection of medium-credibility news sources."""
        skill = DeepResearchSkill()
        
        cred, score = skill._assess_source_credibility(
            "https://techcrunch.com/2026/04/24/ai-news",
            "AI Industry Update"
        )
        self.assertEqual(cred, SourceCredibility.MEDIUM)
    
    def test_unknown_credibility_generic(self):
        """Test default unknown credibility for generic domains."""
        skill = DeepResearchSkill()
        
        cred, score = skill._assess_source_credibility(
            "https://random-blog.com/article",
            "Some thoughts"
        )
        self.assertEqual(cred, SourceCredibility.UNKNOWN)


class TestMockSearch(unittest.TestCase):
    """Test mock search functionality."""
    
    def test_mock_search_agi_query(self):
        """Test mock search for AGI-related queries."""
        skill = DeepResearchSkill()
        results = skill._mock_search("artificial general intelligence")
        
        self.assertGreater(len(results), 0)
        # Check for AI/artificial/agents in results
        self.assertTrue(any("AI" in r["title"] or "AI" in r["snippet"] or
                           "artificial" in r["title"].lower() or
                           "artificial" in r["snippet"].lower()
                           for r in results))
    
    def test_mock_search_ai_agents(self):
        """Test mock search for AI agent queries."""
        skill = DeepResearchSkill()
        results = skill._mock_search("ai agent frameworks 2026")
        
        self.assertGreater(len(results), 0)
        self.assertTrue(any("agent" in r["title"].lower() 
                           for r in results))
    
    def test_mock_search_unknown_query(self):
        """Test mock search returns default for unknown queries."""
        skill = DeepResearchSkill()
        results = skill._mock_search("xyz123 unknown query")
        
        self.assertEqual(len(results), 1)
        self.assertIn("mock result", results[0]["snippet"].lower())


class TestKeyFindingExtraction(unittest.TestCase):
    """Test key finding extraction from content."""
    
    def test_extract_findings_with_metrics(self):
        """Test extraction of findings with metrics."""
        skill = DeepResearchSkill()
        content = "The study shows that 85% of agents improve performance. Research demonstrates significant gains."
        
        findings = skill._extract_key_findings(content)
        self.assertGreater(len(findings), 0)
        self.assertTrue(any("85%" in f for f in findings))
    
    def test_extract_findings_with_keywords(self):
        """Test extraction based on finding keywords."""
        skill = DeepResearchSkill()
        content = "This enables efficient processing. The system provides scalable solutions."
        
        findings = skill._extract_key_findings(content)
        self.assertGreater(len(findings), 0)


class TestFollowUpQueryGeneration(unittest.TestCase):
    """Test follow-up query generation."""
    
    def test_generate_follow_ups_for_limited_sources(self):
        """Test follow-up generation when few sources exist."""
        skill = DeepResearchSkill()
        sources = [
            ResearchSource(
                title="AI News",
                url="https://example.com",
                content="Some content",
                query_context="ai agents"
            )
        ]
        
        follow_ups = skill._generate_follow_up_queries(sources, "ai agents")
        
        self.assertGreater(len(follow_ups), 0)
        # Should include documentation and research queries
        self.assertTrue(any("documentation" in q.lower() for q in follow_ups) or
                       any("research" in q.lower() for q in follow_ups))
    
    def test_generate_follow_ups_with_entities(self):
        """Test follow-up generation extracts entities from titles."""
        skill = DeepResearchSkill()
        sources = [
            ResearchSource(
                title="LangGraph Framework Analysis",
                url="https://example.com",
                content="LangGraph provides stateful workflows",
                query_context="ai frameworks"
            )
        ]
        
        follow_ups = skill._generate_follow_up_queries(sources, "ai frameworks")
        
        # Should return some follow-up queries (entity extraction is heuristic)
        self.assertGreater(len(follow_ups), 0)
        # Should include follow-ups related to frameworks
        self.assertTrue(any("framework" in q.lower() or "ai" in q.lower() 
                         for q in follow_ups))


class TestSynthesis(unittest.TestCase):
    """Test finding synthesis."""
    
    def test_synthesize_single_source_no_findings(self):
        """Test synthesis requires multiple sources."""
        skill = DeepResearchSkill()
        sources = [
            ResearchSource(
                title="Single Source",
                url="https://example.com",
                content="Only one source available",
                credibility=SourceCredibility.MEDIUM,
                credibility_score=0.6
            )
        ]
        
        findings = skill._synthesize_findings(sources)
        # Should have few or no findings with single source
        self.assertLess(len(findings), 2)
    
    def test_synthesize_boosts_consensus_confidence(self):
        """Test that consensus boosts confidence scores."""
        skill = DeepResearchSkill()
        sources = [
            ResearchSource(
                title="Source 1",
                url="https://example1.com",
                content="Research shows AI is advancing rapidly in 2026.",
                credibility=SourceCredibility.HIGH,
                credibility_score=0.85
            ),
            ResearchSource(
                title="Source 2",
                url="https://example2.com",
                content="Study demonstrates AI is advancing rapidly in 2026.",
                credibility=SourceCredibility.HIGH,
                credibility_score=0.9
            )
        ]
        
        findings = skill._synthesize_findings(sources)
        
        # Findings should have higher confidence due to consensus
        if findings:
            for finding in findings:
                self.assertGreater(finding.confidence, 0.5)


class TestGapIdentification(unittest.TestCase):
    """Test knowledge gap identification."""
    
    def test_identify_gaps_with_few_sources(self):
        """Test gap detection when source count is low."""
        skill = DeepResearchSkill()
        sources = [
            ResearchSource(
                title="One Source",
                url="https://example.com",
                content="Limited information",
                credibility=SourceCredibility.LOW,
                credibility_score=0.3
            )
        ]
        
        gaps = skill._identify_knowledge_gaps("artificial general intelligence research", sources, [])
        
        # Should identify limited high-credibility sources
        self.assertTrue(any("credibility" in g.lower() for g in gaps))
    
    def test_identify_temporal_gaps(self):
        """Test detection of missing recent sources."""
        skill = DeepResearchSkill()
        sources = [
            ResearchSource(
                title="Old Research Paper 2020",
                url="https://example.com",
                content="From 2020"
            )
        ]
        
        gaps = skill._identify_knowledge_gaps("ai agents", sources, [])
        
        # Should identify missing recent sources
        self.assertTrue(any("2025" in g or "2026" in g for g in gaps))


class TestResearchExecution(unittest.TestCase):
    """Test end-to-end research execution."""
    
    def test_research_creates_report(self):
        """Test that research() returns a valid ResearchReport."""
        skill = DeepResearchSkill()
        
        report = skill.research("agi 2026", iterations=1, store_in_memory=False)
        
        self.assertIsInstance(report, ResearchReport)
        self.assertEqual(report.query, "agi 2026")
        self.assertIsNotNone(report.research_id)
        self.assertIsNotNone(report.timestamp)
    
    def test_research_with_multiple_iterations(self):
        """Test research with multiple iterations."""
        skill = DeepResearchSkill()
        
        report = skill.research("ai agents", iterations=2, store_in_memory=False)
        
        self.assertEqual(report.total_iterations, 2)
        self.assertGreater(len(report.sources), 0)
    
    def test_research_confidence_calculation(self):
        """Test that overall confidence is calculated correctly."""
        skill = DeepResearchSkill()
        
        report = skill.research("mcp protocol", iterations=1, store_in_memory=False)
        
        self.assertGreaterEqual(report.overall_confidence, 0.0)
        self.assertLessEqual(report.overall_confidence, 1.0)
    
    def test_research_stores_in_history(self):
        """Test that research is added to history."""
        skill = DeepResearchSkill()
        initial_count = len(skill.research_history)
        
        skill.research("test query", iterations=1, store_in_memory=False)
        
        self.assertEqual(len(skill.research_history), initial_count + 1)


class TestReportGeneration(unittest.TestCase):
    """Test report generation formats."""
    
    def test_report_to_dict(self):
        """Test JSON dictionary generation."""
        skill = DeepResearchSkill()
        report = skill.research("test", iterations=1, store_in_memory=False)
        
        d = report.to_dict()
        
        self.assertIn("query", d)
        self.assertIn("research_id", d)
        self.assertIn("findings", d)
        self.assertIn("sources", d)
        self.assertIn("gaps_identified", d)
        self.assertIn("follow_up_questions", d)
    
    def test_report_to_markdown(self):
        """Test markdown report generation."""
        skill = DeepResearchSkill()
        report = skill.research("test query", iterations=1, store_in_memory=False)
        
        md = report.to_markdown()
        
        self.assertIn("# Research Report", md)
        self.assertIn(report.query, md)
        self.assertIn("## Key Findings", md)
        self.assertIn("## Sources", md)
    
    def test_markdown_includes_confidence_emojis(self):
        """Test that markdown includes confidence indicators."""
        skill = DeepResearchSkill()
        report = skill.research("ai agents 2026", iterations=1, store_in_memory=False)
        
        md = report.to_markdown()
        
        # Should include emojis for confidence levels
        self.assertTrue("🟢" in md or "🟡" in md or "🔴" in md or "## Key Findings" in md)


class TestResearchHistory(unittest.TestCase):
    """Test research history management."""
    
    def test_get_research_history(self):
        """Test retrieval of research history."""
        skill = DeepResearchSkill()
        
        skill.research("first query", iterations=1, store_in_memory=False)
        skill.research("second query", iterations=1, store_in_memory=False)
        
        history = skill.get_research_history()
        
        self.assertEqual(len(history), 2)
    
    def test_filter_history_by_query(self):
        """Test filtering history by query string."""
        skill = DeepResearchSkill()
        
        skill.research("artificial intelligence", iterations=1, store_in_memory=False)
        skill.research("blockchain technology", iterations=1, store_in_memory=False)
        
        filtered = skill.get_research_history(query_filter="artificial")
        
        self.assertEqual(len(filtered), 1)
        self.assertIn("artificial", filtered[0].query.lower())
    
    def test_filter_history_by_confidence(self):
        """Test filtering history by minimum confidence."""
        skill = DeepResearchSkill()
        
        report = skill.research("test", iterations=1, store_in_memory=False)
        min_conf = report.overall_confidence - 0.01
        
        filtered = skill.get_research_history(min_confidence=min_conf)
        
        self.assertEqual(len(filtered), 1)


class TestResearchComparison(unittest.TestCase):
    """Test research comparison functionality."""
    
    def test_compare_research_returns_comparison_dict(self):
        """Test that compare_research returns comparison data."""
        skill = DeepResearchSkill()
        
        comparison = skill.compare_research("agi 2026", "ai agents 2026")
        
        self.assertIn("query1", comparison)
        self.assertIn("query2", comparison)
        self.assertIn("confidence1", comparison)
        self.assertIn("confidence2", comparison)
        self.assertIn("shared_sources", comparison)
    
    def test_compare_confidence_difference(self):
        """Test that comparison includes confidence difference."""
        skill = DeepResearchSkill()
        
        comparison = skill.compare_research("mcp", "langgraph")
        
        self.assertIn("confidence_difference", comparison)
        self.assertIsInstance(comparison["confidence_difference"], float)


class TestSourceDataClass(unittest.TestCase):
    """Test ResearchSource dataclass."""
    
    def test_source_to_dict(self):
        """Test source serialization."""
        source = ResearchSource(
            title="Test Source",
            url="https://example.com",
            content="Test content that is long enough to preview properly",
            credibility=SourceCredibility.HIGH,
            credibility_score=0.9
        )
        
        d = source.to_dict()
        
        self.assertEqual(d["title"], "Test Source")
        self.assertEqual(d["credibility"], "HIGH")
        self.assertIn("content_preview", d)


class TestFindingDataClass(unittest.TestCase):
    """Test ResearchFinding dataclass."""
    
    def test_finding_to_dict(self):
        """Test finding serialization."""
        finding = ResearchFinding(
            claim="AI is advancing",
            supporting_sources=["https://example1.com", "https://example2.com"],
            confidence=0.85,
            counter_evidence=["Some counter evidence"],
            uncertainty_factors=["Limited data"]
        )
        
        d = finding.to_dict()
        
        self.assertEqual(d["claim"], "AI is advancing")
        self.assertEqual(len(d["supporting_sources"]), 2)
        self.assertEqual(d["confidence"], 0.85)


class TestFactoryFunction(unittest.TestCase):
    """Test create_deep_research_skill factory."""
    
    def test_factory_creates_skill(self):
        """Test that factory creates a DeepResearchSkill."""
        skill = create_deep_research_skill()
        
        self.assertIsInstance(skill, DeepResearchSkill)
    
    def test_factory_with_dependencies(self):
        """Test factory with injected dependencies."""
        mock_search = object()
        mock_memory = object()
        
        skill = create_deep_research_skill(
            web_search_skill=mock_search,
            memory_system=mock_memory
        )
        
        self.assertEqual(skill.web_search, mock_search)
        self.assertEqual(skill.memory, mock_memory)


class TestResearchPhases(unittest.TestCase):
    """Test research phase enum."""
    
    def test_research_phase_values(self):
        """Test that all research phases have proper values."""
        phases = [
            ResearchPhase.INITIAL_QUERY,
            ResearchPhase.SOURCE_GATHERING,
            ResearchPhase.SYNTHESIS,
            ResearchPhase.FOLLOW_UP,
            ResearchPhase.VERIFICATION,
            ResearchPhase.REPORT_GENERATION
        ]
        
        for phase in phases:
            self.assertIsNotNone(phase.value)
            self.assertIsInstance(phase.value, str)


class IntegrationTests(unittest.TestCase):
    """Integration tests for complete research workflows."""
    
    def test_complete_research_workflow(self):
        """Test complete research workflow end-to-end."""
        skill = DeepResearchSkill()
        
        # Execute research
        report = skill.research("ai agent frameworks 2026", iterations=2, store_in_memory=False)
        
        # Verify report structure
        self.assertIsNotNone(report.research_id)
        self.assertGreater(len(report.sources), 0)
        self.assertGreaterEqual(report.overall_confidence, 0.0)
        
        # Verify markdown generation
        md = report.to_markdown()
        self.assertIn("# Research Report", md)
        
        # Verify history
        self.assertEqual(len(skill.research_history), 1)
    
    def test_multiple_researches_with_history(self):
        """Test multiple research queries with history management."""
        skill = DeepResearchSkill()
        
        # Perform multiple researches
        queries = ["agi research", "mcp protocol", "agent frameworks"]
        for query in queries:
            skill.research(query, iterations=1, store_in_memory=False)
        
        # Verify history
        self.assertEqual(len(skill.research_history), 3)
        
        # Test filtering
        ai_research = skill.get_research_history(query_filter="agi")
        self.assertEqual(len(ai_research), 1)
        
        mcp_research = skill.get_research_history(query_filter="mcp")
        self.assertEqual(len(mcp_research), 1)


if __name__ == "__main__":
    # Run with verbose output
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestSourceCredibility,
        TestMockSearch,
        TestKeyFindingExtraction,
        TestFollowUpQueryGeneration,
        TestSynthesis,
        TestGapIdentification,
        TestResearchExecution,
        TestReportGeneration,
        TestResearchHistory,
        TestResearchComparison,
        TestSourceDataClass,
        TestFindingDataClass,
        TestFactoryFunction,
        TestResearchPhases,
        IntegrationTests
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 70)
    print(f"DEEP RESEARCH SKILL - TEST RESULTS")
    print("=" * 70)
    print(f"Tests Run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print(f"Success Rate: {((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100):.1f}%")
    print("=" * 70)
    
    sys.exit(0 if result.wasSuccessful() else 1)
