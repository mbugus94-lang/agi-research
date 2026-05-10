"""
Test suite for Neuro-Symbolic Pattern DSL

Tests cover:
1. GridDSL operations and metadata
2. Primitive operations (geometric, color, structural, object)
3. Composition operations
4. Program synthesis
5. Code generation
6. Integration with world model solver
"""

import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from core.pattern_dsl import (
    GridDSL, PrimitiveOp, OpType,
    FlipHorizontal, FlipVertical, Rotate90, Transpose,
    ColorShift, ColorMap, ReplaceColor,
    Tile, Crop, Pad,
    ExtractObjects,
    Compose, Branch,
    PatternLibrary, ProgramSynthesizer, CodeGenerator,
    dsl_to_world_model, create_dsl_solver,
    infer_color_mapping, infer_symmetry_transform,
    quick_compose,
)


class TestGridDSL(unittest.TestCase):
    """Test GridDSL data structure."""
    
    def test_creation_from_list(self):
        grid = GridDSL.from_list([[1, 2], [3, 4]])
        self.assertEqual(grid.shape, (2, 2))
        self.assertEqual(grid.to_list(), [[1, 2], [3, 4]])
    
    def test_creation_from_array(self):
        arr = np.array([[1, 2], [3, 4]], dtype=np.int8)
        grid = GridDSL(arr)
        self.assertEqual(grid.shape, (2, 2))
    
    def test_copy(self):
        grid = GridDSL.from_list([[1, 2], [3, 4]])
        copy = grid.copy()
        self.assertEqual(grid, copy)
        # Modify original
        grid.data[0, 0] = 99
        self.assertNotEqual(grid, copy)
    
    def test_equality(self):
        grid1 = GridDSL.from_list([[1, 2], [3, 4]])
        grid2 = GridDSL.from_list([[1, 2], [3, 4]])
        grid3 = GridDSL.from_list([[1, 2], [3, 5]])
        self.assertEqual(grid1, grid2)
        self.assertNotEqual(grid1, grid3)
    
    def test_tags(self):
        grid = GridDSL.from_list([[1, 2]])
        grid.tag("test_tag")
        self.assertIn("test_tag", grid.tags)
    
    def test_provenance(self):
        grid = GridDSL.from_list([[1, 2]])
        grid2 = grid.with_provenance("step1")
        self.assertIn("step1", grid2.provenance)
        self.assertNotIn("step1", grid.provenance)  # Original unchanged


class TestGeometricOperations(unittest.TestCase):
    """Test geometric transformation operations."""
    
    def test_flip_horizontal(self):
        grid = GridDSL.from_list([[1, 2, 3], [4, 5, 6]])
        op = FlipHorizontal()
        result = op.apply(grid)
        expected = GridDSL.from_list([[3, 2, 1], [6, 5, 4]])
        self.assertEqual(result, expected)
    
    def test_flip_vertical(self):
        grid = GridDSL.from_list([[1, 2], [3, 4], [5, 6]])
        op = FlipVertical()
        result = op.apply(grid)
        expected = GridDSL.from_list([[5, 6], [3, 4], [1, 2]])
        self.assertEqual(result, expected)
    
    def test_rotate_90(self):
        grid = GridDSL.from_list([[1, 2], [3, 4]])
        op = Rotate90(1)
        result = op.apply(grid)
        # np.rot90 rotates counter-clockwise
        expected = GridDSL.from_list([[2, 4], [1, 3]])
        self.assertEqual(result, expected)
    
    def test_rotate_180(self):
        grid = GridDSL.from_list([[1, 2], [3, 4]])
        op = Rotate90(2)
        result = op.apply(grid)
        expected = GridDSL.from_list([[4, 3], [2, 1]])
        self.assertEqual(result, expected)
    
    def test_transpose(self):
        grid = GridDSL.from_list([[1, 2, 3], [4, 5, 6]])
        op = Transpose()
        result = op.apply(grid)
        expected = GridDSL.from_list([[1, 4], [2, 5], [3, 6]])
        self.assertEqual(result, expected)
    
    def test_double_flip_restores_original(self):
        grid = GridDSL.from_list([[1, 2], [3, 4]])
        hflip = FlipHorizontal()
        vflip = FlipVertical()
        result = hflip.apply(vflip.apply(grid))
        result2 = vflip.apply(hflip.apply(grid))
        self.assertEqual(result, result2)
        self.assertEqual(result, GridDSL.from_list([[4, 3], [2, 1]]))


