"""
Tests for ARC-AGI-3 Solver
Validates pattern recognition, symmetry analysis, and test-time adaptation
"""

import sys
sys.path.insert(0, '/home/workspace/agi-research')

import unittest
import numpy as np
from core.arc_agi_solver import (
    Grid, ARCTask, ARCSolver, PatternLibrary, SymmetryAnalyzer,
    PatternType, create_sample_task, create_color_progression_task
)


class TestGrid(unittest.TestCase):
    """Test Grid operations"""
    
    def test_grid_creation(self):
        """Test grid creation from list"""
        grid = Grid([
            [1, 2, 3],
            [4, 5, 6]
        ])
        self.assertEqual(grid.shape, (2, 3))
        self.assertEqual(grid.height, 2)
        self.assertEqual(grid.width, 3)
    
    def test_grid_equality(self):
        """Test grid equality"""
        grid1 = Grid([[1, 2], [3, 4]])
        grid2 = Grid([[1, 2], [3, 4]])
        grid3 = Grid([[1, 2], [3, 5]])
        
        self.assertEqual(grid1, grid2)
        self.assertNotEqual(grid1, grid3)
    
    def test_grid_rotate(self):
        """Test grid rotation"""
        grid = Grid([
            [1, 2],
            [3, 4]
        ])
        rotated = grid.rotate(1)
        # np.rot90 rotates counterclockwise: [[1,2],[3,4]] -> [[2,4],[1,3]]
        expected = Grid([
            [2, 4],
            [1, 3]
        ])
        self.assertEqual(rotated, expected)
    
    def test_grid_flip_horizontal(self):
        """Test horizontal flip"""
        grid = Grid([
            [1, 2, 3],
            [4, 5, 6]
        ])
        flipped = grid.flip(1)
        expected = Grid([
            [3, 2, 1],
            [6, 5, 4]
        ])
        self.assertEqual(flipped, expected)
    
    def test_grid_flip_vertical(self):
        """Test vertical flip"""
        grid = Grid([
            [1, 2],
            [3, 4],
            [5, 6]
        ])
        flipped = grid.flip(0)
        expected = Grid([
            [5, 6],
            [3, 4],
            [1, 2]
        ])
        self.assertEqual(flipped, expected)
    
    def test_grid_transpose(self):
        """Test grid transpose"""
        grid = Grid([
            [1, 2, 3],
            [4, 5, 6]
        ])
        transposed = grid.transpose()
        expected = Grid([
            [1, 4],
            [2, 5],
            [3, 6]
        ])
        self.assertEqual(transposed, expected)
    
    def test_grid_replace_color(self):
        """Test color replacement"""
        grid = Grid([
            [1, 2, 1],
            [2, 1, 2]
        ])
        replaced = grid.replace_color(1, 9)
        expected = Grid([
            [9, 2, 9],
            [2, 9, 2]
        ])
        self.assertEqual(replaced, expected)
    
    def test_grid_fill(self):
        """Test grid fill"""
        grid = Grid([
            [1, 2],
            [3, 4]
        ])
        filled = grid.fill(0)
        expected = Grid([
            [0, 0],
            [0, 0]
        ])
        self.assertEqual(filled, expected)


class TestSymmetryAnalyzer(unittest.TestCase):
    """Test symmetry analysis"""
    
    def test_vertical_symmetry(self):
        """Test vertical symmetry detection"""
        grid = Grid([
            [1, 2, 1],
            [3, 4, 3]
        ])
        self.assertTrue(SymmetryAnalyzer.has_vertical_symmetry(grid))
    
    def test_no_vertical_symmetry(self):
        """Test non-symmetric grid"""
        grid = Grid([
            [1, 2, 3],
            [4, 5, 6]
        ])
        self.assertFalse(SymmetryAnalyzer.has_vertical_symmetry(grid))
    
    def test_horizontal_symmetry(self):
        """Test horizontal symmetry"""
        grid = Grid([
            [1, 2],
            [3, 4],
            [1, 2]
        ])
        self.assertTrue(SymmetryAnalyzer.has_horizontal_symmetry(grid))
    
    def test_rotational_symmetry(self):
        """Test 180-degree rotational symmetry"""
        grid = Grid([
            [1, 2],
            [2, 1]
        ])
        self.assertTrue(SymmetryAnalyzer.has_rotational_symmetry(grid))
    
    def test_diagonal_symmetry(self):
        """Test diagonal symmetry"""
        grid = Grid([
            [1, 2],
            [2, 1]
        ])
        self.assertTrue(SymmetryAnalyzer.has_diagonal_symmetry(grid))
    
    def test_symmetry_scores(self):
        """Test symmetry score calculation"""
        grid = Grid([
            [1, 2, 1],
            [3, 4, 3]
        ])
        scores = SymmetryAnalyzer.get_symmetry_score(grid)
        self.assertEqual(scores['vertical'], 1.0)
        self.assertEqual(scores['horizontal'], 0.0)


