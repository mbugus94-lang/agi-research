"""
Test Suite for Self-Evolving Agent System

Validates the hierarchical LLM architecture and evolution methods:
- Base LLM: Core reasoning and task understanding
- Operational SLM: Fast, efficient task execution
- Code-Gen LLM: Code generation and tool synthesis
- Teacher LLM: Evaluation, feedback, and curriculum generation

Evolution methods tested:
- Curriculum Learning
- Reinforcement Learning
- Genetic Algorithm
- Hybrid Evolution
"""

import unittest
import time
from typing import Dict, Any, List

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.self_evolving_agent import (
    SelfEvolvingAgent, BaseLLM, OperationalSLM, CodeGenLLM, TeacherLLM,
    TaskInstance, TaskDifficulty, EvolutionMethod, EvaluationResult,
    ToolUseTrace, create_curriculum_agent, create_rl_agent, 
    create_genetic_agent, create_hybrid_agent
)


class TestBaseLLM(unittest.TestCase):
    """Test Base LLM - Core reasoning and task understanding."""
    
    def setUp(self):
        self.base_llm = BaseLLM()
        self.sample_task = TaskInstance(
            task_id="test_task",
            description="Implement a Python function to sort a list",
            difficulty=TaskDifficulty.INTERMEDIATE,
            expected_output="sorted_list",
            tools_required=["code_gen", "test"]
        )
    
    def test_task_understanding(self):
        """Test task understanding and analysis."""
        understanding = self.base_llm.understand_task(self.sample_task)
        
        self.assertIn("task_type", understanding)
        self.assertIn("complexity_score", understanding)
        self.assertIn("required_capabilities", understanding)
        self.assertIn("decomposition", understanding)
        self.assertEqual(understanding["task_type"], "coding")
        self.assertEqual(understanding["estimated_difficulty"], 2)
    
    def test_complexity_calculation(self):
        """Test complexity score computation."""
        complexity = self.base_llm._compute_complexity(self.sample_task)
        self.assertGreaterEqual(complexity, 0.0)
        self.assertLessEqual(complexity, 1.0)
        
        # More tools = higher complexity
        task_with_more_tools = TaskInstance(
            task_id="complex_task",
            description="Analyze and generate report",
            difficulty=TaskDifficulty.ADVANCED,
            expected_output="report",
            tools_required=["search", "analyze", "summarize", "visualize", "format"]
        )
        complex_complexity = self.base_llm._compute_complexity(task_with_more_tools)
        self.assertGreater(complex_complexity, complexity)
    
    def test_task_classification(self):
        """Test task classification by type."""
        tasks = [
            ("Implement a function", "coding"),
            ("Analyze data patterns", "analysis"),
            ("Search for research papers", "information_retrieval"),
            ("Create a schedule", "planning"),
            ("Do something", "general")
        ]
        
        for desc, expected_type in tasks:
            task = TaskInstance(
                task_id="classify_test",
                description=desc,
                difficulty=TaskDifficulty.ELEMENTARY,
                expected_output="output",
                tools_required=[]
            )
            task_type = self.base_llm._classify_task(task)
            self.assertEqual(task_type, expected_type)
    
    def test_task_decomposition(self):
        """Test hierarchical task decomposition."""
        decomp = self.base_llm._decompose_task(self.sample_task)
        self.assertIsInstance(decomp, list)
        self.assertGreater(len(decomp), 0)
        
        # Simple tasks have fewer steps
        simple_task = TaskInstance(
            task_id="simple",
            description="Add two numbers",
            difficulty=TaskDifficulty.ELEMENTARY,
            expected_output="sum",
            tools_required=[]
        )
        simple_decomp = self.base_llm._decompose_task(simple_task)
        self.assertEqual(len(simple_decomp), 1)
    
    def test_constraint_extraction(self):
        """Test constraint extraction from task descriptions."""
        constrained_task = TaskInstance(
            task_id="constrained",
            description="Must implement exactly as specified within 5 minutes",
            difficulty=TaskDifficulty.ADVANCED,
            expected_output="result",
            tools_required=[]
        )
        constraints = self.base_llm._extract_constraints(constrained_task)
        self.assertIn("hard_requirement", constraints)
        self.assertIn("time_bound", constraints)
    
    def test_cache_reuse(self):
        """Test task understanding caching."""
        u1 = self.base_llm.understand_task(self.sample_task)
        u2 = self.base_llm.understand_task(self.sample_task)
        # Should return same cached result
        self.assertEqual(u1, u2)


