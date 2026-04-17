"""
Integrated Agent System - Self-Improving Closed Loop

Connects reflection, planning, and memory modules to enable:
- Performance-informed planning strategies
- Reflection reports stored in tiered memory
- Execute → Reflect → Plan → Improve cycle

Based on research insights:
- SMGI: Coupled structural dynamics (θ, T_θ)
- Self-Evolving Agent: Evolution through execution feedback
- Ouroboros: Self-modifying with constitutional safety
- Active Inference: Minimize expected free energy through action-perception loops
"""

from typing import Dict, List, Any, Optional, Callable, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum, auto
from datetime import datetime
import json
import time
import uuid

from .planner import HierarchicalPlanner, Plan, SubTask, TaskType, PlanStatus, ResourceBudget
from .reflection import (
    ReflectionEngine, PerformanceRecord, CapabilityAssessment,
    ImprovementGoal, ProposedChange, ReflectionScope, ChangeStatus
)
from .tiered_memory import TieredMemorySystem, MemoryTier, MemoryEntry


class ExecutionPhase(Enum):
    """Phases of the integrated execution cycle."""
    PLANNING = auto()
    EXECUTING = auto()
    REFLECTING = auto()
    LEARNING = auto()
    IMPROVING = auto()


@dataclass
class ExecutionCycle:
    """A complete execution-reflection-learning cycle."""
    cycle_id: str
    goal: str
    plan_id: Optional[str] = None
    
    # Phase tracking
    phase: ExecutionPhase = field(default=ExecutionPhase.PLANNING)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    # Execution metrics
    tasks_executed: int = 0
    tasks_succeeded: int = 0
    tasks_failed: int = 0
    total_execution_time_ms: float = 0.0
    
    # Reflection insights
    performance_summary: Optional[Dict] = None
    capability_updates: List[str] = field(default_factory=list)
    improvement_goals_created: List[str] = field(default_factory=list)
    
    # Memory references
    memory_context_id: Optional[str] = None
    reflection_report_id: Optional[str] = None


@dataclass
class StrategyAdaptation:
    """Adaptive planning strategy based on performance data."""
    task_type: str
    current_strategy: str
    success_rate: float
    avg_execution_time: float
    
    # Adaptive parameters
    decomposition_depth: int  # Adjust based on failure patterns
    exploration_budget_multiplier: float  # Increase for uncertain tasks
    retry_threshold: int  # Max retries before escalation
    
    # Strategy effectiveness tracking
    adaptations_applied: List[Dict] = field(default_factory=list)