class TestPatternLibrary(unittest.TestCase):
    """Test pattern detection"""
    
    def test_detect_vertical_flip(self):
        """Test vertical flip pattern detection"""
        library = PatternLibrary()
        
        input_grid = Grid([
            [1, 2, 3],
            [4, 5, 6]
        ])
        output_grid = Grid([
            [3, 2, 1],
            [6, 5, 4]
        ])
        
        hypotheses = library.analyze_pair(input_grid, output_grid)
        self.assertTrue(any(h.pattern_type == PatternType.SYMMETRY for h in hypotheses))
    
    def test_detect_horizontal_flip(self):
        """Test horizontal flip pattern detection"""
        library = PatternLibrary()
        
        input_grid = Grid([
            [1, 2],
            [3, 4],
            [5, 6]
        ])
        output_grid = Grid([
            [5, 6],
            [3, 4],
            [1, 2]
        ])
        
        hypotheses = library.analyze_pair(input_grid, output_grid)
        symmetry_hypotheses = [h for h in hypotheses if h.pattern_type == PatternType.SYMMETRY]
        self.assertTrue(len(symmetry_hypotheses) > 0)
    
    def test_detect_rotation(self):
        """Test rotation pattern detection"""
        library = PatternLibrary()
        
        input_grid = Grid([
            [1, 2],
            [3, 4]
        ])
        output_grid = Grid([
            [3, 1],
            [4, 2]
        ])
        
        hypotheses = library.analyze_pair(input_grid, output_grid)
        symmetry_hypotheses = [h for h in hypotheses if h.pattern_type == PatternType.SYMMETRY]
        self.assertTrue(len(symmetry_hypotheses) > 0)
    
    def test_detect_tiling(self):
        """Test tiling pattern detection"""
        library = PatternLibrary()
        
        input_grid = Grid([
            [1, 2],
            [3, 4]
        ])
        output_grid = Grid([
            [1, 2, 1, 2],
            [3, 4, 3, 4],
            [1, 2, 1, 2],
            [3, 4, 3, 4]
        ])
        
        hypotheses = library.analyze_pair(input_grid, output_grid)
        repetition_hypotheses = [h for h in hypotheses if h.pattern_type == PatternType.REPETITION]
        self.assertTrue(len(repetition_hypotheses) > 0)
    
    def test_detect_color_shift(self):
        """Test color shift pattern detection"""
        library = PatternLibrary()
        
        input_grid = Grid([
            [1, 1],
            [2, 2]
        ])
        output_grid = Grid([
            [2, 2],
            [3, 3]
        ])
        
        hypotheses = library.analyze_pair(input_grid, output_grid)
        progression_hypotheses = [h for h in hypotheses if h.pattern_type == PatternType.PROGRESSION]
        self.assertTrue(len(progression_hypotheses) > 0)
    
    def test_apply_transformation(self):
        """Test applying detected transformation"""
        library = PatternLibrary()
        
        input_grid = Grid([[1, 2, 3]])
        output_grid = Grid([[3, 2, 1]])
        
        hypotheses = library.analyze_pair(input_grid, output_grid)
        self.assertTrue(len(hypotheses) > 0)
        
        # Apply to new input
        new_input = Grid([[4, 5, 6]])
        result = hypotheses[0].apply(new_input)
        expected = Grid([[6, 5, 4]])
        self.assertEqual(result, expected)


