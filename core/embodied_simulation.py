"""
Embodied AI Simulation Layer

Provides a virtual environment for agent interaction, physical reasoning,
and goal inference capabilities inspired by ARC-AGI-3 and embodied AI research.

Key Features:
- Grid-world environment with objects and physics
- Multi-modal perception (visual, spatial, relational)
- Action-effect learning through interaction
- Goal inference from observations
- Sim-to-real transfer preparation

Research Basis:
- Meta/ARI: Physical world training for AGI
- ARC-AGI-3: Goal inference without explicit instructions
- SMGI: Structural theory of general intelligence
"""

from enum import Enum, auto
from typing import Dict, List, Tuple, Optional, Set, Any, Callable
from dataclasses import dataclass, field
from copy import deepcopy
import json
import random
from abc import ABC, abstractmethod


class CellType(Enum):
    """Types of cells in the grid world."""
    EMPTY = 0
    AGENT = 1
    OBSTACLE = 2
    GOAL = 3
    OBJECT = 4
    INTERACTIVE = 5


class ActionType(Enum):
    """Possible actions in the environment."""
    MOVE_UP = auto()
    MOVE_DOWN = auto()
    MOVE_LEFT = auto()
    MOVE_RIGHT = auto()
    INTERACT = auto()
    PICKUP = auto()
    DROP = auto()
    WAIT = auto()


@dataclass
class Position:
    """2D position in the grid."""
    x: int
    y: int
    
    def __add__(self, other: 'Position') -> 'Position':
        return Position(self.x + other.x, self.y + other.y)
    
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Position):
            return False
        return self.x == other.x and self.y == other.y
    
    def __hash__(self) -> int:
        return hash((self.x, self.y))
    
    def manhattan_distance(self, other: 'Position') -> int:
        return abs(self.x - other.x) + abs(self.y - other.y)


@dataclass
class Object:
    """An object in the environment."""
    id: str
    obj_type: str
    position: Position
    properties: Dict[str, Any] = field(default_factory=dict)
    is_portable: bool = False
    is_interactive: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.obj_type,
            "position": {"x": self.position.x, "y": self.position.y},
            "properties": self.properties,
            "portable": self.is_portable,
            "interactive": self.is_interactive
        }


@dataclass
class Action:
    """An action with preconditions and effects."""
    action_type: ActionType
    target_position: Optional[Position] = None
    object_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "type": self.action_type.name,
            "target": {"x": self.target_position.x, "y": self.target_position.y} if self.target_position else None,
            "object": self.object_id
        }


@dataclass
class Perception:
    """Multi-modal perception of the environment."""
    visual_grid: List[List[int]]  # What the agent sees
    agent_position: Position
    nearby_objects: List[Object]
    spatial_relations: Dict[str, List[str]]  # e.g., {"left": ["wall", "door"]}
    proprioception: Dict[str, Any]  # Agent's own state
    
    def to_dict(self) -> Dict:
        return {
            "visual_grid": self.visual_grid,
            "agent_position": {"x": self.agent_position.x, "y": self.agent_position.y},
            "nearby_objects": [obj.to_dict() for obj in self.nearby_objects],
            "spatial_relations": self.spatial_relations,
            "proprioception": self.proprioception
        }


@dataclass
class Transition:
    """State transition for learning action effects."""
    state_before: Dict
    action: Action
    state_after: Dict
    reward: float
    terminated: bool
    timestamp: int


class PhysicsEngine:
    """Simple physics for the simulation."""
    
    def __init__(self):
        self.gravity = True
        self.collision_enabled = True
        self.pushable_objects: Set[str] = set()
    
    def apply_gravity(self, world: 'World') -> List[Tuple[str, Position, Position]]:
        """Apply gravity to objects. Returns list of (object_id, old_pos, new_pos)."""
        movements = []
        for obj in world.objects.values():
            if obj.properties.get("affected_by_gravity", False):
                new_y = obj.position.y + 1
                if new_y < world.height and world.grid[new_y][obj.position.x] == CellType.EMPTY:
                    old_pos = obj.position
                    obj.position = Position(obj.position.x, new_y)
                    movements.append((obj.id, old_pos, obj.position))
        return movements
    
    def check_collision(self, world: 'World', pos: Position) -> bool:
        """Check if position is collidable."""
        if not world.is_valid_position(pos):
            return True
        cell = world.grid[pos.y][pos.x]
        return cell in [CellType.OBSTACLE]


