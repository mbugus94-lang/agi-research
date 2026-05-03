"""
Test suite for Embodied AI Simulation Layer.

Validates:
- World creation and manipulation
- Agent perception and action
- Physics engine (gravity, collisions)
- Goal inference (ARC-AGI-3 style)
- Path planning
- Action-effect learning
- Serialization/deserialization
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import unittest
from core.embodied_simulation import (
    World, EmbodiedAgent, GoalInferenceTask,
    Action, ActionType, Position, Object, CellType,
    create_simple_navigation_task, create_object_collection_task
)


class TestWorldBasics(unittest.TestCase):
    """Test basic world operations."""
    
    def test_world_creation(self):
        """Test creating a world with dimensions."""
        world = World(10, 10)
        self.assertEqual(world.width, 10)
        self.assertEqual(world.height, 10)
        self.assertEqual(len(world.grid), 10)
        self.assertEqual(len(world.grid[0]), 10)
    
    def test_valid_position(self):
        """Test position validation."""
        world = World(5, 5)
        self.assertTrue(world.is_valid_position(Position(0, 0)))
        self.assertTrue(world.is_valid_position(Position(4, 4)))
        self.assertFalse(world.is_valid_position(Position(-1, 0)))
        self.assertFalse(world.is_valid_position(Position(5, 5)))
        self.assertFalse(world.is_valid_position(Position(10, 10)))
    
    def test_place_agent(self):
        """Test placing agent in world."""
        world = World(5, 5)
        self.assertTrue(world.place_agent(Position(2, 2)))
        self.assertEqual(world.agent_position, Position(2, 2))
        self.assertEqual(world.grid[2][2], CellType.AGENT)
    
    def test_place_agent_invalid(self):
        """Test placing agent at invalid position."""
        world = World(5, 5)
        self.assertFalse(world.place_agent(Position(-1, 0)))
        self.assertFalse(world.place_agent(Position(10, 10)))
    
    def test_place_obstacle(self):
        """Test placing obstacles."""
        world = World(5, 5)
        self.assertTrue(world.place_obstacle(Position(1, 1)))
        self.assertEqual(world.grid[1][1], CellType.OBSTACLE)
    
    def test_place_goal(self):
        """Test placing goal."""
        world = World(5, 5)
        self.assertTrue(world.place_goal(Position(4, 4)))
        self.assertEqual(world.goal_position, Position(4, 4))
        self.assertEqual(world.grid[4][4], CellType.GOAL)
    
    def test_place_object(self):
        """Test placing objects."""
        world = World(5, 5)
        obj = Object("obj1", "box", Position(2, 2))
        self.assertTrue(world.place_object(obj))
        self.assertIn("obj1", world.objects)
        self.assertEqual(world.objects["obj1"].position, Position(2, 2))


class TestAgentMovement(unittest.TestCase):
    """Test agent movement and collision."""
    
    def test_move_up(self):
        """Test moving up."""
        world = World(5, 5)
        world.place_agent(Position(2, 2))
        
        success, msg = world.move_agent(Position(0, -1))
        self.assertTrue(success)
        self.assertEqual(world.agent_position, Position(2, 1))
    
    def test_move_down(self):
        """Test moving down."""
        world = World(5, 5)
        world.place_agent(Position(2, 2))
        
        success, msg = world.move_agent(Position(0, 1))
        self.assertTrue(success)
        self.assertEqual(world.agent_position, Position(2, 3))
    
    def test_move_left(self):
        """Test moving left."""
        world = World(5, 5)
        world.place_agent(Position(2, 2))
        
        success, msg = world.move_agent(Position(-1, 0))
        self.assertTrue(success)
        self.assertEqual(world.agent_position, Position(1, 2))
    
    def test_move_right(self):
        """Test moving right."""
        world = World(5, 5)
        world.place_agent(Position(2, 2))
        
        success, msg = world.move_agent(Position(1, 0))
        self.assertTrue(success)
        self.assertEqual(world.agent_position, Position(3, 2))
    
    def test_collision_with_boundary(self):
        """Test collision with world boundary."""
        world = World(5, 5)
        world.place_agent(Position(0, 0))
        
        success, msg = world.move_agent(Position(-1, 0))
        self.assertFalse(success)
        self.assertEqual(world.agent_position, Position(0, 0))
    
    def test_collision_with_obstacle(self):
        """Test collision with obstacle."""
        world = World(5, 5)
        world.place_agent(Position(1, 1))
        world.place_obstacle(Position(2, 1))
        
        success, msg = world.move_agent(Position(1, 0))
        self.assertFalse(success)
        self.assertEqual(world.agent_position, Position(1, 1))


class TestPerception(unittest.TestCase):
    """Test agent perception system."""
    
    def test_basic_perception(self):
        """Test basic perception structure."""
        world = World(5, 5)
        world.place_agent(Position(2, 2))
        world.place_goal(Position(4, 4))
        
        perception = world.get_perception(view_distance=2)
        
        self.assertIsNotNone(perception.visual_grid)
        self.assertEqual(perception.agent_position, Position(2, 2))
        self.assertIn("up", perception.spatial_relations)
        self.assertIn("position", perception.proprioception)
    
    def test_spatial_relations(self):
        """Test spatial relation detection."""
        world = World(5, 5)
        world.place_agent(Position(2, 2))
        world.place_obstacle(Position(2, 1))  # Above agent
        world.place_obstacle(Position(3, 2))  # Right of agent
        
        perception = world.get_perception(view_distance=2)
        
        self.assertIn("obstacle", perception.spatial_relations["up"])
        self.assertIn("obstacle", perception.spatial_relations["right"])
    
    def test_nearby_objects(self):
        """Test detection of nearby objects."""
        world = World(10, 10)
        world.place_agent(Position(5, 5))
        
        obj_near = Object("near", "coin", Position(6, 6))
        obj_far = Object("far", "coin", Position(9, 9))
        world.place_object(obj_near)
        world.place_object(obj_far)
        
        perception = world.get_perception(view_distance=3)
        
        near_ids = [obj.id for obj in perception.nearby_objects]
        self.assertIn("near", near_ids)
        self.assertNotIn("far", near_ids)


class TestEmbodiedAgent(unittest.TestCase):
    """Test embodied agent behavior."""
    
    def test_agent_creation(self):
        """Test creating an embodied agent."""
        world = World(5, 5)
        agent = EmbodiedAgent("test_agent", world)
        
        self.assertEqual(agent.agent_id, "test_agent")
        self.assertEqual(agent.world, world)
        self.assertEqual(len(agent.transition_history), 0)
    
    def test_agent_perceive(self):
        """Test agent perception."""
        world = World(5, 5)
        world.place_agent(Position(2, 2))
        agent = EmbodiedAgent("test", world)
        
        perception = agent.perceive()
        self.assertIsNotNone(perception)
        self.assertEqual(perception.agent_position, Position(2, 2))
    
    def test_agent_act_move(self):
        """Test agent taking movement action."""
        world = World(5, 5)
        world.place_agent(Position(2, 2))
        agent = EmbodiedAgent("test", world)
        
        action = Action(ActionType.MOVE_UP)
        success, result = agent.act(action)
        
        self.assertTrue(success)
        self.assertEqual(world.agent_position, Position(2, 1))
        self.assertEqual(len(agent.transition_history), 1)
    
    def test_agent_act_collision(self):
        """Test agent action with collision."""
        world = World(5, 5)
        world.place_agent(Position(0, 0))
        
        agent = EmbodiedAgent("test", world)
        action = Action(ActionType.MOVE_LEFT)
        success, result = agent.act(action)
        
        self.assertFalse(success)
        self.assertEqual(world.agent_position, Position(0, 0))
    
    def test_reward_calculation(self):
        """Test reward calculation."""
        world = World(5, 5)
        world.place_agent(Position(1, 1))
        world.place_goal(Position(3, 3))
        
        agent = EmbodiedAgent("test", world)
        
        # Initial distance: 4, reward should be positive
        reward = agent._calculate_reward(True)
        self.assertGreater(reward, 0)
        
        # Move closer
        world.place_agent(Position(2, 2))
        closer_reward = agent._calculate_reward(True)
        self.assertGreater(closer_reward, reward)
    
    def test_goal_reward(self):
        """Test reward for reaching goal."""
        world = World(5, 5)
        world.place_agent(Position(2, 2))
        world.place_goal(Position(2, 2))
        
        agent = EmbodiedAgent("test", world)
        reward = agent._calculate_reward(True)
        
        self.assertGreaterEqual(reward, 10.0)
    
    def test_action_effect_learning(self):
        """Test that agent learns action effects."""
        world = World(5, 5)
        world.place_agent(Position(2, 2))
        
        agent = EmbodiedAgent("test", world)
        
        # Take some actions
        agent.act(Action(ActionType.MOVE_UP))
        agent.act(Action(ActionType.MOVE_DOWN))
        agent.act(Action(ActionType.MOVE_LEFT))
        
        # Check learned effects
        knowledge = agent.get_learned_knowledge()
        self.assertEqual(knowledge["transition_count"], 3)
        self.assertIn(ActionType.MOVE_UP, agent.action_effects)
    
    def test_termination_detection(self):
        """Test that agent detects goal completion."""
        world = World(5, 5)
        world.place_agent(Position(2, 2))
        world.place_goal(Position(2, 1))
        
        agent = EmbodiedAgent("test", world)
        action = Action(ActionType.MOVE_UP)
        success, result = agent.act(action)
        
        self.assertTrue(result["terminated"])


class TestPathPlanning(unittest.TestCase):
    """Test agent path planning."""
    
    def test_simple_path(self):
        """Test planning a simple path."""
        world = World(5, 5)
        world.place_agent(Position(1, 1))
        
        agent = EmbodiedAgent("test", world)
        path = agent.plan_path(Position(3, 3))
        
        # Path from (1,1) to (3,3) should have 4 moves
        self.assertEqual(len(path), 4)
        
        # Execute and verify we reach target
        for action in path:
            success, _ = agent.act(action)
            self.assertTrue(success)
        
        self.assertEqual(world.agent_position, Position(3, 3))
    
    def test_path_avoids_obstacles(self):
        """Test that path planning avoids obstacles."""
        world = World(5, 5)
        world.place_agent(Position(1, 1))
        world.place_goal(Position(3, 1))
        
        # Place obstacle in direct path
        world.place_obstacle(Position(2, 1))
        
        agent = EmbodiedAgent("test", world)
        path = agent.plan_path(Position(3, 1))
        
        # Should find a path around the obstacle
        self.assertGreater(len(path), 2)  # Longer than direct path
    
    def test_no_path(self):
        """Test when no path exists."""
        world = World(5, 5)
        world.place_agent(Position(1, 1))
        
        # Surround agent with obstacles
        world.place_obstacle(Position(0, 1))
        world.place_obstacle(Position(2, 1))
        world.place_obstacle(Position(1, 0))
        world.place_obstacle(Position(1, 2))
        
        agent = EmbodiedAgent("test", world)
        path = agent.plan_path(Position(4, 4))
        
        self.assertEqual(len(path), 0)


class TestGoalInference(unittest.TestCase):
    """Test ARC-AGI-3 style goal inference."""
    
    def test_simple_navigation_inference(self):
        """Test inferring navigation goal."""
        world_in = World(5, 5)
        world_in.place_agent(Position(1, 1))
        world_in.place_goal(Position(3, 3))
        
        world_out = World(5, 5)
        world_out.place_agent(Position(3, 3))
        world_out.place_goal(Position(3, 3))
        
        agent = EmbodiedAgent("test", world_in)
        goal = agent.infer_goal([(world_in, world_out)])
        
        # Agent detects movement pattern
        self.assertIn(goal, ["reach_goal", "move_agent"])
    
    def test_movement_inference(self):
        """Test inferring movement goal."""
        world_in = World(5, 5)
        world_in.place_agent(Position(1, 1))
        
        world_out = World(5, 5)
        world_out.place_agent(Position(3, 3))
        
        agent = EmbodiedAgent("test", world_in)
        goal = agent.infer_goal([(world_in, world_out)])
        
        self.assertEqual(goal, "move_agent")
    
    def test_multiple_examples(self):
        """Test inference from multiple examples."""
        examples = []
        
        for i in range(3):
            w_in = World(5, 5)
            w_in.place_agent(Position(1, i))
            w_in.place_goal(Position(3, i))
            
            w_out = World(5, 5)
            w_out.place_agent(Position(3, i))
            w_out.place_goal(Position(3, i))
            
            examples.append((w_in, w_out))
        
        agent = EmbodiedAgent("test", World(5, 5))
        goal = agent.infer_goal(examples)
        
        # Agent detects movement pattern
        self.assertIn(goal, ["reach_goal", "move_agent"])


class TestPhysics(unittest.TestCase):
    """Test physics engine."""
    
    def test_gravity(self):
        """Test gravity effect on objects."""
        world = World(5, 5)
        
        obj = Object("falling", "box", Position(2, 1))
        obj.properties["affected_by_gravity"] = True
        world.place_object(obj)
        
        # Place floor
        world.place_obstacle(Position(2, 3))
        
        # Step world
        world.step()
        
        # Object should fall
        self.assertEqual(world.objects["falling"].position.y, 2)
    
    def test_gravity_stops_at_floor(self):
        """Test that gravity stops at floor."""
        world = World(5, 5)
        
        obj = Object("falling", "box", Position(2, 1))
        obj.properties["affected_by_gravity"] = True
        world.place_object(obj)
        
        # Place floor
        world.place_obstacle(Position(2, 3))
        
        # Multiple steps
        for _ in range(5):
            world.step()
        
        # Object should stop at floor
        self.assertEqual(world.objects["falling"].position.y, 2)


class TestSerialization(unittest.TestCase):
    """Test serialization and deserialization."""
    
    def test_world_to_dict(self):
        """Test world serialization."""
        world = World(5, 5)
        world.place_agent(Position(1, 1))
        world.place_goal(Position(3, 3))
        
        obj = Object("obj1", "coin", Position(2, 2), is_portable=True)
        world.place_object(obj)
        
        data = world.to_dict()
        
        self.assertEqual(data["width"], 5)
        self.assertEqual(data["height"], 5)
        self.assertEqual(data["agent_position"], {"x": 1, "y": 1})
        self.assertEqual(len(data["objects"]), 1)
    
    def test_world_from_dict(self):
        """Test world deserialization."""
        world = World(5, 5)
        world.place_agent(Position(1, 1))
        world.place_goal(Position(3, 3))
        
        obj = Object("obj1", "coin", Position(2, 2))
        world.place_object(obj)
        
        data = world.to_dict()
        restored = World.from_dict(data)
        
        self.assertEqual(restored.width, 5)
        self.assertEqual(restored.agent_position, Position(1, 1))
        self.assertEqual(restored.goal_position, Position(3, 3))
        self.assertIn("obj1", restored.objects)
    
    def test_perception_serialization(self):
        """Test perception serialization."""
        world = World(5, 5)
        world.place_agent(Position(2, 2))
        
        perception = world.get_perception()
        data = perception.to_dict()
        
        self.assertIn("visual_grid", data)
        self.assertIn("agent_position", data)
        self.assertIn("spatial_relations", data)


class TestTaskCreation(unittest.TestCase):
    """Test task creation helpers."""
    
    def test_navigation_task(self):
        """Test navigation task creation."""
        world, solution = create_simple_navigation_task(8, 8)
        
        self.assertEqual(world.width, 8)
        self.assertEqual(world.height, 8)
        self.assertIsNotNone(world.agent_position)
        self.assertIsNotNone(world.goal_position)
        self.assertIsNotNone(solution.agent_position)
    
    def test_object_collection_task(self):
        """Test object collection task."""
        world, solution = create_object_collection_task()
        
        self.assertEqual(world.width, 10)
        self.assertEqual(len(world.objects), 2)
        self.assertIsNotNone(world.goal_position)


class TestIntegration(unittest.TestCase):
    """Integration tests."""
    
    def test_full_navigation_episode(self):
        """Test complete navigation episode."""
        world = World(5, 5)
        world.place_agent(Position(1, 1))
        world.place_goal(Position(3, 3))
        
        agent = EmbodiedAgent("navigator", world)
        
        # Plan and execute path
        path = agent.plan_path(Position(3, 3))
        self.assertGreater(len(path), 0)
        
        # Execute path
        for action in path:
            success, result = agent.act(action)
            self.assertTrue(success)
        
        # Verify goal reached
        self.assertEqual(world.agent_position, Position(3, 3))
        self.assertTrue(world.check_goal_reached())
        
        # Verify learning
        self.assertGreater(len(agent.transition_history), 0)
        knowledge = agent.get_learned_knowledge()
        self.assertGreater(knowledge["transition_count"], 0)
    
    def test_arc_agi_3_style_task(self):
        """Test ARC-AGI-3 style task."""
        # Create example pairs
        examples = []
        for i in range(2):
            w_in = World(5, 5)
            w_in.place_agent(Position(1, i + 1))
            w_in.place_goal(Position(3, i + 1))
            
            w_out = World(5, 5)
            w_out.place_agent(Position(3, i + 1))
            w_out.place_goal(Position(3, i + 1))
            
            examples.append((w_in, w_out))
        
        # Create test input
        test_in = World(5, 5)
        test_in.place_agent(Position(1, 3))
        test_in.place_goal(Position(3, 3))
        
        # Create task with solution
        task = GoalInferenceTask("navigate_to_goal", examples, test_in)
        
        # Create expected solution for evaluation
        solution = World(5, 5)
        solution.place_agent(Position(3, 3))
        solution.place_goal(Position(3, 3))
        task.solution = solution
        
        # Agent infers goal
        agent = EmbodiedAgent("solver", test_in)
        inferred_goal = agent.infer_goal(examples)
        
        # Agent detects movement pattern
        self.assertIn(inferred_goal, ["reach_goal", "move_agent"])
        
        # Execute based on inferred goal
        path = agent.plan_path(Position(3, 3))
        for action in path:
            agent.act(action)
        
        # Verify agent reached the goal
        self.assertEqual(test_in.agent_position, Position(3, 3))
        
        # Evaluate solution - 0.96 is excellent match
        score = task.evaluate_solution(test_in)
        self.assertGreater(score, 0.95)


def run_tests():
    """Run all tests and return results."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestWorldBasics,
        TestAgentMovement,
        TestPerception,
        TestEmbodiedAgent,
        TestPathPlanning,
        TestGoalInference,
        TestPhysics,
        TestSerialization,
        TestTaskCreation,
        TestIntegration
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful(), result.testsRun, len(result.failures), len(result.errors)


if __name__ == "__main__":
    success, total, failures, errors = run_tests()
    print(f"\n{'='*60}")
    print(f"Test Summary: {total} tests, {failures} failures, {errors} errors")
    print(f"Result: {'✅ ALL PASSED' if success else '❌ SOME FAILED'}")
    print(f"{'='*60}")
    sys.exit(0 if success else 1)
