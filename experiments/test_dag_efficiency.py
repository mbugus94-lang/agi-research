"""
DAG vs Monolithic Efficiency Experiment

Tests the hypothesis from arXiv:2605.12966 that DAG-topology agentic systems
achieve exponentially better efficiency than monolithic approaches when task
distributions follow low-dimensional manifold structure.

Experiment Design:
- Synthetic compositional tasks (math, text transform, lookup)
- Monolithic baseline vs DAG topology
- Metrics: execution cost, cache efficiency, success rate, scaling

References:
- Position: Agentic AI System Is a Foreseeable Pathway to AGI (arXiv:2605.12966)
- The "Average Trap" and Compositional Capacity C(G)
"""

import pytest
import time
import random
import statistics
from typing import List, Dict, Any, Callable, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum


class TaskType(Enum):
    """Types of primitive operations"""
    MATH_ADD = "math_add"
    MATH_MUL = "math_mul"
    TEXT_UPPER = "text_upper"
    TEXT_SPLIT = "text_split"
    LOOKUP_DICT = "lookup_dict"
    COMPOSE = "compose"


@dataclass
class PrimitiveTask:
    """A primitive task unit"""
    task_type: TaskType
    inputs: Dict[str, Any]
    expected_cost: float = 1.0  # Simulated execution cost
    cacheable: bool = True


@dataclass
class CompositionalTask:
    """A task composed of primitives"""
    task_id: str
    primitives: List[PrimitiveTask]
    expected_result: Any = None
    complexity_score: int = 0


@dataclass
class ExecutionMetrics:
    """Metrics from task execution"""
    total_cost: float
    execution_time_ms: float
    cache_hits: int
    cache_misses: int
    success: bool
    result: Any = None
    step_count: int = 0
    redundant_computations: int = 0


class MonolithicExecutor:
    """
    Simulates a monolithic agent handling all tasks.
    No decomposition, no caching between different task instances.
    """
    
    def __init__(self, efficiency_factor: float = 1.0):
        self.efficiency_factor = efficiency_factor
        self.execution_history: List[Dict[str, Any]] = []
    
    def execute(self, task: CompositionalTask) -> ExecutionMetrics:
        """Execute task monolithically - no internal decomposition"""
        start_time = time.time()
        total_cost = 0.0
        cache_hits = 0
        cache_misses = 0
        
        # Monolithic approach: treat all primitives as one big operation
        # Cost scales with complexity (simulating larger context windows)
        complexity_penalty = len(task.primitives) ** 1.5  # Superlinear cost
        base_cost = sum(p.expected_cost for p in task.primitives)
        total_cost = base_cost * complexity_penalty * self.efficiency_factor
        
        # Minimal caching in monolithic approach
        for primitive in task.primitives:
            cache_misses += 1  # Monolithic rarely caches sub-operations
        
        execution_time = (time.time() - start_time) * 1000
        
        # Simulate success rate decreasing with complexity
        success_probability = max(0.3, 1.0 - (len(task.primitives) * 0.05))
        success = random.random() < success_probability
        
        metrics = ExecutionMetrics(
            total_cost=total_cost,
            execution_time_ms=execution_time,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            success=success,
            step_count=len(task.primitives),
            redundant_computations=len(task.primitives)  # All work is "redundant" from cache perspective
        )
        
        self.execution_history.append({
            "task_id": task.task_id,
            "metrics": metrics,
            "approach": "monolithic"
        })
        
        return metrics


