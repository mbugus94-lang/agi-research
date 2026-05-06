"""
ARC-AGI-3 Solver: Abstract Reasoning and Pattern Transformation
Based on arXiv:2603.24621v1 - ARC-AGI-3: A New Challenge for Frontier Agentic Intelligence

Key insights from research:
- Humans solve 100%; frontier AI <1% (March 2026)
- Tests fluid adaptive efficiency using only Core Knowledge priors
- Requires goal inference, environment exploration, and abstract pattern reasoning
- Symmetry-aware encoding and test-time adaptation are critical
"""

from typing import List, Dict, Tuple, Optional, Set, Callable, Any
from dataclasses import dataclass, field
from enum import Enum, auto
import numpy as np
from collections import defaultdict
import copy


class ARCColor(Enum):
    """ARC-AGI color palette (0-9)"""
    BLACK = 0
    BLUE = 1
    RED = 2
    GREEN = 3
    YELLOW = 4
    GREY = 5
    PINK = 6
    ORANGE = 7
    CYAN = 8
    MAROON = 9


class PatternType(Enum):
    """Types of patterns found in ARC tasks"""
    SYMMETRY = auto()
    REPETITION = auto()
    PROGRESSION = auto()
    XOR = auto()
    OR = auto()
    AND = auto()
    TRANSFORMATION = auto()
    OBJECT_MANIPULATION = auto()
    COUNTING = auto()
    SORTING = auto()


@dataclass
class Grid:
    """Represents an ARC grid with operations"""
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
    
    def get_objects(self, connectivity: str = "4") -> List[Dict]:
        """Extract connected components as objects"""
        from scipy import ndimage
        
        objects = []
        visited = np.zeros_like(self.data, dtype=bool)
        
        for color in range(10):
            mask = (self.data == color) & ~visited
            if not mask.any():
                continue
                
            if connectivity == "4":
                structure = np.array([[0,1,0],[1,1,1],[0,1,0]])
            else:
                structure = np.ones((3,3))
            
            labeled, num_features = ndimage.label(mask, structure=structure)
            
            for i in range(1, num_features + 1):
                obj_mask = labeled == i
                visited[obj_mask] = True
                
                coords = np.argwhere(obj_mask)
                min_row, min_col = coords.min(axis=0)
                max_row, max_col = coords.max(axis=0)
                
                objects.append({
                    'color': color,
                    'mask': obj_mask,
                    'bbox': (min_row, min_col, max_row, max_col),
                    'pixels': coords.tolist(),
                    'size': len(coords),
                    'centroid': coords.mean(axis=0).tolist()
                })
        
        return objects
    
    def rotate(self, k: int = 1) -> 'Grid':
        """Rotate grid 90*k degrees"""
        return Grid(np.rot90(self.data, k))
    
    def flip(self, axis: int = 0) -> 'Grid':
        """Flip grid along axis (0=vertical, 1=horizontal)"""
        return Grid(np.flip(self.data, axis))
    
    def transpose(self) -> 'Grid':
        """Transpose grid"""
        return Grid(self.data.T)
    
    def crop(self, top: int, left: int, bottom: int, right: int) -> 'Grid':
        """Crop grid to bounding box"""
        return Grid(self.data[top:bottom, left:right])
    
    def replace_color(self, old: int, new: int) -> 'Grid':
        """Replace one color with another"""
        result = self.data.copy()
        result[result == old] = new
        return Grid(result)
    
    def fill(self, color: int) -> 'Grid':
        """Fill entire grid with color"""
        return Grid(np.full_like(self.data, color))
    
    def overlay(self, other: 'Grid', x: int = 0, y: int = 0) -> 'Grid':
        """Overlay another grid at position"""
        result = self.data.copy()
        h, w = other.shape
        result[y:y+h, x:x+w] = other.data
        return Grid(result)
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, Grid):
            return False
        return np.array_equal(self.data, other.data)
    
    def __hash__(self) -> int:
        return hash(self.data.tobytes())


@dataclass
class ARCTask:
    """Represents an ARC-AGI task with train and test examples"""
    id: str
    train_examples: List[Tuple[Grid, Grid]]  # (input, output) pairs
    test_input: Grid
    test_output: Optional[Grid] = None
    
    def __repr__(self) -> str:
        return f"ARCTask({self.id}, {len(self.train_examples)} train examples)"


