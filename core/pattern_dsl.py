"""
Neuro-Symbolic Pattern DSL (Domain Specific Language)
Based on: ARC-AGI-3 research + Neuro-Symbolic hybrid approaches

Provides a composable, declarative language for grid transformations that:
1. Enables program synthesis from examples
2. Supports compositional pattern building
3. Integrates with executable world models
4. Offers higher-level abstractions beyond raw Python code

Key insight from research: Compositional reasoning requires structured
representations that bridge neural pattern recognition with symbolic
program construction.
"""

from typing import List, Dict, Tuple, Optional, Callable, Any, Union, Set
from dataclasses import dataclass, field
from enum import Enum, auto
from abc import ABC, abstractmethod
import numpy as np
import copy
from collections import defaultdict


class OpType(Enum):
    """Types of transformation operations."""
    GEOMETRIC = "geometric"       # Rotation, flip, transpose
    COLOR = "color"               # Color mapping, arithmetic
    OBJECT = "object"             # Object extraction, manipulation
    STRUCTURAL = "structural"     # Tiling, cropping, padding
    COMPOSITIONAL = "compositional"  # Composition of other ops


class GridType(Enum):
    """Type categories for grid typing system."""
    ANY = auto()
    SQUARE = auto()           # NxN grids
    RECTANGULAR = auto()      # MxN grids
    SINGLE_COLOR = auto()     # Only one non-zero color
    MULTI_COLOR = auto()      # Multiple colors
    SYMMETRIC = auto()        # Symmetric patterns


@dataclass(frozen=True)
class TypeConstraint:
    """Type constraint for operation composition."""
    input_shape: Optional[Tuple[int, ...]] = None
    input_colors: Optional[Set[int]] = None
    output_shape: Optional[Tuple[int, ...]] = None
    output_colors: Optional[Set[int]] = None
    preserves_dimensions: Optional[bool] = None
    
    def check(self, input_grid: 'GridDSL', output_grid: 'GridDSL') -> bool:
        """Check if constraint is satisfied."""
        if self.input_shape and input_grid.shape != self.input_shape:
            return False
        if self.output_shape and output_grid.shape != self.output_shape:
            return False
        if self.preserves_dimensions is not None:
            if self.preserves_dimensions and input_grid.shape != output_grid.shape:
                return False
        return True


@dataclass
class GridDSL:
    """Grid representation with DSL metadata."""
    data: np.ndarray
    tags: Set[str] = field(default_factory=set)
    provenance: List[str] = field(default_factory=list)
    
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
    
    def copy(self) -> 'GridDSL':
        return GridDSL(
            data=self.data.copy(),
            tags=set(self.tags),
            provenance=list(self.provenance)
        )
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, GridDSL):
            return False
        return np.array_equal(self.data, other.data)
    
    def to_list(self) -> List[List[int]]:
        return self.data.tolist()
    
    @staticmethod
    def from_list(data: List[List[int]]) -> 'GridDSL':
        return GridDSL(np.array(data, dtype=np.int8))
    
    def tag(self, tag: str) -> 'GridDSL':
        """Add a tag to the grid."""
        self.tags.add(tag)
        return self
    
    def with_provenance(self, step: str) -> 'GridDSL':
        """Add provenance information."""
        new_grid = self.copy()
        new_grid.provenance.append(step)
        return new_grid


class PrimitiveOp(ABC):
    """Abstract base class for primitive operations."""
    
    def __init__(self, name: str, op_type: OpType, complexity: int = 1):
        self.name = name
        self.op_type = op_type
        self.complexity = complexity
        self.constraints: List[TypeConstraint] = []
    
    @abstractmethod
    def apply(self, grid: GridDSL) -> GridDSL:
        """Apply the operation to a grid."""
        pass
    
    def add_constraint(self, constraint: TypeConstraint) -> 'PrimitiveOp':
        """Add a type constraint."""
        self.constraints.append(constraint)
        return self
    
    def __call__(self, grid: GridDSL) -> GridDSL:
        return self.apply(grid)
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.name})"
    
    def to_code(self) -> str:
        """Generate Python code representation."""
        return f"# {self.name}\n"


