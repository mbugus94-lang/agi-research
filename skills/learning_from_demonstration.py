"""
Learning from Demonstration (LfD) Module

Enables the agent to learn new skills from examples rather than explicit programming.
Based on neuroscience-inspired continuous learning research and AGI skill acquisition principles.

Key capabilities:
- Record demonstrations of successful task executions
- Extract reusable patterns from multiple demonstrations
- Synthesize executable skill definitions
- Version-controlled skill library
- Transfer learning to new contexts

Inspired by:
- Human skill acquisition through imitation and practice
- Neuroscience-inspired continual learning (arXiv:2504.20109v1)
- Program synthesis from examples (arXiv:2605.05138v1)
"""

import json
import uuid
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Tuple, Set
from enum import Enum, auto
from pathlib import Path
import copy


class DemonstrationType(Enum):
    """Types of demonstrations that can be recorded."""
    TASK_EXECUTION = "task_execution"
    TOOL_USAGE = "tool_usage"
    DECISION_SEQUENCE = "decision_sequence"
    REPAIR_SEQUENCE = "repair_sequence"  # Learning from mistakes


class SkillType(Enum):
    """Types of skills that can be learned."""
    SEQUENTIAL = "sequential"  # Step-by-step procedures
    CONDITIONAL = "conditional"  # If-then rules
    ITERATIVE = "iterative"  # Loops and repetitions
    COMPOSITE = "composite"  # Combination of other skills


class PatternType(Enum):
    """Types of patterns that can be extracted."""
    ACTION_SEQUENCE = "action_sequence"
    PARAMETER_MAPPING = "parameter_mapping"
    STATE_TRANSITION = "state_transition"
    ERROR_RECOVERY = "error_recovery"


@dataclass
class ActionStep:
    """A single action in a demonstration."""
    step_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    action_type: str = ""  # tool_call, reasoning, decision, etc.
    tool_name: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    pre_state: Dict[str, Any] = field(default_factory=dict)
    post_state: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_ms: float = 0.0
    success: bool = True
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "action_type": self.action_type,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "pre_state": self.pre_state,
            "post_state": self.post_state,
            "timestamp": self.timestamp,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "notes": self.notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ActionStep':
        return cls(
            step_id=data.get("step_id", str(uuid.uuid4())[:8]),
            action_type=data.get("action_type", ""),
            tool_name=data.get("tool_name"),
            parameters=data.get("parameters", {}),
            pre_state=data.get("pre_state", {}),
            post_state=data.get("post_state", {}),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            duration_ms=data.get("duration_ms", 0.0),
            success=data.get("success", True),
            notes=data.get("notes", "")
        )


@dataclass
class Demonstration:
    """A complete demonstration of a task or skill."""
    demo_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    demo_type: DemonstrationType = DemonstrationType.TASK_EXECUTION
    task_description: str = ""
    goal: str = ""
    steps: List[ActionStep] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    outcome: str = ""
    success: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: List[str] = field(default_factory=list)
    source: str = "manual"  # manual, agent_execution, human_demo
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "demo_id": self.demo_id,
            "demo_type": self.demo_type.value,
            "task_description": self.task_description,
            "goal": self.goal,
            "steps": [s.to_dict() for s in self.steps],
            "context": self.context,
            "outcome": self.outcome,
            "success": self.success,
            "created_at": self.created_at,
            "tags": self.tags,
            "source": self.source
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Demonstration':
        return cls(
            demo_id=data.get("demo_id", str(uuid.uuid4())),
            demo_type=DemonstrationType(data.get("demo_type", "task_execution")),
            task_description=data.get("task_description", ""),
            goal=data.get("goal", ""),
            steps=[ActionStep.from_dict(s) for s in data.get("steps", [])],
            context=data.get("context", {}),
            outcome=data.get("outcome", ""),
            success=data.get("success", True),
            created_at=data.get("created_at", datetime.now().isoformat()),
            tags=data.get("tags", []),
            source=data.get("source", "manual")
        )
    
    def add_step(self, step: ActionStep) -> None:
        """Add a step to the demonstration."""
        self.steps.append(step)
    
    def get_duration_ms(self) -> float:
        """Calculate total duration of the demonstration."""
        return sum(s.duration_ms for s in self.steps)
    
    def get_tools_used(self) -> Set[str]:
        """Get set of tools used in this demonstration."""
        return {s.tool_name for s in self.steps if s.tool_name}


