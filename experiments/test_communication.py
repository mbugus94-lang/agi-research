"""
Tests for Multi-Agent Communication Protocol.

Validates:
1. Agent registration and identity management
2. Message passing (direct and broadcast)
3. Cryptographic message signing and verification
4. Reputation scoring and updates
5. Union formation and social dynamics
6. Network topology and routing
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.communication import (
    CommunicationProtocol, MessageType, AgentRole,
    Message, ReputationScore, SocialUnion
)


def test_agent_registration():
    """Test 1: Agent registration and identity."""
    print("\n[TEST 1] Agent Registration")
    protocol = CommunicationProtocol()
    
    # Register agents with different roles
    protocol.register_agent("Worker1", AgentRole.WORKER)
    protocol.register_agent("Coord1", AgentRole.COORDINATOR)
    protocol.register_agent("Spec1", AgentRole.SPECIALIST)
    
    assert len(protocol.agents) == 3, f"Expected 3 agents, got {len(protocol.agents)}"
    assert protocol.agents["Worker1"].role == AgentRole.WORKER
    assert protocol.agents["Coord1"].role == AgentRole.COORDINATOR
    
    # Check reputation initialized
    assert "Worker1" in protocol.reputations
    assert protocol.reputations["Worker1"].overall == 0.5  # Default
    
    print("   ✅ All agents registered with correct roles and initial reputation")
    return True


def test_network_connections():
    """Test 2: Network topology and connections."""
    print("\n[TEST 2] Network Connections")
    protocol = CommunicationProtocol()
    
    # Register agents
    for i in range(4):
        protocol.register_agent(f"Agent{i}", AgentRole.WORKER)
    
    # Create connections
    protocol.connect_agents("Agent0", "Agent1")
    protocol.connect_agents("Agent0", "Agent2")
    protocol.connect_agents("Agent2", "Agent3")
    
    # Verify bidirectional
    assert "Agent1" in protocol.agents["Agent0"].connections
    assert "Agent0" in protocol.agents["Agent1"].connections
    assert "Agent2" in protocol.routing_table["Agent0"]
    
    # Check no connection between 1 and 2
    assert "Agent2" not in protocol.agents["Agent1"].connections
    
    print("   ✅ Bidirectional connections established correctly")
    return True


def test_direct_messaging():
    """Test 3: Direct message passing."""
    print("\n[TEST 3] Direct Messaging")
    protocol = CommunicationProtocol()
    
    protocol.register_agent("Sender", AgentRole.WORKER)
    protocol.register_agent("Receiver", AgentRole.WORKER)
    protocol.connect_agents("Sender", "Receiver")
    
    # Send direct message
    content = {"task": "Analyze data", "priority": "high"}
    msg = protocol.send_message(
        "Sender", "Receiver", MessageType.DIRECT, content, priority=8
    )
    
    assert msg is not None, "Message should be created"
    assert msg.sender_id == "Sender"
    assert msg.recipient_id == "Receiver"
    assert msg.content == content
    assert msg.priority == 8
    assert msg.signature is not None, "Message should be signed"
    
    # Verify message in inbox
    inbox = protocol.read_inbox("Receiver", mark_read=False)
    assert len(inbox) == 1
    assert inbox[0].content == content
    
    print("   ✅ Direct messaging with signing works correctly")
    return True


def test_broadcast_messaging():
    """Test 4: Broadcast messaging."""
    print("\n[TEST 4] Broadcast Messaging")
    protocol = CommunicationProtocol()
    
    # Create star topology (center connected to all)
    protocol.register_agent("Center", AgentRole.COORDINATOR)
    for i in range(3):
        protocol.register_agent(f"Node{i}", AgentRole.WORKER)
        protocol.connect_agents("Center", f"Node{i}")
    
    # Broadcast requires minimum reputation
    # Default reputation is 0.5, which exceeds threshold of 0.3
    content = {"announcement": "System update"}
    msg = protocol.send_message(
        "Center", None, MessageType.BROADCAST, content, priority=9
    )
    
    assert msg is not None
    assert msg.recipient_id is None  # Broadcast
    
    # Check all connected agents received it
    for i in range(3):
        inbox = protocol.read_inbox(f"Node{i}", mark_read=False)
        assert len(inbox) == 1, f"Node{i} should have 1 message"
        assert inbox[0].content == content
    
    # Center should not receive its own broadcast
    center_inbox = protocol.read_inbox("Center", mark_read=False)
    assert len(center_inbox) == 0
    
    print("   ✅ Broadcast messaging reaches all connected agents")
    return True


def test_reputation_gating():
    """Test 5: Reputation-based message gating."""
    print("\n[TEST 5] Reputation Gating")
    protocol = CommunicationProtocol()
    
    # Create low-reputation agent
    protocol.register_agent("LowRep", AgentRole.WORKER)
    protocol.register_agent("Receiver", AgentRole.WORKER)
    protocol.connect_agents("LowRep", "Receiver")
    
    # Manually lower reputation
    protocol.reputations["LowRep"].overall = 0.2
    protocol.reputations["LowRep"].competence = 0.2
    protocol.reputations["LowRep"].reliability = 0.2
    
    # Try to broadcast (requires 0.3 reputation)
    msg = protocol.send_message(
        "LowRep", None, MessageType.BROADCAST, {"test": "data"}
    )
    
    assert msg is None, "Low reputation agent should not be able to broadcast"
    
    # Direct message should still work (no reputation gate)
    msg = protocol.send_message(
        "LowRep", "Receiver", MessageType.DIRECT, {"test": "data"}
    )
    assert msg is not None, "Direct messages should not be gated by reputation"
    
    print("   ✅ Reputation correctly gates broadcast privileges")
    return True


def test_reputation_updates():
    """Test 6: Reputation scoring and updates."""
    print("\n[TEST 6] Reputation Updates")
    protocol = CommunicationProtocol()
    
    protocol.register_agent("Rater", AgentRole.WORKER)
    protocol.register_agent("Rated", AgentRole.WORKER)
    
    # Initial reputation
    initial = protocol.reputations["Rated"].overall
    assert initial == 0.5
    
    # Positive interaction
    protocol.update_reputation("Rated", "Rater", True, {
        "competence": 0.9, "reliability": 0.9, "honesty": 0.9, "cooperation": 0.9
    })
    
    # Reputation should increase
    new_rep = protocol.reputations["Rated"].overall
    assert new_rep > initial, f"Reputation should increase, got {new_rep} vs {initial}"
    assert protocol.reputations["Rated"].competence > 0.5
    
    # Negative interaction
    protocol.update_reputation("Rated", "Rater", False, {
        "competence": 0.3, "reliability": 0.2, "honesty": 0.5, "cooperation": 0.3
    })
    
    # Reputation should decrease
    final_rep = protocol.reputations["Rated"].overall
    # Should be between initial and new_rep but weighted by failure
    assert protocol.reputations["Rated"].successful_interactions == 1
    assert protocol.reputations["Rated"].failed_interactions == 1
    
    print(f"   ✅ Reputation updates correctly (initial: {initial:.3f}, current: {final_rep:.3f})")
    return True


def test_reputation_weighted_rating():
    """Test 7: High-reputation raters have more influence."""
    print("\n[TEST 7] Weighted Reputation Rating")
    protocol = CommunicationProtocol()
    
    protocol.register_agent("HighRepRater", AgentRole.WORKER)
    protocol.register_agent("LowRepRater", AgentRole.WORKER)
    protocol.register_agent("Rated", AgentRole.WORKER)
    
    # Set up rater reputations
    protocol.reputations["HighRepRater"].overall = 0.9
    protocol.reputations["LowRepRater"].overall = 0.3
    
    # Low rep rater gives high ratings
    protocol.update_reputation("Rated", "LowRepRater", True, {
        "competence": 0.9, "reliability": 0.9
    })
    after_low = protocol.reputations["Rated"].competence
    
    # High rep rater gives low ratings
    protocol.update_reputation("Rated", "HighRepRater", False, {
        "competence": 0.2, "reliability": 0.2
    })
    after_high = protocol.reputations["Rated"].competence
    
    # High rep rater's low rating should have more impact
    assert after_high < after_low, "High rep rater should have more influence"
    
    print(f"   ✅ Weighted rating works (low rater impact: {after_low:.3f}, high rater impact: {after_high:.3f})")
    return True


def test_union_formation():
    """Test 8: Union/syndicate formation."""
    print("\n[TEST 8] Union Formation")
    protocol = CommunicationProtocol()
    
    # Create high-reputation founders
    protocol.register_agent("Founder1", AgentRole.COORDINATOR)
    protocol.register_agent("Founder2", AgentRole.SPECIALIST)
    
    # Boost reputations
    protocol.reputations["Founder1"].overall = 0.8
    protocol.reputations["Founder2"].overall = 0.75
    
    # Form union
    union = protocol.form_union(
        name="Test Union",
        purpose="Testing social dynamics",
        founder_ids=["Founder1", "Founder2"],
        governance_model="democratic"
    )
    
    assert union is not None, "Union should be formed"
    assert len(union.founders) == 2
    assert "Founder1" in union.members
    assert union.coordinator_id == "Founder1"
    assert union.governance_model == "democratic"
    
    # Check agents know about union
    assert union.id in protocol.agents["Founder1"].unions
    
    print(f"   ✅ Union formed with {len(union.members)} members")
    return True


def test_union_restriction():
    """Test 9: Union formation with insufficient reputation."""
    print("\n[TEST 9] Union Reputation Restriction")
    protocol = CommunicationProtocol()
    
    protocol.register_agent("LowRep1", AgentRole.WORKER)
    protocol.register_agent("LowRep2", AgentRole.WORKER)
    
    # Keep default/low reputation - manually set below threshold
    protocol.reputations["LowRep1"].overall = 0.3
    protocol.reputations["LowRep2"].overall = 0.3
    protocol.reputations["LowRep1"].competence = 0.3
    protocol.reputations["LowRep1"].reliability = 0.3
    
    # Try to form union (requires 0.4 rep)
    union = protocol.form_union(
        name="Bad Union",
        purpose="Should fail",
        founder_ids=["LowRep1", "LowRep2"]
    )
    
    assert union is None, "Low-reputation founders should not form union"
    assert len(protocol.unions) == 0
    
    print("   ✅ Low-reputation agents correctly blocked from forming unions")
    return True


def test_union_joining():
    """Test 10: Joining unions with reputation check."""
    print("\n[TEST 10] Union Membership")
    protocol = CommunicationProtocol()
    
    # Setup: high-rep founders, medium and low rep workers
    protocol.register_agent("Founder", AgentRole.COORDINATOR)
    protocol.reputations["Founder"].overall = 0.8
    
    protocol.register_agent("MedRep", AgentRole.WORKER)
    protocol.reputations["MedRep"].overall = 0.6
    
    protocol.register_agent("LowRep", AgentRole.WORKER)
    protocol.reputations["LowRep"].overall = 0.3
    
    # Form union
    union = protocol.form_union(
        name="Quality Collective",
        purpose="High-quality work",
        founder_ids=["Founder"],
        min_reputation_to_join=0.4
    )
    
    # Med rep can join
    success_med = protocol.join_union("MedRep", union.id)
    assert success_med, "Medium reputation should allow joining"
    
    # Low rep cannot join
    success_low = protocol.join_union("LowRep", union.id)
    assert not success_low, "Low reputation should be rejected"
    
    assert "MedRep" in union.members
    assert "LowRep" not in union.members
    
    print(f"   ✅ Union membership correctly gated by reputation")
    return True


def test_message_crypto():
    """Test 11: Message signing and verification."""
    print("\n[TEST 11] Cryptographic Signatures")
    
    protocol = CommunicationProtocol()
    protocol.register_agent("Alice", AgentRole.WORKER)
    protocol.register_agent("Bob", AgentRole.WORKER)
    
    # Get keys
    alice_private = protocol.agents["Alice"].private_key
    alice_public = protocol.agents["Alice"].public_key
    
    # Create and sign message
    msg = Message(
        id="test123",
        sender_id="Alice",
        recipient_id="Bob",
        message_type=MessageType.DIRECT,
        content={"test": "message"}
    )
    
    signature = msg.sign(alice_private)
    assert msg.signature is not None
    assert len(msg.signature) == 16  # Our truncated SHA256
    
    # Verify with correct key
    valid = msg.verify(alice_public)
    assert valid, "Signature should verify with correct public key"
    
    # Wrong key should fail
    bob_public = protocol.agents["Bob"].public_key
    invalid = msg.verify(bob_public)
    assert not invalid, "Wrong key should fail verification"
    
    print("   ✅ Message signing and verification works correctly")
    return True


def test_union_decay():
    """Test 12: Union thermodynamic decay."""
    print("\n[TEST 12] Union Energy Decay")
    protocol = CommunicationProtocol()
    
    protocol.register_agent("Founder", AgentRole.COORDINATOR)
    protocol.reputations["Founder"].overall = 0.8
    
    union = protocol.form_union("Active Union", "Testing", founder_ids=["Founder"])
    
    initial_energy = union.energy_level
    assert initial_energy == 1.0
    
    # Record activity (increases energy)
    union.record_activity("task_completed", value=0.2)
    assert union.energy_level == 1.0  # Already at max
    
    # Simulate decay
    import time
    union.last_activity = time.time() - 3600  # 1 hour ago
    union.decay()
    
    assert union.energy_level < initial_energy, "Energy should decay after inactivity"
    
    print(f"   ✅ Union energy decays correctly ({initial_energy} → {union.energy_level:.3f})")
    return True


def test_top_reputation():
    """Test 13: Top reputation agent ranking."""
    print("\n[TEST 13] Reputation Rankings")
    protocol = CommunicationProtocol()
    
    # Create agents with varied reputations
    reps = [0.3, 0.45, 0.6, 0.75, 0.9]
    for i, rep_val in enumerate(reps):
        protocol.register_agent(f"Agent{i}", AgentRole.WORKER)
        protocol.reputations[f"Agent{i}"].overall = rep_val
    
    # Get top 3
    top = protocol.get_top_reputation_agents(3)
    
    assert len(top) == 3
    # Should be ordered by reputation (highest first)
    assert top[0][0] == "Agent4", f"Expected Agent4, got {top[0][0]}"  # Highest
    assert top[0][1] > top[1][1], "Should be sorted descending"
    assert top[1][1] > top[2][1]
    
    print(f"   ✅ Reputation ranking correct: {[a for a, _ in top]}")
    return True


def test_network_stats():
    """Test 14: Network statistics aggregation."""
    print("\n[TEST 14] Network Statistics")
    protocol = CommunicationProtocol()
    
    # Setup network
    for i in range(3):
        protocol.register_agent(f"A{i}", AgentRole.WORKER)
    protocol.connect_agents("A0", "A1")
    protocol.connect_agents("A1", "A2")
    
    # Send some messages
    protocol.send_message("A0", "A1", MessageType.DIRECT, {"test": 1})
    protocol.send_message("A1", None, MessageType.BROADCAST, {"test": 2})
    
    # Get stats
    stats = protocol.get_network_stats()
    
    assert stats["total_agents"] == 3
    assert stats["total_connections"] == 2  # A0-A1 and A1-A2 (bidirectional = 4/2)
    # Note: broadcasts don't stay in inbox, they're processed
    assert "average_reputation" in stats
    
    print(f"   ✅ Network stats: {stats['total_agents']} agents, {stats['total_connections']} connections")
    return True


def test_message_priority():
    """Test 15: Message priority sorting."""
    print("\n[TEST 15] Message Priority")
    protocol = CommunicationProtocol()
    
    protocol.register_agent("Sender", AgentRole.WORKER)
    protocol.register_agent("Receiver", AgentRole.WORKER)
    protocol.connect_agents("Sender", "Receiver")
    
    # Send messages with different priorities
    protocol.send_message("Sender", "Receiver", MessageType.DIRECT, {"n": 1}, priority=3)
    protocol.send_message("Sender", "Receiver", MessageType.DIRECT, {"n": 2}, priority=9)
    protocol.send_message("Sender", "Receiver", MessageType.DIRECT, {"n": 3}, priority=5)
    
    # Read inbox (should be sorted by priority)
    inbox = protocol.read_inbox("Receiver", mark_read=False)
    
    # Highest priority first
    assert inbox[0].priority == 9
    assert inbox[1].priority == 5
    assert inbox[2].priority == 3
    
    print("   ✅ Messages correctly sorted by priority")
    return True


def run_all_tests():
    """Run all communication protocol tests."""
    print("="*60)
    print("🧪 Multi-Agent Communication Protocol Tests")
    print("="*60)
    
    tests = [
        test_agent_registration,
        test_network_connections,
        test_direct_messaging,
        test_broadcast_messaging,
        test_reputation_gating,
        test_reputation_updates,
        test_reputation_weighted_rating,
        test_union_formation,
        test_union_restriction,
        test_union_joining,
        test_message_crypto,
        test_union_decay,
        test_top_reputation,
        test_network_stats,
        test_message_priority,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"   ❌ FAILED")
        except Exception as e:
            failed += 1
            print(f"   ❌ EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*60)
    print(f"📊 Test Results: {passed}/{len(tests)} passed")
    if failed == 0:
        print("✅ ALL TESTS PASSED!")
    else:
        print(f"❌ {failed} tests failed")
    print("="*60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
