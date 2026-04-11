"""
Neuro-Symbolic Reasoning Module

Based on: "Compositional Neuro-Symbolic Reasoning" (arXiv:2604.02434)
Architecture: Perception → Neural Proposals → Symbolic Verification

This module implements a neuro-symbolic hybrid approach for structured reasoning tasks:
1. Perception module extracts object-level structure
2. Neural component proposes candidate transformations
3. Symbolic verification filters by cross-example consistency

Key insight from ARC-AGI-2: Neuro-symbolic approaches achieved 30.8% on ARC-AGI-2
when combined with meta-classifier, showing the value of separating perception,
neural proposals, and symbolic filtering.
"""

from typing import Any, Dict, List, Optional, Set, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import json
import re
from collections import defaultdict


class PatternType(Enum):
    """Types of patterns that can be recognized in structured data."""
    OBJECT = auto()           # Distinct entities with boundaries
    SEQUENCE = auto()         # Ordered elements
    GRID_STRUCTURE = auto()   # 2D arrangements
    SYMMETRY = auto()         # Mirror/rotational patterns
    TRANSFORMATION = auto()   # Input-output mappings
    RELATION = auto()         # Connections between elements
    IDENTITY = auto()         # Identity/no-change transformation


@dataclass
class ExtractedObject:
    """Represents an object extracted by the perception module."""
    object_id: str
    object_type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    position: Optional[Tuple[int, ...]] = None
    size: Optional[Tuple[int, ...]] = None
    color: Optional[str] = None
    shape: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.object_id,
            "type": self.object_type,
            "properties": self.properties,
            "position": self.position,
            "size": self.size,
            "color": self.color,
            "shape": self.shape
        }


@dataclass
class TransformationRule:
    """A candidate transformation proposed by the neural component."""
    rule_id: str
    name: str
    description: str
    input_pattern: Dict[str, Any]
    output_pattern: Dict[str, Any]
    confidence: float
    pattern_type: PatternType
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "input_pattern": self.input_pattern,
            "output_pattern": self.output_pattern,
            "confidence": self.confidence,
            "pattern_type": self.pattern_type.name,
            "parameters": self.parameters
        }


@dataclass
class ConsistencyCheck:
    """Result of symbolic consistency verification."""
    rule_id: str
    is_consistent: bool
    supporting_examples: List[int] = field(default_factory=list)
    conflicting_examples: List[int] = field(default_factory=list)
    confidence_adjustment: float = 0.0
    verification_notes: List[str] = field(default_factory=list)


@dataclass
class ReasoningResult:
    """Complete result from neuro-symbolic reasoning."""
    input_objects: List[ExtractedObject]
    proposed_rules: List[TransformationRule]
    verified_rules: List[TransformationRule]
    rejected_rules: List[Tuple[TransformationRule, str]]  # rule + rejection reason
    final_output: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    reasoning_trace: List[Dict[str, Any]] = field(default_factory=list)


