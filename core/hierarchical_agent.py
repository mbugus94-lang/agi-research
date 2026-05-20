"""
Hierarchical Self-Evolving Agent Framework

Implementation based on arXiv:2601.11658v1 "Towards AGI: A Pragmatic Approach 
Towards Self Evolving Agent"

Architecture:
- BaseReasoner: High-level reasoning and planning
- OperationalExecutor: Task execution with existing tools  
- ToolSynthesizer: Code generation for missing tools
- TeacherSupervisor: Guidance, evaluation, and curriculum design
- EvolutionEngine: CL, RL, GA-based improvement

Evolution Mechanisms:
- Curriculum Learning (CL): Fast recovery and strong generalization
- Reward-Based Learning (RL): Excels on high-difficulty tasks
- Genetic Algorithm (GA): Promotes high behavioral diversity
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Tuple, Set
from enum import Enum, auto
import json
import hashlib
import random
from datetime import datetime
from collections import defaultdict


class TaskDifficulty(Enum):
    """Task difficulty levels for curriculum learning"""
    EASY = auto()
    MEDIUM = auto()
    HARD = auto()
    EXPERT = auto()


class EvolutionStrategy(Enum):
    """Evolution strategies as per the paper"""
    CURRICULUM_LEARNING = "cl"  # Fast recovery, strong generalization
    REWARD_BASED_LEARNING = "rl"  # High-difficulty task excellence
    GENETIC_ALGORITHM = "ga"  # High behavioral diversity


@dataclass
class Tool:
    """Represents a tool that can be used or synthesized"""
    tool_id: str
    name: str
    description: str
    code: str  # Python code implementing the tool
    signature: str  # Function signature
    dependencies: List[str] = field(default_factory=list)
    usage_count: int = 0
    success_rate: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
    evolved_from: Optional[str] = None  # Parent tool ID if evolved


@dataclass
class Task:
    """Hierarchical task representation"""
    task_id: str
    description: str
    subtasks: List['Task'] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    difficulty: TaskDifficulty = TaskDifficulty.EASY
    domain: str = "general"
    expected_output: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_primitive(self) -> bool:
        """Check if this is a leaf-level primitive task"""
        return len(self.subtasks) == 0
    
    def get_all_tools(self) -> Set[str]:
        """Get all tools required for this task and subtasks"""
        tools = set(self.required_tools)
        for subtask in self.subtasks:
            tools.update(subtask.get_all_tools())
        return tools


@dataclass
class ExecutionTrace:
    """Record of task execution"""
    trace_id: str
    task_id: str
    steps: List[Dict[str, Any]] = field(default_factory=list)
    success: bool = False
    execution_time: float = 0.0
    tools_used: List[str] = field(default_factory=list)
    tools_synthesized: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class EvolutionCandidate:
    """Candidate for evolution via GA"""
    candidate_id: str
    tools: List[Tool]
    fitness_score: float = 0.0
    generation: int = 0
    parent_ids: List[str] = field(default_factory=list)
    mutations: List[str] = field(default_factory=list)


class BaseReasoner:
    """
    High-level reasoning and planning component.
    
    Responsible for:
    - Task decomposition
    - Strategy selection
    - Goal analysis
    """
    
    def __init__(self):
        self.reasoning_history: List[Dict[str, Any]] = []
        
    def decompose_task(self, task: Task, available_tools: Set[str]) -> Task:
        """
        Decompose a complex task into hierarchical subtasks.
        
        Returns a task tree with subtasks that can be executed
        with available tools or need synthesis.
        """
        if task.is_primitive():
            # Check if we have the required tool
            missing_tools = set(task.required_tools) - available_tools
            if missing_tools:
                # Mark for tool synthesis
                task.metadata['needs_synthesis'] = list(missing_tools)
            return task
        
        # Decompose further
        decomposed_subtasks = []
        for subtask in task.subtasks:
            decomposed = self.decompose_task(subtask, available_tools)
            decomposed_subtasks.append(decomposed)
        
        task.subtasks = decomposed_subtasks
        
        # Record reasoning
        self.reasoning_history.append({
            'task_id': task.task_id,
            'action': 'decompose',
            'subtask_count': len(decomposed_subtasks),
            'missing_tools': list(task.get_all_tools() - available_tools)
        })
        
        return task
    
    def select_strategy(self, task: Task, execution_history: List[ExecutionTrace]) -> EvolutionStrategy:
        """
        Select appropriate evolution strategy based on task characteristics.
        
        - CL: For tasks needing fast recovery and generalization
        - RL: For high-difficulty tasks with clear reward signals
        - GA: For tasks needing behavioral diversity exploration
        """
        # Analyze task characteristics
        if task.difficulty == TaskDifficulty.HARD or task.difficulty == TaskDifficulty.EXPERT:
            # High difficulty tasks benefit from RL
            if any(trace.success for trace in execution_history[-5:] if trace.task_id == task.task_id):
                return EvolutionStrategy.REWARD_BASED_LEARNING
        
        # Check if we need behavioral diversity
        recent_tools = set()
        for trace in execution_history[-10:]:
            recent_tools.update(trace.tools_used)
        
        if len(recent_tools) < 3:  # Low diversity
            return EvolutionStrategy.GENETIC_ALGORITHM
        
        # Default to curriculum learning for general improvement
        return EvolutionStrategy.CURRICULUM_LEARNING
    
    def analyze_goal(self, goal: str) -> Dict[str, Any]:
        """Analyze a high-level goal and extract key components"""
        # Simple keyword-based analysis
        analysis = {
            'goal': goal,
            'domain_keywords': [],
            'likely_tools_needed': [],
            'estimated_complexity': 'unknown'
        }
        
        # Extract domain hints
        domains = {
            'code': ['code', 'program', 'function', 'algorithm', 'implement'],
            'data': ['data', 'analyze', 'process', 'transform', 'aggregate'],
            'web': ['search', 'web', 'url', 'http', 'scrape', 'fetch'],
            'math': ['calculate', 'compute', 'math', 'equation', 'solve'],
            'text': ['text', 'string', 'parse', 'format', 'convert']
        }
        
        goal_lower = goal.lower()
        for domain, keywords in domains.items():
            if any(kw in goal_lower for kw in keywords):
                analysis['domain_keywords'].append(domain)
        
        return analysis


class OperationalExecutor:
    """
    Task execution component using available tools.
    
    Similar to SLM (Small Language Model) agent in the paper.
    """
    
    def __init__(self, tool_registry: Dict[str, Tool] = None):
        self.tool_registry = tool_registry or {}
        self.execution_log: List[Dict[str, Any]] = []
        
    def register_tool(self, tool: Tool):
        """Register a tool for execution"""
        self.tool_registry[tool.tool_id] = tool
        
    def execute_task(self, task: Task, context: Dict[str, Any] = None) -> ExecutionTrace:
        """
        Execute a primitive task using available tools.
        
        Returns execution trace with success/failure and metadata.
        """
        trace = ExecutionTrace(
            trace_id=self._generate_id(),
            task_id=task.task_id
        )
        
        context = context or {}
        start_time = datetime.now()
        
        try:
            # Execute each required tool in sequence
            for tool_id in task.required_tools:
                if tool_id not in self.tool_registry:
                    raise ValueError(f"Tool {tool_id} not available")
                
                tool = self.tool_registry[tool_id]
                
                # Simulate tool execution (in real implementation, would exec code)
                step_result = self._execute_tool(tool, task, context)
                
                trace.steps.append({
                    'tool': tool_id,
                    'success': step_result['success'],
                    'output': step_result.get('output'),
                    'error': step_result.get('error')
                })
                trace.tools_used.append(tool_id)
                
                if not step_result['success']:
                    trace.success = False
                    trace.error_message = step_result.get('error', 'Unknown error')
                    break
            
            if not trace.error_message:
                trace.success = True
                
        except Exception as e:
            trace.success = False
            trace.error_message = str(e)
        
        trace.execution_time = (datetime.now() - start_time).total_seconds()
        
        # Update tool usage stats
        for tool_id in trace.tools_used:
            if tool_id in self.tool_registry:
                self.tool_registry[tool_id].usage_count += 1
                # Update success rate
                tool = self.tool_registry[tool_id]
                total = tool.usage_count
                success_count = sum(1 for t in self.execution_log 
                                  if tool_id in t.get('tools_used', []) 
                                  and t.get('success', False))
                tool.success_rate = success_count / total if total > 0 else 0
        
        self.execution_log.append({
            'trace_id': trace.trace_id,
            'task_id': task.task_id,
            'success': trace.success,
            'tools_used': trace.tools_used
        })
        
        return trace
    
    def _execute_tool(self, tool: Tool, task: Task, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single tool - simulated for now"""
        # In real implementation, this would safely execute tool.code
        return {
            'success': True,
            'output': f"Executed {tool.name} on {task.task_id}"
        }
    
    def _generate_id(self) -> str:
        """Generate unique execution trace ID"""
        return hashlib.md5(
            f"{datetime.now().isoformat()}{random.random()}".encode()
        ).hexdigest()[:12]