class TestOperationalSLM(unittest.TestCase):
    """Test Operational SLM - Fast task execution."""
    
    def setUp(self):
        self.slm = OperationalSLM()
        self.tools = {
            "test_tool": lambda x: f"Result: {x}",
            "fail_tool": lambda x: (_ for _ in ()).throw(Exception("Tool failed"))
        }
    
    def test_basic_execution(self):
        """Test basic task execution."""
        task = TaskInstance(
            task_id="exec_test",
            description="Test execution",
            difficulty=TaskDifficulty.ELEMENTARY,
            expected_output="result",
            tools_required=["test_tool"]
        )
        
        result, traces = self.slm.execute(task, {"task_type": "general"}, self.tools)
        
        self.assertIn("test_tool", result)
        self.assertEqual(len(traces), 1)
        self.assertTrue(traces[0].success)
        self.assertEqual(traces[0].tool_name, "test_tool")
    
    def test_caching(self):
        """Test execution result caching."""
        task = TaskInstance(
            task_id="cache_test",
            description="Cacheable task",
            difficulty=TaskDifficulty.ELEMENTARY,
            expected_output="cached",
            tools_required=[]
        )
        
        # First execution
        r1, _ = self.slm.execute(task, {"task_type": "general"}, self.tools)
        # Second execution should use cache
        r2, _ = self.slm.execute(task, {"task_type": "general"}, self.tools)
        
        # Should be cached
        self.assertEqual(self.slm.get_performance_stats()["cache_size"], 1)
    
    def test_tool_failure_handling(self):
        """Test handling of tool failures."""
        task = TaskInstance(
            task_id="fail_test",
            description="Test with failing tool",
            difficulty=TaskDifficulty.ELEMENTARY,
            expected_output="result",
            tools_required=["fail_tool"]
        )
        
        result, traces = self.slm.execute(task, {"task_type": "general"}, self.tools)
        
        self.assertEqual(len(traces), 1)
        self.assertFalse(traces[0].success)
        self.assertIn("fail_tool_error", result)
    
    def test_pattern_registration(self):
        """Test custom execution pattern registration."""
        custom_pattern = lambda t, tools: {"custom": True, "task": t.description}
        self.slm.register_pattern("custom_type", custom_pattern)
        
        task = TaskInstance(
            task_id="pattern_test",
            description="Use pattern",
            difficulty=TaskDifficulty.ELEMENTARY,
            expected_output="output",
            tools_required=[]
        )
        
        result, _ = self.slm.execute(task, {"task_type": "custom_type"}, {})
        self.assertTrue(result["custom"])
    
    def test_performance_stats(self):
        """Test performance statistics tracking."""
        stats = self.slm.get_performance_stats()
        self.assertIn("cache_size", stats)
        self.assertIn("pattern_count", stats)
        self.assertIn("target_response_time", stats)


class TestCodeGenLLM(unittest.TestCase):
    """Test Code-Gen LLM - Tool synthesis."""
    
    def setUp(self):
        self.codegen = CodeGenLLM()
    
    def test_tool_synthesis(self):
        """Test tool generation from requirements."""
        requirement = "Create a tool to parse JSON and extract nested values"
        
        tool_spec = self.codegen.synthesize_tool(requirement)
        
        self.assertIn("tool_id", tool_spec)
        self.assertIn("name", tool_spec)
        self.assertIn("description", tool_spec)
        self.assertIn("parameters", tool_spec)
        self.assertIn("implementation", tool_spec)
        self.assertEqual(tool_spec["version"], 1)
    
    def test_tool_name_generation(self):
        """Test automatic tool name generation."""
        name1 = self.codegen._generate_tool_name("Parse JSON data files")
        name2 = self.codegen._generate_tool_name("Transform XML to CSV format")
        
        self.assertTrue(name1.startswith("tool_"))
        self.assertTrue(name2.startswith("tool_"))
        self.assertNotEqual(name1, name2)
    
    def test_synthesis_history(self):
        """Test synthesis history tracking."""
        initial_count = len(self.codegen.synthesis_history)
        
        self.codegen.synthesize_tool("Tool A")
        self.codegen.synthesize_tool("Tool B")
        
        self.assertEqual(len(self.codegen.synthesis_history), initial_count + 2)
    
    def test_synthesis_stats(self):
        """Test synthesis statistics."""
        # Generate some tools
        for i in range(3):
            self.codegen.synthesize_tool(f"Tool requirement {i}")
        
        stats = self.codegen.get_synthesis_stats()
        self.assertIn("total_tools", stats)
        self.assertIn("total_modifications", stats)
        self.assertIn("synthesis_attempts", stats)
        
        self.assertGreaterEqual(stats["total_tools"], 3)