class TestARCSolver(unittest.TestCase):
    """Test ARC solver"""
    
    def test_solver_creation(self):
        """Test solver initialization"""
        solver = ARCSolver()
        self.assertIsNotNone(solver.pattern_library)
        self.assertIsNotNone(solver.symmetry_analyzer)
    
    def test_solve_symmetry_task(self):
        """Test solving symmetry task"""
        solver = ARCSolver()
        task = create_sample_task()
        
        result = solver.solve(task)
        evaluation = solver.evaluate(task, result)
        
        self.assertTrue(evaluation['correct'])
        self.assertEqual(evaluation['pixel_accuracy'], 1.0)
    
    def test_solve_color_progression_task(self):
        """Test solving color progression task"""
        solver = ARCSolver()
        task = create_color_progression_task()
        
        result = solver.solve(task)
        evaluation = solver.evaluate(task, result)
        
        self.assertTrue(evaluation['correct'])
        self.assertEqual(evaluation['pixel_accuracy'], 1.0)
    
    def test_solver_stats(self):
        """Test solver statistics"""
        solver = ARCSolver()
        task = create_sample_task()
        solver.solve(task)
        
        stats = solver.get_stats()
        self.assertEqual(stats['total_attempts'], 1)
        self.assertIn('pattern_distribution', stats)
        self.assertIn('avg_confidence', stats)
    
    def test_evaluation_without_ground_truth(self):
        """Test evaluation when ground truth unavailable"""
        solver = ARCSolver()
        
        task = ARCTask(
            id="no_truth",
            train_examples=[],
            test_input=Grid([[1, 2], [3, 4]]),
            test_output=None
        )
        
        result = solver.solve(task)
        evaluation = solver.evaluate(task, result)
        
        self.assertEqual(evaluation['status'], 'no_ground_truth')
    
    def test_partial_accuracy(self):
        """Test partial accuracy calculation"""
        solver = ARCSolver()
        
        task = ARCTask(
            id="partial",
            train_examples=[],
            test_input=Grid([[1, 2], [3, 4]]),
            test_output=Grid([[1, 2], [3, 5]])
        )
        
        prediction = Grid([[1, 2], [3, 4]])
        evaluation = solver.evaluate(task, prediction)
        
        self.assertFalse(evaluation['correct'])
        self.assertEqual(evaluation['pixel_accuracy'], 0.75)


class TestARCTimeAdapter(unittest.TestCase):
    """Test test-time adaptation"""
    
    def test_adaptation_finds_patterns(self):
        """Test that adaptation finds consistent patterns"""
        solver = ARCSolver()
        task = create_sample_task()
        
        hypotheses = solver.adapter.adapt(task)
        
        # Should find at least one pattern
        self.assertTrue(len(hypotheses) > 0)
        
        # Pattern should have high confidence
        self.assertGreater(hypotheses[0].confidence, 0.5)
    
    def test_adaptation_history(self):
        """Test adaptation history tracking"""
        solver = ARCSolver()
        task = create_sample_task()
        
        solver.adapter.adapt(task)
        
        self.assertEqual(len(solver.adapter.adaptation_history), 1)
        self.assertEqual(solver.adapter.adaptation_history[0]['task_id'], task.id)
    
    def test_consistent_patterns_boosted(self):
        """Test that consistent patterns across examples get boosted confidence"""
        solver = ARCSolver()
        
        # Create task where same pattern applies to all examples
        train_1_in = Grid([[1, 2], [3, 4]])
        train_1_out = Grid([[4, 3], [2, 1]])  # Rotate 180
        
        train_2_in = Grid([[5, 6], [7, 8]])
        train_2_out = Grid([[8, 7], [6, 5]])  # Rotate 180
        
        task = ARCTask(
            id="consistent",
            train_examples=[(train_1_in, train_1_out), (train_2_in, train_2_out)],
            test_input=Grid([[1, 1], [2, 2]]),
            test_output=Grid([[2, 2], [1, 1]])
        )
        
        hypotheses = solver.adapter.adapt(task)
        
        # Should find rotation pattern with high confidence
        rotation_patterns = [h for h in hypotheses if 'rotate' in h.description.lower()]
        if rotation_patterns:
            self.assertGreater(rotation_patterns[0].confidence, 0.8)


class TestIntegration(unittest.TestCase):
    """Integration tests"""
    
    def test_full_pipeline(self):
        """Test complete solving pipeline"""
        # Create a multi-example task
        train_examples = [
            (Grid([[1, 2]]), Grid([[2, 1]])),
            (Grid([[3, 4]]), Grid([[4, 3]])),
            (Grid([[5, 6]]), Grid([[6, 5]]))
        ]
        
        task = ARCTask(
            id="integration_test",
            train_examples=train_examples,
            test_input=Grid([[7, 8]]),
            test_output=Grid([[8, 7]])
        )
        
        solver = ARCSolver()
        result = solver.solve(task)
        evaluation = solver.evaluate(task, result)
        
        self.assertTrue(evaluation['correct'])
    
    def test_multiple_pattern_types(self):
        """Test solver handles different pattern types"""
        test_cases = [
            ("flip", create_sample_task()),
            ("color_shift", create_color_progression_task())
        ]
        
        solver = ARCSolver()
        
        for name, task in test_cases:
            with self.subTest(pattern=name):
                result = solver.solve(task)
                evaluation = solver.evaluate(task, result)
                self.assertTrue(evaluation['correct'], f"Failed on {name}")


def run_tests():
    """Run all tests with verbosity"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestGrid))
    suite.addTests(loader.loadTestsFromTestCase(TestSymmetryAnalyzer))
    suite.addTests(loader.loadTestsFromTestCase(TestPatternLibrary))
    suite.addTests(loader.loadTestsFromTestCase(TestARCSolver))
    suite.addTests(loader.loadTestsFromTestCase(TestARCTimeAdapter))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
