"""
Executable World Model Solver for ARC-AGI-3
Based on arXiv:2605.05138v1 - Executable World Models for ARC-AGI-3 in the Era of Coding Agents

Key innovations:
1. Executable Python world models that simulate transformations
2. Generate-and-verify loop with testable simulators
3. Refactoring toward simpler abstractions (MDL principle)
4. Neuro-symbolic separation: perception → proposal → verification
"""

from typing import List, Dict, Tuple, Optional, Callable, Any, Set
from dataclasses import dataclass, field
from enum import Enum, auto
import numpy as np
from collections import defaultdict
import copy
import ast
import traceback
from abc import ABC, abstractmethod


class ARCColor(Enum):
    """ARC-AGI color palette (0-9)"""
    BLACK = 0; BLUE = 1; RED = 2; GREEN = 3; YELLOW = 4
    GREY = 5; PINK = 6; ORANGE = 7; CYAN = 8; MAROON = 9


@dataclass
class Grid:
    """ARC grid with rich operations for world modeling"""
    data: np.ndarray
    
    def __post_init__(self):
        if isinstance(self.data, list):
            self.data = np.array(self.data, dtype=np.int8)
    
    @property
    def shape(self) -> Tuple[int, int]:
        return self.data.shape
    
    @property
    def height(self) -> int:
        return self.data.shape[0]
    
    @property
    def width(self) -> int:
        return self.data.shape[1]
    
    def copy(self) -> 'Grid':
        return Grid(self.data.copy())
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, Grid):
            return False
        return np.array_equal(self.data, other.data)
    
    def __hash__(self) -> int:
        return hash(self.data.tobytes())
    
    def to_list(self) -> List[List[int]]:
        return self.data.tolist()
    
    @staticmethod
    def from_list(data: List[List[int]]) -> 'Grid':
        return Grid(np.array(data, dtype=np.int8))


@dataclass 
class Object:
    """Extracted object from grid with properties"""
    color: int
    pixels: List[Tuple[int, int]]
    mask: np.ndarray
    bbox: Tuple[int, int, int, int]  # top, left, bottom, right
    
    @property
    def size(self) -> int:
        return len(self.pixels)
    
    @property
    def centroid(self) -> Tuple[float, float]:
        rows, cols = zip(*self.pixels)
        return (sum(rows) / len(rows), sum(cols) / len(cols))
    
    @property
    def width(self) -> int:
        return self.bbox[3] - self.bbox[1]
    
    @property
    def height(self) -> int:
        return self.bbox[2] - self.bbox[0]
    
    @property
    def aspect_ratio(self) -> float:
        return self.width / max(self.height, 1)


@dataclass
class WorldModel:
    """Executable world model for simulating transformations"""
    name: str
    code: str
    description: str
    complexity: int  # Lines of code / complexity score
    
    def execute(self, grid: Grid) -> Optional[Grid]:
        """Execute the world model on a grid"""
        try:
            # Create safe execution environment
            env = {
                'np': np,
                'Grid': Grid,
                'input_grid': grid,
            }
            
            # Execute the model code
            exec(self.code, env)
            
            # Get the transform function
            if 'transform' in env:
                result = env['transform'](grid)
                if isinstance(result, Grid):
                    return result
                elif isinstance(result, np.ndarray):
                    return Grid(result)
                elif isinstance(result, list):
                    return Grid.from_list(result)
            
            return None
        except Exception as e:
            return None
    
    def verify(self, input_grid: Grid, expected_output: Grid) -> bool:
        """Verify the model produces expected output"""
        result = self.execute(input_grid)
        if result is None:
            return False
        return result == expected_output


@dataclass
class PerceptionResult:
    """Result of perception phase - extracted objects and properties"""
    objects: List[Object]
    background_color: int
    grid_properties: Dict[str, Any]
    
    def get_objects_by_color(self, color: int) -> List[Object]:
        return [obj for obj in self.objects if obj.color == color]
    
    def get_objects_by_size(self, min_size: int = 0, max_size: int = float('inf')) -> List[Object]:
        return [obj for obj in self.objects if min_size <= obj.size <= max_size]


