"""
Tests for self_analysis module.
Validates codebase analysis and self-improvement proposal system.
"""

import sys
import os
import tempfile
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.self_analysis import (
    CodebaseAnalyzer, SelfImprovementEngine, 
    ImprovementProposal, ImprovementType, CodeIssue
)


def test_codebase_analyzer_structure():
    """Test structure analysis functionality."""
    print("\n🧪 Testing CodebaseAnalyzer...")
    
    analyzer = CodebaseAnalyzer(codebase_path="/home/workspace/agi-research")
    results = analyzer.analyze_structure()
    
    # Verify we have results
    assert "missing_files" in results, "Should track missing files"
    assert "present_files" in results, "Should track present files"
    assert "coverage_percentage" in results, "Should calculate coverage"
    
    # Core files should exist
    assert results["coverage_percentage"] > 0, "Should detect some files"
    print(f"   ✅ Structure analysis: {results['coverage_percentage']:.1f}% coverage")
    print(f"   ✅ Found {len(results['present_files'])} present files")
    
    return True


def test_code_quality_analysis():
    """Test code quality metrics."""
    print("\n🧪 Testing code quality analysis...")
    
    analyzer = CodebaseAnalyzer(codebase_path="/home/workspace/agi-research")
    
    # Analyze a known file
    quality = analyzer.analyze_code_quality("core/agent.py")
    
    assert "lines" in quality, "Should count lines"
    assert "quality_score" in quality, "Should calculate quality score"
    assert quality["quality_score"] > 0, "Should have positive quality score"
    
    print(f"   ✅ agent.py: {quality['lines']} lines, score: {quality['quality_score']:.1f}")
    
    return True


def test_improvement_opportunity_detection():
    """Test opportunity detection."""
    print("\n🧪 Testing improvement opportunity detection...")
    
    analyzer = CodebaseAnalyzer(codebase_path="/home/workspace/agi-research")
    opportunities = analyzer.identify_improvement_opportunities()
    
    assert isinstance(opportunities, list), "Should return list of opportunities"
    
    # Should find some opportunities in any codebase
    print(f"   ✅ Found {len(opportunities)} improvement opportunities")
    
    for opp in opportunities[:3]:
        print(f"      • [{opp.get('priority', 'unknown')}] {opp.get('type', 'unknown')}: {opp.get('description', '')[:50]}...")
    
    return True


def test_self_improvement_engine_creation():
    """Test engine creation and basic operation."""
    print("\n🧪 Testing SelfImprovementEngine...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = SelfImprovementEngine(
            codebase_path="/home/workspace/agi-research",
            storage_path=f"{tmpdir}/proposals.json"
        )
        
        assert engine.analyzer is not None, "Should have analyzer"
        assert isinstance(engine.proposals, list), "Should have proposals list"
        
        print("   ✅ Engine created successfully")
        
        return True


def test_proposal_generation():
    """Test that analysis generates proposals."""
    print("\n🧪 Testing proposal generation...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = SelfImprovementEngine(
            codebase_path="/home/workspace/agi-research",
            storage_path=f"{tmpdir}/proposals.json"
        )
        
        # Run analysis (this generates proposals)
        results = engine.run_full_analysis()
        
        assert "proposals_generated" in results, "Should track proposal count"
        
        # Check proposals were created
        if engine.proposals:
            print(f"   ✅ Generated {len(engine.proposals)} proposals")
            
            # Verify proposal structure
            for p in engine.proposals[:2]:
                assert p.id, "Proposal should have ID"
                assert p.component, "Proposal should have component"
                assert p.status == "proposed", "New proposals should be 'proposed'"
                assert p.requires_review, "All self-modifications require review"
                print(f"      • {p.id}: {p.component} ({p.improvement_type.value})")
        else:
            print("   ⚠️ No proposals generated (may indicate complete codebase)")
        
        return True


def test_proposal_review_workflow():
    """Test review and implementation workflow."""
    print("\n🧪 Testing review workflow...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = SelfImprovementEngine(
            codebase_path="/home/workspace/agi-research",
            storage_path=f"{tmpdir}/proposals.json"
        )
        
        # Generate a test proposal manually
        from datetime import datetime
        proposal = ImprovementProposal(
            id="test_001",
            title="Test proposal",
            improvement_type=ImprovementType.ENHANCEMENT,
            component="test",
            description="Test description",
            rationale="Testing workflow",
            expected_impact="None",
            target_file=None,
            risk_level="SAFE"
        )
        engine.proposals.append(proposal)
        
        # Test review
        pending = engine.get_pending_proposals()
        assert len(pending) == 1, "Should have one pending proposal"
        
        # Reject the proposal
        engine.review_proposal("test_001", approved=False, feedback="Test rejection")
        
        assert proposal.status == "rejected", "Should be rejected"
        assert proposal.reviewer_feedback == "Test rejection"
        
        print("   ✅ Review workflow works correctly")
        
        return True