class ToolSynthesizer:
    """
    Code generation component for synthesizing new tools when existing ones fail.
    
    Similar to Code-Generation LLM in the paper.
    """
    
    def __init__(self):
        self.synthesis_history: List[Dict[str, Any]] = []
        self.synthesized_tools: Dict[str, Tool] = {}
        
    def synthesize_tool(
        self, 
        task_description: str, 
        required_capability: str,
        failed_attempts: List[ExecutionTrace] = None
    ) -> Tool:
        """
        Synthesize a new tool based on task requirements.
        
        In a real implementation, this would use an LLM to generate code.
        """
        tool_id = f"tool_{self._generate_id()}"
        
        # Generate tool code based on capability description
        code = self._generate_tool_code(required_capability, failed_attempts)
        
        tool = Tool(
            tool_id=tool_id,
            name=f"synthesized_{required_capability[:20]}",
            description=f"Auto-generated tool for: {task_description[:100]}",
            code=code,
            signature=f"def {required_capability.replace(' ', '_')}(input_data):",
            dependencies=self._infer_dependencies(required_capability)
        )
        
        self.synthesized_tools[tool_id] = tool
        
        self.synthesis_history.append({
            'tool_id': tool_id,
            'task_description': task_description,
            'capability': required_capability,
            'timestamp': datetime.now()
        })
        
        return tool
    
    def evolve_tool(self, tool: Tool, feedback: List[ExecutionTrace]) -> Tool:
        """
        Evolve an existing tool based on execution feedback.
        
        Creates a new version with improvements based on failure patterns.
        """
        # Analyze failures
        failure_patterns = self._analyze_failures(feedback, tool.tool_id)
        
        # Generate improved code
        improved_code = self._improve_tool_code(tool.code, failure_patterns)
        
        evolved_tool = Tool(
            tool_id=f"{tool.tool_id}_v{self._get_next_version(tool.tool_id)}",
            name=f"{tool.name}_evolved",
            description=f"Evolved from {tool.tool_id}: {tool.description}",
            code=improved_code,
            signature=tool.signature,
            dependencies=tool.dependencies,
            evolved_from=tool.tool_id
        )
        
        self.synthesized_tools[evolved_tool.tool_id] = evolved_tool
        
        return evolved_tool
    
    def _generate_tool_code(self, capability: str, failed_attempts: List[ExecutionTrace] = None) -> str:
        """Generate tool code - simulated implementation"""
        # In real implementation, this would call an LLM
        template = f'''def {capability.replace(' ', '_')}(input_data):
    """
    Auto-generated tool for: {capability}
    """
    # Implementation logic here
    result = process_input(input_data)
    return result
'''
        return template
    
    def _improve_tool_code(self, code: str, failure_patterns: List[str]) -> str:
        """Improve existing tool code based on failure patterns"""
        # Add error handling based on failure patterns
        improvements = []
        for pattern in failure_patterns:
            improvements.append(f"    # Handle: {pattern}")
        
        improved = code.replace("# Implementation logic here", 
                               "\n".join(improvements) + "\n    # Implementation logic here")
        return improved
    
    def _analyze_failures(self, feedback: List[ExecutionTrace], tool_id: str) -> List[str]:
        """Analyze execution traces to identify failure patterns"""
        patterns = []
        for trace in feedback:
            if not trace.success and tool_id in trace.tools_used:
                if trace.error_message:
                    patterns.append(trace.error_message)
        return list(set(patterns))  # Deduplicate
    
    def _infer_dependencies(self, capability: str) -> List[str]:
        """Infer Python dependencies based on capability description"""
        deps = []
        capability_lower = capability.lower()
        
        if any(kw in capability_lower for kw in ['http', 'web', 'url', 'api']):
            deps.append('requests')
        if any(kw in capability_lower for kw in ['data', 'csv', 'table']):
            deps.append('pandas')
        if any(kw in capability_lower for kw in ['math', 'calculate', 'statistics']):
            deps.append('numpy')
        
        return deps
    
    def _get_next_version(self, tool_id: str) -> int:
        """Get next version number for evolved tool"""
        versions = [t for t in self.synthesized_tools.keys() 
                   if t.startswith(f"{tool_id}_v")]
        if not versions:
            return 2
        return max(int(v.split('_v')[-1]) for v in versions) + 1
    
    def _generate_id(self) -> str:
        return hashlib.md5(str(datetime.now().timestamp()).encode()).hexdigest()[:8]