@dataclass
class PatternHypothesis:
    """A hypothesis about the transformation pattern"""
    pattern_type: PatternType
    description: str
    confidence: float
    transform_fn: Callable[[Grid], Grid]
    evidence: List[Dict] = field(default_factory=list)
    
    def apply(self, grid: Grid) -> Grid:
        """Apply the transformation"""
        return self.transform_fn(grid)


class SymmetryAnalyzer:
    """Analyze symmetry properties of grids"""
    
    @staticmethod
    def has_vertical_symmetry(grid: Grid) -> bool:
        """Check if grid is symmetric around vertical axis"""
        return np.array_equal(grid.data, np.fliplr(grid.data))
    
    @staticmethod
    def has_horizontal_symmetry(grid: Grid) -> bool:
        """Check if grid is symmetric around horizontal axis"""
        return np.array_equal(grid.data, np.flipud(grid.data))
    
    @staticmethod
    def has_rotational_symmetry(grid: Grid) -> bool:
        """Check if grid has 180-degree rotational symmetry"""
        return np.array_equal(grid.data, np.rot90(grid.data, 2))
    
    @staticmethod
    def has_diagonal_symmetry(grid: Grid) -> bool:
        """Check if grid is symmetric around diagonal"""
        if grid.height != grid.width:
            return False
        return np.array_equal(grid.data, grid.data.T)
    
    @staticmethod
    def get_symmetry_score(grid: Grid) -> Dict[str, float]:
        """Get symmetry scores for all types"""
        return {
            'vertical': float(SymmetryAnalyzer.has_vertical_symmetry(grid)),
            'horizontal': float(SymmetryAnalyzer.has_horizontal_symmetry(grid)),
            'rotational': float(SymmetryAnalyzer.has_rotational_symmetry(grid)),
            'diagonal': float(SymmetryAnalyzer.has_diagonal_symmetry(grid))
        }


