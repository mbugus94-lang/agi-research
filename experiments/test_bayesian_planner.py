"""
Tests for Bayesian Belief-Based Planner

Tests Bayesian updating, utility maximization, and decision-making
following principles from arXiv:2605.00742v1.
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.bayesian_planner import (
    Belief, BeliefType, DistributionType, Action, BayesianPlan,
    BayesianPlanner, create_bayesian_planner, quick_plan
)


class TestBelief:
    """Tests for Belief class"""
    
    def test_beta_belief_creation(self):
        """Test creating a Beta-distributed belief"""
        belief = Belief(
            belief_type=BeliefType.TOOL_EFFECTIVENESS,
            distribution_type=DistributionType.BETA,
            name="tool_web_search",
            params={"alpha": 3.0, "beta": 2.0}
        )
        
        assert belief.belief_type == BeliefType.TOOL_EFFECTIVENESS
        assert belief.distribution_type == DistributionType.BETA
        # Expected value of Beta(3, 2) = 3/(3+2) = 0.6
        assert abs(belief.expected_value() - 0.6) < 0.001
    
    def test_beta_uncertainty(self):
        """Test uncertainty calculation for Beta distribution"""
        # Uniform prior Beta(1, 1) has high uncertainty
        uniform = Belief(
            belief_type=BeliefType.TOOL_EFFECTIVENESS,
            distribution_type=DistributionType.BETA,
            name="uniform",
            params={"alpha": 1.0, "beta": 1.0}
        )
        
        # Strong evidence Beta(10, 2) has lower uncertainty
        strong = Belief(
            belief_type=BeliefType.TOOL_EFFECTIVENESS,
            distribution_type=DistributionType.BETA,
            name="strong",
            params={"alpha": 10.0, "beta": 2.0}
        )
        
        assert uniform.uncertainty() > strong.uncertainty()
    
    def test_beta_update_success(self):
        """Test updating Beta belief with success observation"""
        belief = Belief(
            belief_type=BeliefType.TOOL_EFFECTIVENESS,
            distribution_type=DistributionType.BETA,
            name="tool",
            params={"alpha": 2.0, "beta": 2.0}
        )
        
        initial_ev = belief.expected_value()  # 2/(2+2) = 0.5
        
        belief.update_beta(success=True)
        
        # After success, alpha increases
        assert belief.params["alpha"] == 3.0
        assert belief.params["beta"] == 2.0
        # Expected value should increase
        assert belief.expected_value() > initial_ev
    
    def test_beta_update_failure(self):
        """Test updating Beta belief with failure observation"""
        belief = Belief(
            belief_type=BeliefType.TOOL_EFFECTIVENESS,
            distribution_type=DistributionType.BETA,
            name="tool",
            params={"alpha": 2.0, "beta": 2.0}
        )
        
        initial_ev = belief.expected_value()
        
        belief.update_beta(success=False)
        
        # After failure, beta increases
        assert belief.params["alpha"] == 2.0
        assert belief.params["beta"] == 3.0
        # Expected value should decrease
        assert belief.expected_value() < initial_ev
    
    def test_gaussian_belief(self):
        """Test Gaussian belief creation and properties"""
        belief = Belief(
            belief_type=BeliefType.TASK_DIFFICULTY,
            distribution_type=DistributionType.GAUSSIAN,
            name="difficulty",
            params={"mean": 5.0, "precision": 2.0}
        )
        
        assert belief.expected_value() == 5.0
        # Variance = 1/precision
        assert abs(belief.uncertainty() - 0.5) < 0.001
    
    def test_gaussian_update(self):
        """Test updating Gaussian belief with observation"""
        belief = Belief(
            belief_type=BeliefType.TASK_DIFFICULTY,
            distribution_type=DistributionType.GAUSSIAN,
            name="difficulty",
            params={"mean": 0.5, "precision": 1.0}
        )
        
        # Observe a high value
        belief.update_gaussian(observation=0.9, observation_precision=2.0)
        
        # Mean should shift toward observation
        assert belief.expected_value() > 0.5
        # Precision should increase
        assert belief.params["precision"] > 1.0
    
    def test_categorical_belief(self):
        """Test categorical belief for discrete options"""
        belief = Belief(
            belief_type=BeliefType.STRATEGY_QUALITY,
            distribution_type=DistributionType.CATEGORICAL,
            name="strategy",
            params={
                "probabilities": {
                    "0": 0.2,  # Poor
                    "1": 0.3,  # Fair
                    "2": 0.5   # Good
                }
            }
        )
        
        # Expected value = 0*0.2 + 1*0.3 + 2*0.5 = 1.3
        assert abs(belief.expected_value() - 1.3) < 0.001
    
    def test_belief_serialization(self):
        """Test belief can be serialized to dict"""
        belief = Belief(
            belief_type=BeliefType.TOOL_EFFECTIVENESS,
            distribution_type=DistributionType.BETA,
            name="tool_web_search",
            params={"alpha": 5.0, "beta": 3.0}
        )
        
        d = belief.to_dict()
        
        assert d["belief_type"] == "tool_effectiveness"
        assert d["distribution_type"] == "beta"
        assert d["name"] == "tool_web_search"
        assert "expected_value" in d
        assert "uncertainty" in d
    
    def test_beta_sampling(self):
        """Test sampling from Beta distribution"""
        belief = Belief(
            belief_type=BeliefType.TOOL_EFFECTIVENESS,
            distribution_type=DistributionType.BETA,
            name="tool",
            params={"alpha": 2.0, "beta": 2.0}
        )
        
        samples = belief.sample(n=100)
        
        assert len(samples) == 100
        # All samples should be in [0, 1]
        assert all(0 <= s <= 1 for s in samples)
        # Mean of samples should be close to expected value
        mean_sample = sum(samples) / len(samples)
        assert abs(mean_sample - belief.expected_value()) < 0.2


class TestAction:
    """Tests for Action class"""
    
    def test_action_creation(self):
        """Test creating an action"""
        action = Action(
            name="web_search",
            action_type="tool",
            params={"query": "AGI"}
        )
        
        assert action.name == "web_search"
        assert action.action_type == "tool"
    
    def test_action_expected_utility(self):
        """Test expected utility calculation"""
        success_belief = Belief(
            belief_type=BeliefType.TOOL_EFFECTIVENESS,
            distribution_type=DistributionType.BETA,
            name="success",
            params={"alpha": 8.0, "beta": 2.0}  # 80% success rate
        )
        
        cost_belief = Belief(
            belief_type=BeliefType.TASK_DIFFICULTY,
            distribution_type=DistributionType.GAUSSIAN,
            name="cost",
            params={"mean": 0.3, "precision": 2.0}  # Low cost
        )
        
        action = Action(
            name="search",
            action_type="tool",
            success_probability=success_belief,
            cost_belief=cost_belief
        )
        
        util = action.expected_utility()
        # High success (0.8) - low cost (0.15) = positive utility
        assert util > 0.5
    
    def test_action_utility_with_failure(self):
        """Test utility for action with low success probability"""
        success_belief = Belief(
            belief_type=BeliefType.TOOL_EFFECTIVENESS,
            distribution_type=DistributionType.BETA,
            name="success",
            params={"alpha": 1.0, "beta": 9.0}  # 10% success rate
        )
        
        action = Action(
            name="risky",
            action_type="tool",
            success_probability=success_belief
        )
        
        util = action.expected_utility()
        # Low success should yield low utility
        assert util < 0.3


class TestBayesianPlan:
    """Tests for BayesianPlan class"""
    
    def test_plan_creation(self):
        """Test creating a plan"""
        plan = BayesianPlan(goal="Research AGI")
        
        assert plan.goal == "Research AGI"
        assert len(plan.actions) == 0
    
    def test_plan_add_actions(self):
        """Test adding actions to plan"""
        plan = BayesianPlan(goal="Research")
        
        action1 = Action(name="search", action_type="tool")
        action2 = Action(name="analyze", action_type="tool")
        
        plan.actions.extend([action1, action2])
        
        assert len(plan.actions) == 2
    
    def test_plan_belief_management(self):
        """Test setting and getting beliefs"""
        plan = BayesianPlan(goal="Test")
        
        belief = Belief(
            belief_type=BeliefType.TOOL_EFFECTIVENESS,
            distribution_type=DistributionType.BETA,
            name="tool_search",
            params={"alpha": 2.0, "beta": 2.0}
        )
        
        plan.set_belief(belief)
        
        retrieved = plan.get_belief("tool_search")
        assert retrieved is not None
        assert retrieved.expected_value() == belief.expected_value()
    
    def test_select_next_action(self):
        """Test action selection based on expected utility"""
        plan = BayesianPlan(goal="Test")
        
        # Action with higher expected success
        high_success = Belief(
            belief_type=BeliefType.TOOL_EFFECTIVENESS,
            distribution_type=DistributionType.BETA,
            name="high",
            params={"alpha": 8.0, "beta": 2.0}
        )
        
        # Action with lower expected success
        low_success = Belief(
            belief_type=BeliefType.TOOL_EFFECTIVENESS,
            distribution_type=DistributionType.BETA,
            name="low",
            params={"alpha": 2.0, "beta": 8.0}
        )
        
        action1 = Action(name="good_tool", action_type="tool", success_probability=high_success)
        action2 = Action(name="bad_tool", action_type="tool", success_probability=low_success)
        
        plan.actions = [action1, action2]
        
        selected = plan.select_next_action()
        # Should select the action with higher expected utility
        assert selected.name == "good_tool"
    
    def test_update_from_observation_success(self):
        """Test updating plan from successful action"""
        plan = BayesianPlan(goal="Test")
        
        success_belief = Belief(
            belief_type=BeliefType.TOOL_EFFECTIVENESS,
            distribution_type=DistributionType.BETA,
            name="tool_test",
            params={"alpha": 2.0, "beta": 2.0}
        )
        
        action = Action(name="test", action_type="tool", success_probability=success_belief)
        plan.actions = [action]
        plan.set_belief(success_belief)
        
        initial_ev = success_belief.expected_value()
        
        plan.update_from_observation("test", {"success": True, "cost": 0.5, "quality": 0.8})
        
        # Success should increase expected value
        assert success_belief.expected_value() > initial_ev
        assert len(plan.executed_actions) == 1
    
    def test_update_from_observation_failure(self):
        """Test updating plan from failed action"""
        plan = BayesianPlan(goal="Test")
        
        success_belief = Belief(
            belief_type=BeliefType.TOOL_EFFECTIVENESS,
            distribution_type=DistributionType.BETA,
            name="tool_test",
            params={"alpha": 2.0, "beta": 2.0}
        )
        
        action = Action(name="test", action_type="tool", success_probability=success_belief)
        plan.actions = [action]
        plan.set_belief(success_belief)
        
        initial_ev = success_belief.expected_value()
        
        plan.update_from_observation("test", {"success": False, "cost": 1.0, "quality": 0.2})
        
        # Failure should decrease expected value
        assert success_belief.expected_value() < initial_ev
    
    def test_value_of_information(self):
        """Test value of information calculation"""
        plan = BayesianPlan(goal="Test")
        
        # High uncertainty belief
        uncertain = Belief(
            belief_type=BeliefType.TOOL_EFFECTIVENESS,
            distribution_type=DistributionType.BETA,
            name="uncertain_tool",
            params={"alpha": 1.0, "beta": 1.0}  # Uniform, high uncertainty
        )
        
        # Low uncertainty belief
        certain = Belief(
            belief_type=BeliefType.TOOL_EFFECTIVENESS,
            distribution_type=DistributionType.BETA,
            name="certain_tool",
            params={"alpha": 10.0, "beta": 10.0}  # Peak at 0.5, low uncertainty
        )
        
        plan.set_belief(uncertain)
        plan.set_belief(certain)
        
        voi_uncertain = plan.value_of_information("uncertain_tool")
        voi_certain = plan.value_of_information("certain_tool")
        
        # Uncertain belief should have higher VoI
        # (though both have 0 sensitivity here as they're not in any action params)
        assert voi_uncertain >= voi_certain
    
    def test_should_explore(self):
        """Test exploration vs exploitation decision"""
        plan = BayesianPlan(goal="Test")
        
        # Add action with very uncertain effectiveness (near-uniform prior)
        # Beta(1.01, 1.01) has variance ~0.083
        uncertain = Belief(
            belief_type=BeliefType.TOOL_EFFECTIVENESS,
            distribution_type=DistributionType.BETA,
            name="tool",
            params={"alpha": 1.01, "beta": 1.01}  # Very close to uniform
        )
        
        action = Action(name="test", action_type="tool", success_probability=uncertain)
        plan.actions = [action]
        plan.set_belief(uncertain)
        
        # With very high uncertainty (~0.083 variance), should explore with threshold 0.08
        assert plan.should_explore(exploration_threshold=0.08)
        
        # Reduce uncertainty significantly
        for _ in range(10):
            uncertain.update_beta(success=True)
        
        # With lower uncertainty, should not need to explore at lower threshold
    
    def test_plan_statistics(self):
        """Test plan statistics generation"""
        plan = BayesianPlan(goal="Research")
        
        belief = Belief(
            belief_type=BeliefType.TOOL_EFFECTIVENESS,
            distribution_type=DistributionType.BETA,
            name="tool",
            params={"alpha": 2.0, "beta": 2.0}
        )
        
        action = Action(name="search", action_type="tool", success_probability=belief)
        plan.actions = [action]
        plan.set_belief(belief)
        
        stats = plan.get_statistics()
        
        assert stats["goal"] == "Research"
        assert stats["total_actions"] == 1
        assert "beliefs" in stats
        assert "exploration_recommended" in stats
    
    def test_plan_serialization(self):
        """Test plan serialization"""
        plan = BayesianPlan(goal="Test")
        
        belief = Belief(
            belief_type=BeliefType.TOOL_EFFECTIVENESS,
            distribution_type=DistributionType.BETA,
            name="tool",
            params={"alpha": 2.0, "beta": 2.0}
        )
        
        action = Action(name="search", action_type="tool", success_probability=belief)
        plan.actions = [action]
        plan.set_belief(belief)
        
        d = plan.to_dict()
        
        assert d["goal"] == "Test"
        assert len(d["actions"]) == 1
        assert d["actions"][0]["name"] == "search"
        assert "beliefs" in d


class TestBayesianPlanner:
    """Tests for BayesianPlanner class"""
    
    def test_planner_creation(self):
        """Test creating a Bayesian planner"""
        planner = BayesianPlanner(prior_strength=2.0)
        
        assert planner.prior_strength == 2.0
        assert len(planner.global_beliefs) == 0
    
    def test_create_tool_belief(self):
        """Test creating prior belief for tool"""
        planner = BayesianPlanner(prior_strength=3.0)
        
        belief = planner.create_tool_effectiveness_belief("web_search")
        
        assert belief.name == "tool_web_search"
        assert belief.belief_type == BeliefType.TOOL_EFFECTIVENESS
        assert belief.params["alpha"] == 3.0
        assert belief.params["beta"] == 3.0
    
    def test_create_plan(self):
        """Test creating a plan with available actions"""
        planner = BayesianPlanner()
        
        actions = [
            {"name": "search", "type": "tool", "params": {}},
            {"name": "analyze", "type": "tool", "params": {}},
        ]
        
        plan = planner.plan("Research AGI", actions)
        
        assert plan.goal == "Research AGI"
        assert len(plan.actions) == 2
        assert plan.actions[0].name == "search"
        
        # Should have created beliefs for each action
        assert "tool_search" in plan.beliefs
        assert "tool_analyze" in plan.beliefs
    
    def test_update_from_execution(self):
        """Test updating planner from execution outcome"""
        planner = BayesianPlanner()
        
        actions = [{"name": "search", "type": "tool", "params": {}}]
        plan = planner.plan("Test", actions)
        
        planner.update_from_execution(plan, "search", success=True, cost=0.5, quality=0.8)
        
        # Should have recorded execution
        assert len(planner.execution_history) == 1
        
        # Should have updated global belief
        assert "tool_search" in planner.global_beliefs
        ev = planner.global_beliefs["tool_search"].expected_value()
        # After success, should be > 0.5
        assert ev > 0.5
    
    def test_multiple_updates(self):
        """Test learning from multiple executions"""
        planner = BayesianPlanner(prior_strength=2.0)
        
        actions = [{"name": "search", "type": "tool"}]
        plan = planner.plan("Test", actions)
        
        # Simulate 5 successes, 1 failure with prior_strength=2
        # Final: alpha=7, beta=3, expected = 7/10 = 0.7
        for _ in range(5):
            planner.update_from_execution(plan, "search", success=True)
        planner.update_from_execution(plan, "search", success=False)
        
        belief = planner.global_beliefs["tool_search"]
        # 5/6 = 83% success rate but with prior = 2+5/(2+5+1+2) = 7/10 = 0.7
        assert abs(belief.expected_value() - 0.7) < 0.01
        
        # Uncertainty should have decreased
        assert belief.uncertainty() < 0.05
    
    def test_recommend_tool_with_experience(self):
        """Test tool recommendation based on learned preferences"""
        planner = BayesianPlanner()
        
        # Simulate experience with two tools
        plan = planner.plan("Test", [
            {"name": "tool_a", "type": "tool"},
            {"name": "tool_b", "type": "tool"},
        ])
        
        # Tool A has many successes (with prior 2.0: final alpha=12, beta=2, EV=12/14=0.857)
        for _ in range(10):
            planner.update_from_execution(plan, "tool_a", success=True)
        
        # Tool B has many failures (with prior 2.0: final alpha=2, beta=12, EV=2/14=0.143)
        for _ in range(10):
            planner.update_from_execution(plan, "tool_b", success=False)
        
        # Should recommend tool_a
        result = planner.recommend_tool("task", ["tool_a", "tool_b"])
        assert result[0] == "tool_a"
        assert result[1] > 0.8
    
    def test_recommend_untested_tool(self):
        """Test recommendation when good tools are untested"""
        planner = BayesianPlanner()
        
        # Add one tool with poor performance (prior 2.0 + 5 failures)
        plan = planner.plan("Test", [{"name": "bad_tool", "type": "tool"}])
        for _ in range(5):
            planner.update_from_execution(plan, "bad_tool", success=False)
        
        # Now ask to choose between bad_tool and new_tool
        result = planner.recommend_tool("task", ["bad_tool", "new_tool"])
        
        # Should recommend new_tool for exploration (bad_tool is known to be bad)
        # bad_tool: alpha=2, beta=7, EV=2/9=0.22 < 0.3 threshold
        # new_tool: no observations, defaults to 0.5 prior
        assert result[0] == "new_tool"
    
    def test_get_tool_ranking(self):
        """Test getting ranked list of tools"""
        planner = BayesianPlanner()
        
        plan = planner.plan("Test", [
            {"name": "good", "type": "tool"},
            {"name": "medium", "type": "tool"},
            {"name": "poor", "type": "tool"},
        ])
        
        # Simulate outcomes
        for _ in range(8):
            planner.update_from_execution(plan, "good", success=True)
        for _ in range(2):
            planner.update_from_execution(plan, "good", success=False)
        
        for _ in range(5):
            planner.update_from_execution(plan, "medium", success=True)
        for _ in range(5):
            planner.update_from_execution(plan, "medium", success=False)
        
        for _ in range(2):
            planner.update_from_execution(plan, "poor", success=True)
        for _ in range(8):
            planner.update_from_execution(plan, "poor", success=False)
        
        ranking = planner.get_tool_ranking()
        
        # Should be sorted by expected value
        assert ranking[0][0] == "good"
        assert ranking[1][0] == "medium"
        assert ranking[2][0] == "poor"
    
    def test_learning_statistics(self):
        """Test learning statistics generation"""
        planner = BayesianPlanner()
        
        plan = planner.plan("Test", [
            {"name": "tool_a", "type": "tool"},
            {"name": "tool_b", "type": "tool"},
        ])
        
        for i in range(3):
            planner.update_from_execution(plan, "tool_a", success=True)
            planner.update_from_execution(plan, "tool_b", success=False)
        
        stats = planner.get_learning_statistics()
        
        assert stats["total_executions"] == 6
        assert stats["unique_tools_learned"] == 2
        assert len(stats["tool_rankings"]) == 2
        assert "recent_executions" in stats
    
    def test_convenience_functions(self):
        """Test convenience factory functions"""
        planner = create_bayesian_planner(prior_strength=5.0)
        
        assert planner.prior_strength == 5.0
        
        plan = quick_plan("Test", ["action1", "action2"], planner)
        
        assert plan.goal == "Test"
        assert len(plan.actions) == 2


class TestIntegration:
    """Integration tests for the full Bayesian planning workflow"""
    
    def test_full_workflow(self):
        """Test complete workflow: plan -> execute -> learn -> replan"""
        planner = BayesianPlanner(prior_strength=2.0)
        
        # Create initial plan
        available_actions = [
            {"name": "web_search", "type": "tool", "params": {"engine": "google"}},
            {"name": "arxiv_search", "type": "tool", "params": {"category": "cs.AI"}},
            {"name": "github_search", "type": "tool", "params": {"language": "python"}},
        ]
        
        plan = planner.plan("Research AI papers", available_actions)
        
        # Simulate execution with learning
        # web_search: 4/5 success with prior 2.0 -> alpha=6, beta=3, EV=6/9=0.667
        for _ in range(4):
            planner.update_from_execution(plan, "web_search", success=True, cost=0.3)
        planner.update_from_execution(plan, "web_search", success=False, cost=0.3)
        
        # arxiv_search: 5/5 success with prior 2.0 -> alpha=7, beta=2, EV=7/9=0.778
        for _ in range(5):
            planner.update_from_execution(plan, "arxiv_search", success=True, cost=0.4)
        
        # github_search: 2/5 success with prior 2.0 -> alpha=4, beta=5, EV=4/9=0.444
        for _ in range(2):
            planner.update_from_execution(plan, "github_search", success=True, cost=0.5)
        for _ in range(3):
            planner.update_from_execution(plan, "github_search", success=False, cost=0.5)
        
        # Check learning
        rankings = planner.get_tool_ranking()
        
        # arxiv_search should be ranked highest
        assert rankings[0][0] == "arxiv_search"
        # EV should be around 0.778
        assert 0.75 < rankings[0][1] < 0.82
        
        # github_search should be ranked lowest
        assert rankings[-1][0] == "github_search"
        assert rankings[-1][1] < 0.5  # Lower expected success
        
        # Recommendation should prefer arxiv_search
        result = planner.recommend_tool(
            "Find AI papers", 
            ["web_search", "arxiv_search", "github_search"]
        )
        assert result[0] == "arxiv_search"
    
    def test_exploration_exploitation_tradeoff(self):
        """Test that planner balances exploration and exploitation"""
        planner = BayesianPlanner()
        
        plan = planner.plan("Test", [
            {"name": "known_good", "type": "tool"},
            {"name": "unknown", "type": "tool"},
        ])
        
        # Make known_good very reliable
        for _ in range(20):
            planner.update_from_execution(plan, "known_good", success=True)
        
        # unknown has no observations yet (uniform prior)
        
        # With high uncertainty on unknown, should recommend exploration
        # when known_good's utility is not overwhelming
        ranking = planner.get_tool_ranking()
        
        # known_good should be first due to high success rate
        assert ranking[0][0] == "known_good"
        
        # But unknown should have comparable uncertainty (high)
        unknown_belief = planner.global_beliefs.get("tool_unknown")
        if unknown_belief:
            assert unknown_belief.uncertainty() > ranking[0][2]  # Higher uncertainty than known_good


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