@dataclass
class ExtractedPattern:
    """A pattern extracted from one or more demonstrations."""
    pattern_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    pattern_type: PatternType = PatternType.ACTION_SEQUENCE
    name: str = ""
    description: str = ""
    action_sequence: List[Dict[str, Any]] = field(default_factory=list)
    parameter_schema: Dict[str, Any] = field(default_factory=dict)
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    source_demos: List[str] = field(default_factory=list)
    confidence: float = 0.0
    frequency: int = 0  # How many times this pattern was observed
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type.value,
            "name": self.name,
            "description": self.description,
            "action_sequence": self.action_sequence,
            "parameter_schema": self.parameter_schema,
            "preconditions": self.preconditions,
            "postconditions": self.postconditions,
            "source_demos": self.source_demos,
            "confidence": self.confidence,
            "frequency": self.frequency,
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExtractedPattern':
        return cls(
            pattern_id=data.get("pattern_id", str(uuid.uuid4())[:12]),
            pattern_type=PatternType(data.get("pattern_type", "action_sequence")),
            name=data.get("name", ""),
            description=data.get("description", ""),
            action_sequence=data.get("action_sequence", []),
            parameter_schema=data.get("parameter_schema", {}),
            preconditions=data.get("preconditions", []),
            postconditions=data.get("postconditions", []),
            source_demos=data.get("source_demos", []),
            confidence=data.get("confidence", 0.0),
            frequency=data.get("frequency", 0),
            created_at=data.get("created_at", datetime.now().isoformat())
        )


@dataclass
class LearnedSkill:
    """A skill learned from demonstrations and patterns."""
    skill_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    skill_type: SkillType = SkillType.SEQUENTIAL
    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    patterns: List[ExtractedPattern] = field(default_factory=list)
    parameter_schema: Dict[str, Any] = field(default_factory=dict)
    required_tools: List[str] = field(default_factory=list)
    estimated_success_rate: float = 0.0
    usage_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    parent_skill: Optional[str] = None  # For version tracking
    demonstrations_used: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "skill_type": self.skill_type.value,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "patterns": [p.to_dict() for p in self.patterns],
            "parameter_schema": self.parameter_schema,
            "required_tools": self.required_tools,
            "estimated_success_rate": self.estimated_success_rate,
            "usage_count": self.usage_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "parent_skill": self.parent_skill,
            "demonstrations_used": self.demonstrations_used
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LearnedSkill':
        return cls(
            skill_id=data.get("skill_id", str(uuid.uuid4())[:12]),
            skill_type=SkillType(data.get("skill_type", "sequential")),
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            patterns=[ExtractedPattern.from_dict(p) for p in data.get("patterns", [])],
            parameter_schema=data.get("parameter_schema", {}),
            required_tools=data.get("required_tools", []),
            estimated_success_rate=data.get("estimated_success_rate", 0.0),
            usage_count=data.get("usage_count", 0),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            parent_skill=data.get("parent_skill"),
            demonstrations_used=data.get("demonstrations_used", [])
        )
    
    def bump_version(self, bump_type: str = "patch") -> None:
        """Bump the skill version."""
        parts = self.version.split(".")
        major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
        
        if bump_type == "major":
            major += 1
            minor = 0
            patch = 0
        elif bump_type == "minor":
            minor += 1
            patch = 0
        else:
            patch += 1
        
        self.version = f"{major}.{minor}.{patch}"
        self.updated_at = datetime.now().isoformat()


