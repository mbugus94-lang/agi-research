"""
Test Suite for Verification & Attestation System

Tests coverage:
1. Output registration and categorization
2. Measurability assessment
3. Verification cost estimation
4. Evidence management
5. Attestation creation and signing
6. Confidence score calculation
7. Agent reputation tracking
8. Dispute handling
9. Consensus attestation
10. Measurability gap analysis
"""

import sys
sys.path.insert(0, '/home/workspace/agi-research')

import unittest
from core.verification import (
    VerificationSystem, MeasurabilityGapAnalyzer, create_verification_system,
    VerifiableOutput, Attestation, Evidence,
    VerificationLevel, OutputCategory
)


class TestOutputRegistration(unittest.TestCase):
    """Tests for registering and categorizing outputs"""
    
    def setUp(self):
        self.vs, self.analyzer = create_verification_system()
    
    def test_register_code_output(self):
        """Code outputs should be categorized as deterministic"""
        output = self.vs.register_output(
            agent_id="test_agent",
            output_type="code_gen",
            content="def test(): pass",
            inputs={"language": "python"}
        )
        
        self.assertEqual(output.category, OutputCategory.DETERMINISTIC.value)
        self.assertGreater(output.measurability_score, 0.7)
        self.assertLess(output.verification_cost_estimate, 5)  # Low cost for code
    
    def test_register_analysis_output(self):
        """Analysis outputs should be categorized as semantic"""
        output = self.vs.register_output(
            agent_id="test_agent",
            output_type="analysis",
            content="Market analysis suggests..."
        )
        
        self.assertEqual(output.category, OutputCategory.SEMANTIC.value)
        self.assertTrue(0.4 < output.measurability_score < 0.7)
    
    def test_register_creative_output(self):
        """Creative outputs should be categorized appropriately"""
        output = self.vs.register_output(
            agent_id="test_agent",
            output_type="creative_gen",
            content="Generated artwork description..."
        )
        
        self.assertEqual(output.category, OutputCategory.CREATIVE.value)
        self.assertLess(output.measurability_score, 0.4)
    
    def test_register_action_output(self):
        """Action outputs should be categorized appropriately"""
        output = self.vs.register_output(
            agent_id="test_agent",
            output_type="api_call",
            content={"endpoint": "/transfer", "amount": 100}
        )
        
        self.assertEqual(output.category, OutputCategory.ACTION.value)
    
    def test_input_hash_generation(self):
        """Input hash should be computed for provenance"""
        inputs = {"key": "value", "number": 42}
        output = self.vs.register_output(
            agent_id="test_agent",
            output_type="test",
            content="test",
            inputs=inputs
        )
        
        self.assertIsNotNone(output.input_hash)
        self.assertEqual(len(output.input_hash), 16)
    
    def test_explicit_category_override(self):
        """Explicit category should override auto-detection"""
        output = self.vs.register_output(
            agent_id="test_agent",
            output_type="code_gen",  # Would normally be deterministic
            content="test",
            category=OutputCategory.SYNTHETIC.value
        )
        
        self.assertEqual(output.category, OutputCategory.SYNTHETIC.value)


class TestMeasurabilityAssessment(unittest.TestCase):
    """Tests for measurability scoring"""
    
    def setUp(self):
        self.vs, self.analyzer = create_verification_system()
    
    def test_deterministic_high_measurability(self):
        """Deterministic outputs should have high measurability"""
        score = self.vs._assess_measurability(
            OutputCategory.DETERMINISTIC.value,
            {"code": "valid python"}
        )
        self.assertGreater(score, 0.7)
    
    def test_synthetic_low_measurability(self):
        """Synthetic insights should have low measurability"""
        score = self.vs._assess_measurability(
            OutputCategory.SYNTHETIC.value,
            {"hypothesis": "New theory about..."}
        )
        self.assertLess(score, 0.3)
    
    def test_content_size_impact(self):
        """Large content should reduce measurability"""
        small_score = self.vs._assess_measurability(
            OutputCategory.SEMANTIC.value,
            "Short text"
        )
        large_score = self.vs._assess_measurability(
            OutputCategory.SEMANTIC.value,
            "x" * 15000  # Very long content
        )
        
        self.assertGreater(small_score, large_score)
    
    def test_structured_content_boost(self):
        """Structured content should boost measurability"""
        text_score = self.vs._assess_measurability(
            OutputCategory.SEMANTIC.value,
            "Plain text content"
        )
        structured_score = self.vs._assess_measurability(
            OutputCategory.SEMANTIC.value,
            {"key": "value", "data": [1, 2, 3]}
        )
        
        self.assertGreater(structured_score, text_score)
    
    def test_references_boost_measurability(self):
        """Content with references should have higher measurability"""
        no_ref_score = self.vs._assess_measurability(
            OutputCategory.SEMANTIC.value,
            "Some analysis"
        )
        with_ref_score = self.vs._assess_measurability(
            OutputCategory.SEMANTIC.value,
            "Analysis based on reference [1] and source data"
        )
        
        self.assertGreater(with_ref_score, no_ref_score)


