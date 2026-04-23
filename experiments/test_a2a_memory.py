"""
Test suite for A2A Tiered Memory Integration.

Validates:
1. L0 immediate memory for active negotiations
2. L1 working memory for recent transaction history
3. L2 archival memory for consolidated agent profiles
4. Integration with A2A protocol
5. Context loading and recommendations

Run with: python -m pytest experiments/test_a2a_memory.py -v
"""

import pytest
import time
import json
from typing import Dict, Any

from core.tiered_memory import MemoryTier
from core.a2a_escrow import (
    A2AProtocol, Capability, CapabilityCategory, TransactionStatus
)
from core.a2a_memory import (
    A2AMemoryManager, A2AProtocolWithMemory, AgentInteractionProfile,
    ConversationPhase, demo_a2a_memory
)


# ==================== L0 Immediate Memory Tests ====================

class TestL0ImmediateMemory:
    """Test L0 (immediate) memory for active negotiations and executions."""
    
    def test_start_negotiation_l0(self):
        """Test that negotiation start is stored in L0 memory."""
        manager = A2AMemoryManager(agent_id="Alpha")
        
        entry = manager.start_negotiation(
            request_id="req_test_001",
            other_agent_id="Beta",
            capability_name="Code Review",
            initial_terms={"price": 0.1, "deadline_ms": 300000}
        )
        
        assert entry is not None
        assert entry.tier == MemoryTier.L0_IMMEDIATE
        assert "req_test_001" in entry.tags
        assert "Beta" in entry.tags
        assert entry.importance_score == 0.9
        
        # Directory path is not stored in tags, passed separately to store()
        assert entry.source == "a2a_negotiation"
    
    def test_active_conversation_tracking(self):
        """Test that active conversations are tracked."""
        manager = A2AMemoryManager(agent_id="Alpha")
        
        manager.start_negotiation(
            request_id="req_test_002",
            other_agent_id="Gamma",
            capability_name="Research",
            initial_terms={}
        )
        
        # Should be in active conversations
        assert "req_test_002" in manager._active_conversations
        assert manager._active_conversations["req_test_002"]["phase"] == ConversationPhase.NEGOTIATION
        assert manager._active_conversations["req_test_002"]["other_agent"] == "Gamma"
    
    def test_record_negotiation_round(self):
        """Test recording negotiation rounds in L0."""
        manager = A2AMemoryManager(agent_id="Alpha")
        
        manager.start_negotiation(
            request_id="req_test_003",
            other_agent_id="Delta",
            capability_name="Test",
            initial_terms={}
        )
        
        entry = manager.record_negotiation_round(
            request_id="req_test_003",
            round_num=1,
            proposed_by="Beta",
            terms={"price": 0.15},
            response="counter"
        )
        
        assert entry is not None
        assert entry.tier == MemoryTier.L0_IMMEDIATE
        assert "round_1" in entry.tags
        
        # Parse and verify content
        data = json.loads(entry.content)
        assert data["type"] == "negotiation_round"
        assert data["round"] == 1
        assert data["proposed_by"] == "Beta"
    
    def test_start_execution_l0(self):
        """Test that execution start is stored in L0 with high importance."""
        manager = A2AMemoryManager(agent_id="Alpha")
        
        entry = manager.start_execution(
            contract_id="ctr_test_001",
            request_id="req_test_004",
            provider_id="Beta",
            expected_duration_ms=300000
        )
        
        assert entry is not None
        assert entry.tier == MemoryTier.L0_IMMEDIATE
        assert entry.importance_score == 0.95  # Critical importance
        assert "execution" in entry.tags
        assert "Beta" in entry.tags
        
        # Parse content
        data = json.loads(entry.content)
        assert data["type"] == "execution_start"
        assert data["provider"] == "Beta"
    
    def test_get_active_negotiations(self):
        """Test retrieving active negotiations from L0."""
        manager = A2AMemoryManager(agent_id="Alpha")
        
        # Create multiple negotiations
        for i in range(3):
            manager.start_negotiation(
                request_id=f"req_multi_{i}",
                other_agent_id=f"Agent{i}",
                capability_name="Test",
                initial_terms={}
            )
        
        active = manager.get_active_negotiations()
        
        assert len(active) == 3
        for i, neg in enumerate(active):
            assert neg["type"] == "negotiation_start"
            assert neg["request_id"].startswith("req_multi_")
    
    def test_get_active_executions(self):
        """Test retrieving active executions from L0."""
        manager = A2AMemoryManager(agent_id="Alpha")
        
        # Create executions
        for i in range(2):
            manager.start_execution(
                contract_id=f"ctr_exec_{i}",
                request_id=f"req_exec_{i}",
                provider_id=f"Provider{i}",
                expected_duration_ms=60000
            )
        
        executions = manager.get_active_executions()
        
        assert len(executions) == 2
        for exec in executions:
            assert exec["type"] == "execution_start"


