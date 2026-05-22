"""
Multi-Agent Coordination System

Implements collaborative AI agent teams for complex task decomposition and execution.

Based on:
- Nature 2026: "Teams of AI agents boost speed of research" - multi-agent systems
  for hypothesis generation, experiment design, and analysis
- OpenAI Symphony: Agent orchestration without PR boundaries
- AggAgent (arXiv:2604.11753): Parallel scaling through agentic aggregation

Architecture:
- AgentPool: Manages team of specialized agents
- TaskRouter: Distributes subtasks based on agent capabilities
- ConsensusBuilder: Aggregates results from multiple agents
- SharedMemory: Enables inter-agent communication
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Tuple, Set
from enum import Enum
import asyncio
import json
import time
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


class AgentRole(Enum):
    """Predefined agent roles in multi-agent teams"""
    RESEARCHER = "researcher"           # Information gathering and analysis
    PLANNER = "planner"                 # Task decomposition and strategy
    EXECUTOR = "executor"               # Action execution and tool use
    CRITIC = "critic"                   # Review and quality assurance
    SYNTHESIZER = "synthesizer"       # Result aggregation and summary
    COORDINATOR = "coordinator"       # Team orchestration
    SPECIALIST = "specialist"         # Domain-specific expertise


class TaskStatus(Enum):
    """Status of delegated task"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class ConsensusStrategy(Enum):
    """Strategies for aggregating multi-agent results"""
    MAJORITY_VOTE = "majority_vote"
    WEIGHTED_CONFIDENCE = "weighted_confidence"
    EXPERT_HIERARCHY = "expert_hierarchy"
    DEBATE_RESOLUTION = "debate_resolution"
    UNANIMOUS = "unanimous"
    BEST_OF_N = "best_of_n"


@dataclass
class AgentCapability:
    """Description of what an agent can do"""
    capability_id: str
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    estimated_duration: float  # seconds
    success_rate: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "estimated_duration": self.estimated_duration,
            "success_rate": self.success_rate
        }


@dataclass
class SubTask:
    """A decomposed task for delegation"""
    task_id: str
    parent_task_id: Optional[str]
    description: str
    role: AgentRole
    required_capabilities: List[str]
    input_data: Dict[str, Any]
    dependencies: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    @property
    def duration(self) -> float:
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "parent_task_id": self.parent_task_id,
            "description": self.description,
            "role": self.role.value,
            "required_capabilities": self.required_capabilities,
            "dependencies": self.dependencies,
            "status": self.status.value,
            "assigned_agent": self.assigned_agent,
            "result": self.result,
            "confidence": self.confidence,
            "duration": self.duration
        }


@dataclass
class AgentProfile:
    """Profile of an agent in the multi-agent system"""
    agent_id: str
    name: str
    role: AgentRole
    capabilities: List[AgentCapability]
    agent_instance: Any  # Reference to actual agent object
    performance_history: List[Dict[str, Any]] = field(default_factory=list)
    current_load: int = 0
    max_concurrent: int = 3
    
    @property
    def avg_success_rate(self) -> float:
        if not self.performance_history:
            return 0.5
        recent = self.performance_history[-10:]
        return sum(p.get("success", 0) for p in recent) / len(recent)
    
    @property
    def avg_duration(self) -> float:
        if not self.performance_history:
            return 60.0
        recent = self.performance_history[-10:]
        return sum(p.get("duration", 60) for p in recent) / len(recent)
    
    def can_handle(self, capabilities: List[str]) -> bool:
        """Check if agent has all required capabilities"""
        agent_caps = {c.capability_id for c in self.capabilities}
        return all(cap in agent_caps for cap in capabilities)
    
    def is_available(self) -> bool:
        """Check if agent can accept more work"""
        return self.current_load < self.max_concurrent
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role.value,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "avg_success_rate": self.avg_success_rate,
            "avg_duration": self.avg_duration,
            "current_load": self.current_load,
            "max_concurrent": self.max_concurrent,
            "available": self.is_available()
        }