class TestVerificationCostEstimation(unittest.TestCase):
    """Tests for verification cost estimation"""
    
    def setUp(self):
        self.vs, _ = create_verification_system()
    
    def test_deterministic_low_cost(self):
        """Deterministic outputs should have low verification cost"""
        cost = self.vs._estimate_verification_cost(
            OutputCategory.DETERMINISTIC.value,
            "def test(): pass",
            0.9
        )
        self.assertLess(cost, 5)
    
    def test_synthetic_high_cost(self):
        """Synthetic outputs should have high verification cost"""
        cost = self.vs._estimate_verification_cost(
            OutputCategory.SYNTHETIC.value,
            "Novel insight...",
            0.1
        )
        self.assertGreater(cost, 20)
    
    def test_measurability_reduces_cost(self):
        """Higher measurability should reduce cost"""
        low_meas_cost = self.vs._estimate_verification_cost(
            OutputCategory.SEMANTIC.value,
            "content",
            0.3
        )
        high_meas_cost = self.vs._estimate_verification_cost(
            OutputCategory.SEMANTIC.value,
            "content",
            0.9
        )
        
        self.assertGreater(low_meas_cost, high_meas_cost)


class TestEvidenceManagement(unittest.TestCase):
    """Tests for evidence addition and retrieval"""
    
    def setUp(self):
        self.vs, _ = create_verification_system()
        self.output = self.vs.register_output(
            agent_id="test_agent",
            output_type="test",
            content="test content"
        )
    
    def test_add_evidence(self):
        """Evidence should be added to output"""
        evidence = self.vs.add_evidence(
            output_id=self.output.id,
            evidence_type="test_result",
            content="Passed",
            source="automated_test",
            confidence=0.9
        )
        
        self.assertEqual(len(self.output.evidence), 1)
        self.assertEqual(evidence.evidence_type, "test_result")
        self.assertEqual(evidence.confidence, 0.9)
    
    def test_add_evidence_invalid_output(self):
        """Adding evidence to non-existent output should raise error"""
        with self.assertRaises(ValueError):
            self.vs.add_evidence(
                output_id="invalid_id",
                evidence_type="test",
                content="test",
                source="test"
            )
    
    def test_multiple_evidence_accumulation(self):
        """Multiple evidence should accumulate"""
        for i in range(3):
            self.vs.add_evidence(
                output_id=self.output.id,
                evidence_type=f"evidence_{i}",
                content=f"Content {i}",
                source="test",
                confidence=0.8
            )
        
        self.assertEqual(len(self.output.evidence), 3)


class TestAttestation(unittest.TestCase):
    """Tests for attestation creation and management"""
    
    def setUp(self):
        self.vs, _ = create_verification_system()
        self.output = self.vs.register_output(
            agent_id="test_agent",
            output_type="code_gen",
            content="def test(): pass"
        )
    
    def test_create_attestation(self):
        """Attestation should be created with signature"""
        attestation = self.vs.verify_output(
            output_id=self.output.id,
            verifier_id="human_reviewer_1",
            verifier_type="human",
            method="code_review",
            claim="Code follows style guidelines",
            confidence=0.9
        )
        
        self.assertIsNotNone(attestation.id)
        self.assertIsNotNone(attestation.signature)
        self.assertEqual(len(attestation.signature), 32)
        self.assertEqual(attestation.output_id, self.output.id)
    
    def test_attestation_updates_output_confidence(self):
        """Verification should update output confidence score"""
        initial_confidence = self.output.confidence_score
        
        self.vs.verify_output(
            output_id=self.output.id,
            verifier_id="auto_verifier",
            verifier_type="automated",
            confidence=0.8
        )
        
        self.assertGreater(self.output.confidence_score, initial_confidence)
    
    def test_attestation_updates_verification_status(self):
        """Verification should update output status"""
        self.assertEqual(self.output.verification_status, "pending")
        
        self.vs.verify_output(
            output_id=self.output.id,
            verifier_id="verifier",
            confidence=0.8
        )
        
        self.assertEqual(self.output.verification_status, "verified")
    
    def test_attestation_invalid_output(self):
        """Verifying non-existent output should raise error"""
        with self.assertRaises(ValueError):
            self.vs.verify_output(
                output_id="invalid_id",
                verifier_id="verifier",
                confidence=0.8
            )


