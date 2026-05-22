"""
Test suite for Multi-Agent Coordination System.

Tests cover:
- Agent pool registration and retrieval
- Task routing and decomposition
- Parallel execution
- Consensus building strategies
- Shared memory communication
- End-to-end multi-agent collaboration
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass
from typing import Dict, Any, List

from core.multi_agent import (
    AgentPool, TaskRouter, ConsensusBuilder, SharedMemory, MultiAgentOrchestrator,
    AgentRole, AgentCapability, AgentProfile, SubTask, TaskStatus,
    ConsensusStrategy, ConsensusResult,
    create_orchestrator, quick_collaborate
)


class MockAgent:
    """Mock agent for testing"""
    def __init__(self, name: str, success_rate: float = 0.9):
        self.name = name
        self.success_rate = success_rate
        self.run_calls = []
    
    def run(self, goal: str, initial_context: Dict[str, Any] = None):
        self.run_calls.append((goal, initial_context))
        
        @dataclass
        class MockResult:
            success: bool
            output: Any
            execution_time: float
            thoughts: List = None
            observations: List = None
        
        import random
        success = random.random() < self.success_rate
        
        return MockResult(
            success=success,
            output={"result": f"Mock output for {goal}", "success": success},
            execution_time=0.5,
            thoughts=[],
            observations=[]
        )


class TestAgentCapability(unittest.TestCase):
    def test_capability_creation(self):
        """Test AgentCapability dataclass"""
        cap = AgentCapability(
            capability_id="web_search",
            name="Web Search",
            description="Search the web for information",
            input_schema={"query": "string"},
            output_schema={"results": "list"},
            estimated_duration=10.0,
            success_rate=0.85
        )
        
        self.assertEqual(cap.capability_id, "web_search")
        self.assertEqual(cap.name, "Web Search")
        self.assertEqual(cap.estimated_duration, 10.0)
        
        # Test serialization
        d = cap.to_dict()
        self.assertEqual(d["capability_id"], "web_search")
        self.assertEqual(d["success_rate"], 0.85)


class TestAgentProfile(unittest.TestCase):
    def setUp(self):
        self.capabilities = [
            AgentCapability("web_search", "Web Search", "", {}, {}, 10.0, 0.9),
            AgentCapability("analysis", "Analysis", "", {}, {}, 5.0, 0.8)
        ]
        self.mock_agent = MockAgent("Test Agent")
        self.profile = AgentProfile(
            agent_id="agent_1",
            name="Test Agent",
            role=AgentRole.RESEARCHER,
            capabilities=self.capabilities,
            agent_instance=self.mock_agent
        )
    
    def test_profile_creation(self):
        """Test AgentProfile initialization"""
        self.assertEqual(self.profile.agent_id, "agent_1")
        self.assertEqual(self.profile.role, AgentRole.RESEARCHER)
        self.assertEqual(len(self.profile.capabilities), 2)
    
    def test_can_handle(self):
        """Test capability matching"""
        self.assertTrue(self.profile.can_handle(["web_search"]))
        self.assertTrue(self.profile.can_handle(["web_search", "analysis"]))
        self.assertFalse(self.profile.can_handle(["web_search", "coding"]))
    
    def test_avg_success_rate_no_history(self):
        """Test default success rate with no history"""
        self.assertEqual(self.profile.avg_success_rate, 0.5)
    
    def test_avg_success_rate_with_history(self):
        """Test success rate calculation with history"""
        self.profile.performance_history = [
            {"success": 1, "duration": 5.0},
            {"success": 0, "duration": 10.0},
            {"success": 1, "duration": 5.0}
        ]
        self.assertEqual(self.profile.avg_success_rate, 2/3)
    
    def test_is_available(self):
        """Test availability based on load"""
        self.assertTrue(self.profile.is_available())
        self.profile.current_load = 3
        self.assertFalse(self.profile.is_available())


class TestAgentPool(unittest.TestCase):
    def setUp(self):
        self.pool = AgentPool()
        self.mock_agent = MockAgent("Research Agent")
        self.capabilities = [
            AgentCapability("web_search", "Web Search", "", {}, {}, 10.0, 0.9)
        ]
    
    def test_register_agent(self):
        """Test agent registration"""
        profile = self.pool.register_agent(
            agent_id="researcher_1",
            name="Research Agent",
            role=AgentRole.RESEARCHER,
            capabilities=self.capabilities,
            agent_instance=self.mock_agent
        )
        
        self.assertEqual(profile.agent_id, "researcher_1")
        self.assertIn("researcher_1", self.pool.agents)
        self.assertIn("researcher_1", self.pool.agents_by_role[AgentRole.RESEARCHER])
        self.assertIn("researcher_1", self.pool.agents_by_capability["web_search"])
    
    def test_find_agents_by_role(self):
        """Test finding agents by role"""
        self.pool.register_agent(
            "r1", "Researcher 1", AgentRole.RESEARCHER,
            self.capabilities, self.mock_agent
        )
        self.pool.register_agent(
            "r2", "Researcher 2", AgentRole.RESEARCHER,
            self.capabilities, MockAgent("R2")
        )
        self.pool.register_agent(
            "p1", "Planner 1", AgentRole.PLANNER,
            [AgentCapability("planning", "Planning", "", {}, {}, 5.0)],
            MockAgent("Planner")
        )
        
        researchers = self.pool.find_agents_for_task(role=AgentRole.RESEARCHER)
        self.assertEqual(len(researchers), 2)
        
        planners = self.pool.find_agents_for_task(role=AgentRole.PLANNER)
        self.assertEqual(len(planners), 1)
    
    def test_find_agents_by_capability(self):
        """Test finding agents by required capabilities"""
        self.pool.register_agent(
            "r1", "Researcher 1", AgentRole.RESEARCHER,
            self.capabilities, self.mock_agent
        )
        self.pool.register_agent(
            "c1", "Coder 1", AgentRole.EXECUTOR,
            [AgentCapability("coding", "Coding", "", {}, {}, 15.0)],
            MockAgent("Coder")
        )
        
        capable = self.pool.find_agents_for_task(required_capabilities=["web_search"])
        self.assertEqual(len(capable), 1)
        self.assertEqual(capable[0].agent_id, "r1")
    
    def test_find_agents_by_availability(self):
        """Test filtering by availability"""
        self.pool.register_agent(
            "r1", "Researcher 1", AgentRole.RESEARCHER,
            self.capabilities, self.mock_agent, max_concurrent=1
        )
        
        # Initially available
        available = self.pool.find_agents_for_task(available_only=True)
        self.assertEqual(len(available), 1)
        
        # Make busy
        self.pool.agents["r1"].current_load = 1
        available = self.pool.find_agents_for_task(available_only=True)
        self.assertEqual(len(available), 0)
    
    def test_get_team_for_task(self):
        """Test team assembly"""
        # Register agents for different roles
        for role in [AgentRole.RESEARCHER, AgentRole.PLANNER, AgentRole.EXECUTOR]:
            caps = [AgentCapability(f"{role.value}_cap", "", "", {}, {}, 10.0)]
            self.pool.register_agent(
                f"{role.value}_1", f"{role.value} Agent", role,
                caps, MockAgent(role.value)
            )
        
        team = self.pool.get_team_for_task("Research and build something", team_size=3)
        self.assertGreaterEqual(len(team), 2)  # At least researcher + executor
    
    def test_update_agent_performance(self):
        """Test performance tracking"""
        self.pool.register_agent(
            "r1", "Researcher", AgentRole.RESEARCHER,
            self.capabilities, self.mock_agent
        )
        
        self.pool.update_agent_performance("r1", "task_1", True, 5.0)
        self.pool.update_agent_performance("r1", "task_2", False, 10.0)
        
        profile = self.pool.agents["r1"]
        self.assertEqual(len(profile.performance_history), 2)
        self.assertEqual(profile.avg_success_rate, 0.5)
    
    def test_pool_stats(self):
        """Test pool statistics"""
        stats = self.pool.get_pool_stats()
        self.assertEqual(stats["total_agents"], 0)
        
        self.pool.register_agent(
            "r1", "Researcher", AgentRole.RESEARCHER,
            self.capabilities, self.mock_agent
        )
        
        stats = self.pool.get_pool_stats()
        self.assertEqual(stats["total_agents"], 1)
        self.assertEqual(stats["available_agents"], 1)


class TestTaskRouter(unittest.TestCase):
    def setUp(self):
        self.pool = AgentPool()
        self.router = TaskRouter(self.pool)
        
        # Register test agents
        self.pool.register_agent(
            "r1", "Researcher", AgentRole.RESEARCHER,
            [AgentCapability("web_search", "", "", {}, {}, 10.0)],
            MockAgent("Researcher")
        )
        self.pool.register_agent(
            "p1", "Planner", AgentRole.PLANNER,
            [AgentCapability("planning", "", "", {}, {}, 5.0)],
            MockAgent("Planner")
        )
    
    def test_decompose_task(self):
        """Test task decomposition"""
        subtasks = self.router.decompose_task("Research AGI developments")
        
        self.assertGreaterEqual(len(subtasks), 2)  # At least research + plan
        
        # Check roles are assigned
        roles = [s.role for s in subtasks]
        self.assertIn(AgentRole.RESEARCHER, roles)
        self.assertIn(AgentRole.PLANNER, roles)
    
    def test_assign_task(self):
        """Test task assignment"""
        subtask = SubTask(
            task_id="t1",
            parent_task_id=None,
            description="Test task",
            role=AgentRole.RESEARCHER,
            required_capabilities=["web_search"],
            input_data={}
        )
        
        agent_id = self.router.assign_task(subtask)
        self.assertIsNotNone(agent_id)
        self.assertEqual(subtask.assigned_agent, agent_id)
        self.assertEqual(subtask.status, TaskStatus.ASSIGNED)
    
    def test_assign_task_no_matching_agent(self):
        """Test task assignment when no agent matches"""
        subtask = SubTask(
            task_id="t1",
            parent_task_id=None,
            description="Test task",
            role=AgentRole.CRITIC,  # No critic agent registered
            required_capabilities=["review"],
            input_data={}
        )
        
        agent_id = self.router.assign_task(subtask)
        self.assertIsNone(agent_id)
    
    def test_execute_subtask(self):
        """Test subtask execution"""
        subtask = SubTask(
            task_id="t1",
            parent_task_id=None,
            description="Research AGI",
            role=AgentRole.RESEARCHER,
            required_capabilities=["web_search"],
            input_data={"query": "AGI"},
            assigned_agent="r1"
        )
        
        result = self.router.execute_subtask(subtask)
        
        self.assertIn("output", result)
        self.assertEqual(subtask.status, TaskStatus.COMPLETED)
        self.assertIsNotNone(subtask.completed_at)
        self.assertGreater(subtask.duration, 0)


class TestConsensusBuilder(unittest.TestCase):
    def setUp(self):
        self.builder = ConsensusBuilder(ConsensusStrategy.WEIGHTED_CONFIDENCE)
        
        # Mock agent profiles
        self.agent_profiles = {
            "agent_1": Mock(),
            "agent_2": Mock(),
            "agent_3": Mock()
        }
        self.agent_profiles["agent_1"].avg_success_rate = 0.9
        self.agent_profiles["agent_2"].avg_success_rate = 0.8
        self.agent_profiles["agent_3"].avg_success_rate = 0.7
    
    def test_weighted_consensus(self):
        """Test weighted confidence consensus"""
        results = [
            {"output": "Result A", "confidence": 0.9},
            {"output": "Result A", "confidence": 0.8},
            {"output": "Result B", "confidence": 0.7}
        ]
        
        consensus = self.builder.build_consensus(
            results=results,
            agent_ids=["agent_1", "agent_2", "agent_3"],
            agent_profiles=self.agent_profiles
        )
        
        self.assertIsInstance(consensus, ConsensusResult)
        self.assertEqual(consensus.strategy, ConsensusStrategy.WEIGHTED_CONFIDENCE)
        self.assertEqual(len(consensus.participating_agents), 3)
        self.assertGreater(consensus.confidence, 0)
    
    def test_majority_vote_consensus(self):
        """Test majority vote consensus"""
        builder = ConsensusBuilder(ConsensusStrategy.MAJORITY_VOTE)
        
        results = [
            {"output": "Yes"},
            {"output": "Yes"},
            {"output": "No"}
        ]
        
        consensus = builder.build_consensus(
            results=results,
            agent_ids=["agent_1", "agent_2", "agent_3"],
            agent_profiles=self.agent_profiles
        )
        
        self.assertEqual(consensus.strategy, ConsensusStrategy.MAJORITY_VOTE)
        self.assertEqual(consensus.aggregated_result.get("output"), "Yes")
        self.assertGreaterEqual(consensus.agreement_score, 0.6)
    
    def test_best_of_n_consensus(self):
        """Test best-of-n consensus"""
        builder = ConsensusBuilder(ConsensusStrategy.BEST_OF_N)
        
        results = [
            {"output": "Good", "confidence": 0.9},
            {"output": "Bad", "confidence": 0.5},
            {"output": "OK", "confidence": 0.7}
        ]
        
        consensus = builder.build_consensus(
            results=results,
            agent_ids=["agent_1", "agent_2", "agent_3"],
            agent_profiles=self.agent_profiles
        )
        
        self.assertEqual(consensus.strategy, ConsensusStrategy.BEST_OF_N)
        # Should pick highest confidence result
        self.assertEqual(consensus.aggregated_result.get("output"), "Good")


class TestSharedMemory(unittest.TestCase):
    def setUp(self):
        self.memory = SharedMemory()
    
    def test_post_message(self):
        """Test posting messages"""
        msg_id = self.memory.post_message(
            agent_id="agent_1",
            message_type="result",
            content={"data": "test"},
            target_agents=["agent_2"]
        )
        
        self.assertIsNotNone(msg_id)
        self.assertEqual(len(self.memory.messages), 1)
        self.assertEqual(self.memory.messages[0]["agent_id"], "agent_1")
    
    def test_get_messages(self):
        """Test message retrieval"""
        self.memory.post_message("agent_1", "result", "msg1")
        self.memory.post_message("agent_2", "query", "msg2")
        self.memory.post_message("agent_1", "result", "msg3")
        
        # Get all for agent_2
        messages = self.memory.get_messages(for_agent="agent_2")
        self.assertEqual(len(messages), 1)
        
        # Get by type
        messages = self.memory.get_messages(message_type="result")
        self.assertEqual(len(messages), 2)
    
    def test_store_and_get_result(self):
        """Test result storage"""
        self.memory.store_result("task_1", {"output": "success"})
        
        result = self.memory.get_result("task_1")
        self.assertEqual(result["result"]["output"], "success")
        
        # Non-existent task
        result = self.memory.get_result("task_999")
        self.assertIsNone(result)
    
    def test_context_management(self):
        """Test shared context"""
        self.memory.set_context("key1", "value1")
        self.assertEqual(self.memory.get_context("key1"), "value1")
        
        # Non-existent key
        self.assertIsNone(self.memory.get_context("key2"))


class TestMultiAgentOrchestrator(unittest.TestCase):
    def setUp(self):
        self.orchestrator = MultiAgentOrchestrator()
        
        # Register test agents
        for i, role in enumerate([AgentRole.RESEARCHER, AgentRole.PLANNER, AgentRole.EXECUTOR]):
            caps = [AgentCapability(f"cap_{i}", f"Cap {i}", "", {}, {}, 10.0)]
            self.orchestrator.register_agent(
                agent_id=f"agent_{i}",
                name=f"Agent {i}",
                role=role,
                capabilities=caps,
                agent_instance=MockAgent(f"Agent{i}", success_rate=0.95)
            )
    
    def test_orchestrator_initialization(self):
        """Test orchestrator setup"""
        stats = self.orchestrator.get_stats()
        self.assertEqual(stats["pool_stats"]["total_agents"], 3)
    
    def test_register_agent(self):
        """Test agent registration through orchestrator"""
        profile = self.orchestrator.register_agent(
            agent_id="test_agent",
            name="Test Agent",
            role=AgentRole.CRITIC,
            capabilities=[AgentCapability("review", "Review", "", {}, {}, 5.0)],
            agent_instance=MockAgent("Critic")
        )
        
        self.assertEqual(profile.agent_id, "test_agent")
        self.assertIn("test_agent", self.orchestrator.pool.agents)
    
    def test_execute_simple_task(self):
        """Test end-to-end task execution"""
        result = self.orchestrator.execute(
            task="Research AGI developments",
            team_size=3,
            require_consensus=False
        )
        
        self.assertIn("task", result)
        self.assertIn("subtasks", result)
        self.assertIn("execution_time", result)
        self.assertGreaterEqual(len(result["subtasks"]), 2)
    
    def test_execute_with_consensus(self):
        """Test task execution with consensus building"""
        result = self.orchestrator.execute(
            task="Analyze AGI research findings",
            team_size=3,
            require_consensus=True
        )
        
        self.assertIn("consensus", result)
        # Consensus may be None if not enough subtasks


class TestHelperFunctions(unittest.TestCase):
    def test_create_orchestrator(self):
        """Test orchestrator factory"""
        orch = create_orchestrator()
        self.assertIsInstance(orch, MultiAgentOrchestrator)
    
    def test_quick_collaborate(self):
        """Test quick collaboration helper"""
        agents = [MockAgent(f"Agent{i}") for i in range(2)]
        
        result = quick_collaborate(
            task="Simple research task",
            agents=agents
        )
        
        self.assertIn("task", result)
        self.assertIn("subtasks", result)


class TestIntegration(unittest.TestCase):
    """Integration tests for full workflows"""
    
    def test_research_team_workflow(self):
        """Test a complete research team workflow"""
        orchestrator = create_orchestrator()
        
        # Assemble research team
        roles = [AgentRole.RESEARCHER, AgentRole.PLANNER, AgentRole.EXECUTOR, AgentRole.CRITIC]
        
        for i, role in enumerate(roles):
            caps = [
                AgentCapability(f"{role.value}_skill", f"{role.value.title()} Skill", "", {}, {}, 10.0)
            ]
            orchestrator.register_agent(
                agent_id=f"{role.value}_agent",
                name=f"{role.value.title()} Agent",
                role=role,
                capabilities=caps,
                agent_instance=MockAgent(f"{role.value}Agent", success_rate=0.9)
            )
        
        # Execute complex task
        result = orchestrator.execute(
            task="Research the latest AGI developments and create a summary report",
            team_size=4
        )
        
        # Verify result structure
        self.assertEqual(result["task"], "Research the latest AGI developments and create a summary report")
        self.assertIn("subtasks", result)
        self.assertIn("execution_time", result)
        
        # Check pool stats
        stats = orchestrator.get_stats()
        self.assertEqual(stats["pool_stats"]["total_agents"], 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
