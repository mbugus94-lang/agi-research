"""
Comprehensive tests for Agent-to-Agent (A2A) Escrow & Transaction Protocol.

Test coverage includes:
- Capability advertisement and discovery
- Service request and negotiation
- Escrow creation and management
- Contract lifecycle
- Attestation and settlement
- Dispute resolution
- Reputation-based access control
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.a2a_escrow import (
    A2AProtocol, Capability, CapabilityCategory, ServiceRequest,
    TransactionStatus, Attestation, Contract
)


class TestA2ACapabilityManagement(unittest.TestCase):
    """Test capability advertisement and discovery."""
    
    def setUp(self):
        self.a2a = A2AProtocol()
        self.agent_reputations = {
            "Alpha": 0.85,
            "Beta": 0.75,
            "Gamma": 0.60,
        }
        self.a2a.set_reputation_callback(lambda aid: self.agent_reputations.get(aid, 0.5))
    
    def test_advertise_capability(self):
        """Test basic capability advertisement."""
        cap = self.a2a.advertise_capability(
            agent_id="Beta",
            category=CapabilityCategory.CODE,
            name="Code Review",
            description="Security code review",
            estimated_duration_ms=300000,
            tags=["python", "security"]
        )
        
        self.assertIsNotNone(cap)
        self.assertTrue(cap.capability_id.startswith("cap_"))
        self.assertEqual(cap.agent_id, "Beta")
        self.assertEqual(cap.category, CapabilityCategory.CODE)
        self.assertEqual(cap.name, "Code Review")
        self.assertIn("python", cap.tags)
    
    def test_capability_success_rate_calculation(self):
        """Test success rate calculation for capabilities."""
        cap = self.a2a.advertise_capability(
            agent_id="Beta",
            category=CapabilityCategory.CODE,
            name="Test Cap",
            description="Test",
            estimated_duration_ms=1000
        )
        
        # Initial rate should be 0.5 (neutral)
        self.assertEqual(cap.calculate_success_rate(), 0.5)
        
        # After some transactions
        cap.total_requests = 10
        cap.successful_completions = 8
        self.assertEqual(cap.calculate_success_rate(), 0.8)
    
    def test_capability_availability_check(self):
        """Test capability can accept new requests."""
        cap = self.a2a.advertise_capability(
            agent_id="Beta",
            category=CapabilityCategory.CODE,
            name="Test Cap",
            description="Test",
            estimated_duration_ms=1000,
            max_concurrent=2
        )
        
        self.assertTrue(cap.can_accept_request())
        
        cap.current_requests = 2
        self.assertFalse(cap.can_accept_request())
        
        cap.is_available = False
        self.assertFalse(cap.can_accept_request())
    
    def test_discover_capabilities_by_category(self):
        """Test capability discovery by category."""
        self.a2a.advertise_capability(
            agent_id="Beta",
            category=CapabilityCategory.CODE,
            name="Code Review",
            description="Code review",
            estimated_duration_ms=300000
        )
        
        self.a2a.advertise_capability(
            agent_id="Gamma",
            category=CapabilityCategory.RESEARCH,
            name="Research",
            description="Web research",
            estimated_duration_ms=600000
        )
        
        code_caps = self.a2a.discover_capabilities(
            category=CapabilityCategory.CODE,
            available_only=False
        )
        
        self.assertEqual(len(code_caps), 1)
        self.assertEqual(code_caps[0].name, "Code Review")
    
    def test_discover_capabilities_by_tags(self):
        """Test capability discovery by tags."""
        self.a2a.advertise_capability(
            agent_id="Beta",
            category=CapabilityCategory.CODE,
            name="Security Review",
            description="Security review",
            estimated_duration_ms=300000,
            tags=["security", "python"]
        )
        
        self.a2a.advertise_capability(
            agent_id="Gamma",
            category=CapabilityCategory.CODE,
            name="Performance Review",
            description="Performance review",
            estimated_duration_ms=300000,
            tags=["performance", "python"]
        )
        
        results = self.a2a.discover_capabilities(
            tags=["security"],
            available_only=False
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Security Review")
    
    def test_discover_available_only(self):
        """Test filtering by availability."""
        cap = self.a2a.advertise_capability(
            agent_id="Beta",
            category=CapabilityCategory.CODE,
            name="Test Cap",
            description="Test",
            estimated_duration_ms=1000,
            max_concurrent=1
        )
        
        # Not available
        cap.current_requests = 1
        
        all_caps = self.a2a.discover_capabilities(
            category=CapabilityCategory.CODE,
            available_only=False
        )
        self.assertEqual(len(all_caps), 1)
        
        available_caps = self.a2a.discover_capabilities(
            category=CapabilityCategory.CODE,
            available_only=True
        )
        self.assertEqual(len(available_caps), 0)
    
    def test_capability_to_dict(self):
        """Test capability serialization."""
        cap = self.a2a.advertise_capability(
            agent_id="Beta",
            category=CapabilityCategory.CODE,
            name="Test",
            description="Test desc",
            estimated_duration_ms=1000,
            tags=["tag1"]
        )
        
        data = cap.to_dict()
        
        self.assertEqual(data["agent_id"], "Beta")
        self.assertEqual(data["category"], "code")
        self.assertEqual(data["name"], "Test")
        self.assertEqual(data["tags"], ["tag1"])
        self.assertIn("success_rate", data)
        self.assertIn("available_slots", data)


class TestA2AServiceRequests(unittest.TestCase):
    """Test service request and negotiation."""
    
    def setUp(self):
        self.a2a = A2AProtocol()
        self.a2a.set_reputation_callback(lambda aid: {"Alpha": 0.85, "Beta": 0.75}.get(aid, 0.5))
        
        self.cap = self.a2a.advertise_capability(
            agent_id="Beta",
            category=CapabilityCategory.CODE,
            name="Code Review",
            description="Code review service",
            estimated_duration_ms=300000,
            min_reputation_required=0.5
        )
    
    def test_request_service_success(self):
        """Test successful service request."""
        request = self.a2a.request_service(
            requester_id="Alpha",
            capability_id=self.cap.capability_id,
            task_description="Review my code",
            requirements={"language": "python"},
            proposed_payment={"type": "reputation", "amount": 0.1},
            deadline_ms=600000
        )
        
        self.assertIsNotNone(request)
        self.assertTrue(request.request_id.startswith("req_"))
        self.assertEqual(request.requester_id, "Alpha")
        self.assertEqual(request.provider_id, "Beta")
        self.assertEqual(request.status, TransactionStatus.PROPOSED)
    
    def test_request_service_reputation_too_low(self):
        """Test request rejected due to low reputation."""
        # Requester with reputation 0.3 < required 0.5
        request = self.a2a.request_service(
            requester_id="Charlie",  # Not in reputation dict, defaults to 0.5
            capability_id=self.cap.capability_id,
            task_description="Review my code",
            requirements={},
            proposed_payment={},
            deadline_ms=600000
        )
        
        # Charlie has 0.5 rep which meets 0.5 requirement, so passes
        # Let's test with higher requirement
        
        high_rep_cap = self.a2a.advertise_capability(
            agent_id="Beta",
            category=CapabilityCategory.CODE,
            name="Premium Service",
            description="High quality",
            estimated_duration_ms=300000,
            min_reputation_required=0.9  # Very high
        )
        
        request2 = self.a2a.request_service(
            requester_id="Alpha",  # Has 0.85 rep
            capability_id=high_rep_cap.capability_id,
            task_description="Review my code",
            requirements={},
            proposed_payment={},
            deadline_ms=600000
        )
        
        self.assertIsNone(request2)  # Rejected due to reputation
    
    def test_request_service_invalid_capability(self):
        """Test request with non-existent capability."""
        request = self.a2a.request_service(
            requester_id="Alpha",
            capability_id="cap_nonexistent",
            task_description="Review my code",
            requirements={},
            proposed_payment={},
            deadline_ms=600000
        )
        
        self.assertIsNone(request)
    
    def test_negotiate_terms_accepted(self):
        """Test accepting proposed terms."""
        request = self.a2a.request_service(
            requester_id="Alpha",
            capability_id=self.cap.capability_id,
            task_description="Review my code",
            requirements={},
            proposed_payment={},
            deadline_ms=600000
        )
        
        result = self.a2a.negotiate_terms(
            request_id=request.request_id,
            counter_terms={"deadline_ms": 300000},
            accepted=True
        )
        
        self.assertTrue(result)
        self.assertEqual(request.status, TransactionStatus.NEGOTIATING)
        self.assertIsNotNone(request.negotiated_terms)
    
    def test_negotiate_terms_counter(self):
        """Test proposing counter-terms."""
        request = self.a2a.request_service(
            requester_id="Alpha",
            capability_id=self.cap.capability_id,
            task_description="Review my code",
            requirements={},
            proposed_payment={},
            deadline_ms=600000
        )
        
        result = self.a2a.negotiate_terms(
            request_id=request.request_id,
            counter_terms={"deadline_ms": 300000, "payment": 0.15},
            accepted=False
        )
        
        self.assertTrue(result)
        self.assertEqual(request.negotiation_rounds, 1)
        self.assertEqual(request.negotiated_terms["deadline_ms"], 300000)
    
    def test_negotiate_max_rounds(self):
        """Test negotiation limited by max rounds."""
        request = self.a2a.request_service(
            requester_id="Alpha",
            capability_id=self.cap.capability_id,
            task_description="Review my code",
            requirements={},
            proposed_payment={},
            deadline_ms=600000
        )
        
        # Exhaust max negotiation rounds
        for i in range(request.max_negotiation_rounds + 2):
            result = self.a2a.negotiate_terms(
                request_id=request.request_id,
                counter_terms={},
                accepted=False
            )
        
        # Should eventually fail
        self.assertFalse(result)
    
    def test_request_expiration(self):
        """Test request expiration."""
        request = self.a2a.request_service(
            requester_id="Alpha",
            capability_id=self.cap.capability_id,
            task_description="Review my code",
            requirements={},
            proposed_payment={},
            deadline_ms=600000
        )
        
        # Manually set expiration to past
        request.expires_at = 0
        
        self.assertTrue(request.is_expired())
    
    def test_request_to_dict(self):
        """Test request serialization."""
        request = self.a2a.request_service(
            requester_id="Alpha",
            capability_id=self.cap.capability_id,
            task_description="Review my code",
            requirements={"key": "value"},
            proposed_payment={"type": "rep"},
            deadline_ms=600000
        )
        
        data = request.to_dict()
        
        self.assertEqual(data["requester_id"], "Alpha")
        self.assertEqual(data["provider_id"], "Beta")
        self.assertEqual(data["requirements"], {"key": "value"})
        self.assertEqual(data["status"], "proposed")


class TestA2AEscrow(unittest.TestCase):
    """Test escrow creation and management."""
    
    def setUp(self):
        self.a2a = A2AProtocol()
        self.a2a.set_reputation_callback(lambda aid: {"Alpha": 0.85, "Beta": 0.75}.get(aid, 0.5))
        
        self.cap = self.a2a.advertise_capability(
            agent_id="Beta",
            category=CapabilityCategory.CODE,
            name="Code Review",
            description="Code review",
            estimated_duration_ms=300000,
            min_reputation_required=0.5
        )
    
    def test_create_escrow_success(self):
        """Test successful escrow creation."""
        request = self.a2a.request_service(
            requester_id="Alpha",
            capability_id=self.cap.capability_id,
            task_description="Review my code",
            requirements={},
            proposed_payment={},
            deadline_ms=600000
        )
        
        self.a2a.negotiate_terms(request.request_id, {}, accepted=True)
        
        escrow = self.a2a.create_escrow(request.request_id)
        
        self.assertIsNotNone(escrow)
        self.assertTrue(escrow.escrow_id.startswith("esc_"))
        self.assertEqual(escrow.request_id, request.request_id)
        self.assertFalse(escrow.is_fully_funded())
    
    def test_create_escrow_not_negotiated(self):
        """Test escrow creation fails if not negotiated."""
        request = self.a2a.request_service(
            requester_id="Alpha",
            capability_id=self.cap.capability_id,
            task_description="Review my code",
            requirements={},
            proposed_payment={},
            deadline_ms=600000
        )
        
        # Don't negotiate
        escrow = self.a2a.create_escrow(request.request_id)
        
        self.assertIsNone(escrow)
    
    def test_deposit_to_escrow_client(self):
        """Test client deposit to escrow."""
        request = self.a2a.request_service(
            requester_id="Alpha",
            capability_id=self.cap.capability_id,
            task_description="Review my code",
            requirements={},
            proposed_payment={},
            deadline_ms=600000
        )
        
        self.a2a.negotiate_terms(request.request_id, {}, accepted=True)
        escrow = self.a2a.create_escrow(request.request_id)
        
        result = self.a2a.deposit_to_escrow(escrow.escrow_id, "client", "sig123")
        
        self.assertTrue(result)
        self.assertTrue(escrow.client_deposited)
        self.assertFalse(escrow.is_fully_funded())
    
    def test_deposit_to_escrow_provider(self):
        """Test provider deposit to escrow."""
        request = self.a2a.request_service(
            requester_id="Alpha",
            capability_id=self.cap.capability_id,
            task_description="Review my code",
            requirements={},
            proposed_payment={},
            deadline_ms=600000
        )
        
        self.a2a.negotiate_terms(request.request_id, {}, accepted=True)
        escrow = self.a2a.create_escrow(request.request_id)
        
        result = self.a2a.deposit_to_escrow(escrow.escrow_id, "provider", "sig456")
        
        self.assertTrue(result)
        self.assertTrue(escrow.provider_deposited)
    
    def test_fully_funded_escrow(self):
        """Test escrow fully funded."""
        request = self.a2a.request_service(
            requester_id="Alpha",
            capability_id=self.cap.capability_id,
            task_description="Review my code",
            requirements={},
            proposed_payment={},
            deadline_ms=600000
        )
        
        self.a2a.negotiate_terms(request.request_id, {}, accepted=True)
        escrow = self.a2a.create_escrow(request.request_id)
        
        self.a2a.deposit_to_escrow(escrow.escrow_id, "client", "sig123")
        self.a2a.deposit_to_escrow(escrow.escrow_id, "provider", "sig456")
        
        self.assertTrue(escrow.is_fully_funded())
        self.assertFalse(escrow.can_release())  # No attestation yet
    
    def test_escrow_expiration(self):
        """Test escrow expiration."""
        request = self.a2a.request_service(
            requester_id="Alpha",
            capability_id=self.cap.capability_id,
            task_description="Review my code",
            requirements={},
            proposed_payment={},
            deadline_ms=600000
        )
        
        self.a2a.negotiate_terms(request.request_id, {}, accepted=True)
        escrow = self.a2a.create_escrow(request.request_id)
        
        # Set deadline in the past
        escrow.deadline = 0
        
        self.assertTrue(escrow.is_expired())


class TestA2AContract(unittest.TestCase):
    """Test contract lifecycle."""
    
    def setUp(self):
        self.a2a = A2AProtocol()
        self.a2a.set_reputation_callback(lambda aid: {"Alpha": 0.85, "Beta": 0.75, "Verifier": 0.9}.get(aid, 0.5))
        
        self.cap = self.a2a.advertise_capability(
            agent_id="Beta",
            category=CapabilityCategory.CODE,
            name="Code Review",
            description="Code review",
            estimated_duration_ms=300000,
            min_reputation_required=0.5
        )
        
        # Create a complete workflow
        self.request = self.a2a.request_service(
            requester_id="Alpha",
            capability_id=self.cap.capability_id,
            task_description="Review my code",
            requirements={},
            proposed_payment={},
            deadline_ms=600000
        )
        
        self.a2a.negotiate_terms(self.request.request_id, {}, accepted=True)
        self.escrow = self.a2a.create_escrow(self.request.request_id)
        self.a2a.deposit_to_escrow(self.escrow.escrow_id, "client", "sig123")
        self.a2a.deposit_to_escrow(self.escrow.escrow_id, "provider", "sig456")
        self.contract = self.a2a.create_contract(self.escrow.escrow_id)
    
    def test_create_contract_success(self):
        """Test successful contract creation."""
        self.assertIsNotNone(self.contract)
        self.assertTrue(self.contract.contract_id.startswith("ctr_"))
        self.assertEqual(self.contract.client_id, "Alpha")
        self.assertEqual(self.contract.provider_id, "Beta")
        self.assertEqual(self.contract.status, TransactionStatus.ESCROWED)
    
    def test_create_contract_not_funded(self):
        """Test contract creation fails if escrow not funded."""
        # Create new request and escrow but don't fund
        request = self.a2a.request_service(
            requester_id="Alpha",
            capability_id=self.cap.capability_id,
            task_description="Review code 2",
            requirements={},
            proposed_payment={},
            deadline_ms=600000
        )
        
        self.a2a.negotiate_terms(request.request_id, {}, accepted=True)
        escrow = self.a2a.create_escrow(request.request_id)
        # Don't deposit
        
        contract = self.a2a.create_contract(escrow.escrow_id)
        self.assertIsNone(contract)
    
    def test_contract_to_dict(self):
        """Test contract serialization."""
        data = self.contract.to_dict()
        
        self.assertEqual(data["client_id"], "Alpha")
        self.assertEqual(data["provider_id"], "Beta")
        self.assertEqual(data["status"], "escrowed")
        self.assertIsNone(data["quality_score"])
        self.assertIsNone(data["completed_at"])
    
    def test_submit_deliverable(self):
        """Test deliverable submission."""
        # First start execution
        self.a2a.start_execution(self.contract.contract_id)
        
        result = self.a2a.submit_deliverable(
            contract_id=self.contract.contract_id,
            deliverable={"report": "All good"},
            evidence="evidence_hash_123"
        )
        
        self.assertTrue(result)
        self.assertEqual(len(self.contract.deliverables), 1)
        self.assertEqual(self.contract.deliverables[0]["data"]["report"], "All good")
    
    def test_create_attestation(self):
        """Test attestation creation."""
        att = self.a2a.create_attestation(
            contract_id=self.contract.contract_id,
            verifier_id="Verifier",
            claim="Work verified",
            evidence_hash="hash123",
            verification_score=0.85,
            private_key="key123"
        )
        
        self.assertIsNotNone(att)
        self.assertTrue(att.attestation_id.startswith("att_"))
        self.assertEqual(att.contract_id, self.contract.contract_id)
        self.assertEqual(att.verifier_id, "Verifier")
        self.assertEqual(att.verification_score, 0.85)
        self.assertIsNotNone(att.signature)  # Should be signed
    
    def test_release_escrow_success(self):
        """Test successful escrow release."""
        # Start execution
        self.a2a.start_execution(self.contract.contract_id)
        
        # Submit deliverable and create attestation
        self.a2a.submit_deliverable(
            contract_id=self.contract.contract_id,
            deliverable={"report": "All good"},
            evidence="hash"
        )
        
        self.a2a.create_attestation(
            contract_id=self.contract.contract_id,
            verifier_id="Verifier",
            claim="Verified",
            evidence_hash="hash",
            verification_score=0.85,
            private_key="key"
        )
        
        # Update capability stats for test
        self.cap.total_requests = 5
        self.cap.successful_completions = 4
        self.cap.average_quality_score = 0.8
        
        result = self.a2a.release_escrow(self.contract.contract_id)
        
        self.assertTrue(result)
        self.assertEqual(self.contract.status, TransactionStatus.COMPLETED)
        self.assertIsNotNone(self.contract.completed_at)
        self.assertIsNotNone(self.contract.quality_score)
        # Times should be approximately equal (within a few milliseconds)
        self.assertAlmostEqual(self.escrow.released_at, self.contract.completed_at, places=2)
    
    def test_release_escrow_no_attestation(self):
        """Test escrow release fails without attestation."""
        result = self.a2a.release_escrow(self.contract.contract_id)
        
        self.assertFalse(result)
    
    def test_release_escrow_insufficient_confidence(self):
        """Test escrow release fails with low attestation confidence."""
        # Start execution first
        self.a2a.start_execution(self.contract.contract_id)
        
        # Create attestation with very low score
        self.a2a.create_attestation(
            contract_id=self.contract.contract_id,
            verifier_id="Verifier",
            claim="Verified",
            evidence_hash="hash",
            verification_score=0.1,  # Too low
            private_key="key"
        )
        
        result = self.a2a.release_escrow(self.contract.contract_id)
        
        self.assertFalse(result)
    
    def test_capability_stats_updated_on_release(self):
        """Test capability stats update when escrow released."""
        # Start execution
        self.a2a.start_execution(self.contract.contract_id)
        
        # Setup for release
        self.a2a.submit_deliverable(
            contract_id=self.contract.contract_id,
            deliverable={"report": "All good"},
            evidence="hash"
        )
        
        self.a2a.create_attestation(
            contract_id=self.contract.contract_id,
            verifier_id="Verifier",
            claim="Verified",
            evidence_hash="hash",
            verification_score=0.9,
            private_key="key"
        )
        
        self.a2a.release_escrow(self.contract.contract_id)
        
        # Stats should be updated
        self.assertEqual(self.cap.successful_completions, 1)
        self.assertEqual(self.cap.average_quality_score, 0.9)


class TestA2ADisputeResolution(unittest.TestCase):
    """Test dispute resolution."""
    
    def setUp(self):
        self.a2a = A2AProtocol()
        self.a2a.set_reputation_callback(lambda aid: {"Alpha": 0.85, "Beta": 0.75}.get(aid, 0.5))
        
        self.cap = self.a2a.advertise_capability(
            agent_id="Beta",
            category=CapabilityCategory.CODE,
            name="Code Review",
            description="Code review",
            estimated_duration_ms=300000,
            min_reputation_required=0.5
        )
        
        # Create workflow
        request = self.a2a.request_service(
            requester_id="Alpha",
            capability_id=self.cap.capability_id,
            task_description="Review my code",
            requirements={},
            proposed_payment={},
            deadline_ms=600000
        )
        
        self.a2a.negotiate_terms(request.request_id, {}, accepted=True)
        escrow = self.a2a.create_escrow(request.request_id)
        self.a2a.deposit_to_escrow(escrow.escrow_id, "client", "sig123")
        self.a2a.deposit_to_escrow(escrow.escrow_id, "provider", "sig456")
        self.contract = self.a2a.create_contract(escrow.escrow_id)
    
    def test_raise_dispute(self):
        """Test raising a dispute."""
        result = self.a2a.raise_dispute(
            contract_id=self.contract.contract_id,
            raised_by="Alpha",
            reason="Deliverable not as specified"
        )
        
        self.assertTrue(result)
        self.assertEqual(self.contract.status, TransactionStatus.DISPUTED)
        self.assertEqual(self.a2a.stats["disputed_contracts"], 1)
    
    def test_raise_dispute_invalid_contract(self):
        """Test raising dispute for non-existent contract."""
        result = self.a2a.raise_dispute(
            contract_id="ctr_nonexistent",
            raised_by="Alpha",
            reason="Issue"
        )
        
        self.assertFalse(result)
    
    def test_resolve_dispute_client_wins(self):
        """Test dispute resolution - client wins."""
        self.a2a.raise_dispute(
            contract_id=self.contract.contract_id,
            raised_by="Alpha",
            reason="Issue"
        )
        
        result = self.a2a.resolve_dispute(
            contract_id=self.contract.contract_id,
            resolution="client_wins",
            arbiter_id="Arbiter"
        )
        
        self.assertTrue(result)
        self.assertEqual(self.contract.status, TransactionStatus.CANCELLED)
    
    def test_resolve_dispute_provider_wins(self):
        """Test dispute resolution - provider wins."""
        self.a2a.raise_dispute(
            contract_id=self.contract.contract_id,
            raised_by="Alpha",
            reason="Issue"
        )
        
        result = self.a2a.resolve_dispute(
            contract_id=self.contract.contract_id,
            resolution="provider_wins",
            arbiter_id="Arbiter"
        )
        
        self.assertTrue(result)
        self.assertEqual(self.contract.status, TransactionStatus.COMPLETED)
        self.assertEqual(self.contract.quality_score, 0.5)  # Neutral


class TestA2AProtocolStats(unittest.TestCase):
    """Test protocol statistics and analytics."""
    
    def setUp(self):
        self.a2a = A2AProtocol()
        self.a2a.set_reputation_callback(lambda aid: {"Alpha": 0.85, "Beta": 0.75, "Verifier": 0.9}.get(aid, 0.5))
    
    def test_get_protocol_stats_empty(self):
        """Test stats on empty protocol."""
        stats = self.a2a.get_protocol_stats()
        
        self.assertEqual(stats["total_capabilities"], 0)
        self.assertEqual(stats["active_contracts"], 0)
        self.assertEqual(stats["success_rate"], 0)  # No contracts yet
    
    def test_get_protocol_stats_with_data(self):
        """Test stats with transactions."""
        cap = self.a2a.advertise_capability(
            agent_id="Beta",
            category=CapabilityCategory.CODE,
            name="Code Review",
            description="Code review",
            estimated_duration_ms=300000,
            min_reputation_required=0.5
        )
        
        # Complete a workflow
        request = self.a2a.request_service(
            requester_id="Alpha",
            capability_id=cap.capability_id,
            task_description="Review code",
            requirements={},
            proposed_payment={},
            deadline_ms=600000
        )
        
        self.a2a.negotiate_terms(request.request_id, {}, accepted=True)
        escrow = self.a2a.create_escrow(request.request_id)
        self.a2a.deposit_to_escrow(escrow.escrow_id, "client", "sig")
        self.a2a.deposit_to_escrow(escrow.escrow_id, "provider", "sig")
        contract = self.a2a.create_contract(escrow.escrow_id)
        
        # Start execution before submitting
        self.a2a.start_execution(contract.contract_id)
        
        # Complete the contract
        self.a2a.submit_deliverable(contract.contract_id, {"result": "done"}, "hash")
        self.a2a.create_attestation(contract.contract_id, "Verifier", "done", "hash", 0.8, "key")
        self.a2a.release_escrow(contract.contract_id)
        
        stats = self.a2a.get_protocol_stats()
        
        self.assertEqual(stats["total_capabilities"], 1)
        self.assertEqual(stats["total_requests"], 1)
        self.assertEqual(stats["successful_contracts"], 1)
        self.assertEqual(stats["success_rate"], 1.0)
        self.assertEqual(stats["active_contracts"], 0)
    
    def test_get_agent_transaction_history(self):
        """Test agent transaction history."""
        cap = self.a2a.advertise_capability(
            agent_id="Beta",
            category=CapabilityCategory.CODE,
            name="Code Review",
            description="Code review",
            estimated_duration_ms=300000,
            min_reputation_required=0.5
        )
        
        # Create and complete workflow
        request = self.a2a.request_service(
            requester_id="Alpha",
            capability_id=cap.capability_id,
            task_description="Review code",
            requirements={},
            proposed_payment={},
            deadline_ms=600000
        )
        
        self.a2a.negotiate_terms(request.request_id, {}, accepted=True)
        escrow = self.a2a.create_escrow(request.request_id)
        self.a2a.deposit_to_escrow(escrow.escrow_id, "client", "sig")
        self.a2a.deposit_to_escrow(escrow.escrow_id, "provider", "sig")
        contract = self.a2a.create_contract(escrow.escrow_id)
        
        # Start execution
        self.a2a.start_execution(contract.contract_id)
        
        # Complete
        self.a2a.submit_deliverable(contract.contract_id, {"result": "done"}, "hash")
        self.a2a.create_attestation(contract.contract_id, "Verifier", "done", "hash", 0.8, "key")
        self.a2a.release_escrow(contract.contract_id)
        
        # Check Alpha's history
        alpha_history = self.a2a.get_agent_transaction_history("Alpha")
        self.assertEqual(alpha_history["total_transactions"], 1)
        self.assertEqual(len(alpha_history["contracts_as_client"]), 1)
        self.assertEqual(len(alpha_history["contracts_as_provider"]), 0)
        
        # Check Beta's history
        beta_history = self.a2a.get_agent_transaction_history("Beta")
        self.assertEqual(beta_history["total_transactions"], 1)
        self.assertEqual(len(beta_history["contracts_as_client"]), 0)
        self.assertEqual(len(beta_history["contracts_as_provider"]), 1)


class TestA2AIntegration(unittest.TestCase):
    """Integration tests for complete A2A workflows."""
    
    def test_complete_successful_workflow(self):
        """Test a complete successful agent transaction."""
        a2a = A2AProtocol()
        a2a.set_reputation_callback(lambda aid: {"Alpha": 0.85, "Beta": 0.75, "Verifier": 0.9}.get(aid, 0.5))
        
        # 1. Beta advertises capability
        cap = a2a.advertise_capability(
            agent_id="Beta",
            category=CapabilityCategory.CODE,
            name="Security Audit",
            description="Security code audit",
            estimated_duration_ms=300000,
            tags=["security", "audit"]
        )
        
        # 2. Alpha discovers capability
        results = a2a.discover_capabilities(category=CapabilityCategory.CODE)
        self.assertEqual(len(results), 1)
        
        # 3. Alpha requests service
        request = a2a.request_service(
            requester_id="Alpha",
            capability_id=cap.capability_id,
            task_description="Audit my code",
            requirements={"language": "python"},
            proposed_payment={"type": "reputation", "amount": 0.1},
            deadline_ms=600000
        )
        self.assertIsNotNone(request)
        
        # 4. Negotiate and agree
        a2a.negotiate_terms(request.request_id, {"payment": 0.15}, accepted=True)
        
        # 5. Create escrow
        escrow = a2a.create_escrow(request.request_id)
        self.assertIsNotNone(escrow)
        
        # 6. Fund escrow
        a2a.deposit_to_escrow(escrow.escrow_id, "client", "sig_alpha")
        a2a.deposit_to_escrow(escrow.escrow_id, "provider", "sig_beta")
        
        # 7. Create contract
        contract = a2a.create_contract(escrow.escrow_id)
        self.assertIsNotNone(contract)
        
        # 8. Start execution
        a2a.start_execution(contract.contract_id)
        
        # 9. Execute and submit
        a2a.submit_deliverable(contract.contract_id, {"report": "Secure"}, "hash")
        
        # 10. Attest
        a2a.create_attestation(contract.contract_id, "Verifier", "Verified", "hash", 0.95, "key")
        
        # 11. Release
        result = a2a.release_escrow(contract.contract_id)
        self.assertTrue(result)
        
        # Verify final state
        self.assertEqual(contract.status, TransactionStatus.COMPLETED)
        self.assertEqual(cap.successful_completions, 1)
    
    def test_reputation_based_rejection(self):
        """Test reputation-based access control."""
        a2a = A2AProtocol()
        a2a.set_reputation_callback(lambda aid: {"Alpha": 0.85, "LowRep": 0.2}.get(aid, 0.5))
        
        # High reputation requirement
        cap = a2a.advertise_capability(
            agent_id="Beta",
            category=CapabilityCategory.CODE,
            name="Premium Service",
            description="High quality service",
            estimated_duration_ms=300000,
            min_reputation_required=0.8  # High bar
        )
        
        # Low reputation agent gets rejected
        request = a2a.request_service(
            requester_id="LowRep",
            capability_id=cap.capability_id,
            task_description="Do work",
            requirements={},
            proposed_payment={},
            deadline_ms=600000
        )
        self.assertIsNone(request)
        
        # High reputation agent succeeds
        request = a2a.request_service(
            requester_id="Alpha",
            capability_id=cap.capability_id,
            task_description="Do work",
            requirements={},
            proposed_payment={},
            deadline_ms=600000
        )
        self.assertIsNotNone(request)
    
    def test_multiple_verifiers_attestation(self):
        """Test multiple verifiers with weighted confidence."""
        a2a = A2AProtocol()
        a2a.set_reputation_callback(
            lambda aid: {"Alpha": 0.85, "Beta": 0.75, "V1": 0.9, "V2": 0.8, "V3": 0.7}.get(aid, 0.5)
        )
        
        cap = a2a.advertise_capability(
            agent_id="Beta",
            category=CapabilityCategory.CODE,
            name="Test",
            description="Test",
            estimated_duration_ms=1000,
            min_reputation_required=0.0
        )
        
        # Setup workflow
        request = a2a.request_service(
            requester_id="Alpha",
            capability_id=cap.capability_id,
            task_description="Test",
            requirements={},
            proposed_payment={},
            deadline_ms=60000
        )
        a2a.negotiate_terms(request.request_id, {}, accepted=True)
        escrow = a2a.create_escrow(request.request_id)
        a2a.deposit_to_escrow(escrow.escrow_id, "client", "sig")
        a2a.deposit_to_escrow(escrow.escrow_id, "provider", "sig")
        contract = a2a.create_contract(escrow.escrow_id)
        a2a.submit_deliverable(contract.contract_id, {"result": "done"}, "hash")
        
        # Create attestations with varying confidence
        a2a.create_attestation(contract.contract_id, "V1", "done", "hash", 0.3, "key1")
        a2a.create_attestation(contract.contract_id, "V2", "done", "hash", 0.2, "key2")
        a2a.create_attestation(contract.contract_id, "V3", "done", "hash", 0.1, "key3")
        
        # Total confidence = 0.6, should pass (need > 0.5)
        result = a2a.release_escrow(contract.contract_id)
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