# === GEOMETRIC OPERATIONS ===

class FlipHorizontal(PrimitiveOp):
    """Horizontal flip (left-right)."""
    
    def __init__(self):
        super().__init__("flip_horizontal", OpType.GEOMETRIC, 1)
    
    def apply(self, grid: GridDSL) -> GridDSL:
        result = np.fliplr(grid.data)
        return GridDSL(result, grid.tags, grid.provenance + ["flip_h"])
    
    def to_code(self) -> str:
        return "np.fliplr(grid)"


class FlipVertical(PrimitiveOp):
    """Vertical flip (up-down)."""
    
    def __init__(self):
        super().__init__("flip_vertical", OpType.GEOMETRIC, 1)
    
    def apply(self, grid: GridDSL) -> GridDSL:
        result = np.flipud(grid.data)
        return GridDSL(result, grid.tags, grid.provenance + ["flip_v"])
    
    def to_code(self) -> str:
        return "np.flipud(grid)"


class Rotate90(PrimitiveOp):
    """Rotate 90 degrees clockwise."""
    
    def __init__(self, k: int = 1):
        super().__init__(f"rotate_{90*k}", OpType.GEOMETRIC, 1)
        self.k = k
    
    def apply(self, grid: GridDSL) -> GridDSL:
        result = np.rot90(grid.data, self.k)
        return GridDSL(result, grid.tags, grid.provenance + [f"rot_{self.k}"])
    
    def to_code(self) -> str:
        return f"np.rot90(grid, {self.k})"


class Transpose(PrimitiveOp):
    """Matrix transpose."""
    
    def __init__(self):
        super().__init__("transpose", OpType.GEOMETRIC, 1)
    
    def apply(self, grid: GridDSL) -> GridDSL:
        result = grid.data.T
        return GridDSL(result, grid.tags, grid.provenance + ["transpose"])
    
    def to_code(self) -> str:
        return "grid.T"


# === COLOR OPERATIONS ===

class ColorShift(PrimitiveOp):
    """Shift all colors by a value (mod 10)."""
    
    def __init__(self, shift: int):
        super().__init__(f"color_shift_{shift}", OpType.COLOR, 1)
        self.shift = shift
    
    def apply(self, grid: GridDSL) -> GridDSL:
        result = (grid.data + self.shift) % 10
        return GridDSL(result, grid.tags, grid.provenance + [f"shift_{self.shift}"])
    
    def to_code(self) -> str:
        return f"(grid + {self.shift}) % 10"


class ColorMap(PrimitiveOp):
    """Map specific colors to new values."""
    
    def __init__(self, mapping: Dict[int, int]):
        super().__init__(f"color_map_{mapping}", OpType.COLOR, 2)
        self.mapping = mapping
    
    def apply(self, grid: GridDSL) -> GridDSL:
        result = grid.data.copy()
        for old, new in self.mapping.items():
            result[result == old] = new
        return GridDSL(result, grid.tags, grid.provenance + [f"map_{self.mapping}"])
    
    def to_code(self) -> str:
        mapping_str = str(self.mapping)
        return f"color_map(grid, {mapping_str})"


class ReplaceColor(PrimitiveOp):
    """Replace one color with another."""
    
    def __init__(self, from_color: int, to_color: int):
        super().__init__(f"replace_{from_color}_to_{to_color}", OpType.COLOR, 1)
        self.from_color = from_color
        self.to_color = to_color
    
    def apply(self, grid: GridDSL) -> GridDSL:
        result = grid.data.copy()
        result[result == self.from_color] = self.to_color
        return GridDSL(result, grid.tags, grid.provenance + [f"repl_{self.from_color}_{self.to_color}"])
    
    def to_code(self) -> str:
        return f"replace_color(grid, {self.from_color}, {self.to_color})"


