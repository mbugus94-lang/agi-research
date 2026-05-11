"""
Test suite for Learning from Demonstration (LfD) module.

Tests all major components:
- DemonstrationRecorder
- PatternExtractor
- SkillSynthesizer
- TransferLearning
"""

import unittest
import tempfile
import shutil
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from skills.learning_from_demonstration import (
    DemonstrationRecorder, PatternExtractor, SkillSynthesizer, TransferLearning,
    Demonstration, ActionStep, ExtractedPattern, LearnedSkill,
    DemonstrationType, SkillType, PatternType,
    create_lfd_system
)


class TestActionStep(unittest.TestCase):
    """Test ActionStep data class."""
    
    def test_create_action_step(self):
        step = ActionStep(
            action_type="tool_call",
            tool_name="search",
            parameters={"query": "test"},
            success=True
        )
        self.assertEqual(step.action_type, "tool_call")
        self.assertEqual(step.tool_name, "search")
        self.assertEqual(step.parameters["query"], "test")
        self.assertTrue(step.success)
        self.assertIsNotNone(step.step_id)
    
    def test_action_step_to_dict(self):
        step = ActionStep(
            action_type="reasoning",
            parameters={"thought": "analyze"},
            duration_ms=100.5
        )
        d = step.to_dict()
        self.assertEqual(d["action_type"], "reasoning")
        self.assertEqual(d["parameters"]["thought"], "analyze")
        self.assertEqual(d["duration_ms"], 100.5)
    
    def test_action_step_from_dict(self):
        data = {
            "step_id": "abc123",
            "action_type": "decision",
            "tool_name": None,
            "parameters": {"choice": "option_a"},
            "pre_state": {},
            "post_state": {"result": "success"},
            "timestamp": "2026-05-11T10:00:00",
            "duration_ms": 50.0,
            "success": True,
            "notes": "test note"
        }
        step = ActionStep.from_dict(data)
        self.assertEqual(step.step_id, "abc123")
        self.assertEqual(step.action_type, "decision")
        self.assertEqual(step.parameters["choice"], "option_a")


class TestDemonstration(unittest.TestCase):
    """Test Demonstration data class."""
    
    def test_create_demonstration(self):
        demo = Demonstration(
            task_description="Search for information",
            goal="Find relevant results",
            demo_type=DemonstrationType.TASK_EXECUTION,
            tags=["search", "information"]
        )
        self.assertEqual(demo.task_description, "Search for information")
        self.assertEqual(demo.goal, "Find relevant results")
        self.assertEqual(demo.demo_type, DemonstrationType.TASK_EXECUTION)
        self.assertEqual(demo.tags, ["search", "information"])
        self.assertIsNotNone(demo.demo_id)
    
    def test_add_step(self):
        demo = Demonstration(task_description="Test task")
        step = ActionStep(action_type="tool_call", tool_name="calculator")
        demo.add_step(step)
        self.assertEqual(len(demo.steps), 1)
        self.assertEqual(demo.steps[0].tool_name, "calculator")
    
    def test_get_duration(self):
        demo = Demonstration(task_description="Test")
        demo.add_step(ActionStep(duration_ms=100.0))
        demo.add_step(ActionStep(duration_ms=200.0))
        demo.add_step(ActionStep(duration_ms=50.0))
        self.assertEqual(demo.get_duration_ms(), 350.0)
    
    def test_get_tools_used(self):
        demo = Demonstration(task_description="Test")
        demo.add_step(ActionStep(tool_name="search"))
        demo.add_step(ActionStep(tool_name="calculator"))
        demo.add_step(ActionStep(tool_name="search"))  # Duplicate
        tools = demo.get_tools_used()
        self.assertEqual(tools, {"search", "calculator"})
    
    def test_demonstration_roundtrip(self):
        demo = Demonstration(
            task_description="Complex task",
            goal="Achieve result",
            demo_type=DemonstrationType.TOOL_USAGE,
            tags=["test"]
        )
        demo.add_step(ActionStep(action_type="start"))
        demo.add_step(ActionStep(action_type="process", success=True))
        
        data = demo.to_dict()
        restored = Demonstration.from_dict(data)
        
        self.assertEqual(restored.task_description, demo.task_description)
        self.assertEqual(restored.goal, demo.goal)
        self.assertEqual(restored.demo_type, demo.demo_type)
        self.assertEqual(len(restored.steps), len(demo.steps))