class World:
    """The simulated environment."""
    
    def __init__(self, width: int = 10, height: int = 10):
        self.width = width
        self.height = height
        self.grid: List[List[CellType]] = [[CellType.EMPTY for _ in range(width)] for _ in range(height)]
        self.objects: Dict[str, Object] = {}
        self.agent_position: Optional[Position] = None
        self.goal_position: Optional[Position] = None
        self.physics = PhysicsEngine()
        self.history: List[Dict] = []
        self.step_count = 0
        
    def is_valid_position(self, pos: Position) -> bool:
        """Check if position is within bounds."""
        return 0 <= pos.x < self.width and 0 <= pos.y < self.height
    
    def get_cell(self, pos: Position) -> CellType:
        """Get cell type at position."""
        if not self.is_valid_position(pos):
            return CellType.OBSTACLE
        return self.grid[pos.y][pos.x]
    
    def set_cell(self, pos: Position, cell_type: CellType):
        """Set cell type at position."""
        if self.is_valid_position(pos):
            self.grid[pos.y][pos.x] = cell_type
    
    def place_agent(self, pos: Position) -> bool:
        """Place agent at position."""
        if self.is_valid_position(pos) and self.grid[pos.y][pos.x] == CellType.EMPTY:
            if self.agent_position:
                self.set_cell(self.agent_position, CellType.EMPTY)
            self.agent_position = pos
            self.set_cell(pos, CellType.AGENT)
            return True
        return False
    
    def place_object(self, obj: Object) -> bool:
        """Place object in world."""
        if self.is_valid_position(obj.position) and self.grid[obj.position.y][obj.position.x] == CellType.EMPTY:
            self.objects[obj.id] = obj
            cell_type = CellType.INTERACTIVE if obj.is_interactive else CellType.OBJECT
            self.set_cell(obj.position, cell_type)
            return True
        return False
    
    def place_goal(self, pos: Position) -> bool:
        """Place goal at position."""
        if self.is_valid_position(pos):
            self.goal_position = pos
            self.set_cell(pos, CellType.GOAL)
            return True
        return False
    
    def place_obstacle(self, pos: Position) -> bool:
        """Place obstacle at position."""
        if self.is_valid_position(pos) and self.grid[pos.y][pos.x] == CellType.EMPTY:
            self.set_cell(pos, CellType.OBSTACLE)
            return True
        return False
    
    def move_agent(self, direction: Position) -> Tuple[bool, str]:
        """Move agent in direction. Returns (success, message)."""
        if not self.agent_position:
            return False, "No agent in world"
        
        new_pos = self.agent_position + direction
        
        # Check bounds
        if not self.is_valid_position(new_pos):
            return False, "Out of bounds"
        
        # Check collision
        cell = self.get_cell(new_pos)
        if cell == CellType.OBSTACLE:
            return False, "Collision with obstacle"
        
        # Move agent
        self.set_cell(self.agent_position, CellType.EMPTY)
        self.agent_position = new_pos
        self.set_cell(new_pos, CellType.AGENT)
        
        return True, "Moved successfully"
    
    def get_perception(self, view_distance: int = 3) -> Perception:
        """Get agent's perception of the environment."""
        if not self.agent_position:
            raise ValueError("No agent in world")
        
        # Visual grid (what agent sees)
        visual_grid = []
        for dy in range(-view_distance, view_distance + 1):
            row = []
            for dx in range(-view_distance, view_distance + 1):
                pos = Position(self.agent_position.x + dx, self.agent_position.y + dy)
                if self.is_valid_position(pos):
                    row.append(self.grid[pos.y][pos.x].value)
                else:
                    row.append(-1)  # Out of bounds
            visual_grid.append(row)
        
        # Nearby objects
        nearby = []
        for obj in self.objects.values():
            if obj.position.manhattan_distance(self.agent_position) <= view_distance:
                nearby.append(obj)
        
        # Spatial relations
        relations = {"up": [], "down": [], "left": [], "right": []}
        directions = {
            "up": Position(0, -1),
            "down": Position(0, 1),
            "left": Position(-1, 0),
            "right": Position(1, 0)
        }
        for name, delta in directions.items():
            check_pos = self.agent_position + delta
            if self.is_valid_position(check_pos):
                cell = self.get_cell(check_pos)
                if cell != CellType.EMPTY:
                    relations[name].append(cell.name.lower())
                for obj in self.objects.values():
                    if obj.position == check_pos:
                        relations[name].append(obj.obj_type)
        
        # Proprioception
        proprioception = {
            "position": {"x": self.agent_position.x, "y": self.agent_position.y},
            "step_count": self.step_count,
            "carrying": None  # Could track carried objects
        }
        
        return Perception(
            visual_grid=visual_grid,
            agent_position=self.agent_position,
            nearby_objects=nearby,
            spatial_relations=relations,
            proprioception=proprioception
        )
    
    def step(self) -> Dict:
        """Advance simulation by one step. Apply physics, update state."""
        self.step_count += 1
        
        # Apply physics
        movements = self.physics.apply_gravity(self)
        
        # Record history
        state = {
            "step": self.step_count,
            "agent_pos": {"x": self.agent_position.x, "y": self.agent_position.y} if self.agent_position else None,
            "object_positions": {oid: {"x": obj.position.x, "y": obj.position.y} for oid, obj in self.objects.items()},
            "movements": [(oid, {"x": old.x, "y": old.y}, {"x": new.x, "y": new.y}) for oid, old, new in movements]
        }
        self.history.append(state)
        
        return state
    
    def check_goal_reached(self) -> bool:
        """Check if agent reached goal."""
        if not self.agent_position or not self.goal_position:
            return False
        return self.agent_position == self.goal_position
    
    def to_dict(self) -> Dict:
        """Serialize world state."""
        return {
            "width": self.width,
            "height": self.height,
            "agent_position": {"x": self.agent_position.x, "y": self.agent_position.y} if self.agent_position else None,
            "goal_position": {"x": self.goal_position.x, "y": self.goal_position.y} if self.goal_position else None,
            "objects": [obj.to_dict() for obj in self.objects.values()],
            "step_count": self.step_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'World':
        """Deserialize world state."""
        world = cls(data["width"], data["height"])
        
        if data.get("agent_position"):
            world.place_agent(Position(data["agent_position"]["x"], data["agent_position"]["y"]))
        
        if data.get("goal_position"):
            world.place_goal(Position(data["goal_position"]["x"], data["goal_position"]["y"]))
        
        for obj_data in data.get("objects", []):
            obj = Object(
                id=obj_data["id"],
                obj_type=obj_data["type"],
                position=Position(obj_data["position"]["x"], obj_data["position"]["y"]),
                properties=obj_data.get("properties", {}),
                is_portable=obj_data.get("portable", False),
                is_interactive=obj_data.get("interactive", False)
            )
            world.place_object(obj)
        
        world.step_count = data.get("step_count", 0)
        return world


class GoalInferenceTask:
    """
    ARC-AGI-3 style task where agent must infer goal from observations.
    Agent sees example input-output pairs and must determine the transformation.
    """
    
    def __init__(self, name: str, examples: List[Tuple[World, World]], test_input: World):
        self.name = name
        self.examples = examples  # (input_world, output_world) pairs
        self.test_input = test_input
        self.solution: Optional[World] = None
        
    def evaluate_solution(self, agent_output: World) -> float:
        """Evaluate how close agent's solution is to expected output."""
        if not self.solution:
            return 0.0
        
        # Compare grid states
        correct_cells = 0
        total_cells = self.solution.width * self.solution.height
        
        for y in range(self.solution.height):
            for x in range(self.solution.width):
                if agent_output.grid[y][x] == self.solution.grid[y][x]:
                    correct_cells += 1
        
        return correct_cells / total_cells
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "examples": [
                {"input": inp.to_dict(), "output": out.to_dict()}
                for inp, out in self.examples
            ],
            "test_input": self.test_input.to_dict()
        }