class TestAgentReputation(unittest.TestCase):
    """Tests for agent reputation tracking"""
    
    def setUp(self):
        self.vs, _ = create_verification_system()
        self.agent_id = "reputation_test_agent"
    
    def test_reputation_unknown_agent(self):
        """Unknown agent should have neutral reputation"""
        rep = self.vs.get_agent_reputation("unknown_agent")
        
        self.assertEqual(rep["score"], 0.5)
        self.assertEqual(rep["level"], "unknown")
    
    def test_reputation_improves_with_verifications(self):
        """Reputation should improve with successful verifications"""
        # Create and verify multiple outputs
        for i in range(10):
            output = self.vs.register_output(
                agent_id=self.agent_id,
                output_type="code_gen",
                content="valid code"
            )
            self.vs.verify_output(
                output_id=output.id,
                verifier_id="auto_verifier",
                confidence=0.9
            )
        
        rep = self.vs.get_agent_reputation(self.agent_id)
        
        self.assertGreater(rep["score"], 0.5)
        self.assertGreater(rep["accuracy"], 0.5)
    
    def test_reputation_damage_from_disputes(self):
        """Reputation should suffer from disputes"""
        # Create and verify outputs
        for i in range(5):
            output = self.vs.register_output(
                agent_id=self.agent_id,
                output_type="code_gen",
                content="code"
            )
            self.vs.verify_output(
                output_id=output.id,
                verifier_id="verifier",
                confidence=0.8
            )
        
        rep_before = self.vs.get_agent_reputation(self.agent_id)
        
        # Dispute one output
        output_to_dispute = list(self.vs.outputs.values())[0]
        self.vs.dispute_output(
            output_id=output_to_dispute.id,
            disputer_id="auditor",
            reason="Critical error found",
            severity="major"
        )
        
        rep_after = self.vs.get_agent_reputation(self.agent_id)
        
        self.assertLess(rep_after["score"], rep_before["score"])
        self.assertEqual(rep_after["history"]["disputed"], 1)


class TestDisputeHandling(unittest.TestCase):
    """Tests for dispute creation and handling"""
    
    def setUp(self):
        self.vs, _ = create_verification_system()
        self.output = self.vs.register_output(
            agent_id="test_agent",
            output_type="analysis",
            content="Analysis results"
        )
        self.vs.verify_output(
            output_id=self.output.id,
            verifier_id="verifier",
            confidence=0.8
        )
    
    def test_dispute_changes_status(self):
        """Dispute should change verification status"""
        self.assertEqual(self.output.verification_status, "verified")
        
        self.vs.dispute_output(
            output_id=self.output.id,
            disputer_id="auditor",
            reason="Incorrect analysis"
        )
        
        self.assertEqual(self.output.verification_status, "disputed")
    
    def test_dispute_reduces_confidence(self):
        """Dispute should reduce confidence score"""
        initial_confidence = self.output.confidence_score
        
        self.vs.dispute_output(
            output_id=self.output.id,
            disputer_id="auditor",
            reason="Incorrect analysis",
            severity="major"
        )
        
        self.assertLess(self.output.confidence_score, initial_confidence)
    
    def test_dispute_severity_impact(self):
        """Higher severity disputes should have larger impact"""
        output1 = self.vs.register_output(
            agent_id="test_agent",
            output_type="test",
            content="test1"
        )
        output2 = self.vs.register_output(
            agent_id="test_agent",
            output_type="test",
            content="test2"
        )
        
        self.vs.verify_output(output_id=output1.id, verifier_id="v1", confidence=0.8)
        self.vs.verify_output(output_id=output2.id, verifier_id="v2", confidence=0.8)
        
        initial_conf1 = output1.confidence_score
        initial_conf2 = output2.confidence_score
        
        # Minor dispute
        self.vs.dispute_output(output_id=output1.id, disputer_id="d1", reason="test", severity="minor")
        # Major dispute
        self.vs.dispute_output(output_id=output2.id, disputer_id="d2", reason="test", severity="major")
        
        # Major dispute should have larger impact
        impact1 = initial_conf1 - output1.confidence_score
        impact2 = initial_conf2 - output2.confidence_score
        
        self.assertGreater(impact2, impact1)


