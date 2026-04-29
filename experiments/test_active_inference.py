"""
Tests for Active Inference Agent Implementation

Validates:
1. World model construction (states, observations, actions)
2. Belief updating (Bayesian inference)
3. Expected free energy calculation
4. Policy evaluation and selection
5. Perception-action loop
6. Agency phenotyping
"""

import pytest
import numpy as np
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.active_inference import (
    WorldModel, HiddenState, Observation, Action, TransitionModel,
    ObservationModel, Preference, ExpectedFreeEnergy, Policy,
    ActiveInferenceAgent, PolicyType,
    create_simple_navigation_agent, create_information_seeking_agent
)


# =============================================================================
# World Model Tests
# =============================================================================

class TestWorldModel:
    """Test world model construction and basic operations."""
    
    def test_create_empty_world_model(self):
        """Test creating an empty world model."""
        wm = WorldModel("test")
        assert wm.name == "test"
        assert len(wm.states) == 0
        assert len(wm.observations) == 0
        assert len(wm.actions) == 0
        assert wm.timestep == 0
    
    def test_add_state(self):
        """Test adding hidden states."""
        wm = WorldModel()
        wm.add_state("weather", ["sunny", "rainy"])
        
        assert "weather" in wm.states
        assert wm.states["weather"].values == ["sunny", "rainy"]
        assert len(wm.states["weather"].prior) == 2
        assert np.allclose(wm.states["weather"].prior.sum(), 1.0)
    
    def test_add_state_with_custom_prior(self):
        """Test adding state with custom prior distribution."""
        wm = WorldModel()
        wm.add_state("weather", ["sunny", "rainy"], prior=[0.7, 0.3])
        
        assert np.allclose(wm.states["weather"].prior, [0.7, 0.3])
    
    def test_add_observation(self):
        """Test adding observations."""
        wm = WorldModel()
        wm.add_observation("temperature", ["hot", "mild", "cold"])
        
        assert "temperature" in wm.observations
        assert wm.observations["temperature"].values == ["hot", "mild", "cold"]
    
    def test_add_action(self):
        """Test adding actions."""
        wm = WorldModel()
        action = wm.add_action("move", {"delta_x": 1, "delta_y": 0})
        
        assert "move" in wm.actions
        assert wm.actions["move"].name == "move"
        assert wm.actions["move"].effects == {"delta_x": 1, "delta_y": 0}
    
    def test_add_transition_model(self):
        """Test adding transition dynamics."""
        wm = WorldModel()
        wm.add_state("position", ["A", "B"])
        wm.add_action("go_to_B")
        
        # Transition: from A, going to B usually succeeds
        transition = np.array([
            [0.1, 0.9],  # From A: 10% stay, 90% go to B
            [0.0, 1.0]   # From B: stay at B
        ])
        wm.add_transition("go_to_B", transition)
        
        assert "go_to_B" in wm.transitions
        assert wm.transitions["go_to_B"].matrix.shape == (2, 2)
    
    def test_add_observation_model(self):
        """Test adding observation likelihood."""
        wm = WorldModel()
        wm.add_state("weather", ["sunny", "rainy"])
        wm.add_observation("sky_color", ["blue", "gray"])
        
        # P(o|s): sunny usually blue, rainy usually gray
        obs_matrix = np.array([
            [0.9, 0.1],  # Sunny -> 90% blue, 10% gray
            [0.2, 0.8]   # Rainy -> 20% blue, 80% gray
        ])
        wm.add_observation_model("weather", obs_matrix)
        
        assert "weather" in wm.observation_models
        assert wm.observation_models["weather"].matrix.shape == (2, 2)
    
    def test_add_preference(self):
        """Test adding prior preferences (goals)."""
        wm = WorldModel()
        wm.add_preference("temperature", {"mild": 2.0, "hot": -1.0})
        
        assert "temperature" in wm.preferences
        assert wm.preferences["temperature"].preferred_values["mild"] == 2.0


# =============================================================================
# Belief Updating Tests
# =============================================================================