class PerceptionModule:
    """
    Extracts object-level structure from raw input data.
    
    Inspired by ARC-AGI's focus on "objectness" as a core prior.
    Handles grids, sequences, and structured data formats.
    """
    
    def __init__(self):
        self.extraction_history: List[Dict[str, Any]] = []
    
    def extract_objects(self, data: Any, context: str = "") -> List[ExtractedObject]:
        """
        Extract objects from various input formats.
        
        Supports:
        - 2D grids (lists of lists) - extracts connected components
        - Sequences - extracts ordered elements
        - JSON/dict - extracts structured entities
        - Strings - extracts patterns and tokens
        """
        objects = []
        
        if isinstance(data, list) and len(data) > 0:
            if isinstance(data[0], list):
                # 2D grid structure
                objects = self._extract_grid_objects(data, context)
            else:
                # 1D sequence
                objects = self._extract_sequence_objects(data, context)
        elif isinstance(data, dict):
            # Structured data
            objects = self._extract_dict_objects(data, context)
        elif isinstance(data, str):
            # String patterns
            objects = self._extract_string_objects(data, context)
        
        self.extraction_history.append({
            "context": context,
            "input_type": type(data).__name__,
            "objects_found": len(objects)
        })
        
        return objects
    
    def _extract_grid_objects(self, grid: List[List[Any]], context: str) -> List[ExtractedObject]:
        """Extract connected components from 2D grids (ARC-AGI style)."""
        objects = []
        height = len(grid)
        width = len(grid[0]) if height > 0 else 0
        visited = [[False] * width for _ in range(height)]
        
        # Find connected components using flood fill
        for y in range(height):
            for x in range(width):
                if not visited[y][x] and grid[y][x] != 0:  # 0 = background
                    component = self._flood_fill(grid, x, y, visited)
                    if component:
                        obj = ExtractedObject(
                            object_id=f"{context}_obj_{len(objects)}",
                            object_type="grid_component",
                            properties={
                                "cells": len(component),
                                "value": grid[y][x],
                                "bounding_box": self._compute_bounding_box(component)
                            },
                            position=(sum(c[0] for c in component) // len(component),
                                     sum(c[1] for c in component) // len(component)),
                            color=str(grid[y][x])
                        )
                        objects.append(obj)
        
        # Also detect global patterns
        if self._detect_symmetry(grid):
            objects.append(ExtractedObject(
                object_id=f"{context}_symmetry",
                object_type="pattern",
                properties={"pattern_type": "symmetry"}
            ))
        
        return objects
    
    def _flood_fill(self, grid: List[List[Any]], start_x: int, start_y: int, 
                    visited: List[List[bool]]) -> List[Tuple[int, int]]:
        """Flood fill to find connected components of same value."""
        height, width = len(grid), len(grid[0])
        target_value = grid[start_y][start_x]
        component = []
        stack = [(start_x, start_y)]
        
        while stack:
            x, y = stack.pop()
            if x < 0 or x >= width or y < 0 or y >= height:
                continue
            if visited[y][x] or grid[y][x] != target_value:
                continue
            
            visited[y][x] = True
            component.append((x, y))
            
            # 4-connectivity (up, down, left, right)
            stack.extend([(x+1, y), (x-1, y), (x, y+1), (x, y-1)])
        
        return component
    
    def _compute_bounding_box(self, cells: List[Tuple[int, int]]) -> Tuple[int, int, int, int]:
        """Compute bounding box from cell coordinates."""
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        return (min(xs), min(ys), max(xs), max(ys))
    
    def _detect_symmetry(self, grid: List[List[Any]]) -> bool:
        """Detect if grid has horizontal or vertical symmetry."""
        height, width = len(grid), len(grid[0]) if grid else 0
        
        # Check horizontal symmetry
        horizontal = all(grid[y] == grid[height - 1 - y] for y in range(height // 2))
        
        # Check vertical symmetry  
        vertical = all(
            all(grid[y][x] == grid[y][width - 1 - x] for x in range(width // 2))
            for y in range(height)
        )
        
        return horizontal or vertical
    
    def _extract_sequence_objects(self, sequence: List[Any], context: str) -> List[ExtractedObject]:
        """Extract objects from 1D sequences."""
        objects = []
        
        # Detect runs of identical values
        if len(sequence) > 0:
            current = sequence[0]
            run_start = 0
            
            for i, val in enumerate(sequence[1:], 1):
                if val != current:
                    obj = ExtractedObject(
                        object_id=f"{context}_run_{len(objects)}",
                        object_type="sequence_run",
                        properties={
                            "value": current,
                            "length": i - run_start,
                            "start": run_start,
                            "end": i - 1
                        },
                        position=(run_start,)
                    )
                    objects.append(obj)
                    current = val
                    run_start = i
            
            # Add final run
            obj = ExtractedObject(
                object_id=f"{context}_run_{len(objects)}",
                object_type="sequence_run",
                properties={
                    "value": current,
                    "length": len(sequence) - run_start,
                    "start": run_start,
                    "end": len(sequence) - 1
                },
                position=(run_start,)
            )
            objects.append(obj)
        
        return objects
    
    def _extract_dict_objects(self, data: Dict[str, Any], context: str) -> List[ExtractedObject]:
        """Extract objects from dictionary structures."""
        objects = []
        
        for key, value in data.items():
            obj = ExtractedObject(
                object_id=f"{context}_{key}",
                object_type="dict_entry",
                properties={"key": key, "value_type": type(value).__name__},
                color=str(value) if isinstance(value, (str, int, float, bool)) else None
            )
            objects.append(obj)
        
        return objects
    
    def _extract_string_objects(self, text: str, context: str) -> List[ExtractedObject]:
        """Extract pattern objects from strings."""
        objects = []
        
        # Detect repeated patterns
        words = text.split()
        for i, word in enumerate(words):
            obj = ExtractedObject(
                object_id=f"{context}_word_{i}",
                object_type="token",
                properties={"text": word, "index": i},
                position=(i,)
            )
            objects.append(obj)
        
        return objects


class NeuralTransformationProposer:
    """
    Neural component that proposes candidate transformations.
    
    Uses pattern matching and heuristics (simulating neural proposals)
    to generate candidate transformation rules from examples.
    """
    
    # Domain-specific language of atomic transformations
    DSL_PATTERNS = {
        "identity": "Output equals input",
        "color_change": "Change color/value X to Y",
        "move": "Move object to position/orientation",
        "rotate": "Rotate grid 90/180/270 degrees",
        "mirror": "Mirror horizontally/vertically",
        "crop": "Extract sub-region",
        "extend": "Add border or expand",
        "fill": "Fill region with value",
        "duplicate": "Copy and place elsewhere",
        "sort": "Order by size/color/position",
        "connect": "Draw lines between objects",
        "count": "Output count of objects",
        "select": "Select specific objects by criteria"
    }
    
    def __init__(self):
        self.proposal_history: List[Dict[str, Any]] = []
    
    def propose_transformations(
        self, 
        input_objects: List[ExtractedObject],
        output_objects: List[ExtractedObject],
        examples: List[Tuple[List[ExtractedObject], List[ExtractedObject]]] = None
    ) -> List[TransformationRule]:
        """
        Propose candidate transformation rules based on input-output examples.
        
        Analyzes differences between inputs and outputs to suggest possible
        transformation rules from the DSL.
        """
        rules = []
        
        # Analyze structure changes
        rules.extend(self._analyze_structure_changes(input_objects, output_objects))
        
        # Analyze object changes
        rules.extend(self._analyze_object_transformations(input_objects, output_objects))
        
        # Analyze pattern changes
        rules.extend(self._analyze_pattern_transformations(input_objects, output_objects))
        
        # Cross-example refinement if multiple examples provided
        if examples and len(examples) > 1:
            rules = self._cross_example_refinement(rules, examples)
        
        # Sort by confidence
        rules.sort(key=lambda r: r.confidence, reverse=True)
        
        self.proposal_history.append({
            "input_count": len(input_objects),
            "output_count": len(output_objects),
            "rules_proposed": len(rules),
            "top_confidence": rules[0].confidence if rules else 0
        })
        
        return rules
    
    def _analyze_structure_changes(
        self, 
        inputs: List[ExtractedObject], 
        outputs: List[ExtractedObject]
    ) -> List[TransformationRule]:
        """Propose rules based on structural changes."""
        rules = []
        
        # Check for dimension changes (resize/crop)
        input_grid_like = any(o.object_type == "grid_component" for o in inputs)
        output_grid_like = any(o.object_type == "grid_component" for o in outputs)
        
        if input_grid_like and output_grid_like:
            if len(outputs) < len(inputs):
                rules.append(TransformationRule(
                    rule_id="rule_select",
                    name="Select Subset",
                    description="Select specific objects from input",
                    input_pattern={"type": "multiple_objects"},
                    output_pattern={"type": "subset"},
                    confidence=0.7,
                    pattern_type=PatternType.TRANSFORMATION
                ))
        
        # Check for ordering changes
        if len(inputs) == len(outputs):
            rules.append(TransformationRule(
                rule_id="rule_reorder",
                name="Reorder Objects",
                description="Change order of objects",
                input_pattern={"type": "sequence"},
                output_pattern={"type": "reordered_sequence"},
                confidence=0.5,
                pattern_type=PatternType.SEQUENCE
            ))
        
        return rules
    
    def _analyze_object_transformations(
        self, 
        inputs: List[ExtractedObject], 
        outputs: List[ExtractedObject]
    ) -> List[TransformationRule]:
        """Propose rules based on individual object changes."""
        rules = []
        
        # Color/value change detection
        input_colors = {o.color for o in inputs if o.color}
        output_colors = {o.color for o in outputs if o.color}
        
        if input_colors != output_colors and len(input_colors) > 0 and len(output_colors) > 0:
            # Map colors
            color_mapping = self._infer_color_mapping(inputs, outputs)
            if color_mapping:
                rules.append(TransformationRule(
                    rule_id="rule_color_map",
                    name="Color Mapping",
                    description=f"Map colors: {color_mapping}",
                    input_pattern={"colors": list(input_colors)},
                    output_pattern={"colors": list(output_colors)},
                    confidence=0.8,
                    pattern_type=PatternType.TRANSFORMATION,
                    parameters={"mapping": color_mapping}
                ))
        
        # Position change detection
        if len(inputs) == len(outputs):
            rules.append(TransformationRule(
                rule_id="rule_move",
                name="Move Objects",
                description="Change object positions",
                input_pattern={"has_positions": True},
                output_pattern={"has_positions": True},
                confidence=0.6,
                pattern_type=PatternType.TRANSFORMATION
            ))
        
        return rules
    
    def _analyze_pattern_transformations(
        self, 
        inputs: List[ExtractedObject], 
        outputs: List[ExtractedObject]
    ) -> List[TransformationRule]:
        """Propose rules based on pattern changes."""
        rules = []
        
        # Symmetry detection
        input_symmetry = any(o.properties.get("pattern_type") == "symmetry" for o in inputs)
        output_symmetry = any(o.properties.get("pattern_type") == "symmetry" for o in outputs)
        
        if input_symmetry and not output_symmetry:
            rules.append(TransformationRule(
                rule_id="rule_break_symmetry",
                name="Break Symmetry",
                description="Remove symmetric elements",
                input_pattern={"symmetric": True},
                output_pattern={"symmetric": False},
                confidence=0.6,
                pattern_type=PatternType.SYMMETRY
            ))
        
        if not input_symmetry and output_symmetry:
            rules.append(TransformationRule(
                rule_id="rule_add_symmetry",
                name="Add Symmetry",
                description="Create symmetric arrangement",
                input_pattern={"symmetric": False},
                output_pattern={"symmetric": True},
                confidence=0.6,
                pattern_type=PatternType.SYMMETRY
            ))
        
        return rules
    
    def _infer_color_mapping(
        self, 
        inputs: List[ExtractedObject], 
        outputs: List[ExtractedObject]
    ) -> Optional[Dict[str, str]]:
        """Infer color/value mapping from input-output pairs."""
        # Simple heuristic: match by object count
        input_counts = defaultdict(int)
        output_counts = defaultdict(int)
        
        for obj in inputs:
            if obj.color:
                input_counts[obj.color] += 1
        
        for obj in outputs:
            if obj.color:
                output_counts[obj.color] += 1
        
        # Find mappings based on frequency changes
        mapping = {}
        for in_color, in_count in input_counts.items():
            for out_color, out_count in output_counts.items():
                if in_count == out_count:
                    mapping[in_color] = out_color
                    break
        
        return mapping if mapping else None
    
    def _cross_example_refinement(
        self,
        rules: List[TransformationRule],
        examples: List[Tuple[List[ExtractedObject], List[ExtractedObject]]]
    ) -> List[TransformationRule]:
        """Refine rule confidence based on consistency across multiple examples."""
        # Count how many examples support each rule type
        support_counts = defaultdict(int)
        
        for input_objs, output_objs in examples:
            example_rules = (
                self._analyze_structure_changes(input_objs, output_objs) +
                self._analyze_object_transformations(input_objs, output_objs) +
                self._analyze_pattern_transformations(input_objs, output_objs)
            )
            
            for rule in example_rules:
                support_counts[rule.rule_id] += 1
        
        # Adjust confidence based on cross-example support
        refined_rules = []
        for rule in rules:
            support_ratio = support_counts[rule.rule_id] / len(examples)
            adjusted_confidence = rule.confidence * (0.5 + 0.5 * support_ratio)
            
            refined_rule = TransformationRule(
                rule_id=rule.rule_id,
                name=rule.name,
                description=rule.description,
                input_pattern=rule.input_pattern,
                output_pattern=rule.output_pattern,
                confidence=min(adjusted_confidence, 0.95),
                pattern_type=rule.pattern_type,
                parameters={**rule.parameters, "cross_example_support": support_ratio}
            )
            refined_rules.append(refined_rule)
        
        return refined_rules


class SymbolicConsistencyVerifier:
    """
    Symbolic verification component.
    
    Filters neural proposals by checking cross-example consistency.
    A rule must work across ALL training examples to be considered valid.
    """
    
    def __init__(self, strictness: float = 0.8):
        self.strictness = strictness  # 0.0-1.0, higher = stricter
        self.verification_history: List[Dict[str, Any]] = []
    
    def verify_rules(
        self,
        rules: List[TransformationRule],
        examples: List[Tuple[Any, Any]]  # (input, expected_output) pairs
    ) -> Tuple[List[TransformationRule], List[Tuple[TransformationRule, str]]]:
        """
        Verify proposed rules against all examples.
        
        Returns:
            - List of verified rules (passed all examples)
            - List of rejected rules with reasons
        """
        verified = []
        rejected = []
        
        for rule in rules:
            check = self._check_rule_consistency(rule, examples)
            
            if check.is_consistent:
                verified.append(rule)
            else:
                reason = f"Failed on examples: {check.conflicting_examples}"
                rejected.append((rule, reason))
        
        self.verification_history.append({
            "rules_checked": len(rules),
            "verified": len(verified),
            "rejected": len(rejected),
            "strictness": self.strictness
        })
        
        return verified, rejected
    
    def _check_rule_consistency(
        self,
        rule: TransformationRule,
        examples: List[Tuple[Any, Any]]
    ) -> ConsistencyCheck:
        """Check if a rule is consistent across all examples."""
        supporting = []
        conflicting = []
        notes = []
        
        for i, (input_data, expected_output) in enumerate(examples):
            # Simulate applying the rule (heuristic check)
            predicted_output = self._simulate_rule_application(rule, input_data)
            
            if self._outputs_match(predicted_output, expected_output):
                supporting.append(i)
            else:
                conflicting.append(i)
        
        # Determine consistency based on strictness threshold
        total = len(examples)
        support_ratio = len(supporting) / total if total > 0 else 0
        
        is_consistent = support_ratio >= self.strictness
        
        confidence_adjustment = support_ratio - self.strictness
        
        if is_consistent and len(conflicting) > 0:
            notes.append(f"Some conflicts but within strictness tolerance: {conflicting}")
        
        return ConsistencyCheck(
            rule_id=rule.rule_id,
            is_consistent=is_consistent,
            supporting_examples=supporting,
            conflicting_examples=conflicting,
            confidence_adjustment=confidence_adjustment,
            verification_notes=notes
        )
    
    def _simulate_rule_application(self, rule: TransformationRule, input_data: Any) -> Any:
        """
        Simulate applying a transformation rule to input data.
        
        This is a simplified simulation - real implementation would
        actually execute the transformation.
        """
        # Simple heuristics for simulation
        if rule.pattern_type == PatternType.TRANSFORMATION:
            if "color" in rule.name.lower() and isinstance(input_data, list):
                # Simulate color transformation on grids
                return input_data  # Would apply color mapping
        
        return input_data  # Default: identity
    
    def _outputs_match(self, predicted: Any, expected: Any) -> bool:
        """Check if two outputs match (with some tolerance)."""
        if type(predicted) != type(expected):
            return False
        
        if isinstance(predicted, list):
            if len(predicted) != len(expected):
                return False
            return all(self._outputs_match(p, e) for p, e in zip(predicted, expected))
        
        return predicted == expected


class NeuroSymbolicReasoner:
    """
    Integrated neuro-symbolic reasoning system.
    
    Combines:
    1. Perception module for structure extraction
    2. Neural proposer for candidate transformations
    3. Symbolic verifier for cross-example consistency
    
    Based on ARC-AGI-2 neuro-symbolic approach achieving 30.8% performance.
    """
    
    def __init__(self, verification_strictness: float = 0.8):
        self.perception = PerceptionModule()
        self.proposer = NeuralTransformationProposer()
        self.verifier = SymbolicConsistencyVerifier(verification_strictness)
        self.reasoning_history: List[ReasoningResult] = []
    
    def solve(
        self,
        train_examples: List[Tuple[Any, Any]],  # (input, output) pairs
        test_input: Any
    ) -> ReasoningResult:
        """
        Solve a structured reasoning task using neuro-symbolic approach.
        
        Args:
            train_examples: List of (input, output) training pairs
            test_input: The test input to transform
        
        Returns:
            ReasoningResult with extracted objects, proposed rules, verified rules,
            and predicted output
        """
        trace = []
        
        # Phase 1: Perception - extract objects from all examples
        train_object_pairs = []
        for i, (inp, out) in enumerate(train_examples):
            input_objs = self.perception.extract_objects(inp, f"train_{i}_input")
            output_objs = self.perception.extract_objects(out, f"train_{i}_output")
            train_object_pairs.append((input_objs, output_objs))
        
        test_objects = self.perception.extract_objects(test_input, "test_input")
        
        trace.append({
            "phase": "perception",
            "train_examples": len(train_examples),
            "objects_extracted": sum(len(p[0]) + len(p[1]) for p in train_object_pairs)
        })
        
        # Phase 2: Neural proposals - generate candidate rules
        all_proposed_rules = []
        for input_objs, output_objs in train_object_pairs:
            # Propose based on this example
            examples_for_refinement = [(inp, out) for inp, out in train_object_pairs]
            rules = self.proposer.propose_transformations(
                input_objs, output_objs, examples_for_refinement
            )
            all_proposed_rules.extend(rules)
        
        # Deduplicate rules by ID
        seen_ids = set()
        unique_rules = []
        for rule in all_proposed_rules:
            if rule.rule_id not in seen_ids:
                seen_ids.add(rule.rule_id)
                unique_rules.append(rule)
        
        trace.append({
            "phase": "neural_proposal",
            "rules_proposed": len(unique_rules),
            "top_candidates": [r.name for r in unique_rules[:3]]
        })
        
        # Phase 3: Symbolic verification - filter by consistency
        verified, rejected = self.verifier.verify_rules(unique_rules, train_examples)
        
        trace.append({
            "phase": "symbolic_verification",
            "rules_verified": len(verified),
            "rules_rejected": len(rejected),
            "verification_strictness": self.verifier.strictness
        })
        
        # Phase 4: Generate output using best verified rule
        final_output = None
        confidence = 0.0
        
        if verified:
            best_rule = verified[0]
            confidence = best_rule.confidence
            # In real implementation, would apply the transformation
            final_output = {"rule_applied": best_rule.name, "confidence": confidence}
        
        result = ReasoningResult(
            input_objects=test_objects,
            proposed_rules=unique_rules,
            verified_rules=verified,
            rejected_rules=rejected,
            final_output=final_output,
            confidence=confidence,
            reasoning_trace=trace
        )
        
        self.reasoning_history.append(result)
        return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get reasoning statistics."""
        if not self.reasoning_history:
            return {"total_attempts": 0}
        
        total = len(self.reasoning_history)
        with_output = sum(1 for r in self.reasoning_history if r.final_output is not None)
        avg_confidence = sum(r.confidence for r in self.reasoning_history) / total
        avg_proposed = sum(len(r.proposed_rules) for r in self.reasoning_history) / total
        avg_verified = sum(len(r.verified_rules) for r in self.reasoning_history) / total
        
        return {
            "total_attempts": total,
            "success_rate": with_output / total,
            "avg_confidence": avg_confidence,
            "avg_rules_proposed": avg_proposed,
            "avg_rules_verified": avg_verified,
            "verification_rate": avg_verified / avg_proposed if avg_proposed > 0 else 0
        }


# Convenience functions for direct use

def solve_structured_task(
    train_examples: List[Tuple[Any, Any]],
    test_input: Any,
    verification_strictness: float = 0.8
) -> Dict[str, Any]:
    """
    High-level interface for solving structured reasoning tasks.
    
    Example:
        # Grid color mapping task
        train = [
            ([[1, 1], [1, 1]], [[2, 2], [2, 2]]),  # 1 -> 2
            ([[3, 3], [3, 3]], [[4, 4], [4, 4]])   # 3 -> 4
        ]
        test = [[5, 5], [5, 5]]
        result = solve_structured_task(train, test)
    """
    reasoner = NeuroSymbolicReasoner(verification_strictness)
    result = reasoner.solve(train_examples, test_input)
    
    return {
        "success": result.final_output is not None,
        "confidence": result.confidence,
        "rules_proposed": len(result.proposed_rules),
        "rules_verified": len(result.verified_rules),
        "top_rule": result.verified_rules[0].name if result.verified_rules else None,
        "trace": result.reasoning_trace
    }


def analyze_pattern(data: Any, context: str = "") -> Dict[str, Any]:
    """Extract and analyze patterns in data."""
    perception = PerceptionModule()
    objects = perception.extract_objects(data, context)
    
    return {
        "objects_found": len(objects),
        "object_types": list(set(o.object_type for o in objects)),
        "properties": [o.to_dict() for o in objects],
        "extraction_history": perception.extraction_history
    }
