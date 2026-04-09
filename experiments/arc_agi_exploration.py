"""
ARC-AGI-3 Style Exploration Environment

Based on arXiv:2603.24621v1 - ARC-AGI-3 benchmark insights:
- Humans: 100%, Frontier AI: <1% on abstract reasoning tasks
- Tests fluid adaptive efficiency over scale
- Abstract turn-based environments with NO explicit instructions
- Agents must infer goals from core priors alone

Core priors (innate human intuitions):
1. Objectness - bounded, persistent entities
2. Goal-directedness - agents act toward objectives
3. Agentness - other entities have mental states
4. Natural numbers and basic geometry
5. Elementary physics (containment, support, etc.)
"""

from typing import List, Dict, Any, Optional, Tuple, Callable, Set
from dataclasses import dataclass, field
from enum import Enum, auto
import json
import random
import copy
from datetime import datetime


class CellType(Enum):
    """Abstract cell types - agents must infer meaning from patterns."""
    EMPTY = 0
    AGENT = 1  # The agent's current position
    OBSTACLE = 2  # Impassable
    GOAL_MARKER = 3  # Hint of objective location
    RESOURCE = 4  # Collectible
    INTERACTIVE = 5  # Can be manipulated
    HAZARD = 6  # Dangerous
    PORTAL = 7  # Transports elsewhere


class Action(Enum):
    """Basic actions - semantics depend on context."""
    MOVE_NORTH = auto()
    MOVE_SOUTH = auto()
    MOVE_EAST = auto()
    MOVE_WEST = auto()
    INTERACT = auto()  # Context-dependent action
    WAIT = auto()
    EXPLORE = auto()  # Systematic unknown-cell exploration


@dataclass
class Observation:
    """What the agent perceives - limited, local view."""
    grid_view: List[List[int]]  # Local 5x5 or 7x7 view
    position: Tuple[int, int]
    inventory: Dict[str, int]
    step_count: int
    energy: float  # Depletes with actions
    recent_events: List[str] = field(default_factory=list)


@dataclass
class CorePrior:
    """
    Innate intuitive understanding that humans apply automatically.
    Agents must develop equivalent through exploration.
    """
    name: str
    description: str
    activation_pattern: Callable[[Any], float]  # Returns confidence 0-1
    
    # Examples of this prior in action
    test_cases: List[Dict] = field(default_factory=list)


@dataclass
class ExplorationHypothesis:
    """Agent's working theory about the environment."""
    id: str
    description: str
    confidence: float  # 0.0 to 1.0
    evidence: List[Dict] = field(default_factory=list)
    contradictions: List[Dict] = field(default_factory=list)
    predictions: List[str] = field(default_factory=list)
    
    def update_confidence(self, new_evidence: Dict):
        """Bayesian-like confidence update."""
        if new_evidence.get("supports"):
            self.confidence = min(1.0, self.confidence + 0.1)
            self.evidence.append(new_evidence)
        else:
            self.confidence = max(0.0, self.confidence - 0.15)
            self.contradictions.append(new_evidence)


@dataclass
class ExplorationSession:
    """Complete exploration episode."""
    environment_id: str
    start_time: datetime
    actions_taken: List[Tuple[Action, Any]] = field(default_factory=list)
    observations: List[Observation] = field(default_factory=list)
    hypotheses_formed: List[ExplorationHypothesis] = field(default_factory=list)
    goals_inferred: List[str] = field(default_factory=list)
    success: Optional[bool] = None
    final_score: float = 0.0