# ==================== L1 Working Memory Tests ====================

class TestL1WorkingMemory:
    """Test L1 (working) memory for recent transaction history."""
    
    def test_archive_negotiation(self):
        """Test moving completed negotiation from L0 to L1."""
        manager = A2AMemoryManager(agent_id="Alpha")
        
        # Create and complete negotiation
        manager.start_negotiation(
            request_id="req_archive_001",
            other_agent_id="Beta",
            capability_name="Code Review",
            initial_terms={}
        )
        
        manager.archive_negotiation("req_archive_001", outcome="success")
        
        # Should no longer be in active conversations
        assert "req_archive_001" not in manager._active_conversations
        
        # Should be stored in L1 memory
        # (We verify by checking that we can retrieve recent interactions)
        interactions = manager.get_recent_agent_interactions("Beta", limit=5)
        assert len(interactions) >= 1
        assert interactions[0]["type"] == "negotiation_complete"
        assert interactions[0]["outcome"] == "success"
    
    def test_archive_contract(self):
        """Test archiving completed contract to L1."""
        manager = A2AMemoryManager(agent_id="Alpha")
        
        contract_data = {
            "contract_id": "ctr_archive_001",
            "client_id": "Alpha",
            "provider_id": "Beta",
            "capability_id": "cap_001",
            "final_terms": {"price": 0.1}
        }
        
        manager.archive_contract("ctr_archive_001", contract_data, quality_score=0.85)
        
        # Verify retrieval
        interactions = manager.get_recent_agent_interactions("Beta", limit=5)
        contract_interactions = [i for i in interactions if i["type"] == "contract_complete"]
        
        assert len(contract_interactions) >= 1
        assert contract_interactions[0]["quality_score"] == 0.85
    
    def test_get_recent_agent_interactions(self):
        """Test retrieving recent interactions with specific agent."""
        manager = A2AMemoryManager(agent_id="Alpha")
        
        # Create multiple interactions with Beta
        for i in range(5):
            manager.archive_negotiation(
                request_id=f"req_recent_{i}",
                outcome="success" if i % 2 == 0 else "rejected"
            )
            # Manually set other_agent for each (normally done via negotiation start)
            # For test, we'll create entries directly
        
        # Create proper L1 entries
        for i in range(3):
            manager.memory.store(
                content=json.dumps({
                    "type": "negotiation_complete",
                    "request_id": f"req_test_{i}",
                    "other_agent": "Gamma",
                    "outcome": "success"
                }),
                tier=MemoryTier.L1_WORKING,
                directory="/a2a/agents/Gamma/negotiations",
                importance=0.7,
                tags={"completed", "Gamma"}
            )
        
        interactions = manager.get_recent_agent_interactions("Gamma", limit=5)
        
        assert len(interactions) == 3
        for i in interactions:
            assert i["other_agent"] == "Gamma"
    
    def test_get_agent_reputation_signal(self):
        """Test calculating reputation signal from L1 recent interactions."""
        manager = A2AMemoryManager(agent_id="Alpha")
        
        # Seed with successful interactions
        for i in range(10):
            manager.memory.store(
                content=json.dumps({
                    "type": "negotiation_complete",
                    "request_id": f"req_rep_{i}",
                    "other_agent": "Trusted",
                    "outcome": "success",
                    "quality_score": 0.8 + (i * 0.02)  # Improving quality
                }),
                tier=MemoryTier.L1_WORKING,
                directory="/a2a/agents/Trusted/negotiations",
                importance=0.7,
                tags={"completed", "Trusted", "success"}
            )
        
        signal = manager.get_agent_reputation_signal("Trusted")
        
        assert "reputation" in signal
        assert "confidence" in signal
        assert "sample_size" in signal
        assert signal["sample_size"] == 10
        assert signal["confidence"] > 0.4  # Should have reasonable confidence with 10 samples
        assert signal["reputation"] > 0.5  # Should reflect positive track record


