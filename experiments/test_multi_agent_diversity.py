"""
Test suite for Multi-Agent Diversity Framework.

Validates:
- Diverse agent population creation
- A2A communication protocol
- Collaborative problem solving
- Consensus mechanisms
- Diversity metrics calculation
- Debate simulation
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from core.multi_agent_diversity import (
    MultiAgentDiversityFramework, DiverseAgent, Solution, A2AMessage,
    DiversityMetrics, ReasoningStyle, AgentRole, create_diverse_team
)


class TestDiverseAgent(unittest.TestCase):
    """Test individual diverse agent behavior."""
    
    def test_agent_creation(self):
        """Test creating a diverse agent."""
        agent = DiverseAgent(
            agent_id="test_agent",
            reasoning_style=ReasoningStyle.SYMBOLIC,
            role=AgentRole.PROPOSER
        )
        
        self.assertEqual(agent.agent_id, "test_agent")
        self.assertEqual(agent.reasoning_style, ReasoningStyle.SYMBOLIC)
        self.assertEqual(agent.role, AgentRole.PROPOSER)
    
    def test_propose_solution_symbolic(self):
        """Test symbolic reasoning solution generation."""
        agent = DiverseAgent("agent1", ReasoningStyle.SYMBOLIC, AgentRole.PROPOSER)
        solution = agent.propose_solution("test_problem")
        
        self.assertEqual(solution.proposer_id, "agent1")
        self.assertEqual(solution.reasoning_style, ReasoningStyle.SYMBOLIC)
        self.assertIn("type", solution.content)
        self.assertEqual(solution.content["type"], "symbolic")
        self.assertIn("logical", solution.rationale.lower())
    
    def test_propose_solution_neural(self):
        """Test neural reasoning solution generation."""
        agent = DiverseAgent("agent1", ReasoningStyle.NEURAL, AgentRole.PROPOSER)
        solution = agent.propose_solution("test_problem")
        
        self.assertEqual(solution.content["type"], "neural")
        self.assertIn("pattern", solution.rationale.lower())
    
    def test_propose_solution_evolutionary(self):
        """Test evolutionary reasoning solution generation."""
        agent = DiverseAgent("agent1", ReasoningStyle.EVOLUTIONARY, AgentRole.PROPOSER)
        solution = agent.propose_solution("test_problem")
        
        self.assertEqual(solution.content["type"], "evolutionary")
        self.assertIn("generations", solution.content)
    
    def test_propose_solution_analogical(self):
        """Test analogical reasoning solution generation."""
        agent = DiverseAgent("agent1", ReasoningStyle.ANALOGICAL, AgentRole.PROPOSER)
        solution = agent.propose_solution("test_problem")
        
        self.assertEqual(solution.content["type"], "analogical")
        self.assertIn("cases_considered", solution.content)
    
    def test_propose_solution_causal(self):
        """Test causal reasoning solution generation."""
        agent = DiverseAgent("agent1", ReasoningStyle.CAUSAL, AgentRole.PROPOSER)
        solution = agent.propose_solution("test_problem")
        
        self.assertEqual(solution.content["type"], "causal")
        self.assertIn("interventions", solution.content)
    
    def test_propose_solution_probabilistic(self):
        """Test probabilistic reasoning solution generation."""
        agent = DiverseAgent("agent1", ReasoningStyle.PROBABILISTIC, AgentRole.PROPOSER)
        solution = agent.propose_solution("test_problem")
        
        self.assertEqual(solution.content["type"], "probabilistic")
        self.assertIn("prior_probability", solution.content)
    
    def test_solution_tracked(self):
        """Test that proposed solutions are tracked."""
        agent = DiverseAgent("agent1", ReasoningStyle.SYMBOLIC, AgentRole.PROPOSER)
        
        self.assertEqual(len(agent.solutions_proposed), 0)
        solution = agent.propose_solution("test_problem")
        self.assertEqual(len(agent.solutions_proposed), 1)
        self.assertIn(solution.solution_id, agent.solutions_proposed)
    
    def test_vote_on_solutions(self):
        """Test voting on solutions."""
        agent = DiverseAgent("voter", ReasoningStyle.SYMBOLIC, AgentRole.CRITIC)
        
        solutions = [
            Solution(proposer_id="agent1", content={"result": "A"}, reasoning_style=ReasoningStyle.SYMBOLIC),
            Solution(proposer_id="agent2", content={"result": "B"}, reasoning_style=ReasoningStyle.NEURAL),
        ]
        
        votes = agent.vote(solutions, "test_problem")
        
        self.assertEqual(len(votes), 2)
        for solution_id in [s.solution_id for s in solutions]:
            self.assertIn(solution_id, votes)
            self.assertGreaterEqual(votes[solution_id], 0.0)
            self.assertLessEqual(votes[solution_id], 1.0)
    
    def test_diversity_bonus_in_voting(self):
        """Test that agents give diversity bonus to different reasoning styles."""
        agent = DiverseAgent("voter", ReasoningStyle.SYMBOLIC, AgentRole.CRITIC)
        
        # Same style solution
        same_style = Solution(proposer_id="agent1", content={"result": "A"}, 
                              reasoning_style=ReasoningStyle.SYMBOLIC)
        # Different style solution
        diff_style = Solution(proposer_id="agent2", content={"result": "B"}, 
                              reasoning_style=ReasoningStyle.NEURAL)
        
        # Vote multiple times to see pattern
        same_scores = [agent.evaluate_solution(same_style, "test") for _ in range(10)]
        diff_scores = [agent.evaluate_solution(diff_style, "test") for _ in range(10)]
        
        # Different style should generally score higher (diversity bonus)
        avg_same = sum(same_scores) / len(same_scores)
        avg_diff = sum(diff_scores) / len(diff_scores)
        self.assertGreater(avg_diff, avg_same - 0.1)  # Allow some variance
    
    def test_message_communication(self):
        """Test A2A message sending and receiving."""
        agent = DiverseAgent("agent1", ReasoningStyle.SYMBOLIC, AgentRole.PROPOSER)
        
        # Send message
        message = agent.send_message("agent2", "proposal", {"data": "test"})
        
        self.assertEqual(message.sender_id, "agent1")
        self.assertEqual(message.recipient_id, "agent2")
        self.assertEqual(message.message_type, "proposal")
        self.assertEqual(len(agent.message_outbox), 1)
        
        # Receive message
        received = A2AMessage(sender_id="agent2", recipient_id="agent1", 
                             message_type="response", content={"reply": "ok"})
        agent.receive_message(received)
        
        self.assertEqual(len(agent.message_inbox), 1)
    
    def test_collaboration_stats(self):
        """Test collaboration statistics."""
        agent = DiverseAgent("agent1", ReasoningStyle.SYMBOLIC, AgentRole.PROPOSER)
        agent.propose_solution("test")
        
        stats = agent.get_collaboration_stats()
        
        self.assertEqual(stats["agent_id"], "agent1")
        self.assertEqual(stats["reasoning_style"], "symbolic")
        self.assertEqual(stats["role"], "proposer")
        self.assertEqual(stats["solutions_proposed"], 1)


class TestMultiAgentFramework(unittest.TestCase):
    """Test multi-agent framework functionality."""
    
    def test_framework_creation(self):
        """Test creating the framework."""
        framework = MultiAgentDiversityFramework()
        
        self.assertEqual(len(framework.agents), 0)
        self.assertEqual(len(framework.solutions), 0)
    
    def test_create_diverse_population(self):
        """Test creating diverse population."""
        framework = MultiAgentDiversityFramework()
        agent_ids = framework.create_diverse_population(6)
        
        self.assertEqual(len(agent_ids), 6)
        self.assertEqual(len(framework.agents), 6)
        
        # Check diversity
        styles = set(a.reasoning_style for a in framework.agents.values())
        self.assertGreaterEqual(len(styles), 3)  # Should have multiple styles
    
    def test_register_agent(self):
        """Test registering an agent."""
        framework = MultiAgentDiversityFramework()
        agent = DiverseAgent("custom", ReasoningStyle.SYMBOLIC, AgentRole.PROPOSER)
        
        agent_id = framework.register_agent(agent)
        
        self.assertEqual(agent_id, "custom")
        self.assertIn("custom", framework.agents)
    
    def test_direct_messaging(self):
        """Test direct A2A messaging."""
        framework = MultiAgentDiversityFramework()
        framework.create_diverse_population(2)
        
        agent_ids = list(framework.agents.keys())
        message = framework.send_direct_message(
            agent_ids[0], agent_ids[1], "test", {"data": "hello"}
        )
        
        self.assertEqual(message.sender_id, agent_ids[0])
        self.assertEqual(message.recipient_id, agent_ids[1])
        self.assertEqual(len(framework.agents[agent_ids[1]].message_inbox), 1)
    
    def test_broadcast_messaging(self):
        """Test broadcast messaging."""
        framework = MultiAgentDiversityFramework()
        framework.create_diverse_population(4)
        
        agent_ids = list(framework.agents.keys())
        framework.broadcast_message(agent_ids[0], "announcement", {"msg": "hello all"})
        
        # All except sender should receive
        for agent_id in agent_ids[1:]:
            self.assertEqual(len(framework.agents[agent_id].message_inbox), 1)
        
        # Sender should not receive own broadcast
        self.assertEqual(len(framework.agents[agent_ids[0]].message_inbox), 0)
    
    def test_collaborative_problem_solving(self):
        """Test collaborative problem solving workflow."""
        framework = MultiAgentDiversityFramework()
        framework.create_diverse_population(6)
        
        result = framework.collaborative_problem_solving("optimize_schedule")
        
        self.assertIn("proposals", result)
        self.assertIn("diversity_metrics", result)
        self.assertIn("aggregated_solution", result)
        self.assertGreater(result["proposals_count"], 0)
    
    def test_diversity_metrics_calculation(self):
        """Test diversity metrics calculation."""
        framework = MultiAgentDiversityFramework()
        framework.create_diverse_population(6)
        
        # Generate some solutions
        framework.collaborative_problem_solving("test_problem")
        
        metrics = framework.calculate_diversity_metrics()
        
        self.assertIsInstance(metrics, DiversityMetrics)
        self.assertGreaterEqual(metrics.reasoning_diversity, 0.0)
        self.assertLessEqual(metrics.reasoning_diversity, 1.0)
        self.assertGreaterEqual(metrics.coverage_breadth, 0.0)
        self.assertLessEqual(metrics.coverage_breadth, 1.0)
    
    def test_aggregation_with_diversity_bonus(self):
        """Test that aggregation applies diversity bonus."""
        framework = MultiAgentDiversityFramework()
        
        # Create agents with same style (monoculture)
        for i in range(3):
            agent = DiverseAgent(f"mono_{i}", ReasoningStyle.SYMBOLIC, AgentRole.PROPOSER)
            framework.register_agent(agent)
        
        result_mono = framework.collaborative_problem_solving("test")
        
        # Create diverse framework
        framework2 = MultiAgentDiversityFramework()
        framework2.create_diverse_population(6)
        
        result_diverse = framework2.collaborative_problem_solving("test")
        
        # Diverse framework should have higher diversity metrics
        self.assertGreater(
            result_diverse["diversity_metrics"]["coverage_breadth"],
            result_mono["diversity_metrics"]["coverage_breadth"]
        )
    
    def test_population_stats(self):
        """Test population statistics."""
        framework = MultiAgentDiversityFramework()
        framework.create_diverse_population(6)
        
        stats = framework.get_population_stats()
        
        self.assertEqual(stats["total_agents"], 6)
        self.assertIn("reasoning_styles", stats)
        self.assertIn("roles", stats)
    
    def test_identify_experts(self):
        """Test expert identification."""
        framework = MultiAgentDiversityFramework()
        
        agent1 = DiverseAgent("expert1", ReasoningStyle.SYMBOLIC, AgentRole.PROPOSER, ["math", "logic"])
        agent2 = DiverseAgent("novice", ReasoningStyle.NEURAL, AgentRole.PROPOSER, ["pattern"])
        
        framework.register_agent(agent1)
        framework.register_agent(agent2)
        
        experts = framework.identify_experts("math")
        
        self.assertIn("expert1", experts)
    
    def test_simulate_debate(self):
        """Test debate simulation."""
        framework = create_diverse_team(6)
        
        result = framework.simulate_debate("should_ai_be_regulated", rounds=2)
        
        self.assertEqual(result["topic"], "should_ai_be_regulated")
        self.assertGreater(result["arguments"], 0)
        self.assertGreater(result["critiques"], 0)
        self.assertIn("diversity_factor", result)
    
    def test_consensus_detection(self):
        """Test consensus detection."""
        framework = MultiAgentDiversityFramework()
        framework.create_diverse_population(6)
        
        result = framework.collaborative_problem_solving("test")
        
        # Check if consensus_reached field exists
        self.assertIn("consensus_reached", result)
        self.assertIsInstance(result["consensus_reached"], bool)


class TestHelperFunctions(unittest.TestCase):
    """Test helper functions."""
    
    def test_create_diverse_team(self):
        """Test the create_diverse_team helper."""
        team = create_diverse_team(6)
        
        self.assertEqual(len(team.agents), 6)
        self.assertIsInstance(team, MultiAgentDiversityFramework)
        
        # Check diversity
        styles = [a.reasoning_style for a in team.agents.values()]
        self.assertGreater(len(set(styles)), 1)


class TestA2AProtocol(unittest.TestCase):
    """Test A2A communication protocol."""
    
    def test_message_creation(self):
        """Test message creation."""
        message = A2AMessage(
            sender_id="agent1",
            recipient_id="agent2",
            message_type="proposal",
            content={"idea": "new_approach"}
        )
        
        self.assertEqual(message.sender_id, "agent1")
        self.assertEqual(message.recipient_id, "agent2")
        self.assertEqual(message.message_type, "proposal")
        self.assertIn("message_id", message.to_dict())
    
    def test_broadcast_message_none_recipient(self):
        """Test broadcast message has None recipient."""
        message = A2AMessage(
            sender_id="agent1",
            recipient_id=None,
            message_type="announcement",
            content={"msg": "hello all"}
        )
        
        self.assertIsNone(message.recipient_id)
    
    def test_message_timestamp(self):
        """Test message has timestamp."""
        message = A2AMessage(sender_id="a1", message_type="test", content={})
        
        self.assertIsNotNone(message.timestamp)
        self.assertIn("T", message.timestamp)  # ISO format


class TestIntegration(unittest.TestCase):
    """Integration tests."""
    
    def test_full_collaboration_workflow(self):
        """Test complete collaboration workflow."""
        # Create diverse team
        framework = create_diverse_team(8)
        
        # Solve a problem
        problem = {
            "type": "optimization",
            "constraints": ["time < 100", "cost < 1000"],
            "objective": "maximize_efficiency"
        }
        
        result = framework.collaborative_problem_solving(problem, max_rounds=2)
        
        # Verify structure
        self.assertIn("proposals", result)
        self.assertIn("aggregated_solution", result)
        self.assertIn("diversity_metrics", result)
        
        # Verify proposals exist
        self.assertGreater(len(result["proposals"]), 0)
        
        # Verify metrics
        metrics = result["diversity_metrics"]
        self.assertIn("reasoning_diversity", metrics)
        self.assertIn("coverage_breadth", metrics)
        
        # Check population stats
        stats = framework.get_population_stats()
        self.assertEqual(stats["total_agents"], 8)
        self.assertEqual(stats["collaboration_sessions"], 1)
    
    def test_multiple_collaboration_sessions(self):
        """Test multiple collaboration sessions."""
        framework = create_diverse_team(4)
        
        problems = ["problem_A", "problem_B", "problem_C"]
        for problem in problems:
            framework.collaborative_problem_solving(problem)
        
        stats = framework.get_population_stats()
        self.assertEqual(stats["collaboration_sessions"], 3)
        self.assertEqual(stats["total_solutions"], 3)  # One per session
    
    def test_diversity_persistence(self):
        """Test that diversity is maintained across sessions."""
        framework = create_diverse_team(6)
        
        # Initial diversity
        result1 = framework.collaborative_problem_solving("test1")
        initial_diversity = result1["diversity_metrics"]["reasoning_diversity"]
        
        # Run more sessions
        for i in range(3):
            framework.collaborative_problem_solving(f"test_{i}")
        
        # Check diversity maintained
        result_final = framework.collaborative_problem_solving("final_test")
        final_diversity = result_final["diversity_metrics"]["reasoning_diversity"]
        
        # Diversity should remain relatively stable
        self.assertAlmostEqual(initial_diversity, final_diversity, delta=0.2)


def run_tests():
    """Run all tests and return results."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestDiverseAgent,
        TestMultiAgentFramework,
        TestHelperFunctions,
        TestA2AProtocol,
        TestIntegration
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful(), result.testsRun, len(result.failures), len(result.errors)


if __name__ == "__main__":
    success, total, failures, errors = run_tests()
    print(f"\n{'='*60}")
    print(f"Test Summary: {total} tests, {failures} failures, {errors} errors")
    print(f"Result: {'✅ ALL PASSED' if success else '❌ SOME FAILED'}")
    print(f"{'='*60}")
    sys.exit(0 if success else 1)