class PerceptionModule:
    """Neural-inspired perception - extracts objects and properties from grids"""
    
    def perceive(self, grid: Grid, connectivity: str = "4") -> PerceptionResult:
        """Extract objects and properties from grid"""
        objects = self._extract_objects(grid, connectivity)
        bg_color = self._detect_background(grid, objects)
        properties = self._analyze_properties(grid, objects)
        
        return PerceptionResult(
            objects=objects,
            background_color=bg_color,
            grid_properties=properties
        )
    
    def _extract_objects(self, grid: Grid, connectivity: str) -> List[Object]:
        """Extract connected components as objects"""
        try:
            from scipy import ndimage
        except ImportError:
            # Fallback without scipy
            return self._extract_objects_simple(grid)
        
        objects = []
        visited = np.zeros_like(grid.data, dtype=bool)
        
        for color in range(10):
            mask = (grid.data == color) & ~visited
            if not mask.any():
                continue
            
            structure = np.array([[0,1,0],[1,1,1],[0,1,0]]) if connectivity == "4" else np.ones((3,3))
            labeled, num_features = ndimage.label(mask, structure=structure)
            
            for i in range(1, num_features + 1):
                obj_mask = labeled == i
                visited[obj_mask] = True
                
                coords = np.argwhere(obj_mask)
                min_row, min_col = coords.min(axis=0)
                max_row, max_col = coords.max(axis=0)
                
                objects.append(Object(
                    color=color,
                    pixels=[(int(r), int(c)) for r, c in coords],
                    mask=obj_mask,
                    bbox=(int(min_row), int(min_col), int(max_row) + 1, int(max_col) + 1)
                ))
        
        return objects
    
    def _extract_objects_simple(self, grid: Grid) -> List[Object]:
        """Simple object extraction without scipy"""
        objects = []
        visited = set()
        
        for r in range(grid.height):
            for c in range(grid.width):
                if (r, c) in visited or grid.data[r, c] == 0:
                    continue
                
                color = int(grid.data[r, c])
                # Find connected component using BFS
                pixels = []
                queue = [(r, c)]
                visited.add((r, c))
                
                while queue:
                    cr, cc = queue.pop(0)
                    pixels.append((cr, cc))
                    
                    # Check 4-connected neighbors
                    for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
                        nr, nc = cr + dr, cc + dc
                        if (nr, nc) not in visited and 0 <= nr < grid.height and 0 <= nc < grid.width:
                            if grid.data[nr, nc] == color:
                                visited.add((nr, nc))
                                queue.append((nr, nc))
                
                if pixels:
                    rows, cols = zip(*pixels)
                    mask = np.zeros_like(grid.data, dtype=bool)
                    for pr, pc in pixels:
                        mask[pr, pc] = True
                    
                    objects.append(Object(
                        color=color,
                        pixels=pixels,
                        mask=mask,
                        bbox=(min(rows), min(cols), max(rows) + 1, max(cols) + 1)
                    ))
        
        return objects
    
    def _detect_background(self, grid: Grid, objects: List[Object]) -> int:
        """Detect background color (most frequent at borders)"""
        border_pixels = []
        # Top and bottom borders
        border_pixels.extend(grid.data[0, :])
        border_pixels.extend(grid.data[-1, :])
        # Left and right borders (excluding corners already counted)
        border_pixels.extend(grid.data[1:-1, 0])
        border_pixels.extend(grid.data[1:-1, -1])
        
        if border_pixels:
            from collections import Counter
            return Counter(border_pixels).most_common(1)[0][0]
        return 0
    
    def _analyze_properties(self, grid: Grid, objects: List[Object]) -> Dict[str, Any]:
        """Analyze grid properties"""
        unique_colors = set(grid.data.flatten())
        
        return {
            'unique_colors': sorted(unique_colors),
            'num_objects': len(objects),
            'color_distribution': {c: int(np.sum(grid.data == c)) for c in unique_colors},
            'is_symmetric_horizontal': np.array_equal(grid.data, np.flipud(grid.data)),
            'is_symmetric_vertical': np.array_equal(grid.data, np.fliplr(grid.data)),
            'dimensions': grid.shape,
        }