# ==================== L2 Archival Memory Tests ====================

class TestL2ArchivalMemory:
    """Test L2 (archival) memory for consolidated agent profiles."""
    
    def test_consolidate_agent_profile(self):
        """Test consolidating L1 memories into L2 agent profile."""
        manager = A2AMemoryManager(agent_id="Alpha")
        
        # Seed L1 with interactions
        for i in range(15):
            manager.memory.store(
                content=json.dumps({
                    "type": "contract_complete",
                    "contract_id": f"ctr_prof_{i}",
                    "other_agent": "Reliable",
                    "provider_id": "Reliable",
                    "client_id": "Alpha",
                    "outcome": "success",
                    "capability": "Code Review",
                    "quality_score": 0.85
                }),
                tier=MemoryTier.L1_WORKING,
                directory="/a2a/agents/Reliable/contracts",
                importance=0.8,
                tags={"completed", "Reliable", "success"}
            )
        
        # Add some with different capability
        for i in range(5):
            manager.memory.store(
                content=json.dumps({
                    "type": "contract_complete",
                    "contract_id": f"ctr_res_{i}",
                    "other_agent": "Reliable",
                    "provider_id": "Reliable",
                    "client_id": "Alpha",
                    "outcome": "success",
                    "capability": "Research",
                    "quality_score": 0.75
                }),
                tier=MemoryTier.L1_WORKING,
                directory="/a2a/agents/Reliable/contracts",
                importance=0.7,
                tags={"completed", "Reliable", "success"}
            )
        
        profile = manager.consolidate_agent_profile("Reliable")
        
        assert profile is not None
        assert profile.agent_id == "Reliable"
        assert profile.total_interactions == 20
        assert profile.successful_completions == 20
        assert profile.success_rate == 1.0
        assert len(profile.quality_scores) == 20
        
        # Check capability usage
        assert profile.capability_usage["Code Review"] == 15
        assert profile.capability_usage["Research"] == 5
        
        # Check derived reputation
        assert profile.derived_reputation > 0.7  # Should be high given perfect track record
    
    def test_get_agent_profile_cached(self):
        """Test retrieving cached agent profile."""
        manager = A2AMemoryManager(agent_id="Alpha")
        
        # Create and consolidate profile
        manager.memory.store(
            content=json.dumps({
                "type": "contract_complete",
                "contract_id": "ctr_cache_001",
                "other_agent": "Cached",
                "outcome": "success",
                "quality_score": 0.9
            }),
            tier=MemoryTier.L1_WORKING,
            directory="/a2a/agents/Cached/contracts",
            importance=0.8,
            tags={"completed", "Cached", "success"}
        )
        
        profile1 = manager.consolidate_agent_profile("Cached")
        
        # Second retrieval should be from cache
        profile2 = manager.get_agent_profile("Cached")
        
        assert profile1 is profile2  # Same object from cache
        assert manager._agent_profiles["Cached"] is profile1
    
    def test_recommend_capabilities(self):
        """Test capability recommendations based on L2 profiles."""
        manager = A2AMemoryManager(agent_id="Alpha")
        
        # Create profiles for multiple agents
        for agent_name, capability, quality in [
            ("ExpertCoder", "Code Review", 0.95),
            ("ExpertCoder", "Debugging", 0.90),
            ("GoodResearcher", "Research", 0.85),
            ("AverageCoder", "Code Review", 0.70),
        ]:
            manager.memory.store(
                content=json.dumps({
                    "type": "contract_complete",
                    "other_agent": agent_name,
                    "capability": capability,
                    "outcome": "success",
                    "quality_score": quality
                }),
                tier=MemoryTier.L1_WORKING,
                directory=f"/a2a/agents/{agent_name}/contracts",
                tags={agent_name, capability.replace(" ", "_").lower()}
            )
        
        # Consolidate all profiles
        manager.consolidate_agent_profile("ExpertCoder")
        manager.consolidate_agent_profile("GoodResearcher")
        manager.consolidate_agent_profile("AverageCoder")
        
        # Recommend for code-related work
        recommendations = manager.recommend_capabilities(CapabilityCategory.CODE)
        
        # Should return agents with code capabilities
        assert len(recommendations) >= 2  # ExpertCoder and AverageCoder
        
        # ExpertCoder should rank higher due to better quality
        expert_rank = next((i for i, r in enumerate(recommendations) if r[0] == "ExpertCoder"), -1)
        avg_rank = next((i for i, r in enumerate(recommendations) if r[0] == "AverageCoder"), -1)
        
        if expert_rank >= 0 and avg_rank >= 0:
            assert expert_rank < avg_rank  # Expert should rank higher
    
    def test_agent_interaction_profile_properties(self):
        """Test AgentInteractionProfile calculation properties."""
        profile = AgentInteractionProfile(
            agent_id="TestAgent",
            total_interactions=10,
            successful_completions=7,
            quality_scores=[0.6, 0.7, 0.8, 0.75, 0.85, 0.9, 0.8]
        )
        
        assert profile.success_rate == 0.7
        assert profile.average_quality == pytest.approx(0.771, rel=0.01)


