"""
SCRAT-Inspired Verifiable Action System
Based on: "Selective Compliance via Recursive Assessment Tree" (arXiv:2604.03201)

Core Insight: Integration beats component optimization
- Tight coupling of control, structured episodic memory, and verifiers
- Verification happens DURING action loop, not just post-hoc
- Structured episodic memory with retrieval for future control decisions
- Partial observability handling with hypothesis tracking
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any, Tuple, Set
from enum import Enum
from datetime import datetime
import hashlib
import json


class ActionStatus(Enum):
    """Status of an action in the verifiable loop."""
    PROPOSED = "proposed"           # Initial proposal
    VERIFICATION_PENDING = "verification_pending"
    VERIFIED = "verified"           # Passed verification
    REJECTED = "rejected"           # Failed verification
    EXECUTED = "executed"           # Successfully executed
    FAILED = "failed"               # Execution failed
    RECOVERED = "recovered"         # Failed but recovered


class VerificationLevel(Enum):
    """Levels of verification strictness."""
    NONE = 0        # No verification (unsafe)
    SYNTACTIC = 1   # Basic format/syntax check
    SEMANTIC = 2    # Meaning/constraint validation
    SIMULATION = 3  # Simulate before execute
    EXHAUSTIVE = 4  # Full verification with rollbacks


@dataclass
class Observation:
    """Structured observation from the environment."""
    timestamp: datetime
    partial_view: Dict[str, Any]  # What was actually observed
    visibility_bounds: Tuple[Set[str], Set[str]]  # (visible_attrs, hidden_attrs)
    raw_data: Any
    
    def get_hash(self) -> str:
        """Cryptographic hash for memory integrity."""
        content = json.dumps({
            'timestamp': self.timestamp.isoformat(),
            'partial_view': self.partial_view,
            'raw_type': type(self.raw_data).__name__
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class Hypothesis:
    """Working theory about the environment state."""
    hypothesis_id: str
    description: str
    confidence: float  # 0.0 - 1.0
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    contradictions: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def update_confidence(self, new_evidence: Dict[str, Any], supports: bool):
        """Update confidence based on new evidence."""
        self.updated_at = datetime.now()
        if supports:
            self.evidence.append(new_evidence)
            # Bayesian-like update
            self.confidence = min(1.0, self.confidence + 0.1)
        else:
            self.contradictions.append(new_evidence)
            self.confidence = max(0.0, self.confidence - 0.15)


@dataclass
class EpisodicMemory:
    """Structured episodic memory for control decisions."""
    episode_id: str
    context: Dict[str, Any]
    observations: List[Observation] = field(default_factory=list)
    hypotheses: Dict[str, Hypothesis] = field(default_factory=dict)
    actions: List['VerifiableAction'] = field(default_factory=list)
    outcomes: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    
    def get_relevant_memories(self, query: Dict[str, Any], k: int = 5) -> List[Dict]:
        """Retrieve memories relevant to current control decision."""
        scored = []
        for action in self.actions:
            score = self._similarity_score(action, query)
            scored.append((score, action))
        
        # Also check hypothesis relevance
        for hyp in self.hypotheses.values():
            score = self._hypothesis_relevance(hyp, query)
            scored.append((score, hyp))
        
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:k]
    
    def _similarity_score(self, action: 'VerifiableAction', query: Dict) -> float:
        """Calculate similarity between action context and query."""
        score = 0.0
        for key, value in query.items():
            if key in action.context and action.context[key] == value:
                score += 1.0
        return score / max(len(query), 1)
    
    def _hypothesis_relevance(self, hyp: Hypothesis, query: Dict) -> float:
        """Calculate hypothesis relevance to query."""
        query_str = json.dumps(query, sort_keys=True).lower()
        desc_match = sum(1 for word in hyp.description.lower().split() 
                        if word in query_str)
        return (desc_match / max(len(hyp.description.split()), 1)) * hyp.confidence


@dataclass
class VerificationResult:
    """Result of action verification."""
    passed: bool
    verification_type: str
    checks_performed: List[str]
    warnings: List[str]
    errors: List[str]
    simulation_result: Optional[Dict] = None
    rollback_plan: Optional[List[Dict]] = None
    confidence: float = 0.0


@dataclass
class VerifiableAction:
    """An action in the verifiable action loop."""
    action_id: str
    action_type: str
    parameters: Dict[str, Any]
    context: Dict[str, Any]
    status: ActionStatus = ActionStatus.PROPOSED
    verification_level: VerificationLevel = VerificationLevel.SEMANTIC
    
    # Verification tracking
    pre_verification: Optional[VerificationResult] = None
    post_verification: Optional[VerificationResult] = None
    
    # Execution tracking
    execution_start: Optional[datetime] = None
    execution_end: Optional[datetime] = None
    execution_result: Optional[Any] = None
    execution_error: Optional[str] = None
    
    # Memory integration
    memory_references: List[str] = field(default_factory=list)
    hypothesis_references: List[str] = field(default_factory=list)
    
    created_at: datetime = field(default_factory=datetime.now)


class ActionVerifier:
    """Verifier that checks actions before execution."""
    
    def __init__(self, level: VerificationLevel = VerificationLevel.SEMANTIC):
        self.level = level
        self.verification_history: List[VerificationResult] = []
    
    def verify(self, action: VerifiableAction, 
               context: Dict[str, Any],
               memory: Optional[EpisodicMemory] = None) -> VerificationResult:
        """Verify an action before execution."""
        
        checks = []
        warnings = []
        errors = []
        simulation = None
        rollback = None
        
        # Level 1: Syntactic check
        if self.level.value >= VerificationLevel.SYNTACTIC.value:
            checks.append("syntax_check")
            if not self._check_syntax(action):
                errors.append("Syntax validation failed")
        
        # Level 2: Semantic check
        if self.level.value >= VerificationLevel.SEMANTIC.value:
            checks.append("semantic_check")
            semantic_ok, semantic_warnings = self._check_semantic(action, context)
            warnings.extend(semantic_warnings)
            if not semantic_ok:
                errors.append("Semantic validation failed")
        
        # Level 3: Simulation
        if self.level.value >= VerificationLevel.SIMULATION.value:
            checks.append("simulation")
            simulation = self._simulate_action(action, context)
            if simulation.get('predicted_failure', False):
                errors.append(f"Simulation predicted failure: {simulation.get('failure_reason')}")
        
        # Level 4: Exhaustive (with rollback plan)
        if self.level.value >= VerificationLevel.EXHAUSTIVE.value:
            checks.append("rollback_plan")
            rollback = self._generate_rollback_plan(action, context)
        
        passed = len(errors) == 0
        
        # Check against memory for similar failures
        if memory and passed:
            similar_failures = self._check_memory_for_failures(action, memory)
            if similar_failures:
                warnings.append(f"Similar actions failed {similar_failures} times in memory")
                passed = False  # Conservative: require higher verification
        
        result = VerificationResult(
            passed=passed,
            verification_type=self.level.name,
            checks_performed=checks,
            warnings=warnings,
            errors=errors,
            simulation_result=simulation,
            rollback_plan=rollback,
            confidence=1.0 - (len(warnings) * 0.1) - (len(errors) * 0.3)
        )
        
        self.verification_history.append(result)
        return result
    
    def _check_syntax(self, action: VerifiableAction) -> bool:
        """Basic syntax/format validation."""
        return (
            action.action_id and 
            action.action_type and
            isinstance(action.parameters, dict)
        )
    
    def _check_semantic(self, action: VerifiableAction, 
                        context: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Semantic/constraint validation."""
        warnings = []
        
        # Check if action is contextually appropriate
        if action.action_type == "write" and context.get("read_only", False):
            return False, ["Write action in read-only context"]
        
        # Check parameter ranges
        for param, value in action.parameters.items():
            if isinstance(value, (int, float)):
                if abs(value) > 1e6:
                    warnings.append(f"Large value detected for {param}: {value}")
        
        return True, warnings
    
    def _simulate_action(self, action: VerifiableAction, 
                       context: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate action execution to predict outcome."""
        # Simplified simulation
        simulation_result = {
            'predicted_success': True,
            'predicted_failure': False,
            'estimated_cost': self._estimate_cost(action),
            'side_effects': []
        }
        
        # Check for obvious issues
        if action.action_type == "delete" and not action.parameters.get("confirm", False):
            simulation_result['predicted_failure'] = True
            simulation_result['failure_reason'] = "Delete without confirmation"
        
        return simulation_result
    
    def _estimate_cost(self, action: VerifiableAction) -> float:
        """Estimate computational/resource cost."""
        base_costs = {
            "read": 1.0,
            "write": 2.0,
            "compute": 3.0,
            "search": 5.0,
            "delete": 2.0
        }
        return base_costs.get(action.action_type, 1.0)
    
    def _generate_rollback_plan(self, action: VerifiableAction,
                                context: Dict[str, Any]) -> List[Dict]:
        """Generate plan to undo action if needed."""
        rollback_steps = []
        
        if action.action_type == "write":
            # Plan: restore previous state
            rollback_steps.append({
                "type": "restore",
                "target": action.parameters.get("target"),
                "backup_context": context.get("backup", {})
            })
        elif action.action_type == "delete":
            # Plan: recreate from backup
            rollback_steps.append({
                "type": "recreate",
                "data": action.parameters.get("backup_data")
            })
        
        return rollback_steps
    
    def _check_memory_for_failures(self, action: VerifiableAction,
                                   memory: EpisodicMemory) -> int:
        """Check episodic memory for similar action failures."""
        failure_count = 0
        for past_action in memory.actions:
            if (past_action.action_type == action.action_type and
                past_action.status == ActionStatus.FAILED):
                # Check parameter similarity
                if self._parameter_similarity(past_action.parameters, action.parameters) > 0.7:
                    failure_count += 1
        return failure_count
    
    def _parameter_similarity(self, params1: Dict, params2: Dict) -> float:
        """Calculate similarity between parameter sets."""
        if not params1 or not params2:
            return 0.0
        
        common_keys = set(params1.keys()) & set(params2.keys())
        all_keys = set(params1.keys()) | set(params2.keys())
        
        if not all_keys:
            return 0.0
        
        matches = sum(1 for k in common_keys if params1[k] == params2[k])
        return matches / len(all_keys)


class VerifiableActionLoop:
    """
    Main SCRAT-inspired action loop.
    Tight coupling: Control ↔ Memory ↔ Verifier
    """
    
    def __init__(self, 
                 verification_level: VerificationLevel = VerificationLevel.SEMANTIC,
                 enable_recovery: bool = True):
        self.verifier = ActionVerifier(level=verification_level)
        self.enable_recovery = enable_recovery
        
        # Current episode
        self.current_episode: Optional[EpisodicMemory] = None
        
        # Action execution callbacks (type -> function)
        self.action_handlers: Dict[str, Callable] = {}
        
        # Statistics
        self.stats = {
            'actions_proposed': 0,
            'actions_verified': 0,
            'actions_executed': 0,
            'actions_failed': 0,
            'actions_recovered': 0,
            'verification_failures': 0
        }
    
    def register_action_handler(self, action_type: str, 
                                handler: Callable[[Dict], Any]):
        """Register a handler for an action type."""
        self.action_handlers[action_type] = handler
    
    def start_episode(self, episode_id: str, context: Dict[str, Any]) -> EpisodicMemory:
        """Start a new episodic memory session."""
        self.current_episode = EpisodicMemory(
            episode_id=episode_id,
            context=context
        )
        return self.current_episode
    
    def propose_action(self, action_type: str, parameters: Dict[str, Any],
                       context: Optional[Dict] = None) -> VerifiableAction:
        """Propose an action in the loop."""
        self.stats['actions_proposed'] += 1
        
        action_id = f"action_{self.stats['actions_proposed']}_{datetime.now().strftime('%H%M%S')}"
        
        action = VerifiableAction(
            action_id=action_id,
            action_type=action_type,
            parameters=parameters,
            context=context or {},
            status=ActionStatus.PROPOSED
        )
        
        return action
    
    def verify_and_execute(self, action: VerifiableAction,
                           observation_callback: Optional[Callable] = None) -> Tuple[bool, Any]:
        """
        Full verifiable action loop:
        1. Retrieve relevant memories
        2. Verify action
        3. Execute if verified
        4. Store outcome in episodic memory
        5. Update hypotheses
        """
        if not self.current_episode:
            raise ValueError("No active episode. Call start_episode() first.")
        
        # Step 1: Retrieve relevant memories for control decision
        relevant = self.current_episode.get_relevant_memories(action.context, k=3)
        action.memory_references = [r[1].action_id if hasattr(r[1], 'action_id') else r[1].hypothesis_id 
                                    for r in relevant if r[0] > 0.5]
        
        # Step 2: Pre-execution verification
        action.status = ActionStatus.VERIFICATION_PENDING
        verification = self.verifier.verify(action, action.context, self.current_episode)
        action.pre_verification = verification
        
        if not verification.passed:
            action.status = ActionStatus.REJECTED
            self.stats['verification_failures'] += 1
            self.current_episode.actions.append(action)
            return False, {"error": "Verification failed", "result": verification}
        
        action.status = ActionStatus.VERIFIED
        self.stats['actions_verified'] += 1
        
        # Step 3: Execute action
        execution_result = self._execute_action(action)
        
        # Step 4: Post-execution verification
        if observation_callback:
            observation = observation_callback()
            observation_hash = observation.get_hash()
            self.current_episode.observations.append(observation)
            
            # Verify outcome matches expectation
            post_verification = self._verify_outcome(action, execution_result, observation)
            action.post_verification = post_verification
        
        # Step 5: Store in episodic memory
        self.current_episode.actions.append(action)
        self.current_episode.outcomes.append({
            'action_id': action.action_id,
            'result': execution_result,
            'timestamp': datetime.now().isoformat()
        })
        
        # Update statistics
        if action.status == ActionStatus.EXECUTED:
            self.stats['actions_executed'] += 1
        elif action.status == ActionStatus.FAILED:
            self.stats['actions_failed'] += 1
        
        success = action.status in [ActionStatus.EXECUTED, ActionStatus.RECOVERED]
        return success, execution_result
    
    def _execute_action(self, action: VerifiableAction) -> Any:
        """Execute the action using registered handler."""
        action.execution_start = datetime.now()
        
        handler = self.action_handlers.get(action.action_type)
        if not handler:
            action.execution_error = f"No handler for action type: {action.action_type}"
            action.status = ActionStatus.FAILED
            action.execution_end = datetime.now()
            return None
        
        try:
            result = handler(action.parameters)
            action.execution_result = result
            action.status = ActionStatus.EXECUTED
            
            # Check if recovery is needed
            if self.enable_recovery and self._needs_recovery(result):
                recovery_result = self._attempt_recovery(action, result)
                if recovery_result:
                    action.status = ActionStatus.RECOVERED
                    self.stats['actions_recovered'] += 1
                    result = recovery_result
            
        except Exception as e:
            action.execution_error = str(e)
            action.status = ActionStatus.FAILED
            
            if self.enable_recovery:
                recovery_result = self._attempt_recovery(action, None, str(e))
                if recovery_result:
                    action.status = ActionStatus.RECOVERED
                    self.stats['actions_recovered'] += 1
                    result = recovery_result
            else:
                result = None
        
        action.execution_end = datetime.now()
        return result
    
    def _needs_recovery(self, result: Any) -> bool:
        """Check if result indicates need for recovery."""
        if isinstance(result, dict):
            return result.get('status') == 'partial' or result.get('needs_recovery', False)
        return False
    
    def _attempt_recovery(self, action: VerifiableAction, 
                          partial_result: Any,
                          error: Optional[str] = None) -> Optional[Any]:
        """Attempt to recover from action failure."""
        # Use rollback plan from pre-verification
        if action.pre_verification and action.pre_verification.rollback_plan:
            # Simplified recovery: return backup data
            return {
                'status': 'recovered',
                'original_action': action.action_id,
                'recovery_plan': action.pre_verification.rollback_plan,
                'error': error
            }
        return None
    
    def _verify_outcome(self, action: VerifiableAction,
                        result: Any, observation: Observation) -> VerificationResult:
        """Verify the outcome matches expectations."""
        # Check if observation is consistent with expected outcome
        warnings = []
        errors = []
        
        # Simple consistency check
        if action.action_type == "write":
            # Verify written data appears in observation
            expected_target = action.parameters.get("target")
            if expected_target and expected_target not in str(observation.partial_view):
                warnings.append("Written data not visible in observation")
        
        return VerificationResult(
            passed=len(errors) == 0,
            verification_type="post_execution",
            checks_performed=["outcome_consistency"],
            warnings=warnings,
            errors=errors,
            confidence=0.9 if not warnings else 0.7
        )
    
    def create_hypothesis(self, description: str, 
                          initial_confidence: float = 0.5) -> Hypothesis:
        """Create a new hypothesis in current episode."""
        if not self.current_episode:
            raise ValueError("No active episode")
        
        hyp_id = f"hyp_{len(self.current_episode.hypotheses)}_{datetime.now().strftime('%H%M%S')}"
        
        hypothesis = Hypothesis(
            hypothesis_id=hyp_id,
            description=description,
            confidence=initial_confidence
        )
        
        self.current_episode.hypotheses[hyp_id] = hypothesis
        return hypothesis
    
    def test_hypothesis(self, hypothesis_id: str, 
                       action: VerifiableAction,
                       outcome: Dict[str, Any]) -> None:
        """Test a hypothesis with action outcome."""
        if not self.current_episode:
            return
        
        hyp = self.current_episode.hypotheses.get(hypothesis_id)
        if not hyp:
            return
        
        # Simple test: does outcome support hypothesis?
        supports = outcome.get('success', False)
        hyp.update_confidence({'action': action.action_id, 'outcome': outcome}, supports)
        
        action.hypothesis_references.append(hypothesis_id)
    
    def end_episode(self) -> EpisodicMemory:
        """End current episode and return memory."""
        episode = self.current_episode
        self.current_episode = None
        return episode
    
    def get_stats(self) -> Dict[str, int]:
        """Get loop statistics."""
        return self.stats.copy()
    
    def get_episode_summary(self) -> Dict[str, Any]:
        """Get summary of current episode."""
        if not self.current_episode:
            return {"error": "No active episode"}
        
        return {
            'episode_id': self.current_episode.episode_id,
            'duration': (datetime.now() - self.current_episode.created_at).total_seconds(),
            'observations': len(self.current_episode.observations),
            'hypotheses': len(self.current_episode.hypotheses),
            'actions': len(self.current_episode.actions),
            'action_breakdown': self._get_action_breakdown(),
            'top_hypotheses': self._get_top_hypotheses(3)
        }
    
    def _get_action_breakdown(self) -> Dict[str, int]:
        """Get breakdown of actions by status."""
        breakdown = {}
        for action in self.current_episode.actions:
            status = action.status.value
            breakdown[status] = breakdown.get(status, 0) + 1
        return breakdown
    
    def _get_top_hypotheses(self, n: int) -> List[Dict]:
        """Get top N hypotheses by confidence."""
        sorted_hyps = sorted(
            self.current_episode.hypotheses.values(),
            key=lambda h: h.confidence,
            reverse=True
        )
        return [
            {
                'id': h.hypothesis_id,
                'description': h.description[:50] + "..." if len(h.description) > 50 else h.description,
                'confidence': h.confidence,
                'evidence_count': len(h.evidence)
            }
            for h in sorted_hyps[:n]
        ]


class PartialObservableEnvironment:
    """
    Simulated environment with partial observability.
    For testing hypothesis-driven control.
    """
    
    def __init__(self, full_state: Dict[str, Any], visibility_mask: Set[str]):
        self.full_state = full_state
        self.visibility_mask = visibility_mask
        self.action_history = []
    
    def observe(self) -> Observation:
        """Get partial observation of environment."""
        partial_view = {k: v for k, v in self.full_state.items() 
                       if k in self.visibility_mask}
        hidden = set(self.full_state.keys()) - self.visibility_mask
        
        return Observation(
            timestamp=datetime.now(),
            partial_view=partial_view,
            visibility_bounds=(self.visibility_mask, hidden),
            raw_data=self.full_state
        )
    
    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute action on environment."""
        self.action_history.append(action)
        
        action_type = action.get('type')
        
        if action_type == 'read':
            target = action.get('target')
            if target in self.full_state:
                return {'success': True, 'data': self.full_state[target]}
            return {'success': False, 'error': 'Not found'}
        
        elif action_type == 'write':
            target = action.get('target')
            value = action.get('value')
            self.full_state[target] = value
            return {'success': True, 'written': {target: value}}
        
        elif action_type == 'explore':
            # Exploration might reveal new attributes
            new_visible = action.get('reveal', set())
            self.visibility_mask.update(new_visible)
            return {'success': True, 'newly_visible': new_visible}
        
        return {'success': False, 'error': 'Unknown action type'}