class TestTeacherLLM(unittest.TestCase):
    """Test Teacher LLM - Evaluation and feedback."""
    
    def setUp(self):
        self.teacher = TeacherLLM()
        self.task = TaskInstance(
            task_id="eval_test",
            description="Test evaluation task",
            difficulty=TaskDifficulty.INTERMEDIATE,
            expected_output="correct_output",
            tools_required=["tool1", "tool2"]
        )
    
    def test_perfect_evaluation(self):
        """Test evaluation with perfect result."""
        traces = [
            ToolUseTrace("tool1", {}, "result1", True, 0.5),
            ToolUseTrace("tool2", {}, "result2", True, 0.5)
        ]
        
        result = self.teacher.evaluate(
            self.task, "correct_output", traces, attempts=1
        )
        
        self.assertTrue(result.success)
        self.assertGreaterEqual(result.score, 0.9)
        self.assertEqual(result.attempts, 1)
        self.assertIn("Excellent", result.teacher_feedback)
    
    def test_failed_evaluation(self):
        """Test evaluation with incorrect result."""
        traces = [
            ToolUseTrace("tool1", {}, "result1", False, 1.0)
        ]
        
        result = self.teacher.evaluate(
            self.task, "wrong_output", traces, attempts=3
        )
        
        self.assertFalse(result.success)
        self.assertLess(result.score, 0.5)
        self.assertEqual(result.attempts, 3)
        self.assertIn("Needs improvement", result.teacher_feedback)
    
    def test_improvement_suggestions(self):
        """Test generation of improvement suggestions."""
        traces = [
            ToolUseTrace("failing_tool", {}, None, False, 2.0),
            ToolUseTrace("failing_tool", {}, None, False, 2.0),
        ]
        
        result = self.teacher.evaluate(
            self.task, "output", traces, attempts=2
        )
        
        self.assertGreater(len(result.improvement_suggestions), 0)
        # Should suggest improving the failing tool
        suggestions_text = " ".join(result.improvement_suggestions)
        self.assertIn("failing_tool", suggestions_text)
    
    def test_curriculum_generation(self):
        """Test curriculum task generation."""
        # Use high performance to trigger difficulty advancement
        performance_history = [0.96, 0.97, 0.98, 0.95, 0.99]  # Above 0.95 threshold
        
        curriculum = self.teacher.generate_curriculum(
            TaskDifficulty.ELEMENTARY, performance_history
        )
        
        self.assertEqual(len(curriculum), 5)  # 5 tasks per stage
        
        # With excellent performance, should advance difficulty
        avg = sum(performance_history) / len(performance_history)
        if avg > 0.95:  # excellence threshold
            self.assertGreater(curriculum[0].difficulty.value, 1)
    
    def test_evaluation_stats(self):
        """Test evaluation statistics tracking."""
        # Perform some evaluations
        for i in range(5):
            traces = [ToolUseTrace("t", {}, "o", True, 0.2)]
            self.teacher.evaluate(
                self.task, "correct_output", traces, attempts=1
            )
        
        stats = self.teacher.get_evaluation_stats()
        self.assertIn("evaluations", stats)
        self.assertIn("average_score", stats)
        self.assertIn("success_rate", stats)
        self.assertGreaterEqual(stats["evaluations"], 5)