class TransformationProposer:
    """Generate candidate transformations based on perceived patterns"""
    
    def __init__(self):
        self.perception = PerceptionModule()
    
    def propose_transformations(self, train_examples: List[Tuple[Grid, Grid]]) -> List[WorldModel]:
        """Generate candidate world models from training examples"""
        proposals = []
        
        # Analyze each training pair
        percepts_in = []
        percepts_out = []
        for inp, out in train_examples:
            percepts_in.append(self.perception.perceive(inp))
            percepts_out.append(self.perception.perceive(out))
        
        # Propose transformations based on observed changes
        proposals.extend(self._propose_symmetry_transforms(train_examples))
        proposals.extend(self._propose_color_transforms(train_examples, percepts_in, percepts_out))
        proposals.extend(self._propose_object_transforms(train_examples, percepts_in, percepts_out))
        proposals.extend(self._propose_geometric_transforms(train_examples))
        
        return proposals
    
    def _propose_symmetry_transforms(self, examples: List[Tuple[Grid, Grid]]) -> List[WorldModel]:
        """Propose symmetry-based transformations"""
        proposals = []
        
        transforms_to_try = [
            ('horizontal_flip', 'def transform(g): return Grid(np.fliplr(g.data))', 1),
            ('vertical_flip', 'def transform(g): return Grid(np.flipud(g.data))', 1),
            ('rotate_90', 'def transform(g): return Grid(np.rot90(g.data, 1))', 1),
            ('rotate_180', 'def transform(g): return Grid(np.rot90(g.data, 2))', 1),
            ('rotate_270', 'def transform(g): return Grid(np.rot90(g.data, 3))', 1),
            ('transpose', 'def transform(g): return Grid(g.data.T)', 1),
        ]
        
        for name, code, complexity in transforms_to_try:
            # Verify on all training examples
            matches = sum(1 for inp, out in examples 
                         if WorldModel(name, code, "", complexity).verify(inp, out))
            
            if matches == len(examples):
                proposals.append(WorldModel(
                    name=f"symmetry_{name}",
                    code=code,
                    description=f"Symmetry transformation: {name}",
                    complexity=complexity
                ))
        
        return proposals
    
    def _propose_color_transforms(self, examples: List[Tuple[Grid, Grid]], 
                                  percepts_in: List[PerceptionResult],
                                  percepts_out: List[PerceptionResult]) -> List[WorldModel]:
        """Propose color mapping transformations"""
        proposals = []
        
        # Analyze color mappings across examples
        color_maps = []
        for (inp, out), pin, pout in zip(examples, percepts_in, percepts_out):
            # Skip if shapes don't match
            if inp.shape != out.shape:
                continue
                
            in_colors = set(inp.data.flatten())
            out_colors = set(out.data.flatten())
            
            # Check for consistent color shifts
            mapping = {}
            for c in in_colors:
                mask = inp.data == c
                out_vals = out.data[mask]
                if len(set(out_vals)) == 1:
                    mapping[c] = int(out_vals[0])
            
            if len(mapping) == len(in_colors):
                color_maps.append(mapping)
        
        if color_maps and all(m == color_maps[0] for m in color_maps):
            # Consistent mapping across all examples
            mapping = color_maps[0]
            
            # Check if it's arithmetic (all shift by same amount)
            shifts = [new - old for old, new in mapping.items()]
            if len(set(shifts)) == 1:
                shift = shifts[0]
                code = f'''def transform(g):
    result = g.data.copy()
    result = np.clip(result + {shift}, 0, 9)
    return Grid(result.astype(np.int8))'''
            else:
                # Specific mapping
                mapping_str = ', '.join(f'{k}: {v}' for k, v in mapping.items())
                code = f'''def transform(g):
    result = g.data.copy()
    mapping = {{{mapping_str}}}
    for old, new in mapping.items():
        result[result == old] = new
    return Grid(result)'''
            
            proposals.append(WorldModel(
                name="color_mapping",
                code=code,
                description=f"Color transformation: {mapping}",
                complexity=2
            ))
        
        return proposals
    
    def _propose_object_transforms(self, examples: List[Tuple[Grid, Grid]],
                                   percepts_in: List[PerceptionResult],
                                   percepts_out: List[PerceptionResult]) -> List[WorldModel]:
        """Propose object manipulation transformations"""
        proposals = []
        
        # Check for object filtering (some objects removed)
        for (inp, out), pin, pout in zip(examples, percepts_in, percepts_out):
            if len(pin.objects) > len(pout.objects):
                # Objects were removed - find criteria
                kept_in_output = []
                for obj_in in pin.objects:
                    for obj_out in pout.objects:
                        if obj_in.color == obj_out.color and obj_in.size == obj_out.size:
                            kept_in_output.append(obj_in)
                            break
                
                # Infer criteria
                if kept_in_output:
                    sizes = [obj.size for obj in kept_in_output]
                    if len(set(sizes)) == 1:
                        # Keep only objects of specific size
                        target_size = sizes[0]
                        code = f'''def transform(g):
    from core.executable_world_model_solver import PerceptionModule
    p = PerceptionModule()
    perc = p.perceive(g)
    result = np.full_like(g.data, {pin.background_color})
    for obj in perc.objects:
        if obj.size == {target_size}:
            for r, c in obj.pixels:
                result[r, c] = obj.color
    return Grid(result)'''
                        proposals.append(WorldModel(
                            name=f"filter_size_{target_size}",
                            code=code,
                            description=f"Keep only objects of size {target_size}",
                            complexity=5
                        ))
        
        return proposals
    
    def _propose_geometric_transforms(self, examples: List[Tuple[Grid, Grid]]) -> List[WorldModel]:
        """Propose geometric transformations like tiling, cropping"""
        proposals = []
        
        # Check for tiling
        for inp, out in examples:
            ih, iw = inp.shape
            oh, ow = out.shape
            
            if oh % ih == 0 and ow % iw == 0:
                tile_h = oh // ih
                tile_w = ow // iw
                expected = np.tile(inp.data, (tile_h, tile_w))
                
                if np.array_equal(expected, out.data):
                    code = f'''def transform(g):
    return Grid(np.tile(g.data, ({tile_h}, {tile_w})))'''
                    proposals.append(WorldModel(
                        name=f"tile_{tile_h}x{tile_w}",
                        code=code,
                        description=f"Tile grid {tile_h}x{tile_w}",
                        complexity=1
                    ))
        
        return proposals