def test_implementation_safety():
    """Test that implementation respects safety rules."""
    print("\n🧪 Testing implementation safety...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = SelfImprovementEngine(
            codebase_path=tmpdir,  # Use temp to avoid affecting real codebase
            storage_path=f"{tmpdir}/proposals.json"
        )
        
        # Create a proposal without approval
        from datetime import datetime
        proposal = ImprovementProposal(
            id="unapproved_001",
            title="Unapproved change",
            improvement_type=ImprovementType.ENHANCEMENT,
            component="test",
            description="Test unapproved",
            rationale="Testing safety",
            expected_impact="None",
            target_file="test.py",
            proposed_code="# Test",
            risk_level="SAFE"
        )
        engine.proposals.append(proposal)
        
        # Try to implement without approval
        result = engine.implement_proposal("unapproved_001")
        
        assert not result["success"], "Should fail without approval"
        assert "not approved" in result["error"], "Should indicate approval required"
        
        print("   ✅ Safety check: Unapproved changes are blocked")
        
        # Now approve and implement
        engine.review_proposal("unapproved_001", approved=True, feedback="Approved for test")
        result = engine.implement_proposal("unapproved_001")
        
        assert result["success"], "Should succeed after approval"
        assert proposal.status == "implemented"
        
        print("   ✅ Approved changes can be implemented")
        
        return True


def test_summary_generation():
    """Test summary report generation."""
    print("\n🧪 Testing summary generation...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = SelfImprovementEngine(
            codebase_path="/home/workspace/agi-research",
            storage_path=f"{tmpdir}/proposals.json"
        )
        
        # Run analysis
        engine.run_full_analysis()
        
        # Get summary
        summary = engine.get_summary()
        
        assert "Self-Analysis Summary" in summary, "Should have header"
        assert isinstance(summary, str), "Summary should be string"
        
        print(f"   ✅ Generated summary ({len(summary)} chars)")
        
        return True


def test_proposal_persistence():
    """Test that proposals are saved and loaded."""
    print("\n🧪 Testing proposal persistence...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_path = f"{tmpdir}/proposals.json"
        
        # Create engine and add proposal
        engine1 = SelfImprovementEngine(
            codebase_path="/home/workspace/agi-research",
            storage_path=storage_path
        )
        
        from datetime import datetime
        proposal = ImprovementProposal(
            id="persist_test",
            title="Persistence test",
            improvement_type=ImprovementType.DOCUMENTATION,
            component="docs",
            description="Test persistence",
            rationale="Testing save/load",
            expected_impact="None"
        )
        engine1.proposals.append(proposal)
        engine1._save()
        
        # Create new engine instance and load
        engine2 = SelfImprovementEngine(
            codebase_path="/home/workspace/agi-research",
            storage_path=storage_path
        )
        
        assert len(engine2.proposals) == 1, "Should load saved proposal"
        assert engine2.proposals[0].id == "persist_test", "Should preserve ID"
        
        print("   ✅ Proposal persistence works correctly")
        
        return True


def run_all_tests():
    """Run all self-analysis tests."""
    print("\n" + "="*60)
    print("🧪 Self-Analysis Module Test Suite")
    print("="*60)
    
    tests = [
        test_codebase_analyzer_structure,
        test_code_quality_analysis,
        test_improvement_opportunity_detection,
        test_self_improvement_engine_creation,
        test_proposal_generation,
        test_proposal_review_workflow,
        test_implementation_safety,
        test_summary_generation,
        test_proposal_persistence
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"   ❌ Test returned False")
        except Exception as e:
            failed += 1
            print(f"   ❌ Test failed with error: {e}")
    
    print("\n" + "="*60)
    print(f"📊 Results: {passed}/{len(tests)} tests passed")
    print("="*60)
    
    if failed == 0:
        print("✅ All tests passed!")
    else:
        print(f"❌ {failed} test(s) failed")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
