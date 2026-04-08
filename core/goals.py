"""
Goal Management System for AGI Agents.

Inspired by Open-Sable's goal-oriented architecture and research on:
- arXiv:2603.24621v1 (ARC-AGI-3): Agents must infer goals from environment
- arXiv:2603.28928v1: Goal definitions drive emergent social structures

Provides hierarchical goal management with:
1. Goal decomposition (breaking down complex goals)
2. Progress tracking with metrics
3. Conflict detection and resolution
4. Priority management (dynamic re-prioritization)
5. Goal relationships (dependencies, subgoals)
6. Temporal management (deadlines, scheduling)
"""

from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime, timedelta
import time
import json


class GoalStatus(Enum):
    """Lifecycle states for goals."""
    PENDING = auto()      # Created but not started
    ACTIVE = auto()       # Currently being pursued
    BLOCKED = auto()      # Waiting on dependencies or resources
    PAUSED = auto()       # Temporarily suspended
    COMPLETED = auto()    # Successfully achieved
    FAILED = auto()       # Failed after max attempts
    ABANDONED = auto()    # Explicitly cancelled


class GoalPriority(Enum):
    """Priority levels with numeric values for comparison."""
    CRITICAL = 5    # Must complete, blocks everything else
    HIGH = 4        # Important, should complete soon
    NORMAL = 3      # Standard priority
    LOW = 2         # Can be deferred
    BACKLOG = 1     # Nice to have


class ConflictType(Enum):
    """Types of goal conflicts."""
    RESOURCE = auto()     # Competing for same resources
    TEMPORAL = auto()     # Timing/deadline conflicts
    LOGICAL = auto()      # Mutually exclusive outcomes
    DEPENDENCY = auto()   # Circular or broken dependencies


@dataclass
class ProgressMetrics:
    """Quantifiable progress toward a goal."""
    percent_complete: float = 0.0  # 0.0 to 100.0
    subgoals_completed: int = 0
    subgoals_total: int = 0
    
    # Activity metrics
    attempts_made: int = 0
    attempts_max: int = 3  # Max retry attempts
    
    # Time tracking
    time_spent_seconds: float = 0.0
    time_estimated_seconds: float = 0.0
    
    # Quality metrics
    success_rate: float = 0.0  # For iterative goals
    error_count: int = 0
    last_error: Optional[str] = None
    
    def is_on_track(self) -> bool:
        """Check if progress is on track for completion."""
        if self.time_estimated_seconds <= 0:
            return self.percent_complete >= 0
        expected_progress = (self.time_spent_seconds / self.time_estimated_seconds) * 100
        return self.percent_complete >= expected_progress * 0.8  # 20% slack
    
    def can_retry(self) -> bool:
        """Check if more attempts are allowed."""
        return self.attempts_made < self.attempts_max
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "percent_complete": self.percent_complete,
            "subgoals_completed": self.subgoals_completed,
            "subgoals_total": self.subgoals_total,
            "attempts_made": self.attempts_made,
            "attempts_max": self.attempts_max,
            "time_spent_seconds": self.time_spent_seconds,
            "time_estimated_seconds": self.time_estimated_seconds,
            "success_rate": self.success_rate,
            "error_count": self.error_count,
            "last_error": self.last_error
        }


@dataclass
class Goal:
    """A goal the agent pursues."""
    id: str
    description: str
    status: GoalStatus = GoalStatus.PENDING
    priority: GoalPriority = GoalPriority.NORMAL
    
    # Hierarchy
    parent_id: Optional[str] = None
    subgoal_ids: List[str] = field(default_factory=list)
    
    # Dependencies
    depends_on: List[str] = field(default_factory=list)  # Goal IDs that must complete first
    blocks: List[str] = field(default_factory=list)    # Goals blocked until this completes
    
    # Temporal
    created_at: float = field(default_factory=time.time)
    deadline: Optional[float] = None  # Unix timestamp
    scheduled_start: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Progress
    metrics: ProgressMetrics = field(default_factory=ProgressMetrics)
    
    # Metadata
    tags: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Success criteria
    success_criteria: List[str] = field(default_factory=list)
    
    def is_overdue(self) -> bool:
        """Check if goal has passed deadline."""
        if self.deadline is None or self.status in [GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.ABANDONED]:
            return False
        return time.time() > self.deadline
    
    def time_remaining(self) -> Optional[float]:
        """Seconds until deadline, or None if no deadline."""
        if self.deadline is None:
            return None
        return max(0, self.deadline - time.time())
    
    def can_start(self, completed_goals: Set[str]) -> bool:
        """Check if all dependencies are satisfied."""
        return all(dep in completed_goals for dep in self.depends_on)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.name,
            "priority": self.priority.name,
            "priority_value": self.priority.value,
            "parent_id": self.parent_id,
            "subgoal_ids": self.subgoal_ids,
            "depends_on": self.depends_on,
            "blocks": self.blocks,
            "created_at": self.created_at,
            "deadline": self.deadline,
            "scheduled_start": self.scheduled_start,
            "completed_at": self.completed_at,
            "metrics": self.metrics.to_dict(),
            "tags": list(self.tags),
            "metadata": self.metadata,
            "success_criteria": self.success_criteria,
            "is_overdue": self.is_overdue(),
            "time_remaining": self.time_remaining()
        }