class TeacherSupervisor:
    """
    Guidance, evaluation, and curriculum design component.
    
    Similar to Teacher-LLM in the paper.
    """
    
    def __init__(self):
        self.curriculum: List[Task] = []
        self.evaluations: List[Dict[str, Any]] = []
        self.guidance_history: List[Dict[str, Any]] = []
        
    def design_curriculum(
        self, 
        target_task: Task, 
        current_difficulty: TaskDifficulty
    ) -> List[Task]:
        """
        Design a curriculum of progressively harder tasks.
        
        Uses curriculum learning principles from the paper.
        """
        curriculum = []
        
        # Start with easier variants
        difficulties = [TaskDifficulty.EASY, TaskDifficulty.MEDIUM, 
                       TaskDifficulty.HARD, TaskDifficulty.EXPERT]
        
        start_idx = difficulties.index(current_difficulty)
        
        for i, diff in enumerate(difficulties[start_idx:], start=start_idx):
            task_variant = Task(
                task_id=f"{target_task.task_id}_curriculum_{i}",
                description=f"[{diff.name}] {target_task.description}",
                difficulty=diff,
                domain=target_task.domain,
                required_tools=target_task.required_tools[:max(1, len(target_task.required_tools) - i)]
            )
            curriculum.append(task_variant)
        
        self.curriculum.extend(curriculum)
        return curriculum
    
    def evaluate_execution(
        self, 
        trace: ExecutionTrace, 
        expected_output: Any
    ) -> Dict[str, Any]:
        """
        Evaluate execution quality and provide feedback.
        
        Returns evaluation metrics and improvement suggestions.
        """
        evaluation = {
            'trace_id': trace.trace_id,
            'success': trace.success,
            'efficiency_score': 1.0 / (1 + trace.execution_time),
            'tool_efficiency': len(set(trace.tools_used)) / max(len(trace.steps), 1),
            'correctness': trace.success,  # Simplified - would compare to expected
            'suggestions': []
        }
        
        # Generate suggestions
        if not trace.success:
            evaluation['suggestions'].append("Consider tool synthesis for missing capabilities")
        
        if trace.execution_time > 10:  # Slow execution
            evaluation['suggestions'].append("Optimize tool selection or caching")
        
        if len(trace.tools_synthesized) > 2:
            evaluation['suggestions'].append("Review if synthesized tools can be consolidated")
        
        self.evaluations.append(evaluation)
        return evaluation
    
    def provide_guidance(
        self, 
        task: Task, 
        execution_history: List[ExecutionTrace]
    ) -> Dict[str, Any]:
        """Provide guidance for task execution based on history"""
        # Analyze similar past executions
        similar_traces = [t for t in execution_history if t.task_id.startswith(task.task_id[:10])]
        
        success_rate = sum(1 for t in similar_traces if t.success) / max(len(similar_traces), 1)
        
        guidance = {
            'task_id': task.task_id,
            'estimated_difficulty': task.difficulty.name,
            'historical_success_rate': success_rate,
            'recommended_strategy': self._recommend_strategy(similar_traces, success_rate),
            'warnings': []
        }
        
        if success_rate < 0.5:
            guidance['warnings'].append("Low historical success rate - consider curriculum learning")
        
        if task.difficulty == TaskDifficulty.EXPERT:
            guidance['warnings'].append("Expert-level task - tool synthesis likely needed")
        
        self.guidance_history.append(guidance)
        return guidance
    
    def _recommend_strategy(
        self, 
        similar_traces: List[ExecutionTrace], 
        success_rate: float
    ) -> str:
        """Recommend execution strategy based on historical performance"""
        if success_rate > 0.8:
            return "direct_execution"
        elif success_rate > 0.5:
            return "cautious_with_verification"
        else:
            return "tool_synthesis_first"


