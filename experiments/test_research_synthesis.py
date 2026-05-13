"""
Test suite for Research Synthesis Skill.

Tests AggAgent-inspired research aggregation patterns:
- Theme extraction from multiple sources
- Contradiction detection
- Gap identification  
- Insight generation
- Next step recommendations
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime, timedelta
from skills.research_synthesis import (
    ResearchFinding, SynthesisTheme, SynthesisReport,
    ResearchSynthesizer, quick_synthesize, create_synthesizer
)


class TestResearchFinding:
    """Test ResearchFinding dataclass."""
    
    def test_finding_creation(self):
        """Test creating a research finding."""
        finding = ResearchFinding(
            source="arXiv:2604.18292",
            source_type="arxiv",
            title="Agent-World",
            content="Self-evolving training arena for agents",
            date=datetime(2026, 4, 20),
            tags=["self-evolution", "benchmarks"],
            confidence=0.9,
        )
        assert finding.source == "arXiv:2604.18292"
        assert finding.source_type == "arxiv"
        assert "self-evolution" in finding.tags
        assert finding.confidence == 0.9
        print("✓ Finding creation test passed")
    
    def test_finding_to_dict(self):
        """Test finding serialization."""
        finding = ResearchFinding(
            source="github.com/example",
            source_type="github",
            title="GenericAgent",
            content="Minimal self-evolving agent framework",
            date=datetime(2026, 4, 15),
        )
        d = finding.to_dict()
        assert d["source"] == "github.com/example"
        assert d["source_type"] == "github"
        assert "date" in d
        print("✓ Finding to_dict test passed")


class TestSynthesisTheme:
    """Test SynthesisTheme dataclass."""
    
    def test_theme_creation(self):
        """Test creating a synthesis theme."""
        theme = SynthesisTheme(
            theme_id="theme_self_evolution",
            name="Self Evolution",
            description="Self-evolving agent patterns",
            supporting_findings=["arXiv:1", "arXiv:2", "github:3"],
            confidence=0.85,
        )
        assert theme.theme_id == "theme_self_evolution"
        assert len(theme.supporting_findings) == 3
        assert theme.confidence == 0.85
        print("✓ Theme creation test passed")
    
    def test_theme_contradictions(self):
        """Test theme with contradictions."""
        theme = SynthesisTheme(
            theme_id="theme_multi_agent",
            name="Multi Agent",
            description="Multi-agent orchestration",
            supporting_findings=["source1", "source2"],
            confidence=0.7,
            contradictions=["confidence_disagreement", "temporal_contradiction"],
        )
        assert len(theme.contradictions) == 2
        print("✓ Theme contradictions test passed")


class TestSynthesisReport:
    """Test SynthesisReport dataclass."""
    
    def test_report_creation(self):
        """Test creating a synthesis report."""
        report = SynthesisReport(
            report_id="test_001",
            generated_at=datetime.now(),
            num_sources=5,
            num_findings=12,
            themes=[],
            key_insights=["Insight 1", "Insight 2"],
            contradictions=[],
            research_gaps=["Gap 1"],
            next_steps=["Step 1", "Step 2"],
        )
        assert report.report_id == "test_001"
        assert report.num_sources == 5
        assert len(report.key_insights) == 2
        print("✓ Report creation test passed")
    
    def test_report_to_markdown(self):
        """Test markdown generation."""
        theme = SynthesisTheme(
            theme_id="theme_test",
            name="Test Theme",
            description="A test theme",
            supporting_findings=["source1", "source2"],
            confidence=0.9,
        )
        report = SynthesisReport(
            report_id="md_test",
            generated_at=datetime.now(),
            num_sources=2,
            num_findings=3,
            themes=[theme],
            key_insights=["Key insight"],
            contradictions=[],
            research_gaps=[],
            next_steps=["Next step"],
        )
        md = report.to_markdown()
        assert "# Research Synthesis Report" in md
        assert "Test Theme" in md
        assert "Key insight" in md
        print("✓ Report to_markdown test passed")


class TestResearchSynthesizer:
    """Test ResearchSynthesizer functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.synthesizer = ResearchSynthesizer()
        
        # Sample findings for testing
        self.sample_findings = [
            ResearchFinding(
                source="arXiv:2604.18292",
                source_type="arxiv",
                title="Agent-World",
                content="Self-evolving training arena from ByteDance. Agent-World-8B outperforms proprietary models on 23 benchmarks through co-evolution of policies and environments.",
                date=datetime(2026, 4, 20),
                tags=["self-evolution", "benchmarks"],
                confidence=0.95,
            ),
            ResearchFinding(
                source="github.com/razzant/ouroboros",
                source_type="github",
                title="Ouroboros",
                content="Self-modifying AI agent with BIBLE.md constitution. Multi-model review and persistent identity across restarts.",
                date=datetime(2026, 4, 18),
                tags=["self-evolution", "governance"],
                confidence=0.88,
            ),
            ResearchFinding(
                source="github.com/lsdefine/GenericAgent",
                source_type="github",
                title="GenericAgent",
                content="Minimal self-evolving agent with skill tree crystallization. Browser automation and screen vision.",
                date=datetime(2026, 4, 15),
                tags=["self-evolution", "skills"],
                confidence=0.92,
            ),
            ResearchFinding(
                source="arXiv:2604.11753v1",
                source_type="arxiv",
                title="AggAgent",
                content="Parallel scaling for long-horizon agentic tasks. AggAgent coordinates parallel rollouts for aggregation and synthesis.",
                date=datetime(2026, 4, 13),
                tags=["parallelization", "aggregation"],
                confidence=0.90,
            ),
            ResearchFinding(
                source="github.com/aden-hive/hive",
                source_type="github",
                title="OpenHive",
                content="Production-grade multi-agent harness with graph-based DAG execution and self-healing capabilities.",
                date=datetime(2026, 4, 10),
                tags=["multi-agent", "orchestration", "dag"],
                confidence=0.85,
            ),
            ResearchFinding(
                source="github.com/VoltAgent/voltagent",
                source_type="github",
                title="VoltAgent",
                content="TypeScript multi-agent framework with VoltOps console and MCP compatibility.",
                date=datetime(2026, 4, 8),
                tags=["multi-agent", "mcp"],
                confidence=0.87,
            ),
            ResearchFinding(
                source="arXiv:2604.02434",
                source_type="arxiv",
                title="Compositional Neuro-Symbolic Reasoning",
                content="Neuro-symbolic framework for ARC-AGI. Compositional reasoning with DSL improves performance 16% to 30.8%.",
                date=datetime(2026, 4, 2),
                tags=["neuro-symbolic", "arc-agi", "dsl"],
                confidence=0.93,
            ),
            ResearchFinding(
                source="arXiv:2604.15236",
                source_type="arxiv",
                title="Agentic Microphysics",
                content="Safety framework for multi-agent interactions. Population-level risk analysis for generative AI.",
                date=datetime(2026, 4, 16),
                tags=["safety", "multi-agent", "governance"],
                confidence=0.82,
            ),
        ]
    
    def test_add_finding(self):
        """Test adding a single finding."""
        self.synthesizer.add_finding(self.sample_findings[0])
        assert len(self.synthesizer.findings) == 1
        print("✓ Add finding test passed")
    
    def test_add_findings_batch(self):
        """Test adding multiple findings."""
        self.synthesizer.add_findings_batch(self.sample_findings[:3])
        assert len(self.synthesizer.findings) == 3
        print("✓ Add findings batch test passed")
    
    def test_extract_themes(self):
        """Test theme extraction."""
        self.synthesizer.add_findings_batch(self.sample_findings)
        themes = self.synthesizer.extract_themes()
        
        # Should identify self_evolution theme from multiple findings
        assert "self_evolution" in themes
        assert len(themes["self_evolution"]) >= 3
        
        # Should identify multi_agent theme
        assert "multi_agent" in themes
        
        print("✓ Theme extraction test passed")
    
    def test_synthesize_basic(self):
        """Test basic synthesis."""
        self.synthesizer.add_findings_batch(self.sample_findings)
        report = self.synthesizer.synthesize("test_report_001")
        
        assert report.report_id == "test_report_001"
        assert report.num_sources == 8
        assert report.num_findings == 8
        assert len(report.themes) > 0
        assert len(report.key_insights) > 0
        assert len(report.next_steps) > 0
        
        print("✓ Basic synthesis test passed")
    
    def test_self_evolution_theme_strength(self):
        """Test that self-evolution theme has high confidence."""
        self.synthesizer.add_findings_batch(self.sample_findings)
        report = self.synthesizer.synthesize()
        
        # Find self-evolution theme
        self_evol_themes = [t for t in report.themes if "self_evolution" in t.theme_id]
        assert len(self_evol_themes) > 0
        
        theme = self_evol_themes[0]
        assert theme.confidence > 0.85  # High confidence from multiple sources
        assert len(theme.supporting_findings) >= 3
        
        print("✓ Self-evolution theme strength test passed")
    
    def test_multi_agent_theme_detection(self):
        """Test multi-agent theme detection."""
        self.synthesizer.add_findings_batch(self.sample_findings)
        report = self.synthesizer.synthesize()
        
        multi_agent_themes = [t for t in report.themes if "multi_agent" in t.theme_id]
        assert len(multi_agent_themes) > 0
        
        print("✓ Multi-agent theme detection test passed")
    
    def test_neuro_symbolic_theme(self):
        """Test neuro-symbolic theme detection."""
        self.synthesizer.add_findings_batch(self.sample_findings)
        
        # Check themes_dict from extract_themes (not just report themes which require 2+ findings)
        themes = self.synthesizer.extract_themes()
        assert "neuro_symbolic" in themes
        assert len(themes["neuro_symbolic"]) >= 1
        
        # Also verify it appears in report if we have enough findings
        if len(themes["neuro_symbolic"]) >= 2:
            report = self.synthesizer.synthesize()
            neuro_themes = [t for t in report.themes if "neuro_symbolic" in t.theme_id]
            assert len(neuro_themes) > 0
        
        print("✓ Neuro-symbolic theme detection test passed")
    
    def test_key_insights_generation(self):
        """Test key insights generation."""
        self.synthesizer.add_findings_batch(self.sample_findings)
        report = self.synthesizer.synthesize()
        
        # Should have insights about strong themes
        assert len(report.key_insights) > 0
        
        # Should mention self-evolution as strong consensus
        insights_text = " ".join(report.key_insights)
        assert "self" in insights_text.lower() or "evolution" in insights_text.lower() or "consensus" in insights_text.lower()
        
        print("✓ Key insights generation test passed")
    
    def test_contradiction_detection(self):
        """Test contradiction detection."""
        # Create fresh synthesizer for clean test (not using sample findings)
        fresh_synthesizer = ResearchSynthesizer()
        
        # Add findings with confidence disagreement (gap > 0.5)
        conflicting_findings = [
            ResearchFinding(
                source="arXiv:1",
                source_type="arxiv",
                title="Paper A",
                content="Self-evolution is the key to AGI with autonomous improvement",
                date=datetime(2026, 5, 1),
                confidence=0.95,
            ),
            ResearchFinding(
                source="arXiv:2",
                source_type="arxiv",
                title="Paper B",
                content="Self-evolution approaches show limited progress and are not effective",
                date=datetime(2026, 5, 10),
                confidence=0.25,  # Large gap (> 0.5) triggers contradiction
            ),
        ]
        fresh_synthesizer.add_findings_batch(conflicting_findings)
        
        themes = fresh_synthesizer.extract_themes()
        contradictions = fresh_synthesizer.identify_contradictions(themes)
        
        # Should detect confidence disagreement
        assert len(contradictions) > 0
        
        print("✓ Contradiction detection test passed")
    
    def test_gap_identification(self):
        """Test research gap identification."""
        self.synthesizer.add_findings_batch(self.sample_findings)
        
        themes = self.synthesizer.extract_themes()
        gaps = self.synthesizer.identify_gaps(themes)
        
        # Should identify some gaps
        assert isinstance(gaps, list)
        
        # Likely to identify missing themes like parallelization
        print(f"Identified {len(gaps)} research gaps")
        print("✓ Gap identification test passed")
    
    def test_next_steps_recommendation(self):
        """Test next steps recommendations."""
        self.synthesizer.add_findings_batch(self.sample_findings)
        report = self.synthesizer.synthesize()
        
        # Should have recommended steps
        assert len(report.next_steps) > 0
        
        # Steps should mention prototyping or implementation
        steps_text = " ".join(report.next_steps).lower()
        assert any(word in steps_text for word in ["prototype", "implement", "investigate", "expand", "deep"])
        
        print("✓ Next steps recommendation test passed")
    
    def test_cross_theme_insights(self):
        """Test cross-theme insight generation."""
        # Add findings that should trigger cross-theme insights
        cross_findings = [
            ResearchFinding(
                source="test1",
                source_type="test",
                title="Test Self-Evolving Multi-Agent",
                content="Agents that evolve in multi-agent environments show stronger generalization",
                date=datetime(2026, 5, 1),
                tags=["self-evolution", "multi-agent"],
            ),
            ResearchFinding(
                source="test2",
                source_type="test",
                title="Test Neuro-Symbolic Benchmark",
                content="Neuro-symbolic approaches showing measurable benchmark improvements",
                date=datetime(2026, 5, 2),
                tags=["neuro-symbolic", "benchmarks"],
            ),
        ]
        self.synthesizer.add_findings_batch(cross_findings)
        
        themes = self.synthesizer.extract_themes()
        insights = self.synthesizer.generate_key_insights(themes)
        
        # Should have cross-theme insights
        assert len(insights) > 0
        
        print("✓ Cross-theme insights test passed")
    
    def test_clear_findings(self):
        """Test clearing all findings."""
        self.synthesizer.add_findings_batch(self.sample_findings)
        assert len(self.synthesizer.findings) == 8
        
        self.synthesizer.clear()
        assert len(self.synthesizer.findings) == 0
        
        print("✓ Clear findings test passed")
    
    def test_empty_synthesis_raises_error(self):
        """Test that synthesizing with no findings raises error."""
        empty_synthesizer = ResearchSynthesizer()
        try:
            empty_synthesizer.synthesize()
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "No findings to synthesize" in str(e)
        
        print("✓ Empty synthesis error test passed")
    
    def test_export_import_findings(self, tmp_path="/tmp"):
        """Test exporting and importing findings."""
        self.synthesizer.add_findings_batch(self.sample_findings[:3])
        
        filepath = f"{tmp_path}/test_findings.json"
        self.synthesizer.export_findings(filepath)
        
        # Verify file was created
        assert os.path.exists(filepath)
        
        # Import into new synthesizer
        new_synthesizer = ResearchSynthesizer()
        new_synthesizer.import_findings(filepath)
        
        assert len(new_synthesizer.findings) == 3
        
        # Cleanup
        os.remove(filepath)
        
        print("✓ Export/import findings test passed")