class DemonstrationRecorder:
    """Records and manages demonstrations."""
    
    def __init__(self, storage_path: Optional[str] = None):
        self.demonstrations: Dict[str, Demonstration] = {}
        self.active_recordings: Dict[str, Demonstration] = {}
        self.storage_path = Path(storage_path) if storage_path else None
        
        if self.storage_path:
            self._load_demonstrations()
    
    def start_recording(self, task_description: str, goal: str = "",
                       demo_type: DemonstrationType = DemonstrationType.TASK_EXECUTION,
                       context: Optional[Dict[str, Any]] = None,
                       tags: Optional[List[str]] = None) -> str:
        """Start recording a new demonstration."""
        demo = Demonstration(
            task_description=task_description,
            goal=goal,
            demo_type=demo_type,
            context=context or {},
            tags=tags or []
        )
        self.active_recordings[demo.demo_id] = demo
        return demo.demo_id
    
    def record_step(self, demo_id: str, action_type: str,
                   parameters: Dict[str, Any],
                   tool_name: Optional[str] = None,
                   pre_state: Optional[Dict[str, Any]] = None,
                   post_state: Optional[Dict[str, Any]] = None,
                   duration_ms: float = 0.0,
                   success: bool = True,
                   notes: str = "") -> None:
        """Record a single step in an active demonstration."""
        if demo_id not in self.active_recordings:
            raise ValueError(f"No active recording with ID {demo_id}")
        
        step = ActionStep(
            action_type=action_type,
            tool_name=tool_name,
            parameters=parameters,
            pre_state=pre_state or {},
            post_state=post_state or {},
            duration_ms=duration_ms,
            success=success,
            notes=notes
        )
        self.active_recordings[demo_id].add_step(step)
    
    def stop_recording(self, demo_id: str, outcome: str = "",
                      success: bool = True) -> Demonstration:
        """Stop recording and save the demonstration."""
        if demo_id not in self.active_recordings:
            raise ValueError(f"No active recording with ID {demo_id}")
        
        demo = self.active_recordings.pop(demo_id)
        demo.outcome = outcome
        demo.success = success
        self.demonstrations[demo_id] = demo
        
        if self.storage_path:
            self._save_demonstrations()
        
        return demo
    
    def get_demonstration(self, demo_id: str) -> Optional[Demonstration]:
        """Retrieve a demonstration by ID."""
        return self.demonstrations.get(demo_id)
    
    def find_demonstrations(self, task_pattern: Optional[str] = None,
                           tags: Optional[List[str]] = None,
                           successful_only: bool = True) -> List[Demonstration]:
        """Find demonstrations matching criteria."""
        results = []
        for demo in self.demonstrations.values():
            if successful_only and not demo.success:
                continue
            if task_pattern and task_pattern.lower() not in demo.task_description.lower():
                continue
            if tags and not any(t in demo.tags for t in tags):
                continue
            results.append(demo)
        return results
    
    def _save_demonstrations(self) -> None:
        """Save demonstrations to disk."""
        if not self.storage_path:
            return
        self.storage_path.mkdir(parents=True, exist_ok=True)
        data = {k: v.to_dict() for k, v in self.demonstrations.items()}
        with open(self.storage_path / "demonstrations.json", "w") as f:
            json.dump(data, f, indent=2)
    
    def _load_demonstrations(self) -> None:
        """Load demonstrations from disk."""
        if not self.storage_path:
            return
        file_path = self.storage_path / "demonstrations.json"
        if file_path.exists():
            with open(file_path, "r") as f:
                data = json.load(f)
                self.demonstrations = {k: Demonstration.from_dict(v) for k, v in data.items()}


