"""
Self-Evolving Agent System (arXiv:2601.11658v1)

A pragmatic self-evolving agent implementing hierarchical LLM architecture:
- Base LLM: Core reasoning and task understanding
- Operational SLM (Small Language Model): Fast, efficient task execution
- Code-Gen LLM: Code generation and tool synthesis
- Teacher LLM: Evaluation, feedback, and curriculum generation

Evolution methods supported:
- Curriculum Learning: Gradual difficulty progression with rapid recovery
- Reinforcement Learning: Policy optimization for high-difficulty tasks
- Genetic Algorithms: Population-based diversity preservation

Reference: "Towards AGI: Pragmatic Self-Evolving Agent" (arXiv:2601.11658v1)
"""

from typing import Dict, List, Any, Optional, Callable, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum, auto
import random
import json
import time
from collections import defaultdict
import copy


class EvolutionMethod(Enum):
    """Evolution strategies for agent improvement."""
    CURRICULUM_LEARNING = auto()  # Gradual difficulty, fast recovery
    REINFORCEMENT_LEARNING = auto()  # RL for high-difficulty tasks
    GENETIC_ALGORITHM = auto()  # Population diversity preservation
    HYBRID = auto()  # Combine multiple methods


class TaskDifficulty(Enum):
    """Task difficulty levels for curriculum learning."""
    ELEMENTARY = 1
    INTERMEDIATE = 2
    ADVANCED = 3
    EXPERT = 4
    RESEARCH = 5


@dataclass
class ToolUseTrace:
    """Record of tool usage in task execution."""
    tool_name: str
    inputs: Dict[str, Any]
    outputs: Any
    success: bool
    execution_time: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class TaskInstance:
    """Individual task with difficulty and tool requirements."""
    task_id: str
    description: str
    difficulty: TaskDifficulty
    expected_output: Any
    tools_required: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    tool_traces: List[ToolUseTrace] = field(default_factory=list)


@dataclass
class EvolutionCheckpoint:
    """Snapshot of agent state during evolution."""
    generation: int
    timestamp: float
    performance_metrics: Dict[str, float]
    agent_weights: Dict[str, Any]
    curriculum_stage: TaskDifficulty
    population_diversity: float


@dataclass
class EvaluationResult:
    """Task evaluation outcome with detailed metrics."""
    task_id: str
    success: bool
    output: Any
    tool_traces: List[ToolUseTrace]
    execution_time: float
    attempts: int
    teacher_feedback: str
    score: float  # 0.0 to 1.0
    improvement_suggestions: List[str]


class BaseLLM:
    """
    Core reasoning and task understanding module.
    Handles high-level planning and semantic understanding.
    """
    
    def __init__(self, model_name: str = "base_llm"):
        self.model_name = model_name
        self.reasoning_patterns: Dict[str, Any] = {}
        self.task_understanding_cache: Dict[str, Dict] = {}
    
    def understand_task(self, task: TaskInstance) -> Dict[str, Any]:
        """Analyze task requirements and create execution plan."""
        cache_key = f"{task.task_id}_{hash(task.description) % 10000}"
        
        if cache_key in self.task_understanding_cache:
            return self.task_understanding_cache[cache_key]
        
        understanding = {
            "task_type": self._classify_task(task),
            "complexity_score": self._compute_complexity(task),
            "required_capabilities": task.tools_required,
            "decomposition": self._decompose_task(task),
            "key_constraints": self._extract_constraints(task),
            "estimated_difficulty": task.difficulty.value
        }
        
        self.task_understanding_cache[cache_key] = understanding
        return understanding
    
    def _classify_task(self, task: TaskInstance) -> str:
        """Classify task into category."""
        description_lower = task.description.lower()
        if "code" in description_lower or "implement" in description_lower:
            return "coding"
        elif "analyze" in description_lower or "research" in description_lower:
            return "analysis"
        elif "search" in description_lower or "find" in description_lower:
            return "information_retrieval"
        elif "plan" in description_lower or "schedule" in description_lower:
            return "planning"
        return "general"
    
    def _compute_complexity(self, task: TaskInstance) -> float:
        """Estimate task complexity (0.0 to 1.0)."""
        base = task.difficulty.value / 5.0
        tool_factor = min(len(task.tools_required) * 0.1, 0.3)
        desc_length = min(len(task.description) / 500, 0.2)
        return min(base + tool_factor + desc_length, 1.0)
    
    def _decompose_task(self, task: TaskInstance) -> List[str]:
        """Break task into sub-tasks."""
        if task.difficulty.value <= 2:
            return ["execute_directly"]
        
        decompositions = {
            "coding": ["understand_requirements", "design_approach", "implement", "test", "refine"],
            "analysis": ["gather_data", "analyze_patterns", "synthesize_insights", "present_findings"],
            "information_retrieval": ["formulate_query", "search", "filter_results", "compile_answer"],
            "planning": ["identify_constraints", "generate_options", "evaluate_tradeoffs", "create_schedule"]
        }
        
        task_type = self._classify_task(task)
        return decompositions.get(task_type, ["analyze", "execute", "verify"])
    
    def _extract_constraints(self, task: TaskInstance) -> List[str]:
        """Extract constraints from task description."""
        constraints = []
        desc_lower = task.description.lower()
        
        if "must" in desc_lower:
            constraints.append("hard_requirement")
        if "within" in desc_lower and ("minute" in desc_lower or "hour" in desc_lower):
            constraints.append("time_bound")
        if "exactly" in desc_lower or "precise" in desc_lower:
            constraints.append("precision_required")
        
        return constraints
    
    def adapt_reasoning(self, feedback: List[EvaluationResult]):
        """Update reasoning patterns based on evaluation feedback."""
        for result in feedback:
            if not result.success:
                pattern_key = f"failed_{result.task_id.split('_')[0]}"
                self.reasoning_patterns[pattern_key] = {
                    "failure_count": self.reasoning_patterns.get(pattern_key, {}).get("failure_count", 0) + 1,
                    "suggestions": result.improvement_suggestions
                }