class TestEvolutionMethods(unittest.TestCase):
    """Test different evolution methods."""
    
    def setUp(self):
        self.tools = {
            "search": lambda q: {"results": [f"Result for {q}"]},
            "analyze": lambda q: {"analysis": f"Analysis of {q}"},
            "test_tool": lambda q: {"test": "passed"}
        }
    
    def test_curriculum_agent_creation(self):
        """Test curriculum learning agent creation."""
        agent = create_curriculum_agent()
        self.assertEqual(agent.evolution_method, EvolutionMethod.CURRICULUM_LEARNING)
        self.assertEqual(agent.current_difficulty, TaskDifficulty.ELEMENTARY)
    
    def test_rl_agent_creation(self):
        """Test RL agent creation."""
        agent = create_rl_agent()
        self.assertEqual(agent.evolution_method, EvolutionMethod.REINFORCEMENT_LEARNING)
    
    def test_genetic_agent_creation(self):
        """Test genetic algorithm agent creation."""
        agent = create_genetic_agent(population_size=10)
        self.assertEqual(agent.evolution_method, EvolutionMethod.GENETIC_ALGORITHM)
        self.assertEqual(len(agent.population), 10)
    
    def test_hybrid_agent_creation(self):
        """Test hybrid evolution agent creation."""
        agent = create_hybrid_agent()
        self.assertEqual(agent.evolution_method, EvolutionMethod.HYBRID)
    
    def test_evolution_cycle(self):
        """Test full evolution cycle execution."""
        agent = create_hybrid_agent()
        
        tasks = [
            TaskInstance(
                task_id=f"evo_task_{i}",
                description=f"Task {i}",
                difficulty=TaskDifficulty.ELEMENTARY if i < 3 else TaskDifficulty.INTERMEDIATE,
                expected_output=f"output_{i}",
                tools_required=["test_tool"]
            )
            for i in range(5)
        ]
        
        result = agent.evolve(tasks, self.tools)
        
        self.assertIn("generation", result)
        self.assertIn("evolution_method", result)
        self.assertIn("results", result)
        self.assertEqual(result["evolution_method"], "HYBRID")
        self.assertEqual(len(result["results"]), 5)
        
        # Check metrics
        self.assertIn("total_score", result)
        self.assertIn("avg_score", result)
        self.assertIn("success_rate", result)
    
    def test_curriculum_progression(self):
        """Test curriculum difficulty progression."""
        agent = create_curriculum_agent()
        
        # Start at elementary
        self.assertEqual(agent.current_difficulty, TaskDifficulty.ELEMENTARY)
        
        # Simulate excellent performance
        high_scores = [0.95, 0.97, 0.96, 0.98, 0.94]
        agent.performance_history = high_scores
        
        # Trigger curriculum evolution
        tasks = [
            TaskInstance(
                task_id="prog_test",
                description="Progression test",
                difficulty=agent.current_difficulty,
                expected_output="out",
                tools_required=["test_tool"]
            )
        ]
        
        result = agent.evolve(tasks, self.tools)
        
        # Should advance difficulty
        improvements = result.get("improvements", {})
        if "curriculum" in improvements:
            curr = improvements["curriculum"]
            # With high scores, should advance
            self.assertEqual(curr["method"], "curriculum_learning")
    
    def test_checkpoint_creation(self):
        """Test evolution checkpoint creation."""
        agent = create_hybrid_agent()
        
        tasks = [
            TaskInstance(
                task_id="ckpt_test",
                description="Checkpoint test",
                difficulty=TaskDifficulty.ELEMENTARY,
                expected_output="out",
                tools_required=["test_tool"]
            )
        ]
        
        agent.evolve(tasks, self.tools)
        
        # Should have created checkpoints
        self.assertGreater(len(agent.checkpoints), 0)
        
        checkpoint = agent.checkpoints[0]
        self.assertEqual(checkpoint.generation, 1)
        self.assertIn("performance_metrics", checkpoint.__dict__ or vars(checkpoint))