@dataclass
class Conflict:
    """A conflict between goals."""
    id: str
    type: ConflictType
    goal_ids: List[str]  # Goals involved in conflict
    description: str
    severity: float  # 0.0 to 1.0
    detected_at: float = field(default_factory=time.time)
    resolved: bool = False
    resolution: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.name,
            "goal_ids": self.goal_ids,
            "description": self.description,
            "severity": self.severity,
            "detected_at": self.detected_at,
            "resolved": self.resolved,
            "resolution": self.resolution
        }


class GoalManager:
    """
    Manages hierarchical goals with conflict detection and progress tracking.
    
    Key capabilities:
    - Hierarchical goal decomposition (parent/subgoals)
    - Dependency management (prerequisites, blocking)
    - Dynamic priority adjustment
    - Conflict detection (resource, temporal, logical)
    - Progress tracking with completion metrics
    """
    
    def __init__(self):
        self.goals: Dict[str, Goal] = {}
        self.conflicts: Dict[str, Conflict] = {}
        self.active_stack: List[str] = []  # Currently active goal hierarchy
        self.completed_ids: Set[str] = set()
        
        # Configuration
        self.max_active_goals = 5
        self.auto_detect_conflicts = True
        
        # Statistics
        self.stats = {
            "total_goals_created": 0,
            "total_goals_completed": 0,
            "total_goals_failed": 0,
            "total_conflicts_detected": 0,
            "total_conflicts_resolved": 0
        }
    
    def create_goal(
        self,
        description: str,
        priority: GoalPriority = GoalPriority.NORMAL,
        parent_id: Optional[str] = None,
        depends_on: Optional[List[str]] = None,
        deadline: Optional[datetime] = None,
        success_criteria: Optional[List[str]] = None,
        tags: Optional[Set[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Goal:
        """
        Create a new goal.
        
        Args:
            description: What the goal aims to achieve
            priority: Importance level
            parent_id: Parent goal for hierarchical organization
            depends_on: Prerequisites that must complete first
            deadline: When the goal must be completed
            success_criteria: Measurable conditions for success
            tags: Categorization labels
            metadata: Additional structured data
            
        Returns:
            The created Goal object
        """
        goal_id = f"goal_{int(time.time() * 1000)}_{len(self.goals)}"
        
        goal = Goal(
            id=goal_id,
            description=description,
            priority=priority,
            parent_id=parent_id,
            depends_on=depends_on or [],
            deadline=deadline.timestamp() if deadline else None,
            success_criteria=success_criteria or [],
            tags=tags or set(),
            metadata=metadata or {}
        )
        
        self.goals[goal_id] = goal
        self.stats["total_goals_created"] += 1
        
        # Update parent's subgoal list
        if parent_id and parent_id in self.goals:
            self.goals[parent_id].subgoal_ids.append(goal_id)
        
        # Check for conflicts with existing goals
        if self.auto_detect_conflicts:
            self._detect_conflicts_for_goal(goal)
        
        return goal
    
    def decompose_goal(
        self,
        parent_id: str,
        subgoal_descriptions: List[str],
        parallel: bool = True
    ) -> List[Goal]:
        """
        Break a goal into subgoals.
        
        Args:
            parent_id: Goal to decompose
            subgoal_descriptions: List of subgoal descriptions
            parallel: If True, subgoals have no inter-dependencies
            
        Returns:
            List of created subgoals
        """
        if parent_id not in self.goals:
            raise ValueError(f"Parent goal {parent_id} not found")
        
        parent = self.goals[parent_id]
        parent.metrics.subgoals_total = len(subgoal_descriptions)
        
        subgoals = []
        previous_id = None
        
        for i, desc in enumerate(subgoal_descriptions):
            # If not parallel, each subgoal depends on previous
            depends_on = []
            if not parallel and previous_id:
                depends_on = [previous_id]
            
            subgoal = self.create_goal(
                description=desc,
                priority=parent.priority,  # Inherit priority
                parent_id=parent_id,
                depends_on=depends_on,
                success_criteria=[f"Complete: {desc}"]
            )
            subgoals.append(subgoal)
            previous_id = subgoal.id
        
        return subgoals
    
    def start_goal(self, goal_id: str) -> bool:
        """
        Mark a goal as active and begin pursuit.
        
        Returns:
            True if goal was started, False if blocked
        """
        if goal_id not in self.goals:
            return False
        
        goal = self.goals[goal_id]
        
        # Check dependencies
        if not goal.can_start(self.completed_ids):
            missing = [dep for dep in goal.depends_on if dep not in self.completed_ids]
            goal.status = GoalStatus.BLOCKED
            goal.metadata["blocked_reason"] = f"Waiting on: {missing}"
            return False
        
        # Check if we're at max active goals
        active_count = sum(1 for g in self.goals.values() if g.status == GoalStatus.ACTIVE)
        if active_count >= self.max_active_goals:
            goal.status = GoalStatus.PAUSED
            goal.metadata["paused_reason"] = "Max active goals reached"
            return False
        
        goal.status = GoalStatus.ACTIVE
        goal.scheduled_start = time.time()
        
        # Push to active stack if there's a parent
        if goal.parent_id:
            self.active_stack.append(goal_id)
        
        return True
    
    def update_progress(
        self,
        goal_id: str,
        percent: Optional[float] = None,
        metrics_update: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update progress metrics for a goal."""
        if goal_id not in self.goals:
            return
        
        goal = self.goals[goal_id]
        
        if percent is not None:
            goal.metrics.percent_complete = max(0, min(100, percent))
        
        if metrics_update:
            for key, value in metrics_update.items():
                if hasattr(goal.metrics, key):
                    setattr(goal.metrics, key, value)
        
        # Check if all subgoals completed
        if goal.subgoal_ids:
            completed_subgoals = sum(
                1 for sid in goal.subgoal_ids
                if self.goals.get(sid, Goal("", "")).status == GoalStatus.COMPLETED
            )
            goal.metrics.subgoals_completed = completed_subgoals
            goal.metrics.percent_complete = (completed_subgoals / len(goal.subgoal_ids)) * 100
    
    def complete_goal(self, goal_id: str, success: bool = True) -> None:
        """Mark a goal as completed or failed."""
        if goal_id not in self.goals:
            return
        
        goal = self.goals[goal_id]
        
        if success:
            goal.status = GoalStatus.COMPLETED
            goal.metrics.percent_complete = 100.0
            self.stats["total_goals_completed"] += 1
            self.completed_ids.add(goal_id)
        else:
            goal.status = GoalStatus.FAILED
            self.stats["total_goals_failed"] += 1
        
        goal.completed_at = time.time()
        
        # Remove from active stack
        if goal_id in self.active_stack:
            self.active_stack.remove(goal_id)
        
        # Check if parent is now completable
        if goal.parent_id and goal.parent_id in self.goals:
            parent = self.goals[goal.parent_id]
            if all(
                self.goals.get(sid, Goal("", "")).status == GoalStatus.COMPLETED
                for sid in parent.subgoal_ids
            ):
                self.complete_goal(goal.parent_id, success=True)
        
        # Unblock dependent goals
        for blocked_id in goal.blocks:
            if blocked_id in self.goals:
                blocked = self.goals[blocked_id]
                if blocked.status == GoalStatus.BLOCKED:
                    # Check if still blocked by others
                    if blocked.can_start(self.completed_ids):
                        blocked.status = GoalStatus.PENDING
    
    def get_active_goals(self) -> List[Goal]:
        """Get all currently active goals."""
        return [g for g in self.goals.values() if g.status == GoalStatus.ACTIVE]
    
    def get_next_pending(self) -> Optional[Goal]:
        """Get the highest priority pending goal that can start."""
        pending = [
            g for g in self.goals.values()
            if g.status == GoalStatus.PENDING and g.can_start(self.completed_ids)
        ]
        
        if not pending:
            return None
        
        # Sort by priority (desc), then by deadline (asc)
        pending.sort(key=lambda g: (-g.priority.value, g.deadline or float('inf')))
        return pending[0]
    
    def prioritize(self, goal_id: str, new_priority: GoalPriority) -> None:
        """Change a goal's priority."""
        if goal_id in self.goals:
            self.goals[goal_id].priority = new_priority
    
    def _detect_conflicts_for_goal(self, goal: Goal) -> List[Conflict]:
        """Detect conflicts between a goal and existing goals."""
        conflicts = []
        
        for other in self.goals.values():
            if other.id == goal.id:
                continue
            
            # Check temporal conflicts (same deadline, both high priority)
            if (goal.deadline and other.deadline and 
                abs(goal.deadline - other.deadline) < 3600 and  # Within 1 hour
                goal.priority.value >= GoalPriority.HIGH.value and
                other.priority.value >= GoalPriority.HIGH.value):
                
                conflict = Conflict(
                    id=f"conflict_{int(time.time() * 1000)}",
                    type=ConflictType.TEMPORAL,
                    goal_ids=[goal.id, other.id],
                    description=f"Both goals have tight deadlines around the same time",
                    severity=0.7
                )
                self.conflicts[conflict.id] = conflict
                conflicts.append(conflict)
                self.stats["total_conflicts_detected"] += 1
            
            # Check logical conflicts (mutually exclusive tags)
            if goal.tags and other.tags:
                mutually_exclusive = [{"focus", "explore"}, {"build", "research"}]
                for me_set in mutually_exclusive:
                    if goal.tags & me_set and other.tags & me_set and goal.tags & me_set != other.tags & me_set:
                        conflict = Conflict(
                            id=f"conflict_{int(time.time() * 1000)}_2",
                            type=ConflictType.LOGICAL,
                            goal_ids=[goal.id, other.id],
                            description=f"Mutually exclusive approaches: {me_set}",
                            severity=0.6
                        )
                        self.conflicts[conflict.id] = conflict
                        conflicts.append(conflict)
                        self.stats["total_conflicts_detected"] += 1
        
        return conflicts
    
    def resolve_conflict(self, conflict_id: str, resolution: str) -> bool:
        """Mark a conflict as resolved with a resolution strategy."""
        if conflict_id not in self.conflicts:
            return False
        
        conflict = self.conflicts[conflict_id]
        conflict.resolved = True
        conflict.resolution = resolution
        self.stats["total_conflicts_resolved"] += 1
        
        # Apply resolution strategy
        if "prioritize" in resolution.lower():
            # Assume resolution mentions a goal ID to prioritize
            for goal_id in conflict.goal_ids:
                if goal_id in self.goals and goal_id in resolution:
                    self.prioritize(goal_id, GoalPriority.HIGH)
        elif "defer" in resolution.lower():
            # Defer one goal
            for goal_id in conflict.goal_ids:
                if goal_id in self.goals:
                    self.prioritize(goal_id, GoalPriority.LOW)
        
        return True
    
    def get_goal_tree(self, root_id: Optional[str] = None) -> Dict[str, Any]:
        """Get a hierarchical view of goals."""
        if root_id:
            root = self.goals.get(root_id)
            if not root:
                return {}
            return self._build_tree_node(root)
        
        # Get all root goals (no parent)
        roots = [g for g in self.goals.values() if g.parent_id is None]
        return {
            "roots": [self._build_tree_node(r) for r in roots],
            "stats": self.stats
        }
    
    def _build_tree_node(self, goal: Goal) -> Dict[str, Any]:
        """Recursively build goal tree."""
        node = goal.to_dict()
        node["subgoals"] = [
            self._build_tree_node(self.goals[sid])
            for sid in goal.subgoal_ids
            if sid in self.goals
        ]
        return node
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get summary of all goal statuses."""
        status_counts = {s.name: 0 for s in GoalStatus}
        priority_counts = {p.name: 0 for p in GoalPriority}
        
        for goal in self.goals.values():
            status_counts[goal.status.name] += 1
            priority_counts[goal.priority.name] += 1
        
        overdue_count = sum(1 for g in self.goals.values() if g.is_overdue())
        active_count = sum(1 for g in self.goals.values() if g.status == GoalStatus.ACTIVE)
        
        return {
            "by_status": status_counts,
            "by_priority": priority_counts,
            "total": len(self.goals),
            "overdue": overdue_count,
            "active": active_count,
            "completed": len(self.completed_ids),
            "completion_rate": len(self.completed_ids) / max(1, len(self.goals)),
            "stats": self.stats
        }
    
    def save(self, filepath: str) -> None:
        """Save all goals to a JSON file."""
        data = {
            "goals": {gid: g.to_dict() for gid, g in self.goals.items()},
            "conflicts": {cid: c.to_dict() for cid, c in self.conflicts.items()},
            "completed_ids": list(self.completed_ids),
            "stats": self.stats
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load(self, filepath: str) -> None:
        """Load goals from a JSON file."""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        # Reconstruct goals from dicts
        for gid, gdict in data.get("goals", {}).items():
            goal = Goal(
                id=gdict["id"],
                description=gdict["description"],
                status=GoalStatus[gdict["status"]],
                priority=GoalPriority[gdict["priority"]],
                parent_id=gdict.get("parent_id"),
                subgoal_ids=gdict.get("subgoal_ids", []),
                depends_on=gdict.get("depends_on", []),
                blocks=gdict.get("blocks", []),
                created_at=gdict.get("created_at", time.time()),
                deadline=gdict.get("deadline"),
                success_criteria=gdict.get("success_criteria", []),
                tags=set(gdict.get("tags", []))
            )
            self.goals[gid] = goal
        
        self.completed_ids = set(data.get("completed_ids", []))
        self.stats = data.get("stats", self.stats)


def demo():
    """Demonstrate goal management capabilities."""
    print("=" * 60)
    print("🎯 Goal Management System Demo")
    print("=" * 60)
    
    manager = GoalManager()
    
    # Create a complex project goal
    print("\n📋 Creating top-level research goal...")
    research_goal = manager.create_goal(
        description="Implement AGI research agent with goal management",
        priority=GoalPriority.HIGH,
        success_criteria=["System operational", "Tests passing", "Documentation complete"],
        tags={"research", "build"}
    )
    print(f"   Created: {research_goal.id}")
    
    # Decompose into subgoals
    print("\n🔨 Decomposing into subgoals...")
    subgoals = manager.decompose_goal(
        research_goal.id,
        [
            "Review latest AGI research papers",
            "Design goal hierarchy architecture",
            "Implement goal management system",
            "Write comprehensive tests",
            "Create documentation"
        ],
        parallel=False  # Sequential for this demo
    )
    print(f"   Created {len(subgoals)} subgoals")
    
    # Create a parallel exploratory goal
    print("\n🔍 Creating parallel exploration goal...")
    explore_goal = manager.create_goal(
        description="Explore multi-agent social dynamics research",
        priority=GoalPriority.NORMAL,
        tags={"explore", "research"}  # Note: "explore" vs "focus" - potential conflict!
    )
    
    # Check for conflicts
    print("\n⚠️  Conflict detection...")
    conflicts = manager._detect_conflicts_for_goal(explore_goal)
    if conflicts:
        print(f"   Detected {len(conflicts)} conflict(s)")
        for c in conflicts:
            print(f"   - {c.type.name}: {c.description}")
    
    # Start working on subgoals
    print("\n▶️  Starting work...")
    for sg in subgoals[:2]:  # Start first 2
        started = manager.start_goal(sg.id)
        status = "✅ Started" if started else "❌ Blocked"
        print(f"   {status}: {sg.description[:40]}...")
    
    # Update progress
    print("\n📊 Updating progress...")
    manager.update_progress(subgoals[0].id, percent=50.0)
    print(f"   Subgoal 1: 50% complete")
    
    # Complete first subgoal
    print("\n✅ Completing first subgoal...")
    manager.complete_goal(subgoals[0].id, success=True)
    
    # Now second subgoal should be unblocked
    print("\n🔄 Checking unblocked goals...")
    next_goal = manager.get_next_pending()
    if next_goal:
        print(f"   Next pending: {next_goal.description[:40]}...")
    
    # Summary
    print("\n" + "=" * 60)
    print("📈 Goal Tree Summary")
    print("=" * 60)
    tree = manager.get_goal_tree()
    for root in tree.get("roots", []):
        print(f"\n🎯 {root['description']}")
        print(f"   Status: {root['status']} | Progress: {root['metrics']['percent_complete']:.0f}%")
        for sg in root.get("subgoals", []):
            print(f"   └─ {sg['description'][:50]}... [{sg['status']}]")
    
    print("\n" + "=" * 60)
    print("📊 Status Summary")
    print("=" * 60)
    summary = manager.get_status_summary()
    for status, count in summary["by_status"].items():
        if count > 0:
            print(f"   {status}: {count}")
    print(f"\n   Completion rate: {summary['completion_rate']:.1%}")
    print(f"   Overdue goals: {summary['overdue']}")
    
    # Save/Load demo
    print("\n💾 Save/Load demo...")
    manager.save("/tmp/goals_demo.json")
    print("   Saved to /tmp/goals_demo.json")
    
    new_manager = GoalManager()
    new_manager.load("/tmp/goals_demo.json")
    print(f"   Loaded {len(new_manager.goals)} goals")


if __name__ == "__main__":
    demo()
