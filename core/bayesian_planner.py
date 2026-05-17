"""
Bayesian Belief-Based Planner

Implements Bayesian decision theory for agentic orchestration per
arXiv:2605.00742v1 "Position: Agentic AI Orchestration Should Be Bayes-Consistent"

Key principles:
- Maintain beliefs about task-relevant latent quantities
- Update beliefs from interactions (Bayesian updating)
- Choose actions in utility-aware, principled way
- Use approximations where full Bayesian updating is infeasible

References:
- Bayesian decision theory for agentic control layers
- Value of information for tool selection
- Belief-based resource allocation
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable, Tuple
from enum import Enum
import json
import math
from datetime import datetime


class BeliefType(Enum):
    """Types of beliefs the planner can maintain"""
    TASK_DIFFICULTY = "task_difficulty"      # How hard is this task?
    TOOL_EFFECTIVENESS = "tool_effectiveness"  # How well does a tool work?
    STRATEGY_QUALITY = "strategy_quality"      # Is this strategy working?
    ENVIRONMENT_STATE = "environment_state"  # Current world state
    USER_PREFERENCE = "user_preference"        # What does the user want?


class DistributionType(Enum):
    """Supported probability distributions for beliefs"""
    BETA = "beta"          # Binary outcomes (success/failure)
    GAUSSIAN = "gaussian"  # Continuous values
    CATEGORICAL = "categorical"  # Discrete options


@dataclass
class Belief:
    """
    A probabilistic belief about some latent quantity.
    
    Uses conjugate priors for efficient Bayesian updating:
    - Beta for binary outcomes (success/failure)
    - Gaussian with known variance for continuous
    - Categorical with Dirichlet prior for discrete
    """
    belief_type: BeliefType
    distribution_type: DistributionType
    name: str
    
    # Distribution parameters
    # Beta: alpha, beta (pseudo-counts of success/failure)
    # Gaussian: mean, precision (inverse variance)
    # Categorical: probability vector
    params: Dict[str, Any] = field(default_factory=dict)
    
    # Observation history
    observations: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    last_updated: float = field(default_factory=lambda: datetime.now().timestamp())
    
    def expected_value(self) -> float:
        """Get expected value of the belief"""
        if self.distribution_type == DistributionType.BETA:
            alpha = self.params.get("alpha", 1.0)
            beta = self.params.get("beta", 1.0)
            return alpha / (alpha + beta)
        elif self.distribution_type == DistributionType.GAUSSIAN:
            return self.params.get("mean", 0.0)
        elif self.distribution_type == DistributionType.CATEGORICAL:
            probs = self.params.get("probabilities", {})
            if not probs:
                return 0.0
            # Expected value = sum(value * probability)
            return sum(float(k) * v for k, v in probs.items())
        return 0.0
    
    def uncertainty(self) -> float:
        """Get uncertainty (variance/entropy) of the belief"""
        if self.distribution_type == DistributionType.BETA:
            alpha = self.params.get("alpha", 1.0)
            beta = self.params.get("beta", 1.0)
            # Variance of Beta distribution
            return (alpha * beta) / ((alpha + beta)**2 * (alpha + beta + 1))
        elif self.distribution_type == DistributionType.GAUSSIAN:
            precision = self.params.get("precision", 1.0)
            return 1.0 / precision if precision > 0 else float('inf')
        elif self.distribution_type == DistributionType.CATEGORICAL:
            probs = self.params.get("probabilities", {})
            # Entropy
            return -sum(p * math.log(p) for p in probs.values() if p > 0)
        return 1.0
    
    def update_beta(self, success: bool, weight: float = 1.0):
        """Update Beta distribution with new observation"""
        if self.distribution_type != DistributionType.BETA:
            raise ValueError("Belief is not Beta distributed")
        
        if success:
            self.params["alpha"] = self.params.get("alpha", 1.0) + weight
        else:
            self.params["beta"] = self.params.get("beta", 1.0) + weight
        
        self.observations.append({
            "timestamp": datetime.now().timestamp(),
            "success": success,
            "weight": weight
        })
        self.last_updated = datetime.now().timestamp()
    
    def update_gaussian(self, observation: float, observation_precision: float):
        """
        Update Gaussian belief with new observation.
        Uses precision-weighted combination for conjugate update.
        """
        if self.distribution_type != DistributionType.GAUSSIAN:
            raise ValueError("Belief is not Gaussian distributed")
        
        prior_mean = self.params.get("mean", 0.0)
        prior_precision = self.params.get("precision", 1.0)
        
        # Bayesian update for Gaussian with known variance
        posterior_precision = prior_precision + observation_precision
        posterior_mean = (prior_precision * prior_mean + 
                         observation_precision * observation) / posterior_precision
        
        self.params["mean"] = posterior_mean
        self.params["precision"] = posterior_precision
        
        self.observations.append({
            "timestamp": datetime.now().timestamp(),
            "value": observation,
            "precision": observation_precision
        })
        self.last_updated = datetime.now().timestamp()
    
    def sample(self, n: int = 1) -> List[float]:
        """Sample from the belief distribution"""
        import random
        
        samples = []
        for _ in range(n):
            if self.distribution_type == DistributionType.BETA:
                # Use expected value as approximation
                alpha = self.params.get("alpha", 1.0)
                beta = self.params.get("beta", 1.0)
                # Simple rejection sampling approximation
                samples.append(random.betavariate(alpha, beta))
            elif self.distribution_type == DistributionType.GAUSSIAN:
                mean = self.params.get("mean", 0.0)
                precision = self.params.get("precision", 1.0)
                # Box-Muller transform
                u1, u2 = random.random(), random.random()
                std = 1.0 / math.sqrt(precision)
                z = math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)
                samples.append(mean + z * std)
            elif self.distribution_type == DistributionType.CATEGORICAL:
                probs = self.params.get("probabilities", {})
                if probs:
                    values = list(probs.keys())
                    weights = list(probs.values())
                    samples.append(random.choices(values, weights=weights)[0])
        
        return samples
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "belief_type": self.belief_type.value,
            "distribution_type": self.distribution_type.value,
            "name": self.name,
            "params": self.params,
            "expected_value": self.expected_value(),
            "uncertainty": self.uncertainty(),
            "observation_count": len(self.observations),
            "created_at": self.created_at,
            "last_updated": self.last_updated
        }


@dataclass
class Action:
    """A possible action with expected utility"""
    name: str
    action_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    
    # Beliefs about this action
    success_probability: Optional[Belief] = None
    cost_belief: Optional[Belief] = None
    quality_belief: Optional[Belief] = None
    
    def expected_utility(self, utility_fn: Optional[Callable] = None) -> float:
        """
        Calculate expected utility of taking this action.
        Default: maximize success probability, minimize cost.
        """
        if utility_fn:
            return utility_fn(self)
        
        # Default utility = success_prob - normalized_cost
        util = 0.0
        if self.success_probability:
            util += self.success_probability.expected_value()
        if self.cost_belief:
            # Assume cost is normalized 0-1, subtract
            util -= self.cost_belief.expected_value() * 0.5
        return util


@dataclass
class BayesianPlan:
    """
    A plan that maintains beliefs about task execution.
    
    Unlike classical plans, Bayesian plans continuously update beliefs
    based on observations and can revise decisions when beliefs change.
    """
    goal: str
    actions: List[Action] = field(default_factory=list)
    beliefs: Dict[str, Belief] = field(default_factory=dict)
    
    # Execution state
    executed_actions: List[Tuple[Action, Dict[str, Any]]] = field(default_factory=list)
    current_action_index: int = 0
    
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    
    def get_belief(self, name: str) -> Optional[Belief]:
        """Get a belief by name"""
        return self.beliefs.get(name)
    
    def set_belief(self, belief: Belief):
        """Set or update a belief"""
        self.beliefs[belief.name] = belief
    
    def update_from_observation(self, action_name: str, outcome: Dict[str, Any]):
        """Update beliefs based on action outcome"""
        # Find the action
        action = next((a for a in self.actions if a.name == action_name), None)
        if not action:
            return
        
        # Update success probability belief
        if action.success_probability and "success" in outcome:
            action.success_probability.update_beta(outcome["success"])
        
        # Update cost belief
        if action.cost_belief and "cost" in outcome:
            # Normalize cost to 0-1 range (assumes cost <= 100)
            normalized_cost = min(outcome["cost"], 100) / 100
            action.cost_belief.update_gaussian(normalized_cost, 1.0)
        
        # Update quality belief
        if action.quality_belief and "quality" in outcome:
            action.quality_belief.update_gaussian(outcome["quality"], 1.0)
        
        # Record execution
        self.executed_actions.append((action, outcome))
    
    def select_next_action(self) -> Optional[Action]:
        """
        Select next action based on expected utility.
        This is the core Bayesian decision-making step.
        """
        remaining = self.actions[self.current_action_index:]
        if not remaining:
            return None
        
        # Select action with highest expected utility
        best_action = max(remaining, key=lambda a: a.expected_utility())
        return best_action
    
    def value_of_information(self, belief_name: str) -> float:
        """
        Calculate value of information for a belief.
        High VoI means reducing uncertainty would significantly improve decisions.
        """
        belief = self.beliefs.get(belief_name)
        if not belief:
            return 0.0
        
        uncertainty = belief.uncertainty()
        
        # Simple VoI: uncertainty * sensitivity of decisions to this belief
        # High uncertainty in a belief that strongly affects action selection
        # has high VoI
        
        sensitivity = 0.0
        for action in self.actions:
            # Check if action utilities would change significantly with belief update
            if belief_name in str(action.params):
                sensitivity += 1.0
        
        return uncertainty * sensitivity
    
    def should_explore(self, exploration_threshold: float = 0.3) -> bool:
        """
        Decide if we should explore (try uncertain actions) or exploit (use best known).
        Based on uncertainty in action effectiveness beliefs.
        """
        total_uncertainty = sum(
            a.success_probability.uncertainty() if a.success_probability else 0
            for a in self.actions
        )
        avg_uncertainty = total_uncertainty / len(self.actions) if self.actions else 0
        return avg_uncertainty > exploration_threshold
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get plan statistics for debugging/observability"""
        return {
            "goal": self.goal,
            "total_actions": len(self.actions),
            "executed_actions": len(self.executed_actions),
            "remaining_actions": len(self.actions) - self.current_action_index,
            "beliefs": {name: b.to_dict() for name, b in self.beliefs.items()},
            "exploration_recommended": self.should_explore(),
            "highest_voi_belief": max(
                ((n, self.value_of_information(n)) for n in self.beliefs.keys()),
                key=lambda x: x[1]
            ) if self.beliefs else None
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "actions": [
                {
                    "name": a.name,
                    "type": a.action_type,
                    "expected_utility": a.expected_utility()
                }
                for a in self.actions
            ],
            "beliefs": {name: b.to_dict() for name, b in self.beliefs.items()},
            "statistics": self.get_statistics()
        }


