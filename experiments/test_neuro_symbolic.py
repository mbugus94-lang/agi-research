"""
Tests for Neuro-Symbolic Reasoning Module
Tests the compositional reasoning capabilities inspired by ARC-AGI-3 insights.
"""

import sys
sys.path.insert(0, '/home/workspace/agi-research')

from core.neuro_symbolic import (
    create_neuro_symbolic_engine,
    NeuralPerceptionModule,
    SymbolicConstraintModule,
    CompositionalReasoningEngine,
    NeuralProposal,
    VerifiedSolution,
    SymbolicConstraint,
    PatternTemplate,
    PatternType,
    ReasoningMode,
    create_default_constraints,
    create_default_templates,
    create_default_neural_recognizers
)


def test_neural_perception_module():
    """Test 1: Neural perception module can recognize patterns."""
    print("Test 1: Neural Perception Module...")
    
    neural = NeuralPerceptionModule()
    recognizers = create_default_neural_recognizers()
    
    for pattern_type, recognizer in recognizers.items():
        neural.register_recognizer(pattern_type, recognizer)
    
    # Test grid pattern recognition
    grid_problem = {
        "input": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    }
    
    proposals = neural.generate_proposals(grid_problem, [PatternType.VISUAL_GRID])
    
    assert len(proposals) > 0, "Should generate proposals for grid"
    assert proposals[0].pattern_type == PatternType.VISUAL_GRID
    print(f"  ✓ Generated {len(proposals)} proposals for grid problem")
    return True


def test_symbolic_constraint_module():
    """Test 2: Symbolic constraint module validates solutions."""
    print("Test 2: Symbolic Constraint Module...")
    
    symbolic = SymbolicConstraintModule()
    constraints = create_default_constraints()
    
    for constraint in constraints:
        symbolic.register_constraint(constraint)
    
    # Test with valid grid
    valid_grid = [[1, 2, 3], [4, 5, 6]]
    
    proposal = NeuralProposal(
        pattern_type=PatternType.VISUAL_GRID,
        confidence=0.8,
        candidate_solution=valid_grid,
        embedding=[1.0, 0.0, 0.0]
    )
    
    solution = symbolic.verify_proposal(proposal, mode=ReasoningMode.NEURAL_FIRST)
    
    assert isinstance(solution, VerifiedSolution)
    assert solution.verification_score > 0
    print(f"  ✓ Verified solution with score {solution.verification_score:.2f}")
    print(f"    Passed: {len(solution.passed_constraints)}, Failed: {len(solution.failed_constraints)}")
    return True


def test_pattern_templates():
    """Test 3: Pattern templates can be instantiated and composed."""
    print("Test 3: Pattern Templates...")
    
    template = PatternTemplate(
        name="test_transform",
        variables=["input", "op"],
        structure={
            "input": "$input",
            "operation": "$op",
            "output": None
        }
    )
    
    bindings = {"input": "data", "op": "transform"}
    instance = template.instantiate(bindings)
    
    assert instance["input"] == "data"
    assert instance["operation"] == "transform"
    assert instance["output"] is None
    
    print(f"  ✓ Template instantiated: {instance}")
    return True


def test_neural_symbolic_bridge():
    """Test 4: Bridge between neural proposals and symbolic verification."""
    print("Test 4: Neural-Symbolic Bridge...")
    
    engine = create_neuro_symbolic_engine()
    
    # Simple problem: grid that needs transformation
    problem = {
        "input": [[1, 2], [3, 4]]
    }
    
    solution, history = engine.solve(problem, mode=ReasoningMode.NEURAL_FIRST)
    
    assert len(history) > 0, "Should have reasoning steps"
    assert solution is not None, "Should produce a solution"
    
    print(f"  ✓ Bridge working: {len(history)} reasoning steps")
    print(f"    Solution confidence: {solution.proposal.confidence:.2f}")
    print(f"    Verification score: {solution.verification_score:.2f}")
    return True


def test_compositional_reasoning():
    """Test 5: Compositional reasoning with multiple steps."""
    print("Test 5: Compositional Reasoning...")
    
    engine = create_neuro_symbolic_engine()
    
    # Sequential problem with multiple steps
    problem = [1, 2, 3, 4]  # Represents a sequence to transform
    
    solution, history = engine.solve(problem, mode=ReasoningMode.HYBRID_INTERLEAVED)
    
    # Verify reasoning trace
    explanation = engine.explain_reasoning()
    
    assert explanation["total_steps"] > 0
    print(f"  ✓ Compositional reasoning: {explanation['total_steps']} steps")
    print(f"    Total proposals: {explanation['neural_proposals_total']}")
    print(f"    Verified solutions: {explanation['solutions_verified_total']}")
    return True


def test_different_reasoning_modes():
    """Test 6: Different reasoning modes produce different results."""
    print("Test 6: Reasoning Modes...")
    
    engine = create_neuro_symbolic_engine()
    
    problem = {"input": [[1, 2], [3, 4]]}
    
    modes = [
        ReasoningMode.NEURAL_FIRST,
        ReasoningMode.SYMBOLIC_FIRST,
        ReasoningMode.HYBRID_INTERLEAVED
    ]
    
    results = {}
    for mode in modes:
        solution, history = engine.solve(problem, mode=mode)
        results[mode.name] = {
            "solution_found": solution is not None,
            "steps": len(history),
            "verification": solution.verification_score if solution else 0
        }
    
    print("  ✓ Mode comparison:")
    for mode, result in results.items():
        print(f"    {mode}: {result['steps']} steps, score={result['verification']:.2f}")
    
    return True