class AbstractGridEnvironment:
    """
    Abstract grid world where agents explore without explicit instructions.
    Similar to ARC-AGI pattern: infer the transformation rule from examples.
    """
    
    def __init__(self, width: int = 20, height: int = 20, 
                 visibility_radius: int = 3, max_steps: int = 100):
        self.width = width
        self.height = height
        self.visibility_radius = visibility_radius
        self.max_steps = max_steps
        
        # Grid: abstract cells
        self.grid: List[List[CellType]] = []
        self.agent_pos: Tuple[int, int] = (0, 0)
        self.goal_positions: Set[Tuple[int, int]] = set()
        self.resource_positions: Set[Tuple[int, int]] = set()
        self.interactive_positions: Set[Tuple[int, int]] = set()
        
        # Hidden state - agent must infer
        self._true_goal: Optional[str] = None
        self._reward_function: Optional[Callable] = None
        
        # Step tracking
        self.step_count = 0
        self.energy = 100.0
        self.inventory: Dict[str, int] = {}
        self.event_log: List[str] = []
        
    def generate_task(self, task_type: str = "unknown"):
        """
        Generate an abstract task without telling the agent what to do.
        Task types remain implicit - agent must infer from structure.
        """
        self.grid = [[CellType.EMPTY for _ in range(self.width)] 
                     for _ in range(self.height)]
        
        # Place agent randomly
        self.agent_pos = (random.randint(1, self.height-2), 
                         random.randint(1, self.width-2))
        self._set_cell(self.agent_pos, CellType.AGENT)
        
        # Generate different implicit task structures
        if task_type == "collection":
            self._setup_collection_task()
        elif task_type == "navigation":
            self._setup_navigation_task()
        elif task_type == "manipulation":
            self._setup_manipulation_task()
        elif task_type == "avoidance":
            self._setup_avoidance_task()
        else:
            # Random combination - agent must figure out which applies
            task_choices = ["collection", "navigation", "manipulation", "avoidance"]
            selected = random.choice(task_choices)
            getattr(self, f"_setup_{selected}_task")()
            
        self._true_goal = task_type
        
    def _setup_collection_task(self):
        """Agent must collect resources to implicit goal zone."""
        # Scatter resources
        for _ in range(random.randint(3, 8)):
            pos = self._random_empty_position()
            self._set_cell(pos, CellType.RESOURCE)
            self.resource_positions.add(pos)
            
        # Create goal zone (subtle marker)
        goal_x = random.randint(self.width//2, self.width-2)
        goal_y = random.randint(1, self.height-2)
        self._set_cell((goal_y, goal_x), CellType.GOAL_MARKER)
        self.goal_positions.add((goal_y, goal_x))
        
        self._reward_function = lambda: self.inventory.get("resource", 0) * 10
        
    def _setup_navigation_task(self):
        """Agent must find path to distant goal."""
        # Create maze-like obstacles
        for _ in range(self.width * self.height // 8):
            pos = self._random_empty_position()
            if self._manhattan_dist(pos, self.agent_pos) > 3:  # Not too close
                self._set_cell(pos, CellType.OBSTACLE)
                
        # Place distant goal
        far_pos = self._find_farthest_reachable()
        self._set_cell(far_pos, CellType.GOAL_MARKER)
        self.goal_positions.add(far_pos)
        
        self._reward_function = lambda: 100 if self.agent_pos in self.goal_positions else 0
        
    def _setup_manipulation_task(self):
        """Agent must manipulate interactive elements."""
        # Place interactive objects in pattern
        for i in range(3):
            pos = (self.height // 2, 3 + i * 4)
            if self._in_bounds(pos):
                self._set_cell(pos, CellType.INTERACTIVE)
                self.interactive_positions.add(pos)
                
        # Goal behind interactives
        goal_pos = (self.height // 2, self.width - 3)
        self._set_cell(goal_pos, CellType.GOAL_MARKER)
        self.goal_positions.add(goal_pos)
        
        self._reward_function = lambda: 50 * self.inventory.get("activated", 0)
        
    def _setup_avoidance_task(self):
        """Agent must reach goal while avoiding hazards."""
        # Place hazards in path
        mid_y = self.height // 2
        for x in range(2, self.width - 2):
            if random.random() < 0.3:
                self._set_cell((mid_y, x), CellType.HAZARD)
                
        # Safe path above or below
        safe_y = mid_y - 2 if random.random() < 0.5 else mid_y + 2
        
        # Goal at end
        goal_pos = (safe_y, self.width - 3)
        self._set_cell(goal_pos, CellType.GOAL_MARKER)
        self.goal_positions.add(goal_pos)
        
        self._reward_function = lambda: (100 if self.agent_pos in self.goal_positions else 0) \
                                       - (50 if self.energy < 50 else 0)
    
    def _set_cell(self, pos: Tuple[int, int], cell_type: CellType):
        if self._in_bounds(pos):
            self.grid[pos[0]][pos[1]] = cell_type
            
    def _get_cell(self, pos: Tuple[int, int]) -> CellType:
        if self._in_bounds(pos):
            return self.grid[pos[0]][pos[1]]
        return CellType.OBSTACLE  # Out of bounds = obstacle
        
    def _in_bounds(self, pos: Tuple[int, int]) -> bool:
        return 0 <= pos[0] < self.height and 0 <= pos[1] < self.width
        
    def _random_empty_position(self) -> Tuple[int, int]:
        while True:
            pos = (random.randint(0, self.height-1), 
                  random.randint(0, self.width-1))
            if self._get_cell(pos) == CellType.EMPTY:
                return pos
                
    def _manhattan_dist(self, a: Tuple[int, int], b: Tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])
        
    def _find_farthest_reachable(self) -> Tuple[int, int]:
        """Find position far from agent (for navigation tasks)."""
        corners = [
            (1, 1), (1, self.width-2),
            (self.height-2, 1), (self.height-2, self.width-2)
        ]
        return max(corners, key=lambda c: self._manhattan_dist(c, self.agent_pos))
    
    def get_observation(self) -> Observation:
        """Return local visibility - agent must explore to see full picture."""
        y, x = self.agent_pos
        r = self.visibility_radius
        
        # Extract visible region
        view = []
        for dy in range(-r, r+1):
            row = []
            for dx in range(-r, r+1):
                check_pos = (y + dy, x + dx)
                if self._in_bounds(check_pos):
                    row.append(self._get_cell(check_pos).value)
                else:
                    row.append(-1)  # Out of bounds indicator
            view.append(row)
            
        return Observation(
            grid_view=view,
            position=self.agent_pos,
            inventory=copy.deepcopy(self.inventory),
            step_count=self.step_count,
            energy=self.energy,
            recent_events=self.event_log[-5:]  # Last 5 events
        )
    
    def execute_action(self, action: Action) -> Tuple[Observation, float, bool, Dict]:
        """
        Execute action, return (observation, reward, done, info).
        Agent must learn what actions do through exploration.
        """
        self.step_count += 1
        self.energy -= 1.0
        
        reward = 0.0
        info = {"action_result": "unknown"}
        
        old_pos = self.agent_pos
        new_pos = old_pos
        
        if action in [Action.MOVE_NORTH, Action.MOVE_SOUTH, 
                     Action.MOVE_EAST, Action.MOVE_WEST]:
            # Movement
            dy, dx = {
                Action.MOVE_NORTH: (-1, 0),
                Action.MOVE_SOUTH: (1, 0),
                Action.MOVE_EAST: (0, 1),
                Action.MOVE_WEST: (0, -1)
            }[action]
            
            new_pos = (old_pos[0] + dy, old_pos[1] + dx)
            
            # Check collision
            target_cell = self._get_cell(new_pos)
            if target_cell == CellType.OBSTACLE:
                self.event_log.append(f"Bump at step {self.step_count}")
                reward -= 1  # Penalty for hitting wall
                new_pos = old_pos  # Stay in place
                info["action_result"] = "blocked"
            elif target_cell == CellType.HAZARD:
                self.energy -= 20  # Major energy loss
                self.event_log.append(f"Hazard at step {self.step_count}")
                reward -= 10
                info["action_result"] = "hazard"
            elif target_cell == CellType.RESOURCE:
                # Auto-collect on move
                self.inventory["resource"] = self.inventory.get("resource", 0) + 1
                self.resource_positions.discard(new_pos)
                self._set_cell(new_pos, CellType.EMPTY)
                self.event_log.append(f"Collected at step {self.step_count}")
                reward += 5
                info["action_result"] = "collected"
            else:
                info["action_result"] = "moved"
                
        elif action == Action.INTERACT:
            # Interact with adjacent cells
            for dy, dx in [(-1,0), (1,0), (0,-1), (0,1)]:
                check_pos = (old_pos[0] + dy, old_pos[1] + dx)
                cell = self._get_cell(check_pos)
                
                if cell == CellType.INTERACTIVE:
                    self.inventory["activated"] = self.inventory.get("activated", 0) + 1
                    self.interactive_positions.discard(check_pos)
                    self._set_cell(check_pos, CellType.EMPTY)
                    self.event_log.append(f"Activated at step {self.step_count}")
                    reward += 10
                    info["action_result"] = "activated"
                    break
                elif cell == CellType.PORTAL:
                    # Teleport to random location
                    new_pos = self._random_empty_position()
                    self.event_log.append(f"Teleported at step {self.step_count}")
                    info["action_result"] = "teleported"
                    break
                    
        elif action == Action.EXPLORE:
            # Systematic exploration - find nearest unknown and move toward it
            # Simplified: just move toward edge of visibility
            info["action_result"] = "exploring"
            reward += 0.5  # Small reward for exploration
            
        # Update agent position
        if new_pos != old_pos:
            self._set_cell(old_pos, CellType.EMPTY)
            self.agent_pos = new_pos
            self._set_cell(new_pos, CellType.AGENT)
            
        # Check goal achievement
        if self.agent_pos in self.goal_positions:
            if self.inventory.get("resource", 0) >= 3 or \
               self._true_goal == "navigation":
                reward += 100
                self.event_log.append(f"Goal reached at step {self.step_count}")
                info["goal_achieved"] = True
                
        # Check termination
        done = False
        if self.step_count >= self.max_steps:
            done = True
            info["termination"] = "max_steps"
        elif self.energy <= 0:
            done = True
            info["termination"] = "energy_depleted"
        elif info.get("goal_achieved"):
            done = True
            info["termination"] = "success"
            
        # Apply reward function if set
        if self._reward_function:
            reward += self._reward_function()
            
        return self.get_observation(), reward, done, info
    
    def render_text(self) -> str:
        """ASCII visualization for debugging."""
        symbols = {
            CellType.EMPTY: "·",
            CellType.AGENT: "@",
            CellType.OBSTACLE: "█",
            CellType.GOAL_MARKER: "★",
            CellType.RESOURCE: "◆",
            CellType.INTERACTIVE: "□",
            CellType.HAZARD: "▲",
            CellType.PORTAL: "○"
        }
        lines = []
        for row in self.grid:
            lines.append("".join(symbols.get(c, "?") for c in row))
        return "\n".join(lines)


class CorePriorLibrary:
    """
    Library of core priors that humans (and good agents) use for exploration.
    Based on ARC priors: objectness, goal-directedness, numerosity, etc.
    """
    
    def __init__(self):
        self.priors: Dict[str, CorePrior] = {}
        self._initialize_priors()
        
    def _initialize_priors(self):
        """Define innate intuitive priors."""
        
        # Object persistence - things don't randomly disappear
        self.priors["object_persistence"] = CorePrior(
            name="object_persistence",
            description="Objects continue to exist when not observed",
            activation_pattern=self._detect_object_persistence
        )
        
        # Goal-directedness - agents act toward objectives
        self.priors["goal_directedness"] = CorePrior(
            name="goal_directedness",
            description="Agent's actions are purposeful, directed toward goals",
            activation_pattern=self._detect_goal_directedness
        )
        
        # Spatial continuity - smooth paths preferred
        self.priors["spatial_continuity"] = CorePrior(
            name="spatial_continuity",
            description="Movement is generally continuous in space",
            activation_pattern=self._detect_spatial_continuity
        )
        
        # Resource value - collectibles have utility
        self.priors["resource_value"] = CorePrior(
            name="resource_value",
            description="Collectible items are likely valuable",
            activation_pattern=self._detect_resource_value
        )
        
        # Hazard avoidance - dangerous things should be avoided
        self.priors["hazard_avoidance"] = CorePrior(
            name="hazard_avoidance",
            description="Entities that reduce energy are harmful",
            activation_pattern=self._detect_hazard_avoidance
        )
        
        # Pattern completion - environments have structure
        self.priors["pattern_completion"] = CorePrior(
            name="pattern_completion",
            description="Partial patterns can be completed systematically",
            activation_pattern=self._detect_pattern_completion
        )
        
    def _detect_object_persistence(self, history: List) -> float:
        """Check if agent tracks objects across time."""
        # High if agent revisits locations expecting objects
        return 0.7  # Placeholder
        
    def _detect_goal_directedness(self, history: List) -> float:
        """Check if agent shows persistent directed behavior."""
        return 0.6
        
    def _detect_spatial_continuity(self, history: List) -> float:
        """Check if agent moves smoothly vs jumping randomly."""
        return 0.8
        
    def _detect_resource_value(self, history: List) -> float:
        """Check if agent collects when possible."""
        return 0.5
        
    def _detect_hazard_avoidance(self, history: List) -> float:
        """Check if agent avoids energy-reducing events."""
        return 0.9 if any("Hazard" in str(h) for h in history[-3:]) else 0.3
        
    def _detect_pattern_completion(self, history: List) -> float:
        """Check if agent completes partial patterns."""
        return 0.4


class ExplorationAgent:
    """
    Agent that explores without explicit instructions.
    Forms hypotheses, tests predictions, adapts strategy.
    """
    
    def __init__(self, name: str = "Explorer"):
        self.name = name
        self.prior_library = CorePriorLibrary()
        self.hypotheses: List[ExplorationHypothesis] = []
        self.exploration_history: List[Dict] = []
        self.current_goal: Optional[str] = None
        
        # Mapping state
        self.known_map: Dict[Tuple[int, int], int] = {}
        self.visited_positions: Set[Tuple[int, int]] = set()
        
    def explore(self, env: AbstractGridEnvironment, 
                max_steps: int = None) -> ExplorationSession:
        """
        Main exploration loop - agent must figure out what to do.
        """
        session = ExplorationSession(
            environment_id=f"env_{random.randint(1000, 9999)}",
            start_time=datetime.now()
        )
        
        max_steps = max_steps or env.max_steps
        
        print(f"\n🔬 {self.name} starting exploration...")
        print(f"   Environment: {env.width}x{env.height}")
        print(f"   Max steps: {max_steps}")
        print(f"   No instructions provided - agent must infer goal.")
        print(f"   Visibility radius: {env.visibility_radius}")
        
        for step in range(max_steps):
            obs = env.get_observation()
            session.observations.append(obs)
            
            # Update internal map
            self._update_map(obs)
            self.visited_positions.add(obs.position)
            
            # Form/refine hypotheses
            if step % 5 == 0:  # Every 5 steps
                self._form_hypotheses(obs, session)
            
            # Select action based on current understanding
            action = self._select_action(obs, session)
            
            # Execute
            new_obs, reward, done, info = env.execute_action(action)
            
            session.actions_taken.append((action, info))
            
            # Learn from result
            self._learn_from_result(action, obs, new_obs, reward, info, session)
            
            if step % 10 == 0:
                print(f"   Step {step}: pos={obs.position}, "
                      f"energy={obs.energy:.1f}, "
                      f"inventory={obs.inventory}")
                if self.hypotheses:
                    top_hyp = max(self.hypotheses, key=lambda h: h.confidence)
                    print(f"      Top hypothesis: {top_hyp.description[:50]}...")
            
            if done:
                break
                
        # Evaluate success
        session.success = info.get("goal_achieved", False)
        session.final_score = self._calculate_score(env, session)
        session.hypotheses_formed = self.hypotheses
        
        print(f"\n✅ Exploration complete!")
        print(f"   Success: {session.success}")
        print(f"   Steps: {len(session.actions_taken)}")
        print(f"   Score: {session.final_score:.1f}")
        print(f"   Hypotheses formed: {len(session.hypotheses_formed)}")
        
        return session
    
    def _update_map(self, obs: Observation):
        """Integrate observation into internal world model."""
        y, x = obs.position
        r = len(obs.grid_view) // 2
        
        for dy, row in enumerate(obs.grid_view):
            for dx, cell_value in enumerate(row):
                world_y = y + (dy - r)
                world_x = x + (dx - r)
                if cell_value >= 0:  # Valid cell
                    self.known_map[(world_y, world_x)] = cell_value
    
    def _form_hypotheses(self, obs: Observation, session: ExplorationSession):
        """Generate hypotheses about environment structure."""
        # Check for collectibles
        if obs.inventory.get("resource", 0) > 0 and not any(
            h.description.startswith("Collect resources") for h in self.hypotheses
        ):
            h = ExplorationHypothesis(
                id=f"h_{len(self.hypotheses)}",
                description="Collect resources - they may be valuable for goal",
                confidence=0.5
            )
            self.hypotheses.append(h)
            
        # Check for hazards
        if any("Hazard" in e for e in obs.recent_events):
            if not any(h.description.startswith("Avoid hazards") for h in self.hypotheses):
                h = ExplorationHypothesis(
                    id=f"h_{len(self.hypotheses)}",
                    description="Avoid red markers - they reduce energy",
                    confidence=0.8
                )
                self.hypotheses.append(h)
                
        # Check for goal markers
        if any(CellType.GOAL_MARKER.value in row for row in obs.grid_view):
            if not any("★" in h.description or "star" in h.description.lower() 
                      for h in self.hypotheses):
                h = ExplorationHypothesis(
                    id=f"h_{len(self.hypotheses)}",
                    description="Reach the ★ marker - likely the goal",
                    confidence=0.6
                )
                self.hypotheses.append(h)
    
    def _select_action(self, obs: Observation, session: ExplorationSession) -> Action:
        """Choose next action based on current hypotheses."""
        # Simple heuristic strategy
        
        # If we see goal nearby, move toward it
        y, x = obs.position
        r = len(obs.grid_view) // 2
        
        for dy, row in enumerate(obs.grid_view):
            for dx, cell in enumerate(row):
                if cell == CellType.GOAL_MARKER.value:
                    # Goal visible!
                    goal_y = y + (dy - r)
                    goal_x = x + (dx - r)
                    
                    # Move toward it
                    if goal_y < y:
                        return Action.MOVE_NORTH
                    elif goal_y > y:
                        return Action.MOVE_SOUTH
                    elif goal_x < x:
                        return Action.MOVE_WEST
                    elif goal_x > x:
                        return Action.MOVE_EAST
                        
        # If resource nearby, collect it
        for dy, row in enumerate(obs.grid_view):
            for dx, cell in enumerate(row):
                if cell == CellType.RESOURCE.value:
                    # Resource visible
                    res_y = y + (dy - r)
                    res_x = x + (dx - r)
                    
                    if abs(res_y - y) + abs(res_x - x) <= 1:
                        # Adjacent - move to collect
                        if res_y < y:
                            return Action.MOVE_NORTH
                        elif res_y > y:
                            return Action.MOVE_SOUTH
                        elif res_x < x:
                            return Action.MOVE_WEST
                        elif res_x > x:
                            return Action.MOVE_EAST
                            
        # Avoid hazards
        for dy, row in enumerate(obs.grid_view):
            for dx, cell in enumerate(row):
                if cell == CellType.HAZARD.value:
                    haz_y = y + (dy - r)
                    haz_x = x + (dx - r)
                    
                    # If hazard is in direction we might move, avoid
                    if haz_y == y - 1 and haz_x == x:  # North is hazard
                        return Action.MOVE_EAST if random.random() < 0.5 else Action.MOVE_WEST
                    # Similar for other directions...
                    
        # Default: explore systematically
        # Find nearest unvisited cell
        unvisited = [(py, px) for (py, px) in self.known_map.keys() 
                    if (py, px) not in self.visited_positions 
                    and self.known_map[(py, px)] != CellType.OBSTACLE.value]
        
        if unvisited:
            target = min(unvisited, key=lambda p: abs(p[0]-y) + abs(p[1]-x))
            if target[0] < y:
                return Action.MOVE_NORTH
            elif target[0] > y:
                return Action.MOVE_SOUTH
            elif target[1] < x:
                return Action.MOVE_WEST
            elif target[1] > x:
                return Action.MOVE_EAST
                
        # Random movement as last resort
        return random.choice([Action.MOVE_NORTH, Action.MOVE_SOUTH, 
                             Action.MOVE_EAST, Action.MOVE_WEST])
    
    def _learn_from_result(self, action: Action, old_obs: Observation,
                          new_obs: Observation, reward: float,
                          info: Dict, session: ExplorationSession):
        """Update hypotheses based on action outcomes."""
        # Update confidence based on rewards
        for h in self.hypotheses:
            if "resources" in h.description and reward > 0:
                h.confidence = min(1.0, h.confidence + 0.1)
            if "hazard" in h.description and "hazard" in str(info):
                h.confidence = min(1.0, h.confidence + 0.15)
                
        self.exploration_history.append({
            "action": action.name,
            "reward": reward,
            "info": info,
            "inventory_delta": {
                k: new_obs.inventory.get(k, 0) - old_obs.inventory.get(k, 0)
                for k in set(old_obs.inventory.keys()) | set(new_obs.inventory.keys())
            }
        })
    
    def _calculate_score(self, env: AbstractGridEnvironment, 
                        session: ExplorationSession) -> float:
        """Calculate final exploration score."""
        base = 100 if session.success else 0
        
        # Efficiency bonus
        efficiency = max(0, 1 - (len(session.actions_taken) / env.max_steps))
        
        # Coverage bonus
        coverage = len(self.visited_positions) / (env.width * env.height)
        
        # Hypothesis quality
        hyp_bonus = sum(h.confidence for h in session.hypotheses_formed) * 5
        
        return base + efficiency * 50 + coverage * 30 + hyp_bonus


def run_exploration_benchmark(n_tasks: int = 5) -> Dict:
    """
    Run multiple ARC-AGI style exploration tasks and measure performance.
    """
    print("=" * 60)
    print("🧪 ARC-AGI-3 Style Exploration Benchmark")
    print("=" * 60)
    print("\nAbstract reasoning without explicit instructions.")
    print("Agents must infer goals from core priors alone.")
    print(f"Running {n_tasks} random tasks...\n")
    
    results = []
    
    task_types = ["collection", "navigation", "manipulation", "avoidance"]
    
    for i in range(n_tasks):
        task_type = random.choice(task_types)
        
        print(f"\n{'='*40}")
        print(f"Task {i+1}/{n_tasks}: {task_type.upper()}")
        print(f"{'='*40}")
        
        # Create environment (task type hidden from agent)
        env = AbstractGridEnvironment(
            width=15, 
            height=15,
            visibility_radius=3,
            max_steps=80
        )
        env.generate_task(task_type=task_type)
        
        # Create agent
        agent = ExplorationAgent(name=f"Explorer-{i+1}")
        
        # Run exploration
        session = agent.explore(env)
        
        results.append({
            "task_type": task_type,
            "success": session.success,
            "score": session.final_score,
            "steps": len(session.actions_taken),
            "hypotheses": len(session.hypotheses_formed),
            "coverage": len(agent.visited_positions) / (env.width * env.height)
        })
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 BENCHMARK RESULTS")
    print("=" * 60)
    
    successes = sum(1 for r in results if r["success"])
    avg_score = sum(r["score"] for r in results) / len(results)
    avg_steps = sum(r["steps"] for r in results) / len(results)
    avg_coverage = sum(r["coverage"] for r in results) / len(results)
    
    print(f"\nSuccess Rate: {successes}/{n_tasks} ({100*successes/n_tasks:.1f}%)")
    print(f"Average Score: {avg_score:.1f}")
    print(f"Average Steps: {avg_steps:.1f}")
    print(f"Average Coverage: {avg_coverage:.1%}")
    
    # By task type
    print("\nBy Task Type:")
    for tt in task_types:
        tt_results = [r for r in results if r["task_type"] == tt]
        if tt_results:
            tt_success = sum(1 for r in tt_results if r["success"])
            tt_score = sum(r["score"] for r in tt_results) / len(tt_results)
            print(f"  {tt:12s}: {tt_success}/{len(tt_results)} success, "
                  f"avg score {tt_score:.1f}")
    
    print("\n📝 Interpretation:")
    print("   >100: Excellent - strong hypothesis formation and goal achievement")
    print("   50-100: Good - partial success with some exploration")
    print("   <50: Needs improvement - failed to infer task structure")
    print("\n🎯 ARC-AGI-3 Reference:")
    print("   Human baseline: ~100% success, adaptive from core priors")
    print("   Frontier AI (2026): <1% on novel abstract tasks")
    
    return {
        "n_tasks": n_tasks,
        "success_rate": successes / n_tasks,
        "avg_score": avg_score,
        "avg_steps": avg_steps,
        "avg_coverage": avg_coverage,
        "results": results
    }


if __name__ == "__main__":
    # Run benchmark
    benchmark_results = run_exploration_benchmark(n_tasks=5)