class PatternExtractor:
    """Extracts reusable patterns from demonstrations."""
    
    def __init__(self):
        self.patterns: Dict[str, ExtractedPattern] = {}
    
    def extract_action_sequence(self, demonstrations: List[Demonstration],
                                min_frequency: int = 2) -> List[ExtractedPattern]:
        """Extract common action sequences from demonstrations."""
        # Find common subsequences
        sequences = []
        for demo in demonstrations:
            seq = [(s.action_type, s.tool_name) for s in demo.steps]
            sequences.append(seq)
        
        # Find common patterns (simplified - looks for exact matches)
        pattern_counts: Dict[Tuple, int] = {}
        pattern_sources: Dict[Tuple, List[str]] = {}
        
        for i, seq in enumerate(sequences):
            for length in range(2, min(len(seq) + 1, 6)):  # 2-5 step patterns
                for start in range(len(seq) - length + 1):
                    subseq = tuple(seq[start:start + length])
                    pattern_counts[subseq] = pattern_counts.get(subseq, 0) + 1
                    if subseq not in pattern_sources:
                        pattern_sources[subseq] = []
                    pattern_sources[subseq].append(demonstrations[i].demo_id)
        
        # Create patterns for frequent sequences
        extracted = []
        for subseq, count in pattern_counts.items():
            if count >= min_frequency:
                pattern = ExtractedPattern(
                    pattern_type=PatternType.ACTION_SEQUENCE,
                    name=f"pattern_{subseq[0][0]}_sequence",
                    description=f"Common {len(subseq)}-step sequence",
                    action_sequence=[{"action_type": a, "tool_name": t} for a, t in subseq],
                    source_demos=pattern_sources[subseq],
                    frequency=count,
                    confidence=min(1.0, count / len(demonstrations))
                )
                self.patterns[pattern.pattern_id] = pattern
                extracted.append(pattern)
        
        return extracted
    
    def extract_parameter_mappings(self, demonstrations: List[Demonstration]) -> List[ExtractedPattern]:
        """Extract parameter value patterns across demonstrations."""
        patterns = []
        
        # Group steps by action type and tool
        step_groups: Dict[Tuple, List[ActionStep]] = {}
        for demo in demonstrations:
            for step in demo.steps:
                key = (step.action_type, step.tool_name)
                if key not in step_groups:
                    step_groups[key] = []
                step_groups[key].append(step)
        
        for (action_type, tool_name), steps in step_groups.items():
            if len(steps) < 2:
                continue
            
            # Find common parameter keys
            all_params = [set(s.parameters.keys()) for s in steps]
            common_params = set.intersection(*all_params) if all_params else set()
            
            # Find parameters that vary
            varying_params = {}
            for param in common_params:
                values = [s.parameters[param] for s in steps]
                if len(set(str(v) for v in values)) > 1:
                    varying_params[param] = values
            
            if varying_params:
                pattern = ExtractedPattern(
                    pattern_type=PatternType.PARAMETER_MAPPING,
                    name=f"param_mapping_{action_type}_{tool_name or 'none'}",
                    description=f"Parameter patterns for {action_type}",
                    parameter_schema={
                        "action_type": action_type,
                        "tool_name": tool_name,
                        "varying_params": list(varying_params.keys()),
                        "example_values": {k: v[:3] for k, v in varying_params.items()}
                    },
                    source_demos=[s.step_id for s in steps[:3]],
                    frequency=len(steps),
                    confidence=0.7
                )
                self.patterns[pattern.pattern_id] = pattern
                patterns.append(pattern)
        
        return patterns
    
    def get_pattern(self, pattern_id: str) -> Optional[ExtractedPattern]:
        """Get a pattern by ID."""
        return self.patterns.get(pattern_id)
    
    def find_similar_patterns(self, pattern: ExtractedPattern,
                             threshold: float = 0.8) -> List[ExtractedPattern]:
        """Find patterns similar to the given pattern."""
        similar = []
        for other in self.patterns.values():
            if other.pattern_id == pattern.pattern_id:
                continue
            similarity = self._calculate_similarity(pattern, other)
            if similarity >= threshold:
                similar.append(other)
        return similar
    
    def _calculate_similarity(self, p1: ExtractedPattern, p2: ExtractedPattern) -> float:
        """Calculate similarity between two patterns."""
        if p1.pattern_type != p2.pattern_type:
            return 0.0
        
        if p1.pattern_type == PatternType.ACTION_SEQUENCE:
            seq1 = [(a.get("action_type"), a.get("tool_name")) for a in p1.action_sequence]
            seq2 = [(a.get("action_type"), a.get("tool_name")) for a in p2.action_sequence]
            
            if not seq1 or not seq2:
                return 0.0
            
            # Simple Jaccard similarity for sequences
            set1, set2 = set(seq1), set(seq2)
            intersection = len(set1 & set2)
            union = len(set1 | set2)
            return intersection / union if union > 0 else 0.0
        
        return 0.5  # Default for other types


