"""
Comprehensive tests for A2A (Agent-to-Agent) Protocol Implementation

Tests cover:
- Message envelope creation and serialization
- Agent registry and discovery
- Memory escrow operations (lock, commit, rollback)
- Delegation and handoff mechanisms
- End-to-end message routing
"""

import unittest
from datetime import datetime
import time
import sys
sys.path.insert(0, '/home/workspace/agi-research')

from core.a2a_protocol import (
    A2AProtocol, A2AEnvelope, AgentIdentity, AgentCapability,
    MessageType, EscrowAction, HandoffMode, A2AMemoryEscrow,
    A2ARegistry, create_a2a_protocol
)


class TestA2AEnvelope(unittest.TestCase):
    """Test message envelope functionality."""
    
    def test_create_envelope(self):
        """Test creating a basic envelope."""
        envelope = A2AEnvelope(
            message_id="msg-001",
            message_type=MessageType.REQUEST,
            sender_id="agent-a",
            recipient_id="agent-b",
            timestamp=datetime.now(),
            payload={"action": "query", "data": "test"}
        )
        
        self.assertEqual(envelope.message_id, "msg-001")
        self.assertEqual(envelope.message_type, MessageType.REQUEST)
        self.assertEqual(envelope.sender_id, "agent-a")
        self.assertEqual(envelope.payload["action"], "query")
    
    def test_envelope_serialization(self):
        """Test envelope to/from dict conversion."""
        original = A2AEnvelope(
            message_id="msg-002",
            message_type=MessageType.RESPONSE,
            sender_id="agent-x",
            recipient_id="agent-y",
            timestamp=datetime.now(),
            correlation_id="msg-001",
            payload={"result": "success"}
        )
        
        data = original.to_dict()
        restored = A2AEnvelope.from_dict(data)
        
        self.assertEqual(restored.message_id, original.message_id)
        self.assertEqual(restored.message_type, original.message_type)
        self.assertEqual(restored.correlation_id, original.correlation_id)
    
    def test_envelope_signing(self):
        """Test message signing and verification."""
        secret = "my-secret-key"
        envelope = A2AEnvelope(
            message_id="msg-003",
            message_type=MessageType.REQUEST,
            sender_id="agent-1",
            recipient_id="agent-2",
            timestamp=datetime.now(),
            payload={"data": "sensitive"}
        )
        
        # Sign the envelope
        envelope.sign(secret)
        self.assertIsNotNone(envelope.signature)
        
        # Verify with correct secret
        self.assertTrue(envelope.verify(secret))
        
        # Verify with wrong secret fails
        self.assertFalse(envelope.verify("wrong-secret"))


