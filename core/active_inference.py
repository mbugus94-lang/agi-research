"""
Active Inference Agent - Predictive World Modeling

Implementation of active inference from theoretical neurobiology for AI agency.
Based on arXiv:2604.23278 - Active Inference: A Method for Phenotyping Agency in AI Systems

Core Concepts:
- Generative world models with posterior beliefs over hidden states
- Prior preferences over observations (goal-directed behavior)
- Policy selection via expected free energy minimization
- Explainable action selection through belief updating

Key Components:
1. WorldModel: Predictive model of environment dynamics
2. BeliefState: Posterior beliefs over hidden states
3. ExpectedFreeEnergy: Cost function for policy evaluation
4. ActiveInferenceAgent: Agent using active inference for decision-making
"""

from typing import Dict, List, Any, Optional, Callable, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
import numpy as np
import json
import uuid


class PolicyType(Enum):
    """Types of policies for action selection."""
    EXPLORE = auto()      # Reduce uncertainty
    EXPLOIT = auto()      # Maximize expected reward
    BALANCE = auto()      # Balance exploration/exploitation


@dataclass
class HiddenState:
    """A hidden state in the world model."""
    name: str
    values: List[Any]
    prior: np.ndarray  # Prior distribution P(s)
    posterior: Optional[np.ndarray] = None  # Posterior Q(s|o)
    
    def __post_init__(self):
        if self.posterior is None:
            self.posterior = self.prior.copy()
    
    def update_posterior(self, observation_likelihood: np.ndarray, observation_idx: int):
        """Update posterior beliefs given observation (Bayesian update)."""
        # Q(s|o) ∝ P(o|s) * Q(s)
        likelihood = observation_likelihood[:, observation_idx]
        unnormalized = likelihood * self.posterior
        self.posterior = unnormalized / (unnormalized.sum() + 1e-10)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "values": self.values,
            "prior": self.prior.tolist(),
            "posterior": self.posterior.tolist()
        }


@dataclass
class Observation:
    """An observation from the environment."""
    name: str
    values: List[Any]
    current: Optional[Any] = None
    
    def get_index(self, value: Any) -> int:
        """Get index of a value in the observation space."""
        return self.values.index(value) if value in self.values else 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "values": self.values,
            "current": self.current
        }


@dataclass
class Action:
    """An action that can be taken by the agent."""
    name: str
    index: int
    effects: Dict[str, Any] = field(default_factory=dict)  # Expected state changes
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "index": self.index,
            "effects": self.effects
        }


@dataclass
class TransitionModel:
    """P(s'|s,a) - Transition dynamics of the environment."""
    action: Action
    matrix: np.ndarray  # Shape: (num_states, num_next_states)
    
    def get_next_state_dist(self, current_state_idx: int) -> np.ndarray:
        """Get distribution over next states given current state."""
        return self.matrix[current_state_idx, :]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.to_dict(),
            "matrix": self.matrix.tolist()
        }


@dataclass
class ObservationModel:
    """P(o|s) - Observation likelihood given hidden state."""
    matrix: np.ndarray  # Shape: (num_states, num_observations)
    
    def get_observation_likelihood(self, state_idx: int) -> np.ndarray:
        """Get likelihood of observations given state."""
        return self.matrix[state_idx, :]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "matrix": self.matrix.tolist()
        }


@dataclass
class Preference:
    """Prior preferences over observations (goal-directed behavior)."""
    observation_name: str
    preferred_values: Dict[Any, float]  # Value -> Preference strength
    
    def get_preference_vector(self, observation_values: List[Any]) -> np.ndarray:
        """Get preference vector over all observation values."""
        prefs = np.zeros(len(observation_values))
        for value, strength in self.preferred_values.items():
            if value in observation_values:
                prefs[observation_values.index(value)] = strength
        # Normalize to log preferences
        prefs = prefs - prefs.max()  # For numerical stability
        return prefs
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "observation_name": self.observation_name,
            "preferred_values": self.preferred_values
        }


@dataclass
class ExpectedFreeEnergy:
    """
    Expected Free Energy (EFE) for policy evaluation.
    
    G(π) = Expected divergence between predicted and preferred observations
         + Expected uncertainty (information gain)
    
    Lower EFE = better policy
    """
    pragmatic_value: float  # Expected utility/goal achievement
    epistemic_value: float  # Expected information gain
    total: float  # Combined EFE
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pragmatic_value": self.pragmatic_value,
            "epistemic_value": self.epistemic_value,
            "total": self.total
        }