class SkillSynthesizer:
    """Synthesizes skills from extracted patterns."""
    
    def __init__(self, skill_library_path: Optional[str] = None):
        self.skills: Dict[str, LearnedSkill] = {}
        self.skill_library_path = Path(skill_library_path) if skill_library_path else None
        
        if self.skill_library_path:
            self._load_skills()
    
    def synthesize_skill(self, name: str, description: str,
                        patterns: List[ExtractedPattern],
                        demonstrations: List[Demonstration],
                        skill_type: SkillType = SkillType.SEQUENTIAL) -> LearnedSkill:
        """Synthesize a new skill from patterns and demonstrations."""
        # Collect required tools
        tools: Set[str] = set()
        for pattern in patterns:
            for action in pattern.action_sequence:
                if action.get("tool_name"):
                    tools.add(action["tool_name"])
        
        for demo in demonstrations:
            tools.update(demo.get_tools_used())
        
        # Build parameter schema
        param_schema = self._infer_parameter_schema(patterns, demonstrations)
        
        # Calculate estimated success rate
        success_count = sum(1 for d in demonstrations if d.success)
        success_rate = success_count / len(demonstrations) if demonstrations else 0.0
        
        skill = LearnedSkill(
            skill_type=skill_type,
            name=name,
            description=description,
            patterns=patterns,
            parameter_schema=param_schema,
            required_tools=list(tools),
            estimated_success_rate=success_rate,
            demonstrations_used=[d.demo_id for d in demonstrations]
        )
        
        self.skills[skill.skill_id] = skill
        
        if self.skill_library_path:
            self._save_skills()
        
        return skill
    
    def refine_skill(self, skill_id: str, new_demonstrations: List[Demonstration],
                    new_patterns: Optional[List[ExtractedPattern]] = None) -> LearnedSkill:
        """Refine an existing skill with new demonstrations."""
        if skill_id not in self.skills:
            raise ValueError(f"Skill {skill_id} not found")
        
        old_skill = self.skills[skill_id]
        
        # Create new version
        refined = LearnedSkill(
            skill_type=old_skill.skill_type,
            name=old_skill.name,
            description=old_skill.description,
            patterns=old_skill.patterns + (new_patterns or []),
            parameter_schema=self._merge_param_schemas(
                old_skill.parameter_schema,
                self._infer_parameter_schema([], new_demonstrations)
            ),
            required_tools=list(set(old_skill.required_tools) | 
                              set().union(*(d.get_tools_used() for d in new_demonstrations))),
            parent_skill=skill_id,
            demonstrations_used=old_skill.demonstrations_used + [d.demo_id for d in new_demonstrations]
        )
        
        # Update success rate
        all_demos = old_skill.demonstrations_used + [d.demo_id for d in new_demonstrations]
        success_count = sum(1 for d in new_demonstrations if d.success)
        old_success = old_skill.estimated_success_rate * len(old_skill.demonstrations_used)
        refined.estimated_success_rate = (old_success + success_count) / len(all_demos) if all_demos else 0.0
        
        refined.bump_version("minor" if new_patterns else "patch")
        self.skills[refined.skill_id] = refined
        
        if self.skill_library_path:
            self._save_skills()
        
        return refined
    
    def get_skill(self, skill_id: str) -> Optional[LearnedSkill]:
        """Get a skill by ID."""
        return self.skills.get(skill_id)
    
    def find_skills(self, name_pattern: Optional[str] = None,
                   required_tool: Optional[str] = None) -> List[LearnedSkill]:
        """Find skills matching criteria."""
        results = []
        for skill in self.skills.values():
            if name_pattern and name_pattern.lower() not in skill.name.lower():
                continue
            if required_tool and required_tool not in skill.required_tools:
                continue
            results.append(skill)
        return results
    
    def execute_skill(self, skill_id: str, parameters: Dict[str, Any],
                     tool_registry: Optional[Dict[str, Callable]] = None) -> Dict[str, Any]:
        """Execute a learned skill with given parameters."""
        skill = self.get_skill(skill_id)
        if not skill:
            return {"success": False, "error": f"Skill {skill_id} not found"}
        
        results = []
        for pattern in skill.patterns:
            if pattern.pattern_type == PatternType.ACTION_SEQUENCE:
                for action in pattern.action_sequence:
                    action_type = action.get("action_type")
                    tool_name = action.get("tool_name")
                    
                    if tool_name and tool_registry and tool_name in tool_registry:
                        try:
                            tool_result = tool_registry[tool_name](**parameters)
                            results.append({
                                "action": action_type,
                                "tool": tool_name,
                                "result": tool_result,
                                "success": True
                            })
                        except Exception as e:
                            results.append({
                                "action": action_type,
                                "tool": tool_name,
                                "error": str(e),
                                "success": False
                            })
        
        skill.usage_count += 1
        
        return {
            "success": all(r.get("success", True) for r in results),
            "skill_id": skill_id,
            "skill_name": skill.name,
            "results": results
        }
    
    def _infer_parameter_schema(self, patterns: List[ExtractedPattern],
                                demonstrations: List[Demonstration]) -> Dict[str, Any]:
        """Infer parameter schema from patterns and demonstrations."""
        schema = {"properties": {}, "required": []}
        
        # Collect all parameter keys
        all_params: Dict[str, Set[type]] = {}
        for demo in demonstrations:
            for step in demo.steps:
                for key, value in step.parameters.items():
                    if key not in all_params:
                        all_params[key] = set()
                    all_params[key].add(type(value))
        
        # Build schema
        type_mapping = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object"
        }
        
        for key, types in all_params.items():
            schema["properties"][key] = {
                "type": [type_mapping.get(t, "string") for t in types]
            }
        
        return schema
    
    def _merge_param_schemas(self, schema1: Dict, schema2: Dict) -> Dict:
        """Merge two parameter schemas."""
        merged = {"properties": {}, "required": []}
        
        for key in set(schema1.get("properties", {}).keys()) | set(schema2.get("properties", {}).keys()):
            if key in schema1.get("properties", {}) and key in schema2.get("properties", {}):
                # Merge types
                types1 = schema1["properties"][key].get("type", [])
                types2 = schema2["properties"][key].get("type", [])
                merged["properties"][key] = {
                    "type": list(set(types1 if isinstance(types1, list) else [types1]) | 
                                set(types2 if isinstance(types2, list) else [types2]))
                }
            elif key in schema1.get("properties", {}):
                merged["properties"][key] = schema1["properties"][key]
            else:
                merged["properties"][key] = schema2["properties"][key]
        
        return merged
    
    def _save_skills(self) -> None:
        """Save skills to disk."""
        if not self.skill_library_path:
            return
        self.skill_library_path.mkdir(parents=True, exist_ok=True)
        data = {k: v.to_dict() for k, v in self.skills.items()}
        with open(self.skill_library_path / "skill_library.json", "w") as f:
            json.dump(data, f, indent=2)
    
    def _load_skills(self) -> None:
        """Load skills from disk."""
        if not self.skill_library_path:
            return
        file_path = self.skill_library_path / "skill_library.json"
        if file_path.exists():
            with open(file_path, "r") as f:
                data = json.load(f)
                self.skills = {k: LearnedSkill.from_dict(v) for k, v in data.items()}