class EvolutionEngine:
    """
    Evolution mechanisms: CL, RL, GA-based improvement.
    
    Implements the three evolution strategies from the paper.
    """
    
    def __init__(self):
        self.population: List[EvolutionCandidate] = []
        self.generation = 0
        self.fitness_history: List[Dict[str, Any]] = []
        
    def evolve_with_curriculum_learning(
        self,
        task: Task,
        teacher: TeacherSupervisor,
        executor: OperationalExecutor,
        baseline_performance: float
    ) -> Tuple[Tool, float]:
        """
        Curriculum Learning evolution strategy.
        
        Fast recovery and strong generalization by training on
        progressively harder tasks.
        """
        curriculum = teacher.design_curriculum(task, TaskDifficulty.EASY)
        
        evolved_tools = []
        current_performance = baseline_performance
        
        for curriculum_task in curriculum:
            # Attempt execution
            trace = executor.execute_task(curriculum_task)
            evaluation = teacher.evaluate_execution(trace, curriculum_task.expected_output)
            
            if evaluation['success']:
                current_performance = min(1.0, current_performance + 0.2)
                # Mark tools used in this task as evolved
                for tool_id in trace.tools_used:
                    if tool_id in executor.tool_registry:
                        evolved_tools.append(executor.tool_registry[tool_id])
            else:
                # Need to evolve
                current_performance = max(0.0, current_performance - 0.1)
        
        # Return best evolved tool
        best_tool = evolved_tools[-1] if evolved_tools else None
        return best_tool, current_performance
    
    def evolve_with_reward_learning(
        self,
        task: Task,
        synthesizer: ToolSynthesizer,
        iterations: int = 10
    ) -> Tuple[Tool, float]:
        """
        Reward-Based Learning evolution strategy.
        
        Excels on high-difficulty tasks by using explicit reward signals
        to guide tool improvement.
        """
        # Initialize with random tool variant
        base_tool = synthesizer.synthesize_tool(
            task.description,
            task.required_tools[0] if task.required_tools else "general_processor"
        )
        
        best_tool = base_tool
        best_reward = 0.0
        
        for i in range(iterations):
            # Generate variant
            variant = synthesizer.evolve_tool(
                best_tool if i > 0 else base_tool,
                []  # Would use actual execution feedback
            )
            
            # Evaluate (simulated)
            reward = self._calculate_reward(variant, task, i)
            
            if reward > best_reward:
                best_reward = reward
                best_tool = variant
        
        return best_tool, best_reward
    
    def evolve_with_genetic_algorithm(
        self,
        population_size: int = 10,
        generations: int = 5,
        mutation_rate: float = 0.1
    ) -> EvolutionCandidate:
        """
        Genetic Algorithm evolution strategy.
        
        Promotes high behavioral diversity by maintaining a population
        of diverse tool combinations and selecting best performers.
        """
        # Initialize population
        if not self.population:
            for i in range(population_size):
                candidate = EvolutionCandidate(
                    candidate_id=f"ga_candidate_{i}_gen0",
                    tools=[],  # Would initialize with diverse tool sets
                    generation=0
                )
                self.population.append(candidate)
        
        for gen in range(generations):
            self.generation = gen
            
            # Evaluate fitness
            for candidate in self.population:
                candidate.fitness_score = self._evaluate_fitness(candidate)
            
            # Select top performers
            self.population.sort(key=lambda x: x.fitness_score, reverse=True)
            top_performers = self.population[:population_size // 2]
            
            # Create new generation through crossover and mutation
            new_population = top_performers.copy()
            
            while len(new_population) < population_size:
                parent1, parent2 = random.sample(top_performers, 2)
                child = self._crossover(parent1, parent2, gen)
                
                if random.random() < mutation_rate:
                    child = self._mutate(child)
                
                new_population.append(child)
            
            self.population = new_population
            
            # Record fitness history
            avg_fitness = sum(c.fitness_score for c in self.population) / len(self.population)
            self.fitness_history.append({
                'generation': gen,
                'avg_fitness': avg_fitness,
                'best_fitness': self.population[0].fitness_score
            })
        
        return self.population[0]  # Return best candidate
    
    def _calculate_reward(self, tool: Tool, task: Task, iteration: int) -> float:
        """Calculate reward for RL-based evolution"""
        # Simplified reward calculation
        base_reward = 0.5
        
        # Bonus for dependencies that match task domain
        if task.domain == 'code' and 'ast' in tool.dependencies:
            base_reward += 0.2
        if task.domain == 'data' and 'pandas' in tool.dependencies:
            base_reward += 0.2
        
        # Penalty for complexity (fewer deps = simpler = better)
        base_reward -= len(tool.dependencies) * 0.05
        
        # Iteration bonus (convergence)
        base_reward += iteration * 0.01
        
        return max(0.0, min(1.0, base_reward))
    
    def _evaluate_fitness(self, candidate: EvolutionCandidate) -> float:
        """Evaluate fitness of a GA candidate"""
        if not candidate.tools:
            return 0.0
        
        # Fitness based on tool diversity and historical performance
        diversity_score = len(set(t.name for t in candidate.tools)) / max(len(candidate.tools), 1)
        avg_success = sum(t.success_rate for t in candidate.tools) / max(len(candidate.tools), 1)
        
        return (diversity_score * 0.3) + (avg_success * 0.7)
    
    def _crossover(
        self, 
        parent1: EvolutionCandidate, 
        parent2: EvolutionCandidate,
        generation: int
    ) -> EvolutionCandidate:
        """Create child through crossover of two parents"""
        # Mix tools from both parents
        all_tools = parent1.tools + parent2.tools
        selected_tools = random.sample(
            all_tools, 
            k=min(len(all_tools), max(len(parent1.tools), len(parent2.tools)))
        )
        
        return EvolutionCandidate(
            candidate_id=f"ga_candidate_gen{generation}_{self._generate_id()}",
            tools=selected_tools,
            generation=generation,
            parent_ids=[parent1.candidate_id, parent2.candidate_id]
        )
    
    def _mutate(self, candidate: EvolutionCandidate) -> EvolutionCandidate:
        """Mutate a candidate by adding/removing/swapping tools"""
        candidate.mutations.append(f"mutated_at_{datetime.now().isoformat()}")
        
        # Random mutation: could add, remove, or swap tools
        mutation_type = random.choice(['add', 'remove', 'swap'])
        
        if mutation_type == 'add':
            # Would add a new random tool in real implementation
            pass
        elif mutation_type == 'remove' and candidate.tools:
            candidate.tools = candidate.tools[:-1]
        
        return candidate
    
    def _generate_id(self) -> str:
        return hashlib.md5(str(random.random()).encode()).hexdigest()[:6]


class HierarchicalSelfEvolvingAgent:
    """
    Main agent class integrating all hierarchical components.
    
    Implements the full self-evolving agent framework from the paper.
    """
    
    def __init__(self):
        self.reasoner = BaseReasoner()
        self.executor = OperationalExecutor()
        self.synthesizer = ToolSynthesizer()
        self.teacher = TeacherSupervisor()
        self.evolution = EvolutionEngine()
        
        self.execution_history: List[ExecutionTrace] = []
        self.task_library: Dict[str, Task] = {}
        self.evolution_stats: Dict[str, Any] = {
            'total_executions': 0,
            'successful_executions': 0,
            'tools_synthesized': 0,
            'tools_evolved': 0,
            'curriculum_tasks_completed': 0
        }
        
    def execute(self, goal: str, context: Dict[str, Any] = None) -> ExecutionTrace:
        """
        Execute a goal using the hierarchical self-evolving framework.
        
        Flow:
        1. Reasoner analyzes goal and decomposes into tasks
        2. Teacher provides guidance based on history
        3. Executor attempts with available tools
        4. If fails, Synthesizer creates new tools
        5. Evolution engine improves performance over time
        """
        # Step 1: Analyze goal
        analysis = self.reasoner.analyze_goal(goal)
        
        # Create task from goal
        task = Task(
            task_id=f"goal_{self._generate_id()}",
            description=goal,
            difficulty=TaskDifficulty.MEDIUM,  # Default, would be estimated
            domain=analysis['domain_keywords'][0] if analysis['domain_keywords'] else 'general'
        )
        
        # Step 2: Get guidance
        guidance = self.teacher.provide_guidance(task, self.execution_history)
        
        # Step 3: Decompose task
        available_tools = set(self.executor.tool_registry.keys())
        decomposed_task = self.reasoner.decompose_task(task, available_tools)
        
        # Step 4: Execute (may involve tool synthesis if needed)
        trace = self._execute_with_synthesis(decomposed_task, guidance)
        
        # Step 5: Evaluate and evolve if needed
        evaluation = self.teacher.evaluate_execution(trace, task.expected_output)
        
        if not trace.success or evaluation['efficiency_score'] < 0.5:
            # Trigger evolution
            self._evolve_for_task(task, trace, evaluation)
        
        # Update stats
        self.execution_history.append(trace)
        self.evolution_stats['total_executions'] += 1
        if trace.success:
            self.evolution_stats['successful_executions'] += 1
        self.evolution_stats['tools_synthesized'] += len(trace.tools_synthesized)
        
        return trace
    
    def _execute_with_synthesis(
        self, 
        task: Task, 
        guidance: Dict[str, Any]
    ) -> ExecutionTrace:
        """
        Execute task, synthesizing tools if needed.
        """
        # Check if synthesis is needed
        if task.metadata.get('needs_synthesis'):
            for missing_tool in task.metadata['needs_synthesis']:
                # Synthesize missing tool
                new_tool = self.synthesizer.synthesize_tool(
                    task.description,
                    missing_tool
                )
                self.executor.register_tool(new_tool)
        
        # Now execute
        if task.is_primitive():
            return self.executor.execute_task(task)
        
        # Execute subtasks
        trace = ExecutionTrace(
            trace_id=self._generate_id(),
            task_id=task.task_id,
            success=True
        )
        
        for subtask in task.subtasks:
            subtrace = self._execute_with_synthesis(subtask, guidance)
            trace.steps.extend(subtrace.steps)
            trace.tools_used.extend(subtrace.tools_used)
            trace.tools_synthesized.extend(subtrace.tools_synthesized)
            
            if not subtrace.success:
                trace.success = False
                trace.error_message = subtrace.error_message
                break
        
        return trace
    
    def _evolve_for_task(
        self,
        task: Task,
        trace: ExecutionTrace,
        evaluation: Dict[str, Any]
    ):
        """
        Trigger appropriate evolution strategy based on task characteristics.
        """
        strategy = self.reasoner.select_strategy(task, self.execution_history)
        
        if strategy == EvolutionStrategy.CURRICULUM_LEARNING:
            # Use curriculum learning for general improvement
            baseline = self.evolution_stats['successful_executions'] / max(
                self.evolution_stats['total_executions'], 1
            )
            evolved_tool, new_performance = self.evolution.evolve_with_curriculum_learning(
                task, self.teacher, self.executor, baseline
            )
            if evolved_tool:
                self.evolution_stats['tools_evolved'] += 1
                
        elif strategy == EvolutionStrategy.REWARD_BASED_LEARNING:
            # Use RL for hard tasks
            evolved_tool, reward = self.evolution.evolve_with_reward_learning(
                task, self.synthesizer
            )
            self.evolution_stats['tools_evolved'] += 1
            
        elif strategy == EvolutionStrategy.GENETIC_ALGORITHM:
            # Use GA for diversity
            best_candidate = self.evolution.evolve_with_genetic_algorithm()
            self.evolution_stats['tools_evolved'] += len(best_candidate.tools)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get agent evolution statistics"""
        return {
            **self.evolution_stats,
            'success_rate': (
                self.evolution_stats['successful_executions'] / 
                max(self.evolution_stats['total_executions'], 1)
            ),
            'total_tools': len(self.executor.tool_registry),
            'synthesized_tools': len(self.synthesizer.synthesized_tools),
            'execution_history_length': len(self.execution_history),
            'reasoning_steps': len(self.reasoner.reasoning_history),
            'curriculum_length': len(self.teacher.curriculum),
            'ga_generations': self.evolution.generation
        }
    
    def register_builtin_tool(self, name: str, description: str, code: str):
        """Register a built-in tool"""
        tool = Tool(
            tool_id=f"builtin_{name}",
            name=name,
            description=description,
            code=code,
            signature=f"def {name}(*args, **kwargs):"
        )
        self.executor.register_tool(tool)
    
    def _generate_id(self) -> str:
        return hashlib.md5(
            f"{datetime.now().isoformat()}{random.random()}".encode()
        ).hexdigest()[:10]


# Convenience factory function
def create_hierarchical_agent() -> HierarchicalSelfEvolvingAgent:
    """Factory function to create a fully initialized hierarchical agent"""
    agent = HierarchicalSelfEvolvingAgent()
    
    # Register some basic built-in tools
    agent.register_builtin_tool(
        "calculate",
        "Perform mathematical calculations",
        "def calculate(expression): return eval(expression)"
    )
    
    agent.register_builtin_tool(
        "search",
        "Search for information",
        "def search(query): return f'Search results for: {query}'"
    )
    
    agent.register_builtin_tool(
        "transform_text",
        "Transform text (uppercase, lowercase, etc.)",
        "def transform_text(text, operation): return getattr(text, operation)()"
    )
    
    return agent
