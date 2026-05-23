"""
Self-Honing Module - Inspired by ASH: Agents that Self-Hone via Embodied Learning
(arXiv:2605.14211v1)

Core concept: Self-improvement through:
1. Recording execution trajectories (episodes)
2. Extracting reusable patterns (Inverse Dynamics Model approach)
3. Identifying key moments from successful executions
4. Crystallizing learnings into skill updates

References:
- ASH: Agents that Self-Hone via Embodied Learning (arXiv:2605.14211v1)
- SkillsVote: Lifecycle Governance of Agent Skills (arXiv:2605.18401v1)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Set
from enum import Enum
import json
import hashlib
import time
from collections import defaultdict


class TrajectoryType(Enum):
    """Types of execution trajectories"""
    TASK_COMPLETION = "task_completion"
    TOOL_EXECUTION = "tool_execution"
    RECOVERY = "recovery"
    EXPLORATION = "exploration"


class MomentImportance(Enum):
    """Importance level of key moments"""
    CRITICAL = 1.0    # Success/failure turning points
    HIGH = 0.8        # Significant state changes
    MEDIUM = 0.5      # Useful patterns
    LOW = 0.2         # Background context


@dataclass
class KeyMoment:
    """
    Key moment identified from trajectory (like ASH's unsupervised moment identification)
    """
    moment_id: str
    timestamp: float
    trajectory_id: str
    step_number: int
    state_before: Dict[str, Any]
    action_taken: str
    state_after: Dict[str, Any]
    outcome: str  # "success", "failure", "neutral"
    importance: MomentImportance
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "moment_id": self.moment_id,
            "timestamp": self.timestamp,
            "trajectory_id": self.trajectory_id,
            "step_number": self.step_number,
            "state_before": self.state_before,
            "action_taken": self.action_taken,
            "state_after": self.state_after,
            "outcome": self.outcome,
            "importance": self.importance.value,
            "context": self.context
        }


@dataclass
class ExecutionTrajectory:
    """
    Complete execution trace (episode) for learning
    Similar to ASH's trajectories for IDM training
    """
    trajectory_id: str
    task_description: str
    trajectory_type: TrajectoryType
    start_time: float
    end_time: Optional[float] = None
    steps: List[Dict[str, Any]] = field(default_factory=list)
    outcome: Optional[str] = None  # "success", "failure", "abandoned"
    key_moments: List[KeyMoment] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration(self) -> float:
        if self.end_time:
            return self.end_time - self.start_time
        return 0.0
    
    @property
    def step_count(self) -> int:
        return len(self.steps)
    
    def add_step(self, action: str, observation: Dict[str, Any], 
                 state: Dict[str, Any]) -> None:
        """Add execution step to trajectory"""
        self.steps.append({
            "step_number": len(self.steps) + 1,
            "action": action,
            "observation": observation,
            "state": state,
            "timestamp": time.time()
        })
    
    def complete(self, outcome: str, metadata: Optional[Dict] = None) -> None:
        """Mark trajectory as complete"""
        self.end_time = time.time()
        self.outcome = outcome
        if metadata:
            self.metadata.update(metadata)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "trajectory_id": self.trajectory_id,
            "task_description": self.task_description,
            "trajectory_type": self.trajectory_type.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "step_count": self.step_count,
            "outcome": self.outcome,
            "steps": self.steps,
            "key_moments": [km.to_dict() for km in self.key_moments],
            "metadata": self.metadata
        }


@dataclass
class ExtractedPattern:
    """
    Reusable pattern extracted from trajectories
    Analogous to IDM-extracted supervision from ASH
    """
    pattern_id: str
    pattern_type: str  # "action_sequence", "recovery_strategy", "state_transition"
    source_trajectories: List[str]
    frequency: int
    success_rate: float
    action_template: List[str]
    preconditions: Dict[str, Any]
    postconditions: Dict[str, Any]
    parameter_slots: List[str]
    confidence: float
    extracted_at: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type,
            "source_trajectories": self.source_trajectories,
            "frequency": self.frequency,
            "success_rate": self.success_rate,
            "action_template": self.action_template,
            "preconditions": self.preconditions,
            "postconditions": self.postconditions,
            "parameter_slots": self.parameter_slots,
            "confidence": self.confidence,
            "extracted_at": self.extracted_at
        }


class TrajectoryStore:
    """Storage for execution trajectories with indexing"""
    
    def __init__(self):
        self.trajectories: Dict[str, ExecutionTrajectory] = {}
        self.by_type: Dict[TrajectoryType, List[str]] = defaultdict(list)
        self.by_outcome: Dict[str, List[str]] = defaultdict(list)
        self.by_task: Dict[str, List[str]] = defaultdict(list)
    
    def store(self, trajectory: ExecutionTrajectory) -> None:
        """Store a trajectory"""
        self.trajectories[trajectory.trajectory_id] = trajectory
        self.by_type[trajectory.trajectory_type].append(trajectory.trajectory_id)
        if trajectory.outcome:
            self.by_outcome[trajectory.outcome].append(trajectory.trajectory_id)
        self.by_task[trajectory.task_description].append(trajectory.trajectory_id)
    
    def get(self, trajectory_id: str) -> Optional[ExecutionTrajectory]:
        return self.trajectories.get(trajectory_id)
    
    def get_by_type(self, ttype: TrajectoryType) -> List[ExecutionTrajectory]:
        return [self.trajectories[tid] for tid in self.by_type[ttype]]
    
    def get_successful(self) -> List[ExecutionTrajectory]:
        return [self.trajectories[tid] for tid in self.by_outcome.get("success", [])]
    
    def get_by_task_pattern(self, pattern: str) -> List[ExecutionTrajectory]:
        """Get trajectories matching task description pattern"""
        results = []
        pattern_lower = pattern.lower()
        for task, tids in self.by_task.items():
            if pattern_lower in task.lower():
                results.extend([self.trajectories[tid] for tid in tids])
        return results


class KeyMomentIdentifier:
    """
    Identifies key moments from trajectories (ASH-style unsupervised identification)
    """
    
    def __init__(self):
        self.importance_thresholds = {
            "state_change_magnitude": 0.7,
            "outcome_transition": 0.9,
            "tool_success": 0.8,
            "error_recovery": 0.85
        }
    
    def identify_moments(self, trajectory: ExecutionTrajectory) -> List[KeyMoment]:
        """Extract key moments from a completed trajectory"""
        moments = []
        
        if not trajectory.steps:
            return moments
        
        # Identify outcome transitions (success/failure turning points)
        moments.extend(self._find_outcome_transitions(trajectory))
        
        # Identify significant state changes
        moments.extend(self._find_state_changes(trajectory))
        
        # Identify tool execution successes/failures
        moments.extend(self._find_tool_moments(trajectory))
        
        # Identify recovery patterns
        moments.extend(self._find_recovery_moments(trajectory))
        
        # Deduplicate by step number, keeping highest importance
        moments_by_step = {}
        for moment in moments:
            existing = moments_by_step.get(moment.step_number)
            if not existing:
                moments_by_step[moment.step_number] = moment
            elif moment.importance.value > existing.importance.value:
                # New moment has higher importance - keep it but merge contexts
                merged_context = {**existing.context, **moment.context}
                moment.context = merged_context
                moments_by_step[moment.step_number] = moment
            else:
                # Existing moment has higher or equal importance - merge context into it
                merged_context = {**existing.context, **moment.context}
                existing.context = merged_context
        
        return list(moments_by_step.values())
    
    def _find_outcome_transitions(self, trajectory: ExecutionTrajectory) -> List[KeyMoment]:
        """Find moments where outcome changed significantly"""
        moments = []
        
        # Check final outcome
        if trajectory.outcome == "success":
            # Last step is critical
            if trajectory.steps:
                last_step = trajectory.steps[-1]
                moment = KeyMoment(
                    moment_id=self._generate_id(f"{trajectory.trajectory_id}_outcome"),
                    timestamp=last_step["timestamp"],
                    trajectory_id=trajectory.trajectory_id,
                    step_number=last_step["step_number"],
                    state_before=trajectory.steps[-2]["state"] if len(trajectory.steps) > 1 else {},
                    action_taken=last_step["action"],
                    state_after=last_step["state"],
                    outcome="success",
                    importance=MomentImportance.CRITICAL,
                    context={"type": "task_completion"}
                )
                moments.append(moment)
        
        return moments
    
    def _find_state_changes(self, trajectory: ExecutionTrajectory) -> List[KeyMoment]:
        """Find significant state changes"""
        moments = []
        
        for i, step in enumerate(trajectory.steps):
            if i == 0:
                continue
            
            prev_state = trajectory.steps[i-1]["state"]
            curr_state = step["state"]
            
            # Calculate state change magnitude
            change_score = self._calculate_state_change(prev_state, curr_state)
            
            # Lower threshold to ensure we catch meaningful changes
            threshold = self.importance_thresholds["state_change_magnitude"]
            if change_score >= threshold:
                importance = MomentImportance.HIGH if change_score > 0.9 else MomentImportance.MEDIUM
                moment = KeyMoment(
                    moment_id=self._generate_id(f"{trajectory.trajectory_id}_state_{i}"),
                    timestamp=step["timestamp"],
                    trajectory_id=trajectory.trajectory_id,
                    step_number=step["step_number"],
                    state_before=prev_state,
                    action_taken=step["action"],
                    state_after=curr_state,
                    outcome="neutral",
                    importance=importance,
                    context={"state_change_score": change_score}
                )
                moments.append(moment)
        
        return moments
    
    def _find_tool_moments(self, trajectory: ExecutionTrajectory) -> List[KeyMoment]:
        """Find important tool execution moments"""
        moments = []
        
        for step in trajectory.steps:
            action = step["action"]
            obs = step.get("observation", {})
            
            # Check if this is a tool execution (multiple indicators)
            is_tool = (
                "tool" in action.lower() or
                "tool_used" in obs or
                obs.get("tool_used") is not None
            )
            
            if is_tool:
                success = obs.get("success", False)
                importance = MomentImportance.HIGH if success else MomentImportance.CRITICAL
                
                moment = KeyMoment(
                    moment_id=self._generate_id(f"{trajectory.trajectory_id}_tool_{step['step_number']}"),
                    timestamp=step["timestamp"],
                    trajectory_id=trajectory.trajectory_id,
                    step_number=step["step_number"],
                    state_before={},
                    action_taken=action,
                    state_after={},
                    outcome="success" if success else "failure",
                    importance=importance,
                    context={"tool_execution": True, "tool_result": obs}
                )
                moments.append(moment)
        
        return moments
    
    def _find_recovery_moments(self, trajectory: ExecutionTrajectory) -> List[KeyMoment]:
        """Find error recovery moments"""
        moments = []
        
        prev_failed = False
        prev_action = None
        for step in trajectory.steps:
            obs = step.get("observation", {})
            success = obs.get("success", True)
            
            if not success:
                prev_failed = True
                prev_action = step["action"]
            elif prev_failed:
                # Recovery moment - previous action failed, this one succeeded
                moment = KeyMoment(
                    moment_id=self._generate_id(f"{trajectory.trajectory_id}_recovery_{step['step_number']}"),
                    timestamp=step["timestamp"],
                    trajectory_id=trajectory.trajectory_id,
                    step_number=step["step_number"],
                    state_before={},
                    action_taken=step["action"],
                    state_after={},
                    outcome="success",
                    importance=MomentImportance.HIGH,
                    context={"recovery": True, "recovered_from": prev_action}
                )
                moments.append(moment)
                prev_failed = False
        
        return moments
    
    def _calculate_state_change(self, before: Dict, after: Dict) -> float:
        """Calculate magnitude of state change"""
        if not before and not after:
            return 0.0
        
        # Handle empty cases
        if not before or not after:
            # All keys are new or removed - maximum change
            non_empty = after if after else before
            return 1.0 if non_empty else 0.0
        
        # All keys from both states
        all_keys = set(before.keys()) | set(after.keys())
        if not all_keys:
            return 0.0
        
        # Count changes (including additions and removals)
        changed = 0
        for k in all_keys:
            if before.get(k) != after.get(k):
                changed += 1
        
        return changed / len(all_keys)
    
    def _generate_id(self, seed: str) -> str:
        return hashlib.md5(seed.encode()).hexdigest()[:16]


class PatternExtractor:
    """
    Extract reusable patterns from trajectories (IDM-like extraction)
    """
    
    def __init__(self):
        self.min_pattern_frequency = 2
        self.min_success_rate = 0.6
    
    def extract_patterns(self, trajectories: List[ExecutionTrajectory]) -> List[ExtractedPattern]:
        """Extract patterns from multiple trajectories"""
        patterns = []
        
        # Extract action sequence patterns
        seq_patterns = self._extract_sequence_patterns(trajectories)
        patterns.extend(seq_patterns)
        
        # Extract recovery patterns
        recovery_patterns = self._extract_recovery_patterns(trajectories)
        patterns.extend(recovery_patterns)
        
        # Extract state transition patterns
        transition_patterns = self._extract_transition_patterns(trajectories)
        patterns.extend(transition_patterns)
        
        return patterns
    
    def _extract_sequence_patterns(self, trajectories: List[ExecutionTrajectory]) -> List[ExtractedPattern]:
        """Extract common action sequences"""
        # Group trajectories by task similarity
        task_groups = defaultdict(list)
        for traj in trajectories:
            task_groups[traj.task_description].append(traj)
        
        patterns = []
        for task, task_trajs in task_groups.items():
            if len(task_trajs) < self.min_pattern_frequency:
                continue
            
            # Find common prefix
            common_prefix = self._find_common_prefix([t.steps for t in task_trajs])
            
            if len(common_prefix) >= 2:
                successful = [t for t in task_trajs if t.outcome == "success"]
                success_rate = len(successful) / len(task_trajs)
                
                if success_rate >= self.min_success_rate:
                    pattern = ExtractedPattern(
                        pattern_id=self._generate_pattern_id("sequence", task),
                        pattern_type="action_sequence",
                        source_trajectories=[t.trajectory_id for t in task_trajs],
                        frequency=len(task_trajs),
                        success_rate=success_rate,
                        action_template=[s["action"] for s in common_prefix],
                        preconditions={},
                        postconditions={},
                        parameter_slots=self._extract_parameters(common_prefix),
                        confidence=success_rate * min(1.0, len(task_trajs) / 10),
                        extracted_at=time.time()
                    )
                    patterns.append(pattern)
        
        return patterns
    
    def _extract_recovery_patterns(self, trajectories: List[ExecutionTrajectory]) -> List[ExtractedPattern]:
        """Extract error recovery patterns from key moments"""
        patterns = []
        
        # Collect all recovery moments
        recovery_moments = []
        for traj in trajectories:
            for moment in traj.key_moments:
                if moment.context.get("recovery"):
                    recovery_moments.append((traj, moment))
        
        # Group by action taken
        by_action = defaultdict(list)
        for traj, moment in recovery_moments:
            by_action[moment.action_taken].append((traj, moment))
        
        for action, moments in by_action.items():
            if len(moments) >= self.min_pattern_frequency:
                pattern = ExtractedPattern(
                    pattern_id=self._generate_pattern_id("recovery", action),
                    pattern_type="recovery_strategy",
                    source_trajectories=[m[0].trajectory_id for m in moments],
                    frequency=len(moments),
                    success_rate=1.0,  # All were successful recoveries
                    action_template=[action],
                    preconditions={"preceding_failure": True},
                    postconditions={"recovered": True},
                    parameter_slots=[],
                    confidence=min(1.0, len(moments) / 5),
                    extracted_at=time.time()
                )
                patterns.append(pattern)
        
        return patterns
    
    def _extract_transition_patterns(self, trajectories: List[ExecutionTrajectory]) -> List[ExtractedPattern]:
        """Extract state transition patterns"""
        patterns = []
        
        # Collect transitions from key moments
        transitions = []
        for traj in trajectories:
            for moment in traj.key_moments:
                if moment.importance in [MomentImportance.HIGH, MomentImportance.CRITICAL]:
                    transition_key = (
                        tuple(sorted(moment.state_before.items())),
                        moment.action_taken,
                        tuple(sorted(moment.state_after.items()))
                    )
                    transitions.append((traj, moment, transition_key))
        
        # Group by transition key
        by_transition = defaultdict(list)
        for traj, moment, key in transitions:
            by_transition[key].append((traj, moment))
        
        for transition_key, moments in by_transition.items():
            if len(moments) >= self.min_pattern_frequency:
                before_state = dict(transition_key[0])
                action = transition_key[1]
                after_state = dict(transition_key[2])
                
                successful = [m for m in moments if m[1].outcome == "success"]
                success_rate = len(successful) / len(moments)
                
                pattern = ExtractedPattern(
                    pattern_id=self._generate_pattern_id("transition", action),
                    pattern_type="state_transition",
                    source_trajectories=[m[0].trajectory_id for m in moments],
                    frequency=len(moments),
                    success_rate=success_rate,
                    action_template=[action],
                    preconditions=before_state,
                    postconditions=after_state,
                    parameter_slots=[],
                    confidence=success_rate * min(1.0, len(moments) / 5),
                    extracted_at=time.time()
                )
                patterns.append(pattern)
        
        return patterns
    
    def _find_common_prefix(self, step_lists: List[List[Dict]]) -> List[Dict]:
        """Find common prefix of action sequences"""
        if not step_lists:
            return []
        
        prefix = []
        min_len = min(len(steps) for steps in step_lists)
        
        for i in range(min_len):
            action = step_lists[0][i]["action"]
            if all(steps[i]["action"] == action for steps in step_lists):
                prefix.append(step_lists[0][i])
            else:
                break
        
        return prefix
    
    def _extract_parameters(self, steps: List[Dict]) -> List[str]:
        """Extract parameter slots from steps"""
        params = set()
        for step in steps:
            action = step["action"]
            # Find variable parts in action strings
            if ":" in action:
                params.add("query")
            if "{" in action:
                params.add("template_param")
        return list(params)
    
    def _generate_pattern_id(self, ptype: str, seed: str) -> str:
        return f"{ptype}_{hashlib.md5(seed.encode()).hexdigest()[:12]}"


class SelfHoningEngine:
    """
    Main self-honing engine implementing ASH-style learning loop:
    1. Record trajectories during execution
    2. Identify key moments (unsupervised)
    3. Extract patterns (IDM-like)
    4. Update skills based on patterns
    """
    
    def __init__(
        self,
        skill_crystallizer: Optional[Any] = None,
        min_patterns_before_update: int = 3
    ):
        self.trajectory_store = TrajectoryStore()
        self.moment_identifier = KeyMomentIdentifier()
        self.pattern_extractor = PatternExtractor()
        self.skill_crystallizer = skill_crystallizer
        self.min_patterns_before_update = min_patterns_before_update
        
        self.active_trajectory: Optional[ExecutionTrajectory] = None
        self.extracted_patterns: List[ExtractedPattern] = []
        self.honing_stats = {
            "trajectories_recorded": 0,
            "patterns_extracted": 0,
            "skills_updated": 0,
            "last_honing": None
        }
    
    def start_trajectory(self, task_description: str, 
                         trajectory_type: TrajectoryType = TrajectoryType.TASK_COMPLETION,
                         metadata: Optional[Dict] = None) -> str:
        """Start recording a new execution trajectory"""
        trajectory_id = self._generate_trajectory_id()
        
        self.active_trajectory = ExecutionTrajectory(
            trajectory_id=trajectory_id,
            task_description=task_description,
            trajectory_type=trajectory_type,
            start_time=time.time(),
            metadata=metadata or {}
        )
        
        return trajectory_id
    
    def record_step(self, action: str, observation: Dict[str, Any],
                   state: Dict[str, Any]) -> None:
        """Record a step in the active trajectory"""
        if self.active_trajectory:
            self.active_trajectory.add_step(action, observation, state)
    
    def complete_trajectory(self, outcome: str, 
                           metadata: Optional[Dict] = None) -> ExecutionTrajectory:
        """Complete and store the active trajectory"""
        if not self.active_trajectory:
            raise ValueError("No active trajectory to complete")
        
        self.active_trajectory.complete(outcome, metadata)
        
        # Identify key moments
        moments = self.moment_identifier.identify_moments(self.active_trajectory)
        self.active_trajectory.key_moments = moments
        
        # Store trajectory
        self.trajectory_store.store(self.active_trajectory)
        self.honing_stats["trajectories_recorded"] += 1
        
        completed = self.active_trajectory
        self.active_trajectory = None
        
        return completed
    
    def hone(self) -> Dict[str, Any]:
        """
        Execute self-honing: extract patterns and update skills
        Returns summary of honing activity
        """
        # Get successful trajectories
        successful = self.trajectory_store.get_successful()
        
        if len(successful) < 2:
            return {"status": "insufficient_data", "message": "Need more successful trajectories"}
        
        # Extract patterns
        new_patterns = self.pattern_extractor.extract_patterns(successful)
        self.extracted_patterns.extend(new_patterns)
        self.honing_stats["patterns_extracted"] += len(new_patterns)
        
        # Update skills if crystallizer available
        skills_updated = 0
        if self.skill_crystallizer and len(self.extracted_patterns) >= self.min_patterns_before_update:
            skills_updated = self._update_skills_from_patterns(new_patterns)
        
        self.honing_stats["skills_updated"] += skills_updated
        self.honing_stats["last_honing"] = time.time()
        
        return {
            "status": "success",
            "patterns_extracted": len(new_patterns),
            "total_patterns": len(self.extracted_patterns),
            "skills_updated": skills_updated,
            "trajectories_analyzed": len(successful)
        }
    
    def _update_skills_from_patterns(self, patterns: List[ExtractedPattern]) -> int:
        """Update skills based on extracted patterns"""
        updated = 0
        
        for pattern in patterns:
            # Only high-confidence patterns
            if pattern.confidence < 0.7:
                continue
            
            # Convert pattern to skill update
            if self._apply_pattern_to_skill(pattern):
                updated += 1
        
        return updated
    
    def _apply_pattern_to_skill(self, pattern: ExtractedPattern) -> bool:
        """Apply an extracted pattern to improve a skill"""
        # This would integrate with skill_crystallizer
        # For now, record the pattern for later skill creation
        return True
    
    def get_learned_patterns(self, pattern_type: Optional[str] = None) -> List[ExtractedPattern]:
        """Get learned patterns, optionally filtered by type"""
        if pattern_type:
            return [p for p in self.extracted_patterns if p.pattern_type == pattern_type]
        return self.extracted_patterns
    
    def get_improvement_suggestions(self) -> List[Dict[str, Any]]:
        """Generate skill improvement suggestions from patterns"""
        suggestions = []
        
        for pattern in self.extracted_patterns:
            if pattern.confidence >= 0.8 and pattern.success_rate >= 0.8:
                suggestions.append({
                    "type": "reliable_pattern",
                    "pattern_id": pattern.pattern_id,
                    "description": f"Reliable {pattern.pattern_type} pattern with {pattern.success_rate:.0%} success rate",
                    "action_template": pattern.action_template,
                    "confidence": pattern.confidence,
                    "recommendation": "Consider crystallizing into skill"
                })
        
        return suggestions
    
    def get_stats(self) -> Dict[str, Any]:
        """Get self-honing statistics"""
        return {
            **self.honing_stats,
            "stored_trajectories": len(self.trajectory_store.trajectories),
            "extracted_patterns": len(self.extracted_patterns),
            "active_recording": self.active_trajectory is not None
        }
    
    def _generate_trajectory_id(self) -> str:
        return f"traj_{int(time.time())}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"


# Convenience functions
def create_self_honing_engine(skill_crystallizer: Optional[Any] = None) -> SelfHoningEngine:
    """Create a self-honing engine"""
    return SelfHoningEngine(skill_crystallizer=skill_crystallizer)


__all__ = [
    "SelfHoningEngine",
    "TrajectoryStore",
    "KeyMomentIdentifier",
    "PatternExtractor",
    "ExecutionTrajectory",
    "KeyMoment",
    "ExtractedPattern",
    "TrajectoryType",
    "MomentImportance",
    "create_self_honing_engine"
]