class TestA2ARegistry(unittest.TestCase):
    """Test agent registry functionality."""
    
    def setUp(self):
        self.registry = A2ARegistry()
    
    def test_register_agent(self):
        """Test registering an agent."""
        agent = AgentIdentity(
            agent_id="agent-001",
            name="Research Agent",
            capabilities=[
                AgentCapability("web_search", "Search the web", "1.0"),
                AgentCapability("summarize", "Summarize text", "1.0")
            ]
        )
        
        result = self.registry.register(agent)
        self.assertTrue(result)
        
        # Verify retrieval
        retrieved = self.registry.get_agent("agent-001")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, "Research Agent")
    
    def test_discover_by_capability(self):
        """Test discovering agents by capability."""
        # Register multiple agents
        for i in range(3):
            agent = AgentIdentity(
                agent_id=f"agent-{i}",
                name=f"Agent {i}",
                capabilities=[AgentCapability("web_search", f"Search {i}")]
            )
            self.registry.register(agent)
        
        # Add one with different capability
        special_agent = AgentIdentity(
            agent_id="agent-special",
            name="Special Agent",
            capabilities=[AgentCapability("code_gen", "Generate code")]
        )
        self.registry.register(special_agent)
        
        # Discover
        search_agents = self.registry.discover(capability="web_search")
        code_agents = self.registry.discover(capability="code_gen")
        
        self.assertEqual(len(search_agents), 3)
        self.assertEqual(len(code_agents), 1)
    
    def test_update_status(self):
        """Test updating agent status."""
        agent = AgentIdentity(
            agent_id="agent-status",
            name="Status Agent"
        )
        self.registry.register(agent)
        
        # Update status
        result = self.registry.update_status("agent-status", "busy")
        self.assertTrue(result)
        
        retrieved = self.registry.get_agent("agent-status")
        self.assertEqual(retrieved.status, "busy")
    
    def test_unregister_agent(self):
        """Test unregistering an agent."""
        agent = AgentIdentity(
            agent_id="agent-temp",
            name="Temporary Agent"
        )
        self.registry.register(agent)
        
        # Unregister
        result = self.registry.unregister("agent-temp")
        self.assertTrue(result)
        
        # Verify removal
        self.assertIsNone(self.registry.get_agent("agent-temp"))
    
    def test_message_routing(self):
        """Test routing messages to handlers."""
        received_messages = []
        
        def handler(envelope):
            received_messages.append(envelope)
            return A2AEnvelope(
                message_id="response-001",
                message_type=MessageType.RESPONSE,
                sender_id=envelope.recipient_id,
                recipient_id=envelope.sender_id,
                timestamp=datetime.now(),
                correlation_id=envelope.message_id,
                payload={"ack": True}
            )
        
        agent = AgentIdentity(agent_id="router-agent", name="Router")
        self.registry.register(agent, handler)
        
        # Send message
        message = A2AEnvelope(
            message_id="test-msg",
            message_type=MessageType.REQUEST,
            sender_id="sender",
            recipient_id="router-agent",
            timestamp=datetime.now(),
            payload={"test": True}
        )
        
        response = self.registry.route_message(message)
        
        self.assertEqual(len(received_messages), 1)
        self.assertEqual(response.message_type, MessageType.RESPONSE)


class TestA2AMemoryEscrow(unittest.TestCase):
    """Test memory escrow functionality."""
    
    def setUp(self):
        self.escrow = A2AMemoryEscrow()
    
    def test_create_escrow(self):
        """Test creating an escrow."""
        escrow_id = self.escrow.create_escrow(
            memory_key="shared-memory-1",
            owner_id="agent-owner",
            data={"value": 100},
            authorized_agents=["agent-1", "agent-2"]
        )
        
        self.assertIsNotNone(escrow_id)
        
        status = self.escrow.get_status(escrow_id)
        self.assertEqual(status["owner_id"], "agent-owner")
        self.assertEqual(status["version"], 0)
    
    def test_lock_and_write(self):
        """Test locking and writing to escrow."""
        escrow_id = self.escrow.create_escrow(
            memory_key="memory-2",
            owner_id="owner",
            data={"counter": 0},
            authorized_agents=["agent-a"]
        )
        
        # Lock
        result = self.escrow.lock(escrow_id, "agent-a")
        self.assertTrue(result)
        
        # Write
        result = self.escrow.write(escrow_id, "agent-a", {"counter": 1})
        self.assertTrue(result)
        
        # Verify
        data = self.escrow.read(escrow_id, "agent-a")
        self.assertEqual(data["counter"], 1)
    
    def test_lock_prevents_concurrent_access(self):
        """Test that lock prevents concurrent write access."""
        escrow_id = self.escrow.create_escrow(
            memory_key="memory-3",
            owner_id="owner",
            data={},
            authorized_agents=["agent-1", "agent-2"]
        )
        
        # Agent 1 locks
        self.assertTrue(self.escrow.lock(escrow_id, "agent-1"))
        
        # Agent 2 cannot lock
        self.assertFalse(self.escrow.lock(escrow_id, "agent-2"))
        
        # Agent 2 cannot write
        self.assertFalse(self.escrow.write(escrow_id, "agent-2", {"test": True}))
    
    def test_unauthorized_access(self):
        """Test unauthorized agents cannot access."""
        escrow_id = self.escrow.create_escrow(
            memory_key="memory-4",
            owner_id="owner",
            data={"secret": "data"},
            authorized_agents=["authorized-agent"]
        )
        
        # Unauthorized agent cannot lock
        result = self.escrow.lock(escrow_id, "unauthorized-agent")
        self.assertFalse(result)
        
        # Unauthorized agent cannot read
        data = self.escrow.read(escrow_id, "unauthorized-agent")
        self.assertIsNone(data)
    
    def test_commit_releases_lock(self):
        """Test commit releases the lock."""
        escrow_id = self.escrow.create_escrow(
            memory_key="memory-5",
            owner_id="owner",
            data={"state": "initial"},
            authorized_agents=["agent-a", "agent-b"]
        )
        
        # Lock and write
        self.escrow.lock(escrow_id, "agent-a")
        self.escrow.write(escrow_id, "agent-a", {"state": "modified"})
        self.escrow.commit(escrow_id, "agent-a")
        
        # Now agent-b can lock
        result = self.escrow.lock(escrow_id, "agent-b")
        self.assertTrue(result)
    
    def test_rollback(self):
        """Test rollback functionality."""
        escrow_id = self.escrow.create_escrow(
            memory_key="memory-6",
            owner_id="owner",
            data={"version": 1},
            authorized_agents=["agent-rollback"]
        )
        
        # Lock, modify and commit version 2
        self.escrow.lock(escrow_id, "agent-rollback")
        self.escrow.write(escrow_id, "agent-rollback", {"version": 2})
        self.escrow.commit(escrow_id, "agent-rollback")
        
        # Lock again and write version 3
        self.escrow.lock(escrow_id, "agent-rollback")
        self.escrow.write(escrow_id, "agent-rollback", {"version": 3})
        
        # Rollback to version 2 (committed version)
        result = self.escrow.rollback(escrow_id, "agent-rollback")
        self.assertTrue(result)
        
        # Verify rolled back to version 2
        data = self.escrow.read(escrow_id, "agent-rollback")
        self.assertEqual(data["version"], 2)