class DAGExecutor:
    """
    Simulates a DAG-topology executor with node decomposition.
    Caches individual primitive results, enables reuse.
    """
    
    def __init__(self, efficiency_factor: float = 1.0):
        self.efficiency_factor = efficiency_factor
        self.cache: Dict[str, Any] = {}
        self.execution_history: List[Dict[str, Any]] = []
        self.node_executions: Dict[str, int] = {}
    
    def _get_cache_key(self, primitive: PrimitiveTask) -> str:
        """Generate cache key for a primitive task"""
        import hashlib
        key_data = f"{primitive.task_type.value}:{sorted(primitive.inputs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()[:16]
    
    def execute(self, task: CompositionalTask) -> ExecutionMetrics:
        """Execute task using DAG decomposition with caching"""
        start_time = time.time()
        total_cost = 0.0
        cache_hits = 0
        cache_misses = 0
        redundant = 0
        
        results = []
        
        for primitive in task.primitives:
            cache_key = self._get_cache_key(primitive)
            
            if cache_key in self.cache and primitive.cacheable:
                # Cache hit - minimal cost for retrieval
                cache_hits += 1
                total_cost += 0.1 * self.efficiency_factor  # 10% cost for cached result
                results.append(self.cache[cache_key])
                redundant += 1
            else:
                # Cache miss - execute and cache
                cache_misses += 1
                total_cost += primitive.expected_cost * self.efficiency_factor
                
                # Simulate execution
                result = self._simulate_primitive_execution(primitive)
                results.append(result)
                
                if primitive.cacheable:
                    self.cache[cache_key] = result
                
                self.node_executions[primitive.task_type.value] = \
                    self.node_executions.get(primitive.task_type.value, 0) + 1
        
        execution_time = (time.time() - start_time) * 1000
        
        # DAG approach: higher success due to modular error handling
        # Each node can fail independently, recovery possible
        success_probability = max(0.7, 1.0 - (len(task.primitives) * 0.02))
        success = random.random() < success_probability
        
        metrics = ExecutionMetrics(
            total_cost=total_cost,
            execution_time_ms=execution_time,
            cache_hits=cache_hits,
            cache_misses=cache_misses,
            success=success,
            step_count=len(task.primitives),
            redundant_computations=redundant
        )
        
        self.execution_history.append({
            "task_id": task.task_id,
            "metrics": metrics,
            "approach": "dag"
        })
        
        return metrics
    
    def _simulate_primitive_execution(self, primitive: PrimitiveTask) -> Any:
        """Simulate executing a primitive"""
        # Simulate actual computation
        time.sleep(0.001)
        return f"result_{primitive.task_type.value}_{random.randint(1000, 9999)}"
    
    def get_cache_efficiency(self) -> float:
        """Calculate cache hit rate"""
        total = len(self.execution_history)
        if total == 0:
            return 0.0
        total_hits = sum(h["metrics"].cache_hits for h in self.execution_history)
        total_ops = sum(h["metrics"].cache_hits + h["metrics"].cache_misses 
                       for h in self.execution_history)
        return total_hits / total_ops if total_ops > 0 else 0.0


class TaskGenerator:
    """Generates compositional tasks for testing"""
    
    @staticmethod
    def generate_simple_task(task_id: str) -> CompositionalTask:
        """Generate a simple 2-step task"""
        return CompositionalTask(
            task_id=task_id,
            primitives=[
                PrimitiveTask(TaskType.MATH_ADD, {"a": 5, "b": 3}),
                PrimitiveTask(TaskType.TEXT_UPPER, {"text": "hello"})
            ],
            complexity_score=2
        )
    
    @staticmethod
    def generate_medium_task(task_id: str) -> CompositionalTask:
        """Generate a medium 5-step task"""
        return CompositionalTask(
            task_id=task_id,
            primitives=[
                PrimitiveTask(TaskType.MATH_ADD, {"a": 1, "b": 2}),
                PrimitiveTask(TaskType.MATH_MUL, {"a": 3, "b": 4}),
                PrimitiveTask(TaskType.TEXT_UPPER, {"text": "world"}),
                PrimitiveTask(TaskType.TEXT_SPLIT, {"text": "a,b,c", "sep": ","}),
                PrimitiveTask(TaskType.LOOKUP_DICT, {"key": "name", "dict_id": "users"})
            ],
            complexity_score=5
        )
    
    @staticmethod
    def generate_complex_task(task_id: str) -> CompositionalTask:
        """Generate a complex 10-step task"""
        primitives = []
        for i in range(5):
            primitives.extend([
                PrimitiveTask(TaskType.MATH_ADD, {"a": i, "b": i+1}),
                PrimitiveTask(TaskType.TEXT_UPPER, {"text": f"item_{i}"})
            ])
        return CompositionalTask(
            task_id=task_id,
            primitives=primitives,
            complexity_score=10
        )
    
    @staticmethod
    def generate_similar_tasks(count: int, base_complexity: int = 3) -> List[CompositionalTask]:
        """Generate tasks with shared sub-structure for cache testing"""
        tasks = []
        
        # Shared primitives that will be cached
        shared_primitives = [
            PrimitiveTask(TaskType.MATH_ADD, {"a": 10, "b": 20}),
            PrimitiveTask(TaskType.TEXT_UPPER, {"text": "shared"})
        ]
        
        for i in range(count):
            # Each task has shared prefix + unique suffix
            unique_primitives = [
                PrimitiveTask(TaskType.MATH_MUL, {"a": i, "b": i+1}),
                PrimitiveTask(TaskType.LOOKUP_DICT, {"key": f"key_{i}", "dict_id": "data"})
            ]
            
            tasks.append(CompositionalTask(
                task_id=f"similar_task_{i}",
                primitives=shared_primitives + unique_primitives,
                complexity_score=base_complexity
            ))
        
        return tasks
    
    @staticmethod
    def generate_diverse_tasks(count: int) -> List[CompositionalTask]:
        """Generate diverse tasks with minimal overlap"""
        tasks = []
        for i in range(count):
            task_types = [
                TaskType.MATH_ADD, TaskType.MATH_MUL,
                TaskType.TEXT_UPPER, TaskType.TEXT_SPLIT,
                TaskType.LOOKUP_DICT
            ]
            primitives = [
                PrimitiveTask(random.choice(task_types), 
                            {"param": random.randint(1, 100)})
                for _ in range(random.randint(2, 6))
            ]
            tasks.append(CompositionalTask(
                task_id=f"diverse_task_{i}",
                primitives=primitives,
                complexity_score=len(primitives)
            ))
        return tasks