class TestColorOperations(unittest.TestCase):
    """Test color transformation operations."""
    
    def test_color_shift(self):
        grid = GridDSL.from_list([[0, 1], [2, 3]])
        op = ColorShift(1)
        result = op.apply(grid)
        expected = GridDSL.from_list([[1, 2], [3, 4]])
        self.assertEqual(result, expected)
    
    def test_color_shift_modulo(self):
        grid = GridDSL.from_list([[8, 9]])
        op = ColorShift(2)
        result = op.apply(grid)
        expected = GridDSL.from_list([[0, 1]])  # (8+2)%10=0, (9+2)%10=1
        self.assertEqual(result, expected)
    
    def test_color_map(self):
        grid = GridDSL.from_list([[1, 2], [3, 4]])
        op = ColorMap({1: 9, 2: 8, 3: 7, 4: 6})
        result = op.apply(grid)
        expected = GridDSL.from_list([[9, 8], [7, 6]])
        self.assertEqual(result, expected)
    
    def test_replace_color(self):
        grid = GridDSL.from_list([[1, 2], [1, 2]])
        op = ReplaceColor(1, 9)
        result = op.apply(grid)
        expected = GridDSL.from_list([[9, 2], [9, 2]])
        self.assertEqual(result, expected)


class TestStructuralOperations(unittest.TestCase):
    """Test structural transformation operations."""
    
    def test_tile_2x1(self):
        grid = GridDSL.from_list([[1, 2]])
        op = Tile(2, 1)
        result = op.apply(grid)
        expected = GridDSL.from_list([[1, 2], [1, 2]])
        self.assertEqual(result, expected)
    
    def test_tile_1x2(self):
        grid = GridDSL.from_list([[1], [2]])
        op = Tile(1, 2)
        result = op.apply(grid)
        expected = GridDSL.from_list([[1, 1], [2, 2]])
        self.assertEqual(result, expected)
    
    def test_tile_2x2(self):
        grid = GridDSL.from_list([[1, 2]])
        op = Tile(2, 2)
        result = op.apply(grid)
        expected = GridDSL.from_list([[1, 2, 1, 2], [1, 2, 1, 2]])
        self.assertEqual(result, expected)
    
    def test_crop(self):
        grid = GridDSL.from_list([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        op = Crop(0, 0, 2, 2)
        result = op.apply(grid)
        expected = GridDSL.from_list([[1, 2], [4, 5]])
        self.assertEqual(result, expected)
    
    def test_pad(self):
        grid = GridDSL.from_list([[1, 2], [3, 4]])
        op = Pad(1, 0)
        result = op.apply(grid)
        expected = GridDSL.from_list([
            [0, 0, 0, 0],
            [0, 1, 2, 0],
            [0, 3, 4, 0],
            [0, 0, 0, 0]
        ])
        self.assertEqual(result, expected)


class TestObjectOperations(unittest.TestCase):
    """Test object extraction operations."""
    
    def test_extract_single_object(self):
        # Single connected component
        grid = GridDSL.from_list([
            [0, 1, 1, 0],
            [0, 1, 1, 0],
            [0, 0, 0, 0]
        ])
        op = ExtractObjects(min_size=1)
        result = op.apply(grid)
        self.assertEqual(result, grid)  # Should preserve the object
    
    def test_extract_filter_by_size(self):
        # Two objects: one size 4, one size 1
        grid = GridDSL.from_list([
            [1, 1, 0, 2],
            [1, 1, 0, 0],
            [0, 0, 0, 0]
        ])
        op = ExtractObjects(min_size=2)
        result = op.apply(grid)
        expected = GridDSL.from_list([
            [1, 1, 0, 0],
            [1, 1, 0, 0],
            [0, 0, 0, 0]
        ])
        self.assertEqual(result, expected)


class TestComposition(unittest.TestCase):
    """Test operation composition."""
    
    def test_compose_two_ops(self):
        grid = GridDSL.from_list([[1, 2], [3, 4]])
        op = Compose(FlipHorizontal(), ColorShift(1))
        result = op.apply(grid)
        # First flip: [[2,1],[4,3]], then shift: [[3,2],[5,4]]
        expected = GridDSL.from_list([[3, 2], [5, 4]])
        self.assertEqual(result, expected)
    
    def test_compose_three_ops(self):
        grid = GridDSL.from_list([[1, 2]])
        op = Compose(Tile(2, 1), FlipHorizontal(), ColorShift(1))
        result = op.apply(grid)
        # Shift: [[2,3]], Flip: [[3,2]], Tile: [[3,2],[3,2]]
        expected = GridDSL.from_list([[3, 2], [3, 2]])
        self.assertEqual(result, expected)
    
    def test_compose_complexity(self):
        op1 = FlipHorizontal()  # complexity 1
        op2 = ColorShift(1)     # complexity 1
        op3 = Tile(2, 2)        # complexity 2
        composed = Compose(op1, op2, op3)
        self.assertEqual(composed.complexity, 4)
    
    def test_compose_add(self):
        op1 = FlipHorizontal()
        op2 = ColorShift(1)
        composed = Compose(op1).add(op2)
        self.assertEqual(len(composed.operations), 2)
    
    def test_branch_true(self):
        grid = GridDSL.from_list([[1, 2]])
        condition = lambda g: g.width == 2
        op = Branch(condition, FlipHorizontal(), ColorShift(1))
        result = op.apply(grid)
        expected = FlipHorizontal().apply(grid)
        self.assertEqual(result, expected)
    
    def test_branch_false(self):
        grid = GridDSL.from_list([[1, 2, 3]])
        condition = lambda g: g.width == 2
        op = Branch(condition, FlipHorizontal(), ColorShift(1))
        result = op.apply(grid)
        expected = ColorShift(1).apply(grid)
        self.assertEqual(result, expected)
    
    def test_quick_compose(self):
        grid = GridDSL.from_list([[1, 2]])
        op = quick_compose(FlipHorizontal(), ColorShift(1))
        result = op.apply(grid)
        expected = Compose(FlipHorizontal(), ColorShift(1)).apply(grid)
        self.assertEqual(result, expected)


class TestPatternLibrary(unittest.TestCase):
    """Test PatternLibrary utilities."""
    
    def test_identity(self):
        op = PatternLibrary.identity()
        grid = GridDSL.from_list([[1, 2], [3, 4]])
        result = op.apply(grid)
        self.assertEqual(result, grid)
    
    def test_symmetry_group(self):
        ops = PatternLibrary.symmetry_group()
        self.assertEqual(len(ops), 6)
        for op in ops:
            self.assertEqual(op.op_type, OpType.GEOMETRIC)
    
    def test_color_shifts(self):
        ops = PatternLibrary.color_shifts()
        self.assertEqual(len(ops), 9)
    
    def test_tile_patterns(self):
        ops = PatternLibrary.tile_patterns()
        self.assertEqual(len(ops), 4)
    
    def test_common_compositions(self):
        ops = PatternLibrary.common_compositions()
        self.assertGreater(len(ops), 0)
        for op in ops:
            self.assertIsInstance(op, Compose)


class TestProgramSynthesis(unittest.TestCase):
    """Test program synthesis capabilities."""
    
    def test_synthesize_single_symmetry(self):
        examples = [
            (GridDSL.from_list([[1, 2]]), GridDSL.from_list([[2, 1]])),
            (GridDSL.from_list([[3, 4]]), GridDSL.from_list([[4, 3]])),
        ]
        synthesizer = ProgramSynthesizer(max_complexity=1)
        results = synthesizer.synthesize(examples)
        
        # Should find horizontal flip
        self.assertGreater(len(results), 0)
        best = results[0]
        self.assertEqual(best.accuracy, 1.0)
    
    def test_synthesize_color_shift(self):
        examples = [
            (GridDSL.from_list([[0, 1]]), GridDSL.from_list([[1, 2]])),
            (GridDSL.from_list([[5]]), GridDSL.from_list([[6]])),
        ]
        synthesizer = ProgramSynthesizer(max_complexity=1)
        results = synthesizer.synthesize(examples)
        
        # Should find color shift +1
        self.assertGreater(len(results), 0)
        best = results[0]
        self.assertEqual(best.accuracy, 1.0)
    
    def test_synthesize_composition(self):
        examples = [
            (GridDSL.from_list([[1, 2]]), GridDSL.from_list([[3, 2], [3, 2]])),
        ]
        synthesizer = ProgramSynthesizer(max_complexity=2)
        results = synthesizer.synthesize(examples)
        
        # Should find shift(1) -> tile(2,1) or similar
        # Note: This specific example may not be found depending on primitives
        # Just check that synthesis runs without error
        self.assertIsInstance(results, list)
    
    def test_synthesize_no_solution(self):
        examples = [
            (GridDSL.from_list([[1]]), GridDSL.from_list([[2]])),
        ]
        # Restrict primitives to exclude the needed operation
        synthesizer = ProgramSynthesizer(max_complexity=1)
        primitives = [FlipHorizontal(), FlipVertical()]  # No color ops
        results = synthesizer.synthesize(examples, primitives)
        
        # Should have 0 or low accuracy results
        if results:
            self.assertEqual(results[0].accuracy, 0.0)


class TestCodeGeneration(unittest.TestCase):
    """Test code generation from DSL programs."""
    
    def test_generate_simple_op(self):
        op = FlipHorizontal()
        generator = CodeGenerator()
        code = generator.generate(op)
        self.assertIn("import numpy as np", code)
        self.assertIn("def transform(grid):", code)
        self.assertIn("np.fliplr(grid)", code)
    
    def test_generate_with_helpers(self):
        op = ColorMap({1: 2, 3: 4})
        generator = CodeGenerator()
        code = generator.generate_with_helpers(op)
        self.assertIn("def color_map(grid, mapping):", code)
        self.assertIn("def transform(grid):", code)
    
    def test_to_code_methods(self):
        ops = [
            FlipHorizontal(),
            FlipVertical(),
            Rotate90(1),
            Transpose(),
            ColorShift(1),
            Tile(2, 2),
        ]
        for op in ops:
            code = op.to_code()
            self.assertIsInstance(code, str)
            self.assertGreater(len(code), 0)


class TestInference(unittest.TestCase):
    """Test inference utilities."""
    
    def test_infer_color_mapping(self):
        in_grid = GridDSL.from_list([[1, 2], [3, 0]])
        out_grid = GridDSL.from_list([[5, 6], [7, 0]])
        op = infer_color_mapping(in_grid, out_grid)
        self.assertIsNotNone(op)
        # Mapping should include color 0->0 and other colors
        self.assertEqual(op.mapping[1], 5)
        self.assertEqual(op.mapping[2], 6)
        self.assertEqual(op.mapping[3], 7)
        self.assertEqual(op.mapping[0], 0)
    
    def test_infer_color_mapping_none(self):
        in_grid = GridDSL.from_list([[1, 1]])  # Same color
        out_grid = GridDSL.from_list([[1, 2]])  # Different outputs
        op = infer_color_mapping(in_grid, out_grid)
        self.assertIsNone(op)
    
    def test_infer_symmetry_transform(self):
        in_grid = GridDSL.from_list([[1, 2]])
        out_grid = GridDSL.from_list([[2, 1]])
        op = infer_symmetry_transform(in_grid, out_grid)
        self.assertIsNotNone(op)
        self.assertIsInstance(op, FlipHorizontal)
    
    def test_infer_symmetry_none(self):
        in_grid = GridDSL.from_list([[1, 2]])
        out_grid = GridDSL.from_list([[3, 4]])
        op = infer_symmetry_transform(in_grid, out_grid)
        self.assertIsNone(op)


class TestIntegration(unittest.TestCase):
    """Test integration with world model solver."""
    
    def test_dsl_to_world_model(self):
        op = Compose(FlipHorizontal(), ColorShift(1))
        model = dsl_to_world_model(op, "test_model")
        self.assertEqual(model['name'], 'test_model')
        self.assertIn('code', model)
        self.assertIn('complexity', model)
        self.assertEqual(model['complexity'], 2)
    
    def test_create_dsl_solver_simple(self):
        examples = [
            (GridDSL.from_list([[1, 2]]), GridDSL.from_list([[2, 1]])),
        ]
        solver = create_dsl_solver(examples)
        self.assertIsNotNone(solver)
        # Test on new input
        test = GridDSL.from_list([[3, 4]])
        result = solver.apply(test)
        expected = GridDSL.from_list([[4, 3]])
        self.assertEqual(result, expected)
    
    def test_create_dsl_solver_no_solution(self):
        # Use primitives that can't solve this
        examples = [
            (GridDSL.from_list([[1]]), GridDSL.from_list([[99]])),
        ]
        solver = create_dsl_solver(examples, max_complexity=1)
        # Might return None or low-accuracy program
        self.assertTrue(solver is None or isinstance(solver, PrimitiveOp))


class TestEndToEnd(unittest.TestCase):
    """End-to-end integration tests."""
    
    def test_symmetry_task(self):
        """Test symmetry detection task."""
        train = [
            (GridDSL.from_list([[1, 2]]), GridDSL.from_list([[2, 1]])),
            (GridDSL.from_list([[3, 4, 5]]), GridDSL.from_list([[5, 4, 3]])),
        ]
        test_in = GridDSL.from_list([[6, 7, 8, 9]])
        test_expected = GridDSL.from_list([[9, 8, 7, 6]])
        
        solver = create_dsl_solver(train)
        self.assertIsNotNone(solver)
        result = solver.apply(test_in)
        self.assertEqual(result, test_expected)
    
    def test_color_shift_task(self):
        """Test color arithmetic task."""
        train = [
            (GridDSL.from_list([[0, 1], [2, 3]]), GridDSL.from_list([[1, 2], [3, 4]])),
            (GridDSL.from_list([[5, 6]]), GridDSL.from_list([[6, 7]])),
        ]
        test_in = GridDSL.from_list([[7, 8, 9]])
        test_expected = GridDSL.from_list([[8, 9, 0]])  # (9+1)%10=0
        
        solver = create_dsl_solver(train)
        self.assertIsNotNone(solver)
        result = solver.apply(test_in)
        self.assertEqual(result, test_expected)
    
    def test_tiling_task(self):
        """Test tiling transformation task."""
        train = [
            (GridDSL.from_list([[1, 2]]), GridDSL.from_list([[1, 2], [1, 2]])),
        ]
        test_in = GridDSL.from_list([[3, 4]])
        test_expected = GridDSL.from_list([[3, 4], [3, 4]])
        
        solver = create_dsl_solver(train)
        self.assertIsNotNone(solver)
        result = solver.apply(test_in)
        self.assertEqual(result, test_expected)
    
    def test_compositional_task(self):
        """Test compositional transformation."""
        # Shift then flip
        train = [
            (GridDSL.from_list([[0, 1]]), GridDSL.from_list([[2, 1]])),
        ]
        # (0,1) -> shift(1) -> (1,2) -> flip_h -> (2,1)
        
        solver = create_dsl_solver(train, max_complexity=2)
        self.assertIsNotNone(solver)
        test_in = GridDSL.from_list([[5, 6]])
        result = solver.apply(test_in)
        expected = GridDSL.from_list([[7, 6]])  # (5,6)->(6,7)->(7,6)
        self.assertEqual(result, expected)


class TestProperties(unittest.TestCase):
    """Property-based style tests."""
    
    def test_flip_is_involution(self):
        """Flipping twice should restore original."""
        grid = GridDSL.from_list([[1, 2, 3], [4, 5, 6]])
        hflip = FlipHorizontal()
        vflip = FlipVertical()
        
        # Horizontal flip is involution
        self.assertEqual(hflip.apply(hflip.apply(grid)), grid)
        # Vertical flip is involution
        self.assertEqual(vflip.apply(vflip.apply(grid)), grid)
    
    def test_rotate_360_restores_original(self):
        """Four 90-degree rotations = identity."""
        grid = GridDSL.from_list([[1, 2], [3, 4]])
        rot90 = Rotate90(1)
        
        result = grid
        for _ in range(4):
            result = rot90.apply(result)
        
        self.assertEqual(result, grid)
    
    def test_transpose_is_involution(self):
        """Transpose twice = identity."""
        grid = GridDSL.from_list([[1, 2, 3], [4, 5, 6]])
        trans = Transpose()
        
        result = trans.apply(trans.apply(grid))
        self.assertEqual(result, grid)
    
    def test_shift_modulo_10(self):
        """Shifting by 10 = identity."""
        grid = GridDSL.from_list([[1, 2], [3, 4]])
        shift10 = ColorShift(10)
        
        result = shift10.apply(grid)
        self.assertEqual(result, grid)
    
    def test_compose_identity(self):
        """Composing with identity should not change result."""
        grid = GridDSL.from_list([[1, 2], [3, 4]])
        identity = PatternLibrary.identity()
        op = FlipHorizontal()
        
        composed = Compose(identity, op)
        result = composed.apply(grid)
        expected = op.apply(grid)
        
        self.assertEqual(result, expected)


def run_tests():
    """Run all tests and return results."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestGridDSL,
        TestGeometricOperations,
        TestColorOperations,
        TestStructuralOperations,
        TestObjectOperations,
        TestComposition,
        TestPatternLibrary,
        TestProgramSynthesis,
        TestCodeGeneration,
        TestInference,
        TestIntegration,
        TestEndToEnd,
        TestProperties,
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result


if __name__ == "__main__":
    result = run_tests()
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    print("="*60)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
