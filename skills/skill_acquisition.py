"""
Self-Evolving Skill Acquisition Module for AGI agents.

Based on research from Agent-World (arXiv:2604.18292) and GenericAgent patterns,
this module enables agents to crystallize successful execution paths into reusable
skills, organize them in a skill tree with dependency tracking, and evolve them
through continuous learning.

Key concepts:
- Skill Crystallization: Convert successful demonstrations into reusable skills
- Skill Tree: Hierarchical organization with dependency tracking
- Skill Evolution: Versioning and iterative improvement
- Transfer Learning: Apply skills to new contexts
"""

from typing import Dict, List, Any, Optional, Callable, Set, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum, auto
import json
import hashlib
import uuid
from collections import defaultdict


class SkillStatus(Enum):
    """Status of a skill in its lifecycle."""
    DRAFT = auto()        # Just recorded, not yet validated
    VALIDATED = auto()    # Successfully tested
    ACTIVE = auto()       # In active use
    DEPRECATED = auto()   # Superseded by newer version
    BROKEN = auto()       # Failed validation, needs repair


class SkillType(Enum):
    """Types of skills based on their origin and nature."""
    ATOMIC = auto()       # Basic, indivisible skill
    COMPOSITE = auto()    # Composed of sub-skills
    ADAPTIVE = auto()     # Self-modifying based on context
    META = auto()         # Skills about skill management