class TestSelfEvolvingAgentIntegration(unittest.TestCase):
    """Integration tests for the complete self-evolving agent."""
    
    def setUp(self):
        self.agent = create_hybrid_agent()
        self.tools = {
            "search": lambda q: {"data": f"Search: {q}"},
            "analyze": lambda q: {"analysis": f"Analysis: {q}"},
            "code_gen": lambda q: {"code": f"Code for: {q}"},
            "test": lambda q: {"test": "passed"}
        }
    
    def test_full_workflow(self):
        """Test complete agent workflow with all LLM modules."""
        # Create diverse tasks
        tasks = [
            TaskInstance(
                task_id="wf_1",
                description="Search for AGI research papers",
                difficulty=TaskDifficulty.ELEMENTARY,
                expected_output="papers",
                tools_required=["search"]
            ),
            TaskInstance(
                task_id="wf_2",
                description="Analyze code performance patterns",
                difficulty=TaskDifficulty.INTERMEDIATE,
                expected_output="patterns",
                tools_required=["analyze"]
            ),
            TaskInstance(
                task_id="wf_3",
                description="Implement sorting algorithm",
                difficulty=TaskDifficulty.ADVANCED,
                expected_output="code",
                tools_required=["code_gen", "test"]
            )
        ]
        
        # Run multiple evolution cycles
        for cycle in range(3):
            result = self.agent.evolve(tasks, self.tools)
            
            self.assertIn("results", result)
            self.assertEqual(len(result["results"]), 3)
            
            # All results should have evaluations
            for eval_result in result["results"]:
                self.assertIsInstance(eval_result, EvaluationResult)
                self.assertIn(eval_result.task_id, [t.task_id for t in tasks])
    
    def test_evolution_report(self):
        """Test comprehensive evolution reporting."""
        # Run some evolution cycles
        tasks = [
            TaskInstance(
                task_id="report_test",
                description="Report test task",
                difficulty=TaskDifficulty.ELEMENTARY,
                expected_output="out",
                tools_required=["test"]
            )
        ]
        
        for _ in range(2):
            self.agent.evolve(tasks, self.tools)
        
        report = self.agent.get_evolution_report()
        
        # Check all expected fields
        self.assertIn("generation", report)
        self.assertIn("evolution_method", report)
        self.assertIn("current_difficulty", report)
        self.assertIn("execution_stats", report)
        self.assertIn("population_diversity", report)
        self.assertIn("evolved_tools_count", report)
        self.assertIn("checkpoints", report)
        self.assertIn("llm_stats", report)
        self.assertIn("recent_performance", report)
        
        # Validate types
        self.assertIsInstance(report["generation"], int)
        self.assertIsInstance(report["evolved_tools_count"], int)
        self.assertIsInstance(report["population_diversity"], float)
    
    def test_multi_generation_evolution(self):
        """Test evolution across multiple generations."""
        agent = create_genetic_agent(population_size=5)
        
        tasks = [
            TaskInstance(
                task_id="gen_test",
                description="Generation test",
                difficulty=TaskDifficulty.ELEMENTARY,
                expected_output="out",
                tools_required=["test"]
            )
        ]
        
        initial_generation = agent.generation
        
        # Run multiple generations
        for _ in range(3):
            agent.evolve(tasks, self.tools)
        
        # Generation should advance
        self.assertGreater(agent.generation, initial_generation)
        
        # Population should be maintained
        self.assertEqual(len(agent.population), 5)
    
    def test_performance_history_tracking(self):
        """Test performance history accumulation."""
        tasks = [
            TaskInstance(
                task_id="hist_test",
                description="History tracking",
                difficulty=TaskDifficulty.ELEMENTARY,
                expected_output="out",
                tools_required=["test"]
            )
        ]
        
        initial_len = len(self.agent.performance_history)
        
        self.agent.evolve(tasks, self.tools)
        
        # Should have added to performance history
        self.assertGreater(len(self.agent.performance_history), initial_len)
    
    def test_tool_synthesis_integration(self):
        """Test that tool synthesis is tracked during evolution."""
        # Create task that triggers code generation
        tasks = [
            TaskInstance(
                task_id="synth_int",
                description="Generate data parser tool",
                difficulty=TaskDifficulty.ADVANCED,
                expected_output="tool",
                tools_required=["code_gen"]
            )
        ]
        
        initial_tools = len(self.agent.evolved_tools)
        
        # Note: Actual synthesis would require more complex tool
        # This tests that the structure is in place
        self.agent.evolve(tasks, self.tools)
        
        # Code gen LLM should have history
        self.assertGreater(len(self.agent.code_gen_llm.synthesis_history), 0)


class TestDifferentTaskDifficulties(unittest.TestCase):
    """Test agent behavior with different difficulty levels."""
    
    def setUp(self):
        self.agent = create_hybrid_agent()
        self.tools = {"test": lambda x: {"result": x}}
    
    def test_elementary_tasks(self):
        """Test elementary difficulty tasks."""
        task = TaskInstance(
            task_id="elem",
            description="Simple task",
            difficulty=TaskDifficulty.ELEMENTARY,
            expected_output="simple",
            tools_required=["test"]
        )
        
        result = self.agent.evolve([task], self.tools)
        self.assertEqual(len(result["results"]), 1)
        # Elementary tasks should succeed easily
        self.assertTrue(result["results"][0].success)
    
    def test_expert_tasks(self):
        """Test expert difficulty tasks."""
        task = TaskInstance(
            task_id="expert",
            description="Complex expert task",
            difficulty=TaskDifficulty.EXPERT,
            expected_output="complex",
            tools_required=["test", "test", "test", "test", "test"]
        )
        
        result = self.agent.evolve([task], self.tools)
        self.assertEqual(len(result["results"]), 1)
        # Score should reflect difficulty
        self.assertLessEqual(result["results"][0].score, 1.0)
    
    def test_research_tasks(self):
        """Test research difficulty tasks (highest)."""
        task = TaskInstance(
            task_id="research",
            description="Novel research task",
            difficulty=TaskDifficulty.RESEARCH,
            expected_output="breakthrough",
            tools_required=["test"] * 10
        )
        
        # Base LLM should classify this appropriately
        understanding = self.agent.base_llm.understand_task(task)
        self.assertEqual(understanding["estimated_difficulty"], 5)


if __name__ == "__main__":
    # Run tests with verbosity
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("=" * 60)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