class WorldModel:
    """
    Generative world model for active inference.
    
    Encodes beliefs about:
    - Hidden states of the environment
    - How states generate observations
    - How actions change states
    - Prior preferences (goals)
    """
    
    def __init__(self, name: str = "world_model"):
        self.name = name
        self.states: Dict[str, HiddenState] = {}
        self.observations: Dict[str, Observation] = {}
        self.actions: Dict[str, Action] = {}
        self.transitions: Dict[str, TransitionModel] = {}
        self.observation_models: Dict[str, ObservationModel] = {}
        self.preferences: Dict[str, Preference] = {}
        self.timestep: int = 0
    
    def add_state(self, name: str, values: List[Any], prior: Optional[np.ndarray] = None):
        """Add a hidden state variable."""
        if prior is None:
            prior = np.ones(len(values)) / len(values)
        else:
            prior = np.array(prior)
            prior = prior / prior.sum()  # Normalize
        
        self.states[name] = HiddenState(name, values, prior)
        return self
    
    def add_observation(self, name: str, values: List[Any]):
        """Add an observation variable."""
        self.observations[name] = Observation(name, values)
        return self
    
    def add_action(self, name: str, effects: Optional[Dict[str, Any]] = None) -> Action:
        """Add an available action."""
        action = Action(name, len(self.actions), effects or {})
        self.actions[name] = action
        return action
    
    def add_transition(self, action_name: str, matrix: np.ndarray):
        """Add transition model P(s'|s,a) for an action."""
        if action_name in self.actions:
            self.transitions[action_name] = TransitionModel(
                self.actions[action_name], np.array(matrix)
            )
        return self
    
    def add_observation_model(self, state_name: str, matrix: np.ndarray):
        """Add observation likelihood P(o|s)."""
        self.observation_models[state_name] = ObservationModel(np.array(matrix))
        return self
    
    def add_preference(self, observation_name: str, preferred_values: Dict[Any, float]):
        """Add prior preferences over observations (goals)."""
        self.preferences[observation_name] = Preference(observation_name, preferred_values)
        return self
    
    def update_beliefs(self, observations: Dict[str, Any]):
        """
        Update posterior beliefs given observations.
        
        Performs approximate Bayesian inference:
        Q(s) ∝ P(o|s) * Q(s) for each observation
        """
        for obs_name, obs_value in observations.items():
            if obs_name in self.observations:
                self.observations[obs_name].current = obs_value
                obs_idx = self.observations[obs_name].get_index(obs_value)
                
                # Update beliefs for connected states
                for state_name, obs_model in self.observation_models.items():
                    if state_name in self.states:
                        self.states[state_name].update_posterior(
                            obs_model.matrix, obs_idx
                        )
        self.timestep += 1
    
    def calculate_expected_free_energy(
        self, 
        action_name: str, 
        policy_type: PolicyType = PolicyType.BALANCE
    ) -> ExpectedFreeEnergy:
        """
        Calculate Expected Free Energy for a policy (sequence of actions).
        
        For a single action, this evaluates:
        - Pragmatic value: How well does it achieve goals?
        - Epistemic value: How much does it reduce uncertainty?
        """
        if action_name not in self.transitions:
            return ExpectedFreeEnergy(0.0, 0.0, float('inf'))
        
        transition = self.transitions[action_name]
        
        pragmatic_value = 0.0
        epistemic_value = 0.0
        
        # For each state, calculate expected outcomes
        for state_name, state in self.states.items():
            if state_name not in self.observation_models:
                continue
            
            obs_model = self.observation_models[state_name]
            
            # Expected next state distribution
            expected_next_state = np.zeros(len(state.values))
            for i, prob in enumerate(state.posterior):
                expected_next_state += prob * transition.get_next_state_dist(i)
            
            # Expected observations
            expected_obs = np.zeros(obs_model.matrix.shape[1])
            for i, prob in enumerate(expected_next_state):
                expected_obs += prob * obs_model.get_observation_likelihood(i)
            
            # Pragmatic value: alignment with preferences
            if state_name in self.preferences:
                pref = self.preferences[state_name]
                if state_name in self.observations:
                    obs_values = self.observations[state_name].values
                    pref_vector = pref.get_preference_vector(obs_values)
                    # Higher preference match = lower EFE
                    pragmatic_value -= np.dot(expected_obs, np.exp(pref_vector))
            
            # Epistemic value: expected information gain
            # (reduction in uncertainty about states)
            uncertainty_before = -np.sum(state.posterior * np.log(state.posterior + 1e-10))
            uncertainty_after = -np.sum(expected_next_state * np.log(expected_next_state + 1e-10))
            epistemic_value -= max(0, uncertainty_after - uncertainty_before)
        
        # Combine based on policy type
        if policy_type == PolicyType.EXPLORE:
            total = -epistemic_value  # Maximize information gain
        elif policy_type == PolicyType.EXPLOIT:
            total = pragmatic_value  # Minimize goal divergence
        else:  # BALANCE
            total = pragmatic_value - 0.5 * epistemic_value
        
        return ExpectedFreeEnergy(
            pragmatic_value=pragmatic_value,
            epistemic_value=epistemic_value,
            total=total
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "timestep": self.timestep,
            "states": {k: v.to_dict() for k, v in self.states.items()},
            "observations": {k: v.to_dict() for k, v in self.observations.items()},
            "actions": {k: v.to_dict() for k, v in self.actions.items()},
            "transitions": {k: v.to_dict() for k, v in self.transitions.items()},
            "preferences": {k: v.to_dict() for k, v in self.preferences.items()}
        }