class OperationalSLM:
    """
    Small, fast language model for efficient task execution.
    Optimized for speed and common task patterns.
    """
    
    def __init__(self, model_name: str = "operational_slm"):
        self.model_name = model_name
        self.fast_patterns: Dict[str, Callable] = {}
        self.execution_cache: Dict[str, Any] = {}
        self.response_time_target = 1.0  # seconds
    
    def execute(self, task: TaskInstance, plan: Dict[str, Any], 
                tools: Dict[str, Callable]) -> Tuple[Any, List[ToolUseTrace]]:
        """Execute task quickly using cached patterns."""
        traces = []
        start_time = time.time()
        
        # Check for cached execution pattern
        cache_key = self._get_cache_key(task)
        if cache_key in self.execution_cache and task.difficulty.value <= 2:
            return self.execution_cache[cache_key], traces
        
        # Execute based on task type
        task_type = plan.get("task_type", "general")
        
        if task_type in self.fast_patterns:
            result = self.fast_patterns[task_type](task, tools)
        else:
            result = self._generic_execute(task, tools, traces)
        
        execution_time = time.time() - start_time
        
        # Cache simple tasks
        if task.difficulty.value <= 2 and execution_time < self.response_time_target:
            self.execution_cache[cache_key] = result
        
        return result, traces
    
    def _get_cache_key(self, task: TaskInstance) -> str:
        """Generate cache key for task."""
        return f"{hash(task.description) % 10000}_{task.difficulty.value}"
    
    def _generic_execute(self, task: TaskInstance, tools: Dict[str, Callable],
                         traces: List[ToolUseTrace]) -> Any:
        """Generic task execution with tool calls."""
        result = {"task": task.description, "status": "in_progress"}
        
        for tool_name in task.tools_required:
            if tool_name in tools:
                tool_start = time.time()
                try:
                    tool_result = tools[tool_name](task.description)
                    trace = ToolUseTrace(
                        tool_name=tool_name,
                        inputs={"query": task.description},
                        outputs=tool_result,
                        success=True,
                        execution_time=time.time() - tool_start
                    )
                    result[tool_name] = tool_result
                except Exception as e:
                    trace = ToolUseTrace(
                        tool_name=tool_name,
                        inputs={"query": task.description},
                        outputs=str(e),
                        success=False,
                        execution_time=time.time() - tool_start
                    )
                    result[f"{tool_name}_error"] = str(e)
                
                traces.append(trace)
        
        result["status"] = "completed"
        return result
    
    def register_pattern(self, task_type: str, pattern: Callable):
        """Register fast execution pattern for task type."""
        self.fast_patterns[task_type] = pattern
    
    def get_performance_stats(self) -> Dict[str, float]:
        """Return execution performance statistics."""
        return {
            "cache_size": len(self.execution_cache),
            "pattern_count": len(self.fast_patterns),
            "target_response_time": self.response_time_target
        }