class TransferLearning:
    """Handles transfer of learned skills to new contexts."""
    
    def __init__(self, skill_synthesizer: SkillSynthesizer):
        self.skill_synthesizer = skill_synthesizer
    
    def adapt_skill(self, skill_id: str, target_context: Dict[str, Any],
                   adaptation_strategy: str = "parameter_mapping") -> Optional[LearnedSkill]:
        """Adapt a skill to a new context."""
        skill = self.skill_synthesizer.get_skill(skill_id)
        if not skill:
            return None
        
        if adaptation_strategy == "parameter_mapping":
            return self._adapt_by_parameter_mapping(skill, target_context)
        elif adaptation_strategy == "pattern_substitution":
            return self._adapt_by_pattern_substitution(skill, target_context)
        else:
            return None
    
    def _adapt_by_parameter_mapping(self, skill: LearnedSkill,
                                    target_context: Dict[str, Any]) -> LearnedSkill:
        """Adapt skill by mapping parameters to new context."""
        # Create adapted parameter schema
        adapted_schema = copy.deepcopy(skill.parameter_schema)
        
        # Map context values to parameters
        for key in adapted_schema.get("properties", {}):
            if key in target_context:
                adapted_schema["properties"][key]["default"] = target_context[key]
        
        # Create adapted skill
        adapted = LearnedSkill(
            skill_type=skill.skill_type,
            name=f"{skill.name}_adapted",
            description=f"{skill.description} (adapted for new context)",
            patterns=skill.patterns,
            parameter_schema=adapted_schema,
            required_tools=skill.required_tools,
            parent_skill=skill.skill_id,
            demonstrations_used=skill.demonstrations_used
        )
        
        adapted.estimated_success_rate = skill.estimated_success_rate * 0.9  # Slight penalty for adaptation
        
        self.skill_synthesizer.skills[adapted.skill_id] = adapted
        return adapted
    
    def _adapt_by_pattern_substitution(self, skill: LearnedSkill,
                                      target_context: Dict[str, Any]) -> LearnedSkill:
        """Adapt skill by substituting patterns based on context."""
        # Clone patterns with substitutions
        adapted_patterns = []
        for pattern in skill.patterns:
            adapted_pattern = copy.deepcopy(pattern)
            
            # Substitute tool names if mappings provided
            if "tool_mappings" in target_context:
                for action in adapted_pattern.action_sequence:
                    old_tool = action.get("tool_name")
                    if old_tool in target_context["tool_mappings"]:
                        action["tool_name"] = target_context["tool_mappings"][old_tool]
            
            adapted_patterns.append(adapted_pattern)
        
        adapted = LearnedSkill(
            skill_type=skill.skill_type,
            name=f"{skill.name}_substituted",
            description=f"{skill.description} (pattern substituted)",
            patterns=adapted_patterns,
            parameter_schema=skill.parameter_schema,
            required_tools=list(set(
                target_context.get("tool_mappings", {}).get(t, t) 
                for t in skill.required_tools
            )),
            parent_skill=skill.skill_id,
            demonstrations_used=skill.demonstrations_used
        )
        
        adapted.estimated_success_rate = skill.estimated_success_rate * 0.85  # Higher penalty for substitution
        
        self.skill_synthesizer.skills[adapted.skill_id] = adapted
        return adapted
    
    def compose_skills(self, skill_ids: List[str], name: str,
                      description: str) -> Optional[LearnedSkill]:
        """Compose multiple skills into a new composite skill."""
        skills = [self.skill_synthesizer.get_skill(sid) for sid in skill_ids]
        if not all(skills):
            return None
        
        # Combine patterns
        all_patterns = []
        for skill in skills:
            all_patterns.extend(skill.patterns)
        
        # Combine required tools
        all_tools = set()
        for skill in skills:
            all_tools.update(skill.required_tools)
        
        # Combine demonstrations
        all_demos = []
        for skill in skills:
            all_demos.extend(skill.demonstrations_used)
        
        composed = LearnedSkill(
            skill_type=SkillType.COMPOSITE,
            name=name,
            description=description,
            patterns=all_patterns,
            required_tools=list(all_tools),
            demonstrations_used=list(set(all_demos))
        )
        
        # Average success rate with penalty for composition
        avg_success = sum(s.estimated_success_rate for s in skills) / len(skills)
        composed.estimated_success_rate = avg_success * 0.9
        
        self.skill_synthesizer.skills[composed.skill_id] = composed
        return composed


# Convenience function for creating an LfD system
def create_lfd_system(storage_path: Optional[str] = None) -> Tuple[DemonstrationRecorder, PatternExtractor, SkillSynthesizer, TransferLearning]:
    """Create a complete Learning from Demonstration system."""
    recorder = DemonstrationRecorder(storage_path=storage_path)
    extractor = PatternExtractor()
    synthesizer = SkillSynthesizer(skill_library_path=storage_path)
    transfer = TransferLearning(synthesizer)
    return recorder, extractor, synthesizer, transfer