# === STRUCTURAL OPERATIONS ===

class Tile(PrimitiveOp):
    """Tile the grid NxM times."""
    
    def __init__(self, n: int, m: int):
        super().__init__(f"tile_{n}x{m}", OpType.STRUCTURAL, 2)
        self.n = n
        self.m = m
    
    def apply(self, grid: GridDSL) -> GridDSL:
        result = np.tile(grid.data, (self.n, self.m))
        return GridDSL(result, grid.tags, grid.provenance + [f"tile_{self.n}_{self.m}"])
    
    def to_code(self) -> str:
        return f"np.tile(grid, ({self.n}, {self.m}))"


class Crop(PrimitiveOp):
    """Crop grid to specified bounds."""
    
    def __init__(self, top: int, left: int, bottom: int, right: int):
        super().__init__(f"crop_{top},{left},{bottom},{right}", OpType.STRUCTURAL, 2)
        self.bounds = (top, left, bottom, right)
    
    def apply(self, grid: GridDSL) -> GridDSL:
        t, l, b, r = self.bounds
        result = grid.data[t:b, l:r]
        return GridDSL(result, grid.tags, grid.provenance + [f"crop_{self.bounds}"])
    
    def to_code(self) -> str:
        t, l, b, r = self.bounds
        return f"grid[{t}:{b}, {l}:{r}]"


class Pad(PrimitiveOp):
    """Pad grid with a color."""
    
    def __init__(self, padding: int, color: int = 0):
        super().__init__(f"pad_{padding}_color_{color}", OpType.STRUCTURAL, 2)
        self.padding = padding
        self.color = color
    
    def apply(self, grid: GridDSL) -> GridDSL:
        result = np.pad(
            grid.data,
            ((self.padding, self.padding), (self.padding, self.padding)),
            constant_values=self.color
        )
        return GridDSL(result, grid.tags, grid.provenance + [f"pad_{self.padding}"])
    
    def to_code(self) -> str:
        return f"np.pad(grid, {self.padding}, constant_values={self.color})"


# === OBJECT OPERATIONS ===

class ExtractObjects(PrimitiveOp):
    """Extract objects and return grid with only objects of certain properties."""
    
    def __init__(self, min_size: int = 1, max_size: Optional[int] = None):
        super().__init__(f"extract_objects_{min_size}_{max_size}", OpType.OBJECT, 3)
        self.min_size = min_size
        self.max_size = max_size
    
    def apply(self, grid: GridDSL) -> GridDSL:
        # Simple connected component extraction
        visited = np.zeros_like(grid.data, dtype=bool)
        result = np.zeros_like(grid.data)
        
        for r in range(grid.height):
            for c in range(grid.width):
                if visited[r, c] or grid.data[r, c] == 0:
                    continue
                
                color = int(grid.data[r, c])
                pixels = []
                queue = [(r, c)]
                visited[r, c] = True
                
                while queue:
                    cr, cc = queue.pop(0)
                    pixels.append((cr, cc))
                    
                    for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                        nr, nc = cr + dr, cc + dc
                        if 0 <= nr < grid.height and 0 <= nc < grid.width:
                            if not visited[nr, nc] and grid.data[nr, nc] == color:
                                visited[nr, nc] = True
                                queue.append((nr, nc))
                
                # Check size constraint
                size = len(pixels)
                if size >= self.min_size and (self.max_size is None or size <= self.max_size):
                    for pr, pc in pixels:
                        result[pr, pc] = color
        
        return GridDSL(result, grid.tags, grid.provenance + [f"extract_{self.min_size}"])
    
    def to_code(self) -> str:
        return f"extract_objects(grid, min_size={self.min_size}, max_size={self.max_size})"


# === COMPOSITION OPERATIONS ===