class IntegratedAgent:
    """
    Self-improving agent integrating planning, reflection, and memory.
    
    Implements the closed loop: Execute → Reflect → Plan → Improve
    """
    
    def __init__(
        self,
        agent_id: str = "default",
        planner: Optional[HierarchicalPlanner] = None,
        reflection: Optional[ReflectionEngine] = None,
        memory: Optional[TieredMemorySystem] = None
    ):
        self.agent_id = agent_id
        
        # Core components
        self.planner = planner or HierarchicalPlanner(max_depth=4)
        self.reflection = reflection or ReflectionEngine(agent_id=agent_id)
        self.memory = memory or TieredMemorySystem()
        
        # Execution state
        self.active_cycles: Dict[str, ExecutionCycle] = {}
        self.completed_cycles: List[ExecutionCycle] = []
        self.strategy_adaptations: Dict[str, StrategyAdaptation] = {}
        
        # Configuration
        self.max_cycles_in_memory = 50
        self.min_samples_for_adaptation = 10
        self.reflection_interval = 5  # Reflect every N tasks
        
    # ============ Core Execution Loop ============
    
    def execute_goal(
        self,
        goal: str,
        execute_fn: Callable[[SubTask], Tuple[bool, Any]],
        budget: Optional[ResourceBudget] = None,
        context: Optional[Dict] = None
    ) -> ExecutionCycle:
        """
        Execute a complete goal through the integrated loop.
        
        Flow:
        1. Plan with performance-informed strategy
        2. Execute with real-time reflection recording
        3. Reflect on execution patterns
        4. Store learnings in tiered memory
        5. Adapt strategies for future planning
        """
        # Start new cycle
        cycle = ExecutionCycle(
            cycle_id=f"cycle_{int(time.time())}_{uuid.uuid4().hex[:8]}",
            goal=goal
        )
        self.active_cycles[cycle.cycle_id] = cycle
        
        try:
            # Phase 1: Planning with reflection-informed strategy
            cycle.phase = ExecutionPhase.PLANNING
            plan = self._create_informed_plan(goal, context or {}, budget)
            cycle.plan_id = plan.plan_id
            
            # Phase 2: Execution with real-time reflection
            cycle.phase = ExecutionPhase.EXECUTING
            self._execute_plan_with_reflection(plan, execute_fn, cycle)
            
            # Phase 3: Reflection on cycle performance
            cycle.phase = ExecutionPhase.REFLECTING
            self._reflect_on_cycle(cycle)
            
            # Phase 4: Store learnings in memory
            cycle.phase = ExecutionPhase.LEARNING
            self._store_cycle_memory(cycle, plan)
            
            # Phase 5: Strategy adaptation
            cycle.phase = ExecutionPhase.IMPROVING
            self._adapt_strategies_from_cycle(cycle)
            
            cycle.completed_at = datetime.now()
            self.completed_cycles.append(cycle)
            
            return cycle
            
        finally:
            del self.active_cycles[cycle.cycle_id]
    
    def _create_informed_plan(
        self,
        goal: str,
        context: Dict[str, Any],
        budget: Optional[ResourceBudget]
    ) -> Plan:
        """Create plan with performance-informed strategy adaptations."""
        # Analyze goal type
        task_type = self.planner.decomposition_strategy.analyze_task_type(goal, context)
        
        # Apply strategy adaptations if available
        type_key = task_type.name
        if type_key in self.strategy_adaptations:
            adaptation = self.strategy_adaptations[type_key]
            
            # Adjust planner parameters based on adaptation
            if adaptation.success_rate < 0.5:
                # Low success: increase depth and exploration budget
                self.planner.max_depth = min(6, adaptation.decomposition_depth + 1)
                budget = budget or ResourceBudget()
                budget.max_iterations = int(budget.max_iterations * adaptation.exploration_budget_multiplier)
            elif adaptation.success_rate > 0.9:
                # High success: can simplify
                self.planner.max_depth = max(3, adaptation.decomposition_depth - 1)
        
        # Create the plan
        return self.planner.create_plan(goal, budget, context)
    
    def _execute_plan_with_reflection(
        self,
        plan: Plan,
        execute_fn: Callable[[SubTask], Tuple[bool, Any]],
        cycle: ExecutionCycle
    ):
        """Execute plan while recording performance for reflection."""
        execution_log: List[Dict] = []
        
        while not self.planner.is_plan_complete(plan):
            # Check budget
            if plan.budget.is_exhausted():
                break
            
            # Get next executable task
            task = self.planner.get_next_executable_task(plan)
            if not task:
                break
            
            # Execute with timing
            start_time = time.time()
            success, output = execute_fn(task)
            execution_time_ms = (time.time() - start_time) * 1000
            
            # Update cycle metrics
            cycle.tasks_executed += 1
            cycle.total_execution_time_ms += execution_time_ms
            if success:
                cycle.tasks_succeeded += 1
            else:
                cycle.tasks_failed += 1
            
            # Determine task type for reflection categorization
            task_type = self._categorize_task_type(task)
            
            # Record performance for reflection
            quality_score = self._estimate_quality_score(success, output, execution_time_ms)
            error_type = self._classify_error(output) if not success else None
            
            record = PerformanceRecord(
                task_id=task.task_id,
                task_type=task_type,
                success=success,
                execution_time_ms=execution_time_ms,
                quality_score=quality_score,
                error_type=error_type,
                metadata={
                    'plan_id': plan.plan_id,
                    'cycle_id': cycle.cycle_id,
                    'task_description': task.description[:100]
                }
            )
            
            self.reflection.record_performance(record)
            
            # Log execution
            execution_log.append({
                'task_id': task.task_id,
                'success': success,
                'execution_time_ms': execution_time_ms,
                'quality_score': quality_score
            })
            
            # Periodic reflection during long executions
            if cycle.tasks_executed % self.reflection_interval == 0:
                self._mid_execution_reflection(cycle, execution_log)
    
    def _categorize_task_type(self, task: SubTask) -> str:
        """Categorize task for performance tracking."""
        if task.task_type == TaskType.EXPLORATORY:
            return "exploratory_task"
        elif task.task_type == TaskType.SEQUENTIAL:
            return "sequential_task"
        elif task.task_type == TaskType.PARALLEL:
            return "parallel_task"
        elif task.task_type == TaskType.ATOMIC:
            return "atomic_task"
        else:
            return f"task_{task.task_type.name.lower()}"
    
    def _estimate_quality_score(
        self,
        success: bool,
        output: Any,
        execution_time_ms: float
    ) -> float:
        """Estimate quality score based on success and output characteristics."""
        if not success:
            return 0.0
        
        # Base score for success
        score = 0.7
        
        # Bonus for reasonable execution time (< 1 second)
        if execution_time_ms < 1000:
            score += 0.2
        elif execution_time_ms < 5000:
            score += 0.1
        
        # Check output validity
        if output and not (isinstance(output, str) and len(output) < 10):
            score += 0.1
        
        return min(1.0, score)
    
    def _classify_error(self, output: Any) -> Optional[str]:
        """Classify error type from output."""
        if isinstance(output, Exception):
            error_str = str(output).lower()
            if 'timeout' in error_str or 'timed out' in error_str:
                return 'timeout'
            elif 'connection' in error_str or 'network' in error_str:
                return 'network'
            elif 'permission' in error_str or 'unauthorized' in error_str:
                return 'permission'
            elif 'memory' in error_str:
                return 'memory'
            else:
                return 'execution_error'
        return 'unknown_error'
    
    def _mid_execution_reflection(self, cycle: ExecutionCycle, recent_log: List[Dict]):
        """Perform lightweight reflection during long executions."""
        # Quick pattern analysis
        recent_successes = sum(1 for log in recent_log[-5:] if log['success'])
        recent_total = len(recent_log[-5:])
        
        if recent_total > 0:
            recent_rate = recent_successes / recent_total
            if recent_rate < 0.4:
                # Poor recent performance - could trigger replanning
                # For now, just log the insight
                cycle.improvement_goals_created.append(
                    f"mid_exec_alert:_low_success_rate_{recent_rate:.2f}"
                )
    
    def _reflect_on_cycle(self, cycle: ExecutionCycle):
        """Comprehensive reflection after cycle completion."""
        # Analyze patterns for each task type encountered
        task_types = set()
        for record in self.reflection.performance_history:
            if record.metadata.get('cycle_id') == cycle.cycle_id:
                task_types.add(record.task_type)
        
        # Generate performance summaries
        cycle.performance_summary = {}
        for task_type in task_types:
            analysis = self.reflection.analyze_performance_patterns(task_type)
            cycle.performance_summary[task_type] = analysis
            
            # Assess capabilities for underperforming types
            if isinstance(analysis, dict) and analysis.get('success_rate', 1.0) < 0.8:
                assessment = self.reflection.assess_capability(
                    f"{task_type}_capability",
                    task_type
                )
                cycle.capability_updates.append(assessment.capability_name)
        
        # Identify problem areas
        problems = self.reflection.identify_problem_areas()
        
        # Create improvement goals for problem areas
        for problem in problems:
            goal = self.reflection.create_improvement_goal(
                target_capability=problem['task_type'],
                target_score=0.9,
                priority=8 if problem['severity'] == 'high' else 6,
                strategy=f"Focus on {problem['task_type']} with {problem['sample_size']} samples"
            )
            cycle.improvement_goals_created.append(goal.goal_id)
    
    def _store_cycle_memory(self, cycle: ExecutionCycle, plan: Plan):
        """Store cycle insights in tiered memory system."""
        # Store execution context in working memory
        context_data = {
            'cycle_id': cycle.cycle_id,
            'goal': cycle.goal,
            'plan_summary': self.planner.get_plan_summary(plan),
            'execution_metrics': {
                'tasks_executed': cycle.tasks_executed,
                'tasks_succeeded': cycle.tasks_succeeded,
                'tasks_failed': cycle.tasks_failed,
                'total_time_ms': cycle.total_execution_time_ms
            }
        }
        
        # Use the memory system to store with appropriate tier
        context_id = self._store_with_tier(
            content=json.dumps(context_data),
            metadata={
                'type': 'execution_context',
                'goal': cycle.goal[:100],
                'success_rate': cycle.tasks_succeeded / max(1, cycle.tasks_executed)
            }
        )
        cycle.memory_context_id = context_id
        
        # Generate and store reflection report
        reflection_report = self.reflection.generate_reflection_report()
        
        # Store in episodic memory for future reference
        report_content = json.dumps(reflection_report, indent=2)
        report_id = self._store_with_tier(
            content=report_content,
            metadata={
                'type': 'reflection_report',
                'generated_at': reflection_report['generated_at'],
                'cycles_completed': len(self.completed_cycles)
            },
            tier=MemoryTier.EPISODIC  # Important insights go to episodic
        )
        cycle.reflection_report_id = report_id
        
        # Store improvement goals as semantic knowledge
        for goal_id in cycle.improvement_goals_created:
            if goal_id in self.reflection.improvement_goals:
                goal = self.reflection.improvement_goals[goal_id]
                goal_content = json.dumps({
                    'goal_id': goal.goal_id,
                    'target_capability': goal.target_capability,
                    'target_score': goal.target_score,
                    'current_score': goal.current_score,
                    'strategy': goal.strategy
                })
                self._store_with_tier(
                    content=goal_content,
                    metadata={
                        'type': 'improvement_goal',
                        'capability': goal.target_capability,
                        'priority': goal.priority
                    },
                    tier=MemoryTier.SEMANTIC  # Goals are semantic knowledge
                )
    
    def _store_with_tier(
        self,
        content: str,
        metadata: Dict[str, Any],
        tier: Optional[MemoryTier] = None
    ) -> str:
        """Store content in memory with appropriate tier selection."""
        # If tier not specified, determine from content characteristics
        if tier is None:
            tier = self._determine_appropriate_tier(content, metadata)
        
        # Create directory path based on type
        memory_type = metadata.get('type', 'general')
        directory = f"/{memory_type}"
        
        # Store using tiered memory system
        entry = self.memory.store(
            content=content,
            tier=tier,
            directory=directory,
            importance=metadata.get('importance', 0.5),
            tags=set(metadata.get('tags', [])),
            source=f"integrated_agent:{self.agent_id}"
        )
        
        # Return a unique ID for this memory
        return f"{tier.value}:{directory}:{entry.timestamp}"
    
    def _determine_appropriate_tier(
        self,
        content: str,
        metadata: Dict[str, Any]
    ) -> MemoryTier:
        """Determine appropriate memory tier for content."""
        # High-priority insights go to L1_WORKING for intermediate retention
        if metadata.get('success_rate', 1.0) < 0.5:
            return MemoryTier.L1_WORKING  # Learn from failures
        
        # Improvement goals and strategies go to L2_ARCHIVAL for long-term
        if metadata.get('type') in ['improvement_goal', 'strategy_adaptation']:
            return MemoryTier.L2_ARCHIVAL
        
        # Execution details go to L0_IMMEDIATE for current session
        if metadata.get('type') == 'execution_context':
            return MemoryTier.L0_IMMEDIATE
        
        # Default to L0
        return MemoryTier.L0_IMMEDIATE
    
    def _get_tier_token_limit(self, tier: MemoryTier) -> int:
        """Get appropriate token limit for memory tier."""
        limits = {
            MemoryTier.L0_IMMEDIATE: 4000,
            MemoryTier.L1_WORKING: 8000,
            MemoryTier.L2_ARCHIVAL: 16000
        }
        return limits.get(tier, 4000)
    
    def _adapt_strategies_from_cycle(self, cycle: ExecutionCycle):
        """Adapt planning strategies based on cycle performance."""
        if not cycle.performance_summary:
            return
        
        for task_type, analysis in cycle.performance_summary.items():
            if isinstance(analysis, dict) and 'success_rate' in analysis:
                # Create or update strategy adaptation
                adaptation = StrategyAdaptation(
                    task_type=task_type,
                    current_strategy=self._get_current_strategy(task_type),
                    success_rate=analysis['success_rate'],
                    avg_execution_time=analysis.get('avg_execution_time_ms', 1000.0),
                    decomposition_depth=self._calculate_optimal_depth(analysis),
                    exploration_budget_multiplier=self._calculate_budget_multiplier(analysis),
                    retry_threshold=self._calculate_retry_threshold(analysis),
                    adaptations_applied=[{
                        'cycle_id': cycle.cycle_id,
                        'timestamp': datetime.now().isoformat(),
                        'trigger': f"success_rate_{analysis['success_rate']:.2f}"
                    }]
                )
                
                self.strategy_adaptations[task_type] = adaptation
                
                # Propose strategic change through reflection system
                if analysis['success_rate'] < 0.6:
                    self._propose_strategy_improvement(task_type, adaptation)
    
    def _get_current_strategy(self, task_type: str) -> str:
        """Get current strategy for task type."""
        if task_type in self.strategy_adaptations:
            return self.strategy_adaptations[task_type].current_strategy
        
        # Default strategies based on type
        defaults = {
            'exploratory_task': 'hypothesis_based_decomposition',
            'sequential_task': 'dependency_ordered_execution',
            'parallel_task': 'concurrent_execution_with_aggregation',
            'atomic_task': 'direct_execution'
        }
        return defaults.get(task_type, 'default_strategy')
    
    def _calculate_optimal_depth(self, analysis: Dict) -> int:
        """Calculate optimal decomposition depth from performance analysis."""
        base_depth = 4
        success_rate = analysis.get('success_rate', 0.7)
        
        if success_rate < 0.5:
            # More depth for exploration on failing tasks
            return min(6, base_depth + 2)
        elif success_rate > 0.9:
            # Less depth for well-understood tasks
            return max(3, base_depth - 1)
        
        return base_depth
    
    def _calculate_budget_multiplier(self, analysis: Dict) -> float:
        """Calculate budget multiplier from uncertainty metrics."""
        base_multiplier = 1.0
        trend = analysis.get('trend', 'stable')
        
        if trend == 'declining':
            # Increase budget for exploration when performance declines
            return 1.5
        elif analysis.get('error_patterns'):
            # Increase budget when errors are common
            error_rate = len(analysis['error_patterns']) / max(1, analysis.get('total_records', 1))
            return 1.0 + (error_rate * 0.5)
        
        return base_multiplier
    
    def _calculate_retry_threshold(self, analysis: Dict) -> int:
        """Calculate retry threshold from failure patterns."""
        base_threshold = 3
        failure_rate = 1.0 - analysis.get('success_rate', 0.7)
        
        # More retries for high-failure tasks (up to a limit)
        return min(5, base_threshold + int(failure_rate * 3))
    
    def _propose_strategy_improvement(
        self,
        task_type: str,
        adaptation: StrategyAdaptation
    ):
        """Propose a strategic improvement through reflection system."""
        # Create a strategic improvement proposal
        change = self.reflection.propose_change(
            scope=ReflectionScope.INTERNAL_STATE,
            description=f"Adapt planning strategy for {task_type}",
            rationale=f"Low success rate ({adaptation.success_rate:.2f}) suggests current strategy ineffective. "
                     f"Increasing depth to {adaptation.decomposition_depth} and budget multiplier to "
                     f"{adaptation.exploration_budget_multiplier} for better exploration.",
            expected_impact={
                'success_rate': 0.9 - adaptation.success_rate,  # Expected improvement
                'execution_time': adaptation.avg_execution_time * 0.1  # Slight time increase
            },
            implementation=json.dumps({
                'task_type': task_type,
                'decomposition_depth': adaptation.decomposition_depth,
                'budget_multiplier': adaptation.exploration_budget_multiplier,
                'retry_threshold': adaptation.retry_threshold
            })
        )
        
        # Auto-approve internal state changes with sufficient rationale
        if len(change.rationale) > 50 and not change.constitutional_violations:
            self.reflection.approve_change(change.change_id)
    
    # ============ Memory-Augmented Planning ============
    
    def plan_with_memory(
        self,
        goal: str,
        context: Optional[Dict] = None
    ) -> Tuple[Plan, List[Dict]]:
        """
        Create plan augmented with relevant memories.
        
        Retrieves similar past executions and their outcomes
        to inform current planning strategy.
        """
        # Search memory for similar goals
        similar_executions = self._retrieve_relevant_memories(goal)
        
        # Build context from memories
        memory_context = context or {}
        if similar_executions:
            memory_context['similar_past_executions'] = similar_executions
            
            # Extract strategy insights
            strategies = [m['metadata'].get('strategy', 'unknown') 
                         for m in similar_executions]
            success_rates = [m['metadata'].get('success_rate', 0.5) 
                            for m in similar_executions]
            
            if success_rates:
                best_strategy_idx = success_rates.index(max(success_rates))
                memory_context['recommended_strategy'] = strategies[best_strategy_idx]
                memory_context['expected_success_rate'] = max(success_rates)
        
        # Create plan with memory-augmented context
        plan = self.planner.create_plan(
            goal=goal,
            budget=None,
            context=memory_context
        )
        
        return plan, similar_executions
    
    def _retrieve_relevant_memories(self, goal: str) -> List[Dict]:
        """Retrieve relevant past execution memories for a goal."""
        relevant_memories = []
        
        # Use completed cycles instead of memory system for now
        # (memory system has different API than assumed)
        goal_keywords = set(goal.lower().split())
        
        for cycle in self.completed_cycles[-self.max_cycles_in_memory:]:
            if cycle.memory_context_id:  # Cycle was stored
                cycle_goal = cycle.goal.lower()
                cycle_keywords = set(cycle_goal.split())
                
                # Calculate relevance
                if goal_keywords:
                    overlap = len(goal_keywords & cycle_keywords)
                    relevance = overlap / len(goal_keywords)
                else:
                    relevance = 0.0
                
                if relevance > 0.3:  # Threshold for relevance
                    relevant_memories.append({
                        'cycle_id': cycle.cycle_id,
                        'goal': cycle.goal,
                        'relevance': relevance,
                        'success_rate': cycle.tasks_succeeded / max(1, cycle.tasks_executed),
                        'metadata': {
                            'strategy': self._get_strategy_from_cycle(cycle),
                            'success_rate': cycle.tasks_succeeded / max(1, cycle.tasks_executed),
                            'total_time_ms': cycle.total_execution_time_ms
                        }
                    })
        
        # Sort by relevance
        relevant_memories.sort(key=lambda x: x['relevance'], reverse=True)
        return relevant_memories[:5]  # Top 5 relevant
    
    def _get_strategy_from_cycle(self, cycle: ExecutionCycle) -> str:
        """Extract strategy used in a cycle."""
        # Try to find strategy adaptation for this cycle's goal
        for task_type, adaptation in self.strategy_adaptations.items():
            for record in adaptation.adaptations_applied:
                if record.get('cycle_id') == cycle.cycle_id:
                    return adaptation.current_strategy
        
        return 'unknown'
    
    # ============ Self-Improvement Proposals ============
    
    def propose_capability_improvements(self) -> List[ProposedChange]:
        """
        Propose improvements based on reflection analysis.
        
        Generates concrete improvement proposals for
        underperforming capabilities.
        """
        proposals = []
        
        # Get current capability profile
        profile = self.reflection.get_capability_profile()
        
        for capability_name, assessment in profile.items():
            if assessment.confidence < 0.7:
                # Need more data before proposing changes
                continue
            
            if assessment.proficiency_score < 0.7:
                # Underperforming - propose improvement
                proposal = self._create_capability_improvement_proposal(
                    capability_name,
                    assessment
                )
                proposals.append(proposal)
        
        return proposals
    
    def _create_capability_improvement_proposal(
        self,
        capability_name: str,
        assessment: CapabilityAssessment
    ) -> ProposedChange:
        """Create improvement proposal for a capability."""
        # Determine scope based on capability type
        if 'planning' in capability_name.lower():
            scope = ReflectionScope.INTERNAL_STATE
        elif 'memory' in capability_name.lower():
            scope = ReflectionScope.CONFIGURATION
        else:
            scope = ReflectionScope.INTERNAL_STATE
        
        # Build rationale from weaknesses
        rationale = f"Capability {capability_name} shows proficiency {assessment.proficiency_score:.2f} "
        rationale += f"(confidence: {assessment.confidence:.2f}). "
        
        if assessment.weaknesses:
            rationale += f"Identified weaknesses: {', '.join(assessment.weaknesses[:3])}. "
        
        if assessment.improvement_suggestions:
            rationale += f"Suggested improvements: {', '.join(assessment.improvement_suggestions[:2])}."
        
        # Expected impact
        impact = {
            'proficiency_increase': (0.9 - assessment.proficiency_score) * 0.8,
            'confidence_increase': 0.1,
            'execution_time_change': -0.1
        }
        
        return self.reflection.propose_change(
            scope=scope,
            description=f"Improve {capability_name} capability",
            rationale=rationale,
            expected_impact=impact,
            implementation=f"Practice {capability_name} with diverse test cases and "
                          f"implement {assessment.improvement_suggestions[0] if assessment.improvement_suggestions else 'error handling'}"
        )
    
    # ============ Status and Reporting ============
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get comprehensive agent status."""
        total_cycles = len(self.completed_cycles)
        
        if total_cycles > 0:
            avg_success_rate = sum(
                c.tasks_succeeded / max(1, c.tasks_executed)
                for c in self.completed_cycles
            ) / total_cycles
            
            total_tasks = sum(c.tasks_executed for c in self.completed_cycles)
            total_successes = sum(c.tasks_succeeded for c in self.completed_cycles)
        else:
            avg_success_rate = 0.0
            total_tasks = 0
            total_successes = 0
        
        return {
            'agent_id': self.agent_id,
            'cycles_completed': total_cycles,
            'total_tasks_executed': total_tasks,
            'overall_success_rate': round(total_successes / max(1, total_tasks), 3),
            'average_cycle_success_rate': round(avg_success_rate, 3),
            'active_cycles': len(self.active_cycles),
            'strategy_adaptations_count': len(self.strategy_adaptations),
            'capability_assessments': len(self.reflection.capability_assessments),
            'improvement_goals_active': len([g for g in self.reflection.improvement_goals.values() 
                                           if g.status == 'active']),
            'reflection_stats': {
                'performance_records': len(self.reflection.performance_history),
                'proposed_changes': len(self.reflection.change_history)
            }
        }
    
    def export_state(self) -> Dict[str, Any]:
        """Export full agent state for persistence."""
        return {
            'agent_id': self.agent_id,
            'completed_cycles': [
                {
                    'cycle_id': c.cycle_id,
                    'goal': c.goal,
                    'started_at': c.started_at.isoformat(),
                    'completed_at': c.completed_at.isoformat() if c.completed_at else None,
                    'tasks_executed': c.tasks_executed,
                    'tasks_succeeded': c.tasks_succeeded,
                    'tasks_failed': c.tasks_failed,
                    'total_execution_time_ms': c.total_execution_time_ms
                }
                for c in self.completed_cycles
            ],
            'strategy_adaptations': {
                k: {
                    'task_type': v.task_type,
                    'current_strategy': v.current_strategy,
                    'success_rate': v.success_rate,
                    'decomposition_depth': v.decomposition_depth,
                    'exploration_budget_multiplier': v.exploration_budget_multiplier,
                    'retry_threshold': v.retry_threshold
                }
                for k, v in self.strategy_adaptations.items()
            },
            'reflection_state': self.reflection.export_state()
        }


def create_integrated_agent(agent_id: str = "integrated_1") -> IntegratedAgent:
    """Factory function to create a configured integrated agent."""
    return IntegratedAgent(agent_id=agent_id)