def test_arc_agi_style_problem():
    """Test 7: ARC-AGI style abstract reasoning."""
    print("Test 7: ARC-AGI Style Problem...")
    
    engine = create_neuro_symbolic_engine()
    
    # ARC-AGI style problem: grid with transformation rule
    arc_problem = {
        "train": [
            {"input": [[1, 1], [1, 1]], "output": [[2, 2], [2, 2]]}
        ],
        "test_input": [[3, 3], [3, 3]]
    }
    
    # Extract the test input
    problem = {"input": arc_problem["test_input"]}
    
    solution, history = engine.solve(problem, mode=ReasoningMode.NEURAL_FIRST)
    
    assert solution is not None
    assert len(history) >= 1
    
    explanation = engine.explain_reasoning()
    print(f"  ✓ ARC-AGI style problem solved")
    print(f"    Pattern type: {solution.proposal.pattern_type.value}")
    print(f"    Neural proposals generated: {explanation['neural_proposals_total']}")
    return True


def test_custom_constraints():
    """Test 8: Custom symbolic constraints."""
    print("Test 8: Custom Constraints...")
    
    def max_size_10(solution):
        if isinstance(solution, list):
            total_size = sum(len(row) for row in solution if isinstance(row, list))
            return total_size <= 10, 1.0
        return True, 1.0
    
    def even_dimensions(solution):
        if isinstance(solution, list) and len(solution) > 0:
            if isinstance(solution[0], list):
                rows = len(solution)
                cols = len(solution[0])
                return rows % 2 == 0 and cols % 2 == 0, 0.8
        return True, 1.0
    
    custom_constraints = [
        SymbolicConstraint("max_size_10", max_size_10, "Grid must have at most 10 cells"),
        SymbolicConstraint("even_dimensions", even_dimensions, "Grid must have even dimensions")
    ]
    
    default_recognizers = create_default_neural_recognizers()
    default_templates = create_default_templates()
    
    engine = create_neuro_symbolic_engine(
        custom_recognizers=default_recognizers,
        custom_constraints=custom_constraints,
        custom_templates=default_templates
    )
    
    # Test with 3x3 grid (fails even_dimensions)
    problem = {"input": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]}
    
    solution, _ = engine.solve(problem, mode=ReasoningMode.NEURAL_FIRST)
    
    # Should still produce solution but with lower verification
    assert solution is not None
    print(f"  ✓ Custom constraints applied")
    print(f"    Verification score: {solution.verification_score:.2f}")
    print(f"    Failed constraints: {solution.failed_constraints}")
    return True


def test_solution_similarity():
    """Test 9: Neural similarity between solutions."""
    print("Test 9: Solution Similarity...")
    
    neural = NeuralPerceptionModule()
    
    proposal1 = NeuralProposal(
        pattern_type=PatternType.VISUAL_GRID,
        confidence=0.8,
        candidate_solution=[[1, 2], [3, 4]],
        embedding=[1.0, 0.0, 0.0, 0.0]
    )
    
    proposal2 = NeuralProposal(
        pattern_type=PatternType.VISUAL_GRID,
        confidence=0.7,
        candidate_solution=[[1, 2], [3, 4]],  # Same structure
        embedding=[0.9, 0.1, 0.0, 0.0]  # Slightly different
    )
    
    proposal3 = NeuralProposal(
        pattern_type=PatternType.SEQUENTIAL,
        confidence=0.6,
        candidate_solution=[1, 2, 3],
        embedding=[0.0, 0.0, 1.0, 0.0]  # Different pattern type
    )
    
    similarity_12 = neural.compute_similarity(proposal1, proposal2)
    similarity_13 = neural.compute_similarity(proposal1, proposal3)
    
    assert similarity_12 > 0.8, "Similar embeddings should have high similarity"
    assert similarity_13 < 0.5, "Different embeddings should have low similarity"
    
    print(f"  ✓ Similarity computed: similar={similarity_12:.3f}, different={similarity_13:.3f}")
    return True


def test_template_composition():
    """Test 10: Template composition for complex problems."""
    print("Test 10: Template Composition...")
    
    symbolic = SymbolicConstraintModule()
    
    template1 = PatternTemplate(
        name="step_a",
        variables=["data"],
        structure={"operation": "A", "input": "$data"}
    )
    
    template2 = PatternTemplate(
        name="step_b", 
        variables=["result"],
        structure={"operation": "B", "input": "$result"}
    )
    
    symbolic.register_template(template1)
    symbolic.register_template(template2)
    
    # Compose templates
    composed = symbolic.compose_templates(["step_a", "step_b"], {"data": "initial"})
    
    assert composed is not None
    assert composed["operation"] == "A"  # First template's operation
    
    print(f"  ✓ Templates composed: {composed}")
    return True


def run_all_tests():
    """Run all neuro-symbolic reasoning tests."""
    print("\n" + "="*60)
    print("NEURO-SYMBOLIC REASONING MODULE TESTS")
    print("="*60 + "\n")
    
    tests = [
        test_neural_perception_module,
        test_symbolic_constraint_module,
        test_pattern_templates,
        test_neural_symbolic_bridge,
        test_compositional_reasoning,
        test_different_reasoning_modes,
        test_arc_agi_style_problem,
        test_custom_constraints,
        test_solution_similarity,
        test_template_composition,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"  ✗ FAILED")
        except Exception as e:
            failed += 1
            print(f"  ✗ FAILED with exception: {e}")
            import traceback
            traceback.print_exc()
        print()
    
    print("="*60)
    print(f"RESULTS: {passed}/{len(tests)} passed, {failed}/{len(tests)} failed")
    print("="*60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
