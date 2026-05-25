"""
Multi-Agent Coordination Skill Module

Implements delegation and collaboration patterns for multi-agent systems.
Based on research findings from MetaAgent-X (arXiv:2605.14212v1) and
Agentic Systems as Boosting Weak Reasoning Models (arXiv:2605.14163v1).

Key capabilities:
- Task decomposition and delegation to specialized agents
- Result aggregation from multiple agent outputs
- Conflict resolution when agents disagree
- Dynamic agent team assembly based on task requirements
- Hierarchical coordination (manager + worker agents)

References:
- MetaAgent-X: End-to-end RL for automatic multi-agent systems
- Co-Scientist/Robin: AI agent teams for research (Nature 2026)
- Google ADK v2.0.0: Dynamic agent collaboration patterns
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Tuple
from enum import Enum
import hashlib
import time
from datetime import datetime
from collections import defaultdict


class AgentRole(Enum):
    """Roles an agent can take in a multi-agent system"""
    COORDINATOR = "coordinator"      # Manages delegation and aggregation
    WORKER = "worker"                # Executes specific subtasks
    VERIFIER = "verifier"            # Validates outputs from other agents
    SPECIALIST = "specialist"        # Deep expertise in specific domain
    GENERALIST = "generalist"        # Broad capability across domains


class DelegationStrategy(Enum):
    """Strategies for task delegation"""
    ROUND_ROBIN = "round_robin"      # Distribute evenly across workers
    CAPABILITY_MATCH = "capability"  # Match task to best-suited agent
    LOAD_BALANCED = "load_balanced"  # Consider current agent load
    REDUNDANT = "redundant"          # Send to multiple agents for verification
    HIERARCHICAL = "hierarchical"    # Manager delegates to specialists


class AggregationMethod(Enum):
    """Methods for aggregating results from multiple agents"""
    VOTING = "voting"                # Simple majority vote
    WEIGHTED = "weighted"            # Weight by agent confidence/history
    CONSENSUS = "consensus"          # Require agreement above threshold
    BEST_OF_N = "best_of_n"          # Select highest quality output
    MERGE = "merge"                  # Combine outputs into unified result


@dataclass
class AgentProfile:
    """Profile of a participating agent"""
    agent_id: str
    role: AgentRole
    capabilities: List[str] = field(default_factory=list)
    current_load: int = 0
    success_rate: float = 0.8
    avg_response_time: float = 1.0
    last_active: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def capability_match_score(self, task_requirements: List[str]) -> float:
        """Calculate how well this agent matches task requirements"""
        if not task_requirements:
            return 0.5
        matches = sum(1 for req in task_requirements if req in self.capabilities)
        return matches / len(task_requirements)
    
    def availability_score(self) -> float:
        """Calculate current availability (0-1, higher = more available)"""
        load_factor = 1.0 / (1.0 + self.current_load * 0.2)
        recency = min(1.0, (time.time() - self.last_active) / 60)
        return load_factor * (0.5 + 0.5 * recency)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role.value,
            "capabilities": self.capabilities,
            "current_load": self.current_load,
            "success_rate": self.success_rate,
            "avg_response_time": self.avg_response_time,
            "availability": self.availability_score()
        }


@dataclass
class SubTask:
    """A delegated subtask"""
    task_id: str
    description: str
    assigned_to: str
    requirements: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, in_progress, complete, failed
    result: Optional[Any] = None
    confidence: float = 0.0
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    
    def is_ready(self, completed_task_ids: set) -> bool:
        """Check if all dependencies are satisfied"""
        return all(dep in completed_task_ids for dep in self.dependencies)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "assigned_to": self.assigned_to,
            "requirements": self.requirements,
            "dependencies": self.dependencies,
            "status": self.status,
            "has_result": self.result is not None,
            "confidence": self.confidence,
            "duration": (self.completed_at - self.created_at) 
                        if self.completed_at else None
        }


@dataclass
class AgentOutput:
    """Output from an agent with metadata for aggregation"""
    agent_id: str
    subtask_id: str
    output: Any
    confidence: float
    reasoning: str = ""
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "subtask_id": self.subtask_id,
            "output": self.output,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "timestamp": self.timestamp
        }


@dataclass
class DelegationPlan:
    """A complete plan for delegating a task across agents"""
    plan_id: str
    original_task: str
    strategy: DelegationStrategy
    subtasks: List[SubTask] = field(default_factory=list)
    agent_assignments: Dict[str, str] = field(default_factory=dict)  # task_id -> agent_id
    created_at: float = field(default_factory=time.time)
    
    def get_ready_subtasks(self, completed_ids: set) -> List[SubTask]:
        """Get subtasks ready for execution"""
        return [st for st in self.subtasks if st.is_ready(completed_ids)]
    
    def completion_rate(self) -> float:
        """Calculate completion percentage"""
        if not self.subtasks:
            return 0.0
        complete = sum(1 for st in self.subtasks if st.status == "complete")
        return complete / len(self.subtasks)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "original_task": self.original_task,
            "strategy": self.strategy.value,
            "completion_rate": self.completion_rate(),
            "subtask_count": len(self.subtasks),
            "subtasks": [st.to_dict() for st in self.subtasks]
        }


@dataclass
class AggregationResult:
    """Result of aggregating multiple agent outputs"""
    outputs: List[AgentOutput]
    method: AggregationMethod
    final_result: Any
    confidence: float
    agreement_score: float  # How much agents agreed
    dissenters: List[str] = field(default_factory=list)  # Agents who disagreed
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "output_count": len(self.outputs),
            "method": self.method.value,
            "confidence": self.confidence,
            "agreement_score": self.agreement_score,
            "dissenter_count": len(self.dissenters),
            "final_result": self.final_result
        }


class AgentRegistry:
    """Registry of available agents for coordination"""
    
    def __init__(self):
        self.agents: Dict[str, AgentProfile] = {}
        self.capability_index: Dict[str, List[str]] = defaultdict(list)
    
    def register_agent(self, profile: AgentProfile) -> None:
        """Register an agent for coordination"""
        self.agents[profile.agent_id] = profile
        for cap in profile.capabilities:
            self.capability_index[cap].append(profile.agent_id)
    
    def unregister_agent(self, agent_id: str) -> bool:
        """Remove an agent from registry"""
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            for cap in agent.capabilities:
                if agent_id in self.capability_index[cap]:
                    self.capability_index[cap].remove(agent_id)
            del self.agents[agent_id]
            return True
        return False
    
    def get_agent(self, agent_id: str) -> Optional[AgentProfile]:
        """Get agent by ID"""
        return self.agents.get(agent_id)
    
    def find_agents_by_capability(
        self,
        capability: str,
        min_availability: float = 0.3
    ) -> List[AgentProfile]:
        """Find agents with specific capability"""
        agent_ids = self.capability_index.get(capability, [])
        agents = [self.agents[aid] for aid in agent_ids if aid in self.agents]
        return [a for a in agents if a.availability_score() >= min_availability]
    
    def find_best_agent(
        self,
        requirements: List[str],
        strategy: DelegationStrategy = DelegationStrategy.CAPABILITY_MATCH
    ) -> Optional[AgentProfile]:
        """Find best agent for given requirements"""
        candidates = []
        
        # Find agents matching at least one requirement
        for req in requirements:
            for agent in self.find_agents_by_capability(req):
                if agent not in candidates:
                    candidates.append(agent)
        
        if not candidates:
            return None
        
        # Score candidates based on strategy
        if strategy == DelegationStrategy.CAPABILITY_MATCH:
            scored = [(a.capability_match_score(requirements), a) for a in candidates]
        elif strategy == DelegationStrategy.LOAD_BALANCED:
            scored = [(a.availability_score() * a.success_rate, a) for a in candidates]
        else:
            scored = [(a.success_rate, a) for a in candidates]
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1] if scored else None
    
    def get_team_for_task(
        self,
        task_description: str,
        team_size: int = 3,
        required_capabilities: Optional[List[str]] = None
    ) -> List[AgentProfile]:
        """Assemble a team of agents for a task"""
        required_capabilities = required_capabilities or []
        
        # Extract capabilities from task description
        task_caps = self._extract_capabilities(task_description)
        all_requirements = list(set(required_capabilities + task_caps))
        
        # Find best team composition
        candidates = []
        for agent in self.agents.values():
            match_score = agent.capability_match_score(all_requirements)
            if match_score > 0:
                candidates.append((match_score, agent))
        
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        # Select top N with diverse capabilities
        selected = []
        covered_caps = set()
        for _, agent in candidates:
            if len(selected) >= team_size:
                break
            # Check if agent adds new capabilities
            new_caps = set(agent.capabilities) - covered_caps
            if new_caps or len(selected) < team_size // 2:
                selected.append(agent)
                covered_caps.update(agent.capabilities)
        
        return selected
    
    def _extract_capabilities(self, task_description: str) -> List[str]:
        """Extract capability requirements from task description"""
        capability_keywords = {
            "research": ["research", "search", "analysis", "investigation"],
            "coding": ["code", "programming", "development", "implementation"],
            "writing": ["write", "document", "content", "draft"],
            "math": ["math", "calculation", "computation", "numerical"],
            "web": ["web", "http", "api", "scraping"],
            "data": ["data", "database", "storage", "retrieval"],
            "planning": ["plan", "strategy", "coordinate", "organize"],
            "verification": ["verify", "test", "validate", "check"]
        }
        
        task_lower = task_description.lower()
        found_caps = []
        for cap, keywords in capability_keywords.items():
            if any(kw in task_lower for kw in keywords):
                found_caps.append(cap)
        
        return found_caps
    
    def update_agent_metrics(
        self,
        agent_id: str,
        success: bool,
        response_time: float
    ) -> None:
        """Update agent performance metrics"""
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            # Update success rate with exponential moving average
            agent.success_rate = 0.9 * agent.success_rate + 0.1 * (1.0 if success else 0.0)
            agent.avg_response_time = 0.9 * agent.avg_response_time + 0.1 * response_time
            agent.last_active = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_count": len(self.agents),
            "capability_count": len(self.capability_index),
            "agents": [a.to_dict() for a in self.agents.values()]
        }


class TaskDecomposer:
    """Decomposes tasks into delegable subtasks"""
    
    def __init__(self, registry: AgentRegistry):
        self.registry = registry
    
    def decompose(
        self,
        task: str,
        strategy: DelegationStrategy = DelegationStrategy.HIERARCHICAL
    ) -> DelegationPlan:
        """Decompose a task into subtasks for delegation"""
        plan_id = hashlib.md5(f"{task}:{time.time()}".encode()).hexdigest()[:12]
        
        # Analyze task to determine decomposition approach
        caps = self._analyze_task(task)
        
        if strategy == DelegationStrategy.HIERARCHICAL:
            subtasks = self._hierarchical_decomposition(task, caps)
        elif strategy == DelegationStrategy.REDUNDANT:
            subtasks = self._redundant_decomposition(task, caps)
        else:
            subtasks = self._sequential_decomposition(task, caps)
        
        return DelegationPlan(
            plan_id=plan_id,
            original_task=task,
            strategy=strategy,
            subtasks=subtasks
        )
    
    def _analyze_task(self, task: str) -> List[str]:
        """Analyze task to identify required capabilities"""
        return self.registry._extract_capabilities(task)
    
    def _sequential_decomposition(
        self,
        task: str,
        capabilities: List[str]
    ) -> List[SubTask]:
        """Simple sequential decomposition"""
        subtasks = []
        prev_id = None
        
        for i, cap in enumerate(capabilities[:4]):
            task_id = f"seq_{i}"
            subtasks.append(SubTask(
                task_id=task_id,
                description=f"{cap.capitalize()} phase of: {task[:50]}",
                assigned_to="",  # Will be assigned later
                requirements=[cap],
                dependencies=[prev_id] if prev_id else []
            ))
            prev_id = task_id
        
        return subtasks
    
    def _hierarchical_decomposition(
        self,
        task: str,
        capabilities: List[str]
    ) -> List[SubTask]:
        """Hierarchical decomposition with coordination subtasks"""
        subtasks = []
        
        # Add coordination/management subtask
        subtasks.append(SubTask(
            task_id="coord_0",
            description=f"Coordinate execution of: {task[:50]}",
            assigned_to="",
            requirements=["planning", "coordination"],
            dependencies=[]
        ))
        
        # Add parallel capability subtasks
        for i, cap in enumerate(capabilities[:3]):
            subtasks.append(SubTask(
                task_id=f"parallel_{i}",
                description=f"Execute {cap} component",
                assigned_to="",
                requirements=[cap],
                dependencies=["coord_0"]
            ))
        
        # Add integration subtask
        parallel_ids = [f"parallel_{i}" for i in range(len(capabilities[:3]))]
        subtasks.append(SubTask(
            task_id="integrate_0",
            description="Integrate results from all components",
            assigned_to="",
            requirements=["planning", "verification"],
            dependencies=parallel_ids
        ))
        
        return subtasks
    
    def _redundant_decomposition(
        self,
        task: str,
        capabilities: List[str]
    ) -> List[SubTask]:
        """Create redundant subtasks for verification (best-of-N)"""
        subtasks = []
        
        # Create 3 parallel instances of the same task
        for i in range(3):
            subtasks.append(SubTask(
                task_id=f"redundant_{i}",
                description=f"Instance {i+1}: {task[:50]}",
                assigned_to="",
                requirements=capabilities,
                dependencies=[]  # All parallel
            ))
        
        return subtasks


class ResultAggregator:
    """Aggregates results from multiple agents"""
    
    def aggregate(
        self,
        outputs: List[AgentOutput],
        method: AggregationMethod = AggregationMethod.WEIGHTED,
        agent_registry: Optional[AgentRegistry] = None
    ) -> AggregationResult:
        """Aggregate outputs from multiple agents"""
        if not outputs:
            return AggregationResult(
                outputs=[],
                method=method,
                final_result=None,
                confidence=0.0,
                agreement_score=0.0
            )
        
        if len(outputs) == 1:
            return AggregationResult(
                outputs=outputs,
                method=method,
                final_result=outputs[0].output,
                confidence=outputs[0].confidence,
                agreement_score=1.0
            )
        
        if method == AggregationMethod.VOTING:
            return self._voting_aggregate(outputs)
        elif method == AggregationMethod.WEIGHTED:
            return self._weighted_aggregate(outputs, agent_registry)
        elif method == AggregationMethod.BEST_OF_N:
            return self._best_of_n_aggregate(outputs)
        elif method == AggregationMethod.CONSENSUS:
            return self._consensus_aggregate(outputs)
        else:
            return self._merge_aggregate(outputs)
    
    def _voting_aggregate(self, outputs: List[AgentOutput]) -> AggregationResult:
        """Simple voting aggregation"""
        # Group outputs by their string representation
        votes: Dict[str, List[AgentOutput]] = defaultdict(list)
        for out in outputs:
            key = str(out.output)
            votes[key].append(out)
        
        # Find majority
        majority = max(votes.values(), key=len)
        final_result = majority[0].output
        
        # Calculate agreement
        agreement = len(majority) / len(outputs)
        dissenters = [o.agent_id for o in outputs if o not in majority]
        
        return AggregationResult(
            outputs=outputs,
            method=AggregationMethod.VOTING,
            final_result=final_result,
            confidence=sum(o.confidence for o in majority) / len(majority),
            agreement_score=agreement,
            dissenters=dissenters
        )
    
    def _weighted_aggregate(
        self,
        outputs: List[AgentOutput],
        registry: Optional[AgentRegistry]
    ) -> AggregationResult:
        """Weighted aggregation by agent success rate and output confidence"""
        weighted_outputs = []
        
        for out in outputs:
            weight = out.confidence
            if registry:
                agent = registry.get_agent(out.agent_id)
                if agent:
                    weight *= agent.success_rate
            weighted_outputs.append((weight, out))
        
        # Select highest weighted
        weighted_outputs.sort(key=lambda x: x[0], reverse=True)
        best = weighted_outputs[0][1]
        
        # Calculate weighted agreement
        total_weight = sum(w for w, _ in weighted_outputs)
        agreement = weighted_outputs[0][0] / total_weight if total_weight > 0 else 0
        
        dissenters = [o.agent_id for w, o in weighted_outputs[1:] if w < 0.5 * best.confidence]
        
        return AggregationResult(
            outputs=outputs,
            method=AggregationMethod.WEIGHTED,
            final_result=best.output,
            confidence=best.confidence * agreement,
            agreement_score=agreement,
            dissenters=dissenters
        )
    
    def _best_of_n_aggregate(self, outputs: List[AgentOutput]) -> AggregationResult:
        """Select best output by confidence"""
        best = max(outputs, key=lambda o: o.confidence)
        
        # Count how many are close to best
        threshold = best.confidence * 0.9
        agreeing = [o for o in outputs if o.confidence >= threshold]
        
        dissenters = [o.agent_id for o in outputs if o.confidence < threshold]
        
        return AggregationResult(
            outputs=outputs,
            method=AggregationMethod.BEST_OF_N,
            final_result=best.output,
            confidence=best.confidence,
            agreement_score=len(agreeing) / len(outputs),
            dissenters=dissenters
        )
    
    def _consensus_aggregate(
        self,
        outputs: List[AgentOutput],
        threshold: float = 0.7
    ) -> AggregationResult:
        """Require consensus above threshold"""
        avg_confidence = sum(o.confidence for o in outputs) / len(outputs)
        
        if avg_confidence >= threshold:
            # Use voting result if consensus exists
            return self._voting_aggregate(outputs)
        else:
            # Return uncertainty indication
            return AggregationResult(
                outputs=outputs,
                method=AggregationMethod.CONSENSUS,
                final_result={
                    "status": "low_confidence",
                    "candidates": [o.output for o in outputs],
                    "recommendation": "human_review"
                },
                confidence=avg_confidence,
                agreement_score=avg_confidence,
                dissenters=[o.agent_id for o in outputs]
            )
    
    def _merge_aggregate(self, outputs: List[AgentOutput]) -> AggregationResult:
        """Merge outputs into unified result"""
        # For structured data, merge fields
        # For text, concatenate or synthesize
        merged = {
            "contributions": [o.output for o in outputs],
            "agents": [o.agent_id for o in outputs],
            "confidences": [o.confidence for o in outputs]
        }
        
        return AggregationResult(
            outputs=outputs,
            method=AggregationMethod.MERGE,
            final_result=merged,
            confidence=sum(o.confidence for o in outputs) / len(outputs),
            agreement_score=1.0,  # Merging doesn't require agreement
            dissenters=[]
        )


class MultiAgentCoordinator:
    """
    Main coordination component for multi-agent systems.
    
    Implements patterns from MetaAgent-X and Co-Scientist research.
    """
    
    def __init__(self):
        self.registry = AgentRegistry()
        self.decomposer = TaskDecomposer(self.registry)
        self.aggregator = ResultAggregator()
        self.active_plans: Dict[str, DelegationPlan] = {}
        self.execution_history: List[Dict[str, Any]] = []
    
    def register_agent(
        self,
        agent_id: str,
        role: AgentRole,
        capabilities: List[str],
        **kwargs
    ) -> AgentProfile:
        """Register an agent for coordination"""
        profile = AgentProfile(
            agent_id=agent_id,
            role=role,
            capabilities=capabilities,
            **kwargs
        )
        self.registry.register_agent(profile)
        return profile
    
    def delegate_task(
        self,
        task: str,
        strategy: DelegationStrategy = DelegationStrategy.CAPABILITY_MATCH,
        aggregation: AggregationMethod = AggregationMethod.WEIGHTED,
        required_capabilities: Optional[List[str]] = None
    ) -> DelegationPlan:
        """
        Delegate a task using multi-agent coordination.
        
        Returns a delegation plan that can be executed.
        """
        # Create delegation plan
        plan = self.decomposer.decompose(task, strategy)
        
        # Find agents for each subtask
        for subtask in plan.subtasks:
            agent = self.registry.find_best_agent(
                subtask.requirements,
                strategy
            )
            if agent:
                subtask.assigned_to = agent.agent_id
                plan.agent_assignments[subtask.task_id] = agent.agent_id
                agent.current_load += 1
        
        self.active_plans[plan.plan_id] = plan
        return plan
    
    def execute_plan(
        self,
        plan: DelegationPlan,
        execution_callback: Optional[Callable[[SubTask], AgentOutput]] = None
    ) -> AggregationResult:
        """
        Execute a delegation plan and aggregate results.
        
        execution_callback: Function that takes a SubTask and returns AgentOutput
        """
        if not execution_callback:
            raise ValueError("execution_callback is required")
        
        completed_ids = set()
        outputs: List[AgentOutput] = []
        
        # Execute subtasks respecting dependencies
        while len(completed_ids) < len(plan.subtasks):
            ready = plan.get_ready_subtasks(completed_ids)
            if not ready:
                break  # Deadlock or all done
            
            for subtask in ready:
                if subtask.status == "pending":
                    subtask.status = "in_progress"
                    
                    # Execute via callback
                    output = execution_callback(subtask)
                    outputs.append(output)
                    
                    # Update subtask
                    subtask.result = output.output
                    subtask.confidence = output.confidence
                    subtask.status = "complete"
                    subtask.completed_at = time.time()
                    
                    completed_ids.add(subtask.task_id)
                    
                    # Update agent metrics
                    self.registry.update_agent_metrics(
                        subtask.assigned_to,
                        success=output.confidence > 0.5,
                        response_time=time.time() - subtask.created_at
                    )
                    
                    # Reduce agent load
                    agent = self.registry.get_agent(subtask.assigned_to)
                    if agent:
                        agent.current_load = max(0, agent.current_load - 1)
        
        # Aggregate results
        result = self.aggregator.aggregate(outputs, AggregationMethod.WEIGHTED, self.registry)
        
        # Record execution
        self.execution_history.append({
            "plan_id": plan.plan_id,
            "task": plan.original_task,
            "strategy": plan.strategy.value,
            "success": result.confidence > 0.5,
            "confidence": result.confidence,
            "agreement": result.agreement_score
        })
        
        return result
    
    def coordinate_team(
        self,
        task: str,
        team_size: int = 3,
        required_capabilities: Optional[List[str]] = None
    ) -> Tuple[List[AgentProfile], DelegationPlan]:
        """
        Assemble a team and create a delegation plan.
        
        Returns the assembled team and delegation plan.
        """
        team = self.registry.get_team_for_task(
            task,
            team_size,
            required_capabilities
        )
        
        plan = self.delegate_task(
            task,
            strategy=DelegationStrategy.HIERARCHICAL,
            required_capabilities=required_capabilities
        )
        
        return team, plan
    
    def get_coordination_stats(self) -> Dict[str, Any]:
        """Get statistics on coordination performance"""
        if not self.execution_history:
            return {
                "executions": 0,
                "registered_agents": len(self.registry.agents),
                "active_plans": len(self.active_plans)
            }
        
        recent = self.execution_history[-100:]  # Last 100
        
        return {
            "executions": len(self.execution_history),
            "avg_confidence": sum(e["confidence"] for e in recent) / len(recent),
            "avg_agreement": sum(e["agreement"] for e in recent) / len(recent),
            "success_rate": sum(1 for e in recent if e["success"]) / len(recent),
            "active_plans": len(self.active_plans),
            "registered_agents": len(self.registry.agents)
        }
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "registry": self.registry.to_dict(),
            "stats": self.get_coordination_stats(),
            "active_plans": list(self.active_plans.keys())
        }


def create_coordinator() -> MultiAgentCoordinator:
    """Factory function to create a configured coordinator"""
    return MultiAgentCoordinator()


def quick_delegate(
    task: str,
    agents: List[Tuple[str, List[str]]],  # (agent_id, capabilities)
    execution_callback: Callable[[SubTask], AgentOutput]
) -> AggregationResult:
    """
    Quick delegation with minimal setup.
    
    Convenience function for rapid multi-agent coordination.
    """
    coordinator = create_coordinator()
    
    # Register agents
    for agent_id, capabilities in agents:
        coordinator.register_agent(
            agent_id=agent_id,
            role=AgentRole.WORKER,
            capabilities=capabilities
        )
    
    # Create and execute plan
    plan = coordinator.delegate_task(task)
    return coordinator.execute_plan(plan, execution_callback)