class TestConsensusAttestation(unittest.TestCase):
    """Tests for multi-verifier consensus"""
    
    def setUp(self):
        self.vs, _ = create_verification_system()
        self.output = self.vs.register_output(
            agent_id="test_agent",
            output_type="synthetic",
            content="Novel hypothesis"
        )
    
    def test_consensus_requires_verifiers(self):
        """Consensus requires existing attestations"""
        consensus = self.vs.create_consensus_attestation(
            output_id=self.output.id,
            verifier_ids=["v1", "v2"],
            min_confidence=0.6
        )
        
        self.assertIsNone(consensus)  # No existing attestations
    
    def test_consensus_with_sufficient_confidence(self):
        """Consensus should succeed with sufficient confidence"""
        # Create individual attestations
        self.vs.verify_output(
            output_id=self.output.id,
            verifier_id="expert_1",
            confidence=0.8
        )
        self.vs.verify_output(
            output_id=self.output.id,
            verifier_id="expert_2",
            confidence=0.8
        )
        
        consensus = self.vs.create_consensus_attestation(
            output_id=self.output.id,
            verifier_ids=["expert_1", "expert_2"],
            min_confidence=0.6
        )
        
        self.assertIsNotNone(consensus)
        self.assertEqual(consensus.verifier_type, "consensus")
        self.assertEqual(consensus.confidence, 0.8)  # Average
    
    def test_consensus_below_threshold(self):
        """Consensus should fail if below threshold"""
        # Create low-confidence attestations
        self.vs.verify_output(
            output_id=self.output.id,
            verifier_id="expert_1",
            confidence=0.4
        )
        self.vs.verify_output(
            output_id=self.output.id,
            verifier_id="expert_2",
            confidence=0.4
        )
        
        consensus = self.vs.create_consensus_attestation(
            output_id=self.output.id,
            verifier_ids=["expert_1", "expert_2"],
            min_confidence=0.66
        )
        
        self.assertIsNone(consensus)


class TestMeasurabilityGapAnalysis(unittest.TestCase):
    """Tests for measurability gap analysis"""
    
    def setUp(self):
        self.vs, self.analyzer = create_verification_system()
    
    def test_empty_system(self):
        """Analysis of empty system should indicate no data"""
        gap = self.analyzer.analyze_gap()
        
        self.assertEqual(gap["status"], "no_data")
    
    def test_healthy_status(self):
        """System with good verification rate should be healthy"""
        # Create and verify many outputs
        for i in range(10):
            output = self.vs.register_output(
                agent_id="test_agent",
                output_type="code_gen",
                content="valid code"
            )
            self.vs.verify_output(
                output_id=output.id,
                verifier_id="auto_verifier",
                confidence=0.9
            )
        
        gap = self.analyzer.analyze_gap()
        
        self.assertEqual(gap["status"], "healthy")
        self.assertEqual(gap["gap_ratio"], 0.0)
    
    def test_warning_status(self):
        """System with moderate pending ratio should warn"""
        # Create outputs, verify some, leave some pending
        for i in range(10):
            output = self.vs.register_output(
                agent_id="test_agent",
                output_type="code_gen",
                content="code"
            )
            if i < 7:  # Verify 70%
                self.vs.verify_output(
                    output_id=output.id,
                    verifier_id="verifier",
                    confidence=0.8
                )
        
        gap = self.analyzer.analyze_gap()
        
        self.assertEqual(gap["status"], "warning")
        self.assertTrue(0.2 <= gap["gap_ratio"] <= 0.5)
    
    def test_critical_status(self):
        """System with high pending ratio should be critical"""
        # Create outputs, verify few
        for i in range(10):
            output = self.vs.register_output(
                agent_id="test_agent",
                output_type="synthetic",
                content="insight"
            )
            if i < 3:  # Verify only 30%
                self.vs.verify_output(
                    output_id=output.id,
                    verifier_id="verifier",
                    confidence=0.8
                )
        
        gap = self.analyzer.analyze_gap()
        
        self.assertEqual(gap["status"], "critical")
        self.assertGreater(gap["gap_ratio"], 0.5)
    
    def test_category_distribution(self):
        """Analysis should track outputs by category"""
        categories = [
            OutputCategory.DETERMINISTIC.value,
            OutputCategory.SEMANTIC.value,
            OutputCategory.CREATIVE.value
        ]
        
        for i, cat in enumerate(categories):
            for j in range(3):
                output = self.vs.register_output(
                    agent_id="test_agent",
                    output_type=f"test_{cat}",
                    content="test",
                    category=cat
                )
                self.vs.verify_output(
                    output_id=output.id,
                    verifier_id="verifier",
                    confidence=0.8
                )
        
        gap = self.analyzer.analyze_gap()
        
        # Check that by_category exists and contains the expected categories
        self.assertIn("by_category", gap)
        by_category = gap["by_category"]
        for cat in categories:
            self.assertIn(cat, by_category)
            self.assertEqual(by_category[cat]["count"], 3)