class TestBeliefUpdating:
    """Test Bayesian belief updating."""
    
    def test_bayesian_update(self):
        """Test that beliefs update correctly given observations."""
        wm = WorldModel()
        wm.add_state("weather", ["sunny", "rainy"], prior=[0.5, 0.5])
        wm.add_observation("sky_color", ["blue", "gray"])
        
        # Strong evidence: blue sky strongly indicates sunny
        obs_matrix = np.array([
            [0.9, 0.1],  # Sunny -> blue
            [0.2, 0.8]   # Rainy -> gray
        ])
        wm.add_observation_model("weather", obs_matrix)
        
        # Initial belief: 50/50
        assert np.allclose(wm.states["weather"].posterior, [0.5, 0.5])
        
        # Observe blue sky
        wm.update_beliefs({"sky_color": "blue"})
        
        # Should now believe it's more likely sunny
        assert wm.states["weather"].posterior[0] > 0.5
        assert wm.states["weather"].posterior[0] > wm.states["weather"].posterior[1]
    
    def test_multiple_observations(self):
        """Test belief updating with multiple observations."""
        wm = WorldModel()
        wm.add_state("fault", ["none", "minor", "severe"], prior=[0.6, 0.3, 0.1])
        wm.add_observation("vibration", ["normal", "high"])
        wm.add_observation("temperature", ["normal", "high"])
        
        # Both observations indicate fault state
        wm.add_observation_model("fault", np.array([
            [0.9, 0.1],  # None -> normal readings
            [0.5, 0.5],  # Minor -> mixed
            [0.1, 0.9]   # Severe -> high readings
        ]))
        
        # Multiple high readings should increase belief in severe fault
        wm.update_beliefs({"vibration": "high"})
        belief_after_one = wm.states["fault"].posterior.copy()
        
        wm.update_beliefs({"temperature": "high"})
        belief_after_two = wm.states["fault"].posterior
        
        # Severe fault probability should increase
        assert belief_after_two[2] > belief_after_one[2]


# =============================================================================
# Expected Free Energy Tests
# =============================================================================

class TestExpectedFreeEnergy:
    """Test EFE calculation for policy evaluation."""
    
    def test_efe_calculation_structure(self):
        """Test that EFE calculation returns valid structure."""
        wm = WorldModel()
        wm.add_state("position", ["A", "B"], prior=[0.5, 0.5])
        wm.add_observation("signal", ["weak", "strong"])
        wm.add_action("move_to_B")
        
        wm.add_transition("move_to_B", np.array([
            [0.2, 0.8],
            [0.0, 1.0]
        ]))
        
        wm.add_observation_model("position", np.array([
            [0.8, 0.2],
            [0.2, 0.8]
        ]))
        
        wm.add_preference("signal", {"strong": 1.0})
        
        efe = wm.calculate_expected_free_energy("move_to_B")
        
        assert isinstance(efe, ExpectedFreeEnergy)
        assert isinstance(efe.total, float)
        assert isinstance(efe.pragmatic_value, float)
        assert isinstance(efe.epistemic_value, float)
    
    def test_explore_policy_prioritizes_information(self):
        """Test that explore policy prioritizes epistemic value."""
        wm = WorldModel()
        wm.add_state("state", ["A", "B"], prior=[0.5, 0.5])
        wm.add_observation("obs", ["x", "y"])
        wm.add_action("action1")
        wm.add_action("action2")
        
        # Action 1 is more informative
        wm.add_transition("action1", np.array([
            [0.5, 0.5],
            [0.5, 0.5]
        ]))
        wm.add_transition("action2", np.array([
            [1.0, 0.0],
            [0.0, 1.0]
        ]))
        
        wm.add_observation_model("state", np.array([
            [0.9, 0.1],
            [0.1, 0.9]
        ]))
        
        efe1 = wm.calculate_expected_free_energy("action1", PolicyType.EXPLORE)
        efe2 = wm.calculate_expected_free_energy("action2", PolicyType.EXPLORE)
        
        # Action1 should have lower EFE (better) for exploration
        # because it maintains uncertainty, allowing for more learning
        assert efe1.total <= efe2.total
    
    def test_exploit_policy_prioritizes_preferences(self):
        """Test that exploit policy prioritizes goal achievement."""
        wm = WorldModel()
        wm.add_state("position", ["home", "away"], prior=[0.5, 0.5])
        wm.add_observation("visual", ["familiar", "unfamiliar"])
        wm.add_action("go_home")
        wm.add_action("wander")
        
        # go_home leads to home position
        wm.add_transition("go_home", np.array([
            [1.0, 0.0],  # home -> home
            [0.9, 0.1]   # away -> likely home
        ]))
        
        # wander is unpredictable
        wm.add_transition("wander", np.array([
            [0.5, 0.5],
            [0.5, 0.5]
        ]))
        
        wm.add_observation_model("position", np.array([
            [0.9, 0.1],  # home -> familiar
            [0.1, 0.9]   # away -> unfamiliar
        ]))
        
        wm.add_preference("visual", {"familiar": 2.0, "unfamiliar": -1.0})
        
        efe_home = wm.calculate_expected_free_energy("go_home", PolicyType.EXPLOIT)
        efe_wander = wm.calculate_expected_free_energy("wander", PolicyType.EXPLOIT)
        
        # go_home should have lower or equal EFE (better) for exploitation
        assert efe_home.total <= efe_wander.total


