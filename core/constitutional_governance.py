"""
Constitutional Governance Framework

Implements rule-based constraints on agent behavior, safety circuit breakers,
and human-in-the-loop approval workflows based on:
- Ouroboros BIBLE.md constitutional pattern
- Claude AI incident safety learnings
- Anthropic's Constitutional AI research

Core concepts:
- Constitution: Immutable principles + amendable rules
- Circuit Breakers: Automatic stops on dangerous operations
- Approval Gates: Human-in-the-loop for critical decisions
- Violation Detection: Monitor and flag rule violations
"""

import json
import hashlib
import time
from enum import Enum, auto
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Callable, Any, Set
from datetime import datetime
import threading


class RulePriority(Enum):
    """Priority levels for constitutional rules."""
    CRITICAL = auto()    # Cannot be overridden, immediate halt
    HIGH = auto()        # Requires explicit override with justification
    MEDIUM = auto()      # Warning + logging, override tracked
    LOW = auto()         # Advisory only, logged for review


class RuleCategory(Enum):
    """Categories of constitutional rules."""
    SAFETY = "safety"              # Physical/social harm prevention
    SECURITY = "security"          # Data/system security
    ETHICS = "ethics"              # Moral/ethical constraints
    OPERATIONAL = "operational"    # Operational boundaries
    TRANSPARENCY = "transparency"  # Explainability/audit requirements


class ApprovalStatus(Enum):
    """Status of approval requests."""
    PENDING = auto()
    APPROVED = auto()
    DENIED = auto()
    EXPIRED = auto()


class CircuitBreakerState(Enum):
    """States for circuit breaker pattern."""
    CLOSED = auto()      # Normal operation
    OPEN = auto()        # Blocking requests
    HALF_OPEN = auto()   # Testing if recovered


@dataclass
class ConstitutionalRule:
    """A single rule in the constitution."""
    id: str
    name: str
    description: str
    category: RuleCategory
    priority: RulePriority
    condition: str  # String representation of condition logic
    action: str  # "block", "warn", "require_approval", "log"
    immutable: bool = False  # True for core principles
    created_at: float = field(default_factory=time.time)
    amended_at: Optional[float] = None
    amendment_reason: Optional[str] = None
    violation_count: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "priority": self.priority.name,
            "condition": self.condition,
            "action": self.action,
            "immutable": self.immutable,
            "created_at": self.created_at,
            "amended_at": self.amended_at,
            "amendment_reason": self.amendment_reason,
            "violation_count": self.violation_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ConstitutionalRule":
        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            category=RuleCategory(data["category"]),
            priority=RulePriority[data["priority"]],
            condition=data["condition"],
            action=data["action"],
            immutable=data.get("immutable", False),
            created_at=data["created_at"],
            amended_at=data.get("amended_at"),
            amendment_reason=data.get("amendment_reason"),
            violation_count=data.get("violation_count", 0)
        )


@dataclass
class ApprovalRequest:
    """Request for human approval on critical operations."""
    id: str
    operation_type: str
    description: str
    context: Dict[str, Any]
    requested_at: float
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_at: Optional[float] = None
    approved_by: Optional[str] = None
    denial_reason: Optional[str] = None
    expiry_seconds: int = 3600  # 1 hour default
    
    def is_expired(self) -> bool:
        if self.status != ApprovalStatus.PENDING:
            return False
        return time.time() - self.requested_at > self.expiry_seconds


@dataclass
class ViolationReport:
    """Report of a constitutional rule violation."""
    id: str
    rule_id: str
    rule_name: str
    timestamp: float
    operation: str
    context: Dict[str, Any]
    action_taken: str
    severity: RulePriority
    resolved: bool = False


@dataclass
class CircuitBreaker:
    """Circuit breaker for dangerous operations."""
    name: str
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[float] = None
    
    def record_success(self):
        """Record a successful operation."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.CLOSED
            self.failure_count = 0
        elif self.state == CircuitBreakerState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self) -> bool:
        """Record a failure. Returns True if breaker should trip."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            return True
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            return True
        
        return False
    
    def can_execute(self) -> bool:
        """Check if operation can proceed."""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        
        if self.state == CircuitBreakerState.OPEN:
            if self.last_failure_time and \
               time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                return True
            return False
        
        return True  # HALF_OPEN allows one test