class TestQuickSynthesize:
    """Test quick_synthesize convenience function."""
    
    def test_quick_synthesize(self):
        """Test quick synthesis from raw data."""
        findings_data = [
            {
                "source": "arXiv:2604.18292",
                "source_type": "arxiv",
                "title": "Agent-World",
                "content": "Self-evolving training arena",
                "date": "2026-04-20",
                "tags": ["self-evolution"],
            },
            {
                "source": "github.com/example",
                "source_type": "github",
                "title": "GenericAgent",
                "content": "Self-evolving agent framework",
                "date": "2026-04-15",
                "tags": ["self-evolution"],
            },
            {
                "source": "arXiv:2604.11753v1",
                "source_type": "arxiv",
                "title": "AggAgent",
                "content": "Parallel scaling for agentic tasks",
                "date": "2026-04-13",
                "tags": ["parallelization"],
            },
        ]
        
        report = quick_synthesize(findings_data)
        
        assert report.num_findings == 3
        assert report.num_sources == 3
        assert len(report.themes) > 0
        assert len(report.key_insights) > 0
        
        print("✓ Quick synthesize test passed")


class TestCreateSynthesizer:
    """Test create_synthesizer convenience function."""
    
    def test_create_synthesizer(self):
        """Test synthesizer factory function."""
        synthesizer = create_synthesizer()
        
        assert isinstance(synthesizer, ResearchSynthesizer)
        assert len(synthesizer.findings) == 0
        assert len(synthesizer.theme_extractors) > 0
        
        print("✓ Create synthesizer test passed")