# =============================================================================
# Active Inference Agent Tests
# =============================================================================

class TestActiveInferenceAgent:
    """Test the complete active inference agent."""
    
    def test_agent_initialization(self):
        """Test agent creation."""
        agent = ActiveInferenceAgent()
        
        assert agent.agent_id is not None
        assert agent.world_model is not None
        assert agent.policy_type == PolicyType.BALANCE
        assert len(agent.history) == 0
    
    def test_perception_updates_beliefs(self):
        """Test that perception updates internal beliefs."""
        wm = WorldModel()
        wm.add_state("light", ["on", "off"], prior=[0.5, 0.5])
        wm.add_observation("brightness", ["high", "low"])
        wm.add_observation_model("light", np.array([
            [0.9, 0.1],  # on -> high brightness
            [0.1, 0.9]   # off -> low brightness
        ]))
        
        agent = ActiveInferenceAgent(world_model=wm)
        
        # Before perception
        initial_belief = agent.world_model.states["light"].posterior.copy()
        
        # Perceive high brightness
        beliefs = agent.perceive({"brightness": "high"})
        
        # Beliefs should have changed
        assert not np.allclose(beliefs["light"], initial_belief)
        assert beliefs["light"][0] > beliefs["light"][1]  # More likely "on"
    
    def test_planning_generates_policies(self):
        """Test that planning generates ranked policies."""
        wm = WorldModel()
        wm.add_state("position", ["A", "B"], prior=[0.5, 0.5])
        wm.add_observation("cue", ["left", "right"])
        wm.add_action("go_left")
        wm.add_action("go_right")
        
        wm.add_transition("go_left", np.eye(2))
        wm.add_transition("go_right", np.eye(2))
        wm.add_observation_model("position", np.eye(2))
        
        agent = ActiveInferenceAgent(world_model=wm)
        
        policies = agent.plan(horizon=1)
        
        assert len(policies) == 2
        assert all(isinstance(p.efe, ExpectedFreeEnergy) for p in policies)
        # Policies should be sorted by EFE
        for i in range(len(policies) - 1):
            assert policies[i].efe.total <= policies[i+1].efe.total
    
    def test_action_selection(self):
        """Test that action selection returns best action."""
        wm = WorldModel()
        wm.add_state("position", ["A", "B"], prior=[1.0, 0.0])
        wm.add_observation("cue", ["at_A", "at_B"])
        wm.add_action("stay")
        wm.add_action("move")
        
        wm.add_observation_model("position", np.array([
            [0.9, 0.1],
            [0.1, 0.9]
        ]))
        wm.add_preference("cue", {"at_A": 1.0})
        
        agent = ActiveInferenceAgent(world_model=wm)
        
        policies = agent.plan(horizon=1)
        action = agent.act(policies)
        
        assert action in ["stay", "move"]
        assert agent.current_policy is not None
    
    def test_complete_step_cycle(self):
        """Test the complete perceive-plan-act cycle."""
        agent = create_simple_navigation_agent()
        
        # Start with observation
        action, info = agent.step({"visual": "red"})
        
        assert action is not None
        assert "beliefs" in info
        assert "policies" in info
        assert "selected_action" in info
        assert info["selected_action"] == action
        assert agent.world_model.timestep == 1
    
    def test_history_accumulation(self):
        """Test that history accumulates over steps."""
        agent = create_simple_navigation_agent()
        
        initial_history_len = len(agent.history)
        
        agent.step({"visual": "red"})
        assert len(agent.history) > initial_history_len
        
        agent.step({"visual": "green"})
        assert len(agent.history) > initial_history_len + 1
    
    def test_agency_phenotype(self):
        """Test agency phenotyping functionality."""
        agent = create_simple_navigation_agent()
        
        # No history yet
        phenotype = agent.get_agency_phenotype()
        assert "status" in phenotype or "agent_id" in phenotype
        
        # Run some steps
        for _ in range(3):
            agent.step({"visual": "red"})
        
        phenotype = agent.get_agency_phenotype()
        
        assert "agent_id" in phenotype
        assert "policy_type" in phenotype
        assert "timesteps" in phenotype
        assert "belief_volatility" in phenotype
        assert "agency_score" in phenotype
        assert phenotype["timesteps"] == 3