class PatternLibrary:
    """Library of common ARC patterns and their detectors"""
    
    def __init__(self):
        self.patterns: Dict[PatternType, List[Callable]] = {
            PatternType.SYMMETRY: [self._detect_symmetry],
            PatternType.REPETITION: [self._detect_repetition],
            PatternType.PROGRESSION: [self._detect_progression],
            PatternType.OBJECT_MANIPULATION: [self._detect_object_changes],
            PatternType.COUNTING: [self._detect_counting],
        }
    
    def _detect_symmetry(self, input_grid: Grid, output_grid: Grid) -> Optional[PatternHypothesis]:
        """Detect if transformation involves symmetry operations"""
        analyzer = SymmetryAnalyzer()
        
        # Check if output is a symmetry transformation of input
        transforms = [
            ("vertical_flip", lambda g: g.flip(1)),
            ("horizontal_flip", lambda g: g.flip(0)),
            ("rotate_90", lambda g: g.rotate(1)),
            ("rotate_180", lambda g: g.rotate(2)),
            ("rotate_270", lambda g: g.rotate(3)),
            ("transpose", lambda g: g.transpose()),
        ]
        
        for name, transform in transforms:
            if transform(input_grid) == output_grid:
                return PatternHypothesis(
                    pattern_type=PatternType.SYMMETRY,
                    description=f"Symmetry: {name}",
                    confidence=1.0,
                    transform_fn=transform,
                    evidence=[{'transform': name}]
                )
        
        return None
    
    def _detect_repetition(self, input_grid: Grid, output_grid: Grid) -> Optional[PatternHypothesis]:
        """Detect tiling/repetition patterns"""
        ih, iw = input_grid.shape
        oh, ow = output_grid.shape
        
        # Check if output is a tiled version of input
        if oh % ih == 0 and ow % iw == 0:
            tile_h = oh // ih
            tile_w = ow // iw
            
            expected = np.tile(input_grid.data, (tile_h, tile_w))
            if np.array_equal(expected, output_grid.data):
                return PatternHypothesis(
                    pattern_type=PatternType.REPETITION,
                    description=f"Tiling: {tile_h}x{tile_w}",
                    confidence=1.0,
                    transform_fn=lambda g: Grid(np.tile(g.data, (tile_h, tile_w))),
                    evidence=[{'tile_h': tile_h, 'tile_w': tile_w}]
                )
        
        return None
    
    def _detect_progression(self, input_grid: Grid, output_grid: Grid) -> Optional[PatternHypothesis]:
        """Detect color progression patterns"""
        # Only check if shapes match
        if input_grid.shape != output_grid.shape:
            return None
            
        input_colors = set(input_grid.data.flatten())
        output_colors = set(output_grid.data.flatten())
        
        # Check for color shifts
        if len(input_colors) == len(output_colors):
            shifts = {}
            for ic in input_colors:
                mask = input_grid.data == ic
                output_val = output_grid.data[mask]
                if len(set(output_val)) == 1:
                    shifts[ic] = output_val[0]
            
            if len(shifts) == len(input_colors):
                def color_shift(grid):
                    result = grid.data.copy()
                    for old, new in shifts.items():
                        result[result == old] = new
                    return Grid(result)
                
                return PatternHypothesis(
                    pattern_type=PatternType.PROGRESSION,
                    description=f"Color shift: {shifts}",
                    confidence=0.9,
                    transform_fn=color_shift,
                    evidence=[{'shifts': shifts}]
                )
        
        return None
    
    def _detect_object_changes(self, input_grid: Grid, output_grid: Grid) -> Optional[PatternHypothesis]:
        """Detect object manipulation patterns"""
        try:
            input_objs = input_grid.get_objects()
            output_objs = output_grid.get_objects()
            
            if len(input_objs) != len(output_objs):
                # Object count changed - might be filtering or duplication
                return PatternHypothesis(
                    pattern_type=PatternType.OBJECT_MANIPULATION,
                    description=f"Object count: {len(input_objs)} -> {len(output_objs)}",
                    confidence=0.7,
                    transform_fn=lambda g: g,  # Placeholder
                    evidence=[{'input_count': len(input_objs), 'output_count': len(output_objs)}]
                )
        except:
            pass
        
        return None
    
    def _detect_counting(self, input_grid: Grid, output_grid: Grid) -> Optional[PatternHypothesis]:
        """Detect counting patterns (output is count of something in input)"""
        # If output is a small grid (1x1 or similar), might be counting
        oh, ow = output_grid.shape
        if oh <= 2 and ow <= 2:
            # Count unique colors, objects, etc.
            input_colors = len(set(input_grid.data.flatten()))
            if output_grid.data.flatten()[0] == input_colors:
                return PatternHypothesis(
                    pattern_type=PatternType.COUNTING,
                    description="Count unique colors",
                    confidence=0.8,
                    transform_fn=lambda g: Grid(np.array([[len(set(g.data.flatten()))]])),
                    evidence=[{'count': input_colors}]
                )
        
        return None
    
    def analyze_pair(self, input_grid: Grid, output_grid: Grid) -> List[PatternHypothesis]:
        """Analyze an input-output pair and return matching patterns"""
        hypotheses = []
        
        for pattern_type, detectors in self.patterns.items():
            for detector in detectors:
                hypothesis = detector(input_grid, output_grid)
                if hypothesis:
                    hypotheses.append(hypothesis)
        
        return hypotheses