def run_all_tests():
    """Run all tests in the test suite."""
    print("\n" + "="*60)
    print("RESEARCH SYNTHESIS SKILL TEST SUITE")
    print("="*60 + "\n")
    
    test_classes = [
        TestResearchFinding(),
        TestSynthesisTheme(),
        TestSynthesisReport(),
        TestResearchSynthesizer(),
        TestQuickSynthesize(),
        TestCreateSynthesizer(),
    ]
    
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    
    for test_class in test_classes:
        class_name = test_class.__class__.__name__
        print(f"\n{class_name}")
        print("-" * len(class_name))
        
        # Get all test methods
        methods = [m for m in dir(test_class) if m.startswith("test_")]
        
        for method_name in methods:
            total_tests += 1
            try:
                method = getattr(test_class, method_name)
                
                # Setup if available
                if hasattr(test_class, 'setup_method'):
                    test_class.setup_method()
                
                method()
                passed_tests += 1
                
            except AssertionError as e:
                print(f"  ✗ {method_name}: FAILED - {e}")
                failed_tests += 1
            except Exception as e:
                print(f"  ✗ {method_name}: ERROR - {e}")
                failed_tests += 1
    
    print("\n" + "="*60)
    print(f"RESULTS: {passed_tests}/{total_tests} passed")
    if failed_tests > 0:
        print(f"         {failed_tests} failed")
    print("="*60 + "\n")
    
    return failed_tests == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