@dataclass
class ConsensusResult:
    """Result of multi-agent consensus building"""
    consensus_id: str
    strategy: ConsensusStrategy
    participating_agents: List[str]
    individual_results: List[Dict[str, Any]]
    aggregated_result: Dict[str, Any]
    confidence: float
    agreement_score: float  # How much agents agree
    dissenting_views: List[Dict[str, Any]]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "consensus_id": self.consensus_id,
            "strategy": self.strategy.value,
            "participating_agents": self.participating_agents,
            "individual_results_count": len(self.individual_results),
            "aggregated_result": self.aggregated_result,
            "confidence": self.confidence,
            "agreement_score": self.agreement_score,
            "dissenting_views": self.dissenting_views
        }


class AgentPool:
    """
    Manages a pool of specialized agents.
    
    Based on Nature 2026 multi-agent research teams concept where
    different agents specialize in different aspects of problem-solving.
    """
    
    def __init__(self):
        self.agents: Dict[str, AgentProfile] = {}
        self.agents_by_role: Dict[AgentRole, List[str]] = {role: [] for role in AgentRole}
        self.agents_by_capability: Dict[str, List[str]] = {}
        self.shared_memory: SharedMemory = SharedMemory()
    
    def register_agent(
        self,
        agent_id: str,
        name: str,
        role: AgentRole,
        capabilities: List[AgentCapability],
        agent_instance: Any,
        max_concurrent: int = 3
    ) -> AgentProfile:
        """Register a new agent in the pool"""
        profile = AgentProfile(
            agent_id=agent_id,
            name=name,
            role=role,
            capabilities=capabilities,
            agent_instance=agent_instance,
            max_concurrent=max_concurrent
        )
        
        self.agents[agent_id] = profile
        self.agents_by_role[role].append(agent_id)
        
        for cap in capabilities:
            if cap.capability_id not in self.agents_by_capability:
                self.agents_by_capability[cap.capability_id] = []
            self.agents_by_capability[cap.capability_id].append(agent_id)
        
        return profile
    
    def find_agents_for_task(
        self,
        role: Optional[AgentRole] = None,
        required_capabilities: List[str] = None,
        available_only: bool = True
    ) -> List[AgentProfile]:
        """Find agents matching task requirements"""
        candidates = []
        
        # Start with role-based filtering if specified
        if role:
            agent_ids = self.agents_by_role.get(role, [])
        else:
            agent_ids = list(self.agents.keys())
        
        # Filter by capabilities
        for agent_id in agent_ids:
            profile = self.agents.get(agent_id)
            if not profile:
                continue
            
            if available_only and not profile.is_available():
                continue
            
            if required_capabilities and not profile.can_handle(required_capabilities):
                continue
            
            candidates.append(profile)
        
        # Sort by success rate (highest first)
        candidates.sort(key=lambda p: p.avg_success_rate, reverse=True)
        return candidates
    
    def get_team_for_task(
        self,
        task_description: str,
        team_size: int = 3
    ) -> List[AgentProfile]:
        """
        Assemble a team of agents for a complex task.
        
        Uses heterogeneous team composition based on task needs:
        - Researcher: Information gathering
        - Planner: Strategy and decomposition
        - Executor: Implementation
        - Critic: Quality review
        """
        team = []
        
        # Determine required roles based on task description
        roles_needed = self._analyze_task_roles(task_description)
        
        # Select best agent for each role
        for role in roles_needed[:team_size]:
            candidates = self.find_agents_for_task(role=role)
            if candidates:
                team.append(candidates[0])
        
        return team
    
    def _analyze_task_roles(self, task: str) -> List[AgentRole]:
        """Analyze task to determine what roles are needed"""
        task_lower = task.lower()
        roles = []
        
        # Keywords indicating role needs
        if any(w in task_lower for w in ["research", "analyze", "investigate", "find", "search"]):
            roles.append(AgentRole.RESEARCHER)
        if any(w in task_lower for w in ["plan", "design", "strategy", "decompose", "structure"]):
            roles.append(AgentRole.PLANNER)
        if any(w in task_lower for w in ["build", "implement", "execute", "code", "create"]):
            roles.append(AgentRole.EXECUTOR)
        if any(w in task_lower for w in ["review", "critique", "verify", "check", "validate"]):
            roles.append(AgentRole.CRITIC)
        if any(w in task_lower for w in ["summarize", "synthesize", "compile", "integrate"]):
            roles.append(AgentRole.SYNTHESIZER)
        
        # Default to researcher + executor if no specific roles detected
        if not roles:
            roles = [AgentRole.RESEARCHER, AgentRole.EXECUTOR]
        
        # Always add coordinator for multi-agent tasks
        if len(roles) > 1:
            roles.insert(0, AgentRole.COORDINATOR)
        
        return roles
    
    def update_agent_performance(
        self,
        agent_id: str,
        task_id: str,
        success: bool,
        duration: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update agent's performance history"""
        if agent_id in self.agents:
            record = {
                "task_id": task_id,
                "success": 1 if success else 0,
                "duration": duration,
                "timestamp": datetime.now().timestamp(),
                "metadata": metadata or {}
            }
            self.agents[agent_id].performance_history.append(record)
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get statistics about the agent pool"""
        total_agents = len(self.agents)
        available = sum(1 for a in self.agents.values() if a.is_available())
        
        role_distribution = {
            role.value: len(ids) for role, ids in self.agents_by_role.items()
        }
        
        avg_success = sum(a.avg_success_rate for a in self.agents.values()) / max(total_agents, 1)
        
        return {
            "total_agents": total_agents,
            "available_agents": available,
            "busy_agents": total_agents - available,
            "role_distribution": role_distribution,
            "avg_pool_success_rate": avg_success,
            "total_capabilities": len(self.agents_by_capability)
        }


class TaskRouter:
    """
    Routes tasks to appropriate agents based on capabilities and load.
    
    Implements intelligent task distribution inspired by AggAgent's
    parallel scaling approach.
    """
    
    def __init__(self, agent_pool: AgentPool):
        self.pool = agent_pool
        self.pending_tasks: Dict[str, SubTask] = {}
        self.assigned_tasks: Dict[str, SubTask] = {}
        self.completed_tasks: Dict[str, SubTask] = {}
        
    def decompose_task(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[SubTask]:
        """
        Decompose a complex task into subtasks for different agents.
        
        Simplified decomposition - in production, use LLM-based planning.
        """
        subtasks = []
        context = context or {}
        
        # Simple heuristic decomposition
        # In practice, use a PLANNER agent for this
        task_lower = task_description.lower()
        
        # Phase 1: Research (if needed)
        if any(w in task_lower for w in ["research", "analyze", "find"]):
            task_id = self._generate_task_id()
            subtasks.append(SubTask(
                task_id=task_id,
                parent_task_id=None,
                description=f"Research: {task_description}",
                role=AgentRole.RESEARCHER,
                required_capabilities=["web_search", "data_analysis"],
                input_data={"query": task_description, **context}
            ))
        
        # Phase 2: Planning (always)
        research_task = subtasks[-1].task_id if subtasks else None
        task_id = self._generate_task_id()
        subtasks.append(SubTask(
            task_id=task_id,
            parent_task_id=None,
            description=f"Plan approach for: {task_description}",
            role=AgentRole.PLANNER,
            required_capabilities=["task_decomposition", "strategy"],
            input_data={"task": task_description, **context},
            dependencies=[research_task] if research_task else []
        ))
        
        # Phase 3: Execution
        plan_task = task_id
        task_id = self._generate_task_id()
        subtasks.append(SubTask(
            task_id=task_id,
            parent_task_id=None,
            description=f"Execute: {task_description}",
            role=AgentRole.EXECUTOR,
            required_capabilities=["code_generation", "tool_use"],
            input_data={"task": task_description, **context},
            dependencies=[plan_task]
        ))
        
        # Phase 4: Review
        exec_task = task_id
        task_id = self._generate_task_id()
        subtasks.append(SubTask(
            task_id=task_id,
            parent_task_id=None,
            description=f"Review results for: {task_description}",
            role=AgentRole.CRITIC,
            required_capabilities=["quality_review", "verification"],
            input_data={"task": task_description, **context},
            dependencies=[exec_task]
        ))
        
        return subtasks
    
    def assign_task(self, subtask: SubTask) -> Optional[str]:
        """Assign a subtask to the best available agent"""
        candidates = self.pool.find_agents_for_task(
            role=subtask.role,
            required_capabilities=subtask.required_capabilities
        )
        
        if not candidates:
            return None
        
        # Select best candidate (already sorted by success rate)
        best_agent = candidates[0]
        subtask.assigned_agent = best_agent.agent_id
        subtask.status = TaskStatus.ASSIGNED
        
        # Update agent load
        best_agent.current_load += 1
        
        self.pending_tasks[subtask.task_id] = subtask
        return best_agent.agent_id
    
    def execute_subtask(self, subtask: SubTask) -> Dict[str, Any]:
        """Execute a subtask using its assigned agent"""
        if not subtask.assigned_agent:
            return {"error": "No agent assigned", "success": False}
        
        agent_profile = self.pool.agents.get(subtask.assigned_agent)
        if not agent_profile:
            return {"error": "Agent not found", "success": False}
        
        subtask.status = TaskStatus.IN_PROGRESS
        subtask.started_at = time.time()
        
        try:
            # Execute via agent instance
            agent = agent_profile.agent_instance
            result = agent.run(
                goal=subtask.description,
                initial_context=subtask.input_data
            )
            
            subtask.result = {
                "output": result.output,
                "success": result.success,
                "execution_time": result.execution_time
            }
            subtask.status = TaskStatus.COMPLETED
            subtask.confidence = 0.9 if result.success else 0.3
            
        except Exception as e:
            subtask.result = {"error": str(e), "success": False}
            subtask.status = TaskStatus.FAILED
            subtask.confidence = 0.0
        
        finally:
            subtask.completed_at = time.time()
            agent_profile.current_load -= 1
            
            # Update performance
            self.pool.update_agent_performance(
                agent_id=subtask.assigned_agent,
                task_id=subtask.task_id,
                success=subtask.status == TaskStatus.COMPLETED,
                duration=subtask.duration
            )
        
        return subtask.result or {}
    
    def execute_parallel(
        self,
        subtasks: List[SubTask],
        max_workers: int = 3
    ) -> List[Dict[str, Any]]:
        """Execute multiple independent subtasks in parallel"""
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(self.execute_subtask, task): task
                for task in subtasks
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append({"error": str(e), "task_id": task.task_id, "success": False})
        
        return results
    
    def _generate_task_id(self) -> str:
        """Generate unique task ID"""
        return hashlib.md5(f"{time.time()}:{len(self.pending_tasks)}".encode()).hexdigest()[:12]


class ConsensusBuilder:
    """
    Builds consensus from multiple agent results.
    
    Implements strategies from AggAgent and multi-agent consensus research.
    """
    
    def __init__(self, strategy: ConsensusStrategy = ConsensusStrategy.WEIGHTED_CONFIDENCE):
        self.strategy = strategy
    
    def build_consensus(
        self,
        results: List[Dict[str, Any]],
        agent_ids: List[str],
        agent_profiles: Dict[str, AgentProfile]
    ) -> ConsensusResult:
        """Build consensus from multiple agent outputs"""
        
        consensus_id = hashlib.md5(
            f"{time.time()}:{len(results)}".encode()
        ).hexdigest()[:12]
        
        if self.strategy == ConsensusStrategy.WEIGHTED_CONFIDENCE:
            return self._weighted_confensus(results, agent_ids, agent_profiles, consensus_id)
        elif self.strategy == ConsensusStrategy.MAJORITY_VOTE:
            return self._majority_vote(results, agent_ids, consensus_id)
        elif self.strategy == ConsensusStrategy.BEST_OF_N:
            return self._best_of_n(results, agent_ids, consensus_id)
        else:
            # Default to weighted
            return self._weighted_confensus(results, agent_ids, agent_profiles, consensus_id)
    
    def _weighted_confensus(
        self,
        results: List[Dict[str, Any]],
        agent_ids: List[str],
        agent_profiles: Dict[str, AgentProfile],
        consensus_id: str
    ) -> ConsensusResult:
        """Weight results by agent success rate and confidence"""
        # Handle empty results
        if not results or not agent_ids:
            return ConsensusResult(
                consensus_id=consensus_id,
                strategy=self.strategy,
                participating_agents=[],
                individual_results=[],
                aggregated_result={},
                confidence=0.0,
                agreement_score=0.0,
                dissenting_views=[]
            )
        
        # Calculate weights based on agent history
        weights = []
        for agent_id in agent_ids:
            profile = agent_profiles.get(agent_id)
            if profile:
                weights.append(profile.avg_success_rate)
            else:
                weights.append(0.5)
        
        # Normalize weights
        total_weight = sum(weights)
        if total_weight > 0:
            weights = [w / total_weight for w in weights]
        else:
            weights = [1.0 / len(results)] * len(results)
        
        # Extract and aggregate outputs
        outputs = []
        for r in results:
            output = r.get("output", r) if isinstance(r, dict) else r
            outputs.append(output)
        
        # For text outputs, concatenate weighted
        # For structured outputs, average numerics, pick highest confidence categoricals
        aggregated = self._aggregate_outputs(outputs, weights)
        
        # Calculate agreement
        agreement = self._calculate_agreement(outputs)
        
        # Identify dissent
        dissenting = []
        avg_confidence = sum(weights) / len(weights)
        for i, (result, weight) in enumerate(zip(results, weights)):
            if weight < avg_confidence * 0.5:
                dissenting.append({
                    "agent_id": agent_ids[i],
                    "result": result,
                    "weight": weight
                })
        
        return ConsensusResult(
            consensus_id=consensus_id,
            strategy=self.strategy,
            participating_agents=agent_ids,
            individual_results=results,
            aggregated_result=aggregated,
            confidence=sum(weights) / len(weights),
            agreement_score=agreement,
            dissenting_views=dissenting
        )
    
    def _majority_vote(
        self,
        results: List[Dict[str, Any]],
        agent_ids: List[str],
        consensus_id: str
    ) -> ConsensusResult:
        """Simple majority vote for categorical outputs"""
        # Count occurrences
        outputs = [str(r.get("output", r)) for r in results]
        from collections import Counter
        vote_counts = Counter(outputs)
        
        # Find majority
        majority_output, majority_count = vote_counts.most_common(1)[0]
        agreement = majority_count / len(results)
        
        # Find dissenters
        dissenting = []
        for i, output in enumerate(outputs):
            if output != majority_output:
                dissenting.append({
                    "agent_id": agent_ids[i],
                    "result": results[i],
                    "vote": output
                })
        
        return ConsensusResult(
            consensus_id=consensus_id,
            strategy=ConsensusStrategy.MAJORITY_VOTE,
            participating_agents=agent_ids,
            individual_results=results,
            aggregated_result={"output": majority_output, "votes": dict(vote_counts)},
            confidence=agreement,
            agreement_score=agreement,
            dissenting_views=dissenting
        )
    
    def _best_of_n(
        self,
        results: List[Dict[str, Any]],
        agent_ids: List[str],
        consensus_id: str
    ) -> ConsensusResult:
        """Select the single best result based on confidence scores"""
        # Find result with highest confidence
        best_idx = 0
        best_confidence = 0.0
        
        for i, result in enumerate(results):
            conf = result.get("confidence", 0.5)
            if conf > best_confidence:
                best_confidence = conf
                best_idx = i
        
        best_result = results[best_idx]
        
        # All others are dissenting
        dissenting = [
            {"agent_id": agent_ids[i], "result": results[i]}
            for i in range(len(results)) if i != best_idx
        ]
        
        return ConsensusResult(
            consensus_id=consensus_id,
            strategy=ConsensusStrategy.BEST_OF_N,
            participating_agents=agent_ids,
            individual_results=results,
            aggregated_result=best_result,
            confidence=best_confidence,
            agreement_score=1.0 / len(results),  # Low agreement since we picked one
            dissenting_views=dissenting
        )
    
    def _aggregate_outputs(
        self,
        outputs: List[Any],
        weights: List[float]
    ) -> Dict[str, Any]:
        """Aggregate outputs based on their structure"""
        if not outputs:
            return {}
        
        # If all are dicts with same keys, aggregate numerics
        if all(isinstance(o, dict) for o in outputs):
            result = {}
            keys = set(outputs[0].keys())
            
            for key in keys:
                values = [o.get(key) for o in outputs if key in o]
                
                # Try numeric aggregation
                numeric_values = [v for v in values if isinstance(v, (int, float))]
                if numeric_values and len(numeric_values) == len(values):
                    weighted_sum = sum(v * w for v, w in zip(numeric_values, weights))
                    result[key] = weighted_sum
                else:
                    # Pick most common non-numeric
                    from collections import Counter
                    most_common = Counter(str(v) for v in values).most_common(1)[0][0]
                    result[key] = most_common
            
            return result
        
        # Default: return weighted concatenation
        return {"outputs": outputs, "weights": weights}
    
    def _calculate_agreement(self, outputs: List[Any]) -> float:
        """Calculate how much agents agree (0-1)"""
        if len(outputs) < 2:
            return 1.0
        
        # Simple: count identical outputs
        from collections import Counter
        output_strs = [str(o) for o in outputs]
        counts = Counter(output_strs)
        most_common_count = counts.most_common(1)[0][1]
        
        return most_common_count / len(outputs)


class SharedMemory:
    """
    Shared memory space for inter-agent communication.
    
    Enables agents to share context, results, and build collective understanding.
    """
    
    def __init__(self):
        self.messages: List[Dict[str, Any]] = []
        self.context: Dict[str, Any] = {}
        self.results: Dict[str, Dict[str, Any]] = {}
    
    def post_message(
        self,
        agent_id: str,
        message_type: str,
        content: Any,
        target_agents: Optional[List[str]] = None
    ) -> str:
        """Post a message to the shared memory"""
        msg_id = hashlib.md5(
            f"{agent_id}:{time.time()}".encode()
        ).hexdigest()[:12]
        
        message = {
            "msg_id": msg_id,
            "agent_id": agent_id,
            "type": message_type,
            "content": content,
            "target_agents": target_agents,
            "timestamp": datetime.now().timestamp()
        }
        
        self.messages.append(message)
        return msg_id
    
    def get_messages(
        self,
        for_agent: Optional[str] = None,
        message_type: Optional[str] = None,
        since: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve messages from shared memory"""
        messages = self.messages
        
        if for_agent:
            messages = [
                m for m in messages
                if m["agent_id"] == for_agent
                or (m.get("target_agents") and for_agent in m["target_agents"])
            ]
        
        if message_type:
            messages = [m for m in messages if m["type"] == message_type]
        
        if since:
            messages = [m for m in messages if m["timestamp"] > since]
        
        return messages
    
    def store_result(self, task_id: str, result: Dict[str, Any]) -> None:
        """Store a task result for access by other agents"""
        self.results[task_id] = {
            "result": result,
            "timestamp": datetime.now().timestamp()
        }
    
    def get_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a stored result"""
        return self.results.get(task_id)
    
    def set_context(self, key: str, value: Any) -> None:
        """Set shared context value"""
        self.context[key] = value
    
    def get_context(self, key: str) -> Any:
        """Get shared context value"""
        return self.context.get(key)


class MultiAgentOrchestrator:
    """
    Main orchestrator for multi-agent collaboration.
    
    Coordinates teams of agents to solve complex tasks through:
    1. Task decomposition
    2. Agent assignment
    3. Parallel execution
    4. Consensus building
    5. Result synthesis
    """
    
    def __init__(self):
        self.pool = AgentPool()
        self.router = TaskRouter(self.pool)
        self.consensus_builder = ConsensusBuilder()
        self.shared_memory = self.pool.shared_memory
    
    def execute(
        self,
        task: str,
        team_size: int = 3,
        require_consensus: bool = True
    ) -> Dict[str, Any]:
        """
        Execute a complex task using multi-agent collaboration.
        
        Workflow:
        1. Decompose task into subtasks
        2. Assign subtasks to specialized agents
        3. Execute in dependency order
        4. Build consensus on results (if multiple agents per subtask)
        5. Synthesize final output
        """
        start_time = time.time()
        
        # Step 1: Decompose task
        subtasks = self.router.decompose_task(task)
        
        # Step 2: Assign agents
        for subtask in subtasks:
            self.router.assign_task(subtask)
        
        # Step 3: Execute with dependency handling
        results = self._execute_with_dependencies(subtasks)
        
        # Step 4: Build consensus if multiple parallel executions
        consensus = None
        if require_consensus and len(subtasks) > 1:
            agent_ids = [s.assigned_agent for s in subtasks if s.assigned_agent]
            consensus = self.consensus_builder.build_consensus(
                results=[s.result for s in subtasks if s.result],
                agent_ids=agent_ids,
                agent_profiles=self.pool.agents
            )
        
        # Step 5: Synthesize final output
        execution_time = time.time() - start_time
        
        return {
            "task": task,
            "success": all(s.status == TaskStatus.COMPLETED for s in subtasks),
            "subtasks": [s.to_dict() for s in subtasks],
            "consensus": consensus.to_dict() if consensus else None,
            "execution_time": execution_time,
            "team_size": team_size,
            "shared_memory_messages": len(self.shared_memory.messages)
        }
    
    def _execute_with_dependencies(self, subtasks: List[SubTask]) -> List[Dict[str, Any]]:
        """Execute subtasks respecting dependencies"""
        completed: Set[str] = set()
        results = []
        
        # Group by dependency level
        levels = self._topological_sort(subtasks)
        
        for level in levels:
            # Execute this level in parallel
            level_tasks = [t for t in subtasks if t.task_id in level]
            level_results = self.router.execute_parallel(level_tasks)
            results.extend(level_results)
            completed.update(level)
        
        return results
    
    def _topological_sort(self, subtasks: List[SubTask]) -> List[Set[str]]:
        """Sort subtasks by dependency levels for parallel execution"""
        task_map = {s.task_id: s for s in subtasks}
        
        levels = []
        remaining = set(s.task_id for s in subtasks)
        completed = set()
        
        while remaining:
            # Find tasks with no uncompleted dependencies
            ready = {
                tid for tid in remaining
                if all(dep in completed for dep in task_map[tid].dependencies)
            }
            
            if not ready:
                # Cycle detected - force execution
                ready = remaining
            
            levels.append(ready)
            completed.update(ready)
            remaining -= ready
        
        return levels
    
    def register_agent(
        self,
        agent_id: str,
        name: str,
        role: AgentRole,
        capabilities: List[AgentCapability],
        agent_instance: Any,
        max_concurrent: int = 3
    ) -> AgentProfile:
        """Register an agent with the orchestrator"""
        return self.pool.register_agent(
            agent_id=agent_id,
            name=name,
            role=role,
            capabilities=capabilities,
            agent_instance=agent_instance,
            max_concurrent=max_concurrent
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive orchestrator statistics"""
        return {
            "pool_stats": self.pool.get_pool_stats(),
            "pending_tasks": len(self.router.pending_tasks),
            "completed_tasks": len(self.router.completed_tasks),
            "shared_memory_messages": len(self.shared_memory.messages),
            "stored_results": len(self.shared_memory.results)
        }


def create_orchestrator() -> MultiAgentOrchestrator:
    """Factory function to create a configured orchestrator"""
    return MultiAgentOrchestrator()


def quick_collaborate(
    task: str,
    agents: List[Any],  # Agent instances
    agent_roles: Optional[List[AgentRole]] = None
) -> Dict[str, Any]:
    """
    Quick multi-agent collaboration without full setup.
    
    Convenience function for rapid team assembly.
    """
    orchestrator = create_orchestrator()
    
    # Auto-assign roles if not provided
    default_roles = [
        AgentRole.RESEARCHER,
        AgentRole.PLANNER,
        AgentRole.EXECUTOR,
        AgentRole.CRITIC,
        AgentRole.SYNTHESIZER
    ]
    roles = agent_roles or default_roles[:len(agents)]
    
    # Register agents
    for i, (agent, role) in enumerate(zip(agents, roles)):
        orchestrator.register_agent(
            agent_id=f"agent_{i}",
            name=f"Agent {i+1}",
            role=role,
            capabilities=[AgentCapability(
                capability_id="general",
                name="General Execution",
                description="Execute general tasks",
                input_schema={},
                output_schema={},
                estimated_duration=60.0
            )],
            agent_instance=agent,
            max_concurrent=2
        )
    
    return orchestrator.execute(task, team_size=len(agents))