class Compose(PrimitiveOp):
    """Compose multiple operations sequentially."""
    
    def __init__(self, *operations: PrimitiveOp):
        names = " -> ".join(op.name for op in operations)
        super().__init__(f"compose({names})", OpType.COMPOSITIONAL, sum(op.complexity for op in operations))
        self.operations = list(operations)
    
    def apply(self, grid: GridDSL) -> GridDSL:
        result = grid
        for op in self.operations:
            result = op.apply(result)
        return result
    
    def to_code(self) -> str:
        return " -> ".join(op.to_code() for op in self.operations)
    
    def add(self, op: PrimitiveOp) -> 'Compose':
        """Add operation to composition."""
        return Compose(*self.operations, op)


class Branch(PrimitiveOp):
    """Apply different operations based on a condition."""
    
    def __init__(self, 
                 condition: Callable[[GridDSL], bool],
                 if_true: PrimitiveOp,
                 if_false: PrimitiveOp):
        super().__init__(f"branch({if_true.name},{if_false.name})", OpType.COMPOSITIONAL, 
                        max(if_true.complexity, if_false.complexity) + 1)
        self.condition = condition
        self.if_true = if_true
        self.if_false = if_false
    
    def apply(self, grid: GridDSL) -> GridDSL:
        if self.condition(grid):
            return self.if_true.apply(grid)
        else:
            return self.if_false.apply(grid)
    
    def to_code(self) -> str:
        return f"if (condition): {self.if_true.to_code()} else: {self.if_false.to_code()}"


# === DSL LIBRARY ===

class PatternLibrary:
    """Library of common transformation patterns."""
    
    @staticmethod
    def identity() -> PrimitiveOp:
        """Identity transformation."""
        class Identity(PrimitiveOp):
            def __init__(self):
                super().__init__("identity", OpType.COMPOSITIONAL, 0)
            def apply(self, grid: GridDSL) -> GridDSL:
                return grid.copy()
            def to_code(self) -> str:
                return "grid"
        return Identity()
    
    @staticmethod
    def symmetry_group() -> List[PrimitiveOp]:
        """All symmetry transformations."""
        return [
            FlipHorizontal(),
            FlipVertical(),
            Rotate90(1),
            Rotate90(2),
            Rotate90(3),
            Transpose(),
        ]
    
    @staticmethod
    def color_shifts() -> List[PrimitiveOp]:
        """Common color shift operations."""
        return [ColorShift(i) for i in range(1, 10)]
    
    @staticmethod
    def tile_patterns() -> List[PrimitiveOp]:
        """Common tiling patterns."""
        return [
            Tile(1, 2),  # Horizontal double
            Tile(2, 1),  # Vertical double
            Tile(2, 2),  # 2x2 tile
            Tile(3, 1),  # Triple vertical
        ]
    
    @staticmethod
    def common_compositions() -> List[PrimitiveOp]:
        """Common operation compositions."""
        return [
            Compose(FlipHorizontal(), FlipVertical()),
            Compose(Rotate90(1), ColorShift(1)),
            Compose(Tile(2, 1), ColorShift(1)),
        ]


# === PROGRAM SYNTHESIS ===

@dataclass
class SynthesisResult:
    """Result of program synthesis."""
    program: PrimitiveOp
    accuracy: float
    complexity: int
    examples_verified: int
    total_examples: int
    
    @property
    def score(self) -> float:
        """Combined score (higher is better)."""
        # Accuracy is primary, with penalty for complexity
        return self.accuracy - (self.complexity * 0.01)