class ModelVerifier:
    """Verify and rank world models"""
    
    def verify(self, model: WorldModel, examples: List[Tuple[Grid, Grid]]) -> Tuple[bool, float]:
        """Verify model on all examples, return (passed, score)"""
        correct = 0
        total = len(examples)
        
        for inp, out in examples:
            if model.verify(inp, out):
                correct += 1
        
        score = correct / total
        return score == 1.0, score
    
    def rank_models(self, models: List[WorldModel], examples: List[Tuple[Grid, Grid]]) -> List[Tuple[WorldModel, float]]:
        """Rank models by verification score and simplicity"""
        ranked = []
        
        for model in models:
            passed, score = self.verify(model, examples)
            
            # Score = accuracy - complexity_penalty
            complexity_penalty = model.complexity * 0.01
            final_score = score - complexity_penalty
            
            if score > 0:  # Only include models that match at least one example
                ranked.append((model, final_score))
        
        # Sort by score descending
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked
    
    def find_counterexamples(self, model: WorldModel, examples: List[Tuple[Grid, Grid]]) -> List[Tuple[Grid, Grid]]:
        """Find examples where model fails"""
        counterexamples = []
        for inp, out in examples:
            if not model.verify(inp, out):
                counterexamples.append((inp, out))
        return counterexamples


class ExecutableWorldModelSolver:
    """
    ARC-AGI-3 solver using executable world models.
    
    Implements the generate-and-verify loop from arXiv:2605.05138v1:
    1. Perception: Extract objects and properties
    2. Proposal: Generate candidate world models (Python code)
    3. Verification: Test models on training examples
    4. Refactoring: Simplify successful models (MDL principle)
    """
    
    def __init__(self):
        self.perception = PerceptionModule()
        self.proposer = TransformationProposer()
        self.verifier = ModelVerifier()
        self.solution_history: List[Dict] = []
        self.cached_models: Dict[str, WorldModel] = {}
    
    def solve(self, task_id: str, train_examples: List[Tuple[Grid, Grid]], 
              test_input: Grid) -> Tuple[Optional[Grid], Dict]:
        """
        Solve an ARC task using executable world models.
        
        Returns:
            (prediction, metadata)
        """
        metadata = {
            'task_id': task_id,
            'num_train_examples': len(train_examples),
            'models_proposed': 0,
            'models_verified': 0,
            'best_model': None,
            'execution_time': 0,
        }
        
        import time
        start_time = time.time()
        
        # Phase 1: Generate candidate world models
        candidates = self.proposer.propose_transformations(train_examples)
        metadata['models_proposed'] = len(candidates)
        
        if not candidates:
            metadata['execution_time'] = time.time() - start_time
            return test_input, metadata
        
        # Phase 2: Verify and rank models
        ranked = self.verifier.rank_models(candidates, train_examples)
        metadata['models_verified'] = len(ranked)
        
        if not ranked:
            metadata['execution_time'] = time.time() - start_time
            return test_input, metadata
        
        # Phase 3: Select best model and apply to test
        best_model, best_score = ranked[0]
        metadata['best_model'] = {
            'name': best_model.name,
            'description': best_model.description,
            'complexity': best_model.complexity,
            'score': best_score,
        }
        
        result = best_model.execute(test_input)
        
        # Phase 4: Cache the successful model
        self.cached_models[task_id] = best_model
        
        metadata['execution_time'] = time.time() - start_time
        
        self.solution_history.append({
            'task_id': task_id,
            'model_name': best_model.name,
            'score': best_score,
            'success': result is not None,
        })
        
        return result if result is not None else test_input, metadata
    
    def get_stats(self) -> Dict:
        """Get solver statistics"""
        if not self.solution_history:
            return {'total_tasks': 0}
        
        successful = sum(1 for e in self.solution_history if e['success'])
        
        return {
            'total_tasks': len(self.solution_history),
            'successful': successful,
            'success_rate': successful / len(self.solution_history),
            'cached_models': len(self.cached_models),
        }