class TestDemonstrationRecorder(unittest.TestCase):
    """Test DemonstrationRecorder class."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.recorder = DemonstrationRecorder(storage_path=self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_start_recording(self):
        demo_id = self.recorder.start_recording(
            task_description="Test task",
            goal="Test goal",
            tags=["test"]
        )
        self.assertIsNotNone(demo_id)
        self.assertIn(demo_id, self.recorder.active_recordings)
    
    def test_record_step(self):
        demo_id = self.recorder.start_recording("Test")
        self.recorder.record_step(
            demo_id=demo_id,
            action_type="tool_call",
            parameters={"query": "hello"},
            tool_name="search",
            duration_ms=100.0
        )
        self.assertEqual(len(self.recorder.active_recordings[demo_id].steps), 1)
    
    def test_record_step_invalid_id(self):
        with self.assertRaises(ValueError):
            self.recorder.record_step(
                demo_id="invalid_id",
                action_type="tool_call",
                parameters={}
            )
    
    def test_stop_recording(self):
        demo_id = self.recorder.start_recording("Test")
        self.recorder.record_step(demo_id, "action", {})
        demo = self.recorder.stop_recording(demo_id, "Completed successfully", True)
        
        self.assertEqual(demo.outcome, "Completed successfully")
        self.assertTrue(demo.success)
        self.assertNotIn(demo_id, self.recorder.active_recordings)
        self.assertIn(demo_id, self.recorder.demonstrations)
    
    def test_stop_recording_invalid_id(self):
        with self.assertRaises(ValueError):
            self.recorder.stop_recording("invalid_id")
    
    def test_find_demonstrations(self):
        # Create some demonstrations
        demo1_id = self.recorder.start_recording("Search task", tags=["search"])
        self.recorder.stop_recording(demo1_id, "Done", True)
        
        demo2_id = self.recorder.start_recording("Calculate task", tags=["math"])
        self.recorder.stop_recording(demo2_id, "Done", True)
        
        demo3_id = self.recorder.start_recording("Failed search", tags=["search"])
        self.recorder.stop_recording(demo3_id, "Error", False)
        
        # Find by pattern (successful only by default)
        search_demos = self.recorder.find_demonstrations(task_pattern="search")
        self.assertEqual(len(search_demos), 1)  # Only successful search demo
        
        # Find by pattern including failed
        all_search_demos = self.recorder.find_demonstrations(
            task_pattern="search", 
            successful_only=False
        )
        self.assertEqual(len(all_search_demos), 2)  # Including failed one
        
        # Find by tag
        math_demos = self.recorder.find_demonstrations(tags=["math"])
        self.assertEqual(len(math_demos), 1)
        
        # Find successful only
        successful = self.recorder.find_demonstrations(successful_only=True)
        self.assertEqual(len(successful), 2)
    
    def test_persistence(self):
        # Create and save
        demo_id = self.recorder.start_recording("Persistent task")
        self.recorder.record_step(demo_id, "action", {"key": "value"})
        self.recorder.stop_recording(demo_id, "Saved", True)
        
        # Create new recorder pointing to same path
        new_recorder = DemonstrationRecorder(storage_path=self.temp_dir)
        self.assertIn(demo_id, new_recorder.demonstrations)
        self.assertEqual(new_recorder.demonstrations[demo_id].task_description, "Persistent task")


class TestPatternExtractor(unittest.TestCase):
    """Test PatternExtractor class."""
    
    def setUp(self):
        self.extractor = PatternExtractor()
    
    def test_extract_action_sequence(self):
        # Create similar demonstrations
        demos = []
        for i in range(3):
            demo = Demonstration(task_description=f"Task {i}")
            demo.add_step(ActionStep(action_type="start", tool_name="init"))
            demo.add_step(ActionStep(action_type="process", tool_name="worker"))
            demo.add_step(ActionStep(action_type="end", tool_name="cleanup"))
            demos.append(demo)
        
        patterns = self.extractor.extract_action_sequence(demos, min_frequency=2)
        self.assertGreater(len(patterns), 0)
        
        # Check pattern properties
        for pattern in patterns:
            self.assertIsInstance(pattern, ExtractedPattern)
            self.assertEqual(pattern.pattern_type, PatternType.ACTION_SEQUENCE)
            self.assertGreaterEqual(pattern.frequency, 2)
    
    def test_extract_parameter_mappings(self):
        demos = []
        for i in range(3):
            demo = Demonstration(task_description=f"Task {i}")
            step = ActionStep(
                action_type="search",
                tool_name="web_search",
                parameters={"query": f"test{i}", "limit": 10}
            )
            demo.add_step(step)
            demos.append(demo)
        
        patterns = self.extractor.extract_parameter_mappings(demos)
        self.assertGreater(len(patterns), 0)
        
        # Should find varying 'query' parameter
        found_query = any("query" in p.parameter_schema.get("varying_params", []) 
                         for p in patterns)
        self.assertTrue(found_query)
    
    def test_get_pattern(self):
        pattern = ExtractedPattern(
            pattern_type=PatternType.ACTION_SEQUENCE,
            name="test_pattern"
        )
        self.extractor.patterns[pattern.pattern_id] = pattern
        
        retrieved = self.extractor.get_pattern(pattern.pattern_id)
        self.assertEqual(retrieved.name, "test_pattern")
    
    def test_find_similar_patterns(self):
        # Create two similar patterns
        p1 = ExtractedPattern(
            pattern_type=PatternType.ACTION_SEQUENCE,
            action_sequence=[
                {"action_type": "a", "tool_name": "tool1"},
                {"action_type": "b", "tool_name": "tool2"}
            ]
        )
        p2 = ExtractedPattern(
            pattern_type=PatternType.ACTION_SEQUENCE,
            action_sequence=[
                {"action_type": "a", "tool_name": "tool1"},
                {"action_type": "b", "tool_name": "tool2"}
            ]
        )
        p3 = ExtractedPattern(
            pattern_type=PatternType.ACTION_SEQUENCE,
            action_sequence=[
                {"action_type": "x", "tool_name": "tool3"}
            ]
        )
        
        self.extractor.patterns[p1.pattern_id] = p1
        self.extractor.patterns[p2.pattern_id] = p2
        self.extractor.patterns[p3.pattern_id] = p3
        
        similar = self.extractor.find_similar_patterns(p1, threshold=1.0)
        self.assertEqual(len(similar), 1)
        self.assertEqual(similar[0].pattern_id, p2.pattern_id)


class TestSkillSynthesizer(unittest.TestCase):
    """Test SkillSynthesizer class."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.synthesizer = SkillSynthesizer(skill_library_path=self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_synthesize_skill(self):
        # Create patterns
        pattern = ExtractedPattern(
            pattern_type=PatternType.ACTION_SEQUENCE,
            name="search_pattern",
            action_sequence=[
                {"action_type": "tool_call", "tool_name": "search"},
                {"action_type": "tool_call", "tool_name": "analyze"}
            ],
            confidence=0.9,
            frequency=5
        )
        
        # Create demonstrations
        demo = Demonstration(task_description="Search and analyze", success=True)
        demo.add_step(ActionStep(tool_name="search"))
        demo.add_step(ActionStep(tool_name="analyze"))
        
        skill = self.synthesizer.synthesize_skill(
            name="search_analyze_skill",
            description="Search for information and analyze results",
            patterns=[pattern],
            demonstrations=[demo],
            skill_type=SkillType.SEQUENTIAL
        )
        
        self.assertEqual(skill.name, "search_analyze_skill")
        self.assertEqual(skill.skill_type, SkillType.SEQUENTIAL)
        self.assertIn("search", skill.required_tools)
        self.assertIn("analyze", skill.required_tools)
        self.assertEqual(skill.estimated_success_rate, 1.0)
        self.assertIsNotNone(skill.skill_id)
    
    def test_refine_skill(self):
        # Create initial skill
        pattern = ExtractedPattern(
            pattern_type=PatternType.ACTION_SEQUENCE,
            action_sequence=[{"action_type": "action1", "tool_name": "tool1"}]
        )
        demo = Demonstration(task_description="Initial", success=True)
        skill = self.synthesizer.synthesize_skill(
            "test_skill", "Test", [pattern], [demo]
        )
        
        # Refine with new demonstrations
        new_demo = Demonstration(task_description="Additional", success=True)
        new_demo.add_step(ActionStep(tool_name="tool2"))
        
        refined = self.synthesizer.refine_skill(
            skill.skill_id,
            [new_demo]
        )
        
        self.assertEqual(refined.parent_skill, skill.skill_id)
        self.assertIn("tool2", refined.required_tools)
        self.assertNotEqual(refined.skill_id, skill.skill_id)
    
    def test_refine_skill_not_found(self):
        with self.assertRaises(ValueError):
            self.synthesizer.refine_skill("invalid_id", [])
    
    def test_find_skills(self):
        pattern = ExtractedPattern(action_sequence=[])
        demo = Demonstration(task_description="Test", success=True)
        
        skill1 = self.synthesizer.synthesize_skill(
            "search_skill", "Search", [pattern], [demo]
        )
        skill2 = self.synthesizer.synthesize_skill(
            "calculate_skill", "Calculate", [pattern], [demo]
        )
        
        search_results = self.synthesizer.find_skills(name_pattern="search")
        self.assertEqual(len(search_results), 1)
        self.assertEqual(search_results[0].name, "search_skill")
    
    def test_execute_skill(self):
        # Create a skill with a mock tool
        pattern = ExtractedPattern(
            pattern_type=PatternType.ACTION_SEQUENCE,
            action_sequence=[{"action_type": "tool_call", "tool_name": "mock_tool"}]
        )
        demo = Demonstration(success=True)
        skill = self.synthesizer.synthesize_skill("test", "Test", [pattern], [demo])
        
        # Create mock tool registry
        def mock_tool(**kwargs):
            return {"result": "success"}
        
        tool_registry = {"mock_tool": mock_tool}
        
        result = self.synthesizer.execute_skill(skill.skill_id, {}, tool_registry)
        self.assertTrue(result["success"])
        self.assertEqual(result["skill_name"], "test")
        self.assertEqual(skill.usage_count, 1)
    
    def test_execute_skill_not_found(self):
        result = self.synthesizer.execute_skill("invalid_id", {})
        self.assertFalse(result["success"])
        self.assertIn("error", result)
    
    def test_skill_version_bump(self):
        skill = LearnedSkill(name="test", version="1.0.0")
        
        skill.bump_version("patch")
        self.assertEqual(skill.version, "1.0.1")
        
        skill.bump_version("minor")
        self.assertEqual(skill.version, "1.1.0")
        
        skill.bump_version("major")
        self.assertEqual(skill.version, "2.0.0")
    
    def test_persistence(self):
        pattern = ExtractedPattern(action_sequence=[])
        demo = Demonstration(success=True)
        skill = self.synthesizer.synthesize_skill("persistent", "Test", [pattern], [demo])
        
        # Create new synthesizer
        new_synthesizer = SkillSynthesizer(skill_library_path=self.temp_dir)
        self.assertIn(skill.skill_id, new_synthesizer.skills)
        self.assertEqual(new_synthesizer.skills[skill.skill_id].name, "persistent")