class CodeGenLLM:
    """
    Code generation and tool synthesis module.
    Creates new tools and modifies existing code.
    """
    
    def __init__(self, model_name: str = "code_gen_llm"):
        self.model_name = model_name
        self.generated_tools: Dict[str, Dict] = {}
        self.code_patterns: Dict[str, str] = {}
        self.synthesis_history: List[Dict] = []
    
    def synthesize_tool(self, requirement: str, examples: List[Dict] = None) -> Dict[str, Any]:
        """Generate new tool based on requirement description."""
        tool_id = f"synthesized_{hash(requirement) % 100000}"
        
        # Simulate code generation
        tool_spec = {
            "tool_id": tool_id,
            "name": self._generate_tool_name(requirement),
            "description": requirement,
            "parameters": self._infer_parameters(requirement),
            "implementation": self._generate_implementation(requirement, examples),
            "examples": examples or [],
            "generation_timestamp": time.time(),
            "version": 1
        }
        
        self.generated_tools[tool_id] = tool_spec
        self.synthesis_history.append({
            "timestamp": time.time(),
            "requirement": requirement,
            "tool_id": tool_id
        })
        
        return tool_spec
    
    def _generate_tool_name(self, requirement: str) -> str:
        """Generate descriptive name for tool."""
        words = requirement.lower().split()[:5]
        key_words = [w for w in words if len(w) > 3 and w not in 
                    ["create", "generate", "implement", "build", "make"]]
        if key_words:
            return f"tool_{'_'.join(key_words[:3])}"
        return f"tool_{hash(requirement) % 10000}"
    
    def _infer_parameters(self, requirement: str) -> Dict[str, str]:
        """Infer tool parameters from requirement."""
        params = {}
        req_lower = requirement.lower()
        
        if "search" in req_lower or "find" in req_lower:
            params["query"] = "string"
        if "filter" in req_lower or "select" in req_lower:
            params["criteria"] = "dict"
        if "transform" in req_lower or "convert" in req_lower:
            params["input_data"] = "any"
            params["output_format"] = "string"
        if "summarize" in req_lower or "analyze" in req_lower:
            params["content"] = "string"
            params["max_length"] = "int"
        
        return params if params else {"input": "any"}
    
    def _generate_implementation(self, requirement: str, examples: List[Dict]) -> str:
        """Generate Python code implementation."""
        # Template-based code generation
        template = f'''def {self._generate_tool_name(requirement)}({', '.join(self._infer_parameters(requirement).keys())}):
    """
    {requirement}
    """
    # Implementation
    result = {{}}
    
    # TODO: Implement logic based on requirement
    # Generated for: {requirement[:50]}...
    
    return result
'''
        return template
    
    def modify_existing(self, tool_id: str, feedback: str) -> Dict[str, Any]:
        """Modify existing tool based on feedback."""
        if tool_id not in self.generated_tools:
            return {"error": f"Tool {tool_id} not found"}
        
        tool = self.generated_tools[tool_id]
        tool["version"] += 1
        tool["modification_history"] = tool.get("modification_history", []) + [{
            "timestamp": time.time(),
            "feedback": feedback,
            "version": tool["version"]
        }]
        
        return tool
    
    def get_synthesis_stats(self) -> Dict[str, int]:
        """Return tool synthesis statistics."""
        return {
            "total_tools": len(self.generated_tools),
            "total_modifications": sum(
                len(t.get("modification_history", [])) 
                for t in self.generated_tools.values()
            ),
            "synthesis_attempts": len(self.synthesis_history)
        }