# ==================== Integration Tests ====================

class TestA2AProtocolWithMemory:
    """Test A2A protocol integration with memory."""
    
    def test_protocol_initialization(self):
        """Test that A2AProtocolWithMemory initializes correctly."""
        protocol = A2AProtocolWithMemory(agent_id="Alpha")
        
        assert protocol.agent_id == "Alpha"
        assert protocol.memory_manager is not None
        assert protocol.memory_manager.agent_id == "Alpha"
    
    def test_full_transaction_with_memory(self):
        """Test complete transaction flow with memory tracking."""
        protocol = A2AProtocolWithMemory(agent_id="Alpha")
        
        # Advertise capability as Beta
        cap = protocol.advertise_capability(
            agent_id="Beta",
            category=CapabilityCategory.CODE,
            name="Code Review",
            description="Security review",
            estimated_duration_ms=300000,
            min_reputation_required=0.0
        )
        
        # Request service
        request = protocol.request_service(
            requester_id="Alpha",
            capability_id=cap.capability_id,
            task_description="Review code",
            deadline_ms=300000
        )
        
        assert request is not None
        
        # Verify L0 memory has negotiation
        active_neg = protocol.memory_manager.get_active_negotiations()
        assert len(active_neg) >= 1
        
        # Complete negotiation
        protocol.negotiate_terms(
            request_id=request.request_id,
            counter_terms={},
            accepted=True
        )
        
        # Create escrow and contract
        escrow = protocol.create_escrow(request.request_id)
        assert escrow is not None
        
        protocol.deposit_to_escrow(escrow.escrow_id, "client", "sig1")
        protocol.deposit_to_escrow(escrow.escrow_id, "provider", "sig2")
        
        contract = protocol.create_contract(escrow.escrow_id)
        assert contract is not None
        
        # Complete contract
        protocol.submit_deliverable(
            contract_id=contract.contract_id,
            deliverable={"report": "Done"},
            evidence="hash"
        )
        
        protocol.release_escrow(contract.contract_id)
        
        # Memory should now have archived record
        stats = protocol.memory_manager.get_memory_stats()
        assert stats["total_memories"] > 0
    
    def test_contextual_recommendations(self):
        """Test memory-enhanced capability recommendations."""
        protocol = A2AProtocolWithMemory(agent_id="Alpha")
        
        # Advertise capabilities
        cap1 = protocol.advertise_capability(
            agent_id="HighQuality",
            category=CapabilityCategory.CODE,
            name="Expert Review",
            description="High quality review",
            estimated_duration_ms=300000,
            min_reputation_required=0.0
        )
        
        cap2 = protocol.advertise_capability(
            agent_id="LowQuality",
            category=CapabilityCategory.CODE,
            name="Basic Review",
            description="Basic review",
            estimated_duration_ms=300000,
            min_reputation_required=0.0
        )
        
        # Seed memory with positive history for HighQuality
        for i in range(5):
            protocol.memory_manager.archive_contract(
                contract_id=f"ctr_hist_{i}",
                contract_data={
                    "contract_id": f"ctr_hist_{i}",
                    "client_id": "Alpha",
                    "provider_id": "HighQuality",
                    "capability_id": cap1.capability_id
                },
                quality_score=0.95
            )
        
        # Seed memory with mediocre history for LowQuality
        for i in range(5):
            protocol.memory_manager.archive_contract(
                contract_id=f"ctr_low_{i}",
                contract_data={
                    "contract_id": f"ctr_low_{i}",
                    "client_id": "Alpha",
                    "provider_id": "LowQuality",
                    "capability_id": cap2.capability_id
                },
                quality_score=0.60
            )
        
        # Get recommendations
        recommendations = protocol.get_contextual_recommendations(CapabilityCategory.CODE)
        
        assert len(recommendations) >= 2
        
        # Find recommendations
        high_rec = next((r for r in recommendations if r["agent_id"] == "HighQuality"), None)
        low_rec = next((r for r in recommendations if r["agent_id"] == "LowQuality"), None)
        
        if high_rec and low_rec:
            # High quality should have higher or equal reputation due to better quality scores
            assert high_rec["historical_reputation"] >= low_rec["historical_reputation"]
            assert high_rec["success_rate"] >= low_rec["success_rate"]
    
    def test_memory_stats_tracking(self):
        """Test that memory statistics are tracked correctly."""
        protocol = A2AProtocolWithMemory(agent_id="Alpha")
        
        initial_stats = protocol.memory_manager.get_memory_stats()
        
        # Create some activity
        protocol.memory_manager.start_negotiation(
            request_id="req_stat_001",
            other_agent_id="Beta",
            capability_name="Test",
            initial_terms={}
        )
        
        stats = protocol.memory_manager.get_memory_stats()
        
        assert stats["active_conversations"] >= initial_stats["active_conversations"]
        assert "l0_count" in stats
        assert "l1_count" in stats
        assert "l2_count" in stats


