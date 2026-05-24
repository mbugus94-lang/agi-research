"""
Skill Governance Lifecycle Module

Inspired by SkillsVote: Lifecycle Governance of Agent Skills 
(arXiv:2605.18401v1)

Implements the skill governance pipeline:
Collection → Recommendation → Evolution

Integrates with:
- SelfHoningEngine (pattern extraction from trajectories)
- CategoryFramework (skill composition via morphisms)
- WorkflowDAG (skill execution and verification)

Key Features:
1. Skill Lifecycle Management (DRAFT → VALIDATED → ACTIVE → DEPRECATED)
2. Pattern-to-Skill Crystallization (from Self-Honing patterns)
3. Skill Recommendation Engine (context-aware skill suggestion)
4. Skill Evolution Pipeline (versioned improvements)
5. Skill Verification & Validation (pre-deployment gates)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Set, Tuple, Union
from enum import Enum, auto
from datetime import datetime
import hashlib
import json
import time
import uuid
from collections import defaultdict


class SkillLifecycleStage(Enum):
    """Stages in the skill lifecycle pipeline."""
    DRAFT = "draft"              # Initial creation, not validated
    VALIDATING = "validating"    # Undergoing verification tests
    VALIDATED = "validated"      # Passed validation, ready for activation
    ACTIVE = "active"            # Deployed and available for use
    DEPRECATED = "deprecated"    # Scheduled for removal
    BROKEN = "broken"            # Failed in production, needs repair
    RETIRED = "retired"          # No longer available


class SkillType(Enum):
    """Types of crystallized skills."""
    ATOMIC = "atomic"            # Single, indivisible operation
    COMPOSITE = "composite"      # Composed of sub-skills
    ADAPTIVE = "adaptive"        # Self-modifying based on context
    META = "meta"                # Skills that create/modify other skills
    RECOVERY = "recovery"        # Error handling and recovery


class PatternConfidence(Enum):
    """Confidence levels for pattern crystallization."""
    LOW = 0.3       # Needs more validation
    MEDIUM = 0.6    # Acceptable for draft skills
    HIGH = 0.8      # Ready for active deployment
    CERTAIN = 0.95  # Proven over many executions


@dataclass
class SkillVersion:
    """Version information for a skill."""
    major: int = 1
    minor: int = 0
    patch: int = 0
    
    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"
    
    def bump_major(self) -> 'SkillVersion':
        return SkillVersion(self.major + 1, 0, 0)
    
    def bump_minor(self) -> 'SkillVersion':
        return SkillVersion(self.major, self.minor + 1, 0)
    
    def bump_patch(self) -> 'SkillVersion':
        return SkillVersion(self.major, self.minor, self.patch + 1)


@dataclass
class SkillVerificationResult:
    """Results from skill validation testing."""
    passed: bool
    tests_run: int
    tests_passed: int
    coverage_percent: float
    execution_time_ms: float
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class CrystallizedSkill:
    """
    A skill crystallized from execution patterns.
    Ready for lifecycle governance.
    """
    skill_id: str
    name: str
    description: str
    skill_type: SkillType
    lifecycle_stage: SkillLifecycleStage
    
    # Source information
    derived_from_patterns: List[str]  # Pattern IDs
    extracted_from_trajectories: List[str]  # Trajectory IDs
    
    # Content
    action_template: List[str]
    parameter_schema: Dict[str, Any]
    preconditions: Dict[str, Any]
    postconditions: Dict[str, Any]
    required_tools: List[str]
    
    # Versioning
    version: SkillVersion
    previous_versions: List[Tuple[str, SkillVersion]] = field(default_factory=list)
    
    # Performance tracking
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    average_performance: float = 0.0
    last_used: Optional[float] = None
    
    # Metadata
    created_at: float = field(default_factory=time.time)
    tags: Set[str] = field(default_factory=set)
    domain: str = "general"
    
    # Verification
    verification_result: Optional[SkillVerificationResult] = None
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0
    
    @property
    def maturity_score(self) -> float:
        """Calculate maturity score (0-1) based on usage and success."""
        usage_score = min(self.usage_count / 100, 1.0) * 0.4
        success_score = self.success_rate * 0.4
        version_score = min(self.version.major / 3, 1.0) * 0.2
        return usage_score + success_score + version_score
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "skill_type": self.skill_type.value,
            "lifecycle_stage": self.lifecycle_stage.value,
            "derived_from_patterns": self.derived_from_patterns,
            "extracted_from_trajectories": self.extracted_from_trajectories,
            "action_template": self.action_template,
            "parameter_schema": self.parameter_schema,
            "preconditions": self.preconditions,
            "postconditions": self.postconditions,
            "required_tools": self.required_tools,
            "version": str(self.version),
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.success_rate,
            "average_performance": self.average_performance,
            "maturity_score": self.maturity_score,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "tags": list(self.tags),
            "domain": self.domain
        }


@dataclass
class SkillRecommendation:
    """A context-aware skill recommendation."""
    skill_id: str
    confidence: float
    relevance_score: float
    context_match: Dict[str, Any]
    reason: str
    estimated_success_rate: float


@dataclass
class EvolutionProposal:
    """Proposal for evolving/upgrading a skill."""
    original_skill_id: str
    proposed_skill_id: str
    change_type: str  # "patch", "minor", "major"
    improvements: List[str]
    new_patterns: List[str]
    breaking_changes: bool
    estimated_impact: float
    proposed_version: SkillVersion


class SkillRegistry:
    """Central registry for all crystallized skills."""
    
    def __init__(self):
        self.skills: Dict[str, CrystallizedSkill] = {}
        self.by_stage: Dict[SkillLifecycleStage, Set[str]] = defaultdict(set)
        self.by_type: Dict[SkillType, Set[str]] = defaultdict(set)
        self.by_domain: Dict[str, Set[str]] = defaultdict(set)
        self.by_tag: Dict[str, Set[str]] = defaultdict(set)
        
    def register(self, skill: CrystallizedSkill) -> None:
        """Register a skill in the registry."""
        self.skills[skill.skill_id] = skill
        self.by_stage[skill.lifecycle_stage].add(skill.skill_id)
        self.by_type[skill.skill_type].add(skill.skill_id)
        self.by_domain[skill.domain].add(skill.skill_id)
        for tag in skill.tags:
            self.by_tag[tag].add(skill.skill_id)
    
    def get(self, skill_id: str) -> Optional[CrystallizedSkill]:
        """Get a skill by ID."""
        return self.skills.get(skill_id)
    
    def update_stage(self, skill_id: str, new_stage: SkillLifecycleStage) -> bool:
        """Update a skill's lifecycle stage."""
        skill = self.skills.get(skill_id)
        if not skill:
            return False
        
        # Remove from old stage
        self.by_stage[skill.lifecycle_stage].discard(skill_id)
        
        # Update skill
        skill.lifecycle_stage = new_stage
        
        # Add to new stage
        self.by_stage[new_stage].add(skill_id)
        
        return True
    
    def find_by_stage(self, stage: SkillLifecycleStage) -> List[CrystallizedSkill]:
        """Find all skills in a given lifecycle stage."""
        return [self.skills[sid] for sid in self.by_stage[stage]]
    
    def find_active(self) -> List[CrystallizedSkill]:
        """Find all active skills."""
        return self.find_by_stage(SkillLifecycleStage.ACTIVE)
    
    def find_by_domain(self, domain: str) -> List[CrystallizedSkill]:
        """Find skills by domain."""
        return [self.skills[sid] for sid in self.by_domain[domain]]
    
    def find_by_tags(self, tags: Set[str]) -> List[CrystallizedSkill]:
        """Find skills matching any of the given tags."""
        skill_ids = set()
        for tag in tags:
            skill_ids.update(self.by_tag[tag])
        return [self.skills[sid] for sid in skill_ids]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get registry statistics."""
        return {
            "total_skills": len(self.skills),
            "by_stage": {stage.value: len(sids) for stage, sids in self.by_stage.items()},
            "by_type": {stype.value: len(sids) for stype, sids in self.by_type.items()},
            "domains": list(self.by_domain.keys()),
            "active_maturity_avg": sum(
                s.maturity_score for s in self.find_active()
            ) / len(self.by_stage[SkillLifecycleStage.ACTIVE]) if self.by_stage[SkillLifecycleStage.ACTIVE] else 0
        }


class PatternCrystallizer:
    """
    Crystallizes extracted patterns into governed skills.
    Bridge between SelfHoningEngine and SkillRegistry.
    """
    
    def __init__(self, registry: SkillRegistry):
        self.registry = registry
        self.min_confidence = PatternConfidence.MEDIUM
        self.crystallization_log: List[Dict] = []
    
    def crystallize(
        self,
        pattern_id: str,
        pattern_type: str,
        action_template: List[str],
        frequency: int,
        success_rate: float,
        source_trajectories: List[str],
        confidence: float,
        preconditions: Dict[str, Any],
        postconditions: Dict[str, Any],
        parameter_slots: List[str]
    ) -> Optional[CrystallizedSkill]:
        """
        Crystallize a pattern into a draft skill.
        
        Only crystallize patterns that meet confidence thresholds.
        """
        if confidence < self.min_confidence.value:
            return None
        
        # Determine skill type from pattern type
        skill_type = self._determine_skill_type(pattern_type)
        
        # Generate skill metadata
        skill_id = self._generate_skill_id(pattern_id)
        name = self._generate_skill_name(pattern_type, action_template)
        description = self._generate_description(pattern_type, action_template, success_rate)
        
        # Build parameter schema from parameter slots
        parameter_schema = self._build_parameter_schema(parameter_slots)
        
        # Create draft skill
        skill = CrystallizedSkill(
            skill_id=skill_id,
            name=name,
            description=description,
            skill_type=skill_type,
            lifecycle_stage=SkillLifecycleStage.DRAFT,
            derived_from_patterns=[pattern_id],
            extracted_from_trajectories=source_trajectories,
            action_template=action_template,
            parameter_schema=parameter_schema,
            preconditions=preconditions,
            postconditions=postconditions,
            required_tools=self._extract_tools(action_template),
            version=SkillVersion(0, 1, 0),  # Start at 0.1.0 for drafts
            tags=self._generate_tags(pattern_type),
            domain=self._infer_domain(action_template)
        )
        
        # Register in registry
        self.registry.register(skill)
        
        # Log crystallization
        self.crystallization_log.append({
            "timestamp": time.time(),
            "pattern_id": pattern_id,
            "skill_id": skill_id,
            "confidence": confidence,
            "success_rate": success_rate
        })
        
        return skill
    
    def _determine_skill_type(self, pattern_type: str) -> SkillType:
        """Determine skill type from pattern type."""
        mapping = {
            "action_sequence": SkillType.COMPOSITE,
            "recovery_strategy": SkillType.RECOVERY,
            "state_transition": SkillType.ATOMIC,
            "tool_usage": SkillType.ATOMIC,
            "error_handling": SkillType.RECOVERY
        }
        return mapping.get(pattern_type, SkillType.ATOMIC)
    
    def _generate_skill_id(self, pattern_id: str) -> str:
        """Generate unique skill ID from pattern ID."""
        hash_input = f"{pattern_id}_{time.time()}"
        return f"skill_{hashlib.md5(hash_input.encode()).hexdigest()[:12]}"
    
    def _generate_skill_name(self, pattern_type: str, action_template: List[str]) -> str:
        """Generate human-readable skill name."""
        if action_template:
            first_action = action_template[0].split("_")[0] if "_" in action_template[0] else action_template[0][:20]
            return f"{pattern_type.replace('_', ' ').title()} - {first_action}"
        return f"{pattern_type.replace('_', ' ').title()} Skill"
    
    def _generate_description(self, pattern_type: str, action_template: List[str], 
                              success_rate: float) -> str:
        """Generate skill description."""
        return (
            f"Auto-crystallized {pattern_type} skill with {len(action_template)} steps. "
            f"Derived from execution patterns with {success_rate:.0%} historical success rate."
        )
    
    def _build_parameter_schema(self, parameter_slots: List[str]) -> Dict[str, Any]:
        """Build JSON Schema-like parameter definition."""
        schema = {"type": "object", "properties": {}, "required": []}
        for param in parameter_slots:
            schema["properties"][param] = {"type": "string"}
            schema["required"].append(param)
        return schema
    
    def _extract_tools(self, action_template: List[str]) -> List[str]:
        """Extract tool names from action template."""
        tools = set()
        for action in action_template:
            if "tool" in action.lower():
                # Simple heuristic: extract tool names
                parts = action.split("_")
                for part in parts:
                    if part.lower() in ["search", "code", "write", "read", "execute"]:
                        tools.add(part)
        return list(tools)
    
    def _generate_tags(self, pattern_type: str) -> Set[str]:
        """Generate tags from pattern type."""
        return {pattern_type, "auto-crystallized", "draft"}
    
    def _infer_domain(self, action_template: List[str]) -> str:
        """Infer domain from action patterns."""
        combined = " ".join(action_template).lower()
        if any(x in combined for x in ["search", "arxiv", "paper", "research"]):
            return "research"
        if any(x in combined for x in ["code", "write", "read", "file"]):
            return "coding"
        if any(x in combined for x in ["data", "csv", "json", "query"]):
            return "data"
        return "general"


class SkillRecommendationEngine:
    """
    Context-aware skill recommendation.
    Based on SkillsVote recommendation phase.
    """
    
    def __init__(self, registry: SkillRegistry):
        self.registry = registry
        self.usage_history: List[Dict] = []
    
    def recommend(
        self,
        context: Dict[str, Any],
        available_skills: Optional[List[str]] = None,
        top_k: int = 5
    ) -> List[SkillRecommendation]:
        """
        Recommend skills based on execution context.
        
        Context may include:
        - Current task description
        - Required tools
        - Domain
        - Preconditions (current state)
        """
        # Get candidate skills
        if available_skills:
            candidates = [self.registry.get(sid) for sid in available_skills]
            candidates = [s for s in candidates if s is not None]
        else:
            candidates = self.registry.find_active()
        
        # Score each candidate
        scored = []
        for skill in candidates:
            score, match_info = self._calculate_relevance(skill, context)
            confidence = score * skill.maturity_score
            
            scored.append((skill, confidence, score, match_info))
        
        # Sort by confidence
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Return top-k recommendations
        recommendations = []
        for skill, confidence, relevance, match_info in scored[:top_k]:
            rec = SkillRecommendation(
                skill_id=skill.skill_id,
                confidence=confidence,
                relevance_score=relevance,
                context_match=match_info,
                reason=match_info.get("reason", "Pattern match"),
                estimated_success_rate=skill.success_rate
            )
            recommendations.append(rec)
        
        return recommendations
    
    def _calculate_relevance(
        self,
        skill: CrystallizedSkill,
        context: Dict[str, Any]
    ) -> Tuple[float, Dict[str, Any]]:
        """Calculate relevance score and match info."""
        scores = []
        match_info = {}
        
        # Domain match
        if "domain" in context:
            if skill.domain == context["domain"]:
                scores.append(0.3)
                match_info["domain_match"] = True
        
        # Tag overlap
        if "tags" in context:
            overlap = skill.tags & set(context["tags"])
            if overlap:
                scores.append(0.25 * (len(overlap) / len(context["tags"])))
                match_info["tag_overlap"] = list(overlap)
        
        # Tool compatibility
        if "required_tools" in context:
            required = set(context["required_tools"])
            available = set(skill.required_tools)
            if required <= available:  # Skill provides all required tools
                scores.append(0.25)
                match_info["tool_compatible"] = True
        
        # Precondition match
        if "preconditions" in context:
            current_state = context["preconditions"]
            pre_match = self._match_preconditions(skill.preconditions, current_state)
            scores.append(0.2 * pre_match)
            match_info["precondition_match"] = pre_match
        
        total_score = sum(scores)
        match_info["reason"] = f"Matched on {len([s for s in scores if s > 0])} criteria"
        
        return total_score, match_info
    
    def _match_preconditions(self, preconditions: Dict, current_state: Dict) -> float:
        """Calculate precondition match score (0-1)."""
        if not preconditions:
            return 1.0  # No preconditions = always matches
        
        matches = 0
        for key, value in preconditions.items():
            if key in current_state and current_state[key] == value:
                matches += 1
        
        return matches / len(preconditions)
    
    def record_usage(self, skill_id: str, success: bool, context: Dict) -> None:
        """Record skill usage for learning."""
        self.usage_history.append({
            "skill_id": skill_id,
            "success": success,
            "context": context,
            "timestamp": time.time()
        })


class SkillEvolutionPipeline:
    """
    Pipeline for evolving skills based on new patterns.
    Implements SkillsVote evolution phase.
    """
    
    def __init__(self, registry: SkillRegistry, crystallizer: PatternCrystallizer):
        self.registry = registry
        self.crystallizer = crystallizer
        self.proposals: List[EvolutionProposal] = []
        self.evolution_threshold = 0.15  # Min improvement to propose evolution (reduced from 0.7)
    
    def propose_evolution(
        self,
        skill_id: str,
        new_patterns: List[Dict[str, Any]]
    ) -> Optional[EvolutionProposal]:
        """
        Propose evolving a skill based on new patterns.
        
        Analyzes if new patterns suggest improvements to existing skill.
        """
        skill = self.registry.get(skill_id)
        if not skill:
            return None
        
        # Calculate potential improvement
        improvements = []
        breaking = False
        
        for pattern in new_patterns:
            # Check if pattern extends current skill
            if self._is_extension(skill, pattern):
                improvements.append(f"Extended with {pattern['pattern_type']}")
            # Check if pattern refines current skill
            elif self._is_refinement(skill, pattern):
                improvements.append(f"Refined {pattern['pattern_type']} precision")
            # Check if pattern replaces part of skill
            elif self._is_replacement(skill, pattern):
                improvements.append(f"Replaced with improved {pattern['pattern_type']}")
                breaking = True
        
        if not improvements:
            return None
        
        # Calculate version bump
        change_type, new_version = self._calculate_version_bump(skill, breaking, improvements)
        
        # Estimate impact
        estimated_impact = self._estimate_impact(skill, new_patterns)
        
        if estimated_impact < self.evolution_threshold:
            return None  # Not enough improvement to justify evolution
        
        proposal = EvolutionProposal(
            original_skill_id=skill_id,
            proposed_skill_id=f"{skill_id}_v{new_version}",
            change_type=change_type,
            improvements=improvements,
            new_patterns=[p["pattern_id"] for p in new_patterns],
            breaking_changes=breaking,
            estimated_impact=estimated_impact,
            proposed_version=new_version
        )
        
        self.proposals.append(proposal)
        return proposal
    
    def _is_extension(self, skill: CrystallizedSkill, pattern: Dict) -> bool:
        """Check if pattern extends the skill (adds new capabilities)."""
        return len(pattern.get("action_template", [])) > len(skill.action_template)
    
    def _is_refinement(self, skill: CrystallizedSkill, pattern: Dict) -> bool:
        """Check if pattern refines the skill (improves existing)."""
        return (pattern.get("success_rate", 0) > skill.success_rate and
                pattern.get("pattern_type") == skill.skill_type.value)
    
    def _is_replacement(self, skill: CrystallizedSkill, pattern: Dict) -> bool:
        """Check if pattern replaces part of the skill."""
        # Heuristic: pattern is shorter but more successful
        return (pattern.get("success_rate", 0) > skill.success_rate + 0.2 and
                len(pattern.get("action_template", [])) < len(skill.action_template))
    
    def _calculate_version_bump(
        self,
        skill: CrystallizedSkill,
        breaking: bool,
        improvements: List[str]
    ) -> Tuple[str, SkillVersion]:
        """Calculate new version based on changes."""
        if breaking:
            return "major", skill.version.bump_major()
        elif len(improvements) > 1:
            return "minor", skill.version.bump_minor()
        else:
            return "patch", skill.version.bump_patch()
    
    def _estimate_impact(self, skill: CrystallizedSkill, patterns: List[Dict]) -> float:
        """Estimate impact of evolution (0-1)."""
        if not patterns:
            return 0.0
        
        # Average success rate improvement
        avg_success = sum(p.get("success_rate", 0) for p in patterns) / len(patterns)
        success_improvement = max(0, avg_success - skill.success_rate)
        
        # Frequency weight
        total_frequency = sum(p.get("frequency", 1) for p in patterns)
        frequency_score = min(total_frequency / 10, 1.0)
        
        return (success_improvement * 0.6) + (frequency_score * 0.4)


class SkillGovernanceLifecycle:
    """
    Main orchestrator for skill governance.
    
    Manages the full pipeline:
    1. Collection: Patterns from Self-Honing → Draft Skills
    2. Recommendation: Context-aware skill suggestion
    3. Evolution: Skill improvement proposals
    """
    
    def __init__(self):
        self.registry = SkillRegistry()
        self.crystallizer = PatternCrystallizer(self.registry)
        self.recommendation_engine = SkillRecommendationEngine(self.registry)
        self.evolution_pipeline = SkillEvolutionPipeline(self.registry, self.crystallizer)
        
        # Validation gates
        self.validation_hooks: List[Callable[[CrystallizedSkill], bool]] = []
    
    def crystallize_pattern(self, pattern_data: Dict[str, Any]) -> Optional[CrystallizedSkill]:
        """
        Collection phase: Crystallize a pattern into a draft skill.
        """
        return self.crystallizer.crystallize(
            pattern_id=pattern_data["pattern_id"],
            pattern_type=pattern_data["pattern_type"],
            action_template=pattern_data["action_template"],
            frequency=pattern_data["frequency"],
            success_rate=pattern_data["success_rate"],
            source_trajectories=pattern_data["source_trajectories"],
            confidence=pattern_data["confidence"],
            preconditions=pattern_data.get("preconditions", {}),
            postconditions=pattern_data.get("postconditions", {}),
            parameter_slots=pattern_data.get("parameter_slots", [])
        )
    
    def validate_skill(self, skill_id: str, 
                       verification_result: SkillVerificationResult) -> bool:
        """
        Validation gate: Move skill from DRAFT → VALIDATED.
        """
        skill = self.registry.get(skill_id)
        if not skill or skill.lifecycle_stage != SkillLifecycleStage.DRAFT:
            return False
        
        skill.verification_result = verification_result
        
        if not verification_result.passed:
            self.registry.update_stage(skill_id, SkillLifecycleStage.BROKEN)
            return False
        
        # Run custom validation hooks
        for hook in self.validation_hooks:
            if not hook(skill):
                self.registry.update_stage(skill_id, SkillLifecycleStage.BROKEN)
                return False
        
        # Move to validated
        self.registry.update_stage(skill_id, SkillLifecycleStage.VALIDATED)
        return True
    
    def activate_skill(self, skill_id: str) -> bool:
        """
        Activation: Move skill from VALIDATED → ACTIVE.
        """
        skill = self.registry.get(skill_id)
        if not skill or skill.lifecycle_stage != SkillLifecycleStage.VALIDATED:
            return False
        
        # Ensure version is at least 1.0.0 for active skills
        if skill.version.major == 0:
            skill.version = SkillVersion(1, 0, 0)
        
        self.registry.update_stage(skill_id, SkillLifecycleStage.ACTIVE)
        return True
    
    def deprecate_skill(self, skill_id: str, reason: str = "") -> bool:
        """Deprecate a skill (scheduled for removal)."""
        skill = self.registry.get(skill_id)
        if not skill:
            return False
        
        skill.tags.add(f"deprecated:{reason}")
        return self.registry.update_stage(skill_id, SkillLifecycleStage.DEPRECATED)
    
    def recommend_skills(self, context: Dict[str, Any], 
                         top_k: int = 5) -> List[SkillRecommendation]:
        """
        Recommendation phase: Get context-aware skill recommendations.
        """
        return self.recommendation_engine.recommend(context, top_k=top_k)
    
    def propose_evolution(self, skill_id: str, 
                          new_patterns: List[Dict]) -> Optional[EvolutionProposal]:
        """
        Evolution phase: Propose skill improvements.
        """
        return self.evolution_pipeline.propose_evolution(skill_id, new_patterns)
    
    def record_execution(self, skill_id: str, success: bool, 
                         context: Dict[str, Any]) -> None:
        """
        Record skill execution outcome for learning.
        """
        skill = self.registry.get(skill_id)
        if skill:
            skill.usage_count += 1
            skill.last_used = time.time()
            if success:
                skill.success_count += 1
            else:
                skill.failure_count += 1
        
        self.recommendation_engine.record_usage(skill_id, success, context)
    
    def add_validation_hook(self, hook: Callable[[CrystallizedSkill], bool]) -> None:
        """Add custom validation hook."""
        self.validation_hooks.append(hook)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get governance statistics."""
        return {
            "registry": self.registry.get_statistics(),
            "crystallizations": len(self.crystallizer.crystallization_log),
            "proposals": len(self.evolution_pipeline.proposals)
        }


# Convenience functions
def create_skill_governance() -> SkillGovernanceLifecycle:
    """Create a skill governance lifecycle manager."""
    return SkillGovernanceLifecycle()


__all__ = [
    "SkillGovernanceLifecycle",
    "SkillRegistry",
    "PatternCrystallizer",
    "SkillRecommendationEngine",
    "SkillEvolutionPipeline",
    "CrystallizedSkill",
    "SkillRecommendation",
    "EvolutionProposal",
    "SkillLifecycleStage",
    "SkillType",
    "SkillVersion",
    "SkillVerificationResult",
    "PatternConfidence",
    "create_skill_governance"
]