class TestA2AProtocol(unittest.TestCase):
    """Test full A2A protocol integration."""
    
    def setUp(self):
        self.protocol = create_a2a_protocol(secret="test-secret")
        
        # Register test agents
        self.agent_a = AgentIdentity(
            agent_id="agent-a",
            name="Agent A",
            capabilities=[AgentCapability("compute", "Perform calculations")]
        )
        self.agent_b = AgentIdentity(
            agent_id="agent-b",
            name="Agent B",
            capabilities=[AgentCapability("storage", "Store data")]
        )
    
    def test_create_and_send_message(self):
        """Test creating and sending a message."""
        # Register handler for agent-b
        def handler(envelope):
            return self.protocol.create_message(
                sender_id="agent-b",
                recipient_id=envelope.sender_id,
                message_type=MessageType.RESPONSE,
                payload={"received": True},
                correlation_id=envelope.message_id
            )
        
        self.protocol.registry.register(self.agent_b, handler)
        
        # Create and send message
        message = self.protocol.create_message(
            sender_id="agent-a",
            recipient_id="agent-b",
            message_type=MessageType.REQUEST,
            payload={"action": "test"}
        )
        
        response = self.protocol.send(message)
        
        self.assertIsNotNone(response)
        self.assertEqual(response.message_type, MessageType.RESPONSE)
    
    def test_discover_message(self):
        """Test capability discovery via protocol."""
        self.protocol.registry.register(self.agent_a)
        self.protocol.registry.register(self.agent_b)
        
        discover_msg = self.protocol.create_message(
            sender_id="agent-c",
            recipient_id="system",
            message_type=MessageType.DISCOVER,
            payload={"capability": "compute"}
        )
        
        response = self.protocol.send(discover_msg)
        
        self.assertEqual(response.message_type, MessageType.RESPONSE)
        self.assertEqual(len(response.payload["agents"]), 1)
        self.assertEqual(response.payload["agents"][0]["id"], "agent-a")
    
    def test_delegation(self):
        """Test task delegation."""
        # Register capable agent
        def handler(envelope):
            return self.protocol.create_message(
                sender_id="agent-delegate",
                recipient_id=envelope.sender_id,
                message_type=MessageType.RESPONSE,
                payload={"delegated": True, "result": "done"},
                correlation_id=envelope.message_id
            )
        
        delegate_agent = AgentIdentity(
            agent_id="agent-delegate",
            name="Delegate Agent",
            capabilities=[AgentCapability("analysis", "Analyze data")]
        )
        self.protocol.registry.register(delegate_agent, handler)
        
        # Send delegation request
        delegate_msg = self.protocol.create_message(
            sender_id="agent-requester",
            recipient_id="system",
            message_type=MessageType.DELEGATE,
            payload={
                "task": {"type": "analysis", "data": [1, 2, 3]},
                "requirements": ["analysis"]
            }
        )
        
        result = self.protocol.send(delegate_msg)
        
        # Should route to capable agent
        self.assertEqual(result.recipient_id, "agent-delegate")
        self.assertEqual(result.message_type, MessageType.REQUEST)
    
    def test_handoff(self):
        """Test conversation handoff."""
        def handler(envelope):
            return envelope  # Echo back
        
        new_agent = AgentIdentity(
            agent_id="agent-new",
            name="New Agent"
        )
        self.protocol.registry.register(new_agent, handler)
        
        handoff_msg = self.protocol.create_message(
            sender_id="agent-old",
            recipient_id="system",
            message_type=MessageType.HANDOFF,
            payload={
                "new_agent_id": "agent-new",
                "mode": "TEMPORARY",
                "context": {"conversation_id": "conv-123"}
            }
        )
        
        result = self.protocol.send(handoff_msg)
        
        self.assertEqual(result.recipient_id, "agent-new")
        self.assertEqual(result.message_type, MessageType.NOTIFY)
        self.assertEqual(result.payload["mode"], "TEMPORARY")
    
    def test_escrow_via_protocol(self):
        """Test escrow operations through protocol messages."""
        # Create escrow
        escrow_id = self.protocol.escrow.create_escrow(
            memory_key="protocol-memory",
            owner_id="agent-a",
            data={"shared": "data"},
            authorized_agents=["agent-a", "agent-b"]
        )
        
        # Lock via protocol
        lock_msg = self.protocol.create_message(
            sender_id="agent-a",
            recipient_id="system",
            message_type=MessageType.ESCROW,
            payload={"action": "LOCK", "escrow_id": escrow_id}
        )
        
        response = self.protocol.send(lock_msg)
        
        self.assertTrue(response.payload["success"])
        self.assertEqual(response.payload["action"], "LOCK")
    
    def test_message_history(self):
        """Test message history tracking."""
        # Register agents
        self.protocol.registry.register(self.agent_a)
        self.protocol.registry.register(self.agent_b)
        
        # Send multiple messages
        for i in range(5):
            msg = self.protocol.create_message(
                sender_id="agent-a",
                recipient_id="agent-b",
                message_type=MessageType.REQUEST,
                payload={"seq": i}
            )
            self.protocol.send(msg)
        
        # Check history
        history = self.protocol.get_message_history()
        self.assertGreaterEqual(len(history), 5)
        
        # Filter by agent
        agent_a_history = self.protocol.get_message_history(agent_id="agent-a")
        self.assertGreaterEqual(len(agent_a_history), 5)
        
        # Filter by type
        request_history = self.protocol.get_message_history(
            message_type=MessageType.REQUEST
        )
        self.assertGreaterEqual(len(request_history), 5)
    
    def test_signature_verification(self):
        """Test that protocol verifies signatures."""
        # Create signed message
        message = self.protocol.create_message(
            sender_id="agent-a",
            recipient_id="agent-b",
            message_type=MessageType.REQUEST,
            payload={"test": True},
            sign=True
        )
        
        # Should verify successfully
        self.assertTrue(message.verify(self.protocol.secret))
        
        # Tampered message should fail
        message.payload["test"] = False
        self.assertFalse(message.verify(self.protocol.secret))