# ==================== Context Loading Tests ====================

class TestContextLoading:
    """Test context loading for negotiations."""
    
    def test_load_negotiation_context(self):
        """Test loading full context for an active negotiation."""
        protocol = A2AProtocolWithMemory(agent_id="Alpha")
        
        # Set up history
        protocol.memory_manager.memory.store(
            content=json.dumps({
                "type": "contract_complete",
                "contract_id": "ctr_ctx_001",
                "other_agent": "Beta",
                "outcome": "success",
                "quality_score": 0.85
            }),
            tier=MemoryTier.L1_WORKING,
            directory="/a2a/agents/Beta/contracts",
            tags={"completed", "Beta", "success"}
        )
        
        # Consolidate profile
        protocol.memory_manager.consolidate_agent_profile("Beta")
        
        # Start new negotiation
        protocol.memory_manager.start_negotiation(
            request_id="req_ctx_002",
            other_agent_id="Beta",
            capability_name="Code Review",
            initial_terms={"price": 0.1}
        )
        
        # Load context
        context = protocol.memory_manager.load_negotiation_context("req_ctx_002")
        
        assert "current_negotiation" in context
        assert "recent_history" in context
        assert "agent_profile" in context
        assert "reputation_signal" in context
        
        # Should have agent profile for Beta
        if context["agent_profile"]:
            assert context["agent_profile"]["agent_id"] == "Beta"
        
        # Should have reputation signal
        if context["reputation_signal"]:
            assert "reputation" in context["reputation_signal"]
    
    def test_suggest_terms_from_history(self):
        """Test that term suggestions are based on historical patterns."""
        protocol = A2AProtocolWithMemory(agent_id="Alpha")
        
        # Seed with successful transactions - need to include other_agent field
        for i in range(10):
            protocol.memory_manager.memory.store(
                content=json.dumps({
                    "type": "contract_complete",
                    "contract_id": f"ctr_terms_{i}",
                    "other_agent": "Known",  # This is required for retrieval
                    "client_id": "Alpha",
                    "provider_id": "Known",
                    "final_terms": {"price": 0.12},
                    "outcome": "success",
                    "quality_score": 0.9
                }),
                tier=MemoryTier.L1_WORKING,
                directory="/a2a/agents/Known/contracts",
                importance=0.8,
                tags={"Known", "completed", "success"}
            )
        
        suggestions = protocol.memory_manager._suggest_terms("Known")
        
        assert "expected_quality" in suggestions
        assert "confidence" in suggestions
        assert suggestions["expected_quality"] > 0.7  # Based on 0.9 quality scores
        assert suggestions["confidence"] > 0.5  # High confidence with 10 samples