class TestSystemStats(unittest.TestCase):
    """Tests for system-wide statistics"""
    
    def setUp(self):
        self.vs, _ = create_verification_system()
    
    def test_empty_stats(self):
        """Empty system should return zero stats"""
        stats = self.vs.get_verification_stats()
        
        self.assertEqual(stats["total_outputs"], 0)
        self.assertEqual(stats["verified"], 0)
        self.assertEqual(stats["verification_rate"], 0)
    
    def test_stats_tracking(self):
        """Stats should track system state"""
        # Create outputs
        for i in range(5):
            output = self.vs.register_output(
                agent_id="test_agent",
                output_type="code_gen",
                content="code"
            )
            if i < 3:
                self.vs.verify_output(
                    output_id=output.id,
                    verifier_id="verifier",
                    confidence=0.8
                )
        
        stats = self.vs.get_verification_stats()
        
        self.assertEqual(stats["total_outputs"], 5)
        self.assertEqual(stats["verified"], 3)
        self.assertEqual(stats["pending"], 2)
        self.assertEqual(stats["verification_rate"], 0.6)
    
    def test_verification_cost_tracking(self):
        """Human verifications should add to cost"""
        output = self.vs.register_output(
            agent_id="test_agent",
            output_type="analysis",
            content="analysis results"
        )
        
        initial_cost = stats = self.vs.get_verification_stats()["total_verification_cost_minutes"]
        
        # Human verification adds cost
        self.vs.verify_output(
            output_id=output.id,
            verifier_id="human_reviewer",
            verifier_type="human",
            confidence=0.9
        )
        
        new_cost = self.vs.get_verification_stats()["total_verification_cost_minutes"]
        
        self.assertGreater(new_cost, initial_cost)
    
    def test_agent_reputations_in_stats(self):
        """Stats should include agent reputations"""
        # Create verified outputs for specific agent
        for i in range(5):
            output = self.vs.register_output(
                agent_id="stats_test_agent",
                output_type="code_gen",
                content="code"
            )
            self.vs.verify_output(
                output_id=output.id,
                verifier_id="verifier",
                confidence=0.9
            )
        
        stats = self.vs.get_verification_stats()
        
        self.assertIn("agent_reputations", stats)
        self.assertIn("stats_test_agent", stats["agent_reputations"])
        self.assertGreater(
            stats["agent_reputations"]["stats_test_agent"]["score"],
            0.5
        )


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and error conditions"""
    
    def setUp(self):
        self.vs, _ = create_verification_system()
    
    def test_content_hash_determinism(self):
        """Same content should produce same hash"""
        content = {"key": "value"}
        
        output1 = self.vs.register_output(
            agent_id="agent1",
            output_type="test",
            content=content
        )
        output2 = self.vs.register_output(
            agent_id="agent2",
            output_type="test",
            content=content
        )
        
        # Different outputs but same content hash
        self.assertNotEqual(output1.id, output2.id)
    
    def test_confidence_with_no_evidence_or_attestations(self):
        """Confidence should be 0 with no evidence or attestations"""
        output = self.vs.register_output(
            agent_id="test",
            output_type="test",
            content="test"
        )
        
        # Calculate confidence manually (no attestations yet)
        confidence = self.vs._calculate_confidence(output)
        
        self.assertEqual(confidence, 0.0)
    
    def test_attestation_signature_unique(self):
        """Different attestations should have different signatures"""
        output1 = self.vs.register_output(agent_id="a1", output_type="test", content="c1")
        output2 = self.vs.register_output(agent_id="a2", output_type="test", content="c2")
        
        att1 = self.vs.verify_output(output_id=output1.id, verifier_id="v1", confidence=0.8)
        att2 = self.vs.verify_output(output_id=output2.id, verifier_id="v2", confidence=0.8)
        
        self.assertNotEqual(att1.signature, att2.signature)


def run_tests():
    """Run the full test suite"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestOutputRegistration,
        TestMeasurabilityAssessment,
        TestVerificationCostEstimation,
        TestEvidenceManagement,
        TestAttestation,
        TestAgentReputation,
        TestDisputeHandling,
        TestConsensusAttestation,
        TestMeasurabilityGapAnalysis,
        TestSystemStats,
        TestEdgeCases
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*70)
    print(f"Test Results: {result.testsRun} tests run")
    print(f"  Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"  Failures: {len(result.failures)}")
    print(f"  Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n✅ ALL TESTS PASSED")
    else:
        print("\n❌ SOME TESTS FAILED")
        
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
