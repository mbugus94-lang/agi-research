"""
Multi-Agent Diversity Framework

Implements epistemic diversity in multi-agent systems based on:
- "Many Agents, Not One" (arXiv:2603.29075): Diverse teams outperform single agents
- Agent-World research: Collaborative agents broaden search space
- A2A (Agent-to-Agent) protocol for inter-agent communication

Key Features:
- Diverse reasoning approaches (symbolic, neural, evolutionary, analogical)
- Consensus mechanisms with diversity preservation
- Epistemic diversity scoring
- Collective intelligence aggregation
- A2A communication protocol
"""

import uuid
import random
import math  # Added import
from enum import Enum, auto
from typing import Dict, List, Optional, Callable, Any, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import statistics


class ReasoningStyle(Enum):
    """Different reasoning approaches for epistemic diversity."""
    SYMBOLIC = "symbolic"      # Logic-based, rule-following
    NEURAL = "neural"          # Pattern recognition, statistical
    EVOLUTIONARY = "evolutionary"  # Variation, selection, adaptation
    ANALOGICAL = "analogical"  # Case-based, similarity matching
    CAUSAL = "causal"          # Cause-effect, intervention reasoning
    PROBABILISTIC = "probabilistic"  # Bayesian, uncertainty handling


class AgentRole(Enum):
    """Roles in collaborative problem solving."""
    PROPOSER = "proposer"      # Generates solutions
    CRITIC = "critic"          # Evaluates and challenges
    SYNTHESIZER = "synthesizer"  # Combines perspectives
    EXECUTOR = "executor"      # Implements solutions
    OBSERVER = "observer"      # Monitors and reports


@dataclass
class A2AMessage:
    """Agent-to-Agent communication message."""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str = ""
    recipient_id: Optional[str] = None  # None = broadcast
    message_type: str = ""  # proposal, critique, consensus_request, vote
    content: Any = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "recipient_id": self.recipient_id,
            "message_type": self.message_type,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }


@dataclass
class Solution:
    """A proposed solution with metadata."""
    solution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    proposer_id: str = ""
    content: Any = None
    reasoning_style: ReasoningStyle = ReasoningStyle.SYMBOLIC
    confidence: float = 0.5
    rationale: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    votes: Dict[str, float] = field(default_factory=dict)  # agent_id -> vote_score
    
    def to_dict(self) -> Dict:
        return {
            "solution_id": self.solution_id,
            "proposer_id": self.proposer_id,
            "content": self.content,
            "reasoning_style": self.reasoning_style.value,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "created_at": self.created_at,
            "vote_count": len(self.votes),
            "average_vote": statistics.mean(self.votes.values()) if self.votes else 0.0
        }


@dataclass
class DiversityMetrics:
    """Metrics for population diversity."""
    reasoning_diversity: float = 0.0  # Shannon entropy of reasoning styles
    opinion_diversity: float = 0.0    # Variance in opinions/solutions
    consensus_strength: float = 0.0   # Agreement level
    coverage_breadth: float = 0.0     # Solution space coverage
    
    def to_dict(self) -> Dict:
        return {
            "reasoning_diversity": round(self.reasoning_diversity, 3),
            "opinion_diversity": round(self.opinion_diversity, 3),
            "consensus_strength": round(self.consensus_strength, 3),
            "coverage_breadth": round(self.coverage_breadth, 3)
        }


