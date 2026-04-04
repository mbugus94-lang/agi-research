"""
Multi-Agent Orchestrator based on Google/MIT research findings.

Paper: "Towards a Science of Scaling Agent Systems" (2026)
Key insights:
- Centralized orchestration improves parallel tasks by +81%
- Centralized limits error amplification to 4.4x (vs 17x for independent)
- Sequential tasks perform 39-70% worse with multi-agent
- Cost is 2-6x higher than single-agent

Architecture patterns implemented:
1. Orchestrator-Worker: Central coordinator with specialist agents
2. Hierarchical: Multi-level agent management
3. Topology-aware: Switches strategy based on task characteristics
"""

from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from enum import Enum, auto
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor


class TaskType(Enum):
    """Classification of task characteristics."""
    PARALLEL = auto()      # Independent sub-tasks that can run concurrently
    SEQUENTIAL = auto()    # Each step depends on previous
    HYBRID = auto()        # Mix of parallel and sequential components
    SINGLE = auto()        # Best handled by single agent


class OrchestrationTopology(Enum):
    """Coordination patterns from research."""
    CENTRALIZED = auto()   # Orchestrator validates all outputs (accuracy-focused)
    DECENTRALIZED = auto() # Peer-to-peer communication (throughput-focused)
    HYBRID = auto()        # Mix based on sub-task requirements


class AgentRole(Enum):
    """Specialist agent roles."""
    RESEARCHER = "researcher"
    ANALYZER = "analyzer"
    EXECUTOR = "executor"
    VALIDATOR = "validator"
    SYNTHESIZER = "synthesizer"


@dataclass
class SubTask:
    """A unit of work assigned to an agent."""
    id: str
    description: str
    role: AgentRole
    input_data: Any = None
    expected_output_type: str = "text"
    dependencies: List[str] = field(default_factory=list)
    max_retries: int = 2
    timeout_seconds: float = 30.0


@dataclass
class TaskResult:
    """Result from an agent execution."""
    subtask_id: str
    success: bool
    output: Any
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0
    agent_name: str = ""
    retry_count: int = 0


@dataclass
class OrchestrationConfig:
    """Configuration for orchestrator behavior."""
    topology: OrchestrationTopology = OrchestrationTopology.CENTRALIZED
    max_parallel_agents: int = 5
    error_threshold: float = 0.3  # Max error rate before fallback
    enable_validation: bool = True
    validation_strictness: str = "medium"  # low, medium, high
    cost_budget: Optional[float] = None  # Max cost in USD


class SpecialistAgent:
    """
    A specialist agent with a specific role.
    
    In production, this would wrap an LLM with role-specific prompting.
    For now, implements the interface with simulated behavior.
    """
    
    def __init__(
        self,
        name: str,
        role: AgentRole,
        execute_func: Callable[[SubTask], TaskResult],
        capabilities: List[str] = None
    ):
        self.name = name
        self.role = role
        self.execute_func = execute_func
        self.capabilities = capabilities or []
        self.execution_count = 0
        self.error_count = 0
    
    def execute(self, subtask: SubTask) -> TaskResult:
        """Execute a subtask with retry logic."""
        start_time = time.time()
        retry_count = 0
        
        while retry_count <= subtask.max_retries:
            try:
                result = self.execute_func(subtask)
                result.execution_time_ms = (time.time() - start_time) * 1000
                result.agent_name = self.name
                result.retry_count = retry_count
                
                self.execution_count += 1
                if not result.success:
                    self.error_count += 1
                
                return result
                
            except Exception as e:
                retry_count += 1
                if retry_count > subtask.max_retries:
                    return TaskResult(
                        subtask_id=subtask.id,
                        success=False,
                        output=None,
                        error_message=str(e),
                        execution_time_ms=(time.time() - start_time) * 1000,
                        agent_name=self.name,
                        retry_count=retry_count
                    )
                time.sleep(0.1 * retry_count)  # Exponential backoff
    
    @property
    def error_rate(self) -> float:
        """Calculate current error rate."""
        if self.execution_count == 0:
            return 0.0
        return self.error_count / self.execution_count