class EmbodiedAgent:
    """
    An agent that can interact with the embodied simulation.
    Learns action effects and performs goal inference.
    """
    
    def __init__(self, agent_id: str, world: World):
        self.agent_id = agent_id
        self.world = world
        self.transition_history: List[Transition] = []
        self.action_effects: Dict[ActionType, List[Dict]] = {}
        self.learned_policies: Dict[str, Callable] = {}
        self.current_task: Optional[GoalInferenceTask] = None
        
    def perceive(self) -> Perception:
        """Get current perception."""
        return self.world.get_perception()
    
    def act(self, action: Action) -> Tuple[bool, Dict]:
        """Execute action and observe result."""
        # Record state before
        state_before = self.world.to_dict()
        
        # Execute action
        success = False
        message = ""
        
        if action.action_type == ActionType.MOVE_UP:
            success, message = self.world.move_agent(Position(0, -1))
        elif action.action_type == ActionType.MOVE_DOWN:
            success, message = self.world.move_agent(Position(0, 1))
        elif action.action_type == ActionType.MOVE_LEFT:
            success, message = self.world.move_agent(Position(-1, 0))
        elif action.action_type == ActionType.MOVE_RIGHT:
            success, message = self.world.move_agent(Position(1, 0))
        elif action.action_type == ActionType.WAIT:
            success, message = True, "Waited"
        else:
            message = f"Action {action.action_type} not implemented"
        
        # Advance world step
        self.world.step()
        
        # Record state after
        state_after = self.world.to_dict()
        
        # Calculate reward
        reward = self._calculate_reward(success)
        
        # Check if goal reached
        terminated = self.world.check_goal_reached()
        
        # Record transition
        transition = Transition(
            state_before=state_before,
            action=action,
            state_after=state_after,
            reward=reward,
            terminated=terminated,
            timestamp=self.world.step_count
        )
        self.transition_history.append(transition)
        
        # Learn action effects
        self._learn_action_effect(action, state_before, state_after)
        
        return success, {
            "message": message,
            "reward": reward,
            "terminated": terminated,
            "perception": self.perceive().to_dict()
        }
    
    def _calculate_reward(self, action_success: bool) -> float:
        """Calculate reward for action."""
        reward = 0.0
        
        if action_success:
            reward += 0.1
        
        # Reward for reaching goal
        if self.world.check_goal_reached():
            reward += 10.0
        
        # Reward for moving closer to goal
        elif self.world.agent_position and self.world.goal_position:
            distance = self.world.agent_position.manhattan_distance(self.world.goal_position)
            reward += max(0, (10 - distance) * 0.05)
        
        return reward
    
    def _learn_action_effect(self, action: Action, before: Dict, after: Dict):
        """Learn the effect of an action."""
        effect = {
            "agent_moved": False,
            "objects_moved": [],
            "goal_reached": False
        }
        
        # Check if agent moved
        if before.get("agent_position") != after.get("agent_position"):
            effect["agent_moved"] = True
        
        # Check goal
        if self.world.check_goal_reached():
            effect["goal_reached"] = True
        
        # Store effect
        if action.action_type not in self.action_effects:
            self.action_effects[action.action_type] = []
        self.action_effects[action.action_type].append(effect)
    
    def infer_goal(self, examples: List[Tuple[World, World]]) -> str:
        """
        Infer goal from example input-output pairs.
        ARC-AGI-3 style goal inference.
        """
        patterns = []
        
        for inp, out in examples:
            # Analyze transformation
            diff = self._analyze_transformation(inp, out)
            patterns.append(diff)
        
        # Find common pattern
        if patterns:
            return self._synthesize_goal(patterns)
        
        return "unknown"
    
    def _analyze_transformation(self, before: World, after: World) -> Dict:
        """Analyze what changed between two world states."""
        changes = {
            "agent_moved": False,
            "objects_moved": [],
            "grid_changes": []
        }
        
        # Check agent movement
        if before.agent_position != after.agent_position:
            changes["agent_moved"] = True
        
        # Check object movements
        for obj_id in before.objects:
            if obj_id in after.objects:
                if before.objects[obj_id].position != after.objects[obj_id].position:
                    changes["objects_moved"].append(obj_id)
        
        # Check grid changes
        for y in range(min(before.height, after.height)):
            for x in range(min(before.width, after.width)):
                if before.grid[y][x] != after.grid[y][x]:
                    changes["grid_changes"].append({
                        "pos": {"x": x, "y": y},
                        "from": before.grid[y][x].name,
                        "to": after.grid[y][x].name
                    })
        
        return changes
    
    def _synthesize_goal(self, patterns: List[Dict]) -> str:
        """Synthesize goal description from observed patterns."""
        # Simple pattern matching
        all_agent_moved = all(p["agent_moved"] for p in patterns)
        all_goal_reached = all(self.world.check_goal_reached() for p in patterns)
        
        if all_goal_reached:
            return "reach_goal"
        elif all_agent_moved:
            return "move_agent"
        elif any(p["objects_moved"] for p in patterns):
            return "move_objects"
        else:
            return "unknown_transformation"
    
    def plan_path(self, target: Position) -> List[Action]:
        """Plan a path to target using BFS."""
        if not self.world.agent_position:
            return []
        
        start = self.world.agent_position
        
        # BFS
        queue = [(start, [])]
        visited = {start}
        
        directions = [
            (Position(0, -1), ActionType.MOVE_UP),
            (Position(0, 1), ActionType.MOVE_DOWN),
            (Position(-1, 0), ActionType.MOVE_LEFT),
            (Position(1, 0), ActionType.MOVE_RIGHT)
        ]
        
        while queue:
            pos, path = queue.pop(0)
            
            if pos == target:
                return path
            
            for delta, action_type in directions:
                new_pos = pos + delta
                
                if new_pos in visited:
                    continue
                
                if not self.world.is_valid_position(new_pos):
                    continue
                
                if self.world.get_cell(new_pos) == CellType.OBSTACLE:
                    continue
                
                visited.add(new_pos)
                new_path = path + [Action(action_type)]
                queue.append((new_pos, new_path))
        
        return []  # No path found
    
    def get_learned_knowledge(self) -> Dict:
        """Get learned knowledge summary."""
        return {
            "action_effects": {
                action.name: effects[-10:] if len(effects) > 10 else effects
                for action, effects in self.action_effects.items()
            },
            "transition_count": len(self.transition_history),
            "learned_policies": list(self.learned_policies.keys())
        }