class TeacherLLM:
    """
    Evaluation, feedback, and curriculum generation module.
    Provides assessment and learning guidance.
    """
    
    def __init__(self, model_name: str = "teacher_llm"):
        self.model_name = model_name
        self.evaluation_criteria: Dict[str, Dict] = {}
        self.curriculum_stages: List[TaskDifficulty] = list(TaskDifficulty)
        self.feedback_history: List[Dict] = []
        self.performance_thresholds = {
            "pass": 0.6,
            "good": 0.8,
            "excellent": 0.95
        }
    
    def evaluate(self, task: TaskInstance, output: Any, 
                 traces: List[ToolUseTrace]) -> EvaluationResult:
        """Evaluate task execution and provide feedback."""
        # Calculate success
        success = self._check_success(task, output, traces)
        
        # Calculate score
        score = self._calculate_score(task, output, traces, success)
        
        # Generate feedback
        feedback = self._generate_feedback(task, output, traces, score)
        
        # Generate improvement suggestions
        suggestions = self._generate_suggestions(task, traces, score)
        
        result = EvaluationResult(
            task_id=task.task_id,
            success=success,
            output=output,
            tool_traces=traces,
            execution_time=sum(t.execution_time for t in traces) if traces else 0,
            attempts=1,
            teacher_feedback=feedback,
            score=score,
            improvement_suggestions=suggestions
        )
        
        self.feedback_history.append({
            "timestamp": time.time(),
            "task_id": task.task_id,
            "score": score,
            "success": success
        })
        
        return result
    
    def _check_success(self, task: TaskInstance, output: Any, 
                       traces: List[ToolUseTrace]) -> bool:
        """Determine if task was completed successfully."""
        # Check tool success rate
        if traces:
            success_rate = sum(1 for t in traces if t.success) / len(traces)
            if success_rate < 0.5:
                return False
        
        # Check output structure
        if isinstance(output, dict):
            if "error" in output and output["error"]:
                return False
            if "status" in output and output["status"] == "completed":
                return True
        
        return True  # Default to success if no clear failure indicators
    
    def _calculate_score(self, task: TaskInstance, output: Any,
                        traces: List[ToolUseTrace], success: bool) -> float:
        """Calculate performance score (0.0 to 1.0)."""
        if not success:
            return random.uniform(0.1, 0.4)  # Partial credit
        
        base_score = 0.6 if success else 0.0
        
        # Tool efficiency bonus
        if traces:
            avg_tool_success = sum(1 for t in traces if t.success) / len(traces)
            efficiency_bonus = avg_tool_success * 0.2
            
            # Speed bonus
            total_time = sum(t.execution_time for t in traces)
            if total_time < 1.0:
                speed_bonus = 0.1
            elif total_time < 5.0:
                speed_bonus = 0.05
            else:
                speed_bonus = 0.0
        else:
            efficiency_bonus = 0.0
            speed_bonus = 0.1  # Bonus for tool-less completion
        
        # Difficulty adjustment
        difficulty_factor = task.difficulty.value / 5.0
        
        score = base_score + efficiency_bonus + speed_bonus + (difficulty_factor * 0.1)
        return min(score, 1.0)
    
    def _generate_feedback(self, task: TaskInstance, output: Any,
                          traces: List[ToolUseTrace], score: float) -> str:
        """Generate natural language feedback."""
        if score >= self.performance_thresholds["excellent"]:
            return f"Excellent work on {task.task_id}. Execution was efficient and correct."
        elif score >= self.performance_thresholds["good"]:
            return f"Good performance on {task.task_id}. Minor optimizations possible."
        elif score >= self.performance_thresholds["pass"]:
            return f"Acceptable completion of {task.task_id}. Some issues encountered."
        else:
            return f"Needs improvement on {task.task_id}. Review tool usage and approach."
    
    def _generate_suggestions(self, task: TaskInstance, 
                              traces: List[ToolUseTrace], score: float) -> List[str]:
        """Generate specific improvement suggestions."""
        suggestions = []
        
        if score < self.performance_thresholds["good"]:
            # Check for tool failures
            failed_tools = [t.tool_name for t in traces if not t.success]
            if failed_tools:
                suggestions.append(f"Improve reliability of tools: {', '.join(set(failed_tools))}")
            
            # Check execution time
            if traces and sum(t.execution_time for t in traces) > 5.0:
                suggestions.append("Optimize execution speed - consider caching or parallelization")
            
            # Check tool count
            if len(traces) > 5:
                suggestions.append("Reduce tool chain complexity - combine or streamline operations")
        
        if not suggestions and score < 1.0:
            suggestions.append("Fine-tune parameters for optimal performance")
        
        return suggestions
    
    def generate_curriculum(self, current_stage: TaskDifficulty,
                           performance_history: List[float]) -> List[TaskInstance]:
        """Generate next curriculum based on performance."""
        avg_performance = sum(performance_history) / len(performance_history) if performance_history else 0.5
        
        # Determine next difficulty
        if avg_performance > self.performance_thresholds["excellent"]:
            next_difficulty = min(current_stage.value + 1, 5)
        elif avg_performance > self.performance_thresholds["good"]:
            next_difficulty = current_stage.value
        else:
            next_difficulty = max(current_stage.value - 1, 1)
        
        next_difficulty_enum = TaskDifficulty(next_difficulty)
        
        # Generate curriculum tasks
        curriculum = []
        for i in range(5):  # 5 tasks per stage
            task = TaskInstance(
                task_id=f"curriculum_{next_difficulty_enum.name}_{i}",
                description=f"Curriculum task at {next_difficulty_enum.name} level",
                difficulty=next_difficulty_enum,
                expected_output=f"output_{i}",
                tools_required=["search", "analyze"][:i+1]
            )
            curriculum.append(task)
        
        return curriculum
    
    def get_evaluation_stats(self) -> Dict[str, Any]:
        """Return evaluation statistics."""
        if not self.feedback_history:
            return {"evaluations": 0}
        
        scores = [f["score"] for f in self.feedback_history]
        return {
            "evaluations": len(self.feedback_history),
            "average_score": sum(scores) / len(scores),
            "success_rate": sum(1 for f in self.feedback_history if f["success"]) / len(self.feedback_history),
            "excellent_rate": sum(1 for f in self.feedback_history if f["score"] >= 0.95) / len(self.feedback_history)
        }