class OrchestratorAgent:
    """
    Central orchestrator coordinating multiple specialist agents.
    
    Implements findings from Google/MIT research:
    - Centralized validation to limit error amplification
    - Task decomposition based on parallel vs sequential characteristics
    - Dynamic topology selection based on task type
    """
    
    def __init__(self, config: OrchestrationConfig = None):
        self.config = config or OrchestrationConfig()
        self.agents: Dict[AgentRole, List[SpecialistAgent]] = {
            role: [] for role in AgentRole
        }
        self.results: Dict[str, TaskResult] = {}
        self.execution_log: List[Dict] = []
    
    def register_agent(self, agent: SpecialistAgent):
        """Register a specialist agent."""
        self.agents[agent.role].append(agent)
    
    def classify_task(self, task_description: str) -> TaskType:
        """
        Classify task as parallel, sequential, or single-agent optimal.
        
        Based on research: tasks with >5-7 sequential tool interactions
        favor single agent; parallelizable tasks favor multi-agent.
        """
        task_lower = task_description.lower()
        
        # Sequential indicators (each step depends on previous)
        sequential_keywords = [
            "step by step", "sequentially", "in order", "first then",
            "plan", "strategize", "compile", "build", "implement"
        ]
        
        # Parallel indicators (independent sub-tasks)
        parallel_keywords = [
            "analyze multiple", "compare", "research", "gather from",
            "aggregate", "synthesize", "multiple sources", "various aspects"
        ]
        
        sequential_score = sum(1 for kw in sequential_keywords if kw in task_lower)
        parallel_score = sum(1 for kw in parallel_keywords if kw in task_lower)
        
        if sequential_score > parallel_score:
            return TaskType.SEQUENTIAL
        elif parallel_score > sequential_score:
            return TaskType.PARALLEL
        else:
            return TaskType.HYBRID
    
    def decompose_task(self, task_description: str, task_type: TaskType) -> List[SubTask]:
        """
        Decompose task into subtasks based on classification.
        
        Research finding: Decomposition is key to multi-agent gains.
        Poor decomposition can cause 39-70% performance degradation.
        """
        subtasks = []
        
        if task_type == TaskType.PARALLEL:
            # Create parallel research/analysis subtasks
            subtasks = [
                SubTask(
                    id="research_1",
                    description=f"Research aspect A of: {task_description}",
                    role=AgentRole.RESEARCHER,
                    expected_output_type="text"
                ),
                SubTask(
                    id="research_2",
                    description=f"Research aspect B of: {task_description}",
                    role=AgentRole.RESEARCHER,
                    expected_output_type="text"
                ),
                SubTask(
                    id="analyze",
                    description="Analyze findings and identify patterns",
                    role=AgentRole.ANALYZER,
                    dependencies=["research_1", "research_2"],
                    expected_output_type="analysis"
                ),
                SubTask(
                    id="synthesize",
                    description="Synthesize final answer from analysis",
                    role=AgentRole.SYNTHESIZER,
                    dependencies=["analyze"],
                    expected_output_type="text"
                )
            ]
        
        elif task_type == TaskType.SEQUENTIAL:
            # Sequential execution with validation checkpoints
            subtasks = [
                SubTask(
                    id="plan",
                    description=f"Create execution plan for: {task_description}",
                    role=AgentRole.ANALYZER,
                    expected_output_type="plan"
                ),
                SubTask(
                    id="execute",
                    description="Execute the planned steps",
                    role=AgentRole.EXECUTOR,
                    dependencies=["plan"],
                    expected_output_type="result"
                ),
                SubTask(
                    id="validate",
                    description="Validate execution results",
                    role=AgentRole.VALIDATOR,
                    dependencies=["execute"],
                    expected_output_type="validation"
                )
            ]
        
        else:  # HYBRID or default
            subtasks = [
                SubTask(
                    id="analyze",
                    description=f"Analyze requirements for: {task_description}",
                    role=AgentRole.ANALYZER,
                    expected_output_type="requirements"
                ),
                SubTask(
                    id="execute",
                    description="Execute based on analysis",
                    role=AgentRole.EXECUTOR,
                    dependencies=["analyze"],
                    expected_output_type="result"
                )
            ]
        
        return subtasks
    
    def execute_parallel(self, subtasks: List[SubTask]) -> Dict[str, TaskResult]:
        """
        Execute independent subtasks in parallel.
        
        Research shows +81% improvement on parallelizable tasks.
        """
        results = {}
        ready_tasks = [st for st in subtasks if not st.dependencies]
        pending_tasks = [st for st in subtasks if st.dependencies]
        
        with ThreadPoolExecutor(max_workers=self.config.max_parallel_agents) as executor:
            # Execute ready tasks in parallel
            futures = {}
            for subtask in ready_tasks:
                agents = self.agents.get(subtask.role, [])
                if agents:
                    # Select agent with lowest error rate
                    agent = min(agents, key=lambda a: a.error_rate)
                    futures[executor.submit(agent.execute, subtask)] = subtask
            
            # Collect results
            for future in futures:
                subtask = futures[future]
                try:
                    result = future.result(timeout=30)
                    results[subtask.id] = result
                    
                    # Log execution
                    self.execution_log.append({
                        "subtask_id": subtask.id,
                        "agent": result.agent_name,
                        "success": result.success,
                        "duration_ms": result.execution_time_ms
                    })
                    
                except Exception as e:
                    results[subtask.id] = TaskResult(
                        subtask_id=subtask.id,
                        success=False,
                        output=None,
                        error_message=str(e)
                    )
            
            # Execute dependent tasks
            for subtask in pending_tasks:
                deps_satisfied = all(
                    dep_id in results and results[dep_id].success
                    for dep_id in subtask.dependencies
                )
                
                if deps_satisfied:
                    agents = self.agents.get(subtask.role, [])
                    if agents:
                        agent = min(agents, key=lambda a: a.error_rate)
                        result = agent.execute(subtask)
                        results[subtask.id] = result
                else:
                    results[subtask.id] = TaskResult(
                        subtask_id=subtask.id,
                        success=False,
                        output=None,
                        error_message="Dependencies not satisfied"
                    )
        
        return results
    
    def execute_centralized(self, subtasks: List[SubTask]) -> Dict[str, TaskResult]:
        """
        Execute with centralized validation (accuracy-focused).
        
        Research: Limits error amplification to 4.4x vs 17x for independent.
        """
        results = {}
        executed = set()
        
        def can_execute(subtask: SubTask) -> bool:
            return all(dep_id in executed for dep_id in subtask.dependencies)
        
        pending = subtasks.copy()
        
        while pending:
            # Find next executable task
            ready = [st for st in pending if can_execute(st)]
            
            if not ready:
                # Deadlock or missing dependencies
                break
            
            for subtask in ready:
                agents = self.agents.get(subtask.role, [])
                
                if not agents:
                    results[subtask.id] = TaskResult(
                        subtask_id=subtask.id,
                        success=False,
                        output=None,
                        error_message=f"No agent available for role {subtask.role}"
                    )
                    continue
                
                # Select best agent
                agent = min(agents, key=lambda a: a.error_rate)
                result = agent.execute(subtask)
                
                # Centralized validation
                if self.config.enable_validation and result.success:
                    validation = self._validate_result(subtask, result)
                    if not validation:
                        result.success = False
                        result.error_message = "Failed validation"
                
                results[subtask.id] = result
                executed.add(subtask.id)
                pending.remove(subtask)
                
                # Check error rate
                error_rate = sum(1 for r in results.values() if not r.success) / len(results)
                if error_rate > self.config.error_threshold:
                    print(f"⚠️ Error rate {error_rate:.2%} exceeds threshold, considering fallback")
        
        return results
    
    def _validate_result(self, subtask: SubTask, result: TaskResult) -> bool:
        """Validate an agent's output."""
        # Simple validation - in production, use LLM or rule-based checks
        if result.output is None:
            return False
        if isinstance(result.output, str) and len(result.output) < 10:
            return False
        return True
    
    def execute(self, task_description: str) -> Dict[str, Any]:
        """
        Execute a task using appropriate orchestration strategy.
        
        Main entry point that implements research findings:
        1. Classify task type
        2. Decompose appropriately
        3. Select topology based on task characteristics
        4. Execute with error control
        """
        print(f"\n{'='*60}")
        print(f"🎯 Orchestrator: {task_description}")
        print(f"{'='*60}\n")
        
        # Step 1: Classify task
        task_type = self.classify_task(task_description)
        print(f"📊 Task classified as: {task_type.name}")
        
        # Step 2: Decompose
        subtasks = self.decompose_task(task_description, task_type)
        print(f"📋 Decomposed into {len(subtasks)} subtasks")
        for st in subtasks:
            deps = f" (depends on: {st.dependencies})" if st.dependencies else ""
            print(f"   - [{st.role.value}] {st.id}: {st.description[:50]}...{deps}")
        
        # Step 3: Select topology based on task type
        if task_type == TaskType.SEQUENTIAL:
            # Sequential tasks favor centralized validation
            self.config.topology = OrchestrationTopology.CENTRALIZED
        elif task_type == TaskType.PARALLEL:
            # Parallel tasks can use hybrid for efficiency
            self.config.topology = OrchestrationTopology.HYBRID
        
        print(f"🔧 Using topology: {self.config.topology.name}")
        
        # Step 4: Execute
        start_time = time.time()
        
        if self.config.topology == OrchestrationTopology.CENTRALIZED:
            results = self.execute_centralized(subtasks)
        else:
            results = self.execute_parallel(subtasks)
        
        execution_time = time.time() - start_time
        
        # Step 5: Synthesize final answer
        final_result = self._synthesize_results(task_description, results)
        
        # Calculate metrics
        success_count = sum(1 for r in results.values() if r.success)
        error_rate = 1 - (success_count / len(results)) if results else 0
        
        print(f"\n📊 Execution Summary:")
        print(f"   - Subtasks: {len(subtasks)}")
        print(f"   - Successful: {success_count}/{len(results)}")
        print(f"   - Error rate: {error_rate:.1%}")
        print(f"   - Total time: {execution_time:.2f}s")
        
        return {
            "task": task_description,
            "task_type": task_type.name,
            "topology": self.config.topology.name,
            "success": error_rate < self.config.error_threshold,
            "error_rate": error_rate,
            "execution_time_s": execution_time,
            "final_answer": final_result,
            "subtask_results": {
                k: {
                    "success": v.success,
                    "agent": v.agent_name,
                    "duration_ms": v.execution_time_ms
                }
                for k, v in results.items()
            }
        }
    
    def _synthesize_results(self, task_description: str, results: Dict[str, TaskResult]) -> str:
        """Synthesize final answer from subtask results."""
        successful_results = [r for r in results.values() if r.success]
        
        if not successful_results:
            return "Task failed: No subtasks completed successfully"
        
        # Simple synthesis - in production, use synthesizer agent
        synthesis = f"Task: {task_description}\n\n"
        synthesis += "Results:\n"
        for result in successful_results:
            output = result.output if isinstance(result.output, str) else str(result.output)
            synthesis += f"- [{result.agent_name}] {output[:100]}...\n"
        
        return synthesis
    
    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        agent_stats = {}
        for role, agents in self.agents.items():
            agent_stats[role.value] = {
                "count": len(agents),
                "total_executions": sum(a.execution_count for a in agents),
                "total_errors": sum(a.error_count for a in agents),
                "avg_error_rate": sum(a.error_rate for a in agents) / len(agents) if agents else 0
            }
        
        return {
            "agents": agent_stats,
            "execution_log_count": len(self.execution_log),
            "config": {
                "topology": self.config.topology.name,
                "max_parallel": self.config.max_parallel_agents,
                "error_threshold": self.config.error_threshold
            }
        }