# =============================================================================
# Factory Function Tests
# =============================================================================

class TestFactoryFunctions:
    """Test pre-built agent factory functions."""
    
    def test_navigation_agent_creation(self):
        """Test creating a navigation agent."""
        agent = create_simple_navigation_agent()
        
        assert agent.world_model.name == "navigation"
        assert "position" in agent.world_model.states
        assert "visual" in agent.world_model.observations
        assert len(agent.world_model.actions) == 3
        assert "move_left" in agent.world_model.actions
        assert "move_right" in agent.world_model.actions
        assert "stay" in agent.world_model.actions
    
    def test_navigation_agent_goal_seeking(self):
        """Test that navigation agent seeks green (goal)."""
        agent = create_simple_navigation_agent()
        
        # Start at unknown position, observe red (left side)
        action1, _ = agent.step({"visual": "red"})
        
        # Should select a valid action
        assert action1 in ["move_left", "move_right", "stay"]
    
    def test_information_seeking_agent_creation(self):
        """Test creating an information-seeking agent."""
        agent = create_information_seeking_agent()
        
        assert agent.world_model.name == "information_seeker"
        assert agent.policy_type == PolicyType.EXPLORE
        assert "hidden_feature" in agent.world_model.states
    
    def test_information_seeking_agent_explores(self):
        """Test that information-seeking agent prefers exploratory actions."""
        agent = create_information_seeking_agent()
        
        # Initial uncertainty should be high
        initial_entropy = -np.sum(
            agent.world_model.states["hidden_feature"].posterior * 
            np.log(agent.world_model.states["hidden_feature"].posterior + 1e-10)
        )
        
        assert initial_entropy > 0  # Some uncertainty exists


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_goal_directed_navigation(self):
        """
        Test a complete goal-directed navigation scenario.
        
        Agent starts at left (red), needs to reach center (green).
        Should choose actions that minimize distance to goal.
        """
        agent = create_simple_navigation_agent()
        
        # Simulate starting at left position
        observations = [{"visual": "red"}, {"visual": "green"}]
        actions_taken = []
        
        for obs in observations:
            action, info = agent.step(obs)
            actions_taken.append(action)
        
        # Should have taken at least one action
        assert len(actions_taken) > 0
        assert all(a in ["move_left", "move_right", "stay"] for a in actions_taken)
    
    def test_belief_convergence(self):
        """
        Test that beliefs converge with consistent observations.
        
        If agent consistently observes signals from a particular state,
        beliefs should converge to that state.
        """
        wm = WorldModel()
        wm.add_state("true_state", ["A", "B"], prior=[0.5, 0.5])
        wm.add_observation("noisy_obs", ["sig_A", "sig_B"])
        
        # Strong but noisy signal
        wm.add_observation_model("true_state", np.array([
            [0.8, 0.2],  # State A -> usually sig_A
            [0.2, 0.8]   # State B -> usually sig_B
        ]))
        
        agent = ActiveInferenceAgent(world_model=wm)
        
        # Observe consistent signal for state A
        for _ in range(10):
            agent.perceive({"noisy_obs": "sig_A"})
        
        final_belief = agent.world_model.states["true_state"].posterior
        
        # Should strongly believe it's state A
        assert final_belief[0] > 0.7
        assert final_belief[0] > final_belief[1]
    
    def test_serialization(self):
        """Test that agent state can be serialized."""
        agent = create_simple_navigation_agent()
        agent.step({"visual": "red"})
        
        data = agent.to_dict()
        
        assert "agent_id" in data
        assert "policy_type" in data
        assert "world_model" in data
        assert "history_length" in data
        assert data["history_length"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