class TestEndToEndWorkflows(unittest.TestCase):
    """Test end-to-end multi-agent workflows."""
    
    def test_collaborative_problem_solving(self):
        """Test collaborative problem solving between agents."""
        protocol = create_a2a_protocol()
        
        # Setup: Planner agent delegates to worker agents
        results = []
        
        def planner_handler(envelope):
            # Return acknowledgment
            return protocol.create_message(
                sender_id="planner",
                recipient_id=envelope.sender_id,
                message_type=MessageType.RESPONSE,
                payload={"plan_accepted": True}
            )
        
        def worker_handler(envelope):
            results.append(envelope.payload)
            return protocol.create_message(
                sender_id="worker",
                recipient_id=envelope.sender_id,
                message_type=MessageType.RESPONSE,
                payload={"task_complete": True}
            )
        
        planner = AgentIdentity(
            agent_id="planner",
            name="Planner Agent",
            capabilities=[AgentCapability("planning", "Create plans")]
        )
        worker = AgentIdentity(
            agent_id="worker",
            name="Worker Agent",
            capabilities=[AgentCapability("execution", "Execute tasks")]
        )
        
        protocol.registry.register(planner, planner_handler)
        protocol.registry.register(worker, worker_handler)
        
        # Workflow: Client requests plan, plan delegates to worker
        client_request = protocol.create_message(
            sender_id="client",
            recipient_id="planner",
            message_type=MessageType.REQUEST,
            payload={"request": "solve_problem", "problem": "complex-task"}
        )
        
        planner_response = protocol.send(client_request)
        self.assertIsNotNone(planner_response)
        
        # Planner delegates to worker
        delegate_msg = protocol.create_message(
            sender_id="planner",
            recipient_id="system",
            message_type=MessageType.DELEGATE,
            payload={
                "task": {"type": "execution", "problem": "complex-task"},
                "requirements": ["execution"]
            }
        )
        
        worker_task = protocol.send(delegate_msg)
        self.assertEqual(worker_task.recipient_id, "worker")
    
    def test_memory_sharing_workflow(self):
        """Test collaborative memory sharing via escrow."""
        protocol = create_a2a_protocol()
        
        # Create shared memory escrow
        escrow_id = protocol.escrow.create_escrow(
            memory_key="collaborative-data",
            owner_id="agent-alpha",
            data={"contributions": []},
            authorized_agents=["agent-alpha", "agent-beta"]
        )
        
        # Agent alpha locks and adds contribution
        protocol.escrow.lock(escrow_id, "agent-alpha")
        data = protocol.escrow.read(escrow_id, "agent-alpha")
        data["contributions"].append({"agent": "alpha", "value": "contribution-1"})
        protocol.escrow.write(escrow_id, "agent-alpha", data)
        protocol.escrow.commit(escrow_id, "agent-alpha")
        
        # Agent beta locks and adds contribution
        protocol.escrow.lock(escrow_id, "agent-beta")
        data = protocol.escrow.read(escrow_id, "agent-beta")
        data["contributions"].append({"agent": "beta", "value": "contribution-2"})
        protocol.escrow.write(escrow_id, "agent-beta", data)
        protocol.escrow.commit(escrow_id, "agent-beta")
        
        # Verify final state
        final_data = protocol.escrow.read(escrow_id, "agent-alpha")
        self.assertEqual(len(final_data["contributions"]), 2)
        self.assertEqual(final_data["contributions"][0]["agent"], "alpha")
        self.assertEqual(final_data["contributions"][1]["agent"], "beta")


def run_tests():
    """Run all A2A protocol tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestA2AEnvelope))
    suite.addTests(loader.loadTestsFromTestCase(TestA2ARegistry))
    suite.addTests(loader.loadTestsFromTestCase(TestA2AMemoryEscrow))
    suite.addTests(loader.loadTestsFromTestCase(TestA2AProtocol))
    suite.addTests(loader.loadTestsFromTestCase(TestEndToEndWorkflows))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