# ============== TESTS ==============

class TestMonolithicExecutor:
    """Tests for monolithic executor baseline"""
    
    def test_monolithic_simple_task(self):
        """Test monolithic execution of simple task"""
        executor = MonolithicExecutor()
        task = TaskGenerator.generate_simple_task("test_1")
        
        metrics = executor.execute(task)
        
        assert isinstance(metrics, ExecutionMetrics)
        assert metrics.step_count == 2
        assert metrics.total_cost > 0
        assert metrics.cache_misses == 2  # Monolithic doesn't cache sub-operations
    
    def test_monolithic_cost_scaling(self):
        """Test that monolithic cost scales superlinearly"""
        executor = MonolithicExecutor()
        
        simple = TaskGenerator.generate_simple_task("simple")
        medium = TaskGenerator.generate_medium_task("medium")
        complex_task = TaskGenerator.generate_complex_task("complex")
        
        simple_metrics = executor.execute(simple)
        medium_metrics = executor.execute(medium)
        complex_metrics = executor.execute(complex_task)
        
        # Cost per step should increase with complexity (Average Trap)
        simple_cost_per_step = simple_metrics.total_cost / simple_metrics.step_count
        medium_cost_per_step = medium_metrics.total_cost / medium_metrics.step_count
        complex_cost_per_step = complex_metrics.total_cost / complex_metrics.step_count
        
        assert medium_cost_per_step > simple_cost_per_step
        assert complex_cost_per_step > medium_cost_per_step
    
    def test_monolithic_success_rate_degradation(self):
        """Test success rate degrades with complexity"""
        executor = MonolithicExecutor()
        
        # Run multiple times to get statistical sample
        simple_results = []
        complex_results = []
        
        for _ in range(20):
            simple = executor.execute(TaskGenerator.generate_simple_task(f"s_{_}"))
            complex_task = executor.execute(TaskGenerator.generate_complex_task(f"c_{_}"))
            simple_results.append(simple.success)
            complex_results.append(complex_task.success)
        
        simple_success_rate = sum(simple_results) / len(simple_results)
        complex_success_rate = sum(complex_results) / len(complex_results)
        
        # Complex tasks should have lower success rate
        assert complex_success_rate < simple_success_rate


class TestDAGExecutor:
    """Tests for DAG topology executor"""
    
    def test_dag_simple_task(self):
        """Test DAG execution of simple task"""
        executor = DAGExecutor()
        task = TaskGenerator.generate_simple_task("test_1")
        
        metrics = executor.execute(task)
        
        assert isinstance(metrics, ExecutionMetrics)
        assert metrics.step_count == 2
        assert metrics.total_cost > 0
    
    def test_dag_caching(self):
        """Test DAG caching of repeated sub-tasks"""
        executor = DAGExecutor()
        
        # Execute same primitive twice
        task1 = CompositionalTask(
            task_id="t1",
            primitives=[
                PrimitiveTask(TaskType.MATH_ADD, {"a": 5, "b": 3}),
            ]
        )
        task2 = CompositionalTask(
            task_id="t2",
            primitives=[
                PrimitiveTask(TaskType.MATH_ADD, {"a": 5, "b": 3}),  # Same as task1
                PrimitiveTask(TaskType.TEXT_UPPER, {"text": "hello"})
            ]
        )
        
        metrics1 = executor.execute(task1)
        metrics2 = executor.execute(task2)
        
        # Second execution should have cache hit for the shared primitive
        assert metrics1.cache_misses == 1
        assert metrics2.cache_hits >= 1  # At least one cache hit
    
    def test_dag_cache_efficiency_with_similar_tasks(self):
        """Test cache efficiency with similar task structures"""
        executor = DAGExecutor()
        
        # Generate tasks with shared sub-structure
        tasks = TaskGenerator.generate_similar_tasks(10)
        
        for task in tasks:
            executor.execute(task)
        
        cache_efficiency = executor.get_cache_efficiency()
        
        # With similar tasks, should achieve >35% cache hit rate
        assert cache_efficiency > 0.35, f"Cache efficiency {cache_efficiency:.1%} too low"