class ProgramSynthesizer:
    """Synthesize transformation programs from input/output examples."""
    
    def __init__(self, max_complexity: int = 5):
        self.max_complexity = max_complexity
        self.library = PatternLibrary()
    
    def synthesize(self, 
                   examples: List[Tuple[GridDSL, GridDSL]],
                   primitives: Optional[List[PrimitiveOp]] = None) -> List[SynthesisResult]:
        """
        Synthesize programs that explain the examples.
        
        Uses a simple search: try all primitives, then compositions up to max_complexity.
        """
        if primitives is None:
            primitives = self._get_default_primitives()
        
        results = []
        
        # Try single primitives
        for op in primitives:
            accuracy = self._verify(op, examples)
            if accuracy > 0:
                results.append(SynthesisResult(
                    program=op,
                    accuracy=accuracy,
                    complexity=op.complexity,
                    examples_verified=int(accuracy * len(examples)),
                    total_examples=len(examples)
                ))
        
        # Try compositions (up to 2 operations for efficiency)
        if self.max_complexity >= 2:
            for op1 in primitives:
                for op2 in primitives:
                    composed = Compose(op1, op2)
                    accuracy = self._verify(composed, examples)
                    if accuracy > 0:
                        results.append(SynthesisResult(
                            program=composed,
                            accuracy=accuracy,
                            complexity=composed.complexity,
                            examples_verified=int(accuracy * len(examples)),
                            total_examples=len(examples)
                        ))
        
        # Sort by score
        results.sort(key=lambda r: r.score, reverse=True)
        return results
    
    def _verify(self, program: PrimitiveOp, 
                examples: List[Tuple[GridDSL, GridDSL]]) -> float:
        """Verify program on all examples, return accuracy."""
        correct = 0
        for inp, expected_out in examples:
            try:
                actual_out = program.apply(inp)
                if actual_out == expected_out:
                    correct += 1
            except Exception:
                pass
        return correct / len(examples)
    
    def _get_default_primitives(self) -> List[PrimitiveOp]:
        """Get default set of primitives to try."""
        primitives = []
        primitives.extend(self.library.symmetry_group())
        primitives.extend(self.library.color_shifts()[:5])  # Limit shifts
        primitives.extend(self.library.tile_patterns())
        primitives.append(ExtractObjects(min_size=1))
        return primitives


# === CODE GENERATION ===

class CodeGenerator:
    """Generate executable Python code from DSL programs."""
    
    def generate(self, program: PrimitiveOp, 
                 function_name: str = "transform") -> str:
        """Generate Python function from DSL program."""
        lines = [
            "import numpy as np",
            "",
            f"def {function_name}(grid):",
            f"    # Generated from DSL: {program.name}",
            f"    result = {program.to_code()}",
            "    return result",
        ]
        return "\n".join(lines)
    
    def generate_with_helpers(self, program: PrimitiveOp,
                              function_name: str = "transform") -> str:
        """Generate code with helper functions."""
        helpers = self._get_helpers(program)
        
        lines = [
            "import numpy as np",
            "",
        ]
        
        if helpers:
            lines.extend(helpers)
            lines.append("")
        
        lines.extend([
            f"def {function_name}(grid):",
            f"    # Generated from DSL: {program.name}",
            f"    return {program.to_code()}",
        ])
        
        return "\n".join(lines)
    
    def _get_helpers(self, program: PrimitiveOp) -> List[str]:
        """Get required helper functions."""
        helpers = []
        
        # Check what helpers are needed
        code = program.to_code()
        if "color_map" in code:
            helpers.append(self._color_map_helper())
        if "replace_color" in code:
            helpers.append(self._replace_color_helper())
        if "extract_objects" in code:
            helpers.append(self._extract_objects_helper())
        
        return helpers
    
    def _color_map_helper(self) -> str:
        return '''def color_map(grid, mapping):
    result = grid.copy()
    for old, new in mapping.items():
        result[result == old] = new
    return result'''
    
    def _replace_color_helper(self) -> str:
        return '''def replace_color(grid, from_c, to_c):
    result = grid.copy()
    result[result == from_c] = to_c
    return result'''
    
    def _extract_objects_helper(self) -> str:
        return '''def extract_objects(grid, min_size=1, max_size=None):
    from collections import deque
    visited = np.zeros_like(grid, dtype=bool)
    result = np.zeros_like(grid)
    
    for r in range(grid.shape[0]):
        for c in range(grid.shape[1]):
            if visited[r, c] or grid[r, c] == 0:
                continue
            
            color = int(grid[r, c])
            pixels = []
            queue = deque([(r, c)])
            visited[r, c] = True
            
            while queue:
                cr, cc = queue.popleft()
                pixels.append((cr, cc))
                for dr, dc in [(-1,0), (1,0), (0,-1), (0,1)]:
                    nr, nc = cr + dr, cc + dc
                    if 0 <= nr < grid.shape[0] and 0 <= nc < grid.shape[1]:
                        if not visited[nr, nc] and grid[nr, nc] == color:
                            visited[nr, nc] = True
                            queue.append((nr, nc))
            
            size = len(pixels)
            if size >= min_size and (max_size is None or size <= max_size):
                for pr, pc in pixels:
                    result[pr, pc] = color
    
    return result'''