class SelfEvolvingAgent:
    """
    Main self-evolving agent coordinating all LLM modules.
    
    Implements evolution through:
    1. Curriculum Learning: Progressive difficulty with rapid recovery
    2. Reinforcement Learning: Policy optimization for complex tasks
    3. Genetic Algorithm: Population diversity for robust solutions
    """
    
    def __init__(
        self,
        evolution_method: EvolutionMethod = EvolutionMethod.HYBRID,
        population_size: int = 5,
        mutation_rate: float = 0.1
    ):
        # Hierarchical LLM modules
        self.base_llm = BaseLLM()
        self.operational_slm = OperationalSLM()
        self.code_gen_llm = CodeGenLLM()
        self.teacher_llm = TeacherLLM()
        
        # Evolution configuration
        self.evolution_method = evolution_method
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        
        # State
        self.generation = 0
        self.current_difficulty = TaskDifficulty.ELEMENTARY
        self.population: List[Dict[str, Any]] = []
        self.performance_history: List[float] = []
        self.checkpoints: List[EvolutionCheckpoint] = []
        self.evolved_tools: Dict[str, Any] = {}
        
        # Metrics
        self.execution_stats = {
            "total_tasks": 0,
            "successful_tasks": 0,
            "total_evaluations": 0,
            "evolution_cycles": 0
        }
        
        # Initialize population for genetic algorithm
        if evolution_method in [EvolutionMethod.GENETIC_ALGORITHM, EvolutionMethod.HYBRID]:
            self._initialize_population()
    
    def _initialize_population(self):
        """Initialize genetic algorithm population."""
        for i in range(self.population_size):
            individual = {
                "id": f"individual_{i}",
                "base_weights": self._random_weights(),
                "slm_patterns": set(),
                "fitness": 0.0
            }
            self.population.append(individual)
    
    def _random_weights(self) -> Dict[str, float]:
        """Generate random weights for individual."""
        return {
            "reasoning": random.uniform(0.5, 1.0),
            "execution": random.uniform(0.5, 1.0),
            "code_gen": random.uniform(0.5, 1.0),
            "learning_rate": random.uniform(0.01, 0.1)
        }
    
    def execute_task(self, task: TaskInstance, 
                    tools: Dict[str, Callable] = None) -> EvaluationResult:
        """
        Execute a task using the hierarchical LLM architecture.
        
        Flow:
        1. Base LLM: Understand task and create plan
        2. Operational SLM: Execute efficiently
        3. Code-Gen LLM: Synthesize tools if needed
        4. Teacher LLM: Evaluate and provide feedback
        """
        tools = tools or {}
        start_time = time.time()
        
        # Step 1: Base LLM - Understand and plan
        understanding = self.base_llm.understand_task(task)
        
        # Step 2: Check if tool synthesis needed
        missing_tools = [t for t in task.tools_required if t not in tools]
        for missing in missing_tools:
            # Use Code-Gen LLM to synthesize missing tool
            new_tool_spec = self.code_gen_llm.synthesize_tool(
                f"Tool to perform {missing} operations",
                examples=[]
            )
            self.evolved_tools[missing] = new_tool_spec
        
        # Step 3: Operational SLM - Execute with tools
        output, traces = self.operational_slm.execute(task, understanding, tools)
        
        # Step 4: Teacher LLM - Evaluate
        evaluation = self.teacher_llm.evaluate(task, output, traces)
        
        # Update metrics
        self.execution_stats["total_tasks"] += 1
        if evaluation.success:
            self.execution_stats["successful_tasks"] += 1
        self.performance_history.append(evaluation.score)
        
        return evaluation
    
    def evolve(self, task_batch: List[TaskInstance],
               tools: Dict[str, Callable] = None) -> Dict[str, Any]:
        """
        Execute evolution cycle on task batch.
        
        Returns evolution metrics and improvements.
        """
        tools = tools or {}
        cycle_start = time.time()
        
        results = []
        
        # Execute all tasks
        for task in task_batch:
            result = self.execute_task(task, tools)
            results.append(result)
        
        # Apply evolution method
        if self.evolution_method == EvolutionMethod.CURRICULUM_LEARNING:
            improvements = self._curriculum_learning_evolution(results)
        elif self.evolution_method == EvolutionMethod.REINFORCEMENT_LEARNING:
            improvements = self._reinforcement_learning_evolution(results)
        elif self.evolution_method == EvolutionMethod.GENETIC_ALGORITHM:
            improvements = self._genetic_evolution(results)
        else:  # HYBRID
            improvements = self._hybrid_evolution(results)
        
        # Create checkpoint
        checkpoint = EvolutionCheckpoint(
            generation=self.generation,
            timestamp=time.time(),
            performance_metrics={
                "avg_score": sum(r.score for r in results) / len(results),
                "success_rate": sum(1 for r in results if r.success) / len(results)
            },
            agent_weights=self._get_current_weights(),
            curriculum_stage=self.current_difficulty,
            population_diversity=self._calculate_diversity()
        )
        self.checkpoints.append(checkpoint)
        
        # Update generation
        self.generation += 1
        self.execution_stats["evolution_cycles"] += 1
        
        return {
            "generation": self.generation,
            "results_count": len(results),
            "improvements": improvements,
            "checkpoint": checkpoint,
            "cycle_time": time.time() - cycle_start,
            "evolution_method": self.evolution_method.name
        }
    
    def _curriculum_learning_evolution(self, results: List[EvaluationResult]) -> Dict[str, Any]:
        """Evolve using curriculum learning - rapid recovery, gradual difficulty."""
        avg_score = sum(r.score for r in results) / len(results)
        
        # Adjust difficulty based on performance
        if avg_score > 0.9:
            old_difficulty = self.current_difficulty
            self.current_difficulty = min(
                TaskDifficulty(self.current_difficulty.value + 1),
                TaskDifficulty.RESEARCH
            )
            return {
                "method": "curriculum_learning",
                "difficulty_changed": old_difficulty != self.current_difficulty,
                "new_difficulty": self.current_difficulty.name,
                "avg_score": avg_score,
                "rationale": "Excellent performance - advancing curriculum"
            }
        elif avg_score < 0.5:
            old_difficulty = self.current_difficulty
            self.current_difficulty = max(
                TaskDifficulty(self.current_difficulty.value - 1),
                TaskDifficulty.ELEMENTARY
            )
            return {
                "method": "curriculum_learning",
                "difficulty_changed": old_difficulty != self.current_difficulty,
                "new_difficulty": self.current_difficulty.name,
                "avg_score": avg_score,
                "rationale": "Poor performance - regressing for recovery"
            }
        
        return {
            "method": "curriculum_learning",
            "difficulty_changed": False,
            "current_difficulty": self.current_difficulty.name,
            "avg_score": avg_score,
            "rationale": "Maintaining current curriculum level"
        }
    
    def _reinforcement_learning_evolution(self, results: List[EvaluationResult]) -> Dict[str, Any]:
        """Evolve using reinforcement learning - optimize for high-difficulty tasks."""
        # Calculate reward
        total_reward = sum(r.score * (r.task_id.count("hard") + 1) for r in results)
        
        # Update policy (simplified - update operational SLM patterns)
        for result in results:
            if result.score > 0.8:
                # Reinforce successful patterns
                self.operational_slm.register_pattern(
                    f"success_pattern_{result.task_id}",
                    lambda t, tools: result.output
                )
        
        # Update base LLM reasoning
        self.base_llm.adapt_reasoning(results)
        
        return {
            "method": "reinforcement_learning",
            "total_reward": total_reward,
            "policy_updates": len([r for r in results if r.score > 0.8]),
            "rationale": "Policy optimized for high-value completions"
        }
    
    def _genetic_evolution(self, results: List[EvaluationResult]) -> Dict[str, Any]:
        """Evolve using genetic algorithm - maintain population diversity."""
        # Update fitness scores
        for individual in self.population:
            individual["fitness"] = sum(
                r.score for r in results
            ) / len(results) * random.uniform(0.9, 1.1)  # Add noise for diversity
        
        # Sort by fitness
        self.population.sort(key=lambda x: x["fitness"], reverse=True)
        
        # Select top performers
        survivors = self.population[:self.population_size // 2]
        
        # Create offspring through crossover and mutation
        offspring = []
        while len(offspring) < self.population_size - len(survivors):
            parent1 = random.choice(survivors)
            parent2 = random.choice(survivors)
            
            child = self._crossover(parent1, parent2)
            child = self._mutate(child)
            offspring.append(child)
        
        # Update population
        self.population = survivors + offspring
        
        # Apply best individual's weights
        best = self.population[0]
        # (In real implementation, would apply weights to LLM modules)
        
        return {
            "method": "genetic_algorithm",
            "best_fitness": best["fitness"],
            "population_diversity": self._calculate_diversity(),
            "generations_completed": self.generation,
            "rationale": "Population evolved with diversity preservation"
        }
    
    def _hybrid_evolution(self, results: List[EvaluationResult]) -> Dict[str, Any]:
        """Combine curriculum, RL, and genetic evolution."""
        # Run curriculum learning for difficulty adjustment
        curriculum_result = self._curriculum_learning_evolution(results)
        
        # Run RL for policy optimization
        rl_result = self._reinforcement_learning_evolution(results)
        
        # Run genetic for population diversity (every 3 generations)
        genetic_result = None
        if self.generation % 3 == 0:
            genetic_result = self._genetic_evolution(results)
        
        return {
            "method": "hybrid",
            "curriculum": curriculum_result,
            "reinforcement_learning": rl_result,
            "genetic": genetic_result,
            "rationale": "Multi-method evolution for comprehensive improvement"
        }
    
    def _crossover(self, parent1: Dict, parent2: Dict) -> Dict[str, Any]:
        """Create child through crossover of two parents."""
        child = {
            "id": f"child_{self.generation}_{random.randint(0, 1000)}",
            "base_weights": {},
            "slm_patterns": parent1["slm_patterns"].copy(),
            "fitness": 0.0
        }
        
        # Crossover weights
        for key in parent1["base_weights"]:
            if random.random() < 0.5:
                child["base_weights"][key] = parent1["base_weights"][key]
            else:
                child["base_weights"][key] = parent2["base_weights"][key]
        
        # Merge patterns
        child["slm_patterns"].update(parent2["slm_patterns"])
        
        return child
    
    def _mutate(self, individual: Dict[str, Any]) -> Dict[str, Any]:
        """Apply mutation to individual."""
        # Mutate weights
        for key in individual["base_weights"]:
            if random.random() < self.mutation_rate:
                individual["base_weights"][key] *= random.uniform(0.8, 1.2)
                individual["base_weights"][key] = min(individual["base_weights"][key], 1.0)
        
        return individual
    
    def _calculate_diversity(self) -> float:
        """Calculate population diversity metric."""
        if not self.population or len(self.population) < 2:
            return 0.0
        
        # Calculate average pairwise difference
        differences = []
        for i, ind1 in enumerate(self.population):
            for ind2 in self.population[i+1:]:
                diff = sum(
                    abs(ind1["base_weights"].get(k, 0) - ind2["base_weights"].get(k, 0))
                    for k in set(ind1["base_weights"]) | set(ind2["base_weights"])
                )
                differences.append(diff)
        
        return sum(differences) / len(differences) if differences else 0.0
    
    def _get_current_weights(self) -> Dict[str, float]:
        """Get current agent weights."""
        if self.population:
            return self.population[0]["base_weights"]
        return {"reasoning": 1.0, "execution": 1.0, "code_gen": 1.0, "learning_rate": 0.05}
    
    def get_evolution_report(self) -> Dict[str, Any]:
        """Generate comprehensive evolution report."""
        return {
            "generation": self.generation,
            "evolution_method": self.evolution_method.name,
            "current_difficulty": self.current_difficulty.name,
            "execution_stats": self.execution_stats,
            "population_diversity": self._calculate_diversity(),
            "evolved_tools_count": len(self.evolved_tools),
            "checkpoints": len(self.checkpoints),
            "llm_stats": {
                "base_llm": {"reasoning_patterns": len(self.base_llm.reasoning_patterns)},
                "operational_slm": self.operational_slm.get_performance_stats(),
                "code_gen_llm": self.code_gen_llm.get_synthesis_stats(),
                "teacher_llm": self.teacher_llm.get_evaluation_stats()
            },
            "recent_performance": {
                "last_10_avg": sum(self.performance_history[-10:]) / min(len(self.performance_history), 10)
                                  if self.performance_history else 0,
                "trend": "improving" if len(self.performance_history) > 10 and
                         self.performance_history[-1] > self.performance_history[-10]
                         else "stable"
            }
        }


# Factory functions for easy agent creation

def create_curriculum_agent() -> SelfEvolvingAgent:
    """Create agent optimized for curriculum learning."""
    return SelfEvolvingAgent(
        evolution_method=EvolutionMethod.CURRICULUM_LEARNING
    )


def create_rl_agent() -> SelfEvolvingAgent:
    """Create agent optimized for reinforcement learning."""
    return SelfEvolvingAgent(
        evolution_method=EvolutionMethod.REINFORCEMENT_LEARNING
    )


def create_genetic_agent(population_size: int = 10) -> SelfEvolvingAgent:
    """Create agent optimized for genetic evolution."""
    return SelfEvolvingAgent(
        evolution_method=EvolutionMethod.GENETIC_ALGORITHM,
        population_size=population_size
    )


def create_hybrid_agent() -> SelfEvolvingAgent:
    """Create agent using hybrid evolution methods."""
    return SelfEvolvingAgent(
        evolution_method=EvolutionMethod.HYBRID,
        population_size=5
    )


if __name__ == "__main__":
    # Demo execution
    print("=" * 60)
    print("Self-Evolving Agent System Demo")
    print("Based on: arXiv:2601.11658v1 - Pragmatic Self-Evolving Agent")
    print("=" * 60)
    
    # Create hybrid agent
    agent = create_hybrid_agent()
    
    # Create sample tasks
    tasks = [
        TaskInstance(
            task_id="task_1",
            description="Search for information about AGI research",
            difficulty=TaskDifficulty.ELEMENTARY,
            expected_output="research_results",
            tools_required=["search"]
        ),
        TaskInstance(
            task_id="task_2",
            description="Analyze and summarize code performance",
            difficulty=TaskDifficulty.INTERMEDIATE,
            expected_output="analysis_report",
            tools_required=["analyze", "summarize"]
        ),
        TaskInstance(
            task_id="task_3",
            description="Implement new tool for data transformation",
            difficulty=TaskDifficulty.ADVANCED,
            expected_output="working_tool",
            tools_required=["code_gen", "test"]
        )
    ]
    
    # Define available tools
    tools = {
        "search": lambda q: f"Search results for: {q}",
        "analyze": lambda q: f"Analysis of: {q}",
        "summarize": lambda q: f"Summary: {q[:50]}...",
        "code_gen": lambda q: f"Generated code for: {q}",
        "test": lambda q: f"Tests passed for: {q}"
    }
    
    # Execute evolution cycle
    print("\n🧬 Running Evolution Cycle...")
    evolution_result = agent.evolve(tasks, tools)
    
    print(f"\n📊 Evolution Results:")
    print(f"  Generation: {evolution_result['generation']}")
    print(f"  Method: {evolution_result['evolution_method']}")
    print(f"  Cycle Time: {evolution_result['cycle_time']:.2f}s")
    
    # Print detailed improvements
    if "curriculum" in evolution_result.get("improvements", {}):
        curr = evolution_result["improvements"]["curriculum"]
        print(f"\n📚 Curriculum Learning:")
        print(f"  Current Difficulty: {curr.get('current_difficulty') or curr.get('new_difficulty')}")
        print(f"  Rationale: {curr['rationale']}")
    
    # Generate report
    print("\n📈 Evolution Report:")
    report = agent.get_evolution_report()
    print(f"  Total Tasks: {report['execution_stats']['total_tasks']}")
    print(f"  Successful: {report['execution_stats']['successful_tasks']}")
    print(f"  Evolution Cycles: {report['execution_stats']['evolution_cycles']}")
    print(f"  Population Diversity: {report['population_diversity']:.4f}")
    print(f"  Evolved Tools: {report['evolved_tools_count']}")
    
    print("\n🎯 Hierarchical LLM Stats:")
    for llm_name, stats in report["llm_stats"].items():
        print(f"  {llm_name}: {stats}")
    
    print("\n✅ Demo Complete!")