def create_simple_navigation_task(width: int = 8, height: int = 8) -> Tuple[World, World]:
    """Create a simple navigation task."""
    # Input world
    world = World(width, height)
    
    # Place agent and goal
    world.place_agent(Position(1, 1))
    world.place_goal(Position(width - 2, height - 2))
    
    # Add some obstacles
    for x in range(2, width - 2):
        world.place_obstacle(Position(x, 3))
    
    # Create solution (world with agent at goal)
    solution = World(width, height)
    solution.place_agent(Position(width - 2, height - 2))
    solution.place_goal(Position(width - 2, height - 2))
    for x in range(2, width - 2):
        solution.place_obstacle(Position(x, 3))
    
    return world, solution


def create_object_collection_task() -> Tuple[World, World]:
    """Create a task where agent must collect objects."""
    world = World(10, 10)
    
    # Place agent
    world.place_agent(Position(1, 1))
    
    # Place objects to collect
    obj1 = Object("coin1", "coin", Position(3, 3), is_portable=True)
    obj2 = Object("coin2", "coin", Position(7, 7), is_portable=True)
    world.place_object(obj1)
    world.place_object(obj2)
    
    # Place goal
    world.place_goal(Position(8, 8))
    
    # Solution: agent at goal with coins collected
    solution = World(10, 10)
    solution.place_agent(Position(8, 8))
    solution.place_goal(Position(8, 8))
    
    return world, solution


# Export main classes
__all__ = [
    'World',
    'EmbodiedAgent',
    'GoalInferenceTask',
    'Perception',
    'Action',
    'ActionType',
    'Position',
    'Object',
    'CellType',
    'PhysicsEngine',
    'Transition',
    'create_simple_navigation_task',
    'create_object_collection_task'
]