class DiverseAgent:
    """
    An agent with specific reasoning style and role in collaborative system.
    """
    
    def __init__(self, agent_id: str, reasoning_style: ReasoningStyle,
                 role: AgentRole = AgentRole.PROPOSER, capabilities: Optional[List[str]] = None):
        self.agent_id = agent_id
        self.reasoning_style = reasoning_style
        self.role = role
        self.capabilities = capabilities or []
        self.message_inbox: List[A2AMessage] = []
        self.message_outbox: List[A2AMessage] = []
        self.solutions_proposed: List[str] = []
        self.votes_cast: Dict[str, float] = {}
        self.collaboration_score = 0.0
        
    def propose_solution(self, problem: Any, context: Optional[Dict] = None) -> Solution:
        """Generate a solution using the agent's reasoning style."""
        # Apply reasoning style to problem
        if self.reasoning_style == ReasoningStyle.SYMBOLIC:
            content = self._symbolic_reasoning(problem, context)
            rationale = "Used logical deduction and rule-based inference"
        elif self.reasoning_style == ReasoningStyle.NEURAL:
            content = self._neural_reasoning(problem, context)
            rationale = "Used pattern recognition and statistical inference"
        elif self.reasoning_style == ReasoningStyle.EVOLUTIONARY:
            content = self._evolutionary_reasoning(problem, context)
            rationale = "Used variation, selection, and adaptation"
        elif self.reasoning_style == ReasoningStyle.ANALOGICAL:
            content = self._analogical_reasoning(problem, context)
            rationale = "Used case-based reasoning and similarity matching"
        elif self.reasoning_style == ReasoningStyle.CAUSAL:
            content = self._causal_reasoning(problem, context)
            rationale = "Used cause-effect and intervention analysis"
        elif self.reasoning_style == ReasoningStyle.PROBABILISTIC:
            content = self._probabilistic_reasoning(problem, context)
            rationale = "Used Bayesian inference and uncertainty handling"
        else:
            content = {"approach": "default", "result": str(problem)}
            rationale = "Default reasoning"
        
        solution = Solution(
            proposer_id=self.agent_id,
            content=content,
            reasoning_style=self.reasoning_style,
            confidence=random.uniform(0.6, 0.95),
            rationale=rationale
        )
        self.solutions_proposed.append(solution.solution_id)
        return solution
    
    def _symbolic_reasoning(self, problem: Any, context: Optional[Dict]) -> Dict:
        """Logic-based reasoning."""
        return {
            "type": "symbolic",
            "rules_applied": ["deduction", "modus_ponens"],
            "steps": ["analyze_constraints", "derive_conclusion"],
            "result": f"symbolic_solution_{hash(str(problem)) % 1000}"
        }
    
    def _neural_reasoning(self, problem: Any, context: Optional[Dict]) -> Dict:
        """Pattern-based reasoning."""
        return {
            "type": "neural",
            "patterns_recognized": ["feature_extraction", "similarity_matching"],
            "activation": random.uniform(0.7, 0.99),
            "result": f"neural_solution_{hash(str(problem)) % 1000}"
        }
    
    def _evolutionary_reasoning(self, problem: Any, context: Optional[Dict]) -> Dict:
        """Variation and selection reasoning."""
        return {
            "type": "evolutionary",
            "generations": random.randint(10, 100),
            "mutations": random.randint(5, 50),
            "fitness": random.uniform(0.6, 0.95),
            "result": f"evolved_solution_{hash(str(problem)) % 1000}"
        }
    
    def _analogical_reasoning(self, problem: Any, context: Optional[Dict]) -> Dict:
        """Case-based reasoning."""
        cases = context.get("similar_cases", []) if context else []
        return {
            "type": "analogical",
            "cases_considered": len(cases) + random.randint(3, 10),
            "similarity_threshold": random.uniform(0.7, 0.9),
            "result": f"analogical_solution_{hash(str(problem)) % 1000}"
        }
    
    def _causal_reasoning(self, problem: Any, context: Optional[Dict]) -> Dict:
        """Cause-effect reasoning."""
        return {
            "type": "causal",
            "interventions": ["identify_causes", "test_effects"],
            "counterfactuals_considered": random.randint(2, 8),
            "result": f"causal_solution_{hash(str(problem)) % 1000}"
        }
    
    def _probabilistic_reasoning(self, problem: Any, context: Optional[Dict]) -> Dict:
        """Bayesian reasoning."""
        return {
            "type": "probabilistic",
            "prior_probability": random.uniform(0.3, 0.7),
            "posterior_probability": random.uniform(0.6, 0.95),
            "uncertainty": random.uniform(0.05, 0.2),
            "result": f"probabilistic_solution_{hash(str(problem)) % 1000}"
        }
    
    def evaluate_solution(self, solution: Solution, problem: Any) -> float:
        """Evaluate a solution and return a score (0.0-1.0)."""
        # Agents prefer solutions from different reasoning styles (diversity bonus)
        base_score = random.uniform(0.5, 0.9)
        
        if solution.reasoning_style != self.reasoning_style:
            # Diversity bonus - agents value different perspectives
            base_score += 0.1
        
        if solution.proposer_id == self.agent_id:
            # Slight self-preference
            base_score += 0.05
        
        return min(1.0, base_score)
    
    def vote(self, solutions: List[Solution], problem: Any) -> Dict[str, float]:
        """Vote on solutions, returning solution_id -> score mapping."""
        votes = {}
        for solution in solutions:
            score = self.evaluate_solution(solution, problem)
            votes[solution.solution_id] = score
            self.votes_cast[solution.solution_id] = score
        return votes
    
    def receive_message(self, message: A2AMessage):
        """Receive a message from another agent."""
        self.message_inbox.append(message)
    
    def send_message(self, recipient_id: Optional[str], message_type: str, 
                    content: Any, metadata: Optional[Dict] = None) -> A2AMessage:
        """Send a message to another agent (or broadcast)."""
        message = A2AMessage(
            sender_id=self.agent_id,
            recipient_id=recipient_id,
            message_type=message_type,
            content=content,
            metadata=metadata or {}
        )
        self.message_outbox.append(message)
        return message
    
    def get_collaboration_stats(self) -> Dict:
        """Get agent's collaboration statistics."""
        return {
            "agent_id": self.agent_id,
            "reasoning_style": self.reasoning_style.value,
            "role": self.role.value,
            "solutions_proposed": len(self.solutions_proposed),
            "votes_cast": len(self.votes_cast),
            "messages_received": len(self.message_inbox),
            "messages_sent": len(self.message_outbox)
        }
    
    def __repr__(self) -> str:
        return f"DiverseAgent({self.agent_id}, {self.reasoning_style.value}, {self.role.value})"