# Example specialist agent implementations for testing

def create_mock_agent(name: str, role: AgentRole, success_rate: float = 0.9) -> SpecialistAgent:
    """Create a mock specialist agent for testing."""
    
    def execute(subtask: SubTask) -> TaskResult:
        import random
        success = random.random() < success_rate
        
        if success:
            return TaskResult(
                subtask_id=subtask.id,
                success=True,
                output=f"[{role.value}] Completed: {subtask.description}"
            )
        else:
            return TaskResult(
                subtask_id=subtask.id,
                success=False,
                output=None,
                error_message="Simulated failure"
            )
    
    return SpecialistAgent(name=name, role=role, execute_func=execute)


if __name__ == "__main__":
    # Demo: Multi-agent orchestration
    print("="*60)
    print("Multi-Agent Orchestrator Demo")
    print("Based on Google/MIT Research (2026)")
    print("="*60)
    
    # Create orchestrator with centralized topology (for accuracy)
    config = OrchestrationConfig(
        topology=OrchestrationTopology.CENTRALIZED,
        max_parallel_agents=3,
        enable_validation=True
    )
    orchestrator = OrchestratorAgent(config)
    
    # Register specialist agents
    orchestrator.register_agent(create_mock_agent("Researcher-1", AgentRole.RESEARCHER, 0.95))
    orchestrator.register_agent(create_mock_agent("Researcher-2", AgentRole.RESEARCHER, 0.90))
    orchestrator.register_agent(create_mock_agent("Analyzer-1", AgentRole.ANALYZER, 0.92))
    orchestrator.register_agent(create_mock_agent("Executor-1", AgentRole.EXECUTOR, 0.88))
    orchestrator.register_agent(create_mock_agent("Validator-1", AgentRole.VALIDATOR, 0.95))
    orchestrator.register_agent(create_mock_agent("Synthesizer-1", AgentRole.SYNTHESIZER, 0.93))
    
    # Test parallel task
    print("\n" + "="*60)
    print("TEST 1: Parallel Task (Research + Analysis)")
    print("="*60)
    result1 = orchestrator.execute(
        "Research and analyze the impact of AI on healthcare from multiple sources"
    )
    print(f"\n✅ Success: {result1['success']}")
    print(f"📈 Error rate: {result1['error_rate']:.1%}")
    
    # Test sequential task
    print("\n" + "="*60)
    print("TEST 2: Sequential Task (Plan + Execute)")
    print("="*60)
    result2 = orchestrator.execute(
        "Plan and implement a Python function to calculate fibonacci numbers"
    )
    print(f"\n✅ Success: {result2['success']}")
    print(f"📈 Error rate: {result2['error_rate']:.1%}")
    
    # Print stats
    print("\n" + "="*60)
    print("Orchestrator Statistics")
    print("="*60)
    import json
    print(json.dumps(orchestrator.get_stats(), indent=2))