class ARCTimeAdapter:
    """Test-time adaptation for ARC tasks using lightweight updates"""
    
    def __init__(self, base_solver: 'ARCSolver'):
        self.base_solver = base_solver
        self.adaptation_history: List[Dict] = []
    
    def adapt(self, task: ARCTask, num_iterations: int = 5) -> List[PatternHypothesis]:
        """Adapt solver to task using training examples"""
        # Collect all pattern hypotheses from training
        all_hypotheses = defaultdict(list)
        
        for input_grid, output_grid in task.train_examples:
            hypotheses = self.base_solver.pattern_library.analyze_pair(input_grid, output_grid)
            for h in hypotheses:
                all_hypotheses[h.pattern_type].append(h)
        
        # Score hypotheses by consistency across examples
        scored_hypotheses = []
        for pattern_type, hypotheses in all_hypotheses.items():
            if len(hypotheses) == len(task.train_examples):
                # Pattern appears in all examples
                avg_confidence = sum(h.confidence for h in hypotheses) / len(hypotheses)
                
                # For progression patterns, analyze if it's an arithmetic pattern
                if pattern_type == PatternType.PROGRESSION:
                    all_shifts = []
                    for h in hypotheses:
                        if 'shifts' in h.evidence[0]:
                            all_shifts.extend(h.evidence[0]['shifts'].items())
                    
                    # Check if all shifts are by the same amount (arithmetic progression)
                    increments = [new - old for old, new in all_shifts]
                    if increments and len(set(increments)) == 1:
                        # Arithmetic pattern: all colors shift by same amount
                        increment = increments[0]
                        
                        def make_increment_shift(inc):
                            def color_shift(grid):
                                # Use vectorized addition with clipping to valid color range
                                result = np.clip(grid.data + inc, 0, 9).astype(np.int8)
                                return Grid(result)
                            return color_shift
                        
                        representative = PatternHypothesis(
                            pattern_type=PatternType.PROGRESSION,
                            description=f"Color progression: +{increment}",
                            confidence=min(avg_confidence * 1.2, 1.0),
                            transform_fn=make_increment_shift(increment),
                            evidence=[{'increment': increment, 'type': 'arithmetic'}]
                        )
                    else:
                        # Merge specific mappings
                        merged_shifts = dict(all_shifts)
                        
                        def make_merged_shift(shifts):
                            def color_shift(grid):
                                result = grid.data.copy()
                                for old, new in shifts.items():
                                    result[result == old] = new
                                return Grid(result)
                            return color_shift
                        
                        representative = PatternHypothesis(
                            pattern_type=PatternType.PROGRESSION,
                            description=f"Color shift (merged): {merged_shifts}",
                            confidence=min(avg_confidence * 1.2, 1.0),
                            transform_fn=make_merged_shift(merged_shifts),
                            evidence=[{'shifts': merged_shifts}]
                        )
                else:
                    # Use the first hypothesis as representative for other patterns
                    representative = hypotheses[0]
                    representative.confidence = min(avg_confidence * 1.2, 1.0)  # Boost for consistency
                
                scored_hypotheses.append(representative)
        
        # Sort by confidence
        scored_hypotheses.sort(key=lambda h: h.confidence, reverse=True)
        
        self.adaptation_history.append({
            'task_id': task.id,
            'hypotheses_found': len(scored_hypotheses),
            'top_confidence': scored_hypotheses[0].confidence if scored_hypotheses else 0
        })
        
        return scored_hypotheses


class ARCSolver:
    """Main ARC-AGI-3 solver with pattern recognition and test-time adaptation"""
    
    def __init__(self):
        self.pattern_library = PatternLibrary()
        self.symmetry_analyzer = SymmetryAnalyzer()
        self.adapter = ARCTimeAdapter(self)
        self.solution_history: List[Dict] = []
    
    def solve(self, task: ARCTask, use_adaptation: bool = True) -> Grid:
        """Solve an ARC task"""
        if use_adaptation:
            # Test-time adaptation
            hypotheses = self.adapter.adapt(task)
        else:
            # Single-shot solving
            hypotheses = []
            for input_grid, output_grid in task.train_examples:
                h = self.pattern_library.analyze_pair(input_grid, output_grid)
                hypotheses.extend(h)
        
        # Try hypotheses in order of confidence
        for hypothesis in hypotheses:
            try:
                result = hypothesis.apply(task.test_input)
                
                self.solution_history.append({
                    'task_id': task.id,
                    'pattern_type': hypothesis.pattern_type.name,
                    'confidence': hypothesis.confidence,
                    'description': hypothesis.description
                })
                
                return result
            except Exception as e:
                continue
        
        # Fallback: return input unchanged
        self.solution_history.append({
            'task_id': task.id,
            'pattern_type': 'FALLBACK',
            'confidence': 0.0,
            'description': 'No pattern matched'
        })
        
        return task.test_input
    
    def evaluate(self, task: ARCTask, prediction: Grid) -> Dict:
        """Evaluate prediction against ground truth (if available)"""
        if task.test_output is None:
            return {'status': 'no_ground_truth'}
        
        correct = (prediction == task.test_output)
        
        # Calculate additional metrics
        if correct:
            pixel_accuracy = 1.0
        else:
            pred_flat = prediction.data.flatten()
            truth_flat = task.test_output.data.flatten()
            matches = np.sum(pred_flat == truth_flat)
            pixel_accuracy = matches / len(pred_flat)
        
        return {
            'correct': correct,
            'pixel_accuracy': pixel_accuracy,
            'prediction_shape': prediction.shape,
            'expected_shape': task.test_output.shape
        }
    
    def get_stats(self) -> Dict:
        """Get solver statistics"""
        if not self.solution_history:
            return {'total_attempts': 0}
        
        pattern_counts = defaultdict(int)
        for entry in self.solution_history:
            pattern_counts[entry['pattern_type']] += 1
        
        return {
            'total_attempts': len(self.solution_history),
            'pattern_distribution': dict(pattern_counts),
            'avg_confidence': sum(e['confidence'] for e in self.solution_history) / len(self.solution_history)
        }