@dataclass
class Policy:
    """A policy (sequence of actions) for evaluation."""
    actions: List[str]
    efe: Optional[ExpectedFreeEnergy] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "actions": self.actions,
            "efe": self.efe.to_dict() if self.efe else None
        }


class ActiveInferenceAgent:
    """
    Agent that uses active inference for perception, planning, and action.
    
    Implements the perception-action loop:
    1. Observe environment
    2. Update beliefs (perception)
    3. Evaluate policies (planning)
    4. Select action minimizing expected free energy
    5. Execute action
    6. Repeat
    """
    
    def __init__(
        self,
        agent_id: Optional[str] = None,
        world_model: Optional[WorldModel] = None,
        policy_type: PolicyType = PolicyType.BALANCE
    ):
        self.agent_id = agent_id or str(uuid.uuid4())
        self.world_model = world_model or WorldModel()
        self.policy_type = policy_type
        
        self.history: List[Dict[str, Any]] = []
        self.current_policy: Optional[Policy] = None
        self.created_at = datetime.now()
    
    def perceive(self, observations: Dict[str, Any]) -> Dict[str, np.ndarray]:
        """
        Perception: Update beliefs given observations.
        
        Returns updated belief states.
        """
        self.world_model.update_beliefs(observations)
        
        beliefs = {
            name: state.posterior 
            for name, state in self.world_model.states.items()
        }
        
        self.history.append({
            "type": "perception",
            "timestep": self.world_model.timestep,
            "observations": observations,
            "beliefs": {k: v.tolist() for k, v in beliefs.items()}
        })
        
        return beliefs
    
    def plan(self, horizon: int = 1) -> List[Policy]:
        """
        Planning: Evaluate all possible policies and rank by EFE.
        
        For horizon=1, evaluates individual actions.
        For horizon>1, evaluates action sequences (computationally expensive).
        """
        policies = []
        
        # Generate candidate policies
        if horizon == 1:
            for action_name in self.world_model.actions:
                efe = self.world_model.calculate_expected_free_energy(
                    action_name, self.policy_type
                )
                policies.append(Policy([action_name], efe))
        else:
            # Multi-step policy evaluation (simplified)
            # In practice, use sophisticated search algorithms
            pass
        
        # Sort by EFE (lower is better)
        policies.sort(key=lambda p: p.efe.total if p.efe else float('inf'))
        
        self.history.append({
            "type": "planning",
            "timestep": self.world_model.timestep,
            "policies_evaluated": len(policies),
            "best_policy": policies[0].to_dict() if policies else None
        })
        
        return policies
    
    def act(self, policies: Optional[List[Policy]] = None) -> Optional[str]:
        """
        Action: Select and return the best action.
        
        Returns the action name with minimum expected free energy.
        """
        if policies is None:
            policies = self.plan(horizon=1)
        
        if not policies:
            return None
        
        best_policy = policies[0]
        self.current_policy = best_policy
        
        action = best_policy.actions[0] if best_policy.actions else None
        
        self.history.append({
            "type": "action",
            "timestep": self.world_model.timestep,
            "selected_action": action,
            "efe": best_policy.efe.to_dict() if best_policy.efe else None
        })
        
        return action
    
    def step(self, observations: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        Complete perception-action loop step.
        
        Returns: (selected_action, info_dict)
        """
        # Perceive
        beliefs = self.perceive(observations)
        
        # Plan
        policies = self.plan(horizon=1)
        
        # Act
        action = self.act(policies)
        
        info = {
            "beliefs": beliefs,
            "policies": policies,
            "selected_action": action,
            "timestep": self.world_model.timestep
        }
        
        return action, info
    
    def get_agency_phenotype(self) -> Dict[str, Any]:
        """
        Get computational phenotype of agency.
        
        Characterizes the agent's decision-making style through:
        - Belief updating patterns
        - Policy selection tendencies
        - Exploration vs exploitation balance
        """
        if not self.history:
            return {"status": "no_history"}
        
        perception_events = [h for h in self.history if h["type"] == "perception"]
        action_events = [h for h in self.history if h["type"] == "action"]
        
        # Calculate belief change patterns
        belief_changes = []
        for i in range(1, len(perception_events)):
            prev_beliefs = perception_events[i-1].get("beliefs", {})
            curr_beliefs = perception_events[i].get("beliefs", {})
            
            for state_name in prev_beliefs:
                if state_name in curr_beliefs:
                    prev = np.array(prev_beliefs[state_name])
                    curr = np.array(curr_beliefs[state_name])
                    change = np.abs(curr - prev).sum()
                    belief_changes.append(change)
        
        # Calculate EFE patterns
        efe_values = []
        for event in action_events:
            if event.get("efe"):
                efe_values.append(event["efe"]["total"])
        
        return {
            "agent_id": self.agent_id,
            "policy_type": self.policy_type.name,
            "timesteps": self.world_model.timestep,
            "belief_volatility": np.mean(belief_changes) if belief_changes else 0.0,
            "average_efe": np.mean(efe_values) if efe_values else 0.0,
            "exploration_tendency": 1.0 if self.policy_type == PolicyType.EXPLORE else 
                                   0.0 if self.policy_type == PolicyType.EXPLOIT else 0.5,
            "agency_score": len(action_events) / max(1, self.world_model.timestep)
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "policy_type": self.policy_type.name,
            "world_model": self.world_model.to_dict(),
            "history_length": len(self.history),
            "created_at": self.created_at.isoformat()
        }


def create_simple_navigation_agent() -> ActiveInferenceAgent:
    """
    Create a simple navigation agent example.
    
    Agent navigates in a 1D environment with:
    - States: position (left, center, right)
    - Observations: visual cues (red, green, blue)
    - Actions: move_left, move_right, stay
    - Goal: reach center (green observation)
    """
    wm = WorldModel("navigation")
    
    # Hidden states: agent position
    wm.add_state("position", ["left", "center", "right"], prior=[0.3, 0.4, 0.3])
    
    # Observations: visual cues at each position
    wm.add_observation("visual", ["red", "green", "blue"])
    
    # Actions
    wm.add_action("move_left")
    wm.add_action("move_right")
    wm.add_action("stay")
    
    # Transition model: how actions change position
    # P(s'|s, move_left)
    wm.add_transition("move_left", np.array([
        [1.0, 0.0, 0.0],  # From left -> stay left
        [0.8, 0.2, 0.0],  # From center -> likely left
        [0.0, 0.8, 0.2]   # From right -> likely center
    ]))
    
    # P(s'|s, move_right)
    wm.add_transition("move_right", np.array([
        [0.2, 0.8, 0.0],  # From left -> likely center
        [0.0, 0.2, 0.8],  # From center -> likely right
        [0.0, 0.0, 1.0]   # From right -> stay right
    ]))
    
    # P(s'|s, stay)
    wm.add_transition("stay", np.array([
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0]
    ]))
    
    # Observation model: P(o|s)
    # Position -> Visual cue mapping
    wm.add_observation_model("position", np.array([
        [0.8, 0.1, 0.1],  # left -> mostly red
        [0.1, 0.8, 0.1],  # center -> mostly green (goal!)
        [0.1, 0.1, 0.8]   # right -> mostly blue
    ]))
    
    # Preferences: prefer green observation (center position)
    wm.add_preference("visual", {"green": 2.0, "red": -1.0, "blue": -1.0})
    
    return ActiveInferenceAgent(world_model=wm, policy_type=PolicyType.BALANCE)


def create_information_seeking_agent() -> ActiveInferenceAgent:
    """
    Create an agent that seeks information (epistemic drive).
    
    Agent prefers actions that reduce uncertainty about hidden states.
    """
    wm = WorldModel("information_seeker")
    
    # Uncertain initial state
    wm.add_state("hidden_feature", ["A", "B", "C"], prior=[0.33, 0.33, 0.34])
    
    # Observations provide information about hidden feature
    wm.add_observation("signal", ["weak", "medium", "strong"])
    
    # Actions that change how much information is revealed
    wm.add_action("passive_observation")
    wm.add_action("active_probe")
    wm.add_action("experiment")
    
    # Observation model: different actions reveal different amounts of info
    # (Simplified - in reality would depend on action)
    wm.add_observation_model("hidden_feature", np.array([
        [0.5, 0.3, 0.2],   # State A -> noisy signal
        [0.3, 0.4, 0.3],   # State B -> noisy signal
        [0.2, 0.3, 0.5]    # State C -> noisy signal
    ]))
    
    return ActiveInferenceAgent(world_model=wm, policy_type=PolicyType.EXPLORE)