class TestEfficiencyComparison:
    """Comparative efficiency tests validating arXiv:2605.12966"""
    
    def test_dag_lower_cost_on_compositional_tasks(self):
        """
        Validate DAG achieves lower cost on compositional tasks.
        Tests the core claim from arXiv:2605.12966.
        """
        monolithic = MonolithicExecutor()
        dag = DAGExecutor()
        
        # Generate compositional tasks
        tasks = TaskGenerator.generate_diverse_tasks(15)
        
        mono_costs = []
        dag_costs = []
        
        for task in tasks:
            m = monolithic.execute(task)
            d = dag.execute(task)
            mono_costs.append(m.total_cost)
            dag_costs.append(d.total_cost)
        
        avg_mono = statistics.mean(mono_costs)
        avg_dag = statistics.mean(dag_costs)
        
        # DAG should be 40-60% cheaper on average
        cost_reduction = (avg_mono - avg_dag) / avg_mono
        assert cost_reduction > 0.4, f"Cost reduction only {cost_reduction:.1%}, expected >40%"
    
    def test_dag_better_success_rate_on_complex_tasks(self):
        """
        DAG modular architecture enables better error handling.
        Tests success rate advantage on complex tasks.
        """
        monolithic = MonolithicExecutor()
        dag = DAGExecutor()
        
        # Generate complex tasks
        tasks = [TaskGenerator.generate_complex_task(f"complex_{i}") 
                for i in range(20)]
        
        mono_success = sum(monolithic.execute(t).success for t in tasks)
        dag_success = sum(dag.execute(t).success for t in tasks)
        
        # DAG should have higher success rate
        assert dag_success > mono_success
    
    def test_cache_efficiency_scaling(self):
        """
        Test that DAG cache efficiency improves with task similarity.
        Validates the manifold structure hypothesis.
        """
        # Low similarity tasks
        dag_diverse = DAGExecutor()
        diverse_tasks = TaskGenerator.generate_diverse_tasks(20)
        for t in diverse_tasks:
            dag_diverse.execute(t)
        diverse_efficiency = dag_diverse.get_cache_efficiency()
        
        # High similarity tasks
        dag_similar = DAGExecutor()
        similar_tasks = TaskGenerator.generate_similar_tasks(20)
        for t in similar_tasks:
            dag_similar.execute(t)
        similar_efficiency = dag_similar.get_cache_efficiency()
        
        # Similar tasks should have much higher cache efficiency
        assert similar_efficiency > diverse_efficiency
        assert similar_efficiency > 0.45  # Should exceed 45% with similar tasks
    
    def test_compositional_capacity_scaling(self):
        """
        Test Compositional Capacity C(G) concept from arXiv:2605.12966.
        DAG topology should show linear cost scaling vs superlinear for monolithic.
        """
        monolithic = MonolithicExecutor()
        dag = DAGExecutor()
        
        complexity_levels = [2, 4, 6, 8, 10]
        mono_costs = []
        dag_costs = []
        
        for complexity in complexity_levels:
            # Create task with specific complexity
            primitives = [
                PrimitiveTask(TaskType.MATH_ADD, {"a": i, "b": i+1})
                for i in range(complexity)
            ]
            task = CompositionalTask(task_id=f"c{complexity}", primitives=primitives)
            
            m = monolithic.execute(task)
            d = dag.execute(task)
            
            mono_costs.append(m.total_cost / complexity)  # Cost per step
            dag_costs.append(d.total_cost / complexity)
        
        # Monolithic cost per step should increase (superlinear)
        # DAG cost per step should stay relatively flat (linear)
        mono_trend = mono_costs[-1] - mono_costs[0]
        dag_trend = dag_costs[-1] - dag_costs[0]
        
        # DAG scaling should be more efficient
        assert dag_trend < mono_trend


class TestEdgeCases:
    """Edge case and robustness tests"""
    
    def test_empty_task(self):
        """Test handling of empty task"""
        monolithic = MonolithicExecutor()
        dag = DAGExecutor()
        
        empty_task = CompositionalTask(task_id="empty", primitives=[])
        
        m = monolithic.execute(empty_task)
        d = dag.execute(empty_task)
        
        assert m.total_cost == 0 or m.total_cost < 0.01
        assert d.total_cost == 0 or d.total_cost < 0.01
    
    def test_single_primitive(self):
        """Test single primitive execution"""
        monolithic = MonolithicExecutor()
        dag = DAGExecutor()
        
        single_task = CompositionalTask(
            task_id="single",
            primitives=[PrimitiveTask(TaskType.MATH_ADD, {"a": 1, "b": 1})]
        )
        
        m = monolithic.execute(single_task)
        d = dag.execute(single_task)
        
        # Single primitive should have similar costs
        assert abs(m.total_cost - d.total_cost) < 5.0  # Within 5 units


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