class BayesianPlanner:
    """
    A planner that uses Bayesian decision theory for action selection.
    
    Maintains beliefs about:
    - Which strategies work for which tasks
    - Tool effectiveness
    - Task difficulty
    
    Updates beliefs from execution outcomes.
    Selects actions to maximize expected utility.
    """
    
    def __init__(self, prior_strength: float = 2.0):
        self.prior_strength = prior_strength  # Pseudo-observations for priors
        self.global_beliefs: Dict[str, Belief] = {}
        self.execution_history: List[Dict[str, Any]] = []
    
    def create_tool_effectiveness_belief(self, tool_name: str) -> Belief:
        """Create prior belief about a tool's effectiveness"""
        return Belief(
            belief_type=BeliefType.TOOL_EFFECTIVENESS,
            distribution_type=DistributionType.BETA,
            name=f"tool_{tool_name}",
            params={"alpha": self.prior_strength, "beta": self.prior_strength}
        )
    
    def create_strategy_quality_belief(self, strategy_name: str) -> Belief:
        """Create prior belief about a strategy's quality"""
        return Belief(
            belief_type=BeliefType.STRATEGY_QUALITY,
            distribution_type=DistributionType.BETA,
            name=f"strategy_{strategy_name}",
            params={"alpha": self.prior_strength, "beta": self.prior_strength}
        )
    
    def plan(self, goal: str, available_actions: List[Dict[str, Any]]) -> BayesianPlan:
        """
        Create a Bayesian plan for achieving a goal.
        
        Args:
            goal: The goal to achieve
            available_actions: List of possible actions with their types and params
        
        Returns:
            BayesianPlan with beliefs initialized
        """
        plan = BayesianPlan(goal=goal)
        
        for action_spec in available_actions:
            action_name = action_spec["name"]
            action_type = action_spec.get("type", "unknown")
            params = action_spec.get("params", {})
            
            # Create beliefs for this action
            success_belief = self.create_tool_effectiveness_belief(action_name)
            cost_belief = Belief(
                belief_type=BeliefType.TASK_DIFFICULTY,
                distribution_type=DistributionType.GAUSSIAN,
                name=f"cost_{action_name}",
                params={"mean": 0.5, "precision": 1.0}
            )
            quality_belief = Belief(
                belief_type=BeliefType.STRATEGY_QUALITY,
                distribution_type=DistributionType.GAUSSIAN,
                name=f"quality_{action_name}",
                params={"mean": 0.5, "precision": 1.0}
            )
            
            action = Action(
                name=action_name,
                action_type=action_type,
                params=params,
                success_probability=success_belief,
                cost_belief=cost_belief,
                quality_belief=quality_belief
            )
            
            plan.actions.append(action)
            plan.set_belief(success_belief)
            plan.set_belief(cost_belief)
            plan.set_belief(quality_belief)
        
        return plan
    
    def update_from_execution(self, plan: BayesianPlan, action_name: str, 
                             success: bool, cost: float = 0.0, quality: float = 0.0):
        """
        Update beliefs based on action execution outcome.
        This is the learning step - Bayesian updating.
        """
        outcome = {
            "success": success,
            "cost": cost,
            "quality": quality,
            "timestamp": datetime.now().timestamp()
        }
        
        plan.update_from_observation(action_name, outcome)
        
        # Also update global beliefs
        global_belief_name = f"tool_{action_name}"
        if global_belief_name not in self.global_beliefs:
            self.global_beliefs[global_belief_name] = self.create_tool_effectiveness_belief(action_name)
        
        self.global_beliefs[global_belief_name].update_beta(success)
        
        # Record in history
        self.execution_history.append({
            "plan_goal": plan.goal,
            "action": action_name,
            "outcome": outcome
        })
    
    def recommend_tool(self, task_description: str, available_tools: List[str]) -> Tuple[str, float]:
        """
        Recommend the best tool for a task based on current beliefs.
        
        Returns:
            (recommended_tool, expected_success_probability)
        """
        if not available_tools:
            return (None, 0.0)
        
        best_tool = None
        best_prob = 0.0
        
        for tool in available_tools:
            belief_name = f"tool_{tool}"
            if belief_name in self.global_beliefs:
                prob = self.global_beliefs[belief_name].expected_value()
            else:
                # Prior belief (uniform)
                prob = 0.5
            
            if prob > best_prob:
                best_prob = prob
                best_tool = tool
        
        # If no tool has high probability, recommend exploration
        if best_prob < 0.3 and available_tools:
            # Return first untested tool
            untested = [t for t in available_tools 
                       if f"tool_{t}" not in self.global_beliefs]
            if untested:
                return (untested[0], 0.5)  # Unknown, worth exploring
        
        # Ensure we return a valid tool
        if best_tool is None and available_tools:
            best_tool = available_tools[0]
            best_prob = 0.5
            
        return (best_tool, best_prob)
    
    def get_tool_ranking(self) -> List[Tuple[str, float, float]]:
        """
        Get ranked list of tools by expected effectiveness.
        
        Returns:
            List of (tool_name, expected_success_prob, uncertainty)
        """
        rankings = []
        for name, belief in self.global_beliefs.items():
            if belief.belief_type == BeliefType.TOOL_EFFECTIVENESS:
                tool_name = name.replace("tool_", "")
                rankings.append((
                    tool_name,
                    belief.expected_value(),
                    belief.uncertainty()
                ))
        
        # Sort by expected value, break ties by lower uncertainty
        rankings.sort(key=lambda x: (x[1], -x[2]), reverse=True)
        return rankings
    
    def get_learning_statistics(self) -> Dict[str, Any]:
        """Get statistics about what the planner has learned"""
        return {
            "total_executions": len(self.execution_history),
            "unique_tools_learned": sum(
                1 for b in self.global_beliefs.values()
                if b.belief_type == BeliefType.TOOL_EFFECTIVENESS
            ),
            "tool_rankings": self.get_tool_ranking(),
            "average_success_rate": sum(
                b.expected_value() for b in self.global_beliefs.values()
                if b.belief_type == BeliefType.TOOL_EFFECTIVENESS
            ) / len([b for b in self.global_beliefs.values() 
                   if b.belief_type == BeliefType.TOOL_EFFECTIVENESS]) if self.global_beliefs else 0,
            "recent_executions": self.execution_history[-10:] if self.execution_history else []
        }


# Convenience functions

def create_bayesian_planner(prior_strength: float = 2.0) -> BayesianPlanner:
    """Factory function to create a Bayesian planner"""
    return BayesianPlanner(prior_strength=prior_strength)


def quick_plan(goal: str, actions: List[str], planner: Optional[BayesianPlanner] = None) -> BayesianPlan:
    """Create a quick plan with simple action specifications"""
    if planner is None:
        planner = create_bayesian_planner()
    
    action_specs = [
        {"name": a, "type": "tool", "params": {}}
        for a in actions
    ]
    
    return planner.plan(goal, action_specs)