class ConstitutionalGovernance:
    """
    Main governance framework implementing constitutional constraints.
    
    Features:
    - Rule definition and enforcement
    - Circuit breakers for dangerous operations
    - Human approval workflows
    - Violation tracking and reporting
    - Constitutional amendments with safeguards
    """
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.rules: Dict[str, ConstitutionalRule] = {}
        self.approval_requests: Dict[str, ApprovalRequest] = {}
        self.violations: List[ViolationReport] = []
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.approval_handlers: List[Callable[[ApprovalRequest], None]] = []
        self._lock = threading.RLock()
        
        # Initialize default constitution
        self._init_default_constitution()
    
    def _init_default_constitution(self):
        """Initialize with core immutable principles."""
        core_rules = [
            ConstitutionalRule(
                id="core-001",
                name="No Harm to Humans",
                description="The agent must not take actions that cause physical, emotional, or financial harm to humans.",
                category=RuleCategory.SAFETY,
                priority=RulePriority.CRITICAL,
                condition="action.could_cause_human_harm",
                action="block",
                immutable=True
            ),
            ConstitutionalRule(
                id="core-002",
                name="No Unauthorized System Modifications",
                description="The agent must not modify system files, configurations, or infrastructure without explicit approval.",
                category=RuleCategory.SECURITY,
                priority=RulePriority.CRITICAL,
                condition="action.modifies_system_state AND NOT action.has_explicit_approval",
                action="block",
                immutable=True
            ),
            ConstitutionalRule(
                id="core-003",
                name="Data Privacy Protection",
                description="The agent must not expose, share, or process personal data in unauthorized ways.",
                category=RuleCategory.ETHICS,
                priority=RulePriority.CRITICAL,
                condition="action.handles_pii AND NOT action.has_consent",
                action="block",
                immutable=True
            ),
            ConstitutionalRule(
                id="core-004",
                name="Transparency in Decision Making",
                description="The agent must provide clear reasoning for significant decisions.",
                category=RuleCategory.TRANSPARENCY,
                priority=RulePriority.HIGH,
                condition="action.significant_impact AND NOT action.has_explanation",
                action="require_approval",
                immutable=True
            ),
            ConstitutionalRule(
                id="ops-001",
                name="Resource Usage Limits",
                description="Operations consuming excessive resources require justification.",
                category=RuleCategory.OPERATIONAL,
                priority=RulePriority.MEDIUM,
                condition="action.estimated_cost > threshold.cost_high",
                action="require_approval",
                immutable=False
            ),
            ConstitutionalRule(
                id="ops-002",
                name="External API Call Rate Limiting",
                description="Rate limit external API calls to prevent abuse.",
                category=RuleCategory.OPERATIONAL,
                priority=RulePriority.MEDIUM,
                condition="api.call_rate > threshold.rate_limit",
                action="warn",
                immutable=False
            ),
            ConstitutionalRule(
                id="eth-001",
                name="Bias Detection and Mitigation",
                description="Flag potentially biased outputs for review.",
                category=RuleCategory.ETHICS,
                priority=RulePriority.HIGH,
                condition="output.potentially_biased",
                action="require_approval",
                immutable=False
            )
        ]
        
        for rule in core_rules:
            self.rules[rule.id] = rule
    
    def add_rule(self, rule: ConstitutionalRule, amendment_reason: Optional[str] = None) -> bool:
        """Add a new rule to the constitution."""
        with self._lock:
            if rule.id in self.rules and self.rules[rule.id].immutable:
                return False  # Cannot modify immutable rules
            
            rule.amended_at = time.time()
            rule.amendment_reason = amendment_reason
            self.rules[rule.id] = rule
            return True
    
    def remove_rule(self, rule_id: str) -> bool:
        """Remove a rule (only if not immutable)."""
        with self._lock:
            if rule_id not in self.rules:
                return False
            if self.rules[rule_id].immutable:
                return False
            del self.rules[rule_id]
            return True
    
    def evaluate_operation(self, operation: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate an operation against all constitutional rules.
        
        Returns:
            Dict with 'allowed', 'violations', 'required_approvals', 'warnings'
        """
        with self._lock:
            result = {
                "allowed": True,
                "violations": [],
                "required_approvals": [],
                "warnings": []
            }
            
            for rule in self.rules.values():
                # Evaluate rule condition (simplified - would use proper parser in production)
                triggered = self._evaluate_condition(rule.condition, operation, context)
                
                if triggered:
                    rule.violation_count += 1
                    
                    if rule.priority == RulePriority.CRITICAL:
                        result["allowed"] = False
                        result["violations"].append({
                            "rule_id": rule.id,
                            "rule_name": rule.name,
                            "severity": rule.priority.name,
                            "action": rule.action
                        })
                        self._log_violation(rule, operation, context, rule.action)
                    
                    elif rule.action == "require_approval":
                        approval_id = self._request_approval(operation, context, rule)
                        result["required_approvals"].append(approval_id)
                    
                    elif rule.action == "warn":
                        result["warnings"].append({
                            "rule_id": rule.id,
                            "rule_name": rule.name,
                            "message": rule.description
                        })
            
            return result
    
    def _evaluate_condition(self, condition: str, operation: str, context: Dict) -> bool:
        """
        Evaluate a rule condition against the operation context.
        Simplified implementation - production would use proper expression parser.
        """
        # Simple pattern matching for demonstration
        condition_lower = condition.lower()
        
        # Check operation type patterns
        if "modifies_system_state" in condition_lower:
            system_ops = ["delete", "modify", "update", "write", "chmod", "rm", "mv"]
            if any(op in operation.lower() for op in system_ops):
                if "has_explicit_approval" in condition_lower:
                    return not context.get("has_approval", False)
                return True
        
        if "could_cause_human_harm" in condition_lower:
            harmful_ops = ["execute", "run", "deploy", "send", "transfer"]
            if any(op in operation.lower() for op in harmful_ops):
                if context.get("targets_human", False):
                    return True
        
        if "handles_pii" in condition_lower:
            if context.get("contains_pii", False):
                if "has_consent" in condition_lower:
                    return not context.get("has_consent", False)
                return True
        
        if "significant_impact" in condition_lower:
            if context.get("impact_score", 0) > 0.7:
                if "has_explanation" in condition_lower:
                    return not context.get("has_explanation", False)
                return True
        
        if "estimated_cost" in condition_lower:
            if context.get("estimated_cost", 0) > 100:
                return True
        
        if "potentially_biased" in condition_lower:
            if context.get("bias_score", 0) > 0.5:
                return True
        
        return False
    
    def _log_violation(self, rule: ConstitutionalRule, operation: str, 
                       context: Dict, action_taken: str):
        """Log a rule violation."""
        violation = ViolationReport(
            id=self._generate_id(),
            rule_id=rule.id,
            rule_name=rule.name,
            timestamp=time.time(),
            operation=operation,
            context=context.copy(),
            action_taken=action_taken,
            severity=rule.priority
        )
        self.violations.append(violation)
    
    def _request_approval(self, operation: str, context: Dict, 
                          rule: ConstitutionalRule) -> str:
        """Create an approval request."""
        approval_id = self._generate_id()
        request = ApprovalRequest(
            id=approval_id,
            operation_type=operation,
            description=f"Operation requires approval due to rule: {rule.name}",
            context={
                "operation": operation,
                "triggering_rule": rule.to_dict(),
                **context
            },
            requested_at=time.time()
        )
        self.approval_requests[approval_id] = request
        
        # Notify handlers
        for handler in self.approval_handlers:
            try:
                handler(request)
            except Exception:
                pass
        
        return approval_id
    
    def _generate_id(self) -> str:
        """Generate unique ID."""
        data = f"{self.agent_id}:{time.time()}:{threading.current_thread().ident}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def approve_operation(self, approval_id: str, approver: str) -> bool:
        """Approve a pending operation."""
        with self._lock:
            if approval_id not in self.approval_requests:
                return False
            
            request = self.approval_requests[approval_id]
            if request.is_expired():
                request.status = ApprovalStatus.EXPIRED
                return False
            
            request.status = ApprovalStatus.APPROVED
            request.approved_at = time.time()
            request.approved_by = approver
            return True
    
    def deny_operation(self, approval_id: str, reason: str) -> bool:
        """Deny a pending operation."""
        with self._lock:
            if approval_id not in self.approval_requests:
                return False
            
            request = self.approval_requests[approval_id]
            request.status = ApprovalStatus.DENIED
            request.denial_reason = reason
            return True
    
    def register_circuit_breaker(self, name: str, failure_threshold: int = 5,
                                  recovery_timeout: float = 60.0):
        """Register a circuit breaker for an operation type."""
        self.circuit_breakers[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )
    
    def check_circuit_breaker(self, name: str) -> bool:
        """Check if circuit breaker allows execution."""
        if name not in self.circuit_breakers:
            return True
        return self.circuit_breakers[name].can_execute()
    
    def record_circuit_result(self, name: str, success: bool):
        """Record result for circuit breaker."""
        if name not in self.circuit_breakers:
            return
        
        if success:
            self.circuit_breakers[name].record_success()
        else:
            self.circuit_breakers[name].record_failure()
    
    def get_constitution(self) -> Dict:
        """Get full constitution as dictionary."""
        return {
            "agent_id": self.agent_id,
            "rules": {rid: r.to_dict() for rid, r in self.rules.items()},
            "immutable_count": sum(1 for r in self.rules.values() if r.immutable),
            "total_rules": len(self.rules)
        }
    
    def get_violations(self, since: Optional[float] = None,
                       severity: Optional[RulePriority] = None) -> List[ViolationReport]:
        """Get violation reports with optional filtering."""
        violations = self.violations
        
        if since:
            violations = [v for v in violations if v.timestamp > since]
        
        if severity:
            violations = [v for v in violations if v.severity == severity]
        
        return violations
    
    def get_pending_approvals(self) -> List[ApprovalRequest]:
        """Get all pending approval requests."""
        pending = []
        for req in self.approval_requests.values():
            if req.status == ApprovalStatus.PENDING and not req.is_expired():
                pending.append(req)
        return pending
    
    def export_constitution(self, filepath: str):
        """Export constitution to JSON file."""
        with open(filepath, 'w') as f:
            json.dump(self.get_constitution(), f, indent=2)
    
    def import_constitution(self, filepath: str) -> bool:
        """Import constitution from JSON file."""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            for rule_data in data.get("rules", {}).values():
                rule = ConstitutionalRule.from_dict(rule_data)
                # Don't overwrite immutable rules
                if rule.id in self.rules and self.rules[rule.id].immutable:
                    continue
                self.rules[rule.id] = rule
            
            return True
        except Exception:
            return False


class GovernedAgent:
    """
    Wrapper that adds constitutional governance to any agent.
    
    Usage:
        agent = GovernedAgent(base_agent, governance)
        result = agent.execute("delete_file", {"path": "/important/file"})
        # Will block if violates constitution
    """
    
    def __init__(self, agent_id: str, governance: Optional[ConstitutionalGovernance] = None):
        self.agent_id = agent_id
        self.governance = governance or ConstitutionalGovernance(agent_id)
        self.execution_history: List[Dict] = []
    
    def execute(self, operation: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an operation with constitutional checks.
        
        Returns:
            Dict with 'success', 'result', 'violations', 'approval_required'
        """
        # Check circuit breaker
        breaker_name = context.get("circuit_breaker", operation)
        if not self.governance.check_circuit_breaker(breaker_name):
            return {
                "success": False,
                "error": f"Circuit breaker open for {breaker_name}",
                "violations": [],
                "approval_required": False
            }
        
        # Evaluate against constitution
        evaluation = self.governance.evaluate_operation(operation, context)
        
        if not evaluation["allowed"]:
            return {
                "success": False,
                "error": "Operation blocked by constitutional rules",
                "violations": evaluation["violations"],
                "approval_required": False
            }
        
        if evaluation["required_approvals"]:
            return {
                "success": False,
                "error": "Operation requires human approval",
                "violations": [],
                "approval_required": True,
                "approval_ids": evaluation["required_approvals"]
            }
        
        # Log warnings
        for warning in evaluation["warnings"]:
            self.execution_history.append({
                "timestamp": time.time(),
                "operation": operation,
                "warning": warning
            })
        
        # Execute operation (placeholder - would call actual agent)
        try:
            result = {"status": "executed", "operation": operation}
            self.governance.record_circuit_result(breaker_name, True)
            
            self.execution_history.append({
                "timestamp": time.time(),
                "operation": operation,
                "success": True
            })
            
            return {
                "success": True,
                "result": result,
                "violations": [],
                "approval_required": False
            }
        
        except Exception as e:
            self.governance.record_circuit_breaker(breaker_name, False)
            
            self.execution_history.append({
                "timestamp": time.time(),
                "operation": operation,
                "success": False,
                "error": str(e)
            })
            
            return {
                "success": False,
                "error": str(e),
                "violations": [],
                "approval_required": False
            }


# Default constitution export
DEFAULT_CONSTITUTION = {
    "core_principles": [
        {
            "id": "core-001",
            "name": "No Harm to Humans",
            "description": "The agent must not take actions that cause physical, emotional, or financial harm to humans.",
            "priority": "CRITICAL",
            "immutable": True
        },
        {
            "id": "core-002",
            "name": "No Unauthorized System Modifications",
            "description": "The agent must not modify system files, configurations, or infrastructure without explicit approval.",
            "priority": "CRITICAL",
            "immutable": True
        },
        {
            "id": "core-003",
            "name": "Data Privacy Protection",
            "description": "The agent must not expose, share, or process personal data in unauthorized ways.",
            "priority": "CRITICAL",
            "immutable": True
        },
        {
            "id": "core-004",
            "name": "Transparency in Decision Making",
            "description": "The agent must provide clear reasoning for significant decisions.",
            "priority": "HIGH",
            "immutable": True
        }
    ]
}


def create_default_governance(agent_id: str) -> ConstitutionalGovernance:
    """Factory function to create governance with default constitution."""
    return ConstitutionalGovernance(agent_id)