# === INTEGRATION WITH WORLD MODEL SOLVER ===

def dsl_to_world_model(program: PrimitiveOp, 
                       name: Optional[str] = None) -> Dict[str, Any]:
    """
    Convert DSL program to world model format for integration.
    
    Returns dict compatible with executable_world_model_solver.WorldModel
    """
    generator = CodeGenerator()
    code = generator.generate_with_helpers(program)
    
    return {
        'name': name or program.name,
        'code': code,
        'description': f'DSL program: {program.name}',
        'complexity': program.complexity,
        'dsl_program': program,
    }


def create_dsl_solver(examples: List[Tuple[GridDSL, GridDSL]],
                      max_complexity: int = 3) -> Optional[PrimitiveOp]:
    """
    Create a DSL-based solver for the given examples.
    
    Returns the best program found, or None if no solution.
    """
    synthesizer = ProgramSynthesizer(max_complexity=max_complexity)
    results = synthesizer.synthesize(examples)
    
    if not results:
        return None
    
    best = results[0]
    if best.accuracy == 1.0:
        return best.program
    
    return best.program if best.accuracy >= 0.5 else None


# === UTILITY FUNCTIONS ===

def quick_compose(*ops: PrimitiveOp) -> Compose:
    """Quick helper to compose operations."""
    return Compose(*ops)


def infer_color_mapping(in_grid: GridDSL, out_grid: GridDSL) -> Optional[ColorMap]:
    """Infer color mapping from input/output pair."""
    if in_grid.shape != out_grid.shape:
        return None
    
    in_colors = set(in_grid.data.flatten())
    mapping = {}
    
    for color in in_colors:
        mask = in_grid.data == color
        out_vals = out_grid.data[mask]
        if len(set(out_vals)) == 1:
            mapping[color] = int(out_vals[0])
    
    if len(mapping) == len(in_colors):
        return ColorMap(mapping)
    
    return None


def infer_symmetry_transform(in_grid: GridDSL, out_grid: GridDSL) -> Optional[PrimitiveOp]:
    """Infer symmetry transformation from input/output pair."""
    if in_grid.shape != out_grid.shape:
        return None
    
    # Try each symmetry
    transforms = PatternLibrary.symmetry_group()
    for t in transforms:
        result = t.apply(in_grid)
        if result == out_grid:
            return t
    
    return None


# Export public API
__all__ = [
    # Core classes
    'GridDSL',
    'PrimitiveOp',
    'OpType',
    'TypeConstraint',
    'Compose',
    'Branch',
    
    # Geometric ops
    'FlipHorizontal',
    'FlipVertical',
    'Rotate90',
    'Transpose',
    
    # Color ops
    'ColorShift',
    'ColorMap',
    'ReplaceColor',
    
    # Structural ops
    'Tile',
    'Crop',
    'Pad',
    
    # Object ops
    'ExtractObjects',
    
    # Library
    'PatternLibrary',
    'ProgramSynthesizer',
    'SynthesisResult',
    'CodeGenerator',
    
    # Integration
    'dsl_to_world_model',
    'create_dsl_solver',
    
    # Utilities
    'quick_compose',
    'infer_color_mapping',
    'infer_symmetry_transform',
]