class MultiAgentDiversityFramework:
    """
    Framework for managing diverse agent populations and collective intelligence.
    """
    
    def __init__(self, min_diversity_threshold: float = 0.5):
        self.agents: Dict[str, DiverseAgent] = {}
        self.solutions: Dict[str, Solution] = {}
        self.message_log: List[A2AMessage] = []
        self.min_diversity_threshold = min_diversity_threshold
        self.collaboration_history: List[Dict] = []
        
    def create_diverse_population(self, size: int, 
                                  reasoning_styles: Optional[List[ReasoningStyle]] = None,
                                  roles: Optional[List[AgentRole]] = None) -> List[str]:
        """Create a diverse population of agents."""
        if reasoning_styles is None:
            reasoning_styles = list(ReasoningStyle)
        if roles is None:
            roles = [AgentRole.PROPOSER, AgentRole.CRITIC, AgentRole.SYNTHESIZER]
        
        agent_ids = []
        for i in range(size):
            style = reasoning_styles[i % len(reasoning_styles)]
            role = roles[i % len(roles)]
            agent_id = f"agent_{i}_{style.value}_{role.value}"
            
            agent = DiverseAgent(
                agent_id=agent_id,
                reasoning_style=style,
                role=role
            )
            self.agents[agent_id] = agent
            agent_ids.append(agent_id)
        
        return agent_ids
    
    def register_agent(self, agent: DiverseAgent) -> str:
        """Register an existing agent."""
        self.agents[agent.agent_id] = agent
        return agent.agent_id
    
    def broadcast_message(self, sender_id: str, message_type: str, 
                         content: Any, metadata: Optional[Dict] = None):
        """Broadcast a message to all agents."""
        if sender_id not in self.agents:
            raise ValueError(f"Sender {sender_id} not found")
        
        message = A2AMessage(
            sender_id=sender_id,
            recipient_id=None,  # Broadcast
            message_type=message_type,
            content=content,
            metadata=metadata or {}
        )
        
        # Deliver to all agents except sender
        for agent_id, agent in self.agents.items():
            if agent_id != sender_id:
                agent.receive_message(message)
        
        self.message_log.append(message)
        return message
    
    def send_direct_message(self, sender_id: str, recipient_id: str,
                           message_type: str, content: Any,
                           metadata: Optional[Dict] = None) -> A2AMessage:
        """Send a direct message between agents."""
        if sender_id not in self.agents:
            raise ValueError(f"Sender {sender_id} not found")
        if recipient_id not in self.agents:
            raise ValueError(f"Recipient {recipient_id} not found")
        
        message = A2AMessage(
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_type=message_type,
            content=content,
            metadata=metadata or {}
        )
        
        self.agents[recipient_id].receive_message(message)
        self.agents[sender_id].message_outbox.append(message)
        self.message_log.append(message)
        return message
    
    def collaborative_problem_solving(self, problem: Any, 
                                     max_rounds: int = 3,
                                     context: Optional[Dict] = None) -> Dict:
        """
        Execute collaborative problem solving with the agent population.
        
        Phase 1: Each agent proposes a solution
        Phase 2: Agents vote on solutions
        Phase 3: Aggregate results with diversity weighting
        """
        # Phase 1: Proposal generation
        proposals = []
        for agent in self.agents.values():
            if agent.role == AgentRole.PROPOSER:
                solution = agent.propose_solution(problem, context)
                self.solutions[solution.solution_id] = solution
                proposals.append(solution)
        
        # Phase 2: Voting
        for agent in self.agents.values():
            votes = agent.vote(proposals, problem)
            for solution_id, score in votes.items():
                if solution_id in self.solutions:
                    self.solutions[solution_id].votes[agent.agent_id] = score
        
        # Phase 3: Aggregation with diversity weighting
        aggregated = self._aggregate_solutions(proposals)
        
        # Calculate diversity metrics
        metrics = self.calculate_diversity_metrics(proposals)
        
        result = {
            "problem": problem,
            "proposals_count": len(proposals),
            "proposals": [p.to_dict() for p in proposals],
            "aggregated_solution": aggregated,
            "diversity_metrics": metrics.to_dict(),
            "consensus_reached": metrics.consensus_strength > 0.7,
            "rounds": max_rounds
        }
        
        self.collaboration_history.append(result)
        return result
    
    def _aggregate_solutions(self, solutions: List[Solution]) -> Dict:
        """Aggregate solutions with diversity weighting."""
        if not solutions:
            return {}
        
        # Calculate weights based on diversity bonus
        style_counts = defaultdict(int)
        for s in solutions:
            style_counts[s.reasoning_style] += 1
        
        weighted_votes = {}
        for solution in solutions:
            # Diversity bonus: underrepresented styles get higher weight
            style_count = style_counts[solution.reasoning_style]
            diversity_weight = 1.0 / style_count if style_count > 0 else 1.0
            
            # Average vote score
            avg_vote = statistics.mean(solution.votes.values()) if solution.votes else 0.0
            
            weighted_votes[solution.solution_id] = avg_vote * diversity_weight
        
        # Select top solution
        if weighted_votes:
            top_solution_id = max(weighted_votes, key=weighted_votes.get)
            top_solution = self.solutions.get(top_solution_id)
            return {
                "selected_solution_id": top_solution_id,
                "proposer": top_solution.proposer_id if top_solution else None,
                "reasoning_style": top_solution.reasoning_style.value if top_solution else None,
                "weighted_score": weighted_votes.get(top_solution_id, 0),
                "diversity_bonus_applied": True
            }
        return {}
    
    def calculate_diversity_metrics(self, solutions: Optional[List[Solution]] = None) -> DiversityMetrics:
        """Calculate diversity metrics for the agent population."""
        if solutions is None:
            solutions = list(self.solutions.values())
        
        # Reasoning diversity (Shannon entropy)
        style_counts = defaultdict(int)
        for agent in self.agents.values():
            style_counts[agent.reasoning_style] += 1
        
        total = len(self.agents)
        entropy = 0.0
        for count in style_counts.values():
            if count > 0:
                p = count / total
                entropy -= p * math.log2(p)  # Proper Shannon entropy calculation
        
        max_entropy = len(ReasoningStyle)
        reasoning_diversity = entropy / max_entropy if max_entropy > 0 else 0.0
        
        # Opinion diversity (variance in vote patterns)
        if solutions and all(s.votes for s in solutions):
            all_votes = []
            for s in solutions:
                all_votes.extend(s.votes.values())
            if len(all_votes) > 1:
                opinion_diversity = statistics.stdev(all_votes) if len(all_votes) > 1 else 0.0
            else:
                opinion_diversity = 0.0
        else:
            opinion_diversity = 0.0
        
        # Consensus strength
        if solutions:
            vote_counts = defaultdict(int)
            for s in solutions:
                for voter, vote in s.votes.items():
                    if vote > 0.7:  # Strong support threshold
                        vote_counts[s.solution_id] += 1
            if vote_counts:
                max_votes = max(vote_counts.values())
                consensus_strength = max_votes / len(self.agents)
            else:
                consensus_strength = 0.0
        else:
            consensus_strength = 0.0
        
        # Coverage breadth
        unique_styles = len(set(s.reasoning_style for s in solutions))
        coverage_breadth = unique_styles / len(ReasoningStyle)
        
        return DiversityMetrics(
            reasoning_diversity=reasoning_diversity,
            opinion_diversity=opinion_diversity,
            consensus_strength=consensus_strength,
            coverage_breadth=coverage_breadth
        )
    
    def get_population_stats(self) -> Dict:
        """Get statistics about the agent population."""
        style_counts = defaultdict(int)
        role_counts = defaultdict(int)
        
        for agent in self.agents.values():
            style_counts[agent.reasoning_style.value] += 1
            role_counts[agent.role.value] += 1
        
        return {
            "total_agents": len(self.agents),
            "reasoning_styles": dict(style_counts),
            "roles": dict(role_counts),
            "total_solutions": len(self.solutions),
            "total_messages": len(self.message_log),
            "collaboration_sessions": len(self.collaboration_history)
        }
    
    def identify_experts(self, domain: str) -> List[str]:
        """Identify agents with relevant capabilities for a domain."""
        experts = []
        for agent_id, agent in self.agents.items():
            if domain in agent.capabilities or agent.reasoning_style == ReasoningStyle.SYMBOLIC:
                experts.append(agent_id)
        return experts
    
    def simulate_debate(self, topic: str, rounds: int = 3) -> Dict:
        """Simulate a structured debate on a topic."""
        # Proposers make arguments
        arguments = []
        for agent in self.agents.values():
            if agent.role == AgentRole.PROPOSER:
                arg = agent.send_message(None, "argument", {
                    "topic": topic,
                    "stance": random.choice(["for", "against"]),
                    "reasoning": agent.reasoning_style.value
                })
                arguments.append(arg)
        
        # Critics evaluate
        critiques = []
        for agent in self.agents.values():
            if agent.role == AgentRole.CRITIC:
                for arg in arguments:
                    critique = agent.send_message(arg.sender_id, "critique", {
                        "target_argument": arg.message_id,
                        "evaluation": random.uniform(0.3, 0.9),
                        "feedback": f"Critique from {agent.reasoning_style.value} perspective"
                    })
                    critiques.append(critique)
        
        # Synthesizers create summary
        syntheses = []
        for agent in self.agents.values():
            if agent.role == AgentRole.SYNTHESIZER:
                synthesis = agent.send_message(None, "synthesis", {
                    "topic": topic,
                    "arguments_considered": len(arguments),
                    "critiques_addressed": len(critiques),
                    "synthesis": f"Integrated view from {agent.reasoning_style.value} perspective"
                })
                syntheses.append(synthesis)
        
        return {
            "topic": topic,
            "rounds": rounds,
            "arguments": len(arguments),
            "critiques": len(critiques),
            "syntheses": len(syntheses),
            "diversity_factor": len(set(a.reasoning_style for a in self.agents.values())) / len(ReasoningStyle)
        }


def create_diverse_team(size: int = 6) -> MultiAgentDiversityFramework:
    """Helper function to create a diverse agent team."""
    framework = MultiAgentDiversityFramework()
    
    # Create agents with different styles
    styles = list(ReasoningStyle)
    roles = [AgentRole.PROPOSER, AgentRole.CRITIC, AgentRole.SYNTHESIZER,
             AgentRole.EXECUTOR, AgentRole.OBSERVER, AgentRole.PROPOSER]
    
    for i in range(size):
        agent = DiverseAgent(
            agent_id=f"team_member_{i}",
            reasoning_style=styles[i % len(styles)],
            role=roles[i % len(roles)],
            capabilities=[f"capability_{j}" for j in range(i + 1)]
        )
        framework.register_agent(agent)
    
    return framework


# Export main classes
__all__ = [
    'MultiAgentDiversityFramework',
    'DiverseAgent',
    'Solution',
    'A2AMessage',
    'DiversityMetrics',
    'ReasoningStyle',
    'AgentRole',
    'create_diverse_team'
]