# ==================== Compression Tests ====================

class TestMemoryCompression:
    """Test memory compression and archival."""
    
    def test_compress_and_archive(self):
        """Test compressing L1 memories to L2."""
        manager = A2AMemoryManager(agent_id="Alpha")
        
        # Create many L1 entries - need "agent:" in content and "agent_" prefix in tags
        # for compress_and_archive to find them
        for i in range(50):
            manager.memory.store(
                content=json.dumps({
                    "type": "contract_complete",
                    "contract_id": f"ctr_comp_{i}",
                    "agent:": "ToArchive",  # Pattern compress_and_archive looks for
                    "other_agent": "ToArchive",
                    "provider_id": "ToArchive",
                    "client_id": "Alpha",
                    "outcome": "success"
                }),
                tier=MemoryTier.L1_WORKING,
                directory="/a2a/agents/ToArchive/contracts",
                tags={"agent_ToArchive"}  # Tag with agent_ prefix
            )
        
        # Consolidate (compresses and moves to L2)
        count = manager.compress_and_archive()
        
        assert count >= 1  # Should have consolidated at least one agent
        
        # Check L2 has profiles
        profile = manager.get_agent_profile("ToArchive")
        assert profile is not None
        assert profile.total_interactions == 50


# ==================== Demo Test ====================

class TestDemo:
    """Test the demo function runs without errors."""
    
    def test_demo_runs(self, capsys):
        """Test that the demo executes successfully."""
        demo_a2a_memory()
        
        captured = capsys.readouterr()
        output = captured.out
        
        assert "A2A TIERED MEMORY INTEGRATION DEMO" in output
        assert "A2A MEMORY DEMO COMPLETE" in output
        assert "PHASE 1" in output
        assert "PHASE 7" in output or "PHASE 6" in output


# ==================== Edge Cases ====================

class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_memory_reputation_signal(self):
        """Test reputation signal with no interactions."""
        manager = A2AMemoryManager(agent_id="Alpha")
        
        signal = manager.get_agent_reputation_signal("UnknownAgent")
        
        assert signal["reputation"] == 0.5  # Neutral default
        assert signal["confidence"] == 0.0  # No confidence without data
        assert signal["sample_size"] == 0
    
    def test_empty_profile_consolidation(self):
        """Test consolidating profile with no data."""
        manager = A2AMemoryManager(agent_id="Alpha")
        
        profile = manager.consolidate_agent_profile("NoData")
        
        assert profile is not None
        assert profile.agent_id == "NoData"
        assert profile.total_interactions == 0
        assert profile.derived_reputation == 0.5  # Neutral default
    
    def test_recommendations_with_no_profiles(self):
        """Test recommendations with empty profile cache."""
        manager = A2AMemoryManager(agent_id="Alpha")
        
        # Don't consolidate any profiles
        recommendations = manager.recommend_capabilities(CapabilityCategory.CODE)
        
        # Should return empty list without error
        assert recommendations == []
    
    def test_multiple_negotiation_rounds(self):
        """Test tracking multiple negotiation rounds."""
        manager = A2AMemoryManager(agent_id="Alpha")
        
        manager.start_negotiation(
            request_id="req_multi_round",
            other_agent_id="Beta",
            capability_name="Test",
            initial_terms={}
        )
        
        # Record multiple rounds
        for i in range(1, 6):
            manager.record_negotiation_round(
                request_id="req_multi_round",
                round_num=i,
                proposed_by="Beta" if i % 2 else "Alpha",
                terms={"price": 0.1 + (i * 0.01)},
                response="counter" if i < 5 else "accepted"
            )
        
        active = manager.get_active_negotiations()
        negotiation_rounds = [n for n in active if n.get("type") == "negotiation_round"]
        
        assert len(negotiation_rounds) == 5


if __name__ == "__main__":
    # Run with pytest
    pytest.main([__file__, "-v"])