class TestTransferLearning(unittest.TestCase):
    """Test TransferLearning class."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.synthesizer = SkillSynthesizer(skill_library_path=self.temp_dir)
        self.transfer = TransferLearning(self.synthesizer)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_adapt_skill_parameter_mapping(self):
        # Create original skill
        pattern = ExtractedPattern(action_sequence=[])
        demo = Demonstration(success=True)
        skill = self.synthesizer.synthesize_skill("original", "Original", [pattern], [demo])
        skill.parameter_schema = {"properties": {"query": {"type": "string"}}}
        
        # Adapt to new context
        adapted = self.transfer.adapt_skill(
            skill.skill_id,
            target_context={"query": "default_value"},
            adaptation_strategy="parameter_mapping"
        )
        
        self.assertIsNotNone(adapted)
        self.assertEqual(adapted.parent_skill, skill.skill_id)
        self.assertIn("default_value", str(adapted.parameter_schema))
        self.assertLess(adapted.estimated_success_rate, skill.estimated_success_rate)
    
    def test_adapt_skill_pattern_substitution(self):
        pattern = ExtractedPattern(
            action_sequence=[{"action_type": "call", "tool_name": "old_tool"}]
        )
        demo = Demonstration(success=True)
        demo.add_step(ActionStep(tool_name="old_tool"))
        skill = self.synthesizer.synthesize_skill("original", "Original", [pattern], [demo])
        skill.required_tools = ["old_tool"]
        
        adapted = self.transfer.adapt_skill(
            skill.skill_id,
            target_context={"tool_mappings": {"old_tool": "new_tool"}},
            adaptation_strategy="pattern_substitution"
        )
        
        self.assertIsNotNone(adapted)
        self.assertIn("new_tool", adapted.required_tools)
        self.assertNotIn("old_tool", adapted.required_tools)
    
    def test_adapt_skill_not_found(self):
        result = self.transfer.adapt_skill("invalid_id", {})
        self.assertIsNone(result)
    
    def test_compose_skills(self):
        # Create two skills
        pattern = ExtractedPattern(action_sequence=[])
        demo = Demonstration(success=True)
        
        skill1 = self.synthesizer.synthesize_skill("skill1", "First", [pattern], [demo])
        skill2 = self.synthesizer.synthesize_skill("skill2", "Second", [pattern], [demo])
        
        # Add different tools to each
        skill1.required_tools = ["tool_a"]
        skill2.required_tools = ["tool_b"]
        
        composed = self.transfer.compose_skills(
            [skill1.skill_id, skill2.skill_id],
            "combined_skill",
            "Combined skill description"
        )
        
        self.assertIsNotNone(composed)
        self.assertEqual(composed.skill_type, SkillType.COMPOSITE)
        self.assertEqual(composed.name, "combined_skill")
        self.assertIn("tool_a", composed.required_tools)
        self.assertIn("tool_b", composed.required_tools)
    
    def test_compose_skills_invalid_id(self):
        result = self.transfer.compose_skills(["invalid_id"], "test", "test")
        self.assertIsNone(result)


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete LfD system."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.recorder, self.extractor, self.synthesizer, self.transfer = create_lfd_system(self.temp_dir)
    
    def tearDown(self):
        shutil.rmtree(self.temp_dir)
    
    def test_end_to_end_workflow(self):
        """Test complete workflow: record -> extract -> synthesize -> transfer."""
        
        # Step 1: Record multiple similar demonstrations
        demos = []
        for i in range(3):
            demo_id = self.recorder.start_recording(
                task_description="Search and summarize",
                goal="Find and summarize information",
                tags=["search", "summarize"]
            )
            
            # Simulate search step
            self.recorder.record_step(
                demo_id=demo_id,
                action_type="tool_call",
                tool_name="web_search",
                parameters={"query": f"topic_{i}", "limit": 10},
                duration_ms=500.0
            )
            
            # Simulate analysis step
            self.recorder.record_step(
                demo_id=demo_id,
                action_type="reasoning",
                parameters={"analysis_type": "summarize"},
                duration_ms=200.0
            )
            
            # Stop recording
            demo = self.recorder.stop_recording(demo_id, f"Completed {i}", True)
            demos.append(demo)
        
        self.assertEqual(len(self.recorder.demonstrations), 3)
        
        # Step 2: Extract patterns
        patterns = self.extractor.extract_action_sequence(demos, min_frequency=2)
        self.assertGreater(len(patterns), 0)
        
        # Step 3: Synthesize skill
        skill = self.synthesizer.synthesize_skill(
            name="search_and_summarize",
            description="Search for information and summarize results",
            patterns=patterns,
            demonstrations=demos
        )
        
        self.assertEqual(skill.name, "search_and_summarize")
        self.assertIn("web_search", skill.required_tools)
        
        # Step 4: Transfer to new context
        adapted = self.transfer.adapt_skill(
            skill.skill_id,
            target_context={"default_limit": 20},
            adaptation_strategy="parameter_mapping"
        )
        
        self.assertIsNotNone(adapted)
        self.assertEqual(adapted.parent_skill, skill.skill_id)
    
    def test_learning_from_failures(self):
        """Test learning from both successful and failed demonstrations."""
        
        # Successful demo
        success_id = self.recorder.start_recording("Complex task")
        self.recorder.record_step(success_id, "step1", {}, success=True)
        self.recorder.record_step(success_id, "step2", {}, success=True)
        success_demo = self.recorder.stop_recording(success_id, "Success", True)
        
        # Failed demo
        fail_id = self.recorder.start_recording("Complex task")
        self.recorder.record_step(fail_id, "step1", {}, success=True)
        self.recorder.record_step(fail_id, "step2", {}, success=False)
        fail_demo = self.recorder.stop_recording(fail_id, "Failed", False)
        
        # Extract patterns from both
        all_demos = [success_demo, fail_demo]
        patterns = self.extractor.extract_action_sequence(all_demos, min_frequency=1)
        
        # Synthesize skill - should have reduced success rate
        skill = self.synthesizer.synthesize_skill(
            "complex_task",
            "Perform complex task",
            patterns,
            all_demos
        )
        
        self.assertEqual(skill.estimated_success_rate, 0.5)  # 1 out of 2 successful


if __name__ == "__main__":
    unittest.main()
