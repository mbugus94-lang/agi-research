"""
Tests for Self-Honing Module (ASH-inspired)

Validates:
1. Trajectory recording and storage
2. Key moment identification
3. Pattern extraction
4. Self-honing loop integration
5. Statistics tracking
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from unittest.mock import MagicMock, patch
import time

from core.self_honing import (
    SelfHoningEngine,
    TrajectoryStore,
    KeyMomentIdentifier,
    PatternExtractor,
    ExecutionTrajectory,
    KeyMoment,
    ExtractedPattern,
    TrajectoryType,
    MomentImportance,
    create_self_honing_engine
)


class TestTrajectoryStore(unittest.TestCase):
    """Test trajectory storage and indexing"""
    
    def setUp(self):
        self.store = TrajectoryStore()
    
    def test_store_and_retrieve(self):
        """Test basic storage and retrieval"""
        traj = ExecutionTrajectory(
            trajectory_id="test_1",
            task_description="Test task",
            trajectory_type=TrajectoryType.TASK_COMPLETION,
            start_time=time.time()
        )
        
        self.store.store(traj)
        
        retrieved = self.store.get("test_1")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.task_description, "Test task")
    
    def test_get_by_type(self):
        """Test filtering by trajectory type"""
        traj1 = ExecutionTrajectory(
            trajectory_id="t1",
            task_description="Task 1",
            trajectory_type=TrajectoryType.TASK_COMPLETION,
            start_time=time.time()
        )
        traj2 = ExecutionTrajectory(
            trajectory_id="t2",
            task_description="Task 2",
            trajectory_type=TrajectoryType.RECOVERY,
            start_time=time.time()
        )
        
        self.store.store(traj1)
        self.store.store(traj2)
        
        recovery_trajs = self.store.get_by_type(TrajectoryType.RECOVERY)
        self.assertEqual(len(recovery_trajs), 1)
        self.assertEqual(recovery_trajs[0].trajectory_id, "t2")
    
    def test_get_successful(self):
        """Test filtering successful trajectories"""
        traj1 = ExecutionTrajectory(
            trajectory_id="t1",
            task_description="Success task",
            trajectory_type=TrajectoryType.TASK_COMPLETION,
            start_time=time.time()
        )
        traj1.outcome = "success"
        
        traj2 = ExecutionTrajectory(
            trajectory_id="t2",
            task_description="Failure task",
            trajectory_type=TrajectoryType.TASK_COMPLETION,
            start_time=time.time()
        )
        traj2.outcome = "failure"
        
        self.store.store(traj1)
        self.store.store(traj2)
        
        successful = self.store.get_successful()
        self.assertEqual(len(successful), 1)
        self.assertEqual(successful[0].trajectory_id, "t1")
    
    def test_get_by_task_pattern(self):
        """Test searching by task description pattern"""
        traj1 = ExecutionTrajectory(
            trajectory_id="t1",
            task_description="Web search for papers",
            trajectory_type=TrajectoryType.TASK_COMPLETION,
            start_time=time.time()
        )
        traj2 = ExecutionTrajectory(
            trajectory_id="t2",
            task_description="Code generation task",
            trajectory_type=TrajectoryType.TASK_COMPLETION,
            start_time=time.time()
        )
        
        self.store.store(traj1)
        self.store.store(traj2)
        
        search_trajs = self.store.get_by_task_pattern("search")
        self.assertEqual(len(search_trajs), 1)
        self.assertEqual(search_trajs[0].trajectory_id, "t1")


class TestExecutionTrajectory(unittest.TestCase):
    """Test execution trajectory functionality"""
    
    def test_add_step(self):
        """Test adding steps to trajectory"""
        traj = ExecutionTrajectory(
            trajectory_id="test",
            task_description="Test",
            trajectory_type=TrajectoryType.TASK_COMPLETION,
            start_time=time.time()
        )
        
        traj.add_step(
            action="search",
            observation={"results": 10},
            state={"query": "test"}
        )
        
        self.assertEqual(len(traj.steps), 1)
        self.assertEqual(traj.steps[0]["action"], "search")
        self.assertEqual(traj.steps[0]["step_number"], 1)
    
    def test_step_number_increment(self):
        """Test step numbers auto-increment"""
        traj = ExecutionTrajectory(
            trajectory_id="test",
            task_description="Test",
            trajectory_type=TrajectoryType.TASK_COMPLETION,
            start_time=time.time()
        )
        
        traj.add_step("action1", {}, {})
        traj.add_step("action2", {}, {})
        traj.add_step("action3", {}, {})
        
        self.assertEqual(traj.steps[0]["step_number"], 1)
        self.assertEqual(traj.steps[1]["step_number"], 2)
        self.assertEqual(traj.steps[2]["step_number"], 3)
    
    def test_complete_trajectory(self):
        """Test completing a trajectory"""
        traj = ExecutionTrajectory(
            trajectory_id="test",
            task_description="Test",
            trajectory_type=TrajectoryType.TASK_COMPLETION,
            start_time=time.time()
        )
        
        traj.complete("success", {"accuracy": 0.95})
        
        self.assertEqual(traj.outcome, "success")
        self.assertIsNotNone(traj.end_time)
        self.assertGreater(traj.duration, 0)
        self.assertEqual(traj.metadata["accuracy"], 0.95)
    
    def test_to_dict(self):
        """Test serialization"""
        traj = ExecutionTrajectory(
            trajectory_id="test",
            task_description="Test",
            trajectory_type=TrajectoryType.TASK_COMPLETION,
            start_time=time.time()
        )
        
        traj.add_step("action", {"result": "ok"}, {})
        traj.complete("success")
        
        d = traj.to_dict()
        self.assertEqual(d["trajectory_id"], "test")
        self.assertEqual(d["outcome"], "success")
        self.assertEqual(len(d["steps"]), 1)


class TestKeyMomentIdentification(unittest.TestCase):
    """Test key moment identification (ASH-style)"""
    
    def setUp(self):
        self.identifier = KeyMomentIdentifier()
    
    def test_identify_outcome_transition(self):
        """Test identifying success/failure turning points"""
        traj = ExecutionTrajectory(
            trajectory_id="test",
            task_description="Test",
            trajectory_type=TrajectoryType.TASK_COMPLETION,
            start_time=time.time()
        )
        
        traj.add_step("step1", {"success": True}, {"state": 1})
        traj.add_step("step2", {"success": True}, {"state": 2})
        traj.complete("success")
        
        moments = self.identifier.identify_moments(traj)
        
        # Should have at least the completion moment
        self.assertGreaterEqual(len(moments), 1)
        
        # Check that there's a critical moment
        critical = [m for m in moments if m.importance == MomentImportance.CRITICAL]
        self.assertGreaterEqual(len(critical), 1)
    
    def test_identify_state_changes(self):
        """Test identifying significant state changes"""
        traj = ExecutionTrajectory(
            trajectory_id="test",
            task_description="Test",
            trajectory_type=TrajectoryType.TASK_COMPLETION,
            start_time=time.time()
        )
        
        # Big state change
        traj.add_step("action1", {}, {"a": 1, "b": 2, "c": 3})
        traj.add_step("action2", {}, {"a": 1, "b": 99, "c": 99, "d": 4})
        traj.complete("success")
        
        moments = self.identifier.identify_moments(traj)
        
        # Should identify the state change
        state_changes = [m for m in moments if "state_change_score" in m.context]
        self.assertGreaterEqual(len(state_changes), 1)
    
    def test_identify_tool_moments(self):
        """Test identifying tool execution moments"""
        traj = ExecutionTrajectory(
            trajectory_id="test",
            task_description="Test",
            trajectory_type=TrajectoryType.TASK_COMPLETION,
            start_time=time.time()
        )
        
        traj.add_step(
            "tool_search",
            {"success": True, "tool_used": "web_search"},
            {}
        )
        traj.complete("success")
        
        moments = self.identifier.identify_moments(traj)
        
        # Should identify tool moment
        tool_moments = [m for m in moments if m.context.get("tool_execution")]
        self.assertEqual(len(tool_moments), 1)
        self.assertEqual(tool_moments[0].outcome, "success")
    
    def test_identify_recovery_moments(self):
        """Test identifying error recovery patterns"""
        traj = ExecutionTrajectory(
            trajectory_id="test",
            task_description="Test",
            trajectory_type=TrajectoryType.TASK_COMPLETION,
            start_time=time.time()
        )
        
        traj.add_step("action1", {"success": False}, {})
        traj.add_step("recovery_action", {"success": True}, {})
        traj.complete("success")
        
        moments = self.identifier.identify_moments(traj)
        
        # Should identify recovery
        recovery = [m for m in moments if m.context.get("recovery")]
        self.assertEqual(len(recovery), 1)
        self.assertEqual(recovery[0].action_taken, "recovery_action")


class TestPatternExtraction(unittest.TestCase):
    """Test pattern extraction (IDM-like)"""
    
    def setUp(self):
        self.extractor = PatternExtractor()
    
    def test_extract_sequence_patterns(self):
        """Test extracting common action sequences"""
        # Create multiple similar successful trajectories
        trajs = []
        for i in range(3):
            traj = ExecutionTrajectory(
                trajectory_id=f"traj_{i}",
                task_description="Web research task",
                trajectory_type=TrajectoryType.TASK_COMPLETION,
                start_time=time.time()
            )
            traj.add_step("analyze_query", {"success": True}, {})
            traj.add_step("search_web", {"success": True}, {})
            traj.add_step("summarize", {"success": True}, {})
            traj.outcome = "success"
            trajs.append(traj)
        
        patterns = self.extractor.extract_patterns(trajs)
        
        # Should extract sequence pattern
        seq_patterns = [p for p in patterns if p.pattern_type == "action_sequence"]
        self.assertGreaterEqual(len(seq_patterns), 1)
        
        # Pattern should have common actions
        self.assertIn("analyze_query", seq_patterns[0].action_template)
    
    def test_extract_recovery_patterns(self):
        """Test extracting recovery patterns"""
        trajs = []
        for i in range(3):
            traj = ExecutionTrajectory(
                trajectory_id=f"traj_{i}",
                task_description="Task with recovery",
                trajectory_type=TrajectoryType.RECOVERY,
                start_time=time.time()
            )
            traj.add_step("action1", {"success": False}, {})
            traj.add_step("retry_with_fallback", {"success": True}, {})
            
            # Add recovery moment manually for test
            traj.key_moments.append(KeyMoment(
                moment_id=f"km_{i}",
                timestamp=time.time(),
                trajectory_id=traj.trajectory_id,
                step_number=2,
                state_before={},
                action_taken="retry_with_fallback",
                state_after={},
                outcome="success",
                importance=MomentImportance.HIGH,
                context={"recovery": True}
            ))
            
            traj.outcome = "success"
            trajs.append(traj)
        
        patterns = self.extractor.extract_patterns(trajs)
        
        # Should extract recovery pattern
        recovery = [p for p in patterns if p.pattern_type == "recovery_strategy"]
        self.assertGreaterEqual(len(recovery), 1)
        self.assertEqual(recovery[0].action_template[0], "retry_with_fallback")
    
    def test_pattern_confidence_calculation(self):
        """Test confidence based on frequency and success"""
        trajs = []
        for i in range(5):
            traj = ExecutionTrajectory(
                trajectory_id=f"traj_{i}",
                task_description="Same task",
                trajectory_type=TrajectoryType.TASK_COMPLETION,
                start_time=time.time()
            )
            traj.add_step("action", {"success": True}, {})
            traj.outcome = "success"
            trajs.append(traj)
        
        patterns = self.extractor.extract_patterns(trajs)
        
        # High frequency + high success = higher confidence
        for p in patterns:
            self.assertGreaterEqual(p.confidence, 0.5)
            self.assertLessEqual(p.confidence, 1.0)


class TestSelfHoningEngine(unittest.TestCase):
    """Test main self-honing engine"""
    
    def setUp(self):
        self.engine = create_self_honing_engine()
    
    def test_start_trajectory(self):
        """Test starting trajectory recording"""
        traj_id = self.engine.start_trajectory(
            task_description="Test task",
            trajectory_type=TrajectoryType.TASK_COMPLETION
        )
        
        self.assertIsNotNone(traj_id)
        self.assertTrue(traj_id.startswith("traj_"))
        self.assertIsNotNone(self.engine.active_trajectory)
    
    def test_record_step(self):
        """Test recording steps"""
        self.engine.start_trajectory("Test")
        
        self.engine.record_step(
            action="search",
            observation={"results": 5},
            state={"query": "test"}
        )
        
        self.assertEqual(len(self.engine.active_trajectory.steps), 1)
    
    def test_complete_trajectory(self):
        """Test completing trajectory"""
        self.engine.start_trajectory("Test")
        self.engine.record_step("action", {"success": True}, {})
        
        completed = self.engine.complete_trajectory("success")
        
        self.assertEqual(completed.outcome, "success")
        self.assertIsNone(self.engine.active_trajectory)
        self.assertEqual(self.engine.honing_stats["trajectories_recorded"], 1)
    
    def test_hone_insufficient_data(self):
        """Test honing with insufficient data"""
        result = self.engine.hone()
        
        self.assertEqual(result["status"], "insufficient_data")
    
    def test_hone_extracts_patterns(self):
        """Test successful honing extracts patterns"""
        # Record multiple successful trajectories
        for i in range(3):
            self.engine.start_trajectory("Web research")
            self.engine.record_step("analyze", {"success": True}, {"intent": "research"})
            self.engine.record_step("search", {"success": True}, {"results": 10})
            self.engine.complete_trajectory("success")
        
        result = self.engine.hone()
        
        self.assertEqual(result["status"], "success")
        self.assertGreater(result["patterns_extracted"], 0)
        self.assertGreaterEqual(result["trajectories_analyzed"], 3)
    
    def test_get_learned_patterns(self):
        """Test retrieving learned patterns"""
        # Create patterns
        pattern = ExtractedPattern(
            pattern_id="test_pattern",
            pattern_type="action_sequence",
            source_trajectories=["t1", "t2"],
            frequency=2,
            success_rate=1.0,
            action_template=["step1", "step2"],
            preconditions={},
            postconditions={},
            parameter_slots=[],
            confidence=0.9,
            extracted_at=time.time()
        )
        
        self.engine.extracted_patterns.append(pattern)
        
        patterns = self.engine.get_learned_patterns()
        self.assertEqual(len(patterns), 1)
        
        filtered = self.engine.get_learned_patterns("action_sequence")
        self.assertEqual(len(filtered), 1)
        
        empty = self.engine.get_learned_patterns("nonexistent")
        self.assertEqual(len(empty), 0)
    
    def test_get_improvement_suggestions(self):
        """Test generating improvement suggestions"""
        # Add high-confidence pattern
        pattern = ExtractedPattern(
            pattern_id="reliable_pattern",
            pattern_type="action_sequence",
            source_trajectories=["t1", "t2", "t3"],
            frequency=3,
            success_rate=0.95,
            action_template=["analyze", "search", "summarize"],
            preconditions={},
            postconditions={},
            parameter_slots=[],
            confidence=0.95,
            extracted_at=time.time()
        )
        
        self.engine.extracted_patterns.append(pattern)
        
        suggestions = self.engine.get_improvement_suggestions()
        
        self.assertGreaterEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["type"], "reliable_pattern")
    
    def test_get_stats(self):
        """Test statistics tracking"""
        stats = self.engine.get_stats()
        
        self.assertIn("trajectories_recorded", stats)
        self.assertIn("patterns_extracted", stats)
        self.assertIn("stored_trajectories", stats)
        self.assertIn("active_recording", stats)
    
    def test_multiple_hone_cycles(self):
        """Test multiple honing cycles accumulate patterns"""
        for cycle in range(2):
            for i in range(3):
                self.engine.start_trajectory(f"Task cycle {cycle}")
                self.engine.record_step("action", {"success": True}, {})
                self.engine.complete_trajectory("success")
            
            result = self.engine.hone()
            self.assertEqual(result["status"], "success")
        
        # Should have accumulated patterns
        self.assertGreater(len(self.engine.extracted_patterns), 0)


class TestIntegration(unittest.TestCase):
    """Integration tests"""
    
    def test_full_self_honing_workflow(self):
        """Test complete self-honing workflow"""
        engine = create_self_honing_engine()
    
        # Simulate multiple task executions (need 5+ for high confidence patterns)
        tasks = [
            ("Web research AGI", ["analyze_query", "search_web", "summarize"]),
            ("Web research AI", ["analyze_query", "search_web", "summarize"]),
            ("Web search papers", ["analyze_query", "search_web", "summarize"]),
            ("Web research ML", ["analyze_query", "search_web", "summarize"]),
            ("Web search AI", ["analyze_query", "search_web", "summarize"]),
            ("Web research GPT", ["analyze_query", "search_web", "summarize"]),
        ]
    
        for task_desc, actions in tasks:
            engine.start_trajectory(task_desc, TrajectoryType.TASK_COMPLETION)
            for action in actions:
                engine.record_step(
                    action=action,
                    observation={"success": True, "result": "ok"},
                    state={"progress": actions.index(action)}
                )
            engine.complete_trajectory("success", {"accuracy": 0.92})
    
        # Execute self-honing
        result = engine.hone()
    
        self.assertEqual(result["status"], "success")
        self.assertGreaterEqual(result["patterns_extracted"], 1)
    
        # Get suggestions
        suggestions = engine.get_improvement_suggestions()
    
        # Should suggest crystallizing reliable patterns
        self.assertGreaterEqual(len(suggestions), 1)
    
    def test_key_moment_to_pattern_flow(self):
        """Test flow from moments to patterns"""
        engine = create_self_honing_engine()
        
        # Create trajectory with recovery
        engine.start_trajectory("Task with error", TrajectoryType.TASK_COMPLETION)
        engine.record_step("action1", {"success": False}, {})
        engine.record_step("recovery_retry", {"success": True}, {})
        engine.record_step("action2", {"success": True}, {})
        engine.complete_trajectory("success")
        
        # Create similar trajectory
        engine.start_trajectory("Another task", TrajectoryType.TASK_COMPLETION)
        engine.record_step("action1", {"success": False}, {})
        engine.record_step("recovery_retry", {"success": True}, {})
        engine.record_step("action2", {"success": True}, {})
        engine.complete_trajectory("success")
        
        # Honing should extract recovery pattern
        result = engine.hone()
        
        recovery_patterns = [p for p in engine.extracted_patterns 
                          if p.pattern_type == "recovery_strategy"]
        self.assertGreaterEqual(len(recovery_patterns), 1)


def run_tests():
    """Run all tests and return results"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestTrajectoryStore))
    suite.addTests(loader.loadTestsFromTestCase(TestExecutionTrajectory))
    suite.addTests(loader.loadTestsFromTestCase(TestKeyMomentIdentification))
    suite.addTests(loader.loadTestsFromTestCase(TestPatternExtraction))
    suite.addTests(loader.loadTestsFromTestCase(TestSelfHoningEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == "__main__":
    result = run_tests()
    sys.exit(0 if result.wasSuccessful() else 1)