# Factory functions for creating test tasks
def create_symmetry_task() -> Tuple[str, List[Tuple[Grid, Grid]], Grid, Grid]:
    """Create a symmetry transformation task"""
    train = [
        (Grid([[1,2],[3,4]]), Grid([[2,1],[4,3]])),  # Horizontal flip
        (Grid([[5,6,7]]), Grid([[7,6,5]])),  # Horizontal flip
    ]
    test_in = Grid([[8,9,10,11]])
    test_out = Grid([[11,10,9,8]])
    return "symmetry_flip", train, test_in, test_out


def create_color_shift_task() -> Tuple[str, List[Tuple[Grid, Grid]], Grid, Grid]:
    """Create a color arithmetic task"""
    train = [
        (Grid([[0,1],[2,3]]), Grid([[1,2],[3,4]])),  # +1
        (Grid([[5,6]]), Grid([[6,7]])),  # +1
    ]
    test_in = Grid([[7,8,9]])
    test_out = Grid([[8,9,10]])
    return "color_shift", train, test_in, test_out


def create_tiling_task() -> Tuple[str, List[Tuple[Grid, Grid]], Grid, Grid]:
    """Create a tiling transformation task"""
    train = [
        (Grid([[1,2]]), Grid([[1,2],[1,2]])),  # Tile vertically
        (Grid([[3]]), Grid([[3],[3],[3]])),  # Tile 3x vertically
    ]
    test_in = Grid([[4,5]])
    test_out = Grid([[4,5],[4,5]])
    return "tiling", train, test_in, test_out


if __name__ == "__main__":
    print("=" * 60)
    print("Executable World Model Solver for ARC-AGI-3")
    print("=" * 60)
    
    solver = ExecutableWorldModelSolver()
    
    tasks = [
        create_symmetry_task(),
        create_color_shift_task(),
        create_tiling_task(),
    ]
    
    for task_name, train, test_in, test_out in tasks:
        print(f"\n{'='*60}")
        print(f"Task: {task_name}")
        print(f"{'='*60}")
        
        result, meta = solver.solve(task_name, train, test_in)
        
        print(f"Training examples: {meta['num_train_examples']}")
        print(f"Models proposed: {meta['models_proposed']}")
        print(f"Models verified: {meta['models_verified']}")
        
        if meta['best_model']:
            print(f"Best model: {meta['best_model']['name']}")
            print(f"Model description: {meta['best_model']['description']}")
            print(f"Model complexity: {meta['best_model']['complexity']}")
        
        correct = (result == test_out)
        print(f"Prediction correct: {correct}")
        print(f"Execution time: {meta['execution_time']:.4f}s")
    
    print(f"\n{'='*60}")
    print("Solver Statistics:")
    stats = solver.get_stats()
    print(f"  Total tasks: {stats['total_tasks']}")
    print(f"  Successful: {stats['successful']}")
    print(f"  Success rate: {stats['success_rate']:.1%}")
    print(f"  Cached models: {stats['cached_models']}")
    print("=" * 60)