@dataclass
class ExecutionStep:
    """A single step in a demonstrated execution."""
    step_number: int
    action: str                    # What was done
    tool_used: Optional[str]       # Tool name if applicable
    input_params: Dict[str, Any]   # Input parameters
    output_result: Any             # Result/observation
    context: Dict[str, Any]        # Execution context
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "action": self.action,
            "tool_used": self.tool_used,
            "input_params": self.input_params,
            "output_result": self.output_result,
            "context": self.context,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionStep":
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass
class SkillDemonstration:
    """A recorded demonstration of successfully completing a task."""
    demo_id: str
    task_description: str
    domain: str                    # Domain/category (e.g., "web_search", "file_ops")
    steps: List[ExecutionStep]
    success_outcome: Any
    performance_metrics: Dict[str, float]  # e.g., {"accuracy": 0.95, "time": 1.2}
    context: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        if not self.demo_id:
            self.demo_id = str(uuid.uuid4())[:8]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "demo_id": self.demo_id,
            "task_description": self.task_description,
            "domain": self.domain,
            "steps": [s.to_dict() for s in self.steps],
            "success_outcome": self.success_outcome,
            "performance_metrics": self.performance_metrics,
            "context": self.context,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillDemonstration":
        data["steps"] = [ExecutionStep.from_dict(s) for s in data["steps"]]
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)
    
    def get_fingerprint(self) -> str:
        """Generate unique fingerprint for deduplication."""
        content = json.dumps({
            "task": self.task_description,
            "domain": self.domain,
            "n_steps": len(self.steps),
            "tools": [s.tool_used for s in self.steps]
        }, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()[:12]


@dataclass
class Skill:
    """
    A crystallized skill extracted from demonstrations.
    
    Skills are reusable execution patterns that can be applied
    to similar tasks across different contexts.
    """
    skill_id: str
    name: str
    description: str
    domain: str
    skill_type: SkillType
    status: SkillStatus
    
    # Source information
    derived_from: List[str] = field(default_factory=list)  # demo_ids
    parent_skill: Optional[str] = None  # For hierarchical skills
    sub_skills: List[str] = field(default_factory=list)
    
    # Execution pattern
    pattern_template: Dict[str, Any] = field(default_factory=dict)
    required_tools: List[str] = field(default_factory=list)
    parameter_schema: Dict[str, Any] = field(default_factory=dict)
    
    # Performance tracking
    usage_count: int = 0
    success_count: int = 0
    total_execution_time: float = 0.0
    average_performance: float = 0.0
    
    # Versioning
    version: int = 1
    previous_versions: List[str] = field(default_factory=list)
    
    # Metadata
    tags: Set[str] = field(default_factory=set)
    dependencies: Set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.now)
    last_used: Optional[datetime] = None
    last_validated: Optional[datetime] = None
    
    def __post_init__(self):
        if not self.skill_id:
            self.skill_id = f"{self.domain}_{self.name.lower().replace(' ', '_')}_{str(uuid.uuid4())[:6]}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "skill_type": self.skill_type.name,
            "status": self.status.name,
            "derived_from": self.derived_from,
            "parent_skill": self.parent_skill,
            "sub_skills": self.sub_skills,
            "pattern_template": self.pattern_template,
            "required_tools": self.required_tools,
            "parameter_schema": self.parameter_schema,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "total_execution_time": self.total_execution_time,
            "average_performance": self.average_performance,
            "version": self.version,
            "previous_versions": self.previous_versions,
            "tags": list(self.tags),
            "dependencies": list(self.dependencies),
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "last_validated": self.last_validated.isoformat() if self.last_validated else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Skill":
        data["skill_type"] = SkillType[data["skill_type"]]
        data["status"] = SkillStatus[data["status"]]
        data["tags"] = set(data.get("tags", []))
        data["dependencies"] = set(data.get("dependencies", []))
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("last_used"):
            data["last_used"] = datetime.fromisoformat(data["last_used"])
        if data.get("last_validated"):
            data["last_validated"] = datetime.fromisoformat(data["last_validated"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        if self.usage_count == 0:
            return 0.0
        return self.success_count / self.usage_count
    
    @property
    def maturity_score(self) -> float:
        """Calculate maturity based on usage and validation."""
        score = 0.0
        if self.status == SkillStatus.ACTIVE:
            score += 0.3
        if self.status == SkillStatus.VALIDATED:
            score += 0.2
        score += min(self.usage_count / 100, 0.3)  # Cap at 30%
        score += self.success_rate * 0.2
        return min(score, 1.0)
    
    def record_execution(self, success: bool, execution_time: float, performance: float):
        """Record an execution instance."""
        self.usage_count += 1
        if success:
            self.success_count += 1
        self.total_execution_time += execution_time
        self.last_used = datetime.now()
        
        # Update running average
        self.average_performance = (
            (self.average_performance * (self.usage_count - 1) + performance)
            / self.usage_count
        )


class SkillDemonstrationRecorder:
    """Records and stores successful task executions as demonstrations."""
    
    def __init__(self):
        self._demonstrations: Dict[str, SkillDemonstration] = {}
        self._fingerprints: Set[str] = set()  # For deduplication
    
    def record_demonstration(
        self,
        task_description: str,
        domain: str,
        steps: List[ExecutionStep],
        success_outcome: Any,
        performance_metrics: Dict[str, float],
        context: Dict[str, Any] = None
    ) -> SkillDemonstration:
        """
        Record a successful task execution as a demonstration.
        
        Args:
            task_description: What task was accomplished
            domain: Category/domain of the task
            steps: Execution steps taken
            success_outcome: The successful result
            performance_metrics: Performance data (accuracy, time, etc.)
            context: Additional context
        
        Returns:
            The recorded demonstration
        """
        demo = SkillDemonstration(
            demo_id=str(uuid.uuid4())[:8],
            task_description=task_description,
            domain=domain,
            steps=steps,
            success_outcome=success_outcome,
            performance_metrics=performance_metrics,
            context=context or {}
        )
        
        # Check for duplicates
        fingerprint = demo.get_fingerprint()
        if fingerprint in self._fingerprints:
            # Find and return existing
            for d in self._demonstrations.values():
                if d.get_fingerprint() == fingerprint:
                    return d
        
        self._demonstrations[demo.demo_id] = demo
        self._fingerprints.add(fingerprint)
        
        return demo
    
    def get_demonstration(self, demo_id: str) -> Optional[SkillDemonstration]:
        """Retrieve a demonstration by ID."""
        return self._demonstrations.get(demo_id)
    
    def find_demonstrations(
        self,
        domain: str = None,
        min_performance: float = None
    ) -> List[SkillDemonstration]:
        """Find demonstrations matching criteria."""
        results = list(self._demonstrations.values())
        
        if domain:
            results = [d for d in results if d.domain == domain]
        
        if min_performance:
            results = [
                d for d in results
                if d.performance_metrics.get("accuracy", 0) >= min_performance
            ]
        
        return sorted(results, key=lambda d: d.created_at, reverse=True)
    
    def get_all_demonstrations(self) -> List[SkillDemonstration]:
        """Get all recorded demonstrations."""
        return list(self._demonstrations.values())
    
    def clear(self):
        """Clear all demonstrations."""
        self._demonstrations.clear()
        self._fingerprints.clear()


class PatternExtractor:
    """
    Extracts reusable patterns from demonstrations.
    
    Uses abstraction to identify common patterns across multiple
    successful executions of similar tasks.
    """
    
    def extract_pattern(
        self,
        demonstrations: List[SkillDemonstration]
    ) -> Dict[str, Any]:
        """
        Extract a generalized pattern from multiple demonstrations.
        
        Args:
            demonstrations: Similar demonstrations to generalize from
        
        Returns:
            Pattern template with variables for context-specific values
        """
        if not demonstrations:
            return {}
        
        # Analyze step sequences
        step_patterns = self._analyze_step_sequences(demonstrations)
        
        # Extract parameter schemas
        param_schema = self._extract_parameter_schema(demonstrations)
        
        # Identify required tools
        tools = self._identify_required_tools(demonstrations)
        
        # Create abstraction template
        template = {
            "step_pattern": step_patterns,
            "variable_slots": self._identify_variable_slots(demonstrations),
            "invariant_structure": self._extract_invariant_structure(demonstrations)
        }
        
        return {
            "template": template,
            "parameter_schema": param_schema,
            "required_tools": tools,
            "source_count": len(demonstrations)
        }
    
    def _analyze_step_sequences(
        self,
        demonstrations: List[SkillDemonstration]
    ) -> List[Dict[str, Any]]:
        """Analyze common step sequences across demonstrations."""
        if not demonstrations:
            return []
        
        # Find the most common sequence structure
        sequences = [[s.action for s in d.steps] for d in demonstrations]
        
        # Simple approach: use the most common sequence
        from collections import Counter
        sequence_counts = Counter(tuple(s) for s in sequences)
        most_common = sequence_counts.most_common(1)[0][0]
        
        return [{"action_type": action} for action in most_common]
    
    def _extract_parameter_schema(
        self,
        demonstrations: List[SkillDemonstration]
    ) -> Dict[str, Any]:
        """Extract parameter schema from demonstration inputs."""
        all_params = defaultdict(list)
        
        for demo in demonstrations:
            for step in demo.steps:
                for key, value in step.input_params.items():
                    all_params[key].append(type(value).__name__)
        
        schema = {}
        for param, types in all_params.items():
            most_common_type = max(set(types), key=types.count)
            schema[param] = {
                "type": most_common_type,
                "frequency": len(types) / len(demonstrations),
                "required": len(types) == len(demonstrations)
            }
        
        return schema
    
    def _identify_required_tools(
        self,
        demonstrations: List[SkillDemonstration]
    ) -> List[str]:
        """Identify tools consistently used across demonstrations."""
        tool_usage = defaultdict(int)
        
        for demo in demonstrations:
            demo_tools = set(s.tool_used for s in demo.steps if s.tool_used)
            for tool in demo_tools:
                tool_usage[tool] += 1
        
        # Tools used in >50% of demonstrations
        threshold = len(demonstrations) * 0.5
        return [tool for tool, count in tool_usage.items() if count >= threshold]
    
    def _identify_variable_slots(
        self,
        demonstrations: List[SkillDemonstration]
    ) -> List[str]:
        """Identify parameters that vary across demonstrations."""
        if len(demonstrations) < 2:
            return []
        
        variable_slots = []
        
        # Check first step inputs for variability
        first_steps = [d.steps[0] for d in demonstrations if d.steps]
        all_keys = set()
        for step in first_steps:
            all_keys.update(step.input_params.keys())
        
        for key in all_keys:
            values = [s.input_params.get(key) for s in first_steps if key in s.input_params]
            if len(set(str(v) for v in values)) > 1:  # Values differ
                variable_slots.append(key)
        
        return variable_slots
    
    def _extract_invariant_structure(
        self,
        demonstrations: List[SkillDemonstration]
    ) -> Dict[str, Any]:
        """Extract the invariant structure common to all demonstrations."""
        if not demonstrations:
            return {}
        
        # Common context keys
        all_context_keys = [set(d.context.keys()) for d in demonstrations]
        common_keys = all_context_keys[0].intersection(*all_context_keys[1:]) if len(all_context_keys) > 1 else set()
        
        return {
            "common_context_keys": list(common_keys),
            "num_steps_range": (
                min(len(d.steps) for d in demonstrations),
                max(len(d.steps) for d in demonstrations)
            )
        }


class SkillTree:
    """
    Hierarchical organization of skills with dependency tracking.
    
    Skills are organized in a tree structure where:
    - Parent skills are more general/abstract
    - Child skills are specialized variants or sub-tasks
    - Dependencies indicate skills that must be available for another to work
    """
    
    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._domain_index: Dict[str, Set[str]] = defaultdict(set)
        self._tag_index: Dict[str, Set[str]] = defaultdict(set)
        self._dependency_graph: Dict[str, Set[str]] = defaultdict(set)
    
    def add_skill(self, skill: Skill) -> bool:
        """
        Add a skill to the tree.
        
        Args:
            skill: The skill to add
        
        Returns:
            True if added, False if already exists
        """
        if skill.skill_id in self._skills:
            return False
        
        self._skills[skill.skill_id] = skill
        self._domain_index[skill.domain].add(skill.skill_id)
        
        for tag in skill.tags:
            self._tag_index[tag].add(skill.skill_id)
        
        for dep in skill.dependencies:
            self._dependency_graph[skill.skill_id].add(dep)
        
        return True
    
    def get_skill(self, skill_id: str) -> Optional[Skill]:
        """Get a skill by ID."""
        return self._skills.get(skill_id)
    
    def find_skills(
        self,
        domain: str = None,
        tags: Set[str] = None,
        status: SkillStatus = None,
        min_maturity: float = None
    ) -> List[Skill]:
        """Find skills matching criteria."""
        candidates = set(self._skills.keys())
        
        if domain:
            candidates &= self._domain_index.get(domain, set())
        
        if tags:
            for tag in tags:
                candidates &= self._tag_index.get(tag, set())
        
        results = [self._skills[sid] for sid in candidates]
        
        if status:
            results = [s for s in results if s.status == status]
        
        if min_maturity:
            results = [s for s in results if s.maturity_score >= min_maturity]
        
        return sorted(results, key=lambda s: s.maturity_score, reverse=True)
    
    def get_dependencies(self, skill_id: str) -> Set[str]:
        """Get direct dependencies for a skill."""
        return self._dependency_graph.get(skill_id, set())
    
    def get_all_dependencies(self, skill_id: str, visited: Set[str] = None) -> Set[str]:
        """Get all transitive dependencies for a skill."""
        if visited is None:
            visited = set()
        
        if skill_id in visited:
            return set()
        
        visited.add(skill_id)
        direct = self.get_dependencies(skill_id)
        
        all_deps = set(direct)
        for dep in direct:
            all_deps |= self.get_all_dependencies(dep, visited)
        
        return all_deps
    
    def get_dependents(self, skill_id: str) -> Set[str]:
        """Get skills that depend on this skill."""
        dependents = set()
        for sid, deps in self._dependency_graph.items():
            if skill_id in deps:
                dependents.add(sid)
        return dependents
    
    def check_dependency_cycles(self) -> Optional[List[str]]:
        """Check for dependency cycles in the skill tree."""
        visited = set()
        rec_stack = set()
        
        def dfs(node: str, path: List[str]) -> Optional[List[str]]:
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in self._dependency_graph.get(node, []):
                if neighbor not in visited:
                    result = dfs(neighbor, path + [neighbor])
                    if result:
                        return result
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor) if neighbor in path else 0
                    return path[cycle_start:] + [neighbor]
            
            rec_stack.remove(node)
            return None
        
        for skill_id in self._skills:
            if skill_id not in visited:
                cycle = dfs(skill_id, [skill_id])
                if cycle:
                    return cycle
        
        return None
    
    def get_skill_lineage(self, skill_id: str) -> List[Skill]:
        """Get lineage from root to this skill (parent chain)."""
        lineage = []
        current = self._skills.get(skill_id)
        
        while current:
            lineage.insert(0, current)
            if current.parent_skill:
                current = self._skills.get(current.parent_skill)
            else:
                break
        
        return lineage
    
    def get_subtree(self, skill_id: str) -> List[Skill]:
        """Get all skills in the subtree rooted at skill_id."""
        root = self._skills.get(skill_id)
        if not root:
            return []
        
        subtree = [root]
        to_process = list(root.sub_skills)
        
        while to_process:
            sid = to_process.pop(0)
            skill = self._skills.get(sid)
            if skill:
                subtree.append(skill)
                to_process.extend(skill.sub_skills)
        
        return subtree
    
    def remove_skill(self, skill_id: str) -> bool:
        """Remove a skill from the tree."""
        if skill_id not in self._skills:
            return False
        
        skill = self._skills[skill_id]
        
        # Check if other skills depend on it
        dependents = self.get_dependents(skill_id)
        if dependents:
            # Can't remove - other skills depend on it
            return False
        
        del self._skills[skill_id]
        self._domain_index[skill.domain].discard(skill_id)
        
        for tag in skill.tags:
            self._tag_index[tag].discard(skill_id)
        
        # Only delete from dependency graph if entry exists
        if skill_id in self._dependency_graph:
            del self._dependency_graph[skill_id]
        
        return True
    
    def get_all_skills(self) -> List[Skill]:
        """Get all skills in the tree."""
        return list(self._skills.values())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the skill tree."""
        status_counts = defaultdict(int)
        type_counts = defaultdict(int)
        
        for skill in self._skills.values():
            status_counts[skill.status.name] += 1
            type_counts[skill.skill_type.name] += 1
        
        return {
            "total_skills": len(self._skills),
            "by_status": dict(status_counts),
            "by_type": dict(type_counts),
            "by_domain": {d: len(s) for d, s in self._domain_index.items()},
            "cycle_detected": self.check_dependency_cycles() is not None
        }


class SkillCrystallizer:
    """
    Crystallizes successful demonstrations into reusable skills.
    
    This is the core of the self-evolution capability - converting
    successful execution patterns into generalized, reusable skills.
    """
    
    def __init__(
        self,
        recorder: SkillDemonstrationRecorder = None,
        extractor: PatternExtractor = None,
        skill_tree: SkillTree = None
    ):
        self.recorder = recorder or SkillDemonstrationRecorder()
        self.extractor = extractor or PatternExtractor()
        self.skill_tree = skill_tree or SkillTree()
    
    def crystallize_skill(
        self,
        demo_ids: List[str],
        name: str,
        description: str,
        parent_skill: str = None,
        tags: Set[str] = None
    ) -> Optional[Skill]:
        """
        Crystallize demonstrations into a reusable skill.
        
        Args:
            demo_ids: IDs of demonstrations to crystallize from
            name: Name for the new skill
            description: Description of what the skill does
            parent_skill: Optional parent skill ID
            tags: Tags for categorization
        
        Returns:
            The crystallized skill, or None if failed
        """
        # Retrieve demonstrations
        demonstrations = []
        for demo_id in demo_ids:
            demo = self.recorder.get_demonstration(demo_id)
            if demo:
                demonstrations.append(demo)
        
        if not demonstrations:
            return None
        
        # Extract pattern
        pattern = self.extractor.extract_pattern(demonstrations)
        
        if not pattern:
            return None
        
        # Get domain from first demonstration
        domain = demonstrations[0].domain
        
        # Create skill
        skill = Skill(
            skill_id="",
            name=name,
            description=description,
            domain=domain,
            skill_type=SkillType.COMPOSITE if len(demonstrations) > 1 else SkillType.ATOMIC,
            status=SkillStatus.DRAFT,
            derived_from=demo_ids,
            parent_skill=parent_skill,
            pattern_template=pattern["template"],
            required_tools=pattern["required_tools"],
            parameter_schema=pattern["parameter_schema"],
            tags=tags or set(),
            dependencies=set(pattern["required_tools"])  # Tools are dependencies
        )
        
        # Add to skill tree
        if self.skill_tree.add_skill(skill):
            # Update parent skill if specified
            if parent_skill:
                parent = self.skill_tree.get_skill(parent_skill)
                if parent:
                    parent.sub_skills.append(skill.skill_id)
            
            return skill
        
        return None
    
    def evolve_skill(
        self,
        skill_id: str,
        new_demonstrations: List[str],
        improved_description: str = None
    ) -> Optional[Skill]:
        """
        Evolve an existing skill with new demonstrations.
        
        Creates a new version of the skill incorporating learnings
        from additional successful executions.
        
        Args:
            skill_id: ID of skill to evolve
            new_demonstrations: New demo IDs to incorporate
            improved_description: Optional updated description
        
        Returns:
            The evolved skill (new version)
        """
        original = self.skill_tree.get_skill(skill_id)
        if not original:
            return None
        
        # Combine original and new demonstrations
        all_demos = list(set(original.derived_from + new_demonstrations))
        
        # Crystallize new version
        new_skill = self.crystallize_skill(
            demo_ids=all_demos,
            name=original.name,
            description=improved_description or original.description,
            parent_skill=original.parent_skill,
            tags=original.tags
        )
        
        if new_skill:
            # Update versioning
            new_skill.version = original.version + 1
            new_skill.previous_versions = original.previous_versions + [skill_id]
            
            # Mark original as superseded
            original.status = SkillStatus.DEPRECATED
            
            return new_skill
        
        return None
    
    def validate_skill(
        self,
        skill_id: str,
        test_contexts: List[Dict[str, Any]]
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate a skill against test contexts.
        
        Args:
            skill_id: Skill to validate
            test_contexts: List of test contexts to validate against
        
        Returns:
            (success, validation_results)
        """
        skill = self.skill_tree.get_skill(skill_id)
        if not skill:
            return False, {"error": "Skill not found"}
        
        # Check dependencies
        deps = self.skill_tree.get_all_dependencies(skill_id)
        missing_deps = [d for d in deps if d not in self.skill_tree._skills]
        
        if missing_deps:
            return False, {"error": f"Missing dependencies: {missing_deps}"}
        
        # Simulate validation (in real implementation, would execute skill)
        results = {
            "skill_id": skill_id,
            "tests_run": len(test_contexts),
            "dependencies_ok": len(missing_deps) == 0,
            "pattern_complete": bool(skill.pattern_template),
            "tools_available": all(
                t in self.skill_tree._skills for t in skill.required_tools
            ),
            "can_activate": len(missing_deps) == 0 and bool(skill.pattern_template)
        }
        
        success = results["can_activate"]
        
        if success:
            skill.status = SkillStatus.VALIDATED
            skill.last_validated = datetime.now()
        else:
            skill.status = SkillStatus.BROKEN
        
        return success, results
    
    def specialize_skill(
        self,
        skill_id: str,
        specialization_name: str,
        specialization_desc: str,
        specific_context: Dict[str, Any]
    ) -> Optional[Skill]:
        """
        Create a specialized variant of a skill for a specific context.
        
        Args:
            skill_id: Parent skill to specialize
            specialization_name: Name for specialized skill
            specialization_desc: Description
            specific_context: Context-specific parameters
        
        Returns:
            Specialized skill
        """
        parent = self.skill_tree.get_skill(skill_id)
        if not parent:
            return None
        
        # Create specialized skill as child
        specialized = Skill(
            skill_id="",
            name=specialization_name,
            description=specialization_desc,
            domain=parent.domain,
            skill_type=SkillType.ADAPTIVE,
            status=SkillStatus.DRAFT,
            parent_skill=skill_id,
            pattern_template=parent.pattern_template,  # Inherit pattern
            required_tools=parent.required_tools,
            parameter_schema=parent.parameter_schema,
            tags=parent.tags | {"specialized"}
        )
        
        # Add context-specific configuration
        specialized.pattern_template["specialization_context"] = specific_context
        
        if self.skill_tree.add_skill(specialized):
            parent.sub_skills.append(specialized.skill_id)
            return specialized
        
        return None


# ==================== Convenience Functions ====================

def create_crystallizer() -> SkillCrystallizer:
    """Factory function to create a new crystallizer with all components."""
    return SkillCrystallizer()


def quick_crystallize(
    demonstrations: List[SkillDemonstration],
    name: str,
    description: str
) -> Optional[Skill]:
    """
    Quick crystallization from demonstrations.
    
    One-shot function to crystallize skills without managing components.
    """
    crystallizer = create_crystallizer()
    
    # Record demonstrations
    demo_ids = []
    for demo in demonstrations:
        recorded = crystallizer.recorder.record_demonstration(
            task_description=demo.task_description,
            domain=demo.domain,
            steps=demo.steps,
            success_outcome=demo.success_outcome,
            performance_metrics=demo.performance_metrics,
            context=demo.context
        )
        demo_ids.append(recorded.demo_id)
    
    # Crystallize
    return crystallizer.crystallize_skill(
        demo_ids=demo_ids,
        name=name,
        description=description
    )


# ==================== Example Usage ====================

if __name__ == "__main__":
    # Demo: Create a skill from web search demonstrations
    
    # Create steps for a successful web search task
    steps = [
        ExecutionStep(
            step_number=1,
            action="Analyze query intent",
            tool_used=None,
            input_params={"query": "AGI latest research 2026"},
            output_result={"intent": "research", "domain": "AI"},
            context={"user_goal": "stay updated on AGI"}
        ),
        ExecutionStep(
            step_number=2,
            action="Execute web search",
            tool_used="web_search",
            input_params={"query": "AGI latest research 2026", "time_range": "week"},
            output_result={"results": 10, "sources": ["arxiv", "techcrunch"]},
            context={}
        ),
        ExecutionStep(
            step_number=3,
            action="Filter by relevance",
            tool_used=None,
            input_params={"min_relevance": 0.7},
            output_result={"filtered_results": 5},
            context={}
        )
    ]
    
    # Record demonstration
    recorder = SkillDemonstrationRecorder()
    demo = recorder.record_demonstration(
        task_description="Research latest AGI developments",
        domain="web_research",
        steps=steps,
        success_outcome="Summary of 5 key AGI research papers",
        performance_metrics={"accuracy": 0.92, "time_seconds": 3.5},
        context={"goal_type": "research", "depth": "overview"}
    )
    
    print(f"Recorded demonstration: {demo.demo_id}")
    print(f"Fingerprint: {demo.get_fingerprint()}")
    
    # Create another similar demonstration
    steps2 = [
        ExecutionStep(
            step_number=1,
            action="Analyze query intent",
            tool_used=None,
            input_params={"query": "neural network architectures 2026"},
            output_result={"intent": "research", "domain": "AI"},
            context={"user_goal": "learn about NN architectures"}
        ),
        ExecutionStep(
            step_number=2,
            action="Execute web search",
            tool_used="web_search",
            input_params={"query": "neural network architectures 2026", "time_range": "month"},
            output_result={"results": 8, "sources": ["arxiv", "medium"]},
            context={}
        ),
        ExecutionStep(
            step_number=3,
            action="Filter by relevance",
            tool_used=None,
            input_params={"min_relevance": 0.8},
            output_result={"filtered_results": 4},
            context={}
        )
    ]
    
    demo2 = recorder.record_demonstration(
        task_description="Research neural network architectures",
        domain="web_research",
        steps=steps2,
        success_outcome="Summary of 4 architecture papers",
        performance_metrics={"accuracy": 0.88, "time_seconds": 2.8},
        context={"goal_type": "research", "depth": "overview"}
    )
    
    # Crystallize into skill
    crystallizer = SkillCrystallizer(recorder=recorder)
    
    skill = crystallizer.crystallize_skill(
        demo_ids=[demo.demo_id, demo2.demo_id],
        name="Web Research Task",
        description="Execute structured web research with intent analysis and result filtering",
        tags={"research", "web", "autonomous"}
    )
    
    if skill:
        print(f"\nCrystallized skill: {skill.skill_id}")
        print(f"Name: {skill.name}")
        print(f"Type: {skill.skill_type.name}")
        print(f"Required tools: {skill.required_tools}")
        print(f"Parameter schema: {list(skill.parameter_schema.keys())}")
        
        # Validate
        success, results = crystallizer.validate_skill(
            skill.skill_id,
            test_contexts=[{"query": "test"}]
        )
        print(f"\nValidation: {'PASSED' if success else 'FAILED'}")
        print(f"Results: {results}")
        
        # Tree stats
        print(f"\nSkill tree stats: {crystallizer.skill_tree.get_stats()}")