def create_sample_task(task_id: str = "sample_001") -> ARCTask:
    """Create a sample ARC task for testing"""
    # Example: Vertical flip pattern
    train_1_input = Grid([
        [1, 2, 3],
        [4, 5, 6],
        [7, 8, 9]
    ])
    train_1_output = Grid([
        [3, 2, 1],
        [6, 5, 4],
        [9, 8, 7]
    ])
    
    train_2_input = Grid([
        [0, 1],
        [2, 3]
    ])
    train_2_output = Grid([
        [1, 0],
        [3, 2]
    ])
    
    test_input = Grid([
        [5, 6, 7, 8],
        [1, 2, 3, 4]
    ])
    test_output = Grid([
        [8, 7, 6, 5],
        [4, 3, 2, 1]
    ])
    
    return ARCTask(
        id=task_id,
        train_examples=[(train_1_input, train_1_output), (train_2_input, train_2_output)],
        test_input=test_input,
        test_output=test_output
    )


def create_color_progression_task(task_id: str = "color_prog_001") -> ARCTask:
    """Create a color progression task with consistent color shifts"""
    # Use consistent color shift: each color n becomes n+1
    train_1_input = Grid([
        [0, 0],
        [1, 1]
    ])
    train_1_output = Grid([
        [1, 1],
        [2, 2]
    ])
    
    train_2_input = Grid([
        [2, 2, 2],
        [3, 3, 3]
    ])
    train_2_output = Grid([
        [3, 3, 3],
        [4, 4, 4]
    ])
    
    test_input = Grid([
        [4, 4],
        [5, 5]
    ])
    test_output = Grid([
        [5, 5],
        [6, 6]
    ])
    
    return ARCTask(
        id=task_id,
        train_examples=[(train_1_input, train_1_output), (train_2_input, train_2_output)],
        test_input=test_input,
        test_output=test_output
    )


if __name__ == "__main__":
    # Test the solver
    print("=" * 50)
    print("ARC-AGI-3 Solver Test")
    print("=" * 50)
    
    solver = ARCSolver()
    
    # Test symmetry task
    print("\n1. Testing Symmetry (Vertical Flip) Task:")
    task1 = create_sample_task()
    result1 = solver.solve(task1)
    eval1 = solver.evaluate(task1, result1)
    print(f"   Prediction correct: {eval1['correct']}")
    print(f"   Pixel accuracy: {eval1['pixel_accuracy']:.2%}")
    
    # Test color progression task
    print("\n2. Testing Color Progression Task:")
    task2 = create_color_progression_task()
    result2 = solver.solve(task2)
    eval2 = solver.evaluate(task2, result2)
    print(f"   Prediction correct: {eval2['correct']}")
    print(f"   Pixel accuracy: {eval2['pixel_accuracy']:.2%}")
    
    # Print stats
    print("\n3. Solver Statistics:")
    stats = solver.get_stats()
    print(f"   Total attempts: {stats['total_attempts']}")
    print(f"   Pattern distribution: {stats['pattern_distribution']}")
    print(f"   Average confidence: {stats['avg_confidence']:.2%}")
    
    print("\n" + "=" * 50)
    print("Test Complete")
    print("=" * 50)
